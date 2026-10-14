# Task 1: The fills module

> Contract: [README.md](README.md) 3.2, 3.3, 3.6 (the balance notes), 3.8. Decisions D1 (`pool`), D3 (`fill`). Run in
> a scratch copy on 2026-10-14: 20 tests OK. Pure: no threads, no files, no HTTP.

**Files**
- Create: `console/fills.py` (below, whole), `tests/test_fills.py` (below, whole)

**Imports allowed in `console/fills.py`**: `time`, `datetime` (`datetime`, `timedelta`), and from the package
`claude_cli` (MODELS, EFFORTS, model_alias). Nothing from `tasks`, `server`, `runs`, `usage`, `harness`: `tasks`
imports `fills`, and `fills` must run before and after plan 5.

## 1.1 What each function does

| Function | Signature | Does |
|---|---|---|
| `split_rung` | `(rung) -> (harness, model)` | plan 5's rule: a known harness name before the first colon, else Claude |
| `model_key` | `(rung, cfg=None) -> str` | the fill's key (README 3.2) |
| `rank_of` | `(rung, cfg=None) -> str` | the rung's rank (README 3.2) |
| `provider` | `(rung) -> str` | `anthropic` for a Claude family, else `PROVIDER[harness]`; for `peak_hours` |
| `tier_rungs` | `(cfg, tier) -> [(rung, effort)]` | config `tiers[tier]` cleaned: bad or repeated entries dropped, a bad effort read as `auto` |
| `hard_only` | `(rung, tier, cfg=None) -> bool` | rank above the tier's rank |
| `pool` | `(cfg, rank, *, check=False, hard=False, refuse=None) -> [(rung, effort)]` | the rungs a step of that rank balances over (D1 a: weaker rungs Fred placed join) |
| `windows` | `(now, month_start_day=1) -> {name: (start, end)}` | local day, week from Monday, month from the billing day |
| `pace` | `(allowance, start, end, now) -> float` | linear, at least one hour of the window, capped at the allowance |
| `used` | `(days, other, key, day_keys) -> (usd, unknown_runs)` | Claude transcripts plus other harnesses' priced runs |
| `fill` | `(days, other, key, allowance, now, month_start_day=1) -> dict` | one key's three windows, `binding`, `share`, `unknown_runs` (D3 a) |
| `keys_of` | `(cfg, days=None, other=None) -> [key]` | allowances, tier rungs, used families, other harnesses' keys |
| `via_of` | `(cfg, key) -> [harness]` | the harnesses whose tier rungs reach the key |
| `fills` | `(days, other, cfg, now) -> {key: fill + via}` | `Hub.budget()`'s body |
| `price` | `(tokens, row) -> float | None` | tokens x a price row (USD per million); None when either is missing |
| `merge_other` | `(days, other) -> days` | a copy of the days with the other harnesses' priced cost in `cost` / `models` and `unknown` counts |
| `peak_add` | `(cfg, rung, now) -> float` | what `peak_hours` adds to the rung's share now; 0 when off |
| `balance` | `(rungs, budget, cfg, *, tier="", prev_rung="", prev_age=None, now=None) -> dict` | the pick: `{"rung", "effort", "share", "note", "over"}` |
| `fail_hours` | `(tasks, cfg, now, days=30) -> {key: {"runs", "fails", "via"}}` | each verify verdict counted on the model that wrote the checked step, at the hour it started |

## 1.2 `console/fills.py` (final code)

`D1` marks the `pool` line that keeps weaker rungs (with D1 (b) the `elif` becomes `elif r != base and not (hard and
order.index(r) > order.index(base)): continue`). `D3` marks the `fill` line that makes a key with an unpriced run
unknown (with D3 (b): `if best is None:`).

