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

    def test_pasted_prompt_title_and_drive_letter(self):
        self.feed(ev("UserPromptSubmit", T0, prompt='<pasted_content id="9a1c"> Project: D:/x', project_dir="d:/repo"),
                  ev("Stop", T0 + 1, sid="s2", project_dir="D:/repo"))
        self.assertEqual(self.row(T0 + 2)["title"], "Project: D:/x")
        self.assertEqual({r["project_dir"] for r in self.state.snapshot(T0 + 2)["sessions"]}, {"D:/repo"})


if __name__ == "__main__":
    unittest.main()
