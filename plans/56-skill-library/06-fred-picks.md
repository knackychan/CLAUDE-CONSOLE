# Task 6: Fred's own pick, on a Prep step row and on Add next step

> Contract: [README.md](README.md) 3.4 (`resolve`'s `fred`), 3.10. Decision D6 (his pick ignores `kinds` and may name an
> unindexed skill). BRAINSTORM 14.4 item 4.
> Backend only: the request fields, their checks, what is stored and the preview's preset. The multi-selects are
> Task 8's contract. Fred picks at creation; a planned step's skills are not editable afterwards (not in this plan).

**Files**
- Modify: `console/server.py` (`Hub.skills_check`, `Handler._task_new`, `Hub.create_task`, `Hub.preview_next`,
  `Hub._next_package`, `Hub.request_next`)
- Modify: `tests/test_server.py`, `tests/test_task_messages.py` (the Add next step tests live in the first)

Commit boundary: `feat: Fred picks the skills of a step when he starts a task or adds a step (plan 56 T6)`.

## 6.1 Code

`Hub.skills_check(names) -> (list, why)`: `names` must be a list (else `(None, "skills must be a list of names")`); each
item a string; deduplicated in order; every name must be a `hand` row of `self.skill_registry()` (the row exists, its
body is readable, no marker line); the first failure returns `(None, "<name>: <the row's why or 'unknown skill'>")`.
`[]` is valid and means "none". A name that is only `hand` (unindexed, or an invalid entry) is accepted (D6).

`Handler._task_new`: in the existing per-step loop (the one that calls `rung_ok`), when `"skills" in item`:
`names, why = self.hub.skills_check(item["skills"])`; a `why` returns `self._error(400, f"step {n}: skills: {why}")`.
Nothing is created before every step passed.

`Hub.create_task(card, steps, ...)`: in the existing loop that puts Fred's rung picks back
(`for item, step in zip(shown, [p for p in planned if p["kind"] in tasks.PREP_KINDS])`), add: `if "skills" in item:`
`names, why = self.skills_check(item["skills"])`; a `why` raises `runs.RunError("skills: " + why)` before anything is
saved (the route has already refused it with a 400; this guards other callers); else `step["skills_in"] = {"fred":
names}` (the checked, deduplicated list). The auto-inserted verify has no row on the card and takes the code's pick.
`tasks.plan_steps` is unchanged.

`Hub.preview_next(request)` (after `route` is known, before `_next_package`): build the hypothetical step `{"n": len(task
["steps"]) + 1, "kind": kind, "goal": instructions.strip(), "source_step": source["n"]}`; `reg = self.skill_registry()`;
`vocab = skills.vocabulary(reg)`; `tags, files = skills.inputs(self.folder, task, hyp, vocab)`; if the request has
`skills` (not None), `names, why = self.skills_check(request["skills"])` and a `why` returns `400, {"error":
"skills: " + why}`; then `res = skills.resolve(reg, kind, tags, files, fred=names_or_None)`. The answer gains
`"skills": {"names": res["names"], "by": res["by"], "tags": tags, "files": len(files), "dropped": res["dropped"]}`.
Nothing is read from a skill body, nothing is written, nothing starts.

`_next_package(..., skills=None)`: when `skills` is not None, the canonical JSON of the validated list
(`json.dumps(list, ensure_ascii=False)`) is added to what the `revision` hashes; with `None` the revision is exactly
today's. Both `preview_next` and `request_next` pass the same checked list.

`Hub.request_next(request, origin)`: the signed `payload` adds `"skills"` only when `request.get("skills")` is not None
(README 3.11); for `origin == "fred"` and a non-None list, after `tasks.append_step`: `step["skills_in"] = {"fred":
names}` (an empty list is stored, it means "none"); for `origin == "supervisor"` Task 5 stores `{"supervisor": [...]}`.
`request_next` re-runs `skills_check` itself (the body is untrusted) and returns `400, {"error": "skills: ..."}`.

The Board and the window never see a skill body here; `skills.md` appears when the step starts (Task 3).

## 6.2 Tests first (red before the code)

`tests/test_server.py` (scratch library from the golden fixture, `Hub.user_home` in a temp dir, fake claude)
- `test_skills_check_table`: `[]` ok; `["ui-ux-review", "ui-ux-review"]` -> one; `["unindexed"]` ok (D6);
  `["ghost"]` -> `ghost: unknown skill`; `["marker-skill"]` -> `marker-skill: marker line: END HANDOFF`; `["no-folder"]`
  -> `no-folder: no SKILL.md`; `"ui-ux-review"`, `[3]`, `None` -> the list errors.
- `test_start_with_fred_picks_stores_them_and_the_step_obeys`: `POST /api/task` with step rows `[{kind: "code", goal,
  skills: ["unindexed"]}, {kind: "scout", goal, skills: []}]`: the planned steps hold `skills_in == {"fred":
  ["unindexed"]}` and `{"fred": []}`; step 1 starts with `skills == ["unindexed"]`, `skills_by == "fred"` and no
  `handoff-quality`; step 2 starts with no skills at all, no `skills.md`, and still the `--disable-slash-commands` limit
  (an empty Fred pick stays empty, even for an `always` skill). A Fred pick of `ui-ux-review` on a `scout` step is kept
  (kinds are ignored, D6).
- `test_start_with_a_bad_pick_is_a_400_and_starts_nothing`: the five failures above, each `400`, message `step 1:
  skills: ...`; no task, no folder, no run, the Prep card still there.
- `test_start_without_a_skills_key_is_unchanged`: the same body without `skills` gives steps with no `skills_in`.
- `test_next_preview_returns_the_codes_preset`: a done source whose saved touched files are `web/app.js` and
  instructions `polish the web page`: `skills.names` equals `resolve(...)`'s, `by == "code"`, `tags` holds `web`,
  `files == 1`; `GET`-style repeated calls start nothing and write nothing (task.json bytes unchanged).
- `test_next_preview_with_a_fred_pick_and_a_bad_one`: `skills: ["unindexed"]` -> `by == "fred"`, names `["unindexed"]`;
  `skills: ["ghost"]` -> 400 `skills: ghost: unknown skill`.
- `test_next_revision_covers_the_pick_only_when_present`: the same request with and without `skills`, and with two
  different lists, gives three revisions where the two without a list equal today's value (pinned from a request with
  no `skills` key); a request whose `revision` came from a different list is 409 `This step changed`.
- `test_next_request_stores_the_pick_and_is_idempotent`: `skills_in == {"fred": [...]}` on the new step; the same
  `request_id` and body returns the same step; the same id with a different list is 409 `request_id was already used
  with different content`; an empty list is stored as `{"fred": []}`.
- `test_next_step_started_with_a_pick_records_it`: the step's `skills_by == "fred"`, `received.md` carries the manifest
  once (Task 3's manual-step rule), the stream prompt holds the picked bodies.

## 6.3 Steps and acceptance

- [ ] 1. Write the tests; run them red.
- [ ] 2. `skills_check`, `_task_new` and `create_task`, then `preview_next`, `_next_package`, `request_next`. Focused
      tests green.
- [ ] 3. Full suite green; commit with the message above.
