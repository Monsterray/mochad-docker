#!/bin/sh

set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 <vX.Y.Z tag> [release-notes-output]" >&2
    exit 2
fi

tag="$1"
notes_file="${2:-}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
root_dir="$(dirname -- "$script_dir")"
version_file="${VERSION_FILE:-$root_dir/VERSION}"
changelog_file="${CHANGELOG_FILE:-$root_dir/CHANGELOG.md}"

if [ ! -f "$version_file" ]; then
    echo "Version file not found: $version_file" >&2
    exit 1
fi

version="$(cat "$version_file")"
version_lines="$(wc -l < "$version_file" | tr -d '[:space:]')"
value_lines="$(printf '%s\n' "$version" | wc -l | tr -d '[:space:]')"

if [ "$version_lines" != "1" ] || [ "$value_lines" != "1" ]; then
    echo "VERSION must contain exactly one newline-terminated line" >&2
    exit 1
fi

if ! printf '%s\n' "$version" | grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'; then
    echo "VERSION is not a canonical X.Y.Z version: $version" >&2
    exit 1
fi

expected_tag="v$version"
if [ "$tag" != "$expected_tag" ]; then
    echo "Release tag $tag does not exactly match packaging version $version (expected $expected_tag)" >&2
    exit 1
fi

if [ ! -f "$changelog_file" ]; then
    echo "Changelog not found: $changelog_file" >&2
    exit 1
fi

section_heading="$(awk -v prefix="## [$version] - " '
    index($0, prefix) == 1 {
        date = substr($0, length(prefix) + 1)
        if (date ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) {
            print
            exit
        }
    }
' "$changelog_file")"
if [ -z "$section_heading" ]; then
    echo "CHANGELOG.md must date the $version release as YYYY-MM-DD before tagging" >&2
    exit 1
fi
notes="$(awk -v heading="$section_heading" '
    $0 == heading { found = 1; next }
    found && /^## / { exit }
    found { print }
    END { if (!found) exit 2 }
' "$changelog_file")" || {
    echo "Missing changelog section: $section_heading" >&2
    exit 1
}

if ! printf '%s\n' "$notes" | grep -q '[^[:space:]]'; then
    echo "Changelog section is empty: $section_heading" >&2
    exit 1
fi

if [ -n "$notes_file" ]; then
    printf '%s\n' "$notes" > "$notes_file"
fi

printf '%s\n' "$version"
