"""Manual browser regression with scratch data and fake runners: py -m tests.live_task_chat_check.

Uses an already installed Playwright and Edge. Makes no provider calls or changes to the running service.
"""
import threading
import time

from playwright.sync_api import sync_playwright

from tests.test_server import TaskServerTest


def main():
    fixture = TaskServerTest()
    fixture.setUp()
    stop = threading.Event()
    failures = []
    def tick():
        while not stop.wait(0.1):
            fixture.hub.poll_once()
            fixture.hub.advance()
    worker = threading.Thread(target=tick, daemon=True)
    try:
        tid = fixture.make_task(words="HANDOFF-OK SLOW")
        sid = fixture.hub.tasks[tid]["steps"][0]["session"]
        worker.start()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 900, "height": 900})
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.goto(f"http://127.0.0.1:{fixture.port}/")
            page.wait_for_function("snap && snap.tasks.length")
            page.evaluate("id => openTask(id)", tid)
            box = page.locator("#b-tcont")
            box.wait_for(state="visible")
            box.fill("browser correction HANDOFF-OK")
            page.locator('[data-tact="cont"]').click()
            page.wait_for_function("boardData?.data?.task?.messages?.[0]?.status === 'queued'")
            assert box.input_value() == ""
            assert fixture.hub.tasks[tid]["current"] == 1
            assert page.get_by_text("Queued for the end of this turn", exact=True).is_visible()
            assert page.get_by_role("button", name="Open chat", exact=True).count() == 0

            box.fill("retained draft")
            with page.expect_file_chooser() as choose:
                page.locator(f'[data-attach="task:{tid}"]').click()
            choose.value.set_files({"name": "draft.txt", "mimeType": "text/plain", "buffer": b"draft attachment"})
            page.wait_for_function("id => att['task:' + id]?.length === 1", arg=tid)
            box.evaluate("e => { e.focus(); e.setSelectionRange(2, 7); }")
            page.wait_for_timeout(150)
            page.evaluate("id => goChat(id, 1)", tid)  # plan 44: a task opens its Overview; the step tabs belong to a step page
            page.wait_for_selector('[data-itab="recv"]')
            for tab in ("recv", "hand", "route", "files", "chat"):
                page.locator(f'[data-itab="{tab}"]').click()
                assert box.is_visible() and box.input_value() == "retained draft"
            other = fixture.make_task(words="HANDOFF-OK SLOW")
            page.evaluate("id => openTask(id)", other)
            page.wait_for_function("id => document.querySelector('#b-tcont')?.dataset.tid === id", arg=other)
            box.fill("other task draft")
            page.evaluate("id => openTask(id)", tid)
            page.wait_for_function("id => document.querySelector('#b-tcont')?.dataset.tid === id", arg=tid)
            assert box.input_value() == "retained draft"
            assert page.evaluate("id => att['task:' + id].length", tid) == 1
            assert box.evaluate("e => [e.selectionStart, e.selectionEnd]") == [2, 7]

            # Only the fake runner waits for an EOF. This ends its turn normally, without injecting guidance.
            fixture.hub.runs.live[sid].stdin.close()
            deadline = time.time() + 20
            while fixture.hub.tasks[tid]["current"] == 1 and time.time() < deadline:
                page.wait_for_timeout(100)
            assert fixture.hub.tasks[tid]["current"] == 2
            assert fixture.hub.tasks[tid]["messages"][0]["status"] == "dispatched"
            page.evaluate("id => goChat(id, 1)", tid)
            page.wait_for_function("document.querySelector('#b-tcont')?.dataset.sid === boardData?.data?.task?.steps[1]?.session")
            assert "Message current step 02" in page.locator(".task-composer label").inner_text()
            assert "History: step 01" in page.locator(".task-composer").inner_text()
            assert box.input_value() == "retained draft"
            assert page.get_by_role("button", name="Use current step").is_visible()

            for width in (900, 400, 340):
                for color in ("dark", "light"):
                    page.set_viewport_size({"width": width, "height": 760})
                    page.emulate_media(color_scheme=color, reduced_motion="reduce")
                    page.wait_for_timeout(100)
                    assert box.is_visible()
                    assert box.bounding_box()["width"] <= width
                    assert box.bounding_box()['y'] + box.bounding_box()['height'] <= 760
                    send = page.locator('[data-tact="cont"]').bounding_box()
                    assert send['y'] + send['height'] <= 760
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, color)
                    assert page.locator('.task-composer').bounding_box()['y'] >= 0

            question = fixture.make_task(words="HANDOFF-OK", steps=[{"kind": "scout", "goal": "look STOP-ASK"},
                                                                     {"kind": "code", "goal": "write SLOW"}])
            fixture.until(question, lambda t: t['state'] == 'waiting', 'question waits')
            page.evaluate("id => openTask(id)", question)
            page.get_by_role('button', name='Send answer', exact=True).wait_for()
            box.fill('calc.py HANDOFF-OK')
            page.get_by_role('button', name='Send answer', exact=True).click()
            page.wait_for_function("id => snap.tasks.find(t => t.id === id)?.current === 2", arg=question)
            assert fixture.hub.tasks[question]['messages'][0]['status'] == 'dispatched'

            failed = fixture.make_task(words='HANDOFF-OK MAXTURNS')
            task = fixture.until(failed, lambda t: t['state'] == 'stuck', 'capped run waits for retry')
            task['goal'] = task['goal'].replace('MAXTURNS', '')
            page.evaluate('id => openTask(id)', failed)
            page.wait_for_function("id => document.querySelector('#b-tcont')?.dataset.tid === id", arg=failed)
            box.fill('guidance for explicit retry HANDOFF-OK')
            page.get_by_role('button', name='Send', exact=True).click()
            page.wait_for_function("boardData?.data?.task?.messages?.[0]?.status === 'queued'")
            retry = page.get_by_role('button', name='Retry', exact=True)
            retry.click()
            page.get_by_role('button', name='Retry and carry queued guidance? Click again', exact=True).click()
            page.wait_for_function("boardData?.data?.task?.messages?.[0]?.status === 'dispatched'")
            assert not failures, failures
            browser.close()
        print("Task chat browser checks passed: queued correction, progression, drafts, attachments, selection, tabs, history, question, explicit retry after a cap; 900/400/340 px, dark/light, reduced motion.")
    finally:
        stop.set()
        if worker.is_alive():
            worker.join(5)
        fixture.tearDown()
        fixture.doCleanups()


if __name__ == "__main__":
    main()
