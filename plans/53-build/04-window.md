# Task 4: the Board shows and drives a build (README section 5)

Files: `web/app.js`, `web/style.css` (tokens first, no new colour), `tests/test_web.py`.
Commit boundary: `feat: the build row, page and New build form on the Board (plan 53 Task 4)`.
Depends on Task 3. The page reads `GET /api/state` `builds`, `GET /api/build` and posts the 4.7 routes; it holds no
rule of its own (plan 36 3.4): a button shows only when `actions` lists it, greyed with its `off` reason.
Drawn with the parts the locked `design/rework/locked/workflow-autopilot.html` already has (plan 52 Task 8: UI-3
head, UI-4 sections, UI-5 rows, UI-7 dock card, UI-8 bar); the Board's project groups (UI-1) are not built here, so
the row sits in the group its `group` says, as task rows do today.

## State

- `let boardBuild = "";` beside `boardTask` (app.js:110): the picked build (`""` none); `boardPick` is `"b"` on the
  build head. `window.json` keeps it as `board_build` (through `/api/draft` like `board_tab`; `paths.save_window`
  accepts the key, `folds_ok` is untouched). Picking a task or a card clears `boardBuild`; picking a build clears
  `boardTask`.
- `let buildData = null;` `{id, sig, data}` of `GET /api/build`, fetched when the pick changes and when the row's
  signature changes (`buildRowSig(row)`: state, why, current, spent, updated, item.state), as `taskRowSig` does.
