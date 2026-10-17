# Plan 42: One task chat and input at every stage

Date: 2026-10-17. Status: queued delivery implemented and verified with fake runners. Live provider checks remain open.
Master: [../PLAN.md](../PLAN.md). Extends plans 25, 36, 39 and 41.

## Goal

Selecting a task opens its current conversation on the right, with the same controls and input everywhere. Remove Open chat once that panel provides all applicable session actions. Let Fred type and submit corrections or extra information throughout a task, with an honest indication of when the agent will receive them.

## Starting point

- `web/app.js:stepButtons` renders Open chat with `data-open`, navigating to the separate session page. The conversation overlaps, but its controls differ.
- `stepFooter` replaces the input with Working during a live turn, omits it when there is no session or the selected step is historical, and otherwise limits it to chat steps. Opening Add next step also replaces the footer.
- The session page's follow-up input depends on `levers.continue`. `Hub.levers` refuses Continue while working and reserves active automatic-chain turns for task actions. This is a server contract, not merely a hidden textarea.
- The harness interface supports starting, resuming and stopping runs; it does not currently define a common live-steering operation. Do not assume writing text to stdin delivers it safely.
- Plan 41 changes are already in the working tree. Build on its Stop, Retry and Mark step done behavior; preserve those changes.

## Interaction contract

1. Selecting a task opens the current step's Chat tab. Selecting an older step opens its history. Keep Received, Handoff, Route and Plan available.
2. Keep a composer anchored below the inspector content, available across its tabs. Use one renderer and submission handler for task conversations; retain the standalone session page for sessions without a task and route task-owned session links to their task/step.
3. Show the destination above the input, for example `Message current step 03: Implement`. When reading history, retain an obvious historical label and target the current step explicitly. Never resume an old step by accident.
4. Use Send for normal messages and Send answer for an explicit question. Keep Stop, Retry, Mark step done, Add next step and Finish task as distinct actions with their existing server gates. Move all applicable session-only controls into this panel before removing Open chat.
5. Keep the input visible when sending is unavailable. Explain why beside it, retain the draft, and show the relevant recovery action. Do not silently discard text or clear it on failed submission.
6. Keep a draft per task, with the destination step/attempt captured separately. Preserve drafts, selection and attachments across polling, tab changes, task switches and temporary errors. Use existing draft storage where possible; do not put attachment bytes into window preferences.
7. Add next step remains a separate, explicitly labelled operation. Its form must not silently replace or consume the message draft.

| Task condition | Input and delivery |
|---|---|
| Planned, no run yet | Accept task guidance and include it before the first step starts; sending alone does not start the task. |
| Running | Accept guidance now. Deliver during the turn only through a verified adapter capability; otherwise show `Queued for the end of this turn`. |
| Waiting for an answer | Send through the existing task answer path, including Plan-gap decision handling where applicable. |
| Idle current chat | Continue the current conversation using the existing guarded path. |
| Paused, stopped, failed or usage-limited | Accept and retain guidance, but do not restart implicitly. Deliver with the explicit Resume/Retry action; show the applicable reason and recovery control. |
| Finished task | Keep the draft editable; offer Add next step with the text explicitly transferred after the user selects that action. Do not silently reopen a completed step. |
| Runs disabled, missing folder/CLI, or disconnected | Show the reason, preserve the draft and disable delivery. |
| External terminal/editor session | Preserve the existing fork-only policy. Never inject into an externally owned process. |

## Delivery rules

- Add a task-scoped message operation in `console/server.py`, governed by server-computed availability and mode. Reuse existing continuation, answer, attachment validation and cold-cache checks when they apply. Do not make every session's Continue legal while busy.
- Persist accepted guidance under the existing task data directory before acknowledging it. Record message/request id, task, destination step and attempt, text/files, delivery mode and status. Repeated requests must not create repeated turns.
- Distinguish queued, dispatched and failed messages in the conversation. Do not claim the model has read a message merely because a process write succeeded. Allow queued guidance to be cancelled before dispatch.
- Under the same synchronization used for step completion/advance, check pending guidance before handoff validation, briefing and starting the next step. Guidance accepted for the current step gets a follow-up turn on that step before progression. Rebuild its handoff from the resulting work before advancing.
- If completion or Retry wins the race before acceptance, return the changed destination and retain the draft for confirmation. Never silently redirect an already accepted message to a different attempt.
- Pending guidance survives window closure and service restart. A message whose dispatch outcome is uncertain after a crash stays visible for recovery; do not automatically replay potentially applied instructions.
- Pending guidance must remain visible through Stop, Retry, Mark step done and Finish task. Require an explicit disposition before an action would strand it or advance past it. Do not overwrite the task plan with arbitrary chat text.
- First ship queued steering with truthful timing. Add live delivery only for adapters proven to support it by their actual protocol and a focused integration check. Unsupported adapters retain the queue behavior. No automatic Stop, process kill or model switch to simulate steering.

## Implementation slices

### 1. Unify navigation and controls

Inventory callers of `data-open`, `goChat`, `stepButtons`, `stepFooter`, `taskChatAct`, `act`, session follow-up rendering and Board/task selection. Map every existing action to the shared panel, including answers, attachments, cold-cache confirmation, terminal access and history links. Introduce the shared composer without changing execution rules yet. Remove Open chat only after action parity is covered.

Files: `web/app.js`, `web/style.css`, `tests/test_web.py`; `web/index.html` only if the existing pane needs a stable composer mount. Preserve focus, caret, scroll position and task identity during asynchronous redraws. Keep the input outside the scrolling transcript and usable at narrow widths, with keyboard labels and visible focus.

### 2. Accept and deliver task guidance

