"""Plan 44 backend: the supervisor's policy, audit, digest and bounded pass (pure tests)."""
import math
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
