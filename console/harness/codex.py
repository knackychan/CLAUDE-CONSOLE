"""The Codex CLI adapter: `codex exec --json -` with the prompt on stdin (README 3.3, 3.4)."""
import ctypes
import json
import os
import tomllib
from ctypes import wintypes
from pathlib import Path

from .. import claude_cli, limits, redact
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
WINDOWS = os.name == "nt"


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
    if not read_only:
        # Package installs need network access and writable package/toolchain caches.
        cmd += ["-c", "sandbox_workspace_write.network_access=true"]
        roots = _package_roots(cwd)
        if roots:
            cmd += ["-c", "sandbox_workspace_write.writable_roots=" + json.dumps(roots, ensure_ascii=False)]
    if env(read_only):
        # Keep Store app aliases available to commands after Codex selects a runnable shell.
        cmd += ["-c", "shell_environment_policy.set.PATH=" + json.dumps(os.environ.get("PATH", ""))]
    if fork:
        cmd += ["fork", fork]
    elif resume:
        cmd += ["resume", session_id]
    cmd += ["-"]
    return cmd, (prompt + claude_cli.STOP_FOOTER).encode("utf-8")


def _package_roots(cwd: str) -> list[str]:
    """Existing npm and Rust storage folders; resolve relative overrides against the step's workspace."""
    npm = os.environ.get("npm_config_cache") or (
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "npm-cache") if WINDOWS
        else os.path.join(os.path.expanduser("~"), ".npm"))
    roots = []
    for value in (npm, os.environ.get("CARGO_HOME") or os.path.expanduser("~/.cargo"),
                  os.environ.get("RUSTUP_HOME") or os.path.expanduser("~/.rustup")):
        path = Path(value)
        if not path.is_absolute():
            path = Path(cwd) / path
        if path.is_dir():
            root = path.resolve().as_posix()
            if root not in roots:
                roots.append(root)
    return roots


def env(read_only: bool) -> dict:
    if os.name == "nt":
        path = os.environ.get("PATH", "")
        # Store PowerShell aliases cannot start with Codex's restricted Windows token.
        kept = [p for p in path.split(os.pathsep) if not (
            "windowsapps" in p.lower().replace("\\", "/").split("/")
            and (Path(p) / "pwsh.exe").is_file())]
        filtered = os.pathsep.join(kept)
        if filtered != path:
            return {"PATH": filtered}
    return {}


def write_block(cwd: str) -> str:
    """Plan 43: why Codex's Windows sandbox cannot write in `cwd`, else "". Reads only: the sandbox mode in
    config.toml and the folder's owner; anything unreadable counts as fine (D2)."""
    if not WINDOWS or not cwd:
        return ""
    if _sandbox_mode() == "unelevated":
        return ('codex: its Windows sandbox is "unelevated", where Python temp folders fail; set '
                '[windows] sandbox = "elevated" in ~/.codex/config.toml and run codex once')
    if not _owned_by_me(cwd):
        who = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
        return (f"codex: {cwd} belongs to another Windows account, so its sandbox cannot write there; "
                f'in an admin PowerShell: icacls "{cwd}" /setowner "{who}"')
    return ""


def _sandbox_mode() -> str:
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    try:
        with open(os.path.join(home, "config.toml"), "rb") as f:
            win = tomllib.load(f).get("windows")
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    return str(win.get("sandbox", "")) if isinstance(win, dict) else ""


def _owned_by_me(path: str) -> bool:
    """True when this process's user owns `path`; True too when Windows cannot tell (no false alarm)."""
    advapi, kernel = ctypes.WinDLL("advapi32"), ctypes.WinDLL("kernel32")
    advapi.GetNamedSecurityInfoW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD,
                                            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                          ctypes.POINTER(wintypes.DWORD)]
    advapi.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    owner, sd = ctypes.c_void_p(), ctypes.c_void_p()
    if advapi.GetNamedSecurityInfoW(path, 1, 1, ctypes.byref(owner), None, None, None, ctypes.byref(sd)):
        return True  # SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION
    token = wintypes.HANDLE()
    try:
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
            return True
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))  # TokenUser
        buf = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, buf, size, ctypes.byref(size)):
            return True
        return bool(advapi.EqualSid(owner, ctypes.c_void_p.from_buffer(buf).value))  # TOKEN_USER.User.Sid
    finally:
        if token:
            kernel.CloseHandle(token)
        kernel.LocalFree(sd)


def is_result(line: dict) -> bool:
    return line.get("type") in ("turn.completed", "turn.failed")


def _item_text(item: dict) -> str:
    text = item.get("text")
    if isinstance(text, str) and text:
        return text
    strings = [v for v in item.values() if isinstance(v, str)]
    return max(strings, key=len) if strings else ""


def summary(lines: list) -> dict:
    final, subtype, tokens, sid, hit = "", "", None, "", None
    shell_failed = False
    write_failed = False
    for d in lines:
        kind = d.get("type")
        error = d.get("error")
        message = d.get("message") or (error.get("message") if isinstance(error, dict) else "")
        if kind in ("error", "turn.failed") and isinstance(message, str) and limits.TEXT.search(message):
            hit = {"why": message[:160], "until": None, "window_s": limits.window_s(message)}
        if kind == "thread.started" and isinstance(d.get("thread_id"), str):
            sid = d["thread_id"]
        elif kind == "item.completed":
            item = d.get("item") or {}
            if item.get("type") == "command_execution":
                output = item.get("aggregated_output") or ""
                if "CreateProcessAsUserW failed:" in output or "Failed to create unified exec process:" in output:
                    shell_failed = True
                elif item.get("exit_code") == 0:
                    shell_failed = False
            if item.get("type") == "file_change":
                write_failed = item.get("status") == "failed"
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
            shell_failed = False
            write_failed = False
    if subtype == "success" and shell_failed:
        subtype = "error_shell_start"
    elif subtype == "success" and write_failed:
        subtype = "error_write_denied"
    return {"final": final, "subtype": subtype, "cost": None, "tokens": tokens, "session_id": sid,
            "denials": [], "exit_cap": False, "limit": hit}


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
    turn_lines = []
    for d in lines:
        kind = d.get("type")
        if kind == "turn.started":
            turn_lines = []
        turn_lines.append(d)
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
            status = "error" if summary(turn_lines)["subtype"] in ("error_shell_start", "error_write_denied") else "success"
            items.append({"role": "result", "text": f"{status} · {turns} turns"})
        elif kind == "turn.failed":
            turns += 1
            items.append({"role": "result", "text": f"error · {turns} turns"})
    return items


def stop(proc) -> str:
    claude_cli.kill_tree(proc.pid)
    return "kill"


def terminal_command(exe: list, session_id: str, model: str, effort: str):
    return list(exe) + ["resume", session_id, "-m", model]
