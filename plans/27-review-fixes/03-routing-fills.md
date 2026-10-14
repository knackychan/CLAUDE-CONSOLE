# Task 3: Routing and fills (B10, B11, B12, K7, K8, K9, G5, plan-18 nit)

> Contract: [README.md](README.md), the review findings B10, B11, B12, K7, K8, K9, G5 and the plan 18 nit "an unknown
> pick balances with no `pick refused` note". Depends on nothing of plan 27 (any order with Tasks 1, 2, 4, 5).
> Run in a scratch copy on 2026-10-14 (PR #1 head `cf69a48`, Linux, Python 3.13): before 525 run, 3 failures and 1
> error (the four Linux baseline failures); after 537 run, the same four, nothing else (12 tests added).
> Lands on: `console/server.py` functions `reload_models`, `rung_ok`, `poll_once`, `count_run` and one line of
> `start_step`. Task 4 also edits `start_step` (the git snapshot): this task only moves the one
> `self.reload_models()` line, so apply both by anchor, not by line number. Task 1 edits other functions of
> `console/paths.py` and `console/usage.py` is not in its list; this task touches `paths._ladder_from` only.

**Files**
- Modify: `console/tasks.py` (`step_route`: two edits)
- Modify: `console/fills.py` (`peak_add`: one line)
- Modify: `console/paths.py` (`_ladder_from` replaced whole)
- Modify: `console/usage.py` (the import block, `_read` replaced whole, new `_set_aside`, one line each in
  `load_days` and `load_other`, `add_other` and `save_days` replaced whole)
- Modify: `console/server.py` (`Hub.reload_models`, `Hub.rung_ok`, `Hub.poll_once`, `Hub.count_run` with a new class
  attribute `_count_lock`, one line moved in `Hub.start_step`)
- Modify: `tests/test_tasks.py`, `tests/test_fills.py`, `tests/test_usage.py`, `tests/test_harness.py`,
  `tests/test_server.py` (the tests in 3.6, and one changed assertion in
  `HarnessServerTest.test_run_refuses_off_or_unknown_rung`)

Decisions made while writing this task (the review does not make them):
- Decision: an unknown pick's note uses `refuse(pick)` first and `unknown model` only when the gate gives no reason,
  and is preceded by the usual `pick: <rung>` note, because in the service the gate is `rung_ok`, which now says
  `model gone from models.json: <rung>` (G5, README 3.2b of plan 5); `step_route` alone (tests, no gate) says
  `pick refused: unknown model -> balance`. The pin branch already reads `refuse` first the same way.
- Decision: `rung_ok`'s new reason covers rungs of the other harnesses only (after the on and found checks, as the
  review asks). A Claude rung keeps `unknown model or effort`: `rung_ok` checks no "on" or "found" for Claude, and a
  typo on a plain Run must stay a 400.
- Decision: `/api/run` with `codex:nope` on a codex that is on and found now answers 409
  `model gone from models.json: codex:nope` (was 400 `unknown model or effort`), because `_run` maps only the exact
  string `unknown model or effort` to 400 and this task does not touch `_run`. The one assertion of
  `test_run_refuses_off_or_unknown_rung` is updated.
- Decision: `count_run` holds a class-level `Hub._count_lock` around `add_other` and the assignment, because
  assigning the returned dict under `self.lock` alone still lets two overlapping calls assign in the wrong order
  (A writes, B writes, B assigns, A assigns its older dict: one run short, the K8 symptom). Lock order is
  `_count_lock` then `FILE_LOCK`, and `_count_lock` then `self.lock`; nothing takes `_count_lock` while holding
  either, so it cannot deadlock.
- Decision: an unreadable usage-days.json is copied (not moved) to `usage-days.json.bad`, once: the first copy is
  never overwritten by a later bad file. The original stays in place, readers see `{}` and writers skip until Fred
  mends or deletes it. A JSON value that is not an object counts as unreadable.
