# Plan 60: A step writes handoff.md

Status: **plan only, 2026-11-08; not approved and not built**. D1a-D1e and D2-D7 below are for Fred.
The task files contain the proposed final code and anchored integration edits for the recommended answers.
They are not authorization to build. Read this table with Fred first; record his answers before implementation.

Why: Fred chose a file over a tolerant reply parser on 2026-11-08. In plan 52's live check, task
`20261108-203300-f400`, `01-scout/notes.1.md`, Codex wrote the six headings but ended its last sentence with
`END HANDOFF`. `tasks.parse_handoff` requires a separate marker line and rejected the note. The evidence file
was read, including that last line. [Decision record](../decisions-2026-11-08.md), F2.

Contract amended: [plan 23](../23-handoff/README.md), sections 3.2 and 3.5, **step-note transport only**.
`tasks.HEADINGS`, the six sections, the brief continuity checks, whole Goal and Troubleshooting, and code-read
git/test facts remain the contract. Facts are never compacted. PLAN / END PLAN and SUBPLAN remain in replies.
The session-handoff skill, raw chats, Prep, planner, supervisor and tool-free replan are separate protocols.

Read against `d63b58d` plus the working tree on 2026-11-08. Another chat is fixing F1/F3 in tasks/server/tests;
rebase the anchors below on its committed result. Do not copy old routing or supervisor code over that fix.
Plan 52's real-provider check remains open; plan 54 is built and Fred says the service was restarted on it.
Neither status is changed here. Plan 57 is reserved on its branch. `plans/` and PLAN.md were checked again
immediately before creating this folder: 60 was free.

## 1. Tasks, in order

| # | File | Delivers after review | Depends on |
|---|---|---|---|
| 1 | [01-file-contract.md](01-file-contract.md) | Fresh output locations, bounded file reader, legacy selector, atomic publication | decisions |
| 2 | [02-harness-writes.md](02-harness-writes.md) | Per-run output grants, Claude file guard, Codex sandbox, explicit unavailable routes | 1 |
| 3 | [03-service-readers.md](03-service-readers.md) | Launch/resume reservation, all five readers, checked-note persistence, restart and UI state | 1-2 |
| 4 | [04-prompts.md](04-prompts.md) | Shared prompt and thirteen worker kind files; Fred's Reset to repo copy list | 1-3 |
| 5 | [05-check-and-close.md](05-check-and-close.md) | Focused regression matrix, real harness checks, Handoff tab, contract amendment and close | 1-4 |

The new protocol must ship as one coordinated release; intermediate commits are not rollout points.
No tests, product files or configuration were written or run for this planning session. Future checks below
are instructions for the build session, not claimed results.

## 2. Decisions for Fred

Only the choice of **file instead of tolerant markers** is already decided. Every row below remains open.
The code in the task files describes option (a); choosing another option requires revising that code first.

