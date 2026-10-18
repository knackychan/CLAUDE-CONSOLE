import copy
import sys
import tempfile
import unittest
from pathlib import Path

from console import compact, paths, tasks

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
FIELDS = {"goal": "Fix add() in calc.py", "findings": ["add() is in calc.py:2", "test_add covers it"],
          "files": ["calc.py"], "troubleshooting": [], "questions": [], "next": "Fix add() and run the test"}
RAW = ("# Step 01: scout on haiku/low, session s1\n\n## Goal\nFix add() in calc.py; this step: find add()\n"
       "## Findings\nadd() is in calc.py:2\ntest_add in tests/test_calc.py covers it and fails on a negative number\n"
       "the callers in report.py and cli.py pass ints only\n## Files touched\n- (none)\n## Troubleshooting\n- (none)\n"
       "## Open questions\n- (none)\n## Next\nFix add() and run the test")
OLD_RAW = ("# Step 01: scout on haiku/low, session s1\n\n## Findings\nadd() is in calc.py:2\n"
           "## Files touched\n- (none)\n## Open questions\n- (none)\n## Next\nFix add() and run the test")


def make_task(project_dir="."):
    steps = tasks.plan_steps([{"kind": "scout", "goal": "Find add()"}, {"kind": "code", "goal": "Fix add()"}], 6)
    return tasks.new_task(project_dir, "APP", "Fix add", "Fix add() in calc.py", steps, "normal", {}, "", "auto", 1.0)


