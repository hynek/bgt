# Core API

## Batteries-included

Reach for these first:
[`SupervisedService`][bgt.SupervisedService] composes a service and its supervisor, starts the loop in a background thread, and offers `stop()`, `is_running`, and a context manager.

::: bgt
    options:
      members:
        - SupervisedService
        - IntervalOnlyWakeup
        - as_work_factory


## Escape hatches

You do not have to use *bgt*'s supervision:
[`Service`][bgt.Service] is a plain blocking loop that you can run on a thread you own, for example your main thread, under a process supervisor.

You can also implement a [`Loop`][bgt.typing.Loop] of your own.

::: bgt
    options:
      members:
        - Service
        - Supervisor


## Exceptions

::: bgt.exceptions
    options:
      members:
        - SuppressedCrashError
