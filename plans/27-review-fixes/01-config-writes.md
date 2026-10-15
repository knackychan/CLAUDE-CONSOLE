# Task 1: config.json writes (K1, K2, B7, G8)

> Contract: [review.md](review.md) findings K1, K2, B7 and G8; plan 26 README 3.1 (Reload shows a hand edit),
> plan 24 README D2 (a) (`opus_max_turns` "is read as a fallback once, then dropped from config.json").
> Depends on: nothing of plan 27 (the first task). Decisions: two, marked `Decision:` in 1.3 and 1.1.
> Run in a scratch copy on 2026-10-14: the whole suite 532 tests (525 before, seven added), only the 4 Linux
> baseline failures (test_tray import, test_redact Windows path, test_usage local day, test_window placement);
> `tests.test_paths` 6 OK (3 before), `tests.test_tuning` 14 OK (13 before).
> Lands on: plan 26 Task 1 (`set_config`, `tuning._number`, `Hub.reload_tuning`, `Hub.save_models`,
> `Handler._config_models`), plan 23 (`set_setting`, `Handler._setting`), plan 5 (`set_harness`, `Handler._harness`),
> plan 24 Task 1 (the `opus_max_turns` fallback in `load_config`, kept as is). Tasks 2 to 6 of plan 27 touch none of
> these functions.

**Files**
- Modify: `console/paths.py` (new `CONFIG_LOCK`, `_rewrite_config`, `_drop_opus_max_turns`; `set_harness`,
  `add_project`, `set_config`, `set_setting` rewritten on `_rewrite_config`; one line in `ensure_config`)
- Modify: `console/tuning.py` (`_number`: the first `if`)
- Modify: `console/server.py` (`Hub.reload_tuning` replaced whole; `Handler._harness`, `Handler._setting`,
  `Handler._allow`, `Handler._config_models`: one `except OSError` each)
- Modify: `tests/test_paths.py` (`import threading`; `PlanKeysTest.test_opus_max_turns_is_read_once_then_dropped`;
  class `ConfigWriteTest`)
- Modify: `tests/test_tuning.py` (`NumbersTest.test_a_huge_integer_is_refused_not_raised`)
- Modify: `tests/test_server.py` (three tests in `TaskServerTest`)

What the review found, in short: the four config.json writers read, change and write the file with no lock and one
shared `config.json.tmp`, from the threads of a `ThreadingHTTPServer` (K1: a lost update, or `FileNotFoundError` when
one thread's `os.replace` moves the temp file another thread is about to move; on Windows `os.replace` can also raise
`PermissionError`, which no handler catches, so the POST drops the connection). `Hub.reload_tuning` keeps the live
value of a page key Fred deleted by hand and takes any value without a check (K2). `tuning._number` calls `math.isfinite`
and `float()` on a huge int and raises `OverflowError` (B7). `opus_max_turns` is read on every load and never leaves
config.json (G8).

## 1.1 `console/paths.py`

Replace everything from `def set_harness(folder: Path, name: str, on: bool) -> None:` down to (not including) the line
`_WINDOW_LOCK = threading.Lock()  # the page (project) and the window (form, place) both save` whole (that is
`set_harness`, `add_project`, `set_config`, the `SETTINGS` line and `set_setting`) with:

