# Plan 17: Task folders and step chain. Guided implementation plan

> Design: [../17-task-folders.md](../17-task-folders.md) (sections 1 to 10; the decisions of section 8 are all taken
> as option (a), Fred 2026-10-12). Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
> Earlier plans this builds on: [16-demand-routing](../16-demand-routing.md), [03-levers](../03-levers.md),
> [08-cold-handoff](../08-cold-handoff.md), [13-handoff-next](../13-handoff-next.md).

This folder is the plan. No code is written in it: each task file names the files, the functions with their
exact signatures, the data shapes, the prompt text, the tests with what they assert, and the ordered steps.
The code is written when a task is executed, test first, and placed one task at a time (cp + test + commit).
Everything that could drift from the design is pinned in section 3 (the contract) and in each task's
"Drift guards" list.

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-tasks-module.md](01-tasks-module.md) | `console/tasks.py` (rules, routes, handoff parse and check, chain transitions, task files), `console/step_prompt.md`, config keys, `tests/test_tasks.py` | nothing |
| 2 | [02-cli-and-runs.md](02-cli-and-runs.md) | `claude_cli.run_command` limits (`--disallowedTools`, `--tools`, `--max-budget-usd`, `--max-turns`), `runs.start` limits kept in the run meta, `run_started` with `task` and `step`, `state.Session.task` | 1 |
| 3 | [03-prep-steps.md](03-prep-steps.md) | Prep proposes `steps`, code validates and appends `verify`, the prompt's kinds block, the fake claude's `CHAIN` word | 1 |
| 4 | [04-service.md](04-service.md) | `Hub.tasks`, `Hub.task_levers`, `Hub.advance` in the hub loop, the `/api/task*` routes, tasks in the snapshot, `auto_steps` skipping task sessions, task-folder retention | 1, 2, 3 |
| 5 | [05-window.md](05-window.md) | The effort slider, Run as task with the editable step list, the task card in the list, the Task page, the step tag on session rows | 4 |
| 6 | [06-live-check.md](06-live-check.md) | Fred's live check in CONTENT MANAGER | 5 |
| 7 | [07-close.md](07-close.md) | PLAN.md, BRAINSTORM D16 and the section 2 line, CLAUDE.md line, this folder's state | 6 |

Each task ends with its own commit. Start state: 169 tests OK on `master` (2026-10-12, the working tree of plans 15
and 16 included). Other chats edit `PLAN.md`, `web/app.js` and `web/style.css` in parallel: apply the window task
as anchored edits, never a whole-file copy, and stage only this plan's lines.

## 2. Decisions taken (Fred, 2026-10-12: "a" everywhere; 17 to 20 confirmed the same day)

| # | Decision | Taken |
|---|---|---|
| 1 | Non-goals | D16 added to BRAINSTORM: a linear step chain advanced by the service when a step ends is not a task graph or a scheduler; branches, parallel steps, queues and more than one retry stay out |
| 2 | Who proposes the steps | Prep returns an optional `steps` list; code validates it and appends the verify step; Fred edits on the card |
| 3 | Who writes the handoff | The service, from the `HANDOFF ... END HANDOFF` block of the step's final message; the model writes nothing into `~/.claude/console/` |
| 4 | Advance | The service starts the next step as soon as the handoff checks out; Pause and Stop at any time |
| 5 | `edit` row | haiku/low (the misses floor raises it after one failure) |
| 6 | After a verify FAIL | Insert `fix` on the escalated route and a `verify` after it, once per task; a second FAIL is stuck |
| 7 | Retention | Task folders 90 days (`task_retention_days`); run streams keep `retention_days` (14) |
| 8 | Window scope | Run as task on the card, the task card in the list, the Task page with Stop / Pause / Retry |
| 9 | Step budget | `--max-budget-usd 3` per step (`task_step_budget_usd`), `task_max_steps` 6 |
| 10 | Tool sets | As the rules table (section 3.4) |
| 11 | Model budget | Sub-plan 18; plan 17 only consumes `Hub.budget()` (an empty dict until 18) |
| 12 | Routing under budget pressure | One model down at a higher effort when a model is over `budget_warn_at` of its pace; `verify` holds for Fred |
| 13 | Fable | Never picked by code; Fred sets it on a step of the card and confirms once per task |
| 14 | Opus thinks, Haiku reads, Sonnet writes | Opus only on `design`, a verify of a Sonnet step, one fix; `reasoning high` gives a `code` or `debug` step `high` effort, never Opus; `opus_max_turns` 12 on a design step |
| 15 | Pace | Sub-plan 18 (the windows, the month start day, the caps) |
| 16 | Effort slider | Auto, or one fixed level for every step on the rule's model; kept in `window.json`; with a fixed effort, escalation moves the model |
| 17 | Model ladder (design 4.10) | `ladder` in `config.json`, newest first per tier; `Hub.model_id(tier)` picks the rung when a step starts; code takes an older rung only under budget pressure; Fred may pick any rung on a card or a step (confirmed 2026-10-12). Open fact unresolved by the live check: /usage has no per-Opus line (2026-10-12). |
| 18 | Storage (design 4.11) | The retention table, a 20 KB note cap, the data-folder size line on the Usage page with `storage_warn_mb` 500 (confirmed 2026-10-12) |
| 20 | Brief between steps (design 4.12) | A Haiku pass (no tools, one turn, structured output) compacts the raw note plus the previous brief into a rolling brief of at most `brief_max_words` for the next step; code checks it and falls back to fixed cuts; `steps/NN-<kind>.brief.md`; the next step reads the brief only (Fred, 2026-10-12) |
| 19 | Clear on done (design 4.11) | On `done` the service deletes the step run streams and every note but the last good one; keeps task.json, chain.jsonl, prompt.md; `task_clear_on_done` true; a Clear lever on any task that is not running (Fred, 2026-10-12) |

