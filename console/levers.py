"""Phase 3 levers: the texts Verify, Handoff and Escalate send, the escalation step, the order after
Verify, and the routing-misses file. When a lever is allowed is decided in one place: server.Hub.levers."""
import time
from pathlib import Path

from . import claude_cli, redact

VERIFY_TEXT = ("Check the work of this session. If a `verifier` agent is available (the project's "
               "`.claude/agents` or `~/.claude/agents`), run it with the Agent tool; otherwise "
               "run the project's tests or checks once. Do not edit any file. End your final message "
               "with one line: `VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`.")
HANDOFF_TEXT = "/session-handoff"
HANDOFF_SKILL = Path("skills") / "session-handoff" / "SKILL.md"
MISSES_FILE = "routing-misses.md"
MISSES_HEAD = ("# Routing misses\n\nOne line per Escalate, written by Claude Console. "
               "Prep reads the lines of its project.\n\n")
MISSES_SHOWN = 20


def escalate_step(model: str, effort: str):
    """One step up (route-model: effort first, then a bigger model): effort +1 up to high, then
    the next model at the same effort; on the top model, effort +1. None when nothing is above."""
    models, efforts = claude_cli.MODELS, claude_cli.EFFORTS
    if model not in models or effort not in efforts:
        return None
    e, m = efforts.index(effort), models.index(model)
    if e < efforts.index("high"):
        return model, efforts[e + 1]
    if m + 1 < len(models):
        return models[m + 1], effort
    if e + 1 < len(efforts):
        return model, efforts[e + 1]
    return None


def escalate_text(detail: str, model: str, effort: str) -> str:
    failed = detail or "see the last VERDICT line"
    return (f"The checks failed: {failed}. You now run on {model}/{effort} (escalated once). Find and fix "
            "the cause, run the checks again, then end your final message with one line: "
            "`VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`.")


def after_verify(verdict: str) -> tuple:
    """The levers that follow Verify, in button order: a PASS is handed off (the next task) or accepted
    (Mark done); a FAIL is escalated first."""
    if verdict == "PASS":
        return ("handoff", "done")
    if verdict == "FAIL":
        return ("escalate", "handoff", "done")
    return ("handoff", "escalate", "done")


def handoff_ready(project_dir: str, home: Path = None) -> bool:
    """True when Claude Code can expand /session-handoff here: the project's or Fred's own skill."""
    places = [Path(project_dir) / ".claude" if project_dir else None, Path(home or Path.home()) / ".claude"]
    return any(p is not None and (p / HANDOFF_SKILL).is_file() for p in places)


def miss_line(project: str, task_type: str, route_from: str, route_to: str, detail: str,
              now: float = None) -> str:
    day = time.strftime("%Y-%m-%d", time.localtime(now or time.time()))
    why = redact.clip(redact.mask(detail), 120) or "verifier FAIL"
    return (f"- {day} - {project} - {task_type or 'unrouted'}: {route_from} failed ({why}); "
            f"next time start at {route_to}.")


def add_miss(folder: Path, line: str) -> None:
    path = Path(folder) / MISSES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    head = "" if path.exists() else MISSES_HEAD
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(head + line + "\n")


def read_misses(folder: Path, project: str, limit: int = MISSES_SHOWN) -> list:
    """The last `limit` miss lines of one project (matched by the project folder's name)."""
    try:
        lines = (Path(folder) / MISSES_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    tag = f" - {project} - "
    return [line for line in lines if line.startswith("- ") and tag in line][-limit:]
