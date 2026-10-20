# Plan 49: Workflow autopilot. One prompt, a plan, a run loop, Fred only at real decisions

Status: decided 2026-10-20 (Fred: D1 c, D2 to D6 as recommended). Task files 01 to 07 written the same day;
nothing implemented. Process only: the visual design of the action bar is another chat's work.

| # | File | Delivers | Depends on |
|---|---|---|---|
| 1 | [01-intake-chain.md](01-intake-chain.md) | a supervised Start runs the planner's whole chain | none |
| 2 | [02-exceptions.md](02-exceptions.md) | the two bugs (2a), the supervisor on exceptions only (2b) | 1 |
| 3 | [03-decision-card.md](03-decision-card.md) | DECISION block, the card, the default after a timeout | 1 |
| 4 | [04-finish.md](04-finish.md) | the finish summary, Accept, Reopen | 1 |
| 5 | [05-levels.md](05-levels.md) | gated / auto / suggest / off, gated by default | 2, 3 |
| 6 | [06-actions-contract.md](06-actions-contract.md) | GET /api/task `actions` for the UI chat | 3, 4, 5 |
| 7 | [07-live-check.md](07-live-check.md) | headless and live checks, docs | 1-6 |
| 8 | [08-design-lock.md](08-design-lock.md) | the locked UI: `design/rework/locked/workflow-autopilot.html` | 6 |

Tests first in every task, one commit per task, `py -m unittest discover -s tests` at each boundary. Other chats
edit `PLAN.md`, `BRAINSTORM.md` and `web/app.js` in parallel: anchored edits, stage only this plan's lines.
Master: [../../PLAN.md](../../PLAN.md). Lands on plans 17 (chain), 24 (plan and replan), 42 (messages),
44 (supervisor backend), 47 (planner), 48 (three moments). Design: [../../BRAINSTORM.md](../../BRAINSTORM.md) 7.6.

## 1. What happened on task 20261020-081005-06c2 (ARTCOUSTIC-AUDIO-REPORT, 2026-10-20)

Timeline from `~/.claude/console/tasks/20261020-081005-06c2/` (chain.jsonl, supervisor.jsonl, task.json):

| Time | What | Cost |
|---|---|---|
| 08:10 | Prep (haiku, 7 turns) and the planner (opus, 5 turns): scope ok, steps `scout, design, code` (+ verify by code) | $0.121 |
| 08:10:55 | Start, `supervised: true`, mode `suggest` (config default). Task created with ONE step (scout); design and code saved as `supervisor.proposed`, `progression: manual` | |
| 08:11:22 | Scout done (27 s). Task `waiting`, why `choose next step`, owner `fred`. Four open questions in its handoff | $0.010 |
| 08:11:42 | Wake 1 after the 20 s debounce: haiku pass suggests `add_next_step design`; `for_fred` repeats two of the scout's questions. Mode suggest: card waits for Approve | $0.002 |
| 08:14:05 | Fred switches the task to `auto`. The suggestion is marked `superseded`. No wake follows. The task sits at `choose next step` for good; the page says "supervised · auto", the card shows the last audit line ("Add a step"), and "Paused: step 1 ended. Nothing starts until you Resume" | |

Root causes, in order of weight:

1. **Supervised intake throws the chain away** (`console/server.py:2903-2924`, `_supervised_task`, plan 44 D7).
   The planner wrote three steps; `_supervised_task` keeps only the first and makes the task `progression: manual`.
   So every step end is a manual boundary (`console/tasks.py:682-685`), every boundary is one paid wake plus a
   20 s debounce, and in `suggest` every wake needs Approve. The automatic chain of plan 17 (steps in order,
   brief between, verify after the last edit, fix once on the escalated route, retry once, stuck after the second
   failure) is exactly the run loop Fred asked for, and supervised mode does not use it. The scripted chain runs
   only with the supervisor off (plan 48 D2, D5).
