#!/usr/bin/env bash
set -Eeuo pipefail

SUITE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d /tmp/klippertools-online-lifecycle.XXXXXX)"
REPOSITORY_ROOT="$(mktemp -d /tmp/klippertools-online-repository.XXXXXX)"

cleanup() {
    rm -rf -- "$TEST_ROOT" "$REPOSITORY_ROOT"
}
trap cleanup EXIT

fail() {
    printf 'online lifecycle test failed: %s\n' "$*" >&2
    exit 1
}

mkdir -p \
    "$TEST_ROOT/klipper/klippy/extras" \
    "$TEST_ROOT/moonraker/moonraker/components" \
    "$TEST_ROOT/printer_data/config" \
    "$TEST_ROOT/mainsail"
printf 'v2.17.0\n' > "$TEST_ROOT/mainsail/.version"
printf 'original-ui\n' > "$TEST_ROOT/mainsail/index.html"
printf '{"theme":"original"}\n' > "$TEST_ROOT/mainsail/config.json"
printf '[server]\nhost: 0.0.0.0\n' > "$TEST_ROOT/printer_data/config/moonraker.conf"
cat > "$TEST_ROOT/printer_data/config/printer.cfg" <<'CFG'
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
CFG

unzip -q "$SUITE_ROOT/dist/klippertools-suite-0.2.1.zip" \
    -d "$REPOSITORY_ROOT"
git -C "$REPOSITORY_ROOT" init -q -b main
git -C "$REPOSITORY_ROOT" config user.name "Klippertools Test"
git -C "$REPOSITORY_ROOT" config user.email "test@example.invalid"
git -C "$REPOSITORY_ROOT" add .
git -C "$REPOSITORY_ROOT" commit -qm "test release"

run_env() {
    env \
        HOME="$TEST_ROOT" \
        _KLIPPERTOOLS_TEST_ALLOW_ROOT=1 \
        _KLIPPERTOOLS_TEST_PRINT_STATE=standby \
        KLIPPER_DIR="$TEST_ROOT/klipper" \
        PRINTER_DATA_DIR="$TEST_ROOT/printer_data" \
        CONFIG_DIR="$TEST_ROOT/printer_data/config" \
        MAINSAIL_DIR="$TEST_ROOT/mainsail" \
        MOONRAKER_DIR="$TEST_ROOT/moonraker" \
        KLIPPERTOOLS_DIR="$TEST_ROOT/klippertools" \
        KLIPPERTOOLS_REPOSITORY_URL="file://$REPOSITORY_ROOT" \
        KLIPPERTOOLS_SOURCE_URL="file://$REPOSITORY_ROOT" \
        KLIPPERTOOLS_REF=main \
        KLIPPERTOOLS_SOURCE_REF=main \
        "$@"
}

run_env "$SUITE_ROOT/install-online.sh" >/dev/null
run_env "$TEST_ROOT/klippertools/scripts/check-install.sh" >/dev/null
printf '\n# online update preservation test\n' \
    >> "$TEST_ROOT/printer_data/config/klippertools.cfg"
run_env "$TEST_ROOT/klippertools/scripts/update-online.sh" >/dev/null
grep -q 'online update preservation test' \
    "$TEST_ROOT/printer_data/config/klippertools.cfg" ||
    fail "online update overwrote user configuration"
run_env "$TEST_ROOT/klippertools/scripts/check-install.sh" >/dev/null
run_env "$TEST_ROOT/klippertools/scripts/uninstall.sh" >/dev/null
[[ ! -e "$TEST_ROOT/klippertools" ]] || fail "uninstall left the checkout active"

# A clean bootstrap must be possible immediately after uninstall.
run_env "$SUITE_ROOT/install-online.sh" >/dev/null
run_env "$TEST_ROOT/klippertools/scripts/check-install.sh" >/dev/null

printf 'online install, update, uninstall, and reinstall tests passed\n'
