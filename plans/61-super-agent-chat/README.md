# Plan 61: Super agent acts and chat. Fred talks; the super agent presses the card actions. Guided implementation plan

> Direction update 2026-11-11: BRAINSTORM D20 and [plan 62](../62-task-orchestrators.md) supersede the global
> chat and cross-task tool scope below. Reuse the gated action/audit design for one fixed-model orchestrator
> per task, selected from connected CLIs and counted in shared global usage. Re-scope before implementation.

> Design: [../../design/brainstorm/2026-11-09-super-agent-chat.md](../../design/brainstorm/2026-11-09-super-agent-chat.md)
> (sections 0 to 14; C1 to C5 decided by Fred 2026-11-09). BRAINSTORM D19 and 7.7. Slice 3 of
> [../../design/brainstorm/2026-11-08-super-agent.md](../../design/brainstorm/2026-11-08-super-agent.md) section 9.
> Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md). Lands on plans 44 (the audit
> pattern, `task_lever` origin), 52 (`Hub.actions`), 54 (`paths.write_text_atomic`), 58 (the passes, `super.jsonl`,
> the `super` ledger) and 59 (the page, the box, Later, Orders).

Status: **written 2026-11-09, plan only.** Baseline: master `4a0eb05` (docs) and branch `plan-58` at `d557f22` (plan 58
Tasks 1 to 6 built, not merged). Every code fact below was read on `plan-58`; nothing is implemented and no product
file was touched. Decided by Fred 2026-11-09 (section 5): D1 (b, bounded), D2 (a), D3 (a); the task files follow
them.

**The build waits.** Tasks 1 to 4 build after plan 58 Tasks 1 to 6 are merged to master, on scratch services only.
Task 5 (background acts) builds after plan 58's live check (its Task 7), and runs on one real project first. Task 6
(the thread in the window) builds after plan 59's web tasks and after Fred locks the mock that Task 6 starts with.

| # | File | Delivers | Depends on |
|---|---|---|---|
| 1 | [01-act-layer.md](01-act-layer.md) | `console/superact.py` (pure rules), `Hub.super_act` and `Hub._press`, the act audit, uncertain acts, Undo, `task_lever`'s super agent label, the super agent's Approve (`_supervisor_dispatch` by `super`, one step past the work cap) | plan 58 T1-6 merged |
| 2 | [02-limits-and-ledger.md](02-limits-and-ledger.md) | the six settings (config defaults, tuning whitelist, checks), the `chat` ledger section, GET /api/usage `chat`, the Usage page row | 1 |
| 3 | [03-endpoint-and-tools.md](03-endpoint-and-tools.md) | `console/mcp.py` (stateless JSON-RPC), `guard.mcp_ok`, `POST /api/mcp`, `console/chattools.py` (nine tools), `superchat.py` part 1 (the thread file), `Hub.chat_card` | 1, 2 |
| 4 | [04-chat-runner.md](04-chat-runner.md) | `superchat.py` part 2 (prompt, command, stream reader), the turn thread, memory, Stop, restart recovery, `GET` and `POST /api/super/chat`, `snap.chat`; the fake claude chat mode | 3 |
| 5 | [05-background-acts.md](05-background-acts.md) | `act` in plan 58's answer, its checks and caps, the press from `_super_complete` only, the act rule in `SCHEMA_REMINDER`, the one opus retry after a second FAIL | 1, 2, plan 58 live check |
| 6 | [06-thread-window.md](06-thread-window.md) | the mock (a design session, locked by Fred), then the Thread section, the chip, Confirm cards, act lines with Undo; `later`, `bring_back` and Save order on plan 59 Task 3 | 4, plan 59 web, mock lock |
| 7 | [07-live-check-close.md](07-live-check-close.md) | Fred's live day by talking, cost per turn and per day, the effort choice, CLAUDE.md and PLAN.md lines | 1-6 |

