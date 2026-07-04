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
