# Task 6: the unshown states, the observed page, the page-driven acceptance

Files: `web/app.js`, `web/style.css`, `tests/test_web.py`, `tests/live_autopilot_check.py`, `tests/live_board_check.py`.
Commit boundary: `feat: handed, paused and stopped pages, the observed page head, page-driven acceptance (plan 55 Task 6)`.
Depends on Tasks 4 and 5, and on Fred's D14 answer at stop 1. Assumes D13 a, D14 a.

What the user gets: every state has a page that says what happened and offers only what `actions` serves. A handed
task shows its note and Start next task in a card; a paused or stopped task shows no card (nothing waits on Fred) and
its bar carries Resume, Retry or Finish; an observed VS Code or terminal chat gets the same head and bar look as a task.
Plan 52 Task 7's acceptance stops calling routes and clicks the page.

Already done by Task 2 (no code here, tests only): `ready`, `paused`, `stopped` (`taskCard` returns "", `taskBar` draws
the served bar and primary), `stuck` (the red card), `accepted` (the Finished card tagged Accepted, `accept` off and not
drawn). `preparing` keeps the Prep job row and `inspJob` (README section 5).

## 1. Code (`web/app.js`)

### 1.1 The handed card (replaces `handedBox`)

In `function taskCard(t, d, row)` (Task 2), replace the last line
`  return "";  // handed: Task 6; running, paused, stopped, ready: nothing waits on Fred` by:

```js
  if (s === "handed") {  // D14 a: the note as a fold, Start next task; a run that wrote no note says why (the card has no Retry: section 4.2)
    const cs = t.steps.find((x) => x.n === t.current), shown = taskShown(row);
    const q = d.handoff ? "The handoff note is saved. Start the next task from it."
      : shown === "handing" ? `The chat of step ${two(cs ? cs.n : 0)} is writing its handoff note.`
      : (d.levers || {}).retry === "" ? "No handoff note: the step's run failed." : "No handoff note: the handoff run did not finish.";
    const note = d.handoff ? foldLine("tho" + t.id, firstLine(d.handoff), d.handoff) : "";
    const open = cs && cs.session ? `<button class="btn" data-bpick="s${cs.n}" data-btask="${tid}">Open step ${two(cs.n)}</button>` : "";
    return dockCard({ tag: "Handed off", tone: d.handoff && !t.handoff_to ? "y" : "q", q, body: note, left: open, right: P.map((a) => btn(a, "you")).join("") });
  }
  return "";  // running, paused, stopped, ready: nothing waits on Fred
```

`firstLine(text)`: if `grep -n "function firstLine(" web/app.js` finds none, add above `taskCard`:
`function firstLine(text) { return String(text || "").split("\n").map((x) => x.replace(/^#+\s*/, "").trim()).find(Boolean) || ""; }`

`start_next` with an empty `post` opens the existing follow-up path: in `openActionForm(a, tid)` (Task 2) add the
branch `if (a.id === "start_next") return taskAct("next", null, tid);` (the `taskAct` `next` case that `handedBox`'s
button used, unchanged).

