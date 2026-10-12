# Task 6: Fred's live check (CONTENT MANAGER, real claude)

> Claude cannot start auto-mode runs (its classifier refuses), so this task is Fred's. Record the outcome in
> PLAN.md History (Task 7). Expected cost: a three-step task with scout on haiku, code on sonnet, verify on opus,
> under about 3 USD at list prices; the verify step's `--max-budget-usd 3` caps each step.

Before: restart the tray (`py -m console`) so the service serves `tasks` and the new routes; `config.json` keeps
its keys (the five new ones take their defaults).

- [ ] 1. **Slider.** Type a task, pick `high` on the slider, reload the window: the pick is still `high`
      (`window.json` `effort`). Put it back to Auto.
- [ ] 2. **Prep with steps.** Enter a request that has a reading part and a writing part (for example: "find
      where the calendar export is built, then add a CSV export next to it with a test"). The card lists steps
      (scout, code, verify expected). Edit one goal. Run as task.
- [ ] 3. **Chain.** The list shows the task under Working with `step 1 / 3 · scout · haiku low`; its session row
      carries the `step 1/3` tag; the Task page shows the chain. When step 1 ends: `steps/01-scout.md` exists
      under `~/.claude/console/tasks/<id>/` with the four headings; step 2 starts on sonnet/medium by itself;
      step 3 on opus/medium. The verify's `VERDICT:` line decides: PASS -> task Done; FAIL -> a fix on sonnet/high
      and a second verify, with a new line in `routing-misses.md` tagged `CONTENT MANAGER - code`.
- [ ] 4. **Bad handoff.** Start a one-step task whose goal says "do not write the HANDOFF block" (through a
      `code` step with an empty edit). The step ends, runs once more with the retry sentence, then the task is
      Stuck with `(after one retry)`; Retry starts it again.
- [ ] 5. **Stop and Retry.** Stop a running step from the Task page (two clicks): the stream shows the interrupt,
      the task is Stopped, owner fred; Retry starts the step again as a new session.
- [ ] 6. **Question.** A step that ends with `STOP: <question>` puts the task on Waiting; answer on the session
      page; the chain goes on after the answer's turn.
- [ ] 7. **Fable.** Set `fable` on a step of a card: the card says it may bill credits; the task waits on
      `confirm Fable`; Confirm starts it (or Stop it before to spend nothing).
- [ ] 8. **Pause.** Pause while a step runs; when it ends nothing starts; Resume starts the next step.
- [ ] 9. **Nothing outside the data folder.** `git status --short` in CONTENT MANAGER shows only what the steps
      edited; no `.claude/tasks` or note files in the repo; `~/.claude/console/hook-errors.log` has no new line.
- [ ] 10. **Plain Run unchanged.** A plain Prep + Run and a Run raw still work with the slider on Auto.
- [ ] 11. **Older rung.** Run raw with `claude-haiku-4-5` picked on the card: the row shows `haiku 4.5`, the
      result's `modelUsage` names it; then look at `/usage` in a terminal session before and after a
      `claude-opus-4-6` run to see whether the plan counts it with Opus 5.5 or apart (the open fact of decision 17).
- [ ] 12. **Storage line.** The Usage page foot shows the folder size by subfolder; `runs/` is the big one.
- [ ] 14. **Brief.** After step 1 of the item 3 task the row says briefing for a few seconds, then
      `steps/01-scout.brief.md` exists, shorter than the raw note, four headings; step 2's Chat shows the brief in its
      first prompt and not the raw note.
- [ ] 13. **Clear.** The done task of item 3 has only task.json, chain.jsonl, prompt.md and its last note left, and
      its step streams are gone from `runs/`; its step rows still open and their Chat reads the transcript. Clear
      on a stuck task removes its folder and its row.

Differences from the plan go into PLAN.md History as one line each (Task 7), and into the code only through a
plan change.
