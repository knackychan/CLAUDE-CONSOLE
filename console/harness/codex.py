"""The Codex CLI adapter: `codex exec --json -` with the prompt on stdin (README 3.3, 3.4)."""
from .. import claude_cli, redact
from . import section, which

NAME = "codex"
EXE_NAMES = ("codex.exe", "codex.cmd", "codex")
TIERS = tuple(claude_cli.MODELS)
CAPS = False
INTERRUPT = False
RESUME = True
HOOKS = False
EFFORT = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}
CHAT_TEXT = 4000


def find_exe(cfg: dict):
    return which(EXE_NAMES, section(cfg, NAME).get("exe", ""))


def version_command(exe: list) -> list:
    return list(exe) + ["--version"]


def run_command(exe: list, model: str, effort: str, cwd: str, session_id: str, *, prompt: str,
                resume: bool = False, fork: str = "", read_only: bool = False, budget: float = 0.0,
                max_turns: int = 0, name: str = ""):
    """Options stand before `resume` / `fork`; the prompt is read from stdin (`-`). budget, max_turns and name
    have no Codex flag and are ignored (step_timeout_s is the cap)."""
    cmd = list(exe) + ["exec", "--json", "-C", cwd, "--skip-git-repo-check", "-m", model,
                       "-c", f'model_reasoning_effort="{EFFORT.get(effort, "medium")}"',
                       "-s", "read-only" if read_only else "workspace-write"]
    if fork:
        cmd += ["fork", fork]
    elif resume:
        cmd += ["resume", session_id]
    cmd += ["-"]
    return cmd, (prompt + claude_cli.STOP_FOOTER).encode("utf-8")


def env(read_only: bool) -> dict:
    return {}


def is_result(line: dict) -> bool:
    return line.get("type") in ("turn.completed", "turn.failed")


def _item_text(item: dict) -> str:
    text = item.get("text")
    if isinstance(text, str) and text:
        return text
    strings = [v for v in item.values() if isinstance(v, str)]
    return max(strings, key=len) if strings else ""


def summary(lines: list) -> dict:
    final, subtype, tokens, sid = "", "", None, ""
    for d in lines:
        kind = d.get("type")
        if kind == "thread.started" and isinstance(d.get("thread_id"), str):
            sid = d["thread_id"]
        elif kind == "item.completed":
            item = d.get("item") or {}
            if item.get("type") == "agent_message":
                final = _item_text(item)
        elif kind == "turn.completed":
            subtype = "success"
            usage = d.get("usage")
            if isinstance(usage, dict):
                cached = usage.get("cached_input_tokens") or 0
                tokens = {"input": max((usage.get("input_tokens") or 0) - cached, 0),
                          "output": usage.get("output_tokens") or 0, "cache_read": cached, "context": None}
        elif kind == "turn.failed" or (kind == "error" and subtype != "success"):
            subtype = "error"
        elif kind == "turn.started":
            subtype = ""
    return {"final": final, "subtype": subtype, "cost": None, "tokens": tokens, "session_id": sid,
            "denials": [], "exit_cap": False}


def _tool_text(item: dict) -> str:
    kind = item.get("type", "")
    if kind == "command_execution":
        what = item.get("command", "")
    elif kind == "file_change":
        changes = item.get("changes")
        what = ", ".join(str(c.get("path", c)) if isinstance(c, dict) else str(c) for c in changes) \
            if isinstance(changes, list) else ""
    elif kind == "mcp_tool_call":
        what = item.get("tool", "")
    elif kind == "web_search":
        what = item.get("query", "")
    else:
        what = ""
    return f"{kind} {redact.clip(str(what), 300)}".strip()


def chat(lines: list, cwd: str) -> list:
    items, turns = [], 0
    for d in lines:
        kind = d.get("type")
        if "raw" in d:
            items.append({"role": "note", "text": redact.clip(d["raw"], 300)})
        elif kind == "cc_prompt":
            items.append({"role": "you", "text": d.get("text", "")[:CHAT_TEXT], "ts": d.get("ts"),
                          "files": d.get("files") or []})
        elif kind == "item.completed":
            item = d.get("item") or {}
            if item.get("type") == "agent_message":
                items.append({"role": "claude", "text": _item_text(item)[:CHAT_TEXT], "files": []})
            else:
                items.append({"role": "tool", "text": _tool_text(item)})
        elif kind == "error":
            items.append({"role": "note", "text": redact.clip(str(d.get("message", "error")), 300)})
        elif kind == "turn.completed":
            turns += 1
            items.append({"role": "result", "text": f"success · {turns} turns"})
        elif kind == "turn.failed":
            turns += 1
            items.append({"role": "result", "text": f"error · {turns} turns"})
    return items


def stop(proc) -> str:
    claude_cli.kill_tree(proc.pid)
    return "kill"


def terminal_command(exe: list, session_id: str, model: str, effort: str):
    return list(exe) + ["resume", session_id, "-m", model]
