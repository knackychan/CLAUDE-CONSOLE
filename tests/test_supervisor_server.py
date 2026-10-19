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
from tests import test_server


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
        task["steps"][0].update(state="done", session="s1", ended=100.0, dir="01-scout", model="haiku", effort="low", attempts=[
            {"session": "s1", "cost": 0.1, "started": 90.0, "ended": 100.0, "why": "", "final": True}])
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



ADD = {"decision": "add_next_step", "kind": "verify", "instructions": "Check step 01 against the goal",
       "model": "auto", "reason": "a scout finished", "confidence": "high", "for_fred": ""}


class DispatchTest(WakeTest):
    """Plan 44 T6: approved decisions go through the existing Hub operations, gated and at most once."""

    def pending(self, tid, decision, triggers=("choose_next",), status="suggest", wake=1):
        task = self.hub.tasks[tid]
        task["supervisor"]["wakes"] = max(task["supervisor"]["wakes"], wake)
        task["supervisor"]["pending"] = {"wake": wake, "events": [f"e{wake}"], "triggers": list(triggers),
                                         "decision": dict(decision), "revision": supervisor.revision(self.folder, task),
                                         "epoch": task["supervisor"]["epoch"], "status": status, "error": "",
                                         "by": "", "dispatch": None}
        supervisor.append_log(self.folder, tid, {"ts": 1.0, "wake": wake, "phase": "claimed", "events": [f"e{wake}"]})
        tasks.save(self.folder, task)

    def stuck_task(self, tid="20260101-000000-dddd"):
        tid = self.supervised_task(tid)
        task = self.hub.tasks[tid]
        task["steps"][0].update(state="failed", avoid=["codex"])
        task["steps"][0]["attempts"][-1]["why"] = "it hit the turn cap (30 turns)"
        task.update(state="stuck", owner="fred", why="it hit the turn cap (30 turns) (after one retry)")
        tasks.save(self.folder, task)
        tasks.log(self.folder, tid, [tasks._line(110.0, task["steps"][0], "task:running", "task:stuck", task["why"])])
        return tid

    def test_dispatch_uses_existing_preview_revision_and_uuid(self):
        tid = self.supervised_task()
        tasks.write_note(self.folder, self.hub.tasks[tid], self.hub.tasks[tid]["steps"][0],
                         "## Goal\ngoal\n## Findings\n- f\n## Files touched\n- (none)\n## Troubleshooting\n- (none)\n"
                         "## Open questions\n- (none)\n## Next\n- verify")
        self.answer = dict(decision=dict(ADD), cost=0.001, model="haiku", turns=2, error="")
        self.hub._sup_hook(self.hub.tasks[tid])
        self.tick(30.0)
        self.drain()
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["pending"]["status"], "suggest")
        previews, requests = [], []
        real_preview, real_request = self.hub.preview_next, self.hub.request_next

        def preview(req):
            got = real_preview(req)
            previews.append((req, got))
            return got

        def request(req, **kw):
            requests.append((req, kw))
            return real_request(req, **kw)
        with mock.patch.object(self.hub, "preview_next", side_effect=preview), \
                mock.patch.object(self.hub, "request_next", side_effect=request):
            code, body = self.hub._supervisor_dispatch(tid, 1, "fred")
            self.assertEqual(code, 200, body)
            again = self.hub._supervisor_dispatch(tid, 1, "fred")
        self.assertEqual(len(requests), 1)
        req, kw = requests[0]
        self.assertEqual(kw, {"origin": "supervisor"})
        self.assertEqual(req["request_id"], supervisor.request_id(tid, 1))
        self.assertEqual(req["revision"], previews[0][1][1]["revision"])
        self.assertEqual((req["model"], req["kind"], req["source_session"]), ("auto", "verify", "s1"))
        self.assertEqual(again[1]["step"], body["step"])
        task = self.hub.tasks[tid]
        self.assertEqual(len(task["steps"]), 2)
        self.assertTrue((self.folder / "tasks" / tid / tasks.step_file(task["steps"][1], "received-handoff.md")).exists())
        self.assertIsNone(task["supervisor"]["pending"])
        phases = [r["phase"] for r in supervisor.read_log(self.folder, tid)]
        self.assertEqual(phases[-2:], ["dispatching", "outcome"])

    def test_live_gates_win_after_valid_model_result(self):
        changes = {
            "project": lambda t: self.hub.cfg.update(projects=[]),
            "exe": lambda t: setattr(self.hub.runs, "exe", []),
            "later": lambda t: t["steps"].append(tasks._blank(2, "code", "x")),
            "source": lambda t: t["steps"][0].update(session="s9"),
            "fable": lambda t: t.update(why="confirm Fable"),
        }
        for name, change in changes.items():
            with self.subTest(name):
                self.hub.cfg["projects"] = [str(self.project)]
                self.hub.runs.exe = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
                tid = self.supervised_task()
                self.pending(tid, ADD)
                change(self.hub.tasks[tid])
                with mock.patch.object(self.hub, "request_next") as request, \
                        mock.patch.object(self.hub, "task_lever") as lever:
                    code, _ = self.hub._supervisor_dispatch(tid, 1, "fred")
                self.assertEqual(code, 409, name)
                self.assertEqual((request.call_count, lever.call_count), (0, 0))
        tid = self.supervised_task()
        self.hub.tasks[tid].update(why="step 02 opus over its pace")
        self.pending(tid, dict(decision="confirm", reason="r", confidence="high", for_fred=""))
        with mock.patch.object(self.hub, "task_lever") as lever:
            self.assertEqual(self.hub._supervisor_dispatch(tid, 1, "fred")[0], 409)
        self.assertEqual(lever.call_count, 0)

    def test_guidance_during_pass_holds_all_dispatches(self):
        decisions = [dict(decision="retry", note="n", reason="r", confidence="high", for_fred=""),
                     dict(decision="stop", reason="r", confidence="high", for_fred=""),
                     dict(decision="confirm", reason="r", confidence="high", for_fred=""), dict(ADD)]
        for d in decisions:
            with self.subTest(d["decision"]):
                tid = self.supervised_task()
                self.pending(tid, d, triggers=("stalled",))
                self.hub.tasks[tid]["messages"] = [{"id": "m", "status": "queued"}]
                with mock.patch.object(self.hub, "request_next") as request, \
                        mock.patch.object(self.hub, "task_lever") as lever:
                    code, body = self.hub._supervisor_dispatch(tid, 1, "fred")
                self.assertEqual((code, body["error"]), (409, "held: pending guidance"))
                self.assertEqual((request.call_count, lever.call_count), (0, 0))
                self.assertEqual(self.hub.tasks[tid]["supervisor"]["pending"]["status"], "held")
        # guidance that arrives during the pass holds its result
        tid = self.supervised_task("20260101-000000-eeee")
        self.answer = dict(decision=dict(ADD), cost=0.001, model="haiku", turns=2, error="")
        self.gate.clear()
        self.hub._sup_hook(self.hub.tasks[tid])
        self.tick(30.0)
        self.hub.tasks[tid]["messages"] = [{"id": "m", "status": "queued"}]
        self.gate.set()
        self.drain()
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["pending"]["status"], "held")

    def test_held_guidance_drain_revalidates_or_requeues_once(self):
        self.hub.sup_recovered = True  # only the drain is under test here
        tid = self.supervised_task()
        self.pending(tid, ADD, status="held")
        self.tick(1.0)
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["pending"]["status"], "suggest")
        other = self.supervised_task("20260101-000000-ffff")
        self.pending(other, ADD, status="held")
        tasks.write_step_file(self.folder, self.hub.tasks[other], self.hub.tasks[other]["steps"][0], "facts.md", "new")
        self.tick(2.0)
        self.assertIsNone(self.hub.tasks[other]["supervisor"]["pending"])
        self.assertEqual(self.hub.wakes[other]["triggers"], ["choose_next"])
        self.assertEqual(self.hub.wakes[other]["due"], 22.0)
        self.tick(3.0)
        self.assertEqual(self.hub.wakes[other]["due"], 22.0)  # one fresh wake, not one per advance
        self.tick(22.0)
        self.drain()
        self.assertEqual([c["task"] for c in self.calls], [other])

    def test_held_add_step_is_not_appended_or_confirmed_again(self):
        tid = self.supervised_task()
        self.pending(tid, ADD)
        with mock.patch.object(self.hub, "preview_next", return_value=(200, {"revision": "r1"})), \
                mock.patch.object(self.hub, "request_next", return_value=(
                    200, {"task": tid, "step": 2, "request_id": "x", "status": "held"})) as request, \
                mock.patch.object(self.hub, "task_lever") as lever:
            self.assertEqual(self.hub._supervisor_dispatch(tid, 1, "fred")[1]["status"], "held")
            for _ in range(3):
                self.hub._supervisor_dispatch(tid, 1, "fred")
                self.tick(100.0)
            self.hub.reconcile_supervisor()
        self.assertEqual((request.call_count, lever.call_count), (1, 0))
        self.assertIn("held for Fred", tasks.read_chain(self.folder, self.hub.tasks[tid])[-1]["why"])

    def test_duplicate_lever_dispatch_and_outcome_failure_do_not_repeat(self):
        tid = self.stuck_task()
        retry = dict(decision="retry", note="name the failing line", reason="r", confidence="high", for_fred="")
        self.pending(tid, retry, triggers=("stuck",))
        with mock.patch.object(self.hub, "task_lever", return_value=(200, {"task": tid, "state": "running"})) as lever:
            threads = [threading.Thread(target=self.hub._supervisor_dispatch, args=(tid, 1, "fred")) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        self.assertEqual(lever.call_count, 1)
        # an outcome that cannot be saved never invokes the operation twice
        tid = self.stuck_task("20260101-000000-1111")
        self.pending(tid, retry, triggers=("stuck",))
        real = self.hub._sup_record

        def no_outcome(task_id, record):
            if record.get("phase") == "outcome":
                raise OSError("disk full")
            return real(task_id, record)
        with mock.patch.object(self.hub, "_sup_record", side_effect=no_outcome), \
                mock.patch.object(self.hub, "task_lever", return_value=(200, {"task": tid})) as lever:
            self.hub._supervisor_dispatch(tid, 1, "fred")
            self.hub._supervisor_dispatch(tid, 1, "fred")
        self.assertEqual(lever.call_count, 1)
        again = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)  # restart: dispatching is uncertain
        self.assertEqual(again.tasks[tid]["supervisor"]["pending"]["status"], "uncertain")
        with mock.patch.object(again, "task_lever") as lever:
            self.assertEqual(again._supervisor_dispatch(tid, 1, "fred")[0], 409)
        self.assertEqual(lever.call_count, 0)
        # a lever that raised after its effect may have happened: uncertain, never replayed
        tid = self.stuck_task("20260101-000000-2222")
        self.pending(tid, retry, triggers=("stuck",))
        with mock.patch.object(self.hub, "task_lever", side_effect=RuntimeError("socket")) as lever:
            self.assertEqual(self.hub._supervisor_dispatch(tid, 1, "fred")[0], 500)
            self.assertEqual(self.hub._supervisor_dispatch(tid, 1, "fred")[0], 500)  # its saved outcome
        self.assertEqual(lever.call_count, 1)
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["pending"]["status"], "uncertain")

    def test_intent_write_failure_prevents_effect(self):
        retry = dict(decision="retry", note="n", reason="r", confidence="high", for_fred="")
        for where in ("append", "save"):
            with self.subTest(where):
                tid = self.stuck_task()
                self.pending(tid, retry, triggers=("stuck",))
                target = (mock.patch.object(supervisor, "append_log", side_effect=OSError("disk")) if where == "append"
                          else mock.patch.object(tasks, "save", side_effect=OSError("disk")))
                with target, mock.patch.object(self.hub, "task_lever") as lever:
                    code, _ = self.hub._supervisor_dispatch(tid, 1, "fred")
                self.assertEqual((code, lever.call_count), (500, 0))

    def test_retry_preserves_limits_avoid_and_note(self):
        seen = {}

        def capture(task, n):
            seen[task["id"]] = {"note": task.get("retry_note"), "why": task.get("retry_why"),
                                "avoid": list(tasks.step(task, n).get("avoid") or [])}
        mine, fred = self.stuck_task(), self.stuck_task("20260101-000000-3333")
        self.pending(mine, dict(decision="retry", note="name the failing line", model="sonnet", reason="r",
                                confidence="high", for_fred=""), triggers=("stuck",))
        with mock.patch.object(self.hub, "start_step", side_effect=capture):
            self.assertEqual(self.hub._supervisor_dispatch(mine, 1, "fred")[0], 200)
            self.assertEqual(self.hub.task_lever(fred, "retry", note="name the failing line", model="sonnet")[0], 200)
        self.assertEqual(seen[mine], seen[fred])
        self.assertEqual(seen[mine]["avoid"], ["codex"])
        self.assertEqual(seen[mine]["note"], "name the failing line")

    def test_automatic_dispatch_is_not_active_yet(self):
        self.hub.sup_auto = False  # the Task 6 checkpoint: Task 8 is what turns automatic dispatch on
        tid = self.stuck_task()
        self.hub.tasks[tid]["supervisor"]["mode"] = "auto"
        self.pending(tid, dict(decision="retry", note="n", reason="r", confidence="high", for_fred=""),
                     triggers=("stuck",))
        with mock.patch.object(self.hub, "task_lever") as lever:
            self.assertEqual(self.hub._supervisor_dispatch(tid, 1, "auto")[0], 409)
        self.assertEqual(lever.call_count, 0)



