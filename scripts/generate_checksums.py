#!/usr/bin/env python3
"""Regenerate the deterministic repository checksum manifest."""

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SHA256SUMS"


def included_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == MANIFEST:
            continue
        relative = path.relative_to(ROOT)
        if "__pycache__" in relative.parts or ".git" in relative.parts:
            continue
        if path.name.endswith((".pyc", ".pyo")):
            continue
        # The complete suite archive contains this manifest, so including the
        # archive (or its sidecar) here would create a circular checksum.
        if (
            relative.parent == Path("dist")
            and relative.name.startswith("klippertools-suite-")
            and relative.name.endswith((".zip", ".zip.sha256"))
        ):
            continue
        yield path, relative


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def main():
    lines = [
        "%s  ./%s\n" % (digest(path), relative.as_posix())
        for path, relative in included_files()
    ]
    temporary = MANIFEST.with_suffix(".tmp")
    temporary.write_text("".join(lines), encoding="utf-8")
    temporary.replace(MANIFEST)


if __name__ == "__main__":
    main()
