# Task 4: the list (UI-1) and the steps under a running row (UI-2)

Files: `web/app.js`, `web/style.css`, `web/index.html` (one line), `tests/test_web.py`, `tests/live_board_check.py`.
Commit boundary: `feat: the Board list by project under a pinned Needs you (plan 55 Task 4)`. Depends on Task 2.
Assumes D9 a, D10 a, D11 a. **Stop 2 follows this task** (README section 6).

What the user gets: everything that needs Fred, in every project, pinned on top; then one group per project, its name
only; a Console run as a filled card, an outside chat as a dashed card whose status line starts with its app
(`VS Code · working`); a running run lists its steps, each line a link to its step page; a task in Needs you leaves a
muted line in its own project group. On a two-column Board with nothing picked, the first pinned task opens (plan 38 U8).

Today's list is close to this already: rows (`taskHtml`, `sessionRow`, `prepTaskHtml`, `reviewHtml`) stay; the
grouping, the observed status line, the step lines and the Prep row under a task change.

## 1. Code (`web/app.js`)

### 1.1 Grouping (replaces `chainGroups`, `secHtml`, `chainHtml`)

Replace the three functions `function chainGroups() {`, `function secHtml(`, `function chainHtml() {` (each whole) by:

```js
let earlierOpen = new Set();  // the project groups whose "Done earlier" fold is open (this window only)
let homeDone = false;         // plan 38 U8: the first pinned task was opened once on this load
function projectGroups() {  // [[dir, {live, obs, today, earlier, ts}]] in scope, newest activity first (plan 53 adds its build rows to `live`)
  const today = todayKey(), by = new Map();
  const at = (dir) => { const k = [...by.keys()].find((x) => sameDir(x, dir)) ?? dir; if (!by.has(k)) by.set(k, { live: [], obs: [], today: [], earlier: [], ts: 0 }); return by.get(k); };
  for (const t of (snap.tasks || []).filter(taskInScope)) {
    const g = at(t.project_dir), grp = taskGroup(t);
    g.ts = Math.max(g.ts, t.updated);
    if (grp === "needs") g.live.push({ pinned: t });
    else if (grp === "done") (dayOf(t.updated) === today ? g.today : g.earlier).push(t);
    else g.live.push(t);
  }
  for (const j of prepRows().filter((x) => x.state === "running")) { const g = at(j.project_dir); g.live.unshift(j); g.ts = Math.max(g.ts, j.ts); }
  for (const s of snap.sessions.filter((x) => inScope(x) && !x.task && !x.chat_task && x.group !== "needs" && x.group !== "empty")) {
    const g = at(s.project_dir);
    g.ts = Math.max(g.ts, s.last_ts);
    if (s.group === "done") (dayOf(s.last_ts) === today ? g.today : g.earlier).push(s);
    else g.obs.push(s);
  }
  return [...by.entries()].sort((a, b) => b[1].ts - a[1].ts);
}
function listHtml() {  // UI-1: Needs you pinned across projects (D11 a), then one group per project, its name only (D10 a)
  const item = (x) => (x.kind === "review" ? reviewHtml(x) : x.steps ? taskHtml(x) : x.raw !== undefined ? prepTaskHtml(x) : sessionRow(x));
  const needT = (snap.tasks || []).filter((t) => taskGroup(t) === "needs").sort((a, b) => b.updated - a.updated);
  const needJ = preps().filter((j) => j.state !== "running"), needS = snap.sessions.filter((s) => !s.task && !s.chat_task && s.group === "needs");
  const n = needT.length + needJ.length + needS.length;
  let html = n ? `<div class="p-pin" id="needsec"><span class="lbl y">Needs you · ${n} · all projects</span>${[...needJ, ...needT].map(item).join("")}${needS.map(sessionRow).join("")}</div>` : "";
  for (const [dir, g] of projectGroups()) {
    html += `<div class="p-prj"><span class="nm" title="${esc(dir)}">${esc(projectName(dir))}</span></div>`
      + g.live.map((x) => (x.pinned ? `<div class="p-quiet" title="${esc(x.pinned.title)}"><span class="t">${esc(x.pinned.title)}</span><span> · in Needs you</span></div>` : item(x))).join("")
      + g.obs.map(sessionRow).join("") + g.today.map(item).join("");
    if (g.earlier.length) {
      const open = earlierOpen.has(dir);
      html += `<button class="p-earlier" data-earlier="${esc(dir)}" aria-expanded="${open}">Done earlier · ${g.earlier.length}<span class="car">&#9662;</span></button>`;
      if (open) for (const [k, rows, ss] of doneDays(g.earlier.filter((x) => x.steps), g.earlier.filter((x) => !x.steps))) html += dayGroup(k, rows, ss);
    }
  }
  const older = snap.older || 0;  // unchanged from chainHtml: the Older row, then the empty chats behind the header menu
  if (older) {
    html += `<div class="v-sec${olderOpen ? "" : " fd"}"><button class="dh" data-older aria-expanded="${olderOpen}" title="Tasks finished more than ${OLDER_DAYS} days ago; they open in place, by day"><span class="lbl">Older · ${older}</span><span class="car">&#9662;</span></button></div>`;
    if (olderOpen) html += !olderRows ? '<p class="note m">Reading the older tasks.</p>' : doneDays(olderRows.tasks.filter(taskInScope), []).map(([k, rows]) => dayGroup(k, rows, [])).join("");
  }
  if (emptyOpen) html += groups().empty.map((s) => quietHtml(s, !scope)).join("");
  return html || emptyBoard();
}
function homePick() {  // plan 38 U8 (D5 a), placed here: a two-column Board with nothing picked opens the first pinned task, once
  if (homeDone || boardTask || boardPick || page !== "board" || $("vboard").clientWidth < 700) return;
  homeDone = true;
  const first = (snap.tasks || []).filter((t) => taskGroup(t) === "needs").sort((a, b) => b.updated - a.updated)[0];
  if (first) openTask(first.id);
}
```

`prepTaskHtml` objects are Prep jobs (they carry `raw`); `reviewHtml` jobs carry `kind: "review"`. Check the `item`
dispatch against `prepTaskHtml(j)`'s and `reviewHtml(j)`'s inputs when building (both read `j.raw` or `j.kind`).

In `async function renderBoard()`: replace `setHtml($("bchain"), chainHtml());` with
`setHtml($("bchain"), listHtml());` and add on the next line `homePick();`. Replace the `setHtml($("bfoot"), ...)`
statement's last line (the `<button class="q" ... aria-label="Legend">?</button>`) with nothing, keeping the
keyboard hints: the legend described the mini context cells this task removes (plan 38 Task 5, half moot).

The click handler: add `[data-earlier],` to the selector and, before the `data-txfold` branch:

```js
  else if (t.dataset.earlier !== undefined) { const k = t.dataset.earlier; if (earlierOpen.has(k)) earlierOpen.delete(k); else earlierOpen.add(k); renderBoard(); }
