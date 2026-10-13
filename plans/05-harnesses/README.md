# Plan 5: Harness adapters. Guided implementation plan

> Design: [../../design/brainstorm/2026-10-13-orchestration.md](../../design/brainstorm/2026-10-13-orchestration.md)
> sections 3 and 3.1 (D-2, D-3, D-8; Fred, 2026-10-13). Master: [../../PLAN.md](../../PLAN.md). Rules:
> [../../CLAUDE.md](../../CLAUDE.md). Builds on [17-tasks](../17-tasks/README.md) (steps as runs, `step_route`,
> picks, the ladder) and [02-run](../02-run.md) (window runs, `RunManager`).

This folder is the plan. No code is written in it: each task names the files, the functions with their exact
signatures, the data shapes, the tests with what they assert, and the ordered steps. The code is written when a
task is executed, test first, and placed one task at a time (test + commit). Anything that could drift from the
design is pinned in section 3 (the contract) and in each task's "Drift guards".

**State: written 2026-10-13 (this chat), Tasks 1 to 7 to execute. Start state: 328 tests OK on `master`.**

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-harness-package.md](01-harness-package.md) | `console/harness/` (the adapter contract, the registry, the Claude adapter wrapping `claude_cli`), the `harnesses` config block and `paths.set_harness`, rung names `harness:model`, `tests/test_harness.py` | nothing |
| 2 | [02-codex.md](02-codex.md) | `console/harness/codex.py`, `tests/fake_codex.py` | 1 |
| 3 | [03-opencode-cmd.md](03-opencode-cmd.md) | `console/harness/opencode.py`, `console/harness/cmd.py`, `tests/fake_opencode.py`, `tests/fake_cmd.py` | 1 |
| 4 | [04-runs-state.md](04-runs-state.md) | `RunManager` runs any adapter (command, stdin, end of run, stop, chat, timeout), `run_started` carries `harness`, a session row from the run lines alone, the gauge from the adapter's usage | 1, 2 |
| 5 | [05-service.md](05-service.md) | The probe at start, `/api/config` `harnesses`, `POST /api/harness`, harness rungs as picks in `/api/run` and on task steps, levers off for what an adapter cannot do, `Hub.final_message` through the adapter | 4 |
| 6 | [06-window.md](06-window.md) | The Harnesses block in the settings popover, rung labels `codex · gpt-5.6-codex`, the harness chip on the session head and the task card, the off reasons | 5 |
| 7 | [07-live-check-close.md](07-live-check-close.md) | Fred's live check (one step per adapter), then PLAN.md, BRAINSTORM 4 and this folder's state | 6 |

Each task ends with its own commit. Other chats may edit `PLAN.md`, `web/app.js` and `web/style.css`: apply the
window task as anchored edits, never a whole-file copy, and stage only this plan's lines.

## 2. Decisions taken (Fred, 2026-10-13)

| # | Decision | Taken |
|---|---|---|
| 1 | Which harnesses | Claude Code (built), Codex CLI, OpenCode, Command Code; one adapter module each (D-2) |
| 2 | Tier of a harness | A rung is `harness:model` and maps to a Claude tier alias (`haiku`, `sonnet`, `opus`) in config.json, so every rule that ranks models keeps working. OpenCode and Command Code rungs may map to `haiku` only (their subscriptions allow little); Codex rungs to any tier (D-2) |
| 3 | Who routes to a non-Claude rung | In this plan only Fred: a pick on the Prep card's route or on a step row. Automatic balancing by usage fills is sub-plan 18 |
| 4 | Prep and the brief pass | Stay on Claude's Haiku (their schema output is checked there) |
| 5 | On / off | `config.json` `harnesses.<name>.on` and `.exe`; a switch in the window; rungs of a harness that is off or not found never route and are not offered (D-8) |
| 6 | Unknown facts | Cost, tokens and steps an adapter cannot report show as unknown, never as zero (D-3) |
| 7 | Caps | Codex and OpenCode have no turn or spend flag: `step_timeout_s` (default 1800) ends such a run and the chain treats it as a step that hit its cap; Command Code uses `--max-turns` (exit code 8 on the cap) |
| 8 | Stop | An adapter without an interrupt is stopped with `claude_cli.kill_tree` (the tree, so the model's child commands end too); the rule "Stop is the stream-json interrupt, never a kill of a run this service owns" holds for Claude runs, and this is the one documented exception for harnesses that have no interrupt |
| 9 | Self-updates | Command Code updated itself during a `--help` call: every `cmd` command gets `--no-auto-update`, and the probe records each harness's version at every service start |
| 10 | What a non-Claude session shows | Chat from the adapter's stream (final text, tool events where the adapter knows them), no Steps from hooks (the hooks are Claude Code's), gauge from the adapter's usage or none, levers Continue (where the adapter resumes) and Stop only; Verify, Handoff, Escalate and Open in terminal are off with the reason `claude only` |

