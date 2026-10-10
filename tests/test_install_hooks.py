import unittest

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


if __name__ == "__main__":
    unittest.main()
