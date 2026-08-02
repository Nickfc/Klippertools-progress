import importlib.util
import pathlib
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "klipper" / "calibration_center.py"
)
SPEC = importlib.util.spec_from_file_location("calibration_center", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CalibrationCenter = MODULE.CalibrationCenter


class FakeReactor:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now


class FakeObject:
    def __init__(self, status=None):
        self.status = status or {}

    def get_status(self, eventtime):
        return self.status


class FakeGcode:
    def __init__(self, commands):
        self.commands = {command: {} for command in commands}
        self.scripts = []

    def get_status(self, eventtime):
        return {"commands": self.commands}

    def run_script_from_command(self, script):
        self.scripts.append(script)


class FakePrinter:
    command_error = RuntimeError

    def __init__(self, objects):
        self.objects = objects

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)


class FakeGcmd:
    def __init__(self, params):
        self.params = {key.upper(): str(value) for key, value in params.items()}
        self.responses = []

    @staticmethod
    def error(message):
        return RuntimeError(message)

    def get(self, name, default=...):
        if name in self.params:
            return self.params[name]
        if default is ...:
            raise RuntimeError("missing %s" % name)
        return default

    def get_float(self, name, default=..., minval=None, maxval=None,
                  above=None, below=None):
        raw = self.get(name, default)
        if raw is default:
            return raw
        value = float(raw)
        if minval is not None and value < minval:
            raise RuntimeError("minimum")
        if maxval is not None and value > maxval:
            raise RuntimeError("maximum")
        if above is not None and value <= above:
            raise RuntimeError("above")
        if below is not None and value >= below:
            raise RuntimeError("below")
        return value

    def respond_info(self, message):
        self.responses.append(message)


