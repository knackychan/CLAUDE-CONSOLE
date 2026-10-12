# Task 3: Every attempt recorded, costs summed, a paused task closes an ended step

> Contract: [README.md](README.md) 3.1, 3.2. Findings A4, A5, A6. Depends on Task 1 (`cap=`).

**Files**
- Modify: `console/tasks.py`, `console/server.py`, `tests/test_tasks.py`, `tests/test_server.py`

## 3.1 Evidence

- A5: `20261012-124746-9a3e` step 1 was stopped: `cost` stayed 0 in task.json while its stream had 0.127 USD. The
  stop path (`Hub.task_lever` -> `tasks.fred`) never sets a cost, and the cost only lands with `run_ended`, after
  the Stop. `20261012-122014-915f` step 1 ran twice (no HANDOFF block, then a retry): `cost` 0.142 is the second
  session's only, because `Hub._ended` sets `cs["cost"] = s["cost"]` of the current session.
- A6: the same step's first session (`89444ba8...`) is named nowhere in task.json (`session` holds the retry's), so
  `tasks.clear` cannot return it and its `runs/<sid>.jsonl` stays.
- A4: `_advance_one` returns at once when `owner != "service"`, so a step that ended while paused stays `running`
  with no note, brief or chain line until Resume (`20261012-124746-9a3e`: the step ended during the pause, the
  `running -> done` line is one second after `resumed by Fred`).

## 3.2 `console/tasks.py`

- `_blank` adds `"attempts": []`. `STEP_KEYS` is frozen to the plan 17 keys so old task.json files stay whole:
  `STEP_KEYS = tuple(k for k in _blank(0, "", "") if k != "attempts")`.
- `attempts(step: dict) -> list`:

```python
def attempts(step: dict) -> list:
    """Every session the step ran in, oldest first. A step from before plan 19 has no list: its one session."""
    if step.get("attempts"):
        return step["attempts"]
    if not step.get("session"):
        return []
    return [{"session": step["session"], "cost": step.get("cost") or 0, "started": step.get("started"),
             "ended": step.get("ended"), "why": "", "final": True}]
```

