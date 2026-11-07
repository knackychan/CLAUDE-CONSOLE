# Plan 53: Build. An ordered list of sub-plans, run one task at a time, with the Console's own gates

Status: written 2026-11-07 from Fred's brief (a chat on 2026-11-07: "once the plans are done, a Goal/auto mode that
reviews the plan, edits it, implements a sub-plan, verifies it, steers on drift, re-implements, goes to the next
sub-plan, with the model engine choosing models as it goes"). D1 to D8 are written as defaults, recommended option
first; Fred changes them before anything is built. Plan only: no code, no config, no test changed by this plan's
writing. Lands on plans 17 (chain), 24 (plan and replan), 44 (supervisor), 47 (planner), 52 (autopilot: Tasks 1 to 6
built, `c9b9f00` to `282feca`; Task 7 headless `29fcc73`, its live check is Fred's and open; `GET /api/task` `actions`
is what the UI reads) and 54 (`paths.write_text_atomic`, `c0793b3`). Refreshed 2026-11-07 against `9b6f988` (1167
tests OK): not ready to build, see section 9.

### Change list of the 2026-11-07 refresh (D1 to D8 untouched, D9 added; each item names where it landed)

1. Code references re-checked against HEAD and corrected. What moved is the table at the top of `03-service.md`; the
   `ce9d64f` baseline is now the fourth of six plan 52 commits this plan stacks on.
2. Built facts replace "Task 5 levels recommended first": section 2.1 (four levels, `gated` the default, the
   `remember: "auto"` routes, Accept, `actions`) and one new decision, D9, for how the build level composes with the task
   level without a second gate (written as a default; Fred answers it with D1 to D8).
3. Writes: `build.json` goes through `paths.write_text_atomic` (plan 54) under `Hub.tlock`; `build.jsonl` is append only.
   Task 1 says so and has two tests (4.1, `01-build-module.md`).
4. Task 4 names its seam with plan 55 (`04-window.md`, "Seam contract"). Plan 55 is an uncommitted draft whose section 7
   already names the parts (`pageHead`, `sect`, `planRow`, `dockCard`, `barHtml`, `projectGroups`); the contract quotes
   those names as provisional and must be checked against the committed plan. Three web claims were wrong and are fixed: `sect()` does not exist in
   `app.js`, a `board_build` key cannot ride `/api/draft`, and the Models page needs `TUNE` and `MGROUP` entries.
5. Failure paths: section 4.9, 19 rows, each with an outcome and a test. Eleven outcomes are new (restart re-seat, task
   linked after a crash, `drop_prep`, planner failure at `auto`, project unavailable, two builds, a folder changed
   after the preview, a missing file, a refused lever, a nested tick, a failed save).
6. Contract corrections found while checking code: the item prompt passes through Prep's rewrite (a code guard keeps
   the scope line, Task 2); its DECISION line contradicts the design kind; the auto Accept must wait for the last brief
   and the done wake (D6 note); an item keeps its `files` and `questions` so a Deleted task loses nothing; `keep` is a
   list of files plus a `digest`; `limit_stuck` takes its key from the stuck why; the supervisor is not $0 (one haiku
   done wake per sub-plan, section 6); a failed planner now holds an `auto` build (F19), which changes the old Task 3
   test that `PLANNER-FAIL` never holds.
7. Added, small: `build.lint` (warnings on the preview), a headless acceptance script before Fred's live check (Task 5),
   section 8.1 (downgrade recipes: D3 (b) as written is a new step kind, not cheap), section 9 Readiness. The old
   section 9 "Order and checks" is now section 10.

| # | File | Delivers | Depends on |
|---|---|---|---|
| 1 | [01-build-module.md](01-build-module.md) | `console/build.py`: the sub-plan list from a folder with its lint and digest, build.json (through `paths.write_text_atomic`) and build.jsonl, the state moves, the item prompt, spent, the accept and limit rules and the summary; `tests/test_build.py` | nothing |
| 2 | [02-planner-drift.md](02-planner-drift.md) | the planner judges drift in a build: the Build context in its prompt, `drift` and `drift_note` in its answer, the kind file rules (adopt, drift, separate paragraphs); the design kind adopts a sub-plan file; Prep's scope guard on the card; `tests/test_planner.py`, `tests/test_prep.py` | nothing |
| 3 | [03-service.md](03-service.md) | `Hub.builds`, the build tick inside `advance`, a prep started by the service, the task linked by its card (and its task level by D9), Accept and the one retry at `auto`, the cap, restart recovery, the routes, the snapshot rows, `actions`; `tests/test_build_server.py` | 1, 2 |
| 4 | [04-window.md](04-window.md) | the Board: the build row, the build page (items, dock card, bar), the New build form, drawn with plan 55's parts through a written seam; `tests/test_web.py` | 3, and plan 55 (seam contract) |
| 5 | [05-live-check.md](05-live-check.md) | a headless acceptance script (Claude's, real HTTP, fake claude) and Fred's live check on a real sub-plan folder | 3 (script), 4 (live check) |
| 6 | [06-close.md](06-close.md) | PLAN.md row and History, BRAINSTORM D17 and the section 2 note, CLAUDE.md line | 5 |

Tests first in every code task, one commit per task, `py -m unittest discover -s tests` at each boundary. Other chats
edit `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md` and `web/app.js` in parallel: anchored edits, stage only this plan's lines.
Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md). Design: BRAINSTORM 7.6 and the
locked `design/rework/locked/workflow-autopilot.html` (plan 52 Task 8: UI-1 to UI-9); this plan adds no visual
language, only one more card kind drawn with the same parts.

