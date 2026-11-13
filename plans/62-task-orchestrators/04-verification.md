# Fixtures, acceptance cases and evidence

Parent: [plan 62](../62-task-orchestrators.md). Prototype checks and runtime checks are separate.
This document specifies future checks; writing the plan is not evidence that they have run.

## 1. Mockup fixtures

Reuse the reference's fictional task/project names so visual comparison is straightforward. Replace its old
global-supervisor copy and semantics. All connection/model availability below is sample data.

Sample route table:

| CLI | State | Routes and role |
|---|---|---|
| Codex | Connected/enabled, orchestration capable in fixture | Astra: orchestration and workers |
| Claude Code | Connected/enabled, orchestration capable in fixture | Opus: orchestration/verification; Sonnet: workers |
| OpenCode | Disconnected | No eligible orchestration route |
| Command Code | Disabled | No eligible orchestration route |

Store display name separately from configured route identity. Sample Astra can use `codex:gpt-6-astra`; Opus
and Sonnet can use existing Claude aliases. These strings do not assert actual installation or availability.
All six initial owners have requested/resolved effort High. The sample Codex mapping is Low -> Low,
Medium -> Medium, High -> High, Xhigh -> High, Max -> High, matching the currently read adapter. The sample
Claude mapping passes each of those five labels through unchanged, as the current wrapper does. These are
fixture mappings, not proof of what an installed provider version accepts. Use Medium when demonstrating
a changed global default so the new task's resolved effort visibly differs from the existing High tasks.

### 1.1 Initial tasks

| Fixture ID / task | Project/title | Owner | State/current work | Primary action |
|---|---|---|---|---|
| `import` / T-017 | Fieldnotes CRM / Keep customer notes on import | Opus, Claude Code | Question at step 3: append or replace duplicate notes; no writes pending a decision | Reply |
| `audio` / T-024 | Waveform Studio / Retry interrupted audio exports | Opus, Claude Code | First failed verification at step 4, Suggest mode; cancellation race needs a focused code fix then reverify | Review proposal |
| `thumbnails` / T-031 | Catalog Atlas / Cache product thumbnails | Astra, Codex | Step 3 implementation by Sonnet, Claude Code; orchestrator waiting for worker result | Open task |
| `captions` / T-038 | Frame Orchard / Preserve speaker names in captions | Opus, Claude Code | Step 2 worker running quietly on Sonnet; silence alone does not prove failure | Open task |
| `search` / T-033 | Harbor Reader / Add keyboard search | Astra, Codex | Step 2 worker on Astra; same model, separate worker session/context | Open task |
| `archive` / T-012 | Ledger Grove / Export invoice archive | Opus, Claude Code | Current verification passed; Ready, not accepted | Review result |

Initial Needs you count: three tasks (T-017, T-024, T-012). Initial active-worker count: three (T-031, T-038,
T-033). The three waiting orchestrators must not be portrayed as three actively thinking model calls.

Keep the reference's step names where they fit. T-024's new proposal is an ordinary within-cap code repair and
fresh verification, not its former second-failure exception or a switch of the task's owner. Approving it
adds/starts one permitted worker step once; future verification is planned until its own simulated start.

T-031 acceptance examples:

- Requested dimensions remain distinct in the cache key.
- Cache retention is bounded and eviction works.
- Existing thumbnail behavior passes relevant regression checks.

Initial criteria are not all Passed while implementation runs. A later writing change makes previously checked
code-result criteria `Needs recheck`. T-012 has complete current evidence but awaits the user acceptance action.

### 1.2 Usage ledger

All numbers are fictional processed-token totals and cost estimates. Costs are specified fixture values,
not calculated from current provider prices. Use integer cents in the prototype to make reconciliation exact.
Each row is a distinct run/turn identity, with role and task attribution. Render totals from these rows.

