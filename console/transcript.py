"""The last turns of a Claude Code chat in words, read from its transcript: a VS Code or terminal chat
has no stream of its own. Read only, from the end of the file; tool calls, tool results and thinking
stay out (Steps shows tool calls)."""
import base64
import json
import re
from datetime import datetime
from pathlib import PurePath

from . import attach, redact

TAIL_BYTES = 4 * 1024 * 1024  # read from the end: the last few turns of a long chat, pasted images included
HEAD_BYTES = 256 * 1024  # the first prompt is near the start of the file
TURNS = 6
TEXT_MAX = 1500   # the first prompt (a title, a brief goal)
TURN_MAX = 20000  # one chat turn: a long reply must not end mid-word
# A block Claude Code or an extension puts into a user line (<system-reminder>, <command-name>, ...).
# Fred's own pastes stay, as in cc_events.py.
_INJECTED = re.compile(r"\s*<(?!pasted_content\b)([A-Za-z][\w-]*)[^>]*>.*?</\1>\s*", re.S)
_PASTED = re.compile(r"</?pasted_content[^>]*>")
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}  # the kinds a Chat thumbnail shows (attach.kind_of)


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


def _attached(content, uuid: str = "") -> list:
    """Files Fred sent with a prompt: pasted or dropped images, attached documents (name, kind, size).
    An image also says where it is (`at`: the line's uuid and the block's index) for its thumbnail."""
    out = []
    for k, b in enumerate(content if isinstance(content, list) else []):
        src = b.get("source") if isinstance(b, dict) else None
        if not isinstance(src, dict) or b.get("type") not in ("image", "document"):
            continue
        data = src.get("data") if isinstance(src.get("data"), str) else ""
        size = len(data) * 3 // 4 if src.get("type") == "base64" else len(data.encode("utf-8"))
        if b["type"] == "image":
            out.append({"name": f"image {sum(f['kind'] == 'image' for f in out) + 1}", "kind": "image", "bytes": size,
                        **({"at": [uuid, k]} if uuid else {})})
        else:
            out.append({"name": redact.clip(str(b.get("title") or "document"), 120),
                        "kind": "pdf" if src.get("media_type") == "application/pdf" else "text", "bytes": size})
    return out


def note_write(wrote: list, block: dict, cwd: str = "") -> None:
    """A Write call inside the session's folder is a file Claude made: it shows under Claude's next
    words. Scratch files elsewhere (temp scripts) stay in Steps."""
    if block.get("type") != "tool_use" or block.get("name") != "Write" or not cwd:
        return
    name = redact.summarize("Write", block.get("input"), cwd)
    if name and not PurePath(name).is_absolute() and ":" not in name and all(f["name"] != name for f in wrote):
        ext = name.rsplit(".", 1)[-1].lower()
        wrote.append({"name": name, "kind": "image" if ext in IMAGE_EXT else "file", "bytes": None})


def flush_wrote(items: list, wrote: list) -> None:
    """Files Claude wrote with no words after them (the turn ended or Fred spoke next)."""
    if wrote:
        items.append({"role": "claude", "text": "", "files": wrote[:]})
        wrote.clear()


def turns(path, limit: int = TURNS) -> list:
    """[{role: you | claude | note, text, ts, files}] oldest first: the last `limit` turns of the transcript.
    `files`: what Fred attached to a prompt, or what Claude wrote before a reply."""
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
    out, wrote = [], []
    for raw in lines:
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        kind = rec.get("type") if isinstance(rec, dict) else None
        if kind not in ("user", "assistant") or rec.get("isMeta") or rec.get("isSidechain"):
            continue
        msg = rec.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        text = _words(content)
        files = _attached(content, str(rec.get("uuid") or "")) if kind == "user" else []
        if kind == "assistant":
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict):
                    note_write(wrote, block, rec.get("cwd") or "")
        if not text and not files:
            continue
        ts = _when(rec.get("timestamp"))
        if text.startswith("[Request interrupted"):
            out.append({"role": "note", "text": "stopped", "ts": ts})
            continue
        text = redact.mask(text)
        if len(text) > TURN_MAX:
            text = text[:TURN_MAX].rstrip() + "\n[cut here, the full text is in the transcript]"
        if kind == "user":
            flush_wrote(out, wrote)
            out.append({"role": "you", "text": text, "ts": ts, "files": files})
        else:
            out.append({"role": "claude", "text": text, "ts": ts, "files": wrote[:]})
            wrote.clear()
    flush_wrote(out, wrote)
    return out[-limit:]


def image(path, uuid: str, k: int):
    """(bytes, media type) of image block `k` in Fred's line `uuid`, for its Chat thumbnail; None when
    the line, the block or the image is not there. Read only, line by line."""
    path = str(path or "")
    if not path.endswith(".jsonl") or not uuid:
        return None
    needle = f'"{uuid}"'.encode("utf-8")
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                if needle not in raw:
                    continue
                rec = json.loads(raw)
                if not isinstance(rec, dict) or rec.get("uuid") != uuid:
                    continue  # a line that only points at it (parentUuid)
                content = (rec.get("message") or {}).get("content")
                block =content[k] if isinstance(content, list) and 0 <= k < len(content) else None
                src = block.get("source") if isinstance(block, dict) and block.get("type") == "image" else None
                if not isinstance(src, dict) or src.get("type") != "base64":
                    return None
                data = base64.b64decode(src.get("data") or "")
                kind = attach.kind_of(data)
                return (data, kind[1]) if kind and kind[0] == "image" else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    return None


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
