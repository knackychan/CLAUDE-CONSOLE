# Task 7: Docs (PLAN.md, the plan texts the review found wrong, memory)

> Contract: [README.md](README.md) section 2 (decisions) and 4 (what each task changed in an earlier plan's contract).
> Depends on: Tasks 1 to 5 placed (Task 6's lines are added when Task 6 is placed). Docs only: no code, no test.
> Other chats edit `PLAN.md` and the plan folders in parallel: anchored edits only, stage only this task's lines.

**Files**
- Modify: `PLAN.md` (plans table row 27, Build order, History line)
- Modify: `plans/05-harnesses/README.md`, `plans/05-harnesses/03-opencode-cmd.md`, `plans/05-harnesses/04-runs-state.md`
- Modify: `plans/24-plan-and-replan/README.md`, `plans/24-plan-and-replan/03-service.md`
- Modify: `plans/23-handoff/03-facts.md`, `plans/23-handoff/06-window.md`, `plans/23-handoff/01-handoff-block.md`
- Modify: `plans/25-cells-board/02-board-shell.md`, `plans/25-cells-board/03-chain.md`, `plans/25-cells-board/08-live-check.md`
- Modify: `plans/18-fills/README.md`, `plans/26-models-page/README.md`
- Modify: this folder's README status line

Each edit below names the file, the line to find (grep for the quoted text) and what it becomes. Where a line is
appended, it is appended as a new bullet or sentence ending `(plan 27)`, so a reader sees where it came from.

## 7.1 `PLAN.md`

1. In the plans table, after the row starting `| 26 |`, insert:

```text
| 27 | [plans/27-review-fixes/](plans/27-review-fixes/README.md) (guided plan, 8 tasks) - fixes from the plan-by-plan review of PR #1 (2026-10-14): config.json writes under one lock, plan and replan edges, routing and fills edges, handoff and facts edges, the window, harness edges after the plan 5 live check | written 2026-10-14 |
```

2. In `## Build order (2026-10-14)`, after the table row starting `| 6 | [25 Cells Board]`, insert:

```text
| 7 | [27 Review fixes](plans/27-review-fixes/README.md) | fixes found by reading every plan against the placed code | all six placed; its Task 6 also needs plan 5's live check |
```

3. Append to `## History`:

```text
- 2026-10-14 - Plan 27 written (fixes from the plan-by-plan review of PR #1, `plans/27-review-fixes/review.md`: 12 bugs, 14 risks, 9 gaps, nits). Every code task was run in a scratch copy of the PR head `cf69a48`, tests first, and Tasks 1 to 6 were then applied together in order: 571 tests, only the four Linux baseline failures. Q1 and Q2 written for (a). No code changed on the PR.
```


4. When plan 27 is placed, change its table row's last cell to `code done <date> (Tasks 1-5, PR <n>), Task 6 after plan 5's live check` and add a History line in the style of the 2026-10-14 placement line.

## 7.2 Plan 5

1. `plans/05-harnesses/README.md`, decision row `| 12 | A pick whose harness went off |`: replace its third cell with:

```text
A task step whose pick names a harness that is off or not found when the step starts is balanced inside the pick's rank, with the route note `pick refused: <harness> is off -> balance` (plan 18 decision 10; Fred, Q1 (a) of plan 27, 2026-10-14). A plain Run Fred points at such a rung is refused (409), never moved
```

2. Same file, section 3.2b: after the sentence about a rung removed from models.json, append `The route note reads `model gone from models.json: <rung>`, and `Hub.reload_models` writes one console.log line per dropped entry (plan 27 Task 3).`

3. Same file, the line containing `all unpriced as `cost unknown``: append `On the Task page the words sit in the row's sub line, the Board and the inspector show them in place of the figure (plan 27 Task 5).`

4. `plans/05-harnesses/03-opencode-cmd.md`: both lines containing `TIERS = ("haiku",)` in the OpenCode block become `TIERS = ("haiku", "opus")` (decision 11: Kimi K3 and GLM 5.3 join think), as the tree has it.

5. `plans/05-harnesses/04-runs-state.md`, the drift guard containing `byte-for-byte`: append `Since plan 5 Task 4 every stream, Claude's too, ends with the `cc_exit` line; the Claude adapter's chat and summary skip it.`

6. When Task 6 is placed: same README, decision 8 (Stop): append `A harness without an interrupt that is still running 10 s after its final event is stopped by its adapter and ends as success (`runs.RESULT_GRACE_S`, plan 27 Task 6); on POSIX `kill_tree` kills the run's process group.`

## 7.3 Plan 24

1. `plans/24-plan-and-replan/README.md`, the fake table row `| `REPLAN` |`: the word is `REPLAN-ASK` (as `tests/fake_claude.py` has it); the same in the list line containing `and `REPLAN` (Confirm, Keep`.
2. `plans/24-plan-and-replan/03-service.md` and README line containing `runs a task `scout, design, code, test, verify``: append `After the split the steps read `scout, design, code, code, verify, test`: `plan.rebuild` places the verify right after the last edit kind (the tests follow the code; plan 27 review nit).`
3. Same README, section 3.10 (the step limit): append `Room is `tasks.room_after(task, n, cfg)`: `task_max_steps - n` less the done steps a redo keeps after n; a verify or fix is never counted, in `_ended` and `replan.check` alike (plan 27 Task 2).`
4. Same README, section 3.4 (what the design step writes): append `A `Replan:` line from the design step itself is refused (`replan refused: design step`); the design prompt asks for a search step before the design instead (plan 27 Task 2).`
5. Same README, D2's text containing `then dropped from config.json`: append `Placed by plan 27 Task 1 in `paths.ensure_config` at service start.`
6. Same README, 3.7 (Fred edits the plan): append `Only while the task is running or waiting (plan 27 Task 2); the Answer lever needs a plan.md.`

## 7.4 Plan 23

1. `plans/23-handoff/03-facts.md`, the line `+UNTRACKED_READ_MAX = 1024 * 1024 ...`: append below the code block `Plan 27 Task 4: `UNTRACKED_READ_MAX` is 256 KB and at most `UNTRACKED_MAX` (100) untracked files are read; both git calls carry `-c core.quotePath=false`.`
2. `plans/23-handoff/06-window.md`, the cut view (6.7 and the `headingBlock(wrote, cut, ...)` call): append `The "as sent" view also lists `meta.cut` struck under Findings, so a LONG cut shows `N kept · M cut` (plan 27 Task 4); `factsFold` opens red without `force`, so it can be closed.`
3. `plans/23-handoff/01-handoff-block.md`, 1.2 (`step_prompt.md`): append `As placed, an empty slot adds no blank line (`${plan}What the earlier steps left you:` and `${lessons}${part}Rules`, with `step_prompt` adding the "\n\n" only to a non-empty slot); same text otherwise.`
4. The guard "git_base is never sent to the window" (plan 23 Task 5): append `Nor `touched`, the full changed-path list the D5 check reads (plan 27 Task 4).`

## 7.5 Plan 25

1. `plans/25-cells-board/02-board-shell.md`, the line containing `!e.target.closest(".tabs")) return boardKey(e);`: append `Plan 27 Task 5 also skips a focused button or select inside the Board, so Enter presses it; and `showPage` leaving the Board (Ctrl+N, Ctrl+P, any page but a session opened from it) calls `board(false)`.`
2. `plans/25-cells-board/03-chain.md` line 25 (`| cost | `stepCost(s)`: `? cost` ...`) and the guard `cost unknown is `? cost``: the word is `cost unknown` (plan 5 README 3.6), never `0.00`; plan 27 Task 5.
3. `plans/25-cells-board/08-live-check.md` item 9: `? cost` becomes `cost unknown`.

## 7.6 Plans 18 and 26

1. `plans/18-fills/README.md`, decision 6: append `A verify whose pool is empty still holds when its own rung is over `budget_warn_at` (plan 27 Task 3).` Section 3.5 (usage-days.json): append `An unreadable file is never overwritten: it is copied once to `usage-days.json.bad` and the write is skipped (plan 27 Task 3).`
2. `plans/26-models-page/README.md`, 3.1 (Reload): append `A page key deleted from config.json returns to its default on Reload; a value `tuning.validate` refuses keeps the live value and writes a console.log line (plan 27 Task 1). A Save posts only the tiers that changed; hidden rows sit behind a show button with their own remove button (plan 27 Task 5).`

## 7.7 This folder and memory

1. In [README.md](README.md), change the Status line to `placed <date> on <branch>` when the code tasks are placed.
2. Project memory: update `pr1-plan-review` with the placement (branch, PR, test count) and what is still open.

## 7.8 Steps

1. Make the edits of 7.1 to 7.6 (7.2 item 6 only once Task 6 is placed).
2. `git diff --stat` shows only the files of the Files list.
3. Commit: `docs: plan 27 placed; earlier plan texts amended where the review found them wrong (plan 27 Task 7)`.

## 7.9 Drift guards

- No code file changes in this task.
- An earlier plan's text is amended by appending, never by deleting its history; decision rows are the one place a
  cell is replaced (7.2 item 1), because the decision itself changed.
