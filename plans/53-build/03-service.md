# Task 3: the service runs the build (README 4.5 to 4.9; D1, D4, D6, D8, D9)

Files: `console/server.py` (`Hub.__init__`, `advance`, `create_task`, `task_lever`, `drop_prep`, `snapshot`, the `_build_*`
methods and the `Handler` routes), `tests/test_build_server.py` (new), `tests/test_server.py`, `tests/fake_claude.py` (one
word, `QUESTION-OPEN`).
Commit boundary: `feat: builds: the tick, the linked task, auto accept, the cap, the routes (plan 53 Task 3)`. This is the
largest task; build it as two commits if it helps, **A** (state, tick, linking, recovery, `task_lever` origin, `drop_prep`,
`_build_mode`) and **B** (routes, snapshot, actions), each tests first, the message naming A or B.
Depends on Tasks 1 and 2. Line numbers below are from HEAD `9b6f988` (2026-11-07); check them before editing.

## What moved since this task was written (ce9d64f to 9b6f988; plan 52 Tasks 5 and 6, plan 54, Task 7)

| Reference | At `ce9d64f` | At `9b6f988` |
|---|---|---|
| `Hub.__init__`: `self.lock` / `self.tasks` / `self.tlock` | 76 / 78 / 79 (the old text said "line 76") | 76 / 78 / 79 |
| `Hub.advance` | 3244 | 3432; the `_supervisor_tick` block is 3444-3447 |
| `Hub.create_task` | 2946 | 3134; `self.tasks[...] = task` 3159-3160, `drop_prep` 3161, `advance` 3162; signature `create_task(card, steps, effort, title="", *, supervised=False, supervisor_mode=None)`, `supervised` "changes nothing" |
| `Hub.task_lever` | 3804 | 4025; new keyword `remember=None`; the non-Fred branch (`else`) is 4076-4079 |
| `Hub._ended` plan hold | 3405 | 3537 (def); the hold is 3631: `(plan_hold or self._level(task) == "gated")` |
| `Hub._supervisor_tick` | 1664 | 1852 |
| `Hub.delete_tasks`, `Hub.snapshot`, `Hub.start_prep`, `_prep_job`, `drop_prep` | 998, 551, 444, 466, 502 | unchanged |
| new, used here | | `Hub._level` 3996, `Hub.remember_level` 3999, `Hub.actions` 1109, `Hub._base` 975, `Hub.allowed` 4125, `supervisor.VISIBLE` (supervisor.py:207) |
| `paths.write_text_atomic` | plan 34's temp file and `os.replace` | plan 54: `winfiles.write_text` on Windows, same signature; `tasks.save`, `config`, `window`, `usage`, kind files already use it |
| `Handler.do_POST` routes dict / `do_GET` | | 4346-4363 / 4294; `_task_new` 4585; `_draft` 4663 |

## Hub state

- `__init__`: `self.builds = build.load_all(folder)` right after `self.tasks = tasks.load_all(folder)` (line 78), under no
  lock (the loop is not running yet); `self._build_busy = False` (F18); `self._build_recovered = False` (F1 to F3);
  `self._build_refused = {}` (build id -> `(task["updated"], error)` of the last refused Accept, F17, in memory only).
  `self.build_lock` is not needed: every build move happens under `tlock`, as task moves do.
- `advance()` (line 3432): after the `try: self._supervisor_tick()` block (3444-3447), inside the same `with self.tlock:`:

  ```python
  try:
      self._build_tick()
  except Exception as exc:  # a build never stops the hub loop
      self._log(f"build tick failed: {type(exc).__name__}: {exc}")
  ```

  `advance` is also called by `create_task` and by `task_lever` (retry, confirm, redo, keep, stepdone), so the tick can
  be entered from inside itself. `_build_tick` returns at once when `self._build_busy` and sets it in a `try/finally`
  (F18).

## The tick (`Hub._build_tick`, under tlock)

