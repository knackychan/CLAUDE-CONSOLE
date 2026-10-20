# Task 5: autonomy levels gated / auto / suggest / off (D1 c)

Files: `console/supervisor.py` (`MODES`, `auto_reason`), `console/paths.py`, `console/tuning.py`, `console/server.py`
(`_ended` plan hold, `_replan_done` replan_auto, `_decision_default`), `web/app.js` (`supMode`, `startLine`, the mode
segment: four words; the UI chat owns the look), `tests/test_supervisor.py`, `tests/test_server.py`,
`tests/test_tuning.py`, `tests/test_web.py`.
Commit boundary: `feat: autonomy levels, gated by default (plan 52 Task 5)`.
Line numbers checked at `1d6e279` (README section 6).

## The words

`supervisor.MODES = ("off", "suggest", "gated", "auto")`; `tuning.SUPERVISOR_MODES` (tuning.py:52) the same; `paths.DEFAULTS`
`"supervisor_mode": "gated"`. `supervisor_projects` maps a project to one of the four. A saved task keeps its own
word (`policy()` as today); an unknown word fails closed to `off` with the reason, as today.

| Level | plan hold | replan proposal | decision with a default | supervisor dispatch |
|---|---|---|---|---|
| off | config `plan_hold` | config `replan_auto` | waits | none |
| suggest | config `plan_hold` | waits | waits | every decision needs Approve |
| gated | always (the task waits `plan ready: confirm` after its design step) | `confirm` auto within caps | waits | as auto, except `confirm` of `plan ready: confirm` which needs Fred |
| auto | config `plan_hold` (off by default) | `confirm` auto within caps | default after `decision_timeout_s` | as plan 44 |

## Code

- `Hub._ended` (server.py:3405): `elif (self.cfg["plan_hold"] or self._level(task) == "gated") and action == "next":`.
  `Hub._level(task) -> str` = `supervisor.policy(self.cfg, task, time.time())["mode"]`.
- `Hub._replan_done` (server.py:3695, 3701): `auto = self.cfg["replan_auto"] or self._level(task) in ("gated", "auto")`
  and the proposal still waits when the task is paused; the chain line says `replanned: applied (level auto)`.
  No supervisor pass is spent on a replan hold at gated/auto: the chain applies it itself (plan 24's apply).
- `supervisor.auto_reason(decision, task, policy)`: `if policy.get("mode") not in ("auto", "gated"): return ...`;
  then, for `gated` only: `if kind == "confirm" and task.get("why") == "plan ready: confirm": return "gated: you
  confirm the plan"`. Every cap check stays.
- `Hub._sup_auto`: `if mode not in ("auto", "gated"): return`.
- `Hub._decision_default`: `auto` only (Task 3).
- The mode words in `web/app.js` (text and defaults only; the look is the UI chat's):
  - `supMode` (app.js:1143-1144): both literal lists become `cfg.supervisor_config.modes` (the service sends
    `supervisor.MODES`), the fallback `"suggest"` becomes `"gated"`;
  - the task menu segment (app.js:3744): the literal `["off", "suggest", "auto"]` becomes the same list;
  - plan 50's Models card: `supSaved` (app.js:2411) and `supRows` (app.js:2611-2613) default to `"gated"` (the
    `ed` test, the `default ...` sub line and the reset link `data-msup="mode:gated"`); the segment already reads
    `cfg.supervisor_config.modes`, so it shows four words with no other change;
  - `startLine` (plan 48 3.3) names the level as today.
- Switch up from the card (README section 2, Fred 2026-10-20): `Hub.remember_level(task, level) -> str`, called
  under tlock before the gate passes: validates `level in MODES`, writes `supervisor_projects[norm(task["project_dir"])]
  = level` through `tuning.validate` and `paths.set_config` (the one config lock, plan 27), sets
  `task["supervisor"]["mode"] = level` with the chain line `supervisor mode: <old> -> <level> by Fred (project)`,
  and returns "" or the refusal. Callers:
  - `Hub.task_lever(task_id, "confirm", ..., remember=None)` (`POST /api/task/confirm {task, remember: "auto"}`):
    `remember` is applied first; a refusal is a 400 and nothing is confirmed. Only `plan ready: confirm` accepts
    `remember` (409 "remember applies to the plan confirm only" on a Fable or pace confirm).
  - `Hub.task_message(body)` with `remember: "auto"` in `answer` mode on a task whose `decision` has a default: the
    level is written, then the message is saved as today. The text must equal the default option's text (400
    otherwise: the switch means "take defaults").
  Tests: `tests/test_server.py::test_confirm_with_remember_auto_sets_the_project_level_once` (config.json gains the
  project at auto, the task runs on, a second task in the project starts at auto, a refused level confirms
  nothing), `test_remember_is_refused_on_a_fable_confirm`,
  `tests/test_task_messages.py::test_answer_with_remember_auto_takes_the_default_and_switches`.

## Tests (red first)

- `tests/test_supervisor.py::test_gated_dispatches_everything_but_the_plan_confirm`,
  `test_unknown_level_fails_closed_to_off`.
- `tests/test_server.py::test_gated_task_holds_the_plan_once_then_runs` (chain scout, design PLAN-OK, code, verify:
  waits at `plan ready: confirm`; the supervisor wake on that hold ends `suggest` with reason "gated: you confirm
  the plan"; POST /api/task/confirm: the rest runs with no further wake; the done wake is the only other one),
  `test_auto_task_applies_a_replan_without_confirm`, `test_level_default_is_gated_for_a_new_task`.
- `tests/test_tuning.py::test_supervisor_levels_accept_gated`.
- `tests/test_web.py::test_mode_segment_has_four_levels` (the task menu), and in plan 50's
  `SupervisorSettingsTest`: `test_models_card_has_four_levels_and_defaults_to_gated` (four `data-msup="mode:..."`
  buttons, `gated` pressed with no edit, a click on `suggest` posts `{supervisor_mode: "suggest"}`, reset returns to
  `gated`) and `test_start_mode_falls_back_to_gated` (`supMode` with no project entry and no global word).
