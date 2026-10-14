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


def brief_command(exe: list, model: str, schema: dict) -> list:
    """Prep's command with no tools at all and six turns: the brief pass reads nothing and decides nothing. A
    structured answer takes 2 turns, a schema re-prompt one more each; 3 ended in error_max_turns live."""
    cmd = prep_command(exe, model, schema)
    cmd[cmd.index("--tools") + 1] = ""
    return cmd + ["--max-turns", "6"]


def run_command(exe: list, model: str, effort: str, session_id: str, resume: bool = False,
                name: str = "", fork: str = "", disallow: tuple = (), tools: str = None,
                budget: float = 0.0, max_turns: int = 0, strict_mcp: bool = False) -> list:
    """D5: auto mode, nobody answers prompts (a denial ends up in the result). Prompts go in on stdin.
    `fork`: start `session_id` as a copy of that chat (its context, a new id; the original is not touched).
    Step limits (plan 17): `disallow` tool names, `tools` (the --tools list), a spend cap, a turn cap; plan 23:
    `strict_mcp` loads no MCP server (--strict-mcp-config with no --mcp-config, as Prep runs)."""
    cmd = exe + ["-p", "--model", model, "--effort", effort, "--permission-mode", "auto",
                 "--permission-prompts", "none", "--input-format", "stream-json",
                 "--output-format", "stream-json", "--verbose"]
    if disallow:
        cmd += ["--disallowedTools", ",".join(disallow)]
    if tools is not None:
        cmd += ["--tools", tools]
    if strict_mcp:
        cmd += ["--strict-mcp-config"]
    if budget and budget > 0:
        cmd += ["--max-budget-usd", f"{budget:.2f}"]
    if max_turns and max_turns > 0:
        cmd += ["--max-turns", str(int(max_turns))]
    if fork:
        cmd += ["--resume", fork, "--fork-session", "--session-id", session_id]
    elif resume:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id]
    if name and not resume:
        cmd += ["--name", name]
    return cmd


HARNESS_NAMES = ("claude", "codex", "opencode", "cmd")  # equal to harness.NAMES (a test asserts it)


def split_rung(rung: str) -> tuple:
    """"codex:gpt-6.1-sol" -> ("codex", "gpt-6.1-sol"); anything else is a Claude rung."""
    rung = str(rung or "")
    name, sep, rest = rung.partition(":")
    if sep and name in HARNESS_NAMES:
        return name, rest
    return "claude", rung


def model_alias(model: str) -> str:
    """claude-sonnet-5-5 -> sonnet (the names routes use); "" when unknown or a rung of another harness."""
    name, model = split_rung(model)
    if name != "claude":
        return ""
    low = str(model or "").lower()
    return next((m for m in MODELS if m in low), "")


def _rung_models(cfg: dict, name: str) -> dict:
    """model -> tier of one non-Claude harness: models.json (cfg["models"]), else the section's own list."""
    models = (cfg.get("models") or {}).get(name)
    if not isinstance(models, dict):
        section = (cfg.get("harnesses") or {}).get(name)
        models = section.get("models") if isinstance(section, dict) else None
    return models if isinstance(models, dict) else {}


def tier_of(model: str, cfg: dict = None) -> str:
    """The tier alias of an alias or a ladder rung (claude-opus-4-6 -> opus); for a `harness:model` rung the
    tier config gives it (needs `cfg`); "" when none."""
    name, bare = split_rung(model)
    if name == "claude":
        return model_alias(bare)
    tier = _rung_models(cfg or {}, name).get(bare)
    return tier if tier in MODELS else ""


def known_model(cfg: dict, model: str) -> bool:
    """A tier alias or a rung of the configured ladder; a `harness:model` rung whose harness is on, whose
    model is listed and whose tier the adapter may hold."""
    name, bare = split_rung(model)
    if name == "claude":
        return bare in MODELS or any(bare in rungs for rungs in (cfg.get("ladder") or {}).values())
    section = (cfg.get("harnesses") or {}).get(name)
    if not isinstance(section, dict) or section.get("on") is not True:
        return False
    tier = tier_of(model, cfg)
    if not tier:
        return False
    from . import harness  # late: harness imports this module
    try:
        return tier in harness.get(name).TIERS
    except KeyError:
        return False


def terminal_command(exe: list, session_id: str, model: str = "", effort: str = "") -> list:
    """Interactive resume on the run's own model and effort (not Fred's default)."""
    cmd = exe + ["--resume", session_id]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    return cmd


def user_message(text: str, blocks: list = ()) -> bytes:
    """`blocks`: attached files (console/attach.py), after the text in one content list."""
    content = [{"type": "text", "text": text}, *blocks] if blocks else text
    msg = {"type": "user", "message": {"role": "user", "content": content}}
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


class _BasicLimits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.c_ulong), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_ulong),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_ulong),
                ("SchedulingClass", ctypes.c_ulong)]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("Basic", _BasicLimits), ("IoCounters", ctypes.c_ulonglong * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


_service_job = None  # the job object every run joins; its handle closes when this process exits


def join_service_job(pid) -> bool:
    """Put a run into the service's job. The job kills its members when its last handle closes, which is when
    this service exits for any reason (crash, quit, restart), so no run outlives its service as an orphan.
    Windows only; False elsewhere or when the job cannot be used."""
    global _service_job
    if os.name != "nt":
        return False
    k = ctypes.windll.kernel32
    k.CreateJobObjectW.restype = ctypes.c_void_p  # handles are 64-bit: no int truncation
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    k.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    k.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    if _service_job is None:
        job = k.CreateJobObjectW(None, None)
        if not job:
            return False
        info = _ExtendedLimits()
        info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # 9: extended limits
            k.CloseHandle(job)
            return False
        _service_job = job
    proc = k.OpenProcess(0x0100 | 0x0001, False, int(pid))  # PROCESS_SET_QUOTA | PROCESS_TERMINATE
    if not proc:
        return False
    try:
        return bool(k.AssignProcessToJobObject(_service_job, proc))
    finally:
        k.CloseHandle(proc)


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


UNTRACKED_READ_MAX = 1024 * 1024  # an untracked file larger than this counts 0 lines (plan 23 facts)


def git_snapshot(cwd: str, commit: str):
    """The tree against `commit` for the facts (plan 23): {path: [plus, minus]} from `git diff --numstat <commit>`,
    plus each untracked file as [its lines, 0]; None when git cannot tell (not a repo, no commit). Read only: no git
    object, index or file is written."""
    from . import facts  # here, not at the top: facts is pure and imports redact only
    if not commit:
        return None
    outs = []
    for cmd in (["git", "diff", "--numstat", commit], ["git", "ls-files", "--others", "--exclude-standard"]):
        try:
            out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW,
                                 encoding="utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        outs.append(out.stdout)
    untracked = {}
    for name in outs[1].splitlines()[:facts.SNAPSHOT_MAX]:
        path = Path(cwd) / name
        try:
            untracked[name] = path.read_bytes().count(b"\n") if path.stat().st_size <= UNTRACKED_READ_MAX else 0
        except OSError:
            untracked[name] = 0
    return facts.snapshot(outs[0], untracked)


def git_status(cwd: str) -> list:
    """`git status --short` lines of `cwd` ([] when it is not a repo or git is missing)."""
    try:
        out = subprocess.run(["git", "status", "--short"], cwd=cwd, capture_output=True, text=True,
                             timeout=10, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return []
    return out.stdout.splitlines() if out.returncode == 0 else []
