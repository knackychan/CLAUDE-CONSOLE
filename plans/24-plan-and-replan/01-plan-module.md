# Task 1: The plan module, the design prompt and the prompt slots

> Contract: [README.md](README.md) 3.1, 3.2 (`plan`, `part`, `hard`), 3.4, 3.5, 3.10. Decisions D1 (`design_input`) and
> D2 (`design_max_turns` in `design_text`). Run in a scratch copy on 2026-10-14: 21 tests OK.

**Files**
- Create: `console/plan.py`, `console/design_prompt.md` (already in the tree: written with this plan), `tests/test_plan.py`
- Modify: `console/step_prompt.md` (the `$plan` and `$part` slots), `console/tasks.py` (`step_prompt` signature),
  `console/paths.py` (the keys of README 3.8), `tests/test_tasks.py`

## 1.1 Steps, in order

1. Add the config keys to `paths.DEFAULTS` (README 3.8): `plan_max_kb`, `plan_max_parts`, `plan_hold`, `replan_auto`,
   `design_max_turns`; remove `opus_max_turns`. In `paths.load` (where the defaults are merged with config.json), a
   config.json that still has `opus_max_turns` and no `design_max_turns` keeps the value it had, once:
   `cfg.setdefault("design_max_turns", cfg.pop("opus_max_turns", DEFAULTS["design_max_turns"]))` after the merge
   (D2 a; with D2 b keep `opus_max_turns` and skip this step). `tests/test_paths.py::test_design_max_turns_replaces_the_opus_cap`.
2. Write `tests/test_plan.py` as listed in 1.4; run it: every test fails on the import.
3. Write `console/plan.py` as listed in 1.3; run the module's tests: 21 OK.
4. `console/step_prompt.md`: the two slots, as in 1.5. `tasks.step_prompt` takes `special`, `plan`, `part`:

```python
def step_prompt(task: dict, step: dict, prev_note: str, retry_reason: str = "", special: str = "",
                plan: str = "", part: str = "") -> str:
    kind = step["kind"]
    special = special or (Template(VERIFY_STEP).safe_substitute(checked=step["checked"] or step["n"] - 1)
                          if kind == "verify" else _fix_text(task, step) if kind == "fix" else "")
    retry = (f"Your earlier attempt at this step ended without a handoff: {retry_reason}. "
             "Start again from the note above.") if retry_reason else ""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        title=task["title"], goal=str(task.get("goal", ""))[:GOAL_MAX], n=step["n"], m=len(task["steps"]),
        kind=kind, step_goal=step["goal"], special=special, retry=retry, plan=plan, part=part,
        prev=prev_note or "This is the first step: there is no handoff note yet.")
```

   `tests/test_tasks.py::test_step_prompt_carries_the_plan_and_the_part` asserts the plan text sits before "Handoff
   note of the previous step" and the part text right before "Rules for this step:", and that with both empty the
   prompt equals today's (the existing step_prompt tests keep passing unchanged).
5. `tasks.RULES` gains `"replan": ("haiku", "low", "")` after `"design"` (Task 2 uses it; placing it here keeps
   `PREP_KINDS` stable for both tasks). `tests/test_tasks.py::test_rules_name_the_replan_kind`.
6. Full suite, commit `plan 24 task 1: plan module, design prompt, prompt slots`.

## 1.2 Drift guards

- `plan.py` imports `tasks` and `redact` only; `tasks` does not import `plan` (the service does).
- `check` is the single validator (README 3.11); every reason string is the one of README 3.4.
- `rebuild` replaces planned steps whose kind is among the parts' kinds only; done steps keep their place.
- `design_input` (D1 a) reads raw notes with `tasks.read_note`, never the briefs; with D1 (b) the function is not
  written and the service passes the brief as for any step.
- `design_text` reads `cfg["design_max_turns"]` (D2 a); with D2 (b) it reads `cfg["opus_max_turns"]`.

## 1.3 `console/plan.py` (final code, as verified)

