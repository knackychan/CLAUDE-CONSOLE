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
  `subprocess.run(..., capture_output=True, timeout=20, creationflags=NO_WINDOW, env=claude_cli.child_env() | adapter.env(False))` (OpenCode's no-update variable rides on the probe too) and
  keep the first line of stdout (stderr when stdout is empty) clipped at 60; `self.found[name]`, `self.versions_h[name]`,
  and `self.runs.exes[name] = [exe]` (dropped when not found). Never raises: a failure is `found False`, version `""`,
  one line in the service log. Returns `self.harnesses()`. With `self.lock` held for the dict writes; the version
  bump and `changed.notify_all()` so the page redraws.
- models.json (README 3.2b): `Hub` rereads it when its mtime changed, at each `/api/config` and before each step
  starts; `/api/config` gains `models_file: {"path", "count", "error"}`; `POST /api/models/reload` forces it; `POST /api/models/open` opens
  that one fixed path with `os.startfile` (no path from the caller).
- `Hub.harnesses() -> dict`: `{name: {"on", "found", "version", "models": harness.models_of(cfg, name), "tiers": list(TIERS)}}`
  for every name in `harness.NAMES`; `claude` has `models {}` and `tiers` the full list.
- `Hub.set_harness(name, on) -> dict`: `name == "claude" and not on` -> `ValueError("Prep and the brief pass run on Claude")`;
  `paths.set_harness(self.folder, name, on)`; `self.cfg = paths.load_config()`-style reload of that key only
  (`self.cfg["harnesses"][name]["on"] = on`; the file is the truth, the dict follows); `self.probe([name])`.
- `Hub.rung_ok(rung, kind="") -> str`: `""` when `claude_cli.known_model(cfg, rung)` and (Claude rung, or
  `self.found[harness]`) and, for `opencode` / `cmd`, `kind` is `""` (a plain Run) or, never `verify` or `fix`, a kind the model's
  tier covers: an `opus` model any kind, a `haiku` model a kind whose `tasks.RULES[kind][0] in ("haiku", "sonnet")`
  (README decision 11, D-2); else the reason: `unknown model or effort`, `codex is off`, `codex: not found on PATH`,
  `opencode: deepseek-v4.1-flash is not a think model`, `cmd: not on verify or fix steps`.
- `Hub.levers(sid)`: for a session with `harness != "claude"`: `verify`, `handoff`, `escalate`, `terminal` carry
  `"claude only"`; `continue` is on when the adapter's `RESUME` and the run is not live (the cold-cache guard applies
  as today); `stop` as today; Brief a new task / Verify in a new task stay on (they start Claude sessions from facts).
- `Hub._route_for(task, s)`: a harness pick goes to `tasks.step_route` as its tier (`pick=claude_cli.tier_of(pick,
  cfg)`), so the rule, floor, hint, cap and budget rank it as they rank a Claude pick. Today `step_route` reads the
  pick through `model_alias`, which gives `""` for `codex:...` (the pick would be dropped without a note) and, before
  Task 1, `sonnet` for an OpenCode id containing it. `tasks.py` itself does not change.
- `Hub.start_step(task, n)`: the existing line `model = pick if pick and pick not in MODELS and tier_of(pick) ==
  tier else model_id(tier)` keeps its shape with `tier_of(pick, self.cfg)`, so a harness pick is used when the route
  kept its tier and the budget did not move it. Then:
  - `harness, model_id = split_rung(model)`; when the harness is not `claude` and `rung_ok(model, kind)` refuses it
    (turned off or not found since Prep, or a cheap rung on a non-read kind), the step runs on `self.model_id(tier)`
    with the note `harness: codex off -> sonnet` (README decision 12).
  - The run starts with `harness=harness`, `model=model_id`, `read_only = kind in READ_ONLY_KINDS` (kinds whose
    `tasks.RULES[kind][2]` is exactly `Read,Grep,Glob`: scout, explain; Bash or web tools make a kind not read only),
    `max_turns = READ_MAX_TURNS (15) if adapter.CAPS and kind in ("scout", "search") else` today's Opus rule
    (`read_max_turns` arrives with plan 23 and replaces the constant).
  - `tasks.start_step` stores the whole rung in `s["model"]`, the tier in `s["tier"]` (already), and `s["harness"]`.
    The route notes gain `harness: codex` when it is not Claude.
  - `budget` and `disallow` / `tools` reach only the Claude adapter (Task 4); nothing else in the call changes.
- `Hub.pull` / `_run` route: `rung_ok(model)` instead of `known_model` alone; a harness rung starts the run with
  `harness` and `model` split; Prep stays Claude.
