# Plan 24: The design step writes the plan; the bounded replan. Guided implementation plan

> Design: [../../design/brainstorm/2026-10-13-orchestration.md](../../design/brainstorm/2026-10-13-orchestration.md)
> sections 8 (D-7) and 8b (D-9), and the interface doc
> [../../design/brainstorm/2026-10-13-interface.md](../../design/brainstorm/2026-10-13-interface.md) section 7 (Task
> page: Plan row, Replan wait, Plan gap and plan_hold askboxes) and 8.3 (Plan tab, `handoff · plan` chip). Mock:
> [../../design/rework/locked/cells-board.html](../../design/rework/locked/cells-board.html), views `Plan tab`, `Plan gap
> waits`, `Task · sub-plans`, `Task · plan hold`, `Replan wait`, and the list card `Plan gap`. Contract this plan
> changes: [../17-tasks/README.md](../17-tasks/README.md) (3.2, 3.3, 3.6, 3.7) as plan 19 left it. Master:
> [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
>
> Written against today's code (plan 22 placed, 328 tests). Plan 23 (six-heading handoff, facts, tools per kind) is not
> written yet: where it lands first, its README says which of this plan's lines move (3.5 names them).

Status: written 2026-10-14; Fred took (a) on D1 and D2 the same day (D3 open). Tasks 1 and 2 were run in a scratch copy of the working tree (39 tests OK: 21 in
`tests/test_plan.py`, 6 in `tests/test_replan.py`, 12 in `tests/test_compact.py`); their final code is in the task
files. D3 waits for Fred; the plan is written for the recommended option of each.

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-plan-module.md](01-plan-module.md) | `console/plan.py` (parse, check, split, files, answers, prompt parts), `console/design_prompt.md`, the `$plan` / `$part` slots of `step_prompt.md`, `tests/test_plan.py` | nothing |
| 2 | [02-replan.md](02-replan.md) | `console/replan.py` and `console/replan_prompt.md` (the pass, its check, propose, apply, keep), `compact._ask` taking a schema, `tasks.RULES["replan"]`, `tests/test_replan.py` | nothing |
| 3 | [03-service.md](03-service.md) | `Hub`: the design step's input and turn cap, the PLAN block saved and checked when a design step ends, the rebuild after a split, the size and plan_hold waits, the `Plan gap:` wait, the replan step run and its wait; levers `answer`, `redo`, `keep`, Confirm extended; routes `POST /api/task/answer`, `POST /api/task/plan`; `GET /api/task` and `task_row` with the plan; config keys; the fake claude's words; `tests/test_server.py`, `tests/test_tasks.py` | 1, 2 |
| 4 | [04-window.md](04-window.md) | Task page: the Plan row (single and split), the Plan gap, plan hold, plan size and replan askboxes, `from plan` on step rows, the list card's buttons; the Models tuning row `Turns on design` | 3 |
| 5 | [05-live-check.md](05-live-check.md) | Fred's live check | 4 |
| 6 | [06-close.md](06-close.md) | PLAN.md, the two design docs, CLAUDE.md line, this folder's state | 5 |

Tasks 1 to 3 are Python, tests first; each ends with its own commit. Task 4 is browser code (`node --check web/app.js`,
the full suite, headless Edge at 400 and 340 px with the fake claude). Task 5 is Fred's: Claude never starts a run.
Start state: 328 tests OK on `claude/project-thread-j5s3mn` (2026-10-14). Other chats edit `web/app.js`, `PLAN.md`
and the design docs in parallel: anchored edits only, stage only this plan's lines.

## 2. Decisions (Fred). Recommended option first; the plan is written for it

Everything the brainstorm settles (8b, D-9: who writes, the PLAN block, never cut, the six headings, the code checks,
sub-plans with one write step each, `Plan gap:`, the defaults `plan_max_kb` 100, `plan_max_parts` 6, `plan_hold` off,
the split applied without a confirm) is not reopened here. Three points it does not settle:

| # | Question | Options | Plan written for |
|---|---|---|---|
| D1 | What the design step reads from the steps before it. The brief is capped at `brief_max_words` (400) and compacted by Haiku; a plan built from a compacted scout loses the file paths and line numbers the plan must cite. | (a) the raw handoff notes of every earlier step, whole (`plan.design_input`; a scout note is at most `NOTE_MAX` 20 KB, so a design step reads at most a few notes); the brief pass still runs after the scout for the chain log and the window; (b) the previous step's brief, as every other step | (a), Fred 2026-10-14 |
| D2 | The design step's turn cap. Today `opus_max_turns` 12 caps a design step on opus only; a plan with final code for every change needs more reading than a 400-word handoff did, and the think tier has rungs on other harnesses (plan 5). | (a) one key `design_max_turns` 30 for a design step on any rung, replacing `opus_max_turns` (the old key is read as a fallback once, then dropped from config.json); (b) keep `opus_max_turns` 12 and cap only opus | (a), Fred 2026-10-14 |
| D3 | How the handover from step to step is packaged. | (a) the task folder is the package: the service composes each step's prompt from `prompt.md`, the previous brief, `plan.md` and the step's own part (plan 23 adds the facts), and the chain line that starts a step says what it was given (`read: brief 02 · plan 12.4 KB · part 2`); no per-step folder, no copies; (b) a folder per step, `steps/NN/` with a copy of what that step received | (a) |

A different answer changes only the lines the task files mark `D1`, `D2` or `D3`.

## 3. The contract (changes to plans/17-tasks/README.md; everything else there still holds)

### 3.1 Files and places

```
~/.claude/console/tasks/<id>/
  task.json                 plan meta (3.2), steps with part and hard
  chain.jsonl               the lines of 3.3
  plan.md                   the plan, or the index of a split plan; written by the service only, never cut
  plan/01-<slug>.md         one file per sub-plan, `# Part N: <title>` then the block as written
  steps/NN-replan.md        the replan pass's note: the question, the steps before and after (3.9)
console/plan.py             the plan module (Task 1)
console/design_prompt.md    the design step's `$special` text (Task 1)
console/replan.py           the replan step (Task 2)
console/replan_prompt.md    the replan pass's prompt (Task 2)
```

- `tasks.clear(home, task, keep_last)` keeps `plan.md` and `plan/` in both modes (clear on done and Fred's Clear
  keep the plan with task.json, chain.jsonl and the last note). Retention deletes the folder whole, as today.
- The plan files are masked by `redact.mask` like a note (secrets a design step read never land on disk).
- Only the service writes the folder (plan 17 rule 3.10). The design step writes no file: its final message carries
  the plan; Fred's edits go through `POST /api/task/plan`.

### 3.2 task.json

```json
{"id": "...", "plan": {"from": 2, "words": 4870, "kb": 28.1,
                       "parts": [{"n": 1, "kind": "code", "title": "Harness module", "file": "plan/01-harness-module.md",
                                  "owns": ["console/harness.py"], "depends": [], "hard": false, "step": 3}]},
 "steps": [{"n": 3, "kind": "code", "goal": "Part 1: Harness module", "part": 1, "hard": false, "...": "..."}],
 "replan": {"step": 2, "why": "week buckets first", "added": [0], "dropped": [],
            "before": [{"kind": "code", "goal": "..."}], "after": [{"kind": "code", "goal": "..."}]},
 "replan_steps": [{"n": 3, "kind": "code", "...": "..."}],
 "redo": "which file holds the ladder?"}
