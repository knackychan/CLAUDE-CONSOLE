# Plan 37: Every CLI hooked like Claude Code. Guided implementation plan

> Asked by Fred, 2026-10-15: "hook the others too, same behavior and treatment as Claude Code CLI". Master:
> [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md). Builds on
> [05-harnesses](../05-harnesses/README.md) (adapters, rungs, `harness_session`), [01-watch](../01-watch.md) (the
> hook, `State`), [18-fills](../18-fills/README.md) (`usage.add_other`).

This folder is the plan. No code is written in it: each task names the files, the functions with their signatures,
the data shapes, the tests with what they assert, and the ordered steps. The code is written when a task is
executed, test first, one task at a time (test + commit).

**State: written 2026-10-15 from the code, the CLIs' docs and this machine's own session files (section 5). Tasks 1
to 7 to execute. Start state: 633 tests OK on Windows (working tree of branch `claude/project-thread-jctz3k` with
the uncommitted plan 33-36 work of other chats).**

## 1. Why

The Console sees a chat only when `cc_events.py` runs as a hook, and only Claude Code has it installed
(`~/.claude/settings.json`). A Codex, OpenCode or Command Code chat Fred starts in VS Code or a terminal fires
nothing, so it never shows; today's Codex VS Code chats are in `~/.codex/sessions/2026/10/15/` and nothing reads
them. The `harnesses.<name>.on` switch only lets the Console start its own runs there.

All three CLIs have a hook system now (section 5). This plan installs the same `cc_events.py` in each, so every
chat on this machine becomes a session row with the same states, Steps, gauge, verdict, reply, usage and levers as a
Claude Code chat. Plan 05 decision 10 (`claude only` on Verify, Handoff, Escalate, Open in terminal) is replaced by
section 3.6.

## 2. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-hook-record.md](01-hook-record.md) | `cc_events.py --harness <name>`: the harness tag, the window-run id rewrite (`CC_CONSOLE_SID`), tool names mapped to Claude's, the Codex and Command Code transcript tails, turn tokens on Stop | nothing |
| 2 | [02-opencode-plugin.md](02-opencode-plugin.md) | `hooks/opencode/claude-console.js`: OpenCode 2.x plugin (default `{id, setup}`, `ctx.event.subscribe`) turning its bus events into Claude-shaped hook input, piped to `cc_events.py --harness opencode` | 1 |
| 3 | [03-install.md](03-install.md) | `install_hooks.py --harness claude,codex,cmd,opencode`: merge and remove in `~/.codex/hooks.json`, `~/.commandcode/settings.json`, the OpenCode plugin directory `plugins/claude-console/` | 1, 2 |
| 4 | [04-state-usage.md](04-state-usage.md) | `State` takes `harness`, `Interrupt`, sources and titles of the other CLIs; the service counts an outside chat's turn tokens through `usage.add_other` | 1 |
| 5 | [05-chat.md](05-chat.md) | The Chat tab of an outside chat on any CLI: `transcript.turns` / `first_prompt` read Codex rollouts, Command Code transcripts and OpenCode's database (read only) | 4 |
| 6 | [06-levers.md](06-levers.md) | Levers on every harness: Continue, Verify, Handoff, Escalate as forks of an outside chat; Escalate's ladder per harness; Open in terminal for Codex, OpenCode, Command Code; `CC_CONSOLE_SID` in runs | 4 |
| 7 | [07-live-check-close.md](07-live-check-close.md) | Fred installs and trusts the hooks, one chat per CLI, the recorded shapes fix the tool tables; PLAN.md, CLAUDE.md, BRAINSTORM | 1-6 |

Other chats edit `PLAN.md`, `CLAUDE.md`, `console/server.py`, `web/app.js` in parallel: anchored edits only, stage
only this plan's lines. **Lands on** plan 34 (`cc_events.py` main: the import inside never-raise): if plan 34 is
placed first, Task 1 adds its argv parsing inside that same `try`.

## 3. The contract (what every task keeps)

### 3.1 One hook, one log

- One script, `cc_events.py`, for all four CLIs. Its first argument pair `--harness <name>` names the CLI; absent or
  unknown means `claude` (the existing Claude install passes no argument and keeps working unchanged).
- The rules of CLAUDE.md hold for every CLI: never raises, always exits 0, no network, summaries only through
  `console/redact.py`, writes `~/.claude/console/events-<day>.jsonl` (or `CC_CONSOLE_HOME`) and nothing else.
