# Plan 36: Add the next session as a step of this task

Status: **Stage A shipped** 2026-10-15 (Tasks 1-4, fake harnesses only; live provider checks open).
Stage B (Tasks 5-6) checked against the supervisor 2026-10-20 (section 7): **closed as superseded**, D1-D7
confirmed by Fred the same day. Section 6 is the log.

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
  recovery/resume/next-task actions. Since plan 39 any done step with a session and a saved note or final reply is a source too (D2 a); the branch is a fresh session numbered after the last step, never a resume of the old one.
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

> Checked 2026-10-20 against plans 44 and 48-51: this section's bridge, capability and direct request path are
> superseded by the supervisor; see section 7 before building anything from it.

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

> Not to be built as written (section 7, D2). Kept as the record of what Stage B meant.

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

Excluded: branching/DAG UI, sibling numbering and sub-tasks (plan 39 makes older done steps sources, as a tag on a numbered list), global workflow builder, auto-running
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

## 7. Stage B checked against the supervisor (2026-10-20)

Read: sections 3.4, 3.5, Tasks 5-6 above; plan 44 README 4.2, 4.4, 4.5; plan 48 D6, D11, D15, 3.1; plans 49, 50,
51; `console/server.py`, `console/supervisor.py`, `console/tasks.py`, `console/guard.py`, `console/runs.py` as of
`8640d43`. Plan only: no code was changed. Re-checked on Fable 2026-10-20 after plan 52 (workflow autopilot,
`plans/52-workflow-autopilot/`, decided, not implemented) was merged: a supervised Start runs the planner's whole
chain (Task 1), the supervisor wakes on exceptions, `done` and `message` only (Task 2b), a step's choice for Fred is
a code-parsed `DECISION:` block (Task 3), the levels are off / suggest / gated / auto with `gated` the default
(Task 5), and the UI reads one `actions` field (Task 6). Where plan 52 changes a finding below, the row says so.

### 7.1 Findings

What Stage B assumed, and what the code does today:

