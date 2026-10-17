# Task 2: Overview, Steps, Files and the one action area

> Contract: [README.md](README.md) 3.4. NAVIGATION.md "Task Overview", "Action hierarchy",
> "Remove information clutter". No server change (all gates exist in `Hub.task_levers` /
> `Hub.levers` / `GET /api/task`).

**Files**
- Modify: `web/app.js` (`inspTask` rebuild, `taskButtons`, `stepButtons`, `nextActions`, `stepFooter`,
  `renderLevers`, `noteLine`, remove `taskSessionButtons` / `nextSecondary`)
- Modify: `web/style.css` (`.tabs [aria-current]`, `.btn.complete`, `.task-actions`, `.action-more`,
  `.done-confirm`, the task-view sections)
- Modify: `tests/test_web.py`

## 2.1 The three task views

- `inspTask(t, d, row)` rebuilds around a view switch `taskView` in `{overview, steps, files}`:
  - A view bar (`<nav class="tabs">` with `data-tact="taskview" data-view=...`, `aria-current` on the active)
    under the breadcrumb and head. The head is title, state word, one meta line (`project · $cost`).
  - **Overview**: source/target handoff links (when `handoff_from` / `handoff_to`), the Goal section
    (`t.goal`, first lines always visible, long text scrolls), the attention area (2.3), the current-step
    progress link (`data-bpick="s<n>"`), the latest result fold, then the shared composer (2.4).
  - **Steps**: one button per step (`data-bpick="s<n>"`), `Step NN · kind`, the goal, the state; the Activity
    fold (chain lines) under it.
  - **Files**: Original prompt (`prompt.md`), the plan fold (`planPane`), Task handoff (`handoff_document`,
    Task 3), Inherited handoff (`handoff_context`, Task 3), then one fold per step's files (`filesPane`).
  - `taskAct` gains `taskview` (sets `taskView` and re-renders) and the Mark-done confirm arms (2.6).
- The old `inspTask` body (prompt.md fold, open/closed questions, chain log, the wall of buttons in the head)
  is replaced. Questions move into the attention area; the chain log moves to Steps > Activity; prompt.md moves
  to Files > Original prompt.

## 2.2 The action area (`taskButtons`)

- Two prominent actions plus a `<details class="action-more">` More (a `<summary class="btn sm">More</summary>`
  over an `.action-list`). Buttons render only when their lever reads `""`; a disabled/absent action is hidden,
  not greyed. Groups are stable and left-aligned (`justify-content: flex-start`).
- Prominent, state-specific:
  - running current step: `Stop` (`levers.stop === ""`).
  - paused / a fresh follow-up (`handoff_from` and not started): `Resume` (label `Start task` on a follow-up).
  - failed current step: `Retry` (opens the existing `retryForm` beside the reason).
  - `Add step` (`levers.add_next === ""` and no form open) — one button, `data-tact="nextopen"` with the source
    step; no separate Verify button.
  - `Mark done` (`.btn.complete`, green, `levers.done === ""` and state not done) with the inline confirm (2.6).
- More: `Pause task` (`pause`), `Accept step result` (`stepdone`), `Hand off task` (`d.handoff_available === ""`,
  Task 3), `Open in terminal` (`step_levers.terminal === ""`, not live), `Use a stronger model`
  (`step_levers.escalate === ""`), `Review rules` (session `rules_warn`), `Open task folder`, `Delete task`
  (`clear`, `.stop`).
- Remove `nextSecondary` and `taskSessionButtons` entirely; fold their remaining actions into `taskButtons` or
  the attention area. `stepButtons(t, s, d, row)`: when `s.n === t.current` return `taskButtons(t, d)`, else
  the single "Add step from here" branch action.

## 2.3 The attention area (one place for questions, confirms, failures)

- Replace the scattered `wait`/`now`/`askbox` blocks with one `section.task-attention` at the top of Overview:
  - worker question (`row.asks`, not a plan gap): the question and the answer composer (the shared composer is
    already the answer path).
  - plan gap / replanned: the gap text and `Open step NN`.
  - confirm wait (`levers.confirm === ""`): the reason and the one `confirmLabel` button.
  - stuck / stopped / failed: the reason and `retryForm` beside it.
  - `redo` (`levers.redo === ""`) renders with its reason, not as a floating button.
