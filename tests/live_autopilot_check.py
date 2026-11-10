"""Headless acceptance of plan 52 (Task 7): py -m tests.live_autopilot_check [check numbers].

Real HTTP service on a scratch CC_CONSOLE_HOME with the fake claude (no provider, never the running service), the real
page in the installed Playwright and Edge, headless. Seven checks, each on its own service:

  1 gated chain: Enter, Start, one Confirm, code, verify PASS, done, finish summary, Accept, one supervisor pass
  2 auto: a DECISION card, a fake clock past decision_timeout_s, the default taken, logged, joined to plan.md
  3 a step crashes twice: the chain retry, stuck, one sonnet wake, a Retry card with a note, Approve runs attempt 3
  4 a task started at suggest, switched to auto at a plan hold: the standing card dispatches, no Paused note
  5 900 / 400 / 340 px, dark and light, reduced motion over the states of check 7: no horizontal scroll, no page error
  6 the Models page Supervisor card and the task menu: off, suggest, gated, auto, gated the default
  7 GET /api/task `actions` at every state (README 52 section 3), read only (the task folder is unchanged)

Today's page has no control for Accept, the decision options or the supervisor card's Approve (plan 52's UI is a later
plan), so those steps call the route and body that `actions` names, as the later page will. Everything else a check
does through the page is what today's page has: the composer, the Prep card's Start, Confirm plan, the task menu.
The supervisor clock is a fake (Hub.sup_clock) and so is the decision timeout's `now`; production code has no seam.
"""
import contextlib
import http.client
import json
import re
import sys
import threading
import time
import traceback
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from console import paths, plan, supervisor, tasks
from tests.test_server import TaskServerTest

WIDTHS = (900, 400, 340)
WORDS = "HANDOFF-OK PLAN-OK VERDICT-PASS"  # what the fake worker needs in a step's prompt to behave
MODES = ["off", "suggest", "gated", "auto"]
FIELDS = {"id", "label", "post", "body", "off", "confirm"}
NOISE = ("/api/draft", "/api/window")  # the page saves its own state; not a click of Fred's
DOT = "·"


def S(kind, goal=None):
    return {"kind": kind, "goal": goal or f"do {kind}"}


