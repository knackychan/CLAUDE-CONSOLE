# Task 12: integration acceptance and backend close

> Contract: [README.md](README.md), all hard rules. Lands on Tasks 1-11.

**Files**
- Modify: `tests/test_supervisor_server.py` (cross-feature acceptance tests, reuse existing fixtures)
- Modify: `PLAN.md`, `plans/44-supervisor/README.md`, `plans/44-supervisor/BRAINSTORM.md` (state only)
- Modify: `CLAUDE.md` only for the durable shipped API/invariant paragraph after tests pass
- No frontend, skill-library, hook installer or other CLI settings changes.

## 12.1 Acceptance matrix (fake providers, temporary roots)

| Case | Required observable result |
|---|---|
| design -> suggestion -> Approve -> code -> verify PASS | One worker per accepted wake, saved handovers/source lineage, gated Finish; no persistent supervisor session |
| two transitions inside debounce, duplicates and 100 idle advances | One pass with combined triggers, no duplicate call or due re-arm from duplicates |
| several triggers during a blocked pass | One dirty follow-up, maximum one active/task and configured global bound |
| queued/failed/uncertain guidance before wake or arriving in flight | No premature pass/dispatch, held audit, no guidance replay, fresh advice after changed evidence |
| stale Approve, repeated Approve/Reject and duplicate request id | 409 for stale/conflicting action, <=1 effect for identical action, no extra step |
| held Add step at pace/Fable | One durable step reservation, no auto Confirm/reappend, Fred's explicit gate remains |
| three auto additions then fourth, retry once, second FAIL | Fourth/extra recovery suggested or escalated; human reset explicit, restart does not reset |
| work/task/day limits, active reservations and deleted task | No next launch after cap, costs/reservations retained exactly once and visible on Usage |
| missing executable, timeout, bad JSON/schema, CLI error/overrun | One terminal no-decision, cost preserved/unknown reserved, active slot freed, no model retry loop |
| disk errors before claim/intent, after effect, restart | No effect before durable intent; possible effect becomes uncertain; no lever replay or duplicate step |
| pause/off/delete/evidence edit during pass | No stale dispatch or task recreation; paid costs still settle |
| stalled Claude step | Sonnet once, no automatic Stop; Stop and subsequent Retry each require approval |
| automatic done, no room and questions/holds/external chats | Only eligible done check, force-suggest; all excluded wakes spend nothing |
| replay | One bounded call, original vs fresh displayed, accounting-only write, never dispatch |
| R1: restart during debounce | Every eligible current boundary recovered once by original event id; consumed/superseded events stay idle |
| R2: Pause/Resume at manual choose-next or FAIL | Real shared routes accept both, retain manual ownership, no chain start; old in-flight advice never dispatches |
| R3: kind-only replay edit | Evidence revision equal, prompt_hash different and equal to executed stdin hash; original audit unchanged |

Add named tests `test_supervised_manual_lifecycle_end_to_end`,
`test_crash_at_each_dispatch_boundary_has_at_most_one_effect`, and
`test_all_pending_guidance_states_block_all_supervisor_actions`. Use subtests for crash points: before claim,
after claim, after result before task save, after dispatch intent, after reservation before worker session,
after worker start before outcome. Reconstruct a fresh Hub from saved fixtures and call advance explicitly.
Do not delete existing plan 36/42 recovery tests or weaken their assertions to make this feature fit.

Review closure gate: run the named R1 tests in Tasks 5/9, R2 tests in Task 7 and R3 tests in Tasks 4/11.
Inspect persisted event ids, pause/epoch, and claim prompt_hash in the fake lifecycle artifacts. Each review
annotation in README must map to passing behavioral evidence before backend closure; a documentation edit
or mocked gate that skips task_levers/tasks.fred is not proof. Keep these annotations as design rationale.

## 12.2 Commands and review

```bat
py -m unittest tests.test_supervisor tests.test_supervisor_server tests.test_supervisor_replay
py -m unittest tests.test_task_messages tests.test_server tests.test_tasks tests.test_compact tests.test_replan tests.test_handoff tests.test_limits tests.test_usage tests.test_tuning tests.test_kinds
py -m unittest discover -s tests
node --check web/app.js
```

Run focused tests as failures are fixed, then one final full run. Inspect the resulting task.json,
supervisor.jsonl, chain.jsonl, received.md/received-handoff.md and shared cost ledger from a fake lifecycle.
Confirm every real dispatch call graph ends in request_next or task_lever, every admission/dispatch checks
pending guidance, and no new scheduler/RunManager supervisor session/tool access was introduced. Verify
no code outside allowed data paths writes runtime supervisor artifacts. Existing plan mirror exception stays.

## 12.3 Documentation and commit

- [ ] 1. Write integration tests red, resolve failures within this plan, run the commands above.
- [ ] 2. Update PLAN.md to backend implemented with actual commit/check evidence and separate remaining
      UI, skill library and live checks. Mark task checklists only for work actually placed.
- [ ] 3. Add shipped invariants/routes to CLAUDE.md and status pointer to BRAINSTORM.md without changing
      Fred's decided policy. Navigation remains shipped; its UI supervisor attention wiring is still pending.
- [ ] 4. Commit: `test: verify supervisor backend safety and close its plan (plan 44 backend T12)`.

## 12.4 Separate live check, Fred

Not required to write this plan; do not claim it passed after fake-provider tests. When Fred runs the backend:
use a permitted scratch project/manual task in suggest mode, inspect one real decision and measured cost,
Approve one next step, then inspect a real provider rejection and replay. Check the installed CLI actually
honors the bounded command and returns the expected cost envelope. No automatic hook installation or edits
to another CLI's settings. Real billing can exceed CLI estimates within an in-flight call; further launches
must stop at the observed cap. Board UI is unavailable until its separate frontend slice lands.

**Done for this backend:** all automated cases pass and indexes accurately distinguish shipped backend from
parked UI/skills. The implementation run stops here; it does not silently begin those other features.
