# Klippertools Calibration Center
#
# Copyright (C) 2026 Klippertools contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import re
import shlex


PLUGIN_VERSION = "0.5.0"
_PROFILE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


FLOW_DEFINITIONS = {
    "pid": {
        "title": "PID calibration",
        "command": "PID_CALIBRATE",
        "required_objects": ("heaters",),
        "requires_homing": False,
        "attended": True,
        "heats": True,
        "moves": False,
        "permanent_result": True,
    },
    "bed_mesh": {
        "title": "Bed mesh",
        "command": "BED_MESH_CALIBRATE",
        "required_objects": ("bed_mesh",),
        "requires_homing": True,
        "attended": True,
        "heats": False,
        "moves": True,
        "permanent_result": True,
    },
    "z_offset": {
        "title": "Z offset",
        "commands": ("PROBE_CALIBRATE", "Z_ENDSTOP_CALIBRATE"),
        "required_objects": (),
        "requires_homing": True,
        "attended": True,
        "heats": False,
        "moves": True,
        "permanent_result": True,
    },
    "input_shaper": {
        "title": "Input shaper",
        "command": "SHAPER_CALIBRATE",
        "required_objects": ("resonance_tester", "input_shaper"),
        "requires_homing": True,
        "attended": True,
        "heats": False,
        "moves": True,
        "permanent_result": True,
    },
    "pressure_advance": {
        "title": "Pressure advance",
        "commands": ("TUNING_TOWER", "SET_PRESSURE_ADVANCE"),
        "required_objects": ("extruder",),
        "requires_homing": False,
        "attended": True,
        "heats": False,
        "moves": False,
        "permanent_result": False,
    },
    "rotation_distance": {
        "title": "Extruder rotation distance",
        "required_objects": ("configfile", "extruder"),
        "requires_homing": False,
        "attended": True,
        "heats": False,
        "moves": False,
        "permanent_result": False,
    },
    "first_layer": {
        "title": "First-layer check",
        "required_objects": ("toolhead", "extruder"),
        "requires_homing": False,
        "attended": True,
        "heats": False,
        "moves": False,
        "permanent_result": False,
    },
}


