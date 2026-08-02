#!/usr/bin/env python3
"""Prepare the Klippertools v0.8.1 dashboard-layout hotfix.

The v0.8.0 source archives accidentally repeated the Tool Registry and Health
Timeline panel names in two dashboard arrays. Mainsail therefore inserted many
copies of those cards and its settings screen could not persist a useful hidden
state. This script repairs both supported source archives, adds a getter-level
self-heal for already-saved layouts, and updates release metadata to 0.8.1.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OLD_VERSION = "0.8.0"
NEW_VERSION = "0.8.1"
SOURCE_ARCHIVES = (
    ROOT / "source" / "mainsail-v2.17.0-klippertools-source.zip",
    ROOT / "source" / "mainsail-v2.18.2-klippertools-source.zip",
)
TARGET_PANEL_RE = re.compile(r"^(?P<indent>\s*)'(?P<name>tool-registry|health-timeline)',\s*$")
RETURN_RE = re.compile(
    r"(?m)^(?P<indent>\s*)return panels\.filter\(\(element(?P<any_type>:\s*any)?\)\s*=>\s*"
    r"allPossiblePanels\.includes\(element\.name\)\)\s*;?\s*$"
)


def replace_required(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise RuntimeError(f"expected text not found in {path}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def collapse_target_runs(text: str) -> tuple[str, int]:
    """Deduplicate exact panel-name lines inside each contiguous array run."""
    output: list[str] = []
    seen: set[str] = set()
    removed = 0

    for line in text.splitlines(keepends=True):
        match = TARGET_PANEL_RE.match(line.rstrip("\r\n"))
        if match:
            name = match.group("name")
            if name in seen:
                removed += 1
                continue
            seen.add(name)
        else:
            seen.clear()
        output.append(line)

    return "".join(output), removed


def add_self_heal(text: str, archive: Path) -> str:
    if "v0.8.1 self-heal" in text:
        return text

    matches = list(RETURN_RE.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(
            f"{archive}: expected one compatible dashboard return statement, found {len(matches)}"
        )

    match = matches[0]
    indent = match.group("indent")
    element = "element: any" if match.group("any_type") else "element"
    replacement = f"""{indent}// v0.8.1 self-heal: old v0.8.0 layouts may contain duplicate
{indent}// Klippertools panel entries. Keep the first saved visibility/order entry
{indent}// for each panel so Dashboard and Interface Settings become usable again.
{indent}const seenPanelNames = new Set<string>()
{indent}return panels.filter(({element}) => {{
{indent}    if (!allPossiblePanels.includes(element.name) || seenPanelNames.has(element.name)) return false
{indent}    seenPanelNames.add(element.name)
{indent}    return true
{indent}}})"""
    return text[: match.start()] + replacement + text[match.end() :]


def repair_getters(data: bytes, archive: Path) -> bytes:
    text = data.decode("utf-8")
    text, removed = collapse_target_runs(text)
    if removed < 2 and "v0.8.1 self-heal" not in text:
        raise RuntimeError(f"{archive}: duplicate dashboard panel run was not found")

    text = add_self_heal(text, archive)

    standalone = [
        match.group("name")
        for line in text.splitlines()
        if (match := TARGET_PANEL_RE.match(line))
    ]
    for name in ("tool-registry", "health-timeline"):
        if standalone.count(name) != 2:
            raise RuntimeError(
                f"{archive}: expected two intentional standalone {name!r} entries, "
                f"found {standalone.count(name)}"
            )
    return text.encode("utf-8")


def repair_source_archive(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing source archive: {path}")

    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".zip", delete=False) as handle:
        temporary = Path(handle.name)

    try:
        found_getters = False
        with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(
            temporary, "w", allowZip64=True
        ) as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == "src/store/gui/getters.ts":
                    data = repair_getters(data, path)
                    found_getters = True
                elif info.filename == "klippertools-build.txt":
                    data = data.replace(OLD_VERSION.encode(), NEW_VERSION.encode())
                target.writestr(info, data)
        if not found_getters:
            raise RuntimeError(f"{path}: src/store/gui/getters.ts is missing")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def update_release_metadata() -> None:
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = NEW_VERSION
    manifest["released"] = "2026-08-02"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    replace_required(
        ROOT / "scripts" / "lifecycle.py",
        f'VERSION = "{OLD_VERSION}"',
        f'VERSION = "{NEW_VERSION}"',
    )
    replace_required(
        ROOT / "tests" / "test_release_metadata.py",
        f'EXPECTED_VERSION = "{OLD_VERSION}"',
        f'EXPECTED_VERSION = "{NEW_VERSION}"',
    )

    for path in sorted((ROOT / "klipper").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        old = f'PLUGIN_VERSION = "{OLD_VERSION}"'
        if old in text:
            path.write_text(
                text.replace(old, f'PLUGIN_VERSION = "{NEW_VERSION}"'),
                encoding="utf-8",
            )

    for relative in (
        "README.md",
        "mainsail/klippertools-build.txt",
        "scripts/build-mainsail-v0.8.0.sh",
        ".github/workflows/build-v08.yml",
        ".github/workflows/validate.yml",
        "docs/ARCHITECTURE.md",
        "docs/VALIDATION.md",
    ):
        path = ROOT / relative
        if path.exists():
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(OLD_VERSION, NEW_VERSION), encoding="utf-8")

    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    heading = f"## {NEW_VERSION} - 2026-08-02"
    if heading not in text:
        entry = f"""{heading}

- Fixed the v0.8.0 dashboard registration typo that repeated Nozzle & Tool
  Registry and Printer Health Timeline entries in every Mainsail layout.
- Added a safe getter-level deduplication migration so already-contaminated
  browser layouts recover automatically while preserving the first saved order
  and visibility value for each panel.
- Rebuilt and linted both supported Mainsail versions and repackaged the suite.

"""
        marker = "# Changelog\n\n"
        if marker not in text:
            raise RuntimeError("CHANGELOG.md heading not found")
        changelog.write_text(text.replace(marker, marker + entry, 1), encoding="utf-8")


def main() -> None:
    update_release_metadata()
    for archive in SOURCE_ARCHIVES:
        repair_source_archive(archive)
    print("Prepared Klippertools v0.8.1 dashboard duplicate hotfix")


if __name__ == "__main__":
    main()
