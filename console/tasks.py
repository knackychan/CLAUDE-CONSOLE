"""Task folders and the step chain (plan 17): a task is a short list of steps, each one a fresh `claude -p`
run, handed on through a note. This module is pure: rules, routes, the handoff check, the chain transitions
(on dicts) and the files of a task folder. The service (server.Hub) is its only caller; it starts the runs,
reads the final messages and writes every file. A model never writes into the task folder.

    <home>/tasks/<id>/   task.json   the task and its steps (written whole, through a temp file)
                         prompt.md   the task text as Fred ran it (the service writes it)
                         steps/NN-<kind>.md   the handoff note of a finished step
                         chain.jsonl one line per transition"""
import copy
import json
import os
import re
import shutil
import time
from pathlib import Path
from string import Template

from . import claude_cli, levers, redact, routing

RULES = {  # kind -> (model, effort, --tools list; "" = the default set). verify and fix are computed.
    "scout": ("haiku", "low", "Read,Grep,Glob"),
    "search": ("haiku", "low", "Read,Grep,Glob,WebFetch,WebSearch"),
    "draft": ("haiku", "low", ""),
    "proofread": ("haiku", "low", ""),
    "edit": ("haiku", "low", ""),
    "code": ("sonnet", "medium", ""),
    "document": ("sonnet", "medium", ""),
    "explain": ("sonnet", "medium", "Read,Grep,Glob"),
    "debug": ("sonnet", "high", ""),
    "test": ("haiku", "low", "Bash,Read,Grep,Glob"),
    "design": ("opus", "high", "Read,Grep,Glob,WebFetch,WebSearch"),
    "verify": ("", "", "Bash,Read,Grep,Glob"),
    "fix": ("", "", ""),
}
KINDS = tuple(RULES)
PREP_KINDS = tuple(k for k in KINDS if k not in ("verify", "fix"))  # what Prep may propose
EDIT_KINDS = frozenset({"edit", "code", "debug", "document", "draft"})  # a verify follows the last of them
DISALLOW = ("Agent",)
HEADINGS = ("## Findings", "## Files touched", "## Open questions", "## Next")
MARK_START, MARK_END = "HANDOFF", "END HANDOFF"
NOTE_MAX = 20 * 1024
GOAL_MAX = 6000
STEP_GOAL_MAX = 200
TASK_STATES = ("planned", "running", "waiting", "stuck", "done", "stopped")
STEP_STATES = ("planned", "running", "done", "failed")
EFFORT_CAP = {m: claude_cli.EFFORTS[-1] for m in claude_cli.MODELS}  # every alias took `max` (CLI 2.1.296)
_TOP = ("opus", "high")  # the most a step runs on unless Fred picks fable
_HINT = re.compile(r"Next model:\s*([a-z]+)/([a-z]+)")
PROMPT_FILE = Path(__file__).resolve().parent / "step_prompt.md"


def safe_id(text) -> str:
    return text if isinstance(text, str) and re.fullmatch(r"[0-9a-f-]{1,20}", text) else ""


# -- routes -----------------------------------------------------------------------------------------------

def verify_route(checked: tuple) -> tuple:
    """One model above the checked step, never above opus; effort at least medium, at most high."""
    models, efforts = claude_cli.MODELS, claude_cli.EFFORTS
    model = models[min(models.index(checked[0]) + 1, models.index("opus"))]
    effort = efforts[min(max(efforts.index(checked[1]), efforts.index("medium")), efforts.index("high"))]
    return model, effort


