# One orchestrator per task (2026-11-11)

Status: **new architecture direction requested by Fred; design and migration plan, not implemented.**
Supersedes the shared reasoning role in D18/D19 and plans 58, 59 and 61. Existing shipped behavior is still
described by those plans until migrated. Detailed implementation contract: [plan 62](../../plans/62-task-orchestrators.md),
expanded with runtime rules, implementation slices, a separate-agent mockup brief and verification cases.

## 1. Decisions from this conversation

- Each task has its own orchestrator, context and durable memory. No model supervises every project's work.
- The orchestrator can create worker sessions for scouting, planning, implementation, verification and repairs,
  choosing further steps when the task's goal remains unmet.
- **Keep the same orchestrator model for the whole task.** Fred corrected his earlier checkpoint-switch answer.
  Rotation applies when assigning new tasks, not between steps of a running task.
- Assignment uses the actual connected, enabled CLIs and their available models. Astra and Opus are examples,
  not a hardcoded pair or a promise that either is available on this machine.
- Fred can set the global reasoning effort for orchestrators.
- Orchestrator usage counts toward the same global model usage as all other sessions. Isolated context does
  not mean a separate allowance, token pool or balancing score.
- Workers retain their own contexts. The orchestrator receives necessary results through task files rather
  than loading worker conversations wholesale.

The remaining mechanics below are proposed defaults, not claims of shipped behavior or measured savings.

## 2. Ownership and execution

```text
Console service: shared usage, eligible routes, limits, events and task overview
  |
  +-- Task A / fixed orchestrator model A / Task A memory
  |     +-- scout session -> handoff + evidence
  |     +-- implementation session -> handoff + evidence
  |     +-- verification session -> verdict + evidence
  |
  +-- Task B / fixed orchestrator model B / Task B memory
        +-- whichever worker steps Task B needs
```

The service coordinates execution in code. It can show all tasks and arbitrate shared capacity without
putting their contents into a global model prompt. Only one orchestrator turn can act on a task at a time.
One durable orchestrator identity belongs to that task, even if its CLI process ends between turns.

The orchestrator owns the goal, acceptance criteria, choices and follow-through. Workers own bounded pieces
of work. The service owns validation, launches, budgets, permissions, persistence and recovery. Worker kinds
use the existing task kinds; they do not recursively create another uncontrolled agent hierarchy.

A turn wakes on a task message, a worker result, failure, question or an existing eligible boundary. It:

1. Reads the task's bounded state packet and the new result.
2. Checks progress against explicit acceptance criteria and the evidence available.
3. Dispatches the next needed worker, requests a decision, or records readiness for acceptance.
4. Saves its checkpoint and yields while the worker runs. No model polling loop consumes tokens while waiting.

Scouting and planning are optional when the task already supplies enough information. Verification checks
the actual goal, not just whether the worker exited successfully. A failing check can lead to a focused repair
and another verification. Missing evidence stays unknown. Existing step, retry, spend, guidance and autonomy
gates still apply; an unmet goal is not permission for unlimited retries or silently expanded scope.

For the first implementation, keep the existing sequential step chain within each task. Separate tasks may
run concurrently within shared limits. Parallel workers within one task and writer worktrees remain separate
work; the architecture does not require a new task graph or scheduler.

## 3. Assignment, effort and shared usage

At task start, the service obtains eligible orchestrator routes from enabled harnesses, configured models,
current availability and demonstrated support for the required scoped tools. Reuse `harness`, `rung_ok`,
`limits` and `fills` rather than maintaining a second model catalog. The current adapters are a starting point;
worker support alone does not prove that a CLI can run this orchestrator's restricted MCP session.

Reuse global usage balancing when selecting among eligible models. Assignment happens once and the resolved
harness/model is persisted on the task. Later steps, retries, restarts and context renewals retain it. Explicit
model picks remain explicit. If the assigned route is limited, disconnected or removed, wait with the reason;
do not silently swap models. Any user-requested reassignment is an explicit exception, recorded on the task.

