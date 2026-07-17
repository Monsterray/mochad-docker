#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
version="$(tr -d '\n' < VERSION)"
fail() { echo "FAIL: $*" >&2; exit 1; }

[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-dev|-rc[1-9][0-9]*)?$ ]] || fail "VERSION must be a supported semantic version"
set -a
. release/versions.env
set +a

[ "$IMAGE_VERSION" = "$version" ] || fail "IMAGE_VERSION ($IMAGE_VERSION) does not match VERSION ($version)"
[[ "$MOCHAD_REPOSITORY" == https://* ]] || fail "MOCHAD_REPOSITORY must be an HTTPS Git URL"
[[ "$MOCHAD_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "MOCHAD_SOURCE_SHA must be a full 40-character lowercase Git SHA"
[[ "$MOCHAD_REDUX_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-dev|-rc[1-9][0-9]*)?$ ]] || fail "MOCHAD_REDUX_VERSION is not a supported semantic version"
[[ "$ALPINE_IMAGE" =~ ^.+@sha256:[0-9a-f]{64}$ ]] || fail "ALPINE_IMAGE must be digest-qualified"
[[ "$ALPINE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "ALPINE_DIGEST must be a sha256 digest"
[ "${ALPINE_IMAGE##*@}" = "$ALPINE_DIGEST" ] || fail "ALPINE_IMAGE and ALPINE_DIGEST disagree"
[ "$ALPINE_BASE_IMAGE" = "$ALPINE_IMAGE" ] || fail "ALPINE_BASE_IMAGE must match ALPINE_IMAGE"

grep -Fq 'ARG IMAGE_VERSION' Dockerfile || fail "Dockerfile does not accept IMAGE_VERSION"
grep -Fq 'org.opencontainers.image.version="${IMAGE_VERSION}"' Dockerfile || fail "Docker label does not use IMAGE_VERSION"
grep -Fq 'io.github.monsterray.mochad-redux.revision=' Dockerfile || fail "Dockerfile lacks Redux revision label"
grep -Fq '/usr/share/mochad-docker/build-info.json' Dockerfile || fail "Dockerfile does not generate build-info.json"

evidence_version="${version%-dev}"
grep -Fq "## [$version]" CHANGELOG.md || fail "CHANGELOG.md has no heading for $version"
evidence="validation/releases/v${evidence_version}.md"
[ -f "$evidence" ] || fail "missing release evidence template or record: $evidence"
grep -Fq -- "- Release: v$evidence_version" "$evidence" || fail "release evidence does not declare v$evidence_version"

if git describe --tags --exact-match >/dev/null 2>&1; then
    [ "$(git describe --tags --exact-match)" = "v$version" ] || fail "checked-out tag does not match VERSION"
fi
echo "PASS: version consistency completed for mochad-docker $version"
