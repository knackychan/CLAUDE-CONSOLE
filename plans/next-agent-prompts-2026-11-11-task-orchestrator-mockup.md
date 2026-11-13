# Prompt for the separate task-orchestrator mockup agent

Paste the block below into the design agent. The planning agent has written the architecture and implementation
contract; this prompt delegates only the local proposed mockup. No backend work is requested.

```text
Build the interactive task-orchestrator mockup specified by plan 62.

Workspace: D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE
Output: design/rework/proposed/task-orchestrator-chat/index.html
Visual inspiration: design/rework/proposed/supervision-chat/index.html

You are the separate design/mockup agent. Implement the proposed mockup and its local verification artifacts.
Do not implement the runtime, change production files/configuration, launch real agents, call Console APIs,
restart a service, publish anything or mark the design approved. The architecture being unimplemented is
expected and does not block this local mockup.

Read in this order:
1. CLAUDE.md and PLAN.md's plan 62 entry/active architecture section.
2. plans/62-task-orchestrators.md, including requirements R01-R10 and defaults D01-D15.
3. design/brainstorm/2026-11-11-task-orchestrators.md.
4. plans/62-task-orchestrators/01-runtime-contract.md.
5. plans/62-task-orchestrators/02-implementation.md for boundaries only; do not execute its runtime slices.
6. plans/62-task-orchestrators/03-mockup-contract.md.
7. plans/62-task-orchestrators/04-verification.md.
8. The complete supervision-chat/index.html, its verify.py and visual-review.txt, and relevant desktop/mobile,
   dark/light screenshots. Inspect the rendered reference or its supplied images before building.

Authority is the user's latest instruction, then plan 62's confirmed requirements and explicit contracts.
The source mockup supplies visual language, not product behavior. Older global-agent plans and mockups do not
override plan 62. Preserve the reference's identity even if a design skill suggests a different aesthetic.

Essential behavior you must preserve:
- One orchestrator owns one task. There is no global agent conversation or model reading every project.
- Keep its assigned model/CLI throughout the task. New-task assignment can rotate among eligible routes
  on connected CLIs using global usage. A disconnected/limited owner waits; no automatic model swap.
- Global effort is a default for newly assigned orchestrators. Existing tasks retain their saved effort.
- Orchestrator decisions, workers, retries and checkpoint reloads all contribute to existing global model
  usage. Role/task breakdowns are subsets, never additional charges or a separate allowance.
- Workers retain separate contexts. The orchestrator loads a bounded checkpoint and selected task evidence,
  not entire worker transcripts. Context bytes, token telemetry and archived history are different measures.
- The orchestrator chooses further steps from unmet acceptance criteria and evidence. Do not impose a
  mandatory scout/plan/code/verify pipeline or infer completion from a worker's exit alone.

Implement the specified screen hierarchy:
- Full-width Tasks overview with task cards and a code-built Needs you count; no global composer.
- On a selected task, a task-scoped Orchestrator conversation/composer on the left and Overview, Step chat,
  Context on the right, inspired by the reference's layout.
- Narrow layouts show one panel at a time, including Orchestrator as a peer view.
- One visible composer addresses the selected task's orchestrator. Worker Step chat is read-only. Inspecting
  a worker never retargets messages; drafts remain separate per task.
- New task, Orchestrator settings, Global usage and a read-only observed-session view.

Follow 03 for exact copy, state transitions, visual inheritance, responsive rules, query parameters and scope.
Follow 04 for the six task fixtures, connection fixtures, exact reconciled usage ledger, context example,
scenarios S01-S24 and checks M01-M22. Do not copy the old global drafts, recipient IDs, extra supervisor
personality or second-failure retry exception from supervision-chat.

Use plain HTML/CSS/JS with in-memory, deterministic fixture state. Work from file:// without a server or
network requests. Reuse installed/local assets only. Keep fictional sample/simulated/proposed disclosure
visible. Put scenario/theme/viewport/playback/reset controls outside the product frame. Every visible control
must work locally or show its precise unavailable reason; do not draw dead decorative controls.

Preserve chronology, expanded tools, scroll, focus and drafts during stream updates. Show submission,
orchestrator receipt and worker delivery separately. Ready is not Accepted. Paused is not Stopped. Unknown
usage is not zero. Context renewal changes the session while retaining the same owner and global usage.

Only write inside design/rework/proposed/task-orchestrator-chat/. Inspect existing contents first and preserve
unrelated work if the folder already exists. Do not modify supervision-chat, supervision-operator, web/, console/,
the architecture plan or the user's live data. Record any genuine contract gap in review.html with evidence;
do not quietly solve it by inventing a different product.

Deliver:
- index.html and any necessary local CSS/JS/assets.
- review.html: R01-R10 traceability, deliberate reference changes, scenario coverage, runtime assumptions,
  remaining limitations, and "Proposed, not approved".
- verify.py plus check-results.json with actual M01-M22 results, browser/network errors and evidence paths.
- screenshots/ covering the viewport/theme/state matrix in 04.
- source-head.txt with current HEAD and reference HTML fingerprint.
- visual-review.txt stating which images you inspected and which issues you fixed.

Build the complete mockup, run functional/overflow/keyboard/reduced-motion/network checks, inspect desktop and
mobile images in both themes, fix defects and perform a focused confirmation pass. Do not claim checks you
could not execute. Tests from the reference must be adapted to the new architecture, especially message
recipients, removed global conversation, fixed ownership and shared usage.

Finish with the clickable entry page, a concise description of the implemented views, actual verification
results, and any remaining gaps. Do not ask whether to proceed with the mockup: this prompt authorizes it.
```
