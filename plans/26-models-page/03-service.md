# Task 3: The service: the config route, the Save, the pin

> Contract: [README.md](README.md) 3.2, 3.4, 3.6. Depends on Tasks 1 and 2. Run in a scratch copy on 2026-10-14
> (plan 18 applied, plan 5 not placed): `tests/test_server.py` 90 OK (plan 18's 87 + 3); the full suite 384 run, only
> the four failures of this box.
> Lands on: plan 18 Task 4 (`Hub._route_for`: one argument added; `/api/config`'s `tiers` and `kinds_tier`), plans 5
> Task 5, 23 and 24 Task 3 (keys they added to the `/api/config` dict: moved unchanged into `Handler._config`).
> Plan 25 Task 1 adds its two `/api/config` keys at the end of the dict `Handler._config` returns, after this task's
> `kind_rules` line.

**Files**
- Modify: `console/server.py` (the import line; new `Hub.save_models`; `Hub._route_for`; new `Handler._config`;
  `do_GET`'s `/api/config`; `do_POST`'s routes; new `Handler._config_models`)
- Modify: `tests/test_server.py` (three tests in `TaskServerTest`)

## 3.1 `Hub`

Add `tuning` to the `from . import (...)` list, in alphabetical order (after `transcript`).

Before `def rung_ok(self, rung, kind="")` (plan 5's):

```python
    def save_models(self, changes) -> dict:
        """POST /api/config/models (plan 26): check the changes (tuning.validate), write the ones kept to config.json
        with every other key as written, and put them in the live config, so the next step reads them (a running
        step keeps its rung). Returns the refusals {key: reason}, {} when saved. ValueError: config.json unreadable."""
        clean, errors = tuning.validate(changes, self.cfg)
        if errors:
            return errors
        paths.set_config(self.folder, clean)
        with self.lock:
            for key, value in clean.items():
                self.cfg[key] = {**self.cfg.get(key, {}), **value} if key == "tiers" else value
            self.version += 1
            self.changed.notify_all()
        return {}
```

`tiers` merges into the live config one level deep as `set_config` merges it into the file and `load_config` reads it;
every other key replaces the live value (`kinds` and `allowances` default to `{}`, so the saved dict is the whole
value).

In `Hub._route_for` (plan 18's), the last argument line gains the pin:

```python
            refuse=lambda rung: self.rung_ok(rung, s["kind"]), pin=(self.cfg.get("kinds") or {}).get(s["kind"]))
```

## 3.2 `Handler`: GET `/api/config` and POST `/api/config/models`

Move the dict `do_GET` answers on `/api/config` into a new method after `_error`, as it stands after plans 5, 23, 24
and 18 (every key they added stays, in place), and add three keys at its end:

```python
    def _config(self) -> dict:
        """GET /api/config, and the answer of a Models page Save (plan 26)."""
        cfg, window = self.hub.cfg, paths.load_window(self.hub.folder)
        return {"projects": project_list(cfg), "models": claude_cli.MODELS,
                ...  # every key of today's dict, plans 5, 23, 24 and 18 included, unchanged
                "kinds": tasks.PREP_KINDS, "edit_kinds": sorted(tasks.EDIT_KINDS),
                "tiers": self.hub.tier_view(),
                "kinds_tier": {k: tasks.kind_tier(k) for k in tasks.PREP_KINDS},
                "handoff_auto": bool(cfg["handoff_auto"]),  # plan 23 Task 5's key (plan 18 put its two keys before it)
                "kind_pins": cfg.get("kinds") or {}, "tuning": tuning.view(cfg),
                "kind_rules": {k: {"rank": r[0], "effort": r[1], "tools": r[2]} for k, r in tasks.RULES.items()}}
```

(The `...` line stands for the keys between `"models"` and `"kinds"` exactly as the file has them; in the scratch copy
they were `efforts`, `default_model`, `default_effort`, `claude`, `config_path`, `gauge`, `project`, `brief`,
`ladder`, `effort`; plan 5 adds its own keys there, and they stay. Plan 23 Task 5 added `handoff_auto` after
`edit_kinds` and plan 18 Task 4 put `tiers` and `kinds_tier` right after `edit_kinds`, before it: the skeleton above
shows those three in that order; keep exactly one copy of each.) The `kinds` key keeps
the list of Prep kinds: the window's step rows and plan 25 read it; config `kinds` goes out as `kind_pins`.

`do_GET`'s branch becomes:

```python
        if url.path == "/api/config":
            return self._json(self._config())
```

In `do_POST`'s `routes` dict, after `"/api/review": self._review` (plans 5, 23, 24 add routes there; keep theirs):

```python
                  "/api/config/models": self._config_models,
```

Before `def _draft(self, body)`:

```python
    def _config_models(self, body):
        """Plan 26: the Models and tuning page's Save. Only the whitelisted keys of tuning.KEYS, each checked; 400
        with every reason ({"error": all of them on one line, "errors": {key: reason}}), else the new config."""
        try:
            errors = self.hub.save_models(body.get("changes"))
        except ValueError as exc:
            return self._error(409, str(exc))
        if errors:
            text = "; ".join(f"{k}: {v}" if k else v for k, v in errors.items())
            return self._json({"error": text, "errors": errors}, 400)
        return self._json(self._config())
```

`do_POST` checks `guard.host_ok` and `guard.post_ok` before any route, and `_body` caps the size (`MAX_BODY`): the
route needs nothing more.

## 3.3 Tests (`tests/test_server.py`, `TaskServerTest`, before `test_a_rung_can_be_run_by_hand`)

```python
    def test_models_page_saves_to_config_json(self):
        """Plan 26: POST /api/config/models writes the checked keys, keeps every other key, and the hub uses them."""
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["kind_pins"], cfg["tuning"]["task_max_steps"]["value"]), ({}, 6))
        self.assertEqual(cfg["tuning"]["balance_margin"], {"value": 0.1, "default": 0.1, "min": 0, "max": 0.5,
                                                           "unit": "share", "group": "balancing"})
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "config.json").write_text(json.dumps({"projects": [str(self.project)], "port": 47770,
                                                             "tiers": {"write": ["sonnet"]}}), encoding="utf-8")
        status, data = self.call("/api/config/models", {"changes": {
            "task_max_steps": 8, "balance_margin": 0.15, "tiers": {"read": ["haiku", "claude-haiku-4-5"]},
            "kinds": {"test": {"rung": "auto", "effort": "medium"}}, "allowances": {"opus": {"day_usd": 12}}}})
        self.assertEqual(status, 200, data)
        self.assertEqual((data["tuning"]["task_max_steps"]["value"], data["kind_pins"]),
                         (8, {"test": {"rung": "auto", "effort": "medium"}}))
        written = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.assertEqual((written["projects"], written["port"], written["task_max_steps"]), ([str(self.project)], 47770, 8))
        self.assertEqual(written["tiers"], {"write": ["sonnet"], "read": [{"rung": "haiku", "effort": "auto"},
                                                                         {"rung": "claude-haiku-4-5", "effort": "auto"}]})
        self.assertEqual((self.hub.cfg["task_max_steps"], self.hub.cfg["balance_margin"]), (8, 0.15))
        self.assertEqual([r["rung"] for r in data["tiers"]["read"]], ["haiku", "claude-haiku-4-5"])
        self.assertEqual(len(self.hub.cfg["tiers"]["think"]), len(paths.DEFAULTS["tiers"]["think"]))  # untouched tier
        self.assertEqual(self.hub.cfg["allowances"], {"opus": {"day_usd": 12}})

    def test_models_page_refuses_with_reasons(self):
        before = self.hub.cfg["task_max_steps"]
        status, data = self.call("/api/config/models", {"changes": {"task_max_steps": 99, "port": 1}})
        self.assertEqual(status, 400)
        self.assertEqual(data["errors"], {"task_max_steps": "between 1 and 12", "port": "not a setting this page changes"})
        self.assertIn("task_max_steps: between 1 and 12", data["error"])
        self.assertEqual(self.hub.cfg["task_max_steps"], before)
        self.assertFalse((self.folder / "config.json").exists() and
                         "task_max_steps" in json.loads((self.folder / "config.json").read_text(encoding="utf-8")))
        self.assertEqual(self.call("/api/config/models", {"changes": []})[0], 400)
        self.assertEqual(self.call("/api/config/models", {"other": 1})[0], 400)
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "config.json").write_text("{ broken", encoding="utf-8")
        status, data = self.call("/api/config/models", {"changes": {"task_max_steps": 7}})
        self.assertEqual(status, 409)
        self.assertIn("fix it by hand", data["error"])
        self.assertEqual((self.folder / "config.json").read_text(encoding="utf-8"), "{ broken")  # never overwritten

    def test_a_pinned_kind_routes_its_steps(self):
        status, data = self.call("/api/config/models", {"changes": {"kinds": {"code": {"rung": "claude-haiku-4-5",
                                                                                         "effort": "low"}}}})
        self.assertEqual(status, 200, data)
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual((step["model"], step["tier"], step["effort"]), ("claude-haiku-4-5", "haiku", "low"))
        self.assertIn("pin code: claude-haiku-4-5", step["notes"])
        self.assertIn("pin effort: low", step["notes"])
```

## 3.4 Steps

1. The three tests; run `py -m unittest tests.test_server`: 404 on `/api/config/models`, KeyError `kind_pins`.
2. The `server.py` edits in the order 3.1, 3.2; run: every test OK.
3. The whole suite: the count + 3.
4. Commit: `plan 26 task 3: the Models page's config route and Save; pins reach the route (N tests OK)`.

## 3.5 Drift guards

- `Hub.save_models` is the only caller of `paths.set_config`; nothing else writes config.json for the page.
- A Save is all or nothing: one refused key and nothing is written.
- `GET /api/config` keeps every key it had; the window's existing readers are untouched.
