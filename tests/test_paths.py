"""Plan 24 config keys in paths.DEFAULTS and the opus_max_turns fallback; plan 27 the config.json writers."""
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from console import paths


class PlanKeysTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": self.tmp})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_design_max_turns_replaces_the_opus_cap(self):
        cfg = paths.load_config()
        self.assertEqual((cfg["design_max_turns"], cfg["plan_max_kb"], cfg["plan_max_parts"]), (30, 100, 6))
        self.assertIs(cfg["plan_hold"], False)
        self.assertIs(cfg["replan_auto"], False)
        self.assertNotIn("opus_max_turns", cfg)
        (Path(self.tmp) / "config.json").write_text(json.dumps({"opus_max_turns": 15}), encoding="utf-8")
        cfg = paths.load_config()
        self.assertEqual(cfg["design_max_turns"], 15)
        self.assertNotIn("opus_max_turns", cfg)
        (Path(self.tmp) / "config.json").write_text(
            json.dumps({"opus_max_turns": 15, "design_max_turns": 40}), encoding="utf-8")
        self.assertEqual(paths.load_config()["design_max_turns"], 40)

    def test_opus_max_turns_is_read_once_then_dropped(self):
        """Plan 27 (G8, plan 24 D2): the service start moves the old key into design_max_turns and drops it."""
        path = Path(self.tmp) / "config.json"
        path.write_text(json.dumps({"opus_max_turns": 15, "projects": ["C:/x"], "user_name": ""}), encoding="utf-8")
        self.assertEqual(paths.ensure_config()["design_max_turns"], 15)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                         {"projects": ["C:/x"], "user_name": "", "design_max_turns": 15})
        self.assertEqual(paths.ensure_config()["design_max_turns"], 15)  # read from the new key from now on
        path.write_text(json.dumps({"opus_max_turns": 15, "design_max_turns": 40, "user_name": ""}), encoding="utf-8")
        self.assertEqual(paths.ensure_config()["design_max_turns"], 40)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"design_max_turns": 40, "user_name": ""})


class ConfigWriteTest(unittest.TestCase):
    """Plan 27 (K1): every read-modify-write of config.json holds paths.CONFIG_LOCK and its own temp file."""

    def test_concurrent_writers_all_land(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"projects": []}), encoding="utf-8")
            errors = []

            def write(n):
                try:
                    for i in range(15):
                        paths.set_config(folder, {f"k{n}_{i}": i})
                        if n == 0:
                            paths.set_setting(Path(folder), "handoff_auto", bool(i % 2))
                        elif n == 1:
                            paths.set_harness(Path(folder), "codex", bool(i % 2))
                        elif n == 2:
                            paths.add_project(Path(folder), os.path.join(folder, f"p{i}"))
                except Exception as exc:  # a lost race shows as an error or a missing key
                    errors.append(f"{type(exc).__name__}: {exc}")

            threads = [threading.Thread(target=write, args=(n,)) for n in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = [f"k{n}_{i}" for n in range(6) for i in range(15) if f"k{n}_{i}" not in data]
            self.assertEqual(missing, [])
            self.assertEqual(len(data["projects"]), 15)
            self.assertIs(data["handoff_auto"], False)
            self.assertIs(data["harnesses"]["codex"]["on"], False)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["config.json"])  # no temp file left

    def test_a_failed_replace_keeps_the_file_and_leaves_no_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"projects": ["C:/x"]}), encoding="utf-8")
            with mock.patch("console.paths.os.replace", side_effect=PermissionError(13, "Access is denied")):
                with self.assertRaises(OSError):
                    paths.set_config(folder, {"task_max_steps": 8})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"projects": ["C:/x"]})
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["config.json"])
            paths.set_config(folder, {"task_max_steps": 8})  # the lock was released
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["task_max_steps"], 8)