```python
CONFIG_LOCK = threading.Lock()  # plan 27 (K1): every read-modify-write of config.json; the HTTP handlers run in threads


def _rewrite_config(path: Path, change, missing=None) -> None:
    """Read <path> (config.json), apply `change(data)` and write it back whole through a temp file of this write's
    own, all under CONFIG_LOCK. A missing file starts as `missing()`, or raises ValueError when `missing` is None;
    a file that is not a JSON object raises ValueError and is left as is (never overwrite Fred's file). OSError
    from the write (os.replace on Windows while a reader holds the file) propagates, with the temp file removed."""
    with CONFIG_LOCK:
        if path.exists() or missing is None:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None
            if not isinstance(data, dict):
                raise ValueError(f"cannot read {path}: fix it by hand")
        else:
            data = missing()
        change(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"config.json.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise


def set_harness(folder: Path, name: str, on: bool) -> None:
    """Write harnesses.<name>.on into <folder>/config.json; every other key stays as written.
    Raises ValueError for an unknown name or a config.json that cannot be read."""
    if name not in HARNESSES:
        raise ValueError(f"unknown harness: {name}")

    def change(data):
        harnesses = data.get("harnesses")
        if not isinstance(harnesses, dict):
            harnesses = data["harnesses"] = {}
        entry = harnesses.get(name)
        if not isinstance(entry, dict):
            entry = harnesses[name] = {"on": False, "exe": ""}
        entry["on"] = bool(on)

    _rewrite_config(Path(folder) / "config.json", change)


def add_project(folder: Path, project: str) -> None:
    """Add `project` to "projects" in <folder>/config.json; every other key stays as written.
    Raises ValueError when config.json exists but cannot be read (never overwrite Fred's file)."""

    def change(data):
        projects = data.get("projects") if isinstance(data.get("projects"), list) else []
        key = os.path.normcase(os.path.abspath(project))
        if all(os.path.normcase(os.path.abspath(p)) != key for p in projects if isinstance(p, str)):
            projects.append(project)
        data["projects"] = projects

    _rewrite_config(Path(folder) / "config.json", change, lambda: copy.deepcopy(DEFAULTS))


def set_config(folder: Path, values: dict, merge=("tiers",)) -> None:
    """Write `values` into <folder>/config.json with every other key as written (plan 26; set_harness does the same
    for one key): a key named in `merge` updates the file's object one level deep (a tier Fred did not touch keeps
    its list), any other key replaces the file's value. Raises ValueError when config.json exists but cannot be read
    (never overwrite Fred's file)."""

    def change(data):
        for key, value in values.items():
            if key in merge and isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value

    _rewrite_config(Path(folder) / "config.json", change, dict)


SETTINGS = ("handoff_auto",)  # plan 23: the booleans the window may flip through POST /api/setting


def set_setting(folder: Path, key: str, value: bool) -> None:
    """Write one whitelisted boolean into <folder>/config.json; every other key stays as written. ValueError for a key
    that is not in SETTINGS, a value that is not a bool, or a config.json that cannot be read."""
    if key not in SETTINGS:
        raise ValueError(f"not a setting: {key}")
    if not isinstance(value, bool):
        raise ValueError(f"{key} takes true or false")

    def change(data):
        data[key] = value

    _rewrite_config(Path(folder) / "config.json", change, lambda: copy.deepcopy(DEFAULTS))


def _drop_opus_max_turns(folder: Path) -> None:
    """Plan 24 D2: the old opus_max_turns counts once as design_max_turns (when that key is not set), then leaves
    config.json. Run at the service start; a file that cannot be read or written is left as is."""
    path = Path(folder) / "config.json"
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(user, dict) or "opus_max_turns" not in user:
        return

    def change(data):
        if "opus_max_turns" in data:
            data.setdefault("design_max_turns", data["opus_max_turns"])
            del data["opus_max_turns"]

    try:
        _rewrite_config(path, change)
    except (OSError, ValueError):
        pass  # load_config still reads the old key as the fallback
```

Keep the two blank lines before `_WINDOW_LOCK`. `threading` is already imported (for `_WINDOW_LOCK`).

In `ensure_config`, insert after the line
`        path.write_text(json.dumps(DEFAULTS, indent=2) + "\n", encoding="utf-8")` (dedented one level, so it runs
whether or not the file was just written), before `    load_models()  # writes models.json when missing`:

```python
    _drop_opus_max_turns(path.parent)
```

`ensure_config` then reads:

```python
def ensure_config() -> dict:
    """Write config.json with the defaults if it does not exist, then load it."""
    path = home() / "config.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULTS, indent=2) + "\n", encoding="utf-8")
    _drop_opus_max_turns(path.parent)
    load_models()  # writes models.json when missing
    return load_config()
```

Decision: the `opus_max_turns` drop runs in `ensure_config` (the service start, `console/__main__.py`), not in
`load_config`, because `load_config` stays a pure read (tests and any future caller can load the config without
writing it) and the start is the "once" D2 means. `load_config`'s fallback lines stay: they cover a file that could
not be rewritten.

