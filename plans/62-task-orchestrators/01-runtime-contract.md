# Runtime contract

Parent: [plan 62](../62-task-orchestrators.md). Status: specified target, not shipped behavior.
This contract governs the meaning of the UI as well as the future runtime.

## 1. Roles and authority

| Role | Owns | Cannot do |
|---|---|---|
| User | Goal, constraints, reserved decisions, acceptance and settings | Nothing here removes existing manual controls |
| Service | State, routes, shared limits/usage, tool scope, dispatch and recovery | Delegate validation or accounting authority to model prose |
| Task orchestrator | One task's interpretation, worker choices, result review and continuity | Read all projects, change its assignment or grant itself permissions |
| Worker | One bounded assignment, execution and handoff | Inherit orchestrator credentials or create an uncontrolled agent hierarchy |

The old supervisor and new orchestrator are successive implementations of the same decision role. Exactly one
engine receives decision wakes and dispatch authority for a migrated task. Do not overload the existing
`task.owner` field, which already distinguishes human and system responsibility, with the new engine identity.

## 2. Assignment and effort

Assignment is a service action performed on first Start:

1. Enumerate enabled/configured routes through the existing harness registry and model configuration.
2. Require executable/connection availability, a suitable think-capable model, supported effort and proven
   restricted-tool support. An installed CLI alone does not prove orchestration capability.
3. Apply route limits and existing admission gates. Retain the reason for each exclusion.
4. Auto uses existing global fill/balancing and tie behavior among eligible routes. An explicit pick is
   validated and never silently substituted. There is no independent round-robin scheduler.
5. Persist route, normalized model key, requested/resolved effort and assignment reason before launch.
   A creation-time preview is provisional; a changed actual assignment must be visible when Start completes.

Workers may use other routes. Decisions, retries, context renewals and recovery retain the orchestrator's
saved route. A disabled, removed or rate-limited owner waits; reconnecting permits resumption through current
gates. New global effort/model-pool changes do not alter existing assignments. v1 has no automatic fallback.

The global default uses the configuration whitelist and adapter effort mapping. Show the actual resolved value.
Do not invent an unsupported provider label. Without a safe mapping the route is ineligible with a reason.
Changes apply to future assignments; worker effort policies remain independent.

## 3. State and storage

Add optional metadata so legacy tasks remain readable. The following is the structural contract; reuse existing
run/session IDs, event IDs and revision mechanisms rather than creating parallel registries.

```text
task.orchestrator
  schema_version: 1
  assignment:
    rung: configured harness/model route
    model_key: existing fills.model_key result
    effort_requested: saved default or explicit creation choice
    effort_resolved: adapter-supported value
    assigned_at: timestamp
    reason: bounded service-generated explanation
  generation: monotonically increasing decision generation
  current_turn: existing run/pass reference or null

task.acceptance[]
  id: stable within this task
  text: criterion
  source: original request/plan/user-decision reference
  status: unknown | pass | fail
  evidence: accepted artifact references
  checked_basis: revision actually checked, or null
```

An exposed `checkpoint_revision` is derived from the accepted checkpoint file, not a second authoritative
pointer that can disagree after an interrupted save. The checkpoint contains its own source basis/version.

Derive labels, attention counts and totals from canonical records. Do not persist independent competing copies
of UI status. Requirement changes are explicit revisions. User acceptance remains an existing user action,
not another model-authored criterion value.

| Path under the task folder | Producer | Purpose |
|---|---|---|
| `task.json`, `prompt.md`, existing plan files | Service | Canonical state, original request and plan |
| `chain.jsonl`, `supervisor.jsonl` | Service | Transitions and intent/outcome audit |
| `orchestrator/checkpoint.json` | Validated model proposal, service-published | Bounded working memory |
| `orchestrator/<wake>/received.md` | Service | Exact admitted input and coverage |
| Existing run records/transcripts | Runner | Full conversation for inspection/accounting |
| `<step>/received.md` | Existing prompt builder | Worker assignment and selected inputs |
| `<step>/handoff.md`, `brief.md` | Existing handoff flow | Original result and compact derivative |
| `<step>/facts.md`, `verdict.md` | Existing fact/verdict flow | Evidence and checked revision |

