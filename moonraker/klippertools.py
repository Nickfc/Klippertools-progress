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


SERVICE_SCHEMA = 1
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


# Conservative starting points for a rebuilt Ender 7.  They are editable
# inspection reminders, not manufacturer service guarantees.
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
        for path in (self.repo_path, self.state_path, self.service_data_path):
            try:
                path.relative_to(home)
            except ValueError as exc:
                raise config.error(f"Klippertools path must remain inside {home}: {path}") from exc

        self.service_state = self._load_service_state()
        self._dirty = False
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
        if hasattr(self.server, "register_notification"):
            self.server.register_notification("klippertools:service_changed")
        if hasattr(self.server, "register_event_handler"):
            self.server.register_event_handler("server:klippy_ready", self._handle_klippy_ready)
            self.server.register_event_handler("server:klippy_disconnect", self._handle_klippy_disconnect)
            self.server.register_event_handler("server:klippy_shutdown", self._handle_klippy_disconnect)
            self.server.register_event_handler("job_state:state_changed", self._handle_job_state_changed)

    async def component_init(self) -> None:
        if self.service_timer is not None:
            self.service_timer.start(delay=1.0)

    def _load_service_state(self) -> Dict[str, Any]:
        if not self.service_data_path.exists():
            return _default_state()
        try:
            value = json.loads(self.service_data_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or int(value.get("schema", 0)) != SERVICE_SCHEMA:
                raise ValueError("unsupported Service Manager data schema")
            counters = value.get("counters")
            if not isinstance(counters, dict):
                raise ValueError("missing counters")
            for key in COUNTER_KEYS:
                number = float(counters.get(key, 0.0))
                counters[key] = number if math.isfinite(number) and number >= 0 else 0.0
            if not isinstance(value.get("tasks"), list) or not isinstance(value.get("history"), list):
                raise ValueError("invalid tasks or history")
            value.setdefault("collector", {})
            value.setdefault("telemetry", {})
            return value
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            logging.exception("Unable to load Klippertools Service Manager data; preserving corrupt file")
            try:
                corrupt = self.service_data_path.with_name(self.service_data_path.name + ".corrupt-" + str(int(_epoch())))
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

    async def _handle_klippy_disconnect(self) -> None:
        self._printer_state = "disconnected"
        if self._dirty:
            self._save_service_state()

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

    def _reconcile_print(self, stats: Mapping[str, Any]) -> None:
        telemetry = self.service_state.setdefault("telemetry", {})
        state = str(stats.get("state", "unknown")).lower()
        self._printer_state = state
        filename = str(stats.get("filename", ""))
        current_duration = max(0.0, float(stats.get("print_duration", 0.0) or 0.0))
        current_filament = max(0.0, float(stats.get("filament_used", 0.0) or 0.0))
        active = state in ACTIVE_STATES
        same_job = filename and filename == telemetry.get("job_key")
        was_active = bool(telemetry.get("active", False))
        if active and (not was_active or not same_job):
            self.service_state["counters"]["prints"] += 1
            telemetry.update({"job_key": filename, "print_duration": current_duration, "filament_used": current_filament, "active": True})
            self._dirty = True
            return
        if same_job:
            duration_delta = max(0.0, current_duration - float(telemetry.get("print_duration", 0.0) or 0.0))
            filament_delta = max(0.0, current_filament - float(telemetry.get("filament_used", 0.0) or 0.0))
            if duration_delta or filament_delta:
                self.service_state["counters"]["print_time_s"] += duration_delta
                self.service_state["counters"]["filament_mm"] += filament_delta
                self._dirty = True
        telemetry.update({"job_key": filename, "print_duration": current_duration, "filament_used": current_filament, "active": active})

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

    def _task_status(self, task: Mapping[str, Any], now: float) -> Dict[str, Any]:
        metrics = [self._metric_status(task, item, now) for item in task.get("thresholds", []) if item.get("enabled", True) and str(item.get("metric", "")) in METRICS and float(item.get("limit", 0.0) or 0.0) > 0]
        progress = max((item["progress"] for item in metrics), default=0.0)
        state = "due" if progress >= 1.0 else "soon" if progress >= 0.8 else "good"
        estimated = [item["estimated_due"] for item in metrics if item["estimated_due"] is not None]
        snoozed = now < float(task.get("snoozed_until", 0.0) or 0.0) or float(self.service_state["counters"].get("prints", 0.0)) < float(task.get("snooze_prints_until", 0.0) or 0.0)
        result = json.loads(json.dumps(task))
        result.update({"metrics": metrics, "progress": progress, "state": state, "due": state == "due", "snoozed": snoozed, "estimated_due": min(estimated) if estimated else None})
        return result

    async def _handle_service_status(self, _web_request) -> Dict[str, Any]:
        now = _epoch()
        tasks = [self._task_status(task, now) for task in self.service_state["tasks"] if task.get("enabled", True)]
        tasks.sort(key=lambda item: (-float(item["progress"]), str(item["name"]).lower()))
        notifications = [task for task in tasks if task["due"] and not task["snoozed"] and self._printer_state not in ACTIVE_STATES]
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
        now = _epoch()
        base = dict(existing or {})
        base.update({"id": task_id, "name": name, "area": area, "instructions": instructions, "thresholds": thresholds, "enabled": bool(raw.get("enabled", True)), "recommended": bool(raw.get("recommended", False)), "updated_at": now})
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
            old = dict(self.service_state["counters"])
            self.service_state["counters"] = {key: 0.0 for key in COUNTER_KEYS}
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
            imported = [self._validated_task(item) for item in payload["tasks"]]
            if not bool(args.get("replace", False)):
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
            self.service_state["tasks"] = imported if bool(args.get("replace", False)) else self.service_state["tasks"] + imported
            self.service_state["history"].append({"type": "import", "at": now, "count": len(imported)})
        else:
            raise self.server.error(f"Unsupported Service Manager action: {action}", 400)
        self._changed(save=True)
        return await self._handle_service_status(web_request)

    async def _handle_service_export(self, _web_request) -> Dict[str, Any]:
        return {"format": "klippertools-service", "schema": SERVICE_SCHEMA, "exported_at": _utc_now(), "tasks": self.service_state["tasks"], "history": self.service_state["history"]}

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
                return
            self.update_status.update({"state": "complete", "message": "Update installed; restarting Klipper and Moonraker", "finished_at": _utc_now(), "restart_required": True})
            logging.info("Klippertools update completed: %s", message)
            await self._restart_services()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logging.exception("Klippertools update controller failed")
            self.update_status.update({"state": "error", "message": str(exc), "finished_at": _utc_now(), "restart_required": False})

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


def load_component(config):
    return Klippertools(config)
