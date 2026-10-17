"""The whole-task handoff (plan 44 navigation, Task 3): a code-built digest of what the task saved, one Haiku pass
over that digest, and the six handoff headings a follow-up task starts from. The pass reads the digest only, never
the live context or a transcript, and writes nothing: the service writes every file. A failed pass ends in a code
fallback built from the same saved files, so a handoff is never blocked on it."""
from . import compact, plan, redact, tasks

DIGEST_MAX = 12 * 1024  # characters; sections are cut from the bottom, the head and the step lines never
PROMPT_HEAD = "Summarize a whole task for a handoff."
MISSING = "No saved result. Do not assume this step completed."
EXCERPT = "[excerpt; full text in the cited evidence]"
EXCERPT_CUT = 500  # characters of one step's Findings the fallback keeps
_LIST = {"type": "array", "items": {"type": "string"}}
HANDOFF_SCHEMA = {
    "type": "object",
    "properties": {"goal": {"type": "string"}, "findings": _LIST, "files": _LIST, "troubleshooting": _LIST,
                   "questions": _LIST, "next": {"type": "string"}},
    "required": ["goal", "findings", "files", "troubleshooting", "questions", "next"],
    "additionalProperties": False,
}


def _identity(task: dict) -> str:
    return f'Task {task["id"]} "{task["title"]}" in {task["project"]} ({task["project_dir"]}).'


def _step_line(s: dict) -> str:
    route = f"{s['model']}/{s['effort']}" if s.get("model") else "not run"
    return (f"{s['n']:02d} {s['kind']} · {route} · {s['state']} · {s.get('verdict') or 'no verdict'} · "
            f"${tasks.step_cost(s):.2f} · {s.get('retries') or 0} retries")


def _texts(home, task: dict) -> dict:
    """step number -> the brief of the step, else its note: what the later steps and the open questions read."""
    out = {}
    for s in task["steps"]:
        text = tasks.read_brief(home, task, s["n"]) or tasks.read_note(home, task, s["n"])
        if text:
            out[s["n"]] = text
    return out


def _open(task: dict, texts: dict) -> list:
    return [q for q in tasks.open_questions(task, texts) if not q["closed"]]


def _failed(s: dict) -> list:
    return [f"attempt {k} failed: {a['why']}" for k, a in enumerate(tasks.attempts(s), 1) if a.get("why")]


def _body(home, task: dict, s: dict) -> str:
    """One step's saved result for the digest: its note, else its brief, else its final reply; the facts the service
    read (git and the last test) and the failed attempts after it."""
    text = (tasks.read_note(home, task, s["n"]) or tasks.read_brief(home, task, s["n"])
            or tasks.read_step_file(home, task, s, "notes.md"))
    lines = [f"Step {s['n']:02d} ({s['kind']}, {s['state']})", text.strip() or MISSING]
    facts = tasks.read_facts(home, task, s["n"])
    if facts.strip():
        lines += ["Facts the service read when the step ended:", facts.strip()]
    lines += [f"- {x}" for x in _failed(s)]
    return "\n".join(lines)


def _last_verdict(home, task: dict) -> str:
    verifies = [s for s in task["steps"] if s["kind"] == "verify" and s["state"] != "planned"]
    if not verifies:
        return ""
    s = verifies[-1]
    text = tasks.read_step_file(home, task, s, "verdict.md").strip()
    return f"Last verify (step {s['n']:02d}): {s.get('verdict') or 'no verdict'}\n" + (
        text or s.get("verdict_detail") or "No verdict file saved.")


