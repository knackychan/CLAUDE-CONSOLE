# Plan 44: supervisor backend. Guided implementation plan

> Design: [BRAINSTORM.md](BRAINSTORM.md), decisions D1-D13, taken 2026-10-17.
> Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
> Shipped companion: [navigation/README.md](navigation/README.md).

Status: **plan written, backend not implemented**, 2026-10-18. Inspected baseline: `654c1bd`, clean tree.
This is a plan-only change. Execute a task only in a subsequent implementation run. The task files specify
files, signatures, data, tests, acceptance checks and commit boundaries; implementation is written test first.
There is no SPEC.md, AGENTS.md or docs/superpowers tree at this baseline. Use this repository's plans layout.

## 1. Goal and scope

After an eligible task transition, build a small digest from saved evidence and run one bounded Claude pass.
Validate its JSON as untrusted data, then suggest or dispatch through the existing Hub operations. Keep every
decision recoverable and visible through backend read APIs. Default to suggest; automatic work needs Fred's
explicit per-task, per-project or global auto setting and all existing gates.

This plan covers the supervisor backend across brainstorm slices A-C: configuration, persisted policy and
audit, digest, runner, wakes, approvals, automatic dispatch and caps, supervised intake, stalled/done wakes,
Usage data and replay. Tasks 1-7 form the suggest-only checkpoint; Task 8 enables automatic dispatch.

**Parked, not prerequisites:** brainstorm section 14's skill library (D14-D18), tags, skill selection/inlining,
Skills tab, and optional add-dir loading; all Board/composer/Prep-card/Models-page/Usage-page rendering.
This backend rejects a `skills` decision field until that separately planned registry exists. It does not
silently ignore the field or invent a registry. Backend intake and approval routes are included so the later
UI has a complete contract. Navigation Tasks 1-5 are shipped; do not re-execute their historical reset advice.

## 2. Tasks, in order

### Review annotations, 2026-10-18: binding implementation guidance

These corrections are part of the design, not optional follow-up work. They do not mark any backend work
implemented. Follow the task files and prove the named cases before closing their commit boundaries.

| Review | Failure to prevent | Owning tasks | Required proof |
|---|---|---|---|
| R1 | Restart during debounce loses stuck, plan-hold or automatic-done advice | 2, 5, 9, 12 | Recover each eligible unclaimed boundary once, using its original event id; consumed events never rerun |
| R2 | Manual owner Fred is mistaken for explicit Pause | 7, 12 | Shared gates and mutation accept Pause/Resume at a supervised manual boundary; no chain launch or stale dispatch |
| R3 | Replay hides a kind-only prompt change behind an unchanged task revision | 3, 4, 5, 11, 12 | Separate exact-prompt fingerprint changes while evidence revision stays equal |

R1 extends recovery to the full wake matrix; it does not replay interrupted claims or dispatches. R2 is a
targeted correction to the shared human Pause/Resume gates, not permission for supervisor dispatch to bypass
gates. R3 adds comparison metadata, not a new approval gate, model call or historical prompt archive.

| # | File | Deliverable | Depends on | Commit boundary |
|---|---|---|---|---|
| 1 | [01-policy-config.md](01-policy-config.md) | Defaults, validated tuning, task policy and legacy compatibility | none | policy and config tests green |
| 2 | [02-audit-recovery.md](02-audit-recovery.md) | Audit, spend reservations, wake identity, recovery and deduplication | 1 | journal/recovery tests green |
| 3 | [03-digest-decisions.md](03-digest-decisions.md) | Bounded digest and strict decision validator | 1, 2 | pure contract tests green |
| 4 | [04-bounded-pass.md](04-bounded-pass.md) | Tool-free runner, kind seed and failure/cost handling | 3 | fake CLI tests green |
| 5 | [05-wakes.md](05-wakes.md) | Event hooks, debounce, coalescing and bounded workers | 2-4 | deterministic wake tests green |
| 6 | [06-dispatch.md](06-dispatch.md) | Existing Hub dispatch, durable intent and held/stale handling | 3, 5 | gate and dispatch tests green |
| 7 | [07-approval-api.md](07-approval-api.md) | Mode/Approve/Reject API, read projections and human-action bookkeeping | 6 | suggest-only checkpoint green |
| 8 | [08-autonomy.md](08-autonomy.md) | Auto mode, retry/FAIL-loop and money/step limits | 7 | autonomy and cap tests green |
| 9 | [09-holds-stalls-done.md](09-holds-stalls-done.md) | Remaining manual wakes, plan holds, report-only stalls and done checks | 8 | transition matrix green |
| 10 | [10-supervised-intake.md](10-supervised-intake.md) | Manual first-step intake with remaining Prep intent preserved | 9 | intake compatibility tests green |
| 11 | [11-usage-replay.md](11-usage-replay.md) | Auditable spend projection and bounded replay CLI | 2, 4, 8-10 | Usage/replay tests green |
| 12 | [12-acceptance-close.md](12-acceptance-close.md) | Adversarial integration checks, indexes and handoff | 1-11 | full regression and docs commit |

