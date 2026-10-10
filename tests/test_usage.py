import json
import tempfile
import unittest
from pathlib import Path

from console import paths, usage

PRICES = paths.DEFAULTS["prices"]


def line(mid, model="claude-opus-5-5", ts="2026-10-10T10:00:00.000Z", side=False, **use):
    return json.dumps({"type": "assistant", "isSidechain": side, "timestamp": ts,
                       "message": {"id": mid, "model": model, "usage": use}}) + "\n"


class CostTest(unittest.TestCase):
    def test_message_cost(self):
        self.assertAlmostEqual(usage.message_cost("claude-opus-5-5", {"input_tokens": 1_000_000}, PRICES), 4.0)
        tagged = {"cache_creation_input_tokens": 300_000, "cache_read_input_tokens": 1_000_000,
                  "cache_creation": {"ephemeral_1h_input_tokens": 100_000}, "output_tokens": 10_000}
        # 200K 5-minute writes x 2.50 + 100K 1-hour writes x 4.00 + 1M reads x 0.20 + 10K out x 10
        self.assertAlmostEqual(usage.message_cost("claude-sonnet-5-5", tagged, PRICES), 0.5 + 0.4 + 0.2 + 0.1)
        self.assertAlmostEqual(usage.message_cost("claude-opus-5-5", {"output_tokens": 1_000_000, "speed": "fast"},
                                                  PRICES), 40.0)
        self.assertEqual(usage.message_cost("gpt-5", {"input_tokens": 1_000_000}, PRICES), 0.0)


class UsageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "s1.jsonl")
        self.usage = usage.Usage(PRICES)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, mode="a"):
        with open(self.path, mode, encoding="utf-8") as fh:
            fh.write(text)

    def test_reads_as_the_file_grows_and_counts_each_message_once(self):
        self.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n"
                   + line("m1", input_tokens=1_000_000)
                   + line("m1", input_tokens=1_000_000)  # the same message, its next content block
                   + line("m2", model="<synthetic>", input_tokens=5)
                   + line("m3", ts="2026-10-10T11:00:00.000Z", output_tokens=50_000)[:40], "w")
        self.assertEqual(self.usage.poll(self.path), 1)
        self.assertAlmostEqual(self.usage.cost([self.path]), 4.0)
        self.write(line("m3", ts="2026-10-10T11:00:00.000Z", output_tokens=50_000)[40:])
        self.assertEqual(self.usage.poll(self.path), 1)
        self.assertEqual(self.usage.poll(self.path), 0)
        self.assertAlmostEqual(self.usage.cost([self.path]), 5.0)
        since = usage._when("2026-10-10T10:30:00Z")
        self.assertAlmostEqual(self.usage.cost([self.path], since=since), 1.0)
        self.assertEqual(self.usage.poll(str(Path(self.tmp.name) / "missing.jsonl")), 0)

    def test_fork_copies_count_once_and_families(self):
        self.write(line("m1", input_tokens=1_000_000) + line("m2", model="claude-haiku-5-5", output_tokens=1_000_000), "w")
        fork = str(Path(self.tmp.name) / "s2.jsonl")
        Path(fork).write_text(line("m1", input_tokens=1_000_000) + line("m9", model="claude-sonnet-5-5",
                                                                         input_tokens=1_000_000), encoding="utf-8")
        self.usage.poll(self.path)
        self.usage.poll(fork)
        self.assertAlmostEqual(self.usage.cost([fork]), 2.0)
        fams = self.usage.families([self.path, fork])
        self.assertEqual(sorted(fams), ["haiku", "opus", "sonnet"])
        self.assertAlmostEqual(fams["opus"], 4.0)
        self.usage.keep([fork])
        self.assertEqual(self.usage.cost([self.path]), 0)
        self.assertEqual(self.usage.poll(fork), 0)  # still read up to its end
        self.assertEqual(Path(usage.agent_path(self.path, "a1")).as_posix(),
                         Path(self.tmp.name, "s1", "subagents", "agent-a1.jsonl").as_posix())


if __name__ == "__main__":
    unittest.main()
