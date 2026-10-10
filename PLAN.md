# Plan: Claude Console (master)

> Context: [BRAINSTORM.md](BRAINSTORM.md) (design, decisions D1-D10), [CLAUDE.md](CLAUDE.md) (rules)

## Goal

Build the companion window in five phases (BRAINSTORM section 12). Each phase is one sub-plan and
ends with working, tested software.

## Sub-plans

| # | Sub-plan | State |
|---|---|---|
| 1 | [plans/01-watch.md](plans/01-watch.md) - hooks, service, tree, gauge, Steps, Needs you, Quiet / Stall?, 2 writers | done 2026-10-10 |
| 2 | [plans/02-run.md](plans/02-run.md) - prompt box, Prep card, Run / Run raw, Chat, Stop, Open in terminal, crash recovery, STOP answers | done 2026-10-10 |
| 3 | [plans/03-levers.md](plans/03-levers.md) - Continue, Verify, Handoff, Escalate + verdict + routing-misses, follow-up hint, Timeline | done 2026-10-10 |
| 4 | [plans/04-polish.md](plans/04-polish.md) - rules-size warning, should-delegate flag, model-mix strip, in-chat handoff Done, move skills to ~/.claude | done 2026-10-10 |
| 5 | Other harnesses - Codex CLI, OpenCode, Command Code | to write |
| 6 | Visual rework - Console Cells (BRAINSTORM 7.5, `design/rework/locked/console-cells.html`): borderless pill + rail + focus pane, cell motif, estimated cost, activity buckets | design locked 2026-10-10; plan to write after phase 4 |

## Changes to the design made while planning phase 1

- **Gauge uses token thresholds, not % of the window.** The 5.x models (Opus 5.5, Sonnet 5.5,
  Haiku 5.5, Fable) run with a 1M window by default (code.claude.com/docs/en/model-config), so
  40% / 60% of the window would only warn at 400K / 600K. Defaults: yellow from 150K tokens, red
  from 300K (`gauge_yellow_tokens`, `gauge_red_tokens` in `config.json`). The bar is full at red.
  This replaces BRAINSTORM sections 6 and 13 "context window size per model".
- **Hook time is about 75 ms** per event on this machine (Python start-up), not the 50 ms target.
  It is async, so it never delays a session.
- **STOP questions are shown in phase 1** (display only; answering comes with Continue in phase 2):
  the parse is one regex and the state already exists.
- Phase 1 sessions are only those Claude Code reports through hooks; "Interrupted" needs the
  window's own runs and comes in phase 2.

## Changes to the design made while planning phase 2

- **Stop is an interrupt over stdin, not a signal.** Ctrl+C to a hidden console did nothing; the
  stream-json `control_request` `interrupt` stops the turn cleanly. Runs therefore use
  `--input-format stream-json` and the service keeps their stdin; a run left over from an earlier
  service can only be killed (`taskkill /T`). Closing the window gives stdin EOF: the turn finishes.
- **Prep runs without hooks, skills or MCP** (`--settings {"disableAllHooks": true}`,
  `--disable-slash-commands`, `--strict-mcp-config`, `--tools Read,Grep,Glob`): $0.03 instead of $0.11,
  and Prep never shows as a session.
- **The service picks the session id** (`--session-id`), so the window knows the session before the
  first hook line; source `window` comes from `run_started`, never from the inherited
  `CLAUDE_CODE_ENTRYPOINT` (removed from the child environment with the other session variables).
- **STOP footer added by the service** to every window-run prompt; the global CLAUDE.md line for VS
  Code sessions is an optional Fred step (Claude does not edit it).
- **Answer / Resume only for window runs** in phase 2; Continue for any session stays in phase 3.
- **Allow runs here** (Fred, after tasks 1-6): the window can add a folder to `config.json`
  `"projects"` with one click, only for a folder a Claude Code session already ran in (plan 02 Task 6b).

## Changes to the design made while planning phase 3

- **`haiku` stays an alias.** On CLI 2.1.296 it resolves to `claude-haiku-5-5` (verified); the Haiku
  4.5 of phase 2 came from CLI 2.1.288 (Haiku 5.5 needs 2.1.293+). No full model ids.
- **VS Code / terminal chats are forked, never resumed in place** (Fred): `--resume <id>
  --fork-session --session-id <new>` gives a window copy with the old context; the original chat is
  not touched. Window runs keep resuming their own id.
- **Verify is a button** (Fred) that asks for a `VERDICT: PASS|FAIL` line; the hook reads verdicts
  from `last_assistant_message` on Stop and SubagentStop, so the service writes no `verdict` line.
- **Escalate ladder** (Fred): effort +1 up to high, then the next model at the same effort; once per
  task; `escalated` is a field of `run_started`, not its own event line.
- **routing-misses.md lives in `~/.claude/console/`** (CLAUDE.md data rule), one line per Escalate
  tagged with the project; Prep reads the project's lines. The `route-model` skill keeps its own file
  until phase 4 moves it.
- **Handoff only where the `session-handoff` skill is installed** (Fred): CONTENT MANAGER now,
  everywhere after phase 4.

## Changes to the design made while planning phase 4

- **Rules size from a new hook event** (Fred): `InstructionsLoaded` logs every CLAUDE.md / rules file a
  session loads, with lines and bytes. Warning at 200 lines in one file (docs target) or 16 KB in all;
  a row badge plus the file list in the detail. Fred re-runs `install_hooks.py --write` once.
