# Plan 38: Codex task fixes (incident 2026-10-16, task 20261016-082254-5dff)

> Evidence: [troubleshooting/2026-10-16-codex-task-5dff.md](../troubleshooting/2026-10-16-codex-task-5dff.md).
> Touches plan 05 (the Codex adapter), plan 17 / 23 (step end, handoff), plan 29 (Prep kind file), plan 36
> (manual progression: a blocked step waits there too). Historical task records are not rewritten and the task is
> not resumed by code.

## Decisions

1. **Codex discovery runs what `codex` runs.** `harnesses.codex.exe` still wins when it exists. Otherwise the
   candidates are the native binaries an npm install keeps under its shim (`<shim dir>/node_modules/@openai/codex/`
   `node_modules/@openai/codex-*/vendor/*/bin/codex.exe`, then `vendor/*/bin/codex.exe`), then `codex.exe` on PATH.
   The first one with its sibling `codex-code-mode-host(.exe)` wins; with none complete, the first candidate; with
   no candidate, the old `which` order (a shim). No user path is written in code, the sandbox flag is untouched, and
   the npm `.cmd` shim is never run when a native binary stands under it (batch files re-parse their arguments).
2. **A blocked step says so, in one checked line.** The step prompt's `## Next` gains an optional
   `Status: blocked: <why>` line, only for a step that could not do its work at all. A tool error worked round, a
   failing test reported, or an open question is not blocked. `tasks.blocked_of(block)` reads it (the last such
   line, masked, 200 characters). The service treats it like a `Plan gap:`: the task waits with
   `asks: Blocked: <why>`, the step stays unfinished, nothing advances (auto or manual). No `Status:` line, or
   `Status: done`, keeps today's behaviour, so old handoffs and other harnesses pass unchanged. A failed run still
   goes the retry path; the line is read only from a run that ended cleanly with a block.
3. **A nested Codex error keeps its message.** `item.completed` with `item.type == "error"` is a chat note with the
   item's `message`, masked (`redact.mask`) and cut to 300 characters like the top-level `error` line (which now
   masks too). `summary` is unchanged: a recoverable item error never fails the turn.
4. **Findings-only work routes to explain, not design.** Prep's kind table: `design` is the implementation PLAN the
   write steps follow; `explain` covers an audit or review across many files with findings only; one line says a
   read-only audit is explain (scout for a quick one) and that Prep rates its reasoning demand high when the audit
   needs Opus. The design kind file and PLAN validation stay as they are. The seed changes reach a running
   console only for kind files still missing in `<home>/kinds/`: Fred resets `prep.md` on the Kinds tab (or deletes
   it) to take the new text.

## Steps

1. `console/harness/codex.py`: `find_exe` per decision 1; `chat` per decision 3. Tests in `tests/test_harness.py`.
2. `console/step_prompt.md` and `console/tasks.py` (`blocked_of`); `console/server.py` `_ended` waits on it.
   Tests in `tests/test_tasks.py` and `tests/test_server.py` (fake_claude marker `STEP-BLOCKED`).
3. `dotclaude/console/kinds/prep.md` per decision 4.
4. `py -m unittest discover -s tests`.

## Recovery of task 20261016-082254-5dff (Fred, after the service restart)

1. Restart the service so the new discovery runs; the Models page or the probe line shows the Codex version (0.162.1
   expected, not 0.155.0-alpha). Setting `harnesses.codex.exe` is no longer needed.
2. Reset `prep.md` on the Kinds tab if new tasks should take the routing text.
3. Step 02 (test) is recorded done without tests: do not trust its handoff. Stop the waiting task (or answer step 03's
   STOP question) and start the audit again as a new task, or add a fresh test step on the Board with Add next step.
4. A live Codex turn (one `codex exec --json` step) checks decisions 1 and 3 on the real CLI; the unit tests mock it.
