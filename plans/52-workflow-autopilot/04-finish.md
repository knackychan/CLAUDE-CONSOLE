# Task 4: finish, the summary and Accept / Reopen (change D, D5 a)

Files: `console/tasks.py` (`summary`, `fred` lever `accept`), `console/server.py` (`task_levers`, `task_lever`,
GET /api/task `summary`, `task_row`), `tests/test_tasks.py`, `tests/test_server.py`.
Commit boundary: `feat: the finish summary and Accept on a done task (plan 52 Task 4)`.

## Summary (code, no model)

```python
def summary(home, task: dict) -> dict:
    """The finish card of a done task, from saved data only: {"goal", "steps": [{"n", "kind", "model", "verdict",
    "cost"}], "files": [paths from every step's facts, deduplicated, in step order], "cost": total,
    "questions": open questions still listed by tasks.open_questions over the briefs, "accepted": ts or 0}."""
```

GET /api/task adds `"summary": tasks.summary(self.hub.folder, task) if task["state"] == "done" else None`.

## Accept

- `tasks.fred(task, "accept", now)`: allowed when `state == "done"` and `not task.get("accepted")`; sets
  `task["accepted"] = now`, chain line `accepted by <you>`; returns `(True, "", lines)`. Refused otherwise
  (`"task is running"`, `"already accepted"`).
- `Hub.task_levers`: `"accept": "" if state == "done" and not t.get("accepted") else reason`. `Hub.task_lever`
  accepts `accept` through the existing lever loop (`/api/task/accept`); `_supervisor_fred(task, now, "accept")`
  runs as for any lever: a pending D12 card (`suggest`, decision `wait` or `add_next_step`) is superseded and
  logged `by fred, action accept`.
- `task_row`: `"accepted": bool(t.get("accepted"))`; the `needs` group rule: a done task with a visible pending card
  stays in `needs` until Accept or Approve (as today, D9); an accepted task is `done` whatever the card said.

## Reopen

No new code: the message box in `next` mode (plan 48, Task 1 widened it to any done task). A next-step message on
a done chain task goes through `request_next`, which converts the task to `progression: manual` (plan 36 3.1), so
the appended step ends at `choose next step` and the supervisor's manual wake serves it. Accept stays open after a
reopen only once the task is done again (`accepted` is popped by `tasks.append_step`).

## Tests (red first)

- `tests/test_tasks.py::test_summary_lists_steps_files_cost_and_open_questions`, `test_accept_only_once_on_done`.
- `tests/test_server.py::test_get_task_summary_on_done_only`, `test_accept_supersedes_the_done_card_and_groups_done`
  (done chain task with a `suggest` card from the done wake: `task_row.group == "needs"`; POST /api/task/accept:
  group `done`, `supervisor.pending` None, outcome record `superseded ... accept`; a second POST 409).
- `tests/test_task_messages.py::test_reopen_a_done_chain_task_with_a_next_message` (one `request_next`, step
  appended, `progression == "manual"`, `accepted` gone).
