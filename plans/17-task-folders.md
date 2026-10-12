# Sub-plan 17: Task folders, step chain and demand routing per step

> Master: [PLAN.md](../PLAN.md). Rules: [CLAUDE.md](../CLAUDE.md). Builds on [16-demand-routing.md](16-demand-routing.md)
> (demand route, `Hub.pull`, `Hub.auto_steps`), [03-levers.md](03-levers.md) (levers, misses), [08-cold-handoff.md](08-cold-handoff.md)
> (briefs) and [13-handoff-next.md](13-handoff-next.md) (handoff then next chat).

**State: design. Fred took option (a) on every decision of section 8, 1 to 20 (2026-10-12). The guided implementation plan
is the folder [17-tasks/](17-tasks/README.md): one file per task, no code until a task is executed.**

## 1. Goal

A task is a chain of steps. Each step is one fresh `claude -p` run on the model and effort its kind calls
for: scouting, lookups, bulk edits and test runs on Haiku or Sonnet, design and hard bugs on Opus, verification
one model above the step it checks. Each step ends with a handoff note that the next step reads. The service
(code, not a model) keeps the chain going: it checks every handoff before the next step starts, retries a broken
step once from the last good handoff, and marks the task stuck when that fails. Each task keeps its chain, its
handoffs and its context in one folder under the console's data folder. No subagents: every step is its own
`claude -p` process with the Agent tool removed.

## 2. Facts checked (2026-10-12, CLI 2.1.296, code.claude.com/docs/en/cli-reference)

- `--disallowedTools "Agent"` removes the Agent tool from the model's context (a bare tool name removes the
  tool; a scoped rule only denies matching calls). `--tools "Read,Grep,Glob"` restricts the built-in set (Prep
  already uses it). `--max-budget-usd` stops a print-mode run at a client-side estimate (headroom needed;
  v2.1.217+). `--max-turns` limits agentic turns in print mode. `--session-id`, `--name`, `--fork-session`
  are as plans 02 and 03 use them.
- A window run is one `claude -p --resume <id>` process per turn (plan 16): a step is therefore a run that
  never resumes, except a STOP answer or a retry, which are new turns of the same step session.
- The service already has everything a step needs: `runs.RunManager.start` (detached process, stream copy in
  `runs/<sid>.jsonl`, `run_started` / `run_ended` lines), `Handler._last_reply` (the full final message of a
  window run from its stream, not the hook's 120-character summary), verdicts from the hook (`VERDICT:` on Stop
  and SubagentStop), `STOP:` questions as a state, `Hub.levers` as the one gate, `Hub.auto_steps` in the hub
  loop, `routing.pick` / `routing.floor` and `levers.escalate_step` / `levers.miss_line`.
- Writing a file outside the project folder from inside an auto-mode run may be denied by the classifier
  (plan 02 saw denials for less). So the model never writes into `~/.claude/console/`: the service writes the
  handoff file from the step's final message (section 4.3). This also keeps the CLAUDE.md data rule for Claude's
  own runs.
- Fable in print mode: "When a Fable request there would bill to usage credits, Claude Code bills it without
  asking" and "Neither Fable model is the account-type default on any plan" (code.claude.com/docs/en/model-config,
  2026-10-12). So a step on Fable can spend credits with no prompt: code never picks Fable; only Fred does, with a
  confirm (section 4.8).
- The same page says rate-limit errors never trigger a model switch, and it says nothing about quantization or a
  model getting worse under heavy use. What is documented is usage limits per plan window (5 hours, 7 days, with
  Opus counted on its own on the claude.ai plans): heavy Opus use ends in a limit, not a weaker Opus. Section 4.8
  tracks the limit; the plan takes no position on quantization beyond "not documented".
- Older models stay selectable by full name: `--model` takes "a model alias, or a model name"; the model-config page
  lists `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-sonnet-4-5`,
  `claude-haiku-4-5`, `claude-opus-5`, `claude-sonnet-5` and names none as retired (2026-10-12). A name is not
  checked up front: a mistyped one fails on the first request. Whether the plan's usage counters treat an older
  model apart from the newest of its tier is not on the page: Fred watches `/usage` during the live check (item 11).

## 3. Non-goals check (BRAINSTORM section 2)

| Non-goal | What this design has | Verdict |
|---|---|---|
| Task graph | A list of steps run in order, one `current` index. The only change to the list at run time is one insert after a verify FAIL (a fix step, then a verify again). No branches, joins, dependencies or parallel steps. | Close to the line. Needs Fred's sign-off as a clarification of section 2: "a linear step chain is not a task graph" (D16). |
| Scheduler | Nothing is queued or timed. The hub loop that already runs `auto_steps` (plan 16) advances a task the moment its step's run has ended. A second task in a project that already has a running task is refused with a 409, not queued. | Fits. |
| Locks | No lock files. `task.json` is written whole through a temp file and `os.replace` (as `window.json`), by the one service. The "2 writers" warning and the one-task-per-project refusal stand in for a lock. | Fits. |
| Daemon with named pipes | The existing tray service, nothing new. A closed service leaves a step's run going (as any window run); at restart `reconcile` closes it and the chain goes on from `task.json`. | Fits. |
| Controller leases | `owner` is `service` (the loop advances) or `fred` (paused: clicks only). No expiry, no takeover. | Fits. |
| No model calls except through the harness CLIs | Every step is `claude -p`; the supervisor is Python. | Fits. |
| Hash-bound manifests | `task.json` records the start commit per step (as runs do), no hashes of files. | Fits. |

