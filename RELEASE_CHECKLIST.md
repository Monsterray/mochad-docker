# Release Checklist

Use this checklist before publishing a GitHub release or Docker image.

## Version

- [ ] Confirm `VERSION`, the Docker `IMAGE_VERSION` defaults, the README badge,
  and the documented image reference all contain the intended version.
- [ ] Replace the versioned changelog section's `Unreleased` marker with the
  release date in `YYYY-MM-DD` form and keep new work under the top-level
  `Unreleased` section.
- [ ] Run `scripts/validate-release.sh vX.Y.Z /tmp/release-notes.md` and inspect
  the extracted notes.
- [ ] Confirm the matching `mochad-redux` `vX.Y.Z` tag exists and reports the
  same plain semantic version before tagging this repository.
- [ ] Create the exact validated `vX.Y.Z` tag only after all verification is
  complete.

## Verification

- [ ] Run `docker compose config`.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `sh -n mochad-entrypoint.sh scripts/*.sh`.
- [ ] Build the Docker image.
- [ ] Record the resolved `mochad-redux` commit SHA and version.
- [ ] Confirm the tagged build resolved `mochad-redux` from the matching release
  tag rather than a moving branch.
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
- [ ] Push the validated version tag and confirm the workflow publishes only the
  matching GHCR version tag.
- [ ] Confirm image publication completes before GitHub Release creation.
- [ ] Confirm the GitHub Release is marked latest and its notes match the
  versioned `CHANGELOG.md` section.
- [ ] Re-run the tag workflow only when intentionally updating the existing
  release; it must not create a duplicate GitHub Release.
