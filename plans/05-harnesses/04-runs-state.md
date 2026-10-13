# Task 4: runs on any adapter, the run lines, the session row

> Contract: [README.md](README.md) 3.5, 3.6. Depends on Tasks 1 and 2 (the Codex fake is the second harness the
> tests drive). Task 3's adapters plug in with no change here.

**Files**
- Modify: `console/runs.py` (`RunManager.start`, `_spawn`, `_watch`, `_finish`, `stop`, `chat`, `result_record`, `reconcile`)
- Modify: `console/state.py` (`Session.harness`, the row, the gauge from `run_ended.tokens`, a session from `run_started` alone)
- Modify: `console/tasks.py` (`cap_reason`: `error_step_timeout`)
- Modify: `tests/test_runs.py`, `tests/test_state.py`, `tests/test_tasks.py`

## `console/runs.py`

- `RunManager.__init__(self, cfg, folder, exe=None, exes=None)`: `exe` stays the Claude command prefix (every
  existing caller and test); `exes` is `{harness name: command prefix list}` for the others, default `{}`. The
  service fills it from the probe (Task 5). `self.exe_for(name) -> list | None`: `self.exe` for `claude`, else
  `self.exes.get(name)`.
- `start(..., harness: str = "claude", read_only: bool = False)`:
  - On `resume` the harness is `old.get("harness") or "claude"` and the argument is ignored (README decision 13:
    `Hub.pull` and the STOP answers pass none); on `fork` it is the forked run's meta harness. Only a new run takes
    the argument.
  - `adapter = harness_pkg.get(harness)`; `exe = self.exe_for(harness)`; none -> `RunError(f"{harness}: not found")`.
  - The prompt and the footer move into the adapter: `cmd, stdin = adapter.run_command(exe, model, effort, cwd, sid_or_resume_id, prompt=prompt, resume=..., fork=..., read_only=read_only, budget=..., max_turns=..., name=redact.clip(title, 60), **claude_only)` where `claude_only = {"tools": ..., "disallow": ..., "blocks": attach.blocks(files)}` for `claude` and `{"variants": cfg["effort_variant"].get(model), "prompt_file": str(self.runs / f"{sid}.prompt.md")}` for
    `opencode` (the file written, prompt plus STOP footer, before `run_command`), else `{}`. A `ValueError` from
    `run_command` (Command Code's shim refusal) becomes `RunError` with its message.
  - For a non-Claude resume the id passed is `old["harness_session"]` (RunError `"this session cannot be resumed: no harness session id"` when empty); for `fork` likewise the meta of the forked run.
  - For `cmd` (the one adapter with the prompt in argv) and `len(prompt) > 30000`: `RunError(f"prompt too long for {harness} ({len(prompt)} chars)")`.
  - `_spawn(cmd, cwd, path, stdin, env)`: as today with `env = claude_cli.child_env() | adapter.env(read_only)`;
    writes `stdin` bytes when not None; for an adapter with `INTERRUPT` false, closes stdin right after, or at once
    when `stdin` is None (Codex reads the prompt to EOF; a CLI that reads piped stdin would otherwise wait
    forever; Claude keeps stdin open for the interrupt, unchanged). Files (`attach`) ride only with Claude; for others `attach.summary(files)` still goes in the `cc_prompt` line and the file names are appended to the prompt as `Attached files: a.png, b.pdf` (the model cannot read them: the note says so).
  - The meta gains `harness`, `harness_session: ""`, `read_only`, `timed_out: false`. `run_started` gains `harness`.
- `_watch`: `is_result = adapter.is_result`; the end condition as today (`result is not None or proc.poll() ...`);
  after `proc.poll()` is not None the service appends one line `{"type": "cc_exit", "code": proc.returncode, "ts": ...}`
  to the stream (what the defensive adapters read). Timeout: when `not adapter.CAPS and cfg["step_timeout_s"] > 0`
  and `time.time() - started > step_timeout_s` and the process is alive: `adapter.stop(proc)`, `self.stopping` is NOT
  set (this is a cap, not Fred's Stop), `timed_out = True`, and the meta's `timed_out` is saved true (Task 5's
  `final_message` reads it). For Claude (`CAPS` true) nothing changes.
- `_finish(sid, result_lines, exit_code, timed_out=False)`: `summary = adapter.summary(the stream lines from the meta's offset)` (this turn only; a resumed session's file holds every turn);
  the meta gets `harness_session = summary["session_id"]` when the meta's is empty and it differs from `sid`; `result_record` takes the summary.
- `result_record(session_id, summary, exit_code, stopped, timed_out)`: `subtype` = `"error_step_timeout"` when `timed_out`, else `summary["subtype"]`; `cost` only when `summary["cost"] is not None`; `tokens` only when not None; `denials` as today; `interrupted` = no summary final and not stopped and not timed out.
- `stop(sid)`: a live process: `adapter.stop(proc)` (`"interrupt"` or `"kill"`; `stopping` set either way); the rest as today.
- `chat(path, cwd, limit, harness="claude")`: `harness_pkg.get(harness).chat(lines, cwd)` after the `cc_prompt` / `raw` handling that stays here; `RunManager.chat_of(sid)` reads the meta's harness and calls it (Task 5 uses it).
- `reconcile`: unchanged in logic; a result is `adapter.is_result` of the meta's harness.
- `prune` also globs `runs/*.prompt.md`; `forget` deletes `<sid>.prompt.md` with the stream and the meta.
- `open_terminal`: `open_terminal` raises `RunError("claude only")` when the meta's harness has `terminal_command` returning None.

## `console/state.py`

- `Session` gains `harness = "claude"`; `run_started` sets it (`rec.get("harness") or "claude"`), the hooks never
  carry it. The snapshot row gains `"harness"`.
- `run_ended` with `tokens` whose `context` is a number: `s.ctx_tokens = tokens["context"]` (the field `State`
  has; the gauge reads it). No adapter reports one yet (Codex's usage is spend: README 3.4), so a non-Claude row
  keeps `ctx_tokens None` and the page shows `context unknown` (Task 6). `tokens` is kept on the line for plan 18.
- `Session.cost` is a float today (`s.cost += float(rec.get("cost") or 0)`, the row `round(s.cost, 4)`), so it
  cannot be `None` without a change: `Session.cost_unknown = False`; a `run_ended` with no `cost` key sets it; the
  row's `cost` and `spent` are `None` when `cost_unknown` and `s.cost == 0`. The Usage mix counts only sessions
  with a transcript, so a non-Claude run adds nothing there in this plan.
- `run_ended` with a subtype other than `success` on a session whose `harness != "claude"`: `s.failed =
  {"error": subtype, "details": ""}` (unless stopped or interrupted), so `state_of` gives Failed. Today only the
  StopFailure hook sets `failed`; a Claude row is unchanged.
- A session whose only lines are `run_started` / `run_ended` (no hooks): title from `run_started.title`, model
  and effort from it, `window True`, state `Running` while live, then `Idle` (`run_ended` success), `Failed`
  (an error subtype), `Interrupted`; the existing code paths for window runs decide this: the test pins it.

## `console/tasks.py`

- `cap_reason("error_step_timeout", limits)` -> `f"it hit the step timeout ({limits.get('timeout_s') or '?'} s)"`;
  `runs.start` puts `timeout_s` into the meta's `limits` for adapters with `CAPS` false.

## Tests

`tests/test_runs.py` (new, `HarnessRunsTest`, built on the module's existing fixtures with a scratch home):
- `test_start_codex_writes_prompt_on_stdin_and_closes_it`: `RunManager(cfg, home, exe=[fake_claude], exes={"codex": [sys.executable, "tests/fake_codex.py"]})`; `start(cwd, "hi", "gpt-5.6-codex", "medium", harness="codex")`; wait for `run_ended`: the stream holds `thread.started` .. `turn.completed` then `cc_exit 0`; the meta has `harness == "codex"`, `harness_session == "th_fake"`; `run_started` carries `harness`; `run_ended` carries `tokens` and no `cost` key.
- `test_resume_codex_uses_the_thread_id`: a second `start(..., resume=sid, harness="codex")` builds a command with `resume th_fake` (patch `_spawn` to capture the command).
- `test_step_timeout_stops_a_capless_run`: `cfg["step_timeout_s"] = 1`, prompt `SLOW`: `run_ended.subtype == "error_step_timeout"`, `stopped False`, `interrupted False`; `tasks.cap_reason` gives the timeout text.
- `test_resume_takes_the_harness_from_the_meta`: after the Codex run ends, `start(cwd, "go on", "gpt-5.6-codex", "medium", resume=sid)` with no `harness` argument builds a Codex command (`resume th_fake`), never a `claude` one.
- `test_stdin_closed_for_argv_adapters`: a stub adapter whose `run_command` returns `(cmd, None)` and whose command is a script that reads stdin to EOF then prints a result line: the run ends (no hang) within 5 s.
- `test_prompt_too_long_for_cmd`: a 40 000-character prompt on `harness="cmd"` (the fake) raises `RunError` before any process starts.
- `test_chat_dispatches_on_harness`: `chat_of(sid)` of the Codex run gives roles `[you, tool, claude, result]`.
- `test_stop_kills_a_codex_run`: prompt `SLOW`, `stop(sid)` returns `"kill"`, `run_ended.stopped True`.
- `test_open_terminal_refused_for_codex`: `RunError("claude only")`.

`tests/test_state.py`:
- `test_session_from_run_lines_only`: `run_started` (harness codex, model, title) then `run_ended` (success, tokens with `context: None`, no `cost`): one row, `harness == "codex"`, title set, `ctx_tokens is None`, state Replied then Idle, `cost is None`, `spent is None`; a second session's `run_ended` with `subtype: "error"` has state Failed.
- `test_hook_sessions_are_claude`: an existing fixture's row has `harness == "claude"`.

`tests/test_tasks.py`: `test_cap_reason_timeout`.

## Steps

1. Write the twelve tests (nine in `test_runs`, two in `test_state`, one in `test_tasks`); run: TypeError on `exes`, AttributeError on `chat_of`, KeyError on `harness`.
2. `runs.py` first (start, spawn, watch, finish, stop, chat), then `state.py`, then `tasks.cap_reason`; run until green.
3. Whole suite: 354 + 12 = 366. `node --check web/app.js` unchanged (no page change in this task).
4. Commit: `feat: runs and state on any harness adapter (plan 05 Task 4)`.

## Drift guards

- A Claude run's command, stdin, interrupt and `run_ended` line are byte-for-byte what they were (the Claude adapter is a move, not a change): `test_runs`'s earlier tests pin it.
- `stopping` is set by Fred's Stop only; a timeout is `error_step_timeout`, never `stopped`.
- `cost` and `tokens` are absent, never `0`, when unknown.
