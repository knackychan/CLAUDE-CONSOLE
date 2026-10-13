# Task 5: the service: probe, settings routes, picks of harness rungs, levers

> Contract: [README.md](README.md) 3.6, 3.7. Depends on Task 4.

**Files**
- Modify: `console/server.py` (`make_server`, `Hub.__init__`, `Hub.probe`, `Hub.harnesses`, `Hub.levers`, `Hub.start_step`, `Hub.final_message`, `Handler` routes `/api/config`, `/api/harness`, `/api/run`, `/api/task`, `/api/chat`, `/api/terminal`)
- Modify: `console/__main__.py` (nothing but the log line listing the harnesses found)
- Modify: `tests/test_server.py` (class `HarnessServerTest`)

## `Hub`

- `make_server(cfg, port, folder, exe=None, exes=None)`: `exes` as `RunManager`'s; default `{}`; the tests pass the fakes.
- `Hub.__init__`: `self.exes = dict(exes or {})`, `self.versions_h = {}` (harness -> version string),
  `self.found = {}` (harness -> bool); `self.probe()` runs in a daemon thread at start (`threading.Thread(target=self.probe, name="probe")`), and again from `set_harness`.
- `Hub.probe(names=None) -> dict`: for each harness that is `on` (`harness.is_on`): `exe = harness.find_exe(cfg, name)`
  (for `claude`: `self.runs.exe` already found by `make_server`); when found, run `adapter.version_command([exe])` with
  `subprocess.run(..., capture_output=True, timeout=20, creationflags=NO_WINDOW, env=claude_cli.child_env())` and
  keep the first line of stdout (stderr when stdout is empty) clipped at 60; `self.found[name]`, `self.versions_h[name]`,
  and `self.runs.exes[name] = [exe]` (dropped when not found). Never raises: a failure is `found False`, version `""`,
  one line in the service log. Returns `self.harnesses()`. With `self.lock` held for the dict writes; the version
  bump and `changed.notify_all()` so the page redraws.
- `Hub.harnesses() -> dict`: `{name: {"on", "found", "version", "models": harness.models_of(cfg, name), "tiers": list(TIERS)}}`
  for every name in `harness.NAMES`; `claude` has `models {}` and `tiers` the full list.
- `Hub.set_harness(name, on) -> dict`: `name == "claude" and not on` -> `ValueError("Prep and the brief pass run on Claude")`;
  `paths.set_harness(self.folder, name, on)`; `self.cfg = paths.load_config()`-style reload of that key only
  (`self.cfg["harnesses"][name]["on"] = on`; the file is the truth, the dict follows); `self.probe([name])`.
- `Hub.rung_ok(rung) -> str`: `""` when `claude_cli.known_model(cfg, rung)` and (Claude rung, or `self.found[harness]`);
  else the reason: `unknown model or effort`, `codex is off`, `codex: not found on PATH`.
- `Hub.levers(sid)`: for a session with `harness != "claude"`: `verify`, `handoff`, `escalate`, `terminal` carry
  `"claude only"`; `continue` is on when the adapter's `RESUME` and the run is not live (the cold-cache guard applies
  as today); `stop` as today; Brief a new task / Verify in a new task stay on (they start Claude sessions from facts).
- `Hub.start_step(task, n)`: a step whose `pick` is a harness rung: `harness, model = split_rung(pick)`; the run
  starts with `harness=harness`, `model=model`, `read_only = kind in read kinds` (`tasks.RULES[kind][2]` names
  Read / Grep / Glob only), `max_turns = cfg["read_max_turns"] if the adapter has CAPS and the kind is read-only else 0`
  (`read_max_turns` arrives with plan 23; until then 15 as a module constant, named in the step notes). Without a
  pick nothing changes (Claude's rung of the tier). `s["harness"]` is kept on the step dict (the Task page shows it).
  The route notes gain `harness: codex` when a pick names one.
- `Hub.pull` / `_run` route: `rung_ok(model)` instead of `known_model` alone; a harness rung starts the run with
  `harness` and `model` split; Prep stays Claude.
- `Hub.final_message(sid)`: through `self.runs.chat_of(sid)`'s adapter summary: `(summary["final"], summary["subtype"])`.
- `Hub.last_reply`: `self.runs.chat_of(sid)` for window runs (any harness).

## `Handler`

- `GET /api/config`: adds `"harnesses": self.hub.harnesses()`; `"claude"` stays and equals `harnesses["claude"]["found"]`.
- `POST /api/harness {"name", "on"}` (guard header as every POST): 400 on an unknown name or a non-bool `on`,
  400 with the message for Claude off, 500 `cannot read config.json: fix it by hand` on ValueError; returns `{"harnesses": ...}`.
- `POST /api/run`: `rung_ok` (400 unknown, 409 off or not found with the reason); `fable_ok` as today (a Fable
  rung is Claude's).
- `POST /api/task`: each step `model` through `rung_ok` (400 with the step number and reason).
- `GET /api/chat`: `chat_of` for window runs.
- `POST /api/terminal`: 409 `claude only` from the RunError.

## Tests (`HarnessServerTest`, `make_server` with the fake claude and `exes={"codex": fake_codex}`, codex `on` in the test cfg with `models {"gpt-5.6-codex": "sonnet"}`)

- `test_config_lists_harnesses`: `/api/config` has `harnesses` with the four names; `codex.on True`, `codex.found True` after the probe (poll until the probe thread is done, 5 s cap), `codex.version` starts with `codex-cli`; `opencode.on False`.
- `test_harness_switch`: `POST /api/harness {"name": "opencode", "on": true}` writes config.json and returns `opencode.on True`, `found False` (no fake given); turning `claude` off is 400; an unknown name 400.
- `test_run_on_a_codex_rung`: `POST /api/run {"model": "codex:gpt-5.6-codex", ...}` starts a run whose `run_started` has `harness codex` and `model gpt-5.6-codex`; the snapshot row shows `harness codex`; `/api/levers` for it has `verify == "claude only"`, `terminal == "claude only"`, `continue == ""` once ended.
- `test_run_refuses_off_or_unknown_rung`: `cmd:deepseek-flash` with cmd off -> 409 with `cmd is off`; `codex:nope` -> 400.
- `test_task_step_pick_on_codex`: `POST /api/task` with a scout step whose `model` is `codex:gpt-5.6-codex`: the step runs on codex (`run_started.harness`), `read_only` in the meta, the step dict has `harness == "codex"`, its notes contain `harness: codex`; a HANDOFF-OK echo from the fake completes the step and the chain goes on (the next step on Claude's fake).
- `test_chat_and_final_message_for_codex`: `/api/chat?session=` gives the fake's items; `Hub.final_message` returns the agent text and `success`.
- `test_probe_never_raises`: a harness `on` with an `exe` path that does not exist: `found False`, `version ""`, no exception, the service keeps serving.

## Steps

1. Write the seven tests; run: KeyError on `harnesses`, 404 on `/api/harness`.
2. `Hub` first (probe, harnesses, set_harness, rung_ok, levers, start_step, final_message), then the routes; run until green.
3. Whole suite: 365 + 7 = 372.
4. Commit: `feat: harness probe, switch route, rung picks, levers (plan 05 Task 5)`.

## Drift guards

- `Hub.levers` and `Hub.task_levers` stay the only gates: nothing in the new routes starts a run outside them.
- The probe runs a `--version` only; it never runs a prompt.
- `paths.set_harness` is the only write to config.json here, through the guarded POST.
- A rung of a harness that is off or not found is refused with its reason; nothing silently falls back to Claude for a run Fred pointed at another harness.
