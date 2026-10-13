# Interface design: harnesses, fills, handoff, replan and the Cells Board (2026-10-13)

- Asked by Fred, thread "Interface design for plan 5" ("exhaustive design").
- Covers the window side of plan 5 (harness adapters, `plans/05-harnesses/`) and of the brainstorm
  `2026-10-13-orchestration.md` sections 3.1, 4, 5, 7 and 8 (plans 18, 23, 24, 25 in its section 9).
- Mockup: `design/rework/locked/cells-board.html` (thirteen views, sample data, dark and light), locked by
  Fred on 2026-10-13 (D-6): plan 25 and the window tasks of plans 5, 18, 23 and 24 take their code from it.
- Read first: `web/app.js` (list, Task page, Prep page, session page, Usage page, picker popover),
  `web/style.css` (tokens, cells, sprites), `design/rework/locked/cells-drawer.html`, `usage.html`,
  `status-sprites.html`, plan 5 README (3.6, 3.7, decisions 10 to 13), plan 17 README (task.json, states).
- State: design only, no code changed. Decisions D-1 to D-8 stand; ID-1 to ID-9 (section 12) are taken by
  Fred, all as proposed except ID-5 (no cells for a handoff's words).

## 0. Short answer

The compact window (340 to 400 px) keeps everything Cells Drawer locked and takes every new fact in place:
a rung is words (`codex · gpt-5.6-codex · medium`) wherever a model showed, the settings popover gets a
Harnesses group with a switch per CLI, every model select lists tiers (think / write / read) holding rungs on
any CLI that is on, the Task page's step rows gain a context gauge (no word cells for the
handoffs, ID-5), the today breakdown and the Usage page show the fills per model, and a replan waits as any other wait.

The Board is the one new page: the window widened to 900 px from a button, the chain of a task on the left
as connected cells (steps as blocks, briefs as the connectors, a fix insert as a bracket), and one picked
thing on the right (a step, a brief, the task head, or the measure table). Same tokens, same cells, no new
colour: orange stays "needs you", unknown stays unknown.

Two zones (Opus 5.5 review, 2026-10-13, `2026-10-13-interface-review.md`): what Fred acts on stays in
sight; how, why, history and exact counts sit behind one closed line each (a fold), and done things shrink
to two lines. The review's P1 and P2 lists are applied in the mock and in this doc.

## 1. Rules this design keeps (BRAINSTORM 7.5, CLAUDE.md)

- Tokens, type and the cell motif of Console Cells; all styling in `web/style.css`; no build step.
- Orange only for "needs you" (a question, a replan to confirm, a handed-off note to start, a model over its
  pace that the router leaves); red and green only for state; blue for a note being written. State is never
  colour alone: glyph or sprite plus word. Two tokens exist for the chat alone (ID-8): `--me` (violet,
  Fred's turns) and `--ai` (the writing blue, the agent's turns); they colour nothing else.
- One Doto figure per screen. Every quantity in cells, but a handoff's words: those are a figure in the
  inspector only, never cells (ID-5, Fred: a visual for the word count was confusing and cluttered the UI).
  An unknown is a word, never a zero (D-3).
- Words: a step **receives** a handoff and **writes** one. Received is what it got from the step before, after
  the brief pass; Handoff is what it wrote for the step after. "Note" and "brief" stay names in the code
  (ID-9: Fred, 2026-10-13, Note / Brief took minutes to read at first sight).
