# Task 7: Close the plan

> After Task 6. Docs only; stage only these lines (other chats edit the same files).

- [ ] 1. `BRAINSTORM.md`: add row **D16** to the decisions table: "Task chain (2026-10-12): a linear step chain
      under `~/.claude/console/tasks/<id>/`, advanced by the service when a step's handoff checks out, retried once
      from the last good note, then stuck; not a task graph or a scheduler. Opus thinks, Haiku reads, Sonnet
      writes; Fable only on Fred's confirm; one effort slider for the whole task (`plans/17-tasks/`)". Add one
      sentence to section 2 after the list: "A linear step chain (D16) is allowed; branches, parallel steps,
      queues and more than one retry are not."
- [ ] 2. `CLAUDE.md` Rules: add "Tasks: a linear chain under `~/.claude/console/tasks/<id>/`; every step is one
      fresh `claude -p` with the Agent tool removed; a step starts only through `server.Hub.task_levers`; the
      service writes every file in a task folder, never the model; code never picks Fable."
- [ ] 3. `PLAN.md`: row 17 state to `done <date>`; one History line per task placed (tests count, what differed
      from the plan, Fred's live check outcome); row 18 stays `to write` until plan 18 is written.
- [ ] 4. This folder's `README.md`: a `## State` section at the end: placed on <date>, N tests OK, what the live
      check changed.
- [ ] 5. Commit: `docs: close plan 17 (task chain), D16, CLAUDE.md task rule`.