- **Should delegate** (Fred): 10 or more main-chat Read / Grep / Glob / WebFetch / WebSearch steps in
  one turn give a `delegate?` badge; never a Needs-you state.
- **Model mix** (Fred): sessions and agent runs per model family plus window runs and their cost, in
  the bottom status strip.
- **A handoff inside a chat makes it Done** (Fred): a typed `/session-handoff` (logged as the prompt;
  a typed skill bypasses PreToolUse) or Claude's own `Skill session-handoff` step, then Stop.
- **Skills move through the repo** (Fred): generic `route-model`, `session-handoff` and `verifier`
  live in `dotclaude/`; Fred copies them to `~/.claude` (a protected path for Claude) in that order and
  deletes CONTENT MANAGER's two skill copies; its verifier stays as a project override.
- **route-model writes chat misses to `~/.claude/console/routing-misses.md`** (Fred), in the
  console's format, so Prep reads them; its table is Prep's table (a test checks it).

## History

- 2026-10-10 - Master plan and sub-plan 01 written. All phase 1 code was run once in a scratch folder
  before being pasted into 01: 37 tests OK, the hook timed on a real transcript (about 75 ms), the
  service smoke-tested with curl (state, static, SSE, foreign Host refused).
- 2026-10-10 - Phase 1 code placed (tasks 0-7, 37 tests OK); Fred ran `install_hooks.py --write`; live: sessions, Steps and the red gauge (this chat at 337.5K) show; hooks also apply to already-open chats. Open: agent-row live check, then Task 8.
- 2026-10-10 - Fred asked for prompting from the window: that is phase 2 (Run); write plans/02-run.md after phase 1 closes.
- 2026-10-10 - Phase 1 done: 37 tests OK; live check passed (an Explore agent row appeared under its session while running, then `✓ Done` with model, steps and tokens; no hook-errors.log). Differed from 01: Fred asked for agent rows to show their state text and a green context bar (`State.gauge(tokens)` now serves sessions and agents; one assertion added, still 37 tests).
- 2026-10-10 - Sub-plan 02 written (zero-decision, final code): verified in a scratch clone (60 tests OK, real Prep through the service, window flows in a browser with a fake claude); the plan re-applied to a fresh clone reproduces that code. Claude could not start a live auto-mode run (its classifier refuses): Task 7 live check is Fred's.
- 2026-10-10 - Phase 2 done: 63 tests OK; live check passed (Prep card, Run with Steps and Chat, Stop, Open in terminal, a run survived closing the window, no error-log lines). Differed from 02: `Allow runs in <name>` button (Task 6b), port 47770, a run that succeeded despite auto-mode denials stays Idle with a note, injected prompt blocks no longer become titles, Open in terminal keeps the run's model and effort. Open: `--model haiku` gives Haiku 4.5 on CLI 2.1.288.
- 2026-10-10 - Sub-plan 03 written (zero-decision, final code): Fred decided fork for VS Code chats, Handoff where the skill is, a Verify button, ladder "effort to high, then model", keep the `haiku` alias (verified Haiku 5.5 on CLI 2.1.296). Verified in a scratch clone: 78 tests OK, tasks replayed in a fresh clone (64, 69, 74, 75, 78), window flows in a browser with the fake claude, fork and `/skill` over stream-json checked with real `claude -p` calls. Task 7 live check is Fred's (Claude cannot start auto-mode runs).
- 2026-10-10 - Phase 3 done: 79 tests OK; live check passed (Verify PASS badge, Continue with the follow-up hint, Escalate sonnet/medium -> sonnet/high with its routing-misses line, which the next Prep read, a fork of this VS Code chat answered from its context and left it untouched, `haiku` ran as claude-haiku-5-5, no error-log lines; Handoff in CONTENT MANAGER not tried). Differed from 03: `STOP: none` was read as a STOP question (fixed in the hook, 1 test); with the skill missing there is no Handoff button, only the off note; a `/session-handoff` typed inside a VS Code chat does not make it Done.
- 2026-10-10 - Sub-plan 04 written (zero-decision, final code): Fred decided the rules limits (200 lines per file or 16 KB in all, via the InstructionsLoaded hook, row badge + detail list), "should delegate" at 10 main-chat reads per turn, the model mix (sessions + agents per model, window runs and cost) in the bottom strip, Done after a handoff inside a chat, the skill move through `dotclaude/` with Fred's copies (handoff, verifier, route-model), chat misses in `~/.claude/console/routing-misses.md`, CONTENT MANAGER keeping its verifier. Verified in a scratch clone: 87 tests OK, tasks replayed in a fresh clone (80, 84, 84, 87), window checked in a browser with the fake claude, InstructionsLoaded fields and the generic skills checked with real `claude -p` calls on 2.1.296. Task 5 (hooks, copies into ~/.claude, live check) is Fred's.
- 2026-10-10 - Phase 4 done: 87 tests OK. Tasks 1-4 placed exactly as written (80, 84, 84, 87); Fred re-installed the hooks, copied the three `dotclaude/` files to `~/.claude` and removed CONTENT MANAGER's two skill copies. Live: `rules 21.0 KB` on a new CONTENT MANAGER chat, `delegate?` after 27 main-chat reads, window Handoff and a typed `/session-handoff` made sessions Done, Verify PASS badge, `/route-model` set the row's route and read the console misses file, no error-log lines. Differed from 04: Verify ignored `~/.claude/agents` and the strip sat below the scrolling page (both fixed, still 87 tests); after the restart Verify ran the `~/.claude` verifier (agent row, PASS); not seen live yet: a route-model miss write.