## 1. What Fred asked, and what the Console already does

The loop Fred described, step by step, against the code at `9b6f988` (the table was written at `ce9d64f`; nothing in it
changed meaning when plan 52 Tasks 5 and 6 landed):

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

### 2.1 What plan 52 built, as this plan uses it (checked at `9b6f988`), and D9

This replaces the earlier "Task 5 levels recommended first": Task 5 is built (`a06147f`), so a build stacks on it.

- Levels. `supervisor.MODES = ("off", "suggest", "gated", "auto")`, default `gated` (`paths.DEFAULTS["supervisor_mode"]`),
  one per project in `supervisor_projects`, one per task in `task["supervisor"]["mode"]` (`supervisor.initial`,
  `Hub._level`). `POST /api/task` takes `supervised: true` plus an optional `supervisor_mode` (400 without `supervised`);
  `create_task(card, steps, effort, title, *, supervised, supervisor_mode)` sets the task's own mode. A saved task keeps it.
- What a level does inside one task. `gated`: the task waits once at `plan ready: confirm` after its design step (Fred's
  Confirm), applies replans itself, waits on every DECISION and dispatches the other supervisor moves like `auto`. `auto`: no
  plan hold unless config `plan_hold`, a DECISION default is taken after `decision_timeout_s` (600 s), supervisor moves
  stay inside the caps. Hard stops at every level: Fable confirm, pace and usage holds, a second verify FAIL, the caps,
  Pause, Stop, Delete, a DECISION without a default.
- `remember: "auto"`. `POST /api/task/confirm {task, remember: "auto"}` (the plan hold only) and `POST /api/task/message
  {mode: "answer", text: <the default>, remember: "auto"}` write the project's level into `supervisor_projects` and the
  task's own mode, then pass that gate. They are task gates: a build never calls them and never writes
  `supervisor_projects`.
- Accept. `POST /api/task/accept` (lever `accept`): only on a `done` task, once; sets `task["accepted"]` and the chain
  line `accepted by Fred`; 409 while guidance is pending. `GET /api/task` carries `summary` (steps, files, still-open
  questions, cost, `accepted`) on a done task and `actions` in every state (`done`: primary `accept`).
- A done task is not settled at once. Its last brief is written after the state turns `done` (`task["briefing"]`,
  `Hub.briefing`), and the done wake (one haiku pass, `supervisor.boundary` trigger `done`, 20 s debounce) may then leave
  a card. The open questions in `summary` come from the last brief.

D9, how a build composes with the task level (new; default (a), for Fred with D1 to D8). The build level (D1) decides only
who makes the two moves between sub-plans, Start and Accept. Everything inside a sub-plan (plan confirm, replans,
DECISIONs, holds, the supervisor) stays the task level's. The build adds no gate, so no sub-plan is gated twice by two
settings:

| Build level | Starts sub-plan n | Accepts it | Task level of its task | Fred's clicks per sub-plan |
|---|---|---|---|---|
| `gated` | Fred: Start on the card, the ordinary `POST /api/task` | Fred: Accept | the project's (global default `gated`) | Start, Confirm plan (the task's own gate; gone when the project is `auto`), Accept |
| `auto` | the service: `create_task` from the card's steps | the build, through the accept lever, by D6 | `auto` | none on a clean run |

