# Plan 09: Usage page Implementation Plan

> Related plans: [../PLAN.md](../PLAN.md) (master), [06-rework.md](06-rework.md) (the estimate from transcripts this builds on), [07-cells-drawer.md](07-cells-drawer.md) (the window and the spend breakdown it opens from), [08-cold-handoff.md](08-cold-handoff.md) (written in parallel; also edits `server.py`, `app.js`, `style.css`)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md) D13 and 7.5; the locked mockup [../design/rework/locked/usage.html](../design/rework/locked/usage.html) (its notes column holds the reasoning); [../CLAUDE.md](../CLAUDE.md)

**Goal:** A Usage page in the Cells Drawer window: estimated cost and tokens per day, week and month from every Claude Code transcript on this machine, a calendar of days, the picked day by project and model, and Days / Weeks / Months as columns of cells in $ or tokens. History outlives Claude Code's 30-day transcript cleanup.

**Architecture:** `console/usage.py` gains `History` (reads every `*.jsonl` under `~/.claude/projects` as it grows, one offset per file, each message id once; sums per local day: cost, four token kinds, cost per project, cost per model family), `weeks` and `months` (Monday-first weeks and calendar months from the day totals), and `load_days` / `merge_days` / `save_days` for `usage-days.json`. `server.Hub` runs the scan in its own thread (`cc-usage`, at start, then every 60 s), keeps the merged days and serves them at `GET /api/usage` (through `guard.py` like every request). `web/` gets a fourth page, `usage`, opened from a button in the spend breakdown.

**Tech Stack:** unchanged: Python 3.14 standard library, plain HTML/CSS/JS, `unittest`.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `master`). Start: 99 tests OK. Other chats edit `web/app.js`, `web/style.css`, `console/server.py` and the shared docs in parallel: anchored edits only, stage only this plan's lines.

---

## Fixed decisions (Fred, 2026-10-11)

1. **Its own page**, like Prep: a `Usage by day, week, month ›` button in the spend breakdown opens it; Back and Esc return to the list. Drawn first as a mockup, locked as `design/rework/locked/usage.html` (D13).
2. **Estimated cost and tokens**, at the `config.json` list prices (fast mode 2x), from the transcripts. Projects show for the picked day only. No per-project chart.
3. **Every transcript**: all of `~/.claude/projects/**/*.jsonl` (subagent files included), not only the shown sessions. Read only. Each message id counts once across files (forks copy their parent's lines). The day is the local date of the message's `timestamp`. A file's project is the folder name of the first `cwd` in it.
4. **History**: closed days (before today) go to `~/.claude/console/usage-days.json` (`{"days": {date: {...}}}`, written whole through a temp file). For a day in both the file and the transcripts, the larger cost wins (a deleted transcript lowers the scan; a late line raises it).
5. **Calendar tones in multiples of `daily_budget_usd`**: under 1x, under 3x, under 6x, 6x and more; no use = empty cell; before the first day with data = outlined; today ringed in orange.
6. **Tokens count all four kinds** (input, output, cache write, cache read); the picked day splits them.
7. **Columns of cells**: each column one day, week or month; each cell the smallest of 1, 2, 5, 10, 20, 25, 50, ... ($, or million tokens) that keeps the tallest column within 20 cells; a part-full top cell is half tone; the limit as an orange dashed line on Days in $ only. Days = last 30, Weeks = last 12 (Monday first), Months = last 12.
8. **Scan cost**: 308 files, 1.42 GB took 2.2 s warm on this machine; the scan runs in its own thread so the window never waits. `/api/usage` answers `ready: false` until the first scan ends.

## API

`GET /api/usage` ->

```json
{"ready": true, "today": "2026-10-11", "first": "2026-09-11", "limit": 15,
 "days": {"2026-10-10": {"cost": 247.96, "tokens": [7268, 2915724, 11785649, 566161688],
                         "projects": {"CONTENT MANAGER": 151.81}, "models": {"opus": 205.35}}},
 "weeks": [{"start": "2026-07-27", "cost": 0.0, "tokens": 0}],
 "months": [{"month": "2025-11", "cost": 0.0, "tokens": 0}]}
```

`weeks` and `months` hold 12 entries each, oldest first, the current week / month last.

## Code map

```text
console/usage.py   + message_tokens, day_of, History, weeks, months, load_days, merge_days, save_days
console/server.py  + Hub.history, Hub.read_history, the cc-usage thread, GET /api/usage
web/index.html     + section data-page="usage"
web/app.js         + usage page renderer (head, figures, calendar, picked day, columns, tooltip), the
                     breakdown button, Esc back
web/style.css      + usage page classes (mockup's, on the existing tokens)
tests/test_usage.py   + HistoryTest, AggregateTest, DaysFileTest
tests/test_server.py  + UsageEndpointTest
```

## TODO

- [x] Task 0: lock the mockup; D13, PLAN row 9, this plan
- [ ] Task 1: `usage.py` history, weeks, months, days file (tests first)
- [ ] Task 2: service: `cc-usage` thread, `/api/usage` (tests first)
- [ ] Task 3: the Usage page in the window
- [ ] Task 4: check in a browser against the real transcripts (Claude), then the native window (Fred)

### Task 1: history and aggregation in `usage.py`

- [ ] Tests in `tests/test_usage.py`: two days of messages (local timestamps) in two files and a subagent file, a fork copy, a `<synthetic>` line; `History.scan` sums cost, four token kinds, projects (from `cwd`) and models per day and counts each id once; a second scan reads only what grew; `weeks` gives 12 Monday-first buckets, oldest first, with sums; `months` gives 12 calendar months across a year boundary; `save_days` writes closed days only, `merge_days` keeps the larger cost. Run: they fail.
- [ ] Code, then `py -m unittest discover -s tests`: all pass. Commit `feat: usage history per day, week and month from every transcript`.

### Task 2: the service

- [ ] Test in `tests/test_server.py`: with `hub.user_home` on a temp folder holding a transcript, `/api/usage` answers `ready: false` before `hub.read_history()` and the days, weeks and months after; `usage-days.json` lands in the data folder with closed days only; a foreign Host is refused. Run: fails.
- [ ] Code (`Hub.read_history`, the thread in `Hub.start`, the route), then all tests. Commit `feat: /api/usage serves daily, weekly and monthly totals`.

### Task 3: the page

- [ ] `index.html` section, `app.js` renderer and events, `style.css` classes, as anchored edits. The page reads `/api/usage` when opened and every 60 s while shown. Commit only this task's hunks (`feat: Usage page in the window`).

### Task 4: checks

- [ ] Claude: the service on a spare port with `CC_CONSOLE_HOME` on a temp folder, the page in headless Edge at 400 and 340 px: calendar and columns filled from the real transcripts, Days / Weeks / Months, $ / tokens, month ‹ ›, a picked day, dark and light.
- [ ] Fred: `py -m console`, open the spend breakdown, `Usage by day, week, month ›`.
