# Plan 36: Add the next session as a step of this task

Status: **Stage A shipped** 2026-10-15 (Tasks 1-4, fake harnesses only; live provider checks open).
Stage B (Tasks 5-6) not started. Section 6 is the log.

Design contract: [next-step design guideline](../../design/brainstorm/2026-10-15-next-step.md).
Master index: [PLAN.md](../../PLAN.md). Existing contracts: [task chains](../17-tasks/README.md),
[handoffs](../23-handoff/README.md), [Board](../25-cells-board/README.md),
[models](../26-models-page/README.md), and [harnesses](../05-harnesses/README.md).

## 1. Outcome and authority

After a chat replies, Fred can continue that conversation or add a fresh Code, Verify,
Investigate, Plan, or Chat session to the **same task**, in the **same project folder**.
The last step supplies the handover. The new session may use another enabled provider/model.
The same operation will be callable by an agent after Fred explicitly requests it.

Example: `01 Chat / Haiku -> 02 Code / Sol -> 03 Verify / Astra`, one task ID and history.
This is not the existing Start next chat action, which seeds a separate task.

The user approved this direction and asked for a guided implementation plan and design guideline.
The technical choices below are this plan's implementation defaults, not claims that they have
already shipped or that each detail was separately selected by Fred. Follow them together;
record any necessary contract change here and in the design guideline before implementing it.
Do not quietly substitute a simpler behavior that loses task continuity or model choice.

Keep the repository's numbered plan convention. Do not create a second planning tree.
Implement Stage A (visible controls) completely before Stage B (agent requests).
No implementation, live model calls, dependency installs, or settings changes are authorized
by this documentation-only task.

## 2. Findings that the implementation must address

| Existing location | Current behavior | Required change |
|---|---|---|
| `web/app.js`: `chatTab` | Board chat footer renders only Continue | Add the next-step flow and restore relevant session actions |
| `renderLevers`, `act`, `stepAct` | Older session view has other actions; handlers have different session lookup paths | Share availability/operation, always address the selected source explicitly |
| `server.Hub.chat_task`, `_chat_tick` | Chat tasks assume `steps[0]`; `chat=True`, owner `window` | Allow a chat-origin task to progress without overwriting its first chat |
| `snapshot`, `task_row`, `task_levers`, `levers` | Chat/task mapping and permissions depend on the old shape | Map every historical session and gate current actions server-side |
| `tasks.CHAT`, `chat_step`, `checked_route`, `on_step_ended` | Chat is not a normal planned kind; Verify can insert a fix automatically | Explicit manual progression with no unexpected fix or follow-on run |
| `Hub.start_step`, `_advance_one`, `_ended`, `_go_on` | Service owns automatic chain advancement | Reuse launch/finalization, stop at the manual step boundary |
| `brief.build`, `Hub.brief_text`, `compact`, `facts`, `tasks.HEADINGS` | Existing brief/handoff machinery; generic new-task briefs are clipped | Build a traceable step handover, preserve decisions and report omissions |
| `tasks.step_route`, `fills.pool`, `Hub._route_for` | Ranked routing and balancing; some refused picks fall back | An explicit next-step model must run exactly or fail visibly |
| `paths.DEFAULTS` model tiers | Astra is configured as `codex:gpt-6-astra` | Resolve through the live registry; never through Claude's Agent menu |
| `runs.start`, harness adapters | All actual launches already have one abstraction | Keep using it, with a fresh session, not provider-to-provider resume |

Before each edit, search every caller of the changed helper and all `chat`, `steps[0]`,
session membership, and step-kind assumptions in the affected modules and tests.
The working tree already has unrelated edits in server, tasks, app, styles, tests and PLAN.md.
Use anchored edits; do not reset, overwrite, or stage unrelated work.

## 3. Locked behavioral contract

### 3.1 Identity, progression, and scope