```python
"""The plan the design step writes (brainstorm 8b, plan 24): the PLAN block and the SUBPLAN blocks of the step's final
message, parsed and checked here, saved by the service as tasks/<id>/plan.md and plan/NN-<slug>.md, read whole by every
later step. Pure functions on text and dicts; the file functions take the data home, as tasks.py's do. The plan is never
compacted and never cut: the only bound is plan_max_kb, and over it the task waits for Fred."""
import re
from datetime import date
from pathlib import Path
from string import Template

from . import redact, tasks

MARK_START, MARK_END = "PLAN", "END PLAN"
PART_END = "END SUBPLAN"
_PART = re.compile(r"^SUBPLAN\s+(\d+)\s+([a-z]+)\s+(\S.*?)\s*$")  # SUBPLAN 1 code <title>
HEADINGS = ("## Goal", "## Decisions", "## Out of scope", "## Files", "## Steps", "## Acceptance")
INDEX_HEADINGS = ("## Goal", "## Decisions", "## Out of scope", "## Sub-plans", "## Acceptance")
PART_HEADINGS = ("## Files", "## Actions", "## Tests", "## Done check")
STEP_HEADINGS = ("#### Files", "#### Actions", "#### Tests", "#### Done check")
WRITE_KINDS = ("code", "document", "debug", "edit", "draft")  # tasks.EDIT_KINDS, in the order the prompt names them
FILE = "plan.md"
PART_DIR = "plan"
PROMPT_FILE = Path(__file__).resolve().parent / "design_prompt.md"
_STEP = re.compile(r"^### Step (\d+): ([a-z]+)\s*$", re.M)
_ROW = re.compile(r"^\|\s*(\d+)\s*\|(.*)\|\s*$")
_GAP = re.compile(r"^[\s`*>\-]*Plan gap:\**\s*(.+?)[\s`*]*$", re.M)
_BAD = re.compile(r"\b(TBD|TODO)\b")
_HEAD = re.compile(r"^#{1,4} ", re.M)


# -- parse ------------------------------------------------------------------------------------------------

def parse(text):
    """{"index": str, "parts": [{"n", "kind", "title", "text"}]} from the last PLAN .. END PLAN block of `text` and every
    SUBPLAN n kind title .. END SUBPLAN block after it (marker lines left out, dressed as tasks._mark allows); None when
    there is no PLAN block."""
    lines = str(text or "").splitlines()
    blocks, start = [], None
    for i, line in enumerate(lines):
        mark = tasks._mark(line)
        if mark == MARK_START:
            start = i
        elif mark == MARK_END and start is not None:
            blocks.append((start, i))
            start = None
    if not blocks:
        return None
    a, b = blocks[-1]
    parts, head = [], None
    for i in range(b + 1, len(lines)):
        mark = tasks._mark(lines[i])
        m = _PART.match(mark)
        if m and head is None:
            head = (i, int(m.group(1)), m.group(2), m.group(3))
        elif mark == PART_END and head is not None:
            parts.append({"n": head[1], "kind": head[2], "title": head[3],
                          "text": "\n".join(lines[head[0] + 1:i]).strip() + "\n"})
            head = None
    return {"index": "\n".join(lines[a + 1:b]).strip() + "\n", "parts": parts}


def section(text: str, heading: str) -> str:
    """The lines under `heading` (a `## ` line) up to the next `## ` line; "" when the heading is absent."""
    lines = str(text or "").splitlines()
    out, on = [], False
    for line in lines:
        if line.strip() == heading:
            on, out = True, []
            continue
        if on and line.startswith("## "):
            break
        if on:
            out.append(line)
    return "\n".join(out).strip()


def step_section(text: str, n: int) -> str:
    """The `### Step N: <kind>` section whole (its head line included) up to the next `### ` or `## ` line; "" when absent."""
    lines = str(text or "").splitlines()
    out, on = [], False
    for line in lines:
        m = _STEP.match(line)
        if m and int(m.group(1)) == n:
            on, out = True, [line]
            continue
        if on and (line.startswith("### ") or line.startswith("## ")):
            break
        if on:
            out.append(line)
    return "\n".join(out).strip()


def table(index: str) -> list:
    """The rows of the Sub-plans table: [{"n", "title", "kind", "owns": [...], "depends": [ints], "hard": bool}], in the
    order written; a row that is not `| n | ... |` with six cells is skipped."""
    rows = []
    for line in section(index, "## Sub-plans").splitlines():
        m = _ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) != 5:
            continue
        title, kind, owns, depends, hard = cells
        rows.append({"n": int(m.group(1)), "title": title, "kind": kind,
                     "owns": [f for f in (x.strip() for x in owns.split(",")) if f and f != "-"],
                     "depends": [int(x) for x in re.findall(r"\d+", depends)],
                     "hard": hard.lower().startswith("y")})
    return rows


def gap(block: str) -> str:
    """The first `Plan gap:` line of a HANDOFF block (a writer that met a fork the plan does not settle); "" when none."""
    m = _GAP.search(str(block or ""))
    return m.group(1).strip() if m else ""