- `let newBuild = null;` the New build form's draft `{project_dir, folder, goal_file, title, level, cap, items, busy,
  error}` while the form is open.

## The row (`buildHtml(b)`, drawn by `chainHtml` after the task rows of the same group)

`statusLine`'s sibling `buildLine(b)` returns `[text, tone]` from the row alone: `b.line` when the service gives one
(waiting, held, paused, stopped, done, preparing); when `b.state === "running"` and `b.item.task` names a task the
window knows, `` `build · ${b.current} of ${b.count} · ${two(b.current)} ` + statusLine(thatTaskRow)[0] `` with that
line's tone. The mark is the task sprite of the state word (`taskMark` with `state` mapped: waiting -> `waiting`,
running -> `running`, stopped -> `stopped`, done -> `done`). The row's second line: the line and `money(b.spent)`.
Click: `boardBuild = b.id; boardPick = "b"`.

## The page (`inspBuild(b, d)`, in `boardInspector` when `boardBuild`)

- Head (UI-3): eyebrow `b.project`, title, meta line: the state pill (`tone()` words), `Now · sub-plan 3 of 9`,
  `Level` as the UI-3 switch (`data-bact="level:gated"` / `level:auto`, the current one pressed), `Spent $12.40 of
  $25` in the Doto figure (`of $25` absent when the cap is 0).
- Sections (UI-4, `sect(label, muted, body)` as the inspector's other sections): **Goal** (the goal file path with
  `copyBtn`, or "no goal file", and the folder); **Sub-plans**: one row per item, the UI-5 row (rail mark, `two(n)`,
  title, the state word, `money(cost)`): a row whose item has a task is a link that calls `openTask(item.task)`; a
  `ready` row opens its card (`openTask(item.prep)`: a Prep id is a Board pick already); a `drift` line under the row
  when `item.drift_note` (`◆ drift minor · <note>`, muted, the UI-5 supervisor-line style); **Done** when
  `d.summary`: accepted / skipped / failed counts, the files list as a fold, the open questions fold (reusing
  `questionsFold`'s shape).
- The dock card (UI-7, `dock(head, body, buttons, id)` as `inspTask` uses it) from `d.actions.primary` and `.bar`:
  the tag is the state word (`Ready`, `Drift`, `Prep failed`, `Cap`, `Accept`, `Paused`), the sentence is `b.why`, the
  buttons are the listed actions with the primary at the right edge. `Raise cap` carries a number input
  (`data-bcap`) whose value rides in the body. `Open the card` / `Open the task` are page moves (`openTask`), not
  posts; `actions` lists them with `post: ""`.
- The bar (UI-8): Folder (`/api/open_folder` on the build folder's absolute path, which `d.build.project_dir +
  folder` gives), Delete (two clicks, `confirm: true`), the spend figure, then Stop, Pause after this sub-plan /
  Resume, from `d.actions.menu`.
- "Start, and run the rest automatically": in `prepHtml(c)` (app.js:1159), when the card's id is the `prep` of a
  build's current item (`snap.builds.find(...)`), a second Start button (`data-start-auto`) that posts
  `/api/build/level {level: "auto"}` then runs `startCard` as the first Start does (`startCard(c, button, {buildAuto:
  bid})`); hidden when the build is already `auto`. The card also shows the planner's drift note above the step list
  when `c.planner.drift` is `minor` or `major`, as the scope note is shown (one muted line, the word as a tag).

Actions: `buildAct(name, button, id)` beside `taskAct`: posts `/api/build/<lever>` with `{build: id}` plus `n`
(skip), `level`, `cap_usd`; on 409 the error shows in the busy box (`busyBox`) as task actions do; then `actRedraw()`.

## New build (the form)

`headerMenu()` (app.js:1018) gains `item("newbuild", "New build…", "a folder of sub-plans")` after Measure; `go("newbuild")`
opens `inspNewBuild()` in the inspector pane: fields project (the scope's project preselected; `projectRows()` for the
list), folder (text), goal file (text, optional), title (optional), level (a two-word segment, gated pressed), cap (a
number, `cfg.tuning.build_cap_usd.value` prefilled); **Preview** posts `/api/build/preview` and lists the items with a
checkbox each (all checked), their titles and word counts, and the goal file's state (`found` / `not found`);
**Create** posts `/api/build` with `keep` = the checked numbers, then picks the new build. Errors (400 / 403) show
under the form. Nothing starts: the page says so under Create ("Creates the build. Start is on its page.").

## Style

`web/style.css`: the build row reuses `.v-tk` / `.v-th` (one modifier class `.v-bd` for the mark's rail colour from
the existing tokens); the page reuses the inspector's section, row, dock and bar classes; the New build form reuses the
Hand off task form's field classes. No new tokens, no emojis, no em-dashes.

## Tests (first, red), `tests/test_web.py` (the Node harness; `render(expr)`)

- `BuildRowTest::test_build_line_per_state`: `buildLine` on a waiting row -> `["needs you · sub-plan 3 ready: Start",
  "y"]`; done -> `["done · 8 sub-plans · $84.20", "g"]`; running with a task row in `snap.tasks` -> starts with
  `build · 3 of 9 · 03 ` and carries that task's line; stopped -> `stopped · 3 of 9`.
- `BuildRowTest::test_build_row_in_its_group`: `chainHtml()` with one build in `needs` and one in `done` draws each
  under its group head, after the task rows.
- `BuildPageTest::test_head_sections_and_rows`: `inspBuild(b, d)` has the eyebrow, the meta line's three facts, one
  row per item with the state word and cost, a `data-open` on rows with a task, the drift line under the item that
  has a note, and the Done section only when `d.summary`.
- `BuildPageTest::test_dock_and_bar_follow_actions`: with `d.actions` of the Cap state the dock shows Raise cap (with
  the number input) and Stop and nothing else; with the Ready state the primary is Open the card; the bar lists only
  what `menu` names; an action with `off` is disabled with the reason in its title.
- `BuildPageTest::test_start_auto_button_on_a_build_card`: `prepHtml(card)` with a build whose current item's prep is
  the card shows the second Start; not when the build is `auto`; not on a card outside a build; the drift note line
  appears for `minor` and `major`, not for `none`.
- `NewBuildFormTest::test_form_preview_and_create_bodies`: `inspNewBuild()` has the six fields and Preview; after a
  preview the items have checkboxes; the Create body (`newBuildBody()`) carries `keep` of the checked numbers, the
  level and the cap as numbers.
- `node --check web/app.js` clean; headless Edge at 900 and 400 px with the fake claude: no page error, no horizontal
  scroll (the live_window_check script, as plan 24 Task 4 did).