## 3. The contract (what every task must keep)

### 3.1 Files and places

- Task folders: `<paths.home()>/tasks/<task-id>/` with `task.json`, `prompt.md`, `steps/NN-<kind>.md`,
  `chain.jsonl`. Nothing else is created there. Nothing is written anywhere else (CLAUDE.md data rule).
- A task id is `prep.new_id()` (`YYYYMMDD-HHMMSS-xxxx`). `tasks.safe_id(text)` accepts only
  `[0-9a-f-]` of length 20 or less; every route and file read uses it first.
- `task.json` is written whole through `task.json.tmp` and `os.replace`, by the service only.
- Step sessions are ordinary window runs: their streams stay in `runs/<sid>.jsonl`; `task.json` names them.

### 3.2 task.json

```json
{"id": "20261012-101500-3f2a", "project_dir": "D:\\WORK\\CONTENT MANAGER", "project": "CONTENT MANAGER",
 "title": "Add the usage calendar export", "type": "normal", "demand": {"reasoning": "medium", "volume": "high"},
 "effort": "auto", "state": "running", "owner": "service", "current": 2, "last_good": 1,
 "escalated": "", "fable_ok": false, "prep": "20261012-101455-9c1d", "why": "",
 "created": 1760235300.0, "updated": 1760235900.0,
 "steps": [
   {"n": 1, "kind": "scout", "goal": "Find the export code paths and the tests that cover them", "model": "haiku",
    "effort": "low", "pick": "", "session": "7b3c...", "state": "done", "handoff": "steps/01-scout.md",
    "verdict": "", "retries": 0, "cost": 0.02, "start_commit": "146c432", "started": 1760235310.0,
    "ended": 1760235400.0, "notes": ["rule scout: haiku/low"]},
   {"n": 2, "kind": "code", "goal": "Write the export and its tests", "model": "sonnet", "effort": "medium",
    "pick": "", "session": "a91e...", "state": "running", "handoff": "", "verdict": "", "retries": 0, "cost": 0,
    "start_commit": "146c432", "started": 1760235410.0, "ended": null, "notes": ["rule code: sonnet/medium"]},
   {"n": 3, "kind": "verify", "goal": "Check step 2", "model": "", "effort": "", "pick": "", "session": "",
    "state": "planned", "handoff": "", "verdict": "", "retries": 0, "cost": 0, "start_commit": "", "started": null,
    "ended": null, "notes": []}
 ]}
```

- Task `state`: `planned`, `running`, `waiting`, `stuck`, `done`, `stopped`. `owner`: `service` or `fred`.
- Step `state`: `planned`, `running`, `done`, `failed`. `pick`: a model Fred set on the card (`""` = the rule);
  the only way `fable` can appear. `checked` (verify and fix steps only, else 0): the `n` of the step this one
  checks or fixes; its `model` / `effort` are the `checked` route of README 3.5.