- Append monotonically numbered steps to the existing task. Preserve its ID, original goal,
  project directory, Prep artifacts, session IDs, previous step folders, attempts, and costs.
- New session means `resume=None` and no fork of the previous provider conversation.
  The project working tree is shared. This feature creates no worktree or filesystem snapshot.
- The source must be the current last step, with a completed turn and no live run, pending
  answer, active handover preparation, or unstarted successor. A completed task may be reopened
  by an explicit append. A manual boundary paused with `why: "choose next step"` is also
  eligible. Other paused, stopped, failed/stuck, and handed tasks must first use their existing
  recovery/resume/next-task actions. Historical steps are inspectable, not branch points.
- A replied legacy chat is eligible even though its task/step state still says `running`.
  Derive readiness from the actual run and filed turn, not just the task state string.
- Introduce optional `progression: "manual"` on tasks when this feature first appends a step.
  Absence preserves existing legacy behavior. Retain single-chat behavior until conversion.
  On conversion remove the legacy whole-task `chat` flag; derive chat behavior from the current
  step's kind. Do not retroactively migrate every task on startup.
- At a manual boundary, finish the step, persist evidence, and leave the task paused with
  `why: "choose next step"`, owner `fred`. Its ordinary Resume action must not restart the
  completed step or auto-advance; offer Add next step or Finish instead. Do not add Verify,
  Fix, Replan, or execute a plan
  automatically. New Code runs exactly one code step. A manual Verify FAIL reports failure
  and waits; it does not start a fix. Existing automatic tasks keep their current behavior.
- Manual Plan uses the existing design role/parser and saves the plan, but does not rebuild
  or run a chain from it. Implement this explicit branch; do not send Plan through the existing
  automatic plan expansion by accident. A subsequent manual step receives the applicable plan
  and its own instructions without pretending its step number matches the generated plan.
- New Chat steps use the normal conversation runner and can take multiple Continue turns.
  The new Chat prompt includes the handover; later Continue turns resume that same conversation.
- Once a successor is committed, earlier sessions cannot be continued through Console controls.
  An externally resumed old session invalidates an unlaunched request; surface it as a conflict.
  Do not let its events reopen or replace the current step.
- Finish task remains explicit and does not delete any history. The existing separate-task
  handoff flow stays available with distinct wording.

### 3.2 Next-step choices and routing

| UI work | Stored kind | Notes |
|---|---|---|
| Code | `code` | Normal editing tools and existing code role |
| Verify | `verify` | `checked` references the source step, including Chat |
| Investigate | `scout` | Existing read-only investigation role |
| Plan | `design` | Save plan, manual boundary, no chain expansion |
| Chat | `chat` | Fresh conversation with the handover |

Default work: Code; default model: Auto; instructions required and editable. Seed instructions
from a usable previous Next section, otherwise leave blank. For Verify use a concrete default
asking to check the previous step against its goal, tests, and unresolved risks without edits.
Do not infer a launch or work kind by parsing an ordinary assistant reply.

Resolve Auto through existing kind/effort/tier policy. For Chat use the existing run default.
For Auto Verify, use the source's actual rank/effort with the existing verify rule and eligible
check pool. Prefer a different actual model when an eligible alternative exists. Display the
resolved route; when none differs, say that it is a fresh session on the same model.
Never claim model independence merely because the session ID differs.

An explicit pick is an exact registered rung, not a tier alias. Validate kind compatibility,
enabled harness, executable and configured model. Preserve current check exclusions
(`opencode` and `cmd`) and budget/Fable holds. A disabled/missing explicit model is an error,
never silent Auto, Opus, or another provider. Do not globally change automatic-chain routing.
Use `fills.rank_of` for a non-Claude source Chat; `model_alias` alone cannot rank Astra.
Revalidate at launch; if Auto's resolved route changed since preview, refresh the preview and
require Start again. Existing paid-model/budget confirmation remains step-specific.

