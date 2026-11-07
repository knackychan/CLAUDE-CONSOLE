# Plan 53: Build. An ordered list of sub-plans, run one task at a time, with the Console's own gates

Status: written 2026-11-07 from Fred's brief (a chat on 2026-11-07: "once the plans are done, a Goal/auto mode that
reviews the plan, edits it, implements a sub-plan, verifies it, steers on drift, re-implements, goes to the next
sub-plan, with the model engine choosing models as it goes"). D1 to D8 are written as defaults, recommended option
first; Fred changes them before anything is built. Plan only: no code, no config, no test changed by this plan's
writing. Lands on plans 17 (chain), 24 (plan and replan), 44 (supervisor), 47 (planner), 52 (autopilot: Tasks 1 to 4
are built at `ce9d64f`; Task 5 levels is recommended first, Task 6 `actions` is what the UI reads).

| # | File | Delivers | Depends on |
|---|---|---|---|
| 1 | [01-build-module.md](01-build-module.md) | `console/build.py`: the sub-plan list from a folder, build.json and build.jsonl, the state moves, the item prompt, spent and the summary; `tests/test_build.py` | nothing |
| 2 | [02-planner-drift.md](02-planner-drift.md) | the planner judges drift in a build: the Build context in its prompt, `drift` and `drift_note` in its answer, the kind file rule; the design kind adopts a sub-plan file; `tests/test_planner.py`, `tests/test_prep.py` | nothing |
| 3 | [03-service.md](03-service.md) | `Hub.builds`, the build tick inside `advance`, a prep started by the service, the task linked by its card, Accept and the one retry at `auto`, the cap, the routes, the snapshot rows; `tests/test_build_server.py` | 1, 2 |
| 4 | [04-window.md](04-window.md) | the Board: the build row, the build page (items, dock card, bar), the New build form; `tests/test_web.py` | 3 |
| 5 | [05-live-check.md](05-live-check.md) | Fred's live check on a real sub-plan folder | 4 |
| 6 | [06-close.md](06-close.md) | PLAN.md row and History, BRAINSTORM D17 and the section 2 note, CLAUDE.md line | 5 |

Tests first in every code task, one commit per task, `py -m unittest discover -s tests` at each boundary. Other chats
edit `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md` and `web/app.js` in parallel: anchored edits, stage only this plan's lines.
Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md). Design: BRAINSTORM 7.6 and the
locked `design/rework/locked/workflow-autopilot.html` (plan 52 Task 8: UI-1 to UI-9); this plan adds no visual
language, only one more card kind drawn with the same parts.

## 1. What Fred asked, and what the Console already does

The loop Fred described, step by step, against the code at `ce9d64f`:

| Fred's step | Exists | Where |
|---|---|---|
| review the plan | per task: the planner pass (opus, read-only, 10 tool calls) reviews the scope and writes the step list; the design step (opus) reads the repo and writes plan.md with the shape `plan.check` enforces | plan 47, plan 24 |
| edit the plan | per task: Fred edits plan.md through `POST /api/task/plan`; a step's `Replan:` line runs a bounded replan, applied without Confirm at `auto` | plan 24 |
| implement a sub-step | the chain: scout, design, code steps in order, a brief between, each step on its own model | plan 17, plan 52 Task 1 |
| verify | one verify after the last edit, one model up; FAIL inserts a fix on the escalated route and a second verify; a second FAIL is stuck | plan 17 |
| steer on drift | within a task only: verify FAILs a departure from plan.md (`plan.VERIFY_RULE`); a `Plan gap:` or `DECISION:` stops the task with a card | plan 24, plan 52 Task 3 |
| re-implement | the fix step; Retry on a model with a note; Redo design | plans 17, 33, 40 |
| the model engine | `tasks.step_route`: the kind's rule, Fred's pin, demand, the routing-miss floor, the hint, the pace cap, the balance over the tier's rungs by usage share (`fills`), a usage limit keeps a rung out (`Hub.rung_ok`) | plans 17, 18, 26, 35, 40, 45 |
| Fred only at real decisions | the DECISION card with a default taken after a timeout at `auto`; the finish card with Accept | plan 52 Tasks 3 and 4 |
| go to the next sub-plan | **missing**: a task is one chain; nothing holds an ordered list of sub-plans and starts the next after the previous one is accepted. Today Fred types the next prompt or uses Hand off / Create follow-up | plan 44 navigation |
| drift across sub-plans | **missing**: nothing compares what the finished sub-plans left with the build's goal before the next one starts | |
| a budget for the whole | **missing**: the caps are per step (`task_step_budget_usd`), per supervisor pass and per day; nothing counts the whole build | |

