"""Plan 44 backend: the supervisor's Hub and HTTP behavior (fake runners, temporary roots)."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from console import paths, server, supervisor, tasks, usage


class SupervisorServerTest(unittest.TestCase):
    """Hub-level supervisor tests: no hub loop runs, advance/reconcile are called by hand."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        data = Path(self.tmp.name) / "data"
        data.mkdir()
        self.env = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": str(data)})
        self.env.start()
        self.addCleanup(self.env.stop)
        cfg = dict(paths.load_config(), projects=[str(self.project)], supervisor_mode="suggest")
        fake = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
        self.hub = server.Hub(cfg, self.folder, exe=fake)
        self.hub.user_home = Path(self.tmp.name)

    def tearDown(self):
        for proc in list(self.hub.runs.live.values()):
            proc.kill()
        end = time.time() + 10
        while self.hub.runs.live and time.time() < end:
            time.sleep(0.05)
        self.tmp.cleanup()

    def supervised_task(self, tid="20260101-000000-abcd"):
        task = tasks.new_task(str(self.project), "proj", "Sup", "goal", tasks.plan_steps(
            [{"kind": "scout", "goal": "look"}], 6), "normal", {}, "", "auto", 100.0, id_=tid)
        task["supervisor"] = supervisor.initial(self.hub.cfg, str(self.project), 100.0)
        task["progression"] = "manual"
        task["steps"][0].update(state="done", session="s1", ended=100.0)
        task.update(state="waiting", owner="fred", why="choose next step", current=1, last_good=1)
        tasks.save(self.folder, task)
        tasks.log(self.folder, tid, [tasks._line(100.0, task["steps"][0], "running", "done", "choose next step")])
        self.hub.tasks[tid] = task
        return tid

    def test_recovery_rebuilds_saved_result_after_task_save_failure(self):
        tid = self.supervised_task()
        supervisor.append_log(self.folder, tid, {"ts": 100.0, "wake": 1, "phase": "claimed", "events": ["e1"]})
        supervisor.append_log(self.folder, tid, {"ts": 101.0, "wake": 1, "phase": "result", "cost": 0.04,
                                                 "decision": {"decision": "wait", "reason": "r", "confidence": "low",
                                                              "for_fred": ""}, "status": "suggest", "by": "auto"})
        stale = json.loads((self.folder / "tasks" / tid / "task.json").read_text(encoding="utf-8"))
        self.assertEqual((stale["supervisor"]["usd"], stale["supervisor"]["wakes"]), (0.0, 0))
        with mock.patch.object(server.Hub, "task_lever", side_effect=AssertionError("no lever")),                 mock.patch("console.compact._ask", side_effect=AssertionError("no model")):
            hub = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)  # __init__ reconciles once
        hub.user_home = self.hub.user_home
        task = hub.tasks[tid]
        self.assertAlmostEqual(task["supervisor"]["usd"], 0.04)
        self.assertEqual(task["supervisor"]["wakes"], 2)
        self.assertEqual(task["supervisor"]["pending"]["wake"], 1)
        self.assertEqual(task["supervisor"]["pending"]["decision"]["decision"], "wait")
        saved = json.loads((self.folder / "tasks" / tid / "task.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(saved["supervisor"]["usd"], 0.04)  # the projection was saved
        self.assertEqual(hub.reconcile_supervisor(), [])  # reconcile twice is idempotent

    def test_dispatching_lever_becomes_uncertain_never_replayed(self):
        tid = self.supervised_task()
        supervisor.append_log(self.folder, tid, {"ts": 100.0, "wake": 1, "phase": "claimed", "events": ["e1"]})
        supervisor.append_log(self.folder, tid, {"ts": 101.0, "wake": 1, "phase": "dispatching",
                                                 "dispatch": {"call": "task_lever", "request_id": "r"}})
        hub = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        hub.user_home = self.hub.user_home
        with mock.patch.object(hub, "task_lever", side_effect=AssertionError("no replay")) as lever:
            hub.reconcile_supervisor()
            hub.advance()
        self.assertEqual(lever.call_count, 0)
        task = hub.tasks[tid]
        self.assertEqual(task["supervisor"]["pending"]["status"], "uncertain")
        records = supervisor.read_log(self.folder, tid)
        self.assertEqual(records[-1]["phase"], "recovered")
        hub.reconcile_supervisor()  # idempotent: no second recovered record
        self.assertEqual(len(supervisor.read_log(self.folder, tid)), len(records))
        task["supervisor"]["pending"] = None  # a lost projection is rebuilt as uncertain from the recovered record
        tasks.save(self.folder, task)
        again = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        self.assertEqual(again.tasks[tid]["supervisor"]["pending"]["status"], "uncertain")
        self.assertEqual(len(supervisor.read_log(self.folder, tid)), len(records))

    def test_interrupted_claim_is_no_decision_with_unknown_cost(self):
        tid = self.supervised_task()
        pid = supervisor.request_id(tid, 1)
        usage.reserve_supervisor(self.folder, pid, {"task": tid, "wake": 1, "day": "2026-10-18"}, 0.5, 2.0)
        supervisor.append_log(self.folder, tid, {"ts": 100.0, "wake": 1, "phase": "claimed", "events": ["e1"],
                                                 "day": "2026-10-18", "reserved": 0.5})
        with mock.patch("console.compact._ask", side_effect=AssertionError("no model retry")):
            hub = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
            hub.reconcile_supervisor()
        records = supervisor.read_log(self.folder, tid)
        self.assertEqual([r["phase"] for r in records], ["claimed", "recovered"])
        self.assertEqual(records[-1]["outcome"], "no-decision")
        self.assertEqual(usage.load_supervisor(self.folder)["records"][pid]["status"], "unknown")
        self.assertIn("e1", supervisor.fold_log(records)["wakes"][1]["events"])  # consumed, never a retry
        self.assertEqual(hub.tasks[tid]["supervisor"]["wakes"], 2)

    def test_reserved_next_step_recovery_does_not_append_or_launch(self):
        def reserved(session):
            task = tasks.new_task(str(self.project), "proj", "Manual", "goal", tasks.plan_steps(
                [{"kind": "scout", "goal": "look"}], 6), "normal", {}, "", "auto", 100.0)
            task["supervisor"] = supervisor.initial(self.hub.cfg, str(self.project), 100.0)
            task.update(state="waiting", owner="fred", why="starting step 01", current=1, progression="manual")
            task["steps"][0].update(state="planned", request_status="starting", request_id="req-1", source_step=0,
                                    session=session)
            tasks.save(self.folder, task)
            self.hub.tasks[task["id"]] = task
            supervisor.append_log(self.folder, task["id"], {"ts": 100.0, "wake": 1, "phase": "dispatching",
                                                            "dispatch": {"call": "request_next", "request_id": "req-1",
                                                                         "step": 1}})
            return task["id"]
        missing, recorded = reserved(""), reserved("s9")
        with mock.patch.object(self.hub.runs, "start", side_effect=AssertionError("no launch")) as start,                 mock.patch.object(self.hub, "request_next", side_effect=AssertionError("no append")):
            for _ in range(2):  # twice: idempotent
                self.hub.reconcile_supervisor()
                self.hub.reconcile_next_steps()
        self.assertEqual(start.call_count, 0)
        for tid in (missing, recorded):
            self.assertEqual(len(self.hub.tasks[tid]["steps"]), 1)
            self.assertEqual(self.hub.tasks[tid]["supervisor"]["pending"]["status"], "uncertain")
        self.assertEqual(self.hub.tasks[missing]["state"], "stuck")  # plan 36: Retry explicitly
        self.assertEqual(self.hub.tasks[missing]["steps"][0]["request_status"], "failed")
        self.assertEqual(self.hub.tasks[recorded]["steps"][0]["request_status"], "running")

    def test_clear_keeps_supervisor_audit(self):
        tid = self.supervised_task()
        supervisor.append_log(self.folder, tid, {"ts": 100.0, "wake": 1, "phase": "result", "cost": 0.01})
        root = self.folder / "tasks" / tid
        before = {name: (root / name).read_bytes() for name in ("task.json", "chain.jsonl", "supervisor.jsonl")}
        tasks.clear(self.folder, self.hub.tasks[tid], keep_last=True)
        for name, data in before.items():
            self.assertEqual((root / name).read_bytes(), data, name)


if __name__ == "__main__":
    unittest.main()
