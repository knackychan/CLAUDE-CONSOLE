"""Phase 3 levers: the texts Verify, Handoff and Escalate send, the escalation step, the order after
Verify, the routing-misses file and (plan 22) the lessons file. When a lever is allowed is decided in one
place: server.Hub.levers."""
import time
from pathlib import Path

from . import claude_cli, redact

VERIFY_TEXT = ("Check the work of this session. If a `verifier` agent is available (the project's "
               "`.claude/agents` or `~/.claude/agents`), run it with the Agent tool; otherwise "
               "run the project's tests or checks once. Do not edit any file. End your final message "
               "with one line: `VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`.")
HANDOFF_TEXT = "/session-handoff"
HANDOFF_ROUTE = ("sonnet", "medium")  # after a PASS: a fresh chat writes the note from a brief (Fred: c, 2026-10-13)
HANDOFF_SKILL = Path("skills") / "session-handoff" / "SKILL.md"
MISSES_FILE = "routing-misses.md"
MISSES_HEAD = ("# Routing misses\n\nOne line per Escalate, written by Claude Console, and one `floor ... used` line "
               "when a step on that floor passed (it ends the floor). Prep reads the lines of its project.\n\n")
MISSES_SHOWN = 20
LESSONS_FILE = "lessons.md"
LESSONS_HEAD = ("# Lessons\n\nOne line per lesson: a step's `Lesson:` line (written by Claude Console) or a "
                "chat's (written by session-handoff). The rules review reads the lines of its project.\n\n")
LESSONS_SHOWN = 40
FIX_FRAME = ("Before you edit: name up to three plausible causes, the evidence for and against each, and the "
             "smallest check that tells them apart; run that check; fix only the cause it confirmed.")


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
    return (f"The checks failed: {failed}. You now run on {model}/{effort} (escalated once). {FIX_FRAME} "
            "Then run the checks again and end your final message with one line: "
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


def _day(now: float = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))


def miss_line(project: str, task_type: str, route_from: str, route_to: str, detail: str,
              now: float = None) -> str:
    why = redact.clip(redact.mask(detail), 120) or "verifier FAIL"
    return (f"- {_day(now)} - {project} - {task_type or 'unrouted'}: {route_from} failed ({why}); "
            f"next time start at {route_to}.")


def used_line(project: str, kind: str, route: str, task_id: str, n: int, now: float = None) -> str:
    """Plan 32: the floor `route` of `kind` did its job once (step `n` of `task_id` ran on it and passed); the next
    step of that kind starts at its rule again (routing.live)."""
    return f"- {_day(now)} - {project} - {kind}: floor {route} used by task {task_id} step {n:02d}; it passed."


def lesson_line(project: str, kind: str, text: str, now: float = None) -> str:
    """One lesson: `- <day> - <project> - <step kind or chat>: <one sentence>` (masked, clipped at 200)."""
    what = redact.clip(redact.mask(" ".join(str(text or "").split())), 200)
    return f"- {_day(now)} - {project} - {kind or 'chat'}: {what}"


def _append(folder: Path, name: str, head: str, line: str) -> None:
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    lead = "" if path.exists() and path.stat().st_size else head  # decided before the open creates the file
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(lead + line + "\n")


def _read(folder: Path, name: str, project: str, limit: int) -> list:
    """The last `limit` lines of one project (matched by the project folder's name)."""
    try:
        lines = (Path(folder) / name).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    tag = f" - {project} - "
    return [line for line in lines if line.startswith("- ") and tag in line][-limit:]


def add_miss(folder: Path, line: str) -> None:
    _append(folder, MISSES_FILE, MISSES_HEAD, line)


def read_misses(folder: Path, project: str, limit: int = MISSES_SHOWN) -> list:
    return _read(folder, MISSES_FILE, project, limit)


def add_lesson(folder: Path, line: str) -> None:
    _append(folder, LESSONS_FILE, LESSONS_HEAD, line)


def read_lessons(folder: Path, project: str, limit: int = LESSONS_SHOWN) -> list:
    return _read(folder, LESSONS_FILE, project, limit)
