import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from console import paths, prep

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
FIELDS = {"goal": "Fix add()", "where": "calc.py", "keep": "", "done_when": "tests pass",
          "last_decisions": "", "question": "which file?", "reason": "small",
          "route": {"type": "mechanical", "model": "sonnet", "effort": "low"}}


class PrepTest(unittest.TestCase):
    def test_format_prompt_skips_empty_fields(self):
        self.assertEqual(prep.format_prompt(FIELDS),
                         "Goal: Fix add()\nWhere: calc.py\nDone when: tests pass\nOpen question: which file?")

    def test_build_prompt_inserts_the_request(self):
        text = prep.build_prompt("  make $HOME {x} work  ")
        self.assertTrue(text.rstrip().endswith("Request:\nmake $HOME {x} work"))
        self.assertIn("| risky |", text)

    def test_parse_output(self):
        good = json.dumps({"is_error": False, "structured_output": FIELDS, "total_cost_usd": 0.03, "num_turns": 5})
        self.assertEqual(prep.parse_output(good)["fields"]["goal"], "Fix add()")
        for bad in ("nope", json.dumps({"is_error": True, "result": "boom"}), json.dumps({"result": "x"}),
                    json.dumps({"structured_output": dict(FIELDS, route={"model": "gpt", "effort": "low"})})):
            with self.assertRaises(prep.PrepError):
                prep.parse_output(bad)

    def test_run_prep_saves_the_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            card = prep.run_prep(cfg, Path(tmp), tmp, "fix the add function", FAKE)
            self.assertEqual(card["route"], {"type": "mechanical", "model": "sonnet", "effort": "low"})
            self.assertTrue(card["prompt"].startswith("Goal: Fix add() in calc.py\nWhere: calc.py:2"))
            self.assertEqual(prep.load(Path(tmp), card["id"])["raw"], "fix the add function")
            self.assertIsNone(prep.load(Path(tmp), "../x"))
            with self.assertRaises(prep.PrepError):
                prep.run_prep(cfg, Path(tmp), tmp, "BROKEN", FAKE)


if __name__ == "__main__":
    unittest.main()
