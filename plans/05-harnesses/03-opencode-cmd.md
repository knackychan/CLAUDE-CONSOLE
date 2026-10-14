# Task 3: the OpenCode and Command Code adapters and their fakes

> Contract: [README.md](README.md) 3.3, 3.4 (the two right columns). Depends on Task 1. Facts: `opencode run --help`
> and `cmdc --help` (Command Code 1.81.0) pasted by Fred on 2026-10-13 (the design doc, section 3).

**Files**
- Create: `console/harness/opencode.py`, `console/harness/cmd.py`
- Create: `tests/fake_opencode.py`, `tests/fake_cmd.py`
- Modify: `tests/test_harness.py` (classes `OpenCodeTest`, `CmdTest`)

## `console/harness/opencode.py`

```text
NAME = "opencode"; EXE_NAMES = ("opencode.exe", "opencode.cmd", "opencode"); TIERS = ("haiku",)
CAPS = False; INTERRUPT = False; RESUME = True; HOOKS = False

run_command(exe, model, effort, cwd, session_id, *, prompt, resume=False, fork="", read_only=False, budget=0.0,
            max_turns=0, name="", variants=None, prompt_file="") -> (list, None)
    variant = (variants or {}).get(effort, "")          variants = cfg["effort_variant"].get(model) (runs passes it)
    m = model + ("#" + variant if variant else "")
    cmd = exe + ["run", "--standalone", "--format", "json", "--auto", "-m", m, "--file", prompt_file]
    if name: cmd += ["--title", name]
    if fork: cmd += ["--session", fork, "--fork"]      elif resume: cmd += ["--session", session_id]
    cmd += [MESSAGE]                                   MESSAGE = "Do the task in the attached file."
    return cmd, None
env(read_only) -> dict
    {"OPENCODE_DISABLE_AUTOUPDATE": "1"} plus, when read_only,
    {"OPENCODE_PERMISSION": json.dumps({"edit": "deny", "bash": "deny", "webfetch": "deny"})}
```

- The prompt (with the STOP footer) is in `prompt_file`, which `runs.start` writes as `runs/<sid>.prompt.md`
  before the spawn (Task 4); argv carries one fixed sentence. No stdin flag in this version, and an argv prompt
  through the npm `opencode.cmd` shim is re-parsed by `cmd.exe` (README 3.3, Shims). `prompt_file` empty raises
  `ValueError` (a programming error, never a run).