Behaviour kept from today: `set_harness` refuses a missing config.json (`missing=None`); `add_project` and
`set_setting` start a missing file from `DEFAULTS`; `set_config` starts it empty (`dict`); every writer raises
`ValueError("cannot read <path>: fix it by hand")` and leaves an unreadable file untouched. New: the temp file is
`config.json.<pid>.<thread id>.tmp` and is removed when the write fails; the `OSError` reaches the caller.

## 1.2 `console/tuning.py` (`_number`)

Replace these two lines of `_number`:

```python
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return f"a whole number {span}" if whole else f"a number {span}"
```

with:

```python
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"a whole number {span}" if whole else f"a number {span}"
    if isinstance(value, int) and not low <= value <= high:
        return span  # plan 27 (B7): a huge int never reaches float(), which raises OverflowError
    if not math.isfinite(value):
        return f"a whole number {span}" if whole else f"a number {span}"
```

The rest of `_number` stays. An int inside a range converts to float safely (every `TUNING` bound is under 10**6),
and an int out of range gave `span` before too, so no reason text changes.

## 1.3 `console/server.py` (`Hub.reload_tuning`)

Replace `def reload_tuning(self) -> None:` whole (from its `def` line to the blank line before
`    def models_file(self) -> dict:`) with:

```python
    def reload_tuning(self) -> None:
        """Reread the Models page keys (tuning.KEYS) from config.json when its mtime changed, so a hand edit shows
        after Reload (plan 26 README 3.1); every other key keeps its value from the service start. Plan 27 (K2): a
        page key absent from the file goes back to its default; a value tuning.validate refuses is not taken (the
        live value stays) and console.log names it."""
        mtime = self._config_mtime()
        if mtime is None or mtime == self.config_mtime:
            return
        self.config_mtime = mtime
        path = self.folder / "config.json"
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(user, dict):
            return
        with self.lock:
            for key in tuning.KEYS:
                if key not in user:
                    self.cfg[key] = copy.deepcopy(paths.DEFAULTS.get(key))
            present = {key: user[key] for key in tuning.KEYS if key in user}
            clean, errors = tuning.validate(present, self.cfg) if present else ({}, {})
            for key in present:
                if key in errors:
                    self._log(f"config.json {key} refused: {errors[key]}")
                    continue
                default, value = paths.DEFAULTS.get(key), clean[key]
                self.cfg[key] = {**default, **value} if isinstance(default, dict) and isinstance(value, dict) \
                    else value
            self.version += 1
            self.changed.notify_all()
```

The keys absent from the file reset first, so `tuning.validate`'s cross check (yellow under red) and its model checks
see the config the file describes. `validate` returns the normalized value (a tier's bare rung string becomes
`{"rung", "effort": "auto"}`, an auto and auto kind pin is dropped); the reload stores that, merged one level into
the default for a dict key as before. A key the cross check refuses is in both `clean` and `errors`; `errors` wins.

Decision: a refused value leaves the live value as it was (the start value or the last good reload), not the
default, because "dropped" in the review means "not taken", and the page then shows what the service really uses.
A deleted key resets to `copy.deepcopy(paths.DEFAULTS[key])` as the review says. `_log` writes `console.log` only
(no lock), so it is safe under `self.lock`.

## 1.4 `console/server.py` (the config POST handlers)

In `Handler._harness`, insert after

```python
            message = str(exc)
            return self._error(400 if name == "claude" and not on else 500, message)
```

the lines:

```python
        except OSError as exc:  # plan 27 (K1): the write failed (os.replace on Windows while a reader holds the file)
            return self._error(500, f"cannot write config.json: {exc.strerror or exc}")
```

In `Handler._setting`, insert after

```python
            paths.set_setting(self.hub.folder, key, value)
        except ValueError as exc:
            return self._error(400, str(exc))
```

the lines:

```python
        except OSError as exc:  # plan 27 (K1)
            return self._error(500, f"cannot write config.json: {exc.strerror or exc}")
```

In `Handler._allow` (it serves `/api/allow` and `/api/open_folder`; `Hub.allow` calls `paths.add_project`), insert after

