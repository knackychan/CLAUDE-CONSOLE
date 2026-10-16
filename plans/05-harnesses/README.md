# Plan 5: Harness adapters. Guided implementation plan

> Design: [../../design/brainstorm/2026-10-13-orchestration.md](../../design/brainstorm/2026-10-13-orchestration.md)
> sections 3 and 3.1 (D-2, D-3, D-8; Fred, 2026-10-13). Master: [../../PLAN.md](../../PLAN.md). Rules:
> [../../CLAUDE.md](../../CLAUDE.md). Builds on [17-tasks](../17-tasks/README.md) (steps as runs, `step_route`,
> picks, the ladder) and [02-run](../02-run.md) (window runs, `RunManager`).

This folder is the plan. No code is written in it: each task names the files, the functions with their exact
signatures, the data shapes, the tests with what they assert, and the ordered steps. The code is written when a
task is executed, test first, and placed one task at a time (test + commit). Anything that could drift from the
design is pinned in section 3 (the contract) and in each task's "Drift guards".

**Placed 2026-10-14** on branch `claude/implement-orchestration-plans-1y4bic` (PR #1): every code task, tests first where the task says, one commit per task; open decisions as (a). Fred's live check and the close task are open.

**State: written 2026-10-13, reviewed the same day against the code, D-1 to D-8 and Fred's pasted `--help`
outputs (section 6 lists what the review changed). Tasks 1 to 7 to execute. Start state: 328 tests OK on `master`
(Windows; Linux discovers 326).**

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-harness-package.md](01-harness-package.md) | `console/harness/` (the adapter contract, the registry, the Claude adapter wrapping `claude_cli`), the `harnesses` config block and `paths.set_harness`, rung names `harness:model`, `tests/test_harness.py` | nothing |
| 2 | [02-codex.md](02-codex.md) | `console/harness/codex.py`, `tests/fake_codex.py` | 1 |
| 3 | [03-opencode-cmd.md](03-opencode-cmd.md) | `console/harness/opencode.py`, `console/harness/cmd.py`, `tests/fake_opencode.py`, `tests/fake_cmd.py` | 1 |
| 4 | [04-runs-state.md](04-runs-state.md) | `RunManager` runs any adapter (command, stdin, end of run, stop, chat, timeout), `run_started` carries `harness`, a session row from the run lines alone, the gauge from the adapter's usage | 1, 2 |
| 5 | [05-service.md](05-service.md) | The probe at start, `/api/config` `harnesses`, `POST /api/harness`, harness rungs as picks in `/api/run` and on task steps, levers off for what an adapter cannot do, `Hub.final_message` through the adapter | 4 |
| 6 | [06-window.md](06-window.md) | The Harnesses block in the settings popover, rung labels `codex · gpt-6.1-sol`, the harness chip on the session head and the task card, the off reasons | 5 |
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
| 8 | Stop (Fred confirmed after the review, 2026-10-13) | An adapter without an interrupt is stopped with `claude_cli.kill_tree` (the tree, so the model's child commands end too); the rule "Stop is the stream-json interrupt, never a kill of a run this service owns" holds for Claude runs, and this is the one documented exception for harnesses that have no interrupt |
| 9 | Self-updates | Command Code updated itself during a `--help` call: every `cmd` command gets `--no-auto-update`, and the probe records each harness's version at every service start |
| 10 | What a non-Claude session shows | Chat from the adapter's stream (final text, tool events where the adapter knows them), no Steps from hooks (the hooks are Claude Code's), gauge from the adapter's usage or none, levers Continue (where the adapter resumes) and Stop only; Verify, Handoff, Escalate and Open in terminal are off with the reason `claude only` **(replaced by plan 37, 2026-10-15: the same hook runs in every CLI, so an outside chat gets Steps, gauge, usage and every lever - Verify, Handoff, Escalate and Open in terminal run as forks of the chat; only De-escalate stays window-only)** |
| 11 | What OpenCode and Command Code may run (D-2) | Command Code lists cheap models only (tier `haiku`). OpenCode lists cheap models (tier `haiku`) and two think models, `opencode-go/kimi-k3` and `opencode-go/glm-5.3` (tier `opus`; Fred, 2026-10-14). A rung of either is offered and accepted by its model's tier: a `haiku` model on kinds whose rule tier is `haiku` or `sonnet` (scout, search, draft, proofread, edit, test, code, document, explain, debug; Fred, 2026-10-14: well-designed code can be written by a cheap model), an `opus` model on any kind, and any of them on a plain Run; never on `verify` or `fix`. Verify stays one tier above the rung, so a cheap rung's code is checked by a `sonnet` rung. A refused pick says `opencode: deepseek-v4.1-flash is not a think model` or `cmd: not on verify or fix steps` |
| 12 | A pick whose harness went off | A task step whose pick names a harness that is off or not found when the step starts is balanced inside the pick's rank, with the route note `pick refused: <harness> is off -> balance` (plan 18 decision 10; Fred, Q1 (a) of plan 27, 2026-10-14). A plain Run Fred points at such a rung is refused (409), never moved |
| 13 | Which harness a later turn uses | The run meta's `harness`, always: Continue, a STOP answer, a retry and Stop read it from the meta; only a new run takes `harness` from its caller |
| 14 | Where the model lists live (Fred, 2026-10-14) | In their own file, `~/.claude/console/models.json` (3.2b), one list per CLI including Claude's, edited by hand and reread when it changes: adding or dropping a model never needs a rebuild or a restart |

