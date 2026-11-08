# Task 5: Prove the boundary, then amend the contract

Plan only. Nothing below ran in the planning session. Build execution first requires Fred's decisions in the
README. Future paths: focused tests/fixtures already named in Tasks 1-4; `CLAUDE.md`, plan 23 README's amendment,
this folder's status and this plan's own PLAN.md row/History line. Do not close plan 52 or change another plan's
status as a side effect. Fred's live check is separate evidence.

## 1. Focused checks to implement

Use existing temporary homes/fake providers. Locate actual fixture names before editing; repository inventory
must be rechecked because concurrent F1/F3 work touches tests/test_server.py. No network, installed settings or
real task mutation in unit tests. Keep legacy fixtures; file-mode fixtures write the path received in the prompt,
not a hard-coded canonical handoff.md.

| Test name to add to the appropriate existing suite | Required assertion |
|---|---|
| test_file_note_with_ack_reply | Good file + `Done.` passes; no marker parser needed |
| test_file_note_does_not_use_reply_fallback | Missing file + valid strict markers or six reply headings fails automatic and manual workers |
| test_retry_cannot_use_previous_file | Attempt 1 good file with failed run; attempt 2 clean reply but no file fails |
| test_continue_gets_new_output | STOP/DECISION turn with complete file; answer's turn writes nothing; old file cannot pass |
| test_legacy_inflight_and_continue | No metadata means old markers, including Continue after upgrade; a fresh Retry upgrades |
| test_late_output_cannot_complete_new_turn | Old process/session/generation completion cannot publish, even if its file appears late |
| test_reservation_save_failure_does_not_spawn | Directory/save failure leaves no process; missing meta never silently selects legacy |
| test_file_on_error_is_not_success | Parameterize interruption, stop, timeout, limit and failed subtype; good file does not override them |
| test_question_does_not_require_file_yet | STOP/DECISION first; file Plan gap recognized; generation changes only when answer launches |
| test_design_needs_plan_and_file | Good PLAN but missing file fails, including manual; good file but missing PLAN fails |
| test_file_verdict_findings | PASS/FAIL remains reply-sourced; verdict.md Findings comes from file, even when reply has no headings |
| test_publication_failure_holds | No successful transition, brief, supervisor success wake or next launch; prior canonical bytes survive |
| test_canonical_before_task_commit_restart | Simulated crash after publication; no model replay and at most one durable progression |
| test_add_next_uses_checked_file_with_ack | _next_source and _next_package use saved body with a short reply or cleared stream; preview revision changes when accepted body changes |
| test_new_source_never_uses_reply_fallback | New worker without accepted note cannot become a reply-built Add next source; legacy/chat still can |
| test_all_five_reader_paths | guidance gap, next package, chat tick legacy, end acceptance, verdict file each covered |
| test_get_does_not_touch_candidate | snapshot/task GET does not open/seal/publish candidate files or write metadata |
| test_file_live_state | writing while live even if file exists; no false unchecked/success; explicit error after rejection |
| test_old_flat_and_four_heading_notes | historical display and old_ok read paths stay usable; new four-heading file rejected |
| test_code_built_notes_unchanged | Mark step done and tool-free replan still publish service-built notes; no model file required |
| test_session_handoff_unchanged | skill, ordinary chats and auto handoff keep their parser and handed.md behavior |
| test_scoped_harness_output | per-adapter arguments, preserved package caches/PATH/cwd, source-read-only kinds, unsupported-route refusal |
| test_output_not_in_project_facts | file output does not inflate Files touched/git facts; test facts remain code-read |

Also run Task 1's bounded-read/link/atomic cases and Task 2's guard checks. Avoid tests that merely mirror argv
construction without testing the refusal, identity and persistence behavior. One small end-to-end fake chain
scout -> code -> verify proves the new file reaches the brief and next prompt while final replies lack markers.

For reference, this is the complete minimal good body to use in new fixtures; it deliberately contains neither
marker. Keep the existing marker GOOD fixture for old-protocol tests.

```python
FILE_GOOD = """## Goal
Check the requested task. This step finds the files.
## Findings
console/tasks.py owns note validation.
## Files touched
- (none)
## Troubleshooting
- (none)
## Open questions
- (none)
## Next
Read the named code and implement the reviewed plan.
"""
```

The regression for task f400 uses its failure **shape**, not private project text: a legacy reply with
`Next sentence. END HANDOFF` still fails the strict legacy parser; the same six sections written to a new file
pass with a plain reply. This proves the transport changed rather than hiding a tolerant-parser patch.

