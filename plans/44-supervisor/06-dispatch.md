# Task 6: gated, idempotent dispatch and held decisions

> Contract: [README.md](README.md) 4.2, 4.4-4.5. Lands on Task 5. Auto still disabled until Task 8.

**Files**
- Modify: `console/server.py` (new `Hub._supervisor_dispatch`, `_supervisor_done`; keyword-only origin
  on `task_lever` and `request_next`; existing gates and reservation flow retained)
- Modify: `console/supervisor.py` (dispatch outcome projection)
- Modify: `tests/test_supervisor_server.py`, `tests/test_task_messages.py`

## 6.1 Dispatch signature and order

`Hub._supervisor_dispatch(task_id: str, wake: int, by: str) -> tuple` returns the usual (HTTP-style status,
body), used internally and by Task 7's approval route. by is internal auto/fred approve only. Never trust a
body-provided decision, source session, authority, model id or request id. Read the saved pending decision.

Under tlock, in order: fetch current task/pending; detect previously completed same wake and return saved
outcome without an effect; reject uncertain/superseded/off/paused; compare semantic revision and epoch;
block asks/Plan gap and all pending guidance; get live task_levers and next_sources/ownership; call check;
apply authority/caps; prepare exactly one existing operation; append durable dispatching; call operation;
append outcome, save projection and return its status. Human reset ordering is specified in Task 7.

| Decision | Existing operation |
|---|---|
| add_next_step | preview_next({task, source_step, source_session, kind, instructions, model:'auto'}), then request_next with returned revision and stable UUID5 |
| confirm/keep/retry/stepdone/stop | task_lever(task, action, retry note/model only where applicable, internal origin) |
| finish | task_lever(task, 'done', internal origin) |
| wait/escalate_to_fred/answer | no mutating operation; wait logged, escalation shown, answer refused/escalated |

Use `task_lever(..., *, origin='fred')` and `request_next(..., *, origin='fred')`; all existing HTTP/manual
callers retain the default. Supervisor calls identify their origin and never reset Fred's autonomy window.
Origin is a private call argument, not a public request field. These methods still own their live gates,
validation, retries, routing and persistence; the supervisor does not duplicate their effects in tasks.fred.

If queued guidance arrives after the model starts, save held pending intent before doing anything. On drain,
revalidate unchanged evidence; a changed epoch/revision replaces the held intent with one fresh wake, rather
than executing advice written before the guidance. Never automatically carry, answer, cancel or replay guidance.
Refusal preserves reason and a non-executable/suggested card as appropriate; it does not spend on another pass.

Both supervisor revision and Add-step preview revision must pass; preserve request_next's internal second
preview and signature checks. `status: held` is success at reserving a step, not permission to append again.
Link it as 'held step NN' and leave the Fable/pace hold to Fred. Unknown outcome after invoking a lever becomes
uncertain, no replay. Disk error before dispatching persists no effect. Outcome-save failure never invokes
the operation twice. A newer task dict from request_next must be refetched before writing pending/outcome.

## Tests first

- `test_dispatch_uses_existing_preview_revision_and_uuid`: assert preview_next/request_next calls and saved
  received-handoff/received files, fresh session resume=None, stable repeated request id and one new step.
- `test_live_gates_win_after_valid_model_result`: change source, remove project, change route/model limits,
  later unfinished step, live run and plan/Fable/pace state between pass and dispatch; no bypass.
- `test_guidance_during_pass_holds_all_dispatches`: loop over actions including retry/stop/confirm, where
  existing gates sometimes allow a queued-message action; supervisor still makes zero dispatch calls.
- `test_held_guidance_drain_revalidates_or_requeues_once`: unchanged held fixture can dispatch once;
  new guidance/epoch or saved evidence change invalidates advice and coalesces one fresh wake.
- `test_held_add_step_is_not_appended_or_confirmed_again`: request_next returns held; repeated completion/
  dispatch/advance/restart leaves one reservation and no task_lever(confirm).
- `test_duplicate_lever_dispatch_and_outcome_failure_do_not_repeat`: repeated calls, concurrent calls,
  failure after side effect and restart all produce <=1 call; uncertain state requires human dismissal.
- `test_intent_write_failure_prevents_effect`: inject OSError in audit append and tasks.save; no work starts.
- `test_retry_preserves_limits_avoid_and_note`: same plan 40/43 route refusal/avoid behavior as Fred's Retry.

## Steps and acceptance

- [ ] 1. Read all task_lever/request_next callers; write above tests red around real Hub methods/fake workers.
- [ ] 2. Add dispatch and origin defaults with no public gate changes; focused tests green.
- [ ] 3. Run `py -m unittest tests.test_supervisor_server tests.test_task_messages tests.test_server tests.test_limits`.
      Full suite; commit: `feat: dispatch supervisor advice through existing task gates (plan 44 backend T6)`.

**Drift guard:** automatic dispatch is not activated in this commit, even if saved mode is auto.
