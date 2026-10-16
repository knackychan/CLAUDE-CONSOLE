# Plan 38: Fixes from the UI/UX audit of 2026-10-16. Guided implementation plan

> Findings: [../reviews/2026-10-16-ui-ux-audit/README.md](../reviews/2026-10-16-ui-ux-audit/README.md) (dual
> review, 28/40). Master: [../PLAN.md](../PLAN.md). Rules: [../CLAUDE.md](../CLAUDE.md).
>
> Start state: `686524b` (plan 36 task 4, branch `claude/project-thread-r9z0h9`). Anchor by the quoted lines,
> never by line numbers; the numbers below are those of 686524b.

Status: written 2026-10-16. Fred decided 2026-10-16: D1 b, D2 a, D3 a, D4 b, D5 a, D6 a (name open); U11 added.
The tasks below follow those answers. Every task writes its test first where a test can see the change
(server and state code), and checks web changes headless with `tests/fake_claude.py` as in plan 36 Task 4.

## 1. Findings taken

| Id | Audit | Where | Defect |
|---|---|---|---|
| U1 | P1 | `console/state.py` group switch (`elif state == "replied": group = "replied"` / `else: group = "working"`); `console/server.py` `if t.get("chat") and r is not None:` | an idle session sits in Working; a chat task follows it, so a replied chat hides under Working while the inspector says REPLIED |
| U2 | P1 | `web/app.js` `handPane`: `if (s.state === "running") return ... Writing` | a replied chat step's Handoff tab says Writing |
| U3 | P2 | `web/app.js` `stepButtons`, `nextActions` (only called from `chatTab`) | Add next step and Finish task vanish off the Chat tab |
| U4 | P2 | `web/app.js` picker Settings band (`Turn on` buttons next to `role="switch"`, buttons inside `role="listbox"`) | one surface, two controls for on/off; picker is the settings page |
| U5 | P2 | `web/style.css` `@container (max-width: 372px) { .v-pg { display: none; } }`; `.v-calh` legend | 340 px: legend overflows (`button.v-over 276..354`); Usage and Models lose their route |
| U6 | P2 | `web/style.css` `.lbl` 10.5 px, 9.5 px weekday and tag labels, `.v-pg` 17 px, `?` 16-18 px, week arrows 18 px | text and targets under the 11 px / 24 px floor |
| U7 | P3 | `web/app.js` calendar strip and Usage day columns | 14 (Board) and 31 (Usage) tab stops; make each a roving group |
| U8 | 2nd P1 | `web/app.js` Board right pane, `Measure: pick a project` | the home is an instruction, not the chat that needs Fred |
| U9 | 2nd P2 | `web/app.js` `BWORD` replied tone `y` | REPLIED orange in the inspector, grey on the list; orange means needs-you only |
| U10 | minor | see Task 7 | copy and contrast fixes |
| U11 | Fred | `web/app.js` `fold()`, `web/style.css` `.lbl` | clickable fold heads look like static labels; too many headers and meta lines |

