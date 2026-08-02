#!/usr/bin/env bash
set -Eeuo pipefail

SUITE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
    printf 'lifecycle safety test failed: %s\n' "$*" >&2
    exit 1
}

make_fixture() {
    local root=$1
    mkdir -p \
        "$root/klipper/klippy/extras" \
        "$root/moonraker/moonraker/components" \
        "$root/printer_data/config" \
        "$root/mainsail"
    cp -a "$SUITE_ROOT" "$root/klippertools"
    printf 'v2.17.0\n' > "$root/mainsail/.version"
    printf 'original-ui\n' > "$root/mainsail/index.html"
    printf '{"theme":"original"}\n' > "$root/mainsail/config.json"
    printf 'previous-probe-backend\n' > "$root/klipper/klippy/extras/probe_progress.py"
    printf 'previous-suite-config\n' > "$root/printer_data/config/klippertools.cfg"
    printf '[server]\nhost: 0.0.0.0\n' > "$root/printer_data/config/moonraker.conf"
    cat > "$root/printer_data/config/printer.cfg" <<'CFG'
[include mainsail.cfg]


[gcode_macro PRINT_START]
gcode:
    M140 S60
    M104 S150
    M190 S60
    G28
    BED_MESH_CALIBRATE
    M109 S210
    G1 X10 Y10


[gcode_macro PRINT_END]
gcode:
    M104 S0
CFG
    cp -a "$root/printer_data/config/printer.cfg" "$root/printer.cfg.original"
}

run_env() {
    local root=$1
    shift
    env \
        HOME="$root" \
        _KLIPPERTOOLS_TEST_ALLOW_ROOT=1 \
        _KLIPPERTOOLS_TEST_PRINT_STATE=standby \
        KLIPPER_DIR="$root/klipper" \
        PRINTER_DATA_DIR="$root/printer_data" \
        CONFIG_DIR="$root/printer_data/config" \
        MAINSAIL_DIR="$root/mainsail" \
        MOONRAKER_DIR="$root/moonraker" \
        KLIPPERTOOLS_DIR="$root/klippertools" \
        "$@"
}

normal_root="$(mktemp -d /tmp/klippertools-safety-normal.XXXXXX)"
crash_install_root="$(mktemp -d /tmp/klippertools-safety-crash-install.XXXXXX)"
crash_update_root="$(mktemp -d /tmp/klippertools-safety-crash-update.XXXXXX)"
crash_uninstall_root="$(mktemp -d /tmp/klippertools-safety-crash-uninstall.XXXXXX)"
legacy_update_root="$(mktemp -d /tmp/klippertools-safety-legacy-update.XXXXXX)"
upgrade_021_root="$(mktemp -d /tmp/klippertools-safety-upgrade-021.XXXXXX)"
cleanup() {
    rm -rf -- "$normal_root" "$crash_install_root" "$crash_update_root" \
        "$crash_uninstall_root" "$legacy_update_root" "$upgrade_021_root"
}
trap cleanup EXIT

# Verification must detect content corruption, not merely the presence of a file.
make_fixture "$normal_root"
if env \
    HOME="$normal_root" \
    _KLIPPERTOOLS_TEST_ALLOW_ROOT=1 \
    _KLIPPERTOOLS_TEST_PRINT_STATE=printing \
    KLIPPER_DIR="$normal_root/klipper" \
    PRINTER_DATA_DIR="$normal_root/printer_data" \
    CONFIG_DIR="$normal_root/printer_data/config" \
    MAINSAIL_DIR="$normal_root/mainsail" \
    MOONRAKER_DIR="$normal_root/moonraker" \
    KLIPPERTOOLS_DIR="$normal_root/klippertools" \
    "$normal_root/klippertools/scripts/install.sh" >/dev/null 2>&1; then
    fail "installer accepted an active print"
fi
[[ ! -e "$normal_root/printer_data/klippertools-install-state" ]] ||
    fail "print interlock refusal created install state"
grep -q '^original-ui$' "$normal_root/mainsail/index.html" ||
    fail "print interlock refusal changed Mainsail"
run_env "$normal_root" "$normal_root/klippertools/scripts/install.sh" >/dev/null
printf 'this is invalid Python !\n' > "$normal_root/klipper/klippy/extras/nozzle_guard.py"
if run_env "$normal_root" "$normal_root/klippertools/scripts/check-install.sh" >/dev/null 2>&1; then
    fail "integrity check accepted a corrupted backend"
