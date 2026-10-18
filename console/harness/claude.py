"""The Claude Code adapter: claude_cli and the stream-json shapes behind the adapter contract (no new behaviour)."""
import uuid

from .. import claude_cli, limits, redact, transcript
from . import section

NAME = "claude"
EXE_NAMES = ("claude.exe", "claude.cmd", "claude")
TIERS = tuple(claude_cli.MODELS)
CAPS = INTERRUPT = RESUME = HOOKS = True
CHAT_TEXT = 4000


def find_exe(cfg: dict):
    """harnesses.claude.exe, then the old claude_exe; claude_cli.find_exe keeps the shim rule."""
    exe = section(cfg, NAME).get("exe") or cfg.get("claude_exe", "")
    return claude_cli.find_exe({"claude_exe": exe})


def version_command(exe: list) -> list:
    return list(exe) + ["--version"]


def run_command(exe: list, model: str, effort: str, cwd: str, session_id: str, *, prompt: str,
                resume: bool = False, fork: str = "", read_only: bool = False, budget: float = 0.0,
                max_turns: int = 0, name: str = "", tools=None, disallow: tuple = (), blocks: tuple = (),
                strict_mcp: bool = False):
    """(the argument list, the stdin bytes). `cwd` and `read_only` are unused: the service sets the process cwd
    and a Claude step limits its tools through `tools` / `disallow`."""
    cmd = claude_cli.run_command(exe, model, effort, session_id, resume=resume, name=name, fork=fork,
                                 disallow=disallow, tools=tools, budget=budget, max_turns=max_turns,
                                 strict_mcp=strict_mcp)
    footer = "" if prompt.startswith("/") else claude_cli.STOP_FOOTER
    return cmd, claude_cli.user_message(prompt + footer, blocks)


def is_result(line: dict) -> bool:
    return line.get("type") == "result"


def summary(lines: list) -> dict:
    final, result, hit = "", None, None
    for d in lines:
        if d.get("type") == "assistant" and not d.get("parent_tool_use_id"):
            for block in (d.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text", "").strip():
                    final = block["text"]
        elif d.get("type") == "result":
            result = d
            text = str(d.get("result") or "")
            if d.get("is_error") and limits.TEXT.search(text):
                hit = {"why": text[:160], "until": None, "window_s": limits.window_s(text)}
        elif d.get("type") == "rate_limit_event":
            info = d.get("rate_limit_info") or {}
            if info.get("status") == "rejected" and info.get("errorCode") == "credits_required":  # plan 45: this model only
                hit = {"why": "credits required", "until": info.get("resetsAt"), "window_s": None, "model": True}
            elif info.get("status") == "rejected":
                name = str(info.get("rateLimitType") or "usage").replace("_", " ")
                hit = {"why": f"{name} limit", "until": info.get("resetsAt"), "window_s": None}
    result = result or {}
    denials = []
    for d in (result.get("permission_denials") or [])[:3]:
        tool = d.get("tool_name", "")
        denials.append({"tool": tool, "what": redact.summarize(tool, d.get("tool_input"))})
    subtype = result.get("subtype", "")
    return {"final": final, "subtype": subtype, "cost": result.get("total_cost_usd"), "tokens": None,
            "session_id": result.get("session_id", ""), "denials": denials,
            "exit_cap": subtype in ("error_max_turns", "error_max_budget_usd"), "limit": hit}


def chat(lines: list, cwd: str) -> list:
    """runs.chat's body: prompts, assistant text (with the files written before it), tool calls, results."""
    items, wrote = [], []
    for d in lines:
        kind = d.get("type")
        if "raw" in d:
            items.append({"role": "note", "text": redact.clip(d["raw"], 300)})
        elif kind == "cc_prompt":
            transcript.flush_wrote(items, wrote)
            items.append({"role": "you", "text": d.get("text", "")[:CHAT_TEXT], "ts": d.get("ts"),
                          "files": d.get("files") or []})
        elif kind == "assistant" and not d.get("parent_tool_use_id"):
            for block in (d.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text", "").strip():
                    items.append({"role": "claude", "text": block["text"][:CHAT_TEXT], "files": wrote[:]})
                    wrote.clear()
                elif block.get("type") == "tool_use":
                    what = redact.summarize(block.get("name"), block.get("input"), cwd)
                    items.append({"role": "tool", "text": f"{block.get('name', '')} {what}".strip()})
                    transcript.note_write(wrote, block, cwd)
        elif kind == "user" and not d.get("parent_tool_use_id"):
            content = (d.get("message") or {}).get("content")
            if isinstance(content, list) and any("[Request interrupted" in str(b.get("text", ""))
                                                 for b in content if isinstance(b, dict)):
                items.append({"role": "note", "text": "stopped"})
        elif kind == "result":
            transcript.flush_wrote(items, wrote)
            cost = d.get("total_cost_usd") or 0
            denials = len(d.get("permission_denials") or [])
            text = f"{d.get('subtype', '')} · ${cost:.2f} · {d.get('num_turns', 0)} turns"
            if denials:
                text += f" · {denials} denied"
            items.append({"role": "result", "text": text})
    transcript.flush_wrote(items, wrote)
    return items


def stop(proc) -> str:
    """Interrupt over stdin; never a kill. Raises OSError / ValueError when stdin is closed (the caller knows)."""
    proc.stdin.write(claude_cli.interrupt_message("stop-" + uuid.uuid4().hex[:8]))
    proc.stdin.flush()
    return "interrupt"


def terminal_command(exe: list, session_id: str, model: str, effort: str) -> list:
    return claude_cli.terminal_command(exe, session_id, model, effort)


def env(read_only: bool) -> dict:
    return {}
