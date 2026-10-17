# Plan 44: an event-driven supervisor for tasks and steps. Brainstorm

Status: **decided** 2026-10-17 (Fred took option (a) on D1 to D17 except D15 (b), and "no limit" on D18, section 15;
nothing is open). The guided plan comes next. Design only: no code changed here.

Context: [CLAUDE.md](../../CLAUDE.md), [BRAINSTORM.md](../../BRAINSTORM.md) (non-goals, D16),
[2026-10-13-orchestration.md](../../design/brainstorm/2026-10-13-orchestration.md) (D-1: no orchestrator agent),
plans [17](../17-tasks/README.md) (chain contract), [23](../23-handoff/README.md) (six headings, facts),
[24](../24-plan-and-replan/README.md) (plan, replan, holds), [33](../33-handoff-retry.md) (Retry with a note),
[35](../35-token-balancing.md) (balancing), [36](../36-next-step/README.md) (Add next step, manual progression),
[39](../39-task-actions.md) (any done step is a source), [41](../41-step-actions.md) (Stop, Retry, Mark step done),
[42](../42-unified-task-chat.md) (guidance queue, no automatic replay).

## 1. Fred's request

"I want to rethink the way we are handling the step and tasks, i want to have some automatism controlled by a
supervisor LLM. So I would like to embed Claude Code to be able to take decision and automatically create step,
review the task and see what could be the next step added. Start a verify or a code implementation once a design
has been done, if a task is stuck, he could take over. But i also want to be very token efficient so this LLM
should not be always on to verify everything at any time, so it could, once a status change for any step, start a
claude code session to ask him to verify the folder of the task, and take a decision for next phase. Writing up a
prompt would create that claude code session like we have today to route toward the right task format etc."

## 2. What exists today (read 2026-10-17, branch claude/brainstorm-task-actions)

- **Two ways a task runs.** An automatic chain (`Hub.create_task` from a Prep card with steps, `POST /api/task`):
  `Hub.advance` runs every second from the hub loop (`Hub.run`, `POLL_S` 1), `_advance_one` -> `_ended` ->
  `tasks.on_step_ended` -> `_go_on` -> `start_step`; a verify FAIL inserts `fix` + `verify` once, a bad handoff retries
  once then `stuck`. A manual task (`progression: "manual"`, plan 36): every step ends at `waiting` /
  `choose next step` (or `VERDICT: FAIL: ...`), owner `fred`, and only Add next step (`POST /api/task/next/preview`,
  `POST /api/task/next`) or Finish (`POST /api/task/done`) moves it. Every prompt typed in the window is a task of one
  `chat` step (`Hub.chat_task`, plan 29) and becomes manual at its first Add next step.
- **The gates.** `Hub.levers(session)` for session levers; `Hub.task_levers(task)` for `start`, `stop`, `pause`,
  `resume`, `retry`, `stepdone`, `confirm`, `clear`, `done`, `answer`, `redo`, `keep`, `add_next`;
  `Hub._next_source` / `next_sources` for which step may be a source. Nothing starts unless the gate answers `""`.
- **What the folder holds** (`~/.claude/console/tasks/<id>/`): `task.json`, `prompt.md`, `chain.jsonl`,
  `00-prep/` (prep.json, scouting.md, handoff.md), `NN-<kind>/` with `role.md`, `received.md`,
  `received-handoff.md` (manual steps), `notes.md`, `handoff.md` (the six-heading block, `tasks.HEADINGS`),
  `brief.md`, `facts.md` (diff stat and last test, never compacted), `verdict.md`, `notes.<k>.md` of a failed
  attempt; `plan.md` and `plan/NN-*.md` from a design step; `messages/<id>.json` (plan 42).
- **Cheap passes already exist**: the brief (`compact.run_brief`, `claude_cli.brief_command`: `--tools ""`,
  `--json-schema`, `--max-turns 6`, hooks off, no session persistence, about $0.001 on haiku) and the replan
  (`replan.run_replan`, same command, `replan.check` validates, Fred confirms unless `replan_auto`). Both run in a
  thread from the hub (`_brief_job`, `_replan_job`), never as a session row.
- **Stuck today** means task state `stuck` with a `why`: `<reason> (after one retry)`, `verify failed twice: ...`,
  a usage limit (`cs["limit"]`, plan 40), `error_write_denied` (plan 43), a route that cannot run (`rung_ok`), or a
  move that raised (`_broken`). Fred's ways out: Retry with a note and a model (plans 33, 40), Mark step done (41),
  Finish, Delete.
- **Decision D-1 of 2026-10-13**: no persistent orchestrator agent. This brainstorm keeps it: the supervisor is one
  bounded pass per wake, like the brief and the replan, not a session that watches.

## 3. The shape in one paragraph

A new module `console/supervisor.py` and a new kind file `dotclaude/console/kinds/supervisor.md`. When a task
transition the service already produces lands on a wake list, the hub loop waits a short debounce, builds a compact
digest of the task folder with code, runs one `claude -p` with no tools and a JSON schema, validates the answer
against `Hub.task_levers` / `Hub.next_sources` and the autonomy policy, then either suggests (a card on the Board,
Approve / Reject) or dispatches through the existing Hub methods. Every wake is one line in
`tasks/<id>/supervisor.jsonl`. The model never touches a file, a process or an endpoint.