Tests first in every task, one commit per task, `py -m unittest discover -s tests` at each boundary (about 10 minutes:
run it in the background and read the finished output), `node --check web/app.js` after a web change. No paid
provider in any test, a scratch `CC_CONSOLE_HOME`, never port 47770, never a write in `~/.claude`. Other chats edit
`PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md`, `web/app.js`, `console/server.py` and `console/__main__.py` in parallel:
anchor every edit by its quoted line, stage explicit paths, and stage only this plan's hunks of a shared file
non-interactively (`git hash-object -w` of HEAD's file plus this hunk, then `git update-index --cacheinfo
100644,<blob>,<path>`). Never stage `console/__main__.py`. Run `ls plans` before any new plan file.

## 1. Goal and scope

Fred finds the buttons tiring: every answer is a page switch and a click. This plan lets him say what he wants in one
box and have the super agent press the card actions for him, and lets plan 58's passes press them alone in projects
at `auto`. The cards stay as they are (C1); nothing gains a power the cards do not already have.

Done when: Fred clears a real day's items by talking (Task 7); every press, his or the background's, is one audit
pair in `super.jsonl` and one line in the thread; an always-yours action never runs without his click; an uncertain
act is never replayed.

**Out of scope:** jobs, worktrees, push and merge (slices 4 and 5); a resident process (one `claude -p` per message);
any write outside `~/.claude/console/`; opening a terminal or a folder from the chat (D2); observed VS Code or
terminal chats (D3); a Models page card for the new settings (config by hand through the whitelist, as plan 58 D9).

## 2. Facts checked 2026-11-09

- **CLI flags** (code.claude.com `cli-reference`, read 2026-11-09): `--permission-prompts none` ("Pass `none` when
  nobody can answer, and Claude Code denies them instead"), `--strict-mcp-config`, `--mcp-config`, `--allowedTools`,
  `--tools ""` (disables all built-in tools), `--setting-sources` (comma list; empty loads none), `--settings` (path or
  inline JSON), `--disable-slash-commands`, `--append-system-prompt-file`, `--max-budget-usd` (print mode; with
  `--resume` earlier totals do not count), `--session-id` (a UUID), `--resume`, `--effort` (`low` to `max`),
  `--include-partial-messages` (needs `-p` and stream-json output), `--input-format stream-json`. `--safe-mode`
  disables MCP servers: never used. `--system-prompt-snapshot off` rebuilds the prompt on every request: not used
  (section 4, row 6).
- **Environment** (`env-vars`): `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` ("prevent loading any CLAUDE.md memory files"),
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
- **`Hub.actions(task)`** (`server.py:1146`): `{state, line, primary, bar, menu, message}`, each action `{id, label,
  post, body, off, confirm}`. Posts: `/api/task/<lever>` for `stop`, `pause`, `resume` (also `start` and `start_next`
  with a follow-up), `confirm` (also `confirm_auto` with `remember: "auto"`), `clear` (`delete`, `drop`), `done`
  (`finish`), `accept`, `stepdone`, `redo`, `keep`; `/api/task/message` (decision options by their key, and
  `default_auto` with `remember`); `/api/task/supervisor` (`level_<mode>`, `approve`, `reject`, `dismiss`);
  `/api/continue` (`resume` of a stopped window run); `/api/terminal`; `/api/task/folder`. Forms (`post` ""): `retry`,
  `handoff`, `add_step` (body carries `source_step`, `source_session`), `reopen`, `start_next` without a follow-up,
  `edit_steps`, `edit_prompt`, `edit_plan`, `review`. An observed chat's card has `state` `observed` and only fork
  actions.
- **Routes' Hub methods** (`do_POST`, `server.py:4943`): `_task_lever` calls `hub.task_lever(task, lever, note, model,
  pending, remember=)`; `_task_message` calls `hub.task_message(body)` (needs `request_id`, `text`, `target`);
  `_task_supervisor` calls `hub.supervisor_action(body)`; `_lever` calls `hub.pull(session, lever, text, confirm,
  files)`; `_task_next_preview` and `_task_next` call `hub.preview_next(request)` and `hub.request_next(request,
  origin=)` (payload `task, source_step, source_session, kind, instructions, model`, then `revision` and a UUID
  `request_id`); `task_handoff(body, preview=True)` returns `{text, revision, cost}` and the save needs `create` (bool),
  `request_id` (32 hex) and `revision`. `_terminal`, `_task_folder` and `_done` keep their logic in `Handler`.
- **`task_lever` origin** (`server.py:4623`): `origin == "fred"` calls `_supervisor_fred(task, now, lever)`; any other
  origin replaces `" by Fred"` with `" by the supervisor"` in the lines and `why`.
- **Locks**: `self.lock` (`threading.Lock`), `self.tlock` (`threading.RLock`); the order is `tlock` then `lock`
  (`task_lever` holds `tlock` and reads sessions).
- **Plan 58**: `superagent.append_log(home, record)` masks every string and raises `OSError`; `read_log(home)` raises
  `ValueError` on a corrupt line; `check()` returns `{ann, digest, notes, dropped, trimmed}`; `_super_complete` calls
  `_super_publish(job, result)`; `job["bases"]` maps item keys to their basis; an item key is
  `task:<id>:<event>`; `usage.reserve_super`, `record_super`, `load_super`, `super_spent` own the `super` section.
- **Plan 59** (documented, not built): `POST /api/super` grows `later`, `bring_back`, `seen`, `message`, `orders`
  (`{action: "orders", text}` replaces `orders.md` whole); web names `swPage`, `swTarget`, `swBox`, `swSend`, `sect`.
- **`make_server`** returns `(httpd, hub)`; the Hub does not know the bound port (tests bind port 0).
- **`tests/fake_claude.py`**: `run()` serves stream-json; `--json-schema` goes to `prep()`.
- **Plan 44 dispatch** (master `368cb15`, read for D1): `_supervisor_dispatch(task_id, wake, by)` runs
  `supervisor.auto_reason` only when `by` is neither `fred` nor `message`, and `_supervisor_fred` (the window reset)
  only for `fred`. `auto_reason` tests, in order: the mode, a gated plan, report-only wakes (`REPORT_ONLY`: `done`,
  `stalled`, `stalled_stop`), the kind (`AUTO_KINDS`: add step, confirm, keep, retry, finish), the work window, the
  step count, `task_max_steps`, a repair whose verify failed, a used retry. `supervisor.check` refuses a retry with
  none left in every mode. `start_step` stops a supervisor-caused chain at the work cap (`supervisor work cap reached
  ($x of $y)`, owner `fred`, no suggestion). A stall's suggestion is Stop (the step still runs); its follow-up is a
  fixed Retry that needs an Approve in every mode (plan 44 D6). `Hub.actions` serves Approve for a `suggest` pending
  only.

## 3. Contract

### 3.1 The act layer (Task 1)

`Hub.super_act(task_id, action_id, args, origin, *, forwarded="", card_hash="")`, origins `chat`, `super` and `fred`
(a Confirm card Fred clicked). The only path by which the super agent changes anything. In order:

1. The task exists; its card is `Hub.actions(task)` now; its level is `supervisor.policy(cfg, task, now)["mode"]`.
2. `superact.verdict`: an observed card is refused; the id must be on the card and its `off` empty; a window-only id
   (`edit_steps`, `edit_prompt`, `edit_plan`, `review`, `terminal`, `folder`, and any other empty `post` outside
   `superact.FORMS`, which covers `start_next` without a follow-up) is refused `opens in the window`. For `super`: the
   level must be `auto`, the item not always forwarded (one lift, 3.6), the action not always yours, never the task
   supervisor's `reject` or `dismiss`, and its `approve` only for a kind in `supervisor.AUTO_KINDS` (D1, 3.6). For
   `chat`: an always-yours action answers `needs_click`. `fred` presses.
3. A Confirm card's `card_hash` must equal the card's hash now, else `out of date: the card changed`.
4. An earlier uncertain act on the task refuses every origin: `an earlier act on this task is uncertain: dismiss it
   in the thread first`. For `super`, the caps of 3.2 must have room.
5. `superact.clean_args`: only the form's own fields (3.1.2); a press with a `post` takes none.
6. The intent line (`phase: act`) goes to `super.jsonl` before the effect; an audit that cannot be written refuses
   (503). The press (`Hub._press`, 3.1.3). The outcome line (`phase: acted`) after. An exception inside the press, or
   an outcome line that cannot be written, makes the act uncertain: shown, never replayed, until Fred dismisses it.

Answers: `200 {outcome: "done", act, label, task, title}`, `200 {outcome: "needs_click", why, label, task, title,
action, args, hash}`, `409 {outcome: "refused", why, label}` (a route's own refusal keeps its status), `400` for bad
arguments, `500 {outcome: "uncertain"}`.

#### 3.1.1 Always yours (`superact.ALWAYS`, every level, both model origins)

`delete`, `drop`, `finish`, `stop`, `stepdone` (Accept step result), `confirm_auto` and `default_auto` and every
`level_<mode>` (a level change), and `confirm` when `task["why"] == "confirm Fable"` (Fable) or `tasks.held(task)` (Run
anyway). The chat gets `needs_click`; the passes are refused.

#### 3.1.2 Forms (`superact.FORMS`)

| Id | Arguments | Press |
|---|---|---|
| `retry` | `model` (auto, haiku, sonnet, opus), `note` | `task_lever(task, "retry", note, model or "")` |
| `add_step` | `text` (required), `model`, `kind` (`tasks.NEXT_KINDS`, default `code`) | `preview_next`, then `request_next` with its `revision` and a new UUID |
| `handoff` | `follow_up` (bool, default false), `note` | `task_handoff(preview=True)`, then the save with `create` = `follow_up`, a new 32-hex id, the preview's `revision` |
| `reopen` | `text` (required) | `task_message` with the card's `message.target`, a new UUID |

`note` and `text`: at most 500 characters, stripped, masked.

#### 3.1.3 Presses with a post (`Hub._press`)

| Post | Call |
|---|---|
| `/api/task/<lever>` (the eleven levers of `do_POST`) | `task_lever(body["task"], lever, "", None, "", origin=who, remember=body.get("remember"))` |
| `/api/task/message` | `task_message(body)` (a decision option keeps its served deterministic `request_id`) |
| `/api/task/supervisor` | `supervisor_action(body)`; a pass's `approve`: `_supervisor_dispatch(task, wake, "super")` (3.6) |
| `/api/continue` | `pull(body["session"], "continue", body.get("text", ""), False, [])` |
| anything else | refused `opens in the window` (`superact.verdict` already refuses `/api/terminal` and `/api/task/folder`) |

`who` is `fred` for the `chat` and `fred` origins (the press is on Fred's word, so plan 44's `_supervisor_fred` runs
as for his click) and `super` for the passes; `task_lever` then writes `by the super agent` (Task 1 edit).

#### 3.1.4 Undo (`superact.UNDO`)

`pause` to `resume`, `resume` to `pause`, `start`, `confirm`, `retry` and `add_step` to `stop`. Undo is Fred's click
(origin `fred`), so Stop needs no Confirm. Accept has no server Undo: its line opens the card's Reopen form (Task 6).

### 3.2 Limits (Task 2)

| Key | Default | Range | Meaning |
|---|---|---|---|
| `chat_model` | `sonnet` | haiku, sonnet, opus | the chat's model; never fable |
| `chat_turn_usd` | 0.50 | 0.05 to 2 | `--max-budget-usd` of one turn, and its ledger reservation |
| `chat_day_usd` | 3.00 | 0 to 20 | a local day's chat spend; 0 turns the chat off |
| `chat_timeout_s` | 600 | 60 to 1800 | one turn's wall clock |
| `super_acts_day` | 20 | 0 to 100 | background acts in a local day; 0 turns them off |
| `super_acts_task_hour` | 2 | 0 to 6 | background acts on one task within an hour |

All six are in `tuning.TUNING` (group `super`), so `POST /api/config/models` is their only writer. A wrong value keeps
the chat (or the background acts) off with the reason, like `superagent.settings`. The chat's spend is the `chat`
section of `usage-days.json` (records `kind: "chat"`, the `super` rules), shown in GET /api/usage `chat` and as a
row of the Usage page's passes block.

### 3.3 The endpoint (Task 3)

`POST /api/mcp`: JSON-RPC 2.0, one message per request, stateless. `initialize` (echoes a known protocol version,
else the newest), `ping`, `tools/list`, `tools/call`; a notification (no `id`) answers 202 with no body; any other
method answers `-32601 Method not found`. Checked before `guard.post_ok`: the loopback Host (`guard.host_ok`) and
`Authorization: Bearer <token>` (`guard.mcp_ok`, a constant-time compare against the live turns' tokens). A missing,
wrong or stale token answers 401. Arguments are checked against the tool's schema (`additionalProperties: false`);
a bad one answers a tool error, not a protocol error. Results are masked, cut at 160,000 characters and split into
text parts of at most 40,000. Read tools carry `readOnlyHint`. `GET /api/mcp` answers 405.

### 3.4 The tools (Task 3, `console/chattools.py`)

`overview`, `task {task}`, `read {task, what, step?}`, `usage`, `act {task, action, model?, note?, text?, kind?,
follow_up?}`, `tell {task, text}`, `session {session, action: answer|resume, text?}`, `new_work {project, text}`,
`propose_order {text}`; Task 6 adds `later {keys}` and `bring_back {keys}`. `act` with `needs_click` adds a Confirm
card to the thread; `propose_order` adds a Save order card; `new_work` starts Prep only and adds a Prep card (Start
stays on the Prep card, BRAINSTORM D4).

### 3.5 The chat engine (Task 4)

One `claude -p` per message, in `~/.claude/console/super/chat/work/` (empty), with:

```
<exe> -p --model <chat_model> --effort medium --input-format stream-json --output-format stream-json --verbose
  --include-partial-messages --tools "" --mcp-config <run>/mcp.json --strict-mcp-config
  --allowedTools mcp__console__overview,...,mcp__console__propose_order --permission-prompts none
  --setting-sources "" --settings {"disableAllHooks": true} --disable-slash-commands
  --append-system-prompt-file <run>/system.md --max-budget-usd <chat_turn_usd> (--session-id <uuid> | --resume <uuid>)
```

Environment: `claude_cli.child_env()` plus the two variables of section 2. Spawned like `runs._spawn` (no window,
breakaway, the service job) but by the Hub itself, never through `runs.start`, so the chat is never a session row.
stdin stays open for the interrupt; stdout is read line by line. `mcp.json` holds `http://127.0.0.1:<hub.port>/api/mcp`
and the turn's token; `runs/<turn>/` is deleted when the turn ends and at service start.

Each message's stdin is `<earlier_chat>` (a fresh session only: the last 6 exchanges, 2,000 characters each, and the
passes' `notes.md`), then `<console_context>` (page, selected task or run, local time, the standing orders), then
Fred's text. A fresh session starts on the first message, after New chat, when `prompt_hash` or the model changed,
when the last turn's context passed `gauge_yellow_tokens`, and once more when a resume is lost ("No conversation
found"). One turn at a time. Stop writes the stream-json interrupt (never a kill); the partial reply is kept. A turn
over `chat_timeout_s`, or one that calls a tool outside the list, is killed (`claude_cli.kill_tree`).

Files: `super/chat/thread.json` (`{v: 1, session, prompt_hash, model, tokens, turns, cards}`, the last 200 of each,
written with `paths.write_text_atomic`; an unreadable file blocks sending until New chat, which keeps it as
`thread.1.json`).

### 3.6 Background acts (Task 5)

An answer entry may say `"do": "act"` with `"act": {"action", "args"}`. `superagent.check` validates its shape,
stores the entry as a `forward` annotation (the item stays in the queue with its `say` line) and returns it in
`acts`; an always-forwarded item's act is trimmed (one lift, rule 2 below). `Hub._super_complete` (never
`_super_reconcile`) then presses each act through `super_act(..., "super")` after these checks: the super agent is not
paused; the item is still live with the pass's basis; the act layer's own checks (3.1, level `auto`, caps). A refused
act is one `act_refused` line.