class Rig:
    """One scratch service (the TaskServerTest fixture), a worker thread that ticks the hub as the hub loop would,
    a frozen supervisor clock and one page."""

    def __init__(self, browser, width=900):
        self.closed = False
        self.fx = TaskServerTest()
        self.fx.setUp()
        self.hub, self.folder = self.fx.hub, self.fx.folder
        quiet = self.fx.httpd.handle_error

        def handle_error(request, client_address):  # the page left mid-response (it navigated or closed): not a finding
            if not isinstance(sys.exception(), (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
                quiet(request, client_address)

        self.fx.httpd.handle_error = handle_error
        self.clock = [0.0]
        self.hub.sup_clock = lambda: self.clock[0]
        self.clicks, self.page_errors, self.worker_errors, self.probed = [], [], [], set()
        self.gate, self.stop = threading.Lock(), threading.Event()
        self.worker = threading.Thread(target=self._tick, daemon=True)
        self.worker.start()
        self.page = browser.new_page(viewport={"width": width, "height": 900})
        self.page.on("pageerror", lambda e: self.page_errors.append("pageerror: " + str(e)))
        self.page.on("console", self._console)
        self.page.on("request", self._request)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _tick(self):
        while not self.stop.wait(0.1):
            with self.gate:
                try:
                    self.hub.poll_once()
                    self.hub.advance()
                except Exception as exc:  # a broken tick is a finding, not a silent dead thread
                    self.worker_errors.append(f"{type(exc).__name__}: {exc}")

    def _console(self, msg):
        if msg.type == "error" and not (msg.location or {}).get("url", "").endswith("favicon.ico"):
            self.page_errors.append("console error: " + msg.text)

    def _request(self, req):
        if req.method == "POST":
            self.clicks.append(urlparse(req.url).path)

    def close(self):
        if self.closed:
            return
        self.closed = True
        with contextlib.suppress(Exception):
            self.page.goto("about:blank")  # the page's streams end here, not as aborted requests at shutdown
            self.page.wait_for_timeout(300)
        self.stop.set()
        if self.worker.is_alive():
            self.worker.join(5)
        with contextlib.suppress(Exception):
            self.page.close()
        self.fx.tearDown()
        self.fx.doCleanups()

    # -- the service ----------------------------------------------------------------------------------------------

    def call(self, path, body=None):
        if body is not None:
            self.clicks.append(path)
        return self.fx.call(path, body)

    def get(self, tid):
        code, data = self.fx.call(f"/api/task?id={tid}")
        assert code == 200, (code, data)
        return data

    def prep(self, text="CHAIN fix add"):
        code, data = self.call("/api/prep", {"project_dir": str(self.fx.project), "prompt": text})
        assert code == 200, (code, data)
        row = self.fx.prep_job(data["job"])
        assert row and row["state"] == "done", row
        return row["card"]

    def start(self, words, steps, text="CHAIN fix add", mode=None):
        """POST /api/task with the body the Prep card's Start posts (supervised: true)."""
        card = self.prep(text)
        body = {"prep": card["id"], "prompt": f"{card['prompt']}\n{words}".strip(), "steps": steps,
                "effort": "auto", "supervised": True}
        if mode:
            body["supervisor_mode"] = mode
        code, data = self.call("/api/task", body)
        assert code == 200, (code, data)
        return data["task"]

    @staticmethod
    def find(actions, action_id):
        return next((a for place in ("primary", "bar", "menu") for a in actions[place] if a["id"] == action_id), None)

    def act(self, tid, action_id):
        """Call the route and body that GET /api/task `actions` names for `action_id`, as the later page will."""
        actions = self.get(tid)["actions"]
        found = self.find(actions, action_id)
        assert found, f"no action {action_id} in {[a['id'] for p in ('primary', 'bar', 'menu') for a in actions[p]]}"
        assert found["post"], f"{action_id} opens a form, it posts nothing"
        assert not found["off"], f"{action_id} is off: {found['off']}"
        return self.call(found["post"], found["body"])

    def bump(self, seconds=100.0):
        self.clock[0] += seconds

    def log(self, tid):
        return supervisor.read_log(self.folder, tid)

    def settle(self, tid, n=1, seconds=40):
        """Wait until n supervisor passes have a result record and no pass is running."""
        end = time.time() + seconds
        while time.time() < end:
            done = [r for r in self.log(tid) if r.get("phase") == "result"]
            if len(done) >= n and not self.hub.supervising:
                return done
            time.sleep(0.1)
        raise AssertionError(f"{n} supervisor passes did not settle: {self.log(tid)}")

    def row(self, tid):
        return next(t for t in self.hub.snapshot()["tasks"] if t["id"] == tid)

    def tree(self, tid):
        base = self.folder / "tasks" / tid
        return {str(p.relative_to(base)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(base.rglob("*")) if p.is_file()}

    @contextlib.contextmanager
    def frozen(self):
        """The worker waits, and no brief or supervisor thread is running: nothing but this check touches the disk."""
        with self.gate:
            end = time.time() + 30
            while (self.hub.supervising or self.hub.briefing) and time.time() < end:
                time.sleep(0.05)
            assert not self.hub.supervising and not self.hub.briefing, "a brief or a pass never finished"
            yield

    def route_exists(self, path):
        """An unknown path answers plain text 404; a known route answers JSON for a body it refuses."""
        if path in self.probed:
            return True
        conn = http.client.HTTPConnection("127.0.0.1", self.fx.port, timeout=30)
        conn.request("POST", path, body=b"{}", headers={"Host": f"127.0.0.1:{self.fx.port}", "X-CC": "1",
                                                        "Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        ok = "json" in (resp.getheader("Content-Type") or "")
        if ok:
            self.probed.add(path)
        return ok

    # -- the page -------------------------------------------------------------------------------------------------

    def load(self):
        self.page.goto(f"http://127.0.0.1:{self.fx.port}/")
        self.page.wait_for_function("snap && cfg && cfg.supervisor_config")

    def says(self, tid):
        """The status line today's page draws for the task (its own statusLine)."""
        return self.page.evaluate(
            "id => { const t = snap.tasks.find((x) => x.id === id); return t ? statusLine(t)[0] : null; }", tid)

    def wait_says(self, tid, needle, seconds=20):
        end, text = time.time() + seconds, None
        while time.time() < end:
            text = self.says(tid)
            if text and needle in text:
                return text
            time.sleep(0.2)
        raise AssertionError(f"the page row never said {needle!r}; it says {text!r}")

    def open(self, tid):
        self.page.evaluate("id => openTask(id)", tid)
        self.page.wait_for_function("id => boardData?.id === id && boardData.data && boardData.data.task", arg=tid)
        self.page.wait_for_timeout(100)

    def fits(self):
        return self.page.evaluate(
            "document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth")

    def assert_clean(self):
        assert not self.page_errors, self.page_errors
        assert not self.worker_errors, self.worker_errors


class Ctx:
    def __init__(self, browser):
        self.browser, self.shared, self.rigs = browser, {}, []

    def rig(self):
        rig = Rig(self.browser)
        self.rigs.append(rig)
        return rig

    def close(self):
        for rig in reversed(self.rigs):  # last opened, first closed: each one's CC_CONSOLE_HOME patch is restored in order
            rig.close()


# -- 1 -------------------------------------------------------------------------------------------------------------

def check_gated_chain(ctx):
    with ctx.rig() as rig:
        hub, fx, page = rig.hub, rig.fx, rig.page
        hub.cfg["supervisor_mode"] = "gated"
        rig.load()
        # Moment 1: type a prompt, Enter. Prep and the planner run; the row says ready.
        page.fill("#c-prompt", "CHAIN PLANNER-DESIGN fix add")
        page.press("#c-prompt", "Enter")
        page.wait_for_function("snap.preps.length === 1 && snap.preps[0].state === 'done'", timeout=60000)
        tid = page.evaluate("snap.preps[0].id")
        ready = page.locator(f'.v-th[data-btask="{tid}"] .why')
        ready.wait_for()
        assert ready.inner_text() == f"ready {DOT} 4 steps {DOT} Start", ready.inner_text()  # scout, design, code and the verify
        # Moment 2: the card and its one Start (the enhanced prompt gets the fake worker's words).
        page.locator(f'.v-th[data-btask="{tid}"]').click()
        page.locator('#pscroll .fh[data-fkey="prep.edit"]').click()  # Edit steps: the enhanced prompt is behind it
        prompt = page.locator("#p-prompt")
        prompt.wait_for()
        prompt.fill(prompt.input_value() + "\n" + WORDS)
        page.locator('#pbar [data-pact="start"]').click()
        page.wait_for_function("id => snap.tasks.some((t) => t.id === id)", arg=tid)
        task = fx.until(tid, lambda t: t["state"] == "waiting" and not t.get("briefing"), "the plan hold", 90)
        assert task["why"] == "plan ready: confirm", task["why"]
        assert task["supervisor"]["mode"] == "gated"
        assert [(s["kind"], s["state"]) for s in task["steps"]] == [
            ("scout", "done"), ("design", "done"), ("code", "planned"), ("verify", "planned")]
        assert rig.log(tid) == [], "a pass ran between two good steps"
        rig.wait_says(tid, "plan ready: confirm")
        # Moment 3: one Confirm on the opened task, then nothing of Fred's until the finish.
        rig.open(tid)
        confirm = page.locator('.p-card [data-aid="confirm"]')
        confirm.wait_for()
        assert rig.find(rig.get(tid)["actions"], "confirm")["post"] == "/api/task/confirm"
        confirm.click()
        fx.until(tid, lambda t: any(s["n"] == 3 and s["state"] in ("running", "done") for s in t["steps"]),
                 "code starts after the Confirm", 30)
        rig.bump()  # the hold's debounced wake is stale now: it must drop with no pass
        end = time.time() + 10
        while tid in hub.wakes and time.time() < end:
            time.sleep(0.1)
        assert tid not in hub.wakes and rig.log(tid) == [], ("the stale hold wake ran or stayed", rig.log(tid))
        task = fx.until(tid, lambda t: t["state"] == "done" and not t.get("briefing"), "the chain ends", 120)
        assert [(s["kind"], s["state"]) for s in task["steps"]] == [
            ("scout", "done"), ("design", "done"), ("code", "done"), ("verify", "done")]
        assert task["steps"][3]["verdict"] == "PASS"
        assert task["plan"]["from"] == 2
        assert fx.whys(tid).count("plan confirmed by Fred") == 1
        data = rig.get(tid)
        summary = data["summary"]
        assert [s["kind"] for s in summary["steps"]] == ["scout", "design", "code", "verify"], summary
        assert summary["steps"][3]["verdict"] == "PASS" and isinstance(summary["files"], list)
        assert summary["cost"] > 0 and not summary["accepted"]
        assert re.fullmatch(r"done · 4 steps · \$\d+\.\d\d", data["actions"]["line"]), data["actions"]["line"]
        rig.wait_says(tid, f"done {DOT} 4 steps")
        assert rig.log(tid) == [], "a pass ran before the done wake"
        # The one supervisor pass: the done wake, after the final brief.
        rig.bump()
        passes = rig.settle(tid, 1)
        log = rig.log(tid)
        assert [r["phase"] for r in log] == ["claimed", "result"], log
        assert log[0]["triggers"] == ["done"] and log[0]["model"] == "haiku", log[0]
        assert passes[0]["status"] == "wait", passes[0]
        # Accept moves it to Done (the later page's button posts exactly this).
        code, body = rig.act(tid, "accept")
        assert code == 200, body
        data = rig.get(tid)
        assert data["summary"]["accepted"] > 0
        assert rig.find(data["actions"], "accept")["off"] == "already accepted"
        assert rig.row(tid)["group"] == "done" and rig.row(tid)["accepted"] is True
        rig.bump()
        time.sleep(0.6)  # a few ticks: no second pass
        assert [r["phase"] for r in rig.log(tid)] == ["claimed", "result"], rig.log(tid)
        assert tasks.load(rig.folder, tid)["supervisor"]["wakes"] == 1
        clicks = [c for c in rig.clicks if c not in NOISE]
        assert clicks == ["/api/prep", "/api/task", "/api/task/confirm", "/api/task/accept"], clicks
        assert rig.fits()
        rig.assert_clean()


# -- 2 -------------------------------------------------------------------------------------------------------------

def check_auto_decision(ctx):
    with ctx.rig() as rig:
        hub, fx = rig.hub, rig.fx
        hub.cfg["supervisor_mode"] = "auto"
        rig.load()
        tid = rig.start(WORDS, [S("scout", "look"), S("design", "plan it"), S("code", "write it DECIDE-NAME")])
        task = fx.until(tid, lambda t: t["state"] == "waiting" and t["why"].startswith("asks: "), "the decision waits", 90)
        assert task["why"] == "asks: Which name?" and task["supervisor"]["mode"] == "auto", task["why"]
        assert task["steps"][1]["state"] == "done" and hub.cfg["supervisor_mode"] == "auto"
        data = rig.get(tid)
        decision = data["task"]["decision"]
        assert [(o["key"], o["text"]) for o in decision["options"]] == [("a", "SHEETS_DIR"), ("b", "PRODUCT_SHEETS_DIR")]
        assert decision["default"] == "a"
        actions = data["actions"]
        assert actions["state"] == "decision" and actions["line"] == f"needs you {DOT} Which name?", actions["line"]
        assert [a["id"] for a in actions["primary"]] == ["a", "b"], actions["primary"]  # auto: no "take defaults from now on"
        assert rig.row(tid)["decision"]["options"] == decision["options"]
        rig.wait_says(tid, f"needs you {DOT} Which name?")
        rig.open(tid)
        assert rig.page.evaluate("boardData.data.actions.state") == "decision"
        timeout, asked = hub.cfg["decision_timeout_s"], decision["asked"]
        assert timeout == 600
        sid = tasks.current_step(task)["session"]
        with hub.tlock:  # the fake clock: Hub._decision_default takes `now`, as the Task 3 tests call it
            assert hub._decision_default(task, asked + timeout - 1) is False
            assert "taken" not in task["decision"]
            assert hub._decision_default(task, asked + timeout + 1) is True
            saved = tasks.load(rig.folder, tid)
            whys = fx.whys(tid)
            plan_text = plan.read(rig.folder, task)
        assert saved["decision"]["taken"] == "default", saved["decision"]
        assert "decision taken by default: a) SHEETS_DIR" in whys and whys.count("decision taken by default: a) SHEETS_DIR") == 1
        decisions = plan.section(plan_text, "## Decisions")
        assert "Which name?: SHEETS_DIR" in decisions and "- Default," in decisions, decisions
        fx.wait_idle(sid)
        said = [i for i in fx.call(f"/api/chat?session={sid}")[1]["items"] if i["role"] == "you"]
        assert any(i["text"].startswith("SHEETS_DIR") for i in said), said  # the default went into the same session
        rig.assert_clean()


# -- 3 -------------------------------------------------------------------------------------------------------------

def check_crash_retry(ctx):
    with ctx.rig() as rig:
        hub, fx = rig.hub, rig.fx
        hub.cfg["supervisor_mode"] = "suggest"
        rig.load()
        tid = rig.start(WORDS, [S("scout", "look"), S("design", "plan it"), S("code", "write it SLOW SUP-RETRY")])
        task = fx.until(tid, fx.at(2), "the design step runs", 90)  # it reads step 3's goal, so it waits for EOF too
        hub.runs.live[task["steps"][1]["session"]].stdin.close()
        task = fx.until(tid, fx.at(3), "step 3 runs", 90)
        first = task["steps"][2]["session"]
        hub.runs.live[first].kill()  # the first crash
        task = fx.until(tid, lambda t: t["steps"][2]["retries"] == 1 and t["steps"][2]["state"] == "running"
                        and t["steps"][2]["session"] != first, "the chain retries step 3", 60)
        second = task["steps"][2]["session"]
        assert tid not in hub.wakes and rig.log(tid) == [], "the chain's own retry woke the supervisor"
        hub.runs.live[second].kill()  # the second crash
        task = fx.until(tid, lambda t: t["state"] == "stuck", "step 3 sticks after the second crash", 60)
        assert task["why"].endswith("(after one retry)"), task["why"]
        assert len(task["steps"][2]["attempts"]) == 2
        assert hub.wakes[tid]["triggers"] == ["stuck"] and rig.log(tid) == []
        rig.wait_says(tid, "failed")
        # One sonnet wake, a Retry card with a note.
        rig.bump()
        passes = rig.settle(tid, 1)
        log = rig.log(tid)
        claimed = [r for r in log if r["phase"] == "claimed"]
        assert len(claimed) == 1 and claimed[0]["triggers"] == ["stuck"] and claimed[0]["model"] == "sonnet", claimed
        decision = passes[0]["decision"]
        assert decision["decision"] == "retry" and "Start the step again" in decision["note"], decision
        data = rig.get(tid)
        actions = data["actions"]
        assert actions["state"] == "suggestion" and [a["id"] for a in actions["primary"]] == ["approve"], actions
        approve = actions["primary"][0]
        assert approve["post"] == "/api/task/supervisor" and approve["off"] == ""
        assert approve["body"] == {"task": tid, "wake": 1, "action": "approve"}, approve["body"]
        rig.wait_says(tid, f"needs you {DOT} retry")
        assert hub.tasks[tid]["state"] == "stuck", "the card waits for Approve"
        # Approve runs attempt 3, carrying the note.
        code, body = rig.act(tid, "approve")
        assert code == 200, body
        task = fx.until(tid, lambda t: len(t["steps"][2]["attempts"]) == 3 and t["steps"][2]["state"] == "running",
                        "attempt 3 runs", 30)
        third = task["steps"][2]["session"]
        assert third not in (first, second)
        assert decision["note"] in fx.full_prompt(third), "the supervisor's note is not in attempt 3's prompt"
        outcome = [r for r in rig.log(tid) if r.get("phase") == "outcome"]
        assert [(r["status"], r["by"]) for r in outcome] == [("dispatched", "fred")], outcome
        hub.runs.live[third].stdin.close()  # attempt 3 ends normally (the fake worker waits for EOF)
        task = fx.until(tid, lambda t: t["state"] == "done" and not t.get("briefing"), "the chain ends", 90)
        assert task["steps"][3]["verdict"] == "PASS"
        assert len([r for r in rig.log(tid) if r["phase"] == "claimed"]) == 1
        rig.assert_clean()


# -- 4 -------------------------------------------------------------------------------------------------------------

def check_mode_switch(ctx):
    with ctx.rig() as rig:
        hub, fx, page = rig.hub, rig.fx, rig.page
        hub.cfg.update(supervisor_mode="suggest", plan_hold=True)
        rig.load()
        tid = rig.start(WORDS, [S("scout", "look"), S("design", "plan it"), S("code", "write it SUP-CONFIRM")])
        task = fx.until(tid, lambda t: t["state"] == "waiting" and not t.get("briefing"), "the plan hold", 90)
        assert task["why"] == "plan ready: confirm" and task["supervisor"]["mode"] == "suggest"
        rig.bump()
        rig.settle(tid, 1)
        pending = task["supervisor"]["pending"]
        assert pending["status"] == "suggest" and pending["decision"]["decision"] == "confirm", pending
        assert task["why"] == "plan ready: confirm" and task["steps"][2]["state"] == "planned"
        assert rig.row(tid)["paused_after"] == 0 and rig.row(tid)["supervisor"]["attention"] is True
        rig.open(tid)
        assert "Nothing starts until you Resume" not in page.locator("#bwrap").inner_text()
        code, body = rig.act(tid, "level_auto")
        assert code == 200 and body == {"task": tid, "mode": "auto"}, (code, body)
        fx.until(tid, fx.at(3), "the standing card dispatches the Confirm", 30)
        whys = fx.whys(tid)
        assert "supervisor mode: suggest -> auto by Fred" in whys, whys
        assert any(w.startswith("supervisor: dispatched confirm") and "by auto" in w for w in whys), whys
        assert any(w.startswith("plan confirmed") for w in whys), whys
        log = rig.log(tid)
        assert "superseded" not in [r.get("status") for r in log], log
        assert [r["phase"] for r in log] == ["claimed", "result", "dispatching", "outcome"], log
        assert (log[-1]["status"], log[-1]["by"]) == ("dispatched", "auto"), log[-1]
        assert hub.tasks[tid]["supervisor"]["mode"] == "auto" and hub.tasks[tid]["supervisor"]["pending"] is None
        assert rig.row(tid)["paused_after"] == 0
        rig.open(tid)
        assert "Nothing starts until you Resume" not in page.locator("#bwrap").inner_text()
        task = fx.until(tid, lambda t: t["state"] == "done" and not t.get("briefing"), "the chain ends", 90)
        assert task["steps"][3]["verdict"] == "PASS"
        assert len([r for r in rig.log(tid) if r["phase"] == "claimed"]) == 1, "the switch woke the model again"
        rig.assert_clean()


# -- 6 -------------------------------------------------------------------------------------------------------------

def inside(box, outer):
    return box["x"] >= outer["x"] - 1 and box["x"] + box["width"] <= outer["x"] + outer["width"] + 1


def check_models_card(ctx):
    with ctx.rig() as rig:
        hub, fx, page = rig.hub, rig.fx, rig.page
        assert paths.DEFAULTS["supervisor_mode"] == "gated"
        hub.cfg["supervisor_mode"] = paths.DEFAULTS["supervisor_mode"]
        code, config = fx.call("/api/config")
        sc = config["supervisor_config"]
        assert code == 200 and (sc["modes"], sc["mode"], sc["projects"]) == (MODES, "gated", {}), sc
        tid = rig.start("HANDOFF-OK SLOW", [S("scout", "look")])  # a running task for the task menu
        rig.load()
        page.evaluate("showPage('models')")
        page.locator('#mtabs [data-mtab="tuning"]').click()
        seg = page.locator('#mscroll .seg[aria-label="Supervisor mode"] button')
        seg.first.wait_for()
        assert seg.all_inner_texts() == MODES, seg.all_inner_texts()
        assert [b.get_attribute("aria-pressed") for b in seg.all()] == ["false", "false", "true", "false"]
        assert "default gated" in page.locator("#mscroll").inner_text()
        assert page.locator('#mscroll [data-msup="mode:gated"].rs').count() == 0  # gated is the default: no reset link
        for width in WIDTHS:
            for scheme in ("dark", "light"):
                page.set_viewport_size({"width": width, "height": 760})
                page.emulate_media(color_scheme=scheme, reduced_motion="reduce")
                page.wait_for_timeout(100)
                outer = page.locator("#mscroll").bounding_box()
                for button in seg.all():
                    box = button.bounding_box()
                    assert box and inside(box, outer) and box["x"] >= 0 and box["x"] + box["width"] <= width, (width, scheme, box, outer)
                assert rig.fits(), (width, scheme)
        # The same four words on the opened task's menu, the task at its mode.
        page.set_viewport_size({"width": 900, "height": 760})
        rig.open(tid)
        mode = rig.get(tid)["task"]["supervisor"]["mode"]
        assert mode == "gated", mode
        for width in WIDTHS:
            for scheme in ("dark", "light"):
                page.set_viewport_size({"width": width, "height": 760})
                page.emulate_media(color_scheme=scheme, reduced_motion="reduce")
                buttons = page.locator('.p-seg [data-aid^="level_"]')
                buttons.first.wait_for()
                assert buttons.all_inner_texts() == ["gated", "auto"]
                assert [b.get_attribute("aria-pressed") for b in buttons.all()] == ["true", "false"]
                for button in buttons.all():
                    box = button.bounding_box()
                    assert box and box["x"] >= 0 and box["x"] + box["width"] <= width, (width, scheme, box)
                assert rig.fits(), (width, scheme)
        rig.assert_clean()


# -- 7 and 5 -------------------------------------------------------------------------------------------------------

POSTS = {"/api/task/stop", "/api/task/pause", "/api/task/resume", "/api/task/retry", "/api/task/stepdone",
         "/api/task/confirm", "/api/task/clear", "/api/task/done", "/api/task/accept", "/api/task/redo",
         "/api/task/keep", "/api/task/message", "/api/task/supervisor", "/api/task/folder", "/api/terminal",
         "/api/continue", "/api/verify", "/api/handoff", "/api/escalate", ""}


def contract(rig, tid, data):
    """README 52 section 3, the parts every state shares."""
    actions = data["actions"]
    assert {"state", "line", "primary", "bar", "menu", "message"} <= set(actions), set(actions)
    assert actions["message"] == data["message"] and actions["line"]
    ids = []
    for place in ("primary", "bar", "menu"):
        for a in actions[place]:
            assert set(a) == FIELDS, a
            assert isinstance(a["off"], str) and isinstance(a["confirm"], bool) and isinstance(a["body"], dict), a
            assert a["post"] in POSTS, a
            if a["post"]:
                assert rig.route_exists(a["post"]), f"{a['post']} is not a route"
                if a["post"].startswith("/api/task/"):
                    assert a["body"]["task"] == tid, a
            if a["id"] in ("stop", "finish", "delete"):
                assert a["confirm"] is True, a
            ids.append(a["id"])
    assert len(ids) == len(set(ids)), ids
    if actions["state"] in ("running", "plan_ready", "decision"):  # the level menu: four words, one route
        levels = [a for a in actions["menu"] if a["id"].startswith("level_")]
        assert [a["id"] for a in levels] == ["level_" + m for m in MODES], levels
        assert all(a["post"] == "/api/task/supervisor" and a["body"] == {"task": tid, "mode": a["id"][6:]} for a in levels)
    if "recovery" in actions:
        assert actions["recovery"] == data["recovery"]
    return {p: [a["id"] for a in actions[p]] for p in ("primary", "bar", "menu")}


def expect(name, data, tid, ids):
    actions = data["actions"]
    line, state = actions["line"], actions["state"]
    if name in ("planning", "running"):
        assert state == "running" and ids["primary"] == [] and ids["bar"] == ["stop", "pause"], (state, ids)
        kind = "02 design" if name == "planning" else "03 code"
        assert re.fullmatch(rf"running · {kind} · \S+ · \d+[sm]", line), line
        assert {"handoff", "retry", "terminal", "folder", "delete"} <= set(ids["menu"]), ids
    elif name == "plan_ready":
        assert state == "plan_ready" and line == f"plan ready {DOT} confirm", (state, line)
        assert ids["primary"] == ["confirm", "confirm_auto"] and ids["bar"] == ["edit_plan", "redo", "stop"], ids
        confirm = Rig.find(actions, "confirm")
        assert (confirm["post"], confirm["body"], confirm["off"]) == ("/api/task/confirm", {"task": tid}, ""), confirm
        auto = Rig.find(actions, "confirm_auto")
        assert auto["label"] == "Confirm, and run plans automatically from now on", auto
        assert (auto["post"], auto["body"]) == ("/api/task/confirm", {"task": tid, "remember": "auto"}), auto
    elif name == "decision":
        assert state == "decision" and line == f"needs you {DOT} Which name?", (state, line)
        assert ids["primary"] == ["a", "b", "default_auto"] and ids["bar"] == ["stop"], ids
        text = {o["key"]: o["text"] for o in data["task"]["decision"]["options"]}
        for key in ("a", "b"):
            a = Rig.find(actions, key)
            assert a["post"] == "/api/task/message" and a["off"] == "", a
            assert a["body"]["mode"] == "answer" and a["body"]["text"] == text[key], a
            assert a["body"]["target"] == data["message"]["target"], a
            assert re.fullmatch(r"[0-9a-f-]{36}", a["body"]["request_id"]), a
        default = Rig.find(actions, "default_auto")
        assert default["label"] == "Take the default from now on" and default["body"]["remember"] == "auto", default
        assert default["body"]["text"] == text["a"] and default["post"] == "/api/task/message", default
    elif name == "stuck":
        assert state == "stuck" and line.startswith(f"stuck {DOT} "), (state, line)
        assert ids["primary"] == ["retry"] and ids["bar"] == ["stepdone", "finish"], ids
        retry = Rig.find(actions, "retry")
        assert retry["post"] == "" and retry["body"] == {"task": tid} and retry["off"] == "", retry
        assert data["recovery"] is not None and actions["recovery"]["cut"] is not None
    elif name == "suggestion":
        assert state == "suggestion" and line.startswith(f"needs you {DOT} retry: "), (state, line)
        assert ids["primary"] == ["approve"] and ids["bar"][0] == "reject", ids
        pending = data["supervisor"]["pending"]
        for a in (Rig.find(actions, "approve"), Rig.find(actions, "reject")):
            assert a["post"] == "/api/task/supervisor" and a["body"]["wake"] == pending["wake"], a
        assert Rig.find(actions, "approve")["body"]["action"] == "approve"
        assert Rig.find(actions, "reject")["body"]["action"] == "reject"
    elif name in ("done", "accepted"):
        assert state == "done" and re.fullmatch(r"done · 4 steps · \$\d+\.\d\d", line), (state, line)
        assert ids["primary"] == ["accept"] and ids["bar"] == ["reopen"], ids
        assert {"handoff", "folder", "delete"} <= set(ids["menu"]), ids
        accept = Rig.find(actions, "accept")
        assert (accept["post"], accept["body"]) == ("/api/task/accept", {"task": tid}), accept
        assert accept["off"] == ("already accepted" if name == "accepted" else ""), accept
        assert (data["summary"]["accepted"] > 0) is (name == "accepted")


def read_only_capture(rig, name, tid):
    """Two GETs with the worker, the briefs and the passes held: same answer, and the task folder is untouched."""
    with rig.frozen():
        before = rig.tree(tid)
        first, second = rig.get(tid), rig.get(tid)
        after = rig.tree(tid)
    assert before == after, {k: (before.get(k), after.get(k)) for k in set(before) | set(after) if before.get(k) != after.get(k)}
    one, two = dict(first["actions"]), dict(second["actions"])
    if one["state"] == "running":  # the elapsed time ticks
        one.pop("line"), two.pop("line")
    assert one == two, name  # repeated reads and reloads keep the same ids and request ids
    ids = contract(rig, tid, first)
    expect(name, first, tid, ids)
    rig.open(tid)  # the page reads the same field
    assert rig.page.evaluate("boardData.data.actions.state") == first["actions"]["state"]
    return first


def build_states(ctx, capture):
    """The states of check 1 and the ones checks 2 and 3 reach, each captured when it stands, on one service."""
    st = ctx.shared.setdefault("states", {})
    if st.get("complete"):
        return st
    rig = st["rig"] = ctx.rig()
    hub, fx = rig.hub, rig.fx
    hub.cfg["supervisor_mode"] = "gated"
    rig.load()
    ids = st.setdefault("tids", {})

    def to_hold(tid):
        return fx.until(tid, lambda t: t["state"] == "waiting" and t["why"] == "plan ready: confirm"
                        and not t.get("briefing"), "the plan hold", 90)

    # A: the design step is running (planning), the plan waits, the code step is running.
    ids["running"] = a = rig.start(WORDS, [S("scout", "look"), S("design", "plan it SLOW"), S("code", "write it SLOW")])
    task = fx.until(a, fx.at(2), "the design step runs", 90)
    capture("planning", a)
    hub.runs.live[task["steps"][1]["session"]].stdin.close()
    to_hold(a)
    capture("plan_ready", a)
    assert rig.act(a, "confirm")[0] == 200
    fx.until(a, fx.at(3), "the code step runs", 30)
    capture("running", a)
    # B: a decision card.
    ids["decision"] = b = rig.start(WORDS, [S("scout", "look"), S("design", "plan it"), S("code", "write it DECIDE-NAME")])
    to_hold(b)
    assert rig.act(b, "confirm")[0] == 200
    fx.until(b, lambda t: t["state"] == "waiting" and t["why"].startswith("asks: "), "the decision waits", 60)
    capture("decision", b)
    # C: done, then accepted.
    ids["done"] = c = rig.start(WORDS, [S("scout", "look"), S("design", "plan it"), S("code", "write it")])
    to_hold(c)
    assert rig.act(c, "confirm")[0] == 200
    fx.until(c, lambda t: t["state"] == "done" and not t.get("briefing"), "the chain ends", 120)
    capture("done", c)
    assert rig.act(c, "accept")[0] == 200
    capture("accepted", c)
    # E: a plan waiting, left as it is for the page sweep.
    ids["plan_ready"] = e = rig.start(WORDS, [S("scout", "look"), S("design", "plan it"), S("code", "write it")])
    to_hold(e)
    # D: two crashes, stuck; then, once the clock moves, the sonnet pass's Retry card.
    ids["suggestion"] = d = rig.start(WORDS, [S("scout", "look"), S("design", "plan it"),
                                              S("code", "write it SLOW SUP-RETRY")], mode="suggest")
    task = fx.until(d, fx.at(2), "the design step runs", 90)  # it reads step 3's SLOW goal too
    hub.runs.live[task["steps"][1]["session"]].stdin.close()
    task = fx.until(d, fx.at(3), "step 3 runs", 90)
    first = task["steps"][2]["session"]
    hub.runs.live[first].kill()
    task = fx.until(d, lambda t: t["steps"][2]["retries"] == 1 and t["steps"][2]["session"] != first
                    and t["steps"][2]["state"] == "running", "the chain retries step 3", 60)
    hub.runs.live[task["steps"][2]["session"]].kill()
    fx.until(d, lambda t: t["state"] == "stuck", "step 3 sticks", 60)
    capture("stuck", d)
    rig.bump()
    rig.settle(d, 1)
    capture("suggestion", d)
    ids["prep"] = rig.prep("CHAIN fix add")["id"]  # a card left unstarted: the ready row and its page
    st["complete"] = True
    return st


def check_actions(ctx):
    seen = []

    def capture(name, tid):
        read_only_capture(ctx.shared["states"]["rig"], name, tid)
        seen.append(name)

    build_states(ctx, capture)
    assert seen == ["planning", "plan_ready", "running", "decision", "done", "accepted", "stuck", "suggestion"], seen
    ctx.shared["states"]["rig"].assert_clean()


def check_viewports(ctx):
    st = build_states(ctx, lambda name, tid: None)
    rig = st["rig"]
    page, tids = rig.page, st["tids"]
    for width in WIDTHS:
        for scheme in ("dark", "light"):
            page.set_viewport_size({"width": width, "height": 760})
            page.emulate_media(color_scheme=scheme, reduced_motion="reduce")
            for name in ("running", "plan_ready", "decision", "done", "suggestion"):
                rig.open(tids[name])
                assert rig.fits(), (width, scheme, name)
            page.evaluate("id => { boardTask = id; boardPick = 'p'; showPage('board'); }", tids["prep"])
            page.wait_for_function("!document.querySelector('#iprep').hidden")
            page.wait_for_timeout(100)
            assert rig.fits(), (width, scheme, "the Prep card")
            page.evaluate("showPage('board'); boardTask = ''; boardPick = ''; renderBoard()")
            page.wait_for_timeout(100)
            assert rig.fits(), (width, scheme, "the list")
    rig.assert_clean()


# -- the runner ----------------------------------------------------------------------------------------------------

CHECKS = {1: ("gated chain, one Confirm, finish summary, Accept, one pass", check_gated_chain),
          2: ("auto: DECISION card, default after the timeout", check_auto_decision),
          3: ("two crashes, stuck, sonnet wake, Retry card, Approve", check_crash_retry),
          4: ("suggest switched to auto at a plan hold", check_mode_switch),
          5: ("900/400/340 px, dark/light, reduced motion", check_viewports),
          6: ("Models Supervisor card and task menu: four words", check_models_card),
          7: ("GET /api/task actions per state, read only", check_actions)}
ORDER = (1, 2, 3, 4, 6, 7, 5)  # 7 builds the states that 5 sweeps; one service stays open between them


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    wanted = [int(a) for a in argv] or list(CHECKS)
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        ctx = Ctx(browser)
        try:
            for number in [n for n in ORDER if n in wanted]:
                name, fn = CHECKS[number]
                start = time.time()
                try:
                    fn(ctx)
                    results[number] = ("PASS", time.time() - start, "")
                except BaseException as exc:
                    if isinstance(exc, KeyboardInterrupt):
                        raise
                    detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()[:900]
                    last = traceback.extract_tb(exc.__traceback__)[-1]
                    results[number] = ("FAIL", time.time() - start, f"{detail} [{last.filename.split(chr(92))[-1]}:{last.lineno}]")
                print(f"{results[number][0]}  {number}  {name}  {results[number][1]:.1f} s", flush=True)
                if results[number][2]:
                    print("      " + results[number][2], flush=True)
                if number == 5 or (number == 7 and 5 not in wanted):
                    ctx.close()  # the shared service of 7 and 5 goes only after both
                elif number in (1, 2, 3, 4, 6):
                    ctx.close()
        finally:
            ctx.close()
            browser.close()
    failed = [n for n, r in results.items() if r[0] != "PASS"]
    print("\n" + ("All %d checks passed." % len(results) if not failed else "FAILED: " + ", ".join(map(str, failed))), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
