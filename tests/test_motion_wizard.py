import importlib.util
import pathlib
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "klipper" / "motion_wizard.py"
)
SPEC = importlib.util.spec_from_file_location("motion_wizard", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MotionWizard = MODULE.MotionWizard


class FakeReactor:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now


class FakeParams:
    def __init__(self, shaper_type, frequency):
        self.shaper_type = shaper_type
        self.frequency = frequency

    def get_status(self):
        return {
            "shaper_type": self.shaper_type,
            "shaper_freq": "%.3f" % self.frequency,
            "damping_ratio": "0.100000",
        }


class FakeShaper:
    def __init__(self, axis, shaper_type, frequency):
        self.axis = axis
        self.params = FakeParams(shaper_type, frequency)


class MotionWizardStatusTest(unittest.TestCase):
    def make_wizard(self):
        wizard = MotionWizard.__new__(MotionWizard)
        wizard.reactor = FakeReactor()
        wizard.state = "review"
        wizard.phase = "review"
        wizard.message = "Review"
        wizard.error = None
        wizard.completed_axes = {"x"}
        wizard.noise_complete = True
        wizard.pending_save = True
        wizard.started_at = 0.0
        wizard.finished_at = None
        wizard.session_id = 1
        wizard.ready = True
        wizard.toolhead = type("Toolhead", (), {
            "get_status": lambda self, eventtime: {"homed_axes": "xyz"}
        })()
        wizard.input_shaper = type("InputShaper", (), {
            "get_shapers": lambda self: [
                FakeShaper("x", "3hump_ei", 81.4),
                FakeShaper("y", "mzv", 37.2),
            ]
        })()
        return wizard

    def test_exposes_reviewable_axis_results(self):
        wizard = self.make_wizard()
        status = wizard.get_status(12.0)
        self.assertEqual(status["results"]["x"]["type"], "3hump_ei")
        self.assertEqual(status["results"]["x"]["frequency"], 81.4)
        self.assertTrue(status["results"]["x"]["calibrated"])
        self.assertFalse(status["results"]["y"]["calibrated"])
        self.assertTrue(status["pending_save"])

    def test_requires_all_axes_homed(self):
        wizard = self.make_wizard()
        wizard.toolhead = type("Toolhead", (), {
            "get_status": lambda self, eventtime: {"homed_axes": "xy"}
        })()

        class Gcmd:
            @staticmethod
            def error(message):
                return RuntimeError(message)

        with self.assertRaisesRegex(RuntimeError, "Home X, Y, and Z"):
            wizard._assert_homed(Gcmd())


if __name__ == "__main__":
    unittest.main()