## 3. The contract (what every task must keep)

### 3.1 Names

- A **harness name** is one of `claude`, `codex`, `opencode`, `cmd`. `harness.NAMES` is that tuple, in that order.
- A **rung** is `"<harness>:<model>"`; a rung with no colon is a Claude rung (`"sonnet"`, `"claude-opus-4-8"`), so
  every existing config value, task.json and test stays valid. `harness.split_rung(rung) -> (harness, model)`.
- A **tier** is a Claude alias from `claude_cli.MODELS` (`haiku`, `sonnet`, `opus`, `fable`). `claude_cli.tier_of`
  gives a non-Claude rung's tier from config (3.2); `claude_cli.known_model` accepts a rung whose harness is on and
  found and whose model is listed.

### 3.2 config.json

```json
"harnesses": {
  "claude":   {"on": true,  "exe": ""},
  "codex":    {"on": false, "exe": "", "models": {"gpt-5.6-codex": "sonnet", "gpt-5.6-mini": "haiku"}},
  "opencode": {"on": false, "exe": "", "models": {"deepseek/deepseek-v4-flash": "haiku"}},
  "cmd":      {"on": false, "exe": "", "models": {"deepseek-flash": "haiku"}}
},
"step_timeout_s": 1800
```

- `exe` empty: found on PATH (`shutil.which` over the adapter's `EXE_NAMES`); else the path as given.
- `models`: model id -> tier. The model ids above are placeholders Fred replaces with what `--list-models` (cmd),
  the Codex docs and his OpenCode providers give; the adapter never checks a model name up front (a wrong one fails
  on the first request, as Claude's does). `harness.tiers_of(cfg, name)` returns the tiers the adapter may hold:
  `("haiku",)` for `opencode` and `cmd`, every tier for `codex`; a `models` entry outside that is dropped at load
  with a line in `hook-errors.log`-style `console.log` (the service's own log), never raised.
- `claude.exe` (the old key) keeps working: `harnesses.claude.exe` empty falls back to it (`paths.load_config`
  copies it in). `paths.set_harness(folder, name, on) -> None` writes `on` for one harness into config.json as
  `add_project` does (every other key as written; `ValueError` when the file cannot be read).

### 3.3 The adapter contract (`console/harness/__init__.py`)

Every adapter is a module with these names. `harness.get(name) -> module` (`KeyError` for an unknown name),
`harness.REGISTRY = {name: module}`.

```text
NAME: str                      "codex"
EXE_NAMES: tuple               ("codex.exe", "codex.cmd", "codex")      what shutil.which tries, in order
TIERS: tuple                   ("haiku",) or claude_cli.MODELS            the tiers this harness may hold
CAPS: bool                     True when run_command can cap turns or spend (Claude, cmd); False -> step_timeout_s
INTERRUPT: bool                True when stop() interrupts over stdin (Claude); False -> kill_tree
RESUME: bool                   True when a session can be continued (all four)
HOOKS: bool                    True when the Claude Code hooks log this harness's events (Claude only)

find_exe(cfg: dict) -> str | None          the adapter's section of cfg["harnesses"] decides; the real exe, not a shim
version_command(exe: list) -> list         prints the version and exits; no model call, no network beyond auth
run_command(exe: list, model: str, effort: str, cwd: str, session_id: str, *, prompt: str, resume: bool = False,
            fork: str = "", read_only: bool = False, budget: float = 0.0, max_turns: int = 0,
            name: str = "") -> tuple[list, bytes | None]
    the argument list, and the bytes to write on stdin (None when the prompt rides in argv)
is_result(line: dict) -> bool              the stream line that ends a turn
summary(lines: list) -> dict               {"final": str, "subtype": str, "cost": float | None, "tokens": dict | None,
                                            "session_id": str, "denials": list, "exit_cap": bool}
                                           tokens: {"input", "output", "cache_read", "context"} or None
chat(lines: list, cwd: str) -> list        runs.chat items (role you / claude / tool / result / note) from the stream
stop(proc) -> str                          "interrupt" (wrote one on stdin) or "kill" (killed the tree)
terminal_command(exe: list, session_id: str, model: str, effort: str) -> list | None
```

`effort` is a Claude effort word (`low` .. `max`); an adapter maps it to its own scale and drops what it has no
flag for (OpenCode: `#variant` in the model string from `effort_variant`, 3.4). `read_only` replaces Claude's
`--tools` list for an adapter that has sandboxes or modes instead. `session_id` is the console's id for the run;
an adapter that cannot set its own id (Codex, OpenCode, cmd) returns the harness's id in `summary()["session_id"]`
and `runs` keeps both (3.5).

The Claude adapter (`console/harness/claude.py`) wraps `claude_cli` with no behaviour change: `run_command`
returns `(claude_cli.run_command(...), claude_cli.user_message(prompt + footer, blocks))`; `is_result` is
`line.get("type") == "result"`; `summary` reads the result line and the last assistant text as `Hub.final_message`
does today; `chat` is `runs.chat`'s body moved. `claude_cli.py` itself keeps every function (other modules import
it) and gains nothing but the rung helpers (`split_rung`, the config-aware `tier_of` and `known_model`).

### 3.4 Flags per adapter (checked on Fred's machine, 2026-10-13; the plan's facts)

| | Codex CLI 0.162.1 | OpenCode (version: Task 7 adds it) | Command Code 1.81.0 (`cmdc`; help says `cmd`) |
|---|---|---|---|
| Command | `codex exec -` (prompt on stdin), `-C <cwd>`, `--skip-git-repo-check`, `--json`, `-o <file>` (the last message), `-m <model>`, `-c model_reasoning_effort="<low|medium|high>"` (the `-c key=value` form is checked; the key name is from the Codex config docs, confirmed at the live check), `-s read-only` or `-s workspace-write`, `--add-dir` not used, `--ephemeral` not used (a step may resume) | `opencode run --standalone --format json --auto -m <provider/model#variant> <message...>` (no stdin flag, no `--dir`: cwd is the process cwd); `--title <name>`; `--session <id>` `--fork` for a resume or a copy | `cmdc -p "<query>" --output-format json --no-auto-update --skip-onboarding --no-skills -m <model> --effort <low|medium|high> --max-turns <n>`; `--permission-mode plan` (read only) or `accept-edits`; `-n <name>`; `--session <id>` `--fork-session` for a resume or a copy |
| Effort | `low`, `medium`, `high`; `xhigh` and `max` become `high` | `effort_variant` in config per model (`{"deepseek/deepseek-v4-flash": {"low": "", "high": "thinking"}}`); no entry: no `#variant` | `low`, `medium`, `high`; `xhigh` and `max` become `high` ("depends on the model": a model that refuses it fails on the first request) |
| Resume | `codex exec resume <SESSION_ID> -` | `--session <id>` | `--session <id>` or `-r <id>` |
| Fork | `codex exec fork <SESSION_ID> -` | `--session <id> --fork` | `-r <id> --fork-session` |
| Caps | none (`step_timeout_s`) | none (`step_timeout_s`) | `--max-turns`; exit code 8 = cap hit |
| Stop | kill the tree | kill the tree | kill the tree |
| Stream | JSONL: `thread.started` (thread id), `turn.started`, `item.completed` with `item.type == "agent_message"` (the final text), `turn.completed` with `usage` {input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}, `turn.failed`, `error` (shapes from the docs; recorded at the live check) | `--format json`: raw events, shape unknown until the live check; the adapter keeps every line and takes the last text of an assistant part as the final message | NDJSON events then one final result line (shape unknown until the live check) |

Where a shape is unknown the adapter's first version is defensive: `summary()["final"]` is the longest text field
of the last event that has one, `cost` and `tokens` are `None` (shown unknown), and Task 7 pins the real shape
from one recorded run in `tests/fixtures/<harness>-run.jsonl`.

### 3.5 Runs

- `RunManager.start(...)` gains `harness: str = "claude"`. The run meta gains `harness` and `harness_session`
  (the adapter's own id from `summary()`, `""` for Claude where it is the same id). The `run_started` line gains
  `harness`. A resume of a non-Claude run passes `harness_session` as the id to resume.
- The stream file `runs/<sid>.jsonl` holds the adapter's stdout lines as they are, after the `cc_prompt` line the
  service writes (unchanged). Non-JSON lines come back as `{"raw": text}` (unchanged).
- `_watch` ends the run when `is_result` matches a line or the process exits; with `CAPS` false and
  `step_timeout_s` passed, a run older than that is stopped with the adapter's `stop` and its `run_ended` carries
  `subtype: "error_step_timeout"`, which `tasks.cap_reason` turns into `it hit the step timeout (1800 s)`.
- `run_ended` gains `tokens` when the adapter reported them. `cost` is left out (not `0`) when unknown (D-3).
- `stop(sid)`: a live process goes through the adapter's `stop`; a run of an earlier service is killed as today.
- `chat(path, cwd)` dispatches on the meta's harness through the adapter's `chat`.

### 3.6 State

- `run_started` alone creates the session row (check: `State` already builds a session from any line with a
  `session_id`; Task 4's test pins it) with `harness`, `model` (the rung's model), `effort`, `window = True`,
  `source = window`. With no hook lines the row's state follows the run: `Running` while `run_live`, then `Idle` /
  `Done` from `run_ended` as an Interrupted or Failed run does today (`State` reads `run_ended` already).
- The row carries `harness` (`"claude"` for every session the hooks report). The gauge uses `tokens.context` from
  `run_ended` when a non-Claude run reports it, else the row has no gauge (`context_tokens` `None`).
- `Hub.levers(sid)` returns `claude only` for `verify`, `handoff`, `escalate`, `terminal` on a non-Claude session;
  `continue` is on when the adapter's `RESUME` is true and the run is not live; `stop` as today.

### 3.7 Window

- `/api/config` gains `harnesses: {name: {"on": bool, "found": bool, "version": str, "models": {model: tier},
  "tiers": [...]}}` and keeps `claude: bool` (now `harnesses.claude.found`).
- `POST /api/harness {"name", "on"}` flips one harness (`paths.set_harness`), re-probes it, and returns the new
  `harnesses` dict. `claude` cannot be turned off (400, `Prep and the brief pass run on Claude`).
- Rung selects (`modelOptions` in `web/app.js`) list, after Claude's ladder, each harness that is on and found as a
  group: `codex · gpt-5.6-codex`, value `codex:gpt-5.6-codex`. `modelText` shows a non-Claude rung as
  `codex · gpt-5.6-codex` (no version lookup).
- The settings popover (the project picker's popover, under the Runs allowed groups) gets a Harnesses block: one
  row per name with its state word (`on`, `off`, `not found`), the version, and a switch button (`Turn on` /
  `Turn off`), pending until the service answers, as Allow runs is.
- The session head and the task card show the harness before the model when it is not `claude`
  (`codex · gpt-5.6-codex · medium`). A session with no gauge shows `context unknown` in the brief line.

### 3.8 Drift guards for every task

- Commands are argument lists, never shell strings; never the npm `.cmd` shim when a real exe exists.
- Nothing is written outside `paths.home()`; the adapters write nothing at all (the service writes the stream).
- A harness that is off or not found never appears in a select, never routes, and `known_model` refuses its rungs.
- `claude_cli.MODELS` and `EFFORTS` are unchanged; a tier is always one of them.
- No emojis or em-dashes in any text the window shows or the plan writes.

## 4. Config keys added (`paths.DEFAULTS`)

| Key | Default | Used by |
|---|---|---|
| `harnesses` | the 3.2 block with every harness but `claude` off | `harness.find_exe`, the probe, `known_model`, the window |
| `step_timeout_s` | 1800 | `RunManager._watch` for adapters with `CAPS` false |
| `effort_variant` | `{}` | the OpenCode adapter (`{model: {effort: variant}}`) |
