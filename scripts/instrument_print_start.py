#!/usr/bin/env python3
"""Add or remove conservative StartFlow markers in PRINT_START."""

import argparse
import os
from pathlib import Path
import re
import tempfile


STAGES = "bed_heat,homing,mesh,nozzle_heat,purge"
MARKER_PREFIX = "# KLIPPERTOOLS_STARTFLOW:"
INSERTIONS = {
    "begin": "START_FLOW_BEGIN STAGES=" + STAGES,
    "bed_heat": "START_FLOW_STAGE NAME=bed_heat",
    "homing": "START_FLOW_STAGE NAME=homing",
    "mesh": "START_FLOW_STAGE NAME=mesh",
    "nozzle_heat": "START_FLOW_STAGE NAME=nozzle_heat",
    "purge": "START_FLOW_STAGE NAME=purge",
    "complete": "START_FLOW_COMPLETE",
}


class InstrumentationError(ValueError):
    pass


def _section_bounds(lines):
    start = next((
        index for index, line in enumerate(lines)
        if line.strip().lower() == "[gcode_macro print_start]"
    ), None)
    if start is None:
        raise InstrumentationError("[gcode_macro PRINT_START] was not found")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break
    return start, end


def _command_indices(lines, start, end, pattern):
    expression = re.compile(pattern, re.IGNORECASE)
    return [
        index for index in range(start, end)
        if expression.match(lines[index].strip())
    ]


def _one_command(lines, start, end, pattern, label):
    matches = _command_indices(lines, start, end, pattern)
    if len(matches) != 1:
        raise InstrumentationError(
            "PRINT_START needs exactly one %s command; found %d"
            % (label, len(matches)))
    return matches[0]


def add_instrumentation(text):
    lines = text.splitlines(keepends=True)
    start, end = _section_bounds(lines)
    markers = [
        line.strip() for line in lines[start:end]
        if line.strip().startswith(MARKER_PREFIX)
    ]
    if markers:
        expected = {
            MARKER_PREFIX + name for name in INSERTIONS
        }
        if set(markers) != expected:
            raise InstrumentationError(
                "PRINT_START contains an incomplete Klippertools marker set")
        return text, False

    gcode_index = _one_command(
        lines, start, end, r"^gcode\s*:\s*$", "gcode:")
    bed_candidates = _command_indices(
        lines, gcode_index + 1, end, r"^M140(?:\s|$)")
    if not bed_candidates:
        bed_candidates = _command_indices(
            lines, gcode_index + 1, end, r"^M190(?:\s|$)")
    if len(bed_candidates) != 1:
        raise InstrumentationError(
            "PRINT_START needs exactly one M140 or M190 heating start; "
            "found %d" % len(bed_candidates))

    homing_index = _one_command(
        lines, gcode_index + 1, end, r"^G28(?:\s|$)", "G28")
    mesh_index = _one_command(
        lines, gcode_index + 1, end,
        r"^BED_MESH_CALIBRATE(?:\s|$)", "BED_MESH_CALIBRATE")
    nozzle_index = _one_command(
        lines, gcode_index + 1, end, r"^M109(?:\s|$)", "M109")
    complete_index = _one_command(
        lines, gcode_index + 1, end,
        r"^RESPOND\s+MSG\s*=\s*[\"']?Print\s+start\s+complete",
        "final Print start complete RESPOND")

    before = {
        gcode_index + 1: [("begin", INSERTIONS["begin"])],
        bed_candidates[0]: [("bed_heat", INSERTIONS["bed_heat"])],
        homing_index: [("homing", INSERTIONS["homing"])],
        mesh_index: [("mesh", INSERTIONS["mesh"])],
        nozzle_index: [("nozzle_heat", INSERTIONS["nozzle_heat"])],
        complete_index: [("complete", INSERTIONS["complete"])],
    }
    after = {
        nozzle_index: [("purge", INSERTIONS["purge"])],
    }

    output = []
    for index, line in enumerate(lines):
        indent = re.match(r"^\s*", line).group(0)
        if index in before:
            for name, command in before[index]:
                output.append(indent + MARKER_PREFIX + name + "\n")
                output.append(indent + command + "\n")
        output.append(line)
        if index in after:
            for name, command in after[index]:
                output.append(indent + MARKER_PREFIX + name + "\n")
                output.append(indent + command + "\n")
    return "".join(output), True


def remove_instrumentation(text):
    lines = text.splitlines(keepends=True)
    output = []
    changed = False
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith(MARKER_PREFIX):
            output.append(lines[index])
            index += 1
            continue
        name = stripped[len(MARKER_PREFIX):]
        expected = INSERTIONS.get(name)
        if expected is None or index + 1 >= len(lines) or \
                lines[index + 1].strip() != expected:
            raise InstrumentationError(
                "Refusing to remove a modified StartFlow marker: %s"
                % stripped)
        changed = True
        index += 2
    return "".join(output), changed


def atomic_write(path, text):
    stat_result = path.stat()
    descriptor, temp_name = tempfile.mkstemp(
        prefix=path.name + ".", dir=str(path.parent), text=True)
    try:
        with os.fdopen(
                descriptor, "w", encoding="utf-8", newline="") as file:
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
    parser.add_argument(
        "--optional", action="store_true",
        help="report unsupported PRINT_START without failing")
    args = parser.parse_args()

    path = args.printer_cfg.resolve()
    if not path.is_file():
        parser.error("not a file: %s" % path)
    original = path.read_text(encoding="utf-8")
    transform = (
        add_instrumentation if args.action == "add"
        else remove_instrumentation)
    try:
        updated, changed = transform(original)
    except InstrumentationError as error:
        if not args.optional:
            parser.error(str(error))
        print("unsupported: %s" % error)
        return
    if changed:
        atomic_write(path, updated)
    print("updated" if changed else "unchanged")


if __name__ == "__main__":
    main()
