# Task 5: the page and the cards, drawn from GET data

> Contract: [README.md](README.md) 4.5, 4.6, 4.10, 5 (SW-3 to SW-11, SW-15, SW-16). Decisions D1 a, D2 a, D3 a. The page is
> the home pane: it draws `superView` and decides nothing. A button exists because `acts` lists it and is enabled because
> its `off` is "". This task draws and moves focus; Task 6 makes the buttons do things (`swDo` is a stub here).

**Files:** `web/app.js`, `web/style.css`, `tests/test_web.py` (`SuperPageTest`), `tests/live_super_check.py`.
Commit boundary: `feat: the super agent page and its cards (plan 59 T5)`. Depends on Task 4 and plan 55 Tasks 1 to 3
(`pageHead`, `sect`, `actBtn`, `actLabel`, `iconBtn`). Anchors are quoted lines.

What the user gets: with nothing selected the right column shows the super agent: its head, a state note, the queue as
cards (the current one open, orange-tinted; the rest folded to an ask and one `◆` line), Later, Since you looked and
Orders; J K 1-4 Enter S O Esc work on the cards.

## 5.1 Tests first (red), `tests/test_web.py`

```python
import re


@unittest.skipUnless(NODE, "Node is not installed")
class SuperPageTest(unittest.TestCase):
    """Plan 59 Task 5: markup and keys from a canned GET /api/super. No gate in JS: off comes from the data."""
    ITEM = ("{key: 'k1', type: 'task', id: 't1', kind: 'decision', always: '', project: 'ARTCOUSTIC', project_dir: 'D:\\\\a', title: 'Paths and settings',"
            " label: 't1', ask: 'Which name for the product-sheet folder?', why: '', options: ['PRODUCT_SHEETS_DIR', 'SHEETS_DIR'], default: 'PRODUCT_SHEETS_DIR',"
            " left_s: 600, stay: 'the default is taken at 14:16', level: 'auto', age_s: 840, new: false, back: false, incomplete: '', observed: false, do: 'forward', rank: 1,"
            " say: 'Take a: the T02 spec already uses it.', source: '', path: ['ARTCOUSTIC', 'Paths and settings'], open: {kind: 'task', id: 't1', step: 3},"
            " facts: [], own: {mode: 'answer', post: '/api/task/message', off: '', body: {task: 't1', target: {step: 3}}, request_id: true},"
            " acts: {state: 'decision', line: '', hint: '', message: null, bar: [], menu: [], primary: ["
            "{id: '1', label: 'PRODUCT_SHEETS_DIR', post: '/api/task/message', body: {task: 't1'}, off: '', confirm: false},"
            "{id: '2', label: 'SHEETS_DIR', post: '/api/task/message', body: {task: 't1'}, off: '', confirm: false}]}}")
    VIEW = ("superView = {rev: 'r1', state: 'ranked', mode: 'ranked', why: '', paused: false, sorting: null, due: null, orders: '# o\\nfashion first', order_lines: ['fashion first'],"
            " digest: [], notes: '', last: {n: 3, at: 1000, ok: true, error: '', items: 4}, spend: {today: 0.06, passes: 11, day_limit: 1.0, pass_limit: 0.2},"
            " coverage: {live: 4, last_submitted: 4, never_reviewed: 0}, counts: {queue: 1, later: 0, always: 0, new: 0},"
            " controls: {pause: {label: 'Pause', off: ''}, resume: null, sort: {label: 'Sort now', off: ''}}, by_project: {'D:\\\\a': 1},"
            " since: {at: 800, lines: [], spent: {tasks: 0}}, later: [], queue: [{batch: '', rank: 1, answer: null, items: [ITEM]}]}; ")
    SETUP = ("snap = {now: 2000, counts: {needs: 1}, super: {rev: 'r1', mode: 'ranked', for_you: 1, later: 0, line: '', by_project: {}, marks: {}}, tasks: [], sessions: []}; "
             "swCur = 0; swSent = {}; swPick = {}; swAnswerTo = ''; swEditing = false; swSplit = new Set(); swAck = ''; ")

    @classmethod
    def x(cls, expr, view=""):
        return render("const ITEM = " + cls.ITEM + "; " + cls.SETUP + cls.VIEW + view + expr)

    def test_current_card_has_path_tags_ask_options_rec_links_and_one_primary(self):
        html = self.x("swCard(superView.queue[0], 0, true)")
        for want in ('class="sw-qc cur"', "ARTCOUSTIC", "Paths and settings", "decision · 14 min", "default at ",
                     "Which name for the product-sheet folder?", 'data-sw="pick"', "PRODUCT_SHEETS_DIR", "Super agent suggests",
                     "Take a: the T02 spec already uses it.", "Write your own answer", 'data-sw="open"', 'data-sw="later"'):
            self.assertIn(want, html)
        self.assertEqual(html.count("btn you"), 1)
        self.assertIn("Confirm 1", html)  # the preselected default

    def test_a_default_about_to_be_taken_and_an_always_item_stay_here_with_no_later(self):
        always = self.x("ITEM.always = 'Fable confirm'; ITEM.left_s = null; ITEM.stay = 'Fable confirm'; swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertIn("always yours", always)
        self.assertIn("Stays here: Fable confirm", always)
        self.assertNotIn('data-sw="later"', always)
        timed = self.x("swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertIn("Stays here: the default is taken at", timed)
        self.assertNotIn('data-sw="later"', timed)
        plain = self.x("ITEM.left_s = null; ITEM.stay = ''; swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertIn('data-sw="later"', plain)
        self.assertNotIn("Stays here", plain)

    def test_a_card_it_could_not_check_says_so_and_opens_the_task_first(self):
        html = self.x("ITEM.incomplete = 'verify output cut'; ITEM.left_s = null; ITEM.acts = {state: 'done', line: 'done', hint: '', message: null, bar: [], menu: [],"
                      " primary: [{id: 'accept', label: 'Accept', post: '/api/task/accept', body: {task: 't1'}, off: '', confirm: false}]}; ITEM.kind = 'accept';"
                      " swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertIn("Super agent · no recommendation", html)
        self.assertNotIn("Super agent suggests", html)
        self.assertIn("Open the task", html)
        self.assertEqual(html.count("btn you"), 0)       # Accept stays plain
        self.assertIn(">Accept<", html)
        self.assertRegex(html, r'btn go[^>]*data-sw="open"|data-sw="open"[^>]*btn go')

    def test_unranked_keeps_every_action_and_drops_the_advice(self):
        html = self.x("superView.state = 'unranked'; superView.mode = 'paused'; swCard(superView.queue[0], 0, true)")
        self.assertNotIn("Super agent suggests", html)
        self.assertIn("PRODUCT_SHEETS_DIR", html)
        self.assertIn("Confirm 1", html)

    def test_new_not_reviewed_and_back_tags_only_when_ranked(self):
        for field, tag in (("new = true; ITEM.do = ''", "new · not sorted yet"), ("do = ''", "not reviewed yet"), ("back = true", "back from Later")):
            with self.subTest(tag):
                html = self.x(f"ITEM.left_s = null; ITEM.{field}; swCard({{batch: '', items: [ITEM]}}, 0, true)")
                self.assertIn(tag, html)
                self.assertNotIn("Super agent suggests", html)  # advice that predates the item is not shown as a fact
        unranked = self.x("ITEM.new = true; superView.state = 'unranked'; swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertNotIn("new · not sorted yet", unranked)

    def test_a_folded_card_is_an_ask_and_one_line(self):
        html = self.x("swCard(superView.queue[0], 0, false)")
        self.assertIn('class="sw-qc"', html)
        self.assertIn('data-sw="cur"', html)
        self.assertIn("Take a: the T02 spec already uses it.", html)
        self.assertNotIn("btn", html)

    def test_an_observed_chat_only_opens_and_says_where_to_answer(self):
        html = self.x("ITEM.observed = true; ITEM.source = 'vscode'; ITEM.kind = 'stop'; ITEM.own = null; ITEM.left_s = null;"
                      " ITEM.acts = {state: 'observed', line: 'observed', hint: '', message: null, primary: [], bar: [], menu: []}; swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertIn("your VS Code chat", html)
        self.assertIn("Answer it in VS Code", html)
        self.assertIn('data-sw="open"', html)
        self.assertNotIn("Write your own answer", html)
        self.assertNotIn('data-aid=', html)

    def test_a_served_action_that_is_off_is_grey_with_its_reason(self):
        html = self.x("ITEM.acts.primary[0].off = 'still working: wait until it stops'; swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertRegex(html, r'<button[^>]*data-aid="1"[^>]*disabled[^>]*title="still working: wait until it stops"')

    def test_a_sent_card_shows_sent_and_its_buttons_are_off(self):
        html = self.x("swSent.k1 = 1999000; Date.now = () => 2000000; swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertIn("Sent. Waiting for it to move on.", html)
        self.assertIn('aria-busy="true"', html)
        buttons = re.findall(r"<button[^>]*>", html)
        self.assertTrue(buttons)
        for tag in buttons:
            self.assertIn("disabled", tag)
        late = self.x("swSent.k1 = 1980000; Date.now = () => 2000000; swCard({batch: '', items: [ITEM]}, 0, true)")
        self.assertNotIn("Sent.", late)  # after 10 s the card is live again

    def test_a_batch_card_lists_members_and_offers_both_ways(self):
        batch = ("{batch: 'acc', rank: 2, answer: {id: 'accept', label: 'Accept'}, items: ["
                 "Object.assign({}, ITEM, {key: 'a', id: 'ta', kind: 'accept', left_s: null, title: 'Storyboard kit', facts: [['verify passed · 3 steps · $0.41', 'ok']]}),"
                 "Object.assign({}, ITEM, {key: 'b', id: 'tb', kind: 'accept', left_s: null, title: 'Usage page', facts: [['verify passed · 2 steps · $0.18', 'ok']]})]}")
        html = self.x(f"swCard({batch}, 0, true)")
        for want in ("2 tasks", "accept · 2 items", "Storyboard kit", "Usage page", "verify passed · 3 steps", "Review one by one", "Accept both"):
            self.assertIn(want, html)
        self.assertEqual(html.count('data-sw="openid"'), 2)
        none = self.x(f"const B = {batch}; B.answer = null; swCard(B, 0, true)")
        self.assertNotIn("Accept both", none)
        self.assertIn("Review one by one", none)
        split = self.x(f"superView.queue = [{batch}]; swSplit.add('a|b'); swCards().map((c) => c.items.length)")
        self.assertEqual(split, [1, 1])
        self.assertEqual(self.x(f"superView.queue = [{batch}]; swCards().map((c) => c.items.length)"), [2])

    def test_note_per_mode(self):
        want = {"sorting": "Sorting 4 items.", "paused": "Paused by you.", "off": "The super agent is off.",
                "capped": "limit of $1.00 is reached.", "failed": "The last sort failed: the pass took longer than 120 s",
                "waiting": "The first sort starts in a moment.", "error": "claude.exe not found", "partial": "Recommendations cover 2 of 4 items."}
        for mode, text in want.items():
            with self.subTest(mode):
                html = self.x(f"superView.mode = '{mode}'; superView.why = 'claude.exe not found'; superView.sorting = {{n: 4, items: 4, since: 1}};"
                              " superView.last.ok = false; superView.last.error = 'the pass took longer than 120 s'; superView.coverage = {live: 4, last_submitted: 2, never_reviewed: 2};"
                              " swNote(superView)")
                self.assertIn(text, html)
        self.assertEqual(self.x("swNote(superView)"), "")
        off = self.x("superView.mode = 'off'; swNote(superView)")
        self.assertIn('data-sw="settings"', off)
        self.assertIn("Items that always need you come first", off)
        self.assertNotIn("Paused", off)

    def test_head_pill_facts_and_cost(self):
        html = self.x("swHead(superView)")
        for want in ("All projects", "Super agent", "? 1 for you", "Last sorted", "$0.06", "super agent today"):
            self.assertIn(want, html)
        capped = self.x("superView.mode = 'capped'; superView.state = 'unranked'; swHead(superView)")
        self.assertIn("Limit reached", capped)
        self.assertIn("Order", capped)
        self.assertIn("oldest first", capped)
        self.assertIn("of $1.00 today", capped)
        part = self.x("superView.mode = 'partial'; superView.coverage = {live: 14, last_submitted: 10, never_reviewed: 4}; swHead(superView)")
        self.assertIn("10 of 14", part)
        calm = self.x("superView.counts.queue = 0; superView.queue = []; snap.super.for_you = 0; swHead(superView)")
        self.assertIn("Nothing for you", calm)

    def test_for_you_sub_line_and_empty_text(self):
        html = self.x("swPage()")
        self.assertIn("1 item · ranked", html)
        empty = self.x("superView.queue = []; superView.counts.queue = 0; snap.super.for_you = 0; superView.later = [{key: 'z', id: 'z', project: 'P', title: 'T', by: 'sa', why: 'waits', until: '2027-01-15T15:06'}]; swPage()")
        self.assertIn("Nothing for you.", empty)
        self.assertIn("1 wait in Later, the next back at 15:06", empty)

    def test_later_since_and_orders_sections(self):
        later = self.x("superView.later = [{key: 'z', id: 'z', project: 'P', title: 'Hand-off hint', by: 'sa', why: 'Its step is still running.', until: '2027-01-15T14:30'},"
                       " {key: 'y', id: 'y', project: 'P', title: 'Mine', by: 'you', why: 'You put it later.', until: '2027-01-15T15:06'}]; swLater(superView)")
        for want in ("◆ ", "Its step is still running.", "Back 14:30", "You put it later.", 'data-sw="bring"', 'data-key="z"'):
            self.assertIn(want, later)
        self.assertIn("Nothing in Later.", self.x("swLater(superView)"))
        since = self.x("superView.since = {at: 800, lines: [{ts: 900, g: '✓', t: 'Storyboard kit finished', p: 'MOTION STUDIO', tm: '13:40'}], spent: {tasks: 3.1}}; swSince(superView)")
        for want in ("Storyboard kit finished", "13:40", "MOTION STUDIO", "$3.10", "Mark seen", "$0.06", "11 sorts"):
            self.assertIn(want, since)
        self.assertIn("Nothing new since you marked it seen", self.x("swSince(superView)"))
        orders = self.x("swOrders(superView)")
        self.assertIn("<li>fashion first</li>", orders)
        self.assertIn("Edit orders", orders)
        self.assertNotIn("Super agent proposes", orders)  # slice 3
        edit = self.x("swEditing = true; swOrders(superView)")
        self.assertIn("<textarea", edit)
        self.assertIn("# o\nfashion first", edit)
        self.assertIn("Save orders", edit)

    def test_counts_on_the_page_are_the_one_number(self):
        got = self.x("[forYou(), swHead(superView).includes('1 for you'), swPage().includes('1 item'), swCards().reduce((a, c) => a + c.items.length, 0)]")
        self.assertEqual(got, [1, True, True, 1])

    KEYS = ("const calls = []; swDo = (w, c) => calls.push(w); document = {getElementById: () => ({focus() {}}), querySelector: () => null};"
            " renderBoard = () => {}; page = 'board'; boardTask = ''; boardPick = '';"
            " const E = (o) => Object.assign({key: 's', ctrlKey: false, metaKey: false, altKey: false, defaultPrevented: false, preventDefault() {},"
            " target: {closest: () => null, matches: () => false}}, o); ")

    def test_keys_never_fire_while_typing_or_with_a_modifier_or_off_the_home_pane(self):
        cases = {"typing": "swKeys(E({target: {closest: () => ({}), matches: () => false}}))", "ctrl": "swKeys(E({ctrlKey: true}))",
                 "alt": "swKeys(E({altKey: true}))", "meta": "swKeys(E({metaKey: true}))", "a task is open": "boardTask = 't1'; swKeys(E({}))",
                 "already handled": "swKeys(E({defaultPrevented: true}))", "no view": "superView = null; swKeys(E({}))"}
        for label, js in cases.items():
            with self.subTest(label):
                self.assertEqual(self.x(self.KEYS + js + "; calls"), [])
        self.assertEqual(self.x(self.KEYS + "swKeys(E({})); calls"), ["later"])  # S reaches swDo; Task 6 decides what it does

    def test_the_keys_move_pick_confirm_later_and_open(self):
        base = (self.KEYS + "superView.queue.push({batch: '', rank: 2, answer: null, items: [Object.assign({}, ITEM, {key: 'k2', id: 't2', left_s: null})]}); "
                "const key = (k) => swKeys(E({key: k})); ")
        self.assertEqual(self.x(base + "key('j'); const a = swCur; key('k'); const b = swCur; key('j'); key('j'); const c = swCur; [a, b, c]"), [1, 0, 1])
        self.assertEqual(self.x(base + "key('2'); swPick.k1"), "2")            # 2 picks the second option of the current card
        self.assertEqual(self.x(base + "key('3'); swPick.k1 || ''"), "")      # there is no third option
        self.assertEqual(self.x(base + "key('s'); key('o'); key('Enter'); calls"), ["later", "open", "confirm"])

Headless, `tests/live_super_check.py` gains `page_checks` for the home pane: `#bwrap .sw-qc` exists, exactly one `.cur`,
one `.btn.you` inside it, every `.sw-qc .btn` at least 24 px, every text at least 11 px, no horizontal scroll at 900,
400 and 340 px, Tab reaches the current card's controls and J moves focus to the next card.

