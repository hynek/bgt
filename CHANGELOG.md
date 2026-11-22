# Changelog

This file records notable changes to *bgt*.

The format is based on [Keep a Changelog](https://keepachangelog.com/).
This project uses [Calendar Versioning](https://calver.org/).

The first version number is the release year.
The second number starts at 1 each year and increases with each release.
The third number identifies emergency releases from older branches.

> [!IMPORTANT]
> This package is in beta.
> The code is production-grade, but APIs can change before the first stable release.

<!-- changelog follows -->


## [Unreleased](https://github.com/hynek/bgt/compare/26.3.0...HEAD)

### Added

- `bgt.SupervisedService.start_stream()` that starts a `bgt.StreamService` for when you need to write the loop yourself, but still want a supervised background thread.

  It runs a generator function and passes it a stop [`threading.Event`](https://docs.python.org/3/library/threading.html#threading.Event) that you can pass into other APIs (like [`watchfiles.watch()`](https://watchfiles.helpmanual.io/api/watch/)) – or check yourself.

  Each `yield` counts as a completed [work unit](https://bgt.hynek.me/stable/glossary/#work).
  Yield regularly, even when there is no work, because otherwise a quiet but healthy stream looks stuck.
  [#8](https://github.com/hynek/bgt/pull/8)


### Changed

- If a custom loop returns while its stop event is unset, `bgt.Supervisor` now logs an error and restarts the loop.
  Earlier versions stopped supervision.


## [26.3.0](https://github.com/hynek/bgt/compare/26.2.0...26.3.0) - 2026-11-14

### Added

- `bgt.as_async_work_factory()` adapter for async work units that don't require setup, cleanup, or control over the event loop.
  [#6](https://github.com/hynek/bgt/pull/6)


## [26.2.0](https://github.com/hynek/bgt/compare/26.1.0...26.2.0) - 2026-09-06

### Changed

- Just docs!


## [26.1.0](https://github.com/hynek/bgt/tree/26.1.0) - 2026-09-04

### Added

- Initial public release.
  It is the supervision layer from [*pgbg*](https://github.com/hynek/pgbg) to allow using it without a PostgreSQL database.
  The Prometheus metrics and the *structlog* logger are named `bgt` instead of `pgbg`.