- A record of another CLI carries `"harness": "<name>"`; a Claude record carries no `harness` key (records stay
  byte-identical to today's).
- Record events are Claude's names, so `State` needs no second vocabulary. One event is new: `Interrupt`.

### 3.2 What each CLI sends (installed events)

| Record event | Claude Code | Codex (`~/.codex/hooks.json`) | Command Code (`~/.commandcode/settings.json`) | OpenCode (plugin) |
|---|---|---|---|---|
| SessionStart | hook | hook | hook | `session.created` without `parentID` (`opencode run` fires none: Stop carries `entrypoint`) |
| UserPromptSubmit | hook | hook (`prompt`) | none: the prompt comes on Stop from the transcript | `session.inbox.enqueued` with a `user` item (`payload.text`) |
| PreToolUse | hook | hook | hook | `session.tool.called` (name from `session.tool.input.started`) |
| SubagentStart / SubagentStop | hook | hook | none | `session.created` with `parentID` / that child's `session.execution.succeeded` |
| Stop | hook | hook (`last_assistant_message`) | hook, reply and prompt read from `transcript_path` | `session.execution.succeeded` (text from `session.text.ended`, model and tokens from `session.step.*`) |
| StopFailure | hook | none | none | `session.execution.failed` |
| Interrupt (new) | none | hook | none | `session.execution.interrupted` (not `reason: shutdown`) |
| PostCompact | hook | hook | none | `session.compaction.ended` |
| SessionEnd | hook | hook | none | `session.deleted` |
| PermissionDenied, InstructionsLoaded | hook | none | none | none |

Codex handlers: `"type": "command"`, `"async": true`, `"timeout": 5`, `command` and `commandWindows` both
`"<python>" "<cc_events.py>" --harness codex`. Command Code has no `async` key on its docs page: `"timeout": 5`
and the same command with `--harness cmd`; the hook takes about 75 ms (plan 01 timing), so a turn is not slowed.

### 3.3 Tool names

`cc_events.py` maps each CLI's tool name and input keys to Claude's before `redact.summarize`, so `State`'s
`READ_TOOLS` / `WRITE_TOOLS` and the Steps line work unchanged. A name not in the table is kept as it came and its
`what` is "". The tables come from this machine's history (section 5) and are corrected at the live check (Task 7
may edit a table row, never the logic).

| Claude name | Codex | Command Code | OpenCode |
|---|---|---|---|
| Bash | `exec_command`, `shell`, `local_shell`, `exec` (`cmd` key -> `command`, a list joined by spaces) | `shell_command` | `bash`, `shell` |
| PowerShell | | `powershell` | |
| Read | `view_image` (`path` -> `file_path`) | `read_file` | `read` (`filePath` -> `file_path`) |
| Write | | `write_file` | `write` (`filePath` -> `file_path`) |
| Edit | `apply_patch` (`file_path` = first `*** Update File:` / `*** Add File:` / `*** Delete File:` path of the patch text) | `edit_file` | `edit`, `patch` (`filePath` -> `file_path`) |
| Grep | | `grep` | `grep` |
| Glob | | `glob`, `read_directory` (`path` -> `pattern`) | `glob`, `list` (`path` -> `pattern`) |
| WebFetch | | `web_fetch` | `webfetch` |
| WebSearch | `web_search` | | `websearch` |
| Agent | `spawn_agent` (`task_name` -> `description`) | | `task`, `subagent` |
| Skill | | `activate_skill` (`name` -> `skill`) | `skill` (`name` -> `skill`) |
| TodoWrite | | `todo_write` | `todowrite` |
| AskUserQuestion | `request_user_input`, `request_user_input_async` | `ask_user_question` | `question` |

### 3.4 Transcript tails (Stop)

`transcript_tail` stays Claude's. Two siblings read the last 512 KB, never raise, and return the same keys
(`model`, `context_tokens`, `entrypoint`) plus `effort`, `tokens` and, for Command Code, `reply_text` and `prompt`:

- `codex_tail(path)`: rollout JSONL (`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`). `model` and `effort` from the
  last `turn_context` payload; `context_tokens` = the last `event_msg` `token_count` `info.last_token_usage.input_tokens`;
  `tokens` = over the `token_count` events after the last `event_msg` `user_message`: `input` = input_tokens -
  cached_input_tokens, `cache_read` = cached_input_tokens, `output` = output_tokens (sum of `last_token_usage`);
  `entrypoint` from the first line (`session_meta` payload `source`), read from the head (64 KB).
