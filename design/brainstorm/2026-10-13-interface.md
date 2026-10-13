# Interface design: harnesses, fills, handoff, replan and the Cells Board (2026-10-13)

- Asked by Fred, thread "Interface design for plan 5" ("exhaustive design").
- Covers the window side of plan 5 (harness adapters, `plans/05-harnesses/`) and of the brainstorm
  `2026-10-13-orchestration.md` sections 3.1, 4, 5, 7 and 8 (plans 18, 23, 24, 25 in its section 9).
- Mockup: `design/rework/proposed/cells-board.html` (twelve views, sample data, dark and light). Fred locks it
  (D-6), then plan 25 and the window tasks of plans 5, 18, 23 and 24 take their code from it.
- Read first: `web/app.js` (list, Task page, Prep page, session page, Usage page, picker popover),
  `web/style.css` (tokens, cells, sprites), `design/rework/locked/cells-drawer.html`, `usage.html`,
  `status-sprites.html`, plan 5 README (3.6, 3.7, decisions 10 to 13), plan 17 README (task.json, states).
- State: design only, no code changed. Decisions D-1 to D-8 stand; this doc adds ID-1 to ID-7 (section 9).

## 0. Short answer

The compact window (340 to 400 px) keeps everything Cells Drawer locked and takes every new fact in place:
a rung is words (`codex · gpt-5.6-codex · medium`) wherever a model showed, the settings popover gets a
Harnesses group with a switch per CLI, every model select lists tiers (think / write / read) holding rungs on
any CLI that is on, the Task page's step rows gain one line of three gauges (brief in, context reached, note
out), the today breakdown and the Usage page show the fills per model, and a replan waits as any other wait.

The Board is the one new page: the window widened to 900 px from a button, the chain of a task on the left
as connected cells (steps as blocks, briefs as the connectors, a fix insert as a bracket), and one picked
thing on the right (a step, a brief, the task head, or the measure table). Same tokens, same cells, no new
colour: orange stays "needs you", unknown stays unknown.

## 1. Rules this design keeps (BRAINSTORM 7.5, CLAUDE.md)

- Tokens, type and the cell motif of Console Cells; all styling in `web/style.css`; no build step.
- Orange only for "needs you" (a question, a replan to confirm, a handed-off note to start, a model over its
  pace that the router leaves); red and green only for state; blue for a note being written. State is never
  colour alone: glyph or sprite plus word. Two tokens exist for the chat alone (ID-8): `--me` (violet,
  Fred's turns) and `--ai` (the writing blue, the agent's turns); they colour nothing else.
- One Doto figure per screen. Every quantity in cells. An unknown is a word, never a zero (D-3).
- Words: a step **receives** a handoff and **writes** one. Received is what it got from the step before, after
  the brief pass; Handoff is what it wrote for the step after. "Note" and "brief" stay names in the code
  (ID-9: Fred, 2026-10-13, Note / Brief took minutes to read at first sight).
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
- **Today strip breakdown** (`todaymore`): after the model mix legend, a **Fills** row: one small column per
  model that has an allowance, three bars (d / w / m) of 10 cells each, the pace as an orange outline cell,
  the figure as the share of pace, orange when over. Models through two CLIs are one column (Opus through
  Claude Code and Codex). The legend gains `codex · gpt-5.6-codex 14 %` entries and `opencode ·
  deepseek-v4-flash cost unknown · 2 runs` for runs with no usage (never a 0 %).
- **Task card**: the current step's rung reads `codex · gpt-5.6-codex · medium` in the route slot (hidden
  under 372 px as today). A task waiting on a replan shows `replanned: 2 steps added, confirm on the Task
  page or the Board` in orange and the two buttons Confirm plan / Keep old plan in place; Stop stays on the
  Task page.
- **Session card, auto hand off** (D-5): a window run that ended its turn in the red zone and was handed off
  by the service shows as HANDED OFF under Needs you: `↻ handed off by itself at 312K (auto hand off): the
  note is ready, one task = one chat`, the green `note ready` chip, Start next chat and the note link. The
  same card for a VS Code chat says `forked, then handed off` since a VS Code chat is never resumed in place.
- **Composer hint**: when `claude.exe` is missing but another harness is on and found: `claude.exe not
  found: Prep needs it; set "exe" under harnesses.claude`.

## 4. Settings: the picker popover

Under Runs allowed / Runs off, two groups, in the popover's own row grammar (14 px glyph column, name,
state, action):

