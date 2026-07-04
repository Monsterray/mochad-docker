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
- Exposes a health check that verifies the TCP listener is accepting
  connections.
- Requires USB access to the X10 controller from the host. For a CM19A, Docker
  needs access to the USB bus where the controller appears, so the compose file
  maps `/dev/bus/usb:/dev/bus/usb` and runs the container with elevated USB
  permissions.
- The compose service name should remain `mochad` so the bridge can use
  `MOCHAD_HOST=mochad`.

## Configuration

Runtime environment variables:

```text
TZ=America/Los_Angeles
MOCHAD_REPOSITORY=https://github.com/Monsterray/mochad-redux.git
MOCHAD_REF=develop
MOCHAD_FOREGROUND=true
MOCHAD_RAW_DATA=false
MOCHAD_BIND=0.0.0.0
MOCHAD_PORT=1099
MOCHAD_XML_PORT=1100
MOCHAD_OPENREMOTE_PORT=1101
MOCHAD_SHOW_VERSION=false
MOCHAD_SHOW_HELP=false
MOCHAD_ARGS=
```

`MOCHAD_FOREGROUND=true` passes `-d`, which keeps `mochad` in the foreground so
Docker can supervise it. `MOCHAD_RAW_DATA=true` passes `--raw-data`.
`MOCHAD_SHOW_VERSION=true` passes `--version`, and `MOCHAD_SHOW_HELP=true`
passes `--help`; those are mainly useful for one-off diagnostics because
`mochad` exits after printing them. `MOCHAD_ARGS` appends operator-supplied
upstream `mochad` arguments; do not put secrets in it.

`MOCHAD_BIND`, `MOCHAD_PORT`, `MOCHAD_XML_PORT`, and
`MOCHAD_OPENREMOTE_PORT` map to `mochad-redux` listener options. Defaults
preserve the historical behavior: `0.0.0.0:1099`, `0.0.0.0:1100`, and
`0.0.0.0:1101`. Ports must be distinct TCP ports from `1` to `65535`.

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
`MOCHAD_REF` may be a branch, tag, or commit SHA.

## Standalone Run

```sh
docker compose up
```

From another shell, verify the TCP listener is reachable:

```sh
nc -vz localhost 1099
```

Expected result: `nc` reports that the connection to port `1099` succeeded.

## Debug Run

```sh
docker compose -f docker-compose-debug.yml up mochad
```

The debug compose file uses host networking and keeps the container attached so
raw mochad logs are easier to inspect.

## License

The Docker packaging is MIT licensed. Built images contain upstream `mochad`,
which is GPL-2.0 licensed. See [LICENSE.md](LICENSE.md).
