# Task 4: reconcile tests, the browser check, and the plan indexes

> Contract: [README.md](README.md) 1, 5. NAVIGATION.md "Acceptance checks", "Implementation scope and order" item 5.

**Files**
- Modify: `tests/test_web.py`, `tests/test_tasks.py`, `tests/test_server.py` (or their task classes),
  `tests/live_task_chat_check.py` if it asserts the old landing or button set
- Modify: `PLAN.md`, `plans/44-supervisor/NAVIGATION.md` (state + pointer), `plans/44-supervisor/BRAINSTORM.md`
  section 10 (point to the shipped navigation, not the superseded presentation)

## 4.1 Reconcile the web tests

- The interrupted attempt left 12 failures; the rewrite of Tasks 1-3 replaces the affected cases. Update every
  assertion that named the old labels (`Add next step`, `Mark step done`, `Finish task`, `Brief a new task`,
  `Verify in a new task`, `Continue`, `Chain log`, `prompt.md`) and the old landing (task opens the current
  step) to the new contract (Overview, Add step, Accept step result, green Mark done, Activity, Original
  prompt).
- `UnifiedTaskChatTest.test_task_and_owned_session_entry_points_open_current_chat_and_old_attempt`: the task
  entry now opens Overview; the step/attempt links still open the step. Split it into an Overview case and a
  step-link case.
- Keep `test_archived_task_session_links_open_the_task_inspector` (task link -> Overview) and the composer
  parity / delivery-gate cases; adjust their expected HTML only where the action area moved.

## 4.2 The browser fixture check

- `py -m unittest discover -s tests` green; `node --check web\app.js` clean.
- Headless Edge against the fake claude at 900, 400 and 340 px, both themes, keyboard-only: Overview, Steps,
  Files, the action area (More opens and stays usable), the handoff form (preview, Save, Create follow-up,
  then opening the follow-up), and a cold task handed off without a re-read. Read the screenshots; grep the log
  for `Uncaught` (the plan 17 Task 5 command is the template).

## 4.3 Live check (Fred, not Claude)

- On one real manual task: a question, a plan gap and a plan confirm each handled from Overview; a step link
  opens that step; back returns to the list with filters/scroll kept.
- Hand off a stopped task: preview names the source and every step, Save writes the document, Create yields one
  follow-up whose Overview shows the inherited handoff; starting it reads the summary inline.
- No Brief a new task, duplicate Continue/Verify/Mark done, or Delegate hint anywhere.

## 4.4 Indexes and state

- `PLAN.md`: the "Supervisor and navigation design" section points to this guided plan
  (`plans/44-supervisor/navigation/`), marks the navigation slice state, and keeps the supervisor backend
  "implementation plan pending".
- `NAVIGATION.md`: status -> implemented with a pointer to this folder; the "Implementation scope and order"
  items 1-3 and 5 marked done, item 4 (supervisor UI) still pending its backend.
- `BRAINSTORM.md` section 10: keep the "navigation follow-up" note, note the shipped navigation replaces the
  presentation below.

## Steps

- [ ] 1. Reconcile and run `py -m unittest discover -s tests`; fix until green.
- [ ] 2. `node --check web\app.js`; headless Edge pass at 900/400/340 px.
- [ ] 3. Update PLAN.md, NAVIGATION.md, BRAINSTORM.md. Commit: `docs: reconcile plans and close the navigation slice (plan 44 nav T4)`.
- [ ] 4. Hand to Fred for the live check (4.3).

## Drift guards

- No test is deleted to make the suite pass; every changed assertion names the new contract.
- The supervisor backend remains unshipped; do not mark plan 44 itself done here.
- The independent backtick-fence fix in `console/tasks.py` and its test stay; do not revert them.
