# Task 1: the `console/harness/` package, the Claude adapter, the config block

> Contract: [README.md](README.md) sections 3.1 to 3.3 and 4. Depends on nothing. Pure modules: no threads, no
> HTTP, no process started except in `version_command` tests through the fake.

**Files**
- Create: `console/harness/__init__.py`, `console/harness/claude.py`
- Modify: `console/claude_cli.py` (`split_rung`, `model_alias` refuses prefixed rungs, `tier_of(model, cfg=None)`, `known_model(cfg, model)`)
- Modify: `CLAUDE.md` (the two Rules lines on window-run commands and Stop, step 0 below)
- Modify: `console/paths.py` (`DEFAULTS["harnesses"]`, `["step_timeout_s"]`, `["effort_variant"]`, `set_harness`, the `claude_exe` fallback in `load_config`)
- Create: `tests/test_harness.py`

**Imports allowed in `console/harness/__init__.py`**: `importlib`, `shutil`, `pathlib.Path`, and from the package
`claude_cli` (MODELS). Adapters import `json`, `shutil`, `subprocess` (for `kill_tree` through `claude_cli`),
`pathlib.Path`, and `claude_cli`, `redact`, `transcript` (for `note_write` / `flush_wrote` in `chat`). Nothing from
`server`, `runs`, `state`, `tasks`.

## `console/harness/__init__.py` (top to bottom)

```text
docstring: what an adapter is (README 3.3), the rung names, who calls what
NAMES = ("claude", "codex", "opencode", "cmd")
REGISTRY: dict, filled by _load() from the sibling modules (importlib.import_module(f".{name}", __package__))
get(name) -> module                         KeyError on an unknown name
split_rung(rung) -> (harness, model)        "codex:gpt-5.6-codex" -> ("codex", "gpt-5.6-codex"); "sonnet" -> ("claude", "sonnet")
rung(harness, model) -> str                 the inverse; a Claude rung has no prefix
section(cfg, name) -> dict                  cfg["harnesses"].get(name) or {"on": name == "claude", "exe": ""}
tiers_of(cfg, name) -> tuple                get(name).TIERS
models_of(cfg, name) -> dict                the section's "models" filtered to tiers_of (Claude: {} ; its rungs come from the ladder)
is_on(cfg, name) -> bool                    section(cfg, name).get("on") is True
find_exe(cfg, name) -> str | None           get(name).find_exe(cfg)
which(names, exe="") -> str | None          exe when given and it exists; else the first of names shutil.which finds
```

- `which` is the shared body of every adapter's `find_exe`: `exe` from the section wins when the file exists;
  else `shutil.which` over `EXE_NAMES`. The Claude adapter keeps `claude_cli.find_exe`'s shim rule (never the
  `.cmd` when `node_modules/.../claude.exe` exists) and reads `harnesses.claude.exe`, then the old `claude_exe`.
- `models_of` drops an entry whose tier is not in `TIERS` or not in `claude_cli.MODELS`; it never raises.

## `console/harness/claude.py`

```text
NAME = "claude"; EXE_NAMES = ("claude.exe", "claude.cmd", "claude"); TIERS = tuple(claude_cli.MODELS)
CAPS = INTERRUPT = RESUME = HOOKS = True
find_exe(cfg) -> str | None                 claude_cli.find_exe({"claude_exe": section exe or cfg.get("claude_exe", "")})
version_command(exe) -> list                exe + ["--version"]
run_command(exe, model, effort, cwd, session_id, *, prompt, resume=False, fork="", read_only=False, budget=0.0,
            max_turns=0, name="", tools=None, disallow=(), blocks=()) -> (list, bytes)
    (claude_cli.run_command(exe, model, effort, session_id, resume=resume, name=name, fork=fork,
                            disallow=disallow, tools=tools, budget=budget, max_turns=max_turns),
     claude_cli.user_message(prompt + footer, blocks))   footer = "" if prompt.startswith("/") else STOP_FOOTER
is_result(line) -> bool                     line.get("type") == "result"
summary(lines) -> dict                      final: the last top-level assistant text block (parent_tool_use_id absent),
                                            subtype, cost = total_cost_usd, tokens = None (the transcript prices Claude runs),
                                            session_id = result["session_id"], denials (as runs.result_record builds them),
                                            exit_cap = subtype in ("error_max_turns", "error_max_budget_usd")
chat(lines, cwd) -> list                    the body of runs.chat today, unchanged (runs.chat calls it in Task 4)
stop(proc) -> str                           writes claude_cli.interrupt_message(...) on proc.stdin; "interrupt"
terminal_command(exe, session_id, model, effort) -> list   claude_cli.terminal_command(...)
env(read_only) -> dict                      {}
```

