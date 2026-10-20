# Task 2: the supervisor as the exception handler, and the two bugs (change B, D6 a)

Files: `console/server.py` (`_sup_mode` :2137, `_supervisor_fred` :2074, `task_row` `paused_after` :3956),
`console/supervisor.py` (`AUTO_KINDS`, `auto_reason`, `pass_model`, `check`), `dotclaude/console/kinds/supervisor.md`,
`web/app.js:3814` (one condition;
the UI chat may take it instead: say so in the commit), `tests/test_supervisor.py`, `tests/test_supervisor_server.py`,
`tests/test_web.py`.
Line numbers checked at `1d6e279` (README section 6); both bugs are still in the code there.
Two commits: `fix: a mode switch at a boundary dispatches or re-wakes; no Paused note at a supervised boundary
(plan 52 Task 2a)` then `feat: the supervisor wakes on exceptions only (plan 52 Task 2b)`.

## 2a: the bugs

1. `Hub._sup_mode(task, mode)`: after `sup["mode"] = mode`, call `self._supervisor_fred(task, now, "mode",
   keep=pending)` where `pending = sup.get("pending") if its status is "suggest" or "held" else None`: the standing
   suggestion is NOT superseded by a mode change. After the commit:
   - `mode in ("auto", "gated")` and `pending`: `self._sup_auto(task["id"], pending["wake"])` (its live rechecks
     refuse a stale card as today; `gated` is treated by `auto_reason` as Task 5 says).
   - no pending and `supervisor.boundary(task, chain)` is not None: `self.wake_supervisor(task, found["trigger"],
     line)` with `line` = the mode-change chain line just written (a fresh event id; the original boundary event
     was consumed by the earlier wake). `mode == "off"`: as today (wakes dropped, pending cleared).
2. `task_row`: `paused_after` is `0` when `sup.get("paused") is not True and tasks.manual_boundary(t)` (a supervised
   boundary that is not paused). `web/app.js:3814` (today `row.paused_after && lv.resume !== "choose a next step or
   finish the task"`): the note shows only when `lv.resume === ""` (really paused).

Tests: `tests/test_supervisor_server.py::test_mode_switch_to_auto_dispatches_the_standing_suggestion` (suggest
card, POST mode auto: one `request_next`, chain `dispatched add_next_step ... by auto`),
`test_mode_switch_with_no_card_rewakes_once` (card rejected earlier, POST mode auto: one new wake, one pass, none
on a second POST of the same mode), `tests/test_server.py::test_paused_after_is_zero_at_a_supervised_boundary`,
`tests/test_web.py::test_no_paused_note_unless_resume_is_open`.

## 2b: exceptions only

1. `supervisor.boundary`: the `choose_next` and `fail` triggers stay for manual tasks (plan 36). Nothing to change
   for chain tasks: their steps never produce a manual boundary after Task 1.
2. `supervisor.pass_model(settings, triggers)`: unchanged (sonnet on stuck/stalled, haiku elsewhere).
3. `dotclaude/console/kinds/supervisor.md`: the bullet list of moves is rewritten for the exception role:
   - stuck after the chain's own retry: `retry` with a note naming the exact failure from the stuck attempt's tail
     when the digest shows a concrete, different cause to try; else `escalate_to_fred` with both failures in
     `for_fred`;
   - `verify failed twice`: `escalate_to_fred` with the two VERDICT lines, never a code step;
   - a plan hold (`plan ready: confirm`, `plan N KB, over M`, `replanned:`): `confirm` when the plan's Decisions hold
     no question and the steps fit the goal; `keep` when the replan drops a step the goal needs; `escalate_to_fred`
     otherwise;
   - a stalled step: `stop`, for $you to approve;
   - `done`: `finish` when the last verify PASSed and no Open question remains; `add_next_step` only for one
     concrete missing check named in the last handoff's Next; else `wait`;
   - a next-step request from $you: as today (plan 48), keeping plan 51's sentence word for word: "When $you's
     words name haiku, sonnet or opus, return that word as model; otherwise model auto.";
   - never answer a question, never release a Fable or pace hold.
   The paragraph "a design step whose plan is saved: add the first write step" goes: the chain runs the plan. So
   does plan 49's bullet "when the digest lists Planned next: take the first planned step ..." (D7: the digest no
   longer has that list, Task 1 change 6).
4. `supervisor.check`: unchanged. `AUTO_KINDS` unchanged.
5. `Hub._ended`: no change; `_sup_hook` already fires on `manual`, `stuck`, `wait` (holds) and `done`.

Tests: `tests/test_supervisor.py::test_kind_file_names_the_exception_moves` (the seed `supervisor.md` contains
"verify failed twice", "escalate_to_fred" and plan 51's "return that word as model", and neither "first write
step" nor "Planned next"); `tests/test_supervisor_server.py::
test_chain_task_wakes_only_on_stuck_hold_and_done` (a four-step chain with the fake: PASS all the way gives one
wake (done); a crash on step 02 gives the chain retry, then a second crash gives one `stuck` wake on sonnet).
