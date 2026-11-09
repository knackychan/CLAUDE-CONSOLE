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
