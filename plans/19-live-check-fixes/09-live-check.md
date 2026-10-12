# Task 9: Fred's live check (CONTENT MANAGER, real claude)

> Finding C2. Fred runs every run; Claude never starts one and never POSTs `/api/run`, `/api/task` or `/api/prep`.
> Claude may guide, read `~/.claude/console/` and the screens, and write the outcome into PLAN.md History.

Before: restart the tray (`py -m console`) so the service serves Tasks 1 to 7. `config.json` keeps its keys.

Cost: items 1 to 8 cost what plan 17's check cost per task (about 0.5 to 1.5 USD each). Item 9 (verify FAIL) runs
code, verify on opus, fix on sonnet/high and a second verify on opus: about 3 USD. Item 10 runs Fable on usage
credits. Fred decides which to run.

- [ ] 1. **Goal kept.** Prep a request with a reading and a writing part; add ten words at the end of a step goal;
      Run as task: task.json has the whole goal.
- [ ] 2. **No steps from Prep.** A request Prep answers with `steps: []`: the card shows the hint and `+ step`;
      add a code row: the verify row appears, Run as task shows.
- [ ] 3. **Folded list.** While the task runs, the list has one task row and no step session rows; the header's
      `N need you` counts a waiting task once.
- [ ] 4. **Brief.** After each step: the chain line says `brief: A -> B words` with B smaller than the raw note
      (plus the earlier brief for step 2 on); no `error_max_turns`; an open question stays under Open questions.
- [ ] 5. **Pause.** Pause while step 1 runs: when it ends, step 1 is done at once (note, brief, chain line), the
      Task page says `Paused: step 1 ended`; nothing starts; Resume starts step 2.
- [ ] 6. **Costs.** A step that needed a retry shows two tries, the cost is the sum; a stopped step shows its
      cost once the stop lands.
- [ ] 7. **Clear.** Clear a task that had a retry: `runs/` keeps no stream of any of its sessions.
- [ ] 8. **Navigation.** Task page -> Open -> `←` returns to the Task page; the pager says `step K of M`; a step
      older than a day opens its Chat from the transcript (if one exists by then).
- [ ] 9. **Verify FAIL (left from plan 17).** A task whose goal makes the verify fail (for example, the code step's
      goal asks for a test that cannot pass): the verify says `VERDICT: FAIL`, a fix row and a second verify are
      inserted, `routing-misses.md` gets a line tagged `CONTENT MANAGER - code`.
- [ ] 10. **Confirm Fable (left from plan 17).** Dropdowns show `fable 5.1`; a step on fable puts the task on
      Waiting with `Confirm to use Fable 5.1`; on the card, plain Run on fable asks for the second click. Stop it
      before it runs to spend nothing, or confirm once on a one-line request.
- [ ] 11. **Project in sight.** The Prep card names its project at the top and above the buttons; changing the
      project marks the chip for a few seconds.
- [ ] 12. **Draft.** Type, close the window, reopen: `Draft kept from last time` with Clear; typing replaces it.
- [ ] 13. **Nothing outside the data folder.** `git status --short` in CONTENT MANAGER shows only what the steps
      edited; `~/.claude/console/hook-errors.log` has no new line.

Differences go into PLAN.md History as one line each, and into the code only through a plan change.
