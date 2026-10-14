# Task 4: The service: fills, the balanced rung, the other harnesses' runs

> Contract: [README.md](README.md) 3.3, 3.5, 3.7, 3.8, 3.9. Depends on Tasks 1, 2, 3. Decision D3 (`count_run`'s
> unknown run, `fill_marks`' unknown list).
> Run in a scratch copy on 2026-10-14 against today's `server.py` (plan 5 not placed: `Hub.rung_ok` was the two-line
> shim `"" if claude_cli.known_model(self.cfg, rung) else "unknown model or effort"`): `tests/test_server.py` 87 OK
> (84, one test removed, four added); the full suite 362 run, only the four failures of this box. `PlanFiveTest`
> (4.6) needs plan 5's `harness` module and was not run there.
> Lands on: plan 5 Task 5 (`Hub._route_for`'s `pick=claude_cli.tier_of(...)`, `Hub.start_step`'s model line and
> its `rung_ok` fallback with the note `harness: codex off -> sonnet`; plan 5's test
> `test_step_pick_falls_back_when_harness_off`), plan 24 Task 3 (`Hub.start_step`'s `max_turns` line, which this task
> leaves as plan 24 wrote it; `Hub._replan_job`'s `self.model_id` line), plan 23 Task 5 (`Hub.start_step`'s prompt
> lines and `read_max_turns`, left as plan 23 wrote them; `Hub._brief_job`, whose signature gained `touched` and whose
> `run_brief` call passes it: this task replaces only its first two lines and keeps plan 23's; the `/api/config` dict,
> which gained `handoff_auto` after `edit_kinds`: 4.6 inserts before it; `Hub.__init__`, which gained `auto_handed`:
> this task's line still goes after `self.usage_days`). Plan 24 Task 3 also edits `Hub.task_levers` (`answer`, `redo`,
> `keep`): this task changes only its `"next_route"` line.

