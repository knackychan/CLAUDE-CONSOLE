import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from console import claude_cli, harness, paths
from console.harness import claude as claude_adapter
from console.harness import cmd as cmd_adapter
from console.harness import codex, opencode

TESTS = Path(__file__).resolve().parent


def fake(name):
    return [sys.executable, str(TESTS / name)]


def run_fake(name, args, stdin=""):
    return subprocess.run(fake(name) + args, input=stdin, capture_output=True, text=True, timeout=30)


def parse(out):
    return [json.loads(x) for x in out.splitlines() if x.strip()]


def cfg_with(**sections):
    cfg = copy.deepcopy(paths.DEFAULTS)
    for name, section in sections.items():
        cfg["harnesses"][name].update(section)
    return cfg


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": self.tmp})
        patcher.start()
        self.addCleanup(patcher.stop)

    def stub(self, name, tiers):
        mod = types.SimpleNamespace(NAME=name, TIERS=tiers)
        patcher = mock.patch.dict(harness.REGISTRY, {name: mod})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_registry_has_the_four_names(self):
        self.assertEqual(harness.NAMES, ("claude", "codex", "opencode", "cmd"))
        self.assertEqual(harness.get("claude").NAME, "claude")
        with self.assertRaises(KeyError):
            harness.get("x")
        self.assertTrue(set(harness.REGISTRY) <= set(harness.NAMES))

    def test_rung_names(self):
        self.assertEqual(harness.split_rung("codex:gpt-6.1-sol"), ("codex", "gpt-6.1-sol"))
        self.assertEqual(harness.split_rung("sonnet"), ("claude", "sonnet"))
        self.assertEqual(harness.rung("claude", "sonnet"), "sonnet")
        self.assertEqual(harness.rung("cmd", "deepseek-v4.1-flash"), "cmd:deepseek-v4.1-flash")

    def test_tier_of_a_rung_from_config(self):
        cfg = cfg_with(codex={"on": True, "models": {"gpt-6.1-sol": "sonnet"}})
        self.assertEqual(claude_cli.tier_of("codex:gpt-6.1-sol", cfg), "sonnet")
        self.assertEqual(claude_cli.tier_of("codex:nope", cfg), "")
        self.assertEqual(claude_cli.tier_of("claude-opus-4-8"), "opus")

    def test_known_model_needs_on_and_listed(self):
        self.stub("codex", tuple(claude_cli.MODELS))
        self.stub("cmd", ("haiku",))
        off = cfg_with(codex={"models": {"gpt-6.1-sol": "sonnet"}})
        on = cfg_with(codex={"on": True, "models": {"gpt-6.1-sol": "sonnet"}},
                      cmd={"on": True, "models": {"x": "sonnet", "y": "haiku"}})
        self.assertFalse(claude_cli.known_model(off, "codex:gpt-6.1-sol"))
        self.assertTrue(claude_cli.known_model(on, "codex:gpt-6.1-sol"))
        self.assertFalse(claude_cli.known_model(on, "codex:other"))
        self.assertFalse(claude_cli.known_model(on, "cmd:x"))
        self.assertTrue(claude_cli.known_model(on, "cmd:y"))
        self.assertTrue(claude_cli.known_model(on, "sonnet"))
        self.assertTrue(claude_cli.known_model(on, "claude-opus-4-8"))

    def test_models_of_filters_by_tier(self):
        self.stub("cmd", ("haiku",))
        cfg = copy.deepcopy(paths.DEFAULTS)
        cfg["models"] = {"cmd": {"a": "sonnet", "b": "haiku", "c": "nonsense"}}
        self.assertEqual(harness.models_of(cfg, "cmd"), {"b": "haiku"})
        self.assertEqual(harness.models_of(cfg, "missing"), {})

    def test_which_prefers_the_given_exe(self):
        f = Path(self.tmp) / "tool.exe"
        f.write_text("x")
        self.assertEqual(harness.which(("a",), str(f)), str(f))
        with mock.patch("shutil.which", return_value="/bin/a"):
            self.assertEqual(harness.which(("a",), str(f) + ".gone"), "/bin/a")
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(harness.which(("a",), ""))

    def test_claude_adapter_wraps_claude_cli(self):
        cmd, stdin = claude_adapter.run_command(["fake"], "sonnet", "medium", "/w", "sid", prompt="hi")
        self.assertEqual(cmd, claude_cli.run_command(["fake"], "sonnet", "medium", "sid"))
        self.assertEqual(stdin, claude_cli.user_message("hi" + claude_cli.STOP_FOOTER))
        _, slash = claude_adapter.run_command(["fake"], "sonnet", "medium", "/w", "sid", prompt="/skill x")
        self.assertEqual(slash, claude_cli.user_message("/skill x"))
        self.assertTrue(claude_adapter.is_result({"type": "result"}))
        self.assertFalse(claude_adapter.is_result({"type": "assistant"}))
        lines = [{"type": "system", "subtype": "init", "session_id": "sid"},
                 {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}},
                 {"type": "result", "subtype": "success", "total_cost_usd": 0.5, "session_id": "sid"}]
        s = claude_adapter.summary(lines)
        self.assertEqual((s["final"], s["cost"], s["session_id"], s["exit_cap"], s["tokens"]),
                         ("done", 0.5, "sid", False, None))
        lines[-1]["subtype"] = "error_max_turns"
        self.assertTrue(claude_adapter.summary(lines)["exit_cap"])
        self.assertEqual(claude_adapter.chat(lines, "/w")[-1]["role"], "result")

    def test_model_alias_ignores_harness_rungs(self):
        self.assertEqual(claude_cli.model_alias("opencode:openrouter/anthropic/claude-sonnet-4-6"), "")
        self.assertEqual(claude_cli.model_alias("codex:gpt-6.1-sol"), "")
        self.assertEqual(claude_cli.model_alias("claude-sonnet-4-6"), "sonnet")
        self.assertEqual(claude_cli.split_rung("foo:sonnet"), ("claude", "foo:sonnet"))

    def test_set_harness_writes_one_key(self):
        folder = Path(self.tmp)
        (folder / "config.json").write_text(json.dumps({"projects": ["x"]}), encoding="utf-8")
        paths.set_harness(folder, "codex", True)
        data = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(data["projects"], ["x"])
        self.assertIs(data["harnesses"]["codex"]["on"], True)
        with self.assertRaises(ValueError):
            paths.set_harness(folder, "nope", True)
        (folder / "config.json").write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            paths.set_harness(folder, "codex", True)

    def test_models_json(self):
        path = Path(self.tmp) / "models.json"
        models, err = paths.load_models()
        self.assertEqual((models, err), (paths.MODELS_DEFAULT, ""))
        self.assertTrue(path.exists())
        edited = copy.deepcopy(paths.MODELS_DEFAULT)
        edited["claude"] = {"sonnet": "sonnet", "claude-sonnet-9": "sonnet", "opus": "opus", "haiku": "haiku"}
        path.write_text(json.dumps(edited), encoding="utf-8")
        self.assertEqual(paths.load_models()[0]["claude"], edited["claude"])
        cfg = paths.load_config()
        self.assertEqual(cfg["ladder"]["sonnet"], ["sonnet", "claude-sonnet-9"])
        self.assertEqual(cfg["models"]["claude"], edited["claude"])
        path.write_text('{\n "claude": {"a": "opus",\n "b" "x"}}', encoding="utf-8")
        models, err = paths.load_models()
        self.assertEqual(models["claude"], edited["claude"])
        self.assertIn("models.json line 3", err)
        del edited["codex"]
        path.write_text(json.dumps(edited), encoding="utf-8")
        (Path(self.tmp) / "config.json").write_text(
            json.dumps({"harnesses": {"codex": {"models": {"old-model": "sonnet"}}}}), encoding="utf-8")
        self.assertEqual(paths.load_config()["models"]["codex"], {"old-model": "sonnet"})

    def test_ladder_keeps_only_known_tiers(self):
        got = paths._ladder_from({"opus": "opus", "claude-opus-4-8": "opus", "gpt-x": "gpt", "y": "", "z": 3},
                                 {"sonnet": ["sonnet"], "mythos": ["m"]})
        self.assertEqual(got, {"opus": ["opus", "claude-opus-4-8"]})

    def test_defaults_and_claude_exe_fallback(self):
        h = paths.DEFAULTS["harnesses"]
        self.assertIs(h["claude"]["on"], True)
        self.assertEqual([h[n]["on"] for n in ("codex", "opencode", "cmd")], [False] * 3)
        self.assertEqual(paths.DEFAULTS["step_timeout_s"], 1800)
        self.assertEqual(paths.DEFAULTS["effort_variant"], {})
        (Path(self.tmp) / "config.json").write_text(json.dumps({"claude_exe": "C:/c.exe"}), encoding="utf-8")
        self.assertEqual(paths.load_config()["harnesses"]["claude"]["exe"], "C:/c.exe")
        self.assertEqual(paths.HARNESSES, harness.NAMES)
        self.assertEqual(claude_cli.HARNESS_NAMES, harness.NAMES)


