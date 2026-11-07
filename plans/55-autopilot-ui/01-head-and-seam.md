# Task 1: the seam and the page head (UI-3), with the level switch

Files: `web/app.js`, `web/style.css`, `tests/test_web.py`, `tests/live_autopilot_check.py` (check 6's selector),
`tests/live_board_check.py` (new). Commit boundary: `feat: the Board's page head and the actions seam (plan 55 Task 1)`.
Depends on nothing. Assumes D2 a and D4 a (README). Anchors are quoted lines of `9b6f988`.

What the user gets: the opened task's head as locked (project eyebrow, one-line title, status pill, Now / Took, the
Doto cost) and the autonomy level switch in sight instead of inside the ⋯ menu. Everything else on the page is
unchanged; the ⋯ menu loses only its mode segment.

## 1. Tests first (red), `tests/test_web.py`

New class after `class OpenedTaskTest`, reusing its setup:

```python
@unittest.skipUnless(NODE, "Node is not installed")
class AutopilotHeadTest(unittest.TestCase):
    """Plan 55 Task 1: the head reads actions.state for its pill and actions.menu for the level switch; no gate in JS."""
    LEVELS = ("d.actions = {state: 'running', line: 'running', primary: [], bar: [], menu: ['off', 'suggest', 'gated', 'auto'].map((m) => "
              "({id: 'level_' + m, label: m, post: '/api/task/supervisor', body: {task: 't', mode: m}, off: '', confirm: false})), message: null}; ")
    setup = OpenedTaskTest.setup + LEVELS

    def test_head_has_eyebrow_title_pill_and_cost(self):
        html = render(self.setup + "taskHead(t, d, row)")
        self.assertIn('class="p-eb">Console<', html)
        self.assertIn(">Task</h2>", html)
        self.assertIn('class="p-pill n">▸ Running<', html)
        self.assertIn('class="p-cost"', html)
        self.assertIn("$1.00", html)
        for gone in ("task-crumb", "supervised · ", "v-lab"):
            self.assertNotIn(gone, html)
        for state, word in (("plan_ready", "? Plan to confirm"), ("decision", "? Needs you"), ("failed_twice", "✕ Failed twice"),
                            ("done", "✓ Done"), ("hold", "? Held"), ("ready", "Ready to start"), ("stuck", "✕ Stuck")):
            with self.subTest(state):
                self.assertIn(f">{word}<", render(self.setup + f"d.actions.state = '{state}'; taskHead(t, d, row)"))
        self.assertIn("✓ Accepted", render(self.setup + "d.actions.state = 'done'; t.accepted = 5; taskHead(t, d, row)"))

    def test_level_switch_is_the_served_level_actions(self):
        gated = render(self.setup + "d.supervisor = {mode: 'gated'}; levelSeg(d)")
        self.assertIn('data-aid="level_gated" data-afn="runAction" aria-pressed="true"', gated)
        self.assertIn('data-aid="level_auto"', gated)
        self.assertNotIn("level_off", gated)
        self.assertNotIn("level_suggest", gated)
        sug = render(self.setup + "d.supervisor = {mode: 'suggest'}; levelSeg(d)")
        self.assertLess(sug.index("level_suggest"), sug.index("level_gated"))  # D4 a: the task's own word shows, pressed
        self.assertIn('data-aid="level_suggest" data-afn="runAction" aria-pressed="true"', sug)
        self.assertEqual(render(self.setup + "d.supervisor = {mode: 'gated'}; d.actions.menu = []; levelSeg(d)"), "")
        off = render(self.setup + "d.supervisor = {mode: 'gated'}; d.actions.menu[3].off = 'Pause first'; levelSeg(d)")
        self.assertIn('disabled title="Pause first"', off)

    def test_run_action_posts_the_served_body_and_arms_confirm(self):
        got = render(self.setup + """(async () => {
          const calls = []; api = async (p, b) => { calls.push([p, b]); return {}; }; renderBoard = async () => {};
          boardTask = 't'; boardData = {id: 't', data: d};
          d.actions.bar = [{id: 'stop', label: 'Stop', post: '/api/task/stop', body: {task: 't'}, off: '', confirm: true},
                           {id: 'pause', label: 'Pause', post: '/api/task/pause', body: {task: 't'}, off: 'not running', confirm: false}];
          const b = (aid) => ({dataset: {aid}, textContent: '', innerHTML: '', disabled: false});
          await runAction(b('level_auto'));
          const stop = b('stop'); await runAction(stop); const armed = calls.length; await runAction(stop);
          await runAction(b('pause')); await runAction(b('nothing'));
          return {calls, armed};
        })()""")
        self.assertEqual(got["armed"], 1)  # the first click on a confirm action only arms it
        self.assertEqual(got["calls"], [["/api/task/supervisor", {"task": "t", "mode": "auto"}],
                                        ["/api/task/stop", {"task": "t"}]])  # an off action and an unknown id post nothing

    def test_menu_has_no_mode_segment(self):
        self.assertNotIn("supmode", render(self.setup + "d.supervisor = {mode: 'gated'}; taskMenu(t, d)"))
```

