# Plan 19: Fixes from the plan 17 live check. Guided implementation plan

> Context: [CLAUDE.md](../../CLAUDE.md) (rules), [plans/17-tasks/README.md](../17-tasks/README.md) (the contract this
> plan changes; read 3.2 to 3.11 first), [plans/17-tasks/06-live-check.md](../17-tasks/06-live-check.md) (what Fred
> checked), the memory file `plan17-live-check-findings.md` (the evidence of every finding), and the task data of the
> check in `~/.claude/console/tasks/` (`20261012-122014-915f` is the done chain).
>
> Plan 17 Task 7 (close plan 17: PLAN.md History, BRAINSTORM D16, CLAUDE.md line) is another job: not done here.
> Other chats edit PLAN.md, CLAUDE.md and BRAINSTORM.md in parallel: stage only this plan's own lines.

Status: written 2026-10-12; Fred took (a) on D1 to D7 the same day. D1 done: commit c00db0f.

## 1. Tasks, in order

| # | File | What | Findings |
|---|---|---|---|
| 1 | [01-tasks-text.md](01-tasks-text.md) | step goals not cut at 200, bold HANDOFF markers, the verify step's own text, caps named in the retry reason | A1, A8 |
| 2 | [02-brief.md](02-brief.md) | the brief pass: three turns, never longer than what it compacts, open questions kept; live check of 5 briefs | A3 |
| 3 | [03-attempts.md](03-attempts.md) | every attempt of a step recorded (session, cost); costs summed; a paused task closes an ended step; Clear removes every stream | A4, A5, A6 |
| 4 | [04-service.md](04-service.md) | what the window needs from the service: Fable guard on `/api/run`, Run anyway for a budget hold, task-aware counts, model versions, an older step's transcript, `edit_kinds` | A7, A8, B2, B3, B6 |
| 5 | [05-window-tasks.md](05-window-tasks.md) | the list folds step sessions under their task; Task page: Open on every attempt, total cost, attempts, paused line; the step list always on the Prep card | A2, B1, B2, B7 |
| 6 | [06-window-route.md](06-window-route.md) | model versions in every dropdown, Confirm to use Fable on the card and the task, the project on the Prep card and the box, a restored draft marked | A7, B3, B4, B5 |
| 7 | [07-navigation.md](07-navigation.md) | the navigation audit (walk, write down, fix in one task) | B6 |
| 8 | [08-docs.md](08-docs.md) | corrections of plans/17-tasks/06-live-check.md | C1 |
| 9 | [09-live-check.md](09-live-check.md) | Fred's live check of the fixes and of the checks plan 17 left unexercised | C2 |

Tasks 1 to 4 are Python with tests first. Tasks 5 to 7 are browser code (`web/app.js`, `web/index.html`,
`web/style.css`): `node --check web/app.js`, the full suite, and headless Edge at 400 and 340 px. Task 8 is docs.
Task 9 is Fred's: Claude never starts a run, never POSTs `/api/run`, `/api/task` or `/api/prep`.

## 2. Decisions (Fred). Recommended option first; the plan is written for it

