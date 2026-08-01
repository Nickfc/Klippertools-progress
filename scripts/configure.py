#!/usr/bin/env python3
"""Safely add or remove the Klippertools include in printer.cfg."""

import argparse
import os
from pathlib import Path
import tempfile


INCLUDE_LINE = "[include klippertools.cfg]"
COMMENT_LINE = "# Added by Klippertools Suite"
BEGIN_LINE = "# >>> KLIPPERTOOLS SUITE: printer.cfg >>>"
END_LINE = "# <<< KLIPPERTOOLS SUITE: printer.cfg <<<"


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

    # Everything inserted is inside explicit ownership markers.  Removing the
    # block can therefore reproduce every unrelated byte, including deliberate
    # runs of blank lines elsewhere in printer.cfg.
    block = [
        BEGIN_LINE + "\n",
        COMMENT_LINE + "\n",
        INCLUDE_LINE + "\n",
        END_LINE + "\n",
    ]
    lines[insertion:insertion] = block
    return "".join(lines), True


def remove_include(text):
    lines = text.splitlines(keepends=True)
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == BEGIN_LINE),
        None,
    )
    if start is not None:
        end = next(
            (
                index
                for index in range(start + 1, len(lines))
                if lines[index].strip() == END_LINE
            ),
            None,
        )
        if end is None:
            raise ValueError("incomplete Klippertools printer.cfg marker block")
        del lines[start : end + 1]
        return "".join(lines), True

    # Compatibility with 0.2.0: remove only an adjacent installer comment and
    # include.  Never compact global whitespace; exact restoration is handled
    # from the transaction backup when printer.cfg was otherwise unchanged.
    for index, line in enumerate(lines):
        if line.strip() != INCLUDE_LINE:
            continue
        start = index
        if index and lines[index - 1].strip() == COMMENT_LINE:
            start -= 1
        del lines[start : index + 1]
        return "".join(lines), True
    return text, False


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
