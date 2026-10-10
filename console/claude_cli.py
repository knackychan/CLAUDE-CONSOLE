"""Everything about the `claude` executable: where it is, the commands we run, the child environment,
and the Windows process helpers. Commands are argument lists, never shell strings."""
import ctypes
import json
import os
import shutil
import subprocess
from pathlib import Path

MODELS = ["haiku", "sonnet", "opus", "fable"]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]

# Set by a Claude Code session for its own children. A run started from a window that was itself
# launched from a Claude Code terminal must not inherit them (wrong entrypoint, wrong parent session).
SESSION_ENV = {
    "CLAUDECODE", "CLAUDE_AGENT_SDK_VERSION", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_SSE_PORT", "CLAUDE_EFFORT",
    "CLAUDE_PID",
}
STOP_FOOTER = ("\n\nIf you must stop for a decision only Fred can make, end your final message with "
               "one line: STOP: <question>")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
BREAKAWAY = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)


def find_exe(cfg: dict):
    """The real claude.exe. Never the npm .cmd shim: batch files re-parse their arguments."""
    if cfg.get("claude_exe"):
        return cfg["claude_exe"]
    exe = shutil.which("claude.exe")
    if exe:
        return exe
    shim = shutil.which("claude.cmd") or shutil.which("claude")
    if shim:
        cand = Path(shim).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if cand.exists():
            return str(cand)
    return None


def child_env() -> dict:
    return {k: v for k, v in os.environ.items() if k.upper() not in SESSION_ENV}


def prep_command(exe: list, model: str, schema: dict) -> list:
    """Read-only, no hooks (keeps Prep out of the event log), no skills or MCP (cheaper)."""
    return exe + ["-p", "--model", model, "--effort", "low", "--tools", "Read,Grep,Glob",
                  "--permission-mode", "dontAsk", "--disable-slash-commands", "--strict-mcp-config",
                  "--settings", '{"disableAllHooks": true}', "--no-session-persistence",
                  "--output-format", "json", "--json-schema", json.dumps(schema)]


def run_command(exe: list, model: str, effort: str, session_id: str, resume: bool = False,
                name: str = "", fork: str = "") -> list:
    """D5: auto mode, nobody answers prompts (a denial ends up in the result). Prompts go in on stdin.
    `fork`: start `session_id` as a copy of that chat (its context, a new id; the original is not touched)."""
    cmd = exe + ["-p", "--model", model, "--effort", effort, "--permission-mode", "auto",
                 "--permission-prompts", "none", "--input-format", "stream-json",
                 "--output-format", "stream-json", "--verbose"]
    if fork:
        cmd += ["--resume", fork, "--fork-session", "--session-id", session_id]
    elif resume:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id]
    if name and not resume:
        cmd += ["--name", name]
    return cmd


def model_alias(model: str) -> str:
    """claude-sonnet-5-5 -> sonnet (the names routes use); "" when unknown."""
    low = str(model or "").lower()
    return next((m for m in MODELS if m in low), "")


def terminal_command(exe: list, session_id: str, model: str = "", effort: str = "") -> list:
    """Interactive resume on the run's own model and effort (not Fred's default)."""
    cmd = exe + ["--resume", session_id]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    return cmd


def user_message(text: str) -> bytes:
    msg = {"type": "user", "message": {"role": "user", "content": text}}
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")


def interrupt_message(request_id: str) -> bytes:
    msg = {"type": "control_request", "request_id": request_id, "request": {"subtype": "interrupt"}}
    return (json.dumps(msg) + "\n").encode("utf-8")


def pid_alive(pid) -> bool:
    if not pid:
        return False
    if os.name != "nt":
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False
    k = ctypes.windll.kernel32
    handle = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(handle, ctypes.byref(code))
    k.CloseHandle(handle)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


def kill_tree(pid) -> None:
    """Last resort for a run this service did not start (no stdin to send an interrupt to)."""
    subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True,
                   creationflags=NO_WINDOW)


def git_head(cwd: str) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True,
                             timeout=10, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def git_changed(cwd: str, commit: str):
    """Files changed since `commit` (committed or not) plus untracked files; None if unknown."""
    if not commit:
        return None
    names = set()
    for cmd in (["git", "diff", "--name-only", commit], ["git", "ls-files", "--others", "--exclude-standard"]):
        try:
            out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10,
                                 creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        names.update(line for line in out.stdout.splitlines() if line.strip())
    return len(names)
