# Plan 58 review and JEV assessment (2026-11-08)

Plan-only review against Console `7c5e149` and sticker-generator-simple `7d80561`. No implementation,
provider request, service restart or change to the sticker project. This is a contract supplement to
Tasks 1-7, not an eighth implementation task. D1-D11 remain Fred's decisions; D12 below is a new proposal.

## 1. Required corrections

These requirements take precedence over the original implementation sketches and old exact-value test
examples. Each task links its affected rows. The Hub and route recipes have been replaced with implementation
steps because their original error handling could silently acknowledge failed saves or launch an unaudited pass.

| ID | Gap in the original plan | Required behavior | Task |
|---|---|---|---|
| R1 | A missing, invalid or expired `until` became Later forever; no running task means no sweep to rescue it. | Later needs a nonblank reason and a valid future local time, at most 24 hours ahead. Otherwise forward. An active auto-default decision stays forward. An expired Later returns once even with no running tasks. | 2, 3, 5 |
| R2 | Only the first 30 ranked items were submitted again; overflow could never be reviewed. Replacing all annotations also erased advice for unseen items. | Select by least recently reviewed, merge only validated current entries, and report coverage. All live items remain in the API. No automatic paid loop to drain overflow. | 1-3, 5, 6 |
| R3 | Event keys omitted option/default changes, supervisor status/reason and changed STOP text. Completion trusted `seen` from a prior tick. | Expand identity, compare the current decision basis at completion and on GET, and discard stale advice. Always settle paid work even when its advice is stale. | 2, 3, 5, 6 |
| R4 | Claim and Pause saves swallowed errors. Thread-start failure left `busy` set; restart ignored reservations missing from state. | Durable claim before launch, explicit persistence failure, recovery by pass UUID, and guaranteed cleanup. Pause never returns success if it did not persist. | 1, 4-6 |
| R5 | Ledger reads returned zero on error; individual malformed records were ignored; negative costs could restore allowance. | Validate records before totals, reject invalid costs, propagate ledger errors, retain unknown reservations. A refused reservation must be visible in GET. | 4-6 |
| R6 | Sonnet was selected only for newly arrived stuck items; manual Sort/restart could route the same stuck work to Haiku. | Choose from the items actually included in this pass, including tasks stuck beneath a suggestion card. No JEV needed for this rule. | 3, 5 |
| R7 | `describe` copied raw metadata, GET returned raw notes, and item clipping could remove options or open questions. | Mask every external text at the boundary, preserve IDs for lookup, reserve room for orders, and mark incomplete evidence so it cannot justify Later or batching. | 1, 3, 5, 6 |
| R8 | Same-kind batching allowed unrelated decisions; the signal code skipped intervening PASS verdicts. | Batch only identical answer contracts, and compare the last two completed verifies, both FAIL. | 2, 3, 5 |
| R9 | Admission/sweep/debounce used the wall clock; cap/off recovery needed another task event. | Monotonic scheduling; local wall time only for display, expiry and accounting. One wake on a blocked-to-eligible transition with live items, never repeated model-error retries. | 5, 6 |

### R2: bounded coverage, not an unbounded scheduler

Add `reviewed: {key: pass_number}` to state; `sync` removes departed keys from it. Select items by
`(reviewed.get(key, 0), always-first, first_seen, key)`, then fit at most 30 **whole** blocks into the byte budget.
Selection order is independent of the displayed ranked queue. Mark only the handles actually sent as reviewed
   after a current, structurally valid response with at least one usable item. Rejected entries count as attempted
for selection fairness, but receive no invented annotation. Keep prior valid advice for omitted/rejected entries;
expiry, changed basis and hard-forward rules still override it. Never erase unseen items' annotations.

Every accepted batch name is scoped to its pass UUID internally; `batch: acc` in two different passes cannot
join unrelated items. Recheck grouping after filtering departed or stale members. An incomplete/singleton group
is forward. With 65 unchanged small items and three successful Sort passes, each item must have been submitted
at least once, including when 31 items are always-forwarded. Byte-limited cases may require more passes.
Overflow alone starts no model call. The next event, eligible sweep or explicit Sort continues coverage.