2. **A mode switch supersedes the card and never re-wakes.** `_sup_mode` (`server.py:2130-2154`) calls
   `_supervisor_fred` (`server.py:2067-2094`), which drops a pending `suggest` and "emits no wake" (docstring, 2070).
   The boundary's event id is already consumed by wake 1's claim, so `wake_supervisor` refuses it
   (`server.py:1559`, `_sup_consumed` 1542-1547) and `boundary()` (`supervisor.py:214-246`) finds no newer
   transition. Auto mode has nothing to act on until a new transition, which never comes. Expected: a switch to
   auto at a boundary dispatches the standing suggestion (it was checked against the same revision) or wakes
   once on the mode-change chain line.
3. **The questions have no owner.** The scout's `## Open questions` ride the brief into the digest
   (`supervisor.py:446-448`); the supervisor may not answer them (plan 44 D5, `supervisor.py:548-549`), so it
   pastes them into `for_fred`. Nothing says which model answers a question from the repo and which one is Fred's.
4. **The "Paused" note lies.** `web/app.js:3760` shows it whenever `paused_after` is set (owner fred at a boundary,
   `server.py:3935`) and `lv.resume` is not the manual text; at a supervised boundary `task_levers` overwrites
   `resume` with `not paused` (`server.py:1065-1067`), so the note appears although nothing is paused.
5. Smaller: the pass model is haiku on every wake (D4), yet it is asked to write a design step's instructions
   from a 12 KB digest; the planner (opus) had already written that goal. Duplicate work, weaker model.

Fix 2 and 4 are bugs to fix whatever Fred decides below. Fix 1 and 3 are the redesign.

## 2. Target flow

Principle: **the plan drives, the supervisor watches.** Steps come from the planner and the design step, as today
for automatic tasks. The supervisor pass runs only on exceptions, never between two steps that went well. Fred is
interrupted only for a real decision, a cap, a second failure or the final accept.

```
PROMPT  Fred types, Enter (plan 48 moment 1)
  |
INTAKE  Prep, haiku, 1 call: enhanced brief, route, demand, first scouting        (exists: prep.run_prep)
  |
PLANNER opus, read-only, <= 10 tool calls: scope, note, step list                 (exists: planner.run)
  |     The card: scope note, steps, one Start. Start = the only click of a normal task.
  |
START   POST /api/task supervised: the FULL step list becomes the chain (change A)
  |
RUN LOOP (the plan 17 chain, unchanged where it works)
  |  scout haiku -> brief -> design opus (writes plan.md, plan 24) -> [plan gate, D1] -> code sonnet -> brief
  |  -> verify (one model up) -> PASS: next / done
  |                           -> FAIL 1: fix on the escalated route, verify again   (exists: _insert_fix)
  |                           -> FAIL 2: stuck "verify failed twice"               (exists)
  |  crash or no handoff: retry once with the reason, then stuck                   (exists: _retry_or_stuck)
  |  Replan: line from a step -> replan step (haiku) -> applied without confirm when auto (replan_auto)
  |
  |  SUPERVISOR wakes only here (change B):
  |    stuck          -> retry with a note (sonnet pass), or escalate: Fred's card with the two failures
  |    asks: question -> never answered by the supervisor; becomes a DECISION card (change C)
  |    plan hold      -> confirm, when the autonomy level allows it
  |    replanned      -> confirm / keep, when the autonomy level allows it
  |    Fred's message -> guidance for the running step (plan 42) or a next step at done (plan 48)
  |    done           -> the finish card (change D)
  |
FINISH  the last verify PASSed: summary card (goal, steps, verdicts, files touched, cost), Accept / Reopen
```

### Change A: supervised intake keeps the chain

`Hub.create_task(supervised=True)` builds the normal automatic task (`tasks.new_task` with every planned step,
`plan_steps` adds the verify) and attaches the supervisor policy. `_supervised_task`, `progression: manual` at
intake and `supervisor.proposed` go. The chain's own rules do the progression; the supervisor's `boundary()`
loses `choose_next` as a wake trigger for these tasks (a manual task made by plan 36/39 Add step keeps it).

What this removes per step: one haiku pass ($0.002 to $0.01, 12 KB digest), the 20 s debounce, and one Approve
in suggest mode. What stays per step: the brief pass (haiku, $0 when the handoff is under 400 words).

