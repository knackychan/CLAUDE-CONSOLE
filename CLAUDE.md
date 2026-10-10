# CLAUDE.md - Claude Console

A small always-on-top window that shows every Claude Code session on this machine: its route,
subagents, context gauge and what needs Fred. Design: `BRAINSTORM.md`. Plans: `PLAN.md` (index)
and `plans/NN-*.md` (zero-decision sub-plans with the final code).

## Rules

- Read `PLAN.md`, then the active sub-plan, before editing. Follow its steps; if a step needs a
  decision the plan does not make, stop and ask Fred, then update the plan.
- Keep it small. Python 3.14 standard library + pywebview, plain HTML/CSS/JS, no build step, no
  database, no daemon. Anything on the BRAINSTORM "Non-goals" list is out of scope.
- `cc_events.py` runs inside every Claude Code session as an async hook: it must never raise, must
  always exit 0, must not touch the network, and logs summaries only (masked by `console/redact.py`).
- The service binds 127.0.0.1 only and every request passes `console/guard.py`.
- Data lives in `~/.claude/console/` (or env `CC_CONSOLE_HOME`, which the tests use). Never write
  anywhere else, and never edit `~/.claude/settings.json` from code that Claude runs: Fred runs
  `install_hooks.py` himself.
- All styling is in `web/style.css`, tokens first. The visual rework target is locked: BRAINSTORM 7.5,
  `design/rework/locked/console-cells.html`; files in `design/rework/explored/` are not targets.
- Window runs: commands come only from console/claude_cli.py; runs only in config.json "projects"; Stop is the stream-json interrupt, never a kill of a run this service owns.
- Levers: server.Hub.levers alone decides when Continue / Verify / Handoff / Escalate may run; a VS Code or terminal chat is only ever forked, never resumed in place.
- User-level skills and agents live in dotclaude/ (same layout as ~/.claude); Fred copies them to ~/.claude. Code and Claude write ~/.claude/console/ only.
- No emojis or em-dashes in prose. Verify CLI flags and hook fields against code.claude.com docs
  before relying on them.

## Commands

```bat
py -m unittest discover -s tests   :: all tests
py -m console                      :: the window (service inside)
py -m console --serve              :: service only: http://127.0.0.1:47770/
run.bat                            :: the window without a console
py install_hooks.py [--write|--remove]   :: Fred only: add/remove the hooks in ~/.claude/settings.json
```
