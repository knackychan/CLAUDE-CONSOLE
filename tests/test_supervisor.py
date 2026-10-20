"""Plan 44 backend: the supervisor's policy, audit, digest and bounded pass (pure tests)."""
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import claude_cli, compact, kinds, paths, supervisor, tasks


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

    def test_boundary_finds_a_queued_next_message(self):
        with tempfile.TemporaryDirectory() as home:
            task = evidence_task(home)
            s = task["steps"][0]
            chain = lambda: tasks.read_chain(home, task)
            tasks.log(home, task["id"], [tasks._line(120.0, s, "task:running", "task:waiting", "choose next step")])
            self.assertEqual(supervisor.boundary(task, chain())["trigger"], "choose_next")  # none without the message
            mid = "abcdef12-0000-4000-8000-000000000000"
            task["messages"] = [{"id": mid, "mode": "next", "status": "queued", "text": "verify only 340 px"}]
            self.assertEqual(supervisor.boundary(task, chain())["trigger"], "choose_next")  # no chain line names it yet
            line = {"ts": 150.0, "step": 1, "from": "waiting", "to": "waiting", "session": "",
                    "why": "fred: next-step message abcdef12"}
            tasks.log(home, task["id"], [line])
            found = supervisor.boundary(task, chain())
            self.assertEqual((found["trigger"], found["line"]["why"]), ("message", line["why"]))
            self.assertEqual(found["event"], supervisor.event_id(found["line"]))
            for status in ("dispatched", "cancelled"):  # claimed or cancelled: the plain boundary again
                task["messages"][0]["status"] = status
                self.assertEqual(supervisor.boundary(task, chain())["trigger"], "choose_next")
            task["messages"][0].update(status="queued", mode="queued")  # guidance is not a next-step message
            self.assertEqual(supervisor.boundary(task, chain())["trigger"], "choose_next")
            task["messages"][0]["mode"] = "next"
            task["supervisor"]["paused"] = True
            self.assertIsNone(supervisor.boundary(task, chain()))
            task["supervisor"]["paused"] = False
            # a finished manual task
            task.update(state="done", why="marked done by Fred", owner="fred")
            self.assertEqual(supervisor.boundary(task, chain())["trigger"], "message")
            task["progression"] = "automatic"
            self.assertNotEqual((supervisor.boundary(task, chain()) or {}).get("trigger"), "message")

    def test_digest_carries_fred_next(self):
        with tempfile.TemporaryDirectory() as home:
            task = evidence_task(home)
            text = supervisor.digest(home, task, context(task, triggers=["message"], fred_next="verify the 340 px case"))
            self.assertIn("Fred asks for the next step: verify the 340 px case", text)
            self.assertNotIn("Fred asks for the next step", supervisor.digest(home, task, context(task)))
            long = supervisor.digest(home, task, context(task, fred_next="y" * 3000))
            self.assertNotIn("y" * (tasks.STEP_GOAL_MAX + 1), long)

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


FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        self.task = {"id": "20260101-000000-abcd", "project_dir": self.tmp.name, "steps": []}
        self.cfg = cfg(supervisor_timeout_s=90)

    def prompt(self, digest_text="digest SUP-VERIFY"):
        return supervisor.build_prompt(kinds.text(self.home, "supervisor"), self.task, digest_text)

    def test_one_call_has_project_cwd_timeout_and_tool_free_flags(self):
        seen = []
        real = subprocess.run

        def spy(cmd, **kw):
            seen.append((cmd, kw))
            return real(cmd, **kw)
        with mock.patch.object(compact.subprocess, "run", side_effect=spy), \
                mock.patch("console.runs.RunManager.start", side_effect=AssertionError("no worker")):
            got = supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.25)
        self.assertEqual(len(seen), 1)
        cmd, kw = seen[0]
        self.assertEqual(kw["cwd"], self.tmp.name)
        self.assertEqual(kw["timeout"], 90)
        self.assertIs(kw["env"].__class__, dict)
        self.assertEqual(kw["creationflags"], claude_cli.NO_WINDOW)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "6")
        self.assertEqual(cmd[cmd.index("--max-budget-usd") + 1], "0.25")
        self.assertEqual(cmd[cmd.index("--disallowedTools") + 1], "mcp__*")
        self.assertEqual(cmd[cmd.index("--model") + 1], "haiku")
        self.assertEqual(json.loads(cmd[cmd.index("--settings") + 1]), {"disableAllHooks": True})
        self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1]), supervisor.SCHEMA)
        for flag in ("--safe-mode", "--disable-slash-commands", "--strict-mcp-config", "--no-session-persistence"):
            self.assertIn(flag, cmd)
        for flag in ("--resume", "--session-id", "--add-dir", "--bg", "--agents", "--fork-session"):
            self.assertNotIn(flag, cmd)
        self.assertEqual(got["decision"]["kind"], "verify")
        self.assertEqual((got["cost"], got["model"], got["turns"], got["error"]), (0.004, "haiku", 2, ""))
        # a tiny remaining allowance is never rounded up
        with mock.patch.object(compact.subprocess, "run", side_effect=spy):
            supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.0049999)
        cmd = seen[-1][0]
        self.assertLessEqual(float(cmd[cmd.index("--max-budget-usd") + 1]), 0.0049999)

    def test_prompt_order_and_seed_override(self):
        seed = kinds.seed_text("supervisor")
        self.assertTrue(seed.startswith("# supervisor\n\nYou supervise one Claude Console task"))
        self.assertLess(len(seed.split()), 600)
        self.assertLess(len(seed.encode("utf-8")), 4500)
        kinds.ensure(self.home)
        (kinds.folder(self.home) / "supervisor.md").write_text("# supervisor\n\nOWN-EDIT for $You and $you.",
                                                              encoding="utf-8")
        text = supervisor.build_prompt(kinds.text(self.home, "supervisor"), self.task, "cost $5 and $you here",
                                       you="Ann")
        self.assertTrue(text.startswith("OWN-EDIT for Ann and Ann."))
        self.assertLess(text.index("JSON"), text.index("cost $5 and $you here"))
        self.assertTrue(text.endswith("cost $5 and $you here"))  # evidence dollar signs untouched, digest last
        settings = supervisor.policy(cfg(), {"project_dir": "D:\\work"}, 0.0)["settings"]
        self.assertEqual(supervisor.pass_model(settings, ["choose_next"]), "haiku")
        self.assertEqual(supervisor.pass_model(settings, ["stuck"]), "sonnet")
        self.assertEqual(supervisor.pass_model(settings, ["stalled"]), "sonnet")

    def test_prompt_fingerprint_matches_executed_bytes(self):
        captured = []

        def fake(cmd, **kw):
            captured.append(kw["input"])
            body = {"type": "result", "is_error": False, "total_cost_usd": 0.001, "num_turns": 2,
                    "structured_output": {"decision": "wait", "reason": "r", "confidence": "low", "for_fred": ""}}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(body).encode(), b"")
        prompt = self.prompt("\u6f22\u5b57 $5 digest")
        with mock.patch.object(compact.subprocess, "run", side_effect=fake):
            supervisor.run(self.cfg, FAKE, self.task, prompt, "haiku", 0.5)
        self.assertEqual(supervisor.prompt_hash(prompt), hashlib.sha256(captured[0]).hexdigest())
        # a kind-only edit changes the fingerprint, not the evidence revision
        task = evidence_task(self.home)
        rev = supervisor.revision(self.home, task)
        before = supervisor.prompt_hash(supervisor.build_prompt(kinds.text(self.home, "supervisor"), task, "d"))
        kinds.ensure(self.home)
        (kinds.folder(self.home) / "supervisor.md").write_text("# supervisor\n\nEdited.", encoding="utf-8")
        after = supervisor.prompt_hash(supervisor.build_prompt(kinds.text(self.home, "supervisor"), task, "d"))
        self.assertNotEqual(before, after)
        self.assertEqual(supervisor.revision(self.home, task), rev)
        # the claimed prompt is what runs, whatever the kind file says later
        with mock.patch.object(compact.subprocess, "run", side_effect=fake):
            supervisor.run(self.cfg, FAKE, self.task, prompt, "haiku", 0.5)
        self.assertEqual(captured[-1], prompt.encode("utf-8"))

    def test_failures_have_no_decision_and_no_retry(self):
        def envelope(body, code=0):
            return lambda cmd, **kw: subprocess.CompletedProcess(cmd, code, body.encode(), b"")
        good = json.dumps({"type": "result", "is_error": False, "total_cost_usd": 0.01, "num_turns": 2,
                           "structured_output": {"decision": "wait", "reason": "r", "confidence": "low",
                                                 "for_fred": ""}})
        cases = {
            "missing": None,
            "oserror": mock.Mock(side_effect=OSError("nope")),
            "timeout": mock.Mock(side_effect=subprocess.TimeoutExpired("claude", 90)),
            "nonjson": envelope("not json"),
            "nonobject": envelope("[1]"),
            "exit": envelope(good, 3),
            "is_error": envelope(json.dumps({"is_error": True, "subtype": "x", "total_cost_usd": 0.02})),
            "nostructured": envelope(json.dumps({"is_error": False, "total_cost_usd": 0.01})),
            "malformed": envelope(json.dumps({"is_error": False, "total_cost_usd": 0.01,
                                              "structured_output": {"decision": "pause"}})),
            "crash": mock.Mock(side_effect=RuntimeError("boom")),
        }
        for name, effect in cases.items():
            with self.subTest(name):
                calls = mock.Mock(side_effect=effect) if callable(effect) and not isinstance(effect, mock.Mock) \
                    else effect
                if name == "missing":
                    got = supervisor.run(self.cfg, [], self.task, self.prompt(), "haiku", 0.5)
                else:
                    with mock.patch.object(compact.subprocess, "run", calls):
                        got = supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)
                    self.assertEqual(calls.call_count, 1)
                self.assertIsNone(got["decision"])
                self.assertTrue(got["error"])
        with mock.patch.object(compact.subprocess, "run", mock.Mock(side_effect=subprocess.TimeoutExpired("c", 9))):
            self.assertIsNone(supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)["cost"])
        with mock.patch.object(compact.subprocess, "run", mock.Mock(side_effect=OSError("x"))):
            self.assertEqual(supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)["cost"], 0.0)
        self.assertEqual(supervisor.run(self.cfg, FAKE, self.task, self.prompt("SUP-EXIT"), "haiku", 0.5)["cost"],
                         0.004)

    def test_fields_of_another_decision_are_dropped(self):
        # the flat schema lets the model fill every optional field; one that belongs to another decision is dropped,
        # an unknown field is still refused (live: add_next_step came back with "text", 2026-10-20)
        def answer(fields):
            body = {"type": "result", "is_error": False, "total_cost_usd": 0.002, "num_turns": 2,
                    "structured_output": fields}
            return lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, json.dumps(body).encode(), b"")
        base = {"decision": "add_next_step", "reason": "r", "confidence": "high", "for_fred": "", "kind": "code",
                "instructions": "Add the button", "model": "auto"}
        with mock.patch.object(compact.subprocess, "run", side_effect=answer(dict(base, text="", note="x"))):
            got = supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)
        self.assertEqual(got["error"], "")
        self.assertEqual(got["decision"], base)
        # model is always auto for a supervisor step: an omitted or blank one is filled in, another is kept (refused
        # by check) (live: add_next_step came back with no model, 2026-10-20)
        for model in (None, ""):
            fields = dict(base, model=model) if model is not None else {k: v for k, v in base.items() if k != "model"}
            with mock.patch.object(compact.subprocess, "run", side_effect=answer(fields)):
                got = supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)
            self.assertEqual(got["decision"], base)
        with mock.patch.object(compact.subprocess, "run", side_effect=answer(dict(base, model="sonnet"))):
            got = supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)
        self.assertEqual(got["decision"]["model"], "sonnet")
        with mock.patch.object(compact.subprocess, "run", side_effect=answer(dict(base, path="C:/x"))):
            got = supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)
        self.assertIsNone(got["decision"])
        self.assertIn("unknown field path", got["error"])

    def test_invalid_decision_keeps_reported_cost(self):
        got = supervisor.run(self.cfg, FAKE, self.task, self.prompt("SUP-BAD"), "haiku", 0.5)
        self.assertEqual((got["decision"], got["cost"]), (None, 0.004))
        got = supervisor.run(self.cfg, FAKE, self.task, self.prompt("SUP-ERROR"), "haiku", 0.5)
        self.assertEqual((got["decision"], got["cost"]), (None, 0.02))
        for bad in (-1.0, float("nan"), "0.1", None):
            body = json.dumps({"is_error": False, "total_cost_usd": bad, "num_turns": 2,
                               "structured_output": {"decision": "wait", "reason": "r", "confidence": "low",
                                                     "for_fred": ""}})
            with mock.patch.object(compact.subprocess, "run",
                                   lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, body.encode(), b"")):
                self.assertIsNone(supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)["cost"])
        body = json.dumps({"is_error": False, "total_cost_usd": 3.0, "num_turns": 2,
                           "structured_output": {"decision": "wait", "reason": "r", "confidence": "low", "for_fred": ""}})
        with mock.patch.object(compact.subprocess, "run",
                               lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, body.encode(), b"")):
            self.assertEqual(supervisor.run(self.cfg, FAKE, self.task, self.prompt(), "haiku", 0.5)["cost"], 3.0)



