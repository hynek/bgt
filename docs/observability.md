# Observability

Structured log events go to the `bgt` logger via [*structlog*](https://www.structlog.org).


## Prometheus metrics

*bgt* is thoroughly instrumented for the [Prometheus](https://prometheus.io) metrics and monitoring system.

`bgt_supervisor_restarts_total{name}`
:   Crashes that the supervisor restarted after.
    The supervisor never gives up on a crashing loop[^base], so a chronic failure shows up as a sustained restart rate, not as a dead process.
    Alert on the rate.

    The series exists at 0 from the supervisor's start, so the very first restart is already visible to `rate()`.

[^base]: Except for a `BaseException` such as `SystemExit`: that ends supervision for good and is only visible in the logs.

`bgt_service_last_work_unit_timestamp_seconds{name}`
:   Timestamp of the service's last completed work unit.
    Staleness per service is the alert signal.

    The series exists at 0 from the start of a service's first loop run, without clobbering an earlier stamp.
    Therefore, a staleness alert never sits in no-data for a service that cannot complete a work unit.
