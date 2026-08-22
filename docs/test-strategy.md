# Test Strategy

## Ownership

`mochad-docker` tests packaging: source pinning, image construction, runtime
identity, USB group setup, Compose configuration, OCI metadata, package
inventory, and architecture manifests. It does not repeat `mochad-redux`
parser, protocol, or USB lifecycle tests, and it does not test MQTT or Home
Assistant behavior.

## Test Levels

- Packaging unit tests validate Compose and Dockerfile contracts, release
  inputs, version consistency, OCI metadata parsing, backups, and sanitized
  support bundles.
- Container validation builds both the default upstream source and the exact
  resolved `mochad-redux` source, then checks CLI startup, source identity,
  labels, entrypoint behavior, permissions, writable paths, and packages.
- Multiarchitecture validation builds and runs CLI smoke checks for
  `linux/amd64` and `linux/arm64`, then validates the combined OCI index.
- Release validation adds immutable tags, SBOM and provenance attestations,
  license payloads, and release evidence.
- CM15A and CM19A USB operation remains separate hardware evidence. QEMU and
  container startup do not prove controller access.

## Pull Request Gate

The `CI` workflow runs packaging tests, Compose rendering, version checks,
upstream and pinned-Redux image builds, labels, exact-SHA integration, per-
architecture smoke checks, and OCI-index validation. Each built artifact has a
different contract; removing one requires replacement evidence for that
contract rather than a lower build count alone.

The tag-only `Release Image` workflow owns publishing. Pull requests and normal
branch pushes do not publish images or releases.

## Develop Maintenance Record: 2026-08-22

Baseline `6fa1ecb29d3f7bfdd4e6a6ece0c75d7996a53f52` includes PRs #9 and #10.
The support-bundle collector now redacts quoted JSON-style credential values
without matching its own replacement output. Keep the focused redaction tests
when changing collection or serialization.

An older `test-simplification/mochad-docker` branch was reviewed and retired.
Its ownership inventory became this document, but its workflow replacement was
not used because it removed current upstream-source and exact pinned-Redux
build coverage and renamed established checks. Improve CI only from current
`develop`, preserving those contracts and proving replacement checks before
changing branch protection.

The reviewed redaction, documentation, and superseded simplification branches
were deleted after their surviving work merged. Do not recreate them or copy
their old workflow files back into `.github/workflows/`.

## Regression Boundaries

Keep deterministic coverage for exact Redux SHA selection, standalone Compose
rendering, non-root identity, `PUID`/`PGID`/`USB_GID`/`UMASK`, USB device-group
handling, OCI labels, license trees, runtime package selection, and both target
architectures. Record unavailable Docker execution as `NOT RUN` and physical
USB behavior as `HARDWARE REQUIRED`.