- `Hub.final_message(sid)`: through the meta's adapter summary of the current turn: `(summary["final"],
  "error_step_timeout" if meta["timed_out"] else summary["subtype"])`. `_ended` passes that subtype to
  `tasks.cap_reason`, so without the meta flag a timeout would never reach the retry reason.
- `Hub.last_reply`: `self.runs.chat_of(sid)` for window runs (any harness).

## `Handler`

- `GET /api/config`: adds `"harnesses": self.hub.harnesses()`; `"claude"` stays and equals `harnesses["claude"]["found"]`.
- `POST /api/harness {"name", "on"}` (guard header as every POST): 400 on an unknown name or a non-bool `on`,
  400 with the message for Claude off, 500 `cannot read config.json: fix it by hand` on ValueError; returns `{"harnesses": ...}`.
- `POST /api/run`: `rung_ok` (400 unknown, 409 off or not found with the reason); `fable_ok` as today (a Fable
  rung is Claude's).
- `POST /api/task`: each step `model` through `rung_ok(model, step kind)` (400 with the step number and reason).
- `GET /api/chat`: `chat_of` for window runs.
- `POST /api/terminal`: 409 `claude only` from the RunError.

## Tests (`HarnessServerTest`, `make_server` with the fake claude and `exes={"codex": fake_codex}`, codex `on` in the test cfg with `models {"gpt-6.1-sol": "sonnet"}`)

- `test_config_lists_harnesses`: `/api/config` has `harnesses` with the four names; `codex.on True`, `codex.found True` after the probe (poll until the probe thread is done, 5 s cap), `codex.version` starts with `codex-cli`; `opencode.on False`.
- `test_harness_switch`: `POST /api/harness {"name": "opencode", "on": true}` writes config.json and returns `opencode.on True`, `found False` (no fake given); turning `claude` off is 400; an unknown name 400.
- `test_run_on_a_codex_rung`: `POST /api/run {"model": "codex:gpt-6.1-sol", ...}` starts a run whose `run_started` has `harness codex` and `model gpt-6.1-sol`; the snapshot row shows `harness codex`; `/api/levers` for it has `verify == "claude only"`, `terminal == "claude only"`, `continue == ""` once ended.
- `test_run_refuses_off_or_unknown_rung`: `cmd:deepseek-v4.1-flash` with cmd off -> 409 with `cmd is off`; `codex:nope` -> 400.
- `test_task_step_pick_on_codex`: `POST /api/task` with a scout step whose `model` is `codex:gpt-6.1-sol`: the step runs on codex (`run_started.harness`), `read_only` in the meta, the step dict has `harness == "codex"`, its notes contain `harness: codex`; a HANDOFF-OK echo from the fake completes the step and the chain goes on (the next step on Claude's fake).
- `test_chat_and_final_message_for_codex`: `/api/chat?session=` gives the fake's items; `Hub.final_message` returns the agent text and `success`.
- `test_cheap_rung_refused_on_a_design_step`: with `cmd` on and found (the fake) and `models {"deepseek-v4.1-flash": "haiku"}`: `POST /api/task` with a `design` step on `cmd:deepseek-v4.1-flash` is 400 `is not a think model`; a `scout` step and a `code` step on it are accepted; with `opencode` on and found and `models {"kimi-k3": "opus"}`, a `design` step on `opencode:kimi-k3` is accepted and a `verify` on it is 400 `not on verify or fix steps`.
- `test_step_pick_falls_back_when_harness_off`: a task whose scout step picked `codex:gpt-6.1-sol`, then `POST /api/harness` codex off before the step starts: the step runs on Claude's haiku rung, its tier stays the pick's (`sonnet` in the test cfg) and it runs on Claude's sonnet rung with the note `harness: codex off -> sonnet`.
- `test_step_timeout_reaches_the_retry_reason`: `step_timeout_s` 1, a scout step on codex with `SLOW` in its goal: the task's `why` names the step timeout.
- `test_probe_never_raises`: a harness `on` with an `exe` path that does not exist: `found False`, `version ""`, no exception, the service keeps serving.

## Steps

1. Write the ten tests; run: KeyError on `harnesses`, 404 on `/api/harness`.
2. `Hub` first (probe, harnesses, set_harness, rung_ok, levers, start_step, final_message), then the routes; run until green.
3. Whole suite: 366 + 10 = 376.
4. Commit: `feat: harness probe, switch route, rung picks, levers (plan 05 Task 5)`.

## Drift guards

- `Hub.levers` and `Hub.task_levers` stay the only gates: nothing in the new routes starts a run outside them.
- The probe runs a `--version` only; it never runs a prompt.
- `paths.set_harness` is the only write to config.json here, through the guarded POST.
- A rung of a harness that is off or not found is refused with its reason; nothing silently falls back to Claude for a run Fred pointed at another harness.