On its first run only (`not self._build_recovered`): `self._build_recover()` (below), then the flag. Then, for every
build with `state in build.LIVE` and `owner == "service"`, `item = build.current_item(b)`:

0. Project guard (F13). `why = self._base({"project_dir": b["project_dir"]})` (`_base` reads only `project_dir`; it
   covers a project off config.json, no claude.exe and a missing folder, the three things `POST /api/prep` and
   `create_task` refuse separately). Not empty: `build.move(b, "waiting", "project: " + why)` once, commit, and go to the
   next build. Empty while the build waits with a `project:` why: `build.move(b, "running", "")`.
1. The item table:

| item state | what the tick does |
|---|---|
| none (`current == 0` after Start) | nothing here: `build.fred("start")` sets `current = 1` |
| `planned` | cap first (D4): `s = build.spent(b, self._task_cost)`; `cap_usd and s >= cap_usd` -> `build.move(b, "waiting", f"cap: ${s:.2f} of ${cap:.0f} spent")`. Then the file guard (F12): `build.file_sha(project_dir, item["file"]) == ""` -> `move_item(held, "file missing: <file>")`, build `waiting` `sub-plan N: file missing: <file>`. Else `self._build_prep(b, item)` |
| `preparing` | `job = self.preps.get(item["prep"])`. None (Fred dropped it: `drop_prep` already held the item; or a race): `_build_prep(b, item, again=True)`. Running: nothing. `failed`: `move_item(held, "prep failed: " + job["error"])`, build `waiting`, why `sub-plan N: prep failed: ...` (F6). `done`: `card = job["card"]`; `item["drift"], item["drift_note"]` from `card["planner"]`; a non-empty `card["planner"]["error"]` at `auto` -> `move_item(held, "planner failed: " + error)`, build `waiting` (F19; at `gated` the card lands and shows the error); then `gated` -> `move_item(ready, "ready: 4 steps, drift none")`, build `waiting` `sub-plan N ready: Start`; `auto` and `drift == "major"` -> `move_item(held, "drift major: " + note)`, build `waiting` `sub-plan N: drift major: <note>`; `auto` otherwise -> `self._build_start_task(b, item, card)` |
| `ready`, `held` | nothing (Fred's move: the card's Start links the task; `continue`, `skip`, `cap`). One check first (F3): a task with `tasks.prep_id(task) == item["prep"]` exists (a crash left it) -> `_build_linked(b, item, task, recovered=True)` |
| `running` | `t = self.tasks.get(item["task"])`. None -> `move_item(failed, "task deleted")`, build `waiting` (F8). `t.get("accepted")` -> `self._build_close(b, item, "accepted", by, cost)`, `by` read from the task's last `accepted by ...` chain line (Fred's or the build's). Else, `t["state"] == "done"`: `gated` -> build `waiting` `sub-plan N done: Accept`. `auto` -> `busy = self._settled(t)`; `why = build.acceptable(t, tasks.summary(self.folder, t), self._card_visible(t), busy)`; `""` -> `code, data = self.task_lever(t["id"], "accept", origin="build")`: 200 -> the next tick closes the item; otherwise build `waiting` `sub-plan N done: Accept (<data["error"]>)` and `self._build_refused[b["id"]] = (t["updated"], error)` so the lever is not called again until the task changes (F17); `why` not empty -> build `waiting` `sub-plan N done: Accept (<why>)`. D8: `build.limit_stuck(item, t, {k: v for k, v in self.limits.items() if float(v.get("until") or 0) > now})` -> set `item["retried"] = 1` and commit it with the line `retry by the build after the limit reset` **before** `self.task_lever(t["id"], "retry", origin="build")` (F5, F18). Else nothing: the task runs, waits or is stuck on its own page |
| `accepted`, `skipped` as current | cannot happen: `close_item` moved `current` |
| `failed` as current | a wait state, not a close: `move_item` set it (`task deleted`), `current` stays, the build is `waiting` `sub-plan N: task deleted`. Continue resets the item (`task` "", `ended` None) and preps again; Skip closes it as `skipped` |

