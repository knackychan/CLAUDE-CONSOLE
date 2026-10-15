"""The replan step (brainstorm 8, D-7, plan 24): a read-tier pass with no tools, given the task goal, the briefs so far
and the remaining steps, answering with the remaining steps changed. Code validates the answer like tasks.plan_steps
(known kinds, at most MAX_ADDED steps added, the chain within task_max_steps, the verify re-placed); the task waits for
Fred's Confirm plan unless replan_auto is on. Inserted by the service when a handoff's Next line says `Replan: ...`, or
placed by Prep as a step of kind replan."""
import copy
import re
from string import Template

from . import compact, kinds, redact, tasks

KIND = "replan"
MAX_ADDED = 2
PROMPT_FILE = kinds.SEED / "replan.md"  # plan 28: the replan kind file's repo copy (the service reads kinds.text)
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["steps", "why"],
          "properties": {"why": {"type": "string"},
                         "steps": {"type": "array", "items": {
                             "type": "object", "additionalProperties": False, "required": ["kind", "goal"],
                             "properties": {"kind": {"type": "string", "enum": list(tasks.PREP_KINDS)},
                                            "goal": {"type": "string"}}}}}}
_ASK = re.compile(r"\bReplan:\**\s*(.+?)[\s`*]*$", re.M)


def ask_line(block: str) -> str:
    """The `Replan: <what and why>` line of a HANDOFF block (its Next section, or anywhere in it); "" when none."""
    m = _ASK.search(str(block or ""))
    return m.group(1).strip() if m else ""


def remaining(task: dict, n: int) -> list:
    """The planned steps after step `n` that the replan may change: every kind but verify and fix."""
    return [s for s in task["steps"] if s["n"] > n and s["state"] == "planned" and s["kind"] not in ("verify", "fix")]


def insert(task: dict, after_n: int, now: float, why: str) -> list:
    """A replan step right after step `after_n` (the handoff asked for one); the later steps move by one, a verify
    or fix that checks a later step follows it. Returns the chain lines."""
    at = task["steps"].index(tasks.step(task, after_n)) + 1
    for later in task["steps"][at:]:
        if later["checked"] > after_n:
            if later["goal"] == f"Check step {later['checked']}":
                later["goal"] = f"Check step {later['checked'] + 1}"
            later["checked"] += 1
        later["n"] += 1
    s = tasks._blank(after_n + 1, KIND, f"Replan: {why}")
    task["steps"].insert(at, s)
    task["updated"] = now
    return [tasks._line(now, s, "none", "planned", f"replan inserted after {after_n:02d}: {why}")]


def build_prompt(task: dict, n: int, briefs: str, raw: str = None) -> str:
    """The pass's prompt (the replan kind file, `raw`; the repo's seed when None): the goal, what the steps so far left,
    the remaining steps as planned, the kinds it may use and the room left in the chain."""
    s = tasks.step(task, n)
    rest = remaining(task, n)
    lines = [f"- {x['kind']}: {x['goal']}" for x in rest] or ["- (none)"]
    raw = PROMPT_FILE.read_text(encoding="utf-8") if raw is None else raw
    return Template(kinds.body_of(raw)).safe_substitute(
        task=redact.clip(task.get("goal") or task["title"], 600), why=s["goal"].replace("Replan: ", "", 1),
        briefs=briefs or "(nothing yet)", remaining="\n".join(lines), kinds=", ".join(tasks.PREP_KINDS),
        most=len(rest) + MAX_ADDED)


def check(task: dict, n: int, answer, max_steps: int) -> tuple:
    """(steps, "") when the answer is a usable remaining chain, else ([], why). The steps are blank dicts numbered
    from n + 1, the verify re-placed after the last edit, as tasks.plan_steps does; known kinds with a goal only;
    at most MAX_ADDED more than the remaining steps; the chain (verify left out) within tasks.room_after. An answer
    with no edit kind keeps the verify the replaced steps held, of the last edit step before n (plan 27)."""
    rest = remaining(task, n)
    items = answer.get("steps") if isinstance(answer, dict) else None
    if not isinstance(items, list) or not items:
        return [], "no steps in the answer"
    kept = []
    for item in items:
        if not isinstance(item, dict) or item.get("kind") not in tasks.PREP_KINDS or item.get("kind") == KIND:
            return [], f"unknown kind: {item.get('kind') if isinstance(item, dict) else item}"
        goal = item.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            return [], "a step has no goal"
        kept.append((item["kind"], redact.clip(goal, tasks.STEP_GOAL_MAX)))
    if len(kept) > len(rest) + MAX_ADDED:
        return [], f"{len(kept) - len(rest)} steps added, over {MAX_ADDED}"
    room = tasks.room_after(task, n, max_steps)
    if len(kept) > room:
        return [], f"{max_steps - room + len(kept)} steps in all, over task_max_steps {max_steps}"
    steps = [tasks._blank(n + i + 1, kind, goal) for i, (kind, goal) in enumerate(kept)]
    edits = [i for i, s in enumerate(steps) if s["kind"] in tasks.EDIT_KINDS]
    if edits:
        after = edits[-1] + 1
        steps.insert(after, tasks._blank(0, "verify", f"Check step {n + after}", checked=n + after))
        for i, s in enumerate(steps):
            s["n"] = n + i + 1
    else:
        before = [s["n"] for s in task["steps"] if s["n"] < n and s["kind"] in tasks.EDIT_KINDS]
        tail = any(s["n"] > n and s["kind"] == "verify" and s["state"] != "done" for s in task["steps"])
        if before and tail:  # the code is done, its verify was in the replaced tail: it stays, last
            steps.append(tasks._blank(n + len(steps) + 1, "verify", f"Check step {before[-1]}", checked=before[-1]))
    return steps, ""


