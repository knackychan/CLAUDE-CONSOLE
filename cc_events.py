"""Claude Code hook: append one JSON line per event to the Claude Console log.

Registered as an async command hook in ~/.claude/settings.json by install_hooks.py.
It never raises and always exits 0, so it cannot break or slow a session.
"""
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console import paths, redact  # noqa: E402

TAIL_BYTES = 512 * 1024
_ROUTE = re.compile(r"^[\s`*>\-]*Route:\s*(.+?)[\s`*]*$", re.M)
_STOP = re.compile(r"^[\s`*>\-]*STOP:\s*(.+?)[\s`*]*$", re.M)
# A model that obeys the STOP footer with nothing to ask writes `STOP: none`: not a question.
_NO_QUESTION = {"none", "n/a", "-", ""}
# The verifier agent's report: `VERDICT: PASS | FAIL`, then `failing: <file:line> - <error>` lines.
_VERDICT = re.compile(r"^[\s`*>\-]*VERDICT:\s*(PASS|FAIL)\b[ \t`*:\-]*(.*?)[ \t`*]*$", re.M)
_FAILING = re.compile(r"^[\s`*>\-]*failing:\s*(.+?)[\s`*]*$", re.M)
# A block Claude Code or an extension puts before (or instead of) Fred's text, e.g.
# <browser_instruction>, <task-notification>. Fred's own pastes (<pasted_content>) stay.
_INJECTED = re.compile(r"\s*<(?!pasted_content\b)([A-Za-z][\w-]*)[^>]*>.*?</\1>\s*", re.S)


def strip_injected(text: str) -> str:
    """The prompt without the injected blocks at its start."""
    text = str(text or "")
    for _ in range(10):
        m = _INJECTED.match(text)
        if not m:
            break
        text = text[m.end():]
    return text


def project_root(cwd: str):
    """The nearest folder above `cwd` that holds .git, or None."""
    if not cwd:
        return None
    p = Path(cwd)
    for folder in [p, *p.parents][:30]:
        if (folder / ".git").exists():
            return folder
    return None


def last_match(rx, text: str) -> str:
    found = rx.findall(text or "")
    return found[-1].strip() if found else ""


def verdict(text: str) -> dict:
    """The last `VERDICT: PASS|FAIL` line, with its detail (else the first `failing:` line)."""
    found = _VERDICT.findall(text or "")
    if not found:
        return {}
    word, detail = found[-1]
    if not detail and word == "FAIL":
        m = _FAILING.search(text)
        detail = m.group(1) if m else ""
    out = {"verdict": word}
    if detail:
        out["verdict_detail"] = redact.clip(redact.mask(detail), 160)
    return out


def transcript_tail(path, sidechain: bool = False) -> dict:
    """Model, context tokens and entrypoint of the last assistant line of a transcript."""
    out = {}
    if not path:
        return out
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - TAIL_BYTES))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError, ValueError):
        return out
    for line in reversed(lines):
        if '"assistant"' not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("type") != "assistant":
            continue
        if bool(rec.get("isSidechain")) != sidechain:
            continue
        msg = rec.get("message") or {}
        usage = msg.get("usage") or {}
        if not usage or msg.get("model") in (None, "<synthetic>"):
            continue
        out["model"] = msg["model"]
        out["context_tokens"] = (int(usage.get("input_tokens") or 0)
                                 + int(usage.get("cache_read_input_tokens") or 0)
                                 + int(usage.get("cache_creation_input_tokens") or 0))
        if rec.get("entrypoint"):
            out["entrypoint"] = rec["entrypoint"]
        return out
    return out


def build_record(data: dict, now: float = None) -> dict:
    """Turn one hook input into one small, masked log record."""
    event = data.get("hook_event_name", "")
    cwd = data.get("cwd") or ""
    root = project_root(cwd)
    effort = data.get("effort")
    rec = {
        "ts": round(time.time() if now is None else now, 3),
        "event": event,
        "session_id": data.get("session_id", ""),
        "cwd": cwd,
        "project": root.name if root else (Path(cwd).name if cwd else ""),
        "project_dir": str(root) if root else cwd,
        "agent_id": data.get("agent_id"),
        "agent_type": data.get("agent_type"),
        "permission_mode": data.get("permission_mode"),
        "effort": effort.get("level") if isinstance(effort, dict) else effort,
    }
    tool = data.get("tool_name")
    if event == "UserPromptSubmit":
        rec["prompt"] = redact.clip(redact.mask(strip_injected(data.get("prompt", ""))), 120)
    elif event in ("PreToolUse", "PermissionDenied"):
        rec["tool"] = tool
        rec["what"] = redact.summarize(tool, data.get("tool_input"), cwd)
        rec["tool_use_id"] = data.get("tool_use_id")
        if event == "PermissionDenied":
            rec["reason"] = redact.clip(data.get("reason", ""), 120)
    elif event == "SubagentStop":
        tail = transcript_tail(data.get("agent_transcript_path"), sidechain=True)
        rec["model"] = tail.get("model")
        rec["context_tokens"] = tail.get("context_tokens")
        rec.update(verdict(data.get("last_assistant_message")))
    elif event == "Stop":
        rec.update(transcript_tail(data.get("transcript_path")))
        message = data.get("last_assistant_message") or ""
        route = last_match(_ROUTE, message)
        question = last_match(_STOP, message)
        if route:
            rec["route"] = redact.clip(route, 80)
        if question.rstrip(".").lower() not in _NO_QUESTION:
            rec["stop_question"] = redact.clip(redact.mask(question), 200)
        rec.update(verdict(message))
    elif event == "StopFailure":
        rec["error"] = data.get("error") or "unknown"
        rec["error_details"] = redact.clip(redact.mask(data.get("error_details", "")), 120)
    elif event == "SessionStart":
        rec["source"] = data.get("source")
        rec["model"] = data.get("model")
    elif event == "PostCompact":
        rec["trigger"] = data.get("trigger")
    elif event == "SessionEnd":
        rec["reason"] = data.get("reason")
    return {k: v for k, v in rec.items() if v not in (None, "")}


def append(rec: dict) -> None:
    """Add one line to today's events file (one write call per line)."""
    folder = paths.home()
    folder.mkdir(parents=True, exist_ok=True)
    day = time.strftime("%Y-%m-%d", time.localtime(rec["ts"]))
    line = json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(folder / f"events-{day}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(line)


def log_error() -> None:
    try:
        path = paths.home() / "hook-errors.log"
        if path.exists() and path.stat().st_size > 1_000_000:
            path.unlink()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
    except Exception:
        pass


def main() -> int:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        data = json.loads(raw) if raw.strip() else {}
        if isinstance(data, dict) and data.get("hook_event_name"):
            append(build_record(data))
    except Exception:
        log_error()
    return 0


if __name__ == "__main__":
    sys.exit(main())