```python
            self.hub.allow(want)
        except ValueError as exc:
            return self._error(409, str(exc))
```

the same two lines (`except OSError as exc:  # plan 27 (K1)` and its `return`).

In `Handler._config_models` (the handler of `Hub.save_models`), insert after

```python
            errors = self.hub.save_models(body.get("changes"))
        except ValueError as exc:
            return self._error(409, str(exc))
```

the same two lines. `Hub.save_models`, `Hub.set_harness` and `Hub.allow` stay as they are: each writes the file
before it changes `self.cfg`, so a failed write leaves the live config untouched.

## 1.5 Tests

`tests/test_paths.py`: add `import threading` after `import tempfile`, and change the module docstring to
`"""Plan 24 config keys in paths.DEFAULTS and the opus_max_turns fallback; plan 27 the config.json writers."""`.
Insert at the end of class `PlanKeysTest` (after `test_design_max_turns_replaces_the_opus_cap`, replacing the three
blank lines before `class SettingTest` with one blank line, the test, and two blank lines):

```python
    def test_opus_max_turns_is_read_once_then_dropped(self):
        """Plan 27 (G8, plan 24 D2): the service start moves the old key into design_max_turns and drops it."""
        path = Path(self.tmp) / "config.json"
        path.write_text(json.dumps({"opus_max_turns": 15, "projects": ["C:/x"]}), encoding="utf-8")
        self.assertEqual(paths.ensure_config()["design_max_turns"], 15)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"projects": ["C:/x"], "design_max_turns": 15})
        self.assertEqual(paths.ensure_config()["design_max_turns"], 15)  # read from the new key from now on
        path.write_text(json.dumps({"opus_max_turns": 15, "design_max_turns": 40}), encoding="utf-8")
        self.assertEqual(paths.ensure_config()["design_max_turns"], 40)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"design_max_turns": 40})
```

Then insert, before `class SettingTest(unittest.TestCase):`:

```python
class ConfigWriteTest(unittest.TestCase):
    """Plan 27 (K1): every read-modify-write of config.json holds paths.CONFIG_LOCK and its own temp file."""

    def test_concurrent_writers_all_land(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"projects": []}), encoding="utf-8")
            errors = []

            def write(n):
                try:
                    for i in range(15):
                        paths.set_config(folder, {f"k{n}_{i}": i})
                        if n == 0:
                            paths.set_setting(Path(folder), "handoff_auto", bool(i % 2))
                        elif n == 1:
                            paths.set_harness(Path(folder), "codex", bool(i % 2))
                        elif n == 2:
                            paths.add_project(Path(folder), os.path.join(folder, f"p{i}"))
                except Exception as exc:  # a lost race shows as an error or a missing key
                    errors.append(f"{type(exc).__name__}: {exc}")

            threads = [threading.Thread(target=write, args=(n,)) for n in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = [f"k{n}_{i}" for n in range(6) for i in range(15) if f"k{n}_{i}" not in data]
            self.assertEqual(missing, [])
            self.assertEqual(len(data["projects"]), 15)
            self.assertIs(data["handoff_auto"], False)
            self.assertIs(data["harnesses"]["codex"]["on"], False)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["config.json"])  # no temp file left

    def test_a_failed_replace_keeps_the_file_and_leaves_no_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"projects": ["C:/x"]}), encoding="utf-8")
            with mock.patch("console.paths.os.replace", side_effect=PermissionError(13, "Access is denied")):
                with self.assertRaises(OSError):
                    paths.set_config(folder, {"task_max_steps": 8})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"projects": ["C:/x"]})
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["config.json"])
            paths.set_config(folder, {"task_max_steps": 8})  # the lock was released
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["task_max_steps"], 8)
```

`tests/test_tuning.py`: insert in class `NumbersTest`, before `def test_unknown_keys_and_empty_saves_are_refused`:

```python
    def test_a_huge_integer_is_refused_not_raised(self):
        """Plan 27 (B7): float(10**400) overflows; validate keeps its never-raises promise and gives the range."""
        clean, errors = check(task_max_steps=10 ** 400, budget_warn_at=-10 ** 400, daily_budget_usd=10 ** 400,
                              allowances={"opus": {"day_usd": 10 ** 400}})
        self.assertEqual(clean, {})
        self.assertEqual(errors, {"task_max_steps": "between 1 and 12", "budget_warn_at": "between 0.1 and 2",
                                  "daily_budget_usd": "between 0 and 1000",
                                  "allowances": "opus day_usd: between 0 and 100000"})
```