class AutoReasonTest(unittest.TestCase):
    def test_auto_table(self):
        pol = dict(supervisor.policy(cfg(), {"project_dir": "D:\\work"}, 0.0), mode="auto", room=2, work_usd=0.0)
        task = {"current": 1, "steps": [{"n": 1, "kind": "code", "state": "done"}]}
        for kind in ("confirm", "keep", "finish", "retry"):
            self.assertEqual(supervisor.auto_reason({"decision": kind}, task, pol), "", kind)
        self.assertEqual(supervisor.auto_reason({"decision": "add_next_step"}, task, pol), "")
        for kind in ("stop", "stepdone", "answer", "escalate_to_fred", "wait"):
            self.assertTrue(supervisor.auto_reason({"decision": kind}, task, pol), kind)
        for mode in ("off", "suggest"):
            self.assertTrue(supervisor.auto_reason({"decision": "finish"}, task, dict(pol, mode=mode)))
        self.assertTrue(supervisor.auto_reason({"decision": "add_next_step"}, task, dict(pol, auto_steps_left=0)))
        self.assertTrue(supervisor.auto_reason({"decision": "add_next_step"}, task, dict(pol, room=0)))
        self.assertTrue(supervisor.auto_reason({"decision": "retry"}, task, dict(pol, work_usd=5.0)))
        self.assertTrue(supervisor.auto_reason({"decision": "retry"}, task, dict(pol, retries={1: 1})))
        self.assertEqual(supervisor.auto_reason({"decision": "finish", "confidence": "high"}, task,
                                                dict(pol, work_usd=99.0)), "")  # finishing starts nothing

    def test_string_step_keys_from_task_json_are_valid(self):
        task = {"project_dir": "D:\\work", "supervisor": dict(supervisor.initial(cfg(), "D:\\work", 0.0),
                                                              retries={"2": 1})}
        p = supervisor.policy(cfg(), task, 0.0)
        self.assertEqual((p["mode"], p["retries"]), ("suggest", {2: 1}))


