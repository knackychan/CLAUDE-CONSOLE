"""web/app.js rendering, run in Node against stubs of the browser (skipped where Node is not installed)."""
import json
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "web" / "app.js"
NODE = shutil.which("node")
# app.js is a browser script: every browser global is a proxy that absorbs any use, then the expression's value prints
HARNESS = """
const fs = require("fs"), vm = require("vm");
const any = () => new Proxy(function () {}, { get: (t, k) => (k === Symbol.toPrimitive ? () => "" : k === "then" ? undefined : any()),
  apply: () => any(), construct: () => any() });
const ctx = vm.createContext({ document: any(), window: any(), navigator: any(), localStorage: any(), location: any(),
  matchMedia: any(), fetch: () => new Promise(() => {}), setInterval: () => 0, setTimeout: () => 0, clearTimeout() {},
  clearInterval() {}, requestAnimationFrame: () => 0, addEventListener() {}, ResizeObserver: any(),
  MutationObserver: any(), EventSource: any() });
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
Promise.resolve(vm.runInContext(process.argv[2], ctx)).then(value => process.stdout.write(JSON.stringify(value)))
  .catch(error => { console.error(error); process.exitCode = 1; });
"""


def render(expr):
    out = subprocess.run([NODE, "-e", HARNESS, str(APP), expr], capture_output=True, text=True, encoding="utf-8",
                         timeout=30)
    if out.returncode:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


