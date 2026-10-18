# Task 7: approvals, modes, attention and human actions

> Contract: [README.md](README.md) 4.2-4.5. Lands on Task 6. Completes the suggest-only backend checkpoint.

**Files**
- Modify: `console/server.py` (`Handler.do_POST`, new `_task_supervisor`; `Hub.supervisor_action`,
  `supervisor_view`, `_supervisor_fred`; `Handler._task`, `task_row`, `task_levers`; human call sites below)
- Modify: `console/tasks.py` (`fred`, manual Confirm and supervised manual Pause/Resume boundaries)
- Modify: `tests/test_supervisor_server.py`, `tests/test_tasks.py`, `tests/test_server.py`

## 7.1 Exact API

`POST /api/task/supervisor`, using existing guard.host_ok/post_ok, MAX_BODY and _body handling:

- `{task, mode:'off'|'suggest'|'auto'}` changes mode; no wake/model/run on the POST. Save initial policy
  lazily if legacy. It is a Fred act, chain/audit logged. Off clears queued wakes/pending executable intent;
  in-flight results still settle. Auto is stored but suggest-only until Task 8 lands.
- `{task, wake:<positive int>, action:'approve'|'reject', note?:str}`. Reject/dismiss accepts optional
  <=2000-character note; persists it for the next real wake. Reject of uncertain acknowledges without replay.
  Approve invokes _supervisor_dispatch on the saved decision only, never on client-supplied JSON.
- Unknown task 404; invalid/mixed fields, bool/invalid wake, action or mode 400; stale/nonpending/forbidden
  approval 409 with reason; audit/save error 500 before any effect. Same already completed action returns
  its saved result; conflicting action on the same wake returns 409. No approve-all, rerun or force route.
- `Hub.supervisor_action(body: dict) -> tuple`; Handler._task_supervisor is a thin JSON adapter.
- `Hub.supervisor_view(task: dict) -> dict`: mode, wakes, lifetime usd, work_usd, current caps/hold reason,
  pending {wake, decision, status, reason, can_approve, can_reject, error}, and last ten folded audit entries.
  `GET /api/task` exposes it at top-level supervisor. `task_row` exposes mode/attention/wake summary only.
  Pending suggestion/escalation/uncertainty puts the task in Needs you, including otherwise done tasks.
  Do not change why/state to pretend that a suggestion was an actual task transition.

## 7.2 Human origin and pause

`Hub._supervisor_fred(task: dict, now: float, action: str) -> None`: internal, called only after a successful
new human action is accepted, inside the same tlock/persistence transaction. Increments epoch, resets the
current auto/retry/work window, retains lifetime wakes/usd, invalidates older pending advice. It emits no wake.

Reach all actual task action callers: task_lever (including pause/resume/stop), request_next (reservation,
not duplicate request), task_message (new accepted send and successful explicit queue cancel/dispatch),
answer_gap, edit_plan and successful whole-task handoff actions. Initialize policy for Hub.create_task,
chat_task and _follow_up in Hub before saving; no supervisor import in tasks.new_task. Session-level actions
through Hub.pull for an associated task also count as human acts; external sessions remain unaffected.
Reads, previews, failed requests, duplicates, automatic chain moves and internal origin calls never reset.

Pause sets policy.paused; Resume clears it without a gratuitous model call. Stop cancels wakes and old
executable suggestions. Do not infer 'paused' just from manual boundary owner fred. A valid stalled-stop
Approve is the one exception that schedules the fixed retry suggestion described in Task 9.

**R2, shared Pause/Resume correction:** baseline task_levers treats owner fred as already paused, and
tasks.fred refuses Pause for that owner. The baseline Resume gate also refuses a completed manual boundary.
Updating the supervisor bit alone therefore cannot implement this contract. Change both the shared gate
and shared mutation for a task with a validated supervisor policy at a manual boundary (progression manual,
owner fred, current step done, state waiting, why choose next step or VERDICT: FAIL prefix):

| Action | Required state | Result |
|---|---|---|
| Pause | explicit paused false | Set paused true; retain owner/state/why/current and saved evidence |
| Resume | explicit paused true | Clear paused; retain the same manual boundary and owner fred |
| Duplicate Pause/Resume | bit already at requested value | Refuse with reason; no epoch reset or new wake |

