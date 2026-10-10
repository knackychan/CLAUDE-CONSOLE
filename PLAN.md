# Plan: Claude Console (master)

> Context: [BRAINSTORM.md](BRAINSTORM.md) (design, decisions D1-D10), [CLAUDE.md](CLAUDE.md) (rules)

## Goal

Build the companion window in five phases (BRAINSTORM section 12). Each phase is one sub-plan and
ends with working, tested software.

## Sub-plans

| # | Sub-plan | State |
|---|---|---|
| 1 | [plans/01-watch.md](plans/01-watch.md) - hooks, service, tree, gauge, Steps, Needs you, Quiet / Stall?, 2 writers | written 2026-10-10, not started |
| 2 | Run - prompt box, Prep card, Run / Run raw, Chat, Stop, Open in terminal, crash recovery, STOP answers | to write after phase 1 |
| 3 | Levers - Continue, Handoff, Escalate + verdict + routing-misses, follow-up hint, Timeline | to write |
| 4 | Polish - rules-size warning, should-delegate flag, model-mix strip, move skills to ~/.claude | to write |
| 5 | Other harnesses - Codex CLI, OpenCode, Command Code | to write |

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

## History

- 2026-10-10 - Master plan and sub-plan 01 written. All phase 1 code was run once in a scratch folder
  before being pasted into 01: 37 tests OK, the hook timed on a real transcript (about 75 ms), the
  service smoke-tested with curl (state, static, SSE, foreign Host refused).
- 2026-10-10 - Phase 1 code placed (tasks 0-7, 37 tests OK); Fred ran `install_hooks.py --write`; live: sessions, Steps and the red gauge (this chat at 337.5K) show; hooks also apply to already-open chats. Open: agent-row live check, then Task 8.
- 2026-10-10 - Fred asked for prompting from the window: that is phase 2 (Run); write plans/02-run.md after phase 1 closes.
