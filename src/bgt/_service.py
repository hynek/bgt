"""
Background service loops and the wakeup they wait on.
"""

import math
import threading

from contextlib import nullcontext
from types import TracebackType
from typing import Self

import attrs
import structlog

from prometheus_client import Gauge

from ._supervisor import Supervisor
from .exceptions import SuppressedCrashError
from .typing import DoWork, Wakeup, WorkFactory


logger = structlog.stdlib.get_logger("bgt")

SERVICE_LAST_WORK_UNIT = Gauge(
    "bgt_service_last_work_unit_timestamp_seconds",
    "Timestamp of a service's last completed work unit",
    ["name"],
)


def _make_set_event() -> threading.Event:
    """
    Return an already-set event: an `IntervalOnlyWakeup` starts "woken".
    """
    event = threading.Event()
    event.set()

    return event


@attrs.define
class IntervalOnlyWakeup:
    """
    The wakeup for a service that has no external wake source.

    It starts woken, so a service's first work unit runs at startup.

    After that, [`wait()`][bgt.IntervalOnlyWakeup.wait] only ever times out
    and the [`Service`][bgt.Service] polls on its own `interval`.
    [`wake()`][bgt.IntervalOnlyWakeup.wake] ends the wait instantly.

    Other wakeups exist: [*pgbg*](https://pgbg.hynek.me/)'s
    [`Subscription`][pgbg.Subscription] wakes a service on PostgreSQL
    `NOTIFY`s, over a single database connection per process.
    """

    _woken: threading.Event = attrs.field(init=False, factory=_make_set_event)

    def wait(self, timeout: float) -> bool:
        """
        Block up to *timeout* seconds.

        Args:
            timeout: Maximum time to wait for a wakeup.

        Return `True` when woken and `False` on a timeout.
        """
        if self._woken.wait(timeout):
            # The wake is consumed here, so the next `wait` blocks again.
            # Edge-triggered, rather than staying woken forever.
            self._woken.clear()
            return True

        return False

    def wake(self) -> None:
        """
        End the current wait and let the loop re-check its stop event.
        """
        self._woken.set()

    def close(self) -> None:
        """
        Release nothing: there is no external source behind this wakeup.
        """


def as_work_factory(do_work: DoWork) -> WorkFactory:
    """
    Wrap a plain *do_work* callable into a
    [`WorkFactory`][bgt.typing.WorkFactory] with no setup or cleanup.

    Args:
        do_work: A callable that performs one bounded work unit.

    Returns:
        A factory that creates a context manager returning *do_work*.
    """
    return lambda: nullcontext(do_work)


