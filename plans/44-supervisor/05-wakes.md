# Task 5: transition wakes, coalescing and bounded workers

> Contract: [README.md](README.md) 4.1, 4.3-4.4. Lands on Tasks 2-4. Suggest only at this checkpoint.

**Files**
- Modify: `console/server.py` (`Hub.__init__`, `_ended`, `start_step`, `_broken`, `_replan_done`,
  `advance`, `_brief_done`; new methods below)
- Modify: `console/supervisor.py` (eligibility/event classification)
- Modify: `tests/test_supervisor_server.py`, `tests/test_supervisor.py`
- Modify: `tests/test_server.py` (`RunServerTest.setUp`, default supervisor_mode off for unrelated fixtures)

## 5.1 Functions and wiring

- `Hub.wake_supervisor(task: dict, trigger: str, line: dict, now=None) -> None`: classify and deduplicate
  the committed original event, merge into Hub.wakes and re-arm only for new events. `now` is monotonic.
- `Hub._supervisor_tick(now=None) -> list`: called once at the end of advance, after guidance/normal task
  progression; recover missing boundary wakes once, drain due entries up to the global cap. Save claim,
  increment wakes and snapshot digest/revision/epoch/config/kind under tlock before thread start.
- `Hub._supervisor_job(task_id: str, wake: int, snapshot: dict) -> None`: exactly one supervisor.run outside
  locks, catch unexpected exceptions as error result, always call completion in finally-controlled cleanup.
- `Hub._supervisor_done(task_id: str, wake: int, snapshot: dict, result: dict) -> None`: remove active slot
  even on error/deletion; account/audit result once, refetch live task, validate, save pending suggestion or
  wait/escalation/no-decision. Dispatch hook lands in Task 6, auto stays disabled until Task 8. New events
  received during the pass leave one future due entry, never a direct callback-to-worker chain.
- New maps: `Hub.wakes` as README; `Hub.supervising` mapping task id to active wake/snapshot. They are not
  Hub.briefing: supervision must not block the normal guidance path or pretend to be a worker/brief session.

Initial wake set: manual design/verify boundary and any real transition into stuck. Hook `_ended` after
notes/facts/plan and `_commit`, not before; use its actual returned manual/stuck action and original line.
Hook start_step rung/start refusals, `_broken`, and failed replan only on the real transition to stuck.
Do not wake the chain's automatic first retry. Repeated _broken on the same failed state is not a new event.

**R1:** use one eligibility classifier for live hooks and the first-advance recovery scan. At this checkpoint
recover both manual boundaries and stuck boundaries, including failed replan. Recover only the original
transition explaining the current boundary, not all historical transitions. Enqueue unclaimed events with
their original ids and a fresh debounce; brief/guidance blockers defer them. Task 9 extends this same path
for plan holds and automatic done. No claim, terminal result, rejected event or interrupted pass is retried.
**R3:** build the prompt from the captured inputs once before claim, persist its prompt_hash in the claim,
and pass that same prompt to the worker. No second kind-file read or prompt rebuild in the thread.
Old tests' fake tasks must not start surprise paid-pass threads: set supervisor_mode off in RunServerTest's
temporary cfg. New supervisor tests explicitly enable suggest/auto before creating their fixture task;
use the existing test_task_messages inheritance pattern for TaskServerTest helpers. Do not change production
defaults to make the suite quiet. Ensure controlled supervisor workers finish before temp directories close.
Use explicit named transition hooks, not a global '_commit always wakes' rule. Later Tasks 7/9 add the
remaining decided triggers. Do not start supervised passes for old live/replied chat tasks or external sessions.

At worker admission require allowed project/exe/harness availability and policy limits; if brief/guidance
is pending retain the unclaimed wake and check next advance. No repeated audit lines each blocked second.
Own-spend admission/reservations are introduced with audit in Task 2 and enforced before this first callable
scheduler; Task 8 adds work/autonomy counters. A disabled/global limited Claude runner never silently uses
another harness or starts an unpriced model. Missing exe is terminal no-decision for that event, not a loop.

## Tests first (fake clock, controlled threading.Event runner)

- `test_wakes_coalesce_and_rearm_once`: t=0 A due20, t=10 B due30, advance at29 calls none, at30 calls once
  with A+B; a duplicate A at29 does not delay due. Check journal consumed both ids and wake counter once.
- `test_events_during_active_pass_make_one_follow_up`: many new unique/duplicate events while blocked
  worker; max concurrent per task one, exactly one dirty follow-up after debounce, stale result not executable.
- `test_parallel_limit_applies_across_tasks`: parallel=1 and2, three tasks, verify active maximum and that
  finishing/erroring/deleting one releases a slot; no starvation of older due entries (sort due, task id).
- `test_no_wake_for_bookkeeping_chat_external_or_first_retry`: real transitions table; advance 100 times
  with no new event still zero/one calls, not 100.
- `test_pending_guidance_and_brief_defer_without_losing_event`: queued/failed/uncertain guidance, unfinished
  brief and replan block model admission; resolving the blocker yields one call after existing work is filed.
- `test_restart_queues_unhandled_boundary_once`: original waiting boundary without claim gets one wake;
  result, rejected, failed and claimed-interrupted event fixtures get no duplicate pass.
- `test_restart_before_claim_recovers_manual_and_stuck`: restart inside debounce for each initial boundary,
  including failed replan; original event id retained, exactly one call after debounce. Repeat with guidance/
  brief blocking, duplicate advances, and consumed-event controls. Historical superseded boundaries stay idle.
- `test_model_failure_does_not_loop_and_next_transition_can_wake`: terminal no-decision logs reason/cost,
  active slot cleared, same event never retried; distinct later event allowed.

## Steps and acceptance

- [ ] 1. Write deterministic lifecycle tests; mock supervisor.run, never sleep for debounce or call a provider.
- [ ] 2. Add hooks/maps/worker methods. Validate completion after refetch; no changes to normal chain choices.
- [ ] 3. Run `py -m unittest tests.test_supervisor tests.test_supervisor_server tests.test_task_messages tests.test_server`.
      Full suite; commit: `feat: coalesce task transitions into bounded supervisor wakes (plan 44 backend T5)`.

**Drift guard:** Hub.advance remains a short polling iteration; the paid pass is always in the bounded thread.
