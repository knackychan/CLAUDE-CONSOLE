import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import claude_cli, levers, prep, tasks

GOOD = ("## Goal\nAdd the export; this step: fix add()\n## Findings\nadd() is in calc.py:2\n## Files touched\n"
        "- calc.py (fixed add)\n## Troubleshooting\n- (none)\n## Open questions\n- (none)\n## Next\nRun the tests")
OLD = ("## Findings\nadd() is in calc.py:2\n## Files touched\n- calc.py (fixed add)\n"
       "## Open questions\n- (none)\n## Next\nRun the tests")  # a note from before plan 23


class RulesTest(unittest.TestCase):
    def test_rules_name_the_replan_kind(self):
        self.assertEqual(tasks.RULES["replan"], ("haiku", "low", ""))
        self.assertIn("replan", tasks.PREP_KINDS)
        self.assertNotIn("replan", tasks.EDIT_KINDS)

    def rule(self, kind, model, effort, tools):
        route = tasks.step_route(kind)
        self.assertEqual((route["model"], route["effort"]), (model, effort), kind)
        self.assertEqual(route["notes"], [f"rule {kind}: {model}/{effort}"])
        self.assertEqual(route["hold"], "")
        self.assertEqual(tasks.RULES[kind][2], tools, kind)

    def test_rule_scout_haiku_low(self):
        self.rule("scout", "haiku", "low", "Read,Grep,Glob")

    def test_rule_search_haiku_low(self):
        self.rule("search", "haiku", "low", "Read,Grep,Glob,WebFetch,WebSearch")

    def test_rule_draft_haiku_low(self):
        self.rule("draft", "haiku", "low", "Read,Edit,Write,Grep,Glob")

    def test_rule_proofread_haiku_low(self):
        self.rule("proofread", "haiku", "low", "Read,Edit,Write,Grep,Glob")

    def test_rule_edit_haiku_low(self):
        self.rule("edit", "haiku", "low", "Read,Edit,Write,Grep,Glob")

    def test_rule_code_sonnet_medium(self):
        self.rule("code", "sonnet", "medium", "Bash,Read,Edit,Write,Grep,Glob")

    def test_rule_document_sonnet_medium(self):
        self.rule("document", "sonnet", "medium", "Read,Edit,Write,Grep,Glob")

    def test_rule_explain_sonnet_medium(self):
        self.rule("explain", "sonnet", "medium", "Read,Grep,Glob")

    def test_rule_debug_sonnet_high(self):
        self.rule("debug", "sonnet", "high", "Bash,Read,Edit,Write,Grep,Glob")

    def test_rule_test_haiku_low(self):
        self.rule("test", "haiku", "low", "Bash,Read,Grep,Glob")

    def test_rule_design_opus_high(self):
        self.rule("design", "opus", "high", "Read,Grep,Glob,WebFetch,WebSearch")

    def test_kind_sets_safe_id_and_disallow(self):
        self.assertEqual(tasks.RULES["verify"][2], "Bash,Read,Grep,Glob")
        self.assertEqual(tasks.RULES["fix"][2], "Bash,Read,Edit,Write,Grep,Glob")
        self.assertTrue(all(tasks.RULES[k][2] for k in tasks.KINDS if k != "replan"),  # replan: no session
                        "plan 23: every kind names its tools")
        self.assertEqual(tasks.READ_CAPPED, ("scout", "search"))
        self.assertEqual(set(tasks.PREP_KINDS), set(tasks.RULES) - {"verify", "fix"})
        self.assertEqual(set(tasks.EDIT_KINDS), {"edit", "code", "debug", "document", "draft"})
        self.assertEqual(tasks.DISALLOW, ("Agent",))
        self.assertEqual(tasks.safe_id("20261012-101500-3f2a"), "20261012-101500-3f2a")
        for bad in ("", "..", "a/b", "ABC", "20261012-101500-3f2a-extra-long", None):
            self.assertEqual(tasks.safe_id(bad), "", bad)

    def test_kinds_table_matches_prompt(self):
        rows = {}
        for line in prep.PROMPT_FILE.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[0] in tasks.RULES:
                rows[cells[0]] = (cells[2], cells[3])
        for kind in tasks.PREP_KINDS:
            self.assertIn(kind, rows, f"no row for {kind} in the kinds table")
        for kind, route in rows.items():
            self.assertEqual(route, tasks.RULES[kind][:2], kind)

    def test_verify_runs_one_model_up(self):
        cases = [(("haiku", "low"), ("sonnet", "medium")), (("sonnet", "medium"), ("opus", "medium")),
                 (("sonnet", "high"), ("opus", "high")), (("opus", "high"), ("opus", "high")),
                 (("opus", "low"), ("opus", "medium"))]
        for checked, expected in cases:
            self.assertEqual(tasks.verify_route(checked), expected, checked)

    def test_fix_runs_on_the_escalated_route_once(self):
        route = tasks.step_route("fix", checked=("sonnet", "medium"))
        self.assertEqual((route["model"], route["effort"]), ("sonnet", "high"))
        route = tasks.step_route("fix", checked=("fable", "max"))  # nothing above: kept
        self.assertEqual((route["model"], route["effort"]), ("fable", "max"))

    def test_miss_floor_raises_a_step(self):
        miss = levers.miss_line("APP", "scout", "haiku/low", "haiku/medium", "x")
        other = levers.miss_line("APP", "code", "sonnet/medium", "opus/high", "x")
        route = tasks.step_route("scout", misses=[miss])
        self.assertEqual((route["model"], route["effort"]), ("haiku", "medium"))
        self.assertIn("floor scout: haiku/medium", route["notes"])
        route = tasks.step_route("scout", misses=[other])
        self.assertEqual((route["model"], route["effort"]), ("haiku", "low"))

    def test_next_hint_raises_at_most_one_step(self):
        note = "# Step 01: scout on haiku/low, session s1\n\nHANDOFF-less text\n## Next\nGo.\nNext model: opus/high"
        route = tasks.step_route("code", prev=note)
        self.assertEqual((route["model"], route["effort"]), ("sonnet", "high"))
        self.assertIn("hint: opus/high -> one step up", route["notes"])
        for text in ("Next model: haiku/low", "Next model: gpt/high", "Next model: sonnet/turbo", "Next model: sonnet/medium"):
            route = tasks.step_route("code", prev=text)
            self.assertEqual((route["model"], route["effort"]), ("sonnet", "medium"), text)
            self.assertEqual(len(route["notes"]), 1, text)

    def test_pick_keeps_its_model_against_a_hint(self):
        hint = "Next model: opus/high"
        route = tasks.step_route("debug", pick="sonnet", prev=hint)  # one step up would leave sonnet
        self.assertEqual((route["model"], route["effort"]), ("sonnet", "high"))
        self.assertIn("hint: opus/high -> pick sonnet kept", route["notes"])
        route = tasks.step_route("code", pick="sonnet", prev=hint)  # the effort may still step up
        self.assertEqual((route["model"], route["effort"]), ("sonnet", "high"))
        self.assertIn("hint: opus/high -> one step up", route["notes"])
        route = tasks.step_route("design", pick="haiku", prev=hint)
        self.assertEqual((route["model"], route["effort"]), ("haiku", "high"))

    def test_pick_beats_the_miss_floor(self):
        miss = levers.miss_line("APP", "edit", "sonnet/low", "opus/high", "x")
        route = tasks.step_route("edit", pick="sonnet", misses=[miss])  # Fred, 2026-10-13: the model is his
        self.assertEqual((route["model"], route["effort"]), ("sonnet", "high"))  # the floor's effort still counts
        self.assertEqual(route["notes"], ["rule edit: haiku/low", "pick: sonnet", "floor edit: opus/high -> pick sonnet/high kept"])
        route = tasks.step_route("edit", pick="opus", misses=[miss])  # a pick at the floor's model: the floor as is
        self.assertEqual((route["model"], route["effort"]), ("opus", "high"))
        self.assertEqual(route["notes"][-1], "floor edit: opus/high")
        route = tasks.step_route("edit", misses=[miss])  # no pick: the floor stands
        self.assertEqual((route["model"], route["effort"]), ("opus", "high"))

    def test_step_after_opus_goes_back_to_its_rule(self):
        note = "# Step 01: design on opus/high, session s1\n\n## Findings\nUse a table.\n## Next\nWrite it."
        route = tasks.step_route("code", prev=note)
        self.assertEqual((route["model"], route["effort"]), ("sonnet", "medium"))

    def test_task_demand_raises_code_steps(self):
        demand = {"reasoning": "high", "volume": "low"}
        want = {"code": ("sonnet", "high"), "debug": ("sonnet", "high"), "scout": ("haiku", "low"),
                "design": ("opus", "high")}
        for kind, expected in want.items():
            route = tasks.step_route(kind, demand=demand)
            self.assertEqual((route["model"], route["effort"]), expected, kind)
        self.assertIn("demand: effort high", tasks.step_route("code", demand=demand)["notes"])
        self.assertEqual(tasks.step_route("code", demand={"reasoning": "medium"})["effort"], "medium")

    def test_code_never_picks_fable(self):
        route = tasks.step_route("design", prev="Next model: fable/max")
        self.assertEqual((route["model"], route["effort"]), ("opus", "high"))
        route = tasks.step_route("design", pick="fable")
        self.assertEqual((route["model"], route["effort"]), ("fable", "high"))
        self.assertIn("pick: fable", route["notes"])

    def test_opus_only_where_reasoning_is_needed(self):
        for kind in tasks.PREP_KINDS:
            if kind != "design":
                self.assertNotEqual(tasks.step_route(kind)["model"], "opus", kind)
        self.assertEqual(tasks.step_route("verify", checked=("sonnet", "medium"))["model"], "opus")
        self.assertEqual(tasks.step_route("verify", checked=("haiku", "low"))["model"], "sonnet")

    def test_fixed_effort_runs_every_step_at_that_level(self):
        want = {"scout": "haiku", "code": "sonnet", "design": "opus"}
        for kind, model in want.items():
            route = tasks.step_route(kind, effort="max")
            self.assertEqual((route["model"], route["effort"]), (model, "max"), kind)
            self.assertIn("fixed effort: max", route["notes"])
        route = tasks.step_route("verify", checked=("sonnet", "max"), effort="max")
        self.assertEqual((route["model"], route["effort"]), ("opus", "max"))

    def test_fixed_effort_is_clamped_to_the_model_cap(self):
        with mock.patch.dict(tasks.EFFORT_CAP, {"haiku": "high"}):
            route = tasks.step_route("scout", effort="max")
        self.assertEqual((route["model"], route["effort"]), ("haiku", "high"))
        self.assertIn("cap haiku: high", route["notes"])

    def test_escalate_with_fixed_effort_moves_the_model(self):
        route = tasks.step_route("fix", checked=("sonnet", "max"), effort="max")
        self.assertEqual((route["model"], route["effort"]), ("opus", "max"))