class Turns(HTMLParser):  # each chat turn's class and the data-text of the copy buttons inside it
    def __init__(self):
        super().__init__()
        self.turns, self.depth = [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.depth:
            self.depth += tag == "div"
        elif tag == "div" and "turn" in (a.get("class") or "").split():
            self.turns.append([a["class"], []])
            self.depth = 1
        if self.depth and "data-turncopy" in a:
            self.turns[-1][1].append(a.get("data-text"))

    def handle_endtag(self, tag):
        if self.depth and tag == "div":
            self.depth -= 1


@unittest.skipUnless(NODE, "Node is not installed")
class ChatCopyTest(unittest.TestCase):
    def test_copy_reports_success_only_when_clipboard_accepts_text(self):
        for mode in ("native", "fallback", "denied", "throws"):
            with self.subTest(mode=mode):
                result = render("""(async () => {
                  const mode = %s;
                  let copied = null, removed = false, done = false;
                  navigator = {clipboard: {writeText: async text => {
                    if (mode !== 'native') throw Error('denied');
                    copied = text;
                  }}};
                  const field = {select() {}, remove() {removed = true;}};
                  document = {createElement: () => field, body: {appendChild() {}}, execCommand: () => {
                    if (mode === 'throws') throw Error('denied');
                    if (mode === 'fallback') {copied = field.value; return true;}
                    return false;
                  }};
                  const button = {dataset: {text: 'line one\\n<two>'}, classList: {
                    toggle(name, on) {done = on;}, add() {done = true;}, remove() {done = false;}
                  }};
                  await copyTurn(button);
                  return {text: button.textContent, copied, removed, done};
                })()""" % json.dumps(mode))
                success = mode in ("native", "fallback")
                self.assertEqual(result, {"text": "copied" if success else "copy failed",
                                          "copied": "line one\n<two>" if success else None,
                                          "removed": mode != "native", "done": success})

    def test_open_session_keeps_board_visible_and_uses_right_pane(self):
        result = render("""(async () => {
          const pages = ['board', 'session', 'usage', 'models'].map(page => ({dataset: {page}, hidden: true}));
          document = {querySelectorAll: () => pages, getElementById: () => ({})};
          closePicker = () => {}; render = () => {};
          snap = {sessions: [{id: 's', title: 'Working chat'}]};
          form = 'open';
          await openSession('s');
          const visible = pages.filter(p => !p.hidden).map(p => p.dataset.page);
          let rendered = false;
          renderSession = () => {rendered = true;};
          document.querySelector = () => pages[1];
          await renderInspector(null);
          showPage('board');
          return {visible, rendered, after: pages.filter(p => !p.hidden).map(p => p.dataset.page)};
        })()""")
        self.assertEqual(result, {"visible": ["board", "session"], "rendered": True, "after": ["board"]})
        html = APP.with_name("index.html").read_text(encoding="utf-8")
        right = html.index('<div class="v-right">')
        session = html.index('<section data-page="session"')
        inspector = html.index('<div id="bwrap"')
        self.assertLess(right, session)
        self.assertLess(session, inspector)

    def test_standalone_chat_is_one_row_that_opens_its_page(self):
        setup = """snap = {now: 100}; page = 'board'; openId = '';
          s = {id: 's', title: 'Fix the run', state: 'replied', group: 'replied', last_ts: 40,
               symbol: 'R', project: 'Console', model: 'sonnet', harness: 'claude', text: 'Replied',
               effort: 'medium', spent: 1, spent_exact: true, ctx_tokens: 0, prep: ''}; """
        html = render(setup + "sessionRow(s)")
        self.assertEqual(html.count('data-open="s"'), 1)
        self.assertNotIn("data-sview", html)  # no prep or chat sub-rows in the list
        self.assertNotIn('class="v-sr', html)
        self.assertIn("replied · 1m", html)
        # Fred 2026-10-20: a chat from outside the Console is marked with where it runs
        for src, harness, chip in (("vscode", "claude", "VS Code"), ("terminal", "claude", "terminal"), ("?", "codex", "codex")):
            out = render(setup + f"s.source = '{src}'; s.harness = '{harness}'; sessionRow(s)")
            self.assertIn('class="v-tk out"', out)
            self.assertIn(f'<span class="v-src">{chip}</span>', out)
        own = render(setup + "s.source = 'window'; sessionRow(s)")
        self.assertNotIn("v-src", own)
        self.assertNotIn(" out", own)
        idle = render(setup + "s.group = 'working'; s.state = 'idle'; sessionLine(s)")
        self.assertEqual(idle, ["idle", ""])
        busy = render(setup + "s.group = 'working'; s.state = 'running'; s.route = 'auto'; sessionLine(s)")
        self.assertTrue(busy[0].startswith("running · "))

    def test_board_chat_shows_the_answer_prompt_for_a_question(self):
        setup = "snap = {sessions: [{id: 's', state: 'stop', run_live: false, stop_question: 'Shall I fix it?'}], tasks: []}; boardChat = {sid: 's', chat: {items: [], source: 'window'}};"
        html = render(setup + "stepFooter({id: 't', chat: true, state: 'running'}, {n: 1, session: 's', state: 'running'}, {step_levers: {continue: ''}})")
        self.assertIn("Shall I fix it?", html)
        self.assertIn('data-tact="answer"', html)
        self.assertIn("Send answer", html)

    def test_every_chat_message_has_a_copy_button_with_its_text(self):
        chat = {"items": [
            {"role": "you", "text": "the prompt the service built"},
            {"role": "claude", "text": "line one\nline <two> & \"three\""},
            {"role": "tool", "text": "Bash · ls"},
            {"role": "you", "text": "a follow-up"},
            {"role": "claude", "text": "words\nHANDOFF\n## Next\nstep 3\nEND HANDOFF"},
            {"role": "note", "text": "stopped"}]}
        for opts in ({}, {"prompt": True, "step": {"n": 2}}, {"prompt": True, "step": {"n": 2}, "compact": True, "board": True}):
            with self.subTest(opts=opts):
                p = Turns()
                p.feed(render(f"chatPane({json.dumps(chat)}, 's1', 'chat', {json.dumps(opts)})"))
                texts = [i["text"] for i in chat["items"] if i["role"] in ("you", "claude")]
                self.assertEqual([t[1] for t in p.turns], [[t] for t in texts])


@unittest.skipUnless(NODE, "Node is not installed")
class ModelUsageTest(unittest.TestCase):
    def test_bars_show_token_load_and_unused_models_without_allowances(self):
        def model(n):
            return {"share": None, "unknown_runs": 0, "via": ["claude"],
                    **{w: {"used_tokens": n, "used_usd": 0, "allowance_usd": None} for w in ("day", "week", "month")}}
        data = {"fills": {"opus": model(9000), "gpt-6-astra": model(0), "sonnet": model(1000),
                           "unknown-model": model(None)}, "warn_at": 0.8}
        html = render(f"usageFills({json.dumps(data)})")
        self.assertIn("Models · tracked usage", html)
        self.assertIn("gpt-6-astra", html)
        self.assertIn("90 % of today", html)
        self.assertIn("Token usage unavailable", html)
        self.assertIn("<b>?</b>", html)
        self.assertIn('class="f"', html)
        self.assertNotIn("no allowance</span>", html)

    def test_configured_allowance_still_shows_pace(self):
        window = {"used_usd": 5, "allowance_usd": 10, "pace_usd": 6, "share": 0.84, "used_tokens": 9000}
        data = {"fills": {"opus": {"share": 0.84, "binding": "day", "via": ["claude"],
                                    **{w: window for w in ("day", "week", "month")}}}, "warn_at": 0.8}
        html = render(f"usageFills({json.dumps(data)})")
        self.assertIn('data-fill="opus"', html)
        self.assertIn("84 %", html)
        self.assertIn('class="y"', html)


@unittest.skipUnless(NODE, "Node is not installed")
class FoldTest(unittest.TestCase):  # plan 38 U11: a fold head reads as a control, never as a static .lbl caption
    def test_fold_head_has_a_caret_first_and_its_own_label(self):
        html = render('fold("prompt.md", "", "<pre>goal</pre>")')
        self.assertIn('<button class="fh" data-fold aria-expanded="false"><span class="car" aria-hidden="true">▸</span>'
                      '<span class="fl">prompt.md</span>', html)
        self.assertNotIn('class="lbl"', html)


class NextStepUITest(unittest.TestCase):
    """Plan 36 Task 3: the Add next step footer and inline form (web/app.js)."""

    def _setup(self, snap=None, view=None):
        s = "snap = " + json.dumps(snap or {"sessions": [], "tasks": [], "versions": {}, "projects": []}) + "; "
        s += "nextDraft = {}; "
        s += ("nextOpen = null; nextView = " + json.dumps(view) + "; ") if view is not None \
            else "nextOpen = null; nextView = null; "
        return s

    def test_key_binds_the_draft_to_task_and_source_step(self):
        self.assertEqual(render("nextKey({id: 't1'}, {n: 2, session: 's9'})"), "t1|2|s9")

    def test_task_of_session_finds_the_task_for_a_step(self):
        task = {"id": "t", "steps": [{"n": 1, "session": "s"}]}
        snap = {"tasks": [task], "sessions": [], "versions": {}, "projects": []}
        self.assertEqual(render(self._setup(snap=snap) + "taskOfSession('s')"), task)
        self.assertIsNone(render(self._setup(snap=snap) + "taskOfSession('other')"))

    def test_verify_seeds_a_concrete_default(self):
        text = render("nextInstr({steps: []}, {}, {n: 1}, 'verify', null)")
        self.assertIn("VERDICT: PASS or FAIL", text)
        self.assertIn("Do not edit files", text)

    def test_instructions_seed_from_the_previous_next_section(self):
        notes = json.dumps({"1": "HANDOFF\n## Next\nwrite the tests first\nEND HANDOFF"})
        out = render(f"nextSeed({{steps: [{{n: 1}}]}}, {{notes: {notes}}}, {{n: 1}})")
        self.assertEqual(out, "write the tests first")

    def test_a_none_next_section_seeds_blank(self):
        notes = json.dumps({"1": "HANDOFF\n## Next\n(none)\nEND HANDOFF"})
        self.assertEqual(render(f"nextSeed({{steps: [{{n: 1}}]}}, {{notes: {notes}}}, {{n: 1}})"), "")

    def test_draft_is_keyed_and_seeded_once(self):
        out = render(self._setup() + "(() => { const d = nextDraftFor({id: 't', steps: [{n: 1, session: 's'}]}, {}, "
                      "{n: 1, session: 's'}); return {key: nextKey({id: 't'}, {n: 1, session: 's'}), "
                      "draft: d, same: nextDraftFor({id: 't', steps: [{n: 1, session: 's'}]}, {}, "
                      "{n: 1, session: 's'}) === d}; })()")
        self.assertEqual(out, {"key": "t|1|s", "draft": {"kind": "code", "model": "auto", "instr": "", "hi": False},
                               "same": True})

    def test_form_shows_source_work_model_instructions_and_handover(self):
        view = {"key": "t|1|s", "busy": False, "revision": "r",
                "text": "HANDOFF\n## Goal\ngoal\n## Next\nnext\nEND HANDOFF", "fallback": False,
                "route": {"rung": "opus", "model": "opus", "effort": "high", "notes": []},
                "models": [{"rung": "auto", "why": ""}, {"rung": "opus", "why": ""}]}
        html = render(self._setup(view=view) +
                      "nextFormHtml({id: 't', project_dir: 'C:/repo/CONTENT MANAGER', steps: [{n: 1, session: 's', kind: 'chat'}]}, "
                      "{n: 1, session: 's', kind: 'chat'}, null, {})")
        for text in ('id="b-nwork"', 'id="b-nmodel"', 'id="b-ninstr"', 'data-tact="nextstart"',
                     'data-tact="nextcancel"', "From 01 chat", "Same project: CONTENT MANAGER",
                     "Resolved", "Handover from step 01"):
            self.assertIn(text, html)
        for kind in ("Code", "Verify", "Investigate", "Plan", "Chat"):
            self.assertIn(kind, html)

    def test_model_options_disable_unavailable_with_a_reason(self):
        models = [{"rung": "auto", "why": ""}, {"rung": "opus", "why": ""},
                  {"rung": "codex:gpt-6-astra", "why": "harness off"}]
        html = render(self._setup() + "nextModelOptions({model: 'auto'}, {models: " + json.dumps(models) + "})")
        self.assertEqual(html.count('value="auto"'), 1)
        self.assertIn("disabled", html)
        self.assertIn("harness off", html)
        self.assertIn("gpt-6-astra", html)

    def test_resolved_route_and_the_same_model_caveat(self):
        self.assertIn("Resolved", render(self._setup() +
                      "routeLine({busy: false, route: {rung: 'opus', model: 'opus', effort: 'high', notes: []}})"))
        self.assertIn("fresh session on the same model", render(self._setup() +
                      "routeLine({busy: false, route: {rung: 'opus', model: 'opus', effort: 'high', "
                      "notes: ['fresh session, same model']}})"))
        self.assertIn("Checking model", render(self._setup() + "routeLine({busy: true})"))
        self.assertIn("off", render(self._setup() + "routeLine({busy: false, error: 'off'})"))

    def test_add_step_only_where_the_service_allows_it(self):
        enabled = render(self._setup() + "nextActions({id: 't', current: 1}, {n: 1, session: 's', state: 'done'}, {levers: {add_next: ''}})")
        self.assertIn('data-tact="nextopen"', enabled)
        self.assertIn("Add step", enabled)
        self.assertNotIn("Verify", enabled)
        self.assertNotIn("Finish task", enabled)
        off = render(self._setup() + "nextActions({id: 't', current: 1}, {n: 1, session: 's', state: 'done'}, {levers: {add_next: 'still working', done: ''}})")
        self.assertEqual(off, "")
        t = "{id: 't', current: 1, steps: [{n: 1, session: 's', state: 'done'}]}"
        menu = render(self._setup() + f"taskMenu({t}, {{levers: {{add_next: ''}}, next_step: {{source_step: 1}}}}, null)")
        self.assertIn('data-tact="nextopen" data-tid="t" data-n="1" data-at="task"', menu)  # plan 48: in the task menu
        self.assertIn("Add step on a model", menu)
        self.assertNotIn("nextopen", render(self._setup() + f"taskMenu({t}, {{levers: {{add_next: 'still working'}}}}, null)"))

    def test_replied_chat_footer_offers_send_and_the_task_action_area(self):
        snap = {"sessions": [{"id": "s", "state": "stop", "run_live": False}],
                "tasks": [], "versions": {}, "projects": []}
        html = render(self._setup(snap=snap) +
                      "stepFooter({id: 't', chat: true, state: 'running', current: 1, "
                      "steps: [{n: 1, session: 's', state: 'running', kind: 'chat'}]}, "
                      "{n: 1, session: 's', state: 'running', kind: 'chat'}, "
                      "{levers: {add_next: '', done: ''}, step_levers: {handoff: '', next: ''}}, null)")
        self.assertIn(">Send<", html)
        self.assertIn('data-tact="cont"', html)
        self.assertNotIn("Add step", html)  # the composer never duplicates the action area
        dock = render(self._setup(snap=snap) +
                      "stepButtons({id: 't', chat: true, state: 'running', current: 1, "
                      "steps: [{n: 1, session: 's', state: 'running', kind: 'chat'}]}, "
                      "{n: 1, session: 's', state: 'running', kind: 'chat'}, "
                      "{levers: {add_next: '', done: '', handoff: '', next: ''}}, null)")
        bar, menu = dock.split("<details", 1)
        self.assertNotIn("nextopen", bar)  # plan 48: Add step on a model and Finish task are in the task menu
        self.assertIn('data-tact="nextopen"', menu)
        self.assertIn("Finish task", menu)
        self.assertNotIn("Hand off", dock)  # the service did not allow the whole-task handoff here

    def test_step_dock_reads_the_task_action_area_where_the_service_allows_it(self):
        """Plan 48: the current step's dock is the task's bar (Stop prominent, Retry on a model and Accept step result
        in the menu); Stop is not offered on a chat whose turn is over, and the failed-step recovery only on the current step."""
        snap = {"sessions": [{"id": "s", "state": "stop", "run_live": False}], "tasks": [], "versions": {}, "projects": []}
        chat = "{id: 't', chat: true, state: 'running', current: 1, steps: [{n: 1, session: 'gone', state: 'running', kind: 'chat'}]}"
        stuck = render(self._setup(snap=snap) + f"stepButtons({chat}, {{n: 1, session: 'gone', state: 'running', kind: 'chat'}}, "
                       "{levers: {stop: '', stepdone: 'no stopped or stuck step'}}, null)")
        self.assertIn('data-tact="stop"', stuck)  # a chat step with no session row is writing as far as the service knows
        self.assertNotIn("Accept step result", stuck)
        replied = render(self._setup(snap=snap) + "stepButtons({id: 't', chat: true, state: 'running', current: 1, steps: [{n: 1, session: 's', state: 'running', kind: 'chat'}]}, "
                         "{n: 1, session: 's', state: 'running', kind: 'chat'}, {levers: {stop: ''}}, null)")
        self.assertNotIn('data-tact="stop"', replied)
        t = "{id: 't', state: 'stopped', current: 2, steps: [{n: 1, session: 's1', state: 'done', kind: 'scout'}, {n: 2, session: 's2', state: 'failed', kind: 'code'}]}"
        failed = render(self._setup() + f"stepButtons({t}, {{n: 2, session: 's2', state: 'failed', kind: 'code'}}, {{levers: {{retry: '', stepdone: ''}}}}, {{state: 'failed'}})")
        menu = failed.split("<details", 1)[1]
        self.assertIn('data-tact="retryopen" data-tid="t"', menu)
        self.assertIn('data-tact="stepdone" data-tid="t"', menu)
        self.assertIn("Accept step result", menu)
        old = render(self._setup() + f"stepButtons({t}, {{n: 1, session: 's1', state: 'done', kind: 'scout'}}, {{levers: {{retry: '', stepdone: ''}}}}, {{state: 'done'}})")
        self.assertNotIn("Accept step result", old)
        self.assertNotIn("retryopen", old)
        off = render(self._setup() + f"stepButtons({t}, {{n: 2, session: 's2', state: 'failed', kind: 'code'}}, {{levers: {{retry: 'task is stopped', stepdone: 'still working'}}}}, {{state: 'failed'}})")
        self.assertNotIn("Retry", off)
        self.assertNotIn("Accept step result", off)

    def test_task_actions_show_only_where_the_service_allows_it(self):
        """Plan 48: the task menu reads task_levers for Add step on a model, Finish task and Delete, step_levers for
        terminal, and handoff_available for Hand off task; no Verify, Continue or Escalate (D10)."""
        snap = {"sessions": [{"id": "s2", "state": "idle", "run_live": False}], "tasks": [], "versions": {}, "projects": []}
        t = "{id: 't', current: 2, steps: [{n: 1, session: 's1', state: 'done', kind: 'scout'}, {n: 2, session: 's2', state: 'running', kind: 'chat'}]}"
        html = render(self._setup(snap=snap) + f"taskButtons({t}, {{levers: {{add_next: '', done: '', clear: ''}}, "
                      "step_levers: {continue: '', terminal: '', escalate: ''}, next_step: {source_step: 2}, handoff_available: ''})")
        menu = html.split("<details", 1)[1]
        for text in ('data-tact="nextopen" data-tid="t" data-n="2"', 'data-tact="done"', 'data-tact="clear"',
                     'data-tact="handofftask"', 'data-tact="terminal"'):
            self.assertIn(text, menu)
        self.assertLess(menu.index("Finish task"), menu.index("Add step on a model"))
        for text in ("Verify", "Continue", "Mark done", "Mark step done", "escalate", "Use a stronger model"):
            self.assertNotIn(text, html)
        off = render(self._setup(snap=snap) + f"taskButtons({t}, {{levers: {{add_next: 'task is stuck', done: '', clear: 'task is stuck'}}, step_levers: {{}}}})")
        self.assertIn('data-tact="done"', off.split("<details", 1)[1])  # Finish task stays while allowed
        for text in ("Verify", "Continue", "Delete task", "Add step"):
            self.assertNotIn(text, off)

    def test_stuck_box_retry_form_lists_models_and_hides_a_limited_rung(self):
        """Plan 40 Task 3: the stuck box has a note, a Model select (auto first) and Retry; a limited rung is not listed."""
        cfg = {"models": ["opus", "sonnet"], "ladder": {"opus": ["opus", "opencode:opencode-go/kimi-k3"], "sonnet": ["sonnet"]},
               "tiers": {"think": [{"rung": "opus", "rank": "opus", "why": ""},
                                   {"rung": "opencode:opencode-go/kimi-k3", "rank": "opus", "why": "opencode:opencode-go: Go usage limit exceeded (5 hour), until 01:39"}],
                         "write": [{"rung": "sonnet", "rank": "sonnet", "why": ""}], "read": []}}
        html = render(f"cfg = {json.dumps(cfg)}; retryForm({{id: 't'}}, {{n: 1, kind: 'code', pick: 'opencode:opencode-go/kimi-k3'}}, 't')")
        for text in ('id="b-retrynote"', 'id="b-retrymodel"', 'data-tact="retry"', '<option value="" selected>auto</option>',
                     'value="opus"', 'value="sonnet"'):
            self.assertIn(text, html)
        self.assertNotIn("kimi-k3", html)
        stuck = (f"cfg = {json.dumps(cfg)}; " + TaskOverviewTest.setup + "t.state = 'stuck'; t.why = 'no HANDOFF block'; "
                 "t.steps[0].state = 'failed'; t.steps[0].kind = 'code'; row.state = 'stuck'; d.levers = {retry: ''}; ")
        box = render(stuck + "attentionArea(t, d, row)")
        self.assertIn("no HANDOFF block", box)
        self.assertNotIn("b-retrymodel", box)  # plan 48: the stuck box shows the reason; Retry on a model is in the menu
        self.assertIn('data-tact="retryopen"', render(stuck + "taskButtons(t, d)"))
        opened = render(stuck + "retryOpen = 't'; inspTask(t, d, row)")
        self.assertEqual(opened.count('id="b-retrymodel"'), 1)
        self.assertIn('data-tact="retrycancel"', opened)
        self.assertNotIn("b-retrymodel", render(stuck + "retryOpen = ''; inspTask(t, d, row)"))

    def test_tier_card_offers_clear_on_a_limited_rung(self):
        """Plan 45 D3: the hidden line and a limited hidden row carry a clear link with the limit's key."""
        cfg = {"models": ["opus"], "ladder": {}, "harnesses": {}, "efforts": ["high"],
               "tiers": {"think": [{"rung": "fable", "rank": "fable", "why": "fable: credits required, until 08:00", "limit": "fable"},
                                   {"rung": "opus", "rank": "opus", "why": "", "limit": ""}], "write": [], "read": []}}
        setup = (f"cfg = {json.dumps(cfg)}; medit = {{tiers: {{think: [{{rung: 'fable'}}, {{rung: 'opus'}}]}}}}; ")
        html = render(setup + "tierCard('think')")
        self.assertEqual(html.count('data-mclear="fable"'), 1)
        self.assertEqual(render(setup + "mqOpen.add('hthink'); tierCard('think')").count('data-mclear="fable"'), 2)

    def test_handed_box_offers_retry_when_the_service_allows_it(self):
        """Plan 40 Task 5: a handed task with no note and a failed step shows the retry form and the failed-run line."""
        cfg = {"models": ["opus"], "ladder": {"opus": ["opus"]}, "tiers": {"think": [], "write": [], "read": []}}
        call = (f"cfg = {json.dumps(cfg)}; handedBox({{levers: {{retry: ''}}, handoff: ''}}, {{id: 't', state: 'handed'}}, "
                "{n: 1, kind: 'scout', session: 's'}, 'handed')")
        html = render(call)
        self.assertIn("No handoff note: the step's run failed. Retry it on another model.", html)
        for text in ('id="b-retrynote"', 'id="b-retrymodel"', 'data-tact="retry"'):
            self.assertIn(text, html)
        off = render(call.replace("retry: ''", "retry: 'task is handed'"))
        self.assertIn("No handoff note: the handoff run did not finish.", off)
        self.assertNotIn("b-retrymodel", off)

    def test_hand_off_task_reads_the_task_availability(self):
        """Plan 44 nav T2/T3: Hand off task is gated by the task-level handoff_available, never the session levers."""
        html = render(self._setup() + "taskButtons({id: 't', steps: []}, {levers: {}, step_levers: {handoff: '', next: ''}, handoff_available: ''})")
        self.assertIn("Hand off task", html.split("<details", 1)[1])  # plan 48: in the task menu
        off = render(self._setup() + "taskButtons({id: 't', steps: []}, {levers: {}, step_levers: {handoff: '', next: ''}, handoff_available: 'still working'})")
        self.assertNotIn("Hand off task", off)
        self.assertNotIn("Start new task", off)

    def test_older_done_step_offers_a_branch_where_the_service_allows_it(self):
        """Plan 44 nav T2: the dock of an older step reads sources[NN]; the Board reproduces no rule of its own."""
        t = "{id: 't', current: 3, steps: [{n: 1, session: 's1', state: 'done'}, {n: 2, session: 's2', state: 'done'}, {n: 3, session: 's3', state: 'done'}]}"
        ok = render(self._setup() + f"nextActions({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{add_next: '', done: ''}}, sources: {{'01': '', '02': '', '03': ''}}}})")
        self.assertIn('class="btn sm go" data-tact="nextopen" data-tid="t" data-n="2"', ok)
        self.assertIn("Add step from here", ok)
        self.assertNotIn("Verify", ok)
        self.assertNotIn("Finish task", ok)  # the task's own actions stay on the task page and the latest step
        off = render(self._setup() + f"nextActions({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{add_next: ''}}, sources: {{'02': 'no saved note or final reply'}}}})")
        self.assertEqual(off, "")
        latest = render(self._setup() + f"nextActions({t}, {{n: 3, session: 's3', state: 'done'}}, {{levers: {{add_next: '', done: ''}}, sources: {{'03': ''}}}})")
        self.assertIn("Add step", latest)
        self.assertNotIn("Finish task", latest)
        dock = render(self._setup() + f"stepButtons({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{add_next: '', done: ''}}, sources: {{'02': ''}}}}, null)")
        self.assertIn('<details class="action-more" data-key="smenu">', dock)  # plan 48: the older step's menu
        self.assertIn("Add step from here", dock.split("<details", 1)[1])
        self.assertNotIn("Finish task", dock)
        self.assertEqual(render(self._setup() + f"stepButtons({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{add_next: ''}}, sources: {{'02': 'no note'}}}}, null)"), "")

    def test_form_from_an_older_step_names_it_and_the_steps_that_ran_since(self):
        """Plan 39 Task 3 (D4 a, D6 a): the source line, the shared-tree line and the Verify default name the source."""
        view = {"key": "t|2|s2", "busy": False, "revision": "r", "text": "HANDOFF\n## Goal\ngoal\nEND HANDOFF",
                "route": {"rung": "opus", "model": "opus", "effort": "high", "notes": []}, "models": []}
        t = ("{id: 't', project_dir: 'C:/repo/APP', current: 4, steps: [{n: 1, session: 's1', kind: 'scout'}, {n: 2, session: 's2', kind: 'code'}, "
             "{n: 3, session: 's3', kind: 'verify'}, {n: 4, session: 's4', kind: 'chat'}]}")
        html = render(self._setup(view=view) + f"nextOpen = {{tid: 't', key: 't|2|s2'}}; nextFormHtml({t}, {{n: 2, session: 's2', kind: 'code'}}, null, {{}})")
        self.assertIn("From 02 code", html)
        self.assertIn("Starts from step 02's handover on the project as it is now; steps 03 and 04 ran since.", html)
        one = render(self._setup(view=view) + f"sinceLine({t}, {{n: 3}})")
        self.assertIn("step 04 ran since", one)
        self.assertEqual(render(self._setup() + f"sinceLine({t}, {{n: 4}})"), "")
        self.assertTrue(render("verifyDefault(2)").startswith("Check step 02 against its goal, its tests and its unresolved risks"))
        self.assertIn("Do not edit files", render("nextInstr({steps: []}, {}, {n: 2}, 'verify', null)"))

    def test_the_form_is_bound_to_the_source_in_next_open_not_to_current(self):
        """Plan 39 Task 3: openNextForm, nextPreview, startNextStep and nextReseed resolve the source from nextOpen's key."""
        out = render(self._setup() + "(() => { const bd = {task: {id: 't', current: 3, steps: [{n: 2, session: 's2', kind: 'code'}, {n: 3, session: 's3', kind: 'verify'}]}}; "
                     "nextOpen = {tid: 't', key: 't|2|s2'}; const [t, s] = nextSource(bd); "
                     "nextOpen = {tid: 't', key: 't|2|other'}; const [, gone] = nextSource(bd); return [t && t.id, s && s.n, gone]; })()")
        self.assertEqual(out, ["t", 2, None])

    def test_chain_row_tags_a_branch_with_its_source(self):
        """Plan 39 Task 4: `from 02` on the row's second line when source_step is set and is not n - 1; no indentation."""
        t = ("{id: 't', current: 4, steps: [{n: 1, kind: 'scout', state: 'done', source_step: 0}, {n: 2, kind: 'code', state: 'done', source_step: 1}, "
             "{n: 3, kind: 'verify', state: 'done', source_step: 2}, {n: 4, kind: 'code', state: 'done', source_step: 2}]}")
        html = render(self._setup() + f"stepRows({t})")
        self.assertEqual(html.count("from 02"), 1)
        self.assertIn('<span class="n">04</span>', html)
        self.assertNotIn('class="v-subs"', html)  # a branch is a tag, never a nested list
        self.assertEqual(render(self._setup() + f"receivedNote({t}, {{n: 4, state: 'done', source_step: 2}})"), "")

    def test_live_turn_explains_next_step_is_unavailable(self):
        snap = {"sessions": [{"id": "s", "state": "running", "run_live": True}],
                "tasks": [], "versions": {}, "projects": []}
        html = render(self._setup(snap=snap) +
                      "stepFooter({id: 't', chat: true, state: 'running', current: 1, "
                      "steps: [{n: 1, session: 's', state: 'running', kind: 'chat'}]}, "
                      "{n: 1, session: 's', state: 'running', kind: 'chat'}, {}, null)")
        self.assertIn("Add step is available when this turn finishes", html)
        self.assertNotIn("Continue", html)

    def test_start_previews_edited_instructions_first(self):
        """Plan 36 Task 4 (headless pass): the package carries the instructions, so Start after an edit refreshes
        the preview instead of posting a revision the service answers with 'This step changed'."""
        view = "{asked: {kind: 'code', model: 'auto', instr: 'Go on'}}"
        self.assertEqual(render(f"[nextStale({view}, {{kind: 'code', model: 'auto', instr: ' Go on '}}), "
                                f"nextStale({view}, {{kind: 'code', model: 'auto', instr: 'add a test'}}), "
                                f"nextStale({view}, {{kind: 'verify', model: 'auto', instr: 'Go on'}}), "
                                f"nextStale({view}, {{kind: 'code', model: 'opus', instr: 'Go on'}}), "
                                "nextStale({}, {kind: 'code', model: 'auto', instr: 'Go on'})]"),
                         [False, True, True, True, True])

    def test_start_recovers_after_blank_instructions_and_a_failed_preview(self):
        result = render(self._setup() + """(async () => {
          const t = {id: 't', steps: [{n: 1, session: 's', kind: 'code'}]};
          boardData = {id: 't', data: {task: t}};
          nextOpen = {tid: 't', key: nextKey(t, t.steps[0])};
          renderBoard = async () => {};
          const button = {disabled: false};
          document = {querySelector: () => button, getElementById: () => null};
          let calls = [], fail = true;
          api = async (path, body) => {
            calls.push([path, body]);
            if (fail) throw Error('offline');
            return path.endsWith('/preview')
              ? {revision: 'r', route: {rung: 'sonnet', effort: 'high'}} : {step: 2};
          };
          await nextPreview();
          const empty = {error: nextView.error, calls: calls.length};
          nextDraft[nextOpen.key].instr = 'take over';
          await startNextStep(button);
          const failed = nextView.error;
          fail = false;
          await startNextStep(button);
          const reviewed = {revision: nextView.revision, calls: calls.length};
          await startNextStep(button);
          return {empty, failed, reviewed, calls, open: nextOpen, pick: boardPick};
        })()""")
        self.assertIn('Describe what this step should do', result['empty']['error'])
        self.assertEqual(result['empty']['calls'], 0)
        self.assertEqual(result['failed'], 'offline')
        self.assertEqual(result['reviewed'], {'revision': 'r', 'calls': 2})
        self.assertEqual([path for path, _ in result['calls']],
                         ['/api/task/next/preview', '/api/task/next/preview', '/api/task/next'])
        for _, body in result['calls']:
            self.assertEqual(body['instructions'], 'take over')
            self.assertEqual(body['kind'], 'code')
        self.assertEqual(result['calls'][-1][1]['revision'], 'r')
        self.assertIsNone(result['open'])
        self.assertEqual(result['pick'], 's2')

    def test_a_reseed_shows_in_the_open_field(self):
        """Plan 36 Task 4 (headless pass): setHtml keeps a field's typed value over a redraw, so a Work switch
        writes the reseeded instructions into the open field as well as the draft."""
        out = render("(() => { const f = {value: 'Go on'}; document = {getElementById: (id) => id === 'b-ninstr' ? f : null}; "
                     "const d = {instr: 'Go on'}; setInstr(d, verifyDefault(1)); return [d.instr === verifyDefault(1), f.value === verifyDefault(1)]; })()")
        self.assertEqual(out, [True, True])


@unittest.skipUnless(NODE, "Node is not installed")
class UnifiedTaskChatTest(unittest.TestCase):
    setup = """snap = {now: 100, sessions: [{id: 's', state: 'stop', run_live: false,
      window: true, project_dir: 'repo', forks: []}], tasks: [], versions: {}, projects: []};
      t = {id: 't', title: 'Task', state: 'running', current: 1, steps: [
        {n: 1, session: 's', kind: 'chat', state: 'running', goal: 'Implement', notes: []}]};
      d = {task: t, levers: {stop: '', done: '', add_next: ''}, step_levers: {
        continue: '', verify: '', handoff: '', escalate: '', escalate_to: 'opus/high',
        next: '', terminal: '', after_verify: ['handoff', 'escalate', 'done']}};
      boardTask = 't'; boardPick = 's1'; boardData = {id: 't', data: d};
      row = {id: 't', state: 'running', steps: t.steps}; snap.tasks = [row];
      boardChat = {sid: 's', chat: {items: []}}; """

    def test_task_entry_opens_overview_and_step_links_open_the_step(self):
        result = render(self.setup + """(async () => {
          renderBoard = async () => {}; showPage = name => {page = name;};
          openTask('t'); const task = [page, boardTask, boardPick, itab];
          boardData = {id: 't', data: d};
          await openSession('s'); const session = [page, boardTask, boardPick, itab];
          t.steps[0].attempts = [{session: 'old'}]; row.steps = t.steps;
          await openSession('old'); return {task, session, attempt: boardHistory};
        })()""")
        self.assertEqual(result, {"task": ["board", "t", "t", "chat"],
                                  "session": ["board", "t", "s1", "chat"], "attempt": "old"})

    def test_archived_task_session_links_open_the_task_inspector(self):
        result = render(self.setup + """(async () => {
          snap.tasks = []; snap.older = 1; snap.sessions[0].task = 't'; snap.sessions[0].step = 1;
          boardData = null; renderBoard = async () => {}; showPage = p => {page = p;};
          await openSession('s'); return [page, boardTask, boardPick, olderOpen, boardHistory];
        })()""")
        self.assertEqual(result, ['board', 't', 's1', True, 's'])

    def test_composer_is_outside_scroller_on_every_tab_and_next_form_keeps_it(self):
        for tab in ("chat", "recv", "hand", "route", "files", "plan"):
            with self.subTest(tab=tab):
                html = render(self.setup + f"itab = '{tab}'; inspStep(t, t.steps[0], d, row)")
                self.assertEqual(html.count('id="b-tcont"'), 1)
                self.assertLess(html.index('class="idock-bar"'), html.index('id="b-tcont"'))
                self.assertIn('Message current step 01: chat', html)
                self.assertNotIn('Open chat', html)
        html = render(self.setup + "nextOpen = {tid: 't', key: nextKey(t, t.steps[0])}; inspStep(t, t.steps[0], d, row)")
        self.assertIn('id="b-ninstr"', html)
        self.assertIn('id="b-tcont"', html)

    def test_composer_has_no_duplicate_session_controls(self):
        html = render(self.setup + "stepFooter(t, t.steps[0], d)")
        for action in ('cont',):
            self.assertIn(f'data-tact="{action}"', html)
        for text in ('Send', 'Attach'):
            self.assertIn(text, html)
        for gone in ('data-tact="handoff"', 'data-tact="chatdone"', 'data-tact="terminal"', 'data-tact="brief"',
                     'data-tact="vbrief"', 'data-tact="next"', 'data-tact="resume"', 'data-tact="verify"',
                     'data-tact="escalate"', 'Brief a new task', 'Verify in a new task', 'Terminal', 'Hand off'):
            self.assertNotIn(gone, html)
        cold = render(self.setup + "snap.sessions[0].state = 'interrupted'; d.step_levers.cold = {cost: 1, tokens: 1000, idle_s: 3600}; stepFooter(t, t.steps[0], d)")
        self.assertIn('Cold cache', cold)

    def test_table_states_keep_editable_input_and_honest_delivery_gate(self):
        cases = [('planned', 'planned', None, {}, 'not started'),
                 ('running', 'running', 'running', {'continue': 'still working'}, 'Working'),
                 ('waiting', 'running', 'stop', {'continue': ''}, 'Send answer'),
                 ('running', 'running', 'idle', {'continue': ''}, '>Send<'),
                 ('stopped', 'failed', 'interrupted', {'continue': ''}, 'Retry'),
                 ('stuck', 'failed', 'failed', {'continue': 'usage limit'}, 'usage limit'),
                 ('done', 'done', 'done', {'continue': ''}, 'Add step'),
                 ('running', 'running', 'idle', {'continue': 'runs are off'}, 'runs are off')]
        for state, step_state, session_state, levers, text in cases:
            with self.subTest(state=state, session=session_state):
                html = render(self.setup + f"t.state = {json.dumps(state)}; t.steps[0].state = {json.dumps(step_state)}; "
                              f"snap.sessions[0].state = {json.dumps(session_state)}; d.step_levers = {json.dumps(levers)}; "
                              "if (t.state === 'planned') t.steps[0].session = ''; "
                              "if (t.state === 'waiting') snap.sessions[0].stop_question = 'Which?'; "
                              "stepFooter(t, t.steps[0], d)")
                self.assertIn('id="b-tcont"', html)
                self.assertNotIn('id="b-tcont" disabled', html)
                self.assertIn(text, html)
                if state not in ('waiting',) and session_state != 'idle':
                    self.assertIn('disabled', html)

    def test_history_targets_current_and_stale_draft_requires_explicit_retarget(self):
        html = render(self.setup + "t.steps.push({n: 2, session: 's2', kind: 'code', state: 'running'}); t.current = 2; stepFooter(t, t.steps[0], d)")
        self.assertIn('History: step 01', html)
        self.assertIn('Message current step 02: code', html)
        self.assertIn('data-sid="s2"', html)
        html = render(self.setup + "taskDraftFor(t).text = 'keep me'; t.steps[0].session = 'retry'; stepFooter(t, t.steps[0], d)")
        self.assertIn('keep me', html)
        self.assertIn('destination changed', html)
        self.assertIn('Use current step', html)

    def test_send_preserves_draft_and_files_on_error_and_cold_confirmation(self):
        result = render(self.setup + """(async () => {
          const draft = taskDraftFor(t); draft.text = 'correct this';
          const key = taskAttachKey(t.id); att[key] = [{name: 'a.txt', data: 'YQ=='}];
          const box = {value: draft.text}, msg = {};
          document = {getElementById: id => id === 'b-tcont' ? box : msg};
          renderBoard = async () => {};
          let calls = []; api = async (path, body) => {calls.push([path, body]); throw Error('offline');};
          const b = {dataset: {tid: 't'}, textContent: 'Send'};
          d.step_levers.cold = {cost: 1};
          await taskChatAct('cont', b); const first = calls.length;
          await taskChatAct('cont', b);
          return {first, calls, text: draft.text, files: att[key].length, error: draft.error};
        })()""")
        self.assertEqual(result['first'], 0)
        self.assertRegex(result['calls'][0][1].pop('request_id'), r'^[0-9a-f]{32}$')
        self.assertEqual(result['calls'], [['/api/task/message', {'task': 't', 'text': 'correct this',
            'target': {'step': 1, 'session': 's', 'attempt': 1}, 'confirm': True,
            'files': [{'name': 'a.txt', 'data': 'YQ=='}]}]])
        self.assertEqual((result['text'], result['files'], result['error']), ('correct this', 1, 'offline'))

    def test_gap_answer_uses_task_route_and_does_not_drop_unsupported_attachments(self):
        result = render(self.setup + """(async () => {
          row.asks = 'Plan gap: choose'; d.levers.answer = ''; taskDraftFor(t).text = 'Use A';
          const b = {dataset: {tid: 't'}, textContent: 'Send answer'};
          let calls = []; api = async (path, body) => {calls.push([path, body]); return {};};
          renderBoard = async () => {}; actRedraw = () => {}; await taskChatAct('answer', b);
          return calls;
        })()""")
        self.assertRegex(result[0][1].pop('request_id'), r'^[0-9a-f]{32}$')
        self.assertEqual(result, [['/api/task/message', {'task': 't', 'text': 'Use A', 'files': [],
            'target': {'step': 1, 'session': 's', 'attempt': 1}, 'confirm': False}]])

    def test_server_modes_enable_guidance_while_busy_planned_and_paused(self):
        for state, timing in [('running', 'Queued for the end of this turn'),
                              ('planned', 'Saved for the first step. Sending does not start the task.'),
                              ('stopped', 'Sending saves this guidance; nothing runs. Retry asks whether to carry it into the next run.')]:
            with self.subTest(state=state):
                html = render(self.setup + f"t.state = {json.dumps(state)}; d.message = {{mode: 'queued', reason: '', timing: {json.dumps(timing)}}}; stepFooter(t, t.steps[0], d)")
                self.assertIn(timing, html)
                self.assertIn('data-tid="t">Send</button>', html)

    def test_message_retry_reuses_request_id_and_pending_actions_are_explicit(self):
        result = render(self.setup + """(async () => {
          d.message = {reason: '', target: {step: 1, session: 's', attempt: 1}};
          taskDraftFor(t).text = 'keep this'; renderBoard = () => {};
          let calls = []; api = async (p, b) => {calls.push(b); throw Error('offline');};
          const button = {dataset: {tid: 't'}};
          await taskChatAct('cont', button); await taskChatAct('cont', button);
          t.messages = [{id: 'a', status: 'queued', target: {step: 1, attempt: 1}, text: '<correction>'},
            {id: 'b', status: 'uncertain', target: {step: 1, attempt: 1}, text: 'check me'}];
          return {same: calls[0].request_id === calls[1].request_id, html: taskMessages(t, d)};
        })()""")
        self.assertTrue(result['same'])
        for text in ('Queued', 'Outcome unknown', 'Cancel guidance', 'Dismiss after checking conversation', '&lt;correction&gt;'):
            self.assertIn(text, result['html'])

    def test_failed_next_message_offers_resend_into_the_box(self):  # plan 48 D11
        result = render(self.setup + """(async () => {
          t.messages = [{id: 'n', mode: 'next', status: 'failed', target: {step: 1, attempt: 1}, text: 'verify 340 px',
                         error: 'The supervisor chose to wait and added no step. Resend to ask again.'},
            {id: 'g', status: 'failed', target: {step: 1, attempt: 1}, text: 'guidance'}];
          const html = taskMessages(t, d);
          boardData = {data: {task: t}}; actRedraw = () => {};
          let calls = []; api = async (p, b) => {calls.push([p, b]); return {};};
          await taskAct('resendmessage', {dataset: {tid: 't', mid: 'n'}});
          return {html, calls, text: taskDraftFor(t).text};
        })()""")
        self.assertEqual(result['html'].count('data-tact="resendmessage"'), 1)
        self.assertIn('data-tact="resendmessage" data-tid="t" data-mid="n"', result['html'])
        self.assertIn('Resend to ask again', result['html'])
        self.assertEqual(result['calls'], [['/api/task/message', {'task': 't', 'request_id': 'n', 'action': 'cancel',
                                                                  'confirm': False}]])
        self.assertEqual(result['text'], 'verify 340 px')

    def test_text_draft_is_restored_without_putting_attachment_bytes_in_preferences(self):
        result = render(self.setup + """(() => {
          const saved = {};
          localStorage = {setItem(k, v) {saved[k] = v;}, getItem(k) {return saved[k];}};
          const draft = taskDraftFor(t); draft.text = 'persist me'; draft.start = 2;
          att[taskAttachKey('t')] = [{data: 'secret attachment bytes'}];
          saveTaskDraft('t'); delete taskDraft.t;
          return {draft: taskDraftFor(t).text, stored: saved['task-draft:t']};
        })()""")
        self.assertEqual(result['draft'], 'persist me')
        self.assertNotIn('secret attachment bytes', result['stored'])

    def test_task_entry_points_render_identical_actions(self):
        result = render(self.setup + """(async () => {
          let html = '';
          renderBoard = async () => {boardData = {id: 't', data: d}; html = boardInspector(row, d);};
          showPage = name => {page = name;};
          openTask('t'); await renderBoard(); const overview = html;
          await goChat('t', 1); const step = html;
          openTask('t'); await renderBoard(); const again = html;
          return [overview === again, overview !== step];
        })()""")
        self.assertEqual(result, [True, True])

    def test_redraw_keeps_focus_caret_and_scroll_without_copying_another_tasks_text(self):
        result = render("""(() => {
          getSelection = () => ({isCollapsed: true});
          const draw = (other) => {
            const before = {id: 'b-tcont', value: 'draft A', dataset: {tid: 'a'},
              selectionStart: 2, selectionEnd: 5, scrollTop: 18};
            const after = {id: 'b-tcont', value: other ? 'draft B' : 'draft A', dataset: {tid: other ? 'b' : 'a'},
              focus() {this.focused = true;}, setSelectionRange(a, b) {this.selection = [a, b];}};
            let node = before;
            const oldScroll = {scrollTop: 42, clientHeight: 100, scrollHeight: 500}, newScroll = {};
            const el = {contains: () => true, querySelectorAll: () => [before], getAnimations: () => [],
              set innerHTML(v) {node = after;}, querySelector: s => s === '.iscroll' ? (node === before ? oldScroll : newScroll) : node};
            document = {activeElement: before, getElementById: () => node};
            setHtml(el, 'new', {sel: '.iscroll'});
            return {text: after.value, selection: after.selection || null, focused: !!after.focused,
              scroll: newScroll.scrollTop, inputScroll: after.scrollTop || 0};
          };
          return [draw(false), draw(true)];
        })()""")
        self.assertEqual(result, [dict(text='draft A', selection=[2, 5], focused=True, scroll=42, inputScroll=18),
                                  dict(text='draft B', selection=None, focused=False, scroll=42, inputScroll=0)])

    def test_success_clears_only_submitted_text_and_files_even_after_task_switch(self):
        result = render(self.setup + """(async () => {
          const draft = taskDraftFor(t), key = taskAttachKey(t.id); draft.text = 'send this';
          att[key] = [{name: 'a.txt', data: 'YQ=='}];
          let finish; api = () => new Promise(ok => {finish = ok;});
          const b = {dataset: {tid: 't'}};
          const pending = taskChatAct('cont', b);
          draft.text = 'next thought'; att[key].push({name: 'b.txt', data: 'Yg=='});
          boardTask = 'other';
          document = {getElementById: () => ({dataset: {tid: 'other'}, value: 'other draft'})};
          finish({session: 's'}); await pending;
          return {text: draft.text, files: att[key].map(f => f.name), busy: draft.busy};
        })()""")
        self.assertEqual(result, dict(text='next thought', files=['b.txt'], busy=False))

    def test_stale_attempt_blocks_send_and_explicit_retarget_keeps_text(self):
        result = render(self.setup + """(async () => {
          const draft = taskDraftFor(t); draft.text = 'keep this'; t.steps[0].session = 'retry';
          let calls = 0; api = async () => {calls++;}; renderBoard = () => {};
          const b = {dataset: {tid: 't'}};
          await taskChatAct('cont', b); await taskChatAct('retarget', b);
          return [calls, draft.text, draft.target];
        })()""")
        self.assertEqual(result, [0, 'keep this', 't|1|retry'])

    def test_history_fetch_cannot_overwrite_another_tasks_chat(self):
        result = render(self.setup + """(async () => {
          boardChat = null; let finish; api = () => new Promise(ok => {finish = ok;});
          page = 'board'; const pending = boardChatFetch(d, row);
          boardTask = 'other'; boardChat = {sid: 'other-session'};
          finish({items: [{text: 'old task'}]}); await pending;
          return boardChat;
        })()""")
        self.assertEqual(result, {'sid': 'other-session'})

    def test_drafts_and_attachment_keys_are_isolated_and_external_delivery_is_a_fork(self):
        result = render(self.setup + """(() => {
          const a = taskDraftFor(t); a.text = 'draft A'; a.start = 2; a.end = 3;
          att[taskAttachKey(t.id)] = [{name: 'a.txt', data: 'YQ=='}];
          const other = {...t, id: 'other'}; taskDraftFor(other).text = 'draft B';
          const again = taskDraftFor(t); d.step_levers.fork = true;
          return {same: a === again, text: again.text, selection: [again.start, again.end],
            files: att[taskAttachKey('t')].length, others: att[taskAttachKey('other')].length,
            html: stepFooter(t, t.steps[0], d)};
        })()""")
        self.assertTrue(result.pop('same'))
        html = result.pop('html')
        self.assertEqual(result, dict(text='draft A', selection=[2, 3], files=1, others=0))
        self.assertIn('Sends in a window copy', html)
        self.assertIn('a.txt', html)

    def test_paused_missing_tools_and_disconnected_states_disable_only_delivery(self):
        for change, reason in [("t.owner = 'fred'", "Resume or Retry"),
                               ("d.step_levers.continue = 'folder is gone'", "folder is gone"),
                               ("d.step_levers.continue = 'CLI not found'", "CLI not found"),
                               ("streamLost = true", "Disconnected")]:
            with self.subTest(change=change):
                html = render(self.setup + change + "; taskDraftFor(t).text = 'retained'; stepFooter(t, t.steps[0], d)")
                self.assertIn('retained</textarea>', html)
                self.assertIn(reason, html)
                self.assertIn('data-tid="t" disabled>Send', html)

    def test_plan_gap_files_are_retained_and_block_silent_attachment_loss(self):
        result = render(self.setup + """(async () => {
          row.asks = 'Plan gap: choose'; d.levers.answer = ''; taskDraftFor(t).text = 'Use A';
          const key = taskAttachKey(t.id); att[key] = [{name: 'a.txt', data: 'YQ=='}];
          let calls = 0; api = async () => {calls++;};
          await taskChatAct('answer', {dataset: {tid: 't'}});
          return {calls, files: att[key].length, html: stepFooter(t, t.steps[0], d)};
        })()""")
        self.assertEqual((result['calls'], result['files']), (0, 1))
        self.assertIn('Remove the files', result['html'])

    def test_task_recovery_remains_reachable_from_current_conversation(self):
        html = render(self.setup + "d.levers.pause = ''; d.levers.stepdone = ''; stepButtons(t, t.steps[0], d, row)")
        for action in ('stop', 'pause', 'stepdone'):
            self.assertIn(f'data-tact="{action}"', html)
        result = render(self.setup + """(async () => {
          openId = 's'; let name;
          goChat = async () => {}; taskAct = async action => {name = action;};
          await act('stop', {dataset: {}}); return name;
        })()""")
        self.assertEqual(result, 'stop')

    def test_delayed_inspector_cannot_restore_old_task_or_tab(self):
        result = render(self.setup + """(async () => {
          boardData = null; page = 'board'; let finish;
          api = () => new Promise(ok => {finish = ok;});
          const pending = renderInspector(null);
          boardTask = 'other'; boardPick = 's1';
          finish(d); await pending;
          return [boardTask, boardData];
        })()""")
        self.assertEqual(result, ['other', None])

    def test_delayed_navigation_does_not_steal_focus_from_another_task(self):
        result = render(self.setup + """(async () => {
          page = 'board'; let finish, focused = false;
          renderBoard = () => new Promise(ok => {finish = ok;});
          document = {getElementById: () => ({focus() {focused = true;}})};
          const pending = goChat('t', 1); boardTask = 'other';
          finish(); await pending; return focused;
        })()""")
        self.assertFalse(result)


@unittest.skipUnless(NODE, "Node is not installed")
class SelectionTest(unittest.TestCase):
    """Plan 44 navigation T1: a task entry point opens the task; a step link opens that step."""
    setup = """snap = {now: 100, sessions: [{id: 's', state: 'stop', run_live: false,
      window: true, project_dir: 'repo', forks: []}], tasks: [], versions: {}, projects: []};
      t = {id: 't', title: 'Task', state: 'running', current: 1, steps: [
        {n: 1, session: 's', kind: 'chat', state: 'running', goal: 'Implement', notes: []}]};
      d = {task: t, levers: {stop: '', done: '', add_next: ''}, step_levers: {continue: '', verify: '', handoff: ''}};
      boardTask = 't'; boardPick = 't';
      boardData = {id: 't', data: d};
      row = {id: 't', state: 'running', steps: t.steps}; snap.tasks = [row];
      boardChat = {sid: 's', chat: {items: []}}; """

    def test_task_entry_points_open_the_task_not_a_step(self):
        result = render(self.setup + """(async () => {
          renderBoard = async () => {}; showPage = n => {page = n;};
          t.steps.push({n: 2, session: '', kind: 'code', state: 'planned', goal: 'g'}); t.current = 2;
          openTask('t'); return [page, boardTask, boardPick];
        })()""")
        self.assertEqual(result, ['board', 't', 't'])

    def test_step_link_opens_that_step(self):
        result = render(self.setup + """(async () => {
          renderBoard = async () => {}; showPage = n => {page = n;};
          boardData = {id: 't', data: d};
          t.steps.push({n: 2, session: '', kind: 'code', state: 'planned', goal: 'g'}); t.current = 2;
          await goChat('t', 1); return [boardPick, boardTask, itab];
        })()""")
        self.assertEqual(result, ['s1', 't', 'chat'])

    def test_breadcrumb_shows_tasks_title_and_step(self):
        over = render(self.setup + "taskBreadcrumb(t)")
        self.assertIn('data-go="bback"', over)
        self.assertNotIn('Overview', over)  # plan 48: the opened task has no views
        step = render(self.setup + "taskBreadcrumb(t, t.steps[0])")
        self.assertIn('data-task="t"', step)
        self.assertIn('Step 01', step)

    def test_late_fetch_for_a_different_task_is_dropped(self):
        result = render(self.setup + """(async () => {
          boardData = null; page = 'board'; boardPick = 't';
          let finish; api = () => new Promise(ok => {finish = ok;});
          const pending = renderInspector(null);
          boardPick = 's1';
          finish(d); await pending;
          return [boardTask, boardPick, boardData];
        })()""")
        self.assertEqual(result, ['t', 's1', None])


@unittest.skipUnless(NODE, "Node is not installed")
class TaskOverviewTest(unittest.TestCase):
    """Plan 48 3.4 (was plan 44 nav T2): the opened task with its attention area, the route and the bar (Stop or
    Resume, Pause, then the task menu with Finish task and Accept step result)."""
    setup = """snap = {now: 100, sessions: [{id: 's', state: 'stop', run_live: false, window: true, project_dir: 'repo', forks: []}], tasks: [], versions: {}, projects: []};
      t = {id: 't', title: 'Task', state: 'running', current: 1, project: 'Console', effort: 'auto', goal: 'Implement the thing', steps: [
        {n: 1, session: 's', kind: 'chat', state: 'done', goal: 'Implement', notes: []},
        {n: 2, session: '', kind: 'code', state: 'planned', goal: 'Write tests'}]};
      d = {task: t, levers: {stop: '', done: '', add_next: ''}, step_levers: {continue: ''},
        notes: {'1': 'HANDOFF\\n## Goal\\ng\\n## Next\\nn\\nEND HANDOFF'}, chain: [], files: {}, questions: []};
      boardTask = 't'; boardPick = 't'; doneConfirm = '';
      boardData = {id: 't', data: d};
      row = {id: 't', state: 'running', cost: 1, steps: t.steps}; snap.tasks = [row];
      boardChat = {sid: 's', chat: {items: []}}; """

    def test_task_page_has_no_views_and_its_route_opens_the_steps(self):
        html = render(self.setup + "inspTask(t, d, row)")
        for gone in ('data-tact="taskview"', "Current progress", "Original prompt"):
            self.assertNotIn(gone, html)
        self.assertIn('data-bpick="s1"', html)
        self.assertIn('data-bpick="s2"', html)
        self.assertIn("Goal", html)

    def test_finish_task_is_in_the_menu_and_its_confirm_is_inline_and_green(self):
        html = render(self.setup + "taskButtons(t, d)")
        self.assertIn('data-tact="done"', html.split("<details", 1)[1])
        self.assertIn("Finish task", html)
        armed = render(self.setup + "doneConfirm = 't'; taskButtons(t, d)")
        self.assertIn("done-confirm", armed)
        self.assertIn('class="btn sm complete" data-tact="confirmdone"', armed)
        self.assertIn("Finish this task? History stays available.", armed)
        self.assertIn('data-tact="confirmdone"', armed)
        self.assertIn('data-tact="canceldone"', armed)

    def test_accept_step_result_is_recovery_only(self):
        html = render(self.setup + "d.levers.stepdone = ''; d.levers.stop = 'task is running'; taskButtons(t, d)")
        self.assertIn("Accept step result", html)
        self.assertIn('data-tact="stepdone"', html)
        self.assertIn("incomplete", html)  # it names accepting incomplete or failed output
        self.assertLess(html.index("<details"), html.index("Accept step result"))  # in More, never prominent

    def test_retry_is_drawn_once_and_only_when_the_menu_opened_it(self):
        failed = ("cfg = {models: ['opus'], ladder: {opus: ['opus']}, tiers: {think: [], write: [], read: []}}; "
                  "t.state = 'stopped'; t.why = 'stopped by Fred'; t.steps[0].state = 'failed'; row.state = 'stopped'; "
                  "d.levers = {retry: '', stop: 'task is stopped', done: ''}; ")
        shut = render(self.setup + failed + "inspTask(t, d, row)")
        self.assertNotIn('data-tact="retry"', shut)
        self.assertIn('data-tact="retryopen"', shut)
        opened = render(self.setup + failed + "retryOpen = 't'; inspTask(t, d, row)")
        self.assertEqual(opened.count('data-tact="retry"'), 1)
        self.assertIn('id="b-retrynote"', opened)
        result = render(self.setup + failed + """(async () => {
          renderBoard = async () => {}; boardPick = 's1';
          await taskAct('retryopen', {dataset: {tid: 't'}}); const open = [retryOpen, boardPick];
          await taskAct('retrycancel', {dataset: {tid: 't'}}); return [open, retryOpen];
        })()""")
        self.assertEqual(result, [["t", "t"], ""])

    def test_manual_boundary_does_not_say_to_resume(self):
        """A manual task between steps waits for Add step or Mark done; the Overview must not tell Fred to Resume."""
        boundary = ("t.state = 'waiting'; t.why = 'choose next step'; row.state = 'waiting'; row.paused_after = 1; "
                    "d.levers = {resume: 'choose a next step or finish the task', done: '', add_next: ''}; ")
        html = render(self.setup + boundary + "inspTask(t, d, row)")
        self.assertNotIn("Nothing starts until you Resume", html)
        paused = render(self.setup + "row.paused_after = 1; d.levers = {resume: ''}; inspTask(t, d, row)")
        self.assertIn("Nothing starts until you Resume", paused)

    def test_resume_renders_from_the_lever_after_a_pause(self):
        paused = ("t.state = 'waiting'; t.owner = 'fred'; row.state = 'waiting'; row.paused_after = 1; "
                  "d.levers = {resume: '', stop: 'task is waiting'}; taskButtons(t, d)")
        html = render(self.setup + paused)
        self.assertEqual(html.count('data-tact="resume"'), 1)
        self.assertIn(">Resume<", html)
        self.assertNotIn("Start task", html)
        boundary = render(self.setup + "t.state = 'waiting'; t.owner = 'fred'; "
                          "d.levers = {resume: 'choose a next step or finish the task'}; taskButtons(t, d)")
        self.assertNotIn('data-tact="resume"', boundary)
        follow = render(self.setup + "t.state = 'planned'; t.handoff_from = 'src'; "
                        "t.steps = [{n: 1, kind: 'code', state: 'planned', goal: 'x'}]; "
                        "d.levers = {resume: ''}; taskButtons(t, d)")
        self.assertIn("Start task", follow)

    def test_replan_approval_renders_on_overview(self):
        expr = self.setup + """t.state = 'waiting'; t.why = 'replanned: 1 steps added';
          t.steps = [{n: 1, kind: 'scout', state: 'done', goal: 'g1'}, {n: 2, kind: 'replan', state: 'waiting', goal: 'replan'}];
          t.current = 2; row.state = 'waiting';
          t.replan = {before: [{kind: 'scout', goal: 'g1'}], after: [{kind: 'scout', goal: 'g1'}, {kind: 'search', goal: 'g2'}], added: [1], dropped: []};
          d.levers = {confirm: '', keep: '', stop: 'task is waiting'};
          d.replan_note = '## Why\\na search step is needed first';
          inspTask(t, d, row)"""
        html = render(expr)
        self.assertEqual(html.count("Confirm plan"), 1)
        self.assertEqual(html.count("Keep old plan"), 1)
        self.assertIn("search", html)
        self.assertNotIn("Open step 2", html)

    def test_verify_is_inside_add_step_not_standalone(self):
        html = render(self.setup + "taskButtons(t, d)")
        self.assertEqual(html.count('data-tact="nextopen"'), 1)
        self.assertIn("Add step", html)
        self.assertNotIn("nextverify", html)
        self.assertNotIn(">Verify<", html)

    def test_question_and_confirm_share_one_attention_area(self):
        q = render(self.setup + "row.asks = 'Which step?'; inspTask(t, d, row)")
        self.assertEqual(q.count("task-attention"), 1)
        self.assertEqual(q.count("Which step?"), 1)  # never in a heading plus the composer
        c = render(self.setup + "t.state = 'waiting'; t.why = 'confirm Fable'; d.levers.confirm = ''; row.state = 'waiting'; inspTask(t, d, row)")
        self.assertEqual(c.count("task-attention"), 1)
        self.assertIn('data-tact="confirm"', c)

    def test_brief_a_new_task_and_delegate_hint_are_gone(self):
        result = render("""(async () => {
          snap = {now: 100, sessions: [{id: 's'}], tasks: [], versions: {}, projects: []};
          let html = '';
          setHtml = (el, h) => { html = h; };
          api = async () => ({continue: 'a chat', verify: 'off', handoff: 'off', escalate: 'off', next: 'off', after_verify: [], terminal: 'off', cold: null, fork: false, cwd: 'repo'});
          openId = 's'; leversSig = '';
          await renderLevers({id: 's', window: true, run_live: false, stop_question: '', state: 'idle', verdict: '', escalated: '', handoff_hint: '', handoff_by: '', forks: [], last_ts: 0, project_dir: 'repo', rules_warn: ''});
          return html;
        })()""")
        self.assertNotIn("Brief a new task", result)
        self.assertNotIn("Verify in a new task", result)
        self.assertIn("Unavailable:", result)
        note = render("noteLine({id: 's', verdict: '', denials: [], handoff_hint: '', rules_warn: '', delegate_hint: 'delegate? 9 reads in the main chat this turn', reads: 9, two_writers: false, escalated: '', forked_from: '', forks: [], source: 'chat'})")
        self.assertNotIn("delegate?", note)


@unittest.skipUnless(NODE, "Node is not installed")
class HandoffFormTest(unittest.TestCase):
    """Plan 44 navigation T3: the task menu's Hand off task opens a form in the opened task. Preview first; Save document and
    Create follow-up task only after a preview that matches the note; a handed source with handoff_to is not the
    session-level handed task."""
    setup = TaskOverviewTest.setup + """
      PV = {task: 't', text: '## Goal\\ng\\n## Findings\\n- 01: found\\n## Files touched\\nNone recorded.\\n## Troubleshooting\\nNone recorded.\\n## Open questions\\nNone recorded.\\n## Next\\nn',
            revision: 'r1', cost: 0.03, model: 'haiku', fallback: ''};
    """

    def test_handoff_form_is_closed_until_opened(self):
        self.assertEqual(render(self.setup + "handoffForm(t)"), "")
        self.assertEqual(render(self.setup + "handoffDraft.t = {open: false, note: ''}; handoffForm(t)"), "")

    def test_form_offers_only_preview_before_one_exists(self):
        html = render(self.setup + "handoffDraft.t = {open: true, note: 'finish it'}; handoffForm(t)")
        self.assertIn("handoff-form", html)
        self.assertIn('id="b-handoff-note"', html)
        self.assertIn('data-tid="t"', html)
        self.assertIn("finish it", html)
        self.assertIn('data-tact="handoffpreview"', html)
        self.assertIn('data-tact="handoffcancel"', html)
        for text in ("Save document", "Create follow-up task", "handoffsave", "handoffcreate"):
            self.assertNotIn(text, html)

    def test_form_offers_save_and_create_after_a_matching_preview(self):
        html = render(self.setup + "handoffDraft.t = {open: true, note: 'finish it', preview: Object.assign({asked: 'finish it'}, PV)}; handoffForm(t)")
        for text in ("Save document", "Create follow-up task", 'data-tact="handoffsave"', 'data-tact="handoffcreate"',
                     "Refresh preview", "## Findings", "haiku"):
            self.assertIn(text, html)

    def test_a_changed_note_invalidates_the_preview(self):
        html = render(self.setup + "handoffDraft.t = {open: true, note: 'something else', preview: Object.assign({asked: 'finish it'}, PV)}; handoffForm(t)")
        for text in ("Save document", "Create follow-up task", "handoffsave", "handoffcreate"):
            self.assertNotIn(text, html)
        self.assertIn('data-tact="handoffpreview"', html)
        typed = render(self.setup + """(() => {
          handoffDraft.t = {open: true, note: 'finish it', preview: Object.assign({asked: 'finish it'}, PV)};
          let drawn = 0; renderBoard = async () => { drawn++; };
          const kept = handoffTyped({id: 'b-handoff-note', dataset: {tid: 't'}, value: 'finish it '});
          const changed = handoffTyped({id: 'b-handoff-note', dataset: {tid: 't'}, value: 'finish it now'});
          return [kept, changed, drawn, handoffDraft.t.note];
        })()""")
        self.assertEqual(typed, [False, True, 1, "finish it now"])  # only the move from fresh to stale redraws

    def test_a_fallback_preview_says_it_was_built_by_code(self):
        html = render(self.setup + "PV.fallback = 'the pass returned no JSON'; PV.model = ''; handoffDraft.t = {open: true, note: '', preview: Object.assign({asked: ''}, PV)}; handoffForm(t)")
        self.assertIn("the pass returned no JSON", html)
        self.assertIn("Save document", html)  # a fallback is still a handoff

    def test_actions_post_the_preview_save_and_create_requests(self):
        result = render(self.setup + """(async () => {
          const calls = [];
          renderBoard = async () => {};
          showPage = () => {};
          api = async (path, body) => {
            calls.push([path, body]);
            if (path === '/api/task/handoff/preview') return Object.assign({}, PV);
            if (path === '/api/task/handoff') return body.create ? {task: 'new1', source: 't'} : {task: 't', file: 'task-handoff.md'};
            if (path === '/api/state') return {now: 200, sessions: [], tasks: [{id: 'new1', title: 'Continue', state: 'planned', steps: []}], versions: {}, projects: [], counts: {}};
            return {};
          };
          boardPick = 's1';
          await taskHandoff('handofftask', 't');
          const opened = [handoffDraft.t.open, boardPick];
          handoffDraft.t.note = ' finish it ';
          await taskHandoff('handoffpreview', 't');
          const previewed = [handoffDraft.t.preview.revision, handoffDraft.t.preview.asked, /^[0-9a-f]{32}$/.test(handoffDraft.t.request)];
          await taskHandoff('handoffsave', 't');
          const saved = handoffDraft.t.saved;
          await taskHandoff('handoffcreate', 't');
          return {calls, opened, previewed, saved, after: [boardTask, boardPick, handoffDraft.t]};
        })()""")
        self.assertEqual(result["opened"], [True, "t"])  # the form is in the opened task
        self.assertEqual(result["previewed"], ["r1", "finish it", True])
        self.assertTrue(result["saved"])
        paths = [c[0] for c in result["calls"]]
        self.assertEqual(paths, ["/api/task/handoff/preview", "/api/task/handoff", "/api/task/handoff", "/api/state"])
        self.assertEqual(result["calls"][0][1], {"task": "t", "note": "finish it"})
        save, create = result["calls"][1][1], result["calls"][2][1]
        self.assertEqual((save["create"], save["revision"], save["note"], save["task"]), (False, "r1", "finish it", "t"))
        self.assertEqual((create["create"], create["revision"], create["request_id"]), (True, "r1", save["request_id"]))
        self.assertRegex(create["request_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(result["after"][:2], ["new1", "t"])  # the follow-up task opens
        self.assertIsNone(result["after"][2])  # the source's draft is gone

    def test_a_failed_request_keeps_the_draft_and_says_why(self):
        result = render(self.setup + """(async () => {
          renderBoard = async () => {};
          api = async () => { throw new Error('This task already has a follow-up task.'); };
          handoffDraft.t = {open: true, note: 'x'};
          await taskHandoff('handoffpreview', 't');
          return [handoffDraft.t.open, handoffDraft.t.error, handoffDraft.t.busy, handoffForm(t)];
        })()""")
        self.assertEqual(result[:3], [True, "This task already has a follow-up task.", False])
        self.assertIn("This task already has a follow-up task.", result[3])

    def test_cancel_closes_the_form_and_keeps_the_note(self):
        result = render(self.setup + """(async () => {
          renderBoard = async () => {};
          handoffDraft.t = {open: true, note: 'keep me'};
          await taskHandoff('handoffcancel', 't');
          return [handoffDraft.t.open, handoffDraft.t.note, handoffForm(t)];
        })()""")
        self.assertEqual(result, [False, "keep me", ""])

    def test_overview_shows_the_form_and_a_stale_conflict_asks_for_a_refresh(self):
        html = render(self.setup + "handoffDraft.t = {open: true, note: ''}; inspTask(t, d, row)")
        self.assertIn("handoff-form", html)
        conflict = render(self.setup + """(async () => {
          renderBoard = async () => {};
          api = async (path) => { if (path.endsWith('/preview')) return Object.assign({}, PV);
            throw new Error('The task changed. Refresh the handoff preview before saving.'); };
          handoffDraft.t = {open: true, note: ''};
          await taskHandoff('handoffpreview', 't');
          await taskHandoff('handoffsave', 't');
          return [handoffDraft.t.preview, handoffDraft.t.error];
        })()""")
        self.assertIsNone(conflict[0])  # the stale preview is dropped: Save and Create are gone until Refresh
        self.assertIn("Refresh the handoff preview", conflict[1])

    def test_a_source_with_a_follow_up_is_not_the_session_level_handed_task(self):
        self.assertEqual(render("taskShown({state: 'handed', handoff_note: 'task-handoff.md', handoff_to: 'f1'})"), "handed_to")
        self.assertEqual(render("taskShown({state: 'handed', handoff_note: 'steps/01-handoff.md'})"), "handed")
        self.assertEqual(render("taskShown({state: 'handed', group: 'working'})"), "handing")
        self.assertEqual(render("TASK_WORD.handed_to[0]"), "Handed off")
        why = render(self.setup + "snap.now = 100; statusLine({state: 'handed', handoff_note: 'task-handoff.md', handoff_to: 'f1', group: 'done', updated: 90, steps: []})")
        self.assertEqual(why[0], "handed off to follow-up")
        old = render(self.setup + "statusLine({state: 'handed', handoff_note: 'steps/01-handoff.md', group: 'needs', updated: 90, steps: []})")
        self.assertEqual(old[0], "handed off · Start next task")
        html = render(self.setup + "t.state = 'handed'; t.handoff_note = 'task-handoff.md'; t.handoff_to = 'f1'; row.state = 'handed'; row.handoff_note = 'task-handoff.md'; row.handoff_to = 'f1'; d.handoff = 'old note'; inspTask(t, d, row)")
        self.assertNotIn("Start next task", html)
        self.assertIn("Handed off to follow-up", html)
        self.assertIn('data-task="f1"', html)
        session_level = render(self.setup + "t.state = 'handed'; t.handoff_note = 'steps/01-handoff.md'; row.state = 'handed'; row.handoff_note = 'steps/01-handoff.md'; d.handoff = 'the note'; inspTask(t, d, row)")
        self.assertIn("Start next task", session_level)

    def test_a_follow_up_task_id_has_a_label_like_every_other_task(self):
        self.assertEqual(render("labelOf('20261015-093012-a3f2')"), "1015-a3f2")
        self.assertEqual(render("labelOf('0123456789abcdef4567')"), "0123-4567")  # tasks.label: first and last four of 20 hex
        self.assertEqual(render("labelOf('../0123456789abcdef4567')"), "")
        links = render(self.setup + "t.handoff_to = '0123456789abcdef4567'; inspTask(t, d, row)")
        self.assertIn(">0123-4567</button>", links)

    def test_start_next_does_nothing_for_a_task_that_has_a_follow_up(self):
        result = render("""(async () => {
          snap = {now: 1, sessions: [], tasks: [{id: 't', handoff_to: 'f1', current: 1, steps: [{n: 1, session: 's'}]}], versions: {}, projects: []};
          let called = false; api = async () => { called = true; return {}; };
          await startNext('t', {disabled: false});
          return called;
        })()""")
        self.assertFalse(result)


@unittest.skipUnless(NODE, "Node is not installed")
class BoardListTest(unittest.TestCase):
    """Plan 48 moment 3: one list, three groups, one row and one status line per task; the header keeps one menu."""
    setup = """snap = {now: 1000, sessions: [], tasks: [], preps: [], versions: {}, projects: [], counts: {needs: 0}, older: 0};
      scope = ''; boardTask = ''; boardPick = ''; page = 'board'; selecting = ''; emptyOpen = false; olderOpen = false;
      const tk0 = {id: '20261019-100000-aaaa', title: 'Fix the overflow', project: 'Console', project_dir: 'repo', effort: 'auto',
        state: 'running', group: 'working', owner: 'service', current: 2, count: 3, cost: 0.5, updated: 940, why: '', asks: '',
        hand_off: '', chat: false, supervisor: {mode: 'suggest', attention: false, say: ''}, steps: [
        {n: 1, kind: 'scout', state: 'done', model: 'haiku', effort: 'low', harness: 'claude', cost: 0.1},
        {n: 2, kind: 'code', state: 'running', model: 'sonnet', effort: 'high', harness: 'claude', cost: 0.2},
        {n: 3, kind: 'verify', state: 'planned', model: '', effort: '', harness: '', cost: 0}]};
      const mkt = (o) => Object.assign({}, tk0, o, {supervisor: Object.assign({}, tk0.supervisor, o.supervisor || {})}); """

    def test_list_row_is_one_status_line(self):
        cases = {
            "running": ("tk0", "running · 02 code", ""),
            "asks": ("mkt({id: 'a1', state: 'waiting', group: 'needs', owner: 'fred', asks: 'Which database?'})", "needs you · Which database?", "y"),
            "say": ("mkt({id: 'a2', state: 'waiting', group: 'needs', owner: 'fred', why: 'choose next step', "
                    "supervisor: {attention: true, say: 'add_next_step: verify the 340 px case'}})",
                    "needs you · add_next_step: verify the 340 px case", "y"),
            "waits": ("mkt({id: 'a3', state: 'waiting', group: 'needs', owner: 'fred', why: 'confirm Fable'})", "needs you · confirm Fable", "y"),
            "failed": ("mkt({id: 'a4', state: 'stuck', group: 'needs', owner: 'fred', why: 'no HANDOFF block'})", "failed · 02 code: no HANDOFF block", "r"),
            "done": ("mkt({id: 'a5', state: 'done', group: 'done', current: 3})", "done · 3 steps · ", "g"),
            "stopped": ("mkt({id: 'a6', state: 'stopped', group: 'done'})", "stopped", ""),
            "replied": ("mkt({id: 'a7', chat: true, state: 'running', group: 'replied', updated: 820})", "replied · 3m", ""),
        }
        for name, (expr, text, tone) in cases.items():
            with self.subTest(name):
                line = render(self.setup + f"statusLine({expr})")
                self.assertTrue(line[0].startswith(text), line)
                self.assertEqual(line[1], tone, line)
                html = render(self.setup + f"taskHtml({expr})")
                self.assertEqual(html.count('data-bpick="t"'), 1)
                for gone in ("v-lab", "v-more"):  # no label chip, no folding control
                    self.assertNotIn(gone, html)
                self.assertIn(line[0].split(" · ")[0], html)
                # Fred 2026-10-20: a running task (not a chat) unfolds its step rows; the others stay one line
                if name == "running":
                    self.assertEqual(html.count('class="v-subs"'), 1)
                    self.assertEqual(html.count('data-bpick="s'), 3)
                else:
                    self.assertNotIn("v-subs", html)
                    self.assertEqual(html.count("data-bpick="), 1)

    def test_the_opened_task_unfolds_its_steps_in_the_list(self):
        html = render(self.setup + "boardTask = 'a5'; boardPick = 's2'; taskHtml(mkt({id: 'a5', state: 'done', group: 'done'}))")
        self.assertEqual(html.count('class="v-subs"'), 1)
        self.assertIn('picked" data-bpick="s2"', html)
        html = render(self.setup + "taskHtml(mkt({id: 'a5', state: 'done', group: 'done'}))")
        self.assertNotIn("v-subs", html)

    def test_three_groups_and_replied_chats_join_running(self):
        html = render(self.setup + """snap.tasks = [mkt({id: 'n1', state: 'waiting', group: 'needs', asks: 'Which?'}), tk0,
          mkt({id: 'r1', chat: true, state: 'running', group: 'replied', updated: 900}),
          mkt({id: 'd1', state: 'done', group: 'done', updated: 990})]; chainHtml()""")
        for label in ("Needs you · 1", "Running · 2", "Done today"):
            self.assertIn(label, html)
        for gone in (">Replied", ">Working", ">Idle", "Select all", 'data-sel='):
            self.assertNotIn(gone, html)

    def test_the_calendar_and_its_day_inspector_are_gone(self):
        for name in ("renderCal", "calLoad", "calDays", "pickDay", "inspDay", "daySpend", "dayTone", "calPicked", "headWhy"):
            self.assertEqual(render(f"typeof {name}"), "undefined", name)
        self.assertEqual(render("typeof doneOn"), "function")  # the delete bar still needs it
        html = APP.with_name("index.html").read_text(encoding="utf-8")
        for gone in ('id="calh"', 'id="todaymore"', 'data-go="usage"', 'data-go="models"'):
            self.assertNotIn(gone, html.split('<section data-page="usage"')[0], gone)
        self.assertIn('data-go="hmenu"', html)
        self.assertNotIn("overpace", APP.read_text(encoding="utf-8"))

    def test_header_menu_holds_the_pages_measure_selection_and_empty_chats(self):
        html = render(self.setup + "snap.sessions = [{id: 'e', group: 'empty', project_dir: 'repo'}]; headerMenu()")
        for item in ('data-go="usage"', 'data-go="models"', 'data-go="measure"', 'data-go="selectdone"', 'data-go="empties"'):
            self.assertIn(item, html)
        self.assertIn("Show 1 empty chat", html)
        self.assertNotIn("empty chat", render(self.setup + "headerMenu()"))  # none to show, no row
        measure = render(self.setup + "renderBoard = () => {}; go('measure'); [boardPick, boardTask]")
        self.assertEqual(measure, ["m", ""])
        select = render(self.setup + "renderBoard = () => {}; go('selectdone'); selecting === todayKey()")
        self.assertTrue(select)

    def test_nothing_picked_shows_the_empty_line_not_measure(self):
        self.assertIn("Open a task to see its route, its context and the supervisor's last decision", render(self.setup + "emptyPane()"))


@unittest.skipUnless(NODE, "Node is not installed")
class PrepCardTest(unittest.TestCase):
    """Plan 48 moment 1: the card reads the planner line and the steps, then one Start; the editors sit behind Edit steps."""
    setup = """snap = {now: 1000, sessions: [], tasks: [], preps: [], versions: {}, projects: []}; foldState = {};
      cfg = {kinds: ['scout', 'code', 'verify'], edit_kinds: ['code'], efforts: ['low', 'medium', 'high'], tiers: {}, models: [],
        ladder: {}, kinds_tier: {}, default_effort: 'medium', supervisor_config: {mode: 'suggest', projects: {}}};
      card = {id: 'p1', project_dir: 'repo', raw: 'fix it', prompt: 'Fix the 340 px overflow', fields: {}, cost: 0.09, turns: 3,
        route: {type: 'code', model: 'sonnet', effort: 'medium'}, floors: {},
        planner: {scope: 'ok', note: 'One CSS rule and its test', model: 'opus', turns: 2},
        steps: [{kind: 'scout', goal: 'Find the rule that keeps .krow wide'}, {kind: 'code', goal: 'Wrap .krow and add the test'},
                {kind: 'verify', goal: ''}]}; """

    def test_card_has_one_start_and_edit_steps_folded(self):
        out = render(self.setup + "prepHtml(card)")
        bar, body = out["bar"], out["scroll"]
        self.assertEqual(bar.count('data-pact="start"'), 1)
        for gone in ('data-pact="run"', 'data-pact="raw"', 'data-pact="task"', 'id="p-model"', 'id="p-effort"', "Run as task"):
            self.assertNotIn(gone, bar + body)
        for item in ('data-pact="edit"', 'data-pact="cancel"', 'data-pact="review"'):  # the card menu
            self.assertIn(item, bar)
        self.assertIn("supervised · suggest · runs in", bar)
        self.assertIn("One CSS rule and its test", body)  # the planner line
        summary = body.split('data-fkey="prep.edit"')[0]
        for text in ("Find the rule that keeps .krow wide", "Wrap .krow and add the test", "added by the Console after the last editing step"):
            self.assertIn(text, summary)
        self.assertNotIn("<select", summary)
        fold = body.split('data-fkey="prep.edit"')[1]
        self.assertTrue(fold.startswith(' aria-expanded="false"'), fold[:60])
        for editor in ('id="p-prompt"', 'id="p-steps"', 'data-pact="addstep"', 'id="effort"', 'id="p-fable"'):
            self.assertIn(editor, fold.split('class="fb"')[1])
        say = APP.read_text(encoding="utf-8")
        self.assertIn('<span class="kbd">Enter</span>prep and plan', say)
        self.assertIn('<span class="kbd">Ctrl+Enter</span>raw', say)

    def test_start_payload_follows_the_supervisor_mode(self):
        run = """(async () => {
          const els = {'p-prompt': {value: ' Fix it '}, 'p-msg': {innerHTML: ''}};
          document = {getElementById: (id) => els[id] || {value: '', innerHTML: ''}, querySelectorAll: () => [], querySelector: () => null};
          let calls = []; api = async (p, b) => { calls.push([p, b]); return {task: 'T1'}; };
          doRun = async (...a) => { calls.push(['run', a]); return true; }; openTask = () => {};
          stepList = () => CARD_STEPS; card = Object.assign({}, card, {project_dir: CARD_DIR});
          await startCard(card, {dataset: {}, disabled: false});
          return calls;
        })()"""
        steps = "[{kind: 'code', goal: 'Wrap .krow'}]"
        for name, conf, folder, supervised in [("suggest", "{mode: 'suggest', projects: {}}", "repo", True),
                                               ("auto", "{mode: 'auto', projects: {}}", "repo", True),
                                               ("project off", "{mode: 'auto', projects: {'C:\\\\REPO\\\\': 'off'}}", "c:/repo", False),
                                               ("no config", "undefined", "repo", True)]:
            with self.subTest(name):
                calls = render(self.setup + f"cfg.supervisor_config = {conf}; const CARD_STEPS = {steps}, CARD_DIR = {json.dumps(folder)}; " + run)
                self.assertEqual(len(calls), 1, calls)
                path, body = calls[0]
                self.assertEqual(path, "/api/task")
                self.assertEqual(body, {"prep": "p1", "prompt": "Fix it", "steps": [{"kind": "code", "goal": "Wrap .krow"}],
                                        "effort": "auto", "supervised": supervised})
        self.assertEqual(render(self.setup + "cfg.supervisor_config.projects = {'repo': 'off'}; startLine(card)"),
                         "Supervisor off: the steps run as listed")
        calls = render(self.setup + "const CARD_STEPS = [], CARD_DIR = 'repo'; " + run)  # no steps: one chat through /api/run
        self.assertEqual(calls, [["run", ["repo", "Fix it", "auto", "medium", "p1", "", False]]])
        self.assertEqual(render(self.setup + "startLine(Object.assign({}, card, {steps: []}))"), "One chat: no steps were planned")


@unittest.skipUnless(NODE, "Node is not installed")
class NextMessageComposerTest(unittest.TestCase):
    """Plan 48 D3 and D8: at a boundary the box tells the supervisor what to do next, text only."""
    setup = UnifiedTaskChatTest.setup + """t.state = 'done'; t.steps[0].state = 'done';
      d.message = {mode: 'next', reason: '', attachments: false,
        timing: 'Goes to the supervisor. The step it adds from your words starts without Approve.'}; """

    def test_composer_next_mode_label_and_no_attach(self):
        html = render(self.setup + "stepFooter(t, t.steps[0], d)")
        self.assertIn("Tell the supervisor what to do next", html)
        self.assertIn('placeholder="For example: verify only the 340 px case, then finish"', html)
        self.assertIn("Goes to the supervisor.", html)
        self.assertRegex(html, r'data-attach="task:t" disabled title="The supervisor reads text only\. Remove the files\."')
        self.assertNotIn("messagenext", html)
        self.assertIn('data-tid="t">Send</button>', html)
        with_files = render(self.setup + "att[taskAttachKey('t')] = [{name: 'a.png'}]; stepFooter(t, t.steps[0], d)")
        self.assertIn("The supervisor reads text only. Remove the files.", with_files.split('id="b-delivery"')[1])
        self.assertIn('data-tid="t" disabled>Send</button>', with_files)
        guidance = render(UnifiedTaskChatTest.setup + "d.message = {mode: 'queued', reason: '', timing: 'Queued'}; stepFooter(t, t.steps[0], d)")
        self.assertIn("Message current step 01: chat", guidance)
        self.assertNotIn("Tell the supervisor", guidance)


@unittest.skipUnless(NODE, "Node is not installed")
class OpenedTaskTest(unittest.TestCase):
    """Plan 48 3.4: the opened task is a head, the supervisor card, the route, the gauge and closed folds; the bar is
    Stop or Resume, Pause and the task menu."""
    setup = TaskOverviewTest.setup + """
      PEND = {wake: 3, status: 'suggest', reason: 'a verify checks the 340 px case', error: '', can_approve: true, can_reject: true,
        decision: {decision: 'add_next_step', kind: 'verify', source_step: 1, model: 'auto', reason: 'a verify checks the 340 px case'}};
      AUDIT = [{ts: 100, wake: 2, phase: 'outcome', status: 'dispatched', decision: 'retry', cost: 0.002, error: ''},
               {ts: 200, wake: 3, phase: 'decided', status: 'suggest', decision: 'add_next_step', cost: 0.003, error: ''}];
      d.supervisor = {mode: 'suggest', pending: PEND, audit: AUDIT}; """

    def test_sup_card_shows_approve_only_where_allowed(self):
        html = render(self.setup + "supCard(t, d)")
        self.assertIn('data-tact="supapprove" data-tid="t" data-wake="3"', html)
        self.assertIn('data-tact="supreject" data-tid="t" data-wake="3"', html)
        self.assertIn("Add 03 verify from 01&#39;s handover", html)  # esc()
        self.assertIn("a verify checks the 340 px case", html)
        self.assertIn("$0.003", html)
        no = render(self.setup + "PEND.can_approve = false; supCard(t, d)")
        self.assertNotIn("supapprove", no)
        self.assertIn('data-tact="supreject"', no)
        for status in ("uncertain", "escalate", "refused"):
            with self.subTest(status=status):
                odd = render(self.setup + f"PEND.status = '{status}'; PEND.can_approve = false; PEND.error = 'the dispatch did not answer'; supCard(t, d)")
                self.assertIn(">Dismiss<", odd)
                self.assertIn('data-tact="supreject" data-tid="t" data-wake="3" data-dismiss="1"', odd)
                self.assertNotIn("supapprove", odd)
                self.assertIn("a verify checks the 340 px case", odd)
        quiet = render(self.setup + "d.supervisor.pending = null; supCard(t, d)")
        self.assertIn("askbox quiet", quiet)
        self.assertIn("wake 3", quiet)
        self.assertNotIn("supapprove", quiet)
        self.assertNotIn("supreject", quiet)
        self.assertEqual(render(self.setup + "d.supervisor.mode = 'off'; supCard(t, d)"), "")
        self.assertEqual(render(self.setup + "delete d.supervisor; supCard(t, d)"), "")
        posts = render(self.setup + """(async () => {
          const calls = []; api = async (p, b) => { calls.push([p, b]); return {}; }; renderBoard = async () => {};
          const els = {'b-supnote': {value: ' not yet '}}; document = {getElementById: (id) => els[id] || null};
          await taskAct('supapprove', {dataset: {tid: 't', wake: '3'}});
          await taskAct('supreject', {dataset: {tid: 't', wake: '3'}});
          const opened = supCard(t, d).includes('id="b-supnote"'), sent = calls.length;
          await taskAct('supreject', {dataset: {tid: 't', wake: '3'}});
          await taskAct('supreject', {dataset: {tid: 't', wake: '3', dismiss: '1'}});
          await taskAct('supmode', {dataset: {tid: 't', mode: 'auto'}});
          return {calls, opened, sent};
        })()""")
        self.assertTrue(posts["opened"])
        self.assertEqual(posts["sent"], 1)  # the first Reject click only opens the note
        self.assertEqual(posts["calls"], [
            ["/api/task/supervisor", {"task": "t", "wake": 3, "action": "approve"}],
            ["/api/task/supervisor", {"task": "t", "wake": 3, "action": "reject", "note": "not yet"}],
            ["/api/task/supervisor", {"task": "t", "wake": 3, "action": "reject"}],
            ["/api/task/supervisor", {"task": "t", "mode": "auto"}]])

    def test_route_lists_proposed_steps_dim(self):
        html = render(self.setup + "t.supervisor = {proposed: [{kind: 'verify', goal: 'check it', model: ''}, {kind: 'code', goal: 'more', model: ''}]}; routeHtml(t, d, row)")
        self.assertIn('data-bpick="s1"', html)
        self.assertIn('data-bpick="s2"', html)
        self.assertEqual(html.count('class="v-sr pl proposed"'), 2)
        tail = html.split('class="v-sr pl proposed"')[1]
        self.assertIn('<span class="n">03</span>', tail)
        self.assertIn("proposed", tail)
        self.assertNotIn("data-bpick", html.split('class="v-sr pl proposed"', 1)[1])  # a proposed row opens nothing
        self.assertNotIn("proposed", render(self.setup + "routeHtml(t, d, row)").replace("Route", ""))
        gauge = render(self.setup + "t.steps[0].ctx_tokens = 92000; gaugeHtml(t, row)")
        self.assertEqual(gauge.count("<i"), 30)
        self.assertIn("92K", gauge)
        self.assertIn("150K", gauge)
        self.assertIn("300K", gauge)
        unknown = render(self.setup + "t.steps[0].harness = 'codex'; gaugeHtml(t, row)")
        self.assertIn("<b>?</b>", unknown)
        self.assertIn("codex reports a turn&#39;s spend", unknown)

    def test_opened_task_has_no_tabs_and_closed_folds(self):
        html = render(self.setup + "inspTask(t, d, row)")
        for gone in ('data-tact="taskview"', "Overview", "Current progress", "Latest result", "Original prompt"):
            self.assertNotIn(gone, html)
        self.assertIn("supervised · suggest", html)
        self.assertIn('data-bpick="s1"', html)
        self.assertIn("Supervisor suggests", html)
        self.assertLess(html.index("Supervisor suggests"), html.index('data-bpick="s1"'))
        self.assertRegex(html, r'data-fkey="tgoal" aria-expanded="false"')
        self.assertNotIn("Implement the thing</pre>", html.split('data-fkey="tgoal"')[0])

    def test_task_bar_is_stop_or_resume_pause_and_menu(self):
        allowed = ("t.steps[0].state = 'running'; t.state = 'running'; d.levers = {stop: '', pause: '', add_next: '', done: '', retry: '', "
                   "stepdone: '', redo: '', clear: '', resume: 'task is running'}; d.step_levers = {terminal: '', escalate: ''}; "
                   "d.handoff_available = ''; snap.sessions[0].state = 'running'; snap.sessions[0].run_live = true; ")
        html = render(self.setup + allowed + "taskButtons(t, d)")
        bar, menu = html.split("<details", 1)
        self.assertIn('data-tact="stop"', bar)
        self.assertIn('data-tact="pause"', bar)
        self.assertLess(bar.index('data-tact="stop"'), bar.index('data-tact="pause"'))
        for gone in ("nextopen", 'data-tact="done"', 'data-tact="retry', "verify", "escalate", 'data-tact="cont"', "Mark done", "resume"):
            self.assertNotIn(gone, bar)
        for item in ('data-tact="handofftask"', 'data-tact="done"', 'data-tact="nextopen"', 'data-tact="retryopen"',
                     'data-tact="stepdone"', 'data-tact="redo"', 'data-tact="terminal"', 'data-tact="supmode" data-tid="t" data-mode="off"',
                     'data-tact="supmode" data-tid="t" data-mode="auto"', 'data-tact="folder"', 'data-tact="clear"',
                     'data-go="models"', 'data-go="usage"', "Add step on a model", "Retry on a model", "Finish task"):
            self.assertIn(item, menu)
        self.assertIn('data-mode="suggest" aria-pressed="true"', menu)
        for gone in ("escalate", "Use a stronger model", "Verify", "Continue"):
            self.assertNotIn(gone, menu)
        self.assertLess(menu.index("Hand off task"), menu.index("Finish task"))
        self.assertLess(menu.index("Finish task"), menu.index("Add step on a model"))
        off = render(self.setup + "d.levers = {stop: 'x', pause: 'x', add_next: 'x', done: 'x', retry: 'x', stepdone: 'x', redo: 'x', clear: 'x', resume: 'x'}; "
                     "d.step_levers = {terminal: 'x'}; d.handoff_available = 'x'; taskButtons(t, d)")
        for gone in ("stop", "pause", "handofftask", 'data-tact="done"', "nextopen", "retryopen", "stepdone", "redo", "terminal", "clear", "resume"):
            self.assertNotIn(gone, off)
        self.assertIn('data-tact="folder"', off)
        resume = render(self.setup + "d.levers = {resume: '', stop: 'task is waiting', pause: ''}; taskButtons(t, d)")
        bar = resume.split("<details", 1)[0]
        self.assertIn('data-tact="resume"', bar)
        self.assertNotIn('data-tact="stop"', bar)
        self.assertLess(bar.index('data-tact="resume"'), bar.index('data-tact="pause"'))
        nosup = render(self.setup + "delete d.supervisor; taskButtons(t, d)")
        self.assertNotIn("supmode", nosup)


@unittest.skipUnless(NODE, "Node is not installed")
class RecoveryBoxTest(unittest.TestCase):
    """Plan 48 section 7: the attention area says what definitely finished, what was cut and what Fred can do, from
    GET /api/task `recovery`, levers and the uncertain records; it adds no button."""
    setup = TaskOverviewTest.setup + """t.state = 'stuck'; t.why = 'the run did not finish cleanly (after one retry)';
      t.current = 2; t.steps[1].state = 'failed'; t.steps[1].session = 's2';
      d.levers = {retry: '', stepdone: '', resume: 'not paused', stop: 'task is stuck'};
      d.recovery = {done: {step: 1, kind: 'chat', how: 'finished', verdict: '', handoff: '01-chat/handoff.md', facts: '01-chat/facts.md', ended: 50},
        cut: {step: 2, kind: 'code', attempt: 2, cause: 'interrupted', why: 'the run did not finish cleanly', ended: 90}, orphan: null};
      row.state = 'stuck'; """

    def test_recovery_box_names_done_and_cut(self):
        html = render(self.setup + "attentionArea(t, d, row)")
        box = html.split('class="askbox recovery"', 1)[1]
        self.assertIn('data-bpick="s1" data-btask="t">Step 01 chat</button> finished with a saved handoff.', box)
        self.assertIn('data-bpick="s2" data-btask="t">Step 02 code</button>, attempt 2, was interrupted: the run ended without a result (a restart or a crash).', box)
        self.assertIn("Its file edits or other actions may already have happened. Nothing is undone", box)
        self.assertIn("Git and test facts are as recorded when step 01 ended, not a fresh check.", box)
        self.assertLess(html.index("askbox recovery"), html.index("Stuck"))  # above the stuck box
        first = render(self.setup + "d.recovery.done = null; attentionArea(t, d, row)")
        self.assertIn("No completed step recorded.", first)
        self.assertNotIn("not a fresh check", first)
        for cause, text in (("stopped", "was stopped."), ("unknown", "did not finish; the cause is not recorded."),
                            ("failed", "failed: it hit the turn cap (40 turns)."), ("timeout", "failed: it hit the turn cap (40 turns).")):
            with self.subTest(cause=cause):
                out = render(self.setup + f"d.recovery.cut.cause = '{cause}'; d.recovery.cut.why = 'it hit the turn cap (40 turns)'; attentionArea(t, d, row)")
                self.assertIn("attempt 2, " + text, out)
        verdict = render(self.setup + "d.recovery.done.verdict = 'PASS'; d.recovery.done.kind = 'verify'; attentionArea(t, d, row)")
        self.assertIn("Step 01 verify</button> finished: VERDICT PASS.", verdict)
        bare = render(self.setup + "d.recovery.done.handoff = ''; attentionArea(t, d, row)")
        self.assertIn("finished; no handoff was saved.", bare)
        accepted = render(self.setup + "d.recovery.done.how = 'accepted'; attentionArea(t, d, row)")
        self.assertIn("was accepted by you as it was on disk.", accepted)
        long = render(self.setup + "d.recovery.cut.cause = 'failed'; d.recovery.cut.why = '<b>' + 'x'.repeat(400); attentionArea(t, d, row)")
        self.assertIn("&lt;b&gt;", long)  # esc(): a reason is text
        self.assertEqual(render(self.setup + "d.recovery = null; t.state = 'running'; t.why = ''; t.steps[1].state = 'running'; attentionArea(t, d, row)"), "")

    def test_recovery_box_offers_only_open_levers(self):
        html = render(self.setup + "attentionArea(t, d, row)")
        self.assertIn("Retry on a model (task menu) runs step 02 again; attempt 2&#39;s edits stay.", html)
        self.assertIn("Accept step result (task menu) marks step 02 done with the files as they are now.", html)
        self.assertNotIn("Resume lets", html)
        self.assertNotIn("data-tact", html.split('class="askbox recovery"', 1)[1].split("</div>", 1)[0])  # no new button
        none = render(self.setup + "d.levers = {retry: 'still working: wait until it stops', stepdone: 'x', resume: 'x', stop: 'x'}; attentionArea(t, d, row)")
        self.assertIn("No recovery action is open: still working: wait until it stops.", none)
        self.assertNotIn("Retry on a model (task menu)", none)
        orphan = render(self.setup + """t.state = 'running'; t.why = ''; t.steps[1].state = 'running';
          d.recovery = {done: d.recovery.done, cut: null, orphan: {step: 2, attempt: 2}};
          d.levers = {retry: 'task is running', stepdone: 'x', resume: 'not paused', stop: ''}; attentionArea(t, d, row)""")
        self.assertIn("Step 02&#39;s run from an earlier service is still running; nothing else runs on this step until it ends.", orphan)
        self.assertIn("Stop (bar) ends that run.", orphan)
        self.assertNotIn("Retry on a model (task menu)", orphan)
        self.assertNotIn("No recovery action is open", orphan)

    def test_recovery_box_points_to_uncertain_without_repeating_it(self):
        extra = """d.supervisor = {mode: 'suggest', pending: {wake: 4, status: 'uncertain', decision: null, error: 'Service restarted during dispatch; it will not be replayed.', can_approve: false, can_reject: true}, audit: []};
          t.messages = [{id: 'm', status: 'uncertain', text: 'carry on', target: {step: 2, attempt: 2}, error: 'Service restarted during dispatch.'}]; """
        html = render(self.setup + extra + "attentionArea(t, d, row)")
        self.assertIn("The supervisor&#39;s wake 4 dispatch has an unknown outcome (card below). It is never replayed; Dismiss does not mean it failed.", html)
        self.assertIn("Your message to step 02 has an unknown delivery (message box). It is never replayed; Dismiss does not mean it was not delivered.", html)
        self.assertNotIn("carry on", html)  # the composer shows the message
        self.assertNotIn("Service restarted during dispatch", html)  # the card shows the error
        self.assertNotIn("supreject", html)
        alone = render(self.setup + extra + "d.recovery = null; t.state = 'waiting'; t.why = ''; attentionArea(t, d, row)")
        self.assertIn("askbox recovery", alone)
        self.assertNotIn("No completed step recorded", alone)
        off = render(self.setup + extra + "d.supervisor.mode = 'off'; attentionArea(t, d, row)")
        self.assertNotIn("wake 4", off)

    def test_recovery_refresh_keeps_draft_and_focus(self):
        html = render(self.setup + "taskDraftFor(t).text = 'half a thought'; inspTask(t, d, row)")
        body = html.split('class="ipane"', 1)[1]
        self.assertLess(body.index("askbox recovery"), body.index("Route"))
        self.assertIn("half a thought</textarea>", html)
        self.assertNotIn("<textarea", html.split('class="askbox recovery"', 1)[1].split("</div>", 1)[0])
        self.assertNotIn("<input", html.split('class="askbox recovery"', 1)[1].split("</div>", 1)[0])


if __name__ == "__main__":
    unittest.main()