```

- `task["plan"]` is set by `plan.save` when a design step's PLAN block checks out; `parts` is `[]` for a single plan.
  A task without a design step never has it. `words` and `kb` count the index and the parts together.
- A step gets `part` (the sub-plan number) and `hard` only when `plan.rebuild` made it; everything reads them with
  `.get` and `STEP_KEYS` does not grow (old task.json files load; `tasks.whole` unchanged).
- `replan` and `replan_steps` exist only while a replan proposal waits (3.9); `replan.apply` and `replan.keep` pop them.
- `redo` holds the `Plan gap:` question while the design step runs again (Fred's Redo design); popped when it ends.
- `plan_hold_ok` is not needed: Confirm moves the task from `waiting` to `running` and `_go_on` starts the next step.

### 3.3 chain.jsonl lines added (same shape as plan 17 3.3: `t`, `step`, `kind`, `from`, `to`, `why`)

| `why` | When |
|---|---|
| `plan saved: 2,140 w, 12.4 KB` | a design step's PLAN block checked out and was written (single plan) |
| `plan saved: 3 sub-plans, 4,870 w, 28.1 KB` | the same, split |
| `design split into 3 sub-plans: 3 code steps (Prep had 1)` | `plan.rebuild` replaced the write steps |
| `plan 132 KB, over 100` | the task waits (state `waiting`, that why) |
| `plan ready: confirm` | `plan_hold` on: the task waits after the design step |
| `plan confirmed by Fred` / `plan accepted by Fred` | Confirm on the hold / on the size wait |
| `plan edited by Fred` / `plan edited by Fred: part 2` | `POST /api/task/plan` |
| `asks: Plan gap: <question>` | a later step stopped on a gap (the plan 17 question wait, that prefix) |
| `plan gap answered by Fred: <answer>` | Answer: the line joined Decisions and the step's session got the answer |
| `design redone by Fred: <question>` | Redo design: the design step planned again, the later planned steps too |
| `read: brief 02 · plan 12.4 KB · part 2` | appended to `tasks.start_step`'s line notes (D3 a): what the step was given |
| `replan inserted after 01: <why>` | a handoff's `Replan:` line |
| `replanned: 2 steps added` / `replanned: 1 dropped` / `replanned: no change` | the replan pass answered; the task waits unless `replan_auto` |
| `plan changed: 5 steps follow 02` | Confirm plan, or `replan_auto` |
| `old plan kept by Fred` | Keep old plan |
| `replan failed: <why>` | the pass's answer failed `replan.check` or the CLI failed: retry once, then stuck (3.6) |

### 3.4 The plan: shape and checks (`plan.check`, Task 1)

The design step's final message: `PLAN` line, the plan, `END PLAN` line, then (split only) `SUBPLAN n kind title`
... `END SUBPLAN` per part, then the HANDOFF block. Markers are read with `tasks._mark` (bold or backticks allowed,
a quoted `> PLAN` is not a marker); the last PLAN block wins, as the handoff does.

Single plan headings, in this order: `## Goal`, `## Decisions`, `## Out of scope`, `## Files`, `## Steps`,
`## Acceptance`; under Steps one `### Step N: <kind>` per later write step, each with `#### Files`, `#### Actions`,
`#### Tests`, `#### Done check`. Split plan (the index): `## Goal`, `## Decisions`, `## Out of scope`, `## Sub-plans`,
`## Acceptance`; the table `| # | Part | Kind | Owns | Depends on | Hard |`; each part `## Files`, `## Actions`,
`## Tests`, `## Done check`.

Checks, in this order, the first failure is the reason (one retry with it, then stuck, as a bad HANDOFF block):

