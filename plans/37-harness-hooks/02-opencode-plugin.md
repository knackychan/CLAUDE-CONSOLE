# Task 2: the OpenCode plugin

Contract: README 3.2 (OpenCode column), 3.8. Files: `hooks/opencode/claude-console.js` (new),
`tests/test_opencode_plugin.py` (new). No build step: plain ES module, Node built-ins only.

## Shape

Corrected 2026-10-15 from OpenCode 2.0.26's own loader (README 5): a v1 plugin (an exported async function
returning `event` / `chat.message` / `tool.execute.before` hooks) is never called there. The loader reads only the
default export, `{id, effect}` or `{id, setup}`, and `setup(ctx)` reads the v2 event bus.

```js
// Filled by install_hooks.py when it copies the file as index.js (Task 3):
const PYTHON = "__PYTHON__";
const SCRIPT = "__SCRIPT__";

export function toHook(event, mem)   // one OpenCode event -> one Claude-shaped hook input, or null; pure
export function send(input)          // spawn PYTHON SCRIPT --harness opencode, write JSON to stdin; never throws
export function memory(directory)    // a fresh mem
export default {
  id: "claude-console",
  async setup(ctx) {                 // for await (const e of ctx.event.subscribe({signal})) send(toHook(e, mem))
    ...                              // read in the background; returns () => abort, called when the plugin unloads
  },
}
```

A bus event is `{id, created, type, durable, location: {directory}, data: {sessionID, ...}}`. `mem` is one
in-process object: `directory` (`ctx.location.directory`), `dirs[sessionID]` (from `session.created`),
`parent[childID]`, `tools[callID]` = the name from `session.tool.input.started`, and
`last[sessionID] = {text, model, context, tokens}`: `model` = `providerID/id` of `session.step.started`'s `model`;
per `session.step.ended` (or `.failed`) `tokens`: `context` = `input + cache.read + cache.write` of the last step,
`tokens` = the turn sum of `{input, output, cache.read}`; `text` = the last `session.text.ended` text. A turn's
sums reset on its prompt.

Mapping (every input gets `hook_event_name`, `session_id`, `cwd` = `mem.dirs[id] || event.location.directory ||
mem.directory`):

| OpenCode 2.x event | Hook input |
|---|---|
| `session.created`, no `data.parentID` | `SessionStart`, `source: "startup"`, `entrypoint: "cli"` (`opencode run` fires none) |
| `session.created`, `data.parentID` | `SubagentStart` on the parent: `agent_id` = child id, `agent_type: "task"` |
| `session.inbox.enqueued`, `item.type == "user"`, main session | `UserPromptSubmit`, `prompt` = `item.payload.text` |
| `session.tool.called` | `PreToolUse`, `tool_name` = `mem.tools[id]`, `tool_input` = `data.input`, `tool_use_id` = `data.id`; a child session's call goes on the parent with `agent_id` |
| `session.execution.succeeded`, main | `Stop`, `last_assistant_message`, `model`, `context_tokens`, `tokens` from `mem.last`, `entrypoint: "cli"` |
| `session.execution.succeeded`, child | `SubagentStop` on the parent with `agent_id`, `last_assistant_message`, `model`, `context_tokens` |
| `session.execution.interrupted`, `reason` not `shutdown` | `Interrupt` (`shutdown`: null) |
| `session.execution.failed` | `StopFailure`, `error` = `error.type`, `error_details` = `error.message` |
| `session.compaction.ended` | `PostCompact`, `trigger` = `data.reason` |
| `session.deleted` | `SessionEnd`, `reason: "deleted"` |

`send` uses `spawn(PYTHON, [SCRIPT, "--harness", "opencode"], {stdio: ["pipe", "ignore", "ignore"],
windowsHide: true, detached: true, env: process.env})`, writes `JSON.stringify(input)`, ends stdin, `unref()`s; an
`error` event is ignored. `process.env` carries `CC_CONSOLE_SID` for a window run (README 3.5).

## Tests (tests/test_opencode_plugin.py)

Skipped when `node` is not on PATH. Each test runs `node --input-type=module -e` importing the file (with
`__PYTHON__` left as is) and printing JSON for a fixture event sequence (the shapes seen on this machine, README 5):

- `test_node_check`: `node --check hooks/opencode/claude-console.js` exits 0.
- `test_default_export_is_a_v2_plugin`: `default` is `{id: "claude-console", setup}`.
- `test_setup_reads_the_event_stream_and_returns_a_stop`: a fake `ctx.event.subscribe` is read; the returned
  function aborts its signal; a `ctx` with no bus does not throw.
- `test_session_and_subagent`: `session.created` -> SessionStart with the directory; a child -> SubagentStart.
- `test_turn_prompt_tool_and_stop`: prompt, two steps, a `shell` call, a text, `execution.succeeded` -> the
  UserPromptSubmit, PreToolUse and Stop inputs (tokens summed, context of the last step).
- `test_next_prompt_resets_the_sums`, `test_child_events_belong_to_the_parent`,
  `test_failed_interrupted_compacted_deleted`, `test_unknown_event_is_null`.

## Steps

1. Tests first; they fail (no file).
2. Write the plugin; `node --check` it.
3. Run all tests; commit `plan 37 task 2: OpenCode plugin`.

## Drift guards

- No `import` beyond `node:child_process`; no network; no file writes.
- Nothing is sent for `session.step.*`, `session.text.*` or `session.tool.input.*` events: they only fill `mem`.
