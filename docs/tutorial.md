# Getting Started

## Installation

*bgt* is available on [PyPI under the `bgt` name](https://pypi.org/project/bgt/):

```console
$ uv pip install bgt
```


## Background threads

In its simplest configuration, *bgt* allows you to start a thread that runs a function at a fixed interval in the background.
Since real-world software crashes eventually, *bgt* is designed around **failure recovery** and does its best to keep everything running, even if your function raises an exception.

So, the following script starts a [`SupervisedService`][bgt.SupervisedService] (a background thread) and runs for 10 seconds or until you interrupt it.
It runs a **loop** that calls the `do_work` function every 2 seconds (ignore the call to `as_work_factory()` for a second).
A single call of `do_work` is a **work unit** and the process that runs *bgt* threads is a **worker**.

In this case, there's a 25% chance for the function to crash and a 50% chance to return `True`:

```python title="indie_thread.py"  hl_lines="16-22 26-31"
--8<-- "docs/examples/indie_thread.py"
```

You should see occasional crashes, but also multiple "did some work!" in quick succession.

This demonstrates two features:

1. Crashes are reported, but the *bgt*-provided background thread with the loop is kept alive.
2. If `do_work` returns `True`, it's run again *immediately*.

It's easy to get excited by fault-tolerance, but the second feature only becomes important once your work units have to stay short, for example for prompt shutdowns (see [thread cancellation](services.md#thread-cancellation)).

--8<-- "includes/thread-loop-tip.md"


## Crash better

We can do a little better still:
since *bgt* is about failure recovery, it tries to encourage you to write [crash-only] software.

And that's why the default shape of work is not a callable, but a factory of [context managers](https://docs.python.org/3/library/stdtypes.html#context-manager-types).
The previous example used [`as_work_factory()`][bgt.as_work_factory] to adapt a plain function to it, but if you write a function that returns a context manager, that context manager is entered at the start of a loop run – and after each crash.

This gives you the ability to "[microreboot](glossary.md#microreboot)" your loop on failures.
That simplifies the logic a lot, since you don't have to write error-prone recovery code.

Same example, except with an init and cleanup:

```python title="indie_with_init.py"  hl_lines="30-36"
--8<-- "docs/examples/indie_with_init.py"
```

Now, you can see a "work init!" at the start of each loop run and a "work cleanup!" after each crash and on application exit.
Your loop can have its own independent lifecycle.

---

And that concludes our quick tour of *bgt*!
Keep reading our topical guides to learn more details of how it works and if there's a proper noun overflow, don't hesitate to check our [glossary](glossary.md).

If you want your threads to wake up on PostgreSQL events, or want only *one* of your processes to do the work at a time, [*pgbg*](https://pgbg.hynek.me/) builds on *bgt* and [its tutorial](https://pgbg.hynek.me/stable/tutorial/) picks up where this one ends.

[crash-only]: glossary.md#crash-only