GET adds `coverage: {live, last_submitted, never_reviewed}`. `ranked` means advice is available, not that every item
was reviewed in the last call. Done criteria and UI copy must make that distinction.

### R3: a decision basis, not an age or cost hash

Task event identity includes the decision's full `q/options/default/step/asked/taken`, current attempt count,
pending supervisor `wake/status/decision/error`, current usage-limit value and `always_reason`. Session identity
also includes `stop_question`. Use canonical JSON and at least 16 hex SHA-256 characters. Time passing, token
usage, total cost and `updated` alone do not change identity.

Each annotation also stores `basis`, a SHA-256 of the decision-relevant description: event key, effective level,
absolute default deadline, answer contract, relevant open questions/verify evidence and incompleteness flags.
Do not include `age_s`, the ticking `left_s`, previous annotations, pass number or recommendation text. Store a
separate policy hash of the effective orders, kind text and settings used by the pass. No task-file schema changes.

On completion, rebuild live items and these bases under `tlock`; do not trust the previous `seen` map. Accept only
annotations whose key and basis still match. Changed policy discards the whole answer. If any submitted item
became stale, retain eligible individual annotations but discard this pass's global digest and notes. GET filters
stale advice immediately using a copied projection, without writes or waking a pass. The next tick performs the
durable cleanup. A changed basis/policy is one debounced event, not a perpetual timer wake.

### R4/R5: persistence and accounting order

1. Validate settings, storage state and the ledger. Build a bounded immutable input snapshot. No network or model
   call while holding a lock. Task and session views must be coherent under the existing `tlock -> lock` order.
2. Reserve a UUID in `usage-days.json`. Write `claimed` in state and append the claim audit entry successfully
   before starting the thread. The saved claim includes handles, item bases and policy hash, so recovery can
   identify the input without rebuilding old task state. Include `pid` (the pass UUID, not an OS PID) in **every** result/refusal that has one.
   Do not identify settlements by the display counter `n`.
3. Snapshot/claim/log/thread-start failure before invocation settles at zero. Preserve a recoverable claim if that
   settlement/save also fails; keep the queue visible and block further admissions with a storage error. Never
   swallow the error and start a paid process. Keep only live thread references.
4. Persist a masked result containing its known cost or explicit unknown, then settle the reservation. If either
   fails, retain the result/claim for reconciliation and block new admissions. Only after durable accounting may
   the checked annotations/notes be published. Keep `claimed` until the final state save succeeds. A notes-save
   failure leaves the previous notes and a visible storage error; it does not label a partial publish successful.
   These files are not a multi-file transaction: if notes save but final state fails, the new notes may exist.
   Block their reuse and show an unranked storage error until the durable result/claim is reconciled. Recovery
   may republish that saved result only after live-basis validation; it never calls the model again.
5. On restart reconcile `state.claimed`, both audit files and every `reserved` record in the `super` ledger.
   A durable result settles once; an already-settled record stays settled; an orphan reservation becomes unknown
   and stays charged to its admission day. Never rerun a model request on recovery. If state was lost, the ledger
   still protects spend. If evidence conflicts, block and expose the inconsistency instead of picking a cost.
6. Pause/resume persist a candidate state before acknowledging it. A failed save returns 503 and holds admissions
   locally until durable state is restored. Sort must durably log acceptance before arming its in-memory wake;
   a restart may lose that wake as already allowed. No response may claim Pause survived restart when it did not.
7. Missing state is a fresh install; unreadable, corrupt or unsupported-version state is an error and blocks
   passes while showing a raw queue. Do not reset a lost Pause to false. Read failures for an existing orders file
   also block admission; an absent/empty orders file remains valid. Validate annotations loaded from disk.

Validate each `super` ledger record's object shape, local day, status and finite nonnegative amounts. Reserved or
unknown records have zero settled cost and a positive reservation; settled records have a finite nonnegative
cost. Reject booleans, NaN, infinity, negative values and unknown statuses. Invalid reported cost is unknown,
never a negative settlement. Do not change supervisor accounting silently when sharing helpers: preserve its
existing behavior or isolate stricter validation in `load_super`/`record_super`. Test both ledger sections.