- `why`: the reason of the current `waiting`, `stuck` or `stopped` state, shown in the window.
- `demand`: Prep's `reasoning` and `volume` for the task. `effort`: `auto` or one of `claude_cli.EFFORTS`.
- `model` and `effort` of a step are filled when it starts (empty while `planned`), `notes` lists the routing
  steps that applied (section 3.5), in order, so the window and the chain log can show why.

### 3.3 chain.jsonl

One JSON object per line: `{"ts": 1760235410.0, "step": 2, "from": "planned", "to": "running",
"why": "rule code: sonnet/medium", "session": "a91e..."}`. `from` and `to` are step states for step
transitions and task states (prefixed `task:`) for task transitions, for example `"from": "task:running",
"to": "task:stuck"`. Appended with `open(..., "a")`, one `write` per line, never rewritten.

### 3.4 The rules table (kinds)

`tasks.RULES`, kind -> (model, effort, tools). `tools` is the `--tools` list or `""` for the default set.
Every step also gets `--disallowedTools Agent` (`tasks.DISALLOW = ("Agent",)`).

| kind | model | effort | tools |
|---|---|---|---|
| scout | haiku | low | `Read,Grep,Glob` |
| search | haiku | low | `Read,Grep,Glob,WebFetch,WebSearch` |
| draft | haiku | low | `""` |
| proofread | haiku | low | `""` |
| edit | haiku | low | `""` |
| code | sonnet | medium | `""` |
| document | sonnet | medium | `""` |
| explain | sonnet | medium | `Read,Grep,Glob` |
| debug | sonnet | high | `""` |
| test | haiku | low | `Bash,Read,Grep,Glob` |
| design | opus | high | `Read,Grep,Glob,WebFetch,WebSearch` |
| verify | computed (`verify_route`) | computed | `Bash,Read,Grep,Glob` |
| fix | computed (`escalate_step` of the checked step) | computed | `""` |

The web-lookup kind is named `search`, not `lookup`: `lookup` is a Prep route type and
`tests/test_dotclaude.py::table` picks any table row whose first cell is a Prep type, so a `lookup` row in
`prep_prompt.md` would be compared with the route-model skill's table. `tasks.PREP_KINDS` = every kind but
`verify` and `fix` (what Prep may propose). `tasks.EDIT_KINDS` = `{edit, code, debug, document, draft}` (a
`verify` follows the last of them when none does).

### 3.5 The route of a step (`tasks.step_route`, applied in this order, each one appends a note)

1. **rule**: `RULES[kind]`; `verify`: `verify_route(checked)`; `fix`: `levers.escalate_step(checked)`
   (`checked` is the (model, effort) of the step being checked or fixed; when nothing is above, the checked
   route itself).
2. **pick**: a step whose `pick` is set runs on that model at the rule's effort (Fred's choice; `fable` allowed
   here only).
3. **demand**: `demand.reasoning == "high"` and kind in `{code, debug}`: effort at least `high`, model unchanged.
4. **floor**: `routing.floor(misses, kind)`: when its rank is above, take it.
5. **hint**: the previous note's `Next model: m/e` above the route: `levers.escalate_step(route)`, one step only.
6. **cap**: in `auto` effort, a route above opus/high becomes opus/high; a `fable` that is not a `pick` becomes
   `opus`.
7. **budget**: `budget.get(model, 0) >= warn_at` and model is not `haiku`: kind `verify` holds
   (`hold = "<model> over its pace"`); any other kind goes one model down at one effort up
   (`sonnet/xhigh` for `opus/high`, `haiku/high` for `sonnet/medium`), effort capped at `max`.
8. **fixed effort**: `effort != "auto"`: the step's effort is that level on the model chosen above
   (every alias accepted `xhigh` and `max` on CLI 2.1.296, checked 2026-10-12; `EFFORT_CAP` stays a guard
   that clamps to `claude_cli.EFFORTS[-1]`).

Returns `{"model", "effort", "notes": [...], "hold": ""}`; `hold` non-empty means the task waits for Fred.
`verify_route(checked)`: the next model after `checked[0]` in `claude_cli.MODELS`, capped at `opus`; effort
`max(checked[1], "medium")` by `EFFORTS` order, capped at `high`. Examples: haiku/low -> sonnet/medium,
sonnet/medium -> opus/medium, sonnet/high -> opus/high, opus/high -> opus/high. With a fixed effort, `fix` and
Escalate move the model (`levers.escalate_step` is called with effort `high` so it steps the model), the effort
stays fixed.

