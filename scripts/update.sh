#!/usr/bin/env bash
set -Eeuo pipefail

SUITE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_TARGET="${KLIPPERTOOLS_DIR:-$HOME/klippertools}"

if [[ ${1:-} == --source-target ]]; then
    [[ $# -ge 2 ]] || { printf 'Error: --source-target needs a path\n' >&2; exit 2; }
    SOURCE_TARGET=$2
    shift 2
fi

exec python3 "$SUITE_ROOT/scripts/lifecycle.py" update \
    --source-target "$SOURCE_TARGET" "$@"
