# Task 4: where tags come from, Prep and the design step

> Contract: [README.md](README.md) 3.5 (tags), 3.12 item 4. BRAINSTORM 14.4 item 2.
> Tags are words from a fixed vocabulary: the base words plus the tags of the library's ok rows. They only matter to
> `skills.pick`; an unknown word matches nothing. The vocabulary is offered to Prep and to the design step **only when
> the library has a skill that uses tags**, so an empty library or one with only `always` skills adds not one token.

**Files**
- Modify: `console/skills.py` (`uses_tags`, `tags_rule`, `clean_tags`)
- Modify: `console/prep.py` (`SCHEMA` gains `tags`, `parse_output`, `build_prompt(..., extra="")`, `run_prep(..., extra="")`)
- Modify: `console/server.py` (the Prep job call at `prep.run_prep(...)`, `Hub.create_task`, the design branch of `start_step`)
- Modify: `tests/test_skills.py`, `tests/test_prep.py`, `tests/test_plan.py`, `tests/test_server.py`

`dotclaude/console/kinds/*.md` are **not** edited: the rules below are appended by code, so a kind file Fred already
edited gets them without a Reset (README 3.11).

Commit boundary: `feat: Prep and the design step name the tags a step is about (plan 56 T4)`.

## 4.1 Code

`console/skills.py`
```python
def uses_tags(reg) -> bool              # True when at least one ok row has a non-empty `tags`
def clean_tags(raw, vocab=None) -> list # lower-cased, TAG_RE-valid strings, deduplicated, first-seen order; only those in
                                        # `vocab` when it is given; [] for a non-list. Never raises.
def tags_rule(kind: str, vocab) -> str  # "" unless kind in ("prep", "design") and vocab; else the text below
```

`tags_rule("prep", vocab)`:
`Also return "tags": the words from this list that the work touches, each only if it truly applies, or an empty list.
The service uses them to pick the skills a step loads. Words: <vocab joined by ", ">.`

`tags_rule("design", vocab)`:
`Skill tags: as the first line under each "### Step N: <kind>" heading, and as the first line inside each SUBPLAN
block, write one line "Tags: a, b" using only these words: <vocab joined by ", ">. Write "Tags: none" when none applies.
The service reads this line to pick the skills the step loads; it is not one of the plan's checked headings.`

(The texts use plain quotes, no em-dash, no `$`.)

`console/prep.py`
- `SCHEMA["properties"]["tags"] = {"type": "array", "items": {"type": "string"}}`; `required` is unchanged (Haiku leaves
  optional keys out on long answers, `troubleshooting/prep-structured-output.md`).
- `parse_output`: after the `TEXT_KEYS` defaults, `fields["tags"] = clean_tags`-equivalent inline (a list of lower-case
  `[a-z0-9-]` strings, else `[]`). `prep.py` does not import `skills` (README 3.1): the cleaning is four lines here and
  `skills.clean_tags` filters again at the task.
- `build_prompt(raw, misses=(), days=0, you="The user", text=None, extra="")` appends `"\n\n" + extra` when `extra` is
  non-empty; with `extra=""` the result is byte-identical to today's. `run_prep(..., prep_id="", extra="")` passes it,
  so `role.md` (`sent`) shows it.

`console/server.py`
- The Prep job (`prep.run_prep(self.cfg, self.folder, project_dir, raw + note, self.runs.exe, job)`) gains
  `extra=skills.tags_rule("prep", skills.vocabulary(reg)) if skills.uses_tags(reg) else ""` with `reg =
  self.skill_registry()`.
- `Hub.create_task`: after `tasks.new_task(...)`, `tags = skills.clean_tags((card.get("fields") or {}).get("tags"))`;
  `if tags: task["tags"] = tags`. Not in `TASK_KEYS`; read with `.get`. A raw run and a chat task have none.
- `Hub.start_step`, design branch, right after `role = plan.design_text(...)`: when `skills.uses_tags(reg)`,
  `role = role + "\n\n" + skills.tags_rule("design", skills.vocabulary(reg))`. The rendered role (with the rule) is what
  `role.md` records.

`console/plan.py` is not edited. `plan.check` reads headings by exact line and tolerates the extra `Tags:` line (a test
pins that). `skills.inputs` (Task 2) reads the line with `tags_of`.

## 4.2 Tests first (red before the code)

`tests/test_skills.py`
- `test_uses_tags_and_clean_tags`: `uses_tags` is false for an empty registry, for one `always` row without tags, and
  for a trap row that has tags but is not ok; true for an ok row with tags. `clean_tags(["Web", "web", "x y", 3, "UI-UX"])`
  -> `["web", "ui-ux"]`; with a vocab only those in it; `None` and a string -> `[]`.
- `test_tags_rule_texts`: both rules name every vocabulary word, contain no `$`, no U+2014; `tags_rule("prep", [])` and
  `tags_rule("verify", vocab)` are `""`.

`tests/test_prep.py`
- `test_schema_tags_are_optional_and_parse_output_fills_a_list`: `required` still `["goal", "route"]`; a missing key,
  `null`, a string, `["Web", 3, "ui-ux"]` give `[]`, `[]`, `[]`, `["web", "ui-ux"]` in `fields["tags"]`.
- `test_extra_is_appended_after_the_template_only_when_given`: `extra=""` equals the old output byte for byte; with a
  rule it is the old output plus a blank line and the rule.
- `test_run_prep_sends_the_extra_and_role_md_shows_it` (fake claude, scratch home): the saved `00-prep/role.md` ends with
  the rule.

`tests/test_plan.py`
- `test_tags_lines_do_not_change_the_plan_check`: a valid single plan and a valid split plan, each with `Tags:` lines
  under every `### Step N` or first in every SUBPLAN block, pass `plan.check` exactly as without them; `step_section`
  keeps the line; `Tags: none` too.

`tests/test_server.py`
- `test_prep_gets_the_tag_rule_only_with_a_tagged_library`: scratch library with only `handoff-quality`: the prompt Prep
  ran (captured by the fake claude or `role.md`) is byte-identical to today's; add `ui-ux-review`: the rule with the
  vocabulary is appended.
- `test_design_step_role_carries_the_tag_rule`: same condition; `role.md` of the design step ends with the rule; a
  non-design step's role does not.
- `test_create_task_saves_the_cards_tags`: a card whose `fields.tags` is `["Web", "x y"]` -> `task["tags"] == ["web"]`;
  none for a card without tags; the key survives `tasks.save` and `tasks.load_all`.
- `test_tags_reach_the_pick_end_to_end`: library `handoff-quality` + `ui-ux-review`; a code step of a task whose tags
  are `["ui-ux"]` starts with both skills (`skills_by == "code"`); the same step of a task with no tags starts with
  `handoff-quality` only; a design step's plan `Tags: web` line picks it for that step's writer (`### Step 2: code`).

## 4.3 Steps and acceptance

- [ ] 1. Write the tests; run them red.
- [ ] 2. `skills` helpers, then `prep`, then the three server edits. Focused tests green.
- [ ] 3. Full suite green; commit with the message above. `tests/golden_prep.py` is Fred's live Prep run: Task 9 adds
      `tags` to what it prints; it is not part of the automated suite.
