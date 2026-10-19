# Plan 48 - The Board in three moments: Prompt, Run supervised, Supervise

Status: written 2026-10-19, decisions D1-D6 taken by Fred the same day (all as recommended). No code changed.
Design: [BRAINSTORM 7.6](../BRAINSTORM.md) (control table, decisions). Mock:
[design/rework/explored/e-prompt-run-supervise.html](../design/rework/explored/e-prompt-run-supervise.html), explored;
Fred promotes it to `design/rework/locked/` before step 5 starts. Lands on plans 36, 42, 44 (backend) and 47.

## 1. Finding

- Controls pile up per plan. On `850767e` the opened task (`inspTask`, `taskButtons`, `attentionArea`,
  `handoffForm`, `stepFooter`) carries about 35 controls; the step inspector repeats the dock
  (`stepButtons`, `nextActions`, `nextFormHtml`, `histFoot`); the session page has its own levers bar
  (`renderLevers`). The list unfolds every running task into step rows (`stepRows`, `chainStepHtml`,
  `prepRowHtml`) and the Board opens on a calendar (`renderCal`).
- The supervisor backend (plan 44) has no UI: nothing calls `POST /api/task/supervisor`, nothing reads GET
  /api/task `supervisor`, and `runAsTask` never sends `supervised: true`.
- The Prep card asks for decisions it no longer needs to (plan 47 writes the steps): Run, Run raw, Run as task,
  a model and an effort for one session, Edit, Cancel, Review rules, + step.
- The message box cannot say what comes next. At a manual boundary `Hub.message_availability` refuses with
  "This step finished. Select Add next step or confirm the next step", and on a done task "Use Add next step".
  The next step needs the separate plan 36 form (Work, Model, Instructions, preview, Start).
- `task_row` gives the list `supervisor.attention` but not what the suggestion says, so a row cannot name it.

## 2. Decisions

| # | Question | Answer (Fred, 2026-10-19) |
|---|---|---|
| D1 | Supervised by default | Every Start posts `supervised: true`; mode from `supervisor_mode` / `supervisor_projects` (suggest); the task menu changes it per task. |
| D2 | Start when off or blocked | Effective mode off: `supervised: false`, the scripted chain runs the listed steps, said under Start. Fable: two clicks. Pace or limit: the task starts held, its row needs Fred. Guidance, Pause, uncertain: only on a started task, shown on its row and cleared by one control. No steps: one session through `/api/run`. |
| D3 | Message box vs Add next step | The box replaces it on screen; the plan 36 form stays in the task menu (Add step on a model); Add step from here moves to the step's menu. |
| D4 | Raw path | Ctrl+Enter only (hint beside Enter); the card loses Run raw and Run (one session) with its pickers. |
| D5 | Non-goals | None crossed; orchestration D-1 now reads: the scripted chain stays for mode off. |
| D6 | Authority of a next-step message | The message approves the one `add_next_step` the supervisor returns for that wake; instructions are Fred's words; every live gate is rechecked; logged `by fred (message)`. Any other decision waits for Approve. |

Defaults written in (change before building if wrong):