**What a pass may press at `auto` (D1 (b), bounded, Fred 2026-11-09).** What 3.1 allows, within
`super_acts_task_hour` and `super_acts_day`, plus three things Fred chose so a project at `auto` keeps moving while he
is away:

1. **Approve a capped suggestion.** When the task supervisor's own dispatch is held by its step count, its work
   window or its report-only rule (the done wake; the fixed Retry after a stalled step's Stop), a pass may press
   Approve if the suggestion's kind is one the task supervisor may run alone (`supervisor.AUTO_KINDS`: add step,
   confirm, keep, retry, finish; never Stop or Accept step result). The dispatch is `_supervisor_dispatch(task, wake,
   "super")`: every plan 44 gate and `supervisor.check` run, `supervisor.auto_reason` runs under
   `superact.lifted(policy)`, and `_supervisor_fred` does not, so the window is never reset: each Approve buys one
   step, and only Fred's click starts a new window. `start_step` lets that one step past the work cap
   (`sup_cause["by"] == "super"`); the next one waits.
2. **Retry once on opus after a second verify FAIL.** The item stays forwarded (`second verify FAIL`); the one press
   allowed is the card's Retry with `model` `opus`, once per step of a task (`superact.lift`, counted from the intent
   lines). A FAIL after it reaches Fred.
