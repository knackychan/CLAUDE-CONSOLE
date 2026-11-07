# Plan 55 in one page (for Fred)

**What it builds.** The locked autopilot mock in `web/`, in seven tasks. The task page decides which buttons exist,
and whether each is enabled, from GET /api/task `actions` alone; README 1.1 lists the 15 client gate tests it deletes.
One server change: a read-only `prompt` field (D7).

**Order (D1 a).**

1. Head and level switch, plus `tests/live_board_check.py`.
2. Dock card, message box and icon bar with no menu. **Stop 1: screenshots of every state.**
3. Prompt, Brief and Plan sections, and the plan timeline.
4. The list: Needs you pinned, one group per project. **Stop 2.**
5. The step page.
6. The unshown states, the observed page and click-driven acceptance. **Stop 3, with 130 %.**
7. Fred's live look, then the close.

**What goes.** The task menu, taskButtons, attentionArea, confirmLabel, supCard, replanBox, routeHtml, the gauge,
inspGap, inspReplan, stepButtons, handedBox, retryForm, and the Route and Plan tabs.

**What stays.** Composer, Prep, the message-box modes, recovery text, the Models card, Usage, the pill and the 400 px
session list.

**Plan 38.** The type and target floor, U8, U9 and landmarks are done here. Task 4, the page menu, roving strips and
contrast stay in plan 38. Its Task 9 is shared with Task 7.

**Plan 53 seam.** pageHead, sect, foldLine, planRow, svLine, dockCard, actBtn, iconBtn, barHtml, projectGroups and
listHtml. Plan 53 passes its own dispatcher through `data-afn`, and its `buildAct` becomes `buildAct(button)`.

**Decide.** D1 to D14 are in the README. D3 is the one with a cost: Add step and Finish on a running chat task, and
the handoff Retry, are not served by `actions`; a server Task 0 fixes that. D13 also changes the 400 px window's
session head.
