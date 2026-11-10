# Agent prompts: build plan 59, the super agent window (2026-11-08)

Written for: build agents (fresh Claude Code sessions) that start with no memory of this chat. Fred pastes the SHARED
RULES block of `plans/next-agent-prompts-2026-11-07.md`, then one prompt below. Each prompt is self-contained apart
from those rules.

Build correction, 2026-11-09: plan 58 D1 is now (b). Prompt A may build and test on scratch services before plan
52's live check. That live check remains open; this exception does not authorize a production restart or paid
acceptance. The recorded choices below replace Prompt A's answer placeholder.

State at `69fef99` plus the uncommitted review fixes in `plans/59-super-agent-window/` (commit them first:
`docs: plan 59 review fixes`):

- Plan 59 is written and reviewed (README section 10, second history line). Plan only. It is written against the
  **documented** contracts of plans 58 and 55, which are plan only too.
- The build gates (README "The build waits") are: plan 58 built with its Task 7 live check passed and D2, D6, D9, D10
  closed; plan 55 Tasks 1 to 3 built with its Stop 1 passed; Fred's answers to plan 59 section 7 (or the recommended
  column). **Do not start plan 59's Prompts 1 or 2 before all three hold.** Prompt 0 checks them.
- Fred's open calls on plan 59: D1 (the review recommends b-lite: a Task 0 that adds `retry_up` to `Hub.actions`),
  D11 (the review recommends one visible text input at a time). The plan is written for the (a) column; the review
  notes under section 7 say what changes if Fred takes the recommendation.

Prompt 0 ran on 2026-11-08 against `69fef99`: **NO-GO**, correctly. `console/superagent.py`, `tests/test_superagent_server.py`,
`Hub.super_view`, `/api/super` and `usage.load_super` do not exist; `web/app.js` has none of plan 55's parts. Plans 58
and 55 are plan only. So the order is now:

1. Use the recorded answers in `plans/decisions-2026-11-08.md`: plan 58 D1 is now (b), so Prompt A may build on
   scratch services while plan 52's live check stays open. Plan 58 D2 to D12 and plan 55 D1 to D14 are closed.
2. Prompt A (plan 58 Tasks 1 to 6, server) and Prompt B (plan 55 Tasks 1 to 3, web) in parallel, each in its own git
   worktree: their files overlap only in `web/app.js` (plan 58 Task 4 adds one Usage block call; plan 55 adds the seam)
   and `console/server.py` (plan 58's super section; plan 55 Task 3's one read field). Merge A first, then B, with
   anchored hunks.
3. Fred: finish plan 52's live check, then plan 58 Task 7 (real passes, its own cost figure) and plan 55 Stop 1
   (screenshots after Task 2). Plan 55 Stop 2 is skipped (Task 4 is replaced by plan 59).
4. Prompt 0 again, then Prompt 1 (plan 59 server), then Prompt 2 (plan 59 window, ends at Stop 1). Task 8 is Fred's.

Fred only: the live checks and stops above; every plan's decisions; the close of each plan.

---

## PROMPT D: the decision session (docs only; Sonnet; interactive, Fred present)

Goal: close every decision the builds above wait on, one question at a time, and write each answer where the plan
says it goes. You change plan documents only: no product code, no test, no config. Fred is at the keyboard; this is
a conversation, not a batch job.

Read first, in this order: `CLAUDE.md`; `PLAN.md` rows 52, 55, 58, 59 and the History tail; `plans/next-agent-prompts-
2026-11-08-plan59.md` (this file: the order and what each build waits on); `plans/58-super-agent/README.md` section 5
and `08-review-and-jev.md` section 4 (D12); `plans/55-autopilot-ui/README.md` "Decisions" table and sections 4.2, 4.3,
5; `plans/59-super-agent-window/README.md` section 7 with its review notes and section 5.2 (X1 to X8);
`design/brainstorm/2026-11-08-super-agent.md` section 11 (what is already decided: do not reopen D1 to D6, D-a to D-f).
Memory for taste: Fred chose Haiku reads, Sonnet writes, Opus thinks, Fable only by confirm; orange means "for you";
"keep it small"; no emojis, no em-dashes.

