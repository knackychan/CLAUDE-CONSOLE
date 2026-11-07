# Task 4: the Board shows and drives a build (README section 5)

Files: `web/app.js`, `web/style.css` (tokens first, no new colour), `tests/test_web.py`. No server file: the page saves
nothing of its own (State, below).
Commit boundary: `feat: the build row, page and New build form on the Board (plan 53 Task 4)`.
Depends on Task 3, and on plan 55's parts through the seam contract below. The page reads `GET /api/state` `builds`,
`GET /api/build` and posts the 4.7 routes; it holds no rule of its own (plan 36 3.4): a button shows only when
`actions` lists it, greyed with its `off` reason. Drawn with the parts of the locked
`design/rework/locked/workflow-autopilot.html` (plan 52 Task 8: UI-3 head, UI-4 sections, UI-5 rows, UI-7 dock card, UI-8
bar). This task adds no visual language: one more row kind, one more page and one more form, drawn with those parts.

## Seam contract with plan 55 (written 2026-11-07; plan 55 is an uncommitted draft, so check this against it before starting)

Plan 55 builds the locked UI into `web/` and reads `GET /api/task` `actions` only. A build draws with the same parts, so
the two plans meet in one place. While the refresh was written, `plans/55-autopilot-ui/` held an uncommitted draft whose
section 7 ("The seam for plan 53 Task 4") already names the parts below; its names are quoted in the middle column and
are provisional until plan 55 is committed. Where the draft and this section differ, the committed plan 55 wins and this
section is edited before Task 4 starts (rule 6).

What Task 4 needs, by role. The last column is `web/app.js` at `9b6f988`, the fallback of rule 3:

| Role (UI) | Plan 55 draft part (provisional) | At `9b6f988` |
|---|---|---|
| list row (UI-1) | `projectGroups()` and `listHtml()` (its Task 4): a group's `live` list takes any row, `listHtml`'s `item(x)` picks the drawer; this task pushes build rows into `live` and adds one `item` branch calling `buildHtml(b)` | `taskHtml(x)` in `chainHtml()` (app.js:2855), grouped by `chainGroups()`, mark `taskMark(t)` (app.js:70) |
| head (UI-3) | `pageHead({eyebrow, back, title, pill, facts, right, cost})` (its Task 1) | the `ihead` markup in `inspTask(t, d, row)` (3904) |
| section (UI-4) | `sect(label, sub, body)` and `foldLine(key, text)` (its Task 3) | `<div class="blk"><span class="lbl">` blocks. There is **no `sect()` function** in `app.js` today: only the locked mock has one |
| plan row (UI-5) | `planRow({mark, n, kind, route, goal, check, tone, cost, pick})` and `svLine` (its Task 3) | `stepRowHtml` (1096), `stepRows(t)` (2918) |
| dock card (UI-7) | `dockCard({tag, tone, q, why, body, left, right})` (its Task 2) | `dock(head, body, buttons, tid, composer)` (3302) |
| bar and buttons (UI-8) | `barHtml({icons, use, words, bar, primary}, fn)`, `actBtn(a, cls, {fn})`, `iconBtn(a, fn)`; `fn` names the dispatcher, written as `data-aid` plus `data-afn`, tasks use `"runAction"` and this task passes `"buildAct"` (its Tasks 1 and 2) | `stepFooter` (3485), the task menu (`go`, 3961) |

What Task 4 gives plan 55's list and page switch: `buildHtml(b)` (the row; plan 55's draft names it too), `inspBuild(b, d)`,
`inspNewBuild()`, `buildLine(b)` and `buildAct`. Its signature is whatever plan 55's delegated click handler passes for
`data-afn="buildAct"` (the action id and the button); fixed when plan 55 is committed. The list calls `buildHtml` once
per `snap.builds` row, in the group of `b.project_dir` and in the Needs-you pin when `b.group === "needs"`, after the
task rows; the page switch calls `inspBuild` when `boardBuild` is set. Plan 55 states that it draws no build row, page or
form and adds no `boardBuild` state: that matches this task.

Rules:

1. The page decides nothing. Tag, sentence and buttons are `actions.tag`, `actions.why` and `actions.primary/bar/menu`
   (README 4.7), passed to `dockCard` and `barHtml` as an actions-shaped object; an action with `off` is greyed with the
   reason as its title; `post: ""` is a page move (`open_card`, `open_task`), not a request.
