#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

path_exists() {
    [[ -e "$1" || -L "$1" ]]
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
KLIPPER_DIR="${KLIPPER_DIR:-$HOME/klipper}"
PRINTER_DATA_DIR="${PRINTER_DATA_DIR:-$HOME/printer_data}"
CONFIG_DIR="${CONFIG_DIR:-$PRINTER_DATA_DIR/config}"
MAINSAIL_DIR="${MAINSAIL_DIR:-$HOME/mainsail}"
PRINTER_CFG="$CONFIG_DIR/printer.cfg"
SUITE_CFG="$CONFIG_DIR/klippertools.cfg"
STATE_FILE="$PRINTER_DATA_DIR/klippertools-install-state"
LEGACY_STATE_FILE="$PRINTER_DATA_DIR/probe-progress-install-state"
BACKUP_ROOT="$HOME/klippertools-backups"
EXTRA_NAMES=(probe_progress nozzle_guard start_flow motion_wizard)

for managed_path in "$KLIPPER_DIR" "$PRINTER_DATA_DIR" \
        "$CONFIG_DIR" "$MAINSAIL_DIR"; do
    case "$managed_path" in
        "$HOME"/*) ;;
        *) fail "managed paths must be inside $HOME: $managed_path" ;;
    esac
done

for required_command in python3 unzip cp mv mkdir date grep tr; do
    command -v "$required_command" >/dev/null 2>&1 ||
        fail "missing required command: $required_command"
done

for name in "${EXTRA_NAMES[@]}"; do
    [[ -f "$SUITE_ROOT/klipper/$name.py" ]] ||
        fail "Klipper backend is missing: $name.py"
done
[[ -f "$SUITE_ROOT/config/klippertools.cfg" ]] ||
    fail "suite configuration is missing"
[[ -f "$SUITE_ROOT/scripts/configure.py" ]] ||
    fail "configuration helper is missing"
[[ -f "$SUITE_ROOT/scripts/instrument_print_start.py" ]] ||
    fail "StartFlow instrumentation helper is missing"
[[ -d "$KLIPPER_DIR/klippy/extras" ]] ||
    fail "Klipper was not found at $KLIPPER_DIR"
[[ -f "$PRINTER_CFG" ]] ||
    fail "printer.cfg was not found at $PRINTER_CFG"
[[ -d "$MAINSAIL_DIR" && -f "$MAINSAIL_DIR/.version" ]] ||
    fail "Mainsail was not found at $MAINSAIL_DIR"
[[ ! -e "$STATE_FILE" ]] ||
    fail "Klippertools is already installed; uninstall it before reinstalling"
[[ ! -e "$LEGACY_STATE_FILE" ]] ||
    fail "Probe Progress 0.1 is installed; uninstall it before installing Klippertools 0.2"
if grep -Eq '^[[:space:]]*\[include probe_progress\.cfg\]' \
        "$PRINTER_CFG"; then
    fail "printer.cfg still includes probe_progress.cfg; remove the legacy install first"
fi

MAINSAIL_VERSION="$(tr -d '\r\n' < "$MAINSAIL_DIR/.version")"
case "$MAINSAIL_VERSION" in
    v2.17.0)
        DIST_ZIP="$SUITE_ROOT/dist/mainsail-v2.17.0-klippertools.zip"
        ;;
    v2.18.2)
        DIST_ZIP="$SUITE_ROOT/dist/mainsail-v2.18.2-klippertools.zip"
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
[[ -f "$BACKUP_DIR/mainsail-new/klippertools-build.txt" ]] ||
    fail "the UI archive did not contain its Klippertools marker"

if [[ -f "$MAINSAIL_DIR/config.json" ]]; then
    cp -a "$MAINSAIL_DIR/config.json" \
        "$BACKUP_DIR/mainsail-new/config.json"
fi
cp -a "$PRINTER_CFG" "$BACKUP_DIR/printer.cfg"

declare -A EXTRA_EXISTED=()
declare -A EXTRA_MUTATED=()
for name in "${EXTRA_NAMES[@]}"; do
    EXTRA_EXISTED[$name]=0
    EXTRA_MUTATED[$name]=0
done
CONFIG_EXISTED=0
CONFIG_MUTATED=0
PRINTER_MUTATED=0
UI_ORIGINAL_MOVED=0
PRINT_START_INSTRUMENTED=0
CONFIG_INCLUDE_ADDED=0

rollback() {
    local exit_code=$?
    trap - ERR INT TERM
    set +e
    if [[ $UI_ORIGINAL_MOVED -eq 1 && -d "$BACKUP_DIR/mainsail" ]]; then
        if [[ -e "$MAINSAIL_DIR" ]]; then
            mv "$MAINSAIL_DIR" "$BACKUP_DIR/mainsail-failed-install"
        fi
        mv "$BACKUP_DIR/mainsail" "$MAINSAIL_DIR"
    fi
    if [[ $PRINTER_MUTATED -eq 1 ]]; then
        cp -a "$BACKUP_DIR/printer.cfg" "$PRINTER_CFG"
    fi
    if [[ $CONFIG_MUTATED -eq 1 ]]; then
        if path_exists "$SUITE_CFG"; then
            mv "$SUITE_CFG" "$BACKUP_DIR/klippertools.cfg-failed-install"
        fi
        if path_exists "$BACKUP_DIR/klippertools.cfg.previous"; then
            mv "$BACKUP_DIR/klippertools.cfg.previous" "$SUITE_CFG"
        fi
    fi
    for name in "${EXTRA_NAMES[@]}"; do
        if [[ ${EXTRA_MUTATED[$name]} -ne 1 ]]; then
            continue
        fi
        local target="$KLIPPER_DIR/klippy/extras/$name.py"
        if path_exists "$target"; then
            mv "$target" "$BACKUP_DIR/$name.py-failed-install"
        fi
        if path_exists "$BACKUP_DIR/$name.py.previous"; then
            mv "$BACKUP_DIR/$name.py.previous" "$target"
        fi
    done
    printf 'Install failed; original files were restored.\n' >&2
    printf 'Recovery files: %s\n' "$BACKUP_DIR" >&2
    exit "$exit_code"
}
trap rollback ERR INT TERM

for name in "${EXTRA_NAMES[@]}"; do
    target="$KLIPPER_DIR/klippy/extras/$name.py"
    if path_exists "$target"; then
        mv "$target" "$BACKUP_DIR/$name.py.previous"
        EXTRA_EXISTED[$name]=1
    fi
    EXTRA_MUTATED[$name]=1
    cp -a "$SUITE_ROOT/klipper/$name.py" "$target"
done

if path_exists "$SUITE_CFG"; then
    mv "$SUITE_CFG" "$BACKUP_DIR/klippertools.cfg.previous"
    CONFIG_EXISTED=1
fi
CONFIG_MUTATED=1
cp -a "$SUITE_ROOT/config/klippertools.cfg" "$SUITE_CFG"

PRINTER_MUTATED=1
INCLUDE_RESULT="$(
    python3 "$SUITE_ROOT/scripts/configure.py" add "$PRINTER_CFG"
)"
if [[ "$INCLUDE_RESULT" == "updated" ]]; then
    CONFIG_INCLUDE_ADDED=1
fi
INSTRUMENT_RESULT="$(
    python3 "$SUITE_ROOT/scripts/instrument_print_start.py" \
        add "$PRINTER_CFG" --optional
)"
if [[ "$INSTRUMENT_RESULT" == "updated" ]]; then
    PRINT_START_INSTRUMENTED=1
fi

mv "$MAINSAIL_DIR" "$BACKUP_DIR/mainsail"
UI_ORIGINAL_MOVED=1
mv "$BACKUP_DIR/mainsail-new" "$MAINSAIL_DIR"

STATE_TMP="$BACKUP_DIR/install-state.tmp"
{
    printf '%s\n' \
        "PLUGIN_VERSION=0.2.0" \
        "MAINSAIL_VERSION=$MAINSAIL_VERSION" \
        "BACKUP_DIR=$BACKUP_DIR" \
        "KLIPPER_DIR=$KLIPPER_DIR" \
        "PRINTER_DATA_DIR=$PRINTER_DATA_DIR" \
        "CONFIG_DIR=$CONFIG_DIR" \
        "MAINSAIL_DIR=$MAINSAIL_DIR" \
        "CONFIG_EXISTED=$CONFIG_EXISTED" \
        "CONFIG_INCLUDE_ADDED=$CONFIG_INCLUDE_ADDED" \
        "PRINT_START_INSTRUMENTED=$PRINT_START_INSTRUMENTED"
    for name in "${EXTRA_NAMES[@]}"; do
        key="$(state_key "$name")"
        printf 'EXTRA_EXISTED_%s=%s\n' "$key" "${EXTRA_EXISTED[$name]}"
    done
} > "$STATE_TMP"
mv "$STATE_TMP" "$STATE_FILE"

trap - ERR INT TERM
printf '\nKlippertools Suite 0.2.0 installed successfully.\n'
printf 'Backup retained at: %s\n' "$BACKUP_DIR"
if [[ $PRINT_START_INSTRUMENTED -eq 1 ]]; then
    printf 'StartFlow markers were added safely to PRINT_START.\n'
else
    printf 'StartFlow was not auto-instrumented: %s\n' "$INSTRUMENT_RESULT"
    printf 'See docs/STARTFLOW.md for manual stage markers.\n'
fi
printf '\nNext:\n'
printf '  1. In Mainsail, send RESTART in the console.\n'
printf '  2. Hard-refresh the browser (Ctrl+Shift+R).\n'
printf '  3. Run the safe checks in README.md while the printer is idle.\n'