```

Any other caller of `chainHtml`, `chainGroups` or `secHtml` (`grep -n` them) switches to `listHtml` or is deleted
with them. `needsec` keeps its id, so the header's "N need you" button still scrolls to the pin.

### 1.2 Rows

`function sessionRow(s)`: the app moves into the status line (UI-1: no tags on rows). Replace its `l1`/`l2` lines with:

```js
    <div class="l1"><span class="st ${tn}">${sessionMark(s, s.symbol, tn)}</span><span class="t">${esc(s.title)}</span></div>
    <div class="l2"><span class="why${wt ? " " + wt : ""}" title="${esc(text)}">${esc(chip ? `${appName(s)} · ${text}` : text)}</span><span class="cost">${spentText(s)}</span></div></div></div>`;
```

and split `sourceChip` so the name is reusable:

```js
function appName(s) { return s.harness && s.harness !== "claude" ? s.harness : SOURCE_NAME[s.source] || (s.source && s.source !== "?" ? s.source : "outside"); }
function sourceChip(s) { return s.source === "window" ? "" : `<span class="v-src">${esc(appName(s))}</span>`; }  // still the session page's chip
```

### 1.3 Steps under a running row (UI-2)

Replace `function stepRows(t) { ... }` and `function chainStepHtml(t, s, picked) { ... }` by:

```js
const SUB_GLYPH = { done: "✓", running: "▸", replied: "▸", planned: "·", waiting: "?", failed: "✕" };
function stepRows(t) {  // UI-2: one line per step in chain order; the Prep row is the Brief section's link now (D10 a)
  const picked = t.id === boardTask ? boardPick : "";
  return t.steps.map((s) => chainStepHtml(t, s, picked)).join("");
}
function chainStepHtml(t, s, picked) {  // glyph, `01 scout`, the state (with the model while it runs); the line opens the step page
  const shown = stepShown(t, s, t);
  const word = shown === "running" ? `${alias(s.model) || s.model || "auto"} · running` : { planned: "queued", failed: "failed", waiting: "waits", replied: "replied" }[shown] || "done";
  return `<div class="v-sr p-sub ${shown}${picked === "s" + s.n ? " picked" : ""}" data-bpick="s${s.n}" data-btask="${esc(t.id)}" tabindex="0" role="button" title="Open step ${two(s.n)}">
    <span class="sg" aria-hidden="true">${SUB_GLYPH[shown] || "·"}</span><span class="sn">${two(s.n)} ${esc(s.kind)}</span><span class="sm">${esc(word)}</span></div>`;
}
```

Delete each of `prepRowHtml`, `miniCtx`, `receivedNote`, `scoutHint` whose last caller was the old `chainStepHtml` /
`stepRows` (`grep -n` each name first; keep any that the step page still calls). `HINT_IN_W`, `HINT_CTX` go with
`scoutHint`.

### 1.4 Landmark (`web/index.html`)

