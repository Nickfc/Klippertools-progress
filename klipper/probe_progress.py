# Klipper bed-mesh probing progress support
#
# Copyright (C) 2026 Klipper Probe Progress contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
import math


PLUGIN_VERSION = "0.3.0"


def _rounded(value, digits=3):
    return round(float(value), digits)


class ProbeProgressModel:
    """State machine independent from Klipper's runtime.

    A logical matrix cell may contain more than one physical probe position
    when Klipper substitutes points around a configured faulty region.  Each
    physical position may itself contain multiple samples and retries.
    """

    def __init__(self, reactor, eta_seed_points=3,
                 coordinate_tolerance=0.75):
        self.reactor = reactor
        self.eta_seed_points = eta_seed_points
        self.coordinate_tolerance = coordinate_tolerance
        self.session_id = 0
        self.reset()

    def _now(self):
        return self.reactor.monotonic()

    def reset(self):
        self.state = "idle"
        self.phase = "idle"
        self.message = "Ready"
        self.error = None
        self.method = None
        self.profile = None
        self.started_at = None
        self.finished_at = None
        self.cells = []
        self.rows = 0
        self.columns = 0
        self.path_entries = []
        self.physical_index = 0
        self.physical_completed = 0
        self.touches_completed = 0
        self.cell_physical_totals = {}
        self.cell_physical_completed = {}
        self.current_cell = None
        self.current_samples = []
        self.current_retry = 0
        self.samples_per_position = 1
        self.samples_tolerance = 0.0
        self.samples_retries = 0
        self.completed_points = 0
        self.point_started_at = None
        self.point_durations = []
        self.eta_seconds_per_point = None
        self.eta_deadline = None
        self.last_z = None
        self.session_id += 1

    def start(self, base_points, path_entries, rows, columns,
              samples_per_position, samples_tolerance, samples_retries,
              method="automatic", profile="default"):
        self.reset()
        self.state = "probing"
        self.phase = "probing"
        self.message = "Probing bed mesh"
        self.method = method
        self.profile = profile
        self.started_at = self._now()
        self.rows = int(rows)
        self.columns = int(columns)
        self.samples_per_position = max(1, int(samples_per_position))
        self.samples_tolerance = max(0.0, float(samples_tolerance))
        self.samples_retries = max(0, int(samples_retries))

        x_values = sorted(set(_rounded(point[0], 6)
                              for point in base_points))
        y_values = sorted(set(_rounded(point[1], 6)
                              for point in base_points), reverse=True)

        for index, point in enumerate(base_points):
            x_value = _rounded(point[0], 6)
            y_value = _rounded(point[1], 6)
            column = min(range(len(x_values)),
                         key=lambda pos: abs(x_values[pos] - x_value))
            row = min(range(len(y_values)),
                      key=lambda pos: abs(y_values[pos] - y_value))
            self.cells.append({
                "index": index + 1,
                "row": row,
                "column": column,
                "x": _rounded(point[0]),
                "y": _rounded(point[1]),
                "state": "pending",
            })

        self.path_entries = [
            {
                "x": float(entry[0]),
                "y": float(entry[1]),
                "cell": entry[2],
            }
            for entry in path_entries
        ]
        for entry in self.path_entries:
            cell_index = entry["cell"]
            if cell_index is not None:
                self.cell_physical_totals[cell_index] = \
                    self.cell_physical_totals.get(cell_index, 0) + 1
                self.cell_physical_completed.setdefault(cell_index, 0)

        if not self.cells or not self.path_entries:
            self.fail("Klipper generated an empty probe path")
            return
        self._activate_entry()

    def _activate_entry(self):
        self.current_samples = []
        self.current_retry = 0
        if self.physical_index >= len(self.path_entries):
            self.current_cell = None
            self.phase = "finalizing"
            self.message = "Finalizing bed mesh"
            return

        entry = self.path_entries[self.physical_index]
        next_cell = entry["cell"]
        if next_cell is None:
            self.current_cell = None
            self.phase = "zero_reference"
            self.message = "Probing zero reference"
            return

        if next_cell != self.current_cell:
            self.current_cell = next_cell
            self.point_started_at = self._now()
        self.cells[next_cell]["state"] = "active"
        self.phase = "probing"
        self.message = "Probing bed mesh"

    def _coordinate_matches(self, entry, x_value, y_value):
        return (abs(entry["x"] - x_value) <= self.coordinate_tolerance
                and abs(entry["y"] - y_value)
                <= self.coordinate_tolerance)

    def accept_result(self, x_value, y_value, z_value):
        if self.state != "probing" or \
                self.physical_index >= len(self.path_entries):
            return False

        entry = self.path_entries[self.physical_index]
        x_value = float(x_value)
        y_value = float(y_value)
        if not self._coordinate_matches(entry, x_value, y_value):
            logging.warning(
                "probe_progress: ignoring unexpected result at %.3f,%.3f; "
                "expected %.3f,%.3f",
                x_value, y_value, entry["x"], entry["y"])
            return False

        z_value = float(z_value)
        self.last_z = z_value
        self.touches_completed += 1
        self.current_samples.append(z_value)
        sample_range = max(self.current_samples) - min(self.current_samples)
        if sample_range > self.samples_tolerance:
            if self.current_retry >= self.samples_retries:
                self.message = "Probe samples exceeded tolerance"
                return True
            self.current_retry += 1
            self.current_samples = []
            self.message = "Retrying probe samples"
            return True

        if len(self.current_samples) < self.samples_per_position:
            return True

        self._complete_physical_entry()
        return True

    def _complete_physical_entry(self):
        entry = self.path_entries[self.physical_index]
        cell_index = entry["cell"]
        self.physical_completed += 1

        if cell_index is not None:
            complete_count = self.cell_physical_completed[cell_index] + 1
            self.cell_physical_completed[cell_index] = complete_count
            if complete_count >= self.cell_physical_totals[cell_index]:
                self._complete_logical_cell(cell_index)

        self.physical_index += 1
        self._activate_entry()

    def _complete_logical_cell(self, cell_index):
        now = self._now()
        self.cells[cell_index]["state"] = "done"
        self.completed_points += 1
        if self.point_started_at is not None:
            duration = max(0.0, now - self.point_started_at)
            if len(self.point_durations) < self.eta_seed_points:
                self.point_durations.append(duration)

        seed_count = min(self.eta_seed_points, len(self.cells))
        if self.eta_seconds_per_point is None and \
                len(self.point_durations) >= seed_count:
            self.eta_seconds_per_point = (
                sum(self.point_durations[:seed_count]) / seed_count)
            remaining = max(0, len(self.cells) - self.completed_points)
            self.eta_deadline = now + self.eta_seconds_per_point * remaining

    def complete(self):
        if self.state not in ("probing", "complete"):
            return
        now = self._now()
        for cell in self.cells:
            cell["state"] = "done"
        # Returning from Klipper's synchronous automatic probe routine is the
        # authoritative completion signal, even if an optional result event
        # was missed by this observer.
        self.completed_points = len(self.cells)
        self.state = "complete"
        self.phase = "complete"
        self.message = "Bed mesh complete"
        self.current_cell = None
        self.finished_at = now
        self.eta_deadline = now

    def fail(self, message):
        if self.state == "idle" and not self.cells:
            self.state = "error"
        elif self.state == "complete":
            return
        else:
            self.state = "error"
        self.phase = "error"
        self.error = str(message)
        self.message = str(message)
        self.finished_at = self._now()

    def get_status(self, eventtime):
        total_points = len(self.cells)
        progress = 0.0
        if total_points:
            progress = 100.0 * self.completed_points / total_points

        eta_seconds = None
        if self.state == "complete":
            eta_seconds = 0
        elif self.eta_deadline is not None:
            eta_seconds = max(0, int(math.ceil(
                self.eta_deadline - eventtime)))

        elapsed_seconds = 0
        if self.started_at is not None:
            end_time = (self.finished_at if self.finished_at is not None
                        else eventtime)
            elapsed_seconds = max(0, int(round(end_time - self.started_at)))

        current_point = 0
        current_sample = 0
        if self.current_cell is not None:
            current_point = self.current_cell + 1
            current_sample = min(
                self.samples_per_position,
                len(self.current_samples) + 1)

        return {
            "version": PLUGIN_VERSION,
            "session_id": self.session_id,
            "state": self.state,
            "phase": self.phase,
            "active": self.state == "probing",
            "message": self.message,
            "error": self.error,
            "method": self.method,
            "profile": self.profile,
            "current_point": current_point,
            "completed_points": self.completed_points,
            "total_points": total_points,
            "current_sample": current_sample,
            "samples_per_position": self.samples_per_position,
            "current_retry": self.current_retry,
            "samples_retries": self.samples_retries,
            "physical_completed": self.physical_completed,
            "physical_total": len(self.path_entries),
            "touches_completed": self.touches_completed,
            "planned_touches": (
                len(self.path_entries) * self.samples_per_position
            ),
            "progress": round(progress, 1),
            "eta_state": ("available" if eta_seconds is not None
                          else "calculating"),
            "eta_seed_points": min(self.eta_seed_points, total_points),
            "eta_sampled_points": len(self.point_durations),
            "eta_seconds": eta_seconds,
            "elapsed_seconds": elapsed_seconds,
            "last_z": (None if self.last_z is None
                       else round(self.last_z, 6)),
            "matrix": {
                "rows": self.rows,
                "columns": self.columns,
                "cells": [dict(cell) for cell in self.cells],
            },
        }


