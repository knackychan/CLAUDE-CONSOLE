# Plan 62: One orchestrator per task

Status: **detailed implementation and mockup contract, 2026-11-11; not implemented.**
Fred requested this expansion to prevent design drift and give a fresh agent a precise mockup brief.
The mockup is a separate, immediately actionable design task. It does not implement the backend.

Design origin: [task orchestrators](../design/brainstorm/2026-11-11-task-orchestrators.md), BRAINSTORM D20.
Visual reference: [supervision-chat](../design/rework/proposed/supervision-chat/index.html).

## 0. Read order and authority

1. `CLAUDE.md`, this file, and the task-orchestrator design above.
2. [01-runtime-contract.md](62-task-orchestrators/01-runtime-contract.md): ownership, assignment, files,
   context, tools, usage and recovery. Defines what the interface may truthfully imply.
3. [02-implementation.md](62-task-orchestrators/02-implementation.md): integration boundaries and ordered work.
4. [03-mockup-contract.md](62-task-orchestrators/03-mockup-contract.md): destination, inherited visual system,
   screen hierarchy, states, labels and interaction behavior.
5. [04-verification.md](62-task-orchestrators/04-verification.md): fixtures, scenarios, checks and evidence.

Mockup builders read all five but execute only the mockup contract and its verification cases. Their
copy-ready instruction is [the mockup prompt](next-agent-prompts-2026-11-11-task-orchestrator-mockup.md).

Authority, highest first: Fred's latest instruction; confirmed requirements R01-R10; this plan's explicit
contracts; the earlier brainstorm for rationale; the reference HTML for visual language only. Plans 58/59/61
are historical global-agent contracts and sources of reusable gates/audit patterns, not the new UI target.

The UI choices below are specified defaults made to fulfill this planning request. They are not a claim
that Fred has visually approved a mockup. Implement them rather than silently redesigning them. If a requirement
proves impossible, record evidence and the smallest alternative in the review. Routine layout fixes need no
new approval. Never mark the visual design locked just because automated checks pass.

## 1. Confirmed requirements

| ID | Requirement | Drift to reject |
|---|---|---|
| R01 | One logical orchestrator per supervised task. | A model manages all projects or supervises another task supervisor. |
| R02 | Keep the assigned orchestrator model throughout the task. | Alternate models per step, silently fail over, or switch on context renewal. |
| R03 | New assignments use eligible models on connected CLIs. | A hardcoded Astra/Opus pair or unavailable options presented as usable. |
| R04 | A global setting controls default orchestrator effort. | Editing every task separately or altering worker effort as a side effect. |
| R05 | Orchestrator usage contributes to existing global model usage. | Free orchestration, a separate pool, omitted reload tokens or duplicate totals. |
| R06 | The orchestrator assigns workers appropriate to the goal. | A fixed mandatory scout/plan/code/verify ritual or passive status-only orchestration. |
| R07 | Further steps depend on unmet goal/acceptance criteria. | Finish on process exit alone or retry indefinitely despite limits. |
| R08 | Worker contexts stay separate; task files provide necessary results. | Automatically inheriting transcripts or every previous handoff. |
| R09 | Bound all orchestrator input, including tool reads. | A small seed followed by unlimited artifact reads. |
| R10 | Mockup derives from supervision-chat and lives in proposed/. | Overwriting the reference, inheriting its global semantics, or inventing a new visual system. |

Fred corrected the earlier checkpoint-model-switch answer. The final choice is R02. Restarting a CLI process
on the same saved route is context renewal, not model rotation.

## 2. Specified defaults

