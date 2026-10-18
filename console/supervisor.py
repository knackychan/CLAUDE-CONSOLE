"""The event-driven task supervisor (plan 44): policy, audit, digest, the bounded pass, dispatch and replay.

Task 1 lands the policy only: the effective mode, the validated settings, and the saved counters a task carries.
Later tasks add the audit journal, the digest/decision contract and the one-call runner here."""
import hashlib
import json
import math
import os
import re
import uuid
from string import Template

from . import compact, kinds, plan, redact, tasks

MODES = ("off", "suggest", "auto")

# The supervisor's own pass is fixed to one Claude alias per role; a hand edit can never move it to opus/fable.
MODEL_ALIASES = {"supervisor_model": "haiku", "supervisor_stuck_model": "sonnet"}

_INT = {  # key -> (low, high) inclusive; a bool is never a count
    "supervisor_debounce_s": (0, 300),
    "supervisor_parallel": (1, 4),
    "supervisor_timeout_s": (10, 600),
    "supervisor_stall_s": (600, 7200),
    "supervisor_max_auto_steps": (0, 12),
    "supervisor_max_retries": (0, 1),
}
_USD = {  # key -> (low, high) inclusive; finite numbers only, zero disables that allowance
    "supervisor_work_usd": (0, 50),
    "supervisor_task_usd": (0, 10),
    "supervisor_day_usd": (0, 100),
}


def _project_mode(cfg: dict, project_dir: str) -> str:
    proj = cfg.get("supervisor_projects")
    if isinstance(proj, dict) and isinstance(project_dir, str):
        for path, mode in proj.items():
            if isinstance(mode, str) and mode in MODES and tasks.same_dir(path, project_dir):
                return mode
    return ""