def step_route(kind: str, *, pick: str = "", checked=None, demand=None, misses=(), prev: str = "",
               budget=None, warn_at: float = 0.8, effort: str = "auto") -> dict:
    """The route of one step: rule, pick, demand, floor, hint, cap, budget, fixed effort (README 3.5), in
    that order, each one appending a note. `hold` non-empty means the task waits for Fred."""
    models, efforts = claude_cli.MODELS, claude_cli.EFFORTS
    fixed = effort != "auto"
    notes, hold = [], ""
    if kind == "verify":
        model, level = verify_route(checked)
    elif kind == "fix":
        # with a fixed effort the effort cannot step up, so the model does
        model, level = (levers.escalate_step(checked[0], "high" if fixed else checked[1]) or checked)
    else:
        model, level = RULES[kind][:2]
    notes.append(f"rule {kind}: {model}/{level}")
    picked = claude_cli.model_alias(pick)
    if picked:
        model = picked
        notes.append(f"pick: {picked}")
    if (demand or {}).get("reasoning") == "high" and kind in ("code", "debug") \
            and efforts.index(level) < efforts.index("high"):
        level = "high"
        notes.append("demand: effort high")
    low = routing.floor(misses, kind)
    if low and routing.rank(low) > routing.rank((model, level)):
        model, level = low
        notes.append(f"floor {kind}: {model}/{level}")
    hint = next_hint(prev)
    if hint and routing.rank(hint) > routing.rank((model, level)):
        model, level = levers.escalate_step(model, level) or (model, level)
        notes.append(f"hint: {hint[0]}/{hint[1]} -> one step up")
    chosen = (model, level)
    if model == "fable" and picked != "fable" and not (checked and checked[0] == "fable"):
        model = "opus"  # code never picks fable; a fix or verify of a step Fred put on fable may keep it
    if not fixed and model == "opus" and efforts.index(level) > efforts.index(_TOP[1]):
        level = _TOP[1]
    if (model, level) != chosen:
        notes.append(f"cap: {model}/{level}")
    share = (budget or {}).get(model, 0)
    if share >= warn_at and model != "haiku":
        if kind == "verify":
            hold = f"{model} over its pace"
            notes.append(f"budget: {model} {round(share * 100)} % -> hold")
        else:
            was = model
            model, level = models[models.index(model) - 1], efforts[min(efforts.index(level) + 1, len(efforts) - 1)]
            notes.append(f"budget: {was} {round(share * 100)} % -> {model}/{level}")
    if fixed:
        level = effort
        notes.append(f"fixed effort: {effort}")
        cap = EFFORT_CAP[model]
        if efforts.index(level) > efforts.index(cap):
            level = cap
            notes.append(f"cap {model}: {cap}")
    return {"model": model, "effort": level, "notes": notes, "hold": hold}


# -- the handoff block ------------------------------------------------------------------------------------

def parse_handoff(text: str):
    """The last block between a line HANDOFF and a line END HANDOFF (markers left out); None when there is none."""
    blocks, start = [], None
    lines = str(text or "").splitlines()
    for i, line in enumerate(lines):
        mark = line.strip()
        if mark == MARK_START:
            start = i
        elif mark == MARK_END and start is not None:
            blocks.append("\n".join(lines[start + 1:i]))
            start = None
    return blocks[-1] if blocks else None


def check_handoff(block: str) -> str:
    """"" when the four headings stand on their own lines in order and Findings has text; else the reason."""
    lines = str(block or "").splitlines()
    at = []
    for heading in HEADINGS:
        found = [i for i, line in enumerate(lines) if line.strip() == heading]
        if not found:
            return f"missing: {heading}"
        at.append(found[0])
    if at != sorted(at):
        return "headings out of order"
    if not any(line.strip() for line in lines[at[0] + 1:at[1]]):
        return "Findings is empty"
    return ""


def next_hint(block: str):
    """The first `Next model: m/e` that routing.parse accepts, as (model, effort); else None."""
    for m in _HINT.finditer(str(block or "")):
        route = routing.parse(f"{m.group(1)}/{m.group(2)}")
        if route:
            return route
    return None


def note_file(task: dict, step: dict) -> str:
    return f"steps/{step['n']:02d}-{step['kind']}.md"


def brief_file(task: dict, step: dict) -> str:
    """The compacted note the next step reads (compact.py)."""
    return f"steps/{step['n']:02d}-{step['kind']}.brief.md"


def note_text(task: dict, step: dict, block: str) -> str:
    body = redact.mask(block)
    raw = body.encode("utf-8")
    if len(raw) > NOTE_MAX:
        body = raw[:NOTE_MAX].decode("utf-8", "ignore").rstrip() + "\n[cut at 20 KB]"
    head = f"# Step {step['n']:02d}: {step['kind']} on {step['model']}/{step['effort']}, session {step['session']}"
    return f"{head}\n\n{body}"


# -- steps and the chain (pure, on dicts) -----------------------------------------------------------------

def _blank(n: int, kind: str, goal: str, pick: str = "", checked: int = 0) -> dict:
    return {"n": n, "kind": kind, "goal": goal, "model": "", "effort": "", "pick": pick, "session": "",
            "state": "planned", "handoff": "", "verdict": "", "verdict_detail": "", "retries": 0, "cost": 0,
            "start_commit": "", "started": None, "ended": None, "notes": [], "checked": checked}


