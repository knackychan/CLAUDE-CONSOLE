# Task 6: answers in place, Later, batch, the bar and the one box

> Contract: [README.md](README.md) 4.5 to 4.9, 5 (SW-6, SW-9 to SW-11, SW-13, SW-14). Decisions D1 a, D2 a, D4 a, D6 a, D11 a.
> Every answer is a POST to the route the data names (`acts.*.post` and `.body`, `own.post` and `.body`); the page holds
> no route for a task, a session or a decision. The only routes written in the super agent code are `/api/super` and
> the composer's own Prep. A test pins that (6.1, last test).

**Files:** `web/app.js`, `web/style.css`, `tests/test_web.py` (`SuperActTest`), `tests/live_super_check.py`.
Commit boundary: `feat: answer the super agent's cards in place, Later, batch, the bar and the one box (plan 59 T6)`.
Depends on Task 5 and plan 55 Task 2 (`armBtn`, `ARM`, `actLabel`, `openActionForm`, `FORM_IDS`).

What the user gets: Confirm, Accept, Approve, Reject, Retry (opens its form), Start next task, Resume and the rest work
on the card; a batch of identical Accepts is one click or a split; Later puts a card away for an hour; Bring back; Mark
seen; Edit orders; Pause, Resume and Sort in the bar; a box whose chip says where Enter goes.

## 6.1 Tests first (red), `tests/test_web.py`