def words(plan: dict) -> int:
    return len(plan["index"].split()) + sum(len(p["text"].split()) for p in plan["parts"])


def kb(plan: dict) -> float:
    size = len(plan["index"].encode("utf-8")) + sum(len(p["text"].encode("utf-8")) for p in plan["parts"])
    return round(size / 1024, 1)


# -- check ------------------------------------------------------------------------------------------------

def _headings(text: str, wanted: tuple) -> str:
    lines = [line.strip() for line in str(text or "").splitlines()]
    at = []
    for heading in wanted:
        if heading not in lines:
            return f"missing: {heading}"
        at.append(lines.index(heading))
    return "" if at == sorted(at) else "headings out of order"


def check(plan: dict, later: list, max_parts: int, room: int) -> str:
    """"" when the plan has its shape (README 3.4), else the first reason found. `later`: the task's steps after the
    design step (their n and kind); `room`: how many steps may follow the design step after a split, the verify not
    counted (task_max_steps minus the design step's n)."""
    index, parts = plan["index"], plan["parts"]
    if _BAD.search(index) or any(_BAD.search(p["text"]) for p in parts):
        return "TBD or TODO left in the plan"
    why = _headings(index, INDEX_HEADINGS if parts else HEADINGS)
    if why:
        return why
    for line in section(index, "## Decisions").splitlines():
        if line.strip().endswith("?"):
            return f"a Decisions line is a question: {redact.clip(line.strip(), 60)}"
    if not parts:
        found = {int(m.group(1)) for m in _STEP.finditer(index)}
        for s in later:
            if s["kind"] in tasks.EDIT_KINDS and s["n"] not in found:
                return f"missing: ### Step {s['n']}"
        for n in sorted(found):
            why = _headings(step_section(index, n), STEP_HEADINGS)
            if why:
                return f"Step {n}: {why}"
        return ""
    rows = table(index)
    if not rows:
        return "missing: the Sub-plans table"
    if len(parts) > max_parts:
        return f"{len(parts)} parts, over plan_max_parts {max_parts}"
    if len(parts) < 2:
        return "a split needs at least 2 parts"
    if [p["n"] for p in parts] != list(range(1, len(parts) + 1)):
        return "parts not numbered 1 to N in order"
    if [r["n"] for r in rows] != [p["n"] for p in parts]:
        return "the Sub-plans table and the SUBPLAN blocks differ"
    for r, p in zip(rows, parts):
        if r["kind"] not in WRITE_KINDS:
            return f"part {p['n']}: {r['kind']} is not a write kind"
        if r["kind"] != p["kind"]:
            return f"part {p['n']}: the table says {r['kind']}, the block {p['kind']}"
        if any(d < 1 or d >= p["n"] for d in r["depends"]):
            return f"part {p['n']} depends on a part that is not earlier"
        why = _headings(p["text"], PART_HEADINGS)
        if why:
            return f"part {p['n']}: {why}"
    owner = {}
    for r in rows:
        for f in r["owns"]:
            if f in owner and owner[f] not in r["depends"]:
                return f"{f} is owned by parts {owner[f]} and {r['n']}, which does not depend on {owner[f]}"
            owner.setdefault(f, r["n"])
    kinds_of_parts = {p["kind"] for p in parts}
    others = sum(1 for s in later if s["kind"] not in kinds_of_parts and s["kind"] not in ("verify", "fix")
                 and s["state"] != "done")
    if len(parts) + others > room:
        return f"{len(parts) + others} steps after the design step, over task_max_steps"
    return ""


# -- the chain after a split ------------------------------------------------------------------------------