- Two zones (Fred, 2026-10-13: "keep what matters in sight, second-zone information behind a tab or a
  collapsable drawer"). Zone 1: state (word and sprite), what needs Fred, the one figure that matters on the
  screen, the next action, the current step; a number only if it changes what he does now. Zone 2, behind a
  fold: how and why, route notes, exact counts of finished things, provenance (thread ids, paths, diff
  stats), the checks, logs, scales, config names; every sentence that explained the design becomes a title.
  A fold is never silent: its closed line is `Label · the one fact worth seeing ▾` in `--mut` mono; a FAIL,
  an open question, a not-found or an over-pace keeps its tone in that line, and a FAIL or a failing check
  opens its fold by itself. Folds remember their state per window (window.json), as the session page's brief
  fold does. One place per number: a figure shown one line away is not repeated.
- Motion: the running puzzle and the waiting `?` (plan 21), the one blinking cell on the live step; nothing
  else moves by itself. All off under reduced motion.
- The window is a CSS container; nothing scrolls sideways at 340, 400 or 900 px.
- No emojis, no em-dashes, no worktrees, no DAG canvas, no terminals on the Board, no drag to reorder.

## 2. Forms and widths

| Width | What shows | How you get there |
|---|---|---|
| pill 380 x 48 | Unchanged. | Fold. |
| 340 to 400 | Cells Drawer as locked (list, session, Prep, Task, Usage) with the additions of sections 3 to 8. | Default; the grip. |
| 400 to 700 | The same one column, stretched. No second column. | The grip, as today. |
| 700 to 900 | The Board page (section 8). The other pages stay one column at that width. | **Board** on the Task page head, or **⇔ Board** in the list header: the window widens to the saved Board size (900 x 680 the first time, kept in `window.json` as `board: [w, h]`) and opens the Board. **Back** or **Esc** returns to the page it came from at the compact size. Dragging the grip past 700 px lights the ⇔ button; it never switches pages by itself (ID-4). |

`console/window.py` already allows 900 px (`OPEN_MAX_W`). The Board needs one new `WindowApi` call: resize
to a given size and back, which `resize(w, h, keep)` already does for the grip.

## 3. The list (compact)

- **Header**: the ⇔ Board button after the "N need you" chip, hidden in the pill and under 372 px, where the
  Task page's Board button remains the way in. It opens the Board on the scope (All projects: every task,
  newest first).
- **Today strip breakdown** (`todaymore`): closed by default, as locked ("one click away"). Under the strip
  one line shows only while a model is over its pace: `3 models over pace · fills ▾` (the figure in orange),
  and opens the breakdown: the spend legend, the model mix as one line (`opus 48 · sonnet 27 · codex 14 ·
  haiku 9 %`), a second muted line for `opencode · deepseek-v4-flash: cost unknown, 2 runs` and `window
  runs 9`, then one fills line, `fills · opus 84 · sonnet 84 · gpt-5.6-codex 91 % of pace today` with the
  over-pace figures in orange and the Usage button. No cells in the breakdown: the Usage page carries the
  fills. Needs you then starts on the first screen.
- **Task card**: line 2 reads `step 5c of 8` (the fix steps counted, as the Task page does); the current
  step's rung is on the doing line (`5c verify · opus · medium · reads the fix diff`). A task waiting on a
  replan shows `replanned after 01: 2 steps added` in orange (one line, no "confirm on" clause: the buttons
  are under it) and Confirm plan / Keep old plan in place; the replan pass's rung is not shown; Stop stays on
  the Task page. Project names are hidden while the scope is one project; done rows carry no step tag.
- **Session card, auto hand off** (D-5): a window run that ended its turn in the red zone and was handed off
  by the service shows as HANDED OFF under Needs you: the why `↻ handed off by itself at 312K`, then one row
  with the green `✓ handoff ready` chip, Start next chat (its title: seeds the task box, one task = one chat)
  and the `handoff` link. The same card for a VS Code chat says `forked, then handed off` since a VS Code
  chat is never resumed in place.
- **Composer hint**: when `claude.exe` is missing but another harness is on and found: `claude.exe not
  found: Prep needs it; set "exe" under harnesses.claude`.

## 4. Settings: the picker popover

Under Runs allowed / Runs off, two folded rows, in the popover's own row grammar (14 px glyph column, name,
state, action) once open:

- **Harnesses**: closed line `Harnesses · claude, codex on · △ cmd not found ▾`, the not-found part red; it
  opens by itself while a harness is on but not found. Open: one row per name in `cfg.harnesses` order.
  Glyph and state word: `● on` (green glyph), `○ off`, `△ not found` (red glyph, red word). The probed
  version in `.m` after the name (`codex-cli 0.162.1`; blank when not found). The button Turn on / Turn off,
  pending (`...`, disabled) until `POST /api/harness` answers; on error the row's note line carries the
  message in red. `claude` reads `always on`, its title `Prep and the brief pass run on it; it cannot be
  turned off` (the service answers 400). A row that is on but not found carries one note line, `no cmdc.exe
  on PATH · set "exe" in config.json`, the full path and `under harnesses.cmd (not the .cmd shim)` in its
  title. The group's title holds `opencode and cmd rungs run read steps only (cheap tier); rungs of a
  harness that is off never route; a step picked on one falls back to Claude's rung of its tier`.