## 4. The event model

Wakes are transitions, not a clock. They are raised from the places that already write chain lines; no new poller.

| Trigger (real transition) | Where it is raised | Wake |
|---|---|---|
| manual boundary: `tasks.on_step_ended` returns `"manual"` (task `waiting`, why `choose next step` or `VERDICT: FAIL...`, owner `fred`) | `Hub._ended` | yes: the main wake. Includes "a design step just finished" and "a verify just answered" |
| plan 41 Mark step done on a manual task (`tasks.fred("stepdone")` -> `choose next step`) | `Hub.task_lever` | yes |
| task `stuck` (`_retry_or_stuck` second time, `verify failed twice`, `rung_ok` refusal in `start_step`, a limit, `_broken`) | `_ended`, `start_step`, `advance` | yes, flagged `stuck` |
| automatic task `done` (`task:done`), after `_brief_done` wrote the last brief | `_brief_done` | yes (D12 a), slice C: one suggest-only wake, "anything left?", only when `tasks.room_after` leaves room |
| `plan ready: confirm` (`plan_hold`), `plan N KB, over M`, `replanned: ...` | `_ended`, `_replan_done` | yes, flagged `hold`: the supervisor may Confirm or Keep |
| budget hold `<model> over its pace` (`tasks.held`) | `start_step` | no: a pace hold is Fred's money rule (plan 18); the supervisor reports it only |
| step session in `stall` (`state.state_of`: no events 10 min, process alive) for `supervisor_stall_s` | hub tick (`TICK_S` 15, already running `state_of`) | yes, flagged `stalled` (section 6); one wake per attempt |
| `asks: <question>` and `asks: Plan gap:` | `_ended` | no (D5 a: questions are Fred's); the Board already puts them in Needs you |

Never wakes: `running -> running` lines (turn filed, briefing / briefed, cost sync, floors), the automatic first retry
(`retry 1`: code already decided; wait for its end), a task with `tasks.pending_messages(task)` (plan 42: guidance
runs before progression; the supervisor never jumps the queue), a task whose brief is still writing
(`task["briefing"]` or in `Hub.briefing`: the wake waits for `_brief_done` so the digest has the brief), a `chat`
task while its session is live or replied (every turn would wake; a chat wakes only when Fred converts it with Add
next step), Prep and Review jobs, any VS Code / terminal / other-CLI session (not a task), a paused task (owner
`fred` by Fred's Pause: the pause holds the supervisor too), a task whose `supervisor` mode is `off`.

Debounce and coalescing: `Hub.wakes: {task_id: {"due": t, "triggers": [...], "n": k}}`. A trigger sets
`due = now + supervisor_debounce_s` (20) and appends itself; a second trigger before `due` re-arms and merges (one
run, both triggers in the digest). At most one supervisor run per task at a time and `supervisor_parallel` (1)
across tasks; a trigger during a run marks the task dirty and one re-run follows when the run ends, never more.
The wake number `k` is `task["supervisor"]["wakes"]`, incremented when the run starts and saved with task.json, so
every decision, chain line and request id names it (`sup-<task>-<k>`). After a service restart the wake list is
empty; a task left `waiting` at `choose next step` with no decision logged for its last chain line gets one wake on
the first `advance` (the same rule that restarts an unfinished brief).

## 5. Token efficiency

**The digest, built by code** (`supervisor.digest(home, task, hub) -> str`, target under 4K tokens, hard cap 12 KB;
over it the sections are cut from the bottom of this list, never the head):

1. Head: id, title, project, goal (`tasks.prompt_goal`, cut to 600), `progression`, state / why / owner, the triggers
   of this wake, `created`, total cost (`tasks.step_cost` summed), supervisor spend so far on this task.
2. Steps table: `n · kind · model/effort · state · verdict · cost · retries · source_step`, one line each.
3. The last good step's handoff block whole (`tasks.read_note(home, task, last_good)`, at most `NOTE_MAX` by
   construction; the six headings, Goal and Troubleshooting carried whole as plan 23 wants), else its brief.
4. Its facts (`tasks.read_facts`: start and end commit, diff stat, the last test command and its failing lines).
5. The last verify's `verdict.md` when the step before the boundary is a verify or the trigger is `stuck`.
6. Plan: `plan.md` index's `## Goal`, `## Decisions`, `## Acceptance` and the list of `### Step N` or parts with
   which ones are done (`task["plan"]["parts"][i]["step"]` state), never the parts' bodies.
7. Open questions (`tasks.open_questions(task, briefs)`), the chain tail (last 10 lines of `tasks.read_chain`).
8. The stuck attempt's reason and the tail of `notes.<k>.md` (`ACCEPT_TAIL` 3000 characters) on a `stuck` wake only.
9. What is allowed now, in words, from the gates: `task_levers` entries that read `""`, `next_sources` entries that
   read `""`, `add_next` kinds (`tasks.NEXT_KINDS`), the autonomy mode and the remaining caps (auto steps left,
   retries left, USD left). The model picks among what the service already allows; it cannot invent an action.

Never in the digest: transcripts, `runs/<sid>.jsonl`, `notes.md` of a healthy step, the plan parts, received.md,
other tasks, config.json, anything outside the task folder (plus the budget line).

**The run**: `claude_cli.brief_command(exe, model, supervisor.SCHEMA)` as the brief uses it (`--tools ""`,
`--permission-mode dontAsk`, `--disable-slash-commands`, `--strict-mcp-config`, hooks off, `--no-session-persistence`,
`--output-format json --json-schema`, `--max-turns 6`), cwd the project folder as Prep runs (never the data folder),
in a thread like `_brief_job`, `supervisor_timeout_s` 90. No session row, no transcript, no hooks. The pass reads
the digest only (D3 a): no tools, so one wake is one model call and the replay of section 11 is exact. (The rejected
(b), `Read,Grep,Glob` with `--add-dir <task folder>`, would cost turns and make the pass non-deterministic.)

**Prompt order for the cache**: the kind file first (fixed text, `kinds.text(home, "supervisor")`, seeded from
`dotclaude/console/kinds/supervisor.md`, editable on the Kinds tab like every kind), then the schema reminder, then
the digest last. Anthropic's prompt cache (5 minutes) helps only when wakes cluster (a verify right after a code
step); the real lever is the digest size, so the fixed text is kept under 1,500 tokens and says nothing the schema
already enforces.

