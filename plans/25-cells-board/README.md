# Plan 25: The Cells Board. Guided implementation plan

> Design: [../../design/brainstorm/2026-10-13-interface.md](../../design/brainstorm/2026-10-13-interface.md) sections
> 1 (rules, two zones, folds), 2 (widths, the Board button, `window.json` `board`, ID-4), 3 (the list header's Board
> button), 6.1 (chat turns), 7 (Task page head Board button, step rows with the ctx gauge), 8 (the Board), 10, 11, 12
> (ID-1, ID-3, ID-4, ID-5 refused, ID-8, ID-9); the review
> [../../design/brainstorm/2026-10-13-interface-review.md](../../design/brainstorm/2026-10-13-interface-review.md)
> (3.7 to 3.12, P1 to P3, 5 Risks); [../../design/brainstorm/2026-10-13-orchestration.md](../../design/brainstorm/2026-10-13-orchestration.md)
> section 7 (D-6) and 5.1 item 6 (measure). Mock (locked by Fred, 2026-10-13):
> [../../design/rework/locked/cells-board.html](../../design/rework/locked/cells-board.html), views `Step picked`, `Step
> running`, `Handoff picked`, `Task picked`, `Replan waits`, `Plan tab`, `Plan gap waits`, `Measure`, `Empty` (Board),
> `List` (header), `Task page` and `Codex session` (compact). Master: [../../PLAN.md](../../PLAN.md). Rules:
> [../../CLAUDE.md](../../CLAUDE.md).
>
> Build order (cross-plan contract, 2026-10-14): 5 -> 24 -> 23 -> 18 -> 26 -> **25**. This plan lands last. Its start
> state is plan 26 placed; it is written against today's code (plan 22 placed, 328 tests on Windows, 326 on Linux with
> 4 known environment failures) plus the contracts of plans 5 ([../05-harnesses/README.md](../05-harnesses/README.md)
> 3.1, 3.6, 3.7), 24 ([../24-plan-and-replan/README.md](../24-plan-and-replan/README.md) 3.2, 3.7), 23 (the shared
> names of the cross-plan contract: `brief_meta`, `facts`, `end_commit`, `GET /api/task` `facts` / `notes` / `briefs`,
> its window helpers `fold`, `handoffSections`, `headingBlock`, `.hchip`), 18 (rung text, `balance:` notes) and 26.
> Where a task edits a function an earlier plan also edits, its file says so in a "Lands on" line.

