#!/usr/bin/env sh
set -eu

image="${1:?usage: scripts/validate-image-labels.sh <image>}"

require_label() {
    key="$1"
    value="$(docker image inspect "$image" --format "{{ index .Config.Labels \"$key\" }}")"
    if [ -z "$value" ] || [ "$value" = "<no value>" ]; then
        echo "FAIL: missing label $key" >&2
        exit 1
    fi
    printf '%s=%s\n' "$key" "$value"
}

require_label org.opencontainers.image.title
require_label org.opencontainers.image.description
require_label org.opencontainers.image.version
require_label org.opencontainers.image.created
require_label org.opencontainers.image.revision
require_label org.opencontainers.image.source
require_label org.opencontainers.image.licenses
require_label org.opencontainers.image.base.name
require_label org.opencontainers.image.base.digest
require_label io.github.monsterray.mochad-redux.repository
require_label io.github.monsterray.mochad-redux.revision
require_label io.github.monsterray.mochad-redux.version

revision="$(docker image inspect "$image" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
redux_revision="$(docker image inspect "$image" --format '{{ index .Config.Labels "io.github.monsterray.mochad-redux.revision" }}')"
base_name="$(docker image inspect "$image" --format '{{ index .Config.Labels "org.opencontainers.image.base.name" }}')"
base_digest="$(docker image inspect "$image" --format '{{ index .Config.Labels "org.opencontainers.image.base.digest" }}')"

case "$revision" in
    *[!0-9a-f]*|'')
        echo "FAIL: org.opencontainers.image.revision must be a git SHA" >&2
        exit 1
        ;;
esac

case "$redux_revision" in
    unknown)
        ;;
    *[!0-9a-f]*|'')
        echo "FAIL: io.github.monsterray.mochad-redux.revision must be a git SHA" >&2
        exit 1
        ;;
esac

case "$base_name" in
    *alpine:3.22|*alpine@sha256:*)
        ;;
    *)
        echo "FAIL: org.opencontainers.image.base.name must identify Alpine 3.22" >&2
        exit 1
        ;;
esac

case "$base_digest" in
    sha256:*)
        ;;
    *)
        echo "FAIL: org.opencontainers.image.base.digest must be a sha256 digest" >&2
        exit 1
        ;;
esac

echo "PASS: image labels validated"
