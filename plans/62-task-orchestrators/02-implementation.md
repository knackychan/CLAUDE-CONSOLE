# Implementation sequence and integration boundaries

Parent: [plan 62](../62-task-orchestrators.md). Execute only when asked to implement the runtime.
The current task writes this plan and the separate-agent prompt. It does not build runtime or mockup code.

## 1. Baseline and release boundary

Before implementation, read the current versions of every caller named below and check working-tree changes.
Function names are navigation anchors, not permission to paste older plan code over newer fixes. Establish
the focused-test baseline with fake providers and a temporary `CC_CONSOLE_HOME`. Never run tests against the
user's live data home or occupied service port. Do not install hooks, edit CLI settings or restart production.

This is one coordinated runtime feature with incremental implementation slices. Intermediate commits must
not enable a partial runner, incomplete accounting or both decision engines. Mockup work can proceed before
all backend slices because it uses explicitly labelled local fixtures.

Code organization: extend existing pure task/policy/accounting helpers and Hub seams. One small dedicated
orchestrator runner module and one scoped-tool module are reasonable if existing modules cannot hold the
responsibility clearly. Do not duplicate `supervisor.py`, the harness registry or task action dispatch. A new
module does not get its own persistence, usage or scheduling subsystem.

## 2. Slice A: durable identity and evidence

Touch: `console/tasks.py`, `console/paths.py`, `console/supervisor.py`, relevant task/server tests.

1. Add optional versioned orchestrator metadata and acceptance entries from 01. Existing tasks load unchanged.
2. Define the decision-owner predicate once: new orchestration metadata identifies the new owner; absence
   identifies the existing supervisor/manual path. Reuse it for wake admission, completion and restart.
3. Keep assignment immutable after creation except a future explicit user-authorized migration. Save the
   actual route and effort before any provider call. Do not use mutable global defaults on recovery.
4. Define checkpoint validation, maximum byte size, expected generation/revision and task-bound artifact refs.
5. Make checkpoint publication atomic and crash-safe. The simplest storage contract is a self-contained
   `checkpoint.json` with its own version/source basis; avoid a second independently authoritative pointer.
   Any `checkpoint_revision` exposed on task views is derived from the accepted file. If integration stores
   a cached pointer, it is advisory and cannot invalidate the last sound checkpoint after a partial save.
6. Persist exact decision input under the wake directory; reuse existing run records for outputs. Never copy
   transcripts into the checkpoint or silently convert legacy step files.
7. Add criterion/evidence invalidation after writing steps, including failed or partial writes. Conservatively
   invalidate when the working result changed but a reliable fine-grained basis cannot be established.

Checks: legacy load, immutable assignment round trip, atomic-save failure preserves prior bytes, stale/cross-task
checkpoint rejected, missing evidence stays unknown, verification invalidated after later changes. No real launches.

## 3. Slice B: bounded context and artifact access

Touch: supervisor digest helpers, task/brief/facts readers, scoped artifact helper, corresponding tests.

1. Build a task-local artifact registry from trusted step/plan/run metadata. Expose IDs, titles, kind, source
   revision, size and access scope. The registry is derived; do not add an independent search database.
2. Build mandatory/current/selected packet tiers from 01. Do not include other tasks, full worker transcripts,
   global super notes or all historical handoffs. Keep current user constraints and guidance authoritative.
3. Preserve original accepted files and whole required handoff sections. Optional exclusions are explicit.
4. Check byte limits before model admission. Include serialization/tool/role overhead. Required overflow holds.
5. Implement bounded artifact sections/pages and cumulative output/call accounting shared across all tools
   in a decision generation. Exhaustion must still have reserved room for a concise error/outcome.
6. Resolve canonical paths under the selected task; cover absolute/UNC paths, Windows drive-relative paths,
   mixed separators, symlinks, junctions and nonregular files. Do not export arbitrary path reads over MCP.
7. Make source coverage visible in the persisted input and task read projection; it is not a fabricated token
   saving percentage. Separate payload byte metrics from provider session token telemetry.

Checks: exact-boundary sizes, multibyte text, oversized mandatory goal, omitted optional file, missing file,
path escapes, repeated pagination, duplicate calls, six-call exhaustion and a retained valid outcome.

