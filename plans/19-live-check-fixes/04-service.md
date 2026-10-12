# Task 4: What the window needs from the service

> Contract: [README.md](README.md) 3.2 (the hold row), 3.4. Findings A7 (D3 a), A8 hold (D5 a), B2, B3 (D7 a),
> B6 (the header count). Depends on Task 3 (`tasks.attempts`).

**Files**
- Modify: `console/server.py`, `console/state.py`, `console/tasks.py`, `console/transcript.py`
- Modify: `tests/test_server.py`, `tests/test_state.py`, `tests/test_tasks.py`, `tests/test_transcript.py`

## 4.1 Fable needs a confirm on `/api/run` (A7, D3 a)

`Handler._run`, after the `known_model` check:

```python
        if claude_cli.tier_of(model) == "fable" and body.get("fable_ok") is not True:
            return self._error(409, "confirm Fable: it may bill usage credits on this plan")
```

With D3 (b) instead: no server change; Task 6 leaves `fable` out of `#p-model`.

```python
    def test_fable_run_needs_the_confirm(self):  # in RunServerTest
        body = {"project_dir": str(self.project), "prompt": "hi", "model": "fable", "effort": "low"}
        status, data = self.call("/api/run", body)
        self.assertEqual((status, data["error"]), (409, "confirm Fable: it may bill usage credits on this plan"))
        status, data = self.call("/api/run", dict(body, fable_ok=True))
        self.assertEqual(status, 200, data)
```

(`self.call` returns `(status, body)`; use the class's real project attribute name. If `RunServerTest`'s tests are
excluded from `TaskServerTest` by the loop at the end of the file, nothing else is needed.)

## 4.2 Run anyway for a budget hold (A8, D5 a)

- `tasks.fred(task, lever, now, next_n: int = 0)`: `confirm` applies when `state == "waiting"` and
  (`why == "confirm Fable"` or `why.endswith(" over its pace")`). For a hold it sets `task["hold_ok"] = next_n`
  (Fable sets `fable_ok` as before); then the task goes `running`.
- `Hub.task_lever`: passes `next_n=(self._next_step(task) or {}).get("n", 0)`.
- `Hub.task_levers`: `confirm` is `""` for both whys; `start` treats a `waiting` task with a hold `why` like the
  Fable confirm (start is computed, the hub loop does not start it: `_advance_one` returns on `waiting`).
- `Hub.start_step`: `if route["hold"] and task.get("hold_ok") != n:` waits as now; when `hold_ok == n` it starts
  with `route["notes"] + ["budget: hold released by Fred"]` and clears `hold_ok` after the start.

```python
    def test_budget_hold_released_by_confirm(self):
        self.hub.budget = self.over("opus")
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])
        self.until(tid, lambda t: t["state"] == "waiting", "the verify holds")
        self.assertEqual(self.hub.task_levers(tid)["confirm"], "")
        self.assertEqual(self.call("/api/task/confirm", {"task": tid})[0], 200)
        task = self.until(tid, self.at(2), "the verify starts")
        step = task["steps"][1]
        self.assertEqual(claude_cli.tier_of(step["model"]), "opus")  # a rung under the fake budget is fine
        self.assertIn("budget: hold released by Fred", step["notes"])
        self.assertNotIn("hold_ok", task)
```

Unit test in `tests/test_tasks.py` `test_fred_confirm_releases_a_hold`: a task `waiting` with
`why = "opus over its pace"`: `tasks.fred(task, "confirm", NOW, next_n=2)` returns `(True, "", lines)`,
`task["hold_ok"] == 2`, `task["fable_ok"]` stays False, state `running`.

## 4.3 Counts with tasks (B6, the header)

`Hub.snapshot`, after `snap["tasks"]`:

```python
            rows = snap["sessions"]
            loose = [r for r in rows if not r.get("task")]
            count = lambda g: sum(1 for r in loose if r["group"] == g)
            tg = lambda states: sum(1 for t in snap["tasks"] if t["state"] in states)
            snap["counts"] = {"needs": count("needs") + tg(("waiting", "stuck")),
                              "replied": count("replied"), "working": count("working") + tg(("planned", "running")),
                              "done": count("done"), "empty": count("empty")}
```

A done or stopped task is not counted (the list keeps it a day; the header only counts what needs Fred or works).
The tray's `look(counts)` reads the same dict, so its colour and tooltip follow.

```python
    def test_counts_fold_task_steps_into_their_task(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "STOP-ASK look"}])
        self.until(tid, lambda t: t["state"] == "waiting", "the step asks")
        counts = self.hub.snapshot()["counts"]
        self.assertEqual(counts["needs"], 1)  # the task, not also its step session
        self.assertEqual(counts["working"], 0)
```

