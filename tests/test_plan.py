"""Plan 24: the design step's plan (console/plan.py): parse, check, split, files, answers, prompt parts."""
import os
import tempfile
import unittest

from console import plan, tasks

STEP = """### Step {n}: code
#### Files
- calc.py
#### Actions
1. `def add(a: int, b: int) -> int` in calc.py.
#### Tests
- tests/test_calc.py::test_add asserts add(1, 2) == 3
#### Done check
py -m unittest tests.test_calc -q prints OK
"""
INDEX = """# Plan: calc
## Goal
add() in calc.py; done when the test passes.
## Decisions
- add lives in calc.py: the only module.
## Out of scope
- sub()
## Files
- calc.py (change): add()
## Steps
{steps}
## Acceptance
- tests/test_calc.py passes
"""
PART = """## Files
- {f}
## Actions
1. write {f}
## Tests
- tests/test_{f}.py::test_it
## Done check
py -m unittest -q
"""
SPLIT_INDEX = """# Plan: calc
## Goal
two modules.
## Decisions
- one part per module.
## Out of scope
- (none)
## Sub-plans
| # | Part | Kind | Owns | Depends on | Hard |
|---|---|---|---|---|---|
| 1 | Calc module | code | calc.py | - | no |
| 2 | Report module | code | report.py, calc.py | 1 | yes |
## Acceptance
- both suites pass
"""


def single(n=2):
    return "thinking...\nPLAN\n" + INDEX.format(steps=STEP.format(n=n)) + "END PLAN\nHANDOFF\n## Findings\nx\nEND HANDOFF"


def split():
    return ("PLAN\n" + SPLIT_INDEX + "END PLAN\n" + "SUBPLAN 1 code Calc module\n" + PART.format(f="calc.py")
            + "END SUBPLAN\n**SUBPLAN 2 code Report module**\n" + PART.format(f="report.py") + "END SUBPLAN\n"
            "HANDOFF\n## Findings\nx\nEND HANDOFF")


def make_task(kinds=("scout", "design", "code", "test", "verify", "document")):
    steps = [tasks._blank(i + 1, k, f"step {k}") for i, k in enumerate(kinds)]
    for s in steps:
        if s["kind"] == "verify":
            s["checked"] = 3
    return tasks.new_task("D:/x", "x", "calc", "Goal: add()", steps, "normal", {"reasoning": "low", "volume": "low"},
                          "", "auto", now=1.0)


class ParseTest(unittest.TestCase):
    def test_parse_takes_the_last_plan_block_and_the_parts_after_it(self):
        p = plan.parse("PLAN\nold\nEND PLAN\n" + split())
        self.assertIn("## Sub-plans", p["index"])
        self.assertEqual([x["n"] for x in p["parts"]], [1, 2])
        self.assertEqual(p["parts"][1]["title"], "Report module")
        self.assertTrue(p["parts"][0]["text"].startswith("## Files"))
        self.assertIsNone(plan.parse("no plan here"))

    def test_section_and_step_section(self):
        idx = INDEX.format(steps=STEP.format(n=3) + STEP.format(n=5))
        self.assertEqual(plan.section(idx, "## Out of scope"), "- sub()")
        self.assertTrue(plan.step_section(idx, 5).startswith("### Step 5: code"))
        self.assertNotIn("Step 3", plan.step_section(idx, 5))
        self.assertEqual(plan.step_section(idx, 9), "")

    def test_table_reads_the_sub_plans_rows(self):
        rows = plan.table(SPLIT_INDEX)
        self.assertEqual(rows[1], {"n": 2, "title": "Report module", "kind": "code", "owns": ["report.py", "calc.py"],
                                   "depends": [1], "hard": True})
        self.assertEqual(rows[0]["depends"], [])

    def test_gap_finds_the_plan_gap_line(self):
        block = "## Findings\nx\n## Open questions\n- **Plan gap:** config.json or models.json?\n## Next\ngo"
        self.assertEqual(plan.gap(block), "config.json or models.json?")
        self.assertEqual(plan.gap("## Open questions\n- (none)"), "")