class ApprovalTest(DispatchTest):
    """Plan 44 T7: mode/Approve/Reject API, read projections, human-action bookkeeping and the R2 Pause/Resume fix."""

    def http(self):
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), type("H", (server.Handler,), {"hub": self.hub}))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.port = httpd.server_address[1]

    def post(self, path, body, headers=None):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        sent = {"Host": f"127.0.0.1:{self.port}", "X-CC": "1", "Content-Type": "application/json"}
        sent.update(headers or {})
        conn.request("POST", path, body=json.dumps(body).encode("utf-8"), headers={k: v for k, v in sent.items() if v})
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw or b"null")
        except ValueError:
            return resp.status, raw

    def test_mode_endpoint_validation_guards_and_persistence(self):
        self.http()
        tid = self.supervised_task()
        self.assertEqual(self.post("/api/task/supervisor", {"task": tid, "mode": "off"}, {"X-CC": ""})[0], 403)
        self.assertEqual(self.post("/api/task/supervisor", {"task": tid, "mode": "off"}, {"Host": "evil.com"})[0], 403)
        for bad in ({"task": tid, "mode": "loud"}, {"task": tid}, {"task": tid, "mode": "off", "wake": 1},
                    {"task": tid, "wake": True, "action": "approve"}, {"task": tid, "wake": 0, "action": "approve"},
                    {"task": tid, "wake": 1, "action": "rerun"}, {"task": tid, "wake": 1, "action": "reject", "note": 3},
                    {"task": tid, "wake": 1, "action": "reject", "note": "x" * 2001}, {"task": tid, "mode": "off", "x": 1}):
            self.assertEqual(self.post("/api/task/supervisor", bad)[0], 400, bad)
        self.assertEqual(self.post("/api/task/supervisor", {"task": "20260101-000000-9999", "mode": "off"})[0], 404)
        with mock.patch.object(tasks, "save", side_effect=OSError("disk")):
            self.assertEqual(self.post("/api/task/supervisor", {"task": tid, "mode": "auto"})[0], 500)
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["mode"], "suggest")
        self.assertEqual(self.post("/api/task/supervisor", {"task": tid, "mode": "auto"})[0], 200)
        self.assertEqual(self.calls, [])  # a mode POST never calls the model
        again = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        self.assertEqual(again.tasks[tid]["supervisor"]["mode"], "auto")
        self.assertIn("supervisor mode", tasks.read_chain(self.folder, again.tasks[tid])[-1]["why"])
        # off cancels queued wakes and pending executable intent
        self.pending(tid, ADD)
        self.hub.wakes[tid] = {"due": 5.0, "triggers": ["choose_next"], "events": ["x"], "n": 1}
        self.assertEqual(self.post("/api/task/supervisor", {"task": tid, "mode": "off"})[0], 200)
        self.assertNotIn(tid, self.hub.wakes)
        self.assertIsNone(self.hub.tasks[tid]["supervisor"]["pending"])

    def test_suggest_does_nothing_until_approve_and_duplicate_approve_is_safe(self):
        tid = self.stuck_task()
        self.answer = dict(decision=dict(decision="retry", note="fix the line", reason="r", confidence="high",
                                         for_fred=""), cost=0.001, model="sonnet", turns=2, error="")
        self.hub._sup_hook(self.hub.tasks[tid])
        with mock.patch.object(self.hub, "task_lever", wraps=self.hub.task_lever) as lever, \
                mock.patch.object(self.hub, "start_step") as start:
            for at in range(0, 300, 10):
                self.tick(float(at))
            self.drain()
            self.assertEqual((lever.call_count, start.call_count), (0, 0))
            self.assertEqual(self.hub.tasks[tid]["supervisor"]["pending"]["status"], "suggest")
            body = {"task": tid, "wake": 1, "action": "approve"}
            threads = [threading.Thread(target=self.hub.supervisor_action, args=(dict(body),)) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
            code, again = self.hub.supervisor_action(dict(body))
        self.assertEqual(code, 200)
        self.assertTrue(again.get("repeated"))
        self.assertEqual(lever.call_count, 1)
        self.assertEqual(self.hub.supervisor_action({"task": tid, "wake": 1, "action": "reject"})[0], 409)  # conflict

    def test_stale_reject_uncertain_and_forbidden_approval(self):
        self.hub.sup_recovered = True  # the fixture's boundary is represented by its saved pending card
        tid = self.supervised_task()
        self.pending(tid, ADD, wake=2)
        self.assertEqual(self.hub.supervisor_action({"task": tid, "wake": 1, "action": "approve"})[0], 409)
        code, _ = self.hub.supervisor_action({"task": tid, "wake": 2, "action": "reject", "note": "verify later"})
        self.assertEqual(code, 200)
        sup = self.hub.tasks[tid]["supervisor"]
        self.assertEqual((sup["pending"], sup["reject_note"]), (None, "verify later"))
        self.assertEqual(self.hub.supervisor_action({"task": tid, "wake": 2, "action": "reject"})[0], 200)  # saved
        for at in range(0, 300, 10):
            self.tick(float(at))
        self.drain()
        self.assertEqual(self.calls, [])  # a rejection never calls the model at once
        # the rejection note reaches the next real wake's digest
        tasks.log(self.folder, tid, [tasks._line(500.0, self.hub.tasks[tid]["steps"][0], "task:stuck",
                                                 "task:waiting", "choose next step")])
        self.hub._sup_hook(self.hub.tasks[tid])
        self.tick(600.0)
        self.drain()
        self.assertIn("verify later", self.calls[0]["prompt"])
        # uncertain: dismissal acknowledges without replay
        other = self.stuck_task("20260101-000000-4444")
        self.pending(other, dict(decision="retry", note="n", reason="r", confidence="high", for_fred=""),
                     status="uncertain")
        with mock.patch.object(self.hub, "task_lever") as lever:
            self.assertEqual(self.hub.supervisor_action({"task": other, "wake": 1, "action": "approve"})[0], 409)
            self.assertEqual(self.hub.supervisor_action({"task": other, "wake": 1, "action": "reject"})[0], 200)
        self.assertEqual(lever.call_count, 0)
        # answer / Fable / pace are never approvable
        for why, decision in (("choose next step", dict(decision="answer", text="yes", reason="r",
                                                         confidence="high", for_fred="")),
                              ("confirm Fable", dict(decision="confirm", reason="r", confidence="high", for_fred="")),
                              ("step 02 opus over its pace", dict(decision="confirm", reason="r", confidence="high",
                                                                   for_fred=""))):
            t = self.supervised_task("20260101-000000-5555")
            self.hub.tasks[t]["why"] = why
            self.pending(t, decision)
            with mock.patch.object(self.hub, "task_lever") as lever:
                self.assertEqual(self.hub.supervisor_action({"task": t, "wake": 1, "action": "approve"})[0], 409)
            self.assertEqual(lever.call_count, 0)

    def test_pending_attention_is_projected_without_state_change(self):
        tid = self.supervised_task()
        task = self.hub.tasks[tid]
        task.update(state="done", owner="fred", why="")
        self.pending(tid, dict(decision="escalate_to_fred", reason="r", confidence="low", for_fred="Anything left?"),
                     status="escalate")
        for i in range(12):
            supervisor.append_log(self.folder, tid, {"ts": float(i), "wake": 1, "phase": "result", "status": "wait",
                                                     "error": "token sk-secret12345678"})
        view = self.hub.supervisor_view(task)
        self.assertEqual(view["pending"]["status"], "escalate")
        self.assertFalse(view["pending"]["can_approve"])
        self.assertTrue(view["pending"]["can_reject"])
        self.assertEqual(len(view["audit"]), 10)
        self.assertNotIn("sk-secret12345678", json.dumps(view))
        row = server.task_row(task)
        self.assertEqual((row["group"], row["supervisor"]["attention"]), ("needs", True))
        self.assertEqual((task["state"], task["why"]), ("done", ""))  # nothing pretends to be a transition
        self.http()
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("GET", f"/api/task?id={tid}", headers={"Host": f"127.0.0.1:{self.port}"})
        got = json.loads(conn.getresponse().read())
        conn.close()
        self.assertEqual(got["supervisor"]["pending"]["wake"], 1)

    def test_only_new_successful_fred_actions_reset_epoch(self):
        def epoch(tid):
            return self.hub.tasks[tid]["supervisor"]["epoch"]
        tid = self.supervised_task()
        sup = self.hub.tasks[tid]["supervisor"]
        sup.update(auto_steps=2, retries={1: 1}, usd=0.2, wakes=5, work_usd=1.5)
        self.assertEqual(self.hub.task_lever(tid, "pause")[0], 200)
        self.assertEqual(epoch(tid), 1)
        sup = self.hub.tasks[tid]["supervisor"]
        self.assertEqual((sup["auto_steps"], sup["retries"], sup["work_usd"], sup["usd"], sup["wakes"]),
                         (0, {}, 0.0, 0.2, 5))
        self.assertEqual(self.hub.task_lever(tid, "pause")[0], 409)  # duplicate: refused, no reset
        self.assertEqual(epoch(tid), 1)
        self.assertEqual(self.hub.task_lever(tid, "retry")[0], 409)  # refused
        self.assertEqual(epoch(tid), 1)
        self.assertEqual(self.hub.task_lever(tid, "resume")[0], 200)
        self.assertEqual(epoch(tid), 2)
        self.hub.preview_next({"task": tid, "source_step": 1, "source_session": "s1", "kind": "code",
                               "instructions": "x", "model": "auto"})  # a preview resets nothing
        self.assertEqual(epoch(tid), 2)
        with mock.patch.object(self.hub, "start_step"):
            self.assertEqual(self.hub.task_lever(tid, "done", origin="supervisor")[0], 200)
        self.assertEqual(epoch(tid), 2)  # an internal origin never counts as Fred
        # request_next reservation counts once; its duplicate does not
        other = self.supervised_task("20260101-000000-6666")
        req = {"task": other, "source_step": 1, "source_session": "s1", "kind": "code", "instructions": "x",
               "model": "auto", "request_id": "0d6d1f0e-0000-4000-8000-000000000001"}
        req["revision"] = self.hub.preview_next(req)[1]["revision"]
        with mock.patch.object(self.hub, "start_step"):
            self.assertEqual(self.hub.request_next(dict(req))[0], 200)
            self.assertEqual(epoch(other), 1)
            self.hub.request_next(dict(req))
        self.assertEqual(epoch(other), 1)
        # new tasks carry a policy snapshot
        self.assertIn("supervisor", self.hub.tasks[other])

    def test_pause_holds_supervisor_but_manual_boundary_does_not(self):
        tid = self.supervised_task()
        task = self.hub.tasks[tid]
        self.assertEqual(self.hub.task_levers(tid)["pause"], "")  # a manual boundary is not a Pause
        self.hub._sup_hook(task)
        self.assertEqual(self.hub.task_lever(tid, "pause")[0], 200)
        for at in range(0, 300, 10):
            self.tick(float(at))
        self.assertEqual(self.calls, [])
        again = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        self.assertTrue(again.tasks[tid]["supervisor"]["paused"])
        self.assertEqual(self.hub.task_lever(tid, "resume")[0], 200)
        self.assertEqual(self.calls, [])  # Resume makes no wake and no model call by itself

    def test_manual_boundary_pause_resume_uses_shared_gates(self):
        for i, (why, mode) in enumerate((w, m) for w in ("choose next step", "VERDICT: FAIL: test_x fails")
                                        for m in ("suggest", "auto")):
            if True:
                with self.subTest(why=why, mode=mode):
                    self.calls.clear()
                    tid = self.supervised_task(f"20260101-00000{i}-8888")
                    task = self.hub.tasks[tid]
                    task["why"], task["supervisor"]["mode"] = why, mode
                    tasks.log(self.folder, tid, [tasks._line(101.0, task["steps"][0], "task:running", "task:waiting", why)])
                    self.hub.sup_recovered = True
                    self.hub.wakes.clear()
                    self.now = 0.0
                    self.hub._sup_hook(task)
                    self.assertEqual(self.hub.task_lever(tid, "pause")[0], 200)
                    self.assertEqual(self.hub.task_levers(tid)["pause"], "already paused")
                    self.tick(100.0)
                    self.assertEqual(self.calls, [])
                    with mock.patch.object(self.hub, "start_step") as start:
                        self.assertEqual(self.hub.task_lever(tid, "resume")[0], 200)
                    self.assertEqual(start.call_count, 0)
                    task = self.hub.tasks[tid]
                    self.assertEqual((task["owner"], task["state"], task["why"], task["current"]),
                                     ("fred", "waiting", why, 1))
                    self.assertEqual(self.hub.task_lever(tid, "resume")[0], 409)  # duplicate
                    self.tick(200.0)
                    self.drain()
                    self.assertEqual(len(self.calls), 1)  # the original deferred event, once
                    self.tick(400.0)
                    self.drain()
                    self.assertEqual(len(self.calls), 1)
        # an automatic task's Pause and Resume keep their behavior
        auto = self.supervised_task("20260101-000000-7777")
        self.hub.tasks[auto].update(progression=None, owner="service", state="running", why="")
        self.assertEqual(self.hub.task_lever(auto, "pause")[0], 200)
        self.assertEqual(self.hub.tasks[auto]["owner"], "fred")
        with mock.patch.object(self.hub, "start_step"):
            self.assertEqual(self.hub.task_lever(auto, "resume")[0], 200)
        self.assertEqual(self.hub.tasks[auto]["owner"], "service")

    def test_manual_boundary_pause_resume_during_pass_never_dispatches_old_advice(self):
        tid = self.supervised_task()
        self.answer = dict(decision=dict(ADD), cost=0.003, model="haiku", turns=2, error="")
        self.gate.clear()
        self.hub._sup_hook(self.hub.tasks[tid])
        self.tick(30.0)
        self.assertEqual(self.hub.task_lever(tid, "pause")[0], 200)
        self.assertEqual(self.hub.task_lever(tid, "resume")[0], 200)
        with mock.patch.object(self.hub, "request_next") as request:
            self.gate.set()
            self.drain()
            for at in range(40, 400, 10):
                self.tick(float(at))
            self.drain()
            self.assertEqual(self.hub.supervisor_action({"task": tid, "wake": 1, "action": "approve"})[0], 409)
        self.assertEqual(request.call_count, 0)
        self.assertEqual(len(self.calls), 1)  # no retry of its consumed event
        self.assertAlmostEqual(self.hub.tasks[tid]["supervisor"]["usd"], 0.003)
        self.assertEqual(usage.load_supervisor(self.folder)["records"][supervisor.request_id(tid, 1)]["cost"], 0.003)



class AutonomyTest(DispatchTest):
    """Plan 44 T8: auto mode dispatches only its table, within the step, retry and money limits."""

    def auto(self, tid):
        self.hub.tasks[tid]["supervisor"]["mode"] = "auto"
        tasks.save(self.folder, self.hub.tasks[tid])

    def run_wake(self, tid, decision):
        self.answer = dict(decision=dict(decision), cost=0.001, model="haiku", turns=2, error="")
        self.hub._sup_hook(self.hub.tasks[tid])
        self.tick(self.now + 100.0)
        self.drain()

    def test_only_auto_mode_dispatches_eligible_action(self):
        finish = dict(decision="finish", reason="done", confidence="high", for_fred="")
        for mode, want in (("off", None), ("suggest", "suggest"), ("auto", "done")):
            with self.subTest(mode):
                tid = self.supervised_task(f"20260101-000000-{ {'off': 'a0a0', 'suggest': 'a1a1', 'auto': 'a2a2'}[mode]}")
                self.hub.tasks[tid]["supervisor"]["mode"] = mode
                self.hub.sup_recovered = True
                self.run_wake(tid, finish)
                task = self.hub.tasks[tid]
                if want == "done":
                    self.assertEqual(task["state"], "done")
                    self.assertIsNone(task["supervisor"]["pending"])
                elif want == "suggest":
                    self.assertEqual((task["state"], task["supervisor"]["pending"]["status"]), ("waiting", "suggest"))
                else:
                    self.assertIsNone(task["supervisor"]["pending"])
        for d in (dict(decision="stepdone", reason="r", confidence="high", for_fred=""),
                  dict(decision="stop", reason="r", confidence="high", for_fred="")):
            tid = self.stuck_task("20260101-000000-b0b" + ("1" if d["decision"] == "stop" else "2"))
            self.auto(tid)
            self.pending(tid, d, triggers=("stalled", "stuck"))
            with mock.patch.object(self.hub, "task_lever") as lever:
                self.hub._sup_auto(tid, 1)
            self.assertEqual(lever.call_count, 0, d)
            self.assertTrue(self.hub.tasks[tid]["supervisor"]["pending"]["error"])  # stays a suggestion

    def held_add(self, tid):
        return mock.patch.object(self.hub, "request_next", side_effect=lambda req, **kw: (
            200, {"task": tid, "step": 2, "request_id": req["request_id"], "status": "held"}))

    def test_fourth_auto_step_is_suggestion_and_human_action_resets_window(self):
        tid = self.supervised_task()
        self.auto(tid)
        with mock.patch.object(self.hub, "preview_next", return_value=(200, {"revision": "r"})), self.held_add(tid):
            for wake in (1, 2, 3, 4):
                self.pending(tid, ADD, wake=wake)
                self.hub._sup_auto(tid, wake)
        sup = self.hub.tasks[tid]["supervisor"]
        self.assertEqual(sup["auto_steps"], 3)  # held reservations count as slots
        self.assertEqual(sup["pending"]["wake"], 4)
        self.assertIn("approve the next", sup["pending"]["error"])
        again = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        self.assertEqual(again.tasks[tid]["supervisor"]["auto_steps"], 3)  # survives restart
        with mock.patch.object(self.hub, "start_step"):
            self.hub.task_lever(tid, "done", origin="supervisor")  # an internal lever resets nothing
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["auto_steps"], 3)
        self.hub.tasks[tid].update(state="waiting", why="choose next step")
        self.assertEqual(self.hub.task_lever(tid, "pause")[0], 200)
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["auto_steps"], 0)

    def test_task_max_steps_caps_supervisor_only(self):
        self.hub.cfg["task_max_steps"] = 1
        tid = self.supervised_task()
        self.auto(tid)
        self.pending(tid, ADD)
        with mock.patch.object(self.hub, "request_next") as request:
            self.hub._sup_auto(tid, 1)
        self.assertEqual(request.call_count, 0)
        self.assertIn("task_max_steps", self.hub.tasks[tid]["supervisor"]["pending"]["error"])
        req = {"task": tid, "source_step": 1, "source_session": "s1", "kind": "code", "instructions": "x",
               "model": "auto", "request_id": "0d6d1f0e-0000-4000-8000-000000000002"}
        req["revision"] = self.hub.preview_next(req)[1]["revision"]
        with mock.patch.object(self.hub, "start_step"):
            self.assertEqual(self.hub.request_next(req)[0], 200)  # Fred's own Add step is not capped
        self.assertEqual(len(self.hub.tasks[tid]["steps"]), 2)

    def fail_chain(self, tid):
        task = self.hub.tasks[tid]
        verify = tasks._blank(2, "verify", "check", checked=1)
        verify.update(state="done", session="s2", verdict="FAIL", verdict_detail="test_a fails", dir="02-verify",
                      model="haiku", effort="low",
                      attempts=[{"session": "s2", "cost": 0.1, "started": 1, "ended": 2, "why": "", "final": True}])
        code = tasks._blank(3, "code", "repair")
        code.update(state="done", session="s3", sup_lineage=2, source_step=2, dir="03-code", model="haiku",
                    effort="low", attempts=[{"session": "s3", "cost": 0.1, "started": 3, "ended": 4, "why": "",
                                             "final": True}])
        again = tasks._blank(4, "verify", "check", checked=3)
        again.update(state="done", session="s4", verdict="FAIL", verdict_detail="test_a still fails", sup_lineage=2,
                     source_step=3, dir="04-verify", model="haiku", effort="low",
                     attempts=[{"session": "s4", "cost": 0.1, "started": 5, "ended": 6, "why": "", "final": True}])
        task["steps"] += [verify, code, again]
        task.update(current=4, last_good=4, why="VERDICT: FAIL: test_a still fails")
        task["supervisor"]["retries"] = {2: 1}
        tasks.save(self.folder, task)

    def test_retry_allowance_and_second_fail_escalate(self):
        self.hub.cfg["task_max_steps"] = 12
        tid = self.supervised_task()
        self.auto(tid)
        self.fail_chain(tid)
        for kind in ("code", "scout"):
            self.pending(tid, dict(ADD, kind=kind, instructions="repair again"), triggers=("fail",))
            with mock.patch.object(self.hub, "request_next") as request:
                self.hub._sup_auto(tid, 1)
            self.assertEqual(request.call_count, 0, kind)
            error = self.hub.tasks[tid]["supervisor"]["pending"]["error"]
            self.assertIn("test_a fails", error)
            self.assertIn("test_a still fails", error)
        # direct Retry: one supervisor retry per step on top of the chain's own
        stuck = self.stuck_task("20260101-000000-aaa1")
        self.auto(stuck)
        retry = dict(decision="retry", note="name the failing line", reason="r", confidence="high", for_fred="")
        self.pending(stuck, retry, triggers=("stuck",))
        with mock.patch.object(self.hub, "task_lever", return_value=(200, {"task": stuck})) as lever:
            self.hub._sup_auto(stuck, 1)
        self.assertEqual(lever.call_count, 1)
        self.assertEqual(supervisor.policy(self.hub.cfg, self.hub.tasks[stuck], 0.0)["retries"], {1: 1})
        self.pending(stuck, retry, triggers=("stuck",), wake=2)
        with mock.patch.object(self.hub, "task_lever") as lever:
            self.hub._sup_auto(stuck, 2)
        self.assertEqual(lever.call_count, 0)
        reloaded = server.Hub(self.hub.cfg, self.folder, exe=self.hub.runs.exe)
        self.assertEqual(supervisor.policy(self.hub.cfg, reloaded.tasks[stuck], 0.0)["mode"], "auto")  # JSON keys

    def test_work_cost_includes_attempts_live_updates_and_confirmed_chain(self):
        tid = self.supervised_task()
        self.auto(tid)
        task = self.hub.tasks[tid]
        epoch = task["supervisor"]["epoch"]
        task["steps"][0]["attempts"] = [
            {"session": "a", "cost": 2.0, "final": True, "sup": {"wake": 1, "epoch": epoch, "cost_at_start": 0.0}},
            {"session": "b", "cost": 9.0, "final": True, "sup": {"wake": 0, "epoch": epoch - 1, "cost_at_start": 0}},
            {"session": "c", "cost": 0.0, "final": False, "sup": {"wake": 2, "epoch": epoch, "cost_at_start": 0.0}}]
        with mock.patch.object(self.hub, "session", return_value={"cost": 3.5}):
            self.assertEqual(self.hub._sup_work(task), 5.5)  # live cost counted, an older window's not
            self.pending(tid, ADD)
            with mock.patch.object(self.hub, "request_next") as request:
                self.hub._sup_auto(tid, 1)
            self.assertEqual(request.call_count, 0)
            self.assertIn("work cap", task["supervisor"]["pending"]["error"])
        # a supervisor-caused continuation stops launching at the cap; an ordinary chain does not
        auto = self.supervised_task("20260101-000000-aaa2")
        t = self.hub.tasks[auto]
        t.update(progression=None, owner="service", state="running", why="")
        t["steps"].append(tasks._blank(2, "code", "next"))
        t["steps"][0]["attempts"][0]["sup"] = {"wake": 1, "epoch": t["supervisor"]["epoch"], "cost_at_start": 0.0}
        t["steps"][0]["attempts"][0]["cost"] = 6.0
        t["sup_cause"] = {"wake": 1, "epoch": t["supervisor"]["epoch"]}
        with mock.patch.object(self.hub.runs, "start") as start:
            self.hub.start_step(t, 2)
        self.assertEqual(start.call_count, 0)
        self.assertIn("work cap", t["why"])
        t.update(state="running", owner="service", why="")
        t["steps"][1]["state"] = "planned"
        with mock.patch.object(self.hub.runs, "start", return_value="sid-1") as start:
            self.hub.start_step(t, 2)  # no supervisor cause: the chain runs as before
        self.assertEqual(start.call_count, 1)

    def test_task_day_zero_and_inflight_money_caps(self):
        self.hub.cfg["supervisor_task_usd"] = 0
        tid = self.supervised_task()
        self.hub._sup_hook(self.hub.tasks[tid])
        self.tick(30.0)
        self.drain()
        self.assertEqual(self.calls, [])
        self.assertIn("cap", [r for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "result"][-1]["error"])
        # day cap across tasks, with an in-flight reservation and a full overrun recorded
        self.hub.cfg.update(supervisor_task_usd=0.5, supervisor_day_usd=0.6, supervisor_parallel=2)
        a, b = self.supervised_task("20260101-000000-bbb1"), self.supervised_task("20260101-000000-bbb2")
        self.gate.clear()
        self.answer = dict(decision=dict(WAIT), cost=0.9, model="haiku", turns=2, error="")  # an overrun
        self.hub._sup_hook(self.hub.tasks[a])
        self.hub._sup_hook(self.hub.tasks[b])
        self.tick(100.0)
        self.assertEqual(len(self.calls), 2)
        self.assertAlmostEqual(self.calls[0]["max_cost"] + self.calls[1]["max_cost"], 0.6)  # never the same balance
        self.gate.set()
        self.drain()
        records = usage.load_supervisor(self.folder)["records"]
        self.assertEqual(records[supervisor.request_id(a, 1)]["cost"], 0.9)  # recorded in full
        c = self.supervised_task("20260101-000000-bbb3")
        self.hub._sup_hook(self.hub.tasks[c])
        self.tick(300.0)
        self.drain()
        self.assertEqual(len(self.calls), 2)  # the day is spent: no next call

    def test_failed_pass_spend_and_ledger_survive_restart_delete_and_corruption(self):
        tid = self.supervised_task()
        self.answer = dict(decision=None, cost=0.02, model="haiku", turns=6, error="the pass failed: error_max_turns")
        with mock.patch.object(usage, "record_supervisor", return_value={"status": "error", "error": "disk"}):
            self.hub._sup_hook(self.hub.tasks[tid])
            self.tick(30.0)
            self.drain()
            other = self.supervised_task("20260101-000000-ccc1")
            self.hub._sup_hook(self.hub.tasks[other])
            self.tick(100.0)
            self.drain()
        self.assertEqual(len(self.calls), 1)  # an unsettled spend blocks the next launch
        self.tick(101.0)  # the ledger takes it now, and the blocked wake may run
        self.drain()
        self.assertEqual(self.hub.sup_unsettled, {})
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(usage.load_supervisor(self.folder)["records"][supervisor.request_id(tid, 1)]["cost"], 0.02)
        # a corrupt ledger refuses admission and is never overwritten
        path = self.folder / usage.DAYS_FILE
        path.write_text("{bad", encoding="utf-8")
        third = self.supervised_task("20260101-000000-ccc2")
        self.hub._sup_hook(self.hub.tasks[third])
        self.tick(500.0)
        self.drain()
        self.assertEqual(len(self.calls), 2)
        self.assertIn(third, self.hub.wakes)  # retained behind the visible hold, not spent
        self.assertEqual(path.read_text(encoding="utf-8"), "{bad")



