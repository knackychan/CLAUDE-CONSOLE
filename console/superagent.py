"""The super agent (plan 58; design/brainstorm/2026-11-08-super-agent.md, slice 1): one bounded, tool-free pass at a
time over every item that needs the user and every live task. Code rebuilds the digest for each pass; the pass reads it
with a notes file it rewrites and the user's standing orders, and answers with a rank, a batch or a later for each item
plus one recommendation line. It never acts in this slice. This module is pure functions and the files under
<home>/super/; the Hub owns the wakes, the pass thread and the spend (server.py). Required state/policy reads
raise on invalid storage so the Hub can block paid work; optional notes may be absent."""
import hashlib
import json
import math
import os
import re
import statistics
import time
from pathlib import Path
from string import Template

from . import compact, kinds, paths, redact, tasks
from .state import NEEDS_YOU

FOLDER = "super"
STATE_FILE, NOTES_FILE, ORDERS_FILE, LOG_FILE, PROMPT_FILE = (
    "state.json", "notes.md", "orders.md", "super.jsonl", "last-prompt.md")
OLD_LOG = "super.1.jsonl"
LOG_MAX = 5 * 1024 * 1024  # bytes: super.jsonl then moves to super.1.jsonl, replacing the older copy (D8)
MODEL_ALIASES = {"super_model": "haiku", "super_judge_model": "sonnet"}  # fixed, like supervisor.MODEL_ALIASES
_INT = {"super_debounce_s": (0, 300), "super_sweep_s": (300, 3600), "super_timeout_s": (10, 600),
        "super_notes_lines": (0, 200)}  # key -> (low, high) inclusive; a bool is never a count
_USD = {"super_pass_usd": (0, 1), "super_day_usd": (0, 20)}  # finite numbers; 0 turns the passes off
MAX_WAIT_S = 120  # a wake that new events keep pushing still runs this long after its first event
LATER_MAX_S = 86400  # a later's until is at most a day ahead
LINE_MAX = 200  # characters of one notes, orders, digest or task line
NOTES_MAX = 4000  # characters of notes.md after its line cut
ORDERS_MAX = 4000  # characters of the orders a pass reads
ORDERS_SEED = ("# Standing orders for the super agent (plan 58). One order per line, in your own words.\n"
               "# Lines that start with # are not sent to the super agent.\n")


def settings(cfg: dict) -> tuple:
    """(settings, errors): the super agent's numbers from config, checked like supervisor.policy (README 3.2). A bool,
    a wrong type or an out-of-range value takes the floor (0.0 for money) and adds its error; a model other than its
    alias is forced to the alias and adds its error. Any error keeps every pass from starting."""
    out, errors = {}, []
    for key, (low, high) in _INT.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            errors.append(f"{key} must be a whole number between {low} and {high}")
            value = low
        out[key] = value
    for key, (low, high) in _USD.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high \
                or not math.isfinite(value):
            errors.append(f"{key} must be a number between {low} and {high}")
            value = 0.0
        out[key] = float(value)
    for key, want in MODEL_ALIASES.items():
        if cfg.get(key) != want:
            errors.append(f"{key} must be {want}")
        out[key] = want
    return out, errors


def blocked(limits: dict, errors: list, state: dict, exe: bool) -> str:
    """Why no pass may start now ("" when one may), the first that holds: a settings error, off (a zero limit),
    Pause, no claude.exe (README 3.7)."""
    if errors:
        return "settings: " + errors[0]
    if limits["super_day_usd"] <= 0 or limits["super_pass_usd"] <= 0:
        return "off: super_day_usd or super_pass_usd is 0"
    if state.get("paused"):
        return "paused"
    if not exe:
        return "claude.exe not found"
    return ""


def status(limits: dict, errors: list, state: dict, spent: float, exe: bool) -> tuple:
    """(ranked, why) for the queue (README 3.8): blocked(), then over the day limit (`spent` is today's settled plus
    held spend), then no pass yet, then the last pass's error; (True, "") when the last ok pass's annotations hold."""
    why = blocked(limits, errors, state, exe)
    if why:
        return False, why
    if spent >= limits["super_day_usd"]:
        return False, f"over the day limit (${limits['super_day_usd']:.2f})"
    last = state.get("last")
    if not isinstance(last, dict):
        return False, "no pass yet"
    if not last.get("ok"):
        return False, str(last.get("error") or "the last pass failed")
    return True, ""


