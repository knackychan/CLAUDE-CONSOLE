# Sub-plan 13: Handoff opens the next chat, and what follows Verify

> Master: [PLAN.md](../PLAN.md). Decided by Fred 2026-10-11 (option a).

## Decisions

- **Hand off keeps the skill run.** `/api/handoff` still sends `/session-handoff` (a window run resumes,
  a VS Code or terminal chat is forked); its successful end makes the session Done, and the fork's
  original chat too (unchanged since plan 04).
- **Start next chat** after a handoff: the session page offers it once the session is handed off. It
  pre-fills the new-task box with `brief.NEXT_INTRO` plus the skill's last message (its note and
  starter prompt, lines kept, cut at 3000 characters); Fred edits it and runs it through Prep / Run
  like any new task. No run starts by itself; no model call builds the text.
- **Order after Verify** comes from `levers.after_verify(verdict)` through `Hub.levers`:
  PASS: Hand off (primary), Mark done. FAIL: Escalate (primary), Hand off, Mark done.
  No verdict: Hand off, Escalate (off until a FAIL), Mark done. Mark done is the Accept step.

- **Hand off after a PASS re-reads nothing** (Fred: c, 2026-10-13). When the session's verdict is PASS and it
  is not a task step, `Hub.levers` sets `handoff_fresh`; `Hub.pull` then starts a new chat (no resume, no fork) on
  `levers.HANDOFF_ROUTE` (sonnet/medium) with `/session-handoff <brief>`: `brief.build("handoff")`, the facts of
  the session (goal, last message, edited files, verdict, git status) on one line, since newlines in skill
  arguments are not documented. Its `run_started` carries `handoff_of`; its successful end makes the source
  Done with `handoff_by` the new chat, so Start next chat reads the new chat's note. No cold-cache confirm (the
  window skips it too). The skill treats the arguments as the chat. Before a PASS, Hand off works as before.

## Code (placed 2026-10-11)

- `console/state.py`: `Session.handoff_by`, the session whose last message is the note (itself, or its
  Handoff copy for a forked chat); cleared by a new prompt or run; row field `handoff_by`.
- `console/levers.py`: `after_verify`.
- `console/server.py`: `Hub.levers` returns `next` ("" or why it is off) and `after_verify`;
  `/api/brief?kind=next` asks `Hub.levers` first (409 when off) and reads the note from the window
  stream or the transcript (`_last_reply`).
- `console/brief.py`: `NEXT_INTRO`, `build("next", last=...)`.
- `web/app.js`: `Start next chat` button, levers drawn in `after_verify` order.
- Tests: `test_handoff_starts_a_new_session_with_the_note`, `test_lever_order_after_verify`
  (test_server), `test_after_verify` (test_levers), `test_next_brief_keeps_the_note_lines` (test_brief),
  `handoff_by` asserts in test_state. 134 tests OK.

## Task 2 (Fred): live check

In CONTENT MANAGER: Hand off a window run, then click Start next chat; the box holds the note, Run
starts a new row and the old one stays Done. Then Verify a run: PASS shows Hand off first, FAIL shows
Escalate first.
