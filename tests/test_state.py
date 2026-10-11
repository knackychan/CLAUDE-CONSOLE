import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from console import paths, usage
from console.state import State

T0 = 1_000_000.0


def line(mid, ts, model, **use):
    """One transcript line with a usage block, `ts` seconds since the epoch."""
    stamp = datetime.fromtimestamp(ts, timezone.utc).isoformat()
    return json.dumps({"type": "assistant", "timestamp": stamp,
                       "message": {"id": mid, "model": model, "usage": use}}) + "\n"


def ev(event, ts, sid="s1", **extra):
    rec = {"event": event, "ts": ts, "session_id": sid, "project": "repo", "project_dir": "D:/repo"}
    rec.update(extra)
    return rec


class StateTest(unittest.TestCase):
    def setUp(self):
        self.state = State(copy.deepcopy(paths.DEFAULTS))

    def feed(self, *recs):
        for rec in recs:
            self.state.apply(rec)

    def row(self, now, sid="s1"):
        return next(r for r in self.state.snapshot(now)["sessions"] if r["id"] == sid)

    def test_turn_lifecycle_running_quiet_stall_idle_stale(self):
        self.feed(ev("UserPromptSubmit", T0, prompt="fix the updater retry"))
        self.assertEqual(self.row(T0 + 10)["state"], "running")
        self.assertEqual(self.row(T0 + 200)["state"], "quiet")
        self.assertEqual(self.row(T0 + 700)["state"], "stall")
        self.assertEqual(self.row(T0 + 700)["group"], "needs")
        self.feed(ev("Stop", T0 + 20))
        self.assertEqual(self.row(T0 + 30)["state"], "idle")
        self.assertEqual(self.row(T0 + 30)["group"], "working")
        self.assertEqual(self.row(T0 + 2000)["state"], "stale")
        self.assertEqual(self.row(T0 + 2000)["group"], "done")
        self.assertEqual(self.row(T0 + 30)["title"], "fix the updater retry")

    def test_stop_question_blocked_failed_done(self):
        self.feed(ev("UserPromptSubmit", T0), ev("Stop", T0 + 5, stop_question="how many retries?"))
        self.assertEqual((self.row(T0 + 6)["state"], self.row(T0 + 6)["group"]), ("stop", "needs"))
        self.feed(ev("UserPromptSubmit", T0 + 10))
        self.assertEqual(self.row(T0 + 11)["state"], "running")
        self.feed(ev("PermissionDenied", T0 + 12, tool="Bash", what="git push", reason="[Push]"))
        self.assertEqual(self.row(T0 + 13)["state"], "blocked")
        self.feed(ev("UserPromptSubmit", T0 + 14), ev("StopFailure", T0 + 15, error="rate_limit"))
        self.assertEqual(self.row(T0 + 16)["state"], "failed")
        self.feed(ev("SessionEnd", T0 + 17))
        self.assertEqual((self.row(T0 + 18)["state"], self.row(T0 + 18)["group"]), ("done", "done"))

    def test_stop_sets_model_source_route_and_gauge(self):
        self.feed(ev("UserPromptSubmit", T0),
                  ev("Stop", T0 + 1, model="claude-opus-5-5", context_tokens=330000,
                     entrypoint="claude-vscode", route="risky, opus, high"))
        row = self.row(T0 + 2)
        self.assertEqual((row["model"], row["source"], row["route"]), ("claude-opus-5-5", "vscode", "risky, opus, high"))
        self.assertEqual((row["ctx_fill"], row["ctx_tone"], row["group"]), (1.0, "red", "needs"))
        self.feed(ev("PostCompact", T0 + 3))
        self.assertIsNone(self.row(T0 + 4)["ctx_fill"])

    def test_gauge_thresholds(self):
        for tokens, tone in ((10000, "green"), (150000, "yellow"), (300000, "red")):
            self.feed(ev("Stop", T0, sid=f"g{tokens}", context_tokens=tokens))
            self.assertEqual(self.row(T0 + 1, f"g{tokens}")["ctx_tone"], tone)

    def test_agents_nest_under_their_session(self):
        self.feed(ev("UserPromptSubmit", T0),
                  ev("SubagentStart", T0 + 1, agent_id="a1", agent_type="verifier"),
                  ev("PreToolUse", T0 + 2, agent_id="a1", agent_type="verifier", effort="low",
                     tool="Bash", what="py -m unittest"),
                  ev("PreToolUse", T0 + 3, tool="Edit", what="updater.py"))
        row = self.row(T0 + 4)
        self.assertEqual(row["doing"], "Edit updater.py")
        agent = row["agents"][0]
        self.assertEqual((agent["type"], agent["effort"], agent["doing"], agent["steps"]),
                         ("verifier", "low", "Bash py -m unittest", 1))
        self.feed(ev("SubagentStop", T0 + 5, agent_id="a1", model="claude-sonnet-5-5", context_tokens=9100))
        agent = self.row(T0 + 6)["agents"][0]
        self.assertEqual((agent["text"], agent["model"], agent["tokens"]), ("Done", "claude-sonnet-5-5", 9100))
        self.assertEqual((agent["ctx_fill"], agent["ctx_tone"]), (0.03, "green"))
        steps = self.state.steps("s1")
        self.assertEqual([s["agent_type"] for s in steps], ["verifier", "main"])

    def test_two_writers_in_one_repo(self):
        self.feed(ev("PreToolUse", T0, sid="a", tool="Edit", what="x.py"),
                  ev("PreToolUse", T0 + 1, sid="b", tool="Write", what="y.py"),
                  ev("PreToolUse", T0 + 2, sid="c", tool="Read", what="z.py"))
        snap = self.state.snapshot(T0 + 10)
        self.assertEqual(snap["writers"], [{"project_dir": "D:/repo", "sessions": ["a", "b"]}])
        flags = {r["id"]: r["two_writers"] for r in snap["sessions"]}
        self.assertEqual(flags, {"a": True, "b": True, "c": False})
        self.assertEqual(self.state.snapshot(T0 + 700)["writers"], [])

    def test_old_sessions_are_hidden_and_order_is_stable(self):
        self.feed(ev("Stop", T0, sid="old"), ev("Stop", T0 + 90000, sid="new1"),
                  ev("Stop", T0 + 90001, sid="new2"), ev("PreToolUse", T0 + 90002, sid="new1", tool="Read"))
        ids = [r["id"] for r in self.state.snapshot(T0 + 90003)["sessions"]]
        self.assertEqual(ids, ["new1", "new2"])

    def test_window_run_lifecycle(self):
        self.feed(ev("run_started", T0, title="Fix add() in calc.py", route="mechanical",
                     reason="small", prep="p1", start_commit="abc", model="sonnet", effort="low"),
                  ev("UserPromptSubmit", T0 + 1, prompt="Goal: Fix add()"),
                  ev("Stop", T0 + 5, entrypoint="claude-vscode", model="claude-sonnet-5-5"),
                  ev("SessionEnd", T0 + 6),
                  ev("run_ended", T0 + 6, cost=0.25, subtype="success"))
        row = self.row(T0 + 7)
        self.assertEqual((row["state"], row["source"], row["title"], row["route"]),
                         ("idle", "window", "Fix add() in calc.py", "mechanical"))
        self.assertEqual((row["window"], row["run_live"], row["cost"], row["prep"], row["start_commit"]),
                         (True, False, 0.25, "p1", "abc"))
        self.assertEqual(row["model"], "claude-sonnet-5-5")

    def test_interrupted_stopped_and_denied_runs(self):
        self.feed(ev("run_started", T0), ev("run_ended", T0 + 5, interrupted=True))
        row = self.row(T0 + 6)
        self.assertEqual((row["state"], row["symbol"], row["group"]), ("interrupted", "‖", "needs"))
        self.feed(ev("run_started", T0 + 10), ev("run_ended", T0 + 12, stopped=True))
        self.assertEqual((self.row(T0 + 13)["state"], self.row(T0 + 13)["stopped"]), ("idle", True))
        self.feed(ev("run_started", T0 + 20),
                  ev("run_ended", T0 + 22, denials=[{"tool": "Bash", "what": "git push"}]))
        row = self.row(T0 + 23)
        self.assertEqual((row["state"], row["denied"]["what"]), ("blocked", "git push"))
        self.feed(ev("run_started", T0 + 30),  # it still succeeded: Idle, the denials only as a note
                  ev("run_ended", T0 + 32, subtype="success",
                     denials=[{"tool": "Bash", "what": "find ."}, {"tool": "PowerShell", "what": "ls"}]))
        row = self.row(T0 + 33)
        self.assertEqual((row["state"], row["group"], row["denied"]), ("idle", "working", None))
        self.assertEqual([d["tool"] for d in row["denials"]], ["Bash", "PowerShell"])
        self.feed(ev("run_started", T0 + 40))
        self.assertEqual(self.row(T0 + 41)["denials"], [])

    def test_pasted_prompt_title_and_drive_letter(self):
        self.feed(ev("UserPromptSubmit", T0, prompt='<pasted_content id="9a1c"> Project: D:/x', project_dir="d:/repo"),
                  ev("Stop", T0 + 1, sid="s2", project_dir="D:/repo"))
        self.assertEqual(self.row(T0 + 2)["title"], "Project: D:/x")
        self.assertEqual({r["project_dir"] for r in self.state.snapshot(T0 + 2)["sessions"]}, {"D:/repo"})
        self.feed(ev("UserPromptSubmit", T0 + 3, sid="s3", prompt="<browser_instruction># Claude in Chrome…"),
                  ev("UserPromptSubmit", T0 + 4, sid="s3", prompt="fix the title"))
        self.assertEqual(self.row(T0 + 5, "s3")["title"], "fix the title")

    def test_verdict_from_agent_and_main(self):
        self.feed(ev("UserPromptSubmit", T0),
                  ev("SubagentStart", T0 + 1, agent_id="v1", agent_type="verifier"),
                  ev("SubagentStop", T0 + 5, agent_id="v1", verdict="FAIL", verdict_detail="test_calc.py:9 - 3 != 4"),
                  ev("Stop", T0 + 6))
        row = self.row(T0 + 7)
        self.assertEqual((row["verdict"], row["verdict_detail"], row["agents"][0]["verdict"]),
                         ("FAIL", "test_calc.py:9 - 3 != 4", "FAIL"))
        self.feed(ev("UserPromptSubmit", T0 + 8), ev("Stop", T0 + 9, verdict="PASS"))
        self.assertEqual((self.row(T0 + 10)["verdict"], self.row(T0 + 10)["verdict_detail"]), ("PASS", ""))

    def test_escalate_and_handoff_runs(self):
        self.feed(ev("run_started", T0, kind="run", model="sonnet", effort="low"),
                  ev("run_ended", T0 + 5, subtype="success"),
                  ev("run_started", T0 + 6, kind="escalate", escalated="sonnet/low -> sonnet/medium"),
                  ev("run_ended", T0 + 9, subtype="success"))
        row = self.row(T0 + 10)
        self.assertEqual((row["escalated"], row["kind"]), ("sonnet/low -> sonnet/medium", "escalate"))
        self.feed(ev("run_started", T0 + 11, kind="handoff"))
        self.assertEqual((self.row(T0 + 12)["state"], self.row(T0 + 12)["handoff"]), ("running", True))
        self.feed(ev("run_ended", T0 + 13, subtype="error_during_execution"))
        self.assertEqual(self.row(T0 + 14)["state"], "idle")  # a failed handoff is not Done
        self.feed(ev("run_started", T0 + 15, kind="handoff"), ev("run_ended", T0 + 16, subtype="success"))
        self.assertEqual((self.row(T0 + 17)["state"], self.row(T0 + 17)["group"]), ("done", "done"))
        self.feed(ev("run_started", T0 + 18, kind="continue"))
        self.assertEqual(self.row(T0 + 19)["state"], "running")

    def test_fork_of_a_vscode_session(self):
        self.feed(ev("UserPromptSubmit", T0, sid="v", prompt="fix the updater"),
                  ev("UserPromptSubmit", T0 + 1, sid="v"),
                  ev("Stop", T0 + 2, sid="v", context_tokens=1000, entrypoint="claude-vscode"),
                  ev("run_started", T0 + 3, sid="f", kind="handoff", forked_from="v", title="↳ fix the updater"),
                  ev("UserPromptSubmit", T0 + 4, sid="f", prompt="/session-handoff"),
                  ev("run_ended", T0 + 6, sid="f", subtype="success"))
        parent, fork = self.row(T0 + 7, "v"), self.row(T0 + 7, "f")
        self.assertEqual((parent["forks"], parent["state"], parent["source"]), (["f"], "done", "vscode"))
        self.assertEqual((fork["forked_from"], fork["title"], fork["follow_ups"], fork["source"]),
                         ("v", "↳ fix the updater", 2, "window"))
        self.feed(ev("UserPromptSubmit", T0 + 8, sid="v"))  # Fred typed in VS Code again
        self.assertEqual(self.row(T0 + 9, "v")["state"], "running")

    def test_follow_up_hint(self):
        self.feed(ev("UserPromptSubmit", T0), ev("Stop", T0 + 1), ev("UserPromptSubmit", T0 + 2), ev("Stop", T0 + 3))
        self.assertEqual((self.row(T0 + 4)["follow_ups"], self.row(T0 + 4)["handoff_hint"]), (1, False))
        self.feed(ev("UserPromptSubmit", T0 + 5), ev("Stop", T0 + 6))
        self.assertEqual((self.row(T0 + 7)["follow_ups"], self.row(T0 + 7)["handoff_hint"]), (2, True))
        self.feed(ev("Stop", T0, sid="big", context_tokens=400000))
        self.assertTrue(self.row(T0 + 1, "big")["handoff_hint"])
        self.assertFalse(self.row(T0 + 4000, "big")["handoff_hint"])  # Stale?: no hint

    def test_rules_size_warning(self):
        self.feed(ev("InstructionsLoaded", T0, file="~/.claude/CLAUDE.md", scope="User", lines=3, bytes=229,
                     load_reason="session_start"),
                  ev("InstructionsLoaded", T0, file="CLAUDE.md", scope="Project", lines=149, bytes=20791),
                  ev("InstructionsLoaded", T0 + 1, agent_id="a1", file="web/CLAUDE.md", lines=900, bytes=1),
                  ev("UserPromptSubmit", T0 + 2, prompt="fix it"))
        row = self.row(T0 + 3)
        self.assertEqual([r["file"] for r in row["rules"]], ["~/.claude/CLAUDE.md", "CLAUDE.md"])  # not the agent's
        self.assertEqual((row["rules_bytes"], row["rules_warn"]), (21020, "21.0 KB in all (over 16 KB)"))
        self.feed(ev("InstructionsLoaded", T0 + 4, file="CLAUDE.md", scope="Project", lines=230, bytes=9000),
                  ev("InstructionsLoaded", T0 + 4, sid="small", file="CLAUDE.md", lines=33, bytes=2085))
        self.assertEqual(self.row(T0 + 5)["rules_warn"], "CLAUDE.md 230 lines (over 200)")
        self.assertEqual(self.row(T0 + 5, "small")["rules_warn"], "")

    def test_should_delegate_flag(self):
        self.feed(ev("UserPromptSubmit", T0))
        for i in range(9):
            self.feed(ev("PreToolUse", T0 + 1 + i, tool="Read", what=f"f{i}.py"))
        self.feed(ev("PreToolUse", T0 + 10, agent_id="a1", agent_type="Explore", tool="Read"),
                  ev("PreToolUse", T0 + 11, tool="Edit", what="f1.py"))
        self.assertEqual((self.row(T0 + 12)["reads"], self.row(T0 + 12)["delegate_hint"]), (9, False))
        self.feed(ev("PreToolUse", T0 + 13, tool="Grep", what="def x"), ev("Stop", T0 + 14))
        self.assertEqual((self.row(T0 + 15)["reads"], self.row(T0 + 15)["delegate_hint"]), (10, True))
        self.feed(ev("UserPromptSubmit", T0 + 16))
        self.assertEqual((self.row(T0 + 17)["reads"], self.row(T0 + 17)["delegate_hint"]), (0, False))

    def test_handoff_typed_or_called_in_a_chat(self):
        self.feed(ev("UserPromptSubmit", T0, sid="typed", prompt="/session-handoff"),
                  ev("Stop", T0 + 5, sid="typed"),
                  ev("UserPromptSubmit", T0, sid="called", prompt="its time to handoff, give me the prompt"),
                  ev("PreToolUse", T0 + 1, sid="called", tool="Skill", what="session-handoff"),
                  ev("UserPromptSubmit", T0, sid="failed", prompt="/session-handoff"),
                  ev("StopFailure", T0 + 2, sid="failed", error="rate_limit"),
                  ev("UserPromptSubmit", T0, sid="agent", prompt="go"),
                  ev("PreToolUse", T0 + 1, sid="agent", agent_id="a1", tool="Skill", what="session-handoff"),
                  ev("Stop", T0 + 2, sid="agent"))
        self.assertEqual(self.row(T0 + 6, "typed")["state"], "done")
        self.assertEqual(self.row(T0 + 2, "called")["state"], "running")  # Done only once the turn ends
        self.feed(ev("Stop", T0 + 3, sid="called"))
        self.assertEqual((self.row(T0 + 4, "called")["state"], self.row(T0 + 4, "called")["group"]), ("done", "done"))
        self.assertEqual(self.row(T0 + 3, "failed")["state"], "failed")
        self.assertEqual(self.row(T0 + 3, "agent")["state"], "idle")
        self.feed(ev("UserPromptSubmit", T0 + 7, sid="typed", prompt="one more thing"), ev("Stop", T0 + 8, sid="typed"))
        self.assertEqual(self.row(T0 + 9, "typed")["state"], "idle")  # a new prompt reopens it

    def test_spent_exact_or_estimated_and_today(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        chat, run = str(Path(tmp.name) / "a.jsonl"), str(Path(tmp.name) / "b.jsonl")
        Path(chat).write_text(line("m1", T0 - 60, "claude-opus-5-5", input_tokens=1_000_000), encoding="utf-8")
        agent = Path(usage.agent_path(chat, "x1"))
        agent.parent.mkdir(parents=True)
        agent.write_text(line("m2", T0 - 30, "claude-haiku-5-5", output_tokens=2_000_000), encoding="utf-8")
        Path(run).write_text(line("m3", T0 - 20, "claude-sonnet-5-5", input_tokens=500_000), encoding="utf-8")
        self.feed(ev("UserPromptSubmit", T0 - 100, sid="a", transcript_path=chat),
                  ev("SubagentStart", T0 - 40, sid="a", agent_id="x1", agent_type="Explore"),
                  ev("run_started", T0 - 50, sid="b", model="sonnet"),
                  ev("UserPromptSubmit", T0 - 49, sid="b", transcript_path=run),
                  ev("run_ended", T0 - 10, sid="b", cost=1.25, subtype="success"),
                  ev("run_started", T0 - 5, sid="c", model="sonnet"),
                  ev("UserPromptSubmit", T0 - 4, sid="d"))
        reader = usage.Usage(paths.DEFAULTS["prices"])
        for f in self.state.transcripts(T0):
            reader.poll(f)
        snap = self.state.snapshot(T0, reader)
        rows = {r["id"]: r for r in snap["sessions"]}
        self.assertEqual((rows["a"]["spent"], rows["a"]["spent_exact"], rows["a"]["burn"]), (5.0, False, 1.0))
        self.assertEqual(rows["a"]["agents"][0]["cost"], 1.0)
        self.assertEqual((rows["b"]["spent"], rows["b"]["spent_exact"]), (1.25, True))
        self.assertEqual((rows["c"]["spent"], rows["c"]["spent_exact"]), (None, False))  # live, no transcript yet
        self.assertIsNone(rows["d"]["spent"])
        self.assertEqual(snap["spend"], {"today": 6.25, "exact": 1.25, "estimated": 5.0, "burn": 1.2, "budget": 15,
                                         "runs": 1, "models": [["opus", 0.667], ["sonnet", 0.167], ["haiku", 0.167]]})
        self.assertEqual(self.state.snapshot(T0)["spend"]["today"], 1.25)  # no reader: exact only

    def test_route_prep_agent_models_and_escalation(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        chat = str(Path(tmp.name) / "r.jsonl")
        Path(chat).write_text(line("m1", T0 - 60, "claude-opus-5-5", output_tokens=300_000), encoding="utf-8")
        agent = Path(usage.agent_path(chat, "x1"))
        agent.parent.mkdir(parents=True)
        agent.write_text(line("m2", T0 - 30, "claude-haiku-5-5", output_tokens=4_000_000), encoding="utf-8")
        self.feed(ev("run_started", T0 - 100, sid="r", model="opus", prep="p1", prep_model="haiku",
                     prep_cost=0.02, prep_turns=3),
                  ev("UserPromptSubmit", T0 - 99, sid="r", transcript_path=chat),
                  ev("SubagentStart", T0 - 40, sid="r", agent_id="x1", agent_type="Explore"),
                  ev("run_started", T0 - 20, sid="r", kind="escalate", escalated="sonnet/high -> opus/high"))
        reader = usage.Usage(paths.DEFAULTS["prices"])
        for f in self.state.transcripts(T0):
            reader.poll(f)
        row = self.state.snapshot(T0, reader)["sessions"][0]
        self.assertEqual((row["prep_model"], row["prep_cost"], row["prep_turns"]), ("haiku", 0.02, 3))
        self.assertEqual((row["escalated"], row["escalated_ts"]), ("sonnet/high -> opus/high", T0 - 20))
        self.assertEqual(row["agents"][0]["model"], "haiku")  # still running: named by its transcript
        self.assertEqual(row["models"], [["opus", 0.75], ["haiku", 0.25]])  # opus $6, haiku $2
        self.assertEqual(self.state.snapshot(T0)["sessions"][0]["models"], [])  # no reader, no shares

    def test_projects_for_the_picker(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        chat = str(Path(tmp.name) / "a.jsonl")
        Path(chat).write_text(line("m1", T0 - 60, "claude-opus-5-5", input_tokens=1_000_000), encoding="utf-8")
        self.feed(ev("UserPromptSubmit", T0 - 4 * 86400, sid="o", project="OLD", project_dir="D:/old"),
                  ev("UserPromptSubmit", T0 - 100, sid="a", transcript_path=chat),
                  ev("run_started", T0 - 50, sid="b", model="sonnet"),
                  ev("run_ended", T0 - 10, sid="b", cost=1.25, subtype="success"))
        reader = usage.Usage(paths.DEFAULTS["prices"])
        for f in self.state.transcripts(T0):
            reader.poll(f)
        snap = self.state.snapshot(T0, reader)
        self.assertEqual([r["id"] for r in snap["sessions"]], ["a", "b"])  # the old session is not shown ...
        self.assertEqual(snap["projects"], [  # ... but its project still is a choice
            {"dir": "D:/old", "name": "OLD", "last_ts": T0 - 4 * 86400, "today": 0.0},
            {"dir": "D:/repo", "name": "repo", "last_ts": T0 - 10, "today": 5.25}])
        self.assertEqual(self.state.snapshot(T0)["projects"][1]["today"], 1.25)  # no reader: exact only

    def test_activity_cells_per_minute(self):
        now = 1_000_020.0  # a minute boundary
        recs = [ev("UserPromptSubmit", now - 1900)]
        for back, n, agents in ((-10, 12, 2), (5 * 60 - 1, 1, 0), (600, 4, 0), (29 * 60, 7, 0), (31 * 60, 1, 0)):
            recs += [ev("PreToolUse", now - back, tool="Read", what="a.py",
                        **({"agent_id": "x1"} if k < agents else {})) for k in range(n)]
        self.feed(*sorted(recs, key=lambda r: r["ts"]))
        row = self.row(now + 30)
        self.assertEqual(row["activity"], [3] + [0] * 18 + [2] + [0] * 4 + [1] + [0] * 4 + [4])
        self.assertEqual((row["main_steps"], row["turn_ts"]), (23, now - 1900))


if __name__ == "__main__":
    unittest.main()
