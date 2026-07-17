#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
release="${1:-}"

if ! [[ "$release" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-rc[1-9][0-9]*)?$ ]]; then
    echo "Usage: $0 <release-version>" >&2
    exit 64
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "FAIL: release preparation requires a clean working tree" >&2
    exit 1
fi

previous="$(tr -d '\n' < VERSION)"
today="$(date +%F)"
printf '%s\n' "$release" > VERSION
scripts/release/sync-version-files.sh

temporary="$(mktemp "${TMPDIR:-/tmp}/mochad-docker-changelog.XXXXXX")"
awk -v previous="$previous" -v release="$release" -v today="$today" '
    $0 == "## [" previous "] - Unreleased" { print "## [" release "] - " today; next }
    { print }
' CHANGELOG.md > "$temporary"
mv "$temporary" CHANGELOG.md
if ! grep -Fq "## [$release]" CHANGELOG.md; then
    temporary="$(mktemp "${TMPDIR:-/tmp}/mochad-docker-changelog.XXXXXX")"
    awk -v heading="## [$release] - $today" '
        !inserted && /^## / { print heading; print ""; print "- Release preparation in progress."; print ""; inserted = 1 }
        { print }
    ' CHANGELOG.md > "$temporary"
    mv "$temporary" CHANGELOG.md
fi

evidence="validation/releases/v${release}.md"
if [ ! -f "$evidence" ]; then
    sed -e "s/^# Release Evidence: vX.Y.Z/# Release Evidence: v$release/" \
        -e "s/^- Release:$/- Release: v$release/" \
        -e "s/^- Date:$/- Date: $today/" \
        validation/releases/template.md > "$evidence"
fi

scripts/validate/version-consistency.sh
echo "Prepared $release. Review release/versions.env, then validate and commit. No tag, push, publish, or release was created."
