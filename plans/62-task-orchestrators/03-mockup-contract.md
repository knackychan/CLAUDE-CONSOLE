# Handoff contract for the separate mockup agent

Parent: [plan 62](../62-task-orchestrators.md). This document specifies a future design task.
The architecture/planning agent does not build the mockup. The receiving design agent owns its HTML/CSS/JS,
visual execution, local interactions, screenshots and review evidence.

## 1. Deliverable and limits

Create `design/rework/proposed/task-orchestrator-chat/index.html` as a standalone interactive prototype.
Use plain HTML/CSS/JS, inline or local files in that folder. It must work from `file://` without a server.
Read local fixture data from JS, not `fetch()` of JSON that may fail under file-origin restrictions.

Also deliver `review.html`, `verify.py`, `check-results.json`, `source-head.txt`, `screenshots/` and
`visual-review.txt` in the same folder. Tests may adapt the reference's installed Playwright/Edge workflow.
Do not overwrite that reference's verification files or treat its old assertions as the new contract.

No production source/config changes, package/dependency additions, paid calls, live CLI inspection, Console API
requests, production restart, publishing or design-lock changes. All network requests are forbidden in the
prototype, including remote fonts. Do not touch either existing proposed mockup. If the destination already
exists when the design agent starts, inspect and preserve unrelated work; never recursively replace it.

Review toolbar outside the product frame: `Task orchestration / design exploration` and
`Fictional sample tasks. Every action is simulated. Proposed design.` This disclosure stays visible in every
view. Fixtures are authored examples, not claims about the user's projects, installed CLIs, prices or usage.

## 2. What to inherit from supervision-chat

Read the complete HTML, its relevant verify cases, visual-review notes, and desktop/mobile screenshots.
Use the reference as visual authority rather than selecting a new aesthetic from a skill catalog.

Retain its compact Console chrome, cell motif, restrained surfaces, typography hierarchy, thin borders,
two-panel task arrangement, familiar task cards, chronological chat and expandable inline tool/result rows.
Preserve whitespace that distinguishes conversation from structured overview. The design agent may fix
responsive or accessibility problems without changing this identity.

Starting tokens copied from the reference:

| Token | Dark | Light |
|---|---|---|
| Page | `#0b0c0e` | `#dedcd6` |
| Window | `#121315` | `#f4f3ef` |
| Raised | `#1a1c1f` | `#e7e5e0` |
| Inactive | `#24272b` | `#d6d4ce` |
| Ink | `#ebe8e1` | `#17181b` |
| Muted | `#9a9993` | `#5f5e59` |
| Border | `#26292d` | `#d2d0ca` |
| Needs you | `#ff8a3d` | `#b84f00` |
| Error | `#ff5a4e` | `#c0352b` |
| Success | `#5ed39a` | `#1d7a4b` |

Use the existing Segoe UI/system sans stack and Cascadia Mono/Consolas stack. Reuse local font assets only
where the reference already does. Doto remains a restrained heading accent, not the reading font. No new
font package, glass panels, gradients, oversized hero, decorative metric grid or new marketing copy.
If a token fails measured contrast in a particular use, adjust that use minimally and record the change.

The reference's global Super Agent sidebar, global draft, cross-project assistant text, step-recipient composer
and old supervisor retry recommendation are behavior to replace. Changing only their labels is not sufficient.

## 3. Information architecture

```text
Tasks overview (all tasks; no agent conversation)
  -> Selected task
       Left: that task's Orchestrator conversation and sole composer
       Right: Overview | Step chat | Context
  -> New task
  -> Orchestrator settings
  -> Global usage
  -> Observed session (read-only, no assigned orchestrator)
```

Global header: Console identity, `Tasks`, `New task`, `Usage`, `Settings`, and a derived `N for you` count.
Use concise text/normal icons; the brand cell mark can stay decorative. Do not add a persistent third sidebar.
Return to Tasks to choose another task. Back navigation restores scroll/focus and all unsent task drafts.

