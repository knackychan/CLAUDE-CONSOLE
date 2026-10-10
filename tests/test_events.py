import json
import tempfile
import time
import unittest
from pathlib import Path

from console import events


class LogReaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.file = self.folder / "events-2026-10-10.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        with open(self.file, "a", encoding="utf-8") as fh:
            fh.write(text)

    def line(self, ts, event="Stop", sid="s1"):
        return json.dumps({"ts": ts, "event": event, "session_id": sid}) + "\n"

    def test_reads_only_new_lines(self):
        reader = events.LogReader(self.folder)
        self.write(self.line(1) + self.line(2))
        self.assertEqual([r["ts"] for r in reader.read_new()], [1, 2])
        self.assertEqual(reader.read_new(), [])
        self.write(self.line(3))
        self.assertEqual([r["ts"] for r in reader.read_new()], [3])

    def test_waits_for_a_half_written_line(self):
        reader = events.LogReader(self.folder)
        full = self.line(5)
        self.write(full[:10])
        self.assertEqual(reader.read_new(), [])
        self.write(full[10:])
        self.assertEqual([r["ts"] for r in reader.read_new()], [5])

    def test_skips_broken_and_foreign_lines(self):
        reader = events.LogReader(self.folder)
        self.write("{broken\n" + json.dumps({"ts": 1}) + "\n" + self.line(7))
        self.assertEqual([r["ts"] for r in reader.read_new()], [7])

    def test_merges_two_days_in_time_order(self):
        (self.folder / "events-2026-10-09.jsonl").write_text(self.line(4), encoding="utf-8")
        self.write(self.line(2))
        self.assertEqual([r["ts"] for r in events.LogReader(self.folder).read_new()], [2, 4])


class PruneTest(unittest.TestCase):
    def test_removes_files_older_than_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            now = time.mktime((2026, 10, 20, 12, 0, 0, 0, 0, -1))
            for day in ("2026-10-01", "2026-10-05", "2026-10-06", "2026-10-20"):
                (folder / f"events-{day}.jsonl").write_text("", encoding="utf-8")
            removed = events.prune(folder, 14, now=now)
            self.assertEqual(sorted(removed), ["events-2026-10-01.jsonl", "events-2026-10-05.jsonl"])
            self.assertEqual(len(list(folder.glob("*.jsonl"))), 2)


if __name__ == "__main__":
    unittest.main()
