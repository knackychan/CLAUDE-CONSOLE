# Task 7: The compact Task page: the Board button, two-line finished rows, the ctx gauge line

> Contract: [README.md](README.md) 3.4 (`stepGauge`), 3.5 (the Task page head button), 3.6. Design: interface doc 7
> (the Task page: the head's `⇔ Board`, finished rows on two lines, the gauges in sight where they decide something, a
> click opens them on the other rows). Mock: `cells-board.html` function `taskPageHtml("tpage")` (its `row(s)` and
> `head`), the CSS block `/* the per-step context line (plan 25) */` (`.gg` to `.gg .cells.c30 i`) and `.chain .row
> .tries`. Depends on Task 2 (the button opens the Board) and Task 3 (`stepCtx`, `triesHtml`, `scoutHint`).
>
> Lands on: plan 23 Task 6 (the Task page's six-heading handoff fold) and plan 24 Task 4 (`chainRow`'s `from plan` tag,
> the Plan row): this task edits `chainRow` and the head in `drawTask` only; their lines stay.

**Files**
- Modify: `web/app.js` (`drawTask` head, `chainRow`, new `stepGauge(t, s)`, the click handler for `[data-grow]`,
  `openTask` scroll)
- Modify: `web/style.css` (`.gg` rules, `.chain .row.short`, `.chain .row .tries`)

## 7.1 The head button

In `drawTask`'s `.where` line, after the project and cost span:

```js
<button class="btn sm" data-go="board" title="The chain as connected cells, with the handoffs between the steps: the window widens (Esc returns)">&#8660; Board</button>
```

`go("board")` from the Task page opens the Board on this task (Task 2 2.4: `openBoard(taskId)`), Esc returns here.
At 340 px the `.where` line keeps one line: the project span ellipsizes, the button keeps its width (`flex: none`).

## 7.2 `stepGauge(t, s)` and the rows (`chainRow`)

```js
function stepGauge(t, s) {  // the step's context as 15 cells and the figure; unknown is a word (ID-3)
  const ctx = stepCtx(s), live = s.state === "running";
  const unk = s.harness && s.harness !== "claude" ? `${s.harness} reports a turn's spend, not a context size` : "no context reading for this step";
  const cells = ctx == null ? `<b class="mut" title="${esc(unk)}">unknown</b>`
    : `<span class="cells c30">${cellsHtml(ctxClasses(ctx).filter((_, k) => k % 2 === 0).map((c, k) => (live && k === 0 ? c + " live" : c)))}</span><b class="${ctx >= (cfg ? cfg.gauge[1] : 300000) ? "r" : ctx >= (cfg ? cfg.gauge[0] : 150000) ? "y" : ""}">${kTokens(ctx)}</b>`;
  const hint = scoutHint(t, s, null);
  return `<span class="gg"><span title="context reached, 1 cell = 10K">ctx ${cells}</span>${hint ? `<span>· ${hint}</span>` : ""}</span>`;
}
```

- `chainRow(t, s)`: the gauge line shows when the row is the current one, failed (`s.state === "failed"` or verdict
  `FAIL`), or its context is at or past `cfg.gauge[0]`; the other rows that ran are `.short` (two lines: the name line
  and the sub line) and carry `data-grow="<n>"`: a click on the row (not on its Open button) toggles the gauge line in
  place (`grown`, a `Set` of `"<task>:<n>"` kept while the page is open, cleared in `openTask`). Planned rows stay as
  today (no gauge, no grow).
- `triesHtml(s)` after the model in `.nm` (replacing nothing: `stepTries` links stay in the sub line).
- Cost: `?` when `s.cost == null` on a step that ran (plan 5), empty on a planned step.
- `openTask(id)`: after the first draw, the current row scrolls into view (`.row.cur` `scrollIntoView({ block:
  "nearest" })` once per `openTask`).

## 7.3 `web/style.css`

Port `.gg`, `.gg > span`, `.gg .cells`, `.gg .cells.c30`, `.gg b`, `.gg b.y`, `.gg b.r`, `.gg .cells.c30 i` and
`.chain .row .tries { margin-left: 6px; }`; add `.chain .row.short { padding-block: 5px; }` if the stylesheet has no
such rule and `.chain .row[data-grow] { cursor: pointer; }`.

## 7.4 Checks (400 x 760 and 340 x 760, the fake runs)

1. The Task page head has `⇔ Board`; click: the window (in the browser, the page) shows the Board on this task with
   the current step picked; Esc returns to the Task page.
2. The FAIL task: the failed verify and the running fix show the gauge line; the done steps are two lines; a click on
   a done row opens its gauge, a second click closes it; the Open button still opens the chat.
3. A step without `ctx_tokens` reads `ctx unknown` with its title; a running step's gauge follows the live session.
4. 340 px: no horizontal overflow, the head's `.where` on one line.

## 7.5 Steps, in order

1. `style.css` (7.3).
2. `app.js`: the head button, `stepGauge`, `chainRow`, `grown` and the `[data-grow]` click, `openTask`'s scroll.
3. `node --check web/app.js`; the full suite; the checks of 7.4.
4. Commit `plan 25 task 7: Task page: Board button, two-line rows, ctx gauge line (N tests OK)`.

Expected count: unchanged.

## 7.6 Drift guards

- One Doto figure on the Task page stays as it is; the gauges are mono figures.
- The gauge is context only; a handoff's words never get cells (ID-5).
- No second fetch: the gauge reads `d.task` and the live session row.
