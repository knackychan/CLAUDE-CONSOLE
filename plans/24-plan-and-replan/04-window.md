# Task 4: The window: the Plan row, the askboxes, `from plan`, the list card, the tuning row

> Contract: [README.md](README.md) 3.7 (what `GET /api/task` and `task_row` carry). Design: interface doc section 7
> (Task page: Replan wait, Plan, the askboxes) and 8.3 (the Plan tab is plan 25's, the Board). Mock:
> `design/rework/locked/cells-board.html`, views `Task · sub-plans` (`taskPageHtml("tplan")`), `Task · plan hold`
> (`taskPageHtml("thold")`), the task page's Plan row (`taskPageHtml("tpage")`), the list card for task D
> (`listHtml`), and the functions `planSection`, `stepBody`, `partRow`, `planHtml` for the row's open body. Depends on
> Task 3.

**Files**
- Modify: `web/app.js` (`drawTask`, `chainRow`, `taskCard`, `taskAct`, the Models page's Tuning rows when plan 26 is
  placed; else the Settings popover is untouched), `web/style.css` (tokens first: the mock's `.tg`, `.parts`, `.prt`,
  `.hsec .lbl.s`, `.hsec ol`, `.askbox .edbox` rules), `web/index.html` (nothing: the Task page is drawn)
- Modify: `tests/test_server.py` (one test that `GET /api/task` carries `plan`, `parts` and the step's `part`: a
  window contract test, if Task 3 did not add it)

## 4.1 The Plan row (`drawTask`, after `chain`, before `brief`)

- Drawn only when `t.plan` is set (`task_row.plan`). Folded block in the `.blk` language of the handoff fold (plan 19
  Task 5): closed line `Plan · from 02 design · 2,140 w · never cut ▾` for a single plan, `Plan · from 02 design · 3
  sub-plans · 4,870 w ▾` for a split one; `words` from `t.plan.words` with a thousands separator, `from` two digits.
- Open, single plan: the six headings of `d.plan` (the index text) as folded sections (`.hsec`), the current step's
  `### Step N` section open and marked `this step`, the others closed; the mock's `planSection` / `stepBody` render
  the Steps section by step (Files as a list, Actions as an ordered list, code in `pre.text`, Tests as a list, Done
  check as a line). Headings are split on `## ` and `### Step N:` lines in the browser (`planSections(text)` in
  app.js, 15 lines; no Markdown library).
- Open, split plan: the index's Goal, Decisions, Out of scope, Acceptance folded as above, then the parts list
  (`.parts`, one `.prt` row per `t.plan.parts[]`: `1 Harness module · 03 code · done`, the state word from the step the
  part is on (`t.steps.find(s => s.part === p.n)`), `hard` as a muted tag, the current part's row open with its
  sub-plan text from `d.parts[p.n]` rendered as a step body).
- The row's open state is kept while the page is open (`planOpen`, like `rawOpen`), closed on `openTask`.
- `chainRow`: a step with `s.part` gets `<span class="tg">from plan</span>` after the kind (the mock's `.tg`, muted);
  a waiting row shows `t.why` in orange when the task waits on a plan wait and the row is the current step.

## 4.2 The askboxes (`drawTask`, the `why` block)

The existing `ask || hand` branch stays for a plain question; before it, four plan cases on `t.state === "waiting"`
and `t.why`:

| `t.why` | Head | Body | Buttons (left to right) | Say line |
|---|---|---|---|---|
| starts `asks: Plan gap:` | `Plan gap · step 04 stopped, nothing chosen` | the question (`.q`), `<textarea id="t-answer">` placeholder `Your answer joins the plan's Decisions and continues step 04.` | `Send answer` (you, `data-tact="gapanswer"`), `Redo design` (`data-tact="redo"`), `Open step 4` | `A writer never decides for the plan: your answer is written under Decisions as "Fred, <date>: ...".` |
| `plan ready: confirm` | `Plan ready · 3 sub-plans · 4,870 w` (or `· 2,140 w`) | nothing, or on Edit the `.edbox` (a `textarea` of `d.plan` in the mono font, `Save` posting `/api/task/plan`; with parts a select of index / part k and the part's text) | `Confirm plan` (you, `confirm`), `Edit` (`data-fold="edbox"`), `Stop` | `plan_hold is on: the plan waits for you before any step runs.` |
| starts `plan ` and has ` KB, over ` | `Plan is large · 132 KB` | `t.why` | `Accept` (you, `confirm`), `Redo design` (`redo`), `Stop` | `Nothing is cut: the whole plan goes to every later step.` |
| starts `replanned:` | `Replanned · after step 01` | the `replan_note`'s why line, then two lists from `t.replan.before` and `t.replan.after` (the task row carries `replan` only if Task 3 added it to `task_row`; else read `d.task.replan`), added steps marked with `.tg.n`, dropped struck | `Confirm plan` (you, `confirm`), `Keep old plan` (`keep`), `Stop` | `replan_auto is off: a changed plan waits for you.` |

`taskAct` (the `data-tact` handler): `gapanswer` posts `POST /api/task/answer {task, text}` (409 shows the error in
`#ta-msg`, 200 opens nothing: the task row goes running and the page redraws); `redo` and `keep` post the lever
route like `confirm`; `confirm`'s label comes from the case (`Confirm plan`, `Accept`, `Run anyway`, `Confirm to use
...`): compute `confirmLabel(t, row)` once and use it in both the askbox and the bar.

Stuck after a bad plan (`t.state === "stuck"`, current step is the design step): the stuck askbox gains
`Redo design` next to Retry (levers `redo === ""`).

## 4.3 The list card (`taskCard`)

When `t.asks` starts with `Plan gap:`: the card's third line reads the question as today, the buttons `Answer`
(opens the Task page, `data-task`) and `Redo design` (`data-tact="redo" data-tid`); the muted line under the title
reads `step 4 of 8 · code · from plan` when the step has `part`. A `plan ready: confirm` or `plan N KB, over M` why
shows as the why line with `Confirm` / `Accept` opening the Task page (one click, like `confirm Fable` today).

## 4.4 The tuning row (plan 26's Models page; until it is placed, config.json only)

`Turns on design` reads `design_max_turns` (D2 a) in the Tuning tab's Tasks group, next to `Steps at most`; the
mock's Models view carries the row. With D2 (b) the row reads `opus_max_turns` as `Turns on design (opus)`.

## 4.5 Steps, in order

1. `style.css`: the tokens and rules from the mock (`.tg`, `.tg.n`, `.tg.w`, `.parts`, `.prt` grid, `.hsec .lbl.s`,
   `.hsec ol`, `.askbox .edbox`, `.askbox .edbox textarea` in the mono font), under the Task page section.
2. `app.js`: `planSections`, `planRowHtml(t, d)`, the four askbox cases, `chainRow`'s tag, `taskCard`'s buttons,
   `taskAct`'s `gapanswer`, `redo`, `keep`; `confirmLabel`.
3. `node --check web/app.js`; the full suite; headless Edge at 400 and 340 px on the fake runs of Task 3 (the
   `PLAN-OK`, `PLAN-SPLIT`, `PLAN-GAP`, `REPLAN` tasks and `plan_hold` on): the Plan row closed and open, the parts
   list, each askbox, Send answer, Redo design, Confirm plan, Keep old plan, Edit and Save; no console errors, no
   horizontal overflow at 340 px (the closed line stays one line: shorten with `·` figures, never wrap the buttons).
4. Commit `plan 24 task 4: window: Plan row, plan askboxes, from plan, list card`.

## 4.6 Drift guards

- No new visual for word counts (ID-5): the figure is text in the closed line and the chip.
- Orange (`--you`) only on the one button that answers the wait; `Redo design`, `Keep old plan` and `Edit` are plain.
- The plan text is rendered by splitting on headings; code blocks go in `pre.text` as written, never re-flowed.
- The window never writes the plan but through `POST /api/task/plan`; Save is off while a step runs (the route says
  so with 409 and `#ta-msg` shows it).