| Record | Task | Role | Model | Processed tokens | Cost cents |
|---|---|---|---|---:|---:|
| u01 | T-017 | Orchestration | Opus | 18000 | 24 |
| u02 | T-017 | Workers | Sonnet | 36000 | 18 |
| u03 | T-024 | Orchestration | Opus | 22000 | 30 |
| u04 | T-024 | Workers | Sonnet | 48000 | 24 |
| u05 | T-024 | Workers | Opus | 30000 | 42 |
| u06 | T-031 | Orchestration | Astra | 21000 | 18 |
| u07 | T-031 | Workers | Sonnet | 63000 | 31 |
| u08 | T-038 | Orchestration | Opus | 12000 | 16 |
| u09 | T-038 | Workers | Sonnet | 27000 | 14 |
| u10 | T-033 | Orchestration | Astra | 15000 | 12 |
| u11 | T-033 | Workers | Astra | 33000 | 26 |
| u12 | T-012 | Orchestration | Opus | 16000 | 22 |
| u13 | T-012 | Workers | Sonnet | 40000 | 20 |
| u14 | none | Other sessions | Opus | 10000 | 14 |
| u15 | none | Other sessions | Astra | 9000 | 7 |

Expected model totals: Astra 78,000 / $0.63; Opus 108,000 / $1.48; Sonnet 214,000 / $1.07.
Expected global total: **400,000 processed tokens / $3.18**.
Expected task totals: T-017 54,000/$0.42; T-024 100,000/$0.96; T-031 84,000/$0.49;
T-038 39,000/$0.30; T-033 48,000/$0.38; T-012 56,000/$0.42.
Task subtotal 381,000/$2.97 plus other sessions 19,000/$0.21 equals the global total.

Do not create separate hardcoded display totals. Adding another turn or changing its measurement must update
all affected views once. The unknown-usage scenario adds one unknown record and shows a known subtotal plus
`1 session with unavailable usage`; it must not turn unknown into zero or erase the existing known subtotal.

Context renewal demonstration adds a new T-031/Astra orchestration record with 3,000 processed tokens and
3 cents. After completion: Astra 81,000/$0.66, T-031 87,000/$0.52, global 403,000/$3.21. Replaying the same
sample event cannot add it twice. The task's model, effort and archived records stay unchanged.

Auto assignment uses the fixture's usage AND active-load/capability snapshot. With equally idle eligible
routes and no allowances, Astra has lower usage than Opus. If Astra is active and Opus idle, the existing
idle-preference rule can select Opus. Test both rather than claiming lowest token total always wins.

### 1.3 Context fixture

T-031's last decision can show checkpoint 3.6 KiB, initial packet 18.4/32 KiB, additional results 6/16 KiB,
and three of six tool calls. All are illustrative byte/call measurements. An independently supplied 6.4k token
estimate is labelled `Estimated last decision context`, never derived with a fixed bytes-to-tokens conversion.

Sources include original goal/criteria, saved decisions, accepted scout handoff and selected facts. A long
worker transcript is available in Step chat but omitted from the input manifest. Reading it for user inspection
does not mark it model-included. Renewal shows a smaller new input and unchanged archived history, plus the
additional usage record above. Do not claim a measured savings percentage.

## 2. Required scenarios

The review toolbar selects these deterministic fixtures. Do not create more product controls to reach them.
Store scenario state once; all rendered views read that same state.

