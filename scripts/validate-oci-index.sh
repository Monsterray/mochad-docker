#!/usr/bin/env sh
set -eu

usage() {
    echo "usage: scripts/validate-oci-index.sh <image>" >&2
    echo "       scripts/validate-oci-index.sh --archive <oci-layout.tar>" >&2
    exit 64
}

if [ "${1:-}" = "--archive" ]; then
    archive="${2:-}"
    [ -n "$archive" ] && [ -f "$archive" ] || usage

    python3 - "$archive" <<'PY'
import json
import sys
import tarfile

with tarfile.open(sys.argv[1], "r") as archive:
    member = archive.getmember("index.json")
    index = json.load(archive.extractfile(member))

platforms = {
    f'{manifest.get("platform", {}).get("os")}/{manifest.get("platform", {}).get("architecture")}'
    for manifest in index.get("manifests", [])
}
required = {"linux/amd64", "linux/arm64"}
missing = required - platforms
if missing:
    raise SystemExit(f"FAIL: OCI index missing {', '.join(sorted(missing))} manifest(s)")

print("PASS: OCI archive contains linux/amd64 and linux/arm64")
PY
    exit 0
fi

image="${1:-}"
[ -n "$image" ] || usage

inspect="$(docker buildx imagetools inspect "$image")"
printf '%s\n' "$inspect"

printf '%s\n' "$inspect" | grep -q 'linux/amd64' || {
    echo "FAIL: OCI index missing linux/amd64 manifest" >&2
    exit 1
}

printf '%s\n' "$inspect" | grep -q 'linux/arm64' || {
    echo "FAIL: OCI index missing linux/arm64 manifest" >&2
    exit 1
}

echo "PASS: OCI index contains linux/amd64 and linux/arm64"
