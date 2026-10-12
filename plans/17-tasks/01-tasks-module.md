# Task 1: `console/tasks.py`, the step prompt and the config keys

> Contract: [README.md](README.md) sections 3.2 to 3.7. Depends on nothing. Pure module: no threads, no HTTP,
> no `claude` call. The service (Task 4) is its only caller besides the tests.

**Files**
- Create: `console/tasks.py`
- Create: `console/step_prompt.md`
- Modify: `console/paths.py` (DEFAULTS: the eight keys of README section 4)
- Create: `tests/test_tasks.py`

**Imports allowed in `console/tasks.py`**: `json`, `os`, `re`, `time`, `pathlib.Path`, `string.Template`, and
from the package `claude_cli` (MODELS, EFFORTS), `levers` (escalate_step, miss_line, VERIFY_TEXT, escalate_text),
`routing` (parse, rank, floor), `redact` (mask, clip), `prep` (new_id only). Nothing from `server`, `runs`, `state`.

## Module layout (top to bottom)

```text
docstring: what a task is, where it lives, who writes what
KINDS, PREP_KINDS, EDIT_KINDS, RULES, DISALLOW, HEADINGS, MARK_START = "HANDOFF", MARK_END = "END HANDOFF", NOTE_MAX
TASK_STATES, STEP_STATES, EFFORT_CAP
safe_id(text) -> str
-- routes
verify_route(checked) -> (model, effort)
step_route(kind, *, pick="", checked=None, demand=None, misses=(), prev="", budget=None, warn_at=0.8, effort="auto") -> dict
-- handoff
parse_handoff(text) -> str | None
check_handoff(block) -> str
next_hint(block) -> tuple | None
note_file(task, step) -> str
note_text(task, step, block) -> str
-- steps and the chain (pure, on dicts)
plan_steps(proposed, max_steps) -> list
new_task(project_dir, project, title, goal, steps, type_, demand, prep, effort, now) -> dict
step(task, n) -> dict
current_step(task) -> dict | None
start_step(task, n, session, route, start_commit, now) -> list of chain lines
on_step_ended(task, *, ok, block_error, verdict, verdict_detail, question, now) -> (action, chain lines)
fred(task, lever, now) -> (ok: bool, why: str, chain lines)
-- files
folder(home, task_id) -> Path
save(home, task) -> None
load(home, task_id) -> dict | None
load_all(home) -> dict
log(home, task_id, lines) -> None
write_note(home, task, step, block) -> str
read_note(home, task, n) -> str
prune(home, days, now=None) -> list
clear(home, task, keep_last=True) -> list
-- prompts
step_prompt(task, step, prev_note, retry_reason="") -> str
```

## Signatures and behaviour

- `safe_id(text) -> str`: `text` when it matches `^[0-9a-f-]{1,20}$`, else `""`.
- `EFFORT_CAP = {m: claude_cli.EFFORTS[-1] for m in claude_cli.MODELS}` (checked live: every alias takes `max`).
- `verify_route(checked)` and `step_route(...)`: README 3.5. `budget` is `{family: share of pace}` or `None`.
  `prev` is the previous note's text (for `next_hint`). `checked` is a `(model, effort)` tuple for `verify` and
  `fix`, else `None`. Notes are strings like `rule code: sonnet/medium`, `pick: fable`, `demand: effort high`,
  `floor normal: sonnet/high`, `hint: opus/high -> one step up`, `cap: opus/high`,
  `budget: opus 84 % -> sonnet/xhigh`, `fixed effort: max`. `hold` carries budget holds only (`"opus over its
  pace"`); the Fable confirm is the service's check of `fable_ok`, not this function's.
- `parse_handoff`, `check_handoff`, `next_hint`, `note_file`, `note_text`: README 3.6. `note_text` is the header
  line, a blank line, then `redact.mask(block)` cut at `NOTE_MAX` (20 KB) with a last line `[cut at 20 KB]` (README 3.9).
