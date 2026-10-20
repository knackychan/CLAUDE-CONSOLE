# Task 1: supervised intake keeps the chain (change A, D4 a)

Files: `console/server.py` (`create_task` :2883, `_supervised_task` :2924, `_next_ok` :2051, `_task_new`,
`_supervisor_dispatch` :1950-1960, `request_next`), `console/supervisor.py` (`initial`, `boundary`, and plan 49's
plumbing, change 6), `web/app.js` (`decisionText` :3819), `tests/test_server.py`, `tests/test_supervisor.py`,
`tests/test_supervisor_server.py`, `tests/test_task_messages.py`, `tests/test_web.py`.
Commit boundary: `feat: a supervised task runs the planner's whole chain (plan 52 Task 1)`; full suite green.
Line numbers checked at `1d6e279` (README section 6).

## What changes

1. `Hub.create_task(card, steps, effort, title="", *, supervised=False, supervisor_mode=None)`: the signature stays
   (the Board posts it). Body: the `if supervised:` branch and `_supervised_task` are deleted. Every task is built
   by `tasks.new_task(...)` with `planned` (all the steps, verify placed by `plan_steps`), then
   `task["supervisor"] = supervisor.initial(self.cfg, folder, time.time(), mode=supervisor_mode)`. `supervised`
   is accepted and ignored (compatibility); a card with no valid step raises as today ("a task needs at least one
   step"): the no-step path is `/api/run` (plan 48 D2), never a synthetic scout.
2. `supervisor.initial(cfg, project_dir, now, mode=None)`: unchanged signature; `proposed` stays in the dict
   (always `[]`) so old task.json files and `policy()` keep loading.
3. `supervisor.boundary(task, chain)`: the `message` case at the top becomes
   `if tasks.manual_boundary(task) or task.get("state") == "done":` (any progression: a finished chain task can be
   reopened by a next-step message, Task 4). The `done` trigger stays as written (an automatic task done, D12).
4. `Hub._next_ok(task)`: `if task.get("chat"): return False`; manual boundary as today; else
   `task["state"] == "done" and policy valid and mode != "off"` with no progression check.
5. `_task_new` (the POST handler): unchanged validation; the docstring loses "keeps one manual worker".
6. Plan 49's proposal plumbing goes (D7 a): no new task has proposals, and an in-flight supervised task's saved
   `proposed` is ignored (it finishes on the plain manual path). Remove from `console/supervisor.py`: the digest's
   "Planned next" block and `PROPOSED_SHOWN` / `PROPOSED_CLIP`; `"proposal"` in `_OPTIONAL`, `_FIELDS["add_next_step"]`
   and `SCHEMA["properties"]`; the `proposal` check in `shape`; `proposal_of`; `trim_proposed`; the `proposed`
   entry in `revision`; the kind fill from a proposal in `run`; the `proposal` branch in `check` (the kind and
   instructions tests return to their plan 44 form). In `console/server.py`: the `planned` lookup in
   `_supervisor_dispatch` (instructions back to `said or decision["instructions"].strip()`, kind back to
   `decision["kind"]`, no `proposal` in `req` or the intent) and the trim block in `request_next`. In `web/app.js`:
   `decisionText` loses the proposal kind fallback and the `(planned pN)` suffix. A saved decision that still carries
   `proposal` (an old pending card) is refused by `shape` as an unknown field, and its Approve answers 409: Fred
   dismisses it.

## Tests (red first)

- `tests/test_server.py::test_supervised_intake_runs_the_planned_chain` replaces
  `test_supervised_intake_starts_one_manual_step_and_preserves_proposals`: POST /api/task with three steps and
  `supervised: true` makes a task with 4 steps (scout, design, code, verify), `progression` absent, `supervisor.mode`
  from config, `supervisor.proposed == []`; after the fake scout ends, step 02 starts with no wake
  (`hub.wakes` empty, supervisor.jsonl absent).
- `test_supervised_mode_precedence_is_explicit`: kept; it asserts the mode only.
- `test_supervised_design_does_not_rebuild_a_tail`: deleted (a supervised design now rebuilds like any chain).
- `tests/test_supervisor_server.py::test_supervised_intake_keeps_one_step_and_proposals` and
  `test_supervised_intake_no_steps_gets_one_scout`: deleted. `test_supervised_manual_lifecycle_end_to_end` is
  rewritten as `test_supervised_chain_lifecycle_end_to_end`: scout, design (PLAN-OK), code, verify PASS run with
  no Approve; the only wake is the `done` one after the final brief, status `suggest`, decision `wait` or
  `add_next_step` from the scripted fake; `supervisor.usd` counts that one pass.
- `tests/test_task_messages.py::test_boundary_message_is_next_mode`: the done case uses a chain task (no
  `progression`); the manual-boundary case uses a plan 36 task made by `tasks.append_step`.
- Plan 49's tests are deleted with its code (change 6): `tests/test_supervisor.py::ProposalTest`,
  `tests/test_supervisor_server.py::PlannedStepTest` (and its entry in the inherited-test loop at the end of that
  file), `tests/test_web.py::PlannedProposalWebTest`; the `proposed` asserts at `tests/test_server.py:3968` and
  `:3985` go with the intake tests above. New: `tests/test_supervisor.py::test_proposal_is_an_unknown_field`
  (`shape` refuses an `add_next_step` with `proposal`; the digest has no "Planned next").

## Drift guards

- `tasks.manual_boundary` and the plan 36/39 manual tasks are untouched: Add step on a model still makes a manual
  task that pauses at `choose next step`, and the supervisor's `choose_next` wake still serves it.
- No kind file changes here: plan 49's "Planned next" bullet in `supervisor.md` goes in Task 2b's rewrite.
- `plans/49-planner-handover.md` gets the status line "replaced by plan 52 Task 1 (D7)" in this commit.