class SpendViewTest(unittest.TestCase):
    def test_spend_view_folds_settled_unknown_and_reserved(self):
        records = {
            "p1": {"task": "t1", "wake": 1, "day": "2026-10-18", "kind": "wake", "reserved": 0.5, "cost": 0.4,
                   "status": "settled"},
            "p2": {"task": "t1", "wake": 2, "day": "2026-10-18", "kind": "wake", "reserved": 0.3, "cost": 0.0,
                   "status": "unknown"},
            "p3": {"task": "t2", "wake": 1, "day": "2026-10-19", "kind": "replay", "reserved": 0.1, "cost": 0.0,
                   "status": "reserved"},
        }
        view = supervisor.spend_view(records)
        d18 = view["days"]["2026-10-18"]
        self.assertEqual((d18["cost"], d18["runs"], d18["unknown"], d18["reserved"]), (0.4, 2, 1, 0.3))
        self.assertEqual(view["days"]["2026-10-19"]["reserved"], 0.1)
        self.assertEqual(view["tasks"]["t1"]["wakes"][1]["cost"], 0.4)
        self.assertEqual((view["total"]["cost"], view["total"]["runs"]), (0.4, 3))


class ProposalTest(unittest.TestCase):
    """Plan 49: the planner's proposed steps reach the digest, add_next_step can name one, and an added step trims."""

    PLANNED = [{"kind": "code", "goal": "fix X in app.py", "model": "sonnet"},
               {"kind": "verify", "goal": "run the tests", "model": ""}]

    def test_digest_lists_proposed_goals(self):
        with tempfile.TemporaryDirectory() as home:
            task = evidence_task(home)
            task["supervisor"]["proposed"] = [dict(p) for p in self.PLANNED]
            text = supervisor.digest(home, task, context(task))
            self.assertIn("p1 code (sonnet): fix X in app.py", text)
            self.assertIn("p2 verify: run the tests", text)
            self.assertNotIn("Prep proposed kinds", text)
            self.assertLess(text.index("Allowed now"), text.index("p1 code"))
            task["supervisor"]["proposed"] = [{"kind": "code", "goal": f"part {i}", "model": ""} for i in range(1, 10)]
            text = supervisor.digest(home, task, context(task))
            self.assertIn("p8 code: part 8", text)
            self.assertNotIn("p9 code", text)
            self.assertIn("... 1 more", text)
            task["supervisor"]["proposed"] = [{"kind": "code", "goal": "z" * 900, "model": ""}]
            self.assertNotIn("z" * 301, supervisor.digest(home, task, context(task)))

    def check(self, d, proposed=None):
        task = {"id": "t", "state": "waiting", "why": "choose next step", "current": 1, "owner": "fred",
                "steps": [{"n": 1, "kind": "code", "state": "done", "session": "s1"}],
                "supervisor": {"proposed": self.PLANNED if proposed is None else proposed}}
        return supervisor.check(d, task, dict(LEVERS), {"01": ""},
                                {"triggers": ["choose_next"], "owned": [1], "retries_left": 1})

    def test_check_proposal_index_and_kind(self):
        take = ok(decision="add_next_step", proposal=1, model="auto")
        self.assertEqual(self.check(take), (True, ""))
        self.assertTrue(self.check(dict(take, kind="code"))[0])
        self.assertTrue(self.check(dict(take, proposal=2))[0])  # its kind, verify, comes from the proposal
        self.assertEqual(self.check(dict(take, proposal=3)), (False, "proposal p3 is not in the planned list"))
        self.assertEqual(self.check(dict(take, kind="verify")), (False, "kind differs from proposal p1"))
        self.assertFalse(self.check(take, proposed=[])[0])
        self.assertFalse(self.check(dict(take, proposal=0))[0])
        self.assertFalse(self.check(dict(take, proposal=True))[0])
        self.assertFalse(self.check(dict(take, model="sonnet"))[0])
        self.assertFalse(self.check(ok(decision="add_next_step", model="auto", kind="code"))[0])  # no words at all
        self.assertFalse(self.check(ok(decision="wait", proposal=1))[0])  # a field of add_next_step only

    def test_run_fills_kind_from_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = {"id": "20260101-000000-abcd", "project_dir": tmp, "steps": [],
                    "supervisor": {"proposed": [dict(p) for p in self.PLANNED]}}
            prompt = supervisor.build_prompt(kinds.text(tmp, "supervisor"), task, "digest")
            fields = {"decision": "add_next_step", "reason": "r", "confidence": "high", "for_fred": "", "proposal": 2}
            body = {"type": "result", "is_error": False, "total_cost_usd": 0.002, "num_turns": 2,
                    "structured_output": fields}
            with mock.patch.object(compact.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
                    cmd, 0, json.dumps(body).encode(), b"")):
                got = supervisor.run(cfg(), FAKE, task, prompt, "haiku", 0.5)
            self.assertEqual(got["error"], "")
            self.assertEqual((got["decision"]["kind"], got["decision"]["model"], got["decision"]["proposal"]),
                             ("verify", "auto", 2))
            body["structured_output"] = dict(fields, proposal=5)
            with mock.patch.object(compact.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
                    cmd, 0, json.dumps(body).encode(), b"")):
                got = supervisor.run(cfg(), FAKE, task, prompt, "haiku", 0.5)
            self.assertNotIn("kind", got["decision"])  # check() refuses the missing proposal

    def test_trim_proposed(self):
        items = [{"kind": "code", "goal": "a"}, {"kind": "verify", "goal": "b"}, {"kind": "code", "goal": "c"}]
        self.assertEqual(supervisor.trim_proposed(items, "code", 2), [items[2]])  # p1 passed over, p2 used
        self.assertEqual(supervisor.trim_proposed(items, "code"), items[1:])
        self.assertEqual(supervisor.trim_proposed(items, "verify"), [items[0], items[2]])
        self.assertEqual(supervisor.trim_proposed(items, "design"), items)
        self.assertEqual(supervisor.trim_proposed(items, "code", 9), items[1:])  # a stale index: the kind rule
        self.assertEqual(supervisor.trim_proposed(None, "code"), [])
        self.assertEqual(len(items), 3)  # the input is untouched

    def test_revision_changes_with_proposed(self):
        with tempfile.TemporaryDirectory() as home:
            task = evidence_task(home)
            rev = supervisor.revision(home, task)
            task["supervisor"]["proposed"] = [dict(p) for p in self.PLANNED]
            planned = supervisor.revision(home, task)
            self.assertNotEqual(rev, planned)
            task["supervisor"]["proposed"][0]["model"] = "opus"  # the model is not what a decision names
            self.assertEqual(supervisor.revision(home, task), planned)
            task["supervisor"]["proposed"] = task["supervisor"]["proposed"][1:]
            self.assertNotEqual(supervisor.revision(home, task), planned)