def plan_steps(proposed, max_steps: int) -> list:
    """Prep's proposed steps, validated: known kinds with a goal, cut at `max_steps`, and a verify after the
    last step that edits. Full step dicts numbered from 1; [] when nothing valid is left."""
    kept = []
    for item in proposed if isinstance(proposed, list) else []:
        if not isinstance(item, dict) or item.get("kind") not in PREP_KINDS:
            continue
        goal = item.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            continue
        model = item.get("model")
        kept.append((item["kind"], redact.clip(goal, STEP_GOAL_MAX), model if model in claude_cli.MODELS else ""))
    kept = kept[:max_steps]
    steps = [_blank(i + 1, kind, goal, pick) for i, (kind, goal, pick) in enumerate(kept)]
    edits = [i for i, s in enumerate(steps) if s["kind"] in EDIT_KINDS]
    if edits:
        after = edits[-1] + 1
        steps.insert(after, _blank(after + 1, "verify", f"Check step {after}", checked=after))
        for i, s in enumerate(steps):
            s["n"] = i + 1
    return steps


def new_task(project_dir: str, project: str, title: str, goal: str, steps: list, type_: str, demand,
             prep: str, effort: str, now: float) -> dict:
    if not steps:
        raise ValueError("a task needs at least one step")
    if effort != "auto" and effort not in claude_cli.EFFORTS:
        raise ValueError(f"unknown effort: {effort}")
    from .prep import new_id  # here, not at the top: prep imports this module for PREP_KINDS
    return {"id": new_id(), "project_dir": project_dir, "project": project, "title": title,
            "goal": str(goal or "")[:GOAL_MAX], "type": type_, "demand": dict(demand or {}), "effort": effort,
            "state": "planned", "owner": "service", "current": 0, "last_good": 0, "escalated": "",
            "fable_ok": False, "prep": prep, "why": "", "created": now, "updated": now,
            "steps": copy.deepcopy(steps)}


def step(task: dict, n: int) -> dict:
    for s in task["steps"]:
        if s["n"] == n:
            return s
    raise KeyError(n)


def current_step(task: dict):
    return step(task, task["current"]) if task["current"] else None


def checked_route(task: dict, s: dict):
    """(tier, effort) the step `s` (a verify or a fix) checks or fixes, as it ran; None for any other step."""
    if not s.get("checked"):
        return None
    done = step(task, s["checked"])
    tier = done.get("tier") or claude_cli.model_alias(done["model"])
    return (tier, done["effort"]) if tier and done["effort"] else None


def _line(now: float, s, frm: str, to: str, why: str = "") -> dict:
    return {"ts": now, "step": s["n"] if s else 0, "from": frm, "to": to, "why": why,
            "session": s["session"] if s else ""}


def _task_to(task: dict, state: str, why: str, now: float, s, lines: list) -> None:
    """Move the task to `state`; a chain line only when the state changes."""
    if task["state"] != state:
        lines.append(_line(now, s, "task:" + task["state"], "task:" + state, why))
    task["state"], task["why"], task["updated"] = state, why, now


def _finish(task: dict, s: dict, state: str, now: float, lines: list, why: str = "") -> None:
    lines.append(_line(now, s, s["state"], state, why))
    s["state"], s["ended"] = state, now


def start_step(task: dict, n: int, session: str, route: dict, start_commit: str, now: float) -> list:
    s = step(task, n)
    lines = [_line(now, dict(s, session=session), s["state"], "running", " · ".join(route["notes"]))]
    s.update(state="running", model=route["model"], effort=route["effort"], notes=list(route["notes"]),
             session=session, start_commit=start_commit, started=now, ended=None)
    task["current"] = n
    _task_to(task, "running", "", now, s, lines)
    return lines


def _retry_or_stuck(task: dict, s: dict, reason: str, now: float, lines: list) -> str:
    _finish(task, s, "failed", now, lines, reason)
    if s["retries"] == 0:
        s["retries"], s["state"] = 1, "planned"
        lines.append(_line(now, s, "failed", "planned", "retry 1"))
        _task_to(task, "running", reason, now, s, lines)  # the retry's prompt carries the reason
        return "retry"
    _task_to(task, "stuck", f"{reason} (after one retry)", now, s, lines)
    return "stuck"


