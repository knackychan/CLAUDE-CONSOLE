# Task 5: fix the navigation slice review findings

Date: 2026-10-17. Status: implemented 2026-10-17.

> Contract: [NAVIGATION.md](../NAVIGATION.md), especially Task Overview, Action hierarchy,
> Hand off task, and Acceptance checks. Follows the shipped Tasks 1-4 in [README.md](README.md).
> This task fixes the six findings from the implementation review. It does not implement the supervisor.

## Baseline and scope

The review checked the shipped navigation slice at `ee9f098`. All 480 focused tests passed
(233 server, 134 tasks, 81 web, 19 task messages, 13 handoff), as did `node --check web/app.js`.
The existing task-chat browser fixture passed. An additional scratch browser check exercised
handoff Preview -> Save -> Create, opening the planned follow-up, and overflow at 900/400/340 px
in both themes. These passes did not cover the six failures below, which were reproduced separately.

The full repository suite, real-provider delivery and native window were not checked in that review.
Start from the current implementation. Do not apply the historical reset instructions for Tasks 1-4.
Keep the independent backtick-fence fix and all existing guidance delivery gates.

Files to change:

- `web/app.js`: `taskButtons`, `attentionArea`, `overviewBody`; reuse `replanBox`.
- `console/server.py`: `handoff_available`, `_handoff_material`, `task_handoff`, `_follow_up`.
- `console/handoff.py`: only where chat saved-result handling or fingerprint input sharing needs it.
- `tests/test_web.py`, `tests/test_server.py`, `tests/test_handoff.py`,
  `tests/live_task_chat_check.py`: regressions and browser coverage.
- This plan and the plan indexes: record verification and completion after implementation.

Before editing, search every caller of the affected helpers and inspect the existing pause/resume,
chat filing, plan editing, handoff and rendering tests. Keep API routes and server authority unchanged.

## 1. Restore Resume for paused tasks

**Failure:** `taskButtons` requires `t.state === "paused"`. Pause actually keeps `running` or
`waiting` and changes `owner` to `fred`. The server permits Resume but no button appears.
The review reproduced this through `/api/task/pause` with a fake runner after the current step ended.

**Change:** Render Resume from `d.levers.resume === ""`, retaining Start task for an unstarted
follow-up. Do not infer a new persisted state. Keep Stop prominent while a worker still runs;
after it finishes, the permitted Resume must be reachable. Preserve the manual progression boundary:
`resume === "choose a next step or finish the task"` must not show Resume.

**Regression checks:**

- Render actual GET `/api/task` data after Pause and the current step finishing: Resume exists once.
- Clicking it posts `/api/task/resume`; the next step starts through the existing service gate.
- A manual task waiting for Add step has no Resume; an unstarted follow-up still says Start task.

## 2. Revalidate an incomplete handoff before linking the source

**Failure:** Create can persist the destination and then fail while saving the source link.
On retry, the `known` destination branch calls `_link_handoff` before availability or revision checks.
The review injected that write failure, queued guidance, and retried: the API returned 200 and
changed the source to `handed` with its message still queued.

**Change:** Separate an already completed request from an incomplete source link, under `tlock`.

- If the source already links to the matching destination, return the existing success unchanged.
  This is the idempotent replay path; do not rewrite history or require a cached preview.
- If the destination exists but the source link is absent, recheck `handoff_available` before any write.
  Refuse queued/uncertain guidance, live workers, briefing, and a link to a different follow-up.
- Persist a hash of the source material used for creation in the destination's `handoff_request`,
  alongside its existing `source` and `request_id`, before its `task.json` becomes visible.
  Compare that hash with current source material before completing an incomplete link. Reuse the
  material definition from section 3; do not hash the preview cache or depend on it surviving restart.
- Adjust request matching to compare `source` and `request_id` explicitly, rather than whole-dict
  equality now that recovery metadata is present. Include the submitted remaining-work note in the
  material comparison so an incomplete request cannot be retried with different instructions.
