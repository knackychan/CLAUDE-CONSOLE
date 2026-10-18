"""Plan 44 backend: the supervisor's policy, audit, digest and bounded pass (pure tests)."""
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import paths, supervisor, tasks


def cfg(**over):
    base = dict(paths.DEFAULTS, projects=["D:\\work", "C:\\other"],
                supervisor_projects={}, supervisor_mode="suggest")
    base.update(over)
    return base


class PolicyTest(unittest.TestCase):
    def test_default_suggest_and_task_project_global_precedence(self):
        c = cfg(supervisor_projects={"d:/work": "auto"})  # Windows spelling: drive letter and slash differ
        # global default -> suggest; project override -> auto; explicit task mode wins
        self.assertEqual(supervisor.initial(c, "D:\\work", 100.0)["mode"], "auto")
        self.assertEqual(supervisor.initial(c, "C:\\other", 100.0)["mode"], "suggest")
        self.assertEqual(supervisor.initial(c, "D:\\work", 100.0, mode="off")["mode"], "off")
        for mode in supervisor.MODES:
            self.assertEqual(supervisor.initial(c, "C:\\other", 100.0, mode=mode)["mode"], mode)
        # the saved task override survives a later project/global change
        saved = supervisor.initial(c, "C:\\other", 100.0, mode="auto")
        task = {"project_dir": "C:\\other", "supervisor": saved}
        changed = cfg(supervisor_projects={"C:/other": "off"}, supervisor_mode="off")
        self.assertEqual(supervisor.policy(changed, task, 200.0)["mode"], "auto")
        self.assertEqual(saved, supervisor.initial(c, "C:\\other", 100.0, mode="auto"))  # inputs unchanged

    def test_legacy_task_loads_without_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            from unittest import mock
            with mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": tmp}):
                task = tasks.new_task("D:\\work", "work", "Legacy", "goal", tasks.plan_steps(
                    [{"kind": "scout", "goal": "look"}], 6), "normal", {}, "", "auto", 100.0)
                self.assertNotIn("supervisor", task)
                tasks.save(tmp, task)
                loaded = tasks.load(tmp, task["id"])
                self.assertIsNotNone(loaded)
                self.assertTrue(tasks.whole(loaded))
                self.assertNotIn("supervisor", loaded)
                # policy computes an effective policy for a legacy task without mutating it
                before = dict(loaded)
                policy = supervisor.policy(cfg(), loaded, 200.0)
                self.assertEqual(policy["mode"], "suggest")
                self.assertEqual(loaded, before)

    def test_invalid_policy_fails_closed(self):
        # unknown global mode
        p = supervisor.policy(cfg(supervisor_mode="turbo"), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual((p["mode"], bool(p["reason"])), ("off", True))
        # unknown saved task mode
        p = supervisor.policy(cfg(), {"project_dir": "D:\\work", "supervisor": {"mode": "turbo"}}, 0.0)
        self.assertEqual((p["mode"], bool(p["reason"])), ("off", True))
        # booleans as counts, negative and NaN counters, malformed settings never grant extra allowance
        bad = {"mode": "auto", "auto_steps": True, "retries": {1: "x"}, "usd": -1, "work_usd": float("nan")}
        p = supervisor.policy(cfg(), {"project_dir": "D:\\work", "supervisor": bad}, 0.0)
        self.assertEqual(p["mode"], "off")
        self.assertTrue(p["reason"])
        p = supervisor.policy(cfg(supervisor_max_auto_steps=float("inf")), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual(p["mode"], "off")
        p = supervisor.policy(cfg(supervisor_model="opus"), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual((p["mode"], bool(p["reason"])), ("off", True))
        self.assertEqual(p["settings"]["supervisor_model"], "haiku")
        p = supervisor.policy(cfg(supervisor_stuck_model="fable"), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual(p["mode"], "off")
        # zero limits disable the allowance, never make it unlimited
        p = supervisor.policy(cfg(supervisor_max_auto_steps=0, supervisor_work_usd=0), {"project_dir": "D:\\work"}, 0.0)
        self.assertEqual((p["auto_steps_left"], p["work_usd_left"]), (0, 0.0))


class AuditTest(unittest.TestCase):
    def test_event_and_request_ids_are_stable(self):
        line = {"ts": 100.0, "step": 2, "session": "s1", "from": "running", "to": "done", "why": "x", "cost": 1.0}
        self.assertEqual(supervisor.event_id(line), supervisor.event_id(dict(line, cost=9.0)))
        self.assertNotEqual(supervisor.event_id(line), supervisor.event_id(dict(line, step=3)))
        self.assertNotEqual(supervisor.event_id(line), supervisor.event_id(dict(line, why="y")))
        one = supervisor.request_id("task-1", 1)
        self.assertEqual(one, supervisor.request_id("task-1", 1))
        self.assertRegex(one, r"[0-9a-f-]{16,36}")
        self.assertNotEqual(one, supervisor.request_id("task-1", 2))
        self.assertNotEqual(one, supervisor.request_id("task-2", 1))

    def test_append_is_masked_and_fold_counts_cost_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tid = "20260101-000000-abcd"
            claim = {"ts": 100.0, "wake": 1, "phase": "claimed", "events": ["e1"], "day": "2026-01-01",
                     "reserved": 0.1, "token": "sk-secret12345678"}
            result = {"ts": 101.0, "wake": 1, "phase": "result", "cost": 0.03, "day": "2026-01-01", "decision": {}}
            supervisor.append_log(tmp, tid, claim)
            supervisor.append_log(tmp, tid, result)
            supervisor.append_log(tmp, tid, {"ts": 102.0, "wake": 1, "phase": "dispatching"})
            supervisor.append_log(tmp, tid, {"ts": 103.0, "wake": 1, "phase": "outcome"})
            supervisor.append_log(tmp, tid, dict(result))  # a repeated result never multiplies spend
            records = supervisor.read_log(tmp, tid)
            folded = supervisor.fold_log(records)
            self.assertEqual(folded["cost"], 0.03)
            self.assertEqual(folded["days"]["2026-01-01"]["cost"], 0.03)
            self.assertEqual(folded["wakes"][1]["events"], ["e1"])
            raw = (Path(tmp) / "tasks" / tid / "supervisor.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("sk-secret12345678", raw)
            self.assertIn("***", raw)
            with self.assertRaises(ValueError):
                supervisor.append_log(tmp, "../x", claim)

    def test_corrupt_or_truncated_log_is_a_visible_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            tid = "20260101-000000-abcd"
            folder = Path(tmp) / "tasks" / tid
            folder.mkdir(parents=True)
            (folder / "supervisor.jsonl").write_text(
                '{"wake": 1, "phase": "result", "cost": 0.01}\nnot json\n{"wake": 2, "phase": "claimed", "events": ["e2"]}\n',
                encoding="utf-8")
            records = supervisor.read_log(tmp, tid)
            self.assertTrue(any(r.get("corrupt") for r in records))
            self.assertTrue(supervisor.fold_log(records)["uncertain"])
            self.assertEqual(supervisor.read_log(tmp, "20260101-000000-ffff"), [])  # missing file is valid empty

if __name__ == "__main__":
    unittest.main()