An unreadable ledger is an error on GET and admission, never a zero spend display. Read it once per view, under
the existing file lock where needed, and derive totals and status from that same result. Keep the admission day
when a pass crosses midnight. Limits are reservation/admission limits; provider-reported overshoot is recorded
in full and blocks subsequent admissions. Do not promise a hard billing ceiling the CLI cannot guarantee.

### R7/R8: evidence and trust boundaries

Mask user/model text before clipping, including titles, project display names, errors, hand-edited notes and
orders, and the editable kind body. Opaque task/session keys remain usable lookup identities. If `project_dir`
can contain sensitive text, keep the real path internal and mask its display value; future actions target `id`.
Bound the full prompt (kind + reminder + digest), not just the digest: `PROMPT_MAX = 48 * 1024` UTF-8 bytes.
An oversized role is an explicit input error. Never truncate serialized JSON to meet a bound.

Reserve space for bounded standing orders before item selection. If orders exceed their supported limit, report
an error instead of silently dropping policy. Escape/delimit task text, observed chat text and previous model notes
as untrusted evidence; the code-owned schema reminder states that only Fred's orders are priority instructions,
and none can override code gates. Masking alone does not prevent prompt injection.

Build item blocks field by field. If options, open questions or verify evidence cannot fit, include an explicit
`incomplete` flag, keep the full card in GET and force forward/no batch for that item. A missing/truncated brief
means unknown, not "no open questions". Read briefs only for selected items, without an unbounded filesystem
scan under `tlock`. Before publishing a recommendation, recheck its evidence basis.

For batch proposals require matching kind, effective level, question, option keys/text/default and available
answer action. Supervisor suggestions must also match the proposed action. No compatible contract means forward.
Code makes no semantic claim that different questions have the same answer. Batch is presentation only in slice 1.
The last two **completed verify steps**, in step order, must both be FAIL with the same nonempty detail for
`same_fail`; FAIL, PASS, FAIL is not a repeated consecutive failure.

### R9: scheduling and recovery

Keep a monotonic clock for wake first/due and sweep intervals, plus the existing injectable wall clock for seen,
until, local date and audit. The 120-second ceiling bounds debounce only: an existing pass, poll interval or closed
gate can delay launch. Coalesce duplicate events, and prune exited pass threads. A day rollover or an observed
config/executable/storage gate becoming eligible arms one wake when items remain; unchanged eligible ticks do
nothing. A failed model call waits for Sort, a new input event or a changed eligible sweep, never a blind retry.
A restart with unchanged valid state is not itself a wake.

## 2. What the sticker project actually uses

Read-only source: `D:\WORK\10 - AI\SQUARE LAB\DECATHLON\sticker-generator-simple`, commit `7d80561`.

- `scripts/typesafe_checks.py`: `MODEL = "jev-1.14.0"`, direct HTTPS to TypeSafe System One, standard-library
  `urllib`, a replaceable `post` transport, named typed questions, image/text hashes and recorded responses.
- `check_ticket`/`ticket_verdict`: narrow word choices; uncertain answers remain undecided; confident disagreement
  routes a delegated reviewer back to the human. A JEV answer never grants reviewer authority.
- Ticket thresholds 0.75 and 0.8 are tied to that project's visual experiments. Its source comment reports
  60 decisions with no errors from a 160-ticket holdout. I did not independently reproduce that experiment, and
  those thresholds do not transfer to task routing.
- `scripts/typesafe_screen.py`: records keyed by exact artifact hash and screening version, bounded concurrency,
  explicit off/no-key/failure states, advice separate from workflow state.
- `calibration` and `tests/regression/check-typesafe-{checks,prescreen}.py`: compare advice with a human verdict
  on the same artifact; test fake transport, stale bindings and failure paths.

Reuse the pattern: narrow question, immutable evidence/version binding, abstention, deterministic authority,
measured outcomes. Do not copy image crops, ticket thresholds, `.env` lookup, the worker pool or stacked transport
and worker retries into Console.

## 3. Current primary-source findings