```python
"""Usage fills per model and the balance pick (plan 18). Pure: no threads, no files, no HTTP.

A model key names one fill: a Claude rung is its family (`opus`), any other rung the model id after its last `/`
(`opencode:opencode-go/kimi-k3` -> `kimi-k3`), so one model through two CLIs is one fill. Each key has three
windows (the local day, the week from Monday, the month from `month_start_day`); a window's share is what was used
over its linear pace (the allowance times the elapsed part of the window). The share that binds is the highest.
`balance` takes the rung of a tier whose model has the lowest share, keeps the previous step's rung while it is
within `balance_margin` (its warm cache counting for it), and puts rungs with no allowance after the others.
Unknown is never zero: a key with an unpriced run in its month has no share."""
import time
from datetime import datetime, timedelta

from . import claude_cli

HARNESSES = ("claude", "codex", "opencode", "cmd")  # plan 5 harness.NAMES (a test compares them once it exists)
NO_CHECK = ("opencode", "cmd")  # never verify or fix (plan 5 decision 11)
TIERS = ("read", "write", "think")
TIER_RANK = {"read": "haiku", "write": "sonnet", "think": "opus"}
RANK_TIER = {"haiku": "read", "sonnet": "write", "opus": "think", "fable": "think"}
WINDOWS = ("day", "week", "month")
PACE_MIN_S = 3600  # the pace counts at least one hour of a window, so the first minutes of a day do not explode
CACHE_TTL_S = 300  # the prompt cache lives 5 minutes: the warm bonus only while the previous step is that recent
PROVIDER = {"claude": "anthropic", "codex": "openai", "opencode": "opencode", "cmd": "cmd"}


# -- names ------------------------------------------------------------------------------------------------

def split_rung(rung) -> tuple:
    """"codex:gpt-6.1-sol" -> ("codex", "gpt-6.1-sol"); "sonnet" -> ("claude", "sonnet") (plan 5 3.1)."""
    head, sep, rest = str(rung or "").partition(":")
    return (head, rest) if sep and head in HARNESSES else ("claude", str(rung or ""))


def model_key(rung, cfg=None) -> str:
    """The fill a rung counts in: a Claude family alias, else the model id after its last `/`; a Claude model
    reached through another CLI (`opencode:openrouter/anthropic/claude-sonnet-4-6`) counts in its family."""
    harness, model = split_rung(rung)
    last = model.rsplit("/", 1)[-1]
    if harness == "claude":
        return claude_cli.model_alias(model) or model
    return claude_cli.model_alias(last) or last


def rank_of(rung, cfg=None) -> str:
    """A rung's rank (plan 5's tier): a Claude alias by its name, any other from models.json (`cfg["models"]`);
    "" when unknown. Equal to plan 5's `claude_cli.tier_of(rung, cfg)` for every listed rung."""
    harness, model = split_rung(rung)
    if harness == "claude":
        return claude_cli.model_alias(model)
    tier = (((cfg or {}).get("models") or {}).get(harness) or {}).get(model)
    return tier if tier in claude_cli.MODELS else ""


def provider(rung) -> str:
    """Who serves the model, for `peak_hours`: Claude families are anthropic whatever the CLI."""
    harness, _ = split_rung(rung)
    return "anthropic" if model_key(rung) in claude_cli.MODELS else PROVIDER.get(harness, harness)


def tier_rungs(cfg, tier) -> list:
    """[(rung, effort)] of config `tiers[tier]` in order; a malformed or repeated entry is dropped."""
    out, seen = [], set()
    for entry in ((cfg or {}).get("tiers") or {}).get(tier) or []:
        if isinstance(entry, str):
            entry = {"rung": entry, "effort": "auto"}
        if not isinstance(entry, dict) or not isinstance(entry.get("rung"), str) or not entry["rung"]:
            continue
        effort = entry.get("effort") if entry.get("effort") in claude_cli.EFFORTS else "auto"
        if entry["rung"] not in seen:
            seen.add(entry["rung"])
            out.append((entry["rung"], effort))
    return out


def hard_only(rung, tier, cfg=None) -> bool:
    """A rung ranked above its tier's rank (opus in write, fable in think) runs only on hard steps."""
    rank, base = rank_of(rung, cfg), TIER_RANK.get(tier, "")
    return bool(rank and base) and claude_cli.MODELS.index(rank) > claude_cli.MODELS.index(base)


def pool(cfg, rank, *, check=False, hard=False, refuse=None) -> list:
    """The rungs a step of `rank` may balance over, [(rung, effort)] in tier order. A verify or fix (`check`):
    the rungs of exactly that rank, never opencode or cmd. Any other step: the tier's rungs ranked at or under the
    tier's rank, plus the hard-only ones when `hard`; a `fable` rank keeps fable rungs only. `refuse(rung)` gives
    a reason for a rung that cannot run now (harness off, not found, not on this kind); those are skipped."""
    tier = RANK_TIER.get(rank)
    if not tier:
        return []
    order, base = claude_cli.MODELS, TIER_RANK[tier]
    out = []
    for rung, effort in tier_rungs(cfg, tier):
        r = rank_of(rung, cfg)
        if not r:
            continue
        if check:
            if r != rank or split_rung(rung)[0] in NO_CHECK:
                continue
        elif rank == "fable":
            if r != "fable":
                continue
        elif order.index(r) > order.index(base) and not hard:  # D1 a: a weaker rung Fred placed here joins
            continue
        if refuse and refuse(rung):
            continue
        out.append((rung, effort))
    return out


# -- windows, pace and fills --------------------------------------------------------------------------------

def windows(now: float, month_start_day: int = 1) -> dict:
    """{"day" | "week" | "month": (start, end)} as local epoch seconds. The week starts on Monday; the month on
    `month_start_day` (1 to 28, clamped), the billing day."""
    today = datetime.fromtimestamp(now).date()
    day0 = datetime(today.year, today.month, today.day)
    week0 = day0 - timedelta(days=today.weekday())
    msd = min(max(int(month_start_day or 1), 1), 28)
    if today.day >= msd:
        y, m = today.year, today.month
    else:
        y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    month0 = datetime(y, m, msd)
    month1 = datetime(y, m + 1, msd) if m < 12 else datetime(y + 1, 1, msd)
    return {"day": (day0.timestamp(), (day0 + timedelta(days=1)).timestamp()),
            "week": (week0.timestamp(), (week0 + timedelta(days=7)).timestamp()),
            "month": (month0.timestamp(), month1.timestamp())}


def pace(allowance: float, start: float, end: float, now: float) -> float:
    """The linear pace: the allowance times the elapsed part of the window (at least PACE_MIN_S of it)."""
    part = max(now - start, PACE_MIN_S) / max(end - start, 1.0)
    return allowance * min(part, 1.0)


def _days(start: float, now: float) -> list:
    first, last = datetime.fromtimestamp(start).date(), datetime.fromtimestamp(now).date()
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def used(days: dict, other: dict, key: str, keys: list) -> tuple:
    """(USD, unknown runs) of `key` over the day keys: Claude transcripts (`days[d]["models"]`) plus the priced
    runs of other harnesses (`other[d][key]`)."""
    usd, unknown = 0.0, 0
    for d in keys:
        usd += float(((days.get(d) or {}).get("models") or {}).get(key) or 0)
        row = (other.get(d) or {}).get(key) or {}
        usd += float(row.get("cost") or 0)
        unknown += int(row.get("unknown") or 0)
    return usd, unknown


def fill(days: dict, other: dict, key: str, allowance, now: float, month_start_day: int = 1) -> dict:
    """One key's three windows, its binding window and share (README 3.3)."""
    out, best = {}, None
    allowance = allowance if isinstance(allowance, dict) else {}
    for name, (start, end) in windows(now, month_start_day).items():
        usd, unknown = used(days, other, key, _days(start, now))
        cap = allowance.get(f"{name}_usd")
        cap = float(cap) if isinstance(cap, (int, float)) and not isinstance(cap, bool) and cap > 0 else None
        p = pace(cap, start, end, now) if cap else None
        share = round(usd / p, 4) if p else None
        out[name] = {"used_usd": round(usd, 4), "allowance_usd": cap, "pace_usd": round(p, 4) if p else None,
                     "share": share, "unknown_runs": unknown}
        if share is not None and (best is None or share > out[best]["share"]):
            best = name
    unknown = out["month"]["unknown_runs"]
    out["unknown_runs"] = unknown
    if best is None or unknown:  # D3 a (D-3): an unpriced run makes the fill unknown, never smaller
        out["binding"], out["share"] = "", None
    else:
        out["binding"], out["share"] = best, out[best]["share"]
    return out


def keys_of(cfg, days: dict = None, other: dict = None) -> list:
    """Every key worth a fill: the allowances, every rung of the tiers, every key used in the kept days."""
    keys = list((cfg.get("allowances") or {}).keys())
    for tier in TIERS:
        keys += [model_key(r, cfg) for r, _ in tier_rungs(cfg, tier)]
    for d in (days or {}).values():
        keys += [k for k in (d.get("models") or {}) if k in claude_cli.MODELS]
    for d in (other or {}).values():
        keys += list(d)
    return list(dict.fromkeys(k for k in keys if k))


def via_of(cfg, key: str) -> list:
    """The harnesses whose tier rungs reach `key`, in HARNESSES order; a Claude family reached by none: claude."""
    found = {split_rung(r)[0] for t in TIERS for r, _ in tier_rungs(cfg, t) if model_key(r, cfg) == key}
    if not found and key in claude_cli.MODELS:
        found = {"claude"}
    return [h for h in HARNESSES if h in found]


def fills(days: dict, other: dict, cfg: dict, now: float) -> dict:
    """Hub.budget(): {key: fill(...) + {"via": [...]}} for every key of keys_of."""
    allowances = cfg.get("allowances") or {}
    return {k: dict(fill(days, other, k, allowances.get(k), now, cfg.get("month_start_day", 1)), via=via_of(cfg, k))
            for k in keys_of(cfg, days, other)}


def price(tokens, row):
    """USD of one run's tokens ({"input", "output", "cache_read"}, input without the cached part) at a price row
    (USD per million); None when either is missing (unknown, never zero)."""
    if not isinstance(tokens, dict) or not isinstance(row, dict):
        return None
    try:
        return round((int(tokens.get("input") or 0) * float(row["input"])
                      + int(tokens.get("output") or 0) * float(row["output"])
                      + int(tokens.get("cache_read") or 0) * float(row.get("cache_read", row["input"]))) / 1e6, 6)
    except (KeyError, TypeError, ValueError):
        return None


def merge_other(days: dict, other: dict) -> dict:
    """The days with the other harnesses' priced runs added to `cost` and `models`, and `unknown` {key: runs}:
    what the Usage page and the today strip show. A copy; fills read the two apart."""
    out = {d: dict(v, models=dict(v.get("models") or {})) for d, v in days.items()}
    for d, keys in other.items():
        day = out.setdefault(d, {"cost": 0.0, "tokens": [0, 0, 0, 0], "projects": {}, "models": {}})
        for key, row in keys.items():
            cost = float(row.get("cost") or 0)
            if cost:
                day["cost"] = round(float(day.get("cost") or 0) + cost, 4)
                day["models"][key] = round(day["models"].get(key, 0.0) + cost, 4)
            if row.get("unknown"):
                day.setdefault("unknown", {})[key] = int(row["unknown"])
    return out


def peak_add(cfg, rung, now: float) -> float:
    """`peak_hours` {provider: {"hours": "14-19", "add": 0.2}}: what the rung's share gains in those local hours;
    0 when off (the default {})."""
    rule = ((cfg or {}).get("peak_hours") or {}).get(provider(rung))
    if not isinstance(rule, dict):
        return 0.0
    try:
        a, b = (int(x) for x in str(rule.get("hours", "")).split("-"))
        add = float(rule.get("add") or 0)
    except ValueError:
        return 0.0
    hour = time.localtime(now).tm_hour
    inside = a <= hour < b if a <= b else (hour >= a or hour < b)
    return add if inside else 0.0


# -- the balance pick ---------------------------------------------------------------------------------------

def _pct(share) -> str:
    return "no allowance" if share is None else f"{round(share * 100)} %"


def balance(rungs: list, budget: dict, cfg: dict, *, tier: str = "", prev_rung: str = "", prev_age=None,
            now: float = None) -> dict:
    """The rung of `rungs` ([(rung, effort)], tier order) whose model has the lowest share of pace (plus
    `peak_hours`); rungs with no share follow in order. The previous step's rung stays while its share, less
    `cache_bonus` when it ran under CACHE_TTL_S ago, is within `balance_margin` of the lowest. Returns
    {"rung", "effort", "share", "note", "over"}; `over` when every rung has a share at or over `budget_warn_at`."""
    now = time.time() if now is None else now
    margin = float(cfg.get("balance_margin", 0.1))
    bonus = float(cfg.get("cache_bonus", 0.1))
    warn = float(cfg.get("budget_warn_at", 0.8))
    rows = []
    for i, (rung, effort) in enumerate(rungs):
        share = (budget.get(model_key(rung, cfg)) or {}).get("share")
        eff = None if share is None else share + peak_add(cfg, rung, now)
        rows.append({"i": i, "rung": rung, "effort": effort, "share": share, "eff": eff})
    if not rows:
        return {"rung": "", "effort": "auto", "share": None, "note": "", "over": False}
    ranked = sorted(rows, key=lambda r: (r["eff"] is None, r["eff"] if r["eff"] is not None else 0, r["i"]))
    best, first = ranked[0], rows[0]
    chosen, kept = best, False
    prev = next((r for r in rows if r["rung"] == prev_rung), None)
    if prev and prev is not best and prev["eff"] is not None and best["eff"] is not None:
        warm = bonus if prev_age is not None and prev_age < CACHE_TTL_S else 0.0
        if prev["eff"] - warm - best["eff"] <= margin:
            chosen, kept = prev, True
    over = all(r["share"] is not None and r["share"] >= warn for r in rows)
    if len(rows) == 1:
        note = f"balance: {chosen['rung']} only"
    elif all(r["share"] is None for r in rows):
        note = f"balance: no allowance set -> {chosen['rung']} (list order)"
    elif over:
        note = f"balance: every {tier} rung over pace -> {chosen['rung']} {_pct(chosen['share'])}"
    elif chosen is first:
        note = f"balance: {chosen['rung']} {_pct(chosen['share'])}"
    else:
        note = f"balance: {first['rung']} {_pct(first['share'])} -> {chosen['rung']} {_pct(chosen['share'])}"
    if kept:
        note += f" (previous rung kept: {best['rung']} {_pct(best['share'])} is within the margin)"
    if chosen["eff"] is not None and chosen["eff"] != chosen["share"]:
        note += f" (peak {provider(chosen['rung'])} +{round((chosen['eff'] - chosen['share']) * 100)})"
    return {"rung": chosen["rung"], "effort": chosen["effort"], "share": chosen["share"], "note": note, "over": over}


# -- the evidence: verify FAIL by hour ---------------------------------------------------------------------

def fail_hours(tasks: dict, cfg: dict, now: float, days: int = 30) -> dict:
    """{key: {"runs": [24], "fails": [24], "via": [harness]}}: every verify with a verdict in the last `days`,
    counted on the model that wrote the step it checked, at the local hour that step started."""
    out, cutoff = {}, now - days * 86400
    for task in tasks.values():
        steps = {s.get("n"): s for s in task.get("steps") or [] if isinstance(s, dict)}
        for s in steps.values():
            if s.get("kind") != "verify" or s.get("verdict") not in ("PASS", "FAIL"):
                continue
            done = steps.get(s.get("checked"))
            if not done or not done.get("model") or not isinstance(done.get("started"), (int, float)):
                continue
            if done["started"] < cutoff:
                continue
            key = model_key(done["model"], cfg)
            row = out.setdefault(key, {"runs": [0] * 24, "fails": [0] * 24, "via": []})
            hour = time.localtime(done["started"]).tm_hour
            row["runs"][hour] += 1
            row["fails"][hour] += s["verdict"] == "FAIL"
            harness = split_rung(done["model"])[0]
            if harness not in row["via"]:
                row["via"].append(harness)
    return out
```

