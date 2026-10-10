"""Read the daily event files incrementally and prune old ones."""
import json
import time
from pathlib import Path


class LogReader:
    """Returns only lines added since the last call; skips broken lines."""

    def __init__(self, folder: Path, days: int = 2):
        self.folder = Path(folder)
        self.days = days
        self.offsets = {}

    def files(self):
        return sorted(self.folder.glob("events-*.jsonl"))[-self.days:]

    def read_new(self) -> list:
        out = []
        for path in self.files():
            start = self.offsets.get(path.name, 0)
            try:
                with open(path, "rb") as fh:
                    fh.seek(start)
                    chunk = fh.read()
            except OSError:
                continue
            end = chunk.rfind(b"\n")
            if end < 0:
                continue  # nothing, or a line still being written
            self.offsets[path.name] = start + end + 1
            for raw in chunk[:end].splitlines():
                try:
                    rec = json.loads(raw.decode("utf-8"))
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("session_id") and rec.get("event"):
                    out.append(rec)
        out.sort(key=lambda r: r.get("ts", 0))
        return out


def prune(folder: Path, retention_days: int, now: float = None) -> list:
    """Delete events-YYYY-MM-DD.jsonl files older than `retention_days`. Returns names."""
    cutoff = time.strftime("%Y-%m-%d", time.localtime((now or time.time()) - retention_days * 86400))
    removed = []
    for path in Path(folder).glob("events-*.jsonl"):
        day = path.stem[len("events-"):]
        if day < cutoff:
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass
    return removed
