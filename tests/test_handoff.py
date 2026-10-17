import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import compact, handoff, paths, tasks

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
NOTE = ("## Goal\nFix add() in calc.py\n## Findings\nadd() is in calc.py:2\ntest_add covers it\n"
        "## Files touched\n- calc.py\n## Troubleshooting\n- py -3.12 fails here: use py -3.14\n"
        "## Open questions\n- which sign rule?\n## Next\nFix add() and run the test")


def cfg(**over):
    return dict(copy.deepcopy(paths.DEFAULTS), **over)


def make(home, project, with_notes=(1,)):
    """A three-step task whose steps 1 and 3 are done, step 2 failed once; `with_notes` lists the steps with a saved note."""
    steps = tasks.plan_steps([{"kind": "scout", "goal": "Find add()"}, {"kind": "code", "goal": "Fix add()"}], 6)
    task = tasks.new_task(str(project), "APP", "Fix add", "Fix add() in calc.py", steps, "normal", {}, "", "auto", 1.0)
    for s in task["steps"]:
        s.update(model="haiku", effort="low", session=f"s{s['n']}", state="done", cost=0.05, verdict="")
    task["steps"][1]["attempts"] = [{"session": "s2", "cost": 0.02, "started": 1.0, "ended": 2.0,
                                     "why": "ended without a handoff", "final": False}]
    task["steps"][1]["retries"] = 1
    task["steps"][2].update(kind="verify", verdict="PASS", verdict_detail="")
    task.update(state="stopped", why="stopped by Fred", current=3, last_good=3)
    tasks.save(home, task)
    for n in with_notes:
        tasks.write_note(home, task, tasks.step(task, n), NOTE)
    return task


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()

    def test_schema_and_defaults(self):
        self.assertEqual(handoff.HANDOFF_SCHEMA["required"],
                         ["goal", "findings", "files", "troubleshooting", "questions", "next"])
        self.assertIs(handoff.HANDOFF_SCHEMA["additionalProperties"], False)
        self.assertEqual(handoff.HANDOFF_SCHEMA["properties"]["findings"], {"type": "array", "items": {"type": "string"}})
        c = paths.DEFAULTS
        self.assertEqual((c["handoff_on"], c["handoff_model"], c["handoff_max_words"], c["handoff_timeout_s"]),
                         (True, "haiku", 800, 90))

    def test_digest_names_every_step_and_marks_a_missing_note(self):
        task = make(self.home, self.project)
        text = handoff.digest(self.home, task, "finish the sign rule")
        self.assertTrue(text.startswith(f"Task {task['id']}"))
        for line in ("01 scout", "02 code", "03 verify"):
            self.assertIn(line, text)
        self.assertIn("add() is in calc.py:2", text)  # step 1's note
        self.assertIn("No saved result. Do not assume this step completed.", text)  # steps 2 and 3 have none
        self.assertEqual(text.count("No saved result. Do not assume this step completed."), 2)
        self.assertIn("ended without a handoff", text)  # the failed attempt's why
        self.assertIn("PASS", text)
        self.assertIn("which sign rule?", text)
        self.assertIn("finish the sign rule", text)

    def test_digest_never_reads_streams_or_transcripts(self):
        task = make(self.home, self.project)
        runs = self.home / "tasks" / task["id"] / "runs"
        runs.mkdir(parents=True)
        (runs / "s1.jsonl").write_text("TRANSCRIPT-ONLY-WORDS", encoding="utf-8")
        self.assertNotIn("TRANSCRIPT-ONLY-WORDS", handoff.digest(self.home, task, ""))

    def test_digest_is_cut_from_the_bottom_and_keeps_its_head(self):
        task = make(self.home, self.project, with_notes=(1, 2, 3))
        for n in (1, 2, 3):
            tasks.write_note(self.home, task, tasks.step(task, n), NOTE.replace("calc.py:2", "word " * 2500))
        text = handoff.digest(self.home, task, "")
        self.assertLessEqual(len(text), handoff.DIGEST_MAX)
        self.assertTrue(text.startswith(f"Task {task['id']}"))
        self.assertIn("01 scout", text)  # the step lines are never cut
        self.assertIn("03 verify", text)
        self.assertIn("[digest cut", text)

    def test_build_prompt_is_short_and_names_the_headings(self):
        task = make(self.home, self.project)
        digest = handoff.digest(self.home, task, "x")
        prompt = handoff.build_prompt(task, "finish the sign rule", digest)
        self.assertTrue(prompt.startswith(handoff.PROMPT_HEAD))
        for heading in tasks.HEADINGS:
            self.assertIn(heading[3:], prompt)
        self.assertIn(digest, prompt)
        self.assertIn("finish the sign rule", prompt)
        self.assertIn("unavailable", prompt)
        self.assertLess(len(prompt.replace(digest, "")), 4000)  # under 1,000 tokens without the digest

    def test_render_emits_the_six_headings_in_order(self):
        task = make(self.home, self.project)
        fields = {"goal": "Fix add()", "findings": ["01: add() is in calc.py"], "files": ["calc.py"],
                  "troubleshooting": [], "questions": [], "next": "Run the test"}
        text = handoff.render(fields, task, "finish the sign rule")
        at = [text.index(h) for h in tasks.HEADINGS]
        self.assertEqual(at, sorted(at))
        self.assertIn(task["id"], text.split("## Findings")[0])  # Goal carries the identity ...
        self.assertIn("finish the sign rule", text.split("## Findings")[0])  # ... and the remaining-work instructions
        self.assertIn("- 01: add() is in calc.py\n", text)
        self.assertIn("## Troubleshooting\nNone recorded.\n", text)
        self.assertEqual(handoff.check(text, 800), "")
        self.assertEqual(tasks.check_handoff(text), "")

    def test_check_rejects_a_missing_heading_and_an_over_long_block(self):
        task = make(self.home, self.project)
        fields = {"goal": "g", "findings": ["f"], "files": [], "troubleshooting": [], "questions": [], "next": "n"}
        text = handoff.render(fields, task, "")
        self.assertEqual(handoff.check(text, 800), "")
        self.assertEqual(handoff.check(text.replace("## Next", "## Later"), 800), "missing: ## Next")
        long = handoff.render(dict(fields, findings=["word " * 30] * 40), task, "")
        self.assertEqual(handoff.check(long, 800), "over 800 words")

    def test_fallback_is_code_only_and_tags_every_step(self):
        task = make(self.home, self.project)
        text = handoff.fallback(self.home, task, "finish the sign rule")
        self.assertEqual(tasks.check_handoff(text), "")
        self.assertIn("Step 01 (scout, done)", text)
        self.assertIn("Step 02 (code, done)", text)
        self.assertIn("No saved result. Do not assume this step completed.", text)
        self.assertIn("[excerpt; full text in the cited evidence]", text)
        self.assertIn("py -3.12 fails here", text)  # troubleshooting kept
        self.assertIn("calc.py", text.split("## Troubleshooting")[0].split("## Files touched")[1])
        self.assertIn("finish the sign rule", text)

    def test_run_uses_the_fake_haiku_pass(self):
        task = make(self.home, self.project)
        res = handoff.run(cfg(), FAKE, self.home, task, "finish the sign rule")
        self.assertEqual((res["fallback"], res["model"], res["cost"]), ("", "haiku", 0.03))
        self.assertIn("fake handoff summary", res["text"])
        self.assertIn("finish the sign rule", res["text"])  # code put the instructions in the Goal
        self.assertEqual(tasks.check_handoff(res["text"]), "")
        self.assertEqual(res["words"], len(res["text"].split()))

    def test_run_asks_the_handoff_model_with_the_handoff_timeout(self):
        task = make(self.home, self.project)
        seen = {}
        real = compact.claude_cli.brief_command

        def spy(exe, model, schema):
            seen["model"], seen["schema"] = model, schema
            return real(exe, model, schema)

        with mock.patch.object(compact.claude_cli, "brief_command", spy):
            handoff.run(cfg(handoff_model="sonnet", brief_model="haiku"), FAKE, self.home, task, "")
        self.assertEqual((seen["model"], seen["schema"]), ("sonnet", handoff.HANDOFF_SCHEMA))

    def test_run_falls_back_on_every_failure_and_never_raises(self):
        task = make(self.home, self.project)
        expected = handoff.fallback(self.home, task, "BROKEN")
        broken = handoff.run(cfg(), FAKE, self.home, task, "BROKEN")
        self.assertIn("no JSON", broken["fallback"])
        self.assertEqual((broken["text"], broken["cost"], broken["model"]), (expected, 0, ""))
        slow = handoff.run(cfg(handoff_timeout_s=1), FAKE, self.home, task, "SLOW")
        self.assertIn("took longer than 1 s", slow["fallback"])
        gone = handoff.run(cfg(), ["no-such-claude-exe"], self.home, task, "")
        self.assertIn("cannot start claude", gone["fallback"])
        noexe = handoff.run(cfg(), None, self.home, task, "")
        self.assertIn("claude.exe", noexe["fallback"])
        off = handoff.run(cfg(handoff_on=False), FAKE, self.home, task, "")
        self.assertEqual(off["fallback"], "the handoff summary is off")
        for res in (broken, slow, gone, noexe, off):
            self.assertEqual(tasks.check_handoff(res["text"]), "")
            self.assertEqual(res["words"], len(res["text"].split()))

    def test_run_falls_back_on_an_over_long_answer_and_keeps_its_cost(self):
        task = make(self.home, self.project)
        res = handoff.run(cfg(), FAKE, self.home, task, "LONG")
        self.assertEqual(res["fallback"], "over 800 words")
        self.assertEqual((res["cost"], res["model"]), (0.03, ""))  # the pass was paid for, its answer dropped
        self.assertIn("Step 01 (scout, done)", res["text"])

    def test_run_masks_secrets(self):
        task = make(self.home, self.project)
        res = handoff.run(cfg(handoff_on=False), FAKE, self.home, task, "key sk-abcdefghijkl1234")
        self.assertNotIn("sk-abcdefghijkl1234", res["text"])


if __name__ == "__main__":
    unittest.main()
