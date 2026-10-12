# Sub-plan 16: Demand routing and automatic route steps

> Master: [PLAN.md](../PLAN.md). Rules: [CLAUDE.md](../CLAUDE.md).

## Goal

Route each task by its demand (heavy reasoning to Opus, heavy token volume to Haiku or Sonnet), and let
the Escalate and de-escalate steps happen during a task, always through `server.Hub.levers`.

## Facts checked (2026-10-12, CLI 2.1.296)

- A window run is one `claude -p --resume <id>` process per turn (`runs.RunManager.start`; `_watch`
  closes stdin after the result line). Each lever already starts the next turn with its own `--model`
  and `--effort` on the same session id. A model change at a turn boundary needs no fork and no
  transcript copy; only a VS Code or terminal chat is forked, once, as today.
- Inside one process, stream-json input also takes `{"type":"control_request","request":{"subtype":
  "set_model","model":"sonnet"}}` and `{"subtype":"apply_flag_settings","settings":{"effortLevel":
  "medium"}}` between turns (Agent SDK `setModel()` / `applyFlagSettings()`, streaming input only).
  Checked live: a haiku turn, both requests answered `success`, the next turn's init and assistant
  lines were `claude-sonnet-5-5`, same process. Not needed while each turn is its own process.
- A model switch re-writes the context cache at the new model's price (the sonnet turn above wrote
  3527 cache tokens again). The cold-cache guard of plan 08 still applies.
- No mid-turn switch exists: a running turn keeps its model. Within a turn only subagents can run on
  another model.

## Task 1: Demand routing in Prep (done 2026-10-12)

- `console/routing.py`: `by_demand(route)` (reasoning high: at least opus/high; volume high: haiku/low,
  or sonnet/medium when reasoning is medium; else Prep's pick), `floor(misses, type)` (the newest
  "next time start at" of the same task type), `pick(route, misses)` (the higher of the two).
- `console/prep.py`: the schema's `route` gains `reasoning` and `volume` (low / medium / high, required);
  `run_prep` replaces the route's model and effort with `routing.pick` and appends
  `Demand rule: a/b -> c/d.` to the reason when that changed the route. Misses stay a floor, so phase 3's
  learning loop still holds when code decides.
- `console/prep_prompt.md`: how to rate reasoning and volume; the type table is unchanged (the
  `route-model` skill test compares it).
- Tests: `tests/test_routing.py` (5), `test_run_prep_routes_by_demand` with `THINK` / `BULK` in the fake
  claude. 155 tests OK.

## Task 2: Automatic Escalate and de-escalate (done 2026-10-12)

Fred chose (b): the service takes the step by itself at the end of a turn, no confirm.

- `server.Hub.pull(sid, lever, text, confirm)`: the lever body moved out of `Handler._lever`, which now
  only calls it. It asks `Hub.levers` first, so a click and the automatic step pass one gate.
- `Hub.levers` returns `deescalate` and `deescalate_to`: allowed for a window run after a PASS verdict
  when its route is above the task's starting route (`start_route` in the run meta, kept from the
  first turn by `runs.RunManager.start`). De-escalate goes back to that route, which undoes the one
  Escalate exactly; it starts no turn (`runs.RunManager.set_route`): the next turn runs on it.
- `Hub.auto_steps()`, called from the hub loop after each poll: for window runs whose state is
  `verify_failed` it pulls Escalate, for `verified` it pulls de-escalate. Skipped: verdicts older than
  the service's start (`auto_since`, so a restart never escalates old chats), VS Code and terminal chats
  (their Escalate is a fork: still a click), anything `Hub.levers` refuses (once per task, busy, cold
  cache needing a confirm). Escalate still writes its routing-misses line.
- Tests: `test_route_steps_run_by_themselves_through_levers` (FAIL escalates sonnet/medium to
  sonnet/high, a second FAIL does nothing, PASS de-escalates to sonnet/medium with no new turn, the next
  Continue runs on it), `test_route_steps_skip_old_verdicts_and_vscode_chats`, `RoutingTest.test_parse`.
  158 tests OK.
- Not checked live: an automatic Escalate in the real window (Claude cannot start auto-mode runs).