### 3.6 The handoff block

The step's final message ends with:

```text
HANDOFF
## Findings
...
## Files touched
- path (what)
## Open questions
- (none)
## Next
One line for the next step. Optional: Next model: sonnet/high
END HANDOFF
```

- `parse_handoff(text) -> str | None`: the last block between a line `HANDOFF` and a line `END HANDOFF`
  (whole lines, surrounding whitespace ignored), without the marker lines; `None` when there is none.
- `check_handoff(block) -> str`: `""` when the four headings `## Findings`, `## Files touched`,
  `## Open questions`, `## Next` appear in that order, each on its own line, and the Findings section has at
  least one non-empty line; else one of `missing: <heading>`, `headings out of order`, `Findings is empty`.
- `next_hint(block) -> (model, effort) | None`: the first `Next model: <model>/<effort>` that
  `routing.parse` accepts.
- `brief_file(task, step) -> "steps/NN-<kind>.brief.md"`: the compacted note the next step reads (section 3.6b).
- `note_file(task, step) -> "steps/NN-<kind>.md"`; its content is one line
  `# Step NN: <kind> on <model>/<effort>, session <id>`, a blank line, then the block, `redact.mask`ed.

### 3.6b The brief

`console/compact.py` (new, Task 1b in [01-tasks-module.md](01-tasks-module.md)): `BRIEF_SCHEMA` (`findings`:
array of strings, `files`: array of strings, `questions`: array of strings, `next`: string; all required),
`build_prompt(task, step, next_step, prev_brief, raw) -> str` from `console/compact_prompt.md`,
`render(fields) -> str` (the four headings in HANDOFF order, lists as `- ` lines; `Next model:` kept when the raw
note had one and the fields' `next` carries it), `check(block, max_words) -> str` (`tasks.check_handoff` plus
the word cap: `"over N words"`), `fallback(prev_brief, raw) -> str` (code only: the raw note's Files touched and
Open questions as they are, its Findings cut at 1500 characters, Next from the raw note, else from the previous
brief), `run_brief(cfg, exe, task, step, next_step, prev_brief, raw) -> dict` (blocking; `{"text", "cost",
"words", "model", "fallback": "" | why}`; never raises: every failure ends in `fallback`).
`claude_cli.brief_command(exe, model, schema) -> list`: like `prep_command` with `--tools ""` and
`--max-turns 1`. The prompt (final text) is in 01-tasks-module.md. Limits: `brief_max_words` 400,
`brief_model` "haiku", `brief_on` true, `brief_timeout_s` 60.

### 3.7 Transitions (`tasks.on_step_ended` and the service)

| State seen | Condition | Result |
|---|---|---|
| task `planned` | owner `service` | start step 1 |
| step `running`, session live | | nothing |
| step `running`, session ended, `stop_question` set | | task `waiting`, `why = "asks: <question>"`; Fred answers on the session page; the next end is checked again |
| step ended, `ok` and the block checks out | kind not `verify` | note written, step `done`, `last_good = n`; the brief job starts (`task["briefing"] = n`, the row says `briefing`); when `steps/NN-<kind>.brief.md` exists the next step starts, or the task is `done` after the last step (the last step gets a brief too: Start next chat reads it) |
| step ended, `ok`, block ok, kind `verify` | verdict `PASS` | as above |
| | verdict `FAIL`, `escalated == ""` | insert `fix` (route from the checked step) and `verify` after the current step; `escalated = "<from> -> <to>"`; a miss line (`levers.miss_line(project, checked kind, from, to, detail)`); start the fix |
| | verdict `FAIL`, `escalated != ""` | task `stuck`, `why = "verify failed twice: <detail>"` |
| | no verdict | treated as a bad block: `why = "no VERDICT line"`, retry rule below |
| step ended, not `ok` or the block is missing or bad | `retries == 0` | step `failed` then `planned` again with `retries = 1`; restarted on the same route with the retry line in its prompt |
| | `retries == 1` | task `stuck`, `why = "<reason> (after one retry)"` |
| Fred: Stop | | `runs.stop(session)` when live (the interrupt); task `stopped`, owner `fred` |
| Fred: Pause | task `running` or `waiting` | owner `fred` (the live step finishes and is closed as usual: note, brief, chain line; nothing starts after it; plan 19) |
| Fred: Resume | owner `fred`, task not `stuck` / `stopped` | owner `service` |
| Fred: Retry | task `stuck` or `stopped`, no live session | the current step `planned` again (its `retries` kept), task `running`, owner `service`; the previous step session is left as it is |
| Fred: Confirm Fable | task `waiting` on `why = "confirm Fable"` | `fable_ok = true`, task `running` |
| task reaches `done` | `task_clear_on_done` | `tasks.clear(home, task, keep_last=True)` plus the step streams: README 3.9 |
| Fred: Clear | task not `running` / `waiting` and no live session | `tasks.clear(home, task, keep_last=False)` removes the folder; the step streams and metas go too; the task leaves `Hub.tasks` and the list |
| service restart | task `running`, the step's run meta `ended` | the first `advance` treats it as an ended step |