class BriefTest(unittest.TestCase):
    def test_schema_and_defaults(self):
        self.assertEqual(compact.BRIEF_SCHEMA["required"],
                         ["goal", "findings", "files", "troubleshooting", "questions", "next"])
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["findings"], {"type": "array", "items": {"type": "string"}})
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["troubleshooting"],
                         {"type": "array", "items": {"type": "string"}})
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["goal"], {"type": "string"})
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["next"], {"type": "string"})
        cfg = paths.DEFAULTS
        self.assertEqual((cfg["brief_on"], cfg["brief_model"], cfg["brief_max_words"], cfg["brief_timeout_s"]),
                         (True, "haiku", 500, 60))

    def test_render_and_check(self):
        text = compact.render(FIELDS)
        self.assertEqual(text, "## Goal\nFix add() in calc.py\n## Findings\n- add() is in calc.py:2\n- test_add covers it\n"
                               "## Files touched\n- calc.py\n## Troubleshooting\n- (none)\n"
                               "## Open questions\n- (none)\n## Next\nFix add() and run the test")
        self.assertEqual(compact.check(text, 500), "")
        long = compact.render(dict(FIELDS, findings=["word " * 30] * 20))  # 600 words
        self.assertEqual(compact.check(long, 500), "over 500 words")
        self.assertEqual(compact.check("nothing useful", 500), "missing: ## Goal")
        empty = compact.render({"goal": "", "findings": [], "files": [], "troubleshooting": [], "questions": [],
                                "next": ""})
        self.assertEqual(compact.check(empty, 500), "")
        self.assertTrue(empty.startswith("## Goal\n(none)\n## Findings\n- (none)\n"))
        messy = compact.render(dict(FIELDS, findings=["two\nlines  here", "key sk-abcdefghijkl1234"], next="a\nb",
                                    goal="line one\n\n  line   two  "))
        self.assertIn("- two lines here\n- key ***\n", messy)
        self.assertTrue(messy.startswith("## Goal\nline one\nline two\n## Findings"))
        self.assertTrue(messy.endswith("## Next\na b"))

    def test_checks_list_every_check_in_order(self):
        brief = compact.render(FIELDS)
        found = compact.checks(brief, 500, RAW, "")
        self.assertEqual([c["name"] for c in found], ["headings", "words", "shorter", "questions", "goal",
                                                      "troubleshooting", "continuity", "paths"])
        self.assertEqual(found[4], {"name": "goal", "ok": False, "why": "cut the Goal"})  # the pass's own goal line
        self.assertTrue(all(c["ok"] for c in found if c["name"] != "goal"))
        self.assertEqual([c["name"] for c in compact.checks(brief, 500)], ["headings", "words", "shorter", "questions"])

    def test_check_rejects_a_first_brief_not_shorter_than_its_note(self):
        brief = compact.restore(FIELDS, RAW, "")
        self.assertEqual(compact.check(compact.render(brief), 500, RAW + " pad" * 40, ""), "")
        short_raw = ("## Goal\ng\n## Findings\nx\n## Files touched\n- (none)\n## Troubleshooting\n- (none)\n"
                     "## Open questions\n- (none)\n## Next\ngo")
        self.assertTrue(compact.check(compact.render(FIELDS), 500, short_raw, "").startswith(
            "not shorter than what it compacts"))

    def test_check_lets_a_rolling_brief_carry_the_earlier_brief(self):
        prev = compact.render(dict(FIELDS, findings=["earlier step found " + "x " * 30]))
        brief = compact.render(compact.restore(dict(FIELDS, findings=FIELDS["findings"] + ["earlier step found it"]),
                                               RAW, prev))
        self.assertGreater(compact.words(brief), compact.words(compact.render(FIELDS)))
        self.assertEqual(compact.check(brief, 500, RAW, prev), "")

    def test_check_rejects_a_brief_that_drops_open_questions(self):
        raw = RAW.replace("## Open questions\n- (none)", "## Open questions\n- Fred: green suite or no new failures?")
        raw += " pad" * 40
        dropped = compact.render(compact.restore(FIELDS, raw, ""))
        kept = compact.render(compact.restore(dict(FIELDS, questions=["Fred: green suite or no new failures?"]), raw, ""))
        self.assertEqual(compact.check(dropped, 500, raw, ""), "dropped the open questions")
        self.assertEqual(compact.check(kept, 500, raw, ""), "")

    def test_goal_and_troubleshooting_are_carried_whole(self):
        prev = compact.render(dict(FIELDS, troubleshooting=["py -3.12 fails here: use py -3.14"]))
        raw = RAW.replace("## Troubleshooting\n- (none)", "## Troubleshooting\n- the fake needs PYTHONUTF8=1")
        goal, trouble = compact.carried(raw, prev)
        self.assertEqual(goal, ["Fix add() in calc.py; this step: find add()"])
        self.assertEqual(trouble, ["py -3.12 fails here: use py -3.14", "the fake needs PYTHONUTF8=1"])
        paraphrased = dict(FIELDS, troubleshooting=["use a newer python"])
        self.assertEqual(compact.check(compact.render(paraphrased), 500, raw, prev), "cut the Goal")
        self.assertEqual(compact.check(compact.render(dict(paraphrased, goal=goal[0])), 500, raw, prev),
                         "cut the Troubleshooting")
        fixed = compact.restore(paraphrased, raw, prev)
        self.assertEqual((fixed["goal"], fixed["troubleshooting"]), (goal[0], trouble))
        self.assertEqual(paraphrased["troubleshooting"], ["use a newer python"])  # the answer itself is not changed
        self.assertEqual(compact.check(compact.render(fixed), 500, raw, prev), "")
        self.assertEqual(compact.carried(OLD_RAW, "")[0], [])  # an old note has no Goal: nothing to carry
        self.assertEqual(compact.carried(OLD_RAW, prev)[0], ["Fix add() in calc.py"])  # the earlier brief's Goal

    def test_continuity_keeps_a_file_of_the_earlier_files_touched(self):
        prev = compact.render(dict(FIELDS, files=["console/tasks.py (six headings)"]))
        raw = RAW.replace("## Files touched\n- (none)", "## Files touched\n- console/compact.py (checks)")
        lost = compact.restore(dict(FIELDS, files=["console/compact.py"]), raw, prev)
        self.assertEqual(compact.check(compact.render(lost), 500, raw, prev), "names no file of the earlier Files touched")
        kept = compact.restore(dict(FIELDS, files=["console/compact.py", "tasks.py"]), raw, prev)  # a short name counts
        self.assertEqual(compact.check(compact.render(kept), 500, raw, prev), "")
        first = compact.restore(dict(FIELDS, files=[]), raw, "")
        self.assertNotIn("names no file", compact.check(compact.render(first), 500, raw, ""))  # no earlier list

    def test_no_invented_path(self):
        brief = compact.restore(dict(FIELDS, findings=["add() is in calc.py:2", "see web/app.js:40"]), RAW, "")
        self.assertEqual(compact.check(compact.render(brief), 500, RAW, ""), "names a path no step touched: web/app.js")
        self.assertEqual(compact.check(compact.render(brief), 500, RAW, "", touched=["web/app.js"]), "")
        self.assertEqual(compact.paths("calc.py:2, tests/test_calc.py::test_add, D:\\WORK\\APP\\x.py, ./y.md, e.g. "
                                       "i.e. 0.03 v1.2.3 https://code.claude.com/docs/a.html README.md"),
                         {"calc.py", "tests/test_calc.py", "d:/work/app/x.py", "y.md", "readme.md"})

    def test_fallback_keeps_goal_files_trouble_and_cuts_findings(self):
        raw = ("# Step 01: scout on haiku/low, session s1\n\n## Goal\nship it\n## Findings\n" + "a" * 3000 +
               "\nlast line\n## Files touched\n- a.py (x)\n- b.py (y)\n## Troubleshooting\n- pip is offline\n"
               "## Open questions\n- which one?\n## Next\nDo the thing")
        prev = compact.render(dict(FIELDS, files=["a.py (x)", "c.py (z)"], troubleshooting=["tests need -s tests"]))
        text = compact.fallback(prev, raw)
        self.assertEqual(tasks.check_handoff(text), "")
        self.assertIn("## Goal\nship it\n## Findings\n", text)
        self.assertIn("## Files touched\n- a.py (x)\n- b.py (y)\n- c.py (z)\n## Troubleshooting\n- tests need -s tests\n"
                      "- pip is offline\n## Open questions\n- which one?\n## Next\nDo the thing", text)
        self.assertIn("a" * 1500, text)
        self.assertNotIn("a" * 1501, text)
        self.assertEqual(compact.cut_lines(compact._sections(raw)["## Findings"]), ["a" * 3000, "last line"])
        no_next = "## Findings\nseen\n## Files touched\n- (none)\n## Open questions\n- (none)"
        self.assertTrue(compact.fallback(compact.render(FIELDS), no_next).endswith("## Next\nFix add() and run the test"))
        self.assertTrue(compact.fallback("", no_next).endswith("## Next\n(none)"))
        marked = "HANDOFF\n" + RAW.split("\n\n", 1)[1] + "\nEND HANDOFF"  # a raw message with the markers
        self.assertEqual(tasks.check_handoff(compact.fallback("", marked)), "")
        self.assertEqual(tasks.check_handoff(compact.fallback("", "")), "")  # nothing to cut from still checks out
        self.assertEqual(tasks.check_handoff(compact.fallback("", OLD_RAW)), "")  # an old note gives six headings

    def test_a_note_under_the_cap_is_its_own_brief(self):
        """Plan 28 (D14): no pass rewrites a handoff that fits brief_max_words; nothing of it is cut."""
        cfg = copy.deepcopy(paths.DEFAULTS)
        text = compact.as_is(cfg, "", RAW)
        self.assertEqual(tasks.check_handoff(text), "")
        self.assertIn("test_add in tests/test_calc.py covers it and fails on a negative number", text)
        self.assertEqual(text, compact.fallback("", RAW, cut=False))
        self.assertEqual(compact.as_is(dict(cfg, brief_max_words=20), "", RAW), "")  # over the cap: the pass runs
        self.assertEqual(compact.as_is(cfg, "", "no headings at all"), "")
        long_raw = RAW.replace("add() is in calc.py:2", "a" * 3000)
        self.assertIn("a" * 3000, compact.as_is(cfg, "", long_raw))  # one long word: under the cap, kept whole
        self.assertNotIn("a" * 3000, compact.fallback("", long_raw))  # the old fallback cuts it

    def test_build_prompt(self):
        task = make_task()
        text = compact.build_prompt(task, tasks.step(task, 1), tasks.step(task, 2), "", RAW + "\ncost $HOME")
        self.assertTrue(text.startswith("Compact the handoff note"))
        self.assertIn("Task: Fix add", text)
        self.assertIn("Next step (2 of 3, code): Fix add()", text)
        self.assertIn("Raw handoff note of step 1 (scout):\n" + RAW, text)
        self.assertIn("cost $HOME", text)
        self.assertIn("Earlier brief (what the steps before already kept):\n(none", text)
        self.assertIn("goal (the Goal lines of the raw note, copied whole)", text)
        self.assertIn("troubleshooting (every Troubleshooting line", text)
        again = compact.build_prompt(task, tasks.step(task, 2), tasks.step(task, 3), "PREV BRIEF", RAW)
        self.assertIn("PREV BRIEF", again)
        last = compact.build_prompt(task, tasks.step(task, 3), None, "", RAW)
        self.assertIn("this was the last step", last)

    def test_prompt_names_the_goal_and_a_word_target(self):
        task = make_task()
        task["goal"] = "Goal: " + "g" * 600
        text = compact.build_prompt(task, tasks.step(task, 1), tasks.step(task, 2), "", RAW, 120)
        self.assertIn("Task: Goal: ggg", text)
        self.assertNotIn("g" * 400, text)
        self.assertIn("at most 120 words in all", text)
        self.assertIn("never drop one", text)
        self.assertNotIn("$", text)
        self.assertEqual(compact.budget({"brief_max_words": 500}, "w " * 1000, ""), 500)
        self.assertEqual(compact.budget({"brief_max_words": 500}, "w " * 50, ""), 60)
        self.assertEqual(compact.budget({"brief_max_words": 500}, "w " * 200, "w " * 100), 180)

    def test_run_brief_uses_the_fake(self):
        cfg = dict(copy.deepcopy(paths.DEFAULTS), brief_max_words=500)  # the plan 23 default, pinned here
        with tempfile.TemporaryDirectory() as project:
            task = make_task(project)
            result = compact.run_brief(cfg, FAKE, task, tasks.step(task, 1), tasks.step(task, 2), "", RAW)
        self.assertEqual(result["text"], compact.render(compact.restore(FIELDS, RAW, "")))
        self.assertIn("## Goal\nFix add() in calc.py; this step: find add()\n", result["text"])
        self.assertEqual((result["cost"], result["fallback"], result["model"], result["cut"]), (0.03, "", "haiku", []))
        self.assertEqual(result["turns"], 5)
        self.assertTrue(all(c["ok"] for c in result["checks"]))
        self.assertEqual(len(result["checks"]), 8)
        self.assertLess(result["words"], 500)
        self.assertEqual(result["words"], len(result["text"].split()))

    def test_run_brief_cuts_an_over_long_answer_instead_of_dropping_it(self):
        cfg = dict(copy.deepcopy(paths.DEFAULTS), brief_max_words=500)  # the plan 23 default, pinned here
        with tempfile.TemporaryDirectory() as project:
            task = make_task(project)
            raw = RAW.replace("## Files touched", "word " * 120 + "\n## Files touched") + "\nLONG"
            result = compact.run_brief(cfg, FAKE, task, tasks.step(task, 1), tasks.step(task, 2), "", raw)
        self.assertEqual(result["fallback"], "")
        self.assertGreater(len(result["cut"]), 0)
        self.assertTrue(result["cut"][-1].startswith("finding 79 says"))  # the last findings go first
        self.assertLessEqual(result["words"], 500)
        self.assertEqual(result["words"], len(result["text"].split()))
        self.assertIn("finding 0 says", result["text"])
        self.assertNotIn("finding 79 says", result["text"])
        self.assertEqual(compact.check(result["text"], 500), "")

    def test_cut_keeps_every_heading_but_findings(self):
        fields = dict(FIELDS, findings=[f"finding {i} " + "w " * 40 for i in range(20)], files=["calc.py"],
                      troubleshooting=["pip is offline"], questions=["which pi?"], next="Fix add()")
        cut = compact.cut(fields, 200)
        self.assertEqual((cut["files"], cut["troubleshooting"], cut["questions"], cut["next"], cut["goal"]),
                         (["calc.py"], ["pip is offline"], ["which pi?"], "Fix add()", FIELDS["goal"]))
        self.assertLessEqual(compact.words(compact.render(cut)), 200)
        self.assertEqual(cut["findings"], fields["findings"][:len(cut["findings"])])
        self.assertEqual(len(fields["findings"]), 20)  # the answer itself is not changed
        self.assertIsNone(compact.cut(dict(fields, questions=["q " * 300]), 200))  # one finding left, still over

    def test_run_brief_falls_back_on_a_bad_answer(self):
        cfg = dict(copy.deepcopy(paths.DEFAULTS), brief_max_words=500)  # the plan 23 default, pinned here
        with tempfile.TemporaryDirectory() as project:
            task = make_task(project)
            one, two = tasks.step(task, 1), tasks.step(task, 2)
            huge = compact.run_brief(cfg, FAKE, task, one, two, "", RAW + "\nHUGE")
            self.assertEqual(huge["fallback"], "over 500 words")  # one finding alone is too long: nothing to cut
            self.assertEqual(huge["text"], compact.fallback("", RAW + "\nHUGE"))
            self.assertEqual(huge["cost"], 0.03)  # the pass was paid for even though the answer was dropped
            self.assertEqual(huge["checks"][1], {"name": "words", "ok": False, "why": "over 500 words"})
            broken = compact.run_brief(cfg, FAKE, task, one, two, "", RAW + "\nBROKEN")
            self.assertIn("no JSON", broken["fallback"])
            self.assertEqual(broken["text"], compact.fallback("", RAW + "\nBROKEN"))
            self.assertEqual((broken["cost"], broken["checks"], broken["turns"]), (0, [], 0))
            slow = compact.run_brief(dict(cfg, brief_timeout_s=1), FAKE, task, one, two, "", RAW + "\nSLOW")
            self.assertEqual(slow["fallback"], "the brief took longer than 1 s")
            self.assertEqual(slow["text"], compact.fallback("", RAW + "\nSLOW"))
            gone = compact.run_brief(cfg, ["no-such-claude-exe"], task, one, two, "", RAW)
            self.assertIn("cannot start claude", gone["fallback"])
            self.assertEqual(tasks.check_handoff(gone["text"]), "")

    def test_brief_meta_shape(self):
        res = {"text": "x", "cost": 0.0123456789, "words": 290, "model": "haiku", "cut": ["finding 9"],
               "fallback": "", "checks": [{"name": "headings", "ok": True, "why": ""}], "turns": 2}
        meta = compact.brief_meta(res, RAW)
        self.assertEqual(sorted(meta), ["by", "checks", "cost", "cut", "fallback", "raw_w", "sent_w", "turns"])
        self.assertEqual((meta["raw_w"], meta["sent_w"], meta["cut"], meta["by"], meta["cost"], meta["turns"],
                          meta["fallback"]),
                         (compact.words(compact.note_body(RAW)), 290, ["finding 9"], "haiku", 0.012346, 2, ""))
        self.assertNotIn("# Step", compact.note_body(RAW))
        off = compact.brief_meta({"text": "y", "cost": 0, "words": 40, "fallback": "brief is off"}, RAW)
        self.assertEqual((off["by"], off["checks"], off["turns"], off["cut"], off["fallback"]),
                         ("code", [], 0, [], "brief is off"))


