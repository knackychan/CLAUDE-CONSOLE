"""The plan the design step writes (brainstorm 8b, plan 24): the PLAN block and the SUBPLAN blocks of the step's final
message, parsed and checked here, saved by the service as tasks/<id>/plan.md and plan/NN-<slug>.md, read whole by every
later step. Pure functions on text and dicts; the file functions take the data home, as tasks.py's do. The plan is never
compacted and never cut: the only bound is plan_max_kb, and over it the task waits for Fred."""
import re
import shutil
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
_BAD = re.compile(r"\bTBD\b|\bTODO[:(]")  # a placeholder; the word TODO alone is the plan's own section name
_LABEL = re.compile(r"^(#{1,6}\s+|[-*]\s+)?\*{0,2}TODO\*{0,2}:?(?=\s|$)", re.M)  # TODO as a step label, not a placeholder


def _unfinished(text: str) -> bool:
    return bool(_BAD.search(_LABEL.sub("", str(text or ""))))
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
    if _unfinished(index) or any(_unfinished(p["text"]) for p in parts):
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


def drop_parts(home, task: dict, n: int) -> None:
    """Before a redo's plan is saved (plan 27): the earlier plan's plan/ folder goes, and the planned steps after
    design step `n` lose `part`, `hard` and their `Part k: ` goal head, so a single plan reaches them through its
    `### Step N` sections (a split rebuilds them anyway). Done steps keep what they ran with."""
    shutil.rmtree(tasks.folder(home, task["id"]) / PART_DIR, ignore_errors=True)
    for s in task["steps"]:
        if s["n"] > n and s["state"] != "done" and "part" in s:
            del s["part"]
            s.pop("hard", None)
            s["goal"] = re.sub(r"^Part \d+: ", "", s["goal"], count=1)


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
    again, masked like save. Returns the relative file name."""
    rel = FILE if not k else next(p["file"] for p in task["plan"]["parts"] if p["n"] == k)
    path = tasks.folder(home, task["id"]) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if k:
        title = next(p["title"] for p in task["plan"]["parts"] if p["n"] == k)
        text = f"# Part {k}: {title}\n\n" + part_body(text)
    path.write_text(redact.mask(str(text or "")), encoding="utf-8")
    return rel


def with_answer(index: str, answer: str, day: str = "") -> str:
    """The index with `- Fred, <date>: <answer>` as the last line of ## Decisions; the answer on one line, its
    whitespace collapsed (a multi-line answer adds no heading)."""
    day = day or date.today().isoformat()
    answer = " ".join(str(answer or "").split())
    lines = str(index or "").splitlines()
    out, on, placed = [], False, False
    for line in lines:
        if on and line.startswith("## ") and not placed:
            while out and not out[-1].strip():
                out.pop()
            out += [f"- Fred, {day}: {answer}", ""]
            placed = True
        if line.strip() == "## Decisions":
            on = True
        out.append(line)
    if on and not placed:
        while out and not out[-1].strip():
            out.pop()
        out.append(f"- Fred, {day}: {answer}")
    return "\n".join(out).rstrip() + "\n"


def add_answer(home, task: dict, answer: str, day: str = "") -> str:
    """Append Fred's answer to the Decisions of plan.md, masked by write; returns the line written."""
    text = redact.mask(with_answer(read(home, task), answer, day))
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
        max_kb=cfg["plan_max_kb"], max_parts=cfg["plan_max_parts"],
        room=max(tasks.room_after(task, step["n"], cfg["task_max_steps"]), 1),
        write_kinds=", ".join(WRITE_KINDS))


def design_input(home, task: dict, n: int) -> str:
    """What the design step reads instead of a brief: the raw handoff notes of every earlier step, whole (D1); on a
    redo (task["redo"]) also the notes of the done steps after n, which the redo keeps (plan 27)."""
    out = []
    for s in task["steps"]:
        if s["n"] == n or (s["n"] > n and not (task.get("redo") and s["state"] == "done")):
            continue
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
