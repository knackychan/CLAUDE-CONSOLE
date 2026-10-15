"""Plan 24: the replan step (console/replan.py): the ask line, insert, the prompt, check, propose, apply, keep."""
import unittest

from console import replan, tasks


def make_task(kinds=("scout", "code", "test", "verify", "document")):
    steps = [tasks._blank(i + 1, k, f"step {k}") for i, k in enumerate(kinds)]
    for s in steps:
        if s["kind"] == "verify":
            s["checked"], s["goal"] = 2, "Check step 2"
    t = tasks.new_task("D:/x", "x", "fills", "Goal: fills per model", steps, "normal",
                       {"reasoning": "low", "volume": "low"}, "", "auto", now=1.0)
    t["steps"][0]["state"], t["current"], t["last_good"] = "done", 1, 1
    return t


class ReplanTest(unittest.TestCase):
    def test_ask_line_reads_the_next_line(self):
        block = "## Findings\nx\n## Next\n02 code. **Replan:** usage.py has no week bucket yet"
        self.assertEqual(replan.ask_line(block), "usage.py has no week bucket yet")
        self.assertEqual(replan.ask_line("## Next\ngo on"), "")

    def test_insert_puts_a_replan_step_after_the_asking_step(self):
        t = make_task()
        lines = replan.insert(t, 1, 5.0, "no week bucket")
        self.assertEqual([(s["n"], s["kind"]) for s in t["steps"]],
                         [(1, "scout"), (2, "replan"), (3, "code"), (4, "test"), (5, "verify"), (6, "document")])
        self.assertEqual((t["steps"][4]["checked"], t["steps"][4]["goal"]), (3, "Check step 3"))
        self.assertEqual(lines[0]["why"], "replan inserted after 01: no week bucket")
        self.assertEqual(replan.remaining(t, 2), [t["steps"][2], t["steps"][3], t["steps"][5]])

    def test_prompt_carries_the_goal_the_briefs_and_the_remaining_steps(self):
        t = make_task()
        replan.insert(t, 1, 5.0, "no week bucket")
        text = replan.build_prompt(t, 2, "## Findings\n- usage.py builds day buckets only")
        self.assertIn("A step before you asked for it:\nno week bucket", text)
        self.assertIn("Task: Goal: fills per model", text)
        self.assertIn("- code: step code\n- test: step test\n- document: step document", text)
        self.assertIn("At most 5 steps", text)
        self.assertNotIn("$", text)

    def test_check_builds_the_steps_and_replaces_the_verify(self):
        t = make_task()
        replan.insert(t, 1, 5.0, "x")
        answer = {"why": "week buckets first", "steps": [{"kind": "code", "goal": "week buckets"},
                                                          {"kind": "code", "goal": "fills"}, {"kind": "test", "goal": "run"},
                                                          {"kind": "document", "goal": "docs"}]}
        steps, why = replan.check(t, 2, answer, 8)
        self.assertEqual(why, "")
        self.assertEqual([(s["n"], s["kind"]) for s in steps],
                         [(3, "code"), (4, "code"), (5, "test"), (6, "document"), (7, "verify")])
        self.assertEqual(steps[4]["checked"], 6)

    def test_check_refuses_too_many_added_unknown_kinds_and_a_long_chain(self):
        t = make_task()
        replan.insert(t, 1, 5.0, "x")
        many = {"why": "", "steps": [{"kind": "code", "goal": "g"}] * 6}
        self.assertEqual(replan.check(t, 2, many, 12)[1], "3 steps added, over 2")
        self.assertEqual(replan.check(t, 2, {"why": "", "steps": [{"kind": "verify", "goal": "g"}]}, 8)[1], "unknown kind: verify")
        self.assertEqual(replan.check(t, 2, {"why": "", "steps": [{"kind": "replan", "goal": "g"}]}, 8)[1], "unknown kind: replan")
        self.assertEqual(replan.check(t, 2, {"why": "", "steps": [{"kind": "code", "goal": " "}]}, 8)[1], "a step has no goal")
        self.assertEqual(replan.check(t, 2, {"why": "", "steps": []}, 8)[1], "no steps in the answer")
        four = {"why": "", "steps": [{"kind": "code", "goal": "g"}] * 4}
        self.assertEqual(replan.check(t, 2, four, 5)[1], "6 steps in all, over task_max_steps 5")

    def test_check_accepts_an_empty_answer_when_no_step_remains(self):
        t = make_task(("scout", "code", "verify", "replan"))
        t["steps"][1]["state"] = t["steps"][2]["state"] = "done"
        self.assertEqual(replan.remaining(t, 4), [])
        self.assertEqual(replan.check(t, 4, {"why": "nothing left", "steps": []}, 8), ([], ""))
        self.assertEqual(replan.check(t, 4, {"why": ""}, 8)[1], "no steps in the answer")
        self.assertEqual(replan.summary(t), "replanned: no change")

    def test_propose_apply_and_keep(self):
        t = make_task()
        replan.insert(t, 1, 5.0, "x")
        steps, _ = replan.check(t, 2, {"why": "w", "steps": [{"kind": "code", "goal": "week buckets"}, {"kind": "code", "goal": "step code"},
                                                             {"kind": "test", "goal": "step test"}, {"kind": "document", "goal": "step document"}]}, 8)
        lines = replan.propose(t, 2, steps, "week buckets first", 6.0)
        self.assertEqual(t["replan"]["added"], [0])
        self.assertEqual(t["replan"]["dropped"], [])
        self.assertEqual(replan.summary(t), "replanned: 1 steps added")
        self.assertEqual(lines[0]["why"], "replanned: 1 steps added")
        note = replan.note_block(t)
        self.assertIn("## Goal\n", note)
        self.assertIn("## Findings\nweek buckets first\n", note)
        self.assertIn("Steps after:\n- code: week buckets\n- code: step code", note)
        self.assertEqual(tasks.check_handoff(note), "")
        kept = replan.keep(dict(t), 7.0)
        self.assertEqual(kept[0]["why"], "old plan kept by Fred")
        lines = replan.apply(t, 7.0)
        self.assertEqual([(s["n"], s["kind"]) for s in t["steps"]],
                         [(1, "scout"), (2, "replan"), (3, "code"), (4, "code"), (5, "test"), (6, "document"), (7, "verify")])
        self.assertNotIn("replan", t)
        self.assertEqual(lines[0]["why"], "plan changed: 5 steps follow 02")
        self.assertEqual(replan.apply(t, 8.0), [])

    def test_check_keeps_the_verify_of_a_done_edit_step(self):
        t = make_task(kinds=("scout", "code", "replan", "test", "verify"))  # the verify checks step 2
        t["steps"][1]["state"] = t["steps"][2]["state"] = "done"
        steps, why = replan.check(t, 3, {"why": "w", "steps": [{"kind": "test", "goal": "run it"}]}, 8)
        self.assertEqual(why, "")
        self.assertEqual([(s["n"], s["kind"], s["checked"], s["goal"]) for s in steps],
                         [(4, "test", 0, "run it"), (5, "verify", 2, "Check step 2")])
        replan.propose(t, 3, steps, "w", 6.0)
        replan.apply(t, 7.0)
        self.assertEqual([s["kind"] for s in t["steps"]], ["scout", "code", "replan", "test", "verify"])
        done = make_task(kinds=("scout", "code", "verify", "replan", "test"))  # already verified: none added
        for s in done["steps"][:4]:
            s["state"] = "done"
        steps, _ = replan.check(done, 4, {"why": "w", "steps": [{"kind": "test", "goal": "run it"}]}, 8)
        self.assertEqual([s["kind"] for s in steps], ["test"])

    def test_room_counts_the_done_steps_kept_after_n(self):
        t = make_task(kinds=("scout", "replan", "code", "code", "verify"))  # a redo kept step 3 done
        t["steps"][1]["state"] = t["steps"][2]["state"] = "done"
        self.assertEqual(tasks.room_after(t, 2, 6), 3)  # 6 - 2 - the done code step; the verify is not counted
        three = {"why": "", "steps": [{"kind": "code", "goal": "g"}] * 3}
        self.assertEqual(replan.check(t, 2, three, 5)[1], "6 steps in all, over task_max_steps 5")
        self.assertEqual(replan.check(t, 2, three, 6)[1], "")


if __name__ == "__main__":
    unittest.main()