| Reason | Rule |
|---|---|
| `no PLAN block` | `plan.parse` returned None (the service's reason, before `check`) |
| `TBD or TODO left in the plan` | the words, anywhere in the index or a part |
| `missing: ## Files` / `headings out of order` | the heading list of the shape |
| `a Decisions line is a question: ...` | a line under Decisions ending in `?` |
| `missing: ### Step 3` | single: a later step of an edit kind without its section |
| `Step 3: missing: #### Tests` | single: a step section without one of the four |
| `missing: the Sub-plans table` | split: no `\| n \| ... \|` row with six cells under Sub-plans |
| `7 parts, over plan_max_parts 6` / `a split needs at least 2 parts` | the bounds |
| `parts not numbered 1 to N in order` / `the Sub-plans table and the SUBPLAN blocks differ` | numbering |
| `part 2: test is not a write kind` / `part 2: the table says code, the block document` | kinds |
| `part 2 depends on a part that is not earlier` | `Depends on` |
| `part 2: missing: ## Tests` | the part headings |
| `calc.py is owned by parts 1 and 2, which does not depend on 1` | the owner rule |
| `5 steps after the design step, over task_max_steps` | parts plus Prep's other kept kinds > `task_max_steps - n` |

Size is not a check: `plan.kb` over `plan_max_kb` makes the task wait (3.6), nothing is cut.

### 3.5 What the prompts carry

- `console/step_prompt.md` gains two slots: `$plan` after the `$retry` line (before "Handoff note of the previous
  step"), and `$part` right before "Rules for this step:". `tasks.step_prompt(task, step, prev_note, retry_reason="",
  special="", plan="", part="")`: `special` given wins over the verify / fix text; empty slots leave blank lines only.
- Design step: `special = plan.design_text(task, step, cfg, redo=task.get("redo", ""))` (design_prompt.md, Task 1:
  the later steps, the write steps that need a section, `$turns`, `$max_kb`, `$max_parts`, `$room`, the split rules,
  the `Replan:` escape); `prev_note = plan.design_input(home, task, n)` (D1 a: every earlier raw note, whole) or the
  brief with D1 (b); `max_turns = cfg["design_max_turns"]` on every rung (D2 a).
- Every step after the design step of a task with a plan: `plan, part = plan.prompt_parts(home, task, step)`:
  `plan` is "The plan (follow it, do not change it):" + the index whole + the rule line (`PLAN_RULE` for a write
  step: stop with `Plan gap:`; `VERIFY_RULE` for verify and fix: a departure is a FAIL `plan drift: ...`); `part` is
  "Your part of the plan:" + the step's own `### Step N` section, or its sub-plan file whole (`step["part"]`), or every
  part for verify and fix, or nothing for a test or search step. The previous step's brief still follows.
- Plan 23 (when written) replaces `$prev` with its six-heading brief plus facts; the `$plan` and `$part` slots and
  `prompt_parts` stay as here.

### 3.6 Transitions added (README 3.7 of plan 17)

| State seen | Condition | Result |
|---|---|---|
| design step ended, `ok`, handoff checks out | `plan.parse(text)` is None | `block_error = "no PLAN block"`: retry once with the reason, then stuck (the plan 17 rule) |
| the same | `plan.check(...)` returns a reason | `block_error = "plan: <reason>"`: the same |
| the same, the plan checks out | always | `plan.save`, `task["plan"]`, chain `plan saved: ...`; the note and the brief as today; split: `plan.rebuild` (chain `design split ...`), step `part` / `hard` set |
| after the save | `plan.kb(plan) > plan_max_kb` | task `waiting`, why `plan 132 KB, over 100`; Confirm (Accept) runs on, Redo design plans again, Stop |
| after the save, not over | `cfg["plan_hold"]` | task `waiting`, why `plan ready: confirm`; Confirm, Edit (`POST /api/task/plan`), Stop |
| a later step ended with a STOP question | `plan.gap(block)` or the question starts with `Plan gap:` | the plan 17 question wait, why `asks: Plan gap: <q>`; levers Answer, Redo design, Stop |
| Fred: Answer | task `waiting`, why starts `asks: Plan gap:` | `plan.add_answer` (Decisions gains `- Fred, <date>: <answer>`), chain `plan gap answered by Fred: ...`, then the answer goes to the step's session as a STOP answer (`Hub.pull(sid, "continue", text)`), task `running` |
| Fred: Redo design | the same, or `plan 132 KB, over 100`, or `plan ready: confirm` | the current step (if running) is stopped and `failed` (`stopped for a redo`); the design step and every planned step after it go back to `planned`, done steps stay done; `task["redo"] = question`; `current = design n`; chain `design redone by Fred: ...`; task `running`; the design step starts with the question in its prompt; when it ends, `rebuild` replaces planned steps only |
| design step ended | `task["redo"]` | popped before the plan is saved |
| step `replan` is next | always | no session: `Hub.start_replan` runs `replan.run_replan` in a thread (like the brief); the step is `running` with session `""`, model `brief_model`, effort `low`, cost from the pass |
| the replan pass returned | `error` | `replan failed: <why>`: the plan 17 retry once, then stuck |
| the replan pass returned | steps | note `steps/NN-replan.md` (3.9), `replan.propose`, chain `replanned: ...`; `replan_auto` off: the step `done`, task `waiting`, why `replanned: ...`; on: `replan.apply` at once, task `running` |
| Fred: Confirm | why starts `replanned:` | `replan.apply`, chain `plan changed: ...`, task `running`, `_go_on` |
| Fred: Keep old plan | the same | `replan.keep`, chain `old plan kept by Fred`, task `running`, `_go_on` |
| a handoff's Next line | `replan.ask_line(block)` and the task has room | after the note and the brief: `replan.insert` (chain `replan inserted after NN: ...`), then `_go_on` starts the replan step |
| Fred: Confirm | why is `plan ready: confirm` or `plan N KB, over M` | task `running`, chain `plan confirmed by Fred` / `plan accepted by Fred`, `_go_on` |

Pause, Stop, Resume, Retry, Clear and Mark done are unchanged; a paused task holds every one of these waits until
Resume, as today.

### 3.7 Levers and routes (`Hub.task_levers`, `Hub.task_lever`, `Handler`)

- `task_levers` gains `answer` (allowed only when why starts `asks: Plan gap:`), `redo` (allowed when the task has a
  design step and waits on a Plan gap, the size, or the hold; or is stuck after the design step's second bad plan),
  `keep` (allowed when why starts `replanned:`); `confirm`'s reason text covers the four new waits.
- `POST /api/task/answer {task, text}`: 400 on empty text, 409 with the lever's reason, else 200 `{task, state,
  session}` (the step's new turn, as `/api/continue` answers).
- `POST /api/task/redo {task}` and `POST /api/task/keep {task}`: the plain lever route (the loop in `do_POST`).
- `POST /api/task/plan {task, text, part}`: Fred's in-place edit of the index (`part` 0 or absent) or of part k; 409
  unless the task waits on the hold, the size or a Plan gap, or is paused with the next step not started; the text is
  checked with `plan.check` on the edited plan (409 with the reason) and written with `plan.write`; chain `plan edited
  by Fred[: part k]`; `task["plan"]["words"]` and `kb` recounted.
- `GET /api/task?id=`: adds `"plan": <plan.md text or "">`, `"parts": {n: text}` and `"replan_note"` (the replan
  step's note, when one exists) next to `note`, `brief` and `handoff`.
- `task_row` adds `"plan": t.get("plan") or None` and each step's `part` and `hard` (`.get`, default 0 / false).
- `Hub.levers` (session levers) is unchanged: a Plan gap answer also works from the step's chat as a plain Continue,
  without the Decisions line; the window's Answer button uses `/api/task/answer` so the line is written.

### 3.8 Config keys (`console/paths.py` DEFAULTS; Models page Tuning tab in plan 26)

| Key | Default | Meaning |
|---|---|---|
| `plan_max_kb` | 100 | the plan files together; over it the task waits, nothing is cut |
| `plan_max_parts` | 6 | sub-plans at most |
| `plan_hold` | false | the task waits after the design step for Confirm |
| `replan_auto` | false | a replan proposal applies without Confirm |
| `design_max_turns` | 30 | `--max-turns` of a design step on any rung (D2 a; `opus_max_turns` removed, read once as a fallback by `paths.load`) |

### 3.9 The replan step (brainstorm 8, D-7; Task 2)

- Kind `replan` in `tasks.RULES`: `("haiku", "low", "")`; `PREP_KINDS` lists it (Prep may place one after a scout or a
  design), `EDIT_KINDS` does not. It has no session: the service runs `replan.run_replan` in a thread, as the brief.
- The pass: `claude_cli.brief_command(exe, brief_model, replan.SCHEMA)` (no tools, three turns), prompt
  `console/replan_prompt.md` (the goal, the question, the briefs so far, the remaining steps, the kinds, the room),
  answer `{"steps": [{"kind", "goal"}], "why"}`.
- `replan.check(task, n, answer, task_max_steps)`: known kinds (`PREP_KINDS` minus `replan`), a goal per step, at most
  `MAX_ADDED` 2 steps more than the remaining ones, `n + len(steps)` within `task_max_steps`, the verify re-placed after
  the last edit kind (the pass never writes one). Reasons: `no steps in the answer`, `unknown kind: x`, `a step has no
  goal`, `3 steps added, over 2`, `9 steps in all, over task_max_steps 8`.
- The note `steps/NN-replan.md` (written by the service through `tasks.write_note` with a block built by
  `replan.note_block`): `## Findings` the why, `## Files touched` (none), `## Open questions` (none), `## Next` the
  steps before and after as two lists. Its brief is the previous brief (the pass added nothing a later step reads).
- The wait: task `waiting`, why `replanned: 2 steps added`; `task["replan"]` carries `before`, `after`, `added`,
  `dropped` for the window's two lists; Confirm plan applies, Keep old plan drops, Stop stops.
- Inserted by the service: a handoff block's `Replan: <what and why>` line (anywhere in the block; the prompt names
  the Next line) inserts the step right after the step that asked when `len(steps) < task_max_steps`; over the room,
  the chain says `replan refused: no room` and the chain goes on.