3. **Stalls.** A 30-minute stall's suggestion is Stop (the step still runs): Fred's. After his Stop, its fixed Retry
   suggestion is approved by rule 1.

Still Fred's: Fable, a pace hold and a usage limit (Run anyway), a question with no default, Stop, Finish, Delete,
Drop, Accept step result, Reject and Dismiss, a chain stopped mid-way at the work cap (`work cap`: no suggestion to
approve, and Continue there is his takeover), a repair whose verify already failed, a used supervisor retry, the
supervisor's spend cap, and every uncertain act or dispatch.

### 3.7 GET and POST /api/super/chat (Task 4)

GET (reads only): `{busy, stopping, off, error, model, turns, cards, uncertain, acts, spend, tokens, fresh}`. POST,
exact key sets: `{action: "send", text, page?, selected?}` (202 `{turn}`), `{action: "stop"}`, `{action: "new"}`,
`{action: "confirm" | "cancel", card}`, `{action: "dismiss" | "undo", act}`; Task 6 adds `{action: "save_order",
card}`. Otherwise 400 `action: send, stop, new, confirm, cancel, dismiss or undo`. `X-CC` as every POST: no tool can
reach this route, so only the window confirms a card. `snap["chat"] = {busy, turns, open}` drives the window's refresh.

## 4. Departures from the design (plan-time choices)

