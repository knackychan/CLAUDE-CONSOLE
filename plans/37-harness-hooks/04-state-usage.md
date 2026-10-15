# Task 4: State and usage take the other CLIs

Contract: README 3.1, 3.4, 3.5, 3.7. Files: `console/state.py`, `console/server.py`, `tests/test_state.py`,
`tests/test_server.py`.

## State (console/state.py)

- `SOURCES` gains `"vscode": "vscode"`, `"interactive": "terminal"`, `"print": "terminal"`, `"exec": "terminal"`
  (`"cli"` is already `terminal`).
- In the record intake, before the event switch: `if rec.get("harness") and not s.window: s.harness =
  rec["harness"]` (a window run's harness stays the one `run_started` set).
- `SessionStart` and `Stop`: `entrypoint` sets `s.source` as `Stop` does today (Codex sends it on Stop only through
  the tail; OpenCode on SessionStart).
- `Stop` with `rec["prompt"]` (Command Code, README 3.2): when the turn has no prompt yet, it counts as the turn's
  prompt: `s.prompts += 1` once per turn and the title is set from it like `UserPromptSubmit` does. The turn itself
  opened at the first `PreToolUse` (existing code) or, with no tool call, opens and closes on this Stop.
- New event `Interrupt`: `s.in_turn = False`, `s.doing = ""`, `_turn_close`, `s.interrupted = True` (state
  `interrupted`, Needs you, as for a window run Fred stopped). The next `UserPromptSubmit` clears it (existing).
- `Stop` keeps `rec["tokens"]` on the session as `s.turn_tokens` (dict or None) for the service (below).
- The `usage.Usage` cost poll reads `transcript_path` of Claude sessions only (`s.harness == "claude"`): a Codex or
  Command Code transcript is not Claude's format.

## Service (console/server.py)

- `poll_once`: after the `run_ended` loop, a `Stop` record with `harness` other than `claude` whose session is not a
  window run goes to `count_turn(rec)`.
- `count_turn(rec) -> bool`: `key = fills.model_key(f"{rec['harness']}:{rec['model']}", self.cfg)`; `cost =
  fills.price(rec.get("tokens"), prices.get(key))`; `usage.add_other(self.folder, f"{sid}@{ts}", day, key,
  rec.get("tokens"), cost)` under `_count_lock`, then `usage_other` and `version` as `count_run` does. No `model`:
  return False. The `@ts` id makes a restart's replay count once (`seen`).
- `Hub.session` rows already carry `harness` (line 506); nothing else changes there.

## Tests

- `test_state.py`: `test_codex_hook_session_has_harness_and_source` (SessionStart + UserPromptSubmit + PreToolUse +
  Stop with `harness: codex`, `entrypoint: vscode` -> row harness codex, source vscode, one step, Replied);
  `test_cmd_stop_brings_prompt_and_title` (PreToolUse then Stop with `prompt` -> prompts 1, title set);
  `test_cmd_stop_without_tools_opens_and_closes_a_turn`; `test_interrupt_needs_you`;
  `test_window_run_keeps_its_harness` (run_started codex, then a hook record with `harness: codex` and the console
  sid -> one row, window, steps from the hook); `test_usage_poll_skips_other_harness_transcripts`.
- `test_server.py`: `test_outside_codex_stop_counts_turn_tokens` (one Stop with tokens -> usage-days.json `other`
  row for the codex key, runs 1; the same line replayed -> still 1); `test_window_run_stop_not_counted`.

## Steps

1. Tests first; they fail.
2. State changes, then `count_turn`.
3. Run all tests; commit `plan 37 task 4: State and usage take the other CLIs`.

## Drift guards

- A Claude record with no `harness` key sets nothing new.
- Window runs are still counted from `run_ended` only.
