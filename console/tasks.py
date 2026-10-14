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

from . import claude_cli, fills, levers, redact, routing
from .fills import RANK_TIER, TIER_RANK, TIERS  # plan 18: the job tiers (the contract names them here)

RULES = {  # kind -> (model, effort, --tools list; "" = the default set). verify and fix are computed.
    "scout": ("haiku", "low", "Read,Grep,Glob"),
    "search": ("haiku", "low", "Read,Grep,Glob,WebFetch,WebSearch"),
    "draft": ("haiku", "low", "Read,Edit,Write,Grep,Glob"),  # plan 23 (D3): an explicit list on every kind
    "proofread": ("haiku", "low", "Read,Edit,Write,Grep,Glob"),
    "edit": ("haiku", "low", "Read,Edit,Write,Grep,Glob"),
    "code": ("sonnet", "medium", "Bash,Read,Edit,Write,Grep,Glob"),
    "document": ("sonnet", "medium", "Read,Edit,Write,Grep,Glob"),
    "explain": ("sonnet", "medium", "Read,Grep,Glob"),
    "debug": ("sonnet", "high", "Bash,Read,Edit,Write,Grep,Glob"),
    "test": ("haiku", "low", "Bash,Read,Grep,Glob"),
    "design": ("opus", "high", "Read,Grep,Glob,WebFetch,WebSearch"),
    "replan": ("haiku", "low", ""),
    "verify": ("", "", "Bash,Read,Grep,Glob"),
    "fix": ("", "", "Bash,Read,Edit,Write,Grep,Glob"),
}
KINDS = tuple(RULES)
PREP_KINDS = tuple(k for k in KINDS if k not in ("verify", "fix"))  # what Prep may propose
EDIT_KINDS = frozenset({"edit", "code", "debug", "document", "draft"})  # a verify follows the last of them
DISALLOW = ("Agent",)
HEADINGS = ("## Goal", "## Findings", "## Files touched", "## Troubleshooting", "## Open questions", "## Next")
OLD_HEADINGS = ("## Findings", "## Files touched", "## Open questions", "## Next")  # a note from before plan 23
READ_CAPPED = ("scout", "search")  # kinds whose run gets --max-turns read_max_turns (plan 23)
PROMPT_GOAL_MAX = 600  # the goal in a step prompt after step 1: every handoff carries its Goal heading (plan 23)
LESSONS_IN_PROMPT = 5  # the newest lessons of the step's own kind that ride in its prompt (plan 23)
FIRST_STEP = "This is the first step: there is no handoff note yet."
MARK_START, MARK_END = "HANDOFF", "END HANDOFF"
NOTE_MAX = 20 * 1024
GOAL_MAX = 6000
STEP_GOAL_MAX = 1000
TASK_STATES = ("planned", "running", "waiting", "stuck", "done", "stopped", "handed")  # handed: Fred handed off
STEP_STATES = ("planned", "running", "done", "failed", "handed")  # handed: the step Fred handed off
EFFORT_CAP = {m: claude_cli.EFFORTS[-1] for m in claude_cli.MODELS}  # every alias took `max` (CLI 2.1.296)
_TOP = ("opus", "high")  # the most a step runs on unless Fred picks fable
_HINT = re.compile(r"Next model:\s*([a-z]+)/([a-z]+)")
PROMPT_FILE = Path(__file__).resolve().parent / "step_prompt.md"
VERIFY_STEP = ("Check the work of step $checked as the handoff note above describes it: read the files it "
               "touched and run the project's tests or checks once. Do not edit any file. Put one line "
               "`VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>` in your final message, just before "
               "the HANDOFF block.")  # a step's own text: levers.VERIFY_TEXT is the session lever's


def safe_id(text) -> str:
    return text if isinstance(text, str) and re.fullmatch(r"[0-9a-f-]{1,20}", text) else ""


# -- routes -----------------------------------------------------------------------------------------------

def verify_route(checked: tuple) -> tuple:
    """One model above the checked step, never above opus; effort at least medium, at most high."""
    models, efforts = claude_cli.MODELS, claude_cli.EFFORTS
    model = models[min(models.index(checked[0]) + 1, models.index("opus"))]
    effort = efforts[min(max(efforts.index(checked[1]), efforts.index("medium")), efforts.index("high"))]
    return model, effort