One rule carries it: `Hub._build_mode(card_id)` returns `"auto"` when the card is the `prep` of a build item and that build
is at level `auto`; `create_task` uses it when the caller named no `supervisor_mode`. The service's own start and the
card's Start after "Start, and run the rest automatically" both make an `auto` task, and the project's setting is not
changed (a build at `auto` is a per-build choice, like the task menu's per-task level). A build at `gated` asks nothing
of the task. A level change on the build page takes effect at the next sub-plan; a running task keeps its mode (its own
menu changes it). Option (b): the build never sets a task level, so an `auto` build in a `gated` project stops at every
plan confirm and is not unattended.

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
| D9 | How the build level composes with the task level (new, 2026-11-07; section 2.1) | (a) the build level decides only who makes Start and Accept; an `auto` build creates its tasks at task level `auto` (`Hub._build_mode`), a `gated` build leaves the task at the project's level; (b) the build never sets a task level | (a): without it an `auto` build in a `gated` project waits at every plan confirm |

A different answer changes only the lines the task files mark `D1` to `D9`.

Notes from the 2026-11-07 refresh. The decisions above are unchanged; these say what the built code makes them mean.

- D4. `spent` is the closed items' `cost` plus the current task's steps plus its card's Prep and planner cost. Brief passes
  and supervisor passes are not in it (each costs under a cent or two and the supervisor has its own task and day caps,
  plan 44). The default stays 25; Fred's condition for a first app is 60, set on the New build form (or the config key).
- D5. The preview also runs `build.lint` (Task 1), mechanical warnings that never refuse a Create: per item, no `Done
  check` followed by a command (a backticked or fenced line), more than `LINT_WORDS` (1200) words, more than `LINT_TASKS`
  (3) `Task` or `Step` headings; for the goal file, no `Decisions` heading, or one of `TBD`, `TODO`, `choose`, `either`,
  `if needed` under it (the words the design kind bans from Decisions). The two thresholds are defaults for Fred.
- D6. The built Accept is a lever, so the build calls `task_lever(id, "accept", origin="build")` and reads its answer: a
  409 (pending guidance, the project off the list) is not retried in a loop; the build waits with that reason. The rule
  also needs the task settled (last brief written, no done wake queued or running), because the open questions come
  from the last brief and the done wake may propose another step. The five conditions: state `done` and not accepted; the
  last verify PASSed or there is none; `summary["questions"]` empty; no supervisor card (pending status in
  `supervisor.VISIBLE` plus `uncertain` and `dispatching`); settled. `Hub.actions(task)` (plan 52 Task 6) lists the
  same Accept with `off` taken from `task_levers["accept"]`; the build calls the lever, not `actions`, which is the page's
  projection, so the build does not depend on the UI contract. D6 still holds as written: it only adds `settled` and
  the 409 handling.
- D7. The design kind already uses the word "Sub-plans" for the parts of a split plan (`## Sub-plans`, `SUBPLAN n`
  blocks). Task 2's sentence says so, so a model does not read a build's sub-plan file as one of those.
- D8. A limit hit while a step runs is retried by the chain first (plan 17), on another rung when one is free; the stuck
  state D8 acts on arrives only when no rung is free. The key to test is the one in the stuck `why` (the text starts
  `<key>: `), because a step that never started has no `limit` of its own. A reset the CLI did not name expires after
  `limit_cooldown_s` (3600) and may be early: the one retry is then spent and the second stuck waits for Fred. The
  supervisor's stuck wake may retry first inside plan 44's caps; D8 is the build's one extra. A limit that hits Prep or the
  planner writes no `limits.json` entry, so D8 does not cover it: the item is held (4.9, F6) and waits for Fred.

## 4. The contract

### 4.1 Files and places

```
~/.claude/console/builds/<id>/build.json     the build (4.2); written by the service only, whole, through paths.write_text_atomic
~/.claude/console/builds/<id>/build.jsonl    one line per move (4.3), append only, as chain.jsonl is
console/build.py                             the module (Task 1): pure, no threads, no HTTP; files only in load/save/log
tests/test_build.py, tests/test_build_server.py
```

- Writes (plan 54). Every whole-file write of a build, `build.json` today and any file a later change adds, calls
  `paths.write_text_atomic(path, text)` and nothing else: no `.tmp` of its own, no `os.replace`, no in-place write, no
  save retry loop. That keeps whole-file replacement while a metadata reader such as Listary holds the file open; genuine
  write errors and incompatible content locks still refuse the save. The call runs under `Hub.tlock`, the lock every
  build move already takes, so a build save never interleaves with a task move. `build.jsonl` is an append
  (`open(..., "a")`, like `tasks.log`): an append replaces no file, and plan 54 does not cover it. `build.delete` is
  `shutil.rmtree`. Task 1 and its tests say this (`test_save_uses_the_shared_writer`,
  `test_save_while_a_metadata_reader_is_open`).
- The id is `prep.new_id()`'s shape (`20261107-153000-7a1c`, 20 characters, so `tasks.safe_id` accepts it), the label
  `tasks.label(id)`; `Hub.create_build` draws again when `builds/<id>` already exists.
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
    "retried": 0, "why": "", "sha": "9f2c01ab33d4e7a1", "files": ["src/core/paths.ts", "src/core/paths.test.ts"],
    "questions": ["which env var names the sheets folder?"], "started": 1762500010.0, "ended": 1762501000.0},
   {"n": 2, "file": "docs/superpowers/plans/2026-11-05-app/02-settings.md", "title": "Settings", "state": "skipped",
    "prep": "", "task": "", "cost": 0, "drift": "", "drift_note": "", "retried": 0, "why": "skipped by Fred",
    "sha": "", "files": [], "questions": [], "started": null, "ended": 1762501100.0},
   {"n": 3, "file": "docs/superpowers/plans/2026-11-05-app/03-render-queue/README.md", "title": "Render queue",
    "state": "running", "prep": "20261107-161000-9c3d", "task": "20261107-161000-9c3d", "cost": 0, "drift": "minor",
    "drift_note": "02 was skipped: the queue must read SETTINGS_FILE itself", "retried": 0, "why": "",
    "sha": "41d0be77c2a9015e", "files": [], "questions": [], "started": 1762501110.0, "ended": null}
 ]}
