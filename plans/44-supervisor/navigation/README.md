# Plan 44 navigation slice: task Overview, one action area, whole-task handoff. Guided plan

> Design: [../NAVIGATION.md](../NAVIGATION.md) (decided 2026-10-17; the six settled decisions are its
> "Settled decisions" section). Companion to [../BRAINSTORM.md](../BRAINSTORM.md) (supervisor policy, decided;
> its backend ships separately). Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).

This folder is the plan. No code is written in it: each task file names the files, the functions with their
exact signatures, the data shapes, the prompt text, the tests with what they assert, and the ordered steps.
The code is written when a task is executed, test first, placed one task at a time.

This slice ships the presentation and the whole-task handoff. It does **not** ship the plan 44 supervisor
backend (the attention area for supervisor suggestions is wired in Task 2 but stays empty until the
supervisor's `POST /api/task/supervisor` exists; see the drift guards). Decision 5 of NAVIGATION.md: navigation
first, supervisor UI when its backend lands.

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-selection.md](01-selection.md) | Clicking any task entry point opens that task's Overview; a step link opens that step; a breadcrumb returns without losing list state; late fetches never change the selection | nothing |
| 2 | [02-overview-actions.md](02-overview-actions.md) | The Overview (Goal / attention / progress / composer) with Steps and Files views; one action area (two prominent + More); green Mark done; Accept step result; Verify inside Add step; remove Brief a new task, Verify in a new task, duplicate Continue/Verify/Mark done, and the Delegate hint | 1 |
| 3 | [03-handoff.md](03-handoff.md) | Whole-task handoff: a code-built digest, one cheap haiku pass over it, Save document and Create follow-up task, the `handed` state and `handoff_to` / `handoff_from` links, the More > Hand off task flow | 1, 2 |
| 4 | [04-tests-close.md](04-tests-close.md) | Reconcile web/task/server tests, the browser fixture check, PLAN.md and plan indexes, Fred's live check | 1, 2, 3 |

Each task ends with its own commit.

**Start state.** The working tree holds an interrupted navigation/handoff attempt: uncommitted edits in
`web/app.js`, `web/style.css`, `console/server.py`, `console/tasks.py`, `tests/test_web.py` (12 web test
failures). Those edits are **superseded**; reset those files to HEAD before Task 1 and build from this plan.
Two edits are independent and kept: the backtick-fence fix in `console/tasks.py` (`step_prompt`, the
`max(map(len, ...), default=0)` line) and its test in `tests/test_tasks.py` (`bare`). The design docs
(`PLAN.md`, `plans/44-supervisor/BRAINSTORM.md`, `NAVIGATION.md`) stay. Baseline: plan 42/43 green (837+ tests).

## 2. Decisions taken (Fred, 2026-10-17; NAVIGATION.md "Settled decisions")