class CalibrationCenter:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.objects = {}
        self.available_commands = set()
        self.ready = False
        self.state = "idle"
        self.phase = "ready"
        self.active_flow = None
        self.message = "Choose a calibration workflow"
        self.error = None
        self.started_at = None
        self.finished_at = None
        self.session_id = 0
        self.last_result = None
        self.last_command = None

        self.gcode.register_command(
            "CALIBRATION_CENTER_START", self.cmd_CALIBRATION_CENTER_START,
            desc="Start one attended Calibration Center workflow")
        self.gcode.register_command(
            "CALIBRATION_CENTER_ABORT", self.cmd_CALIBRATION_CENTER_ABORT,
            desc="Abort the current Calibration Center workflow")
        self.gcode.register_command(
            "CALIBRATION_CENTER_RESET", self.cmd_CALIBRATION_CENTER_RESET,
            desc="Clear Calibration Center session state")
        self.gcode.register_command(
            "CALIBRATION_CENTER_ROTATION_DISTANCE",
            self.cmd_CALIBRATION_CENTER_ROTATION_DISTANCE,
            desc="Calculate a review-only extruder rotation distance")
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.printer.register_event_handler(
            "klippy:shutdown", self._handle_shutdown)

    def _handle_ready(self):
        names = {
            "bed_mesh", "configfile", "extruder", "heaters", "input_shaper",
            "manual_probe", "pause_resume", "print_stats", "probe",
            "resonance_tester", "toolhead",
        }
        self.objects = {
            name: self.printer.lookup_object(name, None) for name in names
        }
        status = self.gcode.get_status(self.reactor.monotonic())
        self.available_commands = set(status.get("commands", {}))
        self.ready = True
        self.state = "idle"
        self.phase = "ready"
        self.message = "Choose a calibration workflow"

    def _handle_shutdown(self):
        if self.state in ("running", "guided"):
            self._fail("Klipper shutdown during calibration")

    def _object(self, name):
        obj = self.objects.get(name)
        if obj is None:
            obj = self.printer.lookup_object(name, None)
            if obj is not None:
                self.objects[name] = obj
        return obj

    def _object_status(self, name, eventtime=None):
        obj = self._object(name)
        if obj is None:
            return {}
        if eventtime is None:
            eventtime = self.reactor.monotonic()
        return obj.get_status(eventtime)

    def _command_available(self, command):
        # Some helper commands (notably TESTZ/ACCEPT/ABORT) are registered only
        # while their interactive tool is active, so refresh instead of relying
        # solely on the ready-time snapshot.
        status = self.gcode.get_status(self.reactor.monotonic())
        self.available_commands = set(status.get("commands", {}))
        return command in self.available_commands

    def _flow_availability(self, flow):
        definition = FLOW_DEFINITIONS[flow]
        missing_commands = []
        if "command" in definition:
            command = definition["command"]
            if not self._command_available(command):
                missing_commands.append(command)
        for command in definition.get("commands", ()):
            if not self._command_available(command):
                missing_commands.append(command)

        missing_objects = [
            name for name in definition.get("required_objects", ())
            if self._object(name) is None
        ]
        selected_command = definition.get("command")
        if flow == "z_offset":
            probe_ready = (
                self._object("probe") is not None
                and self._command_available("PROBE_CALIBRATE")
            )
            endstop_ready = self._command_available("Z_ENDSTOP_CALIBRATE")
            if probe_ready:
                selected_command = "PROBE_CALIBRATE"
                missing_commands = []
            elif endstop_ready:
                selected_command = "Z_ENDSTOP_CALIBRATE"
                missing_commands = []
            else:
                selected_command = None

        available = not missing_commands and not missing_objects
        reason = None
        if missing_commands:
            reason = "Missing command(s): %s" % ", ".join(missing_commands)
        elif missing_objects:
            reason = "Missing Klipper object(s): %s" % ", ".join(
                missing_objects)
        elif flow == "z_offset" and selected_command is None:
            available = False
            reason = "No probe or Z-endstop calibration command is available"
        return {
            "available": available,
            "reason": reason,
            "command": selected_command,
        }

    def _assert_ready(self, gcmd):
        if not self.ready:
            raise gcmd.error("Calibration Center is not ready")
        if self.state in ("running", "guided"):
            raise gcmd.error("A Calibration Center workflow is already active")
        print_state = self._object_status("print_stats").get("state")
        paused = self._object_status("pause_resume").get("is_paused", False)
        if print_state in ("printing", "paused") or paused:
            raise gcmd.error(
                "Calibration cannot start while a print is active or paused")

    def _assert_confirmed(self, gcmd):
        confirmed = gcmd.get("CONFIRM", "").strip().upper()
        if confirmed != "YES":
            raise gcmd.error(
                "Set CONFIRM=YES after reviewing the attended-operation warning")

    def _assert_homed(self, gcmd):
        status = self._object_status("toolhead")
        homed_axes = status.get("homed_axes", "")
        if not all(axis in homed_axes for axis in "xyz"):
            raise gcmd.error("Home X, Y, and Z before this calibration")

    def _start(self, flow, phase, message):
        self.state = "running"
        self.phase = phase
        self.active_flow = flow
        self.message = message
        self.error = None
        self.started_at = self.reactor.monotonic()
        self.finished_at = None
        self.last_result = None
        self.last_command = None
        self.session_id += 1

    def _review(self, message, result=None):
        self.state = "review"
        self.phase = "review"
        self.message = message
        self.last_result = result
        self.finished_at = self.reactor.monotonic()

    def _guide(self, message, result=None):
        self.state = "guided"
        self.phase = "guided"
        self.message = message
        self.last_result = result
        self.finished_at = None

    def _fail(self, message):
        self.state = "error"
        self.phase = "error"
        self.message = str(message)
        self.error = str(message)
        self.finished_at = self.reactor.monotonic()

    def _run(self, command):
        self.last_command = command
        try:
            self.gcode.run_script_from_command(command)
        except self.printer.command_error as error:
            self._fail(error)
            raise

    def _config_status(self):
        return self._object_status("configfile")

    def _settings(self):
        return self._config_status().get("settings", {})

    def _heater_limits(self, heater):
        settings = self._settings().get(heater, {})
        min_temp = settings.get("min_temp")
        max_temp = settings.get("max_temp")
        return (
            float(min_temp) if min_temp is not None else None,
            float(max_temp) if max_temp is not None else None,
        )

    def _start_pid(self, gcmd):
        heater = gcmd.get("HEATER").strip()
        heaters = self._object_status("heaters").get("available_heaters", [])
        if heater not in heaters:
            raise gcmd.error("HEATER must name an available Klipper heater")
        target = gcmd.get_float("TARGET")
        min_temp, max_temp = self._heater_limits(heater)
        if min_temp is None or max_temp is None:
            raise gcmd.error(
                "Unable to verify this heater's configured temperature limits")
        if not min_temp < target < max_temp:
            raise gcmd.error(
                "TARGET must be inside the heater's configured min/max limits")
        self._start("pid", "heating", "Running attended PID calibration")
        command = "PID_CALIBRATE HEATER=%s TARGET=%.3f" % (
            shlex.quote(heater), target)
        self._run(command)
        self._review(
            "PID result ready for review; SAVE_CONFIG was not run",
            {"heater": heater, "target": target})

    def _start_bed_mesh(self, gcmd):
        self._assert_homed(gcmd)
        profile = gcmd.get("PROFILE", None)
        command = "BED_MESH_CALIBRATE"
        if profile is not None:
            profile = profile.strip()
            if not _PROFILE_RE.match(profile):
                raise gcmd.error(
                    "PROFILE may contain only letters, numbers, dot, dash, and underscore")
            command += " PROFILE=%s" % profile
        self._start("bed_mesh", "probing", "Running attended bed mesh")
        self._run(command)
        self._review(
            "Bed mesh complete and active; review it before any SAVE_CONFIG",
            {"profile": profile})

    def _start_z_offset(self, gcmd, command):
        self._assert_homed(gcmd)
        self._start("z_offset", "manual_probe", "Z-offset helper is active")
        self._run(command)
        manual_status = self._object_status("manual_probe")
        if not manual_status.get("is_active", False):
            self._review(
                "Z-offset helper finished; review pending config before saving")

    def _start_input_shaper(self, gcmd):
        self._assert_homed(gcmd)
        axis = gcmd.get("AXIS", "BOTH").strip().upper()
        if axis not in ("X", "Y", "BOTH"):
            raise gcmd.error("AXIS must be X, Y, or BOTH")
        command = "SHAPER_CALIBRATE"
        if axis != "BOTH":
            command += " AXIS=%s" % axis
        self._start(
            "input_shaper", "vibrating",
            "Running attended input-shaper calibration")
        self._run(command)
        self._review(
            "Input-shaper result ready for review; SAVE_CONFIG was not run",
            {"axis": axis})

    def _start_pressure_advance(self, gcmd):
        start = gcmd.get_float("START", minval=0.0, maxval=5.0)
        factor = gcmd.get_float("FACTOR", above=0.0, maxval=1.0)
        command = (
            "TUNING_TOWER COMMAND=SET_PRESSURE_ADVANCE "
            "PARAMETER=ADVANCE START=%.6f FACTOR=%.6f" % (start, factor)
        )
        self._start(
            "pressure_advance", "command_review",
            "Preparing the user-supplied pressure-advance test command")
        # Do not arm TUNING_TOWER from the backend. The command changes runtime
        # print behavior and has no universal cancel command, so the UI presents
        # this exact preview for a separate send action immediately before the
        # reviewed test print.
        self.last_command = command
        self._guide(
            "Pressure-advance command ready for review; nothing was sent",
            {"start": start, "factor": factor, "command_preview": command})

    def _start_first_layer(self):
        self._start(
            "first_layer", "guided_check",
            "First-layer check uses the user's reviewed sliced test")
        self._guide(
            "Start the reviewed first-layer file from Mainsail; no motion or heat was started")

    cmd_CALIBRATION_CENTER_START_help = (
        "Start one attended Calibration Center workflow")
    def cmd_CALIBRATION_CENTER_START(self, gcmd):
        self._assert_ready(gcmd)
        flow = gcmd.get("FLOW").strip().lower()
        if flow not in FLOW_DEFINITIONS:
            raise gcmd.error("Unknown Calibration Center FLOW")
        availability = self._flow_availability(flow)
        if not availability["available"]:
            raise gcmd.error(availability["reason"])
        self._assert_confirmed(gcmd)

        if flow == "pid":
            self._start_pid(gcmd)
        elif flow == "bed_mesh":
            self._start_bed_mesh(gcmd)
        elif flow == "z_offset":
            self._start_z_offset(gcmd, availability["command"])
        elif flow == "input_shaper":
            self._start_input_shaper(gcmd)
        elif flow == "pressure_advance":
            self._start_pressure_advance(gcmd)
        elif flow == "rotation_distance":
            raise gcmd.error(
                "Use CALIBRATION_CENTER_ROTATION_DISTANCE after measuring filament")
        elif flow == "first_layer":
            self._start_first_layer()
        gcmd.respond_info(self.message)

    cmd_CALIBRATION_CENTER_ROTATION_DISTANCE_help = (
        "Calculate a review-only extruder rotation distance")
    def cmd_CALIBRATION_CENTER_ROTATION_DISTANCE(self, gcmd):
        self._assert_ready(gcmd)
        self._assert_confirmed(gcmd)
        previous = gcmd.get_float("PREVIOUS", above=0.0)
        requested = gcmd.get_float("REQUESTED", above=0.0)
        actual = gcmd.get_float("ACTUAL", above=0.0)
        result = previous * actual / requested
        self._start(
            "rotation_distance", "calculating",
            "Calculating review-only rotation distance")
        self._review(
            "Calculated rotation distance %.3f; no configuration was changed" % result,
            {
                "previous": previous,
                "requested": requested,
                "actual": actual,
                "rotation_distance": round(result, 3),
            })
        gcmd.respond_info(self.message)

    cmd_CALIBRATION_CENTER_ABORT_help = (
        "Abort the current Calibration Center workflow")
    def cmd_CALIBRATION_CENTER_ABORT(self, gcmd):
        if self.active_flow == "z_offset":
            manual = self._object_status("manual_probe")
            if manual.get("is_active", False) and self._command_available("ABORT"):
                self._run("ABORT")
        self.state = "idle"
        self.phase = "ready"
        self.active_flow = None
        self.message = "Calibration Center workflow aborted"
        self.error = None
        self.finished_at = self.reactor.monotonic()
        self.session_id += 1
        gcmd.respond_info(self.message)

    cmd_CALIBRATION_CENTER_RESET_help = "Clear Calibration Center session state"
    def cmd_CALIBRATION_CENTER_RESET(self, gcmd):
        if self.state == "running":
            raise gcmd.error("Abort the active calibration before resetting")
        self.state = "idle"
        self.phase = "ready"
        self.active_flow = None
        self.message = "Choose a calibration workflow"
        self.error = None
        self.started_at = None
        self.finished_at = None
        self.last_result = None
        self.last_command = None
        self.session_id += 1
        gcmd.respond_info("Calibration Center reset")

    def _current_values(self, eventtime):
        settings = self._settings()
        config_status = self._config_status()
        extruder = self._object_status("extruder", eventtime)
        bed_mesh = self._object_status("bed_mesh", eventtime)
        probe_settings = settings.get("probe", {})
        stepper_z = settings.get("stepper_z", {})
        input_shaper = settings.get("input_shaper", {})
        extruder_settings = settings.get("extruder", {})
        return {
            "pressure_advance": extruder.get("pressure_advance"),
            "rotation_distance": extruder_settings.get("rotation_distance"),
            "probe_z_offset": probe_settings.get("z_offset"),
            "z_endstop_position": stepper_z.get("position_endstop"),
            "input_shaper": {
                "shaper_type_x": input_shaper.get("shaper_type_x"),
                "shaper_freq_x": input_shaper.get("shaper_freq_x"),
                "shaper_type_y": input_shaper.get("shaper_type_y"),
                "shaper_freq_y": input_shaper.get("shaper_freq_y"),
            },
            "bed_mesh_profile": bed_mesh.get("profile_name"),
            "save_config_pending": config_status.get(
                "save_config_pending", False),
            "save_config_pending_items": config_status.get(
                "save_config_pending_items", {}),
        }

    def get_status(self, eventtime):
        if self.active_flow == "z_offset" and self.state == "running":
            manual = self._object_status("manual_probe", eventtime)
            if not manual.get("is_active", False):
                self._review(
                    "Z-offset helper finished; review pending config before saving")
        elapsed = 0
        if self.started_at is not None:
            end = self.finished_at or eventtime
            elapsed = max(0, int(round(end - self.started_at)))
        flows = {}
        for flow, definition in FLOW_DEFINITIONS.items():
            availability = self._flow_availability(flow)
            flows[flow] = dict(definition)
            flows[flow].update(availability)
        return {
            "version": PLUGIN_VERSION,
            "ready": self.ready,
            "session_id": self.session_id,
            "state": self.state,
            "phase": self.phase,
            "active_flow": self.active_flow,
            "active": self.state in ("running", "guided"),
            "message": self.message,
            "error": self.error,
            "elapsed_seconds": elapsed,
            "last_result": self.last_result,
            "last_command": self.last_command,
            "flows": flows,
            "current_values": self._current_values(eventtime),
            "automatic_save": False,
        }


def load_config(config):
    return CalibrationCenter(config)