| ID | Decision | Recommended (a), with its cost | Alternatives | Fred |
|---|---|---|---|---|
| D1a | Where does the model write? | `<home>/tasks/<id>/<fixed-step-dir>/attempt-<uuid>/handoff.md`; `<home>` is `CC_CONSOLE_HOME` or `~/.claude/console`. Keep project cwd. The service owns the existing `<step>/handoff.md` and publishes into it after validation. This introduces one small directory per output generation. | (b) model writes the canonical step file, cleared before each run; fewer files, but mixes unchecked and checked data and has a late-writer race. (c) project-local file; easier access, but pollutes worktrees and breaks CLAUDE.md's data-location rule. | open |
| D1b | What does read-only mean here? | Source files remain unedited; writing the assigned output is an explicit exception. Classify scout/search/explain/design/test/verify by kind, not equality with a tool string. Preserve the test/verify shell tools. Claude/OpenCode tool permissions are not an OS sandbox; tests can have side effects already. Codex keeps OS sandbox enforcement. | (b) make every harness OS-read-only except the artifact; a separate sandbox project, not a small handoff change. (c) trust prompt wording and turn all runs into writers; smaller, but removes the protection on scout. | open |
| D1c | How do Claude and Codex get the exception? | Claude: add Write plus a run-local, fail-closed file-tool hook on read-only kinds; allow the exact output path. Codex: a read-only permission profile plus the output directory for read-only kinds; writing kinds retain workspace-write with that directory added to existing roots. Preserve cwd, package roots and Windows setup. More adapter code and real CLI checks. | (b) broader additional workspace write access for all steps; easier but makes source edits possible. (c) another model pass writes each note; extra tokens, latency and failure handling on every step. | open |
| D1d | OpenCode and Command Code read-only steps? | Refuse these **new file-protocol read-only routes** until a supported, per-run narrow exception is proven. Command Code plan mode expressly forbids arbitrary writes. Current OpenCode V2 docs no longer document the adapter's V1 permission environment. Normal writing steps can use the file; existing verify/fix exclusions remain. This reduces the routing pool and must be visible, including for pinned picks. | (b) approve building a Command Code mod / OpenCode V2 configuration integration first, then refresh this plan with its final code. (c) relax source-write restrictions; not recommended. (d) keep reply transport for these harnesses, which is a deliberate exception to the new contract. | open |
| D1e | Unsupported installed versions or conflicting settings? | Refuse before launch with a named reason. Confirm the installed Claude hook fields and Codex profile with Task 5's real checks. Do not edit another CLI's user/project settings, change ownership, disable sandboxing, ignore user configuration or silently route an explicit pick elsewhere. | (b) Fred upgrades/migrates the CLI first; (c) broaden permissions. Capability refusal is preferable to spending a step that cannot write its required output. | open |
| D2 | Stale output on retry or Continue? | Fresh UUID directory for **every launched turn**, not only every counted chain attempt. Save its identity before launching. A retry and a STOP/DECISION answer both receive a new path. Never glob for the newest file or read the previous generation. | (b) delete one fixed filename before launch and require deletion success; still needs protection from a late old process. | open |
| D3 | Forgotten write or invalid file? | Fail new non-chat worker steps, automatic **and manual**, with the file-specific reason. No reply fallback, even when a valid old block or six bare headings appear in the reply. Questions still wait before requiring a completed note. Existing retry limits and Fred's explicit Mark step done remain. | (b) fall back to strict old markers; (c) fall back to six reply headings after a clean end. Both keep a second transport and can hide a broken write grant. | open |
| D4 | Migration and running display? | Version per launched turn: absence of `handoff_output` means legacy reply parsing. In-flight legacy turns and their Continue turns remain legacy; a fresh Retry/new step uses the file. Do not rewrite old notes. File steps show `writing` until the run ends, then checked/ready/sent only after publication. Handoff tab shows accepted data or an explicit error, no live file preview. | (b) live-preview partial files with stat-based invalidation and masking; extra reads, races and UI states. (c) stop every in-flight task at upgrade. | open |
| D5 | What must prompts and local kinds say? | Shared prompt supplies one absolute output path, six headings and no marker wrapper. Every worker kind states the output exception. Notes, VERDICT, PLAN and DECISION stay in the reply. Fred uses Models > Kinds > Reset to repo copy for the thirteen changed kinds after reviewing any custom text. No automatic overwrite of his local kinds. | (b) change shared prompt only and risk contradictory old kind instructions; (c) auto-overwrite custom kinds, losing Fred's edits. | open |
| D6 | Invalid/large files and raw data? | UTF-8 (BOM accepted), six-heading check unchanged, reject over NOTE_MAX (20 KiB) rather than truncate a valid section away. Mask before canonical publication. Do not expose raw output through GET/Open while running; scrub it after the process ends. Reject links, junction escapes, non-regular and multiply linked files. I/O errors refuse advancement. | (b) retain raw files indefinitely; easier diagnosis, more unmasked data. (c) use existing truncation, which can remove Next after validating it. | open |
| D7 | How far does the contract change reach? | Non-chat worker sessions only. Ordinary chat steps, standalone session-handoff, auto handoff, Prep/brief/planner/supervisor and code-built replan/Mark step done notes keep their current producer. Retain parse_handoff for them and history. | (b) convert all these producers too; substantially larger migration, including tool-free passes that cannot write. | open |

D1d is a real tradeoff, not a claim that all four harnesses support equivalent permissions. If Fred wants all
four read-only routes immediately, choose D1d(b) and extend Task 2 before building. Do not smuggle that policy
choice into an adapter during implementation. A scoped native writer would be preferable once verified.

## 3. Cost beside the cheaper option Fred passed over

| Choice | Scope and likely effort, estimate only | Ongoing cost / failure modes |
|---|---|---|
| Tolerant markers (Fred passed over) | Roughly half a day including focused checks: accept a terminal END HANDOFF token at a line end; if END is absent, take the remainder after HANDOFF **only on a clean final run**. Preserve six-heading checks and reject incomplete/error turns. Parsing, its callers' clean-end input and parser/UI checks. | No new writes or permissions. Still depends on reply formatting and can accidentally include trailing commentary/DECISION text; missing start marker still fails. |
| File transport, recommended contract | Roughly 2-4 engineering days plus Fred's live checks, assuming Claude/Codex grant recipes work; more if D1d(b) is selected. Storage, reservation on all launch paths, two adapter grants and two explicit capability refusals, five readers, prompts, fixtures, migration and UI checks. | No extra model pass. Usually at least one extra file-write tool call per turn, plus its tool result tokens and latency. No measured dollar estimate. Missing writes, disk/ACL errors, stale turns and CLI version differences replace delimiter failure. UUID directories add retention work. |