@attrs.define
class Service:
    """
    Loop for a background service.

    Runs work units and waits on a [`Wakeup`][bgt.typing.Wakeup] between loop
    cycles.

    Users must create it using [`build()`][bgt.Service.build].
    """

    _interval: float = attrs.field(alias="interval")
    _name: str = attrs.field(alias="name")
    _wakeup: Wakeup = attrs.field(alias="wakeup")
    _work_factory: WorkFactory = attrs.field(alias="work_factory")
    has_completed_cycle: bool = attrs.field(init=False, default=False)

    @classmethod
    def build(
        cls,
        work_factory: WorkFactory,
        *,
        name: str,
        wakeup: Wakeup,
        interval: float = 1.0,
    ) -> Self:
        """
        Validate arguments and build a service, ready to be supervised.

        Hand the result to [`Supervisor.start()`][bgt.Supervisor.start], to
        run it supervised in a background thread.

        Args:
            work_factory:
                See [`WorkFactory`][bgt.typing.WorkFactory] and
                [Services](services.md).

            name:
                Names the service in logs and metrics. Must not be empty.

            wakeup:
                Ends the wait between loop cycles. See
                [`Wakeup`][bgt.typing.Wakeup].
                An [`IntervalOnlyWakeup`][bgt.IntervalOnlyWakeup] polls on
                *interval* alone. [*pgbg*](https://pgbg.hynek.me/)'s
                [`Subscription`][pgbg.Subscription] adds
                notification-driven wakeups.

                !!! warning
                    Do not share this wakeup with another consumer. The service
                    takes exclusive ownership and closes it when supervision
                    ends.

            interval:
                Maximum seconds to wait for a wakeup. The service runs again
                (performs a *loop cycle*) when this interval expires. Must be
                greater than zero.

        Raises:
            ValueError:
                If *interval* or *name* are invalid.
        """
        if interval <= 0 or not math.isfinite(interval):
            msg = "interval must be > 0"
            raise ValueError(msg)

        if not name:
            msg = "name must not be empty"
            raise ValueError(msg)

        return cls(
            interval=interval,
            name=name,
            wakeup=wakeup,
            work_factory=work_factory,
        )

    def run(self, stop: threading.Event) -> None:
        """
        Wait for wakeups and work until *stop* is set.

        Enters the work factory first: it creates the loop run's `do_work`, and
        its cleanup runs when the loop run ends, crash or not.

        Any failure propagates and a clean return means *stop* was set.
        A factory that suppresses the loop run's crash raises
        [`SuppressedCrashError`][bgt.exceptions.SuppressedCrashError] instead.

        Args:
            stop:
                The event the loop exits on.
        """
        self.has_completed_cycle = False
        # Create the series at 0 without clobbering an earlier stamp.
        SERVICE_LAST_WORK_UNIT.labels(name=self._name)
        log = logger.bind(func="service", name=self._name)
        log.info("service.started")

        with self._work_factory() as do_work:
            while not stop.is_set():
                # Each loop cycle waits first. The startup work unit is
                # triggered by the wakeup's initial wake: `IntervalOnlyWakeup`
                # starts woken, and external wakeups deliver one once they
                # are live.
                self._wait_for_wakeup()
                if stop.is_set():
                    break

                self._run_once(do_work, stop)
                self.has_completed_cycle = True

        if not stop.is_set():
            msg = "the work factory suppressed the loop run's crash"
            raise SuppressedCrashError(msg)

        log.info("service.stopped")

    def wake(self) -> None:
        """
        Wake the loop out of its wait so a set stop takes effect promptly.
        """
        self._wakeup.wake()

    def close(self) -> None:
        """
        Release the wakeup.
        """
        self._wakeup.close()

    def _wait_for_wakeup(self) -> None:
        """
        Wait for a wakeup, falling back to the interval timeout.
        """
        if self._wakeup.wait(self._interval):
            logger.debug("service.woken", name=self._name)

    def _run_once(self, do_work: DoWork, stop: threading.Event) -> None:
        """
        Run the work units of one loop cycle.
        """
        while True:
            again = do_work()
            self.has_completed_cycle = True

            SERVICE_LAST_WORK_UNIT.labels(
                name=self._name
            ).set_to_current_time()

            if not again or stop.is_set():
                return


@attrs.frozen
class SupervisedService:
    """
    Handle for a service that runs under supervision.

    Construct via [`start()`][bgt.SupervisedService.start].

    !!! info "See also"
        [Supervised Service Loops](services.md)
    """

    _service: Service = attrs.field(alias="service")
    _supervisor: Supervisor = attrs.field(alias="supervisor")

    @classmethod
    def start(
        cls,
        work_factory: WorkFactory,
        *,
        name: str,
        wakeup: Wakeup,
        interval: float = 1.0,
        initial_backoff: float = 0.1,
    ) -> Self:
        """
        Build a service for *work_factory* and start running it under a
        [`Supervisor`][bgt.Supervisor].

        *name* names the service, the supervisor, its thread, and the restart
        metric's label.

        See [`Service.build()`][bgt.Service.build] for the service arguments and
        [`Supervisor.start()`][bgt.Supervisor.start] for *initial_backoff*.
        """
        service = Service.build(
            work_factory,
            name=name,
            wakeup=wakeup,
            interval=interval,
        )

        return cls(
            service=service,
            supervisor=Supervisor.start(
                service, name=name, initial_backoff=initial_backoff
            ),
        )

    @property
    def is_running(self) -> bool:
        """
        Return whether the supervising thread is still alive.
        """
        return self._supervisor.is_running

    def stop(self, timeout: float | None = None) -> bool:
        """
        Stop the supervision and the service loop.

        See [`Supervisor.stop()`][bgt.Supervisor.stop].
        """
        return self._supervisor.stop(timeout)

    def __enter__(self) -> Self:
        """
        Return the running service itself.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """
        Stop on exit, whether or not the body raised.
        """
        self.stop()
