#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

if [[ $EUID -eq 0 ]]; then
    fail "run this as the normal Klipper user, not root"
fi

REPOSITORY_URL="${PROBE_PROGRESS_REPOSITORY_URL:-https://github.com/Nickfc/Klippertools-progress.git}"
REPOSITORY_REF="${PROBE_PROGRESS_REF:-main}"
TARGET_DIR="${PROBE_PROGRESS_DIR:-$HOME/klipper-probe-progress}"
STATE_FILE="${PRINTER_DATA_DIR:-$HOME/printer_data}/probe-progress-install-state"

case "$TARGET_DIR" in
    "$HOME"/*) ;;
    *) fail "the install directory must be inside $HOME" ;;
esac

for required_command in git sha256sum python3 unzip mktemp mv rm; do
    command -v "$required_command" >/dev/null 2>&1 ||
        fail "missing required command: $required_command"
done

[[ ! -e "$STATE_FILE" ]] ||
    fail "Probe Progress is already installed; uninstall it before reinstalling"
[[ ! -e "$TARGET_DIR" ]] ||
    fail "$TARGET_DIR already exists; move it aside or use the local installer"

DOWNLOAD_DIR="$(mktemp -d "$HOME/.probe-progress-download.XXXXXX")"
cleanup() {
    case "$DOWNLOAD_DIR" in
        "$HOME/.probe-progress-download."*)
            rm -rf -- "$DOWNLOAD_DIR"
            ;;
    esac
}
trap cleanup EXIT

printf 'Downloading Klipper Probe Progress from GitHub...\n'
git clone --quiet --depth 1 --branch "$REPOSITORY_REF" \
    "$REPOSITORY_URL" "$DOWNLOAD_DIR/repository"

(
    cd "$DOWNLOAD_DIR/repository"
    sha256sum -c SHA256SUMS >/dev/null
)

mv "$DOWNLOAD_DIR/repository" "$TARGET_DIR"
trap - EXIT
cleanup

printf 'Download verified. Starting the transactional installer...\n'
"$TARGET_DIR/scripts/install.sh"