def kind_tier(kind: str) -> str:
    """A kind's job tier: its rule's rank read as a tier (design think; code, document, explain, debug write; the
    rest read); "" for verify and fix, which the rule computes."""
    return RANK_TIER.get(RULES.get(kind, ("",))[0], "")


def step_route(kind: str, *, pick: str = "", checked=None, demand=None, misses=(), prev: str = "",
               budget=None, warn_at: float = 0.8, effort: str = "auto", cfg=None, prev_rung: str = "",
               prev_age=None, hard: bool = False, refuse=None, now: float = None, pin=None) -> dict:
    """The route of one step: rule, pick, demand, floor, hint, cap, balance, fixed effort (README 3.5 of plan 17,
    step 7 rewritten by plan 18), in that order, each one appending a note. A pick keeps its model against the floor
    and the hint (they may still raise the effort) and is never balanced. `budget` is Hub.budget() (fills per model
    key); `cfg` gives the tiers, the balance keys and models.json; `refuse(rung)` a reason a rung cannot run now.
    Returns {"model": the rank of the rung, "rung", "effort", "notes", "hold"}; without `cfg` the rung is the rank
    alias (plan 17's behaviour). `hold` non-empty means the task waits for Fred. `pin` is config `kinds[kind]`
    (plan 26): a pinned rung acts as a pick when the step has none, a pinned effort as the task's fixed effort
    when the task has none; verify and fix are never pinned."""
    efforts = claude_cli.EFFORTS
    pin = pin if isinstance(pin, dict) and kind not in ("verify", "fix") else {}
    pin_rung = pin.get("rung") if cfg is not None and pin.get("rung") not in (None, "", "auto") else ""
    pinned = effort == "auto" and pin.get("effort") in efforts
    if pinned:
        effort = pin["effort"]
    fixed = effort != "auto"
    notes, hold, rung = [], "", ""
    if kind == "verify":
        model, level = verify_route(checked)
    elif kind == "fix":
        # with a fixed effort the effort cannot step up, so the model does
        model, level = (levers.escalate_step(checked[0], "high" if fixed else checked[1]) or checked)
    else:
        model, level = RULES[kind][:2]
    notes.append(f"rule {kind}: {model}/{level}")
    from_pin = False
    if pin_rung and not pick:  # plan 26: the kind's pinned rung, unless it cannot run now (then auto)
        why = (refuse(pin_rung) if refuse else "") or ("" if fills.rank_of(pin_rung, cfg) else "unknown model")
        if why:
            notes.append(f"pin {kind}: {pin_rung} refused: {why} -> auto")
        else:
            pick, from_pin = pin_rung, True
            notes.append(f"pin {kind}: {pin_rung}")
    picked = (fills.rank_of(pick, cfg) if cfg is not None else claude_cli.model_alias(pick)) if pick else ""
    if picked:
        model = picked
        if not from_pin:  # a pin wrote its own note above
            notes.append(f"pick: {pick if cfg is not None else picked}")
        why = refuse(pick) if refuse and cfg is not None and not from_pin else ""
        if why:
            notes.append(f"pick refused: {why} -> balance")
        else:
            rung = pick if cfg is not None else ""
    if (demand or {}).get("reasoning") == "high" and kind in ("code", "debug") \
            and efforts.index(level) < efforts.index("high"):
        level = "high"
        notes.append("demand: effort high")
    low = routing.floor(misses, kind)
    if low and routing.rank(low) > routing.rank((model, level)):
        if picked and low[0] != model:  # Fred's pick keeps its model (2026-10-13); the floor's effort still counts
            level = max(level, low[1], key=efforts.index)
            notes.append(f"floor {kind}: {low[0]}/{low[1]} -> pick {model}/{level} kept")
        else:
            model, level = low
            notes.append(f"floor {kind}: {model}/{level}")
    hint = next_hint(prev)
    if hint and routing.rank(hint) > routing.rank((model, level)):
        up = levers.escalate_step(model, level) or (model, level)
        if picked and up[0] != model:  # a model's hint never moves a step off the model Fred picked
            notes.append(f"hint: {hint[0]}/{hint[1]} -> pick {picked} kept")
        else:
            model, level = up
            notes.append(f"hint: {hint[0]}/{hint[1]} -> one step up")
    chosen = (model, level)
    if model == "fable" and picked != "fable" and not (checked and checked[0] == "fable"):
        model = "opus"  # code never routes a rank to fable; a hard-only fable rung of the think tier may (balance)
    if not fixed and model == "opus" and efforts.index(level) > efforts.index(_TOP[1]):
        level = _TOP[1]
    if (model, level) != chosen:
        notes.append(f"cap: {model}/{level}")
    share = None
    if cfg is not None and not rung:  # 7. balance (plan 18): the emptiest model of the tier, from the first step
        check = kind in ("verify", "fix")
        rungs = fills.pool(cfg, model, check=check, hard=hard and not check, refuse=refuse)
        tier = RANK_TIER.get(model, "")
        if rungs:
            pickd = fills.balance(rungs, budget or {}, cfg, tier=tier, prev_rung="" if check else prev_rung,
                                  prev_age=prev_age, now=now)
            rung, share = pickd["rung"], pickd["share"]
            notes.append(pickd["note"])
            if pickd["effort"] != "auto" and not fixed:
                level = pickd["effort"]
                notes.append(f"rung effort: {level}")
        else:
            rung = model
            notes.append(f"balance: no usable {tier} rung -> {model}")
        model = fills.rank_of(rung, cfg) or model
    elif cfg is not None:
        share = ((budget or {}).get(fills.model_key(rung, cfg)) or {}).get("share")
    if not rung:
        rung = model
    if kind == "verify" and cfg is not None and share is not None and share >= warn_at:
        hold = f"{fills.model_key(rung, cfg)} over its pace"
        notes.append(f"over pace: {rung} {round(share * 100)} % -> hold")
    if fixed:
        level = effort
        notes.append(f"pin effort: {effort}" if pinned else f"fixed effort: {effort}")
    cap = EFFORT_CAP.get(model, efforts[-1])
    if efforts.index(level) > efforts.index(cap):
        level = cap
        notes.append(f"cap {model}: {cap}")
    return {"model": model, "rung": rung, "effort": level, "notes": notes, "hold": hold}


