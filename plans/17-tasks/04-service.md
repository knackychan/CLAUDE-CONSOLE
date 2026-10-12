# Task 4: The supervisor in the service

> Contract: [README.md](README.md) 3.7, 3.8, 3.9. Depends on Tasks 1 to 3. Everything here is in
> `console/server.py` except the retention sweep.

**Files**
- Modify: `console/server.py` (`Hub.__init__`, `Hub.run`, `Hub.snapshot`, new `Hub.tasks`, `Hub.budget`,
  `Hub.task_levers`, `Hub.create_task`, `Hub.start_step`, `Hub.advance`, `Hub.task_lever`, `Hub.last_reply`,
  `Hub.auto_steps` skip; `Handler` routes)
- Modify: `console/__main__.py` (line 40 area: `tasks.prune` next to `runs.prune`)
- Modify: `console/usage.py` (`folder_sizes(home) -> dict`, README 3.9)
- Modify: `console/paths.py` is done in Task 1 (`ladder`, `storage_warn_mb` are among its seven keys)
- Modify: `tests/test_server.py`

## `Hub`

- `__init__`: `self.tasks = tasks.load_all(folder)` (`{id: task}`), guarded by `self.lock` like `state`.
- `budget() -> dict`: returns `{}` (sub-plan 18 fills it from the usage windows, keyed by model id). One method.
- `tier_budget() -> dict`: tier -> the minimum share over the tier's rungs (`{}` while `budget()` is empty); what
  `step_route` receives.
- `model_id(tier) -> str`: README 3.8: the first rung of `cfg["ladder"][tier]` under `cfg["budget_warn_at"]`, else
  the tier alias. A `pick` that is a rung is used as given.
- `last_reply(sid) -> str`: the body of `Handler._last_reply` moved here; the handler calls it.
- `task_levers(task_id) -> dict | None`: `None` for an unknown id. Otherwise `{"start", "stop", "pause",
  "resume", "retry", "confirm"}`, each `""` (allowed) or the reason:
  - common: `Hub.allowed(project_dir)` empty -> `"runs are off in this project: ..."`; no `claude.exe` ->
    the config message; the project folder gone -> `"the task's folder is gone"`.
  - `start` (the next step may start): task `planned` or `running` with the current step not running, owner
    `service`; refused with `"another task is working in this project"` when any other task of the same
    `project_dir` is `running` or `waiting`; refused with `"confirm Fable"` when the next step's `pick` is `fable`
    and `fable_ok` is false (and the task is set `waiting` with that `why` by `advance`).
  - `stop`: task `running` or `waiting`; `pause`: owner `service` and state `running` or `waiting`; `resume`:
    owner `fred` and state `running` or `waiting`; `retry`: state `stuck` or `stopped` and the current step's
    session not live; `confirm`: `why == "confirm Fable"`; `clear`: state `done`, `stuck` or `stopped` and no live
    step session.
  Also returns `"route"` (the current step's `model/effort` or `""`), `"next_route"` (what `tasks.step_route`
  would give the next step, for the window), `"cwd"`.
- `create_task(card, steps, effort, title="") -> str`: `card` is a loaded Prep card (`prep.load`), `steps` the
  edited list from the page (validated again with `tasks.plan_steps`, max from config), `effort` `auto` or a
  level. Refuses (raises `runs.RunError`) when the project is not allowed, the steps are empty, or another task
  of the project is `running` / `waiting`. Builds `tasks.new_task(...)` with `goal = card["prompt"]` (the enhanced
  prompt as edited on the page, passed in `steps` body as `prompt`), `type_ = card["route"]["type"]`,
  `demand = card["demand"]`, `prep = card["id"]`; writes `prompt.md`, `task.json`; drops the Prep job
  (`drop_prep`); stores the task in `self.tasks`; calls `self.advance()` once so step 1 starts at once; returns
  the id.
