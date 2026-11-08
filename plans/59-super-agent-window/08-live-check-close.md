# Task 8: Fred's live check, the measurements, the close

> Contract: [README.md](README.md) section 1 (done when), 9 (risks). Fred decides here whether the window does what
> design section 9 promised: **he answers a day's items from the queue without opening a task page.** Starts after Stop 1
> (Task 7) is answered. Like plan 58 Task 7 and plan 55 Task 7, this is Fred's sitting plus the docs.

**Files:** `tests/live_super_check.py` (the scripted day and `--measure`), `CLAUDE.md`, `PLAN.md`, `design/brainstorm/2026-11-08-super-agent.md`
(History line), `plans/55-autopilot-ui/README.md` and `plans/58-super-agent/README.md` (one note each, anchored).
Commit boundary: `docs: plan 59 built, live check passed (plan 59 T8)`.

## 8.1 The scripted day (headless, before Fred sits down)

`py -m tests.live_super_check --day` runs one scratch service with plan 55's states (plan ready, decision, hold on Fable,
suggestion, two finished tasks that batch, one stuck, one observed chat, one Console-run session that was interrupted), the
fake claude as the pass, and the real page in headless Edge. It answers everything the cards can answer **without opening a
task page**, and fails if `openTask` or `openSession` is called, or if any surface disagrees:

```python
def scripted_day(page, rig):
    page.evaluate("window.__opens = 0; const o = openTask; openTask = (...a) => { window.__opens++; return o(...a); };"
                  " const s = openSession; openSession = (...a) => { window.__opens++; return s(...a); };")
    page.evaluate("showPage('board'); boardTask = ''; boardPick = ''; swSel = ''; renderBoard()")
    start = page.evaluate("forYou()")
    assert start >= 8, ("a day with items", start)
    answered, later = [], 0
    for _ in range(60):
        card = page.locator("#bwrap .sw-qc.cur")
        if not card.count():
            break
        primary = card.locator(".btn.you:not([disabled])")
        if primary.count():                                    # the card's own answer
            label = card.get_attribute("aria-label")
            primary.first.click()
            if "Click again" in primary.first.inner_text():    # a two-click action (Fable): the second click sends
                primary.first.click()
            rig.wait_idle(page)                                # the card shows Sent, then leaves on the service's word
            answered.append(label)
        elif card.locator("[data-sw='later']").count():        # an observed chat or a card with no answer in it: Later, never Open
            card.locator("[data-sw='later']").click()
            rig.wait_idle(page)
            later += 1
        else:
            break                                              # an always item with no answer in the card
    opens = page.evaluate("window.__opens")
    assert opens == 0, ("no task page was opened", opens, answered)
    stuck = page.evaluate("swCards().flatMap((c) => c.items).filter((i) => i.acts.primary.some((a) => a.post && !a.off)).map((i) => i.key)")
    assert not stuck, ("nothing answerable in place remains", stuck)
    c = page.evaluate(COUNT_JS)
    assert c["row"] == c["hdr"] == c["forYou"] == c["items"], ("the counts still agree", c)
    return {"start": start, "answered": len(answered), "later": later, "left": c["items"]}
```

