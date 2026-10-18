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

    def test_standalone_chat_has_task_prep_and_chat_rows(self):
        setup = """snap = {now: 100}; page = 'session'; openId = 's'; sessionView = 'chat';
          s = {id: 's', title: 'Fix the run', state: 'replied', group: 'replied',
               symbol: 'R', project: 'Console', model: 'sonnet', harness: 'claude',
               effort: 'medium', cost: 1, ctx_tokens: 0, prep: ''}; """
        html = render(setup + "sessionTree(s)")
        for view in ('task', 'prep', 'chat'):
            self.assertIn('data-sview="' + view + '"', html)
        self.assertIn('not recorded', html)
        self.assertIn('class="v-sr picked"', html)
        self.assertIn('<b>chat</b>', html)
        recorded = render(setup + "s.prep = 'p'; s.prep_model = 'haiku'; s.prep_cost = 0.01; sessionTree(s)")
        self.assertNotIn('not recorded', recorded)
        self.assertIn('haiku', recorded)

    def test_chat_task_expands_like_other_running_tasks(self):
        self.assertTrue(render("boardTask = ''; taskOpen({id: 't', chat: true, state: 'running', group: 'working'})"))

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

    def test_historical_step_points_to_the_latest(self):
        html = render(self._setup() + "histFoot({id: 't', steps: [{n: 1}, {n: 2, session: 's2'}]}, {n: 1}, {})")
        self.assertIn("Go to step 02", html)

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
        self.assertIn('class="btn sm go" data-tact="nextopen"', dock)
        self.assertIn("Mark done", dock)
        self.assertNotIn("Hand off", dock)  # Hand off task is the whole-task flow, in More

    def test_step_dock_reads_the_task_action_area_where_the_service_allows_it(self):
        """Plan 44 nav T2: the current step's dock is the task action area (Stop prominent, Accept step result in
        More); Stop is not offered on a chat whose turn is over, and the failed-step recovery only on the current step."""
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
        self.assertIn('class="btn sm go" data-tact="retry" data-tid="t"', failed)
        self.assertIn('data-tact="stepdone" data-tid="t"', failed)
        self.assertIn("Accept step result", failed)
        old = render(self._setup() + f"stepButtons({t}, {{n: 1, session: 's1', state: 'done', kind: 'scout'}}, {{levers: {{retry: '', stepdone: ''}}}}, {{state: 'done'}})")
        self.assertNotIn("Accept step result", old)
        off = render(self._setup() + f"stepButtons({t}, {{n: 2, session: 's2', state: 'failed', kind: 'code'}}, {{levers: {{retry: 'task is stopped', stepdone: 'still working'}}}}, {{state: 'failed'}})")
        self.assertNotIn("Retry", off)
        self.assertNotIn("Accept step result", off)

    def test_task_actions_show_only_where_the_service_allows_it(self):
        """Plan 44 nav T2: the one action area reads task_levers for Add step, Mark done and Delete, step_levers for
        terminal and escalate, and handoff_available for Hand off task; no standalone Verify or Continue."""
        snap = {"sessions": [{"id": "s2", "state": "idle", "run_live": False}], "tasks": [], "versions": {}, "projects": []}
        t = "{id: 't', current: 2, steps: [{n: 1, session: 's1', state: 'done', kind: 'scout'}, {n: 2, session: 's2', state: 'running', kind: 'chat'}]}"
        html = render(self._setup(snap=snap) + f"taskButtons({t}, {{levers: {{add_next: '', done: '', clear: ''}}, "
                      "step_levers: {continue: '', terminal: '', escalate: ''}, next_step: {source_step: 2}, handoff_available: ''})")
        for text in ('data-tact="nextopen" data-tid="t" data-n="2"', 'data-tact="done"', 'data-tact="clear"',
                     'data-tact="handofftask"', 'data-tact="terminal"', 'data-tact="escalate"'):
            self.assertIn(text, html)
        self.assertLess(html.index("Add step"), html.index("Mark done"))
        for text in ("Verify", "Continue", "Finish task", "Mark step done"):
            self.assertNotIn(text, html)
        off = render(self._setup(snap=snap) + f"taskButtons({t}, {{levers: {{add_next: 'task is stuck', done: '', clear: 'task is stuck'}}, step_levers: {{}}}})")
        self.assertIn('class="btn sm complete" data-tact="done"', off)  # Mark done stays while allowed
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
        self.assertIn("Hand off task", html)
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
        foot = render(self._setup() + f"histFoot({t}, {{n: 2}}, {{}})")
        self.assertIn("Go to step 03", foot)
        self.assertNotIn("Next steps start", foot)

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
          openTask('t'); const task = [page, boardTask, boardPick, taskView, itab];
          boardData = {id: 't', data: d};
          await openSession('s'); const session = [page, boardTask, boardPick, itab];
          t.steps[0].attempts = [{session: 'old'}]; row.steps = t.steps;
          await openSession('old'); return {task, session, attempt: boardHistory};
        })()""")
        self.assertEqual(result, {"task": ["board", "t", "t", "overview", "chat"],
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
                              ('stopped', 'Saved guidance. Use Resume or Retry explicitly to deliver it.')]:
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

    def test_finished_message_transfer_is_explicit_and_keeps_message_draft(self):
        result = render(self.setup + """(async () => {
          taskDraftFor(t).text = 'new instructions';
          openNextForm = async () => {nextOpen = {tid: 't', key: 'next'}; nextDraft.next = {instr: 'seed'};};
          nextPreview = async () => {}; document = {getElementById: () => null};
          await taskAct('messagenext', {dataset: {tid: 't'}});
          return [nextDraft.next.instr, taskDraftFor(t).text];
        })()""")
        self.assertEqual(result, ['new instructions', 'new instructions'])

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
    """Plan 44 navigation T1: a task entry point opens the task's Overview; a step link opens that step."""
    setup = """snap = {now: 100, sessions: [{id: 's', state: 'stop', run_live: false,
      window: true, project_dir: 'repo', forks: []}], tasks: [], versions: {}, projects: []};
      t = {id: 't', title: 'Task', state: 'running', current: 1, steps: [
        {n: 1, session: 's', kind: 'chat', state: 'running', goal: 'Implement', notes: []}]};
      d = {task: t, levers: {stop: '', done: '', add_next: ''}, step_levers: {continue: '', verify: '', handoff: ''}};
      boardTask = 't'; boardPick = 't'; taskView = 'overview';
      boardData = {id: 't', data: d};
      row = {id: 't', state: 'running', steps: t.steps}; snap.tasks = [row];
      boardChat = {sid: 's', chat: {items: []}}; """

    def test_task_entry_points_open_overview_not_a_step(self):
        result = render(self.setup + """(async () => {
          renderBoard = async () => {}; showPage = n => {page = n;};
          t.steps.push({n: 2, session: '', kind: 'code', state: 'planned', goal: 'g'}); t.current = 2;
          openTask('t'); return [page, boardTask, boardPick, taskView];
        })()""")
        self.assertEqual(result, ['board', 't', 't', 'overview'])

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
        self.assertIn('Overview', over)
        step = render(self.setup + "taskBreadcrumb(t, t.steps[0])")
        self.assertIn('data-task="t"', step)
        self.assertIn('Step 01', step)

    def test_late_fetch_for_a_different_task_is_dropped(self):
        result = render(self.setup + """(async () => {
          boardData = null; page = 'board'; boardPick = 't'; taskView = 'overview';
          let finish; api = () => new Promise(ok => {finish = ok;});
          const pending = renderInspector(null);
          taskView = 'steps';
          finish(d); await pending;
          return [boardTask, boardPick, taskView, boardData];
        })()""")
        self.assertEqual(result, ['t', 't', 'steps', None])