| ID | Scenario | Required proof |
|---|---|---|
| S01 `default` | Six-task overview | Counts 3 Needs you / 3 active workers; fixed owners visible |
| S02 `worker-running` | T-031 step stream | Worker activity, orchestrator waiting, same owner |
| S03 `question` | T-017 question and answer | Same composer, source-step identity, separate delivery receipts |
| S04 `proposal` | T-024 suggested repair | Approve/reject once; within existing caps; no owner switch |
| S05 `ready` | T-012 ready | Current evidence and explicit acceptance |
| S06 `accepted` | T-012 after acceptance | No active composer; explicit reopen |
| S07 `cli-unavailable` | T-031 owner disconnected at decision boundary | Saved owner retained, named hold, no fallback |
| S08 `rate-limited` | T-031 owner temporarily limited | Owner retained; unknown reset not invented |
| S09 `renewal` | New T-031 decision session | Same owner/effort, bounded new input, global usage increment once |
| S10 `checkpoint-error` | Checkpoint publication failed | Prior valid checkpoint retained; no new worker |
| S11 `context-overflow` | Mandatory input cannot fit | Coverage hold, no silent cut or success |
| S12 `uncertain` | Dispatch outcome unknown | No auto-replay, no optimistic duplicated step |
| S13 `budget-hold` | Existing work/day cap reached | Named cap, no override or model swap |
| S14 `paused` | Task paused with queued guidance | No next launch; queue retained; Resume uses gates |
| S15 `stopped` | User stopped current work | Honest stopped state; no automatic retry |
| S16 `capacity` | Worker ready but capacity unavailable | Queued rather than Running |
| S17 `unknown-usage` | One missing usage record | Known subtotal plus missing count, no fake zero |
| S18 `no-eligible-cli` | No eligible owner for a new task | Start unavailable with reason; draft preserved |
| S19 `empty` | No tasks | New task action, no invented activity |
| S20 `loading` | Loading snapshot | Explicit temporary state; no fake normal controls |
| S21 `offline` | Snapshot unavailable | Named error/retry; no invented live status |
| S22 `long-content` | Long task title, path, model label and tool output | Wrapping/local scrolling; readable at 340 px |
| S23 `stale-verification` | Writing after a passed check | Affected criterion needs recheck; Accept unavailable |
| S24 `delivery-uncertain` | Message delivery not confirmed | Saved message retained, no duplicate automatic send |

Disconnecting an owner blocks its next decision; it does not imply an unrelated running worker was killed.
Use a decision boundary for S07/S08 to demonstrate the hold cleanly. S14 states whether an existing worker is
still running; Pause is not Stop. Do not counterfeit production recovery actions to make S12 look resolved.

## 3. Prototype acceptance cases

| Check | Requirements | Procedure and expected result |
|---|---|---|
| M01 | R01,R10 | Overview has task cards and no global conversation/composer. Desktop task view derives visibly from reference. |
| M02 | R01,R02 | Open two different tasks: conversation/identity/assignment differ correctly. Each task's model stays fixed across tabs and state transitions. |
| M03 | R01,R08 | Type distinct drafts for T-031/T-017, switch repeatedly, inspect old/current/planned steps: drafts and recipient remain task-specific. |
| M04 | R02 | Apply S07/S08/S09: no fallback model; renewal preserves model, CLI and effort. |
| M05 | R03 | New task excludes disconnected/unsupported routes, explains why, validates explicit picks and recomputes provisional Auto at Start. |
| M06 | R03,R05 | With equal active load, lower global usage influences new assignment; with differing activity, fixture respects existing idle preference. Existing owners do not change. |
| M07 | R04 | Save different global effort; existing tasks retain High. Newly assigned task uses the new mapped effort. |
| M08 | R05 | Render all ledger projections and compare exact totals above. Duplicate event does not add spend/tokens again. |
| M09 | R05 | Complete renewal: one additional turn updates task/model/global totals exactly. S17 never displays missing usage as zero. |
| M10 | R06,R07 | Approve T-024 proposal once: a focused worker becomes assigned/running; verification remains planned until its event. Reject does not run it. |
| M11 | R07 | T-012 moves Ready -> Accepted only on user action. S23 invalidates evidence and removes acceptance availability. |
| M12 | R08,R09 | Context includes selected sources with coverage; worker transcript stays separate. Bytes/tokens/unknown states have correct labels. |
| M13 | R09 | S10/S11/S12 hold with their reason and preserved evidence; do not claim successful continuation or repeat an uncertain effect. |
| M14 | R01 | Question answer preserves source identity. Submission, receipt and worker delivery are separate chronologically stable events. |
| M15 | R01 | Step chat remains read-only. Message orchestrator focuses the one composer without changing task or sending text. |
| M16 | R01 | Stream updates preserve focus, drafts, expanded tools, scroll and user-event order, including equal-timestamp receipts. |
| M17 | R07 | Pause retains queue, Stop differs from Pause, limits/capacity hold correctly, accepted tasks require explicit reopening. |
| M18 | R10 | Width/theme/narrow tabs and all S01-S24 work; no clipped controls or body overflow. |
| M19 | R10 | Keyboard-only navigation, focus return, dialog Escape, accessible names, non-color status and reduced motion. |
| M20 | R10 | No HTTP(S), production API or real process action. No browser console/page errors. All supplied user text is escaped. |
| M21 | R10 | Reset reproduces initial fixtures/totals. Deep links choose deterministic views; invalid queries fall back safely. |
| M22 | R01,R05 | Observed-session view has no fabricated owner. Its known usage still contributes to global totals. |

