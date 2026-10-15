# Task 2: the Codex adapter and its fake

> Contract: [README.md](README.md) 3.3, 3.4 (Codex column). Depends on Task 1. Facts: `codex exec --help` of
> codex-cli 0.162.1 pasted by Fred on 2026-10-13 (the design doc, section 3).

**Files**
- Create: `console/harness/codex.py`
- Create: `tests/fake_codex.py` (a stand-in for `codex.exe`: same flags, the documented JSONL shapes)
- Modify: `tests/test_harness.py` (class `CodexTest`)

## `console/harness/codex.py`

```text
NAME = "codex"; EXE_NAMES = ("codex.exe", "codex.cmd", "codex"); TIERS = tuple(claude_cli.MODELS)
CAPS = False; INTERRUPT = False; RESUME = True; HOOKS = False
EFFORT = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}

find_exe(cfg) -> str | None            harness.which(EXE_NAMES, harness.section(cfg, NAME).get("exe", ""))
version_command(exe) -> list           exe + ["--version"]
run_command(exe, model, effort, cwd, session_id, *, prompt, resume=False, fork="", read_only=False, budget=0.0,
            max_turns=0, name="") -> (list, bytes)
    cmd = exe + ["exec", "--json", "-C", cwd, "--skip-git-repo-check", "-m", model,
                 "-c", f'model_reasoning_effort="{EFFORT[effort]}"',
                 "-s", "read-only" if read_only else "workspace-write"]
    if fork:   cmd += ["fork", fork]          elif resume: cmd += ["resume", session_id]
    cmd += ["-"]
    return cmd, (prompt + claude_cli.STOP_FOOTER).encode("utf-8")
env(read_only) -> dict                 {}
```

- Options stand before `resume` / `fork`, as the help's `codex exec [OPTIONS] <COMMAND> [ARGS]` shows. Whether
  `exec resume` honours `-s` and `-m` given that way, or keeps the first run's, is Task 7 item 3's second run.
- `-s workspace-write` keeps `.git` read-only inside the folder (Codex's sandbox protects it, per its sandboxing
  docs): a Codex step edits files but cannot commit. Nothing in the chain asks a step to commit
  (`claude_cli.git_changed` counts uncommitted files), so nothing changes; Task 7 notes it if a step tries.

- `budget`, `max_turns`, `name` are accepted and ignored (no flag; README decision 7: `step_timeout_s` is the cap).
- `-` is last: the prompt is read from stdin; `runs` closes stdin after writing it (Task 4), which is what
  `codex exec -` waits for.
- `resume` uses `session_id` as given: `runs` passes the meta's `harness_session` (the thread id from the first
  run) in that slot (Task 4). `fork` likewise takes the thread id to copy.

```text
is_result(line) -> bool                line.get("type") in ("turn.completed", "turn.failed")
summary(lines) -> dict
    final: the text of the last `item.completed` whose item.type == "agent_message" (item.text, else the longest
           string value of item); "" when none
    subtype: "success" after turn.completed, "error" after turn.failed or an `error` event with no turn.completed
             after it, "" when neither
    cost: None (Codex reports tokens, not USD; plan 18 prices them)
    tokens: from the last turn.completed usage: {"input": input_tokens - cached_input_tokens,
            "output": output_tokens, "cache_read": cached_input_tokens, "context": None} or None
            (input_tokens includes the cached ones; the usage is the turn's spend over all its calls, so it
            gives no context size: README 3.4)
    session_id: thread.started thread_id, else ""
    denials: []
    exit_cap: False
chat(lines, cwd) -> list
    one {"role": "claude", "text"} per agent_message item (clipped at runs.CHAT_TEXT), one {"role": "tool",
    "text": f"{item.type} {summary}"} per other item.completed (command_execution: the command; file_change: the
    paths; mcp_tool_call: the tool name; web_search: the query), {"role": "note"} for `error`, and a final
    {"role": "result", "text": "success · N turns"} or "error ..." from turn.completed / turn.failed; the
    cc_prompt lines the service wrote become {"role": "you"} as in runs.chat
stop(proc) -> str                      claude_cli.kill_tree(proc.pid); "kill"
terminal_command(exe, session_id, model, effort) -> None
```