@unittest.skipUnless(NODE, "Node is not installed")
class TaskOverviewTest(unittest.TestCase):
    """Plan 44 navigation T2: the Overview with Goal / attention / progress, the Steps and Files views, and the one
    action area (two prominent + More, green Mark done, Accept step result in More)."""
    setup = """snap = {now: 100, sessions: [{id: 's', state: 'stop', run_live: false, window: true, project_dir: 'repo', forks: []}], tasks: [], versions: {}, projects: []};
      t = {id: 't', title: 'Task', state: 'running', current: 1, project: 'Console', effort: 'auto', goal: 'Implement the thing', steps: [
        {n: 1, session: 's', kind: 'chat', state: 'done', goal: 'Implement', notes: []},
        {n: 2, session: '', kind: 'code', state: 'planned', goal: 'Write tests'}]};
      d = {task: t, levers: {stop: '', done: '', add_next: ''}, step_levers: {continue: ''},
        notes: {'1': 'HANDOFF\\n## Goal\\ng\\n## Next\\nn\\nEND HANDOFF'}, chain: [], files: {}, questions: []};
      boardTask = 't'; boardPick = 't'; taskView = 'overview'; doneConfirm = '';
      boardData = {id: 't', data: d};
      row = {id: 't', state: 'running', cost: 1, steps: t.steps}; snap.tasks = [row];
      boardChat = {sid: 's', chat: {items: []}}; """

    def test_task_page_has_overview_steps_files_views(self):
        over = render(self.setup + "taskView = 'overview'; inspTask(t, d, row)")
        self.assertIn("Goal", over)
        self.assertIn("Current progress", over)
        self.assertIn('data-tact="taskview" data-view="steps"', over)
        self.assertIn('data-tact="taskview" data-view="files"', over)
        steps = render(self.setup + "taskView = 'steps'; inspTask(t, d, row)")
        self.assertIn('data-bpick="s1"', steps)
        self.assertIn('data-bpick="s2"', steps)
        self.assertIn("Write tests", steps)
        files = render(self.setup + "taskView = 'files'; inspTask(t, d, row)")
        self.assertIn("Original prompt", files)

    def test_mark_done_is_green_and_confirm_is_inline(self):
        html = render(self.setup + "taskButtons(t, d)")
        self.assertIn('class="btn sm complete"', html)
        self.assertIn("Mark done", html)
        armed = render(self.setup + "doneConfirm = 't'; taskButtons(t, d)")
        self.assertIn("done-confirm", armed)
        self.assertIn("Mark this task done? History stays available.", armed)
        self.assertIn('data-tact="confirmdone"', armed)
        self.assertIn('data-tact="canceldone"', armed)

    def test_accept_step_result_is_recovery_only(self):
        html = render(self.setup + "d.levers.stepdone = ''; d.levers.stop = 'task is running'; taskButtons(t, d)")
        self.assertIn("Accept step result", html)
        self.assertIn('data-tact="stepdone"', html)
        self.assertIn("incomplete", html)  # it names accepting incomplete or failed output
        self.assertLess(html.index("<details"), html.index("Accept step result"))  # in More, never prominent

    def test_retry_is_not_drawn_twice_on_the_overview(self):
        """The Overview's attention area already has the Retry form (note and model); the action area adds its own
        one-click Retry only where that form is not on the page (the Steps and Files views)."""
        failed = ("cfg = {models: ['opus'], ladder: {opus: ['opus']}, tiers: {think: [], write: [], read: []}}; "
                  "t.state = 'stopped'; t.why = 'stopped by Fred'; t.steps[0].state = 'failed'; row.state = 'stopped'; "
                  "d.levers = {retry: '', stop: 'task is stopped', done: ''}; ")
        over = render(self.setup + failed + "taskView = 'overview'; inspTask(t, d, row)")
        self.assertEqual(over.count('data-tact="retry"'), 1)
        self.assertIn('id="b-retrynote"', over)
        steps = render(self.setup + failed + "taskView = 'steps'; inspTask(t, d, row)")
        self.assertEqual(steps.count('data-tact="retry"'), 1)
        self.assertNotIn('id="b-retrynote"', steps)

    def test_manual_boundary_does_not_say_to_resume(self):
        """A manual task between steps waits for Add step or Mark done; the Overview must not tell Fred to Resume."""
        boundary = ("t.state = 'waiting'; t.why = 'choose next step'; row.state = 'waiting'; row.paused_after = 1; "
                    "d.levers = {resume: 'choose a next step or finish the task', done: '', add_next: ''}; ")
        html = render(self.setup + boundary + "taskView = 'overview'; inspTask(t, d, row)")
        self.assertNotIn("Nothing starts until you Resume", html)
        paused = render(self.setup + "row.paused_after = 1; d.levers = {resume: ''}; taskView = 'overview'; inspTask(t, d, row)")
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
          taskView = 'overview'; inspTask(t, d, row)"""
        html = render(expr)
        self.assertEqual(html.count("Confirm plan"), 1)
        self.assertEqual(html.count("Keep old plan"), 1)
        self.assertIn("search", html)
        self.assertNotIn("Open step 2", html)

    def test_latest_result_skips_planned_and_running_steps(self):
        html = render(self.setup + "taskView = 'overview'; overviewBody(t, d, row)")
        self.assertIn("Latest result · step 01 chat", html)
        no_note = render(self.setup + "d.notes = {}; taskView = 'overview'; overviewBody(t, d, row)")
        self.assertNotIn("Latest result", no_note)
        failed = render(self.setup + """t.steps = [{n: 1, kind: 'code', state: 'done', goal: 'older'},
          {n: 2, kind: 'test', state: 'failed', goal: 'newer'}]; t.current = 2;
          d.notes = {'1': 'HANDOFF\\n## Goal\\nolder\\n## Next\\nn\\nEND HANDOFF', '2': 'HANDOFF\\n## Goal\\nnewer\\n## Next\\nn\\nEND HANDOFF'};
          taskView = 'overview'; overviewBody(t, d, row)""")
        self.assertIn("Latest result · step 02 test", failed)
        self.assertIn("failed", failed)

    def test_verify_is_inside_add_step_not_standalone(self):
        html = render(self.setup + "taskButtons(t, d)")
        self.assertEqual(html.count('data-tact="nextopen"'), 1)
        self.assertIn("Add step", html)
        self.assertNotIn("nextverify", html)
        self.assertNotIn(">Verify<", html)

    def test_question_and_confirm_share_one_attention_area(self):
        q = render(self.setup + "row.asks = 'Which step?'; taskView = 'overview'; inspTask(t, d, row)")
        self.assertEqual(q.count("task-attention"), 1)
        self.assertEqual(q.count("Which step?"), 1)  # never in a heading plus the composer
        c = render(self.setup + "t.state = 'waiting'; t.why = 'confirm Fable'; d.levers.confirm = ''; row.state = 'waiting'; taskView = 'overview'; inspTask(t, d, row)")
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
    """Plan 44 navigation T3: More > Hand off task opens a form in the Overview. Preview first; Save document and
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
          taskView = 'steps';
          await taskHandoff('handofftask', 't');
          const opened = [handoffDraft.t.open, taskView];
          handoffDraft.t.note = ' finish it ';
          await taskHandoff('handoffpreview', 't');
          const previewed = [handoffDraft.t.preview.revision, handoffDraft.t.preview.asked, /^[0-9a-f]{32}$/.test(handoffDraft.t.request)];
          await taskHandoff('handoffsave', 't');
          const saved = handoffDraft.t.saved;
          await taskHandoff('handoffcreate', 't');
          return {calls, opened, previewed, saved, after: [boardTask, boardPick, taskView, handoffDraft.t]};
        })()""")
        self.assertEqual(result["opened"], [True, "overview"])
        self.assertEqual(result["previewed"], ["r1", "finish it", True])
        self.assertTrue(result["saved"])
        paths = [c[0] for c in result["calls"]]
        self.assertEqual(paths, ["/api/task/handoff/preview", "/api/task/handoff", "/api/task/handoff", "/api/state"])
        self.assertEqual(result["calls"][0][1], {"task": "t", "note": "finish it"})
        save, create = result["calls"][1][1], result["calls"][2][1]
        self.assertEqual((save["create"], save["revision"], save["note"], save["task"]), (False, "r1", "finish it", "t"))
        self.assertEqual((create["create"], create["revision"], create["request_id"]), (True, "r1", save["request_id"]))
        self.assertRegex(create["request_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(result["after"][:3], ["new1", "t", "overview"])  # the follow-up's Overview opens
        self.assertIsNone(result["after"][3])  # the source's draft is gone

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
        html = render(self.setup + "handoffDraft.t = {open: true, note: ''}; taskView = 'overview'; inspTask(t, d, row)")
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
        why = render(self.setup + "snap.now = 100; headWhy({state: 'handed', handoff_note: 'task-handoff.md', handoff_to: 'f1', group: 'done', steps: []})")
        self.assertEqual(why[0], "handed off to follow-up")
        old = render(self.setup + "headWhy({state: 'handed', handoff_note: 'steps/01-handoff.md', group: 'needs', steps: []})")
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
        links = render(self.setup + "t.handoff_to = '0123456789abcdef4567'; overviewBody(t, d, row)")
        self.assertIn(">0123-4567</button>", links)

    def test_start_next_does_nothing_for_a_task_that_has_a_follow_up(self):
        result = render("""(async () => {
          snap = {now: 1, sessions: [], tasks: [{id: 't', handoff_to: 'f1', current: 1, steps: [{n: 1, session: 's'}]}], versions: {}, projects: []};
          let called = false; api = async () => { called = true; return {}; };
          await startNext('t', {disabled: false});
          return called;
        })()""")
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
