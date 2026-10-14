# Task 6: Fred's live check

> Claude never starts a run, never POSTs `/api/run`, `/api/task` or `/api/prep`, and never edits
> `~/.claude/console/config.json` for Fred. Fred runs this after Task 5 is placed and the tray's service restarted,
> in a real project (CONTENT MANAGER, or this repo on a scratch branch). Codex or OpenCode on (plan 5's Harnesses
> card) for items 4 and 5.

## 6.1 Allowances and the fills

1. In config.json, `allowances` for the models Fred uses (USD per day, week, month; his plan's real limits, or a
   share of them), for example `{"opus": {"day_usd": 12, "week_usd": 60, "month_usd": 200}, "sonnet": {...},
   "haiku": {...}}`. Restart the service. Expected: the Usage page's `Models · share of pace` lists each key with its
   binding window's bar, the outlined pace cell, and `w ..` / `m ..` for the other two; a click opens the three
   windows. A model with no entry shows a dotted bar and `no allowance`.
2. Compare one row with the day's figures on the same page: `day` used = that family's cost of today; `week` from
   Monday; `month` from `month_start_day`. Note any gap.

## 6.2 The spread

3. Run two tasks of `scout, code, verify` back to back (small requests). Expected: each step's route line ends with a
   `balance:` note naming the shares (`balance: sonnet 31 %` or `balance: sonnet 84 % -> codex:gpt-6.1-sol 22 %`);
   the second task's first step keeps the previous rung while its share is within 10 points (the note's
   `previous rung kept`); the verify runs one rank above the step it checks and never on opencode or cmd.
4. With Codex on and a price row for its model in `prices` (`"gpt-6.1-sol": {"input": ..., "output": ...,
   "cache_read": ...}` per million tokens, from OpenAI's price page): a write step that runs on Codex adds its cost to
   that key's row after the run ends (`via codex`), and a restart of the service does not count it twice.
5. Without a price row (remove it, restart): the next Codex run shows `cost unknown · 1 run` on the Usage row and on
   the day, and the row has no share (D3 a). Put the row back.

## 6.3 Over pace and the hold

6. Set one allowance low (a `day_usd` under today's spend of that model). Expected: the today strip shows
   `1 model over pace · fills`; it opens the breakdown with `fills · opus 140 % of pace` and `Usage ›`; the Usage row
   is orange. A design step of a new task still runs on its tier (no step moves); a code step's verify on that model
   waits `opus over its pace` with Run anyway (Confirm). Put the allowance back.
7. A hard request (Prep shows `reasoning high`) with `fable` the emptiest think model: the design step waits
   `confirm Fable`.

## 6.4 The evidence

8. After a week of tasks: the Verify FAIL by hour fold names the hour with most FAILs per model; note whether one
   provider's FAILs gather in its peak hours (the case for `peak_hours`, still off).

## 6.5 Record

- Each item: what was expected, what was seen, the task id. Findings become fixes in a later plan (as plan 19 did for
  plan 17) or small commits on this branch when they are one-liners.
- The allowances Fred settled on, for the README's D2 and plan 26's Tiers tab defaults.