**Placed 2026-10-14** on branch `claude/implement-orchestration-plans-1y4bic` (PR #1): every code task, tests first where the task says, one commit per task; open decisions as (a). Fred's live check and the close task are open.

Status: written 2026-10-14. Task 1 (the service side) was run in a scratch copy of the working tree with its final
code and tests: `python3 -m unittest discover -s tests` ran 336 tests (the Linux baseline 326 plus 10 new), the only
failures the 4 known Linux environment ones (`test_tray` import, `test_redact ... test_path_tools_are_relative_to_cwd`,
`test_usage ... test_sums_each_local_day_once_per_message`, `test_window ... test_place_is_kept_only_while_on_a_screen`);
the 10 new tests all pass (5 in `tests/test_tasks.py`, 3 in `tests/test_server.py`, 2 in `tests/test_window.py`). Tasks 2 to 7 are browser code ported from the mock; they are guided here and checked by the
executor in headless Edge or Chromium. D1 to D4 are open: the plan is written for (a) on each.

## 1. Tasks, in order

| # | File | What it delivers | Depends on |
|---|---|---|---|
| 1 | [01-service.md](01-service.md) | `tasks.open_questions`, `tasks.read_chain`, `tasks.measure` (and their helpers), the step's `ctx_tokens` stored in `Hub._ended`, `GET /api/measure`, `GET /api/task` `questions` and `chain`, `/api/draft` and `/api/config` `board_tab` and `folds`, `WindowApi.board` and the Board size in `window.json`; tests | nothing |
| 2 | [02-board-shell.md](02-board-shell.md) | The `board` page in `web/index.html`, its CSS frame, `openBoard` / `closeBoard` (the window widens and returns), the two Board buttons (list header, Task page head), the picked task and pick state, the keyboard, the footer, the fold memory | 1 |
| 3 | [03-chain.md](03-chain.md) | The chain column: folded task rows, the task head, step blocks (finished, full, planned), connectors and their variants, the fix bracket, the replan block, the empty Board | 2 |
| 4 | [04-chat.md](04-chat.md) | The chat grammar (6.1) shared by the session page and the Board: `--me` / `--ai`, bubbles, the Prompt fold, the tool fold, the writing mark, the source line; the session page uses it | 2 |
| 5 | [05-step-inspector.md](05-step-inspector.md) | The step inspector: head, tabs Chat / Received / Handoff / Route / Plan, the Facts fold, the replan and Plan gap askboxes on the Board | 3, 4 |
| 6 | [06-handoff-task-measure.md](06-handoff-task-measure.md) | The handoff picked view (one column, struck cut lines, Checks fold), the task head inspector (Now line, open questions, prompt.md, chain log), the Measure table | 3 |
| 7 | [07-task-page.md](07-task-page.md) | The compact Task page: the Board button in the head, two-line finished rows, the ctx gauge line on the current, failed and past-150K rows | 2 |
| 8 | [08-live-check.md](08-live-check.md) | Fred's live check | 7 |
| 9 | [09-close.md](09-close.md) | PLAN.md, the interface doc, this folder's state | 8 |

Task 1 is Python, tests first, its own commit. Tasks 2 to 7 are browser code: anchored edits to `web/app.js`,
`web/style.css` (tokens first) and `web/index.html`, `node --check web/app.js`, the full suite, and a headless check at
900 px (the Board) and at 400 and 340 px (the pages a task touches). Task 8 is Fred's: Claude never starts a run.
Other chats may edit `web/app.js`, `PLAN.md` and the design docs: anchored edits only, stage only this plan's lines.

## 2. Decisions

Taken by the design (not reopened): the Board is a page of the same window, widened by a button to the saved size
(ID-4, 900 x 680 first); two columns, chain 300 px and inspector; Chat first in the step inspector; Received / Handoff
(ID-9); no cells for a handoff's words, figures only (ID-5 refused); a cut is the ink words `cut 122 w` (ID-1); an
unknown context is the word `unknown`, never a zero and never an estimate (ID-3, D-3); `--me` and `--ai` for the chat
only (ID-8); folds with a closed line, a FAIL opens its fold by itself, folds remembered per window (section 1); the
source line at the end of the chat (the locked mock and review 3.8 win over the "on top" of 6.1); no DAG, no
terminals, no drag on the Board.

Open (the docs do not settle them). Recommended option first; the plan is written for it; the lines that change
otherwise carry a `D1` ... `D4` mark in the task files.

| # | Question | Options | Plan written for |
|---|---|---|---|
| D1 | How the fix insert's steps are numbered on the Board, the Task page and the counts. The mock says `5b fix`, `5c verify`, `step 5c of 8`; the service numbers them 6 and 7 and renumbers the later steps (`tasks._insert_fix`), and the folder, the chain log and the session pager use those numbers. | (a) the service's numbers everywhere (`06 fix`, `07 verify`, `step 7 of 8`); the bracket alone shows the insert; (b) the mock's labels (`5b`, `5c`) by a window-side `stepLabel`, with the later steps shown one lower than their file names | (a) |
| D2 | When an open question counts as closed (the task head's `n closed`). The briefs carry Open questions; nothing marks an answer. | (a) closed at the first later brief that no longer carries it (whitespace and case do not count), still open while the last brief carries it; (b) only a step's Findings line that quotes it closes it | (a) |
| D3 | Which kind the measure table's reading names (`fix at 112K from 240 words in is the one to tune`). | (a) the kind with the most context per received word, among kinds with both medians; (b) the kind with the largest context median | (a) |
| D4 | When the muted `△ scout first` hint shows on a step (design 7 and 8.2 show it; no plan gives it data). | (a) a step whose received handoff is under `HINT_IN_W` 300 words and whose context reached `HINT_CTX` 100K or more (figures in its title); (b) no hint until a plan feeds `delegate_after_reads` per step | (a) |

## 3. The contract

### 3.1 Files

```
console/tasks.py        open_questions, read_chain, measure, section_items, question_key, note_words, same_dir (Task 1)
console/server.py       Hub._ended stores ctx_tokens; GET /api/measure; GET /api/task questions, chain;
                        /api/draft and /api/config board_tab, folds (Task 1)
console/window.py       BOARD_W, BOARD_H, BOARD_MIN_W, clamp_board, WindowApi.board, board_size (Task 1)
web/index.html          <section data-page="board"> (Task 2)
web/app.js              the Board page, the chat grammar, the Task page's Board button and gauge line (Tasks 2 to 7)
web/style.css           --me, --ai, the Board rules, the chat rules (Tasks 2 to 7)
~/.claude/console/window.json   board: [w, h], board_tab, folds (written through WindowApi.board and /api/draft)
```

Nothing else is written. The service writes the task folders as before; this plan adds one key per step
(`ctx_tokens`) and reads the rest.

### 3.2 Data (what the Board reads; nothing here is new but `ctx_tokens`, `questions`, `chain` and the measure)

- `snap.tasks[]` (`task_row`, unchanged by this plan): id, title, project, project_dir, state, owner, current, count,
  why, asks, updated, effort, cost, steps (n, kind, state, model, effort, session, verdict, cost, note, attempts); plan
  23 adds `end_commit`, `brief_meta`, `facts`; plan 24 adds `plan`, `part`, `hard`; plan 5 `harness`.
- `GET /api/task?id=` for the picked task (one request per row change, as the Task page does): `task` (task.json whole:
  every step with `goal`, `notes` (route notes), `attempts`, `start_commit`, `started`, `ended`, `verdict_detail`,
  `ctx_tokens`, `brief_meta`, `facts`, `part`, `harness`), `levers`, `step_levers`, `note`, `brief`, `handoff`, plan
  23's `facts` / `notes` / `briefs` (`{"<n>": text}`), plan 24's `plan`, `parts`, `replan_note`, and this plan's:
  - `questions`: `[{"q": str, "opened": n, "closed": n or 0}]` (`tasks.open_questions(task, briefs)`, D2 a).
  - `chain`: the last 200 lines of chain.jsonl, `[{"ts", "step", "from", "to", "why", "session"}]` oldest first.
- A step's `ctx_tokens`: the session row's `ctx_tokens` when the step's run ended (also set when it stopped on a
  question); `None` when the row had none (a non-Claude harness, plan 5 3.6) or a step from before this plan (key
  absent: read with `.get`). A running step's context is the live session row's (`snap.sessions`).
- `GET /api/measure?project=<project folder>&n=10` -> `{"project", "tasks": int, "kinds": [{"kind", "steps",
  "received", "context", "handoff"}], "hot": kind or ""}`; medians rounded to int, `None` when no value. 400 `bad
  measure query` without a project, with one over 1000 characters, or with an `n` that is not digits; `n` held to 1
  .. `MEASURE_MAX` 50.
- `GET /api/chat?session=` unchanged (the Chat tab).
- `/api/config` gains `board_tab` (default `"chat"`) and `folds` (default `{}`) from window.json; `POST /api/draft`
  takes `board_tab` (one of `chat`, `recv`, `hand`, `route`, `plan`) and `folds` (`{key: bool}`, at most 64 keys
  matching `[a-z][a-z0-9.]{0,39}`); 400 `bad board_tab` / `bad folds` otherwise.

### 3.3 The window API (`console/window.py`)

- `WindowApi.board(on) -> [w, h] | None`: on: the open window takes `window.json` `board` (clamped by
  `clamp_board`: width 700 .. 900, height 420 .. 1600; `[900, 680]` when absent); off: the compact `size` again. None
  when the form is the pill. `_board` is never written: a new window process starts compact.
- `resize(w, h, keep)` while the Board is open clamps with `clamp_board` and keeps `board`, never `size`.
- `form("open")` while the Board is open keeps the Board's size (a `fit` after a text-size change); `form("pill")`
  leaves the Board (`_board = False`).

### 3.4 Window names (pinned; Tasks 2 to 7 use exactly these)

State in `web/app.js`: `boardFrom` (`{page, id}` the page the Board opened from, or null), `boardTask` (the picked
task id, `""` none), `boardPick` (`""` nothing, `"t"` the task head, `"s<n>"` a step, `"c<n>"` the connector after step
n), `itab` (`"chat"`, `"recv"`, `"hand"`, `"route"`, `"plan"`; window.json `board_tab`), `boardData` (`{id, sig, data}`,
`GET /api/task` of `boardTask`), `boardChat` (`{sid, at, chat}`), `measureData` (`{project, at, data}`), `foldState`
(window.json `folds`), `toolOpen` (a `Set` of `"<session>:<k>"`, not kept).

Functions: `openBoard(id)`, `closeBoard()`, `renderBoard()`, `boardTasks()`, `boardProject()`, `boardItems(t)`,
`boardKey(e)`, `taskRowSig(row)`, `chainHtml(row, d, picked)`, `stepBlock(t, s, d, row)`, `connBlock(t, s, d)`,
`stepShown(t, s, row)`, `stepCtx(s)`, `ctxMiniHtml(s)`, `ctxRowHtml(s, live)`, `stepCost(s)`, `rungTime(s)`,
`triesHtml(s)`, `scoutHint(t, s, d)`, `inspStep(t, s, d, row)`, `recvPane(t, s, d)`, `handPane(t, s, d)`,
`routePane(s)`, `planPane(t, d, s)`, `factsFold(s, text)` (replaces plan 23's `factsFold(f, text)`), `inspReplan(t, s, d)`, `inspGap(t, s, d)`,
`inspConn(t, s, d)`, `checksFold(meta)`, `inspTask(t, d, row)`, `inspMeasure(m, name)`, `chatPane(chat, sid, source,
o)`, `toolsRow(list, key)`, `promptRow(text, o, key)`, `handoffSplit(text)`, `foldOpen(key, dflt)`, `saveFolds()`,
`stepGauge(t, s)`; helpers named in their task files: `emptyBoard`, `boardInspector`, `boardWrapKey` (Task 2), `stepOf`
(Task 4), `planOpenHtml` (Task 5, split from plan 24's Plan row), `grown` (Task 7). Constants: `AGENT_NAME`, `BWORD`, `HINT_IN_W = 300`, `HINT_CTX = 100000` (D4), `BOARD_KEYS`.
Reused from plan 23 Task 6: `fold`, `handoffSections`, `headingBlock`, `.hchip`; from plan 24 Task 4: `planSections`,
the Plan row renderer, `taskAct` cases `gapanswer`, `redo`, `keep`, `confirm`; from plan 5 Task 6: `modelText` for
rungs.

### 3.5 Words on screen (pinned strings)

| Where | Text |
|---|---|
| List header button | `⇔ Board` (title `Open the Board: the window widens to 900 px`); lit (`.on`) when the window is 700 px or wider |
| Task page head button | `⇔ Board` (title `The chain as connected cells, with the handoffs between the steps: the window widens (Esc returns)`) |
| Crumb | `Board / <project name or All projects> · N tasks` |
| Footer keys | `↑ ↓ step · ← → task · Enter chat · Esc back`; `?` title `A step's context in cells of 10K; the chip between two steps is the handoff the next one received, its words in the inspector` |
| Empty | `No task in <scope>. Type a task in the list; its steps show here as they run.` |
| Connector chips | `handoff`; `handoff · cut N w`; `handoff · plan`; `as written · not compacted`; `writing`; none (dotted) |
| Unknown context | `ctx unknown` (finished block), `unknown` (full block), title `<harness> reports a turn's spend, not a context size` (non-Claude) or `no context reading for this step` |
| Received tab | `Received N w`; head `From NN · N w · compacted` (or `· as written`); step 1 `No handoff: step 1 gets the task goal and Prep's context pack.` |
| Handoff tab | `Handoff R w` or `Handoff R → S w`; head `For NN · wrote R w · NN received S w`; running `Writing. Shows here when the run ends.`; planned `Not started.` |
| Facts fold | `Facts · F files +P · <tests or "no test run">`; FAIL in red and open |
| Checks fold | `Checks · K of N pass · compacted by <by> · $0.004 · T turns`; a failure `1 FAIL: <name>` in red, open |
| Measure head | `Measure · <project> · last N tasks`; meta `median per kind`; legend `median`, `context past 150K` (only when a bar is orange), `cell 10K · words as figures` |
| Measure reading | `A kind that receives a small handoff and reaches a large context reads too much on its own: <kind> at <K>K from <W> words in is the one to tune (scout first, or a turn cap).` |
| Hint | `△ scout first`, title `<W> w in, <K>K reached` (D4) |

### 3.6 Hard rules (never relaxed by a task)

- Orange only for what needs Fred: a waiting task's why, the replan and Plan gap askboxes, an over-pace figure, an
  open question's `?`. A cut, a fallback, a hint, a balance note are never orange.
- A handoff's words are figures, never cells (ID-5). Context is cells of 10K (30 to the red threshold), 15 on a
  finished block; unknown is a word.
- `--me` and `--ai` colour the chat bubbles and their labels only.
- The window writes nothing but through the existing routes; the Board adds only `GET /api/measure`.
- Stop on the Board is the task lever `POST /api/task/stop` (the run's interrupt), never a kill.
- Nothing scrolls sideways at 900, 400 or 340 px. No emojis or em-dashes in any string.
- One Doto figure per screen: the Board has none (the mock's chain cost is mono); the compact pages keep theirs.

### 3.7 Drift guards for the executor

- `GET /api/task` stays one request per task row change (`taskRowSig`); the Board never fetches a note, a brief or a
  facts file on its own.
- Steps are read with `.get` for every key a plan after plan 17 added (`ctx_tokens`, `brief_meta`, `facts`,
  `end_commit`, `part`, `hard`, `harness`); a task.json from plan 22 renders: no cut words, and `ctx unknown`
  where the `ctx_tokens` key is absent.
- The chat grammar is one `chatPane`; the session page and the Board call it with different options, never a copy.
- `fold`, `handoffSections` and `headingBlock` are plan 23's; this plan extends `fold` with `o.key` and `o.force`
  (02-board-shell.md) and `headingBlock`'s existing `whole` flag and fold keys (06-handoff-task-measure.md), and adds
  no second parser.
- The Board is a page, never a second window: `showPage("board")`, `data-page="board"`.

## 4. Verification at the end of every task

- `py -m unittest discover -s tests` all OK (on Fred's Windows: the plan 26 count plus 10 after Task 1); the count in
  the commit message.
- Task 1: the new tests fail before the code and pass after it (run in a scratch copy for this plan: see Status).
- Tasks 2 to 7: `node --check web/app.js`; the service with the fake claude on a `CC_CONSOLE_HOME` temp folder
  (`py -m console --serve`), a task `CHAIN fix add` with `HANDOFF-OK` run to done and one with `VERDICT-FAIL` run to its
  fix (the fake's words, plan 17 Task 4), opened in headless Edge or Chromium at 900 x 680 (Board) and 400 x 760 / 340
  x 760 (list, Task page, session page): the checks each task lists, no console error, no horizontal overflow
  (`document.documentElement.scrollWidth <= innerWidth` and the same for `.bchain`, `.binsp`).
- Task 8: Fred's live run (08-live-check.md).
