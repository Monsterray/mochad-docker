# Configuration

The `.env` file supplies Compose build inputs and runtime environment
variables. Build inputs are consumed only by `docker compose build`.

## Build Inputs

```text
MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git
MOCHAD_REF=develop
MOCHAD_SOURCE_SHA=unknown
IMAGE_VERSION=0.4.0
ALPINE_BASE_IMAGE=alpine:3.22
ALPINE_DIGEST=unknown
MOCHAD_REDUX_REVISION=unknown
MOCHAD_REDUX_VERSION=unknown
REQUIRE_AUDITED_SOURCE=false
```

`MOCHAD_REF` may be a branch, tag, or commit SHA. `MOCHAD_COMMIT` is a
deprecated compatibility alias used only when `MOCHAD_REF` is unset. Release
builds use a full Redux SHA and digest-qualified Alpine image.

```sh
MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git \
MOCHAD_REF=<full-commit-sha> \
docker compose build --no-cache
```

Resolved inputs are recorded in OCI labels and
`/usr/share/mochad-docker/build-info.json`.

## Runtime Environment

```text
TZ=UTC
PUID=911
PGID=911
USB_GID=auto
USB_DEBUG=false
UMASK=022
MOCHAD_FOREGROUND=true
MOCHAD_RAW_DATA=false
MOCHAD_BIND=0.0.0.0
MOCHAD_PORT=1099
MOCHAD_XML_ENABLED=true
MOCHAD_XML_PORT=1100
MOCHAD_OPENREMOTE_ENABLED=true
MOCHAD_OPENREMOTE_PORT=1101
MOCHAD_SHOW_VERSION=false
MOCHAD_SHOW_HELP=false
MOCHAD_ARGS=
```

`USB_GID` is independent from `PGID`. `auto` reads the numeric owner group
from a detected CM15A or CM19A device node. An explicit value must match the
host group that owns the mapped controller.

`MOCHAD_FOREGROUND=true` passes `-d`. `MOCHAD_RAW_DATA=true` passes
`--raw-data`. `MOCHAD_SHOW_VERSION` and `MOCHAD_SHOW_HELP` are one-shot
diagnostics because the daemon exits after printing. `MOCHAD_ARGS` appends
operator-supplied daemon arguments and must not contain secrets.

Listener defaults preserve historical behavior:

```text
main        0.0.0.0:1099
xmlsocket   0.0.0.0:1100
openremote  0.0.0.0:1101
```

Enabled ports must be distinct values from `1` to `65535`.

## USB Permissions

Recommended host nodes are `root:x10` mode `0660`. With `USB_GID=auto`, the
entrypoint creates a supplementary group matching that numeric GID, inspects
the controller node, validates access, and then permanently drops privileges.

If Compose `user:` is set, initialization is bypassed. The volume must already
be owned correctly and `group_add` must supply the USB node's group.

## IPv6

Set `MOCHAD_BIND=::` for all IPv6 interfaces or `MOCHAD_BIND=::1` for loopback:

```sh
MOCHAD_BIND=:: docker compose up
```

This changes the in-container listener. Host IPv6 publishing also requires
Docker daemon and host network support. The daemon requests IPv4-mapped
dual-stack operation, but kernel policy may refuse it. Startup logs report the
actual result.

## Local and Published Images

Local development uses the Compose `build:` block. A published image can
replace it after confirming that the matching tag exists in GHCR:

```yaml
image: ghcr.io/monsterray/mochad-docker:0.4.0
```

Do not treat a README example as proof that a tag has been published.
