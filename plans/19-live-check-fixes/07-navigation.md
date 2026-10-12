# Task 7: Navigation audit, then one fix

> Finding B6. Depends on Tasks 5 and 6 (the folded list changes the pager). Browser code only.

**Files**
- Modify: `web/app.js`, `web/index.html` (the session page's back button), `web/style.css` only if needed.
- This file: section 7.2 gets the walk's findings before any code.

## 7.1 Known from reading the code (2026-10-12)

| # | Where | What happens | Fix |
|---|---|---|---|
| N1 | Session page opened from the Task page (Open, `try K`, Answer on the session page) or from a task card's Open | `←` and Esc go to the list: the Task page and its scroll are lost | one-level back: the session page returns to the page it came from |
| N2 | Task page opened from a session's `task · step 2/4` link | `←` goes to the list, not back to the session | the same back |
| N3 | The pager `N of M` on a step session | with step sessions folded out of the list (Task 5), `navList()` falls back to every session: `17 of 52` through unrelated chats | on a step session the pager steps through the task's steps (`step 2 of 3`, each step's last attempt) |
| N4 | Header `N need you` | counted step sessions, not tasks | done in Task 4 (counts) |
| N5 | Task page of a task that is gone (`taskData === false`) | text only, `←` is the only way | add `<span class="link" data-go="list">Back to the list</span>` to the message |
| N6 | Pill form (path 7) | the rail's chips and the peek card still list step sessions (`liveSessions()` has no task filter); a chip opens the step session, whose `task · step N/M` link reaches the task | kept: a chip is a live run and the folded list is the open form's; no change |
| N7 | Session page of a plain run (path 5) | the pager steps through the folded list (`2 of 2`), `New task here` scopes the list and focuses the box | none: works |
| N8 | Prep card (path 1) | Back and Esc keep the card on the strip, Open again shows it, Cancel drops it | none: works |
| N9 | Usage page from the today strip (path 8) | `←` returns to the list at its scroll | none: works |

Walked 2026-10-12 at 400 px on the scratch home (fake claude, CDP script in the scratchpad). Confirmed by the walk:
N1 (Task page `Open` and `try 1`, the task card's `Open` on a question: `←` and Esc land on the list), N2 (the
session's `task` link, then `←`: the list), N3 (a step session's pager read `19 of 21`, `6 of 21`, through every
session), N5 (the gone message has no link). N4 holds after Task 4: the header said `4 need you` with three stuck
tasks and one waiting task, the Needs you section listed the same four. Path 2's `Run as task` was not walked
(a waiting task held the scratch project); the Task page it opens is the one walked from the list.

## 7.2 The walk (Claude, headless Edge on the scratch home of Task 5)

Walk each path at 400 px and write one row per dead end, lost position or inconsistent back arrow into the table
above (N6 onward), before any code:

1. list -> type a request -> Enter -> strip `Ready to run` -> Prep card -> Back (card kept) -> open again -> Cancel.
2. Prep card -> Run as task -> Task page -> Open step 1 -> `←` -> (expect Task page) -> Esc -> list.
3. list -> task card (Needs you, a question) -> Open -> answer -> `←`.
4. Task page -> `try 1` -> pager `‹ ›` -> `←`.
5. Session page of a plain run -> pager through the list -> `New task here` -> list scope.
6. Header `N need you` with a waiting task and a waiting loose session -> the Needs you section.
7. Pill form: a step session's peek card -> open -> `←`.
8. Usage page from the today strip -> `←`; Task page -> Clear (two clicks) -> list.

Drive the page through `msedge --headless --remote-debugging-port` and a small CDP script in the scratchpad, or
by loading the page with a `#` hash per state and screenshots; the script stays in the scratchpad.

## 7.3 The fix (one task, after the walk)

```js
let backTo = null;       // {page: "task", id} or {page: "session", id}: where the session or Task page's ← returns
function goBack() {      // the session page and the Task page: back where they came from, else the list
  const b = backTo;
  backTo = null;
  if (b && b.page === "task" && (snap.tasks || []).some((t) => t.id === b.id)) return openTask(b.id);
  if (b && b.page === "session") return openSession(b.id, tab);
  showPage("list");
}
```

- Put `backTo` with the other `let`s and `goBack` right after `step(d)`.
- The click handler: `[data-open]` inside `#tscroll` or a `.card.task` sets `backTo = {page: "task", id: <task>}`
  before `openSession`; `[data-task]` on the session page sets `backTo = {page: "session", id: openId}` before
  `openTask`. Any other `data-open` / `data-task` / `data-go="list"` clears it.
- `index.html`: the `←` of the session and Task pages becomes `data-go="back"`; `go("back")` calls `goBack()`;
  Esc on those pages calls `goBack()` too. Titles: `Back (Esc)`.
- `navList()`: when the open session is a task step (`current()?.task`, or `oldStep(openId)` of Task 5), return the
  task's steps' last-attempt sessions in step order as stub rows `{id}`; `renderSession` writes `step K of M`
  instead of `K of M` then. `step(d)` keeps working on that list (it only needs `id`).
- N5's link. Each row N6+ of the walk is fixed here or, when it needs a decision, written down and asked.

## 7.4 Order

1. 7.2 walk; the table filled; commit the plan file `docs: navigation audit findings (plan 19 Task 7)`.
2. 7.3 code; walk the eight paths again; screens at 400 and 340 px; `node --check web/app.js`; suite; commit
   `fix: back returns where it came from, the step pager (plan 19 Task 7)`.
3. PLAN.md History line; commit.