- Read and validate the saved inherited summary before recovery. An unavailable summary, missing
  recovery hash on an older partial draft, or changed source must return a clear 409 without writes.
  Preserve both tasks and name the existing draft in the error. Do not silently replace, delete,
  or launch it. The user can inspect/delete that draft and make a fresh handoff explicitly.
- Recovery with unchanged source and intact evidence finishes the link once, including after restart.

**Regression checks:** Inject failure specifically after destination save but before source linking.
Retry unchanged, then repeat in separate cases with pending guidance, a live worker, changed source,
missing inherited summary and another destination link. Successful recovery produces one draft and
one source-link history entry; refusals leave source state/messages intact. Reload saved tasks into
a new Hub and repeat the successful and refused recovery cases with an empty preview cache.

## 3. Make preview revisions cover all saved inputs

**Failure:** `_handoff_material` omits the saved plan, plan parts, final replies and other inputs
read by the summarizer. The review edited a plan successfully through `Hub.edit_plan`, then saved
the preceding preview successfully. Its summary could therefore contradict the transferred evidence.

**Change:** Fingerprint all task fields and saved inputs that affect the digest, fallback or evidence
copies. Include goal/title/project, step goals/state/session/attempt details, questions, plan metadata
and contents/parts, prompt, notes, briefs, facts, saved final replies, verdicts and the relevant chain tail.
Represent absent documents explicitly so a file appearing or disappearing also changes the revision.
Use existing safe file readers and deterministic ordering. Share the input enumeration where practical
instead of maintaining independent lists that can drift.

Continue excluding the output `task-handoff.md` so Save then Create works from one preview.
Keep the existing intentional exclusion of cost-only updates. A changed input requires a fresh preview;
neither Save nor Create may quietly regenerate the reviewed text. Keep the Haiku pass outside `tlock`.
Compare current material again under the lock at commit time, including changes during the pass.

**Regression checks:**

- Preview, successfully edit the plan through the existing API, then Save/Create: both return 409.
- Change a plan part, saved final reply, verdict, or an input file's presence: the preview is stale.
- Change evidence while the fake summary call is blocked: committing its result is refused.
- Unchanged Save then Create and a cost-only update still work; ordinary completed-request replay works.

## 4. Restore handoff for one-step chat tasks

**Failure:** `handoff_available` rejects `task.chat`, telling the user to hand off through the session.
The consolidated toolbar no longer renders that session action, and opening the session routes back
to the task inspector. There is no reachable handoff action for the chat task.

**Change:** Allow chat tasks through the same whole-task saved-file handoff path. Remove the blanket
chat rejection, preserving live-worker, guidance, briefing and existing-follow-up gates. Read the
chat's saved `notes.md` when no structured handoff exists; do not fetch a live transcript or resume a
cold session. Check `_chat_tick` filing and the existing digest/fallback before adding any new code.
Ensure the saved chat reply is represented in both summary paths and the source revision.

The follow-up remains the existing one-code-step manual draft. Its inherited goal, summary and copied
evidence follow the same contract as other tasks. A source already done stays done; an unfinished
source becomes handed. Standalone external-session handoff remains unchanged.

**Regression checks:** Build a real chat-task fixture with a completed turn, saved plain reply and no
HANDOFF block. Hand off through More, preview, save and create. Assert saved reply context is retained,
one follow-up exists, and no worker starts. Cover both model-summary and fallback paths. Repeat with a
live chat run and pending guidance: refusal remains enforced. Replace the test that expects every chat
task to be rejected with these cases.

## 5. Put replan approval on Overview

**Failure:** The `replanned:` branch in `attentionArea` renders only Open step. Confirm plan and
Keep old plan remain on the step view, contrary to the task-level approval contract.

**Change:** Render the existing `replanBox(t, currentStep, d, row)` in Overview's attention area when a
replan awaits review. It already shows the proposed changes and reads the service's confirm/keep gates.
Do not duplicate its buttons elsewhere on Overview. Keep the step view available and preserve plan-gap
answers through the shared composer. This supersedes Task 2 section 2.3's replan-only Open step placement.