def rebuild(task: dict, n: int, parts: list, now: float) -> list:
    """After design step `n` split the plan: the planned steps after it whose kind is a part's kind (Prep's code steps
    when the parts are code) are replaced by one step per part, in the table's order (`part` = its number, `hard` from
    the table); the done steps after it keep their place, the other planned steps (a test, a document the plan does
    not cover) follow the parts in their order, and the verify is re-placed after the last edit kind. Sets each part's
    "step". Returns the chain line."""
    design = tasks.step(task, n)
    at = task["steps"].index(design) + 1
    after = task["steps"][at:]
    kinds_of_parts = {p["kind"] for p in parts}
    had = sum(1 for s in after if s["kind"] in kinds_of_parts)
    done = [s for s in after if s["state"] == "done"]
    others = [s for s in after if s["state"] != "done" and s["kind"] not in kinds_of_parts
              and s["kind"] not in ("verify", "fix")]
    new = []
    for p in parts:
        s = tasks._blank(0, p["kind"], f"Part {p['n']}: {p['title']}")
        s["part"], s["hard"] = p["n"], bool(p.get("hard"))
        new.append(s)
    steps = task["steps"][:at] + done + new + others
    last = max(i for i, s in enumerate(steps) if s["kind"] in tasks.EDIT_KINDS)
    steps.insert(last + 1, tasks._blank(0, "verify", "", checked=0))
    for i, s in enumerate(steps):
        s["n"] = i + 1
    steps[last + 1].update(goal=f"Check step {last + 1}", checked=last + 1)
    for p, s in zip(parts, new):
        p["step"] = s["n"]
    task["steps"], task["updated"] = steps, now
    kinds = ", ".join(f"{sum(1 for s in new if s['kind'] == k)} {k}" for k in dict.fromkeys(s["kind"] for s in new))
    return [tasks._line(now, design, "done", "done",
                        f"design split into {len(parts)} sub-plans: {kinds} steps (Prep had {had})")]


# -- files ------------------------------------------------------------------------------------------------

def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(title or "").lower()).strip("-")[:40] or "part"


def part_file(n: int, title: str) -> str:
    return f"{PART_DIR}/{n:02d}-{slug(title)}.md"


def save(home, task: dict, plan: dict, n: int) -> dict:
    """Write plan.md (the plan, or the index) and plan/NN-<slug>.md per part, masked like a note; returns the value of
    task["plan"]: {"from": n, "words", "kb", "parts": [{"n", "kind", "title", "file", "owns", "depends", "hard",
    "step": 0}]} ("step" is set by rebuild)."""
    folder = tasks.folder(home, task["id"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / FILE).write_text(redact.mask(plan["index"]), encoding="utf-8")
    rows = {r["n"]: r for r in table(plan["index"])}
    meta = []
    for p in plan["parts"]:
        rel = part_file(p["n"], p["title"])
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Part {p['n']}: {p['title']}\n\n" + redact.mask(p["text"]), encoding="utf-8")
        r = rows.get(p["n"], {})
        meta.append({"n": p["n"], "kind": p["kind"], "title": p["title"], "file": rel, "owns": r.get("owns", []),
                     "depends": r.get("depends", []), "hard": bool(r.get("hard")), "step": 0})
    return {"from": n, "words": words(plan), "kb": kb(plan), "parts": meta}


def read(home, task: dict) -> str:
    try:
        return (tasks.folder(home, task["id"]) / FILE).read_text(encoding="utf-8")
    except OSError:
        return ""


def read_part(home, task: dict, k: int) -> str:
    meta = (task.get("plan") or {}).get("parts") or []
    part = next((p for p in meta if p["n"] == k), None)
    if part is None:
        return ""
    try:
        return (tasks.folder(home, task["id"]) / part["file"]).read_text(encoding="utf-8")
    except OSError:
        return ""


def part_body(text: str) -> str:
    """A part's text without the `# Part N: <title>` head line `save` wrote (what Fred's edit sends back)."""
    lines = str(text or "").splitlines()
    if lines and lines[0].startswith("# Part "):
        lines = lines[1:]
    return "\n".join(lines).strip() + "\n"


def write(home, task: dict, text: str, k: int = 0) -> str:
    """Fred's edit of the index (k = 0) or of part k, through the service; a part is written with its head line
    again. Returns the relative file name."""
    rel = FILE if not k else next(p["file"] for p in task["plan"]["parts"] if p["n"] == k)
    path = tasks.folder(home, task["id"]) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if k:
        title = next(p["title"] for p in task["plan"]["parts"] if p["n"] == k)
        text = f"# Part {k}: {title}\n\n" + part_body(text)
    path.write_text(str(text or ""), encoding="utf-8")
    return rel


def with_answer(index: str, answer: str, day: str = "") -> str:
    """The index with `- Fred, <date>: <answer>` as the last line of ## Decisions."""
    day = day or date.today().isoformat()
    lines = str(index or "").splitlines()
    out, on, placed = [], False, False
    for line in lines:
        if on and line.startswith("## ") and not placed:
            while out and not out[-1].strip():
                out.pop()
            out += [f"- Fred, {day}: {answer.strip()}", ""]
            placed = True
        if line.strip() == "## Decisions":
            on = True
        out.append(line)
    if on and not placed:
        while out and not out[-1].strip():
            out.pop()
        out.append(f"- Fred, {day}: {answer.strip()}")
    return "\n".join(out).rstrip() + "\n"


def add_answer(home, task: dict, answer: str, day: str = "") -> str:
    """Append Fred's answer to the Decisions of plan.md; returns the line written."""
    text = with_answer(read(home, task), answer, day)
    write(home, task, text)
    return text.rstrip().splitlines()[-1] if not section(text, "## Decisions") else section(text, "## Decisions").splitlines()[-1]


# -- what the prompts carry -------------------------------------------------------------------------------

def design_text(task: dict, step: dict, cfg: dict, redo: str = "") -> str:
    """The design step's part of the step prompt (console/design_prompt.md): the later steps, the write steps that need a
    ### Step N section, the limits, and on a redo the question and the steps already done."""
    later = [s for s in task["steps"] if s["n"] > step["n"]]
    lines = [f"- Step {s['n']}: {s['kind']}. {s['goal']}" + (" (done, kept)" if s["state"] == "done" else "")
             for s in later] or ["- (none planned yet)"]
    edits = ", ".join(str(s["n"]) for s in later if s["kind"] in tasks.EDIT_KINDS and s["state"] != "done") or "none"
    redo_text = ""
    if redo:
        redo_text = ("Fred asked for this plan again: " + redo + " Plan the steps that are not done; a done step keeps "
                     "its place and its work, and its handoff is above.")
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        turns=cfg["design_max_turns"], later="\n".join(lines), edit_steps=edits, redo=redo_text,
        max_kb=cfg["plan_max_kb"], max_parts=cfg["plan_max_parts"], room=max(cfg["task_max_steps"] - step["n"], 1),
        write_kinds=", ".join(WRITE_KINDS))


