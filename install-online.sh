#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

if [[ $EUID -eq 0 ]]; then
    if [[ ${_KLIPPERTOOLS_TEST_ALLOW_ROOT:-0} != 1 || \
          $HOME != /tmp/klippertools-* ]]; then
        fail "run this as the normal Klipper user, not root"
    fi
fi

REPOSITORY_URL="${KLIPPERTOOLS_REPOSITORY_URL:-${PROBE_PROGRESS_REPOSITORY_URL:-https://github.com/Nickfc/Klippertools-progress.git}}"
REPOSITORY_REF="${KLIPPERTOOLS_REF:-${PROBE_PROGRESS_REF:-main}}"
TARGET_DIR="${KLIPPERTOOLS_DIR:-$HOME/klippertools}"
STATE_FILE="${PRINTER_DATA_DIR:-$HOME/printer_data}/klippertools-install-state"

case "$TARGET_DIR" in
    "$HOME"/*) ;;
    *) fail "the install directory must be inside $HOME" ;;
esac
case "$REPOSITORY_URL" in
    https://*|ssh://*|git@*|file://*) ;;
    *) fail "unsupported or unsafe repository URL" ;;
esac
[[ "$REPOSITORY_URL" != -* ]] || fail "unsafe repository URL"
git check-ref-format --branch "$REPOSITORY_REF" >/dev/null 2>&1 ||
    fail "invalid repository ref: $REPOSITORY_REF"

for required_command in git sha256sum python3 unzip mktemp mv rm; do
    command -v "$required_command" >/dev/null 2>&1 ||
        fail "missing required command: $required_command"
done

[[ ! -e "$STATE_FILE" ]] ||
    fail "Klippertools is already installed; uninstall it before reinstalling"
[[ ! -e "$TARGET_DIR" ]] ||
    fail "$TARGET_DIR already exists; move it aside or use the local installer"

DOWNLOAD_DIR="$(mktemp -d "$HOME/.klippertools-download.XXXXXX")"
cleanup() {
    case "$DOWNLOAD_DIR" in
        "$HOME/.klippertools-download."*)
            rm -rf -- "$DOWNLOAD_DIR"
            ;;
    esac
}
trap cleanup EXIT

printf 'Downloading Klippertools Suite from GitHub...\n'
git clone --quiet --depth 1 --branch "$REPOSITORY_REF" \
    -- "$REPOSITORY_URL" "$DOWNLOAD_DIR/repository"

(
    cd "$DOWNLOAD_DIR/repository"
    sha256sum -c SHA256SUMS >/dev/null
)

mv "$DOWNLOAD_DIR/repository" "$TARGET_DIR"

printf 'Download verified. Starting the transactional installer...\n'
export KLIPPERTOOLS_SOURCE_URL="$REPOSITORY_URL"
export KLIPPERTOOLS_SOURCE_REF="$REPOSITORY_REF"
if ! "$TARGET_DIR/scripts/install.sh" "$@"; then
    # If rollback completed there is no journal and the verified checkout can
    # be removed, allowing a clean retry.  If a power-loss journal remains,
    # keep the checkout because it may assist manual inspection.
    if [[ ! -e "${PRINTER_DATA_DIR:-$HOME/printer_data}/klippertools-transaction.json" && \
          -d "$TARGET_DIR" ]]; then
        mv "$TARGET_DIR" "$DOWNLOAD_DIR/failed-repository"
    fi
    fail "installation did not complete"
fi