Files: `console/server.py` (task API, eligibility, answer routing, completion/advance), `console/tasks.py` (existing task persistence), `console/runs.py` (run lifecycle only where needed), and attachment handling through the existing module. Add minimal persisted pending-message data with backward-compatible defaults for old task folders. Update the composer to display the server's delivery mode and message status.

Implement queued delivery and progression ordering together. Do not ship an accepted queue that the scheduler can bypass. Reuse existing locks and task events rather than introduce a daemon, database or generic job system.

### 3. Verify optional live delivery

Inspect `console/harness/__init__.py` and each adapter's process lifecycle. Verify supported steering protocols against official runner documentation at implementation time. Introduce an adapter capability only where proven; test delivery while a tool is running and while a turn finishes. Queued delivery remains the baseline for all other runners.

### 4. Regression and live checks

- Extend `tests/test_web.py`: every state in the table, identical controls through all task entry points, historical targeting, composer visible across tabs, no Open chat duplication, drafts and attachments retained after errors and redraws.
- Extend `tests/test_server.py` and `tests/test_tasks.py`: busy guidance accepted without a concurrent run, answer/Plan-gap routing, queue-before-advance ordering, multiple messages in order, duplicate request id, stale step/attempt, stop/retry/finish with pending guidance, restart recovery and denied projects.
- Extend `tests/test_runs.py` and adapter tests only if their protocol changes. Cover failures and unknown dispatch outcomes, not only successful writes.
- Run focused tests, `node --check web/app.js`, then `py -m unittest discover -s tests` after integration.
- Live check: type while a task streams, submit a correction, observe its delivery status and incorporation before the next step, switch tasks and return, answer a question, retry after a limit, inspect an old step, and use the narrow window. Confirm no hidden composer, lost draft, duplicate turn or accidental history mutation.

## Completion criteria and scope

One task selection opens the usable conversation without a second Open chat action. The composer stays visible and preserves input throughout task transitions. Guidance can be submitted while work runs, with explicit delivery timing, and cannot be skipped by automatic progression. Existing recovery, attachments, answer semantics and external-session ownership remain intact.

No visual redesign, new dependency, automatic interruption, editing completed history or cross-task message routing. No runner is advertised as supporting true mid-turn steering.

## Implementation record, 2026-10-17

- Task and task-owned session links open the shared inspector conversation. Historical steps and earlier attempts stay read-only; the composer names the current destination separately. The composer remains below the scrolling pane across tabs and alongside the separate Add next step form. The redundant Open chat action is removed after moving session controls into the panel.
- `POST /api/task/message` accepts a request id and exact step/session/attempt target, validates attachments, and saves the message before acknowledging it. Old task folders need no migration. Text, destination, mode and status live in task.json; parsed attachment bytes live in `messages/<request-id>.json` under the same task folder and never enter snapshots or window preferences.
- The task lock covers acceptance, dispatch and progression. Each queued message runs in order on the same step before handoff validation, briefing or advancement. Planned guidance joins the first prompt. A replan pass processes guidance with its previous result before presenting a proposal. Ordinary chat steps also have an explicit Retry path after Stop or failure.
- Stop retains guidance. Retry requires a second click explicitly carrying it to the new attempt, recorded separately from the original target. Finish, Mark step done, Delete, Add next step and plan-changing actions require the guidance to be resolved first. Queued messages can be cancelled. A crash during dispatch leaves an uncertain outcome requiring inspection and dismissal; it is never automatically replayed. Pending guidance is exempt from history hiding and retention pruning.
- Answers keep question semantics and add a Plan-gap decision only when answering a Plan gap, including attachment support and cold-cache confirmation. Other chat text does not edit the plan. External conversations are forked into a window copy. Unsupported attachment formats or runners retain a clear reason and the draft.
- Each task keeps its text draft and destination in local storage; attachment bytes stay in window memory until acceptance. Focus, selection, textarea scroll and attachments survive polling, tabs, task switches and temporary errors. Text-only request ids also survive a window reload after an unacknowledged submission.
- Adapter review: all four adapters remain on queued delivery. The existing run watcher closes input after a result; no live-steering capability or process write was added. Official documentation checked: [Claude streaming input](https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode) describes sequential queued messages in a persistent SDK session, [Codex non-interactive sessions](https://learn.chatgpt.com/docs/non-interactive-mode#resume-a-non-interactive-session) documents a separate exec resume, and [OpenCode CLI](https://opencode.ai/docs/cli/#run) documents run/continue/session. These do not establish tested mid-turn delivery for the adapters in this project. No live capability was enabled without the required provider integration check.
- Automated coverage lives in `tests/test_task_messages.py`, `tests/test_tasks.py` and `tests/test_web.py`. `py -m tests.live_task_chat_check` uses installed Playwright and Edge against a scratch service and fake runner: submit while streaming, observe queued then dispatched before progression, preserve drafts/files/selection across task switches and tabs, inspect history while targeting the current step, answer a question, explicitly Retry after a cap, and check 900/400/340 px in dark/light and reduced motion. At 760 px height, the textarea and Send button remain inside the viewport. This browser check passed.
- Verification: `py -m unittest discover -s tests` passed 837 tests. Final boundary fixes were followed by `py -m unittest tests.test_web tests.test_tasks tests.test_task_messages`, 210 tests passing (including 19 guidance tests). `node --check web/app.js` and `git diff --check` passed. The first full run's unrelated Codex retry fixture was corrected by the concurrent Plan 43 work before the passing full run; its writing step succeeded, but the test had incorrectly waited for the fake verifier too.

Still open: a real-provider Windows window check for a correction during a tool call, a question, and recovery after a provider usage limit. True mid-turn delivery is optional and remains disabled until its protocol and integration checks pass.
