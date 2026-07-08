#!/bin/sh
set -eu

PUID="${PUID:-911}"
PGID="${PGID:-911}"
USB_GID="${USB_GID:-911}"
TZ="${TZ:-UTC}"
UMASK="${UMASK:-022}"

mochad_bool_enabled() {
    case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|on)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

is_number() {
    case "$1" in
        ''|*[!0-9]*)
            return 1
            ;;
        *)
            return 0
            ;;
    esac
}

name_for_gid() {
    awk -F: -v gid="$1" '$3 == gid { print $1; exit }' /etc/group
}

name_for_uid() {
    awk -F: -v uid="$1" '$3 == uid { print $1; exit }' /etc/passwd
}

prepare_runtime_user() {
    if ! is_number "$PUID" || ! is_number "$PGID" || ! is_number "$USB_GID"; then
        echo "[STARTUP] PUID, PGID, and USB_GID must be numeric" >&2
        exit 64
    fi

    if [ "$PUID" = "0" ] || [ "$PGID" = "0" ] || [ "$USB_GID" = "0" ]; then
        echo "[STARTUP] PUID, PGID, and USB_GID must be non-root IDs" >&2
        exit 64
    fi

    if ! umask "$UMASK"; then
        echo "[STARTUP] UMASK must be a valid octal mask" >&2
        exit 64
    fi

    export TZ
    mkdir -p /config

    if [ "$(id -u)" != "0" ]; then
        echo "[STARTUP] running as preconfigured user uid=$(id -u) gid=$(id -g); skipping PUID/PGID initialization"
        return
    fi

    primary_group="$(name_for_gid "$PGID" || true)"
    if [ -z "$primary_group" ]; then
        primary_group="appgroup"
        addgroup -g "$PGID" "$primary_group"
    fi

    runtime_user="$(name_for_uid "$PUID" || true)"
    if [ -z "$runtime_user" ]; then
        runtime_user="appuser"
        adduser -D -H -u "$PUID" -G "$primary_group" "$runtime_user"
    else
        addgroup "$runtime_user" "$primary_group" >/dev/null 2>&1 || true
    fi

    usb_group="$(name_for_gid "$USB_GID" || true)"
    if [ -z "$usb_group" ]; then
        usb_group="x10usb"
        addgroup -g "$USB_GID" "$usb_group"
    fi

    if [ "$usb_group" != "$primary_group" ]; then
        addgroup "$runtime_user" "$usb_group" >/dev/null 2>&1 || true
    fi

    chown -R "$PUID:$PGID" /config
    echo "[STARTUP] prepared /config owner=${PUID}:${PGID} umask=${UMASK} tz=${TZ}"
    echo "[USB] runtime user uid=${PUID} gid=${PGID} supplementary_usb_gid=${USB_GID}"
}

inspect_usb_nodes() {
    if [ ! -d /dev/bus/usb ]; then
        echo "[USB] /dev/bus/usb is not mounted; bind mount /dev/bus/usb and allow cgroup rule c 189:* rwm" >&2
        exit 66
    fi

    usb_nodes="$(find /dev/bus/usb -type c 2>/dev/null || true)"
    if [ -z "$usb_nodes" ]; then
        echo "[USB] no USB device nodes found under /dev/bus/usb" >&2
        exit 66
    fi

    echo "[USB] mapped USB device nodes:"
    printf '%s\n' "$usb_nodes" | while IFS= read -r node; do
        ls -l "$node"
    done

    x10_nodes=""
    for sysdev in /sys/bus/usb/devices/*; do
        [ -r "$sysdev/idVendor" ] || continue
        [ -r "$sysdev/idProduct" ] || continue
        vendor="$(cat "$sysdev/idVendor")"
        product="$(cat "$sysdev/idProduct")"
        case "${vendor}:${product}" in
            0bc7:0001|0bc7:0002)
                [ -r "$sysdev/busnum" ] || continue
                [ -r "$sysdev/devnum" ] || continue
                busnum="$(cat "$sysdev/busnum")"
                devnum="$(cat "$sysdev/devnum")"
                node="$(printf '/dev/bus/usb/%03d/%03d' "$busnum" "$devnum")"
                if [ -e "$node" ]; then
                    x10_nodes="${x10_nodes}${node}
"
                fi
                ;;
        esac
    done

    if [ -z "$x10_nodes" ]; then
        echo "[USB] no CM15A/CM19A controller node found; check USB passthrough and supported vendor/product IDs 0bc7:0001 or 0bc7:0002" >&2
        exit 66
    fi

    echo "[USB] detected X10 controller nodes:"
    printf '%s' "$x10_nodes" | while IFS= read -r node; do
        [ -n "$node" ] || continue
        ls -l "$node"
    done

    if [ "$(id -u)" = "0" ]; then
        # Validate the exact user/group set the daemon will run with. This
        # catches host udev rules that forgot root:x10 ownership or 0660 mode.
        # shellcheck disable=SC2086
        if ! su-exec "$runtime_user" sh -c 'for node in "$@"; do [ -r "$node" ] && [ -w "$node" ] || exit 1; done' sh $x10_nodes; then
            echo "[USB] non-root access failed; set host USB nodes to root:x10 mode 0660 and set USB_GID to the host x10 group id" >&2
            exit 66
        fi
    fi

    echo "[USB] non-root USB access validation passed"
}

prepare_runtime_user
inspect_usb_nodes

MOCHAD_COMMAND="${MOCHAD_COMMAND:-/usr/local/bin/mochad}"

set -- "$MOCHAD_COMMAND"

if mochad_bool_enabled "${MOCHAD_FOREGROUND:-true}"; then
    set -- "$@" "-d"
fi

if mochad_bool_enabled "${MOCHAD_RAW_DATA:-false}"; then
    set -- "$@" "--raw-data"
fi

if [ -n "${MOCHAD_BIND:-}" ]; then
    set -- "$@" "--bind" "$MOCHAD_BIND"
fi

if [ -n "${MOCHAD_PORT:-}" ]; then
    set -- "$@" "--port" "$MOCHAD_PORT"
fi

if mochad_bool_enabled "${MOCHAD_XML_ENABLED:-true}"; then
    set -- "$@" "--enable-xml"
else
    set -- "$@" "--disable-xml"
fi

if [ -n "${MOCHAD_XML_PORT:-}" ]; then
    set -- "$@" "--xml-port" "$MOCHAD_XML_PORT"
fi

if mochad_bool_enabled "${MOCHAD_OPENREMOTE_ENABLED:-true}"; then
    set -- "$@" "--enable-openremote"
else
    set -- "$@" "--disable-openremote"
fi

if [ -n "${MOCHAD_OPENREMOTE_PORT:-}" ]; then
    set -- "$@" "--openremote-port" "$MOCHAD_OPENREMOTE_PORT"
fi

if [ "${MOCHAD_SHOW_VERSION:-false}" = "true" ]; then
    set -- "$@" "--version"
fi

if [ "${MOCHAD_SHOW_HELP:-false}" = "true" ]; then
    set -- "$@" "--help"
fi

if [ -n "${MOCHAD_ARGS:-}" ]; then
    # Intentionally allow shell word splitting for operator-supplied flags.
    # Do not put secrets in MOCHAD_ARGS.
    # shellcheck disable=SC2086
    set -- "$@" $MOCHAD_ARGS
fi

if [ "$(id -u)" = "0" ]; then
    exec su-exec "$runtime_user" "$@"
fi

exec "$@"
