"""Plan 48 section 7 restart check with scratch data and the fake runner: py -m tests.live_recovery_check [shots dir].

A service runs two tasks, a step's run dies while the service is down, a second service starts on the same data
folder, and the browser opens each task: the recovery box must match the saved files, and opening starts no work.
Uses an already installed Playwright and Edge. Makes no provider calls or changes to the running service.
"""
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from console import server, tasks
from tests.test_server import TaskServerTest

LONG = ("the run did not finish cleanly: " + "a very long interruption reason with an artifact name "
        "02-explain/handoff-with-a-long-file-name-that-has-no-spaces-at-all-to-break-on.md " * 4).strip()


def main():
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    fixture = TaskServerTest()
    fixture.setUp()
    failures, stop = [], threading.Event()
    try:
        # 1. The first service: step 01 ends, step 02 runs (SLOW waits); a one-step task runs its only step.
        done_then_cut = fixture.make_task(steps=[{"kind": "scout", "goal": "look around"},
                                                 {"kind": "explain", "goal": "say what you saw SLOW"}])
        first_cut = fixture.make_task(steps=[{"kind": "scout", "goal": "look around SLOW"}])
        for tid, n in ((done_then_cut, 2), (first_cut, 1)):
            task = fixture.until(tid, lambda t, n=n: t["steps"][n - 1]["state"] == "running"
                                 and t["steps"][n - 1]["session"] in fixture.hub.runs.live, f"step {n} runs")
            task["steps"][n - 1]["retries"] = 1  # its automatic retry is spent: the restart leaves it for Fred
            tasks.save(fixture.folder, task)
        # 2. The service goes down (nothing advances any more), then the step processes die.
        sids = [fixture.hub.tasks[t]["steps"][n - 1]["session"] for t, n in ((done_then_cut, 2), (first_cut, 1))]
        fixture.httpd.shutdown()
        for sid in sids:
            fixture.hub.runs.live[sid].kill()
        end = time.time() + 15
        while time.time() < end and any(fixture.hub.runs.live.get(s) for s in sids if s in fixture.hub.runs.live
                                        and fixture.hub.runs.live[s].poll() is None):
            time.sleep(0.05)
        # 3. A second service on the same data folder: its own startup order, then its loop.
        httpd, hub = server.make_server(fixture.hub.cfg, port=0, folder=fixture.folder, exe=fixture.hub.runs.exe)
        hub.user_home = fixture.hub.user_home
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        hub.runs.reconcile()
        hub.reconcile_next_steps()

        def tick():
            while not stop.wait(0.1):
                hub.poll_once()
                hub.advance()
        threading.Thread(target=tick, daemon=True).start()
        end = time.time() + 25
        while time.time() < end and not all(hub.tasks[t]["state"] == "stuck" for t in (done_then_cut, first_cut)):
            time.sleep(0.1)
        for tid in (done_then_cut, first_cut):
            assert hub.tasks[tid]["state"] == "stuck", (tid, hub.tasks[tid]["state"], hub.tasks[tid]["why"])
        saved = tasks.load(fixture.folder, done_then_cut)
        assert saved["steps"][0]["state"] == "done"
        assert tasks.read_note(fixture.folder, saved, 1), "step 01 saved a handoff"
        assert saved["steps"][1]["attempts"][-1]["cause"] == "interrupted"
        port = httpd.server_address[1]

        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 900, "height": 900})
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.on("console", lambda m: failures.append(m.text + " " + str(m.location.get("url"))) if m.type == "error" and not str(m.location.get("url")).endswith("/favicon.ico") else None)  # the window has no favicon route
            page.goto(f"http://127.0.0.1:{port}/")
            page.wait_for_function("snap && snap.tasks.length")
            before = (sorted(p.name for p in (fixture.folder / "runs").iterdir()), dict(hub.runs.live),
                      [len(s["attempts"]) for t in hub.tasks.values() for s in t["steps"]])

            page.evaluate("id => openTask(id)", done_then_cut)
            box = page.locator(".askbox.recovery")
            box.wait_for(state="visible")
            text = box.inner_text()
            for want in ("Step 01 scout finished with a saved handoff.",
                         "Step 02 explain, attempt 1, was interrupted: the run ended without a result",
                         "Nothing is undone", "Retry on a model (task menu) runs step 02 again"):
                assert want in text, (want, text)
            assert page.locator('[data-tact="chatresume"], [data-tact="resume"]').count() == 0  # stuck: Retry, never Resume
            assert "Retry asks whether to carry it" in page.locator("#b-delivery").inner_text()
            page.locator('.askbox.recovery [data-bpick="s1"]').focus()
            page.keyboard.press("Enter")
            page.wait_for_function("boardPick === 's1'")
            page.evaluate("id => openTask(id)", first_cut)
            page.wait_for_function("document.querySelector('.askbox.recovery')?.innerText.includes('No completed step recorded.')")
            assert "Step 01 scout, attempt 1, was interrupted" in page.locator(".askbox.recovery").inner_text()

            time.sleep(1.5)  # a few loop passes and refreshes with the tasks open
            after = (sorted(p.name for p in (fixture.folder / "runs").iterdir()), dict(hub.runs.live),
                     [len(s["attempts"]) for t in hub.tasks.values() for s in t["steps"]])
            assert after == before, ("opening started work", before, after)

            # Long reasons and artifact names: a failed cause shows the saved why.
            cut = hub.tasks[done_then_cut]["steps"][1]["attempts"][-1]
            cut.update(cause="failed", why=LONG)
            page.evaluate("id => openTask(id)", done_then_cut)
            page.wait_for_function("document.querySelector('.askbox.recovery')?.innerText.includes('a very long interruption')")
            draft = page.locator("#b-tcont")
            draft.fill("kept draft")
            draft.evaluate("e => { e.focus(); e.setSelectionRange(1, 4); }")
            for width in (900, 400, 340):
                for color in ("dark", "light"):
                    page.set_viewport_size({"width": width, "height": 760})
                    page.emulate_media(color_scheme=color, reduced_motion="reduce")
                    page.wait_for_timeout(150)
                    b = box.bounding_box()
                    assert b and b["x"] >= 0 and b["x"] + b["width"] <= width, (width, color, b)
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, color)
                    assert draft.input_value() == "kept draft"
                    if shots:
                        shots.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(shots / f"recovery-{width}-{color}.png"))
            page.evaluate("renderBoard()")  # a redraw keeps the draft, the caret and the focus
            page.wait_for_timeout(200)
            assert draft.input_value() == "kept draft"
            assert page.evaluate("[document.activeElement?.id, document.activeElement?.selectionStart, document.activeElement?.selectionEnd]") == ["b-tcont", 1, 4]
            browser.close()
        stop.set()
        httpd.shutdown()
        httpd.server_close()
        assert not failures, failures
        print("recovery check: PASS")
    finally:
        stop.set()
        fixture.tearDown()


if __name__ == "__main__":
    main()
