# Task 2: Pins in the route

> Contract: [README.md](README.md) 3.2, 3.5. Depends on nothing (plan 18 placed). Run in a scratch copy on
> 2026-10-14: `tests/test_tasks.py` 80 OK (plan 18's 74 + 6).
> Lands on: plan 18 Task 2 (`tasks.step_route`: one keyword and four small edits on its final code; nothing else in
> it moves).

**Files**
- Modify: `console/tasks.py` (`step_route`: signature, docstring tail, the pin read, the pin before the pick, the
  pick note, the fixed-effort note)
- Modify: `console/paths.py` (`DEFAULTS["kinds"]`)
- Modify: `tests/test_tasks.py` (class `PinRouteTest` at the end, before `if __name__`)

## 2.1 `console/tasks.py`, `step_route`

Signature: the last line gains `pin=None`:

```python
               prev_age=None, hard: bool = False, refuse=None, now: float = None, pin=None) -> dict:
```

Docstring: its last line (plan 18's ``    alias (plan 17's behaviour). `hold` non-empty means the task waits for
Fred."""``) becomes these three lines:

```python
    alias (plan 17's behaviour). `hold` non-empty means the task waits for Fred. `pin` is config `kinds[kind]`
    (plan 26): a pinned rung acts as a pick when the step has none, a pinned effort as the task's fixed effort
    when the task has none; verify and fix are never pinned."""
```

Replace the two lines `efforts = claude_cli.EFFORTS` and `fixed = effort != "auto"` with:

```python
    efforts = claude_cli.EFFORTS
    pin = pin if isinstance(pin, dict) and kind not in ("verify", "fix") else {}
    pin_rung = pin.get("rung") if cfg is not None and pin.get("rung") not in (None, "", "auto") else ""
    pinned = effort == "auto" and pin.get("effort") in efforts
    if pinned:
        effort = pin["effort"]
    fixed = effort != "auto"
```

After `notes.append(f"rule {kind}: {model}/{level}")`, before `picked = ...`:

```python
    from_pin = False
    if pin_rung and not pick:  # plan 26: the kind's pinned rung, unless it cannot run now (then auto)
        why = (refuse(pin_rung) if refuse else "") or ("" if fills.rank_of(pin_rung, cfg) else "unknown model")
        if why:
            notes.append(f"pin {kind}: {pin_rung} refused: {why} -> auto")
        else:
            pick, from_pin = pin_rung, True
            notes.append(f"pin {kind}: {pin_rung}")
```

In the `if picked:` block, the `pick:` note and the refusal line become:

```python
        if not from_pin:  # a pin wrote its own note above
            notes.append(f"pick: {pick if cfg is not None else picked}")
        why = refuse(pick) if refuse and cfg is not None and not from_pin else ""
```

Step 8's note:

```python
    if fixed:
        level = effort
        notes.append(f"pin effort: {effort}" if pinned else f"fixed effort: {effort}")
```

## 2.2 `console/paths.py`

In `DEFAULTS`, before `"allowances"` (plan 18):

```python
    "kinds": {},  # plan 26: kind -> {"rung": "auto" | rung, "effort": "auto" | effort}; absent keeps the code's rule
```

## 2.3 Tests (`tests/test_tasks.py`, class `PinRouteTest`)

Uses plan 18's `BALANCE_CFG` and `shares`.

```python
class PinRouteTest(unittest.TestCase):
    """Plan 26: config `kinds` pins a kind's rung and effort; a step's pick and the task's fixed effort come first."""

    def route(self, kind, **kw):
        return tasks.step_route(kind, cfg=BALANCE_CFG, warn_at=0.8, **kw)

    def test_a_pinned_rung_runs_as_a_pick(self):
        route = self.route("code", pin={"rung": "codex:gpt-6.1-sol", "effort": "auto"},
                           budget=shares({"gpt-6.1-sol": 0.95, "sonnet": 0.1}))
        self.assertEqual((route["model"], route["rung"]), ("sonnet", "codex:gpt-6.1-sol"))  # never balanced
        self.assertIn("pin code: codex:gpt-6.1-sol", route["notes"])
        self.assertFalse(any(n.startswith("pick:") or n.startswith("balance") for n in route["notes"]))

    def test_a_pinned_rung_that_cannot_run_routes_as_auto(self):
        refuse = lambda rung: "codex is off" if rung.startswith("codex:") else ""
        route = self.route("code", pin={"rung": "codex:gpt-6.1-sol"}, refuse=refuse)
        self.assertEqual(route["rung"], "sonnet")
        self.assertIn("pin code: codex:gpt-6.1-sol refused: codex is off -> auto", route["notes"])
        route = self.route("code", pin={"rung": "codex:gone"})
        self.assertIn("pin code: codex:gone refused: unknown model -> auto", route["notes"])

    def test_the_step_pick_beats_the_pin(self):
        route = self.route("code", pick="opus", pin={"rung": "codex:gpt-6.1-sol"})
        self.assertEqual(route["rung"], "opus")
        self.assertIn("pick: opus", route["notes"])
        self.assertFalse(any(n.startswith("pin ") for n in route["notes"]))

    def test_a_pinned_effort_is_fixed_and_capped(self):
        route = self.route("scout", pin={"rung": "auto", "effort": "high"}, demand={"reasoning": "high"})
        self.assertEqual((route["rung"], route["effort"]), ("haiku", "high"))
        self.assertIn("pin effort: high", route["notes"])
        route = self.route("scout", pin={"effort": "max"})  # haiku's cap still applies
        self.assertEqual(route["effort"], tasks.EFFORT_CAP.get("haiku", "max"))
        route = self.route("scout", pin={"effort": "high"}, effort="low")  # the task's fixed effort comes first
        self.assertEqual(route["effort"], "low")
        self.assertIn("fixed effort: low", route["notes"])

    def test_verify_and_fix_are_never_pinned(self):
        for kind, checked in (("verify", ("sonnet", "medium")), ("fix", ("sonnet", "medium"))):
            route = self.route(kind, checked=checked, pin={"rung": "haiku", "effort": "low"})
            self.assertFalse(any(n.startswith("pin") for n in route["notes"]), kind)

    def test_without_cfg_a_pinned_rung_is_ignored(self):
        route = tasks.step_route("code", pin={"rung": "codex:gpt-6.1-sol", "effort": "high"})
        self.assertEqual((route["rung"], route["effort"]), ("sonnet", "high"))
```

## 2.4 Steps

1. Add `PinRouteTest`; run `py -m unittest tests.test_tasks`: TypeError, unexpected keyword `pin`.
2. The `tasks.py` and `paths.py` edits; run: every test OK (plan 18's tests unchanged: `pin` defaults to `None`).
3. The whole suite: the count + 6.
4. Commit: `plan 26 task 2: a kind's pinned rung and effort in the route (N tests OK)`.

## 2.5 Drift guards

- A pin never reaches verify or fix; a step's pick and the task's fixed effort come first.
- A refused pin routes as auto (the balance), never as the pin's rank (a refused pick balances at its rank; README
  3.5 says why the two differ: interface 9b).
- `step_route` stays pure; `pin` comes in as an argument.
