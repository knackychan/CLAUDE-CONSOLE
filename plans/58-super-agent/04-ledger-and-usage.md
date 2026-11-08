# Task 4: the `super` ledger section, GET /api/usage `super` and the Usage block

> Contract: [README.md](README.md) 3.11 (ledger), 3.13; decision D7.
> Reuses plan 44's ledger (`usage.py:398-500`) with a `section` keyword, and plan 50's Usage block
> (`usageSupervisor`, `web/app.js:2314`) with a `key` argument. With the defaults, every existing string and
> behaviour is unchanged.

**Files**
- Modify: `console/usage.py` (`load_supervisor` and `record_supervisor` gain `section`; new `load_super`,
  `reserve_super`, `record_super`, `super_spent`)
- Modify: `console/server.py` (`Hub.usage_report`: the `super` block; other chats edit this file, README rules)
- Modify: `web/app.js` (`PASSES_WORDS`, `usageSupervisor(data, key)`, the Usage page call, the footer sentence)
- Modify: `tests/test_usage.py` (`SuperLedgerTest`), `tests/test_web.py` (`SupervisorSettingsTest`)

Commit boundary: `feat: super agent spend ledger and Usage block (plan 58 T4)`.

## 4.1 `console/usage.py`

Required review: [R4/R5 persistence and accounting](08-review-and-jev.md#r4r5-persistence-and-accounting-order).
Keep the existing FILE_LOCK and whole-file atomic writer. Reuse existing section mechanics, but not permissive
record validation that could make a corrupt ledger look like free allowance.

Implement these small interfaces; no new ledger file:

- `load_supervisor(folder, *, section="supervisor")` and
  `record_supervisor(folder, pass_id, result, *, section="supervisor")`: parameterize only the section lookup,
  error label and assignment. Keep default callers' behavior. Grep all callers before changing either signature.
- `load_super(folder)`: return `{error, records}` from section super. An absent section is empty; unreadable JSON,
  a nonobject section or **any invalid record** is an explicit error. Validate each record against review R5 before
  returning totals. Do not silently skip malformed rows or filter them out of the budget.
- `reserve_super(folder, pass_id, day, pass_limit, day_limit)`: under FILE_LOCK, read and validate the full super
  section, refuse duplicates/errors, compute settled + reserved/unknown for the admission day, and atomically
  reserve the lesser of the pass limit and day remainder. Round money to six decimals; a remainder rounding to
  zero is a cap, never a model invocation without a budget. Validate finite positive limits at this boundary too.
  Preserve every other file section. Return reserved/reserved_amount/day or a specific refusal.
- `record_super(folder, pass_id, result)`: validate the existing record, then use section-aware settlement.
  A reported finite nonnegative number is known; bool, negative, NaN, infinity or missing is unknown.
  Preserve the reservation for unknown cost. Known costs settle in full, including above the reservation.
  Identical repeated settlement is harmless; conflicting settlement refuses. Never overwrite settled with unknown.
- `super_spent(records, day)`: pure totals from an already-validated records mapping. Callers must check
  load_super's error before calling it. GET loads once and derives its complete spend view from that result;
  an error never becomes (0, 0). No folder-based overload.

New records remain `{day, kind: "super", reserved, cost, status}`, keyed by UUID. Reservations/unknown have cost 0
and positive reserved; settled has a finite nonnegative cost and retains the recorded admission day. R4 defines how
the Hub reconciles these records with claims/results after interruption. A ledger write failure stays an error
and keeps the last durable reservation; do not launch new work until reconciliation succeeds.

## 4.2 `console/server.py`, `Hub.usage_report`

After `spend = supervisor.spend_view(ledger["records"])`:

```python
        super_ledger = usage.load_super(self.folder)  # plan 58: the super agent's passes, apart from the supervisor's
        super_days = supervisor.spend_view(super_ledger["records"])["days"]
```

and the returned dict gains, after the `supervisor` entry:

```python
                "super": {"days": super_days,
                          "today": super_days.get(today, {"cost": 0.0, "runs": 0, "unknown": 0, "reserved": 0.0}),
                          "day_limit": self.cfg.get("super_day_usd", 0), "pass_limit": self.cfg.get("super_pass_usd", 0),
                          "error": super_ledger["error"]}}
```

## 4.3 `web/app.js`

Replace the head of `usageSupervisor` and its three worded strings:

```js
// plan 58 (D7): the super agent's passes draw in a block of their own, through the same function
const PASSES_WORDS = { supervisor: ["Supervisor passes", "supervisor"], super: ["Super agent passes", "super agent"] };
function usageSupervisor(data = usage, key = "supervisor") {
  const sv = data[key], [title, who] = PASSES_WORDS[key];
```

- the error line: `` `<p class="note r">The ${who} ledger could not be read: ${esc(sv.error)}</p>` ``
- the label: `` <span class="lbl">${title}</span> ``
- the cells' title: `` title="cells of $0.50 up to the ${who}'s day limit" ``

Every other line of the function stays. The Usage page call (`app.js:2753`) becomes `usageSupervisor() +
usageSupervisor(usage, "super")`, and the footer sentence (`:2755`) reads `Supervisor and super agent passes are
counted from usage-days.json, apart from the transcripts.`

## 4.4 Tests first (red before the code)

`tests/test_usage.py`, `SuperLedgerTest` (scratch folder; `DAY = "2027-01-15"`):
- `test_reserve_is_the_lesser_of_pass_and_day_left`: limits 0.2 and 1.0 reserve 0.2; with 0.95 settled that day
  (one record settled through `record_super`), the next reserves 0.05; the record is `{"day": DAY, "kind": "super",
  "reserved": 0.05, "cost": 0.0, "status": "reserved"}`; a reservation on another day ignores this day's spend.
- `test_unknown_cost_keeps_its_reservation`: `record_super(pid, {"cost": None})` gives status `unknown` and
  `super_spent(load_super(folder)["records"], DAY)` counts the reservation; a known cost settles in full, even above the reservation (0.3 on
  a 0.2 reservation is 0.3); settling twice with the same cost is `settled`, with another cost `conflict`.
- `test_cap_and_a_tiny_remainder`: day limit 0.008 with 0.008 settled gives `{"status": "cap", "error": "super agent
  day limit reached", "reserved": 0.0}`; day limit 0.0080004 with 0.008 settled (a remainder of 0.0000004, which
  rounds to nothing) is a cap too (settled costs are rounded to a millionth, so the remainder comes from the limit);
  a duplicate pass id gives `duplicate`.
- `test_invalid_records_and_costs_fail_closed`: nonobject record, invalid day/status, negative/bool/NaN/infinite
  amounts refuse admission and surface an error in load_super. Invalid reported cost retains unknown spend.
  Failure to write settlement leaves the reservation; already-settled records cannot be reset to unknown.
- `test_midnight_and_concurrent_sections`: a pass finishing after midnight settles on its admission day;
  concurrent supervisor/super saves preserve both sections under FILE_LOCK.
- `test_sections_are_apart`: a supervisor reservation (`reserve_supervisor`) and a super reservation in one file:
  `load_supervisor(folder)["records"]` holds only the first, `load_super(folder)["records"]` only the second; a
  super spend of 0.9 leaves the supervisor's day allowance whole.
- `test_unreadable_and_malformed_ledgers`: a usage-days.json of `{` makes `reserve_super` an error (`usage-days.json is
  unreadable`) and is set aside like the supervisor's; `{"super": []}` gives `usage-days.json super is not an object`
  from `reserve_super`, `record_super` and `load_super`; `load_supervisor` on `{"supervisor": []}` still reads
  `usage-days.json supervisor is not an object` (the default unchanged).
- `test_save_days_keeps_the_super_section`: after a reservation, `save_days` with a closed day keeps `data["super"]`.

`tests/test_web.py`, in `SupervisorSettingsTest` beside `test_usage_shows_supervisor_spend` (which stays unchanged):

```python
    def test_usage_shows_super_agent_spend(self):  # plan 58 (D7): its own block, through the same function
        days = {"2026-10-20": {"cost": 0.03, "runs": 9, "unknown": 0, "reserved": 0.2}}
        data = {"today": "2026-10-20",
                "supervisor": {"days": {}, "today": {}, "task_limit": 0.5, "day_limit": 2, "error": ""},
                "super": {"days": days, "today": days["2026-10-20"], "day_limit": 1, "pass_limit": 0.2, "error": ""}}
        html = render(f"uMonth = '2026-10'; usageSupervisor({json.dumps(data)}, 'super')")
        self.assertIn("Super agent passes", html)
        self.assertIn("of $1.00 a day", html)
        self.assertIn("9 passes", html)
        self.assertIn("up to the super agent's day limit", html)
        self.assertNotIn("Supervisor passes", html)
        self.assertEqual(render(f"uMonth = '2026-10'; usageSupervisor({json.dumps(data)})"), "")  # nothing spent there
        bad = dict(data, super=dict(data["super"], error="usage-days.json super is not an object"))
        self.assertIn("The super agent ledger could not be read: usage-days.json super is not an object",
                      render(f"uMonth = '2026-10'; usageSupervisor({json.dumps(bad)}, 'super')"))
        self.assertEqual(render(f"uMonth = '2026-10'; usageSupervisor({json.dumps({'today': '2026-10-20'})}, 'super')"), "")
        self.assertIn('usageSupervisor() + usageSupervisor(usage, "super")', APP.read_text(encoding="utf-8"))
```

`tests/test_server.py`: the existing `usage_report` tests keep passing; Task 6 asserts the `super` block over HTTP.

## 4.5 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_usage tests.test_web`: red for the missing functions and
      the missing block.
- [ ] 2. Make the 4.1 to 4.3 edits. `node --check web/app.js`. Focused tests green, plan 44's ledger tests
      (`tests/test_supervisor.py`, `tests/test_supervisor_server.py`) unchanged and green.
- [ ] 3. Full suite green (report the count). Stage `console/usage.py` and the tests by path, and only this task's
      hunks of `console/server.py` and `web/app.js` (non-interactive staging, README rules). Commit with the message
      above.
