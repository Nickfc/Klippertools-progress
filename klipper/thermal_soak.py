# Klippertools Thermal Soak Assistant
#
# Copyright (C) 2026 Klippertools contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from collections import deque
import math


PLUGIN_VERSION = "0.8.0"


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


class ThermalSoakModel:
    """Evaluate temperature stability without assuming a specific printer.

    A soak is complete only after the sensor remains near its requested target,
    the regression slope is low, and the observed range stays inside the
    configured band for the complete stability window.
    """

    TERMINAL_STATES = ("stable", "timed_out", "canceled", "error")

    def __init__(self):
        self.learned_durations = {}
        self.session_id = 0
        self.reset()

    def reset(self):
        self.session_id += 1
        self.state = "idle"
        self.message = "Waiting for a thermal soak"
        self.sensor = None
        self.target = 0.0
        self.window_seconds = 300.0
        self.max_wait_seconds = 1800.0
        self.temperature_tolerance = 0.30
        self.slope_limit = 0.05
        self.range_limit = 0.50
        self.started_at = None
        self.finished_at = None
        self.temperature = None
        self.sensor_target = 0.0
        self.start_temperature = None
        self.slope_c_per_min = None
        self.range_c = None
        self.stable_seconds = 0.0
        self.eta_seconds = None
        self.error = None
        self.samples = deque()
        self._condition_since = None

    def begin(self, eventtime, sensor, target, window_seconds=300.0,
              max_wait_seconds=1800.0, temperature_tolerance=0.30,
              slope_limit=0.05, range_limit=0.50):
        self.reset()
        self.state = "heating"
        self.message = "Heating toward target"
        self.sensor = str(sensor)
        self.target = float(target)
        self.window_seconds = float(window_seconds)
        self.max_wait_seconds = float(max_wait_seconds)
        self.temperature_tolerance = float(temperature_tolerance)
        self.slope_limit = float(slope_limit)
        self.range_limit = float(range_limit)
        self.started_at = float(eventtime)

    def _window_samples(self, eventtime):
        lower = eventtime - self.window_seconds
        return [sample for sample in self.samples if sample[0] >= lower]

    @staticmethod
    def _regression_slope(samples):
        if len(samples) < 2:
            return None
        origin = samples[0][0]
        points = [(timestamp - origin, temperature)
                  for timestamp, temperature in samples]
        mean_x = sum(point[0] for point in points) / len(points)
        mean_y = sum(point[1] for point in points) / len(points)
        denominator = sum((point[0] - mean_x) ** 2 for point in points)
        if denominator <= 0.0:
            return None
        numerator = sum((point[0] - mean_x) * (point[1] - mean_y)
                        for point in points)
        return numerator / denominator * 60.0

    def _learned_key(self):
        return "%s:%.1f" % (self.sensor, self.target)

    def _record_completion(self, elapsed):
        key = self._learned_key()
        previous = self.learned_durations.get(key)
        if previous is None:
            self.learned_durations[key] = elapsed
        else:
            self.learned_durations[key] = previous * 0.7 + elapsed * 0.3

    def _estimate_eta(self, eventtime, temperature, slope):
        elapsed = max(0.0, eventtime - self.started_at)
        learned = self.learned_durations.get(self._learned_key())
        live = None
        if temperature < self.target - self.temperature_tolerance:
            if slope is not None and slope > 0.01:
                live = ((self.target - temperature) / slope * 60.0
                        + self.window_seconds)
        else:
            live = max(0.0, self.window_seconds - self.stable_seconds)
        estimates = [value for value in (live,
                     None if learned is None else learned - elapsed)
                     if value is not None]
        if not estimates:
            return None
        return int(math.ceil(max(0.0, sum(estimates) / len(estimates))))

    def add_sample(self, eventtime, temperature, sensor_target=0.0):
        if self.state == "idle" or self.state in self.TERMINAL_STATES:
            return
        now = float(eventtime)
        value = float(temperature)
        if not math.isfinite(value):
            self.fail("Temperature sensor returned a non-finite value", now)
            return
        self.temperature = value
        self.sensor_target = float(sensor_target or 0.0)
        if self.start_temperature is None:
            self.start_temperature = value
        self.samples.append((now, value))
        retention = max(self.window_seconds, 180.0) + 30.0
        while self.samples and self.samples[0][0] < now - retention:
            self.samples.popleft()

        window = self._window_samples(now)
        self.slope_c_per_min = self._regression_slope(window)
        self.range_c = (max(sample[1] for sample in window)
                        - min(sample[1] for sample in window)) if window else None
        at_target = abs(value - self.target) <= self.temperature_tolerance
        slope_ok = (self.slope_c_per_min is not None
                    and abs(self.slope_c_per_min) <= self.slope_limit)
        instantaneous_ok = at_target and slope_ok
        if instantaneous_ok:
            if self._condition_since is None:
                self._condition_since = now
            self.stable_seconds = max(0.0, now - self._condition_since)
        else:
            self._condition_since = None
            self.stable_seconds = 0.0

        span = window[-1][0] - window[0][0] if len(window) >= 2 else 0.0
        range_ok = (self.range_c is not None
                    and self.range_c <= self.range_limit)
        if (at_target and slope_ok and range_ok
                and span >= self.window_seconds * 0.98):
            self.state = "stable"
            self.message = "Temperature is stable"
            self.finished_at = now
            self.stable_seconds = self.window_seconds
            self.eta_seconds = 0
            self._record_completion(max(0.0, now - self.started_at))
            return

        if now - self.started_at >= self.max_wait_seconds:
            self.state = "timed_out"
            self.message = "Thermal soak timed out"
            self.finished_at = now
            self.eta_seconds = None
            return

        if value < self.target - self.temperature_tolerance:
            self.state = "heating"
            self.message = "Heating toward target"
        else:
            self.state = "stabilizing"
            self.message = "Holding temperature until drift settles"
        self.eta_seconds = self._estimate_eta(
            now, value, self.slope_c_per_min)

    def cancel(self, eventtime):
        if self.state == "idle" or self.state in self.TERMINAL_STATES:
            return
        self.state = "canceled"
        self.message = "Thermal soak canceled"
        self.finished_at = float(eventtime)
        self.eta_seconds = None

    def fail(self, message, eventtime):
        self.state = "error"
        self.message = str(message)
        self.error = str(message)
        self.finished_at = float(eventtime)
        self.eta_seconds = None

    def get_status(self, eventtime):
        elapsed = 0.0
        if self.started_at is not None:
            end = self.finished_at if self.finished_at is not None else eventtime
            elapsed = max(0.0, float(end) - self.started_at)
        if self.state == "stable":
            progress = 100.0
        elif self.state == "idle":
            progress = 0.0
        elif self.state in ("timed_out", "canceled", "error"):
            progress = _clamp(100.0 * elapsed / self.max_wait_seconds,
                              0.0, 99.0)
        elif (self.temperature is not None and self.start_temperature is not None
              and self.target > self.start_temperature
              and self.temperature < self.target - self.temperature_tolerance):
            heat_progress = ((self.temperature - self.start_temperature)
                             / (self.target - self.start_temperature))
            progress = _clamp(heat_progress * 70.0, 0.0, 70.0)
        else:
            progress = 70.0 + _clamp(
                self.stable_seconds / self.window_seconds, 0.0, 1.0) * 30.0
        learned = self.learned_durations.get(self._learned_key()) \
            if self.sensor else None
        return {
            "version": PLUGIN_VERSION,
            "session_id": self.session_id,
            "state": self.state,
            "active": self.state in ("heating", "stabilizing"),
            "message": self.message,
            "error": self.error,
            "sensor": self.sensor,
            "target": round(self.target, 2),
            "temperature": (None if self.temperature is None
                            else round(self.temperature, 2)),
            "sensor_target": round(self.sensor_target, 2),
            "temperature_tolerance": self.temperature_tolerance,
            "slope_limit_c_per_min": self.slope_limit,
            "slope_c_per_min": (None if self.slope_c_per_min is None
                                else round(self.slope_c_per_min, 4)),
            "range_limit_c": self.range_limit,
            "range_c": (None if self.range_c is None
                        else round(self.range_c, 3)),
            "window_seconds": int(round(self.window_seconds)),
            "max_wait_seconds": int(round(self.max_wait_seconds)),
            "stable_seconds": int(round(self.stable_seconds)),
            "elapsed_seconds": int(round(elapsed)),
            "eta_seconds": self.eta_seconds,
            "learned_duration_seconds": (None if learned is None
                                         else int(round(learned))),
            "progress": round(progress, 1),
        }


