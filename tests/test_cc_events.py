import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cc_events
from tests import fixtures


def assistant_line(model="claude-sonnet-5-5", inp=10, read=1000, create=90, side=False, entry="claude-vscode"):
    return json.dumps({"type": "assistant", "isSidechain": side, "entrypoint": entry,
                       "message": {"model": model, "usage": {"input_tokens": inp,
                                   "cache_read_input_tokens": read,
                                   "cache_creation_input_tokens": create}}})


class TranscriptTailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "t.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_last_main_assistant_line(self):
        self.path.write_text("\n".join([
            assistant_line(read=5),
            json.dumps({"type": "user"}),
            assistant_line(model="claude-haiku-5-5", read=9999, side=True),
            assistant_line(read=2000),
            "{broken",
        ]) + "\n", encoding="utf-8")
        out = cc_events.transcript_tail(self.path)
        self.assertEqual(out, {"model": "claude-sonnet-5-5", "context_tokens": 2100,
                               "entrypoint": "claude-vscode"})

    def test_sidechain_for_agent_transcripts(self):
        self.path.write_text(assistant_line(model="claude-haiku-5-5", side=True) + "\n", encoding="utf-8")
        self.assertEqual(cc_events.transcript_tail(self.path, sidechain=True)["model"], "claude-haiku-5-5")

    def test_missing_file_gives_empty(self):
        self.assertEqual(cc_events.transcript_tail(self.path), {})
        self.assertEqual(cc_events.transcript_tail(None), {})


class BuildRecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "myrepo"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "src").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def base(self, event, **extra):
        data = {"hook_event_name": event, "session_id": "s1", "cwd": str(self.repo / "src"),
                "permission_mode": "auto", "effort": {"level": "medium"}}
        data.update(extra)
        return data

    def test_project_is_git_root(self):
        rec = cc_events.build_record(self.base("SessionStart", source="startup"), now=100.0)
        self.assertEqual(rec["project"], "myrepo")
        self.assertEqual(rec["project_dir"], str(self.repo))
        self.assertEqual(rec["effort"], "medium")
        self.assertEqual(rec["ts"], 100.0)
        self.assertNotIn("agent_id", rec)

    def test_prompt_is_masked_and_clipped(self):
        rec = cc_events.build_record(self.base("UserPromptSubmit", prompt="token=abc " + "y" * 300))
        self.assertTrue(rec["prompt"].startswith("token=***"))
        self.assertEqual(len(rec["prompt"]), 120)

    def test_injected_blocks_are_not_the_prompt(self):
        prompt = ('<browser_instruction># Claude in Chrome\n' + "x" * 500 + '</browser_instruction>\n'
                  '<pasted_content id="1">Project: D:/x</pasted_content>')
        rec = cc_events.build_record(self.base("UserPromptSubmit", prompt=prompt))
        self.assertEqual(rec["prompt"], '<pasted_content id="1">Project: D:/x</pasted_content>')
        rec = cc_events.build_record(self.base("UserPromptSubmit",
                                               prompt="<task-notification><task-id>b1</task-id></task-notification>"))
        self.assertEqual(rec.get("prompt", ""), "")  # empty fields are left out of the line

    def test_pre_tool_use_has_summary_not_input(self):
        rec = cc_events.build_record(self.base("PreToolUse", tool_name="Read", tool_use_id="t1",
                                               tool_input={"file_path": str(self.repo / "src" / "a.py")},
                                               agent_id="ag1", agent_type="Explore"))
        self.assertEqual((rec["tool"], rec["what"], rec["agent_id"]), ("Read", "a.py", "ag1"))
        self.assertNotIn("tool_input", rec)

    def test_stop_reads_route_and_stop_question(self):
        msg = "Done.\n`Route: mechanical, low effort, cavecrew-builder on sonnet`\nSTOP: how many retries?"
        rec = cc_events.build_record(self.base("Stop", last_assistant_message=msg, transcript_path=""))
        self.assertEqual(rec["route"], "mechanical, low effort, cavecrew-builder on sonnet")
        self.assertEqual(rec["stop_question"], "how many retries?")

    def test_stop_keeps_the_start_of_the_reply_masked(self):
        rec = cc_events.build_record(self.base("Stop", transcript_path="",
                                               last_assistant_message="## Done\n\nThe retry is in token=abc123 now. " + "x" * 200))
        self.assertTrue(rec["reply"].startswith("Done The retry is in token=*** now."))
        self.assertEqual(len(rec["reply"]), 120)
        self.assertNotIn("reply", cc_events.build_record(self.base("Stop", transcript_path="")))

    def test_stop_none_is_no_question(self):
        for answer in ("none", "None.", "n/a", "-"):
            rec = cc_events.build_record(self.base("Stop", last_assistant_message=f"Done.\nSTOP: {answer}"))
            self.assertNotIn("stop_question", rec, answer)

    def test_verdict_from_stop_and_subagent_stop(self):
        msg = ("Checked.\nVERDICT: FAIL\nchecks: py -m unittest -> 1 failed\n"
               "failing: tests/test_calc.py:9 - AssertionError: 3 != 4")
        rec = cc_events.build_record(self.base("Stop", transcript_path="", last_assistant_message=msg))
        self.assertEqual((rec["verdict"], rec["verdict_detail"]),
                         ("FAIL", "tests/test_calc.py:9 - AssertionError: 3 != 4"))
        rec = cc_events.build_record(self.base("SubagentStop", agent_id="a1", agent_type="verifier",
                                               last_assistant_message="**VERDICT: PASS**\nchecks: ok"))
        self.assertEqual(rec["verdict"], "PASS")
        self.assertNotIn("verdict_detail", rec)
        rec = cc_events.build_record(self.base("Stop", last_assistant_message="VERDICT: FAIL token=abc broke"))
        self.assertEqual(rec["verdict_detail"], "token=*** broke")
        self.assertNotIn("verdict", cc_events.build_record(self.base("Stop", last_assistant_message="all good")))

    def test_instructions_loaded_measures_the_file(self):
        rules = self.repo / "CLAUDE.md"
        rules.write_bytes(b"# Rules\n" + b"- one rule\n" * 4 + b"last line")
        rec = cc_events.build_record(self.base("InstructionsLoaded", file_path=str(rules),
                                               memory_type="Project", load_reason="session_start"))
        self.assertEqual((rec["file"], rec["lines"], rec["bytes"], rec["scope"], rec["load_reason"]),
                         ("CLAUDE.md", 6, 61, "Project", "session_start"))
        mine = Path(self.tmp.name) / ".claude" / "CLAUDE.md"
        mine.parent.mkdir()
        mine.write_bytes(b"one\ntwo\n")
        with mock.patch.object(Path, "home", return_value=Path(self.tmp.name)):
            rec = cc_events.build_record(self.base("InstructionsLoaded", file_path=str(mine), memory_type="User"))
        self.assertEqual((rec["file"], rec["lines"], rec["bytes"]), ("~/.claude/CLAUDE.md", 2, 8))
        rec = cc_events.build_record(self.base("InstructionsLoaded", file_path=str(self.repo / "gone.md")))
        self.assertEqual(rec["file"], "gone.md")
        self.assertNotIn("lines", rec)

    def test_turn_events_carry_the_transcript_path(self):
        for event in ("SessionStart", "UserPromptSubmit", "Stop"):
            rec = cc_events.build_record(self.base(event, transcript_path="C:/t/s1.jsonl"))
            self.assertEqual(rec["transcript_path"], "C:/t/s1.jsonl", event)
        rec = cc_events.build_record(self.base("PreToolUse", tool_name="Read", transcript_path="C:/t/s1.jsonl"))
        self.assertNotIn("transcript_path", rec)

    def test_permission_denied_keeps_reason(self):
        rec = cc_events.build_record(self.base("PermissionDenied", tool_name="Bash",
                                               tool_input={"command": "git push"}, reason="[Push]"))
        self.assertEqual((rec["what"], rec["reason"]), ("git push", "[Push]"))

    def test_permission_denied_reason_is_masked(self):
        """Plan 34 F3: the reason can quote the command."""
        rec = cc_events.build_record(self.base("PermissionDenied", tool_name="Bash", tool_input={"command": "x"},
                                               reason="denied: OPENAI_API_KEY=" + "test-only-value in command"))
        self.assertEqual(rec["reason"], "denied: OPENAI_API_KEY=*** in command")


class OtherHarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.repo = self.dir / "myrepo"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "src").mkdir()

    def base(self, event, **extra):
        data = {"hook_event_name": event, "session_id": "s1", "cwd": str(self.repo / "src")}
        data.update(extra)
        return data

    def test_harness_arg(self):
        self.assertEqual(cc_events.harness_arg([]), "claude")
        self.assertEqual(cc_events.harness_arg(["--harness"]), "claude")
        self.assertEqual(cc_events.harness_arg(["--harness", "x"]), "claude")
        self.assertEqual(cc_events.harness_arg(["--harness", "codex"]), "codex")
        self.assertEqual(cc_events.harness_arg(["--harness", "opencode", "x"]), "opencode")

    def test_claude_records_unchanged(self):
        cases = [self.base("SessionStart", source="startup", model="claude-sonnet-5-5"),
                 self.base("UserPromptSubmit", prompt="hello"),
                 self.base("PreToolUse", tool_name="Read", tool_input={"file_path": "a.py"}),
                 self.base("SubagentStop", agent_id="a1"),
                 self.base("Stop", last_assistant_message="done"),
                 self.base("StopFailure", error="boom"),
                 self.base("PostCompact", trigger="auto"),
                 self.base("SessionEnd", reason="other"),
                 self.base("Interrupt", source="ctrl-c")]
        for data in cases:
            self.assertNotIn("harness", cc_events.build_record(data, harness="claude"), data["hook_event_name"])
            self.assertNotIn("harness", cc_events.build_record(data), data["hook_event_name"])

    def test_codex_tool_map(self):
        self.assertEqual(cc_events.map_tool("codex", "exec_command", {"cmd": ["git", "status"]}),
                         ("Bash", {"command": "git status"}))
        patch = "*** Begin Patch\n*** Update File: " + str(self.repo / "src" / "a.py") + "\n@@\n-x\n+y\n"
        rec = cc_events.build_record(self.base("PreToolUse", tool_name="apply_patch", tool_input={"input": patch}),
                                     harness="codex")
        self.assertEqual((rec["tool"], rec["what"]), ("Edit", "a.py"))
        rec = cc_events.build_record(self.base("PreToolUse", tool_name="mystery", tool_input={"a": 1}),
                                     harness="codex")
        self.assertEqual((rec["tool"], rec.get("what", "")), ("mystery", ""))
        self.assertEqual(rec["harness"], "codex")

    def test_opencode_and_cmd_tool_map(self):
        self.assertEqual(cc_events.map_tool("opencode", "read", {"filePath": "src/a.py"}),
                         ("Read", {"file_path": "src/a.py"}))
        self.assertEqual(cc_events.map_tool("cmd", "edit_file", {"file_path": "a.py"}), ("Edit", {"file_path": "a.py"}))
        rec = cc_events.build_record(self.base("PreToolUse", tool_name="read_directory", tool_input={"path": "src"}),
                                     harness="cmd")
        self.assertEqual((rec["tool"], rec["what"]), ("Glob", "src"))

    def test_opencode_stop_as_the_plugin_sends_it(self):
        data = self.base("Stop", last_assistant_message="done", entrypoint="cli",
                         model="opencode-go/deepseek-v4.1-flash", context_tokens=10361,
                         tokens={"input": 171, "output": 40, "cache_read": 20480})
        rec = cc_events.build_record(data, harness="opencode")
        self.assertEqual((rec["model"], rec["context_tokens"], rec["entrypoint"]),
                         ("opencode-go/deepseek-v4.1-flash", 10361, "cli"))
        self.assertEqual(rec["tokens"], {"input": 171, "output": 40, "cache_read": 20480})

    def test_console_sid_rewrite(self):
        data = self.base("UserPromptSubmit", prompt="hello")
        rec = cc_events.build_record(data, harness="codex", env={"CC_CONSOLE_SID": "c1"})
        self.assertEqual((rec["session_id"], rec["harness_session"]), ("c1", "s1"))
        rec = cc_events.build_record(data, harness="claude", env={"CC_CONSOLE_SID": "c1"})
        self.assertEqual(rec["session_id"], "s1")
        self.assertNotIn("harness_session", rec)
        self.assertNotIn("harness", rec)

    def test_ide_context_stripped(self):
        prompt = "# Context from my IDE setup:\n\n## Active file: a.py\n\n## My request:\nfix it"
        self.assertEqual(cc_events.strip_ide_context(prompt), "fix it")
        self.assertEqual(cc_events.strip_ide_context("plain"), "plain")
        rec = cc_events.build_record(self.base("UserPromptSubmit", prompt=prompt), harness="codex")
        self.assertEqual(rec["prompt"], "fix it")

    def test_codex_tail(self):
        path = fixtures.codex_rollout(self.dir / "rollout.jsonl")
        self.assertEqual(cc_events.codex_tail(path),
                         {"model": "gpt-6-astra", "effort": "medium", "context_tokens": 1200,
                          "tokens": {"input": 1100, "output": 80, "cache_read": 1100}, "entrypoint": "vscode"})
        rec = cc_events.build_record(self.base("Stop", transcript_path=str(path), model="gpt-6-astra"),
                                     harness="codex")
        self.assertEqual((rec["model"], rec["context_tokens"], rec["tokens"]["input"]),
                         ("gpt-6-astra", 1200, 1100))
        self.assertEqual(rec["entrypoint"], "vscode")
        self.assertEqual(rec["effort"], "medium")
        self.assertNotIn("reply", rec)  # Codex sends last_assistant_message; the tail has no reply_text key

    def test_cmd_tail(self):
        path = fixtures.cmd_transcript(self.dir / "c1.jsonl")
        self.assertEqual(cc_events.cmd_tail(path),
                         {"model": "m3", "effort": "high", "context_tokens": 3000,
                          "tokens": {"input": 1000, "output": 300, "cache_read": 4000},
                          "reply_text": "# Report\n\nDone.", "prompt": "audit the project",
                          "entrypoint": "interactive"})
        rec = cc_events.build_record(self.base("Stop", transcript_path=str(path)), harness="cmd")
        self.assertEqual(rec["prompt"], "audit the project")
        self.assertEqual(rec["reply"], "Report Done.")  # clipped to one line
        self.assertEqual(rec["model"], "m3")

    def test_tails_never_raise(self):
        missing = self.dir / "none.jsonl"
        junk = self.dir / "junk.jsonl"
        junk.write_bytes(b"\x00\x01\xff\xfe not json at all\n" * 20)
        empty = self.dir / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        for path in (missing, junk, empty, None):
            for fn in (cc_events.codex_tail, cc_events.cmd_tail):
                self.assertEqual(fn(path), {}, f"{fn.__name__} {path}")

    def test_main_harness_arg_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": tmp}), \
                mock.patch.object(sys, "argv", ["cc_events.py", "--harness", "codex"]), \
                mock.patch("sys.stdin", io.TextIOWrapper(io.BytesIO(b"not json"))):
            self.assertEqual(cc_events.main(), 0)