def _insert_fix(task: dict, s: dict, now: float, detail: str) -> None:
    """After the failed verify `s`: a fix on the escalated route, then a verify of the fix. Later steps move."""
    checked = step(task, s["checked"]) if s["checked"] else task["steps"][max(task["steps"].index(s) - 1, 0)]
    old = checked_route(task, dict(s, checked=checked["n"]))
    new = step_route("fix", checked=old, effort=task["effort"])
    task["escalated"] = f"{old[0]}/{old[1]} -> {new['model']}/{new['effort']}"
    task["miss"] = levers.miss_line(task["project"], checked["kind"], f"{old[0]}/{old[1]}",
                                    f"{new['model']}/{new['effort']}", detail, now)
    at = task["steps"].index(s) + 1
    for later in task["steps"][at:]:
        if later["checked"] > s["n"]:
            if later["goal"] == f"Check step {later['checked']}":
                later["goal"] = f"Check step {later['checked'] + 2}"
            later["checked"] += 2
        later["n"] += 2
    fix = _blank(s["n"] + 1, "fix", f"Fix what step {checked['n']} left failing", checked=checked["n"])
    again = _blank(s["n"] + 2, "verify", f"Check step {s['n'] + 1}", checked=s["n"] + 1)
    task["steps"][at:at] = [fix, again]


def on_step_ended(task: dict, *, ok: bool, block_error: str, verdict: str, verdict_detail: str,
                  question: str, now: float):
    """The current step's session ended (README 3.7). Returns (action, chain lines); action is "wait",
    "next", "done", "fix" (start `current + 1`, the fix), "retry" or "stuck". Mutates `task`."""
    s = current_step(task)
    if s is None:
        raise ValueError("the task has no current step")
    lines = []
    if question:
        _task_to(task, "waiting", f"asks: {question}", now, s, lines)
        return "wait", lines
    reason = ""
    if not ok:
        reason = "the run did not finish cleanly" + (f" ({block_error})" if block_error else "")
    elif block_error:
        reason = block_error
    elif s["kind"] == "verify" and verdict not in ("PASS", "FAIL"):
        reason = "no VERDICT line"
    if reason:
        return _retry_or_stuck(task, s, reason, now, lines), lines
    if s["kind"] == "verify":
        s["verdict"], s["verdict_detail"] = verdict, verdict_detail
    if s["kind"] == "verify" and verdict == "FAIL":
        if task["escalated"]:
            _finish(task, s, "failed", now, lines, "VERDICT: FAIL")
            _task_to(task, "stuck", "verify failed twice" + (f": {verdict_detail}" if verdict_detail else ""),
                     now, s, lines)
            return "stuck", lines
        _finish(task, s, "done", now, lines, "VERDICT: FAIL")
        task["last_good"] = s["n"]
        _insert_fix(task, s, now, verdict_detail)
        _task_to(task, "running", "", now, s, lines)
        return "fix", lines
    _finish(task, s, "done", now, lines, f"VERDICT: {verdict}" if s["kind"] == "verify" else "")
    task["last_good"] = s["n"]
    if s["n"] < len(task["steps"]):
        _task_to(task, "running", "", now, s, lines)
        return "next", lines
    _task_to(task, "done", "", now, s, lines)
    return "done", lines


def fred(task: dict, lever: str, now: float):
    """Fred's levers on the task state. (True, "", chain lines) when it applies, else (False, why, [])."""
    state, s, lines = task["state"], current_step(task), []
    if lever == "stop":
        if state in ("done", "stopped"):
            return False, f"task is {state}", []
        if s and s["state"] == "running":
            _finish(task, s, "failed", now, lines, "stopped by Fred")
        _task_to(task, "stopped", "stopped by Fred", now, s, lines)
        task["owner"] = "fred"
    elif lever == "pause":
        if state not in ("running", "waiting"):
            return False, "not running or waiting", []
        if task["owner"] == "fred":
            return False, "already paused", []
        task["owner"], task["updated"] = "fred", now
        lines.append(_line(now, s, "task:" + state, "task:" + state, "paused by Fred"))
    elif lever == "resume":
        if state in ("stuck", "stopped", "done"):
            return False, f"task is {state}", []
        if task["owner"] != "fred":
            return False, "not paused", []
        task["owner"], task["updated"] = "service", now
        lines.append(_line(now, s, "task:" + state, "task:" + state, "resumed by Fred"))
    elif lever == "retry":
        if state not in ("stuck", "stopped"):
            return False, "not stuck or stopped", []
        if s and s["state"] != "done":  # a finished step is not run twice: the next one is already planned
            lines.append(_line(now, s, s["state"], "planned", "retry by Fred"))
            s["state"] = "planned"
        _task_to(task, "running" if s else "planned", "", now, s, lines)
        task["owner"] = "service"
    elif lever == "confirm":
        if not (state == "waiting" and task["why"] == "confirm Fable"):
            return False, "nothing to confirm", []
        task["fable_ok"] = True
        _task_to(task, "running", "", now, s, lines)
    else:
        return False, f"unknown lever: {lever}", []
    return True, "", lines


