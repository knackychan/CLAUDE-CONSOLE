# Task 5: The step inspector: head, tabs Chat / Received / Handoff / Route / Plan, Facts, the replan and Plan gap askboxes

> Contract: [README.md](README.md) 3.2, 3.4, 3.5 (tab labels, Facts fold), 3.6. Design: interface doc 8.2 (the picked
> step: Chat first), 8.3 (Received / Handoff, ID-9; the Plan tab), 7 (the askboxes), brainstorm 8b. Mock:
> `cells-board.html` functions `inspStep`, `inspReplan`, `inspGap`, `planPane`, `planHtml`, `planSection`, `stepBody`,
> `partRow`, the views `Board · step`, `Board · live`, `Board · replan`, `Board · plan`, `Board · plan gap`, and the CSS
> block `/* inspector pieces */` (`.ihead` to `.fold.facts .mono`, `.plan1` to `.plan1 li.drop`). Depends on Tasks 3
> and 4.
>
> Lands on: plan 23 Task 6 (`fold`, `handoffSections`, `headingBlock`, the facts file in `d.facts`), plan 24 Task 4
> (`planSections`, the Plan row's open body `planRowHtml(t, d)`, `taskAct` cases `gapanswer`, `redo`, `keep`,
> `confirm`, the `.edbox`, `POST /api/task/plan`; plan 23's `factsFold(f, text)`, replaced in 5.5). This task splits plan 24's Plan row body into
> `planOpenHtml(t, d, cur, o)` (5.6) and makes `taskAct` read the task id from the button (5.8).

**Files**
- Modify: `web/app.js` (`inspStep`, `recvPane`, `handPane`, `routePane`, `planPane`, `factsFold`, `inspReplan`,
  `inspGap`; `boardInspector`'s step cases; plan 24's `planRowHtml` split; `taskAct`, `stepAct` id lookup; the Board's
  chat fetch)
- Modify: `web/style.css` (the inspector rules)

## 5.1 The head (`inspStep(t, s, d, row)`)

```
<div class="ihead">
  <div class="ln1">[sprite][BWORD word]  <h2>NN kind</h2>  <span class="lr">[Open chat][Stop][Open try 1]</span></div>
  <div class="meta"><span>rung</span><span>cost <b>...</b></span><span>time</span></div>
</div>
<div class="tabs" role="tablist">...</div>
<div class="ipane">...</div>
```

- Word and sprite: `BWORD[stepShown(t, s, row)]` (Task 3).
- `Open chat` (`data-open="<s.session>"`, title `The session page, with its levers`) when the step has a session (a
  replan step has none). `Stop` (`btn sm stop`, `data-tact="stop" data-tid="<t.id>"`) when `s.state === "running"`
  and `d.levers.stop === ""`: the task lever, the run's interrupt (README 3.6). `Open try 1` (`data-open` of the first
  failed attempt's session) when the step is `failed` with an earlier attempt.
- Meta: `rungTime(s)` split as rung (`modelText`, or `rung at start` when planned) and time; `cost <b>` with
  `stepCost(s)` (`unknown` spelled out when null).

## 5.2 The tabs

| Key (`itab`) | Label | Shown |
|---|---|---|
| `chat` | `Chat` | always |
| `recv` | `Received` and, when the step got a handoff, ` <span class="n">S w</span>` (`prev.brief_meta.sent_w`, else the brief file's word count) | always |
| `hand` | `Handoff` and ` <span class="n">R w</span>`, or `R → S w` when the next step received fewer (`s.brief_meta.raw_w`, `.sent_w`) | always |
| `route` | `Route` | always |
| `plan` | `Plan <span class="n">W w</span>` (`t.plan.words` with a thousands separator, no arrow: a plan is never cut) | `d.plan && t.plan && s.n >= t.plan.from` |

A tab that is not shown on this step falls back to `chat` for the draw, without changing `itab` (so the next step
that has a Plan tab opens on it again). Tabs are `button role="tab" data-itab="<key>" aria-selected`; ← → on a focused
tab moves through them (the keydown handler's `[data-tab]` branch extended to `[data-itab]`).

## 5.3 The Chat tab

- The step's session (`s.session`): `boardChat` holds `{sid, at, chat}`; `renderBoard` fetches `GET /api/chat?session=`
  when the pick's session differs from `boardChat.sid`, or every 2 s while the step runs (`snap.now - boardChat.at >= 2`
  or the live row's `turn_ts` moved). The pane is `chatPane(boardChat.chat, s.session, "chat", { prompt: true, step: s,
  compact: true, board: true })`.
- No session: planned `Not started: the chat shows here as the step runs.`; a replan step `No chat: the replan step
  runs one Haiku turn with no tools; its answer is in the Handoff tab.`

## 5.4 Received (`recvPane(t, s, d)`)

- Step 1: `<p class="note m">No handoff: step 1 gets the task goal and Prep's context pack.</p>`
- Else: head `.blk .hd` `From NN` and `S w · compacted` (or `· as written` when `prev.brief_meta.fallback`); body
  `headingBlock(handoffSections(d.briefs[s.n - 1]), [], ["goal", "findings", "questions", "next"])`. No brief file:
  `The brief of step NN is not on disk (cleared, or the step never ran).`
- The step after a design step (plan 24): one line above the headings, `and plan.md, W w, never cut (the Plan tab)`.

## 5.5 Handoff (`handPane(t, s, d)`)

- Running: `Writing. Shows here when the run ends.`; planned: `Not started.`; done without a note: `No handoff: the
  step ended without a HANDOFF block.`
- Else: head `For NN+1` and `wrote R w · NN+1 received S w` (or `· sent as written` on a fallback; the last step reads
  `For the task's end` and `wrote R w`); body `headingBlock(handoffSections(d.notes[s.n]), meta.cut || [])` (plan 23:
  the cut lines struck in place, tagged `cut`); then `factsFold(s, d.facts[s.n])`.
- `factsFold(s, text)`:

```js
function factsFold(s, text) {  // the facts the service gathered when the step ended (plan 23): diff stat and the test line
  const f = s.facts || null;
  if (!f || !text) return "";
  const fail = String(f.tests || "").startsWith("FAIL");  // plan 23: "" (no test run), "23 OK" or "FAIL <first failing line>"
  const info = `${f.files} files +${f.plus}${f.minus ? " -" + f.minus : ""} · ${esc(f.tests || "no test run")}`;
  return fold("Facts", info, `<pre class="text mono">${esc(text)}</pre>`, { cls: "facts", tone: fail ? "r" : "", open: fail, force: fail, key: "facts" });
}
```

  Plan 23 Task 6 already defines `function factsFold(f, text)` (its first argument is the facts dict, not the step).
  Replace that function with this one (one definition in app.js, never two), and in plan 23's `handoffFold` change
  the call `factsFold(sn && sn.facts, d.facts[String(n)])` to `factsFold(sn || {}, d.facts[String(n)])`.

## 5.6 Route (`routePane(s)`) and Plan (`planPane(t, d, s)`)

- Route: `.blk` `Goal` with `s.goal`; `.blk` `Route · in the order the rules applied` with `s.notes` as `.rn` chips
  (`<span class="y">` for `/every .* over pace/`: plan 18's balance notes; the rest muted); then `Attempts` with
  `stepTries(s)` when there are two or more.
- Plan: plan 24 Task 4's open Plan row body, split out of `planRowHtml(t, d)` as `planOpenHtml(t, d, cur, o)` (`cur`
  the step whose `### Step N` or part opens, `o.design` opens Goal and Decisions, `o.verify` opens Acceptance;
  `planRowHtml` calls it with `t.current`). `planPane` wraps it:
  head `plan.md` (`+ N parts`) and the line by role: the design step `written by this step · K KB of <plan_max_kb>`; a
  split plan `index and part N sent to this step`; verify or fix `the whole plan: Steps and Acceptance are what you
  check`; else `the whole plan, your ### Step N again at the end of the prompt`. Fold keys `plan.<heading>` (`goal`,
  `dec`, `out`, `files`, `steps`, `acc`).
- Edit on the Board: on the design step while the next step has not started (`d.levers.plan === ""` if plan 24
  exposes it, else `t.steps.find(x => x.n === s.n + 1).state === "planned"`), an `Edit` button (`data-fold="edbox"`)
  opens plan 24's `.edbox` under the head; `Save` posts `POST /api/task/plan` through plan 24's Save
  handler, given the task id from `data-tid`. Errors go to `#b-msg` (5.8).

## 5.7 The askboxes on the Board

- `inspReplan(t, s, d)`: the picked step is the replan step and `row.why` starts `replanned:`. The mock's head
  (`Waiting`, `NN replan`), the askbox `Replanned · after step NN` with `d.replan_note`'s why line, `New plan · N
  steps (was M)` and the list from `t.replan.after` (added `li.add`, kept `li.old`; dropped from `t.replan.before`
  struck `li.drop`), buttons `Confirm plan` (`btn you`, `data-tact="confirm" data-tid`), `Keep old plan` (`keep`),
  `Stop` (`stop`); folds `Why it ran` (the earlier step's `Next:` line) and `Route` (`s.notes`, cost, time).
- `inspGap(t, s, d)`: the picked step is the current one and `row.asks` starts `Plan gap:`. Head as 5.1 with `· from
  plan`; the askbox `Plan gap · step NN stopped, nothing chosen`, the question, `<textarea class="in" rows="2">`
  placeholder `Your answer joins the plan's Decisions as Fred, <date>: ... and continues step NN in its chat.`,
  buttons `Send answer` (`btn you`, `data-tact="gapanswer" data-tid`), `Redo design` (`redo`), `Stop`; then the tabs
  of 5.2, Plan tab included.
- `boardInspector`'s `s<n>` case picks `inspReplan`, `inspGap` or `inspStep` in that order.

## 5.8 `taskAct` and `stepAct` from the Board

- `taskAct(name, button)`: `const id = button.dataset.tid || taskId;` and every `taskId` after the arm block reads
  `id`; `gapanswer` reads the textarea in `button.closest(".askbox")` (not `#t-answer` by id); after a success on the
  Board, `boardData = null; renderBoard();` instead of `taskSig = ""; renderTaskPage();`; errors go to `$("b-msg")`
  on the Board (`<div id="b-msg" class="say"></div>` under the inspector head), `#t-msg` / `#ta-msg` on the Task page.
- `clear` from the Board (the task head, Task 6) leaves the Board's pick on the next task, not the list.
- Orange (`btn you`) only on the button that answers the wait (README 3.6).

## 5.9 `web/style.css`

Port `.ihead` to `.ihead .ln1 .lr`, `.binsp .tabs`, `.ipane`, `.ipane .chat .turn p`, `.ipane .doing`, `.rn`, `.rn
span`, `.rn span b`, `.rn span.y`, `.fold.facts`, `.fold.facts .mono`, `.plan1` to `.plan1 li.drop`. `.hb`, `.hsec`,
`.fold` and the plan rules are plan 23's and plan 24's: do not copy them twice (check `grep -n "^\.hsec" web/style.css`).

## 5.10 Checks (900 x 680, the fake runs; and a task.json edited by hand for the plan cases)

1. Pick a done step: the head, `Chat` open on the step's chat (Prompt row folded, HANDOFF chip), `Received`
   with no figure on step 1 and its no-handoff line, `Handoff 412 → 290 w` when `brief_meta` says so, the Facts fold closed
   with its line; a step whose facts say `FAIL` shows it red and open.
2. Pick the running step: `Stop` (two clicks, the task lever), the chat refreshing every 2 s, `Writing.` in Handoff.
3. Route: the goal and the notes in order; a note `every 5h over pace` in orange.
4. `itab` survives a pick change and a reload (window.json `board_tab`); a step without a plan shows Chat when
   `itab` is `plan`.
5. With plan 24 placed: a task with `plan.md`: the Plan tab from the design step on, `this step` section open; Edit and
   Save on the design step before step 3 starts; the replan and Plan gap askboxes; Send answer posts and the board
   redraws; a 409 shows in `#b-msg`.
6. No horizontal overflow in `.binsp` with a long goal, a 200-column facts line (`pre.text` wraps) and a long model.

## 5.11 Steps, in order

1. `style.css` (5.9).
2. `app.js`: the Board's chat fetch in `renderBoard`; `inspStep`, `recvPane`, `handPane`, `factsFold`, `routePane`;
   the `planOpenHtml` split and `planPane`; `inspReplan`, `inspGap`; `boardInspector`'s step case; `taskAct` (5.8).
3. `node --check web/app.js`; the full suite; the checks of 5.10.
4. Commit `plan 25 task 5: the step inspector and the Board's askboxes (N tests OK)`.

Expected count: unchanged.

## 5.12 Drift guards

- Received and Handoff render the files plan 23 serves (`d.briefs`, `d.notes`, `d.facts`) with plan 23's
  `handoffSections` and `headingBlock`: no second parser, no fetch per tab.
- Chat is the first tab and the default (ID-9); the tab words are Received and Handoff in the window, `brief` and
  `note` stay code names.
- Stop is the task lever; Open chat goes to the session page, where the session levers live.
