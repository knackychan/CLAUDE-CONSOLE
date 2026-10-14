import json
import tempfile
import unittest
from datetime import datetime
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


def local(day, hour=12):
    """An ISO timestamp at `hour` local time on `day`, with the local offset (the day must not depend on the zone)."""
    return datetime.fromisoformat(f"{day}T{hour:02d}:00:00").astimezone().isoformat()


def cwd_line(mid, day, cwd, model="claude-opus-5-5", **use):
    return json.dumps({"type": "assistant", "cwd": cwd, "timestamp": local(day),
                       "message": {"id": mid, "model": model, "usage": use}}) + "\n"


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "projects"
        (self.root / "d--A" / "s1" / "subagents").mkdir(parents=True)
        (self.root / "d--B").mkdir()
        self.hist = usage.History(PRICES)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sums_each_local_day_once_per_message(self):
        a = self.root / "d--A" / "s1.jsonl"
        a.write_text(cwd_line("m1", "2026-10-09", "D:/work/A", input_tokens=1_000_000, output_tokens=100)
                     + cwd_line("m1", "2026-10-09", "D:/work/A", input_tokens=1_000_000, output_tokens=100)
                     + cwd_line("m2", "2026-10-10", "D:/work/A", model="<synthetic>", input_tokens=9),
                     encoding="utf-8")
        (self.root / "d--A" / "s1" / "subagents" / "agent-x.jsonl").write_text(
            cwd_line("m3", "2026-10-10", "D:/work/A", model="claude-haiku-5-5", output_tokens=1_000_000,
                     cache_read_input_tokens=7, cache_creation_input_tokens=5), encoding="utf-8")
        fork = self.root / "d--B" / "s2.jsonl"
        fork.write_text(cwd_line("m1", "2026-10-09", "D:/work/B", input_tokens=1_000_000, output_tokens=100)
                        + cwd_line("m4", "2026-10-10", "D:/work/B", model="claude-sonnet-5-5",
                                   input_tokens=1_000_000), encoding="utf-8")
        self.assertEqual(self.hist.scan(self.root), 3)
        days = self.hist.days()
        self.assertEqual(sorted(days), ["2026-10-09", "2026-10-10"])
        d9, d10 = days["2026-10-09"], days["2026-10-10"]
        self.assertAlmostEqual(d9["cost"], 4.002)
        self.assertEqual(d9["tokens"], [1_000_000, 100, 0, 0])
        self.assertEqual(set(d9["projects"]), {"A"})  # the copy in the fork counts once, in the file seen first
        self.assertAlmostEqual(d10["cost"], 0.5 + 2.0)
        self.assertEqual(d10["tokens"], [1_000_000, 1_000_000, 5, 7])
        self.assertAlmostEqual(d10["projects"]["B"], 2.0)
        self.assertEqual(sorted(d10["models"]), ["haiku", "sonnet"])
        self.assertEqual(self.hist.scan(self.root), 0)
        with open(fork, "a", encoding="utf-8") as fh:
            fh.write(cwd_line("m5", "2026-10-10", "D:/work/B", model="claude-sonnet-5-5", output_tokens=100_000))
        self.assertEqual(self.hist.scan(self.root), 1)
        self.assertAlmostEqual(self.hist.days()["2026-10-10"]["cost"], 3.5)
        self.assertEqual(self.hist.scan(Path(self.tmp.name) / "missing"), 0)


class AggregateTest(unittest.TestCase):
    DAYS = {"2026-10-05": {"cost": 1.0, "tokens": [1, 2, 3, 4]},     # Monday
            "2026-10-11": {"cost": 2.0, "tokens": [0, 0, 0, 10]},    # Sunday, same week
            "2026-10-12": {"cost": 4.0, "tokens": [0, 0, 0, 100]},   # Monday, next week
            "2025-12-31": {"cost": 8.0, "tokens": [1000, 0, 0, 0]}}

    def test_weeks_start_on_monday(self):
        weeks = usage.weeks(self.DAYS, "2026-10-14", n=3)
        self.assertEqual([w["start"] for w in weeks], ["2026-09-28", "2026-10-05", "2026-10-12"])
        self.assertEqual([w["cost"] for w in weeks], [0.0, 3.0, 4.0])
        self.assertEqual([w["tokens"] for w in weeks], [0, 20, 100])

    def test_months_cross_the_year(self):
        months = usage.months(self.DAYS, "2026-10-14", n=11)
        self.assertEqual(months[0]["month"], "2025-12")
        self.assertEqual(months[-1]["month"], "2026-10")
        self.assertEqual(len(months), 11)
        self.assertEqual(months[0]["cost"], 8.0)
        self.assertEqual(months[0]["tokens"], 1000)
        self.assertEqual(months[-1]["cost"], 7.0)
        self.assertEqual(months[-1]["tokens"], 120)
        self.assertEqual(months[5]["cost"], 0.0)


