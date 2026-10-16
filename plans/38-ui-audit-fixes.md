# Plan 38: Fixes from the UI/UX audit of 2026-10-16. Guided implementation plan

> Findings: [../reviews/2026-10-16-ui-ux-audit/README.md](../reviews/2026-10-16-ui-ux-audit/README.md) (dual
> review, 28/40). Master: [../PLAN.md](../PLAN.md). Rules: [../CLAUDE.md](../CLAUDE.md).
>
> Start state: `686524b` (plan 36 task 4, branch `claude/project-thread-r9z0h9`). Anchor by the quoted lines,
> never by line numbers; the numbers below are those of 686524b.

Status: written 2026-10-16; no code changed. **Waiting on Fred for D1-D6** (section 3). Each decision is written
for option (a); the tasks below assume (a). Every task writes its test first where a test can see the change
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
| 8 | Fred's live check on Windows; PLAN.md row and History | all | none |

One commit each: `plan 38 task N: <what> (<findings>) (<n> tests OK)`.

### Task 1 (U1)

In `console/server.py`, the chat-task line, map an idle session to Replied for a chat task only (D1 a). Leave
`state.py` as is, so the sessions list keeps an old idle chat out of Replied:

```python
    if t.get("chat") and r is not None:  # plan 30: a chat task sits where its session would; plan 38: idle is a turn over, Fred's next
        group = (r["group"] if r["group"] in ("needs", "replied") else
                 "replied" if r["state"] == "idle" and t["state"] == "running" else
                 "working" if r["group"] in ("working", "empty") else "done")
```

Tests: `test_server`: a chat task whose session row is `state idle, group working` and task state running lands in
`replied`; a done chat task with an idle session stays `done`. Check the inspector: `stepShown` already says replied.

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

- Tokens: `.lbl` 11 px; footer hints and picker foot 11 px; 9.5 px weekday, tag and heat-map labels to 10 px
  (they are data captions, D4 a), everything functional to 11 px.
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
- Title (D6 b in section 3): `ContextCompanion` stays until Fred names it.
- Landmarks: `<main>` around the Board, `<nav>` on the page buttons, an `aria-live="polite"` region for OFFLINE,
  Writing and "as saved".
- `:active` press feedback: `.btn:active, .v-th:active, .v-sr:active { transform: scale(.97); }` with
  `transition: transform 120ms ease-out` under `prefers-reduced-motion: no-preference`.

### Task 8

Fred on Windows, 100 % and 130 %: 340, 400, 900 px; a real week; a replied chat (U1, U2); Add next step from the
Handoff tab (U3); the Settings page (U4); light theme selects. Then the PLAN.md row and History.

## 3. Decisions for Fred

- **D1** Idle into Replied: (a) for chat tasks only, in server.py (sessions list unchanged); (b) in state.py for
  every session, as the audit suggests (old idle chats would fill Replied).
- **D2** Settings: (a) its own page next to Usage and Models; (b) keep it in the picker, only unify to switches.
- **D3** Narrow window: (a) hide the legend under 400 px and one `...` page menu under 372 px; (b) wrap the legend
  and keep the page buttons, smaller.
- **D4** Data captions (weekday, tags, heat-map hours): (a) 10 px; (b) 11 px like all text.
- **D5** Home pane: (a) auto-pick the first Needs you / Replied step; (b) keep Measure as home, shorten its text.
- **D6** (a) darken light `--off` one step; (b) the window title: keep `ContextCompanion`, or rename to Claude
  Console now.
