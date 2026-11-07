# Plan 57: Codex task fixes (incident 2026-10-16, task 20261016-082254-5dff), ported onto master

> Master: [../PLAN.md](../PLAN.md). Rules: [../CLAUDE.md](../CLAUDE.md). Evidence:
> [../troubleshooting/2026-10-16-codex-task-5dff.md](../troubleshooting/2026-10-16-codex-task-5dff.md).
> Touches plan 5 (the Codex adapter), plan 17 / 23 (step end, handoff), plan 29 (Prep kind file), plan 36 (manual
> progression), plan 43 (Codex write check), plan 47 (planner kind file) and plan 52 Tasks 3 and 6 (the DECISION card
> and the `actions` field). Historical task records are not rewritten and the task is not resumed by code.

Status: code done 2026-11-07 on branch `claude/port-codex-fixes` (D1 to D4 and the planner mirror; 1180 tests OK, 13 of
them new; `node --check web/app.js` clean; `py -m tests.live_autopilot_check` 7 of 7). The live Codex turn (step 4) and
the recovery of the incident task are Fred's.

## 1. Where this came from

The fixes were written on 2026-10-16 as "plan 38" in one commit (`424548f`) on `origin/claude/project-thread-jctz3k`,
on top of `4d7fa38`. Master took the number 38 for the UI audit and moved on (plans 43 to 54), so the branch could not
merge. It was ported by hand, decision by decision, tests first, one commit each; `git merge` was not run. The four
decisions of the old plan stand; this file renumbers it and records how each one sits with what master has since.

## 2. Decisions

1. **Codex discovery runs what `codex` runs.** `harnesses.codex.exe` still wins when it exists. Otherwise the candidates
   are the native binaries an npm install keeps under its shim (`<shim dir>/node_modules/@openai/codex/node_modules/`
   `@openai/codex-*/vendor/*/bin/codex.exe`, then `vendor/*/bin/codex.exe`), then `codex.exe` on PATH. The first one with
   its sibling `codex-code-mode-host(.exe)` wins; with none complete, the first candidate; with no candidate, the old
   `which` order (a shim). No user path is written in code, the sandbox flag is untouched, and the npm `.cmd` shim is never
   run when a native binary stands under it (batch files re-parse their arguments; `claude_cli.find_exe` has the same rule).
   *Fit with plan 43:* none to reconcile. `codex.write_block` reads `[windows] sandbox` and the project folder's owner and
   never the executable; `find_exe` reads the disk for binaries and never the folder or config.toml. A test pins that
   neither calls the other. A copy of `codex.exe` without its host (the `~/.codex/.sandbox-bin` one of the incident) is not
   a write-check case: it starts, then cannot run tools.
2. **A blocked step says so, in one checked line.** The step prompt's `## Next` gains an optional
   `Status: blocked: <why>` line, only for a step that could not do its work at all. A tool error worked round, a failing
   test, an open question or a DECISION is not blocked. `tasks.blocked_of(block)` reads the last such line in the Next
   section (masked, 200 characters; a bare `Status: blocked` still blocks). No Status line, `Status: done` or a Status line
   in another section keeps today's behaviour, so old handoffs and other harnesses pass unchanged.
   *Fit with plan 52 (default, Fred to confirm):* a blocked step waits as a plain question does. `Hub._ended` ends it
   through `tasks.on_step_ended(question="Blocked: <why>")`, so the task is `waiting` with `why` `asks: Blocked: <why>`,
   the step stays running (unfinished), `cs["asked"]` is set, and nothing advances, automatic or manual. This reuses the
   existing `asks:` state and adds no waiting state, no `actions` state name, no UI and no config. Consequences, all
   by test unless marked (read), which is by reading the code:

   | Neighbour | Behaviour with a blocked step |
   |---|---|
   | `STOP:`, `DECISION:` or a Plan gap with a STOP line in the same reply | that question wins (it is checked first and is more specific); the Status line is ignored |
   | `Plan gap:` under Open questions without a STOP line | (read) blocked wins (checked before the gap); the gap, if real, comes back when the step runs again |
   | a design step | it waits before `plan.parse`: no plan is saved, no `plan ready: confirm` hold, no level gate is reached |
   | DECISION default (`auto`, `decision_timeout_s`) | none: a blocked step has no `task["decision"]`, so `_decision_default` has no default to take; it waits on every level (a question without a default is a hard stop, README 52 section 2) |
   | supervisor wake | none: `supervisor.boundary` wakes on `stuck`, `hold` (exact plan holds), `done`, `message` and manual boundaries, not on `asks:` (tested); `_supervisor_dispatch` refuses with "a question waits for Fred" (read) |
   | `GET /api/task` `actions` | `state: decision`, `line: needs you · Blocked: <why>`, no primary (no options, no `default_auto`), bar `[stop]`, the usual menu; `message.mode` is `answer` once the run has ended (README 52 section 3, the plain-question row) |
   | answering | the existing answer path: POST /api/task/message continues the step's own session, the task runs again, and the step ends with a new handoff (without the Status line it finishes normally) |
   | a handoff that fails its checks | (read) the retry path, as today: the line is read only from a valid handoff |
   | usage limit or a failed run | (read) the retry path: `ok` is false, so the line is not read |

   Fred's ways out are the ones a question has: answer it (restore the tool, then say so), Stop (then Retry on a model
   or Resume), or Finish.
