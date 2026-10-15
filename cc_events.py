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
try:
    from console import paths, redact  # noqa: E402
except Exception:  # plan 34 F1: a broken console package must not break the session (never raise, exit 0)
    paths = redact = None

TAIL_BYTES = 512 * 1024
HEAD_BYTES = 64 * 1024  # a Codex rollout's session_meta (its entrypoint) stands on the first line
RULES_READ_MAX = 4 * 1024 * 1024  # a rules file bigger than this is counted by size only
HARNESSES = ("claude", "codex", "opencode", "cmd")
# Each CLI's tool name and input keys -> Claude's, so State and the Steps line need no second vocabulary
# (README 3.3). A name that is not here is kept as it came.
TOOL_MAP = {
    "codex": {
        "exec_command": ("Bash", {"cmd": "command"}),
        "shell": ("Bash", {"cmd": "command"}),
        "local_shell": ("Bash", {"cmd": "command"}),
        "exec": ("Bash", {"cmd": "command"}),
        "view_image": ("Read", {"path": "file_path"}),
        "apply_patch": ("Edit", {}),
        "web_search": ("WebSearch", {}),
        "spawn_agent": ("Agent", {"task_name": "description"}),
        "request_user_input": ("AskUserQuestion", {}),
        "request_user_input_async": ("AskUserQuestion", {}),
    },
    "cmd": {
        "shell_command": ("Bash", {}),
        "powershell": ("PowerShell", {}),
        "read_file": ("Read", {}),
        "write_file": ("Write", {}),
        "edit_file": ("Edit", {}),
        "grep": ("Grep", {}),
        "glob": ("Glob", {}),
        "read_directory": ("Glob", {"path": "pattern"}),
        "web_fetch": ("WebFetch", {}),
        "activate_skill": ("Skill", {"name": "skill"}),
        "todo_write": ("TodoWrite", {}),
        "ask_user_question": ("AskUserQuestion", {}),
    },
    "opencode": {
        "bash": ("Bash", {}),
        "shell": ("Bash", {}),
        "read": ("Read", {"filePath": "file_path"}),
        "write": ("Write", {"filePath": "file_path"}),
        "edit": ("Edit", {"filePath": "file_path"}),
        "patch": ("Edit", {"filePath": "file_path"}),
        "grep": ("Grep", {}),
        "glob": ("Glob", {}),
        "list": ("Glob", {"path": "pattern"}),
        "webfetch": ("WebFetch", {}),
        "websearch": ("WebSearch", {}),
        "task": ("Agent", {}),
        "subagent": ("Agent", {}),
        "skill": ("Skill", {"name": "skill"}),
        "todowrite": ("TodoWrite", {}),
        "question": ("AskUserQuestion", {}),
    },
}
_PATCH_FILE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+?)\s*$", re.M)
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
# The service reads the transcript for the estimated cost (console/usage.py): a path, never content.
TRANSCRIPT_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop")


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


def rules_file(path, root) -> dict:
    """A loaded CLAUDE.md / rules file: a short name (inside the project, or ~/...), lines, bytes."""
    if not path:
        return {}
    p = Path(path)
    name = p.as_posix()
    for base, prefix in ((root, ""), (Path.home(), "~/")):
        if base and p.is_relative_to(base):
            name = prefix + p.relative_to(base).as_posix()
            break
    out = {"file": name}
    try:
        out["bytes"] = p.stat().st_size
        with open(p, "rb") as fh:
            data = fh.read(RULES_READ_MAX)
    except OSError:
        return out
    out["lines"] = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
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


def harness_arg(argv: list) -> str:
    """The CLI named by `--harness <name>`; absent or unknown means Claude (its install passes no argument)."""
    for i, arg in enumerate(argv):
        if arg == "--harness" and i + 1 < len(argv) and argv[i + 1] in HARNESSES:
            return argv[i + 1]
    return "claude"


def patch_path(text) -> str:
    """The first `*** Update|Add|Delete File: <path>` of a Codex apply_patch text, or ""."""
    m = _PATCH_FILE.search(str(text or ""))
    return m.group(1).strip() if m else ""


def strip_ide_context(text) -> str:
    """Codex VS Code puts its editor state before the prompt: keep what follows the last `## My request:`."""
    text = str(text or "")
    at = text.rfind("## My request:")
    return text[at + len("## My request:"):].strip() if at >= 0 else text


def map_tool(harness: str, tool, tool_input) -> tuple:
    """(Claude's tool name, the input with Claude's keys) for one CLI (README 3.3). A name or a key that is
    not in the table is kept as it came, so `redact.summarize` gives "" for a tool it does not know."""
    name = str(tool or "")
    claude, keys = (TOOL_MAP.get(harness) or {}).get(name, (name, {}))
    raw = tool_input if isinstance(tool_input, dict) else {}
    out = {}
    for key, value in raw.items():
        out[keys.get(key, key)] = value
    if name == "apply_patch":  # the patch text itself names the file
        text = tool_input if isinstance(tool_input, str) else next(
            (v for v in raw.values() if isinstance(v, str) and "*** " in v), "")
        out["file_path"] = patch_path(text)
    for key, value in list(out.items()):
        if isinstance(value, list) and all(isinstance(v, (str, int, float)) for v in value):
            out[key] = " ".join(str(v) for v in value)  # a Codex command arrives as a list
    return claude, out


