# Task 3: saved-evidence digest and decision contract

> Contract: [README.md](README.md) 4.2, 4.5; brainstorm sections 5-6. Lands on Tasks 1-2.

**Files**
- Modify: `console/supervisor.py` (`SCHEMA`, `DIGEST_MAX`, `digest`, `revision`, `check`)
- Modify: `tests/test_supervisor.py` (`DigestTest`, `DecisionTest`)

## 3.1 Digest and revision

- `digest(home, task: dict, context: dict) -> str`: context contains the active wake's triggers, policy,
  levers, sources, owned-source facts and budget summary, captured from the live Hub under tlock. This
  refines the brainstorm's hub argument into immutable data for worker/replay safety. No calls
  to transcript, runs.chat_of, final_message, git or network. Only saved files in this task, plus gate/policy
  numbers and budget summary already in memory. Never include config.json, other tasks, plan part bodies,
  received files, healthy notes.md or run JSONL. Missing files are named unavailable, never interpreted PASS.
- `revision(home, task: dict) -> str`: semantic hash of task goal/project/progression/state/why, explicit
  pause/epoch, step identity/state/session/attempt and source lineage, saved notes/briefs/facts/verdict and
  plan index metadata/text. Exclude audit/chain noise, updated timestamps, own-spend counters and cost-only
  updates. Revision reads the same permitted evidence, not transcripts. Gates/spend are checked separately
  live. Save revision at pass start; compare it at completion and Approve.

**R3 distinction:** revision deliberately excludes kind text. Task 4 adds `prompt_hash(prompt: str) -> str`,
SHA256 of the exact rendered prompt's UTF-8 bytes. Task 5 persists it with the claim; Task 11 compares it
alongside revision. Do not widen revision's signature or make prompt edits a new dispatch gate. A kind-only
edit must leave revision equal while changing prompt_hash; evidence edits can change both.

Use a local `DigestError` for mandatory-input overflow/unreadable required evidence. Existing gate methods
may consult their normal session/run metadata while constructing context; the digest itself does not pull
those streams into model input. Tests pass prepared context and make forbidden evidence readers raise.

Digest order: identity/goal (tasks.prompt_goal with current step, 600 chars)/state/owner/triggers/costs;
step table; last-good handoff else brief; its facts; relevant last verify; plan Goal/Decisions/Acceptance
and Step headings/part status; open questions; last ten chain records; stuck-attempt reason plus at most
ACCEPT_TAIL characters; finally allowed actions/source numbers/mode/remaining caps and Prep proposed kinds.
Reject note from the last human rejection is included next to the head, once, if present.

**Resolve the size conflict explicitly:** NOTE_MAX is 20 KB, larger than this digest's hard 12 KB. Never byte-cut
a handoff or facts and imply they are complete. Reserve identity, concise step table and 'Allowed now' first
(the latter cannot disappear when evidence is long). Add evidence blocks whole in priority order, dropping
lower-priority blocks first. If a whole note/facts block still cannot fit, include a short omission marker with
its saved relative file name and byte size. Goal and Troubleshooting are never partially quoted. If even the
mandatory head/table/gates cannot fit, return a typed digest-too-large failure and launch no model. Do not edit
any saved evidence. UTF-8 byte length, including omission markers, must be <= 12 * 1024, including CJK text.
This is a conservative packing rule for the brainstorm's incompatible whole-note and hard-cap requirements.

## 3.2 Schema and validator

SCHEMA is one object, additionalProperties false, required decision/reason/confidence/for_fred. Exact fields:
decision enum add_next_step/confirm/keep/retry/stepdone/stop/finish/answer/escalate_to_fred/wait;
reason nonblank <=1000 chars; confidence low/medium/high; for_fred <=400 chars;
optional kind, instructions, model, source_step, note, text. Bound instructions by STEP_GOAL_MAX, note by
server.NOTE_MAX's 2000-character contract (keep a local constant to avoid importing server), answer text
<=400. Apply required/forbidden per-action fields in check; no generic JSON-schema dependency.

`check(decision, task, levers, sources, policy) -> tuple`: reject non-dict, extra fields, missing/wrong type,
bool source numbers, invalid enum/kind, blank instructions, bad model, non-owned/external sources, blocked
live gate, disallowed wake/action combination and forbidden confirmations. Use policy for validated source
ownership, trigger flags and cap facts, never as a way to override a nonempty lever/source refusal.
For add_next_step require model auto; resolve omitted source from current in code and consult sources['NN'].
Source ownership may use the task's persisted service-launched attempt when stream/meta were legitimately
cleared; do not reject all old sources just because clear-on-done freed their stream. An external session
without an owned task attempt remains forbidden. Escalate_to_fred requires nonblank for_fred text.
Retry model is empty or haiku/sonnet/opus, note nonblank. `stop` requires stalled trigger and explicit human
approval at dispatch. `stepdone` requires human approval regardless of confidence. `answer` always refuses
with 'questions are Fred\'s'; Hub records the original and an effective escalate_to_fred. Confidence never
grants authority. Valid shape plus insufficient autonomy becomes a suggestion at Task 8, not malformed JSON.

## Tests first

- `DigestTest.test_saved_evidence_and_allowed_actions_only`: unique sentinel in each allowed/disallowed file;
  mock disallowed readers to raise; allowed handoff/facts preserved exactly, source and remaining caps present.
- `test_utf8_cap_whole_blocks_and_missing_evidence`: CJK oversized note/facts and many steps; no partial
  headings/facts, omission markers correct; mandatory overflow launches nothing in later runner test.
- `test_revision_ignores_cost_noise_but_changes_with_evidence_or_human_action`: mutate each input independently.
- `DecisionTest.test_each_decision_and_gate`: table-driven allow/refuse for every enum and matching lever.
- `test_unknown_fields_wrong_types_and_model_ids_refused`: paths/commands/skills, bool numbers, unknown
  confidence, long instructions/note/for_fred, exact or external model ids, source mismatch/later unfinished.
- `test_questions_fable_and_pace_cannot_be_approved`: even high confidence, auto mode or human flag cannot
  make answer/Fable/pace confirm legal. Manual source eligibility is always the supplied live gate's answer.

## Steps and acceptance

- [ ] 1. Pure tests red; add only schema/packing/revision/check logic, with no Hub mutations.
- [ ] 2. `py -m unittest tests.test_supervisor` green; full suite.
- [ ] 3. Commit: `feat: validate supervisor decisions over bounded saved evidence (plan 44 backend T3)`.

**Drift guard:** do not reuse handoff.digest's character truncation: this contract is UTF-8 bytes and whole facts.