# -- the handoff block ------------------------------------------------------------------------------------

def _mark(line: str) -> str:
    """A marker line as the model may dress it: `**HANDOFF**`, `` `END HANDOFF` ``, `### HANDOFF`."""
    return line.strip().strip("*_`#").strip()


def parse_handoff(text: str):
    """The last block between a line HANDOFF and a line END HANDOFF (markers left out); None when there is none."""
    blocks, start = [], None
    lines = str(text or "").splitlines()
    for i, line in enumerate(lines):
        mark = _mark(line)
        if mark == MARK_START:
            start = i
        elif mark == MARK_END and start is not None:
            blocks.append("\n".join(lines[start + 1:i]))
            start = None
    return blocks[-1] if blocks else None


def live_note(text: str) -> str:
    """What a running step's reply says about its note so far: "writing" (no HANDOFF line, or no END HANDOFF yet)
    or "unchecked" (the whole block stands; the check runs when the run ends)."""
    return "unchecked" if parse_handoff(text) is not None else "writing"


def note_state(task: dict, s: dict, live: str = "") -> str:
    """The state of step `s`'s handoff note for the window: "" (none yet), "writing" / "unchecked" (`live`, the
    step runs), "checked" (it passed; the brief is made or there is no next step), "ready" (passed, briefed,
    the next step has not started), "sent" (the next step started), "handed" (Fred handed the task off here and the
    session-handoff note is in the task folder)."""
    if s["state"] == "handed":
        return "handed" if task.get("handoff_note") else ""
    if s["state"] == "running":
        return live or "writing"
    if not s.get("handoff") or s["state"] != "done":
        return ""
    if task.get("briefing") == s["n"] or s["n"] >= len(task["steps"]):
        return "checked"
    return "ready" if step(task, s["n"] + 1)["state"] == "planned" else "sent"


