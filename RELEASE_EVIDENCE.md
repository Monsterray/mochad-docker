# Release Evidence

Record these fields for every published `mochad-docker` image.

Use only recorded output from CI, `docker buildx imagetools inspect`, and
`docker image inspect`. Do not infer USB hardware behavior from QEMU builds.

## Required Fields

- Packaging SHA:
- Docker packaging version:
- `mochad-redux` repository:
- `mochad-redux` SHA:
- `mochad-redux` version:
- Alpine image:
- Alpine digest:
- `linux/amd64` platform digest:
- `linux/arm64` platform digest:
- Manifest digest:
- OCI labels:
- Installed package list:
- SBOM location:
- Provenance attestation location:
- Packaging license path: `/usr/share/licenses/mochad-docker/LICENSE.md`
- Daemon license path: `/usr/share/licenses/mochad-redux/COPYING`
- Daemon notice path: `/usr/share/licenses/mochad-redux/NOTICE`
- Daemon source lineage path: `/usr/share/licenses/mochad-redux/docs/source-lineage.md`

## Validation Commands

```sh
docker buildx imagetools inspect ghcr.io/monsterray/mochad-docker:<version>
docker image inspect ghcr.io/monsterray/mochad-docker:<version>
docker run --rm --entrypoint sh ghcr.io/monsterray/mochad-docker:<version> -c \
  'find /usr/share/licenses -maxdepth 4 -type f -print | sort'
```

Hardware validation must be recorded separately with real CM15A or CM19A
controllers.
