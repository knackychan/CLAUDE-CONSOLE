"""Masking and short summaries: nothing secret or long ever reaches the event log."""
import re
from pathlib import PurePath

_SECRETS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
]
_ASSIGN = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:api[_-]?key|token|secret|password)[A-Z0-9_]*)\s*([=:])\s*"
    r"(\"[^\"]*\"|'[^']*'|\S+)"
)
_PATH_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}


def mask(text) -> str:
    """Replace token-shaped strings and key=value secrets with ***."""
    if not text:
        return ""
    text = str(text)
    for rx in _SECRETS:
        text = rx.sub("***", text)
    return _ASSIGN.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)


def clip(text, limit: int) -> str:
    """Collapse whitespace and cut to `limit` characters (ending with an ellipsis)."""
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _short_path(path: str, cwd: str) -> str:
    try:
        return str(PurePath(path).relative_to(PurePath(cwd))).replace("\\", "/")
    except (ValueError, TypeError):
        return str(path).replace("\\", "/")


def summarize(tool, tool_input, cwd: str = "") -> str:
    """One short, masked line saying what a tool call touches."""
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tool in _PATH_TOOLS:
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        return clip(_short_path(path, cwd), 80) if path else ""
    if tool in ("Bash", "PowerShell"):
        return clip(mask(ti.get("command", "")), 80)
    if tool in ("Grep", "Glob"):
        return clip(mask(ti.get("pattern", "")), 60)
    if tool in ("Agent", "Task"):
        kind = ti.get("subagent_type") or "agent"
        return clip(f"{kind}: {ti.get('description', '')}", 80)
    if tool == "Skill":
        return clip(ti.get("skill", ""), 60)
    if tool == "WebFetch":
        url = re.sub(r"^https?://", "", str(ti.get("url", "")))
        return clip(url.split("/")[0], 60)
    if tool == "WebSearch":
        return clip(mask(ti.get("query", "")), 60)
    return ""
