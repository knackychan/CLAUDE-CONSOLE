# Task 5: the Hub. State at start, the tick, admission, the pass thread, the result

> Contract: [README.md](README.md) 3.5, 3.6, 3.7, 3.11. Decisions D2, D3, D4.
> Mirrors plan 44's Hub supervisor (`server.py:1778-2106`): one claim under `tlock`, the model call outside every
> lock, completion always runs, the ledger settles once. Simpler: one pass at a time for the whole service, one wake
> in memory, no dispatch.

**Files**
- Modify: `console/server.py` (other chats edit this file: anchored edits, stage only this task's hunks, README rules)
  - the import line, `SUPER_POLL_S`, `Hub.__init__`, `Hub.run`, a new section of `_super_*` methods
- Create: `tests/test_superagent_server.py` (`SuperHubTest`; Task 6 adds `SuperRouteTest` to the same file)

Commit boundary: `feat: super agent wakes, admission and pass results in the Hub (plan 58 T5)`.

## 5.1 `console/server.py`

**Import** (line 16-17): `superagent` joins the list, alphabetical: `..., replan, review, routing, runs, superagent,
supervisor, tasks, transcript, tuning, usage)`.

**Constant**, after `TICK_S = 15.0`:

```python
SUPER_POLL_S = 5.0  # plan 58: the super agent's tick in Hub.run (items, wakes, admission)
```

**`Hub.__init__`**, after `self.sup_unsettled = {}` and before `self.probing = ...`:

```python
        # plan 58: the super agent, one pass at a time over every item that needs Fred (no acts)
        self.super = superagent.load_state(self.folder)  # state.json: seen, annotations, the last pass, Pause
        self.super_wake = None  # the one pending wake {first, due, events, asked}; memory only
        self.super_busy = None  # the running pass's snapshot, or None
        self.super_threads = []  # the pass threads (tests join them)
        self.super_clock = time.time  # wall clock: seen, until and the debounce (tests pass their own)
        self.super_running = None  # ids of the tasks running at the last tick; None before the first tick
        self.super_swept = 0.0  # when a sweep was last considered
        self._super_recover()
```

**`Hub.run`**: `last_super = 0.0  # plan 58: the first loop ticks the super agent` after `last_tick =
time.monotonic()`, and after `self.tick()`:

```python
            if time.monotonic() - last_super >= SUPER_POLL_S:
                last_super = time.monotonic()
                self._super_tick()
```

**The section**, inserted immediately before the line `    # -- plan 44: supervisor wakes (Task 5) ----...`:

```python
    # -- plan 58: the super agent (one pass at a time sorts what needs Fred across every task; no acts) -----------

    def _super_save(self) -> None:
        try:
            superagent.save_state(self.folder, self.super)
        except OSError as exc:
            self._log(f"super agent: state.json not saved: {exc}")

    def _super_log(self, record: dict) -> None:
        try:
            superagent.append_log(self.folder, record)
        except OSError as exc:
            self._log(f"super agent: super.jsonl: {exc}")

    def _super_recover(self) -> None:
        """README 58 3.11, once at start: a pass claimed before a restart settles as unknown in the ledger (its
        reservation stays held), gets its result line and becomes the last pass, failed. seen and ann stay."""
        claimed = self.super.get("claimed")
        if not isinstance(claimed, dict):
            return
        pid, n, at = claimed.get("pid"), claimed.get("n"), claimed.get("at")
        if isinstance(pid, str) and pid:
            usage.record_super(self.folder, pid, {"cost": None})
        n = n if isinstance(n, int) and not isinstance(n, bool) else self.super["n"]
        handles = claimed.get("handles") if isinstance(claimed.get("handles"), dict) else {}
        error = "the service restarted during the pass"
        self.super["last"] = {"n": n, "at": float(at) if isinstance(at, (int, float)) and not isinstance(at, bool)
                              else 0.0, "ok": False, "error": error, "model": str(claimed.get("model") or ""),
                              "cost": None, "turns": 0, "ms": 0, "items": len(handles),
                              "trigger": str(claimed.get("trigger") or ""), "fingerprint": ""}
        self.super["claimed"] = None
        self._super_log({"phase": "result", "n": n, "ok": False, "error": error, "cost": None, "turns": 0, "ms": 0,
                         "kept": 0, "dropped": [], "trimmed": [], "out": None})
        self._super_save()

    def _super_arm(self, now: float, events: list, at_once: bool = False) -> None:
        """The one pending wake (README 58 3.6): each event pushes it super_debounce_s later, never past MAX_WAIT_S
        after its first event; Resume and Sort make it due at once."""
        wake = self.super_wake
        if wake is None:
            wake = self.super_wake = {"first": now, "due": now, "events": [], "asked": False}
        wake["events"].extend(events)
        wake["asked"] = wake["asked"] or at_once
        debounce = superagent.settings(self.cfg)[0]["super_debounce_s"]
        wake["due"] = wake["first"] if wake["asked"] else min(now + debounce, wake["first"] + superagent.MAX_WAIT_S)

    def _super_tick(self, now=None) -> bool:
        """README 58 3.6, every SUPER_POLL_S from run(): bring the item memory to the live needs set, arm the wake on
        events (new items, items back from later, tasks that ended) or on a sweep, and admit a due pass. Never
        raises (a failure is logged; the next tick tries again). True when a pass started."""
        now = self.super_clock() if now is None else now
        try:
            with self.tlock:
                snap = self.snapshot()
                live = superagent.items(snap, self.tasks)
                new, back, changed = superagent.sync(self.super, live, now)
                running = {tid for tid, t in self.tasks.items() if t.get("state") == "running"}
                ended = [tid for tid in sorted(self.super_running or ())
                         if (self.tasks.get(tid) or {}).get("state") in ("done", "stopped", "stuck", "handed")]
                self.super_running = running
                events = [("new", k) for k in new] + [("back", k) for k in back] + [("ended", t) for t in ended]
                if events:
                    self._super_arm(now, events)
                elif self.super_wake is None and running and live:
                    self._super_sweep(now, live)
                if changed:
                    self._super_save()
                return self._super_admit(now, snap, live)
        except Exception as exc:  # the super agent never stops the hub loop
            self._log(f"super agent tick failed: {type(exc).__name__}: {redact.clip(redact.mask(str(exc)), 200)}")
            return False

    def _super_sweep(self, now: float, live: list) -> None:
        """README 58 3.6 step 4: every super_sweep_s while a task runs; a wake only when the fingerprint moved."""
        since = max(self.super_swept, superagent.last_at(self.super))
        if now - since < superagent.settings(self.cfg)[0]["super_sweep_s"]:
            return
        self.super_swept = now
        sigs = superagent.signals(self.tasks, now)
        last = self.super.get("last") if isinstance(self.super.get("last"), dict) else {}
        if superagent.fingerprint(live, self.tasks, sigs) != last.get("fingerprint"):
            self._super_arm(now, [("sweep", "")])

    def _super_admit(self, now: float, snap: dict, live: list) -> bool:
        """README 58 3.7, under tlock: a due wake, no pass running, every gate open and a reservation; then the
        snapshot, the claim (state.json and the claimed line) and the pass thread. A blocked wake is dropped."""
        wake = self.super_wake
        if wake is None or wake["due"] > now or self.super_busy is not None:
            return False
        limits, errors = superagent.settings(self.cfg)
        if superagent.blocked(limits, errors, self.super, bool(self.runs.exe)) or not live:
            self.super_wake = None  # Resume, Sort or the next event arms another
            return False
        pid = uuid.uuid4().hex
        got = usage.reserve_super(self.folder, pid, usage.day_of(now), limits["super_pass_usd"],
                                  limits["super_day_usd"])
        self.super_wake = None
        if got["status"] != "reserved":
            self._super_log({"phase": "refused", "status": got["status"], "error": got.get("error", "")})
            return False
        self.super["n"] += 1
        n = self.super["n"]
        try:
            job = self._super_snapshot(n, pid, got["reserved"], wake, snap, live, now, limits)
        except Exception as exc:  # nothing was launched: the reservation settles at no cost
            usage.record_super(self.folder, pid, {"cost": 0.0})
            error = f"the digest failed: {type(exc).__name__}: {redact.clip(redact.mask(str(exc)), 200)}"
            self.super["last"] = {"n": n, "at": now, "ok": False, "error": error, "model": "", "cost": 0.0,
                                  "turns": 0, "ms": 0, "items": len(live),
                                  "trigger": superagent.trigger_words(wake["events"]), "fingerprint": ""}
            self._super_log({"phase": "result", "n": n, "ok": False, "error": error, "cost": 0.0, "turns": 0,
                             "ms": 0, "kept": 0, "dropped": [], "trimmed": [], "out": None})
            self._super_save()
            return False
        self.super["claimed"] = {"n": n, "pid": pid, "at": now, "model": job["model"], "handles": job["handles"],
                                 "trigger": job["trigger"]}
        self._super_log({"phase": "claimed", "n": n, "pid": pid, "trigger": job["trigger"], "model": job["model"],
                         "handles": job["handles"], "bytes": len(job["prompt"].encode("utf-8")),
                         "prompt_hash": job["prompt_hash"], "reserved": got["reserved"]})
        self._super_save()
        self.super_busy = job
        thread = threading.Thread(target=self._super_job, args=(job,), name="super-pass", daemon=True)
        self.super_threads.append(thread)
        thread.start()
        return True

    def _super_describe(self, item: dict, rows: dict, sessions: dict, now: float) -> dict:
        """One item with its card fields (superagent.describe): a task's from Hub.actions (read only) and its
        effective level; a session's from its snapshot row, at level observed."""
        if item["type"] == "session":
            return superagent.describe(item, None, sessions.get(item["id"]) or {}, {}, "observed", 0, now)
        task = self.tasks[item["id"]]
        try:
            view = self.actions(task)
        except Exception:  # the card line is a nicety, never a failed pass
            view = {}
        return superagent.describe(item, task, rows.get(item["id"]) or {}, view,
                                   supervisor.policy(self.cfg, task, now)["mode"], self.cfg["decision_timeout_s"], now)

    def _super_snapshot(self, n: int, pid: str, reserved: float, wake: dict, snap: dict, live: list, now: float,
                        limits: dict) -> dict:
        """Everything the pass reads, built once under tlock: the items described in the order the last ok pass
        left (then the later ones), each task item with its open questions, the live lines, the signals, the head,
        the digest and the prompt (saved as last-prompt.md; the same string is hashed and run)."""
        rows = {r["id"]: r for r in snap.get("tasks") or []}
        sessions = {r["id"]: r for r in snap.get("sessions") or []}
        described = [self._super_describe(item, rows, sessions, now) for item in live]
        placed = superagent.queue(described, self.super, now, ranked=True)
        ordered = [i for card in placed["queue"] for i in card["items"]] + placed["later"]
        for item in ordered:
            task = self.tasks.get(item["id"]) if item["type"] == "task" else None
            if task is not None:
                briefs = {s["n"]: tasks.read_brief(self.folder, task, s["n"]) for s in task["steps"]}
                item["questions"] = [q["q"] for q in tasks.open_questions(task, briefs) if not q["closed"]]
        new_keys = {key for what, key in wake["events"] if what == "new"}
        model = superagent.pass_model(limits, [i for i in ordered if i["key"] in new_keys])
        lines = [superagent.task_line(t, supervisor.policy(self.cfg, t, now)["mode"], now)
                 for t in superagent.live_tasks(self.tasks)]
        sigs = superagent.signals(self.tasks, now)
        trigger = superagent.trigger_words(wake["events"])
        spent = sum(usage.super_spent(self.folder, usage.day_of(now))) - reserved  # this pass's own hold left out
        head = {"n": n, "trigger": trigger, "spent": max(0.0, spent), "day_usd": limits["super_day_usd"],
                "levels": superagent.levels(self.cfg)}
        you = paths.you(self.cfg)
        notes = superagent.cut_notes(superagent.read_notes(self.folder), limits["super_notes_lines"])
        text, handles = superagent.digest(head, ordered, superagent.read_orders(self.folder), notes, lines, sigs,
                                          you, now)
        prompt = superagent.build_prompt(kinds.text(self.folder, "super"), text, you, limits["super_notes_lines"])
        superagent.save_prompt(self.folder, prompt)
        return {"n": n, "pid": pid, "reserved": reserved, "model": model, "prompt": prompt,
                "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "handles": handles,
                "items": {i["key"]: {"kind": i["kind"], "always": i["always"]} for i in live},
                "trigger": trigger, "at": now, "cwd": str(superagent.folder(self.folder)),
                "fingerprint": superagent.fingerprint(live, self.tasks, sigs),
                "cfg": dict(copy.deepcopy(self.cfg), super_timeout_s=limits["super_timeout_s"]),
                "notes_lines": limits["super_notes_lines"]}

    def _super_job(self, job: dict) -> None:
        """Exactly one superagent.run outside every lock; completion always runs."""
        result = {"out": None, "cost": None, "model": job["model"], "turns": 0, "error": "the pass did not run",
                  "ms": 0}
        try:
            result = superagent.run(job["cfg"], self.runs.exe, job["cwd"], job["prompt"], job["model"],
                                    job["reserved"])
        except Exception as exc:
            result = dict(result, error="the pass failed: " + redact.clip(redact.mask(str(exc)), 200))
        finally:
            self._super_done(job, result)

    def _super_done(self, job: dict, result: dict) -> None:
        """Settle the spend once, check the answer (README 58 3.7), keep it when ok, and write the result line and
        state.json. A failed pass changes no annotation, digest or notes, and unranks the queue."""
        with self.tlock:
            self.super_busy = None
            settled = usage.record_super(self.folder, job["pid"], {"cost": result.get("cost")})
            if settled.get("status") not in ("settled", "unknown"):
                self._log(f"super agent pass {job['n']}: the ledger kept its reservation: {settled.get('error', '')}")
            ok = not result.get("error") and isinstance(result.get("out"), dict)
            kept, dropped, trimmed = 0, [], []
            if ok:
                try:
                    got = superagent.check(result["out"], job["handles"], job["items"], self.super_clock(),
                                           job["notes_lines"])
                except Exception as exc:  # a check bug is a failed pass, never a dead thread
                    ok = False
                    result = dict(result, error=f"the pass gave no answer (the check failed: {type(exc).__name__})")
                else:
                    self.super["ann"] = {k: a for k, a in got["ann"].items() if k in self.super["seen"]}
                    self.super["digest"] = got["digest"]
                    kept, dropped, trimmed = len(self.super["ann"]), got["dropped"], got["trimmed"]
                    try:
                        superagent.save_notes(self.folder, got["notes"])
                    except OSError as exc:
                        self._log(f"super agent: notes.md not saved: {exc}")
            self.super["last"] = {"n": job["n"], "at": job["at"], "ok": ok, "error": result.get("error") or "",
                                  "model": result.get("model") or job["model"], "cost": result.get("cost"),
                                  "turns": result.get("turns") or 0, "ms": result.get("ms") or 0,
                                  "items": len(job["handles"]), "trigger": job["trigger"],
                                  "fingerprint": job["fingerprint"]}
            self.super["claimed"] = None
            self._super_log({"phase": "result", "n": job["n"], "ok": ok, "error": result.get("error") or "",
                             "cost": result.get("cost"), "turns": result.get("turns") or 0,
                             "ms": result.get("ms") or 0, "kept": kept, "dropped": dropped, "trimmed": trimmed,
                             "out": result.get("out")})
            self._super_save()
        with self.lock:
            self.version += 1
            self.changed.notify_all()
```

`last.at` is the claim time: an item first seen during the pass (after the claim) is new in the next ranked queue,
since that pass never saw it.

## 5.2 Tests first (red before the code)

`tests/test_superagent_server.py`, head and fixture:

```python
"""Plan 58: the super agent in the Hub (Task 5: superagent.run patched, a frozen clock, no hub loop) and over HTTP
(Task 6: the fake claude). Scratch homes only; no paid provider, no port 47770, no ~/.claude."""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from console import paths, server, superagent, supervisor, tasks, usage

T0 = 1_800_000_000.0
FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
DECISION = {"q": "Which file?", "options": [{"key": "1", "text": "style.css"}, {"key": "2", "text": "app.js"}],
            "default": "1", "step": 1, "asked": T0}


def make_task(hub, project, n, state="waiting", why="plan ready: confirm", **extra):
    """Task n of `hub` (id 20270115-0800NN-a0NN, label 0115-a0NN): one code step, then the verify; current 1; the
    step runs when the task does, else it is done; saved and put in hub.tasks. Task 6 uses it too."""
    tid = f"20270115-0800{n:02d}-a0{n:02d}"
    t = tasks.new_task(str(project), "proj", f"Task {n}", "goal",
                       tasks.plan_steps([{"kind": "code", "goal": "edit"}], 6), "normal", {}, "", "auto", T0, id_=tid)
    t["supervisor"] = supervisor.initial(hub.cfg, str(project), T0)
    running = state == "running"
    t["steps"][0].update(state="running" if running else "done", started=T0, ended=None if running else T0 + 60,
                         dir="01-code", model="sonnet", effort="medium",
                         attempts=[{"session": "", "cost": 0.1, "started": T0, "ended": None if running else T0 + 60,
                                    "why": "", "final": not running}])
    t.update(state=state, why="" if running else why, current=1, **extra)
    tasks.save(hub.folder, t)
    hub.tasks[tid] = t
    return tid


class SuperHubTest(unittest.TestCase):
    """Hub level: _super_tick is called by hand at frozen times; superagent.run is patched (no model, no process)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        data = Path(self.tmp.name) / "data"
        data.mkdir()
        env = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": str(data)})
        env.start()
        self.addCleanup(env.stop)
        self.now, self.calls, self.answer = T0, [], None
        self.gate = threading.Event()
        self.gate.set()

        def fake_run(cfg, exe, cwd, prompt, model, max_cost):
            self.calls.append({"cfg": cfg, "cwd": cwd, "prompt": prompt, "model": model, "max_cost": max_cost})
            self.gate.wait(10)
            if self.answer:
                return self.answer(prompt)
            handles = re.findall(r"^(I\d+) ", prompt, re.M)
            out = {"items": [{"key": h, "do": "forward", "rank": len(handles) - k, "say": f"say {h}"}
                             for k, h in enumerate(handles)], "digest": ["sorted"], "notes": "watching"}
            return {"out": out, "cost": 0.003, "model": model, "turns": 2, "error": "", "ms": 5}
        patch = mock.patch.object(superagent, "run", side_effect=fake_run)
        patch.start()
        self.addCleanup(patch.stop)
        self.hub = self.make_hub(Path(self.tmp.name) / "home")
        self.addCleanup(self.drain)

    def make_hub(self, folder, **cfg):
        hub = server.Hub(dict(paths.load_config(), projects=[str(self.project)], supervisor_mode="gated", **cfg),
                         folder, exe=FAKE)
        hub.user_home = Path(self.tmp.name)
        hub.super_clock = lambda: self.now
        return hub

    def drain(self, hub=None):
        self.gate.set()
        for t in list((hub or self.hub).super_threads):
            t.join(10)

    def task(self, n, state="waiting", why="plan ready: confirm", hub=None, **extra):
        return make_task(hub or self.hub, self.project, n, state, why, **extra)

    def tick(self, at, hub=None):
        self.now = at
        return (hub or self.hub)._super_tick()

    def log(self, phase=None, hub=None):
        return [r for r in superagent.read_log((hub or self.hub).folder) if phase is None or r.get("phase") == phase]

    def key(self, tid, hub=None):
        hub = hub or self.hub
        return next(i["key"] for i in superagent.items(hub.snapshot(), hub.tasks) if i["id"] == tid)
```

`SuperHubTest` (each assertion exact; `day = usage.day_of(T0)`):
- `test_new_items_arm_one_debounced_pass`: task 1 waiting (`plan ready: confirm`). `tick(T0)` is False and
  `super_wake["due"]` is T0+20; `state.json` holds `seen` `{key1: T0}`. `tick(T0+19)` is False; `tick(T0+20)` is
  True; drain. One call: `max_cost` 0.2, `model` `haiku`, `cwd` `str(home / "super")`, `cfg["super_timeout_s"]` 120;
  its prompt holds `"# Super agent pass 1 · "`, `"Triggers: 1 new item"`, `"I1 · task 0115-a001 · proj · Task 1"` and
  `"ask: plan ready · confirm"`, and equals `last-prompt.md`. Then `super["last"]` has `n` 1, `ok` True, `cost`
  0.003, `items` 1, `at` T0+20; `ann[key1]` is `{"do": "forward", "rank": 1, "say": "say I1", "why": "", "batch": "",
  "until": None}`; `digest` `["sorted"]`; `notes.md` `"watching\n"`; `claimed` None; the log phases are `["claimed",
  "result"]`, the claim's `prompt_hash` is the SHA-256 of the prompt and its `bytes` the prompt's UTF-8 size;
  `usage.load_super(home)["records"]` holds one record, `settled` at 0.003; `hub.version` went up. Ticks every 5 s
  from T0+25 to T0+300 start nothing more.
- `test_new_events_never_push_a_pass_past_max_wait`: task 1 at T0, then a new task every 15 s up to T0+105 (8 in
  all), each followed by its tick: the due times read T0+20, 35, 50, 65, 80, 95, 110, then 120 (the ceiling).
  `tick(T0+119)` is False, `tick(T0+120)` True; the prompt's Triggers line is `"Triggers: 8 new items"`.
- `test_one_pass_at_a_time_and_events_during_it_wait`: gate cleared; task 1 at T0; `tick(T0+20)` True. Task 2 at
  T0+25: `tick(T0+25)` False and the wake is due T0+45; `tick(T0+50)` False (one pass at a time). Gate set, drain:
  `tick(T0+55)` True; drain; two calls; the second prompt holds `"Triggers: 1 new item"` and handles `I1` and `I2`.
- `test_nothing_to_sort_starts_nothing`: no task: ticks from T0 to T0+300 start nothing; `super_wake` is None; no
  `state.json`, no `super.jsonl`, no `super` section in usage-days.json. A wake armed by hand (`_super_arm(T0,
  [("asked", "sort")], at_once=True)`) is dropped at the next tick: no call, `super_wake` None.
- `test_a_task_that_ends_wakes_a_pass`: task 1 waiting and task 2 running at T0; pass 1 at T0+20, drained. Task 2's
  state set to `done` (no card: not an item): `tick(T0+100)` arms a wake due T0+120 whose events are `[("ended",
  tid2)]`; `tick(T0+120)` True; its prompt holds `"Triggers: 1 task ended"`.
- `test_sweep_runs_only_when_the_fingerprint_changed`: task 1 waiting, task 2 running; pass 1 at T0+20, drained.
  `tick(T0+919)` arms nothing; task 2's attempt cost set to 0.6 (still under a dollar): `tick(T0+920)` considers a
  sweep (`super_swept` T0+920) and arms nothing (the fingerprint holds); task 2's current step `retries` set to 1:
  `tick(T0+1819)` arms nothing (under `super_sweep_s` since the sweep), `tick(T0+1820)` arms a wake with events
  `[("sweep", "")]`; `tick(T0+1840)` True and its prompt holds `"Triggers: sweep"`. With task 2 done instead, no
  sweep is considered at all (`super_swept` unchanged).
- `test_an_item_back_from_later_wakes_a_pass`: `self.answer` puts `I1` later with `until` `time.strftime(
  "%Y-%m-%dT%H:%M", time.localtime(T0 + 600))`; pass 1 at T0+20, drained: `ann[key1]["do"]` is `later` and its
  `until` T0+600. `tick(T0+599)` arms nothing; `tick(T0+600)` arms a wake with events `[("back", key1)]` and sets
  `ann[key1]["back"]` True; `tick(T0+605)` adds no second back event (the wake's events stay `[("back", key1)]`);
  `tick(T0+620)` True with `"Triggers: 1 back from later"`.
- `test_restart_settles_a_claimed_pass_and_keeps_the_order`: pass 1 over task 1 ok (drained). Gate cleared; task 2
  at T0+30; `tick(T0+50)` True (pass 2 claimed, blocked). `hub2 = self.make_hub(home)`: `hub2.super["claimed"]` is
  None; `hub2.super["last"]` has `n` 2, `ok` False, `error` `"the service restarted during the pass"`, `cost` None,
  `items` 2, `at` T0+50; `hub2.super["ann"]` equals pass 1's annotations and `hub2.super["seen"]` holds both keys
  at T0 and T0+30; the ledger record of pass 2 is `unknown` with `reserved` 0.2, so `usage.super_spent(home, day)` is
  `(0.003, 0.2)`; the log has a `result` line with `n` 2 and that error. `tick(T0+60, hub2)` is False and
  `hub2.super_wake` is None (a restart does not cause a pass by itself).
- `test_pause_off_no_exe_and_bad_settings_start_nothing`: subTests, each on a fresh hub in its own folder with task
  1: paused (`hub.super["paused"] = True`), `super_day_usd` 0, `super_pass_usd` 0, `hub.runs.exe = None`,
  `super_debounce_s` `"20"`, `super_model` `"opus"`. `tick(T0)` and `tick(T0+20)` start nothing, `super_wake` is
  None after T0+20, no call, and usage-days.json has no `super` section.
- `test_day_limit_caps_the_passes`: `super_day_usd` 0.008. Task k at T0+100k for k = 1..4, each with `tick(T0+100k)`,
  `tick(T0+100k+20)` and a drain: the calls' `max_cost` are 0.008, 0.005 and 0.002 (`assertAlmostEqual`, 6 places);
  the fourth admission is False and the last `refused` line is `{"status": "cap", "error": "super agent day limit
  reached"}` (plus `ts` and `phase`); `superagent.status(*superagent.settings(hub.cfg), hub.super,
  sum(usage.super_spent(home, day)), True)` is `(False, "over the day limit ($0.01)")`.
- `test_failed_pass_keeps_the_last_answer_and_unranks`: pass 1 over task 1 ok. `self.answer` returns `{"out": None,
  "cost": 0.02, "model": "haiku", "turns": 6, "error": "the pass failed: error_max_turns", "ms": 9}`; task 2 at T0+30,
  pass 2 at T0+50: `ann`, `digest` and `notes.md` are pass 1's; `last` has `n` 2, `ok` False, that `error`, `cost`
  0.02; `superagent.status(...)` is `(False, "the pass failed: error_max_turns")`; pass 2's ledger record is
  `settled` at 0.02.
- `test_answer_is_checked_masked_and_logged`: task 1 waiting `confirm Fable` (always) and task 2 `plan ready:
  confirm`, both at T0 (I1 is task 1: always items come first). `self.answer` returns items `[{I1, later, rank 2,
  say "set token=abc"}, {I2, forward, rank 1, say "b"}, {I9, forward, rank 3, say "c"}]`, digest `["d"]`, notes `"n"`:
  `ann[key1]` is `{"do": "forward", "rank": 2, "say": "set token=***", ...}`, `ann[key2]` rank 1; the result line has
  `kept` 2, `dropped` `[{"at": 2, "why": "unknown handle I9"}]`, `trimmed` `[{"at": 0, "why": "always forwarded:
  Fable confirm"}]`, and its `out` holds `"set token=***"`; `super.jsonl` holds no `abc` and every line parses.
- `test_notes_keep_the_line_limit`: `super_notes_lines` 3 and an answer whose notes are 10 lines: `notes.md` holds 3
  lines; the next pass's prompt holds `"Your notes from the last pass:\n"` followed by those 3 lines, and `"at most 3
  lines"`. With `super_notes_lines` 0, `notes.md` is `""` and the next prompt reads `"Your notes from the last
  pass:\nnone"`.
- `test_digest_carries_items_orders_notes_and_levels`: `super/orders.md` holds `"# mine\nnever raise chats before
  18:00\n"`; `cfg["supervisor_projects"]` `{str(project): "auto"}`; task 1 waiting `asks: Which file?` with the
  decision of table 4.1, its supervisor mode `auto` (`supervisor.initial(cfg, project, T0, mode="auto")`), and a brief
  for step 1 written by `tasks.write_brief` whose `## Open questions` holds `- Keep the old class names?`. Pass 1 at
  T0+20: the prompt holds `"Standing orders from the user:\nnever raise chats before 18:00"` (no `# mine`), `"Levels:
  global gated; proj auto"`, `"Spend today: $0.00 of $1.00 a day"`, `"ask: needs you · Which file?"`, `"options: 1)
  style.css 2) app.js · default style.css, taken in 9 min"` (600 s from T0, seen at T0+20), `"open questions: Keep the
  old class names?"` and `"Live tasks (1):\n0115-a001 proj · waiting · step 1/2 code sonnet/medium · done · $0.10 ·
  retries 0 · FAILs 0 · level auto"`.
- `test_judge_model_for_a_new_stuck_item`: task 1 stuck (`step 01 failed`) at T0: pass 1's model is `sonnet`; task 2
  waiting at T0+100: pass 2's model is `haiku` (the stuck item is no longer new).
- `test_a_failing_tick_is_logged_never_raised`: with `superagent.items` patched to raise `RuntimeError("boom")`,
  `tick(T0)` is False and `home / "console.log"` holds `"super agent tick failed: RuntimeError: boom"`.
- `test_hub_loop_ticks_the_super_agent`: with `poll_once`, `auto_steps`, `advance`, `read_costs`, `tick`,
  `reconcile_next_steps` and `runs.reconcile` patched to do nothing, and `_super_tick` patched to record the call and
  set `hub._stop`, `hub.run()` returns after one loop with exactly one `_super_tick` call.

## 5.3 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_superagent_server`: red for the missing Hub methods.
- [ ] 2. Make the 5.1 edits. Focused tests green; `tests/test_supervisor_server.py` and `tests/test_server.py` still
      green (the Hub's start and its tick order are unchanged but for the new call).
- [ ] 3. Full suite green (report the count). Stage the new test file by path and only this task's hunks of
      `console/server.py` (non-interactive staging, README rules). Commit with the message above.
