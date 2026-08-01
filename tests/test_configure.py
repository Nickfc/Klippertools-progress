import importlib.util
import pathlib
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "scripts" / "configure.py"
)
SPEC = importlib.util.spec_from_file_location("configure", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConfigureTest(unittest.TestCase):
    def test_adds_after_mainsail_include(self):
        original = (
            "[include mainsail.cfg]\n"
            "[mcu]\n"
            "serial: /dev/example\n"
        )
        updated, changed = MODULE.add_include(original)
        self.assertTrue(changed)
        self.assertIn(
            "[include mainsail.cfg]\n"
            "\n"
            "# Added by Klipper Probe Progress\n"
            "[include probe_progress.cfg]\n"
            "\n"
            "[mcu]",
            updated,
        )

    def test_add_is_idempotent(self):
        original = (
            "[include mainsail.cfg]\n"
            "[include probe_progress.cfg]\n"
        )
        updated, changed = MODULE.add_include(original)
        self.assertFalse(changed)
        self.assertEqual(updated, original)

    def test_adds_before_save_config(self):
        original = (
            "[mcu]\n"
            "serial: /dev/example\n"
            "\n"
            "#*# <---------------------- SAVE_CONFIG "
            "---------------------->\n"
        )
        updated, changed = MODULE.add_include(original)
        self.assertTrue(changed)
        self.assertLess(
            updated.index("[include probe_progress.cfg]"),
            updated.index("SAVE_CONFIG"),
        )

    def test_remove_keeps_unrelated_configuration(self):
        original = (
            "[include mainsail.cfg]\n"
            "\n"
            "# Added by Klipper Probe Progress\n"
            "[include probe_progress.cfg]\n"
            "\n"
            "[mcu]\n"
            "serial: /dev/example\n"
        )
        updated, changed = MODULE.remove_include(original)
        self.assertTrue(changed)
        self.assertNotIn("probe_progress", updated)
        self.assertIn("[include mainsail.cfg]", updated)
        self.assertIn("serial: /dev/example", updated)


if __name__ == "__main__":
    unittest.main()
