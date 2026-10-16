> Mirrored by Claude Console from its task folder tasks/20261016-095927-6346/02-design/ for history. Edit the console's copy: this file is rewritten.

# Plan: Claude Console security, workflow and reliability audit

## Goal

Audit the current Claude Console working tree without changing files. Identify security gaps, contradictory behavior, task workflow failures, avoidable performance costs and states that prevent progress.

Claude Console is a local, single-user application that monitors CLI sessions and runs task chains across several harnesses. This audit assumes one Windows user, several concurrent tasks, service restarts and occasional subprocess or filesystem failures.

Completion consists of this prioritised findings report and the existing step 3 test run:

```powershell
py -m unittest discover -s tests
```

Run it from `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE`. Report the actual `Ran N tests` summary, outcome counts, exit code and every failing or erroring test name verbatim. No test count or passing result is claimed by this design step.

## Decisions

- Audit the current working tree, including its existing changes; the scout’s clean-tree statement no longer describes this checkout.
- Read the hook at repository-root `cc_events.py`; `console/cc_events.py` does not exist.
- Work alone and make no file edits.
- Keep the existing next step as a test run; add no implementation or document steps.
- Treat suggested corrections and focused test scenarios below as audit recommendations, not authorisation to implement them.
- Mark a finding **Confirmed by reading code** when the stated input or failure condition follows directly through the implementation.
- Mark a finding **Suspicion needing a test** when scheduling or external process behavior must establish the outcome.
- Use **P1** for unintended write access, lost supervision, lost handoff continuity or service-wide blocking; use **P2** for narrower workflow, security and performance gaps.
- Do not classify an unexecuted test as passing, failing or reproducing a finding.
- Do not equate passing the existing suite with disproving findings that need additional fault-injection tests.
- Preserve the project’s single-user localhost design; this report does not require remote authentication or a new service architecture.

### Prioritised findings

#### A01. P1 — Read-only design and search steps receive writable non-Claude execution settings

**Confirmed by reading code.**

**Evidence:** `console/tasks.py:30`, `console/tasks.py:39`, `console/server.py:42`, `console/server.py:1467`, `console/server.py:1470`, `console/runs.py:190`, `console/harness/codex.py:61`, `console/harness/opencode.py:45`, `console/harness/cmd.py:43`.

The service recognises read-only work only when the tool string equals `Read,Grep,Glob`. Search and design add web tools, so both produce `read_only=False`. The tool list itself is forwarded only to Claude. Consequently, a design step routed to Codex receives `workspace-write`; OpenCode receives no read-only permission override. Search has the same problem, including Command Code’s `accept-edits` setting.

This contradicts the no-edit role of these steps and permits accidental repository changes during an audit or design.

**Smallest correction:** Determine read-only status from whether the step’s tool policy permits mutation, and apply that status consistently through every adapter.

**Focused check:** Inspect generated commands and environments for scout, explain, search and design on each eligible harness. All four must retain read-only settings; write kinds must retain their intended permissions. The existing Codex scout assertion at `tests/test_server.py:2700` covers only the exact-string case.

#### A02. P1 — An exception outside task advancement can permanently stop the hub

**Confirmed by reading code.**

**Evidence:** `console/server.py:455`, `console/server.py:460`, `console/server.py:261`, `console/server.py:269`, `console/events.py:35`, `console/state.py:164`, `console/state.py:348`.

`Hub.advance` catches failures separately for each task, but `Hub.run` does not protect polling, automatic actions, cost reading or reconciliation. Event validation checks only that an object has a session ID and event. For example, an event with `ts: "bad"` can reach a numeric conversion or mixed-type sort and raise.

The hub thread then exits while the HTTP server remains available. Tasks stop advancing and the window can continue showing stale state.

**Smallest correction:** Validate event field types before applying them, isolate individual bad records, and keep the hub loop alive with a logged error when one operation fails.

**Focused check:** Feed a malformed event followed by a valid event and verify that the valid event is processed and subsequent hub iterations run. `tests/test_server.py:1571` covers a bad token count in the separately guarded accounting path, not these earlier failures.

#### A03. P1 — Filesystem failures can leave processes unsupervised or lose their completion permanently

**Confirmed by reading code.**

