#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

path_exists() {
    [[ -e "$1" || -L "$1" ]]
}

if [[ $EUID -eq 0 ]]; then
    fail "run this as the normal Klipper user, not root"
fi

PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KLIPPER_DIR="${KLIPPER_DIR:-$HOME/klipper}"
PRINTER_DATA_DIR="${PRINTER_DATA_DIR:-$HOME/printer_data}"
CONFIG_DIR="${CONFIG_DIR:-$PRINTER_DATA_DIR/config}"
MAINSAIL_DIR="${MAINSAIL_DIR:-$HOME/mainsail}"
PRINTER_CFG="$CONFIG_DIR/printer.cfg"
EXTRA_PATH="$KLIPPER_DIR/klippy/extras/probe_progress.py"
PLUGIN_CFG="$CONFIG_DIR/probe_progress.cfg"
STATE_FILE="$PRINTER_DATA_DIR/probe-progress-install-state"
BACKUP_ROOT="$HOME/probe-progress-backups"

for managed_path in "$KLIPPER_DIR" "$PRINTER_DATA_DIR" \
        "$CONFIG_DIR" "$MAINSAIL_DIR"; do
    case "$managed_path" in
        "$HOME"/*) ;;
        *) fail "managed paths must be inside $HOME: $managed_path" ;;
    esac
done

for required_command in python3 unzip cp mv mkdir date; do
    command -v "$required_command" >/dev/null 2>&1 ||
        fail "missing required command: $required_command"
done

[[ -f "$PLUGIN_ROOT/klipper/probe_progress.py" ]] ||
    fail "plugin backend is missing"
[[ -f "$PLUGIN_ROOT/config/probe_progress.cfg" ]] ||
    fail "plugin configuration is missing"
[[ -f "$PLUGIN_ROOT/scripts/configure.py" ]] ||
    fail "configuration helper is missing"
[[ -d "$KLIPPER_DIR/klippy/extras" ]] ||
    fail "Klipper was not found at $KLIPPER_DIR"
[[ -f "$PRINTER_CFG" ]] ||
    fail "printer.cfg was not found at $PRINTER_CFG"
[[ -d "$MAINSAIL_DIR" && -f "$MAINSAIL_DIR/.version" ]] ||
    fail "Mainsail was not found at $MAINSAIL_DIR"
[[ ! -e "$STATE_FILE" ]] ||
    fail "Probe Progress is already installed; uninstall it before reinstalling"

MAINSAIL_VERSION="$(tr -d '\r\n' < "$MAINSAIL_DIR/.version")"
case "$MAINSAIL_VERSION" in
    v2.17.0)
        DIST_ZIP="$PLUGIN_ROOT/dist/mainsail-v2.17.0-probe-progress.zip"
        ;;
    v2.18.2)
        DIST_ZIP="$PLUGIN_ROOT/dist/mainsail-v2.18.2-probe-progress.zip"
        ;;
    *)
        fail "Mainsail $MAINSAIL_VERSION is unsupported; expected v2.17.0 or v2.18.2"
        ;;
esac
[[ -f "$DIST_ZIP" ]] || fail "UI build is missing: $DIST_ZIP"

BACKUP_DIR="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)-$$"
[[ ! -e "$BACKUP_DIR" ]] || fail "backup path already exists: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR/mainsail-new"
unzip -q "$DIST_ZIP" -d "$BACKUP_DIR/mainsail-new"
[[ -f "$BACKUP_DIR/mainsail-new/probe-progress-build.txt" ]] ||
    fail "the UI archive did not contain its Probe Progress marker"

if [[ -f "$MAINSAIL_DIR/config.json" ]]; then
    cp -a "$MAINSAIL_DIR/config.json" \
        "$BACKUP_DIR/mainsail-new/config.json"
fi
cp -a "$PRINTER_CFG" "$BACKUP_DIR/printer.cfg"

EXTRA_EXISTED=0
CONFIG_EXISTED=0
MUTATED=0
UI_ORIGINAL_MOVED=0

rollback() {
    local exit_code=$?
    trap - ERR INT TERM
    set +e
    if [[ $UI_ORIGINAL_MOVED -eq 1 &&
          -d "$BACKUP_DIR/mainsail" ]]; then
        if [[ -e "$MAINSAIL_DIR" ]]; then
            mv "$MAINSAIL_DIR" "$BACKUP_DIR/mainsail-failed-install"
        fi
        mv "$BACKUP_DIR/mainsail" "$MAINSAIL_DIR"
    fi
    if [[ $MUTATED -eq 1 ]]; then
        cp -a "$BACKUP_DIR/printer.cfg" "$PRINTER_CFG"
        if path_exists "$EXTRA_PATH"; then
            mv "$EXTRA_PATH" "$BACKUP_DIR/probe_progress.py-failed-install"
        fi
        if path_exists "$BACKUP_DIR/probe_progress.py.previous"; then
            mv "$BACKUP_DIR/probe_progress.py.previous" "$EXTRA_PATH"
        fi
        if path_exists "$PLUGIN_CFG"; then
            mv "$PLUGIN_CFG" "$BACKUP_DIR/probe_progress.cfg-failed-install"
        fi
        if path_exists "$BACKUP_DIR/probe_progress.cfg.previous"; then
            mv "$BACKUP_DIR/probe_progress.cfg.previous" "$PLUGIN_CFG"
        fi
    fi
    printf 'Install failed; original files were restored.\n' >&2
    printf 'Recovery files: %s\n' "$BACKUP_DIR" >&2
    exit "$exit_code"
}
trap rollback ERR INT TERM

MUTATED=1
if path_exists "$EXTRA_PATH"; then
    mv "$EXTRA_PATH" "$BACKUP_DIR/probe_progress.py.previous"
    EXTRA_EXISTED=1
fi
cp -a "$PLUGIN_ROOT/klipper/probe_progress.py" "$EXTRA_PATH"

if path_exists "$PLUGIN_CFG"; then
    mv "$PLUGIN_CFG" "$BACKUP_DIR/probe_progress.cfg.previous"
    CONFIG_EXISTED=1
fi
cp -a "$PLUGIN_ROOT/config/probe_progress.cfg" "$PLUGIN_CFG"
python3 "$PLUGIN_ROOT/scripts/configure.py" add "$PRINTER_CFG" >/dev/null

mv "$MAINSAIL_DIR" "$BACKUP_DIR/mainsail"
UI_ORIGINAL_MOVED=1
mv "$BACKUP_DIR/mainsail-new" "$MAINSAIL_DIR"

STATE_TMP="$BACKUP_DIR/install-state.tmp"
printf '%s\n' \
    "PLUGIN_VERSION=0.1.0" \
    "MAINSAIL_VERSION=$MAINSAIL_VERSION" \
    "BACKUP_DIR=$BACKUP_DIR" \
    "KLIPPER_DIR=$KLIPPER_DIR" \
    "PRINTER_DATA_DIR=$PRINTER_DATA_DIR" \
    "CONFIG_DIR=$CONFIG_DIR" \
    "MAINSAIL_DIR=$MAINSAIL_DIR" \
    "EXTRA_EXISTED=$EXTRA_EXISTED" \
    "CONFIG_EXISTED=$CONFIG_EXISTED" \
    > "$STATE_TMP"
mv "$STATE_TMP" "$STATE_FILE"

trap - ERR INT TERM
printf '\nKlipper Probe Progress 0.1.0 installed successfully.\n'
printf 'Backup retained at: %s\n' "$BACKUP_DIR"
printf '\nNext:\n'
printf '  1. In Mainsail, send RESTART in the console.\n'
printf '  2. Hard-refresh the browser (Ctrl+Shift+R).\n'
printf '  3. Run the safe 3x3 test command from README.md while idle.\n'