Wide selected-task view preserves approximately the reference's 330 px conversation column and flexible
content area inside its roughly 1460 px maximum frame. At narrower widths the design agent must preserve
readability rather than compress two columns indefinitely; use the reference's 760 px collapse boundary as
the starting point. At 900 px the two-panel layout must still be usable.

On narrow windows show one peer panel at a time: `Orchestrator`, `Overview`, `Step chat`, `Context`. These panels
refer to the same selected task. Fit the navigation at 340 px using compact text/wrapping if needed; no body
horizontal overflow. Opening a task on narrow screens defaults to Orchestrator; desktop shows the conversation
beside Overview. Task questions/approvals always open or focus Orchestrator regardless of screen size.

At most one visible composer. On mobile it appears only in Orchestrator, with a `Message orchestrator` affordance
from other views. On desktop it stays in the left panel while right-side tabs change. Do not retain a hidden
duplicate focusable textarea or a separate worker-message composer.

## 4. Screen contracts

### V01 Tasks overview

Use the reference's task grid/list and project labels. Full-width overview, with no empty conversation sidebar.
Needs-you items precede active work; accepted/paused items can be in separate labelled groups. One task card
represents one task, not one orchestrator session or one worker. Global prose is deterministic status copy,
not an assistant claiming to have reviewed all projects.

Each card shows project/title, task status, fixed orchestrator model and CLI, current worker/step (if any),
latest task-level update and one primary next action. Effort and secondary metrics may be a quieter line.
Keep the cell step sequence, labelled as the currently planned steps because the plan can evolve.

Default primary actions: `Open task`, `Reply`, `Review proposal`, `Review result`, or `View reason` according
to the fixture's served state. Cards can include a compact read-only current-worker preview, explicitly labelled
as a worker preview, but it must not crowd out the task-level reason. Optional previews are off by default.

Do not show raw transcripts, context JSON, MCP tool names or byte limits on every card. An observed session
gets a separate row with `Observed session` and `Open session`, never a fabricated orchestrator assignment.

### V02 Selected task and Orchestrator conversation

Keep the selected project/task ID visible. The conversation header says `Orchestrator`, with fixed model,
CLI, resolved effort and current orchestration status. Task title sits in the shared task header/right header;
do not repeat a large title in every panel.

Show concise chronological events: user goal/guidance, orchestrator choices and reasons, worker assignment,
worker-result receipt, evidence review, next action, questions, approval outcomes and session renewal.
Detailed worker execution belongs in Step chat. Tool events may expand into a brief input/result; they do not
dump full files or hidden reasoning. Every worker event names its originating step.

Composer label: `To: T-031 orchestrator` (actual selected fixture ID). Helper text during work:
`Guidance is saved for this task and delivered at the next safe boundary.` During a question, show the question
and originating step above the same composer and use `Send answer`. Otherwise use `Send`.

Enter inserts a newline. Clicking Send or Ctrl/Cmd+Enter submits. Empty/whitespace text does nothing. Escape
dismisses an open dialog but never discards a draft or stops a task. Escape model/user text on insertion.

Sending creates a user event and visible `Queued` receipt; a deterministic simulated delivery creates a separate
`Received by orchestrator` event. If forwarded to a worker, create `Delivered to step 03` separately. Navigation
does not count as delivery. An uncertain-delivery scenario stays uncertain and cannot auto-resend.

When a question is active, optional suggested answers only fill the composer; they do not submit silently.
Approval cards have `Approve proposal` and `Reject proposal` using the existing gate meaning. Approval never
switches the orchestrator model. Rejection holds the proposal and permits a note via the task composer.

### V03 Overview

Read order: task goal/constraints; current status and next reason; acceptance criteria with evidence state;
step sequence; quiet task usage breakdown. The current worker's model is labelled separately from the owner.
Show `Orchestrator: Astra / Codex` and `Current worker: Sonnet / Claude Code` as separate roles where relevant.

Acceptance rows use `Not checked`, `Passed`, `Failed` or `Needs recheck`, with links to the corresponding sample
evidence. Ready work shows `Ready for your acceptance`; only `Accept result` changes it to `Accepted`.
Show a failed check's concrete reason and proposed repair, not a generic progress percentage.