def _whole(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _money(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def initial(cfg: dict, project_dir: str, now: float, mode=None) -> dict:
    """README 4.3 defaults for a new task's `supervisor` dict: global/project/task mode precedence, empty
    pending/proposed/retries, zero counters. No IO and no mutation of `cfg`."""
    picked = mode if mode in MODES else ""
    if not picked:
        picked = _project_mode(cfg, project_dir)
    if not picked:
        picked = cfg.get("supervisor_mode", "suggest")
    if picked not in MODES:
        picked = "off"
    return {"mode": picked, "wakes": 0, "auto_steps": 0, "retries": {}, "usd": 0.0, "work_usd": 0.0,
            "since_fred": now, "epoch": 0, "paused": False, "last_event": "", "proposed": [], "pending": None}


def policy(cfg: dict, task: dict, now: float) -> dict:
    """The effective, validated supervisor policy of one task. A legacy task without `supervisor` works lazily and
    is never mutated; an invalid saved mode/counter or a malformed hand-edited setting fails closed to off with a
    visible reason, never to auto and never to a larger allowance."""
    has_sup = isinstance(task.get("supervisor"), dict)
    sup = task.get("supervisor") if has_sup else {}
    errors = []

    if has_sup and "mode" in sup:
        mode = sup["mode"]
        if mode not in MODES:
            errors.append("supervisor mode must be off, suggest or auto")
            mode = "off"
    else:
        mode = _project_mode(cfg, task.get("project_dir")) or cfg.get("supervisor_mode", "suggest")
        if mode not in MODES:
            errors.append("supervisor_mode must be off, suggest or auto")
            mode = "off"

    settings = {}
    for key, (low, high) in _INT.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            errors.append(f"{key} must be a whole number between {low} and {high}")
            value = low  # the safe floor, never extra allowance
        settings[key] = value
    for key, (low, high) in _USD.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not low <= value <= high:
            errors.append(f"{key} must be a number between {low} and {high}")
            value = 0.0
        settings[key] = float(value)
    for key, want in MODEL_ALIASES.items():
        value = cfg.get(key)
        if value != want:
            errors.append(f"{key} must be {want}")
            value = want
        settings[key] = value

    if has_sup:
        auto_steps = _whole(sup.get("auto_steps"))
        if auto_steps is None:
            errors.append("supervisor auto_steps invalid")
            auto_steps = 0
        epoch = sup.get("epoch")
        if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
            errors.append("supervisor epoch invalid")
            epoch = 0
        usd = _money(sup.get("usd"))
        if usd is None:
            errors.append("supervisor usd invalid")
            usd = 0.0
        work_usd = _money(sup.get("work_usd"))
        if work_usd is None:
            errors.append("supervisor work_usd invalid")
            work_usd = 0.0
        since_fred = sup.get("since_fred")
        if isinstance(since_fred, bool) or not isinstance(since_fred, (int, float)):
            since_fred = now
        paused = sup.get("paused") is True
        retries, raw_retries = {}, sup.get("retries")
        if not isinstance(raw_retries, dict):
            raw_retries = {}
        for k, v in raw_retries.items():
            n = _whole(v)
            if not isinstance(k, int) or isinstance(k, bool) or k < 1 or n is None:
                errors.append("supervisor retries invalid")
                retries = {}
                break
            retries[k] = n
    else:
        auto_steps, epoch, usd, work_usd, paused, retries = 0, 0, 0.0, 0.0, False, {}
        since_fred = now

    return {"mode": "off" if errors else mode, "reason": "; ".join(errors), "settings": settings,
            "paused": paused, "epoch": epoch, "since_fred": since_fred,
            "auto_steps": auto_steps, "auto_steps_left": max(0, settings["supervisor_max_auto_steps"] - auto_steps),
            "retries": retries, "usd": usd, "work_usd": work_usd,
            "work_usd_left": max(0.0, settings["supervisor_work_usd"] - work_usd),
            "last_event": sup.get("last_event") if isinstance(sup.get("last_event"), str) else "",
            "proposed": sup.get("proposed") if isinstance(sup.get("proposed"), list) else [],
            "pending": sup.get("pending") if isinstance(sup.get("pending"), dict) else None}


# -- audit, event identity and restart recovery -----------------------------------------------------------

_EVENT_KEYS = ("ts", "step", "session", "from", "to", "why", "attempt")  # never cost or supervisor audit text


def event_id(line: dict) -> str:
    """SHA256 of the canonical qualifying original transition: timestamp, step, session, from, to and why only."""
    data = {k: line.get(k) for k in _EVENT_KEYS}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def request_id(task_id: str, wake: int) -> str:
    """UUID5(NAMESPACE_URL, `sup-<task>-<wake>`): the same logical wake always names the same request id."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sup-{task_id}-{wake}"))


def read_log(home, task_id: str) -> list:
    """The task's masked supervisor.jsonl as records in order; [] when absent. A bad line becomes a corruption
    marker so admission/recovery can see a visible hold instead of a free empty allowance."""
    try:
        path = tasks.folder(home, task_id) / "supervisor.jsonl"
    except ValueError:
        raise
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            out.append({"corrupt": True, "line": redact.clip(line, 200)})
            continue
        if not isinstance(rec, dict):
            out.append({"corrupt": True, "line": redact.clip(line, 200)})
            continue
        out.append(rec)
    return out


def append_log(home, task_id: str, record: dict) -> None:
    """Mask and append one lifecycle record, flush before returning; IO errors propagate so the Hub fails closed."""
    path = tasks.folder(home, task_id) / "supervisor.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = redact.mask(json.dumps(record, ensure_ascii=False, sort_keys=True))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text + "\n")
        fh.flush()


VISIBLE = ("suggest", "held", "escalate", "refused")  # pending statuses Fred sees; wait/no-decision leave none


def boundary(task: dict, chain: list):
    """The one eligibility classifier (live hooks and the restart scan, R1): {trigger, line, event} when the task
    stands at an eligible boundary now, with the original chain line that explains it; else None. Chat tasks and
    Fred's explicit Pause never qualify."""
    if not isinstance(task, dict) or task.get("chat") or not task.get("steps"):
        return None
    sup = task.get("supervisor") if isinstance(task.get("supervisor"), dict) else {}
    if sup.get("paused") is True:
        return None
    cs = tasks.current_step(task) if task.get("current") else None
    why, trigger, want = task.get("why", ""), "", ""
    if task.get("state") == "stuck":
        trigger, want = "stuck", "task:stuck"
    elif (task.get("progression") == "manual" and task.get("state") == "waiting" and task.get("owner") == "fred"
          and cs and cs["state"] == "done" and (why == "choose next step" or why.startswith("VERDICT: FAIL"))):
        trigger, want = ("choose_next" if why == "choose next step" else "fail"), "task:waiting"
    if not trigger:
        return None
    line = next((r for r in reversed(chain or []) if r.get("to") == want and (trigger == "stuck" or r.get("why") == why)),
                None)
    if line is None:
        return None
    return {"trigger": trigger, "line": line, "event": event_id(line)}


def fold_log(records: list) -> dict:
    """Fold lifecycle records by wake and phase: per-wake state, claimed events, pending, total priced cost (a
    result is counted once per wake, never once per lifecycle row), per-day cost/reservations and uncertainty."""
    wakes, days, uncertain = {}, {}, False
    for rec in records:
        if rec.get("corrupt"):
            uncertain = True
            continue
        wake = rec.get("wake")
        if not isinstance(wake, int) or isinstance(wake, bool):
            continue
        w = wakes.setdefault(wake, {"events": [], "status": "", "cost": 0.0, "uncertain": False,
                                    "decision": None, "record": None, "state": ""})
        if isinstance(rec.get("status"), str):
            w["state"] = rec["status"]  # the latest lifecycle status of this wake
        for e in rec.get("events") or []:
            if isinstance(e, str) and e not in w["events"]:
                w["events"].append(e)
        phase = rec.get("phase")
        if phase in ("claimed", "result", "dispatching", "outcome", "recovered"):
            w["status"] = phase
        if isinstance(rec.get("decision"), dict):
            w["decision"] = rec["decision"]
            w["record"] = rec
        if phase == "result":
            c = rec.get("cost")
            if isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) and c > 0:
                w["cost"] = round(float(c), 6)
                day = rec.get("day")
                if isinstance(day, str):
                    days.setdefault(day, {"cost": 0.0, "reserved": 0.0})["cost"] = round(float(c), 6)
            w["record"] = rec
        if phase == "claimed":
            day, reserved = rec.get("day"), rec.get("reserved")
            if isinstance(day, str) and isinstance(reserved, (int, float)) and not isinstance(reserved, bool):
                days.setdefault(day, {"cost": 0.0, "reserved": 0.0})["reserved"] = round(float(reserved), 6)
        if phase == "dispatching" or rec.get("outcome") == "uncertain":
            w["uncertain"] = True
            uncertain = True
    pending = None
    if wakes:
        top = max(wakes)
        w = wakes[top]
        if w["uncertain"] and w["status"] in ("dispatching", "recovered"):
            pending = {"wake": top, "events": w["events"], "decision": None, "status": "uncertain",
                       "error": "Service restarted during dispatch; it will not be replayed.", "by": "", "dispatch": None}
        elif w["decision"] is not None and w["record"] and w["state"] in VISIBLE:
            r = w["record"]
            pending = {"wake": top, "events": w["events"], "triggers": r.get("triggers") or [],
                       "decision": w["decision"], "revision": r.get("revision", ""), "epoch": r.get("epoch", 0),
                       "status": w["state"], "error": r.get("error", ""), "by": r.get("by", ""),
                       "dispatch": r.get("dispatch")}
    return {"wakes": wakes, "cost": round(sum(w["cost"] for w in wakes.values()), 6), "days": days,
            "uncertain": uncertain, "pending": pending}


# -- digest and decision contract (Task 3) --------------------------------------------------------------------

DIGEST_MAX = 12 * 1024  # UTF-8 bytes, omission markers included
ACCEPT_TAIL = 3000  # characters of a stuck attempt's notes.<k>.md
CHAIN_TAIL = 10
REASON_MAX, FOR_FRED_MAX, TEXT_MAX = 1000, 400, 400
NOTE_MAX = 2000  # server.NOTE_MAX's Retry-note contract; kept here so this module never imports server
DECISIONS = ("add_next_step", "confirm", "keep", "retry", "stepdone", "stop", "finish", "answer",
             "escalate_to_fred", "wait")
CONFIDENCE = ("low", "medium", "high")
RETRY_MODELS = ("", "haiku", "sonnet", "opus")
_OPTIONAL = {"kind": str, "instructions": str, "model": str, "source_step": int, "note": str, "text": str}
_FIELDS = {"add_next_step": ("kind", "instructions", "model", "source_step"), "retry": ("note", "model"),
           "answer": ("text",)}  # every other decision carries the four required fields only
_LEVER = {"confirm": "confirm", "keep": "keep", "retry": "retry", "stepdone": "stepdone", "stop": "stop",
          "finish": "done"}
_CONFIRMABLE = re.compile(r"plan ready: confirm|plan \d+(\.\d+)? KB, over \d+(\.\d+)?|replanned:.*", re.S)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["decision", "reason", "confidence", "for_fred"],
    "properties": {
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "reason": {"type": "string", "minLength": 1, "maxLength": REASON_MAX},
        "confidence": {"type": "string", "enum": list(CONFIDENCE)},
        "for_fred": {"type": "string", "maxLength": FOR_FRED_MAX},
        "kind": {"type": "string", "enum": list(tasks.NEXT_KINDS)},
        "instructions": {"type": "string", "minLength": 1, "maxLength": tasks.STEP_GOAL_MAX},
        "model": {"type": "string"},
        "source_step": {"type": "integer", "minimum": 1},
        "note": {"type": "string", "maxLength": NOTE_MAX},
        "text": {"type": "string", "maxLength": TEXT_MAX},
    },
}


