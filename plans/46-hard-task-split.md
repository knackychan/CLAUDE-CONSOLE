# Plan 46 - A hard task is a design step on Opus/Astra, then a code step on the write tier

Status: written 2026-10-19 from Fred's brief ("if the task is considered Hard, make a Prep + design/plan phase using
Opus/Astra, then a code task using the other for implementation, but Opus/Astra should not code"). Decisions D1-D4
are written for (a).

## 1. Finding

Task 20261019 "Implement all remaining Plan 1C": Prep rated it hard (`reasoning: high`) and proposed no steps, so
`Hub._run` made one chat (plan 29). The card's route is raised to opus/high by `routing.by_demand`, Auto then
balanced the opus pool and picked `codex:gpt-6-astra` (`server.py` `_run`, `fills.pool(..., hard=True)`), and that one
session planned, implemented and checked on the dearest rung.

Two more places already let a hard task code on Opus-rank rungs:
- `Hub._route_for` passes `hard=True` to every step of a task whose demand is `reasoning: high`, and `fills.pool`
  then adds the hard-only rungs of the write tier (`opus`) to a `code` step.
- A sub-plan part marked `hard` (plan 24) does the same for its write step.

The split itself already exists and needs no new machinery: the `design` kind (opus/high, read-only tools, think
tier: opus, Astra, kimi, glm, fable) writes `plan.md`; the `code` kind (sonnet/medium, write tier) implements it; the
Console adds a verify after the last edit step (`tasks.plan_steps`).

## 2. Decisions (recommended option first; the plan is written for it)

| # | Question | Options | Written for |
|---|---|---|---|
| D1 | What makes a task hard | (a) Prep's `route.reasoning == "high"` (the same test `by_demand` and `_route_for` use today) | (a) |
| D2 | What a hard card with no design step becomes | (a) code adds the missing steps: a `design` step after any leading scout/search steps, and a `code` step at the end when no step edits; (b) code refuses the card | (a) |
| D3 | Chat on a hard card | (a) never an error and never a chat: Run on a hard card starts its task (its steps, or the ones `hard_steps` adds); a Raw prompt (no card) is the way to force one model and is untouched (Fred, 2026-10-19: no 409s, the pipeline always makes steps); (b) refuse with a 409 | (a) |
| D4 | Who may not code | (a) `code` and `debug` steps never get a hard-only (Opus-rank) rung from the pool, hard task or hard sub-plan part alike; a pick, a pin, an Escalate floor or a Fix are Fred's explicit choices and still hold; (b) also refuse a pick of opus on a code step | (a) |

## 3. Changes

### 3.1 `console/tasks.py`: `hard_steps` and `NO_HARD_KINDS`

After `EDIT_KINDS`:

```python
NO_HARD_KINDS = ("code", "debug")  # plan 46 D4: a writer never takes a hard-only (Opus-rank) rung from the pool
READ_FIRST = ("scout", "search")
DESIGN_GOAL = "Design the change and write the plan the writers follow."
CODE_GOAL = "Implement the plan, with its tests."
```

After `plan_steps`:

```python
def hard_steps(proposed, demand, max_steps: int) -> list:
    """Plan 46: Prep's proposed steps for a hard task (demand reasoning high) with a design step in them and a
    step that edits after it: the missing design goes after the leading scout / search steps, the missing code
    step goes last. Not hard, or not a list: unchanged. Validation and the verify stay plan_steps's."""
    items = [i for i in proposed if isinstance(i, dict)] if isinstance(proposed, list) else []
    if (demand or {}).get("reasoning") != "high":
        return items
    if not any(i.get("kind") == "design" for i in items):
        lead = 0
        while lead < len(items) and items[lead].get("kind") in READ_FIRST:
            lead += 1
        items.insert(lead, {"kind": "design", "goal": DESIGN_GOAL})
    if not any(i.get("kind") in EDIT_KINDS for i in items):
        items = items[:max(max_steps - 1, 1)] + [{"kind": "code", "goal": CODE_GOAL}]
    return items
```

`plan_steps` cuts at `max_steps` from the front and appends a verify, so the trim above keeps the code step inside
the cap (the verify may make it `max_steps + 1` entries long only after the cut, as today).