3. **A nested Codex error keeps its message.** `item.completed` with `item.type == "error"` is a chat note with the item's
   `message`, masked (`redact.mask`) and cut to 300 characters like the top-level `error` line (which now masks too).
   `summary` is unchanged: a recoverable item error never fails the turn (plan 43's `error_write_denied` and
   `error_shell_start` are separate and unchanged).
4. **Findings-only work routes to explain, not design.** Prep's kind table: `design` is the implementation PLAN the write
   steps follow; `explain` covers an audit or review across many files with findings only; one line says a read-only audit
   is explain (scout for a quick one) and that Prep rates its reasoning high when the audit needs Opus. The design kind file
   and PLAN validation stay as they are. This is a repo-copy change (`dotclaude/console/kinds/prep.md`): a running console
   keeps its own `<home>/kinds/prep.md` until Fred takes the repo copy on the Models page (Reset to repo copy).
5. **The planner kind file mirrors D4** (default, Fred to confirm; added in this port, not in the old plan). Plan 47's
   planner pass rewrites Prep's steps with its own kind table (`dotclaude/console/kinds/planner.md`) and puts one design
   step in the middle of a hard task, so an audit Prep sent to explain could come back as design. The same two rows and rule
   line went in. It is its own commit; reverting it leaves D4 as in the old plan.

## 3. Steps as built (tests first, one commit each)

1. D1: `console/harness/codex.py` (`HOST`, `NATIVE`, `_vendored`, `_complete`, `find_exe`); `tests/test_harness.py`
   (`test_find_exe_skips_an_incomplete_sandbox_copy`, `test_find_exe_without_a_complete_install`,
   `test_find_exe_leaves_the_write_check_alone`).
2. D3: `codex.chat`; `test_nested_error_keeps_its_message_masked`.
3. D2: `console/step_prompt.md`, `console/tasks.py` (`blocked_of`), `console/server.py` (`_ended`), `tests/fake_claude.py`
   (word `STEP-BLOCKED`), `tests/test_tasks.py` (`test_blocked_of`, the prompt assertions), `tests/test_server.py` (six
   `blocked` tests and one row in `test_actions_per_state`).
4. D4: `dotclaude/console/kinds/prep.md`; `tests/test_kinds.py::test_prep_routes_findings_only_work_to_explain`.
5. D5: `dotclaude/console/kinds/planner.md`; `tests/test_kinds.py::test_planner_keeps_audits_out_of_design_too`.
6. This plan, the PLAN.md row and the incident note.

## 4. Differences from the old branch

- `blocked_of` reads the Next section only, and its regex stays on one line (the old one let a bare `Status: blocked`
  take the next line as its reason). A test pins both.
- `_ended` reads the line only from a handoff that passed its checks (`not block_error`); the old code read it from any
  block of a clean run.
- The old code's `web/app.js` and `web/style.css` hunks are **dropped**. They belong to a different feature that the old
  commit carried along: a chat with no task picked on the Board (`boardPick` "o<id>", `inspSession`, `boardSessFetch`, a
  `.card.picked` outline). They target `cardHtml` and `quietHtml` inside `.v-chain`; on master the Board chain draws such a
  chat with `sessionRow` (a `.v-th` row that opens the session page and already takes `.picked`), so the hunks no longer
  apply and re-deriving them would be a new Board feature that no plan asks for. None of the four decisions touches the web.
- The old branch's `tests/test_tasks.py` change that raised a step-prompt length bound from 9000 to 9100 is not needed: no
  such bound exists on master.
- Not copied: the 293-line task-folder plan in `.claude/console/plans/20261016-095927-6346-audit-the-whole-claude-console-claude/`
  (the mirror of an unrelated audit task); it stays on the old branch as history. The incident note was copied.

## 5. Recovery of task 20261016-082254-5dff (Fred, unchanged from the old plan)

1. Restart the service so the new discovery runs; the Models page or the probe line shows the Codex version (0.162.1
   expected, not 0.155.0-alpha). Setting `harnesses.codex.exe` is no longer needed.
2. Take the repo copy of `prep.md` (and `planner.md`) on the Models page if new tasks should take the routing text.
3. Step 02 (test) is recorded done without tests: do not trust its handoff. Stop the waiting task (or answer step 03's
   STOP question) and start the audit again as a new task, or add a fresh test step on the Board with Add next step.
4. A live Codex turn (one `codex exec --json` step) checks decisions 1 and 3 on the real CLI; the unit tests mock it. Step 4
   of the old plan, Fred's.

## 6. Questions for Fred

- D2 reuses the `asks:` waiting state (default). A separate `blocked` state with its own `actions` line and an
  "Accept anyway" button would need a UI task; say so if wanted.
- D5 (planner mirror): keep, or revert the commit.
- Whether a Claude step may also write `Status: blocked` is settled by the prompt (every harness shares `step_prompt.md`);
  Codex's own "host missing" case is only the first user.