- `plan_steps(proposed, max_steps)`: keeps items that are dicts with `kind in PREP_KINDS` and a non-empty string
  `goal` (clipped to 200 characters with `redact.clip`); drops the rest; cuts at `max_steps`; appends
  `{"kind": "verify", "goal": "Check step N"}` after the last step whose kind is in `EDIT_KINDS` when the step
  after it is not a `verify`; returns `[]` when fewer than 1 step remain. A one-step list (plus its verify) is
  still a task when the page asks for one; the page decides (Task 5: Run as task shows from 2 proposed steps).
  Each returned step is a full step dict as in README 3.2 with `n` numbered from 1, `pick` from the proposal's
  `model` when it is in `claude_cli.MODELS` (else `""`), all run fields empty.
- `new_task(...)`: the README 3.2 dict with `id = prep.new_id()`, `state = "planned"`, `owner = "service"`,
  `current = 0`, `last_good = 0`, `escalated = ""`, `fable_ok = False`, `why = ""`, `created = updated = now`.
  `effort` must be `auto` or in `EFFORTS` (else `ValueError`). `steps` must be non-empty (else `ValueError`).
- `step(task, n)`: the step dict with that `n` (`KeyError` when none). `current_step(task)`: the step at
  `current`, or `None` when `current == 0`.
- `start_step(task, n, session, route, start_commit, now)`: sets the step `running` with `model`, `effort`,
  `notes` from `route`, `session`, `start_commit`, `started = now`, `ended = None`; `task.current = n`,
  `task.state = "running"`, `task.why = ""`, `task.updated = now`. Returns the chain lines
  (`[{"ts", "step", "from": "planned", "to": "running", "why": " · ".join(notes), "session"}]` plus
  `task:planned -> task:running` on the first start).
- `on_step_ended(task, *, ok, block_error, verdict, verdict_detail, question, now)`: README 3.7 rows for an ended
  step. `block_error` is `check_handoff`'s result or `"no HANDOFF block"`. Returns `(action, lines)` with action
  one of `"wait"` (a question), `"next"` (start `current + 1`), `"done"`, `"fix"` (fix and verify inserted; start
  `current + 1`, which is the fix), `"retry"` (the same step again), `"stuck"`. It mutates `task` (step states,
  `last_good`, `escalated`, `why`, `state`, `updated`, the inserted steps renumbered so `n` stays 1..M) and returns
  the chain lines. The miss line for the fix is NOT written here (no file access): the service writes it with
  `levers.add_miss` when the action is `"fix"`, using `task["miss"]` set by this function
  (`levers.miss_line(project, checked kind, from, to, detail, now)`).
- `fred(task, lever, now)`: README 3.7 Fred rows for `stop`, `pause`, `resume`, `retry`, `confirm`: returns
  `(True, "", lines)` when the transition applies, else `(False, why, [])` with the reason (`"not stuck or stopped"`,
  `"already paused"`, `"nothing to confirm"`, ...). `stop` on a task that is already `done` / `stopped` is refused.
  It never touches a process: the service calls `runs.stop` before `fred(task, "stop")`.
- `folder(home, task_id) -> Path`: `Path(home) / "tasks" / task_id`. `save`: `task.json` through the temp file.
  `load`: `None` on a bad id, a missing file or bad JSON. `load_all`: `{id: task}` for every `tasks/*/task.json`
  that loads. `log`: appends the lines to `chain.jsonl`. `write_note`: writes `note_text` to `note_file`, sets
  `step["handoff"]`, returns the relative path. `read_note(home, task, n)`: the note text of step `n` or `""`.
  `prune(home, days, now)`: deletes task folders whose `task.json` mtime is older than `days` and whose state is
  `done`, `stopped` or `stuck`; returns the removed ids. `clear(home, task, keep_last)`: README 3.9; sets
  `task["cleared"] = True` and `step["handoff"] = ""` on the removed notes; returns the step session ids (every
  non-empty `session`), in order; with `keep_last=False` removes the folder with `shutil.rmtree` (the one extra
  import). Every file is UTF-8.
