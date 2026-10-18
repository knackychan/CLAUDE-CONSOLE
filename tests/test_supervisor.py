"""Plan 44 backend: the supervisor's policy, audit, digest and bounded pass (pure tests)."""
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import paths, supervisor, tasks


def cfg(**over):
    base = dict(paths.DEFAULTS, projects=["D:\\work", "C:\\other"],
                supervisor_projects={}, supervisor_mode="suggest")
    base.update(over)
    return base


class PolicyTest(unittest.TestCase):
    def test_default_suggest_and_task_project_global_precedence(self):
        c = cfg(supervisor_projects={"d:/work": "auto"})  # Windows spelling: drive letter and slash differ
        # global default -> suggest; project override -> auto; explicit task mode wins
        self.assertEqual(supervisor.initial(c, "D:\\work", 100.0)["mode"], "auto")
        self.assertEqual(supervisor.initial(c, "C:\\other", 100.0)["mode"], "suggest")
        self.assertEqual(supervisor.initial(c, "D:\\work", 100.0, mode="off")["mode"], "off")
        for mode in supervisor.MODES:
            self.assertEqual(supervisor.initial(c, "C:\\other", 100.0, mode=mode)["mode"], mode)
        # the saved task override survives a later project/global change
        saved = supervisor.initial(c, "C:\\other", 100.0, mode="auto")
        task = {"project_dir": "C:\\other", "supervisor": saved}
        changed = cfg(supervisor_projects={"C:/other": "off"}, supervisor_mode="off")
        self.assertEqual(supervisor.policy(changed, task, 200.0)["mode"], "auto")
        self.assertEqual(saved, supervisor.initial(c, "C:\\other", 100.0, mode="auto"))  # inputs unchanged

    def test_legacy_task_loads_without_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            from unittest import mock
            with mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": tmp}):
                task = tasks.new_task("D:\\work", "work", "Legacy", "goal", tasks.plan_steps(
                    [{"kind": "scout", "goal": "look"}], 6), "normal", {}, "", "auto", 100.0)
                self.assertNotIn("supervisor", task)
                tasks.save(tmp, task)
                loaded = tasks.load(tmp, task["id"])
                self.assertIsNotNone(loaded)
                self.assertTrue(tasks.whole(loaded))
                self.assertNotIn("supervisor", loaded)
                # policy computes an effective policy for a legacy task without mutating it
                before = dict(loaded)
                policy = supervisor.policy(cfg(), loaded, 200.0)
                self.assertEqual(policy["mode"], "suggest")
                self.assertEqual(loaded, before)

    def test_invalid_policy_fails_closed(self):
        # unknown global mode
        p = supervisor.policy(cfg(supervisor_mode="turbo"), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual((p["mode"], bool(p["reason"])), ("off", True))
        # unknown saved task mode
        p = supervisor.policy(cfg(), {"project_dir": "D:\\work", "supervisor": {"mode": "turbo"}}, 0.0)
        self.assertEqual((p["mode"], bool(p["reason"])), ("off", True))
        # booleans as counts, negative and NaN counters, malformed settings never grant extra allowance
        bad = {"mode": "auto", "auto_steps": True, "retries": {1: "x"}, "usd": -1, "work_usd": float("nan")}
        p = supervisor.policy(cfg(), {"project_dir": "D:\\work", "supervisor": bad}, 0.0)
        self.assertEqual(p["mode"], "off")
        self.assertTrue(p["reason"])
        p = supervisor.policy(cfg(supervisor_max_auto_steps=float("inf")), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual(p["mode"], "off")
        p = supervisor.policy(cfg(supervisor_model="opus"), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual((p["mode"], bool(p["reason"])), ("off", True))
        self.assertEqual(p["settings"]["supervisor_model"], "haiku")
        p = supervisor.policy(cfg(supervisor_stuck_model="fable"), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual(p["mode"], "off")
        # zero limits disable the allowance, never make it unlimited
        p = supervisor.policy(cfg(supervisor_max_auto_steps=0, supervisor_work_usd=0), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual((p["auto_steps_left"], p["work_usd_left"]), (0, 0.0))


class AuditTest(unittest.TestCase):
    def test_event_and_request_ids_are_stable(self):
        line = {"ts": 100.0, "step": 2, "session": "s1", "from": "running", "to": "done", "why": "x", "cost": 1.0}
        self.assertEqual(supervisor.event_id(line), supervisor.event_id(dict(line, cost=9.0)))
        self.assertNotEqual(supervisor.event_id(line), supervisor.event_id(dict(line, step=3)))
        self.assertNotEqual(supervisor.event_id(line), supervisor.event_id(dict(line, why="y")))
        one = supervisor.request_id("task-1", 1)
        self.assertEqual(one, supervisor.request_id("task-1", 1))
        self.assertRegex(one, r"[0-9a-f-]{16,36}")
        self.assertNotEqual(one, supervisor.request_id("task-1", 2))
        self.assertNotEqual(one, supervisor.request_id("task-2", 1))

    def test_append_is_masked_and_fold_counts_cost_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tid = "20260101-000000-abcd"
            claim = {"ts": 100.0, "wake": 1, "phase": "claimed", "events": ["e1"], "day": "2026-01-01",
                     "reserved": 0.1, "token": "sk-secret12345678"}
            result = {"ts": 101.0, "wake": 1, "phase": "result", "cost": 0.03, "day": "2026-01-01", "decision": {}}
            supervisor.append_log(tmp, tid, claim)
            supervisor.append_log(tmp, tid, result)
            supervisor.append_log(tmp, tid, {"ts": 102.0, "wake": 1, "phase": "dispatching"})
            supervisor.append_log(tmp, tid, {"ts": 103.0, "wake": 1, "phase": "outcome"})
            supervisor.append_log(tmp, tid, dict(result))  # a repeated result never multiplies spend
            records = supervisor.read_log(tmp, tid)
            folded = supervisor.fold_log(records)
            self.assertEqual(folded["cost"], 0.03)
            self.assertEqual(folded["days"]["2026-01-01"]["cost"], 0.03)
            self.assertEqual(folded["wakes"][1]["events"], ["e1"])
            raw = (Path(tmp) / "tasks" / tid / "supervisor.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("sk-secret12345678", raw)
            self.assertIn("***", raw)
            with self.assertRaises(ValueError):
                supervisor.append_log(tmp, "../x", claim)

    def test_corrupt_or_truncated_log_is_a_visible_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            tid = "20260101-000000-abcd"
            folder = Path(tmp) / "tasks" / tid
            folder.mkdir(parents=True)
            (folder / "supervisor.jsonl").write_text(
                '{"wake": 1, "phase": "result", "cost": 0.01}\nnot json\n{"wake": 2, "phase": "claimed", "events": ["e2"]}\n',
                encoding="utf-8")
            records = supervisor.read_log(tmp, tid)
            self.assertTrue(any(r.get("corrupt") for r in records))
            self.assertTrue(supervisor.fold_log(records)["uncertain"])
            self.assertEqual(supervisor.read_log(tmp, "20260101-000000-ffff"), [])  # missing file is valid empty


GOOD_NOTE = ("# Step 01: code on sonnet/high, session s1\n\nHANDOFF\n## Goal\nGOAL-SENTINEL ship it\n## Findings\n"
             "- found\n## Files touched\n- a.py\n## Troubleshooting\n- TROUBLE-SENTINEL\n## Open questions\n- (none)\n"
             "## Next\n- verify\nEND HANDOFF\n")


def evidence_task(home, steps=("code",)):
    """A manual task at a choose-next boundary with a saved handoff, facts, brief and forbidden files."""
    task = tasks.new_task("D:\\work", "work", "Dig", "the goal", tasks.plan_steps(
        [{"kind": k, "goal": f"do {k}"} for k in steps], 12), "normal", {}, "", "auto", 100.0,
        id_="20260101-000000-abcd")
    task["steps"] = [s for s in task["steps"] if s["kind"] != "verify"] if steps == ("code",) else task["steps"]
    task["supervisor"] = supervisor.initial(cfg(), "D:\\work", 100.0)
    task["progression"] = "manual"
    s = task["steps"][0]
    s.update(state="done", session="s1", ended=100.0, model="sonnet", effort="high", cost=0.5, dir="01-code",
             attempts=[{"session": "s1", "cost": 0.5, "started": 90.0, "ended": 100.0, "why": "", "final": True}])
    task.update(state="waiting", owner="fred", why="choose next step", current=1, last_good=1)
    tasks.save(home, task)
    tasks.write_step_file(home, task, s, "handoff.md", GOOD_NOTE)
    s["handoff"] = tasks.note_file(task, s)
    tasks.write_step_file(home, task, s, "facts.md", "FACTS-SENTINEL start abc end def\n")
    tasks.write_step_file(home, task, s, "brief.md", "BRIEF-SENTINEL\n## Open questions\n- OPENQ-SENTINEL?\n")
    tasks.write_step_file(home, task, s, "notes.md", "HEALTHY-NOTES-SENTINEL")
    tasks.write_step_file(home, task, s, "received.md", "RECEIVED-SENTINEL")
    tasks.log(home, task["id"], [tasks._line(100.0, s, "running", "done", "CHAIN-SENTINEL")])
    (Path(home) / "config.json").write_text('{"x": "CONFIG-SENTINEL"}', encoding="utf-8")
    return task


LEVERS = {"start": "task is waiting", "stop": "", "pause": "already paused", "resume": "choose", "retry": "task is waiting",
          "stepdone": "no stopped or stuck step", "confirm": "nothing to confirm", "clear": "task is waiting", "done": "",
          "answer": "no plan gap waits", "redo": "nothing to redo", "keep": "no plan change waits",
          "route": "sonnet/high", "next_route": "", "cwd": "D:\\work", "add_next": ""}


def context(task, **over):
    ctx = {"triggers": ["choose_next"], "policy": supervisor.policy(cfg(), task, 100.0), "levers": dict(LEVERS),
           "sources": {"01": ""}, "owned": [1], "budget": {"task_left": 0.5, "day_left": 2.0}, "reject_note": "",
           "stuck": None}
    ctx.update(over)
    return ctx


class DigestTest(unittest.TestCase):
    def test_saved_evidence_and_allowed_actions_only(self):
        with tempfile.TemporaryDirectory() as home:
            task = evidence_task(home)
            other = dict(task, id="20260101-000000-ffff")
            tasks.save(home, other)
            tasks.write_step_file(home, other, other["steps"][0], "handoff.md", "OTHER-TASK-SENTINEL")
            from console import plan, transcript
            with mock.patch.object(plan, "read_part", side_effect=AssertionError("plan part")), \
                    mock.patch.object(transcript, "read_messages", side_effect=AssertionError("transcript"), create=True):
                text = supervisor.digest(home, task, context(task, reject_note="REJECT-SENTINEL"))
            for good in ("GOAL-SENTINEL", "TROUBLE-SENTINEL", "FACTS-SENTINEL", "OPENQ-SENTINEL", "CHAIN-SENTINEL",
                         "REJECT-SENTINEL", "Allowed now", "done", "add_next_step from 01", "auto steps left"):
                self.assertIn(good, text)
            self.assertIn(GOOD_NOTE.split("\n\n", 1)[1].strip(), text)  # the handoff whole, exactly
            for bad in ("HEALTHY-NOTES-SENTINEL", "RECEIVED-SENTINEL", "CONFIG-SENTINEL", "OTHER-TASK-SENTINEL"):
                self.assertNotIn(bad, text)
            self.assertNotIn("retry", text.split("Allowed now", 1)[1].split("\n")[1])

    def test_utf8_cap_whole_blocks_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as home:
            task = evidence_task(home)
            s = task["steps"][0]
            big = "HANDOFF\n## Goal\n" + "\u6f22" * 7000 + "\n## Troubleshooting\n- x\nEND HANDOFF\n"
            tasks.write_step_file(home, task, s, "handoff.md", big)
            tasks.write_step_file(home, task, s, "facts.md", "\u5b57" * 5000)
            for n in range(2, 40):
                task["steps"].append(tasks._blank(n, "code", f"step {n} " + "\u6587" * 30))
            text = supervisor.digest(home, task, context(task))
            self.assertLessEqual(len(text.encode("utf-8")), supervisor.DIGEST_MAX)
            self.assertNotIn("\u6f22" * 10, text)  # never a partial handoff
            self.assertIn("omitted", text)
            self.assertIn("01-code/handoff.md", text)
            self.assertIn("Allowed now", text)
            # a missing facts file is named unavailable, never read as PASS
            (tasks.folder(home, task["id"]) / "01-code" / "facts.md").unlink()
            text = supervisor.digest(home, task, context(task))
            self.assertIn("unavailable", text)
            # a mandatory head that cannot fit is a typed failure
            task["steps"].extend(tasks._blank(n, "code", "\u6587" * 300) for n in range(40, 200))
            with self.assertRaises(supervisor.DigestError):
                supervisor.digest(home, task, context(task))

    def test_revision_ignores_cost_noise_but_changes_with_evidence_or_human_action(self):
        with tempfile.TemporaryDirectory() as home:
            task = evidence_task(home)
            rev = supervisor.revision(home, task)
            noise = json.loads(json.dumps(task))
            noise["updated"] = 999.0
            noise["steps"][0]["cost"] = 7.0
            noise["steps"][0]["attempts"][0]["cost"] = 7.0
            noise["supervisor"]["usd"], noise["supervisor"]["wakes"] = 0.3, 4
            tasks.log(home, task["id"], [{"ts": 1, "why": "supervisor: wait"}])
            self.assertEqual(supervisor.revision(home, noise), rev)
            for change in (lambda t: t.update(why="other"), lambda t: t["supervisor"].update(epoch=1),
                           lambda t: t["supervisor"].update(paused=True), lambda t: t.update(goal="new"),
                           lambda t: t["steps"][0].update(session="s2"), lambda t: t.update(state="stuck")):
                t = json.loads(json.dumps(task))
                change(t)
                self.assertNotEqual(supervisor.revision(home, t), rev)
            tasks.write_step_file(home, task, task["steps"][0], "facts.md", "changed")
            self.assertNotEqual(supervisor.revision(home, task), rev)


def ok(**over):
    d = {"decision": "wait", "reason": "r", "confidence": "low", "for_fred": ""}
    d.update(over)
    return d


class DecisionTest(unittest.TestCase):
    def setUp(self):
        self.task = {"id": "t", "state": "waiting", "why": "choose next step", "current": 1, "owner": "fred",
                     "steps": [{"n": 1, "kind": "code", "state": "done", "session": "s1"}]}
        self.policy = {"triggers": ["choose_next"], "owned": [1], "retries_left": 1}

    def check(self, d, levers=None, sources=None, task=None, policy=None):
        return supervisor.check(d, task or self.task, dict(LEVERS, **(levers or {})),
                                {"01": ""} if sources is None else sources, dict(self.policy, **(policy or {})))

    def test_each_decision_and_gate(self):
        add = ok(decision="add_next_step", kind="verify", instructions="check it", model="auto")
        cases = [
            (add, {}, True), (dict(add, source_step=1), {}, True), (add, {"add_next": "busy"}, False),
            (ok(decision="confirm"), {}, False),
            (ok(decision="keep"), {"keep": ""}, True), (ok(decision="keep"), {}, False),
            (ok(decision="retry", note="fix line 3"), {"retry": ""}, True),
            (ok(decision="retry", note="fix", model="sonnet"), {"retry": ""}, True),
            (ok(decision="retry", note="fix"), {}, False),
            (ok(decision="stepdone"), {"stepdone": ""}, True), (ok(decision="stepdone"), {}, False),
            (ok(decision="stop"), {}, False),
            (ok(decision="finish"), {}, True), (ok(decision="finish"), {"done": "still working"}, False),
            (ok(decision="answer", text="yes"), {"answer": ""}, False),
            (ok(decision="escalate_to_fred", for_fred="which one?"), {}, True),
            (ok(decision="escalate_to_fred"), {}, False), (ok(), {}, True),
        ]
        for d, levers, want in cases:
            got, why = self.check(d, levers)
            self.assertEqual(got, want, (d, levers, why))
            self.assertEqual(bool(why), not want)
        self.assertFalse(self.check(ok(decision="retry", note="fix"), {"retry": ""}, policy={"retries_left": 0})[0])
        self.assertTrue(self.check(ok(decision="stop"), policy={"triggers": ["stalled"]})[0])
        for why in ("plan ready: confirm", "plan 30 KB, over 24", "replanned: 2 steps"):
            task = dict(self.task, why=why)
            self.assertTrue(self.check(ok(decision="confirm"), {"confirm": ""}, task=task)[0], why)
        self.assertEqual(self.check(ok(decision="answer", text="yes"), {"answer": ""})[1], "questions are Fred's")

    def test_unknown_fields_wrong_types_and_model_ids_refused(self):
        add = ok(decision="add_next_step", kind="verify", instructions="check it", model="auto")
        bad = [None, [], "wait", ok(path="C:/x"), ok(command="rm"), ok(skills=["a"]), ok(confidence="sure"),
               ok(reason=" "), ok(reason="x" * 1001), ok(for_fred="x" * 401), ok(decision="pause"),
               {"decision": "wait", "reason": "r", "confidence": "low"}, ok(reason=3),
               dict(add, source_step=True), dict(add, source_step="1"), dict(add, kind="debug"),
               dict(add, instructions=" "), dict(add, instructions="x" * (tasks.STEP_GOAL_MAX + 1)),
               dict(add, model="claude-sonnet-5-5"), dict(add, model="sonnet"), dict(add, model=""),
               {k: v for k, v in add.items() if k != "model"}, dict(add, note="n"),
               dict(add, source_step=2), ok(kind="code"), ok(decision="retry", note=" "),
               ok(decision="retry", note="x" * 2001), ok(decision="retry", note="n", model="fable"),
               ok(decision="retry", note="n", model="claude-opus-5-5"), ok(decision="answer", text="x" * 401)]
        levers = {"retry": ""}
        for d in bad:
            self.assertFalse(self.check(d, levers)[0], d)
        external = dict(self.task, steps=[{"n": 1, "kind": "code", "state": "done", "session": "ext"}])
        self.assertFalse(self.check(add, task=external, policy={"owned": []})[0])
        self.assertFalse(self.check(add, sources={"01": "a later step has not finished"})[0])
        unfinished = dict(self.task, steps=[{"n": 1, "kind": "code", "state": "running", "session": "s1"}])
        self.assertFalse(self.check(add, task=unfinished)[0])

    def test_questions_fable_and_pace_cannot_be_approved(self):
        high = dict(confidence="high")
        self.assertFalse(self.check(ok(decision="answer", text="yes", **high), {"answer": ""},
                                    policy={"mode": "auto", "human": True})[0])
        for why in ("confirm Fable", "step 02 opus over its pace"):
            task = dict(self.task, why=why)
            self.assertFalse(self.check(ok(decision="confirm", **high), {"confirm": ""}, task=task,
                                        policy={"human": True})[0], why)
        add = ok(decision="add_next_step", kind="code", instructions="x", model="auto", **high)
        self.assertFalse(self.check(add, sources={"01": "task uses automatic progression"}, policy={"human": True})[0])


if __name__ == "__main__":
    unittest.main()
