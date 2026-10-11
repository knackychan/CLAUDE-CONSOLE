"""A new-task brief built from the facts of a session, with no model call: what a fresh chat needs to
take over a session whose context is too large to re-read (the cold-cache guard offers it)."""
from . import levers, redact

GOAL_MAX = 1200
LAST_MAX = 1200
FILES_MAX = 20
STATUS_MAX = 20
TASK_INTRO = ("Take over a task from an earlier chat whose context was too large to re-read. Start from "
              "the repo and the facts below, and check anything you rely on.")
VERIFY_INTRO = ("The earlier chat is not available here (its context was too large to re-read). Judge the "
                "files as they are now, from the facts below.")


def build(kind: str, goal: str = "", last: str = "", files: list = (), verdict: str = "", detail: str = "",
          status: list = (), plan: bool = False) -> str:
    """`kind` is "task" (hand the work over) or "verify" (VERIFY_TEXT plus the facts)."""
    out = [levers.VERIFY_TEXT + " " + VERIFY_INTRO if kind == "verify" else TASK_INTRO]
    if goal:
        out += ["", "Goal (the first prompt of the earlier chat):", redact.clip(goal, GOAL_MAX)]
    if last:
        out += ["", "Where it stopped (the last message of Claude):", redact.clip(last, LAST_MAX)]
    if files:
        shown = list(files)[:FILES_MAX]
        more = len(files) - len(shown)
        out += ["", "Files the earlier chat edited:"] + [f"- {f}" for f in shown]
        if more > 0:
            out.append(f"- and {more} more")
    if verdict:
        out += ["", "Last check: " + redact.clip(f"{verdict} {detail}".strip(), 200)]
    if status:
        shown = [redact.mask(line) for line in list(status)[:STATUS_MAX]]
        more = len(status) - len(shown)
        out += ["", "Git status of the folder now:"] + shown
        if more > 0:
            out.append(f"... and {more} more")
    if plan and kind != "verify":
        out += ["", "Read PLAN.md first."]
    return "\n".join(out)
