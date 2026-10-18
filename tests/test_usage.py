import json
import tempfile
import unittest
from unittest import mock
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
        self.assertEqual(d9["model_tokens"], {"opus": 1_000_100})
        self.assertEqual(set(d9["projects"]), {"A"})  # the copy in the fork counts once, in the file seen first
        self.assertAlmostEqual(d10["cost"], 0.5 + 2.0)
        self.assertEqual(d10["tokens"], [1_000_000, 1_000_000, 5, 7])
        self.assertAlmostEqual(d10["projects"]["B"], 2.0)
        self.assertEqual(sorted(d10["models"]), ["haiku", "sonnet"])
        self.assertEqual(d10["model_tokens"], {"haiku": 1_000_012, "sonnet": 1_000_000})
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
    def test_rescan_adds_model_tokens_at_equal_cost_without_erasing_larger_saved_totals(self):
        kept = {"2026-10-10": {"cost": 5.0, "models": {"opus": 5.0}}}
        scanned = {"2026-10-10": {"cost": 5.0, "models": {"opus": 5.0}, "model_tokens": {"opus": 700}}}
        merged = usage.merge_days(kept, scanned)
        self.assertEqual(merged["2026-10-10"]["model_tokens"], {"opus": 700})
        self.assertNotIn("model_tokens", kept["2026-10-10"])
        partial = {"2026-10-10": {"cost": 1.0, "model_tokens": {"opus": 100}}}
        self.assertEqual(usage.merge_days(merged, partial), merged)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(usage.save_days(tmp, kept, "2026-10-11"))
            self.assertTrue(usage.save_days(tmp, scanned, "2026-10-11"))
            self.assertEqual(usage.load_days(tmp), merged)

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
            self.assertEqual(row, {"cost": 0.75, "runs": 2, "unknown": 0, "tokens": [2000, 400, 1000],
                                   "tokens_unknown": 0})

    def test_an_unpriced_run_is_unknown_never_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.add_other(folder, "s2@1.0", "2026-10-14", "deepseek-v4.1-flash", None, None)
            usage.add_other(folder, "s2@2.0", "2026-10-14", "deepseek-v4.1-flash", self.TOK, None)
            row = usage.load_other(folder)["2026-10-14"]["deepseek-v4.1-flash"]
            self.assertEqual((row["runs"], row["unknown"], row["cost"], row["tokens"]), (2, 2, 0.0, [1000, 200, 500]))
            self.assertEqual(row["tokens_unknown"], 1)

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

    def test_add_other_returns_what_it_wrote(self):
        with tempfile.TemporaryDirectory() as folder:
            wrote = usage.add_other(folder, "s4@1.0", "2026-10-14", "kimi-k3", None, 1.0)
            self.assertEqual(wrote, usage.load_other(folder))
            self.assertEqual(wrote["2026-10-14"]["kimi-k3"]["cost"], 1.0)
            self.assertIsNone(usage.add_other(folder, "s4@1.0", "2026-10-14", "kimi-k3", None, 1.0))


