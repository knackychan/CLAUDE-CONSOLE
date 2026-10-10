"""Estimated cost from Claude Code transcripts: each assistant message's usage x the price table in
config.json ("prices", USD per million tokens). Read only, as the files grow: one offset per file.
A message's usage repeats on each of its content-block lines, and a fork copies its parent's lines,
so a message id counts once, in the first file it was seen in."""
import json
import os
import threading
import time
from datetime import datetime
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
