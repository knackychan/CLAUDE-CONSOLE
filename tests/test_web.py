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
        out = render(f"nextSeed({{steps: [{{n: 1}}]}}, {{notes: {notes}}}, {{n: 2}})")
        self.assertEqual(out, "write the tests first")

    def test_a_none_next_section_seeds_blank(self):
        notes = json.dumps({"1": "HANDOFF\n## Next\n(none)\nEND HANDOFF"})
        self.assertEqual(render(f"nextSeed({{steps: [{{n: 1}}]}}, {{notes: {notes}}}, {{n: 2}})"), "")

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
        html = render(self._setup() + "nextActions({id: 't'}, {levers: {add_next: 'still working', done: 'x'}})")
        self.assertIn("Add next step", html)
        self.assertIn("still working", html)
        self.assertNotIn("Finish task", html)
        enabled = render(self._setup() + "nextActions({id: 't'}, {levers: {add_next: '', done: ''}})")
        self.assertIn('data-tact="nextopen"', enabled)
        self.assertIn("Finish task", enabled)

    def test_historical_step_points_to_the_latest(self):
        html = render(self._setup() + "histFoot({id: 't', steps: [{n: 1}, {n: 2, session: 's2'}]}, {n: 1}, {})")
        self.assertIn("Next steps start from the latest step", html)
        self.assertIn("Go to step 02", html)

    def test_replied_chat_footer_offers_continue_and_next_step(self):
        snap = {"sessions": [{"id": "s", "state": "stop", "run_live": False}],
                "tasks": [], "versions": {}, "projects": []}
        html = render(self._setup(snap=snap) +
                      "stepFooter({id: 't', chat: true, state: 'running', current: 1, "
                      "steps: [{n: 1, session: 's', state: 'running', kind: 'chat'}]}, "
                      "{n: 1, session: 's', state: 'running', kind: 'chat'}, "
                      "{levers: {add_next: '', done: '', handoff: '', next: ''}}, null)")
        self.assertIn("Continue", html)
        self.assertIn('data-tact="cont"', html)
        self.assertIn("Add next step", html)
        self.assertIn("Finish task", html)
        self.assertIn("Hand off", html)
        self.assertIn("Start new task", html)

    def test_live_turn_explains_next_step_is_unavailable(self):
        snap = {"sessions": [{"id": "s", "state": "running", "run_live": True}],
                "tasks": [], "versions": {}, "projects": []}
        html = render(self._setup(snap=snap) +
                      "stepFooter({id: 't', chat: true, state: 'running', current: 1, "
                      "steps: [{n: 1, session: 's', state: 'running', kind: 'chat'}]}, "
                      "{n: 1, session: 's', state: 'running', kind: 'chat'}, {}, null)")
        self.assertIn("Add next step is available when this turn finishes", html)
        self.assertNotIn("Continue", html)


if __name__ == "__main__":
    unittest.main()
