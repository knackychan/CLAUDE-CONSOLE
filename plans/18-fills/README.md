# Plan 18: Tiers, usage fills and balancing. Guided implementation plan

> Design: [../../design/brainstorm/2026-10-13-orchestration.md](../../design/brainstorm/2026-10-13-orchestration.md)
> section 4 (D-4: the tiers think / write / read with rungs on any harness, a usage fill per model over the day, the
> week and the month, balancing as a spread from the first step with `balance_margin` hysteresis, the warm-cache
> bonus of 5.1 item 2, hard-only stronger models, Fable in think for hard design only, verify one rank above,
> `warn_at` only marks and holds a verify, `peak_hours` optional and off, the verify FAIL rate per rung per hour) and
> section 9 row 18; D-3 (unknown is never zero). The interface doc
> [../../design/brainstorm/2026-10-13-interface.md](../../design/brainstorm/2026-10-13-interface.md) sections 3 (the
> today strip's fills line), 5 (model selects with the tier groups), 9 (Usage page: Models share of pace, one bar of
> 20 cells for the binding window, Verify FAIL by hour), 10, 11 and 12 (ID-6). Mock:
> [../../design/rework/locked/cells-board.html](../../design/rework/locked/cells-board.html), `listHtml` (the
> `.overpace` line, `.todaymore`, `.fline`) and `usageHtml` (`.mfill`, `.heat`). Contracts this plan changes:
> [../17-task-folders.md](../17-task-folders.md) 4.8 and [../17-tasks/README.md](../17-tasks/README.md) 3.5 step 7
> and 3.8 (`Hub.budget`, `Hub.model_id`, `budget_warn_at`); [../05-harnesses/README.md](../05-harnesses/README.md)
> (ranks, rungs, models.json 3.2b, decision 11, `run_ended.tokens` kept "so plan 18 can count them"). Fred,
> 2026-10-14 (project memory): spread work across models from the first step (the lowest fill against pace within
> the tier wins, the 10-point margin allows repeats), never fill one model to 80 % and then move; 80 % only flags
> over pace; verify runs one tier above the writer; non-Claude cost is usage x a price row keyed by model key, an
> unpriced run counts as unknown, never zero. Cross-plan names: the thread lead's contract of 2026-10-14 (ranks,
> tiers, fills). Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
>
> Build order: 5 -> 24 -> 23 -> 18 -> 26 -> 25. Start state: plans 5, 24 and 23 placed. Where a task edits a function
> one of them also edits, its file says so in a "Lands on" line.

