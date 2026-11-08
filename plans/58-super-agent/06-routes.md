# Task 6: GET /api/super and POST /api/super

> Contract: [README.md](README.md) 3.9, 3.10; decision D6. The GET is the data contract slice 2's window reads: it
> may grow fields later, never lose these. It starts nothing and writes nothing.

**Files**
- Modify: `console/server.py` (`Hub.super_view`, `Hub.super_action`, one GET line, one POST route, one handler;
  other chats edit this file: stage only this task's hunks, README rules)
- Modify: `tests/test_superagent_server.py` (`SuperRouteTest`)

Commit boundary: `feat: GET and POST /api/super (plan 58 T6)`.

## 6.1 `console/server.py`

This recipe replaces the old source block. Required:
[review R2-R5 and R7-R9](08-review-and-jev.md#1-required-corrections).

**Hub.super_view (GET, pure projection).**

- Read settings and snapshot under the existing lock order; copy current super state/busy/wake. Describe all
  live items, not only the last 30 submitted, and filter advice against current basis/policy without mutating
  Hub state or disk. Do not wait for a tick to remove a resolved question or changed answer contract.
- Load and validate the super ledger once. Use that same result for totals, status and today's run count.
  A read/validation error makes state unranked, names the error and returns `spend.today: null` plus
  `spend.error`; it must not display zero. Storage/input errors and the latest refusal are also visible.
- Queue from the filtered projection. Expiry and always rules apply even when a pass is running or GET arrives
  before the next tick. Mask/cut notes and display metadata. Preserve opaque IDs; no raw prompt, token or
  external credential may appear in the API.
- Keep README 3.9 fields. Add `coverage: {live, last_submitted, never_reviewed}`, derived from the live
  set, last handles count and reviewed map. Report `due` using the monotonic clock; `since` stays wall time.
  A missing seen entry is new whenever ranked, including equal timestamps.
- If files/brief evidence are read outside tlock, bound that work and compare the copied basis again before
  returning. Changed evidence is unknown/stale, never a reason to show an old recommendation.
- Do not call sync on live state, save/log, arm wakes, start a thread or invoke a provider from GET.

**Hub.super_action (POST).**

- Accept exactly `{action: pause|resume|sort}`, otherwise 400. Keep 409 for Sort while paused.
- Pause/resume build a candidate state under tlock and persist it before acknowledging; log the action with
  the existing redaction rules. If either required write fails, return 503 with a masked error and retain a
  local admission block until reconciliation succeeds. A durable Pause stays paused even if its log write fails.
- Pause drops pending work only after its saved state takes effect. A launched pass may finish and settle;
  its advice remains invisible while paused. A claimed but not invoked pass rechecks Pause and settles zero.
- Resume, once durably saved/logged, arms one immediate wake. Sort durably logs acceptance, then arms its
  in-memory wake. Duplicate clicks coalesce, never start parallel passes.
- Notify changed only for visible changes. Return 200 with super_view only after required persistence succeeds.
  No action may bypass input, executable, storage or accounting gates.

**HTTP wiring.** Add the GET branch beside /api/usage, the POST route beside /api/task/supervisor/replay and
the small handler below. Existing Host/loopback/X-CC guards apply unchanged.

```python
# Handler.do_GET:
if url.path == "/api/super":
    return self._json(self.hub.super_view())

# Handler.do_POST routes:
routes["/api/super"] = self._super

# Handler method:
def _super(self, body):
    status, data = self.hub.super_action(body)
    return self._json(data, status)
```

## 6.2 Tests first (red before the code)

Add regression cases for unreadable/malformed ledger (null spend plus error), failed Pause save (503, no paid
start, no false durable acknowledgement), changed decision before a tick, hand-edited secret notes, coverage for
65 items and new item at an equal clock. Mock every write/model entry point in the GET purity check.

`SuperRouteTest(test_server.RunServerTest)` in `tests/test_superagent_server.py` (`from tests import
test_server`): the real fake claude, the hub loop not started; `setUp` calls `super().setUp()` and sets
`self.hub.cfg["super_debounce_s"] = 0`, so one `self.hub._super_tick()` arms and admits a pass at once; a `pass_()`
helper ticks, asserts True and joins `self.hub.super_threads` (30 s). Tasks come from Task 5's module function
`make_task(self.hub, self.project, n, ...)`. The class keeps `RunServerTest`'s `supervisor_mode` `off`, so every level
reads `off`.

- `test_get_super_ranks_after_a_fake_pass`: task 1 waiting `plan ready: confirm`, task 2 waiting `confirm Fable`.
  GET `/api/super` before any tick: 200, `state` `unranked`, `why` `no pass yet`, `paused` False, `sorting` None,
  `due` None, the queue cards `[task 2], [task 1]` (always first), task 2's item `always` `"Fable confirm"`, `ask`
  `"held · confirm Fable"`, `level` `off`, `kind` `hold`, `new` False, `say` `""`; task 1's `ask` `"plan ready ·
  confirm"`; `digest` `[]`; `last` None; `counts` `{"queue": 2, "later": 0, "always": 1, "new": 0}`. Then `pass_()`
  and GET: `state` `ranked`, `why` `""`; cards `[task 2], [task 1]`; task 1's `say` `"fake: I2"` and `rank` 1, task
  2's `say` `"fake: I1"` and `do` `forward`; `digest` `["fake digest: 2 items"]`; `notes` starts `"fake notes\n# Super
  agent pass 1 · "`; `last` has `n` 1, `ok` True, `model` `haiku`, `cost` 0.003, `items` 2; `spend` `{"today": 0.003,
  "passes": 1, "day_limit": 1.0, "pass_limit": 0.2}`; `last-prompt.md` exists and the claimed line's `prompt_hash` is
  its SHA-256. Task 3 added, GET without a tick: its card comes last with `new` True and `counts["new"]` 1.
- `test_super_error_leaves_the_queue_unranked_and_keeps_the_cost`: `super/orders.md` holds `SUPER-ERROR`; task 1
  waiting; `pass_()`; GET: `state` `unranked`, `why` `"the pass failed: error_max_turns"`, every `say` `""`, `last`
  `ok` False with `cost` 0.02; GET `/api/usage` `super.today` has `cost` 0.02 and `runs` 1. With `SUPER-BAD` instead
  (a fresh folder): `why` `"the pass gave no answer (items is missing or not a list)"`.
- `test_super_later_and_unknown_handles`: orders `SUPER-LATER SUPER-UNKNOWN`, tasks 1 and 2: after `pass_()`, the
  item that was `I1` sits in `later` with `why` `"fake: it can wait"` and a non-empty `until`; `counts["later"]` 1;
  the result line's `dropped` is `[{"at": 2, "why": "unknown handle I99"}]`.
- `test_post_super_pause_resume_and_sort`: a POST without `X-CC` is 403; `{"action": "nap"}`, `{}` and `{"action":
  "sort", "x": 1}` are 400 `{"error": "action: pause, resume or sort"}`. `pause`: 200, `paused` True, `state`
  `unranked`, `why` `paused`; the last `super.jsonl` line has `phase` `pause` and `by` `fred`; `state.json` has
  `paused` true. `sort` while paused: 409 `{"error": "paused: resume first"}`. `resume`: 200, `paused` False, `due` 0.
  With task 1 waiting, `pass_()` runs one pass whose prompt (`last-prompt.md`) holds `"Triggers: 1 new item, asked"`.
  Then `sort`: 200 and `due` 0; the next `pass_()` has `"Triggers: asked"`.
- `test_get_super_starts_nothing_and_writes_nothing`: tasks 1 and 2 waiting, no tick; with `paths.write_text_atomic`
  and `superagent.append_log` patched to fail the test, three GETs of `/api/super` answer 200; `hub.super_threads` is
  `[]`, `hub.super_wake` None; no `super/` folder and no `super` section in usage-days.json exist.
- `test_usage_report_has_the_super_agent`: GET `/api/usage` before any pass has `super` `{"days": {}, "today":
  {"cost": 0.0, "runs": 0, "unknown": 0, "reserved": 0.0}, "day_limit": 1.0, "pass_limit": 0.2, "error": ""}`; after
  one `pass_()`, `super.today` has `runs` 1 and `cost` 0.003, and the `supervisor` block is unchanged (no runs).

## 6.3 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_superagent_server`: red for the missing route and methods.
- [ ] 2. Make the 6.1 edits. Focused tests green; `tests/test_server.py` green (`RunServerTest` unchanged).
- [ ] 3. Full suite green (report the count). Stage the test file by path and only this task's hunks of
      `console/server.py` (non-interactive staging, README rules). Commit with the message above.