- `start_step` (the pure one) appends `{"session": session, "cost": 0, "started": now, "ended": None, "why": "",
  "final": False}` to `s.setdefault("attempts", [])` after `attempts(s)` has been copied in for an old step
  (`s["attempts"] = list(attempts(s))` first, so an old step's earlier session is kept).
- `_finish(task, s, state, now, lines, why="")` also sets the last attempt's `ended = now` and `why = why`
  (when the step has attempts).
- `step_cost(step) -> float`: `round(sum(a["cost"] or 0 for a in attempts(step)), 6)`.
- `clear` returns `list(dict.fromkeys(a["session"] for s in task["steps"] for a in attempts(s) if a["session"]))`.

Tests (`tests/test_tasks.py`):

```python
    def test_start_step_records_each_attempt(self):
        task = make(("code",))
        run(task, 1)
        end(task, ok=True, block_error="no HANDOFF block")  # retry
        tasks.start_step(task, 1, "s-two", {"model": "sonnet", "effort": "medium", "notes": []}, "", NOW + 5)
        a = tasks.step(task, 1)["attempts"]
        self.assertEqual([x["session"] for x in a], [a[0]["session"], "s-two"])
        self.assertEqual((a[0]["why"], a[0]["ended"] is not None, a[1]["ended"]), ("no HANDOFF block", True, None))

    def test_old_step_without_attempts_reads_as_one(self):
        old = {"session": "s1", "cost": 0.2, "started": 1.0, "ended": 2.0}
        self.assertEqual(tasks.attempts(old), [{"session": "s1", "cost": 0.2, "started": 1.0, "ended": 2.0,
                                                "why": "", "final": True}])
        self.assertEqual(tasks.attempts({"session": ""}), [])
        task = make(("code",))
        for s in task["steps"]:
            del s["attempts"]
        self.assertTrue(tasks.whole(task))

    def test_clear_returns_every_attempt_session(self):
        task = make(("code",))
        run(task, 1)
        end(task, ok=True, block_error="no HANDOFF block")
        tasks.start_step(task, 1, "s-two", {"model": "sonnet", "effort": "medium", "notes": []}, "", NOW + 5)
        first = tasks.step(task, 1)["attempts"][0]["session"]
        with tempfile.TemporaryDirectory() as home:
            tasks.save(home, task)
            self.assertEqual(tasks.clear(home, task, keep_last=False), [first, "s-two"])
```

(`run` and `end` are the helpers at lines 237 and 242; `end` forwards keywords to `on_step_ended`. Use the
session id `run` gives in place of `a[0]["session"]` if it is fixed there.)

## 3.3 `console/server.py`

- `Hub.sync_costs(task) -> bool`: for every attempt of every step with `final` false and a session: when the
  run has ended (`self.runs.meta(sid)` has `ended`, or there is no meta and the session row is not `run_live`)
  and the session row exists, set `cost = row["cost"]` and `final = True`; then `step["cost"] = tasks.step_cost(step)`
  for that step. Returns True when anything changed. No chain line (a cost is not a transition).
- `_advance_one(task)`: first `if self.sync_costs(task): self._commit(task)`; then, before the owner check:

```python
        cs = tasks.current_step(task)
        if task["owner"] == "fred" and task["state"] in ("running", "waiting") and cs and cs["state"] == "running":
            return self._ended(task, cs)  # paused: the step that ended is closed; nothing starts after it (A4)
```

- `_ended`: drop `cs["cost"] = s["cost"]`; call `self.sync_costs(task)` before `self._commit(task, lines)`; the
  `_go_on` at its end runs only when `task["owner"] == "service"`.
- `_go_on`: return `""` at once when `task["owner"] != "service"` (before the Fable check, so a paused task never
  turns `waiting` on `confirm Fable`).
- `task_row`: `"cost": round(sum(tasks.step_cost(s) for s in t["steps"]), 4)`; each step row adds
  `"attempts": [{"session": a["session"], "cost": a["cost"], "why": a["why"]} for a in tasks.attempts(s)]`.

Tests (`TaskServerTest`; the fake's result costs 0.01 per run, an interrupt's too):

```python
    def test_retry_sums_the_cost_of_both_attempts(self):
        tid = self.make_task(words="", steps=[{"kind": "scout", "goal": "look"}])  # no HANDOFF: retry, then stuck
        task = self.until(tid, lambda t: t["state"] == "stuck", "stuck after the retry")
        self.until(tid, lambda t: all(a["final"] for a in t["steps"][0]["attempts"]), "both costs in")
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual(len(step["attempts"]), 2)
        self.assertAlmostEqual(step["cost"], 0.02)
        row = next(r for r in self.hub.snapshot()["tasks"] if r["id"] == tid)
        self.assertEqual(len(row["steps"][0]["attempts"]), 2)

    def test_stopped_step_gets_its_cost(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "SLOW look"}])
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.call("/api/task/stop", {"task": tid})
        self.wait_idle(sid)
        task = self.until(tid, lambda t: t["steps"][0]["attempts"][0]["final"], "the stopped run's cost")
        self.assertAlmostEqual(task["steps"][0]["cost"], 0.01)

    def test_clear_removes_every_attempt_stream(self):
        tid = self.make_task(words="", steps=[{"kind": "scout", "goal": "look"}])
        task = self.until(tid, lambda t: t["state"] == "stuck", "stuck after the retry")
        sids = [a["session"] for a in task["steps"][0]["attempts"]]
        for sid in sids:
            self.wait_idle(sid)
        self.assertEqual(self.call("/api/task/clear", {"task": tid})[0], 200)
        for sid in sids:
            self.assertFalse(self.hub.runs.stream_path(sid).exists(), sid)

    def test_pause_closes_an_ended_step(self):
        tid = self.make_task(steps=self.TWO)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.call("/api/task/pause", {"task": tid})
        self.wait_idle(sid)
        task = self.until(tid, lambda t: t["steps"][0]["state"] == "done", "step 1 closed while paused")
        self.assertEqual((task["owner"], task["steps"][1]["session"]), ("fred", ""))
        self.assertTrue((self.folder / "tasks" / tid / "steps" / "01-scout.md").exists())
        self.until(tid, lambda t: not t.get("briefing"), "the brief ran while paused")
        self.assertEqual(self.hub.advance(), [])  # nothing starts while paused
        self.call("/api/task/resume", {"task": tid})
        self.until(tid, self.at(2), "step 2 starts after Resume")
```

`test_pause_and_resume` asserts `self.hub.advance() == []` right after the step finished; with A4 that pass
closes the step. Change its middle to: `self.until(tid, lambda t: t["steps"][0]["state"] == "done", "closed")`,
then `self.assertEqual(len([s for s in self.hub.tasks[tid]["steps"] if s["session"]]), 1)`. `words=""` in the
new tests: if `post_task` puts the words on a line of their own, an empty string must leave no `HANDOFF-OK`
(it does: `f"{card['prompt']}\n{words}".strip()`). The brief thread of the pause test needs the hub's brief to
finish: `until` polls, and `_brief_done` clears `briefing`.

## 3.4 Order (one commit per step)

1. 3.2 tests, fail; `attempts`, `_blank`, `STEP_KEYS`, `start_step`, `_finish`, `step_cost`, `clear`; suite;
   commit `feat: every attempt of a step is recorded (plan 19 Task 3)`.
2. Cost and Clear server tests, fail; `sync_costs`, `_ended`, `task_row`; suite; commit.
3. Pause test, fails; `_advance_one`, `_go_on`, the changed `test_pause_and_resume`; suite; commit.
4. plans/17-tasks/README.md 3.7: add the paused row and point to this plan (one line each); PLAN.md History
   line; commit.
