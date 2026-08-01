#!/usr/bin/env bash
set -Eeuo pipefail

SUITE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
    printf 'transaction test failed: %s\n' "$*" >&2
    exit 1
}

run_for_version() {
    local version=$1
    local test_root
    test_root="$(mktemp -d "/tmp/klippertools-${version#v}.XXXXXX")"
    case "$test_root" in
        /tmp/klippertools-*) ;;
        *) fail "unexpected temporary path: $test_root" ;;
    esac

    cleanup_case() {
        rm -rf -- "$test_root"
    }
    trap cleanup_case RETURN

    mkdir -p \
        "$test_root/klipper/klippy/extras" \
        "$test_root/printer_data/config" \
        "$test_root/mainsail"
    printf '%s\n' "$version" > "$test_root/mainsail/.version"
    printf 'original-ui\n' > "$test_root/mainsail/index.html"
    printf '{"theme":"original"}\n' > "$test_root/mainsail/config.json"
    printf 'previous-probe-backend\n' \
        > "$test_root/klipper/klippy/extras/probe_progress.py"
    printf 'previous-suite-config\n' \
        > "$test_root/printer_data/config/klippertools.cfg"

    cat > "$test_root/printer_data/config/printer.cfg" <<'CFG'
[include mainsail.cfg]

[gcode_macro PRINT_START]
gcode:
    {% set BED = params.BED|default(60)|float %}
    M140 S{BED}
    M104 S150
    M190 S{BED}
    G28
    BED_MESH_CLEAR
    BED_MESH_CALIBRATE PROFILE=print
    M109 S210
    G92 E0
    G1 X10 Y10
    RESPOND MSG="Print start complete"

[gcode_macro PRINT_END]
gcode:
    M104 S0
CFG
    if [[ "$version" == v2.18.2 ]]; then
        python3 "$SUITE_ROOT/scripts/configure.py" add \
            "$test_root/printer_data/config/printer.cfg" >/dev/null
    fi
    cp -a "$test_root/printer_data/config/printer.cfg" \
        "$test_root/printer.cfg.original"

    local -a runner
    if [[ $EUID -eq 0 ]]; then
        runner=(env "HOME=$test_root" _KLIPPERTOOLS_TEST_ALLOW_ROOT=1)
    else
        runner=(env "HOME=$test_root")
    fi

    "${runner[@]}" \
        KLIPPER_DIR="$test_root/klipper" \
        PRINTER_DATA_DIR="$test_root/printer_data" \
        CONFIG_DIR="$test_root/printer_data/config" \
        MAINSAIL_DIR="$test_root/mainsail" \
        "$SUITE_ROOT/scripts/install.sh" >/dev/null

    for backend in probe_progress nozzle_guard start_flow motion_wizard; do
        [[ -f "$test_root/klipper/klippy/extras/$backend.py" ]] ||
            fail "$version did not install $backend.py"
    done
    grep -q '^\[include klippertools.cfg\]$' \
        "$test_root/printer_data/config/printer.cfg" ||
        fail "$version did not add the suite include"
    grep -q 'START_FLOW_STAGE NAME=mesh' \
        "$test_root/printer_data/config/printer.cfg" ||
        fail "$version did not instrument PRINT_START"
    [[ -f "$test_root/mainsail/klippertools-build.txt" ]] ||
        fail "$version did not install the UI marker"

    "${runner[@]}" \
        KLIPPER_DIR="$test_root/klipper" \
        PRINTER_DATA_DIR="$test_root/printer_data" \
        CONFIG_DIR="$test_root/printer_data/config" \
        MAINSAIL_DIR="$test_root/mainsail" \
        "$SUITE_ROOT/scripts/check-install.sh" >/dev/null

    printf '{"theme":"changed-after-install"}\n' \
        > "$test_root/mainsail/config.json"
    "${runner[@]}" \
        PRINTER_DATA_DIR="$test_root/printer_data" \
        "$SUITE_ROOT/scripts/uninstall.sh" >/dev/null

    cmp -s "$test_root/printer.cfg.original" \
        "$test_root/printer_data/config/printer.cfg" ||
        fail "$version did not restore printer.cfg exactly"
    grep -q '^previous-probe-backend$' \
        "$test_root/klipper/klippy/extras/probe_progress.py" ||
        fail "$version did not restore the previous backend"
    [[ ! -e "$test_root/klipper/klippy/extras/nozzle_guard.py" ]] ||
        fail "$version left a new backend behind"
    grep -q '^previous-suite-config$' \
        "$test_root/printer_data/config/klippertools.cfg" ||
        fail "$version did not restore the previous suite config"
    grep -q '^original-ui$' "$test_root/mainsail/index.html" ||
        fail "$version did not restore the original UI"
    grep -q 'changed-after-install' "$test_root/mainsail/config.json" ||
        fail "$version did not preserve the latest Mainsail settings"
    [[ ! -e "$test_root/printer_data/klippertools-install-state" ]] ||
        fail "$version left an active install state behind"

    trap - RETURN
    cleanup_case
}

run_for_version v2.17.0
run_for_version v2.18.2
printf 'transactional install tests passed\n'
