import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from console import claude_cli


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

    def test_model_alias(self):
        names = ("claude-sonnet-5-5", "claude-haiku-4-5-20251001", "opus", "gpt-9", None)
        self.assertEqual([claude_cli.model_alias(m) for m in names], ["sonnet", "haiku", "opus", "", ""])

    def test_prep_command_is_read_only_and_hookless(self):
        cmd = claude_cli.prep_command(["claude.exe"], "haiku", {"type": "object"})
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Read,Grep,Glob")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(json.loads(cmd[cmd.index("--settings") + 1]), {"disableAllHooks": True})
        self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1]), {"type": "object"})

    def test_messages(self):
        self.assertEqual(json.loads(claude_cli.user_message("hé")),
                         {"type": "user", "message": {"role": "user", "content": "hé"}})
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

    def test_pid_alive(self):
        self.assertTrue(claude_cli.pid_alive(os.getpid()))
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        self.assertFalse(claude_cli.pid_alive(proc.pid))
        self.assertFalse(claude_cli.pid_alive(None))


if __name__ == "__main__":
    unittest.main()
