import importlib.util
import pathlib
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "klipper" / "probe_progress.py"
)
SPEC = importlib.util.spec_from_file_location("probe_progress", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ProbeProgressModel = MODULE.ProbeProgressModel
ProbeProgress = MODULE.ProbeProgress


class FakeReactor:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def rectangular_points(columns, rows):
    points = []
    for row in range(rows):
        values = range(columns) if row % 2 == 0 \
            else range(columns - 1, -1, -1)
        for column in values:
            points.append((float(column * 10), float(row * 10)))
    return points


def direct_path(points):
    return [(point[0], point[1], index)
            for index, point in enumerate(points)]


class ProbeProgressModelTest(unittest.TestCase):
    def setUp(self):
        self.reactor = FakeReactor()
        self.model = ProbeProgressModel(self.reactor)

    def start(self, columns=3, rows=3, samples=3, tolerance=0.025,
              retries=5):
        points = rectangular_points(columns, rows)
        self.model.start(
            points, direct_path(points), rows, columns,
            samples, tolerance, retries)
        return points

    def complete_current_point(self, point, seconds=2.0,
                               z_values=(0.0, 0.01, 0.005)):
        self.reactor.advance(seconds)
        for z_value in z_values:
            self.assertTrue(self.model.accept_result(
                point[0], point[1], z_value))

    def test_matrix_uses_physical_orientation(self):
        points = self.start()
        status = self.model.get_status(self.reactor.monotonic())
        cells = status["matrix"]["cells"]
        # The first physical point is front-left and therefore bottom-left.
        self.assertEqual((cells[0]["row"], cells[0]["column"]), (2, 0))
        # Serpentine point four is middle-right.
        self.assertEqual((cells[3]["row"], cells[3]["column"]), (1, 2))
        self.assertEqual(points[3], (20.0, 10.0))

    def test_cell_is_green_only_after_all_samples(self):
        points = self.start()
        self.reactor.advance(1)
        self.model.accept_result(points[0][0], points[0][1], 0.0)
        self.model.accept_result(points[0][0], points[0][1], 0.01)
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["matrix"]["cells"][0]["state"], "active")
        self.assertEqual(status["completed_points"], 0)

        self.model.accept_result(points[0][0], points[0][1], 0.005)
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["matrix"]["cells"][0]["state"], "done")
        self.assertEqual(status["matrix"]["cells"][1]["state"], "active")
        self.assertEqual(status["completed_points"], 1)

    def test_retry_keeps_cell_active_and_resets_sample_count(self):
        points = self.start()
        self.model.accept_result(points[0][0], points[0][1], 0.0)
        self.model.accept_result(points[0][0], points[0][1], 0.05)
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["current_retry"], 1)
        self.assertEqual(status["current_sample"], 1)
        self.assertEqual(status["matrix"]["cells"][0]["state"], "active")

        for z_value in (0.0, 0.01, 0.005):
            self.model.accept_result(points[0][0], points[0][1], z_value)
        self.assertEqual(self.model.completed_points, 1)

    def test_eta_is_seeded_from_first_three_logical_points(self):
        points = self.start()
        for point in points[:3]:
            self.complete_current_point(point, seconds=2.0)
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["eta_sampled_points"], 3)
        self.assertEqual(status["eta_seconds"], 12)
        self.assertEqual(status["progress"], 33.3)

        self.reactor.advance(5)
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["eta_seconds"], 7)

    def test_faulty_region_substitutes_share_one_matrix_cell(self):
        points = rectangular_points(3, 3)
        path = [
            (0.0, 1.0, 0),
            (1.0, 0.0, 0),
        ] + [(point[0], point[1], index)
             for index, point in enumerate(points[1:], start=1)]
        self.model.start(points, path, 3, 3, 1, 0.025, 0)
        self.model.accept_result(0.0, 1.0, 0.0)
        self.assertEqual(self.model.cells[0]["state"], "active")
        self.assertEqual(self.model.completed_points, 0)
        self.model.accept_result(1.0, 0.0, 0.0)
        self.assertEqual(self.model.cells[0]["state"], "done")
        self.assertEqual(self.model.completed_points, 1)

    def test_unexpected_coordinate_does_not_advance(self):
        self.start()
        self.assertFalse(self.model.accept_result(99, 99, 0.0))
        self.assertEqual(self.model.physical_index, 0)
        self.assertEqual(self.model.completed_points, 0)

    def test_failure_preserves_current_cell(self):
        self.start()
        self.model.fail("Probe timeout")
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["state"], "error")
        self.assertEqual(status["matrix"]["cells"][0]["state"], "active")
        self.assertEqual(status["error"], "Probe timeout")

    def test_authoritative_completion_recovers_a_missed_event(self):
        self.start()
        self.model.complete()
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["state"], "complete")
        self.assertEqual(status["progress"], 100.0)
        self.assertTrue(all(
            cell["state"] == "done"
            for cell in status["matrix"]["cells"]))

    def test_seven_by_seven_three_sample_mesh_counts_147_touches(self):
        points = self.start(columns=7, rows=7)
        for point in points:
            for z_value in (0.0, 0.01, 0.005):
                self.model.accept_result(point[0], point[1], z_value)
        self.model.complete()
        status = self.model.get_status(self.reactor.monotonic())
        self.assertEqual(status["total_points"], 49)
        self.assertEqual(status["completed_points"], 49)
        self.assertEqual(status["planned_touches"], 147)
        self.assertEqual(status["touches_completed"], 147)
        self.assertEqual(status["progress"], 100.0)


class ProbeProgressIntegrationTest(unittest.TestCase):
    def test_uses_klippers_tolerance_retry_parameter_name(self):
        calibration = {
            "points": [(10.0, 20.0)],
            "probe_path": [(10.0, 20.0)],
            "config": {"x_count": 1, "y_count": 1},
        }

        class ProbeManager:
            def get_substitutes(self):
                return {}

        class BedMeshController:
            probe_mgr = ProbeManager()

            def dump_calibration(self):
                return calibration

        class BedMesh:
            bmc = BedMeshController()

        class Probe:
            def get_probe_params(self, gcmd):
                return {
                    "samples": 3,
                    "samples_tolerance": 0.025,
                    "samples_tolerance_retries": 5,
                }

        class Gcmd:
            def get(self, name, default=None):
                return default

        class Model:
            def __init__(self):
                self.arguments = None
                self.completed = False

            def start(self, *arguments):
                self.arguments = arguments

            def complete(self):
                self.completed = True

            def fail(self, message):
                self.fail_message = message

        progress = ProbeProgress.__new__(ProbeProgress)
        progress.bed_mesh = BedMesh()
        progress.probe = Probe()
        progress.model = Model()
        progress.printer = type(
            "Printer", (), {"command_error": RuntimeError}
        )()
        progress.original_start_probe = lambda gcmd: "complete"

        result = progress._start_bed_mesh_probe(Gcmd())
        self.assertEqual(result, "complete")
        self.assertEqual(progress.model.arguments[6], 5)
        self.assertTrue(progress.model.completed)


if __name__ == "__main__":
    unittest.main()