The decisions to close, in this order (dependencies first):

1. Gate facts, not choices: is plan 52's live check done (PLAN.md row 52 still says open)? Is the service restarted
   on plan 54? Record what Fred says in the PLAN.md row only if he says it happened, with the date.
2. Plan 58, D1 to D12 (12 rows): D1 (when to build) and D2 (spend at the upgrade) first, since they gate the rest and
   the money; D12 (JEV) last, default no.
3. Plan 55, D1 to D14: D1 (task order), D3 (buttons `actions` does not serve) and D14 (unshown states) first; D10 and
   D11 are moot for the list (plan 59 Task 4 replaces plan 55 Task 4) but still answer them as the roll-up's inner
   grouping (plan 59 D7 and D8 restate them): say so when you ask.
4. Plan 59, D1 to D11: D10 first (it widens what reaches Fred), then D1 and D11 (the review recommends the (b)-lite
   and the one-visible-input variant: present both columns and the review note, no steering beyond the plan's own
   words), then the rest. X8 is already applied (`paused_at`); X1 to X7 need no answer unless Fred wants the mock changed.

How to ask: one decision per question. Each question carries, in at most eight lines: the question in Fred's words
(not the table's jargon), what (a) and (b) each cost or save in use (clicks, money, risk, what he sees), the plan's
recommendation and the review's where it differs, and what else changes with each answer (the task file lines the
plan marks `[Dn]`, other decisions it settles or reopens). Offer "recommended" and "other" as the two options plus a
free answer. Skip a question when an earlier answer settles it, and say which answer did. Never ask two things at
once; never ask what the brainstorm already decided; never ask about the mock's visuals (locked). If Fred's answer is
neither (a) nor (b), restate it as a new option (c) in his words and confirm it before writing. If Fred asks "what
would you do", answer in two lines with the reason, then ask again.

How to write each answer, right after Fred confirms it (so a stopped session loses nothing):

- In the plan's README decision table, append a column `Taken` with `(a)`, `(b)` or `(c)` per row, and under the table
  a block `Decided by Fred, <date>` with one line per decision: `D<n>: <choice>. <his reason in one clause, if he gave
  one>.` Change the README's Status line from "decisions open for Fred" to "decisions closed <date>" when the last one
  lands.
- In the task files, where the plan marks lines `[Dn]` for the other answer, apply the chosen option's lines (the
  plan says exactly what changes; make only those edits, anchored by the quoted line). When (c) is chosen, write the
  new line in the plan's own voice and tag it `[Dn c, Fred <date>]`.
- In `PLAN.md`, the plan's row: "D1-D11 open for Fred" becomes "D1-D11 closed <date>"; one History line per plan.
- Keep a running list `plans/decisions-<date>.md` of every answer in order (plan, decision, choice, reason), so the
  build prompts can paste it. Write it incrementally.

Commit after each plan's set is closed, docs only, explicit paths, your lines only (other chats edit `PLAN.md`):
`docs: plan 58 decisions closed (Fred, <date>)` and the same for 55 and 59.

Do not: build anything, change the locked mocks, reopen the brainstorm's decisions, invent a decision the plans do not
list, decide for Fred when he hesitates (park it in the running list as "open", move on, come back at the end), or
start the build prompts. If a decision needs a fact you cannot read in the repo (a cost, a date, a live-check result),
ask Fred for the fact first, as its own question.

Done when: every row of the three tables has a `Taken` value or is parked as open with Fred's word, the task files
carry the chosen lines, `PLAN.md` rows and History say closed, `plans/decisions-<date>.md` lists everything, and the
report under 30 lines names the parked decisions and which build prompt may start now (A and B need plan 58 D1, D2 and
plan 55 D1, D3, D14 at least).

---

## PROMPT A: build plan 58, super agent v1, Tasks 1 to 6 (code; Sonnet, Opus for Task 5's admission and completion)

