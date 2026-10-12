# Task 5: The window: one row per task, every step reachable, the step list always on the card

> Contract: [README.md](README.md) 3.5. Findings A2 (D2), B1 (D6 a), B2, B7. Depends on Tasks 3 and 4 (the
> row's `attempts`, `paused_after`, `hold`; `/api/config` `edit_kinds`; `/api/chat` by transcript).

**Files**
- Modify: `web/app.js`, `web/style.css` (and `web/index.html` only if a page needs a new element; none is planned)
- No Python. Checks: `node --check web/app.js`, the suite, headless Edge (5.6).

## 5.1 The list folds step sessions (B1, D6 a)

`groups()`: `const mine = snap.sessions.filter((s) => inScope(s) && !s.task);`. Nothing else changes in the
list: `taskCard` already shows the task under Needs you / Working / Done today, with Open on a question wait.
`taskTag(s)` stays (the session page and the peek card still name the step). `navList()` reads `groups()`, so a
step session opened from the Task page is out of the list: its pager is Task 7's.

## 5.2 Task page rows: Open on every attempt (B2, B7)

`chainRow(t, s)` (attempts come from the full task.json in `taskData`, `tasks.attempts` shape; a step from before
plan 19 has none: use `s.session` as its one attempt):

- The Open button shows whenever the step has a session, cleared or not (the step's last attempt).
- The sub line: verdict, then `try N of M` when there are two attempts or more, each earlier attempt as
  `<span class="link" data-open="SID">try K</span>` followed by its `why` (escaped), then the goal.
- The cost cell is the step's `cost` (the sum, Task 3).

```js
function stepTries(s) {  // the earlier attempts of a step, each a link to its chat: "try 1 (no HANDOFF block)"
  const all = s.attempts && s.attempts.length ? s.attempts : (s.session ? [{ session: s.session, why: "" }] : []);
  return all.slice(0, -1).map((a, k) => `<span class="link" data-open="${esc(a.session)}">try ${k + 1}</span>${a.why ? " " + esc(a.why) : ""}`).join(" · ");
}
```

Put it right above `chainRow`; `chainRow`'s `sub` becomes `[verdict, stepTries(s), esc(s.goal)]`, and the Open
test drops `&& !t.cleared`.

## 5.3 A step session older than a day (B2)

`renderSession()` with no `s` (the id is not in the snapshot): when the id is an attempt of the open task
(`oldStep(openId)` searches `taskData.task.steps[*].attempts` and `session`), draw a header instead of
`Starting ...`:

```js
function oldStep(id) {  // [task, step] when `id` is a session of the task on the Task page; else null
  const t = taskData && taskData.task;
  const s = t && t.steps.find((x) => x.session === id || (x.attempts || []).some((a) => a.session === id));
  return s ? [t, s] : null;
}
```

Header: `<h2>` the task title, the line `step N/M · kind · older than a day: the Chat reads its transcript`, a
link back (`<span class="link" data-task="ID">task</span>`). Then `renderOldChat(id)` fills `#proc` with the chat
markup of `GET /api/chat?session=ID` and no tabs. To share the markup, move the chat body of `renderProc` into
`chatPane(chat, sid, source)` right above `renderProc` (returns the `<div class="chat">...</div>` string) and call
it from both; this is the only move inside `renderProc`. Levers: `setHtml($("levers"), "")`.

## 5.4 Task page head and lines (B7)

- The where line: `${project} / effort: ${effort} · $${money(row.cost)}` (the total; the row is in `snap.tasks`).
- Paused: when `row.paused_after`, under the head: `<p class="note m">Paused: step N ended. Nothing starts until
  you Resume.</p>`; while paused and a step runs, the head's `· paused` stays as it is.
- A hold: the confirm button reads `Run anyway` when `row.hold`, with the why line `opus over its pace` already in
  the askbox. The Fable label is Task 6's.
- The off reasons line keeps its four levers (stop, pause, retry, clear); add `resume` when the task is paused and
  `lv.resume` is not `""` (it then says why Resume is off).

## 5.5 The step list always on the Prep card (A2, D2)

- `showPrep()` always draws the Steps block (drop both `steps.length >= 2` tests). With no rows, `#p-steps` holds
  `<p class="m mut" data-nosteps>Prep proposed no steps. Add steps to run this as a task.</p>`.
- `prepAct("addstep")` removes `[data-nosteps]` first.
- `stepsChanged()`: the Console's verify row follows the rows: when a `[data-row]` has a kind in
  `cfg.edit_kinds` and there is no `.srow.fixed`, append `stepRowHtml({ kind: "verify" })`; when none has, remove
  it. Run as task shows when the rows (verify included) number 2 or more.
- The `change` listener (app.js line 1629) also calls `stepsChanged()` for `[data-skind]`.
- Nothing about the verify is sent: `stepList()` reads `[data-row]` only, and the service appends the verify
  (`tasks.plan_steps`).

## 5.6 Check in headless Edge (Claude's part)

Scratch home in the scratchpad (never `~/.claude/console`):

```bat
set CC_CONSOLE_HOME=<scratchpad>\cc19-home
:: config.json there: "port": 47791, "claude_exe" = the fake (a .cmd that runs py tests\fake_claude.py), "projects": [a scratch project]
py -m console --serve
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --disable-gpu --window-size=400,760 --enable-logging --v=0 --screenshot=<scratchpad>\list-400.png http://127.0.0.1:47791/
```

Seed through the API of the scratch service only (fake claude, scratch home): a `CHAIN` Prep and Run as task with
`HANDOFF-OK` (done chain), a task without HANDOFF (stuck after the retry: two attempts), a plain Prep with no
steps. Screens at 400 and 340 px, each PNG read:

1. The list: one task row per task, no step session rows; Done today counts tasks and loose sessions only.
2. The Task page of the stuck task: `try 1` link with its why, Open on the step, the total cost.
3. The Task page of the done (cleared) task: Open on every step.
4. A session page opened from a `try 1` link (its Chat).
5. The Prep card of the no-steps Prep: the hint, `+ step`, a code row added: the verify row appears, Run as task
   shows.

To check the older-than-a-day view, open `#` with an id whose transcript exists under the scratch
`user_home` only (the service's `user_home` follows `Path.home()`: point the scratch test at a fake transcript by
running the service with `USERPROFILE` set to a scratch folder for this one screen). No `Uncaught` in the log.

## 5.7 Order (one commit per step)

1. 5.1; load the list; commit `feat: the list folds step sessions under their task (plan 19 Task 5)`.
2. 5.2 and 5.4; Task page screens; commit.
3. 5.3 (`chatPane` moved out first, screens unchanged, then the old view); commit.
4. 5.5; Prep screens; commit.
5. `node --check web/app.js`, the suite; PLAN.md History line; commit.
