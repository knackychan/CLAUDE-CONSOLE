"""Plan 24 config keys in paths.DEFAULTS and the opus_max_turns fallback."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import paths


class PlanKeysTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": self.tmp})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_design_max_turns_replaces_the_opus_cap(self):
        cfg = paths.load_config()
        self.assertEqual((cfg["design_max_turns"], cfg["plan_max_kb"], cfg["plan_max_parts"]), (30, 100, 6))
        self.assertIs(cfg["plan_hold"], False)
        self.assertIs(cfg["replan_auto"], False)
        self.assertNotIn("opus_max_turns", cfg)
        (Path(self.tmp) / "config.json").write_text(json.dumps({"opus_max_turns": 15}), encoding="utf-8")
        cfg = paths.load_config()
        self.assertEqual(cfg["design_max_turns"], 15)
        self.assertNotIn("opus_max_turns", cfg)
        (Path(self.tmp) / "config.json").write_text(
            json.dumps({"opus_max_turns": 15, "design_max_turns": 40}), encoding="utf-8")
        self.assertEqual(paths.load_config()["design_max_turns"], 40)



class SettingTest(unittest.TestCase):
    def test_plan_23_defaults(self):
        d = paths.DEFAULTS
        self.assertEqual((d["read_max_turns"], d["handoff_auto"]), (15, False))
        self.assertEqual(paths.SETTINGS, ("handoff_auto",))

    def test_set_setting_writes_one_key(self):
        with tempfile.TemporaryDirectory() as folder:
            paths.set_setting(Path(folder), "handoff_auto", True)  # no config.json yet: the defaults plus the key
            data = json.loads((Path(folder) / "config.json").read_text(encoding="utf-8"))
            self.assertIs(data["handoff_auto"], True)
            self.assertEqual(data["brief_max_words"], paths.DEFAULTS["brief_max_words"])
            data["projects"] = ["C:/x"]
            (Path(folder) / "config.json").write_text(json.dumps(data), encoding="utf-8")
            paths.set_setting(Path(folder), "handoff_auto", False)
            data = json.loads((Path(folder) / "config.json").read_text(encoding="utf-8"))
            self.assertEqual((data["handoff_auto"], data["projects"]), (False, ["C:/x"]))  # the rest stays
            self.assertFalse((Path(folder) / "config.json.tmp").exists())
            for key, value in (("brief_on", False), ("handoff_auto", "yes"), ("handoff_auto", 1)):
                with self.assertRaises(ValueError):
                    paths.set_setting(Path(folder), key, value)
            (Path(folder) / "config.json").write_text("{broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                paths.set_setting(Path(folder), "handoff_auto", True)
            self.assertEqual((Path(folder) / "config.json").read_text(encoding="utf-8"), "{broken")  # left as is


if __name__ == "__main__":
    unittest.main()