| ID | Default |
|---|---|
| D01 | Assign at first Start, persist before the first model call. Creation previews are provisional. |
| D02 | Resolve/save global effort at assignment. Later default edits affect future assignments only. |
| D03 | Apply existing global fill/routing policy among eligible think-capable routes. Explicit picks remain explicit. |
| D04 | An unavailable assigned route waits with its reason. No automatic reassignment. |
| D05 | A fresh bounded decision session per wake, on the same model. Session reuse is a later measured optimization. |
| D06 | One active decision and one worker at a time per task in v1; separate tasks may run under shared limits. |
| D07 | Canonical state and memory are service-owned task files. No new database or global memory agent. |
| D08 | The global view is a code-built overview/Needs you queue with no model conversation. |
| D09 | One orchestrator composer per selected task. Step chat is an inspection surface in this mockup. |
| D10 | Preserve the wide reference layout: task-scoped conversation left, task content right. |
| D11 | Right-hand views: Overview, Step chat, Context. Narrow screens add Orchestrator as a peer view. |
| D12 | Preserve autonomy, user-reserved actions, ordered guidance, retry/spend limits and uncertainty recovery. |
| D13 | Model reassignment controls, parallel workers, jobs/worktrees and cross-task imports are outside the mockup. |
| D14 | Prototype bounds: 8 KiB checkpoint, 32 KiB initial packet, 8 KiB/read, 16 KiB additional responses, six calls/decision. These are not token guarantees. |
| D15 | Mock behavior is local, deterministic and visibly simulated. No production API, live CLI or provider calls. |

## 3. Scope map

| Area | Reuse/integration points |
|---|---|
| Task/persistence | `console/tasks.py`, `console/paths.py`; optional metadata, existing folders and atomic saves |
| Decision ownership | `console/supervisor.py`, Hub admission/snapshot/completion/recovery and task guidance |
| Worker dispatch | `preview_next`, `request_next`, `start_step`, existing kinds, runs and harnesses |
| Context | Existing handoffs, `console/compact.py`, `console/facts.py`, prompt/plan files and source references |
| Restricted tools | `console/guard.py`, Hub actions; task-scoped adaptation of plan 61's unbuilt MCP concept |
| Model/effort | Harness registry, `console/claude_cli.py`, fills, limits and tuning whitelist |
| Accounting | `console/usage.py`, fills, Hub usage views and run/hook/transcript readers |
| Global role retirement | `console/superagent.py` and callers; preserve history and deterministic queue functions |
| Future product UI | `web/app.js`, `web/style.css`, after separate mockup review |
| Mockup only | `design/rework/proposed/task-orchestrator-chat/`, plain HTML/CSS/JS and local fixtures |

Plan 60's worker-written file transport remains separate. Existing service-published handoff files suffice.
A mocked feature is not a backend capability merely because the prototype depicts it.

## 4. Definition of done

Planning: every confirmed requirement has explicit behavior and verification; runtime and visual contracts
are separated; the mockup has a destination, reference tokens, screens/states, interaction rules and fixtures;
a fresh agent can follow the prompt without guessing rotation, context, usage or message destination.

Mockup: all specified views/scenarios render, transitions follow the local state contract, screenshots are
inspected, and delivery includes entry page, review, results, screenshots and reference provenance. No visual
approval or runtime integration is claimed.

Runtime: each slice in 02 passes its focused checks before enabling further effects. Global usage counts once;
code enforces scope and ownership; legacy/new engines cannot dispatch together. Real CLI controls are proven
before cutover. Mock checks never count as runtime evidence.

## 5. Drift rules

- No global assistant, cross-project reasoning thread or duplicate supervisor personality.
- No worker-model change presented as orchestrator rotation; no silent mid-task reassignment.
- No transcript selection that retargets the composer, or drafts shared between tasks.
- No context bytes labelled as tokens, archived history as current context, or unknown usage as zero.
- No queued message marked delivered, planned worker marked running, or ready task marked accepted prematurely.
- No copied global draft/recipient IDs, obsolete retry exceptions or cross-task tools from the reference.
- No additional quota controls, workflow editors, memory services or settings beyond the specified surface.
- Fixture controls live in the external review toolbar, not inside the product UI.
- Do not edit production, the reference, the sibling supervision-operator mockup or unrelated plans.

## 6. Change record

- 2026-11-11: initial architecture direction and implementation outline recorded.
- 2026-11-11: expanded at Fred's request into runtime contract, execution plan, mockup contract, verification
  matrix and standalone build prompt. Reference HTML and supplied desktop/mobile screenshots inspected.
