# Klippertools StartFlow
#
# Copyright (C) 2026 Klippertools contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import math


PLUGIN_VERSION = "0.2.0"
DEFAULT_STAGES = [
    ("bed_heat", "Heating bed", 120.0),
    ("homing", "Homing", 35.0),
    ("mesh", "Bed mesh", 180.0),
    ("nozzle_heat", "Heating nozzle", 90.0),
    ("purge", "Purging", 20.0),
]


def _display_name(name):
    return name.replace("_", " ").strip().title()


class StartFlowModel:
    def __init__(self, reactor, estimates=None, learning_rate=0.3):
        self.reactor = reactor
        self.learning_rate = learning_rate
        self.estimates = dict(
            (name, seconds) for name, label, seconds in DEFAULT_STAGES)
        if estimates:
            self.estimates.update(estimates)
        self.labels = dict(
            (name, label) for name, label, seconds in DEFAULT_STAGES)
        self.session_id = 0
        self.instrumentation_seen = False
        self.reset()

    def _now(self):
        return self.reactor.monotonic()

    def reset(self):
        self.state = "idle"
        self.message = "Waiting for PRINT_START"
        self.started_at = None
        self.finished_at = None
        self.current_index = None
        self.stages = []
        self.error = None
        self.session_id += 1

    def begin(self, stage_names=None):
        self.reset()
        self.instrumentation_seen = True
        self.state = "running"
        self.message = "Starting print preparation"
        self.started_at = self._now()
        names = stage_names or [item[0] for item in DEFAULT_STAGES]
        for name in names:
            self.stages.append({
                "name": name,
                "label": self.labels.get(name, _display_name(name)),
                "state": "pending",
                "started_at": None,
                "finished_at": None,
                "duration_seconds": None,
                "estimate_seconds": round(
                    float(self.estimates.get(name, 30.0)), 1),
            })

    def _complete_current(self, now):
        if self.current_index is None:
            return
        stage = self.stages[self.current_index]
        if stage["state"] != "active":
            return
        duration = max(0.0, now - stage["started_at"])
        stage["state"] = "done"
        stage["finished_at"] = now
        stage["duration_seconds"] = round(duration, 1)
        previous = self.estimates.get(stage["name"], duration)
        learned = (previous * (1.0 - self.learning_rate)
                   + duration * self.learning_rate)
        self.estimates[stage["name"]] = max(1.0, learned)
        stage["estimate_seconds"] = round(
            self.estimates[stage["name"]], 1)

    def stage(self, name, label=None):
        if self.state != "running":
            self.begin([name])
        now = self._now()
        self._complete_current(now)
        index = next((
            position for position, stage in enumerate(self.stages)
            if stage["name"] == name and stage["state"] == "pending"
        ), None)
        if index is None:
            self.stages.append({
                "name": name,
                "label": label or self.labels.get(
                    name, _display_name(name)),
                "state": "pending",
                "started_at": None,
                "finished_at": None,
                "duration_seconds": None,
                "estimate_seconds": round(
                    float(self.estimates.get(name, 30.0)), 1),
            })
            index = len(self.stages) - 1
        stage = self.stages[index]
        if label:
            stage["label"] = label
        stage["state"] = "active"
        stage["started_at"] = now
        self.current_index = index
        self.message = stage["label"]

    def complete(self):
        if self.state != "running":
            return
        now = self._now()
        self._complete_current(now)
        self.current_index = None
        self.state = "complete"
        self.message = "Print preparation complete"
        self.finished_at = now

    def fail(self, message):
        if self.state != "running":
            return
        now = self._now()
        if self.current_index is not None:
            stage = self.stages[self.current_index]
            stage["state"] = "error"
            stage["finished_at"] = now
        self.state = "error"
        self.error = str(message)
        self.message = str(message)
        self.finished_at = now

    def _eta_seconds(self, eventtime):
        if self.state == "complete":
            return 0
        if self.state != "running":
            return None
        remaining = 0.0
        for index, stage in enumerate(self.stages):
            if stage["state"] == "pending":
                remaining += self.estimates.get(stage["name"], 30.0)
            elif stage["state"] == "active":
                elapsed = max(0.0, eventtime - stage["started_at"])
                remaining += max(
                    0.0, self.estimates.get(stage["name"], 30.0)
                    - elapsed)
        return int(math.ceil(remaining))

    def get_status(self, eventtime):
        total = len(self.stages)
        completed = len([
            stage for stage in self.stages if stage["state"] == "done"
        ])
        progress = 100.0 * completed / total if total else 0.0
        elapsed = 0
        if self.started_at is not None:
            end = self.finished_at or eventtime
            elapsed = max(0, int(round(end - self.started_at)))
        current_stage = None
        if self.current_index is not None:
            current_stage = self.stages[self.current_index]["name"]
        return {
            "version": PLUGIN_VERSION,
            "session_id": self.session_id,
            "state": self.state,
            "active": self.state == "running",
            "message": self.message,
            "error": self.error,
            "instrumentation_seen": self.instrumentation_seen,
            "current_stage": current_stage,
            "completed_stages": completed,
            "total_stages": total,
            "progress": round(progress, 1),
            "eta_seconds": self._eta_seconds(eventtime),
            "elapsed_seconds": elapsed,
            "stages": [dict(stage) for stage in self.stages],
        }


