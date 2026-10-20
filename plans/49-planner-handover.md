# Plan 49 - The planner's steps reach the supervisor

Status: written 2026-10-20 from the supervision review (items 1 and 2). D1-D4 are written in as defaults; Fred
confirms or changes them before step 1. No code changed. Lands on plans 36, 44 (backend), 47 and 48.

## 1. Finding

- Plan 47's Opus pass writes each step's kind, goal and model. A supervised task keeps steps 2..n as
  `task.supervisor.proposed` (`Hub._supervised_task`, server.py:2910), but the supervisor's digest carries only
  their kinds: "- Prep proposed kinds: code, verify" (`supervisor.digest`, supervisor.py:418). The Haiku pass
  then writes each step's instructions again from the design plan and handoff; the planner's goal text never
  reaches a worker.
- `proposed` is written once and never trimmed. `routeHtml` (app.js:3805) numbers the proposals after the
  latest step, so after step 02 is added the route still shows every original proposal as 03, 04, ...: stale,
  and one of them is the step that already ran.
- `supervisor.revision` leaves `proposed` out, so a decision that names a proposal could be checked against a
  list that has changed since.

## 2. Decisions (defaults, Fred confirms)

| # | Question | Default |
|---|---|---|
| D1 | How the supervisor takes a proposal | New optional `add_next_step` field `proposal` (integer, 1-based index into the live `proposed` list). With it, `kind` may be omitted and must equal the proposal's kind when given; `instructions` may be omitted. |
| D2 | Whose words become the step's instructions | Fred's next-step message words (plan 48 D6/D11), else the proposal's saved goal verbatim, else the supervisor's `instructions`. With a proposal, the supervisor's own `instructions` are ignored (the planner's text is the reviewed one). |
| D3 | Which proposals a new step removes | Any step added through `request_next` (supervisor, message, Fred's menu Add step on a model) trims the list: with a `proposal` k, items 1..k go (a skipped earlier proposal is passed over); without one, the first item of the same kind goes; no match, nothing goes. |
| D4 | The proposal's model | Unchanged: a supervisor step still runs on `auto` (review item 3 is separate). The digest shows the planner's model so the reason can mention it. |

## 3. Changes

### 3.1 `console/supervisor.py`

- `_OPTIONAL` gains `"proposal": int`; `_FIELDS["add_next_step"]` gains `"proposal"`; `SCHEMA["properties"]` gains
  `"proposal": {"type": "integer", "minimum": 1}`.
- `run`: the model fill (`model` blank -> `auto`) stays. When `proposal` is set and `kind` is missing, fill `kind`
  from `task["supervisor"]["proposed"][proposal - 1]` if that item exists (else leave it; `check` refuses).
- `check`, `add_next_step` branch, before the kind test:
  - `p = decision.get("proposal")`; when set: `items = (task.get("supervisor") or {}).get("proposed") or []`;
    refuse `"proposal p<N> is not in the planned list"` when `p > len(items)`; refuse
    `"kind differs from proposal p<N>"` when `decision.get("kind")` is set and differs from `items[p-1]["kind"]`.
  - The instructions test runs only when `proposal` is absent (D2).
  - Everything after (model auto, source, levers, sources) is unchanged.
- `digest`: replace the "Prep proposed kinds" line with a block inside the mandatory gates:

  ```text
  - Planned next (the planner's steps; name one with proposal: N):
    p1 code (sonnet): <goal, redact.clip 300>
    p2 verify: <goal, redact.clip 300>
  ```

  At most `PROPOSED_SHOWN = 8` items, then `... N more`. The model in brackets only when the item has one.
- `revision`: `data["proposed"] = [[p.get("kind"), p.get("goal")] for p in sup.get("proposed") or []]`. This makes
  every saved pending card stale once after the upgrade (Approve answers 409 "the task changed since this
  suggestion"); acceptable, said in History.
- New pure helper `trim_proposed(proposed: list, kind: str, proposal=None) -> list` implementing D3; no IO.

### 3.2 `console/server.py`

- `_supervisor_dispatch`, `add_next_step` branch: `p = decision.get("proposal")`; `item = sup["proposed"][p-1]` when
  set. `req["kind"] = decision.get("kind") or item["kind"]`; `req["instructions"] = said or (item["goal"] if item
  else decision["instructions"].strip())`; `req["proposal"] = p` when set. `intent` gains `"proposal": p`.
- `request_next`: read `proposal = request.get("proposal")` (accepted only when `origin == "supervisor"` and an int;
  ignored otherwise). It is not added to `payload`, so the plan 36 `request_hash` of a repeated request id is
  unchanged. After `tasks.append_step`, when `updated.get("supervisor")` is a dict: `sup["proposed"] =
  supervisor.trim_proposed(sup.get("proposed") or [], payload["kind"], proposal)`, inside the same `_commit`.
  A repeated request id returns before this, so it trims once.
- `_supervisor_dispatch` already calls `request_next(..., origin="supervisor")` (server.py:1983) after
  `preview_next(req)`; the extra `proposal` key in `req` is not read by `preview_next`.

### 3.3 `dotclaude/console/kinds/supervisor.md`

Replace the first bullet's "add the first write step of that plan" with: "when the digest lists Planned next,
take the first one that still fits with `proposal: N` and no instructions; write your own instructions only when
no planned step fits, quoting the plan's Step heading, files and done check." Fred copies the file to
`~/.claude/console/kinds/` (Models page Reset to repo copy).

### 3.4 Web

None. `routeHtml` already draws `t.supervisor.proposed`; trimming the saved list fixes the stale rows.
`decisionText` keeps "Add 03 code from 02's handover"; when the decision has `proposal`, it adds " (planned p1)".

## 4. Tests (first, red)

`tests/test_supervisor.py`:

- `test_digest_lists_proposed_goals`: two proposals -> "p1 code (sonnet): fix" and "p2 verify: ..." lines; nine
  proposals -> eight lines and "... 1 more"; no "Prep proposed kinds" line.
- `test_check_proposal_index_and_kind`: p1 ok without kind or instructions; p3 of two refused; kind verify vs a
  code proposal refused; no proposal and no instructions still refused.
- `test_run_fills_kind_from_proposal`.
- `test_trim_proposed`: index k drops 1..k; kind match drops the first of that kind; no match keeps all.
- `test_revision_changes_with_proposed`.

`tests/test_supervisor_server.py`:

- `test_proposal_step_uses_planner_goal_and_trims`: supervised task with proposals code "fix X" and verify "run
  tests"; fake pass returns `add_next_step` `proposal: 1`; Approve -> step 02 kind code, goal "fix X", proposed is
  `[verify]`, `received.md` saved.
- `test_message_words_win_over_proposal`: a next-step message plus `proposal: 1` -> instructions are Fred's words,
  proposal 1 is still trimmed.
- `test_menu_add_step_trims_first_same_kind`: Fred's plan 36 Add step (origin fred, kind verify) drops the verify
  proposal only; a `proposal` field in Fred's body is ignored.
- `test_repeated_request_id_trims_once` (crash after the step is saved, two Hubs, plan 44 recovery).
- `test_stale_proposal_refused`: a pending card names p2, then Fred adds a step from the menu -> Approve 409 stale.

`tests/test_web.py`: `test_route_drops_used_proposal` (route after one added step shows one proposed row).

## 5. Order and checks

One commit per step, tests first, stage only this plan's lines (other chats edit PLAN.md, CLAUDE.md and
`web/app.js`).

1. Tests red (3 to 4).
2. `supervisor.py` (3.1). `py -m unittest tests.test_supervisor`.
3. `server.py` (3.2). `py -m unittest tests.test_supervisor_server tests.test_server`, then
   `py -m unittest discover -s tests`.
4. `supervisor.md` (3.3) and `decisionText` (3.4); `node --check web/app.js`.
5. Docs: PLAN row 49 status and History.

Live check (Fred): a supervised task from a three-step planner card; the first suggestion names p1 and its card
shows the planner's goal; after Approve the route shows one fewer proposed row.

## 6. Not done here

- The proposal's model (D4, review item 3), the mode UI (item 5), the Reject hint (item 6) and the other review
  items stay open.
- No change to plan 47's planner pass or to the scripted chain (mode off keeps `plan_steps`).
