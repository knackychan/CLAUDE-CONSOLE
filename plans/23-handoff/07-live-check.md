# Task 7: Fred's live check

> Claude never starts a run, never POSTs `/api/run`, `/api/task`, `/api/prep` or `/api/setting`. Fred runs this after
> Task 6 is placed, the dotclaude skill copied to `~/.claude/skills/session-handoff/`, and the tray's service
> restarted. A real project: CONTENT MANAGER, or this repo on a scratch branch.

## 7.1 The block and the brief

1. A task `scout, code, test, verify` that edits two files (effort auto). Each step's chat ends with the chip
   `HANDOFF block · N w · six headings`; `tasks/<id>/steps/01-scout.md` holds the six headings; the Goal restates the
   task and the step's part.
2. The Task page's Handoff fold after the scout: `Handoff for 02 · N w · Next: ...`; open: `compacted from M w`, the
   six headings, `as 01 wrote it` shows the raw note with any cut finding struck. task.json's step 1 has `brief_meta`
   with eight checks, all ok, `by` the brief model.
3. A task where a step hits a dead end on purpose (ask it to use a tool or interpreter version the machine lacks):
   the Troubleshooting line reaches every later brief word for word.
4. Record per step: raw words, sent words, the cut count, the brief's cost and turns (the measure plan 25 will show).

## 7.2 The facts

5. After the code step: `steps/02-code.facts.md` lists the two files with their line counts (the step did not
   commit: the head reads `..working tree`); the test step's facts show `Tests: <the command>` and `Ran N tests ... OK`;
   the Facts fold's closed line `2 files +N -M · N OK`. A failing test (break one on purpose in a scratch branch):
   FAIL in red, the fold open, the failing lines only.
6. The code step's prompt (the chat's first turn) carries the scout's facts under its brief.
7. Compare the model's Files touched with the facts: note any step whose claim and facts differ (the drift signal).

## 7.3 Lean steps

8. A scout's run: `runs/<sid>.meta.json` limits show `strict_mcp: true` and `max_turns: 15`; the chat's init line lists
   no MCP tool. Compare the first turn's input tokens with a step from before plan 23 (the harness prompt saving of
   brainstorm 5.1 item 1): write both numbers in the History line.
9. A code step's tools: Bash, Read, Edit, Write, Grep, Glob only (D3).
10. A step after step 1 shows the goal cut to 600 characters when the task's goal is longer.
11. Add a `- <day> - <project> - code: ...` lesson by hand (or let a step write one): the next code step's prompt
    carries it under `Lessons from earlier code steps`; a scout's does not.

## 7.4 Auto handoff

12. Settings band: `Window runs · auto hand off: off`; switch it on: config.json has `"handoff_auto": true`.
13. A window run driven past `gauge_red_tokens` (a long reading task, or lower `gauge_red_tokens` for one run): when its
    turn ends, the service runs `/session-handoff` in it; the card `Handed off` under Needs you with
    `↻ handed off by itself at N K`, `✓ handoff ready`, Start next chat; Start next chat seeds the task box with the
    skill's HANDOFF block and the card leaves Needs you.
14. A VS Code chat past red: a fork runs the skill (the VS Code chat untouched), the card says `forked, then handed off`.
15. Switch it off again (the default).

## 7.5 Record

- Each item: expected, seen, the task or session id. Findings become fixes in a follow-up plan (as plan 19 did for 17)
  or small commits when they are one-liners.
- The D1 to D5 answers Fred takes after seeing it run.