Use the existing Console data home, legacy step readers and atomic writer. No duplicate repository or full
transcript copy in the checkpoint. An atomic-write failure holds progression; no in-place fallback. Plan 60's
alternative file producer remains separate and is not required for this design.

## 4. Checkpoint and evidence

Checkpoint fields: schema/task/source revision; concise progress; still-relevant decisions with reasons and
primary sources; unresolved questions/risks/failed approaches; next intended action and the criterion it serves;
incorporated result IDs and references to older omitted evidence.

Do not put authoritative spend, assignment, permission grants, full transcripts or hidden chain of thought in
the checkpoint. Code rebuilds facts and gates. Reject malformed, oversized, cross-task or stale proposals and
preserve the previous valid checkpoint. Missing artifacts are unknown evidence, never successful empty results.

Original goals, decisions, troubleshooting, handoffs and facts remain available in full. The checkpoint does
not erase them. Consequential or disputed claims lead to targeted reads of original evidence, not repeated
summarization of earlier summaries. Worker handoffs retain the six existing headings and whole Goal and
Troubleshooting contract. The existing brief target of about 500 words is a target, not permission to cut rules.

Acceptance evidence names criterion, worker/run, artifact and checked result basis. Writing changes invalidate
affected verification. In v1, conservatively invalidate code-result verification after a writing step when
precise dependency information is unavailable; do not add a dependency graph. Non-code criteria can rely on
artifact inspection or a recorded human decision. Schema-valid provenance alone does not prove correctness.

`Needs recheck` is a read projection of previously passed evidence whose basis is stale. Canonical current
status is unknown until rechecked; retain the old pass and source in history rather than rewriting history.

## 5. Decision lifecycle

| Phase | Required behavior |
|---|---|
| Wake | Coalesce task-specific messages/boundaries/results using existing event identities. No model polling. |
| Admit | Claim one generation; check decision owner, guidance, route, permissions, limits and reservation. |
| Assemble | Consistent task snapshot, bounded packet, coverage and exact admitted-input record. |
| Run | Fresh session on fixed route, task-bound tools only; visible concise rationale/action events. |
| Decide | Smallest useful next action based on unmet criteria, evidence and available actions. |
| Checkpoint | Validate and atomically persist memory against the expected revision before a worker launch. |
| Dispatch | Recheck live gates/revision; persist intent, invoke existing Hub path, persist outcome. |
| Yield | End decision process and await event/worker/user without spending model tokens. |
| Reconcile | Settle usage once; recover known effects and hold uncertain outcomes without replay. |

A checkpoint write or action can change a revision. Tool responses return the current revision, which later
mutations must use. Checkpoint intent is not proof an action occurred; the audit records the effect. After
restart, reconcile the audit and current state before following the checkpoint's proposed next action.

Choose steps adaptively. An explicit small fix can go directly to code; uncertain behavior may need scout;
larger changes may need design; failed verification can need a focused repair. Every assignment names the
intended result and how to check it. There is no mandatory five-stage ceremony.

At every action preserve Pause/off, guidance ordering/uncertainty, questions, caps, permissions, revision and
dispatch holds. Existing retry/step limits remain ceilings. Renaming an ineffective retry as a new step or task
must not reset its lineage/caps. Worker activity does not require a simultaneously thinking orchestrator.

On migrated tasks, a completed worker first passes the existing end/handoff/facts validation, then produces
an orchestrator wake. Legacy automatic chain advancement must not launch the next planned worker behind the
new owner's back. The orchestrator can authorize the existing next planned step through the same launch gates;
it does not have to append a duplicate. Invalid/missing worker output produces a failure event with bounded
diagnostics, never accepted evidence. User guidance during a worker run can wake a decision for that message,
but cannot bypass the one-worker limit or dispatch an incompatible second worker.

## 6. Context budget

Packet priority:

1. Mandatory: identity, authoritative goal/constraints, relevant acceptance, active guidance, allowed actions
   and remaining limits.