def check_handoff(block: str, old_ok: bool = False) -> str:
    """"" when the six headings stand on their own lines in order and Goal and Findings have text; else the reason.
    `old_ok`: a four-heading note from before plan 23 (an old task folder) passes too; only read paths pass it."""
    lines = str(block or "").splitlines()
    if old_ok and not any(line.strip() in ("## Goal", "## Troubleshooting") for line in lines):
        return _check_headings(lines, OLD_HEADINGS)
    return _check_headings(lines, HEADINGS)


def _check_headings(lines: list, headings: tuple) -> str:
    at = []
    for heading in headings:
        found = [i for i, line in enumerate(lines) if line.strip() == heading]
        if not found:
            return f"missing: {heading}"
        at.append(found[0])
    if at != sorted(at):
        return "headings out of order"
    for heading in ("## Goal", "## Findings"):
        if heading in headings:
            i = headings.index(heading)
            if not any(line.strip() for line in lines[at[i] + 1:at[i + 1]]):
                return f"{heading[3:]} is empty"
    return ""


def next_hint(block: str):
    """The first `Next model: m/e` that routing.parse accepts, as (model, effort); else None."""
    for m in _HINT.finditer(str(block or "")):
        route = routing.parse(f"{m.group(1)}/{m.group(2)}")
        if route:
            return route
    return None


# The hook's patterns (cc_events.py runs in the hook and is not imported here). The Stop hook is async and may
# land after run_ended, so the service reads the verdict and the question in the step's reply itself.
_VERDICT = re.compile(r"^[\s`*>\-]*VERDICT:\s*(PASS|FAIL)\b[ \t`*:\-]*(.*?)[ \t`*]*$", re.M)
_STOP = re.compile(r"^[\s`*>\-]*STOP:\s*(.+?)[\s`*]*$", re.M)
_NO_QUESTION = {"none", "n/a", "-", ""}


def reply_verdict(text: str) -> tuple:
    """(PASS or FAIL, detail) of the last whole `VERDICT:` line; ("", "") when there is none."""
    found = _VERDICT.findall(str(text or ""))
    if not found:
        return "", ""
    word, detail = found[-1]
    return word, redact.clip(redact.mask(detail.strip()), 160)


def reply_question(text: str) -> str:
    """The last whole `STOP: <question>` line's question; "" for none (`STOP: none` is not a question)."""
    found = _STOP.findall(str(text or ""))
    question = found[-1].strip() if found else ""
    return "" if question.rstrip(".").lower() in _NO_QUESTION else redact.clip(redact.mask(question), 200)


_LESSON = re.compile(r"^[\s`*>\-]*Lesson:\**\s*(.+?)[\s`*]*$", re.M)


def lesson_of(block: str) -> str:
    """The last `Lesson: <one sentence>` line of a handoff block (plan 22); "" for none or `Lesson: none`."""
    found = _LESSON.findall(str(block or ""))
    text = found[-1].strip() if found else ""
    return "" if text.rstrip(".").lower() in _NO_QUESTION else text


def note_file(task: dict, step: dict) -> str:
    return f"steps/{step['n']:02d}-{step['kind']}.md"


def handoff_file(task: dict, step: dict) -> str:
    """The session-handoff skill's note of the step Fred handed off."""
    return f"steps/{step['n']:02d}-handoff.md"


def facts_file(task: dict, step: dict) -> str:
    """The facts the service read when the step ended (git and its last test command): never compacted."""
    return f"steps/{step['n']:02d}-{step['kind']}.facts.md"


def brief_file(task: dict, step: dict) -> str:
    """The compacted note the next step reads (compact.py)."""
    return f"steps/{step['n']:02d}-{step['kind']}.brief.md"


def note_text(task: dict, step: dict, block: str, what: str = "") -> str:
    """A note file: one head line, then `block` masked and cut at 20 KB. `what` replaces the step's kind and route."""
    body = redact.mask(block)
    raw = body.encode("utf-8")
    if len(raw) > NOTE_MAX:
        body = raw[:NOTE_MAX].decode("utf-8", "ignore").rstrip() + "\n[cut at 20 KB]"
    what = what or f"{step['kind']} on {step['model']}/{step['effort']}"
    return f"# Step {step['n']:02d}: {what}, session {step['session']}\n\n{body}"