Edits to existing tests in the same commit (they assert what this task moves):

- `SupervisorSettingsTest.test_mode_segment_has_four_levels`: rename to `test_head_level_switch_follows_d4` and
  replace its body with `render(AutopilotHeadTest.setup + "d.supervisor = {mode: 'off'}; levelSeg(d)")` asserting
  `level_off`, `level_gated`, `level_auto` present and `level_suggest` absent.
- `OpenedTaskTest.test_task_bar_is_stop_or_resume_pause_and_menu`: drop the two `supmode` items from the list and the
  `assertIn('data-mode="suggest" aria-pressed="true"', menu)` line; keep `assertNotIn("supmode", nosup)`.
- `OpenedTaskTest.test_sup_card_shows_approve_only_where_allowed`: drop `await taskAct('supmode', ...)` and the last
  expected call `["/api/task/supervisor", {"task": "t", "mode": "auto"}]`.
- `OpenedTaskTest.test_opened_task_has_no_tabs_and_closed_folds`: replace `assertIn("supervised · suggest", html)` by
  `assertIn('class="p-hd"', html)`.
- `SelectionTest.test_breadcrumb_shows_tasks_title_and_step`: keep (the step page still uses `taskBreadcrumb` until
  Task 5).

## 2. Code (`web/app.js`)

### 2.1 The seam, a new block

Anchor: insert right after the line `function actRedraw() { boardData = null; renderBoard(); }` (it needs `tArmTimer`,
`actMsg` and `actRedraw`, defined just above it), before `async function taskAct(name, button) {`.

