#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

path_exists() {
    [[ -e "$1" || -L "$1" ]]
}

read_state() {
    sed -n "s/^$1=//p" "$STATE_FILE" | tail -n 1
}

state_key() {
    local value=${1^^}
    printf '%s' "${value//-/_}"
}

if [[ $EUID -eq 0 ]]; then
    if [[ ${_KLIPPERTOOLS_TEST_ALLOW_ROOT:-0} != 1 || \
          $HOME != /tmp/klippertools-* ]]; then
        fail "run this as the normal Klipper user, not root"
    fi
fi

SUITE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INITIAL_PRINTER_DATA_DIR="${PRINTER_DATA_DIR:-$HOME/printer_data}"
STATE_FILE="$INITIAL_PRINTER_DATA_DIR/klippertools-install-state"
EXTRA_NAMES=(probe_progress nozzle_guard start_flow motion_wizard)
[[ -f "$STATE_FILE" ]] ||
    fail "install state was not found at $STATE_FILE"
[[ -f "$SUITE_ROOT/scripts/configure.py" ]] ||
    fail "configuration helper is missing"
[[ -f "$SUITE_ROOT/scripts/instrument_print_start.py" ]] ||
    fail "StartFlow instrumentation helper is missing"

BACKUP_DIR="$(read_state BACKUP_DIR)"
KLIPPER_DIR="$(read_state KLIPPER_DIR)"
PRINTER_DATA_DIR="$(read_state PRINTER_DATA_DIR)"
CONFIG_DIR="$(read_state CONFIG_DIR)"
MAINSAIL_DIR="$(read_state MAINSAIL_DIR)"
CONFIG_EXISTED="$(read_state CONFIG_EXISTED)"
CONFIG_INCLUDE_ADDED="$(read_state CONFIG_INCLUDE_ADDED)"
PRINT_START_INSTRUMENTED="$(read_state PRINT_START_INSTRUMENTED)"
declare -A EXTRA_EXISTED=()
for name in "${EXTRA_NAMES[@]}"; do
    key="$(state_key "$name")"
    EXTRA_EXISTED[$name]="$(read_state "EXTRA_EXISTED_$key")"
done

case "$BACKUP_DIR" in
    "$HOME/klippertools-backups/"*) ;;
    *) fail "refusing unexpected backup path: $BACKUP_DIR" ;;
