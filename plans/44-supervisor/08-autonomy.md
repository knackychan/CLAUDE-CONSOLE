# Task 8: automatic dispatch within step, retry and money limits

> Contract: [README.md](README.md) 4.2, 4.5. Lands on Task 7; this commit first activates auto mode.

**Files**
- Modify: `console/supervisor.py` (`policy`, new `auto_reason`, FAIL-lineage and accounting helpers)
- Modify: `console/server.py` (`_supervisor_tick`, `_supervisor_done`, `_supervisor_dispatch`,
  `start_step`, `sync_costs`, human-window bookkeeping)
- Modify: `console/usage.py` only for fixes to existing reservation helpers exposed by tests
- Modify: `tests/test_supervisor.py`, `tests/test_supervisor_server.py`, `tests/test_usage.py`

## 8.1 Authority and attribution

`supervisor.auto_reason(decision: dict, task: dict, policy: dict) -> str`: empty only if the current auto
policy may execute that action; otherwise the reason for a suggestion (not an override of check/gates).
Enable add/confirm/keep/retry/finish only. stepdone, stop and over-cap decisions remain suggestions; answer
remains refused/escalated. Neither confidence nor a configured replan_auto changes supervisor authority.

Count an add slot once at durable reservation, including held/failed reserved steps; failed validation with
no effect consumes no slot. Track supervisor retry intent before a possible launch; uncertain intent keeps
its allowance consumed. Include all supervisor-caused worker attempt costs in current work_usd: retries,
confirm/keep releasing an automatic continuation and subsequent automatic steps in that continuation.
Recheck work budget before each such launch in start_step, without changing ordinary Fred-owned chain
behavior. Attribution must survive an inherited request_next reservation, reloaded task dict and restart.
An existing running attempt never gets force-stopped just because the next-launch threshold was reached.

FAIL lineage: supervisor repair code sourced from FAIL step N consumes retries['N']; save that lineage on the
reserved code step and its verification. A second verify FAIL in that lineage escalates with both verdict
details; it cannot get another repair through source-switching or scout/chat followed by code. Direct Retry
of an attempt has its own per-step allowance on top of the existing chain retry. A real Fred act resets the
supervisor window; it does not rewrite the chain's own retries or historical audit.

## 8.2 Spend admission and durable daily accounting

Own model admission checks task/day total plus all active reservations under tlock, reserving remaining
allowance before launching the subprocess. Parallel>1 cannot each spend the same remaining day balance.
Settle actual costs once; unknown cost retains reservation, no automatic refund/retry. Error/overrun results
cost money too. Zero remaining means no subprocess. Day key is usage.day_of(claim time); keep it stable
across midnight and complete into the admission day's reserved allowance; new-day projections show their
actual recorded day explicitly. No host timezone changes are introduced.

Reuse Task 2's usage.load_supervisor/reserve_supervisor/record_supervisor and Task 5's own-pass admission;
do not add another spend ledger. Supervisor identities survive deletion/restart and settle exactly once;
replay in Task 11 gets distinct marked identities through the same running Hub. Existing days/other/seen
keys stay preserved. An unreadable/unwritable ledger refuses model admission.

The task audit remains the detailed decision record; reconcile missing daily records from its durable claim/
result without double counting. Write the daily reservation and task claim before launching. Keep a durable
reservation on either partial write and show a hold for human inspection; do not silently reclaim it.
Settlement failure blocks further launches until reconciled. Full Delete/prune cannot erase the daily cap;
late completion of a deleted task settles this ledger without recreating the task. Do not cap or erase actual
reported overrun costs. Task 11 only exposes these existing records in Usage.

## Tests first

- `test_only_auto_mode_dispatches_eligible_action`: suggest/off/auto table; stop/stepdone never automatic.
- `test_fourth_auto_step_is_suggestion_and_human_action_resets_window`: first three reserved, fourth not
  dispatched, failed/held reservations not free slots; restart retains count, internal lever calls don't reset.
- `test_task_max_steps_caps_supervisor_only`: room_after and physical length enforced at exact boundary,
  including verify/fix and branches from older sources; Fred's manual Add step still works beyond that cap.
- `test_retry_allowance_and_second_fail_escalate`: direct retry once; FAIL-code-verify FAIL cannot add another
  repair, both details surfaced; a different source/kind cannot launder the failed lineage.
- `test_work_cost_includes_attempts_live_updates_and_confirmed_chain`: all charged once; >=work limit starts
  nothing else; old-epoch completion cannot leak into newly reset window; no ordinary-chain regression.
- `test_task_day_zero_and_inflight_money_caps`: limits at/below/above; two tasks competing under tlock;
  parallel reservations, midnight, invalid/unknown cost, retained full overrun and no next call.
- `test_failed_pass_spend_and_ledger_survive_restart_delete_and_corruption`: priced is_error/bad schema,
  timeout reservation, append/settlement failure, deletion during pass; no free budget after recovery.
- `tests/test_usage.py`: concurrent history/add_other/supervisor writes preserve all sections; settlement
  idempotent; old replayed log identity cannot add twice; unreadable file is never overwritten as empty.

## Steps and acceptance

- [ ] 1. Add cap and ledger tests red before enabling auto. Money tests use finite fixtures and fake clocks.
- [ ] 2. Implement spend helpers/attribution, then enable only the allowed auto dispatch table.
- [ ] 3. `py -m unittest tests.test_supervisor tests.test_supervisor_server tests.test_usage tests.test_task_messages tests.test_server`;
      full suite. Commit: `feat: bound supervisor autonomy and spend (plan 44 backend T8)`.

**Drift guard:** approval can authorize a suggestion, but it cannot authorize forbidden actions or evade any
existing gate. No automatic cap reset, new permission prompt, provider network API or kill-on-budget action.
