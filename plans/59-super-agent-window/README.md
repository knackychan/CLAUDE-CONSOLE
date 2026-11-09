# Plan 59: The super agent window. The row, its page, cards answered in place and one box, reading plan 58's data. Guided implementation plan

> Design: [../../design/brainstorm/2026-11-08-super-agent.md](../../design/brainstorm/2026-11-08-super-agent.md),
> slice 2 of section 9 (sections 5, 6, 9, 11). Locked target (Fred, 2026-11-08):
> [../../design/rework/locked/super-agent.html](../../design/rework/locked/super-agent.html); its "Design read" and
> "Decided by Fred" notes are binding. Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
> Reads: plan 58 (the data, [README](../58-super-agent/README.md) 3.3 to 3.10 and its
> [review R1-R9](../58-super-agent/08-review-and-jev.md)); plan 55 (the web parts, [README](../55-autopilot-ui/README.md)
> Tasks 1 to 3). Replaces plan 55 Task 4 (the list, UI-1 and UI-2). Reuses plan 52's
> [design lock](../52-workflow-autopilot/08-design-lock.md) (head, sections, dock card, box, bar).

Status: **written 2026-11-08, plan only, decisions closed 2026-11-08** (D1 b with a Task 0, the rest a) (section 7; written for each recommended option
(a), the task files mark the lines another answer changes). Baseline `a627264` (docs only since `9b6f988`, 1167 tests
OK). Nothing is implemented and no product file was touched by writing this plan. Fred chose to plan slice 2 now;
design section 9 says each slice's plan follows the build of the one before, so **this plan is written against the
documented contracts of plans 58 and 55, not against code** (section 2 lists every symbol it relies on).

**Amended by design 2026-11-09 (BRAINSTORM D19, `design/brainstorm/2026-11-09-super-agent-chat.md`):** do not build
section 4.9 (a message to the super agent as a note), its `message` action in Task 3, or the `◆ Super agent` box mode
in Task 6. D4 is superseded: the chat plan (slice 3) brings the box mode as a chat that replies and presses card
actions. Everything else in this plan stands, the cards included.

**The build waits.** Do not start Task 1 until all three hold:

1. Plan 58 is built, its Task 7 live check passed, and its D2, D6, D9, D10 are closed (this plan marks where each
   one changes a line: `[58 Dn]`).
2. Plan 55 Tasks 0 to 3 are built ([D1 b, Fred 2026-11-08]: and this plan's Task 0) and its Stop 1 passed (the seam, head, dock card, box, bar, sections, plan timeline;
   `[55 Dn]` marks the open decisions). Plan 55 Task 4 is **not** built: this plan replaces it (section 6, D7). Plan 55
   Tasks 5 to 7 follow this plan unchanged.
3. Fred has answered section 7, or accepted the recommended column.

Task 1 starts with step 0: re-read section 2 against the built code. A renamed symbol is a one-line mapping change in
the one task named in its row, never a redesign.

| # | File | Delivers | Depends on |
|---|---|---|---|
| 0 | (no file yet; [D1 b, Fred 2026-11-08]) | server: `Hub.actions` serves `hint_dismiss` ("Let it continue") on a task with a hand-off hint, which clears that hint so its item leaves the queue; tests first in `tests/test_server.py`. `retry_up` and `run_instead` come from plan 55 Task 0 (55 D3 b), not here | plan 55 Task 0 |
| 1 | [01-state-and-count.md](01-state-and-count.md) | `console/superwin.py` part 1 (pure): state v2 (Later by hand, Bring back, Since you looked log, messages), the `accept` item (D10), the window queue, the one count, the mode, the row line, the controls; `snap["super"]`, `counts.for_you`, the tray; the tick writes the log | plan 58 built |
| 2 | [02-served-cards.md](02-served-cards.md) | `GET /api/super` grows: per-card served actions (`acts`), facts, `incomplete`, `back`, `open`, own-answer, batch answer, `controls`, `since`, `rev`, session cards from `Hub.levers`; read only | 1 |
| 3 | [03-writes.md](03-writes.md) | `POST /api/super` grows: `later`, `bring_back`, `seen`, `message` (wakes a pass), `orders`; the message block in the prompt; durable before the answer | 1, 2 |
| 4 | [04-row-and-list.md](04-row-and-list.md) | web: the super agent row, the roll-up list (replaces plan 55 Task 4), the header and project counts, `swFetch` on `rev`; no task opens by itself | 3, plan 55 T1-3 |
| 5 | [05-page-and-cards.md](05-page-and-cards.md) | web: the page (head, state note, For you, Later, Since you looked, Orders) and the cards, drawn from GET data; the keys | 4 |
| 6 | [06-answers-and-box.md](06-answers-and-box.md) | web: answering in place by the card-kind route table, batch accept and Review one by one, Later and Bring back, Mark seen, Edit orders, Pause / Resume / Sort in the bar, the one box and its chip, Write your own answer, a message to the super agent | 5 |
| 7 | [07-models-card-and-states.md](07-models-card-and-states.md) | the Models page card for the settings (plan 58 D9), every mock state and the unshown ones, `tests/live_super_check.py` at 900, 400, 340 px, dark and light, reduced motion, 130 % | 6 |
| 8 | [08-live-check-close.md](08-live-check-close.md) | Fred's live look with real passes (GET cost measured, "a day's items without a task page"), docs, CLAUDE.md lines, plan 55 and 58 notes | 1-7 |

Tests first in every task, one commit per task, `py -m unittest discover -s tests` at each boundary (about 10 minutes:
run it in the background and read the finished output), `node --check web/app.js` after every web edit (Tasks 4 to 7).
Other chats edit `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md`, `web/app.js`, `web/style.css`, `console/server.py` and
`console/__main__.py` in parallel: anchor every edit by the quoted line, never by a line number; stage explicit paths
and only this plan's hunks of a shared file non-interactively (`git hash-object -w` of HEAD's file plus the hunk, then
`git update-index --cacheinfo 100644,<blob>,<path>`; `git add -p` is interactive and not available here); never stage
`console/__main__.py`. Plan numbers collide between chats: run `ls plans` before any new plan file.

## 1. Goal and scope

Today (plan 58 built) every item that needs Fred is sorted and annotated, but only reachable over HTTP; the window
still pins them unranked and each answer costs a page switch (design gaps G2 to G5). This plan draws the queue:
the super agent as the first row of the list, its page as the home pane, every card answerable where it stands, one
box that always says where Enter goes, and a list that rolls quiet projects up to one line.