2. Current: validated checkpoint, triggering worker result and relevant verification evidence.
3. Selected: older decisions/artifacts needed now, with source IDs and explicit omitted coverage.

If mandatory content cannot fit, hold for a bounded scope/plan split. Never silently clip requirements. Optional
exclusions list source IDs, sizes and reasons. Do not claim a decision examined evidence it did not receive.

| ID | Prototype bound | Enforcement |
|---|---|---|
| C01 | Checkpoint 8 KiB UTF-8 | Validate serialized size; reject instead of truncating JSON or facts |
| C02 | Initial packet 32 KiB UTF-8 | Includes role, rules, tool descriptions, envelopes and task content |
| C03 | Each artifact response 8 KiB UTF-8 | Sections/pages plus source, coverage and continuation metadata |
| C04 | Additional tool results 16 KiB UTF-8 per decision | All delivered envelopes, repeated reads counted again |
| C05 | Six calls per decision | Failed/duplicate calls also count; no free retry loop |

These are initial engineering constants, not five public settings or exact token guarantees. Generated text,
tool arguments/history, adapter output/turn limits and reserved output room also matter. Provider context
telemetry is distinct from byte size. No universal bytes-to-tokens estimate is a correctness boundary.

Fresh decision sessions avoid a growing task-long conversation. Reuse is deferred until full context can be
metered safely. At allowance exhaustion return a small explicit result inside reserved room, yield and name
missing evidence. Do not secretly create another same-wake session to reset the allowance. A later admitted
continuation needs a recorded reason/event and still consumes task/day limits.

Renewal preserves task identity, model/CLI, effort, files and acceptance. The UI can say `New session, same
orchestrator`. Context describes the active session, not archived history size. Unknown context is `Unavailable`.
File storage saves tokens only when loading is selective; actual savings require measurement.

## 7. Restricted tools

These names specify the proposed capabilities, not existing endpoints. Map them to existing service methods;
the UI uses ordinary action descriptions rather than exposing MCP schemas.

| Tool | Input | Result/effect |
|---|---|---|
| `task_state` | No task selector | Scoped state/revision, criteria, allowed actions and remaining room |
| `read_artifact` | Artifact ID, section/page handle | Bounded content, source revision, coverage and continuation |
| `prepare_step` | Existing kind, assignment, source IDs, worker route preference | Existing preview/revision; starts nothing |
| `act` | Served action ID or prepared step reference, revision, request ID | Gated effect, refusal or user decision requirement |
| `save_checkpoint` | Bounded proposal, revision | Accepted checkpoint reference/current revision or error |
| `ask_user` | Bounded question/reason, optional answers | Existing task question flow; no worker launch |

Bind credentials server-side to task, generation and capability set. A tool cannot choose another task, an
arbitrary path/cwd or shell command. Resolve artifact IDs from service-owned metadata; enforce canonical
containment, regular-file validation and defenses against absolute paths, symlinks and junctions. Rejecting
`..` alone is insufficient. Workers do not receive orchestrator credentials.

Expiry/revocation/generation checks invalidate stale credentials after completion, restart and relevant user
controls. Artifact text cannot change those rules. Do not log credentials or MCP config containing secrets.
This scope does not replace worker OS/project sandbox enforcement.

Preserve action availability, origin semantics, idempotent requests, intent-before-effect and reserved user
actions. Do not import plan 61's exceptional cap overrides. Validate installed CLI restrictions/output behavior
before admitting a route; worker support alone is not proof of restricted orchestration support.

## 8. Global usage and limits

One run/turn identity owns each usage record. Task and role (`orchestrator`, `worker`, `other`) are attribution.
Global/model/task/role totals are projections of those records, not charges to add together.

- Normalize with existing `fills.model_key`; retain actual harness/provider identity.
- Count decisions, workers, retries, paid failures and checkpoint reload input.
- Preserve provider input/output/cache semantics. Do not add cache twice when included in input totals.
- Correlate stream/hook/transcript observations. A session can have multiple turns; session ID alone may not
  deduplicate correctly. Use existing turn identity/sequence semantics.
