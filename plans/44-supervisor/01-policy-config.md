# Task 1: configuration and persisted policy

> Contract: [README.md](README.md) 4.1-4.3, 4.5. Lands on inspected baseline `654c1bd`.

**Files**
- Create: `console/supervisor.py` (policy constants/helpers only in this task)
- Modify: `console/paths.py` (`DEFAULTS`), `console/tuning.py` (`TUNING`, `KEYS`, `validate`, `view`)
- Modify: `console/server.py` (`Handler._config`, separate supervisor_config metadata only)
- Create: `tests/test_supervisor.py` (`PolicyTest`)
- Modify: `tests/test_paths.py`, `tests/test_tuning.py` (whitelist and range assertions)

## 1.1 Defaults and validation

| Key | Default | Validation |
|---|---|---|
| supervisor_mode | suggest | off, suggest, auto only |
| supervisor_projects | {} | object of normalized configured-project path -> mode; replace map on save |
| supervisor_model | haiku | Claude alias haiku only |
| supervisor_stuck_model | sonnet | Claude alias sonnet only; no opus/fable/external rung |
| supervisor_debounce_s | 20 | integer 0..300 |
| supervisor_parallel | 1 | integer 1..4 |
| supervisor_timeout_s | 90 | integer 10..600 |
| supervisor_stall_s | 1800 | integer 600..7200 |
| supervisor_max_auto_steps | 3 | integer 0..12 |
| supervisor_max_retries | 1 | integer 0..1 |
| supervisor_work_usd | 5 | finite number 0..50 |
| supervisor_task_usd | 0.50 | finite number 0..10 |
| supervisor_day_usd | 2 | finite number 0..100 |

Zero money/auto-step/retry limits disable that allowance; zero is never unlimited. Do not add the unused
supervisor_ask_s or any skills settings. Keep exact model aliases restricted so a hand edit cannot make a
supervisor pass use Opus/Fable. Other worker models remain chosen by existing routes.

Add mode/map validation branches to tuning.validate using the existing all-or-nothing save. Include those two
keys in KEYS separately from TUNING. Keep tuning.view's current bool/rung/text/numeric contract; web/app.js
tuneBad iterates every tuning key and would reject a new enum/map unit, disabling unrelated settings saves.
Expose mode/map and choices in Handler._config's separate supervisor_config object for future UI consumers;
numeric/rung supervisor settings may use existing supported TUNING units. No frontend work.
Reuse norm_dir/same_dir for Windows path matching, rejecting normalized duplicate project keys and unknown
projects. A removed configured project
still cannot run, regardless of a saved map entry. Invalid runtime hand-edited values produce off plus reason
through policy rather than unvalidated admission. No change to paths' unrelated config merge behavior.

## 1.2 Functions and data

- `supervisor.initial(cfg: dict, project_dir: str, now: float, mode=None) -> dict`: create the README 4.3
  defaults, global/project/task precedence; empty pending/proposed/retries; zero counters; no IO.
- `supervisor.policy(cfg: dict, task: dict, now: float) -> dict`: effective validated settings and task mode,
  remaining counts, saved epoch/pause; legacy tasks without supervisor work without mutating input.
- Do not add supervisor to tasks.KINDS/PREP_KINDS/RULES or TASK_KEYS/whole. It is never a worker step.
- Initial policy is attached at Hub creation sites in Tasks 7/10, when audit and human bookkeeping exist.

## Tests first

- `PolicyTest.test_default_suggest_and_task_project_global_precedence`: table of all modes, Windows spelling
  differences, saved task override surviving a project/global config change; inputs unchanged.
- `test_legacy_task_loads_without_migration`: tasks.whole/load round trip without supervisor still succeeds.
- `test_invalid_policy_fails_closed`: unknown mode, malformed map/counters, booleans as counts, negative,
  NaN/infinity and malformed hand-edited settings cannot select auto or grant extra allowance.
- `tests/test_tuning.py`: valid enum/map round trip; unknown project, invalid mode/model, external and
  opus/fable model values refused; numeric boundary/zero cases; existing keys preserved on atomic save.
- `tests/test_paths.py`: defaults present, reading missing keys does not write CLI settings or task folders.
- `tests/test_tuning.py:test_mode_map_stay_out_of_legacy_numeric_view`: whitelist accepts both keys, but
  existing tuning view contains no unsupported enum/map units; unrelated number saves remain valid.

## Steps and acceptance

- [ ] 1. Add the tests, run `py -m unittest tests.test_supervisor tests.test_tuning tests.test_paths` red.
- [ ] 2. Implement only defaults, validation, policy helpers and metadata. Run focused tests green.
- [ ] 3. Full suite green. Commit: `feat: define supervisor policy and tuning (plan 44 backend T1)`.

**Drift guard:** no wakes, model calls, task migrations or UI. Configuration alone cannot start work.
