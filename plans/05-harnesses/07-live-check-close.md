# Task 7: Fred's live check, the recorded shapes, close

> Depends on Task 6. Fred runs the checks (Claude cannot start auto-mode runs: plan 02); this chat reads the
> results and pins the stream shapes.

## Live check (Fred, on the real machine, a scratch project folder listed in config.json)

1. Restart the tray service. The settings popover lists the four harnesses; `codex` and `cmd` turn on from the
   window and show their versions (`codex-cli 0.162.1`, `Command Code v1.81.0` or newer); `opencode` turns on and
   shows its version (note it here: the plan's facts have none yet). Config.json shows the three `on` flags and
   nothing else changed.
2. Fill `harnesses.codex.models`, `harnesses.opencode.models` and `harnesses.cmd.models` with real ids
   (`cmdc --list-models`, Codex's model names from `codex --help` or its docs, OpenCode's `provider/model` ids);
   restart; the Prep card's route select lists them under their harness.
3. Run raw on `codex:<model>`, prompt `Read calc.py and say what add() does; do not edit anything.` (a read-only
   prompt). Expected: a session row with `codex · <model> · medium`, Chat with the agent text and the tool events,
   `run_ended` with `tokens`, the levers bar with Verify / Hand off / Escalate / Open in terminal off (`claude only`).
   Copy `runs/<sid>.jsonl` to `tests/fixtures/codex-run.jsonl` (mask anything personal; the fixture is small).
4. The same on `cmd:<model>` with `--permission-mode accept-edits` as the adapter sends it, prompt
   `Run py -m unittest discover -s tests and report the summary line.` Expected: the result line in the stream;
   if the run shows a permission prompt or ends without running the command, note it: that is the open fact of
   Task 3 (shell commands under `accept-edits` in `-p` mode) and the rule becomes `--yolo` for `test` steps only,
   with Fred's word. Copy the stream to `tests/fixtures/cmd-run.jsonl`.
5. The same on `opencode:<model>` with a read-only prompt. Note the event shapes; copy to
   `tests/fixtures/opencode-run.jsonl`.
6. A task from the Prep card with a scout step picked on `codex:<model>` and a code step on Claude: the chain
   runs through, the scout's HANDOFF block parses, the brief pass runs, the code step reads it. The Task page shows
   the harness on the scout row.
7. `step_timeout_s` set to 60 in config.json, a Codex run with a prompt that reads a lot: the run ends with
   `error_step_timeout` and, in a task, the retry reason names the timeout. Put the key back.
8. Stop on a live Codex run: the row goes to stopped, the process tree is gone (Task Manager).
9. No lines in the service log that name a harness error except the ones these checks provoked.

## Pin the shapes (this chat, after the fixtures land)

- `tests/test_harness.py` gains `test_codex_fixture`, `test_cmd_fixture`, `test_opencode_fixture`: each reads its
  fixture and asserts `summary()["final"]` is the text Fred saw, `subtype == "success"`, `session_id` non-empty,
  and for Codex `tokens["context"] > 0`. Where the recorded shape differs from the defensive first version
  (`is_result`, `summary`), the adapter is corrected and the README 3.4 table rewritten from the fixture; the
  longest-string fallback stays as the last resort.
- If `cmd` under `accept-edits` did not run the test command (item 4): decision in this file's History, then
  `cmd.run_command` takes `yolo: bool` that `Hub.start_step` sets for `test` steps only, with the note
  `permissions: yolo (test step on cmd)`. Not before Fred's word.

## Close

- `PLAN.md` row 5: `done <date>` with the test count and what differed; a History line.
- `BRAINSTORM.md` section 4 "Harness slot": replace "Only Claude Code is built. Codex CLI (`codex exec`), OpenCode
  (`opencode run`) and Command Code (`cmdc`) are later adapters; their flags and output formats are not checked yet"
  with the four adapters and a pointer to `plans/05-harnesses/README.md` 3.4; the Claude Code commands table keeps
  its place.
- `CLAUDE.md` rules: the line "Window runs: commands come only from console/claude_cli.py" becomes "commands come
  only from the adapters in console/harness/ (claude_cli.py for Claude Code)"; the Stop line gains "; a harness
  with no interrupt is stopped by killing its process tree (plan 05 decision 8)".
- This README's state line: `done <date>`.
- Commit: `docs: plan 05 closed (harness adapters live)`.

## History

- (filled when executed)