def digest(home, task: dict, instructions: str) -> str:
    """The text the pass reads, from saved files only (never a transcript, a run stream, another task or config.json).
    Order: the head, one line per step, the open questions, the last verdict, the chain tail, each step's saved
    result newest first, then the plan. Over DIGEST_MAX the bottom is cut and the cut is said."""
    texts = _texts(home, task)
    head = "\n".join([
        _identity(task), f"Goal: {redact.clip(task.get('goal') or task['title'], 1200)}",
        f"State: {task['state']}" + (f" ({task['why']})" if task.get("why") else "")
        + f"; total cost ${sum(tasks.step_cost(s) for s in task['steps']):.2f}",
        f"Remaining work asked: {instructions.strip() or 'none given'}"])
    steps = "Steps\n" + "\n".join(_step_line(s) for s in task["steps"])
    questions = _open(task, texts)
    sections = [head, steps]
    if questions:
        sections.append("Open questions\n" + "\n".join(f"- {q['q']} (opened at step {q['opened']:02d})" for q in questions))
    verdict = _last_verdict(home, task)
    if verdict:
        sections.append(verdict)
    chain = tasks.read_chain(home, task, 10)
    if chain:
        sections.append("Chain, last 10\n" + "\n".join(
            f"step {c.get('step') or 0:02d} {c.get('from', '')} -> {c.get('to', '')}"
            + (f" ({redact.clip(c['why'], 120)})" if c.get("why") else "") for c in chain))
    sections += [_body(home, task, s) for s in sorted(task["steps"], key=lambda x: -x["n"])]
    index = plan.read(home, task)
    if index.strip():
        parts = [plan.read_part(home, task, p["n"]) for p in (task.get("plan") or {}).get("parts", [])]
        sections.append("Plan\n" + "\n\n".join(x.strip() for x in [index] + parts if x.strip()))
    kept, used, left = [], 0, 0
    for k, text in enumerate(sections):
        room = DIGEST_MAX - used - 80  # 80: the cut marker
        if len(text) + 2 <= room or k < 2:  # the head and the step lines are never cut
            kept.append(text)
            used += len(text) + 2
        else:
            left = len(sections) - k
            if room > 200:
                kept.append(text[:room].rstrip() + " [cut]")
            break
    if left:
        kept.append(f"[digest cut here: {left} later section(s) left out; treat their content as unavailable]")
    return redact.mask("\n\n".join(kept))[:DIGEST_MAX]


def build_prompt(task: dict, instructions: str, digest: str) -> str:
    """A fixed short prompt (the digest is the only variable text). The six headings are the schema's fields."""
    return (f"{PROMPT_HEAD} A follow-up task will start from your summary alone, so it must be accurate.\n"
            "Below is the saved digest of the task: its steps, their saved results and the facts code read. Use only the "
            "digest. Do not guess what it does not say.\n"
            "Fill the six handoff fields:\n"
            "- goal: what the task is for, in one or two sentences.\n"
            "- findings: what the steps found or did, each item citing its step number (for example `Step 02: ...`).\n"
            "- files: the files touched, one per item.\n"
            "- troubleshooting: dead ends and failed attempts, so the follow-up does not repeat them.\n"
            "- questions: open questions that still wait for an answer.\n"
            "- next: the concrete next work, starting from what the remaining-work instructions ask.\n"
            "Rules: summarize the saved evidence honestly. A step with no saved result is unavailable: say so, never "
            "call it a success. Never say verification passed unless the digest shows a PASS verdict. Keep it short.\n"
            f"Remaining work asked: {instructions.strip() or 'none given'}\n\n"
            f"DIGEST OF TASK {task['id']}\n{digest}\n")


def _bullets(items) -> str:
    lines = [f"- {' '.join(str(i).split())}" for i in items if str(i).strip()]
    return "\n".join(lines) or "None recorded."


def render(fields: dict, task: dict, instructions: str) -> str:
    """The six headings in order. Goal carries the task identity, the pass's goal and the remaining-work
    instructions (code, not the pass, puts them in); an empty field is `None recorded.`."""
    goal = [_identity(task)]
    said = " ".join(str(fields.get("goal") or "").split())
    if said:
        goal.append(said)
    if instructions.strip():
        goal.append("Remaining work asked: " + " ".join(instructions.split()))
    nxt = " ".join(str(fields.get("next") or "").split()) or "None recorded."
    return redact.mask("\n".join([
        "## Goal", "\n".join(goal),
        "## Findings", _bullets(fields.get("findings") or []),
        "## Files touched", _bullets(fields.get("files") or []),
        "## Troubleshooting", _bullets(fields.get("troubleshooting") or []),
        "## Open questions", _bullets(fields.get("questions") or []),
        "## Next", nxt]))


