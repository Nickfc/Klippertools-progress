import importlib.util
from pathlib import Path
import types
import unittest


MODULE_PATH = Path(__file__).parents[1] / "klipper" / "service_metrics.py"
SPEC = importlib.util.spec_from_file_location("service_metrics", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeReactor:
    def monotonic(self):
        return 12.5


class FakeToolhead:
    def __init__(self):
        self.position = [0.0, 0.0, 0.0, 0.0]

    def get_position(self):
        return list(self.position)

    def move(self, newpos, _speed):
        self.position = list(newpos)


class FakePrinter:
    def __init__(self):
        self.reactor = FakeReactor()
        self.toolhead = FakeToolhead()
        self.handlers = {}

    def get_reactor(self):
        return self.reactor

    def register_event_handler(self, name, callback):
        self.handlers[name] = callback

    def lookup_object(self, name):
        self.assert_name = name
        return self.toolhead


class ServiceMetricsTest(unittest.TestCase):
    def test_tracks_commanded_xy_z_and_probe_touches(self):
        printer = FakePrinter()
        config = types.SimpleNamespace(get_printer=lambda: printer)
        metrics = MODULE.ServiceMetrics(config)
        metrics._handle_ready()
        printer.toolhead.move([3.0, 4.0, 2.0, 0.0], 100.0)
        printer.toolhead.move([6.0, 8.0, 1.5, 0.0], 100.0)
        metrics._handle_probe_result([0.0, 0.0, 0.1])
        status = metrics.get_status(0.0)
        self.assertEqual(status["xy_distance_mm"], 10.0)
        self.assertEqual(status["z_distance_mm"], 2.5)
        self.assertEqual(status["probe_cycles"], 1)
        self.assertEqual(status["distance_kind"], "commanded")


if __name__ == "__main__":
    unittest.main()
