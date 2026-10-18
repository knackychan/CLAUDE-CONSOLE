# Task 2: audit, event identity and restart recovery

> Contract: [README.md](README.md) 4.3-4.5. Lands on Task 1.

**Files**
- Modify: `console/supervisor.py` (audit/event helpers)
- Modify: `console/server.py` (`Hub.__init__`, new `Hub.reconcile_supervisor`)
- Modify: `console/usage.py` (durable supervisor reservations/results with existing FILE_LOCK and atomic IO)
- Modify: `tests/test_supervisor.py`; create `tests/test_supervisor_server.py`
- Modify: `tests/test_usage.py` (reservation/settlement, corruption and writer compatibility)
- Modify: `tests/test_tasks.py` (retention assertion only)

## 2.1 Signatures and persistence

- `event_id(line: dict) -> str`: SHA256 of canonical original transition JSON; caller supplies only the
  qualifying line. Include timestamp/session/step/from/to/why; never mutable cost or supervisor audit text.
- `request_id(task_id: str, wake: int) -> str`: UUID5(NAMESPACE_URL, `sup-<task>-<wake>`), valid for the
  existing request_next UUID regex. Same logical wake always yields the same id.
- `read_log(home, task_id: str) -> list`: safe_id/folder guard, parsed masked lifecycle records in order;
  absent file is empty; bad/truncated records retain a corruption marker for admission/recovery.
- `append_log(home, task_id: str, record: dict) -> None`: redact.mask the serialized JSON, append one
  newline, flush before returning; IO errors propagate to Hub so it fails closed. No file path from model data.
- `fold_log(records: list) -> dict`: per-wake state, claimed events, pending, total priced cost, per-day
  priced cost/reservations and uncertainty. Reject duplicate result costs; latest valid lifecycle state wins.
- `Hub.reconcile_supervisor() -> list`: under tlock, rebuild atomic task policy projections from journal;
  append recovered records for interrupted passes/dispatches without launching anything. Called once after
  tasks are loaded; request_next's own reservation reconciliation remains the existing path in Hub.run.

Journal is authoritative for a claim/result/intent that reached disk before task.json did. Persist claim and
increment wakes before any subprocess. An append/save error prevents launching. Cost is attached to a single
result identity; subsequent dispatch/approval/recovery lines carry no additional bill. Unknown paid cost is
not zero. Lifetime/day projections include deleted/cleared-task retention behavior discussed in Task 11.

**R1 recovery boundary:** reconciliation restores claims/results/held intent; it does not manufacture a
claim for an event that was merely queued at shutdown. Task 5's first advance recovers those unclaimed
current boundaries from original chain transitions. Task 9 extends that same classification to holds/done.
Keep consumed event identities separate from queued candidates so interrupted claims never become retries.
Claim records also carry R3's prompt_hash once the runner lands; missing older hashes remain unavailable.

A lever left dispatching is uncertain even if the current state looks compatible; never infer permission to
retry it. Add-step intent may link to its request_next reserved step and status, but cannot launch a step
itself. Preserve plan 36's 'starting without session -> stuck, Retry explicitly' behavior. Reconcile twice is
idempotent. A task deleted while its pass runs is not recreated by completion/recovery.

`tasks.clear(keep_last=True)` already keeps task-root supervisor.jsonl. Add a regression assertion instead of
rewriting it. Full Delete still deletes task artifacts according to the existing contract. The durable ledger
below already survives deletion; Task 11 exposes it on Usage. Do not expand retention or prune unrelated files.

## 2.2 Existing Usage file, durable spend identities

Add these helpers in console/usage.py using FILE_LOCK, _read/_write and their atomic/error-preservation
pattern. No second database/file/worker or cross-process locking system:

- `load_supervisor(folder) -> dict`: top-level supervisor mapping from usage-days.json; malformed data
  returns an explicit unavailable/error result rather than a free empty allowance.
- `reserve_supervisor(folder, pass_id: str, record: dict, task_limit: float, day_limit: float) -> dict`:
  under FILE_LOCK, read totals and active reservations, atomically reserve the lesser remaining allowance,
  or return a cap/error reason with no write. record supplies task, wake, day and kind (wake or replay).
  Include task/day results from all saved identities. A temporarily reserved balance defers admission;
  an actually exhausted cap is reported without calling a model.
- `record_supervisor(folder, pass_id: str, result: dict) -> dict`: idempotently settle the reservation with
  finite known cost, or retain reserved allowance with status unknown. Conflicting settlement is refused
  visibly; known cost above reservation is recorded in full. Preserve the admission day.

Stored record: pass-id -> {task, wake, day, kind, reserved, cost, status}; live pass id is request_id(task,wake).
Reserve before model launch, alongside the task's durable claim, and settle after result. Partial persistence
keeps a reservation/claim as uncertain until reconciled, never automatic refund or a paid retry. Rebuild a
missing record from a durable claim/result, deduplicate by pass id. A corrupt file refuses admission; preserve
it as existing Usage writers do. Keep days/other/seen untouched and do not use add_other's short seen horizon.
Ledger records remain after full task Delete/prune and receive late completions without recreating a task.
Task policy usd is projected from ledger totals when read/recovered; replay uses that same budget.

At Task 5's first scheduler, use these helpers for own-pass task/day limits. Task 8 adds work/auto caps;
Task 11 adds Usage display and replay through the same running Hub, which is the only admission owner.

## Tests first

- `AuditTest.test_event_and_request_ids_are_stable`: duplicate same transition matches; new attempt/transition
  differs; request id passes existing regex and differs by task/wake.
- `test_append_is_masked_and_fold_counts_cost_once`: claim/result/dispatch/outcome plus repeated result does
  not multiply spend; secrets masked; task ids with traversal refused.
- `test_corrupt_or_truncated_log_is_a_visible_hold`: no zero-budget fallback; missing file remains valid.
- `SupervisorServerTest.test_recovery_rebuilds_saved_result_after_task_save_failure`: journal committed,
  task projection stale; new Hub repairs counters/pending without running a model.
- `test_dispatching_lever_becomes_uncertain_never_replayed`: repeated reconcile and advance call no lever.
- `test_reserved_next_step_recovery_does_not_append_or_launch`: both session-recorded and missing-session
  crash fixtures keep one numbered step and obey reconcile_next_steps.
- `test_clear_keeps_supervisor_audit`: task.json, chain.jsonl and supervisor.jsonl retained byte for byte.
- `tests/test_usage.py`: reservations constrained at zero/exact limits; concurrent history/other-harness
  writes preserve supervisor records; settlement/recovery cannot duplicate cost; timeout/partial write/
  corruption cannot free allowance; task deletion does not reset the daily total.

## Steps and acceptance

- [ ] 1. Write tests with temporary roots, mocked runner/lever and fabricated journal phases; focused red run.
- [ ] 2. Implement audit and recovery; do not add a second recovery scheduler.
- [ ] 3. Run `py -m unittest tests.test_supervisor tests.test_supervisor_server tests.test_tasks tests.test_usage` and full suite.
      Commit: `feat: persist supervisor audit and recover uncertain intent (plan 44 backend T2)`.

**Drift guard:** journal replay restores evidence/state, never permission for a second side effect.
