import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
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

    def test_brief_command_has_no_tools_and_one_turn(self):
        cmd = claude_cli.brief_command(["claude.exe"], "haiku", {"type": "object"})
        self.assertEqual(cmd[:2], ["claude.exe", "-p"])
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "1")
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


if __name__ == "__main__":
    unittest.main()
