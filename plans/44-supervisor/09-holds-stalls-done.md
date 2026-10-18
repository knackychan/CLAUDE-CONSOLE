# Task 9: remaining boundaries, plan holds, stalls and automatic done

> Contract: [README.md](README.md) 4.2, 4.4; brainstorm D2/D5/D6/D12/D13. Lands on Task 8.

**Files**
- Modify: `console/server.py` (`_ended`, `_replan_done`, `_brief_done`, `task_lever`, `tick`,
  `_supervisor_tick`, `_supervisor_done`)
- Modify: `console/supervisor.py` (trigger classification/model and force-suggest policy)
- Modify: `tests/test_supervisor_server.py`, `tests/test_supervisor.py`

## 9.1 Full backend wake matrix

| Original transition | Producer | Result |
|---|---|---|
| Manual boundary after any non-chat step | _ended returning manual | Debounced wake after saved files |
| Manual task stepdone -> choose next step | task_lever after accept files/commit | Wake; acceptance itself remains Fred-only |
| Manual chat step ends | _chat_tick | No turn-by-turn wake; a later non-chat manual boundary can wake |
| Into stuck, including failed replan | existing Task 5 hooks | Once per real transition; sonnet for this pass only |
| Plan ready/oversize or replan proposal | _ended / _replan_done | Hold wake; confirm/keep only as live gates permit |
| Automatic task done | _brief_done after final brief save/optional stream cleanup | One force-suggest wake, only with room_after > 0 and physical room |
| Live owned Claude task step stalled | existing tick | One force-suggest wake per attempt after threshold |
| asks / Plan gap, pace/Fable hold, paused/off, briefing/guidance | existing gates | No new model call; deferred earlier events stay held where applicable |
| Same-state bookkeeping, automatic retry 1, Prep/Review, external/chat-only | any | No wake |

**R1:** extend Task 5's shared live/recovery classifier in this commit, not only the callbacks. The first
advance must recover an unclaimed current plan-ready/oversize/replanned hold or automatic-done transition
after shutdown during debounce. For done with unfinished briefing, retain/defer the candidate until final
brief completion; the callback and recovery scan must deduplicate the same original done event. Enforce
room, pause/off, questions and all normal gates. Never recover superseded historical holds or replay a
consumed event. Stalls stay on tick's attempt identity, not fabricated chain transitions. Preserve the
specific approved stalled-stop follow-up across restart from its durable dispatch outcome and closed
attempt; ordinary Stop must still produce no follow-up.

At automatic done, terminal no-decision/wait/rejection/approval consumes that done event too. A stream-cleared
task still has its saved handoff/brief/facts; never reopen a transcript. If task_max_steps leaves no room, no
paid 'anything left?' check. Any proposed add still needs next_sources and request_next; do not convert an
automatic chain to manual behind the gate. A valid approved Add step uses the gate's existing reopening path.

Plan holds must be matched exactly (plan ready, oversize format, replanned prefix), not any string beginning
with 'plan'. A pending guidance exception that permits Fred's queued-message Confirm does not permit the
supervisor. Manual Confirm returns to choose-next per Task 7; automatic Confirm/Keep uses existing chain
progression, worker spend attribution and launch checks. If confirmation itself creates a new real manual
boundary, it may enqueue that boundary once; no supervisor audit line is its own trigger.

## 9.2 Stall detection and D6 precedence

In Hub.tick, sample existing state/session rows outside Hub.lock-to-tlock nesting, then under tlock match
current task/session/attempt. Require Claude harness, task worker, actual RunManager ownership/live process,
session state stall, and `now - last_ts >= supervisor_stall_s` (1800 seconds of total inactivity, not another
1800 after the 600-second state threshold). This is observation on the existing 15-second tick, no timer.
Key by step/session/attempt so restarts and repeated ticks cannot spend repeatedly for the same attempt.
Record sonnet selection once for a stuck/stalled wake; there is no second escalation pass, Opus or Fable.
Other harnesses keep their existing timeout/recovery behavior; the supervisor never stops their capless runs.

D6's explicit report-only choice overrides the brainstorm's generic auto-stop table and 'auto only' shorthand.
Even mode auto yields a pending 'Stop and retry?' card. Approve invokes only task_lever('stop'), preserving
RunManager's existing stream interrupt on Claude. Never kill a process or combine stop+retry into one decision.
After that specific approved stop has closed the attempt and costs are filed, enqueue a distinct
stalled_stop follow-up event. Its retry, with note 'the earlier attempt stalled for 30 min', is also forced
suggestion in every mode; it needs another Approve. Fred's ordinary Stop does not cause this follow-up.
If pending guidance/another human action intervenes, hold/invalidate the advice using Tasks 6-7.

## Tests first

- `test_each_real_boundary_and_hold_wakes_once`: parameterized source methods, original transition ids,
  correct timing after files; code/scout boundaries join the original design/verify wake set.
- `test_questions_fable_pace_and_guidance_do_not_wake_or_dispatch`: repeated ticks/advances, live gate
  changes and Fred-only queued-confirm exception all produce zero supervisor effects.
- `test_manual_confirm_and_automatic_keep_use_shared_progression`: no ghost running manual task,
  no tail rebuild, existing automatic chain still advances through start gates.
- `test_done_wakes_after_final_brief_only_and_is_always_suggest`: brief fallback/as-is/paid paths, restart,
  stream cleanup, no room, rejected done suggestion; repeated advance/brief callbacks do not repeat it.
- `test_restart_before_claim_recovers_holds_and_done`: restart during debounce for plan-ready, oversize,
  replanned and automatic done; assert original event identity and one pass. Include unfinished final brief,
  pending guidance, no room, superseded boundary and already consumed controls. After brief completion,
  recovery and callback together still yield one wake, always suggest for done.
- `test_restart_after_approved_stalled_stop_preserves_followup`: durable approved stop plus closed attempt
  yields one forced retry suggestion across restart; claimed follow-up and ordinary Stop yield no duplicate.
- `test_stall_threshold_and_one_wake_per_attempt`: at1799 none/1800 one, revived session no new wake for
  same attempt, new Retry attempt can wake; paused/off/question/external/non-Claude sessions excluded.
- `test_stall_stop_and_followup_retry_each_need_approve`: auto mode cannot stop; first Approve calls only
  task_lever stop, no direct RunManager action; new retry suggestion cannot run until second Approve.
- `test_stuck_model_is_one_sonnet_pass_without_escalation_loop`: error/invalid sonnet result terminal;
  known cap/provider limit refuses admission instead of trying another model.

## Steps and acceptance

- [ ] 1. Add transition/stall tests red with fake clocks and barriers, no wall-clock waits.
- [ ] 2. Expand explicit hooks and tick observation; preserve D6 report-only priority in code comments.
- [ ] 3. `py -m unittest tests.test_supervisor tests.test_supervisor_server tests.test_state tests.test_task_messages tests.test_server`;
      full suite. Commit: `feat: supervise plan holds and report task stalls (plan 44 backend T9)`.

**Drift guard:** no model-generated question answers, persistent agent, separate clock or automatic Stop/Retry pair.
