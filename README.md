# mochad Docker Image

![Status](https://img.shields.io/badge/status-integration%20testing-yellow)
![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/packaging%20license-MIT-green)

This image builds and runs `mochad`, the TCP daemon that talks to the X10 USB
controller.

This repository is the mochad Docker project only. The MQTT bridge is a
separate project and connects to this container over TCP at `mochad:1099` or a
published host port.

The image defaults to the maintained `mochad-redux` repository. The Dockerfile
can build a different repository, branch, tag, or commit by setting
`MOCHAD_REPOSITORY` and `MOCHAD_REF`, but the bridge project does not pin
`mochad`.

Packaging version: `0.1.0`

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

Runtime environment variables:

```text
TZ=America/Los_Angeles
PUID=911
PGID=911
USB_GID=auto
USB_DEBUG=false
UMASK=022
MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git
MOCHAD_REF=develop
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

## Docker Image

The compose file builds the image locally for development and hardware testing.
When published images are enabled later, the intended image name is:

```text
ghcr.io/monsterray/mochad-docker
```

To use a published image in the future, replace the compose `build:` block with
an `image:` reference such as:

```yaml
image: ghcr.io/monsterray/mochad-docker:0.1.0
```

No GitHub Container Registry publishing workflow is enabled yet.

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

The Docker packaging is MIT licensed. Built images contain upstream `mochad`,
which is GPL-2.0 licensed. See [LICENSE.md](LICENSE.md).
