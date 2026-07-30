# mochad-docker Agent Instructions

Workspace `AGENTS.md` defines safety, evidence, machine, and Git boundaries.
This file adds Docker-packaging invariants.
In the shared workspace, conditional routing is under `../docs/agent/`.

## Invariants

- This repository packages a pinned mochad source input; it does not own daemon
  protocol behavior.
- Keep packaging version, embedded Redux version, Redux SHA, and Alpine base
  identity distinct.
- Preserve documented build arguments, entrypoint behavior, ports, non-root
  runtime, PUID/PGID/UMASK handling, USB supplementary group behavior, OCI
  labels, and license paths.
- Docker builds must consume the standalone Redux build/install contract, not
  parent-workspace files or old source paths.
- Do not duplicate Redux unit/parser tests or bridge/Home Assistant behavior.

## Validation Entry Points

Use `.validation/capabilities.json` to select the profile. Start with ShellCheck,
Compose rendering, release-input validation, and packaging unit tests.

Image, runtime identity, filesystem, USB group, labels, package inventory, and
multiarchitecture checks run on the isolated Docker runner. Build once per
commit and reuse the image where practical.

## Prohibited Actions

- Do not use production Docker, MQTT, Home Assistant, credentials, volumes, or
  USB devices for validation.
- Do not change Redux source behavior from this repository.
- Do not use moving branch names as release source inputs.
- Do not claim QEMU or container startup as USB hardware validation.
- Do not add privileged mode or broad capabilities when device mapping and the
  documented USB group contract are sufficient.