fi
cp -a "$normal_root/klippertools/klipper/nozzle_guard.py" \
    "$normal_root/klipper/klippy/extras/nozzle_guard.py"
run_env "$normal_root" "$normal_root/klippertools/scripts/check-install.sh" >/dev/null

# A deployed 0.2.0 key/value state is migrated without losing the true
# pre-suite files needed by a future 0.2.1 uninstall.
make_fixture "$legacy_update_root"
cp -a "$legacy_update_root/printer_data/config/moonraker.conf" \
    "$legacy_update_root/moonraker.conf.original"
rm -rf -- "$legacy_update_root/klippertools"
mkdir -p "$legacy_update_root/klippertools"
unzip -q "$SUITE_ROOT/dist/klippertools-suite-0.2.0.zip" \
    -d "$legacy_update_root/klippertools"
run_env "$legacy_update_root" \
    "$legacy_update_root/klippertools/scripts/install.sh" >/dev/null
grep -q '^PLUGIN_VERSION=0.2.0$' \
    "$legacy_update_root/printer_data/klippertools-install-state" ||
    fail "legacy fixture did not create 0.2.0 state"
mkdir -p "$legacy_update_root/update-stage"
cp -a "$SUITE_ROOT" "$legacy_update_root/update-stage/repository"
run_env "$legacy_update_root" \
    "$legacy_update_root/update-stage/repository/scripts/update.sh" \
    --source-target "$legacy_update_root/klippertools" >/dev/null
run_env "$legacy_update_root" \
    "$legacy_update_root/klippertools/scripts/check-install.sh" >/dev/null
run_env "$legacy_update_root" \
    "$legacy_update_root/klippertools/scripts/uninstall.sh" >/dev/null
cmp -s "$legacy_update_root/printer.cfg.original" \
    "$legacy_update_root/printer_data/config/printer.cfg" ||
    fail "legacy migration uninstall did not restore printer.cfg"
cmp -s "$legacy_update_root/moonraker.conf.original" \
    "$legacy_update_root/printer_data/config/moonraker.conf" ||
    fail "legacy migration uninstall did not restore moonraker.conf"
grep -q '^original-ui$' "$legacy_update_root/mainsail/index.html" ||
    fail "legacy migration uninstall did not restore Mainsail"

# The exact production path from 0.2.1 to 0.3.0 preserves user tuning and
# service data while adding the fifth Klipper collector section.
make_fixture "$upgrade_021_root"
rm -rf -- "$upgrade_021_root/klippertools"
mkdir -p "$upgrade_021_root/klippertools"
unzip -q "$SUITE_ROOT/dist/klippertools-suite-0.2.1.zip" \
    -d "$upgrade_021_root/klippertools"
run_env "$upgrade_021_root" \
    "$upgrade_021_root/klippertools/scripts/install.sh" >/dev/null
printf '\n# retained 0.2.1 user tuning\n' \
    >> "$upgrade_021_root/printer_data/config/klippertools.cfg"
printf '{"sentinel":"preserve-service-data"}\n' \
    > "$upgrade_021_root/printer_data/klippertools-service.json"
service_data_before="$(sha256sum "$upgrade_021_root/printer_data/klippertools-service.json" | cut -d' ' -f1)"
mkdir -p "$upgrade_021_root/update-stage"
cp -a "$SUITE_ROOT" "$upgrade_021_root/update-stage/repository"
run_env "$upgrade_021_root" \
    "$upgrade_021_root/update-stage/repository/scripts/update.sh" \
    --source-target "$upgrade_021_root/klippertools" >/dev/null
grep -q '^\[service_metrics\]$' \
    "$upgrade_021_root/printer_data/config/klippertools.cfg" ||
    fail "0.2.1 upgrade did not enable service_metrics"
grep -q 'retained 0.2.1 user tuning' \
    "$upgrade_021_root/printer_data/config/klippertools.cfg" ||
    fail "0.2.1 upgrade overwrote user tuning"
[[ -f "$upgrade_021_root/klipper/klippy/extras/service_metrics.py" ]] ||
    fail "0.2.1 upgrade did not install service_metrics.py"
service_data_after="$(sha256sum "$upgrade_021_root/printer_data/klippertools-service.json" | cut -d' ' -f1)"
[[ "$service_data_before" == "$service_data_after" ]] ||
    fail "0.2.1 upgrade changed persistent service data"
