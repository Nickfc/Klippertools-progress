import importlib.util
import pathlib
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "klipper" / "start_flow.py"
)
SPEC = importlib.util.spec_from_file_location("start_flow", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
StartFlowModel = MODULE.StartFlowModel


class FakeReactor:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class StartFlowModelTest(unittest.TestCase):
    def setUp(self):
        self.reactor = FakeReactor()
        self.model = StartFlowModel(
            self.reactor,
            estimates={"bed_heat": 100, "homing": 20, "mesh": 60},
            learning_rate=0.5,
        )

    def test_tracks_stages_and_eta(self):
        self.model.begin(["bed_heat", "homing", "mesh"])
        self.model.stage("bed_heat")
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["eta_seconds"], 180)
        self.assertEqual(status["current_stage"], "bed_heat")

        self.reactor.advance(80)
        self.model.stage("homing")
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["completed_stages"], 1)
        self.assertEqual(status["progress"], 33.3)
        self.assertEqual(status["stages"][0]["duration_seconds"], 80.0)

    def test_refines_estimate_from_completed_stage(self):
        self.model.begin(["bed_heat"])
        self.model.stage("bed_heat")
        self.reactor.advance(80)
        self.model.complete()
        self.assertEqual(self.model.estimates["bed_heat"], 90.0)
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["state"], "complete")
        self.assertEqual(status["progress"], 100.0)
        self.assertEqual(status["eta_seconds"], 0)

    def test_command_error_marks_active_stage(self):
        self.model.begin(["mesh"])
        self.model.stage("mesh")
        self.reactor.advance(3)
        self.model.fail("Probe failed")
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["state"], "error")
        self.assertEqual(status["stages"][0]["state"], "error")
        self.assertEqual(status["error"], "Probe failed")

    def test_custom_stage_is_added_safely(self):
        self.model.begin(["homing"])
        self.model.stage("homing")
        self.reactor.advance(2)
        self.model.stage("gantry_level", "Gantry level")
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["total_stages"], 2)
        self.assertEqual(status["current_stage"], "gantry_level")
        self.assertEqual(status["stages"][1]["label"], "Gantry level")


if __name__ == "__main__":
    unittest.main()