- A supervisor suggestion, when the backend lands, renders in this same area; until then nothing extra renders
  (drift guard).

## 2.4 The shared composer

- `stepFooter` loses the `taskSessionButtons` extra line; it keeps Send, Attach, retarget, "Use message in Add
  step" and the delivery line. `taskMessageState` wording changes `Add next step` -> `Add step`.
- `nextActions(t, s, d)` collapses to one "Add step" / "Add step from here" button (the interrupted attempt's
  shape): return `""` unless `s.session` and the source gate (`levers.add_next` for the latest, `sources[n]`
  for an older step) reads `""`.

## 2.5 Remove clutter

- `renderLevers` (session page): delete the `Brief a new task` and `Verify in a new task` buttons and the
  "A new task with a brief costs almost nothing." sentence from the cold-cache line; relabel `Levers off:` ->
  `Unavailable:` and `Hand off is off:` -> `Handoff unavailable:`.
- `noteLine(s)`: delete the `delegate_hint` line (`delegate? N reads in the main chat this turn`).
- Rename user-visible `Add next step` -> `Add step`, `Mark step done` -> `Accept step result` (including the arm
  text), `Finish task` -> `Mark done` (green), `prompt.md` -> `Original prompt`, `Chain log` -> `Activity`.

## 2.6 Mark done confirm

- `doneConfirm` (Task 1) holds the task id while confirming. `taskAct("done")` sets `doneConfirm = id` and
  re-renders; `confirmdone` clears it and dispatches `done`; `canceldone` clears it. The inline confirm box is
  `done-confirm` with "Mark this task done? History stays available." and green `Confirm done` + `Cancel`.

## Steps

- [ ] 1. `taskView` switch + the three views in `inspTask`. `node --check` clean; page loads.
- [ ] 2. `taskButtons` (two prominent + More), `stepButtons`/`nextActions` collapse, remove `nextSecondary` /
      `taskSessionButtons`. Check the action area at 400 px (the More list opens above, no overflow).
- [ ] 3. Attention area + shared composer + clutter removal + relabels. Check a question, a plan gap, a confirm
      and a stuck reason each render once.
- [ ] 4. Green Mark done + inline confirm. Check width stability.
- [ ] 5. Tests below; whole Python suite green. Commit: `feat: task Overview, one action area, clutter removal (plan 44 nav T2)`.

## Tests (tests/test_web.py; rewrite the affected UnifiedTaskChatTest / NextStepUITest cases)

- `test_task_page_has_overview_steps_files_views`: `taskView` switch renders Goal on overview, one step link per
  step on steps, and prompt.md / plan / handoff folds on files.
- `test_mark_done_is_green_and_confirm_is_inline`: `taskButtons` with `levers.done === ""` contains
  `btn.complete` and `Mark done`; arming `done` renders the `done-confirm` box; `confirmdone` dispatches.
- `test_accept_step_result_is_recovery_only`: `levers.stepdone === ""` yields `Accept step result`, never in the
  prominent group, and its arm text says "incomplete".
- `test_verify_is_inside_add_step_not_standalone`: `taskButtons` has exactly one `nextopen` Add step and no
  `nextverify`/Verify button.
- `test_question_and_confirm_share_one_attention_area`: a question and a confirm each render in
  `task-attention` exactly once, not in a heading plus the composer.
- `test_brief_a_new_task_and_delegate_hint_are_gone`: `renderLevers` output lacks `Brief a new task` and
  `Verify in a new task`; `noteLine` lacks `delegate?`.

## Drift guards

- No standalone Verify button anywhere on a task; Verify is a `NEXT_WORK` kind inside the Add step form.
- Mark done (green) is whole-task only; Accept step result is step-level recovery only; never the same button.
- The attention area renders a supervisor suggestion only when the plan 44 backend provides one; no placeholder
  toolbar or empty select ships now.
- Keep server gates untouched; every button posts to an existing `/api/task/*` route.