Each task is one implementation commit with its tests. Each starts by writing the listed behavioral tests and
running them red for the intended missing behavior, then makes the smallest change that turns them green.
Run the focused tests named in each file, then `py -m unittest discover -s tests` at its commit boundary.
Do not record a historical test count as a new result. No paid model call is needed for automated acceptance.

## 3. Current code and reuse map

| Existing code | Use here; current behavior that must survive |
|---|---|
| `console/server.py:Hub.task_levers`, `_guidance_levers`, `_base`, `rung_ok` | Supervisor dispatch obeys shared gates; Task 7 corrects only Fred's manual-boundary Pause/Resume gates (R2) |
| `Hub._next_source`, `next_sources`, `preview_next`, `request_next` | Validate source and preview revision; request_next persists reservation before launch and deduplicates request id |
| `Hub.task_lever`, `tasks.fred` | Stop/Retry/Confirm/Keep/stepdone/done behavior; Retry note, tier route, limits and avoid list stay intact |
| `Hub._ended`, `_replan_done`, `start_step`, `_broken`, `_commit` | Real transition and completion hooks; cost/brief/floor lines are not wakes |
| `Hub.advance`, `tick`, `run` | Existing scheduling loop only; advance drains due wakes, tick observes stalls; no additional polling service |
| `Hub.start_brief`, `_brief_job`, `_brief_done`, `_replan_job` | Deep-copy under tlock, release it for one bounded subprocess, reacquire and refetch live task to apply result |
| `console/compact.py:_ask`, `console/claude_cli.py:brief_command` | Reuse one tool-free structured CLI invocation with timeout; retain the other pass callers' defaults |
| `console/replan.py:check`, `run_replan` | Pure validation and error result pattern; no model repair/retry loop for bad supervisor output |
| `console/tasks.py` readers, `step_cost`, `attempts`, `room_after`, `pending_messages` | Read existing/legacy notes and facts; compute all-attempt costs; pending includes failed/uncertain guidance |
| `console/kinds.py:NAMES`, `ensure`, `text`, `check` | Add non-worker supervisor kind, preserve Fred's edits and person slots |
| `console/paths.py:DEFAULTS`, `set_config`, `write_text_atomic`; `console/tuning.py` | Existing whitelist, atomic writes, unknown config keys preserved |
| `Hub.usage_report`, `console/usage.py:day_of`, `console/__main__.py:main` | Usage projection and early replay branch, using the repository's day convention |
| `tests/fake_claude.py`, `tests/test_server.py:TaskServerTest` | Fake structured pass, explicit advance, temporary project/data roots and real HTTP guards |

There is **no `Hub.model_id`**. Existing brief/replan passes give Claude aliases directly to brief_command.
Resolve supervisor haiku/sonnet the same way; do not add a model resolver. `tasks.room_after` uses the existing
numbering convention (and excludes certain inserted verify/fix work); combine it with an explicit physical
`len(task['steps']) < task_max_steps` check for supervisor appends. Fred's manual Add step remains uncapped.

Manual tasks file notes/facts in `_ended` and do not start a brief. Automatic tasks must finish `_brief_done`
before a pass reads their boundary. Manual design saves its plan without rebuilding a tail of planned steps.
Keep that distinction: a supervisor adds one fresh step, never calls `plan.rebuild` on a manual task.

## 4. Hard contract

### 4.1 Pass and ownership

