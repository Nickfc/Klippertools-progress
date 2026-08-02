# Klippertools Service Manager metric collector
#
# Copyright (C) 2026 Klippertools contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import math


PLUGIN_VERSION = "0.3.0"


class ServiceMetrics:
    """Collect volatile counters that only Klipper can measure accurately.

    Moonraker persists and reconciles these boot-local counters.  XY and Z are
    commanded toolhead travel, including Klipper transforms; they are not
    closed-loop measurements of physical carriage position.
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.boot_id = "%x-%x" % (id(self), int(self.reactor.monotonic() * 1000000.))
        self.xy_distance_mm = 0.
        self.z_distance_mm = 0.
        self.probe_cycles = 0
        self._wrapped = False
        self._original_move = None
        self._last_position = None
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.printer.register_event_handler("probe:update_results", self._handle_probe_result)
        self.printer.register_event_handler("toolhead:set_position", self._handle_set_position)

    def _handle_ready(self):
        if self._wrapped:
            return
        toolhead = self.printer.lookup_object("toolhead")
        self._original_move = toolhead.move
        self._last_position = list(toolhead.get_position())

        def tracked_move(newpos, speed):
            previous = self._last_position
            result = self._original_move(newpos, speed)
            if previous is not None and len(newpos) >= 3:
                dx = float(newpos[0]) - float(previous[0])
                dy = float(newpos[1]) - float(previous[1])
                dz = float(newpos[2]) - float(previous[2])
                self.xy_distance_mm += math.hypot(dx, dy)
                self.z_distance_mm += abs(dz)
            self._last_position = list(newpos)
            return result

        toolhead.move = tracked_move
        self._wrapped = True

    def _handle_probe_result(self, _results):
        self.probe_cycles += 1

    def _handle_set_position(self):
        if not self._wrapped:
            return
        toolhead = self.printer.lookup_object("toolhead")
        self._last_position = list(toolhead.get_position())

    def get_status(self, _eventtime):
        return {
            "version": PLUGIN_VERSION,
            "boot_id": self.boot_id,
            "ready": self._wrapped,
            "xy_distance_mm": round(self.xy_distance_mm, 3),
            "z_distance_mm": round(self.z_distance_mm, 3),
            "probe_cycles": self.probe_cycles,
            "distance_kind": "commanded",
        }


def load_config(config):
    return ServiceMetrics(config)
