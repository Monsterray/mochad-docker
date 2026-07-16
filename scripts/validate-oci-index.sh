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
    index = json.load(archive.extractfile(archive.getmember("index.json")))

    def read_blob(digest):
        algorithm, value = digest.split(":", 1)
        return json.load(archive.extractfile(archive.getmember(f"blobs/{algorithm}/{value}")))

    platforms = set()
    for descriptor in index.get("manifests", []):
        platform = descriptor.get("platform", {})
        operating_system = platform.get("os")
        architecture = platform.get("architecture")

        # OCI descriptors may omit platform metadata. Buildx still records it
        # in the image configuration referenced by the manifest.
        if not operating_system or not architecture:
            manifest = read_blob(descriptor["digest"])
            config = manifest.get("config", {})
            if "digest" not in config:
                continue
            image_config = read_blob(config["digest"])
            operating_system = image_config.get("os")
            architecture = image_config.get("architecture")

        if operating_system and architecture:
            platforms.add(f"{operating_system}/{architecture}")

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
