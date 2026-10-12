import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from console import paths, prep, tasks

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

    def test_schema_shape(self):
        self.assertEqual(set(prep.SCHEMA["required"]), set(FIELDS))
        self.assertEqual(set(prep.SCHEMA["properties"]), set(FIELDS) | {"steps"})
        route = prep.SCHEMA["properties"]["route"]
        self.assertEqual(route["type"], "object")
        self.assertEqual(set(route["required"]), {"type", "reasoning", "volume", "model", "effort"})
        steps = prep.SCHEMA["properties"]["steps"]  # optional: a one-step task leaves it empty
        self.assertNotIn("steps", prep.SCHEMA["required"])
        self.assertEqual(steps["type"], "array")
        self.assertEqual(set(steps["items"]["required"]), {"kind", "goal"})
        self.assertEqual(steps["items"]["properties"]["kind"]["enum"], list(tasks.PREP_KINDS))

    def test_prompt_demands_every_key(self):
        # Haiku sometimes left out `question` (nothing to ask) and `route` (flattened into the top level),
        # and the CLI then fails with error_max_structured_output_retries
        rules = prep.build_prompt("x").split("Output rules")[-1].split("Routing misses")[0]
        for key in prep.SCHEMA["required"]:
            self.assertIn(key, rules)
        self.assertIn('"question": ""', rules)
        self.assertIn("effort at the top level", rules)
        self.assertIn('"steps": []', rules)

    def test_parse_output(self):
        good = json.dumps({"is_error": False, "structured_output": FIELDS, "total_cost_usd": 0.03, "num_turns": 5})
        self.assertEqual(prep.parse_output(good)["fields"]["goal"], "Fix add()")
        for bad in ("nope", json.dumps({"is_error": True, "result": "boom"}), json.dumps({"result": "x"}),
                    json.dumps({"structured_output": dict(FIELDS, route={"model": "gpt", "effort": "low"})})):
            with self.assertRaises(prep.PrepError):
                prep.parse_output(bad)

    def test_error_result_names_the_cause(self):
        # `claude -p --max-turns 1` on a task that needs a tool: no `result`, the reason is in subtype + errors
        out = json.dumps({"is_error": True, "subtype": "error_max_turns", "terminal_reason": "max_turns",
                          "num_turns": 2, "errors": ["Reached maximum number of turns (1)"]})
        with self.assertRaises(prep.PrepError) as ctx:
            prep.parse_output(out)
        self.assertIn("error_max_turns", str(ctx.exception))
        self.assertIn("Reached maximum number of turns (1)", str(ctx.exception))
        with self.assertRaises(prep.PrepError) as ctx:
            prep.parse_output(json.dumps({"is_error": True, "result": "boom"}))
        self.assertIn("boom", str(ctx.exception))

    def test_run_prep_saves_the_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            card = prep.run_prep(cfg, Path(tmp), tmp, "fix the add function", FAKE)
            self.assertEqual(card["route"], {"type": "mechanical", "reasoning": "low", "volume": "low",
                                             "model": "sonnet", "effort": "low"})
            self.assertEqual(card["reason"], "one-line fix with a clear spec")
            self.assertEqual((card["model"], card["cost"], card["turns"]), ("haiku", 0.03, 5))
            self.assertTrue(card["prompt"].startswith("Goal: Fix add() in calc.py\nWhere: calc.py:2"))
            self.assertEqual(prep.load(Path(tmp), card["id"])["raw"], "fix the add function")
            self.assertIsNone(prep.load(Path(tmp), "../x"))
            with self.assertRaises(prep.PrepError):
                prep.run_prep(cfg, Path(tmp), tmp, "BROKEN", FAKE)
            same = prep.run_prep(cfg, Path(tmp), tmp, "fix it", FAKE, prep_id="20261012-101010-ab12")
            self.assertEqual(same["id"], "20261012-101010-ab12")  # the background job's id names the card
            self.assertEqual(prep.load(Path(tmp), same["id"])["raw"], "fix it")


    def test_run_prep_returns_steps_and_appends_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            card = prep.run_prep(cfg, Path(tmp), tmp, "CHAIN fix add", FAKE)
            self.assertEqual([s["kind"] for s in card["steps"]], ["scout", "code", "verify"])
            self.assertEqual([s["n"] for s in card["steps"]], [1, 2, 3])
            self.assertEqual(card["demand"], {"reasoning": "low", "volume": "low"})
            self.assertEqual(prep.load(Path(tmp), card["id"])["steps"], card["steps"])
            plain = prep.run_prep(cfg, Path(tmp), tmp, "fix the add function", FAKE)
            self.assertEqual(plain["steps"], [])

    def test_run_prep_routes_by_demand(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            card = prep.run_prep(cfg, Path(tmp), tmp, "THINK through the lock order", FAKE)
            self.assertEqual((card["route"]["model"], card["route"]["effort"]), ("opus", "high"))
            self.assertTrue(card["reason"].endswith("Demand rule: sonnet/low -> opus/high."))
            card = prep.run_prep(cfg, Path(tmp), tmp, "BULK rename in every file", FAKE)
            self.assertEqual((card["route"]["model"], card["route"]["effort"]), ("haiku", "low"))

    def test_card_carries_the_project_floors_for_the_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            self.assertEqual(prep.run_prep(cfg, Path(tmp), tmp, "fix the add function", FAKE)["floors"], {})
            name = Path(tmp).name
            (Path(tmp) / "routing-misses.md").write_text(
                f"- 2026-10-12 - {name} - code: sonnet/high failed (x); next time start at opus/high.\n", encoding="utf-8")
            card = prep.run_prep(cfg, Path(tmp), tmp, "fix the add function", FAKE)
            self.assertEqual(card["floors"], {"code": {"route": "opus/high", "date": "2026-10-12"}})
            self.assertEqual(prep.load(Path(tmp), card["id"])["floors"], card["floors"])

    def test_prompt_says_the_reason_is_for_one_run_not_for_the_steps(self):
        text = prep.build_prompt("fix it")
        self.assertIn("never say the task needs a model", text)
        self.assertIn("each step's model comes from its kind", text)


if __name__ == "__main__":
    unittest.main()