Verify retains the existing no-edit role and harness restrictions. A Bash allowlist alone is
not a filesystem security boundary; document actual adapter limits rather than claiming that
every provider enforces identical read-only execution. Never remove existing sandbox controls.

### 3.3 Handover package

Reuse the six sections in `tasks.HEADINGS`: Goal, Findings, Files touched, Troubleshooting,
Open questions, Next. Prefer a validated handoff from the source's **latest completed turn**.
An older valid handoff must not override a newer reply just because the newer reply has no block.

For an unstructured chat, first prepare a deterministic fallback from the original task goal,
latest reply, available saved plan/decisions, and code-read facts. Mark it "Built from the last
reply". Unknown troubleshooting/questions must say "Not recorded", not invent answers.
Do not automatically run a paid summarizer just to open the form. Reuse compaction only for
structured notes under its existing rules; preserve Goal, decisions, unresolved questions and
Troubleshooting. Long material can remain in a referenced artifact with a visible omission
notice; never silently cut a decision to fit `brief.build`'s generic new-task limits.

Package and record:

- source task, step, session, and completed-turn identity;
- task goal, plan references, source handoff/fallback, and Fred's separate next-step instructions;
- source end commit and changed-file evidence where available;
- recorded test command/result/verdict with provenance; missing evidence explicitly unknown;
- current git facts and time of capture, clearly separate from the old step's results;
- source artifact references and any compaction/omission metadata.

Preview and launch must use the same saved package. Use an opaque revision covering source
turn, relevant artifacts and captured facts. Recheck source/run state and git facts at launch;
staleness refreshes the preview, not a hidden substitution. It is a consistency check, not a
lock against other tasks editing the shared folder. Keep the new step's existing `received.md`
manifest and save the exact handover body as `received-handoff.md` in that step's folder.
Do not rewrite old notes to manufacture a successful HANDOFF block.

### 3.4 Service operations and persistence

Use one shared Hub operation, called by UI and agent bridge. Proposed endpoints are new;
they are not existing API capabilities:

- `POST /api/task/next/preview`: task, source step/session, kind, instructions, requested rung
  (`auto` or exact ID). Validate inputs and return package revision, preview, resolved route,
  availability/hold reasons. Local preparation only, no model launch.
- `POST /api/task/next`: the same request plus preview revision and a stable request ID.
  Commit one successor and start through the existing scheduler. Return task ID, step number,
  request ID and status (`starting`, `running`, or existing hold state), not a fabricated session.
- `GET /api/task`: expose next-step availability, source revision, pending request and concrete
  reason when off. UI must not independently reproduce business rules.

Reject malformed types, oversized instructions (reuse the existing step-goal bound), unknown
kind/model, foreign source session, unsafe IDs, changed source, and invalid task state.
Resolve cwd from the task; accept no client-supplied cwd or command. Existing loopback guard
and POST header remain mandatory. `Hub.levers` stays authoritative for existing session
actions; `Hub.task_levers` owns append availability and includes it in task detail.

Under `tlock`, validate source and deduplicate request ID, reserve the next number and persist
the request before any process launch. Store the request ID on the new step. Repeat submission
returns the same result; changed payload under the same ID is a conflict. Only one successor
can win for a source turn. Do not hold the lock during model work or long subprocess activity.
Reuse atomic task persistence and chain events. Recovery must distinguish unlaunched,
launched, held and failed requests using task metadata plus run metadata. If launch outcome
cannot be established after a crash, show a recoverable stuck state; never blindly launch twice.
Retry uses the same step/attempt machinery, not a duplicate numbered step.

### 3.5 Agent control, Stage B

Do not route through Claude's Agent tool, add a provider API, parse prose as commands, or
enable arbitrary MCP servers. The smallest provider-neutral bridge is a standard-library
Console client module (`console/next_step.py`) invoked through an existing shell tool, with
structured JSON on stdin/stdout. Expose `models`, `preview`, `request`, and `status` operations.
Launch it with the Console's absolute Python/module location so it works from other projects;
provide the exact invocation through run instructions, never assume the project can import it.

