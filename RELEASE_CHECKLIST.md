# Release Checklist

Use this checklist before publishing a GitHub release or Docker image.

## Version

- [ ] Confirm the release tag and Docker `IMAGE_VERSION` are the same version.
- [ ] Update README version badge.
- [ ] Update `CHANGELOG.md`.
- [ ] Tag the release with the same version.

## Verification

- [ ] Run `docker compose config`.
- [ ] Build the Docker image.
- [ ] Record the resolved `mochad-redux` commit SHA and version.
- [ ] Record the resolved Alpine digest and confirm it is the Dockerfile base
  image input, not only an OCI label.
- [ ] Confirm `/usr/share/licenses/mochad-docker/LICENSE.md` is present.
- [ ] Confirm `/usr/share/licenses/mochad-redux/COPYING` is present for release images.
- [ ] Confirm `/usr/share/licenses/mochad-redux/NOTICE` is present for release images.
- [ ] Confirm `/usr/share/licenses/mochad-redux/docs/source-lineage.md` is present for release images.
- [ ] Start the container with USB access.
- [ ] Confirm `nc -vz localhost 1099` succeeds.
- [ ] Confirm the tested upstream `mochad` version or commit is documented.
- [ ] Record release evidence in `RELEASE_EVIDENCE.md` format.

## Publishing

- [ ] Confirm Docker image labels are correct.
- [ ] Confirm the embedded daemon revision label matches the compiled source.
- [ ] Confirm BuildKit SBOM attestation is attached.
- [ ] Confirm BuildKit max-level provenance attestation is attached.
- [ ] Confirm manifest index contains `linux/amd64` and `linux/arm64`.
- [ ] Confirm no secrets, private paths, or local-only USB names are committed.
- [ ] Publish GitHub release notes from `CHANGELOG.md`.
- [ ] Publish Docker image with matching version tag.
