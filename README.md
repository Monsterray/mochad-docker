# mochad Docker Image

This image builds and runs `mochad`, the TCP daemon that talks to the X10 USB
controller.

This repository is the mochad Docker project only. The MQTT bridge is a
separate project and connects to this container over TCP at `mochad:1099` or a
published host port.

The image has been tested with `mochad` 0.1.18. The Dockerfile can build a
different upstream commit by setting `MOCHAD_COMMIT`, but the bridge project
does not pin `mochad`.

## Runtime Contract

- Listens on TCP port `1099`.
- Exposes a health check that verifies the TCP listener is accepting
  connections.
- Requires USB access to the X10 controller from the host. For a CM19A, Docker
  needs access to the USB bus where the controller appears, so the compose file
  maps `/dev/bus/usb:/dev/bus/usb` and runs the container with elevated USB
  permissions.
- The compose service name should remain `mochad` so the bridge can use
  `MOCHAD_HOST=mochad`.

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
