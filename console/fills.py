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
