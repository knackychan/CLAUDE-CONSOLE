# Task 2: the planner judges drift in a build; the design step adopts a sub-plan file (D3, D7)

Files: `console/planner.py`, `console/prep.py` (`run_prep`, `build_guard`, `summary`), `console/server.py` (`start_prep`, `_prep_job`),
`dotclaude/console/kinds/planner.md`, `dotclaude/console/kinds/design.md`, `tests/fake_claude.py`,
`tests/test_planner.py`, `tests/test_prep.py`, `tests/test_kinds.py`.
Commit boundary: `feat: the planner judges drift from a build context; the design step adopts a sub-plan (plan 53 Task 2)`.
Independent of Task 1: `card["build"]` is a plain dict whose shape README 4.6 fixes; Task 3 builds it with
`build.context`. Checked against HEAD `9b6f988`: `prep.run_prep(cfg, folder, project_dir, raw, exe, prep_id="")`,
`planner.run(cfg, exe, project_dir, card, text)`, `planner.build_prompt(card, you, text)`, `planner.NOTE_MAX` (300),
`Hub.start_prep(project_dir, raw, files=())` and `Hub._prep_job(job, project_dir, raw, note="")` are as this task
describes; `card["planner"]` holds `model, scope, note, cost, turns, error`; `Hub._end_job` and `drop_prep` are unchanged.
The planner runs with `--max-turns 12` and `--max-budget-usd` `planner_max_cost` (0.5): a longer prompt that ends on
the budget is a planner error (README F19), not a drift word.

## `console/planner.py`

