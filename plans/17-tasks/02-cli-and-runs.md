# Task 2: Step limits on the command, kept with the run; `task` and `step` on the run

> Contract: [README.md](README.md) 3.1, 3.4, 3.8. Depends on Task 1 (for `tasks.DISALLOW` in a test only).

**Files**
- Modify: `console/claude_cli.py` (`run_command`)
- Modify: `console/runs.py` (`RunManager.start`, the run meta)
- Modify: `console/state.py` (`Session.task`, `Session.step`, the snapshot row)
- Modify: `tests/test_claude_cli.py`, `tests/test_runs.py`, `tests/test_state.py`

## `console/claude_cli.py`

`run_command(exe, model, effort, session_id, resume=False, name="", fork="", disallow=(), tools=None, budget=0.0,
max_turns=0) -> list`

- `disallow`: a tuple of tool names; non-empty adds `["--disallowedTools", ",".join(disallow)]`.
- `tools`: `None` (nothing added) or a string for `["--tools", tools]` (the same flag Prep uses; `""` would
  disable every tool and is never passed by the plan: `tasks.RULES` uses `""` to mean "default", so `runs.start`
  maps `""` to `None`).
- `budget`: a positive number adds `["--max-budget-usd", f"{budget:.2f}"]`.
- `max_turns`: a positive integer adds `["--max-turns", str(max_turns)]`.
- The flags go after `--verbose` and before the session flags, so the existing assertions on the head of the
  command hold. Flags verified in code.claude.com/docs/en/cli-reference on 2026-10-12 (design section 2).

`tier_of(model) -> str`: the tier alias of an alias or a rung (`model_alias` on the name; `""` when none).
`known_model(cfg, model) -> bool`: `model in MODELS` or in any list of `cfg["ladder"]`. Both are pure.

## `console/runs.py`

`RunManager.start(..., disallow=(), tools="", budget=0.0, max_turns=0)`:

- New runs pass them to `run_command`. The run meta gains `"limits": {"disallow": [...], "tools": "", "budget":
  3.0, "max_turns": 0}`.
- A resumed turn (`resume=sid`) with no limits given reuses the meta's `limits`, so a STOP answer or a retry turn on
  a step keeps its restrictions; a resumed turn with limits given uses the given ones.
- `forget(sid) -> int`: deletes `runs/<sid>.jsonl` and `runs/<sid>.json` of an ended run (`RunError` when the run
  is live or unknown); returns the bytes freed. Used by the task clear (README 3.9).
- `extra` already lands on the `run_started` line: the service puts `{"task": id, "step": n}` there (Task 4);
  nothing to add here beyond the limits.

## `console/state.py`

- `Session.task: str = ""` and `Session.step: int = 0`, set from `run_started` (`rec.get("task")`,
  `int(rec.get("step") or 0)`), cleared by nothing (a step session belongs to its task for good).
- The snapshot row gets `"task": s.task, "step": s.step`.

## Tests

`tests/test_claude_cli.py`:
- `test_step_command_has_no_agent_tool`: `run_command(["claude.exe"], "haiku", "low", "abc", disallow=("Agent",),
  tools="Read,Grep,Glob", budget=3, max_turns=12)` holds `--disallowedTools Agent`, `--tools Read,Grep,Glob`,
  `--max-budget-usd 3.00`, `--max-turns 12`; without the arguments none of the four flags appears; `disallow=
  ("Agent", "Edit")` gives `Agent,Edit`.

- `test_tier_of_and_known_model`: `tier_of("claude-opus-4-6") == "opus"`, `tier_of("opus") == "opus"`,
  `tier_of("gpt") == ""`; `known_model(cfg, "claude-haiku-4-5")` true with the default ladder, `"claude-haiku-3"`
  false, `"sonnet"` true.

`tests/test_runs.py`:
- `test_forget_deletes_an_ended_run_only`: `forget(sid)` after the run ended removes both files and returns their
  size; `forget` on a live `SLOW` run raises `RunError` and leaves the files; `forget("nope")` raises.
- `test_run_started_carries_task_and_step`: `start(..., extra={"task": "t1", "step": 2}, disallow=("Agent",),
  tools="Read,Grep,Glob", budget=3)` -> the `run_started` line has `task` and `step`; `meta(sid)["limits"]` holds
  them; the fake claude ran (it ignores the flags); a `start(resume=sid)` without limits keeps
  `meta["limits"]` unchanged.

`tests/test_state.py`:
- `test_task_and_step_on_the_row`: a `run_started` with `task` and `step` -> the row has them; a plain run has
  `task == ""` and `step == 0`.

## Steps

- [x] 1. Write the three tests. Run them: fail (unknown keyword, missing key).
- [x] 2. `run_command` limits, `tier_of`, `known_model`. Run `tests.test_claude_cli`: pass.
- [x] 3. `runs.start` limits and meta reuse on resume, `forget`. Run `tests.test_runs`: pass.
- [x] 4. `state` fields and row. Run `tests.test_state`: pass.
- [x] 5. Whole suite OK. Commit: `feat: step limits on window runs, task and step on run_started (plan 17 Task 2)`.

## Drift guards

- `run_command` keeps building an argument list; no shell string, no `.cmd` shim.
- The fake claude (`tests/fake_claude.py`) is not changed in this task; it ignores unknown flags already.
- No kill path is added; `stop` is untouched.
