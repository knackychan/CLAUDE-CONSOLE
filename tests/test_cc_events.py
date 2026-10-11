import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cc_events


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


if __name__ == "__main__":
    unittest.main()