**Placed 2026-10-14** on branch `claude/implement-orchestration-plans-1y4bic` (PR #1): every code task, tests first where the task says, one commit per task; open decisions as (a). Fred's live check and the close task are open.

Status: written 2026-10-14. Tasks 1 to 4 were run in a scratch copy of today's tree (plan 22 placed, plan 5 not
placed: `Hub.rung_ok` was a two-line shim over `claude_cli.known_model`): `console/fills.py` with
`tests/test_fills.py` 20 OK, `tests/test_tasks.py` 74 OK (65 - 1 + 10), `tests/test_usage.py` 4 new OK, the service
changes with `tests/test_server.py` 87 OK (84 - 1 + 4 in `TaskServerTest`); the full suite on Linux 362 run, only
the four failures that fail on this box without the plan (`test_tray` import, `test_redact` path,
`test_usage` local day, `test_window` place). Task 4's `PlanFiveTest` needs plan 5's `harness` module and was not
run. Task 5's `web/app.js` passed `node --check` and its Usage functions rendered in node over seeded fills; no
browser on that box, so the headless check is the executor's. The final code is in the task files; the whole plan
adds 37 tests (fills 21, tasks 9 net, usage 4, server 3 net). Open decisions D1 to D3 (section 2): the plan is written for
(a) on each; the task files' `D1` / `D2` / `D3` marks name the lines that would change otherwise.

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-fills-module.md](01-fills-module.md) | `console/fills.py` (model keys, ranks, the tiers' rungs and pools, windows and pace, the fills, prices, the balance pick, `peak_hours`, the FAIL-by-hour counts), `tests/test_fills.py` | nothing |
| 2 | [02-route.md](02-route.md) | `tasks.TIERS`, `TIER_RANK`, `RANK_TIER`, `kind_tier`; `tasks.step_route` with step 7 the balance (the final signature), the config keys of 3.4 in `paths.DEFAULTS`; `tests/test_tasks.py` | 1 |
| 3 | [03-usage-store.md](03-usage-store.md) | `usage.load_other`, `usage.add_other`, `usage.FILE_LOCK`; `save_days` keeps every other key of usage-days.json; `tests/test_usage.py` | nothing |
| 4 | [04-service.md](04-service.md) | `Hub.budget` (the fills), `Hub.tier_view`, `Hub.count_run`, `Hub.fill_marks`; `_route_for`, `start_step` (the rung from the route, the Fable confirm on a balanced fable), `_brief_job` (the step's rung); `Hub.tier_budget` and `Hub.model_id` removed; `/api/config` `tiers` and `kinds_tier`; `/api/usage` `fills`, `fail_hours`; the snapshot's `spend.fills`; `tests/test_server.py` | 1, 2, 3 |
| 5 | [05-window.md](05-window.md) | `modelOptions` with the tier groups, the today strip's over-pace line and fills line, the Usage page's Models share of pace and Verify FAIL by hour, the day's unknown runs; `web/index.html` `#overpace`; `web/style.css` | 4 |
| 6 | [06-live-check.md](06-live-check.md) | Fred's live check | 5 |
| 7 | [07-close.md](07-close.md) | PLAN.md row and History, the design docs, the 17 README pointers, this folder's state | 6 |

Tasks 1 to 4 are Python, tests first; each ends with its own commit. Task 5 is browser code (`node --check
web/app.js`, the full suite, headless Chromium at 400 and 340 px). Task 6 is Fred's: Claude never starts a run.
Other chats edit `web/app.js`, `PLAN.md` and the design docs in parallel: anchored edits only, stage only this
plan's lines.

## 2. Decisions

Taken, with their source (not reopened here):

| # | Decision | Source |
|---|---|---|
| 1 | Job tiers `read`, `write`, `think`; a rung on any harness; the order breaks ties and routes while usage is unknown; rungs of a harness that is off or not found are skipped and hidden, never deleted | D-4, D-8; the lead's contract |
| 2 | One fill per model, not per harness: `fills.model_key` | D-4, brainstorm 6 item 3 |
| 3 | Three windows (day, week from Monday, month from `month_start_day`), linear pace, the highest share binds | D-4, ID-6 |
| 4 | Balance: the lowest share of pace wins inside the tier from the first step; the previous step's rung stays while it is within `balance_margin` (0.1), less `cache_bonus` (0.1) while its cache is warm (5 minutes) | Fred 2026-10-14, brainstorm 5.1 item 2 |
| 5 | A rung ranked above its tier (opus in write, fable in think) runs only on a hard step: `demand.reasoning == "high"` or a sub-plan part marked hard (plan 24) | Fred 2026-10-14 |
| 6 | `budget_warn_at` 0.8 marks over pace (the today line, the Usage bar) and holds a verify whose rung is over it; it never moves a step. A verify whose pool is empty still holds when its own rung is over `budget_warn_at` (plan 27 Task 3). | Fred 2026-10-14 |
| 7 | Verify: one rank above the rung that wrote the step, never opencode or cmd; fix: the failed step's escalated rank (plan 17's rule), never opencode or cmd | plan 17, plan 5 decision 11, Fred 2026-10-14 |
| 8 | Cost of a non-Claude run: its reported cost, else its tokens x the price row in `prices` keyed by model key, else one unknown run; never zero | D-3, Fred 2026-10-14 |
| 9 | `peak_hours` exists and is off (`{}`); the FAIL-by-hour view is the evidence that would turn it on | D-4 |
| 10 | A Fred pick (Prep card, step row) runs as given and is never balanced; a picked rung that cannot run (harness off) balances inside its rank with the note `pick refused: <reason> -> balance` | plan 5 decision 12, plan 17 3.5 |

Open: where the docs do not decide a point, the plan is written for the recommended option.

| # | Question | Options | Plan written for |
|---|---|---|---|
| D1 | A rung ranked below its tier (a cheap `haiku`-rank model Fred placed in `write`, as D-2 of 2026-10-14 does with DeepSeek Flash): does it join the spread? Section 4 says "the spread mixes only rungs whose model ranks at the tier", which read literally leaves the cheap write rungs out | (a) yes: a rung Fred placed in a tier joins its spread; when it wins, the step runs at the rung's own rank, so its verify is one rank above it (sonnet), as plan 5 decision 11 says; (b) no: only rungs at the tier's rank spread, a weaker one runs only when picked | (a) |
| D2 | Default `allowances` | (a) `{}`: no allowance, so every bar is dotted and the tiers' order routes (today's behaviour) until Fred writes his numbers in config.json (or plan 26's Tuning tab); (b) seeded numbers per model | (a) |
| D3 | A key whose month holds an unpriced run (a Codex model with no price row yet) | (a) its share is unknown (`None`): it sorts after the rungs that have one and the Usage row says `cost unknown · n runs`; (b) its share counts the priced runs only, with the unknown count beside it | (a) |

A different answer changes only the lines the task files mark `D1`, `D2` or `D3`.

## 3. The contract

### 3.1 Files

```
console/fills.py          the fills and the balance pick (Task 1), pure: no threads, no files, no HTTP
console/tasks.py          TIERS, TIER_RANK, RANK_TIER (re-exported from fills), kind_tier, step_route (Task 2)
console/usage.py          load_other, add_other, FILE_LOCK; save_days keeps the other keys (Task 3)
console/server.py         Hub.budget, tier_view, count_run, fill_marks, _route_for, start_step, _brief_job (Task 4)
~/.claude/console/usage-days.json   gains "other" and "seen" next to "days" (3.5); nothing new on disk
```

### 3.2 Names (the lead's contract, kept exactly)

- Rank: a Claude alias `haiku` < `sonnet` < `opus` < `fable` (`claude_cli.MODELS` order). `fills.rank_of(rung, cfg)`:
  a Claude rung by its name (`claude_cli.model_alias`), any other from models.json (`cfg["models"][harness][model]`,
  plan 5 3.2b); `""` when unknown. Equal to plan 5's `claude_cli.tier_of(rung, cfg)` on every listed rung (Task 4's
  drift test).
