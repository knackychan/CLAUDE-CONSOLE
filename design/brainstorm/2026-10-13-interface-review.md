# Readability review of the Cells Board mockup (2026-10-13)

- Asked by Fred: "a lot of details and information, but those should be details, data for nerds, and not
  in plain sight. Keep what matters in sight and second-zone information behind a tab or a collapsable drawer."
- Reviewed: `design/rework/proposed/cells-board.html` (13 views, dark, plus tabs and scrolled positions shot
  for this review), against `2026-10-13-interface.md`, BRAINSTORM 7.5 and the locked Cells Drawer.
- Standing and not reopened: the Cells language, the Chat-first inspector, the bubbles, Received / Handoff,
  the one-column handoff view. ID-1 to ID-9 stay Fred's; comments on them are marked as such.
- Measured in the mock at 900 x 680 and 400 x 640 (heights in px, rounded).

## 1. Verdict

1. **What needs Fred is pushed below the fold by history.** On the list, the today breakdown is open by
   default (279 px of fills, legends and a model mix) and the first "Needs you" card starts 367 px down a
   640 px window. On the Board the chain is 1133 px tall in a 619 px pane: four done steps at five lines each
   fill the first screen and the FAIL of 05 and the running 5c sit below it.
2. **Every step says the same numbers three times.** A received word count shows on the connector chip, again
   as `in` on the next block, again in the inspector head and again on the Received tab. Rung, cost, time and
   context repeat between the picked block and the inspector head. Route notes, paths, thread ids, scales and
   "how it works" sentences sit in plain sight on almost every screen.
3. **Orange and the word "You" are spent on things that are not Fred.** The `scout first` hint, the balance
   chip in Route and the "replanned ... confirm on the Task page or the Board" line all burn orange next to the
   real waits; the first chat bubble is labelled You but is the prompt the service wrote.

The fix is the same everywhere: two-line rows for done things, a closed line for every block of provenance,
and one place per number.

## 2. Zoning principle applied

- **Zone 1, in sight**: what Fred acts on or checks at a glance. State (word + sprite), what needs him (a
  question, a replan, a FAIL, a handoff to start), the one figure that matters on that screen, the next action
  (the button), and the current step. A number is zone 1 only if it changes what he does now (cost of a run,
  context past 150K on a live step).
- **Zone 2, behind a tab, a fold or a drawer**: how and why. Route notes, rules, exact token and word counts of
  finished things, provenance (thread ids, paths, commits, `git diff --stat`), the checks, logs, scales and
  legends, config names (`balance_margin`, `replan_auto`), and every sentence that explains the design.
- **Cut**: a number already shown one line away, and a sentence that explains what a control does when the
  control's title can say it.
- **Closed state rule**: a fold is never silent. Its closed line is one row: `Label · the one number or fact
  worth seeing ▾`, in `--mut`, mono for figures. If the folded content holds a FAIL, an open question, a
  not-found or an over-pace, that word shows in the closed line in its state tone (red, orange), and a FAIL or
  a failing check opens the fold by itself. Folds remember their state per window (window.json), as the
  session page's brief fold already does.

## 3. Screen by screen

### 3.1 List (compact)

