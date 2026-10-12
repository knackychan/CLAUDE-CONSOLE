import base64
import copy
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from console import attach, events, paths, runs

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]


def wait_for(check, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if check():
            return True
        time.sleep(0.1)
    return False


class RunsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        self.mgr = runs.RunManager(copy.deepcopy(paths.DEFAULTS), self.folder, FAKE)

    def tearDown(self):
        for proc in list(self.mgr.live.values()):
            proc.kill()
        end = time.time() + 10
        while self.mgr.live and time.time() < end:  # let the watcher threads finish
            time.sleep(0.05)
        self.tmp.cleanup()

    def log(self):
        return events.LogReader(self.folder).read_new()

    def ended(self, sid):
        return [r for r in self.log() if r["event"] == "run_ended" and r["session_id"] == sid]

    def test_run_writes_stream_and_events(self):
        sid = self.mgr.start(str(self.project), "fix add", "sonnet", "low", title="Fix add", route="r", prep="p1")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        started = [r for r in self.log() if r["event"] == "run_started"][0]
        self.assertEqual((started["session_id"], started["title"], started["prep"]), (sid, "Fix add", "p1"))
        self.assertEqual((started["project"], started["project_dir"]), ("proj", str(self.project)))
        end = self.ended(sid)[0]
        self.assertEqual((end["subtype"], end["cost"], end["stopped"], end["interrupted"]),
                         ("success", 0.01, False, False))
        items = runs.chat(self.mgr.stream_path(sid), str(self.project))
        self.assertEqual([i["role"] for i in items], ["you", "claude", "tool", "result"])
        self.assertEqual(items[0]["text"], "fix add")
        self.assertIn("STOP: <question>", items[1]["text"])  # the footer reached claude
        self.assertEqual(items[2]["text"], "Read calc.py")
        self.assertFalse(self.mgr.is_live(sid))

    def test_attached_files_go_inline_and_only_their_summary_is_kept(self):
        files = attach.parse([{"name": "shot.png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\nPIXELS").decode()},
                              {"name": "notes.md", "data": base64.b64encode(b"# notes").decode()}])
        sid = self.mgr.start(str(self.project), "look", "sonnet", "low", files=files)
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        items = runs.chat(self.mgr.stream_path(sid), str(self.project))
        self.assertEqual(items[0]["files"], [{"name": "shot.png", "kind": "image", "bytes": 14},
                                             {"name": "notes.md", "kind": "text", "bytes": 7}])
        self.assertIn("+image +document", items[1]["text"])  # the fake claude got the blocks
        stream = self.mgr.stream_path(sid).read_text(encoding="utf-8")
        self.assertNotIn(files[0]["data"], stream)
        self.assertNotIn("# notes", stream)

    def test_chat_puts_files_claude_wrote_under_its_next_words(self):
        path = self.mgr.runs / "s1.jsonl"
        self.mgr.runs.mkdir(parents=True)
        write = lambda p: {"type": "tool_use", "name": "Write", "input": {"file_path": p, "content": "x"}}
        lines = [{"type": "cc_prompt", "ts": 1, "text": "draw it"},
                 {"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
                     write(str(self.project / "out" / "chart.png")), {"type": "text", "text": "Drew it."},
                     write(str(self.project / "log.txt"))]}},
                 {"type": "result", "subtype": "success", "total_cost_usd": 0.1, "num_turns": 1}]
        path.write_text("".join(json.dumps(d) + "\n" for d in lines), encoding="utf-8")
        items = runs.chat(path, str(self.project))
        self.assertEqual([(i["role"], i["text"]) for i in items if i["role"] != "tool"][:3],
                         [("you", "draw it"), ("claude", "Drew it."), ("claude", "")])
        claude = [i for i in items if i["role"] == "claude"]
        self.assertEqual([f["name"] for f in claude[0]["files"]], ["out/chart.png"])
        self.assertEqual((claude[0]["files"][0]["kind"], claude[1]["files"][0]["name"]), ("image", "log.txt"))

    def test_stop_sends_an_interrupt(self):
        sid = self.mgr.start(str(self.project), "SLOW task", "sonnet", "low")
        self.assertTrue(wait_for(lambda: "echo: SLOW" in self.mgr.stream_path(sid).read_text(encoding="utf-8")))
        self.assertEqual(self.mgr.stop(sid), "interrupt")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        self.assertEqual((self.ended(sid)[0]["stopped"], self.ended(sid)[0]["interrupted"]), (True, False))
        self.assertIn("stopped", [i["text"] for i in runs.chat(self.mgr.stream_path(sid))])
        self.assertEqual(self.mgr.stop(sid), "not running")

    def test_resume_keeps_the_session(self):
        sid = self.mgr.start(str(self.project), "first", "sonnet", "low")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        self.assertEqual(self.mgr.start(str(self.project), "second", "sonnet", "low", resume=sid), sid)
        self.assertTrue(wait_for(lambda: len(self.ended(sid)) == 2))
        texts = [i["text"] for i in runs.chat(self.mgr.stream_path(sid)) if i["role"] == "you"]
        self.assertEqual(texts, ["first", "second"])

    def test_fork_starts_a_window_copy(self):
        sid = self.mgr.start(str(self.project), "/session-handoff", "sonnet", "low", fork="vscode-1",
                             title="↳ fix", kind="handoff", extra={"escalated": "x"})
        self.assertNotEqual(sid, "vscode-1")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        started = [r for r in self.log() if r["event"] == "run_started"][0]
        self.assertEqual((started["kind"], started["forked_from"], started["escalated"]),
                         ("handoff", "vscode-1", "x"))
        claude = [i["text"] for i in runs.chat(self.mgr.stream_path(sid)) if i["role"] == "claude"]
        self.assertEqual(claude, ["echo: /session-handoff"])  # no STOP footer after a /skill
        self.assertEqual(self.mgr.meta(sid)["model"], "sonnet")

    def test_reconcile_marks_a_cut_run_interrupted(self):
        self.mgr.runs.mkdir(parents=True)
        self.mgr.stream_path("dead").write_text('{"type":"cc_prompt","text":"x"}\n', encoding="utf-8")
        self.mgr._save_meta({"session_id": "dead", "pid": 4, "cwd": str(self.project), "offset": 0,
                             "model": "sonnet", "effort": "low", "ended": None})
        with mock.patch.object(runs.claude_cli, "pid_alive", return_value=False):
            self.assertEqual(self.mgr.reconcile(), 1)
            self.assertEqual(self.mgr.reconcile(), 0)
        self.assertEqual(self.ended("dead")[0]["interrupted"], True)

    def test_result_record_lists_denials(self):
        rec = runs.result_record("s", {"subtype": "success", "total_cost_usd": 0.2, "permission_denials": [
            {"tool_name": "Bash", "tool_input": {"command": "git push --force"}}]}, 0, False)
        self.assertEqual(rec["denials"], [{"tool": "Bash", "what": "git push --force"}])
        self.assertTrue(runs.result_record("s", None, None, False)["interrupted"])

    def test_prune_old_run_files(self):
        self.mgr.runs.mkdir(parents=True)
        old = self.mgr.stream_path("old")
        old.write_text("", encoding="utf-8")
        os.utime(old, (1, 1))
        self.mgr.stream_path("new").write_text("", encoding="utf-8")
        self.assertEqual(runs.prune(self.folder, 14), ["runs/old.jsonl"])


if __name__ == "__main__":
    unittest.main()