**Evidence:** `console/runs.py:106`, `console/runs.py:215`, `console/runs.py:217`, `console/runs.py:222`, `console/runs.py:237`, `console/runs.py:280`, `console/runs.py:307`, `console/runs.py:327`, `console/runs.py:381`.

Process launch precedes metadata persistence, the start event and watcher creation. A metadata or event write failure after launch leaves a running process without the normal watcher. The task’s start handler records a failure before receiving its session ID.

Completion has another failure window: `_finish` saves `ended` before emitting `run_ended`. An event-write failure leaves metadata marked ended, but the state machine never receives completion. `_watch` has no `finally` cleanup; reconciliation skips entries still in `live` and later skips metadata already marked ended.

Metadata is also written in place, allowing concurrent readers to observe an incomplete JSON file.

**Smallest correction:** Make metadata replacement atomic, handle failed post-launch setup by closing or supervising the child, guarantee watcher cleanup, and make completion publication recoverable.

**Focused check:** Inject failures at the initial metadata write, start-event append, final metadata write and completion-event append. Every launched child must remain stoppable, and every ended run must eventually produce one effective completion.

#### A04. P1 — A failed brief write releases the next step without its handoff

**Confirmed by reading code.**

**Evidence:** `console/server.py:1784`, `console/server.py:1787`, `console/server.py:1797`, `console/server.py:1800`, `console/server.py:1805`, `console/server.py:1826`, `console/server.py:1411`, `console/tasks.py:957`.

`_brief_done` clears both the in-memory worker flag and `task["briefing"]` before writing the brief. It silently catches an `OSError`. The next advancement sees no pending brief and starts the next step; `read_brief` supplies an empty or incomplete handoff.

A temporary disk or file-sharing error can therefore remove the context on which the next writer depends.

**Smallest correction:** Save the brief successfully before releasing the task. Preserve a retryable pending state or surface a stuck state on persistence failure.

**Focused check:** Make `tasks.write_brief` fail once. Assert that no successor starts until a complete brief has been saved.

#### A05. P1 — A child that does not read stdin can block all automatic task control

**Confirmed by reading code; occurrence with a particular CLI needs reproduction.**

**Evidence:** `console/server.py:1497`, `console/server.py:1477`, `console/server.py:1967`, `console/runs.py:215`, `console/runs.py:241`, `console/runs.py:259`.

Automatic advancement holds the global task lock while starting a process. `_spawn` synchronously writes and flushes the prompt to the child’s stdin. There is no deadline on that write. Registration in `live` and watcher creation happen only after `_spawn` returns.

A child that stays alive without consuming a sufficiently large prompt can block this write indefinitely. Other task operations, including Stop, then wait for the same task lock.

**Smallest correction:** Register and supervise the child before potentially blocking input delivery; keep that delivery outside the global task lock and bound its duration.

**Focused check:** Use a child that never reads stdin and a prompt larger than the pipe capacity. An unrelated task’s Stop must remain responsive, and the stalled launch must terminate or report failure within a bound.

#### A06. P1 — Manual next-step launch can race with Stop or Delete

**Suspicion needing a test.**

**Evidence:** `console/server.py:1229`, `console/server.py:1245`, `console/server.py:1255`, `console/server.py:1256`, `console/server.py:1382`, `console/server.py:1967`.

`request_next` saves and publishes a reservation under `tlock`, releases the lock, then calls `start_step` on the saved task object. `start_step` does not recheck ownership or cancellation. A concurrent Stop can change the reservation to stopped; Delete can subsequently remove it before the original request proceeds.

The suspected outcome is a process launching after Stop, or after its task was deleted, followed by stale state being saved.

**Smallest correction:** Make cancellation and the transition from reservation to launch mutually exclusive, while keeping blocking process I/O outside the global lock.

**Test to settle it:** Pause the request immediately after publishing the reservation. Complete Stop in another thread, then release launch. Assert that nothing starts. Repeat with Stop followed by Delete. Existing sequential request-ID tests do not establish this ordering.

#### A07. P2 — Secret masking still misses ordinary JSON credentials and agent descriptions

**Confirmed by reading code.**

**Evidence:** `console/redact.py:16`, `console/redact.py:24`, `console/redact.py:47`, `console/redact.py:59`, `cc_events.py:408`, `cc_events.py:414`.

