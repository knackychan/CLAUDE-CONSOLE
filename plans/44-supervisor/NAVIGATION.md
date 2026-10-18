# Task navigation and handoff redesign

Date: 2026-10-17. Status: implemented 2026-10-17 (the navigation slice, [navigation/](navigation/README.md) Tasks 1-5); the plan 44 supervisor backend is not shipped.
Review follow-up: the six implementation gaps are fixed in [Task 5: review fixes](navigation/05-review-fixes.md)
(Resume, handoff recovery/revisions, chat handoff, replan approval and latest results). Real-provider handoff
delivery and the native window remain open live checks.
Companion to [supervisor brainstorm 44](BRAINSTORM.md). This records Fred's navigation
request after the supervisor decisions. It changes the presentation proposed in section 10,
not the supervisor's authority, budgets, wake rules or guidance ordering.

## Settled decisions (Fred, 2026-10-17)

1. The handoff summary is built by one cheap haiku pass over the saved digest (like the
   rolling brief), never by re-reading the live context and never a pure code concatenation.
2. Handing a task off sets the source task `handed` and records its `handoff_to` link; it is
   not marked done.
3. Handoff is the cold-cache escape for tasks: it reads saved step files and the haiku digest,
   so a cold task is never re-read. A cold external session (VS Code / terminal / other-CLI,
   not a task) has no saved folder; its escape is the composer -> Prep, and "Brief a new task"
   is removed with no replacement. The composer is the single way to create a task.
4. "Mark done" (green) is the whole-task completion action and replaces "Finish task";
   "Accept step result" replaces "Mark step done" and is recovery only; Verify is a choice
   inside Add step, not a standalone button.
5. Navigation and action cleanup ship before the plan 44 supervisor UI. The supervisor's
   suggestions, approvals and questions share the one Overview attention area when its
   backend lands.
6. Hand off task offers both Save document (write `task-handoff.md` in the source folder only,
   no state change) and Create follow-up task (also create the linked draft and set the source
   `handed`).

## Purpose

Open a task, understand where it stands, answer what it needs, and decide what happens next.
Task identity stays visible throughout. Steps are the history and execution of that task.

The present interface combines task controls, step controls and older session controls in
several rows. `openTask` selects the current step; `taskButtons`, `stepButtons` and
`taskSessionButtons` repeat actions. A task heading consequently does not reliably open
the task's details. The existing uncommitted header-click and confirmation fixes help only
some entry points; preserve their behavior while replacing the shared navigation rule.

## Navigation contract

- Clicking a task title, task header, task link or completed-task row opens that exact
  task's Overview. A one-step chat is still a task and follows the same rule.
- Clicking a step opens that exact step's Conversation. Explicit links to an attempt open
  that attempt. Nothing silently substitutes the latest step.
- The inspector keeps a breadcrumb: Tasks / task title / step, when viewing a step.
  The task title returns to Overview; Tasks returns to the list, retaining its filters,
  expansion and scroll position. Navigation never starts a run.
- Overview, Steps and Files are the task-level destinations. Steps presents the existing
  ordered chain; Files contains the goal, plan and handoff documents. Keep the established
  split view at wide widths and one-pane navigation at narrow widths.
- Step Conversation is primary. Received context, Handoff, Files and execution details
  remain accessible as secondary views, without adding task actions to each tab.
- Polling updates content without changing the selected task, step, attempt or tab.
  Discard late fetch responses for a different selection. Preserve drafts, focus, caret,
  attachments and scroll position through refreshes and navigation.
- Opening a task after creating it lands on Overview with its running state visible.
  An explicit notification about a step may deep-link to that step with the task breadcrumb.

This supersedes plan 42 interaction rule 1 (task selection opens current-step Chat).
It keeps plan 42's shared composer, delivery gates and persisted guidance queue.

## Task Overview

Reading order:

1. Task title and plain-language status. One quiet metadata line: project and cost.
2. Original goal, visible by default. Long goals may expand; the first lines remain visible.
3. What needs attention: a worker question, a confirmation, a failure with its recovery,
   or a supervisor suggestion. Do not repeat the same question in a heading and the composer.
4. Current progress: current step and its outcome, with a link to its conversation and the
   step history. Include the latest useful reply, labelled with its source step.
5. One shared task composer and one consistent task action area.

The Overview must answer real worker questions, including plan gaps, directly. Do not send
Fred to another screen simply to answer. Required confirmations name their consequence:
Confirm plan, Approve extra usage, or the actual recovery action. Do not use one generic
Confirm button for unrelated decisions.

The composer says where delivery goes and when: Answer step 3, Message current step 3,
or Queued for the end of this turn. Reading an older step never changes the destination
silently. Preserve the existing explicit retarget step when the current attempt changes.
Send does not imply Add step, Retry, Resume, or New task.

## Action hierarchy