class HandoffTest(unittest.TestCase):
    def test_parse_handoff_takes_the_last_block(self):
        first = "## Findings\nold"
        msg = f"Done.\n\nHANDOFF\n{first}\nEND HANDOFF\nmore words\n  HANDOFF  \n{GOOD}\n  END HANDOFF  \ntrailing text"
        self.assertEqual(tasks.parse_handoff(msg), GOOD)
        self.assertEqual(tasks.parse_handoff(f"HANDOFF\n{first}\nEND HANDOFF"), first)
        self.assertIsNone(tasks.parse_handoff("no block here"))
        self.assertIsNone(tasks.parse_handoff(f"HANDOFF\n{GOOD}"))  # never closed
        self.assertIsNone(tasks.parse_handoff(f"see the HANDOFF block: {GOOD} END HANDOFF"))  # not whole lines
        self.assertIsNone(tasks.parse_handoff(""))

    def test_parse_handoff_accepts_dressed_markers(self):
        body = "## Findings\nx\n## Files touched\n- (none)\n## Open questions\n- (none)\n## Next\ngo"
        for start, end in (("**HANDOFF**", "**END HANDOFF**"), ("`HANDOFF`", "`END HANDOFF`"),
                           ("### HANDOFF", "### END HANDOFF"), ("  HANDOFF ", "END HANDOFF  ")):
            self.assertEqual(tasks.parse_handoff(f"text\n{start}\n{body}\n{end}\n"), body, start)
        self.assertIsNone(tasks.parse_handoff("**HANDOFF block follows**\n" + body + "\nEND HANDOFF"))

    def test_check_handoff_reasons(self):
        self.assertEqual(tasks.check_handoff(GOOD), "")
        self.assertEqual(tasks.HEADINGS, ("## Goal", "## Findings", "## Files touched", "## Troubleshooting",
                                          "## Open questions", "## Next"))
        self.assertEqual(tasks.check_handoff(GOOD.replace("\n## Next\nRun the tests", "")), "missing: ## Next")
        swapped = GOOD.replace("## Files touched", "## TMP").replace("## Open questions", "## Files touched")
        swapped = swapped.replace("## TMP", "## Open questions")
        self.assertEqual(tasks.check_handoff(swapped), "headings out of order")
        for empty in ("## Findings\n\n## Files touched", "## Findings\n   \n## Files touched"):
            block = GOOD.replace("## Findings\nadd() is in calc.py:2\n## Files touched", empty)
            self.assertEqual(tasks.check_handoff(block), "Findings is empty")
        inline = GOOD.replace("## Next\n", "## Next: ")  # a heading must be a whole line
        self.assertEqual(tasks.check_handoff(inline), "missing: ## Next")

    def test_check_handoff_needs_goal_and_troubleshooting(self):
        self.assertEqual(tasks.check_handoff(GOOD.replace("## Goal\nAdd the export; this step: fix add()\n", "")),
                         "missing: ## Goal")
        self.assertEqual(tasks.check_handoff(GOOD.replace("## Troubleshooting\n- (none)\n", "")),
                         "missing: ## Troubleshooting")
        self.assertEqual(tasks.check_handoff(GOOD.replace("Add the export; this step: fix add()", "  ")), "Goal is empty")
        self.assertEqual(tasks.check_handoff(OLD), "missing: ## Goal")  # a step's new block needs all six

    def test_old_four_heading_note_checks_on_read_paths(self):
        self.assertEqual(tasks.check_handoff(OLD, old_ok=True), "")
        self.assertEqual(tasks.check_handoff(GOOD, old_ok=True), "")
        self.assertEqual(tasks.check_handoff(OLD.replace("## Next\n", "## Next: "), old_ok=True), "missing: ## Next")
        half = GOOD.replace("## Troubleshooting\n- (none)\n", "")  # a Goal heading: a new note, all six
        self.assertEqual(tasks.check_handoff(half, old_ok=True), "missing: ## Troubleshooting")

    def test_next_hint(self):
        self.assertEqual(tasks.next_hint(GOOD + "\nNext model: sonnet/high"), ("sonnet", "high"))
        self.assertIsNone(tasks.next_hint(GOOD + "\nNext model: gpt/high"))
        self.assertIsNone(tasks.next_hint(GOOD))
        both = "Next model: gpt/high\nNext model: opus/low"  # the first one routing.parse accepts
        self.assertEqual(tasks.next_hint(both), ("opus", "low"))

    def test_lesson_of(self):
        self.assertEqual(tasks.lesson_of(GOOD + "\nLesson: profile before optimizing."), "profile before optimizing.")
        self.assertEqual(tasks.lesson_of(GOOD + "\n**Lesson:** keep the first one\nLesson: the last one wins"), "the last one wins")
        for none in ("", GOOD, GOOD + "\nLesson: none", GOOD + "\nLesson: -", GOOD + "\nLesson: N/A."):
            self.assertEqual(tasks.lesson_of(none), "", none)
        self.assertEqual(tasks.lesson_of("a lesson: not a line start"), "")

    def test_verdict_and_question_of_a_reply(self):
        # the Stop hook is async and may land after run_ended: the chain reads them in the reply too
        reply = f"HANDOFF\n{GOOD}\nEND HANDOFF\n**VERDICT: FAIL** test_add - 3 != 4"
        self.assertEqual(tasks.reply_verdict(reply), ("FAIL", "test_add - 3 != 4"))
        self.assertEqual(tasks.reply_verdict("VERDICT: FAIL\nVERDICT: PASS"), ("PASS", ""))  # the last one
        self.assertEqual(tasks.reply_verdict("end with `VERDICT: PASS` or not"), ("", ""))  # not a whole line
        self.assertEqual(tasks.reply_question("text\n- STOP: which file?\n"), "which file?")
        for none in ("STOP: none", "STOP: N/A.", "STOP: -", "no question"):
            self.assertEqual(tasks.reply_question(none), "", none)

    def test_note_file_and_text(self):
        task = {"id": "20261012-101500-3f2a"}
        step = {"n": 2, "kind": "code", "model": "sonnet", "effort": "medium", "session": "abc"}
        self.assertEqual(tasks.note_file(task, step), "steps/02-code.md")
        text = tasks.note_text(task, step, "## Findings\nkey sk-abcdefghijkl1234 used\n## Next\nx")
        self.assertTrue(text.startswith("# Step 02: code on sonnet/medium, session abc\n\n## Findings\n"))
        self.assertIn("key *** used", text)
        self.assertNotIn("sk-abcdefghijkl1234", text)
        big = tasks.note_text(task, step, "line of text\n" * 5000)  # 65 KB
        self.assertTrue(big.endswith("[cut at 20 KB]"))
        self.assertLess(len(big.encode("utf-8")), tasks.NOTE_MAX + 200)
        self.assertEqual(tasks.NOTE_MAX, 20 * 1024)


NOW = 1760235300.0


def make(kinds=("scout", "code"), effort="auto", max_steps=6):
    proposed = [{"kind": k, "goal": f"goal of {k}"} for k in kinds]
    steps = tasks.plan_steps(proposed, max_steps)
    return tasks.new_task("D:\\WORK\\APP", "APP", "Add the export", "Write the export and test it", steps,
                          "normal", {"reasoning": "medium", "volume": "low"}, "20261012-101455-9c1d", effort, NOW)


def run(task, n, model="sonnet", effort="medium"):
    route = {"model": model, "effort": effort, "notes": [f"rule x: {model}/{effort}"], "hold": ""}
    return tasks.start_step(task, n, f"s{n}", route, "abc1234", NOW + n)


def end(task, **kw):
    args = dict(ok=True, block_error="", verdict="", verdict_detail="", question="", now=NOW + 100)
    args.update(kw)
    return tasks.on_step_ended(task, **args)


def kinds_of(task):
    return [s["kind"] for s in task["steps"]]


