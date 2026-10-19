"""The Models and tuning page's settings (plan 26): which config.json keys the page may change, their ranges, and
the check of one Save. Pure: no files, no threads, no HTTP; the service writes what `validate` keeps."""
import math
import os
import re

from . import claude_cli, fills, paths, tasks

# key -> (group, unit, min, max), in the Tuning tab's order. Units: a whole number for steps, s, turns, kb, parts,
# words, tokens; a number for usd and share (a share is a fraction: 0.1 = 10 points); bool; rung (a model); text.
TUNING = {
    "user_name": ("you", "text", 0, paths.NAME_MAX),  # plan 31: one line of text, "" allowed
    "task_max_steps": ("steps", "steps", 1, 12),
    "task_step_budget_usd": ("steps", "usd", 0.1, 50),
    "step_timeout_s": ("steps", "s", 60, 7200),
    "design_max_turns": ("steps", "turns", 1, 200),
    "read_max_turns": ("steps", "turns", 1, 100),
    "plan_max_kb": ("plan", "kb", 10, 1000),
    "plan_max_parts": ("plan", "parts", 2, 12),
    "plan_hold": ("plan", "bool", None, None),
    "replan_auto": ("plan", "bool", None, None),
    "brief_max_words": ("handoff", "words", 100, 2000),
    "brief_timeout_s": ("handoff", "s", 10, 600),
    "balance_margin": ("balancing", "share", 0, 0.5),
    "cache_bonus": ("balancing", "share", 0, 0.5),
    "budget_warn_at": ("balancing", "share", 0.1, 2),
    "daily_budget_usd": ("balancing", "usd", 0, 1000),
    "allowances": ("balancing", "usd", 0, 100000),
    "gauge_yellow_tokens": ("gauge", "tokens", 10000, 1000000),
    "gauge_red_tokens": ("gauge", "tokens", 10000, 1000000),
    "prep_model": ("passes", "rung", None, None),
    "brief_model": ("passes", "rung", None, None),
    "review_model": ("passes", "rung", None, None),
    "default_model": ("passes", "rung", None, None),
    "planner_model": ("passes", "rung", None, None),  # plan 47: the planner pass, Claude only (CLAUDE_ONLY)
    "planner_timeout_s": ("passes", "s", 10, 600),
    "planner_max_cost": ("passes", "usd", 0.05, 5),
    # plan 44: the supervisor's own numeric/rung settings (mode and map are enum/map, in KEYS but not TUNING)
    "supervisor_debounce_s": ("supervisor", "s", 0, 300),
    "supervisor_parallel": ("supervisor", "steps", 1, 4),
    "supervisor_timeout_s": ("supervisor", "s", 10, 600),
    "supervisor_stall_s": ("supervisor", "s", 600, 7200),
    "supervisor_max_auto_steps": ("supervisor", "steps", 0, 12),
    "supervisor_max_retries": ("supervisor", "steps", 0, 1),
    "supervisor_work_usd": ("supervisor", "usd", 0, 50),
    "supervisor_task_usd": ("supervisor", "usd", 0, 10),
    "supervisor_day_usd": ("supervisor", "usd", 0, 100),
    "supervisor_model": ("supervisor", "rung", None, None),
    "supervisor_stuck_model": ("supervisor", "rung", None, None),
}
KEYS = tuple(TUNING) + ("kinds", "tiers", "supervisor_mode", "supervisor_projects")  # the whitelist of POST /api/config/models
SUPERVISOR_MODES = ("off", "suggest", "auto")
SUPERVISOR_MODELS = {"supervisor_model": "haiku", "supervisor_stuck_model": "sonnet"}  # never opus/fable/external
WHOLE = frozenset({"steps", "s", "turns", "kb", "parts", "words", "tokens"})
CLAUDE_ONLY = frozenset({"prep_model", "brief_model", "review_model", "planner_model"})  # their passes run on the Claude CLI
WINDOWS = ("day_usd", "week_usd", "month_usd")
KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
MAX_RUNGS = 12  # per tier


