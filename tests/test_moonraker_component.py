import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


class RequestType:
    GET = "GET"
    POST = "POST"


moonraker_package = types.ModuleType("moonraker")
moonraker_package.__path__ = []
components_package = types.ModuleType("moonraker.components")
components_package.__path__ = []
common_module = types.ModuleType("moonraker.common")
common_module.RequestType = RequestType
sys.modules.setdefault("moonraker", moonraker_package)
sys.modules.setdefault("moonraker.components", components_package)
sys.modules["moonraker.common"] = common_module

MODULE_PATH = Path(__file__).parents[1] / "moonraker" / "klippertools.py"
SPEC = importlib.util.spec_from_file_location(
    "moonraker.components.klippertools", MODULE_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ServerError(Exception):
    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.status_code = status_code


class FakeKlippyApis:
    def __init__(self, state="standby"):
        self.state = state
        self.gcodes = []

    async def query_objects(self, objects, default=None):
        result = {}
        if "print_stats" in objects:
            result["print_stats"] = {"state": self.state}
        if "configfile" in objects:
            result["configfile"] = {
                "settings": {"printer": {"kinematics": "corexy"}}
            }
        return result

    async def get_object_list(self, default=None):
        return ["print_stats", "extruder", "heater_bed", "service_metrics", "nozzle_guard"]

    async def run_gcode(self, script):
        self.gcodes.append(script)
        return "ok"


class FakeMachine:
    def __init__(self):
        self.actions = []
        self.moonraker_restarts = 0

    async def do_service_action(self, action, service):
        self.actions.append((action, service))

    async def restart_moonraker_service(self):
        self.moonraker_restarts += 1


class FakeEventLoop:
    def __init__(self):
        self.callbacks = []

    def delay_callback(self, delay, callback):
        self.callbacks.append((delay, callback))


class FakeServer:
    error = ServerError

    def __init__(self, state="standby"):
        self.klippy_apis = FakeKlippyApis(state)
        self.machine = FakeMachine()
        self.klippy_connection = types.SimpleNamespace(unit_name="klipper")
        self.eventloop = FakeEventLoop()
        self.endpoints = []

    def get_event_loop(self):
        return self.eventloop

    def lookup_component(self, name):
        return getattr(self, name)

    def register_endpoint(self, path, request_type, callback):
        self.endpoints.append((path, request_type, callback))


class FakeConfig:
    error = ServerError

    def __init__(self, server):
        self.server = server

    def get_server(self):
        return self.server

    def get(self, name, default):
        return default


class MoonrakerComponentTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="klippertools-component-")
        self.home = Path(self.temporary.name)
        (self.home / "klippertools" / "scripts").mkdir(parents=True)
        (self.home / "printer_data").mkdir()
        self.home_patch = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        self.home_patch.start()

    def tearDown(self):
        self.home_patch.stop()
        self.temporary.cleanup()

    def component(self, state="standby"):
        server = FakeServer(state)
        return MODULE.Klippertools(FakeConfig(server)), server

    def test_registers_update_and_service_endpoints(self):
        component, server = self.component()
        endpoints = [(path, method) for path, method, _callback in server.endpoints]
        self.assertEqual(
            endpoints,
            [
                ("/machine/klippertools/status", RequestType.GET),
                ("/machine/klippertools/update", RequestType.POST),
                ("/machine/klippertools/service/status", RequestType.GET),
                ("/machine/klippertools/service/action", RequestType.POST),
                ("/machine/klippertools/service/export", RequestType.GET),
                ("/machine/klippertools/tools/status", RequestType.GET),
                ("/machine/klippertools/tools/action", RequestType.POST),
                ("/machine/klippertools/tools/export", RequestType.GET),
                ("/machine/klippertools/timeline/status", RequestType.GET),
                ("/machine/klippertools/timeline/action", RequestType.POST),
                ("/machine/klippertools/timeline/export", RequestType.GET),
            ],
        )
        self.assertIsNone(component.update_task)

    def test_default_service_schedule_has_all_recommended_areas(self):
        component, _server = self.component()
        result = asyncio.run(component._handle_service_status(None))
        self.assertEqual(result["recommended_count"], 10)
        self.assertEqual(len(result["tasks"]), 10)
        self.assertEqual(result["counter_kind"]["xy_distance_mm"], "commanded")
        self.assertIn("probe_cycles", result["metrics"])

    def test_first_threshold_wins_and_service_resets_baseline(self):
        component, _server = self.component()
        task = component.service_state["tasks"][0]
        component.service_state["counters"]["print_time_s"] = 200 * 3600
        status = component._task_status(task, task["serviced_at"] + 1)
        self.assertTrue(status["due"])
        self.assertEqual(status["state"], "due")

        class Request:
            def get_args(self):
                return {"action": "service_task", "task_id": task["id"], "note": "done"}

        asyncio.run(component._handle_service_action(Request()))
        refreshed = component._task_status(task, task["serviced_at"])
        self.assertFalse(refreshed["due"])
        self.assertEqual(component.service_state["history"][-1]["type"], "serviced")

    def test_lifetime_reset_requires_exact_confirmation(self):
        component, _server = self.component()

        class Request:
            def get_args(self):
                return {"action": "reset_counters", "confirmation": "reset"}

        with self.assertRaises(ServerError) as caught:
            asyncio.run(component._handle_service_action(Request()))
        self.assertEqual(caught.exception.status_code, 400)

    def test_live_print_counters_reconcile_without_double_counting(self):
        component, _server = self.component()
        component._reconcile_print(
            {"state": "printing", "filename": "part.gcode", "print_duration": 10, "filament_used": 100}
        )
        self.assertEqual(component.service_state["counters"]["prints"], 1)
        # The first observation becomes the baseline, so installing mid-print
        # never invents earlier usage.
        self.assertEqual(component.service_state["counters"]["print_time_s"], 0)
        component._reconcile_print(
            {"state": "printing", "filename": "part.gcode", "print_duration": 25, "filament_used": 160}
        )
        component._reconcile_print(
            {"state": "complete", "filename": "part.gcode", "print_duration": 30, "filament_used": 180}
        )
        self.assertEqual(component.service_state["counters"]["prints"], 1)
        self.assertEqual(component.service_state["counters"]["print_time_s"], 20)
        self.assertEqual(component.service_state["counters"]["filament_mm"], 80)

    def test_collector_reconciles_boot_local_deltas(self):
        component, _server = self.component()
        component._reconcile_collector(
            {"boot_id": "a", "xy_distance_mm": 100, "z_distance_mm": 10, "probe_cycles": 2}
        )
        self.assertEqual(component.service_state["counters"]["xy_distance_mm"], 0)
        component._reconcile_collector(
            {"boot_id": "a", "xy_distance_mm": 140, "z_distance_mm": 13, "probe_cycles": 5}
        )
        self.assertEqual(component.service_state["counters"]["xy_distance_mm"], 40)
        self.assertEqual(component.service_state["counters"]["z_distance_mm"], 3)
        self.assertEqual(component.service_state["counters"]["probe_cycles"], 3)
        component._reconcile_collector(
            {"boot_id": "b", "xy_distance_mm": 4, "z_distance_mm": 1, "probe_cycles": 1}
        )
        self.assertEqual(component.service_state["counters"]["xy_distance_mm"], 40)

    def test_service_schema_one_migrates_without_losing_history_or_counters(self):
        legacy = MODULE._default_state()
        legacy["schema"] = 1
        legacy.pop("smart", None)
        legacy.pop("mechanism", None)
        legacy["counters"]["prints"] = 42
        legacy["history"].append({"type": "serviced", "at": 1})
        for task in legacy["tasks"]:
            task.pop("smart_signals", None)
        path = self.home / "printer_data" / "klippertools-service.json"
        path.write_text(__import__("json").dumps(legacy), encoding="utf-8")
        component, _server = self.component()
        self.assertEqual(component.service_state["schema"], MODULE.SERVICE_SCHEMA)
        self.assertEqual(component.service_state["counters"]["prints"], 42)
        self.assertEqual(component.service_state["history"][0]["type"], "serviced")
        self.assertIn("smart_signals", component.service_state["tasks"][0])

    def test_smart_maintenance_is_advisory_and_disabled_by_default(self):
        component, _server = self.component()
        task = component.service_state["tasks"][0]
        for index in range(4):
            component._record_event(
                "warning", "motion_calibration_error", "Motion issue",
                source="test", severity="error", save=False)
        before_thresholds = __import__("copy").deepcopy(task["thresholds"])
        before_baseline = dict(task["baseline"])
        status = component._task_status(task, task["serviced_at"] + 10)
        self.assertEqual(status["smart"]["state"], "disabled")
        self.assertFalse(status["smart"]["smart_due"])
        self.assertEqual(task["thresholds"], before_thresholds)
        self.assertEqual(task["baseline"], before_baseline)

    def test_smart_maintenance_explains_earlier_review_when_enabled(self):
        component, _server = self.component()
        task = component.service_state["tasks"][0]
        component.service_state["smart"].update({
            "enabled": True, "min_events": 3,
            "lookback_days": 90, "max_advance_fraction": 0.25,
        })
        # Put the base threshold at 80%; three error events produce a capped
        # 24% advance and therefore an explainable earlier review.
        component.service_state["counters"]["print_time_s"] = 160 * 3600
        now = task["serviced_at"] + 100
        with mock.patch.object(MODULE, "_epoch", return_value=now):
            for _index in range(3):
                component._record_event(
                    "warning", "motion_calibration_error", "Motion issue",
                    source="test", severity="error", save=False)
        before_thresholds = __import__("copy").deepcopy(task["thresholds"])
        before_baseline = dict(task["baseline"])
        status = component._task_status(task, now)
        self.assertEqual(status["smart"]["state"], "suggestion")
        self.assertEqual(status["smart"]["confidence"], "low")
        self.assertTrue(status["smart"]["smart_due"])
        self.assertTrue(status["due"])
        self.assertIn("intervals and baselines are unchanged", status["smart"]["reason"])
        self.assertEqual(task["thresholds"], before_thresholds)
        self.assertEqual(task["baseline"], before_baseline)

    def test_reset_smart_estimates_does_not_reset_lifetime_data(self):
        component, _server = self.component()
        component.service_state["counters"]["prints"] = 17
        baseline = dict(component.service_state["tasks"][0]["baseline"])

        class Request:
            def get_args(self):
                return {
                    "action": "reset_smart_estimates",
                    "confirmation": "RESET SMART ESTIMATES",
                }

        asyncio.run(component._handle_service_action(Request()))
        self.assertEqual(component.service_state["counters"]["prints"], 17)
        self.assertEqual(component.service_state["tasks"][0]["baseline"], baseline)
        self.assertGreater(component.service_state["smart"]["reset_at"], 0)

    def test_detected_corexy_exposes_only_a_matching_preset(self):
        component, _server = self.component()
        asyncio.run(component._detect_printer_mechanism())
        status = asyncio.run(component._handle_service_status(None))
        self.assertEqual(status["mechanism"], "corexy")
        self.assertEqual(status["mechanism_preset"]["label"], "CoreXY motion system")

    def test_timeline_records_print_transitions_without_gcode_contents(self):
        component, _server = self.component()
        component._reconcile_print({
            "state": "printing", "filename": "private/project.gcode",
            "print_duration": 0, "filament_used": 0,
        })
        component._reconcile_print({
            "state": "complete", "filename": "private/project.gcode",
            "print_duration": 120, "filament_used": 800,
        })
        events = component.timeline_state["events"]
        self.assertEqual(events[-2]["type"], "print_started")
        self.assertEqual(events[-1]["type"], "print_completed")
        payload = str(events)
        self.assertNotIn("G1 ", payload)
        self.assertEqual(events[-1]["details"]["print_duration"], 120)

    def test_timeline_records_only_save_config_command_name(self):
        component, _server = self.component()
        asyncio.run(component._handle_gcode_received(
            "SAVE_CONFIG ; sensitive comment\nG1 X100 Y100"))
        event = component.timeline_state["events"][-1]
        self.assertEqual(event["type"], "save_config_requested")
        self.assertEqual(event["details"], {"command": "SAVE_CONFIG"})
        self.assertNotIn("X100", str(event))

    def test_timeline_filters_and_bounded_retention(self):
        component, _server = self.component()
        component.timeline_state["event_limit"] = 100
        for index in range(130):
            component._record_event(
                "warning" if index % 2 else "print",
                "event_%d" % index, "Fact %d" % index,
                source="test", save=False)
        component._save_timeline_state()
        self.assertEqual(len(component.timeline_state["events"]), 100)

        class Request:
            def get_args(self):
                return {"category": "warning", "limit": 10}

        status = asyncio.run(component._handle_timeline_status(Request()))
        self.assertEqual(len(status["events"]), 10)
        self.assertTrue(all(event["category"] == "warning" for event in status["events"]))

    def test_timeline_clear_requires_strong_confirmation(self):
        component, _server = self.component()
        component._record_event("system", "test", "Test", source="test")

        class Request:
            def get_args(self):
                return {"action": "clear", "confirmation": "clear"}

        with self.assertRaises(ServerError) as caught:
            asyncio.run(component._handle_timeline_action(Request()))
        self.assertEqual(caught.exception.status_code, 400)

    def test_tool_registry_install_syncs_nozzle_guard_without_config_write(self):
        component, server = self.component()

        class SaveRequest:
            def get_args(self):
                return {
                    "action": "save_profile",
                    "profile": {
                        "id": "hardened-08",
                        "name": "Hardened 0.8",
                        "diameter": 0.8,
                        "material": "hardened steel",
                        "max_temp": 450,
                    },
                }

        asyncio.run(component._handle_tool_action(SaveRequest()))
        self.assertTrue(component.tool_data_path.is_file())

        class InstallRequest:
            def get_args(self):
                return {"action": "install_profile", "profile_id": "hardened-08"}

        status = asyncio.run(component._handle_tool_action(InstallRequest()))
        self.assertEqual(status["installed_profile_id"], "hardened-08")
        self.assertIn("NOZZLE_GUARD_SET_TOOL DIAMETER=0.800000", server.klippy_apis.gcodes[-1])
        self.assertFalse((self.home / "printer_data" / "config" / "printer.cfg").exists())

    def test_tool_registry_import_preserves_bounded_usage_without_installing(self):
        component, _server = self.component()

        class Request:
            def get_args(self):
                return {
                    "action": "import",
                    "payload": {
                        "profiles": [{
                            "id": "imported-06",
                            "name": "Imported 0.6",
                            "diameter": 0.6,
                            "usage_total": {
                                "filament_mm": 1234,
                                "print_time_s": 600,
                                "prints": 4,
                                "hotend_heater_s": 800,
                            },
                            "installed": True,
                        }]
                    },
                }

        status = asyncio.run(component._handle_tool_action(Request()))
        self.assertIsNone(status["installed_profile_id"])
        profile = status["profiles"][0]
        self.assertFalse(profile["installed"])
        self.assertEqual(profile["usage_total"]["filament_mm"], 1234)
        self.assertEqual(profile["usage_total"]["prints"], 4)

    def test_tool_registry_clear_returns_to_klipper_reference(self):
        component, server = self.component()
        profile = component._validated_profile({
            "id": "brass-04", "name": "Brass 0.4", "diameter": 0.4
        })
        component.tool_state["profiles"].append(profile)
        component.tool_state["installed_profile_id"] = profile["id"]
        profile["usage_baseline"] = dict(component.service_state["counters"])

        class Request:
            def get_args(self):
                return {"action": "clear_installed"}

        status = asyncio.run(component._handle_tool_action(Request()))
        self.assertIsNone(status["installed_profile_id"])
        self.assertEqual(server.klippy_apis.gcodes[-1], "NOZZLE_GUARD_CLEAR_TOOL")

    def test_installed_tool_cannot_be_retired_or_deleted(self):
        component, _server = self.component()
        profile = component._validated_profile({
            "id": "brass-04", "name": "Brass 0.4", "diameter": 0.4
        })
        component.tool_state["profiles"].append(profile)
        component.tool_state["installed_profile_id"] = profile["id"]

        class RetireRequest:
            def get_args(self):
                return {"action": "retire_profile", "profile_id": "brass-04"}

        with self.assertRaises(ServerError) as caught:
            asyncio.run(component._handle_tool_action(RetireRequest()))
        self.assertEqual(caught.exception.status_code, 409)

    def test_tool_usage_is_accumulated_when_removed(self):
        component, _server = self.component()
        profile = component._validated_profile({
            "id": "brass-04", "name": "Brass 0.4", "diameter": 0.4
        })
        component.tool_state["profiles"].append(profile)
        component.tool_state["installed_profile_id"] = profile["id"]
        profile["usage_baseline"] = dict(component.service_state["counters"])
        component.service_state["counters"]["filament_mm"] = 1250
        component.service_state["counters"]["print_time_s"] = 600
        finalized = component._finalize_installed_usage()
        self.assertEqual(finalized["usage"]["filament_mm"], 1250)
        self.assertEqual(finalized["usage"]["print_time_s"], 600)
        self.assertIsNone(finalized["usage_baseline"])


    def test_corrupt_tool_registry_profile_is_preserved_and_reset_safely(self):
        path = self.home / "printer_data" / "klippertools-tools.json"
        path.write_text(__import__("json").dumps({
            "schema": MODULE.TOOL_SCHEMA,
            "profiles": [{
                "id": "bad-04", "name": "Bad", "diameter": 0.4,
                "usage": "not-an-object",
            }],
            "history": [],
            "installed_profile_id": "bad-04",
        }), encoding="utf-8")
        component, _server = self.component()
        self.assertEqual(component.tool_state["profiles"], [])
        self.assertIsNone(component.tool_state["installed_profile_id"])
        preserved = list(path.parent.glob(path.name + ".corrupt-*"))
        self.assertEqual(len(preserved), 1)

    def test_counter_reset_preserves_installed_tool_usage(self):
        component, _server = self.component()
        profile = component._validated_profile({
            "id": "brass-04", "name": "Brass 0.4", "diameter": 0.4
        })
        component.tool_state["profiles"].append(profile)
        component.tool_state["installed_profile_id"] = profile["id"]
        profile["usage_baseline"] = dict(component.service_state["counters"])
        component.service_state["counters"]["filament_mm"] = 2500
        component.service_state["counters"]["print_time_s"] = 900

        class Request:
            def get_args(self):
                return {
                    "action": "reset_counters",
                    "confirmation": "RESET LIFETIME COUNTERS",
                }

        asyncio.run(component._handle_service_action(Request()))
        self.assertEqual(profile["usage"]["filament_mm"], 2500)
        self.assertEqual(profile["usage"]["print_time_s"], 900)
        self.assertEqual(profile["usage_baseline"]["filament_mm"], 0)
        self.assertEqual(component.service_state["counters"]["filament_mm"], 0)
        component.service_state["counters"]["filament_mm"] = 100
        self.assertEqual(component._profile_usage(profile)["filament_mm"], 2600)

    def test_timeline_rejects_non_finite_time_filters(self):
        component, _server = self.component()

        class Request:
            def get_args(self):
                return {"start_at": "nan"}

        with self.assertRaises(ServerError) as caught:
            asyncio.run(component._handle_timeline_status(Request()))
        self.assertEqual(caught.exception.status_code, 400)

    def test_idle_guard_blocks_printing_and_paused(self):
        for state in ("printing", "paused"):
            component, _server = self.component(state)
            with self.assertRaises(ServerError) as caught:
                asyncio.run(component._assert_idle())
            self.assertEqual(caught.exception.status_code, 409)

    def test_restart_rechecks_idle_after_deployment(self):
        component, server = self.component("printing")
        asyncio.run(component._restart_services())
        self.assertEqual(server.machine.actions, [])
        self.assertIn("after the print", component.update_status["message"])


if __name__ == "__main__":
    unittest.main()