- **Window runs**: closed line `Window runs · auto hand off off ▾`. Open: `auto hand off · at 300K`, off /
  on, Turn on / Turn off, and one line `hands off a window run that ends its turn in the red zone (300K) and
  seeds the next chat; a VS Code chat is forked first`. Writes `handoff_auto` through a
  `POST /api/setting`-style route as Allow runs does (ID-2). The threshold is `gauge_red_tokens`, shown, not
  editable here.

Keyboard and sorting of the project rows are unchanged; the new groups are not in the Up / Down ring (they
are buttons, Tab reaches them).

## 5. Prep page and the Run route

- **Model selects** (`modelOptions`): tier groups `think`, `write`, `read` (and `fable` on the Run route),
  each holding rungs on any harness that is on and found, Claude's ladder first as `opus 4.8`, then
  `codex · gpt-5.6`, then the older Claude rungs. `opencode` and `cmd` rungs appear under `read` only, and
  only on the Run route and on step rows whose kind's rule tier is read (`cfg.kinds_tier`). Plan 5 alone
  (before plan 18) draws the same select with the Claude ladder groups followed by one group per harness;
  the tier names arrive with plan 18.
- **A refused pick** (decision 11): the row shows `opencode: read steps only (cheap tier) · back to auto` in
  the row's say line and the select returns to auto. Changing a kind redraws its select; a pick the new kind
  cannot hold falls back to auto the same way.
- **Route reason**: folded under the selects, closed line `why codex · balance ▾`; open: the rule, what
  balancing did (`balance: sonnet 84 % of pace -> codex · gpt-5.6-codex 31 %`), the effort source. A rung
  with no cap keeps one muted line in sight, `△ no turn cap: stops at 1800 s`, the full sentence (`codex has
  no turn or spend cap: this run ends at step_timeout_s (1800 s) if it is still going`) in its title.
- **Scouted**: folded, closed line `Scouted · context pack 1.9 KB · 3 files ▾`; open: the `path:lines`
  citations (brainstorm 5.1 item 3, the small plan of its own) in `.m`.
- **Verify row**: `6 verify · added after the last edit`; the tier rule (`one tier above the step it checks,
  on any harness that is on`) in its title. The paragraph that explained Run as task is the button's title;
  the duplicate `effort: auto` line is gone (the composer says it). `Prep $0.031 · 4 turns · haiku` stays
  the last muted line.

## 6. Session page of a non-Claude step (plan 5 decision 10)

- **Head**: the model chip reads `codex · gpt-5.6-codex · medium` (`modelText` on a `harness:model` rung,
  no version lookup); on a task step the project name leaves the where row (the `task · step 3 of 8` link
  carries it) so the chip has the room. No note line: the brief already says `context unknown`; the thread
  id and the resume mode sit in the chat's source line and in the Continue button's title (`resumes the
  Codex thread 019a3f… with codex exec resume`).
- **Brief**: spent exact when the adapter reports usage, `~` when estimated, `–` when unknown; `$ / min`
  from the same; the context column reads `unknown` in words with no cells (ID-3), its title saying why;
  `session` time; no events column (the Steps tab counts them).
- **Process tabs**: Chat and Steps only (Agents and Timeline come from Claude's hooks). Chat: the folded
  Prompt row, the turns and the tool events the adapter's `chat()` names (command_execution lines as
  notes), the source line at the end (`ended 14:19:48 · codex exec --json · thread 019a3f… · 31 events`).
  Steps: the stream events with their time, kind and text.
- **Levers**: Continue when the adapter resumes and the run is not live; Stop while live (a kill of the
  tree for Codex, OpenCode and Command Code, decision 8, said in the Stop title); Mark done, Brief a new
  task. Verify, Hand off, Escalate and Terminal off; the say line is one line, `claude only: Verify, Hand
  off, Escalate`, the rest in the disabled buttons' titles.