class HoldsStallsDoneTest(AutonomyTest):
    """Plan 44 T9: plan holds, stepdone, automatic done and stalls, live and after a restart."""

    def at(self, tid, state, why, frm="task:running", owner=None, ts=200.0):
        task = self.hub.tasks[tid]
        task.update(state=state, why=why, owner=owner or task["owner"])
        tasks.log(self.folder, tid, [tasks._line(ts, task["steps"][0], frm, f"task:{state}", why)])
        tasks.save(self.folder, task)
        return task

    def done_task(self, tid="20260101-000000-d0d0", briefing=0):
        tid = self.supervised_task(tid)
        task = self.hub.tasks[tid]
        task["progression"] = None
        task["briefing"] = briefing
        self.at(tid, "done", "", owner="service")
        return tid

    def test_each_real_boundary_and_hold_wakes_once(self):
        self.hub.sup_recovered = True
        for i, why in enumerate(("plan ready: confirm", "plan 30 KB, over 24", "replanned: 1 step added")):
            tid = self.supervised_task(f"20260101-00000{i}-e0e0")
            task = self.at(tid, "waiting", why)
            found = supervisor.boundary(task, tasks.read_chain(self.folder, task))
            self.assertEqual(found["trigger"], "hold", why)
            self.hub._sup_hook(task)
            self.hub._sup_hook(task)
            self.assertEqual(len(self.hub.wakes[tid]["events"]), 1)
        for why in ("plan edited by Fred", "plan saved: 3 KB", "planning"):
            tid = self.supervised_task("20260101-000009-e0e0")
            task = self.at(tid, "waiting", why)
            self.assertIsNone(supervisor.boundary(task, tasks.read_chain(self.folder, task)), why)
        # Mark step done on a manual stuck step makes a new choose-next boundary
        tid = self.stuck_task("20260101-000000-e1e1")
        self.hub.wakes.pop(tid, None)
        with mock.patch.object(self.hub, "_accept_step"):
            self.assertEqual(self.hub.task_lever(tid, "stepdone")[0], 200)
        self.assertEqual(self.hub.wakes[tid]["triggers"], ["choose_next"])

    def test_questions_fable_pace_and_guidance_do_not_wake_or_dispatch(self):
        for i, why in enumerate(("asks: which file?", "asks: Plan gap: the schema", "confirm Fable",
                                 "step 02 opus over its pace")):
            tid = self.supervised_task(f"20260101-00000{i}-f0f0")
            task = self.at(tid, "waiting", why, owner="service")
            self.hub._sup_hook(task)
        for at in range(0, 400, 20):
            self.tick(float(at))
        self.drain()
        self.assertEqual(self.calls, [])

    def test_manual_confirm_and_automatic_keep_use_shared_progression(self):
        self.hub.sup_recovered = True
        tid = self.supervised_task()
        task = self.at(tid, "waiting", "plan 30 KB, over 24")
        task["plan"] = {"from": 1, "dir": "01-scout", "parts": [], "kb": 30, "words": 10}
        with mock.patch.object(self.hub, "start_step") as start:
            self.assertEqual(self.hub.task_lever(tid, "confirm")[0], 200)
        self.assertEqual(start.call_count, 0)
        task = self.hub.tasks[tid]
        self.assertEqual((task["state"], task["why"], task["owner"], len(task["steps"])),
                         ("waiting", "choose next step", "fred", 1))
        self.assertEqual(self.hub.wakes[tid]["triggers"], ["choose_next"])  # a new real manual boundary, once

    def test_done_wakes_after_final_brief_only_and_is_always_suggest(self):
        self.hub.sup_recovered = True
        tid = self.done_task(briefing=1)
        self.hub.tasks[tid]["supervisor"]["mode"] = "auto"
        self.hub._sup_hook(self.hub.tasks[tid])
        for at in range(0, 200, 20):
            self.tick(float(at))
        self.assertEqual(self.calls, [])  # the final brief is still writing
        self.hub._brief_done(tid, 1, {"fallback": "", "words": 3, "cost": 0.0, "text": "brief", "model": "haiku",
                                      "cut": []}, "raw")
        self.assertEqual(len(self.hub.wakes[tid]["events"]), 1)  # callback and earlier hook: one event
        self.answer = dict(decision=dict(ADD), cost=0.001, model="haiku", turns=2, error="")
        self.tick(400.0)
        self.drain()
        self.assertEqual(len(self.calls), 1)
        pending = self.hub.tasks[tid]["supervisor"]["pending"]
        self.assertEqual(pending["status"], "suggest")  # never automatic, even in auto mode
        self.assertIn("report only", pending["error"])
        self.hub._brief_done(tid, 1, {"fallback": "", "words": 3, "cost": 0.0, "text": "brief", "model": "haiku",
                                      "cut": []}, "raw")
        for at in range(400, 800, 20):
            self.tick(float(at))
        self.drain()
        self.assertEqual(len(self.calls), 1)
        # no room: no paid check
        self.hub.cfg["task_max_steps"] = 1
        full = self.done_task("20260101-000000-d1d1")
        self.hub._sup_hook(self.hub.tasks[full])
        self.tick(1000.0)
        self.drain()
        self.assertEqual(len(self.calls), 1)

    def test_restart_before_claim_recovers_holds_and_done(self):
        ids = {}
        for i, why in enumerate(("plan ready: confirm", "plan 30 KB, over 24", "replanned: no change")):
            tid = self.supervised_task(f"20260101-00000{i}-a9a9")
            self.at(tid, "waiting", why)
            ids[why] = tid
        ids["done"] = self.done_task()
        ids["briefing"] = self.done_task("20260101-000000-d2d2", briefing=1)
        consumed = self.supervised_task("20260101-000005-a9a9")
        task = self.at(consumed, "waiting", "plan ready: confirm")
        event = supervisor.boundary(task, tasks.read_chain(self.folder, task))["event"]
        supervisor.append_log(self.folder, consumed, {"ts": 1.0, "wake": 1, "phase": "claimed", "events": [event]})
        supervisor.append_log(self.folder, consumed, {"ts": 2.0, "wake": 1, "phase": "result", "events": [event],
                                                      "status": "rejected"})
        old = self.supervised_task("20260101-000006-a9a9")
        self.at(old, "waiting", "plan ready: confirm")
        self.at(old, "running", "", frm="task:waiting", owner="service")  # superseded historical hold
        hub = self.restarted()
        for at in range(0, 300, 10):
            self.now = float(at)
            hub._supervisor_tick()
            for th in hub.sup_threads:
                th.join(10)
        want = sorted(ids[k] for k in ("plan ready: confirm", "plan 30 KB, over 24", "replanned: no change", "done"))
        self.assertEqual(sorted(c["task"] for c in self.calls), want)
        self.assertIn(ids["briefing"], hub.wakes)  # retained until its final brief is written

    def stalled(self, tid="20260101-000000-5a5a", live=True, harness="claude", idle=1800.0):
        tid = self.supervised_task(tid)
        task = self.hub.tasks[tid]
        task.update(progression=None, owner="service", state="running", why="")
        task["steps"][0].update(state="running", session="s1")
        task["steps"][0]["attempts"][-1].update(final=False, started=50.0)
        row = {"state": "stall", "last_ts": 10_000.0 - idle, "harness": harness, "cost": 0.0, "run_live": True}
        return tid, row

    def test_stall_threshold_and_one_wake_per_attempt(self):
        tid, row = self.stalled(idle=1799.0)
        with mock.patch.object(self.hub.runs, "is_live", return_value=True), \
                mock.patch.object(self.hub, "session", return_value=row):
            self.assertEqual(self.hub._sup_stalls(now=10_000.0), [])
            row["last_ts"] = 10_000.0 - 1800.0
            self.assertEqual(self.hub._sup_stalls(now=10_000.0), [tid])
            self.hub._sup_stalls(now=10_050.0)
            self.assertEqual(len(self.hub.wakes[tid]["events"]), 1)  # the same attempt: one event
            for excluded in ("codex",):
                row["harness"] = excluded
                other, _ = self.stalled("20260101-000000-5b5b")
                self.assertNotIn(other, self.hub._sup_stalls(now=10_000.0))
            row["harness"] = "claude"
            self.hub.tasks[tid]["supervisor"]["mode"] = "off"
            self.hub.wakes.clear()
            self.assertNotIn(tid, self.hub._sup_stalls(now=10_000.0))
            self.hub.tasks[tid]["supervisor"]["mode"] = "suggest"
            # a new attempt may wake again
            self.hub.tasks[tid]["steps"][0]["attempts"].append({"session": "s1", "cost": 0, "started": 900.0,
                                                                "ended": None, "why": "", "final": False})
            self.hub._sup_stalls(now=10_000.0)
        self.assertEqual(len(self.hub.wakes[tid]["events"]), 1)
        self.assertEqual(self.hub.wakes[tid]["triggers"], ["stalled"])

    def test_stall_stop_and_followup_retry_each_need_approve(self):
        self.hub.sup_recovered = True
        tid, row = self.stalled()
        self.hub.tasks[tid]["supervisor"]["mode"] = "auto"
        self.answer = dict(decision=dict(decision="stop", reason="stalled", confidence="high", for_fred=""),
                           cost=0.004, model="sonnet", turns=2, error="")
        with mock.patch.object(self.hub.runs, "is_live", return_value=True), \
                mock.patch.object(self.hub, "session", return_value=row), \
                mock.patch.object(self.hub.runs, "stop") as stop:
            self.hub._sup_stalls(now=10_000.0)
            self.tick(100.0)
            self.drain()
            self.assertEqual(self.calls[0]["model"], "sonnet")
            pending = self.hub.tasks[tid]["supervisor"]["pending"]
            self.assertEqual((pending["status"], pending["decision"]["decision"]), ("suggest", "stop"))
            self.assertEqual(stop.call_count, 0)  # auto mode cannot stop
            self.assertEqual(self.hub.supervisor_action({"task": tid, "wake": 1, "action": "approve"})[0], 200)
            self.assertEqual(stop.call_count, 1)  # the stream interrupt through task_lever('stop') only
        task = self.hub.tasks[tid]
        self.assertEqual(task["state"], "stopped")
        with mock.patch.object(self.hub.runs, "is_live", return_value=False), \
                mock.patch.object(self.hub, "task_lever", wraps=self.hub.task_lever) as lever:
            self.tick(200.0)
            self.drain()
            pending = self.hub.tasks[tid]["supervisor"]["pending"]
            self.assertEqual((pending["decision"]["decision"], pending["decision"]["note"]),
                             ("retry", supervisor.STALLED_NOTE))
            self.assertEqual(len(self.calls), 1)  # the follow-up is fixed: no second model call
            self.hub._sup_auto(tid, pending["wake"])
            self.assertEqual(lever.call_count, 0)  # still needs Fred
        # Fred's ordinary Stop makes no follow-up
        plain, _ = self.stalled("20260101-000000-5c5c")
        with mock.patch.object(self.hub.runs, "stop"):
            self.hub.task_lever(plain, "stop")
        self.assertNotIn(plain, self.hub.wakes)

    def test_restart_after_approved_stalled_stop_preserves_followup(self):
        tid, row = self.stalled()
        task = self.hub.tasks[tid]
        task.update(state="stopped", owner="fred", why="stopped by Fred")
        task["steps"][0]["state"] = "failed"
        tasks.save(self.folder, task)
        follow = {"ts": 300.0, "step": 1, "session": "s1", "from": "stalled", "to": "stopped", "why": "stalled_stop",
                  "attempt": 1}
        supervisor.append_log(self.folder, tid, {"ts": 300.0, "wake": 1, "phase": "outcome", "status": "dispatched",
                                                 "action": "approve", "by": "fred", "followup": follow})
        hub = self.restarted()
        with mock.patch.object(hub.runs, "is_live", return_value=False):
            self.now = 0.0
            hub._supervisor_tick()
            self.now = 100.0
            hub._supervisor_tick()
        pending = hub.tasks[tid]["supervisor"]["pending"]
        self.assertEqual(pending["decision"]["note"], supervisor.STALLED_NOTE)
        again = self.restarted()  # the follow-up is consumed now: no duplicate
        with mock.patch.object(again.runs, "is_live", return_value=False):
            self.now = 200.0
            again._supervisor_tick()
            self.now = 400.0
            again._supervisor_tick()
        claims = [r for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "claimed"]
        self.assertEqual(len(claims), 1)

    def test_stuck_model_is_one_sonnet_pass_without_escalation_loop(self):
        self.hub.sup_recovered = True
        tid = self.stuck_task()
        self.answer = dict(decision=None, cost=0.01, model="sonnet", turns=6, error="no decision (unknown field x)")
        self.hub._sup_hook(self.hub.tasks[tid])
        for at in range(0, 600, 10):
            self.tick(float(at))
        self.drain()
        self.assertEqual([c["model"] for c in self.calls], ["sonnet"])


