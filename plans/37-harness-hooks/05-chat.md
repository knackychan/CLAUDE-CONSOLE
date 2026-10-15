# Task 5: the Chat tab of an outside chat on any CLI

Contract: README 3.4, 3.8. Files: `console/transcript.py`, `console/server.py`, `tests/test_transcript.py`.

## Signatures (console/transcript.py)

```python
def turns_of(harness: str, path: str, session_id: str, limit: int = TURNS, opencode_db: Path = None) -> list
def first_prompt_of(harness: str, path: str, session_id: str, opencode_db: Path = None) -> str
def codex_turns(path, limit: int = TURNS) -> list      # rollout: event_msg user_message -> you, agent_message -> claude
def cmd_turns(path, limit: int = TURNS) -> list        # message role user text -> you, assistant text blocks -> claude
def opencode_turns(db: Path, session_id: str, limit: int = TURNS) -> list
OPENCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
```

Items have the shape `turns` returns today (`{"role": "you" | "claude", "text", "ts", "files": []}`), text cut at
`TURN_MAX`, injected blocks stripped with `_INJECTED` (and, for Codex, the IDE context with
`cc_events.strip_ide_context`'s rule, copied as `_IDE_CONTEXT` here: transcript.py does not import the hook).
Codex `agent_message` items with `phase == "commentary"` are kept (they are what the chat showed); reasoning and tool
records are left out, as for Claude.

`opencode_turns`: `sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=1)`, one query
`SELECT type, data, time_created FROM session_message WHERE session_id = ? ORDER BY seq DESC LIMIT ?` (limit x 20
rows, then the last `limit` turns), `user` rows -> you (`data.text`), `assistant` rows -> claude (the `text` content
blocks joined). Any `sqlite3.Error` or bad JSON -> `[]`. The connection is closed in a `finally`.

`turns_of` dispatches: `claude` -> `turns(path, limit)`, `codex` -> `codex_turns`, `cmd` -> `cmd_turns`,
`opencode` -> `opencode_turns(opencode_db or OPENCODE_DB, session_id, limit)`.

## Service (console/server.py)

The three Claude-only reads go through the dispatchers with `s["harness"]`: the chat endpoint (line ~2376),
`last_reply` (line ~743), `brief_text`'s `first_prompt` (line ~754). `transcript.find` stays Claude's (an older
step with no row).

## Tests (tests/test_transcript.py)

- `test_codex_turns`: fixture rollout -> you / claude in order, IDE context stripped, tool calls absent.
- `test_cmd_turns`: fixture -> you / claude; tool_result user records absent.
- `test_opencode_turns`: a temp sqlite file with a `session_message` table and four rows -> two turns; a missing file
  -> `[]`; a database with no such table -> `[]`.
- `test_opencode_db_opened_read_only`: after the call, the temp db's bytes are unchanged.
- `test_turns_of_dispatch`: claude path still reads a Claude transcript.

## Steps

1. Tests first; they fail.
2. Readers, then the dispatchers, then the three call sites.
3. Run all tests; commit `plan 37 task 5: Chat for every CLI`.

## Drift guards

- OpenCode: only `session_message` is queried (README 3.8); no write, no `PRAGMA` that writes.
- Nothing from a transcript is logged.