class ChainTest(unittest.TestCase):
    def test_plan_steps_validates_and_appends_verify(self):
        proposed = [{"kind": "scout", "goal": "a"}, {"kind": "code", "goal": "b"},
                    {"kind": "bogus", "goal": "c"}, {"kind": "test"}]
        steps = tasks.plan_steps(proposed, 6)
        self.assertEqual([s["kind"] for s in steps], ["scout", "code", "verify"])
        self.assertEqual([s["n"] for s in steps], [1, 2, 3])
        self.assertEqual(steps[2]["goal"], "Check step 2")
        self.assertEqual(steps[2]["checked"], 2)
        self.assertEqual(steps[0]["state"], "planned")
        self.assertEqual((steps[0]["model"], steps[0]["pick"], steps[0]["session"], steps[0]["notes"]), ("", "", "", []))
        two = tasks.plan_steps([{"kind": "search", "goal": "a"}, {"kind": "explain", "goal": "b"}], 6)
        self.assertEqual([s["kind"] for s in two], ["search", "explain"])
        done = tasks.plan_steps([{"kind": "code", "goal": "a"}, {"kind": "verify", "goal": "b"}], 6)
        self.assertEqual([s["kind"] for s in done], ["code", "verify"])
        self.assertEqual([s["kind"] for s in tasks.plan_steps(proposed, 1)], ["scout"])
        picked = tasks.plan_steps([{"kind": "design", "goal": "a", "model": "fable"},
                                   {"kind": "scout", "goal": "b", "model": "gpt"}], 6)
        self.assertEqual([s["pick"] for s in picked], ["fable", ""])
        self.assertEqual(tasks.plan_steps([], 6), [])
        self.assertEqual(tasks.plan_steps("junk", 6), [])

    def test_plan_steps_keeps_a_long_goal(self):
        goal = " ".join(["word"] * 180)  # 899 characters
        self.assertEqual(tasks.plan_steps([{"kind": "scout", "goal": goal}], 6)[0]["goal"], goal)
        cut = tasks.plan_steps([{"kind": "scout", "goal": "x" * 1500}], 6)[0]["goal"]
        self.assertEqual((len(cut), cut[-1]), (1000, "…"))

    def test_verify_goes_after_the_last_edit_step(self):
        steps = tasks.plan_steps([{"kind": "code", "goal": "a"}, {"kind": "explain", "goal": "b"}], 6)
        self.assertEqual([s["kind"] for s in steps], ["code", "verify", "explain"])
        self.assertEqual([s["n"] for s in steps], [1, 2, 3])

    def test_new_task_shape(self):
        task = make()
        for key in ("id", "project_dir", "project", "title", "type", "demand", "effort", "state", "owner",
                    "current", "last_good", "escalated", "fable_ok", "prep", "why", "created", "updated", "steps"):
            self.assertIn(key, task)
        self.assertTrue(tasks.safe_id(task["id"]))
        self.assertEqual((task["state"], task["owner"], task["current"], task["last_good"], task["escalated"],
                          task["fable_ok"], task["why"]), ("planned", "service", 0, 0, "", False, ""))
        self.assertEqual((task["created"], task["updated"]), (NOW, NOW))
        self.assertEqual(task["prep"], "20261012-101455-9c1d")
        self.assertEqual(task["goal"], "Write the export and test it")
        with self.assertRaises(ValueError):
            tasks.new_task("D:\\APP", "APP", "t", "g", [], "normal", {}, "", "auto", NOW)
        with self.assertRaises(ValueError):
            make(effort="turbo")
        self.assertEqual(make(effort="max")["effort"], "max")

    def test_step_and_current_step(self):
        task = make()
        self.assertEqual(tasks.step(task, 2)["kind"], "code")
        with self.assertRaises(KeyError):
            tasks.step(task, 9)
        self.assertIsNone(tasks.current_step(task))
        run(task, 1)
        self.assertEqual(tasks.current_step(task)["n"], 1)

    def test_start_step_and_chain_lines(self):
        task = make()
        lines = run(task, 1, "haiku", "low")
        s = tasks.step(task, 1)
        self.assertEqual((s["state"], s["model"], s["effort"], s["session"], s["start_commit"], s["started"]),
                         ("running", "haiku", "low", "s1", "abc1234", NOW + 1))
        self.assertEqual(s["notes"], ["rule x: haiku/low"])
        self.assertIsNone(s["ended"])
        self.assertEqual((task["state"], task["current"], task["why"], task["updated"]), ("running", 1, "", NOW + 1))
        self.assertEqual(len(lines), 2)
        step_line = next(line for line in lines if not str(line["from"]).startswith("task:"))
        task_line = next(line for line in lines if str(line["from"]).startswith("task:"))
        self.assertEqual((step_line["step"], step_line["from"], step_line["to"], step_line["why"], step_line["session"]),
                         (1, "planned", "running", "rule x: haiku/low", "s1"))
        self.assertEqual((task_line["from"], task_line["to"]), ("task:planned", "task:running"))
        self.assertEqual(len(run(task, 2)), 1)  # the task is already running

    def test_good_handoff_moves_to_the_next_step(self):
        task = make(("scout", "explain"))
        run(task, 1)
        action, lines = end(task)
        self.assertEqual(action, "next")
        self.assertEqual((tasks.step(task, 1)["state"], task["last_good"], task["state"]), ("done", 1, "running"))
        self.assertEqual(tasks.step(task, 1)["ended"], NOW + 100)
        self.assertEqual((lines[0]["from"], lines[0]["to"], lines[0]["step"]), ("running", "done", 1))
        run(task, 2)
        action, lines = end(task)
        self.assertEqual(action, "done")
        self.assertEqual((task["state"], task["last_good"]), ("done", 2))
        self.assertEqual(lines[-1]["to"], "task:done")

    def test_question_waits_for_fred(self):
        task = make(("scout", "explain"))
        run(task, 1)
        action, lines = end(task, question="which file?")
        self.assertEqual(action, "wait")
        self.assertEqual((task["state"], task["why"]), ("waiting", "asks: which file?"))
        self.assertEqual(tasks.step(task, 1)["state"], "running")
        self.assertEqual((lines[0]["from"], lines[0]["to"]), ("task:running", "task:waiting"))
        action, lines = end(task, question="and which one?")  # asked again: still waiting, nothing new to log
        self.assertEqual((action, lines, task["why"]), ("wait", [], "asks: and which one?"))
        action, _ = end(task)  # Fred answered, the step ended well
        self.assertEqual((action, task["state"], task["why"]), ("next", "running", ""))

    def test_cap_reason_timeout(self):
        self.assertEqual(tasks.cap_reason("error_step_timeout", {"timeout_s": 1800}),
                         "it hit the step timeout (1800 s)")
        self.assertEqual(tasks.cap_reason("error_step_timeout", None), "it hit the step timeout (? s)")

    def test_cap_reason_names_the_cap(self):
        self.assertEqual(tasks.cap_reason("error_max_turns", {"max_turns": 12}), "it hit the turn cap (12 turns)")
        self.assertEqual(tasks.cap_reason("error_max_budget_usd", {"budget": 3}), "it hit the step budget (3.00 USD)")
        self.assertEqual(tasks.cap_reason("success", {}), "")
        self.assertEqual(tasks.cap_reason("error_max_turns", None), "it hit the turn cap (? turns)")
        task = make(("code",))
        run(task, 1)
        action, _ = end(task, ok=False, cap="it hit the turn cap (12 turns)")
        self.assertEqual((action, task["why"]), ("retry", "it hit the turn cap (12 turns)"))

    def test_bad_handoff_retries_once_then_stuck(self):
        task = make(("scout", "explain"))
        run(task, 1)
        action, lines = end(task, block_error="no HANDOFF block")
        s = tasks.step(task, 1)
        self.assertEqual((action, s["state"], s["retries"], task["state"]), ("retry", "planned", 1, "running"))
        self.assertEqual(task["why"], "no HANDOFF block")
        self.assertEqual([(line["from"], line["to"]) for line in lines], [("running", "failed"), ("failed", "planned")])
        run(task, 1)
        action, lines = end(task, block_error="Findings is empty")
        self.assertEqual((action, task["state"], s["state"]), ("stuck", "stuck", "failed"))
        self.assertEqual(task["why"], "Findings is empty (after one retry)")
        self.assertEqual(lines[-1]["to"], "task:stuck")
        other = make(("scout", "explain"))  # the run itself failed, the block is fine
        run(other, 1)
        self.assertEqual(end(other, ok=False)[0], "retry")
        run(other, 1)
        self.assertEqual(end(other, ok=False)[0], "stuck")
        self.assertTrue(other["why"].endswith("(after one retry)"))

    def three_step_task(self):
        task = make(("scout", "code"))  # scout, code, verify
        run(task, 1, "haiku", "low")
        end(task)
        run(task, 2, "sonnet", "medium")
        end(task)
        run(task, 3, "opus", "medium")
        return task

    def test_verify_fail_inserts_fix_and_verify_once(self):
        task = self.three_step_task()
        action, lines = end(task, verdict="FAIL", verdict_detail="test_x - KeyError: 'a'")
        self.assertEqual(action, "fix")
        self.assertEqual(kinds_of(task), ["scout", "code", "verify", "fix", "verify"])
        self.assertEqual([s["n"] for s in task["steps"]], [1, 2, 3, 4, 5])
        self.assertEqual(task["escalated"], "sonnet/medium -> sonnet/high")
        self.assertIn(" - code: sonnet/medium failed", task["miss"])
        self.assertIn("next time start at sonnet/high.", task["miss"])
        self.assertIn("KeyError", task["miss"])
        fix, again = tasks.step(task, 4), tasks.step(task, 5)
        code = tasks.step(task, 2)
        self.assertEqual((code["model"], code["effort"]), ("sonnet", "medium"))
        self.assertEqual((fix["checked"], again["checked"]), (2, 4))
        self.assertEqual((fix["state"], again["state"]), ("planned", "planned"))
        verify = tasks.step(task, 3)
        self.assertEqual((verify["state"], verify["verdict"], verify["verdict_detail"]),
                         ("done", "FAIL", "test_x - KeyError: 'a'"))
        self.assertEqual((task["state"], task["current"], task["last_good"]), ("running", 3, 3))
        self.assertTrue(lines)
        route = tasks.step_route("fix", checked=(code["model"], code["effort"]))
        before = tasks.step_prompt(task, fix, "PREV")  # the service builds the prompt before the step starts
        self.assertIn(levers.FIX_FRAME, before)  # a fix step names its hypotheses before it edits
        self.assertIn("The checks failed: test_x - KeyError: 'a'. You now run on sonnet/high", before)
        run(task, 4, route["model"], route["effort"])
        self.assertEqual(tasks.step_prompt(task, fix, "PREV"), before)
        self.assertEqual(end(task)[0], "next")
        run(task, 5, "opus", "high")
        action, lines = end(task, verdict="FAIL", verdict_detail="still red")
        self.assertEqual(action, "stuck")
        self.assertTrue(task["why"].startswith("verify failed twice"))
        self.assertIn("still red", task["why"])
        self.assertEqual((task["state"], tasks.step(task, 5)["state"]), ("stuck", "failed"))

    def test_fix_insert_renumbers_later_steps(self):
        task = make(("code", "explain"))  # code, verify, explain
        run(task, 1)
        end(task)
        run(task, 2, "opus", "medium")
        self.assertEqual(end(task, verdict="FAIL", verdict_detail="red")[0], "fix")
        self.assertEqual(kinds_of(task), ["code", "verify", "fix", "verify", "explain"])
        self.assertEqual([s["n"] for s in task["steps"]], [1, 2, 3, 4, 5])
        self.assertEqual([s["goal"] for s in task["steps"] if s["kind"] == "verify"], ["Check step 1", "Check step 3"])
        self.assertEqual(tasks.step(task, 3)["checked"], 1)

    def test_verify_pass_goes_on(self):
        task = self.three_step_task()
        action, _ = end(task, verdict="PASS")
        self.assertEqual(action, "done")
        self.assertEqual((tasks.step(task, 3)["verdict"], tasks.step(task, 3)["state"], task["state"]),
                         ("PASS", "done", "done"))
        mid = make(("code", "explain"))
        run(mid, 1)
        end(mid)
        run(mid, 2, "opus", "medium")
        self.assertEqual(end(mid, verdict="PASS")[0], "next")

    def test_verify_without_verdict_is_a_bad_block(self):
        task = self.three_step_task()
        action, _ = end(task, verdict="")
        self.assertEqual((action, task["why"], tasks.step(task, 3)["retries"]), ("retry", "no VERDICT line", 1))
        run(task, 3, "opus", "medium")
        self.assertEqual(end(task, verdict="")[0], "stuck")
        self.assertEqual(task["why"], "no VERDICT line (after one retry)")
        other = self.three_step_task()  # a FAIL with a bad block is a retry, not a fix
        self.assertEqual(end(other, verdict="FAIL", block_error="missing: ## Next")[0], "retry")
        self.assertEqual(other["escalated"], "")

    def test_fred_confirm_releases_a_hold(self):
        task = make(("code",))
        run(task, 1)
        end(task)
        task.update(state="waiting", why="opus over its pace")
        ok, why, lines = tasks.fred(task, "confirm", NOW, next_n=2)
        self.assertEqual((ok, why, task["state"], task["hold_ok"], task["fable_ok"]), (True, "", "running", 2, False))
        self.assertEqual(lines[-1]["to"], "task:running")
        task.update(state="waiting", why="something else")
        self.assertEqual(tasks.fred(task, "confirm", NOW, next_n=2)[:2], (False, "nothing to confirm"))

    def test_fred_hands_off_or_marks_done(self):
        task = make(("scout", "code"))
        run(task, 1)
        self.assertEqual(tasks.fred(task, "done", NOW + 5)[:2], (False, "task is running"))  # Stop it first
        end(task, question="which file?")
        ok, why, lines = tasks.fred(task, "handoff", NOW + 6)
        self.assertEqual((ok, task["state"], task["why"], task["owner"]), (True, "handed", "handed off by Fred", "fred"))
        self.assertEqual(tasks.step(task, 1)["state"], "handed")  # handed, not a checked step; step 2 never starts
        self.assertEqual([(c["from"], c["to"]) for c in lines], [("running", "handed"), ("task:waiting", "task:handed")])
        self.assertEqual(tasks.fred(task, "handoff", NOW + 7)[:2], (False, "task is handed"))
        ok, _, lines = tasks.fred(task, "done", NOW + 8)  # handed over, then Fred calls it done
        self.assertEqual((ok, task["state"], task["why"]), (True, "done", "marked done by Fred"))
        self.assertEqual(tasks.step(task, 1)["state"], "handed")
        stuck = make(("scout",))
        run(stuck, 1)
        stuck.update(state="stuck")
        tasks.step(stuck, 1)["state"] = "failed"
        self.assertTrue(tasks.fred(stuck, "done", NOW + 9)[0])
        self.assertEqual((stuck["state"], tasks.step(stuck, 1)["state"]), ("done", "failed"))  # a failed step stays

    def test_fred_continue_runs_the_stopped_step_on(self):
        task = make(("scout", "code"))
        run(task, 1)
        end(task)
        run(task, 2)
        self.assertEqual(tasks.fred(task, "continue", NOW + 5)[:2], (False, "not a stopped step"))  # running
        tasks.fred(task, "stop", NOW + 6)
        step = tasks.step(task, 2)
        self.assertEqual((step["state"], step["attempts"][-1]["why"]), ("failed", "stopped by Fred"))
        ok, why, lines = tasks.fred(task, "continue", NOW + 7)
        self.assertEqual((ok, why, task["state"], task["owner"], task["current"]), (True, "", "running", "service", 2))
        self.assertEqual((step["state"], step["session"], step["ended"], step["retries"]), ("running", "s2", None, 0))
        self.assertEqual(len(step["attempts"]), 1)  # the same session: its cost is the session's, not counted twice
        self.assertEqual((step["attempts"][-1]["ended"], step["attempts"][-1]["final"]), (None, False))
        self.assertEqual([(c["from"], c["to"], c["why"]) for c in lines],
                         [("failed", "running", "continued by Fred"), ("task:stopped", "task:running", "")])
        self.assertEqual(end(task)[0], "next")  # its end is read like any step's: the verify comes next
        done = make(("scout", "code"))
        run(done, 1)
        end(done)
        tasks.fred(done, "stop", NOW + 8)  # stopped between steps: step 1 is done, Retry starts step 2
        self.assertEqual(tasks.fred(done, "continue", NOW + 9)[:2], (False, "not a stopped step"))

    def test_fred_levers(self):
        task = make(("scout", "explain"))
        run(task, 1)
        ok, why, lines = tasks.fred(task, "pause", NOW + 5)
        self.assertEqual((ok, task["owner"], task["state"]), (True, "fred", "running"))
        self.assertEqual(tasks.fred(task, "pause", NOW + 6)[:2], (False, "already paused"))
        ok, _, _ = tasks.fred(task, "resume", NOW + 7)
        self.assertEqual((ok, task["owner"]), (True, "service"))
        self.assertFalse(tasks.fred(task, "resume", NOW + 8)[0])
        ok, why, lines = tasks.fred(task, "retry", NOW + 9)
        self.assertEqual((ok, why, lines), (False, "not stuck or stopped", []))
        ok, why, lines = tasks.fred(task, "stop", NOW + 10)
        self.assertEqual((ok, task["state"], task["owner"]), (True, "stopped", "fred"))
        self.assertTrue(lines)
        self.assertFalse(tasks.fred(task, "stop", NOW + 11)[0])
        self.assertFalse(tasks.fred(task, "pause", NOW + 12)[0])
        ok, _, lines = tasks.fred(task, "retry", NOW + 13)
        self.assertEqual((ok, task["state"], task["owner"], tasks.step(task, 1)["state"]),
                         (True, "running", "service", "planned"))
        self.assertTrue(lines)
        stuck = make(("scout", "explain"))
        run(stuck, 1)
        end(stuck, block_error="x")
        run(stuck, 1)
        end(stuck, block_error="x")
        self.assertEqual(stuck["state"], "stuck")
        self.assertFalse(tasks.fred(stuck, "resume", NOW + 14)[0])  # Retry is the way out of stuck
        ok, _, _ = tasks.fred(stuck, "retry", NOW + 15)
        self.assertEqual((ok, stuck["state"], tasks.step(stuck, 1)["state"], tasks.step(stuck, 1)["retries"]),
                         (True, "running", "planned", 1))
        self.assertEqual(tasks.fred(stuck, "confirm", NOW + 16)[:2], (False, "nothing to confirm"))
        waiting = make(("scout", "explain"))
        waiting["state"], waiting["why"] = "waiting", "confirm Fable"
        ok, _, _ = tasks.fred(waiting, "confirm", NOW + 17)
        self.assertEqual((ok, waiting["fable_ok"], waiting["state"], waiting["why"]), (True, True, "running", ""))
        self.assertFalse(tasks.fred(waiting, "bogus", NOW + 18)[0])
        done = make(("scout", "explain"))
        done["state"] = "done"
        self.assertFalse(tasks.fred(done, "stop", NOW + 19)[0])

    def test_files_round_trip(self):
        with tempfile.TemporaryDirectory() as home:
            task = make(("scout", "explain"))
            run(task, 1, "haiku", "low")
            tasks.save(home, task)
            folder = tasks.folder(home, task["id"])
            self.assertEqual(tasks.load(home, task["id"]), task)
            self.assertFalse((folder / "task.json.tmp").exists())
            self.assertEqual(list(tasks.load_all(home)), [task["id"]])
            line = {"ts": 1.0, "step": 1, "from": "planned", "to": "running", "why": "x", "session": "s1"}
            tasks.log(home, task["id"], [line, dict(line, step=2)])
            tasks.log(home, task["id"], [dict(line, step=3)])
            rows = [json.loads(row) for row in (folder / "chain.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([r["step"] for r in rows], [1, 2, 3])
            step = tasks.step(task, 1)
            rel = tasks.write_note(home, task, step, GOOD)
            self.assertEqual(rel, "steps/01-scout.md")
            self.assertEqual((folder / rel).read_text(encoding="utf-8"), tasks.note_text(task, step, GOOD))
            self.assertEqual(step["handoff"], rel)
            self.assertEqual(tasks.read_note(home, task, 1), tasks.note_text(task, step, GOOD))
            self.assertEqual(tasks.read_note(home, task, 2), "")
            self.assertEqual(tasks.read_note(home, task, 0), "")
            for bad in ("", "..", "../x", "a/b", "XYZ"):
                self.assertIsNone(tasks.load(home, bad), bad)
            broken = Path(home) / "tasks" / "abc-def"
            broken.mkdir(parents=True)
            (broken / "task.json").write_text("{not json", encoding="utf-8")
            self.assertIsNone(tasks.load(home, "abc-def"))
            self.assertEqual(list(tasks.load_all(home)), [task["id"]])
            for part in ("state", "steps"):  # a task.json that is not whole would break the hub loop and the list
                (broken / "task.json").write_text(json.dumps({k: v for k, v in task.items() if k != part}),
                                                  encoding="utf-8")
                self.assertIsNone(tasks.load(home, "abc-def"), part)
            half = dict(task, steps=[{k: v for k, v in task["steps"][0].items() if k != "pick"}])
            (broken / "task.json").write_text(json.dumps(half), encoding="utf-8")
            self.assertIsNone(tasks.load(home, "abc-def"))
            with self.assertRaises(ValueError):
                tasks.folder(home, "../escape")

    def test_prune_removes_only_finished_old_tasks(self):
        with tempfile.TemporaryDirectory() as home:
            cases = {"20260101-000000-aaaa": ("done", 100), "20260101-000000-bbbb": ("running", 100),
                     "20260101-000000-cccc": ("done", 10), "20260101-000000-dddd": ("stuck", 100),
                     "20260101-000000-eeee": ("stopped", 100), "20260101-000000-ffff": ("waiting", 100)}
            for tid, (state, age_days) in cases.items():
                task = make(("scout", "explain"))
                task["id"], task["state"] = tid, state
                tasks.save(home, task)
                stamp = NOW - age_days * 86400
                os.utime(tasks.folder(home, tid) / "task.json", (stamp, stamp))
            removed = tasks.prune(home, 90, now=NOW)
            self.assertEqual(sorted(removed), ["20260101-000000-aaaa", "20260101-000000-dddd", "20260101-000000-eeee"])
            self.assertEqual(sorted(tasks.load_all(home)),
                             ["20260101-000000-bbbb", "20260101-000000-cccc", "20260101-000000-ffff"])
            self.assertEqual(tasks.prune(home, 90, now=NOW), [])
            self.assertEqual(tasks.prune(Path(home) / "nothing", 90, now=NOW), [])

    def test_start_step_records_each_attempt(self):
        task = make(("code",))
        run(task, 1)
        end(task, ok=True, block_error="no HANDOFF block")  # retry
        tasks.start_step(task, 1, "s-two", {"model": "sonnet", "effort": "medium", "notes": []}, "", NOW + 5)
        a = tasks.step(task, 1)["attempts"]
        self.assertEqual([x["session"] for x in a], ["s1", "s-two"])
        self.assertEqual((a[0]["why"], a[0]["ended"], a[1]["ended"]), ("no HANDOFF block", NOW + 100, None))
        self.assertEqual((a[0]["final"], a[0]["cost"]), (False, 0))

    def test_old_step_without_attempts_reads_as_one(self):
        old = {"session": "s1", "cost": 0.2, "started": 1.0, "ended": 2.0}
        self.assertEqual(tasks.attempts(old), [{"session": "s1", "cost": 0.2, "started": 1.0, "ended": 2.0,
                                                "why": "", "final": True}])
        self.assertEqual(tasks.attempts({"session": ""}), [])
        task = make(("code",))
        for s in task["steps"]:
            del s["attempts"]
        self.assertTrue(tasks.whole(task))
        run(task, 1)  # an old step that starts again keeps its earlier session
        tasks.step(task, 1)["attempts"] = []
        tasks.step(task, 1).update(session="s0", cost=0.5)
        tasks.start_step(task, 1, "s-new", {"model": "sonnet", "effort": "medium", "notes": []}, "", NOW + 5)
        self.assertEqual([a["session"] for a in tasks.attempts(tasks.step(task, 1))], ["s0", "s-new"])
        self.assertEqual(tasks.step_cost(tasks.step(task, 1)), 0.5)

    def test_fred_redo_resets_the_design_and_later_planned_steps(self):
        task = make(("scout", "design", "code", "code"))
        for n in (1, 2, 3):
            run(task, n)
            end(task)
        run(task, 4)
        task.update(state="waiting", why="asks: Plan gap: which file?")
        ok, why, lines = tasks.fred(task, "redo", NOW + 9)
        self.assertEqual((ok, why), (True, ""))
        self.assertEqual([s["state"] for s in task["steps"][:4]], ["done", "planned", "done", "planned"])
        self.assertEqual((task["state"], task["current"], task["redo"], task["owner"]), ("running", 2, "which file?", "service"))
        self.assertEqual(task["steps"][1]["retries"], 0)
        self.assertEqual(lines[-1]["why"], "design redone by Fred: which file?")
        task.update(state="running", why="")
        self.assertEqual(tasks.fred(task, "redo", NOW)[:2], (False, "nothing to redo"))
        nodesign = make(("scout", "code"))
        nodesign.update(state="waiting", why="plan 130 KB, over 100")
        self.assertEqual(tasks.fred(nodesign, "redo", NOW)[:2], (False, "nothing to redo"))

    def test_fred_keep_drops_the_replan_proposal(self):
        task = make(("scout", "replan", "code"))
        task["replan"], task["replan_steps"] = {"step": 2, "before": [], "after": []}, []
        task.update(state="waiting", why="replanned: no change")
        ok, _, lines = tasks.fred(task, "keep", NOW)
        self.assertEqual((ok, task["state"], "replan" in task, lines[0]["why"]),
                         (True, "running", False, "old plan kept by Fred"))
        self.assertEqual(tasks.fred(task, "keep", NOW)[:2], (False, "no plan change waits"))

    def test_fred_confirm_covers_the_plan_waits(self):
        for why, line in (("plan ready: confirm", "plan confirmed by Fred"),
                          ("plan 130 KB, over 100", "plan accepted by Fred")):
            task = make(("scout", "design", "code"))
            run(task, 1)
            end(task)
            task.update(state="waiting", why=why)
            ok, _, lines = tasks.fred(task, "confirm", NOW)
            self.assertEqual((ok, task["state"], lines[0]["why"]), (True, "running", line), why)
        task = make(("scout", "replan", "code"))
        task["replan"] = {"step": 2, "before": [], "after": []}
        task["replan_steps"] = [tasks._blank(0, "code", "x")]
        task.update(state="waiting", why="replanned: 1 steps added")
        self.assertEqual(tasks.fred(task, "confirm", NOW)[0], True)
        self.assertEqual(task["steps"][-1]["goal"], "x")
        task.update(state="waiting", why="plan something else")
        self.assertEqual(tasks.fred(task, "confirm", NOW)[:2], (False, "nothing to confirm"))

    def test_clear_keeps_plan_md_and_the_parts(self):
        with tempfile.TemporaryDirectory() as home:
            task = make(("scout", "design"))
            for n in (1, 2):
                run(task, n)
                end(task)
                tasks.write_note(home, task, tasks.step(task, n), GOOD)
            folder = tasks.folder(home, task["id"])
            (folder / "plan").mkdir()
            (folder / "plan.md").write_text("# Plan", encoding="utf-8")
            (folder / "plan" / "01-x.md").write_text("# Part 1: x", encoding="utf-8")
            tasks.save(home, task)
            tasks.clear(home, task, keep_last=True)
            self.assertTrue((folder / "plan.md").is_file() and (folder / "plan" / "01-x.md").is_file())
            self.assertFalse((folder / "steps" / "01-scout.md").exists())

    def test_clear_returns_every_attempt_session(self):
        task = make(("code",))
        run(task, 1)
        end(task, ok=True, block_error="no HANDOFF block")
        tasks.start_step(task, 1, "s-two", {"model": "sonnet", "effort": "medium", "notes": []}, "", NOW + 5)
        with tempfile.TemporaryDirectory() as home:
            tasks.save(home, task)
            self.assertEqual(tasks.clear(home, task, keep_last=False), ["s1", "s-two"])

    def test_clear_keeps_the_last_note(self):
        with tempfile.TemporaryDirectory() as home:
            task = make(("scout", "explain", "search"))
            for n in (1, 2, 3):
                run(task, n)
                end(task)
                tasks.write_note(home, task, tasks.step(task, n), GOOD)
            self.assertEqual(task["state"], "done")
            folder = tasks.folder(home, task["id"])
            (folder / "prompt.md").write_text("the goal", encoding="utf-8")
            tasks.log(home, task["id"], [{"ts": 1.0, "step": 3, "from": "running", "to": "done"}])
            tasks.save(home, task)

            def files():
                return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())

            for n in (1, 3):
                tasks.write_facts(home, task, tasks.step(task, n), f"facts {n}")
            self.assertEqual(len(files()), 8)
            self.assertEqual(tasks.clear(home, task, keep_last=True), ["s1", "s2", "s3"])
            self.assertEqual(files(), ["chain.jsonl", "prompt.md", "steps/03-search.facts.md", "steps/03-search.md",
                                       "task.json"])
            self.assertTrue(task["cleared"])
            self.assertEqual([s["handoff"] for s in task["steps"]], ["", "", "steps/03-search.md"])
            self.assertEqual(tasks.clear(home, task, keep_last=False), ["s1", "s2", "s3"])
            self.assertFalse(folder.exists())
            self.assertIsNone(tasks.load(home, task["id"]))

    def test_brief_file_and_read_brief(self):
        task = make(("scout", "explain"))
        run(task, 1)
        self.assertEqual(tasks.brief_file(task, tasks.step(task, 1)), "steps/01-scout.brief.md")
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(tasks.read_brief(home, task, 1), "")
            path = tasks.folder(home, task["id"]) / "steps" / "01-scout.brief.md"
            path.parent.mkdir(parents=True)
            path.write_text("the brief", encoding="utf-8")
            self.assertEqual(tasks.read_brief(home, task, 1), "the brief")
            self.assertEqual(tasks.read_brief(home, task, 0), "")
            self.assertEqual(tasks.read_brief(home, task, 9), "")

    def test_write_brief_mirrors_write_note(self):
        task = make(("scout", "explain"))
        run(task, 1)
        with tempfile.TemporaryDirectory() as home:
            rel = tasks.write_brief(home, task, tasks.step(task, 1), "## Findings\nthe brief")
            self.assertEqual(rel, "steps/01-scout.brief.md")
            self.assertEqual(tasks.read_brief(home, task, 1), "## Findings\nthe brief")
            self.assertEqual(tasks.read_brief(home, task, 2), "")
            self.assertEqual(tasks.step(task, 1)["handoff"], "")  # task.json has no brief key: nothing is set

    def test_clear_keeps_the_last_brief_too(self):
        with tempfile.TemporaryDirectory() as home:
            task = make(("scout", "explain"))
            for n in (1, 2):
                run(task, n)
                end(task)
                tasks.write_note(home, task, tasks.step(task, n), GOOD)
                brief = tasks.folder(home, task["id"]) / tasks.brief_file(task, tasks.step(task, n))
                brief.write_text(f"brief {n}", encoding="utf-8")
            folder = tasks.folder(home, task["id"])
            tasks.save(home, task)
            tasks.clear(home, task, keep_last=True)
            files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
            self.assertEqual(files, ["steps/02-explain.brief.md", "steps/02-explain.md", "task.json"])

    def test_step_prompt_carries_the_plan_and_the_part(self):
        task = make(("scout", "code"))
        step = tasks.step(task, 2)
        bare = tasks.step_prompt(task, step, "NOTE")
        self.assertNotIn("$", bare)
        self.assertIn("\nWhat the earlier steps left you:\nNOTE\n\nRules for this step:", bare)
        text = tasks.step_prompt(task, step, "NOTE", plan="PLAN TEXT", part="PART TEXT")
        self.assertLess(text.index("PLAN TEXT"), text.index("What the earlier steps left you:"))
        self.assertIn("PART TEXT\n\nRules for this step:", text)
        self.assertNotIn("$", text)
        special = tasks.step_prompt(task, step, "NOTE", special="SPECIAL")
        self.assertIn("SPECIAL", special)

    def test_step_prompt_text(self):
        task = make(("scout", "code"))
        run(task, 1)
        first = tasks.step_prompt(task, tasks.step(task, 1), "")
        self.assertIn("What the earlier steps left you:\nThis is the first step: there is no handoff note yet.", first)
        code = tasks.step_prompt(task, tasks.step(task, 2), "PREVIOUS NOTE TEXT\n## Findings\nkept")
        self.assertIn("Task: Add the export\nWrite the export and test it", code)
        self.assertIn("Step 2 of 3: code. goal of code", code)
        self.assertIn("What the earlier steps left you:\nPREVIOUS NOTE TEXT\n## Findings\nkept", code)
        self.assertIn("HANDOFF\n## Goal\n", code)
        start = code.index("\nHANDOFF\n")
        heads = [code.index("\n" + h + "\n", start) for h in tasks.HEADINGS]
        self.assertEqual(heads, sorted(heads))  # the template's six headings, in order
        self.assertTrue(code.rstrip().endswith("END HANDOFF"))
        self.assertIn("`Lesson: <one sentence>`", code)
        self.assertIn("most steps have none", code)
        self.assertIn("do not run /session-handoff", code)
        self.assertNotIn("STOP:", code)
        self.assertNotIn("$", code)
        verify = tasks.step_prompt(task, tasks.step(task, 3), "note")
        self.assertIn("\nCheck the work of step 2 as the handoff note above describes it", verify)
        self.assertIn("just before the HANDOFF block", verify)
        self.assertNotIn("this session", verify)
        self.assertNotIn("with the Agent tool", verify)
        self.assertNotIn("Check the work of step", code)
        retry = tasks.step_prompt(task, tasks.step(task, 2), "note", "no HANDOFF block")
        self.assertIn("Your earlier attempt at this step ended without a handoff: no HANDOFF block. "
                      "Start again from the handoff below.", retry)
        self.assertNotIn("Your earlier attempt", code)
        long = dict(task, goal="g" * 9000)
        self.assertLess(len(tasks.step_prompt(long, tasks.step(long, 1), "")), 9000)

    def test_step_prompt_is_harness_neutral(self):
        task = make(("scout", "code"))
        text = tasks.step_prompt(task, tasks.step(task, 2), "note")
        self.assertNotIn("Agent tool", text)
        self.assertIn("do not hand the work to another agent", text)
        self.assertIn("`Next model: <tier>/<effort>`", text)
        self.assertIn("tier is haiku, sonnet or opus", text.replace("\n", " "))
        self.assertEqual(tasks.next_hint("Next model: opus/high"), ("opus", "high"))  # the hint still parses
        self.assertNotIn(chr(0x2014), tasks.PROMPT_FILE.read_text(encoding="utf-8"))

    def test_prompts_name_the_configured_person(self):
        """Plan 31: no prompt file names Fred; the step prompt's question rule names `you` (paths.you)."""
        for path in sorted(tasks.PROMPT_FILE.parent.glob("*.md")):
            self.assertNotIn("Fred", path.read_text(encoding="utf-8"), path.name)
        task = make(("scout", "code"))
        self.assertIn("- a question the next step or the user must settle", tasks.step_prompt(task, tasks.step(task, 1), ""))
        text = tasks.step_prompt(task, tasks.step(task, 1), "", you="Fred")
        self.assertIn("- a question the next step or Fred must settle", text)
        self.assertNotIn("$", text)

    def test_goal_is_cut_to_600_after_the_first_step(self):
        task = make(("scout", "code"))
        task["goal"] = "g" * 2000
        self.assertEqual(tasks.PROMPT_GOAL_MAX, 600)
        self.assertEqual(tasks.prompt_goal(task, tasks.step(task, 1)), "g" * 2000)  # step 1 has no handoff yet
        later = tasks.prompt_goal(task, tasks.step(task, 2))
        self.assertEqual((len(later), later[-1]), (600, "\u2026"))
        self.assertIn("\n" + later + "\n", tasks.step_prompt(task, tasks.step(task, 2), "note"))
        task["goal"] = "short goal"
        self.assertEqual(tasks.prompt_goal(task, tasks.step(task, 2)), "short goal")

    def test_received_puts_the_facts_under_the_brief(self):
        self.assertEqual(tasks.received("", "facts"), tasks.FIRST_STEP)
        self.assertEqual(tasks.received("BRIEF", ""), "BRIEF")
        both = tasks.received("BRIEF", "git diff --stat a..b")
        self.assertTrue(both.startswith("BRIEF\n\nFacts the service read when that step ended"))
        self.assertTrue(both.endswith("not compacted):\ngit diff --stat a..b"))
        task = make(("scout", "code"))
        text = tasks.step_prompt(task, tasks.step(task, 2), "BRIEF", facts="FACTS LINE")
        self.assertLess(text.index("BRIEF"), text.index("FACTS LINE"))
        self.assertLess(text.index("FACTS LINE"), text.index("Rules for this step:"))

    def test_lessons_for_the_step_kind_only(self):
        lines = ["- 2026-10-01 - APP - code: profile before optimizing",
                 "- 2026-10-02 - APP - scout: grep the callers first",
                 "- 2026-10-03 - APP - chat: a chat lesson reaches no step",
                 "- 2026-10-04 - MY - APP - code: a project name with a dash still parses",
                 "not a lesson line"]
        self.assertEqual(tasks.lessons_for(lines, "code"), ["2026-10-01: profile before optimizing",
                                                            "2026-10-04: a project name with a dash still parses"])
        self.assertEqual(tasks.lessons_for(lines, "scout"), ["2026-10-02: grep the callers first"])
        self.assertEqual(tasks.lessons_for(lines, "verify"), [])
        many = [f"- 2026-10-{d:02d} - APP - code: lesson {d}" for d in range(1, 10)]
        self.assertEqual(tasks.lessons_for(many, "code"), [f"2026-10-{d:02d}: lesson {d}" for d in range(5, 10)])
        task = make(("scout", "code"))
        text = tasks.step_prompt(task, tasks.step(task, 2), "note", lessons=tasks.lessons_for(lines, "code"))
        self.assertIn("Lessons from earlier code steps in this project (use one only where it applies):\n"
                      "- 2026-10-01: profile before optimizing\n", text)
        self.assertLess(text.index("Lessons from"), text.index("Rules for this step:"))
        self.assertNotIn("Lessons from", tasks.step_prompt(task, tasks.step(task, 2), "note"))

    def test_facts_file_round_trip(self):
        with tempfile.TemporaryDirectory() as home:
            task = make(("scout", "code"))
            one = tasks.step(task, 1)
            self.assertEqual(tasks.facts_file(task, one), "steps/01-scout.facts.md")
            self.assertEqual(tasks.read_facts(home, task, 1), "")
            rel = tasks.write_facts(home, task, one, "Tests: py -m unittest token=abc123\nOK")
            self.assertEqual(rel, "steps/01-scout.facts.md")
            self.assertEqual(tasks.read_facts(home, task, 1), "Tests: py -m unittest token=***\nOK")
            self.assertEqual(tasks.read_facts(home, task, 9), "")


class NoteStateTest(unittest.TestCase):
    def test_live_note(self):
        self.assertEqual(tasks.live_note("thinking"), "writing")
        self.assertEqual(tasks.live_note("HANDOFF\n## Findings\nx"), "writing")
        self.assertEqual(tasks.live_note("HANDOFF\n## Findings\nx\nEND HANDOFF"), "unchecked")

    def test_note_state_follows_the_chain(self):
        task = make()
        one, two = tasks.step(task, 1), tasks.step(task, 2)
        self.assertEqual(tasks.note_state(task, one), "")
        one["state"] = "running"
        self.assertEqual(tasks.note_state(task, one), "writing")
        self.assertEqual(tasks.note_state(task, one, "unchecked"), "unchecked")
        one.update(state="done", handoff="steps/01-scout.md")
        task["briefing"] = 1
        self.assertEqual(tasks.note_state(task, one), "checked")
        task["briefing"] = 0
        self.assertEqual(tasks.note_state(task, one), "ready")
        two["state"] = "running"
        self.assertEqual(tasks.note_state(task, one), "sent")
        last = tasks.step(task, len(task["steps"]))
        last.update(state="done", handoff="x")
        self.assertEqual(tasks.note_state(task, last), "checked")

    def test_handoff_note_of_a_handed_task(self):
        task = make(("scout", "code"))
        run(task, 1)
        end(task, question="which file?")
        tasks.fred(task, "handoff", NOW + 6)
        one = tasks.step(task, 1)
        self.assertEqual(tasks.note_state(task, one), "")  # the skill still writes it
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(tasks.read_handoff(home, task), "")
            rel = tasks.write_handoff(home, task, one, "Decided: calc.py\nNext: step 2, token sk-ant-api03-" + "x" * 40)
            self.assertEqual((rel, task["handoff_note"]), ("steps/01-handoff.md", rel))
            self.assertEqual(tasks.note_state(task, one), "handed")
            text = tasks.read_handoff(home, task)
            self.assertTrue(text.startswith("# Step 01: handoff note, session "), text)
            self.assertIn("Next: step 2", text)
            self.assertNotIn("x" * 40, text)  # masked like a step note


BALANCE_CFG = {  # plan 18: tiers over three harnesses (models.json shape of plan 5) and the balance keys
    "models": {"codex": {"gpt-6-astra": "opus", "gpt-6.1-sol": "sonnet"},
               "opencode": {"opencode-go/kimi-k3": "opus", "opencode-go/deepseek-v4.1-flash": "haiku"}},
    "tiers": {"think": [{"rung": "opus", "effort": "auto"}, {"rung": "codex:gpt-6-astra", "effort": "high"},
                        {"rung": "opencode:opencode-go/kimi-k3", "effort": "auto"}, {"rung": "fable", "effort": "auto"}],
              "write": [{"rung": "sonnet", "effort": "auto"}, {"rung": "codex:gpt-6.1-sol", "effort": "auto"},
                        {"rung": "opus", "effort": "auto"},
                        {"rung": "opencode:opencode-go/deepseek-v4.1-flash", "effort": "auto"}],
              "read": [{"rung": "haiku", "effort": "auto"}]},
    "balance_margin": 0.1, "cache_bonus": 0.1, "budget_warn_at": 0.8, "peak_hours": {},
}


def shares(by_key):
    """A Hub.budget() reduced to what step_route reads: the share per model key."""
    return {key: {"share": share} for key, share in by_key.items()}


class BalanceRouteTest(unittest.TestCase):
    """Plan 18: step 7 of step_route is the balance over the tier's rungs."""

    def route(self, kind, **kw):
        return tasks.step_route(kind, cfg=BALANCE_CFG, warn_at=0.8, **kw)

    def test_tier_names(self):
        self.assertEqual(tasks.TIERS, ("read", "write", "think"))
        self.assertEqual(tasks.TIER_RANK, {"read": "haiku", "write": "sonnet", "think": "opus"})
        self.assertEqual(tasks.RANK_TIER, {"haiku": "read", "sonnet": "write", "opus": "think", "fable": "think"})
        self.assertEqual({k: tasks.kind_tier(k) for k in ("design", "code", "explain", "scout", "test", "verify")},
                         {"design": "think", "code": "write", "explain": "write", "scout": "read", "test": "read",
                          "verify": ""})

    def test_without_cfg_the_rung_is_the_rank(self):
        route = tasks.step_route("code", budget=shares({"sonnet": 0.99}))
        self.assertEqual((route["model"], route["rung"], route["hold"]), ("sonnet", "sonnet", ""))
        self.assertEqual(route["notes"], ["rule code: sonnet/medium"])

    def test_balance_spreads_a_tier(self):
        route = self.route("code", budget=shares({"sonnet": 0.84, "gpt-6.1-sol": 0.31, "deepseek-v4.1-flash": 0.5}))
        self.assertEqual((route["model"], route["rung"], route["effort"]), ("sonnet", "codex:gpt-6.1-sol", "medium"))
        self.assertIn("balance: sonnet 84 % -> codex:gpt-6.1-sol 31 %", route["notes"])
        route = self.route("code", budget=shares({"sonnet": 0.2, "gpt-6.1-sol": 0.31}))
        self.assertEqual(route["rung"], "sonnet")
        self.assertEqual(route["notes"][-1], "balance: sonnet 20 %")

    def test_a_cheap_rung_runs_at_its_own_rank(self):
        route = self.route("code", budget=shares({"sonnet": 0.6, "gpt-6.1-sol": 0.5, "deepseek-v4.1-flash": 0.1}))
        self.assertEqual((route["model"], route["rung"]), ("haiku", "opencode:opencode-go/deepseek-v4.1-flash"))

    def test_hard_only_rungs_need_a_hard_step(self):
        budget = shares({"sonnet": 0.6, "gpt-6.1-sol": 0.5, "opus": 0.05, "deepseek-v4.1-flash": 0.4})
        self.assertEqual(self.route("code", budget=budget)["rung"], "opencode:opencode-go/deepseek-v4.1-flash")
        route = self.route("code", budget=budget, hard=True)
        self.assertEqual((route["model"], route["rung"]), ("opus", "opus"))
        route = self.route("design", budget=shares({"opus": 0.5, "gpt-6-astra": 0.6, "kimi-k3": 0.7, "fable": 0.1}))
        self.assertEqual(route["rung"], "opus")  # fable is hard only in think
        route = self.route("design", budget=shares({"opus": 0.5, "gpt-6-astra": 0.6, "kimi-k3": 0.7, "fable": 0.1}), hard=True)
        self.assertEqual((route["model"], route["rung"]), ("fable", "fable"))

    def test_rung_effort_is_used_unless_the_task_fixes_one(self):
        budget = shares({"opus": 0.9, "gpt-6-astra": 0.2, "kimi-k3": 0.95})
        route = self.route("design", budget=budget)
        self.assertEqual((route["rung"], route["effort"]), ("codex:gpt-6-astra", "high"))
        self.assertIn("rung effort: high", route["notes"])
        route = self.route("design", budget=budget, effort="max")
        self.assertEqual((route["rung"], route["effort"]), ("codex:gpt-6-astra", "max"))
        self.assertNotIn("rung effort: high", route["notes"])

    def test_previous_rung_kept_within_margin(self):
        budget = shares({"sonnet": 0.4, "gpt-6.1-sol": 0.31, "deepseek-v4.1-flash": 0.9})
        self.assertEqual(self.route("code", budget=budget)["rung"], "codex:gpt-6.1-sol")
        self.assertEqual(self.route("code", budget=budget, prev_rung="sonnet")["rung"], "sonnet")
        budget = shares({"sonnet": 0.48, "gpt-6.1-sol": 0.31, "deepseek-v4.1-flash": 0.9})
        self.assertEqual(self.route("code", budget=budget, prev_rung="sonnet", prev_age=900)["rung"], "codex:gpt-6.1-sol")
        self.assertEqual(self.route("code", budget=budget, prev_rung="sonnet", prev_age=30)["rung"], "sonnet")

    def test_verify_balances_one_rank_above_and_holds_over_pace(self):
        route = self.route("verify", checked=("sonnet", "medium"), budget=shares({"opus": 0.9, "gpt-6-astra": 0.3, "kimi-k3": 0.0}))
        self.assertEqual((route["model"], route["rung"], route["hold"]), ("opus", "codex:gpt-6-astra", ""))
        route = self.route("verify", checked=("sonnet", "medium"), budget=shares({"opus": 0.9, "gpt-6-astra": 0.95}))
        self.assertEqual((route["rung"], route["hold"]), ("opus", "opus over its pace"))
        self.assertIn("balance: every think rung over pace -> opus 90 %", route["notes"])
        self.assertIn("over pace: opus 90 % -> hold", route["notes"])
        route = self.route("verify", checked=("haiku", "low"), budget=shares({"sonnet": 0.5, "gpt-6.1-sol": 0.1}))
        self.assertEqual((route["model"], route["rung"]), ("sonnet", "codex:gpt-6.1-sol"))  # never deepseek
        route = self.route("fix", checked=("sonnet", "high"), budget=shares({"opus": 0.5, "kimi-k3": 0.0}))
        self.assertEqual(route["rung"], "opus")  # never opencode

    def test_off_rungs_are_skipped(self):
        off = lambda rung: "codex is off" if rung.startswith("codex:") else ""
        route = self.route("code", budget=shares({"sonnet": 0.84, "gpt-6.1-sol": 0.31}), refuse=off)
        self.assertEqual(route["rung"], "sonnet")
        route = self.route("scout", refuse=lambda rung: "off")
        self.assertEqual((route["rung"], route["notes"][-1]), ("haiku", "balance: no usable read rung -> haiku"))

    def test_pick_runs_as_given_and_a_refused_pick_balances(self):
        route = self.route("code", pick="codex:gpt-6.1-sol", budget=shares({"sonnet": 0.1, "gpt-6.1-sol": 0.9}))
        self.assertEqual((route["model"], route["rung"]), ("sonnet", "codex:gpt-6.1-sol"))
        self.assertFalse(any(n.startswith("balance:") for n in route["notes"]))
        off = lambda rung: "codex is off" if rung.startswith("codex:") else ""
        route = self.route("code", pick="codex:gpt-6.1-sol", refuse=off)
        self.assertEqual((route["model"], route["rung"]), ("sonnet", "sonnet"))
        self.assertIn("pick refused: codex is off -> balance", route["notes"])
        route = self.route("design", pick="opencode:opencode-go/kimi-k3")
        self.assertEqual((route["model"], route["rung"], route["notes"][1]),
                         ("opus", "opencode:opencode-go/kimi-k3", "pick: opencode:opencode-go/kimi-k3"))

    def test_an_empty_pool_verify_still_holds_over_pace(self):
        route = self.route("verify", checked=("sonnet", "medium"), budget=shares({"opus": 0.9}),
                           refuse=lambda rung: "off")
        self.assertEqual((route["rung"], route["hold"]), ("opus", "opus over its pace"))
        self.assertEqual(route["notes"][-1], "over pace: opus 90 % -> hold")
        route = self.route("verify", checked=("sonnet", "medium"), budget=shares({"opus": 0.5}),
                           refuse=lambda rung: "off")
        self.assertEqual(route["hold"], "")

    SPREAD = shares({"sonnet": 0.2, "gpt-6.1-sol": 0.5, "deepseek-v4.1-flash": 0.5})

    def test_an_unknown_pick_balances_with_a_note(self):
        route = self.route("code", pick="codex:gpt-9", budget=self.SPREAD)
        self.assertEqual(route["rung"], "sonnet")
        self.assertEqual(route["notes"][1:3], ["pick: codex:gpt-9", "pick refused: unknown model -> balance"])
        gone = lambda rung: f"model gone from models.json: {rung}" if rung == "codex:gpt-9" else ""
        route = self.route("code", pick="codex:gpt-9", budget=self.SPREAD, refuse=gone)
        self.assertIn("pick refused: model gone from models.json: codex:gpt-9 -> balance", route["notes"])


class PinRouteTest(unittest.TestCase):
    """Plan 26: config `kinds` pins a kind's rung and effort; a step's pick and the task's fixed effort come first."""

    def route(self, kind, **kw):
        return tasks.step_route(kind, cfg=BALANCE_CFG, warn_at=0.8, **kw)

    def test_a_pinned_rung_runs_as_a_pick(self):
        route = self.route("code", pin={"rung": "codex:gpt-6.1-sol", "effort": "auto"},
                           budget=shares({"gpt-6.1-sol": 0.95, "sonnet": 0.1}))
        self.assertEqual((route["model"], route["rung"]), ("sonnet", "codex:gpt-6.1-sol"))  # never balanced
        self.assertIn("pin code: codex:gpt-6.1-sol", route["notes"])
        self.assertFalse(any(n.startswith("pick:") or n.startswith("balance") for n in route["notes"]))

    def test_a_pinned_rung_that_cannot_run_routes_as_auto(self):
        refuse = lambda rung: "codex is off" if rung.startswith("codex:") else ""
        route = self.route("code", pin={"rung": "codex:gpt-6.1-sol"}, refuse=refuse)
        self.assertEqual(route["rung"], "sonnet")
        self.assertIn("pin code: codex:gpt-6.1-sol refused: codex is off -> auto", route["notes"])
        route = self.route("code", pin={"rung": "codex:gone"})
        self.assertIn("pin code: codex:gone refused: unknown model -> auto", route["notes"])

    def test_the_step_pick_beats_the_pin(self):
        route = self.route("code", pick="opus", pin={"rung": "codex:gpt-6.1-sol"})
        self.assertEqual(route["rung"], "opus")
        self.assertIn("pick: opus", route["notes"])
        self.assertFalse(any(n.startswith("pin ") for n in route["notes"]))

    def test_a_pinned_effort_is_fixed_and_capped(self):
        route = self.route("scout", pin={"rung": "auto", "effort": "high"}, demand={"reasoning": "high"})
        self.assertEqual((route["rung"], route["effort"]), ("haiku", "high"))
        self.assertIn("pin effort: high", route["notes"])
        route = self.route("scout", pin={"effort": "max"})  # haiku's cap still applies
        self.assertEqual(route["effort"], tasks.EFFORT_CAP.get("haiku", "max"))
        route = self.route("scout", pin={"effort": "high"}, effort="low")  # the task's fixed effort comes first
        self.assertEqual(route["effort"], "low")
        self.assertIn("fixed effort: low", route["notes"])

    def test_verify_and_fix_are_never_pinned(self):
        for kind in ("verify", "fix"):
            route = self.route(kind, checked=("sonnet", "medium"), pin={"rung": "haiku", "effort": "low"})
            self.assertFalse(any(n.startswith("pin") for n in route["notes"]), kind)

    def test_without_cfg_a_pinned_rung_is_ignored(self):
        route = tasks.step_route("code", pin={"rung": "codex:gpt-6.1-sol", "effort": "high"})
        self.assertEqual((route["rung"], route["effort"]), ("sonnet", "high"))


def brief(*questions):
    """A brief as compact.render writes it, with these Open questions."""
    qs = "\n".join(f"- {q}" for q in questions) or "- (none)"
    return f"## Findings\n- x\n## Files touched\n- a.py\n## Open questions\n{qs}\n## Next\nGo on"


class BoardTest(unittest.TestCase):
    """Plan 25 Task 1: open questions from the briefs, the chain log, the measure table."""

    def test_open_questions_open_and_close(self):
        task = make(("scout", "code", "document"))  # scout, code, verify, document
        briefs = {1: brief("Which exe is the real one?"), 2: brief("Which exe is the real one?", "Week or 7 days?"),
                  3: brief("Week or 7 days?")}
        self.assertEqual(tasks.open_questions(task, briefs), [
            {"q": "Which exe is the real one?", "opened": 1, "closed": 3},
            {"q": "Week or 7 days?", "opened": 2, "closed": 0}])

    def test_open_questions_ignore_none_spelling_and_missing_briefs(self):
        task = make(("scout", "code", "document"))
        briefs = {"1": brief(), "2": brief("Which  exe is the REAL one"), "3": "", "4": brief("which exe is the real one?")}
        self.assertEqual(tasks.open_questions(task, briefs), [{"q": "Which  exe is the REAL one", "opened": 2, "closed": 0}])
        self.assertEqual(tasks.open_questions(task, {}), [])
        self.assertEqual(tasks.section_items(brief("a", "b"), tasks.QUESTIONS_HEAD), ["a", "b"])

    def test_read_chain_skips_broken_lines(self):
        with tempfile.TemporaryDirectory() as home:
            task = make()
            self.assertEqual(tasks.read_chain(home, task), [])
            line = {"ts": 1.0, "step": 1, "from": "planned", "to": "running", "why": "", "session": "s1"}
            tasks.log(home, task["id"], [line, dict(line, step=2)])
            with open(tasks.folder(home, task["id"]) / "chain.jsonl", "a", encoding="utf-8") as fh:
                fh.write("{broken\n[1, 2]\n")
            tasks.log(home, task["id"], [dict(line, step=3)])
            self.assertEqual([r["step"] for r in tasks.read_chain(home, task)], [1, 2, 3])
            self.assertEqual([r["step"] for r in tasks.read_chain(home, task, limit=2)], [3])

    def done_task(self, home, project, created, ctx, meta=True):
        """scout, code, verify, all done; ctx = the three ctx_tokens; brief_meta words or files only."""
        task = make(("scout", "code"))
        task.update(project_dir=project, created=created)
        for s, tokens, (raw, sent) in zip(task["steps"], ctx, ((200, 160), (400, 300), (180, 0))):
            s.update(state="done", model="haiku", effort="low", session=f"s{s['n']}", ctx_tokens=tokens)
            if meta:
                s["brief_meta"] = {"raw_w": raw, "sent_w": sent, "cut": [], "checks": [], "by": "haiku",
                                   "cost": 0.004, "turns": 2, "fallback": ""}
            else:
                tasks.write_note(home, task, s, " ".join(["w"] * raw))
                tasks.write_brief(home, task, s, " ".join(["w"] * sent))
        tasks.save(home, task)
        return task

    def test_measure_medians_per_kind(self):
        with tempfile.TemporaryDirectory() as home:
            for k, ctx in enumerate(((30000, 90000, 50000), (40000, 110000, 70000), (50000, None, 60000))):
                self.done_task(home, "D:\\WORK\\APP", NOW + k, ctx)
            self.done_task(home, "D:\\WORK\\OTHER", NOW + 9, (1, 2, 3))  # another project
            planned = make(("scout",))
            planned.update(project_dir="D:\\WORK\\APP", created=NOW + 5)
            tasks.save(home, planned)  # its steps are planned: they add nothing but count as a task
            m = tasks.measure(home, "D:\\WORK\\APP", 10)
            self.assertEqual((m["project"], m["tasks"]), ("D:\\WORK\\APP", 4))
            self.assertEqual(m["kinds"], [
                {"kind": "scout", "steps": 3, "received": None, "context": 40000, "handoff": 200},
                {"kind": "code", "steps": 3, "received": 160, "context": 100000, "handoff": 400},
                {"kind": "verify", "steps": 3, "received": 300, "context": 60000, "handoff": 180}])
            self.assertEqual(m["hot"], "code")  # 100K from 160 words beats 60K from 300
            self.assertEqual(tasks.measure(home, "D:\\WORK\\APP", 1)["tasks"], 1)  # the newest only
            self.assertEqual(tasks.measure(home, "D:\\WORK\\NONE", 10), {"project": "D:\\WORK\\NONE", "tasks": 0,
                                                                         "kinds": [], "hot": ""})

    def test_measure_reads_the_files_without_brief_meta(self):
        with tempfile.TemporaryDirectory() as home:
            self.done_task(home, "D:\\WORK\\APP", NOW, (None, None, None), meta=False)
            m = tasks.measure(home, "D:\\WORK\\APP")
            self.assertEqual([(r["kind"], r["received"], r["context"], r["handoff"]) for r in m["kinds"]],
                             [("scout", None, None, 200), ("code", 160, None, 400), ("verify", 300, None, 180)])
            self.assertEqual(m["hot"], "")  # no context reading: nothing to name


if __name__ == "__main__":
    unittest.main()