- `tasks.TIERS = ("read", "write", "think")`, `tasks.TIER_RANK = {"read": "haiku", "write": "sonnet", "think": "opus"}`,
  `tasks.RANK_TIER = {"haiku": "read", "sonnet": "write", "opus": "think", "fable": "think"}` (defined in `fills`,
  imported by `tasks`). `tasks.kind_tier(kind) = RANK_TIER[RULES[kind][0]]`, `""` for verify and fix.
- `fills.model_key(rung, cfg=None)`: a Claude rung -> its family alias; any other -> the model id after its last `/`,
  except that a Claude family name in that id gives the family (`opencode:openrouter/anthropic/claude-sonnet-4-6`
  -> `sonnet`): one model through two CLIs is one fill.
- `fills.split_rung(rung)`: plan 5's `split_rung`, duplicated so `fills` runs before and after plan 5
  (`fills.HARNESSES == harness.NAMES`, Task 4's drift test).
- Hard only: `fills.hard_only(rung, tier, cfg)` when the rung's rank is above `TIER_RANK[tier]`.

### 3.3 `Hub.budget()` (the fills)

```json
{"opus": {"day":   {"used_usd": 5.0, "allowance_usd": 10.0, "pace_usd": 6.25, "share": 0.8, "unknown_runs": 0},
          "week":  {"used_usd": 15.0, "allowance_usd": 50.0, "pace_usd": 18.39, "share": 0.8156, "unknown_runs": 0},
          "month": {"used_usd": 35.0, "allowance_usd": 150.0, "pace_usd": 64.11, "share": 0.5459, "unknown_runs": 0},
          "binding": "week", "share": 0.8156, "unknown_runs": 0, "via": ["claude"]},
 "kimi-k3": {"day": {"used_usd": 0.0, "allowance_usd": null, "pace_usd": null, "share": null, "unknown_runs": 2},
             "...": "...", "binding": "", "share": null, "unknown_runs": 2, "via": ["opencode"]}}
```

- Keys: every key of `allowances`, the model key of every rung of `tiers`, every Claude family in the kept days,
  every key of the other harnesses' runs (`fills.keys_of`).
- Used: the Claude transcripts' cost per family per day (`usage_days[d]["models"]`, today's scan included) plus the
  other harnesses' priced runs (`usage_other[d][key]["cost"]`), over the window's days up to today.
- Pace: `allowance x max(elapsed, 1 hour) / window length`, capped at the allowance. Window share: used / pace,
  rounded to 4 places; `None` without that window's allowance.
- `binding` and `share`: the window with the highest share; `""` and `None` when no window has an allowance, and
  (D3 a) when the month holds an unpriced run. `unknown_runs`: the month's. `via`: the harnesses whose tier rungs
  reach the key (`["claude"]` for a Claude family no tier lists).
- `{}` until the history thread has read the transcripts once (`usage_ready`): while usage is unknown the order
  routes, never a guess of zero.