```js
// -- plan 55: the page places GET /api/task `actions` (plan 52 Task 6); it never rebuilds a gate -----------------
// A control exists because `actions` lists it and is enabled because its `off` is "". The state word only picks words
// and tones. The parts below take any actions-shaped object, so plan 53's build page reuses them with its own `fn`.
const ACT_COPY = { confirm_auto: "Confirm and auto accept", default_auto: "Take default and auto accept", edit_plan: "Read or edit the plan",
  continue: "Continue (fork)", verify: "Verify (fork)", escalate: "Escalate (fork)" };  // README 4.1: the locked mock's words
const ACT_TIP = { confirm_auto: "Confirm this plan, and set the project to auto: later plans run without asking",
  reject: "Turns it down; a note in the box below says why", continue: "Continue as a fork: a new Console run with its levers" };
const ARM = { stop: "Stop the task? Click again", delete: "Delete the task folder? Click again", drop: "Drop this task? Click again",
  finish: "Finish this task? History stays. Click again" };
const PILL = { ready: ["Ready to start", "y"], running: ["▸ Running", "n"], plan_ready: ["? Plan to confirm", "y"], decision: ["? Needs you", "y"],
  suggestion: ["? Needs you", "y"], hold: ["? Held", "y"], failed_twice: ["✕ Failed twice", "r"], stuck: ["✕ Stuck", "r"], paused: ["Paused", "q"],
  stopped: ["Stopped", "q"], done: ["✓ Done", "g"], handed: ["Handed off", "q"], observed: ["Observed", "q"], preparing: ["Preparing", "q"] };
function acts(d) {  // the opened task's actions; an empty set until GET /api/task answers
  const a = d && d.actions;
  return a && a.state ? a : { state: "", line: "", primary: [], bar: [], menu: [], message: null };
}
function actFind(d, id) { const a = acts(d); return [...a.primary, ...a.bar, ...a.menu].find((x) => x.id === id) || null; }
function actLabel(a, state) {
  if (state === "plan_ready" && a.id === "confirm") return "Confirm";
  if (state === "hold" && a.id === "confirm" && a.confirm) return "Confirm " + (fableName() || "Fable");
  return ACT_COPY[a.id] || a.label;
}
function actTip(a) {
  if (a.off) return a.off;
  if (a.id === "default_auto") {
    const s = Number(((cfg && cfg.tuning && cfg.tuning.decision_timeout_s) || {}).value);
    return `Take the default here, and set the project to auto${s ? `: later defaults are taken after ${Math.round(s / 60)} min` : ""}`;
  }
  return ACT_TIP[a.id] || "";
}
function actBtn(a, cls = "", o = {}) {  // one served action as a button; greyed with its off reason, never hidden here
  const tip = o.tip || actTip(a), label = o.label || actLabel(a, o.state || "");
  return `<button class="btn${cls ? " " + cls : ""}" data-aid="${esc(a.id)}" data-afn="${esc(o.fn || "runAction")}"${a.off ? " disabled" : ""}${tip ? ` title="${esc(tip)}"` : ""}>${o.html || esc(label)}</button>`;
}
function armBtn(button, text) {  // two clicks: the first only says what the second does
  button.dataset.armed = "1";
  button.dataset.label = button.innerHTML;
  button.textContent = text;
  clearTimeout(tArmTimer);
  tArmTimer = setTimeout(() => { delete button.dataset.armed; button.innerHTML = button.dataset.label; }, 3000);
}
function sayAct(text, button) { const msg = actMsg(); if (msg) msg.innerHTML = `<span class="r">${esc(text)}</span>`; else button.textContent = "Failed: " + text; }
async function runAction(button) {  // the one click path of a task action: confirm twice, open its form, or post its body as served
  const d = boardData && boardData.id === boardTask ? boardData.data : null, a = actFind(d, button.dataset.aid);
  if (!a || a.off) return;
  if (a.confirm && !button.dataset.armed) { armBtn(button, ARM[a.id] || `${actLabel(a, acts(d).state)}? Click again`); return; }
  if (!a.post) return openActionForm(a, button, d);
  button.disabled = true;
  try {
    await api(a.post, actBody(a));
    if (a.id === "delete" || a.id === "drop") { boardTask = ""; boardPick = ""; boardData = boardChat = null; renderBoard(); return; }
    actRedraw();
  } catch (e) { button.disabled = false; sayAct(e.message, button); }
}
function actBody(a) { return { ...a.body }; }  // Task 2 adds the box text as Reject's note
function openActionForm(a, button, d) {}  // Task 2 fills the forms (post "": Retry, Hand off, Add step, Edit plan, Reopen, Start next task)
```

### 2.2 The head

Insert after the seam block:

```js
function pageHead(o) {  // UI-3, one layout on the task, step and observed pages (plan 53 Task 4 reuses it)
  const eb = o.back ? `<button class="p-eb" data-bpick="t" data-btask="${esc(o.back.tid)}" title="Back to the task (Esc)">← ${esc(o.back.title)}</button>`
    : `<span class="p-eb">${esc(o.eyebrow || "")}</span>`;
  const facts = (o.facts || []).filter((f) => f && f[1]).map(([k, v, html]) => `<span class="p-fact"><i>${esc(k)}</i>${html ? v : esc(v)}</span>`).join("");
  return `<div class="p-hd"><div class="p-hl">${eb}<h2 title="${esc(o.tip || o.title)}">${esc(o.title)}</h2>
    <div class="p-meta"><span class="p-pill ${o.pill[1]}">${esc(o.pill[0])}</span>${facts}</div></div>
    <div class="p-right">${o.right || ""}<b class="p-cost" title="${esc(o.costTip || "")}">${esc(o.cost)}</b>${o.costSub ? `<span class="p-csub">${esc(o.costSub)}</span>` : ""}</div></div>`;
}
function levelSeg(d) {  // D4 a: gated and auto, plus the task's own word when it is off or suggest; each one a served action
  const mode = d && d.supervisor ? d.supervisor.mode : "", want = ["gated", "auto"];
  if (mode && !want.includes(mode)) want.unshift(mode);
  const items = want.map((m) => actFind(d, "level_" + m)).filter(Boolean);
  if (!items.length) return "";
  return `<span class="p-seg" role="group" aria-label="Autonomy level of this task">${items.map((a) => `<button data-aid="${esc(a.id)}" data-afn="runAction" aria-pressed="${a.body.mode === mode}"${a.off ? ` disabled title="${esc(a.off)}"` : ""}>${esc(a.body.mode)}</button>`).join("")}</span>`;
}
function taskHead(t, d, row) {
  const A = acts(d), cs = t.steps.find((x) => x.n === t.current), first = t.steps.find((x) => x.started);
  const pill = t.accepted ? ["✓ Accepted", "g"] : PILL[A.state] || PILL.running, facts = [];
  if (A.state === "running" && cs && cs.state === "running") facts.push(["Now", `${two(cs.n)} ${cs.kind} on ${modelText(rungOf(cs.harness, cs.model), cs.effort)}, ${stepTime(cs)}`]);
  if (t.state === "done" && first) facts.push(["Took", elapsed(t.updated - first.started)]);
  if (t.handoff_from) facts.push(["Follow-up of", `<button class="olink" data-task="${esc(t.handoff_from)}">${esc(labelOf(t.handoff_from))}</button>`, true]);
  if (t.handoff_to) facts.push(["Handed to", `<button class="olink" data-task="${esc(t.handoff_to)}">${esc(labelOf(t.handoff_to))}</button>`, true]);
  return pageHead({ eyebrow: t.project, title: t.title, tip: `${t.title} · ${taskDir(t.id)} · C copies ${labelOf(t.id)}`, pill, facts,
    right: levelSeg(d), cost: "$" + money(row.cost), costTip: "Spent on this task" });
}
```

### 2.3 `inspTask` uses it

In `function inspTask(t, d, row)`, replace the three lines from
`  const sup = d.supervisor, mode = sup ? (sup.mode === "off" ? "supervisor off" : "supervised · " + sup.mode) : "";`
through the `const head = ...` statement that ends with `<span>task ${labHtml(t.id)}</span></div></div>`;` by:

```js
  const head = taskHead(t, d, row);