| # | Design | Plan | Why |
|---|---|---|---|
| 1 | press "through the same handler the window's POST reaches" | the Hub method each handler calls (3.1.3); handler-only logic is window only | the handlers are one line over these methods; no loopback HTTP, and the origin reaches `task_lever` |
| 2 | a bad token: 401 and the run is killed | 401 only | a wrong token cannot name its run; a tool outside the list still kills |
| 3 | started through `runs.py` | the Hub's own `Popen` with `runs._spawn`'s flags | `runs.start` makes a session row; the design's own rule is that the chat never shows as one |
| 4 | `new_work`: a planned card with Start | Prep only; the Prep card holds Start | BRAINSTORM D4: Prep never starts work by itself |
| 5 | `later`, `bring_back`, Save order in the first build | Task 6, on plan 59 Task 3's `POST /api/super` | those writes are plan 59's; no second writer of `orders.md` |
| 6 | the hash rule or `--system-prompt-snapshot off` (left open) | the hash rule | proven by sticker-generator-simple; `off` rebuilds every request |
| 7 | the act tool's `option` argument | dropped: a decision option is pressed by its served id | one way to name a press |
| 8 | the act checks "its tier is not over pace" | the routes' pace holds; Run anyway stays always yours | a step over pace is held by the existing code, and its release is Fred's |
| 9 | effort "measured on a scratch turn" | `medium` now, measured in Task 7 | a measurement needs a paid turn: Fred's live check |
| 10 | `read` also gives a chat's tail | plan, handoff, note, brief | a chat's tail is an observed session's transcript (D3) |

