# Task 7: Fred's live check, then close

## Fred's steps

1. `py install_hooks.py --harness codex,cmd,opencode` (dry run), read it, then `--write`. Then
   `opencode service restart`: OpenCode's chats run in its background server, which loads plugins when it starts
   (the window runs use `--standalone`, a private server that loads the plugin itself and inherits
   `CC_CONSOLE_SID`). The OpenCode loader was already checked on 2026-10-15 (README 5): the step only confirms
   `msg="loading plugin" id=...\plugins\claude-console` in `~/.local/share/opencode/log/opencode.log`.
2. Trust: run `codex` in a terminal, `/hooks`, trust the `cc_events.py` entries. Run `cmdc` once and accept the
   hooks if it asks (record what it asked, or that it asked nothing).
3. Restart the service (`py -m console`).
4. One chat per CLI, each with one prompt that reads a file and edits one line:
   - Codex in VS Code, and `codex` in a terminal;
   - `cmdc` in a terminal;
   - `opencode` in a terminal, with one `task` subagent.
5. For each: the row shows under its project with the harness chip, title, Steps, Running then Replied, the gauge,
   the source (vscode / terminal). Open Chat: the turns read. Interrupt a Codex turn (Esc): Interrupted.
6. One window run on each harness (Run with a `codex:` / `opencode:` / `cmd:` rung): one row, Steps from the hooks.
7. On an outside Codex chat: Verify (a fork, a VERDICT), then Escalate or Handoff.

## Claude's steps, from the events files of the check

- Record the real tool names and input keys of each CLI (`"tool"` and `"what"` in
  `events-<day>.jsonl`); correct README 3.3 and `TOOL_MAP` rows where they differ (table edits only).
- Record whether Codex sends `agent_id` on a subagent's PreToolUse, whether `CC_CONSOLE_SID` reached each CLI's
  hook, and what Command Code asked for trust; add them to README section 5.
- `hook-errors.log` has no new lines.

## Close

- PLAN.md: the plan 37 row's state; a Log line with what differed.
- CLAUDE.md: the hook rule reads "runs inside every Claude Code, Codex, Command Code and OpenCode session"; the
  settings rule names the other CLIs' config files (`install_hooks.py` only, run by Fred).
- BRAINSTORM: the harness slot line (section 4) says every CLI is watched by the same hook.
- Plan 05 README decision 10: a line saying plan 37 replaced it.