(`rig.wait_idle` is plan 55's Rig wait for the next snapshot; if it is named otherwise, `page.wait_for_function("!document.querySelector('#bwrap .sw-qc[aria-busy=true]')")` does the same.)

The cards that remain after the scripted day are the ones the data says cannot be answered in place: a Retry or Reopen (a
served form that needs the task page, D1) and an always item with no served answer. Observed chats are put later, never opened (D3). The live
check records which and how many, because that is the real answer to "without opening a task page".

## 8.2 Measurements

`py -m tests.live_super_check --measure` builds 30 and 65 live items in a scratch Hub (plan 58's `make_task`, no model) and
prints the median of 20 calls of `Hub.super_view()` and of `Hub.snapshot()`:

```python
def measure(hub, counts=(30, 65)):
    from tests.test_superagent_server import make_task
    out = {}
    for n in counts:
        for k in range(len(hub.tasks) + 1, n + 1):
            make_task(hub, hub.cfg["projects"][0], k)
        view, snap = [], []
        for _ in range(20):
            t = time.perf_counter(); hub.super_view(); view.append(time.perf_counter() - t)
            t = time.perf_counter(); hub.snapshot(); snap.append(time.perf_counter() - t)
        out[n] = {"view_ms": round(statistics.median(view) * 1000, 1), "snapshot_ms": round(statistics.median(snap) * 1000, 1)}
    return out
```

Budgets (README section 9): `super_view` at most 150 ms at 30 items; `snapshot()` at most 20 ms more than without the super
agent. Over budget: do not tune blindly; add the read-only `GET /api/super/card?key=` that serves one card's `acts`
lazily (the page asks for the current card), and say so in Fred's list. No gate moves either way.

## 8.3 Fred's sitting (the script)

Start the service as always (`py -m console`), `super_day_usd` at its default. With real tasks across at least two
projects, over a working day or an hour of staged work:

| # | Do | Expect |
|---|---|---|
| 1 | Open the window with nothing selected | the super agent page; the header, row, pill and project lines say the same number |
| 2 | Answer the first card with its button, then with J K and Enter | the card shows Sent, leaves, the next takes focus; the number drops by one everywhere |
| 3 | Answer a decision by key (1 to 4, Enter) and by Write your own answer | the chip reads `Answer · task`; the answer reaches the task (its page shows the message) |
| 4 | Press S on a card; open Later; Bring it back | Back in an hour; its reason is in sight; Bring back returns it with `back from Later` |
| 5 | Try S on an `always yours` card | it says `Stays here: <reason>`; nothing moves |
| 6 | Accept a batch; then Review one by one on another | each member's task is accepted; a refusal names the task |
| 7 | Pause, then Resume, then Sort now | Paused note and oldest first; Resume sorts; Sort now runs one pass |
| 8 | Select the super agent row; send a message | the chip reads `◆ Super agent`; the next pass's prompt holds it; the log line says it was noted |
| 9 | Edit orders; Save | the list updates; the next pass uses them |
| 10 | Mark seen | the list empties; the spend line restarts |
| 11 | Set `super_day_usd` to 0 on the Models page | `off` note, every action still there, unranked |
| 12 | Use VS Code or a terminal chat that asks something | its card says where to answer; Open shows the read-only page |
| 13 | Look at 900, 400, 340 px and at 130 % text | nothing clipped, every number the same |

Fred writes the result under "Plan 59 live check findings" in the memory file `plan59-live-check-findings.md` (the way
plan 17 and plan 19 did), one line per bug, gap or UI note. Bugs that block the "a day's items" promise are fixed
before the close; the rest are logged and scheduled by Fred.

## 8.4 The close (docs)

`CLAUDE.md`, one paragraph after the Board paragraph (anchored on its last sentence):

> The super agent window (plan 59): its row and page are the home pane of the one window. They read `snap.super` and
> `GET /api/super` and write only `POST /api/super` (pause, resume, sort, later, bring_back, seen, message, orders: its own
> files in `~/.claude/console/super/`). A card is answered only by the route its served `acts` name (`Hub.actions`,
> `Hub.levers`); an observed chat's card only opens Console's read-only page. `snap.counts.for_you` is the one count (header,
> row, page, project lines, tray); the window draws it from the view when `rev` matches, else from the snapshot.

`PLAN.md`: the row 59 added at the plan's writing becomes `built <date>, live check passed` with the findings count; one
History line (anchored on the last line). `design/brainstorm/2026-11-08-super-agent.md` History: `- <date> - Slice 2 built as
plan 59 (plan 59 README, D1 to D10 as Fred answered).` `plans/55-autopilot-ui/README.md`: under Status, `Task 4 was replaced
by plan 59 Task 4 (the roll-up list and the super agent row); build Tasks 5 to 7 on it.` `plans/58-super-agent/README.md`:
under Status, `D9 (Models card) and the window were built by plan 59.`

Memory (the session that closes): update `super-agent-direction.md` with "slice 2 = plan 59 built <date>; slice 3 next", and
the findings file name.

## 8.5 Steps and acceptance

- [ ] 1. Write the scripted day and `--measure`; run both against the built tasks 1 to 7. Fix what they find (a failing
      assertion is a bug in Tasks 1 to 7, fixed there with its own test, not worked around here).
- [ ] 2. Fred's sitting (8.3). Findings logged; blockers fixed.
- [ ] 3. The docs of 8.4. Full suite green (report the count). `git diff --stat` shows only the files above. Stage explicit
      paths and only this plan's hunks of shared files. Commit with the message above.