def check(block: str, max_words: int) -> str:
    """"" when all six headings stand in order and the block is within `max_words`; else the reason."""
    why = tasks.check_handoff(block)
    if why:
        return why
    return f"over {max_words} words" if compact.words(block) > max_words else ""


def fallback(home, task: dict, instructions: str) -> str:
    """Code only: the six headings from the same saved files, each step tagged, each excerpt marked."""
    texts = _texts(home, task)
    findings, files, trouble, seen = [], [], [], set()
    for s in task["steps"]:
        tag = f"Step {s['n']:02d} ({s['kind']}, {s['state']})"
        text = texts.get(s["n"]) or tasks.read_step_file(home, task, s, "notes.md")
        if text.strip():
            body = compact._sections(text).get("## Findings") or compact.note_body(text)
            where = tasks.note_file(task, s) if tasks.read_note(home, task, s["n"]) else tasks.step_file(s, "notes.md")
            findings.append(f"{tag}: {redact.clip(body, EXCERPT_CUT)} {EXCERPT} ({where})")
        else:
            findings.append(f"{tag}: {MISSING}")
        for item in compact._items(text, "## Files touched"):
            if item not in seen:
                seen.add(item)
                files.append(f"{item} (step {s['n']:02d})")
        trouble += [f"Step {s['n']:02d} {line}" for line in compact._items(text, "## Troubleshooting")]
        trouble += [f"Step {s['n']:02d} {line}" for line in _failed(s)]
    nxt = next((compact._sections(texts[n]).get("## Next", "") for n in sorted(texts, reverse=True)
                if compact._sections(texts[n]).get("## Next")), "")
    fields = {"goal": redact.clip(task.get("goal") or task["title"], 600), "findings": findings, "files": files,
              "troubleshooting": trouble, "questions": [f"{q['q']} (opened at step {q['opened']:02d})"
                                                         for q in _open(task, texts)],
              "next": nxt}
    return render(fields, task, instructions)


def run(cfg: dict, exe, home, task: dict, instructions: str) -> dict:
    """Blocking (about 5 to 20 s; the service runs it outside its task lock). Never raises: any failure, or an answer
    that fails `check`, ends in `fallback`. {"text", "cost", "words", "model", "fallback": "" | why}. `cost` is what
    the pass cost even when its answer was dropped."""
    cost, why = 0, ""
    try:
        if not cfg["handoff_on"]:
            why = "the handoff summary is off"
        elif not exe:
            why = "claude.exe not found"
        else:
            prompt = build_prompt(task, instructions, digest(home, task, instructions))
            asked = dict(cfg, brief_timeout_s=cfg["handoff_timeout_s"])
            fields, cost = compact._ask(asked, exe, task["project_dir"], prompt, HANDOFF_SCHEMA, None,
                                        model=cfg["handoff_model"])
            if not compact._fields_ok(fields):
                raise compact.BriefError("the pass returned no structured output")
            text = render(fields, task, instructions)
            why = check(text, cfg["handoff_max_words"])
            if not why:
                return {"text": text, "cost": cost, "words": compact.words(text), "model": cfg["handoff_model"],
                        "fallback": ""}
    except compact.BriefError as exc:
        why = str(exc)
    except Exception as exc:  # the handoff is never blocked on its pass
        why = f"{type(exc).__name__}: {exc}"
    try:
        text = fallback(home, task, instructions)
    except Exception:
        text = render({}, task, instructions)
    return {"text": text, "cost": cost, "words": compact.words(text), "model": "", "fallback": why}