## 1.3 `tests/test_fills.py` (final code)

```python
"""Plan 18: usage fills per model and the balance pick (console/fills.py)."""
import unittest
from datetime import datetime

from console import fills

NOW = datetime(2026, 10, 14, 15, 0).timestamp()  # a Wednesday, 15:00 local
CFG = {
    "models": {"codex": {"gpt-6-astra": "opus", "gpt-6.1-sol": "sonnet", "gpt-6-luna": "haiku"},
               "opencode": {"opencode-go/kimi-k3": "opus", "opencode-go/deepseek-v4.1-flash": "haiku"},
               "cmd": {"deepseek/deepseek-v4.1-flash": "haiku"}},
    "tiers": {"think": [{"rung": "opus", "effort": "auto"}, {"rung": "codex:gpt-6-astra", "effort": "high"},
                        {"rung": "opencode:opencode-go/kimi-k3", "effort": "auto"}, {"rung": "fable", "effort": "auto"}],
              "write": [{"rung": "sonnet", "effort": "auto"}, {"rung": "codex:gpt-6.1-sol", "effort": "auto"},
                        {"rung": "opus", "effort": "auto"},
                        {"rung": "opencode:opencode-go/deepseek-v4.1-flash", "effort": "auto"}],
              "read": [{"rung": "haiku", "effort": "auto"}, {"rung": "cmd:deepseek/deepseek-v4.1-flash", "effort": "auto"}]},
    "allowances": {"opus": {"day_usd": 10, "week_usd": 50, "month_usd": 150}},
    "balance_margin": 0.1, "cache_bonus": 0.1, "budget_warn_at": 0.8, "month_start_day": 1, "peak_hours": {},
}


def at(share):
    return {"share": share}


class NamesTest(unittest.TestCase):
    def test_model_key_names_one_fill(self):
        self.assertEqual(fills.model_key("opus"), "opus")
        self.assertEqual(fills.model_key("claude-opus-4-8"), "opus")
        self.assertEqual(fills.model_key("opencode:opencode-go/kimi-k3"), "kimi-k3")
        self.assertEqual(fills.model_key("cmd:deepseek/deepseek-v4.1-flash"), "deepseek-v4.1-flash")
        self.assertEqual(fills.model_key("opencode:opencode-go/deepseek-v4.1-flash"), "deepseek-v4.1-flash")
        self.assertEqual(fills.model_key("codex:gpt-6.1-sol"), "gpt-6.1-sol")
        self.assertEqual(fills.model_key("opencode:openrouter/anthropic/claude-sonnet-4-6"), "sonnet")

    def test_split_and_rank(self):
        self.assertEqual(fills.split_rung("codex:gpt-6.1-sol"), ("codex", "gpt-6.1-sol"))
        self.assertEqual(fills.split_rung("sonnet"), ("claude", "sonnet"))
        self.assertEqual(fills.rank_of("claude-haiku-4-5"), "haiku")
        self.assertEqual(fills.rank_of("codex:gpt-6-astra", CFG), "opus")
        self.assertEqual(fills.rank_of("codex:nope", CFG), "")
        self.assertEqual(fills.rank_of("codex:gpt-6-astra"), "")  # no models.json, no rank

    def test_tier_rungs_drops_bad_entries(self):
        cfg = {"tiers": {"read": ["haiku", {"rung": "haiku"}, {"rung": ""}, 3, {"rung": "codex:gpt-6-luna",
                                                                                 "effort": "ultra"}]}}
        self.assertEqual(fills.tier_rungs(cfg, "read"), [("haiku", "auto"), ("codex:gpt-6-luna", "auto")])
        self.assertEqual(fills.tier_rungs({}, "think"), [])

    def test_pool_keeps_rank_and_hard_only(self):
        rungs = lambda pool: [r for r, _ in pool]
        self.assertEqual(rungs(fills.pool(CFG, "sonnet")),
                         ["sonnet", "codex:gpt-6.1-sol", "opencode:opencode-go/deepseek-v4.1-flash"])
        self.assertEqual(rungs(fills.pool(CFG, "sonnet", hard=True)),
                         ["sonnet", "codex:gpt-6.1-sol", "opus", "opencode:opencode-go/deepseek-v4.1-flash"])
        self.assertEqual(rungs(fills.pool(CFG, "opus")), ["opus", "codex:gpt-6-astra", "opencode:opencode-go/kimi-k3"])
        self.assertIn("fable", rungs(fills.pool(CFG, "opus", hard=True)))
        self.assertEqual(rungs(fills.pool(CFG, "fable")), ["fable"])
        off = lambda rung: "codex is off" if rung.startswith("codex:") else ""
        self.assertEqual(rungs(fills.pool(CFG, "opus", refuse=off)), ["opus", "opencode:opencode-go/kimi-k3"])
        self.assertTrue(fills.hard_only("opus", "write") and fills.hard_only("fable", "think"))
        self.assertFalse(fills.hard_only("codex:gpt-6-astra", "think", CFG))

    def test_pool_for_checks_has_exact_rank_and_no_cheap_harness(self):
        rungs = lambda pool: [r for r, _ in pool]
        self.assertEqual(rungs(fills.pool(CFG, "opus", check=True)), ["opus", "codex:gpt-6-astra"])
        self.assertEqual(rungs(fills.pool(CFG, "sonnet", check=True)), ["sonnet", "codex:gpt-6.1-sol"])
        self.assertEqual(rungs(fills.pool(CFG, "haiku", check=True)), ["haiku"])


class WindowsTest(unittest.TestCase):
    def test_windows_day_week_month(self):
        w = fills.windows(NOW)
        self.assertEqual(w["day"], (datetime(2026, 10, 14).timestamp(), datetime(2026, 10, 15).timestamp()))
        self.assertEqual(w["week"], (datetime(2026, 10, 12).timestamp(), datetime(2026, 10, 19).timestamp()))
        self.assertEqual(w["month"], (datetime(2026, 10, 1).timestamp(), datetime(2026, 11, 1).timestamp()))
        self.assertEqual(fills.windows(NOW, 20)["month"],
                         (datetime(2026, 9, 20).timestamp(), datetime(2026, 10, 20).timestamp()))
        jan = datetime(2027, 1, 5, 9).timestamp()
        self.assertEqual(fills.windows(jan, 15)["month"],
                         (datetime(2026, 12, 15).timestamp(), datetime(2027, 1, 15).timestamp()))
        self.assertEqual(fills.windows(datetime(2026, 12, 20).timestamp(), 31)["month"][0],
                         datetime(2026, 11, 28).timestamp())  # 31 is clamped to 28

    def test_pace_is_linear_with_a_floor(self):
        start = datetime(2026, 10, 14).timestamp()
        self.assertAlmostEqual(fills.pace(24, start, start + 86400, start + 6 * 3600), 6)
        self.assertAlmostEqual(fills.pace(24, start, start + 86400, start + 60), 1)  # one hour at least
        self.assertAlmostEqual(fills.pace(24, start, start + 86400, start + 2 * 86400), 24)


class FillTest(unittest.TestCase):
    DAYS = {"2026-10-14": {"models": {"opus": 5.0, "sonnet": 1.0}},
            "2026-10-13": {"models": {"opus": 10.0}},
            "2026-10-01": {"models": {"opus": 20.0}},
            "2026-09-30": {"models": {"opus": 99.0}}}

    def test_fill_shares_and_binding(self):
        f = fills.fill(self.DAYS, {}, "opus", CFG["allowances"]["opus"], NOW)
        self.assertEqual(f["day"]["used_usd"], 5.0)
        self.assertAlmostEqual(f["day"]["pace_usd"], 10 * 15 / 24, places=3)
        self.assertAlmostEqual(f["day"]["share"], round(5 / (10 * 15 / 24), 4))
        self.assertEqual(f["week"]["used_usd"], 15.0)  # Monday 12th to today
        self.assertEqual(f["month"]["used_usd"], 35.0)  # September 30th is last month
        best = max(("day", "week", "month"), key=lambda w: f[w]["share"])
        self.assertEqual((f["binding"], f["share"]), (best, f[best]["share"]))
        self.assertEqual(f["unknown_runs"], 0)

    def test_no_allowance_has_no_share(self):
        f = fills.fill(self.DAYS, {}, "sonnet", None, NOW)
        self.assertEqual((f["share"], f["binding"], f["day"]["allowance_usd"], f["day"]["used_usd"]), (None, "", None, 1.0))
        f = fills.fill(self.DAYS, {}, "opus", {"month_usd": 150}, NOW)  # one window only: it binds
        self.assertEqual(f["binding"], "month")

    def test_other_harness_runs_count_and_unpriced_ones_make_it_unknown(self):
        other = {"2026-10-14": {"gpt-6.1-sol": {"cost": 2.0, "runs": 2, "unknown": 0, "tokens": [1, 2, 3]}}}
        f = fills.fill({}, other, "gpt-6.1-sol", {"day_usd": 8}, NOW)
        self.assertEqual(f["day"]["used_usd"], 2.0)
        self.assertIsNotNone(f["share"])
        other["2026-10-02"] = {"gpt-6.1-sol": {"cost": 0, "runs": 1, "unknown": 1, "tokens": [0, 0, 0]}}
        f = fills.fill({}, other, "gpt-6.1-sol", {"day_usd": 8}, NOW)
        self.assertEqual((f["share"], f["binding"], f["unknown_runs"]), (None, "", 1))
        self.assertIsNotNone(f["day"]["share"])  # today itself is priced

    def test_fills_lists_keys_and_via(self):
        out = fills.fills(self.DAYS, {"2026-10-14": {"kimi-k3": {"cost": 1.0, "runs": 1, "unknown": 0}}}, CFG, NOW)
        for key in ("opus", "sonnet", "haiku", "gpt-6-astra", "kimi-k3", "deepseek-v4.1-flash", "fable"):
            self.assertIn(key, out)
        self.assertEqual(out["opus"]["via"], ["claude"])
        self.assertEqual(out["deepseek-v4.1-flash"]["via"], ["opencode", "cmd"])
        self.assertIsNotNone(out["opus"]["share"])
        self.assertIsNone(out["kimi-k3"]["share"])

    def test_price_tokens(self):
        row = {"input": 2, "output": 10, "cache_read": 0.2}
        self.assertEqual(fills.price({"input": 1_000_000, "output": 100_000, "cache_read": 500_000}, row), 3.1)
        self.assertIsNone(fills.price(None, row))
        self.assertIsNone(fills.price({"input": 5}, None))
        self.assertEqual(fills.price({"input": 1_000_000}, {"input": 1, "output": 2}), 1.0)

    def test_merge_other_adds_priced_runs(self):
        days = {"2026-10-14": {"cost": 5.0, "tokens": [1, 1, 1, 1], "projects": {}, "models": {"opus": 5.0}}}
        other = {"2026-10-14": {"gpt-6.1-sol": {"cost": 1.5, "runs": 1, "unknown": 0},
                                "deepseek-v4.1-flash": {"cost": 0, "runs": 2, "unknown": 2}},
                 "2026-10-12": {"gpt-6.1-sol": {"cost": 1.0, "runs": 1, "unknown": 0}}}
        out = fills.merge_other(days, other)
        self.assertEqual(out["2026-10-14"]["cost"], 6.5)
        self.assertEqual(out["2026-10-14"]["models"], {"opus": 5.0, "gpt-6.1-sol": 1.5})
        self.assertEqual(out["2026-10-14"]["unknown"], {"deepseek-v4.1-flash": 2})
        self.assertEqual(out["2026-10-12"]["cost"], 1.0)
        self.assertEqual(days["2026-10-14"]["models"], {"opus": 5.0})  # a copy


class BalanceTest(unittest.TestCase):
    THINK = [("opus", "auto"), ("codex:gpt-6-astra", "high"), ("opencode:opencode-go/kimi-k3", "auto")]

    def test_balance_takes_the_lowest_share(self):
        got = fills.balance(self.THINK, {"opus": at(0.84), "gpt-6-astra": at(0.31), "kimi-k3": at(0.5)}, CFG,
                            tier="think", now=NOW)
        self.assertEqual((got["rung"], got["effort"], got["share"]), ("codex:gpt-6-astra", "high", 0.31))
        self.assertEqual(got["note"], "balance: opus 84 % -> codex:gpt-6-astra 31 %")
        got = fills.balance(self.THINK, {"opus": at(0.2), "gpt-6-astra": at(0.31)}, CFG, tier="think", now=NOW)
        self.assertEqual((got["rung"], got["note"]), ("opus", "balance: opus 20 %"))

    def test_balance_keeps_the_previous_rung_within_margin(self):
        budget = {"opus": at(0.40), "gpt-6-astra": at(0.31), "kimi-k3": at(0.9)}
        got = fills.balance(self.THINK, budget, CFG, tier="think", prev_rung="opus", now=NOW)
        self.assertEqual(got["rung"], "opus")  # 0.40 - 0.31 = 0.09, within 0.1
        self.assertEqual(got["note"], "balance: opus 40 % (previous rung kept: codex:gpt-6-astra 31 % is within the margin)")
        budget["opus"] = at(0.45)
        self.assertEqual(fills.balance(self.THINK, budget, CFG, prev_rung="opus", now=NOW)["rung"], "codex:gpt-6-astra")

    def test_cache_bonus_only_while_warm(self):
        budget = {"opus": at(0.48), "gpt-6-astra": at(0.31)}
        warm = fills.balance(self.THINK, budget, CFG, prev_rung="opus", prev_age=60, now=NOW)
        cold = fills.balance(self.THINK, budget, CFG, prev_rung="opus", prev_age=900, now=NOW)
        self.assertEqual((warm["rung"], cold["rung"]), ("opus", "codex:gpt-6-astra"))  # 0.48 - 0.1 - 0.31 = 0.07

    def test_no_allowance_sorts_after(self):
        got = fills.balance(self.THINK, {"opus": at(0.95), "gpt-6-astra": at(None)}, CFG, tier="think", now=NOW)
        self.assertEqual(got["rung"], "opus")  # the only one with a share, even over pace
        got = fills.balance(self.THINK, {}, CFG, tier="think", now=NOW)
        self.assertEqual((got["rung"], got["note"]), ("opus", "balance: no allowance set -> opus (list order)"))
        self.assertEqual(fills.balance([("haiku", "auto")], {}, CFG, now=NOW)["note"], "balance: haiku only")
        self.assertEqual(fills.balance([], {}, CFG, now=NOW)["rung"], "")

    def test_every_rung_over_pace(self):
        got = fills.balance(self.THINK, {"opus": at(1.1), "gpt-6-astra": at(0.92), "kimi-k3": at(0.95)}, CFG,
                            tier="think", now=NOW)
        self.assertTrue(got["over"])
        self.assertEqual(got["note"], "balance: every think rung over pace -> codex:gpt-6-astra 92 %")

    def test_peak_hours_add_in_their_hours(self):
        cfg = dict(CFG, peak_hours={"anthropic": {"hours": "14-19", "add": 0.2}})
        self.assertEqual(fills.peak_add(cfg, "opus", NOW), 0.2)
        self.assertEqual(fills.peak_add(cfg, "codex:gpt-6-astra", NOW), 0.0)
        self.assertEqual(fills.peak_add(cfg, "opus", datetime(2026, 10, 14, 9).timestamp()), 0.0)
        self.assertEqual(fills.peak_add(dict(CFG, peak_hours={"anthropic": {"hours": "x"}}), "opus", NOW), 0.0)
        got = fills.balance(self.THINK, {"opus": at(0.25), "gpt-6-astra": at(0.31)}, cfg, now=NOW)
        self.assertEqual(got["rung"], "codex:gpt-6-astra")  # 0.25 + 0.2 > 0.31


class FailHoursTest(unittest.TestCase):
    def test_fail_hours_counts_the_writer_hour(self):
        at14 = datetime(2026, 10, 13, 14, 20).timestamp()
        old = NOW - 40 * 86400

        def task(model, started, verdict):
            return {"steps": [{"n": 1, "kind": "code", "model": model, "started": started},
                              {"n": 2, "kind": "verify", "checked": 1, "verdict": verdict, "model": "opus"}]}
        tasks = {"a": task("sonnet", at14, "FAIL"), "b": task("claude-sonnet-4-6", at14, "PASS"),
                 "c": task("codex:gpt-6.1-sol", at14, "FAIL"), "d": task("sonnet", old, "FAIL"),
                 "e": task("sonnet", at14, "")}
        out = fills.fail_hours(tasks, CFG, NOW)
        self.assertEqual((out["sonnet"]["runs"][14], out["sonnet"]["fails"][14]), (2, 1))
        self.assertEqual(sum(out["sonnet"]["runs"]), 2)  # the old one and the one without a verdict are left out
        self.assertEqual((out["gpt-6.1-sol"]["fails"][14], out["gpt-6.1-sol"]["via"]), (1, ["codex"]))


if __name__ == "__main__":
    unittest.main()
```