- D7 Replied and Idle chats join Running in the list; their status line says `replied · 3m` or `idle`.
- D8 A next-step message is text only, 1 to 1000 characters (plan 36's instruction limit); files are refused with
  "The supervisor reads text only. Remove the files."
- D9 The calendar strip and the day inspector leave the Board; the Usage page keeps its calendar. Measure moves to
  the header menu.
- D10 Escalate and Verify have no entry on a task: Retry on a model and Add step on a model cover them. The
  session page of an outside chat keeps its levers (plan 03, plan 37 forks).

No new endpoint. Routes used: `GET /api/task` (route, gauge, `supervisor`, `message`, levers), `POST /api/task`
(Start, with `supervised`), `POST /api/task/supervisor` (Approve, Reject, mode), `POST /api/task/message` (the box,
new `next` mode), `POST /api/continue` (chat tasks, unchanged), `POST /api/task/done` (Finish task),
`POST /api/task/next/preview` and `/api/task/next` (the menu's Add step on a model), `POST /api/run` (a card with no
steps, Ctrl+Enter). The only server changes are inside existing routes: a `next` message mode, its wake, and one
field on `task_row`.

## 3. Changes

### 3.1 Server: the next-step message (D6, D8)

`console/tasks.py`

- `pending_messages(task)`: leave out `mode == "next"` (a next-step message is not guidance for a step, so it
  never holds a pass or a lever).
- `next_messages(task) -> list`: the queued `mode == "next"` messages, oldest first.

`console/server.py`

- `Hub.message_availability(task)`: before the two refusals (`task["state"] == "done"`, `cs["state"] == "done"`),
  when `self._sup_boundary(task)` is true or the task is done with a valid policy whose mode is not off and
  `task.get("progression") == "manual"`: return `mode: "next"`, `reason: ""`, `attachments: False`,
  `timing: "Goes to the supervisor. The step it adds from your words starts without Approve."` With the mode off
  the refusal text becomes "Supervisor off. Use Add step on a model in the task menu." (D3).
- `Hub.task_message(body)`: when `available["mode"] == "next"`: refuse files (400, D8) and text over
  `tasks.STEP_GOAL_MAX` (400); save the message with `mode: "next"`, status `queued`; in the same commit add the
  chain line `{"ts", "step": current, "from": state, "to": state, "session": "", "why": "fred: next-step message
  <first 8 of request_id>"}`; `_supervisor_fred(updated, now, "message")` as today; after the commit call
  `self.wake_supervisor(updated, "message", line)`. Never `_guidance_tick` for this mode. A repeated request id
  returns the saved message and adds no wake.
- `Hub._supervisor_fred(task, now, action)` (reached from `task_lever` for each lever): on `stop` and `done`
  mark queued next messages `cancelled` with `error: "the task was stopped"` / `"the task was finished"`. Delete
  (`clear`) returns before it and removes the folder with the message.
- `Hub._sup_admit(tid, entry)`: when the claim is saved and `"message" in entry["triggers"]`, mark the task's
  queued next messages `dispatched` (delivered to the supervisor) in the same `tasks.save`. A pass that then
  fails leaves them dispatched: never replayed (plan 42 rule); Fred sends again.
- `Hub._sup_snapshot`: `context["fred_next"]` = the texts of the messages claimed by this wake, joined by a blank
  line (empty otherwise).
- `Hub._supervisor_done`: after `status == "suggest"`, when `"message" in snapshot["triggers"]` and the decision is
  `add_next_step`, call `self._supervisor_dispatch(task_id, wake, "message")` instead of `_sup_auto`; any other
  decision follows the existing path (suggest waits, auto dispatches within caps).
- `Hub._supervisor_dispatch(task_id, wake, by)`: accept `by == "message"`. It is Fred's authorization: no epoch
  reset (the message already moved the epoch), no auto slot charged, the existing live rechecks unchanged. The
  request is built in code as today, except `instructions` = the claimed message text verbatim. The chain line
  reads `supervisor: dispatched add_next_step by fred (message)`.
- `task_row(t, ...)`: `supervisor` gains `say`: for a visible pending card, `redact.clip(f"{decision word}:
  {reason}", 120)` (for example `add_next_step: verify the 340 px case`); else `""`.

`console/supervisor.py`

- `boundary(task, chain)`: first case, before stuck: when `tasks.next_messages(task)` is not empty and the task
  is at a manual boundary or done with `progression == "manual"`, return `trigger: "message"` with the chain line
  whose `why` names that message (R1: the restart scan finds it the same way).
- `digest(home, task, context)`: after the reject note, `"Fred asks for the next step: " + clip(fred_next,
  STEP_GOAL_MAX)` when set.
- `check(...)`: unchanged; a message wake may still return wait, finish or escalate_to_fred.

`dotclaude/console/kinds/supervisor.md`: one paragraph: when the digest has "Fred asks for the next step", return
`add_next_step` with the kind, source and tier that fit his words, or `finish` / `stop` only when he asks for it;
never answer him; his words become the instructions, so do not restate them. Fred copies the file to
`~/.claude/console/kinds/` (Models page Reset to repo copy).

### 3.2 Web: the list (moment 3)

`web/index.html`: the header's Usage and Models buttons become one menu button (`data-go="hmenu"`) after the
needs count; `#calh` and `#todaymore` are removed.

`web/app.js`

- `chainGroups()`: three groups, `needs`, `work` (working, replied, idle, running Prep jobs) and `done`, plus the
  Done days and Older as today.
- `statusLine(t) -> [text, tone]` replaces `headWhy`: `needs you · <asks | supervisor.say | why>` (y),
  `failed · <step> <kind>: <why>` (r, state stuck or current step failed), `running · <NN kind> · <rung> · <age>`,
  `replied · <age>` / `idle`, `done · <n> steps · <hh:mm>` (g), `stopped`, `handed off`.
- `taskHtml(t)`: one row (mark, title, cost, status line), `data-bpick="t"`; no `stepRows`, no label chip, no
  folding. `stepRows`, `chainStepHtml`, `prepRowHtml` are used only by the opened route (3.4).
- `sessionTree(s)` becomes `sessionRow(s)`: one row that opens the session page as today.
- `prepTaskHtml(j)`: one row: `preparing · Haiku reads, then the planner` / `failed · <error>` / `ready · N steps
  · Start` (y).
- `dayGroup`: no Select / Select all; the header menu's Select done tasks sets `selecting` to today's key (the
  delete bar, `renderDelbar`, `deleteSelected` unchanged).
- Remove `renderCal`, `calLoad`, `calDays`, `pickDay`, `inspDay`, `daySpend`, `dayTone`, `calPicked` and their
  `data-day` / `data-cal` / `#overpace` click branches. `doneOn` stays for the delete bar.
- `headerMenu()`: Usage, Models and tuning, Measure (picks nothing and shows `inspMeasure`), Select done tasks,
  Show or Hide N empty chats. A page-drawn popover like the project picker, closed by Esc and an outside click.
- `renderBoard()`: when nothing is picked at 900 px the right pane shows the empty line ("Open a task to see its
  route, its context and the supervisor's last decision") instead of Measure.

### 3.3 Web: the composer and the card (moment 1)

- `renderCompose()`: the hint reads `Enter prep and plan · Ctrl+Enter raw`; `renderEffort` is no longer called
  here (the slider moves into the card's Edit steps; `effortPick` and window.json stay).
- `showPrep()`: two layers in `#pscroll`. Summary: `plannerLine(card.planner)`, the steps as read-only rows
  (`stepSummary(card)`: number, goal, kind; the verify row as today's fixed text), one line
  `startLine(card)` and the bar. Edit steps (a fold, closed by default, key `prep.edit`): today's enhanced prompt
  textarea, `#p-steps` with its pickers and + step, floors, the Fable note and the effort slider. The editors are
  always in the DOM so `stepList()` reads them whether the fold is open or not.
- `#pbar`: one `Start` (`data-pact="start"`) and a card menu button with Edit prompt (`edit`), Drop (`cancel`),
  Review rules (`review`). Remove `#p-model`, `#p-effort`, `run`, `raw`, `task`.
- `supMode(projectDir) -> "off" | "suggest" | "auto"`: `cfg.supervisor_config.projects` matched with `sameDir`,
  else `cfg.supervisor_config.mode`, else `"suggest"` (mirrors `supervisor._project_mode`).
- `startLine(card)`: `supervised · <mode> · runs in <project>`; with mode off `Supervisor off: the steps run as
  listed`; with no steps `One chat: no steps were planned`.
- `prepAct("start")` -> `startCard(c, button)`: Fable on any row or the route: arm twice (today's `run` code).
  No steps: `doRun(c.project_dir, prompt, "auto", rawEffort(), c.id, "", fable)`. Else `POST /api/task {prep,
  prompt, steps: stepList(), effort: effortPick, supervised: supMode(c.project_dir) !== "off"}` and
  `openTask(r.task)`. `runAsTask` is folded into it.

### 3.4 Web: the opened task (moments 2 and 3)

- `inspTask(t, d, row)` keeps `dock()` and becomes: head (status, title, meta: project, cost, `supervised ·
  <mode>` from `d.supervisor.mode`, label chip) then body: `attentionArea` (trimmed below), `supCard(t, d)`,
  `routeHtml(t, d, row)`, `gaugeHtml(t, row)`, Goal and questions as closed folds, `handoffForm(t)` and the retry
  and next-step forms when the menu opened them. No Overview / Steps / Files tabs (`taskView` goes).
- `supCard(t, d)`: `d.supervisor.pending` -> the wake, time, model and cost, the decision as one sentence
  (`decisionText(decision)`: `Add 03 verify on sonnet from 02's handover`, `Retry 02 on opus`, `Finish the
  task`), its reason, Approve (`data-tact="supapprove"`, only when `can_approve`) and Reject
  (`data-tact="supreject"`, a second click opens a note field, sent as `note`). Status `uncertain`: Dismiss (the
  same reject call). Status `escalate` or `refused`: the reason and Dismiss. No pending: the last `d.supervisor.audit`
  entry with a decision, quiet (`askbox quiet`). Mode off or no policy: nothing.
- `taskAct`: `supapprove` / `supreject` post `POST /api/task/supervisor {task, wake, action[, note]}` and redraw;
  `supmode` posts `{task, mode}`.
- `routeHtml(t, d, row)`: `chainStepHtml` rows for `t.steps` (each opens `inspStep` as today), then one dim row
  per `t.supervisor.proposed` item numbered after the last step (`proposed`, no rung, no cost, not clickable).
- `gaugeHtml(t, row)`: the current step's `stepCtx` as 30 cells (`ctxClasses`) with the figure and the 150K / 300K
  scale; `?` with `ctxUnknown` for a harness without a context reading.
- `taskButtons(t, d)` -> the bar: Stop (`lv.stop`, two clicks as today) or Resume (`lv.resume`, `Start task` on a
  planned follow-up), Pause (`lv.pause`), then `taskMenu(t, d)`. Each only where the service allows it.
- `taskMenu(t, d)`: Hand off task (`d.handoff_available`), Finish task (`lv.done`, with today's inline confirm),
  Add step on a model (`lv.add_next`, opens `nextFormHtml` from `d.next_step`), Retry on a model (`lv.retry`,
  shows `retryForm` in the body), Accept step result (`lv.stepdone`), Redo design (`lv.redo`), Open in terminal
  (`sl.terminal`), Review rules (rules warning), the mode segment (off / suggest / auto, `supmode`), Open task
  folder, Delete task (`lv.clear`, two clicks), then Models and tuning and Usage. A `details` popover like
  today's More.
- `attentionArea`: keeps the gate's one button (Confirm plan, Accept, Run anyway, Confirm Fable, the replan box,
  the handed box's Start next task); the stuck box shows the reason only (Retry on a model is in the menu, or the
  supervisor's Retry card); the Plan gap box keeps its question and points to the message box (answer mode).
- `stepFooter(t, s, d)`: label and placeholder by `d.message.mode`: `next` -> "Tell the supervisor what to do next"
  / "For example: verify only the 340 px case, then finish"; Attach disabled with the D8 reason. Remove the
  `messagenext` button ("Use message in Add step").
- `stepButtons(t, s, d)`: the current step gets the same bar; an older step gets a menu with Add step from here
  (`nextActions`). `histFoot` goes.

### 3.5 Docs

`CLAUDE.md`, the Board line: the Board also writes `POST /api/task` (Start from the card, with `supervised`),
`POST /api/task/supervisor` (Approve, Reject, the per-task mode) and the `next` mode of `POST /api/task/message`.
`design/rework/README.md`: the mock row (explored, then locked). `PLAN.md` row 48 and History.

## 4. Tests (first)

Server (`py -m unittest tests.test_task_messages tests.test_supervisor tests.test_supervisor_server tests.test_server`):

- `tests/test_task_messages.py::test_boundary_message_is_next_mode`: a supervised manual task at `choose next step`
  and a done supervised task: `message.mode == "next"`, `attachments is False`, reason empty; mode off: the
  "Supervisor off" reason.
- `test_next_message_saves_wakes_once_and_holds_nothing`: accept writes `mode: next`, one chain line, one
  `Hub.wakes` entry with trigger `message`; the same request id again adds no event; `tasks.pending_messages` is
  empty, so `_sup_admit` admits the wake.
- `test_next_message_refuses_files_and_long_text`: files 400, 1001 characters 400.
- `test_stop_and_finish_cancel_a_queued_next_message`; Finish is not refused for it (it is not guidance).
- `tests/test_supervisor.py::test_boundary_finds_a_queued_next_message`: manual boundary and done manual task ->
  trigger `message` with its own chain line; none without the message.
- `test_digest_carries_fred_next`.
- `tests/test_supervisor_server.py::test_message_wake_adds_the_step_without_approve`: suggest mode, the fake pass
  returns `add_next_step` (kind verify): one `request_next`, its instructions equal the message text, chain
  `by fred (message)`, `auto_steps` unchanged, epoch unchanged by the dispatch, message status `dispatched`.
- `test_message_wake_other_decision_waits`: the pass returns `finish`: pending `suggest`, nothing dispatched.
- `test_message_supersedes_a_pending_suggestion`: a pending suggest card, then a message: the old card is
  superseded, Approve of its wake returns 409.
- `test_message_wake_recovered_once_after_restart` (R1): message saved, Hub restarted before the claim: one wake,
  one pass, one step.
- `test_message_wake_respects_live_gates`: a Fable or pace hold on the added step keeps the plan 44 held path; a
  guidance message queued for a running step still blocks the pass.
- `tests/test_server.py::test_task_row_names_the_suggestion`: `supervisor.say` for suggest, escalate, uncertain;
  empty with no pending card.

Web (`py -m unittest tests.test_web`, Node):

- `test_list_row_is_one_status_line`: a running, a needs-you (asks, supervisor say), a failed and a done row give
  one `.tr`-style row each with the status text and tone; no step rows.
- `test_card_has_one_start_and_edit_steps_folded`: `showPrep` markup holds one `data-pact="start"`, no `run` /
  `raw` / `task`, the planner line, the steps summary, and the editors inside the closed fold.
- `test_start_payload_follows_the_supervisor_mode`: suggest / auto -> `supervised: true`; project off -> `false`;
  no steps -> the `/api/run` path.
- `test_sup_card_shows_approve_only_where_allowed`: `can_approve` false hides Approve; uncertain shows Dismiss;
  no pending shows the last audit decision quietly.
- `test_route_lists_proposed_steps_dim`.
- `test_task_bar_is_stop_or_resume_pause_and_menu`: no Add step, Mark done, Retry, Verify, Escalate, Continue
  buttons outside the menu; the menu holds each only where its lever is `""`.
- `test_composer_next_mode_label_and_no_attach`.
- Update to the menu: `test_add_step_only_where_the_service_allows_it`,
  `test_step_dock_reads_the_task_action_area_where_the_service_allows_it`,
  `test_task_actions_show_only_where_the_service_allows_it`, `test_stuck_box_retry_form_lists_models_and_hides_a_limited_rung`,
  `test_older_done_step_offers_a_branch_where_the_service_allows_it`,
  `test_replied_chat_footer_offers_send_and_the_task_action_area`, `test_hand_off_task_reads_the_task_availability`.
  Delete the calendar and day-inspector tests if any assert `renderCal` / `inspDay`.

## 5. Order and checks

One commit per step, tests first, stage only this plan's lines (other chats edit PLAN.md, CLAUDE.md,
BRAINSTORM.md and `web/app.js`).

1. Tests red (server).
2. `tasks.py`, `supervisor.py`, `server.py` next mode and its wake (3.1), `supervisor.md`. Server tests green;
   `py -m unittest discover -s tests`.
3. `task_row` `say`. Full suite.
4. Web tests red; the list and the header menu (3.2). `node --check web/app.js`.
5. The composer and the card (3.3). Needs the mock in `locked/`.
6. The opened task (3.4); update the named web tests; `tests/live_task_chat_check.py` follows the menu for Add
   step and Retry. `node --check web/app.js`, full suite.
7. Docs (3.5).

Headless check (fake claude, scratch home, as plans 39 and 42): type, Enter, the row says preparing then ready,
Start, the supervised task runs step 01, the fake supervisor suggests, Approve, step 02 runs; type a next-step
message at the boundary, a step starts with those words; at 900 / 400 / 340 px, dark and light, reduced motion,
130 % text; no horizontal scroll, no console error.

Live check (Fred): one real prompt from Enter to done in suggest mode with one Approve and one next-step message;
one project set to off runs its listed steps as a chain; the list reads at a glance with three tasks open.

## 6. Not done here

- The session page of an outside chat (VS Code, terminal, other CLIs) keeps its levers and forks (D10).
- The pill and the peek card are unchanged; a peek on a task still opens the task.
- No skill library (plan 44 brainstorm section 14), no Usage or Models page change beyond moving their buttons.
- No automatic Prep-card Start: Start stays Fred's (BRAINSTORM D4, "always review", now one click).
- Plan 36 Stage B (agent requests) and true mid-turn delivery (plan 42) stay open.
- The supervisor's pass, caps and modes are plan 44's; this plan adds only the message trigger and its authority.