### 3.2 `console/prep.py` `run_prep`

Replace the line `steps = tasks.plan_steps(fields.get("steps") or [], cfg["task_max_steps"])  # the only validator` by:

```python
    steps = tasks.plan_steps(tasks.hard_steps(fields.get("steps") or [], {"reasoning": route["reasoning"]},
                                              cfg["task_max_steps"]), cfg["task_max_steps"])  # the only validator
```

`route` is `fields["route"]` there; `route["reasoning"]` is a required schema key. The card shows the steps and Fred
may still edit them on the card: `Hub.create_task` takes his list as given (D2 acts at Prep, never at Start).

### 3.3 `console/server.py`

1. `_route_for`: replace the `hard=` argument by
   `hard=s["kind"] not in tasks.NO_HARD_KINDS and ((task["demand"] or {}).get("reasoning") == "high" or bool(s.get("hard"))),`.
2. `_run`, before `auto = ...`: a card with `route.reasoning == "high"` calls `create_task(card, tasks.hard_steps(<card steps without the verify>, card["demand"], task_max_steps), "auto")` and answers `{"session": "", "task": id}`; `doRun` in `web/app.js` opens the task when `session` is empty. The files Fred attached on a Run are not carried (a task takes the card's).

### 3.4 `dotclaude/console/kinds/prep.md`

After the paragraph that starts "Also split the request into steps", add one line:

`When reasoning is high, put a design step before the writing steps: the design step thinks on the top model, a code step then writes what it decided on a cheaper one. The Console adds both when you leave them out.`

(The repo seed and `kinds.text` read the same file; Fred copies `dotclaude/` to `~/.claude` himself.)

## 4. Tests (first)

- `tests/test_tasks.py::test_hard_steps_adds_design_and_code`: demand `{"reasoning": "high"}`:
  `[]` -> design, code; `[scout, code]` -> scout, design, code; `[design]` -> design, code; `[design, code]`
  unchanged; with `max_steps` 2 and `[scout, scout, scout]` the code step is kept (`items[:1] + [code]`); demand
  `{"reasoning": "low"}` and `"junk"` return the input items / `[]` unchanged. Feeding the result to `plan_steps`
  ends `..., code, verify`.
- `tests/test_tasks.py::test_step_route_code_never_takes_a_hard_only_rung`: `step_route("code", hard=False)` with a
  cfg whose write tier holds `opus` never returns the opus rung; the same call with `hard=True` on kind `design`
  still may (use the existing tiers fixture of `tests/test_fills.py`).
- `tests/test_prep.py::test_hard_card_gets_design_and_code`: `run_prep` with the fake claude answering
  `reasoning: high` and `steps: []` saves a card whose `steps` kinds are `design, code, verify`.
- `tests/test_server.py::test_hard_card_never_runs_as_a_chat`: Run on a hard card whose steps were cleared starts a task
  (design, code, verify); a Raw prompt and a low-reasoning card with no steps still start a chat.
- `tests/test_server.py::test_code_step_of_a_hard_task_is_not_routed_to_opus`: a task of demand high with step 02
  `code`: `_route_for(task, step)["rung"]` is not an opus-rank rung; step 01 `design` is.

## 5. Order and checks

1. Tests 1-5, red. 2. 3.1. 3. 3.2. 4. 3.3. 5. 3.4. One commit per step, stage only this plan's lines (other chats
edit `PLAN.md`, `server.py` and `test_server.py`). Run `py -m unittest discover -s tests`; `node --check web/app.js`
is not needed (no window change).

Live check (Fred): send a Prep prompt like "Implement all remaining Plan 1C"; the card should list design, code,
verify; start it; step 01 runs on Opus or Astra and writes no files, step 02 on Sonnet (or another write-tier rung),
step 03 verifies.

## 6. Not done here

- An Escalate floor (`floor code: opus/high`, plan 22) still lifts a code step to opus after a failed code step: it
  is Fred's own lesson, D4 (a). Say so if a code step should never reach Opus, even on Escalate (D4 b).
- Raw prompts (no card) have no demand, so they stay chats on the model Fred picks.