class ReplayTest(SupervisorServerTest):
    """Plan 44 T11 (Hub level): a replay is a bounded, accounting-only pass over the current saved evidence."""

    def replay_task(self, tid="20260101-000000-1111"):
        tid = self.supervised_task(tid)
        task = self.hub.tasks[tid]
        rev = supervisor.revision(self.folder, task)
        supervisor.append_log(self.folder, tid, {"ts": 100.0, "wake": 1, "phase": "claimed", "events": ["e1"],
                                                 "revision": rev, "epoch": 0, "prompt_hash": "abc123"})
        supervisor.append_log(self.folder, tid, {"ts": 101.0, "wake": 1, "phase": "result", "cost": 0.01,
                                                 "status": "suggest",
                                                 "decision": {"decision": "wait", "reason": "r", "confidence": "low",
                                                              "for_fred": ""},
                                                 "revision": rev, "epoch": 0})
        return tid

    def test_replay_uses_current_files_and_never_dispatches(self):
        tid = self.replay_task()
        before = (self.folder / "tasks" / tid / "task.json").read_bytes()
        captured = {}
        fake = mock.patch.object(supervisor, "run",
                                 side_effect=lambda cfg, exe, task, prompt, model, max_cost: captured.update(
                                     prompt=prompt) or {"decision": dict(WAIT), "cost": 0.001, "model": "haiku",
                                                        "turns": 2, "error": ""})
        fake.start()
        self.addCleanup(fake.stop)
        with mock.patch.object(self.hub, "task_lever", side_effect=AssertionError("no lever")), \
                mock.patch.object(self.hub, "request_next", side_effect=AssertionError("no append")), \
                mock.patch.object(self.hub.runs, "start", side_effect=AssertionError("no worker")):
            code, body = self.hub.replay_supervisor({"task": tid, "wake": 1})
        self.assertEqual(code, 200, body)
        self.assertTrue(body["no_dispatch"])
        self.assertEqual(body["original"]["prompt_hash"], "abc123")
        self.assertEqual(body["fresh"]["prompt_hash"], supervisor.prompt_hash(captured["prompt"]))
        self.assertTrue(body["fresh"]["check"]["ok"])
        self.assertEqual((self.folder / "tasks" / tid / "task.json").read_bytes(), before)
        records = usage.load_supervisor(self.folder)["records"]
        self.assertTrue(any(r.get("kind") == "replay" for r in records.values()))
        self.assertNotIn(tid, self.hub.supervising)

    def test_replay_refuses_off_paused_busy_unknown_and_bad_input(self):
        tid = self.replay_task()
        self.hub.tasks[tid]["supervisor"]["mode"] = "off"
        self.assertEqual(self.hub.replay_supervisor({"task": tid, "wake": 1})[0], 409)
        self.hub.tasks[tid]["supervisor"]["mode"] = "suggest"
        self.hub.tasks[tid]["supervisor"]["paused"] = True
        self.assertEqual(self.hub.replay_supervisor({"task": tid, "wake": 1})[0], 409)
        self.hub.tasks[tid]["supervisor"]["paused"] = False
        self.hub.wakes[tid] = {"due": 0.0, "triggers": [], "events": [], "n": 1}
        self.assertEqual(self.hub.replay_supervisor({"task": tid, "wake": 1})[0], 409)
        self.hub.wakes.clear()
        self.assertEqual(self.hub.replay_supervisor({"task": tid, "wake": 9})[0], 404)
        self.assertEqual(self.hub.replay_supervisor({"task": tid, "wake": True})[0], 400)
        self.assertEqual(self.hub.replay_supervisor({"task": "../x", "wake": 1})[0], 400)


