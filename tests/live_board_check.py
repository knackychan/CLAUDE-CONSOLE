"""Headless look of plan 55's Board: py -m tests.live_board_check [--shots DIR] [state ...].

One scratch service from tests.live_autopilot_check (Rig, build_states: the fake claude, no provider, never the
running service), the real page in headless Edge. Each captured state is opened at 900, 400 and 340 px, dark and light,
reduced motion, device scale 1.0 and 1.3 (WebView2 at 130 %). Asserts: no horizontal scroll, no page or console
error, and the per-task checks in CHECKS. --shots saves one PNG per state, width and scheme for Fred (stops 1 to 3)."""
import sys
import copy
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.live_autopilot_check import Ctx, build_states

WIDTHS, SCALES, SCHEMES = (900, 400, 340), (1.0, 1.3), ("dark", "light")
STATES = ("planning", "ready", "running", "plan_ready", "decision", "suggestion", "hold", "failed_twice", "done", "observed", "preparing", "paused", "stopped", "stuck", "handed", "accepted")
SMALL = """[...document.querySelectorAll('.p-hd *, .p-card *, .p-bar *, .p-box *, .p-sect *')]
  .filter((e) => e.offsetParent && e.childNodes.length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    && parseFloat(getComputedStyle(e).fontSize) < 11).map((e) => e.className + ': ' + e.textContent.trim().slice(0, 30))"""
TINY = """[...document.querySelectorAll('.p-hd button, .p-card button, .p-bar button, .p-box button, .p-sect button')]
  .filter((b) => b.offsetParent).map((b) => [b.className + ' ' + (b.dataset.aid || b.textContent.trim()).slice(0, 30), b.getBoundingClientRect()])
  .filter(([, r]) => r.height < 24 || r.width < 24).map(([n]) => n)"""


def head_checks(page, name):  # Task 1; later tasks add their own functions to CHECKS
    assert page.locator(".p-hd").count() == 1, (name, "one page head")
    assert page.evaluate("document.querySelector('.p-hd h2').scrollWidth >= document.querySelector('.p-hd h2').clientWidth"), name


def dock_checks(page, name):  # Task 2: the card stays in sight, the primary is the rightmost control, no ⋯ menu
    assert page.locator(".idock[data-p] details.action-more").count() == 0, (name, "no task menu")
    card = page.locator(".p-card")
    if name in ("plan_ready", "decision", "suggestion"):
        assert card.count() == 1, (name, "one dock card")
        box, main = card.bounding_box(), page.locator(".idock[data-p]").bounding_box()
        assert box["y"] >= main["y"] and box["y"] + box["height"] <= main["y"] + main["height"], (name, "card scrolled away")
        right = page.locator(".p-card .p-acts > *").last
        assert "you" in (right.get_attribute("class") or ""), (name, "primary at the right")
    if name in ("running", "planning"):
        assert card.count() == 0, (name, "no card while it runs")
    assert page.locator(".p-bar").count() == 1, (name, "one action bar")

CHECKS = [head_checks, dock_checks]


def variants(c):
    """Rare states use captured GET bodies with test-only projections; production has no fixture seam."""
    def state(name, base, word, primary=(), bar=(), menu=None):
        d = c[name] = copy.deepcopy(c[base])
        a = d["actions"]
        a.update(state=word, line=word, primary=list(primary), bar=list(bar), menu=a["menu"] if menu is None else menu)
        a.pop("recovery", None)
        a.pop("hint", None)
        d["supervisor"]["pending"] = None
        d["supervisor"]["rejected"] = None
        return d
    def action(id, label, post="", off="", **body):
        return dict(id=id, label=label, post=post, body=body, off=off, confirm=id in ("stop", "delete", "drop", "finish", "confirm"))
    stop = action("stop", "Stop", "/api/task/stop")
    delete = action("delete", "Delete", "/api/task/clear")
    retry = action("retry", "Retry on a model")
    finish = action("finish", "Finish", "/api/task/done")
    d = state("ready", "plan_ready", "ready", [action("start", "Start", "/api/task/resume")], [action("drop", "Drop", "/api/task/clear")], [])
    d["task"].update(state="planned", current=1)
    for step in d["task"]["steps"]:
        step.update(state="planned", session="")
    d = state("hold", "plan_ready", "hold", [action("confirm", "Confirm", "/api/task/confirm")], [stop])
    d["task"]["why"] = "confirm Fable"
    d = state("failed_twice", "stuck", "failed_twice", [retry], [action("stepdone", "Accept step result", "/api/task/stepdone"), finish], [delete])
    d["actions"]["line"] = "failed twice · verify failed twice"
    d = state("paused", "running", "paused", [action("resume", "Resume", "/api/task/resume")], [stop])
    d["actions"]["message"]["timing"] = "Message the agent; it reads it after Resume"
    d["task"]["state"] = "waiting"
    d = state("stopped", "stuck", "stopped", [retry], [finish], [delete])
    d["task"]["state"] = "stopped"
    d["actions"]["message"]["reason"] = "Task is stopped. Resume or Retry before sending."
    d = state("handed", "done", "handed", [action("start_next", "Start next task")], [], [delete])
    d["task"].update(state="handed", accepted=0)
    d["handoff"] = "Saved handoff for the next task."
    d = state("observed", "running", "observed", [], [], [action("continue", "Continue as a fork", "/api/continue"), action("terminal", "Open in terminal", "/api/terminal")])
    d["actions"]["message"] = None


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    shots = Path(argv[argv.index("--shots") + 1]) if "--shots" in argv else None
    wanted = [a for a in argv if a in STATES] or list(STATES)
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        ctx = Ctx(browser)
        try:
            captures = {}
            def capture(name, tid):
                captures[name] = copy.deepcopy(ctx.shared["states"]["rig"].get(tid))
            st = build_states(ctx, capture)
            variants(captures)
            current = [None]
            rig = st["rig"]
            for scale in SCALES:
                page = browser.new_page(device_scale_factor=scale)
                rig.page = page
                page.on("pageerror", lambda e: rig.page_errors.append("pageerror: " + str(e)))
                page.on("console", rig._console)
                page.route("**/api/task?id=*", lambda route: route.fulfill(json=current[0]) if current[0] else route.continue_())
                rig.load()
                for width in WIDTHS:
                    for scheme in SCHEMES:
                        page.set_viewport_size({"width": width, "height": 760})
                        page.emulate_media(color_scheme=scheme, reduced_motion="reduce")
                        for name in wanted:
                            if name == "preparing":
                                current[0] = None
                                page.evaluate("id => { boardData = null; boardTask = id; boardPick = 'p'; showPage('board'); renderBoard(); }", st["tids"]["prep"])
                                page.locator("#iprep:not([hidden])").wait_for()
                            else:
                                current[0] = captures[name]
                                page.evaluate("boardData = null")
                                rig.open(current[0]["task"]["id"])
                            where = f"{name} {width}px {scheme} x{scale}"
                            try:
                                assert rig.fits(), "horizontal scroll"
                                assert not page.evaluate(SMALL), page.evaluate(SMALL)
                                assert not page.evaluate(TINY), page.evaluate(TINY)
                                if name != "preparing":
                                    assert page.locator('.idock[data-p="task"]').evaluate("e => e.scrollWidth <= e.clientWidth"), "task overflow"
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
