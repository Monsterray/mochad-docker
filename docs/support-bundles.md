# Sanitized Support Bundles

The host-side collector creates a bounded diagnostic archive for
`mochad-docker`. It is not installed in the image, does not modify a running
container, and never uploads its output.

The collector records only packaging-owned facts:

- allowlisted OCI labels, digest, architecture, entrypoint, and default command;
- allowlisted `/usr/share/mochad-docker/build-info.json` fields;
- sanitized Compose structure without values, secrets, host paths, or
  `MOCHAD_ARGS`;
- pseudonymized runtime UID, GID, and supplementary groups;
- permissions for explicitly selected `/dev/bus/usb/NNN/NNN` nodes;
- explicitly requested container logs, limited to 1,000 lines and 128 KiB.

It does not collect Redux protocol diagnostics. Use the Redux-owned collector
for daemon `hello`, `health`, transport, or X10 protocol facts.

## Preview

Preview the collection plan without contacting Docker:

```sh
python3 scripts/support/collect-support-bundle.py \
  --image x10-mochad:local \
  --output mochad-docker-support.tar.gz \
  --dry-run
```

## Collect

Collect immutable image information:

```sh
python3 scripts/support/collect-support-bundle.py \
  --image x10-mochad:local \
  --output mochad-docker-support.tar.gz
```

Add selected runtime facts:

```sh
python3 scripts/support/collect-support-bundle.py \
  --image x10-mochad:local \
  --container mochad \
  --compose-file docker-compose.yml \
  --usb-device /dev/bus/usb/001/002 \
  --include-logs \
  --log-lines 200 \
  --output mochad-docker-support.tar.gz
```

USB nodes must be explicitly named and must match
`/dev/bus/usb/NNN/NNN`. The collector never enumerates `/config`, Docker
credentials, secrets, environment values, or host files.

## Safety

The temporary staging directory is mode `0700`; files and the final archive
are mode `0600`. Operational identities are replaced with aliases such as
`CONTAINER_1`, `USER_1`, `GROUP_1`, `HOST_1`, and `PATH_1`.

The collector scans staged filenames, staged contents, the completed
manifest, and every member of the completed archive. Suspected credentials,
private keys, credential filenames, binary data, or unresolved high-entropy
values fail the operation and delete the distributable archive.

The scanner is intentionally conservative, but it is not proof that sharing
is safe. Extract the archive in a private location and review every entry plus
`manifest.json` before sending it to anyone. A support bundle is sanitized
diagnostic evidence, not a backup.

## Tests

The deterministic test suite does not require Docker:

```sh
python3 -m unittest tests.test_support_bundle -v
```

An optional explicit smoke test can inspect an existing non-production image:

```sh
MOCHAD_DOCKER_SMOKE_IMAGE=x10-mochad:local \
  python3 -m unittest \
  tests.test_support_bundle.SupportBundleTests.test_optional_docker_smoke -v
```
