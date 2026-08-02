import re
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = (
    ROOT / "source" / "mainsail-v2.17.0-klippertools-source.zip",
    ROOT / "source" / "mainsail-v2.18.2-klippertools-source.zip",
)
PANEL_RE = re.compile(r"^\s*'(tool-registry|health-timeline)',\s*$", re.MULTILINE)


class DashboardLayoutHotfixTest(unittest.TestCase):
    def test_source_archives_have_unique_intentional_entries_and_self_heal(self):
        for archive in ARCHIVES:
            with self.subTest(archive=archive.name), zipfile.ZipFile(archive) as source:
                getters = source.read("src/store/gui/getters.ts").decode("utf-8")
                names = PANEL_RE.findall(getters)
                self.assertEqual(2, names.count("tool-registry"))
                self.assertEqual(2, names.count("health-timeline"))
                self.assertIn("v0.8.1 self-heal", getters)
                self.assertIn("const seenPanelNames = new Set<string>()", getters)

    def test_current_patch_aliases_do_not_repeat_dashboard_panel_runs(self):
        for version in ("v2.17.0", "v2.18.2"):
            patch = (ROOT / "mainsail" / f"mainsail-{version}.patch").read_text(encoding="utf-8")
            self.assertNotRegex(
                patch,
                r"(?:\+\s*'tool-registry',\n\+\s*'health-timeline',\n){2,}",
            )
            self.assertIn("seenPanelNames", patch)


if __name__ == "__main__":
    unittest.main()
