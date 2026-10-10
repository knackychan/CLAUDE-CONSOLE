# Visual rework (2026-10-10)

Target for the rework sub-plan (PLAN.md row 6). Decision and summary: BRAINSTORM D11 and section 7.5.
Every session, figure and cost in these mockups is sample data. Open a file in a browser to click
through its views; each page has the window mock on the left and its reasoning on the right.

## Locked

| File | Artifact | What it is |
|---|---|---|
| [locked/console-cells.html](locked/console-cells.html) | https://claude.ai/artifact/9s2oCibRMRPYqdRC8ZAt5d | Console Cells: Rings and Pill redrawn from `../references/` in a cell-grid language, refined with the anti-slop filter. Views: pill, peek, focus, asks you, overview, empty / offline / loading / error |

## Explored (not targets)

| File | Artifact | Outcome |
|---|---|---|
| [explored/a-pill-and-drawer.html](explored/a-pill-and-drawer.html) | https://claude.ai/artifact/Ac61ay92bKkBbKVfLNCpxz | A: kept the folding pill and the answer-in-place peek card |
| [explored/b-triage-board.html](explored/b-triage-board.html) | https://claude.ai/artifact/TLUve8h6ZWkS6sSDoc1Nn3 | B: not chosen; the sparkline idea became the activity cells |
| [explored/c-rail-and-focus.html](explored/c-rail-and-focus.html) | https://claude.ai/artifact/9x9mZUKL84WztY2xpRS9b4 | C: kept the session rail, focus pane, burn rate and agent lanes |
| [explored/d-cells-drawer.html](explored/d-cells-drawer.html) | https://claude.ai/artifact/SqX2KpJqpnV6Q7FA7zhVzn | D: proposal under review. Console Cells without the rail: A's list as home, C's focus content on a full-width session page, a searchable project picker in the header |
| [explored/ca-rings-and-pill.html](explored/ca-rings-and-pill.html) | https://claude.ai/artifact/5jcCWoKfExdC7ncBJjvgCL | C + A merge; Console Cells is its alternate. Written before the anti-slop pass (has an eyebrow label, no sample-data note) |

## Notes for the build

- The mockups load JetBrains Mono and Doto from Google Fonts only so they render anywhere. The app
  makes no network calls: Doto ships as a local woff2 in `web/`, and the figures use Cascadia Mono.
- The mockups are design references, not code to copy: `web/` stays plain HTML/CSS/JS built from
  the existing `app.js` renderers, with all styling in `web/style.css`.
- The artifact links are private to Fred's claude.ai account.