def _tail_lines(path, limit: int = TAIL_BYTES) -> list:
    """The last lines of a file, reading at most `limit` bytes from its end; [] when it cannot be read."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            start = max(0, fh.tell() - limit)
            fh.seek(start)
            data = fh.read()
    except (OSError, TypeError, ValueError):
        return []
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[1:] if start else lines  # the first line was cut in the middle


def _head_source(path) -> str:
    """The `source` of the first `session_meta` in the head of a Codex rollout ("vscode", "cli", "exec")."""
    try:
        with open(path, "rb") as fh:
            data = fh.read(HEAD_BYTES)
    except (OSError, TypeError, ValueError):
        return ""
    for line in data.decode("utf-8", "replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("type") == "session_meta":
            payload = rec.get("payload")
            return str((payload or {}).get("source") or "")
    return ""


def _text_blocks(content) -> str:
    """The text blocks of one Command Code message, joined ("" when there are none)."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    return "\n".join(b["text"] for b in content
                     if isinstance(b, dict) and b.get("type") == "text"
                     and isinstance(b.get("text"), str)).strip()


def _meta_entrypoint(path) -> str:
    """`entrypoint` of the `<id>.meta.json` beside a Command Code transcript, or ""."""
    name = str(path or "")
    if not name.endswith(".jsonl"):
        return ""
    try:
        with open(name[:-6] + ".meta.json", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, TypeError):
        return ""
    return str(data.get("entrypoint") or "") if isinstance(data, dict) else ""


def codex_tail(path) -> dict:
    """Model, effort, context tokens, turn tokens and entrypoint of a Codex rollout's JSONL (README 3.4)."""
    lines = _tail_lines(path)
    if not lines:
        return {}
    model = effort = entrypoint = ""
    context, seen_user, sums = None, False, None
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        kind, payload = (rec.get("type"), rec.get("payload")) if isinstance(rec, dict) else (None, None)
        if not isinstance(payload, dict):
            continue
        if kind == "session_meta":
            entrypoint = str(payload.get("source") or entrypoint)
        elif kind == "turn_context":
            model = payload.get("model") or model
            effort = payload.get("effort") or effort
        elif kind == "event_msg":
            if payload.get("type") == "user_message":
                seen_user, sums = True, {"input": 0, "output": 0, "cache_read": 0}
            elif payload.get("type") == "token_count":
                last = (payload.get("info") or {}).get("last_token_usage")
                if not isinstance(last, dict):
                    continue
                if isinstance(last.get("input_tokens"), (int, float)):
                    context = int(last["input_tokens"])
                if sums is not None:
                    cached = int(last.get("cached_input_tokens") or 0)
                    sums["input"] += max(int(last.get("input_tokens") or 0) - cached, 0)
                    sums["output"] += int(last.get("output_tokens") or 0)
                    sums["cache_read"] += cached
    if not seen_user:
        sums = None
    out = {"model": model, "effort": effort, "context_tokens": context, "tokens": sums,
           "entrypoint": entrypoint or _head_source(path)}
    return {k: v for k, v in out.items() if v not in (None, "")}


def cmd_tail(path) -> dict:
    """Model, effort, context tokens, turn tokens, reply and prompt of a Command Code transcript (README 3.4)."""
    lines = _tail_lines(path)
    if not lines:
        return {}
    model = effort = prompt = reply = ""
    context, sums = None, None
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("type") != "message":
            continue
        msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
        words = _text_blocks(msg.get("content"))
        if msg.get("role") == "user":
            if words:  # a real prompt: a tool result carries no text block
                prompt, reply, sums = words, "", {"input": 0, "output": 0, "cache_read": 0}
            continue
        if msg.get("role") != "assistant":
            continue
        model = rec.get("model") or model
        effort = rec.get("effort") or effort
        usage = rec.get("usage") if isinstance(rec.get("usage"), dict) else {}
        if isinstance(usage.get("inputTokens"), (int, float)):
            context = int(usage["inputTokens"])
        if sums is not None:
            read = int(usage.get("cacheReadTokens") or 0)
            sums["input"] += max(int(usage.get("inputTokens") or 0) - read, 0)
            sums["output"] += int(usage.get("outputTokens") or 0)
            sums["cache_read"] += read
            reply = words or reply
    out = {"model": model, "effort": effort, "context_tokens": context, "tokens": sums,
           "reply_text": reply, "prompt": prompt, "entrypoint": _meta_entrypoint(path)}
    return {k: v for k, v in out.items() if v not in (None, "")}


def harness_tail(harness: str, path) -> dict:
    """The transcript tail of one CLI: Codex's rollout, Command Code's transcript, nothing for OpenCode."""
    if harness == "codex":
        return codex_tail(path)
    if harness == "cmd":
        return cmd_tail(path)
    return {}


