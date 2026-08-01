# Klippertools Motion Wizard
#
# Copyright (C) 2026 Klippertools contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import time


PLUGIN_VERSION = "0.2.1"


class MotionWizard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.state = "idle"
        self.phase = "ready"
        self.message = "Ready for motion calibration"
        self.error = None
        self.completed_axes = set()
        self.noise_complete = False
        self.pending_save = False
        self.started_at = None
        self.finished_at = None
        self.session_id = 0
        self.resonance_tester = None
        self.input_shaper = None
        self.toolhead = None
        self.print_stats = None
        self.ready = False

        self.gcode.register_command(
            "MOTION_WIZARD_NOISE", self.cmd_MOTION_WIZARD_NOISE,
            desc="Run the accelerometer noise check")
        self.gcode.register_command(
            "MOTION_WIZARD_CALIBRATE", self.cmd_MOTION_WIZARD_CALIBRATE,
            desc="Calibrate one input-shaper axis")
        self.gcode.register_command(
            "MOTION_WIZARD_RESET", self.cmd_MOTION_WIZARD_RESET,
            desc="Clear Motion Wizard progress")
        self.printer.register_event_handler(
            "klippy:ready", self._handle_ready)
        self.printer.register_event_handler(
            "klippy:shutdown", self._handle_shutdown)

    def _handle_ready(self):
        self.resonance_tester = self.printer.lookup_object(
            "resonance_tester", None)
        self.input_shaper = self.printer.lookup_object(
            "input_shaper", None)
        self.toolhead = self.printer.lookup_object("toolhead", None)
        self.print_stats = self.printer.lookup_object("print_stats", None)
        self.ready = all((
            self.resonance_tester, self.input_shaper, self.toolhead))
        if not self.ready:
            self.state = "unavailable"
            self.phase = "unavailable"
            self.message = (
                "Motion Wizard requires [resonance_tester] and "
                "[input_shaper]")

    def _handle_shutdown(self):
        if self.state == "running":
            self._fail("Klipper shutdown during motion calibration")

    def _assert_can_run(self, gcmd):
        if not self.ready:
            raise gcmd.error(self.message)
        if self.state == "running":
            raise gcmd.error("Motion Wizard is already running")
        if self.print_stats is not None:
            status = self.print_stats.get_status(self.reactor.monotonic())
            if status.get("state") in ("printing", "paused"):
                raise gcmd.error(
                    "Motion calibration cannot run during a print")

    def _assert_homed(self, gcmd):
        status = self.toolhead.get_status(self.reactor.monotonic())
        homed_axes = status.get("homed_axes", "")
        if not all(axis in homed_axes for axis in "xyz"):
            raise gcmd.error(
                "Home X, Y, and Z before running motion calibration")

    def _start(self, phase, message):
        self.state = "running"
        self.phase = phase
        self.message = message
        self.error = None
        self.started_at = self.reactor.monotonic()
        self.finished_at = None
        self.session_id += 1

    def _finish(self, message):
        self.state = "review" if self.pending_save else "ready"
        self.phase = "review" if self.pending_save else "ready"
        self.message = message
        self.finished_at = self.reactor.monotonic()

    def _fail(self, message):
        self.state = "error"
        self.phase = "error"
        self.message = str(message)
        self.error = str(message)
        self.finished_at = self.reactor.monotonic()

    def _shaper_results(self):
        results = {}
        if self.input_shaper is None:
            return results
        for shaper in self.input_shaper.get_shapers():
            axis = getattr(shaper, "axis", None)
            if axis not in ("x", "y"):
                continue
            status = shaper.params.get_status()
            results[axis] = {
                "type": status["shaper_type"],
                "frequency": float(status["shaper_freq"]),
                "damping_ratio": float(status["damping_ratio"]),
                "calibrated": axis in self.completed_axes,
            }
        return results

    def get_status(self, eventtime):
        elapsed = 0
        if self.started_at is not None:
            end = self.finished_at or eventtime
            elapsed = max(0, int(round(end - self.started_at)))
        homed_axes = ""
        if self.toolhead is not None:
            homed_axes = self.toolhead.get_status(eventtime).get(
                "homed_axes", "")
        completed = len(self.completed_axes)
        progress = completed * 40 + (10 if self.noise_complete else 0)
        if self.pending_save and completed == 2:
            progress = 90
        return {
            "version": PLUGIN_VERSION,
            "session_id": self.session_id,
            "ready": self.ready,
            "state": self.state,
            "phase": self.phase,
            "active": self.state == "running",
            "message": self.message,
            "error": self.error,
            "homed_axes": homed_axes,
            "noise_complete": self.noise_complete,
            "completed_axes": sorted(self.completed_axes),
            "pending_save": self.pending_save,
            "progress": progress,
            "elapsed_seconds": elapsed,
            "results": self._shaper_results(),
        }

    cmd_MOTION_WIZARD_NOISE_help = "Run the accelerometer noise check"
    def cmd_MOTION_WIZARD_NOISE(self, gcmd):
        self._assert_can_run(gcmd)
        self._start("noise", "Measuring accelerometer noise")
        try:
            self.gcode.run_script_from_command("MEASURE_AXES_NOISE")
        except self.printer.command_error as error:
            self._fail(error)
            raise
        self.noise_complete = True
        self._finish("Accelerometer noise check complete")
        gcmd.respond_info("Motion Wizard noise check complete")

    cmd_MOTION_WIZARD_CALIBRATE_help = "Calibrate one input-shaper axis"
    def cmd_MOTION_WIZARD_CALIBRATE(self, gcmd):
        self._assert_can_run(gcmd)
        self._assert_homed(gcmd)
        axis_value = gcmd.get("AXIS").strip().lower()
        if axis_value not in ("x", "y"):
            raise gcmd.error("AXIS must be X or Y")
        axis = axis_value
        self._start(
            "calibrating_%s" % axis,
            "Calibrating %s axis" % axis.upper())
        suffix = "klippertools_%s_%s" % (
            axis, time.strftime("%Y%m%d_%H%M%S"))
        try:
            self.gcode.run_script_from_command(
                "SHAPER_CALIBRATE AXIS=%s NAME=%s" % (
                    axis.upper(), suffix))
        except self.printer.command_error as error:
            self._fail(error)
            raise
        self.completed_axes.add(axis)
        self.pending_save = True
        self._finish(
            "%s-axis result ready for review" % axis.upper())
        gcmd.respond_info(
            "Motion Wizard %s-axis calibration complete; review the result "
            "before SAVE_CONFIG" % axis.upper())

    cmd_MOTION_WIZARD_RESET_help = "Clear Motion Wizard progress"
    def cmd_MOTION_WIZARD_RESET(self, gcmd):
        if self.state == "running":
            raise gcmd.error("Cannot reset Motion Wizard while it is running")
        self.state = "idle"
        self.phase = "ready"
        self.message = "Ready for motion calibration"
        self.error = None
        self.completed_axes = set()
        self.noise_complete = False
        self.pending_save = False
        self.started_at = None
        self.finished_at = None
        self.session_id += 1
        gcmd.respond_info("Motion Wizard reset")


def load_config(config):
    return MotionWizard(config)
