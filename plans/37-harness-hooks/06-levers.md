# Task 6: levers on every harness

Contract: README 3.5, 3.6. Files: `console/server.py`, `console/levers.py`, `console/runs.py`,
`console/harness/codex.py`, `console/harness/opencode.py`, `console/harness/cmd.py`, `tests/test_levers.py`,
`tests/test_runs.py`, `tests/test_server.py`, `tests/test_harness.py`, `web/app.js` (only if a `claude only`
string is matched there).

## runs.py

- `start(...)`: for a non-Claude harness the child env gets `CC_CONSOLE_SID=sid` (`claude_cli.child_env() |
  adapter.env(read_only) | {"CC_CONSOLE_SID": sid}`).
- `start(fork=X, harness=H)` with no meta for `X` (an outside chat): the harness is the caller's `H`, and
  `harness_sid = X` (the row id is the CLI's own id, README 3.5). With a meta, as today.
- `result_record`: for a non-Claude harness, `verdict` / `verdict_detail` from `cc_events.verdict(summary["final"])`
  when the final text has a VERDICT line (README 3.6; the hook may be untrusted). `State`'s `run_ended` branch
  reads no verdict today: add `if rec.get("verdict") and s.verdict_ts < s.turns[-1][0]: self._verdict(s, rec, ts)`
  (only when no Stop of this turn brought one).

## levers.py

```python
def escalate_step(model: str, effort: str, harness: str = "claude", cfg: dict = None)
def handoff_prompt(home: Path = None) -> str   # the session-handoff SKILL.md body after its front matter, or ""
```

- `escalate_step` for `claude`: unchanged. Otherwise: effort +1 while below `high` (the adapter's `EFFORT` keys);
  then the first model of `harness.models_of(cfg, harness)` whose tier ranks above the current model's tier (rank =
  `claude_cli.MODELS` order), same effort; else None.
- `handoff_prompt` reads `~/.claude/skills/session-handoff/SKILL.md` (the file `handoff_ready` checks).

## server.py (Hub.levers, Hub.pull, route_of)

- `hname = (meta.get("harness") if window else s["harness"]) or "claude"`.
- `route_of`: for a non-Claude session without a meta, `model = s["model"]` as it came (no Claude alias),
  `effort = s["effort"]` when the adapter's `EFFORT` has it, else `default_effort`.
- `cold`: None for a non-Claude session (no cache-write price is known).
- Delete the `if hname != "claude"` block that sets `claude only`. Instead: `deescalate` stays window-only (existing
  rule); `escalate` uses `levers.escalate_step(model, effort, hname, self.cfg)`; `handoff` is off with `the
  session-handoff skill is not installed here: ...` when `handoff_prompt()` is ""; `terminal` is off when
  `adapter.terminal_command(...)` is None or there is no meta (an outside chat).
- `cont` for an outside non-Claude chat: `""` when `adapter.RESUME` (fork with the row id), else `this session cannot
  be resumed`.
- `pull`: `handoff` on a non-Claude session sends `levers.handoff_prompt()` instead of `/session-handoff` (the fresh
  variant appends the brief the same way); `runs.start` gets `harness=hname` so a fork of an outside chat runs on
  its own CLI.

## Adapters

`terminal_command(exe, session_id, model, effort)`:

- codex: `exe + ["resume", session_id, "-m", model]`
- opencode: `exe + ["-s", session_id, "-m", model]`
- cmd: `exe + ["-r", session_id, "-m", model, "--no-auto-update"]`

## Tests

- `test_levers.py`: `test_escalate_step_other_harness` (codex low -> codex medium -> high -> next tier model; cmd
  with only haiku-tier models at high -> None); `test_handoff_prompt_strips_front_matter`.
- `test_runs.py`: `test_non_claude_run_env_has_console_sid` (fake codex prints its env var into the stream);
  `test_fork_of_outside_chat_uses_row_id` (no meta, harness codex -> the command has `fork <row id>`);
  `test_run_ended_verdict_from_final_text`.
- `test_server.py`: `test_levers_outside_codex_chat` (row from hook records with `harness: codex` -> continue,
  verify, handoff, escalate allowed and `fork` true; terminal off; deescalate `only for window runs`);
  `test_pull_handoff_on_codex_sends_skill_text`; `test_route_of_keeps_codex_model`.
- `test_harness.py`: the three `terminal_command`s.

## Steps

1. Tests first; they fail.
2. runs, levers, adapters, then server.
3. `node --check web/app.js` if app.js changed; run all tests; commit `plan 37 task 6: levers on every harness`.

## Drift guards

- An outside chat is only forked, never resumed in place (CLAUDE.md).
- `Hub.levers` stays the one place that decides.
- Stop of a run this service owns keeps plan 05 decision 8 (kill the tree for a harness without an interrupt).