# -- steps and the chain (pure, on dicts) -----------------------------------------------------------------

def _blank(n: int, kind: str, goal: str, pick: str = "", checked: int = 0) -> dict:
    return {"n": n, "kind": kind, "goal": goal, "model": "", "effort": "", "pick": pick, "session": "",
            "state": "planned", "handoff": "", "verdict": "", "verdict_detail": "", "retries": 0, "cost": 0,
            "start_commit": "", "started": None, "ended": None, "notes": [], "checked": checked, "attempts": []}


TASK_KEYS = ("id", "project_dir", "project", "title", "type", "demand", "effort", "state", "owner", "current",
             "last_good", "escalated", "fable_ok", "prep", "why", "created", "updated", "steps")
STEP_KEYS = tuple(k for k in _blank(0, "", "") if k != "attempts")  # a task.json from before plan 19 loads


def whole(task) -> bool:
    """True when `task` has every key the service reads; a task.json from another version may not."""
    return (isinstance(task, dict) and all(k in task for k in TASK_KEYS) and isinstance(task["steps"], list)
            and all(isinstance(s, dict) and all(k in s for k in STEP_KEYS) for s in task["steps"]))


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


def attempts(step: dict) -> list:
    """Every session the step ran in, oldest first. A step from before plan 19 has no list: its one session."""
    if step.get("attempts"):
        return step["attempts"]
    if not step.get("session"):
        return []
    return [{"session": step["session"], "cost": step.get("cost") or 0, "started": step.get("started"),
             "ended": step.get("ended"), "why": "", "final": True}]


def step_cost(step: dict) -> float:
    """What the step cost over all its attempts."""
    return round(sum(a["cost"] or 0 for a in attempts(step)), 6)


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
    if s.get("attempts"):
        s["attempts"][-1].update(ended=now, why=why)


def start_step(task: dict, n: int, session: str, route: dict, start_commit: str, now: float) -> list:
    s = step(task, n)
    lines = [_line(now, dict(s, session=session), s["state"], "running", " · ".join(route["notes"]))]
    s["attempts"] = list(attempts(s)) + [{"session": session, "cost": 0, "started": now, "ended": None, "why": "",
                                          "final": False}]
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


def cap_reason(subtype: str, limits) -> str:
    """Why a step's run stopped at one of its caps (the result subtypes of the Agent SDK), else ""."""
    limits = limits or {}
    if subtype == "error_max_turns":
        return f"it hit the turn cap ({limits.get('max_turns') or '?'} turns)"
    if subtype == "error_max_budget_usd":
        return f"it hit the step budget ({float(limits.get('budget') or 0):.2f} USD)"
    if subtype == "error_step_timeout":
        return f"it hit the step timeout ({limits.get('timeout_s') or '?'} s)"
    return ""


def on_step_ended(task: dict, *, ok: bool, block_error: str, verdict: str, verdict_detail: str,
                  question: str, now: float, cap: str = ""):
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
        reason = cap or "the run did not finish cleanly" + (f" ({block_error})" if block_error else "")
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


def held(task: dict) -> bool:
    """The task waits because a step's model is over its pace (step_route's hold)."""
    return task["state"] == "waiting" and task["why"].endswith(" over its pace")


