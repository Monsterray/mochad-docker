# Release Engineering

`VERSION` is the source for the Docker packaging version. The embedded
`mochad-redux` version and SHA remain separate release inputs.

## OCI Metadata

Standard OCI labels identify this packaging repository:

- `org.opencontainers.image.version`
- `org.opencontainers.image.revision`
- `org.opencontainers.image.created`
- `org.opencontainers.image.base.name`
- `org.opencontainers.image.base.digest`

Custom labels identify the embedded daemon:

- `io.github.monsterray.mochad-redux.repository`
- `io.github.monsterray.mochad-redux.revision`
- `io.github.monsterray.mochad-redux.version`

CI validates labels with image inspection. Release timestamps come from the
packaging commit rather than the build wall clock.

## Platforms and Attestations

Release builds target `linux/amd64` and `linux/arm64`. QEMU runs
`mochad --version` and `mochad --help` on each architecture and validates the
combined OCI image index. This is not USB hardware validation.

Tag workflows are configured to publish to:

```text
ghcr.io/monsterray/mochad-docker
```

Published images include BuildKit SBOM and provenance attestations. Pull
requests and manual validation builds do not publish.

## Licenses

Packaging license files are installed under:

```text
/usr/share/licenses/mochad-docker/
```

Audited Redux license, notice, and lineage files are installed separately:

```text
/usr/share/licenses/mochad-redux/
```

Release builds fail if required daemon licensing or source-lineage files are
absent. Consult [release evidence](../RELEASE_EVIDENCE.md) and the
[release checklist](../RELEASE_CHECKLIST.md) before tagging.
