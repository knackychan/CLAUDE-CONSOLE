# Plan 27: Fixes from the plan-by-plan review of PR #1. Guided implementation plan

> Findings: [review.md](review.md), the review of 2026-10-14 (PR #1 head `cf69a48`, plans 5, 24, 23, 18, 26 and 25
> read task by task against the tree): 12 bugs (B1 to B12), 14 risks (K1 to K14), 9 gaps against the plan text
> (G1 to G9) and nits. Every finding has a task below; none is left open except where section 5 says so.
> Contracts this plan changes: the six plan folders above, at the lines Task 7 names. Master: [../../PLAN.md](../../PLAN.md).
> Rules: [../../CLAUDE.md](../../CLAUDE.md).
>
> Start state: plans 5, 24, 23, 18, 26 and 25 placed (PR #1, branch `claude/implement-orchestration-plans-1y4bic`,
> head `cf69a48` or later). Where the head has moved, anchor by the quoted lines, never by line numbers.

Status: written 2026-10-14, not placed. Every code task (1 to 6) was written tests first in its own scratch copy of
`cf69a48`: each new test was run and seen failing for the reason in the review (the task files quote the messages),
then the fix, then the whole suite. Then the six patches were applied together in order 1, 2, 3, 4, 5, 6 on one more
copy of `cf69a48` with no conflict: **570 tests, only the four Linux baseline failures** (test_tray import,
test_redact Windows path, test_usage local day, test_window placement); `node --check web/app.js` OK. The window
tasks were checked in headless Chromium (Task 4 at 400 and 340 px; Task 5 at 900, 400 and 340 px, 50 checks, no
console errors). One more Task 2 fix was then added on the combined copy (2.5.4b, the replan pass restarted after a
service restart, which the first pass of Task 2 left open): its test failed first, then `TaskServerTest` 93 OK, so the
whole plan is 571 tests. The final code is in the task files; every added line of the task files' code blocks was
found in the combined copy.

## 1. Tasks, in order

| # | File | What it delivers | Findings | Tests added |
|---|---|---|---|---|
| 1 | [01-config-writes.md](01-config-writes.md) | `paths.CONFIG_LOCK` and one `_rewrite_config` for every config.json writer (a temp file per write), OSError answered 500 by the config POST handlers, `tuning._number` never raises, `Hub.reload_tuning` resets a deleted key and refuses a bad value, `opus_max_turns` dropped at service start | K1, K2, B7, G8 | 7 |
| 2 | [02-plan-replan.md](02-plan-replan.md) | `tasks.room_after` (one room rule), `replan.check` keeps a done edit step's verify, `plan.drop_parts`, `design_input` on a redo, masked one-line answers, `Hub._base`, the design step's `Replan:` refused, Answer needs a plan, Redo waits for the brief, the project checked before the replan and brief passes, `edit_plan` only while running or waiting | B1 to B5, K12 to K14, G1, plan 24 nits | 13 |
| 3 | [03-routing-fills.md](03-routing-fills.md) | `step_route` holds an empty-pool verify and notes an unknown pick, `peak_add` never raises, models.json reread before the route, usage-days.json never overwritten when unreadable, `add_other` returns what it wrote under `Hub._count_lock`, `count_run` cannot break `poll_once`, `model gone from models.json`, `_ladder_from` keeps known tiers, dropped entries logged | B10 to B12, K7 to K9, G5, plan 18 nit | 12 |
| 4 | [04-handoff-facts.md](04-handoff-facts.md) | a refused auto handoff still escalates and is retried once per turn end, `git_snapshot` with `core.quotePath=false` and lower caps, `/api/task` without `git_base` and `touched`, the full changed-path list in `s["touched"]`, lessons read before the kind filter, the "as sent" view shows cut findings, `factsFold` can be closed | K3 to K6, G2, plan 23 nits | 6 |
| 5 | [05-window.md](05-window.md) | Models page posts only changed tiers and can remove a hidden rung, allowance rows checked, `/api/measure` refuses a non-ASCII digit, the Board left cleanly on Ctrl+N / Ctrl+P, Enter on inspector buttons, the six pinned plan fold keys, `cost unknown`, `.chain .row.short`, plan 25 and 26 nits | B6, B8, B9, G3, G4, G7, G9, plan 25 and 26 nits | 2 (and the 50-check headless script) |
| 6 | [06-harness-edges.md](06-harness-edges.md) | a 10 s grace stop after the final event for harnesses without an interrupt (ends as success), Codex with `cwd=` and a bare effort value, `kill_tree` on POSIX by process group, one STOP footer rule, cmd tokens like Codex, `harnesses()["claude"]["models"]` `{}` | K10, K11, kill_tree gap, plan 5 nits, cmd cached tokens | 6 |
| 7 | [07-docs.md](07-docs.md) | PLAN.md row, Build order and History; the earlier plan texts the review found wrong or that this plan changes | G6 (with Q1), doc nits | none |
| 8 | [08-live-check.md](08-live-check.md) | Fred's live check on Windows | | none |

Order: 1, 2, 3, 4, 5 (Python tests first, one commit each), 7, then 8. **Task 6 waits for Fred's plan 5 live check**
(Q2 (a)): its "Before you start" section lists the five observations it depends on and the lines each one changes;
it then lands with its own commit and Task 7 item 7.2.6. Tasks 1 to 5 touch disjoint functions; where two tasks
touch the same function (Task 3 and Task 4 each change one different line of `Hub.start_step`; Task 1 and Task 3
different functions of `console/paths.py`) the task files say so in their "Lands on" lines.