```

Delete the three `links` lines (`const links = [];` and the two `if (t.handoff_from)` / `if (t.handoff_to)` pushes)
and, in `const body = `, the `${links.length ? ... : ""}` term. In the `return dock(` line replace
`` `${taskBreadcrumb(t)}${head}` `` with `head`. `shown`, `word`, `tn` become unused in `inspTask`: remove them from
the first `const` line, keeping `tid` and `cur`.

### 2.4 The menu loses its segment; the click path

- In `function taskMenu(`, delete the line that starts `  if (sup) m.push(\`<span class="lbl grp">Supervisor for this task</span>`
  (two lines, through `.join("")}</span>\`);`), and `sup` from its first `const` line.
- In `async function supAct(`, delete the line `  if (name === "supmode") body = { task: id, mode: button.dataset.mode };`
  and change `  else if (name === "supapprove")` to `  if (name === "supapprove")`; change
  `    if (name !== "supmode") supNote = "";` to `    supNote = "";`.
- In `async function taskAct(`, change `if (["supapprove", "supreject", "supmode"].includes(name))` to
  `if (["supapprove", "supreject"].includes(name))`.
- The click handler: in the long selector string that starts `const t = e.target.closest("[data-prep],[data-go],`,
  add `[data-aid],` after `[data-tact],`; then before the line `  else if (t.dataset.tact) taskAct(t.dataset.tact, t);`
  insert:

```js
  else if (t.dataset.aid) { const fn = t.dataset.afn === "runAction" ? runAction : window[t.dataset.afn]; if (typeof fn === "function") fn(t); }
```

- `function focusKey(el)`: after the `if (el.dataset.tact)` line insert
  `  if (el.dataset.aid) return \`[data-aid="${el.dataset.aid}"]\`;`.

## 3. Style (`web/style.css`)

Append at the end of the file, one block (tokens unchanged; the plan 38 D4 b floor: no text under 11 px, targets 24 px):

```css
/* plan 55: the page head (UI-3), design/rework/locked/workflow-autopilot.html; one layout on the task, step and observed pages */
.p-hd { display: grid; grid-template-columns: minmax(0, 1fr) 140px; gap: 16px; align-items: end; padding-bottom: 12px; }
.p-hl { min-width: 0; }
.p-eb { display: block; max-width: 100%; font: 600 11px var(--mono); letter-spacing: .04em; color: var(--mut); margin-bottom: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
button.p-eb { background: none; border: 0; padding: 0; min-height: 24px; cursor: pointer; text-align: left; }
button.p-eb:hover { color: var(--ink); text-decoration: underline; text-underline-offset: 3px; }
.p-hd h2 { margin: 0 0 6px; font: 600 17px/1.3 var(--ui); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.p-meta { display: flex; flex-wrap: nowrap; align-items: center; gap: 6px 16px; font: 12px var(--ui); white-space: nowrap; overflow: hidden; }
.p-pill { flex: none; font: 600 12px var(--ui); padding: 2px 9px; border-radius: 10px; background: var(--raise); }
.p-pill.g { color: var(--ok); background: color-mix(in srgb, var(--ok) 12%, var(--raise)); }
.p-pill.y { color: var(--you); background: color-mix(in srgb, var(--you) 12%, var(--raise)); }
.p-pill.r { color: var(--bad); background: color-mix(in srgb, var(--bad) 12%, var(--raise)); }
.p-pill.q { color: var(--mut); }
.p-fact { display: inline-flex; align-items: center; gap: 6px; min-width: 0; color: var(--ink); overflow: hidden; text-overflow: ellipsis; }
.p-fact i { font-style: normal; color: var(--mut); }
.p-right { display: grid; justify-items: end; gap: 4px; text-align: right; }
.p-cost { font: 700 28px/1 var(--dot); font-variant-numeric: tabular-nums; }
.p-csub { font: 12px var(--ui); color: var(--mut); }
.p-seg { display: inline-flex; border: 1px solid var(--line); border-radius: 5px; overflow: hidden; }
.p-seg button { min-height: 24px; min-width: 24px; padding: 0 8px; border: 0; background: transparent; color: var(--mut); font: 600 11px var(--mono); cursor: pointer; }
.p-seg button:hover:not(:disabled) { color: var(--ink); background: var(--raise); }
.p-seg button[aria-pressed="true"] { background: var(--ink); color: var(--win); }
.p-seg button:disabled { opacity: .4; cursor: default; }
@container (max-width: 520px) { .p-hd { grid-template-columns: minmax(0, 1fr) auto; gap: 10px; } .p-cost { font-size: 24px; } }
```

## 4. `tests/live_board_check.py` (new; the headless sweep every later task extends)

```python
"""Headless look of plan 55's Board: py -m tests.live_board_check [--shots DIR] [state ...].

One scratch service from tests.live_autopilot_check (Rig, build_states: the fake claude, no provider, never the
running service), the real page in headless Edge. Each captured state is opened at 900, 400 and 340 px, dark and light,
reduced motion, device scale 1.0 and 1.3 (WebView2 at 130 %). Asserts: no horizontal scroll, no page or console
error, and the per-task checks in CHECKS. --shots saves one PNG per state, width and scheme for Fred (stops 1 to 3)."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.live_autopilot_check import Ctx, build_states

WIDTHS, SCALES, SCHEMES = (900, 400, 340), (1.0, 1.3), ("dark", "light")
STATES = ("planning", "plan_ready", "running", "decision", "done", "suggestion")
SMALL = """[...document.querySelectorAll('.p-hd *, .p-card *, .p-bar *, .p-box *, .p-sect *, .v-chain *')]
  .filter((e) => e.offsetParent && e.childNodes.length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    && parseFloat(getComputedStyle(e).fontSize) < 11).map((e) => e.className + ': ' + e.textContent.trim().slice(0, 30))"""
TINY = """[...document.querySelectorAll('.p-hd button, .p-card button, .p-bar button, .p-box button, .p-sect button')]
  .filter((b) => b.offsetParent).map((b) => [b.className + ' ' + (b.dataset.aid || b.textContent.trim()).slice(0, 30), b.getBoundingClientRect()])
  .filter(([, r]) => r.height < 24 || r.width < 24).map(([n]) => n)"""


def head_checks(page, name):  # Task 1; later tasks add their own functions to CHECKS
    assert page.locator(".p-hd").count() == 1, (name, "one page head")
    assert page.evaluate("document.querySelector('.p-hd h2').scrollWidth >= document.querySelector('.p-hd h2').clientWidth"), name


CHECKS = [head_checks]


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    shots = Path(argv[argv.index("--shots") + 1]) if "--shots" in argv else None
    wanted = [a for a in argv if a in STATES] or list(STATES)
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        ctx = Ctx(browser)
        try:
            st = build_states(ctx, lambda name, tid: None)
            rig = st["rig"]
            for scale in SCALES:
                page = browser.new_page(device_scale_factor=scale)
                rig.page, rig.page_errors = page, []
                page.on("pageerror", lambda e: rig.page_errors.append("pageerror: " + str(e)))
                rig.load()
                for width in WIDTHS:
                    for scheme in SCHEMES:
                        page.set_viewport_size({"width": width, "height": 760})
                        page.emulate_media(color_scheme=scheme, reduced_motion="reduce")
                        for name in wanted:
                            rig.open(st["tids"]["running" if name == "planning" else name])
                            where = f"{name} {width}px {scheme} x{scale}"
                            try:
                                assert rig.fits(), "horizontal scroll"
                                assert not page.evaluate(SMALL), page.evaluate(SMALL)
                                assert not page.evaluate(TINY), page.evaluate(TINY)
                                for check in CHECKS:
                                    check(page, name)
                            except AssertionError as exc:
                                failures.append(f"{where}: {exc}")
                            if shots and scale == 1.0:
                                shots.mkdir(parents=True, exist_ok=True)
                                page.screenshot(path=str(shots / f"{name}-{width}-{scheme}.png"))
                page.close()
            rig.assert_clean()
        finally:
            ctx.close()
            browser.close()
    print("\n".join(failures) or f"All {len(wanted)} states pass at {len(WIDTHS)} widths, {len(SCHEMES)} schemes, {len(SCALES)} scales.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

`SMALL` and `TINY` cover only this plan's parts (`.p-*` and, from Task 4, the list): the rest of the window is plan 38
Task 6's. `tests/live_autopilot_check.py` check 6: replace `page.locator('[data-tact="supmode"]')` with
`page.locator('.p-seg [data-aid^="level_"]')` and its expected words with `["gated", "auto"]` (gated pressed, D4 a).

## 5. Run

`node --check web/app.js`; `py -m unittest tests.test_web`; `py -m tests.live_autopilot_check 6`;
`py -m tests.live_board_check`; the full suite in the background. Expected: the four new tests pass, the edited ones
pass, 1167 + 4 tests OK.