esac
for managed_path in "$KLIPPER_DIR" "$PRINTER_DATA_DIR" \
        "$CONFIG_DIR" "$MAINSAIL_DIR"; do
    case "$managed_path" in
        "$HOME"/*) ;;
        *) fail "refusing unexpected managed path: $managed_path" ;;
    esac
done
for value in "$CONFIG_EXISTED" "$CONFIG_INCLUDE_ADDED" \
        "$PRINT_START_INSTRUMENTED" \
        "${EXTRA_EXISTED[@]}"; do
    [[ "$value" == 0 || "$value" == 1 ]] ||
        fail "invalid install state"
done

PRINTER_CFG="$CONFIG_DIR/printer.cfg"
SUITE_CFG="$CONFIG_DIR/klippertools.cfg"
[[ -d "$BACKUP_DIR/mainsail" ]] ||
    fail "original Mainsail backup is missing"
[[ -f "$BACKUP_DIR/printer.cfg" ]] ||
    fail "original printer.cfg backup is missing"
[[ -f "$PRINTER_CFG" ]] || fail "current printer.cfg is missing"
[[ -d "$MAINSAIL_DIR" ]] || fail "current Mainsail directory is missing"
[[ ! -e "$BACKUP_DIR/mainsail-with-klippertools" ]] ||
    fail "uninstall recovery directory already exists"
for name in "${EXTRA_NAMES[@]}"; do
    if [[ ${EXTRA_EXISTED[$name]} == 1 ]]; then
        path_exists "$BACKUP_DIR/$name.py.previous" ||
            fail "previous $name.py is missing"
    fi
done
if [[ "$CONFIG_EXISTED" == 1 ]]; then
    path_exists "$BACKUP_DIR/klippertools.cfg.previous" ||
        fail "previous klippertools.cfg is missing"
fi

cp -a "$PRINTER_CFG" "$BACKUP_DIR/printer.cfg.before-uninstall"
if [[ -f "$MAINSAIL_DIR/config.json" ]]; then
    cp -a "$MAINSAIL_DIR/config.json" "$BACKUP_DIR/config.json.latest"
fi

declare -A EXTRA_MUTATED=()
for name in "${EXTRA_NAMES[@]}"; do
    EXTRA_MUTATED[$name]=0
done
CONFIG_MUTATED=0
PRINTER_MUTATED=0
UI_CUSTOM_MOVED=0
UI_ORIGINAL_RESTORED=0

rollback() {
    local exit_code=$?
    trap - ERR INT TERM
    set +e
    if [[ $UI_ORIGINAL_RESTORED -eq 1 && -d "$MAINSAIL_DIR" ]]; then
        mv "$MAINSAIL_DIR" "$BACKUP_DIR/mainsail"
    fi
    if [[ $UI_CUSTOM_MOVED -eq 1 && \
          -d "$BACKUP_DIR/mainsail-with-klippertools" ]]; then
        mv "$BACKUP_DIR/mainsail-with-klippertools" "$MAINSAIL_DIR"
    fi
    if [[ $CONFIG_MUTATED -eq 1 ]]; then
        if path_exists "$SUITE_CFG"; then
            mv "$SUITE_CFG" "$BACKUP_DIR/klippertools.cfg.previous"
        fi
        if path_exists "$BACKUP_DIR/klippertools.cfg.installed"; then
            mv "$BACKUP_DIR/klippertools.cfg.installed" "$SUITE_CFG"
        fi
    fi
    for name in "${EXTRA_NAMES[@]}"; do
        if [[ ${EXTRA_MUTATED[$name]} -ne 1 ]]; then
            continue
        fi
        local target="$KLIPPER_DIR/klippy/extras/$name.py"
        if path_exists "$target"; then
            mv "$target" "$BACKUP_DIR/$name.py.previous"
        fi
        if path_exists "$BACKUP_DIR/$name.py.installed"; then
            mv "$BACKUP_DIR/$name.py.installed" "$target"
        fi
    done
    if [[ $PRINTER_MUTATED -eq 1 ]]; then
        cp -a "$BACKUP_DIR/printer.cfg.before-uninstall" "$PRINTER_CFG"
    fi
    printf 'Uninstall failed; installed files were restored.\n' >&2
    printf 'Recovery files: %s\n' "$BACKUP_DIR" >&2
    exit "$exit_code"
}
trap rollback ERR INT TERM

PRINTER_MUTATED=1
if [[ "$PRINT_START_INSTRUMENTED" == 1 ]]; then
    python3 "$SUITE_ROOT/scripts/instrument_print_start.py" \
        remove "$PRINTER_CFG" >/dev/null
fi
if [[ "$CONFIG_INCLUDE_ADDED" == 1 ]]; then
    python3 "$SUITE_ROOT/scripts/configure.py" remove "$PRINTER_CFG" \
        >/dev/null
fi

for name in "${EXTRA_NAMES[@]}"; do
    target="$KLIPPER_DIR/klippy/extras/$name.py"
    if path_exists "$target"; then
        mv "$target" "$BACKUP_DIR/$name.py.installed"
    fi
    EXTRA_MUTATED[$name]=1
    if [[ ${EXTRA_EXISTED[$name]} == 1 ]]; then
        mv "$BACKUP_DIR/$name.py.previous" "$target"
    fi
done

if path_exists "$SUITE_CFG"; then
    mv "$SUITE_CFG" "$BACKUP_DIR/klippertools.cfg.installed"
fi
CONFIG_MUTATED=1
if [[ "$CONFIG_EXISTED" == 1 ]]; then
    mv "$BACKUP_DIR/klippertools.cfg.previous" "$SUITE_CFG"
fi

mv "$MAINSAIL_DIR" "$BACKUP_DIR/mainsail-with-klippertools"
UI_CUSTOM_MOVED=1
mv "$BACKUP_DIR/mainsail" "$MAINSAIL_DIR"
UI_ORIGINAL_RESTORED=1
if [[ -f "$BACKUP_DIR/config.json.latest" ]]; then
    cp -a "$BACKUP_DIR/config.json.latest" "$MAINSAIL_DIR/config.json"
fi

mv "$STATE_FILE" "$BACKUP_DIR/install-state.uninstalled"
trap - ERR INT TERM

printf '\nKlippertools Suite uninstalled successfully.\n'
printf 'Recovery files were retained at: %s\n' "$BACKUP_DIR"
printf '\nNext:\n'
printf '  1. In Mainsail, send RESTART in the console.\n'
printf '  2. Hard-refresh the browser (Ctrl+Shift+R).\n'