Step rows include kind, state, worker route when assigned, and an explicit action: `Open step chat`, `View
planned step`, or `View result`. Completed/planned/running are distinct. Planned steps have no invented messages.
No draggable workflow builder or forced five-step template. Task Pause/Resume/Stop remain secondary actions
and follow the transition table below.

### V04 Step chat

Retain the reference's chronological user assignment, worker replies and expandable tools/results. Header:
step number/name, kind, actual worker CLI/model, run state and latest-output age. Include a step selector.
Completed steps show saved history; future steps show their assignment and `This step has not started`.

This view is read-only in the prototype. Footer: `Worker transcript. Send task guidance to the orchestrator.`
Its link focuses the same orchestrator composer; it does not create a worker draft or send transcript content.
This intentionally replaces the reference's step-targeted message box.

While streaming, update relevant rows in place. Preserve expanded tools, selection, keyboard focus, drafts and
scroll. Auto-follow only if the reader was already at the bottom; otherwise show `New activity`. Keep user
messages and delivery receipts in stable chronological order, including equal-timestamp events.

### V05 Context

Explain the practical boundary with `What this orchestrator receives`. Show three separate groups:

1. Current/last decision input: task goal/criteria, checkpoint, triggering result and selected evidence. Show
   source references and whether a source was included, partially included or available on demand.
2. Saved task memory: decisions/reasons, open questions/risks and next action, all scoped to this task.
3. Worker artifacts: handoff, facts and verdict links per step. Full transcripts are available in Step chat,
   with `Not automatically included in orchestrator context` stated once.

An optional details disclosure shows checkpoint/packet/read sizes and call counts. Bytes remain KiB. A token
figure, if provided, is separately labelled `Measured` or `Estimated`; unknown telemetry is `Unavailable`.
When the orchestrator is waiting for a worker, label its figure `Last decision context`, not active thinking.

Opening a file displays bounded fixture content in an inspection panel/dialog with a source title. It does not
add that file to the model's input or raise usage. Close restores focus. Omitted required context and failed
checkpoint saves show a hold with the actual reason. The task keeps its previous valid checkpoint.

### V06 New task

Fields: configured sample project, task goal, optional acceptance criteria, `Orchestrator: Auto` with an optional
explicit eligible route choice. Show the inherited global effort and actual route preview. Keep unavailable
routes visible with a reason in an availability disclosure, not as selectable enabled options.

Copy: `Assigned once when the task starts. Uses the global model usage balance.` Preview is marked provisional.
Start rechecks the fixture's live availability. An invalid explicit pick produces a named error; no silent
substitution. With no eligible route, keep the draft and disable Start with its reason.

A successful simulated Start creates a separate task ID, fixed assignment, empty task draft and initial local
event. Do not invent completed work or pretend a real CLI started. Unspecified criteria remain to be defined;
they cannot become Passed automatically. Auto may select a different eligible owner for this new task without
changing an earlier task's assignment.

### V07 Orchestrator settings

One setting: `Default orchestrator effort`, using the existing low/medium/high/xhigh/max vocabulary and fixture
adapter mappings. Default High. Save feedback: `Applies to newly assigned tasks. Existing tasks keep their effort.`
Show actual route resolution where an adapter maps a value; do not claim every CLI supports Max natively.

Below it show a read-only sample connection/capability table: CLI, connected/enabled state, models eligible for
orchestration and any exclusion reason. Do not build real connection, installation, permission or billing flows.
Connection switches belong to the external review scenario controls, not Settings.

No settings for rotating active owners, free orchestration allowance, separate model catalog, mandatory worker
pipeline, per-tool memory limits or a global-agent prompt.

### V08 Global usage

One row per normalized model. Show processed tokens, estimated cost and an expandable role breakdown:
Orchestration, Workers, Other sessions. State once that orchestration is included in the model total. Do not
add the breakdown again. Retain CLI/provider detail beneath a model where useful; quota scope is not inferred.