- Decision: `reload_models` logs only when it actually rereads (mtime changed or `force`), not at service start;
  `load_config` at start stays silent (it is not in the review's list).

## 3.1 `console/tasks.py` (`step_route`)

B10 and the plan 18 nit. Two edits inside `step_route`; nothing else in the function changes.

**Edit 1.** Insert after the line

```python
    picked = (fills.rank_of(pick, cfg) if cfg is not None else claude_cli.model_alias(pick)) if pick else ""
```

these lines:

```python
    if pick and not picked and cfg is not None:  # review plan-18 nit: a pick no list knows balances, with a note
        notes.append(f"pick: {pick}")
        notes.append(f"pick refused: {(refuse(pick) if refuse else '') or 'unknown model'} -> balance")
```

**Edit 2.** Replace these five lines (the end of the balance block) whole:

```python
        model = fills.rank_of(rung, cfg) or model
    elif cfg is not None:
        share = ((budget or {}).get(fills.model_key(rung, cfg)) or {}).get("share")
    if not rung:
        rung = model
```

with:

```python
        model = fills.rank_of(rung, cfg) or model
    if not rung:
        rung = model
    if cfg is not None and share is None:  # review B10: a pick, a pin or an empty pool reads its rung's own fill
        share = ((budget or {}).get(fills.model_key(rung, cfg)) or {}).get("share")
```

What changed: before, a verify whose pool was empty (every think rung refused) settled on `rung = model` with
`share` still None, so the `over pace` hold never ran. Now every route with `cfg` reads the settled rung's own fill
when the balance gave none. A balance that returned `share` None (no allowance) reads the same key again and gets
None again: no route changes. Only `verify` holds, as before.

## 3.2 `console/fills.py` (`peak_add`)

B11. Replace the line

```python
    except ValueError:
```

inside `peak_add` (the only `except` in that function) with:

```python
    except (ValueError, TypeError):  # review B11: a hand-edited "add": [1] must not break every route
```

## 3.3 `console/paths.py` (`_ladder_from`)

G5. Replace `def _ladder_from(...)` whole (its `def` line to the blank lines before `def load_config`) with:

```python
def _ladder_from(claude_models: dict, fallback: dict) -> dict:
    """tier -> rungs in file order, the alias (the tier's own name) first; only the tiers of claude_cli.MODELS
    (review G5: Hub.reload_models logs the others)."""
    from .claude_cli import MODELS  # late, as claude_cli.known_model imports harness: paths stays import-free
    ladder = {tier: [] for tier in fallback if tier in MODELS}
    for model, tier in claude_models.items():
        if tier in MODELS:
            ladder.setdefault(tier, []).append(model)
    return {tier: sorted(rungs, key=lambda m: m != tier) for tier, rungs in ladder.items() if rungs}
```

Do not add `claude_cli` to the module's import block (Task 1 edits `paths.py` too; `paths` imports nothing of the
console package at the top).

## 3.4 `console/usage.py`

K7 and K8.

**Imports.** Replace the two lines

```python
import os
import threading
```

at the top with:

```python
import os
import shutil
import threading
```

**`_read`.** Replace `def _read(folder) -> dict:` whole (the module-level one after `SEEN_DAYS`, not the method
`Usage._read`) with `_read` and the new `_set_aside`:

```python
def _read(folder):
    """usage-days.json as a dict: {} when it is missing, None when it is there but cannot be read or is not a JSON
    object (review K7: the writers then keep it as it is)."""
    try:
        text = (Path(folder) / DAYS_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _set_aside(folder) -> None:
    """Copy an unreadable usage-days.json to usage-days.json.bad, once (a later bad file keeps the first copy), so
    Fred can mend it by hand; the history and the other runs are never overwritten. Never raises."""
    bad = Path(folder) / (DAYS_FILE + ".bad")
    if bad.exists():
        return
    try:
        shutil.copyfile(Path(folder) / DAYS_FILE, bad)
    except OSError:
        pass
```

**`load_days`.** Replace `    days = _read(folder).get("days")` with:

```python
    days = (_read(folder) or {}).get("days")
```

**`load_other`.** Replace `    other = _read(folder).get("other")` with:

```python
    other = (_read(folder) or {}).get("other")
```

**`add_other`.** Replace `def add_other(...)` whole (to the blank lines before `def merge_days`) with:

```python
def add_other(folder, run_id: str, day: str, key: str, tokens, cost):
    """Count one ended run of another harness under `day` and `key`: its priced cost, or one unknown run when
    `cost` is None (D-3, never zero); its tokens [input, output, cache read] when known. Returns the runs of other
    harnesses as written (load_other's shape, read under FILE_LOCK: review K8); None when `run_id` was already
    counted (a restart replays the event files) or the file cannot be read or written."""
    with FILE_LOCK:
        data = _read(folder)
        if data is None:  # review K7: never overwrite a file that cannot be read
            _set_aside(folder)
            return None
        seen = data.get("seen") if isinstance(data.get("seen"), dict) else {}
        if any(run_id in ids for ids in seen.values() if isinstance(ids, list)):
            return None
        other = data.get("other") if isinstance(data.get("other"), dict) else {}
        row = other.setdefault(day, {}).setdefault(key, {"cost": 0.0, "runs": 0, "unknown": 0, "tokens": [0, 0, 0]})
        row["runs"] += 1
        if cost is None:
            row["unknown"] += 1
        else:
            row["cost"] = round(row["cost"] + float(cost), 6)
        if isinstance(tokens, dict):
            row["tokens"] = [a + int(tokens.get(k) or 0) for a, k in zip(row["tokens"], ("input", "output", "cache_read"))]
        cutoff = (_date(day) - timedelta(days=SEEN_DAYS - 1)).isoformat()
        seen = {d: ids for d, ids in seen.items() if d >= cutoff and isinstance(ids, list)}
        seen.setdefault(day, []).append(run_id)
        data.update(other=other, seen=seen)
        try:
            _write(folder, data)
        except OSError:
            return None
        return {d: v for d, v in other.items() if isinstance(v, dict)}
```

The return was `True`/`False`; it is now the dict (never empty after a write) or None, so every existing
`assertTrue`/`assertFalse` on it still holds.

**`save_days`.** Replace `def save_days(...)` whole (to the blank lines before `def folder_sizes`) with:

```python
def save_days(folder, days: dict, today: str) -> bool:
    """Keep the closed days (before `today`) of `days` merged into usage-days.json; False when nothing
    changed (no write), when the file cannot be read (it is kept and copied aside: review K7) or cannot be written.
    Every other key of the file is kept."""
    with FILE_LOCK:
        data = _read(folder)
        if data is None:
            _set_aside(folder)
            return False
        kept = load_days(folder)
        merged = merge_days(kept, {d: v for d, v in days.items() if d < today})
        if merged == kept:
            return False
        data["days"] = dict(sorted(merged.items()))  # "other" and "seen" (plan 18) stay as written
        try:
            _write(folder, data)
        except OSError:
            return False
        return True
```

## 3.5 `console/server.py` (class `Hub`)

**`reload_models` (G5).** Insert after the last two lines of the `with self.lock:` block of `reload_models`

```python
            self.version += 1
            self.changed.notify_all()
```

(the ones just before `def _config_mtime`), at the method's indentation (8 spaces), these lines:

```python
        for name, listed in ({} if error else models).items():  # review G5: what the readers leave out, logged
            held = harness.tiers_of(self.cfg, name) if name in harness.NAMES else claude_cli.MODELS
            for model, tier in listed.items():
                if tier not in claude_cli.MODELS:
                    self._log(f"models.json: {name} {model} dropped: unknown tier {tier}")
                elif tier not in held:
                    self._log(f"models.json: {name} {model} dropped: {name} holds no {tier} model")
```

Nothing is dropped here: the readers already leave these entries out (`_ladder_from` from 3.3, `fills.rank_of`,
`claude_cli.tier_of`, `harness.models_of`); this only logs them, outside the lock, once per reread.

**`rung_ok` (G5).** Insert after the two lines

```python
            if not self.found.get(name):
                return f"{name}: not found on PATH"
```

(inside `if name != "claude":`) these lines, at the same indentation:

```python
            if bare not in claude_cli._rung_models(self.cfg, name):  # review G5: README 3.2b of plan 5
                return f"model gone from models.json: {rung}"
```

**`poll_once` (K9).** Replace the three lines

```python
        for rec in new:  # plan 18: the fills count other harnesses' runs from their run_ended lines
            if rec.get("event") == "run_ended":
                self.count_run(rec)
```

with:

```python
        for rec in new:  # plan 18: the fills count other harnesses' runs from their run_ended lines
            if rec.get("event") == "run_ended":
                try:  # review K9: a malformed line never escapes into start_step or the hub loop
                    self.count_run(rec)
                except Exception as exc:
                    self._log(f"count_run {rec.get('session_id')}: {type(exc).__name__}: {exc}")
```