### Change B: the supervisor is the exception handler

Wake triggers: `stuck`, `hold` (plan ready, plan size, replanned), `asks:` (to build the decision card, no model
call), `done`, `message`, `stalled`. Decisions it may still return: `retry`, `confirm`, `keep`, `finish`,
`escalate_to_fred`, `wait`, `stop` (stalled). `add_next_step` stays only for a `message` wake and for `done`
("anything left?", D12). Pass model: sonnet on stuck and stalled (today), haiku elsewhere; opus never.

The chain's own retry (crash) and fix (FAIL 1) run before the supervisor sees anything. The supervisor's one
retry per step (plan 44 cap) is the third attempt and needs a concrete note; without one it escalates.

### Change C: one decision card instead of a question dump

Three kinds of question exist today and they are mixed:

| Kind | Today | Target |
|---|---|---|
| Fact a model can read in the repo ("is vitest in package.json?") | an Open questions line, carried to Fred | the design step must answer it from the repo; the design kind file says so; a design handoff with an unanswered fact question is a plan check failure (`a Decisions line is a question`, plan 24 3.4, already exists) |
| A real choice (SHEETS_DIR vs PRODUCT_SHEETS_DIR) | `STOP:` question or `Plan gap:`, free text, the task waits | `DECISION:` block in the handoff: the question, 2 to 4 options, a default and why; the service parses it once (code, no model), the task waits with the card; Fred clicks an option or types; the answer joins plan.md Decisions (plan 24 `plan.add_answer`) |
| A gap found while coding | `Plan gap:` (plan 24) | unchanged, rendered as the same card with the free-text option only |

Timeout (D2): with a default and the task on an autonomy level that allows it, the service takes the default after
`decision_timeout_s` and logs `decision taken by default: <option>` in the chain; the card stays visible as
history. With no default or on the gated level, the task waits.

Format in the step prompt (one more rule line, `step_prompt.md`): "When you must stop for a choice, end with
`DECISION: <question>` then one line per option `- a) <option>` and `DEFAULT: a <why>`." Parsed like the STOP
line; a `DECISION:` without options is a plain question.

### Change D: finish and accept

At `done` after the final brief the service builds the summary card in code (no model): goal, each step's kind,
model, verdict and cost, files touched (facts), total cost, open questions still listed. Actions: Accept
(`task_lever done`, today's Finish), Reopen (the message box in `next` mode: Fred's words become the next step,
plan 48 D6). The D12 "anything left?" haiku wake stays as the card's one optional line (suggest only).

### Autonomy levels (D1)

One setting, three values, per project with a global default (`supervisor_projects` already maps project to a
word; it takes these words instead of off / suggest / auto):

| Level | Plan gate | Replan | Decision with a default | Caps |
|---|---|---|---|---|
| `gated` (A) | waits for Confirm once (`plan_hold` on for the task) | Confirm | waits | plan 44 caps |
| `auto` (B) | runs on | applied | default after the timeout | plan 44 caps |
| `suggest` | as today: every supervisor decision needs Approve; the chain still runs its steps | Confirm | waits | - |
| `off` | the scripted chain, no supervisor (plan 48 D5) | Confirm | waits | - |

Hard stops at every level, unchanged: Fable confirm, pace and usage holds, the second verify FAIL, the work and
spend caps, Pause, Stop, Delete, a decision without a default.

Switching up from the card (Fred, 2026-10-20): every gate that `auto` would pass by itself carries a second button
that passes it now and moves the project to `auto` for the future: on the plan-confirm card "Confirm, and run
plans automatically from now on"; on a decision card with a default "Take the default, and take defaults from
now on". One POST (`/api/task/confirm {task, remember: "auto"}`, `/api/task/message {..., remember: "auto"}`):
the project's level is written to `supervisor_projects` and the task's own mode set to `auto`, then the gate
passes. The task menu's level segment switches back down at any time.

## 3. User actions per task state