Use reconciled values from 04's fixture ledger. Task views show their attributed subset. `Unknown` and partial
known totals remain explicit; unknown is not zero and incomplete data cannot fill a percentage bar to 0%.
No invented subscription quota, provider reset time or savings percentage. All amounts are labelled sample
estimates, not current vendor prices. Viewing usage never changes usage.

## 5. State and action semantics

| State | Presentation | Allowed prototype effect |
|---|---|---|
| Orchestrator deciding | Active indicator on orchestrator only | Advance sample decision; owner unchanged |
| Worker running | Worker active, orchestrator `Waiting for worker result` | Inspect, queue guidance, Pause or Stop |
| Question | Needs reply, question and source step | Send answer with separate receipt/delivery |
| Suggestion | Needs approval, concrete proposed step/reason | Approve once or reject; no cap bypass |
| Paused | No new step can begin; existing worker semantics stated | Resume through current gates; queued guidance retained |
| Stopped | Current activity ended, history retained | Review/recover through explicit action; no auto-retry |
| CLI unavailable | Fixed owner still shown; named connection reason | Retain task/draft, wait; reconnect only via review scenario |
| Rate limited | Owner unchanged; reset only if fixture supplies one | Wait, inspect usage; no fallback model |
| Capacity waiting | Queued, not running | Start only after simulated capacity becomes available |
| Context renewal | `New session, same orchestrator` | New session reference/context; same route/effort, usage retained |
| Checkpoint/context failure | Named reason, last valid memory preserved | Inspect issue; no fake successful continuation |
| Uncertain dispatch | `Action outcome unknown` | Inspect; no automatic replay or optimistic extra worker |
| Budget hold | Named existing limit, no new work | Inspect usage; no automatic override |
| Ready | Current evidence complete, awaiting acceptance | Accept result explicitly |
| Accepted | History/evidence retained, no active composer | Explicit Reopen first, retain same assignment |

Pause means prevent new progression; do not falsely claim it terminated an already-running worker. Stop acts
on current execution under existing semantics and is explicit. The prototype can use a local confirmation for
Stop explaining the current worker affected. These controls must not clear unresolved messages implicitly.

Counts derive from current fixture states. A pending question/proposal/acceptance counts once per task, never
once per nested card. Background stream advances must not change another task's owner, draft or status.

## 6. Review controls and reproducibility

Outside product chrome: theme, widths, scenario picker, play/pause stream, step simulation and Reset sample.
Default load is Tasks overview, dark theme, stream paused. Reset restores fixtures, drafts, usage and settings.
Use in-memory state; reload can reset the sample. Do not persist real-looking task data into the user's app.

Support deep links with deterministic defaults:

```text
?view=tasks&theme=dark&stream=paused
?view=task&task=thumbnails&panel=overview&theme=dark&stream=paused
?view=task&task=thumbnails&panel=step&step=3&theme=light&stream=paused
?view=task&task=thumbnails&panel=context&scenario=renewal&stream=paused
?view=new | ?view=settings | ?view=usage | ?view=observed
```

Validate unknown query values and fall back to a safe default. Review-only scenario IDs are listed in 04.
Do not put scenario selectors in the product settings or task content. Use stable `data-*` identifiers for
tests without making technical IDs visible to product users.

## 7. Accessibility and rendering

Use semantic controls with visible focus and accessible names. Tabs expose selected state and keyboard
navigation; dialogs manage focus/Escape/return. State is conveyed in words as well as color. Announce concise
delivery/state changes politely, not every streamed token. Hidden panels are not focusable.

Respect reduced motion; paused fixture playback stops all simulated updates. Keep controls usable at 340 px,
400 px and short 760 px windows; scroll content, not the composer off the accessible surface. Long titles,
paths, tool output and model names wrap or scroll within their own bounded area. No page-wide overflow.

The design agent must inspect desktop/mobile and both themes, then fix observed issues. The verification
matrix is functional and architectural; it does not replace visual judgement or claim design approval.