After focused suites pass once, run `py -m unittest discover -s tests` and `node --check web/app.js` once for the
coordinated release. Record actual totals and failures. Do not carry forward another plan's 1167/1180 count.

## 2. Real harness checks after build approval

Use a disposable **project configured by Fred** and a separate scratch CC_CONSOLE_HOME under Console data,
not task f400 or ARTCOUSTIC's dirty worktree. Use full executable paths and the existing process adapter.
Do not change user CLI settings, filesystem ownership or global permissions as part of these checks.

| Harness | Check | Record before release |
|---|---|---|
| Claude | Read-only scout writes exact output with project cwd elsewhere; attempt to Write another project file denied; missing/crashing/timed-out guard blocks; existing hooks and strict MCP preserved | CLI version, argv/settings shape, tool results, source tree diff |
| Codex | Effective read-only profile, output write succeeds, project write refused, Windows elevated sandbox/owner checks on output parent; Continue and retry use new grants; normal writer retains cache roots and PATH | CLI version, effective configuration, sandbox log excerpt on any failure, outcome for new and resumed turns |
| OpenCode | Read-only file route refused before spawn under D1d(a); writing route writes the external output, user deny still wins; harness remains off unless Fred enables it | V2 version, refusal, writer evidence when enabled; unsupported is not marked passed |
| Command Code | Read-only file route refused before spawn; writer gets only the new output parent as additional scope and succeeds; existing verify/fix exclusions stay | CLI version, refusal and writer evidence |

For Codex, a config-layer incompatibility or unenforceable Windows carveout is a failed capability check, not a
reason to use workspace-write for scout. Stop rollout and return to D1e. A successful `--help` lookup is not this
test. For OpenCode, a runnable local v2.0.32 is not proof that the running Console resolved it or that the V1 env
restriction works; preserve the F1 availability fix.

## 3. Window and migration check

On the fake chain, inspect the step Handoff tab at 900/400/340 px, dark and light: writing, accepted six sections,
brief cut lines and Checks, Facts, rejected file reason, retry, cleared stream, historical task and raw chat.
No candidate-file content appears while a process runs. A new file step's brief/Next remains visible without a
HANDOFF chip in its chat. Keyboard tab access and existing actions continue to use served gates. If plan 55/59
has changed the layout, check the current UI rather than reintroducing its old pane structure.

Upgrade scenario: start a legacy run before the upgrade, restart/reconcile, let its old contract finish; Continue
still accepts markers, new Retry asks for a file. New file run interrupted before writing cannot become done
on restart. Clear keeps the last-good canonical note/facts/brief and removes generated attempt directories.

Fred resets or manually merges the thirteen kinds listed in Task 4. Record outcomes here:

| Item | Actual evidence |
|---|---|
| Fred's D1a-D1e, D2-D7 answers | pending |
| Focused tests and full suite | not run |
| Claude/Codex real write and refusal checks | not run |
| OpenCode/Command Code writer checks or explicitly unsupported | not run |
| Window / migration / restart | not run |
| Kind resets or reviewed merges | pending |
| Fred's review of final behavior | pending |

## 4. Close only after the evidence exists

Amend plan 23 README with a dated link to plan 60: its six-heading **content** contract still governs step,
brief and skill; newly launched non-chat worker turns use a file while legacy/chat/skill producers retain their
old transport. Do not rewrite plan 23's historical implementation narrative as if it always used files.

Replace CLAUDE.md's Handoffs rule with this final wording after implementation:

```text
- Handoffs (step notes, briefs, the session-handoff skill) use tasks.HEADINGS, six headings; facts (git and the
  last test) are code-read and never compacted. Plan 23 README is the content contract. Plan 60 is the transport
  amendment: new non-chat worker turns write only their service-assigned attempt-<uuid>/handoff.md; the service
  validates and publishes the step's checked handoff.md. Old/in-flight reply handoffs, chats and the skill keep
  their legacy contract. A read-only worker may write its assigned output, not other Console files.
```

Adjust tasks.py's opening docstring (`A model never writes into the task folder`) to name this sole output
exception. Update harness API docs, not every historical mention of HANDOFF. Existing plan 24 PLAN saves and
session-handoff handed.md remain service-owned. Add this plan's own completion row/History line and measured
results, with explicit staging paths and only its hunks in shared files.

During **this planning session**, the allowed commit is just this folder plus one new PLAN.md row and one new
History line. No CLAUDE.md/plan-23 amendment is applied yet, no product/test/config file changes, no build and no
real agent turn. Stop and give Fred the plan link and commit.
