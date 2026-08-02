import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).parents[1] / "klipper" / "thermal_soak.py"
SPEC = importlib.util.spec_from_file_location("thermal_soak", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ThermalSoakModelTest(unittest.TestCase):
    def model(self, **overrides):
        model = MODULE.ThermalSoakModel()
        values = {
            "eventtime": 0,
            "sensor": "heater_bed",
            "target": 60,
            "window_seconds": 60,
            "max_wait_seconds": 600,
            "temperature_tolerance": 0.3,
            "slope_limit": 0.05,
            "range_limit": 0.5,
        }
        values.update(overrides)
        model.begin(**values)
        return model

    def test_heating_then_full_stable_window(self):
        model = self.model()
        for second in range(0, 121, 2):
            if second < 40:
                temperature = 20 + second
            else:
                temperature = 60.0 + 0.02 * ((second // 2) % 2)
            model.add_sample(second, temperature, 60)
        status = model.get_status(120)
        self.assertEqual(status["state"], "stable")
        self.assertEqual(status["progress"], 100)
        self.assertEqual(status["eta_seconds"], 0)

    def test_target_without_low_drift_is_not_stable(self):
        model = self.model()
        for second in range(0, 181, 2):
            model.add_sample(second, 59.8 + second * 0.002, 60)
        status = model.get_status(180)
        self.assertEqual(status["state"], "stabilizing")
        self.assertGreater(status["slope_c_per_min"], 0.05)

    def test_range_rejects_oscillation(self):
        model = self.model(slope_limit=5.0, range_limit=0.5)
        for second in range(0, 121, 2):
            model.add_sample(second, 59.6 if second % 4 else 60.4, 60)
        status = model.get_status(120)
        self.assertNotEqual(status["state"], "stable")
        self.assertGreater(status["range_c"], 0.5)

    def test_timeout_fails_closed(self):
        model = self.model(max_wait_seconds=120)
        for second in range(0, 122, 2):
            model.add_sample(second, 40, 60)
        status = model.get_status(122)
        self.assertEqual(status["state"], "timed_out")
        self.assertFalse(status["active"])

    def test_live_eta_and_completion_learning(self):
        model = self.model()
        for second in range(0, 31, 2):
            model.add_sample(second, 20 + second, 60)
        self.assertIsNotNone(model.get_status(30)["eta_seconds"])
        for second in range(32, 101, 2):
            model.add_sample(second, 60, 60)
        status = model.get_status(100)
        self.assertEqual(status["state"], "stable")
        self.assertIsNotNone(status["learned_duration_seconds"])

    def test_cancel_and_reset(self):
        model = self.model()
        model.add_sample(1, 25, 60)
        model.cancel(2)
        self.assertEqual(model.get_status(2)["state"], "canceled")
        model.reset()
        self.assertEqual(model.get_status(3)["state"], "idle")


if __name__ == "__main__":
    unittest.main()