The service already computes most of these (`Hub.task_levers`, `message_availability`, `supervisor_view`); the
UI places them. Primary = the one button in sight; secondary = the bar; menu = the task menu. Every state has the
message box (plan 42: guidance while running, answer at a question, next step at done).

| State | Row says | Primary | Secondary (bar) | Menu | Box mode |
|---|---|---|---|---|---|
| preparing | `preparing · Prep, then the planner` | - | Drop | - | - |
| ready (card) | `ready · N steps · Start` | Start | Edit steps, Drop | Edit prompt, Review rules | - |
| running | `running · 02 code · sonnet · 3m` | - | Stop, Pause | Hand off, Retry on a model (after a failed attempt), Open in terminal, level, folder, Delete | guidance (queued for the turn end) |
| plan ready (gated) | `plan ready · confirm` | Confirm plan; Confirm and run plans automatically from now on | Edit plan, Redo design, Stop | as running | guidance |
| needs you: decision | `needs you · <question>` | the options (a, b, c); with a default: Take the default from now on | Redo design (plan gap), Stop | as running | answer (free text = another option) |
| needs you: supervisor card | `needs you · <decision>: <reason>` | Approve | Reject (with a note), Stop | as running | next step (words replace the suggestion) |
| needs you: hold | `held · confirm Fable` / `over its pace` / `usage limit until hh:mm` | Confirm / Run anyway / Retry on a model | Stop | as running | guidance |
| needs you: second failure | `failed twice · <detail>` | Retry on a model (note) | Accept step result, Hand off, Finish | Delete | guidance carried into the retry |
| stuck (crash, no handoff) | `stuck · <why>` | Retry | Accept step result, Finish | Delete | same |
| paused | `paused · after 02` | Resume | Stop | as running | guidance (delivered after Resume) |
| stopped | `stopped` | Resume (continues in the step's session) or Retry | Finish | Delete | guidance |
| done | `done · 4 steps · $0.42` | Accept | Reopen (the box) | Hand off to a follow-up task, Open folder, Delete | next step |
| handed | `handed off` | Start next task | - | Delete | - |

Observed chats (VS Code, terminal, Codex, OpenCode: `source != window`): read only. Row, Steps, gauge, Chat, usage.
Levers as forks only (plan 03, plan 37): Continue as a fork, Verify as a fork, Hand off, Escalate as a fork, Open in
terminal. No Stop, Pause, message, decision card or supervisor; the status says `observed · VS Code`. Nothing is ever
written to another process's stdin (plan 42).

## 4. Cost of the target on the same task

Prep $0.005, planner $0.12, scout $0.01, design on opus (the big one, $0.3 to $1), code sonnet $0.1 to $0.3,
verify $0.05, briefs $0, supervisor $0 when nothing goes wrong. Fred's clicks: Start, maybe one decision, Accept.
Today: the same plus one wake and one Approve per step, and the design step written by a haiku pass.

## 5. Decisions (Fred, 2026-10-20: D1 c; D2 to D6 the recommended option)

| # | Question | Options | Taken |
|---|---|---|---|
| D1 | Autonomy default | (a) `gated`: approve the plan once, then it runs; (b) `auto`; (c) per project, global default `gated` | (c) with `gated` as the default: the plan is the one thing worth a look, and a project like CLAUDE CONSOLE can be `auto` later |
| D2 | Decision timeout on `auto` | (a) 10 minutes then the default; (b) no timeout, always wait; (c) take the default at once, log it | (a) |
| D3 | Who answers fact questions | (a) the design step, from the repo, as a rule of its kind file; (b) one extra haiku `answer` step inserted by the service | (a): no new step kind |
| D4 | The old supervised intake (one step, the rest proposed) | (a) removed; (b) kept behind `supervisor_mode: suggest` | (a): the chain plus `suggest` covers it |
| D5 | Finish summary | (a) built in code from briefs and facts; (b) the D12 haiku wake writes it | (a), the wake adds one line at most |
| D6 | Bug fixes 2 and 4 of section 1 | (a) fixed first, in their own small commit, before the redesign | (a) |

The task files at the top of this README carry each decision.
