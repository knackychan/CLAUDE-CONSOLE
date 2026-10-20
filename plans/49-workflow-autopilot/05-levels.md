# Task 5: autonomy levels gated / auto / suggest / off (D1 c)

Files: `console/supervisor.py` (`MODES`, `auto_reason`), `console/paths.py`, `console/tuning.py`, `console/server.py`
(`_ended` plan hold, `_replan_done` replan_auto, `_decision_default`), `web/app.js` (`supMode`, `startLine`, the mode
segment: four words; the UI chat owns the look), `tests/test_supervisor.py`, `tests/test_server.py`,
`tests/test_tuning.py`, `tests/test_web.py`.
Commit boundary: `feat: autonomy levels, gated by default (plan 49 Task 5)`.

## The words

`supervisor.MODES = ("off", "suggest", "gated", "auto")`; `tuning.SUPERVISOR_MODES` the same; `paths.DEFAULTS`
`"supervisor_mode": "gated"`. `supervisor_projects` maps a project to one of the four. A saved task keeps its own
word (`policy()` as today); an unknown word fails closed to `off` with the reason, as today.

| Level | plan hold | replan proposal | decision with a default | supervisor dispatch |
|---|---|---|---|---|
| off | config `plan_hold` | config `replan_auto` | waits | none |
| suggest | config `plan_hold` | waits | waits | every decision needs Approve |
| gated | always (the task waits `plan ready: confirm` after its design step) | `confirm` auto within caps | waits | as auto, except `confirm` of `plan ready: confirm` which needs Fred |
| auto | config `plan_hold` (off by default) | `confirm` auto within caps | default after `decision_timeout_s` | as plan 44 |

## Code

- `Hub._ended` (server.py:3384): `elif (self.cfg["plan_hold"] or self._level(task) == "gated") and action == "next":`.
  `Hub._level(task) -> str` = `supervisor.policy(self.cfg, task, time.time())["mode"]`.
- `Hub._replan_done` (server.py:3674, 3680): `auto = self.cfg["replan_auto"] or self._level(task) in ("gated", "auto")`
  and the proposal still waits when the task is paused; the chain line says `replanned: applied (level auto)`.
  No supervisor pass is spent on a replan hold at gated/auto: the chain applies it itself (plan 24's apply).
- `supervisor.auto_reason(decision, task, policy)`: `if policy.get("mode") not in ("auto", "gated"): return ...`;
  then, for `gated` only: `if kind == "confirm" and task.get("why") == "plan ready: confirm": return "gated: you
  confirm the plan"`. Every cap check stays.
- `Hub._sup_auto`: `if mode not in ("auto", "gated"): return`.
- `Hub._decision_default`: `auto` only (Task 3).
- Models page: the mode select and the per-project map show four words (`web/app.js`, the existing `supmode`
  segment and the Models page select; text only).

## Tests (red first)

- `tests/test_supervisor.py::test_gated_dispatches_everything_but_the_plan_confirm`,
  `test_unknown_level_fails_closed_to_off`.
- `tests/test_server.py::test_gated_task_holds_the_plan_once_then_runs` (chain scout, design PLAN-OK, code, verify:
  waits at `plan ready: confirm`; the supervisor wake on that hold ends `suggest` with reason "gated: you confirm
  the plan"; POST /api/task/confirm: the rest runs with no further wake; the done wake is the only other one),
  `test_auto_task_applies_a_replan_without_confirm`, `test_level_default_is_gated_for_a_new_task`.
- `tests/test_tuning.py::test_supervisor_levels_accept_gated`.
- `tests/test_web.py::test_mode_segment_has_four_levels`.
