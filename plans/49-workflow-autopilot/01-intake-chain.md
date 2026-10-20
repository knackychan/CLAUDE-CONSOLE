# Task 1: supervised intake keeps the chain (change A, D4 a)

Files: `console/server.py` (`create_task`, `_supervised_task`, `_task_new`), `console/supervisor.py` (`initial`,
`boundary`), `tests/test_server.py`, `tests/test_supervisor_server.py`, `tests/test_task_messages.py`.
Commit boundary: `feat: a supervised task runs the planner's whole chain (plan 49 Task 1)`; full suite green.

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

## Drift guards

- `tasks.manual_boundary` and the plan 36/39 manual tasks are untouched: Add step on a model still makes a manual
  task that pauses at `choose next step`, and the supervisor's `choose_next` wake still serves it.
- No kind file changes here.
