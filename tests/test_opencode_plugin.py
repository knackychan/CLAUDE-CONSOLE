import json
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "hooks" / "opencode" / "claude-console.js"
SKIP = "node is not on PATH"
DIR = "D:/p"


def node(body: str) -> object:
    """Run `body` (which ends by printing JSON) in one node process with the plugin imported as `m`."""
    script = "const m = await import(" + json.dumps(PLUGIN.as_uri()) + ");\n" + body
    done = subprocess.run(["node", "--input-type=module", "-e", script],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def node_events(events: list) -> list:
    """Run toHook over `events` with a fresh `mem`; returns one hook input (or null) per event."""
    return node("const mem = m.memory(" + json.dumps(DIR) + ");\n"
                "const events = " + json.dumps(events) + ";\n"
                "console.log(JSON.stringify(events.map((e) => m.toHook(e, mem))));\n")


def ev(kind: str, sid: str = "s1", **data) -> dict:
    """One OpenCode 2.x bus event as `ctx.event.subscribe` yields it (README 5)."""
    return {"id": "evt_1", "created": 1, "type": kind, "location": {"directory": DIR},
            "data": dict(sessionID=sid, **data)}


def prompt(text: str, sid: str = "s1") -> dict:
    return ev("session.inbox.enqueued", sid, inboxID="msg_1",
              item={"type": "user", "payload": {"text": text, "files": []}, "delivery": "steer"})


def step(tokens: dict, sid: str = "s1") -> list:
    model = {"id": "deepseek-v4.1-flash", "providerID": "opencode-go", "variant": "high"}
    return [ev("session.step.started", sid, assistantMessageID="msg_2", agent="build", model=model),
            ev("session.step.ended", sid, assistantMessageID="msg_2", finish="stop", cost=0.0, tokens=tokens)]


@unittest.skipIf(shutil.which("node") is None, SKIP)
class OpenCodePluginTest(unittest.TestCase):
    def test_node_check(self):
        done = subprocess.run(["node", "--check", str(PLUGIN)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_default_export_is_a_v2_plugin(self):
        out = node("console.log(JSON.stringify({id: m.default.id, setup: typeof m.default.setup,"
                   " keys: Object.keys(m.default)}));\n")
        self.assertEqual(out, {"id": "claude-console", "setup": "function", "keys": ["id", "setup"]})

    def test_setup_reads_the_event_stream_and_returns_a_stop(self):
        out = node("let signal = null;\n"
                   "const ctx = {location: {directory: 'D:/p'}, event: {subscribe: (o) => { signal = o.signal;"
                   " return (async function* () { yield {type: 'model.updated', data: {}}; })(); }}};\n"
                   "const stop = await m.default.setup(ctx);\n"
                   "const before = signal.aborted; stop();\n"
                   "console.log(JSON.stringify([typeof stop, before, signal.aborted]));\n")
        self.assertEqual(out, ["function", False, True])
        broken = node("const stop = await m.default.setup({});\nconsole.log(JSON.stringify(typeof stop));\n")
        self.assertEqual(broken, "function")  # a ctx without an event bus never throws into OpenCode

    def test_session_and_subagent(self):
        out = node_events([ev("session.created", "s1", location={"directory": "D:/q"}),
                           ev("session.created", "c2", parentID="s1")])
        self.assertEqual(out[0], {"session_id": "s1", "cwd": "D:/q", "hook_event_name": "SessionStart",
                                  "source": "startup", "entrypoint": "cli"})
        self.assertEqual(out[1], {"session_id": "s1", "cwd": "D:/q", "hook_event_name": "SubagentStart",
                                  "agent_id": "c2", "agent_type": "task"})

    def test_turn_prompt_tool_and_stop(self):
        tokens = {"input": 50, "output": 38, "reasoning": 19, "cache": {"read": 10240, "write": 0}}
        out = node_events([
            prompt("run echo hi"),
            *step(tokens),
            ev("session.tool.input.started", assistantMessageID="msg_2", id="call_1", name="shell"),
            ev("session.tool.called", assistantMessageID="msg_2", id="call_1", input={"command": "echo hi"},
               executed=False),
            *step({"input": 121, "output": 2, "reasoning": 0, "cache": {"read": 10240, "write": 0}}),
            ev("session.text.ended", assistantMessageID="msg_3", ordinal=0, text="done"),
            ev("session.execution.succeeded"),
        ])
        self.assertEqual(out[0], {"session_id": "s1", "cwd": DIR, "hook_event_name": "UserPromptSubmit",
                                  "prompt": "run echo hi"})
        self.assertEqual(out[1:4], [None, None, None])  # steps and tool names only fill memory
        self.assertEqual(out[4], {"session_id": "s1", "cwd": DIR, "hook_event_name": "PreToolUse",
                                  "tool_name": "shell", "tool_input": {"command": "echo hi"},
                                  "tool_use_id": "call_1"})
        self.assertEqual(out[-1], {"session_id": "s1", "cwd": DIR, "hook_event_name": "Stop",
                                   "last_assistant_message": "done", "entrypoint": "cli",
                                   "model": "opencode-go/deepseek-v4.1-flash", "context_tokens": 10361,
                                   "tokens": {"input": 171, "output": 40, "cache_read": 20480}})

    def test_next_prompt_resets_the_sums(self):
        tokens = {"input": 10, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}}
        out = node_events([prompt("a"), *step(tokens), ev("session.execution.succeeded"),
                           prompt("b"), *step(tokens), ev("session.execution.succeeded")])
        self.assertEqual(out[-1]["tokens"], {"input": 10, "output": 1, "cache_read": 0})

    def test_child_events_belong_to_the_parent(self):
        out = node_events([
            ev("session.created", "s1"), ev("session.created", "c2", parentID="s1"),
            prompt("the task's own prompt", "c2"),
            ev("session.tool.input.started", "c2", id="call_9", name="read"),
            ev("session.tool.called", "c2", id="call_9", input={"filePath": "a.py"}, executed=False),
            ev("session.execution.succeeded", "c2"),
        ])
        self.assertIsNone(out[2])  # a subagent's prompt is not Fred's
        self.assertEqual((out[4]["session_id"], out[4]["agent_id"], out[4]["tool_name"]), ("s1", "c2", "read"))
        self.assertEqual(out[5]["hook_event_name"], "SubagentStop")
        self.assertEqual((out[5]["session_id"], out[5]["agent_id"]), ("s1", "c2"))
        self.assertNotIn("tokens", out[5])
        alone = node_events([ev("session.created", "c2", parentID="s1")])  # `opencode run`: no parent created
        self.assertEqual((alone[0]["session_id"], alone[0]["cwd"]), ("s1", DIR))

    def test_failed_interrupted_compacted_deleted(self):
        out = node_events([
            ev("session.execution.interrupted", reason="user"),
            ev("session.execution.interrupted", reason="shutdown"),
            ev("session.execution.failed", error={"type": "APIError", "message": "boom"}),
            ev("session.compaction.ended", reason="manual", text="", recent=""),
            ev("session.deleted"),
        ])
        self.assertEqual(out[0]["hook_event_name"], "Interrupt")
        self.assertIsNone(out[1])  # OpenCode closing is no turn's end
        self.assertEqual((out[2]["hook_event_name"], out[2]["error"], out[2]["error_details"]),
                         ("StopFailure", "APIError", "boom"))
        self.assertEqual((out[3]["hook_event_name"], out[3]["trigger"]), ("PostCompact", "manual"))
        self.assertEqual((out[4]["hook_event_name"], out[4]["reason"]), ("SessionEnd", "deleted"))

    def test_unknown_event_is_null(self):
        self.assertEqual(node_events([{"type": "lsp.updated", "data": {}}, None]), [None, None])


if __name__ == "__main__":
    unittest.main()