## 5.2 Code (`web/app.js`)

Insert after Task 4's block. `fableName`, `actLabel`, `actBtn`, `pageHead`, `sect` are plan 55's.

```js
// -- plan 59 Task 5: the page --------------------------------------------------------------------------------------
let swCur = 0;            // the focused card
let swSent = {};          // key -> ms: answered in this window; "Sent" until the service says the item left (10 s at most)
let swPick = {};          // key -> the decision option id Fred selected (the default until he picks one)
let swAnswerTo = "";      // key of the card whose "Write your own answer" owns the box
let swSplit = new Set();  // batch cards split by "Review one by one": the members' keys joined by "|"
let swAck = "";           // one line under the For you head after an answer
let swEditing = false;    // Edit orders is open
const SW_SENT_MS = 10000;
const SW_UNR = "Items that always need you come first, then the rest by age, with every action and no recommendations.";
const SW_KIND = { accept: "finished", hand_off: "hand-off hint", handed: "handed off", failed_twice: "failed twice", suggestion: "supervisor suggests",
  hold: "held", stop: "asks you", verify_failed: "verify failed", context: "context" };
const swKindWord = (k) => SW_KIND[k] || String(k || "").replace(/_/g, " ");
const swApp = (s) => ({ vscode: "VS Code", terminal: "terminal", opencode: "OpenCode", codex: "Codex" }[s] || s || "outside");
const swHm = (ts) => (ts ? new Date(ts * 1000).toTimeString().slice(0, 5) : "");
const swUntil = (u) => String(u || "").slice(-5);                         // "2027-01-15T15:06" -> "15:06"
const swAge = (s) => { s = Math.max(0, Math.round(s || 0)); return s < 60 ? "now" : s < 3600 ? Math.round(s / 60) + " min" : Math.round(s / 3600) + " h"; };
const swRanked = (v) => v.state === "ranked";
const swMoney = (x) => "$" + Number(x || 0).toFixed(2);
function swKey(card) { return card.items.map((i) => i.key).join("|"); }
function swCards() {  // the cards as drawn: a split batch becomes one card per member (a window choice, not stored)
  const out = [];
  for (const c of (superView && superView.queue) || []) {
    if (c.items.length > 1 && swSplit.has(swKey(c))) c.items.forEach((i) => out.push({ batch: "", rank: c.rank, answer: null, items: [i] }));
    else out.push(c);
  }
  return out;
}
const swStay = (it) => it.stay || "";  // SW-6: why a card has no Later: code's string (stay_reason), never derived here
function swTags(card, v) {
  const t = [], it = card.items[0], one = card.items.length === 1;
  if (one && it.always) t.push(["always yours", "", "Code always shows this to you: the super agent cannot put it later or batch it"]);
  if (one && it.left_s != null && it.default) t.push([`default at ${swHm(snap.now + it.left_s)}`, "y", `At level auto, Console takes the default at ${swHm(snap.now + it.left_s)}`]);
  if (one && it.observed) t.push([`your ${swApp(it.source)} chat`, "dash", "Only you answer it, in its own app"]);
  if (swRanked(v) && one) {
    if (it.new) t.push(["new · not sorted yet", ""]);
    else if (it.back) t.push(["back from Later", ""]);
    else if (!it.do) t.push(["not reviewed yet", "", "The last sort had no room for it"]);
  }
  return t.length ? `<span class="sw-tags">${t.map(([x, c, tip]) => `<span class="sw-tag${c ? " " + c : ""}"${tip ? ` title="${esc(tip)}"` : ""}>${esc(x)}</span>`).join("")}</span>` : "";
}
function swRec(card, v) {  // SW-5, SW-7: the suggestion block, or why there is none; null when it says nothing
  const it = card.items[0];
  if (!swRanked(v) || it.new || it.back || !it.do) return null;
  if (card.items.some((i) => i.incomplete)) return { none: true, text: card.items.length === 1 ? "It could not check this one: " + it.incomplete + ". Open the task before you answer." : "It could not check every one of these. Open the tasks before you answer." };
  return it.say ? { text: it.say } : null;
}
function swPath(card) {
  if (card.items.length > 1) return `<span class="sw-path"><span class="pt cur">${card.items.length} tasks</span><span class="sep">·</span><span class="pt">${esc([...new Set(card.items.map((i) => i.path[0]))].join(", "))}</span></span>`;
  const p = card.items[0].path;
  return `<span class="sw-path">${p.map((x, k) => `<span class="pt${k === p.length - 1 ? " cur" : ""}">${esc(x)}</span>`).join('<span class="sep">›</span>')}</span>`;
}
function swKindLine(card) {
  const it = card.items[0], n = card.items.length;
  return n > 1 ? `${swKindWord(it.kind)} · ${n} items · ${swAge(Math.min(...card.items.map((i) => i.age_s)))}` : `${swKindWord(it.kind)} · ${swAge(it.age_s)}`;
}
function swBtn(it, a, cls = "", o = {}) {  // one served action; a button exists because acts lists it, off comes from the data
  const tip = a.off || o.tip || "";
  return `<button class="btn${cls ? " " + cls : ""}" data-sw="act" data-key="${esc(it.key)}" data-aid="${esc(a.id)}"${a.off || o.disabled ? " disabled" : ""}${tip ? ` title="${esc(tip)}"` : ""}>${esc(o.label || actLabel(a, it.acts.state))}</button>`;
}
function swOptions(it) {  // a decision's options as selectable rows, the default preselected; the picked one is the primary
  const opts = it.acts.state === "decision" ? it.acts.primary : [];
  if (!opts.length) return { html: "", pick: null };
  const def = opts.find((a) => a.label === it.default) || opts[0], pick = opts.find((a) => a.id === swPick[it.key]) || def;
  const rows = opts.map((a, j) => `<button class="sw-opt${a === def ? " isdef" : ""}" data-sw="pick" data-key="${esc(it.key)}" data-aid="${esc(a.id)}" aria-pressed="${a === pick}"${a.off ? ` disabled title="${esc(a.off)}"` : ""} title="Key ${j + 1}">
    <span class="k">${esc(a.id)}</span><span>${esc(a.label)}</span>${a === def ? `<span class="def">default${it.left_s != null ? " · " + swHm(snap.now + it.left_s) : ""}</span>` : "<span></span>"}</button>`).join("");
  return { html: `<div class="sw-opts" role="group" aria-label="Options">${rows}</div>`, pick };
}
function swMembers(card) {
  return `<ul class="sw-bl">${card.items.map((m) => { const f = (m.facts || [])[0] || ["", "h"];
    return `<li><span class="mk ${f[1] === "ok" ? "g" : "h"}" aria-hidden="true"></span><span class="bt"><b>${esc(m.path.join(" › "))}</b><span class="${f[1] === "ok" ? "ok" : ""}">${esc(f[0])}</span></span><button class="lnk" data-sw="openid" data-key="${esc(m.key)}">Open</button></li>`; }).join("")}</ul>`;
}
function swCard(card, i, cur, dock = false) {
  const v = superView, it = card.items[0], batch = card.items.length > 1, rec = swRec(card, v), sent = !batch && swSent[it.key] && Date.now() - swSent[it.key] < SW_SENT_MS;
  const ask = batch ? `${card.items.length} items with the same question: ${it.ask}` : it.ask;
  const top = `<div class="sw-qtop">${swPath(card)}${swTags(card, v)}<span class="kd">${esc(swKindLine(card))}</span></div>`;
  const label = `${card.items.map((m) => m.title).join(" and ")}: ${ask}`;
  if (!cur) return `<article class="sw-qc" data-sw="cur" data-i="${i}" tabindex="-1" aria-label="${esc(label)}">${top}<div class="sw-ask one">${esc(ask)}</div>${rec ? `<div class="sw-rec1"><span class="sw-dm" aria-hidden="true">◆</span>${rec.none ? "No recommendation: it could not check this one" : esc(rec.text)}</div>` : ""}</article>`;
  const incomplete = card.items.some((m) => m.incomplete), opt = batch ? { html: "", pick: null } : swOptions(it);
  let body = `<div class="sw-ask">${esc(ask)}</div>`;
  if (!batch && it.observed) body += `<div class="sw-why">Only you answer it, in its own app (${esc(swApp(it.source))}). Open shows it here, read only. Answer it in ${esc(swApp(it.source))}.</div>`;
  body += opt.html;
  if (batch) body += swMembers(card);
  else if ((it.facts || []).length) body += `<ul class="sw-bl"><li><span class="mk ${it.facts[0][1] === "ok" ? "g" : "h"}" aria-hidden="true"></span><span class="bt"><span class="${it.facts[0][1] === "ok" ? "ok" : ""}">${esc(it.facts[0][0])}</span></span><span></span></li></ul>`;
  if (rec) body += `<div class="sw-rec${rec.none ? " none" : ""}"><span class="sw-dm" aria-hidden="true">◆</span><span><span class="who">${rec.none ? "Super agent · no recommendation" : "Super agent suggests"}</span>${esc(rec.text)}</span></div>`;
  const links = [], openBtn = incomplete || (!batch && it.observed);  // then Open is a button, not a link
  if (!dock && !openBtn) links.push(`<button class="lnk" data-sw="open" data-key="${esc(it.key)}">Open</button>`);
  if (!batch && it.own) links.push(`<button class="lnk" data-sw="words" data-key="${esc(it.key)}"${it.own.off ? ` disabled title="${esc(it.own.off)}"` : ""}>Write your own answer</button>`);
  const stay = batch ? "" : swStay(it);
  links.push(stay ? `<span class="sw-stay">Stays here: ${esc(stay)}</span>` : `<button class="lnk mut2" data-sw="later" data-key="${esc(swKey(card))}" title="Back in an hour">Later</button>`);
  let btns = "";
  if (batch) btns = `<button class="btn" data-sw="split" data-key="${esc(swKey(card))}">Review one by one</button>` + (card.answer ? `<button class="btn you" data-sw="batch" data-key="${esc(swKey(card))}">${esc(card.answer.label)} ${card.items.length === 2 ? "both" : "all " + card.items.length}</button>` : "");
  else {
    const open = `<button class="btn go" data-sw="open" data-key="${esc(it.key)}">${incomplete ? "Open the task" : "Open"}</button>`;
    const bar = it.acts.bar.map((a) => swBtn(it, a)).join("");
    const prim = opt.pick ? swBtn(it, opt.pick, incomplete ? "" : "you", { label: "Confirm " + opt.pick.id })
      : it.acts.primary.map((a) => swBtn(it, a, incomplete ? "" : "you")).join("");
    btns = (openBtn ? open : "") + bar + prim;
  }
  body += `<div class="sw-acts">${links.join("")}<span class="bs">${btns}</span></div>`;
  if (sent) body += `<div class="sw-foot" role="status">Sent. Waiting for it to move on.</div>`;
  return `<article class="sw-qc cur${dock ? " dock" : ""}" data-sw="card" data-i="${i}" tabindex="${dock ? -1 : 0}" aria-label="${esc(label)}"${sent ? ' aria-busy="true"' : ""}>${top}${sent ? body.replace(/<button class="/g, '<button disabled class="') : body}</article>`;
}
function swNote(v) {  // SW-8, SW-16: one line per mode; "" for ranked
  const n = (cls, mk, h, w) => `<div class="sw-note${cls}"><span class="mk ${mk}" aria-hidden="true"></span><span class="h">${esc(h)}</span><span class="w">${w}</span></div>`;
  const cov = v.coverage || {}, live = cov.live || 0, seen = live - (cov.never_reviewed || 0), link = ' <button class="lnk" data-sw="settings">Models settings</button>';
  switch (v.mode) {
    case "sorting": { const k = v.sorting ? v.sorting.items : 0; return n("", "n live", `Sorting ${k} ${k === 1 ? "item" : "items"}.`, "Cards keep their last recommendations until it ends."); }
    case "partial": return n("", "h", `Recommendations cover ${seen} of ${live} items.`, `The last sort had room for ${seen}. The ${live - seen} marked not reviewed follow, oldest first, until the next sort. Sort now continues it.`);
    case "paused": return n("", "q", "Paused by you.", "Nothing is sorted until you resume. " + SW_UNR);
    case "off": return n("", "q", "The super agent is off.", `Its daily limit is $0. ${SW_UNR}${link}`);
    case "capped": return n("", "q", `Today's limit of ${swMoney((v.spend || {}).day_limit)} is reached.`, `Sorting starts again tomorrow, or raise the limit. ${SW_UNR}${link}`);
    case "failed": return n(" r", "r", `The last sort failed: ${(v.last || {}).error || "no reason given"}`, SW_UNR + " Sort again, or it tries at the next change.");
    case "waiting": return n("", "q", "The first sort starts in a moment.", "Items that always need you come first, then the rest by age.");
    case "error": return n(" r", "r", v.why || "The super agent cannot sort.", SW_UNR);
  }
  return "";
}
function swHead(v) {
  const k = forYou(), p = {
    ranked: k ? [`? ${k} for you`, "y"] : ["✓ Nothing for you", "g"], partial: [`? ${k} for you`, "y"], sorting: ["Sorting", ""], paused: ["Paused", "q"],
    off: ["Off", "q"], capped: ["Limit reached", "q"], failed: ["✕ Sort failed", "r"], error: ["✕ Cannot sort", "r"],
    waiting: k ? [`? ${k} for you`, "y"] : ["✓ Nothing for you", "g"] }[v.mode] || ["", ""];
  const cov = v.coverage || {}, facts = [];
  if (v.mode === "partial") facts.push(["Reviewed", `${(cov.live || 0) - (cov.never_reviewed || 0)} of ${cov.live || 0}`]);
  if (!swRanked(v)) facts.push(["Order", "oldest first"]);
  if (v.last && v.last.ok) facts.push(["Last sorted", swHm(v.last.at)]);
  return pageHead({ eyebrow: "All projects", title: "Super agent", pill: p, facts, cost: swMoney((v.spend || {}).today),
    costSub: v.mode === "capped" ? `of ${swMoney(v.spend.day_limit)} today` : "super agent today" });
}
function swLater(v) {
  if (!v.later.length) return '<p class="sw-calm">Nothing in Later.</p>';
  return `<div class="sw-lt">${v.later.map((e) => `<div class="sw-li"><div class="l1"><span class="pj">${esc(e.project)}</span><span class="pj sep" aria-hidden="true">›</span><span class="t">${esc(e.title)}</span></div>
    <div class="w">${e.by === "sa" ? '<span aria-hidden="true">◆ </span>' : ""}${esc(e.why)} <span class="bk">Back ${esc(swUntil(e.until))}</span></div>
    <button class="btn sm" data-sw="bring" data-key="${esc(e.key)}">Bring back</button></div>`).join("")}</div>`;
}
function swSince(v) {
  const s = v.since || { lines: [], spent: {} }, sp = v.spend || {};
  const spent = `<div class="sw-spent">Spent since ${esc(swHm(s.at) || "the start")}: <b>${swMoney((s.spent || {}).tasks)}</b> on tasks. Super agent today: <b>${swMoney(sp.today)}</b>, ${sp.passes || 0} ${sp.passes === 1 ? "sort" : "sorts"}.</div>`;
  if (!s.lines.length) return `<p class="sw-calm">Nothing new since you marked it seen at ${esc(swHm(s.at))}.</p>${spent}`;
  const rows = s.lines.map((r) => `<div class="sw-dl"><span class="sg ${r.g === "✕" ? "r" : r.g === "✓" ? "g" : ""}" aria-hidden="true">${esc(r.g)}</span><span class="tx2">${esc(r.t)}</span><span class="tm">${esc(r.tm)}</span><span class="pj">${esc(r.p)}</span></div>`).join("");
  return `<div class="sw-dg">${rows}</div>${spent}<button class="lnk" data-sw="seen">Mark seen</button>`;
}
function swOrders(v) {  // SW-11: the lines as a list; Edit opens the file's text. No proposals (slice 3)
  if (swEditing) return `<label class="sr" for="ordersin">Standing orders, one per line</label><textarea class="sw-oed" id="ordersin" rows="6">${esc(v.orders || "")}</textarea>
    <div class="sw-orow"><button class="btn sm ghost" data-sw="ocancel">Cancel</button><button class="btn sm" data-sw="osave">Save orders</button></div>`;
  return (v.order_lines.length ? `<ol class="sw-ord">${v.order_lines.map((o) => `<li>${esc(o)}</li>`).join("")}</ol>` : '<p class="sw-calm">No standing orders.</p>') + '<button class="lnk" data-sw="oedit">Edit orders</button>';
}
function swPage() {
  const v = superView, cards = swCards(), k = forYou(), lat = v.later;
  if (swCur > cards.length - 1) swCur = Math.max(0, cards.length - 1);
  const sub = `${cards.length < k ? `${k} items in ${cards.length} cards` : `${k} ${k === 1 ? "item" : "items"}`}${k ? (swRanked(v) ? " · ranked" : " · oldest first") : ""}`;
  const keys = '<div class="sw-keys" aria-hidden="true"><span><kbd>J</kbd> <kbd>K</kbd> move</span><span><kbd>1</kbd> to <kbd>4</kbd> pick</span><span><kbd>Enter</kbd> confirm</span><span><kbd>S</kbd> later</span><span><kbd>O</kbd> open</span></div>';
  const ack = swAck ? `<p class="sw-ack"><span class="g" aria-hidden="true">✓</span><span>${esc(swAck)}</span></p>` : "";
  const run = swReady() ? (snap.super.line.match(/^(\d+) running/) || [0, 0])[1] : 0;
  const body = swNote(v) + ack + (k ? `<div class="sw-qq">${cards.map((c, i) => swCard(c, i, i === swCur)).join("")}</div>${keys}`
    : `<p class="sw-calm" id="emptyq" tabindex="-1"><b>Nothing for you.</b> ${run} tasks run${lat.length ? `; ${lat.length} wait in Later, the next back at ${esc(swUntil(lat[0].until))}` : ""}. The super agent looks again when something changes.</p>`);
  return swHead(v) + sect("For you", sub, body, k ? "y" : "") + sect("Later", lat.length ? `${lat.length} · back at their time` : "none", swLater(v))
    + sect("Since you looked", `since ${swHm((v.since || {}).at) || "the start"}`, swSince(v)) + sect("Orders", `yours · ${v.order_lines.length}`, swOrders(v));
}
function swDo(what, card) {}  // Task 6: later, open, confirm
function swKeys(e) {  // SW-15: J K 1-4 Enter S O Esc; only on the home pane, never while typing, never with a modifier
  if (!superView || !swHome() || e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
  const tg = e.target;
  if (tg && tg.closest && tg.closest("input, textarea, select, [contenteditable]")) return;
  const cards = swCards(), card = cards[swCur], k = e.key, onCard = tg && tg.matches && tg.matches(".sw-qc"), onCtl = tg && tg.closest && tg.closest("button") && !onCard;
  const move = (d) => { swCur = Math.min(Math.max(swCur + d, 0), cards.length - 1); swAnswerTo = ""; renderBoard(); const c = document.querySelector("#bwrap .sw-qc.cur"); if (c) c.focus(); };
  if (k === "Escape") { if (swAnswerTo) swAnswerTo = ""; else if (swSel) swSel = ""; else return; renderBoard(); }
  else if (!card) return;
  else if (k === "j" || k === "J" || (k === "ArrowDown" && onCard)) move(1);
  else if (k === "k" || k === "K" || (k === "ArrowUp" && onCard)) move(-1);
  else if (/^[1-4]$/.test(k)) {
    const it = card.items[0], opts = card.items.length === 1 && it.acts.state === "decision" ? it.acts.primary : [];
    if (!opts[+k - 1]) return;
    swPick[it.key] = opts[+k - 1].id; renderBoard();
  } else if (k === "Enter") { if (onCtl) return; swDo("confirm", card); }
  else if (k === "s" || k === "S") swDo("later", card);
  else if (k === "o" || k === "O") swDo("open", card);
  else return;
  e.preventDefault();
}
document.addEventListener("keydown", swKeys);
```

Wiring (anchors): in `renderBoard()` after the list is drawn, `if (swHome() && superView) setHtml($("bwrap"), `<div class="sw-page" data-p="super"><div class="iscroll">${swPage()}</div></div>`);`
(the box and bar are added by Task 6 around it, with plan 55's `taskShell`; until then the page scrolls alone); the existing
`homePick`/auto-open of a first task does not exist and is not added. A card's `data-sw="cur"` click sets `swCur`
(Task 6 routes every `data-sw` value; the `cur` branch is added here: `swCur = +t.dataset.i; swAnswerTo = ""; renderBoard();`).
A key `Escape` that leaves a selection never closes the window or the pill (the global Escape handler returns first
when `swKeys` handled it: it already checks `e.defaultPrevented`).

## 5.3 Style (`web/style.css`)

Port the mock's rules for these selector groups (locked mock lines 60 to 365; copy the declarations verbatim, rename the
selector with the `sw-` prefix, keep the `@container` queries): `.qq .qc .qc.cur .qc.dock .qtop .path .pt .sep .kd`,
`.tags .tag .tag.y .tag.dash`, `.ask .ask.one .why`, `.rec .rec .who .rec.none .rec1`, `.opts .opt .opt .k .def .opt.isdef
.opt[aria-pressed="true"]`, `.bl`, `.sacts` (as `.sw-acts` with `.bs`), `.stay` (as `.sw-stay`), `.lnk` (as `.sw-lnk`; the
markup above keeps plan 55's `lnk` class and styles `.lnk` once there: do not define it twice), `.keys .keys kbd`,
`.calm .ack .note .note .mk .h .w .note.r`, `.lt .li`, `.dg .dl .spent`, `.ord .oed .orow`. The two that carry the
decisions Fred took (SW-5):

```css
.sw-qc { padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--win); cursor: pointer; }
.sw-qc.cur { cursor: default; border-color: color-mix(in srgb, var(--you) 45%, var(--line)); background: color-mix(in srgb, var(--you) 6%, var(--win)); }
.sw-qc:focus-visible { outline: 2px solid var(--ink); outline-offset: 1px; }
.sw-rec { display: flex; gap: 8px; margin: 8px 0; padding: 8px 10px; border-radius: 6px; background: var(--raise); color: var(--ink); font-size: 13px; }
.sw-rec .who { display: block; font: 600 11px var(--mono); letter-spacing: .04em; text-transform: uppercase; color: var(--mut); margin-bottom: 2px; }
.sw-rec.none { background: transparent; border: 1px dashed var(--line); color: var(--mut); }
```

Orange stays "for you": only the current card's tint and border, the `you` primary, `default at`, the count and the `? N for you`
pill use `--you`. The 11 px and 24 px floors apply to every ported rule (raise any 10 or 10.5 px label to 11).

## 5.4 Steps and acceptance

- [ ] 1. Write `SuperPageTest` (without the scaffolding lines named above) and the headless `page_checks`; red.
- [ ] 2. Make the 5.2 and 5.3 edits. `node --check web/app.js`; `py -m unittest tests.test_web`; `py -m tests.live_super_check`.
- [ ] 3. Full suite green (report the count). Stage the test files and only this task's hunks of `web/app.js` and
      `web/style.css`. Commit with the message above.