`tests/test_server.py`: insert in class `TaskServerTest`, before `def test_a_pinned_kind_routes_its_steps`:

```python
    def test_models_page_refuses_a_huge_integer(self):
        """Plan 27 (B7): a number too big for a float is a 400 with the range, not a dropped connection."""
        status, data = self.call("/api/config/models", {"changes": {"task_max_steps": 10 ** 400}})
        self.assertEqual((status, data["errors"]), (400, {"task_max_steps": "between 1 and 12"}))

    def test_models_page_reload_resets_a_deleted_key_and_drops_a_refused_value(self):
        """Plan 27 (K2): a page key removed from config.json by hand goes back to its default on Reload; a value
        tuning.validate refuses is not taken (the live value stays) and console.log says so."""
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / "config.json"
        path.write_text(json.dumps({"projects": [str(self.project)], "brief_max_words": 450, "task_max_steps": 8,
                                    "kinds": {"code": {"rung": "haiku", "effort": "low"}}}), encoding="utf-8")
        os.utime(path, (time.time() + 5, time.time() + 5))
        self.call("/api/config")
        self.assertEqual((self.hub.cfg["brief_max_words"], self.hub.cfg["task_max_steps"]), (450, 8))
        path.write_text(json.dumps({"projects": [str(self.project)], "task_max_steps": 99, "plan_hold": "yes"}),
                        encoding="utf-8")
        os.utime(path, (time.time() + 10, time.time() + 10))
        cfg = self.call("/api/config")[1]
        self.assertEqual(self.hub.cfg["brief_max_words"], paths.DEFAULTS["brief_max_words"])  # deleted: the default
        self.assertEqual((cfg["kind_pins"], self.hub.cfg["kinds"]), ({}, {}))
        self.assertEqual((self.hub.cfg["task_max_steps"], self.hub.cfg["plan_hold"]), (8, False))  # refused: kept
        log = (self.folder / "console.log").read_text(encoding="utf-8")
        self.assertIn("config.json task_max_steps refused: between 1 and 12", log)
        self.assertIn("config.json plan_hold refused: true or false", log)

    def test_a_config_write_that_fails_is_a_500(self):
        """Plan 27 (K1): os.replace can raise PermissionError on Windows (a reader holds the file); every config POST
        answers 500 with the reason and the live config keeps its value."""
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "config.json").write_text(json.dumps({"projects": [str(self.project)]}), encoding="utf-8")
        fresh = Path(self.tmp.name) / "fresh"
        fresh.mkdir()
        before = (self.hub.cfg["task_max_steps"], self.hub.cfg["handoff_auto"], self.hub.cfg["harnesses"]["codex"]["on"],
                  list(self.hub.cfg["projects"]))
        with mock.patch("console.paths.os.replace", side_effect=PermissionError(13, "Access is denied")):
            for route, body in (("/api/config/models", {"changes": {"task_max_steps": 7}}),
                                ("/api/setting", {"key": "handoff_auto", "value": True}),
                                ("/api/harness", {"name": "codex", "on": not before[2]}),
                                ("/api/open_folder", {"project_dir": str(fresh)})):
                self.assertEqual(self.call(route, body), (500, {"error": "cannot write config.json: Access is denied"}),
                                 route)
        self.assertEqual((self.hub.cfg["task_max_steps"], self.hub.cfg["handoff_auto"],
                          self.hub.cfg["harnesses"]["codex"]["on"], list(self.hub.cfg["projects"])), before)
        self.assertEqual(json.loads((self.folder / "config.json").read_text(encoding="utf-8")),
                         {"projects": [str(self.project)]})
```

(`HarnessServerTest` inherits `TaskServerTest` but disables the inherited tests, so these run once.)

