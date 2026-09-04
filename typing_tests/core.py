import threading

from collections.abc import Iterator
from contextlib import contextmanager
from typing import assert_type

from bgt import (
    IntervalOnlyWakeup,
    Service,
    SupervisedService,
    Supervisor,
    as_work_factory,
)
from bgt.typing import DoWork, Loop, Wakeup, WorkFactory


def process_orders() -> bool:
    return False


work: DoWork = process_orders
work_factory: WorkFactory = as_work_factory(work)


@contextmanager
def make_work() -> Iterator[DoWork]:
    yield process_orders


ctx_work_factory: WorkFactory = make_work

interval_only_wakeup = IntervalOnlyWakeup()
poll_wakeup: Wakeup = interval_only_wakeup

assert_type(interval_only_wakeup.wait(1.0), bool)
interval_only_wakeup.wake()
interval_only_wakeup.close()


class NullLoop:
    has_completed_cycle: bool = False

    def run(self, stop: threading.Event) -> None:
        pass

    def wake(self) -> None:
        pass

    def close(self) -> None:
        pass


custom_loop: Loop = NullLoop()

supervisor = Supervisor.start(custom_loop, name="stats", initial_backoff=0.1)

assert_type(supervisor.is_running, bool)
assert_type(supervisor.stop(1.0), bool)

with Supervisor.start(custom_loop, name="stats") as held:
    assert_type(held, Supervisor)


class CustomWakeup:
    def wait(self, timeout: float) -> bool:
        return False

    def wake(self) -> None:
        pass

    def close(self) -> None:
        pass


custom_wakeup: Wakeup = CustomWakeup()

plain = Service.build(
    work_factory,
    name="stats",
    wakeup=custom_wakeup,
    interval=5.0,
)
plain_loop: Loop = plain

running_plain = SupervisedService.start(
    work_factory,
    name="stats",
    wakeup=IntervalOnlyWakeup(),
    interval=5.0,
    initial_backoff=0.1,
)

assert_type(running_plain.is_running, bool)
assert_type(running_plain.stop(5.0), bool)

with SupervisedService.start(
    make_work, name="stats", wakeup=IntervalOnlyWakeup()
) as plain_handle:
    assert_type(plain_handle, SupervisedService)