Reuse the shared Hub operation behind a dedicated scoped agent endpoint. Give supported runs
a random per-session capability through their environment, not prompt text or command arguments.
Persist its digest and source binding under Console home for recovery; redact it from logs and
errors. It authorizes only model listing, preview, and one next-step request for that source task
and turn, not arbitrary projects, config changes, deletes, or existing browser POST operations.
Validate capability, source identity and request on every call; revoke on conversion, task finish,
clear/delete, or accepted successor. This narrows the supported interface; it is not isolation
from a malicious same-user process with unrestricted filesystem access.

When Fred says "start a verify session with Astra", the agent resolves Astra against the live
model list and submits one explicit request. An unambiguous display name may resolve to
`codex:gpt-6-astra`; ambiguous names fail with available choices. Do not hard-code alias guesses.
Persist the pending request while the requesting turn is still live. Reply "queued after this
turn", not "started". After the turn ends successfully, refresh its handover from the final
reply/facts and launch the successor. This deferred-finalization behavior is explicit in the
tool contract; an agent preview during a live turn is provisional. A question, interruption,
failure, source conflict or unmet hold stops automatic dispatch and displays the reason.
Show the queued request immediately with Cancel in the Board; cancellation and dispatch use
the same lock. Cancel after launch uses existing Stop semantics, not deletion.

Only explicit user instructions authorize a request. Put that constraint in the bridge tool
instructions; do not claim that a token proves the natural-language authorization. Handover
content is data, never authorization to spawn another step. Do not equip automatically spawned
steps with an inherited instruction to keep spawning. One accepted request closes the source's
capability. Unsupported harness/tool combinations show "Use Add next step in the Console".
For read-only kinds without a shell tool, keep this fallback; do not expand their tool access
solely for orchestration. Existing running sessions need a newly prepared continuation before
they receive bridge instructions/capabilities; do not imply retrospective availability.

## 4. Guided implementation sequence

Each task ends with its checks and an update here. No whole-file replacements or new framework.

### Task 1: Manual progression and compatibility

Files: `console/tasks.py`, `console/server.py`; focused task/server tests and fixtures.

1. Add the optional manual progression contract and pure append validation/transition helpers.
2. Remove first-chat assumptions only where needed: `_chat_tick`, `_advance_one`, snapshot
   membership, `task_row`, `_ended`, `_go_on`, session/task levers, and cost aggregation.
3. Finalize/retain the source Chat when converting; dispatch later Chat steps by current kind.
4. Add manual completion branches before automatic Verify/Fix/Replan/plan expansion can run.
5. Block past-step continuation and preserve recovery/Stop semantics for the current step.

Check: legacy single chat and automatic chain unchanged; Chat -> Code -> Verify retains one ID,
correct numbering/costs, and all artifacts; manual FAIL stops; manual Plan does not schedule work;
chat at step 03 can Continue without modifying step 01; reopen done works; past-step resume denied.

### Task 2: Package, exact route, preview and append API

Files: `console/server.py`, `console/tasks.py`, `console/brief.py`, `console/facts.py` only as needed;
reuse `compact.py`, `fills.py`, `runs.py` and harness adapters; tests in matching modules.

1. Implement local package preparation with source-turn freshness and saved preview revision.
2. Resolve route and validate exact picks, including non-Claude source rank and check exclusions.
3. Implement endpoints, lock/revision checks, persisted request ID and restart reconciliation.
4. Start via the existing run/step path; add Chat handling without indexing `RULES['chat']`.
5. Save exact received body and provenance. Surface holds/errors without substituting models.

Check: stale valid handoff vs newer plain reply; missing/oversized artifacts; unknown test result;
non-git project; exact Astra route; disabled Astra; Auto preview changed; duplicate POST; conflicting
concurrent requests; disk write failure before launch; launch failure and retry; restart before and
after process creation. Use fake harnesses and temporary Console homes, never live credentials.

