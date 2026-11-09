"""Plan 58 pure functions: scratch homes, frozen wall time, fake providers only."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import kinds, paths, superagent, tuning

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
