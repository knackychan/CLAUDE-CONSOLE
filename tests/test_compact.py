import copy
import sys
import tempfile
import unittest
from pathlib import Path

from console import compact, paths, tasks

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
FIELDS = {"findings": ["add() is in calc.py:2", "test_add covers it"], "files": ["calc.py"], "questions": [],
          "next": "Fix add() and run the test"}
RAW = ("# Step 01: scout on haiku/low, session s1\n\n## Findings\nadd() is in calc.py:2\n"
       "## Files touched\n- (none)\n## Open questions\n- (none)\n## Next\nFix add() and run the test")


def make_task(project_dir="."):
    steps = tasks.plan_steps([{"kind": "scout", "goal": "Find add()"}, {"kind": "code", "goal": "Fix add()"}], 6)
    return tasks.new_task(project_dir, "APP", "Fix add", "Fix add() in calc.py", steps, "normal", {}, "", "auto", 1.0)


class BriefTest(unittest.TestCase):
    def test_schema_and_defaults(self):
        self.assertEqual(set(compact.BRIEF_SCHEMA["required"]), {"findings", "files", "questions", "next"})
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["findings"], {"type": "array", "items": {"type": "string"}})
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["next"], {"type": "string"})
        cfg = paths.DEFAULTS
        self.assertEqual((cfg["brief_on"], cfg["brief_model"], cfg["brief_max_words"], cfg["brief_timeout_s"]),
                         (True, "haiku", 400, 60))

    def test_render_and_check(self):
        text = compact.render(FIELDS)
        self.assertEqual(text, "## Findings\n- add() is in calc.py:2\n- test_add covers it\n## Files touched\n- calc.py\n"
                               "## Open questions\n- (none)\n## Next\nFix add() and run the test")
        self.assertEqual(compact.check(text, 400), "")
        long = compact.render(dict(FIELDS, findings=["word " * 30] * 20))  # 600 words
        self.assertEqual(compact.check(long, 400), "over 400 words")
        self.assertEqual(compact.check("nothing useful", 400), "missing: ## Findings")
        empty = compact.render({"findings": [], "files": [], "questions": [], "next": ""})
        self.assertEqual(compact.check(empty, 400), "")
        self.assertIn("## Files touched\n- (none)\n## Open questions\n- (none)\n## Next\n(none)", empty)
        messy = compact.render(dict(FIELDS, findings=["two\nlines  here", "key sk-abcdefghijkl1234"], next="a\nb"))
        self.assertIn("- two lines here\n- key ***\n", messy)
        self.assertTrue(messy.endswith("## Next\na b"))

    def test_fallback_keeps_files_and_cuts_findings(self):
        raw = ("# Step 01: scout on haiku/low, session s1\n\n## Findings\n" + "a" * 3000 +
               "\n## Files touched\n- a.py (x)\n- b.py (y)\n## Open questions\n- which one?\n## Next\nDo the thing")
        text = compact.fallback("", raw)
        self.assertEqual(tasks.check_handoff(text), "")
        self.assertIn("## Files touched\n- a.py (x)\n- b.py (y)\n## Open questions\n- which one?\n## Next\nDo the thing", text)
        self.assertIn("a" * 1500, text)
        self.assertNotIn("a" * 1501, text)
        no_next = "## Findings\nseen\n## Files touched\n- (none)\n## Open questions\n- (none)"
        self.assertTrue(compact.fallback(compact.render(FIELDS), no_next).endswith("## Next\nFix add() and run the test"))
        self.assertTrue(compact.fallback("", no_next).endswith("## Next\n(none)"))
        marked = "HANDOFF\n" + RAW.split("\n\n", 1)[1] + "\nEND HANDOFF"  # a raw message with the markers
        self.assertEqual(tasks.check_handoff(compact.fallback("", marked)), "")
        self.assertEqual(tasks.check_handoff(compact.fallback("", "")), "")  # nothing to cut from still checks out

    def test_build_prompt(self):
        task = make_task()
        text = compact.build_prompt(task, tasks.step(task, 1), tasks.step(task, 2), "", RAW + "\ncost $HOME")
        self.assertTrue(text.startswith("Compact the handoff note"))
        self.assertIn("Task: Fix add", text)
        self.assertIn("Next step (2 of 3, code): Fix add()", text)
        self.assertIn("Raw handoff note of step 1 (scout):\n" + RAW, text)
        self.assertIn("cost $HOME", text)
        self.assertIn("Earlier brief (what the steps before already kept):\n(none", text)
        again = compact.build_prompt(task, tasks.step(task, 2), tasks.step(task, 3), "PREV BRIEF", RAW)
        self.assertIn("PREV BRIEF", again)
        last = compact.build_prompt(task, tasks.step(task, 3), None, "", RAW)
        self.assertIn("this was the last step", last)

    def test_run_brief_uses_the_fake(self):
        cfg = copy.deepcopy(paths.DEFAULTS)
        with tempfile.TemporaryDirectory() as project:
            task = make_task(project)
            result = compact.run_brief(cfg, FAKE, task, tasks.step(task, 1), tasks.step(task, 2), "", RAW)
        self.assertEqual(result["text"], compact.render(dict(FIELDS, files=["calc.py"])))
        self.assertEqual((result["cost"], result["fallback"], result["model"]), (0.03, "", "haiku"))
        self.assertLess(result["words"], 400)
        self.assertEqual(result["words"], len(result["text"].split()))

    def test_run_brief_falls_back_on_a_bad_answer(self):
        cfg = copy.deepcopy(paths.DEFAULTS)
        with tempfile.TemporaryDirectory() as project:
            task = make_task(project)
            one, two = tasks.step(task, 1), tasks.step(task, 2)
            long = compact.run_brief(cfg, FAKE, task, one, two, "", RAW + "\nLONG")
            self.assertEqual(long["fallback"], "over 400 words")
            self.assertEqual(long["text"], compact.fallback("", RAW + "\nLONG"))
            self.assertEqual(long["cost"], 0.03)  # the pass was paid for even though the answer was dropped
            broken = compact.run_brief(cfg, FAKE, task, one, two, "", RAW + "\nBROKEN")
            self.assertIn("no JSON", broken["fallback"])
            self.assertEqual(broken["text"], compact.fallback("", RAW + "\nBROKEN"))
            self.assertEqual(broken["cost"], 0)
            slow = compact.run_brief(dict(cfg, brief_timeout_s=1), FAKE, task, one, two, "", RAW + "\nSLOW")
            self.assertEqual(slow["fallback"], "the brief took longer than 1 s")
            self.assertEqual(slow["text"], compact.fallback("", RAW + "\nSLOW"))
            gone = compact.run_brief(cfg, ["no-such-claude-exe"], task, one, two, "", RAW)
            self.assertIn("cannot start claude", gone["fallback"])
            self.assertEqual(tasks.check_handoff(gone["text"]), "")


if __name__ == "__main__":
    unittest.main()
