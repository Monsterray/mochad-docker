# Changelog

All notable changes to this Docker packaging project will be documented in this
file.

## [Unreleased]

### Added

- Standalone Dockerfile for building and running upstream `mochad`.
- Standalone compose file with CM19A USB bus mapping.
- Health check using `nc` against TCP port `1099`.
- Debug compose file for attached troubleshooting.
- Environment variables to independently enable or disable the XML and
  OpenRemote listeners while preserving default legacy compatibility.

## [0.1.0] - Unreleased

- First release candidate baseline.