Resolve legacy policy in Hub before calling the shared mutation; tasks.py must not import supervisor.
Keep the bit write in the accepted mutation and the human epoch/reset in Hub's existing transaction.
Do not broaden unrelated automatic/chat/plan/Fable/pace gates. This correction is for Fred's existing
Pause/Resume routes only; the supervisor cannot invoke either action.

An unclaimed boundary wake remains deferred while paused and may drain on a later advance after Resume
using its original event id and fresh live checks. Neither POST calls the model or creates an event. Both
successful human actions invalidate older advice through the epoch rule: an already claimed/in-flight pass
still settles cost but cannot dispatch after Pause, even if Resume happens before it returns. Do not requeue
that consumed event or resurrect its pending decision. A new transition is required for another pass.

Approve ordering: validate saved wake/revision/epoch and all hard gates first, then record the successful
human authorization/reset with the original decision identity and revalidate for the resulting epoch before
dispatching. Do not invalidate the very decision being approved. A refused Approve resets nothing. Automatic
dispatch uses origin='supervisor' and cannot look like another Fred act just because it calls task_lever.

For a **manual** design's plan oversize hold, current tasks.fred(confirm) would set running while leaving
owner fred and no scheduled tail. After confirmation, a done current step must instead return to waiting /
choose next step, owner fred. Apply the same manual boundary rule to applicable keep/confirmed replans.
Keep automatic plan-confirm behavior unchanged. Test this in tasks.fred and Hub, rather than inventing a
supervisor-only state mutation. The manual plan does not rebuild automatic planned steps.

## Tests first

- `test_mode_endpoint_validation_guards_and_persistence`: bad Host/missing X-CC 403, invalid shapes 400,
  unknown 404, save failure 500; effective mode survives restart; no paid call in mode POST.
- `test_suggest_does_nothing_until_approve_and_duplicate_approve_is_safe`: fake decision, one explicit
  Approve effect, repeat returns recorded result; concurrent Approves at most one launch.
- `test_stale_reject_uncertain_and_forbidden_approval`: old wake 409, saved rejection note, no immediate
  new call, uncertain dismissal no side effect, answer/Fable/pace unapprovable.
- `test_pending_attention_is_projected_without_state_change`: GET detail and snapshot/Needs you count agree,
  last ten entries folded, masked; a completed task with pending done-check suggestion stays visible.
- `test_only_new_successful_fred_actions_reset_epoch`: table of the callers above, duplicate/refused/preview
  and supervisor-origin controls. Retain lifetime spend/wakes. Late old-epoch costs do not charge new window.
- `test_pause_holds_supervisor_but_manual_boundary_does_not`: explicit pause persists through restart;
  in-flight completion cannot act while paused/off. No wake caused merely by switching mode/resuming.
- `test_manual_boundary_pause_resume_uses_shared_gates`: through real task_levers/task_lever/tasks.fred,
  test choose-next and FAIL in suggest/auto. Pause during debounce prevents admission; Resume retains owner
  fred/state/why/current and starts no chain work. A later advance may claim the original deferred event once.
  Duplicate actions reset nothing; ordinary automatic and chat Pause/Resume behavior remains unchanged.
- `test_manual_boundary_pause_resume_during_pass_never_dispatches_old_advice`: block the fake runner,
  Pause then Resume, release it; cost settles once, zero dispatches and no retry of its consumed event.
  Repeat with restart while paused and verify persisted bit/epoch prevent stale approval.
- `tests/test_tasks.py:test_confirm_manual_plan_returns_to_choose_next`: same saved plan remains, no automatic
  step inserted; automatic confirmation still starts its existing chain through Hub.

## Steps and acceptance

- [ ] 1. API/human-origin/manual-confirm tests red; read every named action caller before editing it.
- [ ] 2. Add thin endpoint and projections, centralized human bookkeeping and shared manual-boundary fix.
- [ ] 3. Focused `py -m unittest tests.test_supervisor_server tests.test_tasks tests.test_task_messages tests.test_server`;
      full suite. Commit: `feat: expose supervisor suggestions and explicit approvals (plan 44 backend T7)`.

**Checkpoint A:** suggest-only is usable through HTTP, default suggest, UI still pending. Verify auto-mode
fixtures cannot dispatch without approval before proceeding to Task 8.