class SupervisedIntakeHubTest(SupervisorServerTest):
    """Plan 44 T10 (Hub level): create_task builds one manual worker and keeps the rest as proposals."""

    def card(self, prompt="Fix add()"):
        return {"id": "20260102-000000-cafe", "project_dir": str(self.project), "prompt": prompt,
                "raw": prompt, "route": {"type": "normal"}, "demand": {}, "fields": {"goal": prompt}}

    def test_supervised_intake_keeps_one_step_and_proposals(self):
        tid = self.hub.create_task(self.card(), [{"kind": "scout", "goal": "look"},
                                                 {"kind": "code", "goal": "fix"}], "auto", supervised=True)
        task = self.hub.tasks[tid]
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout"])
        self.assertEqual(task["progression"], "manual")
        self.assertEqual(task["supervisor"]["proposed"], [{"kind": "code", "goal": "fix", "model": ""}])
        self.assertEqual(task["supervisor"]["mode"], "suggest")
        saved = tasks.load(self.folder, tid)
        self.assertEqual(saved["supervisor"]["proposed"], task["supervisor"]["proposed"])
        self.assertEqual(saved["progression"], "manual")

    def test_supervised_intake_no_steps_gets_one_scout(self):
        tid = self.hub.create_task(self.card("Fix add()"), [], "auto", supervised=True)
        task = self.hub.tasks[tid]
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout"])
        self.assertEqual(task["steps"][0]["goal"], "Fix add()"[:tasks.STEP_GOAL_MAX])
        self.assertEqual(task["goal"], "Fix add()")


