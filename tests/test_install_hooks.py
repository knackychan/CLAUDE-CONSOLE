import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import install_hooks


class InstallHooksTest(unittest.TestCase):
    def test_merge_adds_every_event_once_and_keeps_other_hooks(self):
        other = {"matcher": "Bash", "hooks": [{"type": "command", "command": "x.sh"}]}
        settings = {"model": "opus", "hooks": {"PreToolUse": [other]}}
        install_hooks.merge(settings, python="py.exe")
        install_hooks.merge(settings, python="py.exe")  # second run changes nothing
        self.assertEqual(settings["model"], "opus")
        for event in install_hooks.EVENTS:
            ours = [g for g in settings["hooks"][event] if install_hooks._is_ours(g)]
            self.assertEqual(len(ours), 1, event)
            self.assertEqual(ours[0]["hooks"][0],
                             {"type": "command", "command": "py.exe", "args": [install_hooks.SCRIPT], "async": True})
        self.assertIn(other, settings["hooks"]["PreToolUse"])

    def test_remove_takes_only_ours(self):
        other = {"hooks": [{"type": "command", "command": "x.sh"}]}
        settings = install_hooks.merge({"hooks": {"Stop": [other]}}, python="py.exe")
        install_hooks.remove(settings)
        self.assertEqual(settings, {"hooks": {"Stop": [other]}})
        self.assertEqual(install_hooks.remove(install_hooks.merge({}, python="p")), {})

    def test_write_goes_through_a_temp_file(self):
        """Plan 34 F6: settings.json is replaced whole; a failed replace leaves it as it was and no temp file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text('{"model": "opus"}\n', encoding="utf-8")
            with mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(install_hooks.main(["--write", "--settings", str(path), "--python", "py.exe"]), 0)
            written = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(written["model"], "opus")
            self.assertIn("Stop", written["hooks"])
            before = path.read_text(encoding="utf-8")
            with mock.patch.object(install_hooks.os, "replace", side_effect=PermissionError(13, "in use")), \
                    mock.patch("sys.stdout", io.StringIO()):
                with self.assertRaises(PermissionError):
                    install_hooks.main(["--remove", "--settings", str(path)])
            self.assertEqual(path.read_text(encoding="utf-8"), before)
            self.assertEqual([p.name for p in Path(tmp).glob("*.tmp")], [])


class OtherHarnessInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.files = {"--settings": self.dir / "settings.json", "--codex": self.dir / "hooks.json",
                      "--cmd": self.dir / "cmd-settings.json", "--opencode-dir": self.dir / "plugins"}

    def run_main(self, *harness, remove=False) -> int:
        argv = ["--harness", ",".join(harness)]
        if remove:
            argv.append("--remove")
        else:
            argv.append("--write")
        for flag, path in self.files.items():
            argv += [flag, str(path)]
        argv += ["--python", "py.exe"]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = install_hooks.main(argv)
        self.out = out.getvalue()
        return code

    def read(self, flag: str) -> dict:
        return json.loads(self.files[flag].read_text(encoding="utf-8"))

    def test_codex_merge_keeps_other_hooks(self):
        other = {"hooks": [{"type": "command", "command": "impeccable.sh"}]}
        self.files["--codex"].write_text(json.dumps({"hooks": {"PostToolUse": [other], "Stop": [other]}}),
                                         encoding="utf-8")
        self.assertEqual(self.run_main("codex"), 0)
        data = self.read("--codex")
        for event in install_hooks.CODEX_EVENTS:
            ours = [g for g in data["hooks"][event] if install_hooks._is_ours_cmd(g)]
            self.assertEqual(len(ours), 1, event)
            self.assertEqual(ours[0]["hooks"][0], install_hooks.codex_handler("py.exe"))
        self.assertEqual(data["hooks"]["PostToolUse"], [other])       # not ours: untouched
        self.assertIn(other, data["hooks"]["Stop"])
        self.assertIn("codex", self.out)  # the trust step is printed
        before = self.files["--codex"].read_bytes()
        self.assertEqual(self.run_main("codex"), 0)                    # twice: unchanged
        self.assertEqual(self.files["--codex"].read_bytes(), before)

    def test_codex_remove_takes_only_ours(self):
        other = {"hooks": [{"type": "command", "command": "impeccable.sh"}]}
        original = {"hooks": {"PostToolUse": [other], "Stop": [other]}}
        self.files["--codex"].write_text(json.dumps(original), encoding="utf-8")
        self.run_main("codex")
        self.assertEqual(self.run_main("codex", remove=True), 0)
        self.assertEqual(self.read("--codex"), original)

    def test_cmd_merge_keeps_permissions(self):
        self.files["--cmd"].write_text(json.dumps({"permissions": {"defaultMode": "auto-accept"}}),
                                       encoding="utf-8")
        self.assertEqual(self.run_main("cmd"), 0)
        data = self.read("--cmd")
        self.assertEqual(data["permissions"], {"defaultMode": "auto-accept"})
        self.assertEqual(sorted(data["hooks"]), sorted(install_hooks.CMD_EVENTS))
        for event in install_hooks.CMD_EVENTS:
            self.assertEqual(data["hooks"][event][0]["hooks"][0], install_hooks.cmd_handler("py.exe"))

    def test_opencode_copy_and_remove(self):
        keep = self.files["--opencode-dir"] / "caveman"
        keep.mkdir(parents=True)
        (keep / "plugin.js").write_text("// caveman", encoding="utf-8")
        self.assertEqual(self.run_main("opencode"), 0)
        copied = self.files["--opencode-dir"] / "claude-console"
        self.assertEqual(sorted(p.name for p in copied.iterdir()), ["index.js", "package.json"])
        text = (copied / "index.js").read_text(encoding="utf-8")
        self.assertIn(json.dumps("py.exe"), text)
        self.assertIn(json.dumps(install_hooks.SCRIPT), text)
        self.assertNotIn("__PYTHON__", text)
        self.assertNotIn("__SCRIPT__", text)
        self.assertEqual(json.loads((copied / "package.json").read_text(encoding="utf-8")),
                         {"type": "module", "main": "index.js"})
        self.assertEqual(self.run_main("opencode"), 0)  # a second write changes no content
        self.assertEqual((copied / "index.js").read_text(encoding="utf-8"), text)
        self.assertIn("backup:", self.out)
        self.assertEqual(self.run_main("opencode", remove=True), 0)
        self.assertEqual([p.name for p in sorted(self.files["--opencode-dir"].iterdir())], ["caveman"])
        self.assertEqual(self.run_main("opencode", remove=True), 0)
        self.assertIn("nothing to remove", self.out)

    def test_opencode_dry_run_prints_the_tree(self):
        argv = ["--harness", "opencode", "--opencode-dir", str(self.files["--opencode-dir"])]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(install_hooks.main(argv), 0)
        dest = self.files["--opencode-dir"] / "claude-console"
        for path in (dest, dest / "index.js", dest / "package.json"):
            self.assertIn(str(path), out.getvalue())
        self.assertFalse(self.files["--opencode-dir"].exists())

    def test_bad_json_not_overwritten(self):
        broken = self.dir / "hooks.json"
        broken.write_text('{"hooks": {"Stop": [}', encoding="utf-8")
        before = broken.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.main(["--harness", "codex", "--write", "--codex", str(broken)]), 1)
        self.assertEqual(broken.read_bytes(), before)

    def test_default_is_claude_only(self):
        self.files["--settings"].write_text(json.dumps({"model": "opus"}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_hooks.main(["--write", "--settings", str(self.files["--settings"])]), 0)
        self.assertEqual(self.read("--settings")["model"], "opus")
        for flag in ("--codex", "--cmd"):
            self.assertFalse(self.files[flag].exists(), flag)
        self.assertFalse(self.files["--opencode-dir"].exists())


if __name__ == "__main__":
    unittest.main()
