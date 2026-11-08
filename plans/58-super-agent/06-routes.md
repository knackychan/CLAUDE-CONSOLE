# Task 6: GET /api/super and POST /api/super

> Contract: [README.md](README.md) 3.9, 3.10; decision D6. The GET is the data contract slice 2's window reads: it
> may grow fields later, never lose these. It starts nothing and writes nothing.

**Files**
- Modify: `console/server.py` (`Hub.super_view`, `Hub.super_action`, one GET line, one POST route, one handler;
  other chats edit this file: stage only this task's hunks, README rules)
- Modify: `tests/test_superagent_server.py` (`SuperRouteTest`)

Commit boundary: `feat: GET and POST /api/super (plan 58 T6)`.

## 6.1 `console/server.py`

In the plan 58 section of `Hub`, after `_super_done`:

```python
    def super_view(self) -> dict:
        """GET /api/super (README 58 3.9): the queue as the last ok pass ranked it, or unranked with why. Starts
        nothing and writes nothing."""
        now = self.super_clock()
        limits, errors = superagent.settings(self.cfg)
        with self.tlock:
            snap = self.snapshot()
            live = superagent.items(snap, self.tasks)
            rows = {r["id"]: r for r in snap.get("tasks") or []}
            sessions = {r["id"]: r for r in snap.get("sessions") or []}
            described = [self._super_describe(item, rows, sessions, now) for item in live]
            state = copy.deepcopy(self.super)
            busy, wake = self.super_busy, self.super_wake
        day = usage.day_of(now)
        settled, active = usage.super_spent(self.folder, day)
        ranked, why = superagent.status(limits, errors, state, settled + active, bool(self.runs.exe))
        q = superagent.queue(described, state, now, ranked)
        queued = [i for card in q["queue"] for i in card["items"]]
        today = supervisor.spend_view(usage.load_super(self.folder)["records"])["days"].get(day, {})
        return {"state": "ranked" if ranked else "unranked", "why": why, "paused": state["paused"],
                "sorting": {"n": busy["n"], "items": len(busy["handles"]), "since": busy["at"]} if busy else None,
                "due": max(0, round(wake["due"] - now)) if wake else None,
                "queue": q["queue"], "later": q["later"], "digest": state["digest"] if ranked else [],
                "notes": superagent.read_notes(self.folder), "orders": superagent.read_orders(self.folder),
                "last": state["last"],
                "spend": {"today": round(settled + active, 6), "passes": today.get("runs", 0),
                          "day_limit": limits["super_day_usd"], "pass_limit": limits["super_pass_usd"]},
                "counts": {"queue": len(queued), "later": len(q["later"]),
                           "always": sum(1 for i in queued + q["later"] if i["always"]),
                           "new": sum(1 for i in queued if i["new"])}}

    def super_action(self, body) -> tuple:
        """POST /api/super (README 58 3.10): pause, resume or sort. (status, data); data is the GET view on 200."""
        action = body.get("action") if isinstance(body, dict) and set(body) == {"action"} else None
        if action not in ("pause", "resume", "sort"):
            return 400, {"error": "action: pause, resume or sort"}
        now = self.super_clock()
        with self.tlock:
            if action == "sort" and self.super["paused"]:
                return 409, {"error": "paused: resume first"}
            if action == "pause":
                self.super["paused"] = True
                self.super_wake = None  # a running pass finishes; its answer is kept
            else:
                self.super["paused"] = False
                self._super_arm(now, [("asked", action)], at_once=True)
            self._super_log({"phase": action, "by": "fred"})
            self._super_save()
        with self.lock:
            self.version += 1
            self.changed.notify_all()
        return 200, self.super_view()
```

`Handler.do_GET`, after the `/api/usage` line:

```python
        if url.path == "/api/super":  # plan 58: the super agent's queue, read only
            return self._json(self.hub.super_view())
```

`Handler.do_POST`, after `routes["/api/task/supervisor/replay"] = ...`: `routes["/api/super"] = self._super`, and in
the POST handlers after `_task_supervisor_replay`:

```python
    def _super(self, body):
        status, data = self.hub.super_action(body)
        return self._json(data, status)
```

`super_view` reads the task rows through `snapshot()` and each task's card line through `Hub.actions` (read only, as
GET /api/task does); it holds `tlock` only to copy the state and describe the items, then reads the ledger and the
two text files outside it.

## 6.2 Tests first (red before the code)