- `start_step(task, n) -> None`: computes `route = tasks.step_route(kind, pick=step["pick"], checked=...,
  demand=task["demand"], misses=levers.read_misses(self.folder, task["project"]), prev=tasks.read_note(...,
  task["last_good"]), budget=self.budget(), warn_at=cfg["budget_warn_at"], effort=task["effort"])`; when
  `route["hold"]`: task `waiting`, `why = route["hold"]`, a chain line, save, return. Then
  `prompt = tasks.step_prompt(task, step, prev_note, retry_reason)` (the retry reason is `task["why"]` when
  `step["retries"] == 1` and the step is restarted), `limits` from `tasks.RULES[kind][2]` and `tasks.DISALLOW`,
  `budget = cfg["task_step_budget_usd"]`, `max_turns = cfg["opus_max_turns"] if kind == "design" and
  route["model"] == "opus" else 0`; `model = self.model_id(route["model"])` (the rung; `step["tier"]` keeps the tier). Starts `self.runs.start(cwd, prompt, model, effort, title=f"{task['title']} ·
  {n}/{M} {kind}", route=kind, reason=" · ".join(route["notes"]), prep=task["prep"], kind="task",
  extra={"task": task["id"], "step": n}, disallow=..., tools=..., budget=..., max_turns=...)`. On `runs.RunError`
  or `OSError`: task `stuck`, `why = str(exc)`. Then `tasks.start_step(...)`, log, save, `poll_once`.