So plan 53 adds the list and its two boundary checks, and nothing else: no new step kind, no new pass, no new model
rule. Every sub-plan runs as an ordinary supervised task made from an ordinary Prep card, with the planner, the chain,
the supervisor, the caps and the routing it has today.

Out of scope was checked: BRAINSTORM section 2 names "a task graph" and "a scheduler" as non-goals, and plan 17 needed
D16 ("a linear step chain is not a task graph") to exist. A build is the same shape one level up: a list, one index,
advanced only when the previous item is accepted. D2 below is the clarification it needs; without Fred's yes on D2 this
plan is not built.

## 2. Target flow

```
NEW BUILD   Fred names a project, a folder of sub-plan files and (optional) a goal file; the preview lists the files
  |         in name order; Fred unticks any; Create. Nothing runs. The build is a row on the Board.
  |
START       POST /api/build/start. Item 1 goes `preparing`: the service sends the item prompt (section 4.4) to Prep
  |         (haiku) and the planner (opus) exactly as a typed prompt would; the card lands with the planner's
  |         scope note AND its drift word (Task 2).
  |
  |   gated (D1)                                      auto
  |   the card waits: `sub-plan 1 ready: Start`       drift major: held, Fred's card (Continue / Skip / Stop)
  |   Fred's Start on the card (unchanged POST        else: the service posts the card's steps itself:
  |   /api/task); create_task links the task to       create_task(card, card["steps"], supervised=True)
  |   the build by the card id (no new field)
  |
TASK        the plan 52 chain, unchanged: design adopts the sub-plan file (D7) and writes plan.md, code steps, verify,
  |         fix once, retry once, stuck; DECISION cards; the supervisor on exceptions; every hold and cap of today
  |
DONE        the task's finish card (plan 52 Task 4)
  |   gated: Fred's Accept (unchanged POST /api/task/accept)
  |   auto: the service accepts when the last verify PASSed, no open question is listed and no supervisor card is
  |         visible (D6); else it waits for Fred's Accept, as gated
  |
NEXT        item n closes `accepted` with its cost; the cap is checked (D4); `pause_after` honoured; item n+1 goes
  |         `preparing` with the done list and the open questions of item n in its prompt
  |
END         after the last item: build `done`, a summary in code (items, costs, files, open questions). No model pass.
```

What the build never does: it never starts a step, a run or a pass of its own (Prep, the planner and `create_task`
are the existing calls; the task does the rest); it never edits a sub-plan file or the goal file in the project; it
never runs two items at once; it never reorders items; it has no timer except D8's one retry; it never touches a task
that is not its current item; it never bypasses a task gate (Fable confirm, pace hold, DECISION without a default,
second failure, pending guidance, uncertain dispatch, Pause).

## 3. Decisions (defaults; Fred confirms or changes before Task 1)

