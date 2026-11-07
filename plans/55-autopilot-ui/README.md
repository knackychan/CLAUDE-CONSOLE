# Plan 55: The autopilot Board. The locked UI built into web/, reading `actions` only

Status: written 2026-11-07, plan only (no product code, test or config changed by its writing). D1 to D14 below are
written as defaults with the recommended option first; Fred confirms or changes them before Task 1 starts. Plan 52
D9 (a): "a plan of its own after Task 6, reading `actions` only". Lands on plans 48 (the Board in three moments),
50 (Models Supervisor card), 51 (Reject view), 52 (Task 6 `actions`, Task 8 design lock UI-1 to UI-9), 38 (open
tasks 4 to 7 and 9) and leaves a seam for 53 (Task 4, the build row and page).

Design target: `design/rework/locked/workflow-autopilot.html` (Fred, 2026-10-20). Tokens, type and the cell motif
are Console Cells, unchanged. The mock's strings are the copy; where this plan changes one it says so (section 4).

| # | File | Delivers | Depends on |
|---|---|---|---|
| 1 | [01-head-and-seam.md](01-head-and-seam.md) | the seam (`acts`, `actBtn`, `runAction`), the page head on the opened task (UI-3), the level switch, `tests/live_board_check.py` | none |
| 2 | [02-dock-box-bar.md](02-dock-box-bar.md) | the needs-you dock card (UI-7), the message box hints (UI-8), the bar with icon tools and no menu (UI-8, UI-9); the ⋯ task menu, `supCard`'s pending card and the attention gates go | 1 |
| 3 | [03-body-and-plan.md](03-body-and-plan.md) | the body sections (UI-4: Prompt, Brief, Plan), the plan timeline with `◆ Supervisor` lines (UI-5); `routeHtml`, `gaugeHtml` and the quiet `supCard` go | 2 |
| 4 | [04-list.md](04-list.md) | the list (UI-1: Needs you pinned, one group per project, dashed observed rows) and steps under a running row (UI-2) | 2 |
| 5 | [05-step-page.md](05-step-page.md) | the step page (UI-6: head with ‹ ›, tabs Chat, Received, Handoff, Files, the chat as a thread) | 3 |
| 6 | [06-states-and-check.md](06-states-and-check.md) | the unshown states (preparing, paused, stopped, stuck, handed, accepted), the observed page, the page-driven headless acceptance (plan 52 Task 7's HTTP steps become clicks) | 4, 5 |
| 7 | [07-close.md](07-close.md) | Fred's live look, PLAN.md row and History, CLAUDE.md Board line, plan 38 and 52 notes | 6 |

Tests first in every task (`tests/test_web.py`, the Node harness), one commit per task, the full suite
`py -m unittest discover -s tests` in the background at each boundary (last known good 1167 OK), `node --check
web/app.js` after every web edit, and `py -m tests.live_board_check` (Task 1 creates it) at 900, 400 and 340 px,
dark and light, reduced motion and 130 % text scaling. Other chats edit `web/app.js`, `PLAN.md`, `BRAINSTORM.md` and
`CLAUDE.md` in parallel: anchor every edit by the quoted line, never by a line number, stage explicit paths, never
stage `console/__main__.py`. Line numbers below are those of `9b6f988` and are for finding, not anchoring.

## Decisions (open for Fred; recommended default first)

| # | Question | Default (recommended) | Other option |
|---|---|---|---|
| D1 | Task order | (a) head, then the action surface (dock card, box, bar), then body, list, step page: Fred's plan 52 live check needs Accept, the decision options, Approve and the level switch on the page, and today only HTTP reaches them (section 6) | (b) the list first, as the prompt's example order |
| D2 | Where the mock's button words come from | (a) a small web map `ACT_COPY` keyed by action id (and a `TIP` map for tooltips); `actions` stays unchanged, as UI-9 says ("Task 6 `actions` is unchanged") | (b) change the labels in `Hub.actions` (touches `test_server`, `live_autopilot_check` and the README 52 section 3 wording Fred confirmed on 2026-11-07) |
| D3 | Buttons the mock draws that `actions` does not list (section 4.2: Approve and auto accept; Run on opus instead; Terminal and Folder icons on stuck and stopped tasks; "Retry on a stronger model" as one click; Edit steps and Edit prompt on a saved planned task) | (a) not drawn; a later server plan lists them in `actions` and the page draws them with no web change but an icon or a copy line | (b) a Task 0 here adds them to `Hub.actions` first |
| D4 | The head's level switch (UI-3 shows gated / auto) | (a) two words, gated and auto; when the task is at off or suggest, that word shows too, pressed, so the state is never hidden; off and suggest are set per project on Models | (b) all four words in the head |
| D5 | Notes for Reject and Retry | (a) both take the message box's text as their note (the mock's hints: "Why not, or what to do instead", "Tell the agent what to try differently on the retry"); Retry's model picker opens inside the dock card | (b) keep today's separate note boxes (Reject's second click, the retry form's own textarea) |
| D6 | The spend figure "of $5" in the bar | (a) dropped: no per-task budget exists (`supervisor_work_usd` counts only auto-dispatched work); the bar shows the task's spend | (b) show `of $` + the supervisor work cap when the level is gated or auto |
| D7 | The Prompt section (Fred's typed words; the mock's "you, 08:10") | (a) GET /api/task gains one read field, `prompt` (the task folder's `prompt.md`, masked), in Task 3; no gate, no write | (b) only the Brief section until a later plan |
| D8 | The Risky chip in orange (mock `.chip.y`) | (a) ink, like the other chips: style.css's rule is "orange means needs you and nothing else" | (b) orange as drawn |
| D9 | The status marks (mock: 8 px squares that blink) | (a) keep plan 21's locked status sprites in the list rows and on the plan rail (Fred picked them; they already follow Windows animation effects) | (b) the mock's squares |
| D10 | The list beyond the mock (Done days, Older, Select to delete, empty chats, step 00) | (a) per project: live rows, today's done rows, then one "Done earlier · N" fold that opens that project's days; Older stays one row at the end; Select done tasks stays on the day groups; empty chats stay behind the header menu; the step 00 row leaves the list (the Brief section links to it) | (b) one global Done group under the projects |
| D11 | The Needs you pin under a project scope | (a) the pin always spans all projects (the mock says "all projects"; the header's "N need you" button counts the same set); the project groups follow the scope | (b) the pin follows the scope |
| D12 | The step page's tabs and step-level actions | (a) Chat, Received, Handoff, Files; the Route tab's facts move to the head meta (Model, Took); the Plan tab goes (plan.md opens from the task page's Plan section and the plan card's "Read or edit the plan"); "Add step from here" stays on an older step, reading the served `levers.add_next` and `sources` reasons (a step-level action `actions` does not carry) | (b) also drop Add step from here |
| D13 | The observed page for a session row (a VS Code or terminal chat that is not a task) | (a) the session page gets the UI-3 head and the UI-8 bar, its buttons still from GET /api/levers (the service's gates, not rebuilt); a saved task with an external session reads `actions` like any task | (b) GET /api/levers also returns `actions: Hub.actions(row)` (Fred named `Hub.actions` accepting a session row on 2026-11-07, but no route serves it) |
| D14 | The states the mock did not draw (section 5) | (a) as specified in section 5 (new design, reusing the dock card and bar rules), shown to Fred as screenshots at stop 1 before Task 3 | (b) Fred draws them in the mock first |

## 1. The seam: `actions` decides what shows and what is enabled

CLAUDE.md (Plan 52 Task 6): "GET /api/task `actions` serves the aligned state, row text, primary/bar/menu actions,
message availability, Reject hint and recovery; place these without rebuilding the gates." The page reads
`d.actions` (`boardData.data.actions`) to decide which controls exist and whether each is enabled (`off`), and the
other fields of GET /api/task only as data to show (title, steps, costs, the decision's question and options' text,
the supervisor's audit, the summary, the plan). A form opened by an action with `post: ""` keeps its existing route
and its existing server-side checks.

Display rules that read `off` are allowed and are not gates: an action in `primary`, `bar` or the dock card is drawn
and greyed with `title=off`; a word action from `menu` is drawn only when `off === ""`; an icon from `menu` is always
drawn, greyed with `title=off` when off. A state word picks presentation only (the pill, the dock card's tag, the box
hint); it never enables a control.

### 1.1 Client-side availability tests that `actions` replaces (each deleted in the task that adds its replacement)

| Today (`web/app.js` at `9b6f988`) | What it decides | Replaced by | Task |
|---|---|---|---|
| `taskButtons` (3718): `cs.state === "running" && lv.stop === "" && (!turnOver \|\| queued)`, `lv.resume === ""` with `followUp`, `sl.continue === "" && srow.window && srow.state === "interrupted"` (chatresume), `lv.pause === ""`, `doneConfirm` | Stop / Resume / Start task / Pause / Finish confirm | `actions.bar` and `actions.primary` (`stop`, `pause`, `resume`, `start`, `finish` with `confirm`) through `barHtml` | 2 |
| `taskMenu` (3732): `d.handoff_available === ""`, `lv.done === "" && t.state !== "done"`, `lv.add_next`, `lv.retry`, `lv.stepdone`, `lv.redo`, `sl.terminal`, `srow.rules_warn`, `sup` (mode segment), `lv.clear` | the ⋯ menu entries | `actions.menu` (icons and words) and `actions.bar`; levels in the head | 1 (levels), 2 (rest) |
| `attentionArea` (3796): `row.asks && !gap`, the Plan gap regex, `replan`, handed without `handoff_to`, `["waiting","stuck","stopped"].includes(t.state) && (t.why \|\| failed)`, `lv.confirm === ""`, `row.paused_after && lv.resume === ""` | which gate box shows and its Confirm button | `actions.state` picks the dock card; its buttons are `actions.primary` plus the bar ids the dock takes (section 2 of Task 2) | 2 |
| `confirmLabel` (1847): parses `t.why` (`replanned:`, `plan ready: confirm`, `plan .* KB, over`, `row.hold`) into a label | the Confirm button's words | the action's own `label`, through `ACT_COPY` | 2 |
| `supCard` (3834) pending branch: `sup.mode === "off"`, `SUP_HEAD[p.status]`, `p.can_approve`, dismiss statuses, `p.can_reject`; rejected branch: `d.message.mode === "next"` | Approve / Reject / Dismiss and the after-Reject text | `actions.state === "suggestion"` (`approve`, `reject` or `dismiss` with `wake`), `actions.hint` and `actions.line` after Reject | 2 |
| `replanBox` (3679) `b()`: `lv.confirm`, `lv.keep`, `lv.stop` | Confirm plan / Keep old plan / Stop | `hold` state actions (`confirm`, `keep`, `stop`) in the dock card and bar | 2 |
| `inspGap` (3700) `b()`: `lv.redo`, `lv.stop` | Redo design / Stop on a Plan gap step | `decision` state bar (`redo`, `stop`) on the task page; the step page shows the bar of the task | 2 (task), 5 (step) |
| `stepButtons` (3291): `s.n === t.current` returns `taskButtons` | the current step's bar | the task's `barHtml` on every step page | 5 |
| `taskMessageState` (3535) fallback branch when `d.message` is missing: `!cur.session`, `row.run_live \|\| BUSY`, `t.state === "done"`, Plan gap and `lv.answer`, owner fred or stopped states, `lv.continue` | whether Send is enabled and why not | `actions.message` (`mode`, `reason`, `timing`, `target`, `attachments`, `cold`); the fallback branch is deleted, the page shows "Reading delivery availability. Draft kept." until GET /api/task answers | 2 |
| `taskMessageState`: `answer = gap \|\| !!(row?.stop_question \|\| tr.asks)` | Send answer vs Send | `actions.message.mode === "answer"` | 2 |
| `stepFooter` (3485): `d.message?.mode === "next"` | the box label | `actions.message.mode` (same value, read from `actions`) | 2 |
| `handedBox` (1702): `d.levers.retry === ""` and `d.handoff` | Retry form or Start next task | `handed` state: `start_next` primary; the Retry after a failed hand-off run is not served (section 4.2, D3) | 6 |
| `recoveryBox` (3768): `lv.retry`, `lv.stepdone`, `lv.resume`, `lv.stop` (text lines only, no buttons) | which recovery sentences name an action | the ids present in `actions` (recovery filtering is server-side, README 52 section 3) | 2 |
| `inspTask` (3913): `retryOpen === t.id && (d.levers \|\| {}).retry === "" && !handed` | whether the retry form draws | the `retry` action is present and not `off` | 2 |
| `nextActions` (3475): `lv.add_next === ""`, `(d.sources \|\| {})[two(s.n)] === ""` | Add step / Add step from here | kept on older steps by D12 (served reasons, not a rebuilt rule); the latest step's Add step comes from `actions` (`add_step`, after Reject) | 5 |

Not replaced (data, not gates): `statusLine` (the list row's words; `actions` is per opened task, and running
`Hub.actions` for every row of every snapshot would cost the snapshot loop four gate reads per task), `taskShown`,
`stepShown`, `sessionLine`, `prepTaskHtml` (the Prep card keeps the Prep API, README 52 section 3), the next-step form,
the Hand off form, the composer's draft and retarget logic (client state), `renderLevers` on the session page (D13).

## 2. What plans 48, 50 and 51 lose and keep (README 52 section 6, checked against the code)

| Built | Fate | Where |
|---|---|---|
| Plan 48 opened-task head (`inspTask` `.ihead`, `taskBreadcrumb` on the task page, meta `supervised · mode`, `task <label>`) | replaced by the UI-3 head; the label chip moves to the head's title tooltip and `C` still copies it | Task 1 |
| Plan 48 `taskButtons` and the ⋯ `taskMenu` (Hand off task, Finish task, Add step on a model, Retry on a model, Accept step result, Redo design, Open in terminal, the mode segment, Open task folder, Delete, Models, Usage) | replaced by the bar (icons Hand off, Terminal, Folder, Delete; the state's words; primary at the right) and the head's level switch; Models and Usage stay in the header menu, where they already are (`headerMenu`) | Tasks 1, 2 |
| Plan 48 `attentionArea` gate boxes, `replanBox` buttons, `confirmLabel` | replaced by the dock card | Task 2 |
| Plan 48 `supCard` (pending card, last decision, "No decision yet") | the pending card becomes the dock card (Task 2); the quiet last decision becomes the `◆ Supervisor` lines in the plan (Task 3) | Tasks 2, 3 |
| Plan 51 the view after Reject (`supCard` rejected branch) | its text moves into the dock card, from `actions.line` and `actions.hint` | Task 2 |
| Plan 48 `routeHtml` (the route of step rows, the `proposed` rows of plan 49) and `gaugeHtml` (30 cells) | replaced by the plan timeline (Task 3) and the bar's context cells (Task 2); plan 49's proposed rows are already dead data since plan 52 Task 1 | Tasks 2, 3 |
| Plan 48 list grouping (Needs you / Running / Done by day) in `chainGroups` and `chainHtml` | replaced by the pin and the project groups (D10, D11) | Task 4 |
| Plan 48 D16 step rows under a running task (`stepRows`, `chainStepHtml`) | kept as UI-2, drawn smaller (glyph, `01 scout`, model, state) | Task 4 |
| Plan 48 D17 outside chats marked (`sourceChip`) | kept as UI-1's dashed card with the app in the status line | Task 4 |
| Plan 48 moments 1 and 2 (the composer, Enter, the Prep card with one Start, Ctrl+Enter raw) | kept unchanged (`renderCompose`, `prepHtml`, `startCard`) | none |
| Plan 48 message box modes (guidance, answer, `next`), D6, D11 to D15, pending guidance with Cancel, Dismiss and Resend | kept; the box is restyled (one line, hint as placeholder) and keeps every id and handler | Task 2 |
| Plan 48 section 7 recovery box | kept as text above the body; "(task menu)" in its sentences becomes "(bar)" | Task 2 |
| Plan 50 Models Tuning Supervisor card, Projects fold, nine limits, Tiers row, Usage block | kept unchanged | none |
| Plan 51 next-step message naming haiku / sonnet / opus, the uncertain card keeping its decision | kept (server); the uncertain card is a `suggestion` dock card with Dismiss | Task 2 |

## 3. Plan 38's open tasks (Fred's D1 to D6 stand; this only places the leftovers)

| Plan 38 task | With the new layout | Lands |
|---|---|---|
| 4 Settings out of the picker (D2 a) | still applies, untouched by this plan (the picker and the header are not in the mock) | stays in plan 38 |
| 5 340 px: legend and routes (D3 a) | half moot: the Board footer's legend (`bfoot` "?") describes the list's mini context cells, which Task 4 removes, so the legend line goes with them; the `...` page menu under 372 px still applies to the header | the legend: Task 4 here; the page menu: stays in plan 38 |
| 6 type and target floor (D4 b), roving strips | the floor applies to everything this plan draws: the mock's 10 and 10.5 px labels (`.lbl`, `.lv`, `.def`, `.sub .sm`, `.sv .sg`, `.seg button`) are drawn at 11 px, and its small targets (the level segment, the ‹ › step arrows, the tool pill) get `min-height: 24px`; the roving strips (calendar, Usage days) are not in this plan | the floor: every task here (each task's size scan in `live_board_check`); roving strips: stay in plan 38 |
| 7 home pane (D5 a), replied tone, copy, contrast, title, landmarks, `:active` | U8: with nothing picked on a two-column Board, the first pinned task opens (the task page is now the unit, not a step); U9: the step page's replied word is ink; landmarks: the list is a `<nav>`, the task page a `<main>`; contrast (`--off` one step darker in light, D6 a), the copy items and `:active` stay in plan 38 | U8, U9 and landmarks: Tasks 4 and 5; the rest stays in plan 38 |
| 8 clickable looks clickable (done) | its rule binds the new parts: plan rows have hover, focus and a chevron (UI-5); the Prompt and Brief fold lines get a caret, `cursor: pointer` and the raise hover; their preview text stays muted (a preview, not a label; flagged in Task 3) | Tasks 3, 4 |
| 9 Fred's live check | one sitting with this plan's Task 7: the same widths, 100 % and 130 % | Task 7 |

## 4. Copy: the mock's words, and where `actions` differs

### 4.1 Words taken from the mock (D2 a: `ACT_COPY` and `TIP` in `web/app.js`)

| Action id (state) | `actions.label` | Drawn as (mock) | Tooltip (mock) |
|---|---|---|---|
| `confirm` (plan_ready) | Confirm plan | Confirm | |
| `confirm_auto` | Confirm, and run plans automatically from now on | Confirm and auto accept | Confirm this plan, and set the project to auto: later plans run without asking |
| `default_auto` | Take the default from now on | Take default and auto accept | Take the default here, and set the project to auto: later defaults are taken after N min |
| an option key (decision) | the option text | a selectable row `a  PRODUCT_SHEETS_DIR, as in T02` and the button `Confirm a` | |
| `edit_plan` (plan_ready, moved from the bar to the card, UI-9) | Edit plan | Read or edit the plan | |
| `confirm` with `confirm: true` (hold, Fable) | Confirm | Confirm Fable | |
| `reject` (suggestion) | Reject | Reject | Turns it down; a note in the box below says why |
| `continue` (observed) | Continue as a fork | Continue (fork) | Continue as a fork: a new Console run with its levers |
| `verify`, `escalate` (observed) | Verify as a fork, Escalate as a fork | Verify (fork), Escalate (fork) | |

`N` in the `default_auto` tooltip is `decision_timeout_s / 60` from `cfg` when the config page serves it, else the
sentence ends at "auto". Everything else draws `a.label` unchanged.

### 4.2 Mock buttons `actions` does not list (D3 a: not drawn)

| Mock | State | Why not drawn | What would list it |
|---|---|---|---|
| Approve and auto accept | suggestion | `Hub.actions` has no remember-auto Approve | an `approve_auto` action (`/api/task/supervisor` with `remember: "auto"`, a new body field) |
| Run on opus instead | hold (Fable) | no action names a rung swap at a Fable hold | a `run_instead` action on the existing retry route with `model` |
| Terminal and Folder icons | failed twice, stuck, stopped | the stuck and stopped menus list Delete only | `terminal` and `folder` in those menus (one line each in `Hub.actions`) |
| Retry on a stronger model (one click) | failed twice | `retry` is a form (`post: ""`); "one model up" is a routing rule the page must not compute | a server `model: "up"` on the retry route |
| Edit steps, Edit prompt | ready (saved planned task) | no editor exists for a saved planned task; the Prep card's editors serve Prep jobs only | an editor plan; until then a ready task shows Start and Drop |
| (not in the mock, a loss) Add step on a model, Finish task | running, decision, plan_ready, a replied chat task | today's ⋯ menu has both on any task; `actions` lists `add_step` only after a Reject and `finish` only on stuck, stopped and failed twice. A chat task (plan 42) can then not get a next step or be finished from its page until it stops | `add_step` and `finish` in `common_menu` (two lines in `Hub.actions`); Fred decides with D3 |
| (not in the mock, a loss) Retry on another model when a handoff run wrote no note (plan 40) | handed | the `handed` state lists `start_next` and Delete only; `handedBox` read `d.levers.retry` | `retry` in the handed menu when `lv.retry == ""` |

### 4.3 Copy this plan writes (not in the mock; flagged for Fred at stop 1)

The pill words of the unshown states (section 5), the dock sentences for stuck, handed and accepted, the box hint
"Write what to do instead" after Reject (from `actions.hint`, server copy), the Finished card's sentence
`N steps passed. F files written.` (the mock's "6 tests pass, the build is clean" needs a test count the summary does
not carry), the arm text of the two-click actions (section 2 of Task 2), "(bar)" in the recovery sentences.

## 5. The 400 px window, the pill, Prep and Usage; the unshown states

Coexistence (design lock "Not covered"): the folded pill (`renderFolded`), the 400 px compact window's session list
and session page, the Prep card and inspector (`prepHtml`, `showPrep`, `inspJob`) and the Usage page keep their locked
files and their code; this plan does not touch them. The Board is a page of the one window (plan 25): at 900 px it is
two columns (list 300 px, task page), under 700 px container width it is one column, the list or the opened page with
the existing `.v-back` row (`style.css` `@container (max-width: 699px)`), as the mock's own rule hides the list. The
mock's 400 px screenshot is exactly that one-column page; nothing new is needed for 400 and 340 px beyond the size
scans. A Prep job row opens the Prep card as today (the card is not a task page); its Start creates the task, whose
page is this plan's.

States the mock did not draw (D14 a, new design built from the dock card and bar rules, Fred looks at stop 1):

| State | Pill (tone) | Dock card | Bar (from `actions`) | Box |
|---|---|---|---|---|
| preparing | (no task page: the Prep job row and `inspJob` as today) | none | none | none |
| ready | Ready to start (y, as the mock) | none | Drop; Start primary at the right (orange `you`) | hidden (README 52 section 3: no box) |
| paused | Paused (q) | none: Fred paused it himself, nothing needs him | Stop; Resume primary (ink `go`) | guidance hint: "Message the agent; it reads it after Resume" (from `message.timing`) |
| stopped | Stopped (q) | none | Finish; Resume or Retry on a model primary (ink); Delete icon | guidance hint, Send off with `message.reason` |
| stuck | ✕ Stuck (r) | red card, tag "Stuck", the sentence `t.why`, buttons: See the failure (opens the failed step), Accept step result, Retry on a model (primary) | Finish, Delete icon | "Tell the agent what to try differently on the retry" |
| handed | Handed off (q); with a saved note and no follow-up, ? Handed off (y) | card tag "Handed off", the sentence "The handoff note is saved. Start the next task from it.", the note as a fold, button Start next task (primary) | Delete icon | hidden |
| accepted | ✓ Accepted (g) | the Finished card, without Accept | Hand off icon, Folder icon, Delete icon | next-step hint |

## 6. Stop conditions (Fred looks before the next task starts)

- **Stop 1, after Task 2**: the opened task's head, dock card, box and bar in every state (the mock's nine and section
  5's six), 900 and 400 px, dark and light: `py -m tests.live_board_check --shots <scratch folder>` writes the PNGs;
  Fred looks and answers D14 and any copy in 4.3. Task 3 does not start before his answer.
- **Stop 2, after Task 4**: the list at 900, 400 and 340 px with a scope and without, the pin and a project with done
  days and observed chats. Task 5 waits.
- **Stop 3, after Task 6**: the whole set again, with 130 % text scaling; then Task 7 is Fred's live check.

## 7. The seam for plan 53 Task 4

Plan 53 Task 4 draws a build row and a build page "with the parts the locked mock already has". This plan names
those parts and keeps them free of task-only reads, so the build page passes its own data and its own act function:

- `pageHead({eyebrow, back, title, pill, facts, right})`: the UI-3 head (Task 1).
- `sect(label, sub, body)`: the UI-4 section (Task 3); `foldLine(id, preview, text)` the one-line fold (Task 3).
- `planRow({mark, n, kind, route, goal, check, tone, cost, pick})` and `svLine(...)`: the UI-5 row (Task 3).
- `dockCard({tag, tone, q, why, body, buttons})`: the UI-7 card (Task 2).
- `actBtn(a, cls, {fn})`, `iconBtn(a, fn)` and `barHtml({icons, use, words, bar, primary}, fn)`: buttons from any
  `actions`-shaped object; `fn` names the dispatcher (`"runAction"` for tasks; plan 53 passes `"buildAct"`), written
  as `data-aid` plus `data-afn` so one delegated click handler routes it (`data-act` stays the session levers')
  (Tasks 1, 2).
- `projectGroups()` and `listHtml()`: the UI-1 grouping (Task 4). A group's `live` list takes any row; `listHtml`'s
  `item(x)` picks the row drawer (`taskHtml`, `sessionRow`, `prepTaskHtml`, `reviewHtml`). Plan 53 pushes its build
  rows into `live` in `projectGroups` and adds one `item` branch to its own `buildHtml(b)`; no shared `listRow`.

The dispatcher's signature is `fn(button)` (Task 1's click branch: `window[button.dataset.afn](button)`); it reads
`button.dataset.aid` and finds its action in its own data, as `runAction` does. Plan 53's `buildAct(name, button, id)`
(its 04-window.md) becomes `buildAct(button)` or gets a one-line wrapper.

This plan draws no build row, page or form, and adds no `boardBuild` state.

## 8. Headless checks (every task)

`tests/live_board_check.py` (Task 1) reuses `tests/live_autopilot_check.py`'s `Rig` and `build_states` (import, no
copy): one scratch service, the fake claude, the real page in headless Edge. It opens each captured state and runs
the sweep: widths 900, 400, 340; `color_scheme` dark and light; `reduced_motion: "reduce"`; device scale factor 1.0
and 1.3 (WebView2's 130 %, as plan 36 Task 4). Per page it asserts no horizontal scroll, no page or console error, and
the task's own checks (each task file lists them). `--shots DIR` saves one PNG per state, width and scheme for Fred.
States that a scratch service cannot reach cheaply (hold on Fable, handed) are served by `page.route` on
`/api/task?id=` with a real GET body whose `actions` and task fields are overwritten in the check; production code gets
no seam.
