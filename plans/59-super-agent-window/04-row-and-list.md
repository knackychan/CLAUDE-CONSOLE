# Task 4: the super agent row, the roll-up list, the counts and the fetch

> Contract: [README.md](README.md) 4.3, 5 (SW-1, SW-2, SW-12), 6. Decisions D7 a (plan 55 D10 a inside an opened project),
> D8 a (the queue spans all projects), D9 a (`N for you`). This task builds what plan 55 Task 4 would have built, in
> the locked mock's shape, on the existing `chainGroups`/`secHtml`/`chainHtml` code (plan 55 Task 4 is never built).
> No answer yet: the page of Task 5 and the actions of Task 6 come next; this task leaves the list, the header and the
> data flow right, with the home pane still empty.

**Files:** `web/app.js`, `web/style.css`, `web/index.html` (one attribute), `tests/test_web.py` (`SuperListTest`),
`tests/live_super_check.py` (new; the Rig is plan 55 Task 1's `tests/live_board_check.py` and `tests/live_autopilot_check.py`).
Commit boundary: `feat: the super agent row, the roll-up list and one count in the window (plan 59 T4)`. Depends on
Task 3 and plan 55 Tasks 1 to 3. Anchors are quoted lines; line numbers are for finding only.

What the user gets: the first row of the list is `◆ Super agent  N for you`; each project is one line until something
in it is for him; steps show only under the selected task; the header button says `N for you` and is never hidden.

## 4.1 Tests first (red), `tests/test_web.py`

New class after plan 55's `BoardListTest` replacement (or after `BoardListTest` where plan 55 Task 4 is absent):

```python
@unittest.skipUnless(NODE, "Node is not installed")
class SuperListTest(unittest.TestCase):
    """Plan 59 Task 4: the row, the counts and the roll-up list read snap.super and the view, never a gate."""
    SUP = ("snap.now = 1000; snap.super = {rev: 'r1', mode: 'ranked', for_you: 3, later: 1, line: '4 running · 1 later · sorted 14:01',"
           " by_project: {'D:\\\\p': 2, 'D:\\\\q': 1}, marks: {a: ['queue'], b: ['queue'], c: ['queue'], z: ['later', '15:06']}, error: ''}; "
           "snap.counts = {needs: 5, for_you: 3}; snap.tasks = []; snap.sessions = []; ")

    def test_row_is_first_counts_for_you_and_names_the_line(self):
        html = render(self.SUP + "swRow()")
        self.assertIn('class="sw-row y"', html)
        self.assertIn(">3 for you<", html)
        self.assertIn("4 running · 1 later · sorted 14:01", html)
        self.assertIn('id="sarow"', html)
        zero = render(self.SUP + "snap.super.for_you = 0; snap.super.rev = 'r2'; swRow()")
        self.assertIn('class="sw-cnt z">0 for you<', zero)
        self.assertNotIn('class="sw-row y"', zero)

    def test_one_count_the_view_when_in_sync_else_the_snapshot(self):
        x = self.SUP + "superView = {rev: 'r1', counts: {queue: 2}, by_project: {'D:\\\\p': 2}}; "
        self.assertEqual(render(x + "forYou()"), 2)                      # in sync: the accurate view
        self.assertEqual(render(x + "snap.super.rev = 'r9'; forYou()"), 3)  # out of sync: the snapshot
        self.assertEqual(render(x + "forYouIn('d:/P')"), 2)               # project match goes through sameDir
        self.assertEqual(render("snap = {counts: {needs: 4}}; superView = null; forYou()"), 4)  # an old service: the raw count

    def test_header_button_is_never_hidden_and_says_for_you(self):
        got = render(self.SUP + """const b = {hidden: true, className: '', textContent: ''}; document = {getElementById: (id) => id === 'needsbtn' ? b : {}};
          swHeader(); [b.hidden, b.className, b.textContent]""")
        self.assertEqual(got, [False, "needs", "3 for you"])
        got = render(self.SUP + """const b = {hidden: true, className: '', textContent: ''}; document = {getElementById: (id) => id === 'needsbtn' ? b : {}};
          snap.super.for_you = 0; swHeader(); [b.hidden, b.className, b.textContent]""")
        self.assertEqual(got, [False, "needs z", "0 for you"])

    def test_fetch_only_for_a_new_rev_a_forced_call_or_thirty_seconds(self):
        x = self.SUP + "Date.now = () => 100000; "
        self.assertTrue(render(x + "swNeed()"))                          # nothing fetched yet
        self.assertFalse(render(x + "superView = {rev: 'r1'}; swWant = 'r1'; superAt = 99000; swNeed()"))   # same rev, fresh: no loop
        self.assertTrue(render(x + "superView = {rev: 'r1'}; swWant = 'r0'; superAt = 99000; swNeed()"))    # the snapshot moved
        self.assertTrue(render(x + "superView = {rev: 'r1'}; swWant = 'r1'; superAt = 60000; swNeed()"))    # the 30 s refresh
        self.assertFalse(render("snap = {counts: {needs: 1}}; swNeed()"))                                  # an old service

    def test_a_fetch_that_fails_does_not_loop(self):
        got = render(self.SUP + """(async () => { let calls = 0; api = async () => { calls++; throw new Error('down'); }; renderBoard = () => {};
          await swFetch(); await swFetch(); return calls; })()""")
        self.assertEqual(got, 1)  # swWant records the rev even on failure

    def test_project_line_is_quiet_until_something_is_for_you(self):
        setup = BoardListTest.setup + self.SUP + "projectName = (d) => d; boardTask = ''; swSel = ''; swOpenP = {}; swAllP = {}; "
        quiet = render(setup + "swProjectBlock('D:\\z', {live: [mkt({id: 'r1'}), mkt({id: 'r2'})], obs: [], today: [], earlier: [], ts: 0})")
        self.assertIn('aria-expanded="false"', quiet)
        self.assertIn("2 running", quiet)
        self.assertNotIn("for you", quiet)
        mine = render(setup + "swProjectBlock('D:\\p', {live: [mkt({id: 'a'}), mkt({id: 'r1'}), mkt({id: 'r2'})], obs: [], today: [], earlier: [], ts: 0})")
        self.assertIn("<b>2 for you</b>", mine)
        self.assertIn('aria-expanded="true"', mine)
        self.assertIn("+ 2 more: 2 running", mine)       # a is shown, the two quiet ones fold into one line
        self.assertEqual(mine.count('data-btask="a"'), 1)

    def test_the_counts_on_screen_agree(self):
        got = render(self.SUP + """superView = {rev: 'r1', counts: {queue: 3}, by_project: {'D:\\\\p': 2, 'D:\\\\q': 1}};
          projectName = (d) => d;
          const sum = ['D:\\\\p', 'D:\\\\q'].reduce((a, d) => a + forYouIn(d), 0);
          [forYou(), sum, swRow().includes('>3 for you<')]""")
        self.assertEqual(got, [3, 3, True])

    def test_a_later_task_row_says_when_it_is_back(self):
        x = self.SUP + "boardTask = ''; "
        self.assertEqual(render(x + "statusLine({id: 'z', state: 'waiting', why: '', asks: '', group: 'needs'})[0]"), "later · back 15:06")

    def test_list_html_starts_with_the_row_and_has_no_pin(self):
        html = render(self.SUP + "projectName = (d) => d; boardTask = ''; swSel = ''; scope = ''; listHtml()")
        self.assertTrue(html.lstrip().startswith('<button class="sw-row'))
        for gone in ("needsec", "p-pin", "Needs you ·", "Running ·", "Done today"):
            self.assertNotIn(gone, html)

    def test_selecting_the_row_twice_leaves_it_and_a_project_row_selects_the_new_work_target(self):
        got = render(self.SUP + """renderBoard = () => {}; boardTask = ''; boardPick = ''; swSel = '';
          const el = (d) => ({dataset: d, getAttribute: () => 'false'}); const seq = [];
          swClick(el({sw: 'row'})); seq.push(swSel); swClick(el({sw: 'row'})); seq.push(swSel);
          swClick(el({sw: 'proj', dir: 'D:\\\\q'})); seq.push(swSel, swProj, swOpenP['D:\\\\q']); seq""")
        self.assertEqual(got, ["sa", "", "p", "D:\\q", True])
```

(Steps under the picked task only: checked in the headless sweep below, where the real `taskHtml` runs.)

Edits to existing tests in the same commit: `BoardListTest` tests that assert `chainHtml` groups ("Running ·", "Done
today", the pin) are replaced by the plan 55 Task 4 versions adapted above; `test_web.py` lines asserting
`needsbtn` text `need you` read `for you`.

Headless: `tests/live_super_check.py` is created here with the plan 55 Rig and one check, `list_checks`:

```python
def list_checks(page, name):  # Task 4: the row first, one number, steps only under the picked task, 24 px targets
    assert page.locator("#bchain .sw-row").count() == 1, (name, "one super agent row")
    first = page.evaluate("document.querySelector('#bchain').firstElementChild.className")
    assert "sw-row" in first, (name, "the row is first")
    n = page.evaluate("document.querySelector('#sarow .sw-cnt').textContent")
    assert n == page.evaluate("document.querySelector('#needsbtn').textContent"), (name, "row and header agree", n)
    page.evaluate("showPage('board'); boardTask = ''; boardPick = ''; swSel = ''; renderBoard()")
    assert page.locator("#bchain .p-sub, #bchain .v-sr").count() == 0, (name, "no steps with nothing picked")
```

## 4.2 Code (`web/app.js`)

Insert as one block right after `function taskGroup(t) {` (the list code's neighbours), so it sits with the grouping code.

```js
// -- plan 59: the super agent window. Counts come from snap.super or the view, never from a gate ----------------------
let superView = null;   // the last GET /api/super (queue, later, since, controls, ...)
let superAt = 0;        // when it arrived (ms)
let superBusy = false;
let swWant = "";        // the snapshot rev the last fetch answered: the same rev never fetches again (no loop)
let swSel = "";         // the home pane's selection: "" nothing, "sa" the super agent row, "p" a project row
let swProj = "";        // the selected project row's directory: the New work target
let swOpenP = {};       // project dir -> open (this window only)
let swAllP = {};        // project dir -> its "+ N more" line is open
const SW_REFRESH_MS = 30000;  // served `off` reasons and the time left on a default age: refetch while the page shows

const swReady = () => !!(snap && snap.super);
const swInSync = () => !!superView && swReady() && superView.rev === snap.super.rev;
const swMark = (id) => (swReady() && snap.super.marks && snap.super.marks[id]) || null;  // ["queue"] or ["later", "HH:MM"]
function forYou() { return swInSync() ? superView.counts.queue : swReady() ? snap.super.for_you : snap && snap.counts ? snap.counts.needs : 0; }
function forYouIn(dir) {
  const by = swInSync() ? superView.by_project : swReady() ? snap.super.by_project : {};
  return Object.entries(by || {}).filter(([d]) => sameDir(d, dir)).reduce((a, [, n]) => a + n, 0);
}
function swNeed() { return swReady() && (snap.super.rev !== swWant || Date.now() - superAt > SW_REFRESH_MS); }
async function swFetch(force = false) {
  if (superBusy || !swReady() || !(force || swNeed())) return;
  superBusy = true;
  const want = snap.super.rev;
  try { superView = await api("/api/super"); } catch (e) { /* the snapshot's count stays */ }
  swWant = want;      // also after a failure, and superAt too: one try per rev and per 30 s, never a loop
  superAt = Date.now();
  superBusy = false;
  renderBoard();
}
function swHeader() {  // SW-2: the header button is the same number, muted at 0, never hidden
  const n = forYou(), b = $("needsbtn");
  b.hidden = false;
  b.className = "needs" + (n ? "" : " z");
  b.textContent = `${n} for you`;
}
function swHome() { return page === "board" && !boardTask && !boardPick; }
function swRow() {  // SW-1: the first row of the list, always there
  const n = forYou(), sel = swSel === "sa", line = swReady() ? snap.super.line : "";
  return `<button class="sw-row${n ? " y" : ""}${sel ? " pick" : ""}" id="sarow" data-sw="row"${swHome() ? ' aria-current="page"' : ""} aria-pressed="${sel}"
    title="${sel ? "Selected: the box talks to the super agent. Select again to leave it." : "Open the super agent; select it to talk to it"}">
    <span class="l1"><span class="sw-dm" aria-hidden="true">◆</span><span class="t">Super agent</span><span class="sw-cnt${n ? "" : " z"}">${n} for you</span></span>
    <span class="l2">${esc(line)}</span></button>`;
}
function swQuiet(g, max = 9) {  // "2 running · 1 paused": what a project holds when nothing in it is for Fred
  const rows = [...g.live, ...g.today, ...g.earlier], n = { run: 0, paused: 0, done: 0, later: 0 };
  for (const x of rows) {
    const m = swMark(x.id);
    if (m && m[0] === "later") n.later++;
    else if (x.group === "done" || x.accepted) n.done++;
    else if (x.owner === "fred" && x.steps) n.paused++;
    else n.run++;
  }
  const chats = g.obs.length;
  return [n.run && `${n.run} running`, n.paused && `${n.paused} paused`, n.done && `${n.done} done`, n.later && `${n.later} later`,
    chats && `${chats} ${chats > 1 ? "chats" : "chat"}`].filter(Boolean).slice(0, max).join(" · ") || "nothing live";
}
function swProjectBlock(dir, g) {  // SW-12: one line while quiet; for-you rows and one "more" line when something is for Fred
  const n = forYouIn(dir), selP = swSel === "p" && sameDir(swProj, dir);
  const selT = !!boardTask && [...g.live, ...g.today].some((x) => x.id === boardTask);
  const open = dir in swOpenP ? swOpenP[dir] : n > 0 || selP || selT;
  let h = `<button class="sw-prj${selP ? " pick" : ""}" data-sw="proj" data-dir="${esc(dir)}" aria-expanded="${open}"><span class="car" aria-hidden="true">${open ? "▾" : "▸"}</span>
    <span class="nm" title="${esc(dir)}">${esc(projectName(dir))}</span><span class="sum">${n ? `<b>${n} for you</b>` : esc(swQuiet(g, 1))}</span></button>`;
  if (!open) return h;
  const item = (x) => (x.kind === "review" ? reviewHtml(x) : x.steps ? taskHtml(x) : x.raw !== undefined ? prepTaskHtml(x) : sessionRow(x));
  const mine = (x) => { const m = swMark(x.id); return !!m && m[0] === "queue"; };
  const all = selP || swAllP[dir] || n === 0;
  const shown = all ? g.live : g.live.filter((x) => mine(x) || x.id === boardTask);
  h += shown.map(item).join("") + g.obs.map(sessionRow).join("");
  const hidden = g.live.filter((x) => !shown.includes(x));
  if (hidden.length) h += `<button class="sw-more" data-sw="more" data-dir="${esc(dir)}">+ ${hidden.length} more: ${esc(swQuiet({ live: hidden, obs: [], today: [], earlier: [] }))}</button>`;
  h += g.today.map(item).join("");   // plan 55 D10 a: today's done rows, then the "Done earlier" fold
  if (g.earlier.length) {
    const fold = earlierOpen.has(dir);
    h += `<button class="p-earlier" data-earlier="${esc(dir)}" aria-expanded="${fold}">Done earlier · ${g.earlier.length}<span class="car">&#9662;</span></button>`;
    if (fold) for (const [k, rows, ss] of doneDays(g.earlier.filter((x) => x.steps), g.earlier.filter((x) => !x.steps))) h += dayGroup(k, rows, ss);
  }
  return h;
}
function swClick(el) {  // the delegated click of the row, a project line and "+ N more"
  const d = el.dataset;
  if (d.sw === "row") { swSel = swSel === "sa" ? "" : "sa"; boardTask = ""; boardPick = ""; swAnswerTo = ""; renderBoard(); }
  else if (d.sw === "proj") {
    const isSel = swSel === "p" && sameDir(swProj, d.dir), open = el.getAttribute("aria-expanded") === "true";
    if (isSel) swOpenP[d.dir] = !open; else { swSel = "p"; swProj = d.dir; swOpenP[d.dir] = true; project = d.dir; saveDraft(); }  // the New work target
    boardTask = ""; boardPick = ""; swAnswerTo = ""; renderBoard();
  } else if (d.sw === "more") { swAllP[d.dir] = true; renderBoard(); }
}
```

`projectGroups()` is plan 55 Task 4's body (README 55 section 1.1) with one change, written here because that task is not built:

```js
let earlierOpen = new Set();  // the project groups whose "Done earlier" fold is open (this window only)
function projectGroups() {  // [[dir, {live, obs, today, earlier, ts}]] in scope, newest activity first
  const today = todayKey(), by = new Map();
  const at = (dir) => { const k = [...by.keys()].find((x) => sameDir(x, dir)) ?? dir; if (!by.has(k)) by.set(k, { live: [], obs: [], today: [], earlier: [], ts: 0 }); return by.get(k); };
  for (const t of (snap.tasks || []).filter(taskInScope)) {
    const g = at(t.project_dir), grp = taskGroup(t);
    g.ts = Math.max(g.ts, t.updated);
    if (grp === "done") (dayOf(t.updated) === today ? g.today : g.earlier).push(t);
    else g.live.push(t);                       // a task for Fred stays in its project: the pin is gone
  }
  for (const j of prepRows().filter((x) => x.state === "running")) { const g = at(j.project_dir); g.live.unshift(j); g.ts = Math.max(g.ts, j.ts); }
  for (const s of snap.sessions.filter((x) => inScope(x) && !x.task && !x.chat_task && x.group !== "empty")) {
    const g = at(s.project_dir);
    g.ts = Math.max(g.ts, s.last_ts);
    if (s.group === "done") (dayOf(s.last_ts) === today ? g.today : g.earlier).push(s);
    else if (s.group === "needs") g.live.push(s);
    else g.obs.push(s);
  }
  return [...by.entries()].sort((a, b) => b[1].ts - a[1].ts);
}
```

`listHtml()` replaces `chainHtml` (and `chainGroups`, `secHtml`, which have no other caller after this: `grep -n` them):

```js
function listHtml() {  // SW-1, SW-12: the super agent row, then one rolled-up block per project
  let html = swRow();
  for (const [dir, g] of projectGroups()) html += swProjectBlock(dir, g);
  const older = snap.older || 0;  // unchanged from chainHtml: the Older row, then the empty chats behind the header menu
  if (older) {
    html += `<div class="v-sec${olderOpen ? "" : " fd"}"><button class="dh" data-older aria-expanded="${olderOpen}" title="Tasks finished more than ${OLDER_DAYS} days ago; they open in place, by day"><span class="lbl">Older · ${older}</span><span class="car">&#9662;</span></button></div>`;
    if (olderOpen) html += !olderRows ? '<p class="note m">Reading the older tasks.</p>' : doneDays(olderRows.tasks.filter(taskInScope), []).map(([k, rows]) => dayGroup(k, rows, [])).join("");
  }
  if (emptyOpen) html += groups().empty.map((s) => quietHtml(s, !scope)).join("");
  return html;
}
```

Edits by anchor:

- `renderBoard()`: replace the three lines from `  const nb = snap.counts.needs;` through the line that sets `$("needsbtn").textContent` by `  swHeader();` and `swFetch();` on the next line; replace `setHtml($("bchain"), chainHtml());` by `setHtml($("bchain"), listHtml());`; delete the `homePick();` line if plan 55 Task 4 had added it (it is not built: nothing to delete).
- `function statusLine(t) {`: first line of the body `const m = swMark(t.id); if (m && m[0] === "later") return [\`later · back ${m[1]}\`, ""];`.
- `function taskHtml(t, o = {})`: the line that appends the step rows (`stepRows(t)`) is guarded by `&& t.id === boardTask` (SW-12: steps only under the selected task).
- `go("needs")` becomes `if (name === "needs") { swSel = "sa"; boardTask = ""; boardPick = ""; renderBoard(); const c = document.querySelector("#bwrap .sw-qc.cur"); if (c) c.focus(); }` (the header button selects the super agent row and focuses the current card, Task 5).
- The click handler's selector string (`const t = e.target.closest("[data-prep],[data-go],`): add `[data-sw],` and `[data-earlier],`; before `else if (t.dataset.tact)`: `else if (t.dataset.sw) swClick(t);` (Task 6 makes it `swAct(t)`) and `else if (t.dataset.earlier !== undefined) { const k = t.dataset.earlier; if (earlierOpen.has(k)) earlierOpen.delete(k); else earlierOpen.add(k); renderBoard(); }`.
- Opening any task (`openTask`, `data-bpick`) sets `swSel = ""`.

`web/index.html`: the line `<button id="needsbtn" class="needs" data-go="needs" title="Show what needs you, in every project" hidden></button>` loses `hidden` and its title becomes `Open the super agent: what needs you, in every project`.

## 4.3 Style (`web/style.css`, appended, tokens unchanged)

```css
/* plan 59: the super agent row, project lines and "+ N more" (locked mock: .sa, .prj, .more; prefix sw-) */
.sw-row { display: block; width: calc(100% - 16px); margin: 8px 8px 4px; padding: 7px 10px; text-align: left; border: 1px solid var(--line);
  border-radius: 8px; background: var(--win); color: var(--ink); font: inherit; cursor: pointer; }
.sw-row:hover { background: var(--raise); }
.sw-row.pick, .sw-row[aria-current="page"] { border-color: var(--ink); }
.sw-row.y { border-color: color-mix(in srgb, var(--you) 55%, var(--line)); }
.sw-row .l1 { display: flex; align-items: center; gap: 8px; min-width: 0; }
.sw-dm { color: var(--mut); font-size: 12px; }
.sw-row .t { font: 600 13px var(--ui); flex: 1; min-width: 0; }
.sw-cnt { font: 600 12px var(--mono); color: var(--you); white-space: nowrap; }
.sw-cnt.z { color: var(--mut); }
.sw-row .l2 { display: block; margin-top: 2px; font: 12px var(--ui); color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sw-prj { display: flex; align-items: center; gap: 6px; width: 100%; min-height: 28px; padding: 6px 12px 4px; border: 0; background: none;
  color: var(--ink); font: inherit; text-align: left; cursor: pointer; }
.sw-prj:hover, .sw-prj.pick { background: var(--raise); }
.sw-prj .car { color: var(--mut); width: 12px; }
.sw-prj .nm { flex: 1; min-width: 0; font: 600 11px var(--mono); letter-spacing: .02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sw-prj .sum { font: 11px var(--mono); color: var(--mut); white-space: nowrap; }
.sw-prj .sum b { font-weight: 600; color: var(--you); }
.sw-more { display: block; width: calc(100% - 16px); margin: 2px 8px 4px; min-height: 24px; padding: 2px 9px; border: 0; border-radius: 5px; background: none;
  color: var(--mut); font: 11px var(--mono); text-align: left; cursor: pointer; }
.sw-more:hover { background: var(--raise); color: var(--ink); }
.needs.z { color: var(--mut); }
.p-earlier { display: flex; justify-content: space-between; align-items: center; width: calc(100% - 16px); min-height: 24px; margin: 2px 8px 4px;
  padding: 2px 9px; border: 0; border-radius: 5px; background: transparent; color: var(--mut); font: 11px var(--mono); cursor: pointer; }
.p-earlier:hover { background: var(--raise); color: var(--ink); }
.p-earlier[aria-expanded="true"] .car { transform: rotate(180deg); }
@media (prefers-reduced-motion: no-preference) { :root:not([data-motion="reduce"]) :is(.sw-row, .sw-prj) { transition: border-color .12s, background-color .12s; } }
```

Check while building: the 11 px floor holds for every rule above (plan 38 D4 b); `.needs.z` keeps the button's size.

## 4.4 Steps and acceptance

- [ ] 1. Write `SuperListTest` and `tests/live_super_check.py`; run `py -m unittest tests.test_web.SuperListTest`: red for the missing functions.
- [ ] 2. Make the 4.2 and 4.3 edits. `node --check web/app.js`; `py -m unittest tests.test_web`; `py -m tests.live_super_check`
      (900, 400, 340 px, dark and light, reduced motion, 130 %: no horizontal scroll, the row first, the two numbers equal).
- [ ] 3. Full suite green (report the count). Stage `tests/test_web.py`, `tests/live_super_check.py` and only this
      task's hunks of `web/app.js`, `web/style.css`, `web/index.html`. Commit with the message above.
