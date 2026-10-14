# Visual rework (2026-10-10)

Target for the rework sub-plan (PLAN.md row 6). Decision and summary: BRAINSTORM D11 and section 7.5.
Every session, figure and cost in these mockups is sample data. Open a file in a browser to click
through its views; each page has the window mock on the left and its reasoning on the right.

## Locked

| File | Artifact | What it is |
|---|---|---|
| [locked/cells-drawer.html](locked/cells-drawer.html) | https://claude.ai/artifact/SqX2KpJqpnV6Q7FA7zhVzn | **The target** (locked 2026-10-10, plan 07). Cells Drawer: Console Cells without the rail. The open window is one list (needs you / working / done today) with answer and unblock in place, a searchable project picker in the header, and a full-width session page (head, brief, Steps / Agents / Timeline / Chat). Views: pill, peek, list, session, asks you, empty / offline |
| [locked/console-cells.html](locked/console-cells.html) | https://claude.ai/artifact/9s2oCibRMRPYqdRC8ZAt5d | Console Cells: the tokens, type and cell motif that Cells Drawer keeps (plan 06 built its pill, peek and cells). Its rail, focus pane and Overview are replaced by Cells Drawer. Views: pill, peek, focus, asks you, overview, empty / offline / loading / error |
| [locked/usage.html](locked/usage.html) | - | The Usage page of Cells Drawer (locked 2026-10-11, plan 10): the month total, a calendar of daily cost (tones in multiples of the daily limit), the picked day by project and model, Days / Weeks / Months as columns of cells in $ or tokens (tokens count cache reads). Opened from the spend breakdown. Figures are this machine's transcripts as read on 2026-10-11 |
| [locked/cells-board.html](locked/cells-board.html) | https://claude.ai/artifact/T5VyJFHhHxhvKn1YTzi7Vx | Cells Board (locked 2026-10-13, plan 25): the window side of plans 5, 18, 23, 24 and 25. Nine Board views (step, running step, handoff, task head, replan wait, plan tab, plan gap wait, measure, empty) at 900 px and eight compact views (list with fills, Task page with the per-step context gauge and the handoff fold, Task page with sub-plans and with plan hold (plan 24), settings with the Harnesses switch, Prep with tier selects, a Codex session, Usage with fills and the FAIL-rate heatmap), in two zones: what Fred acts on in sight, the rest behind one closed line each. Design doc: [../brainstorm/2026-10-13-interface.md](../brainstorm/2026-10-13-interface.md) (decisions ID-1 to ID-9 in its section 12; ID-5 refused: no cells for a handoff's words) |

## Explored (not targets)

| File | Artifact | Outcome |
|---|---|---|
| [explored/a-pill-and-drawer.html](explored/a-pill-and-drawer.html) | https://claude.ai/artifact/Ac61ay92bKkBbKVfLNCpxz | A: kept the folding pill and the answer-in-place peek card |
| [explored/b-triage-board.html](explored/b-triage-board.html) | https://claude.ai/artifact/TLUve8h6ZWkS6sSDoc1Nn3 | B: not chosen; the sparkline idea became the activity cells |
| [explored/c-rail-and-focus.html](explored/c-rail-and-focus.html) | https://claude.ai/artifact/9x9mZUKL84WztY2xpRS9b4 | C: kept the session rail, focus pane, burn rate and agent lanes |
| [explored/d-cells-drawer.html](explored/d-cells-drawer.html) | https://claude.ai/artifact/SqX2KpJqpnV6Q7FA7zhVzn | D: locked as [locked/cells-drawer.html](locked/cells-drawer.html) (this file is the proposal that was reviewed). Console Cells without the rail: A's list as home, C's focus content on a full-width session page, a searchable project picker in the header |
| [explored/ca-rings-and-pill.html](explored/ca-rings-and-pill.html) | https://claude.ai/artifact/5jcCWoKfExdC7ncBJjvgCL | C + A merge; Console Cells is its alternate. Written before the anti-slop pass (has an eyebrow label, no sample-data note) |

## Notes for the build

- The mockups load JetBrains Mono and Doto from Google Fonts only so they render anywhere. The app
  makes no network calls: Doto ships as a local woff2 in `web/`, and the figures use Cascadia Mono.
- The mockups are design references, not code to copy: `web/` stays plain HTML/CSS/JS built from
  the existing `app.js` renderers, with all styling in `web/style.css`.
- The artifact links are private to Fred's claude.ai account.
