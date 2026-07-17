#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
version="$(tr -d '\n' < VERSION)"

if ! [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-dev|-rc[1-9][0-9]*)?$ ]]; then
    echo "FAIL: VERSION is not a supported semantic version: $version" >&2
    exit 1
fi

temporary="$(mktemp "${TMPDIR:-/tmp}/mochad-docker-versions.XXXXXX")"
sed "s/^IMAGE_VERSION=.*/IMAGE_VERSION=$version/" release/versions.env > "$temporary"
mv "$temporary" release/versions.env
echo "Updated release/versions.env from VERSION ($version)"
