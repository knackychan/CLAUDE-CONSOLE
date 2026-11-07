# Task 5: the supervisor may add skills to a next step

> Contract: [README.md](README.md) 3.4 (`resolve`'s `add`), 3.9. BRAINSTORM 14.4 item 3 and 14.6.
> Plan 44's README section 1 says the backend rejects a `skills` field until a registry exists. This task lifts that for
> `add_next_step` only. The model's JSON stays untrusted: `supervisor.shape` checks its form, the Hub checks every name
> against the live registry, and a wrong name is dropped and logged, never fatal.

**Files**
- Modify: `console/supervisor.py` (`SCHEMA`, `_OPTIONAL`, `_FIELDS`, `shape`, `clean_skills`, `digest`)
- Modify: `console/server.py` (`_sup_snapshot`, `_sup_replay_snapshot`, `_supervisor_dispatch`, `request_next`)
- Modify: `plans/44-supervisor/README.md` (one anchored note, below)
- Modify: `tests/test_supervisor.py`, `tests/test_supervisor_server.py`, `tests/test_supervisor_replay.py`

Commit boundary: `feat: the supervisor may name skills for the next step it adds (plan 56 T5)`.

## 5.1 Code

`console/supervisor.py`
- `SCHEMA["properties"]["skills"] = {"type": "array", "items": {"type": "string"}}` (not required);
  `_OPTIONAL["skills"] = list`; `_FIELDS["add_next_step"]` gains `"skills"`. `run()` already drops an optional field
  that is not the answered decision's own, so a `retry` carrying `skills` loses it before `shape`.
- `shape`: for `skills` the existing loop checks the type and that the key belongs to the decision (`skills is not a
  field of <decision>` for any other); then every item must be a string that fullmatches `skills.NAME_RE` else
  `skills must be a list of skill names`. There is no count limit (D18). `supervisor.py` imports `skills` for `NAME_RE`
  only.
- `check` is unchanged: `skills` never refuses a decision (BRAINSTORM 14.4: the rest is kept).
- ```python
  def clean_skills(raw, kind: str, rows) -> tuple
      """(kept, dropped) for a decision's `skills` against registry rows (a dict name -> row, or the list):
      names deduplicated in order; a name is kept when its row is ok and allows `kind` (kinds empty = any); dropped
      with why `unknown skill`, the row's own why, or `not for <kind> steps`. Pure. Never raises."""
  ```
  It applies exactly `resolve`'s `add` rule (README 3.4); the two share one helper in `skills.py`
  (`skills.admit(row, kind)`), so they cannot drift.
- `digest(home, task, context)`: `context["skills"]` is a list of `{"name", "description", "kinds"}` for the ok rows
  (the Hub builds it). When non-empty, one more block after the plan view and before "Open questions":
  `Skills available (an add_next_step decision may list names from here in "skills"; leave it out when none fit):`
  then `- <name> [<kinds joined by ", " or "any">]: <description clipped to 300 characters>`. It is built whole and
  goes through the existing byte budget: when it does not fit it is replaced by the existing `omitted (...)` line or
  dropped, never cut. The mandatory head, step table and `Allowed now` are unchanged.
- `revision` is **not** changed: the registry is not task evidence. A library edit changes the digest text, so the
  prompt fingerprint (R3) changes while the evidence revision stays equal, which is what R3 exists to show.

`console/server.py`
- `_sup_snapshot` and `_sup_replay_snapshot` add `"skills": self._sup_skill_rows()` to `context`, where
  `_sup_skill_rows()` = `[{"name", "description" (masked), "kinds"} for ok rows of self.skill_registry()]`. The replay
  builds the same block, so a replay of a pass reproduces its prompt.
- `_supervisor_dispatch`, where `req` is built for `add_next_step`: `kept, dropped = supervisor.clean_skills(
  decision.get("skills"), decision["kind"], {r["name"]: r for r in self.skill_registry()["skills"]})`; when `kept`,
  `req["skills"] = kept`. The dispatching `intent` and the outcome record gain `"skills": kept` and `"skills_dropped":
  dropped` (`[{"name", "why"}]`) in the existing `_sup_record` payloads (masked like every audit line). Auto mode and
  Fred's Approve take the same path. `auto_reason` and the caps are unchanged (D18: no skill cap).
- `request_next(request, origin)`: the signed `payload` adds `"skills"` **only when `request.get("skills")` is not
  None** (README 3.11, so an old request id still matches). After `tasks.append_step`, `if origin == "supervisor" and
  request.get("skills")`: `step["skills_in"] = {"supervisor": [names]}` (each a `NAME_RE` string, deduplicated); for
  `origin == "fred"` Task 6 stores `{"fred": [...]}`. A request with both keeps both keys.

`plans/44-supervisor/README.md`: after the paragraph that says "This backend rejects a `skills` decision field until that
separately planned registry exists. ...", add the note (anchored on that sentence, one paragraph):

`Note (plan 56 Task 5): the registry now exists (plans/56-skill-library/). `skills` is a field of `add_next_step` only,
shaped by `supervisor.shape` and cleaned against the live registry by `supervisor.clean_skills`; every other decision
still refuses it. The rest of this plan stands.`

## 5.2 Tests first (red before the code)

`tests/test_supervisor.py`
- `ShapeTest.test_skills_is_a_field_of_add_next_step_only`: a valid `add_next_step` with `skills: ["a", "b"]` and `[]`
  passes `shape` and `check`; `skills` on `retry`, `keep`, `finish`, `escalate_to_fred` and `wait` fails with `skills is
  not a field of <decision>`; `skills: "a"`, `skills: [3]`, `skills: ["Bad Name"]`, `skills: ["../x"]` fail with
  `skills must be a list of skill names`; 500 valid names pass (D18). The earlier case in
  `test_unknown_fields_wrong_types_and_model_ids_refused` that expected any `skills` to be refused is changed to these.
- `test_run_drops_skills_from_another_decision` (fake `compact._ask`): an answer `{"decision": "retry", ..., "skills":
  [...]}` reaches `check` without the field.
- `CleanSkillsTest.test_table`: against the golden registry of README section 4: `["ui-ux-review", "test-writing"]` for a
  `code` step keeps both; for `scout` drops `ui-ux-review` with `not for scout steps`; `["unindexed", "no-folder",
  "marker-skill", "bad-kinds", "ghost"]` drop with `not in index.json`, `no SKILL.md`, `marker line: END HANDOFF`,
  `index: kinds: unknown kind reviewer`, `unknown skill`; duplicates collapse; input not mutated; `None` -> `([], [])`.
- `DigestTest.test_skills_block`: with `context["skills"]` the block appears after the plan view with the exact title and
  one line per skill, descriptions clipped to 300 characters; with a tight budget it is omitted whole (the `omitted`
  line) and the mandatory blocks are unchanged; without `skills` the digest is byte-identical to today's.
- `test_revision_ignores_the_library_but_the_prompt_hash_changes`: same task, a skill added: `revision` equal,
  `prompt_hash` different (R3).

`tests/test_supervisor_server.py`
- `test_approve_carries_kept_skills_and_logs_the_dropped`: a suggestion `add_next_step` code with `skills:
  ["ui-ux-review", "ghost"]`; Approve: `request_next` got `skills == ["ui-ux-review"]`, the new step has
  `skills_in == {"supervisor": ["ui-ux-review"]}`, the dispatching and outcome lines in `supervisor.jsonl` carry
  `skills` and `skills_dropped == [{"name": "ghost", "why": "unknown skill"}]`; the step then starts with
  `skills_by == "supervisor"` when the name was not already picked by code, `"code"` when it was.
- `test_auto_mode_dispatches_with_skills_inside_the_same_caps`: auto mode: same result; `supervisor_max_auto_steps` still
  counts one slot; no skill-specific refusal exists.
- `test_old_request_ids_still_match`: a step saved by an earlier build (`request_hash` without `skills`) and the same
  request replayed: 200 with the prior step, not 409.
- `test_a_request_without_skills_is_unchanged`: `step` has no `skills_in`.

`tests/test_supervisor_replay.py`
- `test_replay_prompt_includes_the_same_skills_block`: the replay snapshot's prompt equals the live snapshot's for the
  same task and library.

## 5.3 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_supervisor tests.test_supervisor_server
      tests.test_supervisor_replay` red.
- [ ] 2. `supervisor.py` (shape, clean_skills, digest), then the Hub (snapshots, dispatch, request_next), then the plan
      44 note. Focused tests green.
- [ ] 3. Full suite green; commit with the message above.
