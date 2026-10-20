# Task 6: the actions contract for the UI (README section 3 as data)

Files: `console/server.py` (`Hub.actions`, GET /api/task), `tests/test_server.py`, `CLAUDE.md` (one line under the
Board write contract), `plans/52-workflow-autopilot/README.md` (section 3 marked "served by `actions`").
Commit boundary: `feat: GET /api/task actions, the one aligned action set per state (plan 52 Task 6)`.

The UI must not reproduce business rules (plan 36 3.4). Today it reads `levers`, `message`, `supervisor.pending`,
`recovery`, `handoff_available` and `next_step` and decides the bar itself. This task adds one read-only field so
the UI chat places buttons without that logic.

```python
def actions(self, task: dict) -> dict:
    """{"state": word, "line": str, "primary": [action], "bar": [action], "menu": [action]} where an action is
    {"id", "label", "post": "/api/task/<lever>" | "/api/task/supervisor" | "/api/task/message" | "", "body": {...},
     "off": "" | reason, "confirm": bool}. Built from task_levers, message_availability, supervisor_view, recovery
    and next_availability only; a read, nothing starts."""
```

`state` is one of `preparing, ready, running, plan_ready, decision, suggestion, hold, failed_twice, stuck, paused,
stopped, done, handed, observed` by the rules of README section 3 (the table there is the spec; the row text is
`line`). Options of a decision card are the `primary` list (`post: /api/task/message`, `body: {mode: "answer",
text: <option text>}`); Accept is `/api/task/accept`; Approve / Reject carry `wake`. State `plan_ready` lists two primaries: `confirm` (`/api/task/confirm {task}`) and `confirm_auto`
(`{task, remember: "auto"}`, label "Confirm, and run plans automatically from now on"); a decision card with a
default adds `default_auto` after the options (`/api/task/message {mode: answer, text: <default text>, remember:
"auto"}`, label "Take the default from now on"). Neither appears when the project is already at `auto`. An action
whose lever is off is listed with its `off` reason so the UI can grey it with a title, as the levers do today. `confirm: true` marks
the two-click ones (Stop, Delete, Confirm Fable, Finish).

Two states built since this task was written (README section 6) are part of the same field, so the UI reads
`actions` only:

- After Reject (plan 51 D5, `Hub.supervisor_view` `rejected` at server.py:2217): no primary; `line` is "You rejected
  wake N" and the hint names the next move: with `message.mode == "next"` the message box ("Write what to do
  instead", plus "your note goes with it" when `rejected.note`), else the bar's `add_step` and `finish` actions.
- Recovery (plan 48 section 7, GET /api/task `recovery`): when `recovery` is not null, `actions` adds `recovery:
  {done, cut, orphan}` unchanged, and the actions the recovery box names (`retry`, `stepdone`, `resume`, `stop`
  for an orphan) are the ones listed, with their `off` reasons; no action is added that the levers do not open.

An observed chat (`source != window`, plan 37) returns `state: "observed"`, `primary: []`, `bar: []`, and `menu`:
Continue as a fork, Verify as a fork, Hand off, Escalate as a fork, Open in terminal, each from `Hub.levers` of
its session with `post: /api/<lever>` and `body: {session, fork: true}`.

Tests: `tests/test_server.py::test_actions_after_reject_and_in_recovery` (a rejected card: no primary, the
hint by message mode; a cut attempt: `recovery` copied and only the open levers listed), `tests/test_server.py::test_actions_per_state` (one fake task per state, the primary and bar ids as the
table says, every listed `post` is a route `do_POST` serves), `test_actions_never_start_anything` (two GETs, no
run, no wake, task.json unchanged), `test_observed_chat_actions_are_forks_only`.