class AskTest(unittest.TestCase):
    """Plan 44 T4: _ask's optional supervisor arguments leave the other passes' command as it was."""

    def run_ask(self, body, code=0, **kw):
        import json
        import subprocess
        from unittest import mock
        seen = []

        def fake(cmd, **k):
            seen.append((cmd, k))
            if isinstance(body, Exception):
                raise body
            return subprocess.CompletedProcess(cmd, code, json.dumps(body).encode(), b"")
        cfg, info = copy.deepcopy(paths.DEFAULTS), {}
        with mock.patch.object(compact.subprocess, "run", side_effect=fake):
            try:
                got = compact._ask(cfg, FAKE, ".", "p", {"type": "object"}, info, **kw)
            except compact.BriefError as exc:
                got = exc
        return got, info, seen[0]

    def test_default_command_and_timeout_unchanged(self):
        from console import claude_cli
        ok = {"is_error": False, "total_cost_usd": 0.01, "num_turns": 2, "structured_output": {"a": 1}}
        got, info, (cmd, kw) = self.run_ask(ok)
        self.assertEqual(cmd, claude_cli.brief_command(FAKE, paths.DEFAULTS["brief_model"], {"type": "object"}))
        self.assertEqual(kw["timeout"], paths.DEFAULTS["brief_timeout_s"])
        self.assertEqual(got, ({"a": 1}, 0.01))
        self.assertEqual(info, {"turns": 2, "cost": 0.01})

    def test_info_keeps_the_reported_cost_of_a_failure(self):
        import subprocess
        got, info, _ = self.run_ask({"is_error": True, "subtype": "x", "total_cost_usd": 0.02})
        self.assertIsInstance(got, compact.BriefError)
        self.assertEqual(info["cost"], 0.02)
        got, info, _ = self.run_ask({"is_error": False, "total_cost_usd": 0.03, "structured_output": {}}, code=2)
        self.assertIsInstance(got, compact.BriefError)
        self.assertEqual(info["cost"], 0.03)
        got, info, _ = self.run_ask(subprocess.TimeoutExpired("c", 1))
        self.assertIsNone(info["cost"])
        got, info, _ = self.run_ask(OSError("no exe"))
        self.assertEqual(info["cost"], 0.0)
        got, info, (cmd, _) = self.run_ask({"is_error": False, "total_cost_usd": 0.01, "structured_output": {}},
                                           max_cost=0.5, safe_mode=True)
        self.assertEqual(cmd[-5:], ["--max-budget-usd", "0.5", "--safe-mode", "--disallowedTools", "mcp__*"])


if __name__ == "__main__":
    unittest.main()