def fred(task: dict, lever: str, now: float, next_n: int = 0):
    """Fred's levers on the task state. (True, "", chain lines) when it applies, else (False, why, []).
    Confirm is the Fable confirm, or Run anyway for a budget hold of step `next_n` (that step only). Continue is
    Fred's Continue in the session of a stopped task's current step: the task runs on in that session. Handoff is
    Fred's Hand off in the current step's chat: the task is handed over and nothing more starts. Done is Fred's
    Mark done on a task that waits, is stuck, stopped or handed over."""
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
    elif lever == "continue":  # Fred's Continue in the stopped step's own session: the step runs on there
        if state != "stopped" or not s or s["state"] != "failed":
            return False, "not a stopped step", []
        lines.append(_line(now, s, "failed", "running", "continued by Fred"))
        s.update(state="running", ended=None)
        if s.get("attempts"):  # the same session: its cost is read again once the new turn ends
            s["attempts"][-1].update(ended=None, why="", final=False)
        _task_to(task, "running", "", now, s, lines)
        task["owner"] = "service"
    elif lever in ("handoff", "done"):
        if lever == "handoff" and state in ("done", "handed"):
            return False, f"task is {state}", []
        if lever == "done" and state not in ("waiting", "stuck", "stopped", "handed"):
            return False, f"task is {state}", []
        why = "handed off by Fred" if lever == "handoff" else "marked done by Fred"
        if s and s["state"] == "running":  # its turn is over (asks, or a hold): the step ends here, handed or done
            _finish(task, s, "handed" if lever == "handoff" else "done", now, lines, why)
        _task_to(task, "handed" if lever == "handoff" else "done", why, now, s, lines)
        task["owner"] = "fred"
    elif lever == "keep":  # Keep old plan: the replan proposal is dropped
        from . import replan
        if not (state == "waiting" and task["why"].startswith("replanned:")):
            return False, "no plan change waits", []
        lines += replan.keep(task, now)
        _task_to(task, "running", "", now, s, lines)
    elif lever == "redo":  # Redo design: the design step plans again with the question; done steps stay done
        design = next((x for x in task["steps"] if x["kind"] == "design"), None)
        waits = state == "waiting" and (task["why"].startswith("asks: Plan gap:") or task["why"].startswith("plan "))
        if design is None or not (waits or (state == "stuck" and s and s["kind"] == "design")):
            return False, "nothing to redo", []
        question = task["why"][len("asks: Plan gap: "):] if task["why"].startswith("asks: Plan gap:") else task["why"]
        if s and s["state"] == "running":
            _finish(task, s, "failed", now, lines, "stopped for a redo")
        for x in task["steps"]:
            if x["n"] >= design["n"] and x["state"] != "done" or x is design:
                if x["state"] != "planned":
                    lines.append(_line(now, x, x["state"], "planned", "redo by Fred"))
                x["state"], x["session"], x["ended"] = "planned", "", None
        design["retries"] = 0
        task["redo"], task["current"] = question, design["n"]
        _task_to(task, "running", "", now, design, lines)
        lines.append(_line(now, design, "planned", "planned", f"design redone by Fred: {question}"))
        task["owner"] = "service"
    elif lever == "confirm":
        from . import replan
        if held(task):
            task["hold_ok"] = next_n
        elif state == "waiting" and task["why"] == "confirm Fable":
            task["fable_ok"] = True
        elif state == "waiting" and task["why"].startswith("replanned:"):
            lines += replan.apply(task, now)
        elif state == "waiting" and task["why"] == "plan ready: confirm":
            lines.append(_line(now, s, "done", "done", "plan confirmed by Fred"))
        elif state == "waiting" and task["why"].startswith("plan ") and " KB, over " in task["why"]:
            lines.append(_line(now, s, "done", "done", "plan accepted by Fred"))
        else:
            return False, "nothing to confirm", []
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
    return data if whole(data) else None


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


def write_handoff(home, task: dict, step: dict, text: str) -> str:
    """The session-handoff skill's last message in the step Fred handed off, masked and cut like a step note;
    sets task["handoff_note"] and returns the relative name."""
    rel = handoff_file(task, step)
    path = folder(home, task["id"]) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(note_text(task, step, text, "handoff note"), encoding="utf-8")
    task["handoff_note"] = rel
    return rel


def read_handoff(home, task: dict) -> str:
    if not task.get("handoff_note"):
        return ""
    try:
        return (folder(home, task["id"]) / task["handoff_note"]).read_text(encoding="utf-8")
    except OSError:
        return ""


def read_brief(home, task: dict, n: int) -> str:
    try:
        return (folder(home, task["id"]) / brief_file(task, step(task, n))).read_text(encoding="utf-8")
    except (KeyError, OSError):
        return ""


def write_brief(home, task: dict, step: dict, text: str) -> str:
    """The compacted note of `step` (compact.run_brief's text) in its brief file; returns the relative name."""
    rel = brief_file(task, step)
    path = folder(home, task["id"]) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return rel