### 6.1 Chat turns (Fred, 2026-10-13: less clutter, the two sides obvious, an accent each)

Everywhere a chat shows (the session page's Chat tab, the Board's Chat tab, the peek card's reply):

- **Two sides**: the agent's turns are bubbles on the left (`.turn.claude`, at most 82 % wide, a 2 px
  `--ai` edge on the left, a 9 % `--ai` tint over the raised surface, the label `Claude` or the harness's
  name in `--ai`); Fred's turns are bubbles on the right (`.turn.you`, a 2 px `--me` edge on the right, an
  11 % `--me` tint, the label `You` in `--me`, right-aligned). Text stays left-aligned inside both.
- **The prompt folds**: the first turn is the prompt the service built (the goal and the handoff received),
  not something Fred typed, so it is one right-side row with the violet edge, labelled `Prompt`, `goal and
  the handoff of 02 · 53 w ▾`; click opens the text. `You` is kept for what Fred typed (a follow-up, an
  answer).
- **Tool events fold**: a run of consecutive tool events (file_change, command_execution, Read, Bash, Grep)
  becomes one centred quiet row with a failed exit first, `3 tool events · exit 1 · file_change,
  command_execution`, the exit in red, so an ellipsis at 340 px never hides it; click or Space opens the
  list in place, muted mono, and the choice holds for that chat.
- **The HANDOFF block folds**: the last turn shows a chip `HANDOFF block · 412 w · six headings` and the
  Next line; the six headings live in the Handoff tab (Board) or the Task page's handoff block.
- **Writing**: a live turn carries `· writing` and the one blinking cell in its label; no extra line.
- **Source line** on top, unchanged: harness, thread or session id, events, ended or running.
- Nothing else in the window uses `--me` or `--ai`.

## 7. Task page (compact)

- **Head**: `Board` button in the `where` row (native only; hidden when the window cannot resize). No path
  line: the title's tooltip holds it. The Steps header reads `Steps · 8` and `step 5c of 8`; the page opens
  with the current step scrolled into view.
- **Step rows**: a finished step is two lines, `NN kind rung · cost · Open` and its goal (muted, one line).
  The gauge line, `ctx` (15 cells of the 30, past 150K in orange, the figure in the tone of the gauge;
  `unknown` in words for a harness with no context; no `in` / `out` word gauges, ID-5), stays open only on
  the current step, a failed step and a step past 150K; a click on the row opens it on the others. The cell
  scale is the gauge's title. A failed row gives its sub line to
  the verdict whole, `FAIL test_resume_command: options after resume`. Attempt squares show on a row only
  when a try failed; the reason (`try 1 no HANDOFF block`) is in the opened row. The hint `· △ scout first`
  is muted, not orange (it is tuning, not a wait), its figures in its title (`230 w in, 118K reached`; the
  `delegate_after_reads` logic per step).
- **Replan wait** (plan 24): the askbox of the Task page carries `Replanned · after step 01`, the question,
  the plan before and after as two lists with the added steps marked, Confirm plan (orange), Keep old plan,
  Stop, and the line `replan_auto is off: a changed plan waits for you`.
- **Handoff block**: folded, closed line `Handoff for 5c · 230 w · Next: check the fix against the FAIL
  detail ▾`. Open: `compacted from 260 w` and the `as 5b wrote it` link, then the six headings as the
  Board's Received tab renders them (Goal, Findings, Open questions and Next open, Files touched and
  Troubleshooting folded), then the facts the service appended folded to `Facts · 1 file +4 · 23 tests OK ▾`
  (`git diff --stat` from the start to the end commit, the failing lines of the last test command, never
  compacted; a failing test line puts FAIL in red in the closed line and opens it).
- **Auto hand off**: a handed-off task reads as today (plan 13); a window run handed off by the service
  shows the handed box with `by itself at 312K`.

## 8. The Board (plan 25)

### 8.1 Layout

900 x 680 by default. Header: Back, crumb `Board / <scope> · N tasks`, window buttons. Body: two columns,
the chain (300 px, scrolls) and the inspector (the rest, scrolls), a 1 px line between. Footer: the keys
(`↑ ↓ step · ← → task · Enter chat · Esc back`, hidden on the empty Board) and a `?` at the right whose
title is the legend (`a step's context in cells of 10K; the chip between two steps is the handoff the next
one received, its words in the inspector`).