Goal: build slice 1 of the super agent: `console/superagent.py`, the `super/` files, the spend ledger, the Hub's wakes,
admission and pass results, `GET` and `POST /api/super`. No acts, no window. Work in a worktree on branch `plan-58`.

Read first, in this order: `CLAUDE.md`; `PLAN.md` rows 44, 52, 58; `plans/58-super-agent/README.md` whole, then
`08-review-and-jev.md` sections 1 and 5 (R1 to R9 are mandatory and override any older recipe in the task files);
`01` to `06` in order; the code the README section 2 cites: `console/supervisor.py` (`run`, `policy`, `MODEL_ALIASES`,
`append_log`), `console/compact.py` (`_ask`), `console/server.py` (`snapshot`, `task_row`, `actions`,
`_supervisor_tick`, the POST route table), `console/usage.py` (`record_supervisor`, `save_days`), `console/tuning.py`,
`console/paths.py`, `tests/test_supervisor_server.py` (`WakeTest`), `tests/fake_claude.py`.

Fred's plan 58 answers (recorded in `plans/decisions-2026-11-08.md`, D1 corrected 2026-11-09): D1 (b), D2 (a),
D3 (a), D4 (b), D5 (a), D6 (a), D7 (a), D8 (a), D9 (a), D10 (a), D11 (a). D12 (a) is a separate later JEV shadow
evaluation, outside this build. D1 (b) authorizes this scratch-only build before plan 52's live check; do not wait
for that check or mark it passed. Do not restart the production service or run paid acceptance. D2 (a) keeps the
upgrade defaults on at $0.20 a pass and $1.00 a day; fake-provider tests spend nothing. D4 (b) requires all watchdog
signals, including `idle_spend` and `retries` (Task 3's tagged note), with bounded git reads and tests first.

Note: plan 59 will later add `paused_at`, `hand`, `back`, `fwd`, `looked`, `log`, `messages` to
`state.json` as v2 and read v1; keep `load_state` strict as 1.1a says but do not reject a future key list by name.

Do, in order, one commit per task with the message the task file names:

1. Task 1 (`01-settings-and-files.md`, with 1.1a): settings, `blocked`, `status`, the `super/` files, strict
   `load_state`, atomic `save_state`, masked `append_log` (mask every string of the record before dumping; README
   section 2's masking trap), `read_orders`, `cut_notes`, the `super` kind file, the tuning whitelist, the orders seed.
2. Task 2 (`02-items-and-queue.md`, with 2.1a): `items`, `_event` (the R3 basis), `always_reason`, `task_kind`, `sync`
   (returns new, back, changed; forgets departed keys, `reviewed` too), `queue`, `select_items`; golden tables 4.1 and
   4.2 as tests, plus the review regressions (65 items, 31 always, invalid Later, incompatible batches).
3. Task 3 (`03-digest-and-pass.md`, with 3.1a): `describe`, `item_block` with the `incomplete` flag, `digest` reserving
   orders first, `build_prompt` bounded to 48 KiB, `SCHEMA`, `shape`, `check`, `pass_model` (Sonnet when any submitted
   item is stuck, including under a suggestion), `run` through `compact._ask`; the fake claude's super branch.
4. Task 4 (`04-ledger-and-usage.md`): the `super` ledger section (validate every record; an unreadable ledger is an
   error, never zero), `GET /api/usage` `super`, the Usage page block through plan 50's function with a `key` argument.
   This is the one `web/app.js` edit of this prompt: anchored, one call.
5. Task 5 (`05-hub.md`, Opus for the admission and completion steps): state at start and restart reconcile by pass
   UUID, the tick on a monotonic clock (debounce 20 s, ceiling 120 s, sweep on a changed fingerprint, one wake on a
   blocked-to-eligible transition), admission in R4's order (reserve, save the claim, log it, then the thread; any
   failed write settles zero and blocks), the pass thread outside every lock, completion that rebuilds live bases under
   `tlock` and **merges into the live `self.super`** (plan 59 depends on this: a Fred write made during the pass must
   survive), publication only after durable accounting. Fault-injection tests at every boundary of R4.
6. Task 6 (`06-routes.md`): `Hub.super_view` (pure projection, stale advice filtered on a copy, `coverage`, one ledger
   read), `Hub.super_action` (pause and resume persisted before 200, 503 on a failed save, Sort logged then armed),
   the two routes, `SuperRouteTest` over HTTP with the fake claude.

After each task: focused tests, the full suite in the background (about 10 minutes; read the finished output), `node
--check web/app.js` after Task 4, `git diff --stat` shows only the task's files. Every test uses a scratch
`CC_CONSOLE_HOME`, frozen clocks at `T0 = 1_800_000_000.0`, patched `superagent.run` or the fake claude; no paid
provider, no port 47770, no `~/.claude`.

Do not: add `act` or `order` to the schema, call any lever or route from a pass, change `server.task_row`,
`Hub.actions`, the snapshot's `counts` or any task path, change the task supervisor, edit another CLI's config, start
Task 7 (Fred's live check), or implement D12 (JEV). If a task file's recipe contradicts R1 to R9, R1 to R9 win; say
where. If a decision the plan leaves open bites, stop and ask Fred.

Done when: six commits on `plan-58`, the full suite green with its real count in each commit body, and a report under
40 lines: paths and commits, counts, the fake-pass latency, what you did not do, what Fred must do for Task 7 (restart
the service, the items to set up, the two PowerShell commands of 7.1), and the questions for Fred.

---

## PROMPT B: build plan 55 Tasks 1 to 3, the autopilot page from `actions` (code; Sonnet)

Goal: build the opened task's head, the actions seam, the dock card, the box hints, the bar and the body sections of
the locked autopilot UI, reading `GET /api/task` `actions` only. Stop after Task 3 (Task 4, the list, is replaced by
plan 59 Task 4 and is **never built**). Work in a worktree on branch `plan-55`.

Read first, in this order: `CLAUDE.md` (the Board paragraph and plan 52 Task 6 line); `PLAN.md` rows 48, 52, 55;
`plans/55-autopilot-ui/README.md` whole (sections 1, 2, 4, 5, 6, 7); `01-head-and-seam.md`, `02-dock-box-bar.md`,
`03-body-and-plan.md`; `plans/52-workflow-autopilot/08-design-lock.md` (UI-1 to UI-9) and `06-actions-contract.md`;
`design/rework/locked/workflow-autopilot.html` (open it in headless Edge at 900 and 400 px; read its CSS and markup);
`web/app.js` (`inspTask`, `taskButtons`, `taskMenu`, `attentionArea`, `supCard`, `replanBox`, `taskMessageState`,
`stepFooter`, `renderInspector`, the click handler), `web/style.css`, `tests/test_web.py` (the Node harness),
`tests/live_autopilot_check.py` (its `Rig`), `console/server.py` (`Hub.actions`, `_task`).

Fred's plan 55 answers: <Fred pastes D1 to D14, or "recommended column">. D3 (a) means the buttons `actions` does not
serve are not drawn; plan 59's D1 may later add `retry_up` on the server, which this prompt does not do.

Do, in order, one commit per task with the message the task file names:

1. Task 1 (`01-head-and-seam.md`): the seam (`acts`, `actFind`, `actLabel`, `actBtn`, `armBtn`, `runAction`,
   `ACT_COPY`, `ACT_TIP`, `ARM`, `PILL`), `pageHead`, `levelSeg`, `taskHead`; `tests/live_board_check.py` created on
   `live_autopilot_check.Rig`; the Models test edit it names. Every control in the head exists because `actions` lists
   it and is enabled because `off` is "".
2. Task 2 (`02-dock-box-bar.md`): `dockCard`, `iconBtn`, `barHtml`, `useHtml`, `taskShell`, `taskCard` per state,
   `openActionForm` and `actBody` (Reject's note from the box, D5), `boxHint`, `taskMessageState` on `actions.message`
   only (the fallback branch deleted), `stepFooter`; the client gate tests of README 1.1 that this task replaces are
   deleted in the same commit; `supCard`'s pending card, `attentionArea`, `replanBox`'s buttons, `confirmLabel` go.
   `--shots` PNGs for **Stop 1** (the mock's nine states and README section 5's six, 900 and 400 px, dark and light).
3. Task 3 (`03-body-and-plan.md`): the one server read field `prompt` (D7 a: `GET /api/task` gains the masked
   `prompt.md`; no gate, no write; its test in `tests/test_server.py`), `sect`, `foldLine`, `planRow`, `svLine`,
   `planTimeline`, `briefExtra`, `taskBody`; `routeHtml`, `gaugeHtml` and the quiet `supCard` go. Keep every function
   name plan 55 section 7 lists: plan 59 Tasks 5 and 6 call `pageHead`, `sect`, `actBtn`, `actLabel`, `armBtn`, `ARM`,
   `openActionForm`, `FORM_IDS`, `taskShell`, `stepFooter`, `barHtml`, `dockCard`, `iconBtn` by those names.

After each task: `node --check web/app.js`, `py -m unittest tests.test_web`, `py -m tests.live_board_check` (900, 400,
340 px, dark and light, reduced motion, 130 percent: no horizontal scroll, no page error, the 11 px and 24 px floors),
the full suite in the background, `git diff --stat` shows only the task's files. Anchor every `app.js` edit by a quoted
line, never a number.

Do not: build Task 4 (the list, `projectGroups`, `listHtml`, `homePick`, the Needs you pin), Tasks 5 to 7, any button
`actions` does not serve, any availability rule in JS, any change to `Hub.actions`'s gates or wording (D2 a: words come
from `ACT_COPY`), the composer (moments 1 and 2), the pill, the 400 px session page, Prep or Usage. If a mock button has
no served action, grey it out of existence (do not draw it) and list it in the report under D3.

Done when: three commits on `plan-55`, the full suite green with its real count, `node --check` clean, the Stop 1 PNG
folder path, and a report under 40 lines: paths and commits, counts, the deleted client gate tests (README 1.1 rows),
the copy of section 4.3 for Fred to read at Stop 1, what you did not do, and the questions for Fred (D14 and the copy).

---

Order after A and B merge: Fred runs plan 58 Task 7 and plan 55's Stop 1; then Prompt 0 below.

Fred only: the answers to section 7; Stop 1 (the screenshots after Task 7); Task 8's sitting; the close.

---

## PROMPT 0: gate check for plan 59 (read only, ten minutes; Haiku)

Goal: say whether plan 59 may be built today. Change nothing.

Read `plans/59-super-agent-window/README.md` ("The build waits", section 2). Then check, in the code and `PLAN.md`:

1. Plan 58 built: `console/superagent.py` exists with `items`, `sync`, `queue`, `status`, `settings`, `describe`,
   `blank_state`, `load_state`, `save_state`, `append_log`; `console/server.py` has `Hub.super_view`,
   `Hub.super_action`, `_super_tick`, `_super_arm`, `super_wake`, `super_threads`; `tests/test_superagent_server.py`
   has `SuperHubTest` and `make_task`. `PLAN.md` row 58 says built and live check passed; D2, D6, D9, D10 closed.
2. Plan 55 Tasks 1 to 3 built: `web/app.js` has `acts`, `actFind`, `actLabel`, `actBtn`, `armBtn`, `ARM`, `runAction`,
   `pageHead`, `dockCard`, `barHtml`, `taskShell`, `stepFooter`, `openActionForm`, `FORM_IDS`, `sect`, `foldLine`,
   `planRow`, `svLine`; `tests/live_board_check.py` exists; `PLAN.md` row 55 says Tasks 1 to 3 built and Stop 1
   passed. Plan 55 Task 4 is **not** built (no `projectGroups`, `listHtml`, `homePick`, `.p-pin` in `app.js`).
3. Fred's answers to plan 59 section 7 are written under the table (or he said "the recommended column").

For every plan 59 section 2 row, print the plan 58 or 55 name and whether the built code has it under that name, or
under which other name. Report in at most 40 lines: GO or NO-GO, the missing gates, the renamed symbols. Nothing else.

---

## PROMPT 1: plan 59 Tasks 1 to 3, the server side (code; Sonnet, Opus for step 0 only)

Goal: build the data behind the super agent window: `console/superwin.py`, state v2, the one count in the snapshot,
the tray word, `GET /api/super`'s card fields and `POST /api/super`'s five new actions. Nothing visible changes yet.

Read first, in this order: `CLAUDE.md`; `PLAN.md` rows 55, 58, 59; `plans/59-super-agent-window/README.md` whole
(sections 2, 4 and 9 twice); `01-state-and-count.md`, `02-served-cards.md`, `03-writes.md`; the plan 58 files its
section 2 cites (`plans/58-super-agent/README.md` 3.3 to 3.10, `08-review-and-jev.md` R1 to R9, 02, 03, 05, 06) **and
the built code they became**; `console/server.py` (`Hub.actions`, `Hub.levers`, `Hub.task_message`, `Hub.snapshot`,
`task_row`, the super section plan 58 added, the POST route table); `console/tray.py`; `tests/test_superagent_server.py`.

Prompt 0 said GO and listed the renamed symbols; paste its list here: <Fred pastes it>. Fred's section 7 answers:
<Fred pastes them, or "recommended column">. If D1 is b-lite, Task 0 comes first: add `retry_up` to `Hub.actions`
for `failed_twice` and `stuck` (a `model: "up"` body on the existing retry route, `server.py` `task_lever` resolves
"up" to one rung above the step's model through `routing`), with its test in `tests/test_server.py`; then Task 2's
`CARD_ACTS` for those two states gains `retry_up` in `primary`.

Do, in order, one commit per task with the message the task file names:

1. **Step 0 (Opus, 30 minutes, no behaviour).** Section 1.0 of `01-state-and-count.md`: write `Hub._super_inputs(state,
   spend)` and `Hub._super_publish(spend=None)`, fill the mapping table with the built names, and read plan 58's built
   completion to confirm it merges over the live `self.super` under `tlock` (03 step 0). If a plan 58 name differs,
   change the one line the README section 2 row names, nowhere else. If plan 58's completion copies the state at
   admission, fix that one line in Task 3 and say so.
2. **Task 1** (`01-state-and-count.md`): tests first (`tests/test_superwin.py`, `tests/test_superwin_server.py`, the
   edits to `test_superagent.py` and `test_tray.py`), red for the stated reasons, then the code. Non-negotiable:
   `snapshot()` takes no `tlock` and reads no ledger (`test_the_snapshot_takes_no_lock_reads_no_file_and_runs_no_gate`);
   `accept_items` has no time window; a changed key writes no "settled" line; every path that saves `self.super` ends
   with `_super_publish`.
3. **Task 2** (`02-served-cards.md`): `Hub.actions` runs once per live item, in plan 58's describe loop, **outside
   `tlock`**; `_super_card` takes that view; the 30-item budget test prints its median and you put the figure in the
   commit body. `HAND_OFF_CARD` serves the form in `bar`; `OWN_KINDS` has `chat`.
4. **Task 3** (`03-writes.md`): `later`, `bring_back`, `seen`, `message`, `orders`; durable before the answer; the
   completion requirement; `paused_at` on pause and resume; the digest's messages block and the one sentence in
   `SCHEMA_REMINDER`.

After each task: focused tests, then the full suite in the background (`py -m unittest discover -s tests`, about 10
minutes; read the finished output), `git diff --stat` shows only the task's files, stage explicit paths and only this
plan's hunks of `console/server.py` and `console/superagent.py` (the `git hash-object -w` recipe in the plan).

Do not: touch `web/`, add a route that answers a task or a session, change `Hub.actions`'s gates (Task 0 adds one
action, it changes no `off`), change `Hub.levers`, `task_levers` or `supervisor.*`, edit a kind file, run the service,
or start Task 4. If a plan 58 contract turns out to differ from its document in a way one line cannot absorb, stop,
report the row of section 2 and the built code, and wait for Fred.

Done when: three commits (four with Task 0), the full suite green with its real count in each commit body, and a report
under 40 lines: paths and commits, counts, the GET /api/super median at 30 items, every plan 58 name you bound, what
you did not do, and the questions for Fred.

---

## PROMPT 2: plan 59 Tasks 4 to 7, the window (code; Sonnet)

Goal: draw the super agent window: the row and the roll-up list, the page and its cards, the answers in place, the
one box, the Models card, every state; end at Stop 1 with screenshots for Fred.

Read first, in this order: `CLAUDE.md`; `plans/59-super-agent-window/README.md` whole (sections 4.3 to 4.10, 5 and 6
twice); `04-row-and-list.md` to `07-models-card-and-states.md`; `design/rework/locked/super-agent.html` (open it in
headless Edge at 900 and 400 px, press every state button, read its "Design read" and "Decided by Fred" notes: they
are binding); plan 55's built parts in `web/app.js` (`pageHead`, `sect`, `actBtn`, `actLabel`, `armBtn`, `ARM`,
`openActionForm`, `FORM_IDS`, `taskShell`, `stepFooter`, `barHtml`) and `tests/live_board_check.py` (its `Rig`);
`tests/test_web.py` (the Node harness at the top: every browser global is a proxy, `snap` starts null); the Prompt 1
report (the GET fields as built).

Fred's section 7 answers: <Fred pastes them>. If D11 is the review's variant (one visible input at a time), Task 6's
`swBox` and `renderCompose` collapse the left composer's textarea while the home pane shows; the chips, effort and
files strip stay; add one test that the two inputs are never both editable.

Do, in order, one commit per task with the message the task file names, `node --check web/app.js` after every edit:

1. **Task 4** (`04-row-and-list.md`): the row, `listHtml` over today's grouping code, the project lines, `swFetch`
   before `swHeader` in `renderBoard`, `tests/live_super_check.py` created with `list_checks`. The header button says
   `N for you` and is never hidden. The in-flight rule of `swInSync` is in the test.
2. **Task 5** (`05-page-and-cards.md`): the page and the cards from `superView` alone; no gate in JS (`off` comes from
   the data); a decision without a default preselects nothing and Confirm waits for a pick; `page_checks` in the
   headless file; the mock's CSS ported with the `sw-` prefix and the 11 px and 24 px floors.
3. **Task 6** (`06-answers-and-box.md`): `swRunAct` posts what `acts` says and nothing else; the batch posts each
   member's own action; Later, Bring back, Mark seen, Edit orders, Pause, Resume, Sort; the box and its chip;
   `act_checks` in the headless file; the last test of 6.1 (no task route named in the plan 59 region) must pass.
4. **Task 7** (`07-models-card-and-states.md`): the Models card (two table entries), the landmarks, the announcements,
   the `test_tuning` round trip, the state sweep at 900, 400 and 340 px, dark and light, reduced motion, 130 percent;
   `py -m tests.live_super_check --shots <scratch folder>` writes the PNGs. Then **stop** (Stop 1).

After each task: `py -m unittest tests.test_web`, `py -m tests.live_super_check`, the full suite in the background,
`git diff --stat` shows only the task's files, stage explicit paths and only this plan's hunks of `web/app.js`,
`web/style.css`, `web/index.html` (other chats edit `app.js`; anchor by quoted line, never by number).

Do not: compute any availability in JS (a button exists because `acts` lists it, is enabled because `off` is ""),
name a task route inside the plan 59 region, answer an observed chat, draw Undo, a proposed order, a job or a merge
row, build plan 55 Task 4's pin or `homePick`, change `console/`, or start Task 8. If a plan 55 part is missing or
named otherwise, stop and report (section 2 names the task that owns the mapping).

Done when: four commits, the full suite green with its real count, the PNG folder path, and a report under 40 lines:
paths and commits, counts, the screenshot list (eight mock states, `waiting`, `error`, the unshown cards of README
5.3, 900 and 400 px, dark and light), what you did not do, and the three questions Stop 1 asks Fred (do the unshown
states read right; is Open for an observed chat acceptable, D3; are the card buttons the right ones, D1).
