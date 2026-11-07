# Task 5: the step page (UI-3 on a step, UI-6)

Files: `web/app.js`, `web/style.css`, `tests/test_web.py`, `tests/live_board_check.py`, `tests/live_task_chat_check.py`.
Commit boundary: `feat: the step page with its way back, step arrows and chat thread (plan 55 Task 5)`. Depends on
Task 3 and on Fred's answer at stop 2. Assumes D12 a.

What the user gets: a step opens on the same layout as its task: `← task title` as the way back, `02 · Code`, the
step's pill with Model and Took (or For while it runs), the ‹ › arrows above the step's cost, then the tabs Chat,
Received, Handoff, Files. Chat reads as a thread: Console's message on the right, the model's turns on the left, each
run of tool calls folded into one pill, a live "writing" turn while it runs. The task's dock card, box and bar stay
under every step page, so a gate is answered from wherever Fred is.

## 1. Code (`web/app.js`)

### 1.1 The step head (replaces `stepHead` and `taskBreadcrumb`)

Replace `function taskBreadcrumb(t, step = null) { ... }` (whole) and `function stepHead(t, s, d, row, extra = "") { ... }`
(whole) by:

```js
const STEP_PILL = { done: ["✓ Done", "g"], running: ["▸ Running", "n"], replied: ["Replied", "n"], planned: ["· Queued", "q"],
  waiting: ["? Waits for you", "y"], failed: ["✕ Failed", "r"] };  // plan 38 U9: Replied is ink, orange is needs-you only
function stepHead(t, s, d, row) {  // UI-3 on a step: the way back, NN · Kind, the pill, Model and Took; ‹ › above the step's cost
  const shown = stepShown(t, s, row), i = t.steps.findIndex((x) => x.n === s.n), prev = t.steps[i - 1], next = t.steps[i + 1], time = stepTime(s);
  const nav = (x, dir, sym) => `<button${x ? ` data-bpick="s${x.n}" data-btask="${esc(t.id)}"` : " disabled"} title="${dir} step" aria-label="${dir} step">${sym}</button>`;
  return pageHead({ back: { tid: t.id, title: t.title }, title: `${two(s.n)} · ${s.kind[0].toUpperCase()}${s.kind.slice(1)}`, pill: STEP_PILL[shown] || STEP_PILL.planned,
    facts: [["Model", s.state === "planned" ? "picked when it starts" : modelText(rungOf(s.harness, s.model), s.effort)], [s.state === "running" ? "For" : "Took", time]],
    right: `<span class="p-seg p-nav" role="group" aria-label="Steps">${nav(prev, "Previous", "‹")}${nav(next, "Next", "›")}</span>`,
    cost: s.state === "planned" ? "$0" : costUnknown(s) ? "?" : "$" + money(s.cost), costTip: "Spent on this step" });
}
```

### 1.2 The step page (replaces `inspStep`, `inspGap`, `inspReplan`, `stepButtons`)

Replace `function inspStep(t, s, d, row) { ... }` by:

