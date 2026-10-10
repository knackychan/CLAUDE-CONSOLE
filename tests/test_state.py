import copy
import unittest

from console import paths
from console.state import State

T0 = 1_000_000.0


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

    def test_timeline_turns_and_agents(self):
        self.feed(ev("UserPromptSubmit", T0),
                  ev("SubagentStart", T0 + 2, agent_id="a1", agent_type="Explore"),
                  ev("SubagentStop", T0 + 6, agent_id="a1"),
                  ev("Stop", T0 + 8),
                  ev("UserPromptSubmit", T0 + 20),
                  ev("PreToolUse", T0 + 21, agent_id="a2", agent_type="verifier", tool="Bash"))
        t = self.state.timeline("s1", T0 + 30)
        self.assertEqual((t["start"], t["end"]), (T0, T0 + 30))
        self.assertEqual([lane["label"] for lane in t["lanes"]], ["main", "Explore", "verifier"])
        self.assertEqual(t["lanes"][0]["spans"], [[T0, T0 + 8], [T0 + 20, T0 + 30]])
        self.assertEqual(t["lanes"][1]["spans"], [[T0 + 2, T0 + 6]])
        self.assertEqual(t["lanes"][2]["spans"], [[T0 + 21, T0 + 30]])
        self.assertIsNone(self.state.timeline("nope", T0))

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

    def test_model_mix(self):
        self.feed(ev("Stop", T0, sid="a", model="claude-opus-5-5"),
                  ev("SubagentStop", T0 + 1, sid="a", agent_id="x1", model="claude-haiku-5-5"),
                  ev("SubagentStop", T0 + 2, sid="a", agent_id="x2", model="claude-haiku-5-5"),
                  ev("SubagentStart", T0 + 3, sid="a", agent_id="x3"),
                  ev("run_started", T0 + 4, sid="b", model="sonnet"),
                  ev("run_ended", T0 + 5, sid="b", cost=0.25, subtype="success"),
                  ev("run_started", T0 + 6, sid="b"),
                  ev("run_ended", T0 + 7, sid="b", cost=0.5, subtype="success"),
                  ev("Stop", T0 + 8, sid="c", model="gpt-5"),
                  ev("Stop", T0 - 90000, sid="old", model="claude-fable-5-1"))
        self.assertEqual(self.state.snapshot(T0 + 9)["mix"],
                         {"models": [["opus", 1], ["sonnet", 1], ["haiku", 2], ["gpt-5", 1]], "runs": 2, "cost": 0.75})


if __name__ == "__main__":
    unittest.main()
