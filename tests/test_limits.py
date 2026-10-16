import json
import tempfile
import unittest
from pathlib import Path

from console import limits


class LimitsTest(unittest.TestCase):
    def test_provider_groups_shared_subscriptions(self):
        self.assertEqual(limits.provider("opus"), "claude")
        self.assertEqual(limits.provider("opencode:opencode-go/glm-5.3"), "opencode:opencode-go")
        self.assertEqual(limits.provider("codex:gpt-6-astra"), "codex")

    def test_window_names(self):
        self.assertEqual(limits.window_s("5 hour"), 18000)
        self.assertEqual(limits.window_s("seven_day"), 7 * 86400)
        self.assertIsNone(limits.window_s("nothing"))

    def test_read_prunes_expired_and_ignores_broken_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / limits.FILE
            path.write_text(json.dumps({"old": {"until": 9, "why": "old"},
                                        "new": {"until": 11, "why": "new"}}), encoding="utf-8")
            self.assertEqual(limits.read(tmp, now=10), {"new": {"until": 11, "why": "new"}})
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(limits.read(tmp, now=10), {})


if __name__ == "__main__":
    unittest.main()
