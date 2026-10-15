# Plan 37 handoff (written 2026-10-15, session `claude/project-thread-jctz3k`)

## Prompt for the fresh session

> Implement the rest of `plans/37-harness-hooks/README.md`. Tasks 1-5 are done and tested; Task 6's code is
> written and its `test_levers.py` / `test_harness.py` / `test_runs.py` / `test_server.py` tests pass, and
> `py -m unittest discover -s tests` is 676 OK. Still missing: the three `test_server.py` tests Task 6 asks
> for (`test_levers_outside_codex_chat`, `test_pull_handoff_on_codex_sends_skill_text`,
> `test_route_of_keeps_codex_model`). Read `plans/37-harness-hooks/HANDOFF.md` first: it names the files, the
> fixture records and the assertions to use, and the deviations from the plan. Write those three tests, run
> `py -m unittest discover -s tests`, then do Task 7 (Fred's live check + the PLAN.md / CLAUDE.md / BRAINSTORM
> close). Do not commit anything yet: the working tree already holds uncommitted work from plans 33-36 by
> other chats, so a `git commit -a` would sweep their work in. Ask Fred how to land the commits.

## Where the work is (branch `claude/project-thread-jctz3k`)

Start state was 633 tests OK. Test files are run with `py -m unittest discover -s tests` from the repo root
(~5 min) or `py -m unittest tests.<file>` for one file.

### Task 1 - done
`cc_events.py`, `tests/test_cc_events.py`, `tests/fixtures/__init__.py` (new; the small Codex and Command Code
transcript fixtures, written at setUp, shared with Task 5).
Added `HARNESSES`, `TOOL_MAP`, `harness_arg`, `patch_path`, `strip_ide_context`, `map_tool`, `_tail_lines`,
`codex_tail`, `cmd_tail`, `harness_tail`, `_head_source`, `_text_blocks`, `_meta_entrypoint`, `_three_ints`;
`build_record(data, now=None, harness="claude", env=None)` and `main()` now read `--harness`.
`py -m unittest tests.test_cc_events` -> 25 OK.

### Task 2 - done
`hooks/opencode/claude-console.js` (new) + `tests/test_opencode_plugin.py` (new). Node v26 detects the ESM
syntax in a `.js` file with no `package.json`, so `node --check` passes.
`py -m unittest tests.test_opencode_plugin` -> 6 OK (skipped if `node` is absent).
**Risk settled 2026-10-15** (README 5): OpenCode 2.0.26 reads only a `{id, setup}` default export and the v2 bus
(`ctx.event.subscribe`); the plugin was rewritten for it and is installed as the directory
`plugins/claude-console/` (index.js + package.json). Checked with a real `opencode run --standalone` turn under a
scratch `XDG_CONFIG_HOME` and `CC_CONSOLE_HOME`: UserPromptSubmit, PreToolUse (`task` -> Agent, `shell` -> Bash),
SubagentStart / SubagentStop and Stop with model, context and tokens all reached `events-<day>.jsonl`.

### Task 3 - done
`install_hooks.py` rewritten (four harnesses, dry run, backups, `--harness all`), `tests/test_install_hooks.py`
extended (2 old + 6 new tests).
`py -m unittest tests.test_install_hooks` -> 8 OK.

### Task 4 - done
`console/state.py` (SOURCES, session `harness` intake, `turn_prompt`, `turn_tokens`, SessionStart entrypoint,
Stop-prompt for Command Code, `Interrupt`, `files()` only for Claude), `console/server.py` (`poll_once` ->
`count_turn`), `tests/test_state.py` (6 new), `tests/test_server.py` (2 new in `TaskServerTest`).
`py -m unittest tests.test_state` -> 40 OK.

### Task 5 - done
`console/transcript.py` (`codex_turns`, `cmd_turns`, `opencode_turns`, `turns_of`, `first_prompt_of`,
`OPENCODE_DB`), the three `console/server.py` call sites (`_chat`, `last_reply`, `brief_text`),
`tests/test_transcript.py` (6 new).
`py -m unittest tests.test_transcript` -> 14 OK.

