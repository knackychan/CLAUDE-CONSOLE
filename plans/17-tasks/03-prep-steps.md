# Task 3: Prep proposes the steps

> Contract: [README.md](README.md) 3.4 and the design's section 6. Depends on Task 1 (`tasks.PREP_KINDS`,
> `tasks.plan_steps`, `tasks.RULES`).

**Files**
- Modify: `console/prep.py` (SCHEMA, `run_prep`)
- Modify: `console/prep_prompt.md` (a kinds block after the demand block; the type table unchanged)
- Modify: `tests/fake_claude.py` (`CHAIN`)
- Modify: `tests/test_prep.py`, `tests/test_tasks.py` (`test_kinds_table_matches_prompt`)

## `console/prep.py`

- `SCHEMA["properties"]["steps"]`: `{"type": "array", "items": {"type": "object", "properties": {"kind":
  {"type": "string", "enum": tasks.PREP_KINDS}, "goal": {"type": "string"}}, "required": ["kind", "goal"]}}`.
  Not in `required` (a one-step task returns `[]` or leaves it out; the prompt still says to always write the
  key, as it does for `question`, so the structured-output retries stay rare: see
  `troubleshooting/prep-structured-output.md`).
- `run_prep`: after the demand rule, `card["steps"] = tasks.plan_steps(fields.get("steps") or [],
  cfg["task_max_steps"])`. The card is saved with it. `card["demand"] = {"reasoning": route["reasoning"],
  "volume": route["volume"]}` (the task copies it).
- `parse_output` is unchanged (`steps` is optional and validated by `plan_steps`).

## `console/prep_prompt.md`

After the demand block and before `Fields:`, add (final text):

```text
Also split the request into steps when it has more than one kind of work, in `steps` (at most 5; an empty list
when one run should do it all). Each step is one separate run on its own model, so put the reading in a
scout step and the writing in a later one. Kinds and their models:

| kind | what the step does | model | effort |
|---|---|---|---|
| scout | find the files, functions and tests a task touches; quick research summaries | haiku | low |
| search | docs and web lookups, explain a library or an error | haiku | low |
| draft | a first draft of docs, plans or prose | haiku | low |
| proofread | proofreading and wording passes, no code | haiku | low |
| edit | a 1-2 file edit with a clear spec, a rename, a copy | haiku | low |
| code | a feature or fix with a clear spec, and its tests | sonnet | medium |
| document | an important document: a plan, a spec, user-facing docs | sonnet | medium |
| explain | an in-depth explanation across many files | sonnet | medium |
| debug | a failing test or a bug with no known cause | sonnet | high |
| test | run the checks and report, no edits | haiku | low |
| design | architecture, a novel problem, a critical decision, deep research | opus | high |

Do not add a verify step: the Console adds one after the last step that edits.
```

`Fields:` gains `steps (a list of {kind, goal}, or [])` and the output rules sentence gains `steps` in the list of
keys that are always present (`"steps": []` when there is nothing to split).

The type table above it is not changed: `tests/test_dotclaude.py::test_route_table_matches_prep` reads any row
whose first cell is a Prep type; none of the kinds is a Prep type (`search`, not `lookup`).

## `tests/fake_claude.py`

In `prep()`: `fields["steps"] = []` always; when `"CHAIN" in raw`:
`[{"kind": "scout", "goal": "find the add() callers"}, {"kind": "code", "goal": "fix add() and its test"}]`.
The docstring gains the `CHAIN` line.

## Tests

`tests/test_prep.py`:
- `test_schema_shape`: extend: `"steps"` in `properties`, not in `required`; its items require `kind` and `goal`;
  `kind` enum equals `tasks.PREP_KINDS`.
- `test_run_prep_returns_steps_and_appends_verify`: `run_prep(cfg, tmp, tmp, "CHAIN fix add", FAKE)` -> `card
  ["steps"]` kinds are `["scout", "code", "verify"]`, numbered 1..3; `card["demand"] == {"reasoning": "low",
  "volume": "low"}`; a plain request gives `card["steps"] == []`.
- `test_prompt_demands_every_key`: extend: `"steps": []` appears in the output rules.

`tests/test_tasks.py`:
- `test_kinds_table_matches_prompt`: parse the kinds table of `prep.PROMPT_FILE` (rows whose first cell is in
  `tasks.RULES`) and assert each row's model and effort equal `tasks.RULES[kind][:2]`, and that every kind of
  `tasks.PREP_KINDS` has a row.

## Steps

- [x] 1. Write the tests. Run: fail (no `steps` in the schema, no rows in the prompt, no `CHAIN`).
- [x] 2. `prep.py` schema and `run_prep`. `fake_claude.py` `CHAIN`. Run `tests.test_prep`: pass.
- [x] 3. `prep_prompt.md` block and the two sentences. Run `tests.test_tasks` and `tests.test_dotclaude`: pass.
- [x] 4. Whole suite OK. Commit: `feat: Prep proposes task steps; the Console appends the verify (plan 17 Task 3)`.

## Drift guards

- The type table and its five rows stay byte-for-byte; the kinds table is a second table below it.
- `plan_steps` is the only validator; `prep.py` does not check kinds itself.
- The fake claude's three default route fields and its other words (`THINK`, `BULK`, `BROKEN`, `SLOW`) stay.
