"""The Command Code adapter (`cmdc`): `-p <query> --output-format json` (README 3.3, 3.4)."""
import shutil
from pathlib import Path, PurePath

from .. import claude_cli, redact
from . import codex, section, which

NAME = "cmd"
EXE_NAMES = ("cmdc.exe", "cmdc", "cmdc.cmd")  # never "cmd" or "cmd.cmd": `cmd` is Windows' shell
TIERS = ("haiku",)
CAPS = True
INTERRUPT = False
RESUME = True
HOOKS = False
EFFORT = codex.EFFORT
CHAT_TEXT = 4000
SHIM_ERROR = ('cmd: only the npm .cmd shim was found; set "exe" under harnesses.cmd to the real executable')


def find_exe(cfg: dict):
    return which(EXE_NAMES, section(cfg, NAME).get("exe", ""))


def command(exe: list) -> list:
    """Resolve the known npm entry point directly: a batch file would reparse the prompt as shell code."""
    if exe and PurePath(str(exe[0])).suffix.lower() in (".cmd", ".bat"):
        entry = Path(exe[0]).parent / "node_modules" / "command-code" / "dist" / "index.mjs"
        node = shutil.which("node.exe") or shutil.which("node")
        if not entry.is_file() or not node:
            raise ValueError(SHIM_ERROR)
        return [node, str(entry), *exe[1:]]
    return list(exe)


def version_command(exe: list) -> list:
    return command(exe) + ["--no-auto-update", "-v"]


def run_command(exe: list, model: str, effort: str, cwd: str, session_id: str, *, prompt: str,
                resume: bool = False, fork: str = "", read_only: bool = False, budget: float = 0.0,
                max_turns: int = 0, name: str = ""):
    """The query is one argv entry; an npm shim is resolved to Node and never run through a shell."""
    cmd = command(exe) + ["-p", prompt + claude_cli.STOP_FOOTER, "--output-format", "json", "--no-auto-update",
                       "--skip-onboarding", "--no-skills", "-m", model, "--effort", EFFORT.get(effort, "medium"),
                       "--permission-mode", "plan" if read_only else "accept-edits"]
    if max_turns:
        cmd += ["--max-turns", str(int(max_turns))]
    if name:
        cmd += ["-n", name]
    if fork:
        cmd += ["-r", fork, "--fork-session"]
    elif resume:
        cmd += ["--session", session_id]
    return cmd, None


def env(read_only: bool) -> dict:
    return {}


def is_result(line: dict) -> bool:
    return line.get("type") == "result" or ("result" in line and "event" not in line)


def _longest_string(d: dict) -> str:
    strings = [v for v in d.values() if isinstance(v, str)]
    return max(strings, key=len) if strings else ""


def _exit_code(lines: list):
    for d in reversed(lines):
        if d.get("type") == "cc_exit":
            return d.get("code")
    return None


def _session_id(lines: list) -> str:
    for d in lines[:5]:
        for k in ("session_id", "sessionId"):
            if isinstance(d.get(k), str):
                return d[k]
    return ""


def summary(lines: list) -> dict:
    final, assistant, tokens = "", "", None
    for d in lines:
        if is_result(d):
            final = _longest_string({k: v for k, v in d.items() if k != "type"}) or final
        elif d.get("event") == "assistant" and isinstance(d.get("text"), str) and d["text"].strip():
            assistant = d["text"]
        usage = d.get("usage")
        if isinstance(usage, dict):
            cached = usage.get("cached_input_tokens") or usage.get("cache_read_input_tokens") or 0
            tokens = {"input": usage.get("input_tokens") or 0, "output": usage.get("output_tokens") or 0,
                      "cache_read": cached, "context": None}
    code = _exit_code(lines)
    subtype = "success" if code == 0 else "error_max_turns" if code == 8 else "error"
    return {"final": final or assistant, "subtype": subtype, "cost": None, "tokens": tokens,
            "session_id": _session_id(lines), "denials": [], "exit_cap": code == 8}


def chat(lines: list, cwd: str) -> list:
    items = []
    for d in lines:
        kind = d.get("type")
        if "raw" in d:
            items.append({"role": "note", "text": redact.clip(d["raw"], 300)})
        elif kind == "cc_prompt":
            items.append({"role": "you", "text": d.get("text", "")[:CHAT_TEXT], "ts": d.get("ts"),
                          "files": d.get("files") or []})
        elif kind == "cc_exit":
            code = d.get("code")
            items.append({"role": "result", "text": "success" if code == 0 else
                          "error_max_turns" if code == 8 else f"error · exit {code}"})
        elif d.get("event") == "tool":
            what = d.get("input") or ""
            items.append({"role": "tool", "text": f"{d.get('name', '')} {redact.clip(str(what), 300)}".strip()})
        elif d.get("event") == "assistant" and isinstance(d.get("text"), str) and d["text"].strip():
            items.append({"role": "claude", "text": d["text"][:CHAT_TEXT], "files": []})
    return items


def stop(proc) -> str:
    claude_cli.kill_tree(proc.pid)
    return "kill"


def terminal_command(exe: list, session_id: str, model: str, effort: str):
    return list(exe) + ["-r", session_id, "-m", model, "--no-auto-update"]
