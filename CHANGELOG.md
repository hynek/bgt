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


## [Unreleased](https://github.com/hynek/bgt/compare/26.2.0...HEAD)


## [26.2.0](https://github.com/hynek/bgt/compare/26.1.0...26.2.0) - 2026-09-06

### Changed

- Just docs!


## [26.1.0](https://github.com/hynek/bgt/tree/26.1.0) - 2026-09-04

### Added

- Initial public release.
  It is the supervision layer from [*pgbg*](https://github.com/hynek/pgbg) to allow using it without a PostgreSQL database.
  The Prometheus metrics and the *structlog* logger are named `bgt` instead of `pgbg`.
