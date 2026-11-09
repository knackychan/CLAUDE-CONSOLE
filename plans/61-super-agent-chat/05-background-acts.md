# Task 5: background acts

> Contract: [README.md](README.md) 3.6 (D1 (b, bounded), Fred 2026-11-09). Builds after plan 58's live check (its
> Task 7). The first real run is on one project at `auto`; every other project stays where it is.

**Files**
- Modify: `console/superagent.py` (the import, `ACT`, `SCHEMA`, `SCHEMA_REMINDER`, `evidence`, `basis`, `_act_shape`,
  `check`)
- Modify: `console/server.py` (`_super_describe`, `_super_complete`, `Hub._super_acts`; stage only this task's hunks)
- Modify: `tests/fake_claude.py` (`SUPER-ACT` in `superagent()`)
- Modify: `tests/test_superagent.py` (plan 58's D11 schema assertion), `tests/test_superact.py` (`ActCheckTest`,
  `BackgroundActTest`)

Commit boundary: `feat: background acts at auto through the act layer (plan 61 T5)`.

## 5.1 `console/superagent.py`

The `from . import` line gains `superact` (no cycle: `superact` imports `redact`, `supervisor`, `tasks` and `usage`,
none of which imports `superagent`). After `DO = ("forward", "batch", "later")`:

```python
ACT = "act"  # plan 61: an entry that asks code to press one served action; stored as a forward annotation
ACT_ARGS = ("model", "note", "text", "kind", "follow_up")
```

`evidence`: the field tuple gains `"acts"` after `"verify"`, and the drop list (`for field in ("contract", ...`) gains
`"acts"` first, so a full item loses its acts before its evidence. `basis`: its key tuple gains `"acts"`, so a card
that changes makes the annotation stale.

`SCHEMA`, in the item properties, `"do"` becomes `{"type": "string", "enum": list(DO) + [ACT]}` and a new property
follows `"until"`:

```python
                "act": {"type": "object", "additionalProperties": False, "required": ["action"], "properties": {
                    "action": {"type": "string", "maxLength": 40},
                    "args": {"type": "object", "additionalProperties": False, "properties": {
                        "model": {"type": "string", "enum": ["auto", "haiku", "sonnet", "opus"]},
                        "note": {"type": "string", "maxLength": 500},
                        "text": {"type": "string", "maxLength": 500},
                        "kind": {"type": "string", "enum": list(tasks.NEXT_KINDS)},
                        "follow_up": {"type": "boolean"}}}}},
```

`SCHEMA_REMINDER` gains, before `The digest follows.`: `"An item whose block lists acts may answer do act with act
{action, args}, action one of those ids; code checks every act again and may refuse it. After a second verify FAIL
the one act offered is retry with args model opus. "`

A helper before `check`:

```python
def _act_shape(value) -> bool:
    if not isinstance(value, dict) or set(value) - {"action", "args"} or not isinstance(value.get("action"), str) \
            or not value["action"] or len(value["action"]) > 40:
        return False
    args = value.get("args", {})
    return isinstance(args, dict) and not set(args) - set(ACT_ARGS)
```

`check`, four edits:

1. `fields = {"key", "do", "rank", "say", "why", "batch", "until"}` gains `"act"`, and `acts = []` joins `ann,
   dropped, trimmed, seen = {}, [], [], set()`.
2. The operation test `elif entry.get("do") not in DO or ...` reads `elif entry.get("do") not in DO + (ACT,) or ...`,
   and a new test follows it:

```python
            elif ("act" in entry) != (entry.get("do") == ACT) or ("act" in entry and not _act_shape(entry["act"])):
                error = "invalid act"
```

3. The annotation line becomes `a = {"do": "forward" if entry["do"] == ACT else entry["do"], ...}` (the rest
   unchanged), and an act branch goes first in the `reason` chain:

```python
        reason = ""
        if entry["do"] == ACT:
            lifted = superact.LIFT.get(item.get("always") or "") == entry["act"]["action"]  # D1 (b), README 3.6
            if _must_forward(dict(item, always="") if lifted else item) or evidence(item)[1]:
                trimmed.append({"key": handle, "why": "always forwarded: no act"})
            elif entry["act"]["action"] not in (item.get("acts") or []):
                trimmed.append({"key": handle, "why": "act not offered"})
            else:
                acts.append({"key": key, "action": entry["act"]["action"], "args": dict(entry["act"].get("args") or {}),
                             "say": a["say"], "why": a["why"], "forwarded": item.get("always") or ""})
        elif a["do"] != "forward" and (_must_forward(item) or evidence(item)[1]):
```

   (the old `if a["do"] != "forward" and ...` becomes this `elif`; the branches after it are unchanged).
4. The returned dict gains `"acts": acts`.

## 5.2 `console/server.py`

`_super_describe`, after `desc = superagent.describe(item, task, row, view, level, cfg["decision_timeout_s"], now)`:

```python
            if task and level == "auto":  # plan 61: what a pass may press now; nothing at the other levels
                desc["acts"] = superact.pressable(view, task, level, desc.get("always") or item.get("always") or "")
```

`_super_complete`: `checked = None` as the first line inside its outer `try` (a refused answer leaves it None), and
after `self.super_pending_results.pop(job["pid"], None)`:

```python
            if checked and checked["acts"]:
                self._super_acts(job, checked["acts"])  # plan 61: never from _super_reconcile
```

A Hub method after `_super_complete`:

```python
    def _super_acts(self, job, acts):
        """Plan 61 (README 3.6): a pass's acts, each pressed through the act layer after a fresh look. Called by
        _super_complete only, so a pass recovered by _super_reconcile never presses."""
        context = self._super_capture(extra_keys=[a["key"] for a in acts])
        with self.tlock:
            bases, _ = self._super_fresh(context)
            paused = bool(self.super.get("paused"))
        for a in acts:
            parts = a["key"].split(":")
            tid = parts[1] if len(parts) == 3 and parts[0] == "task" else ""
            why = ("the super agent is paused" if paused else "not a task" if not tid else
                   "the item changed" if bases.get(a["key"]) != job["bases"].get(a["key"]) else "")
            if why:
                self._act_note({"phase": "act_refused", "origin": "super", "task": tid, "action": a["action"],
                                "label": a["action"], "why": why, "pass": job["pid"]})
                continue
            self.super_act(tid, a["action"], a["args"], "super", forwarded=a["forwarded"])
```

## 5.3 `tests/fake_claude.py`

In `superagent(raw)`, after the `SUPER-BATCH` branch:

```python
    if "SUPER-ACT" in raw and entries:  # plan 61: I1 presses the first act its block offers
        block = re.search(r"^I1 (\{.*\})$", raw, re.M)
        offered = json.loads(block.group(1)).get("acts") if block else None
        if offered:
            entries[0].update(do="act", act={"action": offered[0]})
```

## 5.4 Tests first

`tests/test_superagent.py`: plan 58's assertion that the schema has no `act` field (D11) now asserts only that it
has no `order` field, and that `SCHEMA["properties"]["items"]["items"]["properties"]["act"]["required"] ==
["action"]`.

`tests/test_superact.py`, `ActCheckTest` (pure): an item `{"key": "task:t1:e1", "type": "task", "id": "t1", "kind":
"plan", "level": "auto", "acts": ["confirm"], "always": "", "deadline": None}` and `handles = {"I1":
"task:t1:e1"}`:

- `{"key": "I1", "do": "act", "rank": 1, "say": "s", "act": {"action": "confirm"}}`: `ann["task:t1:e1"]["do"]` is
  `forward`, `acts == [{"key": "task:t1:e1", "action": "confirm", "args": {}, "say": "s", "why": "", "forwarded":
  ""}]`.
- `"act": {"action": "stop"}`: no act, `trimmed` has `act not offered`; the item with `"always": "Fable confirm"`:
  `always forwarded: no act`.
- D1 (b): the item with `"always": "second verify FAIL"`, `"acts": ["retry"]` and the act `{"action": "retry", "args":
  {"model": "opus", "note": "n"}}`: kept, its `forwarded` `second verify FAIL`; the same item answered with `"act":
  {"action": "confirm"}`: trimmed `always forwarded: no act`.
- `do` `forward` with an `act`, `do` `act` without one, `"act": {"action": "confirm", "args": {"x": 1}}`: each is
  dropped with `invalid act`.

`BackgroundActTest(test_superagent_server.SuperHubTest)`: `setUp` calls `super().setUp()`, then sets
`self.hub.cfg.update(supervisor_mode="auto", super_acts_day=20, super_acts_task_hour=2)` before any task is made, and
patches `self.hub.task_lever` to `(200, {"task": ...})`. A pass runs as plan 58's Hub tests run one (a `task(...)`,
`tick` at the frozen clock, `drain`); `self.answer` returns the entries each test needs.