```python
@unittest.skipUnless(NODE, "Node is not installed")
class SuperActTest(unittest.TestCase):
    """Plan 59 Task 6: a click posts what the data says, nothing else; off posts nothing; a failure leaves the card."""
    CALLS = ("const calls = []; api = async (p, b) => { calls.push([p, b]); if (api.fail) throw new Error(api.fail); return api.ret || {}; };"
             " swFetch = async () => {}; renderBoard = () => {}; armBtn = (b) => { b.dataset.armed = '1'; }; openTask = (id) => calls.push(['open', id]);"
             " openSession = (id) => calls.push(['session', id]); const btn = (aid, key) => ({dataset: {aid, key: key || 'k1'}, disabled: false}); ")

    def x(self, expr):
        return SuperPageTest.x(self.CALLS + expr)

    def test_a_served_action_posts_its_own_route_and_body(self):
        table = [  # state, action as served -> what the click posts
            ("plan_ready", "{id: 'confirm', label: 'Confirm plan', post: '/api/task/confirm', body: {task: 't1'}, off: '', confirm: false}", ["/api/task/confirm", {"task": "t1"}]),
            ("suggestion", "{id: 'approve', label: 'Approve', post: '/api/task/supervisor', body: {task: 't1', wake: 3, action: 'approve'}, off: '', confirm: false}",
             ["/api/task/supervisor", {"task": "t1", "wake": 3, "action": "approve"}]),
            ("done", "{id: 'accept', label: 'Accept', post: '/api/task/accept', body: {task: 't1'}, off: '', confirm: false}", ["/api/task/accept", {"task": "t1"}]),
            ("stuck", "{id: 'stepdone', label: 'Accept step result', post: '/api/task/stepdone', body: {task: 't1'}, off: '', confirm: false}", ["/api/task/stepdone", {"task": "t1"}]),
            ("handed", "{id: 'start_next', label: 'Start next task', post: '/api/task/resume', body: {task: 't9'}, off: '', confirm: false}", ["/api/task/resume", {"task": "t9"}]),
            ("session_interrupted", "{id: 'resume', label: 'Resume', post: '/api/continue', body: {session: 's1', text: 'go on'}, off: '', confirm: false}", ["/api/continue", {"session": "s1", "text": "go on"}]),
            ("decision", "{id: '2', label: 'SHEETS_DIR', post: '/api/task/message', body: {task: 't1', mode: 'answer', text: 'SHEETS_DIR', request_id: 'u'}, off: '', confirm: false}",
             ["/api/task/message", {"task": "t1", "mode": "answer", "text": "SHEETS_DIR", "request_id": "u"}]),
        ]
        for state, action, want in table:
            with self.subTest(state):
                got = self.x(f"ITEM.acts.state = '{state}'; ITEM.acts.primary = [{action}]; ITEM.acts.bar = []; "
                             "superView.queue = [{batch: '', rank: 1, answer: null, items: [ITEM]}]; (async () => { await swRunAct(btn(ITEM.acts.primary[0].id)); return calls; })()")
                self.assertEqual(got, [want])

    def test_off_unknown_and_forms_post_nothing_and_confirm_needs_two_clicks(self):
        base = ("superView.queue = [{batch: '', rank: 1, answer: null, items: [ITEM]}]; ITEM.acts.bar = []; "
                "ITEM.acts.primary = [{id: 'a', label: 'A', post: '/api/x', body: {}, off: 'busy', confirm: false}, {id: 'f', label: 'Retry on a model', post: '', body: {task: 't1'}, off: '', confirm: false},"
                " {id: 'c', label: 'Confirm', post: '/api/task/confirm', body: {task: 't1'}, off: '', confirm: true}]; ")
        self.assertEqual(self.x(base + "(async () => { await swRunAct(btn('a')); await swRunAct(btn('nope')); return calls; })()"), [])
        form = self.x(base + "swPending = null; openActionForm = () => {}; (async () => { await swRunAct(btn('f')); return [calls, swPending]; })()")
        self.assertEqual(form, [[["open", "t1"]], {"tid": "t1", "aid": "f"}])   # the task opens, then its own form
        two = self.x(base + "(async () => { const b = btn('c'); await swRunAct(b); const first = calls.length; await swRunAct(b); return [first, calls.length]; })()")
        self.assertEqual(two, [0, 1])

    def test_a_posted_card_is_sent_and_a_refused_one_keeps_its_reason(self):
        base = ("superView.queue = [{batch: '', rank: 1, answer: null, items: [ITEM]}]; ITEM.acts.bar = []; "
                "ITEM.acts.primary = [{id: 'confirm', label: 'Confirm', post: '/api/task/confirm', body: {task: 't1'}, off: '', confirm: false}]; ")
        ok = self.x(base + "(async () => { await swRunAct(btn('confirm')); return [!!swSent.k1, swErr.k1 || '']; })()")
        self.assertEqual(ok, [True, ""])
        bad = self.x(base + "api.fail = 'a step is running'; (async () => { await swRunAct(btn('confirm')); return [!!swSent.k1, swErr.k1]; })()")
        self.assertEqual(bad, [False, "a step is running"])

    def test_open_goes_to_the_task_the_failed_step_or_the_read_only_chat(self):
        self.assertEqual(self.x("(async () => { swOpen(ITEM); return calls; })()"), [["open", "t1"]])
        step = self.x("ITEM.kind = 'stuck'; ITEM.open.step = 2; (async () => { swOpen(ITEM); return [calls, boardPick]; })()")
        self.assertEqual(step, [[["open", "t1"]], "s2"])
        chat = self.x("ITEM.type = 'session'; ITEM.id = 's7'; ITEM.open = {kind: 'session', id: 's7', step: 0}; (async () => { swOpen(ITEM); return calls; })()")
        self.assertEqual(chat, [["session", "s7"]])

    def test_later_posts_the_card_keys_and_stays_when_the_card_says_so(self):
        got = self.x("ITEM.left_s = null; ITEM.stay = ''; superView.queue = [{batch: 'acc', rank: 1, answer: null, items: [ITEM, Object.assign({}, ITEM, {key: 'k2'})]}];"
                     " api.ret = {done: ['k1', 'k2'], later: [{until: '2027-01-15T15:06'}]}; (async () => { await swDo('later', swCards()[0]); return calls; })()")
        self.assertEqual(got, [["/api/super", {"action": "later", "keys": ["k1", "k2"]}]])
        stays = self.x("(async () => { await swDo('later', swCards()[0]); return [calls, swAck]; })()")   # ITEM has a default about to be taken
        self.assertEqual(stays[0], [])
        self.assertIn("Stays here: the default is taken at", stays[1])
        stale = self.x("ITEM.left_s = null; ITEM.stay = ''; api.fail = 'unknown item'; (async () => { await swDo('later', swCards()[0]); return swAck; })()")
        self.assertIn("changed", stale)

    def test_bring_back_seen_orders_and_the_bar_controls(self):
        got = self.x("(async () => { await swBring('z'); await swSeen(); swEditing = true; await swOrdersSave('a\\nb'); await swControl('pause'); await swControl('resume'); await swControl('sort'); return [calls, swEditing]; })()")
        self.assertEqual(got, [[["/api/super", {"action": "bring_back", "keys": ["z"]}], ["/api/super", {"action": "seen"}],
                                ["/api/super", {"action": "orders", "text": "a\nb"}], ["/api/super", {"action": "pause"}],
                                ["/api/super", {"action": "resume"}], ["/api/super", {"action": "sort"}]], False])
        bar = self.x("swBar()")
        for want in ("11</b> sorts", "$0.06</b> today", 'data-sw="pause"', 'data-sw="sort"', "Sort now"):
            self.assertIn(want, bar)
        paused = self.x("superView.controls = {pause: null, resume: {label: 'Resume', off: ''}, sort: {label: 'Sort now', off: 'Resume first'}}; swBar()")
        self.assertIn('data-sw="resume"', paused)
        self.assertRegex(paused, r'data-sw="sort"[^>]*disabled[^>]*title="Resume first"')

    def test_batch_posts_each_members_own_action_in_order_and_reports_a_refusal(self):
        batch = ("const mem = (k, t) => Object.assign({}, ITEM, {key: k, id: t, title: t, kind: 'accept', left_s: null, acts: {state: 'done', line: '', hint: '', message: null, bar: [], menu: [],"
                 " primary: [{id: 'accept', label: 'Accept', post: '/api/task/accept', body: {task: t}, off: '', confirm: false}]}}); "
                 "superView.queue = [{batch: 'acc', rank: 1, answer: {id: 'accept', label: 'Accept'}, items: [mem('a', 'ta'), mem('b', 'tb'), mem('c', 'tc')]}]; ")
        ok = self.x(batch + "(async () => { await swBatchRun('a|b|c'); return [calls.map((c) => c[1].task), swAck]; })()")
        self.assertEqual(ok, [["ta", "tb", "tc"], "Accept: sent to 3 tasks."])
        part = self.x(batch + "api = async (p, b) => { calls.push([p, b]); if (b.task === 'tb') throw new Error('a step is running'); return {}; };"
                      " (async () => { await swBatchRun('a|b|c'); return [calls.map((c) => c[1].task), swAck, Object.keys(swSent)]; })()")
        self.assertEqual(part[0], ["ta", "tb", "tc"])
        self.assertEqual(part[1], "Accept 2 of 3. tb: a step is running")
        self.assertEqual(sorted(part[2]), ["a", "c"])
        none = self.x(batch + "superView.queue[0].answer = null; (async () => { await swBatchRun('a|b|c'); return calls; })()")
        self.assertEqual(none, [])
        split = self.x(batch + "swClick = () => {}; swAct({dataset: {sw: 'split', key: 'a|b|c'}}); [swCards().length, [...swSplit]]")
        self.assertEqual(split, [3, ["a|b|c"]])

    def test_target_chip_follows_the_selection(self):
        t = lambda pre: self.x(pre + "(() => { const g = swTarget(); return [g.kind, g.chip, g.off]; })()")
        pre = "projectName = (d) => d.split('\\\\').pop(); project = 'D:\\\\last'; swSel = ''; swProj = ''; swAnswerTo = ''; "
        self.assertEqual(t(pre), ["new", "New work · last", False])
        self.assertEqual(t(pre + "swSel = 'p'; swProj = 'D:\\\\other'; "), ["new", "New work · other", False])
        self.assertEqual(t(pre + "swSel = 'sa'; "), ["sa", "◆ Super agent", False])
        self.assertEqual(t(pre + "swSel = 'sa'; superView.mode = 'off'; "), ["sa", "◆ Super agent", True])
        self.assertEqual(t(pre + "swAnswerTo = 'k1'; "), ["answer", "Answer · Paths and settings", False])
        self.assertEqual(t(pre + "swAnswerTo = 'k1'; ITEM.own.off = 'Supervisor off.'; "), ["answer", "Answer · Paths and settings", True])
        self.assertEqual(t(pre + "project = ''; "), ["new", "New work · no project", True])

    def test_send_goes_where_the_chip_says(self):
        box = "document = {getElementById: (id) => id === 'sw-in' ? inp : id === 'c-prompt' ? comp : {focus() {}}}; const inp = {value: 'hello'}, comp = {value: ''}; "
        # New work: the composer's own Prep
        new = self.x(box + "projectName = (d) => d; project = 'D:\\\\p'; swSel = ''; doPrep = () => calls.push(['prep', comp.value]); (async () => { await swSend(); return [calls, inp.value]; })()")
        self.assertEqual(new, [[["prep", "hello"]], ""])
        sa = self.x(box + "swSel = 'sa'; api.ret = Object.assign({}, superView, {kept: false}); (async () => { await swSend(); return [calls, inp.value]; })()")
        self.assertEqual(sa, [[["/api/super", {"action": "message", "text": "hello"}]], ""])
        answer = self.x(box + "swAnswerTo = 'k1'; crypto = {randomUUID: () => 'uuid-1'}; (async () => { await swSend(); return [calls, swAnswerTo, !!swSent.k1]; })()")
        self.assertEqual(answer, [[["/api/task/message", {"task": "t1", "target": {"step": 3}, "text": "hello", "mode": "answer", "request_id": "uuid-1"}]], "", True])
        off = self.x(box + "swSel = 'sa'; superView.mode = 'capped'; (async () => { await swSend(); return calls; })()")
        self.assertEqual(off, [])
        empty = self.x(box + "inp.value = '  '; (async () => { await swSend(); return calls; })()")
        self.assertEqual(empty, [])

    def test_a_session_answer_goes_through_continue_without_a_request_id(self):
        got = self.x("const box = {value: 'yes'}; document = {getElementById: () => box}; ITEM.type = 'session'; ITEM.id = 's5'; ITEM.kind = 'stop';"
                     " ITEM.own = {mode: 'answer', post: '/api/continue', off: '', body: {session: 's5'}, request_id: false}; swAnswerTo = 'k1'; (async () => { await swSend(); return calls; })()")
        self.assertEqual(got, [["/api/continue", {"session": "s5", "text": "yes"}]])

    def test_the_super_agent_code_names_no_task_route(self):
        src = APP.read_text(encoding="utf-8")
        block = src[src.index("// -- plan 59: the super agent window"):src.index("// -- end plan 59")]
        for forbidden in ("/api/task/", "/api/continue", "/api/terminal", "/api/done", "/api/stop", "levers.", "lv."):
            self.assertNotIn(forbidden, block, forbidden)
        self.assertIn('"/api/super"', block)
```

