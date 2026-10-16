# Codex execution and task progression failures

Investigated 2026-10-16. Task: `20261016-082254-5dff`.
Status: findings confirmed; fixed in code by plans/38-codex-task-fixes.md (2026-10-16); a live Codex retry is pending.

## Incident

The task requested a read-only audit, with scout, test, and design steps.
Step 02 used `codex:gpt-6-luna`; step 03 used `codex:gpt-6-astra`.
Both reported that `C:\Users\DEROK137\.codex\.sandbox-bin\codex-code-mode-host.exe`
could not start because the executable was missing. No test results or verified audit
were produced by those steps. Step 02 was nevertheless marked done; step 03 ended
with a STOP question and the task is waiting.

Saved evidence is under `~/.claude/console/tasks/20261016-082254-5dff/`, especially
`task.json`, `chain.jsonl`, and `02-test/{notes,handoff,facts}.md`.
Run metadata and the retained design stream are under `~/.claude/console/runs/`:

- Test session: `d7d5b55d-fcb4-435f-ab51-2ccbd990adbe`.
- Design session: `2c8ed57e-1dec-4a89-a017-f20f2a86118e`.

## Confirmed findings

### 1. High: automatic discovery chooses an incomplete Codex installation

`console/harness/codex.py:6,17` prefers `codex.exe`; the shared resolver is
`console/harness/__init__.py:73`. With the current configuration, calling
`codex.find_exe(cfg)` resolves to `C:\Users\DEROK137\.codex\.sandbox-bin\codex.exe`.
That directory contains only `codex.exe`, reporting `0.155.0-alpha.16.3`.
The retained design stream explicitly reports the missing sibling command host.

The npm installation reports `0.162.1` and includes both native executables at:

```text
C:\Users\DEROK137\AppData\Roaming\npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\
```

Immediate recovery candidate: set the console's `harnesses.codex.exe` to that
installation's native `codex.exe`. A durable discovery fix should avoid selecting
an incomplete internal copy and preserve explicit executable overrides. Do not
hard-code this user's path or disable sandboxing. Merely swapping to the npm CMD
shim needs care: plan 27's harness work already discusses Windows argument quoting.

### 2. High: a blocked test step is accepted as completed

`console/harness/codex.py:66` treats `turn.completed` as transport success.
`console/server.py:1599` and `console/tasks.py:622` then accept a valid handoff
without verifying that the test step completed its work. `tasks.reply_question`
at line 300 recognizes STOP or a question in the final paragraph, not the question
inside this handoff's Open questions section.

Luna reported no tests and asked for the host to be restored, but omitted STOP.
The chain records step 02 as done and immediately starts step 03. A reproduction
using the completion function returned `next`; question detection returned empty.

Fix the distinction between a completed model turn and completed task work.
Use explicit, checked completion/blocking semantics rather than matching arbitrary
English phrases or treating every open question or recoverable tool error as fatal.
Account for the existing limitation that Codex test output is not read by the
Claude-only parser in `console/facts.py`; missing parsed facts alone cannot prove
that a command never ran. Keep legacy handoffs and other harnesses compatible.

### 3. Medium: nested Codex error messages are discarded in chat

`console/harness/codex.py:81,98` renders an `item.completed` event whose item is
`{"type":"error","message":"..."}` as a tool row containing only `error`.
Reproduced with the missing-host event shape. Preserve the diagnostic message
with the existing masking and length limits. A recoverable tool error must not
automatically become a failed task if later work succeeds.

### 4. Medium: the audit step conflicts with the design contract

Prep chose `design` to produce read-only audit findings. However,
`dotclaude/console/kinds/design.md:17` requires an implementation PLAN, and
`console/server.py:1613` rejects a successful design reply without one.
The prep description at `dotclaude/console/kinds/prep.md:47` also calls design
appropriate for deep research, which is broader than that implementation contract.

This is a confirmed contract mismatch and a potential next blocker, not the
observed reason step 03 stopped: its STOP question was handled first.
Prefer routing findings-only work to a suitable existing kind, with sufficient
reasoning effort, while retaining PLAN validation for actual implementation design.

## Verification and limits

Ran directly from the project root during this investigation:

```text
py -m unittest discover -s tests
Ran 741 tests in 359.132s
OK
```

741 passed, zero failures, zero errors. These are investigation-time results,
not results from the failed task's test step. The existing suite passing does not
cover the four reproduced or source-confirmed issues above.

No source code, configuration, or task records were changed during investigation.
No live Codex turn was retried, and the original broad audit remains unfinished.
Line numbers describe the investigated checkout and should be rechecked before edits.
Check planned overlap with plans 05, 17, 23, 24, 27, 34, and 36 before implementation;
this note is an incident record, not a replacement implementation plan.