Done when (design section 9, slice 2): **Fred answers a day's items from the queue without opening a task page**
(Task 8), every state the mock draws is drawn (queue, sorting, partial coverage, empty, paused, off, limit reached,
failed) plus the states it does not draw (section 5.3), and the header, row, page pill, section, project lines and
tray all show one number.

**In scope:** the row and page; cards answered in place; batch accept with Review one by one; Write your own answer;
Later by hand (one fixed hour) and Bring back; Since you looked and Mark seen; Orders (list and Edit); the rolled-up
project list; the box and its chip (New work, Super agent, Answer, Task, Read only); Pause, Resume, Sort in the bar;
header and tray counts; a message to the super agent that wakes a pass; the Models page card (plan 58 D9); and, if Fred
agrees (D10), the `accept` item that lets a finished task reach the queue.

**Out of scope (later slices of the design, and its never list):**

- No acts, Undo or order proposals (slice 3): the page never draws an Undo, a proposed order or an "acted" line; the
  answer schema keeps no `act` or `order`. The mock's "Future" scenarios (acts, job, task in a job, merge) are not built.
- No jobs, stages, job page or job rows (slice 4); no worktrees, merge or conflict items (slice 5); no JEV (plan 58 D12).
- No change to a gate. Every answer is a POST to the route that already owns it (section 4.5). No new route answers a
  task, a session or a decision. `POST /api/super` only reads and writes the super agent's own files.
- No change to `Hub.levers`, `Hub.actions`, `Hub.task_levers`, `supervisor.*` or any task path. `server.task_row`,
  `Hub.snapshot` gain additive fields only.
- No answer to an observed chat (VS Code, terminal) from Console: its card only opens Console's read-only page of it.

## 2. Dependency ledger (plans 58 and 55 are plan only)

Every row is a symbol this plan calls or edits and is not in the code yet. "Doc" is where the contract is written.
When a name changes at build time, only the "Used in" task changes.