```js
function inspStep(t, s, d, row) {  // UI-6: head, four tabs, the pane; the task's card, box and bar under it (D12 a)
  const prev = t.steps.find((x) => x.n === s.n - 1), meta = s.brief_meta || {}, nx = t.steps.find((x) => x.n === s.n + 1);
  const inW = sentWords(t, d, s), outW = meta.raw_w != null ? meta.raw_w : (d.notes || {})[String(s.n)] ? wc(d.notes[String(s.n)]) : null;
  const nf = ((d.files || {})[String(s.n)] || []).length;
  let pane;
  if (s.state === "planned") pane = sect("Goal", prev ? `runs after ${two(prev.n)}` : "runs first", `<p class="brief">${esc(s.goal || "")}</p>`);
  else {
    const tabs = [["chat", "Chat"], ["recv", `Received${inW != null && prev ? ` <span class="n">${inW} w</span>` : ""}`],
      ["hand", `Handoff${outW != null ? ` <span class="n">${outW}${meta.sent_w != null && meta.sent_w < outW && nx ? " → " + meta.sent_w : ""} w</span>` : ""}`],
      ["files", `Files${nf ? ` <span class="n">${nf}</span>` : ""}`]];
    const tab = tabs.some(([k]) => k === itab) ? itab : "chat";
    const body = tab === "chat" ? chatTab(t, s, d) : tab === "recv" ? recvPane(t, s, d) : tab === "hand" ? handPane(t, s, d) : filesPane(t, s, d);
    const add = latestStep(t)?.n === s.n ? "" : nextActions(t, s, d);  // D12 a: Add step from here, on an older step, from the served reasons
    pane = tabsHtml(tabs, tab) + (nextOpen?.key === nextKey(t, s) ? nextFormHtml(t, s, row, d) : "") + (add ? `<div class="p-acts">${add}</div>` : "") + `<div class="ipane">${body}</div>`;
  }
  const A = acts(d);
  return taskShell(t.id, stepHead(t, s, d, row) + pane, taskCard(t, d, row), NO_BOX.has(A.state) ? "" : stepFooter(t, s, d), taskBar(t, d, row, s));
}
```

`function taskBar(t, d, row, withGate = false)` from Task 2 changes its last parameter to the shown step:
`function taskBar(t, d, row, s = null)`; its first line becomes
`const A = acts(d), gate = GATES.has(A.state), taken = new Set(gate ? DOCK_TAKES[A.state] || [] : []);` and its
`use: useHtml(t, row)` becomes `use: useHtml(t, row, s)`.

In `function boardInspector(row, d)`: delete the two lines
`if (s.kind === "replan" && s.n === t.current && String(t.why || "").startsWith("replanned:")) return dock(...);` and
`if (s.n === t.current && /^(asks: )?Plan gap:/.test(row.asks || row.why || "")) return inspGap(t, s, d, row);`:
the replan and the Plan gap are the task's `hold` and `decision` cards, drawn under the step page by `taskCard`.

Delete, each whole: `function inspGap(`, `function inspReplan(`, `function stepButtons(`, `function routePane(`, and
`planPane`'s caller tab (the function `planPane` stays if `planOpenHtml`'s other callers need its helpers; delete it
when `grep -n "planPane("` finds no caller). `itab` values `route` and `plan` saved in `window.json` fall back to
`chat` by the `tabs.some` line.

### 1.3 The chat as a thread (UI-6)

`function promptRow(text, o, key)`: the step's first turn is Console's message. Replace
`<span class="lbl">Prompt</span>` with `<span class="lbl">${o.board ? "Console" : "Prompt"}</span>`. Everything else in
`chatPane` keeps its markup; the thread look is CSS on the step page only (`.idock[data-p="step"]`), so the session page
(400 px window) keeps its locked look. `inspStep` passes `data-p="step"`: change `taskShell`'s first line to take it,
`function taskShell(tid, scroll, card, box, bar, kind = "task")` with `data-p="${kind}"`, and call it with `"step"` from
`inspStep`.

## 2. Style (`web/style.css`, append)

```css
/* plan 55: the step page (UI-6): ‹ › above the cost; the chat as a thread */
.p-nav button { font-size: 13px; padding: 0 10px; }
.idock[data-p="step"] .tabs { margin: 4px 0 0; }
.idock[data-p="step"] .chat { display: grid; gap: 10px; grid-template-columns: minmax(0, 1fr); }
.idock[data-p="step"] .chat .turn { max-width: 86%; font-size: 13px; line-height: 1.55; }
.idock[data-p="step"] .chat .turn.you { justify-self: end; background: var(--raise); border-radius: 10px 10px 2px 10px; padding: 8px 11px; }
.idock[data-p="step"] .chat .turn.claude { justify-self: start; }
.idock[data-p="step"] .chat .turn .lbl { text-transform: none; letter-spacing: 0; font: 11px var(--mono); }
.idock[data-p="step"] .chat .tools { justify-self: start; display: inline-flex; gap: 6px; min-height: 24px; border: 1px solid var(--line);
  border-radius: 12px; padding: 2px 10px 2px 8px; background: none; color: var(--mut); font: 11px var(--mono); cursor: pointer; }
.idock[data-p="step"] .chat .tools:hover { color: var(--ink); border-color: var(--ink); }
.idock[data-p="step"] .chat .tlist { justify-self: start; margin-left: 10px; padding-left: 10px; border-left: 1px solid var(--line); font: 11.5px var(--mono); }
```

