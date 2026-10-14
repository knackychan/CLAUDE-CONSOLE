import copy
import json
import os
import shutil
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from console import claude_cli, harness, paths
from console.harness import claude as claude_adapter


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


if __name__ == "__main__":
    unittest.main()