class MainTest(unittest.TestCase):
    def test_main_appends_one_line_and_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": tmp}):
            payload = json.dumps({"hook_event_name": "SessionEnd", "session_id": "s9", "reason": "other"})
            with mock.patch("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode()))):
                self.assertEqual(cc_events.main(), 0)
            with mock.patch("sys.stdin", io.TextIOWrapper(io.BytesIO(b"not json"))):
                self.assertEqual(cc_events.main(), 0)
            files = list(Path(tmp).glob("events-*.jsonl"))
            self.assertEqual(len(files), 1)
            lines = files[0].read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["reason"], "other")
            self.assertTrue((Path(tmp) / "hook-errors.log").exists())


class ImportFailureTest(unittest.TestCase):
    def test_a_broken_console_package_still_exits_0(self):
        """Plan 34 F1: the import of console sits inside the never-raise rule."""
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(Path(cc_events.__file__), Path(tmp) / "cc_events.py")
            (Path(tmp) / "console").mkdir()
            (Path(tmp) / "console" / "__init__.py").write_text("raise ImportError('broken on purpose')\n",
                                                                encoding="utf-8")
            payload = json.dumps({"hook_event_name": "SessionEnd", "session_id": "s9"}).encode()
            proc = subprocess.run([sys.executable, str(Path(tmp) / "cc_events.py")], input=payload,
                                  capture_output=True, timeout=30,
                                  env=dict(os.environ, CC_CONSOLE_HOME=str(Path(tmp) / "home")))
            self.assertEqual((proc.returncode, proc.stderr), (0, b""))
            self.assertFalse((Path(tmp) / "home").exists())


if __name__ == "__main__":
    unittest.main()
