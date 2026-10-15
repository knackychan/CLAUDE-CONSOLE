import tempfile
import time
import unittest
from pathlib import Path

from console import levers, prep, routing


class LeversTest(unittest.TestCase):
    def test_escalate_step(self):
        cases = {("haiku", "low"): ("haiku", "medium"), ("sonnet", "medium"): ("sonnet", "high"),
                 ("sonnet", "high"): ("opus", "high"), ("opus", "high"): ("fable", "high"),
                 ("opus", "xhigh"): ("fable", "xhigh"), ("fable", "high"): ("fable", "xhigh"),
                 ("fable", "max"): None, ("gpt", "low"): None}
        for (model, effort), want in cases.items():
            self.assertEqual(levers.escalate_step(model, effort), want, (model, effort))

    def test_misses_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = time.mktime((2026, 10, 10, 12, 0, 0, 0, 0, -1))
            line = levers.miss_line("CALC", "mechanical", "sonnet/low", "sonnet/medium",
                                    "test_add - 3 != 4 token=abc", now)
            self.assertEqual(line, "- 2026-10-10 - CALC - mechanical: sonnet/low failed "
                                   "(test_add - 3 != 4 token=***); next time start at sonnet/medium.")
            levers.add_miss(Path(tmp), line)
            levers.add_miss(Path(tmp), levers.miss_line("OTHER", "", "opus/high", "fable/high", "", now))
            self.assertEqual(levers.read_misses(Path(tmp), "CALC"), [line])
            self.assertIn("unrouted: opus/high failed (verifier FAIL)", levers.read_misses(Path(tmp), "OTHER")[0])
            text = (Path(tmp) / "routing-misses.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Routing misses"))
            self.assertEqual(levers.read_misses(Path(tmp) / "nope", "CALC"), [])
            self.assertIn(line, prep.build_prompt("x", [line]))
            self.assertIn("\n(none)\n", prep.build_prompt("x"))
            used = levers.used_line("CALC", "code", "opus/high", "20261015-085403-e56d", 3, now)
            self.assertEqual(used, "- 2026-10-10 - CALC - code: floor opus/high used by task 20261015-085403-e56d "
                                   "step 03; it passed.")
            self.assertIsNone(routing.floor([used], "code"))  # a used line is never a floor itself

    def test_after_verify(self):
        self.assertEqual(levers.after_verify("PASS"), ("handoff", "done"))
        self.assertEqual(levers.after_verify("FAIL"), ("escalate", "handoff", "done"))
        self.assertEqual(levers.after_verify(""), ("handoff", "escalate", "done"))

    def test_handoff_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, home = Path(tmp) / "proj", Path(tmp) / "home"
            proj.mkdir()
            self.assertFalse(levers.handoff_ready(str(proj), home))
            local = proj / ".claude" / "skills" / "session-handoff"
            local.mkdir(parents=True)
            (local / "SKILL.md").write_text("x", encoding="utf-8")
            self.assertTrue(levers.handoff_ready(str(proj), home))
            self.assertFalse(levers.handoff_ready("", home))
            mine = home / ".claude" / "skills" / "session-handoff"
            mine.mkdir(parents=True)
            (mine / "SKILL.md").write_text("x", encoding="utf-8")
            self.assertTrue(levers.handoff_ready("", home))

    def test_lessons_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = time.mktime((2026, 10, 13, 12, 0, 0, 0, 0, -1))
            line = levers.lesson_line("CALC", "code", "  profile before\noptimizing token=abc  ", now)
            self.assertEqual(line, "- 2026-10-13 - CALC - code: profile before optimizing token=***")
            levers.add_lesson(Path(tmp), line)
            levers.add_lesson(Path(tmp), levers.lesson_line("OTHER", "", "x", now))
            self.assertEqual(levers.read_lessons(Path(tmp), "CALC"), [line])
            self.assertEqual(levers.read_lessons(Path(tmp), "OTHER"), ["- 2026-10-13 - OTHER - chat: x"])
            text = (Path(tmp) / "lessons.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Lessons"))
            self.assertEqual(levers.read_lessons(Path(tmp) / "nope", "CALC"), [])
            self.assertEqual(levers.read_misses(Path(tmp), "CALC"), [])  # the two files stay apart
            self.assertLessEqual(len(levers.lesson_line("P", "code", "w" * 500, now)), 240)

    def test_escalate_text_frames_the_fix(self):
        text = levers.escalate_text("test_x - KeyError", "sonnet", "high")
        self.assertTrue(text.startswith("The checks failed: test_x - KeyError. You now run on sonnet/high (escalated once). "))
        self.assertIn(levers.FIX_FRAME, text)
        self.assertIn("three plausible causes", levers.FIX_FRAME)
        self.assertIn("smallest check", levers.FIX_FRAME)
        self.assertTrue(text.endswith("`VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`."))
        self.assertIn("see the last VERDICT line", levers.escalate_text("", "opus", "high"))


if __name__ == "__main__":
    unittest.main()
