# Changelog

All notable changes to this Docker packaging project will be documented in this
file.

## [Unreleased]

## [0.4.0] - Unreleased

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
- The tag workflow is configured to create or update an idempotent GitHub
  Release from this version's changelog section after the multi-platform image
  is published.

### Changed

- Runtime images install the `libusb` shared library instead of development
  headers and build tooling.
- Packaging version surfaces now identify the `0.4.0` release candidate.

### Fixed

- Release builds now compile the exact resolved `mochad-redux` commit recorded
  in OCI metadata and release evidence.
- Release builds now use the exact Alpine digest recorded in OCI metadata.
- CI now runs packaging unit tests and uses current Docker actions with Node 24
  runtimes.
- Multi-platform CI now validates an exported OCI archive without depending on
  a local registry or loopback-network behavior.
- Release builds fail when required `mochad-redux` licensing and source-lineage
  files are absent.
- Tag publishing now rejects malformed or mismatched tags before authenticating
  to GHCR.
