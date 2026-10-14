# Task 1: The settings module and the config writer

> Contract: [README.md](README.md) 3.2, 3.3, 3.6. Depends on nothing. Decision D3 (the `TUNING` ranges).
> Run in a scratch copy on 2026-10-14 (plan 18 applied; plans 5, 23, 24's config keys added by hand to that copy's
> `DEFAULTS`): `tests/test_tuning.py` 13 OK. Lands on: nothing (plans 5, 18, 23, 24 add keys to `paths.DEFAULTS`,
> which this task reads; plan 5's `set_harness` stays as it is).

**Files**
- Create: `console/tuning.py` (whole file below)
- Modify: `console/paths.py` (new `set_config`, after `add_project`)
- Create: `tests/test_tuning.py` (whole file below)

## 1.1 `console/tuning.py`

Every `TUNING` key must have a default in `paths.DEFAULTS` once plans 5, 23, 24 and 18 are placed (`step_timeout_s`
plan 5, `read_max_turns` plan 23, `brief_max_words` 500 plan 23, `design_max_turns` and the `plan_*` / `replan_auto`
keys plan 24, the balance keys plan 18); `ViewTest` checks it. The ranges are D3 (a).

```python
"""The Models and tuning page's settings (plan 26): which config.json keys the page may change, their ranges, and
the check of one Save. Pure: no files, no threads, no HTTP; the service writes what `validate` keeps."""
import math
import re

from . import claude_cli, fills, paths, tasks

# key -> (group, unit, min, max), in the Tuning tab's order. Units: a whole number for steps, s, turns, kb, parts,
# words, tokens; a number for usd and share (a share is a fraction: 0.1 = 10 points); bool; rung (a model).
TUNING = {
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
}
KEYS = tuple(TUNING) + ("kinds", "tiers")  # the whitelist of POST /api/config/models
WHOLE = frozenset({"steps", "s", "turns", "kb", "parts", "words", "tokens"})
CLAUDE_ONLY = frozenset({"prep_model", "brief_model", "review_model"})  # their passes run on the Claude CLI
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
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
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
        else:
            group, unit, low, high = TUNING[key]
            if unit == "bool":
                why = "" if isinstance(value, bool) else "true or false"
            elif unit == "rung":
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
```

## 1.2 `paths.set_config`

After `def add_project(...)` (its whole body) in `console/paths.py`:

```python
def set_config(folder: Path, values: dict, merge=("tiers",)) -> None:
    """Write `values` into <folder>/config.json with every other key as written (plan 26; set_harness does the same
    for one key): a key named in `merge` updates the file's object one level deep (a tier Fred did not touch keeps
    its list), any other key replaces the file's value. Raises ValueError when config.json exists but cannot be read
    (never overwrite Fred's file)."""
    path = Path(folder) / "config.json"
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            raise ValueError(f"cannot read {path}: fix it by hand")
    for key, value in values.items():
        if key in merge and isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("config.json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
```

`add_project` and plan 5's `set_harness` keep their own code (they write one key each); this one writes many.

## 1.3 Tests (`tests/test_tuning.py`)

Classes `ViewTest` (2), `NumbersTest` (6), `KindsTest` (2), `TiersTest` (2), `SetConfigTest` (1). `CFG` carries a
models.json shape (plan 5 3.2b) so codex and opencode rungs have a rank.

```python
"""Plan 26: the Models and tuning page's settings and the check of one Save (console/tuning.py)."""
import json
import tempfile
import unittest
from pathlib import Path

from console import paths, tuning

CFG = dict(paths.DEFAULTS, models={
    "codex": {"gpt-6-astra": "opus", "gpt-6.1-sol": "sonnet", "gpt-6-luna": "haiku"},
    "opencode": {"opencode-go/kimi-k3": "opus", "opencode-go/deepseek-v4.1-flash": "haiku"},
    "cmd": {"deepseek/deepseek-v4.1-flash": "haiku"}})


def check(**changes):
    return tuning.validate(changes, CFG)


class ViewTest(unittest.TestCase):
    def test_every_key_has_its_default_range_and_group(self):
        view = tuning.view(dict(CFG, task_max_steps=8))
        self.assertEqual(list(view), list(tuning.TUNING))
        self.assertEqual(view["task_max_steps"], {"value": 8, "default": paths.DEFAULTS["task_max_steps"], "min": 1,
                                                  "max": 12, "unit": "steps", "group": "steps"})
        self.assertEqual((view["allowances"]["value"], view["allowances"]["default"]), ({}, {}))
        self.assertEqual(view["plan_hold"]["unit"], "bool")
        for key in tuning.TUNING:
            self.assertIn(key, paths.DEFAULTS, key)  # every key the page shows has a default in code

    def test_whitelist_is_the_contracts(self):
        self.assertEqual(set(tuning.KEYS), {
            "task_max_steps", "task_step_budget_usd", "step_timeout_s", "design_max_turns", "read_max_turns",
            "brief_max_words", "brief_timeout_s", "gauge_red_tokens", "gauge_yellow_tokens", "balance_margin",
            "cache_bonus", "budget_warn_at", "daily_budget_usd", "allowances", "plan_max_kb", "plan_max_parts",
            "plan_hold", "replan_auto", "prep_model", "brief_model", "review_model", "default_model", "kinds", "tiers"})


class NumbersTest(unittest.TestCase):
    def test_in_range_is_kept_and_whole_numbers_are_ints(self):
        clean, errors = check(task_max_steps=8.0, balance_margin=0.15, daily_budget_usd=0, plan_hold=True)
        self.assertEqual(errors, {})
        self.assertEqual(clean, {"task_max_steps": 8, "balance_margin": 0.15, "daily_budget_usd": 0, "plan_hold": True})
        self.assertIsInstance(clean["task_max_steps"], int)

    def test_reasons(self):
        clean, errors = check(balance_margin=0.6, task_max_steps=2.5, brief_max_words="500", plan_hold=1,
                              step_timeout_s=True, budget_warn_at=float("nan"))
        self.assertEqual(clean, {})
        self.assertEqual(errors, {"balance_margin": "between 0 and 0.5",
                                  "task_max_steps": "a whole number between 1 and 12",
                                  "brief_max_words": "a whole number between 100 and 2000",
                                  "plan_hold": "true or false",
                                  "step_timeout_s": "a whole number between 60 and 7200",
                                  "budget_warn_at": "a number between 0.1 and 2"})

    def test_unknown_keys_and_empty_saves_are_refused(self):
        self.assertEqual(check(port=1)[1], {"port": "not a setting this page changes"})
        self.assertEqual(check(prices={})[1], {"prices": "not a setting this page changes"})
        self.assertEqual(tuning.validate({}, CFG), ({}, {"": "changes: an object of settings to save"}))
        self.assertEqual(tuning.validate([1], CFG)[1], {"": "changes: an object of settings to save"})

    def test_yellow_starts_under_red(self):
        self.assertEqual(check(gauge_yellow_tokens=300000)[1], {"gauge_yellow_tokens": "yellow must start under red"})
        self.assertEqual(check(gauge_red_tokens=100000)[1], {"gauge_red_tokens": "yellow must start under red"})
        self.assertEqual(check(gauge_yellow_tokens=100000, gauge_red_tokens=200000)[1], {})

    def test_models_of_the_passes(self):
        self.assertEqual(check(prep_model="sonnet", default_model="codex:gpt-6.1-sol")[1], {})
        self.assertEqual(check(brief_model="codex:gpt-6-luna")[1],
                         {"brief_model": "a Claude model: this pass runs on the Claude CLI"})
        self.assertEqual(check(default_model="codex:nope")[1], {"default_model": "unknown model: codex:nope"})
        self.assertEqual(check(review_model="claude-opus-9")[1], {"review_model": "unknown model: claude-opus-9"})

    def test_allowances(self):
        clean, errors = check(allowances={"opus": {"day_usd": 10, "month_usd": 150}, "kimi-k3": {}})
        self.assertEqual((clean["allowances"], errors), ({"opus": {"day_usd": 10, "month_usd": 150}, "kimi-k3": {}}, {}))
        self.assertEqual(check(allowances={"opus": {"day_usd": -1}})[1],
                         {"allowances": "opus day_usd: between 0 and 100000"})
        self.assertEqual(check(allowances={"opus": {"day_tokens": 1}})[1],
                         {"allowances": "opus: only day_usd, week_usd, month_usd"})
        self.assertEqual(check(allowances={"../x": {}})[1], {"allowances": "../x: not a model key"})
        self.assertEqual(check(allowances=[])[1], {"allowances": "an object: model key -> day_usd, week_usd, month_usd"})


class KindsTest(unittest.TestCase):
    def test_pins_are_kept_and_auto_is_dropped(self):
        clean, errors = check(kinds={"code": {"rung": "auto", "effort": "high"}, "test": {"rung": "codex:gpt-6-luna"},
                                     "scout": {"rung": "auto", "effort": "auto"}})
        self.assertEqual(errors, {})
        self.assertEqual(clean["kinds"], {"code": {"rung": "auto", "effort": "high"},
                                          "test": {"rung": "codex:gpt-6-luna", "effort": "auto"}})

    def test_reasons(self):
        self.assertEqual(check(kinds={"verify": {"rung": "opus"}})[1], {"kinds": "verify: set by the rule, not pinnable"})
        self.assertEqual(check(kinds={"fix": {"effort": "high"}})[1], {"kinds": "fix: set by the rule, not pinnable"})
        self.assertEqual(check(kinds={"nap": {}})[1], {"kinds": "unknown kind: nap"})
        self.assertEqual(check(kinds={"code": {"rung": "codex:nope"}})[1], {"kinds": "code: unknown model: codex:nope"})
        self.assertEqual(check(kinds={"code": {"effort": "huge"}})[1],
                         {"kinds": "code: effort: auto or low, medium, high, xhigh, max"})
        self.assertEqual(check(kinds={"code": {"model": "opus"}})[1], {"kinds": "code: rung and effort only"})
        self.assertEqual(check(kinds={"design": {"rung": "opencode:opencode-go/deepseek-v4.1-flash"}})[1],
                         {"kinds": "design: opencode: opencode-go/deepseek-v4.1-flash is not a think model"})
        self.assertEqual(check(kinds={"design": {"rung": "opencode:opencode-go/kimi-k3"}})[1], {})  # opus rank


class TiersTest(unittest.TestCase):
    def test_a_tier_is_normalized(self):
        clean, errors = check(tiers={"read": ["haiku", {"rung": "codex:gpt-6-luna", "effort": "high"}]})
        self.assertEqual(errors, {})
        self.assertEqual(clean["tiers"], {"read": [{"rung": "haiku", "effort": "auto"},
                                                   {"rung": "codex:gpt-6-luna", "effort": "high"}]})

    def test_reasons(self):
        self.assertEqual(check(tiers={"fast": ["haiku"]})[1], {"tiers": "unknown tier: fast"})
        self.assertEqual(check(tiers={"read": []})[1], {"tiers": "read: 1 to 12 rungs"})
        self.assertEqual(check(tiers={"read": ["haiku"] * 13})[1], {"tiers": "read: 1 to 12 rungs"})
        self.assertEqual(check(tiers={"read": ["haiku", "haiku"]})[1], {"tiers": "read 2: listed twice"})
        self.assertEqual(check(tiers={"write": ["sonnet", "codex:nope"]})[1], {"tiers": "write 2: unknown model: codex:nope"})
        self.assertEqual(check(tiers={"think": ["opus", "cmd:deepseek/deepseek-v4.1-flash"]})[1],
                         {"tiers": "think 2: cmd: deepseek/deepseek-v4.1-flash is not a think model"})
        self.assertEqual(check(tiers={"write": [{"rung": "sonnet", "effort": "max!"}]})[1],
                         {"tiers": "write 1: effort: auto or low, medium, high, xhigh, max"})
        self.assertEqual(check(tiers={"write": ["opus", "cmd:deepseek/deepseek-v4.1-flash"]})[1], {})  # D1 a, hard only


class SetConfigTest(unittest.TestCase):
    def test_writes_the_keys_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"projects": ["x"], "tiers": {"write": ["sonnet"]}, "kinds": {"code": {}}}),
                            encoding="utf-8")
            paths.set_config(tmp, {"tiers": {"read": ["haiku"]}, "kinds": {}, "task_max_steps": 8})
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data, {"projects": ["x"], "tiers": {"write": ["sonnet"], "read": ["haiku"]}, "kinds": {},
                                    "task_max_steps": 8})  # tiers merge one level; kinds is replaced whole
            path.write_text("[1]", encoding="utf-8")
            with self.assertRaises(ValueError):
                paths.set_config(tmp, {"task_max_steps": 8})
            self.assertEqual(path.read_text(encoding="utf-8"), "[1]")
            path.unlink()
            paths.set_config(tmp, {"plan_hold": True})  # no file yet: only what was saved
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"plan_hold": True})


if __name__ == "__main__":
    unittest.main()
```

## 1.4 Steps

1. Write `tests/test_tuning.py`; run `py -m unittest tests.test_tuning`: ImportError on `tuning`.
2. `console/tuning.py` and `paths.set_config`; run: 13 OK. If `ViewTest.test_every_key_has_its_default_range_and_group`
   names a key missing from `DEFAULTS`, the plan that owns it is not placed: stop and say which.
3. The whole suite: the count + 13.
4. Commit: `plan 26 task 1: the settings the Models page may change, checked (N tests OK)`.

## 1.5 Drift guards

- `tuning.py` imports `paths` for `DEFAULTS` only; it never reads or writes a file.
- `validate` never raises on any JSON value; a refusal is a reason string.
- `set_config` never touches a file it could not read.
