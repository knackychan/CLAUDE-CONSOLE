"""The last turns of a Claude Code chat in words, read from its transcript: a VS Code or terminal chat
has no stream of its own. Read only, from the end of the file; tool calls, tool results and thinking
stay out (Steps shows tool calls)."""
import json
import re
from datetime import datetime

from . import redact

TAIL_BYTES = 1024 * 1024  # read from the end: enough for the last few turns of a long chat
HEAD_BYTES = 256 * 1024  # the first prompt is near the start of the file
TURNS = 6
TEXT_MAX = 1500
# A block Claude Code or an extension puts into a user line (<system-reminder>, <command-name>, ...).
# Fred's own pastes stay, as in cc_events.py.
_INJECTED = re.compile(r"\s*<(?!pasted_content\b)([A-Za-z][\w-]*)[^>]*>.*?</\1>\s*", re.S)
_PASTED = re.compile(r"</?pasted_content[^>]*>")


def _when(stamp):
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _words(content) -> str:
    """The text blocks of one message, without injected blocks and tool blocks."""
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    else:
        return ""
    text = "\n".join(p for p in parts if isinstance(p, str))
    return _PASTED.sub("", _INJECTED.sub(" ", text)).strip()


def turns(path, limit: int = TURNS) -> list:
    """[{role: you | claude | note, text, ts}] oldest first: the last `limit` turns of the transcript."""
    path = str(path or "")
    if not path.endswith(".jsonl"):
        return []
    try:
        with open(path, "rb") as fh:
            start = max(0, fh.seek(0, 2) - TAIL_BYTES)
            fh.seek(start)
            data = fh.read()
    except OSError:
        return []
    lines = data.split(b"\n")
    if start:
        lines = lines[1:]  # the first line was cut in the middle
    out = []
    for raw in lines:
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        kind = rec.get("type") if isinstance(rec, dict) else None
        if kind not in ("user", "assistant") or rec.get("isMeta") or rec.get("isSidechain"):
            continue
        msg = rec.get("message")
        text = _words(msg.get("content") if isinstance(msg, dict) else None)
        if not text:
            continue
        if text.startswith("[Request interrupted"):
            out.append({"role": "note", "text": "stopped", "ts": _when(rec.get("timestamp"))})
        else:
            out.append({"role": "you" if kind == "user" else "claude", "text": redact.mask(text[:TEXT_MAX]),
                        "ts": _when(rec.get("timestamp"))})
    return out[-limit:]


def first_prompt(path) -> str:
    """The first thing typed in the chat, in words and masked ("" when none is in the first 256 KB)."""
    path = str(path or "")
    if not path.endswith(".jsonl"):
        return ""
    try:
        with open(path, "rb") as fh:
            data = fh.read(HEAD_BYTES)
    except OSError:
        return ""
    for raw in data.split(b"\n"):
        try:
            rec = json.loads(raw)
        except ValueError:
            continue  # also the line cut at the end of the 256 KB
        if not isinstance(rec, dict) or rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
            continue
        msg = rec.get("message")
        text = _words(msg.get("content") if isinstance(msg, dict) else None)
        if text and not text.startswith("[Request interrupted"):
            return redact.mask(text[:TEXT_MAX])
    return ""
