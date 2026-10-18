# Task 11: spend projection and dry-run replay

> Contract: [README.md](README.md) 4.1, 4.5; brainstorm section 11. Lands on Tasks 2, 4, 8-10.

**Files**
- Modify: `console/server.py` (`Hub.usage_report`, `_drop`, new `Hub.replay_supervisor`,
  `Handler._supervisor_replay` and do_POST route)
- Modify: `console/supervisor.py` (`spend_view`; reuse existing `run` for replay)
- Modify: `console/__main__.py` (`main`, early replay argument branch)
- Modify: `tests/test_usage.py`, `tests/test_supervisor.py`, `tests/test_supervisor_server.py`
- Create: `tests/test_supervisor_replay.py` (CLI branch and no-effect checks)

## 11.1 Usage backend

`supervisor.spend_view(records: dict) -> dict`: fold the existing durable daily records into per-day
{cost, runs, unknown, reserved}; repeated lifecycle rows do not add cost. Include task/wake identity in detail
projections, not transcript text. Hub.usage_report gains `supervisor: {days, today, task_limit, day_limit}`.
Keep current days/models/projects/fills totals' shape, and expose these non-transcript pass costs as a separate
explicit component so future Usage UI can show/add them exactly once. Do not insert imaginary token counts,
double-count them as worker transcripts or change usage.History scanning to find no-session passes.

The same ledger drives admission and Usage. `_drop` does not delete daily ledger entries; settlement of a
deleted in-flight task uses the saved pass identity. Keep planned accounting tests from Tasks 2/8 active,
including retained costs after task Delete/prune and midnight admission-day attribution. No paid call is
launched while accounting is corrupt or a prior unknown reservation consumes the allowance.

## 11.2 Replay command

`py -m console --supervisor-replay <task> <wake>`: argparse nargs=2, mutually exclusive with serve/window.
Early branch before ensure_config/pruning/kind seeding/Hub construction/probes/server/tray startup. CLI reads
paths.load_config for the port and validates argument shape; the service reads the safe task/wake, kind and
saved evidence. Unknown task/wake/invalid args fail nonzero with a concise masked error and no model call.

Use the already running service as the single admission owner. The CLI sends the guarded local request
`POST /api/task/supervisor/replay {task, wake}` with X-CC; if the service is absent, fail with 'Start the Console
service before replay'. Do not launch an independent paying subprocess from the CLI or add cross-process locks.
This reuses the repository's urllib/local-service pattern and the one Hub's locks, caps and bounded worker slots.

`Hub.replay_supervisor(body: dict) -> tuple`: validate task/wake, mode/pause/guidance/exe/project and money
admission, refuse busy task/global slot, snapshot the live gates/current saved digest under tlock, and run one
bounded pass outside locks on the request thread. Account in finally and release its slot. Return logged
decision/outcome beside fresh answer/check, original/current revision and prompt_hash, and an explicit
no-dispatch marker. Build the fresh prompt once with Task 4's build_prompt, compute prompt_hash, and send
that same prompt to run. Return a missing historical prompt_hash as null/unavailable, not a reconstruction.
Handler._supervisor_replay is a thin guarded JSON adapter. Accept task/wake only, no client decision or bypass.

Hub reuses supervisor.run directly and returns the small comparison object; no second runner or wrapper.
Current evidence and kind text can differ from the historical wake. R3: evidence revision and exact-prompt
fingerprint answer separate questions. Label each comparison separately; a kind-only edit leaves revision
equal and changes prompt_hash. Do not claim historical content reproduction or add a prompt archive.
Original gate/source snapshots remain in the audit for inspection; the replay digest uses live snapshots.

One explicit replay permits one paid pass within current task/day spend allowance, with the same tool/timeout/
model/budget bounds and no automatic retry. The claim stores the gate/source/triggers context needed here.
Use a new UUID4 with kind replay for its reservation/settlement in the shared Usage ledger; never reuse the
original live dispatch request id. Replay writes money accounting only; it cannot modify task.json, task
audit/chain, pending decisions, project files, modes, action counters, approvals or workers. It never resets
the auto window; lifetime paid-spend projections do reflect its cost. A cap refusal performs no call.
Concurrent live and replay admission share the running Hub and ledger FILE_LOCK/atomic reservation check.

The CLI must not construct a Hub merely to get gates: __init__ starts a probe thread. The existing service
passes immutable live context to digest as in Task 3. No mock Hub class, daemon or generic control client.
CLI stdout is masked JSON/text; exit 0 for a completed dry run, nonzero for input/admission/runner/service error.
Use an HTTP timeout above supervisor_timeout_s plus a small response margin; an HTTP disconnect never
replays the request automatically, and service-side paid accounting still completes.

## Tests first

- `test_usage_reports_actual_supervisor_cost_once`: result+approval/recovery/replay lifecycle, error cost,
  two tasks and retained deleted-task cost; known costs and unknown/reserved clearly separated.
- `test_replay_prints_original_and_fresh_without_task_effect`: snapshot bytes under task/project before
  and after; mock task_lever/request_next/runs.start/server/window/prune/ensure_config/probe to fail if used;
  one fake pass in the existing service, accounting-only change and distinct replay id.
- `test_replay_uses_current_saved_files_and_live_gates`: edit handoff and kind in separate subtests.
  Handoff edit changes evidence revision and prompt_hash; kind-only edit preserves evidence revision and
  changes prompt_hash. Logged decision stays unchanged; fresh hash matches captured stdin bytes. Missing
  historical hash is unavailable. No false claim of exact historical replay and no new task/audit writes.
- `test_replay_invalid_input_failure_and_caps`: bad id/traversal/wake, missing task/wake, incompatible
  args, absent service, off/paused/pending guidance/busy, no executable, timeout/bad result; no retry,
  no effect, paid failure cost/reservation retained; malformed Host/missing X-CC also refused.
- `test_replay_and_live_wake_cannot_double_reserve_day_allowance`: simultaneous admissions from independent
  callers on the shared file lock, total reserved <= remaining; ledger corruption refuses both.
- `test_existing_usage_history_other_harness_and_cli_start_modes_survive`: prior Usage and main modes keep
  default behavior; no dependency or changes to hook installation/config files.

## Steps and acceptance

- [ ] 1. Usage/CLI tests red with temporary data/project and fake command prefix.
- [ ] 2. Add projections and early replay branch, reuse runner and existing durable ledger admission.
- [ ] 3. `py -m unittest tests.test_usage tests.test_supervisor tests.test_supervisor_server tests.test_supervisor_replay`;
      full suite. Commit: `feat: expose supervisor spend and bounded dry-run replay (plan 44 backend T11)`.

**Drift guard:** dry run means no dispatch. A model call still spends money and uses the same spend controls.