## 6.2 Code (`web/app.js`)

Append to Task 5's block. The whole plan 59 code stays one contiguous region from `// -- plan 59: the super agent window`
(Task 4's first comment) to a last line `// -- end plan 59`, which this task adds after `swSend`; the route test above reads
that region. Replace Task 5's stub `function swDo(what, card) {}` by the `swDo` below.

```js
// -- plan 59 Task 6: answers, Later, batch, the bar and the one box -----------------------------------------------------
let swErr = {};          // key -> the refusal of the last click on that card (the service's words)
let swPending = null;    // {tid, aid}: a served form to open once the task page has its data (Retry, Hand off, Reopen, Start next)
let swSentLine = "";     // the line under the page after a message to the super agent or an answer from the box
const swItem = (key) => { for (const c of swCards()) for (const i of c.items) if (i.key === key) return i; return (superView.later || []).find((e) => e.key === key) || null; };
const swCardOf = (key) => swCards().find((c) => swKey(c) === key || c.items.some((i) => i.key === key)) || null;
const swSay = (text) => { swAck = ""; swSentLine = text; renderBoard(); };
function swOpen(it) {  // Open: the task (at the failed step for a stuck card), or Console's read-only page of a chat
  swSel = "";
  if (it.open.kind === "session") { openSession(it.open.id); return; }
  openTask(it.open.id);
  if (["failed_twice", "stuck"].includes(it.kind) && it.open.step) { boardPick = "s" + it.open.step; renderBoard(); }
}
async function swRunAct(button) {  // the one click path of a card's served action: confirm twice, open its form, or post as served
  const it = swItem(button.dataset.key);
  if (!it || !it.acts) return;
  const a = [...it.acts.primary, ...it.acts.bar, ...it.acts.menu].find((x) => x.id === button.dataset.aid);
  if (!a || a.off) return;
  if (a.confirm && !button.dataset.armed) { armBtn(button, (typeof ARM !== "undefined" && ARM[a.id]) || `${actLabel(a, it.acts.state)}? Click again`); return; }
  if (!a.post) { swPending = { tid: it.open.id, aid: a.id }; swOpen(Object.assign({}, it, { kind: "" })); return; }  // a form: the task opens, its own form follows
  delete swErr[it.key];
  try {
    await api(a.post, a.body);
    swSent[it.key] = Date.now();
    swAck = `${actLabel(a, it.acts.state)}: sent to ${it.title}.`;
    await swFetch(true);
  } catch (e) { delete swSent[it.key]; swErr[it.key] = e.message; renderBoard(); }
}
async function swBatchRun(keyStr) {  // each member's own served action, one request each, through its own gate
  const card = swCardOf(keyStr);
  if (!card || !card.answer) return;
  const done = [], failed = [];
  for (const it of card.items) {
    const a = it.acts.primary.find((x) => x.id === card.answer.id);
    if (!a || a.off) { failed.push([it, a ? a.off : "no longer offered"]); continue; }
    try { await api(a.post, a.body); done.push(it); swSent[it.key] = Date.now(); } catch (e) { failed.push([it, e.message]); }
  }
  swAck = failed.length ? `${card.answer.label} ${done.length} of ${card.items.length}. ${failed.map(([i, r]) => `${i.title}: ${r}`).join("; ")}`
    : `${card.answer.label}: sent to ${done.length} tasks.`;
  await swFetch(true);
}
async function swLaterRun(card) {
  const keys = card.items.map((i) => i.key);
  try {
    const r = await api("/api/super", { action: "later", keys });
    swAck = `${card.items.map((i) => i.title).join(" and ")}: in Later, back at ${swUntil((r.later.find((e) => keys.includes(e.key)) || r.later[0] || {}).until)}.`;
    superView = r;
    swWant = swReady() ? snap.super.rev : swWant;
  } catch (e) { swAck = /unknown item/.test(e.message) ? "That changed while you looked: the queue is updated." : e.message; }
  await swFetch(true);
  const c = document.querySelector("#bwrap .sw-qc.cur"); if (c) c.focus();
}
async function swBring(key) { try { superView = await api("/api/super", { action: "bring_back", keys: [key] }); swAck = "Back in For you."; } catch (e) { swAck = e.message; } await swFetch(true); }
async function swSeen() { try { superView = await api("/api/super", { action: "seen" }); swAck = ""; } catch (e) { swAck = e.message; } renderBoard(); }
async function swOrdersSave(text) { try { superView = await api("/api/super", { action: "orders", text }); swEditing = false; } catch (e) { swAck = e.message; } renderBoard(); }
async function swControl(name) { try { superView = await api("/api/super", { action: name }); swAck = ""; } catch (e) { swAck = e.message; } await swFetch(true); }
function swDo(what, card) {  // the keys and the links: later, open, confirm
  if (!card) return;
  const it = card.items[0];
  if (what === "open") swOpen(it);
  else if (what === "confirm") { const b = document.querySelector("#bwrap .sw-qc.cur .btn.you"); if (b && !b.disabled) b.click(); }
  else if (what === "later") {
    const stay = card.items.length === 1 ? swStay(it) : "";
    if (stay) { swAck = `Stays here: ${stay}.`; renderBoard(); return Promise.resolve(); }
    return swLaterRun(card);
  }
}
function swDisarm() { const b = document.querySelector("[data-armed]"); if (b) { delete b.dataset.armed; if (b.dataset.label) b.innerHTML = b.dataset.label; } }
function swAct(t) {  // the delegated click of everything data-sw
  const d = t.dataset;
  switch (d.sw) {
    case "row": case "proj": case "more": return swClick(t);
    case "cur": case "card": swCur = +d.i; swAnswerTo = ""; renderBoard(); const c = document.querySelector("#bwrap .sw-qc.cur"); if (c) c.focus(); return;
    case "pick": swPick[d.key] = d.aid; renderBoard(); return;
    case "act": return swRunAct(t);
    case "open": { const it = swItem(d.key); if (it) swOpen(it); return; }
    case "openid": { const it = swItem(d.key); if (it) swOpen(it); return; }
    case "later": { const card = swCardOf(d.key); return card && swDo("later", card); }
    case "words": swAnswerTo = d.key; renderBoard(); { const i = $("sw-in"); if (i) i.focus(); } return;
    case "split": swSplit.add(d.key); swCur = Math.max(0, swCards().findIndex((c) => c.items.some((i) => i.key === d.key.split("|")[0]))); renderBoard(); return;
    case "batch": return swBatchRun(d.key);
    case "bring": return swBring(d.key);
    case "seen": return swSeen();
    case "oedit": swEditing = true; renderBoard(); { const o = $("ordersin"); if (o) o.focus(); } return;
    case "ocancel": swEditing = false; renderBoard(); return;
    case "osave": return swOrdersSave($("ordersin").value);
    case "pause": case "resume": case "sort": return swControl(d.sw);
    case "settings": mtab = "tuning"; showPage("models"); return;
    case "send": return swSend();
    case "tgx": swAnswerTo = ""; renderBoard(); return;
  }
}
function swTarget() {  // SW-13 and README 4.8: where Enter goes. Code routes, no model.
  if (swAnswerTo) {
    const it = swItem(swAnswerTo);
    if (it && it.own) return { kind: "answer", cls: "an", chip: "Answer · " + it.title, ph: "Your answer to: " + it.ask, own: it.own, key: it.key, off: !!it.own.off };
    swAnswerTo = "";
  }
  if (swSel === "sa") { const off = ["off", "capped", "error"].includes(superView.mode); return { kind: "sa", cls: "sa", chip: "◆ Super agent", ph: off ? "Not sorting today" : "Ask or tell the super agent", off }; }
  const dir = swSel === "p" ? swProj : project;
  return { kind: "new", cls: "", chip: "New work · " + (dir ? projectName(dir) : "no project"), ph: "Describe the new work", off: !dir };
}
function swBox() {
  const t = swTarget(), v = t.kind === "new" ? draft : "";
  return `<div class="sw-steer"><span class="sw-tgt ${t.cls}" id="sw-tgt" title="Where Enter goes: ${esc(t.chip)}"><span class="sr">Enter goes to: </span><span class="tn">${esc(t.chip)}</span>${t.kind === "answer" ? '<button class="sw-tgx" data-sw="tgx" aria-label="Cancel the answer" title="Cancel (Esc)">✕</button>' : ""}</span>
    <input id="sw-in" autocomplete="off" aria-label="Message to ${esc(t.chip)}" placeholder="${esc(t.ph)}" value="${esc(v)}"${t.off ? " disabled" : ""}><button class="btn" data-sw="send" id="sw-send"${t.off ? " disabled" : ""}>Send</button></div>`;
}
function swBar() {  // SW-14: the figures, then Pause or Resume, then Sort; every word and every off reason is served
  const c = superView.controls, sp = superView.spend || {};
  const b = (a, id, cls) => (a ? `<button class="btn${cls}" data-sw="${id}"${a.off ? ` disabled title="${esc(a.off)}"` : ' title="Sort what needs you now"'}>${esc(a.label)}</button>` : "");
  return `<span class="p-use"><b>${sp.passes || 0}</b> sorts<span class="dv"></span><b>${swMoney(sp.today)}</b> today</span><span class="sp"></span>`
    + b(c.pause, "pause", " ghost") + b(c.resume, "resume", " go") + b(c.sort, "sort", "");
}
async function swSend() {
  const t = swTarget(), inp = $("sw-in"), text = inp ? inp.value.trim() : "";
  if (!text || t.off) return;
  if (t.kind === "new") { $("c-prompt").value = text; draft = text; inp.value = ""; doPrep(); return; }   // the composer's own Prep: files, effort, draft stay there
  if (t.kind === "sa") {
    try { const r = await api("/api/super", { action: "message", text }); inp.value = ""; superView = r;
      swSentLine = r.kept ? "Kept: the super agent reads it at the next sort." : "Sent to the super agent: it sorts with your message."; }
    catch (e) { swSentLine = e.message; }
    renderBoard(); return;
  }
  const own = t.own, body = { ...own.body, text };
  if (own.request_id) { body.mode = own.mode; body.request_id = crypto.randomUUID(); }
  try { await api(own.post, body); inp.value = ""; swSent[t.key] = Date.now(); swAck = `Your own answer: sent to ${(swItem(t.key) || {}).title}.`; swAnswerTo = ""; await swFetch(true); }
  catch (e) { swSentLine = e.message; renderBoard(); }
}
// -- end plan 59
```

Anchored edits:

- Task 5's `renderBoard` wiring line becomes
  `if (swHome() && superView) setHtml($("bwrap"), \`<div class="idock sw-shell" data-p="super"><div class="iscroll">${swPage()}</div><p class="sw-sent" role="status">${esc(swSentLine)}</p>${swBox()}<div class="p-bar">${swBar()}</div></div>\`);`
  and, when `swHome()` and no view yet, `<p class="note m">Reading the super agent.</p>` (`swFetch()` runs from `renderBoard`).
- `renderBoard()` after the task page is drawn: `if (swPending && boardData && boardData.id === swPending.tid) { const a = actFind(boardData.data, swPending.aid); swPending = null; if (a && !a.off) openActionForm(a, null, boardData.data); }`
- Task 4's click line `else if (t.dataset.sw) swClick(t);` becomes `else if (t.dataset.sw) swAct(t);` and the selector gains nothing (it already lists `[data-sw]`).
- `swCard` (Task 5): after the `sent` foot add `if (swErr[it.key]) body += \`<div class="sw-foot r" role="alert">${esc(swErr[it.key])}</div>\`;`.
- The keydown listener of `#sw-in`: in the existing `document.addEventListener("keydown"` handler next to the `id === "c-prompt"` branch, add
  `if (id === "sw-in") { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); return swSend(); } if (e.key === "Escape") { e.preventDefault(); if (swAnswerTo) { swAnswerTo = ""; renderBoard(); } else e.target.blur(); return; } }`
  and the `input` handler: `if (e.target.id === "sw-in" && swTarget().kind === "new") { draft = e.target.value; $("c-prompt").value = draft; draftKept = false; saveDraft(); renderCompose(); }` (one draft, two views of it, D11 a).
- `swKeys` (Task 5) begins with `swDisarm();` so any key disarms a two-click button.
- Plan 55's box (`stepFooter`) gains the chip: a `<span class="sw-tgt">Task · ${esc(t.title)}</span>` before the textarea
  (test: `stepFooter` markup contains `Task · <title>`); the observed page's chip is `Read only · ${swApp(source)} chat`
  with the input off (plan 55 Task 6 draws that page and calls `swObservedChip(s)`, defined here:
  `const swObservedChip = (s) => \`Read only · ${swApp(s.source)} chat\`;`).
- `go("needs")` (Task 4) and the click on the row set `swCur = 0`.

## 6.3 Style (`web/style.css`)

Port, with the `sw-` prefix and the mock's declarations: `.steer` (as `.sw-steer`), `.tgt .tn .tgt.sa .tgt.an .tgt.ro` (as
`.sw-tgt`), `.tgx` (as `.sw-tgx`), `.sent` (as `.sw-sent`), `.foot` (as `.sw-foot`, plus `.sw-foot.r { color: var(--bad); }`),
`.btn.sm` is the app's. The chip uses the app's `--ink`, `--mut`, `--you`: orange only on `.sw-tgt.an` (the answer chip,
"for you") as the mock draws it. The bar reuses plan 55's `.p-bar`, `.p-use`, `.sp`. Floors: 24 px targets (`.sw-tgx`,
the chip) and 11 px text.

## 6.4 Steps and acceptance

- [ ] 1. Write `SuperActTest` and extend `tests/live_super_check.py` (click Later and Bring back against a scratch service,
      answer a plan-ready card and a decision; the page, the header and the project line all read the same number after).
- [ ] 2. Make the 6.2 and 6.3 edits. `node --check web/app.js`; `py -m unittest tests.test_web`; `py -m tests.live_super_check`.
- [ ] 3. Full suite green (report the count). Stage the test files and only this task's hunks of `web/app.js` and
      `web/style.css`. Commit with the message above.
