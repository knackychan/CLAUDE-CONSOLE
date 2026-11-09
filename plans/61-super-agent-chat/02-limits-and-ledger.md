# Task 2: the limits and the chat ledger

> Contract: [README.md](README.md) 3.2. The six keys are written only through `POST /api/config/models`
> (`tuning.TUNING`), never by the chat or the passes.

**Files**
- Modify: `console/paths.py` (`DEFAULTS`), `console/tuning.py` (`TUNING`, `CHAT_MODELS`, the rung check)
- Create: `console/superchat.py` (part 0: `settings`, `off`)
- Modify: `console/usage.py` (the `super` ledger functions take a `kind`)
- Modify: `console/server.py` (`Hub.chat_spend`, `usage_report["chat"]`; stage only this task's hunks)
- Modify: `web/app.js` (`PASSES_WORDS`, `usageSupervisor`, the Usage page line)
- Modify: `tests/test_tuning.py` (the whitelist set); Create: `tests/test_superchat.py`

Commit boundary: `feat: chat and background act limits, the chat ledger (plan 61 T2)`.

## 2.1 Settings

`console/paths.py`, in `DEFAULTS` after `"super_day_usd": 1.0,`:

```python
    "chat_model": "sonnet",  # plan 61: the super agent's chat (README 3.2)
    "chat_turn_usd": 0.50,
    "chat_day_usd": 3.0,
    "chat_timeout_s": 600,
    "super_acts_day": 20,  # plan 61: the passes' background acts
    "super_acts_task_hour": 2,
```

`console/tuning.py`, in `TUNING` after `"super_judge_model": ("super", "rung", None, None),`:

```python
    # plan 61: the chat and the background acts (no Models page card, as plan 58 D9)
    "chat_model": ("super", "rung", None, None),
    "chat_turn_usd": ("super", "usd", 0.05, 2),
    "chat_day_usd": ("super", "usd", 0, 20),
    "chat_timeout_s": ("super", "s", 60, 1800),
    "super_acts_day": ("super", "steps", 0, 100),
    "super_acts_task_hour": ("super", "steps", 0, 6),
```

After the `SUPERVISOR_MODELS = {...}` line:

```python
CHAT_MODELS = ("haiku", "sonnet", "opus")  # plan 61: the chat's model, a Claude alias, never fable
```

In `validate`, the rung branch becomes:

```python
            elif unit == "rung":
                if key in SUPERVISOR_MODELS:  # plan 44: the supervisor pass is fixed to one Claude alias
                    why = "" if value == SUPERVISOR_MODELS[key] else f"{SUPERVISOR_MODELS[key]} only"
                elif key == "chat_model":  # plan 61
                    why = "" if value in CHAT_MODELS else "haiku, sonnet or opus"
                else:
```

(the lines after `else:` unchanged).

`console/superchat.py`, part 0:

```python
"""Plan 61: the super agent's chat (README 3.5). Part 0 (Task 2): its settings. Part 1 (Task 3): the thread file.
Part 2 (Task 4): the turn: the prompt, the command and the stream reader. The Hub owns the lock and the process."""
import math

MODELS = ("haiku", "sonnet", "opus")
_USD = {"chat_turn_usd": (0.05, 2), "chat_day_usd": (0, 20)}
_INT = {"chat_timeout_s": (60, 1800)}


def settings(cfg: dict) -> tuple:
    """(limits, errors), checked like superagent.settings: a wrong value takes the floor and adds its error; any
    error keeps the chat off."""
    out, errors = {}, []
    model = cfg.get("chat_model")
    if model not in MODELS:
        errors.append("chat_model must be haiku, sonnet or opus")
        model = "sonnet"
    out["chat_model"] = model
    for key, (low, high) in _USD.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not low <= value <= high:
            errors.append(f"{key} must be a number between {low} and {high}")
            value = 0.0
        out[key] = float(value)
    for key, (low, high) in _INT.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            errors.append(f"{key} must be a whole number between {low} and {high}")
            value = low
        out[key] = value
    return out, errors


def off(limits: dict, errors: list, spent: float, ledger_error: str = "") -> str:
    """Why the chat cannot take a message now; "" when it can. The cards are never affected."""
    if errors:
        return "chat settings: " + errors[0]
    if ledger_error:
        return "chat ledger: " + ledger_error
    if limits["chat_day_usd"] == 0:
        return "chat is off (chat_day_usd is 0)"
    if spent >= limits["chat_day_usd"]:
        return f"chat off for today: ${spent:.2f} of ${limits['chat_day_usd']:.2f}"
    return ""
```

## 2.2 The ledger (`console/usage.py`)

The `super` functions take the section as `kind` (`"super"` by default, so every plan 58 call and message stays):

```python
SUPER_KINDS = {"super": "super agent", "chat": "chat"}  # plan 61: sections with the super rules


def _super_error(records, kind="super"):
    if not isinstance(records, dict):
        return f"usage-days.json {kind} is not an object"
    ...                                     # the loop unchanged, except:
            valid = (rec.get("kind") == kind and rec.get("status") in ("reserved", "unknown", "settled")
                     and _super_money(rec.get("cost")) and _super_money(rec.get("reserved")))
    ...
        if not valid:
            return f"usage-days.json {kind} has an invalid record"
    return ""


def load_super(folder, kind="super") -> dict:
    ...                                     # unchanged, except:
        records = data.get(kind, {})
        error = _super_error(records, kind)


def reserve_super(folder, pass_id: str, day: str, pass_limit: float, day_limit: float, kind="super") -> dict:
    ...                                     # unchanged, except:
        records = data.get(kind, {})
        error = _super_error(records, kind)
        ...
        if amount <= 0:
            return {"status": "cap", "error": f"{SUPER_KINDS[kind]} day limit reached", "reserved": 0.0}
        records[pass_id] = {"day": day, "kind": kind, "reserved": amount, "cost": 0.0, "status": "reserved"}
        data[kind] = records


def record_super(folder, pass_id: str, result: dict, kind="super") -> dict:
    return record_supervisor(folder, pass_id, result, section=kind)
```

In `record_supervisor`, each `section == "super"` and `section != "super"` becomes `section in SUPER_KINDS` and
`section not in SUPER_KINDS`, and `error = _super_error(sup)` becomes `error = _super_error(sup, section)`.

## 2.3 The Hub and the Usage page

`console/server.py`: add `superchat` to the `from . import ...` line. A Hub method after `recent_acts` (Task 1):

```python
    def chat_spend(self):
        """Today's chat spend from its ledger section (README 3.2): settled plus held, and the turns."""
        limits_, errors = superchat.settings(self.cfg)
        ledger, day = usage.load_super(self.folder, "chat"), usage.day_of(time.time())
        settled, held = usage.super_spent(ledger["records"], day)
        spent = round(settled + held, 6)
        return {"today": None if ledger["error"] else spent,
                "turns": sum(1 for r in ledger["records"].values() if r.get("day") == day),
                "day_limit": limits_["chat_day_usd"], "turn_limit": limits_["chat_turn_usd"], "error": ledger["error"],
                "off": superchat.off(limits_, errors, spent, ledger["error"])}
```

In `usage_report`, after the `"super": {...}` entry of the returned dict (its last line is `"pass_limit":
self.cfg.get("super_pass_usd", 0), "error": super_ledger["error"]}`), add `chat_ledger = usage.load_super(self.folder,
"chat")` and `chat_days = supervisor.spend_view(chat_ledger["records"])["days"]` beside the two `super_` lines above
the `return`, and the entry:

```python
                "chat": {"days": chat_days,
                         "today": None if chat_ledger["error"] else chat_days.get(today,
                             {"cost": 0.0, "runs": 0, "unknown": 0, "reserved": 0.0}),
                         "day_limit": self.cfg.get("chat_day_usd", 0),
                         "turn_limit": self.cfg.get("chat_turn_usd", 0), "error": chat_ledger["error"]}}
```

`web/app.js`, the passes block (plan 58 Task 4):

```js
const PASSES_WORDS = { supervisor: ["Supervisor passes", "supervisor"], super: ["Super agent passes", "super agent"],
  chat: ["Super agent chat", "chat", "turn", "turns"] };  // plan 61
function usageSupervisor(data = usage, key = "supervisor") {
  const sv = data[key], [title, who, one = "pass", many = "passes"] = PASSES_WORDS[key];
```

In the same function, `if (err && key === "super")` becomes `if (err && key !== "supervisor")`, and the `plural` line
becomes `const plural = (k) => `${k} ${k === 1 ? one : many}`;` with its two calls `plural(Number(today.runs) || 0)`
and `plural(runs)`. The Usage page line gains `+ usageSupervisor(usage, "chat")` after `usageSupervisor(usage,
"super")`.

## 2.4 Tests first

`tests/test_tuning.py`: the whitelist set gains the six keys.

`tests/test_superchat.py`:

```python
"""Plan 61: the chat. Task 2: settings and ledger; Task 3: the thread file; Task 4: the turn and the routes.
Scratch homes only; no paid provider, no port 47770, no ~/.claude."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import paths, superchat, tuning, usage
from tests.test_superagent_server import T0


class SettingsTest(unittest.TestCase):
    def test_defaults_and_bad_values(self):
        limits, errors = superchat.settings(paths.DEFAULTS)
        self.assertEqual((limits, errors), ({"chat_model": "sonnet", "chat_turn_usd": 0.5, "chat_day_usd": 3.0,
                                             "chat_timeout_s": 600}, []))
        _, errors = superchat.settings(dict(paths.DEFAULTS, chat_model="fable", chat_turn_usd=0, chat_timeout_s=True))
        self.assertEqual(errors, ["chat_model must be haiku, sonnet or opus",
                                  "chat_turn_usd must be a number between 0.05 and 2",
                                  "chat_timeout_s must be a whole number between 60 and 1800"])
        self.assertEqual(superchat.off(limits, [], 3.0), "chat off for today: $3.00 of $3.00")
        self.assertEqual(superchat.off(dict(limits, chat_day_usd=0.0), [], 0), "chat is off (chat_day_usd is 0)")
        self.assertEqual(superchat.off(limits, ["x"], 0), "chat settings: x")
        self.assertEqual(superchat.off(limits, [], 0.4), "")

    def test_tuning_whitelist(self):
        self.assertEqual(tuning.validate({"chat_model": "fable"}, paths.DEFAULTS)[1], {"chat_model": "haiku, sonnet or opus"})
        self.assertEqual(tuning.validate({"chat_model": "opus"}, paths.DEFAULTS), ({"chat_model": "opus"}, {}))
        self.assertIn("chat_turn_usd", tuning.validate({"chat_turn_usd": 0.01}, paths.DEFAULTS)[1])
        self.assertEqual(tuning.validate({"super_acts_day": 0}, paths.DEFAULTS), ({"super_acts_day": 0}, {}))


class ChatLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_chat_section_has_the_super_rules(self):
        day = usage.day_of(T0)
        self.assertEqual(usage.reserve_super(self.folder, "c1", day, 0.5, 1.0, "chat")["status"], "reserved")
        self.assertEqual(usage.reserve_super(self.folder, "c2", day, 0.5, 1.0, "chat")["status"], "reserved")
        self.assertEqual(usage.reserve_super(self.folder, "c3", day, 0.5, 1.0, "chat"),
                         {"status": "cap", "error": "chat day limit reached", "reserved": 0.0})
        self.assertEqual(usage.record_super(self.folder, "c1", {"cost": 0.12}, "chat")["status"], "settled")
        self.assertEqual(usage.record_super(self.folder, "c2", {"cost": None}, "chat")["status"], "unknown")
        records = usage.load_super(self.folder, "chat")["records"]
        self.assertEqual({k: (r["kind"], r["status"], r["cost"]) for k, r in records.items()},
                         {"c1": ("chat", "settled", 0.12), "c2": ("chat", "unknown", 0.0)})
        self.assertEqual(usage.load_super(self.folder)["records"], {})  # the super section is untouched

    def test_a_bad_chat_record_is_an_error(self):
        (self.folder / "usage-days.json").write_text(json.dumps({"chat": {"c1": {"kind": "super"}}}), encoding="utf-8")
        self.assertEqual(usage.load_super(self.folder, "chat")["error"], "usage-days.json chat has an invalid record")
```

`tests/test_superagent_server.py` (`SuperRouteTest.test_usage_report_has_the_super_agent` keeps passing) gains
`test_usage_report_has_the_chat`: GET `/api/usage` has `chat` `{"days": {}, "today": {"cost": 0.0, "runs": 0,
"unknown": 0, "reserved": 0.0}, "day_limit": 3.0, "turn_limit": 0.5, "error": ""}`; and `hub.chat_spend()` is
`{"today": 0.0, "turns": 0, "day_limit": 3.0, "turn_limit": 0.5, "error": "", "off": ""}`.

## 2.5 Steps

- [ ] 1. Write the tests; `py -m unittest tests.test_superchat tests.test_tuning`: red.
- [ ] 2. Make the 2.1 to 2.3 edits. Focused tests green; `tests.test_superagent tests.test_superagent_server
      tests.test_usage` green (the `super` messages unchanged).
- [ ] 3. `node --check web/app.js`. Full suite green (report the count). Stage the new files, the test files,
      `console/paths.py`, `console/tuning.py`, `console/usage.py`, and only this task's hunks of `console/server.py`
      and `web/app.js`. Commit with the message above.
