import importlib.util
import pathlib
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "scripts" / "instrument_print_start.py"
)
SPEC = importlib.util.spec_from_file_location(
    "instrument_print_start", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


SAMPLE = """[include mainsail.cfg]

[gcode_macro PRINT_START]
description: Example
gcode:
    {% set BED = params.BED|default(60)|float %}
    M140 S{BED}
    M104 S150
    M190 S{BED}
    G28
    BED_MESH_CLEAR
    BED_MESH_CALIBRATE PROFILE=print
    M109 S210
    G92 E0
    G1 X10 Y10
    RESPOND MSG="Print start complete"

[gcode_macro PRINT_END]
gcode:
    M104 S0
"""


class InstrumentPrintStartTest(unittest.TestCase):
    def test_adds_all_stages_in_execution_order(self):
        updated, changed = MODULE.add_instrumentation(SAMPLE)
        self.assertTrue(changed)
        positions = [
            updated.index("START_FLOW_BEGIN"),
            updated.index("START_FLOW_STAGE NAME=bed_heat"),
            updated.index("START_FLOW_STAGE NAME=homing"),
            updated.index("START_FLOW_STAGE NAME=mesh"),
            updated.index("START_FLOW_STAGE NAME=nozzle_heat"),
            updated.index("START_FLOW_STAGE NAME=purge"),
            updated.index("START_FLOW_COMPLETE"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(
            updated.index("START_FLOW_STAGE NAME=bed_heat"),
            updated.index("M140 S{BED}"),
        )
        self.assertGreater(
            updated.index("START_FLOW_STAGE NAME=purge"),
            updated.index("M109 S210"),
        )

    def test_add_is_idempotent(self):
        updated, _ = MODULE.add_instrumentation(SAMPLE)
        second, changed = MODULE.add_instrumentation(updated)
        self.assertFalse(changed)
        self.assertEqual(second, updated)

    def test_remove_restores_exact_input(self):
        updated, _ = MODULE.add_instrumentation(SAMPLE)
        restored, changed = MODULE.remove_instrumentation(updated)
        self.assertTrue(changed)
        self.assertEqual(restored, SAMPLE)

    def test_unsupported_macro_is_not_partially_changed(self):
        unsupported = SAMPLE.replace("    G28\n", "")
        with self.assertRaises(MODULE.InstrumentationError):
            MODULE.add_instrumentation(unsupported)
        self.assertNotIn("START_FLOW", unsupported)


if __name__ == "__main__":
    unittest.main()
