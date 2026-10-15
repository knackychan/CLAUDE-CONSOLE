"""Small Codex / Command Code transcript fixtures, written by each test's setUp (never committed files)."""
import json


def _write(path, lines) -> str:
    path = str(path)
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
    return path


def codex_rollout(path, source: str = "vscode") -> str:
    """A rollout with one turn: session_meta, turn_context, the VS Code prompt, an agent message, a tool call
    and two token counts. Model gpt-6-astra/medium, context 1200, tokens {1100, 80, 1100}, source `source`."""
    return _write(path, [
        {"type": "session_meta", "payload": {"session_id": "x1", "source": source, "cwd": "d:\\repo"}},
        {"type": "turn_context", "payload": {"model": "gpt-6-astra", "effort": "medium"}},
        {"type": "event_msg", "payload": {"type": "user_message", "message":
            "# Context from my IDE setup:\n\n## Active file: a.py\n\n## My request:\nfix the retry on line 9"}},
        {"type": "event_msg", "payload": {"type": "agent_message", "message": "Looking at the retry."}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec_command",
                                              "input": "{\"cmd\":[\"git\",\"status\"]}"}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage":
            {"input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 50}}}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage":
            {"input_tokens": 1200, "cached_input_tokens": 700, "output_tokens": 30}}}},
    ])


def cmd_transcript(path, entrypoint: str = "interactive") -> str:
    """A Command Code transcript with one turn: a prompt, two tool-using assistant records and a final reply,
    with its `.meta.json` beside it. Model m3/high, context 3000, tokens {1000, 300, 4000}."""
    _write(path, [
        {"type": "session", "id": "c1", "cwd": "d:\\repo"},
        {"type": "message", "model": "m1", "effort": "high",
         "usage": {"inputTokens": 100, "outputTokens": 10, "cacheReadTokens": 40}, "message":
         {"role": "user", "content": [{"type": "text", "text": "audit the project"}]}},
        {"type": "message", "model": "m2", "effort": "high",
         "usage": {"inputTokens": 2000, "outputTokens": 100, "cacheReadTokens": 1500}, "message":
         {"role": "assistant", "content": [{"type": "thinking", "thinking": "hmm"},
                                           {"type": "tool_use", "name": "read_file", "input": {"file_path": "a"}}]}},
        {"type": "message", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "body"}]}]}},
        {"type": "message", "model": "m3", "effort": "high",
         "usage": {"inputTokens": 3000, "outputTokens": 200, "cacheReadTokens": 2500}, "message":
         {"role": "assistant", "content": [{"type": "text", "text": "# Report\n\nDone."}]}},
    ])
    path = str(path)
    _write(path[:-6] + ".meta.json", [{"model": "m3", "entrypoint": entrypoint, "title": "Project Audit"}])
    return path