## 4. Slice C: assignment, effort and shared accounting

Touch: `console/harness/`, `console/claude_cli.py`, `console/fills.py`, `console/limits.py`, `console/tuning.py`,
`console/paths.py`, `console/usage.py`, Hub usage/budget views, run/hook/transcript readers and fixtures.

1. Reuse configured think-capable rungs; add a positive orchestration-capability check separate from ordinary
   worker support. Until proven for an adapter, give a named exclusion rather than broadening permissions.
2. Add one global `orchestrator_effort` setting through the whitelist; default `high` for the first release.
   Reuse existing effort labels/mappings. Save requested and resolved values at assignment.
3. Route Auto through the existing balancing function with the global usage snapshot and current live limits.
   Preserve explicit picks and deterministic ties. No hardcoded vendor/model pool or new quota scheme.
4. Persist final assignment before launch. If no eligible route remains, keep the task waiting with its draft,
   goal and selected preference intact. Never silently replace an explicit unavailable pick.
5. Trace each existing usage ingestion path and define one authoritative turn identity. Attach task/role to
   the record rather than copying spend into a second additive total.
6. Merge orchestrator turns into the same model totals used by Usage and assignment. Reuse existing model
   normalization, time windows and token semantics. Do not count reserved spend as already settled spend.
7. Reconcile duplicate hook, stream and transcript observations and supervisor-ledger records. Keep missing
   usage/price unknown; do not erase a reservation solely because the process vanished.
8. Expose task/role breakdowns with a reconciliation invariant: sum of attributed records equals their share
   of the global total, and role breakdowns are not added again to that total.

Checks: disabled/missing/unsupported CLI, unsupported effort, a lower-load eligible assignment, fixed owner
despite later load changes, global effort edits, shared model keys across CLIs, duplicates, paid failure,
multi-turn session identity, unknown tokens/cost, concurrent admission and restart reconciliation.

## 5. Slice D: scoped tools and one decision turn

Touch: `console/guard.py`, existing HTTP handler, runner/harness modules, supervisor/Hub lifecycle; fake CLIs.

1. Define task/generation-bound ephemeral credentials and the six capabilities in 01. Keep loopback binding
   and existing request guards. No arbitrary task selector, file path or shell execution capability.
2. Map reads to scoped state/artifacts; prepare maps to existing next-step preview. Save/ask map to validated
   persistence and task question/guidance. Effects call existing Hub methods with a distinct audited origin.
3. Verify installed CLI flags and permission behavior against its local implementation/help and current primary
   documentation before coding them. This plan intentionally does not invent unverified command-line flags.
4. Launch a fresh session per admitted wake on the stored route. Allow only the verified scoped tools. Do not
   let implicit user MCP servers, unrelated memory or project instructions widen the orchestrator's scope.
   Preserve legitimate task/project constraints through the bounded packet.
5. Enforce tool loop, timeout, output and input budgets. Expire credentials after completion/restart and reject
   stale generations. Do not log credentials or credential-bearing MCP configuration.
6. Preserve wake coalescing, existing lock order and one active decision per task. Model execution happens
   outside state locks; effects reacquire gates/revisions at dispatch.
7. Save checkpoint before a worker launch, then intent before effect and outcome after effect. An audit write
   failure refuses dispatch. An uncertain effect holds and is not automatically replayed.
8. Settle usage on success, refusal, timeout, failed launch and recovery. End the decision process while waiting
   for a worker; no background conversational polling.

Checks: forged task/generation, replayed request, stale preview, lost audit write, late tool/result, interrupted
turn, timeout, denied tool, duplicate wake, scoped MCP credential and no thinking while waiting for a worker.

## 6. Slice E: adaptive continuation and user guidance

Touch: Hub next-step/action/completion flows, supervisor policy, task message delivery, worker prompts/kinds.

1. Have the orchestrator produce bounded assignments using existing kinds. Reuse routing and verification
   rules; do not enable nested Agent tools or arbitrary shell-based session spawning.
2. A known small change can skip scout/design. A repair names its failed criterion and source evidence. Each
   new step preserves lineage so retry, escalation and work caps cannot be bypassed by relabelling work.
