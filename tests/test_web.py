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

    def test_board_chat_shows_the_answer_prompt_for_a_question(self):
        setup = "snap = {sessions: [{id: 's', state: 'stop', run_live: false, stop_question: 'Shall I fix it?'}], tasks: []}; boardChat = {sid: 's', chat: {items: [], source: 'window'}};"
        html = render(setup + "chatTab({id: 't', chat: true, state: 'running'}, {n: 1, session: 's', state: 'running'}, {})")
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
        s += "nextDraft = {}; fuDraft = {}; "
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

    def test_add_next_step_disabled_carries_a_reason(self):
        html = render(self._setup() + "nextActions({id: 't', current: 1}, {n: 1, session: 's', state: 'done'}, {levers: {add_next: 'still working', done: 'x'}})")
        self.assertIn("Add next step", html)
        self.assertIn("still working", html)
        self.assertNotIn("Finish task", html)
        enabled = render(self._setup() + "nextActions({id: 't', current: 1}, {n: 1, session: 's', state: 'done'}, {levers: {add_next: '', done: ''}})")
        self.assertIn('data-tact="nextopen"', enabled)
        self.assertIn("Finish task", enabled)

    def test_historical_step_points_to_the_latest(self):
        html = render(self._setup() + "histFoot({id: 't', steps: [{n: 1}, {n: 2, session: 's2'}]}, {n: 1}, {})")
        self.assertIn("Go to step 02", html)

    def test_replied_chat_footer_offers_continue_and_next_step(self):
        snap = {"sessions": [{"id": "s", "state": "stop", "run_live": False}],
                "tasks": [], "versions": {}, "projects": []}
        html = render(self._setup(snap=snap) +
                      "stepFooter({id: 't', chat: true, state: 'running', current: 1, "
                      "steps: [{n: 1, session: 's', state: 'running', kind: 'chat'}]}, "
                      "{n: 1, session: 's', state: 'running', kind: 'chat'}, "
                      "{levers: {add_next: '', done: ''}, step_levers: {handoff: '', next: ''}}, null)")
        self.assertIn("Continue", html)
        self.assertIn('data-tact="cont"', html)
        self.assertNotIn("Add next step", html)  # plan 38 U3: in the dock bar, on every tab
        dock = render(self._setup(snap=snap) +
                      "stepButtons({id: 't', chat: true, state: 'running', current: 1, "
                      "steps: [{n: 1, session: 's', state: 'running', kind: 'chat'}]}, "
                      "{n: 1, session: 's', state: 'running', kind: 'chat'}, "
                      "{levers: {add_next: '', done: '', handoff: '', next: ''}}, null)")
        self.assertIn('class="btn sm go" data-tact="nextopen"', dock)
        self.assertIn("Finish task", dock)
        self.assertIn("Hand off", html)
        self.assertIn("Start new task", html)

    def test_task_page_dock_shows_each_action_only_where_the_service_allows_it(self):
        """Plan 39 Task 2: the task page's dock bar reads task_levers for Add next step, Finish task and Delete, and
        step_levers for Continue and Hand off; Add next step is the filled button, else Finish task."""
        snap = {"sessions": [{"id": "s2", "state": "idle", "run_live": False}], "tasks": [], "versions": {}, "projects": []}
        t = "{id: 't', current: 2, steps: [{n: 1, session: 's1', state: 'done', kind: 'scout'}, {n: 2, session: 's2', state: 'running', kind: 'chat'}]}"
        html = render(self._setup(snap=snap) + f"taskButtons({t}, {{levers: {{add_next: '', done: '', clear: ''}}, "
                      "step_levers: {continue: '', handoff: ''}, next_step: {source_step: 2}})")
        for text in ('class="btn sm go" data-tact="nextopen" data-tid="t" data-n="2"', 'data-tact="nextverify" data-tid="t" data-n="2"',
                     'data-tact="gochat" data-tid="t" data-n="2"', 'data-tact="done"', 'data-tact="handoff"', 'data-tact="clear"'):
            self.assertIn(text, html)
        self.assertLess(html.index("Add next step"), html.index("Finish task"))
        self.assertLess(html.index("Finish task"), html.index("Delete"))
        off = render(self._setup(snap=snap) + f"taskButtons({t}, {{levers: {{add_next: 'task is stuck', done: '', clear: 'task is stuck'}}, "
                     "step_levers: {continue: 'still working', handoff: 'still working'}})")
        self.assertIn('disabled title="task is stuck">Add next step', off)
        self.assertIn('class="btn sm go" data-tact="done"', off)  # the primary falls to Finish task
        for text in ("Verify", "Continue", "Hand off", "Delete"):
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

    def test_hand_off_and_start_new_task_read_the_step_levers(self):
        """Plan 39 Task 2 (plan 36 Task 3 slip): the Board's levers are task_levers, which never carry handoff or next."""
        html = render(self._setup() + "nextSecondary({id: 't'}, {levers: {handoff: '', next: ''}, step_levers: {handoff: 'x', next: 'y'}})")
        self.assertEqual(html, "")
        html = render(self._setup() + "nextSecondary({id: 't'}, {levers: {}, step_levers: {handoff: '', next: ''}})")
        self.assertIn("Hand off", html)
        self.assertIn("Start new task", html)

    def test_older_done_step_offers_a_branch_where_the_service_allows_it(self):
        """Plan 39 Task 3: the dock of an older step reads sources[NN]; the Board reproduces no rule of its own."""
        t = "{id: 't', current: 3, steps: [{n: 1, session: 's1', state: 'done'}, {n: 2, session: 's2', state: 'done'}, {n: 3, session: 's3', state: 'done'}]}"
        ok = render(self._setup() + f"nextActions({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{add_next: '', done: ''}}, sources: {{'01': '', '02': '', '03': ''}}}})")
        self.assertIn('class="btn sm go" data-tact="nextopen" data-tid="t" data-n="2"', ok)
        self.assertIn("Add step from here", ok)
        self.assertIn('data-tact="nextverify" data-tid="t" data-n="2"', ok)
        self.assertIn("Verify this step", ok)
        self.assertNotIn("Finish task", ok)  # the task's own actions stay on the task page and the latest step
        off = render(self._setup() + f"nextActions({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{add_next: ''}}, sources: {{'02': 'no saved note or final reply'}}}})")
        self.assertIn('disabled title="no saved note or final reply">Add step from here', off)
        self.assertNotIn("Verify this step", off)
        self.assertEqual(render(self._setup() + f"nextActions({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{}}}})"), "")
        latest = render(self._setup() + f"nextActions({t}, {{n: 3, session: 's3', state: 'done'}}, {{levers: {{add_next: '', done: ''}}, sources: {{'03': ''}}}})")
        self.assertIn("Add next step", latest)
        self.assertIn("Finish task", latest)
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
        self.assertIn("Add next step is available when this turn finishes", html)
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

    def test_a_reseed_shows_in_the_open_field(self):
        """Plan 36 Task 4 (headless pass): setHtml keeps a field's typed value over a redraw, so a Work switch
        writes the reseeded instructions into the open field as well as the draft."""
        out = render("(() => { const f = {value: 'Go on'}; document = {getElementById: (id) => id === 'b-ninstr' ? f : null}; "
                     "const d = {instr: 'Go on'}; setInstr(d, verifyDefault(1)); return [d.instr === verifyDefault(1), f.value === verifyDefault(1)]; })()")
        self.assertEqual(out, [True, True])


if __name__ == "__main__":
    unittest.main()