**`count_run` (K8).** Replace `def count_run(...)` whole (to the blank line before `def read_costs`) with the class
attribute and the method:

```python
    _count_lock = threading.Lock()  # review K8: one count_run at a time (request threads call poll_once too)

    def count_run(self, rec: dict) -> bool:
        """One ended run of a harness other than Claude (whose transcripts the history prices) into usage-days.json:
        the cost it reported, else its tokens at the price row of its model key, else one unknown run (D-3)."""
        meta = self.runs.meta(rec["session_id"]) or {}
        harness_name = meta.get("harness") or "claude"
        if harness_name == "claude" or not meta.get("model"):
            return False
        key = fills.model_key(f"{harness_name}:{meta['model']}", self.cfg)
        cost = rec.get("cost")
        if not isinstance(cost, (int, float)):
            cost = fills.price(rec.get("tokens"), (self.cfg.get("prices") or {}).get(key))  # D3: None = unknown
        ts = float(rec.get("ts") or time.time())
        with self._count_lock:  # review K8: the dict add_other wrote under FILE_LOCK, kept in the order written
            other = usage.add_other(self.folder, f"{rec['session_id']}@{ts}", usage.day_of(ts), key, rec.get("tokens"), cost)
            if other is None:
                return False
            with self.lock:
                self.usage_other = other
                self.version += 1
                self.changed.notify_all()
        return True
```

**`start_step` (B12).** One line moves; touch nothing else in `start_step` (Task 4 edits it too). Replace

```python
        s, now, lines = tasks.step(task, n), time.time(), []
        route = self._route_for(task, s)
```

with:

```python
        s, now, lines = tasks.step(task, n), time.time(), []
        self.reload_models()  # review B12: a models.json edit reaches this step's route, not the next one
        route = self._route_for(task, s)
```

and delete the line `        self.reload_models()` that stands just before
`        kind, tier, model = s["kind"], route["model"], route["rung"]  # plan 18: the route chose the rung`.

## 3.6 Tests

**`tests/test_tasks.py`.** In class `BalanceRouteTest`, insert after the last method
`test_pick_runs_as_given_and_a_refused_pick_balances` (before `class PinRouteTest`):

```python
    def test_an_empty_pool_verify_still_holds_over_pace(self):
        route = self.route("verify", checked=("sonnet", "medium"), budget=shares({"opus": 0.9}),
                           refuse=lambda rung: "off")
        self.assertEqual((route["rung"], route["hold"]), ("opus", "opus over its pace"))
        self.assertEqual(route["notes"][-1], "over pace: opus 90 % -> hold")
        route = self.route("verify", checked=("sonnet", "medium"), budget=shares({"opus": 0.5}),
                           refuse=lambda rung: "off")
        self.assertEqual(route["hold"], "")

    SPREAD = shares({"sonnet": 0.2, "gpt-6.1-sol": 0.5, "deepseek-v4.1-flash": 0.5})

    def test_an_unknown_pick_balances_with_a_note(self):
        route = self.route("code", pick="codex:gpt-9", budget=self.SPREAD)
        self.assertEqual(route["rung"], "sonnet")
        self.assertEqual(route["notes"][1:3], ["pick: codex:gpt-9", "pick refused: unknown model -> balance"])
        gone = lambda rung: f"model gone from models.json: {rung}" if rung == "codex:gpt-9" else ""
        route = self.route("code", pick="codex:gpt-9", budget=self.SPREAD, refuse=gone)
        self.assertIn("pick refused: model gone from models.json: codex:gpt-9 -> balance", route["notes"])
```

**`tests/test_fills.py`.** In `BalanceTest.test_peak_hours_add_in_their_hours`, insert after the line

```python
        self.assertEqual(fills.peak_add(dict(CFG, peak_hours={"anthropic": {"hours": "x"}}), "opus", NOW), 0.0)
```

these lines:

```python
        self.assertEqual(fills.peak_add(dict(CFG, peak_hours={"anthropic": {"hours": "14-19", "add": [1]}}), "opus", NOW), 0.0)
        self.assertEqual(fills.peak_add(dict(CFG, peak_hours={"anthropic": {"hours": "14-19", "add": {}}}), "opus", NOW), 0.0)
```

**`tests/test_usage.py`.** Replace the import lines `import tempfile` and `import unittest` with:

```python
import tempfile
import unittest
from unittest import mock
```

In class `OtherRunsTest`, insert after the last method `test_seen_ids_are_kept_three_days`, and add the new class
after it (before `if __name__`):

```python
    def test_add_other_returns_what_it_wrote(self):
        with tempfile.TemporaryDirectory() as folder:
            wrote = usage.add_other(folder, "s4@1.0", "2026-10-14", "kimi-k3", None, 1.0)
            self.assertEqual(wrote, usage.load_other(folder))
            self.assertEqual(wrote["2026-10-14"]["kimi-k3"]["cost"], 1.0)
            self.assertIsNone(usage.add_other(folder, "s4@1.0", "2026-10-14", "kimi-k3", None, 1.0))


class UnreadableDaysFileTest(unittest.TestCase):
    """Review K7: an unreadable usage-days.json is never overwritten; it is copied aside once."""

    def test_writers_skip_an_unreadable_file_and_copy_it_aside_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path, bad = folder / usage.DAYS_FILE, folder / (usage.DAYS_FILE + ".bad")
            path.write_text('{"days": {"2026-10-01": {"cost": 9.0}}, "seen"', encoding="utf-8")
            self.assertFalse(usage.add_other(folder, "s5@1.0", "2026-10-14", "kimi-k3", None, 1.0))
            self.assertFalse(usage.save_days(folder, {"2026-10-12": {"cost": 2.0}}, "2026-10-14"))
            self.assertEqual(path.read_text(encoding="utf-8"), '{"days": {"2026-10-01": {"cost": 9.0}}, "seen"')
            self.assertEqual(bad.read_text(encoding="utf-8"), path.read_text(encoding="utf-8"))
            path.write_text("[]", encoding="utf-8")  # not an object: unreadable too; the first copy stays
            self.assertFalse(usage.save_days(folder, {"2026-10-12": {"cost": 2.0}}, "2026-10-14"))
            self.assertEqual((path.read_text(encoding="utf-8"), bad.read_text(encoding="utf-8")[:9]), ("[]", '{"days": '))
            self.assertEqual((usage.load_days(folder), usage.load_other(folder)), ({}, {}))

    def test_a_missing_file_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(usage.save_days(tmp, {"2026-10-12": {"cost": 2.0}}, "2026-10-14"))
            self.assertFalse((Path(tmp) / (usage.DAYS_FILE + ".bad")).exists())

    def test_save_days_returns_false_when_the_write_fails(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(usage, "_write", side_effect=OSError("disk full")):
            self.assertFalse(usage.save_days(tmp, {"2026-10-12": {"cost": 2.0}}, "2026-10-14"))
```

**`tests/test_harness.py`.** In class `HarnessTest`, insert before `def test_defaults_and_claude_exe_fallback`:

```python
    def test_ladder_keeps_only_known_tiers(self):
        got = paths._ladder_from({"opus": "opus", "claude-opus-4-8": "opus", "gpt-x": "gpt", "y": "", "z": 3},
                                 {"sonnet": ["sonnet"], "mythos": ["m"]})
        self.assertEqual(got, {"opus": ["opus", "claude-opus-4-8"]})

```

**`tests/test_server.py`.** Add `import copy` after `import base64` at the top.

In class `TaskServerTest`, insert after `test_runs_of_another_harness_count_once` (after its last line
`self.assertEqual(today["fills"]["over"], [])`):

```python
    def test_count_run_keeps_what_add_other_wrote(self):
        sid, ts = "0000-codex", time.time()
        self.hub.runs.runs.mkdir(parents=True, exist_ok=True)
        self.hub.runs.meta_path(sid).write_text(json.dumps({"harness": "codex", "model": "gpt-6.1-sol"}), encoding="utf-8")
        rec = {"event": "run_ended", "session_id": sid, "ts": ts, "cost": 0.5}
        with mock.patch.object(usage, "load_other", side_effect=AssertionError("read after FILE_LOCK")):
            self.assertTrue(self.hub.count_run(rec))
        self.assertEqual(self.hub.usage_other[usage.day_of(ts)]["gpt-6.1-sol"]["cost"], 0.5)

    def test_a_bad_run_ended_line_never_escapes_poll_once(self):
        sid = "0000-codex"
        self.hub.runs.runs.mkdir(parents=True, exist_ok=True)
        self.hub.runs.meta_path(sid).write_text(json.dumps({"harness": "codex", "model": "gpt-6.1-sol"}), encoding="utf-8")
        rec = {"event": "run_ended", "session_id": sid, "ts": time.time(), "tokens": {"input": "lots"}}
        with mock.patch.object(self.hub.reader, "read_new", return_value=[rec]):
            self.assertEqual(self.hub.poll_once(), 1)
        log = (self.folder / "console.log").read_text(encoding="utf-8")
        self.assertIn("count_run 0000-codex: ValueError", log)
```

