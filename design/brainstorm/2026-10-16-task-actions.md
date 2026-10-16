# Task actions on the task page and on any step: brainstorm

Status: **decided** 2026-10-16 (Fred took option 2 and the recommended placement, then (a) on D1 to D6 the same
day: nothing is open). Becomes [plan 39](../../plans/39-task-actions.md) (to write). Design only: no code changed here.

Context: [CLAUDE.md](../../CLAUDE.md), [BRAINSTORM.md](../../BRAINSTORM.md) (non-goals, 7.5),
[plan 36](../../plans/36-next-step/README.md) and its [design guideline](2026-10-15-next-step.md),
[plan 38](../../plans/38-ui-audit-fixes.md) (U3, U11).

## 1. Fred's problem

"How can we improve the workflow to be able to place the buttons such as Verify / New task etc on every step,
so we can branch a step and make it start a new sub-step from there. OR from the main task overview, there are
no buttons to control anything about that specific task, like adding a new step, doing a Verify step or
anything, and thus we always have to click on the last sub-step to actually take action if we want to Mark done
or anything."

Two complaints in one: the task page is a summary with no controls, and an older step is a dead end. Both are
about where the levers are, not about new kinds of work.

## 2. What the code allows today (read 2026-10-16, branch claude/nice-cori-d93jgp)

