# Task 7: live check and close

> Fred's task: real turns cost money. Needs Tasks 1 to 6 merged and the service restarted by Fred.

## 7.1 Live check (Fred, with the agent watching the files)

1. **One scratch turn first.** `chat_day_usd` 0.50 for the first session. Ask "what needs me?" Expect: `overview`
   read, a short answer naming tasks by title, the turn's cost in the thread and in Usage. Record: seconds, cost,
   tool calls, the context tokens (`thread.json` `tokens`).
2. **Effort.** Five turns at `medium` (the default), then five at `low` (`superchat.EFFORT` changed on a branch, not
   in config): the same questions. Keep `low` only if every answer names the right task and press; record both.
3. **Presses.** One of each: a retry on a named model, an add step, a hand off saved as a document, a reopen with
   words, a Pause then its Undo. Each shows one `act`/`acted` pair in `super.jsonl` and one thread line.
4. **Always yours.** Ask it to stop a task: a Confirm card, nothing pressed until the click; a Fable confirm the
   same. A card changed in the window before the click shows Out of date.
5. **Dictation.** Say "end of this task" by voice: the reply reads it as Hand off, or asks.
6. **Stop and limits.** Stop a long answer: the partial reply stays. Raise the day limit back to 3.00.
7. **Background acts** (Task 5): one project at `auto` for a day; read every `act` and `act_refused` line, and each
   lifted press against README 3.6 (an `act` line with `lift`; a super Approve, `by` `super` in the task's
   `supervisor.jsonl`); Fred decides whether a second project goes to `auto`.
8. **A day by talking.** One working day clearing For you mostly through the chat. Record: turns, cost per turn
   (median, p90), cost per day, presses, Confirm cards, refusals, and what Fred still clicked by hand and why.

Findings go to the plan's History and, for anything to fix, to a numbered list here before any code.

## 7.2 Close

- `CLAUDE.md`: one rule line (stage only that hunk): "Plan 61: the super agent acts only through `Hub.super_act` (the
  card's served actions and gates; an always-yours list in `console/superact.py` needs Fred's click on a Confirm
  card); the chat is one `claude -p` per message on a resumed session with only Console's MCP tools (`POST /api/mcp`,
  a Bearer token per turn); its files are `~/.claude/console/super/chat/`; background acts only at `auto`, within
  `super_acts_day` and `super_acts_task_hour`; a pass's Approve (`_supervisor_dispatch` by `super`) never resets
  Fred's window and buys one step (README 3.6)."
- `PLAN.md`: row 61's status to built, with the live numbers (stage only that hunk).
- `BRAINSTORM.md`: D19's line gains "built (plan 61)" (stage only that hunk).
- This README's History: the build commits and the live numbers.