In class `HarnessServerTest`, `test_run_refuses_off_or_unknown_rung`: replace

```python
        self.assertEqual((status, data["error"]), (400, "unknown model or effort"))
```

with:

```python
        self.assertEqual((status, data["error"]), (409, "model gone from models.json: codex:nope"))
```

In class `HarnessServerTest`, insert before `def test_step_timeout_reaches_the_retry_reason`:

```python
    def use_models_json(self, models):
        """models.json under a data folder the test owns (the Hub reads paths.home()), written with a new mtime."""
        patcher = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": str(self.folder)})
        patcher.start()
        self.addCleanup(patcher.stop)
        path = self.folder / "models.json"
        path.write_text(json.dumps(models), encoding="utf-8")
        old = self.hub.models_mtime or 0
        os.utime(path, ns=(old + 10**9, old + 10**9))

    def test_rung_gone_from_models_json(self):
        self.hub.cfg["models"]["codex"] = {"gpt-6-sol": "sonnet"}
        self.assertEqual(self.hub.rung_ok("codex:gpt-6.1-sol"), "model gone from models.json: codex:gpt-6.1-sol")
        self.assertEqual(self.hub.rung_ok("codex:gpt-6-sol"), "")
        self.hub.cfg["harnesses"]["codex"]["on"] = False
        self.assertEqual(self.hub.rung_ok("codex:gpt-6.1-sol"), "codex is off")

    def test_models_json_is_reread_before_the_route(self):
        steps = [{"kind": "scout", "goal": "look"}, {"kind": "scout", "goal": "again", "model": "codex:gpt-6.1-sol"}]
        tid = self.make_task(steps=steps)
        self.until(tid, self.at(1), "step 1 starts")
        self.use_models_json(dict(copy.deepcopy(paths.MODELS_DEFAULT), codex={"gpt-6-sol": "sonnet"}))
        task = self.until(tid, self.at(2), "step 2 starts")
        step = task["steps"][1]
        self.assertEqual(step["harness"], "claude")
        self.assertIn("pick refused: model gone from models.json: codex:gpt-6.1-sol -> balance", step["notes"])

    def test_reload_models_logs_what_it_drops(self):
        models = copy.deepcopy(paths.MODELS_DEFAULT)
        models["claude"]["claude-x"] = "gpt"
        models["opencode"] = {"opencode-go/kimi-k3": "opus", "opencode-go/sonnet-ish": "sonnet"}
        self.use_models_json(models)
        self.hub.reload_models()
        log = (self.folder / "console.log").read_text(encoding="utf-8")
        self.assertIn("models.json: claude claude-x dropped: unknown tier gpt", log)
        self.assertIn("models.json: opencode opencode-go/sonnet-ish dropped: opencode holds no sonnet model", log)
        self.assertNotIn("kimi-k3", log)
        self.assertNotIn("gpt", self.hub.cfg["ladder"])

```

`use_models_json` patches `CC_CONSOLE_HOME` for the one test: the server tests otherwise never set it, so the Hub's
`_models_mtime` looks at the real `~/.claude/console/models.json` (None on a machine without one). The new mtime is
one second past the one the Hub kept, so `reload_models` rereads.

What each asserts and the failure seen before the fix (scratch copy, 2026-10-14):

