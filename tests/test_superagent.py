"""Plan 58 pure functions: scratch homes, frozen wall time, fake providers only."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import kinds, paths, server, superagent, supervisor, tasks, tuning

T0 = 1_800_000_000.0


class SettingsTest(unittest.TestCase):
    def test_defaults_and_gates(self):
        limits, errors = superagent.settings(paths.DEFAULTS)
        self.assertEqual(errors, [])
        self.assertEqual(limits['super_day_usd'], 1.0)
        self.assertEqual(limits['super_debounce_s'], 20)
        state = superagent.blank_state()
        self.assertEqual(superagent.status(limits, [], state, 0, True), (False, 'no pass yet'))
        self.assertEqual(superagent.blocked(limits, ['x'], state, False), 'settings: x')
        self.assertEqual(superagent.blocked(limits, [], dict(state, paused=True), True), 'paused')
        self.assertIn('off:', superagent.blocked(dict(limits, super_day_usd=0), [], state, True))
        self.assertEqual(superagent.blocked(limits, [], state, False), 'claude.exe not found')
        self.assertEqual(superagent.status(limits, [], state, 1, True), (False, 'over the day limit ($1.00)'))
        self.assertEqual(superagent.status(limits, [], dict(state, last={'ok': True}), 0, True), (True, ''))

    def test_bad_settings_fail_closed(self):
        for key, values in {
            'super_debounce_s': ['20', True, -1, 301, 20.5], 'super_sweep_s': [299],
            'super_timeout_s': [9], 'super_notes_lines': [201],
            'super_pass_usd': [-.1, 1.5, float('inf'), float('nan'), '.2', True, 10**400],
            'super_day_usd': [21], 'super_model': ['opus'], 'super_judge_model': ['haiku'],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    limits, errors = superagent.settings(dict(paths.DEFAULTS, **{key: value}))
                    self.assertEqual(len(errors), 1)
                    self.assertIn(key, errors[0])
                    self.assertTrue(superagent.blocked(limits, errors, {}, True))
        cfg = dict(paths.DEFAULTS)
        del cfg['super_day_usd']
        self.assertTrue(superagent.settings(cfg)[1])

    def test_tuning_and_kind_contract(self):
        self.assertEqual(tuning.validate({'super_model': 'sonnet'}, paths.DEFAULTS)[1],
                         {'super_model': 'haiku only'})
        self.assertIn('super_notes_lines', tuning.validate({'super_notes_lines': 40.5}, paths.DEFAULTS)[1])
        self.assertEqual(tuning.validate({'super_day_usd': 0}, paths.DEFAULTS), ({'super_day_usd': 0}, {}))
        self.assertEqual(tuning.view(paths.DEFAULTS)['super_day_usd']['group'], 'super')
        for slot in ('$You', '$you', '$lines'):
            self.assertIn(slot, kinds.seed_text('super'))


class FilesTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        env = mock.patch.dict(os.environ, CC_CONSOLE_HOME=str(self.home))
        env.start()
        self.addCleanup(env.stop)
        clock = mock.patch.object(superagent.time, 'time', return_value=T0)
        clock.start()
        self.addCleanup(clock.stop)

    def test_seed_and_atomic_writes(self):
        with mock.patch.object(paths, 'write_text_atomic', wraps=paths.write_text_atomic) as write:
            self.assertTrue(superagent.ensure(self.home))
            self.assertFalse(superagent.ensure(self.home))
            self.assertEqual(superagent.read_orders(self.home), '')
            superagent.save_state(self.home, superagent.blank_state())
            superagent.save_notes(self.home, 'notes')
            superagent.save_prompt(self.home, 'prompt')
            self.assertEqual(write.call_count, 4)
        p = superagent.folder(self.home) / 'orders.md'
        p.write_text('mine', encoding='utf-8')
        self.assertFalse(superagent.ensure(self.home))
        self.assertEqual(superagent.read_orders(self.home), 'mine')

    def test_state_missing_roundtrip_and_strict_validation(self):
        state = superagent.blank_state()
        self.assertEqual(superagent.load_state(self.home), state)
        state.update(paused=True, reviewed={'k': 2}, seen={'k': T0}, future_extension={'x': 1})
        superagent.save_state(self.home, state)
        self.assertEqual(superagent.load_state(self.home), state)
        state['ann']['k'] = {'do': 'forward', 'rank': 1, 'say': 'set token=abc', 'why': '',
                             'batch': '', 'until': None, 'basis': 'a' * 64}
        superagent.save_state(self.home, state)
        self.assertEqual(superagent.load_state(self.home)['ann']['k']['say'], 'set token=***')
        path = superagent.folder(self.home) / 'state.json'
        for bad in ['{', '[]', json.dumps(dict(state, v=2)), json.dumps(dict(state, v=True)),
                    json.dumps(dict(state, paused='false')), json.dumps(dict(state, n=True)),
                    json.dumps(dict(state, seen={'k': -1})), json.dumps(dict(state, seen={'k': float('nan')})),
                    json.dumps(dict(state, reviewed={'k': True})),
                    json.dumps(dict(state, ann={'k': {'do': 'later'}})),
                    json.dumps(dict(state, last={'ok': 'yes'})),
                    json.dumps(dict(state, claimed={'pid': 'broken'}))]:
            with self.subTest(bad=bad):
                path.write_text(bad, encoding='utf-8')
                with self.assertRaises(ValueError):
                    superagent.load_state(self.home)
        path.write_bytes(b'\xff')
        with self.assertRaises(ValueError):
            superagent.load_state(self.home)

    def test_orders_are_masked_before_limits_and_never_truncated(self):
        superagent.ensure(self.home)
        path = superagent.folder(self.home) / 'orders.md'
        path.write_text('# head\n\nnever raise chats before 18:00\n  # ignored\ntoken=abc\n', encoding='utf-8')
        self.assertEqual(superagent.read_orders(self.home), 'never raise chats before 18:00\ntoken=***')
        for text in ['x' * 201, '\n'.join(['x' * 199] * 30)]:
            path.write_text(text, encoding='utf-8')
            with self.assertRaises(ValueError):
                superagent.read_orders(self.home)
        with mock.patch.object(Path, 'read_text', side_effect=PermissionError('token=secret')):
            with self.assertRaises(ValueError) as exc:
                superagent.read_orders(self.home)
            self.assertNotIn('secret', str(exc.exception))

    def test_notes_bounds_and_secrets(self):
        self.assertEqual(superagent.cut_notes(None, 40), '')
        self.assertEqual(superagent.cut_notes('x', 0), '')
        self.assertEqual(superagent.cut_notes('token=abc', 40), 'token=***\n')
        text = superagent.cut_notes('\n'.join(['x' * 300] * 50), 40)
        self.assertLessEqual(len(text.rstrip()), 4000)
        self.assertTrue(all(len(line) <= 200 for line in text.splitlines()))

    def test_log_strings_masked_before_dump_and_rotated_history(self):
        rec = {'phase': 'result', 'out': {'items': [{'say': 'set token=abc'}]}}
        superagent.append_log(self.home, rec)
        self.assertEqual(superagent.read_log(self.home)[0]['out']['items'][0]['say'], 'set token=***')
        with mock.patch.object(superagent, 'LOG_MAX', 1):
            superagent.append_log(self.home, {'phase': 'pause'})
            self.assertEqual(len(superagent.read_log(self.home)), 2)
            superagent.append_log(self.home, {'phase': 'resume'})
        self.assertEqual([r['phase'] for r in superagent.read_log(self.home)], ['pause', 'resume'])
        with (superagent.folder(self.home) / 'super.jsonl').open('a', encoding='utf-8') as fh:
            fh.write('{\n')
        with self.assertRaises(ValueError):
            superagent.read_log(self.home)
        self.assertEqual(rec['out']['items'][0]['say'], 'set token=abc')

    def test_required_write_failures_propagate(self):
        with mock.patch.object(paths, 'write_text_atomic', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                superagent.save_state(self.home, superagent.blank_state())
        with mock.patch('builtins.open', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                superagent.append_log(self.home, {'phase': 'claimed'})

    def test_imports_point_one_way(self):
        import ast
        source = Path(superagent.__file__).read_text(encoding='utf-8')
        names = [a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom) for a in n.names]
        self.assertNotIn('server', names)
        self.assertNotIn('supervisor', names)


T0 = 1_800_000_000.0
DECISION = {"q": "Which file?", "options": [{"key": "1", "text": "style.css"}, {"key": "2", "text": "app.js"}],
            "default": "1", "step": 1, "asked": T0}


def make_task(tid, state, why="", **extra):
    """One code step (plus the verify plan_steps adds), current 1, done once with one attempt."""
    t = tasks.new_task("D:/proj", "proj", f"Task {tid[-4:]}", "goal",
                       tasks.plan_steps([{"kind": "code", "goal": "edit"}], 6), "normal", {}, "", "auto", T0, id_=tid)
    t["steps"][0].update(state="done", started=T0, ended=T0 + 60, dir="01-code", model="sonnet", effort="medium",
                         attempts=[{"session": "", "cost": 0.1, "started": T0, "ended": T0 + 60, "why": "",
                                    "final": True}])
    t.update(state=state, why=why, current=1, **extra)
    return t


def session_row(sid, group="needs", state="failed", task="", tone="green"):
    return {"id": sid, "group": group, "state": state, "task": task, "chat_task": "", "turn_ts": T0,
            "ctx_tone": tone, "handoff_by": "", "project": "proj", "project_dir": "D:/proj", "title": "a chat",
            "source": "vscode", "text": "Failed", "stop_question": ""}


def snap_of(*task_list, sessions=()):
    return {"tasks": [server.task_row(t) for t in task_list], "sessions": list(sessions)}


def item(name, kind='hold', always='', **extra):
    return dict(key=name, id=name, type='task', kind=kind, always=always, label=name, title=name,
                project='proj', project_dir='D:/proj', level='gated', incomplete=False,
                contract={'action': ['confirm'], 'question': '', 'options': [], 'default': ''}, **extra)


def annotation(do='forward', rank=1, **extra):
    return dict({'do': do, 'rank': rank, 'say': 'say', 'why': '', 'batch': '', 'until': None, 'basis': 'a' * 64}, **extra)


class ItemsTest(unittest.TestCase):
    def task(self, n, state='waiting', why='plan ready: confirm', **extra):
        return make_task(f'20270115-0800{n:02d}-a0{n:02d}', state, why, **extra)

    def test_golden_items(self):
        cases = [
            ('waiting', 'asks: Which file?', {'decision': DECISION}, 'decision', ''),
            ('waiting', 'asks: Which file?', {'decision': dict(DECISION, default='')}, 'decision', 'decision without a default'),
            ('waiting', 'asks: Which file?', {}, 'question', 'decision without a default'),
            ('waiting', 'confirm Fable', {}, 'hold', 'Fable confirm'),
            ('waiting', 'sonnet over its pace', {}, 'hold', 'pace hold'),
            ('waiting', 'plan ready: confirm', {}, 'hold', ''),
            ('stuck', 'verify failed twice: test_x', {}, 'failed_twice', 'second verify FAIL'),
            ('stuck', 'step 01 failed', {}, 'stuck', ''),
            ('waiting', 'supervisor work cap reached ($5.00 of $5)', {}, 'hold', 'work cap'),
            ('done', '', {'pending': {'wake': 3, 'status': 'suggest', 'decision': {'decision': 'finish'}}}, 'suggestion', ''),
            ('running', '', {'pending': {'wake': 4, 'status': 'uncertain'}}, 'suggestion', 'uncertain dispatch'),
            ('stuck', 'step 01 failed', {'limit': 'claude/sonnet'}, 'stuck', 'usage limit'),
            ('waiting', 'plan ready: confirm', {'messages': [{'status': 'uncertain', 'mode': 'answer'}]}, 'hold', 'uncertain dispatch'),
            ('handed', '', {'handoff_note': 'saved'}, 'handed', ''),
            ('running', '', {}, None, ''), ('done', '', {'accepted': T0}, None, ''),
        ]
        for n, (state, why, extra, kind, always) in enumerate(cases, 1):
            with self.subTest(row=n):
                extra = copy.deepcopy(extra)
                pending, limit = extra.pop('pending', None), extra.pop('limit', None)
                task = self.task(n, state, why, **extra)
                if pending:
                    task['supervisor'] = supervisor.initial(paths.DEFAULTS, 'D:/proj', T0)
                    task['supervisor']['pending'] = pending
                if limit:
                    task['steps'][0]['limit'] = limit
                result = superagent.items(snap_of(task), {task['id']: task})
                if kind is None:
                    self.assertEqual(result, [])
                else:
                    self.assertEqual((result[0]['kind'], result[0]['always']), (kind, always))
                    self.assertEqual(result[0]['label'], tasks.label(task['id']))
        for row, expected in [(session_row('s17'), 'failed'),
                              (session_row('s18', state='running', tone='red'), 'context'),
                              (session_row('s19', task='t'), None),
                              (session_row('s20', group='replied'), None)]:
            result = superagent.items(snap_of(sessions=[row]), {})
            self.assertEqual(result[0]['kind'] if result else None, expected)

    def test_identity_covers_decisions_suggestions_and_stop(self):
        task = self.task(1, 'waiting', 'asks: Which file?', decision=copy.deepcopy(DECISION))
        key = lambda: superagent.items(snap_of(task), {task['id']: task})[0]['key']
        first = key()
        task['updated'] += 60
        task['steps'][0]['attempts'][0]['cost'] = 50
        self.assertEqual(key(), first)
        for mutate in [lambda: task['decision']['options'][0].update(text='new'),
                       lambda: task['decision'].update(default='2'),
                       lambda: task['steps'][0]['attempts'].append({'session': 's2', 'cost': 0, 'why': ''}),
                       lambda: task.update(why='asks: Another question?')]:
            before = key()
            mutate()
            self.assertNotEqual(key(), before)
        row = session_row('s')
        first = superagent.items(snap_of(sessions=[row]), {})[0]['key']
        row['stop_question'] = 'new question'
        self.assertNotEqual(superagent.items(snap_of(sessions=[row]), {})[0]['key'], first)

    def test_pure_and_task_sessions_count_once(self):
        t = self.task(1)
        snap = snap_of(t, sessions=[session_row('s', task=t['id']), session_row('loose')])
        before = copy.deepcopy((snap, t))
        result = superagent.items(snap, {t['id']: t})
        self.assertEqual([i['type'] for i in result], ['task', 'session'])
        self.assertEqual((snap, t), before)


class QueueTest(unittest.TestCase):
    def test_golden_order_and_purity(self):
        data = [item(k, always=a) for k, a in [('G', 'decision without a default'), ('A', 'Fable confirm'),
                ('B', ''), ('C', ''), ('D', ''), ('E', ''), ('H', ''), ('I', ''), ('F', '')]]
        state = superagent.blank_state()
        state.update(seen=dict(zip('GABCDEHIF', [T0+x for x in (90,100,110,120,130,140,150,160,300)])),
                     last={'ok': True, 'at': T0+200})
        state['ann'] = {'A': annotation('later', 9, **{'why': 'wait', 'until': T0+600}),
                        'B': annotation(rank=3), 'C': annotation(rank=1),
                        'D': annotation('batch', 2, **{'batch': 'pid:acc'}),
                        'E': annotation('batch', 4, **{'batch': 'pid:acc'}),
                        'H': annotation('later', 5, **{'why': 'wait', 'until': T0+600})}
        before = copy.deepcopy(state)
        for now, ranked, expected, later in [(T0+400, True, ['G','A','C','DE','B','I','F'], ['H']),
            (T0+700, True, ['G','A','C','DE','B','H','I','F'], []),
            (T0+400, False, list('GABCDEHIF'), [])]:
            result = superagent.queue(data, state, now, ranked)
            self.assertEqual([''.join(i['id'] for i in c['items']) for c in result['queue']], expected)
            self.assertEqual([i['id'] for i in result['later']], later)
            if ranked:
                self.assertTrue(result['queue'][-1]['items'][0]['new'])
                self.assertEqual(result['queue'][1]['items'][0]['do'], 'forward')
            else:
                self.assertTrue(all(not c['items'][0]['say'] and not c['items'][0]['new'] for c in result['queue']))
        self.assertEqual(state, before)

    def test_invalid_later_autodefault_and_incompatible_batches(self):
        data = [item('A'), item('B')]
        state = superagent.blank_state()
        for until, why in [(None, 'wait'), (T0-1, 'wait'), (T0+90000, 'wait'), (T0+500, '')]:
            state['ann'] = {'A': annotation('later', **{'until': until, 'why': why})}
            self.assertEqual(superagent.queue(data, state, T0, True)['later'], [])
        state['ann'] = {k: annotation('batch', **{'batch': 'pid:acc'}) for k in 'AB'}
        data[1]['contract']['question'] = 'different'
        self.assertEqual(len(superagent.queue(data, state, T0, True)['queue']), 2)
        data[1]['contract'] = copy.deepcopy(data[0]['contract'])
        state['ann']['B']['batch'] = 'other:acc'
        self.assertEqual(len(superagent.queue(data, state, T0, True)['queue']), 2)
        self.assertEqual(superagent.queue(data[:1], state, T0, True)['queue'][0]['items'][0]['do'], 'forward')
        state['ann'] = {'A': annotation('later', **{'until': T0+500, 'why': 'wait'})}
        data[0].update(level='auto', deadline=T0+600)
        self.assertEqual(superagent.queue(data, state, T0, True)['later'], [])

    def test_coverage_selection_with_65_items_and_31_always(self):
        live = [item(str(n), always='hard' if n < 31 else '') for n in range(65)]
        state = superagent.blank_state()
        covered = set()
        for n in range(1, 4):
            selected = superagent.select_items(live, state)[:30]
            for i in selected:
                covered.add(i['key'])
                state['reviewed'][i['key']] = n
        self.assertEqual(len(covered), 65)
        self.assertEqual(len(superagent.queue(live, state, T0, True)['queue']), 65)

    def test_sync_forgets_reviewed_and_expiry_is_once(self):
        state = superagent.blank_state()
        live = [item('A'), item('B')]
        self.assertEqual(superagent.sync(state, live, T0), (['A','B'], [], True))
        self.assertEqual(superagent.sync(state, live, T0+1), ([], [], False))
        state['reviewed'] = {'B': 1}
        state['ann'] = {'A': annotation('later', **{'until': T0+5, 'why': 'wait'}), 'Z': annotation()}
        self.assertEqual(superagent.sync(state, live[:1], T0+6), ([], ['A'], True))
        self.assertEqual(state['reviewed'], {})
        self.assertEqual(superagent.sync(state, live[:1], T0+7), ([], [], False))

    def test_new_before_tick_and_equal_clock(self):
        state = superagent.blank_state()
        state['last'] = {'ok': True, 'at': T0}
        result = superagent.queue([item('A')], state, T0, True)
        self.assertTrue(result['queue'][0]['items'][0]['new'])

    def test_malformed_annotations_have_no_advice(self):
        state = superagent.blank_state()
        state['ann']['A'] = {'rank': 'x', 'say': 5, 'batch': ['a']}
        row = superagent.queue([item('A')], state, T0, True)['queue'][0]['items'][0]
        self.assertEqual((row['rank'], row['say'], row['batch']), (None, '', ''))
