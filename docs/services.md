# Supervised Service Loops

!!! abstract ""
    The core task of *bgt* is to reliably run a user-supplied callable repeatedly in the background.

That callable[^callable] we call `do_work` throughout APIs and a call to it is a **work unit**.
The entity that drives your work unit repeatedly is a **service**.

[^callable]: A function, a bound method, a class with a `__call__` method…

A *waiting* service always wakes up regularly via a configurable **interval**.
If the work unit returns `True`, it is run immediately again.
This allows for **bounded runtimes** which are important for prompt shutdowns.
Once the work unit indicates it is done, the service waits again.

A service also takes an object that implements the [`Wakeup`][bgt.typing.Wakeup] protocol which allows for real-time wakeups in addition to the interval.
*bgt* ships with [`IntervalOnlyWakeup`][bgt.IntervalOnlyWakeup] that has no external wake source, so the service wakes up on its interval alone.
Other wakeups exist:
for example, [*pgbg*](https://pgbg.hynek.me/) wakes services up on PostgreSQL `NOTIFY` events.


## Supervision

A plain running [`Service`][bgt.Service] is nothing but a blocking loop.
It's started with its [`run()`][bgt.Service.run] method which repeatedly calls your work unit.
We call one call to `Service.run(stop)` end-to-end a **loop run**.
A loop run ends when the work unit raises an exception or when the supplied `stop` [`threading.Event`][threading.Event] is set from the outside, which signals a graceful shutdown.

Making such a loop reliable is surprisingly difficult, because you have to entangle your business concerns with error handling and service recovery.
[Crash-only design](glossary.md#crash-only) is a lot more robust and allows for cleaner code in your work units.

For that, you wrap your [`Service`][bgt.Service] in a [`Supervisor`][bgt.Supervisor] which runs it in a **background thread** and **restarts** it whenever it dies.
A supervisor owns the thread, retry policy, and final cleanup for a background loop.

The supervisor [reports crashed loop runs](observability.md) and starts a new loop run after an exponential backoff with jitter.
The backoff resets after a loop run completes one healthy loop cycle.

A persistently broken loop crash-loops with backoff and heals as soon as its cause is fixed.
Outside shutdown, every crash is an `ERROR` log, and every restart increments the restart counter (see [Observability](observability.md)).
Alert on the restart rate and on the staleness of the gauges to catch chronic failure.

Only a `BaseException` that is not an `Exception`, such as `SystemExit` or `KeyboardInterrupt`, ends supervision for good.


## Microreboots

Since `Service` takes a *work factory* (a callable that makes a context manager that produces the work callable), you can use it for initialization and cleanup of your work unit's resources.
And since you own the resources in your context manager, they survive for the whole lifetime of the loop run (importantly: *not* per work unit run).

!!! tip
    This allows you to have "loop [microreboots](glossary.md#microreboot)" that in turn allow your work units to be truly [crash-only](glossary.md#crash-only).

*bgt* comes with the [`SupervisedService.start()`][bgt.SupervisedService.start] helper that makes the whole process ergonomic:

```python
def do_work() -> bool:
    """
    Crash-only work unit code goes here.
    """
    ...


@contextmanager
def make_work() -> Generator[DoWork]:
    logger.info("work init!")
    try:
        yield do_work
    finally:
        logger.info("work cleanup!")


with bgt.SupervisedService.start(
    make_work,
    name="example-thread",
    wakeup=bgt.IntervalOnlyWakeup(),
) as svc:
    # do_work runs in the background until we exit this context manager
    ...
```

!!! tip
    See [Getting Started](tutorial.md) for a complete, runnable example.

If you don't need any setup or cleanup work, you can use [`as_work_factory(do_work)`][bgt.as_work_factory] to wrap a plain callable into a no-op factory.


## Lifecycle

[`SupervisedService.stop()`][bgt.SupervisedService.stop] wakes the loop[^via], so a healthy service stops immediately after its current work unit finishes.

[^via]: Via [`Supervisor.stop()`][bgt.Supervisor.stop]

The supervisor can drive anything that satisfies the small [`Loop`][bgt.typing.Loop] protocol:
`run(stop)`, `wake()`, `close()`, and a `has_completed_cycle` attribute.

Within *bgt*, this chapter's [`Service`][bgt.Service] is the only `Loop`.
[*pgbg*](https://pgbg.hynek.me/) implements it for its leader-elected [`ElectedService`][pgbg.ElectedService] and, via an adapter, for its [`NotifyDispatcher`][pgbg.NotifyDispatcher].


## Caveats galore: thread cancellation { #thread-cancellation }

Many caveats throughout the project are caused by the unequivocal fact that it's **impossible** to **safely** and **forcibly** terminate threads in Python.

So for example, shutdown is cooperative.
`stop(timeout)` requests shutdown and waits for the current work unit to finish.
It returns `False` if it remains blocked and there's nothing *bgt* can do about it, except wait some more.

!!! danger
    This is why it's important to keep your work units **bounded** regarding their runtime.
    For bigger workloads, return `True` to be run again immediately, unless the supervisor has been stopped.

    A long-running work unit stalls graceful shutdown, potentially leading to a hard kill by the OS-level supervisor.

---

We are aware of the hacks that make it possible to cancel a thread in Python, but we do not think these hacks have a place in production software.
We do hope, though, that in the age of free-threading, we will get better threading primitives that will improve the situation through a new focus on threads as a viable concurrency primitive.

Also keep in mind that the cancellation in, for example, Go is also strictly cooperative via context cancellation, so this is not a specific Python downside.
