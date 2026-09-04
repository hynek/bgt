import threading

from contextlib import AbstractContextManager
from typing import Protocol


class Wakeup(Protocol):
    """
    A source that wakes a service between work units.

    *bgt* ships [`IntervalOnlyWakeup`][bgt.IntervalOnlyWakeup], which has no
    external wake source. Other wakeups exist: for example,
    [*pgbg*](https://pgbg.hynek.me/)'s [`Subscription`][pgbg.Subscription]
    wakes a service on PostgreSQL `NOTIFY`s.
    """

    def wait(self, timeout: float) -> bool:
        """
        Wait up to *timeout* seconds for a wake.

        Args:
            timeout: The maximum number of seconds to wait for a wake.

        Returns:
            `True` when woken and `False` on a timeout. A `True` return
                consumes the pending wake, so the next call blocks again.
        """
        ...

    def wake(self) -> None:
        """
        End the current wait.

        This method must be thread-safe and idempotent. It can run
        concurrently with or after
        [`close()`][bgt.typing.Wakeup.close]. It must not raise an exception
        in either case. After `close()`, it must do nothing.
        """
        ...

    def close(self) -> None:
        """
        Release the wakeup.

        After this method returns, [`wake()`][bgt.typing.Wakeup.wake] must
        remain a safe no-op.
        """
        ...


class Loop(Protocol):
    """
    A loop that a [`Supervisor`][bgt.Supervisor] keeps alive.

    Only relevant for people implementing their own loops.

    Within *bgt*, implemented by [`Service`][bgt.Service].
    [*pgbg*](https://pgbg.hynek.me/) implements it for its leader-elected
    service and its `NOTIFY` dispatcher.
    """

    @property
    def has_completed_cycle(self) -> bool:
        """
        Whether the current loop run has completed at least one full loop
        cycle.
        """
        ...

    def run(self, stop: threading.Event) -> None:
        """
        Run the loop.

        Block until the stop event is set (a clean return) or something
        breaks (an exception the supervisor restarts after).

        **Must** set `has_completed_cycle` to `False` before any fallible work
        and True once a full loop cycle has completed. This way the supervisor
        can tell a crash after real progress (reset the backoff) from one that
        never got going (grow backoff).

        Args:
            stop: Event that signals the loop to stop.
        """
        ...

    def wake(self) -> None:
        """
        Nudge the loop out of any wait so it re-checks the stop event.

        Called by `Supervisor.stop` right after it sets the event, so a healthy
        loop parked in a wait exits immediately instead of sitting out its poll
        interval.

        Also called before a crash restart, so a wait-first loop's next loop
        run starts its first work unit immediately.

        A loop whose wait can't be interrupted from another thread may make
        this a no-op and accept interval-bounded stop latency.

        This method must be thread-safe and idempotent. It can run
        concurrently with or after [`close()`][bgt.typing.Loop.close]. It
        must not raise an exception in either case. After `close()`, it must
        do nothing.
        """
        ...

    def close(self) -> None:
        """
        Release resources once, when the supervisor stops for good.

        Is **not** run on restarts.

        After this method returns, [`wake()`][bgt.typing.Loop.wake] must
        remain a safe no-op.
        """
        ...


class DoWork(Protocol):
    """
    Callable signature for a service's work.

    Must do **one bounded work unit** (for example, one batch) for responsive
    shutdowns and accurate work-unit metrics.
    """

    def __call__(self) -> bool:
        """
        Perform one bounded work unit.

        Returns:
            `True` to be run again immediately, or `False` to wait for the
                next wakeup.
        """
        ...


class WorkFactory(Protocol):
    """
    Factory for a loop run's work callable.

    Each time a new loop run starts, this factory creates a context manager
    that is immediately entered. Once the loop run exits or crashes, the
    context manager is exited.

    The context manager must produce the work callable that is run by the
    loop. The work callable may return `True` if it wants to run again
    immediately.

    The context manager must not suppress the loop run's exception: the
    service raises
    [`SuppressedCrashError`][bgt.exceptions.SuppressedCrashError] when it
    does, because the supervisor would otherwise mistake the crash for a clean
    stop.

    [`as_work_factory`][bgt.as_work_factory] wraps a plain
    [`DoWork`][bgt.typing.DoWork] callable that needs no setup or cleanup.
    """

    def __call__(self) -> AbstractContextManager[DoWork]:
        """
        Create the work for one loop run.

        Returns:
            A context manager that produces the work callable.
        """
        ...