def view(cfg: dict) -> dict:
    """/api/config `tuning`: {key: {"value", "default", "min", "max", "unit", "group"}} for every TUNING key."""
    out = {}
    for key, (group, unit, low, high) in TUNING.items():
        default = paths.DEFAULTS.get(key, {} if key == "allowances" else None)
        out[key] = {"value": cfg.get(key, default), "default": default, "min": low, "max": high, "unit": unit,
                    "group": group}
    return out


def _fmt(n) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def _number(value, unit: str, low, high) -> str:
    """"" when `value` fits the unit and the range, else the reason."""
    whole = unit in WHOLE
    span = f"between {_fmt(low)} and {_fmt(high)}"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"a whole number {span}" if whole else f"a number {span}"
    if isinstance(value, int) and not low <= value <= high:
        return span  # plan 27 (B7): a huge int never reaches float(), which raises OverflowError
    if not math.isfinite(value):
        return f"a whole number {span}" if whole else f"a number {span}"
    if whole and not float(value).is_integer():
        return f"a whole number {span}"
    if not low <= value <= high:
        return span
    return ""


def _harness_fits(rung: str, think: bool, cfg: dict) -> str:
    """Plan 5 decision 11: an opencode or cmd model that does not rank opus never takes a think kind or tier."""
    harness, model = fills.split_rung(rung)
    if think and harness in fills.NO_CHECK and fills.rank_of(rung, cfg) != "opus":
        return f"{harness}: {model} is not a think model"
    return ""


def _rung(value, cfg: dict) -> str:
    """"" for a model the page may name: a Claude rung of the ladder, or a model models.json ranks."""
    if not isinstance(value, str) or not value:
        return "a model from models.json"
    claude = fills.split_rung(value)[0] == "claude"
    ok = claude_cli.known_model(cfg, value) if claude else bool(fills.rank_of(value, cfg))
    return "" if ok else f"unknown model: {value}"


def _effort(value) -> str:
    return "" if value == "auto" or value in claude_cli.EFFORTS else f"effort: auto or {', '.join(claude_cli.EFFORTS)}"


def _allowances(value) -> tuple:
    if not isinstance(value, dict):
        return None, "an object: model key -> day_usd, week_usd, month_usd"
    clean = {}
    for key, row in value.items():
        if not isinstance(key, str) or not KEY_RE.fullmatch(key):
            return None, f"{key}: not a model key"
        if not isinstance(row, dict) or set(row) - set(WINDOWS):
            return None, f"{key}: only day_usd, week_usd, month_usd"
        for w, n in row.items():
            why = _number(n, "usd", 0, TUNING["allowances"][3])
            if why:
                return None, f"{key} {w}: {why}"
        clean[key] = {w: row[w] for w in WINDOWS if w in row}
    return clean, ""


def _kinds(value, cfg: dict) -> tuple:
    if not isinstance(value, dict):
        return None, "an object: kind -> rung and effort"
    clean = {}
    for kind, pin in value.items():
        if kind in ("verify", "fix"):
            return None, f"{kind}: set by the rule, not pinnable"
        if kind not in tasks.PREP_KINDS:
            return None, f"unknown kind: {kind}"
        if not isinstance(pin, dict) or set(pin) - {"rung", "effort"}:
            return None, f"{kind}: rung and effort only"
        rung, effort = pin.get("rung", "auto"), pin.get("effort", "auto")
        why = "" if rung == "auto" else _rung(rung, cfg) or _harness_fits(rung, tasks.kind_tier(kind) == "think", cfg)
        why = why or _effort(effort)
        if why:
            return None, f"{kind}: {why}"
        if rung != "auto" or effort != "auto":  # auto and auto is the code's rule: nothing to keep
            clean[kind] = {"rung": rung, "effort": effort}
    return clean, ""