The Claude adapter's `run_command` keeps the two extra keyword arguments `tools`, `disallow` and `blocks` (the
attachments) that only Claude has; `runs.start` passes them only to this adapter (Task 4). `cwd` is unused here
(the service sets the process cwd); it is in the signature so every adapter is called the same way.

## `console/claude_cli.py` changes

- `model_alias(model)`: `""` when `split_rung(model)[0] != "claude"` (a known harness name before the first colon),
  else as today. Without this, `opencode:openrouter/anthropic/claude-sonnet-4-6` reads as `sonnet` everywhere
  `model_alias` runs (`tasks.step_route`'s pick, `Hub.route_of`, the Fable checks).
- `split_rung(rung) -> (harness, model)`: as `harness.split_rung` (defined here, re-exported by `harness`, so
  `claude_cli` does not import the package: `harness` imports `claude_cli`).
- `tier_of(model, cfg=None) -> str`: a Claude rung as today (`model_alias`); a `harness:model` rung gives
  `cfg["harnesses"][harness]["models"][model]` when `cfg` is given and the entry exists and is a tier, else `""`.
- `known_model(cfg, model) -> bool`: as today for Claude rungs; a `harness:model` rung is known when the harness
  section is `on`, the model is in its `models`, and its tier is in that adapter's `TIERS` (through a late import of
  `harness` inside the function, to avoid the cycle). `found` is the service's business (Task 5 refuses a rung of
  a harness that is on but not found with `409 codex: not found on PATH`).

## `console/paths.py` changes

- `DEFAULTS["harnesses"]` = README 3.2 block (every harness but `claude` off; the placeholder model ids as written).
- `DEFAULTS["step_timeout_s"] = 1800`, `DEFAULTS["effort_variant"] = {}`.
- `load_config()`: after the merge, when `cfg["harnesses"]["claude"]["exe"]` is empty and `cfg["claude_exe"]` is
  not, copy it in (the old key keeps working). The one-level dict merge already keeps Fred's harness entries.
- `set_harness(folder, name, on) -> None`: like `add_project`: read config.json (ValueError when unreadable),
  `data.setdefault("harnesses", {}).setdefault(name, {"on": False, "exe": ""})["on"] = bool(on)`, write back with
  `indent=2`. `name` must be in `harness.NAMES` (ValueError otherwise; checked without importing `harness`: the
  tuple is duplicated as `paths.HARNESSES` and a test asserts the two are equal).

## Tests (`tests/test_harness.py`, class `HarnessTest`)