Keep at most two prominent workflow actions, plus More. Send and Attach belong to the
composer; they are not duplicated in the task toolbar. Actions align from the left in
stable groups. At narrow widths use a deliberate stacked layout, not a right-aligned
flex row that unpredictably wraps. Keep the input and its Send action reachable when
questions, filenames or errors are long; secondary content scrolls.

| Current control | Proposed placement and behavior |
|---|---|
| Brief a new task | Remove. New task has one entry point and one prompt flow. |
| Verify in a new task | Remove this duplicate shortcut. Verification is a kind in Add step. |
| Add next step | Label Add step. Opens the existing kind/instructions/model preview for this task. |
| Verify | A choice within Add step; a supervisor suggestion may offer Approve verification directly. |
| Continue | Use the shared message composer; no duplicate navigation button. |
| Mark done / Finish task | One green Mark done action for the whole task, where the service allows it. |
| Mark step done | Recovery only, labelled Accept step result; explain that it accepts incomplete/failed output. Never imply the whole task is complete. |
| Hand off / Start next task | One More > Hand off task flow, described below. |
| Terminal | More > Open in terminal, only where supported. |
| Pause / Resume | Show the applicable control for current state; the supervisor respects a manual pause. |
| Stop | Clearly available while work runs, without opening More. |
| Retry | In the failure panel beside its reason, with the existing note/model choices. |
| Delete | More, separate from routine workflow; retain the existing deletion confirmation. |
| Open folder / Review rules / model escalation | More or execution details, where applicable. |

State-specific presentation:

- Running: status, composer, Stop, More. No disabled wall of unavailable workflow buttons.
- Needs answer: question and Send answer. An outstanding supervisor suggestion cannot
  compete with or bypass that question or pending guidance.
- Needs approval: proposal with Approve / Reject and the effect of approval.
- Ready for next action, supervisor off: Add step, green Mark done, More.
- Supervisor preparing a suggestion: show that status honestly; manual action still uses
  the existing gates and invalidates stale suggestions.
- Failed/stopped: reason and Retry; Accept step result stays a secondary recovery option.
- Paused: Resume; retained guidance stays visible.
- Done: completion summary and More; Add step remains available through More if permitted.

Mark done uses a compact inline confirmation: Mark this task done? History stays available.
Use Confirm done (green) and Cancel without changing button widths. Keep pending-message
checks on the server; do not strand queued or uncertain guidance. Completion must not claim
verification passed when it did not. Retain the actual verification status separately.

## Supervisor integration

Use one attention area on Overview and the shared task conversation surface. A suggestion
names the proposed action, the reason, and Approve / Reject. Instructions expand on demand.
Supervisor questions go to Fred; the supervisor cannot answer them on his behalf.

Show a compact setting named Supervisor: Off / Suggest / Auto. Explain each value when
changing it. Wake counts, individual pass costs, raw decision names and logs belong in
Details, not the task heading. Budget holds, uncertain dispatches and errors remain visible
when they affect the next action. Skills belong to step details and the step editor.

Do not render a working supervisor control until the corresponding plan 44 backend slice
exists. Navigation and action cleanup can ship first. When it does exist, stale approvals,
pending guidance, per-task locks and all caps still use the existing server authority.

## Hand off task

Meaning: transfer the remaining work of this specific task into a new linked task with a
written account of where work stopped. It is neither a blank prompt nor a continuation
of only the newest session.

1. More > Hand off task opens a preview naming the source task, its project, current state
   and all included steps. Fred can state the intended remaining work in a short field.
2. Build a task-wide handoff from saved task data, step notes/briefs, facts, the plan,
   verdicts and unresolved questions, summarized by one cheap haiku pass over that saved
   digest (decision 1). Do not require a live session or the session-handoff skill just to
   transfer a stopped task; the live context is never re-read. Failed and unfinished steps
   are included honestly.
3. Present the summary for review. Offer Save handoff document and Create follow-up task.
   Save writes `task-handoff.md` in the source folder only (no new task, no state change);
   Create follow-up task also creates a linked draft and sets the source `handed`. Neither
   launches paid work. The ordinary Start action launches the new task after review.
4. Opening the created task shows its inherited goal, source-task link, handoff and the
   remaining-work instructions. Starting it supplies the summary inline plus a document
   manifest; do not rely exclusively on access to paths outside the project sandbox.
5. Preserve the source task and its history. Record the destination `handoff_to` link and
   set the source state `handed` after creation succeeds. A handoff does not mean the
   original goal was successfully completed; do not mark it Done automatically.

The document uses the existing six handoff headings:

| Heading | Required content |
|---|---|
| Goal | Original task goal, source task identity, project and intended remaining work. |
| Findings | What each relevant step achieved, what is incomplete, and where execution stopped. |
| Files touched | Source file references plus links/paths to the saved plan, step notes, facts and verdicts. |
| Troubleshooting | Failures, attempted fixes, constraints and exact available test results. |
| Open questions | Unresolved decisions and any guidance whose delivery has not been established. |
| Next | Concrete next work, acceptance criteria, and the documents to read first. |

