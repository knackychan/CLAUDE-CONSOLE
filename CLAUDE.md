# CLAUDE.md - Claude Console

A small always-on-top window that shows every Claude Code session on this machine: its route,
subagents, context gauge and what needs Fred. Design: `BRAINSTORM.md`. Plans: `PLAN.md` (index)
and `plans/NN-*.md` (zero-decision sub-plans with the final code).

## Rules

- Read `PLAN.md`, then the active sub-plan, before editing. Follow its steps; if a step needs a
  decision the plan does not make, stop and ask Fred, then update the plan.
- Keep it small. Python 3.14 standard library + pywebview, plain HTML/CSS/JS, no build step, no
  database, no daemon. Anything on the BRAINSTORM "Non-goals" list is out of scope.
- `cc_events.py` runs inside every Claude Code, Codex, Command Code and OpenCode session as an async hook
  (`--harness <name>`, default `claude`): it must never raise, must always exit 0, must not touch the
  network, and logs summaries only (masked by `console/redact.py`).
- The service binds 127.0.0.1 only and every request passes `console/guard.py`.
- Data lives in `~/.claude/console/` (or env `CC_CONSOLE_HOME`, which the tests use). Never write
  anywhere else (one exception, plan 28: a task's plan is mirrored into `<project>/.claude/console/plans/`), and never edit `~/.claude/settings.json`, `~/.codex/hooks.json`,
  `~/.commandcode/settings.json` or the OpenCode plugin file from code that Claude runs: `install_hooks.py`
  is the only code that writes another CLI's config, and Fred runs it himself.
- All styling is in `web/style.css`, tokens first. The visual rework target is locked: BRAINSTORM 7.5,
  `design/rework/locked/cells-drawer.html` (tokens and cell motif: `console-cells.html`; Usage page: `usage.html`); files in
  `design/rework/explored/` are not targets.
- Window runs: commands come only from the adapters in console/harness/ (claude_cli.py for Claude Code); runs only in config.json "projects"; Stop is the stream-json interrupt, never a kill of a run this service owns; a harness with no interrupt (Codex, OpenCode, Command Code) is stopped by killing its process tree (plan 05 decision 8).
- Levers: server.Hub.levers alone decides when Continue / Verify / Handoff / Escalate may run; a VS Code or terminal chat is only ever forked, never resumed in place.
- User-level skills and agents live in dotclaude/ (same layout as ~/.claude); Fred copies them to ~/.claude. Code and Claude write ~/.claude/console/ only.
- The plan a design step writes is saved by the service as tasks/<id>/plan.md and plan/NN-*.md, never cut; plan 24 README is its contract.
- Handoffs (step notes, briefs, the session-handoff skill) use tasks.HEADINGS, six headings; facts (git and the last test) are code-read and never compacted; plan 23 README is the contract.
- The Models and tuning page writes config.json only through POST /api/config/models (console/tuning.py whitelist, all or nothing); it never writes models.json.
- The Board is a page of the one window (plan 25): WindowApi.board(on) alone widens and returns it; it reads GET /api/task, /api/chat and /api/measure and writes nothing but window.json, except a chat task's follow-up (Continue under its chat, the existing POST /api/continue; Fred decided 2026-10-15) and plan 36's Add next step: POST /api/task/next/preview (local, starts nothing) then POST /api/task/next with the preview's revision and a request id, which appends one step to the same task in a fresh session (resume=None) and saves its received-handoff.md and received.md; availability comes only from GET /api/task levers.add_next and next_step, and Finish task is the existing POST /api/task/done. The Hand off task form uses POST /api/task/handoff/preview (local, starts nothing, runs one haiku pass over saved files) and POST /api/task/handoff (Save document writes task-handoff.md only; Create follow-up makes a planned, Fred-owned linked draft and sets the source handed with handoff_to).
- No emojis or em-dashes in prose. Verify CLI flags and hook fields against code.claude.com docs
  before relying on them.

Plan 42 extends the Board's writes: task conversations use POST /api/task/message, with availability and destination
from GET /api/task `message`. Guidance is persisted before acknowledgement and dispatched in order before task
progression. Stop keeps the queue; Retry carries it only with an explicit choice; actions that strand it require
resolution. Uncertain dispatches are never replayed automatically. Standalone sessions retain POST /api/continue.

## Commands

```bat
py -m unittest discover -s tests   :: all tests
py -m console                      :: tray icon (service inside); opens the window
py -m console --window             :: the window only, for a running service
py -m console --serve              :: service only: http://127.0.0.1:47770/
run.bat                            :: the window without a console
py install_hooks.py [--harness all] [--write|--remove]   :: Fred only: add/remove the hooks in ~/.claude/settings.json,
                                                     ~/.codex/hooks.json, ~/.commandcode/settings.json and the OpenCode plugin
```
