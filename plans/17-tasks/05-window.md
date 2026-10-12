# Task 5: The window: effort slider, Run as task, task card, Task page

> Contract: [README.md](README.md) 3.9 (no restructuring of `app.js`), the design's 4.7 and 4.9, the locked
> mockups `design/rework/locked/cells-drawer.html` (layout, cell motif) and `console-cells.html` (tokens).
> Depends on Task 4. Other chats edit `web/app.js` and `web/style.css`: anchored edits only.

**Files**
- Modify: `web/index.html` (the slider under the compose box; a `data-page="task"` section)
- Modify: `web/app.js` (functions listed below, each placed next to its nearest neighbour)
- Modify: `web/style.css` (tokens first; the new selectors listed below)
- `tests/test_window.py` unchanged (no Python here); the check is headless Edge

## 5.1 Effort slider (compose row)

- `index.html`: inside `.compose`, after `#files-compose`, `<div id="effort" class="effort" role="radiogroup"
  aria-label="Effort"></div>`.
- `app.js`: `let effortPick = "auto";` next to `project`; set from `cfg.effort` at start.
  `renderEffort()` (called from `renderCompose`): six buttons `data-eff="auto|low|medium|high|xhigh|max"`,
  `role="radio"`, `aria-checked`, each `<i class="cells">` of one cell lit for the picked level and the ones below
  it (Auto: none lit, label `Auto`), label text in `.m`. Hint text on the right: `Auto: the rules pick per step` or
  `max on every step`. Click sets `effortPick`, `saveDraft()` (which now sends `effort: effortPick`), redraws.
  Alt+ArrowUp / Alt+ArrowDown in the `keydown` handler step through the six values when the compose box or the
  slider has focus.
- `doRun` and `rawRun`: when `effortPick !== "auto"`, the effort sent is `effortPick` (the card's `#p-effort` select
  is pre-set to it in `showPrep`).
- `style.css`: `.effort { display:flex; gap:6px; align-items:center; }`, `.effort button { ... border:0;
  background:transparent; color: var(--mut); }`, `.effort button[aria-checked="true"] { color: var(--ink); }`,
  `.effort .cells { grid-template-columns: repeat(5, 5px); }` (five cells, one per level; Auto shows them unlit).

## 5.2 Run as task (Prep page)

- `showPrep`: after the Route block, when `card.steps.length >= 2`: a block `<span class="lbl">Steps</span>` and
  `<div id="p-steps">` with one row per step: the index, a `<select data-skind>` of `cfg.kinds` (new in
  `/api/config`: `tasks.PREP_KINDS`; `verify` rows are fixed text), an `<input data-sgoal>` with the goal, a
  `<select data-smodel>` with `auto` and `cfg.models` (the Fable confirm note shows when `fable` is picked:
  `Fable may bill usage credits on this plan; the task will ask once`), a remove button; a `+ step` button adds
  a row (kind `code`, empty goal). Under it the effort line: `effort: auto (the rules pick per step)` or `effort:
  max on every step`. The Prep page's `pbar` gains `<button class="btn go" data-pact="task">Run as task</button>`
  before Run when the list has 2 or more rows (Run stays one session).
- `prepAct("task")`: reads the rows into `[{kind, goal, model}]`, drops empty goals, `POST /api/task {prep:
  c.id, prompt: $("p-prompt").value.trim(), steps, effort: effortPick}`; on 200 `card = null`, `openTask(r.task)`;
  on error `$("p-msg")`.
- Rows read into the request as the page shows them: the order on the page is the order of the chain.

## 5.3 Task card (list page)

- `taskGroup(t)`: `waiting` and `stuck` -> `needs`; `running` and `planned` -> `work`; `done`, `stopped` ->
  `done`.
- `renderListPage`: tasks of the scope (`snap.tasks.filter(inScope)`) are drawn at the top of their group,
  before the session cards, with `taskCard(t)`: `<div class="card task" data-task="<id>">`: line 1 the state
  glyph and word (`▶ Task`, `? Waiting`, `× Stuck`, `✓ Done`, `‖ Stopped`), the title, the age; line 2 the
  project, `step 2 / 4 · code · sonnet medium`, the cost; a third line with `why` when set, and for `waiting` on a
  question the answer box of the step session (reuse `cardHtml`'s STOP branch by giving it the step session row:
  the session card of the step stays in the list too, so the task card shows only `why` and `Open`).
- Session cards of a step: `cardHtml` and `quietHtml` add `<span class="tag">step 2/4</span>` after the title
  when `s.task` is set.
- Click on a task card: `openTask(id)`.

## 5.4 Task page

- `index.html`: a `<section data-page="task" hidden>` with the same `.top` bar (Back, crumb `Task`), a
  `<div id="tscroll" class="scroll stack">`, and `<div id="tbar" class="levers">`.
