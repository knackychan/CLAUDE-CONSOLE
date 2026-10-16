"""Plan 28: the kind files (console/kinds.py and dotclaude/console/kinds/): seeded once, read, checked, saved."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from console import kinds, plan, prep, replan, tasks


class KindFilesTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)

    def test_one_seed_per_chain_kind_in_the_shape(self):
        self.assertEqual(kinds.NAMES, tasks.KINDS + ("prep",))  # plan 29: Prep's kind file after the chain kinds
        self.assertNotIn(tasks.CHAT, kinds.NAMES)  # a chat runs the prompt alone
        self.assertEqual(sorted(p.stem for p in kinds.SEED.glob("*.md")), sorted(kinds.NAMES))
        for kind in kinds.NAMES:
            text = kinds.seed_text(kind)
            self.assertEqual(kinds.check(kind, text), "", kind)
            self.assertNotIn("Fred", text, kind)  # plan 31: the person is $you
            self.assertNotIn(chr(0x2014), text, kind)
            if kind not in ("design", "replan", "prep"):  # those three carry their old prompt files whole
                at = [text.index(h) for h in ("## Role", "## Do\n", "## Do not", "## Read", "## Leave behind")]
                self.assertEqual(at, sorted(at), kind)
                self.assertIn("HANDOFF block", text, kind)
        self.assertIn("$checked", kinds.seed_text("verify"))
        self.assertIn("$failed", kinds.seed_text("fix"))
        for slot in ("$turns", "$later", "$edit_steps", "$redo", "$max_kb", "$max_parts", "$room", "$write_kinds"):
            self.assertIn(slot, kinds.seed_text("design"), slot)
        self.assertEqual(plan.PROMPT_FILE, kinds.SEED / "design.md")
        self.assertEqual(replan.PROMPT_FILE, kinds.SEED / "replan.md")
        self.assertEqual(prep.PROMPT_FILE, kinds.SEED / "prep.md")
        for slot in ("$You", "$raw", "$misses", "$window"):
            self.assertIn(slot, kinds.seed_text("prep"), slot)

    def test_prep_routes_findings_only_work_to_explain(self):
        """Plan 38: a read-only audit is not a design step, which must write an implementation PLAN."""
        text = kinds.seed_text("prep")
        row = lambda kind: next(line for line in text.splitlines() if line.startswith(f"| {kind} |"))
        self.assertIn("audit or review", row("explain"))
        self.assertIn("implementation PLAN", row("design"))
        self.assertNotIn("research", row("design"))
        self.assertIn("A read-only audit or review that ends in findings is explain", text)
        self.assertIn("PLAN", kinds.seed_text("design"))  # the design contract itself is unchanged

    def test_ensure_seeds_once_and_keeps_an_edit(self):
        self.assertEqual(kinds.ensure(self.home), list(kinds.NAMES))
        path = Path(self.home) / "kinds" / "code.md"
        path.write_text("# code\n\nmy own rules\n", encoding="utf-8")
        self.assertEqual(kinds.ensure(self.home), [])
        self.assertEqual(kinds.text(self.home, "code"), "# code\n\nmy own rules\n")
        path.write_text("  \n", encoding="utf-8")  # emptied by hand: the seed stands in
        self.assertEqual(kinds.text(self.home, "code"), kinds.seed_text("code"))
        self.assertEqual(kinds.text(self.home, "nope"), "")
        self.assertEqual(kinds.text(tempfile.mkdtemp(), "scout"), kinds.seed_text("scout"))  # not seeded yet

    def test_check_and_save(self):
        self.assertEqual(kinds.check("code", "# code\nx"), "")
        self.assertEqual(kinds.check("code", "# scout\nx"), "the first line must be # code")
        self.assertEqual(kinds.check("code", "  "), "the file is empty")
        self.assertEqual(kinds.check("chat", "# chat\nx"), "unknown kind: chat")
        self.assertEqual(kinds.check("code", "# code\n" + "x" * kinds.KIND_MAX), "over 32 KB")
        self.assertEqual(kinds.save(self.home, "code", "# code\r\nnew rules"), "# code\nnew rules\n")
        self.assertFalse(os.path.exists(os.path.join(self.home, "kinds", "code.md.tmp")))
        with self.assertRaises(ValueError):
            kinds.save(self.home, "code", "no head")
        self.assertEqual(kinds.text(self.home, "code"), "# code\nnew rules\n")  # a refused save changes nothing
        self.assertEqual(kinds.save(self.home, "code", None), kinds.seed_text("code"))  # back to the repo's copy

    def test_body_drops_the_head_line(self):
        self.assertEqual(kinds.body_of("# code\n\n## Role\nx\n"), "## Role\nx")
        self.assertEqual(kinds.body_of("## Role\nx"), "## Role\nx")


class RoleTextTest(unittest.TestCase):
    def test_slots_are_filled_from_the_step_and_the_name(self):
        steps = tasks.plan_steps([{"kind": "scout", "goal": "find"}, {"kind": "code", "goal": "write"}], 6)
        task = tasks.new_task("D:/x", "x", "T", "G", steps, "normal", {}, "", "auto", 1.0)
        verify = tasks.role_text(task, tasks.step(task, 3), kinds.seed_text("verify"), you="Fred")
        self.assertIn("Check the work of step 2 as the handoff note above describes it", verify)
        self.assertFalse(verify.startswith("# verify"))
        own = tasks.role_text(task, tasks.step(task, 1), "# scout\nAsk $you; $You decides; $unknown stays")
        self.assertEqual(own, "Ask the user; The user decides; $unknown stays")
        self.assertEqual(tasks.role_slots(task, tasks.step(task, 1)), {})
