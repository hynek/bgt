import threading

from contextlib import contextmanager, suppress

import pytest
import structlog

from prometheus_client import REGISTRY

from bgt import IntervalOnlyWakeup, Service, SupervisedService, as_work_factory
from bgt._service import SERVICE_LAST_WORK_UNIT
from bgt.exceptions import SuppressedCrashError


def noop_work():
    """
    Do nothing and report no further work.
    """
    return False


class RecordingWakeup:
    """
    A `Wakeup` that records the calls a service makes on it.
    """

    def __init__(self):
        self.calls = []

    def wait(self, timeout):
        """
        Never wake; report a timeout right away.
        """
        self.calls.append(("wait", timeout))

        return False

    def wake(self):
        """
        Record the wake.
        """
        self.calls.append("wake")

    def close(self):
        """
        Record the close.
        """
        self.calls.append("close")


class TestIntervalOnlyWakeup:
    def test_is_born_woken(self):
        """
        A fresh wakeup starts woken, so a wait-first service runs its first
        work unit at startup.
        """
        assert True is IntervalOnlyWakeup().wait(1000)

    def test_consumes_the_wake(self):
        """
        One wait consumes the wake, so the next wait blocks again instead of
        staying woken forever.
        """
        wakeup = IntervalOnlyWakeup()

        wakeup.wake()

        assert True is wakeup.wait(0.01)
        assert False is wakeup.wait(0.01)

    def test_wake_ends_a_wait(self):
        """
        A wake from another thread ends a wait that would otherwise time out.
        """
        wakeup = IntervalOnlyWakeup()
        # Consume the initial wake, so only the threaded wake can end the wait.
        assert True is wakeup.wait(0)
        threading.Timer(0.01, wakeup.wake).start()

        assert True is wakeup.wait(2)

    def test_close_releases_nothing(self):
        """
        Closing has nothing to release and leaves the wakeup usable.
        """
        wakeup = IntervalOnlyWakeup()

        wakeup.close()

        assert True is wakeup.wait(0)


