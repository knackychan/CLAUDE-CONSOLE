# Task 2: The route: tiers, kind_tier and the balance step

> Contract: [README.md](README.md) 3.2, 3.4, 3.6, 3.8. Depends on Task 1. Decision D1 (`test_a_cheap_rung_runs_at_its_own_rank`).
> Run in a scratch copy on 2026-10-14: `tests/test_tasks.py` 74 OK (65 before, one test removed, ten added).
> Lands on: nothing of plans 5, 23 and 24 (plan 5 Task 5 leaves `tasks.py` alone; plan 24 Task 1 adds
> `RULES["replan"]` and `step_prompt`'s slots, plan 23 the prompt and headings: no line of `step_route`).

**Files**
- Modify: `console/tasks.py` (the import line, new `kind_tier`, `step_route` replaced whole)
- Modify: `console/paths.py` (`DEFAULTS`: `budget_warn_at`'s comment, `tiers`, `allowances`, `balance_margin`,
  `cache_bonus`, `month_start_day`, `peak_hours`)
- Modify: `tests/test_tasks.py` (remove `RulesTest.test_budget_pressure_moves_a_step_down`; add `BALANCE_CFG`,
  `shares`, class `BalanceRouteTest` at the end, before `if __name__`)

## 2.1 `console/tasks.py`

Replace the import line `from . import claude_cli, levers, redact, routing` with:

```python
from . import claude_cli, fills, levers, redact, routing
from .fills import RANK_TIER, TIER_RANK, TIERS  # plan 18: the job tiers (the contract names them here)
```

Replace `def step_route(...)` whole (from its `def` line to the blank lines before `# -- the handoff block`) with
`kind_tier` and the new `step_route`:

```python
def kind_tier(kind: str) -> str:
    """A kind's job tier: its rule's rank read as a tier (design think; code, document, explain, debug write; the
    rest read); "" for verify and fix, which the rule computes."""
    return RANK_TIER.get(RULES.get(kind, ("",))[0], "")


def step_route(kind: str, *, pick: str = "", checked=None, demand=None, misses=(), prev: str = "",
               budget=None, warn_at: float = 0.8, effort: str = "auto", cfg=None, prev_rung: str = "",
               prev_age=None, hard: bool = False, refuse=None, now: float = None) -> dict:
    """The route of one step: rule, pick, demand, floor, hint, cap, balance, fixed effort (README 3.5 of plan 17,
    step 7 rewritten by plan 18), in that order, each one appending a note. A pick keeps its model against the floor
    and the hint (they may still raise the effort) and is never balanced. `budget` is Hub.budget() (fills per model
    key); `cfg` gives the tiers, the balance keys and models.json; `refuse(rung)` a reason a rung cannot run now.
    Returns {"model": the rank of the rung, "rung", "effort", "notes", "hold"}; without `cfg` the rung is the rank
    alias (plan 17's behaviour). `hold` non-empty means the task waits for Fred."""
    efforts = claude_cli.EFFORTS
    fixed = effort != "auto"
    notes, hold, rung = [], "", ""
    if kind == "verify":
        model, level = verify_route(checked)
    elif kind == "fix":
        # with a fixed effort the effort cannot step up, so the model does
        model, level = (levers.escalate_step(checked[0], "high" if fixed else checked[1]) or checked)
    else:
        model, level = RULES[kind][:2]
    notes.append(f"rule {kind}: {model}/{level}")
    picked = (fills.rank_of(pick, cfg) if cfg is not None else claude_cli.model_alias(pick)) if pick else ""
    if picked:
        model = picked
        notes.append(f"pick: {pick if cfg is not None else picked}")
        why = refuse(pick) if refuse and cfg is not None else ""
        if why:
            notes.append(f"pick refused: {why} -> balance")
        else:
            rung = pick if cfg is not None else ""
    if (demand or {}).get("reasoning") == "high" and kind in ("code", "debug") \
            and efforts.index(level) < efforts.index("high"):
        level = "high"
        notes.append("demand: effort high")
    low = routing.floor(misses, kind)
    if low and routing.rank(low) > routing.rank((model, level)):
        if picked and low[0] != model:  # Fred's pick keeps its model (2026-10-13); the floor's effort still counts
            level = max(level, low[1], key=efforts.index)
            notes.append(f"floor {kind}: {low[0]}/{low[1]} -> pick {model}/{level} kept")
        else:
            model, level = low
            notes.append(f"floor {kind}: {model}/{level}")
    hint = next_hint(prev)
    if hint and routing.rank(hint) > routing.rank((model, level)):
        up = levers.escalate_step(model, level) or (model, level)
        if picked and up[0] != model:  # a model's hint never moves a step off the model Fred picked
            notes.append(f"hint: {hint[0]}/{hint[1]} -> pick {picked} kept")
        else:
            model, level = up
            notes.append(f"hint: {hint[0]}/{hint[1]} -> one step up")
    chosen = (model, level)
    if model == "fable" and picked != "fable" and not (checked and checked[0] == "fable"):
        model = "opus"  # code never routes a rank to fable; a hard-only fable rung of the think tier may (balance)
    if not fixed and model == "opus" and efforts.index(level) > efforts.index(_TOP[1]):
        level = _TOP[1]
    if (model, level) != chosen:
        notes.append(f"cap: {model}/{level}")
    share = None
    if cfg is not None and not rung:  # 7. balance (plan 18): the emptiest model of the tier, from the first step
        check = kind in ("verify", "fix")
        rungs = fills.pool(cfg, model, check=check, hard=hard and not check, refuse=refuse)
        tier = RANK_TIER.get(model, "")
        if rungs:
            pickd = fills.balance(rungs, budget or {}, cfg, tier=tier, prev_rung="" if check else prev_rung,
                                  prev_age=prev_age, now=now)
            rung, share = pickd["rung"], pickd["share"]
            notes.append(pickd["note"])
            if pickd["effort"] != "auto" and not fixed:
                level = pickd["effort"]
                notes.append(f"rung effort: {level}")
        else:
            rung = model
            notes.append(f"balance: no usable {tier} rung -> {model}")
        model = fills.rank_of(rung, cfg) or model
    elif cfg is not None:
        share = ((budget or {}).get(fills.model_key(rung, cfg)) or {}).get("share")
    if not rung:
        rung = model
    if kind == "verify" and cfg is not None and share is not None and share >= warn_at:
        hold = f"{fills.model_key(rung, cfg)} over its pace"
        notes.append(f"over pace: {rung} {round(share * 100)} % -> hold")
    if fixed:
        level = effort
        notes.append(f"fixed effort: {effort}")
    cap = EFFORT_CAP.get(model, efforts[-1])
    if efforts.index(level) > efforts.index(cap):
        level = cap
        notes.append(f"cap {model}: {cap}")
    return {"model": model, "rung": rung, "effort": level, "notes": notes, "hold": hold}
```

What changed against plan 17's function: the pick is read with `fills.rank_of(pick, cfg)` when `cfg` is given (a
rung on any harness; plan 5 Task 5's `pick=tier_of(pick, cfg)` in `_route_for` goes away in Task 4), its note names
the rung, and a refused pick balances; the old step 7 (one model down at one effort up) is gone; step 7 is the
balance; the effort cap now runs on every route (every `EFFORT_CAP` value is `max`, so no route changes). Without
`cfg` the function is plan 17's but for the budget step: every existing test but the one removed passes unchanged.

## 2.2 `console/paths.py` (`DEFAULTS`)

Replace the line `"budget_warn_at": 0.8,  # share of a model's pace at which a step moves one model down` with:

```python
    "budget_warn_at": 0.8,  # plan 18: share of pace that marks a model over pace and holds a verify on it
    # plan 18: the job tiers; each step takes the emptiest model of its tier (README 3.2 of plans/18-fills)
    "tiers": {
        "think": [{"rung": "opus", "effort": "auto"}, {"rung": "codex:gpt-6-astra", "effort": "auto"},
                  {"rung": "opencode:opencode-go/kimi-k3", "effort": "auto"},
                  {"rung": "opencode:opencode-go/glm-5.3", "effort": "auto"},
                  {"rung": "claude-opus-4-8", "effort": "auto"}, {"rung": "fable", "effort": "auto"}],
        "write": [{"rung": "sonnet", "effort": "auto"}, {"rung": "codex:gpt-6.1-sol", "effort": "auto"},
                  {"rung": "codex:gpt-6-sol", "effort": "auto"}, {"rung": "opus", "effort": "auto"},
                  {"rung": "opencode:opencode-go/deepseek-v4.1-flash", "effort": "auto"},
                  {"rung": "cmd:deepseek/deepseek-v4.1-flash", "effort": "auto"}],
        "read": [{"rung": "haiku", "effort": "auto"}, {"rung": "codex:gpt-6-luna", "effort": "auto"},
                 {"rung": "opencode:opencode-go/deepseek-v4.1-flash", "effort": "auto"},
                 {"rung": "cmd:deepseek/deepseek-v4.1-flash", "effort": "auto"}],
    },
    "allowances": {},  # model key -> {"day_usd", "week_usd", "month_usd"}; a key without one has no allowance
    "balance_margin": 0.1,  # the previous step's rung stays while its share is this close to the lowest
    "cache_bonus": 0.1,  # taken off the previous rung's share while its prompt cache is warm (5 minutes)
    "month_start_day": 1,  # the billing day the month window starts on (1 to 28)
    "peak_hours": {},  # provider -> {"hours": "14-19", "add": 0.2}; off
```

`D2` marks `"allowances": {}` (with D2 (b) the seeded numbers go there).

## 2.3 Tests (`tests/test_tasks.py`)

Remove `RulesTest.test_budget_pressure_moves_a_step_down` (it pinned the step 7 this plan replaces). Add at the end
of the file, before `if __name__ == "__main__":`:

```python
BALANCE_CFG = {  # plan 18: tiers over three harnesses (models.json shape of plan 5) and the balance keys
    "models": {"codex": {"gpt-6-astra": "opus", "gpt-6.1-sol": "sonnet"},
               "opencode": {"opencode-go/kimi-k3": "opus", "opencode-go/deepseek-v4.1-flash": "haiku"}},
    "tiers": {"think": [{"rung": "opus", "effort": "auto"}, {"rung": "codex:gpt-6-astra", "effort": "high"},
                        {"rung": "opencode:opencode-go/kimi-k3", "effort": "auto"}, {"rung": "fable", "effort": "auto"}],
              "write": [{"rung": "sonnet", "effort": "auto"}, {"rung": "codex:gpt-6.1-sol", "effort": "auto"},
                        {"rung": "opus", "effort": "auto"},
                        {"rung": "opencode:opencode-go/deepseek-v4.1-flash", "effort": "auto"}],
              "read": [{"rung": "haiku", "effort": "auto"}]},
    "balance_margin": 0.1, "cache_bonus": 0.1, "budget_warn_at": 0.8, "peak_hours": {},
}


def shares(by_key):
    """A Hub.budget() reduced to what step_route reads: the share per model key."""
    return {key: {"share": share} for key, share in by_key.items()}


class BalanceRouteTest(unittest.TestCase):
    """Plan 18: step 7 of step_route is the balance over the tier's rungs."""

    def route(self, kind, **kw):
        return tasks.step_route(kind, cfg=BALANCE_CFG, warn_at=0.8, **kw)

    def test_tier_names(self):
        self.assertEqual(tasks.TIERS, ("read", "write", "think"))
        self.assertEqual(tasks.TIER_RANK, {"read": "haiku", "write": "sonnet", "think": "opus"})
        self.assertEqual(tasks.RANK_TIER, {"haiku": "read", "sonnet": "write", "opus": "think", "fable": "think"})
        self.assertEqual({k: tasks.kind_tier(k) for k in ("design", "code", "explain", "scout", "test", "verify")},
                         {"design": "think", "code": "write", "explain": "write", "scout": "read", "test": "read",
                          "verify": ""})

    def test_without_cfg_the_rung_is_the_rank(self):
        route = tasks.step_route("code", budget=shares({"sonnet": 0.99}))
        self.assertEqual((route["model"], route["rung"], route["hold"]), ("sonnet", "sonnet", ""))
        self.assertEqual(route["notes"], ["rule code: sonnet/medium"])

    def test_balance_spreads_a_tier(self):
        route = self.route("code", budget=shares({"sonnet": 0.84, "gpt-6.1-sol": 0.31, "deepseek-v4.1-flash": 0.5}))
        self.assertEqual((route["model"], route["rung"], route["effort"]), ("sonnet", "codex:gpt-6.1-sol", "medium"))
        self.assertIn("balance: sonnet 84 % -> codex:gpt-6.1-sol 31 %", route["notes"])
        route = self.route("code", budget=shares({"sonnet": 0.2, "gpt-6.1-sol": 0.31}))
        self.assertEqual(route["rung"], "sonnet")
        self.assertEqual(route["notes"][-1], "balance: sonnet 20 %")

    def test_a_cheap_rung_runs_at_its_own_rank(self):
        route = self.route("code", budget=shares({"sonnet": 0.6, "gpt-6.1-sol": 0.5, "deepseek-v4.1-flash": 0.1}))
        self.assertEqual((route["model"], route["rung"]), ("haiku", "opencode:opencode-go/deepseek-v4.1-flash"))

    def test_hard_only_rungs_need_a_hard_step(self):
        budget = shares({"sonnet": 0.6, "gpt-6.1-sol": 0.5, "opus": 0.05, "deepseek-v4.1-flash": 0.4})
        self.assertEqual(self.route("code", budget=budget)["rung"], "opencode:opencode-go/deepseek-v4.1-flash")
        route = self.route("code", budget=budget, hard=True)
        self.assertEqual((route["model"], route["rung"]), ("opus", "opus"))
        route = self.route("design", budget=shares({"opus": 0.5, "gpt-6-astra": 0.6, "kimi-k3": 0.7, "fable": 0.1}))
        self.assertEqual(route["rung"], "opus")  # fable is hard only in think
        route = self.route("design", budget=shares({"opus": 0.5, "gpt-6-astra": 0.6, "kimi-k3": 0.7, "fable": 0.1}), hard=True)
        self.assertEqual((route["model"], route["rung"]), ("fable", "fable"))

    def test_rung_effort_is_used_unless_the_task_fixes_one(self):
        budget = shares({"opus": 0.9, "gpt-6-astra": 0.2, "kimi-k3": 0.95})
        route = self.route("design", budget=budget)
        self.assertEqual((route["rung"], route["effort"]), ("codex:gpt-6-astra", "high"))
        self.assertIn("rung effort: high", route["notes"])
        route = self.route("design", budget=budget, effort="max")
        self.assertEqual((route["rung"], route["effort"]), ("codex:gpt-6-astra", "max"))
        self.assertNotIn("rung effort: high", route["notes"])

    def test_previous_rung_kept_within_margin(self):
        budget = shares({"sonnet": 0.4, "gpt-6.1-sol": 0.31, "deepseek-v4.1-flash": 0.9})
        self.assertEqual(self.route("code", budget=budget)["rung"], "codex:gpt-6.1-sol")
        self.assertEqual(self.route("code", budget=budget, prev_rung="sonnet")["rung"], "sonnet")
        budget = shares({"sonnet": 0.48, "gpt-6.1-sol": 0.31, "deepseek-v4.1-flash": 0.9})
        self.assertEqual(self.route("code", budget=budget, prev_rung="sonnet", prev_age=900)["rung"], "codex:gpt-6.1-sol")
        self.assertEqual(self.route("code", budget=budget, prev_rung="sonnet", prev_age=30)["rung"], "sonnet")

    def test_verify_balances_one_rank_above_and_holds_over_pace(self):
        route = self.route("verify", checked=("sonnet", "medium"), budget=shares({"opus": 0.9, "gpt-6-astra": 0.3, "kimi-k3": 0.0}))
        self.assertEqual((route["model"], route["rung"], route["hold"]), ("opus", "codex:gpt-6-astra", ""))
        route = self.route("verify", checked=("sonnet", "medium"), budget=shares({"opus": 0.9, "gpt-6-astra": 0.95}))
        self.assertEqual((route["rung"], route["hold"]), ("opus", "opus over its pace"))
        self.assertIn("balance: every think rung over pace -> opus 90 %", route["notes"])
        self.assertIn("over pace: opus 90 % -> hold", route["notes"])
        route = self.route("verify", checked=("haiku", "low"), budget=shares({"sonnet": 0.5, "gpt-6.1-sol": 0.1}))
        self.assertEqual((route["model"], route["rung"]), ("sonnet", "codex:gpt-6.1-sol"))  # never deepseek
        route = self.route("fix", checked=("sonnet", "high"), budget=shares({"opus": 0.5, "kimi-k3": 0.0}))
        self.assertEqual(route["rung"], "opus")  # never opencode

    def test_off_rungs_are_skipped(self):
        off = lambda rung: "codex is off" if rung.startswith("codex:") else ""
        route = self.route("code", budget=shares({"sonnet": 0.84, "gpt-6.1-sol": 0.31}), refuse=off)
        self.assertEqual(route["rung"], "sonnet")
        route = self.route("scout", refuse=lambda rung: "off")
        self.assertEqual((route["rung"], route["notes"][-1]), ("haiku", "balance: no usable read rung -> haiku"))

    def test_pick_runs_as_given_and_a_refused_pick_balances(self):
        route = self.route("code", pick="codex:gpt-6.1-sol", budget=shares({"sonnet": 0.1, "gpt-6.1-sol": 0.9}))
        self.assertEqual((route["model"], route["rung"]), ("sonnet", "codex:gpt-6.1-sol"))
        self.assertFalse(any(n.startswith("balance:") for n in route["notes"]))
        off = lambda rung: "codex is off" if rung.startswith("codex:") else ""
        route = self.route("code", pick="codex:gpt-6.1-sol", refuse=off)
        self.assertEqual((route["model"], route["rung"]), ("sonnet", "sonnet"))
        self.assertIn("pick refused: codex is off -> balance", route["notes"])
        route = self.route("design", pick="opencode:opencode-go/kimi-k3")
        self.assertEqual((route["model"], route["rung"], route["notes"][1]),
                         ("opus", "opencode:opencode-go/kimi-k3", "pick: opencode:opencode-go/kimi-k3"))


```

What each asserts: `test_tier_names` the three constants and `kind_tier`; `test_without_cfg_the_rung_is_the_rank`
plan 17's behaviour without `cfg` (no balance note, a budget ignored); `test_balance_spreads_a_tier` the emptiest
write rung and the two note forms; `test_a_cheap_rung_runs_at_its_own_rank` (D1 a) a haiku-rank rung in write wins
and the route's `model` is `haiku`; `test_hard_only_rungs_need_a_hard_step` opus in write and fable in think only
with `hard`; `test_rung_effort_is_used_unless_the_task_fixes_one`; `test_previous_rung_kept_within_margin` the margin
and the warm bonus through `step_route`; `test_verify_balances_one_rank_above_and_holds_over_pace` the verify pool of
exact rank, the hold and its notes, a cheap rung's code verified on sonnet, a fix never on opencode;
`test_off_rungs_are_skipped` a refused rung skipped and the no-usable-rung note; `test_pick_runs_as_given_and_a_refused_pick_balances`.

## 2.4 Steps

1. Remove the old test, add `BALANCE_CFG`, `shares` and `BalanceRouteTest`; run `py -m unittest tests.test_tasks`:
   the new class fails (`kind_tier` missing, unexpected keyword `cfg`).
2. `tasks.py` and `paths.py` as above; run: 74 OK on the plan 17 file (plus whatever plans 24 and 23 added to it).
3. The whole suite: `tests/test_server.py`'s four budget tests now fail (they mock the old `Hub.budget` shape, which
   Task 4 replaces): `test_budget_hold_waits_for_fred`, `test_budget_hold_released_by_confirm`,
   `test_counts_a_held_task_as_needs`, `test_rung_under_budget_pressure`. Put
   `@unittest.skip("plan 18 Task 4 rewrites it")` on each of the four; Task 4 removes the four decorators. The suite is
   green with 4 skipped more.
4. Commit: `plan 18 task 2: step_route balances inside the tier; tiers and fills keys in config (N tests OK)`.

## 2.5 Drift guards

- `step_route` stays pure: the fills, the config and the gate come in as arguments; no `Hub`, no file.
- The rule table, the floor, the hint and the cap keep plan 17's order and notes; only step 7 is new.
- A pick is never balanced; `budget_warn_at` holds only a verify.
- `TIERS`, `TIER_RANK`, `RANK_TIER` live in `fills` and are imported by `tasks`; nothing defines them twice.