What each asserts: `test_opus_max_turns_is_read_once_then_dropped` the start moves 15 into `design_max_turns`, drops
the old key and keeps the rest, and an explicit `design_max_turns` wins; `test_concurrent_writers_all_land` six threads
on all four writers lose no key and leave no temp file; `test_a_failed_replace_keeps_the_file_and_leaves_no_temp` an
`os.replace` failure raises `OSError`, keeps the file and the lock usable; `test_a_huge_integer_is_refused_not_raised`
10**400 on a whole, a share, a usd key and an allowance gives the range; `test_models_page_refuses_a_huge_integer` the
POST answers 400; `test_models_page_reload_resets_a_deleted_key_and_drops_a_refused_value` a deleted
`brief_max_words` and `kinds` go back to the default, a refused `task_max_steps` 99 and `plan_hold` "yes" keep the live
value and are logged; `test_a_config_write_that_fails_is_a_500` the four config POST routes answer 500 with
`cannot write config.json: Access is denied` and change neither `hub.cfg` nor the file.

## 1.6 Steps

1. Add the tests of 1.5. Run `py -m unittest tests.test_paths tests.test_tuning`: 4 of the new tests fail, as seen in
   the scratch copy:
   - `test_concurrent_writers_all_land`: `AssertionError: Lists differ: ["FileNotFoundError: [Errno 2] No such file or
     directory: '...config.json.tmp' -> '...config.json'", ...] != []`
   - `test_a_failed_replace_keeps_the_file_and_leaves_no_temp`: `Lists differ: ['config.json.tmp', 'config.json'] != ['config.json']`
   - `test_opus_max_turns_is_read_once_then_dropped`: `{'opus_max_turns': 15, 'projects': ['C:/x']} != {'projects': ['C:/x'], 'design_max_turns': 15}`
   - `test_a_huge_integer_is_refused_not_raised`: `OverflowError: int too large to convert to float`
2. Run the three server tests
   (`py -m unittest tests.test_server.TaskServerTest.test_models_page_refuses_a_huge_integer
   tests.test_server.TaskServerTest.test_models_page_reload_resets_a_deleted_key_and_drops_a_refused_value
   tests.test_server.TaskServerTest.test_a_config_write_that_fails_is_a_500`): the huge int and the 500 tests error with
   `http.client.RemoteDisconnected: Remote end closed connection without response` (the service log shows
   `OverflowError` and `PermissionError: [Errno 13] Access is denied`); the reload test fails `AssertionError: 450 != 500`.
3. Apply 1.1 and 1.2; `tests.test_paths` and `tests.test_tuning` are green (6 and 14 OK).
4. Apply 1.3 and 1.4; the three server tests are green.
5. Run the whole suite `py -m unittest discover -s tests`: seven tests more than before, nothing new failing (on Linux
   only the 4 baseline failures).
6. Commit: `plan 27 task 1: config.json writes under one lock, OSError is a 500, reload resets and checks, huge int refused, opus_max_turns dropped (K1 K2 B7 G8)`.

## 1.7 Drift guards

- Every read-modify-write of config.json goes through `paths._rewrite_config` (one `CONFIG_LOCK`); no writer opens
  `config.json.tmp` or calls `os.replace` on config.json by itself. `ensure_config`'s first write of a missing file
  stays as is (nothing else can hold the file before the service starts).
- Lock order: `Hub.allow` takes `hub.lock` then `CONFIG_LOCK`; nothing takes `hub.lock` while holding `CONFIG_LOCK`
  (`_rewrite_config` calls only the writer's own `change`). Keep it that way.
- `_rewrite_config` never writes a file it could not parse as an object; the `ValueError` text stays
  `cannot read <path>: fix it by hand` (the window and two tests show it).
- A write that fails changes neither the file nor `hub.cfg`; the answer is a 500 with `cannot write config.json: <reason>`.
  Do not catch `OSError` in `do_POST` or in the `Hub` methods.
- `tuning.validate` stays pure and never raises; `_number`'s reason texts do not change.
- `reload_tuning` touches only `tuning.KEYS`; every other key keeps its start value (plan 26 README 3.1).
- `load_config` stays read only; its `opus_max_turns` fallback lines stay.
- `cc_events.py` is not touched; nothing here writes outside the data folder.
