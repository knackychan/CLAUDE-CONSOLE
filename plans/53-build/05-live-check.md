# Task 5: the headless acceptance script, then Fred's live check

Claude never starts a run on Fred's account (plan 24 Task 5's rule). The first part below is Claude's and uses a scratch
home and the fake claude, as plan 52 Task 7 did; the second part is Fred's, on a real project.

## Headless (Claude, before Fred's check; Tasks 1 to 3 built, Task 4 not required)

`tests/live_build_check.py` (`py -m tests.live_build_check [check numbers]`), in the style of
`tests/live_autopilot_check.py`: a scratch `CC_CONSOLE_HOME`, the fake claude, a worker thread ticking `poll_once` and
`advance`, the real HTTP routes, no paid provider. It drives the build through the routes because the page may not have
the build controls yet (the same reason plan 52 Task 7 drove Accept by HTTP). When Task 4 is built, checks 1 and 6 also
drive the page.

1. Gated, three sub-plans: New build (preview with a lint warning, Create), Start, the card, the card's Start, Confirm
   plan (the task's own gate), done, Accept, the next item's prompt lists the first, to `done`. The POSTs of the whole run
   are `/api/build/preview`, `/api/build`, `/api/build/start`, `/api/task`, `/api/task/confirm`, `/api/task/accept`.
2. Auto, two sub-plans with the project at `gated`: no click after Start; the tasks run at task level `auto` (D9); the
   build accepts each; the cap holds at a few cents and Raise cap goes on; a done wake is pending and the build waits for it.
3. Drift: `PLANNER-DRIFT-MAJOR` holds an auto build with the note; Continue starts it; `PLANNER-FAIL` holds an auto build
   (F19) and not a gated one.
4. The failure paths that need a restart (F1 to F4): a new Hub on the same scratch home mid-`preparing`, with a ready
   card, between `create_task` and the build's save, and mid-task; no second Prep when a card was saved; no second task.
5. The failure paths that need Fred's hands (F8, F13, F14, F16): Delete the item's task, rename the project folder, a
   second live build, Drop on a card.
6. 900, 400 and 340 px, dark and light, over the build row and page states of checks 1 to 5 (needs Task 4): no horizontal
   scroll, no page error.

Record: the check numbers, the seconds each took, `py -m unittest discover -s tests` count, `node --check web/app.js`,
and the fake-claude call counts that prove F1 and F3 paid nothing twice.

## Live (Fred): a real sub-plan folder of two or three small sub-plans, on a throwaway branch

Before it: the service restarted on the new code; Reset to repo copy on Models for `planner.md` and `design.md` (changed in
Task 2; `supervisor.md` and `design.md` also from plan 52); the folder passes the preview's lint warnings (or Fred has read
them); the cap on the New build form set to 60; plan 52's live check has passed (README section 9).

### Gated (D1 default)

1. Header menu, New build…: the project, the folder, the goal file; Preview lists the files in order with their
   titles and any lint warnings; untick one; Create. The row says `planned`; nothing runs; `builds/<id>/build.json` exists.
2. Start on the build page. The row says `build · 1 of 2 · preparing`; a card appears for the first sub-plan with the
   build line in its prompt, its Goal starting `Sub-plan 1 of 2 (...)`, the planner's scope note and, when it judged, the
   drift word.
3. Start on the card (the ordinary one). The task runs: design adopts the file (its plan.md Decisions name every
   departure as `Departs from <file>`), then waits at `plan ready: confirm` (the task's own gate at the project's
   `gated`); Confirm; code, verify. The build row follows the task's line.
4. The task's finish card. The build row says `needs you · sub-plan 1 done: Accept`. Accept. The second item preps by
   itself; its card prompt lists `- 1 <title>: accepted; files ...`.
5. On the second card, "Start, and run the rest automatically": the level switch on the build page shows `auto`; the
   task starts at task level `auto` (its menu says auto) and does not stop at a plan confirm.
6. After the last Accept (or the build's own accept at auto): the row says `done · 2 sub-plans · $x`; the page's Done
   section lists the files and the open questions; `build.jsonl` reads as README 4.3.

### Auto and the holds

7. A new build at `auto` with the cap set to a few cents: after item 1 the build holds on `cap: ...`; Raise cap; it
   goes on.
8. Edit the second sub-plan file so it contradicts the code item 1 wrote (name a function item 1 renamed); at `auto`
   the planner should answer `major` and the build hold with the note; Continue starts it anyway; or Skip. Note how the
   drift word compares with what happened (README 8.1: the evidence for D3).
9. Stop while a task runs: the task is stopped (its own page says so), the build `stopped`; Start on the build: the
   same item continues through the task's Retry; the build does not start a second task for the item.
10. Pause after this sub-plan: the build waits `paused after 01` once the item closes; Resume.
11. Delete a build that is done: its tasks stay on the Board.

### Failure paths worth one real try (README 4.9)

12. Restart the service while a card waits (F2): the card is back on the strip, nothing was paid again (the console log
    shows `recovered`).
13. Delete the task of a running item from the Board (F8): the build says `task deleted`; Continue preps again.
14. Rename the project folder while a build waits (F13): the row says `project: ...`; put it back and the build goes on.
15. Start a second build in the same project while the first is running (F14): refused with the first's title.
16. If the night allows it: leave an `auto` build running past a usage limit (F5) and read `build.jsonl` in the morning for
    `retry by the build after the limit reset`.

## What to note

Every surprise goes to the plan 53 findings memory (not fixed in this plan): a line Fred would word differently, a
state the row named wrongly, a move the page offered that the service refused, the cost per sub-plan against README
section 6, how often the planner left `drift` out, and whether a design step's plan.md ever failed `plan.check` (the
evidence for README 8.1's recipes).