`ok` = the step session's row has no `interrupted`, `stopped`, `failed`, and its last run ended with
subtype `success` (the run meta and the session row carry all of it). A `STOP:` question is not a failure, and
neither is an auto-mode denial: the model works around it and its handoff says what is left (review, 2026-10-12).

The verdict and the question are read in the step's reply (`tasks.reply_verdict`, `tasks.reply_question`, the
hook's patterns); the Stop hook's values are the fallback, since that hook is async and may land after
`run_ended`. A task move that raises (a disk error, a task.json that is not whole) makes that task `stuck` with
the error as `why`; it never stops the hub loop. `tasks.load` skips a task.json that lacks a key the service
reads (`tasks.whole`).

### 3.8 Model ladder and the rung of a step

`claude_cli.MODELS` stays the four tiers, the vocabulary of every rule, miss line and route text. `config.json`
`ladder` maps each tier to its rungs, newest first, the alias first (`{"haiku": ["haiku", "claude-haiku-4-5"],
"sonnet": ["sonnet", "claude-sonnet-4-6"], "opus": ["opus", "claude-opus-4-8", "claude-opus-4-7",
"claude-opus-4-6"], "fable": ["fable"]}`). `claude_cli.tier_of(model_id) -> str` gives the tier of an alias or a
rung (`model_alias` already finds the family in a full name); `claude_cli.known_model(cfg, model) -> bool` is
true for a tier or a rung of the ladder (the run route and the card use it instead of `in MODELS`).
`Hub.model_id(tier) -> str` returns the first rung of the tier whose budget share (`Hub.budget()`, keyed by
model id, `{}` until sub-plan 18) is under `budget_warn_at`, else the alias. `Hub.start_step` calls it after
`step_route` and passes the rung to `runs.start`; `step["model"]` keeps the rung, `step["tier"]` the tier.
`step_route`'s budget step 7 receives tier shares that `Hub` computes as the minimum share over the tier's rungs,
so a tier is "over its pace" only when every rung is. A step picked by Fred (`pick`) may name a rung; `pick` is
validated with `known_model`.

### 3.9 Storage

- A note is capped: `tasks.NOTE_MAX = 20 * 1024` bytes after masking (`note_text` cuts the block at the cap and
  appends a line `[cut at 20 KB]`); the task prompt is cut at 6000 characters; `chain.jsonl` gets one line per
  transition. `tasks.prune(home, days)` removes only `done`, `stopped` and `stuck` tasks older than the cut-off.
- Clear on done: `tasks.clear(home, task, keep_last) -> list` deletes `steps/*.md` except the last good note when
  `keep_last`, and with `keep_last=False` the whole folder; it returns the step session ids so the service can
  delete `runs/<sid>.jsonl` and `runs/<sid>.json` through `runs.RunManager.forget(sid)` (new: deletes the two
  files of an ended run, never a live one). `advance` calls it when a task reaches `done` and
  `cfg["task_clear_on_done"]`; the chain log gets `task:done -> task:cleared` with the bytes freed in `why`.
  `task["cleared"]` is set so the Task page says `cleared: notes and streams removed` and shows no Open for the
  steps. The step sessions keep their rows (the event log) and their Chat falls back to the transcript.
- The sweep stays where it is (`console/__main__.py` at start, the daily tick); nothing is deleted by size.
- The Usage page's foot shows the data folder's size by subfolder from `usage.folder_sizes(home)` (one
  `os.walk`, run on the usage thread once an hour and at start, served in `/api/usage` as `"storage": {"runs":
  bytes, "tasks": bytes, "events": bytes, "preps": bytes, "other": bytes, "total": bytes}`); over
  `storage_warn_mb` the line turns orange. This is Task 4's last item and Task 5's last line.