class DigestError(Exception):
    """The mandatory digest head cannot fit DIGEST_MAX, or required evidence cannot be read: launch no model."""


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _task_file(home, task: dict, rel: str):
    """A saved file of this task by its relative name; None when absent. Never a path outside the task folder."""
    if not isinstance(rel, str) or not rel or ".." in rel.replace("\\", "/").split("/"):
        return None
    try:
        return (tasks.folder(home, task["id"]) / rel).read_text(encoding="utf-8")
    except OSError:
        return None


def _body(text: str) -> str:
    """A note file without its `# Step NN:` head line."""
    return text.split("\n\n", 1)[1] if text.startswith("# Step ") and "\n\n" in text else text


def _plan_view(home, task: dict) -> str:
    meta = task.get("plan") if isinstance(task.get("plan"), dict) else None
    if not meta:
        return ""
    text = _task_file(home, task, plan.index_file(task))
    if text is None:
        return f"Plan: unavailable ({plan.index_file(task)} missing)"
    keep, inside, out = ("## Goal", "## Decisions", "## Acceptance"), False, []
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() in keep
        if inside or line.startswith("### Step "):
            out.append(line)
    states = {s["n"]: s["state"] for s in task["steps"]}
    for p in meta.get("parts") or []:
        out.append(f"- part {p.get('n')}: {p.get('title', '')} (step {p.get('step') or '-'}: "
                   f"{states.get(p.get('step'), 'not started')})")
    return "Plan (plan.md index):\n" + "\n".join(out).strip()


