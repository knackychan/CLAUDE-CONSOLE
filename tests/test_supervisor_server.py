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
        s1 = task["steps"][0]
        tasks.log(self.folder, tid, [tasks._line(100.0, s1, "running", "done", ""),
                                     tasks._line(100.0, s1, "task:running", "task:waiting", "choose next step")])
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
        self.assertEqual(task["supervisor"]["wakes"], 1)  # the last wake number
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
        self.assertEqual(hub.tasks[tid]["supervisor"]["wakes"], 1)

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



WAIT = {"decision": "wait", "reason": "nothing yet", "confidence": "low", "for_fred": ""}


class WakeTest(SupervisorServerTest):
    """Plan 44 T5: transition wakes, debounce, coalescing and bounded workers (fake clock, controlled runner)."""

    def setUp(self):
        super().setUp()
        self.now = 0.0
        self.hub.sup_clock = lambda: self.now
        self.calls, self.gate = [], threading.Event()
        self.gate.set()
        self.active, self.most = 0, 0
        self.answer = dict(decision=dict(WAIT), cost=0.001, model="haiku", turns=2, error="")
        lock = threading.Lock()

        def fake_run(cfg, exe, task, prompt, model, max_cost):
            with lock:
                self.calls.append({"task": task["id"], "prompt": prompt, "model": model, "max_cost": max_cost})
                self.active += 1
                self.most = max(self.most, self.active)
            self.gate.wait(10)
            with lock:
                self.active -= 1
            answer = self.answer(task) if callable(self.answer) else self.answer
            return dict(answer)
        patch = mock.patch.object(supervisor, "run", side_effect=fake_run)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.drain)

    def drain(self):
        self.gate.set()
        for t in list(self.hub.sup_threads):
            t.join(10)

    def tick(self, at):
        self.now = at
        started = self.hub._supervisor_tick()
        return started

    def line(self, tid, why="choose next step", ts=100.0):
        task = self.hub.tasks[tid]
        return tasks._line(ts, task["steps"][0], "task:running", "task:waiting", why)

    def claims(self, tid):
        return [r for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "claimed"]

    def test_wakes_coalesce_and_rearm_once(self):
        tid = self.supervised_task()
        a, b = self.line(tid), self.line(tid, "other", 101.0)
        self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", a, now=0.0)
        self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", b, now=10.0)
        self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", a, now=29.0)  # duplicate: no re-arm
        self.assertEqual(self.hub.wakes[tid]["due"], 30.0)
        self.assertEqual(self.tick(29.0), [])
        self.assertEqual(self.tick(30.0), [tid])
        self.drain()
        self.assertEqual(len(self.calls), 1)
        claim = self.claims(tid)
        self.assertEqual(len(claim), 1)
        self.assertEqual(claim[0]["events"], [supervisor.event_id(a), supervisor.event_id(b)])
        self.assertEqual(claim[0]["prompt_hash"], supervisor.prompt_hash(self.calls[0]["prompt"]))
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["wakes"], 1)
        self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", a, now=40.0)  # consumed: nothing queued
        self.assertNotIn(tid, self.hub.wakes)
        for at in range(40, 200, 7):
            self.tick(float(at))
        self.drain()
        self.assertEqual(len(self.calls), 1)

    def test_events_during_active_pass_make_one_follow_up(self):
        tid = self.supervised_task()
        self.gate.clear()
        self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", self.line(tid), now=0.0)
        self.assertEqual(self.tick(20.0), [tid])
        for i in range(5):
            self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", self.line(tid, f"e{i}", 200.0 + i), now=21.0)
            self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", self.line(tid, "e0", 200.0), now=22.0)
        for at in (45.0, 60.0, 90.0):
            self.assertEqual(self.tick(at), [])  # one pass per task at a time
        self.now = 100.0
        self.gate.set()
        self.drain()
        self.assertEqual(self.hub.wakes[tid]["due"], 120.0)  # one debounced follow-up after completion
        self.assertEqual(self.tick(119.0), [])
        self.assertEqual(self.tick(120.0), [tid])
        self.drain()
        self.assertEqual((len(self.calls), self.most), (2, 1))
        for at in range(121, 300, 9):
            self.tick(float(at))
        self.drain()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["wakes"], 2)

    def test_parallel_limit_applies_across_tasks(self):
        for parallel in (1, 2):
            with self.subTest(parallel=parallel):
                self.calls.clear()
                self.most = 0
                self.hub.cfg["supervisor_parallel"] = parallel
                ids = [self.supervised_task(f"2026010{parallel}-00000{i}-abcd") for i in range(3)]
                self.gate.clear()
                for i, tid in enumerate(ids):
                    self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", self.line(tid), now=float(i))
                started = self.tick(50.0)
                self.assertEqual(started, ids[:parallel])  # oldest due first
                self.assertEqual(self.tick(51.0), [])
                self.gate.set()
                self.drain()
                self.gate.clear()
                self.assertEqual(self.tick(52.0), ids[parallel:parallel * 2][:parallel] or ids[parallel:])
                self.gate.set()
                self.drain()
                self.tick(53.0)
                self.drain()
                self.assertEqual(sorted(c["task"] for c in self.calls), sorted(ids))
                self.assertLessEqual(self.most, parallel)
                for tid in ids:
                    self.hub.tasks.pop(tid)
        # a deleted task releases its slot and is not recreated
        self.hub.cfg["supervisor_parallel"] = 1
        tid = self.supervised_task("20260109-000000-abcd")
        self.gate.clear()
        self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", self.line(tid), now=0.0)
        self.tick(100.0)
        with self.hub.tlock:
            self.hub._drop(self.hub.tasks[tid])
        self.gate.set()
        self.drain()
        self.assertEqual(self.hub.supervising, {})
        self.assertFalse((self.folder / "tasks" / tid).exists())

    def test_no_wake_for_bookkeeping_chat_external_or_first_retry(self):
        chat = self.supervised_task("20260101-000001-abcd")
        self.hub.tasks[chat]["chat"] = True
        running = self.supervised_task("20260101-000002-abcd")
        self.hub.tasks[running].update(state="running", owner="service", why="")
        retry = self.supervised_task("20260101-000003-abcd")
        self.hub.tasks[retry].update(state="running", owner="service", why="the run did not finish cleanly")
        self.hub.tasks[retry]["steps"][0].update(state="planned", retries=1)
        paused = self.supervised_task("20260101-000004-abcd")
        self.hub.tasks[paused]["supervisor"]["paused"] = True
        off = self.supervised_task("20260101-000005-abcd")
        self.hub.tasks[off]["supervisor"]["mode"] = "off"
        for tid in (chat, running, retry, paused, off):
            self.hub._sup_hook(self.hub.tasks[tid])
        for at in range(0, 2000, 20):
            self.tick(float(at))
        self.drain()
        self.assertEqual(self.calls, [])
        # one real boundary: one call, however often advance runs; a repeated _broken is not a new event
        tid = self.supervised_task()
        task = self.hub.tasks[tid]
        task.update(state="running", owner="service")
        self.hub._broken(task, OSError("disk"))
        self.hub._broken(task, OSError("disk again"))
        self.assertEqual(len(self.hub.wakes[tid]["events"]), 1)
        for at in range(2000, 4000, 20):
            self.tick(float(at))
        self.drain()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]["model"], "sonnet")  # a stuck wake runs on the stuck model

    def test_pending_guidance_and_brief_defer_without_losing_event(self):
        tid = self.supervised_task()
        task = self.hub.tasks[tid]
        for blocker in ("queued", "failed", "uncertain", "brief", "briefing-set"):
            with self.subTest(blocker):
                task.pop("messages", None)
                task.pop("briefing", None)
                self.hub.briefing.discard(tid)
                if blocker == "brief":
                    task["briefing"] = 1
                elif blocker == "briefing-set":
                    self.hub.briefing.add(tid)
                else:
                    task["messages"] = [{"id": "m1", "status": blocker}]
                self.hub._sup_hook(task)
                for at in range(0, 500, 25):
                    self.tick(float(at))
                self.assertEqual(self.calls, [])
                self.assertIn(tid, self.hub.wakes)  # retained, not spent and not lost
        task.pop("messages", None)
        task.pop("briefing", None)
        self.hub.briefing.discard(tid)
        self.tick(600.0)
        self.drain()
        self.assertEqual(len(self.calls), 1)

    def restarted(self):
        hub = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        hub.user_home = self.hub.user_home
        hub.sup_clock = lambda: self.now
        self.addCleanup(lambda: [t.join(10) for t in hub.sup_threads])
        return hub

    def test_restart_queues_unhandled_boundary_once(self):
        fresh = self.supervised_task("20260101-000001-abcd")
        done = {}
        for name in ("result", "rejected", "failed", "claimed"):
            tid = self.supervised_task(f"20260101-00001{len(done)}-abcd")
            event = supervisor.boundary(self.hub.tasks[tid], tasks.read_chain(self.folder, self.hub.tasks[tid]))["event"]
            supervisor.append_log(self.folder, tid, {"ts": 1.0, "wake": 1, "phase": "claimed", "events": [event]})
            if name != "claimed":
                supervisor.append_log(self.folder, tid, {"ts": 2.0, "wake": 1, "phase": "result", "events": [event],
                                                         "status": {"result": "wait", "rejected": "rejected",
                                                                    "failed": "no-decision"}[name]})
            done[name] = tid
        hub = self.restarted()
        self.now = 0.0
        hub._supervisor_tick()
        self.assertEqual(sorted(hub.wakes), [fresh])
        self.assertEqual(hub.wakes[fresh]["due"], 20.0)  # a fresh debounce, never a synthetic timestamp
        for at in range(0, 400, 10):
            self.now = float(at)
            hub._supervisor_tick()
        for t in hub.sup_threads:
            t.join(10)
        self.assertEqual([c["task"] for c in self.calls], [fresh])

    def test_restart_before_claim_recovers_manual_and_stuck(self):
        manual = self.supervised_task("20260101-000001-abcd")
        stuck = self.supervised_task("20260101-000002-abcd")
        t = self.hub.tasks[stuck]
        t.update(state="stuck", owner="fred", why="replan failed: no JSON")
        tasks.log(self.folder, stuck, [tasks._line(150.0, t["steps"][0], "task:running", "task:stuck", t["why"])])
        tasks.save(self.folder, t)
        old = self.supervised_task("20260101-000003-abcd")  # a superseded historical boundary: now running
        self.hub.tasks[old].update(state="running", owner="service", why="")
        tasks.save(self.folder, self.hub.tasks[old])
        live = {tid: supervisor.boundary(self.hub.tasks[tid], tasks.read_chain(self.folder, self.hub.tasks[tid]))
                for tid in (manual, stuck)}
        for tid in (manual, stuck):  # queued inside the debounce, then the service restarts
            self.hub.wake_supervisor(self.hub.tasks[tid], live[tid]["trigger"], live[tid]["line"], now=0.0)
        hub = self.restarted()
        hub.tasks[manual]["messages"] = [{"id": "m", "status": "queued"}]  # a blocker defers, never loses
        for at in range(0, 200, 5):
            self.now = float(at)
            hub._supervisor_tick()
            hub._supervisor_tick()  # duplicate advances
        for th in hub.sup_threads:
            th.join(10)
        self.assertEqual([c["task"] for c in self.calls], [stuck])
        self.assertEqual(self.calls[0]["model"], "sonnet")
        hub.tasks[manual].pop("messages")
        self.now = 300.0
        hub._supervisor_tick()
        for th in hub.sup_threads:
            th.join(10)
        self.assertEqual(sorted(c["task"] for c in self.calls), sorted([manual, stuck]))
        for tid in (manual, stuck):
            claim = [r for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "claimed"]
            self.assertEqual(claim[0]["events"], [live[tid]["event"]])  # the original event id
        self.assertNotIn(old, [c["task"] for c in self.calls])

    def test_model_failure_does_not_loop_and_next_transition_can_wake(self):
        tid = self.supervised_task()
        self.answer = dict(decision=None, cost=0.002, model="haiku", turns=1, error="the pass returned no JSON")
        self.hub._sup_hook(self.hub.tasks[tid])
        for at in range(0, 500, 10):
            self.tick(float(at))
        self.drain()
        self.assertEqual(len(self.calls), 1)
        task = self.hub.tasks[tid]
        self.assertIsNone(task["supervisor"]["pending"])
        self.assertAlmostEqual(task["supervisor"]["usd"], 0.002)
        result = [r for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "result"][-1]
        self.assertEqual((result["status"], result["cost"]), ("no-decision", 0.002))
        self.assertIn("no decision", tasks.read_chain(self.folder, task)[-1]["why"])
        self.assertEqual(self.hub.supervising, {})
        self.assertEqual(usage.load_supervisor(self.folder)["records"][supervisor.request_id(tid, 1)]["cost"], 0.002)
        # a distinct later real transition may wake again
        self.answer = dict(decision=dict(WAIT), cost=0.001, model="haiku", turns=1, error="")
        tasks.log(self.folder, tid, [tasks._line(600.0, task["steps"][0], "task:waiting", "task:waiting", "x"),
                                     tasks._line(601.0, task["steps"][0], "task:stuck", "task:waiting",
                                                 "choose next step")])
        self.hub._sup_hook(task)
        self.tick(700.0)
        self.drain()
        self.assertEqual(len(self.calls), 2)

    def test_missing_exe_is_terminal_not_a_loop(self):
        tid = self.supervised_task()
        self.hub.runs.exe = []
        self.hub._sup_hook(self.hub.tasks[tid])
        for at in range(0, 500, 10):
            self.tick(float(at))
        self.assertEqual(self.calls, [])
        self.assertNotIn(tid, self.hub.wakes)
        results = [r for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "result"]
        self.assertEqual(len(results), 1)
        self.assertIn("claude.exe", results[0]["error"])


if __name__ == "__main__":
    unittest.main()
