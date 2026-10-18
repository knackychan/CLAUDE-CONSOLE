import json
import tempfile
import time
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

    def test_key_is_the_rung_for_a_model_hit(self):  # plan 45 D1
        self.assertEqual(limits.key("fable", {"why": "credits required", "model": True}), "fable")
        self.assertEqual(limits.key("fable", {"why": "five hour limit"}), "claude")

    def test_clock_names_the_day_when_not_today(self):  # plan 45 D2
        now = time.mktime((2026, 10, 19, 7, 0, 0, 0, 0, -1))
        self.assertEqual(limits.clock(now + 3600, now), "08:00")
        self.assertEqual(limits.clock(time.mktime((2026, 11, 1, 8, 0, 0, 0, 0, -1)), now), "Sun 01 Nov 08:00")

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
