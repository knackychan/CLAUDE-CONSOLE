"""The event-driven task supervisor (plan 44): policy, audit, digest, the bounded pass, dispatch and replay.

Task 1 lands the policy only: the effective mode, the validated settings, and the saved counters a task carries.
Later tasks add the audit journal, the digest/decision contract and the one-call runner here."""
import hashlib
import json
import math
import os
import uuid

from . import redact, tasks

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

_EVENT_KEYS = ("ts", "step", "session", "from", "to", "why")  # never mutable cost or supervisor audit text


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
                                    "decision": None, "record": None})
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
        elif w["decision"] is not None and w["record"]:
            r = w["record"]
            pending = {"wake": top, "events": w["events"], "decision": w["decision"],
                       "status": r.get("status", "suggest"), "error": r.get("error", ""), "by": r.get("by", ""),
                       "dispatch": r.get("dispatch")}
    return {"wakes": wakes, "cost": round(sum(w["cost"] for w in wakes.values()), 6), "days": days,
            "uncertain": uncertain, "pending": pending}