### 8.2 The chain

- **Tasks** of the scope, newest first; every task folded to one quiet row (sprite, state word, title,
  age; line 2 the orange `why` of a waiting task, else `N steps`; cost) except the picked one. Project and
  effort are the row's title. Left / Right moves the pick between tasks.
- **Task head** (the unfolded one): the same row raised, the title on two lines, line 2 `step 5c of 8` (the
  fix steps counted) and the cost.
- **Step block, finished**: two lines. Line 1 sprite + state word (DONE), `NN kind`, cost (`0.84`, `~0.84`,
  `? cost`); line 2 the rung `harness · model · effort` and the time in `--mut` (`NN kind` is the one
  semibold per block), and at the right a 15-cell context mini gauge with its figure (the list card's `.ctx`
  grammar; yellow from 150K, red from 300K) or `ctx unknown`, the reason (`codex reports a turn's spend, not
  a context size`) in its title. About 46 px: the running task with its eight steps fits the first screen,
  the FAIL and the live step on it.
- **Step block, current, failed, waiting or picked**: the full block. Lines 1 and 2 as above (the attempt
  squares on line 2 only when a try failed: red failed, green passed, ink live); line 3 `ctx` with 30 cells
  of 10K and the figure (the live cell blinks on a running step), or `unknown` with the reason in its
  title; line 4 the verdict with its detail (whole, the title repeating it), or the muted hint `△ scout
  first` (figures in its title), or the task's wait in orange. No in / out line: the connectors carry the
  words. The current step has an ink edge on the left; the picked block an ink outline.
- **Step block, planned**: one line, `PLANNED NN kind`; `rung at start (rule kind)` in its title.
- **Connector**: the handoff between two steps as the next one received it, a 2 px line and a chip that
  names it: `handoff`, the word count in its title. Variants: after a cut, `handoff · cut 122 w` with the
  cut in ink (ID-1, no orange; ID-5, no cells: the counts are in the inspector); dashed border for a code
  fallback (`as written · not compacted`, the reason in the title); blue dashed `writing`; before a planned
  step a dotted line with no chip. The footer's `?` says what a connector is.
- **Fix insert**: a bracket (a 2 px line with two ticks) under the failed verify holding the fix and the
  second verify, rejoining the chain after them; the fix block shows its escalated rung.
- **Replan**: a step block of kind `replan` (Haiku, no tools, 1 turn), orange while the task waits on it.
- **Empty**: 30 off cells and `No task in <scope>. Type a task in the list; its steps show here as they
  run.`; the inspector and the key hints stay blank.

### 8.3 The inspector (one picked thing)

- **A step**: head on one line (sprite, state word, `NN kind`; Open chat, Stop while live and Open try 1
  after a failed attempt at the right) and one meta line, `rung · cost · time` (context and the words are
  on the picked block, 300 px to the left, and in the tabs), then four tabs, **Chat first** (Fred,
  2026-10-13: the chat has priority over what it read and what it wrote). The tabs read `Chat · Received
  310 w · Handoff 412 → 290 w · Route`: the word counts help choose, the arrow says a cut happened.
  - **Chat**: the step session's chat as the session page's Chat tab shows it (`runs.chat`), in the
    chat grammar of section 6.1: the Prompt row folded, the agent's turns as bubbles on the left, Fred's on
    the right, the tool events folded into one row per run of them with a failed exit first, the HANDOFF
    block as a chip with its Next line, the source line at the end; a running step streams, newest at the
    end, with the writing mark in the agent's label, and the pane follows the end until Fred scrolls up.
  - **Received**: the handoff it got from the step before (`From 02 · 310 w · compacted`), six blocks with
    Goal, Findings, Open questions (when any, the count in orange) and Next open, Files touched (`4 ·
    codex.py, fake_codex.py +2`) and Troubleshooting (`3 lines`) folded; step 1 says it received no handoff,
    only the task goal and the context pack. No green edges and no `never cut` labels: that is a rule, not
    a state, and the handoff view's Checks say it.
  - **Handoff**: the one it wrote for the step after (`For 04 · wrote 412 w · 04 received 290 w`), the
    HANDOFF block as the same six blocks, the lines the brief pass cut left in place, struck and tagged
    `cut`, then the facts the service added folded to `Facts · 4 files +325 · 23 tests OK ▾` (dashed box:
    `git diff --stat <start>..<end>`, the test command's result lines; a failing line puts FAIL in red in
    the closed line and opens it). A running step says `Writing. Shows here when the run ends`; a planned
    one `Not started`.
  - **Route**: Goal; **Route · in the order the rules applied**, one chip per note (rule, pick, demand,
    floor, hint, cap, budget, balance, harness fallback, tools / MCP, sandbox); `every <tier> rung over
    pace` in orange (nothing was left to leave), the `balance:` note muted (the router already acted);
    **Attempts** with each try's reason.
  The picked tab holds while Up / Down move along the chain, and for the window (window.json), as the
  session page's brief fold does. Open chat still goes to the session page for the levers.