CODEX_LINES = [
    {"type": "thread.started", "thread_id": "th_fake"},
    {"type": "turn.started"},
    {"type": "item.completed", "item": {"type": "command_execution", "command": "py -m unittest", "exit_code": 0}},
    {"type": "item.completed", "item": {"type": "agent_message", "text": "all done"}},
    {"type": "turn.completed", "usage": {"input_tokens": 2000, "cached_input_tokens": 800,
                                         "output_tokens": 300, "reasoning_output_tokens": 100}},
]


class CodexTest(unittest.TestCase):
    def test_store_shell_filtered_only_for_codex_startup(self):
        path = r'C:\tools;C:\Users\me\Microsoft\WindowsApps;C:\Windows\System32'
        with mock.patch.object(codex, "os", name="os") as env_os, \
                mock.patch.object(codex.Path, "is_file", return_value=True):
            env_os.name, env_os.pathsep, env_os.environ = "nt", ";", {"PATH": path}
            self.assertEqual(codex.env(False), {"PATH": r'C:\tools;C:\Windows\System32'})
            cmd, _ = codex.run_command(["x"], "m", "low", "/w", "sid", prompt="hi")
            self.assertIn("shell_environment_policy.set.PATH=" + json.dumps(path), cmd)
            env_os.name = "posix"
            self.assertEqual(codex.env(False), {})

    def test_shell_start_failure_is_not_success(self):
        failed = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": -1,
                  "aggregated_output": "Failed to create unified exec process: CreateProcessAsUserW failed: 5"}}
        done = {"type": "turn.completed"}
        self.assertEqual(codex.summary([failed, done])["subtype"], "error_shell_start")
        self.assertEqual(codex.chat([failed, done], "/w")[-1]["text"], "error · 1 turns")
        recovered = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0}}
        self.assertEqual(codex.summary([failed, recovered, done])["subtype"], "success")
        self.assertEqual(codex.summary([failed, done, {"type": "turn.started"}, done])["subtype"], "success")
        ordinary = {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 1,
                    "aggregated_output": "test assertion failed"}}
        self.assertEqual(codex.summary([ordinary, done])["subtype"], "success")

    def test_failed_file_change_is_write_denied(self):
        failed = {"type": "item.completed", "item": {"type": "file_change", "status": "failed",
                  "changes": [{"path": "D:/p/PLAN.md", "kind": "update"}]}}
        done = {"type": "turn.completed"}
        self.assertEqual(codex.summary([failed, done])["subtype"], "error_write_denied")
        self.assertEqual(codex.chat([failed, done], "/w")[-1]["text"], "error · 1 turns")
        wrote = {"type": "item.completed", "item": {"type": "file_change", "status": "completed", "changes": []}}
        self.assertEqual(codex.summary([failed, wrote, done])["subtype"], "success")
        self.assertEqual(codex.summary([failed, done, {"type": "turn.started"}, done])["subtype"], "success")

    def test_write_block_reads_the_sandbox_mode_and_the_owner(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home, "config.toml")
            with mock.patch.dict(os.environ, {"CODEX_HOME": home, "USERDOMAIN": "PC", "USERNAME": "fred"}), \
                    mock.patch.object(codex, "WINDOWS", True):
                with mock.patch.object(codex, "_owned_by_me", return_value=True):
                    self.assertEqual(codex.write_block(home), "")  # no config.toml
                    config.write_text('[windows]\nsandbox = "elevated"\n', encoding="utf-8")
                    self.assertEqual(codex.write_block(home), "")
                    config.write_text("not = [toml", encoding="utf-8")
                    self.assertEqual(codex.write_block(home), "")
                    config.write_text('[windows]\nsandbox = "unelevated"\n', encoding="utf-8")
                    self.assertIn('[windows] sandbox = "elevated"', codex.write_block(home))
                config.write_text('[windows]\nsandbox = "elevated"\n', encoding="utf-8")
                with mock.patch.object(codex, "_owned_by_me", return_value=False):
                    self.assertIn('icacls "D:/old" /setowner "PC\\fred"', codex.write_block("D:/old"))
            with mock.patch.object(codex, "WINDOWS", False):
                self.assertEqual(codex.write_block(home), "")

    @unittest.skipUnless(os.name == "nt", "the owner check is Windows only")
    def test_a_new_folder_is_owned_by_me(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(codex._owned_by_me(d))
        self.assertTrue(codex._owned_by_me(str(Path(d) / "gone")))

    def test_command_shape(self):
        cmd, stdin = codex.run_command(["x"], "gpt-6.1-sol", "xhigh", "D:/p", "sid", prompt="hi")
        self.assertEqual(cmd[:2], ["x", "exec"])
        self.assertIn("--json", cmd)
        self.assertEqual(cmd[cmd.index("-C") + 1], "D:/p")
        self.assertEqual(cmd[cmd.index("-m") + 1], "gpt-6.1-sol")
        self.assertEqual(cmd[cmd.index("-c") + 1], 'model_reasoning_effort="high"')
        self.assertEqual(cmd[cmd.index("-s") + 1], "workspace-write")
        self.assertEqual(cmd[-1], "-")
        self.assertTrue(stdin.decode().endswith(claude_cli.STOP_FOOTER))
        ro, _ = codex.run_command(["x"], "m", "low", "/w", "sid", prompt="hi", read_only=True)
        self.assertEqual(ro[ro.index("-s") + 1], "read-only")
        res, _ = codex.run_command(["x"], "m", "low", "/w", "sid", prompt="hi", resume=True)
        self.assertEqual(res[-3:], ["resume", "sid", "-"])
        self.assertLess(res.index("-s"), res.index("resume"))
        frk, _ = codex.run_command(["x"], "m", "low", "/w", "sid", prompt="hi", fork="th")
        self.assertEqual(frk[-3:], ["fork", "th", "-"])
        for banned in ("--full-auto", "--ephemeral", "--worktree", "-o"):
            self.assertNotIn(banned, cmd)

    def test_summary_from_documented_lines(self):
        s = codex.summary(CODEX_LINES)
        self.assertEqual((s["final"], s["subtype"], s["session_id"], s["cost"]), ("all done", "success", "th_fake", None))
        self.assertEqual(s["tokens"], {"input": 1200, "output": 300, "cache_read": 800, "context": None})
        failed = CODEX_LINES[:4] + [{"type": "turn.failed", "error": {"message": "x"}}]
        self.assertEqual(codex.summary(failed)["subtype"], "error")
        self.assertIsNone(codex.summary(failed)["tokens"])
        self.assertEqual(codex.summary([])["subtype"], "")

    def test_summary_detects_usage_limit_text(self):
        hit = codex.summary([{"type": "error", "message": "You've hit your usage limit"}])["limit"]
        self.assertEqual(hit, {"why": "You've hit your usage limit", "until": None, "window_s": None})
        self.assertIsNone(codex.summary([{"type": "error", "message": "network unavailable"}])["limit"])

    def test_chat_items(self):
        items = codex.chat(CODEX_LINES, "/w")
        self.assertEqual([i["role"] for i in items], ["tool", "claude", "result"])
        self.assertTrue(items[0]["text"].startswith("command_execution"))

    def test_fake_runs_end_to_end(self):
        r = run_fake("fake_codex.py", ["exec", "--json", "-"], "hello there")
        self.assertEqual(r.returncode, 0)
        lines = parse(r.stdout)
        self.assertTrue(codex.is_result(lines[-1]))
        self.assertIn("hello there", codex.summary(lines)["final"])
        self.assertIn("codex-cli", run_fake("fake_codex.py", ["--version"]).stdout)
        cmd, stdin = codex.run_command(["fake"], "m", "low", "/w", "th_old", prompt="again", resume=True)
        r = subprocess.run(fake("fake_codex.py") + cmd[1:], input=stdin.decode(), capture_output=True,
                           text=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(codex.summary(parse(r.stdout))["session_id"], "th_old")
        self.assertEqual(run_fake("fake_codex.py", ["exec", "resume", "t", "--json", "-"], "x").returncode, 2)
        failed = run_fake("fake_codex.py", ["exec", "--json", "-"], "FAIL")
        self.assertEqual(codex.summary(parse(failed.stdout))["subtype"], "error")

    def test_tiers_and_flags(self):
        self.assertEqual(codex.TIERS, tuple(claude_cli.MODELS))
        self.assertIs(codex.CAPS, False)
        self.assertIs(codex.INTERRUPT, False)
        self.assertIs(codex.RESUME, True)
        self.assertIs(codex.HOOKS, False)
        self.assertEqual(harness.get("codex").NAME, "codex")

    def test_terminal_command(self):
        self.assertEqual(codex.terminal_command(["codex"], "th_1", "gpt-6-astra", "medium"),
                         ["codex", "resume", "th_1", "-m", "gpt-6-astra"])


OC_LINES = [
    {"type": "session.created", "sessionID": "oc_fake"},
    {"type": "tool", "tool": "read", "title": "calc.py"},
    {"type": "text", "part": {"text": "the echo"}},
    {"type": "session.idle"},
]


class OpenCodeTest(unittest.TestCase):
    def test_command_shape(self):
        cmd, stdin = opencode.run_command(["oc"], "deepseek/x", "high", "/w", "sid", prompt="SECRET",
                                          variants={"high": "thinking"}, prompt_file="/h/runs/sid.prompt.md")
        self.assertIsNone(stdin)
        self.assertEqual(cmd[:6], ["oc", "run", "--standalone", "--format", "json", "--auto"])
        self.assertEqual(cmd[cmd.index("-m") + 1], "deepseek/x#thinking")
        self.assertEqual(cmd[cmd.index("--file") + 1], "/h/runs/sid.prompt.md")
        self.assertEqual(cmd[-1], opencode.MESSAGE)
        self.assertFalse(any("SECRET" in a for a in cmd))
        plain, _ = opencode.run_command(["oc"], "deepseek/x", "low", "/w", "sid", prompt="p",
                                        variants={"high": "thinking"}, prompt_file="f")
        self.assertNotIn("#", plain[plain.index("-m") + 1])
        res, _ = opencode.run_command(["oc"], "m", "low", "/w", "sid", prompt="p", prompt_file="f", resume=True)
        self.assertEqual(res[res.index("--session") + 1], "sid")
        self.assertNotIn("--fork", res)
        frk, _ = opencode.run_command(["oc"], "m", "low", "/w", "sid", prompt="p", prompt_file="f", fork="old")
        self.assertEqual(frk[frk.index("--session"):frk.index("--session") + 3], ["--session", "old", "--fork"])
        with self.assertRaises(ValueError):
            opencode.run_command(["oc"], "m", "low", "/w", "sid", prompt="p")
        self.assertEqual(set(opencode.env(True)), {"OPENCODE_DISABLE_AUTOUPDATE", "OPENCODE_PERMISSION"})
        self.assertEqual(set(opencode.env(False)), {"OPENCODE_DISABLE_AUTOUPDATE"})

    def test_summary_defensive(self):
        s = opencode.summary(OC_LINES + [{"type": "cc_exit", "code": 0}])
        self.assertEqual((s["final"], s["subtype"], s["session_id"], s["tokens"]), ("the echo", "success", "oc_fake", None))
        self.assertEqual(opencode.summary(OC_LINES + [{"type": "cc_exit", "code": 1}])["subtype"], "error")
        with_tokens = OC_LINES + [{"type": "step", "tokens": {"input": 5, "output": 2, "cache": {"read": 3}}}]
        self.assertEqual(opencode.summary(with_tokens)["tokens"],
                         {"input": 5, "output": 2, "cache_read": 3, "context": None})
        self.assertTrue(opencode.is_result({"type": "session.idle"}))
        self.assertFalse(opencode.is_result({"type": "text"}))

    def test_summary_detects_go_quota_error(self):
        hit = opencode.summary([{"type": "error", "error": {"type": "provider.quota",
            "message": "Go usage limit exceeded", "status": 429,
            "response": {"body": '{"metadata":{"limitName":"5 hour"}}'}}}])["limit"]
        self.assertEqual(hit, {"why": "Go usage limit exceeded (5 hour)", "until": None, "window_s": 18000})

    def test_fake_quota_error(self):
        pf = Path(tempfile.mkdtemp()) / "p.md"
        self.addCleanup(shutil.rmtree, pf.parent, True)
        pf.write_text("QUOTA", encoding="utf-8")
        cmd, _ = opencode.run_command(["fake"], "m", "low", "/w", "sid", prompt="x", prompt_file=str(pf))
        r = subprocess.run(fake("fake_opencode.py") + cmd[1:], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1)
        hit = opencode.summary(parse(r.stdout) + [{"type": "cc_exit", "code": 1}])["limit"]
        self.assertEqual((hit["why"], hit["window_s"]), ("Go usage limit exceeded (5 hour)", 18000))

    def test_claude_rate_limit_rejected_only(self):
        resets = 1792170000
        rejected = {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected",
                    "resetsAt": resets, "rateLimitType": "five_hour"}}
        self.assertEqual(claude_adapter.summary([rejected])["limit"],
                         {"why": "five hour limit", "until": resets, "window_s": None})
        rejected["rate_limit_info"]["status"] = "allowed"
        self.assertIsNone(claude_adapter.summary([rejected])["limit"])

    def test_terminal_command(self):
        self.assertEqual(opencode.terminal_command(["opencode"], "ses_1", "glm-5.3", "high"),
                         ["opencode", "-s", "ses_1", "-m", "glm-5.3"])

    def test_chat_items(self):
        items = opencode.chat(OC_LINES + [{"type": "cc_exit", "code": 0}], "/w")
        self.assertEqual([i["role"] for i in items], ["tool", "claude", "result"])

    def test_fake_end_to_end(self):
        pf = Path(tempfile.mkdtemp()) / "p.md"
        self.addCleanup(shutil.rmtree, pf.parent, True)
        pf.write_text("hello oc", encoding="utf-8")
        cmd, _ = opencode.run_command(["fake"], "m", "low", "/w", "sid", prompt="x", prompt_file=str(pf))
        r = subprocess.run(fake("fake_opencode.py") + cmd[1:], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        lines = parse(r.stdout)
        self.assertTrue(opencode.is_result(lines[-1]))
        self.assertIn("hello oc", opencode.summary(lines + [{"type": "cc_exit", "code": 0}])["final"])
        self.assertEqual(run_fake("fake_opencode.py", ["run", "-m", "x", "msg"]).returncode, 2)
        self.assertIn("0.0.0-fake", run_fake("fake_opencode.py", ["--version"]).stdout)
        pf.write_text("FAIL", encoding="utf-8")
        self.assertEqual(subprocess.run(fake("fake_opencode.py") + cmd[1:], capture_output=True,
                                        timeout=30).returncode, 1)

    def test_tiers_and_flags(self):
        self.assertEqual(opencode.TIERS, ("haiku", "opus"))
        self.assertIs(opencode.CAPS, False)
        self.assertIs(opencode.INTERRUPT, False)
        self.assertEqual(harness.get("opencode").NAME, "opencode")


CMD_LINES = [
    {"event": "start", "session_id": "cmd_fake"},
    {"event": "tool", "name": "read", "input": "calc.py"},
    {"event": "assistant", "text": "the echo"},
    {"type": "result", "result": "the echo", "usage": {"input_tokens": 500, "output_tokens": 100}},
]


class CmdTest(unittest.TestCase):
    def test_npm_launcher_uses_node_without_a_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "cmdc.cmd"
            entry = Path(tmp) / "node_modules" / "command-code" / "dist" / "index.mjs"
            entry.parent.mkdir(parents=True)
            entry.write_text("", encoding="utf-8")
            with mock.patch.object(cmd_adapter.shutil, "which", return_value="node.exe"):
                argv, _ = cmd_adapter.run_command([str(shim)], "m", "low", tmp, "sid", prompt='say & echo "hi"')
                self.assertEqual(argv[:2], ["node.exe", str(entry)])
                self.assertTrue(argv[argv.index("-p") + 1].startswith('say & echo "hi"'))
                self.assertEqual(cmd_adapter.version_command([str(shim)]),
                                 ["node.exe", str(entry), "--no-auto-update", "-v"])

    def test_command_shape(self):
        cmd, stdin = cmd_adapter.run_command(["cmdc"], "gpt-6-luna", "max", "/w", "sid", prompt="do it",
                                             max_turns=15, name="job")
        self.assertIsNone(stdin)
        self.assertEqual(cmd[:3], ["cmdc", "-p", "do it" + claude_cli.STOP_FOOTER])
        for flag in ("--no-auto-update", "--skip-onboarding", "--no-skills"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "json")
        self.assertEqual(cmd[cmd.index("-m") + 1], "gpt-6-luna")
        self.assertEqual(cmd[cmd.index("--effort") + 1], "high")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "accept-edits")
        self.assertEqual(cmd[cmd.index("--max-turns") + 1], "15")
        self.assertEqual(cmd[cmd.index("-n") + 1], "job")
        ro, _ = cmd_adapter.run_command(["cmdc"], "m", "low", "/w", "sid", prompt="p", read_only=True)
        self.assertEqual(ro[ro.index("--permission-mode") + 1], "plan")
        self.assertNotIn("--max-turns", ro)
        res, _ = cmd_adapter.run_command(["cmdc"], "m", "low", "/w", "sid", prompt="p", resume=True)
        self.assertEqual(res[res.index("--session") + 1], "sid")
        frk, _ = cmd_adapter.run_command(["cmdc"], "m", "low", "/w", "sid", prompt="p", fork="old")
        self.assertEqual(frk[frk.index("-r") + 1:frk.index("-r") + 3], ["old", "--fork-session"])
        self.assertNotIn("--yolo", cmd)

    def test_exe_names_never_bare_cmd(self):
        for bad in ("cmd", "cmd.exe", "cmd.cmd"):
            self.assertNotIn(bad, cmd_adapter.EXE_NAMES)
        with self.assertRaises(ValueError):
            cmd_adapter.run_command(["x/cmdc.cmd"], "m", "low", "/w", "sid", prompt="p")

    def test_summary_and_cap(self):
        s = cmd_adapter.summary(CMD_LINES + [{"type": "cc_exit", "code": 0}])
        self.assertEqual((s["final"], s["subtype"], s["session_id"], s["exit_cap"]),
                         ("the echo", "success", "cmd_fake", False))
        self.assertEqual(s["tokens"]["input"], 500)
        capped = cmd_adapter.summary(CMD_LINES[:3] + [{"type": "cc_exit", "code": 8}])
        self.assertEqual((capped["subtype"], capped["exit_cap"], capped["final"]), ("error_max_turns", True, "the echo"))
        self.assertEqual([i["role"] for i in cmd_adapter.chat(CMD_LINES + [{"type": "cc_exit", "code": 0}], "/w")],
                         ["tool", "claude", "result"])

    def test_version_command_has_no_auto_update(self):
        self.assertEqual(cmd_adapter.version_command(["c"]), ["c", "--no-auto-update", "-v"])

    def test_terminal_command(self):
        self.assertEqual(cmd_adapter.terminal_command(["cmdc"], "c_1", "gpt-6-luna", "low"),
                         ["cmdc", "-r", "c_1", "-m", "gpt-6-luna", "--no-auto-update"])

    def test_fake_end_to_end(self):
        cmd, _ = cmd_adapter.run_command(["fake"], "m", "low", "/w", "sid", prompt="hello cmd", max_turns=3)
        r = subprocess.run(fake("fake_cmd.py") + cmd[1:], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)
        lines = parse(r.stdout)
        self.assertTrue(cmd_adapter.is_result(lines[-1]))
        self.assertFalse(cmd_adapter.is_result(lines[0]))
        self.assertIn("hello cmd", cmd_adapter.summary(lines + [{"type": "cc_exit", "code": 0}])["final"])
        cap, _ = cmd_adapter.run_command(["fake"], "m", "low", "/w", "sid", prompt="MAXTURNS")
        self.assertEqual(subprocess.run(fake("fake_cmd.py") + cap[1:], capture_output=True, timeout=30).returncode, 8)
        bare = [a for a in cmd[1:] if a != "--no-auto-update"]
        self.assertEqual(subprocess.run(fake("fake_cmd.py") + bare, capture_output=True, timeout=30).returncode, 2)
        self.assertIn("Command Code", run_fake("fake_cmd.py", cmd_adapter.version_command([])).stdout)

    def test_tiers_and_flags(self):
        self.assertEqual(cmd_adapter.TIERS, ("haiku",))
        self.assertIs(cmd_adapter.CAPS, True)
        self.assertEqual(harness.get("cmd").NAME, "cmd")


if __name__ == "__main__":
    unittest.main()
