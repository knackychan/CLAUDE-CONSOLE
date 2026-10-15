# Task 6: The handoff picked, the task head inspector, the Measure table

> Contract: [README.md](README.md) 3.2 (`brief_meta`, `questions`, `chain`, `/api/measure`), 3.4, 3.5 (Checks fold,
> Measure head and reading), 3.6. Design: interface doc 8.3 (a picked connector: what the next step received, the cut
> lines struck in place; the task head: Now line, open questions, prompt.md, chain log; Measure), ID-1, ID-5, D2 and
> D3 of this README. Mock: `cells-board.html` functions `inspConn`, `headingBlock` (its `whole` argument), `inspTask`,
> `inspMeasure`, the views `Board · handoff`, `Board · task`, `Board · measure`, and the CSS `.hsec li.cut` to `.hsec
> .mono`, `.checks`, `.oq`, `.oqr`, `.clog`, `.now` (the mock's inline Now line), `.measure` to the end of the Board
> block, `.legend`. Depends on Task 3.
>
> Lands on: plan 23 Task 6 (`headingBlock(h, cut, open, whole)`: plan 23 already has the fourth argument `whole`, which
> adds ` · whole` to a heading count): this task adds the folded Goal's `whole · <goal>` line and the fold keys
> `h.<heading>` (6.1). Nothing else of plan 23's changes.

**Files**
- Modify: `web/app.js` (`inspConn`, `checksFold`, `inspTask`, `inspMeasure`; `headingBlock`'s folded Goal and fold keys;
  `boardInspector`'s `t`, `c<n>` and `""` cases; the measure fetch in `renderBoard`)
- Modify: `web/style.css` (the rules named above)

## 6.1 `headingBlock(h, cut, open, whole)` (plan 23's, extended)

- `whole` (default `false`) exists already (plan 23: a heading count reads `N lines · whole`); keep its signature and
  add only: a folded Goal (Goal not in `open`) reads `whole · <goal>` as its closed line when `whole` is true (the brief
  pass carries Goal and Troubleshooting whole: plan 23's check). Nothing else changes.
- Each folded heading passes `key: "h." + <heading key>` to `fold` (`h.files`, `h.trouble`, ...), so Fred's choice
  to keep Files touched open is remembered for every handoff (Task 2 2.6).

## 6.2 A picked connector (`inspConn(t, s, d)`, `boardPick === "c<n>"`)

- `s` the step before the connector, `nx` the one after, `meta = s.brief_meta || {}`.
- No brief yet: `writing` gives `Haiku is compacting the handoff for step NN.`; a fallback with no note gives its
  reason; else `Not written yet.` (a pending connector is not pickable: Task 3 3.5).
- Head: `<h2>Handoff from NN kind to NN kind</h2>`; meta `NN wrote <b>R w</b>`, `NN received <b>S w</b>`, and when
  `meta.cut.length`: `cut <b>R-S w</b>, K Findings lines` (ink, never orange: ID-1), or `sent as written` on a fallback.
- Body: `.blk` `What NN received` with `headingBlock(handoffSections(d.notes[s.n]), meta.cut || [], open, true)`:
  the raw note, the cut lines struck in place and tagged `cut` (plan 23 matches them whitespace-normalised; a cut line
  it cannot place is listed under Findings tagged `cut`), `open` the headings holding a cut line plus `questions` and
  `next`.
- `checksFold(meta)` under it.

```js
function checksFold(meta) {  // what the code checked on the brief pass's answer (plan 23): closed unless one failed
  const list = meta.checks || [];
  if (!list.length) return "";
  const bad = list.filter((c) => !c.ok);
  const info = (bad.length ? `<span class="r">${bad.length} FAIL: ${esc(bad[0].name)}</span>` : `${list.length - bad.length} of ${list.length} pass`)
    + (meta.by ? ` · compacted by ${esc(meta.by)}` : "") + (meta.cost != null ? ` · $${Number(meta.cost).toFixed(3)}` : "")
    + (meta.turns ? ` · ${meta.turns} ${meta.turns === 1 ? "turn" : "turns"}` : "");
  const rows = list.map((c) => `<span><span class="${c.ok ? "g" : "r"}">${c.ok ? "✓" : "✗"}</span> ${esc(c.name)}${c.why ? ": " + esc(c.why) : ""}</span>`).join("");
  return fold("Checks", info, `<div class="checks">${rows}</div>`, { open: !!bad.length, force: !!bad.length, key: "checks" });
}
```

## 6.3 The task head (`inspTask(t, d, row)`, `boardPick === "t"`)

- Head: sprite and `TASK_WORD` word (`taskShown(row)`); `<h2 title="<taskDir(t.id)>">title</h2>`; buttons from
  `d.levers` like the Task page bar: `Stop` (`stop === ""`), `Pause` (`pause === ""`), `Resume`, `Clear` (`clear ===
  ""`), each `data-tact="<name>" data-tid="<t.id>"` (two clicks where the Task page asks two). Meta: `step <current> of
  <count>` (D1 a) or `N steps` when done, `cost <b>money(row.cost)</b>`, `effort <effort>`.
- Now line (`.now`) while a step runs: a live cell, `Now <b>NN kind</b> · rungTime(cur)`, on the right `next NN kind`
  or `last step`.
- The task's why when waiting: the same askbox the Task page draws for a plain question (`row.asks`), with `Send
  answer` through `stepAct` given the task (the Board's answer box is `textarea.in` inside the askbox, read by
  `closest(".askbox")`); the plan waits are Task 5's.
- Open questions (`d.questions`, D2 a): `.blk` `Open questions · <span class="y">N open</span>`, rows `.oqr` with `?`
  (orange) and `opened NN`; none open: `none`. Closed ones in `fold("", "K closed", ..., { cls: "qf", key: "qclosed" })`
  with `✓` (green) and `opened NN · closed NN`.
- prompt.md: `fold("prompt.md", "Done when: <line>", <pre class="text">t.goal</pre>, { key: "promptmd" })`, the line
  from `/Done when:\s*([^\n]*)/` on `t.goal`, else its first line cut to 80 characters.
- Chain log (`d.chain`): `fold("Chain log", "N moves · last hh:mm <move>", rows, { key: "clog" })`, a row
  `<span>hms(ts)</span><span title="why">NN from -> to (why)</span>` (`task` for a task-level move whose `step` is 0),
  oldest first; the closed line's move without its `(why)`.
- Errors in `#b-msg`.

## 6.4 The Measure table (`inspMeasure(m, name)`, `boardPick === ""`)

- Fetch: in `renderBoard`, when the pick is `""`: `GET /api/measure?project=<encodeURIComponent(boardProject())>&n=10`
  when `measureData` is for another project or older than 60 s (`snap.now - measureData.at >= 60`); with no project
  (All projects and no task) the inspector says `Pick a project to measure its tasks.`
- Head `Measure · <name> · last N tasks` (`m.tasks`, `name = projectName(m.project)`), meta `median per kind`.
- Grid `.measure`: header `kind`, `received` (right), `context`, `handoff` (right); one row per `m.kinds[]` in the
  order the service returns: `.k` (`.hot` when `kind === m.hot`), `received` as `W w` (or `pack` for scout with
  `received` null and title `the task goal and the context pack`; any other null `?`), the context as 20 cells over
  200K (`.bar`, tone `y` at or past `cfg.gauge[0]`) with `NK`, or `unknown`; `handoff` as `W w` or `?`.
- Legend: `median`, `context past 150K` only when a bar is orange, `cell 10K · words as figures`.
- Reading (D3 a), when `m.hot`: `A kind that receives a small handoff and reaches a large context reads too much on
  its own: <kind> at <K>K from <W> words in is the one to tune (scout first, or a turn cap).`; no hot kind: nothing.
- Zero tasks: `No finished step in <name> yet: the table fills as tasks run.`

## 6.5 `web/style.css`

Port `.checks`, `.checks .g/.r/.y`, `.oq`, `.oqr` to `.oqr .m`, `.clog`, `.clog > div`, `.clog > div > span:last-child`,
`.measure` to the end of the Board block (`.measure .cells`, `.measure .cells i`, `.measure .k`, `.measure .k.hot`,
`.measure .bar`, `.measure .fig`, `.measure .hd2`), and the `.now` row as the mock draws it (`display: flex; gap: 8px;
align-items: center; font: 11.5px var(--mono);` with the right part `margin-left: auto`). `.hsec li.cut` and its `s`,
`.tag` are plan 23's: copy only what `grep` does not find.

## 6.6 Checks (900 x 680)

1. Pick a `handoff` connector of the fake run: head with the two figures, the raw note's six headings; with a hand
   edited `brief_meta` (`cut: ["<a Findings line>"], raw_w: 412, sent_w: 290, checks: [...one false...]`): `cut 122 w,
   1 Findings lines` in ink, the line struck in place with `cut`, the Checks fold red and open; with all checks true
   it is closed and reads `5 of 5 pass · compacted by haiku · $0.004 · 2 turns`.
2. Pick the task head: buttons by levers, the Now line on the running task, open questions from the briefs (edit a
   brief to add `## Open questions` / `- Is a week Monday to Sunday?` and remove it from a later one: `1 closed`),
   prompt.md closed with its Done when line, the chain log with the moves.
3. Esc to `""`: the Measure table for the project, the reading when a kind is hot; a project with no done task gives
   the zero line.
4. Toggle Files touched open on one handoff, pick another: it is open there too (key `h.files`).
5. No horizontal overflow in `.binsp`; the 20-cell bars keep their width at 700 px.

## 6.7 Steps, in order

1. `style.css` (6.5).
2. `app.js`: `headingBlock`'s folded Goal line and fold keys; `checksFold`, `inspConn`, `inspTask`, `inspMeasure`; the
   measure fetch; `boardInspector`'s remaining cases.
3. `node --check web/app.js`; the full suite; the checks of 6.6.
4. Commit `plan 25 task 6: the handoff inspector, the task head, the Measure table (N tests OK)`.

Expected count: unchanged.

## 6.8 Drift guards

- A cut is ink words and struck lines, never orange, never cells (ID-1, ID-5).
- Measure reads `GET /api/measure` only; the window computes no median.
- The questions are the service's (`d.questions`); the window does not parse briefs for them.