def diff(before: list, after: list) -> dict:
    """What changed between two step lists, for the window: {"added": [indexes in after], "dropped": [indexes in
    before]} by (kind, goal); a verify or fix counts by kind alone, since the service re-places it."""
    key = lambda s: (s["kind"], "" if s["kind"] in ("verify", "fix") else s["goal"])
    old, new = [key(s) for s in before], [key(s) for s in after]
    return {"added": [i for i, k in enumerate(new) if k not in old], "dropped": [i for i, k in enumerate(old) if k not in new]}


def propose(task: dict, n: int, steps: list, why: str, now: float) -> list:
    """Keep the pass's answer on the task: task["replan"] = {"step": n, "before": [...], "after": [...], "why", "added",
    "dropped"}; the lists are [{"kind", "goal"}] for the window. Returns the chain line."""
    before = [s for s in task["steps"] if s["n"] > n]
    d = diff(before, steps)
    task["replan"] = {"step": n, "why": why, "added": d["added"], "dropped": d["dropped"],
                      "before": [{"kind": s["kind"], "goal": s["goal"]} for s in before],
                      "after": [{"kind": s["kind"], "goal": s["goal"]} for s in steps]}
    task["replan_steps"] = copy.deepcopy(steps)
    what = ", ".join(x for x in (f"{len(d['added'])} steps added" if d["added"] else "",
                                 f"{len(d['dropped'])} dropped" if d["dropped"] else "") if x) or "no change"
    return [tasks._line(now, tasks.step(task, n), "done", "done", f"replanned: {what}")]


def note_block(task: dict) -> str:
    """The replan step's handoff note (steps/NN-replan.md, written by the service through tasks.write_note): the why
    under Findings, the steps before and after under Next, so the chain log and the window keep the proposal."""
    r = task.get("replan") or {}
    before = "\n".join(f"- {s['kind']}: {s['goal']}" for s in r.get("before", [])) or "- (none)"
    after = "\n".join(f"- {s['kind']}: {s['goal']}" for s in r.get("after", [])) or "- (none)"
    goal = redact.clip(task.get("goal") or task["title"], 300)
    return ("## Goal\n" + goal + "\n## Findings\n" + (r.get("why") or "no change") + "\n## Files touched\n- (none)\n"
            "## Troubleshooting\n- (none)\n## Open questions\n- (none)\n## Next\nSteps before:\n" + before
            + "\nSteps after:\n" + after)


def summary(task: dict) -> str:
    """The task's why while it waits: `replanned: 2 steps added`, `replanned: 1 dropped`, `replanned: no change`."""
    r = task.get("replan") or {}
    what = ", ".join(x for x in (f"{len(r.get('added', []))} steps added" if r.get("added") else "",
                                 f"{len(r.get('dropped', []))} dropped" if r.get("dropped") else "") if x)
    return f"replanned: {what or 'no change'}"


def apply(task: dict, now: float) -> list:
    """Fred's Confirm plan (or replan_auto): the steps after the replan step become the proposed ones. Returns the
    chain line; the proposal is dropped from the task."""
    r, steps = task.pop("replan", None), task.pop("replan_steps", None)
    if not r or steps is None:
        return []
    n = r["step"]
    task["steps"] = [s for s in task["steps"] if s["n"] <= n] + copy.deepcopy(steps)
    task["updated"] = now
    return [tasks._line(now, tasks.step(task, n), "done", "done", f"plan changed: {len(steps)} steps follow {n:02d}")]


def keep(task: dict, now: float) -> list:
    """Fred's Keep old plan: the proposal is dropped, the steps stay as Prep made them."""
    r = task.pop("replan", None)
    task.pop("replan_steps", None)
    if not r:
        return []
    return [tasks._line(now, tasks.step(task, r["step"]), "done", "done", "old plan kept by Fred")]


def run_replan(cfg: dict, exe: list, task: dict, n: int, briefs: str, raw: str = None) -> dict:
    """Blocking (the service runs it in a thread). Never raises: {"steps": [...] or [], "why": str, "cost": float,
    "error": "" | why}. The pass runs on brief_model with no tools (claude_cli.brief_command, the replan schema);
    `raw` is the replan kind file (kinds.text)."""
    cost = 0
    try:
        answer, cost = compact._ask(cfg, exe, task["project_dir"], build_prompt(task, n, briefs, raw), SCHEMA)
    except compact.BriefError as exc:
        return {"steps": [], "why": "", "cost": cost, "error": str(exc)}
    steps, why = check(task, n, answer, cfg["task_max_steps"])
    return {"steps": steps, "why": redact.clip(str(answer.get("why", "")), 300) if isinstance(answer, dict) else "",
            "cost": cost, "error": why}