Needs Fred's sign-off beyond D16: the service starting the next step by itself across sessions (plan 16 (b)
took that decision within one session); the fix-then-verify insert, which makes the chain change at run time.
Without the insert, a verify FAIL simply marks the task stuck and Fred clicks Retry on the escalated route:
section 8, decision 6 offers both.

## 4. Design

### 4.1 Where task folders live

`~/.claude/console/tasks/<task-id>/`, with `CC_CONSOLE_HOME` overriding `~/.claude/console` as for every
other file (`paths.home()`). The task id has the shape of a Prep id, `YYYYMMDD-HHMMSS-xxxx` (`prep.new_id`).

| Place | For | Against | CLAUDE.md data rule |
|---|---|---|---|
| `~/.claude/console/tasks/` (chosen) | One place next to `runs/`, `preps/`, `routing-misses.md`; the tests already redirect it; one retention sweep; nothing lands in a repo | The task folder is not visible from the project; the window links to it | Allowed: "Data lives in `~/.claude/console/`" |
| `<project>/.claude/tasks/` | Visible in the repo, next to the project's skills | Breaks the rule ("Never write anywhere else"); scatters state over every repo; ends up committed or needs a .gitignore line per project; a step reading its own task folder would read what the last step wrote through git too | Not allowed |
| `%APPDATA%\ClaudeConsole\` | The Windows convention for app data | Nothing in this project uses AppData; a second data root to document, test and prune; `CC_CONSOLE_HOME` would not cover it | Not allowed |
| `Documents\Claude Console\` | Easy to find by hand | Synced by OneDrive on many machines (partial writes seen by the service); not the rule | Not allowed |

If Fred wants a task's result visible in the repo, the handoff note is prose the next chat can paste; nothing
is copied there by code.

### 4.2 Folder layout

```text
~/.claude/console/tasks/20261012-101500-3f2a/
  task.json            state, route, owner, the steps (below)
  prompt.md            the task text as Fred ran it (the Prep card's enhanced prompt, or the raw text)
  steps/01-scout.md    the handoff note of step 1 (written by the service from the step's final message)
  steps/02-code.md
  steps/03-verify.md
  steps/04-fix.md      inserted after a FAIL (section 4.4)
  steps/05-verify.md
  chain.jsonl          one line per transition: {"ts", "step", "from", "to", "why", "session"}
```

The task's chat is its steps' sessions: `task.json` names each step's session id and the window shows them
(`runs/<sid>.jsonl`, the Chat tab, the Steps tab). Nothing is copied: a task folder holds the chain and the
notes, the runs folder holds the streams. Retention: `runs/` and `preps/` keep 14 days (`retention_days`);
task folders keep `task_retention_days` (new key, default 90), so a handoff note outlives its chat (decision 7).

`task.json`:

```json
{
  "id": "20261012-101500-3f2a",
  "project_dir": "D:\\WORK\\CONTENT MANAGER",
  "title": "Add the usage calendar export",
  "type": "normal",
  "state": "running",
  "owner": "service",
  "current": 2,
  "last_good": 1,
  "escalated": "",
  "prep": "20261012-101455-9c1d",
  "created": 1760235300.0,
  "updated": 1760235900.0,
  "steps": [
    {"n": 1, "kind": "scout", "goal": "Find the export code paths and the tests that cover them",
     "model": "haiku", "effort": "low", "session": "7b3c...", "state": "done",
     "handoff": "steps/01-scout.md", "verdict": "", "retries": 0, "cost": 0.02,
     "start_commit": "146c432", "started": 1760235310.0, "ended": 1760235400.0},
    {"n": 2, "kind": "code", "goal": "Write the export and its tests", "model": "sonnet", "effort": "medium",
     "session": "a91e...", "state": "running", "handoff": "", "verdict": "", "retries": 0, "cost": 0,
     "start_commit": "146c432", "started": 1760235410.0, "ended": null},
    {"n": 3, "kind": "verify", "goal": "Check step 2", "model": "opus", "effort": "medium",
     "session": "", "state": "planned", "handoff": "", "verdict": "", "retries": 0, "cost": 0,
     "start_commit": "", "started": null, "ended": null}
  ]
}
```

Task states: `planned` (no step started), `running` (a step's run is live or being checked), `waiting` (the
step asked a `STOP:` question, or a denial: Fred answers on the session page), `stuck` (a step failed its retry,
or a second verify FAIL), `done` (the last step's handoff was good), `stopped` (Fred's Stop; `owner` becomes
`fred`). Step states: `planned`, `running`, `done`, `failed`. `last_good` is the last step with a good handoff:
Retry starts `current` again with that note as input.

### 4.3 The handoff note

The step's final message ends with a block the service cuts out, checks and writes to `steps/NN-<kind>.md`:

```text
HANDOFF
## Findings
What was learned or done, in a few lines.
## Files touched
- console/usage.py (export_csv)
- tests/test_usage.py
## Open questions
- (none)
## Next
One line for the next step. Optional: `Next model: sonnet/high` when the next step needs more than planned.
END HANDOFF
```

`tasks.parse_handoff(text) -> dict | None` takes the last `HANDOFF ... END HANDOFF` block of the message.
`tasks.check_handoff(note) -> str` returns "" when the four headings are there in that order, Findings is not
empty, and Files touched is a list (`- (none)` allowed); else the reason (`no HANDOFF block`,
`missing: Files touched`, `Findings is empty`). The reason goes into `chain.jsonl` and the window. The file
written is the block without the markers, with a first line `# Step NN: <kind> on <model>/<effort>, session <id>`.
The text is masked (`redact.mask`) before it is written, as everything the console writes.

The step prompt (`console/step_prompt.md`, a `string.Template` like `prep_prompt.md`) holds: the task goal
(`prompt.md`), "Step N of M: <kind>" and the step's goal, the previous handoff note in full (or "This is the
first step"), the rules (work only on this step; the Agent tool is not available, do the reading yourself;
do not run `/session-handoff`; end the final message with the HANDOFF block above), and the STOP footer that
`runs.start` already adds. A verify step sends `levers.VERIFY_TEXT` plus the note of the step it checks plus the
HANDOFF block rule; its `VERDICT:` line is read by the hook as today. A fix step sends `levers.escalate_text`
plus the failed verify's note.

### 4.4 The supervisor (code, in the service)

`console/tasks.py` is pure: the rules table, the routes, the handoff parse and check, the transitions and the
file reads and writes. `server.Hub` holds the loaded tasks and is the only caller. The gate is
`Hub.task_levers(task_id)`, next to `Hub.levers`, returning for `start`, `stop`, `retry`, `pause`, `resume`
either "" or why it is off, so a click and the loop pass one gate (CLAUDE.md: `Hub.levers` alone decides when a
run may start; `task_levers` is its task-side half and calls `Hub.allowed`, the same busy checks and the cold
guard; nothing starts a step without it). `Hub.advance()` runs in the hub loop right after `auto_steps`:

| Task and step state | The service sees | It does |
|---|---|---|
| `planned`, `current` 0 | the task was just created and `owner` is `service` | starts step 1 (`tasks.step_route`, `runs.start` with `kind="task"`, `extra={"task", "step"}`), `current` 1, task `running` |
| `running`, step live | `runs.is_live(session)` | nothing |
| `running`, step's session in state `stop` or `blocked` | a `STOP:` line or a denial | task `waiting`; Fred answers through Continue on the session page (a new turn of the step); the next `run_ended` is checked as below |
| `running`, step ended (`run_ended`, `ended` in the run meta) | `_last_reply` has a good HANDOFF block | writes `steps/NN-<kind>.md`, step `done`, `last_good` = N; if it was a verify step, its verdict decides (next row); else starts step N+1, or task `done` when N was the last |
| verify step ended, verdict PASS | | next step, or `done` |
| verify step ended, verdict FAIL, task not escalated | | inserts `fix` (the checked step's route one step up, `levers.escalate_step`; `task.escalated` set; a `routing-misses.md` line with the checked step's kind as type) and a new `verify` after it; starts the fix |
| verify step ended, verdict FAIL, task escalated | | task `stuck` (the window says `verify failed twice`) |
| step ended, no or bad HANDOFF, or `run_ended` with `interrupted`, an error subtype or a denial | first time (`retries` 0) | step `failed`, `retries` 1, then started again on the same route with the `last_good` note and a line "Your earlier attempt ended without a handoff: <reason>" |
| same, `retries` 1 | | task `stuck` |
| any, Fred clicks Stop | | `runs.stop(session)` (the stream-json interrupt, never a kill), task `stopped`, `owner` `fred` |
| `stopped` or `stuck`, Fred clicks Retry | | `current` started again from `last_good` (a fresh session id; the old step session stays as it was), `owner` `service` |
| `running`, Fred clicks Pause | | `owner` `fred`: the live step finishes its turn, nothing starts after it until Resume |
| service restart | `task.json` says `running` and the step's run is gone | `reconcile` emits `run_ended` as today; the next `advance` treats it like any ended step (handoff check, then on or retry) |

Every transition appends one line to `chain.jsonl` and rewrites `task.json`. `Hub.auto_steps` (plan 16) skips
sessions that belong to a task (`run_started` carries `task`): the chain owns their verdicts, so a verify FAIL
never escalates the verify session itself. Plan 16's within-session Escalate / de-escalate keeps working for
plain runs.

### 4.5 Routing per step: escalate and de-escalate between steps

A step's route is decided in code, `tasks.step_route(step, prev_note, misses, cfg) -> (model, effort)`:

1. the rules table (section 5) for the step's kind;
2. raised to the misses floor of that kind (`routing.floor(misses, kind)`: Escalate and the fix step write
   misses with the step kind as the task type, so a kind that failed on Haiku starts on Sonnet next time);
3. raised by at most one step (`levers.escalate_step`) when the previous note says `Next model:` above the
   rule; a hint below the rule is ignored (the rule is already the cheap pick);
4. for `verify`: one model above the step it checks, effort at least medium, capped at opus/high
   (`tasks.verify_route`: haiku/low checks on sonnet/medium, sonnet/medium on opus/medium, opus/anything on
   opus/high; fable is never picked by code);
5. for `fix`: the checked step's route one step up (`levers.escalate_step`), once per task.

De-escalation needs no rule: a `code` step after an opus `design` step starts at its own rule (sonnet/medium),
a `test` step after a `code` step on haiku/low. Within one step, nothing changes mid-run (no mid-turn switch
exists). The cold-cache guard does not apply to a step (a fresh session), only to Fred's Continue on a waiting
step.

### 4.6 No subagents

Every step run adds `--disallowedTools Agent` (`claude_cli.run_command(..., disallow=("Agent",))`). Read-only
kinds also restrict the built-in set with `--tools` (section 5). Every step gets `--max-budget-usd
<task_step_budget_usd>` (default 3, headroom in the estimate per the docs) so a looping step ends with an error
result the chain treats as a failed step. The step prompt says the Agent tool is not available and that the
step does its own reading.

### 4.7 Window (minimal)

- The Prep card gets **Run as task** next to Run when Prep returned two or more steps (section 6): the steps
  (kind, goal, route) are listed on the card and Fred can drop or reorder them before it starts (D4: always
  review). Run stays a single session as today.
- The list shows a task as one card in the group its state maps to (`waiting` and `stuck` under Needs you,
  `running` under Working, `done` and `stopped` under Done today) with `step 2 / 4` and the current step's
  route; its session rows stay under it.
- The Task page: the chain as one cell per step (state glyph and word, kind, route, cost), the current note,
  Stop / Pause / Retry, Open step (the session page), and the folder path. Styling in `web/style.css`, tokens
  first, the cell motif of `console-cells.html`.

### 4.8 Opus-sparing method, model budget and Fable (Fred, 2026-10-12)

Fred's aim: a 100 euro subscription cannot be unlimited Opus 5.5; Fred's own Console data gives about 10 euro per
Opus task, so heavy Opus use must end somewhere (a limit, or a quieter degradation Fred believes in; the plan does
not need to settle which). The method: **Opus thinks, Haiku reads, Sonnet writes.** Opus is treated as a scarce
resource with a paced budget, every other model as the default, and the chain is built so an Opus step is small.

**Opus only where reasoning is needed**

- The rules table (section 5) puts Opus on `design` only; `verify` reaches Opus only when it checks a Sonnet
  step; `fix` reaches Opus only after a verify FAIL on Sonnet, once per task. Scouting, lookups, drafts, edits,
  code, docs and test runs never start on Opus.
- An Opus step never reads the repo for itself: a `scout` step on Haiku runs before it and its handoff note
  carries the facts (files, functions, the failing line). `design` gets `--tools Read,Grep,Glob` for a last look,
  with `--max-turns` (`opus_max_turns`, default 12) so it cannot drift into bulk reading. An Opus step is always a
  fresh session (no transcript replay, the cheapest context there is) and its decisions leave in the note, so
  the Sonnet step after it does the writing.
- Plan 16's demand rule keeps its shape but `reasoning high` alone no longer gives Opus to a step whose kind
  writes code: it raises `code` to sonnet/high; Opus comes only from `design` or an escalation.

**Budget and pace per model**

- The console already prices every transcript message per model family (`usage.History`). Sub-plan 18 sums it
  over the plan windows (the last 5 hours, the last 7 days) and over the billing month, per family.
- `config.json` `model_budget`: per family, `month_usd` (Fred's cap at list prices, the Usage page's unit),
  `week_usd` and `window_usd`; `warn_at` 0.8. The pace is linear: on day 10 of 30, Opus's share of the month's
  cap is a third. Opus over its pace (not only over its cap) is the warning: an orange outline on its row, a
  header chip `opus 84 % of pace`, and a line on the Prep card.
- From Fred's own history, the median cost of a session per family (`usage.History`, the last 30 days) is shown
  on the Prep card next to the route: `about 10 euro on opus, about 2 on sonnet` (list prices), so each choice
  is made with the price in view.

**Routing under pressure** (`tasks.step_route` step 6, from `Hub.budget(family) -> share of pace`)

- A step whose rule lands on a model over `warn_at` of its pace starts one model down at the next higher effort
  (opus/high to sonnet/xhigh) and says so in the chain log and the Route block (`budget: opus 84 %`).
- A `verify` step never goes below the step it checks: it holds (`waiting`, "opus over pace: confirm or verify
  on sonnet") for Fred.
- Over 100 % of the cap the Opus row of the Prep card is off (Run raw still allows it: Fred's call).

**Fable only by Fred**

- Code never picks Fable (a route above opus/high stays opus/high). Print mode bills Fable to usage credits
  without asking (docs, section 2), so Fred sets it on the Prep card or on a step; the card says `Fable may bill
  usage credits on this plan` and asks for a second click, the arm-and-confirm of the cold-cache guard. A task
  with a Fable step holds (`waiting`, "confirm Fable") until Fred confirms on the Task page, once per task.

Where this lands: the budget rows, the pace, the config keys and the Usage page cells are sub-plan 18; plan 17
consumes `Hub.budget(family)` as one input of `step_route` (Task 1 takes a plain dict and plan 18 fills it) and
the per-family median cost on the Prep card.

### 4.9 Effort: auto, or fixed by Fred (Fred, 2026-10-12)

Design, 3D modelling, game assets and game design come out very differently at max effort; Fred wants to set
that himself when he knows it, and let the code decide otherwise.

- **A slider on the compose row**: `Auto` (default) then `low`, `medium`, `high`, `xhigh`, `max`
  (`claude_cli.EFFORTS`, the levels `--effort` takes; `ultracode` is left out: it is xhigh plus a mode of its
  own). It sits next to the project name under the task box, drawn in the cell motif (one cell per level, the
  picked one lit; Auto is the unlit row). Keyboard: Alt+Up / Alt+Down. The last pick is kept in `window.json`
  (`effort`), like the project.
- **Auto**: the rules of sections 4.5 and 5 pick the effort per step, as written. **Fixed**: every step of the
  task runs at that effort on the model its rule picks (Haiku scout at max, Opus design at max, Sonnet code at
  max). The model is still the rules' choice; only the effort is Fred's. The Prep card shows `effort: max (fixed)`
  next to each step's route; a plain Run and Run raw use it the same way (`/api/run` already takes `effort`).
- **Clamp**: "available levels depend on the model" (docs, `--effort`). `claude_cli.EFFORT_CAP` holds the highest
  level each alias accepts (to check live on 2.1.296 in Task 2: `claude -p --model haiku --effort max` on a
  one-word prompt; the result's `modelUsage` and the exit say whether the level was taken). A fixed level above
  a model's cap runs at the cap and the chain log says `effort max -> high (haiku cap)`.
- **Escalation with a fixed effort**: the effort cannot move, so Escalate, `fix` and `verify_route` go straight
  to the next model at the fixed effort (sonnet/max to opus/max). The cold-cache guard and the budget rule are
  unchanged; a fixed `max` on Opus is still subject to the Opus pace warning and the card says so.
- **In the data**: `task.json` gets `"effort": "auto"` or the level; each step keeps its own `effort` as run;
  `run_started` already carries `effort`, so the Route block, the Usage page and the model mix need no change.
- Not a per-model slider: one level for the whole task, as Fred asked; a per-step change is an edit of the step
  list on the card (section 6).

### 4.10 Model ladder: older models as extra rungs (Fred, 2026-10-12)

Fred's idea: Opus 4.6 / 4.7 / 4.8 and Haiku 4.5 are still served; using them spreads the load off Opus 5.5 and
Haiku 5.5. The design keeps the four tiers (haiku, sonnet, opus, fable) as the vocabulary of every rule and
adds, per tier, an ordered list of concrete models, newest first:

```json
"ladder": {"haiku": ["haiku", "claude-haiku-4-5"],
           "sonnet": ["sonnet", "claude-sonnet-4-6"],
           "opus": ["opus", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6"],
           "fable": ["fable"]}
```

- `step_route` still answers a tier. When a step starts, `Hub.model_id(tier)` picks the first rung of that tier
  whose budget share (sub-plan 18, keyed by model id) is under `budget_warn_at`; the alias (newest) when nothing
  is over. The budget rule of 4.8 then applies to the tier only when every rung of the tier is over its pace: same
  tier older first, one tier down second.
- `--model <id>` runs it; `run_started` carries the id; the window's `alias()` still finds the family and
  `modelText` shows the version (`opus 4.6`) when the id carries one. The routing-misses lines keep tiers
  (`sonnet/medium`), so the floor logic is unchanged.
- Prices: `config.json` `prices` stays per family (the estimate is already approximate); sub-plan 18 may add
  `prices_by_id` for the rungs whose list price differs.
- Fred can set a rung by hand on a card or a step (the model select lists the ladder, newest first per tier);
  code picks a rung only under budget pressure. Fable keeps its confirm whatever the rung.
- A rung that stops being served fails on its first request: the step ends `failed`, the retry starts on the
  next rung up (the alias), and the chain log says why. Nothing else is needed.

### 4.11 Storage (Fred, 2026-10-12)

What the console keeps under `~/.claude/console/` and for how long:

| What | Size | Kept | Key |
|---|---|---|---|
| `events-YYYY-MM-DD.jsonl` | about 1 MB per busy day (summaries, masked) | 14 days | `retention_days` |
| `runs/<sid>.jsonl` (window run streams) | 0.1 to 5 MB per run (tool results included) | 14 days | `retention_days` |
| `preps/<id>.json` | a few KB | 14 days | `retention_days` |
| `tasks/<id>/` (task.json, prompt.md, notes, chain.jsonl) | under 100 KB per task: a note is capped at 20 KB (`note_max_kb`), the prompt at 6000 characters, the chain at one line per transition | 90 days, then only `done` / `stopped` / `stuck` tasks are removed | `task_retention_days` |
| `usage-days.json` | one line per closed day (bytes) | for good | |
| `routing-misses.md`, `config.json`, `window.json`, `draft.txt` | tiny | for good | |

- Transcripts are Claude Code's (`~/.claude/projects`, about 1.4 GB on this machine), deleted by Claude Code
  after 30 days; the console reads them and never writes them.
- The sweep runs at start (`console/__main__.py`) and once a day in the tick; nothing is deleted by size.
- The Usage page gets one line at its foot: the data folder's size by subfolder (one `os.walk` per hour on the
  usage thread), so Fred sees when `runs/` grows; a `storage_warn_mb` key (default 500) turns it orange.
- The folder can move: `CC_CONSOLE_HOME` (an environment variable, since `config.json` lives inside the
  folder) points the service, the window and the hook at another drive; the tests already use it.
- Nothing is written anywhere else: a step's note is cut from the model's message, masked and capped before it
  is written; a model never writes into the folder.
- **Clear on done** (Fred, 2026-10-12): when a task reaches `done`, the service deletes what is only history:
  the step run streams and their metas (`runs/<sid>.jsonl`, `runs/<sid>.json`) and every note but the last good
  one. It keeps `task.json`, `chain.jsonl`, `prompt.md` and `steps/NN-<last good>.md` (a few KB: the list, the
  Task page and Start next chat still work; the Chat tab of a step falls back to Claude Code's own transcript, as
  for a VS Code chat). `task_clear_on_done` (default true) turns it off. A `stuck` or `stopped` task keeps
  everything until Fred clicks Retry or **Clear** on the Task page (Clear deletes the whole folder and the step
  streams; also offered on a done task to remove its last few KB). Retention (90 days) still sweeps what is left.

### 4.12 The brief: the handoff compacted between steps (Fred, 2026-10-12)

A raw handoff note can run to thousands of words (a scout lists everything it saw). The next model should read
only what its step needs. So between two steps the service turns the note into a **brief**, and the next step's
prompt carries the brief, never the raw note and never the whole history.

- **Rolling, not cumulative**: the brief of step N is built from the brief of step N-1 plus the raw note of
  step N plus the goal of step N+1 ("carry forward what the next steps still need, drop the rest"). Each step
  reads one brief; what step 1 found reaches step 4 only if the briefs kept carrying it.
- **A Haiku pass, like Prep**: `claude -p --model haiku --effort low --tools "" --max-turns 1 --json-schema ...`
  with hooks, skills and MCP off and no session persistence (`claude_cli.prep_command` shape, a new
  `brief_command`), about $0.01 and 5 to 15 s. It reads no file: the service puts everything in the prompt. The
  output is structured (findings, files, questions, next) with hard limits (`brief_max_words` 400: Findings at
  most 12 lines, Files touched at most 20, Open questions at most 5, Next one line) and is checked by code
  (`tasks.check_handoff` on the rendered block, the word cap). A failed or over-long pass falls back to code:
  the previous brief's Next, the raw note's Files touched and Open questions, and its Findings cut at 1500
  characters. The chain never waits on a failed brief.
- **Files**: `steps/NN-<kind>.md` stays the raw note (what the step said); `steps/NN-<kind>.brief.md` is the
  brief. The Task page shows the brief, with the raw note one click away. Clear on done keeps the last brief
  (and its raw note); Start next chat seeds the composer with the last brief.
- **Not a supervisor**: the brief pass decides nothing (no route, no state); the supervisor stays code. It is one
  more `claude -p`, so BRAINSTORM's "no model calls except through the harness CLIs" holds, and it is never an
  Agent tool call.
- **In the chain**: a step's end writes the raw note, then the brief job runs in a thread (as a Prep job does);
  the task shows `briefing` on its row; when the brief file exists the next step starts. `brief_on` false skips
  the pass (the fallback brief is used, still capped). The first step gets no brief: `This is the first step`.
- **Why Haiku and not the step's own model**: the step already ended; a fresh cheap process with no tools and a
  one-turn cap is the smallest possible context, which is the point.
: step kind to model and effort

From Fred's chart (Haiku: factual questions, brainstorming, first drafts, simple code, proofreading, quick
research summaries. Sonnet: important documents, debugging, in-depth explanations, when Haiku was close, daily
solid work. Opus: when Sonnet failed, novel problems, critical decisions, system architecture, deep research),
the `route-model` table and plan 16's demand rule. Each row names its test in `tests/test_tasks.py`
(`RulesTest`).

| kind | what the step does (chart row) | model | effort | tools | test |
|---|---|---|---|---|---|
| scout | find the files, functions and tests a task touches; quick research summaries; factual questions | haiku | low | Read,Grep,Glob | `test_rule_scout_haiku_low` |
| search | docs and web lookups, explain a library or an error (named `search`, not `lookup`: `lookup` is a Prep route type and a test compares those rows) | haiku | low | Read,Grep,Glob,WebFetch,WebSearch | `test_rule_search_haiku_low` |
| draft | first drafts of docs, plans, prose; brainstorming | haiku | low | default minus Agent | `test_rule_draft_haiku_low` |
| proofread | proofreading, wording passes, no code | haiku | low | default minus Agent | `test_rule_proofread_haiku_low` |
| edit | simple code: a 1-2 file edit with a clear spec, renames, copies (chart: simple code on Haiku; the route-model table says sonnet/low, decision 5) | haiku | low | default minus Agent | `test_rule_edit_haiku_low` |
| code | daily solid work: a feature or fix with a clear spec or plan, and its tests | sonnet | medium | default minus Agent | `test_rule_code_sonnet_medium` |
| document | important documents: a plan, a spec, user-facing docs | sonnet | medium | default minus Agent | `test_rule_document_sonnet_medium` |
| explain | in-depth explanations across many files | sonnet | medium | Read,Grep,Glob | `test_rule_explain_sonnet_medium` |
| debug | debugging: a failing test or a reported bug with no known cause | sonnet | high | default minus Agent | `test_rule_debug_sonnet_high` |
| test | run the checks and report (no edits) | haiku | low | Bash,Read,Grep,Glob | `test_rule_test_haiku_low` |
| design | system architecture, novel problems, critical decisions, deep research | opus | high | Read,Grep,Glob,WebFetch,WebSearch | `test_rule_design_opus_high` |
| verify | check the step before it: one model up, effort at least medium, cap opus/high | computed | computed | Bash,Read,Grep,Glob | `test_verify_runs_one_model_up` |
| fix | after a verify FAIL: the checked step's route one step up, once per task, a miss line | computed | computed | default minus Agent | `test_fix_runs_on_the_escalated_route_once` |

Rules on top of the table, each with its test:

| rule | test |
|---|---|
| A miss of the same kind is a floor (`routing.floor`) | `test_miss_floor_raises_a_step` |
| `Next model:` in the previous note raises by one step at most, never lowers | `test_next_hint_raises_at_most_one_step` |
| A step after an Opus step starts at its own rule (de-escalate by rule) | `test_step_after_opus_goes_back_to_its_rule` |
| Prep's demand still applies to the task: with `reasoning` high the chain's `code` and `debug` steps start one step up (plan 16's `by_demand` on the step's rule) | `test_task_demand_raises_code_steps` |
| Code never picks fable; a route above opus/high stays opus/high unless Fred set it on the card | `test_code_never_picks_fable` |
| Opus only from `design`, a verify of a Sonnet step, or one fix after a FAIL; `reasoning high` raises a code step to sonnet/high, never to Opus | `test_opus_only_where_reasoning_is_needed` |
| A model over `warn_at` of its pace moves a step one model down at a higher effort; verify holds instead | `test_budget_pressure_moves_a_step_down` |
| An Opus `design` step is read-only with `--max-turns opus_max_turns` and always a fresh session | `test_opus_step_is_small` |
| A fixed effort applies to every step on the rule's model, clamped to the model's cap; escalation then moves the model, not the effort | `test_fixed_effort_runs_every_step_at_that_level`, `test_fixed_effort_is_clamped_to_the_model_cap`, `test_escalate_with_fixed_effort_moves_the_model` |
| Every step command carries `--disallowedTools Agent` and `--max-budget-usd` | `test_step_command_has_no_agent_tool` (`tests/test_claude_cli.py`) |
| The route-model skill table and `prep_prompt.md` still match (existing `test_dotclaude` check); the step kinds table is a second table, not a change to the first | existing test, plus `test_kinds_table_matches_prompt` |

## 6. Prep proposes the chain, Fred reviews it

The Prep schema gains an optional `steps` list: `[{"kind": <one of section 5, not verify or fix>, "goal":
<one line>}]`, at most `task_max_steps` (default 6). `prep_prompt.md` lists the kinds and says when to split
(the request has a scouting part, a writing part and a check; or it touches more files than one step should
read) and when not to (a one-step task returns an empty list: Run as today). Code validates: unknown kinds are
dropped, the list is cut at the maximum, and a `verify` step is appended after the last step that edits
(`edit`, `code`, `debug`, `document`, `draft`) when none follows it. The card shows the list; Fred edits
before Run as task (D4). The fake claude gets a `CHAIN` word that returns three steps.

## 7. Constraints kept

- Nothing is written outside `~/.claude/console/`: the service writes task folders there; the model writes
  nothing there (section 4.3). `test_nothing_written_outside_home` runs a chain on the fake claude with
  `CC_CONSOLE_HOME` set and asserts the project folder has only what the fake wrote.
- Code never edits `~/.claude/settings.json`; no new hook event is needed (verdicts and STOP lines already come
  through the hook; the final message comes from the run's stream).
- `cc_events.py` is not touched.
- Steps run only in `config.json` "projects" (`Hub.allowed`, checked at task creation and before every step).
- Stop is `runs.stop` (the interrupt); a step the service did not start is never killed by the chain; `kill_tree`
  stays the last resort for a run from an earlier service, as today.
- No emojis or em-dashes in the plan, the prompts, the notes or the window.

## 8. Open decisions for Fred (before any code)

1. **Non-goals (D16).** Add to BRAINSTORM section 2: "a linear step chain, advanced by the service when a step
   ends, is not a task graph or a scheduler; branches, parallel steps, queues and retries beyond one stay out".
   Recommended: yes. Without it this plan stops here.
2. **Who proposes the steps.** (a, recommended) Prep returns an optional `steps` list; code validates it and
   appends the verify step; Fred edits it on the card. (b) Fixed templates per Prep type (normal: scout, code,
   verify; lookup type: scout, explain). (c) Fred types the steps by hand.
3. **Who writes the handoff file.** (a, recommended) The service, from the HANDOFF block of the final message
   (section 4.3): no file write outside the project by the model, no auto-mode denial risk. (b) The step writes
   `steps/NN.md` itself with the Write tool (needs `--add-dir` on the task folder and may still be denied).
4. **Advance by itself.** (a, recommended, as plan 16 (b)) The service starts the next step as soon as the
   handoff checks out; Fred can Pause or Stop at any time. (b) Each step waits for a click on the Task page.
5. **The `edit` row.** (a, recommended, Fred's chart) haiku/low: the misses floor raises it after one failure.
   (b) sonnet/low as in the route-model table. Either way the route-model table itself is unchanged.
6. **After a verify FAIL.** (a, recommended) Insert a fix step on the escalated route and a verify after it, once
   per task; a second FAIL is stuck (section 4.4). (b) No insert: the task is stuck at once and Retry runs the
   checked step again on the escalated route.
7. **Retention.** Task folders keep 90 days (`task_retention_days`); run streams keep 14 (`retention_days`), so
   a step's chat may be gone while its note stays. Alternative: one retention for both.
8. **Window scope for this plan.** (a, recommended) Run as task on the card, the task card in the list, the Task
   page with Stop / Pause / Retry (section 4.7). (b) No Task page yet: the task card and its session rows only,
   Stop and Retry on the card.
9. **Step budget.** `--max-budget-usd 3` per step and `task_max_steps` 6 as defaults, both in `config.json`.
10. **Tool sets per kind** (section 5 `tools` column), in particular WebFetch and WebSearch for `search` and
    `design`, and `Bash` for `test` and `verify`.
11. **Model budget (plan 18).** The windows (5 hours and 7 days), the budgets per model (`model_budget` in
    `config.json`, USD at list prices as the Usage page counts them, or tokens) and `warn_at` 0.8. Fred sets the
    numbers from the plan's limits; the console cannot read them.
12. **Routing under budget pressure.** (a, recommended) A step on a model over `warn_at` of its pace starts one
    model down at a higher effort and says so; verify holds for Fred; over the cap the Opus row of the card is off.
    (b) Warn only, routes unchanged.
13. **Fable.** (a, recommended) Never picked by code; Fred picks it on a card or a step and confirms once (the
    print-mode credit billing is silent). (b) Fable allowed as the last escalation step with the same confirm.
14. **Opus thinks, Haiku reads, Sonnet writes.** (a, recommended) Opus only on `design`, a verify of a Sonnet step
    and one fix; `reasoning high` gives sonnet/high to a code step, not Opus; `opus_max_turns` 12 on a design
    step. (b) Keep plan 16's rule as is (reasoning high gives opus/high to any task).
15. **Pace, not only cap.** The warning compares each model to a linear pace over the billing month (and to the
    5 hour and 7 day windows). Fred gives the month's start day and the caps in euro at list prices; the console
    cannot read the plan's real counters.
16. **Effort slider.** (a, recommended) One slider on the compose row, Auto by default, a fixed level for the
    whole task on every model, clamped to the model's cap, remembered in `window.json`; escalation moves the model
    when the effort is fixed. (b) The slider only pre-fills the Prep card's effort for the main route and steps keep
    their rules. (c) Also a per-step effort on the card's step list.
17. **Model ladder.** (a, recommended) `ladder` in `config.json`, newest first per tier; code moves to an older
    rung only under budget pressure, same tier before a tier down; Fred may pick any rung by hand. (b) Aliases only,
    as plan 03 decided. Open fact: whether the plan counts an older model apart from the newest (live check item 11).
18. **Storage.** (a, recommended) The retention table of 4.11, a 20 KB note cap, the size line on the Usage page
    with `storage_warn_mb` 500. (b) Retention only, no size line.
19. **Clear on done.** (a, recommended, Fred's ask) On `done` the service deletes the step streams and all notes but
    the last good one, keeps task.json, chain.jsonl, prompt.md; `task_clear_on_done` true; a Clear button for any
    task that is not running. (b) Delete the whole folder on done (the list loses the row at the next restart and
    Start next chat loses the note). (c) Nothing automatic: Clear by hand only.
20. **Brief between steps.** (a, recommended, Fred's ask) A Haiku pass compacts the raw note into a rolling
    brief for the next step (400 words max, structured, code-checked, code fallback), saved next to the raw note;
    the next step reads the brief only. (b) Code-only compaction: fixed cuts per section, no model pass (free, but
    nothing is rephrased for the next step). (c) Raw notes as they are, capped at 20 KB.

## 9. Tasks (written in full, with the final code, once section 8 is answered)

Each task is a cp + test + commit step as in the earlier plans, with its tests failing first.

| # | Task | Files | Tests |
|---|---|---|---|
| 1 | `console/tasks.py`: `KINDS`, `RULES`, `step_route`, `verify_route`, `parse_handoff`, `check_handoff`, `new_task(card, steps, project_dir)`, `load`, `save` (temp file + `os.replace`), `log(folder, line)`, `advance(task, step_ended, reply, verdict, now) -> (task, action)` as a pure transition over the table in 4.4 | new `console/tasks.py`, `console/step_prompt.md`, `console/paths.py` (`task_retention_days`, `task_step_budget_usd`, `task_max_steps`) | new `tests/test_tasks.py`: the rows of section 5, the rules below it, `test_parse_handoff_takes_the_last_block`, `test_check_handoff_reasons`, `test_advance_*` one per row of 4.4, `test_save_is_atomic` |
| 2 | `claude_cli.run_command(disallow=(), tools="", budget=0, max_turns=0)`; `claude_cli.EFFORT_CAP` (checked live per alias); `runs.start(..., disallow, tools, budget, max_turns)` passes them; `run_started` carries `task` and `step` | `console/claude_cli.py`, `console/runs.py` | `test_step_command_has_no_agent_tool`, `test_run_started_carries_task_and_step`, `test_effort_cap_clamps` |
| 3 | Prep `steps` (schema, validation, verify append), `prep_prompt.md` kinds block, fake claude `CHAIN` | `console/prep.py`, `console/prep_prompt.md`, `tests/fake_claude.py` | `test_run_prep_returns_steps_and_appends_verify`, `test_kinds_table_matches_prompt` |
| 4 | Service: `Hub.tasks` (loaded at start from `tasks/*/task.json`), `Hub.task_levers`, `Hub.advance` in the loop, `auto_steps` skips task sessions, `POST /api/task` (from a card: `prep`, `steps`), `GET /api/task?id=`, `POST /api/task/stop`, `/api/task/retry`, `/api/task/pause`, `/api/task/resume`, the task list in the snapshot, `runs.prune` for task folders, `state` tags sessions with their task | `console/server.py`, `console/state.py`, `console/runs.py` | `test_chain_starts_step_one_from_the_card`, `test_good_handoff_starts_the_next_step`, `test_missing_handoff_retries_once_then_stuck`, `test_verify_fail_inserts_fix_and_verify`, `test_second_fail_is_stuck`, `test_stop_question_waits_for_fred`, `test_stop_interrupts_the_step_never_kills`, `test_retry_from_last_good_handoff`, `test_task_only_in_allowed_projects`, `test_one_task_per_project_at_a_time`, `test_auto_steps_skip_task_sessions`, `test_restart_resumes_the_chain`, `test_nothing_written_outside_home` |
| 5 | Window: the effort slider on the compose row (Auto + 5 levels, kept in `window.json`, sent with `/api/prep`, `/api/run` and `/api/task`), Run as task with the editable step list on the Prep page, the task card, the Task page (cells per step), Stop / Pause / Retry, `step N / M` on session rows | `web/app.js`, `web/index.html`, `web/style.css` | headless Edge at 400 and 340 px with the fake claude; `tests/test_window.py` unchanged |
| 6 | Fred: live check in CONTENT MANAGER: a three-step task (scout on haiku, code on sonnet, verify on opus), a forced bad handoff (a step told to skip the block) retried then stuck, Stop mid-step, Retry from the last good note; no `hook-errors.log` lines; nothing new outside `~/.claude/console/` | | |
| 7 | Close: PLAN.md row and History line, BRAINSTORM D16 and the section 2 note, CLAUDE.md line "Tasks: a linear chain under `~/.claude/console/tasks/`, advanced only through `Hub.task_levers`; every step is one `claude -p` with the Agent tool removed" | `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md` | `py -m unittest discover -s tests` |

## 10. Out of scope

Parallel steps, a queue of tasks, worktrees per task, a step that spawns subagents, a model as supervisor,
any write into a project folder by the console, other harnesses (phase 5).
