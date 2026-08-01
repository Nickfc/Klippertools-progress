#!/usr/bin/env python3
"""Safely add or remove the Klippertools include in printer.cfg."""

import argparse
import os
from pathlib import Path
import tempfile


INCLUDE_LINE = "[include klippertools.cfg]"
COMMENT_LINE = "# Added by Klippertools Suite"


def add_include(text):
    lines = text.splitlines(keepends=True)
    if any(line.strip() == INCLUDE_LINE for line in lines):
        return text, False

    insertion = len(lines)
    save_config = next(
        (index for index, line in enumerate(lines)
         if line.strip().startswith("#*# <---------------------- SAVE_CONFIG")),
        None,
    )
    if save_config is not None:
        insertion = save_config

    mainsail = next(
        (index for index, line in enumerate(lines)
         if line.strip() == "[include mainsail.cfg]"),
        None,
    )
    if mainsail is not None:
        insertion = mainsail + 1

    block = [COMMENT_LINE + "\n", INCLUDE_LINE + "\n"]
    if insertion and lines[insertion - 1].strip():
        block.insert(0, "\n")
    if insertion < len(lines) and lines[insertion].strip():
        block.append("\n")
    lines[insertion:insertion] = block
    return "".join(lines), True


def remove_include(text):
    lines = text.splitlines(keepends=True)
    output = []
    changed = False
    for line in lines:
        stripped = line.strip()
        if stripped in (INCLUDE_LINE, COMMENT_LINE):
            changed = True
            continue
        output.append(line)

    # Collapse only the extra blank run that our two-line block may leave.
    compact = []
    for line in output:
        if line.strip() or not compact or compact[-1].strip():
            compact.append(line)
    return "".join(compact), changed


def atomic_write(path, text):
    stat_result = path.stat()
    descriptor, temp_name = tempfile.mkstemp(
        prefix=path.name + ".", dir=str(path.parent), text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp_name, stat_result.st_mode)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("add", "remove"))
    parser.add_argument("printer_cfg", type=Path)
    args = parser.parse_args()

    path = args.printer_cfg.resolve()
    if not path.is_file():
        parser.error(f"not a file: {path}")

    original = path.read_text(encoding="utf-8")
    transform = add_include if args.action == "add" else remove_include
    updated, changed = transform(original)
    if changed:
        atomic_write(path, updated)
    print("updated" if changed else "unchanged")


if __name__ == "__main__":
    main()