class DaysFileTest(unittest.TestCase):
    def test_closed_days_are_kept_and_the_larger_cost_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(usage.load_days(folder), {})
            scanned = {"2026-10-09": {"cost": 5.0}, "2026-10-10": {"cost": 1.0}, "2026-10-11": {"cost": 9.0}}
            self.assertTrue(usage.save_days(folder, scanned, "2026-10-11"))
            self.assertEqual(sorted(usage.load_days(folder)), ["2026-10-09", "2026-10-10"])  # not today
            self.assertFalse(usage.save_days(folder, scanned, "2026-10-11"))  # nothing new: no write
            later = {"2026-10-10": {"cost": 3.0}, "2026-10-11": {"cost": 9.5}}  # 10-09's transcript is gone
            merged = usage.merge_days(usage.load_days(folder), later)
            self.assertEqual({d: v["cost"] for d, v in merged.items()},
                             {"2026-10-09": 5.0, "2026-10-10": 3.0, "2026-10-11": 9.5})
            (folder / "usage-days.json").write_text("not json", encoding="utf-8")
            self.assertEqual(usage.load_days(folder), {})


class OtherRunsTest(unittest.TestCase):
    """Plan 18: runs of other harnesses kept per day in usage-days.json, next to the days."""
    TOK = {"input": 1000, "output": 200, "cache_read": 500}

    def test_a_run_counts_once(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(usage.add_other(folder, "s1@1.0", "2026-10-14", "gpt-6.1-sol", self.TOK, 0.25))
            self.assertFalse(usage.add_other(folder, "s1@1.0", "2026-10-14", "gpt-6.1-sol", self.TOK, 0.25))
            self.assertTrue(usage.add_other(folder, "s1@2.0", "2026-10-14", "gpt-6.1-sol", self.TOK, 0.5))
            row = usage.load_other(folder)["2026-10-14"]["gpt-6.1-sol"]
            self.assertEqual(row, {"cost": 0.75, "runs": 2, "unknown": 0, "tokens": [2000, 400, 1000]})

    def test_an_unpriced_run_is_unknown_never_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.add_other(folder, "s2@1.0", "2026-10-14", "deepseek-v4.1-flash", None, None)
            usage.add_other(folder, "s2@2.0", "2026-10-14", "deepseek-v4.1-flash", self.TOK, None)
            row = usage.load_other(folder)["2026-10-14"]["deepseek-v4.1-flash"]
            self.assertEqual((row["runs"], row["unknown"], row["cost"], row["tokens"]), (2, 2, 0.0, [1000, 200, 500]))

    def test_save_days_keeps_the_other_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.add_other(folder, "s3@1.0", "2026-10-12", "kimi-k3", self.TOK, 1.0)
            day = {"cost": 2.0, "tokens": [1, 2, 3, 4], "projects": {}, "models": {"opus": 2.0}}
            self.assertTrue(usage.save_days(folder, {"2026-10-12": day}, "2026-10-14"))
            self.assertEqual(usage.load_days(folder)["2026-10-12"]["cost"], 2.0)
            self.assertEqual(usage.load_other(folder)["2026-10-12"]["kimi-k3"]["cost"], 1.0)
            usage.add_other(folder, "s3@2.0", "2026-10-13", "kimi-k3", self.TOK, 1.0)
            self.assertEqual(usage.load_days(folder)["2026-10-12"]["cost"], 2.0)  # adding a run keeps the days

    def test_seen_ids_are_kept_three_days(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.add_other(folder, "old@1.0", "2026-10-10", "kimi-k3", None, None)
            usage.add_other(folder, "new@1.0", "2026-10-14", "kimi-k3", None, None)
            seen = json.loads((Path(folder) / usage.DAYS_FILE).read_text(encoding="utf-8"))["seen"]
            self.assertEqual(seen, {"2026-10-14": ["new@1.0"]})
            self.assertEqual(usage.load_other(folder)["2026-10-10"]["kimi-k3"]["runs"], 1)  # the counts stay


if __name__ == "__main__":
    unittest.main()
