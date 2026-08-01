#!/usr/bin/env bash
set -u

KLIPPER_DIR="${KLIPPER_DIR:-$HOME/klipper}"
PRINTER_DATA_DIR="${PRINTER_DATA_DIR:-$HOME/printer_data}"
CONFIG_DIR="${CONFIG_DIR:-$PRINTER_DATA_DIR/config}"
MAINSAIL_DIR="${MAINSAIL_DIR:-$HOME/mainsail}"
PRINTER_CFG="$CONFIG_DIR/printer.cfg"
STATUS=0
EXTRA_NAMES=(probe_progress nozzle_guard start_flow motion_wizard)

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

for name in "${EXTRA_NAMES[@]}"; do
    check "Klipper backend: $name" \
        test -f "$KLIPPER_DIR/klippy/extras/$name.py"
done
check "suite configuration" test -f "$CONFIG_DIR/klippertools.cfg"
check "printer.cfg include" \
    grep -Eq '^[[:space:]]*\[include klippertools\.cfg\]' "$PRINTER_CFG"
check "Mainsail suite build" test -f "$MAINSAIL_DIR/klippertools-build.txt"
check "install state" test -f "$PRINTER_DATA_DIR/klippertools-install-state"

exit "$STATUS"
