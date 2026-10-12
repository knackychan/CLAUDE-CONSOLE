import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import claude_cli, levers, prep, tasks

GOOD = ("## Findings\nadd() is in calc.py:2\n## Files touched\n- calc.py (fixed add)\n"
        "## Open questions\n- (none)\n## Next\nRun the tests")


class RulesTest(unittest.TestCase):
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
        self.rule("draft", "haiku", "low", "")

    def test_rule_proofread_haiku_low(self):
        self.rule("proofread", "haiku", "low", "")

    def test_rule_edit_haiku_low(self):
        self.rule("edit", "haiku", "low", "")

    def test_rule_code_sonnet_medium(self):
        self.rule("code", "sonnet", "medium", "")

    def test_rule_document_sonnet_medium(self):
        self.rule("document", "sonnet", "medium", "")

    def test_rule_explain_sonnet_medium(self):
        self.rule("explain", "sonnet", "medium", "Read,Grep,Glob")

    def test_rule_debug_sonnet_high(self):
        self.rule("debug", "sonnet", "high", "")

    def test_rule_test_haiku_low(self):
        self.rule("test", "haiku", "low", "Bash,Read,Grep,Glob")

    def test_rule_design_opus_high(self):
        self.rule("design", "opus", "high", "Read,Grep,Glob,WebFetch,WebSearch")

    def test_kind_sets_safe_id_and_disallow(self):
        self.assertEqual(tasks.RULES["verify"][2], "Bash,Read,Grep,Glob")
        self.assertEqual(tasks.RULES["fix"][2], "")
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

    def test_budget_pressure_moves_a_step_down(self):
        route = tasks.step_route("design", budget={"opus": 0.84})
        self.assertEqual((route["model"], route["effort"]), ("sonnet", "xhigh"))
        self.assertTrue(any(n.startswith("budget:") for n in route["notes"]))
        route = tasks.step_route("code", budget={"sonnet": 0.9})
        self.assertEqual((route["model"], route["effort"]), ("haiku", "high"))
        route = tasks.step_route("verify", checked=("sonnet", "medium"), budget={"opus": 0.9})
        self.assertEqual((route["model"], route["effort"]), ("opus", "medium"))
        self.assertEqual(route["hold"], "opus over its pace")
        route = tasks.step_route("scout", budget={"haiku": 0.99})  # haiku is never moved down
        self.assertEqual((route["model"], route["effort"], route["hold"]), ("haiku", "low", ""))
        route = tasks.step_route("design", budget={"opus": 0.79})  # under the line
        self.assertEqual((route["model"], route["effort"]), ("opus", "high"))
        route = tasks.step_route("design", budget={"opus": 0.5}, warn_at=0.4)
        self.assertEqual(route["model"], "sonnet")

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
        self.assertEqual(tasks.check_handoff(GOOD.replace("\n## Next\nRun the tests", "")), "missing: ## Next")
        swapped = GOOD.replace("## Files touched", "## TMP").replace("## Open questions", "## Files touched")
        swapped = swapped.replace("## TMP", "## Open questions")
        self.assertEqual(tasks.check_handoff(swapped), "headings out of order")
        for empty in ("## Findings\n\n## Files touched", "## Findings\n   \n## Files touched"):
            block = GOOD.replace("## Findings\nadd() is in calc.py:2\n## Files touched", empty)
            self.assertEqual(tasks.check_handoff(block), "Findings is empty")
        inline = GOOD.replace("## Next\n", "## Next: ")  # a heading must be a whole line
        self.assertEqual(tasks.check_handoff(inline), "missing: ## Next")

    def test_next_hint(self):
        self.assertEqual(tasks.next_hint(GOOD + "\nNext model: sonnet/high"), ("sonnet", "high"))
        self.assertIsNone(tasks.next_hint(GOOD + "\nNext model: gpt/high"))
        self.assertIsNone(tasks.next_hint(GOOD))
        both = "Next model: gpt/high\nNext model: opus/low"  # the first one routing.parse accepts
        self.assertEqual(tasks.next_hint(both), ("opus", "low"))

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
        self.assertEqual(tasks.step(task, 1)["state"], "done")  # the asking step ends; step 2 never starts
        self.assertEqual([(c["from"], c["to"]) for c in lines], [("running", "done"), ("task:waiting", "task:handed")])
        self.assertEqual(tasks.fred(task, "handoff", NOW + 7)[:2], (False, "task is handed"))
        ok, _, lines = tasks.fred(task, "done", NOW + 8)  # handed over, then Fred calls it done
        self.assertEqual((ok, task["state"], task["why"]), (True, "done", "marked done by Fred"))
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

            self.assertEqual(len(files()), 6)
            self.assertEqual(tasks.clear(home, task, keep_last=True), ["s1", "s2", "s3"])
            self.assertEqual(files(), ["chain.jsonl", "prompt.md", "steps/03-search.md", "task.json"])
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

    def test_step_prompt_text(self):
        task = make(("scout", "code"))
        run(task, 1)
        first = tasks.step_prompt(task, tasks.step(task, 1), "")
        self.assertIn("This is the first step: there is no handoff note yet.", first)
        code = tasks.step_prompt(task, tasks.step(task, 2), "PREVIOUS NOTE TEXT\n## Findings\nkept")
        self.assertIn("Task: Add the export\nWrite the export and test it", code)
        self.assertIn("Step 2 of 3: code. goal of code", code)
        self.assertIn("PREVIOUS NOTE TEXT\n## Findings\nkept", code)
        self.assertIn("HANDOFF\n## Findings", code)
        self.assertIn("END HANDOFF", code)
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
                      "Start again from the note above.", retry)
        self.assertNotIn("Your earlier attempt", code)
        long = dict(task, goal="g" * 9000)
        self.assertLess(len(tasks.step_prompt(long, tasks.step(long, 1), "")), 9000)


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


if __name__ == "__main__":
    unittest.main()