| # | Question | Options | Written for |
|---|---|---|---|
| D1 | Autonomy of a build | (a) `gated`: Start and Accept of every sub-plan are Fred's clicks on the ordinary card and finish card; a drift note rides on the card; (b) `auto`: the service starts and accepts within the caps; (c) per build, default `gated`, switchable at any time from the build page, plus "Start, and run the rest automatically" on the first card | (c) with `gated` as the default: the first sub-plan is the one worth watching; a build that went through two or three cleanly can go `auto` |
| D2 | Non-goals | (a) BRAINSTORM D17: "an ordered list of sub-plans, each run as one task, advanced by the service only after the previous task is accepted, is not a task graph or a scheduler: no dependencies, no parallel items, no reordering at run time, no clock except one retry after a usage limit's reset (D8)"; (b) keep it out of scope: this plan is dropped and Fred uses a Claude Code workflow script for the loop | (a) |
| D3 | Who sees drift | (a) the planner pass of the next sub-plan (opus, read-only, already paid for): its prompt gets a Build context (the goal file, the done items with their files and open questions, this sub-plan file) and it answers `drift`: `none`, `minor` (the sub-plan needs small edits it names; the task may go on) or `major` (the remaining sub-plans no longer fit the code or the goal; what to change). `major` holds an `auto` build with a card; at `gated` the note rides on the card. The planner proposes edits as text and never writes a file; (b) one more `review` step at the end of each task on the think tier (a new kind, one more opus run per sub-plan) | (a): no new kind, no new pass, the judgment happens where the next work is being planned |
| D4 | Budget | (a) one cap per build, `cap_usd` (default `build_cap_usd` 25 in config, Tuning group "build"), checked before each item starts: over it the build holds (`cap: $26.10 of $25 spent`) with Raise cap / Stop; the per-step, supervisor and daily caps stay as they are; no per-day cap (plans 40 and 45 already hold a provider until its reset); (b) no build cap | (a) |
| D5 | Input | (a) a folder in the project; every `NN-*.md` file and every `NN-*/README.md` directly under it is one sub-plan, in number order then name order; a file without a leading number is not an item; `README.md` and `PLAN.md` of the folder itself are never items; the goal file is one path Fred names (`PLAN.md`, a spec, or none); Fred unticks items on the preview; (b) also split one file by its `## Task N` / `### Task N` headings (the superpowers plan shape) | (a); (b) is section 7 |
| D6 | Accept at `auto` | (a) the service accepts a done task when its last verify step says PASS (or the task has no verify), `tasks.summary` lists no open question and `supervisor.pending` shows no visible card; otherwise the build waits for Fred's Accept, as at `gated`, with the reason in its row; (b) always accept at `auto` | (a) |
| D7 | How a task takes its sub-plan file | (a) the planner, in a build, always plans one design step first whose goal is "Adopt `<file>`: review it against the repo and write the plan from it; every departure goes under Decisions", then the code steps; the design kind file says what adopting means (Task 2); the sub-plan file in the project is read, never written, by the Console; plan.md in the task folder and its mirror (plan 28) are the reviewed copy; (b) code steps straight from the file, no design step | (a): the design step is Fred's "review and edit the plan" moment, and it gives verify a plan.md to check the diff against |
| D8 | A usage limit on an unattended build | (a) when the current task is stuck with a `why` that names a usage limit (`limits.TEXT`) and every limit entry the step's model falls under has passed its `until`, the build retries that task once (`task_lever retry`, origin `build`, logged `retry by the build after the limit reset`); a second stuck waits for Fred; nothing else runs on a clock; (b) the build waits for Fred's Retry | (a): a limit reset at 03:00 should not cost a night |

A different answer changes only the lines the task files mark `D1` to `D8`.

## 4. The contract

### 4.1 Files and places

```
~/.claude/console/builds/<id>/build.json     the build (4.2); written by the service only, through a temp file
~/.claude/console/builds/<id>/build.jsonl    one line per move (4.3), append only
console/build.py                             the module (Task 1): pure, no threads, no HTTP; files only in load/save/log
tests/test_build.py, tests/test_build_server.py
```

