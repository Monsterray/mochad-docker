# mochad Docker Image

![Status](https://img.shields.io/badge/status-release%20candidate-yellow)
![Version](https://img.shields.io/badge/version-0.4.0-blue)
![License](https://img.shields.io/badge/packaging%20license-MIT-green)

This image builds and runs `mochad`, the TCP daemon that talks to the X10 USB
controller.

This repository is the mochad Docker project only. The MQTT bridge is a
separate project and connects to this container over TCP at `mochad:1099` or a
published host port.

Local Compose builds default to the maintained `mochad-redux` integration branch
for development. The Dockerfile can build a different repository, branch, tag,
or commit with `MOCHAD_REPOSITORY` and `MOCHAD_REF`. Release CI resolves and
builds an exact `mochad-redux` commit and Alpine digest; it never publishes an
image from a moving branch reference.

Packaging version: `0.4.0`

## Image Metadata

OCI labels describe the Docker packaging repository, not the embedded daemon:

- `org.opencontainers.image.version` is the `mochad-docker` packaging version.
- `org.opencontainers.image.revision` is the `mochad-docker` Git commit.
- `org.opencontainers.image.created` is derived from the packaging commit date.
- `org.opencontainers.image.base.name` and
  `org.opencontainers.image.base.digest` identify the exact Alpine base image
  used by release builds.

The embedded daemon is tracked separately with custom labels:

- `io.github.monsterray.mochad-redux.repository`
- `io.github.monsterray.mochad-redux.revision`
- `io.github.monsterray.mochad-redux.version`

CI validates these labels with `docker image inspect`. Multi-platform CI builds
`linux/amd64` and `linux/arm64`, runs `mochad --version` and `mochad --help` on
each architecture, and verifies the combined OCI image index contains both
platform manifests. QEMU validation proves startup diagnostics execute on the
target architecture; it does not validate USB hardware behavior.

## Runtime Contract

- `mochad-redux` listens on TCP port `1099` by default.
- It also opens auxiliary ports `1100` and `1101` for legacy client
  compatibility by default.
- Port `1100` is the legacy Flash XMLSocket-compatible listener. It changes
  event framing from newline-delimited to NUL-delimited for legacy clients, but
  it does not provide structured XML. New integrations, including
  `mochad-mqtt-bridge`, should use the main listener on port `1099`.
- Exposes a health check that verifies the TCP listener is accepting
  connections.
- Requires USB access to the X10 controller from the host. For a CM19A, Docker
  needs access to the USB bus where the controller appears. The compose file
  bind mounts `/dev/bus/usb:/dev/bus/usb` and grants USB character devices with
  `device_cgroup_rules: ["c 189:* rwm"]`.
- The container starts as root only long enough to prepare `/config`, create the
  runtime user/group, inspect USB node permissions, and verify non-root USB
  access. It then drops privileges before starting `mochad`.
- Application binaries remain owned by `root:root`; only `/config` is owned by
  `PUID:PGID`.
- The compose service name should remain `mochad` so the bridge can use
  `MOCHAD_HOST=mochad`.

## Configuration

The `.env` file supplies both Compose build inputs and runtime environment
variables. Build inputs are consumed only by `docker compose build`; changing
them does not alter an already-built image.

Build inputs:

```text
MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git
MOCHAD_REF=develop
IMAGE_VERSION=0.4.0
ALPINE_BASE_IMAGE=alpine:3.22
ALPINE_DIGEST=unknown
MOCHAD_REDUX_REVISION=unknown
MOCHAD_REDUX_VERSION=unknown
REQUIRE_AUDITED_SOURCE=false
```

Runtime environment variables:

```text
TZ=America/Los_Angeles
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

`PUID`, `PGID`, `TZ`, and `UMASK` use the same convention as the MQTT bridge
image. Defaults are `911`, `911`, `UTC` in the image, and `022`.

`USB_GID` is separate from `PGID`. The default `USB_GID=auto` detects the
numeric group ID from the detected CM15A/CM19A USB device node. You can also set
it explicitly to the numeric group ID that owns the host USB device nodes.

A recommended host setup is:

```sh
sudo groupadd --system x10
getent group x10
```

Configure host udev rules so X10 USB nodes are owned by `root:x10` with mode
`0660`. With `USB_GID=auto`, the container reads the numeric `x10` group ID
from the device node. To set it explicitly, use the numeric value from
`getent group x10`; for example, `USB_GID=1005`. The native `mochad-redux` udev
rules use that model.

Set `USB_DEBUG=true` to print every mapped `/dev/bus/usb` node during startup.
By default, startup logs show only the detected X10 controller node to avoid
noisy restart logs.

If Compose `user:` is set, Docker bypasses the entrypoint's `PUID`/`PGID`
initialization. In that mode, pre-own mounted volumes and add the USB group
explicitly with `group_add`.

`MOCHAD_FOREGROUND=true` passes `-d`, which keeps `mochad` in the foreground so
Docker can supervise it. `MOCHAD_RAW_DATA=true` passes `--raw-data`.
`MOCHAD_SHOW_VERSION=true` passes `--version`, and `MOCHAD_SHOW_HELP=true`
passes `--help`; those are mainly useful for one-off diagnostics because
`mochad` exits after printing them. `MOCHAD_ARGS` appends operator-supplied
upstream `mochad` arguments; do not put secrets in it.

`MOCHAD_BIND`, `MOCHAD_PORT`, `MOCHAD_XML_PORT`, and
`MOCHAD_OPENREMOTE_PORT` map to `mochad-redux` listener options.
`MOCHAD_XML_ENABLED` and `MOCHAD_OPENREMOTE_ENABLED` can disable the legacy
auxiliary listeners independently. Defaults preserve the historical behavior:
`0.0.0.0:1099`, `0.0.0.0:1100`, and `0.0.0.0:1101`. Enabled listener ports
must be distinct TCP ports from `1` to `65535`.

For IPv6, set `MOCHAD_BIND=::` for all IPv6 interfaces or `MOCHAD_BIND=::1`
for IPv6 loopback. `mochad-redux` asks the operating system for dual-stack
IPv4-mapped behavior when binding to IPv6, but host kernel policy may still
restrict this.

Example:

```sh
MOCHAD_BIND=:: docker compose up
```

This configures the listener inside the container. Publishing the service on a
host IPv6 address also depends on Docker daemon IPv6 support and the host
network configuration. If IPv6 publishing is not enabled on the host, keep
`MOCHAD_BIND=0.0.0.0` for IPv4-only deployments.

Startup logs report each listener separately, including address family and
dual-stack status:

```text
[TCP] listener ready name=main address=:: port=1099 family=ipv6 dual_stack=enabled
```

If the log reports `dual_stack=failed`, the container or host kernel did not
allow IPv4-mapped IPv6 sockets even though `mochad-redux` requested them.

## Local Build

```sh
docker compose build
```

To test a specific branch of `mochad-redux`, build with:

```sh
MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git \
MOCHAD_REF=develop \
BUILD_DATE="$(git show -s --format=%cI HEAD)" \
VCS_REF="$(git rev-parse HEAD)" \
docker compose build --no-cache
```

Or put those values in `.env`:

```text
MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git
MOCHAD_REF=develop
```

The Dockerfile clones the source inside the build container, so
`MOCHAD_REPOSITORY` should be a Git URL that the Docker builder can reach.
`MOCHAD_REF` may be a branch, tag, or commit SHA. `MOCHAD_COMMIT` is a
deprecated compatibility alias and is only used when `MOCHAD_REF` is not set.
Use `docker compose build --no-cache` when changing refs so Docker does not
reuse an older clone layer.

For a repeatable local build, set `MOCHAD_REF` to a full commit SHA and set
`ALPINE_BASE_IMAGE` to `docker.io/library/alpine@sha256:<digest>`. Release CI
does this automatically and records both immutable inputs in OCI labels.

## Docker Image

The compose file builds the image locally for development and hardware testing.
The release workflow is configured to publish the image for a tag that exactly
matches the packaging version, currently `v0.4.0`, to:

```text
ghcr.io/monsterray/mochad-docker
```

Once that tag has successfully completed the release workflow, a published image
can be selected by replacing the compose `build:` block with this `image:`
reference:

```yaml
image: ghcr.io/monsterray/mochad-docker:0.4.0
```

The tag workflow is configured to publish `linux/amd64` and `linux/arm64`
images to GHCR with BuildKit SBOM and max-level provenance attestations, then
create or update the matching GitHub Release from `CHANGELOG.md`. A README
reference is not evidence that an image has been published; confirm the version
tag in GHCR before pulling it. Manual workflow runs and pull requests build and
validate without publishing. Release evidence requirements are listed in
[RELEASE_EVIDENCE.md](RELEASE_EVIDENCE.md).

Tagged image builds embed the matching `mochad-redux` tag and verify that its
reported version is identical. Publish the Redux release tag before pushing the
same Docker packaging tag. Manual non-publishing builds continue to validate
the configured development reference.

## Standalone Run

```sh
docker compose up
```

From another shell, verify the TCP listener is reachable:

```sh
nc -vz localhost 1099
```

Expected result: `nc` reports that the connection to port `1099` succeeded.

At startup, the container prints the mapped `/dev/bus/usb` device nodes and
fails before launching `mochad` if the non-root runtime user cannot read and
write them.

## Debug Run

```sh
docker compose -f docker-compose-debug.yml up mochad
```

The debug compose file uses host networking and keeps the container attached so
raw mochad logs are easier to inspect.

## License

The Docker packaging is MIT licensed. Built images contain `mochad-redux`,
which is GPL-3.0-or-later licensed after the audited source-lineage closure.
Images install packaging license files under
`/usr/share/licenses/mochad-docker/` and daemon license, notice, and lineage
files under `/usr/share/licenses/mochad-redux/`. Release builds fail if the
required daemon licensing or source-lineage files are absent. See
[LICENSE.md](LICENSE.md).
