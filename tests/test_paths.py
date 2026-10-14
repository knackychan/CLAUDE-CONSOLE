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


if __name__ == "__main__":
    unittest.main()