# -- the super/ files (Task 1) ------------------------------------------------------------------------------

def folder(home) -> Path:
    return Path(home) / FOLDER


def ensure(home) -> bool:
    """The service start: write orders.md with its two comment lines when it is missing; an existing file is never
    touched. True when written; a write error is skipped (a pass then reads no orders)."""
    path = folder(home) / ORDERS_FILE
    if path.exists():
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        paths.write_text_atomic(path, ORDERS_SEED)
    except OSError:
        return False
    return True


def blank_state() -> dict:
    """state.json's shape (README 3.5)."""
    return {"v": 1, "n": 0, "paused": False, "seen": {}, "reviewed": {}, "ann": {}, "last": None,
            "digest": [], "claimed": None}


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _annotation(a):
    if not isinstance(a, dict) or a.get("do") not in ("forward", "batch", "later"):
        return False
    if not _whole(a.get("rank")) or a["rank"] < 1:
        return False
    for name, limit in (("say", 200), ("why", 200), ("batch", 80), ("basis", 64)):
        if not isinstance(a.get(name), str) or len(a[name]) > limit:
            return False
    if not re.fullmatch(r"[0-9a-f]{16,64}", a["basis"]):
        return False
    until = a.get("until")
    if a["do"] == "later":
        return bool(a["why"].strip()) and _num(until) and until > 0
    return until is None