- **Task-level availability already exists in the service.** `Hub.task_levers` (console/server.py) returns
  `add_next` and `done` for every task, chat or chain, and GET /api/task carries `levers`, `next_step`
  (`Hub.next_availability`) and `step_levers` (`Hub.levers` of the current step's session). The task page,
  `inspTask` in web/app.js, renders Stop / Pause / Resume / Retry in its head and Mark done / Delete at its foot;
  it reads none of `add_next`, `next_step` or `step_levers`. The gap is in the Board, not in the service.
- **Lineage is already recorded.** `tasks.append_step` stamps every manual step with `source_step` and
  `source_session`; `Hub.start_step` reads the step's own `received-handoff.md` and reports
  `handover from step NN` from `source_step`, never from `n - 1`. The preview and append APIs already take
  `source_step` and `source_session` from the client. Only `Hub._next_source` insists that the source is the
  current, last step (`source["n"] != len(task["steps"])`, "Next steps start from the latest step").
- **An older step's handover is buildable.** `Hub._next_package` falls back to the step's saved note
  (`tasks.read_note`) when the stream is gone, and stamps the current git facts separately from the source's
  recorded facts.
- **The Board form always targets `t.current`.** `openNextForm`, `nextPreview`, `startNextStep` and
  `nextReseed` find the source with `t.steps.find((x) => x.n === t.current)`; `nextActions` hides the buttons
  unless `s.n === t.current`; `histFoot` shows "Next steps start from the latest step · Go to step NN" on an
  older step. `verifyNext` already shows the one-click pattern: pick the current step, then open the form with
  Verify selected.
- **The Board's Hand off and Start new task never render.** `nextSecondary` reads `levers.handoff` and
  `levers.next`, but the Board's `levers` is `task_levers`, which has no such keys; they live in `step_levers`.
  This is a plan 36 Task 3 slip and plan 39 fixes it in passing.
- **The data model is flat.** `task.json` holds `steps` (monotonic `n`), one `current`, one `last_good`;
  `chain.jsonl` is append-only. BRAINSTORM non-goals rule out a task graph. A sibling step (02b) or a sub-task
  would be a second shape for every reader of `steps`.
- **Rules that bind.** `Hub.levers` alone decides Continue / Verify / Handoff / Escalate; a chat is only ever
  forked, never resumed in place; `Hub.task_levers` owns append availability and the UI must not reproduce the
  business rules (plan 36 3.4); plan 36 3.1 says historical steps are inspectable, not branch points, which this
  brainstorm revises (section 4.2); plan 38 U11: no more chrome than the action needs; the next-step guideline
  binds no new global shortcut.

## 3. Options considered

| # | Option | What changes | Cost | Risk |
|---|---|---|---|---|
| 1 | Task page as a control surface, chain stays linear | The task page dock gets Add next step, Verify, Continue, Finish task, Hand off, all from the latest step. Older steps keep the "latest step" footer. | web/app.js only, about 60 lines, one headless test | none to the service |
| 2 | Option 1 plus Add step from any done step | Any done step with a session and a saved note or final reply is a source. The new step takes the next number (04), records `source_step` 02, `current` moves to it. The chain list shows `from 02`; the Received tab says "Handover from step 02". No letters, no sub-tasks. | server `_next_source` about 20 lines, `tasks.append_step` about 10, `task_row` one field, Board about 80 lines, tests about 10; no new file, no style.css beyond nothing | the project tree is shared: a branch from 02 after 03 edited files runs on today's files with yesterday's handover (section 4.3 says so in the form); a second shape of `steps` is avoided only as long as lineage stays one integer |
| 3 | Branch means fork to a new task | An older step seeds a separate task in the same project with its handover, through the existing Brief a new task / Start new task flow. | smallest service change | exactly what Fred does not want: a new id instead of acting inside this task, history split across two folders |

Sibling steps (02a, 02b) and sub-tasks were weighed and dropped: both add a second shape to `steps`
(numbering, `current`, `last_good`, the fix insert, the Board rows, Finish, `Hub.task_levers`) for the same
outcome as option 2's one tag. A task graph is a BRAINSTORM non-goal.

**Fred's choice (2026-10-16): option 2.** The task page becomes a control surface with the full dock bar;
per-step actions live in the dock bar of the picked step only (no hover actions on chain rows, no "..." menu,
no new keys); a branch is shown as a `from 02` tag on the row and in the Received tab, not as an indented
sub-list.

## 4. The design

### 4.1 The task page: a control surface

The task page (`inspTask`) gets the same docked bar a step page has (`idock`: the head and levers stay, the pane
scrolls). The bar carries, in this order, each only when the service allows it:

| Button | Availability (service field) | What it does |
|---|---|---|
| Add next step (filled `go` when allowed) | `levers.add_next === ""` | picks the latest step and opens the inline form on its Chat tab, as `openNextForm` does today; one click, not two |
| Verify | same as Add next step | the same, with Verify selected (`verifyNext`) |
| Continue | `step_levers.continue === ""` and the latest step is a chat whose turn is over | D1: jump to the latest step's Chat tab and focus the follow-up box |
| Finish task | `levers.done === ""` | the existing POST /api/task/done with its two-click arm; replaces the foot's Mark done (one action, one button) |
| Hand off | `step_levers.handoff === ""` | the existing session lever on the latest chat (`stepAct("handoff")`) |
| Delete (`stop` style, last) | `levers.clear === ""` | unchanged |

Stop / Pause / Resume / Retry stay in the head: they are run controls, not next-action controls. The ask box,
prompt.md, open questions and Chain log stay as they are. A disabled Add next step keeps its reason in the title,
as the step dock does today; nothing else disabled is shown (next-step guideline 5: no permanent toolbar of
disabled actions).

### 4.2 Any done step is a source

Plan 36 3.1 said "historical steps are inspectable, not branch points". Fred revises that: a done step with a
session and a saved note or final reply may be the source of a new step. The chain stays a list.

- **Service rule.** `Hub._next_source(task_id, source_n, source_sid)` drops the three "latest step" conditions
  (`source["n"] != len(task["steps"])`, `any(s["n"] > source["n"])`, and `current_step` as the only candidate)
  and takes `tasks.step(task, source_n)` instead. The source must have the given session, be `done` (D2 says
  which other states), carry a saved note or a final reply, ask no pending question, and have no live run. The
  task conditions stay: a manual boundary (`choose next step`, `VERDICT: FAIL`), a done task (reopen), a replied
  legacy chat, a replied manual chat; a running automatic chain, a stuck or stopped task still answer
  `task is <state>` and use their recovery levers (D5).
- **Availability per step, from the service.** GET /api/task gains `sources`: `{"02": "", "03": "no saved
  note", ...}`, `_next_source` run once per step, so the Board shows a button only where the service would accept
  the request. `next_step` stays as it is for the latest step. `Hub.task_levers["add_next"]` stays the task-level
  answer ("" when any source is available).
- **Append.** `tasks.append_step(task, kind, goal, pick, now, source=None)`: the source is explicit; the new
  number is `len(task["steps"]) + 1`, never `source["n"] + 1`; `checked = source["n"]` for a verify;
  `source_step` and `source_session` as today; `current` and `last_good` go to `source["n"]` until `start_step`
  moves `current` to the new step (as today). When the latest step is a chat still in `running` (its turn over),
  D3 decides whether it is closed or the branch is refused.
- **Package and prompt.** Unchanged: `_next_package` reads the source's final reply or saved note and stamps
  today's git facts under "Current project facts (captured separately)"; `received.md` says "saved handover from
  step 02"; `start_step` reads the step's own `received-handoff.md` and logs `handover from step 02`. The chain
  line of the reservation gains `from step 02`.
- **Verify this step.** A Verify from step 02 is a verify step `checked = 2`; `tasks.checked_route` reads the
  checked step's tier, so "one model up" and "a different eligible model" work as for the latest step. The
  Verify default text names the step it checks (D4).
- **Retry, stuck, Finish, Delete.** Unchanged. A retry of a branch step re-reads its own handover file;
  `last_good` is the source; Finish ends the task whatever its branches; Delete removes the folder.
- **Hub.levers.** Unchanged. An older step's session is never continued, verified or handed off in place; the
  branch is a fresh session (`resume=None`), which is the plan 36 contract and CLAUDE.md's fork rule.

### 4.3 What the Board shows

- **Older step picked.** The dock bar shows Add step from here (filled when `sources[n] === ""`) and Verify
  this step, then Open chat as today. The footer "Next steps start from the latest step · Go to step NN" goes;
  when the service refuses this step as a source, its reason shows once in the dock button's title and the
  footer keeps only Go to step NN. The form opens on this step's Chat tab with "From 02 Chat" as the source
  line, and the form is bound to task + source step + session + revision (plan 36 Task 3's rule), never to
  `t.current`: `openNextForm(tid, kind, n)`, `nextPreview`, `startNextStep` and `nextReseed` take the source
  from `nextOpen`, not from `t.current`.
- **The shared tree, said once.** When the source is not the latest step, one line under the source line of
  the form: "Starts from step 02's handover on the project as it is now; steps 03 and 04 ran since." The
  handover disclosure already shows the current facts captured separately. No diff, no worktree (non-goal).
- **Chain rows.** `chainStepHtml` adds `from 02` to the row's second line when `source_step` is set and is not
  `n - 1`. `receivedNote` reads `source_step` instead of `n - 1`. `task_row` passes `source_step` per step. No
  indentation, no letters, no connector drawn: lineage is a tag.
- **Received tab.** Already says "Handover from task .., step 02, session ..": nothing to add.
- **After Start.** As today: the new step's Chat tab is selected, older steps stay visible, `current` is the new
  step. The step the branch left behind (03) is now historical like any other.

### 4.4 Placement rules (Fred, 2026-10-16)

- Buttons live in the dock bar of the picked thing only: the task page and each step page. The dock already
  sits on every tab (plan 38 U3).
- No hover actions on chain rows, no per-row "..." menu, no new global keys. The chain list stays what U11
  made it: rows that pick, nothing more. Keyboard: the dock buttons are in the tab order after the pane, as
  today.
- One primary per surface: on the task page Add next step is the filled button when allowed, else Finish task
  when allowed; on a step page the same; on a replied chat Continue stays the filled button in the follow-up box.

## 5. Decisions (Fred, 2026-10-16: (a) on all six)

- **D1** Continue from the task page: (a) a Continue button that jumps to the latest step's Chat tab and
  focuses the follow-up box (one click, no second textarea); (b) the follow-up textarea on the task page itself,
  bound to the latest chat's session. Recommended (a): the guideline says never two competing textareas, and the
  task page already has an answer box for a waiting step.
- **D2** Which steps are sources: (a) `done` steps with a session and a saved note or final reply, a FAIL verify
  included (its findings are the handover); (b) also `failed` and `handed` steps when a final reply exists.
  Recommended (a); (b) can follow once a failed step's note is seen to be worth branching from.
- **D3** Branching from an older step while the latest step is a replied chat still in `running`: (a) the chat
  step is closed `done`, as `append_step` does for its own source chat today, and the chain line says so; (b)
  refuse with "Continue or finish the latest chat first". Recommended (a): it is the same move the latest-step
  append makes.
- **D4** The Verify default text on an older step: (a) the existing default with "step NN" filled in ("Check
  step 02 against its goal, its tests and its unresolved risks; do not edit"); (b) the existing text unchanged.
  Recommended (a).
- **D5** Automatic chains: (a) unchanged: a running automatic chain, a stuck or a stopped task refuse a branch and
  keep Retry / Resume / Stop; a done automatic chain converts to manual on its first branch, as today; (b) a
  stuck or stopped task may branch from its last good step as a way out, converting to manual. Recommended (a)
  for plan 39; (b) is a later plan once (a) is lived with.
- **D6** The one-line shared-tree note of 4.3: (a) shown whenever the source is not the latest step; (b) shown
  only when the current facts differ from the source's recorded facts. Recommended (a): simpler, and the line is
  true either way.

## 6. Plan 39 sketch (zero-decision: section 5 is answered, (a) throughout)

One guided plan, five tasks, one commit each, tests first where a test can see the change.

| # | Delivers | Files | Size | Tests |
|---|---|---|---|---|
| 1 | Any done step as a source: `_next_source` takes a step, GET /api/task `sources`, `append_step(source=)`, numbering, `last_good`, the chain line, D2 / D3 / D5 | console/server.py, console/tasks.py | about 50 lines | test_tasks +3 (append from an older step, numbering, closed chat), test_server +4 (sources map, refused states, request from 02 with 03 present, duplicate id) |
| 2 | The task page dock: Add next step, Verify, Continue (D1), Finish task, Hand off, Delete; Mark done leaves the foot; Hand off reads `step_levers` (the dead-button fix) | web/app.js | about 60 lines | test_web +2 (dock on the task page, Hand off shown from step_levers) |
| 3 | Per-step actions on an older step: dock buttons, the footer, the form bound to `nextOpen`'s source, "From NN", the shared-tree line (D6), the Verify default (D4) | web/app.js | about 60 lines | test_web +3 (older step's dock, form from 02, Start appends 04 with `from 02`) |
| 4 | Lineage in the list: `task_row` `source_step`, the `from 02` tag, `receivedNote` by source | console/server.py, web/app.js | about 15 lines | test_server +1, test_web +1 |
| 5 | Headless pass with the fake claude (900 / 400 / 340 px, dark and light): task page dock, branch from 02 with 03 present, Verify this step; Fred's live check on Windows; PLAN.md row and History; plan 36 README 3.1 and its "Excluded" line amended to say older steps are sources since plan 39 | tests, PLAN.md, plans/36-next-step/README.md | none | none |

Not in plan 39: hover actions, a per-row menu, keys, sibling numbering, sub-tasks, a worktree per branch,
branching a running or stuck automatic chain (D5 b), editing the handover package, Stage B of plan 36.

## 7. Acceptance

- [ ] From the task page, one click opens Add next step or Verify on the latest step; Finish task and Hand off
      work there without picking a step.
- [ ] An older done step's dock offers Add step from here and Verify this step; the form says "From 02" and the
      shared-tree line; Start appends the next number with `source_step` 02 and selects its Chat tab.
- [ ] The chain row of the branch reads `from 02`; its Received tab names step 02; step 03 stays visible and
      inspectable.
- [ ] A step the service refuses as a source shows no filled button and gives the reason in the title; the Board
      reproduces no rule of its own.
- [ ] Hand off and Start new task render on the Board where `step_levers` allow them.
- [ ] Hub.levers unchanged: no older session is continued, verified or handed off in place.
- [ ] No hover chrome, no menu, no new keys; 900 / 400 / 340 px, dark and light, reduced motion, 130 % pass.