A `waiting` build whose reason is gone (Fred accepted, the task is back, the cap was raised, the project is back) is
set `running` by the same branch that finds the new state: every branch above starts with `if b["state"] == "waiting"
and <the reason no longer holds>: build.move(b, "running", "")` before it acts. Every move is followed by `build.save`
and `build.log` (`self._build_commit(b, lines)`: log first, then save, as `Hub._commit` does for tasks), and `self.version
+= 1` under `self.lock` so the page redraws. A save that raises (F15) leaves the in-memory move, is logged by the
`advance` handler, and is saved again by the next move; there is no retry loop.

Helpers:

```python
def _build_recover(self) -> None:
    """Once after a start (F1 to F3). For each live build's current item in preparing, ready or held with an item["prep"]:
    (1) a task with tasks.prep_id(task) == item["prep"] exists -> self._build_linked(b, item, task, recovered=True);
    (2) else card = prep.load(self.folder, item["prep"]); a whole card (a dict with a non-empty "steps" and a "planner"
        key) with no tasks/<id>/task.json -> self.preps[item["prep"]] = {"id", "project_dir", "raw": card["raw"],
        "ts": card["ts"], "state": "done", "card": dict(card), "files": []}, line `recovered: card re-seated after
        the service restarted`; a preparing item then takes its done branch in this same tick; no model call;
    (3) else a preparing item: prep.discard(self.folder, item["prep"]) and self._build_prep(b, item, again=True)
        (line `prep again <job>: the service restarted`); a ready or held item: move_item(held, "card gone: Prep
        again"), build waiting `sub-plan N: card dropped` (the orphan prune removed it, README F2)."""

def _build_prep(self, b, item, again=False) -> None:
    """The item prompt to Prep in a job thread (start_prep with build=context); item preparing with the job id and
    item["sha"] = build.file_sha(b["project_dir"], item["file"]). The tick's project guard replaces the checks
    POST /api/prep makes (allowed, claude.exe)."""
    done, questions = self._build_done(b, item)
    ctx = build.context(b, item, done, questions)
    job = self.start_prep(b["project_dir"], build.prompt(b, item, done, questions), build=ctx)
    ...move_item(b, item, "preparing", ("prep again " if again else "prep ") + job + (": the service restarted" if again else ""))

def _build_done(self, b, item) -> tuple:
    """([{"n", "title", "state", "files"}] of the closed items before `item`, the open questions of the last accepted
    one), from the items' own stored `files` and `questions` (README 4.2): no task folder is read, so a Deleted task or
    task_retention_days changes nothing."""

def _build_start_task(self, b, item, card, by="the build") -> None:
    """create_task(card, card["steps"], "auto", f"{b['title']} · {item['n']:02d} {item['title']}", supervised=True)
    inside its own try; supervisor_mode is not passed: create_task takes it from _build_mode (D9). `supervised` is kept
    for the body's shape and changes nothing (its docstring). A RunError (the project left config.json, claude.exe
    gone) holds the item `start failed: <error>`; Continue starts again from the saved card."""

def _build_mode(self, card_id: str):
    """D9: "auto" when card_id is the prep of a build item (preparing, ready or held) and that build's level is
    "auto", else None. create_task calls it when its caller named no supervisor_mode."""

def _build_mark(self, task, card_id):
    """Called by create_task under tlock BEFORE tasks.save: finds the build item whose prep == card_id (build state
    running, waiting or stopped; item preparing, ready or held) and sets task["build"] = {"id", "n"} in memory, so
    task.json is written once with the key. Returns (b, item) or None."""

def _build_linked(self, b, item, task, recovered=False) -> None:
    """Called by create_task AFTER self.tasks[...] = task and BEFORE drop_prep: item running with item["task"], build
    running (a stopped build whose card Fred started resumes: line `resumed by the card's Start`), the line
    `started by Fred on the card` or, from _build_start_task, `started by the build: N steps`, `, recovered` appended
    for F3. The order task first, build second means a crash between them is F3's recovery, never a build that points
    at a task that does not exist."""

def _build_close(self, b, item, state, why, cost) -> None   # build.close_item (files and questions from tasks.summary) + commit
def _task_cost(self, task_id) -> float                      # sum(tasks.step_cost) + (task["prep"] or {}).get("cost") or 0
def _card_visible(self, task) -> bool                       # sup.pending["status"] in supervisor.VISIBLE + ("uncertain", "dispatching")
def _settled(self, task) -> str                             # "brief writing" (task["briefing"] or id in self.briefing), "supervisor pass pending" (id in self.wakes or self.supervising), else ""
def _build_commit(self, b, lines) -> None
```

## Existing methods that change

- `create_task` (line 3134). Three insertions: (1) before `task["supervisor"] = supervisor.initial(...)` (3156):
  `supervisor_mode = supervisor_mode or self._build_mode(card["id"])`; (2) after `self._prep_files(...)` (3157) and
  before `tasks.save` (3158): `mark = self._build_mark(task, card["id"])`; (3) after `self.tasks[task["id"]] = task`
  (3159-3160) and before `self.drop_prep(card["id"])` (3161): `if mark: self._build_linked(*mark, task)`. The order
  matters twice: the item is `running` before `drop_prep` runs, so the hold rule below does not fire for a card that
  became a task; and the task is on disk before the build says so (F3). The body of `POST /api/task` is unchanged (D1:
  the card's Start is the gated move); `task["build"]` is an optional key read with `.get` everywhere (`TASK_KEYS`
  unchanged at 416-417, `tasks.whole` passes).
- `task_lever` (line 4025). `origin` gains `"build"`: the non-Fred branch (4076-4079) takes
  `by = {"supervisor": "the supervisor", "build": "the build"}[origin]` and the two `.replace(" by Fred", " by the
  supervisor")` calls use it; the levers a build may call are `accept` and `retry` only (an assertion in a test, not a
  runtime check: the tick is the only caller). `_supervisor_fred` is not called for a build's lever, as for the
  supervisor's. The new `remember` keyword is not used by a build, and `task_lever` keeps its 409 for pending guidance.
- `delete_tasks` (line 998): unchanged. A deleted task that has `task["build"]` makes the tick's "task deleted" branch fire
  on the next advance (F8).
- `snapshot` (line 551): `snap["builds"] = sorted((build.row(b, rows_by_task.get(current task id)) for b in
  self.builds.values()), key=updated, reverse=True)` and `snap["counts"]["needs"] += builds in needs`. A build's current
  task row is the `task_row` already in `snap["tasks"]` (by id), so no second computation; a task past `DONE_DAYS` (14) is
  left out of `snap["tasks"]` (`old_done`), so for it the row is built with `task_row(t)` directly.
- `drop_prep(job)` (line 502): when the job is an item's `prep` and the item is `preparing` or `ready`, the item goes
  to `held` with `card dropped by Fred` (F16), not back to `planned`: a card Fred dropped must not come back by itself.
  `Hub.drop_prep` is also called by `create_task` and by `/api/run` (line 4470), which is why `_build_linked` runs first.
  A `preparing` item whose job is dropped is also held, and the job's result (`_end_job` finds no job and calls
  `prep.discard`) is thrown away as today.
- `Hub.run` / `tick`: no change; the build tick runs inside `advance`, which the hub loop calls every second.

## Routes (`Handler`)

`do_POST` gains `"/api/build/preview": self._build_preview, "/api/build": self._build_new` and, in a loop like the task
levers (4362-4363), `/api/build/<lever>` for `start, stop, pause, resume, skip, continue, level, cap, delete` ->
`self._build_lever(body, lever)`. `do_GET` gains `/api/build` -> `self._build(query.get("id", [""])[0])` beside
`/api/task` (4323). Every route sits behind `do_POST`'s `guard.host_ok` and `guard.post_ok` check.

- `_build_preview`: `folder = self.hub.allowed(body["project_dir"])` (403), `rel = body.get("folder")` text (400),
  `build.items_from(folder, rel)` (ValueError -> 400 with its text), `goal_ok = not goal_file or (rel_ok(goal_file)
  == "" and the file exists)`; per item `warnings = build.lint(text)`, `goal_warnings = build.lint(goal text, goal=True)`,
  `digest = build.digest(folder, items)`; answers `{items, goal_ok, goal_warnings, digest, error: ""}`. Writes nothing.
- `_build_new`: the same checks; `digest` must equal `build.digest` of the folder now (else 409 "the folder changed
  since the preview: Preview again", F10); `keep` a list of the preview's `file` paths (400 for a path the folder no
  longer lists, or a non-list), order kept; `title` text or `""`; `level` in `build.LEVELS` (default `gated`, D1);
  `cap_usd` number (default `cfg["build_cap_usd"]`); `Hub.create_build(...)` makes the dict (`build.new_build`), saves it,
  logs `created: 9 items from <folder>, goal <goal_file>` and adds it to `self.builds` under tlock; answers `{build: id}`.
- `_build_lever(body, lever)`: `Hub.build_lever(build_id, lever, n=0, level="", cap=None) -> (status, body)` under
  tlock: 404 unknown. `start`: 409 with `self._base(...)` when it is not empty, and 409 `another build is live in this
  project: <title>` when `build.live_in_project(self.builds, b["project_dir"], b["id"])` names one (F14); then
  `build.fred`. `stop` first calls `task_lever(stop)` on the current task when its step runs (its 409 is the answer) and
  drops a `preparing` item's job. `skip` of a `preparing` item drops its job. `continue` (body `{build, again?}`): on
  `held` drift, planner failed or start failed `self._build_start_task(b, item, prep.load(self.folder, item["prep"]))`
  (`_build_prep(b, item)` instead when `prep.load` finds none); on `held` prep failed, file missing, card dropped or
  card gone, or `failed` task deleted `_build_prep(b, item)`; with `again` true always `_build_prep` (the saved card is
  discarded first); on a cap hold 409 "raise the cap first". `delete`: 409 while running
  with a live task, else `build.delete` and the dict leaves `self.builds`. Everything else goes through `build.fred(...)`
  (its refusal is a 409). Each success commits and answers `{build: id, state}`.
- `_build(build_id)`: `{build, items: [{**item, "task_row": task_row(t) | None, "card": prep.summary(card) | None}],
  spent, summary: build.summary(...) when done else None, chain: build.read_chain(...), actions}` where `summary`'s
  `task_summaries` holds `tasks.summary` of the current item's task only.
- `Hub.build_actions(b)` (a read; it starts nothing and writes nothing) returns `{state, tag, why, line, primary, bar,
  menu}` with plan 52 Task 6's action shape `{id, label, post, body, off, confirm}`. `state` is the build state word;
  `line` the row sentence; `tag` and `why` the dock card (`""` when nothing waits). Built from `build.fred`'s own allowed
  table, so an action is listed with its refusal in `off`:

| Situation (4.5) | tag | primary | bar | menu |
|---|---|---|---|---|
| `planned` | | `start` | | `folder`, `delete` |
| `running` | | | `stop`, `pause` | `level_gated`, `level_auto`, `cap`, `folder`, `delete` |
| ready | `Ready` | `open_card` (post `""`) | `skip`, `stop` | as running |
| drift major | `Drift` | `continue` | `prep_again` (post `/api/build/continue`, body `again: true`), `skip`, `stop` | as running |
| prep, planner, file, card or start trouble; task deleted | `Held` | `continue` | `prep_again`, `skip`, `stop` | as running |
| cap | `Cap` | `raise_cap` (post `/api/build/cap`, body `cap_usd` filled by the page's field) | `stop` | as running |
| done task, Accept | `Accept` | `open_task` (post `""`) | `skip`, `stop` | as running |
| paused | `Paused` | `resume` | `stop` | `folder`, `delete` |
| project | `Project` | | `stop` | `folder`, `delete` |
| `stopped` | | `start` | | `folder`, `delete` |
| `done` | | | | `folder`, `delete` |

## Tests (first, red), `tests/test_build_server.py` (a `TaskServerTest` subclass; the fake claude)

Fixture: `self.plans = self.project / "plans"` with `01-first.md` (`# First CHAIN HANDOFF-OK PLAN-OK VERDICT-PASS`),
`02-second.md` (`# Second CHAIN HANDOFF-OK PLAN-OK VERDICT-PASS`) and `PLAN.md` (`# Goal\nbuild it`); the words ride
through the item title into the prompt, so Prep proposes scout + code, the fake planner (Build context) answers scout,
design, code, the design step writes PLAN-OK and the verify PASSes. `make_build(level="gated", cap=25)` posts
`/api/build/preview` then `/api/build` (with its `digest` and `keep`); `until_build(bid, cond)` loops `poll_once` +
`advance` as `until` does. The project is at the default task level `gated`, so a gated build's task stops at `plan
ready: confirm`: the helper `confirm_plan(tid)` posts `/api/task/confirm` (the task's own gate, D9).

- `test_preview_lists_items_and_refuses_outside`: two items in order, titles from the headings, `warnings` and
  `digest` present; `..` -> 400; an unlisted project -> 403; a missing goal file -> `goal_ok` false.
- `test_create_starts_nothing`: the build is `planned`, no Prep job, no task, `builds/<id>/build.json` and `.jsonl`
  exist with the `created:` line.
- `test_create_refuses_a_folder_that_changed_since_the_preview` (F10): add `03-third.md` after the preview -> Create is 409
  and no `builds/` folder appears; a `keep` naming a file the folder no longer lists is 400.
- `test_gated_build_preps_then_waits_for_the_card_start`: Start; item 1 `preparing` with a job and a `sha`; when the card
  lands the item is `ready`, the build `waiting` `sub-plan 1 ready: Start`, the card's prompt carries `Build "..."`,
  the sub-plan path and no Goal line when goal_file is ""; the card's Goal starts `Sub-plan 1 of 2 (`; the snapshot's
  `builds` row is in `needs`; nothing started.
- `test_card_start_links_the_task_and_accept_moves_on`: POST /api/task with the card (the ordinary body) -> the task
  has `build == {id, n: 1}` in task.json on disk, the item is `running`, the build `running`, and the item was `running`
  before `drop_prep` removed the job; run the chain to done, confirming the plan (`until(tid, done)`); the build waits
  `sub-plan 1 done: Accept`; POST /api/task/accept -> item 1 `accepted` with a cost > 0 and stored `files`, item 2
  `preparing` on the next advance, its prompt lists `- 1 First: accepted; files ...`.
- `test_auto_build_starts_and_accepts_by_itself`: level auto: the task is created by the service (chain line
  `started by the build: 4 steps`, the task title `<build> · 01 First`), its `supervisor.mode` is `auto` although the
  project is `gated` (D9), no `plan ready: confirm` hold appears, it runs to done, is accepted by the build once the
  brief is written and no wake is pending (task chain line `accepted by the build`, item cost set), item 2 runs, the
  build ends `done` with the `done: 2 accepted, 0 skipped, $...` line and `GET /api/build` carries the summary.
- `test_auto_build_tasks_run_at_task_level_auto_and_gated_ones_do_not` (D9): the same project at `gated`: a build at
  `auto` makes tasks with `supervisor.mode == "auto"`; a build at `gated` makes the card's task with the project's mode
  `gated` and it waits at `plan ready: confirm`; `POST /api/config/models {supervisor_projects: {<project>: "auto"}}`
  then a new task from a card of that build is `auto` and has no plan hold; the project's config entry is never written
  by the build.
- `test_start_and_run_the_rest_makes_an_auto_task`: `POST /api/build/level {level: auto}` while item 1 is `ready`, then
  the card's ordinary Start -> the task's mode is `auto` (the `_build_mode` rule), the build is `auto`.
- `test_auto_waits_when_not_acceptable`: a done task with an open question (`tests/fake_claude.py` gains one word,
  `QUESTION-OPEN` with HANDOFF-OK: the block's Open questions carries one line, listed in the file's docstring) -> the
  build waits `sub-plan 1 done: Accept (1 open question)`; Fred's Accept moves on.
- `test_auto_waits_for_the_brief_and_the_done_wake`: with `Hub.briefing` holding the task id, then with `Hub.wakes`
  holding it, the build waits with `brief writing` / `supervisor pass pending` and the lever is not called; when both
  clear it accepts.
- `test_accept_refused_by_pending_guidance_waits_with_the_reason` (F17): a queued guidance message on the done task ->
  `task_lever` answers 409; the build waits `sub-plan 1 done: Accept (Resolve pending guidance first...)`; five more
  ticks call the lever zero more times (`mock.patch.object(hub, "task_lever", wraps=...)` count 1); cancelling the
  guidance changes `updated`, and the next tick accepts.
- `test_drift_major_holds_an_auto_build`: `PLANNER-DRIFT-MAJOR` in the heading: item 1 `held` `drift major: fake
  planner: the queue moved`, the build waiting; `/api/build/continue` starts the task from the saved card; at gated
  the same heading only puts the note on the card and the item is `ready`.
- `test_planner_failure_holds_an_auto_build_and_shows_on_a_gated_card` (F19): `PLANNER-FAIL` in the heading: at `auto` item
  1 `held` `planner failed: ...`, build waiting, Continue starts Prep's steps; at `gated` the card lands (`ready`) with
  `planner.error` set and no hold; an answer without drift keys (not an error) reads `none` and does not hold.
- `test_prep_failure_holds_then_continue_preps_again`: a Prep job that raises (mock `prep.run_prep` once) -> `held`
  `prep failed: ...`; continue -> a new job.
- `test_a_limit_error_in_prep_is_not_retried_by_the_build` (F6): the mocked Prep raises "You've hit your limit"; the item
  is held and 10 more ticks start no second job; no `limit_stuck` call is made.
- `test_cap_holds_before_the_next_item`: cap 0.01 with item 1 accepted at cost 0.02 -> `waiting` `cap: $0.02 of $0
  spent` before item 2 preps; `/api/build/cap 5` -> running, item 2 preps.
- `test_skip_stop_pause_resume_delete`: skip a later item; skip the current ready item (its job dropped); stop while
  the task runs (the task is stopped, the build stopped, the item keeps its task); start again -> the same item
  continues through the task's own Retry (the build does not start a new task while the item has one); pause ->
  after the item closes the build waits `paused after 01`; resume; delete refused while running, allowed when
  stopped, the tasks stay.
- `test_drop_holds_the_item` (F16): Drop on a `ready` card (`POST /api/prep/drop`) -> `held` `card dropped by Fred`, no
  new job after 10 ticks; Continue preps again; running the card as a chat (`/api/run` with the prep id) holds it too.
- `test_restart_preps_again` (F1): a `preparing` item with no saved card, a new Hub on the same folder -> the old prep
  folder is discarded, a new job starts with the `prep again` line.
- `test_restart_reseats_a_saved_card` (F1) and `test_restart_reseats_a_ready_card` (F2): a card saved by `prep.save`
  and a `preparing` / `ready` item, a new Hub -> `hub.preps[prep]` is a done job with that card on the first tick, no
  `claude` call is made (the fake counts zero), the `recovered:` line is written, and a `ready` item is startable from
  the card through the ordinary route.
- `test_restart_after_the_orphan_prune_preps_again` (F2): the same with the card's folder removed (`prep.prune_orphans`
  with a clock three days on): a `ready` item is held `card gone`, Continue preps again.
- `test_restart_links_a_task_a_crash_left` (F3): `create_task` run, then the build's own save made to fail once
  (`mock.patch.object(build, "save", side_effect=OSError)`); a new Hub on the same folder -> the tick links the task
  (`started by Fred on the card, recovered`), starts no second task, and the item is `running`.
- `test_restart_mid_task_keeps_the_item` (F4): a new Hub while the task is on step 2: `retried`, `current`, the cap and
  the item survive; the chain resumes as plan 17 does; no second Prep.
- `test_task_deleted_fails_the_item` (F8): delete the item's done task through `/api/tasks/delete` -> item `failed` `task
  deleted`, build waiting; continue preps again.
- `test_deleting_an_accepted_task_keeps_files_and_questions` (F8): accept item 1, delete its task, item 2's prompt still
  lists `- 1 First: accepted; files ...` and the open question, and `GET /api/build` `summary` reports them.
- `test_a_file_edited_before_its_prep_is_read_live` (F11): edit `02-second.md`'s body between Create and Start: the
  build holds nothing, the titles in build.json are the ones from Create, and item 2's Prep job starts.
- `test_file_edited_after_the_card_is_noted_not_held` (F12): edit the file while the card waits, then Start the card: the
  task is linked, the chain line `file edited after its card` is written, nothing is held, and the Console wrote
  nothing in the project (the file's bytes are the test's).
- `test_missing_file_holds_before_prep` (F12): delete `02-second.md` after Start: item 2 is `held` `file missing:
  plans/02-second.md`, build waiting; restoring the file and Continue preps.
- `test_project_unavailable_waits_and_resumes` (F13): rename the project folder (or drop it from `hub.cfg["projects"]`)
  while item 1 is `preparing`: the build is `waiting` `project: ...`, no job starts, nothing is lost; restoring it sets
  the build `running` on the next tick.
- `test_second_live_build_in_a_project_is_refused_at_start` (F14): two builds on one project; Start of the second is 409
  naming the first while the first is `running`; after the first is stopped, the second starts; a `done` or `planned`
  one never blocks.
- `test_a_failed_save_is_logged_and_the_next_tick_saves` (F15): `build.save` raises once inside a tick: `console.log` has
  `build tick failed`, the hub loop goes on, and the next tick writes the same state.
- `test_a_nested_tick_does_not_retry_twice` (F18): with the D8 setup, `task_lever(retry)` calls `advance` inside the tick;
  `retried == 1`, exactly one `retry` chain line on the task, and `_build_tick` ran its body once.
- `test_limit_retry_once` (D8, F5): a task stuck with `why` "claude: usage limit ..., until 08:00 (after one retry)" and
  `hub.limits` holding an expired entry for `claude` -> one `task_lever retry` (origin build; the task chain says `retry
  by the build after the limit reset`), `retried == 1`; stuck again -> nothing more.
- `test_limit_retry_waits_for_the_reset` (F5): the same with an unexpired entry -> no retry; after the entry's `until`
  passes (a fake clock on the dict) -> one retry. A step that never started (no `limit` of its own, the stuck from
  `start_step`'s `rung_ok`) is retried by the key in its why.
- `test_row_follows_a_task_hold_and_the_build_stays_running` (F7): a task `waiting` `claude-opus ... over its pace`:
  the build is `running`, its row line starts `build · 1 of 2 · 01` and carries the hold, group `needs`; no lever call.
- `tests/test_server.py::test_task_lever_origin_build_words`: `origin="build"` writes `by the build` and never calls
  `_supervisor_fred`.
- `test_build_actions_per_state`: one fake build per state of the `build_actions` table; the listed ids, tags and
  posts; every `post` is a route `do_POST` serves; two GETs start nothing and leave `build.json` byte-identical.
- `test_snapshot_builds_rows_and_counts`: `GET /api/state` `builds` rows, `counts.needs` includes a waiting build, a
  build whose task is past `DONE_DAYS` still has a row.