(If `STOP-ASK` has to ride in the prompt rather than the goal, put it in `words=`.)

## 4.4 Model versions (B3, D7 a)

`console/state.py`:

```python
_FULL = re.compile(r"claude-(fable|opus|sonnet|haiku)-(\d+)(?:-(\d{1,2}))?(?:-|$)")


    def versions(self) -> dict:
        """family -> the newest version seen in a full model id ("5.5"), from every session in memory; an alias
        alone says nothing, a family never seen is left out."""
        best = {}
        for s in self.sessions.values():
            m = _FULL.match(s.model or "")
            if m:
                v = (int(m.group(2)), int(m.group(3) or 0))
                best[m.group(1)] = max(best.get(m.group(1), v), v)
        return {fam: f"{a}.{b}" for fam, (a, b) in best.items()}
```

A version without a minor shows `.0` (none is expected). `State.snapshot` adds `"versions": self.versions()`. A date suffix
(`claude-haiku-4-5-20251001`) is handled by `(?:-|$)`.

```python
    def test_snapshot_versions_from_seen_models(self):  # tests/test_state.py
        st = State(...)  # as the other snapshot tests build it
        for sid, model in (("a", "claude-opus-5-5"), ("b", "claude-opus-4-8"), ("c", "sonnet"),
                           ("d", "claude-haiku-4-5-20251001"), ("e", "claude-fable-5-1")):
            ...  # one SessionStart-like event per session with that model, as the file's helpers do
        self.assertEqual(st.snapshot(NOW)["versions"], {"opus": "5.5", "haiku": "4.5", "fable": "5.1"})
```

(The test file has helpers that feed events; use them. `sonnet` alone adds nothing.)

## 4.5 An older step's transcript (B2)

`console/transcript.py`:

```python
def find(root, session_id: str):
    """The transcript of a session by its id under ~/.claude/projects (any project folder); None when not found."""
    if not re.fullmatch(r"[0-9a-f-]{8,64}", str(session_id or "")):
        return None
    hits = sorted(Path(root).glob(f"*/{session_id}.jsonl"))
    return hits[0] if hits else None
```

`Handler._chat`: when there is no meta and `self.hub.session(sid)` is None, `path = transcript.find(
self.hub.user_home / ".claude" / "projects", sid)`; items from `transcript.turns(path)` when found, else `[]`.

```python
    def test_find_by_id(self):  # tests/test_transcript.py
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "D--WORK-APP" / "0b1c2d3e-aaaa-bbbb-cccc-111122223333.jsonl"
            p.parent.mkdir()
            p.write_text("", encoding="utf-8")
            self.assertEqual(transcript.find(root, "0b1c2d3e-aaaa-bbbb-cccc-111122223333"), p)
            self.assertIsNone(transcript.find(root, "../x"))
            self.assertIsNone(transcript.find(root, "0b1c2d3e-0000-0000-0000-000000000000"))
```

Server test `test_chat_of_an_unknown_session_reads_its_transcript`: write a one-turn transcript (the format the
other transcript tests use) under `self.hub.user_home / ".claude" / "projects" / "X" / "<id>.jsonl"` for an id with
no event and no run; `GET /api/chat?session=<id>` returns its turn with `source` `transcript`.

## 4.6 `/api/config` and the task row

- `GET /api/config` adds `"edit_kinds": sorted(tasks.EDIT_KINDS)` (Task 5 draws the Console's verify row when an
  edit kind is in the list). Extend the existing config test with one assertion.
- `task_row` adds `"paused_after"`: `cs["n"]` when `t["owner"] == "fred"` and `t["state"] in ("running",
  "waiting")` and `cs` and `cs["state"] != "running"`, else 0; and `"hold": t["why"].endswith(" over its pace")`.
  Extend `test_pause_closes_an_ended_step` (Task 3) with `row["paused_after"] == 1`.

## 4.7 Order (one commit per step)

1. 4.1 test, fails; guard; suite; commit `feat: a Fable run needs a confirm (plan 19 Task 4)`.
2. 4.2 tests, fail; `fred`, `task_lever`, `task_levers`, `start_step`; suite; commit.
3. 4.3 test, fails; counts; suite (the tray tests too); commit.
4. 4.4 test, fails; `versions`; suite; commit.
5. 4.5 tests, fail; `find`, `_chat`; suite; commit.
6. 4.6 assertions, fail; config key, row keys; suite; commit; PLAN.md History line; commit.