- **A handoff** (a connector picked): head (`Handoff from NN kind to NN+1 kind`; `NN wrote 412 w · NN+1
  received 290 w · cut 122 w, 2 Findings lines`); **one column**, what NN+1 received as six blocks, the
  headings that hold a cut, Open questions and Next open, the lines the brief pass cut left in place under
  their heading, struck and tagged `cut`, the heading's label counting `2 kept · 2 cut` (Fred, 2026-10-13:
  two columns of the same text were unreadable); Goal, Files touched and Troubleshooting folded with
  `whole` in their closed line (the reader came for what was cut); **Checks** folded under the column,
  closed line `Checks · 5 of 5 pass · compacted by haiku · $0.004 · 2 turns ▾`; open: shorter than what it
  compacts, Goal and Troubleshooting whole, open questions kept (n of n), continuity (names a file from the
  previous Files touched), no invented path. A failing check shows `1 FAIL: <name>` in red in the closed
  line and opens the fold by itself.
- **The task head**: head line (state, title; Stop and Pause while running, Clear when done) and the meta
  `step 5c of 8 · cost 4.62 · effort auto`, the task folder in the title's tooltip; a **Now** line in sight:
  the live cell, `Now 5c verify · opus · medium · 2m 40s`, `next 06 document`; **Open questions · n open**
  from the handoffs, the open ones in sight with the step that opened each (orange `?`), the closed ones
  folded (`2 closed ▾`, green `✓` with the step that closed each); **prompt.md** folded, its closed line the
  Done when line; **Chain log** folded, closed line `Chain log · 23 moves · last 14:38 5c planned ->
  running ▾`, open: one line per move with the route notes.
- **Nothing picked** (Esc inside the Board, or a folded task picked): **Measure · <project> · last N
  tasks · median per kind**: columns `received · context · handoff`; per kind the received and written
  handoffs as figures only (`240 w`, `pack` for the scout; ID-5) and the context as a 20-cell bar with its
  figure (`112K`; past 150K in orange, and the legend shows that item only when a bar is orange), the row
  the reading names in ink and the others muted, the cell scale in the legend (`cell 10K`), and the one-line
  reading (brainstorm 5.1 item 6) without its provenance sentence.

### 8.4 Keyboard

Up / Down walk the chain (steps and handoffs, into and out of a fix bracket in order); Left / Right the
tasks; Enter opens the picked step's session page (Back returns to the Board); Esc clears the pick, then
leaves the Board to the page it came from. The pick is an ink outline, like a focused control.

## 9. Usage page (plan 18)

