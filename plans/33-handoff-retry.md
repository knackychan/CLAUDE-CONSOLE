# Plan 33: a rejected handoff says why, and Retry takes a note

> Context: [PLAN.md](../PLAN.md), plan 23 README (the six-heading HANDOFF block contract, unchanged).

## Goal

Task 1015-0b18 step 03 went STUCK with "no HANDOFF block (after one retry)" while its chat showed a complete block:
both attempts left out the closing `END HANDOFF` line. The service needs both markers; the window drew its chip from
the start marker only; the retry prompt named no marker, so the model repeated itself.

## Decisions (Fred, 2026-10-15: fixes 1, 2 and 4)

1. The check names the missing marker: `tasks.missing_block(text)` gives `HANDOFF has no END HANDOFF line` when a
   `HANDOFF` line stands without its end, else `no HANDOFF block`. The retry prompt and the stuck why carry it.
2. The window's step chip is red (`.hchip.bad`) with "no END HANDOFF line: the service rejects it" when the turn
   is done, shorter than `runs.CHAT_TEXT` (4000, a longer reply is cut and proves nothing) and has no end line.
3. Retry takes a note: `POST /api/task/retry {task, note}` (note trimmed, at most `NOTE_MAX` 2000 characters, Retry
   only). `tasks.fred` stores `task["retry_note"]`, and `task["retry_why"]` (the last attempt's why) when the task was
   stuck; `start_step` pops both: the prompt reads "... ended without a handoff: <why>. Start again ... / <you> adds
   for this retry: <note>"; received.md lists the note; the chain line reads `retry by Fred: <note>`.
4. A stuck task's box in the Board shows a textarea and the Retry button (the header Retry is hidden then).
5. Not decided here: accepting a block with no END line (the contract stays strict); editing a step's goal.

## Files

`console/tasks.py` (missing_block, step_prompt note, fred note), `console/server.py` (NOTE_MAX, check, start_step,
task_lever), `web/app.js` (handoffSplit, taskAct, inspTask), `web/style.css` (.hchip.bad),
`tests/test_tasks.py`, `tests/test_server.py`.

## Done check

`py -m unittest tests.test_tasks tests.test_server`: new asserts pass. Known failures not from this plan: four
`HarnessServerTest` tests (models.json on this machine) and `test_bulk_delete_takes_finished_tasks_only`, which is
timing-flaky on the unchanged repo too. Live check: stuck task, type a note, Retry; step prompt shows the note.
