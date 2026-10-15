# Task 3: install_hooks.py for every CLI

Contract: README 3.2, 3.8. Files: `install_hooks.py`, `tests/test_install_hooks.py`. Fred runs it; Claude never
runs it with `--write` or `--remove` (CLAUDE.md).

## Command line

```
py install_hooks.py [--harness claude,codex,cmd,opencode] [--write | --remove] [--python <exe>]
```

`--harness` defaults to `claude` (today's behavior, unchanged). `all` means the four. The dry run prints, per
harness, the file and what would change. `--settings` keeps meaning Claude's file; `--codex`, `--cmd`,
`--opencode-dir` override the other paths (the tests use them).

## Per harness

| Harness | File | Merge | Remove |
|---|---|---|---|
| claude | `~/.claude/settings.json` | as today | as today |
| codex | `~/.codex/hooks.json` | for each of SessionStart, UserPromptSubmit, PreToolUse, SubagentStart, SubagentStop, Stop, PostCompact, SessionEnd, Interrupt: drop our group, append `{"hooks": [codex_handler]}`; other groups kept | drop our groups, drop empty events |
| cmd | `~/.commandcode/settings.json` | SessionStart, PreToolUse, Stop the same way; `permissions` and every other key kept | same |
| opencode | `~/.config/opencode/plugins/claude-console/` (a directory: OpenCode 2.0.26 loads `<dir>/index.js` of each folder in `plugins/` with no `opencode.json` entry, README 5) | `index.js` = `hooks/opencode/claude-console.js` with `__PYTHON__` / `__SCRIPT__` replaced (`json.dumps` of the paths, so backslashes are escaped), `package.json` = `{"type": "module", "main": "index.js"}`, each backed up | delete that directory |

```python
def codex_handler(python) -> dict   # {"type": "command", "command": CMD, "commandWindows": CMD, "async": True, "timeout": 5}
def cmd_handler(python) -> dict     # {"type": "command", "command": CMD, "timeout": 5}
# CMD = f'"{python}" "{SCRIPT}" --harness <name>'
def _is_ours_cmd(group) -> bool     # SCRIPT in a handler's "command"
```

Every write: back up beside the file (`<name>.bak-<stamp>`), write through a temp file and `os.replace`, never
write a file that does not parse (print the error, exit 1). After writing Codex or Command Code, print:
`Trust the new hooks: run codex, type /hooks and trust "cc_events.py"` / `run cmdc once and accept the hooks`.

## Tests (new methods in InstallHooksTest)

- `test_codex_merge_keeps_other_hooks`: a hooks.json with the impeccable PostToolUse and Stop groups -> ours added
  to nine events, theirs untouched; twice -> unchanged.
- `test_codex_remove_takes_only_ours`.
- `test_cmd_merge_keeps_permissions`: `{"permissions": {"defaultMode": "auto-accept"}}` kept; three events added.
- `test_opencode_copy_and_remove`: `claude-console/` holds `index.js` (the two paths as JS strings, no
  `__PYTHON__`) and `package.json`; a second write keeps the content and backs up; remove deletes that directory
  and nothing else in the folder; a second remove says `nothing to remove`.
- `test_opencode_dry_run_prints_the_tree`: the directory and its two files are printed, nothing is written.
- `test_bad_json_not_overwritten`: a broken hooks.json stays byte-identical, exit 1.
- `test_default_is_claude_only`: no `--harness` touches only the Claude file.

## Steps

1. Tests first (all paths under a temp folder); they fail.
2. Write the per-harness merge / remove / copy; the dry run.
3. Run all tests; commit `plan 37 task 3: install_hooks.py for every CLI`.

## Drift guards

- No trust file is written (`~/.codex/config.toml`'s `[hooks.state]`, `~/.commandcode/trusted-hooks.json`).
- Without `--write` / `--remove` nothing is written anywhere.