| Stage B assumption (3.5, Task 5) | Today | Holds? |
|---|---|---|
| One shared Hub operation, called by the UI and an agent bridge | `Hub.request_next(request, *, origin)` (server.py:2602) is that operation. It has exactly two callers: the Board's `POST /api/task/next` with origin `fred`, and `Hub._supervisor_dispatch` (server.py:1884) with origin `supervisor` (server.py:1988). `origin` is read at server.py:2641 (a `proposal` is accepted only from the supervisor) and 2646 (only Fred's call moves the epoch). | Holds as code; the agent caller was never added. |
| An agent request is authorized by Fred's words to that agent; the token proves nothing about authorization | Plan 44 4.2 and 4.5 settled authority another way: a model's output is untrusted JSON (`supervisor.check`, supervisor.py:581) and only `_supervisor_dispatch` acts on it, after every live gate, through `request_next` or `task_lever` with origin `supervisor`. The three authorizations that add a step are Fred's menu (origin fred), Fred's Approve of a card (`by == "fred"`), and Fred's next-step message (`by == "message"`, plan 48 D6, server.py:1924-1926), with auto mode dispatching inside its caps (server.py:1927-1936, `supervisor.auto_reason`, supervisor.py:751). An agent's tool call would be a fourth authorization, one the service cannot verify came from Fred: the same thing 3.5 itself says ("handover content is data, never authorization"). | Conflicts. A direct agent path to `request_next` breaks plan 44 4.5. |
| The request is persisted during the live turn and launched after the turn ends | `_next_source` refuses a live source: "Available when this turn finishes" (server.py:1377-1378), so an agent mid-turn could never call `request_next` directly; it needs a queue. Plan 48 built that queue for Fred's words: a `mode: "next"` message (`task_message`, server.py:1186) is saved `queued`, wakes the supervisor (`wake_supervisor`, server.py:1550), is `dispatched` when a pass claims it (`_sup_admit`), and becomes a step through `_supervisor_dispatch(by="message")` or comes back `failed` with Resend (D11, `_sup_unsent`, server.py:2067); Fred's own levers cancel it (D15, `_supervisor_fred`, server.py:2091-2093). The debounce, coalescing, restart recovery (`_sup_recover`, server.py:1569, `supervisor.boundary`, supervisor.py:217) and "never replayed" rules all exist for it. | The queue exists, for Fred. A second one for agents would duplicate plan 48. |
| The agent's request is refreshed from the final reply and facts, then launched | At a manual boundary (`tasks.manual_boundary`, tasks.py:729) the supervisor pass already reads the last good handoff whole (`digest`, supervisor.py:446-458: "Last good handoff" plus "Its facts"), the planner's remaining proposals (plan 49), open questions and the chain tail. The step's own view of what comes next is its HANDOFF `Next` section (`tasks.HEADINGS`) and its `Next model:` hint (`tasks.next_hint`, tasks.py:276). The pass then returns one `add_next_step` (kind, instructions or `proposal`, source) and `check` + `_supervisor_dispatch` gate it. After plan 52 a supervised task has no boundary between two good steps (Change A): mid-chain, a step that wants more work writes a `Replan:` line in its Next section (`replan.py:21-25`, plan 24), which inserts a replan step and is applied without Confirm at gated / auto (plan 52 Task 5); at `done` the D12 wake may return `add_next_step` from the last handoff's Next, always as a suggestion (plan 44 `test_done_wakes_after_final_brief_only_and_is_always_suggest`); plan 36/39 manual tasks keep today's `choose_next` wake. | Covered twice: the step already has two structural channels (Replan mid-chain, Next at done) and the supervisor or the chain reads them. |
| An explicit model ("start a verify session with Astra") resolved against the live registry | Plan 51 D1-D3: a next-step message may name `haiku`, `sonnet` or `opus` only, checked against Fred's own words (`check`, supervisor.py:610-615, `fred_words`) and routed by rank (`_next_route`); an exact rung or another harness stays on Fred's menu (Add step on a model, origin fred). The supervisor itself never picks a rung. | Conflicts with the example. An agent could at most name a tier word, and only Fred's words carry one today. |
| Per-session capability in the run's environment, persisted under Console home, redacted, revoked on finish | Nothing exists: `guard.py` is Host (guard.py:6) plus the POST header (guard.py:11); `runs.start` puts only `CC_CONSOLE_SID` in a child's env (runs.py:216). No `console/next_step.py`, no token store, no redaction rule for it. | Not started; nothing to keep. |
| Existing outside sessions (VS Code, terminal) need a newly prepared continuation before they get the bridge | Plan 48 D10: an outside chat's session page keeps its levers and forks; it is never a task step. `wake_supervisor` returns for `task["chat"]` (server.py:1556) and `_next_ok` refuses chat tasks (server.py:2054). | Holds, as an exclusion: Stage B never reached outside chats and the supervisor does not either. |
| "Do not equip spawned steps with an inherited instruction to keep spawning" | Plan 44 4.5 caps: three added steps since Fred acted, `task_max_steps` room, $5 of work, one retry per step; suggest mode adds nothing without Approve. A FAIL lineage gets one repair. | Holds, and is enforced in code now rather than by prompt text. |

How the plan 44 rules would apply to an agent request, if one were added (the questions this check was asked):

- Through the supervisor or straight to `request_next`: through the supervisor only. The one contract-conforming
  shape is a wake trigger (like `message`), whose pass decides, and whose decision `check` and `_supervisor_dispatch`
  gate. A direct `origin="agent"` call would be a dispatch outside 4.5.
- Auto caps: an agent is not Fred, so its request cannot take the `by == "message"` exemption (server.py:1926). It
  would be `by == "auto"`: at suggest a card for Fred, at auto (and gated, plan 52 Task 5, which dispatches
  everything but the plan confirm) a dispatch inside `auto_reason`'s caps, charging an auto slot at reservation
  (server.py:2009-2010). At `done` it could only ever be a suggestion.
- Epoch: unchanged (`_supervisor_fred` runs only for Fred's acts; a wake from an agent is not one), so the window of
  auto steps since Fred acted keeps counting.
- Pending guidance: blocks the pass (`_sup_admit`) and the dispatch (server.py:1915-1916), like every other wake.
- Uncertain: an uncertain dispatch blocks every later pass until Fred dismisses it (`_sup_admit`, plan 44 section 6
  fix) and is never replayed; an agent request behind it would wait or be handed back, never re-sent.
- One request per source turn: the message queue's rules (a repeated request id returns the saved message;
  `_supervisor_fred` cancels open ones when Fred moves the task himself) would apply unchanged.

