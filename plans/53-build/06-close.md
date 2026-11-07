# Task 6: close

Files: `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md`, this folder's README (the status line and the State column of section 9).
Commit boundary: `docs: plan 53 built, D1-D9 confirmed, BRAINSTORM D17` (stage only these lines; other chats edit the
same files).

1. `PLAN.md`: row 53's state becomes `code done <date> (D1-D9 confirmed; N tests OK, node --check clean); Fred's live
   check <open | done>`; one History line with the commits per task and the test count.
2. `BRAINSTORM.md` (D2): decisions table, one row `| D17 | Builds (2026-11-07) | an ordered list of sub-plans, each
   run as one task, advanced by the service only after the previous task is accepted, is not a task graph or a
   scheduler: no dependencies, no parallel items, no reordering at run time, no clock except one retry after a usage
   limit's reset; plan 53 |` (checked 2026-11-07: D16 is the last row, D17 is free); section 2, after the non-goals
   paragraph, one sentence: "Clarified by D16 (a linear step chain) and D17 (a linear list of sub-plans, plan 53):
   neither is a task graph or a scheduler."; one History line.
3. `CLAUDE.md`, one rule line under the Board line: "Builds (plan 53): `~/.claude/console/builds/<id>/`, an ordered
   list of sub-plan files run one task at a time through the existing Prep, planner and `create_task`; the build
   starts nothing else, never writes a sub-plan file, and moves on only after the item's task is accepted (Fred at
   `gated`; `build.acceptable` at `auto`); every build move goes through `Hub.build_lever` and the tick inside
   `advance`; `build.json` is written only through `paths.write_text_atomic` under `Hub.tlock`." And the Board's write
   contract sentence gains its build routes: "The Board also writes POST /api/build/preview (local, starts nothing),
   POST /api/build and POST /api/build/<start|stop|pause|resume|skip|continue|level|cap|delete>, and reads GET
   /api/build; the page keeps no build state in window.json; a build at `auto` makes its tasks task level `auto`
   (plan 53 D9) and never writes `supervisor_projects`."
4. `plans/49-planner-handover.md` and plan 52's README are untouched. The memory file `plan52-build-in-progress.md`
   is updated by whoever closes plan 52's live check; this plan adds `plan53-...` memory lines only for live-check
   findings (the existing `plan53-build-conditions.md` is updated to say Task 5 is built and the downgrade recipes are
   README 8.1).
5. README section 9 (Readiness): the State column is brought up to date in the same commit, so the next reader sees
   which preconditions are still open.