A file removes the END-marker problem, not the six-heading requirement or the possibility that a model forgets
its instructions. This proposal is intentionally more work than loosening the parser. It does not fix F1/F3,
make plan 52's live check pass by declaration, or implement plans 55, 56, 57, 58 or 59.

## 4. Contract

### 4.1 Storage and authority

```text
<home>/tasks/<id>/01-scout/
  attempt-<32 lowercase hex>/handoff.md  model output for one launched turn
  handoff.md                           service-published, masked, checked note
  notes.md / notes.<k>.md               existing final reply / failed-attempt chat
  brief.md / facts.md / verdict.md      existing derived artifacts
```

The service creates an empty output **directory**, not a prefilled handoff. The path comes only from the service;
neither a model reply nor an HTTP field chooses it. The model cannot satisfy the next generation by writing
into this generation. `step.dir` stays fixed across replan renumbering. Retries retain the failed generation for
diagnosis after masking; Clear removes only these generated directories under the selected task, and keeps the
last-good canonical handoff/brief/facts as before. No generated directory is a new project workspace.

New metadata is optional, not added to `STEP_KEYS`:

```json
{"handoff_output": "01-scout/attempt-0123456789abcdef0123456789abcdef/handoff.md",
 "handoff_error": "", "handoff_source": "file"}
```

The current step and run metadata carry the output path; each attempt records its latest output path. A resumed
turn replaces that latest path but leaves earlier output directories on disk. A failed-launch reservation remains
diagnostic, never a completed attempt. `handoff_source` is published only with a checked canonical note.

### 4.2 Acceptance and persistence order

1. Resolve the current turn and the current step's matching reservation. A late result for an earlier session,
   turn or generation cannot publish or advance. Preserve the existing guidance dispatch/uncertainty gates.
2. STOP/DECISION still comes from the reply and waits first. The question may be asked before a handoff exists.
   A `Plan gap:` in a valid file also waits; that turn is not marked done.
3. Require a clean run; a valid file never makes an interrupted, stopped, timed-out, limited or failed run pass.
4. Read only the assigned file, bounded; validate `tasks.check_handoff`, then mask and validate the masked body.
   Retain the existing six headings and Goal/Findings non-empty checks. Do not add a new content parser.
5. Prepare the existing PLAN/VERDICT checks. Publish the canonical note atomically using
   `paths.write_text_atomic` **before committing a successful transition**; publication failure leaves the step
   stuck with a save error, no brief, no next step and no success hook. Do not run a model again to fix disk storage.
6. Commit the existing transition and facts/brief work. The canonical note is the reader contract after success,
   including after streams are cleared. No live GET writes files or changes states.

Plan 54 does not currently route `tasks.write_note` through the atomic helper; Task 1 adds that specific save.
It must not widen into a rewrite of every historical writer. Keep the current locks; do not add retry loops or
in-place save fallbacks.

### 4.3 All readers, including the apparent exceptions

Line numbers are reading-session locators only; edit by function/statement anchors after F1/F3 lands.

| Existing server.py location | Proposed source and rule |
|---|---|
| ~1517, task guidance path, `plan.gap(parse_handoff(reply))` | Read the matching ended-turn file through the shared selector before deciding whether guidance answers a Plan gap. Legacy uses reply. |
| ~2728, `_next_package` | Done source prefers the accepted canonical note even if a short final reply exists. Only legacy/chat may build a fallback from the reply. Include accepted file body in preview revision; current facts remain separate. |
| ~3231, `_chat_tick` | Explicitly legacy under D7; keep parser, never require an output file for ordinary chat turns. |
| ~3586, `_ended` | Current file or legacy selector; new file missing is an error also in manual progression. PLAN, VERDICT, STOP and DECISION still read reply. |
| ~3686, `_step_files` | Receive the already selected block as an argument for verdict Findings. Do not parse/read it again. |
| ~1629, `_next_source` synthetic HANDOFF reply | Stop manufacturing a reply wrapper. Check real reply for questions; check saved note independently as evidence that a source exists. |
| ~2727, `_next_package` synthetic HANDOFF reply | Remove wrapping of saved note in markers. Read and validate the saved body directly. Preserve the real reply as source-reply.md. |
| `_live_note`, `tasks.live_note`, `tasks.note_state`, `Handler._step_texts` | Legacy stream cache unchanged; file turns always writing while active. Serve canonical notes only after acceptance, with source/error metadata for the current generation. |
| `compact.py`, `brief.py`, session-handoff skill | Keep existing marker/old-heading compatibility. They read the checked note or a legacy session reply, not live candidate paths. |

After a restart an old in-flight turn has no new metadata and finishes as legacy. A new file turn keeps its
persisted reservation; restart does not allocate a second path, accept a partial file, or rerun a turn whose
launch outcome is uncertain. A new fresh Retry gets the new protocol. Saved four-heading historical notes
remain readable with `old_ok=True` only on historical read paths; new file acceptance uses all six.