# -- files ------------------------------------------------------------------------------------------------

def folder(home, task_id: str) -> Path:
    if not safe_id(task_id):
        raise ValueError(f"unsafe task id: {task_id!r}")
    return Path(home) / "tasks" / task_id


def save(home, task: dict) -> None:
    path = folder(home, task["id"]) / "task.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("task.json.tmp")
    tmp.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load(home, task_id: str):
    if not safe_id(task_id):
        return None
    try:
        data = json.loads((folder(home, task_id) / "task.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load_all(home) -> dict:
    root, found = Path(home) / "tasks", {}
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            task = load(home, entry.name)
            if task:
                found[entry.name] = task
    return found


def log(home, task_id: str, lines: list) -> None:
    path = folder(home, task_id) / "chain.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def write_note(home, task: dict, step: dict, block: str) -> str:
    rel = note_file(task, step)
    path = folder(home, task["id"]) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(note_text(task, step, block), encoding="utf-8")
    step["handoff"] = rel
    return rel


def read_note(home, task: dict, n: int) -> str:
    try:
        return (folder(home, task["id"]) / note_file(task, step(task, n))).read_text(encoding="utf-8")
    except (KeyError, OSError):
        return ""


def read_brief(home, task: dict, n: int) -> str:
    try:
        return (folder(home, task["id"]) / brief_file(task, step(task, n))).read_text(encoding="utf-8")
    except (KeyError, OSError):
        return ""


def prune(home, days: float, now: float = None) -> list:
    """Remove the task folders of `done`, `stopped` and `stuck` tasks whose task.json is older than `days`."""
    cutoff = (time.time() if now is None else now) - days * 86400
    root, removed = Path(home) / "tasks", []
    if not root.is_dir():
        return removed
    for entry in sorted(root.iterdir()):
        task = load(home, entry.name)
        if not task or task.get("state") not in ("done", "stopped", "stuck"):
            continue
        try:
            old = (entry / "task.json").stat().st_mtime < cutoff
        except OSError:
            continue
        if old:
            shutil.rmtree(entry, ignore_errors=True)
            removed.append(entry.name)
    return removed


def clear(home, task: dict, keep_last: bool = True) -> list:
    """Remove what is only history. `keep_last`: every note but the last good one and its brief (task.json,
    chain.jsonl and prompt.md stay); else the whole folder. Returns the step session ids so the caller can
    forget their runs."""
    sessions = [s["session"] for s in task["steps"] if s["session"]]
    root = folder(home, task["id"])
    if keep_last:
        last = step(task, task["last_good"]) if task["last_good"] else None
        keep = note_file(task, last) if last else ""
        kept = {keep, brief_file(task, last) if last else ""}
        for path in sorted((root / "steps").glob("*.md")):
            if f"steps/{path.name}" not in kept:
                path.unlink(missing_ok=True)
        for s in task["steps"]:
            if s["handoff"] != keep:
                s["handoff"] = ""
    else:
        shutil.rmtree(root, ignore_errors=True)
    task["cleared"] = True
    return sessions


# -- prompts ----------------------------------------------------------------------------------------------

def _fix_text(task: dict, s: dict) -> str:
    before = next((x for x in reversed(task["steps"][:task["steps"].index(s)]) if x["kind"] == "verify"), None)
    if s["model"] and s["effort"]:
        route = (s["model"], s["effort"])
    else:  # the service builds the prompt before the step starts
        found = step_route("fix", checked=checked_route(task, s), effort=task["effort"])
        route = (found["model"], found["effort"])
    return levers.escalate_text(before["verdict_detail"] if before else "", *route)


def step_prompt(task: dict, step: dict, prev_note: str, retry_reason: str = "") -> str:
    kind = step["kind"]
    special = levers.VERIFY_TEXT if kind == "verify" else _fix_text(task, step) if kind == "fix" else ""
    retry = (f"Your earlier attempt at this step ended without a handoff: {retry_reason}. "
             "Start again from the note above.") if retry_reason else ""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        title=task["title"], goal=str(task.get("goal", ""))[:GOAL_MAX], n=step["n"], m=len(task["steps"]),
        kind=kind, step_goal=step["goal"], special=special, retry=retry,
        prev=prev_note or "This is the first step: there is no handoff note yet.")