```

- `level`: `gated` or `auto` (D1). `cap_usd`: a number, 0 means no cap (D4). `folder` and `goal_file` are paths
  relative to `project_dir`, forward slashes, as Fred typed them; `goal_file` may be `""`.
- Build `state`: `planned` (created, never started), `running`, `waiting` (the build itself needs Fred: 4.5), `stopped`,
  `done`. `owner`: `service` or `fred` (`fred` while paused after an item, as a task's Pause). `why`: the reason of the
  current `waiting` or `stopped` state, shown in the row; `""` otherwise. `current`: the `n` of the item in progress,
  0 before Start, `len(items) + 1` when done.
- Item `state`: `planned`, `preparing` (its Prep job runs), `ready` (`gated`: the card waits for Start), `held`
  (`auto` drift `major`, a failed Prep, a failed planner at `auto`, a missing sub-plan file, a dropped card or the cap:
  `why` says which), `running` (a task exists and is not accepted), `accepted`, `skipped`, `failed` (its task was
  deleted: `why = "task deleted"`). `prep` is the Prep job id; `task` the task id once one exists. They are the same
  id unless a task already held the card's id (`Hub._free_id`), so a task is matched to its item by
  `tasks.prep_id(task) == item["prep"]`, never by comparing the two strings. `cost` is written once when the item
  closes: the task's step costs plus its card's `cost` (Prep and the planner). `retried` counts D8's retry (0 or 1).
- Item `sha` (new): the first 16 hex characters of the sha256 of the sub-plan file's bytes when the item's Prep starts
  (`""` before, and for a skipped item). It only feeds a note (4.9, F12); nothing is held on it.
- Item `files` and `questions` (new): written once, with `cost`, when the item closes (`close_item`): the task summary's
  deduplicated files and its still-open questions at that moment. The next item's prompt and the build summary read
  these, never the task folder, so a Delete of an accepted task (or `task_retention_days`) loses nothing.
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
| `recovered: card re-seated after the service restarted` | the first tick after a start found the item's saved card whole (4.9, F1 and F2) |
| `ready: 4 steps, drift none` | the card landed at `gated` |
| `started by Fred on the card` / `started by the build: 4 steps` | the task was created (the card's Start, or `auto`); `, recovered` is added when the tick found the task a crash left (F3) |
| `file edited after its card` | the task was linked and the sub-plan file's sha differs from the item's `sha` (note only, F12) |
| `held: drift major: <note>` / `held: prep failed: <error>` / `held: planner failed: <error>` / `held: file missing: <file>` / `held: card dropped by Fred` / `held: cap: $26.10 of $25 spent` | 4.5 |
| `project: <reason>` | build level: `Hub._base` refused (the project left config.json, claude.exe is gone, the folder is gone); cleared by itself (F13) |
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

What Prep receives as the typed prompt of item n. It is stored as the task's `prompt.md` (as typed, plan 29); the task's
goal is not this text but Prep's rewrite of it (`card["prompt"]`, six labelled fields, saved as `00-prep/prompt.md`), so
the lines below reach the steps only as far as Prep and the planner carry them. Two things make that safe: the planner
sees this text as "Request as typed", and `prep.run_prep` guards the card in code when it is given a build (Task 2,
`prep.build_guard`): the sub-plan number and file go at the head of the card's `Goal` and the "no other sub-plan" rule at
the end of its `Keep`. Every step prompt carries the task goal (whole for step 1, its first 600 characters after that,
`tasks.PROMPT_GOAL_MAX`), so the file is named there whatever Prep wrote. The text Prep gets:

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
When the sub-plan file no longer matches the code as it is now, follow the code and name the stale lines (under
Decisions in the plan, or under Open questions in a note). Ask only when the file and the goal file contradict each other.
```

The last line replaces "stop with a DECISION block": the design step may not ask (the service refuses a DECISION from a
design step, `Hub._ended`), and the design step is where a stale file is found first. Limits: `done` lists at most `DONE_SHOWN` 20 items and 6 files
each (`... N more`); open questions at most 6; the whole prompt under `tasks.GOAL_MAX` (6000). Paths are relative to the
project with forward slashes. The prompt is the only text the build writes into a task; the step prompts are the chain's
own.

### 4.5 When the build waits for Fred (`state: waiting`, the row says it)

