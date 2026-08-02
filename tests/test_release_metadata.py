import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.8.0"
BACKENDS = (
    "probe_progress.py",
    "nozzle_guard.py",
    "start_flow.py",
    "motion_wizard.py",
    "service_metrics.py",
    "thermal_soak.py",
    "calibration_center.py",
)


def assigned_string(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


class ReleaseMetadataTest(unittest.TestCase):
    def test_all_runtime_versions_match_manifest(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(EXPECTED_VERSION, manifest["version"])
        self.assertEqual(
            EXPECTED_VERSION,
            assigned_string(ROOT / "scripts" / "lifecycle.py", "VERSION"),
        )
        for backend in BACKENDS:
            with self.subTest(backend=backend):
                self.assertEqual(
                    EXPECTED_VERSION,
                    assigned_string(ROOT / "klipper" / backend, "PLUGIN_VERSION"),
                )

    def test_required_optional_components_are_declared(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        components = set(manifest["components"])
        self.assertTrue(
            {
                "calibration-center",
                "nozzle-tool-registry",
                "printer-health-timeline",
                "smart-maintenance",
            }.issubset(components)
        )

    def test_persistent_paths_are_outside_checkout(self):
        moonraker_conf = (ROOT / "config" / "klippertools-moonraker.conf").read_text(
            encoding="utf-8"
        )
        for name in (
            "klippertools-service.json",
            "klippertools-tools.json",
            "klippertools-timeline.json",
        ):
            self.assertIn(f"~/printer_data/{name}", moonraker_conf)
            self.assertNotIn(f"~/klippertools/{name}", moonraker_conf)

    def test_klipper_config_enables_calibration_center(self):
        config = (ROOT / "config" / "klippertools.cfg").read_text(encoding="utf-8")
        self.assertRegex(config, r"(?m)^\[calibration_center\]$")

    def test_build_script_targets_supported_mainsail_versions(self):
        script = (ROOT / "scripts" / "build-mainsail-v0.8.0.sh").read_text(
            encoding="utf-8"
        )
        versions = set(re.findall(r"v2\.\d+\.\d+", script))
        self.assertEqual({"v2.17.0", "v2.18.2"}, versions)


if __name__ == "__main__":
    unittest.main()
