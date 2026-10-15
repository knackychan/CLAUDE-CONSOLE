"""The OpenCode adapter: `opencode run --standalone --format json` with the prompt in a file (README 3.3, 3.4)."""
import json

from .. import claude_cli, redact
from . import section, which

NAME = "opencode"
EXE_NAMES = ("opencode.exe", "opencode.cmd", "opencode")
TIERS = ("haiku", "opus")
CAPS = False
INTERRUPT = False
RESUME = True
HOOKS = False
MESSAGE = "Do the task in the attached file."
RESULT_TYPES = ("session.idle", "message.completed", "done", "result")
CHAT_TEXT = 4000


def find_exe(cfg: dict):
    return which(EXE_NAMES, section(cfg, NAME).get("exe", ""))


def version_command(exe: list) -> list:
    return list(exe) + ["--version"]


def run_command(exe: list, model: str, effort: str, cwd: str, session_id: str, *, prompt: str,
                resume: bool = False, fork: str = "", read_only: bool = False, budget: float = 0.0,
                max_turns: int = 0, name: str = "", variants=None, prompt_file: str = ""):
    """The prompt rides in `prompt_file` (written by runs), never in argv; cwd is the process cwd."""
    if not prompt_file:
        raise ValueError("opencode: prompt_file is required")
    variant = (variants or {}).get(effort, "")
    m = model + ("#" + variant if variant else "")
    cmd = list(exe) + ["run", "--standalone", "--format", "json", "--auto", "-m", m, "--file", prompt_file]
    if name:
        cmd += ["--title", name]
    if fork:
        cmd += ["--session", fork, "--fork"]
    elif resume:
        cmd += ["--session", session_id]
    cmd += [MESSAGE]
    return cmd, None


def env(read_only: bool) -> dict:
    out = {"OPENCODE_DISABLE_AUTOUPDATE": "1"}
    if read_only:
        out["OPENCODE_PERMISSION"] = json.dumps({"edit": "deny", "bash": "deny", "webfetch": "deny"})
    return out


def is_result(line: dict) -> bool:
    kind = line.get("type")
    return isinstance(kind, str) and (kind in RESULT_TYPES or kind.endswith(".idle"))


def _text_of(d: dict) -> str:
    """The longest string "text" of a line, also one level under "part" or "message"."""
    found = []
    for src in (d, d.get("part"), d.get("message")):
        if isinstance(src, dict) and isinstance(src.get("text"), str):
            found.append(src["text"])
    return max(found, key=len) if found else ""


def _exit_code(lines: list):
    for d in reversed(lines):
        if d.get("type") == "cc_exit":
            return d.get("code")
    return None


def _tokens(lines: list):
    for d in reversed(lines):
        t = d.get("tokens")
        if isinstance(t, dict) and ("input" in t or "output" in t):
            cache = t.get("cache")
            read = cache.get("read", 0) if isinstance(cache, dict) else 0
            return {"input": t.get("input") or 0, "output": t.get("output") or 0, "cache_read": read or 0,
                    "context": None}
    return None


def summary(lines: list) -> dict:
    final, sid = "", ""
    for d in lines:
        text = _text_of(d)
        if text.strip():
            final = text
        if not sid:
            sid = next((d[k] for k in ("sessionID", "session_id") if isinstance(d.get(k), str)), "")
    code = _exit_code(lines)
    return {"final": final, "subtype": "success" if code == 0 else "error", "cost": None,
            "tokens": _tokens(lines), "session_id": sid, "denials": [], "exit_cap": False}


def chat(lines: list, cwd: str) -> list:
    items = []
    for d in lines:
        if "raw" in d:
            items.append({"role": "note", "text": redact.clip(d["raw"], 300)})
        elif d.get("type") == "cc_prompt":
            items.append({"role": "you", "text": d.get("text", "")[:CHAT_TEXT], "ts": d.get("ts"),
                          "files": d.get("files") or []})
        elif d.get("type") == "cc_exit":
            items.append({"role": "result", "text": "success" if d.get("code") == 0 else f"error · exit {d.get('code')}"})
        elif isinstance(d.get("tool"), str):
            what = d.get("title") or d.get("input") or ""
            items.append({"role": "tool", "text": f"{d['tool']} {redact.clip(str(what), 300)}".strip()})
        else:
            text = _text_of(d)
            if text.strip():
                items.append({"role": "claude", "text": text[:CHAT_TEXT], "files": []})
    return items


def stop(proc) -> str:
    claude_cli.kill_tree(proc.pid)
    return "kill"


def terminal_command(exe: list, session_id: str, model: str, effort: str):
    return list(exe) + ["-s", session_id, "-m", model]