def _tiers(value, cfg: dict) -> tuple:
    if not isinstance(value, dict):
        return None, "an object: tier -> its rungs"
    clean = {}
    for tier, rows in value.items():
        if tier not in tasks.TIERS:
            return None, f"unknown tier: {tier}"
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_RUNGS:
            return None, f"{tier}: 1 to {MAX_RUNGS} rungs"
        seen, out = set(), []
        for n, row in enumerate(rows, 1):
            row = {"rung": row, "effort": "auto"} if isinstance(row, str) else row
            if not isinstance(row, dict) or set(row) - {"rung", "effort"} or "rung" not in row:
                return None, f"{tier} {n}: rung and effort only"
            rung, effort = row["rung"], row.get("effort", "auto")
            why = _rung(rung, cfg) or _harness_fits(rung, tier == "think", cfg) or _effort(effort)
            if not why and rung in seen:
                why = "listed twice"
            if why:
                return None, f"{tier} {n}: {why}"
            seen.add(rung)
            out.append({"rung": rung, "effort": effort})
        clean[tier] = out
    return clean, ""


def _supervisor_projects(value, cfg) -> tuple:
    """The supervisor_projects map: normalized configured-project path -> off|suggest|auto. Replaces the map on save;
    an unknown project, an invalid mode or a normalized duplicate key is refused (nothing is written)."""
    if not isinstance(value, dict):
        return None, "an object: project path -> off, suggest or auto"
    clean, seen = {}, {}
    for key, mode in value.items():
        if not isinstance(key, str) or not key:
            return None, "a project path"
        norm = os.path.normcase(os.path.normpath(os.path.abspath(key)))
        if norm in seen:
            return None, f"{key}: listed twice"
        if not any(tasks.same_dir(key, p) for p in (cfg.get("projects") or [])):
            return None, f"not a project listed in config.json: {key}"
        if mode not in SUPERVISOR_MODES:
            return None, f"{key}: off, suggest or auto"
        seen[norm] = True
        clean[norm] = mode
    return clean, ""


def validate(changes, cfg: dict) -> tuple:
    """One Save of the page: (clean, errors). `clean` holds every change that passed, normalized (a tier's bare rung
    string becomes {"rung", "effort": "auto"}, a kind left on auto and auto is dropped); `errors` maps a key to the
    reason it was refused ("" for the request as a whole). The service writes `clean` only when `errors` is empty."""
    if not isinstance(changes, dict) or not changes:
        return {}, {"": "changes: an object of settings to save"}
    clean, errors = {}, {}
    for key, value in changes.items():
        if key not in KEYS:
            errors[key] = "not a setting this page changes"
            continue
        if key == "kinds":
            value, why = _kinds(value, cfg)
        elif key == "tiers":
            value, why = _tiers(value, cfg)
        elif key == "allowances":
            value, why = _allowances(value)
        elif key == "supervisor_mode":
            why = "" if value in SUPERVISOR_MODES else "off, suggest or auto"
        elif key == "supervisor_projects":
            value, why = _supervisor_projects(value, cfg)
        else:
            group, unit, low, high = TUNING[key]
            if unit == "bool":
                why = "" if isinstance(value, bool) else "true or false"
            elif unit == "text":  # plan 31: whitespace collapsed, newlines and tabs included
                why = "" if isinstance(value, str) and len(" ".join(value.split())) <= high \
                    else f"text of at most {high} characters"
                value = " ".join(value.split()) if not why else value
            elif unit == "rung":
                if key in SUPERVISOR_MODELS:  # plan 44: the supervisor pass is fixed to one Claude alias
                    why = "" if value == SUPERVISOR_MODELS[key] else f"{SUPERVISOR_MODELS[key]} only"
                else:
                    why = _rung(value, cfg)
                    if not why and key in CLAUDE_ONLY and fills.split_rung(value)[0] != "claude":
                        why = "a Claude model: this pass runs on the Claude CLI"
            else:
                why = _number(value, unit, low, high)
                if not why and unit in WHOLE:
                    value = int(value)
        if why:
            errors[key] = why
        else:
            clean[key] = value
    merged = {**cfg, **clean}
    if not errors and merged.get("gauge_yellow_tokens", 0) >= merged.get("gauge_red_tokens", 0):
        key = "gauge_yellow_tokens" if "gauge_yellow_tokens" in clean else "gauge_red_tokens"
        errors[key] = "yellow must start under red"
    return clean, errors
