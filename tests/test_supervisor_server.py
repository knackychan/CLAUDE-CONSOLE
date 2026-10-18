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
        tid = self.stuck_task()
        self.hub.tasks[tid]["supervisor"]["mode"] = "auto"
        self.pending(tid, dict(decision="retry", note="n", reason="r", confidence="high", for_fred=""),
                     triggers=("stuck",))
        with mock.patch.object(self.hub, "task_lever") as lever:
            self.assertEqual(self.hub._supervisor_dispatch(tid, 1, "auto")[0], 409)
        self.assertEqual(lever.call_count, 0)


if __name__ == "__main__":
    unittest.main()