- `let taskId = null; let taskData = null;` next to `openId`. `openTask(id)`: `taskId = id; showPage("task")`;
  `renderTaskPage()` (called from `render()` when `page === "task"`): `GET /api/task?id=` once per snapshot
  version (`taskSig` like `leversSig`), then draws:
  - head: state glyph and word, the title, the project, `effort: auto | max`, the folder path in `.m`;
  - the chain: one row per step: a cell row (`.cells` of 6) in the state tone (`f` running with `live` on the
    first cell, `g` done, `r` failed, empty planned), `NN kind`, `model effort`, the verdict, the cost, and
    `Open` (`data-open=<session>`) when the step has a session; the current step's row is bold;
  - the last brief (`brief` from `/api/task`, the raw note as `note`) in a `<pre class="text">` block under
    `<span class="lbl">Brief for the next step</span>` with a `Show raw note` toggle (`data-tact="raw"`, page-only);
    a `briefing` task shows the loading cells and `Haiku is compacting the note` in that block;
  - `why` as an `.askbox` when the task is `waiting` or `stuck` (with the step session's STOP answer box when
    it is a question: a `textarea#answer` and `data-act="answer"` work as on the session page once `openId` is
    the step session; simpler: a button `Answer on the session page` that opens that session);
  - `tbar`: `Stop` (armed, two clicks, as the session page's Stop), `Pause` / `Resume`, `Retry`, `Confirm Fable`
    when `levers.confirm === ""`, `Clear` (armed, two clicks: `Delete its notes and streams? Click again`) when
    `levers.clear === ""`, each drawn only when its lever is `""`; the off reasons in a `.say` line. A cleared task
    shows `cleared: notes and streams removed` under the chain and no Open on its steps.
- `taskAct(name, button)`: `POST /api/task/<name> {task: taskId}`; errors to `#t-msg`.
- Esc on the task page: back to the list. The session page's head shows `task · step 2/4` as a link
  (`data-task=<id>`) when `s.task` is set.

## 5.5 Rungs and storage

- `modelText(model, effort)`: when the model is a full name with a version (`claude-opus-4-6`), show `opus 4.6`
  (`alias` unchanged for the family; a small `version()` helper next to it). The card's model selects (`#p-model`,
  the step rows) list the ladder from `cfg.ladder`, tier by tier, newest first, so a rung can be picked by hand.
- The Usage page's foot gets the storage line from `usage.storage`: `data folder 213 MB: runs 180, events 21,
  tasks 2, preps 1, other 9` in `.m`, orange (`.y`) over `usage.storage_warn_mb`.

## 5.6 Events

The document click handler's selector gains `[data-task],[data-eff],[data-tact]`; `data-task` -> `openTask`,
`data-eff` -> the slider, `data-tact` -> `taskAct`. `showPage` handles `"task"` like `"session"` (scroll to top).

## 5.7 Check in headless Edge (Claude's part of this task)

```bat
set CC_CONSOLE_HOME=%TEMP%\cc17-home
py -m console --serve   :: on a spare port set in that home's config.json ("port": 47791), fake claude in "claude_exe"
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --disable-gpu --window-size=400,760 --screenshot=%TEMP%\cc17-list.png http://127.0.0.1:47791/
```

Seed through the API with the fake claude: a `CHAIN` Prep, Run as task, then screenshots of the list (task card
under Working, the slider under the box), the Prep page with the step list, the Task page (chain rows, note,
buttons) at 400 and 340 px; read each PNG. No console error (`--enable-logging --v=0` with
`--log-file`, grep for `Uncaught`). The fake claude's `HANDOFF-OK` word in the step goals drives the chain to
`done`.

## Steps

- [x] 1. `index.html`: the slider div, the task section. `style.css`: the selectors of 5.1, 5.3 (`.card.task`,
      `.tag`), 5.4 (`.chain`, `.chain .row`). Load the page: nothing broken, the slider drawn empty.
- [x] 2. `app.js` 5.1 (slider, draft, Alt keys, `doRun` / `rawRun` effort). Check: a pick survives a reload
      (window.json).
- [x] 3. `app.js` 5.2 (step list, Run as task). Check with a `CHAIN` Prep.
- [x] 4. `app.js` 5.3 and 5.4 (task card, Task page, levers, step tag). Check the pages at 400 and 340 px.
- [x] 5. `node --check web/app.js` (syntax) and the whole Python suite OK. Commit:
      `feat: effort slider, Run as task, task card and Task page (plan 17 Task 5)`.

## Drift guards

- One slider, one value for the whole task; no per-step effort control (decision 16 a).
- Model per step only through the card's select (`pick`); the Task page never changes a route.
- The task card never starts anything; every button posts to a `/api/task/*` route that goes through
  `task_levers`.
- No new colour: orange for `waiting`, red for `stuck`, green for `done`, ink for `running`, as the state table.
- No animation beyond the one blinking cell on the running step.
