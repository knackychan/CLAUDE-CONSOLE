# Task 3: The other harnesses' runs in usage-days.json

> Contract: [README.md](README.md) 3.5, 3.8. Depends on nothing. Run in a scratch copy on 2026-10-14: the four new
> tests OK, `tests/test_usage.py`'s earlier tests unchanged. Lands on: nothing (plans 5, 23, 24 leave `usage.py` alone).

**Files**
- Modify: `console/usage.py` (`load_days` rewritten over a new `_read`, new `_write`, `FILE_LOCK`, `SEEN_DAYS`,
  `load_other`, `add_other`; `save_days` under the lock, keeping every other key)
- Modify: `tests/test_usage.py` (class `OtherRunsTest`, before `if __name__`)

## 3.1 `console/usage.py`

Replace `def load_days(folder) -> dict:` (its whole body) with:

```python
FILE_LOCK = threading.Lock()  # usage-days.json: the history thread saves days, the hub thread adds runs (plan 18)
SEEN_DAYS = 3  # run ids are kept this many days: the event reader replays the last two daily files at start


def _read(folder) -> dict:
    try:
        data = json.loads((Path(folder) / DAYS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(folder, data: dict) -> None:
    path = Path(folder) / DAYS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(DAYS_FILE + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_days(folder) -> dict:
    """The closed days kept in usage-days.json ({} when missing or unreadable)."""
    days = _read(folder).get("days")
    return {d: v for d, v in days.items() if isinstance(v, dict)} if isinstance(days, dict) else {}


def load_other(folder) -> dict:
    """The runs of other harnesses per day (plan 18): {day: {model key: {"cost", "runs", "unknown", "tokens"}}}
    ({} when missing or unreadable). Kept for good, next to the days."""
    other = _read(folder).get("other")
    return {d: v for d, v in other.items() if isinstance(v, dict)} if isinstance(other, dict) else {}


def add_other(folder, run_id: str, day: str, key: str, tokens, cost) -> bool:
    """Count one ended run of another harness under `day` and `key`: its priced cost, or one unknown run when
    `cost` is None (D-3, never zero); its tokens [input, output, cache read] when known. False when `run_id` was
    already counted (a restart replays the event files) or the file cannot be written."""
    with FILE_LOCK:
        data = _read(folder)
        seen = data.get("seen") if isinstance(data.get("seen"), dict) else {}
        if any(run_id in ids for ids in seen.values() if isinstance(ids, list)):
            return False
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
            return False
        return True
```

`_date` and `timedelta` already exist in the module (`weeks` uses them); `threading` is imported at the top.

Replace the body of `save_days` (keep its signature) with:

```python
def save_days(folder, days: dict, today: str) -> bool:
    """Keep the closed days (before `today`) of `days` merged into usage-days.json; False when nothing
    changed (no write). Every other key of the file is kept."""
    with FILE_LOCK:
        data = _read(folder)
        kept = load_days(folder)
        merged = merge_days(kept, {d: v for d, v in days.items() if d < today})
        if merged == kept:
            return False
        data["days"] = dict(sorted(merged.items()))  # "other" and "seen" (plan 18) stay as written
        _write(folder, data)
        return True
```

## 3.2 Tests (`tests/test_usage.py`, class `OtherRunsTest`)

```python
class OtherRunsTest(unittest.TestCase):
    """Plan 18: runs of other harnesses kept per day in usage-days.json, next to the days."""
    TOK = {"input": 1000, "output": 200, "cache_read": 500}

    def test_a_run_counts_once(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(usage.add_other(folder, "s1@1.0", "2026-10-14", "gpt-6.1-sol", self.TOK, 0.25))
            self.assertFalse(usage.add_other(folder, "s1@1.0", "2026-10-14", "gpt-6.1-sol", self.TOK, 0.25))
            self.assertTrue(usage.add_other(folder, "s1@2.0", "2026-10-14", "gpt-6.1-sol", self.TOK, 0.5))
            row = usage.load_other(folder)["2026-10-14"]["gpt-6.1-sol"]
            self.assertEqual(row, {"cost": 0.75, "runs": 2, "unknown": 0, "tokens": [2000, 400, 1000]})

    def test_an_unpriced_run_is_unknown_never_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.add_other(folder, "s2@1.0", "2026-10-14", "deepseek-v4.1-flash", None, None)
            usage.add_other(folder, "s2@2.0", "2026-10-14", "deepseek-v4.1-flash", self.TOK, None)
            row = usage.load_other(folder)["2026-10-14"]["deepseek-v4.1-flash"]
            self.assertEqual((row["runs"], row["unknown"], row["cost"], row["tokens"]), (2, 2, 0.0, [1000, 200, 500]))

    def test_save_days_keeps_the_other_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.add_other(folder, "s3@1.0", "2026-10-12", "kimi-k3", self.TOK, 1.0)
            day = {"cost": 2.0, "tokens": [1, 2, 3, 4], "projects": {}, "models": {"opus": 2.0}}
            self.assertTrue(usage.save_days(folder, {"2026-10-12": day}, "2026-10-14"))
            self.assertEqual(usage.load_days(folder)["2026-10-12"]["cost"], 2.0)
            self.assertEqual(usage.load_other(folder)["2026-10-12"]["kimi-k3"]["cost"], 1.0)
            usage.add_other(folder, "s3@2.0", "2026-10-13", "kimi-k3", self.TOK, 1.0)
            self.assertEqual(usage.load_days(folder)["2026-10-12"]["cost"], 2.0)  # adding a run keeps the days

    def test_seen_ids_are_kept_three_days(self):
        with tempfile.TemporaryDirectory() as folder:
            usage.add_other(folder, "old@1.0", "2026-10-10", "kimi-k3", None, None)
            usage.add_other(folder, "new@1.0", "2026-10-14", "kimi-k3", None, None)
            seen = json.loads((Path(folder) / usage.DAYS_FILE).read_text(encoding="utf-8"))["seen"]
            self.assertEqual(seen, {"2026-10-14": ["new@1.0"]})
            self.assertEqual(usage.load_other(folder)["2026-10-10"]["kimi-k3"]["runs"], 1)  # the counts stay
```

- `test_a_run_counts_once`: the same run id twice counts once; two runs sum cost and tokens.
- `test_an_unpriced_run_is_unknown_never_zero`: `cost None` adds to `unknown`, never to `cost`; tokens still add.
- `test_save_days_keeps_the_other_runs`: `save_days` after `add_other` keeps `other`, and `add_other` keeps `days`.
- `test_seen_ids_are_kept_three_days`: an id older than three days leaves `seen`; its counts stay in `other`.

## 3.3 Steps

1. Add `OtherRunsTest`; run `py -m unittest tests.test_usage`: AttributeError on `add_other`.
2. The `usage.py` changes; run: every test OK.
3. The whole suite: the count + 4.
4. Commit: `plan 18 task 3: other harnesses' runs kept per day in usage-days.json (N tests OK)`.

## 3.4 Drift guards

- usage-days.json is written through a temp file and `os.replace`, under `FILE_LOCK`, by these two functions only.
- `save_days` never drops a key it does not own; `add_other` never touches `days`.
- A run with no price is one more `unknown`, never `cost += 0` read as priced.