- `DRIFT = ["none", "minor", "major"]`. `SCHEMA["properties"]` gains `"drift": {"type": "string", "enum": DRIFT}` and
  `"drift_note": {"type": "string"}`; `required` stays `["scope", "note", "steps"]` (a pass outside a build answers as
  today; the CLI's structured output allows absent optional keys).
- `shape(fields)`: after the steps check, `if "drift" in fields and fields["drift"] not in DRIFT: return "drift is not
  one of none, minor, major"`; `if "drift_note" in fields and not isinstance(fields["drift_note"], str): return
  "drift_note is not text"`.
- `build_prompt(card, you, text)`: when `card.get("build")` is a dict, append after "Prep's proposed steps" the Build
  context block of README 4.6, built by `build_context_text(ctx)` (new, in this module so Task 1 is not imported):

  ```python
  def build_context_text(ctx: dict) -> str:
      lines = [f"Build context (sub-plan {ctx['n']} of {ctx['of']} of \"{ctx['title']}\"):",
               f"Goal file: {ctx['goal_file'] or '(none: the sub-plans are the goal)'}",
               f"This sub-plan: {ctx['file']}", "Done so far:"]
      lines += [f"- {d['n']} {d['title']}: {d['state']}" + (f"; files {', '.join(d['files'])}" if d.get("files") else "")
                for d in ctx.get("done") or []] or ["- (none: this is the first sub-plan)"]
      if ctx.get("questions"):
          lines.append("Open questions carried: " + " | ".join(ctx["questions"]))
      return "\n".join(lines)
  ```

  The block holds facts only. The instruction to judge drift is in the planner kind file (below), not here, so that
  deleting that one sentence on the Models page switches drift off with no code change (README 8.1).

- `run(...)`: the returned dict gains `"drift": fields.get("drift") or ""` and `"drift_note": redact.clip(" ".join(
  (fields.get("drift_note") or "").split()), NOTE_MAX)`; `_failed` gives both as `""`. Nothing in `run` reads the
  build: the prompt carries it.

## `console/prep.py`

- `run_prep(cfg, folder, project_dir, raw, exe, prep_id="", build=None)`: `build` (a README 4.6 dict or None) is
  passed to `planner.run` inside the card argument (`{"raw": raw, "fields": fields, "route": route, "build": build}`)
  and saved on the card as `card["build"] = build` (absent when None, so a card from before this task loads as
  today). `card["planner"]` gains `"drift"` and `"drift_note"`; in a build a missing drift word is filled here:
  `if build and not plan["drift"]: plan["drift"], plan["drift_note"] = "none", "the planner did not judge drift"`
  (only when `plan["error"]` is empty: a planner that failed is README F19, and the card keeps its error).
- `prep.build_guard(fields: dict, ctx: dict) -> None` (new, called by `run_prep` right after `parse_output` and before
  the card dict is built, only when `build` is given): prefixes `fields["goal"]` with `Sub-plan {n} of {of}
  ({file}): ` unless it already starts so, and appends to `fields["keep"]` (a new line when it is not empty) `Sub-plan
  file {file} is this task's whole scope (its Files, Actions, Tests and Done check): do not do the work of a later
  sub-plan and do not redo an earlier one.` The goal is the first labelled line of `format_prompt`, so the file is
  inside the first 600 characters (`tasks.PROMPT_GOAL_MAX`) that every later step prompt carries; Keep is read by Fred
  on the card. Prep's own wording stays. No other field changes.
- `prep.summary(card)` (task["prep"]) gains `"drift": (card.get("planner") or {}).get("drift", "")` and
  `"drift_note"`, so the task row and the finish card can show them without the card file.

## `console/server.py`

- `Hub.start_prep(project_dir, raw, files=(), build=None) -> str` and `_prep_job(job, project_dir, raw, note="",
  build=None)`: `build` rides to `prep.run_prep`. `POST /api/prep` never passes one (a typed prompt has no build;
  the body key is not read). Task 3's tick is the only caller with a build.

## Kind files (Fred copies them to `~/.claude/console/kinds/` with the Models page's Reset to repo copy)

`dotclaude/console/kinds/planner.md`, a new paragraph before "You never change the route":

> In a build (the card ends with a Build context section), two more rules. They are separate paragraphs on purpose:
> the Console's owner can delete either one on the Models page to switch that decision off (README 8.1).
>
> Adopt: the list always starts with one design step whose goal is `Adopt <this sub-plan file>: review it against the
> repo and write the plan from it; every departure goes under Decisions`, then the code steps that file calls for; a
> scout before the design step only when the file names no files at all. (A sub-plan file here is one file of the
> build's folder, not the `## Sub-plans` split of a plan.)
>
> Drift: judge drift and answer `drift` and `drift_note`: `none` when this sub-plan still fits the code the done
> sub-plans left and the goal file; `minor` when it needs small edits (name them in `drift_note`: the file, the line,
> the change) and the task can go on; `major` when the remaining sub-plans no longer fit the code or the goal (say in
> `drift_note` what must change before any of them runs). You never edit a sub-plan file or the goal file.

`dotclaude/console/kinds/design.md`, a new paragraph after "Read what the plan needs ... the plan is your final
message." (D7):

> When the task names a sub-plan file to adopt (a build), that file is the draft of your plan: read it first, then
> the code it names. Keep its intent and its order; rewrite it into the shape below with the final code where the
> file only describes; close every fork it leaves open; and name every departure from the file under Decisions as
> `Departs from <file>: <what and why>`. Where the file no longer matches the code, follow the code and say so there.
> Do not shorten the file's scope, and do not add the work of a later sub-plan. The file is one file of the build's
> folder; it is not the `## Sub-plans` split described below, which is how you cut your own plan in parts.

`tests/test_kinds.py`: the two seed files carry the new sentences (`"Adopt "` and `"Drift: "` as separate paragraphs in
planner.md, `"sub-plan file to adopt"` and `"not the `## Sub-plans` split"` in design.md) and still start with their
`# name` line; deleting the `Drift: ` paragraph from the planner seed text leaves `"Adopt "` and the file otherwise
unchanged (the switch of README 8.1 works on one paragraph).

## `tests/fake_claude.py`

`planner(raw)`: `PLANNER-DRIFT-MINOR` answers `drift: minor, drift_note: "fake planner: 02 was skipped"`;
`PLANNER-DRIFT-MAJOR` answers `drift: major, drift_note: "fake planner: the queue moved"`; otherwise, when `"Build
context"` is in the request, `drift: none` and `drift_note: ""`; outside a build no drift keys at all (the schema
test). With `"Build context"` in the request and no PLANNER-DESIGN, the fake answers scout, design, code as
PLANNER-DESIGN does (the kind file's first rule), so a build task in the server tests runs a design step. The
docstring at the top of the file lists the two words.

## Tests (first, red)

`tests/test_planner.py`:

- `test_build_context_rides_in_the_prompt`: `build_prompt(dict(CARD, build=CTX), ...)` ends with the README 4.6
  block: the done lines and the carried question, and no instruction to judge drift (that is the kind file's);
  without `build` the prompt is byte-identical to today's.
- `test_shape_accepts_and_refuses_drift`: `drift: "minor"` accepted; `"big"` refused with the reason; a non-text note
  refused; no drift keys accepted.
- `test_run_returns_drift`: a GOOD answer with drift minor and a note -> `drift == "minor"`, the note clipped to
  NOTE_MAX; a failure -> `""` for both.

`tests/test_prep.py`:

- `test_prep_saves_the_build_context_and_drift`: `run_prep(..., build=CTX)` with the fake planner on
  `PLANNER-DRIFT-MAJOR` in the raw text: `card["build"] == CTX`, `card["planner"]["drift"] == "major"`, the note set,
  `prep.summary(card)["drift"] == "major"`; `run_prep` without `build`: no `build` key, `drift == ""`.
- `test_prep_fills_none_when_the_planner_did_not_judge`: a build card and a fake answer without drift keys ->
  `drift == "none"`, note `the planner did not judge drift`.
- `test_planner_error_in_a_build_keeps_its_error_and_fills_no_drift`: a build card with `PLANNER-FAIL` in the raw text ->
  `card["planner"]["error"]` non-empty, `drift == ""` (no fill), Prep's own steps stand.
- `test_prep_guards_the_goal_and_keep_of_a_build_card`: `run_prep(..., build=CTX)` with a fake Prep whose goal and keep
  are empty and then non-empty: `card["fields"]["goal"]` starts with `Sub-plan 3 of 9 (<file>): `, `card["prompt"]`'s
  first line carries it, `card["fields"]["keep"]` ends with the scope sentence and keeps Prep's own text before it; a
  second `build_guard` call changes nothing; a card made without `build` has neither.
- `test_build_card_plans_a_design_step_first`: with a build context the fake planner's list is scout, design, code
  and `card["steps"]` is scout, design, code, verify.