### 3.10 Hard rules (from CLAUDE.md, plan 17 3.10 and the brainstorm; never relaxed by a task)

- The plan is never compacted, cut, summarised or truncated by code, whatever its size; the only size rule is the
  wait of 3.6. `NOTE_MAX` counts the handoff note alone: `tasks.write_note` writes the HANDOFF block only, as
  today, so the plan never counts against it.
- The design step and the replan pass write no file. The model never names a path under `~/.claude/console/`.
- Fred's answer to a Plan gap joins Decisions as a line; the plan is otherwise never rewritten by code. The window edits
  it only through `POST /api/task/plan`, only while nothing after the design step runs.
- A split never adds a kind the plan 17 rules table does not know and never exceeds `task_max_steps` (one check in
  `plan.check`, one in `replan.check`; the service trusts them and re-checks nothing).
- Window runs, VS Code chats and terminal chats have no plan: `prompt_parts` returns `("", "")` for a step before the
  design step and for a task without `plan`; `Hub.levers` does not change.
- No emojis or em-dashes in any prompt or plan text; the prompts say `Fred` where plan 17's do.

### 3.11 Drift guards for the executor

- `plan.check` and `replan.check` are the only validators; the service never parses the plan text itself.
- `rebuild` replaces planned steps whose kind is among the parts' kinds only; a done step after the design step keeps
  its place (a redo after a done code step keeps that step and its work).
