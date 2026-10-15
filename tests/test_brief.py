import unittest

from console import brief, levers


class BriefTest(unittest.TestCase):
    def test_task_brief_lists_the_facts(self):
        text = brief.build("task", goal="Implement the Cells Drawer", last="Step 3 is placed.",
                           files=["web/app.js", "web/style.css"], verdict="FAIL", detail="test_add - 3 != 4",
                           status=[" M web/app.js", "?? notes.md"], plan=True)
        self.assertTrue(text.startswith(brief.TASK_INTRO))
        for part in ("Goal (the first prompt of the earlier chat):\nImplement the Cells Drawer",
                     "Where it stopped (the last message of Claude):\nStep 3 is placed.",
                     "Files the earlier chat edited:\n- web/app.js\n- web/style.css",
                     "Last check: FAIL test_add - 3 != 4",
                     "Git status of the folder now:\n M web/app.js\n?? notes.md",
                     "Read PLAN.md first."):
            self.assertIn(part, text)

    def test_empty_parts_are_left_out(self):
        text = brief.build("task")
        self.assertEqual(text, brief.TASK_INTRO)

    def test_next_brief_keeps_the_note_lines(self):
        text = brief.build("next", goal="g", last="Read PLAN.md.\nNext: step 4.", files=["a.py"], plan=True)
        self.assertEqual(text, brief.NEXT_INTRO + "\n\nHandoff note:\nRead PLAN.md.\nNext: step 4.")
        self.assertEqual(brief.build("next"), brief.NEXT_INTRO)
        self.assertTrue(brief.build("next", last="x" * 5000).endswith("x…"))

    def test_next_brief_of_a_skill_note_is_its_handoff_block(self):
        block = ("HANDOFF\n## Goal\nShip plan 23.\n## Findings\n- the brief pass works\n## Files touched\n- (none)\n"
                 "## Troubleshooting\n- (none)\n## Open questions\n- (none)\n## Next\nWrite the window task.\nEND HANDOFF")
        note = "Done. Next session: /session-handoff resume\n\n" + block
        text = brief.build("next", last=note)
        self.assertIn("## Troubleshooting", text)
        self.assertNotIn("Done. Next session", text)  # the block alone
        self.assertIn("free text", brief.build("next", last="free text"))  # a note with no block keeps its lines

    def test_verify_brief_starts_with_the_verify_text(self):
        text = brief.build("verify", goal="g", files=["a.py"], plan=True)
        self.assertTrue(text.startswith(levers.VERIFY_TEXT))
        self.assertIn(brief.VERIFY_INTRO, text)
        self.assertIn("- a.py", text)
        self.assertNotIn("PLAN.md", text)

    def test_long_lists_and_texts_are_cut_and_masked(self):
        text = brief.build("task", goal="g" * 5000, files=[f"f{k}.py" for k in range(30)],
                           status=[f" M token=abc{k}" for k in range(30)])
        self.assertLess(len(text), 3500)
        self.assertIn("- and 10 more", text)
        self.assertIn("... and 10 more", text)
        self.assertIn(" M token=***", text)
        self.assertNotIn("token=abc", text)


if __name__ == "__main__":
    unittest.main()