### Task 3: Board and compact session UI

Files: `web/app.js`, `web/style.css`, `web/index.html` only if existing containers cannot suffice;
`tests/test_web.py`, existing browser fixtures. Follow the linked design guideline exactly.

1. Render the footer from server availability on the current completed turn.
2. Add the inline Work/Model/Instructions form, handover disclosure, route and source summary.
3. Wire preview, Start, Cancel, errors and preserved draft. Bind to task + source step/session;
   never use a mutable global selection to decide which session the submitted form belongs to.
4. On success select the new step's Chat tab in the same task; keep its older steps accessible.
5. Restore Continue, Hand off and Finish where allowed; expose existing separate-task action
   clearly. Existing Verify entry points for eligible tasks open this form with Verify selected.
   Loose terminal/external sessions keep their existing behavior; importing them is out of scope.

Check: source changes during request; snapshot refresh while typing; old-step selection; double click;
held model; hidden/unavailable actions have reasons; focus after Start/Cancel/error; no transcript
scroll jump; 900/400/340 CSS px; dark/light; 130% text scaling; keyboard and reduced motion.

### Task 4: Stage A acceptance and documentation

Run `py -m unittest discover -s tests` and `node --check web/app.js`. Run a bounded headless
browser pass with fake harnesses at the three widths, fix failures, then one confirmation pass.
Record baseline failures separately rather than changing unrelated tests to force green.
Update CLAUDE.md's Board write contract and task/session documentation to describe only what shipped.
Stage A is complete only when a real UI action creates the fake fresh session and its received
package, not just when render tests find button labels. Do not mark live provider checks complete.

### Task 5: Agent bridge, after Stage A

Files: new `console/next_step.py`, scoped service routes, `runs.py` environment plumbing and
eligible run prompt construction; narrowly scoped adapter changes if required; bridge/service/run tests.

1. Implement the JSON client and scoped capability lifecycle without a new dependency.
2. Inject explicit usage/authorization instructions and the supported invocation into new eligible
   runs and prepared continuations. Keep secrets out of prompt/transcript and argv.
3. Add persisted pending request, final-turn packaging, deduplication, cancellation, and dispatch.
4. Display requested kind/model and status in the same Board footer. Tool response and UI status
   must agree about queued, held, started, rejected and failed states.

Check: agent asks for Astra from a fake Claude Chat; same task/folder, fresh Codex session only
after source exits; duplicate tool call; unknown/ambiguous model; stale/foreign/revoked capability;
attempt to target another task; invalid instruction length; interrupted source; STOP question;
queued cancel; service restart; no automatic successor loop. Assert secrets absent from artifacts.

### Task 6: Final integration and close

Repeat the relevant full checks after Stage B. Manually inspect the fake end-to-end sequence
Chat -> Code -> Verify and a direct Chat -> Astra Verify request. Confirm existing automatic
chains, Continue, handoff-to-new-task, budget/Fable holds, Stop, retry and old saved tasks still work.
When Fred authorizes live checks separately, test one configured cross-provider launch and its
actual sandbox/model availability. Report what was verified locally versus on a real provider.
Mark each stage shipped independently; keep any missing bridge/harness support explicitly open.

## 5. Definition of done and drift guard

- [ ] One task, stable history, same folder, fresh session with saved handover.
- [ ] Exact model selection works or explains why it cannot; no silent provider substitution.
- [ ] Manual boundaries cannot fall into automatic chain behavior.
- [ ] UI and agent calls share service validation and launch machinery.
- [ ] Concurrent clicks/calls and restarts cannot silently create duplicate runs.
- [ ] Missing context is visible; no invented tests, decisions or prior success.
- [ ] All specified UI states pass the design checklist.
- [ ] Compatibility, focused tests, full suite and fake end-to-end evidence recorded.
- [ ] Stage A and Stage B status reflect actual shipped behavior.

