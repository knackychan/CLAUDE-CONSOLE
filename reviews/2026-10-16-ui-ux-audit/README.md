# Claude Console: UI/UX audit (2026-10-16)

Method: dual-agent (A: an isolated design review by a second session · B: Impeccable's detector and Playwright evidence by this session), then one synthesis. This is an audit: no code was changed.

Target: branch `claude/project-thread-r9z0h9` at commit 686524b (plan 36 task 4), the Board as the one view (plan 30), run headless with `tests/fake_claude.py` as the claude exe (the plan 36 seed), screenshotted in Chromium at 900, 400 and 340 px wide, dark and light, plus 400 px at 1.3x scale.

Evidence folder: `reviews/2026-10-16-ui-ux-audit/` (30 screenshots and `impeccable-detect.json`). Names read `<width>-<scheme>-<view>.png`.

Two caveats on the evidence:

- The container has neither Segoe UI Variable nor Cascadia Mono, so every screenshot renders fallback faces. Judgements below are about sizes, spacing, colour and behaviour, not the letterforms Fred sees on Windows.
- The seed is small: four raw chat tasks (one replied, one with a STOP question, one with a failed verdict, one idle) and no multi-step task, no Prep card, no spend. The Board with a real week of work is read from the locked mock (`design/rework/locked/`, `design/board-one-view/`) and the code, not from a live capture.

## Toolkit used

From the attached list, section 5, this is what could be installed and run here, and what each contributed:

| Skill | Status | What it did |
|---|---|---|
| Impeccable 4.6 (pbakaus/impeccable) | installed, launcher ran | `impeccable context` and `impeccable detect --json` over `web/`; the `critique` playbook (Nielsen scores, personas, P0-P3), `operate.md` and `craft-floor.md` as the rubric |
| Playwright + bundled Chromium | ran | 90 screenshots, a contrast scan (alpha-blended), target-size scan, tab-order walk, overflow check, motion inventory |
| Vercel web-design-guidelines (agent-skills) | fetched the live rules | a file:line pass over `web/index.html`, `web/style.css`, `web/app.js` |
| Emil Kowalski `emil-design-eng` | installed | the motion and press-feedback review (Before / After table) |
| UI/UX Pro Max 2.15 | installed, searched | UX guideline lookups (focus, empty states, labels, text reflow, error recovery) |
| gstack `design-review` | read only | its driver needs Aside or a bun build; its UX laws and audit checklist were read and applied by hand |
| Design Motion AI-slop checklist (from the list) | applied | the dashboard slop list at the end |
| Taste Skill (tasteskill.dev) | not found | the site exposes no public repo; skipped |

Not applicable here: 21st.dev Magic, Mobbin, Aura, Open Design and the logo and print tools in the list.

## Design health score

Nielsen's ten heuristics, scored 0-4 by both assessments and reconciled.

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | A replied chat drops from Replied to Working once its session goes idle; the Handoff tab says "Writing" on a step that has replied |
| 2 | Match system and real world | 3 | Fred's vocabulary is consistent (Replied, Needs you, Handoff), but "rung", "fills", "Raw, prep skipped" and "tone: the day's spend · figure: tasks done" are code names on screen |
| 3 | User control and freedom | 3 | Esc, Cancel, Stop and Mark done are everywhere; delete has a confirm bar; nothing undoes Mark done |
| 4 | Consistency and standards | 2 | Turn on buttons next to an on/off switch in one popover; task levers that vanish with the tab; three routes to Usage; a window called ContextCompanion |
| 5 | Error prevention | 3 | Start step stays disabled until the route resolves; out-of-range tuning values block Save |
| 6 | Recognition rather than recall | 3 | The key hints in the footer help; Ctrl+Enter for Raw lives only in a tooltip; "?" is the glyph for an unknown context |
| 7 | Flexibility and efficiency | 3 | Everything has a key, but a keyboard user tabs through 14 calendar days and 5 header buttons before the first task |
| 8 | Aesthetic and minimalist design | 3 | Coherent and dense; the Usage page lists 22 identical empty model rows, the calendar legend line is permanent |
| 9 | Error recovery | 3 | OFFLINE banner, Try again, failed tries kept; a failed harness toggle only says "..." |
| 10 | Help and documentation | 2 | Help is title tooltips and 16 px "?" buttons; nothing explains the cells, the sprites or the groups on first run |
| | **Total** | **28/40** | **Good, with a handful of real defects** |

## Design specificity verdict

**Authored, not interchangeable.** The cells motif (context, spend, fills, sprites), one Doto figure per page, orange reserved for "needs you", mono labels, the calendar strip and the chain of steps under each task could not be lifted onto another product unchanged. The restraint fits Operate mode: no gradients, no cards-in-cards, no decorative motion, system fonts. Where it slips is at the edges: the pill's glyph letters (?, ○, ↩) stand in for an icon system, the project picker doubles as the settings page, and the bottom of the Board carries key hints that read as a terminal's.

**Deterministic scan** (`impeccable detect`, 9 findings, `impeccable-detect.json`):

- 3x cramped padding on the `.top` bars (children flush against the border-bottom): the detector reads the bar's border as the container edge. Low value, but the 36 px bar with 1 px text inset is tight.
- 2x undersized functional text: the footer key hints and the picker foot at 10.5 px (`web/style.css:768`), below its 11 px floor. Real; see P2 below.
- 1x tiny body text: 10.5 px. Same root.
- cream palette (light `--page: #dedcd6`): false positive, a deliberate token (`web/style.css:17`).
- repeating-gradient stripes: false positive, the "no data" columns and the hatched cell are the locked language.
- side-tab accent border (`web/style.css:928`, `border-left: 2px solid var(--line)`): false positive, that is the tree line of the step list.

Browser overlay: not run; the app's HTML is served from the Python service, not a file, and the point of the overlay (a [Human] tab) does not exist in headless Chromium. The Playwright scans below stand in for it.

## What's working

- **One grammar for every quantity.** Spend, context, fills and status all read as cells; a cell blinks only when something is live, and only under `prefers-reduced-motion: no-preference` (`web/style.css:57`, `68-74`). There is no `transition: all` and no entrance choreography anywhere.
- **Orange means one thing.** "1 needs you" in the header, the WAITING card outline, the step's question line, the Send answer button: one colour, one meaning, and the needs group sits first. The focus ring is ink, not orange (`web/style.css:33`), so a keyboard user never mistakes focus for a demand.
- **Empty states teach.** "Measure: pick a project to measure its tasks, or pick a task, a step or a day" on the Board's right pane, "No handoff: step 1 gets the task goal and Prep's context pack", "No transcript left for this day". These explain the model rather than saying nothing is here.
- **Keyboard first.** Tabs are roving (tabindex -1 off the active tab), the picker is a list box with ↑ ↓ Enter, Esc closes the inline form before it backs out of the pick (`web/app.js:3634`), and the Add next step form returns focus to its opener on Cancel (the plan 36 pass confirms it).

## Priority issues

**[P1] A replied chat moves from Replied to Working when its session goes idle.**
Seen: the seed's first chat (`fix add() in calc.py`) sat under REPLIED · 1 in `900-dark-board.png`; ten minutes later, in `900-dark-board-4tasks.png`, it sits under WORKING · 1 with the grey task sprite while nothing is running. The `/api/state` row says `state: idle, group: working`. Cause: `console/state.py:522-524` sends `replied` to the replied group but everything else, idle included, to working; `console/server.py:2045` then seats a chat task where its session's group is, and its own comment says "idle: its turn is over". Why it matters: Working is the group Fred reads as "the machine is busy"; a chat that is waiting for him hides there, and the inspector still says REPLIED (`stepShown` in `web/app.js:2940` treats idle as replied). Fix: in `state.py` map `idle` to the replied group (or to done when the task is not a chat), so chain and inspector agree. Suggested command: `/impeccable harden`.

**[P1] The Handoff tab contradicts its own label on a replied chat step.**
Seen: `900-dark-step-hand.png`. The tab reads "Handoff 65 w", the chat bubble shows the HANDOFF block, the pane says "Writing. Shows here when the run ends." Cause: `handPane` tests `s.state === "running"` (`web/app.js:3052`) while a chat step stays "running" by design and `stepShown` already knows it replied. Fix: gate on `stepShown(...) === "running"` (or `chatReplied`), and show the block. Suggested command: `/impeccable harden`.

**[P2] Task-level levers depend on which inspector tab is open.**
Seen: on the Chat tab the dock offers Continue, Add next step, Finish task, Open chat, Mark done, Task; on Received, Handoff, Route or Files only Open chat, Mark done, Task remain (`web/app.js:2982` builds the bar; Add next step and Finish task live inside `chatTab`). Why it matters: Add next step is the task's primary action after a reply, and it disappears exactly when Fred is reading the handoff he is about to send. The mock's inspector keeps the levers in the dock bar across tabs. Fix: move Add next step and Finish task into `stepButtons` so every tab carries them; keep Continue with the chat. Suggested command: `/impeccable layout`.

**[P2] The project picker is also the settings page, and its controls disagree.**
Seen: `900-dark-picker.png`. The dialog is labelled "Pick a project" (`web/index.html:88`) yet holds Settings, Harnesses with three "Turn on" buttons (`web/app.js:846`), a Models line with Open and Reload, and Window runs with a `role="switch"` (`web/app.js:860`). Why it matters: Operate mode's rule is one control vocabulary per surface; here the same on/off decision is a button on one row and a switch on the next, and the Esc hint, "sorted: needs you, live, recent", applies to half the dialog. The 2026-10-13 interface rework specified one switch per harness row with the Turn on / Turn off buttons gone; that rework lives on `claude/project-thread-j5s3mn` and has not reached this branch. Fix: either port the settings band from that branch, or split Settings out of the picker into the Models and tuning page (which already has a Tuning tab) and leave the picker to pick. Suggested command: `/impeccable distill`.

**[P2] At 340 px the calendar legend overflows the window and the page buttons vanish with no replacement.**
Seen: `340-light-board.png`, "model usa" cut at the right edge; Playwright's overflow check reports `button.v-over 276..354` in a 340 px window at both schemes. The `@container (max-width: 372px)` rule hides Usage and Models (`web/style.css:1003`); Usage stays reachable through the day inspector's Usage button and Models only through the picker's link. Why it matters: 340 is the window's smallest form and the one Fred keeps at the screen edge; the overflow is a visible bug and the hidden buttons are an orphaned route. Fix: let `.v-calh` wrap or drop the "tone … figure" legend line under 400 px (it is a legend, it can live behind the "?" that the footer already has), and keep one route to Usage and Models under 372 px (fold them into the picker's Settings band, or a single "…" page menu). Suggested command: `/impeccable adapt`.

**[P2] Functional text at 9.5 to 10.5 px, and the smallest hit targets, sit under the floor the skills set.**
Measured: 114 elements at 10.5 px Cascadia (the `.lbl` class, `web/style.css:38`), 62 at 11 px, 14 at 9.5 px (weekday labels `web/style.css:864`, tags at `:522`, `:540`, the heat map hours at `:676`); the footer hints and picker foot at 10.5 px. Targets under 24 px: the Usage and Models page buttons at 17 px tall (`web/style.css:849`), the "?" legend at 18 px (`:771`), the Models page "?" at 16 px (`:701`), the week arrows 18 px wide (`:859`), the copy-label chip 18 px, the effort radios 22 x 24 (`:253`), the Usage day-chart columns 9 to 11 px wide and each a tab stop. Why it matters: Fred runs the window at 100 % and at 1.3x scale; at 1.3x the 400 px capture (`400-dark-x1.3-board.png`) is comfortable, at 1x the labels are at the edge of legibility and the page buttons are a precision click. Fix: raise `.lbl` and the footer to 11 px, the `.v-pg` and `.q` buttons to 24 px tall with the same 11 px type, and make the day-chart columns one tab stop with arrow keys. Suggested command: `/impeccable typeset`.

**[P3] Twenty tab stops before the first task.**
Measured by a tab walk at 900 px: scope, needs, Usage, Models, fold, week-before arrow, 14 day buttons, the "model usage" fold, then the first task. The calendar days are plain buttons, not a roving group. Fix: one tab stop for the strip with ← → between days (the tab lists already do this), and the two arrows on Alt+← →.

## Persona red flags

**Alex (power user, keyboard):** lands on the Board and presses Tab; reaches the first task on press 20. Ctrl+Enter for Raw is in a tooltip, not in the footer hints. Reads the handoff before sending the next step and finds Add next step gone from the dock. Will keep using the mouse for the one thing he does most.

**Jordan (first-timer, or Fred after a month away):** sees "0.00", "today, USD · $0.00/min · limit 15", a 30-cell strip, "tone: the day's spend · figure: tasks done", "model usage ▾", "1016-b292", "a chat · Raw, prep skipped", a "?" in the step row. Nothing on screen says what a cell is, what the hatched cell is, what the sprites are, or that "?" is an unknown context rather than a question. The footer "?" is 18 px and only on the Board.

**Sam (screen reader):** the task rows are `div role="button"` with `tabindex` and the Enter handler is global, so they work, but there are no landmarks at all (`main`, `nav`, none), the only heading on the Board is the inspector's `h2`, and the window title says ContextCompanion. The Usage chart exposes 32 columns as 9 px buttons with good labels, which is more rows than content. The sprites are pure CSS with no text alternative; the status word next to them carries the meaning, which is right.

## Minor observations

- Status words. "Replied" is used for a chat whose turn ended and "Waiting" for a step with a STOP question (`web/app.js:2930`), yet the chain's section is "Needs you" and the step row says "which file?". Three words for the same demand on one screen; the mock uses the same three, so this is a note, not a defect.
- The run line under the chat, "Streamed from this window run. start e418d03 · 0 file(s) changed since. · success · $0.01 · 2 turns" (`web/app.js:1393`), carries a dangling "·" after the full stop and "file(s)"; write "0 files changed" and drop the period.
- The failed-verdict chat (`900-dark-step-fail-tools.png`) reads REPLIED with the waiting sprite; "VERDICT: FAIL x" is only the last line of the bubble. For a raw chat that is defensible; a verify step gets the red word. Worth a second look once a verify step is seeded.
- The Usage page with no spend: "over $15: 0 of 0 days used" and 22 identical empty model rows, including the models of harnesses that are off (`900-dark-usage-days.png`). Hide the rows of a harness that is off, or fold them behind "11 models with no usage".
- The Models page has a Reload button alone in its bar until something is edited; "config.json · as saved" is the status. Fine, but the Tiers "+ rung ▾" and the "show" link on "3 hidden · codex is off" are the only underlined links in the app; everything else is a button.
- The pill (`900-dark-pill-peek.png`): four chips with a 9 px glyph under each (?, ○, ↩, ↩). The glyphs are the craft floor's "unicode standing in for icons"; the orange dot on the first chip is the one that carries meaning. Consider dropping the glyph row and letting the dot and the cells speak.
- No `:active` state exists on any button (the stylesheet has no `:active` rule). Hover changes the border only. See the Emil table.
- `<select>` elements rely on the browser's dark `color-scheme` (`web/style.css:13`); fine in WebView2, worth a check in the light theme on Windows where native selects stay light.
- Light theme contrast: the two bubble labels fail AA at 10.5 px (PROMPT 4.26:1 on the violet tint, CLAUDE 4.17:1 on the blue tint, `900-light-step-chat.png`), and "off" on the tuning switches sits at 4.38:1. The week arrows are 1.5:1 in light and 1.7:1 in dark (`.nav`, `.rb` in Usage), which reads as disabled. Everything else passes; dark mode passes everywhere.
- The title is "ContextCompanion" in `web/index.html:6` and `console/window.py:17` (marked temporary on 2026-10-11) while the repo, the docs and the mock say Claude Console.

## Vercel Web Interface Guidelines pass

```text
## web/index.html
web/index.html:6   - title "ContextCompanion" differs from the product name
web/index.html:1   - no <meta name="theme-color">; harmless in pywebview, add if ever opened in a browser
web/index.html:9+  - no landmarks (main/nav); the Board is three sections with no heading
web/index.html:50  - input#filepick has no label; it is hidden and driven by Attach, so ok

## web/style.css
web/style.css:768  - 10.5px functional text (footer hints); 864 - 9.5px weekday labels
web/style.css:849  - .v-pg 17px tall targets; 771, 701 - 18px and 16px "?" buttons
web/style.css      - no :active rule anywhere (press feedback)
web/style.css      - no @media (hover: hover) gate; fine for a desktop window
web/style.css:33   - focus-visible ring present, 2px ink: pass
web/style.css:57   - prefers-reduced-motion honoured: pass; no transition: all: pass
web/style.css:36   - tabular-nums on figures: pass

## web/app.js
web/app.js:1393    - "file(s)" and a dangling separator in the run line
web/app.js:795     - "Starting the run ..." uses three dots, not an ellipsis
web/app.js:846     - Turn on / Turn off buttons where the same popover uses a switch (860)
web/app.js:2502    - 14 calendar day buttons, each a tab stop; make the strip a roving group
web/app.js:1919    - Usage day buttons: same, 31 tab stops on the Usage page
web/app.js:1864    - usd() formats with toLocaleString("en-US"): pass
web/app.js:3313    - tabs with role=tab and roving tabindex: pass
```

## Emil Kowalski review (motion and feel)

The app animates almost nothing, which is the right call for a window Fred glances at hundreds of times a day. The table lists the few places the feel can be tightened.

| Before | After | Why |
| --- | --- | --- |
| no `:active` rule on `.btn`, `.v-th`, `.v-sr` | `.btn:active { transform: scale(.97) }` with `transition: transform 120ms` | a press should be felt; hover only moves the border |
| `.sw` transitions `left .15s` (`web/style.css:308`) | `transform: translateX(28px)` with the same 150 ms ease-out | transform stays on the compositor; `left` triggers layout |
| `.card.grow` animates `max-height` 0 to 8em (`:74`, `:81`) | animate `grid-template-rows: 0fr` to `1fr`, or `clip-path`, with opacity | max-height easing is non-linear in time and jumps when content is short |
| `.spr.flip` keyframes on every state change (`:72`) | keep, 240 ms steps(3) is a state signal | the sprite is the one authored moment, matched to the cells |
| `.card.enter` outline blink 600 ms (`:73`) | keep, it is the one "needs you" entrance; confirm it does not fire on re-render | an entrance that replays on each snapshot would read as noise |
| the pill opens the peek card with no transition | none needed | opened dozens of times a day: no animation is the fast option |

## AI-slop checklist (dashboards)

| Check | Result |
|---|---|
| Purposeless gradients | none; the two repeating gradients are data (hatched cell, no-data column) |
| Pastel icon tiles | none |
| Four identical cards with no hierarchy | no; the Board has one figure and groups in a fixed order |
| 16 px corners and shadows on everything | no; 6 to 8 px radii, borders not shadows |
| Placeholder copy | none; every string is the product's own |
| One flat accent, one primary metric, hairline borders, tabular digits | yes on all four |

The deterministic cream-palette finding is the only slop flag, and it is a token Fred chose for the light theme.

## Screens inventory

Board: `900-dark-board.png`, `900-light-board.png`, `400-dark-board.png`, `340-light-board.png`, `400-dark-x1.3-board.png`, `900-dark-board-4tasks.png`, `400-dark-board-4tasks.png`. Step inspector: `900-dark-step-chat.png`, `900-light-step-chat.png`, `400-dark-step-chat.png`, `340-light-step-chat.png`, `900-dark-step-hand.png`, `900-dark-step-route.png`, `900-dark-step-stop.png`, `900-dark-step-fail-tools.png`. Add next step: `900-dark-step-nextform.png`, `400-dark-step-nextform-verify.png`. Picker: `900-dark-picker.png`. Day and legend: `900-dark-day-picked.png`, `900-dark-overpace.png`. Usage: `900-dark-usage-days.png`, `900-dark-usage-weeks.png`, `400-dark-usage-days.png`. Models: `900-dark-models-kinds.png`, `-tiers.png`, `-tuning.png`. Pill and states: `900-dark-pill-peek.png`, `900-dark-banner.png`, `900-dark-focus-tab4.png`.

## Questions to consider

- What if the picker only picked, and Settings became a page next to Usage and Models, with the harness switches, the models file and auto hand off on it?
- Does the Board need its legend line in the header at all, or does the "?" already own that job?
- What would it take for a step to carry its levers on every tab, so the Handoff tab is where Fred decides to send the next step?

## Second assessment (isolated design review)

The second session scored the same 28/40 without seeing this session's findings. Where the two meet, and where it saw more:

**Both found:** the picker as a settings panel (it adds that the Settings rows are buttons inside `role="listbox"`, `web/app.js:902`, which breaks option navigation for a screen reader), the 340 px overflow, the undersized mono text, no landmarks and one heading, the jargon on the card's second line, the Usage page's rows and prose with no data.

**It found, and this session agrees:**

- **[P1] The Board's right pane greets Fred with an instruction.** At 900 px two thirds of the window is "Measure: pick a project…" (`web/app.js:2737`) on every return. Fix: with nothing picked, auto-pick the newest step of the first card in Needs you or Replied so the Chat tab is the home; keep Measure behind the day pick or the "model usage" fold.
- **[P2] Replied is orange in the inspector and grey on the list.** The step head says REPLIED in the "y" tone (`BWORD`, `web/app.js:2930`) while the card and the REPLIED group label are muted. Orange is reserved for needs-you, so either the inspector word drops to ink or the list gets the same word in the same tone; today the two disagree.
- **Doto "0.00" reads as "0 + 00"** at 30 px in every capture (`web/style.css:853`): the point sits low and heavy. Drop the cents under $1, or use a smaller point glyph.
- **"limit 15" has no unit** in the header figure line; "limit $15".
- **Open chat is the filled primary button** on a step whose chat is already in the pane (`web/app.js:2985`); the primary should be the next action.
- **Light theme cells are faint:** `--off #d6d4ce` on `--win #f4f3ef` makes the spend row almost invisible in `340-light-board.png`.
- **The composer says "New task in proj" and "in proj ▾"** one line apart.
- **Effort is five blank cells** with aria-labels only (`web/app.js:609`); the level reads only on hover or in the truncated "Auto: the rules pick per …" line.
- **No `aria-live` region** for OFFLINE, "Writing" or "as saved": state changes are silent to a screen reader.

**Where this session reads it differently:** its "[P1] Needs you is not signalled on the list" came from a seed with only a replied chat. With a STOP question seeded (`900-dark-board-4tasks.png`) the list does say NEEDS YOU in orange, with the card outlined and the question on its second line. The real defect is the Replied tone mismatch above, not a missing signal.

The full second assessment follows as written.

---


