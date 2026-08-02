# Klippertools Suite update controller and Service Manager
#
# Copyright (C) 2026 Klippertools contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Dict, List, Mapping, Optional

from ..common import RequestType


SERVICE_SCHEMA = 2
TOOL_SCHEMA = 1
TIMELINE_SCHEMA = 1
TOOL_HISTORY_LIMIT = 1000
MAX_TOOL_PROFILES = 500
MAX_SERVICE_TASKS = 500
TIMELINE_EVENT_LIMIT = 2000
TIMELINE_RETENTION_DAYS = 365
TOOL_USAGE_KEYS = ("print_time_s", "filament_mm", "prints", "hotend_heater_s")
PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
SMART_DEFAULTS = {
    "enabled": False,
    "lookback_days": 90,
    "min_events": 3,
    "max_advance_fraction": 0.25,
    "reset_at": 0.0,
}
SMART_SIGNAL_MAP = {
    "xy-rails": ["motion_calibration_error", "print_failed"],
    "z-mechanism": ["calibration_error", "print_failed"],
    "belts-pulleys": ["motion_calibration_error", "print_failed"],
    "extruder-gears": ["print_failed", "nozzle_guard_error"],
    "nozzle-hotend": ["nozzle_mismatch", "nozzle_guard_error", "thermal_soak_error"],
    "heater-wiring": ["thermal_soak_error", "configuration_warning"],
    "probe": ["calibration_error", "configuration_warning"],
    "build-plate": ["print_cancelled", "print_failed"],
    "fans": ["thermal_soak_timed_out", "thermal_soak_error"],
    "electrical-connectors": ["configuration_warning", "thermal_soak_error"],
}
MECHANISM_PRESETS = {
    "corexy": {
        "label": "CoreXY motion system",
        "focus": ["xy-rails", "belts-pulleys", "z-mechanism"],
        "note": "Prioritize belt-path symmetry, idlers, XY rails, and synchronized Z motion."
    },
    "cartesian": {
        "label": "Cartesian motion system",
        "focus": ["xy-rails", "belts-pulleys", "z-mechanism"],
        "note": "Prioritize axis-specific wheels or rails, belt alignment, and Z guidance."
    },
    "delta": {
        "label": "Delta motion system",
        "focus": ["xy-rails", "belts-pulleys", "probe"],
        "note": "Prioritize tower motion, carriage play, arm joints, and calibration repeatability."
    },
}
POLL_SECONDS = 5.0
SAVE_SECONDS = 30.0
ACTIVE_STATES = {"printing", "paused"}
COUNTER_KEYS = (
    "print_time_s",
    "filament_mm",
    "prints",
    "xy_distance_mm",
    "z_distance_mm",
    "hotend_heater_s",
    "bed_heater_s",
    "probe_cycles",
)
METRICS = {
    "print_time_s": {"label": "Print time", "unit": "seconds"},
    "filament_mm": {"label": "Filament", "unit": "millimetres"},
    "prints": {"label": "Prints", "unit": "prints"},
    "calendar_s": {"label": "Calendar age", "unit": "seconds"},
    "xy_distance_mm": {"label": "XY commanded travel", "unit": "millimetres"},
    "z_distance_mm": {"label": "Z commanded travel", "unit": "millimetres"},
    "hotend_heater_s": {"label": "Hotend heater-on time", "unit": "seconds"},
    "bed_heater_s": {"label": "Bed heater-on time", "unit": "seconds"},
    "probe_cycles": {"label": "Probe touches", "unit": "touches"},
}


def _threshold(metric: str, limit: float) -> Dict[str, Any]:
    return {"metric": metric, "limit": float(limit), "enabled": True}


