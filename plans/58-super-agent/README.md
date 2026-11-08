# Plan 58: Super agent v1. One pass at a time sorts what needs Fred across every task; no acts. Guided implementation plan

> Design: [../../design/brainstorm/2026-11-08-super-agent.md](../../design/brainstorm/2026-11-08-super-agent.md),
> slice 1 of section 9 (sections 3.1 to 3.4, 3.6 to 3.8; D4, D5, D-b, D-c, D-e, D-f, approved by Fred 2026-11-08).
> BRAINSTORM D18 and 7.7. Master: [../../PLAN.md](../../PLAN.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).
> Lands on plans 17 (tasks), 44 (the supervisor pass, its ledger and `compact._ask`), 50 (the Usage block), 52 (the
> levels, the decision card, `Hub.actions`), 54 (`paths.write_text_atomic`).

Status: **reviewed 2026-11-08, plan only, decisions closed 2026-11-08** (section 5: D4 b, the rest a; written for each recommended option
(a), the task files mark the lines another answer changes). Baseline `84b9260` (docs only since `9b6f988`, 1167 tests
OK). Nothing is implemented and no product file was touched by writing this plan. Building waits for D1.

Review baseline: `7c5e149`. Read [the review contract and JEV assessment](08-review-and-jev.md) before implementing
any task. It fixes coverage, expiry, stale advice, persistence/accounting, evidence and scheduling gaps; its R1-R9
requirements are mandatory. Tasks 5 and 6 now give corrected implementation steps instead of unsafe copy-paste
recipes. Existing exact-value examples must include the added basis/coverage fields. JEV remains a separate,
optional shadow evaluation (D12), not a replacement for this pass or a new dependency of slice 1.

| # | File | Delivers | Depends on |
|---|---|---|---|
| 1 | [01-settings-and-files.md](01-settings-and-files.md) | `console/superagent.py` part 1 (settings, gates, the `super/` files, the audit log), config defaults, the tuning whitelist, the `super` kind file, the `orders.md` seed at start | none |
| 2 | [02-items-and-queue.md](02-items-and-queue.md) | part 2 (pure): the needs items and their keys, the always-forward reasons, `sync`, the queue order and cards; two golden tables | 1 |
| 3 | [03-digest-and-pass.md](03-digest-and-pass.md) | part 3 (pure but `run`): card text, live task lines, signals, fingerprint, digest, prompt, schema, answer check, model, `run`; the fake claude branch | 1, 2 |
| 4 | [04-ledger-and-usage.md](04-ledger-and-usage.md) | the `super` section of usage-days.json (reserve, settle, read), GET /api/usage `super`, the Usage page block | 1 |
| 5 | [05-hub.md](05-hub.md) | `Hub`: state at start and restart recovery, the tick (events, debounce, ceiling, sweep), admission, the pass thread, the result | 2, 3, 4 |
| 6 | [06-routes.md](06-routes.md) | `GET /api/super` (the ranked queue, read only) and `POST /api/super` (pause, resume, sort); end-to-end tests through the fake claude | 5 |
| 7 | [07-live-check-close.md](07-live-check-close.md) | Fred's live check with real passes (the cost per pass measured), docs, CLAUDE.md line, PLAN.md row | 1-6 |