Field names inside items (`item.text`, `command`, `changes`) are from the docs; `summary` reads them defensively
(`.get` with the longest-string fallback), and Task 7 pins the real shapes from a recorded run into
`tests/fixtures/codex-run.jsonl` and a test that reads it.

## `tests/fake_codex.py`

A Python script the tests run as `[sys.executable, "tests/fake_codex.py"]` (as `fake_claude.py` is). It parses
`exec`, then the options `--json`, `-C`, `-m`, `-c`, `-s`, `--skip-git-repo-check`, then `resume <id>` or
`fork <id>`, then `-`; an option after `resume` / `fork` exits 2 (pins the order); reads the prompt on stdin; prints:

```text
{"type": "thread.started", "thread_id": "th_fake"}
{"type": "turn.started"}
{"type": "item.completed", "item": {"type": "command_execution", "command": "py -m unittest", "exit_code": 0}}
{"type": "item.completed", "item": {"type": "agent_message", "text": "<echo of the prompt's first line> ... HANDOFF block when 'HANDOFF-OK' is in the prompt"}}
{"type": "turn.completed", "usage": {"input_tokens": 2000, "cached_input_tokens": 800, "output_tokens": 300, "reasoning_output_tokens": 100}}
```

Words in the prompt: `HANDOFF-OK` (a valid six-heading block at the end of the message, as `fake_claude` does
after plan 23; until plan 23 the four-heading block), `FAIL` (a `turn.failed` line instead of `turn.completed`),
`SLOW` (sleeps 3 s before the agent_message, for the timeout test of Task 4), `STOP-ASK` (`STOP: which file?`
as the last line). `--version` prints `codex-cli 0.0.0-fake`.

## Tests (`CodexTest`)

- `test_command_shape`: `run_command([..], "gpt-6.1-sol", "xhigh", "D:/p", "sid", prompt="hi")` gives a list that starts with `exec`, contains `--json`, `-C D:/p`, `-m gpt-6.1-sol`, `-c model_reasoning_effort="high"`, `-s workspace-write`, ends with `-`; stdin bytes end with the STOP footer; `read_only=True` gives `-s read-only`; `resume=True` gives `... resume sid -` as the last three items, every option before them; `fork="th"` gives `... fork th -`.
- `test_summary_from_documented_lines`: the five fake lines above give `final` = the agent text, `subtype == "success"`, `tokens == {"input": 1200, "output": 300, "cache_read": 800, "context": None}`, `session_id == "th_fake"`, `cost is None`; with `turn.failed` instead, `subtype == "error"`.
- `test_chat_items`: the same lines give roles `[tool, claude, result]` in order; the tool text starts with `command_execution`.
- `test_fake_runs_end_to_end`: `subprocess.run` the fake with `exec --json -` and a prompt on stdin: stdout parses line by line, the last line `is_result`, `summary` matches; `--version` prints `codex-cli`; a resume command from `run_command` runs (no exit 2).
- `test_tiers_and_flags`: `TIERS == tuple(claude_cli.MODELS)`, `CAPS is False`, `INTERRUPT is False`, `RESUME is True`, `HOOKS is False`; `harness.get("codex").NAME == "codex"`.

## Steps

1. Write the five tests; run: ImportError / KeyError.
2. Write the fake, then the adapter; run until green.
3. Whole suite: 338 + 5 = 343.
4. Commit: `feat: Codex adapter and fake (plan 05 Task 2)`.

## Drift guards

- No `--full-auto` (deprecated), no `--dangerously-bypass-approvals-and-sandbox` or `--approve-for-me` ever, no `--ephemeral` (a step may resume), no `--worktree`.
- The adapter writes no file; `-o` is not used (the final message is read from the stream).
- The STOP footer is added here for Codex (Claude's is added in its adapter too): every harness gets it.
