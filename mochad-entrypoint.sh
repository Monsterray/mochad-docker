#!/bin/sh
set -eu

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

exec "$@"
