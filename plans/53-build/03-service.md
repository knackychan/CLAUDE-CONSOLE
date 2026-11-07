# Task 3: the service runs the build (README 4.5 to 4.8; D1, D4, D6, D8)

Files: `console/server.py` (`Hub.__init__`, `advance`, `create_task`, `task_lever`, `delete_tasks`, `snapshot`, the
`_build_*` handlers and `do_POST` / `do_GET` routes), `tests/test_build_server.py` (new), `tests/test_server.py`,
`tests/fake_claude.py` (one word, `QUESTION-OPEN`).
Commit boundary: `feat: builds: the tick, the linked task, auto accept, the cap, the routes (plan 53 Task 3)`.
Depends on Tasks 1 and 2. Line numbers below are from `ce9d64f`; check them before editing.

## Hub state

- `__init__`: `self.builds = build.load_all(folder)` after `self.tasks` (line 76), under no lock (the loop is not
  running yet). `self.build_lock` is not needed: every build move happens under `tlock`, as task moves do.
- `advance()` (line 3244): after `self._supervisor_tick()`, inside the same `try` shape:

  ```python
  try:
      self._build_tick()
  except Exception as exc:  # a build never stops the hub loop
      self._log(f"build tick failed: {type(exc).__name__}: {exc}")
  ```

## The tick (`Hub._build_tick`, under tlock)

For every build with `state in ("running", "waiting")` and `owner == "service"`, `item = build.current_item(b)`:

| item state | what the tick does |
|---|---|
| none (`current == 0` after Start) | `current = 1` is set by `build.fred("start")`; nothing here |
| `planned` | cap first (D4): `s = build.spent(b, self._task_cost)`; `cap_usd and s >= cap_usd` -> `build.move(b, "waiting", f"cap: ${s:.2f} of ${cap:.0f} spent")`. Else `self._build_prep(b, item)` |
| `preparing` | `job = self.preps.get(item["prep"])`. None (a restart): `prep.discard(self.folder, item["prep"])` then `_build_prep(b, item, again=True)`. `failed`: `move_item(held, "prep failed: " + job["error"])`, build `waiting`, why `sub-plan N: prep failed: ...`. `done`: `card = job["card"]`; `item["drift"], item["drift_note"]` from `card["planner"]`; then `gated` -> `move_item(ready, "ready: 4 steps, drift none")`, build `waiting` `sub-plan N ready: Start`; `auto` and `drift == "major"` -> `move_item(held, "drift major: " + note)`, build `waiting` `sub-plan N: drift major: <note>`; `auto` otherwise -> `self._build_start_task(b, item, card)` |
| `ready`, `held` | nothing (Fred's move: the card's Start links the task; `continue`, `skip`, `cap`) |
| `running` | `t = self.tasks.get(item["task"])`. None -> `move_item(failed, "task deleted")`, build `waiting`. `t.get("accepted")` -> `self._build_close(b, item, "accepted", "accepted by Fred" or the build's line, cost)`. `auto` and `t["state"] == "done"`: `why = build.acceptable(t, tasks.summary(self.folder, t), self._card_visible(t))`; `""` -> `self.task_lever(t["id"], "accept", origin="build")` (the next tick closes the item); else build `waiting` `sub-plan N done: Accept (<why>)` (gated: the same line without the reason). `build.limit_stuck(t, self.limits, now)` (D8) -> `item["retried"] = 1`, `self.task_lever(t["id"], "retry", origin="build")`, line `retry by the build after the limit reset`. Else nothing: the task runs, waits or is stuck on its own page |
| `accepted`, `skipped`, `failed` as current | cannot happen: `close_item` moved `current` |

A `waiting` build whose reason is gone (Fred accepted, the task is back, the cap was raised) is set `running` by the
same branch that finds the new state: every branch above starts with `if b["state"] == "waiting" and <the reason no
longer holds>: build.move(b, "running", "")` before it acts. Every move is followed by `build.save` and `build.log`
(`self._build_commit(b, lines)`), and `self.version += 1` under `self.lock` so the page redraws.

Helpers:

```python
def _build_prep(self, b, item, again=False) -> None:
    """The item prompt to Prep in a job thread (start_prep with build=context); item preparing with the job id."""
    done, questions = self._build_done(b, item)
    ctx = build.context(b, item, done, questions)
    job = self.start_prep(b["project_dir"], build.prompt(b, item, done, questions), build=ctx)
    ...move_item(b, item, "preparing", ("prep again " if again else "prep ") + job + (": the service restarted" if again else ""))

def _build_done(self, b, item) -> tuple:
    """([{"n", "title", "state", "files"}] of the closed items before `item`, the open questions of the last accepted
    one), from tasks.summary of each item's task (files [] when the task is gone)."""

def _build_start_task(self, b, item, card, by="the build") -> None:
    """create_task(card, card["steps"], "auto", f"{b['title']} · {item['n']:02d} {item['title']}", supervised=True)
    inside its own try: a RunError (the project left config.json, claude.exe gone) holds the item with the reason."""

def _build_link(self, task, card_id) -> None:
    """Called by create_task under tlock: the build whose current item's prep == card_id gets item running with the
    task id; task["build"] = {"id": b["id"], "n": item["n"]}; line `started by Fred on the card` (or `started by the
    build: N steps` when _build_start_task set self._build_by)."""

def _build_close(self, b, item, state, why, cost) -> None   # build.close_item + commit; a done build logs its line
def _task_cost(self, task_id) -> float                      # sum(tasks.step_cost) + (task["prep"] or {}).get("cost") or 0
def _card_visible(self, task) -> bool                       # supervisor pending status in supervisor.VISIBLE + ("uncertain",)
def _build_commit(self, b, lines) -> None
```

## Existing methods that change

- `create_task` (line 2946): after `tasks.save(self.folder, task)` and before `self.drop_prep(card["id"])`:
  `self._build_link(task, card["id"])`. The body of `POST /api/task` is unchanged (D1: the card's Start is the gated
  move); `task["build"]` is an optional key read with `.get` everywhere (`TASK_KEYS` unchanged, `tasks.whole` passes).
- `task_lever` (line 3804): `origin` gains `"build"`: the `else` branch's word becomes
  `by = {"supervisor": "the supervisor", "build": "the build"}[origin]` and the replacement uses it; the levers a
  build may call are `accept` and `retry` only (an assertion in a test, not a runtime check: the tick is the only
  caller). `_supervisor_fred` is not called for a build's lever, as for the supervisor's.
- `delete_tasks` (line 998): a deleted task that has `task["build"]` makes the tick's "task deleted" branch fire on
  the next advance; nothing to add here. `_drop` is unchanged.
- `snapshot` (line 551): `snap["builds"] = sorted((build.row(b, rows_by_task.get(current task id)) for b in
  self.builds.values()), key=updated, reverse=True)` and `snap["counts"]["needs"] += builds in needs`. A build's
  current task row is the `task_row` already in `snap["tasks"]` (by id), so no second computation.
- `drop_prep(job)`: when the job is an item's `prep` and the item is `preparing` or `ready`, the item goes back to
  `planned` (Fred dropped the card: the next tick preps again) with the line `card dropped by Fred`.

## Routes (`Handler`)

`do_POST` gains `"/api/build/preview": self._build_preview, "/api/build": self._build_new` and, in a loop like the task
levers, `/api/build/<lever>` for `start, stop, pause, resume, skip, continue, level, cap, delete` -> `self._build_lever(body,
lever)`. `do_GET` gains `/api/build` -> `self._build(query.get("id", [""])[0])`.

- `_build_preview`: `folder = self.hub.allowed(body["project_dir"])` (403), `rel = body.get("folder")` text (400),
  `build.items_from(folder, rel)` (ValueError -> 400 with its text), `goal_ok = not goal_file or (rel_ok(goal_file)
  == "" and the file exists)`; answers `{items, goal_ok, error: ""}`.
- `_build_new`: the same checks; `keep` a list of ints (400 otherwise) filtered against the preview's numbers, order
  kept; `title` text or `""`; `level` in `build.LEVELS` (default `gated`, D1); `cap_usd` number (default
  `cfg["build_cap_usd"]`); `Hub.create_build(...)` makes the dict (`build.new_build`), saves it, logs `created: 9 items
  from <folder>, goal <goal_file>` and adds it to `self.builds` under tlock; answers `{build: id}`.
- `_build_lever(body, lever)`: `Hub.build_lever(build_id, lever, n=0, level="", cap=None) -> (status, body)` under
  tlock: 404 unknown; `stop` first calls `task_lever(stop)` on the current task when its step runs (its 409 is the
  answer) and drops a `preparing` item's job; `skip` of a `preparing` item drops its job; `continue`: on a `held`
  drift item `self._build_start_task(b, item, prep.load(self.folder, item["prep"]))` (the saved card; 409 when it is
  gone: "the card is gone: Skip or Stop"), on `held` prep failed or `failed` task deleted `_build_prep(b, item)`, on a
  cap hold 409 "raise the cap first"; `delete`: 409 while running with a live task, else `build.delete` and the dict
  leaves `self.builds`; everything else through `build.fred(...)` (its refusal is a 409). Each success commits and
  answers `{build: id, state}`.
- `_build(build_id)`: `{build, items: [{**item, "task_row": task_row(t) | None, "card": prep.summary(card) | None}],
  spent, summary: build.summary(...) when done else None, chain: build.read_chain(...), actions}`; `actions` is the
  README section 5 button list by state, in plan 52 Task 6's shape, built from `build.fred`'s own allowed table (one
  function `Hub.build_actions(b)`; a read).