def load_state(home) -> dict:
    """Only an absent file is a fresh install; corrupt state must never lose Pause."""
    try:
        state = json.loads((folder(home) / STATE_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return blank_state()
    except (OSError, ValueError) as exc:
        raise ValueError("super state unreadable: " + redact.mask(str(exc))) from exc
    try:
        if not isinstance(state, dict) or type(state.get("v")) is not int or state["v"] != 1:
            raise ValueError("unsupported state version")
        if not _whole(state.get("n")) or type(state.get("paused")) is not bool:
            raise ValueError("invalid counter or Pause")
        for field in ("seen", "reviewed", "ann"):
            if not isinstance(state.get(field), dict) or any(not isinstance(k, str) for k in state[field]):
                raise ValueError("invalid " + field)
        if any(not _num(v) or v < 0 for v in state["seen"].values()):
            raise ValueError("invalid seen time")
        if any(not _whole(v) for v in state["reviewed"].values()):
            raise ValueError("invalid reviewed counter")
        if any(not _annotation(v) for v in state["ann"].values()):
            raise ValueError("invalid annotation")
        if not isinstance(state.get("digest"), list) or len(state["digest"]) > 3 or any(
                not isinstance(v, str) or len(v) > LINE_MAX for v in state["digest"]):
            raise ValueError("invalid digest")
        last = state.get("last")
        if last is not None:
            if not isinstance(last, dict) or type(last.get("ok")) is not bool:
                raise ValueError("invalid last result")
            for field in ("n", "turns", "ms", "items"):
                if not _whole(last.get(field)):
                    raise ValueError("invalid last " + field)
            if not _num(last.get("at")) or last["at"] < 0:
                raise ValueError("invalid last time")
            if last.get("cost") is not None and (not _num(last["cost"]) or last["cost"] < 0):
                raise ValueError("invalid last cost")
            for field in ("error", "model", "trigger", "fingerprint"):
                if not isinstance(last.get(field), str):
                    raise ValueError("invalid last " + field)
        claim = state.get("claimed")
        if claim is not None:
            if not isinstance(claim, dict) or not _whole(claim.get("n")) or not _num(claim.get("at")) or claim["at"] < 0:
                raise ValueError("invalid claim")
            for field in ("pid", "model", "policy_hash", "trigger"):
                if not isinstance(claim.get(field), str) or not claim[field]:
                    raise ValueError("invalid claim " + field)
            for field in ("handles", "bases"):
                if not isinstance(claim.get(field), dict) or any(
                        not isinstance(k, str) or not isinstance(v, str) for k, v in claim[field].items()):
                    raise ValueError("invalid claim " + field)
        # Unknown extension keys are preserved; supported versions still validate every owned field.
        state["ann"] = _masked(state["ann"])
        state["digest"] = _masked(state["digest"])
        return state
    except (ValueError, TypeError) as exc:
        raise ValueError("super state invalid: " + redact.mask(str(exc))) from exc


def save_state(home, state: dict) -> None:
    """Atomic replacement (plan 54). Required callers propagate failure to admission/action status."""
    path = folder(home) / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.write_text_atomic(path, json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n")


def read_notes(home) -> str:
    """notes.md as the last pass left it; "" when missing or unreadable."""
    try:
        return (folder(home) / NOTES_FILE).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def cut_notes(text, lines: int) -> str:
    """A pass's notes as notes.md keeps them: masked, blank lines dropped, at most `lines` lines of at most LINE_MAX
    characters, at most NOTES_MAX characters in all, ending with a newline; "" for no notes or `lines` 0."""
    if lines <= 0 or not isinstance(text, str):
        return ""
    kept = [line.rstrip()[:LINE_MAX] for line in redact.mask(text).replace("\r\n", "\n").split("\n") if line.strip()]
    out = "\n".join(kept[:lines])[:NOTES_MAX].rstrip()
    return out + "\n" if out else ""


def save_notes(home, text: str) -> None:
    path = folder(home) / NOTES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.write_text_atomic(path, text)


def read_orders(home) -> str:
    try:
        text = (folder(home) / ORDERS_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeError) as exc:
        raise ValueError("super orders unreadable: " + redact.mask(str(exc))) from exc
    lines = [line.strip() for line in redact.mask(text).splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if any(len(line) > LINE_MAX for line in lines) or len("\n".join(lines)) > ORDERS_MAX:
        raise ValueError("super orders exceed supported limits")
    return "\n".join(lines)


def save_prompt(home, prompt: str) -> None:
    """last-prompt.md: the exact stdin of the last pass, for the live check (its texts are masked already)."""
    path = folder(home) / PROMPT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.write_text_atomic(path, prompt)


def _masked(value):
    """Every string of a JSON-ready value masked, keys included. Masking the dumped line instead can swallow a
    closing quote (a value that ends in `token=abc`) and break the line (README section 2); this keeps every line
    valid JSON."""
    if isinstance(value, str):
        return redact.mask(value)
    if isinstance(value, dict):
        return {redact.mask(str(k)): _masked(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_masked(v) for v in value]
    return value


def append_log(home, record: dict) -> None:
    """One JSON line in super.jsonl, every string in it masked (`ts` first unless the record has one). At LOG_MAX
    bytes the file first moves to super.1.jsonl, replacing the older copy; a move that fails is tried again at the
    next line (D8). Raises OSError on the append: the Hub logs it."""
    path = folder(home) / LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.stat().st_size >= LOG_MAX:
            os.replace(path, path.with_name(OLD_LOG))
    except OSError:
        pass
    line = json.dumps(_masked({"ts": time.time(), **record}), ensure_ascii=False, default=str)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()


def read_log(home) -> list:
    out = []
    for name in (OLD_LOG, LOG_FILE):
        try:
            text = (folder(home) / name).read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        except (OSError, UnicodeError) as exc:
            raise ValueError("super audit unreadable: " + redact.mask(str(exc))) from exc
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("not an object")
            except ValueError as exc:
                raise ValueError(f"super audit corrupt: {name} line {n}") from exc
            out.append(record)
    return out


# -- items and the queue (Task 2) ---------------------------------------------------------------------------

def _event(values) -> str:
    """16 hex of canonical JSON SHA-256, stable until the decision evidence changes."""
    raw = json.dumps(values, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def always_reason(task: dict) -> str:
    """README 3.4: why an item of this task reaches the user whatever a pass says, the first that holds; "" when a
    pass may rank it, batch it or put it later."""
    why, state = str(task.get("why") or ""), task.get("state")
    sup = task.get("supervisor") if isinstance(task.get("supervisor"), dict) else {}
    pending = sup.get("pending") if isinstance(sup.get("pending"), dict) else {}
    decision = task.get("decision") if isinstance(task.get("decision"), dict) else {}
    cs = tasks.current_step(task) if task.get("current") else None
    if state == "waiting" and why == "confirm Fable":
        return "Fable confirm"
    if state == "stuck" and why.startswith("verify failed twice"):
        return "second verify FAIL"
    if why.startswith("supervisor work cap reached"):
        return "work cap"
    if pending.get("error") == "supervisor spend cap reached":
        return "spend cap"
    if tasks.held(task):
        return "pace hold"
    if cs and cs.get("limit"):
        return "usage limit"
    if pending.get("status") == "uncertain" or decision.get("taken") == "uncertain" or any(
            isinstance(m, dict) and m.get("status") == "uncertain" for m in task.get("messages") or []):
        return "uncertain dispatch"
    if state == "waiting" and why.startswith("asks: ") and not decision.get("taken") and not decision.get("default"):
        return "decision without a default"  # D10: a plain STOP question has no default either
    return ""


def task_kind(row: dict, task: dict) -> str:
    """The kind of a task's item, from its list row (server.task_row) and task.json, the first that holds:
    suggestion, decision (a question with options), question, hand_off, handed, failed_twice, stuck, hold (any other
    wait: a plan, Fable, a pace, a cap), chat (a chat task's turn), else the task state (README 3.3)."""
    state = task.get("state")
    if (row.get("supervisor") or {}).get("attention"):
        return "suggestion"
    if row.get("asks"):
        return "decision" if state == "waiting" and isinstance(task.get("decision"), dict) else "question"
    if row.get("hand_off"):
        return "hand_off"
    if state == "handed":
        return "handed"
    if state == "stuck":
        return "failed_twice" if str(task.get("why") or "").startswith("verify failed twice") else "stuck"
    if state == "waiting":
        return "hold"
    return "chat" if task.get("chat") else str(state or "")


def items(snap: dict, by_id: dict) -> list:
    """README 3.3, the needs set, from a Hub snapshot (pure): every task row in group needs whose task is in `by_id`
    (Hub.tasks, never changed), then every session row in group needs with neither task nor chat_task (a task's
    session counts as its task, as the snapshot's counts do). The key is "<type>:<id>:<event>"; the event changes
    when the state that raised the item changes, never with time, cost or `updated`."""
    out = []
    for row in snap.get("tasks") or []:
        task = by_id.get(row.get("id"))
        if row.get("group") != "needs" or not isinstance(task, dict):
            continue
        kind = task_kind(row, task)
        sup = task.get("supervisor") if isinstance(task.get("supervisor"), dict) else {}
        pending = sup.get("pending") if isinstance(sup.get("pending"), dict) else {}
        decision = task.get("decision") if isinstance(task.get("decision"), dict) else {}
        cs = tasks.current_step(task) if task.get("current") else None
        event = _event([kind, task.get("state"), task.get("why") or "", task.get("current") or 0,
                        len(tasks.attempts(cs)) if cs else 0, row.get("asks") or "", row.get("hand_off") or "",
                        [pending.get(k) for k in ("wake", "status", "decision", "error")], decision,
                        cs.get("limit") if cs else None, always_reason(task)])
        out.append({"key": f"task:{task['id']}:{event}", "type": "task", "id": task["id"], "kind": kind,
                    "always": always_reason(task), "subject_state": task.get("state"), "project": row.get("project") or "",
                    "project_dir": row.get("project_dir") or "", "title": row.get("title") or "",
                    "label": row.get("label") or task["id"]})
    for row in snap.get("sessions") or []:
        if row.get("group") != "needs" or row.get("task") or row.get("chat_task"):
            continue
        kind = (row["state"] if row.get("state") in NEEDS_YOU else "context" if row.get("ctx_tone") == "red"
                else "handed")
        event = _event([kind, row.get("state"), row.get("turn_ts"), row.get("handoff_by") or "",
                        row.get("stop_question") or ""])
        out.append({"key": f"session:{row['id']}:{event}", "type": "session", "id": row["id"], "kind": kind,
                    "always": "", "project": row.get("project") or "", "project_dir": row.get("project_dir") or "",
                    "title": row.get("title") or "", "label": str(row["id"])[:8]})
    return out


def sync(state: dict, live: list, now: float) -> tuple:
    """Bring state.json's item memory to the live set (README 3.6): a new key is seen `now`; a key that left is
    forgotten with its annotation, and so is an annotation whose key is no longer seen; a later annotation whose until
    has passed is marked back, once. Returns (new keys, back keys, changed). Mutates `state`."""
    keys = {i["key"] for i in live}
    seen, ann = state["seen"], state["ann"]
    new = [i["key"] for i in live if i["key"] not in seen]
    for key in new:
        seen[key] = float(now)
    gone = [k for k in seen if k not in keys]
    for key in gone:
        del seen[key]
    reviewed = state.setdefault("reviewed", {})
    reviewed_gone = [key for key in reviewed if key not in keys]
    for key in reviewed_gone:
        del reviewed[key]
    stale = [k for k in ann if k not in keys]
    for key in stale:
        del ann[key]
    back = []
    for key, a in ann.items():
        until = a.get("until")
        if a.get("do") == "later" and _num(until) and until <= now and not a.get("back"):
            a["back"] = True
            back.append(key)
    return new, back, bool(new or gone or stale or back or reviewed_gone)


def _when(ts) -> str:
    """A timestamp as the local YYYY-MM-DDTHH:MM a pass writes; "" for none."""
    return time.strftime("%Y-%m-%dT%H:%M", time.localtime(ts)) if _num(ts) else ""


def last_at(state: dict) -> float:
    """When the last pass was claimed; 0.0 for no pass, or for a hand-edited `last` whose time is not a number (the
    queue and the sweep read it, and neither may raise)."""
    last = state.get("last")
    at = last.get("at") if isinstance(last, dict) else None
    return float(at) if _num(at) else 0.0


def select_items(items_: list, state: dict) -> list:
    seen, reviewed = state.get("seen", {}), state.get("reviewed", {})
    return sorted(items_, key=lambda i: (reviewed.get(i["key"], 0), not bool(i.get("always")),
                                        seen.get(i["key"], 0), i["key"]))


def _must_forward(item):
    return bool(item.get("always") or item.get("incomplete") or
                item.get("level") == "auto" and item.get("deadline") is not None)


def compatible(group: list) -> bool:
    """Only identical, available answer contracts justify a presentation batch."""
    if len(group) < 2 or any(_must_forward(i) for i in group):
        return False
    first = group[0]
    contract = first.get("contract")
    return bool(contract and contract.get("action") and all(
        i.get("kind") == first.get("kind") and i.get("level") == first.get("level")
        and i.get("contract") == contract for i in group))


def queue(items_: list, state: dict, now: float, ranked: bool) -> dict:
    seen, annotations = state.get("seen", {}), state.get("ann", {})
    rows, later, batches = [], [], {}
    for item in items_:
        key = item["key"]
        a = annotations.get(key)
        a = a if ranked and _annotation(a) else {}
        row = dict(item, age_s=max(0, int(now - seen.get(key, now))),
                   new=bool(ranked and (key not in seen or seen[key] > last_at(state))),
                   do="forward", rank=a.get("rank"), say=redact.mask(a.get("say", "")),
                   why=redact.mask(a.get("why", "")), batch="", until="")
        if a and not _must_forward(item):
            until = a.get("until")
            if a["do"] == "later" and a["why"].strip() and _num(until) and now < until <= now + LATER_MAX_S:
                row.update(do="later", until=_when(until))
                later.append((until, row))
                continue
            if a["do"] == "batch" and isinstance(a.get("batch"), str) and a["batch"]:
                batches.setdefault(a["batch"], []).append(row)
        rows.append(row)
    for identity, group in batches.items():
        if compatible(group):
            for row in group:
                row.update(do="batch", batch=identity.split(":", 1)[-1])
    def order(row):
        age = (seen.get(row["key"], now), row["key"])
        if row.get("always"):
            return (0, 0, *age)
        if ranked and row["rank"] is not None:
            return (1, row["rank"], *age)
        return (3 if row["new"] else 2, 0, *age)
    rows.sort(key=order)
    cards, used = [], set()
    for row in rows:
        if row["key"] in used:
            continue
        identity = annotations.get(row["key"], {}).get("batch") if row["do"] == "batch" else None
        group = sorted(batches[identity], key=order) if identity else [row]
        used.update(i["key"] for i in group)
        cards.append({"batch": row["batch"], "rank": row["rank"], "items": group})
    return {"queue": cards, "later": [row for _, row in sorted(later, key=lambda pair: (pair[0], pair[1]["key"]))]}