`SuperRouteTest(test_server.RunServerTest)` in `tests/test_superagent_server.py` (`from tests import
test_server`): the real fake claude, the hub loop not started; `setUp` calls `super().setUp()` and sets
`self.hub.cfg["super_debounce_s"] = 0`, so one `self.hub._super_tick()` arms and admits a pass at once; a `pass_()`
helper ticks, asserts True and joins `self.hub.super_threads` (30 s). Tasks come from Task 5's module function
`make_task(self.hub, self.project, n, ...)`. The class keeps `RunServerTest`'s `supervisor_mode` `off`, so every level
reads `off`.

- `test_get_super_ranks_after_a_fake_pass`: task 1 waiting `plan ready: confirm`, task 2 waiting `confirm Fable`.
  GET `/api/super` before any tick: 200, `state` `unranked`, `why` `no pass yet`, `paused` False, `sorting` None,
  `due` None, the queue cards `[task 2], [task 1]` (always first), task 2's item `always` `"Fable confirm"`, `ask`
  `"held · confirm Fable"`, `level` `off`, `kind` `hold`, `new` False, `say` `""`; task 1's `ask` `"plan ready ·
  confirm"`; `digest` `[]`; `last` None; `counts` `{"queue": 2, "later": 0, "always": 1, "new": 0}`. Then `pass_()`
  and GET: `state` `ranked`, `why` `""`; cards `[task 2], [task 1]`; task 1's `say` `"fake: I2"` and `rank` 1, task
  2's `say` `"fake: I1"` and `do` `forward`; `digest` `["fake digest: 2 items"]`; `notes` starts `"fake notes\n# Super
  agent pass 1 · "`; `last` has `n` 1, `ok` True, `model` `haiku`, `cost` 0.003, `items` 2; `spend` `{"today": 0.003,
  "passes": 1, "day_limit": 1.0, "pass_limit": 0.2}`; `last-prompt.md` exists and the claimed line's `prompt_hash` is
  its SHA-256. Task 3 added, GET without a tick: its card comes last with `new` True and `counts["new"]` 1.
- `test_super_error_leaves_the_queue_unranked_and_keeps_the_cost`: `super/orders.md` holds `SUPER-ERROR`; task 1
  waiting; `pass_()`; GET: `state` `unranked`, `why` `"the pass failed: error_max_turns"`, every `say` `""`, `last`
  `ok` False with `cost` 0.02; GET `/api/usage` `super.today` has `cost` 0.02 and `runs` 1. With `SUPER-BAD` instead
  (a fresh folder): `why` `"the pass gave no answer (items is missing or not a list)"`.
- `test_super_later_and_unknown_handles`: orders `SUPER-LATER SUPER-UNKNOWN`, tasks 1 and 2: after `pass_()`, the
  item that was `I1` sits in `later` with `why` `"fake: it can wait"` and a non-empty `until`; `counts["later"]` 1;
  the result line's `dropped` is `[{"at": 2, "why": "unknown handle I99"}]`.
- `test_post_super_pause_resume_and_sort`: a POST without `X-CC` is 403; `{"action": "nap"}`, `{}` and `{"action":
  "sort", "x": 1}` are 400 `{"error": "action: pause, resume or sort"}`. `pause`: 200, `paused` True, `state`
  `unranked`, `why` `paused`; the last `super.jsonl` line has `phase` `pause` and `by` `fred`; `state.json` has
  `paused` true. `sort` while paused: 409 `{"error": "paused: resume first"}`. `resume`: 200, `paused` False, `due` 0.
  With task 1 waiting, `pass_()` runs one pass whose prompt (`last-prompt.md`) holds `"Triggers: 1 new item, asked"`.
  Then `sort`: 200 and `due` 0; the next `pass_()` has `"Triggers: asked"`.
- `test_get_super_starts_nothing_and_writes_nothing`: tasks 1 and 2 waiting, no tick; with `paths.write_text_atomic`
  and `superagent.append_log` patched to fail the test, three GETs of `/api/super` answer 200; `hub.super_threads` is
  `[]`, `hub.super_wake` None; no `super/` folder and no `super` section in usage-days.json exist.
- `test_usage_report_has_the_super_agent`: GET `/api/usage` before any pass has `super` `{"days": {}, "today":
  {"cost": 0.0, "runs": 0, "unknown": 0, "reserved": 0.0}, "day_limit": 1.0, "pass_limit": 0.2, "error": ""}`; after
  one `pass_()`, `super.today` has `runs` 1 and `cost` 0.003, and the `supervisor` block is unchanged (no runs).

## 6.3 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_superagent_server`: red for the missing route and methods.
- [ ] 2. Make the 6.1 edits. Focused tests green; `tests/test_server.py` green (`RunServerTest` unchanged).
- [ ] 3. Full suite green (report the count). Stage the test file by path and only this task's hunks of
      `console/server.py` (non-interactive staging, README rules). Commit with the message above.