| Symbol or contract | Doc | Used in | Rides on an open decision | If it moves |
|---|---|---|---|---|
| `superagent.items(snap, by_id)`, item fields `key type id kind always project project_dir title label` | 58 3.3, Task 2 | 1, 2 | none | map in Task 1 step 0 |
| `superagent.items(snap, by_id)` is the only source of items; `superagent._event(values)` (private) builds a key's event hash | 58 3.3, R3 | 1 | R3 | `accept_items` calls it; one line |
| `superagent.sync(state, live, now) -> (new, back, changed)`, `queue(items, state, now, ranked) -> {"queue": [card], "later": [item]}`, `status(...) -> (ranked, why)`, `select_items` | 58 3.6, 3.8, 2.1a | 1 | R1 expiry, R2 coverage | Task 1 wrapper only |
| state functions `blank_state`, `load_state` (strict), `save_state(home, state)`, `append_log(home, record)`, `read_log`, `read_notes`, `read_orders`, `cut_notes`, `ORDERS_MAX`, `LINE_MAX` | 58 Task 1, 1.1a | 1, 3 | R4 (strict read) | Task 1 step 0 |
| state.json v1 keys `v n paused seen reviewed ann last digest claimed` | 58 3.5 | 1 | R3 `basis`, R4 claimed | Task 1 `upgrade` |
| `describe(item, task, row, view, level, timeout_s, now)` card fields (`ask options default left_s level supervisor source`) | 58 3.9, 58/03 `describe` | 1, 2 | none | Task 1 `_super_window`, Task 2 |
| the `incomplete` flag per item: plan 58 sets it when it builds an item's digest block (3.1a, R7), not in `describe`; GET carries it only if the pass stored it with the annotation. **Unverified until plan 58 is built**: Task 2 reads `item.get("incomplete")` and falls back to "" | 58 3.1a, R7 | 2 | R7 | Task 2 mapping line |
| `superagent.settings(cfg) -> (limits, errors)`, `blocked(...)`, `status(...)` | 58 3.2, 3.8, 58/01 | 1 | none | `Hub._super_inputs` |
| `superagent.policy_hash(cfg, folder)` (R3's hash of the effective orders, kind text and settings); `superagent.ORDERS_FILE`, `superagent.folder(home)` | 58 R3, 58/01:44, :118 | 3 | R3 | Task 3 tests (`policy_hash` is this plan's name for it; bind at build) |
| plan 58's GET describe loop: `super_view` already calls `Hub.actions(task)` once per live task item to describe it (3.7, 3.9, 06-routes "Describe all live items") | 58 3.7, 3.9, Task 6 | 2 | none | Task 2 keeps that `view` per key and never calls `actions` a second time |
| `Hub.super` (state dict), `super_clock`, `super_mono`, `_super_tick`, `_super_arm(now, events, at_once)`, `super_threads`, `super_wake` (`{"events": [(what, id)], ...}`), the storage-error flag, `super_view`, `super_action`, the tick's `events` list, `ended` tasks and required-save call, the pass completion's candidate state | 58 Tasks 5, 6 | 1, 2, 3 | D2, D6, R4, R9 | step 0 of Task 1 binds every name listed here: `Hub._super_inputs` binds the derived facts (ranked, error, off, capped, sorting, coverage, spend); the attributes themselves are read directly where section 2 of each task says, and renamed there |
| pass completion merges over the **live** `self.super` under `tlock`, not over the admission-time copy (58/05 "rebuild live items under tlock"; the immutable job holds handles and bases, not the state) | 58 Task 5 | 3 | R4 | Task 3 step 0 asserts it (`test_a_message_that_arrives_during_a_pass_waits_for_the_next`) |
| plan 58 test fixtures: `SuperHubTest` (`task`, `tick`, `drain`, `key`, `log`, `answer`, `gate`, `calls`, `now`), `make_task(hub, project, n, state, why, **extra)` (title `Task N`, project `proj`, `updated` T0), `DECISION`, `T0`; `tests.test_superagent.make_task`, `snap_of`; the golden table 4.2 data is inline in `test_golden_order`, **there is no fixture function** | 58/05:118-192, 58/02:185-228 | 1, 2, 3 | none | Task 1 builds `golden_queue_fixture` itself in `tests/test_superwin.py` from `tests.test_superagent.make_task` and `snap_of` (section 1.1) |
| `usage.load_super(folder)` (the ledger read plan 58's view and admission make) | 58 Task 4 | 1 | R5 | `_super_inputs` takes the spend figure as an argument; the snapshot path reads the cached one |
| `GET /api/super` fields (3.9) incl. `counts.queue`, `coverage`, `sorting`, `last`, `spend`, `orders`, `digest` | 58 3.9, 6.1 | 2, 5 | none | the page reads these names |
| `POST /api/super` `pause`, `resume`, `sort` and its 400 text `action: pause, resume or sort` | 58 3.10, 6.1 | 3, 6 | D6 | Task 3 edits the 400 text and its test |
| `Hub.reload_tuning`, `tuning.TUNING` super keys (group `super`, unit `lines`) | 58 3.2 | 7 | D9 | Task 7 reads `cfg.tuning` |
| plan 55: `acts(d)`, `actFind`, `actBtn`, `armBtn`, `runAction`, `pageHead`, `levelSeg`, `ACT_COPY`, `ARM` | 55 Task 1 | 5, 6 | D2 | Task 5/6 call them by these names |
| plan 55: `dockCard`, `iconBtn`, `barHtml`, `useHtml`, `taskShell`, `boxHint`, `stepFooter`, `taskMessageState`, `openActionForm`, `FORM_IDS` | 55 Task 2 | 5, 6 | D3 (buttons not drawn), D5 (Reject note) | Task 6 |
| plan 55: `sect`, `foldLine`, `planRow`, `svLine` | 55 Task 3 | 5 | none | Task 5 |
| plan 55 Task 4 (`projectGroups`, `listHtml`, `homePick`, `.p-pin`) | 55 Task 4 | 4 replaces | 55 D10, D11 | never built; Task 4 here builds the list on today's `chainHtml` |
| `RESUME_TEXT` (web) and its server twin | `app.js`, `server.py:1239` | 2 | none | Task 2 constant |

Open decisions of other plans this plan is **written against**:

- `[58 D2]` passes on at the upgrade (a): the first run after upgrade is `waiting` then `ranked`. If Fred chooses (b)
  (off until a limit is set) the first screen is `off`; nothing in this plan changes, the Models card is the way out.
- `[58 D6]` Sort by hand (a): the bar's Sort button posts it. `[58 D9]` no Models card in slice 1: Task 7 adds it.
- `[58 D10]` a STOP question without options is always forwarded (a): its card has no Later and says why.
- `[58 D11]` no `act`, no `order` (a): the cards cannot say "I did"; Undo is not drawn.
- `[55 D2 a]` button words come from `ACT_COPY`; `[55 D3 a]` the buttons `actions` does not serve are not drawn (D1 here);
  `[55 D5 a]` Reject takes the box's text; `[55 D10 a]` the list beyond the mock (D7 here); `[55 D11 a]` the queue spans
  all projects (D8 here); `[55 D13 a]` the observed page keeps `GET /api/levers`.
  [D1 b, Fred 2026-11-08] Plan 55 D3 was answered (b): its Task 0 serves `retry_up` and `run_instead`, and this plan's
  Task 0 serves `hint_dismiss`; the cards draw them (Task 2 note above `CARD_ACTS`). Plan 58 D4 was answered (b).

## 3. Facts checked 2026-11-08 (at `a627264`)

- **The answers already exist.** `Hub.actions(task)` (`server.py:1109`) returns, per task, `state`, `line`, `primary`,
  `bar`, `menu` and `message`, each action `{id, label, post, body, off, confirm}`; `post: ""` is a form (retry,
  handoff, add_step, edit_plan, reopen, start_next, review). The task levers post to `/api/task/<lever>` (the route
  table, `server.py:4363`), a decision option to `/api/task/message` with a deterministic `request_id`, an approve or
  reject to `/api/task/supervisor`. `Hub.task_message` (`server.py:1369`) refuses a body whose `target` differs from
  `message_availability(task)["target"]`. Nothing here is rebuilt.
- **A Console-run session without a task is not served by `actions`.** For a session row that is not a window run it
  returns the observed set (forks); for a window run it continues into `task["why"]`, which a session row does not
  carry. Loose window sessions (Needs you: stop, blocked, interrupted, stall) are answered today by the client with
  `needButtons`/`unblock` (`app.js:404`, `433`): `/api/continue` (answer, Resume), `/api/terminal`, `/api/done`.
  Task 2 serves the same four from `Hub.levers(sid)` so the page keeps no gate.
- **Console cannot focus another app's chat.** It does open things: a task folder and models.json through
  `os.startfile` (`server.py:4501`, `:4522`) and a terminal on its own runs (`runs.open_terminal`, `runs.py:396`;
  `/api/terminal` answers 404 `not a window run` for anything else, `server.py:4626`). No code can bring a VS Code or
  terminal chat to the front, so the mock's "Open in terminal / Open in VS Code" buttons need a capability that does not
  exist (D3). A later plan could add `code -r <folder>` (focus the project's VS Code window) as such a capability.
- **A chat task (plans 30, 42) is the common "needs you".** Its plan 58 kind is `chat`; when it is a window run its
  `Hub.actions` message mode is `answer` at a STOP question, so Write your own answer serves it (4.5); when its session
  is observed, `Hub.actions` returns the observed set with no `message` key (`server.py:1131`), so nothing answers it.
- **Gap found while planning: a finished task is not "needing Fred" today.** `server.task_row` (`server.py:4181`) puts a
  task in group `needs` only when it is waiting, stuck, asks a question, shows a hand-off hint, holds a handoff note
  or has a pending supervisor card; a `done` task is group `done` whether or not it was accepted. Plan 58's items are
  that set, so **no Accept card, and no Accept batch, can occur with slice 1's data**, yet the locked mock draws both
  (cards C1, C2, D and the batch `acc`). This plan closes the gap with an `accept` item kind (D10 a, section 4.1a) and
  asks Fred before building it, because it widens what reaches him.
- **The count.** `Hub.snapshot()` builds `counts.needs` from task rows and session rows in group `needs`
  (`server.py:575-580`); the header button reads `snap.counts.needs` (`app.js:2987`, hidden at 0); the tray reads
  `hub.snapshot()["counts"]` through `tray.look` (`tray.py:33`, `:182`), words "N needs you". The folded pill shows
  chips and a peek card, no count; it is not touched.
- **Free-text chain lines.** `chain.jsonl` lines carry a `why` written by many paths; nothing here parses them. Since
  you looked is built from events the tick sees (D5).
- **Tuning.** The Models page draws only keys listed in the web `TUNE` table and groups from `MGROUP`
  (`app.js:2358`, `:2376`); plan 58 adds the `super_*` keys to `tuning.TUNING` so the service already serves them.
- **The new-work target.** The composer's `project` variable (`app.js:88`, window.json through `/api/draft`) is the
  last project used; "New work goes to the last project used" needs no new state.
- **Windows animation effects** are on (memory 2026-10-12): motion follows them, as in the mock.

## 4. The contract

### 4.1 Files and places

```
console/superwin.py              new, pure (Tasks 1, 2): state v2 helpers, window queue, count, mode, controls, row
                                 line, log, messages, card actions filter, batch answer, rev
console/superagent.py            Task 1: blank_state v2, load_state reads v1 and v2 (+ check_extra), one import
console/server.py                Tasks 1-3: snapshot() `super`, Hub._super_inputs/_super_window/_super_card/_session_acts,
                                 tick log lines, super_view growth, super_action growth, one 400 text
console/tray.py                  Task 1: look() reads counts.for_you
web/app.js, web/style.css, web/index.html   Tasks 4-7 (class prefix sw-)
tests/test_superwin.py, tests/test_superwin_server.py   new; additions to test_tray, test_superagent, test_web, test_tuning
tests/live_super_check.py        new (Task 7), extends plan 55's Rig
```

`superwin.py` imports `redact` and `superagent`; it never imports `server` or `supervisor` (a test asserts it).

### 4.1a The `accept` item (D10 a)

`superwin.accept_items(snap, by_id)` adds one item for each task row of the snapshot that is `done`, not accepted, not a
chat and not already a `needs` row (a pending supervisor card keeps its own item). Kind `accept`, never always-forwarded.
Its key's event is a hash of the task id, the step count, the last verify's verdict and the attempt count, so Fred's
Accept (the task leaves the set), a Reopen (new steps) and a new verify change it and time does not. **No window of its
own**: the snapshot already hides a finished task after `DONE_DAYS` (`server.old_done`, `server.py:4154`), and that is
the only horizon; a key never leaves the set because time passed, so no "settled" line is written for a task Fred did
not touch (4.7). At the upgrade every unaccepted finish inside that horizon becomes an item once; the super agent can
batch them ("Accept all N"). `Hub._super_live(snap)` is `superagent.items(snap, self.tasks) + accept_items(snap,
self.tasks)`; every plan 58 call of `superagent.items` becomes that one call (tick, window, view, admission). The raw
`counts.needs` does not change; `for_you` can exceed it, which is why the header and the tray read `for_you`. Wake cost:
none added; plan 58 already wakes when a task ends (58 README 3.6 step 2). What changes is that the tray turns orange on
every unaccepted finish, and at level `auto` the queue is mostly Accept items until slice 3 may accept them.

### 4.2 `state.json` v2 (additive over plan 58 section 3.5)

```json
{"v": 2, "...": "plan 58's keys unchanged",
 "hand": {"<key>": 1800003600.0},
 "back": {"<key>": 12},
 "fwd": ["<key>"],
 "looked": 1800000000.0, "looked_cost": 3.21, "paused_at": null,
 "log": [{"ts": 1800000100.0, "g": "✓", "t": "Storyboard kit finished", "p": "MOTION STUDIO"}],
 "messages": [{"id": "uuid", "ts": 1800000100.0, "text": "fashion_packshots first"}]}
```

- `hand`: Later by hand, key to the epoch it returns (`now + 3600`). Always items cannot enter. Capped at 200.
- `back`: key to the pass counter `n` when the item came back (hand expiry or Bring back); the "back from Later" tag
  shows until a pass later than `n` has finished. `fwd`: keys Fred brought back; whatever a pass says, they stay forward.
- `looked`, `looked_cost`: when Fred last marked Since you looked as seen, and the tasks' total cost then (the spend
  line is the difference, never below 0). A missing value starts at the oldest `seen` time, else now.
- `log`: at most 60 lines, none older than 7 days, text masked and clipped to 160 characters. Written only by the tick
  and by the pass result (4.7). `messages`: at most 3, 500 characters each, masked; cleared by the pass that read them.
- `paused_at`: the epoch of the last Pause (null when not paused); the page reads "Paused by you at HH:MM" from it (the
  mock's copy, SW-8). Set by plan 58's pause branch, cleared by resume; one line each.
- `load_state` reads v1 (adds the defaults, `v` becomes 2 on the next save) and v2; a malformed new key blocks passes
  exactly like a malformed plan 58 key (R4: error, raw queue, no reset). The migration is one way: the first save after
  the upgrade writes `v: 2`, which plan 58-only code refuses as an unsupported version (its 1.1a); say so in the close.

### 4.3 The one number

Code decides it once: `for_you = the items inside the queue cards` (a batch counts each member). The window draws every
count from one source at a time:

| Surface | Reads | Test |
|---|---|---|
| header button, super agent row, page pill, For you sub-line, project lines, bar | the view's `counts.queue` and `by_project` when `view.rev === snap.super.rev`, or while a refetch is in flight and the view is under 30 s old; else `snap.super.for_you` and `snap.super.by_project` | Task 1, 4, 5 |
| tray tooltip | `snap.counts.for_you` (equals `snap.super.for_you`) | Task 1 |
| `GET /api/super` `counts.queue` | the same function over described items | Task 2 |

`snapshot()` computes `snap["super"]` **cheaply and without a lock of its own** (live items described with `view={}`,
the queue, no `Hub.actions`, no brief, file or ledger read): `{rev, mode, for_you, later, line, by_project, marks}`;
`marks` maps a task or session id to `["queue"]` or `["later", "HH:MM"]`. It reads `Hub.super_pub`, a published copy of
the state: every path that changes `self.super` under `tlock` (plan 58's tick save, the pass result save, this plan's
`_super_commit`) ends with `self._super_publish()`, which replaces the reference with a deep copy and caches the ledger
figure the tick read. `snapshot()` never takes `tlock` (today it holds `self.lock` only, briefly, `server.py:551-583`;
GET /api/state, the long poll and the tray must not queue behind task transactions). `rev` is a hash of the live keys
with their stored advice (the **raw** `ann`, in both paths: plan 58 R3's stale-advice filter in GET is applied to the
cards, never to the `rev` basis), Fred's hour, the back markers, the mode and the log tail; it never moves with age,
cost or time left, so the cheap and the full computation agree on it. `GET /api/super` computes the same `rev` and the
accurate counts (evidence-complete, auto-default aware, batches validated, stale advice filtered). The two numbers can
differ by an item for at most one tick (5 s) in two cases: an item's Later validity turned on evidence only the full
view reads (`incomplete`), or GET filtered a stale annotation that the next tick removes durably. The window then shows
the view's number, the tray the snapshot's, and the tick closes it. When the super machinery fails, `for_you` falls
back to the raw `counts.needs` and the mode is `error`: the count is never below what needs Fred (it drops the `accept`
items and shows Fred's Later items again, so it only ever jumps up). The window refetches `GET /api/super` when
`snap.super.rev` differs from the view's, after every action of its own, and every 30 s while the page shows (served
`off` reasons and `left_s` age). `renderBoard` starts the refetch **before** it draws the header, so a stale snapshot
number never shows for a frame while the view is fresh.

### 4.4 `GET /api/super` additions (plan 58 3.9 keeps every field)

Top level: `rev`, `mode` (`ranked partial sorting paused off capped failed waiting error`), `controls`
(`{pause, resume, sort}`, each `{label, off}` or null), `since` (`{at, lines[{ts g t p tm}], spent}`), `order_lines`
(the orders a pass reads, comments dropped), `by_project`, `paused_at` (epoch or null, 4.2); `counts` keeps plan 58's
four keys and `counts.queue` is the one number.

Per item: `back`, `incomplete` (a reason or ""), `stay` (why it has no Later, or ""), `observed`, `path`, `open {kind id step}`, `facts [[text, "ok"|"h"]]`,
`acts {state primary bar menu message}` (the served actions, filtered by an allowlist per state, `off` kept),
`own {mode post body request_id off} | null` (Write your own answer: where the box posts), and per batch card `answer {id label} | null`. A Later entry adds
`by` (`sa` or `you`) and `until` (local `YYYY-MM-DDTHH:MM`). The page never recomputes a gate: a button exists because
`acts` lists it and is enabled because its `off` is "".

### 4.5 Which route answers which card (the heart of the plan)

Every row is an existing route; `off` comes from the gate that owns it. "Opens" means the click selects the task (or
chat) and, where noted, opens the form the existing page already has; nothing is posted.

| Card kind (plan 58 `kind`) | Served state | Buttons (served ids) | Route and body | Gate |
|---|---|---|---|---|
| decision with options | `decision` | one row per option; Confirm `<key>`. The served default is preselected; a decision **without a default** (always-forwarded, plan 58 3.4) preselects nothing, marks no row "default" and keeps Confirm off until Fred picks a row | `POST /api/task/message` `{task, mode: "answer", text, target, request_id}` as served | `Hub.task_message`, `message_availability` |
| decision without options, question | `decision` | Write your own answer | same route, text from the box, `request_id` a new UUID, `target` from `acts.message` | same |
| chat task (plans 30, 42) at a STOP question, Console run | `running` or `decision` | Write your own answer (`acts.message.mode` is `answer`) | same route | same; an observed chat task has no `message` and only opens |
| plan to confirm (`hold`) | `plan_ready` | Confirm | `POST /api/task/confirm` `{task}` | `task_levers.confirm` |
| held: Fable | `hold` | Confirm Fable (two clicks) | `POST /api/task/confirm` | same |
| held: pace | `hold` | Run anyway | `POST /api/task/confirm` | same |
| held: replanned | `hold` | Confirm, Keep old plan | `POST /api/task/confirm`, `POST /api/task/keep` | same |
| held: usage limit | `hold` | Retry on a model (opens the task's retry form) | none (a form) | `retry` |
| supervisor suggestion | `suggestion` | Approve; Reject or Dismiss | `POST /api/task/supervisor` `{task, wake, action}` | `Hub.supervisor_action` |
| done, to accept | `done` | Accept; Reopen (opens the task, box focused) | `POST /api/task/accept` | `task_levers.accept` |
| failed twice, stuck | `failed_twice`, `stuck` | Retry on a model (opens the retry form), Accept step result, Finish | none; `POST /api/task/stepdone`; `POST /api/task/done` (two clicks) | `retry`, `stepdone`, `done` |
| handed with a note | `handed` | Start next task | `POST /api/task/resume` `{task: follow-up}`, or opens the next-step form | `task_levers.resume` |
| hand-off hint | `running` | Hand off now (opens the Hand off form; served in the card's `bar`, since a card draws `primary` and `bar` only) | none (a form) | `handoff_available` |
| Console run, STOP question | session | Write your own answer | `POST /api/continue` `{session, text}` | `Hub.levers.continue` |
| Console run, interrupted | session | Resume | `POST /api/continue` `{session, text: RESUME_TEXT}` | `Hub.levers.continue` |
| Console run, blocked | session | Open in terminal | `POST /api/terminal` `{session}` | `Hub.levers.terminal` |
| Console run, stall | session | Mark done | `POST /api/done` `{session}` | the route |
| Console run, failed, verify FAIL, red gauge, handed | session | Open | none | |
| **observed chat** (VS Code, terminal) | observed | Open (Console's read-only page) | none | answered in its own app |

Every card also carries Open (`O`), Later (`S`) unless it stays here, and the super agent's suggestion block. A card
the super agent could not check (`incomplete`) makes Open the primary and every answer plain (design note 5).

### 4.6 Batch cards

A batch card exists only where plan 58's R8 made one (identical kind, level, question, options, default and answer
action). Its answer button exists only when `answer` is set: every member serves the same enabled, non-confirm
`accept` (D2 a). The click posts each member's own served action in order, one request each, through that member's own
gate. A member that refuses stays in the queue with its reason in the acknowledgement ("Accepted 2 of 3. Plan 56: <reason>").
Review one by one splits the card for this window session only (a set of member keys, not stored). A batch never holds
an always item (plan 58); an unranked state has no batch.

### 4.7 Later by hand, Bring back, Since you looked

- **Later** (`S`, or the link): `POST /api/super {action: "later", keys}`. One fixed hour; the card leaves; Later shows
  `You put it later.` and `Back HH:MM`. An item that stays here (an always item, or a decision whose default is about to be taken at `auto`; code's `stay_reason`)
  answers 409 `stays here: <reason>`; the card shows that string and no Later link. It is separate from the super agent's Later: Fred's hour holds in every mode, the
  super agent's Later returns to For you when sorting is paused, off, capped, failed or in error.
- **Bring back**: `{action: "bring_back", keys}`: from Fred's Later (the key leaves `hand`) or the super agent's (its
  annotation becomes forward); either way the key joins `fwd` and carries `back` until a later pass finishes.
- **Expiry**: a hand entry whose hour passed returns once (`back`), and arms the same wake as plan 58's expired Later.
- **Since you looked**: the tick appends a line when a task ends (finished, failed or stuck), when a key leaves the live
  set ("<task>: <kind> settled": answered here, in VS Code, in a terminal, or by Console at `auto`), and when a pass
  ends ("Super agent sorted 10 items: 8 for you, 2 later" or "sort failed: <error>"). A key that leaves while the same
  subject is still live under a new key (the state changed: a Reopen, a new attempt, a re-asked question) writes no
  "settled" line: nothing was settled. The spend line is the tasks' cost since `looked_cost` plus the super agent's day
  figure. Mark seen: `{action: "seen"}` sets `looked`, `looked_cost` and empties the page's list (the log keeps its lines
  until they age out).

### 4.8 The one box (design section 6; code routes, no model)

| Selected | Chip | Enter does |
|---|---|---|
| nothing, or a project row | `New work · <last project used>` | the composer's own Prep (`doPrep`) with the box's text as the shared draft (D11) |
| the super agent row | `◆ Super agent` | `POST /api/super {action: "message", text}` (4.9) |
| Write your own answer on a card | `Answer · <task>` (✕ and Esc cancel) | the card's served route: `/api/task/message` (answer or next) or `/api/continue` |
| a task or a step | `Task · <title>` | plan 55's box, unchanged |
| an observed chat | `Read only · <app> chat`, input off | nothing |

### 4.9 A message to the super agent

`{action: "message", text}`: 1 to 500 characters (longer is refused, never cut), masked, kept in `state.messages` (at most 3 wait: 409 `3 messages
wait for the next sort`). Accepted while the mode is `ranked`, `partial`, `sorting` or `waiting`: it arms one wake at
once. While `paused` or `failed` it is kept without a wake ("Kept: the super agent reads it at the next sort", as the
mock); in `off`, `capped` and `error` the input is off. The next pass's prompt gets a block `Messages from the user since
the last sort` after the orders, delimited as untrusted evidence (it does not outrank the orders file or any code gate;
the code-owned schema reminder says so); the pass that ends ok clears the messages it read. The reply is the pass's
digest and the log line `Super agent, to "<first 60 characters>": noted for the next sorts. To keep it, add it to your
orders.` (D4 a). Slice 3 can make it reply and propose an order. **Binding requirement on plan 58's completion** (Task 3
step 0 asserts it): the pass publishes its result by merging into the **live** `self.super` under `tlock`, never by
replacing it with a copy taken at admission; a message, a Later, a Bring back or a Mark seen written while the pass ran
must survive, and `drop_messages` removes only the ids the pass read (`job["msgs"]`).

### 4.10 Modes (the mock's eight states and two it does not draw)

| Mode | When (code, first that holds) | Cards | Row line | Note on the page |
|---|---|---|---|---|
| `error` | a settings error, a storage error or no `claude.exe` | unranked | `cannot sort · oldest first` | red note with the reason; no Sort |
| `paused` | Pause | unranked | `paused · oldest first · N running` | "Paused by you at HH:MM." (`paused_at`, 4.2) Resume |
| `off` | `super_day_usd` or `super_pass_usd` is 0 | unranked | `off · oldest first` | "The super agent is off. Its daily limit is $0." Models settings |
| `capped` | today's settled plus held spend reached the day limit | unranked | `today's limit reached · oldest first` | "Today's limit of $X is reached." Models settings |
| `sorting` | a pass is running | as before (ranked keeps its advice) | `sorting N items · N running` | "Sorting N items. Cards keep their last recommendations until it ends." |
| `waiting` | items but no pass yet | unranked | `waiting to sort · N running` | "The first sort starts in a moment." |
| `failed` | the last pass failed | unranked | `last sort failed · oldest first` | red note: the error; Sort again |
| `partial` | ranked and some live item was never reviewed | ranked | `reviewed X of Y · N running` | "Recommendations cover X of Y items." tags "not reviewed yet" |
| `ranked` | otherwise | ranked | `N running · M later · sorted HH:MM` | none |

Unranked keeps every action (design note 6): the cards keep options and buttons; recommendations and batches go; the
super agent's own Later items come back into For you; Fred's hour stays in Later.

## 5. Design lock (the mock to numbered UI decisions)

Locked by Fred, 2026-11-08: `design/rework/locked/super-agent.html` (explored copy `design/rework/explored/f-super-agent.html`).
Console Cells tokens, type and the cell motif are unchanged; orange still means "for you" and nothing else. New CSS
classes carry the prefix `sw-` (the mock's `.row .note .btn .lbl` collide with the app's). Slice 3 to 5 scenes
(`f-acts`, `f-job`, `f-jobtask`, `f-merge`) are not built.

### 5.1 Decisions

| # | Topic | Taken | Task |
|---|---|---|---|
| SW-1 | The super agent row | First row of the list, always present: `◆ Super agent`, `N for you` (orange when N > 0, muted at 0), one code-built line (4.10). Selecting it makes the box talk to the super agent; selecting again leaves it. `aria-current` on the home pane. | 4 |
| SW-2 | One count | Header button `N for you` (muted at 0, never hidden), row, page pill, For you sub-line, project lines and the tray tooltip read one number; a batch counts each member (4.3). | 1, 4 |
| SW-3 | The page is the home pane | Shown with nothing selected, with the super agent row or a project row selected; eyebrow `All projects`, title `Super agent`, pill by mode, facts (Reviewed X of Y, Order oldest first, Last sorted; no "Last good sort", X8), cost right (`$ super agent today`, `of $1.00 today` when capped). Plan 55's `pageHead` (`costSub` is its field). | 5 |
| SW-4 | Four sections | For you, Later, Since you looked, Orders, plan 55's `sect` pattern. | 5 |
| SW-5 | Card anatomy | Path `project › task`, tags, `kind · age`; the ask; the facts code knows; options with the default; a neutral block headed `Super agent suggests`; links (Open, Write your own answer, Later); buttons with one orange primary. The current card is orange-tinted like the dock card; the others fold to ask plus one `◆` line. | 5 |
| SW-6 | What cannot wait says so | "Stays here: <reason>" replaces the Later link on an always item and on a decision whose default is about to be taken (`the default is taken at HH:MM`); tags `always yours`, `default at HH:MM`. | 5, 6 |
| SW-7 | A card it could not check | No suggestion block: `Super agent · no recommendation` and the reason; Open the task is the primary, Accept stays plain. | 5 |
| SW-8 | Unranked keeps every action | The five unranked modes differ only in their note and row line (4.10). | 5, 7 |
| SW-9 | Later | Count and every reason; `◆` marks the super agent's; `Back HH:MM`; Bring back; empty text "Nothing in Later." or the unranked variant. | 5, 6 |
| SW-10 | Since you looked | Lines (glyph, text, time, project), the spend line, Mark seen; empty text names the mark time. No Undo (slice 3). | 5, 6 |
| SW-11 | Orders | The file's lines as a numbered list; Edit orders opens a textarea with Cancel and Save orders. No proposal block (slice 3). | 5, 6 |
| SW-12 | Roll-up list | A quiet project is one line (`CLAUDE CONSOLE · 2 tasks · 1 paused` as `N running · N paused · N done · N later · N chats`); a project with something for you opens and shows those rows plus `+ N more: ...`; steps only under the selected task (changes plan 55 UI-2); observed chats stay dashed rows; a project row selects as the New work target and toggles open. | 4 |
| SW-13 | The box | The chip always names where Enter goes (4.8); placeholders per mode; the sent line under the page; Esc cancels an answer. | 6 |
| SW-14 | The bar on the home pane | Left: `N sorts · $ today`; right: Pause or Resume, then Sort now / Sorting / Sort again, with the served reason as the tooltip when off. | 6 |
| SW-15 | Keys | `J K` move, `1`-`4` pick an option, `Enter` confirms, `S` Later, `O` open, `Esc` back. Only on the home pane, never while typing, never with a modifier, no motion on keyboard moves. | 5, 6 |
| SW-16 | Sorting, partial, empty | The notes of 4.10; "Nothing for you." with the running count and the next Later return; a pass running shows `Sorting N items`. | 5, 7 |
| SW-17 | Widths | 900 px two columns; under 700 px container width one column with `‹ All work`; 400 and 340 px as the mock. | 7 |
| SW-18 | Motion | Dials ENERGY 2, RHYTHM 2, MOTION 1: running marks and button presses only; all off with reduced motion or Windows animation effects off. | 7 |

### 5.2 Where this plan departs from the mock, and why

| # | Mock | Plan | Why |
|---|---|---|---|
| X1 | Observed card: `Open in terminal` / `Open in VS Code`, then the card leaves 1.6 s later | `Open` shows Console's read-only page of the chat and the card says `Answer it in VS Code`; the card leaves when the hook reports the chat moved on | no route opens another app (section 3); the rule "an observed chat is never answered from Console" holds (D3) |
| X2 | An answered card leaves at once | It shows `Sent` with its buttons off and leaves when the service says the item left (usually under 2 s); focus moves then | the count is one number from the service; an optimistic removal would make header and page disagree |
| X3 | `Retry on a stronger model`, `Run on opus instead`, `Let it continue` | Not drawn; the served `Retry on a model` opens the task's retry form | `actions` does not serve them (plan 55 D3 a, D1 here) |
| X4 | `You chose b` in Since you looked | `<task>: <kind> settled` | the tick cannot know who or what answered (D5) |
| X5 | Undo, proposed order | Not drawn | slice 3 |
| X6 | Job and merge rows | Not drawn | slices 4 and 5 |
| X7 | One box | The left composer (files, effort, draft) stays; the page box's `New work` chip hands its text to the same `doPrep` and the two share one draft | the composer carries attachments and the effort slider the mock does not draw (D11) |
| X8 | `Last good sort` fact, `Paused by you at 13:40` | `Paused by you at HH:MM` is drawn (`paused_at`, one float in the v2 state this plan adds anyway); the `Last good sort` fact is not drawn | the state keeps only the last pass; a last-good time would be a second record for one fact nobody acts on |

### 5.3 Unshown states this plan draws (shown to Fred as screenshots at Task 7)

`waiting` (first sort), `error` (settings, storage, no `claude.exe`), the `Sent` card, a message kept while paused or
failed, a failed batch member, a session card of a Console run, a card whose served action is off (grey with the reason
as its tooltip), the empty Later and Since you looked in unranked modes.

## 6. Plan 55 and the list

Plan 55 Task 4 (`projectGroups`, `listHtml`, `homePick`, the `Needs you` pin, `p-pin`) is replaced by Task 4 here: the
pin becomes the super agent row, `homePick` (plan 38 U8: open the first pinned task) is never built because the home pane is
the page, and the
project group keeps plan 55 D10 a (live rows, today's done rows, `Done earlier · N`, `Older`, empty chats behind the
header menu) inside an opened project (D7). Plan 55's `needsec` id moves to the row, so the header button's scroll
becomes "select the super agent row" (`go("needs")`). Plan 55 UI-2 (steps under every running row) narrows to steps
under the selected task. Tasks 5 to 7 of plan 55 build unchanged after this plan.

## 7. Decisions for Fred

Recommended option first; the plan is written for it. The brainstorm closed D1 to D6 and D-a to D-f; plan 58 left D1 to
D12; these are what the window adds.

| # | Question | (a) recommended | (b) | Taken |
|---|---|---|---|---|
| D1 | The one-click buttons the mock draws that `actions` does not serve: `Retry on a stronger model`, `Run on opus instead`, `Let it continue` | not drawn; the card draws the served `Retry on a model`, which opens the task's retry form (plan 55 D3 a); the three can be added later as served actions with no web change | a Task 0 adds `retry_up` and `run_instead` (a `model: "up"` on the retry route) and a dismiss for hand-off hints to `Hub.actions`, then the cards draw them (plan 55 D3 b) | (b) |
| D2 | What a batch button may answer | accept only (`BATCH_ANSWERS`); other batches show as one card with Review one by one | any identical served primary: the same option of identical decisions, identical approvals | (a) |
| D3 | An observed chat's card | `Open` = Console's read-only page, plus `Answer it in VS Code` | a later plan adds a way to focus the other app (a new capability) and the mock's `Open in terminal` / `Open in VS Code` | (a) |
| D4 | A message to the super agent | kept as a note for the next sort(s), read once, no reply text, no order made; the log line says so | no box on the super agent row until slice 3 can reply | (a) |
| D5 | Since you looked wording | code-known events: finished, failed, settled, sorted, spend | also write a line for each answer made through a card (`You chose b`), a write step in every answer path | (a) |
| D6 | Edit orders in the window | yes, `POST /api/super {orders}`: Fred's own write to `super/orders.md`, durable before the answer | file only; the section lists the lines and names the file | (a) |
| D7 | The rest of the list under the roll-up (Done today, Done earlier, Older, Select done tasks, empty chats) | plan 55 D10 a inside each opened project; the quiet line counts `N done` | only what the mock draws; done tasks reachable by `+ N more` alone | (a) |
| D8 | The queue and the project scope filter | the queue spans all projects (plan 55 D11 a); the scope filters the project groups only | the queue and its count follow the scope | (a) |
| D9 | The word on the header button and in the tray | `N for you` (the mock's word) in both; the tray tooltip reads `2 for you, 1 working` | change the button only; the tray keeps `need you` | (a) |
| D10 | Do finished tasks waiting for Accept reach the queue (the mock's Accept cards and the Accept batch)? | yes: every finished task the snapshot still shows (`DONE_DAYS`) and that is not accepted becomes an `accept` item (4.1a); no window of its own, so no item ever leaves because time passed and no false "settled" line is written | no: the queue holds only what plan 58 counts (waiting, stuck, asks, hints, handoffs, suggestions); Accept stays on the task page, and Accept cards wait for jobs (slice 4) | (a) |
| D11 | The New work box | the page box's `New work` chip is a second entry to the existing composer: its text becomes the shared draft and `doPrep` runs (files and effort stay in the left composer, which stays visible) | the left composer moves into the page box (attachments, effort and draft re-homed; a bigger change to plan 48's moment 1) | (a) |

Decided by Fred, 2026-11-08:

- D10: (a) finished tasks waiting for Accept become accept items, no time window.
- D1: (b) retry_up and run_instead from plan 55 Task 0 (55 D3 b); this plan's Task 0 serves hint_dismiss (Let it continue).
- D11: (a) the New work chip is a second entry to the composer; both inputs stay visible (the review's one-visible-input variant not taken).
- D2: (a) a batch button answers Accept only.
- D3: (a) Open shows Console's read-only page; the card says Answer it in VS Code.
- D4: (a) a message is a note for the next sort, read once, no reply.
- D5: (a) Since you looked lists code-known events only.
- D6: (a) orders edited in the window through POST /api/super {orders}.
- D7: (a) plan 55 D10 a inside each opened project; settled by Fred's plan 55 D10 answer.
- D8: (a) the queue spans all projects; settled by Fred's plan 55 D11 answer.
- D9: (a) N for you on the header button and in the tray.

Review notes (2026-11-08, plan review before the build; Fred decides):

- **D1**: the review recommends a (b)-lite: a Task 0 that adds `retry_up` alone (a server `model: "up"` on the existing
  retry route, plan 55 4.2 already names it) and leaves `run_instead` and the hint dismiss for later. Without it every
  stuck and failed-twice card needs the task page for its Retry, which breaks "a day's items without a task page" for
  the most frequent red card. If Fred takes it, Task 2's `CARD_ACTS` for `failed_twice` and `stuck` gains `retry_up` in
  `primary` and the card draws it as the orange primary; nothing else changes.
- **D11**: the review recommends (a) with **one visible text input at a time**: while the home pane shows, the left
  composer's textarea collapses to its chips, effort and files strip and the page box is the input; off the home pane
  the composer returns. Two editable inputs bound to one draft confuse focus and Enter. The mock has one box, so this
  goes back to Fred rather than silently changing the mock.
- **D10** is written for (a) as corrected above (no 24 h window).

## 8. Verification at the end of every task

1. The task's tests were written first and failed for the intended reason before the code.
2. Focused: `py -m unittest tests.test_superwin` (and `tests.test_superwin_server`, `tests.test_web` per task).
3. Full: `py -m unittest discover -s tests` in the background, read the finished output; report the real count (the
   baseline is 1167 plus plans 55 and 58 once built; do not quote the baseline as the result).
4. `node --check web/app.js` after any web edit.
5. `git diff --stat` shows only the task's files; stage explicit paths; the commit message is the one the task names.
6. No test calls a paid provider, touches port 47770 or writes `~/.claude`: scratch `CC_CONSOLE_HOME`, a scratch Hub
   folder, `tests/fake_claude.py`, `superagent.run` patched. Clocks frozen at `T0 = 1_800_000_000.0` (2027).
7. Web tasks also run `py -m tests.live_super_check` (Task 7 creates it; Tasks 4 to 6 add their checks to it).

## 9. Risks

- **Planned against documents.** Plans 58 and 55 may change before they are built. Mitigation: section 2 lists every
  name; Task 1 step 0 binds the derived facts in one method (`Hub._super_inputs`) and maps the plan 58 attributes the
  tasks read directly (`self.super`, `super_clock`, `_super_arm`, `super_wake`, `super_threads`, the tick's `events` and
  `ended`, the completion's candidate) where each task names them; the web names of plan 55 are called, never copied.
- **GET cost and lock scope.** `Hub.actions` runs **once per live item** (plan 58's describe loop; Task 2 reuses that
  view and never calls it again), each call reading several gates: `levers` twice (`actions` and
  `message_availability`, `server.py:1113`, `:1335`), `os.path.isdir`, `handoff_ready`'s stat, `recovery`'s process
  probe. Those calls run **outside `tlock`** on a copied item list, as GET /api/task does today (58 README 2); only the
  copy of state and items is taken under it. Task 2 measures `GET /api/super` with 30 live items on a scratch Hub as
  soon as the cards serve (budget 150 ms at 30; Task 8 repeats it with 65). If it is over, a read-only
  `GET /api/super/card?key=` serves the current card lazily; no gate moves.
- **A stale answer.** A card is a snapshot. Every action posts keys the service re-checks (`404 unknown item`), the
  routes re-check their own gates, and a `rev` mismatch refetches before the next key press.
- **Filtering something important.** Later is counted on the row and the page, its reasons are in sight, always items
  cannot enter it, Fred's hour is one fixed hour, and the unranked modes put the super agent's Later back.
- **Two count sources.** The window reads one source at a time (4.3): the view when its `rev` matches the snapshot's or a refetch is in flight, else the snapshot. A test fails if two window surfaces differ; the tray may lag the window by one tick in the two cases 4.3 names.
- **`snapshot()` latency.** `snap["super"]` reads the published copy `Hub.super_pub` and takes no `tlock`; a test fails if `snapshot()` acquires it or reads the ledger.
- **Key capture.** Keys act only with focus outside input, textarea, select and contenteditable, on the home pane, with
  no modifier; an armed two-click button disarms on any key.

## 10. Status and history

- 2026-11-08: written (plan only) from the locked mock and the documented contracts of plans 58 and 55, against
  `a627264`; the seams read in `server.py` (`actions`, `levers`, `task_message`, `snapshot`, `task_row`), `app.js`
  (`needButtons`, `unblock`, the Models Tuning card, the header count), `tray.py` and `tuning.py`. Decisions D1 to D11
  open for Fred; no product file touched.
- 2026-11-08: reviewed (plan only, same day). Fixed: one `Hub.actions` call per item, outside `tlock` (Task 2);
  `snapshot()` reads a published state copy and takes no lock, reads no ledger (Task 1, `Hub.super_pub`); the hand-off
  hint's form in the card's `bar`; a decision without a default preselects nothing; `chat` tasks answer in place; the
  `accept` item has no 24 h window and a changed key writes no "settled" line (D10 wording); `paused_at` (X8); the
  completion-merges-live-state requirement (4.9); the ledger rows of section 2 (fixtures, `policy_hash`, `incomplete`,
  `settings`, `load_super`); the honest binding statement (section 9); seven tests that could not pass as written
  (Tasks 2, 4, 5, 7, 8). Review notes under section 7 for D1 and D11. Still plan only.
- 2026-11-09: amended by the chat design (BRAINSTORM D19): 4.9, Task 3's `message` action and Task 6's super agent
  box mode are not built here; D4 superseded. Docs only.
