# Plan 41: Stop, Retry and Mark step done on the current step

> Master: [../PLAN.md](../PLAN.md). Rules: [../CLAUDE.md](../CLAUDE.md). Extends plan 33 and 40 (Retry), plan 29 (chat tasks)
> and plan 39 (the dock). Start state: `6e54298`, branch `claude/brainstorm-task-actions`.

Status: code done 2026-10-17 (791 tests OK, `node --check` OK); Fred's live check open. Decisions answered by Fred 2026-10-17
(section 2).

## 1. What happened (task 20261015-155327-be2f)

A chat task showed "writing" for 42 hours. Its session had ended on 2026-10-15; at 10:06 on 2026-10-17 the task went
`done -> running` ("the chat goes on") with no run, no session row and the project not on the allowed list. Every
lever was off: `task_levers` answers `a chat: use its session's levers` for Stop, the session has no row for
`Hub.levers` to answer, Mark done waited on a pending question, Delete refuses a running task. Nothing could end it.

For a normal task the three actions exist but sit in two places: Stop and Retry in the task page's head, Finish task
(the whole task) at its foot. A stopped step's own page showed no action but Open chat, and there was no way to accept
a stopped step and go on.

## 2. Decisions (Fred, 2026-10-17)

- Mark step done: the step turns done with no handoff check and the chain goes on (manual task: waits at `choose next
  step`; automatic task: the next step starts after a brief built from the step's chat tail; last step or a chat: the
  task is done).
- Scope: the current step only. A done step keeps Add step from here (plan 39); Retry never reruns a finished step.

## 3. What changed

| Where | Change |
|---|---|
| `tasks.fred` | new lever `stepdone`: task `stuck` or `stopped` and the current step `failed`; step -> done (`marked done by Fred`, `accepted` stamp), `last_good` = it, then the task is done (chat, or last automatic step), waits (manual) or runs (automatic) |
| `Hub.task_levers` | new key `stepdone` (`_stepdone_off`; off with the project's reason when the chain would start the next step and runs are off there); a chat task's `stop` is allowed while its step runs |
| `Hub.task_lever` / `_accept_step` | for `stepdone`: a code-built six-heading note when the step wrote none (its goal, the tail of its chat, `ACCEPT_TAIL` 3000), `notes.md`, the facts; an automatic task then briefs (`start_brief`) and `advance()` starts the next step |
| `Hub._next_source` | an `accepted` step is not refused for its interrupted run, so Add next step works after Stop and Mark step done on a manual task |
| `Hub._chat_tick` | a chat Fred closed (`owner` fred, task done) stays done until a run is live in its session; a new turn sets `owner` back to `window` |
| `POST /api/task/stepdone` | the lever's route, same body as the other task levers |
| `web/app.js` `stepButtons`, `inspTask` | the current step's dock: Stop (not on a chat whose turn is over), Retry and Mark step done (a failed current step); the task head also has Mark step done; two clicks to arm it |

## 4. Not in this plan

Retry on a chat task (a chat has no step prompt to run again: Continue in its session does that, and a chat task with
runs off cannot start one); Retry of a finished step; a model and note form on the step page (the task page's stuck box
keeps it; the step's Retry is the plain one on the model the service picks).

## 5. Live check (Fred)

1. Restart the service when no task runs. Task 20261015-155327-be2f: Stop on its step, then Mark step done; the task
   leaves Working and Delete turns on.
2. A task with two or more steps: Stop the running step, Mark step done, the next step starts (automatic) or the task
   waits at `choose next step` (manual) and Add next step works.
3. Retry from the step page on a stopped step.
