"""Plan 48 section 7: GET /api/task `recovery`, what definitely finished and what was cut, from saved fields only."""
import json
import time
from unittest import mock

from console import runs, server, supervisor, tasks
from tests.test_server import TaskServerTest as _TaskServerTest

LOOK = {"kind": "scout", "goal": "look around"}


class TaskRecoveryTest(_TaskServerTest):
    def cut_task(self, steps):
        """The last step's run dies without a result (its process is killed), after its one retry: stuck."""
        tid = self.make_task(steps=steps)
        n = len(steps)
        task = self.until(tid, lambda t: t["steps"][n - 1]["state"] == "running" and t["steps"][n - 1]["session"],
                          "the last step runs")
        s = task["steps"][n - 1]
        s["retries"] = 1  # its automatic retry is spent: the cut leaves it stuck for Fred
        sid = s["session"]
        end = time.time() + 15
        while time.time() < end and sid not in self.hub.runs.live:
            time.sleep(0.05)
        self.hub.runs.live[sid].kill()
        return self.until(tid, lambda t: t["state"] == "stuck", "the cut step is stuck")

    def restart(self):
        again = server.Hub(self.hub.cfg, self.folder, self.hub.runs.exe)
        again.user_home = self.hub.user_home
        return again

    def test_cut_after_done_names_both(self):
        task = self.cut_task([LOOK, {"kind": "explain", "goal": "say what you saw SLOW"}])
        rec = self.task(task["id"])[1]["recovery"]
        first = task["steps"][0]
        self.assertEqual({k: rec["done"][k] for k in ("step", "kind", "how", "verdict", "handoff")},
                         {"step": 1, "kind": "scout", "how": "finished", "verdict": "",
                          "handoff": tasks.note_file(task, first)})
        self.assertEqual(rec["done"]["ended"], first["ended"])
        self.assertEqual({k: rec["cut"][k] for k in ("step", "kind", "attempt", "cause")},
                         {"step": 2, "kind": "explain", "attempt": 1, "cause": "interrupted"})
        # "(no HANDOFF block)" is added when the kill lands before the fake's first line: both are the saved why
        self.assertTrue(rec["cut"]["why"].startswith("the run did not finish cleanly"), rec["cut"]["why"])
        self.assertIsNone(rec["orphan"])

    def test_cut_on_first_step_has_no_done(self):
        task = self.cut_task([{"kind": "scout", "goal": "look around SLOW"}])
        rec = self.task(task["id"])[1]["recovery"]
        self.assertIsNone(rec["done"])
        self.assertEqual((rec["cut"]["step"], rec["cut"]["cause"]), (1, "interrupted"))

    def test_cause_is_saved_on_the_attempt(self):
        task = self.cut_task([{"kind": "scout", "goal": "look around SLOW"}])
        self.assertEqual(tasks.load(self.folder, task["id"])["steps"][0]["attempts"][-1]["cause"], "interrupted")
        tid = self.make_task(steps=[{"kind": "scout", "goal": "look around SLOW"}])
        self.until(tid, lambda t: t["steps"][0]["session"] and t["steps"][0]["state"] == "running", "it runs")
        self.assertEqual(self.call("/api/task/stop", {"task": tid})[0], 200)
        task = self.until(tid, lambda t: t["steps"][0]["state"] == "failed", "the stopped step ends")
        self.assertEqual(task["steps"][0]["attempts"][-1]["cause"], "stopped")
        self.assertEqual(self.task(tid)[1]["recovery"]["cut"]["cause"], "stopped")
        tid = self.make_task(steps=[{"kind": "scout", "goal": "look around MAXTURNS"}])
        task = self.until(tid, lambda t: t["state"] == "stuck", "the capped step is stuck")
        self.assertEqual([a["cause"] for a in task["steps"][0]["attempts"]], ["failed", "failed"])
        cut = self.task(tid)[1]["recovery"]["cut"]
        self.assertEqual((cut["attempt"], cut["cause"]), (2, "failed"))
        self.assertIn("turn cap", cut["why"])
        tid = self.make_task(steps=[LOOK])
        task = self.until(tid, lambda t: t["state"] == "done", "a clean step")
        self.assertEqual(task["steps"][0]["attempts"][-1]["cause"], "ok")
        self.assertIsNone(self.task(tid)[1]["recovery"])

    def test_missing_evidence_is_unknown(self):
        task = self.cut_task([LOOK, {"kind": "explain", "goal": "say what you saw SLOW"}])
        task["steps"][1]["attempts"][-1].pop("cause")  # an attempt from before the cause was saved
        (self.folder / "tasks" / task["id"] / tasks.note_file(task, task["steps"][0])).unlink()
        with mock.patch.object(self.hub, "session", return_value=None):  # its run is gone from the event log
            rec = self.task(task["id"])[1]["recovery"]
        self.assertEqual(rec["cut"]["cause"], "unknown")
        self.assertEqual((rec["done"]["step"], rec["done"]["handoff"]), (1, ""))

    def test_result_before_crash_is_done_not_cut(self):
        tid = self.make_task(steps=[LOOK])
        task = self.until(tid, lambda t: t["steps"][0]["session"], "the step starts")
        sid = task["steps"][0]["session"]
        self.wait_idle(sid)
        meta = self.hub.runs.meta(sid)
        self.hub.runs._save_meta(dict(meta, ended=None))  # the service died after the result, before run_ended
        for path in self.folder.glob("events-*.jsonl"):
            kept = [line for line in path.read_text(encoding="utf-8").splitlines()
                    if not (f'"{sid}"' in line and '"run_ended"' in line)]
            path.write_text("".join(line + "\n" for line in kept), encoding="utf-8")
        again = self.restart()
        again.runs.reconcile()
        end = time.time() + 25
        while time.time() < end and again.tasks[tid]["state"] != "done":
            again.poll_once()
            again.advance()
            time.sleep(0.1)
        task = again.tasks[tid]
        self.assertEqual((task["state"], task["steps"][0]["state"]), ("done", "done"))
        self.assertEqual(task["steps"][0]["attempts"][-1]["cause"], "ok")
        self.assertIsNone(again.recovery(task))
        while time.time() < end and (again.runs.live or again.briefing):
            time.sleep(0.1)

    def test_live_orphan_is_named_and_retry_stays_off(self):
        tid = self.make_task(steps=[LOOK])
        task = self.until(tid, lambda t: t["state"] == "done", "the step ends")
        while self.hub.briefing:
            time.sleep(0.1)
        s = task["steps"][0]
        sid = s["session"]
        self.hub.runs.runs.mkdir(parents=True, exist_ok=True)  # a run an earlier service started (done freed its meta)
        self.hub.runs._save_meta({"session_id": sid, "pid": 4, "cwd": str(self.project), "offset": 0,
                                  "model": "sonnet", "effort": "low", "started": 1000.0, "ended": None})
        s["attempts"][-1].update(ended=None, cause="")
        s.update(state="running", ended=None)
        task.update(state="running", owner="service")
        with mock.patch.object(runs.claude_cli, "run_alive", return_value=True), \
                mock.patch.object(runs.claude_cli, "pid_alive", return_value=True):
            status, data = self.task(tid)
            self.assertEqual(data["recovery"]["orphan"], {"step": 1, "attempt": 1})
            self.assertIsNone(data["recovery"]["cut"])
            self.assertNotEqual(data["levers"]["retry"], "")
            self.assertEqual(data["levers"]["stop"], "")
            self.assertEqual(self.call("/api/task/retry", {"task": tid})[0], 409)  # no second writer

    def test_get_task_is_read_only(self):
        task = self.cut_task([LOOK, {"kind": "explain", "goal": "say what you saw SLOW"}])
        folder = self.folder / "tasks" / task["id"]
        before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
        wakes = dict(self.hub.wakes)
        with mock.patch.object(self.hub.runs, "start", side_effect=AssertionError("no run")):
            first, second = self.task(task["id"])[1]["recovery"], self.task(task["id"])[1]["recovery"]
        self.assertEqual(first, second)
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}, before)
        self.assertEqual(self.hub.wakes, wakes)

    def test_stuck_step_session_takes_no_continue(self):
        """A Continue in a stuck step's session would run a turn the task never sees; Retry is the way back."""
        task = self.cut_task([{"kind": "scout", "goal": "look around SLOW"}])
        sid = task["steps"][0]["session"]
        self.assertIn("Retry", self.call(f"/api/levers?session={sid}")[1]["continue"])
        self.assertEqual(self.task(task["id"])[1]["step_levers"]["continue"],
                         "the step is stuck: Retry on a model in the task menu")
        with mock.patch.object(self.hub.runs, "start", side_effect=AssertionError("no run")):
            self.assertEqual(self.call("/api/continue", {"session": sid, "text": "go on"})[0], 409)

    def test_saved_guidance_timing_names_the_way_it_is_delivered(self):
        task = self.cut_task([{"kind": "scout", "goal": "look around SLOW"}])
        self.assertEqual(self.task(task["id"])[1]["message"]["timing"],
                         "Sending saves this guidance; nothing runs. Retry asks whether to carry it into the next run.")
        tid = self.make_task(steps=[{"kind": "scout", "goal": "look around SLOW"}])
        self.until(tid, lambda t: t["steps"][0]["session"] and t["steps"][0]["state"] == "running", "it runs")
        self.assertEqual(self.call("/api/task/pause", {"task": tid})[0], 200)
        self.assertEqual(self.task(tid)[1]["message"]["timing"],
                         "Sending saves this guidance; it is delivered after you Resume.")

    def test_restart_and_polling_replay_nothing(self):
        task = self.cut_task([LOOK, {"kind": "explain", "goal": "say what you saw SLOW"}])
        tid = task["id"]
        task["supervisor"] = supervisor.initial(self.hub.cfg, str(self.project), 100.0)
        task.setdefault("messages", []).append(
            {"id": "m1", "task": tid, "text": "carry on", "target": tasks.message_target(task), "files": [],
             "hash": "h", "mode": "queued", "status": "dispatching", "created": 100.0, "confirm": False, "error": ""})
        tasks.save(self.folder, task)
        supervisor.append_log(self.folder, tid, {"ts": 100.0, "wake": 1, "phase": "claimed", "events": ["e1"]})
        supervisor.append_log(self.folder, tid, {"ts": 101.0, "wake": 1, "phase": "dispatching",
                                                 "dispatch": {"call": "task_lever", "request_id": "r"}})
        for _ in range(2):
            again = self.restart()
            with mock.patch.object(again.runs, "start", side_effect=AssertionError("no run")), \
                    mock.patch.object(again, "task_lever", side_effect=AssertionError("no lever")), \
                    mock.patch.object(again, "request_next", side_effect=AssertionError("no step")), \
                    mock.patch("console.compact._ask", side_effect=AssertionError("no pass")):
                again.runs.reconcile()
                again.reconcile_next_steps()
                for _ in range(3):
                    again.poll_once()
                    again.advance()
                    again.recovery(again.tasks[tid])
            t = again.tasks[tid]
            self.assertEqual(len(t["steps"]), 2)
            self.assertEqual([(m["id"], m["status"]) for m in t["messages"]], [("m1", "uncertain")])
            self.assertEqual(t["supervisor"]["pending"]["status"], "uncertain")
            self.assertEqual(again.recovery(t)["cut"]["step"], 2)
        self.assertEqual(sum(1 for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "recovered"), 1)
        self.assertEqual(json.loads((self.folder / "tasks" / tid / "task.json").read_text(encoding="utf-8"))
                         ["steps"][1]["attempts"][-1]["cause"], "interrupted")


for _name in dir(_TaskServerTest):
    if _name.startswith("test_") and _name not in TaskRecoveryTest.__dict__:
        setattr(TaskRecoveryTest, _name, None)

del _TaskServerTest