Citations must name real saved documents and their step numbers; label missing documents
as unavailable. Preserve facts and failures without inventing a successful outcome. Use
the existing redaction and task file helpers. Save under the Console task directory, not
an arbitrary model-provided path. Copy the handoff into the destination task so deleting
the source later does not remove the starting context; references to deleted originals
must report unavailable. Do not recursively copy transcripts or an entire project.

Creating a follow-up is task-scoped and idempotent. Recheck the source revision under the
task lock before committing; changed work requires a refreshed preview. Active workers
must finish or be explicitly stopped before transfer. Pending/uncertain guidance needs an
explicit resolution; never drop, duplicate or silently claim it was delivered. A failed
document save or task creation must leave the source usable and expose a retryable error.

## Remove information clutter

- Remove the non-actionable Delegate? read-count hint from the main interface. Raw reads,
  routing, model effort, context accounting and event counts remain in execution details.
- Use Goal, Activity and Files in visible navigation instead of prompt.md, Chain log and
  internal file/protocol names. Actual filenames remain in the file browser and citations.
- Hide empty sections. Show unavailable-action reasons near the relevant recovery, not a
  row of technical headings or tooltips on buttons that cannot be clicked.
- Keep real failures, conflicting writers, spend approvals and delivery warnings when they
  affect the user's decision. Simplification must not hide a reason work cannot proceed.

## Implementation scope and order

The guided plan is [navigation/README.md](navigation/README.md) (Tasks 1-4 implemented 2026-10-17): selection
(T1), Overview and the action area (T2), the whole-task handoff (T3), tests and close (T4). This section is the
source for those tasks; the plan is authoritative over any interrupted attempt in the working tree.

1. Fix selection centrally: `openTask`, task/header/day-row click handlers, task-owned
   session links, `goChat`, inspector selection and async fetch guards in `web/app.js`.
   Audit every caller; use explicit step navigation only for intentional deep links. Done (T1).
2. Rebuild Overview and the action hierarchy using the existing plain HTML/CSS/JS and
   Cells palette. Consolidate `taskButtons`, `stepButtons`, `taskSessionButtons`,
   `nextActions`, `nextSecondary`, `stepFooter` and their handlers. Keep server gates.
   Update `web/style.css`, and `web/index.html` only if the existing mounts require it. Done (T2).
3. Add the whole-task handoff preview, saved document and linked draft creation through
   `console/server.py` and `console/tasks.py`: one cheap haiku pass over the saved digest
   (reuse `compact.run_brief` / `brief_command`), the `handed` state and `handoff_to` /
   `handoff_from` link fields. Reuse the current task creation/run path, persistence, safe
   IDs, file readers, redaction and request-id conventions. Define the minimal API and
   persisted link fields in the guided implementation plan before coding. Keep standalone
   external-session handoff behavior separate and working. Done (T3).
4. Integrate plan 44 suggestions when its backend ships. Replace section 10's busy header
   proposal with the attention area and compact setting above; do not change autonomy rules. Pending its backend.
5. Update `tests/test_web.py`, task/server tests and
   `tests/live_task_chat_check.py`; reconcile plans 39, 41, 42 and 44 and the master index. Done (T4).

No new frontend framework, dependency, router abstraction, persistent supervisor session,
or unrelated visual theme change is required. The interrupted navigation/handoff
implementation (edits in `web/app.js`, `web/style.css`, `console/server.py`,
`console/tasks.py`, `tests/test_web.py`) is superseded and will be rewritten against this
plan, not salvaged. The independent backtick-fence fix in `console/tasks.py` and its test
in `tests/test_tasks.py` are separate and must be retained.

## Acceptance checks

- All task entry points open the selected task's Overview, including a one-step chat,
  older completed task and a task other than the newest one. No automatic step redirect.
- Step and attempt links open the specified history; returning to Overview keeps the task.
  Polling and out-of-order responses cannot change that choice.
- A worker question, plan gap and plan confirmation can each be handled from Overview.
  Drafts, attachments, retarget warnings and delivery errors survive navigation and polling.
- No Brief a new task, duplicate Continue, duplicate Verify, or duplicate completion
  controls appear. Mark done is green; Accept step result has distinct scope and wording.
- Running, waiting, failed, paused, handed-off, completed, empty and offline states have
  a clear next action and truthful delivery status. Every displayed control has a working
  handler and tested success, refusal and error behavior.
- Handoff includes completed, failed and unfinished steps and real document references.
  Save-only starts nothing. Create-follow-up yields one linked draft on repeated requests.
  The new task can read its copied context even if external-file access is unavailable.
- Stale previews, concurrent completion, pending guidance, missing files, failed writes,
  restart during creation and deletion of an original source have explicit outcomes.
- At 900, 400 and 340 px, both themes and keyboard-only use: no horizontal overflow,
  arbitrary button wrapping, trapped focus, or inaccessible input/confirmation controls.
- Run focused web/task/server tests and the browser fixture before broader regression.
  Real-provider delivery and the native window remain separate live checks.