- `advance() -> list`: called from the hub loop after `auto_steps`. For each task with `owner == "service"` and
  state in `(planned, running, waiting)`:
  - `planned`: if `task_levers["start"] == ""`: `start_step(task, 1)`.
  - `running` / `waiting` with a current step: `s = self.session(step["session"])`; `None` (the first event is
    not in yet) -> skip; `s["run_live"]` -> if state was `waiting` on a question, set `running` (Fred answered);
    skip; else (ended): `meta = self.runs.meta(sid)`; if `meta` and not `meta.get("ended")` -> skip (the watcher
    has not closed it); if `s["stop_question"]`: `on_step_ended(question=...)` -> waiting; else: `reply =
    self.last_reply(sid)`, `block = tasks.parse_handoff(reply)`, `block_error = "no HANDOFF block" if block is
    None else tasks.check_handoff(block)`, `ok` as README 3.7, `verdict = s["verdict"] if s["verdict_ts"] >=
    step["started"] else ""`, `action, lines = tasks.on_step_ended(...)`; when the block checked out, write the
    note first (`tasks.write_note`); `step["cost"]` from the session row's `cost`; `"fix"`: `levers.add_miss
    (self.folder, task["miss"])`; `"next"` / `"fix"` / `"retry"`: `start_step(task, task["current"] + (0 if retry
    else 1))` only once the brief exists: after a good block the step is done and `self.start_brief(task, n)` runs
    `compact.run_brief` in a thread (`threading.Thread`, daemon, like `_prep_job`), with `prev_brief =
    tasks.read_brief(home, task, last_good - 1)` and the next step's goal; the thread writes
    `steps/NN-<kind>.brief.md` (`tasks.write_brief`), clears `task["briefing"]`, logs `brief: 1240 -> 310 words,
    $0.01` (or `brief fallback: <why>`), saves, bumps the version; `advance` starts the next step on the pass where
    the brief file exists and `briefing` is clear (`brief_on` false: the fallback is written at once, no thread);
    `"done"` with `cfg["task_clear_on_done"]`: `tasks.clear(home, task, keep_last=True)` then
    `runs.forget(sid)` for each returned id (a `RunError` is skipped), the chain line `task:done -> task:cleared`;
    log, save, `poll_once`. Returns `[(task_id, action)]` for the tests.
  - a task whose next step has `pick == "fable"` and `fable_ok` false: `waiting`, `why = "confirm Fable"`.
  - exceptions other than `RunError` / `OSError` are not caught (a bug must show in the test run).
- `task_lever(task_id, lever) -> (status, body)`: the POST body for `stop`, `pause`, `resume`, `retry`,
  `confirm`, `clear` (`clear`: `tasks.clear(keep_last=False)`, `runs.forget` per step, the task leaves `self.tasks`,
  answers `{"task": id, "state": "cleared"}`): `task_levers` first (404 unknown, 409 with the reason); `stop` calls `self.runs.stop(session)` when
  the step is live (the interrupt); then `tasks.fred(task, lever, now)`, log, save; `retry` and `confirm` call
  `advance()` once; returns `200, {"task": id, "state": task["state"]}`.
- `auto_steps`: the `due` comprehension adds `and not s.task` (a step session's verdict belongs to its chain).
- `snapshot`: adds `"tasks": [task_row(t) for t in self.tasks.values()]` sorted by `updated` descending:
  `{"id", "title", "project", "project_dir", "state", "owner", "current", "count": len(steps), "why", "updated",
  "effort", "cost": sum of step costs, "route": current step's model/effort, "steps": [{"n", "kind", "state",
  "model", "effort", "session", "verdict", "retries", "cost"}]}`.
- `run()`: `self.advance()` right after `self.auto_steps()`.

## Retention

In `console/__main__.py`, after `runs.prune(paths.home(), cfg["retention_days"])`, add
`tasks.prune(paths.home(), cfg["task_retention_days"])`.

## `Handler`

- `GET /api/task?id=<id>`: `{"task": <task.json content>, "levers": task_levers, "note": tasks.read_note(...,
  last_good), "brief": tasks.read_brief(..., last_good)}`; 404 on an unknown or unsafe id. `/api/brief?kind=next` on a
  task's last step session seeds the composer with the last brief when the session belongs to a task.
- `POST /api/task` `{"prep": id, "prompt": text, "steps": [{"kind", "goal", "model"?}], "effort": "auto"|level}`:
  `prep.load` the card (404 when missing), the prompt replaces the card's `prompt` (edited on the page; empty ->
  400), `effort` validated (400), `Hub.create_task` (409 on `RunError`); answers `{"task": id}`.
- `POST /api/task/stop|pause|resume|retry|confirm|clear` `{"task": id}` -> `Hub.task_lever`.
- `POST /api/run` and the card's step `model` validate with `claude_cli.known_model(cfg, model)` instead of `in MODELS`,
  so a rung of the ladder can be picked by hand; `/api/config` returns `"ladder": cfg["ladder"]`.
- `/api/usage` adds `"storage"` (README 3.9) from `usage.folder_sizes(home)`, computed on the usage thread at start
  and once an hour, and `"storage_warn_mb"`.
- `/api/draft` accepts `"effort"` (`auto` or a level, else 400) and saves it in `window.json`; `/api/config`
  returns `"effort": window.get("effort", "auto")` and `"kinds": tasks.PREP_KINDS` (the card's kind select).

## Tests (`tests/test_server.py`, class `TaskServerTest(RunServerTest)` reusing `setUp`, `call`, `session`,
`wait_idle`, `verdict`)

Helpers: `prep_card(text)` (POST `/api/prep`, wait for the job, return the card), `task(tid)` (GET `/api/task`),
`wait_step(tid, n, state)` (poll `advance()` through the hub loop or call `self.hub.advance()` directly, 15 s
cap), `handoff_reply(...)`: the fake claude echoes the prompt, so the final message holds no HANDOFF block by
default. To make a step end with a good block, the fake claude gets one more word in `run()`: when the user
message holds `HANDOFF-OK`, its assistant text ends with a valid block; `VERDICT-PASS` / `VERDICT-FAIL` append
`VERDICT: PASS` / `VERDICT: FAIL x` lines (the hook is not running in tests, so the test writes the verdict event
with `self.verdict(sid, ...)` as today). The step prompt carries the step goal, so a test puts the words in the
goals it sends.

- `test_chain_starts_step_one_from_the_card`: `POST /api/task` with the `CHAIN` card and its 3 steps -> 200,
  `task.json` exists under `home/tasks/<id>/` with `prompt.md`; step 1 is running on haiku/low with a session whose
  `run_started` has `task`, `step`, `kind == "task"`, `--disallowedTools Agent` in the meta limits; the Prep job
  is gone from the strip; `task_levers` says `start` is `"another task is working in this project"` for a second
  task of the same project (409 on a second POST).
- `test_good_handoff_starts_the_next_step`: step goals with `HANDOFF-OK`; after step 1 ends, `steps/01-scout.md`
  exists with the header line and the block; step 2 starts on sonnet/medium; `chain.jsonl` has the lines; the
  verify step (3) starts on opus/medium (one model up from sonnet/medium).
- `test_missing_handoff_retries_once_then_stuck`: goals without the word: step 1 ends without a block -> step 1
  runs again (`retries` 1, the retry sentence in its prompt, the same route); ends again without -> task `stuck`,
  `why` ends with `(after one retry)`; `POST /api/task/retry` -> 200, step 1 running again; `retry` on a running
  task -> 409.
- `test_verify_fail_inserts_fix_and_verify`: steps scout, code, verify with `HANDOFF-OK`; the verify step's goal
  also holds `VERDICT-FAIL`, which makes the fake claude sleep 1 s before its result line, so the test can append
  the verdict event (`self.verdict(sid, "FAIL", "test_add - 3 != 4")`) while the run is still live, as the hook
  would at Stop; then: steps are scout, code, verify, fix, verify; the fix runs on sonnet/high; `routing-misses.md`
  has a `code` line; the second verify ending `FAIL` the same way -> `stuck`, `why` starts with `verify failed
  twice`.
- `test_stop_question_waits_for_fred`: a step whose goal holds `STOP-ASK` (new fake word: the assistant text ends
  with `STOP: which file?`; the test writes the Stop event with `stop_question` as the hook would) -> task
  `waiting`, `why == "asks: which file?"`; `POST /api/continue` on the step session (the answer) -> the session
  runs again, task `running`; its end with `HANDOFF-OK` -> next step.
- `test_stop_interrupts_the_step_never_kills`: a `SLOW` step; `POST /api/task/stop` -> 200, the stream shows the
  `[Request interrupted` line (the interrupt path of `runs.stop`), task `stopped`, owner `fred`; `retry` -> the
  step starts again with a new session; the old session row stays.
- `test_pause_and_resume`: `pause` while step 1 runs -> owner `fred`; step 1 ends with a good block -> nothing
  starts (`advance()` returns `[]`); `resume` -> step 2 starts.
- `test_task_only_in_allowed_projects`: a card for a folder not in `projects` -> 403 on `POST /api/task`.
- `test_auto_steps_skip_task_sessions`: a FAIL verdict on a task's step session -> `auto_steps()` returns `[]`
  for it (no automatic Escalate on the step).
- `test_restart_resumes_the_chain`: a task with step 1 running; a second `Hub` on the same folder (as
  `test_reconcile...` does) after the fake run ended -> its first `advance()` finds the ended step and goes on.
- `test_fable_needs_a_confirm`: a step with `"model": "fable"` -> `waiting`, `why == "confirm Fable"`; `POST
  /api/task/confirm` -> the step starts with `--model fable`.
- `test_budget_hold_waits_for_fred`: `self.hub.budget = lambda: {"opus": 0.9}`; a verify of a sonnet step ->
  task `waiting`, `why == "opus over its pace"`; a design step -> runs on sonnet/xhigh with a `budget:` note in
  its `run_started` reason.
- `test_nothing_written_outside_home`: after a two-step chain, the project folder holds only what the fake claude
  wrote (nothing: it writes no file) and `home/tasks/<id>/` holds exactly `task.json`, `prompt.md`, `chain.jsonl`,
  `steps/`.
- `test_done_task_is_cleared`: a two-step chain to `done` -> `runs/<sid>.jsonl` of both steps gone, `steps/` holds
  the last note only, `task.json` says `cleared`, the chain log ends with `task:cleared`; with
  `cfg["task_clear_on_done"] = False` everything stays.
- `test_clear_removes_a_stuck_task`: `POST /api/task/clear` on a stuck task -> 200, the folder is gone, the task is
  out of the snapshot; on a running task -> 409.
- `test_brief_runs_between_steps`: a two-step chain with `HANDOFF-OK`; after step 1 the row says `briefing`, then
  `steps/01-scout.brief.md` exists with the four headings and under 400 words, the chain log has the `brief:` line,
  and step 2's prompt (its `cc_prompt` line in the stream) holds the brief text and not the raw note; with
  `cfg["brief_on"] = False` the brief file is the code fallback and no second `claude` process ran for it.
- `test_brief_fallback_never_blocks_the_chain`: `LONG` in step 1's goal -> the brief is the fallback, the chain log
  says `brief fallback: over 400 words`, step 2 still starts.
- `test_task_snapshot_and_get`: the snapshot's `tasks` row fields; `GET /api/task?id=` returns the task, the levers
  and the last note; `GET /api/task?id=../x` -> 404.
- `test_rung_under_budget_pressure`: `self.hub.budget = lambda: {"opus": 0.9}` (the alias over, the older rungs
  not) -> a design step runs with `--model claude-opus-4-8`, `step["tier"] == "opus"`; with every opus rung over,
  it runs on sonnet/xhigh (the tier drop of `step_route`).
- `test_a_rung_can_be_run_by_hand`: `POST /api/run` with `"model": "claude-haiku-4-5"` -> 200 and the command
  carries it; `"claude-haiku-3"` -> 400.
- `test_usage_reports_storage`: after a run, `/api/usage` has `storage.runs > 0` and `storage.total >= storage.runs`.
- `test_draft_keeps_the_effort`: `POST /api/draft {"text": "", "effort": "max"}` -> `GET /api/config` gives
  `"effort": "max"`; `"effort": "turbo"` -> 400.

## Steps

- [ ] 1. Fake claude words `HANDOFF-OK`, `VERDICT-FAIL` (1 s delay), `STOP-ASK`; docstring lines. Run the suite:
      169 + Tasks 1-3 OK (nothing uses the words yet).
- [ ] 2. Write `TaskServerTest` with the first four tests. Run: 404 on the routes.
- [ ] 3. `Hub.tasks`, `budget`, `last_reply`, `task_levers`, `create_task`, `start_step`, `advance`, the loop call,
      `GET /api/task`, `POST /api/task`. Run the four: pass.
- [ ] 4. Write the remaining tests. Run: fail on the lever routes and the skips.
- [ ] 5. `task_lever`, the six POST routes, the clear on done, `start_brief` and the `briefing` flag, the `auto_steps` skip, the snapshot rows, `tasks.prune` in the
      sweep, `/api/draft` `effort`, `/api/config` `effort` / `kinds` / `ladder`, `model_id` and `tier_budget`, `known_model`
      in the run route, `usage.folder_sizes` and `storage` in `/api/usage`. Run: pass.
- [ ] 6. Whole suite OK. Commit: `feat: task chain supervisor in the service: advance, levers, routes (plan 17 Task 4)`.

## Drift guards

- `advance` reads state and files, then calls `tasks.*` for every decision; no transition is decided in
  `server.py`.
- `task_levers` is called at the top of `advance` (for `start`) and of every POST; no route starts a run on its own.
- One `advance` per loop pass, no thread per task, no timer.
- `runs.stop` is the only stop; `kill_tree` is not called from any task path.
- The miss line of a fix uses the checked step's kind as the type, so `routing.floor` and Prep read it the same way.