- `test_an_act_at_auto_presses`: task 1 waiting `plan ready: confirm`; the prompt (`self.calls[-1]["prompt"]`)
  holds `"acts":["confirm"`; the answer `do` `act` with `act` `{"action": "confirm"}`; after the pass the patched
  `task_lever` was called once with `(t1, "confirm", "", None, "", origin="super", remember=None)`; the audit has the
  `act` (origin `super`) and `acted` pair; `super_view()` still lists the item with `do` `forward` and its `say`.
- `test_gated_never_acts`: `supervisor_mode` `gated` for a fresh Hub and task: the prompt has no `"acts"`; the same
  answer is trimmed `act not offered`; `task_lever` never called.
- `test_always_forwarded_never_acts`: task 2 waiting `confirm Fable`: trimmed `always forwarded: no act`; no press.
- `test_second_fail_retries_once_on_opus` (D1 b): task 2 made `stuck` with `why` `verify failed twice: tests fail` and
  its current step `failed` (`steps[-1]["state"] = "failed"`, then `tasks.save`); its block in the prompt holds
  `"acts":["retry"]`; the answer `do` `act` with `act` `{"action": "retry", "args": {"model": "opus", "note": "verify
  on opus"}}`; the patched `task_lever` was called once with `(t2, "retry", "verify on opus", "opus", "",
  origin="super")`; the intent line has `lift` `second verify FAIL` and `step` the task's `current`. Then
  `self.hub.super_act(t2, "retry", {"model": "opus", "note": "x"}, "super", forwarded="second verify FAIL")` is 409
  `always forwarded: second verify FAIL: the opus retry of this step was used`.