- `test_registry_has_the_four_names`: `harness.NAMES == ("claude", "codex", "opencode", "cmd")`; `get("claude").NAME == "claude"`; `get("x")` raises KeyError. (Tasks 2 and 3 add their modules; until then `REGISTRY` holds `claude` only and `get("codex")` raises: the test checks `set(REGISTRY) <= set(NAMES)`.)
- `test_rung_names`: `split_rung("codex:gpt-5.6-codex") == ("codex", "gpt-5.6-codex")`, `split_rung("sonnet") == ("claude", "sonnet")`, `rung("claude", "sonnet") == "sonnet"`, `rung("cmd", "deepseek-flash") == "cmd:deepseek-flash"`.
- `test_tier_of_a_rung_from_config`: with a cfg where `codex.models == {"gpt-5.6-codex": "sonnet"}`: `claude_cli.tier_of("codex:gpt-5.6-codex", cfg) == "sonnet"`, `tier_of("codex:nope", cfg) == ""`, `tier_of("claude-opus-4-8") == "opus"` (no cfg).
- `test_known_model_needs_on_and_listed`: `known_model(cfg_off, "codex:gpt-5.6-codex")` is False; with `on: True` it is True; a `cmd` model mapped to `sonnet` is not known (TIERS is `("haiku",)` for cmd: this needs Task 3's module, so the test uses a stub module registered in `REGISTRY` with `TIERS = ("haiku",)`); Claude rungs as before (`"sonnet"`, a ladder rung).
- `test_models_of_filters_by_tier`: `models_of(cfg, "cmd")` drops a `sonnet` entry and keeps a `haiku` one (same stub).
- `test_which_prefers_the_given_exe`: a temp file path as `exe` is returned as is; a missing path falls to `shutil.which` (patched to return a fixed string); nothing found gives `None`.
- `test_claude_adapter_wraps_claude_cli`: `run_command([fake], "sonnet", "medium", cwd, sid, prompt="hi")` returns the same list as `claude_cli.run_command([fake], "sonnet", "medium", sid)` and stdin bytes equal to `claude_cli.user_message("hi" + STOP_FOOTER)`; a `/skill` prompt gets no footer; `is_result({"type": "result"})`; `summary` on three recorded lines (init, assistant with text, result) gives `final`, `cost`, `session_id`, `exit_cap False`; `exit_cap True` for `error_max_turns`.
- `test_model_alias_ignores_harness_rungs`: `model_alias("opencode:openrouter/anthropic/claude-sonnet-4-6") == ""`, `model_alias("codex:gpt-5.6-codex") == ""`, `model_alias("claude-sonnet-4-6") == "sonnet"` (unchanged), and a Claude id with a colon in it, if any, is not split (`split_rung` splits only on a name in `NAMES`).
- `test_set_harness_writes_one_key`: on a temp folder with a config.json holding `{"projects": ["x"]}`, `set_harness(folder, "codex", True)` leaves `projects` and gives `harnesses.codex.on == True`; an unknown name raises ValueError; an unreadable file raises ValueError.
- `test_defaults_and_claude_exe_fallback`: `DEFAULTS["harnesses"]["claude"]["on"] is True`, the other three `False`; `load_config` with `claude_exe` set and the harness exe empty copies it; `paths.HARNESSES == harness.NAMES`.

## Steps

0. Edit `CLAUDE.md` Rules first, so no later task breaks a written rule: "Window runs: commands come only from
   console/claude_cli.py" becomes "Window runs: commands come only from the adapters in console/harness/
   (claude_cli.py for Claude Code)"; the Stop clause gains "; a harness with no interrupt (Codex, OpenCode,
   Command Code) is stopped by killing its process tree (plan 05 decision 8)". Fred confirmed decision 8 on
   2026-10-13.
1. Write `tests/test_harness.py` with the ten tests; run: ImportError.
2. Create the package and the Claude adapter; add the `claude_cli` helpers and the `paths` changes; run until green.
3. Run the whole suite: 328 + 10 = 338 (every earlier test unchanged; `test_claude_cli.test_tier_of_and_known_model` still passes with the new signature, `cfg=None` default).
4. Commit: `feat: harness package and Claude adapter, harnesses config (plan 05 Task 1)`.

## Drift guards

- `claude_cli.py` loses nothing and changes no existing call; `runs.py` is untouched in this task.
- The package imports `claude_cli`, never the reverse at module level.
- `DEFAULTS` grows by exactly three keys.