- **Models · share of pace** after the four figures, sorted over pace first: one row per model (the model,
  not the harness; the second line says `claude`, `via codex`, `via opencode, cmd`), one bar of 20 cells for
  the window that binds (the highest share of pace: `day`, `week` or `month` as the bar's label), the pace
  as the orange outline cell, the figure as the share of pace (orange over pace), then the other two windows
  as text (`w 71 · m 52`); a click on the row opens the three bars. A model with no allowance: a dotted bar,
  `–`, `no allowance`. Legend: `used`, `pace`, `20 cells = allowance`, `orange over pace`. The config names
  fold: `config · balance_margin 0.2 · warn_at 0.8 ▾`, open: the router sentence, the Opus fill counting
  both CLIs, `allowance` in config.json. (ID-6 unchanged: the cells stay 20 per window.)
- **Days**: the calendar, the picked day and the Days / Weeks / Months columns stay as locked, above the
  heatmap (the calendar is what the page was for); the picked day's model line lists harness rungs and
  `cost unknown · n runs`.
- **Verify FAIL by hour**: folded, closed line `Verify FAIL by hour · opus peaks 14:00 to 17:00 · last 30
  days ▾`. Open: rows per model that wrote the checked step (the harness in the row's title, so nothing
  truncates), 24 columns, four red tones (`l1` to `l4` over `--bad`), hover `14:00 opus: 3 of 7 FAIL`, a
  dotted row for a rung with no verify yet; under it the one-line reading and that it feeds `peak_hours`
  (off).
- Footer: `Codex usage x its price row; OpenCode and Command Code runs without usage count as unknown,
  never as zero`.

## 10. States and words

| Thing | States shown | Word and mark |
|---|---|---|
| Harness row | on, off, not found, pending | `● on` / `○ off` / `△ not found` / `...` |
| Rung | Claude, other harness | `sonnet · medium` / `codex · gpt-5.6-codex · medium` |
| Step cost | exact, estimated, unknown | `0.84` / `~0.84` / `? cost` |
| Step context | known, hand-off zone, unknown | cells and `92K` / `164K` in orange / `unknown: codex reports spend` |
| Handoff connector | ok, cut, fallback, writing, pending | `handoff` / `handoff · cut 122 w` (the cut in ink) / dashed / blue dashed / dotted line; the words in the chip's title |
| Handoff line | kept, cut | plain / struck, muted, tagged `cut`, in place under its heading |
| Fold | closed, open, opened by itself | `Label · the one fact ▾` muted mono / the body in place / the red or orange word in the closed line and the body open (FAIL, failing check, not found) |
| Finished step | done, done and picked | two lines (state, kind, cost; rung, time, ctx mini) / the full block |
| Task | planned, running, waiting (replan, question, Fable), stuck, done, stopped, handed | plan 17 words and plan 21 sprites; a replan wait says `replanned: n steps added` |
| Fill | under pace, over pace, no allowance | `31 %` / `84 %` orange / `no allowance` dotted |
| FAIL heat | none, 1 to 4 tones, no data | off cell / red tones / dotted outline |

## 11. What each screen needs from the service

| Screen | Data | Plan |
|---|---|---|
| Settings | `/api/config harnesses {name: {on, found, version, models, tiers}}`, `POST /api/harness`, `handoff_auto` and a route to set it | 5 Task 5; 23 |
| Selects | `cfg.kinds_tier`, the tier groups and rungs | 5 Task 6; 18 |
| Cards, heads, rows | `harness` on session rows and task steps; `cost` left out when unknown; `ctx_tokens` None | 5 Tasks 4 and 5 |
| Task page, Board | per step: brief words in, note words out, `start_commit`, `end_commit`, the facts block, attempts with reasons; the brief pass result (words raw / brief / cut, checks); the chain log; open questions with opened / closed step (parsed from the briefs); the replan's before / after | 23, 24, 25 |
| Board measure | medians per kind over the project's tasks (from task.json and the notes) | 25 |
| Usage, list | fills per model (day / week / month: used, allowance, pace), FAIL counts per rung per hour | 18 |
| Window | `window.json board: [w, h]`; `WindowApi.resize` to open and close the Board | 25 |

## 12. Decisions (taken by Fred, 2026-10-13: all as proposed except ID-5)

| # | Question | Decision |
|---|---|---|
| ID-1 | Brainstorm 7 said a connector turns orange when the brief cut findings | No: orange stays "needs you". A cut is the words `cut 122 w` in ink on the chip; a code fallback is dashed |
| ID-2 | Where the auto hand off (D-5, off by default) is switched | A Window runs group in the settings popover, next to Harnesses, Turn on / Turn off; config.json stays the source of truth |
| ID-3 | Context of a non-Claude step: an estimate (characters / 4, hatched) or unknown | Unknown, as plan 5 3.6 decided; the hatched estimate is a plan 25 option if the live runs show usable token counts |
| ID-4 | How the Board opens | A button that widens the window and opens the page, size kept in window.json; never by dragging alone |
| ID-5 | Cells of a handoff | **No** (Fred): a handoff has no cells, a visual for its word count was confusing and cluttered the UI. The count stays a figure in the inspector (the Received and Handoff tabs, the handoff head, the Task page's handoff fold, the measure table) and in the connector chip's title. `brief_max_words` stays 500 in config.json; the measure table and the `cut` word on the chips show after ten tasks whether it bites |
| ID-6 | Cells of a fill | 20 cells = the window's allowance (day, week or month), 1 cell = 5 %; the orange outline cell marks the pace. Usage shows one bar per model, the window that binds, and opens the three on a click (review, P2) |
| ID-7 | The replan wait | A task `waiting` (orange) on the Task page, the Board and the list card, with the new plan as one list, added steps tagged and dropped ones struck in place (the handoff rule applied here, review 3.11); Confirm plan (its title says `replan_auto` is off), Keep old plan (runs Prep's steps), Stop; why it ran and the route fold |
| ID-8 | Chat roles: Fred asked for an accent per side | Two tokens for the chat only, `--me` violet (Fred, right) and `--ai` the writing blue (the agent, left), tinted bubbles with a 2 px edge; tool events and the HANDOFF block folded (6.1) |
| ID-9 | Words for what passes between steps (Fred: Note / Brief took minutes to read) | "Handoff" everywhere the window shows it: a step receives one and writes one; the tabs are Received and Handoff; "sent" or "after the brief pass" for the compacted version; "note" and "brief" stay code names; the Task page's "note ready" chip becomes "handoff ready" |

## 13. History

- 2026-10-13 - Written from `web/app.js`, plan 5 (reviewed), plan 17 and the brainstorm; mockup rendered at
  400 and 900 px in headless Chromium, dark and light, no horizontal overflow, no script error.
- 2026-10-13 - Fred: less clutter in the chat, the two sides obvious, an accent each: section 6.1 (bubbles left and
  right, `--me` and `--ai`, folded tool rows, the HANDOFF chip), ID-8.
- 2026-10-13 - Fred: the chat has priority over what it read and what it wrote. The step inspector now opens
  on a Chat tab; Note, Brief and Route are the tabs behind it (8.3); a "Step running" view added to the mock.
- 2026-10-13 - Fred: Note and Brief were hard to read at first sight. Renamed everywhere the window shows them:
  Received (what the step got) and Handoff (what it wrote for the next step); tabs, chips, the Task page's
  block and the measure headers; ID-9.
- 2026-10-13 - Fred: the handoff picked view was two clashing blocks of text. Now one column, what the next
  step received, with the cut lines struck in place under their heading and the checks under it (8.3); the
  step's Handoff tab marks the same cut lines.
- 2026-10-13 - Fred: the details are data for nerds; keep what matters in sight, second-zone information
  behind a tab or a drawer. Opus 5.5 (high) reviewed every view (`2026-10-13-interface-review.md`: verdict,
  zoning rule, per-screen tables, P1 to P3, risks). Applied in the mock and here: folds with a closed line
  everywhere (1, 4, 5, 7, 8.3, 9), two-line finished steps and one-line planned ones (7, 8.2), one place
  per number (8.2 connectors, 8.3 head), the today breakdown closed with the over-pace line (3), the Prompt
  row and the exit-first tool rows (6.1), orange back to "needs you" only, the duplicate connector before 06
  fixed, one bar per model on Usage (9, ID-6), the replan as one list (ID-7), the balance note muted (8.3).
  Not applied: nothing of P1 and P2; of P3, the counts and words are aligned and the light theme re-shot.
- 2026-10-13 - Fred locked the design: every decision as proposed except ID-5 (no cells for a handoff's
  words: the connector chip says `handoff` or `handoff · cut 122 w`, the Task page keeps the context gauge
  only, the measure table shows words as figures). `brief_max_words` stays 500. Mockup moved to
  `design/rework/locked/cells-board.html`; BRAINSTORM 7.5 and the README name it. Next: plan 25 from
  sections 8 and 11.