- One wake launches at most one `_ask` subprocess, with brief_command's no-tools, no-MCP, hooks-off,
  no-skills/commands, no-session-persistence, JSON-schema and six-turn bounds. A structured response can need
  several CLI turns; there is no Python retry, repair pass, watcher session or resident agent.
- Task 4 adds supervisor-only safe-mode/explicit MCP denial to that reused command, preventing automatic
  project/personal instructions or memory from expanding the digest-only input. Other passes keep defaults.
- Use the configured project cwd only after `_base` passes. No supervisor session row, RunManager worker,
  transcript, hook event, Agent/MCP tool, source-code edit, plan rewrite or network client is introduced.
- Worker steps started by an approved decision still use existing RunManager/harness adapters and limits.
  Supervisor code must never call `runs.start` or `runs.stop` directly to dispatch a decision.
- `Hub.tlock` protects wake maps, policy accounting, validation and mutation. Never hold `Hub.lock` while
  acquiring tlock. Copy cfg/task/input under tlock; the model subprocess runs outside both locks. Completion
  refetches `self.tasks[id]`: request_next replaces the task dict and old references are unsafe.
- A failure records a terminal no-decision outcome for this wake. No fallback action and no automatic retry
  of the same event. Only a genuinely new transition/dirty event can cause another bounded pass.

### 4.2 Modes and authority

`off`: no pass or automatic dispatch. `suggest`: save a pending decision, never start work automatically.
`auto`: only add_next_step, confirm, keep, retry and finish can dispatch automatically after Task 8.
`stepdone` and a stalled `stop` require Fred's explicit approval in every mode. `answer` is recorded as refused
and becomes escalate_to_fred; it is never dispatched, including from Approve. `wait` records no pending work;
`escalate_to_fred` records attention text, with Reject/dismiss but no executable Approve.

Fable confirmation, pace release, questions/Plan gaps, attachments, Pause/Resume, Clear/Delete, project Allow,
Redo design and plan edits are always Fred's. Confirm is limited to the exact plan-ready/oversize/replanned
holds in the brainstorm, checked again immediately before the call. Approve cannot convert a forbidden action
into a permitted one or ignore a live gate. Old automatic chains continue their scripted behavior unchanged.

Each new task snapshots `task.supervisor.mode` from task override, normalized project override, then global
default. A mode POST changes that task only. Reloaded project/global settings apply to future tasks, not to a
saved task's explicit mode. Legacy tasks get effective defaults lazily without changing TASK_KEYS/whole().
An invalid legacy policy/config fails closed to off with a visible reason, never to auto.

### 4.3 Persistent state and events

Keep the brainstorm's fields under `task['supervisor']`:

```text
mode: off|suggest|auto; wakes: int; auto_steps: int; retries: {step-number: int}; usd: number
work_usd: number; since_fred: timestamp
epoch: int; paused: bool; last_event: event-id or ''; proposed: [Prep step dicts]
pending: null or {wake, events, triggers, decision, revision, epoch, status, error, by, dispatch}
```

`epoch` increases on a successful, new Fred action; repeated request ids and refused actions do not reset it.
Reset auto_steps, retries and the current work-cost baseline then; never reset wakes or lifetime usd. Record
per-attempt attribution `{wake, epoch, cost_at_start}` only for supervisor-caused work in the existing step/
attempt data, so retries and late cost updates can be charged without counting another epoch's work twice.
`work_usd` is a projection of those attempts, including live costs, not a new independent money ledger.

The explicit paused bit distinguishes a manual `owner: fred` boundary from Fred's Pause. For older tasks,
infer only an unmatched existing `paused by Fred` chain action; ambiguous Fred-owned running tasks are held.
R2: Task 7 updates both task_levers and tasks.fred for supervised manual choose-next/FAIL boundaries.
Pause sets the explicit bit there; Resume clears it while leaving owner fred and the boundary unchanged.
Neither action starts chain work or creates a wake. Other task gates retain their existing behavior.
Stop by Fred cancels supervisor eligibility; only approval of a supervisor stalled-stop creates its specific
follow-up retry suggestion. Mode off cancels queued wakes and pending executable intent; in-flight paid results
are still audited/accounted but never dispatched.