class UnreadableDaysFileTest(unittest.TestCase):
    """Review K7: an unreadable usage-days.json is never overwritten; it is copied aside once."""

    def test_writers_skip_an_unreadable_file_and_copy_it_aside_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path, bad = folder / usage.DAYS_FILE, folder / (usage.DAYS_FILE + ".bad")
            path.write_text('{"days": {"2026-10-01": {"cost": 9.0}}, "seen"', encoding="utf-8")
            self.assertFalse(usage.add_other(folder, "s5@1.0", "2026-10-14", "kimi-k3", None, 1.0))
            self.assertFalse(usage.save_days(folder, {"2026-10-12": {"cost": 2.0}}, "2026-10-14"))
            self.assertEqual(path.read_text(encoding="utf-8"), '{"days": {"2026-10-01": {"cost": 9.0}}, "seen"')
            self.assertEqual(bad.read_text(encoding="utf-8"), path.read_text(encoding="utf-8"))
            path.write_text("[]", encoding="utf-8")  # not an object: unreadable too; the first copy stays
            self.assertFalse(usage.save_days(folder, {"2026-10-12": {"cost": 2.0}}, "2026-10-14"))
            self.assertEqual((path.read_text(encoding="utf-8"), bad.read_text(encoding="utf-8")[:9]), ("[]", '{"days": '))
            self.assertEqual((usage.load_days(folder), usage.load_other(folder)), ({}, {}))

    def test_a_missing_file_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(usage.save_days(tmp, {"2026-10-12": {"cost": 2.0}}, "2026-10-14"))
            self.assertFalse((Path(tmp) / (usage.DAYS_FILE + ".bad")).exists())

    def test_save_days_returns_false_when_the_write_fails(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(usage, "_write", side_effect=OSError("disk full")):
            self.assertFalse(usage.save_days(tmp, {"2026-10-12": {"cost": 2.0}}, "2026-10-14"))


class SupervisorLedgerTest(unittest.TestCase):
    """Plan 44 T2: the supervisor's own-pass reservations and results in usage-days.json."""

    def rec(self, task="t1", wake=1, day="2026-10-18"):
        return {"task": task, "wake": wake, "day": day, "kind": "wake"}

    def test_reservation_takes_the_lesser_remaining_allowance(self):
        with tempfile.TemporaryDirectory() as folder:
            got = usage.reserve_supervisor(folder, "p1", self.rec(), 0.5, 2.0)
            self.assertEqual((got["status"], got["reserved"]), ("reserved", 0.5))
            self.assertEqual(usage.reserve_supervisor(folder, "p2", self.rec(wake=2), 0.5, 2.0)["status"], "defer")
            self.assertEqual(usage.record_supervisor(folder, "p1", {"cost": 0.2})["status"], "settled")
            got = usage.reserve_supervisor(folder, "p2", self.rec(wake=2), 0.5, 2.0)
            self.assertEqual((got["status"], got["reserved"]), ("reserved", 0.3))
            self.assertEqual(usage.reserve_supervisor(folder, "p3", self.rec(task="t2"), 0.5, 0.4)["status"], "defer")
            self.assertEqual(usage.reserve_supervisor(folder, "p2", self.rec(wake=2), 0.5, 2.0)["status"], "duplicate")

    def test_zero_and_exact_limits_refuse_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(usage.reserve_supervisor(folder, "p0", self.rec(), 0.0, 2.0)["status"], "cap")
            self.assertFalse((Path(folder) / usage.DAYS_FILE).exists())
            usage.reserve_supervisor(folder, "p1", self.rec(), 0.5, 2.0)
            usage.record_supervisor(folder, "p1", {"cost": 0.5})  # exactly the task limit
            self.assertEqual(usage.reserve_supervisor(folder, "p2", self.rec(wake=2), 0.5, 2.0)["status"], "cap")
            usage.reserve_supervisor(folder, "p3", self.rec(task="t2"), 2.0, 0.5)
            usage.record_supervisor(folder, "p3", {"cost": 0.0})
            self.assertEqual(usage.reserve_supervisor(folder, "p4", self.rec(task="t3"), 2.0, 0.5)["status"], "cap")

    def test_settlement_is_idempotent_and_a_conflict_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.reserve_supervisor(folder, "p1", self.rec(), 0.5, 2.0)
            self.assertEqual(usage.record_supervisor(folder, "p1", {"cost": 0.7})["record"]["cost"], 0.7)  # in full
            self.assertEqual(usage.record_supervisor(folder, "p1", {"cost": 0.7})["status"], "settled")
            self.assertEqual(usage.record_supervisor(folder, "p1", {"cost": 0.1})["status"], "conflict")
            records = usage.load_supervisor(folder)["records"]
            self.assertEqual((records["p1"]["cost"], records["p1"]["day"]), (0.7, "2026-10-18"))
            self.assertEqual(usage.record_supervisor(folder, "nope", {"cost": 0.1})["status"], "error")

    def test_unknown_spend_keeps_the_reservation(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.reserve_supervisor(folder, "p1", self.rec(), 0.5, 2.0)
            self.assertEqual(usage.record_supervisor(folder, "p1", {"cost": None})["status"], "unknown")
            self.assertEqual(usage.reserve_supervisor(folder, "p2", self.rec(wake=2), 0.5, 2.0)["status"], "defer")
            self.assertEqual(usage.reserve_supervisor(folder, "p3", self.rec(task="t2"), 2.0, 0.5)["status"], "defer")

    def test_corrupt_or_unwritable_file_refuses_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / usage.DAYS_FILE
            path.write_text("{bad", encoding="utf-8")
            self.assertEqual(usage.reserve_supervisor(folder, "p1", self.rec(), 0.5, 2.0)["status"], "error")
            self.assertEqual(path.read_text(encoding="utf-8"), "{bad")
            self.assertTrue((folder / (usage.DAYS_FILE + ".bad")).exists())
            self.assertTrue(usage.load_supervisor(folder)["error"])
            path.write_text('{"supervisor": []}', encoding="utf-8")
            self.assertTrue(usage.load_supervisor(folder)["error"])
            self.assertEqual(usage.reserve_supervisor(folder, "p1", self.rec(), 0.5, 2.0)["status"], "error")
            path.unlink()
            with mock.patch.object(usage, "_write", side_effect=OSError("disk full")):
                self.assertEqual(usage.reserve_supervisor(folder, "p1", self.rec(), 0.5, 2.0)["status"], "error")
            self.assertEqual(usage.load_supervisor(folder)["records"], {})  # a failed write reserved nothing

    def test_other_writers_keep_the_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.reserve_supervisor(folder, "p1", self.rec(), 0.5, 2.0)
            usage.add_other(folder, "s1@1.0", "2026-10-18", "kimi-k3", None, 1.0)
            usage.save_days(folder, {"2026-10-12": {"cost": 2.0}}, "2026-10-18")
            usage.record_supervisor(folder, "p1", {"cost": 0.1})
            self.assertEqual(usage.load_other(folder)["2026-10-18"]["kimi-k3"]["cost"], 1.0)
            self.assertEqual(usage.load_days(folder)["2026-10-12"]["cost"], 2.0)
            self.assertEqual(usage.load_supervisor(folder)["records"]["p1"]["cost"], 0.1)

    def test_concurrent_writers_lose_nothing(self):
        import threading
        with tempfile.TemporaryDirectory() as folder:
            def sup(i):
                usage.reserve_supervisor(folder, f"p{i}", self.rec(task=f"t{i}"), 0.5, 100.0)
                usage.record_supervisor(folder, f"p{i}", {"cost": 0.01})
            def other(i):
                usage.add_other(folder, f"o{i}@1.0", "2026-10-18", "kimi-k3", None, 0.1)
            threads = [threading.Thread(target=f, args=(i,)) for i in range(10) for f in (sup, other)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(usage.load_supervisor(folder)["records"]), 10)
            self.assertEqual(usage.load_other(folder)["2026-10-18"]["kimi-k3"]["runs"], 10)

    def test_task_deletion_does_not_reset_the_day(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.reserve_supervisor(folder, "p1", self.rec(task="gone"), 2.0, 0.5)
            usage.record_supervisor(folder, "p1", {"cost": 0.4})
            # the task folder never held the ledger: a new task the same day sees the spent day
            got = usage.reserve_supervisor(folder, "p2", self.rec(task="new"), 2.0, 0.5)
            self.assertAlmostEqual(got["reserved"], 0.1)


if __name__ == "__main__":
    unittest.main()
