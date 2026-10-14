import base64
import copy
import json
import os
import signal
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

from console import attach, claude_cli, events, harness, paths, runs, tasks

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
FAKE_CODEX = [sys.executable, str(Path(__file__).resolve().parent / "fake_codex.py")]
FAKE_CMD = [sys.executable, str(Path(__file__).resolve().parent / "fake_cmd.py")]


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

    def test_run_started_carries_task_and_step(self):
        sid = self.mgr.start(str(self.project), "step", "haiku", "low", extra={"task": "t1", "step": 2},
                             disallow=tasks.DISALLOW, tools="Read,Grep,Glob", budget=3, strict_mcp=True)
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        started = [r for r in self.log() if r["event"] == "run_started"][0]
        self.assertEqual((started["task"], started["step"]), ("t1", 2))
        limits = {"disallow": ["Agent"], "tools": "Read,Grep,Glob", "budget": 3, "max_turns": 0, "strict_mcp": True}
        self.assertEqual(self.mgr.meta(sid)["limits"], limits)
        self.assertEqual(len(self.ended(sid)), 1)  # the fake claude ran, whatever the flags
        with mock.patch.object(runs.claude_cli, "run_command", wraps=runs.claude_cli.run_command) as cmd:
            self.assertEqual(self.mgr.start(str(self.project), "retry", "haiku", "low", resume=sid), sid)
            self.assertTrue(wait_for(lambda: len(self.ended(sid)) == 2))
        self.assertEqual(self.mgr.meta(sid)["limits"], limits)
        kwargs = cmd.call_args.kwargs
        self.assertEqual((kwargs["disallow"], kwargs["tools"], kwargs["budget"], kwargs["max_turns"],
                          kwargs["strict_mcp"]), (("Agent",), "Read,Grep,Glob", 3, 0, True))  # a retry keeps them
        plain = self.mgr.start(str(self.project), "plain", "sonnet", "low")  # no limits given: none kept
        self.assertTrue(wait_for(lambda: self.ended(plain)))
        self.assertEqual(self.mgr.meta(plain)["limits"],
                         {"disallow": [], "tools": "", "budget": 0.0, "max_turns": 0, "strict_mcp": False})

    def test_forget_deletes_an_ended_run_only(self):
        sid = self.mgr.start(str(self.project), "first", "sonnet", "low")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        size = self.mgr.stream_path(sid).stat().st_size + self.mgr.meta_path(sid).stat().st_size
        self.assertEqual(self.mgr.forget(sid), size)
        self.assertFalse(self.mgr.stream_path(sid).exists())
        self.assertFalse(self.mgr.meta_path(sid).exists())
        slow = self.mgr.start(str(self.project), "SLOW task", "sonnet", "low")
        self.assertTrue(wait_for(lambda: "echo: SLOW" in self.mgr.stream_path(slow).read_text(encoding="utf-8")))
        with self.assertRaises(runs.RunError):
            self.mgr.forget(slow)
        self.assertTrue(self.mgr.stream_path(slow).exists())
        self.assertTrue(self.mgr.meta_path(slow).exists())
        with self.assertRaises(runs.RunError):
            self.mgr.forget("nope")

    def test_reconcile_marks_a_cut_run_interrupted(self):
        self.mgr.runs.mkdir(parents=True)
        self.mgr.stream_path("dead").write_text('{"type":"cc_prompt","text":"x"}\n', encoding="utf-8")
        self.mgr._save_meta({"session_id": "dead", "pid": 4, "cwd": str(self.project), "offset": 0,
                             "model": "sonnet", "effort": "low", "ended": None})
        with mock.patch.object(runs.claude_cli, "pid_alive", return_value=False):
            self.assertEqual(self.mgr.reconcile(), 1)
            self.assertEqual(self.mgr.reconcile(), 0)
        self.assertEqual(self.ended("dead")[0]["interrupted"], True)

    def test_reconcile_ends_an_orphan_whose_turn_has_a_result(self):
        # the service that owned the run died; its claude process is alive but its turn is done
        self.mgr.runs.mkdir(parents=True)
        self.mgr.stream_path("orphan").write_text(
            '{"type":"cc_prompt","text":"x"}\n{"type":"result","subtype":"success","total_cost_usd":0.1}\n',
            encoding="utf-8")
        self.mgr._save_meta({"session_id": "orphan", "pid": 4, "cwd": str(self.project), "offset": 0,
                             "model": "sonnet", "effort": "low", "ended": None})
        self.mgr.stream_path("working").write_text('{"type":"cc_prompt","text":"x"}\n', encoding="utf-8")
        self.mgr._save_meta({"session_id": "working", "pid": 5, "cwd": str(self.project), "offset": 0,
                             "model": "sonnet", "effort": "low", "ended": None})
        with mock.patch.object(runs.claude_cli, "pid_alive", return_value=True):
            self.assertEqual(self.mgr.reconcile(), 1)
        self.assertIsNotNone(self.mgr.meta("orphan")["ended"])
        self.assertEqual(self.ended("orphan")[0]["interrupted"], False)
        self.assertIsNone(self.mgr.meta("working")["ended"])

    def test_result_record_lists_denials(self):
        summary = harness.get("claude").summary([{"type": "result", "subtype": "success", "total_cost_usd": 0.2,
                                                  "permission_denials": [
            {"tool_name": "Bash", "tool_input": {"command": "git push --force"}}]}])
        rec = runs.result_record("s", summary, 0, False, False)
        self.assertEqual(rec["denials"], [{"tool": "Bash", "what": "git push --force"}])
        self.assertEqual(rec["cost"], 0.2)
        self.assertTrue(runs.result_record("s", harness.get("claude").summary([]), None, False, False)["interrupted"])

    def test_prune_old_run_files(self):
        self.mgr.runs.mkdir(parents=True)
        old = self.mgr.stream_path("old")
        old.write_text("", encoding="utf-8")
        os.utime(old, (1, 1))
        self.mgr.stream_path("new").write_text("", encoding="utf-8")
        self.assertEqual(runs.prune(self.folder, 14), ["runs/old.jsonl"])


class HarnessRunsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        self.mgr = runs.RunManager(copy.deepcopy(paths.DEFAULTS), self.folder, FAKE,
                                   exes={"codex": FAKE_CODEX, "cmd": FAKE_CMD})
        killer = mock.patch.object(claude_cli, "kill_tree", lambda pid: os.kill(int(pid), signal.SIGTERM))
        killer.start()  # taskkill is Windows' tree kill; the fakes have no children
        self.addCleanup(killer.stop)

    def tearDown(self):
        for proc in list(self.mgr.live.values()):
            proc.kill()
        end = time.time() + 10
        while self.mgr.live and time.time() < end:
            time.sleep(0.05)
        self.tmp.cleanup()

    def log(self):
        return events.LogReader(self.folder).read_new()

    def ended(self, sid):
        return [r for r in self.log() if r["event"] == "run_ended" and r["session_id"] == sid]

    def codex_run(self, prompt="hi", **kw):
        sid = self.mgr.start(str(self.project), prompt, "gpt-6.1-sol", "medium", harness="codex", **kw)
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        return sid

    def test_start_codex_writes_prompt_on_stdin_and_closes_it(self):
        sid = self.codex_run()
        types = [d.get("type") for d in runs.read_lines(self.mgr.stream_path(sid), 0)[1]]
        self.assertEqual(types, ["cc_prompt", "thread.started", "turn.started", "item.completed",
                                 "item.completed", "turn.completed", "cc_exit"])
        self.assertEqual(runs.read_lines(self.mgr.stream_path(sid), 0)[1][-1]["code"], 0)
        meta = self.mgr.meta(sid)
        self.assertEqual((meta["harness"], meta["harness_session"], meta["read_only"], meta["timed_out"]),
                         ("codex", "th_fake", False, False))
        self.assertEqual([r["harness"] for r in self.log() if r["event"] == "run_started"], ["codex"])
        end = self.ended(sid)[0]
        self.assertNotIn("cost", end)
        self.assertEqual(end["tokens"], {"input": 1200, "output": 300, "cache_read": 800, "context": None})
        self.assertEqual((end["subtype"], end["stopped"], end["interrupted"]), ("success", False, False))
        self.assertIn("STOP: <question>", runs.chat(self.mgr.stream_path(sid), harness="codex")[2]["text"])

    def test_resume_codex_uses_the_thread_id(self):
        sid = self.codex_run()
        with mock.patch.object(self.mgr, "_spawn", wraps=self.mgr._spawn) as spawn:
            self.assertEqual(self.mgr.start(str(self.project), "more", "gpt-6.1-sol", "medium", resume=sid,
                                            harness="codex"), sid)
            self.assertTrue(wait_for(lambda: len(self.ended(sid)) == 2))
        cmd = spawn.call_args.args[0]
        self.assertEqual(cmd[cmd.index("resume"):cmd.index("resume") + 2], ["resume", "th_fake"])

    def test_resume_takes_the_harness_from_the_meta(self):
        sid = self.codex_run()
        with mock.patch.object(self.mgr, "_spawn", wraps=self.mgr._spawn) as spawn:
            self.mgr.start(str(self.project), "go on", "gpt-6.1-sol", "medium", resume=sid)
            self.assertTrue(wait_for(lambda: len(self.ended(sid)) == 2))
        cmd = spawn.call_args.args[0]
        self.assertEqual(cmd[:len(FAKE_CODEX)], FAKE_CODEX)
        self.assertIn("th_fake", cmd)
        self.assertNotIn("--resume", cmd)
        self.assertEqual(self.mgr.meta(sid)["harness"], "codex")

    def test_step_timeout_stops_a_capless_run(self):
        self.mgr.cfg["step_timeout_s"] = 1
        sid = self.mgr.start(str(self.project), "SLOW task", "gpt-6.1-sol", "medium", harness="codex")
        self.assertTrue(wait_for(lambda: self.ended(sid), 20))
        end = self.ended(sid)[0]
        self.assertEqual((end["subtype"], end["stopped"], end["interrupted"]), ("error_step_timeout", False, False))
        self.assertNotIn("turn.completed", self.mgr.stream_path(sid).read_text(encoding="utf-8"))  # killed
        meta = self.mgr.meta(sid)
        self.assertTrue(meta["timed_out"])
        self.assertEqual(meta["limits"]["timeout_s"], 1)
        self.assertEqual(tasks.cap_reason(end["subtype"], meta["limits"]), "it hit the step timeout (1 s)")

    def test_stdin_closed_for_argv_adapters(self):
        script = 'import sys; sys.stdin.read(); print(\'{"type": "result"}\', flush=True)'
        stub = types.SimpleNamespace(
            NAME="stub", CAPS=False, INTERRUPT=False, RESUME=True, HOOKS=False,
            run_command=lambda exe, *a, **kw: ([sys.executable, "-c", script], None),
            is_result=lambda d: d.get("type") == "result",
            summary=lambda lines: {"final": "", "subtype": "success", "cost": None, "tokens": None,
                                   "session_id": "", "denials": [], "exit_cap": False},
            chat=lambda lines, cwd: [], stop=lambda proc: "kill", terminal_command=lambda *a: None,
            env=lambda read_only: {})
        mgr = runs.RunManager(copy.deepcopy(paths.DEFAULTS), self.folder, FAKE, exes={"stub": ["stub"]})
        with mock.patch.dict(harness.REGISTRY, {"stub": stub}):
            sid = mgr.start(str(self.project), "hi", "m", "low", harness="stub")
            self.assertTrue(wait_for(lambda: self.ended(sid), 5))
        self.assertEqual(self.ended(sid)[0]["subtype"], "success")

    def test_prompt_too_long_for_cmd(self):
        with self.assertRaises(runs.RunError) as ctx:
            self.mgr.start(str(self.project), "x" * 40000, "gpt-6-luna", "low", harness="cmd")
        self.assertIn("prompt too long for cmd (40000 chars)", str(ctx.exception))
        self.assertEqual([r for r in self.log() if r["event"] == "run_started"], [])

    def test_a_harness_without_an_exe_is_refused(self):
        with self.assertRaises(runs.RunError) as ctx:
            self.mgr.start(str(self.project), "hi", "m", "low", harness="opencode")
        self.assertEqual(str(ctx.exception), "opencode: not found")

    def test_chat_dispatches_on_harness(self):
        sid = self.codex_run()
        self.assertEqual([i["role"] for i in self.mgr.chat_of(sid)], ["you", "tool", "claude", "result"])

    def test_stop_kills_a_codex_run(self):
        sid = self.mgr.start(str(self.project), "SLOW task", "gpt-6.1-sol", "medium", harness="codex")
        self.assertTrue(wait_for(lambda: self.mgr.is_live(sid)))
        self.assertEqual(self.mgr.stop(sid), "kill")
        self.assertTrue(wait_for(lambda: self.ended(sid), 20))
        self.assertTrue(self.ended(sid)[0]["stopped"])

    def test_open_terminal_refused_for_codex(self):
        sid = self.codex_run()
        with self.assertRaises(runs.RunError) as ctx:
            self.mgr.open_terminal(sid)
        self.assertEqual(str(ctx.exception), "claude only")


if __name__ == "__main__":
    unittest.main()
