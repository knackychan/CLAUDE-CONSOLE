import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from console import claude_cli, paths


class CommandTest(unittest.TestCase):
    def test_run_command_new_and_resume(self):
        new = claude_cli.run_command(["claude.exe"], "sonnet", "medium", "abc", name="Fix add")
        self.assertEqual(new[:2], ["claude.exe", "-p"])
        for flag, value in (("--model", "sonnet"), ("--effort", "medium"), ("--permission-mode", "auto"),
                            ("--permission-prompts", "none"), ("--input-format", "stream-json"),
                            ("--output-format", "stream-json"), ("--session-id", "abc"), ("--name", "Fix add")):
            self.assertEqual(new[new.index(flag) + 1], value, flag)
        self.assertIn("--verbose", new)
        resumed = claude_cli.run_command(["claude.exe"], "sonnet", "medium", "abc", resume=True, name="x")
        self.assertEqual(resumed[resumed.index("--resume") + 1], "abc")
        self.assertNotIn("--session-id", resumed)
        self.assertNotIn("--name", resumed)

    def test_run_command_fork(self):
        cmd = claude_cli.run_command(["claude.exe"], "sonnet", "low", "new", name="↳ x", fork="old")
        i = cmd.index("--resume")
        self.assertEqual(cmd[i:i + 5], ["--resume", "old", "--fork-session", "--session-id", "new"])
        self.assertEqual(cmd[cmd.index("--name") + 1], "↳ x")

    def test_step_command_has_no_agent_tool(self):
        cmd = claude_cli.run_command(["claude.exe"], "haiku", "low", "abc", disallow=("Agent",),
                                     tools="Read,Grep,Glob", budget=3, max_turns=12)
        for flag, value in (("--disallowedTools", "Agent"), ("--tools", "Read,Grep,Glob"),
                            ("--max-budget-usd", "3.00"), ("--max-turns", "12")):
            self.assertEqual(cmd[cmd.index(flag) + 1], value, flag)
        self.assertLess(cmd.index("--verbose"), cmd.index("--disallowedTools"))
        self.assertLess(cmd.index("--max-turns"), cmd.index("--session-id"))
        plain = claude_cli.run_command(["claude.exe"], "haiku", "low", "abc")
        for flag in ("--disallowedTools", "--tools", "--max-budget-usd", "--max-turns"):
            self.assertNotIn(flag, plain)
        two = claude_cli.run_command(["claude.exe"], "haiku", "low", "abc", disallow=("Agent", "Edit"))
        self.assertEqual(two[two.index("--disallowedTools") + 1], "Agent,Edit")

    def test_step_command_loads_no_mcp_server(self):
        cmd = claude_cli.run_command(["claude.exe"], "haiku", "low", "abc", tools="Read,Grep,Glob", strict_mcp=True)
        self.assertIn("--strict-mcp-config", cmd)
        self.assertNotIn("--mcp-config", cmd)  # strict with no config: no server at all
        self.assertLess(cmd.index("--tools"), cmd.index("--strict-mcp-config"))
        self.assertNotIn("--strict-mcp-config", claude_cli.run_command(["claude.exe"], "haiku", "low", "abc"))

    def test_tier_of_and_known_model(self):
        self.assertEqual([claude_cli.tier_of(m) for m in ("claude-opus-4-6", "opus", "gpt")], ["opus", "opus", ""])
        cfg = copy.deepcopy(paths.DEFAULTS)
        self.assertTrue(claude_cli.known_model(cfg, "claude-haiku-4-5"))
        self.assertFalse(claude_cli.known_model(cfg, "claude-haiku-3"))
        self.assertTrue(claude_cli.known_model(cfg, "sonnet"))

    def test_model_alias(self):
        names = ("claude-sonnet-5-5", "claude-haiku-4-5-20251001", "opus", "gpt-9", None)
        self.assertEqual([claude_cli.model_alias(m) for m in names], ["sonnet", "haiku", "opus", "", ""])

    def test_prep_command_is_read_only_and_hookless(self):
        cmd = claude_cli.prep_command(["claude.exe"], "haiku", {"type": "object"})
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Read,Grep,Glob")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(json.loads(cmd[cmd.index("--settings") + 1]), {"disableAllHooks": True})
        self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1]), {"type": "object"})

    def test_brief_command_has_no_tools_and_six_turns(self):
        cmd = claude_cli.brief_command(["claude.exe"], "haiku", {"type": "object"})
        self.assertEqual(cmd[:2], ["claude.exe", "-p"])
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "6")  # the answer, plus schema re-prompts (3 was hit live)
        self.assertEqual(cmd[cmd.index("--model") + 1], "haiku")
        self.assertEqual(cmd[cmd.index("--effort") + 1], "low")
        self.assertEqual(json.loads(cmd[cmd.index("--settings") + 1]), {"disableAllHooks": True})
        self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1]), {"type": "object"})
        for flag in ("--no-session-persistence", "--disable-slash-commands", "--strict-mcp-config"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd.count("--tools"), 1)

    def test_messages(self):
        self.assertEqual(json.loads(claude_cli.user_message("hé")),
                         {"type": "user", "message": {"role": "user", "content": "hé"}})
        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBO"}}
        self.assertEqual(json.loads(claude_cli.user_message("see", [image]))["message"]["content"],
                         [{"type": "text", "text": "see"}, image])
        self.assertEqual(json.loads(claude_cli.interrupt_message("r1"))["request"], {"subtype": "interrupt"})

    def test_child_env_drops_session_variables_only(self):
        env = {"PATH": "x", "CLAUDE_CODE_ENTRYPOINT": "claude-vscode", "CLAUDECODE": "1",
               "CLAUDE_CONFIG_DIR": "keep"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(claude_cli.child_env(), {"PATH": "x", "CLAUDE_CONFIG_DIR": "keep"})

    def test_terminal_keeps_the_run_model(self):
        self.assertEqual(claude_cli.terminal_command(["claude.exe"], "abc", "sonnet", "low"),
                         ["claude.exe", "--resume", "abc", "--model", "sonnet", "--effort", "low"])
        self.assertEqual(claude_cli.terminal_command(["claude.exe"], "abc"), ["claude.exe", "--resume", "abc"])

    def test_find_exe_prefers_config(self):
        self.assertEqual(claude_cli.find_exe({"claude_exe": r"C:\x\claude.exe"}), r"C:\x\claude.exe")

    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_git_status_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(claude_cli.git_status(tmp), [])  # not a repo
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            Path(tmp, "a.txt").write_text("x", encoding="utf-8")
            self.assertEqual(claude_cli.git_status(tmp), ["?? a.txt"])
        self.assertEqual(claude_cli.git_status(os.path.join(tmp, "gone")), [])

    def test_pid_alive(self):
        self.assertTrue(claude_cli.pid_alive(os.getpid()))
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        self.assertFalse(claude_cli.pid_alive(proc.pid))
        self.assertFalse(claude_cli.pid_alive(None))

    def test_run_alive_refuses_a_recycled_pid(self):
        """Plan 34 F4: a process born after its run's start (plus the slack) holds a recycled pid."""
        with mock.patch.object(claude_cli, "pid_alive", return_value=True), \
                mock.patch.object(claude_cli, "process_started", return_value=100.0):
            self.assertTrue(claude_cli.run_alive(5, 99.0))
            self.assertFalse(claude_cli.run_alive(5, 50.0))
            self.assertTrue(claude_cli.run_alive(5, None))  # an old meta without "started"
        with mock.patch.object(claude_cli, "pid_alive", return_value=True), \
                mock.patch.object(claude_cli, "process_started", return_value=None):
            self.assertTrue(claude_cli.run_alive(5, 50.0))  # creation time unknown: pid_alive alone
        with mock.patch.object(claude_cli, "pid_alive", return_value=False):
            self.assertFalse(claude_cli.run_alive(5, 99.0))

    @unittest.skipUnless(os.name == "nt", "the creation time is read on Windows only")
    def test_process_started_reads_this_process(self):
        born = claude_cli.process_started(os.getpid())
        self.assertIsNotNone(born)
        self.assertLess(born, time.time())
        self.assertGreater(born, time.time() - 86400)
        self.assertIsNone(claude_cli.process_started(None))


@unittest.skipUnless(os.name == "nt", "job objects are Windows only")
class ServiceJobTest(unittest.TestCase):
    def test_a_run_joins_the_service_job_and_a_child_joins_too(self):
        import ctypes
        from ctypes import wintypes
        child = subprocess.Popen([sys.executable, "-c",
                                  "import subprocess,sys,time; "
                                  "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                                  "time.sleep(30)"],
                                 creationflags=claude_cli.NO_WINDOW)
        self.addCleanup(lambda: (claude_cli.kill_tree(child.pid), child.wait()))
        self.assertTrue(claude_cli.join_service_job(child.pid))
        k = ctypes.windll.kernel32
        k.OpenProcess.restype = ctypes.c_void_p
        k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        handle = k.OpenProcess(0x1000, False, child.pid)
        in_job = wintypes.BOOL()
        k.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)]
        self.assertTrue(k.IsProcessInJob(handle, None, ctypes.byref(in_job)))
        k.CloseHandle(handle)
        self.assertTrue(in_job.value)

    def test_the_child_ends_when_the_service_exits(self):
        # a service process that exits without cleaning up: its run must not stay behind as an orphan
        root = str(Path(__file__).resolve().parent.parent)
        service = ("import subprocess, sys; from console import claude_cli; "
                   "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
                   "creationflags=claude_cli.NO_WINDOW | claude_cli.BREAKAWAY); "
                   "claude_cli.join_service_job(c.pid); print(c.pid, flush=True)")
        out = subprocess.run([sys.executable, "-c", service], cwd=root, capture_output=True, text=True,
                             timeout=30, creationflags=claude_cli.NO_WINDOW)
        pid = int(out.stdout.strip().splitlines()[-1])
        for _ in range(50):  # the OS ends the job's members a moment after the service's handles close
            if not claude_cli.pid_alive(pid):
                break
            time.sleep(0.1)
        self.assertFalse(claude_cli.pid_alive(pid))


if __name__ == "__main__":
    unittest.main()
