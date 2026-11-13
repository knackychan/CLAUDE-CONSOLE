# Brainstorm: a super agent over every task, and jobs above tasks (2026-11-08)

> Historical design: [D20's task-orchestrator direction](2026-11-11-task-orchestrators.md) supersedes the
> global reasoning role as of 2026-11-11. Jobs/worktrees remain separate; no runtime migration is implied.

- Asked by Fred, from a video report on DeepSeek's write-up "Exploring Super-agent Design: Towards a More Autonomous
  Agent System" (2026-11-01): one Router talks to the developer and never executes, isolated Workers run one task each,
  a watchdog checks that each Worker progresses. The video's claim: one person can follow only 3 to 5 agent sessions
  before context switching becomes exhausting.
- Fred's request: work toward an orchestrator with a clear interface, to supervise many parallel tasks and subjects
  without exhausting load, with a UI of clearly nested jobs and tasks. Then: "I know I have said that I would have
  preferred not to use an orchestrator to optimize tokens, but I believe we need something to watch over all those
  tasks as a super agent, to treat, decide and filter for me before I give my inputs."
- Read: `BRAINSTORM.md` (2, 6, 7.5, 7.6), `PLAN.md`, plans 20, 44 (BRAINSTORM, README), 52 (README, 08-design-lock),
  53 and 55 READMEs, `design/brainstorm/2026-10-13-orchestration.md`, `design/rework/locked/workflow-autopilot.html`,
  `console/supervisor.py` (modes, `MODEL_ALIASES`, limits, `AUTO_KINDS`, `REPORT_ONLY`, `auto_reason`),
  `console/server.py` (`task_row`, the snapshot counts, `_sup_judge`, `_sup_auto`), `console/state.py` (`NEEDS_YOU`).
- State: design approved by Fred on 2026-11-08 (D1 to D6 asked one at a time, D-a to D-f taken as proposed).
  Brainstorm only: no code changed. Each slice in section 9 becomes its own plan; slice 1 is plan 58.
- Mock: locked by Fred on 2026-11-08 as `design/rework/locked/super-agent.html` (the slice 2 window: the super agent
  row and page, the rolled-up list, one box; the later slices only as marked future scenarios). Its notes hold the
  five visual decisions. The explored copy stays at `design/rework/explored/f-super-agent.html`.

## 0. Short answer

Inside one task the Console already has the video's parts: every step is an isolated worker (a fresh CLI session,
the Agent tool removed), the plan 44 supervisor is a router that never executes (one bounded tool-free pass per wake,
acting only through `Hub`), and Stall? with the 30-minute stall wake is a watchdog. What it lacks is the layer above
tasks. Fred is still the router and the filter between tasks: every item that needs him lands unranked in one pin,
each costs a page switch, the list grows with every running task, nothing groups tasks under one goal, and parallel
writers share one working tree.

Add one role and one level:

1. **The super agent.** One role over every job and task, built like the plan 44 supervisor one level up: bounded
   passes on events, over a digest that code rebuilds each time, a short notes file and Fred's standing orders. It
   filters, ranks and decides (within each task's level) before an item reaches Fred. Never a resident session: its
   context never grows.
2. **Jobs.** A goal split into tasks, in stages: the tasks of a stage run side by side, stages run in order. From a
   typed goal (the planner splits it) or a sub-plan folder (plan 53, absorbed). Parallel writers in one repo get a git
   worktree each.
3. **The window shows it.** The super agent is the first row of the list and its page is the queue; projects, jobs
   and tasks roll up to one line each until something inside needs Fred; one box follows the selection.

## 1. Where the Console stands (read 2026-11-08 at `2e7162d`)

| Video | Console today | Where |
|---|---|---|
| One Router that talks to the developer and never executes | Per task only: the supervisor wakes on exceptions (stuck, hold, done, Fred's message, a stall), runs one tool-free pass, acts through `Hub._supervisor_dispatch` | plans 44, 52 |
| Isolated Workers, one task each | Context: yes, every step is its own `claude -p` (or another harness) with the Agent tool removed. Files: no, parallel tasks share the working tree, with a "2 writers" warning (`State.writers`) | plans 17, 20 |
| A watchdog | Time only: Stall? after 10 min with the process alive, the `supervisor_stall_s` wake (1800 s), `task_step_budget_usd` per step | BRAINSTORM 6, plan 44 |
| working / done / waiting | States per session and task, one status line per task (plan 48), Needs you pinned across projects (plan 52 UI-1) | `state.py`, `server.task_row` |
| 3 to 5 sessions per person | Exceptions only (plan 52), one plan gate at `gated`, a decision takes its default after `decision_timeout_s` at `auto` | plan 52 |

Gaps once ten or more tasks run (where the load still lands on Fred):

- G1 No level above the task. Plan 53's build is one, but linear only (one task at a time).
- G2 The list grows with the number of tasks: UI-2 lists the steps under every running row.
- G3 Every item that needs Fred costs a page switch: the pin row opens the task page, the card is there.
- G4 Nothing ranks, merges or batches those items; the pin is in time order, with no recommendation.
- G5 No re-entry view: after time away nothing says what finished, what was decided, what failed.
- G6 The watchdog only sees time: a step that loops while staying active looks healthy.
- G7 Parallel writers in one repo collide; a half-done edit of one task fails another task's verify.

## 2. The shape

```
Fred:  one box (follows the selection)          one queue (ranked, answered in place)
                    \                             /
        SUPER AGENT: one bounded pass per batch of events; memory in two files
        filters, ranks, decides within each task's level, watches progress
                                    |
Project > Job (stages) > Task (chain + task supervisor, plans 17, 44, 52) > Step (one CLI session)
```

| Layer | Decides | Never |
|---|---|---|
| Code (`Hub`) | every gate and cap, what counts as needing Fred, the queue's membership, a job's stage advance on the hub tick | anything that needs judgment |
| Step (a worker) | its own work, in its folder or worktree | anything outside its step |
| Task supervisor (plans 44, 52) | inside one task: retry, add a step, finish, ask | anything across tasks |
| Super agent | across every job and task: rank, batch, put later, recommend; act at `auto` (section 3.5) | Fable, delete, push, merge, a job's goal or task list |
| Fred | the queue, standing orders, levels, merges, every job edit | |

The orchestration brainstorm's D-1 (2026-10-13) refused a persistent orchestrator for four reasons: its context
accumulates and drifts, it must stay alive on a strong model, its decisions are not auditable, and it is one more thing
that stalls. The super agent answers each one: no context carries between passes (code rebuilds the digest each time,
its memory is a 40-line file it rewrites), it runs on Haiku, every pass and act is a line in `super.jsonl`, and when it
fails the queue still shows, unranked. What changes is the scope: it may decide across tasks.

## 3. The super agent

### 3.1 Wakes

One pass per batch of events, never two at once. Events are debounced (`super_debounce_s`, 20 s), so events that
arrive together make one pass:

- an item enters the needs-Fred set (section 3.3), in any project;
- a task ends (done, stopped, stuck) or a job's stage ends;
- Fred sends it a message (its row selected, section 6);
- a sweep every `super_sweep_s` (900 s) while any task runs, skipped when nothing changed since the last pass (code
  compares a hash of the digest).

### 3.2 Input (all built by code, masked, bounded)

- **Digest**: one line per live job and task: project, job and stage, state, current step (kind, model), age, cost,
  retries, last file change, verify FAILs, effective level. Observed sessions in the needs set: one line each.
- **Items**: each pending item in full: kind, question or card text, options and default, time left before a default
  is taken, the task supervisor's last decision and reason, the last handoff's Open questions (clipped).
- **Signals** (section 3.6) per running task.
- **Notes**: `super/notes.md`, its own memory, at most `super_notes_lines` (40) lines, rewritten by each pass; code
  keeps the first 40.
- **Orders**: `super/orders.md`, Fred's standing orders (priorities, what never to raise, what always to raise). Only
  Fred writes it: by editing the file, or by saving an order the super agent proposes (one click).
- **Levels and caps**: each task's effective level (its own mode, else its project's, else the global one) and the
  caps left.

### 3.3 What counts as needing Fred (code, never the model)

The set the Needs you pin shows today, from the snapshot: a task row in group `needs` (`server.task_row`: waiting,
stuck, a STOP question, a hand-off hint, a handed task with a note and no follow-up, a pending supervisor card) and a
session row in group `needs` (`state.NEEDS_YOU`: stop, blocked, stall, failed, interrupted, verify_failed, or a red
gauge). Jobs add four: a job waiting for its confirm, a stage held by a failed or stopped task, a merge ready, a merge
conflict.

Each item has a key (kind, subject id, the event that raised it). When the state that raised it clears (Fred answered
it here, in VS Code or in a terminal), code removes the item and whatever the super agent wrote about it.

### 3.4 Output contract

One JSON object per pass, validated by code the way `supervisor.check` validates the task supervisor's. Anything
malformed is dropped and logged; the item stays in the queue as it was.

```json
{"items": [{"key": "...", "do": "forward|batch|later|act", "rank": 1,
            "say": "one line for Fred", "why": "one line", "batch": "group id", "until": "event or ISO time",
            "act": {"name": "...", "args": {}}}],
 "digest": ["one to three lines for Fred"],
 "notes": "its rewritten notes",
 "order": "an optional standing order to propose"}
```

- `forward`: in the queue at `rank`, with `say` as the recommendation, drawn as the super agent's (◆), never as a fact.
- `batch`: one card for several items of the same kind (three tasks passed their verify: "Accept all three"; two
  tasks ask the same question).
- `later`: out of the queue into the Later fold, with `why` and `until`; it comes back when `until` passes. Never
  hidden: the fold shows the count and every reason, and S on a card does the same by hand until the next pass.
- `act`: only where section 3.5 allows it. Code rechecks every live gate, writes the intent, dispatches through the
  existing route, writes the outcome (the plan 44 pattern, origin `super`).

Always forwarded, whatever the pass says (code): a Fable confirm, a second verify FAIL, a work, spend, pace or usage
cap, a decision without a default, a merge ready, a merge conflict, an uncertain dispatch. These cannot be `later`,
`batch` or `act`; the pass may still add a `say` line.

Queue order (code): always-forwarded items first, oldest first; then the rest by the last pass's `rank`; items newer
than the last pass after those, oldest first, marked "new". When the super agent is off, paused, failed or over its
cap, the always-forwarded items still come first and the rest follow oldest first, with no `say` lines and one line on
its page saying why.

### 3.5 Authority follows the task's level

| Effective level | The super agent may |
|---|---|
| `off`, `suggest`, `gated` | forward, batch, put later, rank, recommend; propose a standing order |
| `auto` | also act: take a decision's default before its timeout; accept a task whose last verify passed with no open question (which lets a job's next stage start); approve a task-supervisor suggestion that waits only because its wake is report-only (`supervisor.REPORT_ONLY`: done, stalled); pause a task with a no-progress signal or a tier over pace |