# Conservative editable starting points for common FDM printer mechanisms.
# They are inspection reminders, not manufacturer service guarantees.
RECOMMENDED_TASKS = (
    {
        "id": "xy-rails",
        "name": "Clean and lubricate XY rails",
        "area": "Motion",
        "instructions": "Wipe the rails, inspect for contamination or rough spots, then apply the lubricant specified for the installed rail blocks.",
        "thresholds": [_threshold("print_time_s", 200 * 3600), _threshold("xy_distance_mm", 500_000_000), _threshold("calendar_s", 90 * 86400)],
    },
    {
        "id": "z-mechanism",
        "name": "Inspect and lubricate Z mechanism",
        "area": "Motion",
        "instructions": "Clean the Z guides and screws, check couplers and synchronized movement, then lubricate with a compatible product.",
        "thresholds": [_threshold("print_time_s", 250 * 3600), _threshold("z_distance_mm", 15_000_000), _threshold("calendar_s", 120 * 86400)],
    },
    {
        "id": "belts-pulleys",
        "name": "Inspect belts, idlers, and pulleys",
        "area": "Motion",
        "instructions": "Check belt edges and teeth, pulley set screws, bearing play, alignment, and even tension. Replace damaged parts; do not lubricate belts.",
        "thresholds": [_threshold("print_time_s", 500 * 3600), _threshold("xy_distance_mm", 1_500_000_000), _threshold("calendar_s", 180 * 86400)],
    },
    {
        "id": "extruder-gears",
        "name": "Clean and inspect extruder gears",
        "area": "Filament path",
        "instructions": "Remove filament debris, inspect drive teeth and idler wear, check bearing movement, and restore the correct idler tension.",
        "thresholds": [_threshold("filament_mm", 15_000_000), _threshold("print_time_s", 400 * 3600), _threshold("calendar_s", 180 * 86400)],
    },
    {
        "id": "nozzle-hotend",
        "name": "Inspect nozzle and hotend",
        "area": "Hotend",
        "instructions": "Inspect the nozzle orifice, heatbreak, heater block, sock, and signs of leakage. Follow the hot-tightening procedure for the installed hotend.",
        "thresholds": [_threshold("filament_mm", 3_000_000), _threshold("print_time_s", 250 * 3600)],
    },
    {
        "id": "heater-wiring",
        "name": "Inspect heater and thermistor wiring",
        "area": "Electrical",
        "instructions": "With power disconnected and components cool, inspect strain relief, insulation, connectors, crimps, and sensor retention. Repair damage before printing.",
        "thresholds": [_threshold("hotend_heater_s", 1000 * 3600), _threshold("bed_heater_s", 1000 * 3600), _threshold("calendar_s", 365 * 86400)],
    },
    {
        "id": "probe",
        "name": "Inspect and verify probe",
        "area": "Calibration",
        "instructions": "Clean the probe area, inspect mounting and cable routing, check repeatability, and verify Z offset using the normal safe calibration procedure.",
        "thresholds": [_threshold("probe_cycles", 10_000), _threshold("print_time_s", 500 * 3600), _threshold("calendar_s", 180 * 86400)],
    },
    {
        "id": "build-plate",
        "name": "Deep-clean and inspect build plate",
        "area": "Build surface",
        "instructions": "Clean using the surface manufacturer's method and inspect for coating damage, trapped debris, flatness issues, and poor magnetic seating.",
        "thresholds": [_threshold("prints", 50), _threshold("calendar_s", 30 * 86400)],
    },
    {
        "id": "fans",
        "name": "Clean and inspect fans",
        "area": "Cooling",
        "instructions": "Power down, remove dust without overspeeding fan blades, and check noise, free rotation, guards, ducts, and cable clearance.",
        "thresholds": [_threshold("print_time_s", 750 * 3600), _threshold("hotend_heater_s", 750 * 3600), _threshold("calendar_s", 180 * 86400)],
    },
    {
        "id": "electrical-connectors",
        "name": "Inspect electrical connectors",
        "area": "Electrical",
        "instructions": "Disconnect mains power. Check high-current terminals, ferrules, plugs, grounding, strain relief, discoloration, heat damage, and looseness.",
        "thresholds": [_threshold("print_time_s", 1000 * 3600), _threshold("calendar_s", 365 * 86400)],
    },
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch() -> float:
    return time.time()


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _default_tool_state() -> Dict[str, Any]:
    now = _epoch()
    return {
        "schema": TOOL_SCHEMA,
        "created_at": now,
        "updated_at": now,
        "installed_profile_id": None,
        "profiles": [],
        "history": [],
        "sync": {"state": "unknown", "message": "Klipper has not connected yet"},
    }


def _default_timeline_state() -> Dict[str, Any]:
    now = _epoch()
    return {
        "schema": TIMELINE_SCHEMA,
        "created_at": now,
        "updated_at": now,
        "retention_days": TIMELINE_RETENTION_DAYS,
        "event_limit": TIMELINE_EVENT_LIMIT,
        "events": [],
    }


def _fresh_task(template: Mapping[str, Any], now: float, counters: Mapping[str, float]) -> Dict[str, Any]:
    task = json.loads(json.dumps(template))
    task.update({
        "enabled": True,
        "recommended": True,
        "serviced_at": now,
        "baseline": {key: float(counters.get(key, 0.0)) for key in COUNTER_KEYS},
        "snoozed_until": 0.0,
        "snooze_prints_until": 0.0,
        "updated_at": now,
        "smart_signals": list(SMART_SIGNAL_MAP.get(str(template.get("id", "")), [])),
    })
    return task


def _default_state() -> Dict[str, Any]:
    now = _epoch()
    counters = {key: 0.0 for key in COUNTER_KEYS}
    return {
        "schema": SERVICE_SCHEMA,
        "created_at": now,
        "updated_at": now,
        "counters": counters,
        "tasks": [_fresh_task(task, now, counters) for task in RECOMMENDED_TASKS],
        "history": [],
        "smart": dict(SMART_DEFAULTS),
        "mechanism": "unknown",
        "collector": {"boot_id": None, "xy_distance_mm": 0.0, "z_distance_mm": 0.0, "probe_cycles": 0.0},
        "telemetry": {"job_key": "", "print_duration": 0.0, "filament_used": 0.0, "active": False},
    }


class Klippertools:
    def __init__(self, config) -> None:
        self.server = config.get_server()
        self.eventloop = self.server.get_event_loop()
        self.klippy_apis = self.server.lookup_component("klippy_apis")
        self.machine = self.server.lookup_component("machine")
        self.klippy_connection = self.server.lookup_component("klippy_connection")

        home = Path.home().resolve()
        self.repo_path = Path(config.get("repo_path", "~/klippertools")).expanduser().resolve()
        self.state_path = Path(config.get("state_path", "~/printer_data/klippertools-install-state")).expanduser().resolve()
        self.service_data_path = Path(config.get("service_data_path", "~/printer_data/klippertools-service.json")).expanduser().resolve()
        self.tool_data_path = Path(config.get("tool_data_path", "~/printer_data/klippertools-tools.json")).expanduser().resolve()
        self.timeline_data_path = Path(config.get("timeline_data_path", "~/printer_data/klippertools-timeline.json")).expanduser().resolve()
        for path in (self.repo_path, self.state_path, self.service_data_path, self.tool_data_path, self.timeline_data_path):
            try:
                path.relative_to(home)
            except ValueError as exc:
                raise config.error(f"Klippertools path must remain inside {home}: {path}") from exc

        self.service_state = self._load_service_state()
        self.tool_state = self._load_tool_state()
        self.timeline_state = self._load_timeline_state()
        self._dirty = False
        self._tool_dirty = False
        self._timeline_dirty = False
        self._observed_tool_states: Dict[str, str] = {}
        self._last_save_monotonic = 0.0
        self._last_poll_monotonic: Optional[float] = None
        self._available_objects: set[str] = set()
        self._printer_state = "unknown"
        self.service_timer = self.eventloop.register_timer(self._poll_timer) if hasattr(self.eventloop, "register_timer") else None

        self.update_task: Optional[asyncio.Task] = None
        self.update_status: Dict[str, Any] = {
            "state": "idle", "message": "Ready", "started_at": None,
            "finished_at": None, "restart_required": False,
        }
        self.server.register_endpoint("/machine/klippertools/status", RequestType.GET, self._handle_status)
        self.server.register_endpoint("/machine/klippertools/update", RequestType.POST, self._handle_update)
        self.server.register_endpoint("/machine/klippertools/service/status", RequestType.GET, self._handle_service_status)
        self.server.register_endpoint("/machine/klippertools/service/action", RequestType.POST, self._handle_service_action)
        self.server.register_endpoint("/machine/klippertools/service/export", RequestType.GET, self._handle_service_export)
        self.server.register_endpoint("/machine/klippertools/tools/status", RequestType.GET, self._handle_tool_status)
        self.server.register_endpoint("/machine/klippertools/tools/action", RequestType.POST, self._handle_tool_action)
        self.server.register_endpoint("/machine/klippertools/tools/export", RequestType.GET, self._handle_tool_export)
        self.server.register_endpoint("/machine/klippertools/timeline/status", RequestType.GET, self._handle_timeline_status)
        self.server.register_endpoint("/machine/klippertools/timeline/action", RequestType.POST, self._handle_timeline_action)
        self.server.register_endpoint("/machine/klippertools/timeline/export", RequestType.GET, self._handle_timeline_export)
        if hasattr(self.server, "register_notification"):
            self.server.register_notification("klippertools:service_changed")
            self.server.register_notification("klippertools:tools_changed")
            self.server.register_notification("klippertools:timeline_changed")
        if hasattr(self.server, "register_event_handler"):
            self.server.register_event_handler("server:klippy_ready", self._handle_klippy_ready)
            self.server.register_event_handler("server:klippy_disconnect", self._handle_klippy_disconnect)
            self.server.register_event_handler("server:klippy_shutdown", self._handle_klippy_disconnect)
            self.server.register_event_handler("job_state:state_changed", self._handle_job_state_changed)
            self.server.register_event_handler("klippy_connection:gcode_received", self._handle_gcode_received)

    async def component_init(self) -> None:
        if self.service_timer is not None:
            self.service_timer.start(delay=1.0)

    def _load_timeline_state(self) -> Dict[str, Any]:
        if not self.timeline_data_path.exists():
            return _default_timeline_state()
        try:
            value = json.loads(self.timeline_data_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or int(value.get("schema", 0)) != TIMELINE_SCHEMA:
                raise ValueError("unsupported Printer Health Timeline schema")
            if not isinstance(value.get("events"), list):
                raise ValueError("timeline events must be a list")
            value.setdefault("retention_days", TIMELINE_RETENTION_DAYS)
            value.setdefault("event_limit", TIMELINE_EVENT_LIMIT)
            self._prune_timeline(value)
            return value
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            logging.exception("Unable to load Klippertools timeline data; preserving corrupt file")
            try:
                corrupt = self.timeline_data_path.with_name(
                    self.timeline_data_path.name + ".corrupt-" + str(int(_epoch())))
                os.replace(self.timeline_data_path, corrupt)
            except OSError:
                logging.exception("Unable to preserve corrupt Klippertools timeline data")
            return _default_timeline_state()

    def _prune_timeline(self, state: Optional[Dict[str, Any]] = None) -> None:
        target = state if state is not None else self.timeline_state
        retention_days = int(target.get("retention_days", TIMELINE_RETENTION_DAYS) or TIMELINE_RETENTION_DAYS)
        retention_days = max(1, min(3650, retention_days))
        event_limit = int(target.get("event_limit", TIMELINE_EVENT_LIMIT) or TIMELINE_EVENT_LIMIT)
        event_limit = max(100, min(20000, event_limit))
        cutoff = _epoch() - retention_days * 86400
        events = [
            event for event in target.get("events", [])
            if isinstance(event, dict) and float(event.get("at", 0.0) or 0.0) >= cutoff
        ]
        target["events"] = events[-event_limit:]
        target["retention_days"] = retention_days
        target["event_limit"] = event_limit

    def _save_timeline_state(self) -> None:
        self._prune_timeline()
        self.timeline_state["updated_at"] = _epoch()
        _atomic_write_json(self.timeline_data_path, self.timeline_state)
        self._timeline_dirty = False

    def _timeline_safe_value(self, value: Any, depth: int = 0) -> Any:
        if depth >= 4:
            return str(value)[:200]
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, str):
            return value[:500]
        if isinstance(value, Mapping):
            result: Dict[str, Any] = {}
            for index, (key, item) in enumerate(value.items()):
                if index >= 25:
                    break
                result[str(key)[:80]] = self._timeline_safe_value(item, depth + 1)
            return result
        if isinstance(value, (list, tuple)):
            return [self._timeline_safe_value(item, depth + 1) for item in list(value)[:20]]
        return str(value)[:500]

    def _record_event(
        self, category: str, event_type: str, summary: str,
        *, source: str, severity: str = "info",
        details: Optional[Mapping[str, Any]] = None, save: bool = True,
    ) -> Dict[str, Any]:
        category = re.sub(r"[^a-z0-9_.-]+", "_", str(category).lower())[:40] or "other"
        event_type = re.sub(r"[^a-z0-9_.-]+", "_", str(event_type).lower())[:80] or "event"
        if severity not in {"info", "warning", "error"}:
            severity = "info"
        event = {
            "id": "evt-%d" % time.time_ns(),
            "at": _epoch(),
            "category": category,
            "type": event_type,
            "summary": str(summary)[:300],
            "severity": severity,
            "source": str(source)[:160],
            "details": self._timeline_safe_value(details or {}),
        }
        self.timeline_state.setdefault("events", []).append(event)
        self._prune_timeline()
        self._timeline_dirty = True
        if save:
            self._save_timeline_state()
        if hasattr(self.server, "send_event"):
            self.server.send_event("klippertools:timeline_changed", event)
        return event

    async def _handle_gcode_received(self, script: str) -> None:
        for raw_line in str(script).splitlines():
            line = raw_line.split(";", 1)[0].strip()
            if not line:
                continue
            command = line.split(None, 1)[0].upper()
            if command == "SAVE_CONFIG":
                self._record_event(
                    "configuration", "save_config_requested",
                    "SAVE_CONFIG was requested through Moonraker",
                    source="klippy_connection:gcode_received",
                    details={"command": "SAVE_CONFIG"})
            elif command in {"RESTART", "FIRMWARE_RESTART"}:
                self._record_event(
                    "configuration", command.lower() + "_requested",
                    command + " was requested through Moonraker",
                    source="klippy_connection:gcode_received",
                    details={"command": command})

    async def _handle_timeline_status(self, web_request) -> Dict[str, Any]:
        args = web_request.get_args() if web_request is not None and hasattr(web_request, "get_args") else {}
        category = str(args.get("category", "")).strip().lower()
        event_type = str(args.get("type", "")).strip().lower()
        try:
            start_at = float(args.get("start_at", 0.0) or 0.0)
            end_at = float(args.get("end_at", 0.0) or 0.0)
            limit = int(args.get("limit", 300) or 300)
        except (TypeError, ValueError):
            raise self.server.error("Timeline filters must be numeric", 400)
        if not all(math.isfinite(value) and value >= 0.0 for value in (start_at, end_at)):
            raise self.server.error("Timeline time filters must be finite and non-negative", 400)
        if start_at and end_at and start_at > end_at:
            raise self.server.error("Timeline start_at must not be after end_at", 400)
        limit = max(1, min(2000, limit))
        events = []
        for event in reversed(self.timeline_state.get("events", [])):
            if category and event.get("category") != category:
                continue
            if event_type and event.get("type") != event_type:
                continue
            at = float(event.get("at", 0.0) or 0.0)
            if start_at and at < start_at:
                continue
            if end_at and at > end_at:
                continue
            events.append(event)
            if len(events) >= limit:
                break
        categories = sorted({str(event.get("category")) for event in self.timeline_state.get("events", [])})
        return {
            "schema": TIMELINE_SCHEMA,
            "events": events,
            "categories": categories,
            "retention_days": self.timeline_state.get("retention_days"),
            "event_limit": self.timeline_state.get("event_limit"),
            "total_events": len(self.timeline_state.get("events", [])),
            "updated_at": self.timeline_state.get("updated_at"),
        }

    async def _handle_timeline_action(self, web_request) -> Dict[str, Any]:
        args = web_request.get_args()
        action = str(args.get("action", ""))
        if action == "clear":
            if str(args.get("confirmation", "")) != "CLEAR HEALTH TIMELINE":
                raise self.server.error("Timeline clear confirmation did not match", 400)
            count = len(self.timeline_state.get("events", []))
            self.timeline_state["events"] = []
            self._record_event(
                "system", "timeline_cleared",
                "Printer Health Timeline was cleared",
                source="klippertools.timeline",
                details={"removed_events": count})
        elif action == "retention":
            try:
                days = int(args.get("retention_days"))
                limit = int(args.get("event_limit"))
            except (TypeError, ValueError):
                raise self.server.error("Retention settings must be integers", 400)
            if not 1 <= days <= 3650 or not 100 <= limit <= 20000:
                raise self.server.error("Retention must be 1-3650 days and 100-20000 events", 400)
            self.timeline_state["retention_days"] = days
            self.timeline_state["event_limit"] = limit
            self._record_event(
                "system", "timeline_retention_changed",
                "Timeline retention settings changed",
                source="klippertools.timeline",
                details={"retention_days": days, "event_limit": limit})
        else:
            raise self.server.error(f"Unsupported Timeline action: {action}", 400)
        return await self._handle_timeline_status(web_request)

    async def _handle_timeline_export(self, _web_request) -> Dict[str, Any]:
        return {
            "format": "klippertools-health-timeline",
            "schema": TIMELINE_SCHEMA,
            "exported_at": _utc_now(),
            "retention_days": self.timeline_state.get("retention_days"),
            "events": self.timeline_state.get("events", []),
        }

    def _load_tool_state(self) -> Dict[str, Any]:
        if not self.tool_data_path.exists():
            return _default_tool_state()
        try:
            value = json.loads(self.tool_data_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or int(value.get("schema", 0)) != TOOL_SCHEMA:
                raise ValueError("unsupported Tool Registry data schema")
            profiles = value.get("profiles")
            history = value.get("history")
            if not isinstance(profiles, list) or not isinstance(history, list):
                raise ValueError("invalid profiles or history")
            if len(profiles) > MAX_TOOL_PROFILES:
                raise ValueError("too many Tool Registry profiles")
            ids = set()
            for profile in profiles:
                if not isinstance(profile, dict):
                    raise ValueError("tool profile must be an object")
                profile_id = str(profile.get("id", ""))
                if not PROFILE_ID_RE.fullmatch(profile_id) or profile_id in ids:
                    raise ValueError("invalid or duplicate tool profile id")
                ids.add(profile_id)
                name = str(profile.get("name", "")).strip()
                if not name or len(name) > 100:
                    raise ValueError("invalid tool profile name")
                diameter = float(profile.get("diameter"))
                if not math.isfinite(diameter) or not 0.05 <= diameter <= 5.0:
                    raise ValueError("invalid tool profile diameter")
                profile["diameter"] = diameter
                max_temp = profile.get("max_temp")
                if max_temp not in (None, ""):
                    max_temp = float(max_temp)
                    if not math.isfinite(max_temp) or not 1.0 <= max_temp <= 600.0:
                        raise ValueError("invalid tool profile maximum temperature")
                    profile["max_temp"] = max_temp
                else:
                    profile["max_temp"] = None
                usage = profile.get("usage")
                if not isinstance(usage, dict):
                    raise ValueError("invalid tool profile usage")
                for key in TOOL_USAGE_KEYS:
                    number = float(usage.get(key, 0.0) or 0.0)
                    if not math.isfinite(number) or not 0.0 <= number <= 1e15:
                        raise ValueError("invalid tool profile usage counter")
                    usage[key] = number
                baseline = profile.get("usage_baseline")
                if baseline is not None:
                    if not isinstance(baseline, dict):
                        raise ValueError("invalid tool profile usage baseline")
                    for key in TOOL_USAGE_KEYS:
                        number = float(baseline.get(key, 0.0) or 0.0)
                        if not math.isfinite(number) or not 0.0 <= number <= 1e15:
                            raise ValueError("invalid tool profile usage baseline counter")
                        baseline[key] = number
                profile["retired"] = bool(profile.get("retired", False))
            if any(not isinstance(item, dict) for item in history):
                raise ValueError("tool history entries must be objects")
            value["history"] = history[-TOOL_HISTORY_LIMIT:]
            installed = value.get("installed_profile_id")
            if installed is not None and str(installed) not in ids:
                value["installed_profile_id"] = None
            sync = value.get("sync")
            if not isinstance(sync, dict):
                sync = {"state": "unknown", "message": "Klipper has not connected yet"}
                value["sync"] = sync
            return value
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            logging.exception("Unable to load Klippertools Tool Registry data; preserving corrupt file")
            try:
                corrupt = self.tool_data_path.with_name(
                    self.tool_data_path.name + ".corrupt-" + str(int(_epoch())))
                os.replace(self.tool_data_path, corrupt)
            except OSError:
                logging.exception("Unable to preserve corrupt Klippertools tool data")
            return _default_tool_state()

    def _save_tool_state(self) -> None:
        self.tool_state["updated_at"] = _epoch()
        self.tool_state["history"] = self.tool_state.get("history", [])[-TOOL_HISTORY_LIMIT:]
        _atomic_write_json(self.tool_data_path, self.tool_state)
        self._tool_dirty = False

    def _tool_changed(self, save: bool = True) -> None:
        self._tool_dirty = True
        if save:
            self._save_tool_state()
        if hasattr(self.server, "send_event"):
            self.server.send_event(
                "klippertools:tools_changed",
                {"updated_at": self.tool_state.get("updated_at", _epoch())})

    def _tool_history(self, event_type: str, profile: Mapping[str, Any], **details: Any) -> None:
        event = {
            "type": event_type,
            "at": _epoch(),
            "profile_id": str(profile.get("id", "")),
            "profile_name": str(profile.get("name", ""))[:100],
        }
        if details:
            event["details"] = details
        self.tool_state.setdefault("history", []).append(event)
        self.tool_state["history"] = self.tool_state["history"][-TOOL_HISTORY_LIMIT:]

    def _find_profile(self, profile_id: str) -> Dict[str, Any]:
        for profile in self.tool_state.get("profiles", []):
            if profile.get("id") == profile_id:
                return profile
        raise self.server.error(f"Unknown tool profile: {profile_id}", 404)

    def _validated_profile(
        self, raw: Any, existing: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            raise self.server.error("Tool profile must be an object", 400)
        profile_id = str(raw.get("id", existing.get("id") if existing else "")).strip()
        if not profile_id:
            profile_id = "tool-" + str(time.time_ns())
        if not PROFILE_ID_RE.fullmatch(profile_id):
            raise self.server.error("Tool profile id contains unsupported characters", 400)
        name = str(raw.get("name", "")).strip()
        if not name or len(name) > 100:
            raise self.server.error("Tool profile name must contain 1 to 100 characters", 400)
        try:
            diameter = float(raw.get("diameter"))
        except (TypeError, ValueError):
            raise self.server.error("Tool diameter must be numeric", 400)
        if not math.isfinite(diameter) or not 0.05 <= diameter <= 5.0:
            raise self.server.error("Tool diameter must be between 0.05 and 5.0 mm", 400)
        material = str(raw.get("material", "unspecified")).strip()[:60] or "unspecified"
        notes = str(raw.get("notes", "")).strip()[:4000]
        max_temp_raw = raw.get("max_temp")
        max_temp = None
        if max_temp_raw not in (None, ""):
            try:
                max_temp = float(max_temp_raw)
            except (TypeError, ValueError):
                raise self.server.error("Maximum temperature must be numeric", 400)
            if not math.isfinite(max_temp) or not 1.0 <= max_temp <= 600.0:
                raise self.server.error("Maximum temperature must be between 1 and 600 C", 400)
        now = _epoch()
        base = dict(existing or {})
        base.update({
            "id": profile_id,
            "name": name,
            "diameter": diameter,
            "material": material,
            "notes": notes,
            "max_temp": max_temp,
            "updated_at": now,
        })
        base.setdefault("created_at", now)
        base.setdefault("retired", False)
        base.setdefault("retired_at", None)
        base.setdefault("installed_at", None)
        base.setdefault("usage", {key: 0.0 for key in TOOL_USAGE_KEYS})
        base.setdefault("usage_baseline", None)
        for key in TOOL_USAGE_KEYS:
            value = float(base["usage"].get(key, 0.0) or 0.0)
            base["usage"][key] = value if math.isfinite(value) and value >= 0 else 0.0
        return base

    def _profile_usage(self, profile: Mapping[str, Any]) -> Dict[str, float]:
        result = {
            key: max(0.0, float(profile.get("usage", {}).get(key, 0.0) or 0.0))
            for key in TOOL_USAGE_KEYS
        }
        if profile.get("id") == self.tool_state.get("installed_profile_id"):
            baseline = profile.get("usage_baseline")
            if isinstance(baseline, dict):
                for key in TOOL_USAGE_KEYS:
                    current = float(self.service_state.get("counters", {}).get(key, 0.0) or 0.0)
                    start = float(baseline.get(key, current) or 0.0)
                    result[key] += max(0.0, current - start)
        return result

    def _finalize_installed_usage(self) -> Optional[Dict[str, Any]]:
        installed_id = self.tool_state.get("installed_profile_id")
        if not installed_id:
            return None
        profile = self._find_profile(str(installed_id))
        profile["usage"] = self._profile_usage(profile)
        profile["usage_baseline"] = None
        profile["updated_at"] = _epoch()
        return profile

    async def _sync_installed_tool(self) -> None:
        installed_id = self.tool_state.get("installed_profile_id")
        if installed_id:
            profile = self._find_profile(str(installed_id))
            escaped_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(profile.get("name", profile["id"])))[:64]
            script = (
                "NOZZLE_GUARD_SET_TOOL DIAMETER=%.6f PROFILE=%s NAME=%s"
                % (float(profile["diameter"]), profile["id"], escaped_name))
        else:
            script = "NOZZLE_GUARD_CLEAR_TOOL"
        try:
            await self.klippy_apis.run_gcode(script)
        except Exception as exc:
            logging.warning("Unable to synchronize Tool Registry with Nozzle Guard: %s", exc)
            self.tool_state["sync"] = {
                "state": "fallback",
                "message": "Nozzle Guard is using Klipper configuration until synchronization succeeds",
                "error": str(exc)[:500],
            }
        else:
            self.tool_state["sync"] = {
                "state": "synchronized",
                "message": (
                    "Nozzle Guard uses the installed Tool Registry profile"
                    if installed_id else
                    "Nozzle Guard uses Klipper nozzle configuration"),
                "error": None,
            }
        self._tool_changed(save=True)

    async def _handle_tool_status(self, _web_request) -> Dict[str, Any]:
        installed_id = self.tool_state.get("installed_profile_id")
        profiles = []
        for profile in self.tool_state.get("profiles", []):
            item = json.loads(json.dumps(profile))
            item["installed"] = item.get("id") == installed_id
            item["status"] = "installed" if item["installed"] else "retired" if item.get("retired") else "available"
            item["usage_total"] = self._profile_usage(profile)
            profiles.append(item)
        profiles.sort(key=lambda item: (not item["installed"], item.get("retired", False), str(item["name"]).lower()))
        return {
            "schema": TOOL_SCHEMA,
            "installed_profile_id": installed_id,
            "profiles": profiles,
            "history": list(reversed(self.tool_state.get("history", [])[-200:])),
            "sync": dict(self.tool_state.get("sync", {})),
            "updated_at": self.tool_state.get("updated_at"),
        }

    async def _handle_tool_action(self, web_request) -> Dict[str, Any]:
        args = web_request.get_args()
        action = str(args.get("action", ""))
        if action == "save_profile":
            raw = args.get("profile")
            raw_id = str(raw.get("id", "")) if isinstance(raw, dict) else ""
            existing = next((p for p in self.tool_state["profiles"] if p.get("id") == raw_id), None)
            changed_installed = existing is not None and existing.get("id") == self.tool_state.get("installed_profile_id")
            if changed_installed:
                await self._assert_idle()
            profile = self._validated_profile(raw, existing)
            if existing is None:
                if any(p.get("id") == profile["id"] for p in self.tool_state["profiles"]):
                    raise self.server.error("Tool profile id already exists", 409)
                self.tool_state["profiles"].append(profile)
                self._tool_history("created", profile)
            else:
                existing.clear()
                existing.update(profile)
                self._tool_history("updated", existing)
            self._tool_changed(save=True)
            if changed_installed:
                await self._sync_installed_tool()
        elif action == "install_profile":
            await self._assert_idle()
            profile = self._find_profile(str(args.get("profile_id", "")))
            if profile.get("retired"):
                raise self.server.error("Retired tool profiles cannot be installed", 409)
            previous = self._finalize_installed_usage()
            if previous is not None and previous.get("id") != profile.get("id"):
                self._tool_history("removed", previous, usage=previous.get("usage", {}))
            now = _epoch()
            self.tool_state["installed_profile_id"] = profile["id"]
            profile["installed_at"] = now
            profile["usage_baseline"] = {
                key: float(self.service_state.get("counters", {}).get(key, 0.0) or 0.0)
                for key in TOOL_USAGE_KEYS
            }
            profile["updated_at"] = now
            self._tool_history("installed", profile)
            self._tool_changed(save=True)
            await self._sync_installed_tool()
        elif action == "clear_installed":
            await self._assert_idle()
            previous = self._finalize_installed_usage()
            if previous is not None:
                self._tool_history("removed", previous, usage=previous.get("usage", {}))
            self.tool_state["installed_profile_id"] = None
            self._tool_changed(save=True)
            await self._sync_installed_tool()
        elif action == "retire_profile":
            profile = self._find_profile(str(args.get("profile_id", "")))
            if profile.get("id") == self.tool_state.get("installed_profile_id"):
                raise self.server.error("Remove the installed tool before retiring its profile", 409)
            profile["retired"] = True
            profile["retired_at"] = _epoch()
            profile["updated_at"] = _epoch()
            self._tool_history("retired", profile)
            self._tool_changed(save=True)
        elif action == "restore_profile":
            profile = self._find_profile(str(args.get("profile_id", "")))
            profile["retired"] = False
            profile["retired_at"] = None
            profile["updated_at"] = _epoch()
            self._tool_history("restored", profile)
            self._tool_changed(save=True)
        elif action == "delete_profile":
            profile = self._find_profile(str(args.get("profile_id", "")))
            if profile.get("id") == self.tool_state.get("installed_profile_id"):
                raise self.server.error("The installed tool profile cannot be deleted", 409)
            if str(args.get("confirmation", "")) != "DELETE TOOL PROFILE":
                raise self.server.error("Tool profile deletion confirmation did not match", 400)
            self._tool_history("deleted", profile)
            self.tool_state["profiles"].remove(profile)
            self._tool_changed(save=True)
        elif action == "import":
            payload = args.get("payload")
            if not isinstance(payload, dict) or not isinstance(payload.get("profiles"), list):
                raise self.server.error("Import must contain a profiles list", 400)
            incoming = payload["profiles"]
            if len(incoming) > MAX_TOOL_PROFILES or len(self.tool_state["profiles"]) + len(incoming) > MAX_TOOL_PROFILES:
                raise self.server.error("Tool Registry supports at most %d profiles" % MAX_TOOL_PROFILES, 400)
            existing_ids = {str(p.get("id")) for p in self.tool_state["profiles"]}
            imported = []
            for raw in incoming:
                profile = self._validated_profile(raw)
                base_id = profile["id"]
                candidate = base_id
                suffix = 2
                while candidate in existing_ids:
                    candidate = f"{base_id[:54]}-import-{suffix}"
                    suffix += 1
                profile["id"] = candidate
                profile["retired"] = bool(raw.get("retired", False)) if isinstance(raw, dict) else False
                imported_usage = raw.get("usage_total", raw.get("usage", {})) if isinstance(raw, dict) else {}
                if isinstance(imported_usage, dict):
                    for key in TOOL_USAGE_KEYS:
                        try:
                            value = float(imported_usage.get(key, 0.0) or 0.0)
                        except (TypeError, ValueError):
                            value = 0.0
                        profile["usage"][key] = value if math.isfinite(value) and 0.0 <= value <= 1e15 else 0.0
                profile["installed_at"] = None
                profile["usage_baseline"] = None
                existing_ids.add(candidate)
                imported.append(profile)
                self._tool_history("imported", profile)
            self.tool_state["profiles"].extend(imported)
            self._tool_changed(save=True)
        else:
            raise self.server.error(f"Unsupported Tool Registry action: {action}", 400)
        self._record_event(
            "tool", "tool_registry_" + re.sub(r"[^a-z0-9_.-]+", "_", action.lower()),
            "Tool Registry action completed: %s" % action.replace("_", " "),
            source="klippertools.tools",
            details={
                "action": action,
                "profile_id": args.get("profile_id") or (args.get("profile", {}).get("id") if isinstance(args.get("profile"), dict) else None),
            }, save=True)
        return await self._handle_tool_status(web_request)

    async def _handle_tool_export(self, _web_request) -> Dict[str, Any]:
        profiles = []
        for profile in self.tool_state.get("profiles", []):
            item = json.loads(json.dumps(profile))
            item["usage_total"] = self._profile_usage(profile)
            item.pop("usage_baseline", None)
            profiles.append(item)
        return {
            "format": "klippertools-tools",
            "schema": TOOL_SCHEMA,
            "exported_at": _utc_now(),
            "profiles": profiles,
            "history": self.tool_state.get("history", []),
        }

    def _load_service_state(self) -> Dict[str, Any]:
        if not self.service_data_path.exists():
            return _default_state()
        try:
            value = json.loads(self.service_data_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Service Manager data must be an object")
            schema = int(value.get("schema", 0))
            if schema not in (1, SERVICE_SCHEMA):
                raise ValueError("unsupported Service Manager data schema")
            counters = value.get("counters")
            if not isinstance(counters, dict):
                raise ValueError("missing counters")
            for key in COUNTER_KEYS:
                number = float(counters.get(key, 0.0))
                counters[key] = number if math.isfinite(number) and number >= 0 else 0.0
            if not isinstance(value.get("tasks"), list) or not isinstance(value.get("history"), list):
                raise ValueError("invalid tasks or history")
            if len(value["tasks"]) > MAX_SERVICE_TASKS:
                raise ValueError("too many Service Manager tasks")
            migrated = schema == 1
            value["schema"] = SERVICE_SCHEMA
            smart = value.setdefault("smart", dict(SMART_DEFAULTS))
            if not isinstance(smart, dict):
                smart = dict(SMART_DEFAULTS)
                value["smart"] = smart
            for key, default in SMART_DEFAULTS.items():
                smart.setdefault(key, default)
            value.setdefault("mechanism", "unknown")
            value.setdefault("collector", {})
            value.setdefault("telemetry", {})
            task_ids = set()
            for task in value["tasks"]:
                if not isinstance(task, dict):
                    raise ValueError("service task must be an object")
                task_id = str(task.get("id", ""))
                if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", task_id) or task_id in task_ids:
                    raise ValueError("invalid or duplicate service task id")
                task_ids.add(task_id)
                name = str(task.get("name", "")).strip()
                if not name or len(name) > 100:
                    raise ValueError("invalid service task name")
                thresholds = task.get("thresholds")
                baseline = task.get("baseline")
                if not isinstance(thresholds, list) or not thresholds or not isinstance(baseline, dict):
                    raise ValueError("invalid service task thresholds or baseline")
                for threshold in thresholds:
                    if not isinstance(threshold, dict):
                        raise ValueError("service threshold must be an object")
                    metric = str(threshold.get("metric", ""))
                    limit = float(threshold.get("limit", 0.0) or 0.0)
                    if metric not in METRICS or not math.isfinite(limit) or not 0.0 < limit <= 1e15:
                        raise ValueError("invalid service threshold")
                    threshold["limit"] = limit
                    threshold["enabled"] = bool(threshold.get("enabled", True))
                for key in COUNTER_KEYS:
                    number = float(baseline.get(key, 0.0) or 0.0)
                    if not math.isfinite(number) or number < 0.0:
                        raise ValueError("invalid service task baseline")
                    baseline[key] = number
                for field in ("serviced_at", "snoozed_until", "snooze_prints_until"):
                    number = float(task.get(field, 0.0) or 0.0)
                    if not math.isfinite(number) or number < 0.0:
                        raise ValueError("invalid service task timestamp")
                    task[field] = number
                signals = task.setdefault(
                    "smart_signals",
                    list(SMART_SIGNAL_MAP.get(task_id, [])))
                if not isinstance(signals, list) or len(signals) > 20:
                    raise ValueError("invalid service smart signals")
                for signal in signals:
                    if not re.fullmatch(r"[a-z0-9_.-]{1,80}", str(signal)):
                        raise ValueError("invalid service smart signal")
            if migrated:
                _atomic_write_json(self.service_data_path, value)
            return value
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            logging.exception("Unable to load Klippertools Service Manager data; preserving corrupt file")
            try:
                corrupt = self.service_data_path.with_name(
                    self.service_data_path.name + ".corrupt-" + str(int(_epoch())))
                os.replace(self.service_data_path, corrupt)
            except OSError:
                logging.exception("Unable to preserve corrupt Klippertools service data")
            return _default_state()

    def _save_service_state(self) -> None:
        self.service_state["updated_at"] = _epoch()
        self.service_data_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=self.service_data_path.name + ".", dir=self.service_data_path.parent)
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(self.service_state, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.service_data_path)
            directory_fd = os.open(self.service_data_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            self._dirty = False
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise

    def _changed(self, save: bool = False) -> None:
        self._dirty = True
        if save:
            self._save_service_state()
        if hasattr(self.server, "send_event"):
            self.server.send_event("klippertools:service_changed", {"updated_at": self.service_state.get("updated_at", _epoch())})

    async def _handle_klippy_ready(self) -> None:
        try:
            objects = await self.klippy_apis.get_object_list()
            self._available_objects = set(objects or [])
        except Exception:
            logging.exception("Klippertools could not discover Klipper objects")
            self._available_objects = set()
        self._last_poll_monotonic = None
        await self._detect_printer_mechanism()
        await self._sync_installed_tool()
        self._record_event(
            "system", "klipper_ready", "Klipper reported ready",
            source="server:klippy_ready", save=True)

    async def _detect_printer_mechanism(self) -> None:
        try:
            status = await self.klippy_apis.query_objects(
                {"configfile": ["settings"]}, default={})
            settings = status.get("configfile", {}).get("settings", {})
            kinematics = str(settings.get("printer", {}).get("kinematics", "")).lower()
        except Exception:
            logging.debug("Unable to detect printer mechanism", exc_info=True)
            return
        mechanism = "unknown"
        if kinematics.startswith("corexy"):
            mechanism = "corexy"
        elif kinematics == "cartesian":
            mechanism = "cartesian"
        elif kinematics.startswith("delta"):
            mechanism = "delta"
        if mechanism != self.service_state.get("mechanism", "unknown"):
            self.service_state["mechanism"] = mechanism
            self._changed(save=True)
            if mechanism != "unknown":
                self._record_event(
                    "service", "printer_mechanism_detected",
                    "Printer mechanism detected: %s" % mechanism,
                    source="klipper.configfile",
                    details={"kinematics": kinematics, "mechanism": mechanism},
                    save=True)

    async def _handle_klippy_disconnect(self) -> None:
        self._printer_state = "disconnected"
        if self._dirty:
            self._save_service_state()
        if self._tool_dirty:
            self._save_tool_state()
        self._record_event(
            "system", "klipper_disconnected", "Klipper disconnected or shut down",
            source="server:klippy_disconnect", severity="warning", save=True)

    async def _handle_job_state_changed(self, _job_event, _previous, _current) -> None:
        await self._poll_printer()
        if self._dirty:
            self._save_service_state()

    async def _poll_timer(self, eventtime: float) -> float:
        await self._poll_printer(eventtime)
        if self._dirty and eventtime - self._last_save_monotonic >= SAVE_SECONDS:
            self._save_service_state()
            self._last_save_monotonic = eventtime
        return eventtime + POLL_SECONDS

    async def _poll_printer(self, eventtime: Optional[float] = None) -> None:
        monotonic = eventtime if eventtime is not None else time.monotonic()
        elapsed = 0.0 if self._last_poll_monotonic is None else max(0.0, min(15.0, monotonic - self._last_poll_monotonic))
        self._last_poll_monotonic = monotonic
        requested: Dict[str, Optional[List[str]]] = {
            "print_stats": ["state", "filename", "print_duration", "total_duration", "filament_used"]
        }
        known = self._available_objects
        for heater in ("extruder", "heater_bed"):
            if not known or heater in known:
                requested[heater] = ["target"]
        if not known or "service_metrics" in known:
            requested["service_metrics"] = ["boot_id", "xy_distance_mm", "z_distance_mm", "probe_cycles", "distance_kind"]
        observed_fields = {
            "thermal_soak": ["state", "message", "error", "sensor", "target", "elapsed_seconds"],
            "calibration_center": ["state", "active_flow", "message", "error", "last_result"],
            "motion_wizard": ["state", "message", "error", "completed_axes", "results"],
            "nozzle_guard": ["state", "message", "filename", "comparison_source", "installed_profile_id"],
            "configfile": ["save_config_pending", "save_config_pending_items", "warnings"],
        }
        for object_name, fields in observed_fields.items():
            if not known or object_name in known:
                requested[object_name] = fields
        try:
            status = await self.klippy_apis.query_objects(requested, default={})
        except TypeError:
            status = await self.klippy_apis.query_objects(requested)
        except Exception:
            logging.debug("Klippertools service poll unavailable", exc_info=True)
            return
        if not isinstance(status, dict) or "print_stats" not in status:
            return
        self._reconcile_print(status.get("print_stats", {}))
        if elapsed:
            if float(status.get("extruder", {}).get("target", 0.0) or 0.0) > 0:
                self.service_state["counters"]["hotend_heater_s"] += elapsed
                self._dirty = True
            if float(status.get("heater_bed", {}).get("target", 0.0) or 0.0) > 0:
                self.service_state["counters"]["bed_heater_s"] += elapsed
                self._dirty = True
        metrics = status.get("service_metrics")
        if isinstance(metrics, dict):
            self._reconcile_collector(metrics)
        self._observe_status_events(status)

    def _reconcile_print(self, stats: Mapping[str, Any]) -> None:
        telemetry = self.service_state.setdefault("telemetry", {})
        state = str(stats.get("state", "unknown")).lower()
        self._printer_state = state
        filename = str(stats.get("filename", ""))[:300]
        current_duration = max(0.0, float(stats.get("print_duration", 0.0) or 0.0))
        current_filament = max(0.0, float(stats.get("filament_used", 0.0) or 0.0))
        active = state in ACTIVE_STATES
        previous_state = str(telemetry.get("state", "unknown")).lower()
        previous_job = str(telemetry.get("job_key", ""))
        same_job = bool(filename and filename == previous_job)
        was_active = bool(telemetry.get("active", False))

        if active and (not was_active or not same_job):
            self.service_state["counters"]["prints"] += 1
            telemetry.update({
                "job_key": filename,
                "print_duration": current_duration,
                "filament_used": current_filament,
                "active": True,
                "state": state,
            })
            self._dirty = True
            self._record_event(
                "print", "print_started", "Print started",
                source="print_stats",
                details={"filename": filename or None},
                save=True)
            return

        if same_job:
            duration_delta = max(
                0.0, current_duration - float(telemetry.get("print_duration", 0.0) or 0.0))
            filament_delta = max(
                0.0, current_filament - float(telemetry.get("filament_used", 0.0) or 0.0))
            if duration_delta or filament_delta:
                self.service_state["counters"]["print_time_s"] += duration_delta
                self.service_state["counters"]["filament_mm"] += filament_delta
                self._dirty = True

        terminal = state in {"complete", "cancelled", "error"}
        if was_active and terminal and previous_state in ACTIVE_STATES:
            terminal_type = {
                "complete": "print_completed",
                "cancelled": "print_cancelled",
                "error": "print_failed",
            }[state]
            severity = "info" if state == "complete" else "warning" if state == "cancelled" else "error"
            self._record_event(
                "print", terminal_type,
                "Print completed" if state == "complete" else "Print cancelled" if state == "cancelled" else "Print failed",
                source="print_stats", severity=severity,
                details={
                    "filename": filename or previous_job or None,
                    "print_duration": current_duration,
                    "filament_used": current_filament,
                },
                save=True)

        telemetry.update({
            "job_key": filename or previous_job,
            "print_duration": current_duration,
            "filament_used": current_filament,
            "active": active,
            "state": state,
        })

    def _reconcile_collector(self, values: Mapping[str, Any]) -> None:
        collector = self.service_state.setdefault("collector", {})
        boot_id = str(values.get("boot_id", ""))
        same_boot = boot_id and collector.get("boot_id") == boot_id
        for key in ("xy_distance_mm", "z_distance_mm", "probe_cycles"):
            current = max(0.0, float(values.get(key, 0.0) or 0.0))
            previous = max(0.0, float(collector.get(key, 0.0) or 0.0))
            if same_boot and current >= previous:
                delta = current - previous
                if delta:
                    self.service_state["counters"][key] += delta
                    self._dirty = True
            collector[key] = current
        collector["boot_id"] = boot_id
        collector["distance_kind"] = "commanded"

    def _observe_status_events(self, status: Mapping[str, Any]) -> None:
        definitions = {
            "thermal_soak": {
                "stable": ("calibration", "thermal_soak_stable", "Thermal soak reached stability", "info"),
                "timed_out": ("calibration", "thermal_soak_timed_out", "Thermal soak timed out", "warning"),
                "canceled": ("calibration", "thermal_soak_cancelled", "Thermal soak was cancelled", "warning"),
                "error": ("calibration", "thermal_soak_error", "Thermal soak failed", "error"),
            },
            "calibration_center": {
                "review": ("calibration", "calibration_completed", "Calibration result is ready for review", "info"),
                "error": ("calibration", "calibration_error", "Calibration workflow failed", "error"),
            },
            "motion_wizard": {
                "review": ("calibration", "motion_calibration_completed", "Motion calibration result is ready for review", "info"),
                "error": ("calibration", "motion_calibration_error", "Motion calibration failed", "error"),
            },
            "nozzle_guard": {
                "mismatch": ("warning", "nozzle_mismatch", "Nozzle Guard detected a confirmed mismatch", "warning"),
                "error": ("warning", "nozzle_guard_error", "Nozzle Guard could not inspect the selected file", "error"),
            },
        }
        for object_name, state_map in definitions.items():
            values = status.get(object_name)
            if not isinstance(values, Mapping):
                continue
            state = str(values.get("state", ""))
            key = object_name + ":state"
            previous = self._observed_tool_states.get(key)
            self._observed_tool_states[key] = state
            if state == previous or state not in state_map:
                continue
            category, event_type, summary, severity = state_map[state]
            details = {
                key: values.get(key)
                for key in (
                    "message", "error", "sensor", "target", "elapsed_seconds",
                    "active_flow", "last_result", "completed_axes", "results",
                    "filename", "comparison_source", "installed_profile_id")
                if values.get(key) not in (None, "", [], {})
            }
            self._record_event(
                category, event_type, summary,
                source="klipper.%s" % object_name,
                severity=severity, details=details, save=True)

        configfile = status.get("configfile")
        if isinstance(configfile, Mapping):
            pending = bool(configfile.get("save_config_pending", False))
            previous_pending = self._observed_tool_states.get("configfile:pending")
            self._observed_tool_states["configfile:pending"] = "1" if pending else "0"
            if pending and previous_pending != "1":
                self._record_event(
                    "configuration", "configuration_changes_pending",
                    "Klipper has configuration changes pending review",
                    source="klipper.configfile",
                    details={"pending_items": configfile.get("save_config_pending_items", {})},
                    save=True)
            elif not pending and previous_pending == "1":
                self._record_event(
                    "configuration", "configuration_pending_cleared",
                    "Previously pending configuration changes are no longer pending",
                    source="klipper.configfile",
                    details={
                        "note": "This fact alone does not prove whether SAVE_CONFIG, restart, or abort cleared them"
                    }, save=True)
            warnings = configfile.get("warnings", [])
            if isinstance(warnings, list):
                signature = json.dumps(warnings, sort_keys=True, default=str)
                if signature != self._observed_tool_states.get("configfile:warnings"):
                    self._observed_tool_states["configfile:warnings"] = signature
                    for warning in warnings:
                        if not isinstance(warning, Mapping):
                            continue
                        self._record_event(
                            "warning", "configuration_warning",
                            str(warning.get("message", "Klipper configuration warning"))[:300],
                            source="klipper.configfile", severity="warning",
                            details={"type": warning.get("type")}, save=False)
                    if warnings:
                        self._save_timeline_state()

    def _installed_version(self) -> str:
        try:
            text = self.state_path.read_text(encoding="utf-8").lstrip()
            if text.startswith("{"):
                return str(json.loads(text).get("plugin_version", "unknown"))
            for line in text.splitlines():
                if line.startswith("PLUGIN_VERSION="):
                    return line.split("=", 1)[1]
        except (OSError, ValueError, TypeError):
            logging.exception("Unable to read Klippertools install state")
        return "unknown"

    async def _handle_status(self, _web_request) -> Dict[str, Any]:
        result = dict(self.update_status)
        result["installed_version"] = self._installed_version()
        result["updating"] = self.update_task is not None and not self.update_task.done()
        return result

    def _metric_status(self, task: Mapping[str, Any], threshold: Mapping[str, Any], now: float) -> Dict[str, Any]:
        metric = str(threshold.get("metric", ""))
        limit = float(threshold.get("limit", 0.0) or 0.0)
        if metric == "calendar_s":
            used = max(0.0, now - float(task.get("serviced_at", now)))
        else:
            used = max(0.0, float(self.service_state["counters"].get(metric, 0.0)) - float(task.get("baseline", {}).get(metric, 0.0)))
        progress = used / limit if limit > 0 else 0.0
        estimated_due = None
        if metric == "calendar_s":
            estimated_due = float(task.get("serviced_at", now)) + limit
        elif used > 0:
            age = max(1.0, now - float(task.get("serviced_at", now)))
            rate = used / age
            if rate > 0:
                estimated_due = now + max(0.0, limit - used) / rate
        return {
            "metric": metric,
            "label": METRICS.get(metric, {}).get("label", metric),
            "unit": METRICS.get(metric, {}).get("unit", "count"),
            "limit": limit,
            "used": used,
            "remaining": limit - used,
            "progress": progress,
            "due": progress >= 1.0,
            "estimated_due": estimated_due,
        }

    def _smart_status(
        self, task: Mapping[str, Any], metrics: List[Mapping[str, Any]], now: float
    ) -> Dict[str, Any]:
        settings = self.service_state.get("smart", {})
        enabled = bool(settings.get("enabled", False))
        signals = [
            str(item) for item in task.get("smart_signals", [])
            if re.fullmatch(r"[a-z0-9_.-]{1,80}", str(item))
        ]
        limiting = max(metrics, key=lambda item: float(item.get("progress", 0.0)), default=None)
        base_progress = float(limiting.get("progress", 0.0)) if limiting else 0.0
        base = {
            "enabled": enabled,
            "state": "disabled" if not enabled else "insufficient_data",
            "confidence": "none",
            "signals": signals,
            "evidence_count": 0,
            "weighted_score": 0.0,
            "advance_fraction": 0.0,
            "effective_progress": base_progress,
            "smart_due": False,
            "reason": "Smart suggestions are disabled" if not enabled else "No configured warning signals for this task",
            "limiting_threshold": limiting,
            "evidence": [],
        }
        if not enabled or not signals:
            return base
        lookback_days = max(1, min(3650, int(settings.get("lookback_days", 90) or 90)))
        reset_at = float(settings.get("reset_at", 0.0) or 0.0)
        serviced_at = float(task.get("serviced_at", 0.0) or 0.0)
        cutoff = max(now - lookback_days * 86400, reset_at, serviced_at)
        matching = [
            event for event in self.timeline_state.get("events", [])
            if float(event.get("at", 0.0) or 0.0) >= cutoff
            and str(event.get("type", "")) in signals
            and str(event.get("severity", "info")) in {"warning", "error"}
        ]
        weights = {"warning": 1.0, "error": 2.0}
        score = sum(weights.get(str(event.get("severity")), 0.0) for event in matching)
        min_events = max(1, min(20, int(settings.get("min_events", 3) or 3)))
        base.update({
            "evidence_count": len(matching),
            "weighted_score": score,
            "evidence": [
                {
                    "id": event.get("id"),
                    "at": event.get("at"),
                    "type": event.get("type"),
                    "severity": event.get("severity"),
                    "summary": event.get("summary"),
                }
                for event in matching[-20:]
            ],
        })
        if len(matching) < min_events:
            base["reason"] = (
                "%d matching warning/failure event(s); %d required before suggesting an earlier service"
                % (len(matching), min_events))
            return base
        max_advance = float(settings.get("max_advance_fraction", 0.25) or 0.25)
        max_advance = max(0.0, min(0.5, max_advance))
        advance = min(max_advance, score * 0.04)
        denominator = max(0.5, 1.0 - advance)
        effective_progress = base_progress / denominator
        confidence = "low" if len(matching) < 5 else "medium" if len(matching) < 8 else "high"
        counts: Dict[str, int] = {}
        for event in matching:
            event_type = str(event.get("type", ""))
            counts[event_type] = counts.get(event_type, 0) + 1
        base.update({
            "state": "suggestion",
            "confidence": confidence,
            "advance_fraction": advance,
            "effective_progress": effective_progress,
            "smart_due": effective_progress >= 1.0,
            "reason": (
                "%d matching warning/failure events (%s) suggest reviewing this task up to %.0f%% earlier; intervals and baselines are unchanged"
                % (len(matching), ", ".join("%s=%d" % item for item in sorted(counts.items())), advance * 100)),
        })
        return base

    def _task_status(self, task: Mapping[str, Any], now: float) -> Dict[str, Any]:
        metrics = [
            self._metric_status(task, item, now)
            for item in task.get("thresholds", [])
            if item.get("enabled", True)
            and str(item.get("metric", "")) in METRICS
            and float(item.get("limit", 0.0) or 0.0) > 0
        ]
        base_progress = max((item["progress"] for item in metrics), default=0.0)
        base_state = "due" if base_progress >= 1.0 else "soon" if base_progress >= 0.8 else "good"
        smart = self._smart_status(task, metrics, now)
        progress = max(base_progress, float(smart.get("effective_progress", base_progress)))
        due = base_state == "due" or bool(smart.get("smart_due", False))
        state = "due" if due else "soon" if progress >= 0.8 else "good"
        estimated = [item["estimated_due"] for item in metrics if item["estimated_due"] is not None]
        snoozed = (
            now < float(task.get("snoozed_until", 0.0) or 0.0)
            or float(self.service_state["counters"].get("prints", 0.0))
            < float(task.get("snooze_prints_until", 0.0) or 0.0))
        result = json.loads(json.dumps(task))
        result.update({
            "metrics": metrics,
            "base_progress": base_progress,
            "progress": progress,
            "base_state": base_state,
            "state": state,
            "base_due": base_state == "due",
            "due": due,
            "snoozed": snoozed,
            "estimated_due": min(estimated) if estimated else None,
            "smart": smart,
        })
        return result

    async def _handle_service_status(self, _web_request) -> Dict[str, Any]:
        now = _epoch()
        tasks = [self._task_status(task, now) for task in self.service_state["tasks"] if task.get("enabled", True)]
        tasks.sort(key=lambda item: (-float(item["progress"]), str(item["name"]).lower()))
        notifications = [task for task in tasks if task["due"] and not task["snoozed"] and self._printer_state not in ACTIVE_STATES]
        mechanism = str(self.service_state.get("mechanism", "unknown"))
        return {
            "schema": SERVICE_SCHEMA,
            "counter_kind": {"xy_distance_mm": "commanded", "z_distance_mm": "commanded"},
            "printer_state": self._printer_state,
            "metrics": METRICS,
            "counters": dict(self.service_state["counters"]),
            "tasks": tasks,
            "notifications": notifications,
            "history": list(reversed(self.service_state["history"][-200:])),
            "recommended_count": len(RECOMMENDED_TASKS),
            "smart": dict(self.service_state.get("smart", SMART_DEFAULTS)),
            "mechanism": mechanism,
            "mechanism_preset": MECHANISM_PRESETS.get(mechanism),
            "updated_at": self.service_state.get("updated_at"),
        }

    def _validated_task(self, raw: Any, existing: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            raise self.server.error("Task must be an object", 400)
        task_id = str(raw.get("id", existing.get("id") if existing else "")).strip()
        if not task_id:
            task_id = "custom-" + str(int(_epoch() * 1000))
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", task_id):
            raise self.server.error("Task id contains unsupported characters", 400)
        name = str(raw.get("name", "")).strip()
        if not name or len(name) > 100:
            raise self.server.error("Task name must contain 1 to 100 characters", 400)
        area = str(raw.get("area", "Custom")).strip()[:60]
        instructions = str(raw.get("instructions", "")).strip()[:4000]
        thresholds: List[Dict[str, Any]] = []
        if not isinstance(raw.get("thresholds"), list):
            raise self.server.error("Task thresholds must be a list", 400)
        for item in raw["thresholds"]:
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            metric = str(item.get("metric", ""))
            if metric not in METRICS:
                raise self.server.error(f"Unsupported service metric: {metric}", 400)
            limit = float(item.get("limit", 0.0) or 0.0)
            if not math.isfinite(limit) or limit <= 0 or limit > 1e15:
                raise self.server.error("Threshold limits must be positive finite values", 400)
            thresholds.append({"metric": metric, "limit": limit, "enabled": True})
        if not thresholds:
            raise self.server.error("Enable at least one service threshold", 400)
        signals_raw = raw.get(
            "smart_signals",
            existing.get("smart_signals", SMART_SIGNAL_MAP.get(task_id, []))
            if existing else SMART_SIGNAL_MAP.get(task_id, []))
        if not isinstance(signals_raw, list):
            raise self.server.error("Smart signals must be a list", 400)
        smart_signals = []
        for signal in signals_raw[:20]:
            signal = str(signal).strip().lower()
            if not re.fullmatch(r"[a-z0-9_.-]{1,80}", signal):
                raise self.server.error("Smart signal contains unsupported characters", 400)
            if signal not in smart_signals:
                smart_signals.append(signal)
        now = _epoch()
        base = dict(existing or {})
        base.update({
            "id": task_id, "name": name, "area": area,
            "instructions": instructions, "thresholds": thresholds,
            "enabled": bool(raw.get("enabled", True)),
            "recommended": bool(raw.get("recommended", False)),
            "smart_signals": smart_signals, "updated_at": now})
        base.setdefault("serviced_at", now)
        base.setdefault("baseline", dict(self.service_state["counters"]))
        base.setdefault("snoozed_until", 0.0)
        base.setdefault("snooze_prints_until", 0.0)
        return base

    def _find_task(self, task_id: str) -> Dict[str, Any]:
        for task in self.service_state["tasks"]:
            if task.get("id") == task_id:
                return task
        raise self.server.error(f"Unknown service task: {task_id}", 404)

    async def _handle_service_action(self, web_request) -> Dict[str, Any]:
        args = web_request.get_args()
        action = str(args.get("action", ""))
        now = _epoch()
        if action == "save_task":
            raw = args.get("task")
            raw_id = str(raw.get("id", "")) if isinstance(raw, dict) else ""
            existing = next((item for item in self.service_state["tasks"] if item.get("id") == raw_id), None)
            task = self._validated_task(raw, existing)
            if existing is None:
                self.service_state["tasks"].append(task)
            else:
                existing.clear()
                existing.update(task)
        elif action == "delete_task":
            task = self._find_task(str(args.get("task_id", "")))
            self.service_state["tasks"].remove(task)
        elif action == "service_task":
            task = self._find_task(str(args.get("task_id", "")))
            before = self._task_status(task, now)
            self.service_state["history"].append({"type": "serviced", "task_id": task["id"], "task_name": task["name"], "at": now, "note": str(args.get("note", ""))[:1000], "metrics": before["metrics"]})
            task["serviced_at"] = now
            task["baseline"] = dict(self.service_state["counters"])
            task["snoozed_until"] = 0.0
            task["snooze_prints_until"] = 0.0
            task["updated_at"] = now
        elif action == "snooze":
            task = self._find_task(str(args.get("task_id", "")))
            mode = str(args.get("mode", "24h"))
            if mode == "next_print":
                task["snooze_prints_until"] = float(self.service_state["counters"]["prints"]) + 1.0
                task["snoozed_until"] = 0.0
            elif mode == "24h":
                task["snoozed_until"] = now + 86400
                task["snooze_prints_until"] = 0.0
            else:
                raise self.server.error("Unsupported snooze mode", 400)
        elif action == "reset_recommended":
            current = {item.get("id"): item for item in self.service_state["tasks"]}
            rebuilt = []
            for template in RECOMMENDED_TASKS:
                old = current.get(template["id"])
                fresh = _fresh_task(template, now, self.service_state["counters"])
                if old:
                    for key in ("serviced_at", "baseline", "snoozed_until", "snooze_prints_until"):
                        if key in old:
                            fresh[key] = old[key]
                rebuilt.append(fresh)
            self.service_state["tasks"] = rebuilt
            self.service_state["history"].append({"type": "recommended_reset", "at": now})
        elif action == "reset_counters":
            if str(args.get("confirmation", "")) != "RESET LIFETIME COUNTERS":
                raise self.server.error("Lifetime counter reset confirmation did not match", 400)
            await self._assert_idle()
            installed_profile = self._finalize_installed_usage()
            old = dict(self.service_state["counters"])
            self.service_state["counters"] = {key: 0.0 for key in COUNTER_KEYS}
            if installed_profile is not None:
                installed_profile["usage_baseline"] = {
                    key: 0.0 for key in TOOL_USAGE_KEYS
                }
                installed_profile["updated_at"] = now
                self._tool_history(
                    "counter_reset_checkpoint", installed_profile,
                    usage=installed_profile.get("usage", {}))
                self._tool_changed(save=True)
            for task in self.service_state["tasks"]:
                task["baseline"] = dict(self.service_state["counters"])
                task["serviced_at"] = now
            self.service_state["collector"] = {"boot_id": None, "xy_distance_mm": 0.0, "z_distance_mm": 0.0, "probe_cycles": 0.0}
            self.service_state["telemetry"] = {"job_key": "", "print_duration": 0.0, "filament_used": 0.0, "active": False}
            self.service_state["history"].append({"type": "counters_reset", "at": now, "previous": old})
        elif action == "import":
            payload = args.get("payload")
            if not isinstance(payload, dict) or not isinstance(payload.get("tasks"), list):
                raise self.server.error("Import must contain a tasks list", 400)
            incoming = payload["tasks"]
            replacing = bool(args.get("replace", False))
            if len(incoming) > MAX_SERVICE_TASKS or (not replacing and len(self.service_state["tasks"]) + len(incoming) > MAX_SERVICE_TASKS):
                raise self.server.error("Service Manager supports at most %d tasks" % MAX_SERVICE_TASKS, 400)
            imported = [self._validated_task(item) for item in incoming]
            if not replacing:
                used_ids = {str(item.get("id")) for item in self.service_state["tasks"]}
                for task in imported:
                    base_id = task["id"]
                    candidate = base_id
                    suffix = 2
                    while candidate in used_ids:
                        candidate = f"{base_id[:55]}-import-{suffix}"
                        suffix += 1
                    task["id"] = candidate
                    used_ids.add(candidate)
            self.service_state["tasks"] = imported if replacing else self.service_state["tasks"] + imported
            self.service_state["history"].append({"type": "import", "at": now, "count": len(imported)})
        elif action == "smart_settings":
            raw = args.get("settings")
            if not isinstance(raw, dict):
                raise self.server.error("Smart Maintenance settings must be an object", 400)
            enabled = bool(raw.get("enabled", False))
            try:
                lookback_days = int(raw.get("lookback_days", 90))
                min_events = int(raw.get("min_events", 3))
                max_advance = float(raw.get("max_advance_fraction", 0.25))
            except (TypeError, ValueError):
                raise self.server.error("Smart Maintenance settings must be numeric", 400)
            if not 1 <= lookback_days <= 3650:
                raise self.server.error("Smart lookback must be 1 to 3650 days", 400)
            if not 1 <= min_events <= 20:
                raise self.server.error("Smart evidence threshold must be 1 to 20 events", 400)
            if not math.isfinite(max_advance) or not 0.0 <= max_advance <= 0.5:
                raise self.server.error("Smart maximum advance must be between 0 and 0.5", 400)
            current = self.service_state.setdefault("smart", dict(SMART_DEFAULTS))
            current.update({
                "enabled": enabled,
                "lookback_days": lookback_days,
                "min_events": min_events,
                "max_advance_fraction": max_advance,
            })
        elif action == "reset_smart_estimates":
            if str(args.get("confirmation", "")) != "RESET SMART ESTIMATES":
                raise self.server.error("Smart estimate reset confirmation did not match", 400)
            self.service_state.setdefault("smart", dict(SMART_DEFAULTS))["reset_at"] = now
            self.service_state["history"].append({
                "type": "smart_estimates_reset", "at": now})
        else:
            raise self.server.error(f"Unsupported Service Manager action: {action}", 400)
        self._changed(save=True)
        self._record_event(
            "service", "service_" + re.sub(r"[^a-z0-9_.-]+", "_", action.lower()),
            "Service Manager action completed: %s" % action.replace("_", " "),
            source="klippertools.service",
            details={"action": action, "task_id": args.get("task_id")},
            save=True)
        return await self._handle_service_status(web_request)

    async def _handle_service_export(self, _web_request) -> Dict[str, Any]:
        return {
            "format": "klippertools-service",
            "schema": SERVICE_SCHEMA,
            "exported_at": _utc_now(),
            "tasks": self.service_state["tasks"],
            "history": self.service_state["history"],
            "smart": self.service_state.get("smart", SMART_DEFAULTS),
            "mechanism": self.service_state.get("mechanism", "unknown"),
        }

    async def _assert_idle(self) -> str:
        status = await self.klippy_apis.query_objects({"print_stats": ["state"]})
        state = str(status.get("print_stats", {}).get("state", "unknown")).lower()
        if state in ACTIVE_STATES:
            raise self.server.error(f"Klippertools updates are blocked while printer state is {state}", 409)
        if state not in {"standby", "complete", "cancelled", "error"}:
            raise self.server.error(f"Klippertools could not prove the printer is idle (state: {state})", 409)
        return state

    async def _handle_update(self, _web_request) -> Dict[str, Any]:
        if self.update_task is not None and not self.update_task.done():
            raise self.server.error("A Klippertools update is already running", 409)
        await self._assert_idle()
        updater = (self.repo_path / "scripts" / "update-online.sh").resolve()
        try:
            updater.relative_to(self.repo_path)
        except ValueError as exc:
            raise self.server.error("Unsafe Klippertools updater path", 500) from exc
        if not updater.is_file():
            raise self.server.error(f"Klippertools updater is missing: {updater}", 500)
        now = _utc_now()
        self.update_status = {"state": "downloading", "message": "Downloading and verifying update", "started_at": now, "finished_at": None, "restart_required": False}
        self._record_event(
            "update", "update_requested", "Klippertools update was requested",
            source="klippertools.updater", details={"installed_version": self._installed_version()}, save=True)
        self.update_task = asyncio.create_task(self._run_update(updater))
        return {"started": True, "started_at": now}

    async def _run_update(self, updater: Path) -> None:
        environment = os.environ.copy()
        environment["HOME"] = str(Path.home())
        try:
            process = await asyncio.create_subprocess_exec(str(updater), cwd=str(self.repo_path), env=environment, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            output, _unused = await process.communicate()
            message = output.decode("utf-8", errors="replace").strip()
            if process.returncode:
                self.update_status.update({"state": "error", "message": message[-4000:] or f"Updater exited {process.returncode}", "finished_at": _utc_now(), "restart_required": False})
                logging.error("Klippertools update failed: %s", message)
                self._record_event(
                    "update", "update_failed", "Klippertools update failed",
                    source="klippertools.updater", severity="error",
                    details={"exit_code": process.returncode, "message": message[-1000:]}, save=True)
                return
            self.update_status.update({"state": "complete", "message": "Update installed; restarting Klipper and Moonraker", "finished_at": _utc_now(), "restart_required": True})
            logging.info("Klippertools update completed: %s", message)
            self._record_event(
                "update", "update_completed", "Klippertools update installed successfully",
                source="klippertools.updater", details={"message": message[-1000:]}, save=True)
            await self._restart_services()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.exception("Klippertools update controller failed")
            self.update_status.update({"state": "error", "message": str(exc), "finished_at": _utc_now(), "restart_required": False})
            self._record_event(
                "update", "update_controller_error", "Klippertools update controller failed",
                source="klippertools.updater", severity="error",
                details={"error": str(exc)}, save=True)

    async def _restart_services(self) -> None:
        try:
            await self._assert_idle()
        except Exception:
            logging.warning("Klippertools update completed, but a print started before restart")
            self.update_status["message"] = "Update installed; restart Klipper and Moonraker manually after the print"
            return
        try:
            service_name = getattr(self.klippy_connection, "unit_name", "klipper")
            await self.machine.do_service_action("restart", service_name)
            self.eventloop.delay_callback(2.0, self.machine.restart_moonraker_service)
        except Exception:
            logging.exception("Klippertools installed but automatic service restart failed")
            self.update_status["message"] = "Update installed; restart Klipper and Moonraker manually"

    def close(self) -> None:
        if self._dirty:
            self._save_service_state()
        if self._tool_dirty:
            self._save_tool_state()
        if self._timeline_dirty:
            self._save_timeline_state()


def load_component(config):
    return Klippertools(config)