class StartFlow:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        learning_rate = config.getfloat(
            "learning_rate", 0.3, minval=0.0, maxval=1.0)
        estimates = {}
        for name, label, default in DEFAULT_STAGES:
            estimates[name] = config.getfloat(
                "%s_estimate" % name, default, minval=1.0)
        self.model = StartFlowModel(
            self.reactor, estimates, learning_rate)

        self.gcode.register_command(
            "START_FLOW_BEGIN", self.cmd_START_FLOW_BEGIN,
            desc="Begin tracked PRINT_START preparation")
        self.gcode.register_command(
            "START_FLOW_STAGE", self.cmd_START_FLOW_STAGE,
            desc="Advance tracked PRINT_START preparation")
        self.gcode.register_command(
            "START_FLOW_COMPLETE", self.cmd_START_FLOW_COMPLETE,
            desc="Finish tracked PRINT_START preparation")
        self.gcode.register_command(
            "START_FLOW_ABORT", self.cmd_START_FLOW_ABORT,
            desc="Stop tracked PRINT_START preparation")
        self.gcode.register_command(
            "START_FLOW_RESET", self.cmd_START_FLOW_RESET,
            desc="Clear StartFlow status")
        self.printer.register_event_handler(
            "gcode:command_error", self._handle_command_error)
        self.printer.register_event_handler(
            "virtual_sdcard:reset_file", self._handle_reset_file)
        self.printer.register_event_handler(
            "klippy:shutdown", self._handle_shutdown)

    def _handle_command_error(self):
        self.model.fail("Print preparation stopped by a G-code error")

    def _handle_reset_file(self):
        self.model.fail("Print preparation canceled")

    def _handle_shutdown(self):
        self.model.fail("Klipper shutdown during print preparation")

    def get_status(self, eventtime):
        return self.model.get_status(eventtime)

    cmd_START_FLOW_BEGIN_help = "Begin tracked PRINT_START preparation"
    def cmd_START_FLOW_BEGIN(self, gcmd):
        raw_stages = gcmd.get("STAGES", None)
        stages = None
        if raw_stages:
            stages = [
                value.strip().lower() for value in raw_stages.split(",")
                if value.strip()
            ]
        self.model.begin(stages)
        gcmd.respond_info("StartFlow tracking started")

    cmd_START_FLOW_STAGE_help = "Advance tracked PRINT_START preparation"
    def cmd_START_FLOW_STAGE(self, gcmd):
        name = gcmd.get("NAME").strip().lower()
        label = gcmd.get("LABEL", None)
        if label:
            label = label.strip().strip('"').strip("'")
        self.model.stage(name, label)

    cmd_START_FLOW_COMPLETE_help = "Finish tracked PRINT_START preparation"
    def cmd_START_FLOW_COMPLETE(self, gcmd):
        self.model.complete()
        gcmd.respond_info("StartFlow tracking complete")

    cmd_START_FLOW_ABORT_help = "Stop tracked PRINT_START preparation"
    def cmd_START_FLOW_ABORT(self, gcmd):
        reason = gcmd.get("REASON", "Print preparation aborted")
        self.model.fail(reason.strip().strip('"').strip("'"))

    cmd_START_FLOW_RESET_help = "Clear StartFlow status"
    def cmd_START_FLOW_RESET(self, gcmd):
        if self.model.state == "running":
            raise gcmd.error("Cannot reset StartFlow while it is running")
        self.model.reset()
        gcmd.respond_info("StartFlow reset")


def load_config(config):
    return StartFlow(config)