**Files**
- Modify: `console/server.py` (the import line; `Hub.__init__`, `poll_once`, new `count_run`, `usage_report`,
  `snapshot`, new `fill_marks`, `budget`, new `tier_view`, `tier_budget` and `model_id` removed, `_route_for`,
  `task_levers`' `next_route`, `start_step`, `_brief_job`, `_replan_job` (plan 24), `/api/config`)
- Modify: `tests/test_server.py` (the import line; `over`; `test_budget_hold_waits_for_fred`; the three `skip`
  decorators of Task 2 removed; `test_rung_under_budget_pressure` replaced by four tests; plan 5's
  `test_step_pick_falls_back_when_harness_off`)
- Modify: `tests/test_fills.py` (class `PlanFiveTest`, before `if __name__`)

`Hub.rung_ok(rung, kind="")` is plan 5's (Task 5): `""` when the rung can run on that kind, else the reason. This
task only calls it.

## 4.1 Imports and `Hub.__init__`

Add `fills` to the `from . import (...)` list of `console/server.py`, in alphabetical order (after `events`).

In `Hub.__init__`, after `self.usage_days = {}  # day -> totals: ...`:

```python
        self.usage_other = usage.load_other(folder)  # plan 18: day -> {model key: runs of other harnesses}
```

## 4.2 The other harnesses' runs: `poll_once`, `count_run`

In `Hub.poll_once`, after the `with self.lock:` block that notifies on new records and before `return len(new)`:

```python
        for rec in new:  # plan 18: the fills count other harnesses' runs from their run_ended lines
            if rec.get("event") == "run_ended":
                self.count_run(rec)
```

After `poll_once`, add:

```python
    def count_run(self, rec: dict) -> bool:
        """One ended run of a harness other than Claude (whose transcripts the history prices) into usage-days.json:
        the cost it reported, else its tokens at the price row of its model key, else one unknown run (D-3)."""
        meta = self.runs.meta(rec["session_id"]) or {}
        harness = meta.get("harness") or "claude"
        if harness == "claude" or not meta.get("model"):
            return False
        key = fills.model_key(f"{harness}:{meta['model']}", self.cfg)
        cost = rec.get("cost")
        if not isinstance(cost, (int, float)):
            cost = fills.price(rec.get("tokens"), (self.cfg.get("prices") or {}).get(key))  # D3: None = unknown
        ts = float(rec.get("ts") or time.time())
        if not usage.add_other(self.folder, f"{rec['session_id']}@{ts}", usage.day_of(ts), key, rec.get("tokens"), cost):
            return False
        other = usage.load_other(self.folder)
        with self.lock:
            self.usage_other = other
            self.version += 1
            self.changed.notify_all()
        return True
```

The meta's `model` is the model id without the harness (plan 5 Task 4 writes `harness` and `model` apart), hence the
`f"{harness}:{...}"`. `run_ended.tokens` is plan 5's `{"input", "output", "cache_read"}`.

## 4.3 `usage_report`, `snapshot`, `fill_marks`

Replace the head and the return of `Hub.usage_report` (from `with self.lock:` to the end of the `return`) with:

```python
        with self.lock:
            days, ready, storage, other = self.usage_days, self.usage_ready, self.storage, self.usage_other
        now = time.time()
        today = usage.day_of(now)
        days = fills.merge_other(days, other)  # plan 18: the other harnesses' priced runs and unknown counts
        with self.tlock:
            hours = fills.fail_hours(self.tasks, self.cfg, now)
        return {"ready": ready, "today": today, "first": min(days) if days else "",
                "limit": self.cfg["daily_budget_usd"], "days": days,
                "weeks": usage.weeks(days, today), "months": usage.months(days, today),
                "storage": storage, "storage_warn_mb": self.cfg["storage_warn_mb"],
                "fills": self.budget(), "fail_hours": hours, "warn_at": self.cfg["budget_warn_at"],
                "balance_margin": self.cfg["balance_margin"]}
```

In `Hub.snapshot`, replace the line `snap = self.state.snapshot(now, self.usage, self.usage_days.get(usage.day_of(now)))` with:

```python
            today = usage.day_of(now)
            day = fills.merge_other({today: self.usage_days[today]} if today in self.usage_days else {},
                                    {today: self.usage_other.get(today) or {}}).get(today)
            snap = self.state.snapshot(now, self.usage, day)
```

and its last line `            return snap` (inside the `with self.lock:`) with these two lines, out of the lock:

```python
        snap["spend"]["fills"] = self.fill_marks()  # outside the lock: budget() takes it
        return snap
```

After `snapshot`, add:

```python
    def fill_marks(self) -> dict:
        """The today strip's fills line (plan 18): models at or over budget_warn_at of their pace, over pace first
        by share, and today's unpriced runs per model."""
        warn, over, unknown = self.cfg["budget_warn_at"], [], []
        for key, f in self.budget().items():
            share, today = f.get("share"), (f.get("day") or {}).get("unknown_runs")
            if share is not None and share >= warn:
                over.append([key, share, f.get("binding", "")])
            if today:
                unknown.append([key, today])
        return {"over": sorted(over, key=lambda x: -x[1]), "unknown": unknown, "warn_at": warn}
```

`Hub.lock` is not reentrant: `budget()` takes it, so `fill_marks` runs after the `with` block. Plans 23 and 25 add
keys to the snapshot inside that block; they stay where they are.

## 4.4 `budget`, `tier_view`; `tier_budget` and `model_id` removed

Replace `def budget(self)` (its body returns `{}`), `def tier_budget(self)` and `def model_id(self, tier)` (all
three, whole) with:

```python
    def budget(self) -> dict:
        """Plan 18: model key -> its fills (README 3.3 of plans/18-fills): the day, week and month windows, the one
        that binds and its share of pace. {} until the history thread has read the transcripts once: while usage is
        unknown the tiers' order routes, never a guess of zero."""
        with self.lock:
            if not self.usage_ready:
                return {}
            days, other = self.usage_days, self.usage_other
        return fills.fills(days, other, self.cfg, time.time())

    def tier_view(self) -> dict:
        """/api/config `tiers`: every rung of each tier as config.json lists it, with its rank, model key, whether it
        is hard only, and why it cannot run now ("" when it can). The window hides a rung with a reason."""
        return {tier: [{"rung": r, "effort": e, "rank": fills.rank_of(r, self.cfg), "key": fills.model_key(r, self.cfg),
                        "hard": fills.hard_only(r, tier, self.cfg), "why": self.rung_ok(r)}
                       for r, e in fills.tier_rungs(self.cfg, tier)] for tier in tasks.TIERS}
```

## 4.5 The route: `_route_for`, `task_levers`, `start_step`, `_brief_job`, `_replan_job`

Replace `def _route_for(self, task, s)` whole (plan 5 Task 5 changed its `pick=` to `claude_cli.tier_of(s["pick"],
self.cfg)`; `step_route` now reads a rung's rank itself through `fills.rank_of`, so the pick goes in whole) with:

```python
    def _route_for(self, task: dict, s: dict) -> dict:
        """tasks.step_route for step `s`, with everything it reads: the checked step, the misses, the last note, the
        fills, the previous step's rung and age (the warm-cache bonus), hard (Prep's demand or a hard sub-plan part)
        and the gate on rungs (rung_ok: harness off or not found, not on this kind)."""
        last = tasks.step(task, task["last_good"]) if task["last_good"] else None
        ended = last.get("ended") if last else None
        return tasks.step_route(
            s["kind"], pick=s["pick"], checked=tasks.checked_route(task, s), demand=task["demand"],
            misses=routing.fresh(levers.read_misses(self.folder, task["project"]), self.cfg["miss_floor_days"]),
            prev=tasks.read_note(self.folder, task, task["last_good"]),
            budget=self.budget(), warn_at=self.cfg["budget_warn_at"], effort=task["effort"], cfg=self.cfg,
            prev_rung=last["model"] if last else "", prev_age=time.time() - ended if ended else None,
            hard=(task["demand"] or {}).get("reasoning") == "high" or bool(s.get("hard")),
            refuse=lambda rung: self.rung_ok(rung, s["kind"]))
```

In `Hub.task_levers`, the `"next_route"` line becomes:

```python
                    "next_route": f"{route['rung']}/{route['effort']}" if route and not route["hold"] else "",
```

In `Hub.start_step`, replace from `kind, tier = s["kind"], route["model"]` down to the line before `retry = ...`
(today: the `pick = s["pick"]` comment line and the two-line `model = pick if ... else self.model_id(tier)`; after
plan 5 Task 5 also its `harness, model_id = split_rung(model)` and the `rung_ok` fallback block that adds
`harness: <reason> -> <tier>`) with:

```python
        kind, tier, model = s["kind"], route["model"], route["rung"]  # plan 18: the route chose the rung
        if tier == "fable" and not task["fable_ok"]:  # a hard-only fable rung of the think tier bills credits too
            tasks._task_to(task, "waiting", "confirm Fable", now, s, lines)
            return self._commit(task, lines)
        harness, model_id = claude_cli.split_rung(model)  # plan 5's line, kept
```

`step_route` already refused a rung `rung_ok` refuses (`refuse`), so the fallback has nothing left to catch: a pick
whose harness was turned off since Prep balances inside its rank with the note `pick refused: codex is off ->
balance`. Everything after (plan 23's prompt, plan 24's `max_turns` on `design_max_turns`, plan 5's `harness=` /
`model=model_id` / `read_only`, `tasks.start_step(task, n, sid, dict(route, model=model), ...)`,
`s["tier"] = tier`) stays as those plans wrote it. In the scratch copy (no plan 5) the last line above did not
exist and `self.runs.start` took `model`.

In `Hub._brief_job`, replace its first two lines (`model = self.cfg["brief_model"]` and the `cfg = dict(...,
self.model_id(model) ...)` line) with:

```python
        model, ran = self.cfg["brief_model"], s.get("model") or ""
        if model in claude_cli.MODELS and fills.split_rung(ran)[0] == "claude" and fills.rank_of(ran) == model:
            model = ran  # plan 18 (5.1 item 2): the pass runs on the rung the step used, while its cache is warm
        cfg = dict(self.cfg, brief_model=model)
```

In plan 24's `Hub._replan_job`, replace its first two lines the same way, without a step rung (the pass has no
previous run on that tier):

```python
        cfg = dict(self.cfg)  # plan 18: brief_model as config.json says (a Claude alias runs as given)
```

## 4.6 `/api/config`

In `Handler.do_GET`'s `/api/config` answer, after `"kinds": tasks.PREP_KINDS, "edit_kinds": sorted(tasks.EDIT_KINDS)`
(plans 5, 23, 24 add keys around it; keep theirs), add:

```python
                               "tiers": self.hub.tier_view(),
                               "kinds_tier": {k: tasks.kind_tier(k) for k in tasks.PREP_KINDS},
```

If plan 5 Task 6 already put a `kinds_tier` key in this dict (its window task names one, with the rule's rank as the
value), remove that one: the dict keeps only this key (job tier words; this task's `modelOptions` reads them).

## 4.7 Tests

### `tests/test_server.py`

Import line: add `usage`:

```python
from console import attach, brief, claude_cli, events, guard, levers, paths, server, tasks, usage
```

(after plan 5 the list also holds what plan 5 added; keep it alphabetical.)

Replace `def over(self, tier)` in `TaskServerTest` with:

```python
    def over(self, key):
        """A budget() (plan 18) with one model key at 90 % of its pace, binding on the day."""
        return lambda: {key: {"share": 0.9, "binding": "day", "day": {"unknown_runs": 0}}}
```

Remove the three `@unittest.skip("plan 18 Task 4 rewrites it")` lines Task 2 put on
`test_budget_hold_waits_for_fred`, `test_budget_hold_released_by_confirm`, `test_counts_a_held_task_as_needs`. The
last two run unchanged on the new `over("opus")` (the verify of a code step runs on the opus rank, whose key is over
its pace: the verify holds). In `test_budget_hold_waits_for_fred`, replace its first four lines (to the
`assertIn("budget: opus 90 % ...")`) with:

```python
        self.hub.budget = self.over("opus")
        tid = self.make_task(steps=[{"kind": "design", "goal": "plan it"}])  # over pace no longer moves a step
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual((step["model"], step["tier"], step["effort"]), ("opus", "opus", "high"))
        self.assertIn("balance: every think rung over pace -> opus 90 %", self.session(step["session"])["route_reason"])
```

With plan 5 placed, `rung_ok` refuses the think tier's `codex` and `opencode` rungs (both harnesses off in
`DEFAULTS`); `fable` is hard only and the step is not hard. The pool is `opus` and `claude-opus-4-8`, one model key
over its pace, hence `every think rung over pace -> opus 90 %` (the order breaks the tie). The scratch copy's shim
refused the same rungs (`known_model` knows only Claude rungs) and printed this note.

Remove `test_rung_under_budget_pressure` and add in its place:

```python
    def test_balance_spreads_a_tier(self):
        """Plan 18: a write tier of two Claude rungs; the emptiest model runs, its verify one rank above it."""
        self.hub.cfg["tiers"] = dict(self.hub.cfg["tiers"], write=[{"rung": "sonnet", "effort": "auto"},
                                                                   {"rung": "claude-haiku-4-5", "effort": "auto"}])
        self.hub.budget = lambda: {"sonnet": {"share": 0.9, "binding": "week"}, "haiku": {"share": 0.2, "binding": "day"}}
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual((step["model"], step["tier"]), ("claude-haiku-4-5", "haiku"))
        self.assertEqual(self.hub.runs.meta(step["session"])["model"], "claude-haiku-4-5")
        self.assertIn("balance: sonnet 90 % -> claude-haiku-4-5 20 %", step["notes"])
        task = self.until(tid, lambda t: t["state"] == "waiting", "the verify holds")
        self.assertEqual(task["why"], "sonnet over its pace")  # haiku's code is checked on sonnet, over its pace

    def test_a_hard_design_step_on_fable_waits_for_the_confirm(self):
        """Plan 18: fable is hard only in think; when the balance picks it, the Fable confirm still holds the step."""
        self.hub.budget = lambda: {"opus": {"share": 0.9, "binding": "day"}, "fable": {"share": 0.1, "binding": "day"}}
        tid = self.make_task(text="THINK plan it", steps=[{"kind": "design", "goal": "plan it"}])  # reasoning high
        task = self.until(tid, lambda t: t["state"] == "waiting", "the fable step waits")
        self.assertEqual((task["why"], task["steps"][0]["state"]), ("confirm Fable", "planned"))
        self.assertEqual(self.call("/api/task/confirm", {"task": tid})[0], 200)
        task = self.until(tid, self.at(1), "the design step starts")
        self.assertEqual((task["steps"][0]["model"], task["steps"][0]["tier"]), ("fable", "fable"))

    def test_budget_reads_the_usage_days(self):
        today = usage.day_of(time.time())
        self.assertEqual(self.hub.budget(), {})  # usage not read yet: the tiers' order routes
        self.hub.cfg["allowances"] = {"opus": {"day_usd": 10, "week_usd": 50, "month_usd": 150}}
        with self.hub.lock:
            self.hub.usage_days = {today: {"cost": 5.0, "tokens": [0, 0, 0, 0], "projects": {}, "models": {"opus": 5.0}}}
            self.hub.usage_ready = True
        fill = self.hub.budget()["opus"]
        self.assertEqual((fill["day"]["used_usd"], fill["day"]["allowance_usd"]), (5.0, 10.0))
        self.assertIn(fill["binding"], ("day", "week", "month"))
        self.assertEqual(fill["via"], ["claude"])
        self.assertIsNone(self.hub.budget()["sonnet"]["share"])  # no allowance
        data = self.call("/api/usage")[1]
        self.assertEqual((data["fills"]["opus"]["day"]["used_usd"], data["fail_hours"], data["warn_at"]), (5.0, {}, 0.8))
        cfg = self.call("/api/config")[1]
        self.assertEqual(cfg["kinds_tier"]["design"], "think")
        self.assertEqual(cfg["kinds_tier"]["scout"], "read")
        think = {r["rung"]: r for r in cfg["tiers"]["think"]}
        self.assertEqual((think["opus"]["why"], think["opus"]["key"], think["fable"]["hard"]), ("", "opus", True))
        self.assertNotEqual(think["codex:gpt-6-astra"]["why"], "")  # codex is not usable here

    def test_runs_of_another_harness_count_once(self):
        sid, ts = "0000-codex", time.time()
        self.hub.runs.runs.mkdir(parents=True, exist_ok=True)
        self.hub.runs.meta_path(sid).write_text(json.dumps({"harness": "codex", "model": "gpt-6.1-sol"}), encoding="utf-8")
        self.hub.cfg["prices"] = dict(self.hub.cfg["prices"], **{"gpt-6.1-sol": {"input": 2, "output": 10, "cache_read": 0.2}})
        rec = {"event": "run_ended", "session_id": sid, "ts": ts,
               "tokens": {"input": 1_000_000, "output": 100_000, "cache_read": 0}}
        self.assertTrue(self.hub.count_run(rec))
        self.assertFalse(self.hub.count_run(rec))  # a restart replays the line: counted once
        row = self.hub.usage_other[usage.day_of(ts)]["gpt-6.1-sol"]
        self.assertEqual((row["cost"], row["runs"], row["unknown"]), (3.0, 1, 0))
        self.assertTrue(self.hub.count_run(dict(rec, ts=ts + 1, tokens=None)))  # no usage: unknown, never zero
        self.assertEqual(self.hub.usage_other[usage.day_of(ts)]["gpt-6.1-sol"]["unknown"], 1)
        self.hub.runs.meta_path("0000-claude").write_text(json.dumps({"model": "sonnet"}), encoding="utf-8")
        self.assertFalse(self.hub.count_run(dict(rec, session_id="0000-claude")))  # the transcripts price Claude
        today = self.hub.snapshot()["spend"]
        self.assertEqual(today["fills"]["over"], [])
```

`self.hub.runs.meta_path` and `self.hub.runs.runs` are today's `runs.Runs` names; if plan 5 Task 4 renamed them,
use its names (the test only needs a meta with `harness` and `model` for `sid`).

Plan 5's `test_step_pick_falls_back_when_harness_off`: its last assertion on the note `harness: codex off ->
sonnet` becomes:

```python
        self.assertIn("pick refused: codex is off -> balance", step["notes"])
```

and its model assertion stays (the step runs on Claude's `sonnet`: the write tier's one usable rung at the pick's
rank, with the test cfg's codex off).

### `tests/test_fills.py`, class `PlanFiveTest` (needs plan 5)

```python
class PlanFiveTest(unittest.TestCase):
    """fills duplicates plan 5's names so it runs on its own; these keep the two copies equal."""

    def test_names_match_plan_5(self):
        from console import claude_cli, harness, paths
        self.assertEqual(fills.HARNESSES, tuple(harness.NAMES))
        cfg = dict(paths.DEFAULTS, models=paths.MODELS_DEFAULT)
        for name, models in paths.MODELS_DEFAULT.items():
            for model in models:
                rung = model if name == "claude" else f"{name}:{model}"
                self.assertEqual(fills.split_rung(rung), claude_cli.split_rung(rung), rung)
                self.assertEqual(fills.rank_of(rung, cfg), claude_cli.tier_of(rung, cfg), rung)
        for tier in fills.TIERS:  # every default rung of a tier is a model models.json lists
            for rung, _ in fills.tier_rungs(paths.DEFAULTS, tier):
                self.assertTrue(fills.rank_of(rung, cfg), rung)
```

## 4.8 Steps

1. `tests/test_server.py` and `tests/test_fills.py` as above; run `py -m unittest tests.test_server tests.test_fills`:
   the new server tests fail (`count_run`, `tier_view` missing; the hold and spread assertions), `PlanFiveTest` passes
   or names the rung whose rank differs (fix `fills.rank_of`, never the test).
2. The `server.py` changes in the order 4.1 to 4.6; run: every test OK.
3. `grep -n "model_id(\|tier_budget" console/` finds nothing (`model_id` as a local variable name in `start_step` is
   plan 5's and stays: grep for the call form).
4. The whole suite: the count before Task 1 + 37 (fills 20 + 1, test_tasks + 9, test_usage + 4, test_server + 3),
   and no test skipped by this plan.
5. Commit: `plan 18 task 4: the service balances steps on the fills; other harnesses' runs counted (N tests OK)`.

## 4.9 Drift guards

- `Hub.start_step` runs `route["rung"]` as given; no other line in the service chooses a rung for a task step.
- `Hub.budget()` is `{}` until `usage_ready`; `count_run` is the only caller of `usage.add_other`.
- `fill_marks` and `budget` never run while `Hub.lock` is held by the caller (the lock is not reentrant).
- The window reads `tiers[...].why` to hide a rung; config.json keeps every rung (README 3.8).