**Regression checks:** A realistic waiting replan shows its proposal and exactly one Confirm plan and
Keep old plan on Overview. Each button calls its existing endpoint; success updates the same task,
and a refused request displays its error. A plan-gap answer remains usable from Overview without
navigating to a step. Ordinary plan confirmation still renders once.

## 6. Show the latest available result, even with later planned steps

**Failure:** `overviewBody` selects the highest-numbered step and then hides its result when that step
is planned/running. With step 1 done and step 2 planned, no latest result appears despite saved output.

**Change:** Select the highest-numbered step that has a nonblank saved result and is neither planned
nor running. Use the existing saved notes response and label the fold with that source step's number
and kind. Failed output remains labelled honestly. Do not change the current-progress link or switch
the selected step as a side effect.

**Regression checks:** Completed step followed by planned/running steps still shows the completed
result; a newer failed step with saved output is identified as failed; missing/blank notes fall back to
the latest available result; no saved result produces no empty fold. Polling preserves selection.

## Execution and close

- [x] Add the failing regressions for sections 1-6 before changing their implementation.
- [x] Implement sections 2 and 3 together, including the durable partial-create recovery tests.
- [x] Implement sections 1, 4, 5 and 6 using the existing gates, components and endpoints.
- [x] Run the focused suites:

  ```powershell
  py -m unittest tests.test_handoff tests.test_tasks tests.test_server tests.test_task_messages tests.test_web
  node --check web/app.js
  ```

  Result: 495 focused tests OK; `node --check web/app.js` clean.
- [x] Extend `tests/live_task_chat_check.py` with Resume, chat-task handoff, replan approval and latest
  result scenarios. Run `py -m tests.live_task_chat_check` with scratch data and fake runners.
  Check Overview/Steps/Files, handoff Preview/Save/Create, keyboard access, error visibility and overflow
  at 900/400/340 px in both themes. Preserve draft, attachment and selection checks.

  Result: `py -m tests.live_task_chat_check` passed (fake runners, scratch data, Edge headless).
- [x] Run `py -m unittest discover -s tests` after focused checks pass.

  Result: 910 tests OK; `node --check web/app.js` clean.
- [x] Record actual results here and update README, NAVIGATION and PLAN status. Keep real-provider and
  native-window checks explicitly open until performed; the supervisor backend remains unshipped.

## Results

- Resume now renders from `d.levers.resume === ""` in `taskButtons`, so a paused task whose step has ended
  shows Resume; the manual boundary `choose a next step or finish the task` and the unstarted follow-up's
  Start task label are preserved.
- `task_handoff` separates a completed request (idempotent replay) from an incomplete source link. The
  incomplete path revalidates `handoff_available`, reads and validates the saved inherited summary, and
  compares a persisted `handoff_request.material` hash before `_link_handoff`; older partial drafts without
  the hash are refused. `_follow_up` stores the material hash alongside `source` and `request_id`.
- `_handoff_material` now fingerprints the goal/title/project, step goals/state/session/attempt details,
  questions, plan metadata and contents/parts, prompt, notes, briefs, facts, saved final replies, verdicts
  and the chain tail; absent documents are explicit and cost-only updates are still excluded.
- Chat tasks are no longer blanket-rejected by `handoff_available`; they hand off through the saved
  `notes.md` reply, with the same live-worker, guidance, briefing and existing-follow-up gates.
- Overview's `attentionArea` renders `replanBox` for a waiting replan; plan-gap answering stays on Overview.
- Overview's latest-result fold selects the highest-numbered step with a nonblank saved note that is neither
  planned nor running, and labels a failed result.

Open: real-provider handoff delivery and the native window remain unperformed live checks; the plan 44
supervisor backend stays unshipped.

No new dependency, framework, supervisor control, routing policy or live-provider call is needed.
This is a plan only; writing it does not mark any of the fixes implemented.