class TestService:
    def test_run_once_repeats_while_work_reports_more(self):
        """
        Work units repeat while `do_work` returns True and stop when it reports
        no further work.
        """
        calls = []

        def do_work():
            """
            Record the work unit and ask to run twice more.
            """
            calls.append(True)

            return len(calls) < 3

        service = Service.build(
            as_work_factory(do_work),
            name="plain",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )

        service._run_once(do_work, threading.Event())

        assert 3 == len(calls)

    def test_run_once_stops_between_units_when_stop_is_set(self):
        """
        Work stops between work units the moment the stop event is set, even
        while `do_work` still reports more work.
        """
        calls = []

        def do_work():
            """
            Always report more work.
            """
            calls.append(True)

            return True

        service = Service.build(
            as_work_factory(do_work),
            name="plain-stop-between",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )
        stop = threading.Event()
        stop.set()

        service._run_once(do_work, stop)

        assert 1 == len(calls)

    def test_run_once_stamps_the_last_work_unit_gauge(self):
        """
        Every unit stamps the last-work-unit gauge for this service.
        """
        before = SERVICE_LAST_WORK_UNIT.labels(
            name="plain-service"
        )._value.get()
        service = Service.build(
            as_work_factory(noop_work),
            name="plain-service",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )

        service._run_once(noop_work, threading.Event())

        assert (
            before
            < SERVICE_LAST_WORK_UNIT.labels(name="plain-service")._value.get()
        )

    def test_run_returns_without_waiting_when_stopped_mid_work_unit(self):
        """
        A stop request during a work unit ends the run without a wait.
        """
        stop = threading.Event()

        def do_work():
            """
            Request the stop and claim more work.
            """
            stop.set()

            return True

        service = Service.build(
            as_work_factory(do_work),
            name="plain-stop",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )

        service.run(stop)

        assert service.has_completed_cycle

    @pytest.mark.parametrize(
        "bad_kwargs",
        [{"interval": 0}, {"name": ""}],
    )
    def test_build_validates_arguments(self, bad_kwargs):
        """
        Bad intervals and empty names are rejected up front.
        """
        kwargs = {
            "name": "plain",
            "wakeup": IntervalOnlyWakeup(),
            "interval": 30,
        } | bad_kwargs

        with pytest.raises(ValueError):
            Service.build(as_work_factory(noop_work), **kwargs)

    def test_crash_mid_drain_keeps_completed_progress(self):
        """
        A work unit that succeeded counts as progress even when a later work
        unit of the same drain crashes, so the supervisor resets its backoff.
        """
        calls = []

        def do_work():
            """
            Succeed once, then crash.
            """
            calls.append(True)
            if len(calls) > 1:
                raise RuntimeError("second work unit crashed")

            return True

        service = Service.build(
            as_work_factory(do_work),
            name="plain-drain-crash",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )

        with pytest.raises(RuntimeError, match="second work unit crashed"):
            service.run(threading.Event())

        assert service.has_completed_cycle

    def test_crashing_from_birth_still_creates_the_last_work_unit_series(self):
        """
        The last-work-unit series exists from run start, so a staleness alert never
        sits in no-data for a service that cannot complete a work unit.
        """

        def do_work():
            """
            Crash before any work unit completes.
            """
            raise RuntimeError("broken from birth")

        service = Service.build(
            as_work_factory(do_work),
            name="plain-birth-crash",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )

        with pytest.raises(RuntimeError, match="broken from birth"):
            service.run(threading.Event())

        assert 0.0 == REGISTRY.get_sample_value(
            "bgt_service_last_work_unit_timestamp_seconds",
            {"name": "plain-birth-crash"},
        )

    def test_wait_for_wakeup_times_out_without_a_wake(self):
        """
        Without a wake, the wait falls back to the interval timeout.
        """
        wakeup = IntervalOnlyWakeup()
        # Consume the initial wake; this test is about the timeout path.
        assert True is wakeup.wait(0)
        service = Service.build(
            as_work_factory(noop_work),
            name="plain-timeout",
            wakeup=wakeup,
            interval=0.01,
        )

        with structlog.testing.capture_logs() as logs:
            service._wait_for_wakeup()

        assert [] == logs

    def test_wait_for_wakeup_returns_on_a_wake(self):
        """
        A wake ends the wait promptly and is logged.
        """
        wakeup = IntervalOnlyWakeup()
        wakeup.wake()
        service = Service.build(
            as_work_factory(noop_work),
            name="plain-woken",
            wakeup=wakeup,
            interval=30,
        )

        with structlog.testing.capture_logs() as logs:
            service._wait_for_wakeup()

        assert ["service.woken"] == [entry["event"] for entry in logs]

    def test_wake_ends_the_wait_promptly(self):
        """
        `Service.wake()` ends the interval wait, so a stop doesn't sit out
        the interval.
        """
        wakeup = IntervalOnlyWakeup()
        # Consume the initial wake, so only service.wake() can end the wait.
        assert True is wakeup.wait(0)
        service = Service.build(
            as_work_factory(noop_work),
            name="plain-wake",
            wakeup=wakeup,
            interval=30,
        )

        service.wake()
        service._wait_for_wakeup()

    def test_wake_and_close_delegate_to_the_wakeup(self):
        """
        The service passes wakes and the final close through to its wakeup,
        and waits on it with its interval.
        """
        wakeup = RecordingWakeup()
        service = Service.build(
            as_work_factory(noop_work),
            name="plain-delegate",
            wakeup=wakeup,
            interval=30,
        )

        service._wait_for_wakeup()
        service.wake()
        service.close()

        assert [("wait", 30), "wake", "close"] == wakeup.calls

    def test_supervised_service_is_one_handle(self):
        """
        start() runs the service under supervision, and the handle stops it as
        a context manager.
        """
        ran = threading.Event()

        def do_work():
            """
            Signal that a work unit ran.
            """
            ran.set()

            return False

        with SupervisedService.start(
            as_work_factory(do_work),
            name="plain-supervised",
            wakeup=IntervalOnlyWakeup(),
            interval=0.05,
            initial_backoff=0.01,
        ) as handle:
            assert ran.wait(2)
            assert handle.is_running

        assert not handle.is_running

    def test_supervised_service_recovers_from_a_work_unit_error(self):
        """
        A transient error from `do_work` is retried under supervision.
        """
        fail = True
        worked = threading.Event()

        def do_work():
            """
            Fail once, then signal and stop.
            """
            nonlocal fail
            if fail:
                fail = False
                raise RuntimeError("simulated transient do_work failure")

            worked.set()

            return False

        with SupervisedService.start(
            as_work_factory(do_work),
            name="plain-recovers",
            wakeup=IntervalOnlyWakeup(),
            interval=0.05,
            initial_backoff=0.01,
        ) as handle:
            assert worked.wait(2)
            assert handle.is_running

    def test_supervised_service_stops_out_of_a_long_interval(self):
        """
        Stopping wakes the service out of its interval wait instead of
        sitting it out.
        """
        ran = threading.Event()

        def do_work():
            """
            Signal that a work unit ran.
            """
            ran.set()

            return False

        # interval=30: stopping within 2s is only possible if stop wakes the
        # interval wait rather than waiting it out.
        handle = SupervisedService.start(
            as_work_factory(do_work),
            name="plain-long-interval",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
            initial_backoff=0.01,
        )

        assert ran.wait(2)
        assert handle.stop(2)
        assert not handle.is_running


