# Release Checklist

Use this checklist before publishing a GitHub release or Docker image.

## Version

- [ ] Update Docker `IMAGE_VERSION`.
- [ ] Update README version badge.
- [ ] Update `CHANGELOG.md`.
- [ ] Tag the release with the same version.

## Verification

- [ ] Run `docker compose config`.
- [ ] Build the Docker image.
- [ ] Start the container with USB access.
- [ ] Confirm `nc -vz localhost 1099` succeeds.
- [ ] Confirm the tested upstream `mochad` version or commit is documented.

## Publishing

- [ ] Confirm Docker image labels are correct.
- [ ] Confirm no secrets, private paths, or local-only USB names are committed.
- [ ] Publish GitHub release notes from `CHANGELOG.md`.
- [ ] Publish Docker image with matching version tag.