### Task 6 - code written, one test file left
- `console/runs.py`: `CC_CONSOLE_SID` in a non-Claude child's env; a fork with no meta takes the caller's
  harness and uses the row id as the CLI session id; `result_record(..., harness=)` reads the VERDICT line
  through `cc_events.verdict` (function-local import, the hook's own parser) when the hook did not.
- `console/levers.py`: `escalate_step(model, effort, harness="claude", cfg=None)`, `handoff_prompt(home=None)`.
- `console/state.py`: `run_ended` takes `verdict`/`verdict_detail` when no Stop of this turn brought one.
- `console/harness/{codex,opencode,cmd}.py`: `terminal_command`.
- `console/server.py`: `route_of` (another CLI's model as it came), `cold` (None for another CLI),
  `Hub.levers` reads `s["harness"]`, `handoff_prompt` gate, `terminal` only for a window run, `continue` for
  an outside chat, `escalate_step(..., hname, cfg)`; `Hub.pull` sends the skill text for a non-Claude Handoff
  and passes `harness=hname` to `runs.start`.
- `web/app.js`: **no change needed** (there is no `claude only` literal there; the Terminal button is already
  gated on `s.window && !s.run_live`).
- Tests written and passing: `tests/test_levers.py` (2 new), `tests/test_harness.py` (3 new),
  `tests/test_runs.py` (3 new + `test_open_terminal_refused_for_codex` replaced by
  `test_open_terminal_resumes_a_codex_run`), plus `test_run_on_a_codex_rung` rewritten in
  `tests/test_server.py` `HarnessServerTest` (it asserted plan 05 decision 10's four `claude only`; see
  "Suite state").

**Left in Task 6** - the three `tests/test_server.py` tests, best placed in `HarnessServerTest` (it already has
codex on, `FAKE_CODEX` and `self.hub.user_home`):
1. `test_levers_outside_codex_chat` - feed SessionStart (entrypoint `vscode`, model `gpt-6.1-sol`, effort
   `medium`) + UserPromptSubmit + Stop with `verdict: FAIL` for `session_id "cx1"`, `harness "codex"`;
   set `self.hub.cfg["models"]["codex"] = {"gpt-6.1-sol": "sonnet", "gpt-6-astra": "opus"}` and create
   `self.hub.user_home/".claude"/"skills"/"session-handoff"/"SKILL.md"`; then assert `continue`, `verify`,
   `handoff`, `escalate` are `""`, `fork` True, `escalate_to` `gpt-6-astra/medium`, `terminal` off and
   `deescalate` `only for window runs`.
2. `test_pull_handoff_on_codex_sends_skill_text` - `/api/handoff` on that session is 200 and the run's stream
   file (`self.hub.runs.stream_path(new)`) holds the skill body in its `cc_prompt` line.
3. `test_route_of_keeps_codex_model` - `self.hub.route_of("no-such-run", {"harness": "codex", "model":
   "gpt-6-astra", "effort": "high"})` == `("gpt-6-astra", "high")`; `effort "auto"` -> `cfg["default_effort"]`.

### Task 7 - not started
Fred's live check (`py install_hooks.py --harness codex,cmd,opencode` dry run then `--write`, trust the hooks,
restart the service, one chat per CLI, one window run per harness, one Verify/Escalate on an outside Codex
chat), then the close: PLAN.md row + Log line, CLAUDE.md's hook and settings rules, BRAINSTORM's harness slot,
plan 05 README decision 10.

## Deviations from the plan (deliberate, all tested)

- `runs.result_record` uses `cc_events.verdict` (as the plan says) but imported inside the function, to keep
  `console` free of a module-level import of the hook script.
- `TOOL_MAP` holds exactly the rows of README 3.3; `shell_command` (seen 16 724 times in this machine's Codex
  history) was **not** added to the Codex column - Task 7 corrects the table from the live events.
- `codex_turns` keeps every `event_msg` `agent_message`, not only `phase == "commentary"` ones, so a final
  answer is not dropped.
- `first_prompt_of` for the other three CLIs returns the first `you` turn of the tail read (no head reader).
- `Hub.levers`' terminal-off reason is now `only for window runs` instead of `claude only`.
- `Session.turn_tokens` is stored as the plan asks but nothing reads it yet.
- `tests/fixtures/` is a package (`__init__.py` with two builders) rather than three committed files.

## Suite state

`py -m unittest discover -s tests` on 2026-10-15 after Task 6's rewrite: **676 tests, OK** (309 s).
(The start state was 633 tests OK; the 43 new ones are plan 37's.)

Two existing tests had to change because plan 37 replaces plan 05 decision 10:
`test_runs.HarnessRunsTest.test_open_terminal_refused_for_codex` -> `test_open_terminal_resumes_a_codex_run`,
and `test_server.HarnessServerTest.test_run_on_a_codex_rung` (it asserted four `claude only` for a Codex
window run; it now checks verify/terminal allowed, escalate after a FAIL, the handoff skill message, and that
`/api/terminal` runs `FAKE_CODEX + ["resume", "th_fake", "-m", "gpt-6.1-sol"]` with `subprocess.Popen` mocked).

## Commits

`git status` shows the working tree already carries plans 33-36's uncommitted work in `PLAN.md`, `CLAUDE.md`,
`console/{claude_cli,fills,replan,runs,server,state,tasks,usage}.py`, `tests/{test_fills,test_harness,
test_replan,test_runs,test_server,test_state,test_tasks,test_usage}.py`, `web/app.js`, `web/style.css`.
`console/server.py`, `console/runs.py`, `tests/test_server.py`, `tests/test_state.py`, `tests/test_runs.py`
and `tests/test_harness.py` therefore hold **both** chats' work: do not `git add -A`. Task 6's server tests
are still to be written, so nothing of plan 37 should be committed until Fred says how he wants it landed
(one commit per task with partial staging, or one plan-37 commit excluding the other chats' hunks).

Files plan 37 touched that no other chat has touched (safe to stage as-is): `cc_events.py`,
`install_hooks.py`, `console/levers.py`, `console/transcript.py`, `console/harness/{codex,opencode,cmd}.py`,
`hooks/opencode/claude-console.js`, `tests/test_cc_events.py`, `tests/test_install_hooks.py`,
`tests/test_opencode_plugin.py`, `tests/test_transcript.py`, `tests/test_levers.py`, `tests/fixtures/`.