| Element | Now | Zone | Change |
|---|---|---|---|
| Today strip (Doto figure, 30 cells, `today, USD · $0.09 / min`, `limit $15`) | In sight | 1 | Keep as locked. |
| Today breakdown (`todaymore`, 279 px) | Open by default in the mock | 2 | Closed by default, as locked ("one click away"). The closed state is the strip itself plus, only when a model is over pace, one line under it: `3 models over pace · fills ▾` (figures in their tone). |
| Breakdown: spend legend, model mix (3 wrapped lines) | Plain | 2 | Stays inside the breakdown. Merge into one legend line: `opus 48 · sonnet 27 · codex 14 · haiku 9 %`; move `opencode · deepseek-v4-flash cost unknown · 2 runs` and `window runs 9` to a second muted line. |
| Breakdown: Fills (5 models x d / w / m, header `1 cell = 10 %, outline = pace`) | Plain, 5 columns of 3 rows | cut | The Usage page carries the fills. In the breakdown keep one line: `fills · opus 84 · sonnet 84 · gpt-5.6-codex 91 % of pace (day) · Usage ›`, over-pace figures in orange, no cells. Saves about 90 px and a second cell scale. |
| Replan card, why line | `replanned: 2 steps added, confirm on the Task page or the Board` (orange, 2 lines) | 1 | `replanned after 01: 2 steps added` (one line). The buttons are right under it; the "confirm on" clause goes. |
| Replan card, route slot `· haiku · low` | Plain | 2 | Hide on a waiting card: the rung of a replan pass is not what Fred decides. Title attribute keeps it. |
| Handed off card | why line (2 lines) + green chip (1 line) + Start next chat + `handoff note` | 1 | Three statements of one fact. Keep why `↻ handed off by itself at 312K` and chip `✓ handoff ready`; move `(auto hand off): one task = one chat` and `Start next chat seeds the task box` to the button's title. Link reads `handoff`. Card goes from 6 to 4 lines. |
| Working card, l2 `step 5c / 6 · verify · opus · medium` and the doing line `5c verify · opus · medium · reads the fix diff` | Rung said twice | 1 | l2: `step 5c of 8` (count the fix steps, as the Task page does); the doing line keeps `5c verify · opus · medium · reads the fix diff`. |
| Done rows, tag `step 4/4` | Plain | cut | A done task finished its steps. |
| Project name on cards (`CLAUDE-CONSOLE · ...`) | Plain | 2 | Hide when the scope is one project (the scope button names it); show under All projects. |
| ⇔ Board button | In header | 1 | Keep. |

Hierarchy: the Doto figure and the "N need you" chip should be the two loudest things; today the fills grid
(orange figures in five columns) out-shouts both. With the breakdown closed the eye lands on Needs you second,
as locked. Card titles are the only semibold text in a card; costs stay regular mono.

### 3.2 Task page (compact)

| Element | Now | Zone | Change |
|---|---|---|---|
| Head: sprite, `TASK · 3m`, title, `CLAUDE-CONSOLE / effort: auto · $4.62`, ⇔ Board | Plain | 1 | Keep. Title wraps to 2 lines (it does). |
| Head: path `C:\Users\fred\.claude\console\tasks\a7f3e` | Own line | 2 | Cut the line; the title's `title` attribute and a Copy path item on right-click hold it. |
| Steps header scale `in · ctx · out, 1 cell = 50 w / 10K` | Plain | 2 | Cut from the header; put it in the title of each gauge. Header reads `Steps · 8`. |
| Step row (76 px each, 3 lines: name + rung + cost + Open, gauges, goal) | 8 rows = 600 px, the running 5c below the fold | 1 / 2 | Done rows: 2 lines, `NN kind rung · cost · Open` and the goal (muted, one line). The gauge line (`in ctx out`) shows only on the current step, a failed step and a step past 150K; on the others it opens with the row (click the row, not Open). Saves about 22 px per done row (about 130 px on this task). |
| FAIL verdict on 05 | Sub line, red, truncated after `options after ...` | 1 | Verdict leads the sub line and takes it whole: `FAIL test_resume_command: options after resume`; the goal is dropped from a failed row's sub line. |
| `try 1 no HANDOFF block` on 5b | Sub line, plain | 2 | Keep only the attempt squares (red, green) on the row; the reason goes into the expanded row. |
| `· scout first` hint | Orange | 1, muted | Not a "needs you": `· scout first` in `--mut` with a `△` glyph, title `230 w in, 118K reached`. |
| Current step | Not scrolled to | 1 | The page opens scrolled so the current step is the third visible row. |
| Handoff block `Handoff for step 5c · after the brief pass` (raw `## ...` text + facts, 451 px) | Open | 2 | Closed by default. Closed line: `Handoff for 5c · 230 w · Next: check the fix against the FAIL detail ▾`. Opened, it renders the same six blocks as the Board's Received tab (not raw markdown), Facts folded inside it. The button `Show it as 5b wrote it` (clipped at 400 px) becomes a text link `as written` in the closed line's right side. |
| Levers `Stop`, `Pause`, `Retry, Clear off: task is running` | Plain | 1 | Keep. |