class SettingTest(unittest.TestCase):
    def test_plan_23_defaults(self):
        d = paths.DEFAULTS
        self.assertEqual((d["read_max_turns"], d["handoff_auto"]), (15, False))
        self.assertEqual(paths.SETTINGS, ("handoff_auto",))

    def test_set_setting_writes_one_key(self):
        with tempfile.TemporaryDirectory() as folder:
            paths.set_setting(Path(folder), "handoff_auto", True)  # no config.json yet: the defaults plus the key
            data = json.loads((Path(folder) / "config.json").read_text(encoding="utf-8"))
            self.assertIs(data["handoff_auto"], True)
            self.assertEqual(data["brief_max_words"], paths.DEFAULTS["brief_max_words"])
            data["projects"] = ["C:/x"]
            (Path(folder) / "config.json").write_text(json.dumps(data), encoding="utf-8")
            paths.set_setting(Path(folder), "handoff_auto", False)
            data = json.loads((Path(folder) / "config.json").read_text(encoding="utf-8"))
            self.assertEqual((data["handoff_auto"], data["projects"]), (False, ["C:/x"]))  # the rest stays
            self.assertFalse((Path(folder) / "config.json.tmp").exists())
            for key, value in (("brief_on", False), ("handoff_auto", "yes"), ("handoff_auto", 1)):
                with self.assertRaises(ValueError):
                    paths.set_setting(Path(folder), key, value)
            (Path(folder) / "config.json").write_text("{broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                paths.set_setting(Path(folder), "handoff_auto", True)
            self.assertEqual((Path(folder) / "config.json").read_text(encoding="utf-8"), "{broken")  # left as is


class NameTest(unittest.TestCase):
    """Plan 31: config `user_name`, filled once at the service start, read through paths.you."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": self.tmp})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_you_collapses_and_falls_back(self):
        self.assertEqual(paths.you({"user_name": "  Fred \n T.  "}), "Fred T.")
        self.assertEqual(paths.you({"user_name": ""}), "the user")
        self.assertEqual(paths.you({"user_name": ""}, start=True), "The user")
        self.assertEqual(paths.you({"user_name": 7}), "the user")
        self.assertEqual(paths.you({}), "the user")
        self.assertEqual(len(paths.you({"user_name": "x" * 200})), paths.NAME_MAX)
        self.assertEqual(paths.DEFAULTS["user_name"], "")

    def test_os_user_name_prefers_git_then_the_login_and_never_raises(self):
        git = mock.Mock(returncode=0, stdout=b"Fred Tms\n")
        with mock.patch("subprocess.run", return_value=git), mock.patch("getpass.getuser", return_value="ftms"):
            self.assertEqual(paths.os_user_name(), "Fred Tms")
        with mock.patch("subprocess.run", side_effect=OSError("no git")), \
                mock.patch("getpass.getuser", return_value="ftms"):
            self.assertEqual(paths.os_user_name(), "ftms")
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=1, stdout=b"")), \
                mock.patch("getpass.getuser", side_effect=KeyError("no login")):
            self.assertEqual(paths.os_user_name(), "")

    def test_the_first_start_fills_the_name_once(self):
        path = Path(self.tmp) / "config.json"
        with mock.patch.object(paths, "os_user_name", return_value="Fred"):
            self.assertEqual(paths.ensure_config()["user_name"], "Fred")  # a missing file
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["user_name"], "Fred")
        path.write_text(json.dumps({"projects": ["C:/x"]}), encoding="utf-8")  # a file from before plan 31
        with mock.patch.object(paths, "os_user_name", return_value="ftms"):
            self.assertEqual(paths.ensure_config()["user_name"], "ftms")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"projects": ["C:/x"], "user_name": "ftms"})
        path.write_text(json.dumps({"user_name": ""}), encoding="utf-8")  # cleared by hand: stays cleared
        with mock.patch.object(paths, "os_user_name", side_effect=AssertionError("not asked")):
            self.assertEqual(paths.ensure_config()["user_name"], "")
        path.write_text("{broken", encoding="utf-8")  # unreadable: left as is
        with mock.patch.object(paths, "os_user_name", side_effect=AssertionError("not asked")):
            paths.ensure_config()
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")


if __name__ == "__main__":
    unittest.main()