## 3. The contract (what every task must keep)

2026-10-16 Windows Codex repair: exclude PATH entries containing Store `pwsh.exe` during CLI startup so
shell discovery selects unpackaged PowerShell; restore the original PATH for model commands through
`shell_environment_policy.set.PATH`. Keep the existing sandbox mode. A command startup failure that has
no later successful shell command in the turn yields `error_shell_start`, using the task's existing retry
then stuck behavior instead of advancing. Regression coverage: `test_harness.py`, `test_tasks.py`.

### 3.1 Names

- A **harness name** is one of `claude`, `codex`, `opencode`, `cmd`. `harness.NAMES` is that tuple, in that order.
- A **rung** is `"<harness>:<model>"`; a rung with no colon is a Claude rung (`"sonnet"`, `"claude-opus-4-8"`), so
  every existing config value, task.json and test stays valid. `harness.split_rung(rung) -> (harness, model)`.
- A **tier** is a Claude alias from `claude_cli.MODELS` (`haiku`, `sonnet`, `opus`, `fable`). `claude_cli.tier_of`
  gives a non-Claude rung's tier from config (3.2); `claude_cli.known_model` accepts a rung whose harness is on and
  found and whose model is listed.
- `claude_cli.model_alias` (and `alias()` in `web/app.js`) returns `""` for any string with a harness prefix: an
  OpenCode id such as `opencode:openrouter/anthropic/claude-sonnet-4-6` contains `sonnet`, and today's substring
  match would read it as a Claude pick in `tasks.step_route`, the Fable checks and the composer. Every caller that
  ranks a rung goes through `tier_of(rung, cfg)`.
- A task step stores the whole rung in `s["model"]` (`codex:gpt-6.1-sol`), its tier in `s["tier"]` (as
  `Hub.start_step` already does) and `s["harness"]`; `tasks.checked_route` reads `tier`, so Verify and Fix rank a
  harness step by its tier with no change there.

### 3.2 config.json

```json
"harnesses": {
  "claude":   {"on": true,  "exe": ""},
  "codex":    {"on": false, "exe": ""},
  "opencode": {"on": false, "exe": ""},
  "cmd":      {"on": false, "exe": ""}
},
"step_timeout_s": 1800
```