class ThermalSoak:
    cmd_THERMAL_SOAK_START_help = "Start non-blocking thermal stability monitoring"
    cmd_THERMAL_SOAK_WAIT_help = "Wait until a temperature sensor is thermally stable"
    cmd_THERMAL_SOAK_CANCEL_help = "Cancel the active thermal soak"
    cmd_THERMAL_SOAK_RESET_help = "Clear Thermal Soak status"

    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.heaters = None
        self.sensor_object = None
        self.available_sensors = []
        self.default_sensor = config.get("default_sensor", "heater_bed")
        self.default_window = config.getfloat(
            "stability_window", 300.0, minval=30.0, maxval=3600.0)
        self.default_max_wait = config.getfloat(
            "max_wait", 1800.0, minval=60.0, maxval=14400.0)
        self.default_tolerance = config.getfloat(
            "temperature_tolerance", 0.30, above=0.0, maxval=10.0)
        self.default_slope = config.getfloat(
            "slope_limit", 0.05, above=0.0, maxval=10.0)
        self.default_range = config.getfloat(
            "range_limit", 0.50, above=0.0, maxval=20.0)
        self.sample_interval = config.getfloat(
            "sample_interval", 2.0, minval=0.5, maxval=30.0)
        self.model = ThermalSoakModel()
        self.timer = self.reactor.register_timer(
            self._sample_timer, self.reactor.NEVER)
        self.printer.register_event_handler("klippy:ready", self._handle_ready)
        self.printer.register_event_handler("klippy:shutdown", self._handle_shutdown)
        self.gcode.register_command(
            "THERMAL_SOAK_START", self.cmd_THERMAL_SOAK_START,
            desc=self.cmd_THERMAL_SOAK_START_help)
        self.gcode.register_command(
            "THERMAL_SOAK_WAIT", self.cmd_THERMAL_SOAK_WAIT,
            desc=self.cmd_THERMAL_SOAK_WAIT_help)
        self.gcode.register_command(
            "THERMAL_SOAK_CANCEL", self.cmd_THERMAL_SOAK_CANCEL,
            desc=self.cmd_THERMAL_SOAK_CANCEL_help)
        self.gcode.register_command(
            "THERMAL_SOAK_RESET", self.cmd_THERMAL_SOAK_RESET,
            desc=self.cmd_THERMAL_SOAK_RESET_help)

    def _handle_ready(self):
        self.heaters = self.printer.lookup_object("heaters")
        status = self.heaters.get_status(self.reactor.monotonic())
        names = list(status.get("available_sensors", []))
        for heater in status.get("available_heaters", []):
            short_name = heater.split()[-1]
            if short_name not in names:
                names.append(short_name)
        self.available_sensors = sorted(set(names))

    def _handle_shutdown(self):
        if self.model.get_status(self.reactor.monotonic())["active"]:
            self.model.fail("Klipper shutdown during thermal soak",
                            self.reactor.monotonic())

    def _resolve_sensor(self, sensor_name):
        if self.heaters is None:
            raise self.printer.command_error(
                "Thermal Soak is waiting for Klipper to become ready")
        if sensor_name in self.heaters.heaters:
            return self.heaters.lookup_heater(sensor_name)
        sensor = self.printer.lookup_object(sensor_name, None)
        if sensor is None or not hasattr(sensor, "get_temp"):
            raise self.printer.command_error(
                "Unknown temperature sensor '%s'" % (sensor_name,))
        return sensor

    def _parameters(self, gcmd):
        sensor_name = (gcmd.get("SENSOR", self.default_sensor).strip()
                       .strip('"').strip("'"))
        sensor = self._resolve_sensor(sensor_name)
        eventtime = self.reactor.monotonic()
        _current, configured_target = sensor.get_temp(eventtime)
        target = gcmd.get_float("TARGET", configured_target, above=0.0)
        if target <= 0.0:
            raise gcmd.error(
                "THERMAL_SOAK requires TARGET or an active heater target")
        return {
            "eventtime": eventtime,
            "sensor_name": sensor_name,
            "sensor": sensor,
            "target": target,
            "window_seconds": gcmd.get_float(
                "WINDOW", self.default_window, minval=30.0, maxval=3600.0),
            "max_wait_seconds": gcmd.get_float(
                "MAX_WAIT", self.default_max_wait,
                minval=60.0, maxval=14400.0),
            "temperature_tolerance": gcmd.get_float(
                "TOLERANCE", self.default_tolerance,
                above=0.0, maxval=10.0),
            "slope_limit": gcmd.get_float(
                "SLOPE", self.default_slope, above=0.0, maxval=10.0),
            "range_limit": gcmd.get_float(
                "RANGE", self.default_range, above=0.0, maxval=20.0),
        }

    def _start(self, gcmd):
        params = self._parameters(gcmd)
        self.sensor_object = params.pop("sensor")
        sensor_name = params.pop("sensor_name")
        eventtime = params.pop("eventtime")
        self.model.begin(eventtime, sensor_name, **params)
        self.reactor.update_timer(self.timer, eventtime)
        self._sample(eventtime)
        return eventtime

    def _sample(self, eventtime):
        if self.sensor_object is None or not self.model.get_status(eventtime)["active"]:
            return
        try:
            temperature, target = self.sensor_object.get_temp(eventtime)
            self.model.add_sample(eventtime, temperature, target)
        except Exception as exc:
            self.model.fail("Unable to read thermal sensor: %s" % (exc,),
                            eventtime)

    def _sample_timer(self, eventtime):
        self._sample(eventtime)
        if self.model.get_status(eventtime)["active"]:
            return eventtime + self.sample_interval
        return self.reactor.NEVER

    def get_status(self, eventtime):
        status = self.model.get_status(eventtime)
        status.update({
            "ready": self.heaters is not None,
            "available_sensors": list(self.available_sensors),
            "defaults": {
                "sensor": self.default_sensor,
                "window_seconds": int(round(self.default_window)),
                "max_wait_seconds": int(round(self.default_max_wait)),
                "temperature_tolerance": self.default_tolerance,
                "slope_limit_c_per_min": self.default_slope,
                "range_limit_c": self.default_range,
            },
        })
        return status

    def cmd_THERMAL_SOAK_START(self, gcmd):
        self._start(gcmd)
        gcmd.respond_info(
            "Thermal Soak started on %s at %.1fC" %
            (self.model.sensor, self.model.target))

    def cmd_THERMAL_SOAK_WAIT(self, gcmd):
        eventtime = self._start(gcmd)
        next_report = eventtime
        while not self.printer.is_shutdown():
            status = self.model.get_status(eventtime)
            if status["state"] == "stable":
                gcmd.respond_info(
                    "Thermal Soak stable after %ds" %
                    (status["elapsed_seconds"],))
                return
            if status["state"] in ("timed_out", "canceled", "error"):
                raise gcmd.error(status["message"])
            if eventtime >= next_report:
                temp = status["temperature"]
                temp_text = "--" if temp is None else "%.2fC" % (temp,)
                gcmd.respond_info(
                    "Thermal Soak %s: %s, slope %s C/min, ETA %s" % (
                        status["state"], temp_text,
                        "--" if status["slope_c_per_min"] is None
                        else "%.3f" % status["slope_c_per_min"],
                        "calculating" if status["eta_seconds"] is None
                        else "%ds" % status["eta_seconds"]))
                next_report = eventtime + 15.0
            eventtime = self.reactor.pause(eventtime + 1.0)
        raise gcmd.error("Klipper shutdown during thermal soak")

    def cmd_THERMAL_SOAK_CANCEL(self, gcmd):
        self.model.cancel(self.reactor.monotonic())
        self.reactor.update_timer(self.timer, self.reactor.NEVER)
        gcmd.respond_info("Thermal Soak canceled")

    def cmd_THERMAL_SOAK_RESET(self, gcmd):
        if self.model.get_status(self.reactor.monotonic())["active"]:
            raise gcmd.error("Cancel the active thermal soak before resetting")
        self.model.reset()
        self.sensor_object = None
        gcmd.respond_info("Thermal Soak status reset")


def load_config(config):
    return ThermalSoak(config)