An event id hashes canonical JSON of the **qualifying original chain transition** (including timestamp,
step, session, from/to and reason). The stall event additionally names session/attempt. Never use task.updated,
cost, a chain-tail position, the latest supervisor line or tick time as an event identity. Coalesced wakes carry
all event ids; claiming a wake durably consumes them before starting its pass. Persisted claim/result records
suppress duplicates across restart. Same attempt plus a different real transition is a new event.

Append lifecycle records to `tasks/<id>/supervisor.jsonl`, masked, one logical wake folded from records by wake
and phase. Records contain the brainstorm section 11 fields plus phase, event ids, semantic revision and epoch.
The phases are claimed, result, dispatching, outcome and recovered. Claim records also save the gate/source
context used for the prompt, so the audit explains what was allowed then. Multiple records are needed for durable
dispatch intent; cost is counted **once from the result phase**, never once per lifecycle row. No log rewriting.
Task JSON is an atomic projection; a crash after journal append but before task.save is repaired from records.
The existing usage-days.json gains durable supervisor reservation/result identities in Task 2; this remains
the spend authority after deletion or replay, while the task journal remains the decision authority.
Unreadable/corrupt accounting is a visible hold, not a free zero-cost allowance. An incomplete final JSON line
is ignored for display but makes unfinished dispatch uncertain; do not silently lose its budget reservation.

### 4.4 Wakes, held results and restart

`Hub.wakes[id] = {due, triggers, events, n}`; `due` uses a monotonic clock, logs use wall time. Each **new** event
re-arms due by debounce (20 seconds); duplicate events neither re-arm nor launch. One active pass per task,
global `supervisor_parallel` default 1. While active, merge new events into the same pending entry; completion
leaves at most one debounced dirty follow-up. Callbacks never launch the next pass recursively.

No new pass while paused, off, answering a question, chat-only, guidance pending, brief/replan still writing,
project refused or own-spend cap exhausted. A meaningful event blocked by briefing/guidance is retained, not
spent on or lost. Drain only after the existing brief/guidance path resolves it. Failed/uncertain messages still
block. Running-state bookkeeping, first automatic retry, chat turns, Prep/Review and external sessions do not wake.

If guidance arrives during a pass, record `held: pending guidance` and dispatch nothing. When it drains, compare
the saved semantic revision and human epoch: unchanged decisions can be revalidated, while changed guidance/
evidence supersedes them and queues one fresh wake with the retained triggers. Never replay pending guidance.
Any new eligible boundary supersedes a pending older suggestion; Approve of an old wake returns 409.
Refusals do not generate new wakes. Reject persists its optional note for the next real wake, not an immediate call.

On restart, wakes starts empty. Once on the first advance, scan all saved eligible current boundaries:
manual choose-next/FAIL, stuck (including failed replan), plan-ready/oversize/replanned holds, and automatic
done after its final brief. Use the live wake classifier and original persisted transition, never a synthetic
restart timestamp. Without a claim/terminal record for that event, enqueue one wake with a fresh debounce.
Retain brief/guidance-blocked candidates until their existing paths finish; enforce all live admission gates.
Task 5 covers its initial wake set; Task 9 extends both live and recovery classification together. Stall checks
remain in tick with their persisted attempt identity. Recreate durable held decisions without
re-running their model call. A claimed pass interrupted by restart becomes no-decision/uncertain cost, not an
automatic model retry. A lever left dispatching becomes uncertain and requires dismissal; it is never replayed.
For add_next_step, inspect existing request_id reservation via plan 36 recovery; never silently launch or append
another step. One saved decision can have at most one effect.

### 4.5 Validation, dispatch and counters

`supervisor.check(decision, task, levers, sources, policy) -> (bool, why)` validates both shape and action-specific
rules without files or mutation. Unknown fields, wrong JSON types (including bool step numbers), invalid enums,
oversize text, unsupported kinds or non-auto next-step models are rejected. Retry accepts only empty/haiku/
sonnet/opus tier words; the selected worker may still be subject to Fred's existing Fable gate. Resolve omitted
source to current step in code, require a done owned task step with a real service-owned session, and require
its two-digit `next_sources` entry and task_levers.add_next to be empty. External sessions are never sources.