Tests first in every task, one commit per task, `py -m unittest discover -s tests` at each boundary (about 10 minutes:
run it in the background and read the finished output), `node --check web/app.js` after the web change (Task 4).
Other chats edit `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md`, `web/app.js`, `console/server.py` and `console/__main__.py` in
parallel: anchored edits, stage explicit paths, and stage only this plan's hunks of a shared file non-interactively
(`git hash-object -w` of HEAD's file plus this hunk, then `git update-index --cacheinfo 100644,<blob>,<path>`; `git
add -p` is interactive and not available here). Plan numbers collide between chats: run `ls plans` before any new plan
file.

## 1. Goal and scope

Today every item that needs Fred lands unranked in one Needs you pin, each costs a page switch, and the list grows with
every running task (design section 1, gaps G3 to G5). This plan adds the layer above tasks that sorts those items before
they reach him: one bounded pass at a time, on events, over a digest that code rebuilds each time, with a notes file
the pass rewrites and Fred's standing orders. Each pass reviews a bounded selection, groups compatible items, puts
items that lose nothing by waiting into Later, and writes one recommendation line per item. Code decides what counts as
needing Fred, what is always forwarded, the order and every limit; the model's answer only annotates the queue.
All live items remain visible over HTTP; overflow is reported and selected fairly on subsequent eligible passes.

Done when (design section 9, slice 1): real items come back ranked and annotated over HTTP, with truthful coverage;
a failed pass leaves them unranked with the reason; the review regressions pass and cost/latency by model and input
size are measured (Task 7). A single pass is not promised to review more than its item/byte limit.

**Out of scope (the later slices of the design, and its never list):**

- No act of any kind: the answer schema has no `act` field and no `order` field (D11; section 3.14); the super agent
  never calls a lever, a route or `Hub._supervisor_dispatch`. Acts, Undo and order proposals are slice 3.
- No window: no super agent row or page, no cards answered in place, no Later fold, no Since you looked, no roll-up
  list, no box chip, no header or tray count (slice 2, after the mock is made and locked). The only web change is the
  Usage page block (Task 4, D7), which reuses plan 50's block.
- No message to the super agent (the box is slice 2); `POST /api/super {action: "sort"}` stands in (D6).
- No jobs, stages or job items (slice 4), no worktrees, merge items or conflict items (slice 5).
- No replay command (D5) and no watchdog signal that needs git or timing data the service does not keep per step (D4).
- No Models page card for the new settings (D9): `config.json` by hand, through the existing whitelist.
- No change to the task supervisor, its wakes, its ledger section or its non-goals; no change to `server.task_row`,
  `Hub.actions`, the snapshot or any task path. No write in a project folder, no write outside `~/.claude/console/`, no
  edit of another CLI's config.

## 2. Facts checked 2026-11-08 (at `84b9260`)

**The pass command.** No CLI flag is added. The pass is `compact._ask` with `safe_mode=True` and a positive `max_cost`,
exactly the plan 44 supervisor pass (`supervisor.run`, `console/supervisor.py:625`): `claude_cli.brief_command` (`-p
--model M --effort low --permission-mode dontAsk --disable-slash-commands --strict-mcp-config --settings
{"disableAllHooks": true} --no-session-persistence --output-format json --json-schema <schema> --tools "" --max-turns
6`) plus `--max-budget-usd` and `--safe-mode --disallowedTools mcp__*` (`console/compact.py:251-296`). Its docstring:
safe mode means "no CLAUDE.md, memory or plugin rides along". `_ask` takes its timeout from `cfg["brief_timeout_s"]`;
callers pass a copied cfg (`supervisor.py:635`). It raises only `compact.BriefError`; its messages read "the brief
took longer than N s", "cannot start claude: ...", "the brief returned no JSON: ...", "the brief failed: <subtype>",
"claude exited with code N", "the brief returned no structured output". `info["cost"]` is set before any raise (None
when unknown, 0.0 when the process never started).

**The needs set.** `Hub.snapshot()` (`console/server.py:551`) holds `self.lock`, builds `snap["tasks"]` from
`server.task_row` (`:4181`, module level) and counts as needing Fred: task rows in group `needs` plus session rows in
group `needs` that have neither `task` nor `chat_task` (`:575-580`). A task row is `needs` when the task is waiting or
stuck, asks a STOP question, shows a hand-off hint, holds a saved handoff with no follow-up, or has a pending supervisor
card (`supervisor.attention`, statuses suggest, held, escalate, refused, uncertain); an accepted task is `done`. A
session row is `needs` for a state in `state.NEEDS_YOU` (stop, blocked, stall, failed, interrupted, verify_failed), a
red gauge outside DONE, or a handed-off auto handoff (`console/state.py:513-526`).

**What the always-forward list reads** (design 3.4): `why == "confirm Fable"` (`tasks.py:898`, `server.py:1062`),
`why` starting `verify failed twice` (`tasks.py:703`), `why` starting `supervisor work cap reached` (`server.py:3290`),
the spend cap error `supervisor spend cap reached` (`server.py:1921`, `:2680`), `tasks.held(task)` (`why` ending ` over
its pace`, `tasks.py:755`), a current step with `limit` (a usage limit, `server.py:3574`), the uncertain statuses (a
pending card's, a decision's `taken`, a message's, `server.py:83`, `:1465`, `:1579`), and a decision with no `default`
(`task["decision"] = {q, options [{key, text}], default, step, asked, taken?}`, `tasks.py:676`, `server.py:1555`).

**Levels and cards.** `supervisor.policy(cfg, task, now)["mode"]` is a task's effective level (its own, else its
project's, else the global one; `supervisor.py:67`). `Hub.actions(task)` (`server.py:1109`, plan 52 Task 6) returns
the aligned `state` and the row `line` as read-only data; GET /api/task calls it without `tlock`. A decision's default
is taken at `auto` after `decision_timeout_s` from `decision["asked"]` (`server.py:1568`).

**Spend.** The supervisor's ledger is the `supervisor` section of `usage-days.json` (`usage.py:398-500`):
`_supervisor_used(records, task=, day=)` sums settled costs plus held reservations (`reserved` and `unknown`);
`record_supervisor` settles once, keeps an unknown cost's reservation and refuses a conflicting second settlement.
`save_days` keeps every other key of the file (`usage.py:352`). `supervisor.spend_view(records)` folds any records that
carry `day` (`supervisor.py:735`). GET /api/usage `supervisor` is built in `Hub.usage_report` (`server.py:414`); the
web block is `usageSupervisor` (`web/app.js:2314`), drawn at `:2753`, tested by `test_usage_shows_supervisor_spend`.
The only real passes on record are plan 44's: four Haiku passes settled at $0.0015 to $0.0028 (usage-days.json
`supervisor`, 2026-10-20). A super agent pass reads more (every item and every live task); Task 7 measures it.

**Kind files.** `kinds.NAMES` (`kinds.py:13`) holds the worker kinds then prep, supervisor and planner;
`kinds.ensure` (called once at start, `__main__.py:95`) seeds missing files from `dotclaude/console/kinds/`;
`kinds.text` reads `<home>/kinds/<kind>.md` else the seed; `kinds.body_of` drops the head line. The window's Role
files card lists only `cfg.kinds` plus verify and fix, so a new pass kind is edited by hand or through GET and POST
`/api/kind`, like `supervisor.md`. `tests/test_kinds.py:18` pins `NAMES`.

**Settings.** `paths.DEFAULTS` (`paths.py:10`), `tuning.TUNING` (key -> group, unit, min, max), `tuning.KEYS`,
`tuning.SUPERVISOR_MODELS` (fixed aliases), `tuning.WHOLE` (whole-number units), `Hub.reload_tuning` (rereads the
whitelisted keys of `config.json` on GET /api/config when its mtime changed). The window's Tuning tab draws only keys
listed in its own `TUNE` table (`app.js:2631`), so a key added to `TUNING` alone shows nowhere.
`tests/test_tuning.py:31` pins the whitelist as an exact set.

**A masking trap (found while writing this plan; plan 44's code, not changed here).** `supervisor.append_log`
(`supervisor.py:197`) masks the dumped JSON text. When a string value ends in a `key=value` secret (a reason ending
`set token=abc`), `redact.mask`'s `\S+` value swallows the closing quote and the comma, and the line no longer parses
(checked with `redact.mask` on 2026-11-08: `{"reason": "set token=*** "phase": ...`). `supervisor.read_log` turns
that line into a corruption marker, so the restart reconcile (`Hub.reconcile_supervisor`, `server.py:1736`) no longer
sees the record: a lost `result` line reads as a pass the restart cut, and its pending card is not rebuilt. Plan 58's
`append_log` masks every string of the record before dumping it. The plan 44 fix is Fred's to schedule.

**Hub threads and tests.** `Hub.run` (`server.py:529`) loops every `POLL_S` (1 s): `poll_once`, `auto_steps`,
`advance` (which ends with `_supervisor_tick`), `read_costs`, `tick`. `tlock` (an RLock) is taken before `self.lock`
wherever both are held. No test starts the hub loop; `tests/test_supervisor_server.py` builds `server.Hub(cfg, folder,
exe=fake)` with a scratch `CC_CONSOLE_HOME`, freezes `sup_clock` and patches `supervisor.run` (`WakeTest`, `:157`);
`tests/test_server.py:197` (`RunServerTest`) serves HTTP on port 0 with `tests/fake_claude.py`. The fake's `prep()`
routes a `--json-schema` call by its schema's properties (`decision`, `scope`; `fake_claude.py:111-117`).

## 3. The contract

### 3.1 Files and places

```
console/superagent.py          new: settings, blocked, status, the super/ files (Task 1); items, always_reason,
                               task_kind, sync, last_at, queue (Task 2); describe, live_tasks, task_line, signals,
                               fingerprint, levels, trigger_words, item_block, digest, build_prompt, SCHEMA, shape,
                               check, pass_model, run (Task 3)
dotclaude/console/kinds/super.md   the pass's role text (Task 1)
~/.claude/console/super/       state.json, notes.md, orders.md, super.jsonl (and super.1.jsonl), last-prompt.md
~/.claude/console/usage-days.json  a new "super" section beside "supervisor" (Task 4)
console/kinds.py, console/paths.py, console/tuning.py, console/__main__.py   one line or entry each (Task 1)
console/usage.py               load_super, reserve_super, record_super, super_spent; a `section` keyword (Task 4)
console/server.py              Hub: super state, _super_* methods, super_view, super_action, usage_report; Handler
                               routes (Tasks 4-6)
web/app.js                     usageSupervisor(data, key) and one call (Task 4)
tests/test_superagent.py, tests/test_superagent_server.py   new; additions to test_kinds, test_tuning, test_usage,
                               test_web; tests/fake_claude.py gains the super branch (Task 3)
```

`console/superagent.py` imports `compact`, `kinds`, `paths`, `redact`, `tasks` and `state.NEEDS_YOU`; it never imports
`server` or `supervisor` (a test asserts it). `server.py` imports it.

### 3.2 Settings (design 3.7)

| Key | Default | Range | Meaning |
|---|---|---|---|
| `super_model` | `haiku` | fixed | the pass model |
| `super_judge_model` | `sonnet` | fixed | the model when submitted items include a stuck task, including one behind a suggestion (D-b clarified) |
| `super_debounce_s` | 20 | 0 to 300 | each event pushes the pass this much later... |
| (constant `MAX_WAIT_S`) | 120 | | ...but never past this long after the wake's first event |
| `super_sweep_s` | 900 | 300 to 3600 | while a task runs, a sweep this often; skipped when the fingerprint is unchanged (D-c) |
| `super_timeout_s` | 120 | 10 to 600 | one pass's timeout |
| `super_notes_lines` | 40 | 0 to 200 | lines `notes.md` keeps (0: no notes) |
| `super_pass_usd` | 0.20 | 0 to 1 | the most one pass may spend (`--max-budget-usd`) |
| `super_day_usd` | 1.00 | 0 to 20 | the most all passes of a local day may spend |

`superagent.settings(cfg) -> (settings, errors)` checks them like `supervisor.policy`: a bool, a wrong type or an
out-of-range value takes the floor (0.0 for money) and adds `"<key> must be a whole number between L and H"` or `"<key>
must be a number between L and H"`; a model other than its alias adds `"<key> must be <alias>"` and is forced back.
Any error blocks every pass. **Off** is a zero `super_day_usd` or `super_pass_usd`: no new mode word (design D-e spirit;
Fred's `super_day_usd: 0` turns it off). The keys join `tuning.TUNING` (group `super`; unit `lines` joins `WHOLE`) and
the two models join `tuning.SUPERVISOR_MODELS`, so `POST /api/config/models` accepts them and `Hub.reload_tuning`
rereads a hand edit; no window shows them yet (D9).

### 3.3 Items and keys (design 3.3)

`superagent.items(snap, by_id)` takes a `Hub.snapshot()` and `Hub.tasks`, pure. An item:

```
{"key": "task:<id>:<event>" | "session:<id>:<event>", "type": "task" | "session", "id", "kind", "always",
 "project", "project_dir", "title", "label"}
```

- Task items: every row of `snap["tasks"]` in group `needs` whose task is in `by_id`, in the snapshot's order. Session
  items after them: every row of `snap["sessions"]` in group `needs` with neither `task` nor `chat_task`.
- `kind` of a task (`task_kind`, first that holds): `suggestion` (the row's `supervisor.attention`), `decision` (the
  row asks and the waiting task has a `decision` dict), `question` (the row asks), `hand_off`, `handed` (state handed),
  `failed_twice` (stuck, `why` starts `verify failed twice`), `stuck`, `hold` (any other wait), `chat` (a chat task),
  else the state. `kind` of a session: its state when in `NEEDS_YOU`, `context` for a red gauge, else `handed`.
- The **event** is 16 hex of canonical JSON's SHA-256: kind, state, why, current attempt, asks/hand-off, the full
  decision, pending supervisor action/status/error and hard-forward reason; sessions also include STOP text.
  [R3](08-review-and-jev.md#r3-a-decision-basis-not-an-age-or-cost-hash) defines the exact basis. Time, cost or
  `updated` alone never change it. Changed choices or policy invalidate old advice.
- When a key leaves the live set (Fred answered here, in VS Code or in a terminal), `sync` forgets its first-seen time
  and its annotation at the next tick, and GET /api/super never shows it again.

### 3.4 Always forwarded (design 3.4)

`superagent.always_reason(task)`, first that holds; `""` for a session item:

| Reason | When |
|---|---|
| `Fable confirm` | state waiting and `why == "confirm Fable"` |
| `second verify FAIL` | state stuck and `why` starts `verify failed twice` |
| `work cap` | `why` starts `supervisor work cap reached` |
| `spend cap` | the pending supervisor card's `error` is `supervisor spend cap reached` |
| `pace hold` | `tasks.held(task)` |
| `usage limit` | the current step has `limit` |
| `uncertain dispatch` | the pending card's status, the decision's `taken` or any message's status is `uncertain` |
| `decision without a default` | state waiting, `why` starts `asks: `, the decision is not taken and has no `default` (a plain question has none either, D10) |

An always item is forward whatever the answer says (never batch, never later), its rank is ignored, its `say` kept.

### 3.5 `state.json`

```json
{"v": 1, "n": 12, "paused": false,
 "seen": {"<key>": 1800000000.0},
 "reviewed": {"<key>": 12},
 "ann": {"<key>": {"do": "forward|batch|later", "rank": 2, "say": "...", "why": "...", "batch": "", "until": null, "basis": "..."}},
 "last": {"n", "at", "ok", "error", "model", "cost", "turns", "ms", "items", "trigger", "fingerprint"},
 "digest": ["up to three lines of the last ok pass"],
 "claimed": null}
```

`seen`: when each live key was first seen (the age, oldest-first, and "new" after the last pass). `reviewed` tracks
coverage; `ann` merges validated current entries and preserves unseen/rejected entries' still-valid advice.
Failed passes do not erase annotations. `claimed`: `{n, pid, at, model,
handles, bases, policy_hash, trigger}` from the claim to the result; restart reconciles it with the audit and
ledger (3.11). Whole-file
saves through `paths.write_text_atomic`. Missing state is fresh; corrupt, unreadable or unsupported-version state
blocks paid passes and exposes an error. Pause must not silently reset. R4 defines recovery and validation.

### 3.6 Wakes (design 3.1)

`Hub._super_tick(now)` runs every `SUPER_POLL_S` (5 s) from `Hub.run`, under `tlock`, and never raises:

1. `live = items(self.snapshot(), self.tasks)`; `sync(state, live, now)` returns the new keys, the Later keys whose
   `until` has passed (each once), and whether the state changed (then it is saved).
2. Events: each new key, each returned Later key, each task that was running at the last tick and is now done,
   stopped, stuck or handed (none at the first tick after a start).
3. Events arm the one pending wake: `due = min(now + super_debounce_s, first + MAX_WAIT_S)`, `first` being the wake's
   first event. Resume and Sort make it due at once.
4. No event, no pending wake, a task running and at least one item: a sweep when `super_sweep_s` has passed since the
   last sweep and since the last pass; it arms a wake only when `fingerprint(...)` differs from the last pass's.
5. Admission (3.7) when the wake is due and no pass runs.

The wake lives in memory only; a restart with unchanged valid state does not cause a pass by itself. Use monotonic
time for scheduling; R9 adds one wake when a blocked gate becomes eligible and for changed input/policy bases.

### 3.7 The pass (design 3.2, 3.4, 3.7)

**Gates, in order** (a blocked wake is dropped; Resume, Sort or the next event arms another):
`blocked(settings, errors, state, exe)` (settings error, off, paused, no claude.exe); no item (nothing to sort, Sort
included); then `usage.reserve_super(folder, pid, day, super_pass_usd, super_day_usd)`: reserved -> go; cap, duplicate
or error -> a `refused` audit line and no call. The reservation is the lesser of `super_pass_usd` and what is left of
the day (settled plus held), and it is the pass's `--max-budget-usd`.

**Input** (built once under `tlock`, then the thread runs outside every lock): the items described for their cards
(`describe`, from `Hub.actions(task)`, the level and `decision_timeout_s`) selected least-recently-reviewed first
(R2; display order is independent), each selected task item
with its open questions (`tasks.open_questions` over `tasks.read_brief`); the live task lines; the signals (D4); the
orders; the cut notes; the head (pass number, local time, trigger words, spend today of the day limit, levels). The
digest fits at most `ITEMS_MAX` (30) whole items as handles `I1`, `I2`, ... (the answer names handles, code maps them
back); overflow is counted and remains visible. Reserve space for bounded orders first. The prompt is the masked
`super` kind body (slots `$you`, `$You`, `$lines`), the schema reminder,
then the digest. The whole prompt is bounded to 48 KiB UTF-8 (R7). It is saved as `last-prompt.md` and its SHA-256
goes in the claim line. Incomplete evidence is explicit and cannot justify Later or batching.

**Model** (`pass_model`): `super_judge_model` when the submitted items include a task whose state is `stuck`, else
`super_model`. The pass folder (cwd) is `<home>/super` (D3).

**Answer** (`SCHEMA`, checked by `shape` then `check`; untrusted):

```json
{"items": [{"key": "I3", "do": "forward|batch|later", "rank": 1, "say": "one line", "why": "one line",
            "batch": "accept-1", "until": "2026-11-08T16:30"}],
 "digest": ["one to three lines"], "notes": "the rewritten notes"}
```

| Rule | Outcome |
|---|---|
| not an object, an unknown top-level field, `items` or `digest` not a list, `notes` not text (`shape`) | no answer: the pass failed (`the pass gave no answer (<why>)`) |
| an entry not an object, an unknown handle, a second entry for a handle, `do` not forward, batch or later, `rank` not a whole number from 1 | that entry dropped (`dropped` in the audit) |
| `batch` not `[a-z0-9][a-z0-9-]{0,31}` on a batch entry | the entry becomes forward (`trimmed`) |
| Later without a nonblank reason, or `until` not a local `YYYY-MM-DDTHH:MM` after now and at most a day ahead | forward (`trimmed`); never indefinite Later |
| active auto-default decision, or incomplete evidence | forward; never later or batch |
| an always item | forward, batch and until removed (`trimmed`: `always forwarded: <reason>`) |
| a batch with one member, or different kind/level/question/options/default/answer action | each member becomes forward (`trimmed`); batch names are scoped to this pass |
| `say`, `why` | masked, clipped to 200 characters; digest lines masked, clipped, at most 3; notes cut by `cut_notes` |

An ok pass merges current checked annotations. Rebuild live bases at completion, without waiting for a tick;
stale entries are discarded, and any stale submitted item prevents publishing the global digest/notes. Policy
changes discard the whole answer. A failed pass (any `run` error, a bad shape,
the digest failing, a restart) changes none of them and sets `last.ok = false` with the error, which unranks the queue.

**Errors as the queue shows them** (`last.error`): the `BriefError` text with "the brief" read as "the pass" (`the pass
took longer than 120 s`, `the pass failed: error_max_turns`, `claude exited with code 3`, ...), `the pass gave no
answer (<why>)`, `the digest failed: <Exception>: <text>`, `the service restarted during the pass`, `claude.exe not
found`, `no budget for the pass`.

### 3.8 Queue order (design 3.4)

`queue(items, state, now, ranked)` returns `{"queue": [card], "later": [item]}`; each item gains `age_s`, `new`, `do`,
`rank`, `say`, `why`, `batch`, `until` (local `YYYY-MM-DDTHH:MM` or ""). `ranked` is `status(...)[0]`:

- **Ranked**: always items first, oldest first; then annotated items by rank (ties oldest first); then unannotated
  items first seen before the last pass, oldest first; then items first seen after it, oldest first, `new: true`. A
  later item with a valid future `until`, reason and complete evidence leaves for `later` (sorted by until). A
  batch is one card where its best-placed member sits, its other members inside it.
- **Unranked**: always items first, then the rest, both oldest first; no annotation field set, no card holds two items.

`status(settings, errors, state, spent, exe) -> (ranked, why)`: `blocked(...)`, then `over the day limit ($X.XX)` when
today's settled plus held spend reaches `super_day_usd`, then `no pass yet`, then the last pass's error; else `(True,
"")`.

### 3.9 `GET /api/super` (read only: starts nothing, writes nothing)

```json
{"state": "ranked" | "unranked", "why": "", "paused": false,
 "sorting": null | {"n": 13, "items": 4, "since": 1800000020.0},
 "due": null | 12,
 "queue": [{"batch": "", "rank": 1, "items": [{"key", "type", "id", "label", "project", "project_dir", "title",
            "kind", "always", "ask", "options", "default", "left_s", "level", "supervisor", "source",
            "age_s", "new", "do", "rank", "say", "why", "batch", "until"}]}],
 "later": [item], "digest": ["..."], "notes": "...", "orders": "...",
 "last": {"n", "at", "ok", "error", "model", "cost", "turns", "ms", "items", "trigger", "fingerprint"} | null,
 "spend": {"today": 0.031, "passes": 9, "day_limit": 1.0, "pass_limit": 0.2},
 "counts": {"queue": 5, "later": 2, "always": 1, "new": 1},
 "coverage": {"live": 7, "last_submitted": 6, "never_reviewed": 1}}
```

`digest` is empty while unranked. `ask` is one masked line (`Hub.actions(task)["line"]`; `asks: <question>` or `hand
off: <hint>` for the row-only kinds; the state text and STOP question for a session). `options` and `default` are a
decision's texts; `left_s` is the seconds before the default is taken, at `auto` only. This is the data contract slice 2's
window reads; it may grow fields, never lose these.

GET validates current bases and loaded annotations, masks/cuts notes and display metadata, and reports ledger or
storage errors as unranked. Derive spend/status from one validated ledger read; unreadable spend is unknown,
not zero. It does not persist cleanup or trigger work.

### 3.10 `POST /api/super` (guarded like every POST: Host and `X-CC`)

| Body | Effect | Answer |
|---|---|---|
| `{"action": "pause"}` | `paused: true`, the pending wake dropped; a running pass finishes and its answer is kept, the queue shows unranked | 200, the GET view |
| `{"action": "resume"}` | `paused: false`, a wake due at once | 200, the GET view |
| `{"action": "sort"}` | a wake due at once (D6) | 200, the GET view; 409 `paused: resume first` while paused |
| anything else | nothing | 400 `action: pause, resume or sort` |

Each accepted action is durably recorded before acknowledgement. A persistence failure returns 503 and blocks
admission locally; it never returns 200 for an unsaved Pause. R4 specifies ordering and restart behavior.

### 3.11 Spend, audit and restart

- **Ledger**: the `super` section of `usage-days.json`, apart from the `supervisor` section (neither spends the
  other's allowance). Records `{day, kind: "super", reserved, cost, status}` keyed by a uuid4 pass id. A known cost
  settles (even above the reservation); an unknown cost keeps the reservation as `unknown` (never freed); a ledger that
  cannot be written leaves the reservation held, logged, and the next reservation refuses while it stays unreadable.
- **GET /api/usage** gains `super: {days, today, day_limit, pass_limit, error}` (`supervisor.spend_view` over the
  section); the Usage page draws a "Super agent passes" block like plan 50's (D7).
- **super.jsonl** (append only, masked, one JSON object per line, `ts` first): `claimed` (`n`, `pid`, `trigger`,
  `model`, `handles`, `bytes`, `prompt_hash`, `reserved`), `result` (`n`, `ok`, `error`, `cost`, `turns`, `ms`, `kept`,
  `dropped`, `trimmed`, `out`: the raw answer), `refused` (`status`, `error`), `pause`, `resume`, `sort`. At 5 MB it
  moves to `super.1.jsonl`, replacing the older copy (D8).
- **Restart**: reconcile by pass UUID across state, both log files and ledger reservations, including orphans.
  A durable result settles once; only missing results become unknown. Already-settled costs remain unchanged.
  Never replay a model call. R4/R5 define interrupted writes, blocked storage and retained claims.

### 3.12 Redaction (`redact.mask`) at every landing

| Where | Rule |
|---|---|
| the digest and `last-prompt.md` | every text it takes is masked when taken (`describe`, `task_line`, `signals`, `read_orders`, `cut_notes`) |
| `state.json` `ann`, `digest`; `notes.md` | masked and clipped by `check` and `cut_notes` |
| `super.jsonl` | every string of the record masked by `append_log` before the line is dumped (not the dumped line: section 2) |
| GET /api/super | mask display metadata and hand-edited notes as well as card text; preserve usable opaque IDs |

### 3.13 Migration and behaviour change

- New files only. The first start seeds `super/orders.md` (two comment lines). `state.json` appears at the first tick
  that sees an item. No task file, step file or existing config key changes; a `config.json` without the new keys
  takes the defaults.
- `kinds.ensure` seeds `<home>/kinds/super.md` at the first start, as it seeds every missing kind file.
- **Behaviour change Fred should know (D2 a, still unapproved):** from the first item after the upgrade,
  Haiku/Sonnet passes run on their own against a $1.00 daily admission allowance; provider overshoot is recorded.
  `super_day_usd: 0` in `config.json` turns them off. D2 must be resolved before enabling this behavior.

### 3.14 Differences from the design, all smaller or stricter

1. The answer has no `act` and no `order` (slice 3). Its contract reminder is code, not kind-file text, so slice 3 can
   add both without a Reset of an edited `super.md` (plan 56's precedent).
2. Items are the Needs you set only; the four job items join with slices 4 and 5.
3. Two watchdog signals of design 3.6 (D4); the no-file-change spend signal comes with the pause act (slice 3).
   [D4 b, Fred 2026-11-08] All of design 3.6 in slice 1, with a timed git read per running task on each sweep
   (Task 3 note above `signals`).
4. No message wake (slice 2); Sort stands in (D6). No Since you looked or `seen` mark (slice 2). No replay (D5).
5. The digest names items by handle (I1, I2, ...), not by key.
6. A pass never runs with no item; `MAX_WAIT_S` bounds debounce, not time waiting behind a running pass or a closed
   gate. One pass's reservation is the lesser of `super_pass_usd` and the day left; reported overshoot is charged.
7. Later requires an expiring local time and a reason. Off is a zero limit, not a mode.
8. Review R1-R9 tighten correctness without adding acts. JEV is separately proposed under D12.

## 4. Golden tables

### 4.1 Items (Task 2 asserts every row)

Fixture: each task from `tasks.new_task` with one code step (plus the verify `plan_steps` adds), current 1, its row
from `server.task_row(task)`; session rows written by hand with the snapshot row's keys. The decision is `{"q": "Which
file?", "options": [{"key": "1", "text": "style.css"}, {"key": "2", "text": "app.js"}], "default": "1", "step": 1,
"asked": T0}`.

| # | Task or session | Item kind | always |
|---|---|---|---|
| 1 | waiting, `asks: Which file?`, the decision | decision | "" |
| 2 | as 1, the decision without `default` | decision | decision without a default |
| 3 | waiting, `asks: Which file?`, no decision | question | decision without a default |
| 4 | waiting, `confirm Fable` | hold | Fable confirm |
| 5 | waiting, `sonnet over its pace` | hold | pace hold |
| 6 | waiting, `plan ready: confirm` | hold | "" |
| 7 | stuck, `verify failed twice: test_x` | failed_twice | second verify FAIL |
| 8 | stuck, `step 01 failed` | stuck | "" |
| 9 | waiting, `supervisor work cap reached ($5.00 of $5)` | hold | work cap |
| 10 | done, pending card `{wake 3, status suggest, decision finish}` | suggestion | "" |
| 11 | running, pending card `{wake 4, status uncertain}` | suggestion | uncertain dispatch |
| 12 | stuck, `step 01 failed`, current step `limit: "claude/sonnet"` | stuck | usage limit |
| 13 | waiting, `plan ready: confirm`, a message `{status uncertain, mode answer}` | hold | uncertain dispatch |
| 14 | handed, `handoff_note` set, no `handoff_to` | handed | "" |
| 15 | running, no card | (no item) | |
| 16 | done and accepted | (no item) | |
| 17 | session, group needs, state failed, no task | failed | "" |
| 18 | session, group needs, state running, red gauge | context | "" |
| 19 | session, group needs, `task` set | (no item: it counts as its task) | |
| 20 | session, group replied | (no item) | |

Keys: rows 1 to 14 built twice give equal keys; changing `updated` or a step's cost keeps the key; changing `why`,
adding an attempt to the current step, or a new pending wake on row 10 changes it.

### 4.2 Queue order (Task 2)

Items (key: kind, always, first seen): G decision, `decision without a default`, T0+90; A hold, `Fable confirm`,
T0+100; B decision, T0+110; C stuck, T0+120; D hold, T0+130; E hold, T0+140; H hold, T0+150; I hold, T0+160; F
question, T0+300. Last pass ok at T0+200. Annotations: A later rank 9; B forward 3 "b"; C forward 1 "c"; D batch
`acc` 2; E batch `acc` 4; H later 5 until T0+600. Now T0+400.

| Case | Cards (in order) | Later |
|---|---|---|
| ranked | G; A (do forward, say kept); C; [D, E]; B; I; F (new) | H |
| ranked, now T0+700 (H's until passed) | G; A; C; [D, E]; B; H; I; F (new) | none |
| unranked | G; A; B; C; D; E; H; I; F, one item each, no say, no new | none |

## 5. Decisions for Fred

Recommended option first; the plan is written for it. The brainstorm closed D1 to D6 and D-a to D-f; these are what it
did not.

| # | Question | (a) recommended | (b) | Taken |
|---|---|---|---|---|
| D1 | When to build | after plan 52's live check, as design section 9 says: the queue stands on plan 52's levels, decision card and finish card, and a pass ranks what those produce | now: this plan reads `Hub.actions` and changes no plan 52 path, so it could be built and checked on scratch services first | (a) |
| D2 | Passes at the upgrade | on: `super_pass_usd` $0.20, `super_day_usd` $1.00 admission allowance; Haiku or Sonnet by submitted work; actual capacity must be measured in Task 7; `super_day_usd: 0` turns them off | off (`super_day_usd` 0) until you set a limit by hand | (a) |
| D3 | The pass's folder (cwd) | `<home>/super`: no project of yours is the cwd of a pass that reads every project, and safe mode loads no CLAUDE.md anyway | the first project in `config.json` `projects` | (a) |
| D4 | Watchdog signals in slice 1 | two, from data the service keeps: a running step in it for more than twice the median of its kind's ended steps (3 or more), and the same verify failure twice. Spend with no file changed needs per-step git timing the service does not keep; it comes with the pause act (slice 3) | all of design 3.6 now, adding a timed git read per running task to every sweep | (b) |
| D5 | Replay (`py -m console --super-replay PASS`) | slice 3, with the acts it is there to check; slice 1 keeps the last prompt in `last-prompt.md` and each pass's prompt hash and byte size | now, which needs every pass's digest archived | (a) |
| D6 | A way to run a pass by hand | `POST /api/super {"action": "sort"}`, for the live check now and the window's Sort button later | none until the box (slice 2) | (a) |
| D7 | The Usage page | its own block "Super agent passes", drawn by plan 50's function with a `key` argument | one block with a second row for the super agent | (a) |
| D8 | `super.jsonl` growth | moved to `super.1.jsonl` at 5 MB (one older copy kept) | never rotated | (a) |
| D9 | The settings in the window | none in slice 1: `config.json` by hand, reread on the window's GET /api/config or at start; a Models page card with slice 2 | a card now, like plan 50's | (a) |
| D10 | A STOP question with no options | always forwarded, like a decision without a default: nothing else ever answers it | rankable, and a pass may put it later | (a) |
| D11 | `act` and `order` in the answer now | no (slice 3; the contract reminder is code, so no Reset is needed then) | in the schema now and ignored | (a) |
| D12 | JEV for decisions/routing | corrected slice 1 first, then an explicitly enabled Command Code shadow evaluation with human labels; see [assessment](08-review-and-jev.md#4-recommendation-and-implementation-gate) | no JEV experiment | (a) |

D12 is proposed, not approved. Direct TypeSafe HTTP conflicts with the current no-network rule; the sticker
project's transport cannot be copied unchanged. JEV does not produce the prose this pass requires.

Decided by Fred, 2026-11-08:

- D1: (a) after plan 52's live check.
- D2: (a) passes on at the upgrade, $0.20 a pass, $1.00 a day.
- D3: (a) the pass runs in <home>/super.
- D4: (b) all of design 3.6's watchdog signals now, with a timed git read per running task each sweep; the task file's code is for (a), so the build writes the two added signals test first.
- D5: (a) replay in slice 3; slice 1 keeps last-prompt.md and each pass's hash and size.
- D6: (a) POST /api/super sort, later the window's Sort button.
- D7: (a) its own Usage block, Super agent passes.
- D8: (a) super.jsonl rotates to super.1.jsonl at 5 MB.
- D9: (a) settings in config.json by hand; the Models card comes with plan 59.
- D10: (a) a STOP question without options is always forwarded.
- D11: (a) no act or order in the answer until slice 3.
- D12: (a) slice 1 first, then a separately enabled Command Code shadow evaluation as its own later plan.

## 6. Verification at the end of every task

1. The task's tests were written first and failed for the intended reason before the code.
2. Focused: `py -m unittest tests.test_superagent` plus the test modules the task names.
3. Full: `py -m unittest discover -s tests` in the background, read the finished output; report the real count.
4. `node --check web/app.js` after the web change.
5. `git diff --stat` shows only the task's files; stage explicit paths; the commit message is the one the task names.
6. No test calls a paid provider, touches port 47770 or writes `~/.claude`: tests use a scratch `CC_CONSOLE_HOME`, a
   scratch Hub folder and `tests/fake_claude.py`, and `superagent.run` is patched in the Hub tests. Clocks are frozen
   at `T0 = 1_800_000_000.0` (2027), never near 1970 (`time.mktime` refuses times before the epoch on Windows).
7. Run the task's [review regressions](08-review-and-jev.md#5-acceptance-additions), including failure injection
   and stale-input checks. Do not treat old exact-value examples as permission to omit the review contract.

## 7. Status and history

- 2026-11-08: reviewed against `7c5e149`; R1-R9 correct expiry, overflow, stale advice, persistence, spend,
  model selection, evidence, batching and scheduling. JEV assessed from sticker-generator-simple `7d80561`
  and current primary documentation. D12 proposes a separate shadow evaluation through Command Code.
  Plan only; no runtime implementation or paid validation.

- 2026-11-08: written (plan only) from the approved design's slice 1 against `84b9260`; the seams read in
  `server.py`, `supervisor.py`, `usage.py`, `compact.py`, `state.py`, `kinds.py`, `tuning.py`, `paths.py`, the web
  Usage block and the test fixtures. No CLI flag is added (section 2). Decisions D1 to D11 open for Fred.
