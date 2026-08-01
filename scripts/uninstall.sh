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

if [[ $EUID -eq 0 ]]; then
    fail "run this as the normal Klipper user, not root"
fi

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INITIAL_PRINTER_DATA_DIR="${PRINTER_DATA_DIR:-$HOME/printer_data}"
STATE_FILE="$INITIAL_PRINTER_DATA_DIR/probe-progress-install-state"
[[ -f "$STATE_FILE" ]] ||
    fail "install state was not found at $STATE_FILE"
[[ -f "$PLUGIN_ROOT/scripts/configure.py" ]] ||
    fail "configuration helper is missing"

BACKUP_DIR="$(read_state BACKUP_DIR)"
KLIPPER_DIR="$(read_state KLIPPER_DIR)"
PRINTER_DATA_DIR="$(read_state PRINTER_DATA_DIR)"
CONFIG_DIR="$(read_state CONFIG_DIR)"
MAINSAIL_DIR="$(read_state MAINSAIL_DIR)"
EXTRA_EXISTED="$(read_state EXTRA_EXISTED)"
CONFIG_EXISTED="$(read_state CONFIG_EXISTED)"

case "$BACKUP_DIR" in
    "$HOME/probe-progress-backups/"*) ;;
    *) fail "refusing unexpected backup path: $BACKUP_DIR" ;;
esac
for managed_path in "$KLIPPER_DIR" "$PRINTER_DATA_DIR" \
        "$CONFIG_DIR" "$MAINSAIL_DIR"; do
    case "$managed_path" in
        "$HOME"/*) ;;
        *) fail "refusing unexpected managed path: $managed_path" ;;
    esac
done
[[ "$EXTRA_EXISTED" == 0 || "$EXTRA_EXISTED" == 1 ]] ||
    fail "invalid backend state"
[[ "$CONFIG_EXISTED" == 0 || "$CONFIG_EXISTED" == 1 ]] ||
    fail "invalid configuration state"

PRINTER_CFG="$CONFIG_DIR/printer.cfg"
EXTRA_PATH="$KLIPPER_DIR/klippy/extras/probe_progress.py"
PLUGIN_CFG="$CONFIG_DIR/probe_progress.cfg"
[[ -d "$BACKUP_DIR/mainsail" ]] ||
    fail "original Mainsail backup is missing"
[[ -f "$BACKUP_DIR/printer.cfg" ]] ||
    fail "original printer.cfg backup is missing"
[[ -f "$PRINTER_CFG" ]] ||
    fail "current printer.cfg is missing"
[[ -d "$MAINSAIL_DIR" ]] ||
    fail "current Mainsail directory is missing"
[[ ! -e "$BACKUP_DIR/mainsail-with-probe-progress" ]] ||
    fail "uninstall recovery directory already exists"
if [[ "$EXTRA_EXISTED" == 1 ]]; then
    path_exists "$BACKUP_DIR/probe_progress.py.previous" ||
        fail "previous Klipper extra is missing"
fi
if [[ "$CONFIG_EXISTED" == 1 ]]; then
    path_exists "$BACKUP_DIR/probe_progress.cfg.previous" ||
        fail "previous plugin configuration is missing"
fi

cp -a "$PRINTER_CFG" "$BACKUP_DIR/printer.cfg.before-uninstall"
if [[ -f "$MAINSAIL_DIR/config.json" ]]; then
    cp -a "$MAINSAIL_DIR/config.json" "$BACKUP_DIR/config.json.latest"
fi

BACKEND_MUTATED=0
CONFIG_MUTATED=0
UI_CUSTOM_MOVED=0
UI_ORIGINAL_RESTORED=0

rollback() {
    local exit_code=$?
    trap - ERR INT TERM
    set +e
    if [[ $UI_ORIGINAL_RESTORED -eq 1 &&
          -d "$MAINSAIL_DIR" ]]; then
        mv "$MAINSAIL_DIR" "$BACKUP_DIR/mainsail"
    fi
    if [[ $UI_CUSTOM_MOVED -eq 1 &&
          -d "$BACKUP_DIR/mainsail-with-probe-progress" ]]; then
        mv "$BACKUP_DIR/mainsail-with-probe-progress" "$MAINSAIL_DIR"
    fi
    if [[ $CONFIG_MUTATED -eq 1 ]]; then
        if path_exists "$PLUGIN_CFG"; then
            mv "$PLUGIN_CFG" \
                "$BACKUP_DIR/probe_progress.cfg.previous"
        fi
        if path_exists "$BACKUP_DIR/probe_progress.cfg.installed"; then
            mv "$BACKUP_DIR/probe_progress.cfg.installed" "$PLUGIN_CFG"
        fi
    fi
    if [[ $BACKEND_MUTATED -eq 1 ]]; then
        if path_exists "$EXTRA_PATH"; then
            mv "$EXTRA_PATH" \
                "$BACKUP_DIR/probe_progress.py.previous"
        fi
        if path_exists "$BACKUP_DIR/probe_progress.py.installed"; then
            mv "$BACKUP_DIR/probe_progress.py.installed" "$EXTRA_PATH"
        fi
    fi
    cp -a "$BACKUP_DIR/printer.cfg.before-uninstall" "$PRINTER_CFG"
    printf 'Uninstall failed; installed files were restored.\n' >&2
    printf 'Recovery files: %s\n' "$BACKUP_DIR" >&2
    exit "$exit_code"
}
trap rollback ERR INT TERM

python3 "$PLUGIN_ROOT/scripts/configure.py" remove "$PRINTER_CFG" >/dev/null

BACKEND_MUTATED=1
if path_exists "$EXTRA_PATH"; then
    mv "$EXTRA_PATH" "$BACKUP_DIR/probe_progress.py.installed"
fi
if [[ "$EXTRA_EXISTED" == 1 ]]; then
    mv "$BACKUP_DIR/probe_progress.py.previous" "$EXTRA_PATH"
fi

CONFIG_MUTATED=1
if path_exists "$PLUGIN_CFG"; then
    mv "$PLUGIN_CFG" "$BACKUP_DIR/probe_progress.cfg.installed"
fi
if [[ "$CONFIG_EXISTED" == 1 ]]; then
    mv "$BACKUP_DIR/probe_progress.cfg.previous" "$PLUGIN_CFG"
fi

mv "$MAINSAIL_DIR" "$BACKUP_DIR/mainsail-with-probe-progress"
UI_CUSTOM_MOVED=1
mv "$BACKUP_DIR/mainsail" "$MAINSAIL_DIR"
UI_ORIGINAL_RESTORED=1
if [[ -f "$BACKUP_DIR/config.json.latest" ]]; then
    cp -a "$BACKUP_DIR/config.json.latest" "$MAINSAIL_DIR/config.json"
fi

mv "$STATE_FILE" "$BACKUP_DIR/install-state.uninstalled"
trap - ERR INT TERM

printf '\nKlipper Probe Progress uninstalled successfully.\n'
printf 'Recovery files were retained at: %s\n' "$BACKUP_DIR"
printf '\nNext:\n'
printf '  1. In Mainsail, send RESTART in the console.\n'
printf '  2. Hard-refresh the browser (Ctrl+Shift+R).\n'
