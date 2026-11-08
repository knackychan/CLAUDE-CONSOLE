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

`load_supervisor` and `record_supervisor` take the section by keyword; the default keeps every message as it is:

```python
def load_supervisor(folder, *, section: str = "supervisor") -> dict:
    """The supervisor ledger (or plan 58's `super` section) from usage-days.json as {pass_id: record}. A missing
    section is valid empty; an unreadable or malformed section is an explicit error, never a free empty allowance."""
    data = _read(folder)
    if data is None:
        return {"error": "usage-days.json is unreadable", "records": {}}
    sup = data.get(section)
    if sup is None:
        return {"error": "", "records": {}}
    if not isinstance(sup, dict):
        return {"error": f"usage-days.json {section} is not an object", "records": {}}
    return {"error": "", "records": sup}
```

In `record_supervisor(folder, pass_id: str, result: dict, *, section: str = "supervisor")`: `sup =
data.get(section, {})`, the not-an-object error reads `f"usage-days.json {section} is not an object"`, and the write
is `data[section] = sup`. Nothing else in it changes.

After `supervisor_spent`:

```python
# -- plan 58: the super agent's own passes, in a section of their own ------------------------------------------
# Apart from the supervisor's section: neither role spends the other's allowance. A uuid4 pass id is the identity.

def load_super(folder) -> dict:
    return load_supervisor(folder, section="super")


def reserve_super(folder, pass_id: str, day: str, pass_limit: float, day_limit: float) -> dict:
    """Atomically reserve one super agent pass: the lesser of `pass_limit` and what `day` has left (settled plus
    held). A remainder that rounds to nothing is a cap (a zero max_cost would mean no budget flag); a duplicate pass
    id, a cap or an unreadable ledger refuses admission. Never calls a model."""
    with FILE_LOCK:
        data = _read(folder)
        if data is None:
            _set_aside(folder)
            return {"status": "error", "error": "usage-days.json is unreadable"}
        sec = data.get("super", {})
        if not isinstance(sec, dict):
            return {"status": "error", "error": "usage-days.json super is not an object"}
        if pass_id in sec:
            return {"status": "duplicate", "error": "pass already reserved", "record": sec[pass_id]}
        settled, active = _supervisor_used(sec, day=day)
        remaining = round(min(pass_limit, day_limit - settled - active), 6)
        if remaining <= 0:
            return {"status": "cap", "error": "super agent day limit reached", "reserved": 0.0}
        sec[pass_id] = {"day": day, "kind": "super", "reserved": remaining, "cost": 0.0, "status": "reserved"}
        data["super"] = sec
        try:
            _write(folder, data)
        except OSError as exc:
            return {"status": "error", "error": f"cannot write usage-days.json: {exc}"}
        return {"status": "reserved", "reserved": remaining, "day": day}


def record_super(folder, pass_id: str, result: dict) -> dict:
    """Settle one super agent pass (record_supervisor's rules: once, an unknown cost keeps its reservation)."""
    return record_supervisor(folder, pass_id, result, section="super")


def super_spent(folder, day: str) -> tuple:
    """(settled cost, held reservations) of one day's super agent passes; (0.0, 0.0) for an unreadable ledger (the
    next reservation refuses then)."""
    return _supervisor_used(load_super(folder)["records"], day=day)
```

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
  `super_spent(folder, DAY)` counts the reservation; a known cost settles in full, even above the reservation (0.3 on
  a 0.2 reservation is 0.3); settling twice with the same cost is `settled`, with another cost `conflict`.
- `test_cap_and_a_tiny_remainder`: day limit 0.008 with 0.008 settled gives `{"status": "cap", "error": "super agent
  day limit reached", "reserved": 0.0}`; day limit 0.0080004 with 0.008 settled (a remainder of 0.0000004, which
  rounds to nothing) is a cap too (settled costs are rounded to a millionth, so the remainder comes from the limit);
  a duplicate pass id gives `duplicate`.
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