def digest(home, task: dict, context: dict) -> str:
    """The bounded model input of one wake, built from this task's saved files and the gate/policy numbers the Hub
    captured under tlock (`context`): triggers, policy, levers, sources, owned, budget, reject_note, stuck. No
    transcript, run stream, git or network. Blocks are added whole in priority order; a block that cannot fit is
    named by file and size. Raises DigestError when the mandatory head, step table and Allowed now cannot fit."""
    pol = context.get("policy") or {}
    budget = context.get("budget") or {}
    cs = tasks.current_step(task) if task.get("current") else None
    total = round(sum(tasks.step_cost(s) for s in task["steps"]), 4)
    head = [f"# Task {task['id']}: {task.get('title', '')}", f"Project: {task.get('project', '')}",
            "Goal: " + (tasks.prompt_goal(task, cs) if cs else str(task.get("goal", ""))[:tasks.PROMPT_GOAL_MAX]),
            f"Progression: {task.get('progression') or 'automatic'}",
            f"State: {task['state']} / owner {task['owner']} / why: {task['why']}",
            "Triggers: " + ", ".join(context.get("triggers") or []),
            f"Created: {task.get('created')}; work cost ${total}; supervisor spend ${pol.get('usd', 0.0)}"]
    if context.get("reject_note"):
        head.append("Fred rejected the last suggestion: " + redact.clip(str(context["reject_note"]), NOTE_MAX))
    table = ["Steps (n kind model/effort state verdict cost retries source):"]
    for s in task["steps"]:
        table.append(f"{s['n']:02d} {s['kind']} {s.get('model') or '-'}/{s.get('effort') or '-'} {s['state']} "
                     f"{s.get('verdict') or '-'} ${tasks.step_cost(s)} {s.get('retries', 0)} "
                     f"{s.get('source_step') or '-'} " + redact.clip(str(s.get("goal", "")), 80))
    levers = context.get("levers") or {}
    allowed = [k for k, v in levers.items() if v == "" and k not in ("route", "next_route", "cwd", "add_next")]
    sources = [n for n, why in (context.get("sources") or {}).items() if why == ""]
    gates = ["Allowed now:", "- levers: " + (", ".join(allowed) or "none")]
    if levers.get("add_next") == "" and sources:
        gates.append("- add_next_step from " + ", ".join(sources) + " (kinds " + ", ".join(tasks.NEXT_KINDS) +
                     ", model auto)")
    gates.append(f"- mode {pol.get('mode', 'off')}; auto steps left {pol.get('auto_steps_left', 0)}; retries left "
                 f"{context.get('retries_left', 0)}; work USD left {pol.get('work_usd_left', 0.0)}; "
                 f"own USD left task {budget.get('task_left', 0.0)} day {budget.get('day_left', 0.0)}")
    proposed = [p.get("kind") for p in pol.get("proposed") or [] if isinstance(p, dict) and p.get("kind")]
    if proposed:
        gates.append("- Prep proposed kinds: " + ", ".join(proposed))
    mandatory = ["\n".join(head), "\n".join(table), "\n".join(gates)]
    used = sum(_size(b) + 2 for b in mandatory)
    if used > DIGEST_MAX:
        raise DigestError(f"digest head is {used} bytes, over {DIGEST_MAX}")

    blocks = []  # (title, relative file or "", text or None when missing), priority order
    good = tasks.step(task, task["last_good"]) if task.get("last_good") else None
    if good:
        rel = tasks.note_file(task, good)
        text = _task_file(home, task, rel)
        if text is None:
            rel = tasks.brief_file(task, good)
            text = _task_file(home, task, rel)
            blocks.append(("Last good brief", rel, text))
        else:
            blocks.append(("Last good handoff", rel, _body(text)))
        blocks.append(("Its facts", tasks.facts_file(task, good), _task_file(home, task, tasks.facts_file(task, good))))
    verifies = [s for s in task["steps"] if s["kind"] == "verify" and s["state"] in ("done", "failed")]
    if verifies and ((cs and cs["kind"] == "verify") or "stuck" in (context.get("triggers") or [])):
        rel = tasks.step_file(verifies[-1], "verdict.md")
        blocks.append(("Last verify verdict", rel, _task_file(home, task, rel)))
    view = _plan_view(home, task)
    if view:
        blocks.append(("", "", view))
    briefs = {s["n"]: _task_file(home, task, tasks.brief_file(task, s)) or "" for s in task["steps"]}
    qs = [q["q"] for q in tasks.open_questions(task, briefs) if not q["closed"]]
    if qs:
        blocks.append(("Open questions", "", "\n".join(f"- {q}" for q in qs)))
    chain = tasks.read_chain(home, task, CHAIN_TAIL)
    if chain:
        blocks.append(("Chain tail", "chain.jsonl", "\n".join(
            json.dumps({k: r.get(k) for k in ("ts", "step", "from", "to", "why")}, ensure_ascii=False) for r in chain)))
    stuck = context.get("stuck") if isinstance(context.get("stuck"), dict) else None
    if stuck and cs:
        k = stuck.get("attempt")
        rel = tasks.step_file(cs, f"notes.{k}.md") if isinstance(k, int) and not isinstance(k, bool) else ""
        tail = _task_file(home, task, rel) if rel else None
        text = "Reason: " + redact.clip(str(stuck.get("reason", "")), 400)
        if tail:
            text += f"\nTail of {rel}:\n" + tail[-ACCEPT_TAIL:]
        blocks.append(("Stuck attempt", "", text))

    chosen = {}
    for i, (title, rel, text) in enumerate(blocks):
        if text is None:
            out = f"{title}: unavailable ({rel} missing)"
        else:
            out = (f"{title} ({rel}):\n" if title and rel else f"{title}:\n" if title else "") + text.strip()
        if used + _size(out) + 2 > DIGEST_MAX:
            out = f"{title or 'Plan'}: omitted ({rel or 'evidence'}, {_size(text or '')} bytes)"
            if used + _size(out) + 2 > DIGEST_MAX:
                continue
        chosen[i] = out
        used += _size(out) + 2
    parts = mandatory[:2] + [chosen[i] for i in sorted(chosen)] + mandatory[2:]
    return "\n\n".join(parts) + "\n"