class LooseEndsTest(unittest.TestCase):
    """Plan 51: a tier word from Fred's next-step message, and the uncertain card keeps its decision."""

    def check(self, model, triggers=("message",), words="verify on Opus"):
        task = {"id": "t", "state": "waiting", "why": "choose next step", "current": 1, "owner": "fred",
                "steps": [{"n": 1, "kind": "code", "state": "done", "session": "s1"}]}
        d = ok(decision="add_next_step", kind="verify", instructions="check it", model=model)
        return supervisor.check(d, task, dict(LEVERS), {"01": ""},
                                {"triggers": list(triggers), "owned": [1], "retries_left": 1, "fred_words": words})

    def test_message_step_may_name_a_tier_word(self):
        self.assertEqual(self.check("opus"), (True, ""))
        self.assertEqual(self.check("auto"), (True, ""))
        self.assertEqual(self.check("auto", triggers=("choose_next",), words=""), (True, ""))
        self.assertEqual(self.check("opus", words="verify it"), (False, "the model must be one Fred's message names"))
        self.assertEqual(self.check("opus", triggers=("choose_next",)), (False, "a supervisor step runs on model auto"))
        self.assertEqual(self.check("sonnet", words="write two sonnets"),
                         (False, "the model must be one Fred's message names"))  # a whole word only
        for bad in ("fable", "claude-opus-5-5", "codex:gpt-6-luna"):
            self.assertFalse(self.check(bad, words=f"verify on {bad}")[0], bad)

    def test_fold_keeps_uncertain_decision_and_intent(self):
        add = ok(decision="add_next_step", kind="code", instructions="fix", model="auto")
        intent = {"call": "request_next", "request_id": "r1", "source_step": 1}
        records = [{"ts": 1.0, "wake": 2, "phase": "claimed", "events": ["e2"]},
                   {"ts": 2.0, "wake": 2, "phase": "result", "decision": add, "status": "suggest", "triggers": ["message"],
                    "cost": 0.001, "day": "2026-10-20"},
                   {"ts": 3.0, "wake": 2, "phase": "dispatching", "status": "dispatching", "dispatch": intent, "by": "fred"},
                   {"ts": 4.0, "wake": 2, "phase": "recovered", "outcome": "uncertain", "events": ["e2"]}]
        pending = supervisor.fold_log(records)["pending"]
        self.assertEqual(pending["status"], "uncertain")
        self.assertEqual(pending["decision"], add)
        self.assertEqual(pending["triggers"], ["message"])
        self.assertEqual(pending["dispatch"], intent)
        bare = supervisor.fold_log([records[0], dict(records[2])])["pending"]
        self.assertEqual(bare["status"], "uncertain")
        self.assertIsNone(bare["decision"])


if __name__ == "__main__":
    unittest.main()
