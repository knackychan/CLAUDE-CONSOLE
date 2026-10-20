# Plan 51 - Supervisor loose ends: a model in a next-step message, after Reject, the uncertain card

Status: written 2026-10-20 from the supervision review (items 3, 6 and 8). D1-D6 are written in as defaults; Fred
confirms or changes them before step 1. No code changed. Lands on plans 36, 44 (backend), 48 and 49.

## 1. Finding

**Item 3: a next-step message cannot name a model.**

- `supervisor.check`, `add_next_step` branch (console/supervisor.py, after the instructions test): `model != "auto"`
  is refused ("a supervisor step runs on model auto"). `supervisor.run` fills a missing or blank model with `auto`.
- `Hub._supervisor_dispatch` (console/server.py ~1950) builds the request with `"model": "auto"`; for a message wake
  the instructions are Fred's words verbatim (plan 48 D6/D11, plan 49 D2).
- If Fred writes "verify the 340 px case on opus", the step runs on auto and nothing says so. The box's timing line
  (`Hub.message_availability`, server.py:1137) and the footer (`stepFooter`, app.js:3483) do not mention a model.
- `Hub._next_route` (server.py:2513) checks a requested model as an exact rung: `requested != "auto" and
  route["rung"] != requested` is refused. A tier word such as `opus` is routed by rank in `tasks.route` (tasks.py:160-185):
  the balance picks the emptiest rung of that rank, which may be a ladder rung that is not spelled `opus`, so the
  request would be refused as "selected model cannot run this step". Today's menu form sends rungs, so it only hits
  this when a ladder rung and its rank share a name.

**Item 6: after Reject the task waits with no hint.**

- `Hub._sup_reject` (server.py:2160): writes an `outcome` record (`status: rejected`, `action: reject`, `note`), sets
  `pending = None`, keeps the note in `sup["reject_note"]` for the next real wake. No wake is queued.
- `supervisor_view` (server.py:2187) sends the last ten audit records as `{ts, wake, phase, status, decision, cost,
  error}`; a reject's `decision` is "" (its record has none), and the view does not say whether a note waits.
- `supCard` (app.js:3835) then shows "Supervisor · last decision" for the newest record that has a decision, i.e. the
  suggestion Fred just rejected, quiet, as if it still stood. Nothing says what to do next, though the box below is
  already in `next` mode at a supervised boundary.

**Item 8: an uncertain card loses its decision after a restart.**

- `supervisor.fold_log` (console/supervisor.py:249-302) keeps `w["decision"]` from the wake's result record, but the
  uncertain branch (lines 292-294) builds `pending` with `"decision": None` and `"dispatch": None`, and no triggers.
- `reconcile_supervisor` (server.py:1483) copies that pending into task.json when it differs, so after a restart the
  card reads "Supervisor dispatch: outcome unknown" with "Add a step" or an empty sentence, and the plan 48 section 7
  recovery box (app.js:3790) can only say "wake N".
- The dispatching record carries the intent (`dispatch: {call, request_id | lever, source_step, proposal}`), which is
  what Fred needs to check before Dismiss.

## 2. Decisions (defaults, Fred confirms)