- `exe` empty: found on PATH (`shutil.which` over the adapter's `EXE_NAMES`); else the path as given.
- The models of each harness are not in config.json: they live in models.json (3.2b, decision 14). A
  `harnesses.<name>.models` left in config.json by an earlier build is still read for a harness models.json does
  not list.
- Model ids. The ids in 3.2b were checked against the providers' docs on 2026-10-14 (table below);
  Fred trims them to what his plans hold (`cmd --list-models`, `opencode models`, Codex `/model`); the adapter never checks a model name up front (a wrong one fails
  on the first request, as Claude's does). `harness.tiers_of(cfg, name)` returns the tiers the adapter may hold:
  `("haiku", "opus")` for `opencode`, `("haiku",)` for `cmd`, every tier for `codex` (decision 11); a `models` entry outside that is dropped at load
  with a line in `hook-errors.log`-style `console.log` (the service's own log), never raised.
- Models per harness, checked 2026-10-14. Codex: `gpt-6-astra` (most capable, think), `gpt-6.1-sol` (recommended
  for coding, write), `gpt-6-sol` (write), `gpt-6-luna` (focused, repeatable work, read; cheapest); `gpt-5.5`
  retires from Codex on 2026-10-14 and `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex` are gone, so none is listed
  ([Codex models](https://learn.chatgpt.com/docs/models)). OpenCode, through OpenCode Go (`opencode-go/` prefix,
  per-model monthly limits): `deepseek-v4.1-flash` (largest allowance), `glm-5.3-flash`, `qwen3.8-flash`,
  `gpt-6-luna`, and for design `kimi-k3` and `glm-5.3` (tier `opus`, Fred 2026-10-14; each with a $15 monthly limit on Go, which the spread respects through its allowance) ([OpenCode Go](https://opencode.ai/docs/go/)). Command Code (`--model` takes the full id or the part
  after `/`, case-insensitive; default `deepseek/deepseek-v4-flash`): `deepseek/deepseek-v4.1-flash`,
  `z-ai/glm-5.3-flash`, `Qwen/Qwen3.8-Flash`, `gpt-6-luna`, all on its Go plan
  ([Command Code models](https://commandcode.ai/docs/reference/cli/models)). Command Code lists only cheap
  models; OpenCode adds Kimi K3 and GLM 5.3 for design (decision 11); other premium entries (`gpt-6-sol`,
  `deepseek-v4-pro`, Claude) stay out.
- `claude.exe` (the old key) keeps working: `harnesses.claude.exe` empty falls back to it (`paths.load_config`
  copies it in). `paths.set_harness(folder, name, on) -> None` writes `on` for one harness into config.json as
  `add_project` does (every other key as written; `ValueError` when the file cannot be read).

### 3.2b models.json (decision 14)

`~/.claude/console/models.json` (or under `CC_CONSOLE_HOME`), next to config.json: per CLI, model id -> tier,
in the order the window lists them. Written from `paths.MODELS_DEFAULT` (the table below) when missing, as
`ensure_config` writes config.json; Fred edits it by hand (one model per line, a comment-free JSON file).

```json
{
  "claude":   {"opus": "opus", "sonnet": "sonnet", "haiku": "haiku", "fable": "fable",
               "claude-opus-4-8": "opus", "claude-opus-4-7": "opus", "claude-sonnet-4-6": "sonnet", "claude-haiku-4-5": "haiku"},
  "codex":    {"gpt-6-astra": "opus", "gpt-6.1-sol": "sonnet", "gpt-6-sol": "sonnet", "gpt-6-luna": "haiku"},
  "opencode": {"opencode-go/deepseek-v4.1-flash": "haiku", "opencode-go/glm-5.3-flash": "haiku",
               "opencode-go/qwen3.8-flash": "haiku", "opencode-go/gpt-6-luna": "haiku",
               "opencode-go/kimi-k3": "opus", "opencode-go/glm-5.3": "opus"},
  "cmd":      {"deepseek/deepseek-v4.1-flash": "haiku", "z-ai/glm-5.3-flash": "haiku",
               "Qwen/Qwen3.8-Flash": "haiku", "gpt-6-luna": "haiku"}
}
```

- `paths.load_models() -> (dict, str)`: the parsed file and `""`, or the last good dict (the defaults on a first
  failure) and the error (`models.json line 12: Expecting ',' delimiter`); never raises. `load_config` puts the
  dict in `cfg["models"]`; `harness.models_of(cfg, name)` reads `cfg["models"][name]` filtered by `tiers_of`
  (an entry outside is dropped with a line in the service's `console.log`).
- Claude's list is the ladder: `cfg["ladder"][tier]` is built from `models["claude"]` (the ids of that tier in
  file order, the alias first); a `ladder` in config.json is still read when models.json has no `claude` key.
- Reread without a restart: `Hub` keeps the file's mtime and reloads it at each `/api/config` and before each
  step starts; a changed file is used from the next step (a running step keeps its rung). A rung whose model was
  removed routes as auto with the note `model gone from models.json: <rung>`. The route note reads `model gone from models.json: <rung>`, and `Hub.reload_models` writes one console.log line per dropped entry (plan 27 Task 3).
- The window: the Harnesses card ends with one row, `Models · models.json · 22 models`, with `Open` (`POST /api/models/open`:
  `os.startfile` on that one fixed path, no path from the caller, through `guard.py`) and `Reload`; an error
  turns the row red with the message and the window keeps the last good list.
- Ranks are only `haiku`, `sonnet`, `opus`, `fable`: a model's tier is its rank (decision 2); a tier name the
  console does not know is dropped with a log line.

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

find_exe(cfg: dict) -> str | None          the adapter's section of cfg["harnesses"] decides; the real exe when it
                                           can be found, else the shim (see "Shims" below)
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
env(read_only: bool) -> dict               variables added to claude_cli.child_env() for this run ({} for Claude)
```

**Shims.** On Windows the npm installs of Codex, OpenCode and Command Code put a `.cmd` batch shim on PATH. A batch
file re-parses its arguments through `cmd.exe` (the reason `claude_cli.find_exe` never runs `claude.cmd`): a prompt
in argv with a newline, `&`, `|`, `%` or a quote is cut or reinterpreted, and the shim caps the line at 8191
characters. So a prompt never goes in argv through a shim: Codex reads it on stdin, OpenCode reads it from a file
(3.4), Command Code passes it to `-p` only when its exe is not a `.cmd` / `.bat` (else `RunError("cmd: only the
npm .cmd shim was found; set \"exe\" under harnesses.cmd to the real executable")`; Task 7 item 4 records where
the real one is). The fixed flags may pass through a shim.

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
| Command | `codex exec -` (prompt on stdin), `-C <cwd>`, `--skip-git-repo-check`, `--json`, `-o <file>` (the last message), `-m <model>`, `-c model_reasoning_effort="<low|medium|high>"` (the `-c key=value` form is checked; the key name is from the Codex config docs, confirmed at the live check), `-s read-only` or `-s workspace-write`, `--add-dir` not used, `--ephemeral` not used (a step may resume). Options always stand before the subcommand, as the help's `codex exec [OPTIONS] <COMMAND> [ARGS]` says: `codex exec <options> resume <id> -` | `opencode run --standalone --format json --auto -m <provider/model#variant> --file <runs/<sid>.prompt.md> "Do the task in the attached file."` (no stdin flag, no `--dir`: cwd is the process cwd; the prompt file is written by `runs` under the data folder, never by the adapter); `--title <name>`; `--session <id>` `--fork` for a resume or a copy; env `OPENCODE_DISABLE_AUTOUPDATE=1` always, `OPENCODE_PERMISSION` denying `edit` and `bash` on read-only steps (both on the opencode.ai CLI docs' env list; the permission JSON is confirmed at the live check) | `cmdc -p "<query>" --output-format json --no-auto-update --skip-onboarding --no-skills -m <model> --effort <low|medium|high> --max-turns <n>`; `--permission-mode plan` (read only) or `accept-edits`; `-n <name>`; `--session <id>` `--fork-session` for a resume or a copy |
| Effort | `low`, `medium`, `high`; `xhigh` and `max` become `high` | `effort_variant` in config per model (`{"opencode-go/deepseek-v4.1-flash": {"low": "", "high": "thinking"}}`); no entry: no `#variant` | `low`, `medium`, `high`; `xhigh` and `max` become `high` ("depends on the model": a model that refuses it fails on the first request) |
| Resume | `codex exec <options> resume <SESSION_ID> -` | `--session <id>` | `--session <id>` or `-r <id>` |
| Fork | `codex exec <options> fork <SESSION_ID> -` | `--session <id> --fork` | `-r <id> --fork-session` |
| Caps | none (`step_timeout_s`) | none (`step_timeout_s`) | `--max-turns`; exit code 8 = cap hit |
| Stop | kill the tree | kill the tree | kill the tree |
| Stream | JSONL: `thread.started` (thread id), `turn.started`, `item.completed` with `item.type == "agent_message"` (the final text), `turn.completed` with `usage` {input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}, `turn.failed`, `error` (shapes from the docs; recorded at the live check). The usage is the turn's total over all its model calls, and `cached_input_tokens` is part of `input_tokens` (the docs' sample: 24763 input, 24448 cached): it is spend, not the context size, so it never feeds the gauge | `--format json`: raw events, shape unknown until the live check; the adapter keeps every line and takes the last text of an assistant part as the final message | NDJSON events then one final result line (shape unknown until the live check) |

Command Code's `--permission-mode plan` is its read-only mode, but a plan mode may end the turn on a plan
waiting for approval instead of the findings a scout owes: Task 7 item 4 checks it, and the fallback is
`accept-edits` with the step prompt's no-edit rule, as OpenCode without the permission variable.

Where a shape is unknown the adapter's first version is defensive: `summary()["final"]` is the longest text field
of the last event that has one, `cost` and `tokens` are `None` (shown unknown), and Task 7 pins the real shape
from one recorded run in `tests/fixtures/<harness>-run.jsonl`.

### 3.5 Runs

- `RunManager.start(...)` gains `harness: str = "claude"`. The run meta gains `harness` and `harness_session`
  (the adapter's own id from `summary()`, `""` for Claude where it is the same id). The `run_started` line gains
  `harness`. A resume reads the harness from the old meta and ignores the argument (decision 13: `Hub.pull`'s
  Continue and every STOP answer call `start` with no harness) and passes `harness_session` as the id to resume;
  a fork likewise reads the forked run's meta.
- stdin: an adapter with `INTERRUPT` false gets its stdin closed once the prompt bytes are written, or at once
  when it has none (OpenCode, Command Code): a CLI that reads piped stdin when it is not a terminal would
  otherwise wait for an EOF that never comes. Claude keeps stdin open for the interrupt, as today.
- The stream file `runs/<sid>.jsonl` holds the adapter's stdout lines as they are, after the `cc_prompt` line the
  service writes (unchanged). Non-JSON lines come back as `{"raw": text}` (unchanged).
- `_watch` ends the run when `is_result` matches a line or the process exits; with `CAPS` false and
  `step_timeout_s` passed, a run older than that is stopped with the adapter's `stop` and its `run_ended` carries
  `subtype: "error_step_timeout"`, which `tasks.cap_reason` turns into `it hit the step timeout (1800 s)`. The meta
  records `timed_out: true`, because the chain reads the subtype from `Hub.final_message`, not from `run_ended`.
- `summary()` and `chat()` read the lines of the current turn: from the meta's `offset` (after this turn's
  `cc_prompt`), as `reconcile` does, never the whole file of a resumed session.
- `run_ended` gains `tokens` when the adapter reported them. `cost` is left out (not `0`) when unknown (D-3).
- `stop(sid)`: a live process goes through the adapter's `stop`; a run of an earlier service is killed as today.
- `chat(path, cwd)` dispatches on the meta's harness through the adapter's `chat`.

### 3.6 State

- `run_started` alone creates the session row (check: `State` already builds a session from any line with a
  `session_id`; Task 4's test pins it) with `harness`, `model` (the rung's model), `effort`, `window = True`,
  `source = window`. With no hook lines the row's state follows the run: `Running` while `run_live`, then `Idle` /
  `Done` from `run_ended` as an Interrupted or Failed run does today (`State` reads `run_ended` already).
- The row carries `harness` (`"claude"` for every session the hooks report). The gauge uses `tokens.context` from
  `run_ended` only when an adapter reports a true context size (none of the three does yet: Codex's usage is a
  turn's spend), else the row has no gauge (`ctx_tokens` `None`, the field `State` already has).
- Cost: `Session.cost` is a float that `run_ended` adds to. A run_ended with no `cost` key sets
  `Session.cost_unknown`; the row's `cost` and `spent` are `None` when it is set and nothing priced was added
  (D-3). `tasks.step_cost` already reads `None` as 0 for the sum; the Task page shows a step whose attempts are
  all unpriced as `cost unknown`. On the Task page the words sit in the row's sub line, the Board and the inspector show them in place of the figure (plan 27 Task 5).
- An error subtype on `run_ended` of a non-Claude session sets `failed` (`{"error": subtype, "details": ""}`), so
  the row is Failed; a Claude row keeps getting `failed` from its hook only, as today.
- `Hub.levers(sid)` returns `claude only` for `verify`, `handoff`, `escalate`, `terminal` on a non-Claude session;
  `continue` is on when the adapter's `RESUME` is true and the run is not live; `stop` as today.

### 3.7 Window

- `/api/config` gains `harnesses: {name: {"on": bool, "found": bool, "version": str, "models": {model: tier},
  "tiers": [...]}}` and keeps `claude: bool` (now `harnesses.claude.found`).
- `POST /api/harness {"name", "on"}` flips one harness (`paths.set_harness`), re-probes it, and returns the new
  `harnesses` dict. `claude` cannot be turned off (400, `Prep and the brief pass run on Claude`).
- Rung selects (`modelOptions` in `web/app.js`) list, after Claude's ladder, each harness that is on and found as a
  group: `codex · gpt-6.1-sol`, value `codex:gpt-6.1-sol`; `opencode` and `cmd` rungs only on the Run route and
  on step rows whose kind's rule tier is `haiku` (decision 11). `modelText` shows a non-Claude rung as
  `codex · gpt-6.1-sol` (no version lookup).
- The settings popover (the project picker's popover, under the Runs allowed groups) gets a Harnesses block: one
  row per name with its state word (`on`, `off`, `not found`), the version, and a switch button (`Turn on` /
  `Turn off`), pending until the service answers, as Allow runs is.
- The session head and the task card show the harness before the model when it is not `claude`
  (`codex · gpt-6.1-sol · medium`). A session with no gauge shows `context unknown` in the brief line.

### 3.8 Drift guards for every task

- Commands are argument lists, never shell strings; never the npm `.cmd` shim when a real exe exists.
- Nothing is written outside `paths.home()`; the adapters write nothing at all (the service writes the stream).
- A harness that is off or not found never appears in a select, never routes, and `known_model` refuses its rungs.
- `claude_cli.MODELS` and `EFFORTS` are unchanged; a tier is always one of them.
- No emojis or em-dashes in any text the window shows or the plan writes.
- No worktree flag on any harness (Codex `--worktree`, Command Code `-w` / `--worktree`): worktree management is a
  BRAINSTORM non-goal. No `--cloud` (Command Code) and no `--oss` / `--local-provider` (Codex) either.
- No prompt in argv through a `.cmd` / `.bat` shim (3.3, Shims).

## 4. Config keys added (`paths.DEFAULTS`)

| Key | Default | Used by |
|---|---|---|
| `harnesses` | the 3.2 block with every harness but `claude` off | `harness.find_exe`, the probe, `known_model`, the window |
| `step_timeout_s` | 1800 | `RunManager._watch` for adapters with `CAPS` false |
| `effort_variant` | `{}` | the OpenCode adapter (`{model: {effort: variant}}`) |

## 5. Not in this plan

The brainstorm's section 9 put two more items in plan 5. They are moved, so this plan stays the adapters:

- The context pack lite from Prep's citations (brainstorm 5.1 item 3): Prep's schema and step 1's prompt, no
  harness involved. Its own small plan (the brainstorm allows "plan 5 or a small plan of its own").
- The Usage mix with other harnesses: pricing adapter tokens needs a price row per non-Claude model and the fills
  of plan 18; here a non-Claude run's tokens are kept on `run_ended` so plan 18 can count them from the first run.
- The step prompt (`console/step_prompt.md`) still says "The Agent tool is not available here" and `Next model:
  <haiku|sonnet|opus>`; both are harmless to another CLI (it has no Agent tool, and a hint names a tier). Plan 23
  rewrites the prompt for the six-heading block and can make the wording neutral then.

## 6. Review, 2026-10-13

A second pass checked this plan against the code on `master`, D-1 to D-8 and Fred's pasted `--help` outputs.
What it changed, by where it was found:

- **Contradicted D-2**: Task 6 offered `opencode` and `cmd` rungs on every select; D-2 refuses them above the read
  tier. Decision 11, Tasks 5 and 6.
- **Would crash or misroute in the chain**: a harness pick reached `tasks.step_route` through `model_alias`, which
  returns `""` for `codex:...` (the pick was silently dropped) and `sonnet` for an OpenCode id that contains it.
  `_route_for` now passes the pick's tier, `start_step` checks `tier_of(pick, cfg)`. Section 3.1, Task 5.
- **Resumed on the wrong CLI**: `Hub.pull` (Continue, STOP answers) calls `runs.start` with no harness, so the
  default `claude` would have resumed a Codex thread id with `claude --resume`. Decision 13, 3.5, Task 4.
- **Timeout never reached the retry reason**: `Hub._ended` takes the subtype from `final_message`, not from
  `run_ended`. 3.5 (`timed_out` in the meta), Task 5.
- **Wrong context figure**: `input + cached + output` of Codex's `turn.completed` counts the cache twice and is
  a turn's spend over many calls, not the context. 3.4, 3.6, Task 2.
- **Codex resume command**: options after `resume` are not what the help shows. 3.4, Task 2.
- **Hung runs**: stdin stayed open for OpenCode and Command Code. 3.5, Task 4.
- **Prompt through npm shims**: argv prompts through `opencode.cmd` / `cmdc.cmd` are re-parsed by `cmd.exe`. 3.3
  Shims; OpenCode reads a prompt file, Command Code refuses a shim. Tasks 3 and 4.
- **Self-update**: OpenCode updates itself too; `OPENCODE_DISABLE_AUTOUPDATE=1`. Read-only OpenCode steps get a
  permission variable instead of an agent Fred must define. 3.3 `env`, 3.4, Task 3.
- **State facts**: the row field is `ctx_tokens`, not `context_tokens`; `Session.cost` is a float that cannot be
  `None`; nothing in `State` turns an error `run_ended` into Failed. 3.6, Task 4.
- **Counts**: Task 1 listed nine tests and counted ten; Task 4 counted the existing suite as a test. Counts
  redone in each task.
- **Moved out**: context pack lite and the Usage mix (section 5).
- **Rule order**: the CLAUDE.md lines on window-run commands and Stop are changed in Task 1, before the code that
  needs them, not at the close (Task 7); Fred confirmed the Stop exception (decision 8) the same day.