Never, at any level: confirm Fable, delete, push, merge, change a job's goal or task list, write a standing order,
approve a `stop` or `stepdone` suggestion (Fred's in every mode, plan 44 `AUTO_KINDS`), approve anything a cap holds
(caps are always forwarded), or act on an observed VS Code or terminal chat (those are forwarded or put later, never
acted on).

Checked at `2e7162d`: at `auto` a task-supervisor suggestion stays pending only behind a cap, a kind outside
`AUTO_KINDS`, or a report-only wake (`supervisor.auto_reason`). So the approve act is narrow on purpose: it covers the
report-only case and nothing else.

Undo shows in the digest where an existing route reverses the act: Reopen for an accept (plan 52 Task 4), Resume for a
pause. A taken default or an approved step has already started; its line says so and offers Stop.

### 3.6 The watchdog

Code computes per running task, from facts the service already keeps (`chain.jsonl`, step costs, the `facts.py` git
snapshots, verify lines): spend in the last 30 minutes with no file changed, the same failing test in two verifies,
retries used, and time in the current step against the median for its kind. A signal goes into the digest and the pass
judges it: at `auto` it may pause the task, else it forwards one line ("T04 spent $2.40 in 30 min, no file changed:
Pause?").

### 3.7 Cost and limits

- Models: `super_model` haiku; `super_judge_model` sonnet for a batch that holds a stuck task, a held stage or a
  conflict. Fixed aliases like `supervisor.MODEL_ALIASES`: a hand edit can never move them to opus or fable.
- Limits in config.json, through the `POST /api/config/models` whitelist (as plan 50 did for the supervisor):
  `super_debounce_s` 20, `super_sweep_s` 900, `super_timeout_s` 120, `super_pass_usd` (the budget of one pass),
  `super_day_usd`, `super_notes_lines` 40. Over `super_day_usd` the passes stop for the day and the queue shows unranked.
- Pause on its page stops the passes until Resume; the queue shows unranked meanwhile.
- Spend: one super agent row on the Usage page and a figure on its page. Slice 1 measures real pass costs before any
  act is enabled: a pass reads more than a plan 44 pass (one line per live task, plus each pending item in full).

### 3.8 Files and audit

`~/.claude/console/super/`: `notes.md`, `orders.md`, `super.jsonl` (append only, masked: each pass with its trigger,
the items in, the output, its cost; each act's intent and outcome) and `state.json` (the current annotations, when
each item was first seen, the last pass, Pause, and when Fred last marked Since you looked as seen), so a restart keeps
the queue's order. A replay command like plan 44's (`py -m console --super-replay PASS`) re-runs a recorded digest for
accounting only, never dispatching.

## 4. Jobs

### 4.1 Two ways in

- **A typed goal.** Enter on the box with nothing selected: Prep, then the planner (plan 47) sizes it as one task (a
  step list, as today) or as a job (a task list in stages, each task with its goal). The card says which ("1 task ·
  4 steps" or "Job · 3 stages · 4 tasks"), and Fred can flip it before Start.
- **A sub-plan folder** (plan 53's path, its preview and Create kept): each file is one task, one task per stage in
  name order, unless Fred joins two files into one stage on the card. Slice 4 places the entry point.

### 4.2 Stages, not a graph

A job is a list of stages; a stage is a set of tasks that run side by side; stages run in order. One index, advanced
by code on the hub tick when every task of the current stage is accepted (by Fred, or by the super agent at `auto`).
No dependencies between single tasks, no priorities, no timers, no reordering by the service. Each task starts as an
ordinary supervised task through Prep, the planner and `create_task`, with the job's goal, the done list and the
earlier stages' open questions in its prompt (plan 53 section 4.4's item prompt, kept).

A failed or stopped task holds its stage. The item "stage 2 held: T05 failed twice" offers Retry, Skip task (a job
edit: Fred only) and Stop job.

Files: `~/.claude/console/jobs/<id>/job.json` (goal, project, source, stages with task ids, index, state, cost) and
`job.jsonl` (events); `task.json` gains `job` and `stage`. Saves through `paths.write_text_atomic` (plan 54).

### 4.3 Gates and levels (D-a)

A job takes its project's level, and the head of the job page switches it. At `gated`, the job's confirm is its one
plan gate and covers the plan gates of its tasks (no `plan_hold` on a confirmed job's tasks). Decisions, Fable, caps,
a second FAIL and every other hard stop are unchanged, and each task's Accept stays Fred's; the super agent batches
them ("stage 1 done: 3 tasks passed, Accept all"). At `auto` the super agent may accept those, so stages advance on
their own.

### 4.4 Worktrees for parallel writers (D6, D-d)

A per-project switch, `worktrees` in the project's entry of config.json, off until slice 5's live check. With it on:

- **Who gets one.** In a stage with more than one writing task in the same repo (a task with any step of a write
  kind), each of them runs in its own worktree. A lone writer uses the main tree. A standalone task that starts while
  another writer is live in its repo also gets one.
- **Where.** `~/.claude/console/wt/<4 hex>` (short, for the Windows path limit), on branch `console/<task id>`, made
  from the main tree's HEAD at start. When the main tree had uncommitted files, the task's Brief says "worktree from
  <sha>; the main tree had N uncommitted files".
- **Setup.** An optional `setup` command per project (an argument list, never a shell string) runs once in a new
  worktree, before the first write step; a failure is an item.
- **Runs.** Every run of the task uses the worktree as its folder. Hooks report the worktree as `cwd`; the service maps
  it back to the project and the task.
- **Accept** commits the worktree's changes on its branch. This is the Console's only commit; today it only reads git.
- **Merge.** When no writer is live in the main tree, the accepted branches of a stage form one item ("2 branches
  ready to merge into master"); Fred's click merges them in order (`git merge --no-ff`). A conflict or a dirty main
  tree aborts that merge and raises an item: Open in terminal, Try again, Discard branch (two clicks: it deletes work).
  After a clean merge the worktree and its branch are removed.
- **Without it.** A folder that is not a git repo, or a project with the switch off: the writers of a stage run one at
  a time; standalone tasks keep plan 20's shared tree and the "2 writers" warning.

## 5. The window

The mock comes in a later session, built on the locked `workflow-autopilot.html` (Console Cells tokens, type and cell
motif unchanged; orange still means "for you" and nothing else). States to draw: the queue, sorting, calm, off, a job,
a merge, a task in a job; dark and light; 900 and 400 px. What it must show:

- **The super agent row** replaces the Needs you pin. It is the first row of the list and is always there: ◆ Super
  agent, "N for you" in orange when N > 0, and one code-built line (`6 running · 2 later · 5 settled since 13:05`).
  The header's "N need you" button and the tray count the same queue (what reaches Fred), not the raw needs set.
- **Its page is the home pane** (shown when nothing is selected; plan 38 U8's home pane), with four sections:
  - For you: one card per item or batch, self-contained: `project › job › task`, the kind and age, the ask in one
    sentence, the super agent's recommendation (◆, one line), the options or buttons inline, the default with its time
    left at `auto`, Write your own answer (the box targets that task in answer mode), Open. Keys: J and K move, 1 to 4
    pick an option, Enter confirms, S puts it later, O opens. An answered card leaves and the next one takes focus.
  - Later: the count and each reason.
  - Since you looked: what was decided (with Undo where a route exists), what finished and failed, the spend, since
    the `looked` time in `state.json` (its `seen` map holds each item's first-seen time, plan 58); Mark seen.
  - Orders: the file's lines, a proposed order with Save, Edit.

  Empty: "Nothing for you." with the running count and the last pass time. A pass running: "Sorting N new items".
  Off, paused or over its cap: one line with the reason, items unranked.
- **Roll-up list.** At every level the list shows a one-line summary, the children that need Fred, and everything
  when selected. A project is one line when nothing inside is for Fred (`CLAUDE CONSOLE · 2 tasks · 1 paused`); it
  opens on click or when something inside is for Fred. A job is one line (`stage 2/3`) with only its for-you tasks
  under it, or all its tasks when it or one of its tasks is selected. Steps show only under the selected task (this
  changes UI-2). Observed chats stay dashed rows under their project.
- **The job page**: the head (eyebrow `project · job`, title, status pill, facts: Stage, Tasks, Worktrees; the level
  switch and the cost on the right), sections Goal and Split (stages as groups: side-by-side tasks as cards in one row,
  stages stacked in order, ◆ super agent lines where it acted), the dock card (this job's first item: a held stage, a
  merge, a conflict), the box, the bar (Pause job, Stop job). Built from plan 55's seam parts (`pageHead`, `sect`,
  `planRow`, `svLine`, `dockCard`, `barHtml`).
- **The task page** is the locked one; for a task in a job the eyebrow reads `project › job` and the facts add the
  worktree.

## 6. The one box

It follows the selection; code routes it, no model. A target chip at its left always says where Enter goes.

| Selected | The chip says | Enter does |
|---|---|---|
| nothing (the home pane shows) or a project | New work · project | Prep, then the planner sizes it as a task or a job |
| the super agent row | Super agent | wakes one pass with the message; its reply shows on its page and in the digest; it may propose a standing order (one click to save) |
| Write your own answer on a card | Answer · task | the plan 42 answer mode for that task |
| a job | Job · title | wakes the super agent with that job in scope; a change to the job's tasks comes back as a card for Fred |
| a task or a step | Task · title | the plan 42 and 48 modes (guidance, answer, next step), unchanged |

## 7. What this reverses and what stays

| Rule | Before | Now |
|---|---|---|
| Orchestration D-1 (2026-10-13) | no orchestrator agent | a super agent made of bounded passes; still no resident session and no subagents inside steps |
| Plan 44 non-goals | no cross-task or cross-project decisions; no supervision of VS Code or terminal chats | the super agent decides across tasks; observed chats are ranked, never acted on; the task supervisor keeps its own non-goals |
| BRAINSTORM 2 non-goals | no worktree management, no task graph, no scheduler | worktrees for parallel writers, per project; still no graph (a list of stages) and no scheduler (the hub tick advances one index) |
| Plan 20 | no worktree per task | a worktree for a writer that runs beside another one, when the project's switch is on |
| CLAUDE.md data rule | write only in `~/.claude/console/` (and plan 28's plan mirror) | also: worktrees under `~/.claude/console/wt/`, their git metadata in the project's `.git`, `console/*` branches, the commit at Accept and the merge on Fred's click; a listed project's worktree counts as that project for runs. CLAUDE.md changes when slice 5 lands, not before |

Unchanged: the scripted chain, the per-task supervisor, every hard stop and cap, the levels, Fable only by Fred, the
localhost guard and every hook rule.

## 8. Effects on open plans

- Plan 52: its live check comes first; the super agent stands on its levels, decision cards and finish card.
- Plan 55: Tasks 1 to 3 (head, dock, box, bar, body, plan) stand; the job page reuses their parts. Task 4 (the list,
  UI-1 and UI-2) is replaced by slice 2, and its D10 and D11 move there. Plan 55 Tasks 5 to 7 follow unchanged.
- Plan 53: absorbed as the folder path of jobs (slice 4). Its item prompt (4.4), drift check (4.6) and failure paths
  (4.9) carry over. Its proposed D17 wording ("no parallel items") is replaced by BRAINSTORM D17, which allows stages.
- Plan 56 (skill library) and plan 57 (Codex port, on its branch): independent.

## 9. Slices

Each slice is its own plan, written when the one before it is built and checked. UI code waits for the mock to be
locked.

| # | Slice | Needs | Done when |
|---|---|---|---|
| 1 | Super agent v1: items, digest, pass, queue order, notes, orders, audit, limits, Pause, the Usage row; no acts | plan 52 live check | real items come back ranked and annotated over HTTP; a failed pass leaves them unranked; the cost per pass is measured |
| 2 | The window: super agent row and page, cards answered in place, Later, Since you looked, roll-up list, box chip, header and tray count | slice 1, plan 55 Tasks 1 to 3, the mock made and locked | Fred answers a day's items from the queue without opening a task page |
| 3 | Acts at `auto`, Undo, order proposals | slice 2 | a week at `auto` on one project, every act in the digest, none undone because it was wrong |
| 4 | Jobs: planner sizing, stages, the folder path, the job page, stage advance | slice 2 | a typed goal runs as a job of two stages to the end |
| 5 | Worktrees: the switch, create, setup, commit, merge item, conflict item | slice 4 | two writers in one repo finish side by side and merge clean |

## 10. Risks

- **A wrong act at `auto`.** Bounded by the level, the code gates, the caps, the never list, the always-forward list,
  the audit and Undo where it exists; slice 3 starts on one project.
- **Something important filtered away.** Later is never hidden (count and reasons in sight), the always-forward list
  is code, and the item set comes from live state, not from the model.
- **Cost creep.** Debounce, one pass at a time, sweeps only on change, Haiku by default, `super_day_usd`, its own
  Usage row.
- **Two supervisors confuse.** Only the super agent speaks to Fred in the queue; the task supervisor's lines stay on
  the task page (◆ Supervisor, plan 55 UI-5) and its cards reach Fred through the queue.
- **Worktree costs.** Installs per worktree, disk, the Windows path limit, merge conflicts. Behind a per-project
  switch, in the last slice, with short paths.
- **Opus spend on jobs.** Each task of a job gets its own planner pass (opus); slice 4 decides whether the job's split
  can write the step lists of small tasks directly.
- **Stale ranks.** A pass ranks what it saw; newer items sit after the ranked ones, marked new, until the next pass;
  resolved items leave at once.

## 11. Decisions (Fred, 2026-11-08)

| # | Question | Decision |
|---|---|---|
| D1 | What a job is | A goal split into tasks, run in order or side by side: Project > Job > Task > Step |
| D2 | Who splits a goal | Both: the planner splits a typed goal and Fred confirms; a sub-plan folder gives one task per file |
| D3 | How Fred's words reach the right place | One box that follows the selection, routed by code |
| D4 | The super agent's form | Event passes over a code-built digest, with a notes file and standing orders; no resident session |
| D5 | Its authority | Follows the task's level: filter, rank, recommend; at `auto` also act within caps (section 3.5); never Fable, delete, push, merge or a goal change |
| D6 | Parallel writers in one repo | A git worktree per parallel writing task, merged on Fred's click |
| D-a | A job's confirm | Covers its tasks' plan gates |
| D-b | Models | Haiku; Sonnet for a batch with a stuck task, a held stage or a conflict |
| D-c | Sweep | Every 15 min while tasks run, skipped when nothing changed |
| D-d | Worktree switch | Per project, off until slice 5's live check |
| D-e | Running cap | No new knob: the pace and usage holds of plans 18 and 40 apply to every task a job starts |
| D-f | Shown name | Super agent |

Two refinements made while writing this file, against the code: "approve a task supervisor's suggestion" is limited to
report-only wakes (section 3.5), and "start a job's next stage" is code on the hub tick once a stage is accepted, so
the super agent's part is the accept (section 4.2).

## History

- 2026-11-08 - Brainstorm with Fred from the super-agent video report: the gap analysis, D1 to D6 asked one at a time,
  Fred's reversal of D-1 ("something to watch over all those tasks as a super agent"), the design approved as
  presented with D-a to D-f as proposed; this file written. Fred moved the mock to a later session. No code.
- 2026-11-08 - Slice 1 written as plan 58 (`plans/58-super-agent/`, plan only, its D1 to D11 open for Fred). This
  file now names `state.json` in 3.8 (it replaces `seen.json`; Since you looked reads its `looked` time). Found while
  writing it: plan 44's `supervisor.append_log` can write a line that no longer parses (plan 58 README section 2).
- 2026-11-09 - Slice 3 redesigned with Fred as acts and chat (`2026-11-09-super-agent-chat.md`, BRAINSTORM D19): a
  chat with Console MCP tools presses card actions on his word; at `auto` the passes may press any served action
  except a code list kept for Fred (that file's 3.1), which replaces the four narrow acts of section 3.5. The cards
  of section 5 stay.