class AcceptanceTest(AutonomyTest):
    """Plan 44 T12: cross-feature safety cases that close the backend (fake runner, fake clock, fresh Hubs)."""

    def join(self, hub):
        for t in list(hub.sup_threads):
            t.join(10)

    def test_debounce_duplicates_and_idle_advances_make_one_pass(self):
        tid = self.supervised_task()
        a, b = self.line(tid), self.line(tid, "plan ready: confirm", 101.0)
        self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", a, now=0.0)
        self.hub.wake_supervisor(self.hub.tasks[tid], "hold", b, now=10.0)
        for at, line in ((15.0, a), (25.0, b), (29.0, a)):
            self.hub.wake_supervisor(self.hub.tasks[tid], "choose_next", line, now=at)
        self.assertEqual((self.hub.wakes[tid]["due"], self.hub.wakes[tid]["n"]), (30.0, 2))  # duplicates: no re-arm
        for i in range(100):  # the hub loop's real entry point, idle after the one pass
            self.now = 29.0 + i
            self.hub.advance()
            self.join(self.hub)
        self.assertEqual(len(self.calls), 1)
        claim = self.claims(tid)
        self.assertEqual(len(claim), 1)
        self.assertEqual(claim[0]["triggers"], ["choose_next", "hold"])
        self.assertEqual(claim[0]["events"], [supervisor.event_id(a), supervisor.event_id(b)])
        self.assertEqual(self.hub.tasks[tid]["supervisor"]["wakes"], 1)
        self.assertNotIn(tid, self.hub.wakes)

    def test_crash_at_each_dispatch_boundary_has_at_most_one_effect(self):
        """A crash at each point, then a fresh Hub from the saved files and explicit advances (twice restarted).
        The effects are worker launches, levers and appended steps; a saved intent is never replayed."""
        starts = []

        def start(*args, **kwargs):
            starts.append(kwargs.get("title") or "")
            return f"sid-crash-{len(starts)}"
        expect = {  # name -> (model calls after the restart, steps after, pending status after, launches)
            "before_claim": (1, 2, None, 1),
            "after_claim": (0, 1, None, 0),
            "after_result": (0, 1, "suggest", 0),
            "after_intent": (0, 1, "uncertain", 0),
            "after_reservation": (0, 2, "uncertain", 0),
            "after_worker": (0, 2, "uncertain", 0),
        }
        for i, (name, (calls, steps, status, launches)) in enumerate(expect.items(), 1):
            with self.subTest(name=name):
                self.calls.clear()
                starts.clear()
                self.answer = dict(decision=dict(ADD), cost=0.002, model="haiku", turns=2, error="")
                tid = self.supervised_task(f"20260101-00000{i}-c0c0")
                self.auto(tid)  # the adversarial mode: a replayed decision would dispatch by itself
                task = self.hub.tasks[tid]
                event = supervisor.boundary(task, tasks.read_chain(self.folder, task))["event"]
                pid = supervisor.request_id(tid, 1)
                claim = {"ts": 1.0, "wake": 1, "phase": "claimed", "events": [event], "triggers": ["choose_next"],
                         "day": "2026-10-19", "reserved": 0.5, "pass": pid}
                result = {"ts": 2.0, "wake": 1, "phase": "result", "events": [event], "cost": 0.002,
                          "status": "suggest", "decision": dict(ADD), "error": "", "epoch": 0,
                          "revision": supervisor.revision(self.folder, task)}
                intent = {"call": "request_next", "request_id": pid, "source_step": 1}
                if name == "before_claim":
                    self.hub._sup_hook(task)  # queued in memory only, inside the debounce
                else:
                    usage.reserve_supervisor(self.folder, pid, {"task": tid, "wake": 1, "day": "2026-10-19"},
                                             0.5, 2.0)
                    supervisor.append_log(self.folder, tid, claim)
                if name in ("after_result", "after_intent", "after_reservation", "after_worker"):
                    supervisor.append_log(self.folder, tid, result)
                    usage.record_supervisor(self.folder, pid, {"cost": 0.002})
                if name == "after_intent":  # a lever intent: Finish
                    supervisor.append_log(self.folder, tid, {"ts": 3.0, "wake": 1, "phase": "dispatching",
                                                             "status": "dispatching", "by": "auto", "events": [event],
                                                             "dispatch": {"call": "task_lever", "lever": "done"}})
                if name in ("after_reservation", "after_worker"):
                    supervisor.append_log(self.folder, tid, {"ts": 3.0, "wake": 1, "phase": "dispatching",
                                                             "status": "dispatching", "by": "auto", "events": [event],
                                                             "dispatch": intent})
                    step = tasks._blank(2, "verify", "Check step 01 against the goal", checked=1)
                    step.update(request_id=pid, request_status="starting", source_step=1, source_session="s1")
                    if name == "after_worker":
                        step.update(state="running", session="s-worker", started=4.0,
                                    attempts=[{"session": "s-worker", "cost": 0.0, "started": 4.0, "ended": None,
                                               "why": "", "final": False}])
                        task.update(state="running", owner="service", why="", current=2)
                    else:
                        task.update(state="waiting", owner="fred", why="starting step 02", current=2)
                    task["steps"].append(step)
                tasks.save(self.folder, task)
                with mock.patch.object(server.runs.RunManager, "start", side_effect=start), \
                        mock.patch.object(server.Hub, "task_lever", side_effect=AssertionError("no lever replay")):
                    for again in range(2):  # restart twice: recovery is idempotent
                        hub = self.restarted()
                        for k in range(4):
                            self.now = 1000.0 * (again + 1) + 100.0 * k
                            hub.advance()
                            self.join(hub)
                        hub.reconcile_next_steps()
                mine = [c for c in self.calls if c["task"] == tid]
                self.assertEqual(len(mine), calls, name)
                saved = tasks.load(self.folder, tid)
                self.assertEqual(len(saved["steps"]), steps, name)
                self.assertEqual(len(starts), launches, name)
                pending = saved["supervisor"]["pending"]
                self.assertEqual(pending and pending["status"], status, name)
                records = supervisor.read_log(self.folder, tid)
                self.assertLessEqual(sum(1 for r in records if r.get("phase") == "dispatching"), 1, name)
                self.assertEqual(sum(1 for r in records if r.get("phase") == "claimed"), 1, name)
                self.assertEqual(sum(1 for r in records if r.get("phase") == "recovered"),
                                 1 if name in ("after_claim", "after_intent", "after_reservation", "after_worker") else 0,
                                 name)
                if name == "after_claim":
                    self.assertEqual(usage.load_supervisor(self.folder)["records"][pid]["status"], "unknown")
                if name == "after_reservation":
                    self.assertEqual((saved["state"], saved["steps"][1]["request_status"]), ("stuck", "failed"))
                    # the recovery's stuck boundary waits behind the uncertain card; Fred's dismissal releases it once
                    self.assertIn(tid, hub.wakes)
                    self.answer = dict(decision=dict(WAIT), cost=0.001, model="sonnet", turns=2, error="")
                    self.assertEqual(hub.supervisor_action({"task": tid, "wake": 1, "action": "reject"})[0], 200)
                    for k in range(4):
                        self.now += 100.0
                        hub.advance()
                        self.join(hub)
                    self.assertEqual(len([c for c in self.calls if c["task"] == tid]), 1)
                    self.assertEqual(len(tasks.load(self.folder, tid)["steps"]), 2)
                if name == "after_worker":
                    self.assertEqual(saved["steps"][1]["request_status"], "running")

    def test_all_pending_guidance_states_block_all_supervisor_actions(self):
        for i, status in enumerate(("queued", "dispatching", "uncertain", "failed")):
            with self.subTest(status=status):
                self.calls.clear()
                tid = self.supervised_task(f"20260101-00000{i}-9a9a")
                self.auto(tid)
                task = self.hub.tasks[tid]
                message = {"id": f"{i}" * 16, "status": status}
                task["messages"] = [message]
                self.hub.sup_recovered = True
                self.hub.wakes.clear()
                self.now = 0.0
                with mock.patch.object(self.hub, "request_next") as request, \
                        mock.patch.object(self.hub, "preview_next") as preview, \
                        mock.patch.object(self.hub, "task_lever") as lever:
                    # before the wake: no pass, the event is retained
                    self.hub._sup_hook(task)
                    for at in range(0, 300, 20):
                        self.tick(float(at))
                    self.assertEqual(self.calls, [])
                    self.assertIn(tid, self.hub.wakes)
                    # a saved suggestion: no Approve, no automatic dispatch, no replay
                    self.pending(tid, ADD)
                    self.assertEqual(self.hub.supervisor_action({"task": tid, "wake": 1, "action": "approve"})[0], 409)
                    self.hub._sup_auto(tid, 1)
                    self.assertEqual(self.hub.replay_supervisor({"task": tid, "wake": 1})[0], 409)
                    self.assertEqual(task["supervisor"]["pending"]["status"], "held")
                    # guidance that arrives during a pass holds its result, audited, never dispatched
                    task.pop("messages")
                    task["supervisor"]["pending"] = None
                    task["supervisor"]["wakes"] = 1
                    tasks.save(self.folder, task)
                    self.answer = dict(decision=dict(ADD), cost=0.001, model="haiku", turns=2, error="")
                    self.gate.clear()
                    self.now = 400.0
                    self.assertEqual(self.hub._supervisor_tick(), [tid])
                    task["messages"] = [message]
                    self.gate.set()
                    self.drain()
                    self.assertEqual(task["supervisor"]["pending"]["status"], "held")
                    result = [r for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "result"][-1]
                    self.assertEqual((result["status"], result["error"]), ("held", "held: pending guidance"))
                    for at in range(400, 800, 20):
                        self.tick(float(at))
                    self.drain()
                    self.assertEqual((request.call_count, preview.call_count, lever.call_count), (0, 0, 0))
                    self.assertEqual(len(self.calls), 1)
                    self.assertEqual(task["messages"], [message])  # the supervisor never replays guidance
                    # the guidance resolves with changed evidence: the held advice is superseded, one fresh wake
                    message["status"] = "dispatched"
                    tasks.write_step_file(self.folder, task, task["steps"][0], "facts.md", "guidance changed this")
                    self.answer = dict(decision=dict(WAIT), cost=0.001, model="haiku", turns=2, error="")
                    for at in range(800, 1000, 5):
                        self.tick(float(at))
                    self.drain()
                    self.assertEqual(len(self.calls), 2)
                    self.assertIsNone(task["supervisor"]["pending"])
                    self.assertEqual((request.call_count, preview.call_count, lever.call_count), (0, 0, 0))
                self.answer = dict(decision=dict(WAIT), cost=0.001, model="haiku", turns=2, error="")

    def test_pause_off_delete_or_evidence_edit_during_pass_never_dispatches(self):
        changes = {
            "pause": lambda tid: self.hub.task_lever(tid, "pause"),
            "off": lambda tid: self.hub.supervisor_action({"task": tid, "mode": "off"}),
            "delete": lambda tid: self.hub._drop(self.hub.tasks[tid]),
            "evidence": lambda tid: tasks.write_step_file(self.folder, self.hub.tasks[tid],
                                                          self.hub.tasks[tid]["steps"][0], "facts.md", "edited"),
        }
        self.hub.sup_recovered = True
        for i, (name, change) in enumerate(changes.items()):
            with self.subTest(name):
                self.calls.clear()
                tid = self.supervised_task(f"20260101-00000{i}-7b7b")
                self.auto(tid)
                self.answer = dict(decision=dict(ADD), cost=0.003, model="haiku", turns=2, error="")
                self.gate.clear()
                self.hub._sup_hook(self.hub.tasks[tid])
                self.now = 1000.0 * (i + 1)
                self.assertEqual(self.hub._supervisor_tick(), [tid])
                with self.hub.tlock:
                    change(tid)
                with mock.patch.object(self.hub, "request_next") as request, \
                        mock.patch.object(self.hub, "preview_next") as preview, \
                        mock.patch.object(self.hub, "task_lever") as lever:
                    self.gate.set()
                    self.drain()
                    for k in range(40):
                        self.tick(self.now + 10.0)
                    self.drain()
                    code = self.hub.supervisor_action({"task": tid, "wake": 1, "action": "approve"})[0]
                self.assertEqual((request.call_count, preview.call_count, lever.call_count), (0, 0, 0), name)
                self.assertEqual(code, 404 if name == "delete" else 409, name)
                self.assertEqual(len(self.calls), 1, name)  # its consumed event is never retried
                self.assertEqual(usage.load_supervisor(self.folder)["records"][supervisor.request_id(tid, 1)]["cost"],
                                 0.003, name)  # the paid pass settles in the ledger
                self.assertNotIn(tid, self.hub.supervising)
                if name == "delete":
                    self.assertNotIn(tid, self.hub.tasks)
                    self.assertFalse((self.folder / "tasks" / tid).exists())  # never recreated
                else:
                    self.assertAlmostEqual(self.hub.tasks[tid]["supervisor"]["usd"], 0.003)
                    self.assertEqual(len(self.hub.tasks[tid]["steps"]), 1)
        today = self.hub.usage_report()["supervisor"]["days"]
        self.assertAlmostEqual(sum(d["cost"] for d in today.values()), 0.012)  # a deleted task's spend stays

    def test_kind_only_edit_changes_replay_prompt_hash_not_revision(self):
        tid = self.supervised_task()
        self.hub._sup_hook(self.hub.tasks[tid])
        self.tick(100.0)
        self.drain()
        claim = self.claims(tid)[0]
        self.assertEqual(claim["prompt_hash"], supervisor.prompt_hash(self.calls[0]["prompt"]))
        root = self.folder / "tasks" / tid
        audit, saved = (root / "supervisor.jsonl").read_bytes(), (root / "task.json").read_bytes()
        server.kinds.ensure(self.folder)
        (server.kinds.folder(self.folder) / "supervisor.md").write_text("# supervisor\n\nEdited by Fred.",
                                                                       encoding="utf-8")
        code, body = self.hub.replay_supervisor({"task": tid, "wake": 1})
        self.assertEqual(code, 200, body)
        self.assertEqual(body["original"]["revision"], body["fresh"]["revision"])
        self.assertEqual(body["original"]["prompt_hash"], claim["prompt_hash"])
        self.assertNotEqual(body["fresh"]["prompt_hash"], claim["prompt_hash"])
        self.assertEqual(body["fresh"]["prompt_hash"], supervisor.prompt_hash(self.calls[-1]["prompt"]))
        self.assertIn("Edited by Fred.", self.calls[-1]["prompt"])
        self.assertEqual((root / "supervisor.jsonl").read_bytes(), audit)  # the original audit is unchanged
        self.assertEqual((root / "task.json").read_bytes(), saved)


