# Changelog

All notable changes to this Docker packaging project will be documented in this
file.

## [Unreleased]

### Fixed

- Release builds now compile the exact resolved `mochad-redux` commit recorded
  in OCI metadata and release evidence.
- Release builds now use the exact Alpine digest recorded in OCI metadata.
- CI now runs packaging unit tests and uses current Docker actions with Node 24
  runtimes.
- Release builds fail when required `mochad-redux` licensing and source-lineage
  files are absent.

### Changed

- Runtime images install the `libusb` shared library instead of development
  headers and build tooling.

### Added

- Standalone Dockerfile for building and running upstream `mochad`.
- Standalone compose file with CM19A USB bus mapping.
- Health check using `nc` against TCP port `1099`.
- Debug compose file for attached troubleshooting.
- Environment variables to independently enable or disable the XML and
  OpenRemote listeners while preserving default legacy compatibility.
- Basic GitHub Actions CI for Compose validation and Docker builds from
  upstream `mochad` and `Monsterray/mochad-redux`.
- Docker image publishing readiness documentation and ignore-file hygiene.

## [0.1.0] - Unreleased

- First release candidate baseline.