def _three_ints(tokens) -> bool:
    return isinstance(tokens, dict) and all(isinstance(tokens.get(k), int)
                                            for k in ("input", "output", "cache_read"))


def build_record(data: dict, now: float = None, harness: str = "claude", env: dict = None) -> dict:
    """Turn one hook input into one small, masked log record. `harness` names the CLI that sent it
    (README 3.1): a Claude record is unchanged, another carries `"harness"` and, when `CC_CONSOLE_SID`
    is set, the Console's own session id (README 3.5)."""
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
    other = harness != "claude"
    if other:
        rec["harness"] = harness
        env = os.environ if env is None else env
        if env.get("CC_CONSOLE_SID"):
            rec["harness_session"] = data.get("session_id", "")
            rec["session_id"] = env["CC_CONSOLE_SID"]
    tool = data.get("tool_name")
    if event == "UserPromptSubmit":
        prompt = data.get("prompt", "")
        if harness == "codex":
            prompt = strip_ide_context(prompt)
        rec["prompt"] = redact.clip(redact.mask(strip_injected(prompt)), 120)
    elif event in ("PreToolUse", "PermissionDenied"):
        tool_input = data.get("tool_input")
        if other:
            tool, tool_input = map_tool(harness, tool, tool_input)
        rec["tool"] = tool
        rec["what"] = redact.summarize(tool, tool_input, cwd)
        rec["tool_use_id"] = data.get("tool_use_id")
        if event == "PermissionDenied":
            rec["reason"] = redact.clip(redact.mask(data.get("reason", "")), 120)
    elif event == "SubagentStop":
        if other:
            tail = harness_tail(harness, data.get("agent_transcript_path"))
            rec["model"] = tail.get("model") or data.get("model")
            rec["context_tokens"] = tail.get("context_tokens") if tail.get("context_tokens") is not None \
                else data.get("context_tokens")
        else:
            tail = transcript_tail(data.get("agent_transcript_path"), sidechain=True)
            rec["model"] = tail.get("model")
            rec["context_tokens"] = tail.get("context_tokens")
        rec.update(verdict(data.get("last_assistant_message")))
    elif event == "Stop":
        tail = harness_tail(harness, data.get("transcript_path")) if other \
            else transcript_tail(data.get("transcript_path"))
        if other:
            rec["model"] = tail.get("model") or data.get("model")
            if tail.get("context_tokens") is not None:
                rec["context_tokens"] = tail["context_tokens"]
            elif data.get("context_tokens") is not None:
                rec["context_tokens"] = data["context_tokens"]
            tokens = tail.get("tokens") if isinstance(tail.get("tokens"), dict) else data.get("tokens")
            if _three_ints(tokens):
                rec["tokens"] = {k: int(tokens[k]) for k in ("input", "output", "cache_read")}
            if tail.get("entrypoint") or data.get("entrypoint"):
                rec["entrypoint"] = tail.get("entrypoint") or data["entrypoint"]
            if tail.get("effort") and not rec.get("effort"):
                rec["effort"] = tail["effort"]
            if tail.get("prompt"):
                rec["prompt"] = redact.clip(redact.mask(tail["prompt"]), 120)
        else:
            rec.update(tail)
        message = data.get("last_assistant_message") or (tail.get("reply_text", "") if other else "")
        route = last_match(_ROUTE, message)
        question = last_match(_STOP, message)
        if route:
            rec["route"] = redact.clip(route, 80)
        if question.rstrip(".").lower() not in _NO_QUESTION:
            rec["stop_question"] = redact.clip(redact.mask(question), 200)
        rec.update(verdict(message))
        rec["reply"] = redact.clip(redact.mask(message.lstrip("#*>`- \t\r\n")), 120)  # the list shows where the chat stands
    elif event == "StopFailure":
        rec["error"] = data.get("error") or "unknown"
        rec["error_details"] = redact.clip(redact.mask(data.get("error_details", "")), 120)
    elif event == "SessionStart":
        rec["source"] = data.get("source")
        rec["model"] = data.get("model")
        if other and data.get("entrypoint"):
            rec["entrypoint"] = data.get("entrypoint")
    elif event == "PostCompact":
        rec["trigger"] = data.get("trigger")
    elif event == "SessionEnd":
        rec["reason"] = data.get("reason")
    elif event == "InstructionsLoaded":
        rec.update(rules_file(data.get("file_path"), root))
        rec["scope"] = data.get("memory_type")
        rec["load_reason"] = data.get("load_reason")
    if event in TRANSCRIPT_EVENTS:
        rec["transcript_path"] = data.get("transcript_path")
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
    if paths is None or redact is None:  # plan 34 F1: the console package did not import; nothing to log with
        try:
            sys.stdin.buffer.read()  # take the payload so Claude Code's write never meets a closed pipe
        except Exception:
            pass
        return 0
    try:
        harness = harness_arg(sys.argv[1:])
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        data = json.loads(raw) if raw.strip() else {}
        if isinstance(data, dict) and data.get("hook_event_name"):
            append(build_record(data, harness=harness))
    except Exception:
        log_error()
    return 0


if __name__ == "__main__":
    sys.exit(main())