- `step_prompt(task, step, prev_note, retry_reason="")`: `step_prompt.md` (a `string.Template`) with:
  `$title` (the task title), `$goal` (prompt.md's text, clipped to 6000 characters), `$n`, `$m` (the step count),
  `$kind`, `$step_goal`, `$prev` (the previous note or `This is the first step: there is no handoff note yet.`),
  `$retry` (empty, or `Your earlier attempt at this step ended without a handoff: <reason>. Start again from the
  note above.`), `$special` (kind `verify`: `levers.VERIFY_TEXT`; kind `fix`: `levers.escalate_text(detail,
  model, effort)` where the detail comes from the verify step's `verdict_detail`; else empty). No STOP footer here:
  `runs.start` adds it.

## `console/step_prompt.md` (the text, final)

```text
You run one step of a task that Claude Console drives as a chain of separate runs. Earlier steps ran in other
sessions; their findings reach you only through the handoff note below. Later steps will see only your note.

Task: $title
$goal

Step $n of $m: $kind. $step_goal
$special
$retry
Handoff note of the previous step:
$prev

Rules for this step:
- Do only this step. Do not start the next one, and do not run /session-handoff.
- The Agent tool is not available here: read what you need yourself, as little as the step needs.
- Do not edit files unless the step is edit, code, debug, document, draft or fix.
- End your final message with this block, filled in, and nothing after it:

HANDOFF
## Findings
What you learned or did, in a few lines, with the file paths and line numbers that matter.
## Files touched
- path (what changed), or: - (none)
## Open questions
- a question the next step or Fred must settle, or: - (none)
## Next
One line for the next step. Add `Next model: <haiku|sonnet|opus>/<low|medium|high>` only when the next step
needs more than planned.
END HANDOFF
```

## Task 1b: `console/compact.py`, the brief pass (README 3.6b)

**Files**: create `console/compact.py`, `console/compact_prompt.md`; modify `console/claude_cli.py`
(`brief_command`), `tests/fake_claude.py` (the prompt's first line `Compact the handoff note` makes `prep()`
answer the brief schema: findings `["add() is in calc.py:2", "test_add covers it"]`, files `["calc.py"]`,
questions `[]`, next `"Fix add() and run the test"`; with `LONG` in the input, 80 findings lines, so the
check fails and the fallback is used); create `tests/test_compact.py`. `tasks.step_prompt` takes the brief text
as `prev_note` (no change of signature); `tasks.brief_file(task, step)`; `tasks.read_brief(home, task, n)`.

`console/compact_prompt.md` (final text):

```text
Compact the handoff note of a finished step into the brief the next step will read. The next step runs in a
fresh session and sees nothing else: keep what it needs, drop what it does not, carry forward from the earlier
brief what later steps still need. Do not add facts. Do not solve the next step.

Task: $title
Next step ($next_n of $m, $next_kind): $next_goal

Earlier brief (what the steps before already kept):
$prev

Raw handoff note of step $n ($kind):
$raw

Answer with the JSON object only: findings (at most 12 short lines, file paths and line numbers kept),
files (at most 20 paths with what changed), questions (at most 5, only what blocks the next step), next (one
line for the next step; keep a `Next model: m/e` note only if the raw note had one).
```

Tests (`tests/test_compact.py`): `test_render_and_check` (four headings in order, lists as `- ` lines, `(none)` for
empty lists, `over 400 words` on a long one), `test_fallback_keeps_files_and_cuts_findings`, `test_run_brief_uses_the_fake`
(brief text, cost 0.03, words under 400, `fallback == ""`), `test_run_brief_falls_back_on_a_bad_answer` (`LONG` ->
`fallback` says `over 400 words`; a `BROKEN` answer -> `fallback` names the JSON error; the text is the code
fallback), `test_brief_command_has_no_tools_and_one_turn` (in `tests/test_claude_cli.py`).

Steps: tests first (fail on the missing module and flag), then `brief_command`, `compact.py`, the prompt file,
the fake words, `tasks.brief_file` / `read_brief`; whole suite OK; commit
`feat: brief pass: the handoff compacted between steps (plan 17 Task 1b)`.
Done 2026-10-12 (223 tests OK). `clear(keep_last=True)` also keeps the last brief (design 4.12).

## Tests: `tests/test_tasks.py`

Two classes. Every test is written before the code it covers, run once to see it fail, then made to pass.

`RulesTest` (README section 5 of the design, one test per row and rule):
- `test_rule_scout_haiku_low`, `test_rule_search_haiku_low`, ... `test_rule_design_opus_high` (eleven tests, one per
  kind in `RULES` except verify and fix): `step_route(kind)` gives the row's model and effort, and `RULES[kind][2]` the row's tools.
- `test_verify_runs_one_model_up`: haiku/low -> sonnet/medium, sonnet/medium -> opus/medium, sonnet/high ->
  opus/high, opus/high -> opus/high, opus/low -> opus/medium.
- `test_fix_runs_on_the_escalated_route_once`: `step_route("fix", checked=("sonnet", "medium"))` is sonnet/high;
  with checked fable/max, fable/max (nothing above, kept); the once-per-task rule is asserted in `ChainTest`.
- `test_miss_floor_raises_a_step`: a `levers.miss_line("APP", "scout", "haiku/low", "haiku/medium", "x")` makes
  `step_route("scout", misses=[line])` haiku/medium; a miss of another kind changes nothing.
- `test_next_hint_raises_at_most_one_step`: `prev` with `Next model: opus/high` on a `code` step gives
  sonnet/high (one step), not opus; `Next model: haiku/low` on a `code` step changes nothing; junk is ignored.
- `test_step_after_opus_goes_back_to_its_rule`: `step_route("code", prev=<a design note without a hint>)` is
  sonnet/medium.
- `test_task_demand_raises_code_steps`: `demand={"reasoning": "high"}` gives code sonnet/high and debug
  sonnet/high, scout haiku/low (unchanged), design opus/high.
- `test_code_never_picks_fable`: `step_route("design", prev="Next model: fable/max")` is opus/high; with
  `pick="fable"` it is fable/high and the notes hold `pick: fable`.
- `test_opus_only_where_reasoning_is_needed`: for every kind but `design`, `step_route(kind)` is not opus;
  `step_route("verify", checked=("sonnet", "medium"))` is opus; `step_route("verify", checked=("haiku", "low"))` is
  sonnet.
- `test_budget_pressure_moves_a_step_down`: `budget={"opus": 0.84}` makes design sonnet/xhigh with a
  `budget:` note; `budget={"sonnet": 0.9}` makes code haiku/high; `verify` with checked sonnet/medium and
  `budget={"opus": 0.9}` keeps opus/medium and sets `hold`; haiku is never moved down; below `warn_at`
  nothing changes.
- `test_fixed_effort_runs_every_step_at_that_level`: `effort="max"` gives scout haiku/max, code sonnet/max,
  design opus/max, verify of sonnet/max -> opus/max; the notes hold `fixed effort: max`.
- `test_fixed_effort_is_clamped_to_the_model_cap`: with `EFFORT_CAP["haiku"]` patched to `high`, `effort="max"`
  gives haiku/high and a note `cap haiku: high`.
- `test_escalate_with_fixed_effort_moves_the_model`: `step_route("fix", checked=("sonnet", "max"),
  effort="max")` is opus/max.
- `test_kinds_table_matches_prompt`: every kind of `RULES` appears as a row in `console/prep_prompt.md` with the
  same model and effort (Task 3 adds the block; this test is written in Task 3, listed here for completeness).

`HandoffTest`:
- `test_parse_handoff_takes_the_last_block`: two blocks in one message -> the last one, markers removed, inner
  text kept as written; no block -> `None`; a block with text after `END HANDOFF` still parses.
- `test_check_handoff_reasons`: a good block -> `""`; a block without `## Next` -> `missing: ## Next`; headings
  swapped -> `headings out of order`; empty Findings -> `Findings is empty`.
- `test_next_hint`: `Next model: sonnet/high` -> `("sonnet", "high")`; `Next model: gpt/high` -> `None`.
- `test_note_file_and_text`: `steps/02-code.md`, the header line, the masked body (`sk-abcdefghijkl1234` becomes
  `***`); a 60 KB block is cut at `NOTE_MAX` and ends with `[cut at 20 KB]`.

`ChainTest` (pure, on dicts; `now` passed in, no clock):
- `test_plan_steps_validates_and_appends_verify`: `[{"kind": "scout", "goal": "a"}, {"kind": "code", "goal": "b"},
  {"kind": "bogus", "goal": "c"}, {"kind": "test"}]` -> scout, code, verify (3 steps, numbered 1..3); a list of
  `[search, explain]` gets no verify; a list already ending `code, verify` gets no second verify; `max_steps=1`
  cuts to `[scout]`; a `model: "fable"` on a step becomes `pick: "fable"`; `[]` -> `[]`.
- `test_new_task_shape`: every key of README 3.2 is present; `ValueError` on an empty list or `effort="turbo"`.
- `test_start_step_and_chain_lines`: after `start_step(task, 1, "s1", route, "abc", 10.0)`: step 1 running with
  model, effort, notes, session, started; task running, current 1; two chain lines (task and step).
- `test_good_handoff_moves_to_the_next_step`: `on_step_ended(..., ok=True, block_error="", verdict="", ...)` on
  step 1 of 3 -> `"next"`, step 1 done, `last_good` 1; on the last step -> `"done"`, task done.
- `test_question_waits_for_fred`: `question="which file?"` -> `"wait"`, task waiting,
  `why == "asks: which file?"`, the step still running.
- `test_bad_handoff_retries_once_then_stuck`: `block_error="no HANDOFF block"` -> `"retry"`, step planned,
  `retries` 1; a second time -> `"stuck"`, `why` ends with `(after one retry)`; `ok=False` with a good block is
  the same path.
- `test_verify_fail_inserts_fix_and_verify_once`: a task scout, code, verify; the verify ends `FAIL` -> `"fix"`,
  steps are now scout, code, verify, fix, verify (n 1..5), `escalated == "sonnet/medium -> sonnet/high"`,
  `task["miss"]` is a miss line of kind `code`; the fix's `checked` route is `("sonnet", "medium")` (kept in the
  step as `checked`); the second verify ending `FAIL` -> `"stuck"`, `why` starts with `verify failed twice`.
- `test_verify_pass_goes_on`: verify ends `PASS` with a good block -> `"next"` or `"done"`.
- `test_verify_without_verdict_is_a_bad_block`: verdict `""` on a verify -> `"retry"` with `why` `no VERDICT line`.
- `test_fred_levers`: `stop` on running -> stopped, owner fred; `pause` -> owner fred, state kept; `resume` ->
  owner service; `retry` on stuck -> the current step planned again, task running; `retry` on running ->
  refused; `confirm` on `why == "confirm Fable"` -> `fable_ok`, running; `confirm` otherwise refused.
- `test_files_round_trip`: `save`, `load`, `load_all`, `log` (two lines appended, valid JSON), `write_note`
  (file content equals `note_text`, step `handoff` set), `read_note`, a bad id gives `None`; `prune` removes a
  done task older than the cut-off and keeps a running one and a young one. Uses `tempfile.TemporaryDirectory()`.
- `test_clear_keeps_the_last_note`: a done task with three notes: `clear(keep_last=True)` leaves `task.json`,
  `chain.jsonl`, `prompt.md` and the last good note only, returns the three session ids, sets `cleared`;
  `clear(keep_last=False)` removes the folder; `load` then gives `None`.
- `test_step_prompt_text`: the prompt names the task, `Step 2 of 3: code`, holds the previous note verbatim, the
  HANDOFF block rule, no `/session-handoff` instruction to run it, and for a verify step starts the special line
  with `Check the work of this session.`; a retry carries the retry sentence; no `STOP:` footer inside.

## Steps

- [x] 1. Add the eight keys to `paths.DEFAULTS` (README section 4). Run the suite: 169 OK.
- [x] 2. Write `tests/test_tasks.py` with `RulesTest` and `HandoffTest` (every test above except
      `test_kinds_table_matches_prompt`). Run `py -m unittest tests.test_tasks`: every test errors on the missing
      module.
- [x] 3. Write `console/tasks.py` constants, `safe_id`, `verify_route`, `step_route`, the handoff functions. Run
      the two classes: all pass. Fix the code, not the tests, when one fails.
- [x] 4. Write `ChainTest`. Run: errors on the missing functions.
- [x] 5. Write `plan_steps`, `new_task`, `step`, `current_step`, `start_step`, `on_step_ended`, `fred`, the file
      functions, `step_prompt` and `console/step_prompt.md`. Run `ChainTest`: all pass.
- [x] 6. Run the whole suite: 169 + the new tests OK.
- [x] 7. Commit: `feat: tasks module: step rules, handoff check, chain transitions, task files (plan 17 Task 1)`.

## Drift guards

- `tasks.py` has no `import subprocess`, no `import threading`, no `from . import server`.
- `on_step_ended` and `fred` never read or write a file; `save` and `log` never decide anything.
- One insert only (fix + verify), guarded by `escalated`; `retries` never exceeds 1 by the module's own doing.
- `step_route` applies the eight rules in README 3.5 in that order; a new rule is a plan change, not a code change.