Hierarchy: the title and the current row should lead; today the HANDOFF monospace slab is the largest mass on
the page. With it folded, the steps list is the page. The cost column is the only right-aligned figure; keep the
gauges' figures regular, never bold.

### 3.3 Session page (non-Claude step)

| Element | Now | Zone | Change |
|---|---|---|---|
| Head: state, title, `task · step 3/8` link, `CLAUD...` + rung chip + New task here | Project name truncated to `CLAUD...` | 1 | Drop the project on a task step's head (the task link carries it); the rung chip gets the room. |
| Note line (`context unknown: codex reports a turn's spend · thread 019a3f…: Continue resumes it with codex exec resume · no hooks: Steps come from the stream`, 3 lines) | Plain | 2 | Cut from plain sight. The brief already says `context unknown`. Thread id and resume mode go to the Chat source line and the Continue button's title. |
| Brief (path Prep / Run / Verify / Hand off, spent, $ / min, context, session, events) | Locked | 1 | Keep. `events 31` duplicates the Steps tab count: drop it from the brief for non-Claude steps. |
| Chat source line `codex exec --json · thread 019a3f… · 31 events · ended 14:19:48` | Top of the pane | 2 | Move to the end of the chat, muted, as `ended 14:19:48 · codex exec --json · thread 019a3f…`; the top of the pane starts with the first turn. |
| Tool row `3 tool events · file_change, command_execution · exit 1` | `exit 1` cut off by the ellipsis at 400 px | 1 | Put the failure first: `3 tool events · exit 1 · file_change, command_execution`. Same order on the Board. |
| First turn labelled `You` (the prompt the service built) | Violet, full text | 2 | See 3.8 Chat pane: fold it, label `Prompt`. |
| HANDOFF chip + Next | In the last turn | 1 | Keep (Fred's decision). |
| Levers say line `Verify, Hand off, Escalate, Terminal off: claude only · a task step: use the task's levers for Stop` | 2 lines | 2 | One line: `claude only: Verify, Hand off, Escalate`; the rest in the disabled buttons' titles. |

Hierarchy: the title and the brief's spent figure (Doto) lead; the follow-up box and Continue are the action.
Nothing else on this page should be bold.

### 3.4 Settings popover

| Element | Now | Zone | Change |
|---|---|---|---|
| Find, All projects, Runs allowed, Runs off | Plain | 1 | Keep as locked: this is a project picker first. |
| Harnesses group (4 rows + 3 notes, about 230 px) | Open; the popover scrolls (613 px in 508) | 2 | One closed row under Runs off: `Harnesses · claude, codex on · cmd not found ▾`, the not-found part red with `△`. Opens in place; opens by itself when any harness is on but not found. |
| claude note `Prep and the brief pass run on it; it cannot be turned off` | 2 lines | cut | Title on `always on`. |
| cmd note (4 lines with the full config path) | Plain | 1 when open | `no cmdc.exe on PATH · set "exe" in config.json`; the full path in its title. |
| Group note `opencode and cmd rungs run read steps only ...` (4 lines) | Plain | cut | Title on the group label; the Prep select already enforces it with its own refusal line. |
| Window runs group + 4-line note | Plain | 2 | Closed row: `Window runs · auto hand off off ▾`. Open, the note is one line: `hands off a window run that ends in the red zone (300K)`. |
| Footer `↑ ↓ move · Enter pick · sorted: needs you, live, recent` | Plain | 1 | Keep. |

Hierarchy: the project names are the only ink-coloured text at rest; the harness rows today use the same weight
and pull the eye away from the pick. Closed, the two settings rows read as quiet muted lines.

### 3.5 Prep

| Element | Now | Zone | Change |
|---|---|---|---|
| You typed | Plain | 1 | Keep. |
| Scouted (3 lines of `path:lines`) | Plain | 2 | Closed line `Scouted · context pack 1.9 KB · 3 files ▾`. |
| Enhanced prompt textarea | Plain | 1 | Keep. |
| Run route: model select, effort select, `code` | Plain | 1 | Keep. |
| Route reason `rule code: write · balance: sonnet 84 % of pace -> codex ...` (2 lines) | Plain | 2 | Closed line under the selects: `why codex · balance ▾`. |
| No-cap warning (2 lines) | Plain | 1, short | One muted line with `△`: `no turn cap: stops at 1800 s`; the rest in its title. |
| Step rows (kind, model, remove, goal) | Plain | 1 | Keep. |
| Refused pick `opencode: read steps only (cheap tier) · back to auto` | Red under row 5 | 1 | Keep: it changed Fred's pick. |
| Verify row (3 lines of explanation) | Plain | 1, short | `6 verify · added after the last edit`; the tier rule in its title. |
| Paragraph `Run as task: each step's rung comes from ...` (3 lines) | Plain | cut | Title of Run as task. |
| `effort: auto (the rules pick per step)` | Plain | cut | Already on the composer. |
| `Prep $0.031 · 4 turns · haiku` | Plain | 2 | Keep as the last muted line, or in the Back button's title; it is history. |
| Levers (Run as task, Run, Run raw, Edit, Cancel) | Plain | 1 | Keep. |

Hierarchy: the prompt and the step rows are the page; today five explanatory muted blocks between them make the
steps start about 450 px down. With the folds the steps start about 300 px down and the whole plan fits two screens.

### 3.6 Usage

This page is second zone by nature (behind a button). Inside it the order should still put the answer first.

| Element | Now | Zone | Change |
|---|---|---|---|
| Head: Doto month total, month nav, `est. USD · 31.4M tokens · 13 days used` | Plain | 1 | Keep. |
| Four stats (today, week, avg, over $15) | Plain | 1 | Keep. |
| Models · fills, 6 models x 3 bars of 20 cells (509 px) | Open | 1 / 2 | One row per model: name, `via ...`, one 20-cell bar for the window with the highest share of pace (labelled `day`, `week` or `month`) and its figure, then `w 71 · m 52 %` as text. Click the row to open the three bars. Rows sort over-pace first. About 300 px saved. (ID-6 untouched: the cells stay 20.) |
| Header `share of pace · 20 cells = allowance · outline = pace` (truncated) | Plain | 2 | Move into the legend line under the block. |
| Orange sentence `orange figure: over pace, the router leaves ...` | 2 lines, orange | 2 | Muted legend item `orange: over pace`; the router sentence in its title. |
| Note `balance_margin 0.2 · warn_at 0.8 · ...` | Plain | 2 | Closed line `config · balance_margin 0.2 · warn_at 0.8 ▾`, or cut. |
| Verify FAIL rate by hour (heatmap, legend, 3-line reading) | Open | 2 | Closed line `Verify FAIL by hour · opus peaks 14:00 to 17:00 ▾`. Rung labels are truncated (`codex · gpt-5.6-cod`): use the model alone in the row label, the harness in the title. |
| Days (calendar, picked day, columns) | Locked | 1 | Keep as locked, and move it above the FAIL heatmap: the calendar is what the page was for. |
| Footer (estimate source) | Plain | 1 | Keep. |

Hierarchy: Doto total, then the four stats, then the over-pace models. Today the 18 bars of identical weight
make the page a grid of noise; one bar per model lets the orange figures carry the message.

### 3.7 Board: the chain

| Element | Now | Zone | Change |
|---|---|---|---|
| Folded task rows (2 lines: sprite, word, title, age; `CLAUDE-CONSOLE · effort auto · 6…`, cost) | `why` is truncated away on a waiting task | 1 | Line 2 of a folded row: the `why` in orange when waiting, else `N steps · cost`. Drop project (it is in the crumb) and effort. |
| Task head (picked task) | Title truncated at 300 px; `6 steps` (wrong: 8 with the fix) | 1 | Title wraps to 2 lines. Line 2: `step 5c of 8 · $4.62`; effort goes to the inspector. |
| Step block, done (89 px, 5 lines: l1, rung + time, ctx 30 cells, in / out / tries, sub) | All open | 1 / 2 | Two lines: l1 `sprite DONE NN kind ... cost`; l2 `rung · time` left and a 15-cell ctx mini gauge with its figure right (the list card's `.ctx` grammar). About 46 px. |
| Step block, current / failed / waiting / picked | Same 5 lines | 1 | Keep the full block, but drop the `in` / `out` line (see connector) and the tries squares when there is one passing try. Sub line keeps the verdict or the wait. |
| Step block, planned | 2 lines `PLANNED 03 code` / `rung at start (rule code)` | 1 | One line: `PLANNED 03 code`. The rule goes to the title. |
| `ctx unknown: opencode reports spend` (wraps to 2 lines) | Plain | 1 short | `ctx unknown`; the reason in the title. |
| `in` / `out` cells and figures on each block | Plain, duplicate of the connectors | cut | The connector above a block is what it received; the connector below is what it wrote after compaction. Keep the words on the connectors only. |
| Attempts squares (one green square on every done step) | Plain | 1 when > 1 | Show only when there were two tries or a failed one. |
| Connector, ok (`[10 cells] handoff 160 w`, 26 px) | Plain | 1 | Keep the cells (ID-5) but drop the word `handoff` on ok chips: `[cells] 160 w`. The footer legend says what a connector is. |
| Connector, cut | `handoff 290 w · cut 122 w` | 1 | `412 → 290 w · cut 122` with the l2 tone (ID-1 untouched). This replaces the `out 412 w` lost from the block. |
| Connector, fallback (`handoff as written, not compacted · verify FAIL`, truncated) | Truncated at 300 px | 1 | `as written · not compacted`; the reason (`verify FAIL`) in the title; dashed border stays. |
| Connector `5` drawn twice (inside the bracket and again before 06) | Bug in `chainHtml`: step 6 calls `connBlock(t, "5")` | cut | The connector before 06 is the one after 5c (`handoff: writing`); do not repeat `5`. |
| Connectors before planned steps (`no handoff yet` x 4 in the replan view) | Plain chips | cut | A dotted line with no chip between planned steps. |
| Fix bracket | Clear | 1 | Keep. The 5b hint `scout first: 230 w in, 118K reached` in orange becomes muted with `△` (not a "needs you"). |

Hierarchy: in the chain the state words and the step names are the only things that should read at arm's length.
Today the rung line uses ink bold (`.sb .rung b`) on every block and competes with the name; make the rung
`--mut` and keep `NN kind` the only semibold. With 2-line done blocks the whole running task (8 blocks, 8
connectors) is about 620 px: the FAIL and the live step are on the first screen.

### 3.8 Board: inspector, a step picked

| Element | Now | Zone | Change |
|---|---|---|---|
| Head line 1: sprite, word, `03 code` | Plain | 1 | Keep; put Open chat (and Stop when live) on the same line, right. |
| Head meta (rung, cost, time, context, then `in 310 w · out 412 w` on a second line) | 2 lines | 2 | One line: `rung · cost · time`. Context and in / out are on the picked block 300 px to the left and in the tabs. Head goes from 99 px to about 56. |
| Tabs `Chat 8 · Received 310 w · Handoff 412 w · Route` | Plain | 1 | Keep the word counts on Received and Handoff (they help choose), drop `8` on Chat. On a step with a cut, Handoff reads `Handoff 412 → 290 w`. |
| Chat: source line on top | Plain | 2 | At the end of the chat, muted (as 3.3). |
| Chat: first bubble `You` (the service's prompt, 9 lines) | Open, violet | 2 | Fold to one right-side row: `Prompt · goal and the handoff of 02 · 53 w ▾`, violet edge kept, label `Prompt`, not `You`. `You` is kept for what Fred typed (a follow-up, an answer). |
| Chat: agent bubbles, tool rows, HANDOFF chip | Per Fred | 1 | Keep. Tool rows put `exit 1` first (3.3). |
| Received tab header `Handoff it received from step 02 · 310 w · compacted by the brief pass · the only thing it got from the earlier steps` | Plain | cut | `From 02 · 310 w`. |
| Received / Handoff: six heading boxes, all open | Plain | 1 / 2 | Open by default: Goal, Findings, Open questions (when any), Next. Folded with a closed line: `Files touched · 4 · codex.py, fake_codex.py +2 ▾`, `Troubleshooting · 3 lines ▾`. |
| `never cut` labels and green edges on Goal and Troubleshooting | Plain, green | cut | Green is state; this is a rule. The handoff view's Checks say it (`Goal and Troubleshooting carried whole`). |
| Handoff tab header `raw 412 w · sent as 290 w after the brief pass` | Plain | 1 short | `For 04 · wrote 412 w · 04 received 290 w`. |
| Cut lines struck in place, `2 kept · 2 cut` | Per Fred | 1 | Keep. |
| Facts the service added (dashed box, diff stat + test lines, `zero tokens, never compacted`) | Open | 2 | Closed line `Facts · 4 files +325 · 23 tests OK ▾`; a failing test line puts `FAIL` in red in the closed line and opens it. |
| Route tab: Goal, route chips (5 to 6), Attempts | Behind a tab | 2 | Keep behind the tab. The balance chip is orange: make it muted like the others, with the over-pace figure alone in orange only if the doc's "model over its pace" rule is kept (ID-6 area, Fred's call). |
| Running step: `Writing. The handoff shows here when the run ends, checked by code before ...` | Plain | 1 short | `Writing. Shows here when the run ends.` |

Hierarchy: the chat text is the reading; the head should be one quiet line above it. The tab labels are the only
UI-font semibold besides `NN kind`.

### 3.9 Board: inspector, a handoff picked

| Element | Now | Zone | Change |
|---|---|---|---|
| Head `Handoff from 03 code to 04 test` | Plain | 1 | Keep. |
| Meta line 1 `03 wrote 412 w · 04 received 290 w · cut 122 w, 2 Findings lines` | Plain | 1 | Keep, the cut in the l2 tone. |
| Meta line 2 `brief pass: haiku · $0.004 · 2 turns` | Plain | 2 | Into the Checks fold's closed line. |
| `What 04 received` + `the cut lines stay in place, struck` | Plain | 1 / cut | Keep the label; cut the explanation (the strike says it). |
| Six blocks, one column, cuts struck in place | Per Fred | 1 / 2 | Open: the headings that hold a cut, Open questions when any, Next. Folded with closed lines: Goal (`Goal · whole`), Files touched, Troubleshooting (`· whole`). The reader came for what was cut. |
| Checks (5 green ticks) | Open, under the column | 2 | Closed line `Checks · 5 of 5 pass · compacted by haiku $0.004 ▾`; any failing check shows `1 FAIL: <name>` in red in the closed line and the fold opens by itself. |

### 3.10 Board: inspector, the task picked

| Element | Now | Zone | Change |
|---|---|---|---|
| Head: state, title, `CLAUDE-CONSOLE · effort auto · cost 4.62 · 6 steps · ~\.claude\console\tasks\a7f37f3e`; Stop, Pause | Plain | 1 / 2 | Meta: `step 5c of 8 · $4.62 · effort auto`. Path cut to the title's tooltip. Add one first-zone line: `Now 5c verify · opus · 2m 40s · next 06 document`. |
| prompt.md (6 lines, pre) | Open | 2 | Closed line showing the acceptance line: `prompt.md · Done when: 9 tests pass against the fake ... ▾`. |
| Open questions (3 rows; header `from the briefs, the step that opened and the one that closed ...`) | Open | 1 | Keep the open ones in plain sight; closed ones fold: `2 closed ▾`. Cut the header explanation. |
| Chain log (23 lines of moves) | Open | 2 | Closed line `Chain log · 23 moves · last 14:38 5c running ▾`. |

### 3.11 Board: the replan wait

| Element | Now | Zone | Change |
|---|---|---|---|
| Head `WAITING 02 replan` + meta `claude · haiku · low · no tools · 1 turn · cost $0.005 · 6s` | Plain | 1 / 2 | Head line only; the meta goes to Route. |
| Askbox: `REPLANNED · after step 01`, question, Before / After lists, Confirm plan, Keep old plan, Stop | Two columns | 1 | Keep the box. The two lists become one list (Fred's rule for handoffs, applied here): the after plan, added steps tagged `added`, a dropped step struck in place, header `New plan · 6 steps (was 4)`. A comment on ID-7, not a decision. |
| `replan_auto is off: a changed plan waits for you. Turn it on in config.json ...` | 2 lines in the box | 2 | Title on Confirm plan; the box keeps no config talk. |
| Why it ran (3 lines) | Open | 2 | Closed line `Why it ran · 01's Next asked for a replan ▾`. The question in the askbox already says what was found. |
| Route chips (3) | Open | 2 | Closed line `Route · haiku, no tools, validated ▾`. |
| Chain: 4 planned blocks + 4 `no handoff yet` | 2 lines each + chips | 1 short | One-line planned rows, dotted lines with no chips (3.7). |

### 3.12 Board: measure, empty, footer

| Element | Now | Zone | Change |
|---|---|---|---|
| Measure head `median per kind · received, context reached, handoff written` | Plain | 1 short | `Measure · last 12 tasks · median per kind`. |
| Column headers `received · 25 w` etc. | Plain | 2 | Headers `received · context · handoff`; the cell scale moves to the legend. |
| Bars without figures | Plain | 1 | Add the figure after each bar (`240 w`, `112K`, `250 w`): the reading quotes numbers the table does not show. |
| The row the reading names (`fix`) | Same weight as others | 1 | That row in ink, the others in `--mut`; the reading sits directly under the table as it does. |
| Legend `context past 150K` (orange) | No bar is past 150K here | 1 | Show this legend item only when a bar is orange. |
| Reading paragraph (3 lines, ends with `This table is brainstorm 5.1 item 6 ...`) | Plain | 1 / cut | Keep the first sentence; cut the provenance sentence. |
| Empty chain | 30 off cells + one line | 1 | Keep. |
| Empty inspector `Nothing to inspect.` | Plain | cut | Leave the pane empty, or show Measure when the project has past tasks. |
| Footer keys `↑↓ step or handoff · ←→ task · Enter open the chat · Esc back` + scale `1 ctx cell = 10K · 1 word cell = 50 w` | Always on | 1 / 2 | Keys stay (short): `↑↓ step · ←→ task · Enter chat · Esc back`. The scale moves to the cells' titles and to a `?` at the right of the footer that opens a one-line legend (`ctx cell 10K · word cell 50 w · connector = handoff`). On the empty Board the keys hide. |

## 4. Prioritised change list

### P1: plain-sight clutter that hides what matters

1. List: today breakdown closed by default; closed line `N models over pace · fills ▾` only when over pace.
2. List: cut the mini fills grid from the breakdown; one `fills ... · Usage ›` line instead.
3. Board chain: done step blocks become 2 lines (l1 + rung, time, 15-cell ctx mini); full blocks only for the current, failed, waiting and picked steps.
4. Board chain: drop the `in` / `out` line from blocks; connectors carry the words (`160 w`; cut: `412 → 290 w · cut 122`).
5. Board chain: folded task rows show the `why` of a waiting task on line 2 (today truncated away); drop project and effort there.
6. Board chain: fix the duplicate connector `5` before 06 (`chainHtml`); no chips between planned steps; planned blocks one line.
7. Board step inspector: head meta to one line `rung · cost · time`, buttons on the head line; no context or in / out in the head.
8. Board Chat: fold the service's first prompt to `Prompt · goal and the handoff of 02 · 53 w ▾`, labelled Prompt, not You; source line to the end.
9. Task page: done rows 2 lines, gauges only on current / failed / past-150K rows; open scrolled to the current step; FAIL verdict takes the whole sub line.
10. Task page: Handoff block closed by default, closed line with words and Next; opened it renders six blocks, not raw markdown.
11. Tool rows everywhere: `exit 1` before the kinds, so the ellipsis never hides a failure (session page at 400 px hides it today).
12. Orange back to "needs you" only: `scout first` hint (chain and Task page) muted with `△`; the list replan line loses `confirm on the Task page or the Board`.

### P2: second-zone material that should fold

13. Settings: Harnesses and Window runs as closed rows (`Harnesses · claude, codex on · cmd not found ▾`, `Window runs · auto hand off off ▾`); notes to titles.
14. Prep: Scouted, route reason fold to closed lines; the Run as task paragraph and the duplicate effort line cut; verify row one line; no-cap warning one line with `△`.
15. Session page: cut the 3-line note line; `events` out of the brief; levers say line to one line.
16. Step inspector, Received / Handoff tabs: Files touched and Troubleshooting folded with counts; `never cut` labels and green edges removed; tab header lines shortened.
17. Step inspector, Handoff tab: Facts fold to `Facts · 4 files +325 · 23 tests OK ▾`, opening by itself on a failing test.
18. Handoff picked: Checks fold to `Checks · 5 of 5 pass · compacted by haiku $0.004 ▾`; only headings with a cut, Open questions and Next open.
19. Task picked: prompt.md folds to its Done when line; Chain log folds with its last move; closed open questions fold; add the `Now ... · next ...` line; path to tooltip.
20. Replan: Why it ran and Route fold; `replan_auto` sentence to the Confirm title; head meta to Route.
21. Usage: one bar per model (the binding window), click for three; FAIL heatmap folded with its reading in the closed line; Days above it; config note folded.
22. List cards: handed-off card down to why + chip + button; working card says the rung once; project hidden under a one-project scope.

### P3: polish

23. Chain rung text `--mut`, not ink: `NN kind` is the one semibold per block.
24. Counts agree: `step 5c of 8` on list card, task head and session page (today 6, 8 and 3/8).
25. Task head title wraps to 2 lines in the chain; the session head drops the truncated `CLAUD...`.
26. Fallback connector reads `as written · not compacted`, reason in the title.
27. Measure: figures after bars, the named row in ink, dead legend items hidden, provenance sentence cut.
28. Footer: shorter keys, scale behind `?`; keys hidden on the empty Board; empty inspector left blank.
29. Words (ID-9 area, Fred's call): "brief pass" still shows in plain sight in five places (connector title, Received header, Handoff header, handoff meta, Task page block); say `compacted` in plain sight and keep "brief pass" for titles.
30. Re-shoot the light theme: `light-step.png` still shows Note / Brief tabs and `brief 160 w` chips, so it predates ID-9.
31. Usage heatmap rows: model name only (`codex · gpt-5.6-cod` is truncated), harness in the title.

## 5. Risks: what a fold must never hide

- **A FAIL.** A failed step never takes the 2-line form; its verdict is the sub line, whole. A failed check, a
  failing test line in Facts, or an `exit 1` in a tool row puts the red word in the closed line and opens the
  fold by itself. Tool rows put the exit first so truncation cannot eat it.
- **A question or a wait.** Waiting tasks keep their orange `why` on the folded chain row and on the list
  card; the replan askbox is never folded. Open questions stay open in the task inspector and in the Received /
  Handoff tabs whenever any is open; the closed line counts them (`Open questions · 1 open`) in orange.
- **A cut that dropped something the next step needed.** The connector keeps `cut 122` in plain sight; the
  handoff view opens on the headings with cuts; if a check fails (`open questions kept, 0 of 1`) the Checks
  fold opens.
- **A model over its pace.** With the list breakdown closed, the strip adds `N models over pace` only when
  true. On the Usage page over-pace rows sort first and keep the orange figure on their one bar.
- **A harness that is on but not found.** The closed Harnesses row shows `cmd not found` in red with `△` and
  opens by itself; Prep keeps the refusal line on the step row.
- **A run with no cap.** Prep keeps the one-line `△ no turn cap: stops at 1800 s`.
- **Context in the red zone.** The 15-cell mini gauge on a done block keeps the tone (orange past 150K, red past
  300K); a step past 150K keeps its full block; the Task page keeps its gauge line.
- **The live step.** The chain and the Task page open scrolled to the current step; Stop sits on the inspector's
  head line, never inside a fold.
- **Remembered folds.** A fold Fred opened stays open (window.json), but a fold that opened by itself on a
  FAIL closes again only when Fred closes it, so a red state is never re-hidden by navigation.
