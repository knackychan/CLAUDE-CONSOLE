"""Estimated cost from Claude Code transcripts: each assistant message's usage x the price table in
config.json ("prices", USD per million tokens). Read only, as the files grow: one offset per file.
A message's usage repeats on each of its content-block lines, and a fork copies its parent's lines,
so a message id counts once, in the first file it was seen in."""
import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import claude_cli


def agent_path(transcript: str, agent_id: str) -> str:
    """Where Claude Code writes a subagent's transcript: <session>/subagents/agent-<id>.jsonl."""
    return str(Path(transcript).with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl")


def message_cost(model: str, usage: dict, prices: dict) -> float:
    """USD for one message; 0.0 for a model the table does not price."""
    p = prices.get(claude_cli.model_alias(model))
    if not p:
        return 0.0
    tagged = usage.get("cache_creation") or {}
    write_1h = int(tagged.get("ephemeral_1h_input_tokens") or 0)
    write_5m = max(0, int(usage.get("cache_creation_input_tokens") or 0) - write_1h)
    cost = (int(usage.get("input_tokens") or 0) * p["input"]
            + int(usage.get("output_tokens") or 0) * p["output"]
            + int(usage.get("cache_read_input_tokens") or 0) * p["cache_read"]
            + write_5m * p["cache_write_5m"] + write_1h * p["cache_write_1h"]) / 1e6
    return cost * 2 if usage.get("speed") == "fast" else cost


def _when(stamp) -> float:
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


class Usage:
    def __init__(self, prices: dict):
        self.prices = prices
        self.lock = threading.Lock()
        self.offsets = {}   # path -> bytes read (always at a line end)
        self.messages = {}  # path -> {message id: (ts, family, cost)}
        self.owner = {}     # message id -> the path that counts it

    def poll(self, path: str) -> int:
        """Read what was added to `path`; returns the number of new messages."""
        try:
            size = os.path.getsize(path)
        except (OSError, TypeError, ValueError):
            return 0
        start = self.offsets.get(path, 0)
        if size == start:
            return 0
        if size < start:  # rewritten: read it again
            start = 0
            with self.lock:
                for mid in self.messages.pop(path, {}):
                    self.owner.pop(mid, None)
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                data = fh.read()
        except OSError:
            return 0
        end = data.rfind(b"\n") + 1  # a half-written last line waits for the next poll
        new = 0
        with self.lock:
            msgs = self.messages.setdefault(path, {})
            for line in data[:end].splitlines():
                if b'"usage"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) and rec.get("type") == "assistant" else None
                usage = msg.get("usage") if isinstance(msg, dict) else None
                if not usage or msg.get("model") in (None, "<synthetic>"):
                    continue
                mid = msg.get("id") or rec.get("uuid")
                if self.owner.setdefault(mid, path) != path:
                    continue
                new += mid not in msgs
                msgs[mid] = (_when(rec.get("timestamp")), claude_cli.model_alias(msg["model"]),
                             message_cost(msg["model"], usage, self.prices))
            self.offsets[path] = start + end
        return new

    def keep(self, paths) -> None:
        """Forget the files of sessions no longer shown: the service runs for days."""
        keep = set(paths)
        with self.lock:
            for path in (set(self.offsets) | set(self.messages)) - keep:
                for mid in self.messages.pop(path, {}):
                    if self.owner.get(mid) == path:
                        del self.owner[mid]
                self.offsets.pop(path, None)

    def cost(self, paths, since: float = 0.0) -> float:
        with self.lock:
            return sum(c for p in paths for ts, _, c in self.messages.get(p, {}).values() if ts >= since)

    def families(self, paths, since: float = 0.0) -> dict:
        out = {}
        with self.lock:
            for p in paths:
                for ts, fam, c in self.messages.get(p, {}).values():
                    if ts >= since and c:
                        out[fam] = out.get(fam, 0.0) + c
        return out


# -- history: every transcript, per local day (the Usage page) -----------------------------------------
DAYS_FILE = "usage-days.json"


def message_tokens(usage: dict) -> list:
    """[input, output, cache write, cache read] of one message."""
    return [int(usage.get(k) or 0) for k in
            ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")]


def day_of(ts: float) -> str:
    """The local date of a timestamp, YYYY-MM-DD."""
    return time.strftime("%Y-%m-%d", time.localtime(ts))


class History:
    """Cost and tokens per local day from every transcript under a root (~/.claude/projects). Read only,
    as the files grow; a message id counts once, in the first file it was seen in (forks copy lines)."""

    def __init__(self, prices: dict):
        self.prices = prices
        self.lock = threading.Lock()
        self.offsets = {}   # path -> bytes read
        self.project = {}   # path -> the folder name of its first cwd
        self.seen = set()   # message ids counted
        self.totals = {}    # day -> {"cost", "tokens", "projects", "models"}

    def scan(self, root) -> int:
        """Read what every transcript under `root` added; returns the number of new messages."""
        try:
            files = [str(p) for p in Path(root).rglob("*.jsonl")]
        except OSError:
            return 0
        return sum(self._read(path) for path in files)

    def _read(self, path: str) -> int:
        try:
            size = os.path.getsize(path)
        except OSError:
            return 0
        start = self.offsets.get(path, 0)
        if size == start:
            return 0
        if size < start:  # rewritten: read it again; ids already counted stay counted once
            start = 0
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                data = fh.read()
        except OSError:
            return 0
        end = data.rfind(b"\n") + 1
        new = 0
        with self.lock:
            for line in data[:end].splitlines():
                if b'"usage"' not in line and (path in self.project or b'"cwd"' not in line):
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if path not in self.project and isinstance(rec.get("cwd"), str) and rec["cwd"]:
                    self.project[path] = Path(rec["cwd"]).name or rec["cwd"]
                msg = rec.get("message") if rec.get("type") == "assistant" else None
                use = msg.get("usage") if isinstance(msg, dict) else None
                if not use or msg.get("model") in (None, "<synthetic>"):
                    continue
                mid = msg.get("id") or rec.get("uuid")
                if mid in self.seen:
                    continue
                self.seen.add(mid)
                new += 1
                cost = message_cost(msg["model"], use, self.prices)
                day = self.totals.setdefault(day_of(_when(rec.get("timestamp"))),
                                             {"cost": 0.0, "tokens": [0, 0, 0, 0], "projects": {}, "models": {}})
                day["cost"] += cost
                day["tokens"] = [a + b for a, b in zip(day["tokens"], message_tokens(use))]
                proj = self.project.get(path) or Path(path).parent.name
                day["projects"][proj] = day["projects"].get(proj, 0.0) + cost
                fam = claude_cli.model_alias(msg["model"]) or "other"
                day["models"][fam] = day["models"].get(fam, 0.0) + cost
            self.offsets[path] = start + end
        return new

    def days(self) -> dict:
        """A copy of the day totals, costs rounded to 4 places."""
        with self.lock:
            return {d: {"cost": round(v["cost"], 4), "tokens": list(v["tokens"]),
                        "projects": {k: round(c, 4) for k, c in v["projects"].items()},
                        "models": {k: round(c, 4) for k, c in v["models"].items()}}
                    for d, v in self.totals.items()}


def _date(day: str):
    return datetime.strptime(day, "%Y-%m-%d").date()


def _sum(days: dict, keys) -> dict:
    found = [days[k] for k in keys if k in days]
    return {"cost": round(sum(float(d.get("cost") or 0) for d in found), 4),
            "tokens": sum(sum(d.get("tokens") or []) for d in found)}


def weeks(days: dict, today: str, n: int = 12) -> list:
    """The last `n` weeks (Monday first), oldest first, the current week last: {start, cost, tokens}."""
    monday = _date(today) - timedelta(days=_date(today).weekday())
    out = []
    for i in range(n - 1, -1, -1):
        start = monday - timedelta(weeks=i)
        keys = [(start + timedelta(days=k)).isoformat() for k in range(7)]
        out.append({"start": start.isoformat(), **_sum(days, keys)})
    return out


def months(days: dict, today: str, n: int = 12) -> list:
    """The last `n` calendar months, oldest first, the current month last: {month, cost, tokens}."""
    t = _date(today)
    out = []
    for i in range(n - 1, -1, -1):
        y, m = divmod(t.year * 12 + t.month - 1 - i, 12)
        key = f"{y:04d}-{m + 1:02d}"
        out.append({"month": key, **_sum(days, [d for d in days if d.startswith(key)])})
    return out


def load_days(folder) -> dict:
    """The closed days kept in usage-days.json ({} when missing or unreadable)."""
    try:
        data = json.loads((Path(folder) / DAYS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    days = data.get("days") if isinstance(data, dict) else None
    return {d: v for d, v in days.items() if isinstance(v, dict)} if isinstance(days, dict) else {}


def merge_days(kept: dict, scanned: dict) -> dict:
    """Kept and scanned days together; for a day in both the larger cost wins (a deleted transcript
    lowers the scan, a late line raises it)."""
    out = dict(kept)
    for day, v in scanned.items():
        if day not in out or float(v.get("cost") or 0) > float(out[day].get("cost") or 0):
            out[day] = v
    return out


def save_days(folder, days: dict, today: str) -> bool:
    """Keep the closed days (before `today`) of `days` merged into usage-days.json; False when nothing
    changed (no write)."""
    kept = load_days(folder)
    merged = merge_days(kept, {d: v for d, v in days.items() if d < today})
    if merged == kept:
        return False
    path = Path(folder) / DAYS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(DAYS_FILE + ".tmp")
    tmp.write_text(json.dumps({"days": dict(sorted(merged.items()))}, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return True
