# Plan 47 - A planner pass reviews every Prep card and writes its step list

Status: code done 2026-10-19 (steps 1-5, one commit each; 1046 tests OK), live check open. Written 2026-10-19 from Fred's brief ("a planner that reviews the prep on Opus/Astra to be sure we aim at the
right scope"). D1-D3 are Fred's answers (2026-10-19); D4-D6 are defaults written in, change them before building if
wrong.

## 1. Finding

Prep is one Haiku call (`prep_model`, `prep.run_prep`) that scouts, rewrites the prompt, picks the route AND proposes
the steps. The step list is the weakest output: it comes from the cheapest model, in the same breath as the
scouting, and nothing reviews its scope. Plan 46 patches only hard cards, by inserting a design step in code
(`tasks.hard_steps`).

## 2. Decisions

| # | Question | Answer |
|---|---|---|
| D1 | When it runs | Every Prep card (Fred). |
| D2 | What it is | Changed by Fred, 2026-10-19: one bounded `claude -p` like Prep's own, with read-only tools (Read, Grep, Glob), so it can check the repo before it fixes the steps. Never a task session, never writes, never edits the project; it returns the step list as JSON and `run_prep` saves it in the card. |
| D3 | Relation to plan 46 | Fred, 2026-10-19: the planner sets the steps, a design step it planned stays in the list ahead of the code steps, and `tasks.hard_steps` is removed (no fallback). Plan 46 keeps `NO_HARD_KINDS` (D4) and `_route_for`; it loses `hard_steps`, `READ_FIRST`, `DESIGN_GOAL`, `CODE_GOAL` and the `Hub._run` hard-card branch. |
| D4 | Model | `planner_model`, default `opus`, Claude alias only (`CLAUDE_ONLY`): the pass runs the Claude CLI, so Astra cannot be the planner. |
| D5 | Failure | Any failure (timeout, no JSON, bad shape, budget, opus pace or limit hold) keeps Prep's own steps through plain `plan_steps`, with `card["planner"]["error"]` set and shown on the card. Never raises, never blocks the card. A hard card whose planner failed has only Prep's list; the card shows the error so Fred adds the design step by hand. |
| D6 | Cost cap | `planner_max_cost` default 0.50 USD (`--max-budget-usd`) and `--max-turns 12`; the cost is added to `card["cost"]`. |

## 3. What the pass does

Input (stdin): the planner kind file, then the card as evidence: raw prompt, enhanced prompt (`prep.format_prompt`),
route, demand, scouting, and Prep's proposed steps. The pass runs in the project folder with Read, Grep and Glob
only, so it checks Prep's claims (do the files exist, is the change as small or as big as Prep says) and does not
trust the scouting blindly. It may fix, drop, reorder or add steps. If it cannot judge, it says so in `note` and
keeps Prep's steps.

Output schema (`planner.SCHEMA`), all required:

```python
{"scope": "ok" | "too_big" | "too_small" | "unclear",   # does the prompt ask for the right amount of work
 "note": str,                                           # one line for the card, why
 "steps": [{"kind": one of tasks.PREP_KINDS, "goal": str}]}
```

Rules in the kind file `planner.md`: a hard task (`reasoning: high`) starts with its reads, then one `design` step
(think tier, writes plan.md), then `code` steps on the write tier, never a code step before the design; an easy task
is one or two steps; no verify (plan_steps adds it); at most `task_max_steps`.

The planner never changes the route, the demand or the enhanced prompt. Fred edits those on the card as today. If
`scope` is `too_big` or `unclear`, the card shows `note` above the step list; Start is still Fred's.

## 4. Changes

0. `console/claude_cli.py`: `planner_command(exe, model, schema, max_cost)` = `prep_command` with `--effort medium`,
   `--max-turns 12` and `--max-budget-usd` (hooks, MCP and skills stay off, as for Prep).
1. `console/planner.py` (new, about 90 lines): `SCHEMA`, `build_prompt(card, you, text)`, `shape(fields)` (returns
   "" or the reason), `run(cfg, exe, project_dir, card, text) -> {"steps": list, "scope", "note", "cost", "model",
   "turns", "error"}`. `run` copies `prep.run_prep`'s subprocess call (cwd the project, stdin prompt, `planner_timeout_s`; the CLI JSON is
parsed as `prep.parse_output` does: `structured_output`, `total_cost_usd`, `num_turns`, `is_error`) and never raises;
steps pass through `tasks.plan_steps` and an empty result
   is the error "no valid steps". It shares no code with the supervisor.
2. `console/kinds.py`: append `"planner"` to `NAMES` (after `"supervisor"`); `dotclaude/console/kinds/planner.md`
   (first line `# planner`, slots `$You`, `$raw` not used; the card text is appended by `build_prompt`, untouched).