| `why` | Set when | Fred's moves (section 5) |
|---|---|---|
| `sub-plan 3 ready: Start` | `gated`: the card landed | Start on the card (as any card), Edit steps, Skip, Stop |
| `sub-plan 3: drift major: <note>` | `auto`: the planner said `major` | Continue (the task starts from the card as it is), Skip, Stop; Fred edits the files himself meanwhile |
| `sub-plan 3: prep failed: <error>` | the Prep job failed or the planner left no steps and Prep's own list is empty | Continue (Prep again), Skip, Stop |
| `sub-plan 3: planner failed: <error>` | `auto` only: the planner pass failed (`card["planner"]["error"]`), so no design step was planned and no drift was judged; at `gated` the card lands and shows the error as plan 47 D5 does | Continue (start from Prep's steps as they are), Prep again (`continue` with `again`), Skip, Stop |
| `sub-plan 3: file missing: <file>` | before an item's Prep (or an `auto` start) the sub-plan file is not a file under the project | Continue (check again, then Prep), Skip, Stop |
| `sub-plan 3: card dropped` | Fred pressed Drop on the item's card (or ran it as a chat), or a restart's orphan prune removed a waiting card (`card gone`) | Continue (Prep again), Skip, Stop |
| `sub-plan 3: start failed: <error>` | `auto`: `create_task` raised (`RunError`: the project left the list, claude.exe gone) after the project guard passed | Continue (start again from the saved card), Skip, Stop |
| `project: <reason>` | the build itself: `Hub._base` is not empty (F13); clears by itself when it is empty again | none; fix the project, or Stop |
| `cap: $26.10 of $25 spent` | before an item starts, `spent >= cap_usd` (D4) | Raise cap, Stop |
| `sub-plan 3 done: Accept` | `gated`: the task is done; or `auto` and D6 refused (the reason follows: `2 open questions`, `verify FAIL`, `supervisor card`, `brief writing`, `supervisor pass pending`, or the lever's own 409 text) | Accept on the task (as any task), Reopen, Skip, Stop |
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
```

The block holds facts only. The instruction to judge drift, and what `none`, `minor` and `major` mean, live in the
planner kind file alone (Task 2), so that deleting that sentence on the Models page switches drift off with no code
change (8.1). The answer's `drift` (`none` | `minor` | `major`) and `drift_note` (one line, `NOTE_MAX`) are optional in
`planner.SCHEMA` (the `required` list is unchanged, so a pass outside a build answers as today) and land in
`card["planner"]`. A missing `drift` in a build reads `none` with the note `the planner did not judge drift`.

### 4.7 Routes

| Route | Body | Does |
|---|---|---|
| `POST /api/build/preview` | `{project_dir, folder, goal_file?}` | `build.items_from(project_dir, folder)`, the goal file's existence and `build.lint`; `{items: [{n, file, title, words, warnings}], goal_ok, goal_warnings, digest, error}`; `digest` is the sha256 (16 hex) over each item's `file`, size and mtime in list order; writes nothing; 403 outside config.json projects, 400 for a path outside the project or a missing folder |
| `POST /api/build` | `{project_dir, folder, goal_file?, title?, keep?: [file...], digest, level?, cap_usd?}` | creates `builds/<id>/`, state `planned`; `keep` lists the item `file` paths of the preview to keep (default all, order kept; a path the folder no longer lists is a 400); `digest` is the preview's and must equal the folder's now, else 409 "the folder changed since the preview: Preview again" (F10); `{build: id}`. The lint warnings never refuse a Create |
| `POST /api/build/start` | `{build}` | `planned` or `stopped` -> `running`, owner `service`; the tick starts item `current` (1 after creation; the current item again after a Stop, as a Retry would). 409 with the reason when `Hub._base` for the project is not empty (not on the list, no claude.exe, folder gone) and 409 `another build is live in this project: <title>` when a different build of the same `project_dir` is `running` or `waiting` (F14) |
| `POST /api/build/stop` | `{build}` | `task_lever(stop)` on the current task when it runs; the item stays `running` with its task; build `stopped` |
| `POST /api/build/pause` / `resume` | `{build}` | `pause_after` true (the current item finishes, then owner `fred`); Resume: owner `service` |
| `POST /api/build/skip` | `{build, n}` | item `n` -> `skipped` when it is the current item without a live task (planned, preparing, ready, held, done, failed) or a later planned item; a `preparing` item's job is dropped (`drop_prep`); 409 otherwise |
| `POST /api/build/continue` | `{build, again?: true}` | on `held` drift, planner failed or start failed: `create_task` from the saved card (Prep again instead when `prep.load` finds no card); on `held` prep failed, file missing, card dropped or gone, or `failed` task deleted: Prep again; with `again: true` always Prep again, from any hold but the cap; 409 on a cap hold ("raise the cap first") |
| `POST /api/build/level` | `{build, level}` | `gated` or `auto`; takes effect at the next move (a `ready` item stays ready: Fred is already on its card) |
| `POST /api/build/cap` | `{build, cap_usd}` | 0 to 10000; a cap hold clears on the next tick when `spent < cap_usd` |
| `POST /api/build/delete` | `{build}` | not while `running` with a live task (409: stop first); removes `builds/<id>/` |
| `GET /api/build?id=` | | `{build, items: [{..item, task_row or null, card or null}], spent, summary or null, chain: [...], actions}`; `actions` is `{state, tag, why, line, primary, bar, menu}`: the shape of plan 52 Task 6 (`{id, label, post, body, off, confirm}` per action) plus `tag` and `why`, the dock card's tag and sentence (both `""` when nothing waits). A read: it starts nothing and writes nothing |

The card's Start (`POST /api/task`, unchanged body) and the task's Accept (`POST /api/task/accept`) are the `gated`
moves: `create_task` links the task when the card id is an item's `prep` and gives it task level `auto` when that
build is at `auto` (D9, `Hub._build_mode`). `GET /api/state` gains `builds`: one `build.row(b, tasks_rows)` each (4.8).
Every route passes `guard` as today (`do_POST` checks `host_ok` and the `X-CC` header before it looks the route up);
bodies are validated like the task routes (`tasks.safe_id` on ids, paths as text under the project). The routes go into
`Handler.do_POST`'s `routes` dict beside the task levers, and `GET /api/build` into `do_GET` beside `/api/task`.

### 4.8 The row (`build.row`)

`{"id", "label", "title", "project", "project_dir", "state", "owner", "why", "level", "cap_usd", "spent", "current",
"count", "done": accepted + skipped, "group": needs | working | done, "line": the status line, "updated",
"item": {n, title, state, task, prep} of the current item}`. `group` is `needs` when the build waits (4.5) or the
current task's row is in `needs`; `done` when `done` or `stopped`; else `working`. `line` is the one sentence of
section 5. The Board draws the row from this and nothing else (plan 36 3.4: no business rule in the page).

### 4.9 Failure paths of a long unattended build (each has a stated outcome and a test)

The tests are in `tests/test_build_server.py` (Task 3) unless a file is named. "Waits" always means the build is
`waiting` with the `why` of 4.5 and the next tick re-checks the reason, so a fixed cause clears it without a click.

| # | Path | Outcome | Test |
|---|---|---|---|
| F1 | The service restarts while Prep or the planner runs (item `preparing`) | The job thread is gone. If `prep.load` finds a whole card (steps, no `task.json`) it is re-seated in `Hub.preps` as a done job, no model call, line `recovered: card re-seated ...`; else the folder is discarded and Prep runs again, line `prep again <job>: the service restarted` | `test_restart_preps_again`, `test_restart_reseats_a_saved_card` |
| F2 | The service restarts while a card waits (item `ready` or `held`) | `Hub.preps` is empty after a start, so the Board would show no card. The first tick re-seats every saved card of a live build (F1's rule), nothing is paid. A card older than `prep.ORPHAN_DAYS` (2) was removed by `prep.prune_orphans` at the start: the item preps again | `test_restart_reseats_a_ready_card`, `test_restart_after_the_orphan_prune_preps_again` |
| F3 | The service dies between `create_task` and the build's save (the task exists, the item still `preparing`, `ready` or `held`) | The tick finds the task whose `tasks.prep_id` is the item's `prep`, links it (line `started by Fred on the card, recovered`) and starts nothing | `test_restart_links_a_task_a_crash_left` |
| F4 | The service restarts while the item's task runs, waits or is stuck | Nothing for the build: `advance` resumes the chain (plan 17); `retried`, the cap, `current` and every `why` are in `build.json` | `test_restart_mid_task_keeps_the_item` |
| F5 | A usage limit at 03:00 while a step runs | The chain retries once (another rung when one is free); no free rung: the task is stuck `<key>: <text>, until HH:MM (after one retry)`. D8 retries once after that key's entry has passed; a second stuck waits for Fred | `test_limit_retry_once`, `test_limit_retry_waits_for_the_reset`; `tests/test_build.py::test_limit_stuck_takes_the_key_from_the_why` |
| F6 | The same limit hits Prep or the planner of the next item | Prep raises: item `held`, `prep failed: <error>`; no `limits.json` entry exists to wait on, so the build waits for Fred (Continue = Prep again). A planner error is F19 | `test_prep_failure_holds_then_continue_preps_again`, `test_a_limit_error_in_prep_is_not_retried_by_the_build` |
| F7 | A pace hold or a Fable confirm at night (a task gate) | The task waits; the build stays `running`; its row shows the task's own line (`03 · held · over its pace`). D8 does not cover it (section 8, point 4) | `test_row_follows_a_task_hold_and_the_build_stays_running` |
| F8 | Fred Deletes the item's task (Delete is open on a planned, done, stuck or stopped task) | Item `failed`, `task deleted`, build `waiting`; Continue preps again, Skip, Stop. A task Deleted after its item closed changes nothing: the item keeps `files` and `questions` | `test_task_deleted_fails_the_item`, `test_deleting_an_accepted_task_keeps_files_and_questions` |
| F9 | Fred Deletes the build while its task runs | 409 "stop first"; a stopped or done build deletes, its tasks stay | `test_skip_stop_pause_resume_delete` |
| F10 | A sub-plan file is added, removed or edited between the preview and Create | Create sends the preview's `digest`; a different folder digest is 409 "the folder changed since the preview: Preview again", nothing is created. `keep` names files, so a shifted number can never keep the wrong one | `test_create_refuses_a_folder_that_changed_since_the_preview` |
| F11 | A sub-plan file is edited between Create and the item's Prep (or while earlier items run) | The file is read live by Prep, the planner and the design step; only the title was copied at Create and stays. Nothing is held. A file added to the folder after Create is not an item | `test_a_file_edited_before_its_prep_is_read_live` |
| F12 | The file is edited after the card landed, or deleted | Edited: the task is linked as usual (the design step re-reads the file, D7 a), the item's `sha` differs, line `file edited after its card`, nothing held. Deleted before Prep or before an `auto` start: item `held`, `file missing: <file>`, Continue checks again | `test_file_edited_after_the_card_is_noted_not_held`, `test_missing_file_holds_before_prep` |
| F13 | The project folder is moved, renamed, or taken off config.json while the build is live | Each tick asks `Hub._base` for the project first: not empty, the build is `waiting` `project: <reason>`, nothing starts, nothing is lost (paths are relative). It runs again by itself when `_base` is empty. A task already running there is held by its own `_base` checks (plan 27), as outside a build. A permanent move: Stop, Delete, and create a new build with the remaining files ticked | `test_project_unavailable_waits_and_resumes` |
| F14 | Two builds on one project | Create allows both; Start of the second is 409 while the first is `running` or `waiting` (`stopped`, `done` and `planned` do not count). A build and ordinary tasks in one project coexist as tasks do today | `test_second_live_build_in_a_project_is_refused_at_start` |
| F15 | `build.json` cannot be saved (disk error, incompatible content lock) | The tick's `try` logs `build tick failed: <error>`; the in-memory move stays; the next tick saves again. There is no retry loop of its own (plan 54). A restart before the save lands is F3 or F1 | `test_a_failed_save_is_logged_and_the_next_tick_saves` |
| F16 | Fred presses Drop on the item's card, or runs the card as a chat (`/api/run` with the prep id) | `Hub.drop_prep` holds the item: `held`, `card dropped by Fred`. It does not prep again by itself: that would bring the card back after every Drop. Continue = Prep again | `test_drop_holds_the_item` |
| F17 | The build's own `task_lever` call is refused (409: pending guidance, project off the list) | The build does not call it again in a loop: it waits `sub-plan 3 done: Accept (<the lever's text>)` and the next tick tries once more only when the task or the reason changed | `test_accept_refused_by_pending_guidance_waits_with_the_reason` |
| F18 | `task_lever(retry)` calls `advance()`, which would run the build tick inside the tick | `item["retried"] = 1` is committed before the lever, and `Hub._build_busy` makes the nested tick return at once | `test_a_nested_tick_does_not_retry_twice` |
| F19 | The planner pass fails inside a build's Prep (`card["planner"]["error"]`) | `gated`: the card lands as plan 47 D5 shows it; Fred decides. `auto`: no design step was planned and no drift was judged, so the item is `held`, `planner failed: <error>` (Continue starts Prep's steps as they are). An answer that omits the optional `drift` is not an error: it reads `none`, note `the planner did not judge drift` | `test_planner_failure_holds_an_auto_build_and_shows_on_a_gated_card` |

Not covered, by decision of this plan: a pace hold retry (D8 stays limits only), a Prep or planner limit retry (no reset
time is known), moving a build to a new `project_dir`, and a second tick thread (the tick runs in the hub loop only).

## 5. The window (Task 4; the parts are plan 52 Task 8's, nothing new drawn)

Seam. Plan 55 (the web build of `design/rework/locked/workflow-autopilot.html`) owns the list with its project groups,
the head, the section pattern, the step row, the dock card and the bar. This section says what Task 4 puts on top of
them; `04-window.md` ("Seam contract") says what Task 4 needs from them and what it does if a part is missing. Plan 55
was an uncommitted draft when this was refreshed (2026-11-07), so that contract quotes its provisional names and Task 4
must be checked against the committed plan 55 before it starts. Tasks 1 to 3 do not wait for it: the build runs from HTTP, as plan 52 Task 7's headless
check did.

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
- **The dock card** (UI-7), empty unless 4.5 applies: the tag and the sentence are `actions.tag` and `actions.why` (the
  page decides neither): `Ready`, `Drift`, `Held` (prep failed, planner failed, file missing, card dropped, task
  deleted), `Cap`, `Accept`, `Paused`, `Project`; its buttons with the primary at the right: Ready: Skip / Open the card;
  Drift: Stop / Skip / Prep again / Continue; Held: Stop / Skip / Prep again / Continue; Cap: Stop / Raise cap (a number field); Accept: Skip / Open
  the task; Paused: Stop / Resume; Project: Stop. "Start, and run the rest automatically" sits on the first item's card as
  a second Start (plan 52's "and auto accept" shape): `POST /api/build/level {level: auto}` then the card's Start, which
  makes an `auto` task by D9 with no extra body field.
- **The bar** (UI-8): icon tools left (Folder: the build folder in Explorer; Delete), the spend, then Stop, Pause after
  this sub-plan / Resume. No message box: a build takes no words; the task's page has it.
- Every button posts a 4.7 route or the task's own; the page shows a button only when the service's row allows it
  (`GET /api/build` carries `actions`: the same `{id, label, post, body, off}` shape as plan 52 Task 6).

## 6. Cost of a build

Per sub-plan, the same as a supervised task today (plan 52 section 4): Prep $0.005, planner $0.12 to $0.5, design on
opus $0.3 to $1, code $0.1 to $0.3 each, verify $0.05, briefs $0 when a handoff is under
`brief_max_words` and about $0.01 otherwise, and the supervisor about $0.01 per sub-plan: the done wake (one haiku "anything left?" pass after the
last brief, `supervisor.boundary` trigger `done`) runs at every level but `off`, plus a sonnet pass only when a task
sticks. Neither brief nor supervisor spend is in the build's `spent` (D4 note). The build adds $0: the drift judgment
rides in the planner pass (D3), the summary and the accept rule are code (D6). A nine-sub-plan app at $1 to $3 each
lands at $10 to $30, which is why `cap_usd` defaults to 25 (D4). Fred's clicks at `gated`: Start, Confirm plan (the
task's own gate, D9) and Accept per sub-plan; at `auto`: none on a clean run.

## 7. Not done here

- One file split into tasks by its `## Task N` headings (D5 b): a later line in `build.items_from` once a build has run
  from a folder.
- Dependencies, parallel items, a reorder at run time, a retry policy of its own (D2: non-goals).
- Editing a sub-plan file from the Console: the drift note is text; Fred edits in his editor.
- A project-level replan (the planner rewriting the remaining sub-plans): the planner proposes in `drift_note` only.
- The Board's project groups (plan 52 UI-1) and the web build of the locked design (plan 52 D9, now plan 55): the build
  row and page are drawn with plan 55's parts through the seam in `04-window.md`; until plan 55 is built they can be
  drawn with today's list and inspector, and move with that web task.
- A retry after a pace hold or after a Prep or planner limit (no reset time is known for those; 4.9, F6 and F7), moving a
  build to a new `project_dir` (F13), a git-branch check before Start (the throwaway branch is Fred's, section 9).
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

1. **The foundation has not run live.** Plan 52 Tasks 1 to 6 landed on 2026-11-07, and the headless acceptance script
   (`tests/live_autopilot_check.py`, `29fcc73`: 7 checks, real HTTP, real page, fake claude) passes, but Fred's live
   check has not run. The first supervised task, on 2026-10-20, died at step 1 (plan 52 section 1). A chain that
   stalls on one task stalls nine times in a build.
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

- Plan 52's live check passes on two or three real tasks (Task 5, the levels, is built: `a06147f`).
- The first app's sub-plans are written small and command-checkable, in one folder, with a goal file that closes the
  decisions (the preview's `build.lint` warnings, Task 1, check the mechanical part of this).
- The first build runs on a throwaway branch at `gated` with the cap at 60; two sub-plans watched, then `auto`.

D3 and D7 stay as written, with the downgrade recipes of 8.1 (D7 b is cheap; D3 b as written is not, see there). The
Claude Code workflow script remains the fallback if the Console route disappoints; switching costs nothing, since the
sub-plan files are the same input.

### 8.1 Downgrade recipes (checked against the code, 2026-11-07)

| Decision | Switch | What it costs | Evidence that says do it |
|---|---|---|---|
| D7 (a) to (b), no design step | One kind-file edit, no code, no restart: on the Models page edit `planner.md` and replace the build paragraph's first rule by "the list is the code steps the file calls for, each goal starting `Per <file>:`" (`prep.build_guard` already puts the file at the head of the task goal every step prompt carries). Verify then checks the diff against the step goals; no `plan.md` | one Models-page edit; a sub-plan's drift is then seen only by the planner's note and verify | two `plan: ...` refusals (`plan.check`) or a design step over $1 on the first sub-plans, or a plan.md that departs from the file under Decisions without a reason |
| D3 (a), drift off | One kind-file edit, no code: delete the drift sentence from the `planner.md` build paragraph. The answer carries no `drift`; every card reads `none`, note `the planner did not judge drift`; the design step's `Departs from <file>` lines (D7 a) remain the only drift signal | none; an `auto` build no longer holds on `major` | cards whose drift words were `major` on a sub-plan that was fine, or `none` on one that was not, twice in the first four |
| D3 (b) as written, a `review` step after each task | A new step kind: an entry in `tasks.KINDS`, `tasks.RULES`, a kind file, `kinds.NAMES`, the planner's table, the prompt and tests, plus one opus run per sub-plan. Not cheap; do it only if "drift off" proved the signal is worth $0.3 to $1 a sub-plan | a task of its own (about plan 47's size) | the drift note was right but came too early or too late to act on |

The planner's own limits matter here: `--max-turns 12` and `planner_max_cost` 0.5 (`claude_cli.planner_command`). A Build
context makes its prompt longer and asks it to read what the done items wrote; a pass that ends on the budget is a planner
failure (F19). If the first live run shows that, raise `planner_max_cost` on the Models page before touching D3.

## 9. Readiness (2026-11-07, at `9b6f988`): not ready to build

Tasks 1 and 2 could start the day Fred answers D1 to D9; Task 3 follows them; Task 4 also needs plan 55's parts. The
live check (Task 5) needs all of them.

| Precondition | Needed by | State today |
|---|---|---|
| Plan 52 Tasks 1 to 6 built | Tasks 1 to 3 stack on `create_task`, the levels, Accept, `actions` | Done: `c9b9f00` to `282feca`; plan 54 `c0793b3`; Task 7 headless `29fcc73` (7 checks, 1167 tests OK, `node --check web/app.js` clean) |
| Plan 52 live check passed (two or three real tasks at `gated`, then the task 06c2 comparison) | any real build; section 8 condition 1 | Open, Fred's. Also his: restart the tray service on plan 54, and Reset to repo copy on Models for `supervisor.md` and `design.md` |
| D1 to D8 answered (D2 first: BRAINSTORM D17), and D9 | before Task 1 | Not answered. D2 decides whether the plan exists at all; D9 is new in this refresh |
| Plan 55 (web build of the locked UI) or its seam | Task 4 only | Draft only: `plans/55-autopilot-ui/` (README and five task files) was uncommitted at 21:23 on 2026-11-07; its section 7 names the seam parts and the contract in `04-window.md` quotes them as provisional. Tasks 1 to 3 do not wait; Task 4 waits for plan 55's head, section, row, dock and bar tasks, or is built on today's `dock()` and `inspTask` parts and ported later |
| Sub-plan folder lint passed | the first build | No tool today. `build.lint` (Task 1) checks four mechanical things on the preview (a Done check with a command, size, task headings, open words in the goal file's Decisions). Fred's first app folder is not in this repository, so not checked |
| Throwaway branch, `gated`, cap 60, two sub-plans watched | the first build | Fred's. The Console does not read or create the branch. The cap is set on the New build form (the default stays 25) |
| Models page copies of `planner.md` and `design.md` after Task 2 | the live check | After Task 2, Fred's Reset to repo copy |
| Full suite and `node --check web/app.js` green | every task | 1167 tests OK at `9b6f988` |

What is not a blocker: plan 56 (skill library) and the Codex port; a build runs on the `claude` harness's planner and
Prep (both Claude-only, `tuning.CLAUDE_ONLY`) and routes its steps by the tiers as any task.

## 10. Order and checks

1. Fred reads D1 to D9; a changed answer is written into this README and the task files before Task 1.
2. Plan 52 Task 5 is built; nothing to do first. D9 is how a build uses it (section 2.1).
3. Tasks 1 to 3 in order, tests first, one commit each (`feat: ... (plan 53 Task N)`; Task 3 may be two commits, A for
   state, tick, link and recovery and B for routes, snapshot and actions), the full suite at each boundary; Task 4 once
   plan 55's parts exist (or on today's), `node --check web/app.js` after it; stage only this plan's lines.
4. Task 5: the headless script is Claude's and runs before Fred's check; the live check is Fred's. Task 6 closes.
