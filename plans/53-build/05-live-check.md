# Task 5: Fred's live check

Claude never starts a run (plan 24 Task 5's rule). Fred runs this on a real project with a sub-plan folder of two or
three small sub-plans (a throwaway branch), the service restarted on the new code, the kind files copied with Reset to
repo copy (planner.md and design.md changed in Task 2).

## Gated (D1 default)

1. Header menu, New build…: the project, the folder, the goal file; Preview lists the files in order with their
   titles; untick one; Create. The row says `planned`; nothing runs; `builds/<id>/build.json` exists.
2. Start on the build page. The row says `build · 1 of 2 · preparing`; a card appears for the first sub-plan with the
   build line in its prompt, the planner's scope note and, when it judged, the drift word.
3. Start on the card (the ordinary one). The task runs: design adopts the file (its plan.md Decisions name every
   departure as `Departs from <file>`), code, verify. The build row follows the task's line.
4. The task's finish card. The build row says `needs you · sub-plan 1 done: Accept`. Accept. The second item preps by
   itself; its card prompt lists `- 1 <title>: accepted; files ...`.
5. On the second card, "Start, and run the rest automatically": the level switch on the build page shows `auto`; the
   task starts.
6. After the last Accept (or the build's own accept at auto): the row says `done · 2 sub-plans · $x`; the page's Done
   section lists the files and the open questions; `build.jsonl` reads as README 4.3.

## Auto and the holds

7. A new build at `auto` with the cap set to a few cents: after item 1 the build holds on `cap: ...`; Raise cap; it
   goes on.
8. Edit the second sub-plan file so it contradicts the code item 1 wrote (name a function item 1 renamed); at `auto`
   the planner should answer `major` and the build hold with the note; Continue starts it anyway; or Skip.
9. Stop while a task runs: the task is stopped (its own page says so), the build `stopped`; Start on the build: the
   same item continues through the task's Retry; the build does not start a second task for the item.
10. Pause after this sub-plan: the build waits `paused after 01` once the item closes; Resume.
11. Delete a build that is done: its tasks stay on the Board.

## What to note

Every surprise goes to the plan 53 findings memory (not fixed in this plan): a line Fred would word differently, a
state the row named wrongly, a move the page offered that the service refused, the cost per sub-plan against README
section 6.