The assignment pattern expects a key immediately followed by whitespace and `:` or `=`. A quoted JSON key such as `{"password": "hunter2"}` has a closing quote before the colon and is not matched. A value without a recognised token shape remains visible.

The Agent/Task summary branch also clips the description without calling `mask`. A description containing `password=*** reaches the event’s `what` field unchanged.

**Smallest correction:** Cover quoted assignment keys and apply masking to free-text agent descriptions before clipping.

**Focused check:** Pass synthetic JSON credentials through `mask`, and synthetic credentials in an Agent description through `build_record`. Assert that the secret values never appear in the resulting event. These are residual gaps beyond plan 34’s added token shapes.

#### A08. P2 — Some Command Code task steps have no effective cap

**Confirmed by reading code.**

**Evidence:** `console/harness/cmd.py:11`, `console/harness/cmd.py:39`, `console/harness/cmd.py:46`, `console/server.py:1471`, `console/runs.py:184`, `console/runs.py:296`.

Command Code declares `CAPS=True`, which disables the service’s timeout fallback. Its adapter accepts but does not enforce the budget argument. The service passes a turn limit only for design and the read-capped kinds; a Command Code code, draft or test step normally receives `max_turns=0`.

Those routes therefore have neither a supplied turn cap, an enforced spend cap nor the service timeout.

**Smallest correction:** Apply the watchdog when a run has no effective adapter-enforced cap, rather than relying solely on the adapter’s capability flag.

**Focused check:** Generate a Command Code code-step launch and verify that it receives an effective cap. A non-ending fake must eventually produce a timeout failure. Current Command Code tests establish cap behavior only when a turn limit is explicitly supplied.

#### A09. P2 — A failed kill attempt can leave the timeout watcher running forever

**Confirmed by reading code.**

**Evidence:** `console/claude_cli.py:227`, `console/runs.py:295`, `console/runs.py:297`, `console/runs.py:303`, `console/runs.py:335`.

`kill_tree` invokes `taskkill` without a subprocess timeout and ignores its exit status. The watcher marks `timed_out=True` before trying to stop the child, then never attempts another stop. If the command fails while the process stays alive, the watcher loops indefinitely.

On POSIX, the same function still invokes the Windows-only command; this is the already documented plan 27 gap. On Windows, an unsuccessful or hung `taskkill` remains relevant. The normal Stop path also invokes the adapter while holding the run-manager lock.

**Smallest correction:** Bound and check termination, confirm that the process exited, and give a failed termination an explicit recoverable outcome.

**Focused check:** Make the stop operation return without terminating the fake process, then make it raise. Neither case may leave an unreported infinite wait. The current timeout test at `tests/test_runs.py:307` covers successful termination.

#### A10. P2 — Briefs can silently discard unresolved questions

**Confirmed by reading code.**

**Evidence:** `console/compact.py:148`, `console/compact.py:160`, `console/compact.py:212`, `console/compact.py:227`, `console/compact.py:234`.

The model-output check asks only whether some question remains. Two incoming questions can become one and still pass.

The fallback and short-note paths take Open questions only from the current note. If the earlier brief has an unresolved question and the next note says `(none)`, that question disappears without an explicit resolution. The short-note path returns this result without the model-output checks.

**Smallest correction:** Preserve unresolved questions individually across brief paths, with an explicit rule for recorded resolutions.

**Focused check:** Carry two questions through a model brief that retains one; also carry an earlier question through a short current note containing `(none)`. An unresolved question must not disappear.

#### A11. P2 — Recovery depends on recent event files, even when task and run files remain

**Confirmed by reading code.**

**Evidence:** `console/events.py:11`, `console/events.py:17`, `console/server.py:1585`, `console/server.py:1586`, `console/runs.py:384`, `console/server.py:1350`.

At startup, `LogReader` reads only the newest two daily event files. Task files are loaded independently. `_ended` returns immediately when its session is absent from state, while reconciliation skips run metadata already marked ended.

A task can be saved as running, its process can finish, and the service can stop before closing the task. After enough newer event files exist, restarting does not reconstruct that session and the task cannot advance automatically from its persisted completion. Old chat tasks similarly depend on a session row.

**Smallest correction:** Reconcile loaded active tasks against their persisted run metadata and streams independently of the recent-event window.

**Focused check:** Load a running task with ended run metadata whose events are outside the two-file window. It must finish recovery or enter an explicit recoverable state rather than remain silently running.

#### A12. P2 — Proofread edits bypass automatic verification and write-plan requirements

**Confirmed by reading code.**

**Evidence:** `console/tasks.py:32`, `console/tasks.py:48`, `console/tasks.py:428`, `console/plan.py:163`, `console/plan.py:460`, `dotclaude/console/kinds/proofread.md:4`.

Proofread has Edit and Write tools, and its role explicitly fixes files. It is absent from `EDIT_KINDS`. A proofread-only task therefore gets no automatic verifier. The plan validator also does not require its write-step section, and prompt selection does not supply one as its own part.

**Smallest correction:** Classify proofread consistently as a write kind throughout planning and verification.

**Focused check:** A proofread-only proposal must receive the intended verifier, and a design plan preceding proofread must contain and deliver its write-step section.

#### A13. P2 — Growing window-run streams are repeatedly parsed under the snapshot lock

**Confirmed by reading code; user-visible latency is unmeasured.**

**Evidence:** `console/server.py:479`, `console/server.py:498`, `console/server.py:823`, `console/server.py:831`, `console/server.py:841`, `console/runs.py:24`, `console/runs.py:48`, `console/server.py:2492`.

The live-note cache stores the stream size, but each size change causes the entire current turn to be read and parsed again. Snapshot construction does this while holding `Hub.lock`. With frequent output, cumulative parsing grows with the history of the turn instead of only the newly appended bytes.

Window chat also reads the entire stream before selecting its last items. This differs from the bounded transcript-tail readers.

**Smallest correction:** Retain incremental parsing state for live-note extraction and avoid stream parsing while holding the snapshot lock.

**Focused check:** Measure bytes read for equally sized appended chunks and request latency during a large fake run. Preserve the complete final-message and plan paths; display optimisation must not truncate the saved plan.

#### A14. P2 — Prep, review and brief subprocess descendants may outlive cancellation or timeout

**Suspicion needing a test.**

**Evidence:** `console/server.py:438`, `console/server.py:474`, `console/prep.py:113`, `console/review.py:80`, `console/compact.py:249`, `console/runs.py:254`.

These background passes use `subprocess.run` directly and do not join the service job used for ordinary runs. Dropping a Prep card removes its UI state and files but does not cancel its subprocess. `Hub.stop` only sets the hub stop event.

Continued work after dropping a card is visible in the code. Whether timeout or service shutdown leaves descendant processes alive depends on the actual CLI process tree and requires testing.

**Smallest correction:** Give these passes explicit process ownership and cancellation, including their descendants.

**Test to settle it:** Use a fake pass that spawns a long-lived child. Exercise card dismissal, configured timeout and service shutdown separately; inspect whether both parent and child exit. Do not perform this experiment against real paid model calls during step 3.

### Plan 34 F1–F8 reconciliation

| Prior finding | Current assessment | Current evidence |
|---|---|---|
| F1: hook import escapes never-raise handling | Fixed in code; test execution pending | `cc_events.py:15`, `cc_events.py:500`; `tests/test_cc_events.py:303` |
| F2: additional secret shapes missing | The listed patterns were added. Residual gaps are A07; do not report the original patterns as still absent. | `console/redact.py:5`, `console/redact.py:16`; `tests/test_redact.py:21`, `tests/test_redact.py:30` |
| F3: denied reason unmasked | Fixed in code; test execution pending | `cc_events.py:417`; `tests/test_cc_events.py:158` |
| F4: recycled PID used by Stop/reconcile | Creation-time checks are present in both paths. The implementation deliberately falls back to PID-only checks when identity is unavailable. `is_live` still uses PID-only checks, so protection is not universal. | `console/claude_cli.py:215`, `console/runs.py:130`, `console/runs.py:347`, `console/runs.py:388`; `tests/test_runs.py:191`, `tests/test_runs.py:207` |
| F5: draft written in place | Fixed through atomic replacement and a controlled draft-write error response | `console/server.py:2481`, `console/paths.py:312`; `tests/test_server.py:203`, `tests/test_paths.py:174` |
| F6: installer config written in place | Fixed in `_save`, including temporary-file cleanup; the scout’s “partly fixed” status is stale | `install_hooks.py:127`; `tests/test_install_hooks.py:33` |
| F7: server tests read the user’s config/PATH | The named test setups contain the planned isolation; passing status awaits step 3 | `tests/test_server.py:166`, `tests/test_server.py:2548` |
| F8: bulk-delete test pins one racing refusal message | Both valid refusal messages are accepted | `tests/test_server.py:2324` |

### Corrections and checks that did not become findings

- The budget-hold dead end from older history is resolved: `tasks.fred` sets `hold_ok`, and the next launch consumes it. See `console/tasks.py:811`, `console/server.py:1390` and `tests/test_server.py:1247`.
- Clear includes every recorded attempt through `sessions_of` and `attempts`. See `console/tasks.py:1005`, `console/server.py:1812`, `tests/test_tasks.py:901` and `tests/test_server.py:1132`.
- A picked model remaining selected against a model hint is intentional. See `console/tasks.py:144` and `console/tasks.py:151`.
- All implemented GET and POST routes enter the shared guard. POST also checks `X-CC`; the service binds loopback. See `console/server.py:2127`, `console/server.py:2176` and `console/server.py:2684`.
- GET lacking `X-CC` alone does not establish browser-readable cross-origin disclosure. The inspected response code adds no permissive CORS header. No browser exploit was reproduced.
- Current GET `/api/config` calls `reload_models`, which uses `paths.load_models(write=False)`. The scout’s claim that this request creates `models.json` is unsupported by the current call path. See `console/server.py:102` and `console/server.py:2141`.
- Transcript lookup validates session IDs; folder images resolve paths and enforce containment. See `console/transcript.py:189` and `console/attach.py:106`.
- The inspected chat renderer escapes message text and table cells. See `web/app.js:8`, `web/app.js:1313` and `web/app.js:1319`. This is not a complete browser security audit.
- PLAN.md is stale about plan 36: `PLAN.md:50` calls it unimplemented, while `console/server.py:1189` and `console/server.py:1208` implement its API flow.
- OpenCode loader support is no longer wholly unverified: `PLAN.md:255` records a real-turn loader check. Broader plan 37 live acceptance remains open.
- Test facts for non-Claude runs are explicitly unavailable in `console/server.py:1735`. Step 3 must preserve its own test output instead of relying on automatic fact extraction.

## Out of scope

- No fixes, refactors, dependency changes or test additions.
- No changes to the existing dirty working tree.
- No edits to PLAN.md, plan 34, task files or hook configuration.
- No installation of hooks or execution of real model jobs.
- No destructive process-termination experiments.
- No implementation of the focused checks proposed in the findings.
- No claim of complete live CLI, browser, Windows process-tree or POSIX verification.
- No exhaustive review of every renderer, tray/window integration, usage calculation or adapter protocol variant; those remain coverage limits beyond the traced paths.

## Files

None. No file creation or modification is authorised by this plan.

The service’s automatic saving of this response as the task’s `plan.md` is outside this step’s file operations.

## Steps

There are no write steps and therefore no `### Step N` write sections.

The already scheduled step 3 remains a test-only step. Its instructions are in Goal and Acceptance. It must not implement any recommendation or add the focused tests described above.

## Acceptance

- Run `py -m unittest discover -s tests` once from `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE`.
- Capture stdout and stderr through process completion and report the exit code.
- Report the exact number of tests run and all reported failures, errors, skips, expected failures and unexpected successes.
- Copy each failing or erroring test name verbatim from the runner output.
- Report an inability to launch or complete the suite as a test-execution limitation; never substitute historical counts.
- Make no edits to make failures pass.
- Preserve this report’s distinction between code-confirmed findings and suspicions requiring targeted tests.
- Do not claim the full suite reproduces a finding unless its output demonstrates that specific failure.
- Compare `git status --short` before and after the test run; preserve existing changes and report any additional tracked changes without reverting them.
- The allowed source diff attributable to this audit is empty.
- Carry the ranked findings, plan 34 reconciliation and actual test result into the final task report.
