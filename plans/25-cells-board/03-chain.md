# Task 3: The chain column: task rows, step blocks, connectors, the fix bracket, the empty Board

> Contract: [README.md](README.md) 3.2 (what a step carries), 3.4, 3.5 (connector chips, unknown context), 3.6 (orange
> only for Fred, context in cells, words as figures). Design: interface doc 8.1 (the chain), 8.2 (the step block: three
> lengths), 8.4 (connectors), 8.5 (the fix insert), 7 (`step N of M`), D1 and D4 of this README. Mock:
> `cells-board.html` functions `chainHtml`, `stepBlock`, `connBlock`, `triesHtml`, the views `Board · step`, `Board ·
> live`, `Board · empty`, and the CSS blocks `/* a task on the chain */`, `/* a step block */`, `/* the connector
> between two steps */`, `/* a fix insert */`, `.tries`. Depends on Task 2.
>
> Lands on: plan 23 Task 6 (`brief_meta`, `facts` on the task row and in task.json), plan 24 Task 4 (`s.part`, the
> `from plan` tag, `t.plan.from`), plan 5 Task 6 (`modelText` showing `codex · gpt-6.1-sol · medium`, `s.harness`).
> This task reads those keys with `.get`-style guards (`s.brief_meta || {}`) so it runs before or after them.

**Files**
- Modify: `web/app.js` (`chainHtml`, `stepBlock`, `connBlock`, `stepShown`, `stepCtx`, `ctxMiniHtml`, `ctxRowHtml`,
  `stepCost`, `rungTime`, `triesHtml`, `scoutHint`, `emptyBoard`; constants `BWORD`, `HINT_IN_W`, `HINT_CTX`)
- Modify: `web/style.css` (the chain rules)

## 3.1 What a block shows, and where it comes from

