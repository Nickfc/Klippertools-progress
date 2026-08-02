# Klippertools Nozzle Guard
#
# Copyright (C) 2026 Klippertools contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
import os
import re


PLUGIN_VERSION = "0.8.0"
DEFAULT_SCAN_BYTES = 512 * 1024
_PROFILE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class NozzleMetadataParser:
    """Extract numeric nozzle diameters from common slicer comments."""

    _patterns = [
        re.compile(
            r"^\s*;\s*nozzle[_ ]diameter\s*[:=]\s*"
            r"([0-9]+(?:\.[0-9]+)?(?:\s*[,;]\s*"
            r"[0-9]+(?:\.[0-9]+)?)*)",
            re.IGNORECASE | re.MULTILINE),
        re.compile(
            r"^\s*;\s*nozzle[_ ]size\s*[:=]\s*"
            r"([0-9]+(?:\.[0-9]+)?)",
            re.IGNORECASE | re.MULTILINE),
    ]

    @classmethod
    def parse(cls, text):
        values = []
        source = None
        for pattern in cls._patterns:
            for match in pattern.finditer(text):
                if source is None:
                    source = match.group(0).splitlines()[0].strip()
                for raw_value in re.findall(
                        r"[0-9]+(?:\.[0-9]+)?", match.group(1)):
                    value = float(raw_value)
                    if 0.05 <= value <= 5.0 and value not in values:
                        values.append(value)
        return values, source


class NozzleGuardModel:
    def __init__(self, configured_nozzle, tolerance=0.01, mode="block"):
        self.klipper_nozzle = float(configured_nozzle)
        self.configured_nozzle = float(configured_nozzle)
        self.installed_profile_id = None
        self.installed_profile_name = None
        self.comparison_source = "klipper"
        self.tolerance = float(tolerance)
        self.mode = mode
        self.session_id = 0
        self.clear()

    def clear(self):
        self.filename = None
        self.detected_nozzles = []
        self.metadata_source = None
        self.state = "no_file"
        self.message = "No G-code file selected"
        self.overridden = False
        self.session_id += 1

    def set_installed_tool(self, diameter, profile_id, profile_name=None):
        diameter = float(diameter)
        if not 0.05 <= diameter <= 5.0:
            raise ValueError("installed tool diameter must be between 0.05 and 5.0 mm")
        if not _PROFILE_RE.fullmatch(str(profile_id)):
            raise ValueError("installed tool profile id is invalid")
        self.configured_nozzle = diameter
        self.installed_profile_id = str(profile_id)
        self.installed_profile_name = str(profile_name or profile_id)[:100]
        self.comparison_source = "registry"
        self.overridden = False
        self.session_id += 1
        self._evaluate()

    def clear_installed_tool(self):
        self.configured_nozzle = self.klipper_nozzle
        self.installed_profile_id = None
        self.installed_profile_name = None
        self.comparison_source = "klipper"
        self.overridden = False
        self.session_id += 1
        self._evaluate()

    def inspect(self, filename, text):
        self.filename = filename
        self.overridden = False
        self.detected_nozzles, self.metadata_source = NozzleMetadataParser.parse(text)
        self.session_id += 1
        self._evaluate()

    def _reference_label(self):
        if self.comparison_source == "registry":
            return "installed tool profile"
        return "Klipper configuration"

    def _evaluate(self):
        if self.filename is None:
            self.state = "no_file"
            self.message = "No G-code file selected"
            return
        if self.mode == "off":
            self.state = "disabled"
            self.message = "Nozzle Guard is disabled"
            return
        if not self.detected_nozzles:
            self.state = "unknown"
            self.message = "No nozzle metadata found; print is allowed"
            return
        mismatch = any(
            abs(value - self.configured_nozzle) > self.tolerance
            for value in self.detected_nozzles)
        if mismatch:
            self.state = "mismatch"
            self.message = "G-code nozzle does not match the %s" % self._reference_label()
            return
        self.state = "match"
        self.message = "G-code nozzle matches the %s" % self._reference_label()

    def mark_error(self, filename, message):
        self.filename = filename
        self.detected_nozzles = []
        self.metadata_source = None
        self.state = "error"
        self.message = str(message)
        self.overridden = False
        self.session_id += 1

    def override_once(self):
        if self.state != "mismatch":
            return False
        self.overridden = True
        self.state = "overridden"
        self.message = "Mismatch acknowledged for this selected file"
        return True

    def blocks_start(self):
        return self.mode == "block" and self.state == "mismatch"

    def get_status(self):
        return {
            "version": PLUGIN_VERSION,
            "session_id": self.session_id,
            "state": self.state,
            "message": self.message,
            "mode": self.mode,
            "blocking": self.blocks_start(),
            "filename": self.filename,
            "configured_nozzle": round(self.configured_nozzle, 3),
            "klipper_nozzle": round(self.klipper_nozzle, 3),
            "comparison_source": self.comparison_source,
            "installed_profile_id": self.installed_profile_id,
            "installed_profile_name": self.installed_profile_name,
            "detected_nozzles": [round(value, 3) for value in self.detected_nozzles],
            "tolerance": self.tolerance,
            "metadata_source": self.metadata_source,
            "overridden": self.overridden,
        }


class NozzleGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.reactor = self.printer.get_reactor()
        self.scan_bytes = config.getint("scan_bytes", DEFAULT_SCAN_BYTES, minval=4096)
        self.tolerance = config.getfloat("tolerance", 0.01, minval=0.0, maxval=0.25)
        self.mode = config.getchoice(
            "mode", {"block": "block", "warn": "warn", "off": "off"},
            default="block")
        self.model = NozzleGuardModel(0.4, self.tolerance, self.mode)
        self.virtual_sdcard = None
        self.print_stats = None
        self.original_load_file = None
        self.original_do_resume = None
        self.ready = False

        self.gcode.register_command(
            "NOZZLE_GUARD_RECHECK", self.cmd_NOZZLE_GUARD_RECHECK,
            desc="Re-read nozzle metadata from the selected G-code file")
        self.gcode.register_command(
            "NOZZLE_GUARD_OVERRIDE", self.cmd_NOZZLE_GUARD_OVERRIDE,
            desc="Allow one selected file despite a nozzle mismatch")
        self.gcode.register_command(
            "NOZZLE_GUARD_STATUS", self.cmd_NOZZLE_GUARD_STATUS,
            desc="Report the current Nozzle Guard result")
        self.gcode.register_command(
            "NOZZLE_GUARD_SET_TOOL", self.cmd_NOZZLE_GUARD_SET_TOOL,
            desc="Set the installed Tool Registry profile in memory")
        self.gcode.register_command(
            "NOZZLE_GUARD_CLEAR_TOOL", self.cmd_NOZZLE_GUARD_CLEAR_TOOL,
            desc="Return Nozzle Guard to Klipper nozzle configuration")
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.printer.register_event_handler("virtual_sdcard:reset_file", self._handle_reset_file)

    def _handle_ready(self):
        extruder = self.printer.lookup_object("extruder", None)
        self.virtual_sdcard = self.printer.lookup_object("virtual_sdcard", None)
        self.print_stats = self.printer.lookup_object("print_stats", None)
        if extruder is None or self.virtual_sdcard is None:
            self.model.mark_error(None, "Nozzle Guard requires [extruder] and [virtual_sdcard]")
            logging.warning("nozzle_guard: [extruder] or [virtual_sdcard] missing")
            return

        self.model = NozzleGuardModel(extruder.nozzle_diameter, self.tolerance, self.mode)
        self.original_load_file = self.virtual_sdcard._load_file
        self.original_do_resume = self.virtual_sdcard.do_resume
        self.virtual_sdcard._load_file = self._guarded_load_file
        self.virtual_sdcard.do_resume = self._guarded_resume
        self.ready = True

    def _handle_reset_file(self):
        self.model.clear()

    def _guarded_load_file(self, gcmd, filename, check_subdirs=False):
        result = self.original_load_file(gcmd, filename, check_subdirs=check_subdirs)
        self._inspect_current_file()
        return result

    def _guarded_resume(self):
        if self.model.blocks_start():
            expected = ", ".join("%.3g" % value for value in self.model.detected_nozzles)
            source = (
                "installed Tool Registry profile %s" % self.model.installed_profile_name
                if self.model.comparison_source == "registry"
                else "Klipper configuration")
            raise self.gcode.error(
                "Nozzle Guard blocked this print: G-code expects %s mm, but the %s is %.3g mm. "
                "Install the matching tool/profile or run NOZZLE_GUARD_OVERRIDE to acknowledge this selected file."
                % (expected, source, self.model.configured_nozzle))
        if self.model.state == "mismatch":
            self.gcode.respond_info("Nozzle Guard warning: selected G-code nozzle differs from the active reference")
        return self.original_do_resume()

    def _selected_filename(self):
        if self.virtual_sdcard is None:
            return None
        path = self.virtual_sdcard.file_path()
        if not path:
            return None
        try:
            return os.path.relpath(path, self.virtual_sdcard.sdcard_dirname)
        except (AttributeError, ValueError):
            return os.path.basename(path)

    def _read_metadata_text(self, path):
        with open(path, "rb") as gcode_file:
            head = gcode_file.read(self.scan_bytes)
            gcode_file.seek(0, os.SEEK_END)
            file_size = gcode_file.tell()
            tail_start = max(0, file_size - self.scan_bytes)
            gcode_file.seek(tail_start)
            tail = gcode_file.read(self.scan_bytes)
        if tail_start < len(head):
            payload = head + tail[len(head) - tail_start:]
        else:
            payload = head + b"\n" + tail
        return payload.decode("utf-8", errors="replace")

    def _inspect_current_file(self):
        if self.virtual_sdcard is None:
            return
        path = self.virtual_sdcard.file_path()
        filename = self._selected_filename()
        if not path or not filename:
            self.model.clear()
            return
        try:
            text = self._read_metadata_text(path)
            self.model.inspect(filename, text)
        except (IOError, OSError) as error:
            logging.exception("nozzle_guard: metadata read failed")
            self.model.mark_error(filename, "Unable to inspect nozzle metadata: %s" % error)

    def get_status(self, eventtime):
        status = self.model.get_status()
        status["ready"] = self.ready
        return status

    cmd_NOZZLE_GUARD_RECHECK_help = "Re-read nozzle metadata from the selected G-code file"
    def cmd_NOZZLE_GUARD_RECHECK(self, gcmd):
        if self.virtual_sdcard is None or self.virtual_sdcard.file_path() is None:
            raise gcmd.error("No G-code file is selected")
        self._inspect_current_file()
        gcmd.respond_info(self.model.message)

    cmd_NOZZLE_GUARD_OVERRIDE_help = "Allow one selected file despite a nozzle mismatch"
    def cmd_NOZZLE_GUARD_OVERRIDE(self, gcmd):
        if not self.model.override_once():
            raise gcmd.error("There is no active nozzle mismatch to override")
        gcmd.respond_info("Nozzle Guard override accepted for %s" % self.model.filename)

    def _assert_tool_change_idle(self, gcmd):
        if self.print_stats is None:
            raise gcmd.error(
                "Nozzle Guard cannot verify print state for a tool change")
        state = str(
            self.print_stats.get_status(self.reactor.monotonic()).get(
                "state", "unknown")).lower()
        if state in ("printing", "paused"):
            raise gcmd.error(
                "Installed tool reference cannot change while printing or paused")

    cmd_NOZZLE_GUARD_SET_TOOL_help = "Set the installed Tool Registry profile in memory"
    def cmd_NOZZLE_GUARD_SET_TOOL(self, gcmd):
        self._assert_tool_change_idle(gcmd)
        diameter = gcmd.get_float("DIAMETER", minval=0.05, maxval=5.0)
        profile_id = gcmd.get("PROFILE").strip()
        profile_name = gcmd.get("NAME", profile_id).strip()
        try:
            self.model.set_installed_tool(diameter, profile_id, profile_name)
        except ValueError as error:
            raise gcmd.error(str(error))
        gcmd.respond_info(
            "Nozzle Guard now compares against installed profile %s (%.3g mm)"
            % (profile_name, diameter))

    cmd_NOZZLE_GUARD_CLEAR_TOOL_help = "Return Nozzle Guard to Klipper nozzle configuration"
    def cmd_NOZZLE_GUARD_CLEAR_TOOL(self, gcmd):
        self._assert_tool_change_idle(gcmd)
        self.model.clear_installed_tool()
        gcmd.respond_info(
            "Nozzle Guard now compares against Klipper %.3g mm"
            % self.model.klipper_nozzle)

    cmd_NOZZLE_GUARD_STATUS_help = "Report the current Nozzle Guard result"
    def cmd_NOZZLE_GUARD_STATUS(self, gcmd):
        status = self.model.get_status()
        detected = status["detected_nozzles"]
        detected_text = ", ".join("%.3g" % value for value in detected) if detected else "unknown"
        reference = (
            "registry profile %s" % status["installed_profile_name"]
            if status["comparison_source"] == "registry"
            else "Klipper")
        gcmd.respond_info(
            "Nozzle Guard: %s; %s %.3g mm; G-code %s mm"
            % (status["state"], reference, status["configured_nozzle"], detected_text))


def load_config(config):
    return NozzleGuard(config)