- `cmd_tail(path)`: Command Code JSONL (`~/.commandcode/projects/<slug>/<id>.jsonl`, records
  `{"type": "message", "model", "effort", "usage": {inputTokens, outputTokens, cacheReadTokens, cacheWriteTokens},
  "message": {"role", "content": [blocks]}}`). `model`, `effort` from the last assistant record; `context_tokens` =
  its `inputTokens`; `tokens` summed over the assistant records after the last user record with a `text` block
  (`input` = inputTokens - cacheReadTokens); `reply_text` = the text blocks of those assistant records, last one;
  `prompt` = that user record's text; `entrypoint` = `entrypoint` of `<id>.meta.json` beside the file.
- OpenCode has no transcript path: the plugin sends `model`, `context_tokens` and `tokens` in its Stop input, and
  `build_record` takes them as they come when `harness == "opencode"`.

`SOURCES` gains `vscode` -> `vscode`, `cli` -> `terminal`, `exec` -> `terminal` (Codex), `interactive` ->
`terminal`, `print` -> `terminal` (Command Code); an OpenCode record carries `entrypoint: "cli"`.

### 3.5 Window runs: one row, not two

A run the Console starts on Codex, OpenCode or Command Code now fires hooks too, with the CLI's own session id.
`RunManager.start` puts `CC_CONSOLE_SID=<console sid>` in the child's env for every non-Claude harness. When
`cc_events.py` sees it (and the harness is not `claude`), the record's `session_id` becomes that value and the CLI's
id goes to `harness_session`. The run's row then gets its Steps, reply and verdict from the hooks, like a Claude
window run. `count_run` keeps counting window runs from `run_ended`; Stop tokens count only for a session that is not
a window run (3.7), so nothing is counted twice.

### 3.6 Levers on every harness

`Hub.levers` reads the harness from the session row (`s["harness"]`), not only from a run meta. For a non-Claude
session:

