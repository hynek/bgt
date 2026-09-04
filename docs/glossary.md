# Glossary

There's a lot of similar terms and proper nouns – let's try to untangle them!


## General concepts

crash-only software { #crash-only }
:   The core idea of crash-only software is that software gets significantly simpler and more robust if you focus on fast recovery after a crash instead of trying to handle all possible errors everywhere.

    With that, **initialization is recovery**.
    It's ["Have You Tried Turning It Off And On Again?"](https://www.youtube.com/watch?v=5UT8RkSmN4k) for applications.

    In *bgt*, a supervised service can crash anytime, as long as its [work factory][bgt.typing.WorkFactory] knows how to initialize all necessary resources.

    The concept is closely related to the [*Let It Crash*](https://wiki.c2.com/?LetItCrash) philosophy in the – famously fault-tolerant – [Erlang](https://www.erlang.org) ecosystem.
    The term was coined by George Candea and Armando Fox in their [*Crash-Only Software*](https://www.usenix.org/conference/hotos-ix/crash-only-software) paper.

microreboot { #microreboot }
:   Microreboots make crash-only software more practical in the real world.

    Usually, you don't want your whole application to crash because one of ten HTTP connection pools went bad.
    But recovering a resource pool can be difficult or impossible (for example, with stuck resources).

    So you "reboot" only a part of your application and reinitialize the resource from scratch.

    Supervised services with work factories lend themselves to microreboots.

    As with crash-only software, there's a [paper by Candea et al.](https://www.usenix.org/conference/osdi-04/microreboot%E2%80%94-technique-cheap-recovery) on it.


## Services

service
:   A background thread running a [`Service`][bgt.Service] in a *loop*.

worker
:   The process that runs *bgt*'s threads and services.


## Loops and progress

loop
:   A long-running, blocking [`Loop.run()`][bgt.typing.Loop.run] that a *supervisor* drives.
    Within *bgt*: a *service*.

loop cycle
:   One pass through a loop's body: wait, then act.

    A service cycle waits for its wakeup and runs work units.
    A loop reports its progress through its [`has_completed_cycle`][bgt.typing.Loop.has_completed_cycle] attribute.

loop run
:   One execution of a loop's `run()`, from start until it returns or crashes.
    The supervisor starts a new loop run after a backoff.

    Therefore, a *loop run* consists of zero (crashed or stopped before first loop cycle) to infinite (never crashes, never exits) *loop cycles*.

interval
:   The upper bound on a loop cycle's wait, if not interrupted by a wakeup.
    It's the maximum wait time between *loop cycles*.


## Work

work unit
:   One call of `do_work`, time-bounded by contract.
    While `do_work` returns `True`, the next *work unit* runs back-to-back within the same loop cycle.

`do_work`
:   The callable that performs one work unit per call.
    It's your code and the reason why *bgt* exists.
    Its signature is the [`DoWork`][bgt.typing.DoWork] protocol.

work factory
:   Makes a loop run's `do_work` and cleans up when the loop run ends.
    It is called at the start of every loop run, so setup is also recovery.
    [`as_work_factory`][bgt.as_work_factory] wraps a plain `do_work` that needs no setup.


## Waking

wakeup
:   The object a service `wait()`s on between loop cycles.
    It can be anything that satisfies [`Wakeup`][bgt.typing.Wakeup].
    *bgt* ships [`IntervalOnlyWakeup`][bgt.IntervalOnlyWakeup], which has no external wake source.
    [*pgbg*](https://pgbg.hynek.me/)'s [`Subscription`][pgbg.Subscription] is one that fires on PostgreSQL `NOTIFY` events.

wake
:   The pending signal that a wakeup's `wait()` consumes by returning `True`.
    [`Wakeup.wake()`][bgt.typing.Wakeup.wake] delivers one, and any number of pending wakes coalesce into one.


## Supervision

supervisor
:  Owns the thread, the backoff, and the restart policy for one *loop*.
   Usually a [`Supervisor`][bgt.Supervisor].

crash
:   A loop run that ends with an exception.

backoff
:   The exponentially growing delay between a crash and the next loop run.
    It resets after a loop run's first completed loop cycle.

stop
:   The cooperative shutdown request.
    [`SupervisedService.stop()`][bgt.SupervisedService.stop] sets the loop's stop event and wakes it.

handle
:   A batteries-included supervised facade:
    [`SupervisedService`][bgt.SupervisedService].
    It offers `stop()`, `is_running`, and a context manager.