1. The handoff summary is built by one cheap haiku pass over the saved digest, never by re-reading the live
   context, never a pure code concatenation (a code fallback runs when the pass fails, as the brief's does).
2. Handing a task off sets the source task `handed` and records its `handoff_to` link; it is not marked done.
3. Handoff is the cold-cache escape for tasks (reads saved files + the haiku digest, never the cold context).
   A cold external session has no saved folder: its escape is the composer -> Prep. "Brief a new task" is
   removed with no replacement; the composer is the single way to create a task.
4. "Mark done" (green) is the whole-task completion action and replaces "Finish task"; "Accept step result"
   replaces "Mark step done" and is recovery only; Verify is a choice inside Add step, not a standalone button.
5. Navigation and action cleanup ship before the supervisor UI; the supervisor's suggestions, approvals and
   questions share the one Overview attention area when its backend lands.
6. Hand off task offers both Save document (write `task-handoff.md` in the source folder only, no state change)
   and Create follow-up task (also create the linked draft and set the source `handed`).

## 3. The contract (what every task must keep)

### 3.1 Files and places

- Task folders stay `~/.claude/console/tasks/<id>/` (CLAUDE.md data rule). The whole-task handoff writes
  `task-handoff.md` (the summary) into the source folder, and into the follow-up folder `inherited-handoff.md`
  (the same summary) plus a `handoff-source/` folder of evidence copies. Nothing else new is created there.
- A task id is `prep.new_id()`; `tasks.safe_id` guards every route and file read, as today. The follow-up id is
  `prep.new_id()`; the request id is the same 32-hex `uuid()` the Add-step API uses (plan 36).
- `task.json` is written whole through a temp file and `os.replace` (plan 34), by the service only.
- The haiku pass runs in a thread like `_brief_job`, writes nothing, and is priced from its `result` line.

### 3.2 The handoff summary

`console/handoff.py` (new), reusing `compact._ask` (extended with an optional `model` parameter, default
`cfg["brief_model"]`) and `claude_cli.brief_command`:

- `HANDOFF_SCHEMA`: `{"goal": str, "findings": [str], "files": [str], "troubleshooting": [str],
  "questions": [str], "next": str}`, all required, `additionalProperties: false` — the six handoff headings as
  structured fields.
- `digest(home, task, instructions) -> str`: the code-built digest the pass reads (target under 4K tokens, hard
  cap 12 KB; cut sections from the bottom, never the head): head (id, title, project, goal, state/why, total
  cost), one line per step (`NN kind · model/effort · state · verdict · cost · retries`), each step's note or
  brief (whole, `NOTE_MAX`), its facts, the last verify's verdict, open questions, the chain tail (last 10).
  Never transcripts, `runs/*.jsonl`, other tasks, or config.json.
- `build_prompt(task, instructions, digest) -> str`: a fixed short prompt (under 1,000 tokens) that names the
  six headings and tells the pass to summarize saved evidence honestly, cite each step's number, and mark
  missing results as unavailable, never as success.
- `render(fields, task, instructions) -> str`: the six headings (`tasks.HEADINGS`) from the fields, in order;
  Goal carries the task identity and the remaining-work instructions; empty fields render "None recorded."
- `check(block, max_words) -> str`: `""` when all six headings appear in order and the word count is under the
  cap, else the reason (mirror `compact.check`).
- `fallback(home, task, instructions) -> str`: code only — the six headings concatenated from the same saved
  files, each step tagged, with the "[excerpt; full text in the cited evidence]" marker (the interrupted
  attempt's approach, kept as the fallback only).
- `run(cfg, exe, home, task, instructions) -> dict`: blocking; `{"text", "cost", "words", "model", "fallback":
  "" | why}`; never raises — every failure (no exe, parse miss, schema miss, timeout) ends in `fallback`.

### 3.3 The `handed` state and the link fields

`handed` already exists (the session-level `/session-handoff` skill flow, plans 13/40). The whole-task handoff
reuses it and adds the distinguishing link:

- Follow-up task: `handoff_from = <source id>`; a copy of the summary at `inherited-handoff.md` and the evidence
  at `handoff-source/`; one first step, kind `code`, goal = the remaining-work instructions (or a fixed fallback
  when none were given), `state: "planned"`, `owner: "fred"`, `progression: "manual"`. It does not auto-run.
- Source task: `handoff_to = <follow-up id>`, `handoff_note = "task-handoff.md"`; `state` becomes `handed` with
  `why = "Handed off to <id>"` unless it was already `done`. History, files and streams are preserved.
- Starting the follow-up (its Resume, the ordinary Start) runs step 1; step 1's prompt carries
  `inherited-handoff.md` inline (the `n == 1 and task.get("handoff_from")` branch in `step_prompt`), so the
  worker reads the context even when reads outside the project are denied.
- `handed` without `handoff_to` keeps the existing session-level flow (`handedBox`, Start next task); `handed`
  with `handoff_to` shows "Handed off to follow-up" and links the follow-up. `taskShown`, `handedBox` and
  `startNext` must distinguish the two.

### 3.4 The one action area

- `taskButtons(t, d)` renders at most two prominent workflow actions plus one `<details>` "More". Composer
  actions (Send, Attach) are never duplicated here.
- Prominent, state-specific: Stop (running), Resume / Start task (paused or a fresh follow-up), Retry (failed
  current step), Add step (`add_next === ""`), green Mark done (`done === ""`, not done). More holds: Pause
  task, Accept step result, Hand off task, Open in terminal, Use a stronger model (escalate), Review rules,
  Open task folder, Delete task.
- Mark done is a compact inline confirm (`doneConfirm`): "Mark this task done? History stays available." with
  green Confirm done and Cancel; width does not shift on confirm.
- "Accept step result" replaces "Mark step done" everywhere; its arm text names that it accepts incomplete or
  failed output ("Accept this step's incomplete result? Click again"). It never implies the task is done.

### 3.5 Selection contract

- `openTask(id)` opens the task's Overview (`boardPick = "t"`, `taskView = "overview"`), never a step. Every
  task entry point (title, header, day row, completed row, `data-task`, `data-bpick="t"`) funnels through it.
- A step opens only through an explicit step link (`data-bpick="s<n>"` / `goChat`); nothing silently substitutes
  the latest step.
- A breadcrumb `Tasks / title [/ step]` appears in the inspector; Tasks returns to the list keeping filters,
  expansion and scroll. Navigation never starts a run.
- Async fetch guards: a response that arrives for a different task/step/tab than the current selection is
  dropped (`boardData.id`, `boardPick`, `itab`, `taskView` checks in the `await` continuations).

### 3.6 Hard rules (from CLAUDE.md and NAVIGATION.md, never relaxed)

- `Hub.task_levers` is the only gate; the handoff preview and create go through it and `Hub.tlock` like a click.
- The handoff never re-reads the live context: the digest is saved files only; the haiku pass reads the digest.
- The haiku pass never writes into the task folder; the service writes `task-handoff.md` and the follow-up files.
- Save starts nothing and changes nothing; Create starts nothing (the follow-up is a planned draft). No paid
  work runs until Fred starts the follow-up.
- The source task is never marked done by a handoff.
- No emojis or em-dashes in prose; no new dependency, framework or router; `web/app.js` is edited as anchored
  edits, not restructured (plan 17 drift guard).

## 4. Config keys added (`console/paths.py` DEFAULTS)

| key | default | used by |
|---|---|---|
| `handoff_on` | true | `handoff.run`; false uses the code fallback |
| `handoff_model` | "haiku" | the pass model, through `Hub.model_id` |
| `handoff_max_words` | 800 | `handoff.check` |
| `handoff_timeout_s` | 90 | the pass timeout |

## 5. Verification at the end of every task

```bat
py -m unittest discover -s tests
node --check web\app.js
```

All earlier tests still pass; the task's new tests failed first. Task 4 also drives the Board in headless Edge
at 900, 400 and 340 px against the fake claude and reads the screenshots (Overview, Steps, Files, the action
area, the handoff form, a created follow-up).
