"""Headless look of plan 55's Board: py -m tests.live_board_check [--shots DIR] [state ...].

One scratch service from tests.live_autopilot_check (Rig, build_states: the fake claude, no provider, never the
running service), the real page in headless Edge. Each captured state is opened at 900, 400 and 340 px, dark and light,
reduced motion, device scale 1.0 and 1.3 (WebView2 at 130 %). Asserts: no horizontal scroll, no page or console
error, and the per-task checks in CHECKS. --shots saves one PNG per state, width and scheme for Fred (stops 1 to 3)."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.live_autopilot_check import Ctx, build_states

WIDTHS, SCALES, SCHEMES = (900, 400, 340), (1.0, 1.3), ("dark", "light")
STATES = ("planning", "plan_ready", "running", "decision", "done", "suggestion")
SMALL = """[...document.querySelectorAll('.p-hd *, .p-card *, .p-bar *, .p-box *, .p-sect *')]
  .filter((e) => e.offsetParent && e.childNodes.length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    && parseFloat(getComputedStyle(e).fontSize) < 11).map((e) => e.className + ': ' + e.textContent.trim().slice(0, 30))"""
TINY = """[...document.querySelectorAll('.p-hd button, .p-card button, .p-bar button, .p-box button, .p-sect button')]
  .filter((b) => b.offsetParent).map((b) => [b.className + ' ' + (b.dataset.aid || b.textContent.trim()).slice(0, 30), b.getBoundingClientRect()])
  .filter(([, r]) => r.height < 24 || r.width < 24).map(([n]) => n)"""


def head_checks(page, name):  # Task 1; later tasks add their own functions to CHECKS
    assert page.locator(".p-hd").count() == 1, (name, "one page head")
    assert page.evaluate("document.querySelector('.p-hd h2').scrollWidth >= document.querySelector('.p-hd h2').clientWidth"), name


CHECKS = [head_checks]


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    shots = Path(argv[argv.index("--shots") + 1]) if "--shots" in argv else None
    wanted = [a for a in argv if a in STATES] or list(STATES)
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        ctx = Ctx(browser)
        try:
            st = build_states(ctx, lambda name, tid: None)
            rig = st["rig"]
            for scale in SCALES:
                page = browser.new_page(device_scale_factor=scale)
                rig.page, rig.page_errors = page, []
                page.on("pageerror", lambda e: rig.page_errors.append("pageerror: " + str(e)))
                page.on("console", rig._console)
                rig.load()
                for width in WIDTHS:
                    for scheme in SCHEMES:
                        page.set_viewport_size({"width": width, "height": 760})
                        page.emulate_media(color_scheme=scheme, reduced_motion="reduce")
                        for name in wanted:
                            rig.open(st["tids"]["running" if name == "planning" else name])
                            where = f"{name} {width}px {scheme} x{scale}"
                            try:
                                assert rig.fits(), "horizontal scroll"
                                assert not page.evaluate(SMALL), page.evaluate(SMALL)
                                assert not page.evaluate(TINY), page.evaluate(TINY)
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