2. Build pages use plan 55's head, section, plan-row, dock and bar functions with build data and write no CSS beyond one
   modifier class (`.v-bd`) and the New build fields (the Hand off task form's classes).
3. If a part is missing when Task 4 starts, use the fallback column through one-line wrappers: `buildHead(b, d)`,
   `buildSection(label, sub, body)`, `buildDock(b, d)`, `buildBar(b, d)`, `buildPlanRow(item)`. Plan 55 then swaps the
   wrapper bodies, not the page.
4. Plan 55 owns the project groups (UI-1). Until they exist the build row sits in the group `b.group` names, as task rows
   do.
5. The locked mock draws none of the build states. Ready, Drift, Held, Cap, Accept, Paused and Project use the dock card and
   bar rules of UI-7 and UI-8 ("preparing, paused, stopped, stuck and handed states use the same dock card and bar
   rules; they were not drawn", `08-design-lock.md`). They are new design for Fred to look at after the first build.
6. When plan 55 commits, check: the final names of the six roles and the signature `buildAct` must have; whether
   `boardPick` keeps its values (`"t"`, `"p"`, `s<n>`); whether its dock takes (tag, sentence, why, buttons); whether its
   list can take a third row kind; whether the Prep page stays on `prepHtml` (the "Start, and run the rest automatically"
   button lives there); whether `taskMark` still takes a state; whether plan 55's `ACT_COPY` map may carry build action
   ids. Edit this section, then start.

## State

- `let boardBuild = "";` beside `boardTask` (app.js:110): the picked build (`""` none), in memory like `boardTask`;
  `boardPick` is `"b"` on the build head. It is **not** saved in `window.json`: `Handler._draft` (server.py:4663) accepts
  only `project, brief, effort, board_tab, folds`, and a reload shows the build row one click from its page. Picking a task
  or a card clears `boardBuild`; picking a build clears `boardTask`.
- `let buildData = null;` `{id, sig, data}` of `GET /api/build`, fetched when the pick changes and when the row's
  signature changes (`buildRowSig(row)`: state, why, current, spent, updated, item.state), as `taskRowSig` (1854) does.
- `let newBuild = null;` the New build form's draft `{project_dir, folder, goal_file, title, level, cap, items, digest,
  busy, error}` while the form is open.

## The row (`buildHtml(b)`, drawn by `chainHtml` after the task rows of the same group; by `listHtml`'s `item(x)` once plan 55's list exists)

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
- Sections (UI-4): **Goal** (the goal file path with `copyBtn` (1472), or "no goal file", and the folder); **Sub-plans**: one
  row per item, the UI-5 row (rail mark, `two(n)`, title, the state word, `money(cost)`): a row whose item has a task is a
  link that calls `openTask(item.task)` (3192); a `ready` row opens its card (`openTask(item.prep)`: a Prep id is a Board
  pick already); a `drift` line under the row when `item.drift_note` (`◆ drift minor · <note>`, muted, the UI-5
  supervisor-line style); **Done** when `d.summary`: accepted / skipped / failed counts, the files list as a fold, the open
  questions fold (reusing `questionsFold`'s shape, 3759).
- The dock card (UI-7) from `d.actions`: the tag is `actions.tag`, the sentence `actions.why`, the buttons the listed
  `primary` and `bar` actions with the primary at the right edge. `Raise cap` carries a number input (`data-bcap`) whose
  value rides in the body. `Open the card` / `Open the task` are page moves (`openTask`), not posts; `actions` lists them
  with `post: ""`.
- The bar (UI-8): Folder (`/api/open_folder` on the build folder's absolute path, which `d.build.project_dir +
  folder` gives), Delete (two clicks, `confirm: true`), the spend figure, then Stop, Pause after this sub-plan /
  Resume, from `d.actions.menu` and `.bar`. No message box: a build takes no words; the task's page has it.
- "Start, and run the rest automatically": in `prepHtml(c)` (app.js:1161), when the card carries `c.build` (Task 2 saves the
  context on the card) and that build is at `gated` (`snap.builds.find((x) => x.id === c.build.id)`), a second Start
  button (`data-start-auto`) that posts `/api/build/level {build, level: "auto"}` and then runs `startCard(c, button)` as
  the first Start does (`startCard`, 1230, sends its ordinary body; the service makes the task `auto` by D9, README
  2.1, so no body field is added); hidden when the build is already `auto`. The card also shows the planner's drift note
  above the step list when `c.planner.drift` is `minor` or `major`, as the scope note is shown (one muted line, the word as
  a tag), and its error when `c.planner.error` is set (plan 47 shows it already).

Actions: `buildAct(name, button, id)` beside `taskAct` (1863): posts `/api/build/<lever>` with `{build: id}` plus `n`
(skip), `level`, `cap_usd`, `again` (prep_again); on 409 the error shows in the busy box (`busyBox`, 3286) as task actions
do; then `actRedraw()` (1862).

## New build (the form)

`headerMenu()` (app.js:1018) gains `item("newbuild", "New build…", "a folder of sub-plans")` after Measure; `go("newbuild")`
(3961) opens `inspNewBuild()` in the inspector pane: fields project (the scope's project preselected; `projectRows()`
(906) for the list), folder (text), goal file (text, optional), title (optional), level (a two-word segment, gated
pressed), cap (a number, `cfg.tuning.build_cap_usd.value` prefilled); **Preview** posts `/api/build/preview` and lists
the items with a checkbox each (all checked), their titles, word counts and `warnings` (muted, one line each), and the
goal file's state (`found` / `not found`) with its `goal_warnings`; **Create** posts `/api/build` with `keep` = the
checked `file` paths and the preview's `digest`, then picks the new build. A 409 "the folder changed since the preview"
shows under the form and clears the list so Preview runs again. Errors (400 / 403) show under the form. Nothing starts: the
page says so under Create ("Creates the build. Start is on its page.").

## The Models page row (README D4; Task 1 added the key)

The Models page draws only keys with a `TUNE` entry and groups with an `MGROUP` entry (`tuneRow` 2585, the `MGROUP` loop
2633). Two entries, beside the supervisor's: `TUNE.build_cap_usd = ["Build cap", "$", 1]` and `MGROUP.build = ["Build",
"spend cap of a build", "The most one build may spend on its sub-plans (task steps, Prep and the planner) before it
waits for you. 0 means no cap. A new build starts with this number; the New build form can change it."]`.

## Style

`web/style.css`: the build row reuses `.v-tk` / `.v-th` (style.css:913-923; one modifier class `.v-bd` for the mark's rail
colour from the existing tokens); the page reuses the inspector's section, row, dock and bar classes; the New build form
reuses the Hand off task form's field classes. No new tokens, no emojis, no em-dashes.

## Tests (first, red), `tests/test_web.py` (the Node harness; `render(expr)`)

- `BuildRowTest::test_build_line_per_state`: `buildLine` on a waiting row -> `["needs you · sub-plan 3 ready: Start",
  "y"]`; done -> `["done · 8 sub-plans · $84.20", "g"]`; running with a task row in `snap.tasks` -> starts with
  `build · 3 of 9 · 03 ` and carries that task's line; stopped -> `stopped · 3 of 9`; waiting on a project -> `needs
  you · project: ...`.
- `BuildRowTest::test_build_row_in_its_group`: `chainHtml()` with one build in `needs` and one in `done` draws each
  under its group head, after the task rows.
- `BuildPageTest::test_head_sections_and_rows`: `inspBuild(b, d)` has the eyebrow, the meta line's three facts, one
  row per item with the state word and cost, a `data-open` on rows with a task, the drift line under the item that
  has a note, and the Done section only when `d.summary`.
- `BuildPageTest::test_dock_and_bar_follow_actions`: with `d.actions` of the Cap state the dock shows `Cap`, Raise cap (with
  the number input) and Stop and nothing else; with the Ready state the primary is Open the card; with a Held state
  Continue, Prep again, Skip and Stop; the bar lists only what `menu` and `bar` name; an action with `off` is disabled
  with the reason in its title; the page contains no sentence of its own (the tag and sentence are the `actions` strings).
- `BuildPageTest::test_start_auto_button_on_a_build_card`: `prepHtml(card)` with a card whose `build` is a gated build
  shows the second Start; not when the build is `auto`; not on a card outside a build; the drift note line appears for
  `minor` and `major`, not for `none`; the second Start's handler posts `/api/build/level` and then `/api/task` with the
  ordinary body (no `supervisor_mode`).
- `NewBuildFormTest::test_form_preview_and_create_bodies`: `inspNewBuild()` has the six fields and Preview; after a
  preview the items have checkboxes and their warnings; the Create body (`newBuildBody()`) carries `keep` of the checked
  `file` paths, the `digest`, the level and the cap as numbers.
- `ModelsBuildCapTest::test_build_cap_row_and_group`: with `cfg.tuning.build_cap_usd` present the Tuning tab has a
  `Build` card with the `Build cap` row, default 25; without the key (an older service) nothing is drawn and nothing throws.
- `node --check web/app.js` clean; headless Edge at 900 and 400 px with the fake claude: no page error, no horizontal
  scroll (the live_window_check script, as plan 24 Task 4 did, or plan 55's helper if it exists).
