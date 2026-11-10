# Decisions, 2026-11-08 (Fred, decision session)

Written for the build prompts (A, B, 0, 1, 2 in `plans/next-agent-prompts-2026-11-08-plan59.md`): paste this list.
One line per answer, in the order asked. "open" means Fred parked it.

## Gate facts

- Plan 52 live check: not done (Fred, 2026-11-08). Row 52 stays open.
- Service restarted on plan 54 (`c0793b3`): yes (Fred, 2026-11-08). Recorded in PLAN.md row 54.

## Plan 52 live check, first run (Fred, 2026-11-08): stopped, fix first

Task `20261108-203300-f400` ("what do we have pending", ARTCOUSTIC, gated, one scout step) went stuck; Fred did not
retry ("we need to fix that first"). The 06c2 rerun was dropped: its prompt is done and ARTCOUSTIC has uncommitted
work in `src/core/settings.ts`.

- F1: `fills.balance` (token mode) sent a rule "haiku/low" scout to codex, then its chain retry to opencode, which had
  no executable (`exe` empty, "opencode: not found"); the attempt died in 6 s. Fred has since turned opencode off.
- F2: codex wrote a full HANDOFF but put `END HANDOFF` at the end of the last text line, not on its own line;
  `tasks.parse_handoff` rejected it ("HANDOFF has no END HANDOFF line"), so a good note was lost.
- F3: the supervisor digest says "retries left 1" (supervisor retries, `server.py` 1979/2101) while the chain's own
  retry is spent (`step.retries`); the pass flagged the conflict itself.
  Fred, 2026-11-08: replace the reply markers with a `handoff.md` file the step writes (chosen over a tolerant
  parser). A contract change of plan 23, so it gets its own plan (next free number, 60 unless taken), not the fix
  session. The fix session does F1 and F3 only.
- F4: the stuck card offers Dismiss only; Retry is in the task menu (evidence for plan 55 D3, plan 59 D1).

F1 retry routing, Fred, 2026-11-08: Return the chain's automatic retry after a non-Claude harness failure to the
rule's own Claude rung. A retry should not try a second untested harness. Keep Fred's explicit Retry choices.

## Plan 58

| Decision | Choice | Reason |
|---|---|---|
| D1 when to build | (b) build now on scratch services before plan 52's live check | corrected 2026-11-09; supersedes (a); live check remains open |
| D2 passes at the upgrade | (a) on, $0.20 a pass, $1.00 a day | |
| D3 pass folder | (a) <home>/super | |
| D4 watchdog signals | (b) all of design 3.6 now (git read per sweep); build writes the added signals | |
| D5 replay | (a) slice 3 | |
| D6 sort by hand | (a) POST /api/super sort | |
| D7 Usage page | (a) own block | |
| D8 log growth | (a) rotate at 5 MB | |
| D9 settings in the window | (a) config.json; card in plan 59 | |
| D10 STOP without options | (a) always forwarded | |
| D11 act and order | (a) slice 3 | |
| D12 JEV | (a) shadow evaluation later, own plan | |

Correction, 2026-11-09: D1 (b) permits plan 58 Tasks 1 to 6 to build and test on scratch services now. Plan 52's
live check remains open and precedes plan 58 Task 7. No production restart or paid acceptance is authorized by
this build exception. D2 to D12 are unchanged.

## Plan 55

| Decision | Choice | Reason |
|---|---|---|
| D1 task order | (a) head, action surface, then the rest | |
| D3 unserved buttons | (b) Task 0 in Hub.actions (the routed rows of 4.2); Edit steps/prompt out | F4: stuck card had only Dismiss |
| D14 unshown states | (a) section 5 table, screenshots at Stop 1 | |
| D2 button words | (a) ACT_COPY / TIP in the page | |
| D4 level switch | (a) two words, plus the current one | |
| D5 Reject/Retry notes | (a) the message box | |
| D6 spend figure | (a) spend only | |
| D7 Prompt section | (a) read field prompt | |
| D8 Risky chip | (a) ink | |
| D9 status marks | (a) plan 21 sprites | |
| D10 list beyond the mock | (a) per project (inner grouping of plan 59's roll-up) | |
| D11 needs-you under a scope | (a) always all projects | |
| D12 step page | (a) four tabs, Add step from here kept | |
| D13 observed page | (a) new look, levers route | |

## Plan 59

| Decision | Choice | Reason |
|---|---|---|
| D10 Accept items | (a) in the queue | |
| D1 unserved one-click buttons | (b) retry_up, run_instead via 55 Task 0; hint_dismiss via 59 Task 0 | settled by 55 D3 b; Let it continue added |
| D11 New work box | (a) second entry, both visible | review variant not taken |
| D2 batch answers | (a) accept only | |
| D3 observed chat card | (a) read-only page | |
| D4 message to the super agent | (a) note for the next sort | |
| D5 Since you looked | (a) code-known events | |
| D6 edit orders | (a) in the window | |
| D7 rest of the list | (a) | settled by 55 D10 a |
| D8 queue and scope | (a) | settled by 55 D11 a |
| D9 header and tray word | (a) for you in both | |