SCRIPT = [dict(ADD, kind="code", instructions="Fix add() as the plan says"),
          dict(ADD, kind="verify", instructions="Check step 02 against the plan VERDICT-PASS"),
          {"decision": "finish", "reason": "verified", "confidence": "high", "for_fred": ""}]


class LifecycleAcceptanceTest(test_server.TaskServerTest):
    """Plan 44 T12: the whole supervised manual task over real HTTP, with fake_claude workers and a scripted fake
    supervisor pass (no paid provider)."""

    def test_supervised_manual_lifecycle_end_to_end(self):
        self.hub.cfg["supervisor_mode"] = "suggest"
        self.now = 0.0
        self.hub.sup_clock = lambda: self.now
        prompts = []

        def fake_run(cfg, exe, task, prompt, model, max_cost):
            prompts.append(prompt)
            return {"decision": dict(SCRIPT[len(prompts) - 1]), "cost": 0.004, "model": model, "turns": 2,
                    "error": ""}
        card = self.prep_card("fix add")
        with mock.patch.object(supervisor, "run", side_effect=fake_run), \
                mock.patch.object(self.hub.runs, "start", wraps=self.hub.runs.start) as start, \
                mock.patch.object(self.hub, "task_lever", wraps=self.hub.task_lever) as lever:
            status, data = self.call("/api/task", {"prep": card["id"], "prompt": f"{card['prompt']}\nHANDOFF-OK PLAN-OK",
                                                   "steps": [{"kind": "design", "goal": "plan the fix"}],
                                                   "effort": "auto", "supervised": True})
            self.assertEqual(status, 200, data)
            tid = data["task"]
            events = []
            for wake, (n, kind) in enumerate(((1, "design"), (2, "code"), (3, "verify")), 1):
                task = self.until(tid, lambda t: t["state"] == "waiting" and t["owner"] == "fred" and any(
                    s["n"] == n and s["state"] == "done" for s in t["steps"]), f"the {kind} boundary")
                self.assertEqual((task["why"], len(task["steps"])), ("choose next step", n))
                events.append(supervisor.boundary(task, tasks.read_chain(self.folder, task))["event"])
                self.assertIn(tid, self.hub.wakes)
                self.hub.advance()  # inside the debounce: nothing runs
                self.assertEqual(len(prompts), wake - 1)
                self.now += 100.0
                self.hub.advance()
                for t in list(self.hub.sup_threads):
                    t.join(10)
                pending = self.hub.tasks[tid]["supervisor"]["pending"]
                self.assertEqual((pending["wake"], pending["status"]), (wake, "suggest"))
                for _ in range(3):  # suggest mode: nothing starts until Approve
                    self.hub.poll_once()
                    self.hub.advance()
                self.assertEqual((start.call_count, len(self.hub.tasks[tid]["steps"])), (wake, n))
                self.assertNotIn(tid, self.hub.supervising)
                status, body = self.call("/api/task/supervisor", {"task": tid, "wake": wake, "action": "approve"})
                self.assertEqual(status, 200, body)
                self.assertEqual(self.call("/api/task/supervisor", {"task": tid, "wake": wake,
                                                                    "action": "approve"})[1].get("repeated"), True)
            task = self.hub.tasks[tid]
            self.assertEqual(task["state"], "done")  # Finish went through the shared done lever
            self.assertEqual([c.args[1:2] for c in lever.call_args_list], [("done",)])
            self.assertEqual(lever.call_args_list[0].kwargs.get("origin"), "supervisor")
            self.assertEqual(start.call_count, 3)  # design, then one worker per approved add_next_step
        # saved lineage and handovers
        steps = task["steps"]
        self.assertEqual([(s["kind"], s["state"]) for s in steps], [("design", "done"), ("code", "done"),
                                                                     ("verify", "done")])
        self.assertEqual((steps[1]["source_step"], steps[2]["source_step"], steps[2]["verdict"]), (1, 2, "PASS"))
        self.assertTrue(task["plan"])
        for s in steps[1:]:
            for name in ("received-handoff.md", "received.md"):
                self.assertTrue(tasks.read_step_file(self.folder, task, s, name), (s["n"], name))
        sessions = [s["session"] for s in steps]
        self.assertEqual(len(set(sessions)), 3)
        # no persistent supervisor session, worker or thread
        self.hub.poll_once()
        listed = {s["id"] for s in self.hub.snapshot()["sessions"]}
        self.assertEqual(listed, set(sessions))
        self.assertEqual((self.hub.supervising, self.hub.wakes), ({}, {}))
        self.assertFalse(any(t.is_alive() for t in self.hub.sup_threads))
        # the durable artifacts tell the same story
        sup = tasks.load(self.folder, tid)["supervisor"]
        self.assertEqual((sup["wakes"], sup["pending"], sup["epoch"], sup["paused"]), (3, None, 3, False))
        self.assertAlmostEqual(sup["usd"], 0.012)
        records = supervisor.read_log(self.folder, tid)
        for wake in (1, 2, 3):
            mine = [r for r in records if r.get("wake") == wake]
            self.assertEqual([r["phase"] for r in mine], ["claimed", "result", "dispatching", "outcome"], wake)
            self.assertEqual(mine[0]["events"], [events[wake - 1]])  # the original transition's event id
            self.assertEqual(mine[0]["prompt_hash"], supervisor.prompt_hash(prompts[wake - 1]))
            self.assertEqual(mine[-1]["status"], "dispatched")
        self.assertEqual(sum(r.get("cost") or 0 for r in records if r.get("phase") == "result"), 0.012)
        whys = [line["why"] for line in tasks.read_chain(self.folder, task)]
        self.assertEqual(sum(1 for w in whys if w.startswith("supervisor: dispatched")), 3)
        self.assertNotIn("marked done by Fred", whys)  # the supervisor's Finish is labeled as its own
        self.assertIn("marked done by the supervisor", whys)
        self.assertEqual(task["why"], "marked done by the supervisor")
        ledger = usage.load_supervisor(self.folder)["records"]
        for wake in (1, 2, 3):
            self.assertEqual(ledger[supervisor.request_id(tid, wake)]["cost"], 0.004)
        self.assertEqual(self.hub.usage_report()["supervisor"]["today"]["runs"], 3)


