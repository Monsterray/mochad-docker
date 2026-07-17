# Test Strategy

This read-only inventory records the packaging test baseline before
simplification. Runtimes are CI estimates; regression history is `not recorded`
unless the check directly protects a documented release finding.

## Cross-Repository Ownership

`mochad-docker` owns Dockerfile assembly, image labels, package inventory,
non-root runtime identity, USB group setup, Compose shape, and multiarchitecture
smoke. It does not repeat `mochad-redux` parser, USB, or protocol unit tests.
The daemon owns native behavior; the bridge owns MQTT and Home Assistant.

## Tests and Validation Scripts

| Test or script | Behavior / level | Runtime / requirements | Overlap and history | Action / replacement / removal risk |
| --- | --- | --- | --- | --- |
| `tests/test_container_permissions.py` | static Compose/Dockerfile/workflow rules and OCI archive parser; unit | <1s | Some assertions duplicate runtime container checks; release finding coverage for labels/OCI | Keep metadata/archive logic; replace static runtime assertions with one image harness. Removing loses deterministic release metadata checks. |
| `scripts/validate-image-labels.sh` | inspect OCI labels; container | <1s; built image | Python test validates rules, this validates actual image | Keep actual-image check. |
| `scripts/validate-oci-index.sh` | manifest platform presence; release | <1s; OCI archive/image | Python unit covers parser shape | Keep release multiarch artifact check. |
| `scripts/validate-release.sh` | tag/version/changelog contract; release | <1s | workflow invokes it | Keep release-only. |
| `scripts/validate/version-consistency.sh` | VERSION, ledger, Docker metadata | <1s | lightweight source contract | Keep fast. |

## Current CI Jobs

| Job | Behavior / level | Runtime / requirements | Overlap | Action |
| --- | --- | --- | --- | --- |
| `CI / docker` | Compose, labels, two source builds, per-arch smoke, OCI index; container + multiarch | 15-30m; Docker/QEMU/network | Builds five image variants and repeats metadata checks | Split into fast, container, and multiarch workflows; build one native Redux image for runtime checks. |
| `Release Image / image` | tag validation, multiarch build, SBOM/provenance, GHCR publishing | 10-25m | release-specific | Keep release-only; do not run on PRs. |

## Simplification Contract

Fast CI validates the Python-free packaging metadata, version ledger, Compose
rendering, and static archive parser. Container CI builds exactly one native
`mochad-redux` image, then reuses it for CLI, labels, filesystem, PUID/PGID,
USB_GID, UMASK, and package inventory checks. Multiarchitecture CI builds the
combined OCI index only. Source archive, SBOM/provenance, tag validation, and
hardware behavior remain release gates. No daemon parser tests belong here.