class ProbeProgress:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        eta_seed_points = config.getint(
            "eta_seed_points", 3, minval=1)
        coordinate_tolerance = config.getfloat(
            "coordinate_tolerance", 0.75, above=0.0)
        self.model = ProbeProgressModel(
            self.reactor, eta_seed_points, coordinate_tolerance)
        self.gcode = self.printer.lookup_object("gcode")
        self.bed_mesh = None
        self.probe = None
        self.original_start_probe = None
        self.ready = False

        self.gcode.register_command(
            "PROBE_PROGRESS_RESET", self.cmd_PROBE_PROGRESS_RESET,
            desc="Clear the saved probe progress matrix")
        self.printer.register_event_handler(
            "klippy:ready", self._handle_ready)
        self.printer.register_event_handler(
            "klippy:shutdown", self._handle_shutdown)
        self.printer.register_event_handler(
            "klippy:disconnect", self._handle_disconnect)

    def _handle_ready(self):
        self.bed_mesh = self.printer.lookup_object("bed_mesh", None)
        self.probe = self.printer.lookup_object("probe", None)
        if self.bed_mesh is None or self.probe is None:
            self.model.fail(
                "Probe Progress requires [probe] and [bed_mesh]")
            logging.warning("probe_progress: [probe] or [bed_mesh] missing")
            return

        probe_manager = self.bed_mesh.bmc.probe_mgr
        self.original_start_probe = probe_manager.start_probe
        probe_manager.start_probe = self._start_bed_mesh_probe
        # Register after all config objects so compensation handlers update a
        # result before Probe Progress evaluates sample tolerance.
        self.printer.register_event_handler(
            "probe:update_results", self._handle_probe_results)
        self.ready = True

    def _handle_shutdown(self):
        if self.model.state == "probing":
            self.model.fail("Klipper shutdown during probing")

    def _handle_disconnect(self):
        if self.model.state == "probing":
            self.model.fail("Klipper disconnected during probing")

    def _build_path_entries(self, calibration):
        base_points = calibration["points"]
        probe_path = calibration["probe_path"]
        substitutes = self.bed_mesh.bmc.probe_mgr.get_substitutes()
        path_cells = []
        for index in range(len(base_points)):
            substitute_points = substitutes.get(index)
            if substitute_points:
                path_cells.extend([index] * len(substitute_points))
            else:
                path_cells.append(index)
        if len(path_cells) < len(probe_path):
            path_cells.extend([None] * (len(probe_path) - len(path_cells)))
        return [
            (point[0], point[1], path_cells[index])
            for index, point in enumerate(probe_path)
        ]

    def _start_bed_mesh_probe(self, gcmd):
        calibration = self.bed_mesh.bmc.dump_calibration()
        config = calibration["config"]
        probe_params = self.probe.get_probe_params(gcmd)
        path_entries = self._build_path_entries(calibration)
        method = gcmd.get("METHOD", "automatic").lower()
        profile = gcmd.get("PROFILE", "default")

        self.model.start(
            calibration["points"], path_entries,
            config["y_count"], config["x_count"],
            probe_params["samples"],
            probe_params["samples_tolerance"],
            probe_params["samples_tolerance_retries"],
            method, profile)
        try:
            result = self.original_start_probe(gcmd)
        except self.printer.command_error as error:
            self.model.fail(str(error))
            raise
        except Exception as error:
            self.model.fail(str(error))
            raise
        else:
            if method != "manual":
                self.model.complete()
            return result

    def _handle_probe_results(self, results):
        if not results or self.model.state != "probing":
            return
        result = results[0]
        self.model.accept_result(
            result.bed_x, result.bed_y, result.bed_z)

    def get_status(self, eventtime):
        status = self.model.get_status(eventtime)
        status["ready"] = self.ready
        return status

    cmd_PROBE_PROGRESS_RESET_help = "Clear the saved probe progress matrix"
    def cmd_PROBE_PROGRESS_RESET(self, gcmd):
        if self.model.state == "probing":
            raise gcmd.error("Cannot reset Probe Progress while probing")
        self.model.reset()
        gcmd.respond_info("Probe Progress reset")


def load_config(config):
    return ProbeProgress(config)