| On screen | From |
|---|---|
| state word and sprite | `stepShown(t, s, row)`: `"waiting"` when `s.n === t.current` and the task waits (`row.state === "waiting"` or `row.asks`); `"failed"` when `s.verdict === "FAIL"` or `s.state === "failed"`; else `s.state` (`running`, `done`, `planned`, `handed`). `BWORD` maps it to `[word, tone, sprite]`: `running ["Running", "n", "running"]`, `done ["Done", "g", "done"]`, `failed ["Fail", "r", "stuck"]`, `planned ["Planned", "q", "planned"]`, `waiting ["Waiting", "y", "waiting"]`, `handed ["Handed", "y", "done"]` |
| `NN kind` | `two(s.n)` and `s.kind` (D1 a: the service numbers, the insert shows by the bracket); `· from plan` muted when `s.part` |
| cost | `stepCost(s)`: `cost unknown` (muted `.unk`) when `s.cost == null` (plan 5: a harness that reports no cost); `money(s.cost)` otherwise (the service's step cost is the sum of its attempts, exact for a Claude run); nothing on a planned step |
| rung and time | `rungTime(s)`: `modelText(s.model, s.effort)` (with plan 5: the harness first), then ` · ` and `elapsed(s.ended - s.started)` for a finished step or `elapsed(snap.now - s.started)` for a running one; a planned step has neither |
| context | `stepCtx(s)`: the live session row's `ctx_tokens` for a running step (`snap.sessions.find(x => x.id === s.session)`), else `s.ctx_tokens`; `undefined` and `null` both mean unknown |
| tries | `triesHtml(s)`: one 7 px square per attempt (`s.attempts`), red for a try with a `why` (it failed), green for the last one when the step is done, ink live for a running one; shown when there are 2 or more attempts or a failed one |
| sub line | `[verdict FAIL detail (red) or PASS (green), scoutHint, the task's why in orange when the block is the waiting one]` joined by ` · ` |

## 3.2 The three lengths (`stepBlock(t, s, d, row)`)

- **Full** (the mock's `.sb`): the step is current, failed, waiting, picked, or its context is at or past the yellow
  threshold (`cfg.gauge[0]`). Lines: `l1` (sprite and word, `NN kind`, cost), `rung` (`rungTime`, `triesHtml`), the
  context row `ctxRowHtml(s, live)` (`ctx` label, 30 cells of `ctxClasses`, the figure `kTokens` in the tone; unknown:
  the word `unknown` with the title of 3.5 in the README), the `sub` line. `.cur` when running, `.y` when waiting.
- **Finished** (`.sb.short`): two lines; the second is `rungTime` on the left and `ctxMiniHtml(s)` on the right: 15
  cells (every other class of `ctxClasses`) and the figure, or `ctx unknown` (title as above).
- **Planned** (`.sb.one`): one line, `NN kind` muted, title `rung at start (rule <kind>)`.
- Every block is a `div` with `data-bpick="s<n>"`, `tabindex="0"`, `role="button"`, `.picked` when it is the pick.
- The unknown title: `<harness> reports a turn's spend, not a context size` when `s.harness` is set and not
  `claude`; else `no context reading for this step` (a step from before plan 25 has no key).

## 3.3 `scoutHint(t, s, d)` (D4 a)

```js
const HINT_IN_W = 300, HINT_CTX = 100000;  // D4 (a): a small handoff in and a large context reached: the step read on its own
function scoutHint(t, s, d) {
  const prev = t.steps.find((x) => x.n === s.n - 1), meta = (prev && prev.brief_meta) || {};
  const inW = meta.sent_w != null ? meta.sent_w : null, ctx = stepCtx(s);
  if (inW == null || ctx == null || inW >= HINT_IN_W || ctx < HINT_CTX || s.state === "planned") return "";
  return `<span title="${inW} w in, ${kTokens(ctx)} reached">△ scout first</span>`;
}
```

Muted, never orange (README 3.6). With D4 (b) the function returns `""` and the constants go.

## 3.4 The task rows (`chainHtml(row, d, picked)`)

- Every task in `boardTasks()` is a `.tk`; only the picked one (`d` given) is unfolded.
- Head `.thead` (`data-bpick="t"`, `data-btask="<id>"`, title `<project> · effort <effort>`): `l1` sprite and
  `TASK_WORD` word (the existing map, `taskShown(row)`), the title, the age (`ago(snap.now - row.updated)`); `l2`:
  folded: the why in orange when waiting, else `N steps`; unfolded: `step <current> of <count>` (D1 a: the service
  numbers) or `N steps` when done; the cost `money(row.cost)` (mono, no Doto: README 3.6).
- Unfolded: for each step in `d.task.steps` order, the connector after the previous step (3.5) then `stepBlock`. A
  task that is gone (`d === false`) shows its head and `This task is gone.` muted.

## 3.5 Connectors (`connBlock(t, s, d)`, after step `s`)

Not drawn after the last step. `t` is `d.task`; `meta = s.brief_meta || {}`; the next step `nx`.

| Case (first that holds) | Class | Chip | Chip title |
|---|---|---|---|
| `s.state === "running"` or `t.briefing === s.n` | `writing` | `writing` | `step NN is writing its handoff` / `Haiku is compacting the handoff for step NN` |
| no note for `s` (`s.state` planned or failed, `!d.notes[s.n]`) | `pending` | none (a dotted line) | none |
| `meta.fallback` | `fallback` | `as written · not compacted` | `meta.fallback` (the reason) |
| design step with `t.plan && t.plan.from === s.n` | `plan` | `handoff · <b>plan</b>` | `the handoff of step NN, compacted to S words, and plan.md (W words, never cut), which every later step reads` |
| `meta.cut && meta.cut.length` | `cut` | `handoff · <b>cut N w</b>` with `N = meta.raw_w - meta.sent_w` | `step NN wrote R words; the next step received S once compacted, Findings cut N w` |
| else | `""` | `handoff` | `the handoff step NN left for the next step, compacted to S words` |

Each connector is `div.conn` with `data-bpick="c<n>"`, `tabindex="0"`, `role="button"`, except a pending one (not
pickable, not in `boardItems`). The words are figures in the title and the chip, never cells (ID-5).

## 3.6 The fix bracket (D1 a)

A step with `kind === "fix"` and the step after it with `kind === "verify"` and `checked === fix.n` (the shape
`tasks._insert_fix` builds) go inside `<div class="branch"><span class="ln"></span><div class="in">...</div></div>`:
the connector after the failed verify, the fix block, the connector after the fix, the second verify. The chain rejoins
after it (the next connector is drawn outside). Numbers stay the service's (`06 fix`, `07 verify`). The failed verify
above it reads `Fail` with its verdict detail (state `done`, verdict `FAIL`: `stepShown` gives `failed`).

## 3.7 The empty Board (`emptyBoard()`)

```js
function emptyBoard() {
  const where = scope ? projectName(scope) : "any project";
  return `<div class="empty"><div class="cells">${cellsHtml(Array(30).fill(""))}</div>
    <p>No task in ${esc(where)}. Type a task in the list; its steps show here as they run.</p></div>`;
}
```

The inspector is empty and the footer has no keys (Task 2 2.5).

## 3.8 The replan block

A step with `kind === "replan"` (plan 24) is a normal block: `02 replan`, rung `haiku/low`, no session (no Open in
its inspector, Task 5). While the task waits on it (`row.why` starts `replanned:`), it is the waiting block (orange
border, why in orange).

## 3.9 `web/style.css`

Port from the mock, in its order, under `/* the Board (plan 25) */`: `.tk`, `.thead` (and `:hover`, `.t`, the
two-line clamp, `.l2`, `.who.y`), `.thead.picked, .sb.picked, .conn.picked .chip`, `.tk.folded ...`; the step block
`.sb` to `.sb .sub .y`; `.tries`; the connector `.conn` to `.conn.pending .ln`; the fix bracket `.branch` to
`.branch .in .conn`. Add `.conn.plan .chip b { color: var(--ink); }` (the mock styles it inline). The `.l1`, `.l2`,
`.ctx` rules already in the stylesheet (list cards) are reused, not copied again.

## 3.10 Checks (900 x 680, the fake service: one task `CHAIN fix add` with `HANDOFF-OK` done, one with `VERDICT-FAIL` at its fix)

1. The picked task unfolded, the other folded to one row (`2 steps` or its why); ← → swaps them.
2. Done steps are two lines with 15 cells and the figure; the current step is full with 30 cells; planned steps are
   one line. A step whose task.json has no `ctx_tokens` reads `ctx unknown`, title `no context reading for this step`.
3. Connectors: `handoff` between done steps, dotted after the planned ones, `writing` after the running one; edit a
   step's `brief_meta` in the temp task.json (`cut: ["x"], raw_w: 400, sent_w: 300`) and the chip reads
   `handoff · cut 100 w`; `fallback: "pass failed"` gives the dashed `as written · not compacted`.
4. The FAIL task: verify `Fail` with its detail in red, then the bracket with `fix` and the second `verify`, numbered
   as the folder is.
5. A scope with no task: the empty text, no keys in the footer.
6. No horizontal overflow in `.bchain` with a 120-character task title and a 60-character model name.

## 3.11 Steps, in order

1. `style.css` (3.9).
2. `app.js`: `BWORD`, `stepShown`, `stepCtx`, `ctxMiniHtml`, `ctxRowHtml`, `stepCost`, `rungTime`, `triesHtml`,
   `scoutHint`, `stepBlock`, `connBlock`, `chainHtml` (replacing Task 2's stub), `emptyBoard`.
3. `node --check web/app.js`; the full suite; the checks of 3.10.
4. Commit `plan 25 task 3: the Board's chain: step blocks, connectors, fix bracket (N tests OK)`.

Expected count: unchanged.

## 3.12 Drift guards

- Context is cells of 10K up to the red threshold (`ctxClasses`); a handoff's words are figures only.
- Unknown is a word, never `0K` and never an estimate; cost unknown is `cost unknown`, never `0.00`.
- Orange only on the waiting block's border and its why; a cut, a fallback, a hint are ink or muted.
- The chain reads `d.task` and the snapshot row; it fetches nothing of its own.