## Tests (first, red), `tests/test_build_server.py` (a `TaskServerTest` subclass; the fake claude)

Fixture: `self.plans = self.project / "plans"` with `01-first.md` (`# First CHAIN HANDOFF-OK PLAN-OK VERDICT-PASS`),
`02-second.md` (`# Second CHAIN HANDOFF-OK PLAN-OK VERDICT-PASS`) and `PLAN.md` (`# Goal\nbuild it`); the words ride
through the item title into the prompt, so Prep proposes scout + code, the fake planner (Build context) answers scout,
design, code, the design step writes PLAN-OK and the verify PASSes. `make_build(level="gated", cap=25)` posts
`/api/build/preview` then `/api/build`; `until_build(bid, cond)` loops `poll_once` + `advance` as `until` does.

- `test_preview_lists_items_and_refuses_outside`: two items in order, titles from the headings; `..` -> 400; an
  unlisted project -> 403; a missing goal file -> `goal_ok` false.
- `test_create_starts_nothing`: the build is `planned`, no Prep job, no task, `builds/<id>/build.json` and `.jsonl`
  exist with the `created:` line.
- `test_gated_build_preps_then_waits_for_the_card_start`: Start; item 1 `preparing` with a job; when the card lands
  the item is `ready`, the build `waiting` `sub-plan 1 ready: Start`, the card's prompt carries `Build "..."`, the
  sub-plan path and no Goal line when goal_file is ""; the snapshot's `builds` row is in `needs`; nothing started.
- `test_card_start_links_the_task_and_accept_moves_on`: POST /api/task with the card (the ordinary body) -> the task
  has `build == {id, n: 1}`, the item is `running`, the build `running`; run the chain to done (`until(tid, done)`);
  the build waits `sub-plan 1 done: Accept`; POST /api/task/accept -> item 1 `accepted` with a cost > 0, item 2
  `preparing` on the next advance, its prompt lists `- 1 First: accepted; files ...`.
- `test_auto_build_starts_and_accepts_by_itself`: level auto: the task is created by the service (chain line
  `started by the build: 4 steps`, the task title `<build> · 01 First`), runs to done, is accepted by the build (task
  chain line `accepted by the build`, item cost set), item 2 runs, the build ends `done` with the `done: 2 accepted, 0
  skipped, $...` line and `GET /api/build` carries the summary; no supervisor pass ran (`supervisor_mode off`).
- `test_auto_waits_when_not_acceptable`: a done task with an open question (`tests/fake_claude.py` gains one word,
  `QUESTION-OPEN` with HANDOFF-OK: the block's Open questions carries one line, listed in the file's docstring) -> the
  build waits `sub-plan 1 done: Accept (1 open question)`; Fred's Accept moves on.
- `test_drift_major_holds_an_auto_build`: `PLANNER-DRIFT-MAJOR` in the heading: item 1 `held` `drift major: fake
  planner: the queue moved`, the build waiting; `/api/build/continue` starts the task from the saved card; at gated
  the same heading only puts the note on the card and the item is `ready`.
- `test_prep_failure_holds_then_continue_preps_again`: `PLANNER-FAIL` keeps Prep's steps (the card lands: no hold);
  a Prep job that raises (mock `prep.run_prep` once) -> `held` `prep failed: ...`; continue -> a new job.
- `test_cap_holds_before_the_next_item`: cap 0.01 with item 1 accepted at cost 0.02 -> `waiting` `cap: $0.02 of $0
  spent` before item 2 preps; `/api/build/cap 5` -> running, item 2 preps.
- `test_skip_stop_pause_resume_delete`: skip a later item; skip the current ready item (its job dropped); stop while
  the task runs (the task is stopped, the build stopped, the item keeps its task); start again -> the same item
  continues through the task's own Retry (the build does not start a new task while the item has one); pause ->
  after the item closes the build waits `paused after 01`; resume; delete refused while running, allowed when
  stopped, the tasks stay.
- `test_restart_preps_again`: a `preparing` item, a new Hub on the same folder -> the old prep folder is discarded,
  a new job starts with the `prep again` line.
- `test_task_deleted_fails_the_item`: delete the item's done task through `/api/tasks/delete` -> item `failed` `task
  deleted`, build waiting; continue preps again.
- `test_limit_retry_once` (D8): a task stuck with `why` "usage limit ... (after one retry)" and `hub.limits` holding
  an expired entry for anthropic -> one `task_lever retry` (origin build; the task chain says `retry by the build after
  the limit reset`), `retried == 1`; stuck again -> nothing more.
- `tests/test_server.py::test_task_lever_origin_build_words`: `origin="build"` writes `by the build` and never calls
  `_supervisor_fred`.
- `test_build_actions_per_state`: one fake build per README 4.5 state; the listed ids and posts; every `post` is a
  route `do_POST` serves; two GETs start nothing.
