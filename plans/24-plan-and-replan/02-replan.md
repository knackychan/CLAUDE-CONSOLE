# Task 2: The replan step

> Contract: [README.md](README.md) 3.2 (`replan`, `replan_steps`), 3.3, 3.9, 3.11. Brainstorm section 8, D-7. Run in a
> scratch copy on 2026-10-14: 6 tests OK, `tests/test_compact.py` 12 OK after the `_ask` change.

**Files**
- Create: `console/replan.py`, `console/replan_prompt.md`, `tests/test_replan.py`
- Modify: `console/compact.py` (`_ask` takes a schema; the brief's field check moves to `run_brief`),
  `tests/test_compact.py` (one test renamed if it asserted the old reason path; the 12 tests pass as they are)

## 2.1 Steps, in order

1. Write `tests/test_replan.py` (2.5); run it: fails on the import.
2. `console/compact.py`: `_ask(cfg, exe, project_dir, prompt, schema=BRIEF_SCHEMA)` passes `schema` to
   `claude_cli.brief_command` and returns `(structured_output dict, cost)`, raising `BriefError("the brief returned
   no structured output")` only when it is not a dict; a new `_fields_ok(fields) -> bool` holds the brief's check
   (three lists and a `next` string) and `run_brief` raises the same `BriefError` when it fails, right after `_ask`:

```python
def _ask(cfg: dict, exe: list, project_dir: str, prompt: str, schema: dict = BRIEF_SCHEMA):
    """One `claude -p` pass on brief_model with no tools, the answer shaped by `schema`; (answer dict, cost) or
    BriefError with the reason. The replan pass (replan.py) uses it with its own schema."""
    cmd = claude_cli.brief_command(exe, cfg["brief_model"], schema)
    ...  # unchanged up to the structured_output read
    fields = data.get("structured_output")
    if not isinstance(fields, dict):
        raise BriefError("the brief returned no structured output")
    return fields, data.get("total_cost_usd") or 0


def _fields_ok(fields: dict) -> bool:
    """The brief answer has its three lists and the next line."""
    return all(isinstance(fields.get(k), list) for k in ("findings", "files", "questions")) \
        and isinstance(fields.get("next"), str)
```

   and in `run_brief`, after `fields, cost = _ask(...)`: `if not _fields_ok(fields): raise BriefError("the brief
   returned no structured output")`. `tests/test_compact.py` passes unchanged (12 OK).
3. Write `console/replan_prompt.md` (2.4) and `console/replan.py` (2.3); run the module's tests: 6 OK.
4. Full suite, commit `plan 24 task 2: replan step`.

## 2.2 Drift guards

- `replan.check` is the only validator of the pass's answer; it never writes a verify of its own into the answer and
  always re-places one after the last edit kind, as `tasks.plan_steps` does.
- `insert` shifts `n` and `checked` of every later step by one and renames a `Check step N` goal; nothing else moves.
- `diff` counts a verify or fix by kind alone (the service re-places it), so a re-placed verify is never "added".
- `run_replan` never raises: a `BriefError` or a failed check lands in `"error"`; the service turns it into the retry
  rule (README 3.6).
- The pass runs on `cfg["brief_model"]`, resolved by the service to a model id as `start_brief` does (Task 3).

## 2.3 `console/replan.py` (final code, as verified)

```python
"""The replan step (brainstorm 8, D-7, plan 24): a read-tier pass with no tools, given the task goal, the briefs so far
and the remaining steps, answering with the remaining steps changed. Code validates the answer like tasks.plan_steps
(known kinds, at most MAX_ADDED steps added, the chain within task_max_steps, the verify re-placed); the task waits for
Fred's Confirm plan unless replan_auto is on. Inserted by the service when a handoff's Next line says `Replan: ...`, or
placed by Prep as a step of kind replan."""
import copy
import re
from pathlib import Path
from string import Template

from . import compact, redact, tasks

KIND = "replan"
MAX_ADDED = 2
PROMPT_FILE = Path(__file__).resolve().parent / "replan_prompt.md"
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


def build_prompt(task: dict, n: int, briefs: str) -> str:
    """The pass's prompt (console/replan_prompt.md): the goal, what the steps so far left, the remaining steps as
    planned, the kinds it may use and the room left in the chain."""
    s = tasks.step(task, n)
    rest = remaining(task, n)
    lines = [f"- {x['kind']}: {x['goal']}" for x in rest] or ["- (none)"]
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        task=redact.clip(task.get("goal") or task["title"], 600), why=s["goal"].replace("Replan: ", "", 1),
        briefs=briefs or "(nothing yet)", remaining="\n".join(lines), kinds=", ".join(tasks.PREP_KINDS),
        most=len(rest) + MAX_ADDED)


def check(task: dict, n: int, answer, max_steps: int) -> tuple:
    """(steps, "") when the answer is a usable remaining chain, else ([], why). The steps are blank dicts numbered
    from n + 1, the verify re-placed after the last edit, as tasks.plan_steps does; known kinds with a goal only;
    at most MAX_ADDED more than the remaining steps; the chain (verify left out) within max_steps."""
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
    if n + len(kept) > max_steps:
        return [], f"{n + len(kept)} steps in all, over task_max_steps {max_steps}"
    steps = [tasks._blank(n + i + 1, kind, goal) for i, (kind, goal) in enumerate(kept)]
    edits = [i for i, s in enumerate(steps) if s["kind"] in tasks.EDIT_KINDS]
    if edits:
        after = edits[-1] + 1
        steps.insert(after, tasks._blank(0, "verify", f"Check step {n + after}", checked=n + after))
        for i, s in enumerate(steps):
            s["n"] = n + i + 1
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
    return ("## Findings\n" + (r.get("why") or "no change") + "\n## Files touched\n- (none)\n## Open questions\n- (none)\n"
            "## Next\nSteps before:\n" + before + "\nSteps after:\n" + after)


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


def run_replan(cfg: dict, exe: list, task: dict, n: int, briefs: str) -> dict:
    """Blocking (the service runs it in a thread). Never raises: {"steps": [...] or [], "why": str, "cost": float,
    "error": "" | why}. The pass runs on brief_model with no tools (claude_cli.brief_command, the replan schema)."""
    cost = 0
    try:
        answer, cost = compact._ask(cfg, exe, task["project_dir"], build_prompt(task, n, briefs), SCHEMA)
    except compact.BriefError as exc:
        return {"steps": [], "why": "", "cost": cost, "error": str(exc)}
    steps, why = check(task, n, answer, cfg["task_max_steps"])
    return {"steps": steps, "why": redact.clip(str(answer.get("why", "")), 300) if isinstance(answer, dict) else "",
            "cost": cost, "error": why}
```

## 2.4 `console/replan_prompt.md`

```
Replan the rest of a task that Claude Console runs as a chain of separate steps. A step before you asked for it:
$why

Task: $task

What the steps so far found and left (their handoffs, newest last):
$briefs

The remaining steps, as planned now (each one runs in a fresh session on its own model):
$remaining

Answer with the JSON object only: steps, the remaining steps as they should be now, in order, each with its kind
and a one-line goal; why, one line on what changed and the reason. Kinds: $kinds. Keep every remaining step that
still makes sense, change the goals that the findings make wrong, add at most two steps and only what the findings
require, drop a step only when it is now pointless. At most $most steps. Do not add a verify: the service places
one after the last step that edits. Decide nothing beyond the step list.
```

## 2.5 `tests/test_replan.py` (final code, as verified)

```python
"""Plan 24: the replan step (console/replan.py): the ask line, insert, the prompt, check, propose, apply, keep."""
import unittest

from console import replan, tasks


def make_task(kinds=("scout", "code", "test", "verify", "document")):
    steps = [tasks._blank(i + 1, k, f"step {k}") for i, k in enumerate(kinds)]
    for s in steps:
        if s["kind"] == "verify":
            s["checked"], s["goal"] = 2, "Check step 2"
    t = tasks.new_task("D:/x", "x", "fills", "Goal: fills per model", steps, "normal",
                       {"reasoning": "low", "volume": "low"}, "", "auto", now=1.0)
    t["steps"][0]["state"], t["current"], t["last_good"] = "done", 1, 1
    return t


class ReplanTest(unittest.TestCase):
    def test_ask_line_reads_the_next_line(self):
        block = "## Findings\nx\n## Next\n02 code. **Replan:** usage.py has no week bucket yet"
        self.assertEqual(replan.ask_line(block), "usage.py has no week bucket yet")
        self.assertEqual(replan.ask_line("## Next\ngo on"), "")

    def test_insert_puts_a_replan_step_after_the_asking_step(self):
        t = make_task()
        lines = replan.insert(t, 1, 5.0, "no week bucket")
        self.assertEqual([(s["n"], s["kind"]) for s in t["steps"]],
                         [(1, "scout"), (2, "replan"), (3, "code"), (4, "test"), (5, "verify"), (6, "document")])
        self.assertEqual((t["steps"][4]["checked"], t["steps"][4]["goal"]), (3, "Check step 3"))
        self.assertEqual(lines[0]["why"], "replan inserted after 01: no week bucket")
        self.assertEqual(replan.remaining(t, 2), [t["steps"][2], t["steps"][3], t["steps"][5]])

    def test_prompt_carries_the_goal_the_briefs_and_the_remaining_steps(self):
        t = make_task()
        replan.insert(t, 1, 5.0, "no week bucket")
        text = replan.build_prompt(t, 2, "## Findings\n- usage.py builds day buckets only")
        self.assertIn("A step before you asked for it:\nno week bucket", text)
        self.assertIn("Task: Goal: fills per model", text)
        self.assertIn("- code: step code\n- test: step test\n- document: step document", text)
        self.assertIn("At most 5 steps", text)
        self.assertNotIn("$", text)

    def test_check_builds_the_steps_and_replaces_the_verify(self):
        t = make_task()
        replan.insert(t, 1, 5.0, "x")
        answer = {"why": "week buckets first", "steps": [{"kind": "code", "goal": "week buckets"},
                                                          {"kind": "code", "goal": "fills"}, {"kind": "test", "goal": "run"},
                                                          {"kind": "document", "goal": "docs"}]}
        steps, why = replan.check(t, 2, answer, 8)
        self.assertEqual(why, "")
        self.assertEqual([(s["n"], s["kind"]) for s in steps],
                         [(3, "code"), (4, "code"), (5, "test"), (6, "document"), (7, "verify")])
        self.assertEqual(steps[4]["checked"], 6)

    def test_check_refuses_too_many_added_unknown_kinds_and_a_long_chain(self):
        t = make_task()
        replan.insert(t, 1, 5.0, "x")
        many = {"why": "", "steps": [{"kind": "code", "goal": "g"}] * 6}
        self.assertEqual(replan.check(t, 2, many, 12)[1], "3 steps added, over 2")
        self.assertEqual(replan.check(t, 2, {"why": "", "steps": [{"kind": "verify", "goal": "g"}]}, 8)[1], "unknown kind: verify")
        self.assertEqual(replan.check(t, 2, {"why": "", "steps": [{"kind": "replan", "goal": "g"}]}, 8)[1], "unknown kind: replan")
        self.assertEqual(replan.check(t, 2, {"why": "", "steps": [{"kind": "code", "goal": " "}]}, 8)[1], "a step has no goal")
        self.assertEqual(replan.check(t, 2, {"why": "", "steps": []}, 8)[1], "no steps in the answer")
        four = {"why": "", "steps": [{"kind": "code", "goal": "g"}] * 4}
        self.assertEqual(replan.check(t, 2, four, 5)[1], "6 steps in all, over task_max_steps 5")

    def test_propose_apply_and_keep(self):
        t = make_task()
        replan.insert(t, 1, 5.0, "x")
        steps, _ = replan.check(t, 2, {"why": "w", "steps": [{"kind": "code", "goal": "week buckets"}, {"kind": "code", "goal": "step code"},
                                                             {"kind": "test", "goal": "step test"}, {"kind": "document", "goal": "step document"}]}, 8)
        lines = replan.propose(t, 2, steps, "week buckets first", 6.0)
        self.assertEqual(t["replan"]["added"], [0])
        self.assertEqual(t["replan"]["dropped"], [])
        self.assertEqual(replan.summary(t), "replanned: 1 steps added")
        self.assertEqual(lines[0]["why"], "replanned: 1 steps added")
        note = replan.note_block(t)
        self.assertIn("## Findings\nweek buckets first\n", note)
        self.assertIn("Steps after:\n- code: week buckets\n- code: step code", note)
        self.assertEqual(tasks.check_handoff(note), "")
        kept = replan.keep(dict(t), 7.0)
        self.assertEqual(kept[0]["why"], "old plan kept by Fred")
        lines = replan.apply(t, 7.0)
        self.assertEqual([(s["n"], s["kind"]) for s in t["steps"]],
                         [(1, "scout"), (2, "replan"), (3, "code"), (4, "code"), (5, "test"), (6, "document"), (7, "verify")])
        self.assertNotIn("replan", t)
        self.assertEqual(lines[0]["why"], "plan changed: 5 steps follow 02")
        self.assertEqual(replan.apply(t, 8.0), [])


if __name__ == "__main__":
    unittest.main()
```