In `inspTask` (Task 2/3) nothing calls `handedBox` any more; in `attentionArea`'s successor nothing either. Delete,
each whole: `function handedBox(`, `function retryForm(` (its last callers were `handedBox` and the Retry askbox that
Task 2's `retryPick` replaced: check with `grep -n "retryForm(" web/app.js` that none is left). `TASK_WORD.handed`
and `.handing` stay (`statusLine` reads them for list rows).

### 1.2 The observed page (D13 a): the UI-3 head and the UI-8 bar look, buttons still from /api/levers

Replace `function sessionHead(s) { ... }` (whole) by:

```js
function sessionHead(s) {  // D13 a: the UI-3 head on a session page; the levers stay GET /api/levers (the service's gates)
  const tn = tone(s), [, word] = stateWord(s), task = taskOfSession(s.id);
  return pageHead({ eyebrow: `${s.project} · ${appName(s)}`, title: s.title || "01 chat",
    pill: [task ? word : "Observed", task ? tn : "q", task ? sessionMark(s, s.symbol, tn) : ""],
    facts: [["Model", modelText(rungOf(s.harness, s.model), s.effort)]], cost: spentText(s), costTip: "this chat" });
}
```

(`pageHead`'s `pill` takes `[word, tone, mark?]`; if Task 1's `pageHead` takes `[word, tone]` only, its pill line gains
`${o.pill[2] || ""}` before the word. `appName` is Task 4's.)

`async function renderLevers(s)`: no gate changes. Its last line `setHtml($("levers"), html);` becomes
`setHtml($("levers"), html ? `<div class="p-bar p-lv">${html}</div>` : "");` so the session page's two rows take the
bar's spacing, and `data-act` stays the session levers' attribute (Task 1 left it alone).

This head is the session page's in the 400 px window too: the window and the Board show the same section
(`index.html` `section[data-page="session"]`), and no class tells them apart. The mock's 400 px observed page is this
head, so the window follows the mock; flagged for Fred at stop 3 (README D13).

## 2. Style (`web/style.css`, append)

```css
/* plan 55 Task 6: the session page's levers in the bar's look (D13 a) */
#levers .p-lv { display: grid; gap: 8px; padding: 10px 12px; border-top: 1px solid var(--line); }
#levers .p-lv .lr { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
#levers .p-lv .btn { min-height: 24px; font-size: 12px; }
```

## 3. Tests

New, `tests/test_web.py`:

```python
@unittest.skipUnless(NODE, "Node is not installed")
class AutopilotStatesTest(unittest.TestCase):
    """Plan 55 Task 6: handed, paused, stopped and accepted pages; the observed session head."""
    setup = AutopilotDockTest.setup

    def test_handed_card_with_note_and_start_next(self):
        x = ("t.state = 'handed'; d.handoff = '## Goal\\nShip it'; "
             "d.actions = A('handed', [act('start_next', 'Start next task', '')], [], [act('delete', 'Delete', '/api/task/delete', {}, {confirm: true})])")
        html = render(self.setup + x + "; taskCard(t, d, row)")
        self.assertIn(">Handed off<", html)
        self.assertIn("The handoff note is saved. Start the next task from it.", html)
        self.assertIn('data-aid="start_next"', html)
        self.assertIn("Goal", html)  # the note's first line is the fold's preview

    def test_handed_without_a_note_says_why(self):
        x = ("t.state = 'handed'; d.handoff = ''; d.levers = {retry: ''}; "
             "d.actions = A('handed', [act('start_next', 'Start next task', '', {}, {off: 'No handoff saved'})])")
        html = render(self.setup + x + "; taskCard(t, d, row)")
        self.assertIn("No handoff note: the step's run failed.", html)
        self.assertIn("disabled", html.split('data-aid="start_next"')[1][:120])

    def test_paused_and_stopped_draw_no_card_and_the_served_bar(self):
        for state, prim in (("paused", "resume"), ("stopped", "retry")):
            x = f"d.actions = A('{state}', [act('{prim}', 'P', '/api/task/x')], [act('finish', 'Finish task', '/api/task/done')])"
            self.assertEqual(render(self.setup + x + "; taskCard(t, d, row)").strip(), "", state)
            bar = render(self.setup + x + "; taskBar(t, d, row)")
            self.assertIn(f'data-aid="{prim}"', bar)
            self.assertIn('data-aid="finish"', bar)

    def test_old_handed_and_retry_forms_are_gone(self):
        src = APP.read_text(encoding="utf-8")
        for gone in ("function handedBox(", "function retryForm("):
            self.assertNotIn(gone, src)

    def test_observed_session_head(self):
        s = "const s = {id: 'x', project: 'web', title: 'Fix nav', harness: 'claude', source: 'vscode', model: 'sonnet', effort: '', cost: 0.2, state: 'replied', symbol: '', forks: []}; "
        html = render(s + "sessionHead(s)")
        self.assertIn("web · VS Code", html)
        self.assertIn(">Observed<", html)
        self.assertIn('class="p-hd"', html)
```

(`A` and `act` are the Task 2 setup's helpers; `act(id, label, post, body, extra)` with `extra.off` sets `off`. If the
Task 2 helper names differ, these use them as written there.)

Rewritten: every existing test that renders `handedBox` or `retryForm` (`grep -n "handedBox\|retryForm" tests/`) moves
to `taskCard` on a `handed` state or to `retryPick`, listed in the commit body. `SessionHeadTest` or any test that
asserts `sessionHead`'s `ihead` markup is rewritten to `p-hd`.

### 3.1 Page-driven acceptance (`tests/live_autopilot_check.py`)

Plan 52 Task 7 called each route `actions` named, "as the later page will". Now the page exists: add to `class Rig`,
after `def act(`:

```python
    def click(self, tid, action_id, confirm=False):
        """Click the button the page drew for `action_id` (plan 55): the same route and body as act, through the page."""
        self.open(tid)
        button = self.page.locator(f'[data-aid="{action_id}"]').first
        assert button.is_visible(), f"the page drew no {action_id}"
        assert button.is_enabled(), f"{action_id} is off on the page"
        with self.page.expect_response(lambda r: r.request.method == "POST" and "/api/" in r.url) as response:
            button.click()
            if confirm:  # a two-click action arms first (ARM, Task 1), the second click posts
                self.page.locator(f'[data-aid="{action_id}"]').first.click()
        return response.value.status, response.value.json()
```

Then in `check_gated_chain` (Accept), `check_crash_retry` (Approve, at `code, body = rig.act(tid, "approve")`) and
`check_mode_switch` (`rig.act(tid, "level_auto")`), replace those `rig.act(...)` calls by `rig.click(...)` with the
same arguments (the function names are those of `9b6f988`; find each by its quoted call); a decision option is picked and confirmed by clicking `[data-optpick="<key>"]` then `[data-aid="<key>"]`.
`build_states` keeps `rig.act` (it builds states fast, its posts are not what is under test). The `clicks` assertions
keep their lists: the page posts the same routes.

### 3.2 Headless (`tests/live_board_check.py`)

`STATES` gains `"accepted", "paused", "stopped", "handed", "hold_fable", "observed"` (stuck turns into the suggestion
before the sweep; its card is covered by Task 2's Node test). After `build_states`, add
the three states a real POST reaches and the two served by an override:

```python
def more_states(st):  # Task 6: paused and stopped by their real routes; handed and a Fable hold served by page.route
    rig, fx = st["rig"], st["rig"].fx
    ids = st["tids"]
    ids["paused"] = p = rig.start(WORDS, [S("scout", "look SLOW"), S("code", "write it")])
    fx.until(p, fx.at(1), "the scout runs", 60)
    assert rig.act(p, "pause")[0] == 200
    ids["stopped"] = q = rig.start(WORDS, [S("scout", "look SLOW"), S("code", "write it")])
    fx.until(q, fx.at(1), "the scout runs", 60)
    assert rig.act(q, "stop")[0] == 200
    fx.until(q, lambda t: t["state"] == "stopped", "it stops", 30)
    ids["handed"] = ids["hold_fable"] = ids["accepted"]  # a real task, its GET body overridden below


OVERRIDES = {  # name: (task fields, actions) laid over a real GET body
    "handed": ({"state": "handed", "handoff_to": ""}, {"state": "handed", "line": "handed off",
               "primary": [{"id": "start_next", "label": "Start next task", "post": "", "body": {}, "off": "", "confirm": False}],
               "bar": [], "menu": [], "message": {"mode": "", "reason": "handed off"}}),
    "hold_fable": ({"state": "waiting", "why": "confirm Fable"}, {"state": "hold", "line": "held · confirm Fable",
                   "primary": [{"id": "confirm", "label": "Confirm", "post": "/api/task/confirm", "body": {}, "off": "", "confirm": True}],
                   "bar": [], "menu": [], "message": {"mode": "next", "reason": ""}}),
}


def override(page, rig, name):
    if name not in OVERRIDES:
        return
    fields, actions = OVERRIDES[name]

    def serve(route):
        body = route.fetch().json()
        body["task"].update(fields)
        body["actions"] = {**actions, "primary": [dict(a, body={"task": body["task"]["id"]}) for a in actions["primary"]]}
        if name == "handed":
            body["handoff"] = "## Goal\nThe next task starts from this note."
        route.fulfill(json=body)
    page.route("**/api/task?id=*", serve)
```

(`WORDS` and `S` import from `tests.live_autopilot_check` with `Ctx` and `build_states`.) In `main`, call
`more_states(st)` after `build_states`, `override(page, rig, name)` before `rig.open(...)` and `page.unroute("**/api/task?id=*")`
after the state's checks. `observed` opens a session row: `page.evaluate("id => openSession(id)", <a fake session id
from rig.fx's observed fixture>)` if the fixture has one; if `TaskServerTest` has no observed session, `observed` is
served by `page.route("**/api/snapshot*")` adding one row with `source: "vscode"`, the same way.

```python
def state_checks(page, name):  # Task 6: no card where nothing waits on Fred; the handed card; the observed head
    cards = page.locator(".p-card").count()
    if name in ("paused", "stopped", "running"):
        assert cards == 0, (name, "a card where nothing waits on Fred")
    if name == "handed":
        assert page.locator('.p-card [data-aid="start_next"]').is_visible(), name
    if name == "observed":
        assert page.locator("#sbody .p-hd").is_visible() and page.locator("#levers [data-act]").count(), name
```

`CHECKS` gains `state_checks`. The sweep's `SMALL` and `TINY` selectors gain `#levers *` and `#levers button`.

## 4. Stop 3

`py -m tests.live_board_check --shots <scratch>` over every state at 900, 400 and 340 px, dark and light; the 1.3 scale
runs its asserts without shots. Fred looks at the set (README section 6). Task 7 waits for his answer.

## 5. Run

`node --check web/app.js`; `py -m unittest tests.test_web`; `py -m tests.live_autopilot_check`;
`py -m tests.live_task_chat_check`; `py -m tests.live_board_check`; the full suite in the background.
