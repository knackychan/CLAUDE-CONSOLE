"""Plan 58: the super agent in the Hub (Task 5: superagent.run patched, a frozen clock, no hub loop) and over HTTP
(Task 6: the fake claude). Scratch homes only; no paid provider, no port 47770, no ~/.claude."""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from console import paths, server, superagent, supervisor, tasks, usage
from tests import test_server

T0 = 1_800_000_000.0
FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
DECISION = {"q": "Which file?", "options": [{"key": "1", "text": "style.css"}, {"key": "2", "text": "app.js"}],
            "default": "1", "step": 1, "asked": T0}


def make_task(hub, project, n, state="waiting", why="plan ready: confirm", **extra):
    """Task n of `hub` (id 20270115-0800NN-a0NN, label 0115-a0NN): one code step, then the verify; current 1; the
    step runs when the task does, else it is done; saved and put in hub.tasks. Task 6 uses it too."""
    tid = f"20270115-0800{n:02d}-a0{n:02d}"
    t = tasks.new_task(str(project), "proj", f"Task {n}", "goal",
                       tasks.plan_steps([{"kind": "code", "goal": "edit"}], 6), "normal", {}, "", "auto", T0, id_=tid)
    t["supervisor"] = supervisor.initial(hub.cfg, str(project), T0)
    running = state == "running"
    t["steps"][0].update(state="running" if running else "done", started=T0, ended=None if running else T0 + 60,
                         dir="01-code", model="sonnet", effort="medium",
                         attempts=[{"session": "", "cost": 0.1, "started": T0, "ended": None if running else T0 + 60,
                                    "why": "", "final": not running}])
    t.update(state=state, why="" if running else why, current=1, **extra)
    tasks.save(hub.folder, t)
    hub.tasks[tid] = t
    tasks.write_brief(hub.folder, t, t['steps'][0], '## Open questions\n- (none)\n')
    return tid


