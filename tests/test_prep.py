import copy
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

from console import paths, prep, tasks

def _step(kind, goal):
    return tasks.plan_steps([{"kind": kind, "goal": goal}], 6)[0]


FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
FIELDS = {"goal": "Fix add()", "where": "calc.py", "keep": "", "done_when": "tests pass",
          "last_decisions": "", "question": "which file?", "reason": "small", "scouting": "",
          "route": {"type": "mechanical", "model": "sonnet", "effort": "low"}}


class PrepTest(unittest.TestCase):
    def test_format_prompt_skips_empty_fields(self):
        self.assertEqual(prep.format_prompt(FIELDS),
                         "Goal: Fix add()\nWhere: calc.py\nDone when: tests pass\nOpen question: which file?")

    def test_build_prompt_inserts_the_request(self):
        text = prep.build_prompt("  make $HOME {x} work  ")
        self.assertTrue(text.rstrip().endswith("Request:\nmake $HOME {x} work"))
        self.assertIn("The user typed the request at the end", text)  # plan 31
        self.assertIn("Fred typed the request at the end", prep.build_prompt("x", you="Fred"))
        self.assertIn("| risky |", text)

    def test_schema_shape(self):
        # only goal and route are required: Haiku dropped the other keys on long answers and resent the same
        # object on every retry (troubleshooting/prep-structured-output.md); route comes first so it is written
        # before the long text
        self.assertEqual(set(prep.SCHEMA["required"]), {"goal", "route"})
        self.assertEqual(set(prep.SCHEMA["properties"]), set(FIELDS) | {"steps"})
        self.assertEqual(next(iter(prep.SCHEMA["properties"])), "route")
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
        for key in prep.SCHEMA["properties"]:
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

    def test_parse_output_fills_missing_text_fields(self):
        short = {"goal": "Fix add()", "route": FIELDS["route"]}
        fields = prep.parse_output(json.dumps({"structured_output": short}))["fields"]
        for key, _label in prep.LABELS:
            self.assertEqual(fields[key], "" if key != "goal" else "Fix add()")
        self.assertEqual(fields["reason"], "")

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
            where = Path(tmp) / "tasks" / same["id"] / "00-prep"  # plan 29: the card lives in its task folder
            self.assertEqual(sorted(p.name for p in where.iterdir()),
                             ["handoff.md", "prep.json", "prompt.md", "role.md", "scouting.md"])
            self.assertTrue((where / "role.md").read_text(encoding="utf-8").startswith("# prep\n\nYou are a prompt"))
            self.assertIn("Request:\nfix it", (where / "role.md").read_text(encoding="utf-8"))
            self.assertEqual((where / "scouting.md").read_text(encoding="utf-8"),
                             "calc.py:2 add(): the function to fix\ntests/test_calc.py test_add: the test that covers it\n")
            self.assertFalse((Path(tmp) / "preps").exists())

    # -- plan 29: the prompt's task folder, 00-prep/ ---------------------------------------------------------

    def test_a_card_from_before_plan_29_still_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "preps").mkdir()
            (Path(tmp) / "preps" / "20261001-101010-ab12.json").write_text('{"id": "20261001-101010-ab12", "raw": "old"}',
                                                                          encoding="utf-8")
            self.assertEqual(prep.load(Path(tmp), "20261001-101010-ab12")["raw"], "old")

    def test_handoff_text_is_six_headings_from_the_card(self):
        card = {"id": "20261015-101010-ab12", "raw": "fix add", "route": {"model": "sonnet", "effort": "low"},
                "fields": {"goal": "Fix add()  in\ncalc.py", "scouting": "calc.py:2 add(): to fix", "question": "ints?"},
                "steps": [{"kind": "scout", "goal": "find callers"}]}
        text = prep.handoff_text(card)
        self.assertEqual(tasks.check_handoff(text), "")
        self.assertEqual(text, "## Goal\nFix add() in calc.py\n## Findings\ncalc.py:2 add(): to fix\n## Files touched\n"
                               "- (none)\n## Troubleshooting\n- (none)\n## Open questions\n- ints?\n## Next\nfind callers\n")
        self.assertTrue(prep.handoff_text(card, "fix it now").endswith("## Next\nfix it now\n"))
        bare = prep.handoff_text(dict(card, steps=[], fields={"goal": "x"}))
        self.assertIn("## Findings\n(Prep read nothing)\n", bare)
        self.assertTrue(bare.endswith("## Next\nOne chat on sonnet/low does the whole request.\n"))

    def test_first_handoff_cuts_the_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = {"id": "20261015-101010-ab12", "fields": {"goal": "g", "scouting": "x" * 2000}, "steps": [],
                    "route": {}}
            prep.save(tmp, card)
            text = prep.first_handoff(tmp, {"id": card["id"]})
            findings = text.split("## Findings\n")[1].split("\n## Files touched")[0]
            self.assertEqual(len(findings), prep.FINDINGS_CUT)
            self.assertTrue(findings.endswith("\u2026"))
            self.assertEqual(tasks.check_handoff(text), "")
            self.assertEqual(prep.first_handoff(tmp, {"id": "20261015-101010-ffff"}), "")

    def test_begin_discard_and_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            prep.begin(tmp, "20261015-101010-ab12", "  fix add\n")
            where = Path(tmp) / "tasks" / "20261015-101010-ab12"
            self.assertEqual((where / "prompt.md").read_text(encoding="utf-8"), "fix add\n")
            self.assertTrue(prep.discard(tmp, "20261015-101010-ab12"))
            self.assertFalse(where.exists())
            prep.begin(tmp, "20261015-101010-cd34", "run me")
            (Path(tmp) / "tasks" / "20261015-101010-cd34" / "task.json").write_text("{}", encoding="utf-8")
            self.assertFalse(prep.discard(tmp, "20261015-101010-cd34"))  # a task: never removed here
            self.assertFalse(prep.discard(tmp, "../x"))
            prep.begin(tmp, "20261015-101010-ef56", "lost card")
            now = time.time()
            self.assertEqual(prep.prune_orphans(tmp, now=now), [])  # younger than ORPHAN_DAYS
            self.assertEqual(prep.prune_orphans(tmp, now=now + 3 * 86400), ["20261015-101010-ef56"])
            self.assertTrue((Path(tmp) / "tasks" / "20261015-101010-cd34").exists())

    def test_summary_is_step_0(self):
        card = {"id": "20261015-101010-ab12", "model": "haiku", "turns": 5, "cost": 0.03, "reason": "small",
                "route": {"type": "lookup"}, "fields": {"question": ""}, "steps": [_step("scout", "look")]}
        self.assertEqual(prep.summary(card), {"id": card["id"], "state": "done", "model": "haiku", "turns": 5,
                                              "cost": 0.03, "route": {"type": "lookup"}, "reason": "small",
                                              "question": "", "steps": [{"kind": "scout", "goal": "look"}]})
        self.assertEqual(prep.summary(None), {"id": "", "state": "skipped"})
        self.assertEqual(tasks.prep_id({"prep": prep.summary(card)}), card["id"])
        self.assertEqual(tasks.prep_id({"prep": "20261001-101010-ab12"}), "20261001-101010-ab12")


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

    def test_planner_steps_replace_prep_steps(self):
        """Plan 47: the planner's list is the card's; Prep's own steps are only its evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            card = prep.run_prep(cfg, Path(tmp), tmp, "CHAIN PLANNER-DESIGN fix add", FAKE)
            self.assertEqual([s["kind"] for s in card["steps"]], ["scout", "design", "code", "verify"])
            self.assertEqual([s["n"] for s in card["steps"]], [1, 2, 3, 4])
            self.assertEqual((card["planner"]["scope"], card["planner"]["error"], card["planner"]["model"]),
                             ("ok", "", cfg["planner_model"]))
            self.assertEqual(card["planner"]["turns"], 4)
            self.assertIn("fake planner", card["planner"]["note"])
            self.assertEqual(prep.load(Path(tmp), card["id"])["planner"], card["planner"])
            big = prep.run_prep(cfg, Path(tmp), tmp, "CHAIN PLANNER-BIG fix add", FAKE)
            self.assertEqual((big["planner"]["scope"], [s["kind"] for s in big["steps"]]),
                             ("too_big", ["scout", "code", "verify"]))

    def test_planner_failure_keeps_prep_steps(self):
        """Plan 47 D5: any planner failure keeps Prep's steps through plan_steps and shows the error on the card."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            for word in ("PLANNER-FAIL", "PLANNER-NOJSON"):
                card = prep.run_prep(cfg, Path(tmp), tmp, f"CHAIN {word} fix add", FAKE)
                self.assertEqual([s["kind"] for s in card["steps"]], ["scout", "code", "verify"], word)
                self.assertNotEqual(card["planner"]["error"], "", word)
            self.assertEqual(card["planner"]["scope"], "")
            card = prep.run_prep(cfg, Path(tmp), tmp, "THINK PLANNER-FAIL through the lock order", FAKE)
            self.assertEqual(card["steps"], [])  # a hard card whose planner failed has only Prep's list
            self.assertNotEqual(card["planner"]["error"], "")

    def test_planner_design_step_is_kept_and_not_doubled(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            card = prep.run_prep(cfg, Path(tmp), tmp, "THINK CHAIN PLANNER-DESIGN fix add", FAKE)
            self.assertEqual([s["kind"] for s in card["steps"]], ["scout", "design", "code", "verify"])
            self.assertEqual(sum(s["kind"] == "design" for s in card["steps"]), 1)
            self.assertEqual(card["demand"]["reasoning"], "high")

    def test_planner_cost_is_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            card = prep.run_prep(cfg, Path(tmp), tmp, "CHAIN fix add", FAKE)
            self.assertAlmostEqual(card["cost"], 0.03 + 0.02)  # Prep's 0.03 plus the fake planner's 0.02
            self.assertAlmostEqual(card["planner"]["cost"], 0.02)
            self.assertEqual(card["turns"], 5)  # Prep's own turns; the planner's sit in card["planner"]
            failed = prep.run_prep(cfg, Path(tmp), tmp, "CHAIN PLANNER-FAIL fix add", FAKE)
            self.assertAlmostEqual(failed["cost"], 0.03 + 0.02)  # a failed pass still cost its turns
            broken = prep.run_prep(cfg, Path(tmp), tmp, "CHAIN PLANNER-NOJSON fix add", FAKE)
            self.assertAlmostEqual(broken["cost"], 0.03)  # no envelope, no cost known

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

    def test_build_prompt_names_the_miss_window(self):
        self.assertIn("Routing misses in this project in the last 14 days (Escalate wrote them; newest last):\n(none)",
                      prep.build_prompt("x", days=14))
        self.assertIn("Routing misses in this project (Escalate wrote them; newest last):", prep.build_prompt("x"))

    def test_run_prep_reads_only_fresh_misses(self):
        from console import levers, routing
        with tempfile.TemporaryDirectory() as tmp:
            folder, project = Path(tmp) / "home", Path(tmp) / "proj"
            project.mkdir()
            old = "- 2020-01-01 - proj - mechanical: sonnet/low failed (x); next time start at opus/high."
            levers.add_miss(folder, old)
            cfg = dict(copy.deepcopy(paths.DEFAULTS), miss_floor_days=14)
            card = prep.run_prep(cfg, folder, str(project), "fix add", FAKE)
            self.assertEqual((card["route"]["model"], card["route"]["effort"]), ("sonnet", "low"))  # no floor
            self.assertEqual(card["floors"], {})
            card = prep.run_prep(dict(cfg, miss_floor_days=0), folder, str(project), "fix add", FAKE)
            self.assertEqual(card["floors"], {"mechanical": {"route": "opus/high", "date": "2020-01-01"}})
            self.assertEqual((card["route"]["model"], card["route"]["effort"]), ("opus", "high"))


if __name__ == "__main__":
    unittest.main()
