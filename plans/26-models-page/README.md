# Plan 26: Models and tuning page. Guided implementation plan

> Design: the interface doc [../../design/brainstorm/2026-10-13-interface.md](../../design/brainstorm/2026-10-13-interface.md)
> section 9b (Fred, 2026-10-14: a compact page opened from the Settings band's `Models and tuning ›` link; tabs Kinds,
> Tiers, Tuning, each with `n edited`; kinds pinned to a rung and an effort, both `auto` by default; the tiers' rungs in
> order with hidden CLIs counted; the console's own passes; the numbers with their defaults, the blue edge, `reset`
> and the range in red; Save posts the changed keys only, the service writes config.json and reloads them, no rebuild,
> no restart; a `?` on every card head), section 4 (the Settings band) and section 11 (row "Models and tuning"). Mock:
> [../../design/rework/locked/cells-board.html](../../design/rework/locked/cells-board.html), `modelsHtml` and its CSS
> (lines 605 to 651), the Settings band's `Models and tuning ›` link (line 1327). Plan 24
> [../24-plan-and-replan/04-window.md](../24-plan-and-replan/04-window.md) 4.4 (the `Turns on design` row reads
> `design_max_turns`, D2 a); plan 5 [../05-harnesses/README.md](../05-harnesses/README.md) 3.2b (models.json, edited by
> hand, never by the page) and decision 11 (opencode and cmd never on verify or fix; their cheap models only on read
> and write); plan 18 [../18-fills/README.md](../18-fills/README.md) 3.4 and 3.6 (`tiers`, `allowances`, the balance
> keys, `step_route`'s final signature). Cross-plan names: the thread lead's contract of 2026-10-14 ("Kinds and
> tuning", owned by this plan). Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
>
> Build order: 5 -> 24 -> 23 -> 18 -> 26 -> 25. Start state: plans 5, 24, 23 and 18 placed. Where a task edits a
> function one of them also edits, its file says so in a "Lands on" line.

**Placed 2026-10-14** on branch `claude/implement-orchestration-plans-1y4bic` (PR #1): every code task, tests first where the task says, one commit per task; open decisions as (a). Fred's live check and the close task are open.

Status: written 2026-10-14. Tasks 1 to 3 were run in a scratch copy of today's tree with plan 18's Tasks 1 to 5
applied first (plans 5, 23 and 24 not placed: their config keys `step_timeout_s`, `read_max_turns`,
`design_max_turns`, `plan_max_kb`, `plan_max_parts`, `plan_hold`, `replan_auto` were added to that copy's
`paths.DEFAULTS` by hand, and plan 18's two-line `Hub.rung_ok` shim stood in for plan 5's): `tests/test_tuning.py` 13
OK, `tests/test_tasks.py` 80 OK (plan 18's 74 + 6), `tests/test_server.py` 90 OK (plan 18's 87 + 3); the full suite
on Linux 384 run (plan 18's 362 + 22), only the four failures of this box. Task 4's `web/app.js` passed
`node --check`, and its three tabs rendered in node over a real `/api/config` answer of that copy (a pinned codex
rung shown hidden, a hard-only rung, the hidden count, `Turns on design`, a value out of range, the change and
`n edited` counts); no browser on that box, so the headless check is the executor's. The final code is in the task
files. Open decisions D1 to D3 (section 2): the plan is written for (a) on each; the task files' `D1` / `D2` / `D3`
marks name the lines that would change otherwise.

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-tuning-module.md](01-tuning-module.md) | `console/tuning.py` (the whitelist, the ranges, `view`, `validate`), `paths.set_config`, `tests/test_tuning.py` | nothing |
| 2 | [02-route-pins.md](02-route-pins.md) | `tasks.step_route(..., pin=None)`: a kind's pinned rung and effort; `paths.DEFAULTS["kinds"]`; `tests/test_tasks.py` | nothing |
| 3 | [03-service.md](03-service.md) | `Hub.save_models`, `_route_for` passes the pin, `Handler._config` (GET `/api/config` with `kind_pins`, `kind_rules`, `tuning`), `POST /api/config/models`; `tests/test_server.py` | 1, 2 |
| 4 | [04-window.md](04-window.md) | the Models page (`data-page="models"`): Kinds, Tiers, Tuning, Save / Discard / Reload; the Settings band's `Models and tuning ›` link; `web/style.css` | 3 |
| 5 | [05-live-check.md](05-live-check.md) | Fred's live check | 4 |
| 6 | [06-close.md](06-close.md) | PLAN.md row and History, the design docs, this folder's state | 5 |

Tasks 1 to 3 are Python, tests first; each ends with its own commit. Task 4 is browser code (`node --check
web/app.js`, the full suite, headless Edge or Chromium at 400 and 340 px). Task 5 is Fred's: Claude never starts a
run and never edits Fred's config.json. Other chats edit `web/app.js`, `PLAN.md` and the design docs in parallel:
anchored edits only, stage only this plan's lines.

## 2. Decisions

Taken, with their source (not reopened here):

| # | Decision | Source |
|---|---|---|
| 1 | One page, three tabs (Kinds, Tiers, Tuning), opened from the Settings band; each tab label says `n edited`; Save posts only the changed keys; config.json stays the source of truth (a hand edit shows after Reload); nothing is rebuilt or restarted | interface 9b |
| 2 | config `kinds: {kind: {"rung": "auto" or a rung, "effort": "auto" or an effort}}`; a kind absent keeps the code's rule; a pinned rung acts as a pick (note `pin <kind>: <rung>`), a pinned effort as the composer's fixed effort (note `pin effort: <level>`), the model's cap still applies; verify and fix are not pinnable | the lead's contract, interface 9b |
| 3 | A step's own pick (Prep card) comes before the kind's pin; the task's fixed effort (composer) comes before a pinned effort | interface 9b ("the Prep card can still pick another rung for one step"), plan 17 3.5 |
| 4 | A kind pinned to a rung that cannot run now (harness off or not found, model gone from models.json) routes as auto and its row says `pinned model hidden · <reason>` | interface 9b |
| 5 | The whitelist of `POST /api/config/models`: the 22 keys of the contract plus `kinds` and `tiers`; every value checked; the route passes `guard.py` like every POST | the lead's contract, CLAUDE.md |
| 6 | The service writes config.json with every other key as written (as `paths.set_harness` does) and puts the saved keys in the live config: the next step reads them, a running step keeps its rung | interface 9b, plan 5 Task 1 |
| 7 | The page never writes models.json; `+ rung` lists the models of the harnesses that are on and found as models.json lists them, plus Claude's ladder | plan 5 3.2b, interface 9b |
| 8 | Prep, the handoff pass and the rules review take Claude rungs only (their passes run on the Claude CLI); Run default takes any listed rung | plan 5 README (Prep and the brief pass run on Claude) |
| 9 | `Turns on design` reads `design_max_turns`; `opus_max_turns` is not shown | plan 24 4.4, D2 a |
| 10 | Allowances are USD per day, week and month (the mock's K tokens are not the unit) | plan 18 README 3.4, the lead's contract |

Open: where the docs do not decide a point, the plan is written for the recommended option.

| # | Question | Options | Plan written for |
|---|---|---|---|
| D1 | config.json edited by hand while the page is open, then Save | (a) the page posts only the keys it changed; every other key, hand edits included, stays as the file has it; a hand edit of a key the page also changed is overwritten by the Save (Reload first shows it); (b) the service refuses the Save when the file changed since the page loaded (an mtime the page sends back) | (a) |
| D2 | How the Allowances fold lists models | (a) one row per model key of the tiers' usable rungs plus every key already in `allowances`, three fields each (day, week, month); an empty field is no allowance, a row left empty drops the key; (b) only the keys in `allowances`, with an add and a remove control | (a) |
| D3 | The ranges of the Tuning numbers (9b says a value out of range turns red; it does not give the ranges) | (a) the table of 3.3, wide enough for any setting the brainstorm discusses; (b) Fred's numbers per key | (a) |

A different answer changes only the lines the task files mark `D1`, `D2` or `D3`.

## 3. The contract

### 3.1 Files

```
console/tuning.py         the whitelist, the ranges, view and validate (Task 1); pure: no files, no threads, no HTTP
console/paths.py          set_config (Task 1); DEFAULTS["kinds"] = {} (Task 2)
console/tasks.py          step_route gains the keyword `pin` (Task 2)
console/server.py         Hub.save_models, _route_for's pin, Handler._config, Handler._config_models (Task 3)
web/app.js, web/index.html, web/style.css   the Models page (Task 4)
~/.claude/console/config.json   gains "kinds" and whatever Fred saves; nothing else on disk
```

### 3.2 Names

- `tuning.TUNING: {key: (group, unit, min, max)}` in the Tuning tab's order; `tuning.KEYS = tuple(TUNING) + ("kinds",
  "tiers")` is the whitelist. Groups: `steps`, `plan`, `handoff`, `balancing`, `gauge`, `passes`. Units: whole numbers
  `steps`, `s`, `turns`, `kb`, `parts`, `words`, `tokens`; numbers `usd`, `share` (a fraction: 0.1 is 10 points);
  `bool`; `rung`.
- `tuning.view(cfg) -> {key: {"value", "default", "min", "max", "unit", "group"}}` for every `TUNING` key; `default`
  is `paths.DEFAULTS[key]`.
- `tuning.validate(changes, cfg) -> (clean, errors)`: `errors` `{key: reason}` (`""` for the request as a whole);
  `clean` the values that passed, normalized (whole numbers as `int`, a tier's bare rung string as
  `{"rung", "effort": "auto"}`, a kind on auto and auto dropped). The service writes `clean` only when `errors` is
  empty: a Save is all or nothing.
- `paths.set_config(folder, values, merge=("tiers",))`: writes `values` into config.json, every other key as written;
  `tiers` merges one level (a tier not sent keeps its list), any other key replaces the file's value. ValueError when
  the file exists and cannot be read; the file is then never touched.
- `tasks.step_route(..., pin=None)`: `pin` is `cfg["kinds"].get(kind)`; plan 18's signature otherwise unchanged.
- `Hub.save_models(changes) -> errors` (`{}` when saved).

### 3.3 The whitelist and its checks (D3 a for the ranges)

| Key | Group | Unit | Range |
|---|---|---|---|
| `task_max_steps` | steps | steps | 1 to 12 |
| `task_step_budget_usd` | steps | usd | 0.1 to 50 |
| `step_timeout_s` | steps | s | 60 to 7200 |
| `design_max_turns` | steps | turns | 1 to 200 |
| `read_max_turns` | steps | turns | 1 to 100 |
| `plan_max_kb` | plan | kb | 10 to 1000 |
| `plan_max_parts` | plan | parts | 2 to 12 |
| `plan_hold`, `replan_auto` | plan | bool | true or false |
| `brief_max_words` | handoff | words | 100 to 2000 |
| `brief_timeout_s` | handoff | s | 10 to 600 |
| `balance_margin`, `cache_bonus` | balancing | share | 0 to 0.5 |
| `budget_warn_at` | balancing | share | 0.1 to 2 |
| `daily_budget_usd` | balancing | usd | 0 to 1000 (0: no limit) |
| `allowances` | balancing | usd | `{key: {day_usd?, week_usd?, month_usd?}}`, each 0 to 100000; a key `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` |
| `gauge_yellow_tokens`, `gauge_red_tokens` | gauge | tokens | 10000 to 1000000; yellow under red |
| `prep_model`, `brief_model`, `review_model` | passes | rung | a Claude rung `claude_cli.known_model` knows |
| `default_model` | passes | rung | any rung: a Claude rung `known_model` knows, or a model models.json ranks |
| `kinds` | | | `{kind: {rung?, effort?}}`: kind in `tasks.PREP_KINDS` (verify, fix: `set by the rule, not pinnable`); rung `auto` or a listed model; an opencode or cmd model below opus rank never on a think kind; effort `auto` or `claude_cli.EFFORTS` |
| `tiers` | | | `{tier: [rung or {rung, effort?}]}`: tier in `tasks.TIERS`; 1 to 12 rungs; each listed, none twice; the same think rule; effort as above |

Reasons, exactly: `between 1 and 12`, `a whole number between 1 and 12`, `a number between 0.1 and 2`, `true or
false`, `not a setting this page changes`, `unknown model: <rung>`, `a Claude model: this pass runs on the Claude
CLI`, `yellow must start under red`, `<kind>: set by the rule, not pinnable`, `unknown kind: <kind>`,
`<kind>: <reason>`, `unknown tier: <tier>`, `<tier>: 1 to 12 rungs`, `<tier> <n>: listed twice`,
`<tier> <n>: <reason>`, `opencode: <model> is not a think model` (plan 5's words), `effort: auto or low, medium,
high, xhigh, max`, `<key> <window>: between 0 and 100000`, `changes: an object of settings to save`.

### 3.4 Routes

- `GET /api/config` (now `Handler._config()`, the same dict plus three keys): `kind_pins` (config `kinds`; the
  contract's `kinds` name is taken by the existing list of Prep kinds, which the window and plan 25 read),
  `kind_rules: {kind: {"rank", "effort", "tools"}}` (`tasks.RULES`: the Kinds tab's quiet line and the auto effort's
  start), `tuning` (`tuning.view(cfg)`). `tiers` and `kinds_tier` are plan 18's.
- `POST /api/config/models {"changes": {key: value}}` through `guard.py` (Host, X-CC): 200 with the new
  `_config()`; 400 `{"error": "<key>: <reason>; ...", "errors": {key: reason}}` (nothing written); 409 `{"error":
  "cannot read <path>: fix it by hand"}` when config.json is unreadable.

### 3.5 Pins in `step_route`

- Read before the rule: verify and fix ignore `pin`. A pinned effort applies only when the task's effort is `auto`
  and then counts as the task's fixed effort: the demand, floor and hint no longer change the effort, the cap does;
  its note is `pin effort: <level>` in place of `fixed effort: <level>`.
- A pinned rung applies only with `cfg` (the service) and when the step has no pick: `refuse(rung)` or an unknown
  rank refuses it with `pin <kind>: <rung> refused: <reason> -> auto` and the step routes as auto (balance); else it
  becomes the step's pick with the note `pin <kind>: <rung>` (no `pick:` note), so the floor and hint keep its model
  and the balance never moves it.

### 3.6 Hard rules

- Only `POST /api/config/models` writes config.json for the page, only through `paths.set_config`, only keys of
  `tuning.KEYS`, only after `tuning.validate` returned no error. The service never writes `~/.claude/settings.json`
  or models.json.
- The route passes `guard.py` like every POST; the service still binds 127.0.0.1 only.
- A running step keeps its rung and effort; the next step reads the saved values (`Hub.cfg` in place).
- No emojis or em-dashes in any text of the page or the reasons.

### 3.7 Drift guards

- `tuning.py` stays pure: `paths` is imported for `DEFAULTS` only.
- The page never computes a route: a pin's effect shows in the next step's route notes.
- Every key the Tuning tab shows has a default in `paths.DEFAULTS` (Task 1's test).

## 4. Verification at the end of every task

- `py -m unittest discover -s tests` all OK (Windows); the count is written in the task's commit message.
- Tasks 1 and 2: the new tests fail as written before the code and pass after it.
- Task 3: `tests/test_server.py` saves through the route (config.json keeps the other keys, the live config follows),
  refuses with reasons (nothing written, 409 on an unreadable file) and runs a pinned kind's step on its rung and
  effort with the fake claude.
- Task 4: `node --check web/app.js`; headless Chromium or Edge at 400 and 340 px: the three tabs, an edit, its
  `n edited`, a value out of range blocking Save, Save, Discard, Reload; no console errors, no horizontal overflow.
- Task 5: Fred's live check (05-live-check.md).