Not taken (notes, not defects): the three status words (the mock uses them), the failed raw chat's sprite (wait for
a seeded verify step), the Emil `max-height` and `.sw left` rows (feel only; a later polish pass), `<select>` in
light theme on Windows (Fred's live check, Task 8).

## 2. Tasks, in order

| # | Delivers | Findings | Tests |
|---|---|---|---|
| 1 | idle chat in Replied | U1 | +2 (test_state, test_server) |
| 2 | Handoff tab reads the replied state | U2 | headless check |
| 3 | task levers on every inspector tab | U3 | headless check |
| 4 | Settings out of the picker | U4 | headless check, existing picker tests green |
| 5 | 340 px: legend and routes | U5 | Playwright overflow check at 340 |
| 6 | type and target floor, roving strips | U6, U7 | Playwright size scan, tab walk |
| 7 | home pane, Replied tone, copy, contrast, title | U8, U9, U10 | headless check, contrast scan |
| 8 | clickable looks clickable; less chrome | U11 | headless check, Playwright cursor scan |
| 9 | Fred's live check on Windows; PLAN.md row and History | all | none |

One commit each: `plan 38 task N: <what> (<findings>) (<n> tests OK)`.

### Task 1 (U1)

D1 b (Fred: try it and see): in `console/state.py` the group switch maps `idle` with `replied`, for every session:

```python
            elif state in ("replied", "idle"):  # plan 38 D1 b: an idle session's turn is over, the next is Fred's
                group = "replied"
```

The chat-task line in `server.py` then needs no change (it already follows `replied`). Tests: `test_state`: an
idle session's row has group `replied`; `test_server`: a chat task with an idle session lands in `replied`. Watch in
Task 8 whether old idle chats crowd Replied; if they do, fall back to D1 a (chat tasks only, in server.py). Check the inspector: `stepShown` already says replied.

### Task 2 (U2)

`handPane`: replace `if (s.state === "running")` with
`if (stepShown(t, s) === "running" || (s.state === "running" && !(t.chat && chatReplied(s))))`, so a replied chat
step shows its HANDOFF note or the "No handoff" line. Simplest equivalent kept in the code:

```js
  if (s.state === "running" && !(t.chat && chatReplied(s))) return '<p class="note m">Writing. Shows here when the run ends.</p>';
```

Check: `900-dark-step-hand` reproduces the HANDOFF block.

### Task 3 (U3)

Move `nextActions(t, d)` out of `chatTab` and into `stepButtons`, after Stop and before Open chat, as `btn sm`
buttons; Continue stays in `chatTab`. Make Add next step the filled `go` button when `lv.add_next === ""` and the
step is replied or done, and drop `go` from Open chat (second assessment: the primary is the next action). The focus
return in `openNextForm`'s cancel (`querySelector('[data-tact="nextopen"]')`) still finds it.

### Task 4 (U4, D2 a)

Split Settings out of the picker into a third page next to Usage and Models: `Settings` with the harness rows (one
`role="switch"` per harness, Turn on / Turn off buttons removed, port the band from `claude/project-thread-j5s3mn`
if it applies cleanly, else write it here), the Models file line (Open, Reload) and Window runs. The picker keeps
the project list only, so its `role="listbox"` holds options only and its foot hint is true. The `v-pg` button
row gains `Settings`.

### Task 5 (U5, D3 a)

- Under `@container (max-width: 400px)` hide the `tone: ... figure: ...` legend line; the footer `?` already owns it.
- Replace the `.v-pg { display: none; }` rule with a single `...` page menu button under 372 px that lists Usage,
  Models, Settings (a small popover, Esc closes, arrows move).
- Check: Playwright overflow check at 340 px, both schemes, reports nothing.

### Task 6 (U6, U7)

- Tokens: `.lbl` 11 px; footer hints and picker foot 11 px; 9.5 px weekday, tag and heat-map labels to 11 px
  too (D4 b): no text under 11 px anywhere in `web/style.css`.
- Targets: `.v-pg`, `.q` (`?`) and the week arrows to `min-height: 24px; min-width: 24px`; effort radios 24 x 24.
- Roving strips: the calendar days and the Usage day columns become one tab stop each (`tabindex 0` on the picked
  or today's item, `-1` on the rest), Left / Right / Home / End move, Enter picks; the week arrows on Alt+Left /
  Alt+Right. Use the same helper as the tab lists (`role=tab` roving code).
- Check: tab walk at 900 px reaches the first task in 7 stops or fewer; size scan finds no target under 24 px.

### Task 7 (U8, U9, U10)

- U8 (D5 a): with nothing picked, the Board's right pane auto-picks the newest step of the first card in Needs you,
  else Replied; Measure shows only when neither group has a card, or behind the day pick and the `model usage` fold.
  An explicit pick by Fred is never overridden.
- U9: `BWORD.replied` tone from `y` to ink (`""`); orange stays for waiting, needs and Send answer.
- Copy: run line `` `${n} file${n === 1 ? "" : "s"} changed since` `` with no period and no dangling `·`;
  `Starting the run …` (one ellipsis character); `limit $15` (`"limit $" + sp.budget`); the composer's second
  `in proj` dropped; under $1 the Doto figure shows cents as `.42` with no leading `0`, and `0` alone at zero.
- Contrast (light): bubble labels PROMPT and CLAUDE, the tuning switch `off`, and `.nav` / `.rb` week arrows to
  `--mut` at 4.5:1 or better; `--off` cells in light raised until the spend row reads (D6 a: one step darker,
  measured against `--win` at 3:1 for a non-text graphic).
- Title: `ContextCompanion` stays until Fred names it (open).
- Landmarks: `<main>` around the Board, `<nav>` on the page buttons, an `aria-live="polite"` region for OFFLINE,
  Writing and "as saved".
- `:active` press feedback: `.btn:active, .v-th:active, .v-sr:active { transform: scale(.97); }` with
  `transition: transform 120ms ease-out` under `prefers-reduced-motion: no-preference`.

### Task 8 (U11, Fred 2026-10-16)

Fred: "a lot of text that doesn't seem interactable but is, such as prompt.md; all the headers and details make the
UI cluttered". Cause: `fold()` (`web/app.js`) renders its head label with `.lbl`, the same muted mono uppercase as a
static section label, so `prompt.md`, Chain log, Checks, Facts, Route, Why it ran, Window runs, Allowances and
`Verify FAIL by hour` read as captions.

- One rule in `web/style.css`: anything clickable has an ink-coloured label, a caret on the left (`▸` closed, `▾`
  open, rotated by `aria-expanded`), `cursor: pointer` and a `--raise` hover background; static labels keep `.lbl`
  muted with no caret. `fold()` gets its own class `fl` for the head label instead of `lbl`.
- Fold heads drop their `info` text to one short figure (e.g. `prompt.md` shows no `Done when:` line in the head;
  Chain log shows `12`, not the last move); the detail moves into the body.
- Inventory every static heading and meta line in the inspector, task page and picker during this task; remove any
  that repeats what the head or the cells already say (the task label shown twice, rung and cost both in the meta and
  in Route, `task 1016-b292` in the step meta when the task head is above). List what was cut in the commit body.
- Playwright check: every element with `cursor: pointer` is a button, link or `role` control, and every such control
  has `cursor: pointer`.

### Task 9

Fred on Windows, 100 % and 130 %: 340, 400, 900 px; a real week; a replied chat (U1, U2); Add next step from the
Handoff tab (U3); the Settings page (U4); light theme selects. Then the PLAN.md row and History.

## 3. Decisions (answered 2026-10-16: D1 b, D2 a, D3 a, D4 b, D5 a, D6 a; title open)

- **D1** Idle into Replied: (a) for chat tasks only, in server.py (sessions list unchanged); (b) in state.py for
  every session, as the audit suggests (old idle chats would fill Replied).
- **D2** Settings: (a) its own page next to Usage and Models; (b) keep it in the picker, only unify to switches.
- **D3** Narrow window: (a) hide the legend under 400 px and one `...` page menu under 372 px; (b) wrap the legend
  and keep the page buttons, smaller.
- **D4** Data captions (weekday, tags, heat-map hours): (a) 10 px; (b) 11 px like all text.
- **D5** Home pane: (a) auto-pick the first Needs you / Replied step; (b) keep Measure as home, shorten its text.
- **D6** (a) darken light `--off` one step; (b) the window title: keep `ContextCompanion`, or rename to Claude
  Console now.

## 4. History

- 2026-10-16 - Tasks 1, 2, 3 and 8 placed in one commit (they share web/app.js). 740 tests on Linux: all pass but
  four that fail the same on 686524b here (test_tray import, test_redact Windows paths, test_usage local day,
  test_window screen), so they are Linux baseline, not this plan. +4 tests (test_server ChatTaskGroupTest 2,
  test_web FoldTest 1, the replied-footer test now asserts the dock); test_state's idle row now pins `replied`.
  Headless pass (fake claude, `replied_for_s` 5): an idle chat sits under REPLIED; Add next step, Finish task,
  Open chat, Mark done, Task on the Chat, Handoff and Route tabs; Add next step from Route opens the form on Chat;
  the Handoff tab of a replied chat says "No handoff", not Writing. Departures: U2 shows the note only once the run
  writes it (a chat's HANDOFF block in the live bubble is not yet a note; showing it needs the service to parse
  the live reply, left for later). U11 on the task page: the Done-when line left the prompt.md head, Chain log
  shows its count only, Open questions shows only when there are any, the dated folder id left the meta (the
  label chip copies it), and the "Stop off / Retry off / Delete off" line became the meta's tooltip. The Prompt
  chip in the chat keeps its own look (already a bordered control).