3. `console/paths.py` defaults: `planner_model: "opus"`, `planner_timeout_s: 120`, `planner_max_cost: 0.5`.
   `console/tuning.py`: add the three keys (group "passes": rung, s 10-600, usd 0.05-5) and `planner_model` to
   `CLAUDE_ONLY`.
4. `console/prep.py run_prep`: after the demand-rule block, before `card`:

```python
    plan = planner.run(cfg, exe, project_dir, {"raw": raw, "fields": fields, "route": route},
                       kinds.text(folder, "planner"))
    steps = tasks.plan_steps(plan["steps"] or fields.get("steps") or [], cfg["task_max_steps"])  # the only validator
```

   The `tasks.hard_steps(...)` call there is removed. A planner list is used as given (a design step it planned
   stays, none is added). `card["planner"] = {"model", "scope", "note", "cost", "turns", "error"}` and
   `card["cost"] = result["cost"] + (plan["cost"] or 0)`. `prep.summary` and `handoff_text` are unchanged.
   Remove plan 46's `hard_steps` here too: delete `tasks.hard_steps`, `READ_FIRST`, `DESIGN_GOAL`, `CODE_GOAL`
   (`console/tasks.py`) and the branch in `Hub._run` (`console/server.py`) that calls it, so a card with no steps
   runs as before plan 46 (one chat on its route). Keep `NO_HARD_KINDS` and the `_route_for` change (plan 46 D4).
   The `dotclaude/console/kinds/prep.md` line about a design step moves to `planner.md`.
5. `console/server.py`: the card route already returns the card whole; no new route. The Usage page counts a
   planner cost inside the prep cost (D6), so no second ledger.
6. `web/app.js`, `web/style.css`: on the Prep card, one muted line above the step list, `planner.note`, with the
   scope word as a tag only when it is not `ok`; the error text when set. Tokens and cell motif from
   `design/rework/locked/`, no new colors. No emojis, no em-dashes.

## 5. Tests (first)

- `tests/test_planner.py`: `shape` accepts a good object and rejects a bad scope, a non-list steps, an empty goal;
  `run` with a fake subprocess returns plan_steps-validated steps; a timeout, an `is_error` result or bad JSON gives `steps == []`, `error` set,
  cost kept (None stays None); no `exe` gives the "claude.exe not found" error with cost 0.
- `tests/test_prep.py::test_planner_steps_replace_prep_steps`: fake Prep proposes `[code]`, fake planner returns
  `[scout, design, code]`; card steps are scout, design, code, verify.
- `tests/test_prep.py::test_planner_failure_keeps_prep_steps`: planner error; card steps are Prep's through
  plan_steps, `card["planner"]["error"]` is set, `run_prep` does not raise.
- `tests/test_prep.py::test_planner_design_step_is_kept_and_not_doubled`: planner returns `[scout, design, code]`
  on a hard card; steps are scout, design, code, verify with exactly one design.
- `tests/test_prep.py::test_planner_cost_is_added`: card cost is prep plus planner.
- `tests/test_kinds.py`: `NAMES` contains planner; the seed file exists and starts with `# planner`.
- `tests/test_tuning.py`: the three keys validate; `planner_model` rejects a non-Claude rung.
- Delete plan 46's `test_hard_steps_adds_design_and_code` (`tests/test_tasks.py`), `test_hard_card_gets_design_and_code` (`tests/test_prep.py`) and `test_hard_card_never_runs_as_a_chat` (`tests/test_server.py`); keep `test_step_route_code_never_takes_a_hard_only_rung` and `test_code_step_of_a_hard_task_is_not_routed_to_opus`.

## 6. Order and checks

1. Tests red. 2. `planner.py` + kind file + `kinds.NAMES`. 3. `paths.py`, `tuning.py`. 4. `run_prep`. 5. Card UI
(`node --check web/app.js`). One commit per step, stage only this plan's lines (another chat has plan 46 edits open
in `prep.py`, `tasks.py`, `server.py`, `PLAN.md`; build on top of them, never revert them). Run
`py -m unittest discover -s tests`.

Live check (Fred): send a vague, oversized prompt; the card shows scope `too_big` or `unclear` with a one-line note
and a step list that differs from Prep's guess; the card cost is a few cents higher; a hard prompt lists scout,
design, code, verify.

## 7. Not done here

- The planner reads but never writes; it is not a task session and has no resume.
- No Astra planner (the pass is Claude CLI only).
- Easy cards still pay one Opus pass (D1). If the Usage page shows it is not worth it, narrow the trigger to
  `reasoning` medium and high in one line of `run_prep`.
- The supervisor's `proposed` steps come from the same card steps, so they inherit the planner's list; nothing in
  plan 44 changes.