- The id is `prep.new_id()`'s shape (`20261107-153000-7a1c`), the label `tasks.label(id)`.
- Nothing is written in the project. The sub-plan files and the goal file are read by the Console (the preview, the
  item titles) and by the task's steps; the task's plan.md mirror (plan 28) is the one project write that exists today.
- The files a build reads are masked like a note (`redact.mask`) wherever their text lands in a prompt or a file.
- `tasks.clear`, retention and Delete of a task never touch a build; Delete of a build (`POST /api/build/delete`)
  removes `builds/<id>/` only, never its tasks.

### 4.2 build.json

```json
{"id": "20261107-153000-7a1c", "project_dir": "D:\\WORK\\APP", "project": "APP", "title": "Packshots app, phase 1",
 "folder": "docs/superpowers/plans/2026-11-05-app", "goal_file": "docs/superpowers/specs/2026-11-05-app-design.md",
 "level": "gated", "cap_usd": 25.0, "state": "running", "owner": "service", "why": "", "current": 3,
 "pause_after": false, "created": 1762500000.0, "updated": 1762503600.0, "ended": null,
 "items": [
   {"n": 1, "file": "docs/superpowers/plans/2026-11-05-app/01-paths.md", "title": "Paths module", "state": "accepted",
    "prep": "20261107-153010-1b2c", "task": "20261107-153010-1b2c", "cost": 1.42, "drift": "none", "drift_note": "",
    "retried": 0, "why": "", "started": 1762500010.0, "ended": 1762501000.0},
   {"n": 2, "file": "docs/superpowers/plans/2026-11-05-app/02-settings.md", "title": "Settings", "state": "skipped",
    "prep": "", "task": "", "cost": 0, "drift": "", "drift_note": "", "retried": 0, "why": "skipped by Fred",
    "started": null, "ended": 1762501100.0},
   {"n": 3, "file": "docs/superpowers/plans/2026-11-05-app/03-render-queue/README.md", "title": "Render queue",
    "state": "running", "prep": "20261107-161000-9c3d", "task": "20261107-161000-9c3d", "cost": 0, "drift": "minor",
    "drift_note": "02 was skipped: the queue must read SETTINGS_FILE itself", "retried": 0, "why": "",
    "started": 1762501110.0, "ended": null}
 ]}
```

- `level`: `gated` or `auto` (D1). `cap_usd`: a number, 0 means no cap (D4). `folder` and `goal_file` are paths
  relative to `project_dir`, forward slashes, as Fred typed them; `goal_file` may be `""`.