class TestWorkFactory:
    def test_as_work_factory_yields_the_plain_callable(self):
        """
        The wrapped factory yields the callable itself and hands out a fresh
        context manager per call.
        """
        factory = as_work_factory(noop_work)

        with factory() as first, factory() as second:
            assert noop_work is first
            assert noop_work is second

    def test_sets_up_and_cleans_up_around_a_run(self):
        """
        A run enters the factory before the first work unit and exits it when
        the run ends.
        """
        events = []
        stop = threading.Event()

        def do_work():
            """
            Record the work unit and request the stop.
            """
            events.append("work")
            stop.set()

            return False

        @contextmanager
        def work_factory():
            """
            Record setup and cleanup around the run.
            """
            events.append("setup")
            try:
                yield do_work
            finally:
                events.append("cleanup")

        service = Service.build(
            work_factory,
            name="factory-lifecycle",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )

        service.run(stop)

        assert ["setup", "work", "cleanup"] == events

    def test_cleanup_runs_on_a_crash(self):
        """
        A crashing work unit still unwinds through the factory's cleanup, and
        the crash propagates.
        """
        events = []

        def crashing_work():
            """
            Crash the work unit.
            """
            raise RuntimeError("simulated work crash")

        @contextmanager
        def work_factory():
            """
            Record cleanup on the way out.
            """
            try:
                yield crashing_work
            finally:
                events.append("cleanup")

        service = Service.build(
            work_factory,
            name="factory-crash",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )

        with pytest.raises(RuntimeError, match="simulated work crash"):
            service.run(threading.Event())

        assert ["cleanup"] == events

    def test_reenters_the_factory_per_run(self):
        """
        A crash restart calls the factory again.
        """
        setups = []
        worked = threading.Event()

        def do_work():
            """
            Crash the first run's work unit, then signal and stop.
            """
            if len(setups) < 2:
                raise RuntimeError("simulated transient failure")
            worked.set()

            return False

        @contextmanager
        def work_factory():
            """
            Count the setups.
            """
            setups.append(True)
            yield do_work

        with SupervisedService.start(
            work_factory,
            name="factory-reenter",
            wakeup=IntervalOnlyWakeup(),
            interval=0.05,
            initial_backoff=0.01,
        ):
            assert worked.wait(1)

        assert 2 == len(setups)

    def test_suppressed_crash_is_raised(self):
        """
        A factory that swallows the run's crash raises SuppressedCrashError
        instead of ending the run silently.
        """

        def crashing_work():
            """
            Crash the work unit.
            """
            raise RuntimeError("simulated work crash")

        @contextmanager
        def swallowing_factory():
            """
            Swallow the crash, as a well-meaning user might.
            """
            with suppress(RuntimeError):
                yield crashing_work

        service = Service.build(
            swallowing_factory,
            name="factory-swallow",
            wakeup=IntervalOnlyWakeup(),
            interval=30,
        )

        with pytest.raises(SuppressedCrashError):
            service.run(threading.Event())
