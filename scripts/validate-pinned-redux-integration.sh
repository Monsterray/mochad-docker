#!/usr/bin/env bash
set -euo pipefail

image="${1:?usage: validate-pinned-redux-integration.sh IMAGE REDUX_SHA REDUX_VERSION}"
redux_sha="${2:?missing exact mochad-redux SHA}"
redux_version="${3:?missing mochad-redux version}"

case "$redux_sha" in
    [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*)
        [[ ${#redux_sha} -eq 40 ]] || {
            echo "FAIL: mochad-redux SHA must contain exactly 40 hexadecimal characters" >&2
            exit 1
        }
        ;;
    *)
        echo "FAIL: mochad-redux SHA must contain exactly 40 hexadecimal characters" >&2
        exit 1
        ;;
esac

echo "[integration] validating pinned mochad-redux image ${image}"

test "$(docker image inspect --format '{{index .Config.Labels "io.github.monsterray.mochad-redux.revision"}}' "$image")" = "$redux_sha"
test "$(docker image inspect --format '{{index .Config.Labels "io.github.monsterray.mochad-redux.version"}}' "$image")" = "$redux_version"
test "$(docker image inspect --format '{{json .Config.Entrypoint}}' "$image")" = '["/sbin/tini","--"]'
test "$(docker image inspect --format '{{json .Config.Cmd}}' "$image")" = '["/usr/local/bin/mochad-entrypoint.sh"]'

docker run --rm --entrypoint /bin/sh "$image" -c \
    'test -x /usr/local/bin/mochad &&
     test -x /usr/local/bin/mochad-entrypoint.sh &&
     test "$(python3 2>/dev/null || true)" = ""'

version_output="$(docker run --rm --entrypoint /usr/local/bin/mochad "$image" --version)"
printf '%s\n' "$version_output"
printf '%s\n' "$version_output" | grep -F "$redux_version" >/dev/null

build_sha="$(docker run --rm --entrypoint /bin/sh "$image" -c \
    "sed -n 's/.*\"mochad_source_sha\": \"\\([0-9a-f]*\\)\".*/\\1/p' /usr/share/mochad-docker/build-info.json")"
test "$build_sha" = "$redux_sha"

workdir="$(mktemp -d)"
cleanup() {
    rm -rf "$workdir" 2>/dev/null || sudo rm -rf "$workdir"
}
trap cleanup EXIT

mkdir -p "$workdir/dev/001" "$workdir/sys/1-1" "$workdir/config"
printf '0bc7\n' > "$workdir/sys/1-1/idVendor"
printf '0002\n' > "$workdir/sys/1-1/idProduct"
printf '1\n' > "$workdir/sys/1-1/busnum"
printf '2\n' > "$workdir/sys/1-1/devnum"

root_command=()
if [[ "$(id -u)" -ne 0 ]]; then
    command -v sudo >/dev/null || {
        echo "FAIL: synthetic USB-node setup requires root or sudo on the isolated runner" >&2
        exit 1
    }
    root_command=(sudo)
fi

"${root_command[@]}" mknod "$workdir/dev/001/002" c 189 2
"${root_command[@]}" chown 0:34567 "$workdir/dev/001/002"
"${root_command[@]}" chmod 0660 "$workdir/dev/001/002"

cat > "$workdir/config/probe.sh" <<'EOF'
#!/bin/sh
printf 'uid=%s\n' "$(id -u)"
printf 'gid=%s\n' "$(id -g)"
printf 'groups=%s\n' "$(id -G)"
printf 'args='
printf ' <%s>' "$@"
printf '\n'
EOF
chmod 0755 "$workdir/config/probe.sh"

probe_output="$(
    docker run --rm \
        --mount "type=bind,src=$workdir/dev,dst=/dev/bus/usb" \
        --mount "type=bind,src=$workdir/sys,dst=/sys/bus/usb/devices,readonly" \
        --mount "type=bind,src=$workdir/config,dst=/config" \
        --env PUID=12345 \
        --env PGID=23456 \
        --env USB_GID=34567 \
        --env MOCHAD_COMMAND=/config/probe.sh \
        "$image"
)"
printf '%s\n' "$probe_output"

printf '%s\n' "$probe_output" | grep -Fx 'uid=12345' >/dev/null
printf '%s\n' "$probe_output" | grep -Fx 'gid=23456' >/dev/null
printf '%s\n' "$probe_output" | grep -E '^groups=.*(^| )34567( |$)' >/dev/null
printf '%s\n' "$probe_output" | grep -F \
    'args= <-d> <--bind> <0.0.0.0> <--port> <1099> <--enable-xml> <--xml-port> <1100> <--enable-openremote> <--openremote-port> <1101>' \
    >/dev/null

echo "PASS: pinned mochad-redux image integration"
