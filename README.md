# mochad Docker Image

![Status](https://img.shields.io/badge/status-integration%20testing-yellow)
![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/packaging%20license-MIT-green)

This image builds and runs `mochad`, the TCP daemon that talks to the X10 USB
controller.

This repository is the mochad Docker project only. The MQTT bridge is a
separate project and connects to this container over TCP at `mochad:1099` or a
published host port.

The image has been tested with `mochad` 0.1.18. The Dockerfile can build a
different upstream commit by setting `MOCHAD_COMMIT`, but the bridge project
does not pin `mochad`.

Packaging version: `0.1.0`

## Runtime Contract

- Upstream `mochad` listens on TCP port `1099`.
- Upstream also opens auxiliary ports `1100` and `1101` for legacy client
  compatibility.
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
MOCHAD_FOREGROUND=true
MOCHAD_RAW_DATA=false
MOCHAD_SHOW_VERSION=false
MOCHAD_SHOW_HELP=false
MOCHAD_ARGS=
MOCHAD_PORT=1099
```

`MOCHAD_FOREGROUND=true` passes `-d`, which keeps `mochad` in the foreground so
Docker can supervise it. `MOCHAD_RAW_DATA=true` passes `--raw-data`.
`MOCHAD_SHOW_VERSION=true` passes `--version`, and `MOCHAD_SHOW_HELP=true`
passes `--help`; those are mainly useful for one-off diagnostics because
`mochad` exits after printing them. `MOCHAD_ARGS` appends operator-supplied
upstream `mochad` arguments; do not put secrets in it.

Upstream `mochad` 0.1.18 hardcodes its internal TCP listener to `1099`.
It also hardcodes auxiliary listener ports `1100` and `1101`. `MOCHAD_PORT`
controls the host port published by Docker Compose for internal port `1099`,
not the daemon's internal listening port.

Daemon port and bind-address environment variables are not supported by
upstream `mochad` 0.1.18. Do not add `MOCHAD_BIND`, `MOCHAD_LISTEN_PORT`, or
similar variables until this project intentionally maintains a patched upstream
fork.

## Local Build

```sh
docker compose build
```

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
