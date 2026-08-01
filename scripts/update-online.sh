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

CURRENT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_FILE="${PRINTER_DATA_DIR:-$HOME/printer_data}/klippertools-install-state"
[[ -f "$STATE_FILE" ]] || fail "install state was not found at $STATE_FILE"

for required_command in git sha256sum python3 mktemp mv rm; do
    command -v "$required_command" >/dev/null 2>&1 ||
        fail "missing required command: $required_command"
done

mapfile -t SOURCE_INFO < <(
    python3 "$CURRENT_ROOT/scripts/lifecycle.py" source-info
)
[[ ${#SOURCE_INFO[@]} -ge 2 ]] || fail "install state omitted source metadata"
REPOSITORY_URL="${KLIPPERTOOLS_SOURCE_URL:-${SOURCE_INFO[0]}}"
REPOSITORY_REF="${KLIPPERTOOLS_SOURCE_REF:-${SOURCE_INFO[1]}}"
TARGET_DIR="${KLIPPERTOOLS_DIR:-$HOME/klippertools}"

case "$TARGET_DIR" in
    "$HOME"/*) ;;
    *) fail "the source directory must be inside $HOME" ;;
esac
case "$REPOSITORY_URL" in
    https://*|ssh://*|git@*|file://*) ;;
    *) fail "unsupported or unsafe repository URL" ;;
esac
[[ "$REPOSITORY_URL" != -* ]] || fail "unsafe repository URL"
git check-ref-format --branch "$REPOSITORY_REF" >/dev/null 2>&1 ||
    fail "invalid repository ref: $REPOSITORY_REF"

DOWNLOAD_DIR="$(mktemp -d "$HOME/.klippertools-update.XXXXXX")"
cleanup() {
    case "$DOWNLOAD_DIR" in
        "$HOME/.klippertools-update."*) rm -rf -- "$DOWNLOAD_DIR" ;;
    esac
}
trap cleanup EXIT

printf 'Downloading and verifying the Klippertools update...\n'
git clone --quiet --depth 1 --branch "$REPOSITORY_REF" \
    -- "$REPOSITORY_URL" "$DOWNLOAD_DIR/repository"
(
    cd "$DOWNLOAD_DIR/repository"
    sha256sum -c SHA256SUMS >/dev/null
)

export KLIPPERTOOLS_SOURCE_URL="$REPOSITORY_URL"
export KLIPPERTOOLS_SOURCE_REF="$REPOSITORY_REF"
"$DOWNLOAD_DIR/repository/scripts/update.sh" \
    --source-target "$TARGET_DIR" "$@"

# lifecycle.py atomically moved repository out of DOWNLOAD_DIR.  The trap now
# removes only the empty staging parent.