| Lever | Window run (has a meta) | Outside chat (VS Code, terminal) |
|---|---|---|
| Continue | resume, as today | fork through the adapter (`harness_session` = the row id, which is the CLI's id) |
| Verify | `levers.VERIFY_TEXT`, resume | same text, fork |
| Handoff | the `session-handoff` skill's text sent as the prompt (`levers.handoff_prompt`), since the slash command is Claude's | same, fork |
| Escalate | `levers.escalate_step(model, effort, harness, cfg)`: effort up to `high`, then the next model of a higher tier in `models.json`; none above: `already on the top route` | same, fork |
| De-escalate | window runs only, as today | off: `only for window runs` |
| Open in terminal | `codex resume <id> -m <model>`, `opencode -s <id> -m <model>`, `cmdc -r <id> -m <model>` in a new console | off, as for a Claude outside chat (no meta) |

The rule of CLAUDE.md holds: a VS Code or terminal chat is only ever forked, never resumed in place. The verdict of
a non-Claude run comes from its Stop hook; when the hook did not run (untrusted, not installed), `run_ended` carries
`verdict` from the adapter's final text (`cc_events.verdict(final)`), so Verify still works.

### 3.7 Usage

An outside non-Claude chat's Stop record carries `tokens` (`{input, output, cache_read}` of the turn). The service
counts it through `usage.add_other(folder, f"{sid}@{ts}", day, key, tokens, cost)` with `key =
fills.model_key("<harness>:<model>", cfg)` and `cost = fills.price(tokens, prices[key])` (None = unknown, D-3), the
same path `count_run` uses. A Stop of a window run is never counted (its `run_ended` is).

### 3.8 Hard rules

- No hook writes trust state of another CLI. Fred trusts the new hooks himself (Codex `/hooks`, Command Code's
  prompt). `install_hooks.py` prints that step.
- `install_hooks.py` is the only code that writes another CLI's config, and only when Fred runs it with `--write`
  or `--remove`; every write backs the file up first, and an unreadable file is never overwritten.
- OpenCode's database is opened read only (`file:...?mode=ro`, `uri=True`), and only `session_v2` and
  `session_message` are queried (the file also holds credentials).
- The plugin never throws into OpenCode: every handler body is in `try {} catch {}`, the child process is spawned
  detached with `stdio` ignored for output, and a failed spawn is dropped.

## 4. Decisions (for Fred; each written for option (a))

| # | Question | (a), written | (b) |
|---|---|---|---|
| D1 | A chat waiting on a permission prompt (Codex `PermissionRequest`, OpenCode `permission.asked`; Claude's own is not installed either) | Not in this plan: it shows Quiet / Stall? like a Claude chat today | A `PermissionRequest` record and an `asks` state under Needs you, for all four CLIs (Claude's hook too) |
| D2 | Command Code has no prompt hook | The turn opens at its first tool call, the title and prompt arrive on Stop from the transcript; a turn with no tool call shows only when it ends | Also read the transcript tail on every PreToolUse (slower hook) |
| D3 | Outside non-Claude chats in the fills | Counted (3.7), so balancing sees Codex use from VS Code | Not counted |

## 5. Facts this plan rests on (checked 2026-10-15)

- Codex 0.162.1: hooks docs (developers.openai.com/codex/hooks, now learn.chatgpt.com/docs/hooks): events
  SessionStart, SessionEnd, PreToolUse, PermissionRequest, PostToolUse, PreCompact, PostCompact, UserPromptSubmit,
  SubagentStart, SubagentStop, Stop, Interrupt; common input `session_id`, `transcript_path`, `cwd`,
  `hook_event_name`, `model`; Stop has `last_assistant_message`; handler keys `type`, `command`, `commandWindows`,
  `async`, `timeout`; new or changed hooks are skipped until trusted (`/hooks`). `~/.codex/hooks.json` already
  holds an impeccable hook; the installer keeps it.
- Command Code 1.81.0: hooks docs (commandcode.ai/docs/hooks, /reference): events PreToolUse, PostToolUse, Stop,
  SessionStart; input `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `permission_mode`, tool fields;
  `type` command only, `timeout` default 30; config `~/.commandcode/settings.json` (today: `permissions` only).
  Hooks are skipped in plan mode. Trust (`trusted-hooks.json`, today `{}`) is not documented: Task 7 records it.
- OpenCode 2.0.26 (corrected 2026-10-15 from the shipped binary and a `opencode run --standalone` turn under a
  scratch `XDG_CONFIG_HOME`): each folder in `~/.config/opencode/plugins/` (and a project's `.opencode/plugins/`)
  loads at server start with no `opencode.json` entry, through `<folder>/server` then `<folder>/index` (a
  `package.json` `main` is not read; a loose `.js` file there loads too). A `plugin` entry naming a file logs
  `configured plugin path must be a directory` and is dropped (the caveman entry today). The loader reads only the
  default export, `{id, effect}` or `{id, setup}` (`Plugin must export a default definition with an id and an
  effect or setup function.`); v1 hooks (`event`, `chat.message`, `tool.execute.before`) are never called.
  `setup(ctx)` gets `ctx.location.directory` and `ctx.event.subscribe({signal})`, an async iterable of bus events
  `{id, created, type, location: {directory}, data: {sessionID, ...}}`; a turn is `session.inbox.enqueued` (user
  item), `session.execution.started`, `session.step.started` (`model {id, providerID}`), `session.tool.input.started`
  (`name`), `session.tool.called` (`input`), `session.step.ended` (`tokens {input, output, reasoning, cache {read,
  write}}`), `session.text.ended` (`text`), `session.execution.succeeded`; a task subagent is a `session.created`
  with `parentID`. Tool names seen: `shell` (`command`), `task`. The `event` table of `opencode.db` is empty.
  Chats live in `~/.local/share/opencode/opencode.db`: `session_v2` (id, parent_id, directory, title,
  model, time_*) and `session_message` (session_id, type `user` / `assistant`, seq, data JSON with `text` or
  `content` blocks `{type: text | reasoning | tool, ...}` and `model {id, providerID}`).
- Tool names in this machine's history: section 3.3.
- Resume flags from `--help`: `codex resume [SESSION_ID]`, `opencode -s <id>`, `cmdc -r <id>`, each with `-m`.

## 6. Out of scope

Reading the CLIs' files for chats that started before the hooks were installed (a chat shows from its first hook
event on, as a Claude chat did in phase 1); Codex rate-limit percentages (`token_count.rate_limits`) on the Usage
page; any other CLI.