class SuperHubTest(unittest.TestCase):
    """Hub level: _super_tick is called by hand at frozen times; superagent.run is patched (no model, no process)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        data = Path(self.tmp.name) / "data"
        data.mkdir()
        env = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": str(data)})
        env.start()
        self.addCleanup(env.stop)
        self.now, self.mono, self.calls, self.answer = T0, 1000.0, [], None
        self.gate = threading.Event()
        self.gate.set()

        def fake_run(cfg, exe, cwd, prompt, model, max_cost):
            self.calls.append({"cfg": cfg, "cwd": cwd, "prompt": prompt, "model": model, "max_cost": max_cost})
            self.gate.wait(10)
            if self.answer:
                return self.answer(prompt)
            handles = re.findall(r"^(I\d+) ", prompt, re.M)
            out = {"items": [{"key": h, "do": "forward", "rank": len(handles) - k, "say": f"say {h}"}
                             for k, h in enumerate(handles)], "digest": ["sorted"], "notes": "watching"}
            return {"out": out, "cost": 0.003, "model": model, "turns": 2, "error": "", "ms": 5}
        patch = mock.patch.object(superagent, "run", side_effect=fake_run)
        patch.start()
        self.addCleanup(patch.stop)
        self.hub = self.make_hub(Path(self.tmp.name) / "home")
        self.addCleanup(self.drain)

    def make_hub(self, folder, **cfg):
        hub = server.Hub(dict(paths.load_config(), projects=[str(self.project)], supervisor_mode="gated", **cfg),
                         folder, exe=FAKE)
        hub.user_home = Path(self.tmp.name)
        hub.super_clock = lambda: self.now
        hub.super_mono = lambda: self.mono
        return hub

    def drain(self, hub=None):
        self.gate.set()
        for t in list((hub or self.hub).super_threads):
            t.join(10)

    def task(self, n, state="waiting", why="plan ready: confirm", hub=None, **extra):
        return make_task(hub or self.hub, self.project, n, state, why, **extra)

    def tick(self, at, hub=None):
        self.mono += at - self.now
        self.now = at
        return (hub or self.hub)._super_tick()

    def log(self, phase=None, hub=None):
        return [r for r in superagent.read_log((hub or self.hub).folder) if phase is None or r.get("phase") == phase]

    def key(self, tid, hub=None):
        hub = hub or self.hub
        return next(i["key"] for i in superagent.items(hub.snapshot(), hub.tasks) if i["id"] == tid)

    def pass_once(self):
        self.tick(self.now)
        self.assertTrue(self.tick(self.now+20))
        self.drain()

    def test_debounce_accounting_and_no_blind_retry(self):
        tid = self.task(1)
        self.assertFalse(self.tick(T0))
        self.assertEqual(self.hub.super_wake['due'], 1020)
        self.assertFalse(self.tick(T0+19))
        self.assertTrue(self.tick(T0+20))
        self.drain()
        self.assertTrue(self.hub.super['last']['ok'])
        self.assertEqual(self.hub.super['last']['cost'], .003)
        self.assertIn(self.key(tid), self.hub.super['ann'])
        self.assertIsNone(self.hub.super['claimed'])
        records = usage.load_super(self.hub.folder)['records']
        self.assertEqual(len(records), 1)
        self.assertEqual(next(iter(records.values()))['status'], 'settled')
        self.assertEqual([r['phase'] for r in self.log()], ['claimed', 'result'])
        self.assertTrue(all(r.get('pid') for r in self.log()))
        self.assertEqual(self.tick(T0+300), False)
        self.assertEqual(len(self.calls), 1)

    def test_monotonic_ceiling_and_coalescing(self):
        for n in range(1, 9):
            self.task(n)
            self.tick(T0+(n-1)*15)
        self.assertEqual(self.hub.super_wake['due'], 1120)
        self.now = T0-10000
        self.mono = 1119
        self.assertFalse(self.hub._super_tick())
        self.mono = 1120
        self.assertTrue(self.hub._super_tick())
        self.drain()

    def test_pass_is_outside_every_lock_and_fred_writes_survive(self):
        self.task(1)
        def answer(prompt):
            got = []
            def lock_test():
                with self.hub.tlock, self.hub.lock:
                    got.append(True)
            t = threading.Thread(target=lock_test)
            t.start(); t.join(2)
            self.assertEqual(got, [True])
            return {'out': {'items': [{'key':'I1','do':'forward','rank':1,'say':'yes'}],
                            'digest':['ok'], 'notes':'new'}, 'cost': .003, 'error':'', 'turns':2, 'ms':5}
        self.answer = answer
        self.gate.clear()
        self.tick(T0)
        self.assertTrue(self.tick(T0+20))
        self.hub.super['hand'] = {'fred': 'keep me'}
        self.drain()
        self.assertEqual(self.hub.super['hand'], {'fred': 'keep me'})

    def test_resolve_or_change_without_a_tick_discards_stale_advice(self):
        tid = self.task(1)
        self.task(2)
        self.gate.clear()
        self.tick(T0)
        self.tick(T0+20)
        self.hub.tasks[tid].update(state='done', accepted=T0)
        self.drain()
        self.assertEqual(len(self.hub.super['ann']), 1)
        self.assertEqual(self.hub.super['digest'], [])
        self.assertFalse((superagent.folder(self.hub.folder)/'notes.md').exists())
        self.assertEqual(next(iter(usage.load_super(self.hub.folder)['records'].values()))['cost'], .003)

    def test_policy_change_midpass_discards_every_annotation(self):
        self.task(1)
        self.gate.clear()
        self.tick(T0); self.tick(T0+20)
        (superagent.folder(self.hub.folder)/'orders.md').write_text('changed priority', encoding='utf-8')
        self.drain()
        self.assertEqual(self.hub.super['ann'], {})

    def test_model_failure_waits_for_a_new_event(self):
        self.task(1)
        self.answer = lambda prompt: {'out':None, 'cost':None, 'error':'failed', 'ms':0, 'turns':0}
        self.pass_once()
        for t in range(30, 2000, 100):
            self.tick(T0+t)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(next(iter(usage.load_super(self.hub.folder)['records'].values()))['status'], 'unknown')

    def test_coverage_and_annotation_merge_across_sorts(self):
        for n in range(1, 66):
            self.task(n, why='confirm Fable' if n<=31 else 'plan ready: confirm')
        self.pass_once()
        for _ in range(2):
            self.hub._super_arm(self.mono, [('asked','sort')], at_once=True)
            self.assertTrue(self.hub._super_tick())
            self.drain()
        self.assertEqual(len(self.hub.super['reviewed']), 65)
        self.assertEqual(len(self.hub.super['ann']), 65)

    def test_gate_transitions_and_day_rollover_wake_once(self):
        self.task(1)
        self.hub.cfg['super_day_usd'] = 0
        self.tick(T0)
        self.hub.cfg['super_day_usd'] = 1
        self.tick(T0+100)
        self.assertIsNotNone(self.hub.super_wake)
        self.tick(T0+120); self.drain()
        self.assertEqual(len(self.calls), 1)
        self.tick(T0+130)
        self.assertIsNone(self.hub.super_wake)
        self.tick(T0+86400)
        self.assertIsNotNone(self.hub.super_wake)

    def test_stable_restart_is_not_a_wake_and_orphans_are_unknown(self):
        self.task(1)
        self.pass_once()
        restarted = self.make_hub(self.hub.folder)
        self.assertFalse(restarted._super_tick())
        self.assertIsNone(restarted.super_wake)
        usage.reserve_super(self.hub.folder, 'orphan', usage.day_of(T0), .2, 1)
        again = self.make_hub(self.hub.folder)
        self.assertEqual(usage.load_super(again.folder)['records']['orphan']['status'], 'unknown')
        self.assertEqual(len(self.calls), 1)

    def test_faults_at_every_durable_boundary_and_recovery(self):
        for boundary in ['reserve','claim-save','claim-log','thread-start','result-log','settle','notes-save','final-state-save']:
            with self.subTest(boundary=boundary):
                hub = self.make_hub(Path(self.tmp.name)/boundary)
                self.task(1, hub=hub)
                self.now, self.mono = T0, 1000
                real_save, real_log, real_start = superagent.save_state, superagent.append_log, threading.Thread.start
                def save(home, state):
                    if boundary == 'claim-save' and state.get('claimed'):
                        raise OSError('claim disk full')
                    if boundary == 'final-state-save' and state.get('last') and not state.get('claimed'):
                        raise OSError('final disk full')
                    return real_save(home, state)
                def log(home, rec):
                    if boundary == 'claim-log' and rec.get('phase') == 'claimed' or boundary == 'result-log' and rec.get('phase') == 'result':
                        raise OSError('log disk full')
                    return real_log(home, rec)
                with mock.patch.object(superagent, 'save_state', side_effect=save), mock.patch.object(superagent, 'append_log', side_effect=log):
                    with mock.patch.object(usage, 'reserve_super', wraps=usage.reserve_super) as reserve, \
                         mock.patch.object(usage, 'record_super', wraps=usage.record_super) as settle, \
                         mock.patch.object(superagent, 'save_notes', wraps=superagent.save_notes) as notes, \
                         mock.patch.object(threading.Thread, 'start', autospec=True, side_effect=real_start) as start:
                        if boundary == 'reserve': reserve.return_value = {'status':'error','error':'reserve disk full'}; reserve.side_effect = None
                        if boundary == 'settle': settle.return_value = {'status':'error','error':'settle disk full'}; settle.side_effect = None
                        if boundary == 'notes-save': notes.side_effect = OSError('notes disk full')
                        if boundary == 'thread-start': start.side_effect = RuntimeError('no thread')
                        before = len(self.calls)
                        self.tick(T0, hub=hub)
                        self.tick(T0+20, hub=hub)
                        self.drain(hub)
                self.assertFalse(hub.super_busy)
                self.assertTrue(hub.super_error)
                if boundary in ['reserve','claim-save','claim-log','thread-start']:
                    self.assertEqual(len(self.calls), before)
                if boundary == 'final-state-save':
                    task = next(iter(hub.tasks.values()))
                    task['why'] = 'asks: A changed question?'
                    tasks.save(hub.folder, task)
                recovered = self.make_hub(hub.folder)
                if boundary == 'final-state-save':
                    self.assertTrue(recovered.super['notes_blocked'])
                records = usage.load_super(hub.folder)['records']
                self.assertTrue(all(r['status'] != 'reserved' for r in records.values()))
                if boundary == 'reserve':
                    self.assertEqual(records, {})
                elif boundary in ['claim-save', 'claim-log', 'thread-start']:
                    self.assertEqual(sum(r['cost'] for r in records.values()), 0)
                elif boundary != 'result-log':
                    self.assertEqual(sum(r['cost'] for r in records.values()), .003)
                before_records = json.loads(json.dumps(records))
                before_restart = len(self.calls)
                self.make_hub(hub.folder)
                self.assertEqual(len(self.calls), before_restart)
                self.assertEqual(usage.load_super(hub.folder)['records'], before_records)

    def test_expired_later_wakes_once_without_running_tasks(self):
        self.task(1)
        self.answer = lambda prompt: {'out': {'items':[{'key':'I1','do':'later','rank':1,'say':'later',
            'why':'wait', 'until':superagent._when(T0+600)}], 'digest':[], 'notes':''},
            'cost': .003, 'error':'', 'turns':1, 'ms':0}
        self.pass_once()
        self.tick(T0+600)
        events = list(self.hub.super_wake['events'])
        self.tick(T0+605)
        self.assertEqual(self.hub.super_wake['events'], events)
        self.assertEqual([e[0] for e in events], ['back'])

    def test_corrupt_state_blocks_and_zero_items_write_nothing(self):
        self.tick(T0)
        self.assertFalse((superagent.folder(self.hub.folder)/'state.json').exists())
        home = Path(self.tmp.name)/'corrupt'
        superagent.folder(home).mkdir(parents=True)
        (superagent.folder(home)/'state.json').write_text('{', encoding='utf-8')
        hub = self.make_hub(home)
        self.task(1, hub=hub)
        self.assertFalse(hub._super_tick())
        self.assertTrue(hub.super_error)
        self.assertEqual(len(self.calls), 0)
        state = superagent.blank_state()
        state['seen']['bad'] = 10**400
        superagent.save_state(home, state)
        hub = self.make_hub(home)
        self.assertTrue(hub.super_error)
        self.assertFalse(hub._super_tick())

    def test_claim_without_a_claim_log_recovers_unknown_without_replay(self):
        self.task(1)
        self.pass_once()
        job = self.log('claimed')[0]['job']
        pid = job['pid']
        day = usage.day_of(T0)
        home = Path(self.tmp.name)/'claim-only'
        usage.reserve_super(home, pid, day, .2, 1)
        state = superagent.blank_state()
        state.update(n=1, claimed={k:job[k] for k in ('n','pid','at','model','handles','bases','policy_hash','trigger')})
        superagent.save_state(home, state)
        hub = self.make_hub(home)
        self.assertIsNone(hub.super['claimed'])
        self.assertEqual(usage.load_super(home)['records'][pid]['status'], 'unknown')
        self.assertEqual(len(self.calls), 1)

    def test_busy_events_and_thread_list_remain_bounded(self):
        self.task(1)
        self.gate.clear()
        self.tick(T0); self.tick(T0+20)
        self.task(2)
        self.tick(T0+25)
        self.assertFalse(self.tick(T0+50))
        self.drain()
        self.assertTrue(self.tick(T0+55))
        self.drain()
        self.tick(T0+60)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.hub.super_threads, [])

    def test_hub_loop_calls_super_tick(self):
        with mock.patch.multiple(self.hub, poll_once=mock.DEFAULT, auto_steps=mock.DEFAULT, advance=mock.DEFAULT,
                                 read_costs=mock.DEFAULT, tick=mock.DEFAULT, reconcile_next_steps=mock.DEFAULT), \
             mock.patch.object(self.hub.runs, 'reconcile'), \
             mock.patch.object(self.hub, '_super_tick', side_effect=lambda: self.hub._stop.set()) as tick:
            self.hub.run()
        self.assertEqual(tick.call_count, 1)

    def test_missing_ledger_with_a_paid_audit_blocks_instead_of_resetting_spend(self):
        self.task(1)
        self.pass_once()
        (self.hub.folder/usage.DAYS_FILE).unlink()
        restarted = self.make_hub(self.hub.folder)
        self.assertIn('no ledger reservation', restarted.super_error)
        self.assertFalse(restarted._super_tick())
        self.assertEqual(len(self.calls), 1)

    def test_audit_output_uses_the_same_text_bounds_as_published_advice(self):
        self.task(1)
        self.answer = lambda prompt: {'out': {'items':[{'key':'I1','do':'forward','rank':1,'say':'x'*10000}],
            'digest':['x'*10000], 'notes':'\n'.join(['x'*10000]*100)},
            'cost':.003,'error':'','turns':1,'ms':1}
        self.pass_once()
        result = self.log('result')[-1]
        self.assertLessEqual(len(result['out']['items'][0]['say']), superagent.SAY_MAX)
        self.assertLessEqual(len(result['out']['notes']), superagent.NOTES_MAX+1)
        self.assertLessEqual(len(result['out']['digest'][0]), superagent.LINE_MAX)

    def test_reservation_write_that_completed_before_error_is_settled_zero(self):
        self.task(1)
        original = usage._write
        def write(folder, data):
            original(folder, data)
            raise OSError('after replacement')
        self.tick(T0)
        with mock.patch.object(usage, '_write', side_effect=write):
            self.assertFalse(self.tick(T0+20))
        self.assertEqual(self.calls, [])
        records = usage.load_super(self.hub.folder)['records']
        self.assertEqual(next(iter(records.values()))['cost'], 0)
        self.assertEqual(next(iter(records.values()))['status'], 'settled')
        self.make_hub(self.hub.folder)
        self.assertEqual(self.calls, [])


class SuperRouteTest(unittest.TestCase):
    """Reuse the HTTP fixture without repeating its unrelated inherited test cases."""
    call = test_server.RunServerTest.call

    def setUp(self):
        test_server.RunServerTest.setUp(self)
        self.hub.super_clock = lambda: T0
        self.hub.super_mono = lambda: 1000.0
        self.hub.cfg['super_debounce_s'] = 0
        patch = mock.patch.object(server.time, 'time', return_value=T0)
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        for thread in list(self.hub.super_threads):
            thread.join(10)
        test_server.RunServerTest.tearDown(self)

    def task(self, n, **extra):
        return make_task(self.hub, self.project, n, **extra)

    def pass_(self):
        self.assertTrue(self.hub._super_tick(), self.hub.super_error)
        for thread in list(self.hub.super_threads):
            thread.join(10)
        self.assertFalse(self.hub.super_busy)

    def test_get_fake_pass_and_new_equal_clock_item(self):
        self.task(1)
        self.task(2, why='confirm Fable')
        status, before = self.call('/api/super')
        self.assertEqual(status, 200)
        self.assertEqual(before['state'], 'unranked')
        self.assertEqual(before['why'], 'no pass yet')
        self.assertEqual(before['counts'], {'queue':2,'later':0,'always':1,'new':0})
        self.pass_()
        status, after = self.call('/api/super')
        self.assertEqual(after['state'], 'ranked', after['why'])
        self.assertEqual(after['spend']['today'], .003)
        self.assertEqual(after['coverage'], {'live':2,'last_submitted':2,'never_reviewed':0})
        self.assertEqual(after['digest'], ['fake digest: 2 items'])
        self.assertEqual(after['queue'][0]['items'][0]['always'], 'Fable confirm')
        self.assertIn('fake:', after['queue'][1]['items'][0]['say'])
        self.task(3)
        self.assertEqual(self.call('/api/super')[1]['counts']['new'], 1)
        self.assertGreater(after['last']['ms'], 0)

    def test_pause_resume_sort_and_host_guard(self):
        import http.client
        conn = http.client.HTTPConnection('127.0.0.1', self.port)
        conn.request('POST', '/api/super', body='{"action":"sort"}', headers={'Content-Type':'application/json'})
        response = conn.getresponse()
        self.assertEqual(response.status, 403)
        response.read(); conn.close()
        for body in [{}, {'action':'nap'}, {'action':'sort','x':1}, {'action':[]}]:
            self.assertEqual(self.call('/api/super', body)[0], 400)
        self.assertEqual(self.call('/api/super', {'action':'pause'})[1]['why'], 'paused')
        self.assertTrue(superagent.load_state(self.hub.folder)['paused'])
        self.assertEqual(self.call('/api/super', {'action':'sort'})[0], 409)
        self.assertEqual(self.call('/api/super', {'action':'resume'})[1]['due'], 0)
        self.task(1)
        self.pass_()
        self.assertEqual(self.call('/api/super', {'action':'sort'})[1]['due'], 0)
        self.pass_()
        self.assertEqual(usage.super_spent(usage.load_super(self.hub.folder)['records'], usage.day_of(T0))[0], .006)

    def test_failed_pause_or_action_log_is_503_and_blocks_admission(self):
        self.task(1)
        with mock.patch.object(superagent, 'save_state', side_effect=OSError('token=secret')):
            code, data = self.call('/api/super', {'action':'pause'})
        self.assertEqual(code, 503)
        self.assertNotIn('secret', str(data))
        self.assertFalse(self.hub._super_tick())
        self.assertTrue(superagent.load_state(self.hub.folder)['paused'])
        self.assertEqual(self.hub.super_threads, [])
        with mock.patch.object(superagent, 'append_log', side_effect=OSError('log blocked')):
            self.assertEqual(self.call('/api/super', {'action':'resume'})[0], 503)
            self.assertFalse(self.hub._super_tick())

    def test_get_is_pure_and_ledger_is_read_once(self):
        self.task(1)
        before = json.dumps(self.hub.super, sort_keys=True)
        with mock.patch.object(superagent, 'append_log', side_effect=AssertionError('GET wrote log')), \
             mock.patch.object(paths, 'write_text_atomic', side_effect=AssertionError('GET wrote state')), \
             mock.patch.object(superagent, 'run', side_effect=AssertionError('GET ran a provider')), \
             mock.patch.object(usage, 'load_super', wraps=usage.load_super) as read:
            self.assertEqual(self.call('/api/super')[0], 200)
            self.assertEqual(read.call_count, 1)
        self.assertEqual(json.dumps(self.hub.super, sort_keys=True), before)
        self.assertIsNone(self.hub.super_wake)
        self.assertEqual(self.hub.super_threads, [])
        self.assertFalse(superagent.folder(self.hub.folder).exists())

    def test_get_hides_changed_contract_without_a_tick(self):
        tid = self.task(1, why='asks: Which file?', decision=json.loads(json.dumps(DECISION)))
        self.pass_()
        before = json.dumps(self.hub.super, sort_keys=True)
        self.hub.tasks[tid]['decision']['options'][0]['text'] = 'changed option token=secret'
        code, data = self.call('/api/super')
        self.assertEqual(code, 200)
        self.assertFalse(data['queue'][0]['items'][0]['say'])
        self.assertNotIn('secret', json.dumps(data))
        self.assertEqual(data['digest'], [])
        self.assertEqual(json.dumps(self.hub.super, sort_keys=True), before)

    def test_unreadable_ledger_never_reports_zero_and_notes_are_masked(self):
        self.task(1)
        self.pass_()
        (superagent.folder(self.hub.folder)/'notes.md').write_text('token=secret', encoding='utf-8')
        self.assertEqual(self.call('/api/super')[1]['notes'], 'token=***\n')
        ledger_path = self.hub.folder/usage.DAYS_FILE
        ledger_path.unlink()
        missing = self.call('/api/super')[1]
        self.assertIsNone(missing['spend']['today'])
        self.assertFalse(self.hub._super_tick())
        (self.hub.folder/usage.DAYS_FILE).write_text('{', encoding='utf-8')
        data = self.call('/api/super')[1]
        self.assertEqual(data['state'], 'unranked')
        self.assertIsNone(data['spend']['today'])
        self.assertIn('unreadable', data['spend']['error'])
        self.assertIsNone(self.call('/api/usage')[1]['super']['today'])

    def test_fake_errors_later_and_unknown_handles(self):
        self.task(1)
        self.task(2)
        superagent.ensure(self.hub.folder)
        orders = superagent.folder(self.hub.folder)/'orders.md'
        orders.write_text('SUPER-LATER SUPER-UNKNOWN', encoding='utf-8')
        self.pass_()
        data = self.call('/api/super')[1]
        self.assertEqual(len(data['later']), 1)
        self.assertEqual(superagent.read_log(self.hub.folder)[-1]['dropped'], [{'at':2,'why':'unknown handle I99'}])
        orders.write_text('SUPER-ERROR', encoding='utf-8')
        self.call('/api/super', {'action':'sort'})
        self.pass_()
        data = self.call('/api/super')[1]
        self.assertEqual(data['state'], 'unranked')
        self.assertIn('error_max_turns', data['why'])
        self.assertEqual(data['last']['cost'], .02)

    def test_http_coverage_for_65_items_and_policy_changes(self):
        for n in range(1, 66):
            self.task(n, why='confirm Fable' if n<=31 else 'plan ready: confirm')
        self.pass_()
        data = self.call('/api/super')[1]
        self.assertEqual(data['coverage'], {'live':65,'last_submitted':30,'never_reviewed':35})
        self.assertEqual(data['counts']['queue'], 65)
        (superagent.folder(self.hub.folder)/'orders.md').write_text('a new priority', encoding='utf-8')
        data = self.call('/api/super')[1]
        self.assertEqual(data['state'], 'unranked')
        self.assertTrue(all(not i['say'] for c in data['queue'] for i in c['items']))
