#!/usr/bin/env bash
set -u

KLIPPER_DIR="${KLIPPER_DIR:-$HOME/klipper}"
PRINTER_DATA_DIR="${PRINTER_DATA_DIR:-$HOME/printer_data}"
CONFIG_DIR="${CONFIG_DIR:-$PRINTER_DATA_DIR/config}"
MAINSAIL_DIR="${MAINSAIL_DIR:-$HOME/mainsail}"
PRINTER_CFG="$CONFIG_DIR/printer.cfg"
STATUS=0

check() {
    local label=$1
    shift
    if "$@"; then
        printf '[ok]   %s\n' "$label"
    else
        printf '[miss] %s\n' "$label"
        STATUS=1
    fi
}

check "Klipper backend" \
    test -f "$KLIPPER_DIR/klippy/extras/probe_progress.py"
check "plugin configuration" \
    test -f "$CONFIG_DIR/probe_progress.cfg"
check "printer.cfg include" \
    grep -Eq '^[[:space:]]*\[include probe_progress\.cfg\]' "$PRINTER_CFG"
check "Mainsail card build" \
    test -f "$MAINSAIL_DIR/probe-progress-build.txt"
check "install state" \
    test -f "$PRINTER_DATA_DIR/probe-progress-install-state"

exit "$STATUS"