## 5. Decisions for Fred (closed 2026-11-09; the tasks follow the answers)

| # | Question | (a) recommended | (b) |
|---|---|---|---|
| D1 | May a background act press the task supervisor's Approve, Reject or Dismiss at `auto`? | No: the chat and the cards only. At `auto` the task supervisor already acts within its caps; what it leaves on the card is what its caps or its report-only rule kept for Fred | Yes, with the dispatch labelled the super agent's (Task 1 `superact.FRED_SUGGESTION` loses `approve`). **Closed (b), bounded**, Fred 2026-11-09: (a) meant watching Console all day; he chose Approve capped steps, Retry after a second FAIL and Handle stalls, not Run anyway on a pace hold. Approve only, never Reject or Dismiss (3.6) |
| D2 | May the chat press Open in terminal and Open folder? | No: `opens in the window`; the chat says where | Yes: move `_terminal` and `_task_folder` into Hub methods and press them for `chat` only. **Closed (a)**, Fred 2026-11-09: "no need" |
| D3 | Observed VS Code and terminal chats | Not reachable in v1: the chat reads them in `overview` and sends Fred to their card | Confirm cards that fork them through `pull`. **Closed (a)**, Fred 2026-11-09 |

## 6. Failure paths and their tests

| Case | Behaviour | Test |
|---|---|---|
| action not on the card, or off | refused with the reason | `test_superact.VerdictTest`, `SuperActHubTest.test_refusals` |
| always yours from the chat | `needs_click`; nothing pressed; no audit pair | `SuperActHubTest.test_always_yours_needs_click` |
| always yours from the passes, or level not auto | refused; one `act_refused` line | `SuperActHubTest.test_super_origin_gates` |
| audit unwritable | 503, nothing pressed | `SuperActHubTest.test_audit_first` |
| press raises | uncertain; every later act on the task refused until dismissed | `SuperActHubTest.test_uncertain_blocks_until_dismissed` |
| service restart between intent and outcome | the act shows uncertain at start | `SuperActHubTest.test_uncertain_survives_restart` |
| Confirm card after the card changed | `out of date` | `ChatRouteTest.test_confirm_out_of_date` |
| bad or stale token | 401 | `McpRouteTest.test_tokens` |
| unknown method, bad arguments | `-32601`; a tool error | `McpTest` |
| result over 40,000 characters | split into parts | `McpTest.test_split` |
| tool outside the list | the run killed, the turn names it | `ChatRouteTest.test_outside_tool_kills` |
| lost session | one fresh retry with `<earlier_chat>` | `ChatRouteTest.test_lost_session_retries_once` |
| over `chat_day_usd` | 409 `chat off for today`; cards unaffected | `ChatRouteTest.test_day_cap` |
| Stop | interrupt; partial reply kept; state `stopped` | `ChatRouteTest.test_stop_keeps_the_partial_reply` |
| restart mid-turn | the turn `interrupted`, its reservation unknown, `runs/` emptied | `ChatHubTest.test_restart_recovery` |
| background caps | the 21st act of a day, the 3rd on a task in an hour refused | `BackgroundActTest.test_caps` |
| item changed before the press | refused `the item changed` | `BackgroundActTest.test_stale_item` |
| a pass's Approve of a Stop suggestion | 409 `stop needs Fred's approval`; nothing pressed | `AutonomyTest.test_super_approve_never_stops_and_takes_report_only` |
| a pass's Approve past the step cap | dispatched; the window is not reset | `AutonomyTest.test_super_approve_past_the_step_cap_keeps_the_window` |
| the step after a pass's Approve at the work cap | waits `supervisor work cap reached` | `AutonomyTest.test_super_approve_buys_one_step_past_the_work_cap` |
| a second opus retry of a step | refused `... the opus retry of this step was used` | `SuperActHubTest.test_second_fail_retry_once_on_opus` |

## 7. Verification

Each task: its focused tests red, then green; the full suite green (report the count). Task 4 ends with an
end-to-end turn through the fake claude: `tools/list`, an `act` that presses Pause, the reply streamed, the thread
saved. Task 6: headless Edge at 900, 400 and 340 px, dark and light, reduced motion. Task 7: Fred's live day.

## 8. Risks

- **A wrong act at `auto`**: the level, the always-yours list, the always-forwarded items, the caps, the audit and
  Undo bound it; Task 5 runs on one project first.
- **The D1 (b) lifts spend while Fred is away**: each is one press inside `super_acts_task_hour` (2) and
  `super_acts_day` (20), so a task gets at most 2 steps an hour past its supervisor's caps; every press is an `act`
  line, and a super Approve is `by` `super` in the task's `supervisor.jsonl`. Task 7 reads a day of them on one
  project before a second goes to `auto`.
- **Steered text** (a handoff that says "delete this task"): tool results are data by prompt; the always-yours list,
  the gates and the caps are code.
- **Cost creep**: `chat_turn_usd`, `chat_day_usd`, Sonnet by default, cache reads on a resumed session, a ledger row;
  Task 7 measures a real day.
- **CLI drift**: flags re-read on 2026-11-09; the start's tool list is kept on the turn, never refused; a call
  outside the list kills.
- **Two writers of the thread** (the turn thread and tool calls): one `chat_lock`, innermost; `tlock` is never taken
  while it is held.

## History

- 2026-11-09 - Written from the design (C1 to C5) against `plan-58` `d557f22`; CLI and env-var docs re-read; D1 to D3
  open. Plan only.
- 2026-11-09 - D2 and D3 closed (a) with Fred ("no need", "ok"); D1 open, explained (background = plan 58's passes acting with no message from Fred).
- 2026-11-09 - D1 closed (b), bounded, with Fred: (a) meant watching Console all day. He chose Approve capped steps,
  Retry after a second FAIL and Handle stalls, not Run anyway on a pace hold. Task 1 gains the `super` Approve
  (`superact.lifted`, no window reset, one step past the work cap in `start_step`) and `superact.lift`; Task 5's
  `check` keeps the one lifted act; 3.6 lists what stays his. Found while reading plan 44: a stall's own suggestion
  is Stop, so it stays his; a chain stopped mid-way at the work cap has no suggestion and stays his.
