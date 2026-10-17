# Task 1: selection — a task opens its Overview, a step opens that step

> Contract: [README.md](README.md) 3.5, 3.6. NAVIGATION.md "Navigation contract". No server change.

**Files**
- Modify: `web/app.js` (functions below, anchored edits next to their neighbours)
- Modify: `web/style.css` (tokens first; `.task-crumb` and the breadcrumb selectors)
- Modify: `tests/test_web.py` (the tests below)

## 1.1 State and entry

- `let taskView = "overview";` next to `boardPick`; `let doneConfirm = "";` (empty = no confirm). Both reset on
  `openTask`. Add `taskView` to `boardWrapKey`'s key so a view switch restarts the scroll.
- `openTask(id)`: `boardTask = id; boardPick = "t"; taskView = "overview"; doneConfirm = ""; boardHistory = "";
  itab = "chat"; boardData = boardChat = null; showPage("board");`. No `row?.current` lookup, no step pick.
- Every task entry point calls `openTask`:
  - the click handler's `data-task` branch (already `openTask`) and `data-bpick === "t"` branch — remove the
    `.v-th, .v-dayr` condition so a title, header, day row or completed row all `openTask`.
  - `taskLink(s)` (already `data-task`).
  - `taskCard` / day-row task clicks (they carry `data-task` or `data-bpick="t"`).
- A step opens only through `data-bpick="s<n>"` (the click handler already does this) and `goChat`; both keep
  their current behavior. `goChat`'s `if (!n) openTask(tid)` stays (a task with no step -> Overview).

## 1.2 Breadcrumb

- `taskBreadcrumb(t, step = null)`: `<nav class="task-crumb" aria-label="Task navigation">` with a `Tasks`
  button (`data-go="bback"`), a `/`, then either the task title as a link (`data-task="<id>") plus `/ Step NN`
  when viewing a step, or the static word `Overview` on the task views. `stepHead` and the Overview head
  (`inspTask`) prepend it.
- `go("bback")` already resets `boardPick`/`boardTask`; keep it as the Tasks target. It must also clear
  `taskView`/`doneConfirm`. Back from the list to a session keeps `backTo` (unchanged).

## 1.3 Async fetch guards

- In `renderBoard` and `renderInspector`'s `await` continuations (`api("/api/task"...)`, `api("/api/chat"...)`,
  `boardChatFetch`, `measureFetch`), after the await, drop the result unless the selection still matches:
  `boardData?.id === boardTask` and the awaited pick (`boardPick`, `itab`, `taskView`) is unchanged. The
  existing `boardData.id` guard covers the task; extend it to the view and pick where a late response would
  otherwise repaint a stale inspector.

## 1.4 CSS

- `.task-crumb { display:flex; gap:8px; align-items:baseline; color:var(--mut); min-width:0; font-size:12px; }`
  and `.task-crumb .olink { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }`,
  `.task-crumb > :last-child { min-width:0; }` (tokens already defined). No new colour.

## Steps

- [ ] 1. `openTask` -> Overview; remove the `.v-th, .v-dayr` condition; add `taskView`/`doneConfirm` state and
      `boardWrapKey`. `node --check` clean.
- [ ] 2. `taskBreadcrumb`; prepend in `stepHead` and the task head. Check at 400 and 340 px (no overflow).
- [ ] 3. Async guards in the awaits. Check by driving a slow fake fetch and switching task mid-flight (test).
- [ ] 4. Tests below; whole Python suite green. Commit: `feat: task selection opens Overview, step links open the step (plan 44 nav T1)`.

## Tests (tests/test_web.py, class SelectionTest or extend UnifiedTaskChatTest)

- `test_task_entry_points_open_overview_not_a_step`: `openTask('t')` sets `boardPick === 't'` and
  `taskView === 'overview'` even when the task has a current step; assert no `s<n>` pick.
- `test_step_link_opens_that_step`: the click-handler path for `data-bpick="s2"` sets `boardPick === 's2'` and
  does not reset it to the current step.
- `test_breadcrumb_shows_tasks_title_and_step`: `taskBreadcrumb(t)` contains `data-go="bback"` and `Overview`;
  `taskBreadcrumb(t, t.steps[0])` contains `data-task="t"` and `Step 01`.
- `test_late_fetch_for_a_different_task_is_dropped`: emulate a stale `/api/task` resolution and assert the
  inspector does not repaint (reuse the existing `render` fixture pattern).

## Drift guards

- `openTask` never reads `row.current`; the only step navigation is an explicit step link or `goChat`.
- Navigation never starts a run; `openTask` and the breadcrumb post nothing.
- Keep the `data-*` event style; no new router, no hash/history.
