#!/usr/bin/env sh
set -eu

image="${1:?usage: scripts/validate-oci-index.sh <image>}"

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