class NextMessageTest(DispatchTest):
    """Plan 48: Fred's next-step message wakes the supervisor once and authorizes the one add_next_step it returns."""

    TEXT = "verify only the 340 px case, then finish"

    def at_boundary(self, tid="20260101-000000-abcd"):
        tid = self.supervised_task(tid)
        task = self.hub.tasks[tid]
        tasks.write_note(self.folder, task, task["steps"][0],
                         "## Goal\ngoal\n## Findings\n- f\n## Files touched\n- (none)\n## Troubleshooting\n- (none)\n"
                         "## Open questions\n- (none)\n## Next\n- verify")
        return tid

    def say(self, tid, text=None, rid="a" * 32):
        code, body = self.hub.task_message({"task": tid, "text": text or self.TEXT, "request_id": rid,
                                            "target": tasks.message_target(self.hub.tasks[tid])})
        self.assertEqual(code, 200, body)
        return body["message"]

    def run_wake(self, tick=30.0):
        self.tick(tick)
        self.drain()

    def test_message_wake_adds_the_step_without_approve(self):
        tid = self.at_boundary()
        self.answer = dict(decision=dict(ADD, instructions="the model's own words"), cost=0.001, model="haiku",
                           turns=2, error="")
        self.say(tid)
        sup = self.hub.tasks[tid]["supervisor"]
        epoch = sup["epoch"]
        with mock.patch.object(self.hub, "request_next", wraps=self.hub.request_next) as request:
            self.run_wake()
        self.assertEqual(request.call_count, 1)
        req, kw = request.call_args.args[0], request.call_args.kwargs
        self.assertEqual((req["instructions"], req["kind"], kw), (self.TEXT, "verify", {"origin": "supervisor"}))
        self.assertIn(self.TEXT, self.calls[0]["prompt"])  # the pass read his words
        task = self.hub.tasks[tid]
        self.assertEqual(len(task["steps"]), 2)
        self.assertEqual((task["supervisor"]["auto_steps"], task["supervisor"]["epoch"]), (0, epoch))
        self.assertEqual(task["messages"][0]["status"], "dispatched")
        self.assertIsNone(task["supervisor"]["pending"])
        whys = [r["why"] for r in tasks.read_chain(self.folder, task)]
        self.assertTrue(any(w.startswith("supervisor: dispatched add_next_step") and w.endswith("by fred (message))")
                          for w in whys), whys)
        outcome = [r for r in supervisor.read_log(self.folder, tid) if r.get("phase") == "outcome"]
        self.assertEqual([r["status"] for r in outcome], ["dispatched"])

    def test_message_wake_other_decision_waits(self):
        tid = self.at_boundary()
        self.answer = dict(decision={"decision": "finish", "reason": "verified", "confidence": "high", "for_fred": ""},
                           cost=0.001, model="haiku", turns=2, error="")
        self.say(tid)
        with mock.patch.object(self.hub, "request_next") as request, mock.patch.object(self.hub, "task_lever") as lever:
            self.run_wake()
        self.assertEqual((request.call_count, lever.call_count), (0, 0))
        task = self.hub.tasks[tid]
        self.assertEqual(task["supervisor"]["pending"]["status"], "suggest")
        self.assertEqual(task["supervisor"]["pending"]["decision"]["decision"], "finish")
        self.assertEqual(len(task["steps"]), 1)

    def test_message_supersedes_a_pending_suggestion(self):
        tid = self.at_boundary()
        self.pending(tid, ADD)
        self.say(tid)
        self.assertIsNone(self.hub.tasks[tid]["supervisor"]["pending"])
        with mock.patch.object(self.hub, "request_next") as request:
            code, _ = self.hub.supervisor_action({"task": tid, "wake": 1, "action": "approve"})
        self.assertEqual((code, request.call_count), (409, 0))

    def test_message_wake_recovered_once_after_restart(self):
        tid = self.at_boundary()
        self.answer = dict(decision=dict(ADD), cost=0.001, model="haiku", turns=2, error="")
        self.say(tid)
        hub = self.restarted()  # the claim never happened: R1 finds the queued message from the saved files
        self.now = 0.0
        hub._supervisor_tick()
        self.assertEqual(hub.wakes[tid]["triggers"], ["message"])
        for at in range(20, 300, 10):
            self.now = float(at)
            hub._supervisor_tick()
            hub._supervisor_tick()
        for t in hub.sup_threads:
            t.join(10)
        self.assertEqual([c["task"] for c in self.calls], [tid])
        self.assertEqual(len(hub.tasks[tid]["steps"]), 2)
        self.assertEqual(hub.tasks[tid]["messages"][0]["status"], "dispatched")

    def test_message_wake_respects_live_gates(self):
        # a Fable hold on the added step keeps plan 44's held path: the step is added and waits for Fred
        tid = self.at_boundary()
        self.answer = dict(decision=dict(ADD), cost=0.001, model="haiku", turns=2, error="")
        self.say(tid)
        with mock.patch.object(self.hub, "request_next", return_value=(
                200, {"task": tid, "step": 2, "request_id": "x", "status": "held"})) as request:
            self.run_wake()
        self.assertEqual(request.call_count, 1)
        self.assertEqual(self.hub.tasks[tid]["messages"][0]["status"], "dispatched")
        # guidance queued for a running step still blocks the pass
        other = self.at_boundary("20260101-000000-eeee")
        self.say(other)
        self.hub.tasks[other]["messages"].append({"id": "g", "status": "queued", "mode": "queued"})
        before = len(self.calls)
        for at in range(40, 400, 20):
            self.tick(float(at))
        self.drain()
        self.assertEqual(len(self.calls), before)
        self.assertIn(other, self.hub.wakes)
        self.assertEqual(self.hub.tasks[other]["messages"][0]["status"], "queued")  # not claimed, not lost

    def test_stop_between_message_and_claim_sends_nothing(self):
        tid = self.at_boundary()
        self.say(tid)
        self.hub.task_lever(tid, "done")
        self.run_wake()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.hub.tasks[tid]["messages"][0]["status"], "cancelled")


# Each class reuses its parent's fixtures; an inherited test runs once, in the class that defines it.
for _cls in (WakeTest, DispatchTest, ApprovalTest, AutonomyTest, HoldsStallsDoneTest, SupervisedIntakeHubTest,
              ReplayTest, AcceptanceTest, LifecycleAcceptanceTest, NextMessageTest):
    for _name in [n for n in dir(_cls) if n.startswith("test") and n not in vars(_cls)]:
        setattr(_cls, _name, None)
del _cls, _name


if __name__ == "__main__":
    unittest.main()