- **Harnesses · which CLIs may run a step**: one row per name in `cfg.harnesses` order. Glyph and state
  word: `● on` (green glyph), `○ off`, `△ not found` (red glyph, red word). The probed version in `.m` after
  the name (`codex-cli 0.162.1`; blank when not found). The button Turn on / Turn off, pending (`...`,
  disabled) until `POST /api/harness` answers; on error the row's note line carries the message in red.
  `claude` reads `always on` with the note `Prep and the brief pass run on it; it cannot be turned off`
  (the service answers 400). A row that is on but not found carries the note `on, but no cmdc.exe on PATH:
  set "exe" under harnesses.cmd in <config path> (not the .cmd shim)`. One muted line under the group:
  `opencode and cmd rungs run read steps only (cheap tier). Rungs of a harness that is off never route; a
  step picked on one falls back to Claude's rung of its tier.`
- **Window runs**: `auto hand off · at 300K`, off / on, Turn on / Turn off, with the note `when a window
  run ends its turn in the red zone, the service runs the hand off and seeds the next chat; a VS Code chat
  is forked first, never resumed in place`. Writes `handoff_auto` through a `POST /api/setting`-style route
  as Allow runs does (ID-2). The threshold is `gauge_red_tokens`, shown, not editable here.

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
- **Route line**: the rule, what balancing did (`balance: sonnet 84 % of pace -> codex · gpt-5.6-codex
  31 %`), the effort source; and, for a rung with no cap, `codex has no turn or spend cap: this run ends at
  step_timeout_s (1800 s) if it is still going`.
- **Scouted**: `Scouted · context pack 1.9 KB` with the `path:lines` citations (brainstorm 5.1 item 3, the
  small plan of its own) in `.m`.
- **Verify row**: `added by the Console after the last editing step · one tier above the step it checks, on
  any harness that is on`.

## 6. Session page of a non-Claude step (plan 5 decision 10)

- **Head**: the model chip reads `codex · gpt-5.6-codex · medium` (`modelText` on a `harness:model` rung,
  no version lookup). The note line: `context unknown: codex reports a turn's spend · thread 019a3f…:
  Continue resumes it with codex exec resume · no hooks: Steps come from the stream`.