**Model**: `supervisor_model` default `haiku` through `Hub.model_id` (the alias resolves to the newest Haiku, as
`brief_model` does). Claude only: `--json-schema` is a Claude flag and the pass must be structured; the other
harnesses keep taking the steps. Escalation (D4 a): a `stuck` or `stalled` wake runs on `supervisor_stuck_model`
(`sonnet`), once; never opus, never fable. Estimated cost per wake: 4K in + 300 out, about $0.001 on haiku, $0.01 on
sonnet; a ten-step task wakes about ten times: a few cents next to $2 to $10 of workers.

**Caps**: `supervisor_task_usd` 0.50 (the supervisor's own spend per task), `supervisor_day_usd` 2 (over it no wake
runs and the task head says `supervisor: daily cap reached`), counted
from `result.total_cost_usd` as the brief is and written to `supervisor.jsonl` and the chain line. The work it
starts is capped apart (section 7).

**Plan 35**: the supervisor never names a rung. Its decisions carry `model: "auto"` only (D3 of plan 36: an explicit
pick is Fred's); `_next_route` / `step_route` balance by tracked tokens as today, `rung_ok` and the limits apply. A
Retry decision may carry `model: ""` (auto) or a tier word (`haiku`, `sonnet`, `opus`) that the service resolves
through the ladder, never an exact id.

## 6. The decision contract

One JSON object per wake, validated by `supervisor.check(decision, task, levers, sources, policy) -> (ok, why)`:

```json
{"decision": "add_next_step",
 "kind": "verify",
 "instructions": "Check step 02 against plan.md Acceptance: run py -m unittest tests.test_tasks; confirm the three new tests fail on 6e54298 and pass now.",
 "model": "auto",
 "reason": "Step 02 (code) finished with a complete handoff and facts show tests ran green; the plan's Acceptance has not been checked by a verify yet.",
 "confidence": "high",
 "for_fred": ""}
```

`decision` enum and what the service does with it (every row goes through the existing gate; a `409` from the gate
becomes `refused: <why>` in the log and a `suggest` card if the policy allows):

| decision | fields | service call | gate |
|---|---|---|---|
| `add_next_step` | `kind` in `tasks.NEXT_KINDS` (`code`, `verify`, `scout`, `design`, `chat`), `instructions` 1..`STEP_GOAL_MAX`, `model` `"auto"`, optional `source_step` | `Hub.preview_next` then `Hub.request_next` with `request_id = uuid5(sup-<task>-<k>)` and the preview's `revision` | `_next_source` (`next_sources[source]` must be `""`) |
| `confirm` | | `Hub.task_lever(task, "confirm")` | `task_levers["confirm"] == ""` and why in {`plan ready: confirm`, `plan N KB, over M`, `replanned: ...`}; never `confirm Fable`, never a pace hold |
| `keep` | | `task_lever("keep")` | `task_levers["keep"]` |
| `retry` | `note` (joins the prompt, plan 33), `model` `""` or a tier word (plan 40) | `task_lever("retry", note, model)` | `task_levers["retry"]` and `retries_left > 0` |
| `stepdone` | `reason` | `task_lever("stepdone")` | `task_levers["stepdone"]`; `suggest` only at every mode (accepting broken work is Fred's call) |
| `stop` | | `task_lever("stop")`: `runs.stop`, the stream-json interrupt, never a kill | only on a `stalled` wake, and with D6 (a) only as a suggestion ("Stop and retry?"), never dispatched by itself |
| `finish` | `reason` | `task_lever("done")` | `task_levers["done"]` |
| `answer` | `text` | plan 42 `Hub.task_message` with `mode == "answer"` (plan gap decision line included) | off (D5 a): kept in the enum so a decision that wants to answer is logged as `refused: questions are Fred's` and becomes `escalate_to_fred` |
| `escalate_to_fred` | `for_fred` (the question and the options, under 400 characters) | nothing starts; the task joins Needs you with the text | always allowed |
| `wait` | `reason` | nothing; the next transition wakes again | always allowed |

Not in the enum, on purpose: `pause`, `resume`, `clear`, `delete`, `redo`, `edit_plan`, `allow`, `set_model`,
anything with a path or a command. `take over` is not a verb but a policy: on a `stuck` wake the supervisor may
`retry` (once, with a note that names the failing line and a tier word), on a `stalled` wake `stop` then `retry`
(auto only), and when that fails `escalate_to_fred`. The schema has `additionalProperties: false`; a parse failure or
a schema miss is one line `supervisor: no decision (<why>)` and no re-run (the brief's fallback rule: never a loop of
passes).

Sample prompt (the kind file, shortened):

```text
# supervisor

You supervise one Claude Console task after a step changed state. You read a digest of the task folder that the
service built; you do not run anything and you cannot write anything. Answer with one JSON object that matches the
schema. Pick the smallest next move that keeps the task honest:
- a code step with a complete handoff and no verify after it: add a verify step with instructions that name the
  plan's Acceptance lines or the tests to run;
- a design step whose plan is saved: add the first write step of that plan (code), its instructions quoting
  `### Step N`'s Files and Done check; one step at a time, never the whole plan;
- a verify that answered PASS and nothing in Next: finish;
- a verify that answered FAIL: add one code step on the failing line when the detail is concrete; otherwise
  escalate_to_fred with the FAIL detail;
- a stuck task: retry once with a note naming the exact failure and, when the failure is a tool or sandbox refusal,
  a different tier word; after one retry, escalate_to_fred;
- a question for $you, a Fable confirm, a pace hold, a decision the plan does not make: escalate_to_fred or wait.
Write `instructions` for a worker that has never seen this task: files, the check to run, what done looks like.
Never name a model id, a path outside the project, or an action the "Allowed now" list does not carry.
```

## 7. Autonomy levels, defaults and hard stops

`supervisor_mode` in config.json: `off`, `suggest`, `auto`; default `suggest` (D1 a). Per project:
`supervisor_projects: {"<folder>": "auto"}` (D11 a, edited on the Models and tuning page through the plan 26
whitelist). Per task: `task["supervisor"] = {"mode", "wakes", "auto_steps",
"retries", "usd", "work_usd", "since_fred"}`, set at creation from the project or the global default, changed from
the Board switch (section 9) through `POST /api/task/supervisor {task, mode}`; a change is a chain line.

| mode | what a decision does |
|---|---|
| `off` | no wake runs for this task |
| `suggest` | the decision is logged and shown as a card (Approve / Reject); Approve dispatches the same validated decision; nothing starts by itself |
| `auto` | `add_next_step`, `confirm`, `keep`, `retry`, `finish`, `stop` (stalled only) dispatch at once within the caps; `stepdone`, `answer` and anything over a cap fall back to `suggest` |

Hard stops (code, never the prompt):

- `supervisor_max_auto_steps` 3: consecutive steps the supervisor added since Fred last acted on the task
  (`since_fred` resets on any `task_lever`, Approve, Add next step or message by Fred); the fourth is a suggestion.
- `supervisor_max_retries` 1 per step on top of the chain's own automatic retry.
- `supervisor_work_usd` 5: the cost of steps the supervisor started since Fred last acted; over it, suggest only.
- `supervisor_task_usd` 0.50 and `supervisor_day_usd` 2 for its own passes (section 5).
- `task_max_steps` (6) also bounds `add_next_step` from the supervisor (manual appends have no cap today; the
  supervisor gets one, Fred keeps his freedom).
- Always Fred: a Fable confirm (`fable_ok`, plan 17 D13), a pace hold (`Run anyway`), Delete / Clear, Allow runs,
  plan edits (`POST /api/task/plan`), Redo design, Pause / Resume, a project not in `config.json` (`Hub._base`
  refuses the start anyway), any attachment, a step whose source is an external session.
- A pending guidance (plan 42) blocks every dispatch; the decision is logged `held: pending guidance` and re-raised
  when the queue empties.

## 8. Stuck detection and take over

"Stuck" is three concrete things, each with its own flag in the wake:

1. **`stuck` state** (code already decided): second bad handoff, `verify failed twice`, a usage limit, a write or
   shell refusal, a route that cannot run. Wake at once. Allowed moves: `retry` with a note and a tier word (the
   retry runs on `step_route` with the step's `avoid` list of plan 43 and the limits of plan 40 still applied),
   `add_next_step` of kind `scout` from a done step when the failure needs reading first (sources allow it only when
   no later step is unfinished, so usually not while the stuck step stands), `escalate_to_fred`.
2. **`stalled` run**: the current step's session reads `stall` in `state.state_of` (no events for `stall_after_s`
   600 and the process alive) for `supervisor_stall_s` (1800) in all. One wake per attempt. D6 (a): report only,
   in every mode: the decision `stop` becomes a card "Stop and retry?" whose Approve runs `task_lever("stop")` (the
   stream-json interrupt through `runs.stop`; the step ends `failed`, task `stopped`) and, on the wake that follows,
   a suggested `retry` with the note `the earlier attempt stalled for 30 min`. Never on the other harnesses'
   capless runs, which `step_timeout_s` already ends.
3. **A FAIL loop**: a manual task whose last two steps are `verify` FAIL and `code` from it, again FAIL: the second
   FAIL wake may not add another code step (`supervisor_max_retries` counts a FAIL-then-code pair as one retry);
   `escalate_to_fred` with both FAIL details.

Waiting on a question longer than `supervisor_ask_s` (3600) is not stuck: the Board's Needs you shows it already; a
wake would spend tokens to say so. Take over never: kills a process (`kill_tree` stays for runs an earlier service
left), resumes or forks a VS Code / terminal chat (not a task step; `Hub.levers` fork rule untouched), edits files
in the project, writes the plan, answers a Fable confirm, or starts a step whose project is not allowed.

## 9. Intake: from a typed prompt to a supervised task

Today a typed prompt is a chat task (`/api/run` -> `Hub.chat_task`) or, through Prep, Run as task (`/api/task` ->
`Hub.create_task`, an automatic chain) with the Prep card routing it (`prep_prompt.md` type table, demand, steps,
`routing.pick`). The router stays Prep: it scouts with tools in the project, which the supervisor never does, and it
runs for every prompt including plain chats. The supervisor does not become the router (D7).

Proposed (D7 a): the Prep card gains **Run supervised** next to Run and Run as task. It creates a manual task
(`progression: "manual"` from the start, `task["supervisor"]["mode"]` from the project default or `auto` when the
button is explicit) with Prep's first step only (`card["steps"][0]`, usually `scout` or `design`; a card without
steps gets one `scout` with the enhanced prompt as its goal). The step ends at `choose next step` and that is the
supervisor's first wake: it adds the next step from the real outcome, one at a time, within the caps. Prep's later
steps are kept in `task["supervisor"]["proposed"]` and shown in the digest as "Prep proposed: code, test" so the
supervisor keeps the intent without being bound to it. Run as task (the automatic chain) is unchanged: there the
supervisor only wakes at `stuck` and (D12 a, slice C) once at `done`.

## 10. The Board

Minimal, in the existing inspector (plan 25) and the task page dock (plan 39):

- One line in the task head: `Supervisor: suggest · 3 wakes · $0.004`, with a select `off / suggest / auto` that
  writes `POST /api/task/supervisor`. `off` is the pause switch; nothing else.
- A suggestion card in the task conversation panel (plan 42's shared panel, above the composer, same place a
  question shows): `Supervisor suggests: Add verify step. <reason>` with the instructions folded, **Approve** and
  **Reject** (`POST /api/task/supervisor {task, wake, action}`); Reject takes an optional note that the next wake
  reads under "Fred rejected: ...". A pending suggestion puts the task in Needs you (D9 a).
- Skills on a step (section 14): the Board step row's second line gains `skills: ui-ux, design-review` when the
  step ran with any; the Add next step form and the Prep card's step rows carry the skills multi-select.
- A `Supervisor` fold under the chain (next to Received / Handoff / Route / Plan): the decision log from
  `GET /api/task` `supervisor` (last 10 of `supervisor.jsonl`: time, trigger, decision, reason, cost, outcome, by).
- Chain rows: `supervisor: add_next_step verify (auto) · $0.001`, `supervisor suggested: finish`,
  `supervisor refused: a later step has not finished`, `approved by Fred`, `rejected by Fred: ...`.
- The Usage page's spend breakdown gets one `supervisor` row (its passes are priced from the result line as the
  brief's are).

## 11. Audit and safety

- `tasks/<id>/supervisor.jsonl`, append only: `{"ts", "wake", "triggers", "digest_bytes", "model", "cost",
  "decision": {...}, "check": "" | why, "mode", "dispatch": {"call", "request_id", "status"}, "by": "auto" |
  "fred approve" | "fred reject", "outcome": "started 04" | "refused: ..." | "held" | "uncertain"}`. Masked by
  `redact.mask` like a note. `tasks.clear` keeps it with task.json and chain.jsonl.
- Idempotent dispatch: the request id of an `add_next_step` is `uuid5(sup-<task>-<wake>)`, so `request_next`
  returns the same step on a repeat (plan 36 3.4) and a crash between the log line and the launch never makes two
  steps. A lever dispatch is logged `dispatching` before the call; on restart a line left `dispatching` with no
  outcome is `uncertain`: shown on the card, never replayed (plan 42 rule), dismissed by Fred.
- The supervisor is never run while `tasks.pending_messages(task)`; its dispatch takes `Hub.tlock` like a click.
- Every decision passes the same gate a click passes; the model's JSON is data. `check` refuses any field the schema
  does not name, any `kind` outside `NEXT_KINDS`, instructions over `STEP_GOAL_MAX`, a `model` that is not `"auto"`
  or a tier word, a `source_step` whose `next_sources` entry is not `""`.
- Replayable: `py -m console --supervisor-replay <task> <wake>` rebuilds the digest from the folder as it stands and
  prints the decision the log holds next to a fresh dry run (no dispatch): the way to tune the kind file.
- Nothing is written outside `~/.claude/console/` (the plan 28 mirror stays the one exception); config.json gets its
  keys through `paths.ensure_config` and the Models page whitelist (`console/tuning.py`) for the numbers.

## 12. Phasing

1. **Slice A, suggest only**: `console/supervisor.py` (SCHEMA, `digest`, `check`, `run`), the kind file, wakes on
   the manual boundary after a `design` or `verify` step and on `stuck`, `supervisor.jsonl`, the Board card and the
   fold, `POST /api/task/supervisor`, config keys with `supervisor_mode` `suggest`, fake claude words
   (`SUP-VERIFY`, `SUP-CODE`, `SUP-FINISH`, `SUP-ESCALATE`, `SUP-BAD`), tests for digest size, check refusals,
   idempotent request ids, no wake with pending guidance. Skill library part 1 (section 14.7): the folder and its
   seeds, the `index.json` registry, code-only matching by kind, the selected bodies inlined in the step prompt,
   `received.md` and the chain `read:` line naming them, the Board chip. Fred's live check on one real manual task.
2. **Slice B, auto within caps**: the `auto` mode and the hard stops, Run supervised on the Prep card, every manual
   boundary as a wake, `confirm` / `keep` on plan holds, the Usage row. Skill library part 2: Prep's `tags`, the
   supervisor's `skills` field, Fred's override on the Prep card and the Add next step form.
3. **Slice C, take over**: `stalled` detection with the suggested `stop` then `retry` (D6 a), `supervisor_stuck_model`,
   per-project modes (D11 a), the `done` wake for automatic chains (D12 a), the replay command. Skill library part 3:
   the Skills tab next to Kinds, the plan parts' `tags`, the optional `--add-dir` loading mode (D17).

## 13. Risks and non-goals

Risks: a loop of steps that each look reasonable (bounded by `supervisor_max_auto_steps`, `task_max_steps` and
`supervisor_work_usd`); an instruction that drifts from the plan (the digest carries the plan's Acceptance and the
verify kind already fails `plan drift`); haiku misreading a FAIL detail (a FAIL-then-code pair counts as a retry and
the second goes to Fred); cost hidden in many small passes (its own row on Usage and the per-task line); a wake
storm after a restart (one wake per task, only where the last chain line has no decision); the kind file growing
into an orchestrator prompt (kept under 1,500 tokens, reviewed with the replay command).

Non-goals (BRAINSTORM 2, D16, D-1): no always-on session, no scheduler or timer beyond the existing hub tick, no task
graph (one step added at a time, linear numbering as plan 39 leaves it), no cross-task or cross-project decisions,
no supervision of VS Code / terminal / other-CLI chats, no Agent tool, no MCP, no model writing into the task folder
or the project, no new dependency, no plan rewriting by the supervisor (a plan change is still the replan step or
Fred's edit).

## 14. A skill library inside the Console (Fred's second idea, 2026-10-17)

Fred: steps should get the skills that fit their work and nothing else. A design step on UI work gets the design and
ui-ux skills; a code step on the service does not pay for them.

### 14.1 What loads today, and what the docs say (code.claude.com/docs/en/skills and cli-reference, read 2026-10-17)

- A step run (`claude_cli.run_command`) passes `--disallowedTools Agent`, `--tools`, `--strict-mcp-config`, caps and
  `--session-id`; nothing about skills. So every personal skill in `~/.claude/skills/` (route-model,
  session-handoff, whatever else Fred keeps) and every project skill in `<project>/.claude/skills/` loads its
  description into each step's context, whether the step needs it or not. Prep and the brief pass `--disable-slash-commands`
  ("Disable all skills and commands for this session"), so they pay nothing.
- Discovery: personal `~/.claude/skills/<name>/SKILL.md`, project `.claude/skills/`, nested `<subdir>/.claude/skills/`
  (loaded on first read in that subdir), plugins, and "`.claude/skills/<skill-name>/SKILL.md` in a directory passed
  with `--add-dir`" (the skills page; `--bare` confirms "Skills in a directory you pass with `--add-dir` still load").
  Descriptions are always in context, the body "only loads when invoked"; `disable-model-invocation: true` "removes
  the skill from Claude's context entirely"; `skillOverrides: {"name": "off"}` in settings (so through `--settings`)
  turns one off; `Skill(name)` permission rules gate invocation. "Claude Code ignores a field it doesn't recognize
  without reporting an error", so a SKILL.md may carry Console-only frontmatter and stay a valid Claude skill.
- The repo convention: `dotclaude/skills/<name>/SKILL.md` are real Claude skills Fred copies to `~/.claude/skills`;
  `dotclaude/console/kinds/*.md` are seeds `kinds.ensure` copies to `~/.claude/console/kinds/` at service start,
  editable there, never overwritten (plan 28). Only the other three harnesses have no skill mechanism at all.

### 14.2 Where the library lives

`~/.claude/console/skills/<name>/SKILL.md` (plus any files the skill references), seeded from
`dotclaude/console/skills/` by `skills.ensure(home)` exactly as kinds are (D14 a). It is the Console's own library:
not copied to `~/.claude/skills`, never loaded by a VS Code chat, read by the service only. Fred adds a skill by
dropping a folder there and one line in `index.json` (14.3). A skill may also be a pointer: an index entry with
`"source": "~/.claude/skills/<name>"` and no folder makes a personal skill selectable per step without a copy.

### 14.3 The registry: a hand-edited `index.json` (D15 b)

`~/.claude/console/skills/index.json`, one object keyed by skill folder name, is the registry. SKILL.md keeps only
Claude's own frontmatter (so a skill copied from `~/.claude/skills` works unchanged); what the Console needs to pick
it is in the index, which Fred edits by hand (or on the Skills tab, slice C):

```json
{"ui-ux-review": {
   "description": "Checks a screen against the Console Cells rules (tokens, 340 px, state never colour alone).",
   "kinds": ["design", "verify", "code"],
   "tags": ["ui-ux", "web"],
   "paths": ["web/**"],
   "always": false},
 "handoff-quality": {
   "description": "How to write a six-heading HANDOFF block that passes the brief checks.",
   "kinds": [], "tags": [], "paths": [], "always": true}}
```

Fields: `description` (shown on the Board and in the supervisor's digest; a missing one falls back to the SKILL.md
`description` frontmatter, else the folder name), `kinds` (step kinds it may ride with; `[]` = any), `tags`
(matched against the task's tags), `paths` (globs matched against the plan part's Files or the source's Files
touched), `always` (every step of its kinds, no tag needed). Unknown keys are ignored and kept.

- `skills.ensure(home)` copies the seed folders from `dotclaude/console/skills/` and, when `index.json` is missing,
  writes the seed index `dotclaude/console/skills/index.json`; when it exists, it adds only the entries of seed skills
  the index does not name (so a new seed shows up after an update) and never rewrites an entry Fred edited, as
  `kinds.ensure` never replaces an edited kind file. The write goes through a temp file and `os.replace`
  (plan 34 rule). Nothing else writes the index.
- `skills.registry(home) -> dict` reads the index once per service start and again when its mtime or the folder
  listing changes (as `Hub.reload_tuning` watches config.json). It joins the index with the folders:
  - an entry whose folder or SKILL.md is missing: listed with `why: "no SKILL.md"`, never picked;
  - a folder absent from the index: listed with `why: "not in index.json"` and the SKILL.md description, never picked
    by code or the supervisor; Fred may still pick it by hand (the multi-select shows it dimmed), which is the
    cheap way to try a new skill before indexing it;
  - an invalid entry (not an object, `kinds` with an unknown kind, `tags` or `paths` not lists of strings, `always`
    not a bool): listed with `why: "index: <what>"`, never picked; an unparsable index.json keeps the last good
    registry and the task head says `skills: index.json invalid`.
- `GET /api/config` gains `skills: [{name, description, kinds, tags, paths, always, kb, why}]` for the window, in
  index order, the unindexed folders last.

### 14.4 Who picks (D16 a: code first, the supervisor and Fred on top)

1. **Code** (`skills.pick(registry, kind, tags, files, cfg) -> list`, pure, tested): a skill is picked when `kind`
   is in its `kinds` (or `kinds` is empty) and (`always`, or one of its `tags` is among the step's tags, or one of
   its `paths` globs matches a file the step is about). Ordered `always` first, then by the number of matches. No
   count or size limit (D18, Fred): selection by kind, tags and paths alone decides what loads; the received.md
   line and the Board chip show each skill's size so Fred sees what a step paid. Deterministic: the same inputs
   give the same list.
2. **Tags come from** (in order, merged): Prep's card, whose SCHEMA gains `tags` (a list of short words the prompt
   asks for from a fixed vocabulary the registry advertises: `tags` of every skill, plus `backend`, `web`, `tests`,
   `docs`, `data`); the plan part's `Files` and a `Tags:` line the design kind file asks for under each `### Step N`;
   the step's own instructions when Fred or the supervisor wrote them (matched word for word against the vocabulary);
   the source step's `Files touched` for the `paths` match.
3. **The supervisor** may add `"skills": ["ui-ux-review"]` to an `add_next_step` decision. `supervisor.check`
   validates every name against the registry and the kind, and the digest lists the registry (name and description
   only, about 20 tokens per skill) under "Skills available". An unknown name or a kind mismatch is logged and
   dropped, the rest are kept.
4. **Fred** overrides last: the Prep card's step rows and the Add next step form carry a skills multi-select (preset
   to the code's pick; `none` empties it); `step["skills"]` is stored as picked, with `step["skills_by"]`
   (`code`, `supervisor`, `fred`). A Fred pick beats code and the supervisor; an empty Fred pick stays empty.

### 14.5 Enforcement: unselected skills are not loaded (D17 a)

The selected skills ride **inside the step prompt**: `tasks.step_prompt` gains a `$skills` slot right after the role
text, "Skills for this step:" then each SKILL.md body whole (frontmatter stripped, `redact.mask`ed, never cut or
trimmed for size), and nothing else. The step run adds `--disable-slash-commands`, so no personal or project skill
description reaches a step's context any more (today they all do): a step pays only for what was picked. This is
harness-neutral (Codex, OpenCode and Command Code steps get the same text), deterministic (the body is in the prompt,
not behind a Skill call that may never happen), and the prompt is saved whole as role.md's neighbour
`skills.md` in the step folder, so the Board's Received tab shows exactly what the step read. The chain `read:`
line gains `skills ui-ux-review, design-review` and `received.md` lists them with their size.

The rejected (b), a per-step staging folder `<step dir>/skills/.claude/skills/<name>/` passed with `--add-dir` so the
skills load as real skills (description in context, body on invocation), saves tokens only for long skills that a
step may not invoke, works on Claude only, and would make the service write `.claude/` folders under the task
folder; it stays an option for slice C for a very long skill a step may never invoke.

Window runs that are plain chats (`chat_task`) are unchanged: a chat is Fred's session and keeps its personal skills
and slash commands (the Hand off lever runs `/session-handoff` there). Only task steps carry the library.

### 14.6 Where the choice shows and is logged

- Board: the step row's second line `skills: ui-ux-review, design-review` (chip, `skills_by` in its title); the
  Received tab shows `skills.md`; the Add next step form shows the preset with "picked by code from tags ui-ux, web".
- `chain.jsonl`: in the step's start line notes (`read: brief 02 · plan 12.4 KB · skills ui-ux-review`).
- `supervisor.jsonl`: the decision JSON as answered (its `skills`), the check's refusals, and the final list the
  step started with.
- `received.md`: `- skills/ui-ux-review/SKILL.md (6.1 KB, picked by code)`.
- Nothing in the project folder; nothing outside `~/.claude/console/`.

### 14.7 Slicing (also folded into section 12)

Slice A: the folder, `skills.ensure` with the seed `index.json`, the registry, `skills.pick` by kind, `always` and `paths` from
the source's Files touched, the `$skills` slot, `--disable-slash-commands` on steps, `skills.md`, received.md and
the chain line, the Board chip, two seed skills (`handoff-quality`: how to write a six-heading block that passes the
brief checks, kinds any, always; `ui-ux-review`, kinds design / verify / code, tags ui-ux / web). Slice B: Prep's
`tags`, the supervisor's `skills` field, the multi-selects on the Prep card and the Add next step form. Slice C: the
Skills tab next to Kinds (edit in place, no size cap), the plan parts' `Tags:` line, the `--add-dir` mode
behind `skills_load: "inline" | "add-dir"`.

## 15. Decisions (Fred, 2026-10-17: option (a) on D1 to D17 except D15 (b); D18 no limit)

| # | Question | Taken |
|---|---|---|
| D1 | Default mode | `suggest` everywhere; `auto` per project or per task is Fred's switch |
| D2 | Slice A's wake set | the manual boundary after a `design` or `verify` step, plus `stuck` |
| D3 | What the pass reads | the code-built digest only, no tools |
| D4 | Model | haiku; sonnet once on a `stuck` or `stalled` wake; never opus or fable |
| D5 | Questions (`asks:`, Plan gap) | never answered by the supervisor; always Fred |
| D6 | Stalled runs | report only: a card "Stop and retry?"; the Stop is Fred's Approve |
| D7 | Intake | Run supervised on the Prep card: a manual task with Prep's first step, the rest kept as proposed |
| D8 | Caps | auto steps 3, retries 1 per step, own spend $0.50 per task and $2 per day, work $5 since Fred's last act |
| D9 | A pending suggestion | counts in Needs you, like a question |
| D10 | Fixed prompt | a kind file `supervisor.md` through `kinds.text`, editable on the Kinds tab |
| D11 | Per-project override | `supervisor_projects` map in config.json, edited on the Models and tuning page |
| D12 | Automatic chains at `done` | one suggest-only wake asking whether a step is missing, when room is left |
| D13 | `stepdone` | suggest only, at every mode |
| D14 | Where the skill library lives | `~/.claude/console/skills/`, seeded from `dotclaude/console/skills/` like kinds, read by the service only |
| D15 | Registry format | (b), Fred 2026-10-17: a hand-edited `index.json` in the library folder (name -> description, kinds, tags, paths, always), seeded by `skills.ensure`; SKILL.md keeps Claude's frontmatter only |
| D16 | Who picks skills | code by kind, tags and paths; the supervisor may add names; Fred overrides last |
| D17 | How the pick is enforced | bodies inlined whole in the step prompt plus `--disable-slash-commands` on every step run, saved as skills.md |
| D18 | Skill limits | no limit (Fred, 2026-10-17): no cap on the count per step or the size of a skill, nothing trimmed or refused for size; kind, tags and paths alone decide what loads |

Nothing is open.

## History

- 2026-10-17 - Brainstorm written from Fred's request, read against plans 17, 23, 24, 33, 35, 36, 39, 41, 42 and
  the code (`console/tasks.py`, `console/server.py`, `console/replan.py`, `console/compact.py`,
  `console/claude_cli.py`, `dotclaude/`). No code changed. Thirteen decisions open.
- 2026-10-17 - Fred took (a) on D1 to D13 (section 15); the body now reads for them. Fred's skill library idea added
  as section 14, checked against the skills and CLI reference pages of code.claude.com (discovery paths, `--add-dir`,
  `--disable-slash-commands`, `skillOverrides`, unknown frontmatter ignored); D14 to D18 open.
- 2026-10-17 - Fred took (a) on D14, D16 and D17, (b) on D15 (a hand-edited `index.json`, section 14.3) and ruled
  no limit on D18: every skill cap left the design (section 15). Nothing is open.