def revision(home, task: dict) -> str:
    """Semantic hash of what a decision was made over: goal, project, progression, state/why/owner, explicit pause
    and epoch, step identity/state/session/attempts/lineage, saved notes/briefs/facts/verdicts and the plan. Cost,
    timestamps, own-spend counters, the audit and the chain are left out; kind text is left out too (R3)."""
    sup = task.get("supervisor") if isinstance(task.get("supervisor"), dict) else {}
    steps = []
    for s in task["steps"]:
        files = {name: _task_file(home, task, rel) for name, rel in (
            ("note", tasks.note_file(task, s)), ("brief", tasks.brief_file(task, s)),
            ("facts", tasks.facts_file(task, s)), ("verdict", tasks.step_file(s, "verdict.md")))}
        steps.append({"n": s["n"], "kind": s["kind"], "goal": s.get("goal"), "state": s["state"],
                      "session": s.get("session"), "attempts": [a.get("session") for a in tasks.attempts(s)],
                      "source": s.get("source_step"), "verdict": s.get("verdict"),
                      "detail": s.get("verdict_detail"), "files": files})
    meta = task.get("plan") if isinstance(task.get("plan"), dict) else None
    data = {"goal": task.get("goal"), "project": task.get("project_dir"), "progression": task.get("progression"),
            "state": task["state"], "why": task["why"], "owner": task["owner"], "current": task.get("current"),
            "paused": sup.get("paused") is True, "epoch": sup.get("epoch"), "steps": steps,
            "plan": {"meta": {k: meta.get(k) for k in ("from", "dir", "parts")} if meta else None,
                     "text": _task_file(home, task, plan.index_file(task)) if meta else None}}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _text(value, limit: int, blank_ok: bool = False) -> bool:
    return isinstance(value, str) and len(value) <= limit and (blank_ok or bool(value.strip()))


