# Compatibility

The Docker packaging release and the embedded `mochad-redux` daemon are
separate versioned products. `VERSION` identifies the Docker image release;
the daemon repository, immutable source commit, and daemon version are
recorded in [release/versions.env](../release/versions.env).

| mochad-docker | mochad-redux | Redux source commit | Upstream base |
| --- | --- | --- | --- |
| 0.4.0 | 0.4.0 | `518b100169ce41d318f3a971c9b149c47aa89a5c` | mochad 0.1.18 |

For release builds, use the pinned inputs:

```sh
docker compose --env-file release/versions.env build
```

The resulting image records standard OCI labels for this packaging repository
and `io.github.monsterray.mochad-redux.*` labels for the embedded daemon. It
also contains `/usr/share/mochad-docker/build-info.json` for runtime inspection.

## Version Contract

- `VERSION` is the single editable source for the packaging version.
- Version files use `0.5.0`, `0.5.0-dev`, or `0.5.0-rc1`; Git tags use `v0.5.0`.
- `release/versions.env` must use the same `IMAGE_VERSION` and a full 40-digit
  Redux commit SHA. It is intentionally reviewed alongside a release.
- `scripts/release/prepare-release.sh` and
  `scripts/release/prepare-next-dev.sh` prepare version, changelog, and
  evidence files only. They never commit, tag, push, or publish.