def write_facts(home, task: dict, step: dict, text: str) -> str:
    """The facts text of `step` (facts.text), masked; returns the relative name."""
    rel = facts_file(task, step)
    path = folder(home, task["id"]) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact.mask(text), encoding="utf-8")
    return rel


def read_facts(home, task: dict, n: int) -> str:
    try:
        return (folder(home, task["id"]) / facts_file(task, step(task, n))).read_text(encoding="utf-8")
    except (KeyError, OSError):
        return ""


def prune(home, days: float, now: float = None) -> list:
    """Remove the task folders of `done`, `stopped`, `stuck` and `handed` tasks whose task.json is older than `days`."""
    cutoff = (time.time() if now is None else now) - days * 86400
    root, removed = Path(home) / "tasks", []
    if not root.is_dir():
        return removed
    for entry in sorted(root.iterdir()):
        task = load(home, entry.name)
        if not task or task.get("state") not in ("done", "stopped", "stuck", "handed"):
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
    sessions = list(dict.fromkeys(a["session"] for s in task["steps"] for a in attempts(s) if a["session"]))
    root = folder(home, task["id"])
    if keep_last:
        last = step(task, task["last_good"]) if task["last_good"] else None
        keep = note_file(task, last) if last else ""
        kept = {keep, brief_file(task, last) if last else "", facts_file(task, last) if last else "",
                task.get("handoff_note") or ""}
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


_LESSON_LINE = re.compile(r"^- (\d{4}-\d\d-\d\d) - .*? - ([a-z]+): (.+)$")


def lessons_for(lines, kind: str, limit: int = LESSONS_IN_PROMPT) -> list:
    """The lessons a step of `kind` reads: lessons.md lines (levers.read_lessons, one project) whose kind is the
    step's own, newest last, at most `limit`, as `<day>: <sentence>`. A chat's lesson (`chat`) reaches no step."""
    out = []
    for line in lines or ():
        m = _LESSON_LINE.match(str(line).strip())
        if m and m.group(2) == kind:
            out.append(f"{m.group(1)}: {m.group(3)}")
    return out[-limit:] if limit > 0 else []


def received(prev_note: str, facts: str = "") -> str:
    """What the earlier steps left a step: the previous brief, then the facts the service read (never compacted)."""
    if not prev_note:
        return FIRST_STEP
    if not facts:
        return prev_note
    return f"{prev_note}\n\nFacts the service read when that step ended (git and its last test run, not compacted):\n{facts}"


def prompt_goal(task: dict, step: dict) -> str:
    """The goal as a step prompt carries it: whole (up to GOAL_MAX) for step 1, which has no handoff yet; cut to
    PROMPT_GOAL_MAX characters for every later step, whose handoff restates it under ## Goal."""
    goal = str(task.get("goal", ""))[:GOAL_MAX]
    if step["n"] == 1 or len(goal) <= PROMPT_GOAL_MAX:
        return goal
    return goal[:PROMPT_GOAL_MAX - 1].rstrip() + "\u2026"


def step_prompt(task: dict, step: dict, prev_note: str, retry_reason: str = "", special: str = "",
                plan: str = "", part: str = "", facts: str = "", lessons=()) -> str:
    kind = step["kind"]
    special = special or (Template(VERIFY_STEP).safe_substitute(checked=step["checked"] or step["n"] - 1)
                          if kind == "verify" else _fix_text(task, step) if kind == "fix" else "")
    retry = (f"Your earlier attempt at this step ended without a handoff: {retry_reason}. "
             "Start again from the handoff below.") if retry_reason else ""
    taught = (f"Lessons from earlier {kind} steps in this project (use one only where it applies):\n"
              + "\n".join(f"- {line}" for line in lessons) + "\n\n") if lessons else ""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        title=task["title"], goal=prompt_goal(task, step), n=step["n"], m=len(task["steps"]),
        kind=kind, step_goal=step["goal"], special=special, retry=retry,
        plan=plan + "\n\n" if plan else "", lessons=taught, part=part + "\n\n" if part else "",
        prev=received(prev_note, facts))