The global orchestrator effort is a default resolved through each adapter's supported effort mapping and saved
on task creation. Display the actual resolved effort. A global default change applies to new tasks; it does
not silently alter existing tasks or worker effort policies. Effort does not change context or spending caps.

Every orchestrator turn, retry and context renewal is metered using its actual model, alongside workers and
ordinary observed sessions. Reuse `fills.model_key` so the same normalized model across CLIs contributes to
the existing shared fill. Retain provider-specific rate-limit scope; a shared display total does not imply
that separate providers share a billing account or quota.

Usage needs one accounting identity per run/turn. Task and role breakdowns are views of the same records,
not additional charges added to the global total. Count input, output and cache usage under existing
semantics; a checkpoint reload still consumes input. Reconcile terminal events, restarts and hook/transcript
observations without double counting. Missing measurements remain unknown, never zero. Reservations and
active runs participate in shared admission so simultaneous assignments do not ignore in-flight work.

This is a real integration change: today's supervisor/super pass ledgers have separate Usage projections.
Do not assume those projections already feed global model balancing correctly for the new runner.

## 4. Files are the task's memory

Reuse the current task directory under `CC_CONSOLE_HOME` or `~/.claude/console/`:

```text
tasks/<task-id>/
  task.json                     authoritative task/step state, fixed route, effort, acceptance status
  prompt.md                     original request, preserved
  plan.md / plan/                existing plan artifacts, when the task has a plan
  chain.jsonl                    existing event and action history
  supervisor.jsonl              existing per-task decision/dispatch audit
  orchestrator/
    checkpoint.json             bounded decisions, open issues and source references
    <wake>/received.md           exact assembled input for this decision
  01-scout/                     existing step layout
    received.md                 worker's assigned goal and selected input
    handoff.md                  validated result under the existing six headings
    brief.md                    existing compact handoff, where available
    facts.md / verdict.md        code-read facts and verification evidence
    notes.md / notes.<k>.md      detailed output and failed-attempt records
  02-code/ ...
  03-verify/ ...
```

The service owns canonical files and uses the existing atomic writer. No duplicate copy of the repository,
new database, vector store or global memory agent is needed. Use existing run transcripts for deep inspection;
do not duplicate them into the checkpoint. Existing legacy step paths remain readable.

The checkpoint is a small working view, not a replacement for primary evidence. It records the source task
revision, decisions with reasons and source references, unresolved risks/questions, and the intended next
action. Code-owned state, costs, route and acceptance entries are rebuilt from authoritative records rather
than accepted from model-written prose. Preserve past decisions in the task's audit and plan artifacts.

Each acceptance criterion has a stable identity and references the relevant evidence and checked revision.
A later implementation change invalidates verification that no longer covers the current result. An old
successful test or a confident summary cannot mark a changed task ready.

Workers receive only their assignment, applicable task/project rules, relevant decisions and selected prior
artifacts. They return the existing six-heading handoff: Goal, Findings, Files touched, Troubleshooting,
Open questions and Next. Findings distinguish observations from hypotheses and name the source/test evidence.
Detailed findings can remain in task artifacts with references from the handoff.

Use the existing approximately 500-word brief target as a starting point, while preserving the current whole
Goal and Troubleshooting contract. Never truncate required content merely to meet a target. `facts.md` and
original handoffs remain intact on disk. A summary with missing evidence triggers a targeted read or worker
investigation, not a guessed conclusion or another summary of a summary.

This architecture can consume today's service-published handoffs. Plan 60's worker-written `handoff.md`
transport remains separate, with its existing open decisions. It is not silently implemented by this design.

## 5. Bounded context, including tool results

Each decision starts with the task goal and active constraints, acceptance status, current checkpoint, new
worker result, live allowed actions and remaining limits. Older completed steps appear as references and
status entries; their full handoffs and transcripts are not appended to every prompt. Project rules are
scoped to this task's configured project. Cross-task evidence requires an explicit, recorded import.

Proposed initial bounds for a prototype, to be measured before settling defaults:

| Input | Bound and handling |
|---|---|
| Checkpoint | 8 KiB UTF-8; validate replacement, preserve prior valid checkpoint on failure |
| Initial decision packet | 32 KiB UTF-8 including role, tool descriptions and task content |
| Artifact read | 8 KiB UTF-8 per response, including its envelope and coverage information |
| Additional tool responses | 16 KiB UTF-8 cumulative across one decision, not per call |
| Tool loop | At most six calls per decision; checkpoint/yield or report the missing evidence at the bound |

Byte bounds are enforceable payload limits, not token counts. Provider token/context measurements, generated
text and tool-call history must also be included when deciding whether a session has room for another call,
with a reserved output allowance. Do not claim an exact token ceiling from a characters-per-token guess.
Adapters must prove the necessary controls before enabling session reuse.

The simplest first runner starts a fresh bounded decision session at each wake, on the task's **same model**,
from its checkpoint and current files. That preserves the same logical orchestrator without accumulating a
task-long transcript. Later, reuse short sessions only when total context can be metered and kept below the
budget. Renew at a safe boundary with the same model before the limit, rather than depending on emergency
compaction. Compare actual cached input, total tokens and latency before choosing reuse as an optimization.

If required goal/constraints/acceptance content cannot fit, make the incomplete coverage visible and hold
the decision for a bounded scope/plan split. Do not cut instructions silently. Optional artifacts are selected
by relevance with omitted IDs listed. Reads are server-bounded sections or pages with continuation handles;
the cumulative allowance prevents reconstructing a huge transcript through many small reads.

Publish a validated checkpoint against the expected task revision before starting a new decision session.
If publication fails, keep the last valid state and hold progression. A stale session cannot overwrite a
newer checkpoint or dispatch a step. Each completed action is recoverable from the audit independently of
whether the model had time to summarize it.

Files alone do not save tokens: the saving comes from selective, bounded loading. This design avoids growth
proportional to accumulated worker transcripts; actual token and dollar savings need measurement.

## 6. Scoped tools and reliable effects

The initial tool surface should stay small:

| Capability | Existing foundation |
|---|---|
| Read current task state and available actions | `Hub.actions`, supervisor snapshot and existing task reads |
| Read a selected task artifact/section | Existing task files, with bounded access and explicit coverage |
| Prepare/start a worker step | `preview_next`, `request_next`, `start_step`, existing kinds and harnesses |
| Propose or execute an allowed task action | Existing Hub routes, autonomy gates and revision checks |
| Save a checkpoint or ask Fred | Atomic persistence and the existing task guidance/decision machinery |

Bind each tool credential to one task and decision generation on the server. Tool arguments cannot select
another task, arbitrary shell command, cwd or file path. Artifact IDs resolve against service-owned task
metadata with canonical path containment and link/junction checks. Model-supplied text and file contents
remain untrusted data. Workers do not receive the orchestrator's credential or inherited full conversation.

Every mutation rechecks current task state, guidance, mode, budget and revision. Keep intent-before-effect
auditing, idempotent request IDs and uncertain-dispatch holds. Failed or late outputs cannot advance a task.
Existing actions reserved for Fred stay reserved; reporting acceptance evidence does not bypass Finish or
Accept. The new owner replaces the legacy supervisor on migrated tasks so both cannot dispatch the same work.

## 7. Interface and migration

The global view becomes a code-built task overview and Needs you queue. Selecting a task opens its own
orchestrator conversation, fixed model/CLI, effort, current step and next reason. The message destination
must be explicit. With no task selected, the composer creates/selects a task rather than implying a global
agent conversation. Worker transcripts remain available behind their steps.

Show task cost with an orchestration/worker breakdown and the shared global model usage. Context indicators
describe the active orchestrator session, not the size of the task's history on disk.

Plans 58/59/61 contain reusable queue, action, audit and chat ideas, but their shared agent role and global
conversation are superseded. Preserve old records. Migrate at an idle task boundary, drain any legacy pending
decision, and persist the new owner before allowing a turn. Never run both decision engines for one task.
Existing manual/off tasks and external observed chats retain their controls. Jobs/worktrees remain separate.

The two proposed supervision mockups in the IDE still depict global supervision. This session records their
required change in scope; it does not alter either untracked mockup or declare a new visual design locked.
