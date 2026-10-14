# Task 2: The Board shell: the page, widen and return, the buttons, the pick, the keyboard, the fold memory

> Contract: [README.md](README.md) 3.3 (the window API), 3.4 (the pinned names), 3.5 (the strings), 3.6. Design:
> interface doc 2 (the window: one window, a Board button widens it, Esc returns), 4 (list header button), 8 (the
> Board: two columns, footer keys), 1 (folds remembered per window). Mock: `design/rework/locked/cells-board.html`,
> function `boardHtml(v)` (the frame: top bar, `.board`, `.bchain`, `.binsp`, `.bfoot`), `listHtml()` (the `⇔ Board`
> `.wide-btn` in the list header), the CSS block `/* ---- the Board (plan 25) */` (`.board`, `.bchain`, `.binsp`,
> `.bfoot`, `.bfoot .q`) and `.wide-btn`. Depends on Task 1.
>
> Lands on: plan 23 Task 6 (the delegated `[data-fold]` click handler and `fold(label, info, body, o)`): this task
> adds `o.key` to `fold` and the fold memory to that handler (2.6). Plan 26 (the Settings and Models pages) adds pages
> to `showPage` and `go`: the `board` lines sit beside theirs.

**Files**
- Modify: `web/index.html` (one new `<section data-page="board">`, the list header's Board button)
- Modify: `web/app.js` (state and constants of 3.4; `openBoard`, `closeBoard`, `renderBoard`, `boardTasks`,
  `boardProject`, `boardItems`, `boardKey`, `taskRowSig`, `foldOpen`, `saveFolds`; `showPage`, `render`, `go`,
  `goBack`, `saveDraft`, `renderTaskPage`, the global click handler, the keydown handler, the start block)
- Modify: `web/style.css` (the Board frame rules, `.wide-btn`)

## 2.1 `web/index.html`

After the `task` section, before `usage`:

```html
    <section data-page="board" hidden>
      <div class="top">
        <button class="rb" data-go="back" title="Back (Esc)" aria-label="Back">&#8592;</button>
        <span id="bcrumb" class="crumb m">Board</span>
        <span class="sp drag-region" title="Drag to move; double-click to fold"></span>
        <span data-winbtns></span>
      </div>
      <div class="board"><div id="bchain" class="bchain"></div><div id="bwrap" class="bwrap"></div></div>
      <div id="bfoot" class="bfoot"></div>
    </section>
```

In the list header, after `#needsbtn`:

```html
        <button id="boardbtn" class="wide-btn" data-go="board" title="Open the Board: the window widens to 900 px" hidden>&#8660; Board</button>
```

`#bwrap` holds one `<div class="binsp">` (the inspector's scroller, `setHtml($("bwrap"), html, { sel: ".binsp" })`);
`#bchain` scrolls itself (`setHtml($("bchain"), html)` keeps its `scrollTop` because the element stays).

## 2.2 State and constants (`web/app.js`, after `let freshHandoff`)

```js
let boardFrom = null;    // {page, id}: where the Board opened from; Esc and the back arrow return there
let boardTask = "";      // the picked task ("" none: the Board picks the newest in scope)
let boardPick = "";      // "" nothing (the Measure table), "t" the task head, "s<n>" a step, "c<n>" the connector after step n
let itab = "chat";       // the step inspector's tab (window.json board_tab)
let boardData = null;    // {id, sig, data}: GET /api/task of boardTask
let boardChat = null;    // {sid, at, chat}: GET /api/chat of the picked step's session
let measureData = null;  // {project, at, data}: GET /api/measure
let foldState = {};      // window.json folds: {key: open}
const toolOpen = new Set();  // "<session>:<k>": the chat's tool rows Fred opened (not kept)
const BOARD_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Escape"]);
```

Comment on `page`: `// list | session | prep | task | usage | board`.

## 2.3 Open and close

```js
async function openBoard(id) {  // the Board is a page: the window widens to the saved Board size, Esc gives the old size back
  if (form === "pill") await setForm("open");
  boardFrom = page === "board" ? boardFrom : { page, id: page === "task" ? taskId : page === "session" ? openId : "" };
  const t = (snap.tasks || []).find((x) => x.id === id) || boardTasks()[0];
  boardTask = t ? t.id : "";
  boardPick = t && t.steps.some((s) => s.n === t.current) && t.state !== "done" ? "s" + t.current : t ? "t" : "";
  boardData = boardChat = null;
  if (native()) await window.pywebview.api.board(true);
  showPage("board");
}

async function closeBoard() {  // back to the page the Board opened from, at the compact size
  const b = boardFrom;
  boardFrom = null;
  if (native()) await window.pywebview.api.board(false);
  if (b && b.page === "task" && (snap.tasks || []).some((t) => t.id === b.id)) return openTask(b.id);
  if (b && b.page === "session" && b.id) return openSession(b.id, tab);
  showPage("list");
}
```

`boardTasks()`: the tasks in scope (`!scope || sameDir(t.project_dir, scope)`), newest `updated` first; the same day
rule as `taskGroups` (a finished or stopped task a day after its last change is not listed). `boardProject()`:
`scope` when set, else the picked task's `project_dir`, else `""`.

## 2.4 `showPage`, `render`, `go`, `goBack`

- `showPage(name)`: `if (name === "board") { $("bchain").scrollTop = 0; boardData = null; }`; the page list in
  `document.querySelectorAll("[data-page]")` needs nothing else.
- `render()`: `else if (page === "board") renderBoard();`.
- `go(name)`: `if (name === "board") openBoard(page === "task" ? taskId : "");`; `back` on the Board calls
  `closeBoard()` (in `goBack`: `if (page === "board") return closeBoard();` first); `fold` from the Board calls
  `await closeBoard()` before `setForm("pill")` (the pill never keeps the Board size: `form("pill")` clears `_board`
  in the service too).
- A step session opened from the Board returns to it: in the global click handler's `backTo` block, a `data-open`
  inside `#bwrap` or `#bchain` sets `backTo = { page: "board" }`; `goBack()` gains `if (b && b.page === "board") return
  showPage("board");` (no resize: the window is still wide, `boardFrom` is still set).
- The session page opened from the Board is drawn at the Board's width: nothing to do (its rules are fluid); the
  check in 2.9 measures it.

## 2.5 `renderBoard()` (the frame; Tasks 3, 5, 6 fill it)

```js
async function renderBoard() {
  const tasks = boardTasks(), row = tasks.find((t) => t.id === boardTask) || tasks[0];
  if (row && row.id !== boardTask) { boardTask = row.id; boardPick = "t"; boardData = null; }
  $("bcrumb").textContent = `Board / ${scope ? projectName(scope) : "All projects"} · ${tasks.length} ${tasks.length === 1 ? "task" : "tasks"}`;
  setHtml($("bfoot"), tasks.length ? `<span><span class="kbd">↑</span><span class="kbd">↓</span> step</span><span><span class="kbd">←</span><span class="kbd">→</span> task</span><span><span class="kbd">Enter</span> chat</span><span><span class="kbd">Esc</span> back</span><span class="sp"></span>
    <button class="q" title="A step's context in cells of 10K; the chip between two steps is the handoff the next one received, its words in the inspector" aria-label="Legend">?</button>` : "");
  if (!row) {  // the empty Board (Task 3 3.7 draws it)
    setHtml($("bchain"), emptyBoard());
    setHtml($("bwrap"), "");
    return;
  }
  const sig = taskRowSig(row);
  if (!boardData || boardData.id !== row.id || boardData.sig !== sig) {
    const id = row.id, data = await api("/api/task?id=" + encodeURIComponent(id)).catch(() => false);
    if (page !== "board" || boardTask !== id) return;
    boardData = { id, sig, data };
  }
  const d = boardData.data;
  setHtml($("bchain"), tasks.map((t) => chainHtml(t, t.id === row.id ? d : null, t.id === row.id ? boardPick : null)).join(""));
  setHtml($("bwrap"), `<div class="binsp">${await boardInspector(row, d)}</div>`, { sel: ".binsp", reset: boardWrapKey() });
}
```

- `taskRowSig(row)`: the signature line of `renderTaskPage` moved into a function and used by both pages (one
  definition): `[row.updated, row.state, row.owner, row.why, row.briefing, row.cleared, row.cost, row.steps.map((x) =>
  x.note).join(), row.asks, row.hand_off, run ? run.state + run.run_live : ""].join("|")`, `run` the current step's
  session as today. `renderTaskPage` calls it; nothing else in it changes.
- `boardInspector(row, d)`: `d === false` gives `<p class="note m">This task is gone: it was cleared or its folder was
  removed.</p>`; `boardPick === ""` gives `inspMeasure` (Task 6); `"t"` gives `inspTask` (Task 6); `"c<n>"` gives
  `inspConn` (Task 6); `"s<n>"` gives `inspStep`, or `inspReplan` / `inspGap` when the step is the one a replan or a
  Plan gap waits on (Task 5). Until those tasks land it returns `""` for the cases not yet written, so each task's
  check runs on its own.
- `boardWrapKey()`: true when the pick changed since the last draw (`boardWrapKey.last !== boardTask + boardPick +
  itab`), so a new pick starts at the top and a redraw of the same pick keeps the scroll.

## 2.6 The fold memory (`foldOpen`, `saveFolds`, `fold`'s `o.key`)

```js
function foldOpen(key, dflt) { return key && key in foldState ? foldState[key] : !!dflt; }
function saveFolds() { saveDraft(); }  // the draft save carries folds and board_tab (2.7)
```

- `fold(label, info, body, o)` (plan 23 Task 6): when `o.key` is set and `o.force` is not, the open state is
  `foldOpen(o.key, o.open)`, and the button carries `data-fkey="<key>"`. `o.force` (a FAIL, a failing check) opens the
  fold whatever the memory says. Keys are the `[a-z][a-z0-9.]{0,39}` shape the service checks: the Board uses
  `facts`, `checks`, `prompt`, `promptmd`, `clog`, `qclosed`, `plan.<heading>`, `h.<heading>` (the six handoff headings), never a
  step number (a fold's memory is per kind of fold, per window, not per step).
- The `[data-fold]` click handler (plan 23's): after toggling, `if (b.dataset.fkey) { foldState[b.dataset.fkey] =
  open; saveFolds(); }`. Over 64 keys the oldest is dropped before the save (`Object.keys(foldState)[0]`).

## 2.7 `saveDraft` and the start block

- `saveDraft()` posts `{ text: draft, project, brief: briefOpen, effort: effortPick, board_tab: itab, folds: foldState }`.
- The start block: `itab = cfg && ["chat", "recv", "hand", "route", "plan"].includes(cfg.board_tab) ? cfg.board_tab :
  "chat"; foldState = (cfg && cfg.folds) || {};`.

## 2.8 The Board buttons and the keyboard

- `renderTop()`: `$("boardbtn").hidden = !native() && innerWidth < 700;` and `.on` when `innerWidth >= 700` (a window
  dragged past 700 px lights the button; it never switches the page by itself). Under a 372 px container the button
  hides (CSS `@container` on `.top` if the stylesheet has one, else `@media (max-width: 371px)`).
- The Task page head's button is Task 7's.
- `boardKey(e)` in the keydown handler, before the `Escape` branch: `if (page === "board" && form === "open" &&
  BOARD_KEYS.has(e.key) && !inField && !e.target.closest(".tabs")) return boardKey(e);`.

```js
function boardKey(e) {
  const tasks = boardTasks(), k = tasks.findIndex((t) => t.id === boardTask), row = tasks[k];
  e.preventDefault();
  if (e.key === "Escape") { if (boardPick) { boardPick = ""; renderBoard(); } else closeBoard(); return; }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const to = tasks[k + (e.key === "ArrowRight" ? 1 : -1)];
    if (to) { boardTask = to.id; boardPick = "t"; boardData = boardChat = null; renderBoard(); }
    return;
  }
  if (!row) return;
  const items = boardItems(row), at = items.indexOf(boardPick);
  if (e.key === "Enter") {
    const s = boardPick[0] === "s" && row.steps.find((x) => "s" + x.n === boardPick);
    if (s && s.session) { backTo = { page: "board" }; openSession(s.session); }
    return;
  }
  const to = items[at < 0 ? 0 : at + (e.key === "ArrowDown" ? 1 : -1)];
  if (to) { boardPick = to; renderBoard().then(() => { const f = document.querySelector(`#bchain [data-bpick="${to}"]`); if (f) f.focus({ preventScroll: false }); }); }
}
```

- `boardItems(row)`: `["t", "s1", "c1", "s2", ...]` in chain order: the head, then each step, then the connector
  after it when it is not pending (Task 3 3.5 decides pending) and the step is not the last.
- Clicks: an element with `data-bpick` sets `boardPick` (a task head of another task also sets `boardTask` from its
  `data-btask`) and redraws; add `[data-bpick]` and `[data-itab]` to the global click handler's selector list
  (`data-itab` sets `itab`, calls `saveDraft()` and redraws).
- Esc on the session page opened from the Board goes back to the Board (2.4), a second Esc closes it.

## 2.9 `web/style.css` (under the Task page section, `/* the Board (plan 25) */`)

Port the mock's `.board`, `.bchain`, `.binsp`, `.bfoot`, `.bfoot .kbd`, `.bfoot .sp`, `.bfoot .q` and `.wide-btn`,
`.wide-btn:hover`, and add `.wide-btn.on { color: var(--ink); border-color: var(--ink); }`. `[data-page="board"]`
takes the `.win` column layout the other pages use (`display: flex; flex-direction: column; min-height: 0`), `.bwrap`
is `min-height: 0; display: grid;` so `.binsp` scrolls. No new token in this task.

## 2.10 Checks (headless Chromium or Edge, the fake service of README 4)

1. 400 x 760, the list: `⇔ Board` in the header (shown because the window is under 700 px only when native; in the
   browser at 400 px it is hidden: check at 760 px that it shows and is lit `.on`). 340 x 760: hidden, no overflow.
2. 900 x 680, `go("board")`: the crumb `Board / All projects · 2 tasks`, the footer keys, no console error, no
   horizontal overflow on the document, `.bchain`, `.binsp`.
3. `boardKey` with ← → moves the picked task; ↑ ↓ moves `boardPick` through `boardItems`; Esc with a pick clears it,
   a second Esc returns to the list; Enter on a step opens its session and Esc comes back to the Board.
4. `foldState` after toggling a fold with a key: `/api/config` read again carries it; `board_tab` likewise.

## 2.11 Steps, in order

1. `index.html` (2.1); `style.css` (2.9).
2. `app.js`: 2.2, `taskRowSig` (and `renderTaskPage` calling it), 2.3, 2.4, 2.5 with `boardInspector` returning `""`
   and `chainHtml` a stub that lists task titles (Task 3 replaces it), 2.6, 2.7, 2.8.
3. `node --check web/app.js`; `py -m unittest discover -s tests` (the count of Task 1, unchanged); the checks of 2.10.
4. Commit `plan 25 task 2: the Board page, widen and return, the buttons, the keyboard, fold memory (N tests OK)`.

Expected count: unchanged (browser code).

## 2.12 Drift guards

- The Board is a page of the one window (`showPage("board")`); it never opens a second pywebview window.
- The window size changes only through `WindowApi.board(on)`; the grip on the Board calls `resize` as on every page
  (the service keeps it as `board`).
- `GET /api/task` once per row signature: `taskRowSig` is the one definition.
- `saveDraft` stays the one writer of window.json fields from the page.