| # | Question | Default |
|---|---|---|
| D1 | Can a next-step message name a model | Yes, a tier word only: `haiku`, `sonnet` or `opus` (plan 44's Retry words). Never `fable`, a rung or another harness: those stay on the task menu's Add step on a model. |
| D2 | Who reads the word and what guards it | The supervisor returns it as `model`; `check` accepts a tier word only on a wake whose triggers include `message`, and only when that word appears as a whole word in Fred's claimed text (case-insensitive). Otherwise `auto` is still the only model. Every live gate stays (Fable never reachable, pace hold, limits, `rung_ok`). |
| D3 | How a tier word routes | `_next_route` treats a bare rank (`haiku`, `sonnet`, `opus`) as a rank pin: accepted when `fills.rank_of(route["rung"])` equals it, refused with `rung_ok`'s reason otherwise. A rung keeps today's exact check. |
| D4 | What the box says | The timing line adds: "Model: auto, or haiku, sonnet or opus when you name one. An exact model is in the task menu." |
| D5 | After Reject | `supervisor_view` gains `rejected: {wake, note}` when the newest record is a reject outcome and nothing is pending. `supCard` then shows "You rejected wake N" with the rejected decision struck as text (not as the standing decision), then: in `next` mode "Write what to do instead in the box below" plus "your note goes with it" when one waits; otherwise "Add step on a model or Finish task is in the task menu". No new button. |
| D6 | The uncertain card after a restart | `fold_log` keeps the wake's decision, triggers and the dispatching record's intent on the uncertain pending. The card shows the decision sentence and "Outcome unknown"; Dismiss stays the only action (`can_approve` is false for `uncertain`), never replayed. The recovery box names the decision: "The supervisor's wake 4 dispatch (Add 03 code) has an unknown outcome ...". |

## 3. Changes

### 3.1 `console/supervisor.py`

- `TIER_WORDS = ("haiku", "sonnet", "opus")`.
- `check`, `add_next_step`: replace the model test with: `model = decision.get("model")`; accepted when `model ==
  "auto"`, or when `model in TIER_WORDS`, `"message" in triggers` and `re.search(rf"\b{model}\b", policy.get("fred_words")
  or "", re.I)`. Refusal texts: "a supervisor step runs on model auto" (no message wake), "the model must be one Fred's
  message names" (a word he did not write).
- `fold_log`: on a `dispatching` record keep `w["dispatch"] = rec.get("dispatch")` and `w["triggers"] =
  rec.get("triggers") or w.get("triggers")`; on a result record keep `w["triggers"]`. The uncertain pending becomes
  `{"wake", "events", "triggers": w["triggers"] or [], "decision": w["decision"], "status": "uncertain", "error": ...,
  "by": "", "dispatch": w["dispatch"]}`.
- `kinds/supervisor.md` line (dotclaude): "When $you's words name haiku, sonnet or opus, return that word as model;
  otherwise model auto." Fred copies the file (Models page Reset to repo copy).

### 3.2 `console/server.py`

- `_sup_snapshot` context: `fred_words` = the same joined text as `fred_next`; the judge's `check` policy gets it.
- `_supervisor_dispatch`: the `check` policy dict gains `"fred_words": said`; `req["model"] = decision.get("model") or
  "auto"` (a non-message decision can only carry `auto`, `check` already refused anything else).
- `_next_route`: `if requested in supervisor.TIER_WORDS:` compare `fills.rank_of(route["rung"], self.cfg) ==
  requested` (refused with `self.rung_ok(...)` or "no usable <word> model for this step"); else today's rung check.
- `message_availability` (server.py:1137): the D4 sentence appended to the `next` timing.
- `supervisor_view`: `rejected` per D5: when `pending` is None and the last record has `action == "reject"` and
  `status == "rejected"`: `{"wake": r["wake"], "decision": <that wake's result decision word>, "note":
  bool(sup.get("reject_note"))}`; else `None`.
- Chain line of a message dispatch with a model: `supervisor: dispatched add_next_step on opus by fred (message)`.

### 3.3 `web/app.js`

- `supCard`: before the quiet "last decision" branch, `sup.rejected` draws `askbox quiet dec` with "You rejected wake N",
  `decisionText` of the rejected word with the class `was` (struck through), and the D5 line by `d.message.mode`.
- `decisionText` already prints `on <model>` for a non-auto model; no change.
- `recoveryBox` (app.js:3790): the uncertain dispatch line adds ` (${decisionText(pending.decision, t)})` when the
  pending has a decision.

### 3.4 `web/style.css`

`.sup-card .act.was { text-decoration: line-through; color: var(--mut); }` (tokens only).

### 3.5 Docs

CLAUDE.md is unchanged (no new route). PLAN row 51 and History.

## 4. Tests (first, red)

`tests/test_supervisor.py`:

- `test_message_step_may_name_a_tier_word`: `opus` with triggers `message` and fred_words "verify on Opus" ok;
  `opus` without the word refused ("names"); `opus` on a `choose_next` wake refused; `fable` and a rung refused on a
  message wake; `auto` ok everywhere; "sonnets" does not match `sonnet` (whole word).
- `test_fold_keeps_uncertain_decision_and_intent`: claimed, result (add_next_step, triggers), dispatching (intent with
  request_id) -> pending status uncertain, decision kept, triggers kept, dispatch equal to the intent; a dispatching
  record with no result before it -> decision None (unchanged).

`tests/test_supervisor_server.py`:

- `test_message_on_opus_routes_by_rank` (NextMessageTest): message "verify on opus", the pass returns model opus ->
  `request_next` gets model `opus`, the step's route rank is opus, chain says `on opus by fred (message)`.
- `test_message_model_not_written_falls_back_refused`: the pass returns opus for "verify it" -> refused card, the words
  come back to Fred with Resend (plan 48 D11), nothing appended.
- `test_reject_view_says_what_next`: Reject with a note -> `supervisor.rejected == {wake, decision: "add_next_step",
  note: True}`; a new pending card clears it; Reject without a note -> `note: False`.
- `test_uncertain_card_keeps_decision_after_restart`: extends the restart case of
  `test_dispatching_lever_becomes_uncertain_never_replayed` with a result record: the rebuilt pending carries the
  decision and the intent, Approve stays 409, Dismiss works, no lever call.

`tests/test_server.py`: `test_next_route_accepts_a_rank_word` (a ladder rung of rank opus chosen for requested `opus`
is accepted; requested `opus` with no usable opus rung refused with a reason) and the D4 timing text in the existing
plan 48 availability test.

`tests/test_web.py`:

- `test_sup_card_after_reject_points_to_the_box`: `rejected` with mode next -> "You rejected wake 3", the struck
  sentence, "Write what to do instead in the box below", "your note goes with it" only with `note: true`; mode not
  next -> the task menu line; no Approve or Reject buttons.
- `test_recovery_box_names_the_uncertain_decision`.

## 5. Order and checks

One commit per step, tests first, stage only this plan's lines (other chats edit PLAN.md, CLAUDE.md, `web/app.js`).

1. Tests red (4).
2. `supervisor.py` (3.1, the kind line included). `py -m unittest tests.test_supervisor`.
3. `server.py` (3.2). `py -m unittest tests.test_supervisor_server tests.test_server` (run in the background: about
   9 minutes), then the full suite.
4. `web/app.js`, `web/style.css` (3.3, 3.4). `py -m unittest tests.test_web`, `node --check web/app.js`.
5. Docs.

Headless check (fake claude, scratch home, as plan 48): a next-step message "verify on opus" starts a step on an opus
rung; Reject a suggestion and read the hint; stop the service during a dispatch, start it, open the task: the card
names the decision. 400 and 340 px.

Live check (Fred): one next-step message naming a model; one Reject with a note, then a message.

## 6. Not done here

- Stall wakes for Codex, OpenCode and Command Code (review item 9) and the client's `supMode()` mirror (item 10).
- A message that names `fable` or an exact rung: the task menu's Add step on a model.
- No automatic wake after Reject (plan 44 4.4: refusals and rejections never wake; the note waits).
