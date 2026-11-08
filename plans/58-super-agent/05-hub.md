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

This revised recipe replaces the former source block. Implement
[review R1-R9](08-review-and-jev.md#1-required-corrections), especially the persistence sequence in R4.
Do not restore logging-only claim saves, whole-ann replacement, wall-clock debounce or new-items-only routing.

**Wiring.** Import superagent beside supervisor. Add SUPER_POLL_S = 5.0 and call `_super_tick` on that monotonic
cadence from Hub.run, preserving its other calls. The tick contains exceptions, reports a masked visible failure
and never stops the main loop.

**State at start.** Load state strictly; on error keep a raw queue and set a storage error that blocks admissions.
Initialize one pending wake, one busy job, injectable wall and monotonic clocks, running-task IDs, sweep time and
prior admission-block reason/day. Keep only live threads (tests can join them). Reconcile before any admission,
under tlock; start/restart never calls a paid provider merely because an old claim exists.

**Tick and wakes.**

1. Under tlock, snapshot coherently using the existing lock order. Build live items, sync seen/ann/reviewed and
   compare decision bases/policy. Save changed state before admitting a pass. A failed save blocks admission.
2. Coalesce new/back/changed-input/ended events into one wake. Expired Later returns once even with no running
   task. Do not accumulate duplicate events. Track running-to-done/stopped/stuck/handed after the first tick.
3. Use monotonic first/due/sweep times. Debounce is 20 seconds with a 120-second ceiling from first event;
   Sort/Resume are due immediately. A running pass or closed gate can delay admission beyond that ceiling.
4. Eligible sweeps retain the fingerprint check and existing running-task restriction. A local-day rollover or
   an observed blocking config/executable/storage gate becoming eligible arms one wake if items remain.
   A stable restart is not a transition wake. Model failure itself is not a retry event.
5. Keep persistence, ledger and input errors visible to super_view. A refusal must not leave the last successful
   pass looking current. Recovery can clear the error only after the failed read/write/settlement succeeds.

**Admission and immutable job.**

1. Require a due wake, no busy pass, valid settings/storage, enabled/unpaused service, executable and live items.
   Build input and reserve/save/log the claim in review R4's order. No paid thread starts on any failed write.
2. Describe items from Hub.actions, exact effective levels and decision deadlines. Choose candidates by
   select_items, not display order. Read bounded brief evidence for selected candidates only; copy the required
   task data under tlock and perform file/prompt work outside locks, then revalidate before claiming.
   Missing/clipped evidence sets incomplete; never equate it to no open questions.
3. Digest yields the submitted handles. Select Haiku/Sonnet from **those** items, including stuck subjects
   whose visible kind is suggestion. Preserve the immutable handle map, bases, policy hash, prompt/hash/bytes,
   pass UUID, admission day, timeout, reservation, wall claim time and copied settings in the job.
4. Save last-prompt.md, claimed state and audit claim durably. Required writes raise to admission; do not call
   _super_save/_super_log wrappers that only swallow exceptions. Before-run failure settles zero, retains
   recovery evidence if settlement fails, clears busy and exposes the cause.
5. Start one thread outside the critical section once the claim is durable. Catch Thread.start failure explicitly.
   Avoid a race with Pause between claim and invocation: recheck the admitted job/gates before invocation.
   If Pause wins before launch, settle zero; a call already started can finish while the queue stays unranked.

**Completion and publication.**

1. Exactly one run outside locks, with try/finally cleanup. Keep busy until the result has entered the durable
   result/settlement path. Never clear it early enough to overlap another admission.
2. Persist result with pid, cost/unknown and masked bounded output; settle once. A failed result/ledger write
   retains the claim and blocks new admissions until recovered. No successful result status on a partial save.
3. Rebuild live items/bases under tlock without waiting for another tick. Validate/trim untrusted output using
   the submitted immutable handle map. Filter stale keys/bases and reapply live hard-forward rules. Changed
   policy discards all advice. Even discarded advice retains its reported provider charge.
4. Scope batch IDs by pid; merge only current valid annotations. Keep still-valid advice for unseen/rejected
   entries, remove departed/stale entries, and revalidate groups. Update reviewed only for actual submitted
   handles after a current structurally valid response with usable items.
5. If any submitted item is stale, do not publish that response's global digest or notes. Otherwise save bounded
   notes and the candidate state. Retain recovery evidence and report an error on either failure. A successful
   notes save followed by a failed state save is reconciled from the journal before those notes are reused;
   do not promise atomicity across two files or attempt an unsafe overwrite rollback.
   Final state clears claimed only after durable accounting. Publish last.ok only after required writes succeed.
6. Notify changed once the visible state changes. Always release busy in cleanup, keeping storage-error admission
   blocking when publication failed. Prune completed threads.

**Recovery.** Scan state.claimed, both audit files and all reserved super ledger records by UUID. A durable result
settles once, an already-settled record is preserved, an orphan becomes unknown with its reservation held.
Conflicting evidence blocks. Never run a provider during recovery. Repeated restart is idempotent. If a known
result's settlement failed, preserve/retry that cost, not an unknown replacement. Persist recovery state; failure
continues to block. Do not simulate a crash in tests by leaving the original worker active against the same files.

**Evidence APIs.** Keep _super_describe and _super_snapshot as small assembly helpers using existing functions.
No new action dispatcher, no import from superagent into supervisor, no task-file changes. All error messages are
masked before logs/HTTP, including unexpected errors in the worker and at thread start.

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
        self.now, self.mono, self.calls, self.answer = T0, 1000.0, [], None
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
        hub.super_mono = lambda: self.mono
        return hub

    def drain(self, hub=None):
        self.gate.set()
        for t in list((hub or self.hub).super_threads):
            t.join(10)

    def task(self, n, state="waiting", why="plan ready: confirm", hub=None, **extra):
        return make_task(hub or self.hub, self.project, n, state, why, **extra)

    def tick(self, at, hub=None):
        self.mono += at - self.now
        self.now = at
        return (hub or self.hub)._super_tick()

    def log(self, phase=None, hub=None):
        return [r for r in superagent.read_log((hub or self.hub).folder) if phase is None or r.get("phase") == phase]

    def key(self, tid, hub=None):
        hub = hub or self.hub
        return next(i["key"] for i in superagent.items(hub.snapshot(), hub.tasks) if i["id"] == tid)
```

`SuperHubTest` (`day = usage.day_of(T0)`; update shapes for reviewed/basis and translate due assertions to the
injected monotonic clock. Preserve wall-time claim/seen assertions):
- Include every regression in review section 5: stale completion without a tick, policy changes mid-pass,
  65-item coverage/merge, cap rollover/off-to-on exactly once, wall-clock jumps, no retry storm and bounded threads.
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
  "%Y-%m-%dT%H:%M", time.localtime(T0 + 600))` and why `waits for the other task`; pass 1 at T0+20, drained: `ann[key1]["do"]` is `later` and its
  `until` T0+600 and a nonblank reason. `tick(T0+599)` arms nothing; `tick(T0+600)` arms a wake with events `[("back", key1)]` and sets
  `ann[key1]["back"]` True; `tick(T0+605)` adds no second back event (the wake's events stay `[("back", key1)]`);
  `tick(T0+620)` True with `"Triggers: 1 back from later"`.
- `test_restart_reconciles_each_durable_boundary`: use persisted fixtures or a terminated isolated fake process,
  never two active Hubs against one folder. Inject interruption after reserve, claim save/log, result log,
  settlement, notes save and final state save. Known cost is preserved; only missing results become unknown;
  orphan reservations remain charged; recovery twice is identical; no model call is replayed.
- `test_save_and_thread_start_failures_block_cleanly`: claim/state/log failures never start a process; a failed
  thread start settles zero and clears busy. Result/settlement/publication failure retains recoverable evidence,
  exposes a storage error and blocks new admission. Retrying persistence cannot double-charge.
- `test_pause_off_no_exe_and_bad_settings_start_nothing`: subTests, each on a fresh hub in its own folder with task
  1: paused (`hub.super["paused"] = True`), `super_day_usd` 0, `super_pass_usd` 0, `hub.runs.exe = None`,
  `super_debounce_s` `"20"`, `super_model` `"opus"`. `tick(T0)` and `tick(T0+20)` start nothing, `super_wake` is
  None after T0+20, no call, and usage-days.json has no `super` section.
- `test_day_limit_caps_the_passes`: `super_day_usd` 0.008. Task k at T0+100k for k = 1..4, each with `tick(T0+100k)`,
  `tick(T0+100k+20)` and a drain: the calls' `max_cost` are 0.008, 0.005 and 0.002 (`assertAlmostEqual`, 6 places);
  the fourth admission is False and the last `refused` line is `{"status": "cap", "error": "super agent day limit
  reached"}` (plus `ts` and `phase`); `superagent.status(*superagent.settings(hub.cfg), hub.super,
  sum(usage.super_spent(usage.load_super(home)["records"], day)), True)` is `(False, "over the day limit ($0.01)")`.
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
- `test_judge_model_for_submitted_stuck_work`: task 1 stuck at T0 selects Sonnet. Another task event, Sort and sweep
  still select Sonnet when that stuck subject is submitted; repeat with its visible kind suggestion.
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