- Include reservations in admission and replace them with settlement rather than adding both.
- An ended process with missing usage is pending/unknown, never invented zero. Unknown price can coexist with
  known tokens. Estimated costs are labelled estimates.
- Reuse global time windows/reset semantics. A role does not get a separate allowance or reset clock.
- Provider-specific limits retain their real scope even when model usage is normalized across CLIs.

The owner can wait while unrelated tasks continue. Unmeasured orchestration cannot appear less used than
measured models. Current separate supervisor/super Usage projections must be audited; do not assume they
already feed the new global balancing path correctly.

## 9. Messages and UI truth

All task messages address that task's orchestrator. Preserve queued/live/uncertain delivery, ordered persistence
before acknowledgement and visible receipts. User submission, orchestrator receipt and worker delivery are
separate events. Opening another step/artifact/task does not reroute queued content.

Worker questions surface through the orchestrator with the source step identified; answers keep the question
identity. Pause retains queued messages. Stop/retry/finish preserve existing resolution requirements. The mock
must not erase guidance simply to make a transition convenient.

`Worker running` can coexist with `Waiting for worker result`; do not animate the orchestrator as thinking
during that wait. Verification pass is not acceptance. Ready tasks retain `Accept result`; accepted tasks need
explicit reopening before a new message can create more work.

## 10. Migration

1. Land optional readers/schema first so legacy tasks remain usable.
2. Migrate only at an idle safe boundary, without active worker/decision, uncertain effect or unresolved guidance
   dispatch. Preserve questions and explicitly resolve or supersede old suggestions.
3. Record new engine ownership and assignment before accepting a new wake. Restart restores that owner.
4. Disable the global model pass on cutover; preserve its history and useful deterministic overview functions.
5. Never rewrite old spend, transcripts, handoffs, user-customized kind files or CLI configuration.
6. Manual/off tasks and observed external sessions retain their existing behavior; a visible external session
   does not acquire an orchestrator automatically.

Actual CLI capability, metering, cost/latency and provider context controls need implementation evidence. They
do not authorize a mockup builder to invent alternative product behavior.

## 11. Task read projection and action results

Extend the existing task response rather than adding competing read APIs. Names below describe the required
view contract; retain existing fields wherever equivalent. Reads never mutate state or wake a model.

| Projection | Required content |
|---|---|
| Assignment | Saved route/model/CLI labels, requested/resolved effort, assigned-at/reason; unavailable reason kept separate |
| Orchestrator activity | Idle/deciding/waiting/held with precise reason; current or last turn ID; no full hidden reasoning |
| Current worker | Step/run identity, route, kind, actual execution state, last output time; null when none |
| Acceptance | Stable criterion IDs, current status, evidence references and stale-basis indicator |
| Context | Current/last packet identity, source coverage, byte/call counters and separately known/estimated/unknown token telemetry |
| Usage | Attributed settled/unknown/reserved amounts and role breakdown; references the shared accounting source |
| Conversation | Ordered task events with actor/source, recipient, delivery state and monotonically stable sequence |
| Actions/message | Existing served availability/disabled reasons and destination; authoritative for product UI |

Every model-proposed mutation validates field types, enum membership, bounded lengths, identifier ownership
and expected revision/generation before effects. Reject unknown fields on tool inputs so typos do not become
ignored instructions. Numeric limits must be finite and nonnegative where applicable; booleans are not counts.

Action results distinguish these meanings; adapt the existing HTTP status/response conventions without
inventing a parallel error protocol:

- `done`: effect confirmed, current revision and resulting entity ID returned;
- `refused`: no effect, with the live gate/revision/validation reason;
- `needs_user`: no effect, existing question/approval identity returned;
- `uncertain`: intent exists but effect cannot be established, dispatch held and never automatically retried.

Idempotent repeated requests with the same content return the recorded outcome/entity. Reusing an ID with
different content is refused. A read retry can be retried inside remaining context/call limits; a mutation
timeout is not permission for a fresh request ID. Reconcile it first.

Display freshness separately from correctness. A stale last-known snapshot may remain visible with an offline
label, but it does not enable actions. No frontend recomputation of gates from model prose or status colors.