### 4.4 Scope map

Future product paths: `console/tasks.py`, `console/runs.py`, `console/server.py`, `console/harness/claude.py`,
`console/harness/codex.py`, `console/harness/opencode.py`, `console/harness/cmd.py`, new
`console/handoff_guard.py`, `console/step_prompt.md`, the thirteen worker kind files in Task 4, and
`web/app.js`'s Handoff pane. `console/harness/__init__.py` documents the new optional adapter argument.
No new dependency, HTTP write route, model pass, settings field or configurable fallback.

Future checks/fixtures: `tests/test_tasks.py`, `tests/test_harness.py`, `tests/test_runs.py`, `tests/test_server.py`,
`tests/test_dotclaude.py`, `tests/test_web.py`, `tests/fake_claude.py`, `tests/fake_codex.py`,
`tests/fake_opencode.py`, `tests/fake_cmd.py`, and a focused guard test. Recheck these names before the build.
Keep legacy cases; introduce file-mode fixtures explicitly.
No changing every GOOD marker fixture into a file fixture and thereby losing migration coverage.

## 5. Evidence on permissions, checked 2026-11-08

These are documentation findings, not successful write probes. Only local help/version and selected config
keys were read; no agent turn, sandbox probe, build, test or setting mutation was performed.

| Harness | Existing adapter / cwd | Verified documentation and consequence |
|---|---|---|
| Claude Code | Project process cwd; `auto`, prompts none, tools by kind, strict MCP. `read_only` argument unused. | [Permissions](https://code.claude.com/docs/en/permissions) uses `Edit(path)` for Write too; additional directories alone do not narrowly allow one file. [CLI](https://code.claude.com/docs/en/cli-reference) supports run-local settings/tools. [Hooks](https://code.claude.com/docs/en/hooks) supports PreToolUse deny and fail-closed `onFailure: block` from 2.1.295. Task 2 uses a guard rather than assuming `Write(path)` works. |
| Codex | `exec --json -C <project>`, `-s read-only` or `workspace-write`; writer roots include npm/Cargo/Rust caches and network access. Installed help: 0.166.0. | [Permission profiles](https://learn.chatgpt.com/docs/permissions) supports extending `:read-only` with a specific writable path. Legacy `-s` / sandbox settings override profiles: omit `-s` for the new read-only file path and refuse conflicting effective config. [Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox) is a separate platform constraint, not solved by an output pathname. Local top-level config has neither sandbox_mode nor sandbox_workspace_write; windows.sandbox is elevated. |
| OpenCode | `run --standalone --format json --auto --file <prompt>`, project cwd; read-only env currently sets V1 `OPENCODE_PERMISSION` with edit/bash/webfetch deny. Local help: v2.0.32. | [V2 permissions](https://opencode.ai/docs/permissions/) uses ordered `permissions`, `edit`/`shell`, plus external_directory; tool permissions are not an OS sandbox. [Config](https://opencode.ai/docs/config/) does not establish a run-local replacement for the old env setting. Do not assert it works from old examples. D1d(a) refuses new read-only file runs; writers retain existing authority. Fred currently has this harness off. |
| Command Code | Node entry point, project cwd; `plan` when read_only, otherwise accept-edits; no-skills; no OS sandbox implemented here. | [Permissions](https://commandcode.ai/docs/permissions) applies plan's mutation gate before allow rules; its sole writable plan location is outside Console's permitted data root. [CLI](https://commandcode.ai/docs/reference/cli) supports `--add-dir` for writer runs. Do not redirect Console notes into `~/.commandcode/plans`, invent an allowedTools override, or silently switch scout to accept-edits. |

Memory read: `~/.claude/projects/D--MY-DOCS-MY-TOOLS-CLAUDE-CONSOLE/memory/codex-windows-sandbox-writes.md`.
The 2026-10-17 fix needed both the real account owner (machine and account share a name; use the fully qualified
account) and elevated Windows sandbox for Python temporary directories. Check the **new output directory** with
the existing `codex.write_block` as well as the project where applicable. A writable root does not cure an ACL
failure. Diagnostics may point Fred to `.codex/.sandbox/sandbox.<date>.log`; code never changes ACLs/settings.
Use the real Python executable for a later sandbox check, not the `py` launcher.

## 6. Review / release gate

Not ready to build until Fred answers the table, particularly D1d's routing loss, D3's manual-step failure rule,
and D4's migration. Before release, the approved grant must succeed with project cwd outside the output root,
source-edit denial must remain effective to the promised level, and every supported resume path must retain
the policy. Version/help evidence alone is not proof. If a recipe fails the real check, stop and revise D1;
do not ship a broad-permissions workaround. Task 5 records this evidence and Fred's kind-file resets.
