# Task 7: the Models card, every state, announcements and the headless sweep

> Contract: [README.md](README.md) 4.10, 5 (SW-8, SW-16 to SW-18), 5.3 (the unshown states), 9 (key capture). Decision for the
> card: plan 58 D9 ("a Models page card with slice 2"). Nothing in this task adds a route or a gate: it finishes the
> draw (the card, the landmarks, the announcements) and proves every state at every width.

**Files:** `web/app.js`, `web/style.css`, `web/index.html` (two element names), `tests/test_web.py` (`SuperModelsCardTest`,
`SuperA11yTest`), `tests/test_tuning.py` (one round trip), `tests/live_super_check.py` (the state sweep).
Commit boundary: `feat: the super agent's Models card, its states and announcements (plan 59 T7)`.
Depends on Task 6. **Stop 1 follows this task** (section 7.4): Fred looks at the screenshots, including the unshown states.

## 7.1 The Models card (plan 58 D9)

Plan 58 put the `super_*` keys in `tuning.TUNING` (group `super`; unit `lines` is whole) and the `POST /api/config/models`
whitelist, so the service already serves and validates them. The page draws only keys listed in the web `TUNE` table and
groups in `MGROUP` (`app.js:2358`, `:2376`), so the card is two table entries.

Tests first, `tests/test_web.py`:

```python
@unittest.skipUnless(NODE, "Node is not installed")
class SuperModelsCardTest(unittest.TestCase):
    KEYS = ("super_debounce_s", "super_sweep_s", "super_timeout_s", "super_notes_lines", "super_pass_usd", "super_day_usd")

    def test_the_six_numbers_have_labels_and_the_card_follows_the_supervisor_card(self):
        for key in self.KEYS:
            with self.subTest(key):
                self.assertIsNotNone(render(f"TUNE.{key}"))
        order = render("Object.keys(MGROUP)")
        self.assertEqual(order.index("super"), order.index("supervisor") + 1)
        self.assertEqual(render("MGROUP.super[0]"), "Super agent")

    def test_the_card_draws_its_rows_and_says_that_zero_turns_it_off(self):
        html = render("""cfg = {tuning: {super_day_usd: {group: 'super', value: 1, default: 1, min: 0, max: 20, unit: 'usd'},
            super_pass_usd: {group: 'super', value: 0.2, default: 0.2, min: 0, max: 1, unit: 'usd'}}, projects: [], supervisor_config: {modes: [], mode: 'gated', projects: {}}};
          medit = {values: {}, supMode: 'gated', supProjects: {}, kinds: {}, tiers: {}}; mtab = 'tuning'; tuningTab()""")
        self.assertIn("Super agent", html)
        self.assertIn("Spend per day", html)
        self.assertIn("turns it off", html)
        self.assertNotIn("super_model", html)   # the two pass models are fixed (plan 58): not editable here

    def test_the_off_note_links_to_this_card(self):
        got = render("""showPage = (n) => { window.__page = n; }; swAct({dataset: {sw: 'settings'}}); [mtab, window.__page]""")
        self.assertEqual(got, ["tuning", "models"])
```

`tests/test_tuning.py` round trip (the loop Fred will use): save `super_day_usd: 0` through `POST /api/config/models`
(200), `Hub.reload_tuning`, then `Hub.snapshot()["super"]` has `mode` `off` and `line` `off · oldest first`; `super_day_usd: 21`
is refused with the plan 58 range text; `super_model: "opus"` is refused (fixed alias).

Code (`web/app.js`), inside `TUNE` after the supervisor entries and inside `MGROUP` after `supervisor`:

```js
  // plan 59 (plan 58 D9): the super agent's numbers; its two pass models are fixed (haiku, sonnet for stuck work), so they are not here
  super_debounce_s: ["Wait after an event", "s", 1], super_sweep_s: ["Look again every", "s", 1], super_timeout_s: ["Pass timeout", "s", 1],
  super_notes_lines: ["Notes it keeps", "lines", 1], super_pass_usd: ["Spend per sort", "$", 1], super_day_usd: ["Spend per day", "$", 1],
```