def shape(decision) -> str:
    """"" when `decision` has the schema's shape (fields, types, enums, sizes, per-decision fields), else why. The
    runner rejects a bad shape; check() adds the live gates."""
    if not isinstance(decision, dict):
        return "decision is not an object"
    for key in decision:
        if key not in SCHEMA["properties"]:
            return f"unknown field {key}"
    for key in SCHEMA["required"]:
        if not isinstance(decision.get(key), str):
            return f"{key} is missing or not text"
    kind = decision["decision"]
    if kind not in DECISIONS:
        return "unknown decision"
    if not _text(decision["reason"], REASON_MAX):
        return "reason must be 1 to 1000 characters"
    if decision["confidence"] not in CONFIDENCE:
        return "confidence must be low, medium or high"
    if not _text(decision["for_fred"], FOR_FRED_MAX, blank_ok=True):
        return "for_fred is over 400 characters"
    for key, typ in _OPTIONAL.items():
        if key in decision:
            value = decision[key]
            if not isinstance(value, typ) or isinstance(value, bool):
                return f"{key} has the wrong type"
            if key not in _FIELDS.get(kind, ()):
                return f"{key} is not a field of {kind}"
    if "text" in decision and len(decision["text"]) > TEXT_MAX:
        return "text is over 400 characters"
    return ""


