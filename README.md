<!-- --8<-- [start:header] -->
# *bgt*

_Fault-tolerant **b**ack**g**round **t**hreads for Python_
<!-- --8<-- [end:header] -->

[![Documentation at ReadTheDocs](https://img.shields.io/badge/Docs-Read%20Them!-black)](https://bgt.hynek.me)
[![License: MIT](https://img.shields.io/badge/license-MIT-C06524)](https://github.com/hynek/bgt/blob/main/LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/bgt)](https://pypi.org/project/bgt/)
[![No AI slop inside.](https://img.shields.io/badge/no-slop-purple)](https://github.com/hynek/bgt/blob/main/.github/AI_POLICY.md)


<!-- --8<-- [start:spiel] -->
POV: you want a framework-agnostic way to reliably run a plain[^non-async] function or method in the background, continuously or with pauses between work units.

[^non-async]: As in: not `async`.

*bgt* comes to the rescue with:

- A **service** that runs your code in a loop and optionally waits between work units.
  It wakes up on a fixed time interval, or as soon as something wakes it.

- A **supervisor** that runs that loop in a **background thread**.
  If your code crashes, the supervisor restarts the loop after an exponential backoff.
  Write [crash-only](https://bgt.hynek.me/stable/glossary/#crash-only) code, *bgt* takes care of the rest.

- Thorough instrumentation via [*structlog*](https://www.structlog.org/) and [Prometheus](https://prometheus.io).

- Framework and platform independence.

*bgt* is the engine underneath [*pgbg*](https://pgbg.hynek.me/), which adds PostgreSQL `LISTEN` / `NOTIFY`-driven wakeups and leader election with automatic failover on top.
If your services should wake up on database events, or only one process at a time should do the work, that's where to look.

*bgt* is **not** a job queue like [Celery](https://docs.celeryq.dev/) or [RQ](https://python-rq.org).
Common use cases include:

- Periodic cleanup duties for expired caches or sessions.
- Flushing buffered metrics or events.
- Processing a continuous stream of data in bounded batches.

---

Here's a service that runs a work unit every two seconds and survives its own crashes:

```python
import bgt


def do_work() -> bool:
    ...  # one bounded work unit; if it crashes, it doesn't crash the loop

    return False  # False = wait for next wakeup; True = run again immediately


with bgt.SupervisedService.start(
    bgt.as_work_factory(do_work),
    name="example",
    wakeup=bgt.IntervalOnlyWakeup(),
    interval=2,
):
    ...  # do_work runs in the background until we leave this block
```

Return `True` from your work unit to be run again immediately.
This keeps work units short, which makes shutdowns prompt.
<!-- --8<-- [end:spiel] -->

Check out our [step-by-step tutorial](https://bgt.hynek.me/stable/tutorial/) to get an instant feel for the features!


## Installation

The package is available on [PyPI under the `bgt` name](https://pypi.org/project/bgt/):

```console
$ uv pip install bgt
```


## Documentation

Full documentation lives at **<https://bgt.hynek.me/>**.


<!-- --8<-- [start:credits] -->
## Credits

*bgt* is written by [Hynek Schlawack](https://hynek.me/) and distributed under the terms of the [MIT license](https://choosealicense.com/licenses/mit/).

The development is kindly supported by my employer [Variomedia AG](https://www.variomedia.de/) and all my fabulous [GitHub Sponsors](https://github.com/sponsors/hynek).
<!-- --8<-- [end:credits] -->