- **Brief**: spent exact when the adapter reports usage, `~` when estimated, `–` when unknown; `$ / min`
  from the same; the context column reads `unknown` in words with no cells (ID-3); `session` time; the
  steps column becomes `events` (the adapter's stream events) or `–`.
- **Process tabs**: Chat and Steps only (Agents and Timeline come from Claude's hooks). Chat: the final
  message and the tool events the adapter's `chat()` names (command_execution lines as notes). Steps: the
  stream events with their time, kind and text.
- **Levers**: Continue when the adapter resumes and the run is not live; Stop while live (a kill of the
  tree for Codex, OpenCode and Command Code, decision 8, said in the Stop title); Mark done, Brief a new
  task. Verify, Hand off, Escalate and Terminal off with `claude only`. A task step keeps `a task step: use
  the task's levers`.

### 6.1 Chat turns (Fred, 2026-10-13: less clutter, the two sides obvious, an accent each)

Everywhere a chat shows (the session page's Chat tab, the Board's Chat tab, the peek card's reply):

- **Two sides**: the agent's turns are bubbles on the left (`.turn.claude`, at most 82 % wide, a 2 px
  `--ai` edge on the left, a 9 % `--ai` tint over the raised surface, the label `Claude` or the harness's
  name in `--ai`); Fred's turns are bubbles on the right (`.turn.you`, a 2 px `--me` edge on the right, an
  11 % `--me` tint, the label `You` in `--me`, right-aligned). Text stays left-aligned inside both.
- **Tool events fold**: a run of consecutive tool events (file_change, command_execution, Read, Bash, Grep)
  becomes one centred quiet row, `3 tool events · file_change, command_execution · exit 1`, a failed exit in
  red; click or Space opens the list in place, muted mono, and the choice holds for that chat.
- **The HANDOFF block folds**: the last turn shows a chip `HANDOFF block · 412 w · six headings` and the
  Next line; the six headings live in the Handoff tab (Board) or the Task page's handoff block.
- **Writing**: a live turn carries `· writing` and the one blinking cell in its label; no extra line.
- **Source line** on top, unchanged: harness, thread or session id, events, ended or running.
- Nothing else in the window uses `--me` or `--ai`.

## 7. Task page (compact)

- **Head**: `Board` button in the `where` row (native only; hidden when the window cannot resize).
- **Step rows**: the rung in the name (`codex · gpt-5.6-codex · medium`), then one new line under it:
  `in` (the brief it read, cells of 50 words, 10 cells; step 1 shows `pack` for the context pack), `ctx`
  (15 cells of the 30, past 150K in orange, the figure in the tone of the gauge; `unknown` in words for a
  harness with no context), `out` (the note it wrote, cells of 50 words; hidden under 372 px), and the hint
  `· scout first` in orange when a step read under 300 words and reached past `delegate` territory (the
  `delegate_after_reads` logic per step). Attempts and the verdict stay on the sub line as today.
- **Replan wait** (plan 24): the askbox of the Task page carries `Replanned · after step 01`, the question,
  the plan before and after as two lists with the added steps marked, Confirm plan (orange), Keep old plan,
  Stop, and the line `replan_auto is off: a changed plan waits for you`.
- **Handoff block** (`Handoff for step NN · after the brief pass`, a Show it as NN-1 wrote it button): the six
  headings (Goal, Findings, Files touched, Troubleshooting, Open questions, Next)
  and, under `END HANDOFF`, the facts the service appended (`git diff --stat` from the start to the end
  commit, the failing lines of the last test command), never compacted.
- **Auto hand off**: a handed-off task reads as today (plan 13); a window run handed off by the service
  shows the handed box with `by itself at 312K`.

## 8. The Board (plan 25)

### 8.1 Layout

900 x 680 by default. Header: Back, crumb `Board / <scope> · N tasks`, window buttons. Body: two columns,
the chain (300 px, scrolls) and the inspector (the rest, scrolls), a 1 px line between. Footer: the keys
(`↑ ↓ step or brief · ← → task · Enter open the chat · Esc back`) and the scale (`1 ctx cell = 10K · 1
word cell = 50 w`).

### 8.2 The chain

- **Tasks** of the scope, newest first; every task folded to one quiet row (sprite, state word, title,
  age; project, effort, steps, cost) except the picked one. Left / Right moves the pick between tasks.
- **Task head** (the unfolded one): the same row raised, with the task's `why` in orange when waiting.
- **Step block**: line 1 sprite + state word (RUNNING, DONE, FAIL, PLANNED, WAITING), `NN kind`, cost
  (`0.84`, `~0.84`, `? cost`); line 2 the rung `harness · model · effort` and the time; line 3 `ctx` with
  30 cells of 10K and the figure (yellow from 150K, red from 300K; the live cell blinks on a running step),
  or `unknown: codex reports spend`; line 4 `in` and `out` as 10 cells of 50 words with the figure (`pack
  1.9 KB` on step 1, `…` on a running step's out), and the attempts as 7 px squares (red failed, green
  passed, ink live); line 5 the verdict with its detail, or the hint `scout first: 230 w in, 118K reached`,
  or the task's wait. The current step has an ink edge on the left; the picked block an ink outline.
- **Connector**: the handoff between two steps after the brief pass, a 2 px line and a chip: `[cells] handoff
  290 w`. Variants: `· cut 122 w` with the cut part of the cells in the `l2` tone (ID-1, no orange); dashed
  border for a code fallback (`handoff as written, not compacted · verify FAIL`); blue dashed
  `handoff: writing`; `no handoff yet` on a dotted line before a planned step.
- **Fix insert**: a bracket (a 2 px line with two ticks) under the failed verify holding the fix and the
  second verify, rejoining the chain after them; the fix block shows its escalated rung.
- **Replan**: a step block of kind `replan` (Haiku, no tools, 1 turn), orange while the task waits on it.
- **Empty**: 30 off cells and `No task in <scope>. Type a task in the list; its steps show here as they
  run.`

### 8.3 The inspector (one picked thing)

- **A step**: head (sprite, `NN kind`, rung, cost, time, context, in / out; Open chat, Stop while live,
  Open try 1 after a failed attempt), then four tabs, **Chat first** (Fred, 2026-10-13: the chat has
  priority over what it read and what it wrote):
  - **Chat**: the step session's chat as the session page's Chat tab shows it (`runs.chat`), in the
    chat grammar of section 6.1: the source line, the agent's turns as bubbles on the left, Fred's on the
    right, the tool events folded into one row per run of them, the HANDOFF block as a chip with its Next
    line; a running step streams, newest at the end, with the writing mark in the agent's label, and the pane
    follows the end until Fred scrolls up.
  - **Received**: the handoff it got from the step before, after the brief pass (`Handoff it received from
    step NN · 310 w`), six blocks; step 1 says it received no handoff, only the task goal and the context
    pack.
  - **Handoff**: the one it wrote for the step after (`Handoff it wrote for step NN · raw 412 w · sent as
    290 w after the brief pass`), the HANDOFF block as six blocks (Goal and Troubleshooting with a green edge
    and `never cut`; the lines the brief pass cut stay in place, struck and tagged `cut`), then **Facts the
    service added** (dashed box: `git diff --stat <start>..<end>`, the test command's result lines). A
    running step says `Writing. The handoff shows here when the run ends`; a planned one `Not started`.
  - **Route**: Goal; **Route · in the order the rules applied**, one chip per note (rule, pick, demand,
    floor, hint, cap, budget, balance, harness fallback, tools / MCP, sandbox), the balance note and `every
    <tier> rung over pace` in orange; **Attempts** with each try's reason.
  The picked tab holds while Up / Down move along the chain, and for the window (window.json), as the
  session page's brief fold does. Open chat still goes to the session page for the levers.
- **A handoff** (a connector picked): head (`Handoff from NN kind to NN+1 kind`; `NN wrote 412 w · NN+1
  received 290 w · cut 122 w, 2 Findings lines · brief pass: haiku · $0.004 · 2 turns`); **one column**,
  what NN+1 received as six blocks, with the lines the brief pass cut left in place under their heading,
  struck and tagged `cut`, the heading's label counting `2 kept · 2 cut` (Fred, 2026-10-13: two columns of
  the same text were unreadable); **Checks · code, no model** under it: shorter than what it compacts, Goal
  and Troubleshooting whole, open questions kept (n of n), continuity (names a file from the previous Files
  touched), no invented path.
- **The task head**: prompt.md; **Open questions · n open** from the briefs, each with the step that opened
  it and the one that closed it (orange `?` open, green `✓` closed); **Chain log**, one line per move with
  the route notes; Stop and Pause (running), Clear (done).
- **Nothing picked** (Esc inside the Board, or a folded task picked): **Measure · <project> · last N
  tasks**: per kind, the median brief in, context reached and note out as 20-cell bars (context past 150K
  in orange) and the one-line reading (brainstorm 5.1 item 6).

### 8.4 Keyboard

Up / Down walk the chain (steps and handoffs, into and out of a fix bracket in order); Left / Right the
tasks; Enter opens the picked step's session page (Back returns to the Board); Esc clears the pick, then
leaves the Board to the page it came from. The pick is an ink outline, like a focused control.

## 9. Usage page (plan 18)

- **Models · fills** after the four figures: one row per model (the model, not the harness; the second
  line says `claude`, `via codex`, `via opencode, cmd`), three bars day / week / month of 20 cells, the
  pace as the orange outline cell, the figure as the share of pace (orange over pace). A model with no
  allowance: dotted bars, `–`, `no allowance`. Legend: `used`, `linear pace (day 13 of 31 for the month)`,
  and the orange sentence. One muted line: `balance_margin 0.2 · warn_at 0.8 · the Opus fill counts both
  CLIs. Allowances in config.json "allowance"`.
- **Verify FAIL rate by hour · last 30 days**: rows per rung that wrote the checked step, 24 columns, four
  red tones (`l1` to `l4` over `--bad`), hover `14:00 opus: 3 of 7 FAIL`, a dotted row for a rung with no
  verify yet. Under it the one-line reading and that it feeds `peak_hours` (off).
- The calendar, the picked day and the Days / Weeks / Months columns stay as locked; the picked day's model
  line lists harness rungs and `cost unknown · n runs`.
- Footer: `Codex usage x its price row; OpenCode and Command Code runs without usage count as unknown,
  never as zero`.

## 10. States and words

| Thing | States shown | Word and mark |
|---|---|---|
| Harness row | on, off, not found, pending | `● on` / `○ off` / `△ not found` / `...` |
| Rung | Claude, other harness | `sonnet · medium` / `codex · gpt-5.6-codex · medium` |
| Step cost | exact, estimated, unknown | `0.84` / `~0.84` / `? cost` |
| Step context | known, hand-off zone, unknown | cells and `92K` / `164K` in orange / `unknown: codex reports spend` |
| Handoff connector | ok, cut, fallback, writing, pending | `handoff 290 w` / `· cut 122 w` (tone) / dashed / blue dashed / dotted line |
| Handoff line | kept, cut | plain / struck, muted, tagged `cut`, in place under its heading |
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

## 12. Decisions for Fred

| # | Question | Proposed |
|---|---|---|
| ID-1 | Brainstorm 7 said a connector turns orange when the brief cut findings | No: orange stays "needs you". A cut is a tone step on the chip's cells plus `cut 122 w`; a code fallback is dashed |
| ID-2 | Where the auto hand off (D-5, off by default) is switched | A Window runs group in the settings popover, next to Harnesses, Turn on / Turn off; config.json stays the source of truth |
| ID-3 | Context of a non-Claude step: an estimate (characters / 4, hatched) or unknown | Unknown, as plan 5 3.6 decided; the hatched estimate is a plan 25 option if the live runs show usable token counts |
| ID-4 | How the Board opens | A button that widens the window and opens the page, size kept in window.json; never by dragging alone |
| ID-5 | Cells of a handoff | 1 cell = 50 words, 10 cells = `brief_max_words` 500; a handoff over 500 words shows 10 cells plus the figure |
| ID-6 | Cells of a fill | 20 cells = the window's allowance (day, week or month), 1 cell = 5 %; the orange outline cell marks the pace |
| ID-7 | The replan wait | A task `waiting` (orange) on the Task page, the Board and the list card, with the plan before and after; Confirm plan, Keep old plan (runs Prep's steps), Stop |
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