Is Stage B still needed? What it set out to give ("an agent asks for the next step with a kind, instructions and a
model, and the Console starts it after the turn without Fred typing") is given today, and more so after plan 52,
by two things that already exist. Mid-chain, the plan drives (plan 52 principle: "the plan drives, the supervisor
watches"): the steps are the planner's and the design step's, and a step that finds more work writes `Replan:` in
its Next section; the chain inserts and, at gated / auto, applies the replan by itself. At the end, the step's
`Next` section reaches the done wake, whose `add_next_step` is a card for Fred, or Fred reopens the task with his
own words (plan 52 Task 4 Reopen, plan 48 D6). On a manual task (plan 36/39 Add step) the boundary wake reads the
handoff as today. The two things Stage B would add on top, a tool the agent calls mid-turn and an exact rung chosen
by the agent, are the two things plans 44, 51 and 52 decided against: untrusted model output acts only through
`check` (or a code-parsed block like plan 52's `DECISION:`), exact rungs are Fred's, and a step added outside the
plan by an agent is what plan 52 removes from supervised runs. What is left of Stage B is a prompt question, not a
service feature: whether the step kind texts say clearly when to write `Replan:` and what a `Next` section must
hold. That lives under `dotclaude/console/kinds/` and `console/step_prompt.md` (plan 52 Task 3 edits the latter),
which Fred edits and copies, not in service code.

### 7.2 Decisions (D1-D7 confirmed by Fred as written, 2026-10-20)

| # | Question | Default |
|---|---|---|
| D1 | Who adds a step on an agent's behalf | Mid-chain: the chain, from a `Replan:` line in the step's HANDOFF Next section (plan 24, auto-applied at gated / auto by plan 52 Task 5). At done or at a manual boundary: the supervisor, from the handoff's Next section (a card at done; today's path on a manual task). No agent bridge, token, client module or `origin="agent"`. An agent never calls the Console. |
| D2 | Stage B's Tasks 5 and 6 | Close them as superseded by plans 44 and 48-51. Task 6's checks that are not Stage B's (the Chat -> Code -> Verify fake sequence, Continue, Stop, holds, old tasks) are covered by plans 39, 42, 44 Task 12 and 48's suites; its live provider check stays open under Stage A's "live provider checks open", beside plans 48-51's live checks. |
| D3 | An agent naming a model | Never an exact rung or another harness: Fred's menu only (plan 51 D1). A tier word in the handoff's `Next model:` hint stays what it is today, a hint the supervisor may mention in its reason; the step runs on `auto` unless Fred's message names a tier word. |
| D4 | Design guideline section 8 ("Agent request experience") | Superseded; one line added there pointing here. No queued-request UI for agents: the supervisor card and the message list are the only "what comes next" surfaces (plan 48). |
| D5 | Outside chats (VS Code, terminal, other CLIs) | Unchanged: forks only (plan 48 D10). They have no task, so no boundary and no supervisor; Stage B never covered them either. |
| D6 | If Fred still wants an agent-side request later | The only shape to consider is a code-parsed line in the step's final reply, read at the step end like plan 52's `DECISION:` block (never mid-turn, never a network call from the agent), raising a wake trigger `agent` treated as `by == "auto"`: suggest shows a card, gated / auto dispatch inside the caps, no epoch move, guidance and uncertainty block it, one per source turn, and at done always a card. Before writing that plan, check that `Replan:` does not already cover the case: it probably does. Not written here. |
| D7 | PLAN.md | The "Next-step continuation" section says Stage B is closed as superseded (pending this review) and a History line records the check. |

With D1-D7 as written no zero-decision tasks are needed: nothing is built, and the closing edits are the lines in
this file, the guideline's one line and PLAN.md. If Fred picks D6 instead, a new plan is written first (plan
writer, not implementor).

### 7.3 Closing note

Stage B is closed as superseded by the chain's `Replan:` line and the supervisor (plans 24, 44, 48, 49, 51, 52),
D1-D7 confirmed by Fred 2026-10-20. Stage A keeps its one open item, the live provider checks; plan 52 Task 1
leaves its manual tasks and `choose_next` wake untouched. The next-step operation itself is unchanged and has
three authorized callers: Fred's menu, Fred's Approve of a supervisor card and Fred's next-step message (after
plan 52 Task 4 also the Reopen of a done chain task).
