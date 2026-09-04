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


## [Unreleased](https://github.com/hynek/bgt/tree/main)

### Added

- Initial public release.
  The supervision layer was extracted from [*pgbg*](https://github.com/hynek/pgbg) 26.1.0:
  `bgt.Supervisor`, `bgt.Service`, `bgt.SupervisedService`, `bgt.IntervalOnlyWakeup`, `bgt.as_work_factory`, `bgt.exceptions.SuppressedCrashError`, and the protocols in `bgt.typing`.
  The Prometheus metrics and the *structlog* logger are named `bgt` instead of `pgbg`.


## Prehistory

Before *bgt* existed, this code shipped as part of *pgbg*.
See [its changelog](https://github.com/hynek/pgbg/blob/main/CHANGELOG.md) for the time before the split.