- `test_capped_suggestion_is_approved` (D1 b): task 3 waiting `choose next step` with a saved suggestion written as plan
  44's `DispatchTest.pending` writes it (wake 1, status `suggest`, the decision `add_next_step`, error `3 supervisor
  steps since Fred acted: approve the next`); `self.hub._supervisor_dispatch` patched to `(200, {"task": t3})`; its
  block holds `"approve"` in `acts`; the answer act `{"action": "approve"}`; the patched dispatch was called once with
  `(t3, 1, "super")`.
- `test_stale_item`: the answer callback sets `self.hub.tasks[t1]["why"] = "replanned: x"` before it returns; after the
  pass the last audit line is `act_refused` with `the item changed`; no press.
- `test_paused`: the answer callback calls `self.hub.super_action({"action": "pause"})`; the act is refused `the super
  agent is paused`.
- `test_caps`: `super_acts_day` 1, tasks 1 and 3 both plan-ready and both answered with an act: one press, then an
  `act_refused` line with `1 background acts today`.
- `test_reconcile_never_presses`: `self.assertNotIn("_super_acts", inspect.getsource(server.Hub._super_reconcile))`
  and `self.assertNotIn("super_act(", inspect.getsource(server.Hub._super_reconcile))`.
- `test_end_to_end_with_the_fake_claude` (in `SuperRouteTest`'s style, `test_server.RunServerTest`, real fake claude,
  `supervisor_mode` `auto` set before the task): `orders.md` holds `SUPER-ACT`; one pass; the audit has an `act` line
  with origin `super` for task 1's first offered act.

## 5.5 Steps

- [ ] 1. Write the tests; `py -m unittest tests.test_superact tests.test_superagent`: red.
- [ ] 2. Make the 5.1 edits; the pure tests go green; `tests.test_superagent` green.
- [ ] 3. Make the 5.2 and 5.3 edits; `py -m unittest tests.test_superact tests.test_superagent_server` green.
- [ ] 4. Full suite green (report the count). Stage `console/superagent.py`, `tests/fake_claude.py`, the test files
      and only this task's hunks of `console/server.py`. Commit with the message above.
- [ ] 5. Fred: set one project to `auto` (Models page, Supervisor card) and watch a day's `act` lines in the thread
      before a second project (Task 7 records it).
