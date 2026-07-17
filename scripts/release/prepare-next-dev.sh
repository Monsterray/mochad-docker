#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
next_release="${1:-}"

if ! [[ "$next_release" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Usage: $0 <next-release-version>" >&2
    exit 64
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "FAIL: next-development preparation requires a clean working tree" >&2
    exit 1
fi

version="${next_release}-dev"
printf '%s\n' "$version" > VERSION
scripts/release/sync-version-files.sh

temporary="$(mktemp "${TMPDIR:-/tmp}/mochad-docker-changelog.XXXXXX")"
awk -v heading="## [$version] - Unreleased" '
    $0 == "## [Unreleased]" { print heading; next }
    { print }
' CHANGELOG.md > "$temporary"
mv "$temporary" CHANGELOG.md

evidence="validation/releases/v${next_release}.md"
if [ ! -f "$evidence" ]; then
    sed -e "s/^# Release Evidence: vX.Y.Z/# Release Evidence: v$next_release/" \
        -e "s/^- Release:$/- Release: v$next_release/" \
        validation/releases/template.md > "$evidence"
fi

scripts/validate/version-consistency.sh
echo "Prepared $version. Review release/versions.env before release work. No tag, push, publish, or release was created."