Replace the line `          <div id="bchain" class="v-chain" aria-label="Tasks and chats"></div>` with
`          <nav id="bchain" class="v-chain" aria-label="Tasks and chats"></nav>` (plan 38 Task 7's landmark, placed here).

## 2. Style (`web/style.css`, append)

```css
/* plan 55: the list (UI-1, UI-2): Needs you pinned, one group per project, dashed outside chats, steps as links */
.p-pin { margin: 8px 8px 0; padding: 6px; border-radius: 9px; border: 1px solid color-mix(in srgb, var(--you) 40%, transparent);
  background: color-mix(in srgb, var(--you) 5%, transparent); }
.p-pin > .lbl { display: block; padding: 2px 4px 6px; font-size: 11px; }
.p-prj { display: flex; align-items: center; gap: 6px; padding: 14px 12px 5px; }
.p-prj .nm { flex: 1; min-width: 0; font: 600 11px var(--mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.v-tk > .v-th { background: var(--raise); }
.v-tk.out > .v-th { background: transparent; }
.p-quiet { display: flex; min-width: 0; margin: 0 8px 4px; padding: 2px 9px; font-size: 12px; color: var(--mut); white-space: nowrap; }
.p-quiet .t { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.p-earlier { display: flex; justify-content: space-between; align-items: center; width: calc(100% - 16px); min-height: 24px; margin: 2px 8px 4px;
  padding: 2px 9px; border: 0; border-radius: 5px; background: transparent; color: var(--mut); font: 11px var(--mono); cursor: pointer; }
.p-earlier:hover { background: var(--raise); color: var(--ink); }
.p-earlier[aria-expanded="true"] .car { transform: rotate(180deg); }
.v-sr.p-sub { grid-template-columns: 12px minmax(0, 1fr) auto; gap: 6px; align-items: baseline; padding: 3px 8px; font: 12px var(--ui); }
.p-sub .sg { font: 11px var(--mono); color: var(--mut); }
.p-sub.done .sg { color: var(--ok); } .p-sub.running .sg { color: var(--ink); } .p-sub.failed .sg { color: var(--bad); } .p-sub.waiting .sg { color: var(--you); }
.p-sub .sn { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.p-sub.planned .sn { color: var(--mut); }
.p-sub .sm { font: 11px var(--mono); color: var(--mut); white-space: nowrap; }
.p-sub:hover .sn { text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--mut); }
.p-sub.picked { background: var(--raise); box-shadow: inset 2px 0 0 var(--ink); }
```

Check while building: `.v-src`'s 10 px and any other 10 or 10.5 px rule the list still draws are raised to 11 px
(plan 38 D4 b); `.v-tk.y > .v-th` keeps its orange tint inside the pin.

## 3. Tests

`tests/test_web.py` `BoardListTest`:

- Replace `test_three_groups_and_replied_chats_join_running` by:

```python
    def test_pin_spans_projects_and_groups_follow_the_scope(self):
        x = self.setup + """snap.tasks = [mkt({id: 'n1', state: 'waiting', group: 'needs', asks: 'Which?', project_dir: 'other', project: 'Other'}), tk0,
          mkt({id: 'd1', state: 'done', group: 'done', updated: 990}), mkt({id: 'd0', state: 'done', group: 'done', updated: -200000})];
          snap.sessions = [{id: 'o1', title: 'Fix eslint', group: 'working', state: 'running', source: 'vscode', project_dir: 'repo', project: 'repo', last_ts: 950, spent: 1}];
          projectName = (d) => d; """
        html = render(x + "listHtml()")
        self.assertIn("Needs you · 1 · all projects", html)
        self.assertLess(html.index("Needs you"), html.index('class="p-prj"'))
        self.assertIn(">repo<", html)
        self.assertIn(">other<", html)
        self.assertIn("in Needs you", html)  # n1's own group keeps a muted line
        self.assertIn("VS Code · running", html)  # the app in the status line, no chip on the row
        self.assertNotIn('class="v-src"', html)
        self.assertIn('data-earlier="repo" aria-expanded="false">Done earlier · 1', html)
        for gone in ("Running ·", "Done today"):
            self.assertNotIn(gone, html)
        scoped = render(x + "scope = 'repo'; listHtml()")
        self.assertIn("Needs you · 1 · all projects", scoped)  # D11 a
        self.assertNotIn(">other<", scoped)
        opened = render(x + "earlierOpen.add('repo'); listHtml()")
        self.assertIn('data-dayfold=', opened)
```

- `test_list_row_is_one_status_line`: unchanged (the running row still has one `v-subs` and three step links; the
  others none).
- Add:

```python
    def test_step_lines_are_glyph_number_kind_and_state(self):
        html = render(self.setup + "taskHtml(tk0)")
        self.assertIn('<span class="sn">01 scout</span><span class="sm">done</span>', html)
        self.assertIn('<span class="sn">02 code</span><span class="sm">sonnet · running</span>', html)
        self.assertIn('<span class="sn">03 verify</span><span class="sm">queued</span>', html)
        self.assertNotIn('class="mini"', html)
        self.assertNotIn('data-bpick="p"', render(self.setup + "taskHtml(mkt({prep: {state: 'done', model: 'haiku', cost: 0}}))"))

    def test_home_pick_opens_the_first_pinned_task_once(self):
        got = render(self.setup + """const opened = []; openTask = (id) => opened.push(id); document = {getElementById: () => ({clientWidth: 900})};
          snap.tasks = [mkt({id: 'n1', state: 'waiting', group: 'needs', updated: 900}), mkt({id: 'n2', state: 'waiting', group: 'needs', updated: 950})];
          homePick(); homePick(); boardTask = 'x'; homeDone = false; homePick(); opened""")
        self.assertEqual(got, ["n2"])  # newest first, once, never over a pick
        self.assertEqual(render(self.setup + "const o = []; openTask = (id) => o.push(id); document = {getElementById: () => ({clientWidth: 400})}; "
                                "snap.tasks = [mkt({id: 'n1', group: 'needs'})]; homePick(); o"), [])  # one column: the list stays
```

Headless, `tests/live_board_check.py`: add a list sweep after the per-state loop (`page.evaluate("showPage('board');
boardTask = ''; boardPick = ''; renderBoard()")` at each width and scheme) and to `CHECKS`:

```python
def list_checks(page, name):  # Task 4: the pin first, project names, every row and step line a pointer control
    if page.locator(".v-chain").is_visible():
        assert page.locator(".v-chain .p-prj").count() >= 1, (name, "project groups")
        for sel in (".v-chain .v-th", ".v-chain .p-sub"):
            for el in page.locator(sel).all()[:6]:
                assert el.evaluate("e => getComputedStyle(e).cursor") == "pointer", (name, sel)
```

and extend `SMALL` and `TINY` to `.v-chain *` (already listed) so the list meets the 11 px and 24 px floor.

## 4. Run

`node --check web/app.js`; `py -m unittest tests.test_web`; `py -m tests.live_board_check --shots <scratch>`;
`py -m tests.live_autopilot_check 5` (its list sweep); the full suite in the background. Then **stop 2**.