class CalibrationCenterTest(unittest.TestCase):
    def make_center(self, print_state="standby", homed="xyz",
                    commands=None, extra_objects=None):
        if commands is None:
            commands = {
                "PID_CALIBRATE", "BED_MESH_CALIBRATE", "PROBE_CALIBRATE",
                "Z_ENDSTOP_CALIBRATE", "SHAPER_CALIBRATE", "TUNING_TOWER",
                "SET_PRESSURE_ADVANCE", "ABORT",
            }
        gcode = FakeGcode(commands)
        settings = {
            "extruder": {
                "min_temp": 0.0,
                "max_temp": 300.0,
                "rotation_distance": 4.8,
            },
            "heater_bed": {"min_temp": 0.0, "max_temp": 130.0},
            "probe": {"z_offset": 0.2},
            "stepper_z": {"position_endstop": 0.0},
            "input_shaper": {
                "shaper_type_x": "mzv", "shaper_freq_x": 40.0,
                "shaper_type_y": "ei", "shaper_freq_y": 35.0,
            },
        }
        objects = {
            "gcode": gcode,
            "bed_mesh": FakeObject({"profile_name": "default"}),
            "configfile": FakeObject({
                "settings": settings,
                "save_config_pending": False,
                "save_config_pending_items": {},
            }),
            "extruder": FakeObject({"pressure_advance": 0.04}),
            "heaters": FakeObject({
                "available_heaters": ["extruder", "heater_bed"]}),
            "heater_bed": FakeObject({"temperature": 24.0, "target": 0.0}),
            "input_shaper": FakeObject(),
            "manual_probe": FakeObject({"is_active": False}),
            "pause_resume": FakeObject({"is_paused": False}),
            "print_stats": FakeObject({"state": print_state}),
            "probe": FakeObject(),
            "resonance_tester": FakeObject(),
            "toolhead": FakeObject({"homed_axes": homed}),
        }
        if extra_objects:
            objects.update(extra_objects)
        center = CalibrationCenter.__new__(CalibrationCenter)
        center.printer = FakePrinter(objects)
        center.reactor = FakeReactor()
        center.gcode = gcode
        center.objects = objects.copy()
        center.available_commands = set(commands)
        center.ready = True
        center.state = "idle"
        center.phase = "ready"
        center.active_flow = None
        center.message = "Choose a calibration workflow"
        center.error = None
        center.started_at = None
        center.finished_at = None
        center.session_id = 0
        center.last_result = None
        center.last_command = None
        return center, gcode

    def test_catalog_disables_missing_hardware(self):
        center, _ = self.make_center(commands={"PID_CALIBRATE"})
        center.objects["resonance_tester"] = None
        availability = center._flow_availability("input_shaper")
        self.assertFalse(availability["available"])
        self.assertIn("SHAPER_CALIBRATE", availability["reason"])

    def test_refuses_to_start_during_print(self):
        center, _ = self.make_center(print_state="printing")
        with self.assertRaisesRegex(RuntimeError, "print is active"):
            center.cmd_CALIBRATION_CENTER_START(FakeGcmd({
                "FLOW": "first_layer", "CONFIRM": "YES"}))

    def test_refuses_to_start_while_pause_resume_is_paused(self):
        center, _ = self.make_center()
        center.objects["pause_resume"] = FakeObject({"is_paused": True})
        with self.assertRaisesRegex(RuntimeError, "print is active"):
            center.cmd_CALIBRATION_CENTER_START(FakeGcmd({
                "FLOW": "first_layer", "CONFIRM": "YES"}))

    def test_requires_explicit_confirmation(self):
        center, _ = self.make_center()
        with self.assertRaisesRegex(RuntimeError, "CONFIRM=YES"):
            center.cmd_CALIBRATION_CENTER_START(FakeGcmd({
                "FLOW": "first_layer"}))

    def test_motion_workflow_requires_xyz_homing(self):
        center, _ = self.make_center(homed="xy")
        with self.assertRaisesRegex(RuntimeError, "Home X, Y, and Z"):
            center.cmd_CALIBRATION_CENTER_START(FakeGcmd({
                "FLOW": "bed_mesh", "CONFIRM": "YES"}))

    def test_pid_uses_configured_heater_limits(self):
        center, gcode = self.make_center()
        center.cmd_CALIBRATION_CENTER_START(FakeGcmd({
            "FLOW": "pid", "CONFIRM": "YES",
            "HEATER": "heater_bed", "TARGET": 100,
        }))
        self.assertEqual(
            gcode.scripts[-1],
            "PID_CALIBRATE HEATER=heater_bed TARGET=100.000")
        self.assertEqual(center.state, "review")
        self.assertNotIn("SAVE_CONFIG", "\n".join(gcode.scripts))

        center.state = "idle"
        center.active_flow = None
        with self.assertRaisesRegex(RuntimeError, "configured min/max"):
            center.cmd_CALIBRATION_CENTER_START(FakeGcmd({
                "FLOW": "pid", "CONFIRM": "YES",
                "HEATER": "heater_bed", "TARGET": 150,
            }))

    def test_z_offset_prefers_probe_calibrate(self):
        center, gcode = self.make_center()
        center.cmd_CALIBRATION_CENTER_START(FakeGcmd({
            "FLOW": "z_offset", "CONFIRM": "YES"}))
        self.assertEqual(gcode.scripts[-1], "PROBE_CALIBRATE")
        self.assertNotIn("SAVE_CONFIG", "\n".join(gcode.scripts))

    def test_pressure_advance_requires_user_values(self):
        center, gcode = self.make_center()
        center.cmd_CALIBRATION_CENTER_START(FakeGcmd({
            "FLOW": "pressure_advance", "CONFIRM": "YES",
            "START": 0, "FACTOR": 0.005,
        }))
        expected = (
            "TUNING_TOWER COMMAND=SET_PRESSURE_ADVANCE "
            "PARAMETER=ADVANCE START=0.000000 FACTOR=0.005000")
        self.assertEqual(center.last_command, expected)
        self.assertEqual(center.last_result["command_preview"], expected)
        self.assertEqual(gcode.scripts, [])
        self.assertEqual(center.state, "guided")

    def test_rotation_distance_is_calculation_only(self):
        center, gcode = self.make_center()
        center.cmd_CALIBRATION_CENTER_ROTATION_DISTANCE(FakeGcmd({
            "CONFIRM": "YES", "PREVIOUS": 4.8,
            "REQUESTED": 100, "ACTUAL": 97,
        }))
        self.assertEqual(
            center.last_result["rotation_distance"], 4.656)
        self.assertEqual(gcode.scripts, [])
        self.assertIn("no configuration was changed", center.message)

    def test_status_exposes_prerequisites_and_current_values(self):
        center, _ = self.make_center()
        status = center.get_status(5.0)
        self.assertTrue(status["flows"]["pid"]["available"])
        self.assertEqual(status["current_values"]["rotation_distance"], 4.8)
        self.assertEqual(status["current_values"]["pressure_advance"], 0.04)
        self.assertFalse(status["automatic_save"])
        self.assertEqual(status["homed_axes"], "xyz")
        self.assertEqual(status["printer_state"], "standby")
        self.assertEqual(status["current_values"]["heaters"][1]["max_temp"], 130.0)
        self.assertEqual(status["current_values"]["heaters"][1]["temperature"], 24.0)


if __name__ == "__main__":
    unittest.main()