def design_input(home, task: dict, n: int) -> str:
    """What the design step reads instead of a brief: the raw handoff notes of every earlier step, whole (D1)."""
    out = []
    for s in task["steps"]:
        if s["n"] >= n:
            break
        note = tasks.read_note(home, task, s["n"])
        if note:
            out.append(note)
    return "\n\n".join(out)


PLAN_RULE = ("- The plan settles the work. If it does not settle something this step needs, do not choose: stop, put "
             "the question under Open questions starting with `Plan gap:`, and end with the HANDOFF block as usual.")
VERIFY_RULE = ("- Check the diff against the plan's Steps and Acceptance: a departure from them is a FAIL whose detail "
               "starts with `plan drift:`.")


def prompt_parts(home, task: dict, step: dict) -> tuple:
    """(plan, part) for tasks.step_prompt of a step after the design step: the index whole under its head line and the
    rule; the step's own ### Step N section, or its sub-plan file whole, or every part for a verify or a fix; ("", "")
    before the design step or when the task has no plan."""
    meta = task.get("plan")
    if not meta or step["n"] <= meta["from"]:
        return "", ""
    index = read(home, task)
    rule = VERIFY_RULE if step["kind"] in ("verify", "fix") else PLAN_RULE
    plan_text = f"The plan (follow it, do not change it):\n{index}\n{rule}"
    if step["kind"] in ("verify", "fix"):
        own = "\n\n".join(read_part(home, task, p["n"]) for p in meta["parts"]) if meta["parts"] else ""
    elif step.get("part"):
        own = read_part(home, task, step["part"])
    elif step["kind"] in tasks.EDIT_KINDS:
        own = step_section(index, step["n"])
    else:
        own = ""
    return plan_text, (f"Your part of the plan:\n{own}" if own else "")
```

## 1.4 `tests/test_plan.py` (final code, as verified)

```python
"""Plan 24: the design step's plan (console/plan.py): parse, check, split, files, answers, prompt parts."""
import os
import tempfile
import unittest

from console import plan, tasks

STEP = """### Step {n}: code
#### Files
- calc.py
#### Actions
1. `def add(a: int, b: int) -> int` in calc.py.
#### Tests
- tests/test_calc.py::test_add asserts add(1, 2) == 3
#### Done check
py -m unittest tests.test_calc -q prints OK
"""
INDEX = """# Plan: calc
## Goal
add() in calc.py; done when the test passes.
## Decisions
- add lives in calc.py: the only module.
## Out of scope
- sub()
## Files
- calc.py (change): add()
## Steps
{steps}
## Acceptance
- tests/test_calc.py passes
"""
PART = """## Files
- {f}
## Actions
1. write {f}
## Tests
- tests/test_{f}.py::test_it
## Done check
py -m unittest -q
"""
SPLIT_INDEX = """# Plan: calc
## Goal
two modules.
## Decisions
- one part per module.
## Out of scope
- (none)
## Sub-plans
| # | Part | Kind | Owns | Depends on | Hard |
|---|---|---|---|---|---|
| 1 | Calc module | code | calc.py | - | no |
| 2 | Report module | code | report.py, calc.py | 1 | yes |
## Acceptance
- both suites pass
"""


