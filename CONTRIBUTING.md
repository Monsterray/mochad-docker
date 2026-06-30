# Contributing

Thanks for helping improve the mochad Docker packaging.

## Development Rules

- Keep this repository focused on Docker packaging for upstream `mochad`.
- Do not add MQTT bridge code to this project.
- Keep the compose file standalone and based on local files only.
- Document USB permission requirements clearly.
- Never commit credentials, private host paths, or local-only device names.

## Local Checks

When Docker is available, run:

```sh
docker compose config
docker compose build
```

To test a running container:

```sh
nc -vz localhost 1099
```

## Pull Requests

- Keep changes focused.
- Update README and CHANGELOG when packaging behavior changes.
- Note the upstream `mochad` commit or version used for testing.