### 3.10 Hard rules (from CLAUDE.md and BRAINSTORM, never relaxed by a task)

- `Hub.task_levers` is the only gate for `start`, `stop`, `retry`, `pause`, `resume`, `confirm`, `clear`; the hub loop and
  the POST handlers both call it; it uses `Hub.allowed` and the busy checks of `Hub.levers`. Several tasks of the
  same project may run at once (plan 20 replaced the old one-at-a-time refusal). Stop, Pause and Clear start nothing, so they
  do not need the project allowed, claude.exe or the folder.
- While its task is `planned`, `running` or `waiting`, a step session's own levers (Continue, Verify, Hand off,
  Escalate, De-escalate) answer `a task step: use the task's levers`, except Continue on the current step while
  the task waits on its question. `/api/stop` on the current step is the task's Stop (no retry follows).
- Once the task is `stopped`, Continue on the current step's session (not live: `Hub.levers` still refuses it
  while the run is going) is a new turn of that same session and resumes the task (`tasks.fred(task, "continue")`):
  the step goes back to `running`, the task to `running` with `owner` `service`, and `_ended` reads that turn's end
  like any step's (handoff, then the next step). Retry stays a fresh session from `last_good`.
- A step is one fresh `claude -p` with `--disallowedTools Agent`; no `Agent` tool call anywhere in the plan. The
  brief pass is a `claude -p` with no tools and one turn; it decides nothing.
- Stop is `runs.stop` (the stream-json interrupt). The chain never kills a process.
- Code never picks `fable`; `pick == "fable"` needs `fable_ok` (the confirm) before the step starts.
- `cc_events.py`, `install_hooks.py` and `~/.claude/settings.json` are not touched.
- `Hub.auto_steps` skips any session whose `task` is set (the chain owns task verdicts).
- No emojis or em-dashes in prompts, notes, window text or docs.

### 3.11 Drift guards for the executor

- Do not add a queue, a priority, a timer, a lock file, a lease, a second retry, a branch or a parallel step inside one task. Parallel tasks in one project are allowed (plan 20).
- Do not let a model write into the task folder; the service writes every file there.
- The next step's prompt carries the brief only: never the raw note, never earlier briefs, never a transcript.
- Do not pass a `--model` that is not a tier alias or a rung of the configured ladder; do not pin ids in code.
- Do not restructure `web/app.js`; add functions next to their nearest neighbour and keep the data-attribute
  event style (`data-act`, `data-go`, `data-open`).
- Do not change `prep_prompt.md`'s type table or the `route-model` skill (a test pins them).
- A test that cannot be made to fail first is a sign the step is already covered or wrong: stop and check.

## 4. Config keys added (`console/paths.py` DEFAULTS)

| key | default | used by |
|---|---|---|
| `task_retention_days` | 90 | `tasks.prune` (Task 4) |
| `task_step_budget_usd` | 3 | each step's `--max-budget-usd` |
| `task_max_steps` | 6 | `tasks.plan_steps` (Prep's list is cut there, before the verify is appended) |
| `opus_max_turns` | 12 | `--max-turns` on a `design` step |
| `budget_warn_at` | 0.8 | `step_route` step 7 (sub-plan 18 fills `Hub.budget()`) |
| `ladder` | the four tiers with their rungs (section 3.8) | `Hub.model_id`, `claude_cli.known_model` |
| `storage_warn_mb` | 500 | the Usage page's storage line |
| `task_clear_on_done` | true | `Hub.advance` when a task reaches `done` (README 3.9) |
| `brief_on` | true | the brief pass between steps (3.6b); false uses the code fallback |
| `brief_model` | "haiku" | `compact.run_brief` (through `Hub.model_id`) |
| `brief_max_words` | 400 | `compact.check` |
| `brief_timeout_s` | 60 | `compact.run_brief` |

## 5. Verification at the end of every task

```bat
py -m unittest discover -s tests
```

All earlier tests still pass; the task's new tests failed first. Task 5 also loads the page in headless Edge at
400 and 340 px against the fake claude (the command is in 05-window.md) and reads the screenshot for the slider,
the step list, the task card and the Task page.