def single(n=2):
    return "thinking...\nPLAN\n" + INDEX.format(steps=STEP.format(n=n)) + "END PLAN\nHANDOFF\n## Findings\nx\nEND HANDOFF"


def split():
    return ("PLAN\n" + SPLIT_INDEX + "END PLAN\n" + "SUBPLAN 1 code Calc module\n" + PART.format(f="calc.py")
            + "END SUBPLAN\n**SUBPLAN 2 code Report module**\n" + PART.format(f="report.py") + "END SUBPLAN\n"
            "HANDOFF\n## Findings\nx\nEND HANDOFF")


def make_task(kinds=("scout", "design", "code", "test", "verify", "document")):
    steps = [tasks._blank(i + 1, k, f"step {k}") for i, k in enumerate(kinds)]
    for s in steps:
        if s["kind"] == "verify":
            s["checked"] = 3
    return tasks.new_task("D:/x", "x", "calc", "Goal: add()", steps, "normal", {"reasoning": "low", "volume": "low"},
                          "", "auto", now=1.0)


class ParseTest(unittest.TestCase):
    def test_parse_takes_the_last_plan_block_and_the_parts_after_it(self):
        p = plan.parse("PLAN\nold\nEND PLAN\n" + split())
        self.assertIn("## Sub-plans", p["index"])
        self.assertEqual([x["n"] for x in p["parts"]], [1, 2])
        self.assertEqual(p["parts"][1]["title"], "Report module")
        self.assertTrue(p["parts"][0]["text"].startswith("## Files"))
        self.assertIsNone(plan.parse("no plan here"))

    def test_section_and_step_section(self):
        idx = INDEX.format(steps=STEP.format(n=3) + STEP.format(n=5))
        self.assertEqual(plan.section(idx, "## Out of scope"), "- sub()")
        self.assertTrue(plan.step_section(idx, 5).startswith("### Step 5: code"))
        self.assertNotIn("Step 3", plan.step_section(idx, 5))
        self.assertEqual(plan.step_section(idx, 9), "")

    def test_table_reads_the_sub_plans_rows(self):
        rows = plan.table(SPLIT_INDEX)
        self.assertEqual(rows[1], {"n": 2, "title": "Report module", "kind": "code", "owns": ["report.py", "calc.py"],
                                   "depends": [1], "hard": True})
        self.assertEqual(rows[0]["depends"], [])

    def test_gap_finds_the_plan_gap_line(self):
        block = "## Findings\nx\n## Open questions\n- **Plan gap:** config.json or models.json?\n## Next\ngo"
        self.assertEqual(plan.gap(block), "config.json or models.json?")
        self.assertEqual(plan.gap("## Open questions\n- (none)"), "")