Excluded: branching/DAG UI, arbitrary old-step forks, global workflow builder, auto-running
suggestions, automatic fixes in manual mode, new model SDK/provider integration, generic MCP
enablement, replacing the Console design, worktrees, background task queues across projects,
and rewriting historical plans. New test infrastructure is unnecessary where current fakes suffice.

If a needed change extends these boundaries, document the specific conflict first. Routine
implementation choices within this contract do not need a new approval round.

## 6. Implementation log (Stage A)

- 2026-10-15 - Part of Stage A was already in the working tree when this task started: Task 1's pure
  helpers (`tasks.NEXT_KINDS`, `tasks.append_step`, the manual branches of `tasks.on_step_ended` and
  `tasks.fred`) and most of Task 2 (`Hub._next_source`, `next_availability`, `_next_package`,
  `_next_route`, `next_model_options`, `preview_next`, `request_next`, the preview/append routes,
  `task_levers["add_next"]`), with no tests and no Board UI. Fred chose to build on it. Every line of
  it was read against section 3 before its tests were written; a line the contract does not allow was
  changed, not kept.
- 2026-10-15 - Task 1 placed: manual progression and compatibility. Tests first
  (`tests/test_tasks.NextStepTest`, `tests/test_server.NextStepServerTest`). Differences from the
  pre-existing code, all contract-driven: `Hub.levers` blocks every step session of a manual task
  with "Next steps start from the latest step" except the newest chat step, which keeps its turns
  (section 3.1, historical steps are not branch points); that lookup needs `Hub._task_of_session`,
  because a chat task's session carries no task id of its own (plan 29); the preview revision no
  longer covers the rendered text, the capture time or the route's notes, so two previews of an
  unchanged source agree (3.4); `_chat_tick` no longer writes `last_good = 1` for every chat step.
  Check: 12 pure tests and 8 service tests pass; the rest of Task 1's check list is Task 2's and
  Task 3's subject.
- 2026-10-15 - Task 2 placed (commit 53bbd41): the handover package, the exact route, preview and append
  API; NextStepTest 13 and NextStepServerTest 20.
- 2026-10-15 - Task 3 placed (commit f4cf339): the Board's Add next step footer and inline form;
  NextStepUITest 13 in `tests/test_web.py`.
- 2026-10-15 - Task 4 placed: Stage A acceptance. Bounded headless pass (Playwright, Chromium, fake claude,
  a scratch `CC_CONSOLE_HOME`, the service in-process): at 900 px dark a real click on Add next step, typed
  instructions and a click on Start step appended step 02 `code` to the same task with a new session id, wrote
  `tasks/<id>/02-code/received-handoff.md` (the six sections) and `received.md`, selected step 02 on its Chat
  tab, and the step ended at `choose next step` with step 01 unchanged. Then 900 light, 400 and 340 px light
  and dark, reduced motion, and 130 % text scaling (device scale 1.3 at 400 and 340 px, as WebView2 does):
  footer and form with no horizontal overflow, no motion in the form under reduce, Cancel returns focus to
  Add next step, Enter reopens and Escape closes the form, nothing starts, no page errors. The first pass
  found two `web/app.js` failures, both fixed: (1) Start after editing the instructions posted the revision of
  the earlier preview, which covers the instructions, so the service answered "This step changed" and a second
  click was needed; Start now previews the edited Work/Model/Instructions first (`nextStale`) and starts at
  once unless the resolved route changed, which still needs Start again (3.2); (2) a Work switch reseeded the
  draft but `setHtml` kept the field's old text over the redraw, so Verify showed "Go on" while Start would
  send the Verify default; `setInstr` writes the open field too. Two tests in NextStepUITest. Fix pass and
  one confirmation pass: 69 of 69 checks each. `node --check web/app.js` OK. Not done: live provider checks.
