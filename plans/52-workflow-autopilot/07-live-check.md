# Task 7: checks and close

## Headless (Claude, fake claude, scratch `CC_CONSOLE_HOME`, as plans 42 and 48)

1. Type a prompt, Enter, Start on the card with the project at `gated`: the chain runs scout, design (PLAN-OK),
   waits `plan ready: confirm`, one Confirm, then code and verify PASS with no other click; the row ends
   `done · 4 steps · $x`; the finish card lists the steps and files; Accept moves it to Done. Exactly one supervisor
   pass (the done wake) in supervisor.jsonl.
2. The same at `auto` with the fake word `DECIDE-NAME` on the code step: the decision card shows two options; with a
   fake clock past `decision_timeout_s` the default is taken, logged, and plan.md Decisions carries it.
3. A crash on step 03 twice: the chain retry, then stuck, one sonnet wake, a Retry card with a note; Approve runs
   attempt 3.
4. A task started at `suggest`, switched to `auto` at a hold: the standing card dispatches; no "Paused" note.
5. 900 / 400 / 340 px, dark and light, reduced motion: no horizontal scroll, no console error (the UI chat's
   rendering, checked here only for the service fields).

Record: `py -m unittest discover -s tests` count, `node --check web/app.js`.

## Live (Fred)

One real prompt in ARTCOUSTIC-AUDIO-REPORT at `gated`, from Enter to Accept: the plan confirm is the one click
unless a decision card appears. Then the same prompt as task 06c2 again, to compare: cost, clicks, time.

## Close

- `PLAN.md` row 52 state and History line (renumbered from 49 at `8d4c624`); `BRAINSTORM.md` 7.6 gains one paragraph: "Plan 52: the chain is the run
  loop; the supervisor handles exceptions; levels gated / auto / suggest / off; decision cards; the finish card".
- `plans/44-supervisor/README.md` section 1: a note that D7 (supervised intake) is replaced by plan 52 Task 1.
- `plans/48-three-moments.md` section 2: D6 widened to any done task (Reopen).
- `plans/49-planner-handover.md`: already marked replaced in Task 1 (D7); `plans/50-supervisor-settings.md`: a note
  that Task 5 added `gated` and made it the default; `plans/36-next-step/README.md`: Stage B re-read against the
  built plan 52 (D8), as its own check, before Fred closes it.
- The web build of `design/rework/locked/workflow-autopilot.html` is its own plan, written after Task 6 (D9).