```js
  super: ["Super agent", "sorts what needs you", "One short pass at a time sorts what needs you across every task, with its own notes and your standing orders. It runs on haiku, and on sonnet when stuck work is in the batch; those two are fixed. A daily spend of 0 turns it off: the window then lists everything oldest first, with every action."],
```

## 7.2 Landmarks and announcements

Tests, `SuperA11yTest`:

```python
@unittest.skipUnless(NODE, "Node is not installed")
class SuperA11yTest(unittest.TestCase):
    def test_list_is_a_nav_and_the_page_a_main(self):
        html = (APP.parent / "index.html").read_text(encoding="utf-8")
        self.assertRegex(html, r'<nav id="bchain"[^>]*aria-label="Tasks and chats"')
        self.assertRegex(html, r'<main id="bwrap"')
        self.assertEqual(html.count("<main"), 1)

    def test_an_answer_is_announced_once_with_the_new_count(self):
        got = render("""const live = {textContent: ''}; document = {getElementById: (id) => (id === 'sw-live' ? live : {})};
          setTimeout = (f) => f(); snap = {counts: {needs: 2}, super: {rev: 'r1', for_you: 2}}; superView = null;
          swAck = 'Confirm 1: sent to Paths.'; swAnnounceTick(); const first = live.textContent; live.textContent = ''; swAnnounceTick();
          swAck = 'Back in For you.'; swAnnounceTick(); [first, live.textContent]""")
        self.assertEqual(got, ["Confirm 1: sent to Paths. 2 for you.", "Back in For you. 2 for you."])   # the unchanged second tick said nothing

    def test_focus_goes_to_the_next_card_only_when_the_current_one_left(self):
        got = render("""const f = []; document = {querySelector: () => ({focus: () => f.push('card')})}; superView = {queue: [{items: [{key: 'b'}]}], later: []};
          page = 'board'; boardTask = ''; boardPick = ''; swSplit = new Set(); swFocusFix('a'); swFocusFix('b'); f""")
        self.assertEqual(got, ["card"])
```

Code: in `index.html` change `<div id="bchain" class="v-chain" aria-label="Tasks and chats"></div>` to the same element as
`<nav id="bchain" ...></nav>` and `<div id="bwrap" class="bwrap"></div>` to `<main id="bwrap" class="bwrap"></main>`
(check `style.css` for `div#bchain`/`div.bwrap` selectors: `grep -n "div#b\|div\.bwrap"`; none expected).

```js
let swAnnounced = "";
function swAnnounceTick() {  // one polite line per answer, with the new count; nothing when nothing changed
  const live = $("sw-live");
  if (!live || !swAck || swAck === swAnnounced) return;
  swAnnounced = swAck;
  live.textContent = "";
  setTimeout(() => { live.textContent = `${swAck} ${forYou()} for you.`; }, 30);
}
function swFocusFix(prevKey) {  // after a refetch: if the current card left, the next one takes focus (SW-5), else focus stays
  if (!prevKey || !swHome() || !superView || swItem(prevKey)) return;
  const c = document.querySelector("#bwrap .sw-qc.cur");
  if (c) c.focus();
}
```

Wiring: `swFetch` remembers `const prev = (swCards()[swCur] || { items: [{}] }).items[0].key` before the request and calls
`swFocusFix(prev)` after `renderBoard()`; `renderBoard()` calls `swAnnounceTick()` last; the shell (Task 6) carries
`<div class="sr" id="sw-live" aria-live="polite"></div>` once, outside the part `setHtml` replaces (it is a sibling of
`.idock`, drawn once by `renderBoard` when the home pane first shows). Cards never steal focus on a render: only
`swFocusFix`, the keys and the click handlers focus.

## 7.3 Every state, drawn and checked