### 3.4 Config keys (`paths.DEFAULTS`)

| Key | Default | Meaning |
|---|---|---|
| `tiers` | 3.4a | the job tiers' rungs, in order |
| `allowances` | `{}` (D2 a) | `{key: {"day_usd", "week_usd", "month_usd"}}`; a key without an entry has no allowance (dotted bar, sorts after) |
| `balance_margin` | 0.1 | the previous step's rung stays while its share is within this of the lowest |
| `cache_bonus` | 0.1 | taken off the previous rung's share while it ran under 300 s ago |
| `budget_warn_at` | 0.8 (exists) | meaning changes: marks over pace and holds a verify on a rung over it; never moves a step |
| `month_start_day` | 1 | the billing day the month window starts on (1 to 28; 29 to 31 clamp to 28) |
| `peak_hours` | `{}` | `{provider: {"hours": "14-19", "add": 0.2}}`, provider `anthropic` (any Claude family), `openai` (codex), `opencode`, `cmd`; off |
| `prices` | as today | gains rows keyed by model key for other harnesses (Fred adds them, Task 6); a key with no row is unpriced |

3.4a `tiers` default (from the brainstorm and the mock's Tiers tab; every `effort` `"auto"`):

```text
think: opus, codex:gpt-6-astra, opencode:opencode-go/kimi-k3, opencode:opencode-go/glm-5.3, claude-opus-4-8, fable
write: sonnet, codex:gpt-6.1-sol, codex:gpt-6-sol, opus, opencode:opencode-go/deepseek-v4.1-flash,
       cmd:deepseek/deepseek-v4.1-flash
read:  haiku, codex:gpt-6-luna, opencode:opencode-go/deepseek-v4.1-flash, cmd:deepseek/deepseek-v4.1-flash
```

Each entry is `{"rung": str, "effort": "auto" | one of claude_cli.EFFORTS}`; a bare string reads as
`{"rung": s, "effort": "auto"}`. `paths.load_config` merges `tiers` one level deep as it merges every dict, so a
tier Fred writes replaces that tier's default list whole. `ladder` stays (plan 5 builds it from models.json): it
feeds the window's Claude rungs and `known_model`, not the route.

### 3.5 usage-days.json

```json
{"days": {"2026-10-13": {"cost": 9.1, "tokens": [1, 2, 3, 4], "projects": {}, "models": {"opus": 6.0}}},
 "other": {"2026-10-14": {"gpt-6.1-sol": {"cost": 0.75, "runs": 2, "unknown": 0, "tokens": [2000, 400, 1000]}}},
 "seen": {"2026-10-14": ["<session id>@<run_ended ts>"]}}
```

- `other` is written by `usage.add_other` (Task 3) when the service reads a `run_ended` line of a non-Claude run
  (`Hub.count_run`, Task 4); kept for good, like `days`. `seen` holds the counted run ids of the last 3 days (the
  event reader replays the last two daily files at start), so a restart counts nothing twice.
- `save_days` keeps every key it does not own; both writers hold `usage.FILE_LOCK`.
- An unreadable file is never overwritten: it is copied once to `usage-days.json.bad` and the write is skipped (plan 27 Task 3).

### 3.6 `tasks.step_route` (the final signature)

```python
def step_route(kind: str, *, pick: str = "", checked=None, demand=None, misses=(), prev: str = "",
               budget=None, warn_at: float = 0.8, effort: str = "auto", cfg=None, prev_rung: str = "",
               prev_age=None, hard: bool = False, refuse=None, now: float = None) -> dict
```

Returns `{"model": <rank of the rung>, "rung": <the rung to run>, "effort", "notes", "hold"}`. Steps, each with its
note: 1 rule, 2 pick (`pick: <rung>`; a pick `refuse` refuses adds `pick refused: <reason> -> balance`), 3 demand,
4 floor, 5 hint, 6 cap, 7 **balance** (new), 8 fixed effort. Without `cfg` the rung is the rank alias and step 7
does nothing: plan 17's tests keep passing unchanged.

Step 7: a pick that can run is used as given. Else `fills.pool(cfg, rank, check=kind in (verify, fix), hard=hard,
refuse=refuse)` gives the rungs (empty: the rank alias, note `balance: no usable <tier> rung -> <rank>`), and
`fills.balance(...)` picks one. A rung's pinned effort replaces the auto effort (`rung effort: <level>`), unless the
task has a fixed effort. A verify whose rung's share is at or over `warn_at` holds: `hold = "<key> over its pace"`,
note `over pace: <rung> 90 % -> hold`.

Balance notes (`fills.balance`), exactly:

| Case | Note |
|---|---|
| one rung | `balance: opus only` |
| no rung has a share | `balance: no allowance set -> opus (list order)` |
| every rung has a share at or over `budget_warn_at` | `balance: every think rung over pace -> codex:gpt-6-astra 92 %` |
| the tier's first rung is the lowest | `balance: opus 20 %` |
| another rung is lower | `balance: opus 84 % -> codex:gpt-6-astra 31 %` (the first rung, then the chosen one; `no allowance` for a rung without a share) |
| the previous rung kept within the margin | the note above, then ` (previous rung kept: codex:gpt-6-astra 31 % is within the margin)` |
| `peak_hours` added to the chosen rung | then ` (peak anthropic +20)` |

### 3.7 Routes and snapshot

- `GET /api/config` gains `tiers: {tier: [{"rung", "effort", "rank", "key", "hard", "why"}]}` (every entry as
  config.json lists it; `why` is `Hub.rung_ok(rung)`, `""` when it can run) and `kinds_tier: {kind: tier}` for
  `tasks.PREP_KINDS`.
- `GET /api/usage` gains `fills` (`Hub.budget()`), `fail_hours` (`{key: {"runs": [24], "fails": [24], "via": [...]}}`),
  `warn_at`, `balance_margin`; its `days` carry the other harnesses' priced cost in `cost` and `models` and
  `unknown: {key: runs}` (`fills.merge_other`).
- The snapshot's `spend` gains `fills: {"over": [[key, share, binding]], "unknown": [[key, runs]], "warn_at"}`
  (over pace first by share); its `today` and `models` count the other harnesses' priced runs of today.
- `task_levers` `next_route` reads `<rung>/<effort>`.

### 3.8 Hard rules

- `fills.py` is pure; only `usage.py` writes usage-days.json; only `Hub.count_run` calls `usage.add_other`.
- Unknown is never zero: a run with no cost and no priced tokens is an unknown run; a key with an unknown run in its
  month has no share (D3 a); `Hub.budget()` is `{}` until usage was read.
- `budget_warn_at` never moves a step; only a verify holds on it. A Fred pick is never balanced.
- verify and fix never run on `opencode` or `cmd` (`fills.NO_CHECK`), whatever the tiers say.
- A balanced `fable` rung waits for the Fable confirm (`confirm Fable`) as a picked one does.
- Rungs of a harness that is off or not found never route (`refuse`) and never show (`why`); config.json keeps them.
- No emojis or em-dashes in any note or window text.

### 3.9 Drift guards

- `Hub.tier_budget` and `Hub.model_id` are gone: grep finds neither. `tasks.step_route` is the only place a rung is
  chosen for a task step; `Hub.start_step` runs `route["rung"]` as given.
- `s["tier"]` is the rank of the rung that ran (`route["model"]`), so `tasks.checked_route` gives verify the right
  rank with no change there (a cheap rung's step is verified on sonnet).
- The older Claude rungs (`claude-opus-4-8`) share their family's fill (`model_key`): the order puts the alias
  first, so they run when Fred picks them or the alias cannot run.
- `fills.HARNESSES == harness.NAMES` and `fills.rank_of == claude_cli.tier_of` on models.json's rungs (Task 4 test).

### 3.10 Not in this plan

- The median cost per model on the Prep card (plan 17 4.8, PLAN.md row 18's old text): not in D-4 or the interface
  doc; a later small plan if Fred asks.
- Balancing the one-session Run: it runs Prep's pick (the brainstorm balances task steps in `step_route`).
- Editing tiers and allowances in the window: plan 26 (Models and tuning page).

## 4. Verification at the end of every task

- `py -m unittest discover -s tests` all OK (Windows); the count is written in the task's commit message.
- Tasks 1 and 3: the new tests fail as written before the code and pass after it.
- Task 4: `tests/test_server.py` runs the chain through the fake claude with a mocked `Hub.budget` (the spread, the
  hold, the Fable confirm) and a real one over `usage_days` and a codex run meta (counted once, unknown never zero).
- Task 5: `node --check web/app.js`; headless Chromium at 400 and 340 px with the fake claude and a seeded
  usage-days.json: the over-pace line, the breakdown's fills line, the Usage page's rows (open and closed), the
  dotted rows, the heatmap fold; no console errors, no horizontal overflow.
- Task 6: Fred's live run (06-live-check.md).
