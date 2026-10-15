// Claude Console's OpenCode plugin: OpenCode's events turned into the Claude-shaped hook input
// cc_events.py reads, piped to `py cc_events.py --harness opencode` (plan 37, README 3.2).
// install_hooks.py copies this file as index.js into ~/.config/opencode/plugins/claude-console/ and fills the two
// constants below. OpenCode 2.x loads a plugin directory's index.js and reads only its default export
// ({id, setup}); its events are the v2 `session.*` stream (README 5).
// Every handler body is in try/catch and `send` never throws: a failure never reaches OpenCode (README 3.8).
import { spawn } from "node:child_process";

const PYTHON = "__PYTHON__";
const SCRIPT = "__SCRIPT__";

function empty() {
  return { text: "", model: "", context: null, tokens: null };
}

function slotOf(mem, sid) {
  return mem.last[sid] || (mem.last[sid] = empty());
}

// The record's place: the session's own directory once `session.created` named it, else the event's.
function place(mem, id, directory) {
  return { session_id: id || "", cwd: mem.dirs[id] || directory || "" };
}

// A session's own events, or its parent's with `agent_id` when it is a task subagent.
function owner(mem, sid, directory, fields) {
  const parent = mem.parent[sid];
  const out = Object.assign(place(mem, parent || sid, directory), fields);
  if (parent) out.agent_id = sid;
  return out;
}

// One step's tokens: `context` is the last reading of the window, `tokens` the turn's sum.
function addStep(slot, tokens) {
  const cache = tokens.cache || {};
  slot.context = (tokens.input || 0) + (cache.read || 0) + (cache.write || 0);
  slot.tokens = slot.tokens || { input: 0, output: 0, cache_read: 0 };
  slot.tokens.input += tokens.input || 0;
  slot.tokens.output += tokens.output || 0;
  slot.tokens.cache_read += cache.read || 0;
}

// The turn's end: Stop for a chat, SubagentStop for a task subagent's session.
function stop(mem, sid, directory) {
  const slot = mem.last[sid] || empty();
  const parent = mem.parent[sid];
  const out = owner(mem, sid, directory, {
    hook_event_name: parent ? "SubagentStop" : "Stop",
    last_assistant_message: slot.text || "",
  });
  if (!parent) out.entrypoint = "cli";  // `opencode run` fires no session.created: the source comes here too
  if (slot.model) out.model = slot.model;
  if (slot.context != null) out.context_tokens = slot.context;
  if (!parent && slot.tokens) out.tokens = slot.tokens;
  return out;
}

// One OpenCode event -> one Claude-shaped hook input (plan 37 README 3.2), or null when it says nothing
// about a turn. Fills `mem` only; nothing here sends.
export function toHook(event, mem) {
  const data = (event && event.data) || {};
  const sid = data.sessionID;
  const directory = (event && event.location && event.location.directory) || mem.directory;
  switch (event && event.type) {
    case "session.created": {
      if (!sid) return null;
      mem.dirs[sid] = (data.location && data.location.directory) || directory || "";
      if (data.parentID) {  // a task subagent: its events belong to the parent chat
        mem.parent[sid] = data.parentID;
        return Object.assign(place(mem, data.parentID, directory), {
          hook_event_name: "SubagentStart", agent_id: sid, agent_type: "task",
        });
      }
      return Object.assign(place(mem, sid), {
        hook_event_name: "SessionStart", source: "startup", entrypoint: "cli",
      });
    }
    case "session.inbox.enqueued": {
      const item = data.item || {};
      if (item.type !== "user" || mem.parent[sid]) return null;
      mem.last[sid] = empty();  // a turn starts: its sums start at zero
      return Object.assign(place(mem, sid, directory), {
        hook_event_name: "UserPromptSubmit", prompt: (item.payload || {}).text || "",
      });
    }
    case "session.step.started": {
      const model = data.model || {};
      if (model.id) slotOf(mem, sid).model = model.providerID ? model.providerID + "/" + model.id : model.id;
      return null;
    }
    case "session.step.ended":
    case "session.step.failed":
      if (data.tokens) addStep(slotOf(mem, sid), data.tokens);
      return null;
    case "session.text.ended":
      if (data.text) slotOf(mem, sid).text = data.text;
      return null;
    case "session.tool.input.started":
      mem.tools[data.id] = data.name || "";
      return null;
    case "session.tool.called": {
      const name = mem.tools[data.id] || "";
      delete mem.tools[data.id];
      return owner(mem, sid, directory, {
        hook_event_name: "PreToolUse", tool_name: name, tool_input: data.input || {}, tool_use_id: data.id,
      });
    }
    case "session.execution.succeeded":
      return stop(mem, sid, directory);
    case "session.execution.failed": {
      const err = data.error || {};
      return owner(mem, sid, directory, {
        hook_event_name: "StopFailure", error: err.type || "unknown", error_details: err.message || "",
      });
    }
    case "session.execution.interrupted":  // Fred stopped the turn; a shutdown is no turn's end
      if (data.reason === "shutdown") return null;
      return owner(mem, sid, directory, { hook_event_name: "Interrupt" });
    case "session.compaction.ended":
      return Object.assign(place(mem, sid, directory), {
        hook_event_name: "PostCompact", trigger: data.reason || "auto",
      });
    case "session.deleted":
      return Object.assign(place(mem, sid, directory), { hook_event_name: "SessionEnd", reason: "deleted" });
    default:
      return null;
  }
}

// One hook input to cc_events.py, detached: the CLI is never slowed and a failed spawn is dropped.
export function send(input) {
  try {
    const child = spawn(PYTHON, [SCRIPT, "--harness", "opencode"],
      { stdio: ["pipe", "ignore", "ignore"], windowsHide: true, detached: true, env: process.env });
    child.on("error", () => {});
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(input));
    child.unref();
  } catch (e) {
    // dropped: a missing interpreter must not break the chat
  }
}

export function memory(directory) {
  return { directory: directory || "", dirs: {}, parent: {}, last: {}, tools: {} };
}

// `ctx.event.subscribe({signal})` is an async iterable of every event; it is read in the background so setup
// returns at once, and the function setup returns (OpenCode calls it when the plugin unloads) ends the loop.
export default {
  id: "claude-console",
  async setup(ctx) {
    const stop = new AbortController();
    try {
      const mem = memory(ctx && ctx.location && ctx.location.directory);
      const events = ctx.event.subscribe({ signal: stop.signal });
      (async () => {
        for await (const event of events) {
          try {
            const input = toHook(event, mem);
            if (input) send(input);
          } catch (e) {}
        }
      })().catch(() => {});
    } catch (e) {}
    return () => stop.abort();
  },
};
