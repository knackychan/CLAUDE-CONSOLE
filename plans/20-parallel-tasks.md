# Plan 20: parallel tasks per project

> Context: [17-tasks/README.md](17-tasks/README.md) (section 3.10 and 3.11 changed here), [../PLAN.md](../PLAN.md)

## Decision

Fred asked for several tasks to run at once in one project. Plan 17 refused a start when another task of
the same project was `running` or `waiting`. That refusal is removed.

## Changes

1. `console/server.py` `Hub.task_levers`: the `busy` check and its `start` reason are gone.
2. `console/server.py` `Hub.create_task`: the busy refusal is gone; a second task is created and started.
3. `tests/test_server.py`: a second task in the same project has `start` "" (was the refusal).
4. `plans/17-tasks/README.md` sections 3.10 and 3.11 say parallel tasks are allowed.

## Decided by Fred

- No cap on running tasks per project, as in VS Code.
- No worktree per task. Tasks in one folder share one working tree, as VS Code windows do.

## Done when

`py -m unittest discover -s tests` passes with the same count as before, and a second task in a running
project shows Start enabled.