Checked 2026-11-08. JEV returns typed values, not prose. Choice selects among explicit candidates; Score rates a
rubric; Noul supplies a yes-probability. Questions in one request share state but are evaluated independently,
so a later question cannot consume an earlier answer in that request. This suits narrow classifications, not
the full `items/digest/notes` contract. [TypeSafe introduction](https://docs.typesafe.ai/introduction)

Choice returns a selected option and a probability distribution; the question identifier is not shown to the
model. Put the item's handle and evidence in the question instructions/state, not only in its JSON map key.
[Choice reference](https://docs.typesafe.ai/primitives/choice)

`confidence` summarizes a distribution and is not a correctness guarantee or interchangeable with
`probabilities[choice]`; Noul has no separate confidence field. Thresholds need Console-specific evaluation.
[Confidence](https://docs.typesafe.ai/confidence),
[probability routing](https://docs.typesafe.ai/patterns/probability-routing)

Command Code documents headless `-p <request JSON> -m typesafe/jev`, its normal login, and $0.042 per million input
tokens. At that published rate, 10,000 input tokens are $0.00042 before any fallback call. This is an estimate,
not a measured Console latency/cost or a claim about direct TypeSafe pricing.
[Headless decision models](https://commandcode.ai/docs/headless#decision-models-typesafe-jev)

Its Provider API also documents pinned `typesafe/jev-1.14.0`; the models reference lists that pinned ID as API-only.
Do not assume the installed CLI supports pinning. Command Code says JEV has no ZDR-capable upstream, so redacted
cross-project data would reach another provider without a zero-retention guarantee.
[Provider API](https://commandcode.ai/docs/provider),
[available models](https://commandcode.ai/docs/reference/cli/models)

Console's `BRAINSTORM.md` section 2 allows model calls only through harness CLIs and forbids network calls of its
own. Consequently the sticker project's direct HTTP client is outside the current contract. The existing
`console/harness/cmd.py` resolves npm shims safely via Node, but `run_command` appends a STOP footer and chat flags,
and `summary` expects chat results. Neither accepts JEV's raw JSON contract unchanged. Reuse `find_exe` and
`command` in a small dedicated decision-command path; never invoke Windows `cmd.exe` as if it were Command Code.

The existing Claude pass remains viable. Current Claude docs confirm `--safe-mode`, tool disabling and MCP denial;
managed policy can still apply. Task 7 must record the installed version and actual command behavior, rather than
claiming safe mode removes every possible customization. [Claude CLI reference](https://code.claude.com/docs/en/cli-reference)

## 4. Recommendation and implementation gate

**Could: yes. Should: evaluate as an optional classifier after the corrected slice 1 baseline. Do not replace
the Haiku/Sonnet pass or make JEV a prerequisite for plan 58.**

| Use | Recommendation |
|---|---|
| Detect caps, uncertain dispatch, stale items, unavailable models, defaults or permissions | Keep deterministic code. Paying JEV adds no information. |
| Generate `say`, `why`, digest and rewritten notes; diagnose a stuck task | Keep Haiku/Sonnet. JEV does not generate the required text. |
| Route an otherwise ordinary pass to Haiku or Sonnet | First candidate for shadow evaluation. Known stuck inputs force Sonnet before any classifier. |
| Classify Prep demand (`reasoning`/`volume`) | Possible separate follow-up; feed validated categories into existing `routing.pick` and `tasks.step_route`. Prep still needs its written goal/steps, so measure whether an extra call saves anything. |
| Rank urgency or flag an unsupported recommendation | Possible later experiment with labeled examples; measure false demotion. No initial JEV-driven Later or batching. |
| Accept, take a default, approve a supervisor action or route around a cap | Not authorized in slice 1. A probability never supplies permission. |

D12 proposed answer (a): retain the corrected baseline, then run a **separately enabled shadow evaluation through
Command Code**. (b): no JEV experiment. A direct TypeSafe API path would require a separate explicit change to
the no-network design rule; it is not implicitly approved by this review. No new setting or product code now.

The smallest follow-up, if selected:

1. Add one text-only decision request after code gates, before `pass_model`, on the same bounded, masked input.
   One Choice: `routine` (straightforward prioritization), `needs_judgment` (competing evidence or diagnosis),
   `insufficient` (cannot judge from supplied evidence). Explicitly identify the batch in instructions. Shadow
   mode records the choice without changing the existing route. No self-reported "safe to act" question.
2. Keep JEV out of worker model tiers, task session rows and the Claude schema. No SDK, generic provider framework,
   new daemon, image support or second workflow state. Respect the Command Code harness enable switch and health.
3. Validate all question IDs/types, exact candidate keys, finite probabilities in [0,1] summing to 1 within 1e-3,
   selected option membership, confidence range and nonnegative integer usage. Missing/malformed output is no
   answer. Pin model and rubric if supported; otherwise record the returned model and invalidate evaluation/cache
   on alias/version drift. If only an unresolved moving alias is returned, keep the experiment shadow-only
   until a verifiable model version is available. Do not cache decisions across changed bases.
4. One bounded attempt, no nested retries. Missing CLI/login, timeout, auth/credit error, unsupported version,
   invalid output or budget refusal uses the baseline route and records why. If promoted after evaluation,
   `needs_judgment`/`insufficient`/uncertain answers can only upgrade an otherwise-Haiku pass to Sonnet; known
   Sonnet cases never downgrade. This first experiment does not claim inference savings.
5. Before live shadow calls, define the combined JEV + fallback reservation, a finite request byte/token bound,
   timeout and daily budget. The CLI decision docs do not establish a hard per-request USD cap or cost envelope;
   verify installed behavior and retain unknown spend on timeout. Keep provider/reported usage and derived cost
   distinct. Never charge zero just because the decision response lacks `total_cost_usd`.
6. Compare three paths on a project-separated labeled holdout: code rules alone, baseline Haiku/Sonnet,
   JEV-assisted route. Label urgency, need for judgment and unsafe demotions with Fred; baseline model agreement
   alone is not ground truth. Include decisions near expiry, overflow, conflicting projects, missing evidence,
   injection text, stale results and provider failures. Fit thresholds on a separate calibration split.
7. Report missed high-priority cases, unnecessary Sonnet upgrades, abstention/fallback rate, p50/p95 end-to-end
   latency, total provider cost and agreement with human corrections. Choose numerical promotion targets before
   evaluating the holdout. Remain shadow-only unless it improves the agreed quality/latency/cost objective with
   every hard-gate invariant passing. No transfer of the sticker project's 0.75/0.8 thresholds.

## 5. Acceptance additions

All future implementation tests are offline, scratch-home and fake-provider tests. This review itself does not
claim they passed against a product implementation that does not yet exist.

| Tasks | Required regressions |
|---|---|
| 1 | Missing vs corrupt state; lost Pause; unsupported version; malformed annotation; existing unreadable orders; oversized role/orders; secret ending a JSON string. |
| 2-3 | 65 items over successive passes; byte-limited non-ASCII blocks; 31 always items; annotation retention; pass-scoped batches; changed options/default/supervisor/STOP question; invalid Later; auto-default Later; incompatible same-kind batches; FAIL/PASS/FAIL. |
| 4 | Malformed individual ledger rows; negative/NaN/bool costs; tiny reservation rounded to zero; unknown held spend; midnight; cross-section concurrent writes preserve both sections. |
| 5 | Fault injection at reserve, claim-save, claim-log, thread-start, result-log, settle, notes-save and final-state-save; restart each boundary, exactly one charge and no automatic replay. |
| 5-6 | Resolve/change an item between snapshot and completion without a tick; policy edit mid-pass; GET immediately hides stale advice; unreadable ledger never displays zero; Pause save failure is 503. |
| 5-7 | Wall-clock jump cannot extend debounce; cap rollover and off-to-on each wake once; existing stuck task on Sort uses Sonnet; bounded thread list; no blind retries; real latency/cost reported by model and input size. |

Before paid acceptance, close D1-D11 (especially automatic spending D2). If D12 is chosen, a separate follow-up
must satisfy its transport, budget and calibration gates. Reviewing this plan authorizes neither paid trials nor
an implementation of acts.