def check(decision, task: dict, levers: dict, sources: dict, policy: dict) -> tuple:
    """(ok, why) for one model decision against the live gates: shape first, then the action's own rule. Pure: no
    files, no mutation. `policy` carries triggers, owned source steps and retries_left; it can only narrow what the
    supplied levers/sources allow, never override a refusal. Confidence grants nothing."""
    why = shape(decision)
    if why:
        return False, why
    kind = decision["decision"]
    levers, sources, policy = levers or {}, sources or {}, policy or {}
    triggers = policy.get("triggers") or []
    if kind == "answer":
        return False, "questions are Fred's"
    if kind == "wait":
        return True, ""
    if kind == "escalate_to_fred":
        return (True, "") if _text(decision["for_fred"], FOR_FRED_MAX) else (False, "escalate_to_fred needs for_fred")
    if kind == "add_next_step":
        if decision.get("kind") not in tasks.NEXT_KINDS:
            return False, "kind must be one of " + ", ".join(tasks.NEXT_KINDS)
        if not _text(decision.get("instructions"), tasks.STEP_GOAL_MAX):
            return False, f"instructions must be 1 to {tasks.STEP_GOAL_MAX} characters"
        if decision.get("model") != "auto":
            return False, "a supervisor step runs on model auto"
        n = decision.get("source_step", task.get("current"))
        src = next((s for s in task["steps"] if s["n"] == n), None) if isinstance(n, int) else None
        if src is None:
            return False, "unknown source step"
        if src["state"] != "done" or not src.get("session") or n not in (policy.get("owned") or []):
            return False, "the source must be a done step this service ran"
        if levers.get("add_next") != "":
            return False, levers.get("add_next") or "add next step is off"
        why = sources.get(f"{n:02d}")
        if why != "":
            return False, why or "not a source step"
        return True, ""
    if kind == "retry":
        if not _text(decision.get("note"), NOTE_MAX):
            return False, "retry needs a note of 1 to 2000 characters"
        if decision.get("model", "") not in RETRY_MODELS:
            return False, "retry model must be empty, haiku, sonnet or opus"
        if not isinstance(policy.get("retries_left"), int) or policy["retries_left"] <= 0:
            return False, "no supervisor retry left for this step"
    if kind == "stop" and "stalled" not in triggers:
        return False, "stop is only for a stalled step"
    if kind == "confirm":
        why = str(task.get("why", ""))
        if why == "confirm Fable" or tasks.held(task) or not _CONFIRMABLE.fullmatch(why):
            return False, "only Fred confirms this"
    lever = levers.get(_LEVER[kind])
    if lever != "":
        return False, lever or f"{kind} is off"
    return True, ""


# -- the one bounded pass (Task 4) -------------------------------------------------------------------------

SCHEMA_REMINDER = ("Answer with one JSON object that matches the given schema: decision, reason, confidence and "
                   "for_fred, plus only the fields that decision takes. The digest follows.")


def build_prompt(raw: str, task: dict, digest_text: str, you: str = "the user") -> str:
    """The pass's stdin: the supervisor kind body ($you/$You filled), the schema reminder, then the digest last
    and untouched (its dollar signs are evidence, never template slots). Built once per claim; the same string is
    hashed and run."""
    you = you or "the user"
    body = Template(kinds.body_of(raw)).safe_substitute(you=you, You=you[:1].upper() + you[1:])
    return f"{body}\n\n{SCHEMA_REMINDER}\n\n{digest_text}"


def prompt_hash(prompt: str) -> str:
    """R3: SHA256 of the exact UTF-8 prompt sent on stdin; no normalization, no file reads."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def pass_model(settings: dict, triggers) -> str:
    """haiku normally; the stuck model (sonnet) on a stuck or stalled wake only (D4 a). Never opus or fable."""
    stuck = any(t in ("stuck", "stalled") for t in triggers or ())
    return settings["supervisor_stuck_model"] if stuck else settings["supervisor_model"]


def run(cfg: dict, exe: list, task: dict, prompt: str, model: str, max_cost: float) -> dict:
    """Blocking; no writes, no mutation. One tool-free structured `claude -p` in the task's project folder with the
    supervisor's timeout, `max_cost` as the CLI budget, safe mode and every MCP tool denied. Returns {decision:
    dict|None, cost: number|None, model, turns, error}; every failure is no decision and no retry, and a paid
    failure keeps its reported cost (None when unknown, never a free zero)."""
    info = {"cost": None, "turns": 0}
    out = {"decision": None, "cost": None, "model": model, "turns": 0, "error": ""}
    if not exe:
        out.update(cost=0.0, error="claude.exe not found")
        return out
    asked = dict(cfg, brief_timeout_s=cfg["supervisor_timeout_s"])
    try:
        fields, _ = compact._ask(asked, exe, task["project_dir"], prompt, SCHEMA, info, model=model,
                                 max_cost=max_cost, safe_mode=True)
    except compact.BriefError as exc:
        out.update(cost=info.get("cost"), turns=info.get("turns", 0), error=str(exc).replace("the brief", "the pass"))
        return out
    except Exception as exc:  # an unexpected runner failure is still no decision
        out.update(cost=info.get("cost"), error=f"the pass failed: {redact.clip(str(exc), 200)}")
        return out
    out.update(cost=info.get("cost"), turns=info.get("turns", 0))
    why = shape(fields)
    if why:
        out["error"] = "no decision (" + why + ")"
        return out
    out["decision"] = fields
    return out
