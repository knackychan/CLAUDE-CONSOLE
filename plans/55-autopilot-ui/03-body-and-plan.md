# Task 3: the body sections and the plan timeline (UI-4, UI-5)

Files: `web/app.js`, `web/style.css`, `tests/test_web.py`, `tests/live_board_check.py`; with D7 a also
`console/tasks.py`, `console/server.py` (`_task`), `tests/test_server.py`. Commit boundary: `feat: the opened task's
sections and plan timeline (plan 55 Task 3)`. Depends on Task 2 and on Fred's answer at stop 1. Assumes D7 a, D8 a, D9 a.

What the user gets: the opened task reads top-down as locked: Prompt (Fred's words), Brief (Prep's text with the route
as chips), Plan (one row per step with a plain check word and its cost, each row a link to its step page, and the
supervisor's actions as muted `◆ Supervisor` lines where they happened). The route of sprite rows, the 30-cell gauge
(moved to the bar in Task 2), the Goal fold and the quiet "Supervisor · last decision" card go.

## 1. D7 a: one read field (server)

`console/tasks.py`, after `def read_brief(`'s function:

```python
def read_prompt(home, task: dict) -> str:
    """Plan 55 D7: the task's prompt.md as Fred typed it (plan 29 writes it when the prompt is sent), masked; "" when absent."""
    try:
        return redact.mask((folder(home, task["id"]) / "prompt.md").read_text(encoding="utf-8")).strip()
    except OSError:
        return ""
```

`console/server.py` `def _task(self, task_id: str):`, in the `self._json({...})` dict, after the line
`"brief": tasks.read_brief(self.hub.folder, task, last),` add:

```python
                           "prompt": tasks.read_prompt(self.hub.folder, task),  # plan 55 D7: a read, nothing starts
```

Test first, `tests/test_server.py` in `class ActionsServerTest(TaskServerTest):`:

```python
    def test_task_get_serves_the_typed_prompt(self):
        task = self.saved_task("running")
        tasks.save(self.folder, task)
        (self.folder / "tasks" / task["id"] / "prompt.md").write_text("fix the 340 px overflow\n", encoding="utf-8")
        self.assertEqual(self.task(task["id"])[1]["prompt"], "fix the 340 px overflow")
        (self.folder / "tasks" / task["id"] / "prompt.md").unlink()
        self.assertEqual(self.task(task["id"])[1]["prompt"], "")
```

## 2. Code (`web/app.js`)

### 2.1 The parts (insert after `function taskShell(` from Task 2)

```js
ICON.copy = '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 3.5v-.5a1.5 1.5 0 0 0-1.5-1.5H4A1.5 1.5 0 0 0 2.5 3v5A1.5 1.5 0 0 0 4 9.5h.5"/>';
let svOpen = "";  // "<task>|<wake>": the supervisor line whose record is open in place
function sect(label, sub, body, cls = "") {  // UI-4: label column (name, one muted line), a hairline, the body (plan 53 reuses it)
  return `<section class="p-sect${cls ? " " + cls : ""}"><div class="sh"><span class="lbl">${esc(label)}</span>${sub ? `<span class="sm">${sub}</span>` : ""}</div><div class="sb">${body}</div></section>`;
}
function foldLine(key, text, extra = "") {  // UI-4: one line; opened, a selectable box about 5 lines tall with a copy icon, then `extra`
  const open = foldOpen(key, false);
  return `<div class="p-tx"><button class="car" data-txfold="${esc(key)}" aria-expanded="${open}" aria-label="${open ? "Fold" : "Open"}">${open ? "▾" : "▸"}</button>
    ${open ? `<div class="p-txt"><div class="tt">${esc(text)}</div><button class="p-cp" data-turncopy data-text="${esc(text)}" title="Copy to clipboard" aria-label="Copy to clipboard">${svgIcon("copy")}</button></div>${extra}`
      : `<button class="pv" data-txfold="${esc(key)}" aria-expanded="false">${esc(text)}</button>`}</div>`;
}
const CHECK = { passed: ["✓ passed", "g"], done: ["✓ done", "n"], failed: ["✕ failed", "r"], running: ["▸ running", "n"], replied: ["▸ replied", "n"],
  asks: ["? asks you", "y"], held: ["? held", "y"], waiting: ["? waits for you", "y"], planned: ["· queued", "q"] };
function planRow(o) {  // UI-5: rail mark, number, kind, model, the plain check word, cost; the whole row opens the step (plan 53 reuses it)
  return `<div class="p-st${o.cls ? " " + o.cls : ""}" data-bpick="s${o.n}" data-btask="${esc(o.tid)}" tabindex="0" role="button" title="Open step ${two(o.n)}">
    <span class="dt">${o.mark}</span><span class="n">${two(o.n)}</span><span class="what"><b>${esc(o.kind)}</b>${o.route ? `<span class="rt">${esc(o.route)}</span>` : ""}<span class="g">${esc(o.goal)}</span></span>
    <span class="chk ${o.check[1]}">${o.check[0]}</span><span class="c">${esc(o.cost)}</span><span class="go" aria-hidden="true">›</span></div>`;
}
function stepCheck(t, s, A) {
  const shown = stepShown(t, s, boardRow(t.id));
  if (s.verdict === "PASS") return CHECK.passed;
  if (shown === "failed") return CHECK.failed;
  if (s.n === t.current && A.state === "decision") return CHECK.asks;
  if (s.n === t.current && A.state === "hold") return CHECK.held;
  return CHECK[shown] || CHECK.planned;
}
function svLine(a, t) {  // UI-5: a supervisor action where it happened, muted; it opens its record in place (Folder holds supervisor.jsonl)
  const key = `${t.id}|${a.wake}`, open = svOpen === key;
  return `<button class="p-sv" data-sv="${esc(key)}" aria-expanded="${open}" title="The supervisor's record of wake ${esc(a.wake)}"><span class="sg">◆</span><span>Supervisor</span>
    <span class="tx2">${esc(decisionText({ decision: a.decision }, t))}${a.status ? " · " + esc(a.status) : ""}</span><span class="tm">${a.ts ? hhmm(a.ts) : ""}</span></button>
    ${open ? `<div class="p-svd m">wake ${esc(a.wake)} · ${esc(a.phase)} · ${esc(a.status || "")}${a.cost ? " · $" + Number(a.cost).toFixed(3) : ""}${a.error ? " · " + esc(a.error) : ""}</div>` : ""}`;
}
function planTimeline(t, d) {  // one row per step in chain order; each wake's last decision after the step that had started when it was taken
  const A = acts(d), row = boardRow(t.id), byWake = new Map();
  for (const a of (d.supervisor || {}).audit || []) if (a.decision && a.ts) byWake.set(a.wake, a);
  const after = (a) => { let k = -1; t.steps.forEach((s, j) => { if (s.started && s.started <= a.ts) k = j; }); return k; };
  const lines = [...byWake.values()].sort((x, y) => x.ts - y.ts);
  let html = lines.filter((a) => after(a) < 0).map((a) => svLine(a, t)).join("");
  t.steps.forEach((s, j) => {
    const pl = s.state === "planned", check = stepCheck(t, s, A), shown = stepShown(t, s, row);
    html += planRow({ tid: t.id, n: s.n, kind: s.kind, goal: s.goal || "", check, mark: sprite(SR_SPRITE[shown] || "planned"),
      route: pl ? "" : modelText(rungOf(s.harness, s.model), s.effort), cost: pl ? "" : costUnknown(s) ? "?" : "$" + money(s.cost),
      cls: [pl ? "q" : "", check[1] === "r" ? "fail" : check[1] === "y" ? "wait" : ""].filter(Boolean).join(" ") });
    html += lines.filter((a) => after(a) === j).map((a) => svLine(a, t)).join("");
  });
  return `<div class="p-tl">${html}</div>`;
}
const REASONING = { high: "Deep reasoning", medium: "Some reasoning", low: "Light reasoning" };  // README 4.3: new words
function briefExtra(t, d) {  // the route as plain chips (D8 a: all ink), the changed files as a fold of names
  const route = (t.prep && t.prep.route) || {}, dm = t.demand || {}, cap = (w) => w ? w[0].toUpperCase() + w.slice(1) : "";
  const chips = [cap(t.type), REASONING[dm.reasoning] || "", route.model ? `${cap(alias(route.model) || route.model)}, ${route.effort || "auto"} effort` : ""].filter(Boolean);
  const files = (d.summary && d.summary.files) || [];
  return `<div class="p-open">${chips.length ? `<div class="p-chips">${chips.map((c) => `<span class="p-chip">${esc(c)}</span>`).join("")}</div>` : ""}
    ${files.length ? fold(`${files.length} ${files.length === 1 ? "file" : "files"} changed`, "", `<ul class="p-files">${files.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>`, { key: "tfiles" }) : ""}</div>`;
}
function taskBody(t, d) {  // UI-4: Prompt, Brief, Plan, then the open questions; one section pattern
  const p = t.prep && typeof t.prep === "object" ? t.prep : null, n = t.steps.length;
  const prompt = d.prompt ? sect("Prompt", `you, ${hhmm(t.created || t.updated)}`, foldLine("tprompt", d.prompt)) : "";
  const brief = sect("Brief", p && p.state !== "skipped" ? `<button class="olink" data-bpick="p" data-btask="${esc(t.id)}" title="Step 00: the Prep card">prep · ${esc(alias(p.model) || p.model || "haiku")}</button>` : "as typed",
    foldLine("tbrief", t.goal, briefExtra(t, d)));
  const planMd = d.plan && t.plan ? fold("plan.md", `${Number(t.plan.words || 0).toLocaleString("en")} w`, planOpenHtml(t, d, t.steps.find((x) => x.n === t.current), { board: true }), { key: "tplanmd" }) : "";
  const plan = sect("Plan", `${n} ${n === 1 ? "step" : "steps"}`, planTimeline(t, d) + planMd);
  const qs = d.questions || [], open = qs.filter((q) => !q.closed);
  const questions = qs.length ? sect("Questions", `${open.length} open`, `<div class="oq">${[...open, ...qs.filter((q) => q.closed)].map((q) => `<div class="oqr${q.closed ? " closed" : ""}"><span class="gl">${q.closed ? "✓" : "?"}</span><span>${esc(q.q)}</span><span class="m">opened ${two(q.opened)}${q.closed ? " · closed " + two(q.closed) : ""}</span></div>`).join("")}</div>`) : "";
  return prompt + brief + plan + questions;
}
```

### 2.2 `inspTask` and what goes

In `function inspTask(t, d, row)` replace

```js
    ${supCard(t, d)}${routeHtml(t, d, row)}${fold("Goal", "", `<pre class="text goal">${esc(t.goal)}</pre>`, { key: "tgoal" })}${questionsFold(d)}`;
```

by

```js
    ${taskBody(t, d)}`;
```

Delete, each whole: `function routeHtml(`, `function supCard(`, `function supFine(` (unused now), `function questionsFold(`.
Keep `SUP_HEAD` and `decisionText` (the dock card and the supervisor lines use them).

The click handler: add `[data-txfold],[data-sv],` to the selector and, before the `data-optpick` branch:

```js
  else if (t.dataset.txfold) { foldState[t.dataset.txfold] = !foldOpen(t.dataset.txfold, false); saveFolds(); renderBoard(); }
  else if (t.dataset.sv) { svOpen = svOpen === t.dataset.sv ? "" : t.dataset.sv; renderBoard(); }
```

The plan rows reuse `data-bpick="s<n>"`, so the existing click and keyboard paths (`boardKey`, `boardItems`) open the
step: `boardItems()` lists `#bchain [data-bpick]` only, so arrow keys stay on the list; Enter and Space on a focused
`.p-st` go through the existing `keydown` handler for `[role="button"]` (check it: if it is limited to `.v-th`, add
`.p-st` to that selector in the same commit).

## 3. Style (`web/style.css`, append)

```css
/* plan 55: one section pattern (UI-4) and the plan as a step timeline (UI-5) */
.p-sect { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 0 14px; padding: 12px 0; border-top: 1px solid var(--line); }
.p-sect .sh { display: grid; align-content: start; gap: 2px; padding-top: 1px; }
.p-sect .sh .lbl { color: var(--ink); font-size: 11px; }
.p-sect .sh .sm { font: 11px var(--mono); color: var(--mut); }
.p-sect .sh .olink { justify-self: start; font: 11px var(--mono); }
.p-sect .sb { min-width: 0; display: grid; gap: 8px; grid-template-columns: minmax(0, 1fr); }
@container (max-width: 520px) { .p-sect { grid-template-columns: minmax(0, 1fr); gap: 6px; } .p-sect .sh { display: flex; gap: 8px; } }
.p-tx { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 0 4px; align-items: start; }
.p-tx .car { min-height: 24px; background: none; border: 0; color: var(--mut); font: 11px var(--mono); cursor: pointer; text-align: left; }
.p-tx .pv { grid-column: 2; min-height: 24px; background: none; border: 0; border-radius: 4px; padding: 2px 4px; margin-left: -4px; text-align: left;
  font: 13px var(--ui); color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; min-width: 0; }
.p-tx .pv:hover, .p-tx .car:hover { color: var(--ink); background: var(--raise); }
.p-txt { grid-column: 2; position: relative; background: var(--raise); border: 1px solid var(--line); border-radius: 6px; }
.p-txt .tt { max-height: 116px; overflow-y: auto; padding: 8px 36px 8px 10px; font: 13px/1.55 var(--ui); user-select: text; cursor: text; white-space: pre-wrap; scrollbar-width: thin; }
.p-cp { position: absolute; top: 5px; right: 6px; width: 24px; height: 24px; display: grid; place-items: center; border: 0; border-radius: 4px; background: var(--raise); color: var(--mut); cursor: pointer; }
.p-cp:hover { background: var(--off); color: var(--ink); }
.p-open { grid-column: 2; display: grid; gap: 10px; }
.p-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.p-chip { font: 12px var(--ui); padding: 2px 9px; border-radius: 10px; background: var(--raise); color: var(--ink); }
.p-tl { display: grid; grid-template-columns: minmax(0, 1fr); }
.p-st { position: relative; display: grid; grid-template-columns: 16px 22px minmax(0, 1fr) auto auto 10px; gap: 0 10px; align-items: baseline;
  padding: 7px 8px; margin: 0 -8px; border-radius: 6px; cursor: pointer; }
.p-st:hover, .p-st:focus-visible { background: var(--raise); }
.p-st:focus-visible { outline: 2px solid var(--ink); outline-offset: -2px; }
.p-st::before { content: ""; position: absolute; left: 15px; top: 24px; bottom: -7px; width: 1px; background: var(--line); }
.p-st:last-of-type::before { display: none; }
.p-st .dt { align-self: center; position: relative; z-index: 1; }
.p-st .n, .p-st .rt, .p-st .chk, .p-st .c { font: 11px var(--mono); color: var(--mut); white-space: nowrap; }
.p-st .what { min-width: 0; }
.p-st .what b { font-weight: 600; font-size: 13px; }
.p-st .rt { margin-left: 6px; }
.p-st .g { display: block; color: var(--mut); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.p-st .chk.g { color: var(--ok); } .p-st .chk.r { color: var(--bad); } .p-st .chk.y { color: var(--you); } .p-st .chk.n { color: var(--ink); }
.p-st .c { width: 52px; text-align: right; }
.p-st .go { color: var(--mut); font: 14px var(--ui); opacity: 0; }
.p-st:hover .go, .p-st:focus-visible .go { opacity: 1; color: var(--ink); }
.p-st:hover .what b { text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--mut); }
.p-st.q .what b { color: var(--mut); font-weight: 400; }
@media (prefers-reduced-motion: no-preference) { .p-st { transition: background-color .12s; } .p-st .go { transition: opacity .12s; } }
.p-sv { display: grid; grid-template-columns: 16px auto minmax(0, 1fr) auto; gap: 8px; align-items: baseline; width: calc(100% + 16px); min-height: 24px;
  margin: 0 -8px; padding: 5px 8px; border: 0; border-radius: 6px; background: transparent; color: var(--mut); font: 12px var(--ui); text-align: left; cursor: pointer; }
.p-sv:hover { background: var(--raise); color: var(--ink); }
.p-sv .sg { font: 11px var(--mono); text-align: center; }
.p-sv span:nth-child(2) { font: 600 11px var(--mono); }
.p-sv .tx2 { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.p-sv .tm { font: 11px var(--mono); }
.p-svd { padding: 2px 8px 6px 34px; color: var(--mut); overflow-wrap: anywhere; }
@container (max-width: 420px) { .p-st { grid-template-columns: 16px 22px minmax(0, 1fr) auto 10px; } .p-st .c { display: none; } }
```

The Prompt and Brief lines follow plan 38 Task 8's rule (caret, pointer, raise hover); their preview text stays muted
because it is content, not a label (flagged for Fred at stop 2).

## 4. Tests

New, `tests/test_web.py`:

```python
@unittest.skipUnless(NODE, "Node is not installed")
class AutopilotBodyTest(unittest.TestCase):
    """Plan 55 Task 3: Prompt, Brief, Plan as one section pattern; the plan is a timeline of links with supervisor lines."""
    setup = AutopilotDockTest.setup + """d.actions = A('running', [], []); d.prompt = 'fix the overflow';
      t.created = 0; t.type = 'risky'; t.demand = {reasoning: 'high'}; t.prep = {state: 'done', model: 'haiku', route: {model: 'opus', effort: 'high'}};
      t.steps[0].started = 10; t.steps[0].cost = 0.01; t.steps[0].model = 'haiku'; t.steps[0].verdict = 'PASS'; """

    def test_sections_in_order_and_folded(self):
        html = render(self.setup + "taskBody(t, d)")
        self.assertLess(html.index(">Prompt<"), html.index(">Brief<"))
        self.assertLess(html.index(">Brief<"), html.index(">Plan<"))
        self.assertIn('class="pv" data-txfold="tprompt"', html)
        self.assertNotIn("p-chip", html)  # the chips show only when the Brief is open
        opened = render(self.setup + "foldState.tbrief = true; taskBody(t, d)")
        self.assertIn('class="p-chip">Risky<', opened)
        self.assertIn('class="p-chip">Deep reasoning<', opened)
        self.assertIn("Opus, high effort", opened)
        self.assertIn('data-turncopy data-text="Implement the thing"', opened)
        self.assertNotIn(">Prompt<", render(self.setup + "d.prompt = ''; taskBody(t, d)"))

    def test_plan_rows_are_links_with_plain_words(self):
        html = render(self.setup + "planTimeline(t, d)")
        self.assertEqual(html.count('class="p-st'), 2)
        self.assertIn('data-bpick="s1" data-btask="t"', html)
        self.assertIn("✓ passed", html)
        self.assertIn("· queued", html)
        self.assertIn("$0.01", html)
        ask = render(self.setup + "t.current = 2; t.steps[1].state = 'waiting'; row.asks = 'Which?'; d.actions = A('decision', [], []); planTimeline(t, d)")
        self.assertIn("? asks you", ask)

    def test_supervisor_lines_sit_after_the_step_that_had_started(self):
        html = render(self.setup + "t.steps[1].started = 50; d.supervisor = {mode: 'gated', audit: ["
                      "{ts: 20, wake: 1, phase: 'outcome', status: 'dispatched', decision: 'retry'},"
                      "{ts: 60, wake: 2, phase: 'outcome', status: 'suggest', decision: 'finish'}]}; planTimeline(t, d)")
        s1, s2 = html.index('data-bpick="s1"'), html.index('data-bpick="s2"')
        self.assertLess(s1, html.index('data-sv="t|1"'))
        self.assertLess(html.index('data-sv="t|1"'), s2)
        self.assertLess(s2, html.index('data-sv="t|2"'))
        self.assertIn("Finish the task", html)

    def test_the_old_route_gauge_and_quiet_card_are_gone(self):
        src = APP.read_text(encoding="utf-8")
        for gone in ("function routeHtml(", "function supCard(", "function questionsFold(", "Supervisor · last decision"):
            self.assertNotIn(gone, src)
        self.assertIn('class="p-sect"', render(self.setup + "inspTask(t, d, row)"))
```

Deleted or rewritten: `OpenedTaskTest.test_route_lists_proposed_steps_dim` (deleted: plan 49's proposed rows are gone);
`OpenedTaskTest.test_opened_task_has_no_tabs_and_closed_folds` (keep its "no views" assertions on `inspTask`; replace
the `Supervisor suggests` / `tgoal` assertions with `assertIn('data-bpick="s1"', html)` and `assertIn(">Brief<", html)`);
`TaskOverviewTest.test_task_page_has_no_views_and_its_route_opens_the_steps` (`"Goal"` becomes `">Brief<"`);
`RecoveryBoxTest.test_recovery_refresh_keeps_draft_and_focus` keeps its `inspTask` call unchanged.

Headless, `tests/live_board_check.py`, add to `CHECKS`:

```python
def body_checks(page, name):  # Task 3: the sections and the timeline; every row a pointer link with a chevron
    assert page.locator(".p-sect .lbl", has_text="Plan").count() == 1, (name, "a Plan section")
    rows = page.locator(".p-st")
    assert rows.count() >= 2, (name, "plan rows")
    assert rows.first.evaluate("e => getComputedStyle(e).cursor") == "pointer", (name, "rows look clickable")
    rows.first.hover()
    assert rows.first.locator(".go").evaluate("e => getComputedStyle(e).opacity") == "1", (name, "chevron on hover")
```

## 5. Run

`node --check web/app.js`; `py -m unittest tests.test_web tests.test_server`; `py -m tests.live_board_check`;
the full suite in the background.