## 4. Browser and visual evidence

Use installed Playwright with Edge as the reference does. Do not install a browser/dependency without need.
Automate semantic behavior and measure overflow; also open and inspect the resulting images.

Minimum capture matrix:

- Tasks overview and selected T-031 Overview, Step chat and Context at 1510x1080, both themes.
- Selected task at 900x900, both themes, with useful two-panel content.
- Orchestrator and Step chat at 400x760 and 340x760, both themes.
- New task, Settings and Usage at desktop and 340 px; both themes checked, images can focus on the harder case.
- Question, proposal, ready, disconnected owner, renewal and checkpoint failure at desktop; a question and a
  blocked state at 340 px. Reduced-motion and 130% text-size checks for selected task views.

Short-height cases must measure the application viewport itself; a tall external review toolbar must not make
a 760 px screenshot appear usable by pushing the product below the visible area. Use a compact/collapsible
review toolbar or focus the app frame while retaining the sample disclosure.

`check-results.json` records IDs M01-M22 with pass/fail/not-run, evidence file/scenario, console/network errors,
viewports and reference fingerprint. Never fill all entries with PASS without executing the checks.
`visual-review.txt` records what was actually inspected, defects fixed and remaining limitations.
`review.html` maps R01-R10 to the implementing screen and check; names deliberate departures from the reference;
lists backend assumptions and uses the wording `Proposed, not approved`.

`source-head.txt` records current git HEAD, the reference HTML SHA-256 and that uncommitted reference changes
were included if applicable. Recorded reference at planning time:
`e22b0616dd8230e746e62756965702854515774e76b5c6488dd88a5afa6d8122`.
Re-read the source at build time; if changed, reconcile visual evidence rather than treating this hash as a lock.

Do one complete inspection pass, fix the defects it reveals, then a focused confirmation pass. Recheck again
only for a material new change or unresolved failure. No unbounded polishing loop.

## 5. Runtime acceptance cases, for the implementation agent

| Check | Required evidence |
|---|---|
| B01 | Legacy task loading and persisted immutable assignment across worker retries, fresh decisions and restarts |
| B02 | Exactly one decision owner and one dispatch per coalesced event/request, including migration interruption |
| B03 | No cross-task access via IDs, stale credentials, paths, UNC/drive-relative paths, links or junctions |
| B04 | Validated checkpoint publication; prior good state survives failure, stale proposal and corrupt input |
| B05 | Mandatory overflow holds; optional coverage explicit; multibyte payload bounds and cumulative call/read limits enforced |
| B06 | Tool restrictions proven on each admitted CLI; unknown capability excludes rather than broadens permissions |
| B07 | Global effort mapping and immutable saved assignment; no silent fallback on limits/disconnection |
| B08 | Orchestrator/worker/other usage feeds global model fills once; duplicate observations, multi-turn sessions and provider cache semantics covered |
| B09 | Reservations, unknown usage/price, paid failures and crash reconciliation do not create free capacity or duplicate spend |
| B10 | Adaptive worker choice, criterion/evidence validation, stale verification and bounded retry lineage |
| B11 | Guidance persisted before acknowledgement, delivery order preserved, uncertainty never auto-replayed |
| B12 | Intent-before-effect, live gate/revision recheck, late completion rejection and user Pause/Stop precedence |
| B13 | Model process ends while waiting; no paid polling; context renewal does not reset budgets or assignment |
| B14 | Task read projections/actions and UI agree; overview reads neither start work nor mutate state |
| B15 | Global pass retirement preserves history; manual/off/observed paths remain usable and do not gain an owner implicitly |

Tests use fake providers and isolated homes. Real-provider evidence, when authorized, records actual versions,
token/cache counts, context telemetry, latency and cost. Prototype M-checks cannot substitute for these B-checks.