| Test | Finding | Before the fix |
|---|---|---|
| `test_an_empty_pool_verify_still_holds_over_pace` | B10 | `AssertionError: Tuples differ: ('opus', '') != ('opus', 'opus over its pace')` |
| `test_an_unknown_pick_balances_with_a_note` | nit | `AssertionError: Lists differ: ['balance: sonnet 20 %'] != ['pick: codex:gpt-9', 'pick refused: unknown model -> balance']` |
| `test_peak_hours_add_in_their_hours` (2 lines) | B11 | `TypeError: float() argument must be a string or a real number, not 'list'` |
| `test_models_json_is_reread_before_the_route` | B12 | `AssertionError: 'codex' != 'claude'` (also seen with every other fix of this task applied and only the `reload_models` line left where it was) |
| `test_writers_skip_an_unreadable_file_and_copy_it_aside_once` | K7 | `AssertionError: True is not false` (add_other overwrote the bad file) |
| `test_save_days_returns_false_when_the_write_fails` | K7 | `OSError: disk full` |
| `test_a_missing_file_is_written` | K7 | passes before and after (guards the missing-file path) |
| `test_add_other_returns_what_it_wrote` | K8 | `AssertionError: True != {'2026-10-14': {'kimi-k3': {'cost': 1.0, ...}}}` |
| `test_count_run_keeps_what_add_other_wrote` | K8 | `AssertionError: read after FILE_LOCK` (count_run reread with `load_other`) |
| `test_a_bad_run_ended_line_never_escapes_poll_once` | K9 | `ValueError: invalid literal for int() with base 10: 'lots'` |
| `test_rung_gone_from_models_json` | G5 | `AssertionError: 'unknown model or effort' != 'model gone from models.json: codex:gpt-6.1-sol'` |
| `test_ladder_keeps_only_known_tiers` | G5 | `AssertionError: {'opus': [...], 'gpt': ['gpt-x']} != {'opus': ['opus', 'claude-opus-4-8']}` |
| `test_reload_models_logs_what_it_drops` | G5 | `FileNotFoundError: ... home/console.log` (nothing logged) |

## 3.7 Steps

1. Add every test of 3.6 (and the changed assertion). Run
   `py -m unittest tests.test_tasks tests.test_fills tests.test_usage tests.test_harness tests.test_server.TaskServerTest tests.test_server.HarnessServerTest`:
   the twelve listed tests fail or error with the messages in the table (`test_a_missing_file_is_written` passes;
   `test_run_refuses_off_or_unknown_rung` fails on its changed line until 3.5).
2. Apply 3.1 (`tasks.py`), 3.2 (`fills.py`), 3.3 (`paths.py`), 3.4 (`usage.py`), 3.5 (`server.py`) by their anchors.
3. Run the same command: all OK (on Linux, `test_usage.HistoryTest.test_sums_each_local_day_once_per_message` is
   a baseline failure and stays one).
4. The full suite `py -m unittest discover -s tests`: Linux scratch 525 -> 537, only the four Linux baseline
   failures (test_tray import, test_redact Windows path, test_usage local day, test_window placement); on Windows
   all OK.
5. Commit: `Plan 27 Task 3: routing and fills fixes (B10-B12, K7-K9, G5, unknown pick note) (N tests OK)`.

## 3.8 Drift guards

- `step_route` stays pure: the new note reads only `refuse` and `cfg`; no `Hub`, no file. A pick that is known keeps
  its notes exactly as before; without `cfg` (plan 17's path) nothing changes.
- Only a `verify` holds over `budget_warn_at`; the B10 lookup must not add a hold to any other kind.
- `peak_add` still returns 0.0 for any malformed rule; do not log from it (it runs on every route).
- `usage._read` returns `{}` only for a missing file. No writer may write when it returned None. The `.bad` copy is
  made once and never overwritten; nothing deletes or moves `usage-days.json`. Everything stays in the console data
  folder (CLAUDE.md).
- `add_other`'s return is the only source of `Hub.usage_other` after a run is counted; `count_run` must not call
  `usage.load_other` again. Keep the lock order: `_count_lock`, then `FILE_LOCK` (inside `add_other`), then
  `self.lock`; never call `count_run` while holding `self.lock` (`poll_once` calls it after its `with self.lock:`).
- `poll_once` catches around `count_run` only, not around `state.apply` or the reader.
- `rung_ok`'s order stays: off, not found, model gone, unknown model or effort, the kind rules. Do not touch `_run`
  or `_create` (Task 5's and others' functions); their error texts follow `rung_ok`.
- `reload_models` logs outside `self.lock` and never changes `cfg["models"]` beyond what it did before; it is the
  readers that leave the entries out.
- In `start_step`, only the `self.reload_models()` line moves; Task 4's git snapshot edits in the same function are
  separate and must both survive.