Commits: `plan 27 task N: <what> (<findings>)`, with the full suite's count at the end, `(<n> tests OK)`.

## 2. Decisions

Taken here (each task file marks its own with `Decision:` at the place it applies; none changes a design decision of
an earlier plan except Q1):

| # | Decision | Task |
|---|---|---|
| 1 | `opus_max_turns` is copied to `design_max_turns` (when unset) and removed from config.json in `paths.ensure_config` at service start; `load_config` stays read-only | 1 |
| 2 | A value `tuning.validate` refuses on Reload keeps the live value (not the default) and writes a console.log line | 1 |
| 3 | A replan answer keeps a verify only when an unfinished verify sat in the replaced tail; it goes last | 2 |
| 4 | After a redo, `plan/` is removed before every save; a former part step's goal becomes the part title | 2 |
| 5 | Redo waits for the brief through the lever (`brief still writing`); `_brief_done` is unchanged | 2 |
| 6 | The brief pass in a folder taken off the list writes the code fallback brief; the replan pass makes the task stuck | 2 |
| 7 | An unknown pick's note uses the gate's reason first (`model gone from models.json: <rung>`), else `unknown model` | 3 |
| 8 | `model gone from models.json` covers the other harnesses only; `/api/run` with such a rung answers 409 (was 400) | 3 |
| 9 | `count_run` holds `Hub._count_lock` (order `_count_lock`, `FILE_LOCK`, `self.lock`) | 3 |
| 10 | An unreadable usage-days.json is copied once to `usage-days.json.bad`; a JSON value that is not an object counts as unreadable | 3 |
| 11 | The git snapshot stays inside `tlock` (it cannot move out cleanly); the lower caps bound it (worst case 25 MB, was 500 MB) | 4 |
| 12 | The full changed-path list lives in `s["touched"]`, kept in the service like `git_base` | 4 |
| 13 | Hidden tier rows sit behind a `show` / `hide` button on the `N hidden` line, each with a remove button | 5 |
| 14 | On the Task page `cost unknown` goes in the row's sub line (the 38 px cost column cannot hold it at 340 px) | 5 |
| 15 | `planPane`'s Edit shows exactly when plan 25 5.6 says; the service's 409 still guards | 5 |
| 16 | A run stopped after the grace records exit 0, the OS exit code kept in `cc_exit` as `after_result` | 6 |
| 17 | Codex always runs with `cwd=` and a bare effort value, on both `codex.exe` and the `codex.cmd` shim | 6 |
| 18 | No harness adds the STOP footer to a prompt that starts with `/` | 6 |

Open for Fred (written for (a); a different answer changes only the lines named):

| # | Question | Options | Written for |
|---|---|---|---|
| Q1 | A pick whose harness is off when the step starts (review G6) | (a) keep plan 18's behaviour: balance inside the pick's rank, note `pick refused: <harness> is off -> balance`; plan 5 decision 12 amended (Task 7, 7.2 item 1); (b) restore decision 12: run Claude's rung of the same tier (a code change in `tasks.step_route`'s refused-pick branch: the pool becomes the tier's Claude rungs) | (a) |
| Q2 | When Task 6 lands | (a) after Fred's plan 5 live check, on what it shows; (b) now, on the expected behaviour (the fakes) | (a) |

## 3. Behaviour that changes for Fred

- Two saves at the same moment (Models page, harness switch, a setting) both land; a write that fails answers with
  the reason instead of dropping the connection.
- Reload on the Models page shows a key deleted from config.json at its default.
- A design step can no longer ask for a replan of itself; it asks for a search step before the design instead.
- `/api/run` on a codex model removed from models.json answers 409 `model gone from models.json` (was 400).
- After Task 6: an OpenCode or cmd step whose CLI lingers after its last line ends as success about 10 s later.
- Unchanged and worth knowing (plan 18 D2 (a)): with `allowances` empty, routing follows tier order and there is no
  spread until allowances are set on the Models page.

## 4. What each task changes in an earlier plan's contract

Task 7 writes these into the earlier plans; listed here so an executor sees them before starting:

- Plan 5: decision 12 (Q1), 3.2b's note text, 3.6's `cost unknown` placement, decision 8 (Task 6's grace stop),
  the opencode TIERS block, the `cc_exit` drift guard.
- Plan 24: 3.4 (no `Replan:` from the design step), 3.7 (edits only while running or waiting), 3.10 (room rule),
  D2 (where `opus_max_turns` is dropped), the fake word `REPLAN-ASK`, the step order after a split.
- Plan 23: Task 3's caps and `quotePath`, Task 5's guard (no `touched` either), Task 6's cut view and `factsFold`,
  1.2's blank lines.
- Plan 25: 2.8's key guard and leaving the Board, 03-chain's `cost unknown` wording, live check item 9.
- Plans 18 and 26: decision 6 (empty-pool verify holds), 3.5 (unreadable usage-days.json), 3.1 (Reload resets,
  per-tier Save).

## 5. Not in this plan

- Paths containing a tab, newline or double quote are still quoted by git with `quotePath` off (outside K5).
- Older inline styles in `web/app.js` from plans 17 to 24 stay (only the one the review named moves).
- If cmdc does not exit on its own and its result reports an error, Task 6's grace path records success; Task 6's
  "Before you start" says how to adjust `cmd.summary` if the fixture shows an error field.
- The process nit (plan 18 commit subjects without the test count) is history and stays.