- Build `state`: `planned` (created, never started), `running`, `waiting` (the build itself needs Fred: 4.5), `stopped`,
  `done`. `owner`: `service` or `fred` (`fred` while paused after an item, as a task's Pause). `why`: the reason of the
  current `waiting` or `stopped` state, shown in the row; `""` otherwise. `current`: the `n` of the item in progress,
  0 before Start, `len(items) + 1` when done.
- Item `state`: `planned`, `preparing` (its Prep job runs), `ready` (`gated`: the card waits for Start), `held`
  (`auto` drift `major`, a failed Prep, or the cap: `why` says which), `running` (a task exists and is not accepted),
  `accepted`, `skipped`, `failed` (its task was deleted: `why = "task deleted"`). `prep` is the Prep job id (the
  task id too, plan 29); `task` the task id once one exists. `cost` is written once when the item closes: the task's
  step costs plus its card's `cost` (Prep and the planner). `retried` counts D8's retry (0 or 1).
- `build.whole(b)` checks the keys above (`BUILD_KEYS`, `ITEM_KEYS`); `load_all` skips a file that is not whole, as
  `tasks.load` does.

### 4.3 build.jsonl lines

`{"ts": 1762500010.0, "n": 1, "from": "item:planned", "to": "item:preparing", "why": "prep 20261107-153010-1b2c"}`;
`n` is 0 for a build-level move. The `why` words, in the order they happen:

| `why` | When |
|---|---|
| `created: 9 items from docs/.../plans, goal docs/.../spec.md` | `POST /api/build` |
| `started by Fred` / `started at level auto` | `POST /api/build/start` |
| `prep <job id>` | an item's Prep job started (a restart writes `prep again <job id>: the service restarted`) |
| `ready: 4 steps, drift none` | the card landed at `gated` |
| `started by Fred on the card` / `started by the build: 4 steps` | the task was created (the card's Start, or `auto`) |
| `held: drift major: <note>` / `held: prep failed: <error>` / `held: cap: $26.10 of $25 spent` | 4.5 |
| `continued by Fred` | `POST /api/build/continue` on a hold |
| `retry by the build after the limit reset` | D8 |
| `accepted by Fred` / `accepted by the build: verify PASS, no open question` | the item closes (cost in the line: `, $1.42`) |
| `skipped by Fred` | `POST /api/build/skip` |
| `task deleted` | the item's task left `Hub.tasks` |
| `paused after 03 by Fred` / `resumed by Fred` | `pause_after` took effect; Resume |
| `level gated -> auto by Fred` / `cap 25 -> 40 by Fred` | the switches |
| `stopped by Fred` | `POST /api/build/stop` (the current task gets the task Stop first) |
| `done: 8 accepted, 1 skipped, $84.20` | the last item closed |

### 4.4 The item prompt (`build.prompt`)

What Prep receives as the typed prompt of item n (the task's `prompt.md` and `00-prep/prompt.md`, as any prompt):

```
Build "<title>", sub-plan <n> of <N>: <item title>.
Sub-plan file: <item file>. Read it first. Its Files, Actions, Tests and Done check are this task's whole scope: do
not do the work of a later sub-plan, and do not redo an earlier one.
Goal of the whole build: <goal file> (read its Goal and Decisions; this task keeps to them).   [line absent when ""]
Done before this one:
- 1 Paths module: accepted; files src/core/paths.ts, src/core/paths.test.ts
- 2 Settings: skipped
Open questions left by sub-plan 1:                                                            [absent when none]
- which env var names the sheets folder?
When the sub-plan file no longer matches the code as it is now, do not guess: stop with a DECISION block (follow the
file / follow the code / stop) and name the stale lines.
```

Limits: `done` lists at most `DONE_SHOWN` 20 items and 6 files each (`... N more`); open questions at most 6; the
whole prompt under `tasks.GOAL_MAX` (6000). Paths are relative to the project with forward slashes. The prompt is the
only text the build writes into a task; the step prompts are the chain's own.

### 4.5 When the build waits for Fred (`state: waiting`, the row says it)

| `why` | Set when | Fred's moves (section 5) |
|---|---|---|
| `sub-plan 3 ready: Start` | `gated`: the card landed | Start on the card (as any card), Edit steps, Skip, Stop |
| `sub-plan 3: drift major: <note>` | `auto`: the planner said `major` | Continue (the task starts from the card as it is), Skip, Stop; Fred edits the files himself meanwhile |
| `sub-plan 3: prep failed: <error>` | the Prep job failed or the planner left no steps and Prep's own list is empty | Continue (Prep again), Skip, Stop |
| `cap: $26.10 of $25 spent` | before an item starts, `spent >= cap_usd` (D4) | Raise cap, Stop |
| `sub-plan 3 done: Accept` | `gated`: the task is done; or `auto` and D6 refused (the reason follows: `2 open questions`, `verify FAIL`, `supervisor card`) | Accept on the task (as any task), Reopen, Skip, Stop |
| `sub-plan 3: task deleted` | the task is gone | Continue (Prep again), Skip, Stop |
| `paused after 03` | `pause_after` and the item closed | Resume, Stop |

While the current task itself needs Fred (a question, a hold, a supervisor card, stuck), the build stays `running` and
its row shows the task's own status line after the item number (`03 · needs you · <question>`): the task's page has the
moves; the build adds none.

### 4.6 The planner's Build context (Task 2)

`card["build"] = {"id", "n", "of", "title", "file", "goal_file", "done": [{"n", "title", "state", "files"}],
"questions": [...]}` is saved on the card by `prep.run_prep` when `Hub.start_prep` was given a build, and
`planner.build_prompt` appends, after "Prep's proposed steps":

```
Build context (sub-plan 3 of 9 of "Packshots app, phase 1"):
Goal file: docs/.../spec.md
This sub-plan: docs/.../03-render-queue/README.md
Done so far:
- 1 Paths module: accepted; files src/core/paths.ts, src/core/paths.test.ts
- 2 Settings: skipped
Open questions carried: which env var names the sheets folder?
Judge drift (the rule in your kind file): does this sub-plan still fit the code the done sub-plans left and the goal?
```

The answer's `drift` (`none` | `minor` | `major`) and `drift_note` (one line, `NOTE_MAX`) are optional in
`planner.SCHEMA` (the `required` list is unchanged, so a pass outside a build answers as today) and land in
`card["planner"]`. A missing `drift` in a build reads `none` with the note `the planner did not judge drift`.

### 4.7 Routes

| Route | Body | Does |
|---|---|---|
| `POST /api/build/preview` | `{project_dir, folder, goal_file?}` | `build.items_from(project_dir, folder)` and the goal file's existence; `{items: [{n, file, title, words}], goal_ok, error}`; writes nothing; 403 outside config.json projects, 400 for a path outside the project or a missing folder |
| `POST /api/build` | `{project_dir, folder, goal_file?, title?, keep?: [n...], level?, cap_usd?}` | creates `builds/<id>/`, state `planned`; `keep` lists the item numbers of the preview to keep (default all, order kept); `{build: id}` |
| `POST /api/build/start` | `{build}` | `planned` or `stopped` -> `running`, owner `service`; the tick starts item `current` (1 after creation; the current item again after a Stop, as a Retry would) |
| `POST /api/build/stop` | `{build}` | `task_lever(stop)` on the current task when it runs; the item stays `running` with its task; build `stopped` |
| `POST /api/build/pause` / `resume` | `{build}` | `pause_after` true (the current item finishes, then owner `fred`); Resume: owner `service` |
| `POST /api/build/skip` | `{build, n}` | item `n` -> `skipped` when it is the current item without a live task (planned, preparing, ready, held, done, failed) or a later planned item; a `preparing` item's job is dropped (`drop_prep`); 409 otherwise |
| `POST /api/build/continue` | `{build}` | on `held` drift: `create_task` from the saved card; on `held` prep failed or `failed` task deleted: Prep again; 409 on a cap hold ("raise the cap first") |
| `POST /api/build/level` | `{build, level}` | `gated` or `auto`; takes effect at the next move (a `ready` item stays ready: Fred is already on its card) |
| `POST /api/build/cap` | `{build, cap_usd}` | 0 to 10000; a cap hold clears on the next tick when `spent < cap_usd` |
| `POST /api/build/delete` | `{build}` | not while `running` with a live task (409: stop first); removes `builds/<id>/` |
| `GET /api/build?id=` | | `{build, items: [{..item, task_row | null, card | null}], spent, summary | null, chain: [...]}` |

The card's Start (`POST /api/task`, unchanged body) and the task's Accept (`POST /api/task/accept`) are the `gated`
moves: `create_task` links the task when the card id is an item's `prep`. `GET /api/state` gains `builds`: one
`build.row(b, tasks_rows)` each (4.8). Every route passes `guard` as today; bodies are validated like the task
routes (`tasks.safe_id` on ids, paths as text under the project).

### 4.8 The row (`build.row`)

`{"id", "label", "title", "project", "project_dir", "state", "owner", "why", "level", "cap_usd", "spent", "current",
"count", "done": accepted + skipped, "group": needs | working | done, "line": the status line, "updated",
"item": {n, title, state, task, prep} of the current item}`. `group` is `needs` when the build waits (4.5) or the
current task's row is in `needs`; `done` when `done` or `stopped`; else `working`. `line` is the one sentence of
section 5. The Board draws the row from this and nothing else (plan 36 3.4: no business rule in the page).

## 5. The window (Task 4; the parts are plan 52 Task 8's, nothing new drawn)

- **New build**: an entry "New build…" in the header menu opens a form in the inspector pane: project (the scope's
  project, or the picker), folder, goal file, title, level (gated / auto), cap; Preview lists the items with a checkbox
  each and the goal file's state; Create makes the build and opens its page. Nothing starts.
- **The row**, in the list like a task row (mark, title, status line, cost), grouped by `group` today and under its
  project once plan 52's UI-1 lands. Status lines: `build · 3 of 9 · 03 running 02 code · sonnet · 3 min`;
  `needs you · sub-plan 3 ready: Start`; `needs you · 03 · <the task's own line>`; `held · drift major: <note>`;
  `paused after 03`; `stopped · 3 of 9`; `done · 8 sub-plans · $84.20`.
- **The page** (plan 52 UI-3 head, UI-4 body): eyebrow the project, the title, the meta line (state pill, Now: sub-plan
  3 of 9, Level: gated / auto as the UI-3 switch, Spent $12.40 of $25 in Doto). Body, one section pattern:
  - Goal: the goal file path (a copy icon) and the folder.
  - Sub-plans: one row per item, as UI-5 draws steps: rail mark, number, title, state word (planned, preparing, ready,
    held, running, done, accepted, skipped, failed), cost; a row with a task opens the task page; a `ready` row opens
    its card; a `drift` line under a row that has a note (`◆ drift minor: <note>`), muted.
  - Done: the summary (items, files, open questions) when the build is done.
- **The dock card** (UI-7), empty unless 4.5 applies: a tag (`Ready`, `Drift`, `Prep failed`, `Cap`, `Accept`,
  `Paused`), one sentence, its buttons with the primary at the right: Ready: Skip / Open the card; Drift: Stop / Skip /
  Continue; Prep failed: Skip / Continue; Cap: Stop / Raise cap (a number field); Accept: Skip / Open the task; Paused:
  Stop / Resume. "Start, and run the rest automatically" sits on the first item's card as a second Start (plan 52's
  "and auto accept" shape): `POST /api/build/level {level: auto}` then the card's Start.
- **The bar** (UI-8): icon tools left (Folder: the build folder in Explorer; Delete), the spend, then Stop, Pause after
  this sub-plan / Resume. No message box: a build takes no words; the task's page has it.
- Every button posts a 4.7 route or the task's own; the page shows a button only when the service's row allows it
  (`GET /api/build` carries `actions`: the same `{id, label, post, body, off}` shape as plan 52 Task 6).

## 6. Cost of a build

Per sub-plan, the same as a supervised task today (plan 52 section 4): Prep $0.005, planner $0.12 to $0.5, design on
opus $0.3 to $1, code $0.1 to $0.3 each, verify $0.05, briefs $0, supervisor $0 when nothing goes wrong. The build adds
$0: the drift judgment rides in the planner pass (D3), the summary and the accept rule are code (D6). A nine-sub-plan
app at $1 to $3 each lands at $10 to $30, which is why `cap_usd` defaults to 25 (D4). Fred's clicks at `gated`: Start
and Accept per sub-plan; at `auto`: none on a clean run.

## 7. Not done here

- One file split into tasks by its `## Task N` headings (D5 b): a later line in `build.items_from` once a build has run
  from a folder.
- Dependencies, parallel items, a reorder at run time, a retry policy of its own (D2: non-goals).
- Editing a sub-plan file from the Console: the drift note is text; Fred edits in his editor.
- A project-level replan (the planner rewriting the remaining sub-plans): the planner proposes in `drift_note` only.
- The Board's project groups (plan 52 UI-1) and the web build of the locked design (plan 52 D9): the build row and page
  are drawn with today's list and inspector; they move with that web task.
- The Claude Code workflow route (a script that loops over sub-plans with fixed models) stays an alternative Fred can
  take without this plan; it has no usage balancing, no limit holds and no Board.

## 8. Assessment before building (2026-11-07, asked by Fred: "could the app be built this way?")

Verdict: yes, under three conditions (the last list below). The plan is small because everything inside one
sub-plan already exists; the risk is not in plan 53's code, it is in what it stacks on and in how the sub-plans are
written.

What holds up:

- Every piece inside one sub-plan exists and is tested: the chain, the plan.md shape check, verify one model up, the
  fix insert, the DECISION card, the finish card, the supervisor on exceptions, routing with its pace and limit holds.
  Plan 53 adds the list, one drift check and one cap. A small surface, little room for new bugs.
- The model engine is the strong part (routing per kind, usage balance, limit holds, floors from misses) and plan 53
  does not touch it.

Where the doubt is:

1. **The foundation has not run live.** Plan 52 Tasks 1 to 4 landed on 2026-11-07 and no live check has run. The first
   supervised task, on 2026-10-20, died at step 1 (plan 52 section 1). A chain that stalls on one task stalls nine
   times in a build.
2. **D7 (the design step adopts the file) is the weakest decision.** Opus rewrites the sub-plan into the PLAN shape at
   $0.3 to $1 per sub-plan; a sub-plan in another shape can fail `plan.check`, retry and go stuck. The fallback is cheap
   (D7 b: code steps read the file, verify checks the step goal only) and can be taken after the first live run.
3. **Sub-plans must be small.** `task_max_steps` 6, `plan_max_parts` 6, one verify after the last edit. A sub-plan the
   size of plan 44 (12 tasks) must be split into files of one to three code steps, each with a done check that is a
   command. Verify reads diffs and runs tests; it cannot see a screen. An app without tests gets a build that proves
   little.
4. **Unattended nights.** The pace hold (`over its pace`, Fred's Run anyway) and the Fable confirm are Fred's at every
   level, and the design step is opus on every sub-plan. With Fred's pace allowances set, an `auto` build will stop on
   a pace hold overnight; D8 covers the usage-limit reset only. Either accept a click in the morning, or extend D8 to
   the pace hold later, once a build has shown where it stops.
5. **Coherence across sub-plans rests on little.** Each step is a fresh session with a 500-word brief and plan.md (by
   design, for cost). Across sub-plans only the goal file and the planner's drift judgment (read-only, 12 turns, no
   git) hold the line. Medium judgment, not strong; a goal file with a clear Decisions section matters more than any
   code here.

Cost: $10 to $30 for nine clean sub-plans; retries, fixes and a redo add 30 to 50 percent. The default cap of 25 will
hit mid-build on a first app; set 60 for it.

Conditions before Task 1:

- Plan 52's live check passes on two or three real tasks (and Task 5 is built, section 9 step 2).
- The first app's sub-plans are written small and command-checkable, in one folder, with a goal file that closes the
  decisions.
- The first build runs on a throwaway branch at `gated`; two sub-plans watched, then `auto`.

D3 and D7 stay as written: both downgrade cheaply if they misbehave. The Claude Code workflow script remains the
fallback if the Console route disappoints; switching costs nothing, since the sub-plan files are the same input.

## 9. Order and checks

1. Fred reads D1 to D8; a changed answer is written into this README and the task files before Task 1.
2. Plan 52 Task 5 (levels) first, recommended: a build at `auto` then starts tasks whose plan hold is already the
   project's business; without it a build works, with `supervisor_mode` off / suggest / auto as today.
3. Tasks 1 to 4 in order, tests first, one commit each (`feat: ... (plan 53 Task N)`), the full suite at each boundary,
   `node --check web/app.js` after Task 4; stage only this plan's lines.
4. Task 5 is Fred's; Task 6 closes.
