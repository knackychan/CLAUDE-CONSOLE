# Task 1: cc_events.py for every CLI

Contract: README 3.1, 3.3, 3.4, 3.5. Files: `cc_events.py`, `tests/test_cc_events.py`, `tests/fixtures/`
(three small transcript files, written by the test setUp, not committed binaries).

## Signatures

```python
HARNESSES = ("claude", "codex", "opencode", "cmd")
TOOL_MAP: dict    # harness -> {native name: (claude name, {native key: claude key})}, README 3.3
SOURCES_IN = ...  # not here: state.SOURCES owns the mapping (Task 4)

def harness_arg(argv: list) -> str                     # "--harness codex" -> "codex"; anything else -> "claude"
def map_tool(harness: str, tool: str, tool_input) -> tuple   # (claude name, input dict with claude keys)
def patch_path(text: str) -> str                       # first "*** Update|Add|Delete File: <path>" of a patch, or ""
def strip_ide_context(text: str) -> str                # Codex VS Code: the text after the last "## My request:" line
def codex_tail(path) -> dict                           # README 3.4
def cmd_tail(path) -> dict                             # README 3.4
def build_record(data: dict, now: float = None, harness: str = "claude", env: dict = None) -> dict
```

`build_record` keeps its current body for `harness == "claude"` and its current output for every Claude test.
For another harness:

1. `rec["harness"] = harness`.
2. `env = os.environ if env is None else env`; when `env.get("CC_CONSOLE_SID")`: `rec["harness_session"] =
   data["session_id"]`, `rec["session_id"] = env["CC_CONSOLE_SID"]` (README 3.5).
3. `UserPromptSubmit`: the prompt goes through `strip_ide_context` (Codex) before `strip_injected`.
4. `PreToolUse`: `tool, tool_input = map_tool(harness, data.get("tool_name"), data.get("tool_input"))`, then the
   same `rec["tool"]`, `rec["what"]` as Claude.
5. `Stop` / `SubagentStop`: the tail is `codex_tail` / `cmd_tail` / nothing (opencode); `model` falls back to
   `data["model"]` (Codex sends it on every event), `context_tokens` and `tokens` to `data` (opencode). For `cmd`,
   `message = tail["reply_text"]` (no `last_assistant_message`) and `rec["prompt"]` = the tail's prompt, clipped and
   masked like UserPromptSubmit. `tokens` is kept only when it is a dict of three ints.
6. `Interrupt`: no extra fields.
7. `effort`: a tail's `effort` when the input has none.

`main()` reads `harness_arg(sys.argv[1:])` inside its `try` and passes it on. `opencode` input arrives with
`hook_event_name` like the others (Task 2 builds it).

## Tests (tests/test_cc_events.py, new class `OtherHarnessTest`)

- `test_harness_arg`: `[]`, `["--harness"]`, `["--harness", "x"]` -> claude; `["--harness", "codex"]` -> codex.
- `test_claude_records_unchanged`: every existing Claude case with `harness="claude"` has no `harness` key.
- `test_codex_tool_map`: `exec_command {"cmd": ["git", "status"]}` -> Bash `git status`; `apply_patch` with a patch
  text -> Edit with the short path; an unknown tool keeps its name and `what` "".
- `test_opencode_and_cmd_tool_map`: `read {"filePath": ...}` -> Read; `edit_file {"file_path": ...}` -> Edit;
  `read_directory {"path": "src"}` -> Glob `src`.
- `test_console_sid_rewrite`: env `{"CC_CONSOLE_SID": "c1"}`, data session `x1`, harness codex -> session `c1`,
  `harness_session` `x1`; harness claude with the same env -> session `x1`, no `harness_session`.
- `test_ide_context_stripped`: a Codex prompt `# Context from my IDE setup:\n...\n## My request:\nfix it` -> `fix it`.
- `test_codex_tail`: fixture rollout (session_meta source vscode, turn_context model/effort, user_message, two
  token_count) -> model, effort, context_tokens of the last, tokens summed after the user message, entrypoint vscode.
- `test_cmd_tail`: fixture transcript + meta.json -> model, effort, context_tokens, reply_text, prompt, tokens,
  entrypoint `interactive`.
- `test_tails_never_raise`: missing file, binary garbage, empty file -> `{}`.
- `test_main_harness_arg_never_raises`: `main()` with `sys.argv` `["cc_events.py", "--harness", "codex"]` and bad
  stdin returns 0.

## Steps

1. Write the tests; run `py -m unittest tests.test_cc_events` (they fail).
2. Add `HARNESSES`, `TOOL_MAP`, `harness_arg`, `map_tool`, `patch_path`, `strip_ide_context`.
3. Add `codex_tail`, `cmd_tail` (same seek-from-end read as `transcript_tail`; the head read for `session_meta`).
4. Extend `build_record` and `main` as above.
5. Run all tests (`py -m unittest discover -s tests`), commit `plan 37 task 1: cc_events.py for every CLI`.

## Drift guards

- Claude's records do not change: no `harness` key, no new field.
- The hook still never raises, never touches the network, and writes only through `append`.
- A tail reads at most 512 KB from the end plus 64 KB from the head.
