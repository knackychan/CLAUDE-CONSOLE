# Task 2: the planner judges drift in a build; the design step adopts a sub-plan file (D3, D7)

Files: `console/planner.py`, `console/prep.py`, `console/server.py` (`start_prep`, `_prep_job`),
`dotclaude/console/kinds/planner.md`, `dotclaude/console/kinds/design.md`, `tests/fake_claude.py`,
`tests/test_planner.py`, `tests/test_prep.py`, `tests/test_kinds.py`.
Commit boundary: `feat: the planner judges drift from a build context; the design step adopts a sub-plan (plan 53 Task 2)`.
Independent of Task 1: `card["build"]` is a plain dict whose shape README 4.6 fixes; Task 3 builds it with
`build.context`.

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
      lines.append("Judge drift (the rule in your kind file): does this sub-plan still fit the code the done "
                   "sub-plans left and the goal?")
      return "\n".join(lines)
  ```

- `run(...)`: the returned dict gains `"drift": fields.get("drift") or ""` and `"drift_note": redact.clip(" ".join(
  (fields.get("drift_note") or "").split()), NOTE_MAX)`; `_failed` gives both as `""`. Nothing in `run` reads the
  build: the prompt carries it.

## `console/prep.py`

- `run_prep(cfg, folder, project_dir, raw, exe, prep_id="", build=None)`: `build` (a README 4.6 dict or None) is
  passed to `planner.run` inside the card argument (`{"raw": raw, "fields": fields, "route": route, "build": build}`)
  and saved on the card as `card["build"] = build` (absent when None, so a card from before this task loads as
  today). `card["planner"]` gains `"drift"` and `"drift_note"`; in a build a missing drift word is filled here:
  `if build and not plan["drift"]: plan["drift"], plan["drift_note"] = "none", "the planner did not judge drift"`.
- `prep.summary(card)` (task["prep"]) gains `"drift": (card.get("planner") or {}).get("drift", "")` and
  `"drift_note"`, so the task row and the finish card can show them without the card file.

## `console/server.py`

- `Hub.start_prep(project_dir, raw, files=(), build=None) -> str` and `_prep_job(job, project_dir, raw, note="",
  build=None)`: `build` rides to `prep.run_prep`. `POST /api/prep` never passes one (a typed prompt has no build;
  the body key is not read). Task 3's tick is the only caller with a build.

## Kind files (Fred copies them to `~/.claude/console/kinds/` with the Models page's Reset to repo copy)

`dotclaude/console/kinds/planner.md`, a new paragraph before "You never change the route":

> In a build (the card ends with a Build context section), two more rules. First, the list always starts with one
> design step whose goal is `Adopt <this sub-plan file>: review it against the repo and write the plan from it; every
> departure goes under Decisions`, then the code steps that file calls for; a scout before the design step only when
> the file names no files at all. Second, judge drift and answer `drift` and `drift_note`: `none` when this sub-plan
> still fits the code the done sub-plans left and the goal file; `minor` when it needs small edits (name them in
> `drift_note`: the file, the line, the change) and the task can go on; `major` when the remaining sub-plans no longer
> fit the code or the goal (say in `drift_note` what must change before any of them runs). You never edit a sub-plan
> file or the goal file.

`dotclaude/console/kinds/design.md`, a new paragraph after "Read what the plan needs ... the plan is your final
message." (D7):

> When the task names a sub-plan file to adopt (a build), that file is the draft of your plan: read it first, then
> the code it names. Keep its intent and its order; rewrite it into the shape below with the final code where the
> file only describes; close every fork it leaves open; and name every departure from the file under Decisions as
> `Departs from <file>: <what and why>`. Where the file no longer matches the code, follow the code and say so there.
> Do not shorten the file's scope, and do not add the work of a later sub-plan.

`tests/test_kinds.py`: the two seed files carry the new sentences (`"Adopt "` in planner.md, `"sub-plan file to
adopt"` in design.md) and still start with their `# name` line.

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
  block: the done lines, the carried question, the judge line; without `build` the prompt is byte-identical to today's.
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
- `test_build_card_plans_a_design_step_first`: with a build context the fake planner's list is scout, design, code
  and `card["steps"]` is scout, design, code, verify.