class CheckTest(unittest.TestCase):
    def later(self, t, n=2):
        return [s for s in t["steps"] if s["n"] > n]

    def test_check_passes_a_whole_single_plan(self):
        t = make_task()
        p = plan.parse(single(3) .replace(STEP.format(n=3), STEP.format(n=3) + STEP.format(n=6).replace("code", "document")))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "")

    def test_check_names_the_missing_heading_and_step(self):
        t = make_task()
        p = plan.parse(single(3))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "missing: ### Step 6")
        p = plan.parse(single(3).replace("## Acceptance\n", "## Accept\n"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "missing: ## Acceptance")
        both = single(3).replace(STEP.format(n=3), STEP.format(n=3) + STEP.format(n=6))
        p = plan.parse(both.replace("### Step 3: code\n#### Files\n- calc.py\n#### Actions", "### Step 3: code\n#### Files\n- calc.py\n#### Action"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "Step 3: missing: #### Actions")

    def test_check_refuses_todo_and_open_decisions(self):
        t = make_task(("design", "code", "verify"))
        p = plan.parse(single(2).replace("add()", "add() TODO"))
        self.assertEqual(plan.check(p, self.later(t, 1), 6, 5), "TBD or TODO left in the plan")
        p = plan.parse(single(2).replace("- add lives in calc.py: the only module.", "- where does add live?"))
        self.assertTrue(plan.check(p, self.later(t, 1), 6, 5).startswith("a Decisions line is a question"))

    def test_check_passes_a_split_plan_and_counts_the_room(self):
        t = make_task()
        p = plan.parse(split())
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "")
        self.assertEqual(plan.check(p, self.later(t), 6, 3), "4 steps after the design step, over task_max_steps")
        self.assertEqual(plan.check(p, self.later(t), 1, 4), "2 parts, over plan_max_parts 1")

    def test_check_refuses_a_bad_split(self):
        t = make_task()
        p = plan.parse(split().replace("| 2 | Report module | code | report.py, calc.py | 1 | yes |",
                                       "| 2 | Report module | code | report.py, calc.py | - | yes |"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4),
                         "calc.py is owned by parts 1 and 2, which does not depend on 1")
        p = plan.parse(split().replace("| 2 | Report module | code |", "| 2 | Report module | scout |"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "part 2: scout is not a write kind")
        p = plan.parse(split().replace("| 1 | Calc module | code | calc.py | - | no |", "| 1 | Calc module | code | calc.py | 2 | no |"))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "part 1 depends on a part that is not earlier")
        p = plan.parse(split().replace("## Tests\n- tests/test_report.py.py::test_it\n", ""))
        self.assertEqual(plan.check(p, self.later(t), 6, 4), "part 2: missing: ## Tests")


class RebuildTest(unittest.TestCase):
    def test_rebuild_replaces_the_write_steps_and_replaces_the_verify(self):
        t = make_task()
        meta = plan.save(tempfile.mkdtemp(), t, plan.parse(split()), 2)
        lines = plan.rebuild(t, 2, meta["parts"], 5.0)
        self.assertEqual([(s["n"], s["kind"]) for s in t["steps"]],
                         [(1, "scout"), (2, "design"), (3, "code"), (4, "code"), (5, "test"), (6, "document"), (7, "verify")])
        self.assertEqual([s.get("part", 0) for s in t["steps"]], [0, 0, 1, 2, 0, 0, 0])
        self.assertTrue(t["steps"][3]["hard"])
        self.assertEqual(t["steps"][6]["checked"], 6)
        self.assertEqual([p["step"] for p in meta["parts"]], [3, 4])
        self.assertEqual(lines[0]["why"], "design split into 2 sub-plans: 2 code steps (Prep had 1)")

    def test_rebuild_keeps_the_done_steps_on_a_redo(self):
        t = make_task()
        t["steps"][2]["state"] = "done"
        meta = plan.save(tempfile.mkdtemp(), t, plan.parse(split()), 2)
        plan.rebuild(t, 2, meta["parts"], 5.0)
        self.assertEqual([(s["n"], s["kind"], s["state"]) for s in t["steps"]][:4],
                         [(1, "scout", "planned"), (2, "design", "planned"), (3, "code", "done"), (4, "code", "planned")])


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.t = make_task()

    def test_save_writes_the_index_and_the_parts(self):
        meta = plan.save(self.home, self.t, plan.parse(split()), 2)
        self.assertEqual(meta["parts"][1]["file"], "plan/02-report-module.md")
        self.assertTrue(meta["parts"][1]["hard"])
        self.assertEqual(meta["parts"][1]["owns"], ["report.py", "calc.py"])
        self.assertTrue(os.path.exists(os.path.join(self.home, "tasks", self.t["id"], "plan.md")))
        self.t["plan"] = meta
        self.assertTrue(plan.read_part(self.home, self.t, 2).startswith("# Part 2: Report module"))
        self.assertIn("## Sub-plans", plan.read(self.home, self.t))
        self.assertGreater(meta["words"], 40)
        self.assertGreater(meta["kb"], 0)

    def test_with_answer_appends_to_decisions(self):
        text = plan.with_answer(SPLIT_INDEX, "ladder in config.json", "2026-10-14")
        dec = plan.section(text, "## Decisions")
        self.assertEqual(dec.splitlines()[-1], "- Fred, 2026-10-14: ladder in config.json")
        self.assertIn("## Out of scope", text)
        self.assertEqual(plan.section(text, "## Out of scope"), "- (none)")

    def test_add_answer_writes_the_file(self):
        self.t["plan"] = plan.save(self.home, self.t, plan.parse(split()), 2)
        line = plan.add_answer(self.home, self.t, "config.json", "2026-10-14")
        self.assertEqual(line, "- Fred, 2026-10-14: config.json")
        self.assertIn(line, plan.read(self.home, self.t))

    def test_part_body_drops_the_head(self):
        self.assertEqual(plan.part_body("# Part 2: Report\n\n## Files\n- a"), "## Files\n- a\n")
        self.assertEqual(plan.part_body("## Files\n- a\n"), "## Files\n- a\n")

    def test_write_replaces_the_index_or_a_part(self):
        self.t["plan"] = plan.save(self.home, self.t, plan.parse(split()), 2)
        self.assertEqual(plan.write(self.home, self.t, "# edited\n"), "plan.md")
        self.assertEqual(plan.read(self.home, self.t), "# edited\n")
        self.assertEqual(plan.write(self.home, self.t, "## Files\n- b\n", 2), "plan/02-report-module.md")
        self.assertEqual(plan.read_part(self.home, self.t, 2), "# Part 2: Report module\n\n## Files\n- b\n")


class PromptTest(unittest.TestCase):
    CFG = {"design_max_turns": 30, "plan_max_kb": 100, "plan_max_parts": 6, "task_max_steps": 6}

    def test_design_text_lists_the_later_steps_and_the_limits(self):
        t = make_task()
        text = plan.design_text(t, tasks.step(t, 2), self.CFG)
        self.assertIn("- Step 3: code. step code", text)
        self.assertIn("($edit_steps)".replace("$edit_steps", "3, 6"), text)
        self.assertIn("You have 30 turns", text)
        self.assertIn("at most 6", text)
        self.assertIn("within 4 steps", text)
        self.assertNotIn("$", text)

    def test_design_text_on_a_redo_names_the_question_and_the_done_steps(self):
        t = make_task()
        t["steps"][2]["state"] = "done"
        text = plan.design_text(t, tasks.step(t, 2), self.CFG, "step 4 asked: config.json or models.json?")
        self.assertIn("Fred asked for this plan again: step 4 asked", text)
        self.assertIn("- Step 3: code. step code (done, kept)", text)
        self.assertIn("(6)", text)

    def test_prompt_parts_single_plan(self):
        home, t = tempfile.mkdtemp(), make_task()
        t["plan"] = plan.save(home, t, plan.parse(single(3)), 2)
        p, own = plan.prompt_parts(home, t, tasks.step(t, 3))
        self.assertTrue(p.startswith("The plan (follow it, do not change it):\n# Plan: calc"))
        self.assertIn("Plan gap:", p)
        self.assertTrue(own.startswith("Your part of the plan:\n### Step 3: code"))
        p, own = plan.prompt_parts(home, t, tasks.step(t, 5))  # verify
        self.assertIn("plan drift:", p)
        self.assertEqual(own, "")
        self.assertEqual(plan.prompt_parts(home, t, tasks.step(t, 1)), ("", ""))

    def test_prompt_parts_split_plan(self):
        home, t = tempfile.mkdtemp(), make_task()
        t["plan"] = plan.save(home, t, plan.parse(split()), 2)
        plan.rebuild(t, 2, t["plan"]["parts"], 5.0)
        p, own = plan.prompt_parts(home, t, tasks.step(t, 4))
        self.assertTrue(own.startswith("Your part of the plan:\n# Part 2: Report module"))
        self.assertNotIn("Part 1", own)
        p, own = plan.prompt_parts(home, t, tasks.step(t, 7))  # verify: every part
        self.assertIn("# Part 1", own)
        self.assertIn("# Part 2", own)

    def test_design_input_is_every_earlier_note_whole(self):
        home, t = tempfile.mkdtemp(), make_task()
        s = tasks.step(t, 1)
        s.update(model="haiku", effort="low", session="abc")
        tasks.write_note(home, t, s, "## Findings\n" + "long " * 600)
        text = plan.design_input(home, t, 2)
        self.assertTrue(text.startswith("# Step 01: scout on haiku/low"))
        self.assertGreater(len(text.split()), 600)


if __name__ == "__main__":
    unittest.main()
```

## 1.5 `console/step_prompt.md`

After the `$retry` line and before "Handoff note of the previous step:" add a line `$plan` and a blank line; right
before "Rules for this step:" add a line `$part` and a blank line. Nothing else in the file changes. The design
prompt (`console/design_prompt.md`, in the tree) is the design step's `$special`; it names `$turns`, `$later`,
`$edit_steps`, `$redo`, `$max_kb`, `$max_parts`, `$room` and `$write_kinds`, all filled by `plan.design_text`.