- `read_only` has no flag: `env` sets `OPENCODE_PERMISSION` (on the opencode.ai CLI docs' env list) so `--auto`,
  which approves "permissions that are not explicitly denied", meets an explicit deny. Task 7 item 5 checks that
  an edit is refused; if the variable's JSON shape differs, the step prompt's no-edit rule is the only guard and
  the History says so. Nothing is written to OpenCode's own config.
- `OPENCODE_DISABLE_AUTOUPDATE=1` on every run and on the probe: OpenCode updates itself as Command Code does.
- `--standalone`: a private server per run, so a step never depends on OpenCode's background service.
- cwd: the process cwd (no `--dir` on this version).

```text
is_result(line) -> bool      a line whose type names a session or message end: any of ("session.idle",
                             "message.completed", "done", "result") or whose "type" ends with ".idle"
                             (unknown shape: the live check pins it; until then the process exit ends the run)
summary(lines) -> dict       final: the longest text of the last line that has a string "text" (nested one level
                             under "part" or "message" too); subtype "success" when the process exited 0 (runs passes
                             the exit code as a trailing {"type": "cc_exit", "code": n} line it writes itself), else
                             "error"; cost None; tokens: {"input", "output", "cache_read", "context"} from a line with
                             a "tokens" dict holding input / output / cache.read keys, else None; session_id: the
                             first line's "sessionID" or "session_id" string, else ""; denials []; exit_cap False
chat(lines, cwd) -> list     one claude item per text part, one tool item per line with a "tool" string (text:
                             the tool name and its "title" or input summary), a result item from cc_exit
stop(proc) -> str            kill_tree; "kill"
terminal_command(...) -> None
```

## `console/harness/cmd.py`

```text
NAME = "cmd"; EXE_NAMES = ("cmdc.exe", "cmdc", "cmdc.cmd")   never "cmd" or "cmd.cmd": `cmd` is Windows' shell
TIERS = ("haiku",); CAPS = True; INTERRUPT = False; RESUME = True; HOOKS = False
EFFORT = codex.EFFORT (same map)

run_command(exe, model, effort, cwd, session_id, *, prompt, resume=False, fork="", read_only=False, budget=0.0,
            max_turns=0, name="") -> (list, None)
    cmd = exe + ["-p", prompt + claude_cli.STOP_FOOTER, "--output-format", "json", "--no-auto-update",
                 "--skip-onboarding", "--no-skills", "-m", model, "--effort", EFFORT[effort],
                 "--permission-mode", "plan" if read_only else "accept-edits"]
    if max_turns: cmd += ["--max-turns", str(int(max_turns))]
    if name: cmd += ["-n", name]
    if fork: cmd += ["-r", fork, "--fork-session"]      elif resume: cmd += ["--session", session_id]
    return cmd, None
    a `.cmd` / `.bat` exe[0] raises ValueError with the README 3.3 message (Shims): the query is in argv;
    `runs.start` turns it into RunError (adapters do not import `runs`)
version_command(exe) -> list   exe + ["--no-auto-update", "-v"]
env(read_only) -> dict         {}
```

- `accept-edits` accepts file edits; whether shell commands still prompt in `-p` mode is for the live check (Task 7
  item 3): if they do, a `test` or `code` step on cmd cannot run its checks, and the rule becomes `--yolo` for
  those kinds only, with Fred's word first. The plan does not pick `--yolo` by default.
- `-p` with the query as its argument: never through a shim; `runs` refuses a prompt over 30 000 characters for
  it (the Windows command line is 32 767). Whether `-p` with no query reads stdin is Task 7 item 4; if it does, the
  adapter moves the prompt to stdin and both refusals go.
- `--permission-mode plan` on read-only steps may end the turn on a plan instead of the findings (README 3.4);
  Task 7 item 4 checks a scout on it.

```text
is_result(line) -> bool      the final result line: a line with "type" == "result" or with a top-level "result"
                             key and no "event" key (unknown shape: pinned at the live check)
summary(lines) -> dict       final: the result line's longest string value, else the last text of an assistant
                             event; subtype: "success" on exit 0, "error_max_turns" on cc_exit code 8, else "error";
                             cost None; tokens from a "usage" dict when present (same keys as Codex when they exist);
                             session_id: a "session_id" or "sessionId" string anywhere in the first lines, else "";
                             exit_cap: cc_exit code == 8
chat / stop / terminal_command as OpenCode's (terminal: None)
```

## The fakes

`tests/fake_opencode.py`: parses `run`, `--format json`, `-m`, `--session`, `--fork`, `--title`, takes the message
as the last argument and the prompt from the `--file` path (exit 2 when `--file` is missing); prints `{"type": "session.created", "sessionID": "oc_fake"}`, one
`{"type": "tool", "tool": "read", "title": "calc.py"}`, one `{"type": "text", "part": {"text": "<echo> ..."}}`, then
`{"type": "session.idle"}`. Words: `HANDOFF-OK`, `SLOW`, `STOP-ASK` as `fake_codex`; `FAIL` exits 1 after the text.
`--version` prints `0.0.0-fake`.

`tests/fake_cmd.py`: parses `-p <query>`, `--output-format json`, `-m`, `--effort`, `--max-turns`, `--permission-mode`,
`--session`, `-r`, `--fork-session`, `-n`, `-v`; prints `{"event": "start", "session_id": "cmd_fake"}`,
`{"event": "tool", "name": "read", "input": "calc.py"}`, `{"event": "assistant", "text": "<echo> ..."}`, then
`{"type": "result", "result": "<same text>", "usage": {"input_tokens": 500, "output_tokens": 100}}`. `MAXTURNS` in
the query: exits 8 after the events with no result line. `-v` prints `Command Code v0.0.0-fake`. The fake must
refuse to run when `--no-auto-update` is missing (exit 2), which pins decision 9.

## Tests

`OpenCodeTest`: `test_command_shape` (`run --standalone --format json --auto -m deepseek/x#thinking` with
`variants={"high": "thinking"}` and `effort="high"`; no `#` without a variant; `--file <prompt_file>`; the fixed
message last; no prompt text in argv; `--session id` on resume; `--session id --fork` on fork; stdin None;
`env(True)` has both variables, `env(False)` only the update one), `test_summary_defensive`
(the fake's lines plus `cc_exit 0` give the echo as `final`, `subtype success`, `session_id oc_fake`, `tokens None`;
`cc_exit 1` gives `error`), `test_chat_items` (`[tool, claude, result]`), `test_fake_end_to_end`,
`test_tiers_and_flags` (`TIERS == ("haiku",)`, `CAPS False`).

`CmdTest`: `test_command_shape` (`-p <query>` first, `--output-format json`, `--no-auto-update`,
`--skip-onboarding`, `--no-skills`, `-m`, `--effort high` for `max`, `--permission-mode plan` when read only else
`accept-edits`, `--max-turns 15` when given, `-n name`, `--session id`, `-r id --fork-session`),
`test_exe_names_never_bare_cmd` (`"cmd"`, `"cmd.exe"`, `"cmd.cmd"` not in EXE_NAMES; `run_command(["x/cmdc.cmd"], ...)` raises ValueError), `test_summary_and_cap`
(the fake's lines plus `cc_exit 0`: `final` is the result text, `tokens["input"] == 500`; `cc_exit 8` with no result
line: `subtype == "error_max_turns"`, `exit_cap True`), `test_version_command_has_no_auto_update`,
`test_fake_end_to_end` (including `MAXTURNS` -> returncode 8, and a run without `--no-auto-update` -> returncode 2),
`test_tiers_and_flags` (`TIERS == ("haiku",)`, `CAPS True`).

## Steps

1. Write the eleven tests; run: KeyError on `get("opencode")`, `get("cmd")`.
2. Write the two fakes, then the two adapters; run until green.
3. Whole suite: 343 + 11 = 354.
4. Commit: `feat: OpenCode and Command Code adapters and fakes (plan 05 Task 3)`.

## Drift guards

- `TIERS == ("haiku",)` for both (Fred: cheap models only; they may still take write steps, README decision 11); `models_of` drops anything else.
- `--yolo` appears nowhere in the code of this task.
- The console writes nothing into OpenCode's or Command Code's config folders.
- `cc_exit` is a line the service writes into the stream (Task 4), never something an adapter prints.