What each test asserts: `NamesTest` (3): the keys of README 3.2 (two CLIs, one fill; a Claude model through
OpenCode counts in its family), `split_rung` and `rank_of` from models.json, `tier_rungs` cleaning. `test_pool_*`
(2, in `NamesTest`'s file order): the write pool with and without `hard`, fable hard only in think, a refused rung
skipped, the check pools of exact rank with no opencode. `WindowsTest` (2): the three windows on a fixed local date,
a billing day of 20, a January wrap, 31 clamped to 28; the pace and its one-hour floor. `FillTest` (5): used, pace and
share per window and the binding one; no allowance gives no share; another harness's priced run counts and an
unpriced one makes the key unknown while today's window keeps its share; `fills` lists keys and `via`; `price`;
`merge_other`. `BalanceTest` (6): the lowest share and the two note forms, the margin keeps the previous rung (and
stops at 0.45), the cache bonus only while warm, no allowance sorts after and the list-order note, every rung over
pace, `peak_hours` in and out of its hours. `FailHoursTest` (1): FAIL counted on the writer's model at its start
hour; old ones and verdict-less ones left out; a codex row's `via`.

## 1.4 Steps

1. Write `tests/test_fills.py` as in 1.3; run `py -m unittest tests.test_fills`: ImportError.
2. Write `console/fills.py` as in 1.2; run: 20 OK.
3. Run the whole suite: the start count + 20.
4. Commit: `plan 18 task 1: console/fills.py, the fills and the balance pick (N tests OK)`.

## 1.5 Drift guards

- `fills.py` imports nothing from the package but `claude_cli`; no file, no thread, no clock but the `now` given
  (`balance` and `peak_add` read `time` only when `now` is None).
- Unknown stays `None` everywhere (`share`, `pace_usd`, `allowance_usd`, `price`); nothing turns it into 0.
- `NO_CHECK` is the only list of harnesses that never verify or fix; `pool(check=True)` reads it.
- Note strings are exactly README 3.6's table; the window and the chain log show them as written.