`Hub._supervisor_dispatch` rechecks live mode, pause, task/evidence revision, epoch, questions, guidance, current
gates and money immediately under tlock. Build Add-step requests entirely in code, source_session from task,
model auto, UUID5(NAMESPACE_URL, `sup-<task>-<wake>`). Get preview and use **its** revision for request_next;
the supervisor revision is separate. Other decisions call task_lever with an internal origin, never an HTTP
round trip and never tasks.fred directly. Preserve public caller compatibility with keyword-only defaults.

Persist dispatching **before** the side effect and outcome after it. A persistence error before intent means
nothing is dispatched; uncertainty after a possibly successful side effect is recorded/held, never retried.
For a request_next response with status held, the step is already reserved: record the step/id and keep Fred's
pace/Fable hold. Do not append another step or auto-confirm it. Charge an automatic slot at reservation even
if held/failed, to avoid loops of refused launches. An uncertain lever retry consumes its retry allowance.

Auto caps: three added steps since Fred acted; one supervisor retry per step beyond the chain's retry; $5 of
supervisor-caused work since Fred acted; task_max_steps also bounds supervisor appends. A FAIL -> supervisor
code repair uses that FAIL lineage's retry allowance; a following FAIL cannot produce another code repair
(even with a changed source/kind spelling), and escalates with both verdicts. Counts survive restart and internal
dispatch does not reset them. Approve is a real human act; it resets the auto window but retains lifetime pass
spend, task length, gates and any explicit forbiddance. Cap fallback is a suggestion, never a secret gate bypass.

Own passes stop launching at $0.50/task or $2/day. Serialize admission/accounting with tlock and the existing
Usage file lock in their established order, include in-flight
remaining-budget reservations when parallel > 1, and count error results' reported costs. Reserve at most the
remaining task/day allowance, pass that remainder as the CLI budget, then settle actual reported cost. A timed
out/crashed pass with unknown spend retains its reservation and blocks automatic reuse of that allowance.
Work limits gate new launches using current observed attempt costs and retain task_step_budget_usd and existing
harness bounds. CLI costs are estimates and one in-flight call/worker can overshoot a threshold; never claim an
exact billing ceiling or erase an overrun. This limitation of the CLI budget is documented in Task 4 and tested
as 'record full cost; prohibit another launch'. No unasked accounting service or provider integration is added.

## 5. Verification and completion

R3: evidence `revision` remains the task freshness check. Separately save `prompt_hash`, SHA256 of the exact
UTF-8 prompt sent on stdin, including the substituted kind body, schema reminder and packed digest. Build
that prompt once from the snapshot and use those same bytes for hashing and execution. Replay returns
original/current values for both hashes. A kind-only edit changes prompt_hash, not evidence revision; a
missing historical fingerprint is unavailable, never reconstructed from today's files. This fingerprint
is diagnostic metadata and does not itself supersede an otherwise valid pending decision.

New tests live in `tests/test_supervisor.py` (pure/runner) and `tests/test_supervisor_server.py` (Hub/HTTP), with
focused updates to existing config/kinds/compact/task/intake/Usage/CLI suites. Reuse temporary CC_CONSOLE_HOME,
fake_claude, explicit advance and threading.Event barriers. Debounce/stall tests advance a fake clock and release
controlled passes; no 20-second sleeps or real providers. Tests of dispatch inspect call counts and persisted
state, not only rendered text. Each task names the exact edge cases it must make red first.

Task 12 runs the full suite, `node --check web/app.js` as an unchanged-frontend regression check, and the
cross-feature adversarial matrix. A real CLI smoke test is an explicitly separate live check for Fred; no hook
installation, settings edit or paid execution happens during this planning run or automated acceptance.

CLI reference checked 2026-10-18: [Anthropic CLI reference](https://code.claude.com/docs/en/cli-reference).
The bounded pass reuses the repository's command; Task 4 pins its arguments in tests. Current docs confirm
empty tools, structured JSON, turn/timeout-related flags and session-persistence control. CLI budget enforcement
uses estimates and can overshoot. Do not add daemon/background-agent commands or assume their behavior applies
to this one-shot pass. Recheck flags against that primary source when Task 4 is executed.

Backend done means Tasks 1-12 accepted, default suggest, no hidden automatic process, no regression in plans
18/24/36/40/41/42/43 or the shipped navigation/handoff. UI and skill-library work remain explicitly pending.