3. Validate evidence before marking criteria passed; missing/stale results remain unknown. Report ready only
   when current criteria are satisfied and unresolved questions/gates are cleared. Acceptance stays user-owned.
4. Persist messages before acknowledgement. Distinguish queued, received, forwarded and uncertain states.
   Bind answers to the originating question; preserve task/recipient even while the user navigates elsewhere.
5. Keep Pause/Stop/retry semantics and pending-guidance resolution. A user control invalidates incompatible
   pending actions; a late model output cannot reverse it.
6. Keep one worker at a time per task. Reuse shared concurrency/admission limits across tasks; capacity queued
   work is not presented as a running process.
7. Intercept existing automatic chain advancement for migrated tasks at validated worker boundaries. Wake
   the new owner before a next worker launches. Support authorizing an already-planned next step without
   duplicating it, and reject late legacy supervisor completions after the ownership change.

Checks: direct implementation path, scout-to-code path, verify-fix-verify, no-progress cap, question answer,
queued guidance ordered ahead of continuation, Pause with queue intact, manual stop, current evidence and
ready-versus-accepted distinction. User actions reserved in existing policy remain reserved.

## 7. Slice F: read projection and UI integration

Only after backend semantics are stable, use the separately reviewed mockup for product integration.

1. Extend existing task reads with a projection of assignment, orchestrator activity, current worker, criteria,
   context coverage and attributed usage. Keep `Hub.actions` as action/gate authority.
2. Build global counts/status from all task projections in code. Remove global model-authored conversation from
   the target flow. A dashboard read never wakes a model or changes state.
3. Add task-scoped orchestrator transcript/message rendering and preserve worker transcript inspection.
   Use explicit recipients and per-task drafts; do not rebuild server action gates in JS.
4. Global effort writes through the whitelist. Route availability is read from verified server capabilities,
   not a static UI model list. Show unknown usage/context and exclusion reasons honestly.
5. Implement Context as a bounded inspection view: current packet coverage, checkpoint and evidence references.
   Viewing an artifact does not inject it into a model prompt or send a message.
6. Reuse existing CSS/components/tokens. No framework, build step or global UI rewrite is required.

Checks: task switch preserves drafts, step inspection does not retarget, no global composer, server actions
control availability, new-default effort behavior, normalized totals and unknown telemetry rendering.

## 8. Slice G: migration and release checks

New supervised tasks use the new owner after the coordinated release. Legacy tasks migrate only at an eligible
idle boundary. Keep manual/off tasks and observed external sessions unchanged. Migration is not a UI feature
of the mockup and must not invent model reassignment controls.

Migration order: record intent; recheck no active/uncertain work; resolve/supersede legacy pending suggestion;
save the new owner/assignment atomically; record completion. If interrupted, `task.json` establishes which
engine owns the task. Both admission paths re-read it, and stale generations cannot dispatch. A failed migration
keeps its last definite owner and reports the failure without creating another active decision.

Disable global model passes at cutover, preserve their history and code-built queue utility. Do not bulk rewrite
old usage or transcripts. Archive readers continue to show previous models and actions truthfully.

Run affected tests after each slice; run the full regression suite at final integration and `node --check` after
product JS changes. Repeat only for failures or subsequent changes. Use real-provider checks only when authorized;
record exact supported versions, task isolation, assignment persistence, context measurements, all token/cache
usage and task/global reconciliation. No rollout is complete merely because the static mockup passes.

## 9. Required implementation evidence

| Evidence | Must establish |
|---|---|
| Fake two-task run | No cross-task data/actions; both tasks contribute to one model total |
| Long-worker run | Transcript growth does not enlarge the decision packet; deeper reads obey cumulative bounds |
| Restart/interruption matrix | No duplicate dispatch, leaked credential, lost guidance or reassigned owner |
| Verification repair run | Old evidence invalidates; current goal coverage controls readiness |
| Connected-route matrix | Every admitted CLI supports the restricted runner and actual effort/usage semantics |
| Runtime/UI reconciliation | Served state/actions, visible labels, task totals and global usage agree |

No runtime evidence is claimed by writing this plan. The separate mockup agent must execute only the local
prototype work in 03 and the design cases in 04.