- `step["part"]` and `step["hard"]` are read with `.get` everywhere (`task_row`, `prompt_parts`, the window).
- `tasks.on_step_ended` is not changed: the plan checks happen in `Hub._ended` and feed `block_error`, so the retry
  and stuck rules of plan 17 apply unchanged.
- The step prompt's HANDOFF template stays the last thing in the prompt; `$part` sits before the rules, not after
  them.
- `compact._ask` returns whatever dict the schema produced; the brief's field check lives in `run_brief`
  (`_fields_ok`), the replan's in `replan.check`.
- The fake claude answers from words in the prompt only (3.12); no test runs the real CLI.

### 3.12 The fake claude's words (`tests/fake_claude.py`)

| Word in the step prompt | Reply |
|---|---|
| `PLAN-OK` | a valid single plan with one `### Step N: code` section for each number the prompt lists after "each write step (", then the HANDOFF block |
| `PLAN-SPLIT` | a valid split plan with two parts (`Calc module`, `Report module`, the second depends on the first) and the HANDOFF block |
| `PLAN-BAD` | a plan without `## Acceptance` and the HANDOFF block |
| `PLAN-GAP` | the HANDOFF block with `- Plan gap: which file holds the ladder?` under Open questions and `STOP: Plan gap: which file holds the ladder?` after it |
| `REPLAN` | the HANDOFF block whose Next line ends with `Replan: a search step is needed first` |
| `REPLAN-ADD` (in the task goal, read by the brief-mode fake) | the replan schema answer: the remaining steps plus one `search` step first, why `search first` |

## 4. Verification at the end of every task

- `py -m unittest discover -s tests` all OK; the count is written in the task's commit message.
- Task 1 and 2: the module's tests fail as written before the code and pass after it.
- Task 3: `tests/test_server.py` runs a task `scout, design, code, test, verify` through the fake claude with
  `PLAN-OK`, `PLAN-SPLIT`, `PLAN-BAD` (retry then stuck), `PLAN-GAP` (Answer, Redo design) and `REPLAN` (Confirm, Keep
  old plan) on a `CC_CONSOLE_HOME` temp folder; the plan files land in the task folder and nowhere else.
- Task 4: `node --check web/app.js`; headless Edge at 400 and 340 px on the same fake runs: the Plan row closed line,
  the open row, the parts list, every askbox, no console errors.
- Task 5: Fred's live run in a real project (05-live-check.md).
