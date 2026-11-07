# Task 7: Fred's live look and the close

Files: `PLAN.md`, `CLAUDE.md`, `plans/38-*.md` (its status line), `plans/52-workflow-autopilot/README.md` (its D9 note),
this folder's README status line. Commit boundary: `docs: close plan 55 (the autopilot Board)`. Depends on Task 6 and
on Fred's answer at stop 3. No product code.

## 1. Fred's live check (shared with plan 38 Task 9 and plan 52's open live check)

Fred runs `run.bat` against his own service after `py -m console` restarts it (never by a session: the running service
on port 47770 is his). Widen to the Board. In order, and he says what he sees:

1. The list: Needs you pinned at the top across projects; one group per project; dashed observed chats; done days
   folded under Earlier. A running task shows its steps under its row.
2. Open a task that waits on a plan: the head (project eyebrow, title, pill, Now, cost), Confirm in the dock card,
   the box hint, the bar with icons and no ⋯ menu. Confirm. The task runs; the card goes.
3. A decision: the options, the default marked, Confirm. On `auto` the line "Console takes the default in N min".
4. A supervisor suggestion: Approve, Reject with a note from the box.
5. The finished task: the summary card, See the changed files, Accept. The pill says Accepted.
6. A step page: `← task`, ‹ ›, the four tabs, the chat as a thread, the task's card and bar under it.
7. The 400 px window: the session list and page as before, an observed chat's page with the new head (D13).
8. Windows text size 130 %: nothing clips, no horizontal scroll.

Each finding goes in a memory file `plan55-live-check-findings.md` (the plan 17 and 19 habit) and becomes a fix
commit before the close, or a line under README "Open" if Fred says later.

## 2. The close (the session that runs Task 7 applies these; anchored by quoted text)

- This folder's README line 3 `Status: written 2026-11-07, plan only ...` becomes
  `Status: built <date> (<first sha>..<last sha>), Fred's live check <date>.`
- PLAN.md: the plan 55 row's state cell becomes `built <date> (<shas>); live check <date>`; one History line
  `- <date> - Plan 55 built: the autopilot Board reads GET /api/task actions only ... <tests> tests OK.`
- PLAN.md plan 52 row: `Fred's live check and the web build of the locked UI (a later plan, D9) open` becomes
  `web build of the locked UI: plan 55`.
- CLAUDE.md, the Board line (plan 25): after `Plan 48: the Board also writes ...` add the sentence
  `Plan 55: the task page reads GET /api/task actions alone for what shows and what is enabled (no gate in app.js); a
  button posts the action's own post and body; GET /api/task also serves the typed prompt (read only).`
  Stage that one line only (other chats edit CLAUDE.md).
- `plans/38-*.md`: its open tasks 4 to 7 and 9 get `done in plan 55 Task N` or `dropped (plan 55 README section 3)`.
- `plans/52-workflow-autopilot/README.md` D9: `(a) a plan of its own after Task 6` gains `: plan 55`.

## 3. Run

The full suite `py -m unittest discover -s tests` (last good recorded in the README), `py -m tests.live_autopilot_check`,
`py -m tests.live_board_check`, `py -m tests.live_task_chat_check`. Commit with explicit paths; never stage
`console/__main__.py`.