run_env "$upgrade_021_root" \
    "$upgrade_021_root/klippertools/scripts/check-install.sh" >/dev/null

# Update runs from a verified staging tree, preserves user configuration, and
# replaces the source checkout only after all deployed files are ready.
printf '\n# user tuning retained across update\n' \
    >> "$normal_root/printer_data/config/klippertools.cfg"
mkdir -p "$normal_root/update-stage"
cp -a "$normal_root/klippertools" "$normal_root/update-stage/repository"
run_env "$normal_root" \
    "$normal_root/update-stage/repository/scripts/update.sh" \
    --source-target "$normal_root/klippertools" >/dev/null
grep -q 'user tuning retained' "$normal_root/printer_data/config/klippertools.cfg" ||
    fail "update overwrote the user's suite configuration"
[[ ! -e "$normal_root/update-stage/repository" ]] ||
    fail "verified staging checkout was not moved into place"
run_env "$normal_root" "$normal_root/klippertools/scripts/check-install.sh" >/dev/null

# SIGKILL-style install interruption: journal remains, stable recovery helper
# restores every original byte, and recovery can be rerun outside the checkout.
make_fixture "$crash_install_root"
set +e
run_env "$crash_install_root" env _KLIPPERTOOLS_CRASH_AT=after_backends \
    "$crash_install_root/klippertools/scripts/install.sh" >/dev/null 2>&1
status=$?
set -e
[[ $status -eq 97 ]] || fail "install crash injection returned $status instead of 97"
[[ -f "$crash_install_root/printer_data/klippertools-transaction.json" ]] ||
    fail "install crash did not retain a journal"
run_env "$crash_install_root" \
    "$crash_install_root/printer_data/klippertools-recovery/recover.sh" >/dev/null
cmp -s "$crash_install_root/printer.cfg.original" \
    "$crash_install_root/printer_data/config/printer.cfg" ||
    fail "install recovery changed printer.cfg"
grep -q '^previous-probe-backend$' \
    "$crash_install_root/klipper/klippy/extras/probe_progress.py" ||
    fail "install recovery did not restore the prior backend"
grep -q '^original-ui$' "$crash_install_root/mainsail/index.html" ||
    fail "install recovery did not preserve Mainsail"
[[ ! -e "$crash_install_root/printer_data/klippertools-install-state" ]] ||
    fail "install recovery left an active state"

# Update interruption after the live UI rename must restore the installed
# suite, state, source checkout, and Mainsail as a coherent previous version.
make_fixture "$crash_update_root"
run_env "$crash_update_root" "$crash_update_root/klippertools/scripts/install.sh" >/dev/null
mkdir -p "$crash_update_root/update-stage"
cp -a "$crash_update_root/klippertools" "$crash_update_root/update-stage/repository"
set +e
run_env "$crash_update_root" env _KLIPPERTOOLS_CRASH_AT=after_ui_backup \
    "$crash_update_root/update-stage/repository/scripts/update.sh" \
    --source-target "$crash_update_root/klippertools" >/dev/null 2>&1
status=$?
set -e
[[ $status -eq 97 ]] || fail "update crash injection returned $status instead of 97"
run_env "$crash_update_root" \
    "$crash_update_root/printer_data/klippertools-recovery/recover.sh" >/dev/null
run_env "$crash_update_root" \
    "$crash_update_root/klippertools/scripts/check-install.sh" >/dev/null

# Uninstall interruption restores the complete installed suite and its state.
make_fixture "$crash_uninstall_root"
run_env "$crash_uninstall_root" "$crash_uninstall_root/klippertools/scripts/install.sh" >/dev/null
set +e
run_env "$crash_uninstall_root" env _KLIPPERTOOLS_CRASH_AT=after_backends \
    "$crash_uninstall_root/klippertools/scripts/uninstall.sh" >/dev/null 2>&1
status=$?
set -e
[[ $status -eq 97 ]] || fail "uninstall crash injection returned $status instead of 97"
run_env "$crash_uninstall_root" \
    "$crash_uninstall_root/printer_data/klippertools-recovery/recover.sh" >/dev/null
run_env "$crash_uninstall_root" \
    "$crash_uninstall_root/klippertools/scripts/check-install.sh" >/dev/null

printf 'lifecycle safety tests passed\n'