## 3. Tests

New, `tests/test_web.py`:

```python
@unittest.skipUnless(NODE, "Node is not installed")
class AutopilotStepTest(unittest.TestCase):
    """Plan 55 Task 5: the step page: the way back, ‹ ›, four tabs, the task's card, box and bar under it."""
    setup = AutopilotBodyTest.setup

    def test_head_way_back_arrows_and_cost(self):
        html = render(self.setup + "stepHead(t, t.steps[0], d, row)")
        self.assertIn('class="p-eb" data-bpick="t" data-btask="t"', html)
        self.assertIn("← Task", html)
        self.assertIn(">01 · Chat</h2>", html)
        self.assertIn(">✓ Done<", html)
        self.assertIn("<i>Model</i>", html)
        self.assertIn('disabled title="Previous step"', html)
        self.assertIn('data-bpick="s2" data-btask="t" title="Next step"', html)
        self.assertIn("$0.01", html)

    def test_four_tabs_and_the_task_controls_below(self):
        html = render(self.setup + "boardPick = 's1'; itab = 'route'; inspStep(t, t.steps[0], d, row)")
        tabs = re.findall(r'data-itab="(\w+)"', html)
        self.assertEqual(tabs, ["chat", "recv", "hand", "files"])
        self.assertIn('aria-selected="true"', html.split('data-itab="chat"')[1][:40])  # a saved Route tab falls back to Chat
        self.assertIn('data-p="step"', html)
        self.assertIn('class="p-bar"', html)
        planned = render(self.setup + "inspStep(t, t.steps[1], d, row)")
        self.assertIn(">Goal<", planned)
        self.assertIn("runs after 01", planned)
        self.assertNotIn("data-itab", planned)

    def test_old_step_pages_are_gone(self):
        src = APP.read_text(encoding="utf-8")
        for gone in ("function inspGap(", "function inspReplan(", "function stepButtons(", "function taskBreadcrumb(", "function routePane(", 'data-itab="route"'):
            self.assertNotIn(gone, src)
```

(`import re` at the top of `tests/test_web.py` if it is not there.)

Rewritten: `SelectionTest.test_breadcrumb_shows_tasks_title_and_step` becomes `test_step_head_links_back_to_the_task`
(`stepHead(t, t.steps[0], d, row)` has `data-bpick="t"` and the task's title). Any `NextStepUITest` or
`UnifiedTaskChatTest` case that asserts the Route or Plan tab, `stepButtons` or `taskBreadcrumb` is rewritten to the
four tabs and the bar, and listed in the commit body. `tests/live_task_chat_check.py`: its tab loop
(`for tab in (...)` clicking `[data-itab]`) drops `route` and `plan`.

Headless, `tests/live_board_check.py`, after each state's task page also open its first started step
(`page.evaluate("id => { boardPick = 's1'; renderBoard(); }", tid)`) and add to `CHECKS`:

```python
def step_checks(page, name):  # Task 5: on a step page, the way back, four tabs, and the task's bar under it
    if page.locator('.idock[data-p="step"]').count():
        assert page.locator('.p-hd button.p-eb').is_visible(), (name, "the way back")
        assert page.locator(".tabs [data-itab]").count() == 4, (name, "four tabs")
        assert page.locator(".p-bar").is_visible(), (name, "the bar under a step")
```

## 4. Run

`node --check web/app.js`; `py -m unittest tests.test_web`; `py -m tests.live_task_chat_check`;
`py -m tests.live_board_check`; the full suite in the background.
