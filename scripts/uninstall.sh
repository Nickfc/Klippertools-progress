#!/usr/bin/env bash
set -Eeuo pipefail

SUITE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$SUITE_ROOT/scripts/lifecycle.py" uninstall "$@"