class CheckTest(unittest.TestCase):
    def later(self, t, n=2):
        return [s for s in t["steps"] if s["n"] > n]

    def test_check_passes_a_whole_single_plan(self):
        t = make_task()
        p = plan.parse(single(3) .replace(STEP.format(n=3), STEP.format(n=3) + STEP.format(n=6).replace("code", "document")))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "")

    def test_check_names_the_missing_heading_and_step(self):
        t = make_task()
        p = plan.parse(single(3))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "missing: ### Step 6")
        p = plan.parse(single(3).replace("## Acceptance\n", "## Accept\n"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "missing: ## Acceptance")
        both = single(3).replace(STEP.format(n=3), STEP.format(n=3) + STEP.format(n=6))
        p = plan.parse(both.replace("### Step 3: code\n#### Files\n- calc.py\n#### Actions", "### Step 3: code\n#### Files\n- calc.py\n#### Action"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "Step 3: missing: #### Actions")

    def test_check_refuses_todo_and_open_decisions(self):
        t = make_task(("design", "code", "verify"))
        p = plan.parse(single(2).replace("add()", "add() TODO: fill in"))
        self.assertEqual(plan.check(p, self.later(t, 1), 6, 5), "TBD or TODO left in the plan")
        p = plan.parse(single(2).replace("add()", "add() TBD"))
        self.assertEqual(plan.check(p, self.later(t, 1), 6, 5), "TBD or TODO left in the plan")
        p = plan.parse(single(2).replace("add()", "add(); the sub-plan has a TODO list"))
        self.assertEqual(plan.check(p, self.later(t, 1), 6, 5), "")
        p = plan.parse(single(2).replace("add()", "add()\n#### TODO\n- **TODO**: edit calc.py"))
        self.assertEqual(plan.check(p, self.later(t, 1), 6, 5), "")
        p = plan.parse(single(2).replace("- add lives in calc.py: the only module.", "- where does add live?"))
        self.assertTrue(plan.check(p, self.later(t, 1), 6, 5).startswith("a Decisions line is a question"))

    def test_check_passes_a_split_plan_and_counts_the_room(self):
        t = make_task()
        p = plan.parse(split())
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "")
        self.assertEqual(plan.check(p, self.later(t), 6, 3), "4 steps after the design step, over task_max_steps")
        self.assertEqual(plan.check(p, self.later(t), 1, 4), "2 parts, over plan_max_parts 1")

    def test_check_refuses_a_bad_split(self):
        t = make_task()
        p = plan.parse(split().replace("| 2 | Report module | code | report.py, calc.py | 1 | yes |",
                                       "| 2 | Report module | code | report.py, calc.py | - | yes |"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4),
                         "calc.py is owned by parts 1 and 2, which does not depend on 1")
        p = plan.parse(split().replace("| 2 | Report module | code |", "| 2 | Report module | scout |"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "part 2: scout is not a write kind")
        p = plan.parse(split().replace("| 1 | Calc module | code | calc.py | - | no |", "| 1 | Calc module | code | calc.py | 2 | no |"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "part 1 depends on a part that is not earlier")
        p = plan.parse(split().replace("## Tests\n- tests/test_report.py.py::test_it\n", ""))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "part 2: missing: ## Tests")


class RebuildTest(unittest.TestCase):
    def test_rebuild_replaces_the_write_steps_and_replaces_the_verify(self):
        t = make_task()
        meta = plan.save(tempfile.mkdtemp(), t, plan.parse(split()), 2)
        lines = plan.rebuild(t, 2, meta["parts"], 5.0)
        self.assertEqual([(s["n"], s["kind"]) for s in t["steps"]],
                         [(1, "scout"), (2, "design"), (3, "code"), (4, "code"), (5, "test"), (6, "document"), (7, "verify")])
        self.assertEqual([s.get("part", 0) for s in t["steps"]], [0, 0, 1, 2, 0, 0, 0])
        self.assertTrue(t["steps"][3]["hard"])
        self.assertEqual(t["steps"][6]["checked"], 6)
        self.assertEqual([p["step"] for p in meta["parts"]], [3, 4])
        self.assertEqual(lines[0]["why"], "design split into 2 sub-plans: 2 code steps (Prep had 1)")

    def test_rebuild_keeps_the_done_steps_on_a_redo(self):
        t = make_task()
        t["steps"][2]["state"] = "done"
        meta = plan.save(tempfile.mkdtemp(), t, plan.parse(split()), 2)
        plan.rebuild(t, 2, meta["parts"], 5.0)
        self.assertEqual([(s["n"], s["kind"], s["state"]) for s in t["steps"]][:4],
                         [(1, "scout", "planned"), (2, "design", "planned"), (3, "code", "done"), (4, "code", "planned")])


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.t = make_task()

    def test_save_writes_the_index_and_the_parts(self):
        meta = plan.save(self.home, self.t, plan.parse(split()), 2)
        self.assertEqual(meta["parts"][1]["file"], "plan/02-report-module.md")
        self.assertTrue(meta["parts"][1]["hard"])
        self.assertEqual(meta["parts"][1]["owns"], ["report.py", "calc.py"])
        self.assertTrue(os.path.exists(os.path.join(self.home, "tasks", self.t["id"], "plan.md")))
        self.t["plan"] = meta
        self.assertTrue(plan.read_part(self.home, self.t, 2).startswith("# Part 2: Report module"))
        self.assertIn("## Sub-plans", plan.read(self.home, self.t))
        self.assertGreater(meta["words"], 40)
        self.assertGreater(meta["kb"], 0)

    def test_with_answer_appends_to_decisions(self):
        text = plan.with_answer(SPLIT_INDEX, "ladder in config.json", "2026-10-14", "Fred")
        dec = plan.section(text, "## Decisions")
        self.assertEqual(dec.splitlines()[-1], "- Fred, 2026-10-14: ladder in config.json")
        self.assertEqual(plan.section(plan.with_answer(SPLIT_INDEX, "x", "2026-10-15"), "## Decisions").splitlines()[-1],
                         "- The user, 2026-10-15: x")  # plan 31: no name set
        self.assertIn("## Out of scope", text)
        self.assertEqual(plan.section(text, "## Out of scope"), "- (none)")

    def test_add_answer_writes_the_file(self):
        self.t["plan"] = plan.save(self.home, self.t, plan.parse(split()), 2)
        line = plan.add_answer(self.home, self.t, "config.json", "2026-10-14", "Fred")
        self.assertEqual(line, "- Fred, 2026-10-14: config.json")
        self.assertIn(line, plan.read(self.home, self.t))

    def test_part_body_drops_the_head(self):
        self.assertEqual(plan.part_body("# Part 2: Report\n\n## Files\n- a"), "## Files\n- a\n")
        self.assertEqual(plan.part_body("## Files\n- a\n"), "## Files\n- a\n")

    def test_write_replaces_the_index_or_a_part(self):
        self.t["plan"] = plan.save(self.home, self.t, plan.parse(split()), 2)
        self.assertEqual(plan.write(self.home, self.t, "# edited\n"), "plan.md")
        self.assertEqual(plan.read(self.home, self.t), "# edited\n")
        self.assertEqual(plan.write(self.home, self.t, "## Files\n- b\n", 2), "plan/02-report-module.md")
        self.assertEqual(plan.read_part(self.home, self.t, 2), "# Part 2: Report module\n\n## Files\n- b\n")

    def test_write_and_add_answer_mask_and_keep_one_line(self):
        self.t["plan"] = plan.save(self.home, self.t, plan.parse(split()), 2)
        plan.write(self.home, self.t, SPLIT_INDEX + "- token: sk-ant-abcdefghijklmnop\n")
        self.assertNotIn("sk-ant-abcdefghijklmnop", plan.read(self.home, self.t))
        plan.write(self.home, self.t, "## Files\n- api_key=hunter2hunter2\n", 2)
        self.assertNotIn("hunter2hunter2", plan.read_part(self.home, self.t, 2))
        plan.write(self.home, self.t, SPLIT_INDEX)
        line = plan.add_answer(self.home, self.t, "use sk-ant-abcdefghijklmnop\n## Acceptance\n- nothing", "2026-10-14",
                               "Fred")
        self.assertEqual(line, "- Fred, 2026-10-14: use *** ## Acceptance - nothing")
        text = plan.read(self.home, self.t)
        self.assertEqual(text.count("\n## Acceptance\n"), 1)  # the answer adds no heading
        self.assertNotIn("sk-ant-", text)


class PromptTest(unittest.TestCase):
    CFG = {"design_max_turns": 30, "plan_max_kb": 100, "plan_max_parts": 6, "task_max_steps": 6}

    def test_design_text_lists_the_later_steps_and_the_limits(self):
        t = make_task()
        text = plan.design_text(t, tasks.step(t, 2), self.CFG)
        self.assertIn("- Step 3: code. step code", text)
        self.assertIn("($edit_steps)".replace("$edit_steps", "3, 6"), text)
        self.assertIn("You have 30 turns", text)
        self.assertIn("at most 6", text)
        self.assertIn("within 4 steps", text)
        self.assertNotIn("$", text)

    def test_design_text_on_a_redo_names_the_question_and_the_done_steps(self):
        t = make_task()
        t["steps"][2]["state"] = "done"
        text = plan.design_text(t, tasks.step(t, 2), dict(self.CFG, user_name="Fred"),
                                "step 4 asked: config.json or models.json?")
        self.assertIn("Fred asked for this plan again: step 4 asked", text)
        self.assertIn("waits for Fred, so every fork", text)  # plan 31: $you
        self.assertIn("starts with `Fred, <date>:`", text)
        self.assertIn("stops and waits for the user", plan.design_text(t, tasks.step(t, 2), self.CFG))
        self.assertIn("- Step 3: code. step code (done, kept)", text)
        self.assertIn("(6)", text)

    def test_prompt_parts_single_plan(self):
        home, t = tempfile.mkdtemp(), make_task()
        t["plan"] = plan.save(home, t, plan.parse(single(3)), 2)
        p, own = plan.prompt_parts(home, t, tasks.step(t, 3))
        self.assertTrue(p.startswith("The plan (follow it, do not change it):\n# Plan: calc"))
        self.assertIn("Plan gap:", p)
        self.assertTrue(own.startswith("Your part of the plan:\n### Step 3: code"))
        p, own = plan.prompt_parts(home, t, tasks.step(t, 5))  # verify
        self.assertIn("plan drift:", p)
        self.assertEqual(own, "")
        self.assertEqual(plan.prompt_parts(home, t, tasks.step(t, 1)), ("", ""))

    def test_prompt_parts_split_plan(self):
        home, t = tempfile.mkdtemp(), make_task()
        t["plan"] = plan.save(home, t, plan.parse(split()), 2)
        plan.rebuild(t, 2, t["plan"]["parts"], 5.0)
        p, own = plan.prompt_parts(home, t, tasks.step(t, 4))
        self.assertTrue(own.startswith("Your part of the plan:\n# Part 2: Report module"))
        self.assertNotIn("Part 1", own)
        p, own = plan.prompt_parts(home, t, tasks.step(t, 7))  # verify: every part
        self.assertIn("# Part 1", own)
        self.assertIn("# Part 2", own)

    def test_design_input_is_every_earlier_note_whole(self):
        home, t = tempfile.mkdtemp(), make_task()
        s = tasks.step(t, 1)
        s.update(model="haiku", effort="low", session="abc")
        tasks.write_note(home, t, s, "## Findings\n" + "long " * 600)
        text = plan.design_input(home, t, 2)
        self.assertTrue(text.startswith("# Step 01: scout on haiku/low"))
        self.assertGreater(len(text.split()), 600)

    def test_design_input_on_a_redo_adds_the_done_later_notes(self):
        home, t = tempfile.mkdtemp(), make_task()
        for n, words in ((1, "scout found calc.py"), (3, "code step wrote add()"), (4, "test step ran it")):
            s = tasks.step(t, n)
            s.update(model="haiku", effort="low", session=f"s{n}", state="done")
            tasks.write_note(home, t, s, "## Findings\n" + words)
        tasks.step(t, 4)["state"] = "planned"  # a note left by an attempt that is not done: not read
        self.assertNotIn("code step wrote add()", plan.design_input(home, t, 2))  # first design: earlier notes only
        t["redo"] = "which file holds the ladder?"
        text = plan.design_input(home, t, 2)
        self.assertIn("scout found calc.py", text)
        self.assertIn("code step wrote add()", text)
        self.assertNotIn("test step ran it", text)


if __name__ == "__main__":
    unittest.main()