| # | Question | Options | Plan written for |
|---|---|---|---|
| D1 | The plan 17 review fixes (tasks.py, server.py, their tests, README, one PLAN.md line) are uncommitted. Tasks 1 to 4 edit the same files. | (a) commit them first as their own commit `fix: plan 17 review fixes` (262 tests OK on 2026-10-12), staging only those six files; (b) Fred commits them; (c) build on top, uncommitted | (a) |
| D2 | Prep returns `steps: []` when its pre-scout already read the code (A2). | (a) the Prep card always shows the step list with `+ step` (empty list: a hint line), prompt unchanged; (b) as (a), plus one prompt sentence: a request that edits files gets at least its edit step, `[]` only for a question, a lookup or a one-line change; (c) the prompt sentence only | (a) |
| D3 | The card-level model select accepts `fable` and plain Run starts it with no confirm (A7). | (a) the card shows the credits note and Run becomes a two-click `Confirm to use Fable 5.1`; `/api/run` refuses a Fable model without `fable_ok: true` (409); (b) the card select does not list `fable`; Fable only on task steps | (a) |
| D4 | What a rolling brief may add (A3). | (a) a first brief must be shorter than its raw note; a later one shorter than the raw note plus the earlier brief (it carries forward, it never adds); the prompt asks for 60 % of that; open questions never dropped; (b) every brief shorter than its raw note alone (older steps' files and questions may be lost) | (a) |
| D5 | A budget hold has no release but Stop then Retry (A8). | (a) Confirm also releases a hold, for that step only; the button reads `Run anyway`; the route notes say `budget: hold released by Fred`; (b) leave it until sub-plan 18 fills `Hub.budget()` | (a) |
| D6 | Which step sessions leave the list (B1). | (a) every session whose `task` is set: its task row is the way in (Task page, Open per attempt); after Clear the step chats stay in VS Code / transcripts only; (b) only while the task is in `snap.tasks`; after Clear they come back as plain Done rows | (a) |
| D7 | Where the version of an alias comes from (B3). | (a) learned: the newest full id of each family seen in the event log (`claude-fable-5-1` -> `fable 5.1`); a family never seen shows the alias alone; no id in code or config; (b) a new config key `alias_ids` Fred keeps up to date | (a) |

A different answer changes only the task named in the table's last column notes; each task says where.

## 3. The contract (changes to plans/17-tasks/README.md; everything else there still holds)

### 3.1 task.json, step attempts (Task 3)

A step gets `attempts`, one entry per session the step ran in, oldest first:

```json
{"n": 1, "kind": "scout", "session": "de8c...", "cost": 0.14222358, "retries": 1,
 "attempts": [
   {"session": "8944...", "cost": 0.0123, "started": 1791778814.1, "ended": 1791778831.4,
    "why": "no HANDOFF block", "final": true},
   {"session": "de8c...", "cost": 0.1299, "started": 1791778831.5, "ended": 1791778852.2,
    "why": "", "final": true}]}
```

- `tasks.start_step` appends an attempt; `tasks._finish` sets the last attempt's `ended` and `why` (the chain
  line's why). `session` keeps the current attempt's id, as before.
- `cost` of an attempt is the session row's `cost` (state.Session, the sum of its `run_ended` costs), copied by
  `Hub.sync_costs` once the run has ended (`final: true`); a stopped run's cost lands with its `run_ended`, after
  the Stop. The step's `cost` = the sum of its attempts' costs, rounded to 6 places.
- `tasks.attempts(step) -> list` reads a step of a task.json written before this plan (no `attempts` key) as one
  final attempt built from `session`, `cost`, `started`, `ended`, or `[]` when it never ran.
- `STEP_KEYS` stays the plan 17 list: `attempts` is never required by `tasks.whole` (old task.json files load).
- `tasks.clear` returns the sessions of every attempt of every step (no duplicates, in order), so Clear and
  clear-on-done forget every stream (A6).

### 3.2 Transitions changed (README 3.7 of plan 17)

| State seen | Condition | Result |
|---|---|---|
| owner `fred` (paused), step `running`, session ended | | handled as for owner `service` (note, brief, chain lines, `done` / retry / stuck / fix inserted); nothing starts after it (A4) |
| step ended, not `ok` | result subtype `error_max_turns` / `error_max_budget_usd` | the reason is `it hit the turn cap (N turns)` / `it hit the step budget (X USD)` (A8); retry rule unchanged |
| Fred: Confirm | task `waiting`, `why` ends with ` over its pace` | `task["hold_ok"] = n` of the step that holds, task `running`; `start_step` starts it on the held route with the note `budget: hold released by Fred` (D5) |

`Hub.sync_costs(task)` runs at the start of every `_advance_one`, for every task with an attempt that is not
`final`, whatever its state or owner (a stopped task gets its cost too).

### 3.3 The brief (README 3.6b of plan 17)

- `claude_cli.brief_command`: `--max-turns 3`. Structured output re-prompts on a schema mismatch, and each
  re-prompt is a turn (code.claude.com/docs/en/agent-sdk/structured-outputs, read 2026-10-12); a good answer
  already takes 2 turns (`num_turns: 2` in three live runs with `--max-turns 1`, 2026-10-12). Subtypes checked in
  code.claude.com/docs/en/agent-sdk/typescript (`SDKResultMessage`): `error_max_turns`, `error_during_execution`,
  `error_max_budget_usd`, `error_max_structured_output_retries`.
- `compact.limit(raw, prev) -> int`: words of the raw note plus words of the earlier brief (D4 a).
- `compact.check(block, max_words, raw="", prev="") -> str`: `tasks.check_handoff`, then `over N words`, then
  `not shorter than what it compacts (N >= M words)` when `raw` is given and `words(block) >= limit(raw, prev)`,
  then `dropped the open questions` when the raw note or the earlier brief has an open question and the block has
  none. `""` when all hold.
- `compact_prompt.md` asks for at most `$words` words, `$words = max(60, min(brief_max_words, limit * 6 // 10))`,
  keeps every open question, and names the task by its goal (`$task`, the goal cut at 400 characters) instead of
  the 80-character title.

### 3.4 Snapshot and routes (Task 4)

- `snap["versions"]`: `{"fable": "5.1", "opus": "5.5", "sonnet": "5.5", "haiku": "5.5"}`, family -> the newest
  version seen in a full model id of any session in memory (`State.versions()`); a family never seen is absent.
- `snap["counts"]["needs"]` and `["working"]` count a task once: sessions with a `task` are left out, tasks are
  added (`waiting` and `stuck` -> needs, `planned` and `running` -> working). The tray reads the same counts.
- `task_row(t)["steps"][i]["attempts"]`: `[{"session", "cost", "why"}]` (from `tasks.attempts`).
- `task_row(t)["paused_after"]`: the `n` of the current step when the task is paused (`owner == "fred"`) and that
  step is not running (it ended while paused), else 0. The Task page says it plainly.
- `GET /api/config` adds `"edit_kinds": sorted(tasks.EDIT_KINDS)`.
- `POST /api/run`: a model whose tier is `fable` needs `"fable_ok": true` in the body, else 409
  `confirm Fable: it may bill usage credits on this plan` (D3 a).
- `GET /api/chat?session=<id>`: with no run meta and no session row, the transcript is found by id under
  `~/.claude/projects/*/<id>.jsonl` (`transcript.find(root, sid)`), so an older step's Chat still reads.
- `task_levers` `confirm`: also `""` for a hold (`why` ends with ` over its pace`).

### 3.5 Window

- Step sessions (`s.task` set) leave the list's groups (D6 a); the task card is the way in.
- The Task page draws every attempt with its own Open, the total cost, the paused line and `retry 1`.
- Every model text shows a version: `modelText` falls back to `snap.versions[family]` for an alias.
- The Prep card names its project at the top and above the buttons; the box's placeholder names it too.
- A restored draft is marked (`Draft kept from last time` with Clear) and selected on first focus.

## 4. Hard rules (unchanged from CLAUDE.md and plans/17-tasks/README.md 3.10)

- Python 3.14 standard library + pywebview, plain HTML/CSS/JS, no build step, no daemon, no database.
- The service binds 127.0.0.1 only; every request passes `console/guard.py`.
- Data only in `~/.claude/console/` (tests: `CC_CONSOLE_HOME`). Never edit `~/.claude/settings.json`, never run
  `install_hooks.py`, never touch `cc_events.py`.
- `Hub.task_levers` stays the one gate of the task levers; `Hub.levers` of the session levers.
- Stop is the stream-json interrupt (`runs.stop`), never a kill. Code never picks `fable`.
- No emojis or em-dashes in prose, prompts, notes or window text.

## 5. Drift guards for the executor

- Before Task 1: `git status --short`; with D1 (a), commit the six review files as their own commit, then
  `py -m unittest discover -s tests` must say 262 OK. Commit nothing that is not this plan's.
- Re-check `plans/` and the PLAN.md rows before writing a file whose number could collide.
- One step at a time: write the test, see it fail, write the code, run the whole suite, commit. A test that cannot
  be made to fail first means the step is already covered or wrong: stop and check.
- Do not add a queue, a lock file, a lease, a second retry, a branch or a parallel step. Do not let a model write
  into the task folder.
- Do not pass a `--model` that is not a tier alias or a rung of the ladder; do not pin model ids in code or tests
  (tests use the fake's ids or `claude-opus-4-8`-style rungs already in `paths.DEFAULTS`).
- Do not change `prep_prompt.md`'s type table or the route-model skill (a test pins them).
- Do not restructure `web/app.js`: add functions next to their nearest neighbour; keep `data-act`, `data-go`,
  `data-open`, `data-task`, `data-tact`, `data-pact`. All styling in `web/style.css`, tokens first; orange
  (`--you`) only for "needs you", red and green only for state.
- A live `claude -p` from Claude is only the brief check of Task 2 (haiku, about 0.002 USD each, 5 runs). Nothing
  else live without Fred's word.
- Each task ends with a PLAN.md History line (this plan's own line, staged alone) and the plan's row state.

## 6. Verification at the end of every task

```bat
py -m unittest discover -s tests
node --check web/app.js
```

Tasks 5 to 7 also load the page in headless Edge at 400 and 340 px on a scratch home with the fake claude (recipe
in [05-window-tasks.md](05-window-tasks.md) section 5.6) and read every screenshot.