Style additions (`web/style.css`): the sorting mark blinks only under `@media (prefers-reduced-motion: no-preference)`
and `:root:not([data-motion="reduce"])` (the mock's `.live`), on the note's `.mk.n.live`; the red note (`.sw-note.r`) uses
`--bad` for its mark and heading; `.sw-qc[aria-busy="true"] { opacity: .7; }`; nothing animates on a keyboard move.

`tests/live_super_check.py` grows the state sweep. One scratch service (plan 55's `Rig`, the fake claude, no provider, never
the running service) builds a project with tasks in these states; the modes come from service state or, where a scratch
service cannot reach them cheaply, from `page.route("**/api/super", ...)` serving a real GET body with the mode fields
overwritten (production code gets no seam):

| State | How it is reached |
|---|---|
| ranked | a fake pass over the items (`superagent.run` is the fake claude) |
| sorting | the fake pass held on a gate while the page loads |
| partial | `page.route` over a real body with `coverage` and two unannotated items |
| empty (`Nothing for you.`) | every item answered or put later |
| paused | `POST /api/super {pause}` |
| off | `config.json` `super_day_usd: 0`, reloaded |
| capped | `page.route`: `mode` `capped`, `spend.today` = the limit |
| failed | the fake claude's `SUPER-ERROR` order word |
| waiting | before the first pass |
| error | `super_model` set to `opus` in the config (a settings error) |
| the unshown cards | `Sent`, a refused action, a failed batch member, a Console-run session card, an observed card, an off action |

```python
STATES = ("ranked", "sorting", "partial", "empty", "paused", "off", "capped", "failed", "waiting", "error")
COUNT_JS = """(() => {
  const n = (s) => Number((String(s).match(/\\d+/) || [0])[0]);
  const items = swCards().reduce((a, c) => a + c.items.length, 0);
  return {row: n(document.querySelector('#sarow .sw-cnt').textContent), hdr: n(document.querySelector('#needsbtn').textContent),
          pill: n((document.querySelector('#bwrap .p-pill') || {}).textContent || ''), items, forYou: forYou(),
          proj: [...document.querySelectorAll('#bchain .sw-prj .sum b')].reduce((a, b) => a + n(b.textContent), 0),
          cur: document.querySelectorAll('#bwrap .sw-qc.cur').length, rec: document.querySelectorAll('#bwrap .sw-rec').length,
          note: (document.querySelector('#bwrap .sw-note .h') || {}).textContent || ''};
})()"""


def state_checks(page, name):  # every count on screen is one number; one current card; no advice when unranked; the note names the mode
    c = page.evaluate(COUNT_JS)
    assert c["row"] == c["hdr"] == c["forYou"] == c["items"], (name, "the counts agree", c)
    assert c["pill"] in (0, c["row"]), (name, "the pill agrees or names no count", c)
    assert c["proj"] <= c["row"], (name, "project lines never exceed the whole", c)
    assert c["cur"] == (1 if c["items"] else 0), (name, "one current card", c)
    if name in ("paused", "off", "capped", "failed", "waiting", "error"):
        assert c["rec"] == 0, (name, "no recommendation while unranked", c)
    want = {"sorting": "Sorting", "partial": "Recommendations cover", "paused": "Paused", "off": "The super agent is off",
            "capped": "limit of", "failed": "The last sort failed", "waiting": "The first sort starts", "error": ""}.get(name)
    if want:
        assert want in c["note"], (name, "the note names the mode", c["note"])
    if name != "empty":
        assert page.locator("#bwrap .sw-qc .btn:visible").count() >= 1, (name, "unranked keeps every action")
```

The sweep runs each state at 900, 400 and 340 px, dark and light, `reduced_motion: "reduce"`, device scale 1.0 and 1.3, asserts
no horizontal scroll, no console or page error, `SMALL` and `TINY` (11 px, 24 px) over `.sw-*`, and saves
`--shots DIR` PNGs named `<state>-<width>-<scheme>.png` for Fred.

## 7.4 Stop 1 (Fred looks)

`py -m tests.live_super_check --shots <scratch folder>`; Fred opens the PNGs: the eight mock states, `waiting`, `error`,
the unshown cards (5.3), 900 and 400 px, dark and light, and answers: do the unshown states read right; is "Open" for an
observed chat acceptable (D3); are the card buttons the right ones (D1). Task 8 does not start before his answer.

## 7.5 Steps and acceptance

- [ ] 1. Write the tests and extend the sweep; run them: red.
- [ ] 2. Make the 7.1 to 7.3 edits. `node --check web/app.js`; `py -m unittest tests.test_web tests.test_tuning`;
      `py -m tests.live_super_check --shots <scratch>`.
- [ ] 3. Full suite green (report the count). Stage the test files and only this task's hunks of `web/app.js`,
      `web/style.css`, `web/index.html`. Commit with the message above. **Stop 1.**
