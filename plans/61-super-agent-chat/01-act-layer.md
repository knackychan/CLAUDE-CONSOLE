# Task 1: the act layer

> Contract: [README.md](README.md) 3.1. Builds after plan 58 Tasks 1 to 6 are merged to master. D1 (a) and D3 (a)
> are marked where (b) changes a line.

**Files**
- Create: `console/superact.py`
- Modify: `console/server.py` (import, `Hub.__init__`, `Hub.super_act`, `Hub._press`, `Hub.act_dismiss`,
  `Hub.act_undo`, `Hub.recent_acts`, `Hub._super_act_room`, `Hub._act_note`, `task_lever`'s label; stage only this
  task's hunks)
- Create: `tests/test_superact.py`

Commit boundary: `feat: the super agent act layer (plan 61 T1)`.

## 1.1 `console/superact.py`

```python
"""Plan 61: the act layer's rules (README 3.1). Pure: no file, lock, thread or model. Hub.super_act is the only
caller of verdict and clean_args; the Hub presses what they allow, through the Hub method each route calls."""
import hashlib
import json

from . import redact, tasks, usage

ORIGINS = ("chat", "super", "fred")  # fred: a Confirm card or an Undo that Fred clicked in the window
MODELS = ("auto", "haiku", "sonnet", "opus")  # what an act may name; never fable
TEXT_MAX = 500
ALWAYS = {"delete": "Delete", "drop": "Drop", "finish": "Finish", "stop": "Stop", "stepdone": "Accept step result",
          "confirm_auto": "a level change", "default_auto": "a level change"}
WINDOW_ONLY = frozenset({"edit_steps", "edit_prompt", "edit_plan", "review", "terminal", "folder"})  # D2 (a)
FORMS = {"retry": ("model", "note"), "add_step": ("kind", "model", "text"), "handoff": ("follow_up", "note"),
         "reopen": ("text",)}
NEEDS_TEXT = frozenset({"add_step", "reopen"})
FRED_SUGGESTION = frozenset({"approve", "reject", "dismiss"})  # D1 (a): never pressed by a pass; (b) empties it
UNDO = {"pause": "resume", "resume": "pause", "start": "stop", "confirm": "stop", "retry": "stop", "add_step": "stop"}
LEVERS = ("stop", "pause", "resume", "retry", "stepdone", "confirm", "clear", "done", "accept", "redo", "keep")
CAPS = {"super_acts_day": (0, 100), "super_acts_task_hour": (0, 6)}
PLACES = ("primary", "bar", "menu")


def flat(card: dict) -> list:
    return [a for place in PLACES for a in card.get(place) or []]


def find(card: dict, action_id):
    return next((a for a in flat(card) if a.get("id") == action_id), None)


def card_hash(card: dict) -> str:
    """16 hex over the card's state and every action's id, post, body and gate: a Confirm card is out of date once
    this changes."""
    data = [card.get("state"), [[a["id"], a["post"], a["body"], a["off"]] for a in flat(card)]]
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def always_reason(action_id: str, task: dict) -> str:
    """README 3.1.1: why this press is Fred's in every mode; "" when it is not."""
    if action_id in ALWAYS:
        return ALWAYS[action_id]
    if action_id.startswith("level_"):
        return "a level change"
    if action_id == "confirm" and task.get("why") == "confirm Fable":
        return "Fable"
    if action_id == "confirm" and tasks.held(task):
        return "Run anyway"
    return ""


def verdict(origin: str, level: str, card: dict, action_id, task: dict, forwarded: str = "") -> tuple:
    """(kind, why, action): kind is press, click (the chat asks for Fred's Confirm) or refuse. README 3.1 step 2."""
    if card.get("state") == "observed":
        return "refuse", "an observed chat: open its card", None  # D3 (a)
    action = find(card, action_id) if isinstance(action_id, str) else None
    if action is None:
        return "refuse", "not on the card", None
    if action["off"]:
        return "refuse", action["off"], action
    if action_id in WINDOW_ONLY or (not action["post"] and action_id not in FORMS):
        return "refuse", "opens in the window", action
    always = always_reason(action_id, task)
    if origin == "super":
        if level != "auto":
            return "refuse", f"the level is {level}: only auto acts alone", action
        if forwarded:
            return "refuse", "always forwarded: " + forwarded, action
        if always:
            return "refuse", "always yours: " + always, action
        if action_id in FRED_SUGGESTION:
            return "refuse", "the task supervisor's suggestion stays yours", action
    if origin == "chat" and always:
        return "click", always, action
    return "press", "", action


def pressable(card: dict, task: dict, level: str, forwarded: str = "") -> list:
    """The ids a pass may press now (Task 5 shows them in the digest)."""
    return [a["id"] for a in flat(card) if verdict("super", level, card, a["id"], task, forwarded)[0] == "press"]


def clean_args(action_id: str, args) -> tuple:
    """(args, error): only the form's own fields, checked (README 3.1.2); a press with a post takes none."""
    if not isinstance(args, dict):
        return {}, "arguments must be an object"
    allowed = FORMS.get(action_id, ())
    extra = sorted(k for k in args if k not in allowed)
    if extra:
        return {}, f"{action_id} takes no {extra[0]}"
    out = {}
    for key, value in args.items():
        if key == "model" and value not in MODELS:
            return {}, "model: auto, haiku, sonnet or opus"
        if key == "kind" and value not in tasks.NEXT_KINDS:
            return {}, "kind: " + ", ".join(tasks.NEXT_KINDS)
        if key == "follow_up" and not isinstance(value, bool):
            return {}, "follow_up: true or false"
        if key in ("note", "text"):
            if not isinstance(value, str) or len(value.strip()) > TEXT_MAX:
                return {}, f"{key}: text of at most {TEXT_MAX} characters"
            value = redact.mask(value.strip())
        out[key] = value
    if action_id in NEEDS_TEXT and not out.get("text"):
        return {}, "text: say what the step should do"
    return out, ""


def caps(cfg: dict) -> tuple:
    """(caps, errors) of the background acts, checked like superagent.settings; an error keeps them off."""
    out, errors = {}, []
    for key, (low, high) in CAPS.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            errors.append(f"{key} must be a whole number between {low} and {high}")
            value = 0
        out[key] = value
    return out, errors


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def room(records: list, task_id: str, now: float, caps_: dict) -> str:
    """"" when a background act may go now, else why not (README 3.2): the local day's count and the task's hour,
    counted from the audit's intents."""
    if not caps_["super_acts_day"] or not caps_["super_acts_task_hour"]:
        return "background acts are off"
    mine = [r for r in records if r.get("phase") == "act" and r.get("origin") == "super" and _num(r.get("ts"))]
    day = usage.day_of(now)
    if sum(1 for r in mine if usage.day_of(r["ts"]) == day) >= caps_["super_acts_day"]:
        return f"{caps_['super_acts_day']} background acts today"
    if sum(1 for r in mine if r.get("task") == task_id and now - 3600 < r["ts"] <= now) >= caps_["super_acts_task_hour"]:
        return f"{caps_['super_acts_task_hour']} background acts on this task within an hour"
    return ""


def uncertain(records: list) -> dict:
    """{act: intent} for every intent with no outcome and no dismissal: shown, never replayed."""
    open_ = {}
    for r in records:
        act = r.get("act")
        if not isinstance(act, str):
            continue
        if r.get("phase") == "act":
            open_[act] = {k: r.get(k) for k in ("ts", "origin", "task", "action", "label")}
        elif r.get("phase") in ("acted", "act_dismissed"):
            open_.pop(act, None)
    return open_


def joined(records: list, n: int = 20) -> list:
    """The last n acts, newest first: each intent with its outcome (done, refused), uncertain or dismissed, and
    every refused background act."""
    acts, order = {}, []
    for r in records:
        phase, act = r.get("phase"), r.get("act")
        if phase == "act" and isinstance(act, str):
            acts[act] = {"act": act, "ts": r.get("ts"), "origin": r.get("origin"), "task": r.get("task"),
                         "action": r.get("action"), "label": r.get("label"), "args": r.get("args") or {},
                         "state": "uncertain", "why": ""}
            order.append(act)
        elif phase == "acted" and act in acts:
            acts[act].update(state="done" if r.get("ok") else "refused", why=r.get("why") or "")
        elif phase == "act_dismissed" and act in acts:
            acts[act]["state"] = "dismissed"
        elif phase == "act_refused":
            key = f"refused-{len(order)}"
            acts[key] = {"act": "", "ts": r.get("ts"), "origin": r.get("origin"), "task": r.get("task"),
                         "action": r.get("action"), "label": r.get("label"), "args": {}, "state": "refused",
                         "why": r.get("why") or ""}
            order.append(key)
    return [acts[k] for k in reversed(order[-n:])]
```

## 1.2 `console/server.py`

**Import.** Add `superact` to the `from . import ...` line that already names `superagent`.

**`Hub.__init__`.** After the `try`/`except` that loads `self.super` (its last line is
`self.super_error = superagent._clip(exc, 300)`), add:

```python
        self.super_uncertain, self.act_error = {}, ""  # plan 61: intents with no outcome in super.jsonl; never replayed
        try:
            self.super_uncertain = superact.uncertain(superagent.read_log(self.folder))
        except ValueError as exc:
            self.act_error = superagent._clip(exc, 300)
```

**`task_lever`'s label.** Replace the three lines of its non-fred branch:

```python
                for line in lines:
                    line["why"] = line["why"].replace(" by Fred", " by the supervisor")
                task["why"] = task["why"].replace(" by Fred", " by the supervisor")
```

with:

```python
                by = " by the super agent" if origin == "super" else " by the supervisor"  # plan 61
                for line in lines:
                    line["why"] = line["why"].replace(" by Fred", by)
                task["why"] = task["why"].replace(" by Fred", by)
```

**The act layer.** A new block of Hub methods after `super_action` (plan 58 Task 6):

```python
    # -- plan 61: the act layer (README 3.1) -------------------------------------------------------------------
    def super_act(self, task_id, action_id, args=None, origin="chat", *, forwarded="", card_hash=""):
        """The only way the super agent changes anything. Returns (status, body); body["outcome"] is done,
        needs_click, refused or uncertain."""
        if origin not in superact.ORIGINS:
            return 400, {"outcome": "refused", "why": "unknown origin"}
        with self.tlock:
            task = self.tasks.get(task_id) if isinstance(task_id, str) and tasks.safe_id(task_id) else None
            if task is None:
                return 404, {"outcome": "refused", "why": "unknown task"}
            card = self.actions(task)
            level = supervisor.policy(self.cfg, task, time.time())["mode"]
            kind, why, action = superact.verdict(origin, level, card, action_id, task, forwarded)
            title = task.get("title") or task_id
        label = action["label"] if action else str(action_id)[:40]
        if kind != "refuse" and card_hash and card_hash != superact.card_hash(card):
            kind, why = "refuse", "out of date: the card changed"
        if kind != "refuse" and any(u.get("task") == task_id for u in self.super_uncertain.values()):
            kind, why = "refuse", "an earlier act on this task is uncertain: dismiss it in the thread first"
        if kind != "refuse" and origin == "super":
            why = self._super_act_room(task_id)
            kind = "refuse" if why else kind
        if kind == "refuse":
            if origin == "super":
                self._act_note({"phase": "act_refused", "origin": origin, "task": task_id,
                                "action": str(action_id)[:40], "label": label, "why": why})
            return 409, {"outcome": "refused", "why": why, "label": label}
        clean, error = superact.clean_args(action["id"], args or {})
        if error:
            return 400, {"outcome": "refused", "why": error, "label": label}
        if kind == "click":
            return 200, {"outcome": "needs_click", "why": why, "label": label, "task": task_id, "title": title,
                         "action": action["id"], "args": clean, "hash": superact.card_hash(card)}
        act = uuid.uuid4().hex
        intent = {"phase": "act", "act": act, "origin": origin, "task": task_id, "action": action["id"],
                  "label": label, "args": clean}
        try:
            superagent.append_log(self.folder, intent)
        except OSError as exc:
            return 503, {"outcome": "refused", "why": "the audit cannot be written: " + superagent._clip(exc, 200),
                         "label": label}
        held = dict({k: intent[k] for k in ("origin", "task", "action", "label")}, ts=time.time())
        try:
            status, data = self._press(task_id, action, clean, origin)
        except Exception as exc:  # the effect is unknown: shown, never replayed (plan 44 pattern)
            self.super_uncertain[act] = held
            self._super_changed()
            return 500, {"outcome": "uncertain", "why": superagent._clip(exc, 200), "label": label, "act": act}
        ok = 200 <= status < 300
        why = "" if ok else superagent._clip((data or {}).get("error") or f"status {status}", 300)
        try:
            superagent.append_log(self.folder, {"phase": "acted", "act": act, "status": status, "ok": ok, "why": why})
        except OSError:
            self.super_uncertain[act] = held  # the audit has no outcome: what a restart would show
        self._super_changed()
        if not ok:
            return status, {"outcome": "refused", "why": why, "label": label, "act": act}
        return 200, {"outcome": "done", "label": label, "task": task_id, "title": title, "act": act}

    def _press(self, task_id, action, args, origin):
        """One press (README 3.1.2, 3.1.3) through the Hub method its route calls, so every gate runs again."""
        who = "super" if origin == "super" else "fred"
        aid, post, body = action["id"], action["post"], dict(action["body"])
        if not post and aid == "retry":
            model = args.get("model", "")
            return self.task_lever(task_id, "retry", args.get("note", ""), "" if model == "auto" else model, "",
                                   origin=who)
        if not post and aid == "reopen":
            with self.tlock:
                target = self.message_availability(self.tasks[task_id])["target"]
            return self.task_message({"task": task_id, "request_id": str(uuid.uuid4()), "text": args["text"],
                                      "target": target})
        if not post and aid == "add_step":
            request = {"task": task_id, "source_step": body.get("source_step"),
                       "source_session": body.get("source_session"), "kind": args.get("kind", "code"),
                       "instructions": args["text"], "model": args.get("model", "auto")}
            status, preview = self.preview_next(request)
            if status != 200:
                return status, preview
            return self.request_next(dict(request, revision=preview["revision"], request_id=str(uuid.uuid4())),
                                     origin=who)
        if not post and aid == "handoff":
            note = args.get("note", "")
            status, preview = self.task_handoff({"task": task_id, "note": note}, preview=True)
            if status != 200:
                return status, preview
            return self.task_handoff({"task": task_id, "note": note, "create": args.get("follow_up", False),
                                      "request_id": uuid.uuid4().hex, "revision": preview["revision"]})
        lever = post.removeprefix("/api/task/")
        if lever in superact.LEVERS:
            return self.task_lever(body.get("task"), lever, "", None, "", origin=who, remember=body.get("remember"))
        if post == "/api/task/message":
            return self.task_message(body)
        if post == "/api/task/supervisor":
            return self.supervisor_action(body)
        if post == "/api/continue":
            return self.pull(body.get("session"), "continue", body.get("text", ""), False, [])
        return 409, {"error": "opens in the window"}

    def _super_act_room(self, task_id):
        caps, errors = superact.caps(self.cfg)
        if errors:
            return errors[0]
        try:
            records = superagent.read_log(self.folder)
        except ValueError as exc:
            return superagent._clip(exc, 200)
        return superact.room(records, task_id, time.time(), caps)

    def _act_note(self, record):
        try:
            superagent.append_log(self.folder, record)
        except OSError:
            pass  # a refusal changed nothing; its line is best effort

    def act_dismiss(self, act):
        """Fred's dismissal of an uncertain act: one audit line, then it no longer blocks its task."""
        if act not in self.super_uncertain:
            return 404, {"error": "no uncertain act " + str(act)[:40]}
        try:
            superagent.append_log(self.folder, {"phase": "act_dismissed", "act": act, "by": "fred"})
        except OSError as exc:
            return 503, {"error": "the audit cannot be written: " + superagent._clip(exc, 200)}
        self.super_uncertain.pop(act, None)
        self._super_changed()
        return 200, {"act": act}

    def act_undo(self, act):
        """README 3.1.4: the reverse press of a done act, as Fred's own click."""
        try:
            done = next((a for a in superact.joined(superagent.read_log(self.folder), 500) if a["act"] == act), None)
        except ValueError as exc:
            return 409, {"error": superagent._clip(exc, 200)}
        if done is None or done["state"] != "done" or done["action"] not in superact.UNDO:
            return 409, {"error": "this act has no Undo"}
        return self.super_act(done["task"], superact.UNDO[done["action"]], {}, "fred")

    def recent_acts(self, n=20):
        try:
            return superagent._masked(superact.joined(superagent.read_log(self.folder), n))
        except ValueError:
            return []
```

`self.actions(task)` runs inside `tlock` (an `RLock`; `actions` takes `self.lock` inside, the existing order).

## 1.3 Tests first (`tests/test_superact.py`)

```python
"""Plan 61 Task 1: the act layer. Pure rules, then the Hub with tasks from plan 58's make_task. Scratch homes only;
no paid provider, no port 47770, no ~/.claude."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from console import paths, server, superact, superagent, supervisor, tasks
from tests.test_superagent_server import FAKE, T0, make_task


def act(id_, post="/api/task/pause", off="", body=None):
    return {"id": id_, "label": id_.title(), "post": post, "body": body or {"task": "t1"}, "off": off, "confirm": False}


def card(*actions, state="running"):
    return {"state": state, "line": state, "primary": list(actions), "bar": [], "menu": [], "message": {}}


TASK = {"id": "t1", "why": "", "state": "running"}


class VerdictTest(unittest.TestCase):
    def test_order_of_refusals(self):
        c = card(act("pause"), act("x", off="the task is paused"), act("edit_plan", post=""), act("start_next", post=""))
        self.assertEqual(superact.verdict("chat", "gated", c, "nope", TASK)[:2], ("refuse", "not on the card"))
        self.assertEqual(superact.verdict("chat", "gated", c, "x", TASK)[:2], ("refuse", "the task is paused"))
        self.assertEqual(superact.verdict("chat", "gated", c, "edit_plan", TASK)[:2], ("refuse", "opens in the window"))
        self.assertEqual(superact.verdict("chat", "gated", c, "start_next", TASK)[:2], ("refuse", "opens in the window"))
        self.assertEqual(superact.verdict("chat", "gated", card(state="observed"), "continue", TASK)[:2],
                         ("refuse", "an observed chat: open its card"))
        self.assertEqual(superact.verdict("chat", "off", c, "pause", TASK)[:2], ("press", ""))

    def test_always_yours_by_origin(self):
        c = card(act("stop"), act("level_auto", "/api/task/supervisor"), act("confirm", "/api/task/confirm"))
        self.assertEqual(superact.verdict("chat", "auto", c, "stop", TASK)[:2], ("click", "Stop"))
        self.assertEqual(superact.verdict("super", "auto", c, "stop", TASK)[:2], ("refuse", "always yours: Stop"))
        self.assertEqual(superact.verdict("fred", "auto", c, "stop", TASK)[:2], ("press", ""))
        self.assertEqual(superact.verdict("chat", "auto", c, "level_auto", TASK)[:2], ("click", "a level change"))
        fable = dict(TASK, state="waiting", why="confirm Fable")
        self.assertEqual(superact.verdict("chat", "auto", c, "confirm", fable)[:2], ("click", "Fable"))
        self.assertEqual(superact.verdict("chat", "auto", c, "confirm", TASK)[:2], ("press", ""))

    def test_super_origin_needs_auto_and_no_forward(self):
        c = card(act("pause"), act("approve", "/api/task/supervisor"))
        self.assertEqual(superact.verdict("super", "gated", c, "pause", TASK)[:2],
                         ("refuse", "the level is gated: only auto acts alone"))
        self.assertEqual(superact.verdict("super", "auto", c, "pause", TASK, "second verify FAIL")[:2],
                         ("refuse", "always forwarded: second verify FAIL"))
        self.assertEqual(superact.verdict("super", "auto", c, "approve", TASK)[:2],  # D1 (a)
                         ("refuse", "the task supervisor's suggestion stays yours"))
        self.assertEqual(superact.pressable(c, TASK, "auto"), ["pause"])
        self.assertEqual(superact.pressable(c, TASK, "gated"), [])

    def test_card_hash_follows_gates(self):
        a, b = card(act("pause")), card(act("pause", off="busy"))
        self.assertEqual(len(superact.card_hash(a)), 16)
        self.assertNotEqual(superact.card_hash(a), superact.card_hash(b))


class CleanArgsTest(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(superact.clean_args("retry", {"model": "opus", "note": "  verify failed  "}),
                         ({"model": "opus", "note": "verify failed"}, ""))
        self.assertEqual(superact.clean_args("retry", {"model": "fable"})[1], "model: auto, haiku, sonnet or opus")
        self.assertEqual(superact.clean_args("pause", {"note": "x"})[1], "pause takes no note")
        self.assertEqual(superact.clean_args("add_step", {"model": "sonnet"})[1], "text: say what the step should do")
        self.assertEqual(superact.clean_args("add_step", {"text": "x", "kind": "deploy"})[1],
                         "kind: " + ", ".join(tasks.NEXT_KINDS))
        self.assertEqual(superact.clean_args("handoff", {"follow_up": "yes"})[1], "follow_up: true or false")
        self.assertEqual(superact.clean_args("reopen", {"text": "x" * 501})[1], "text: text of at most 500 characters")
        self.assertEqual(superact.clean_args("reopen", {"text": "use token=abc123"})[0], {"text": "use token=***"})


class AuditTest(unittest.TestCase):
    def test_uncertain_joined_and_room(self):
        recs = [{"ts": T0, "phase": "act", "act": "a1", "origin": "super", "task": "t1", "action": "pause", "label": "Pause"},
                {"ts": T0 + 1, "phase": "acted", "act": "a1", "ok": True, "status": 200, "why": ""},
                {"ts": T0 + 2, "phase": "act", "act": "a2", "origin": "chat", "task": "t2", "action": "retry", "label": "Retry"},
                {"ts": T0 + 3, "phase": "act_refused", "origin": "super", "task": "t3", "action": "stop", "why": "always yours: Stop"}]
        self.assertEqual(list(superact.uncertain(recs)), ["a2"])
        self.assertEqual([(a["act"], a["state"]) for a in superact.joined(recs)],
                         [("", "refused"), ("a2", "uncertain"), ("a1", "done")])
        self.assertEqual(list(superact.uncertain(recs + [{"phase": "act_dismissed", "act": "a2"}])), [])
        caps = {"super_acts_day": 20, "super_acts_task_hour": 1}
        self.assertEqual(superact.room(recs, "t1", T0 + 60, caps), "1 background acts on this task within an hour")
        self.assertEqual(superact.room(recs, "t1", T0 + 3601, caps), "")
        self.assertEqual(superact.room(recs, "t9", T0, dict(caps, super_acts_day=1)), "1 background acts today")
        self.assertEqual(superact.room(recs, "t9", T0, dict(caps, super_acts_day=0)), "background acts are off")
        self.assertEqual(superact.caps({"super_acts_day": True, "super_acts_task_hour": 2})[1],
                         ["super_acts_day must be a whole number between 0 and 100"])
```

`SuperActHubTest(unittest.TestCase)`: `setUp` as plan 58's `SuperHubTest` without the `superagent.run` patch (a
scratch `CC_CONSOLE_HOME`, `self.project`, `self.hub = server.Hub(dict(paths.load_config(),
projects=[str(self.project)], supervisor_mode="gated", super_acts_day=20, super_acts_task_hour=2), home,
exe=FAKE)`); `self.log()` returns `superagent.read_log(self.hub.folder)`. Route methods are patched with
`mock.patch.object(self.hub, "<name>", return_value=(200, {...}))` where a real press would start a process; the
mapping and the audit are what this task tests (the routes keep their own tests).

- `test_refusals`: task 1 `make_task(..., state="waiting", why="plan ready: confirm")`. `super_act(t, "nope", {},
  "chat")` is 409 `not on the card` and writes no audit line; `super_act(t, "edit_plan", {}, "chat")` 409 `opens in
  the window`; `super_act("zz", "confirm")` 404; `super_act(t, "confirm", {}, "boss")` 400.
- `test_always_yours_needs_click`: `super_act(t, "stop", {}, "chat")` is 200 with `outcome` `needs_click`, `why`
  `Stop`, `label` `Stop`, `title` `Task 1`, and a 16-hex `hash` equal to `superact.card_hash(hub.actions(task))`;
  `self.log()` is `[]`; the task's state is unchanged.
- `test_press_maps_to_the_route`: with `task_lever` patched: `super_act(t, "confirm", {}, "chat")` calls
  `task_lever(t, "confirm", "", None, "", origin="fred", remember=None)` and answers 200 `done`; `self.log()` phases are
  `["act", "acted"]`, the intent's `origin` `chat`, `action` `confirm`, the outcome's `ok` True. A running task 2:
  `super_act(t2, "retry", {"model": "opus", "note": "n"}, "chat")` calls `task_lever(t2, "retry", "n", "opus", "",
  origin="fred")`; `"model": "auto"` passes `""`. With `preview_next` returning `(200, {"revision": "r1"})` and
  `request_next` patched: `add_step` with `{"text": "fix the gauge"}` calls `request_next` once with `kind` `code`,
  `model` `auto`, `instructions` `fix the gauge`, `revision` `r1`, a UUID `request_id`, `origin="fred"`. With
  `task_handoff` patched (`(200, {"revision": "h1", "text": "..."})` then `(200, {"task": t2})`): `handoff` with
  `{"follow_up": True}` calls it twice, the second body with `create` True, `revision` `h1` and a 32-hex
  `request_id`.
- `test_route_refusal_is_reported`: `task_lever` patched to `(409, {"error": "Resolve pending guidance first."})`:
  `super_act(t, "confirm", {}, "chat")` answers 409 `refused` with that `why`; the outcome line has `ok` False and the
  same `why`.
- `test_super_origin_gates`: the Hub's `supervisor_mode` `gated`: `super_act(t, "confirm", {}, "super")` is 409 `the
  level is gated: only auto acts alone` and the last line is `act_refused` with that `why`. A Hub with
  `supervisor_mode` `auto` and a task made under it: `confirm` from `super` presses with `task_lever(...,
  origin="super")`; `stop` from `super` is 409 `always yours: Stop`.
- `test_super_label`: real path, no patch: task 3 running (`make_task(..., state="running")`); `hub.task_lever(t3,
  "pause", origin="super")` is 200 and the chain line it wrote reads `paused by the super agent` (`tasks.fred` writes
  `paused by Fred`); the same call with `origin="supervisor"` on task 4 reads `paused by the supervisor`.
- `test_audit_first`: `superagent.append_log` patched to raise `OSError("disk full")`: `super_act(t, "confirm", {},
  "chat")` is 503 `the audit cannot be written: disk full`; the patched `task_lever` was never called.
- `test_uncertain_blocks_until_dismissed`: `task_lever` patched to raise `RuntimeError("boom")`: 500 `uncertain`
  with its `act`; `hub.super_uncertain` has it; a second `super_act(t, "confirm", {}, "chat")` is 409 `an earlier act on
  this task is uncertain: dismiss it in the thread first`; `act_dismiss(act)` is 200 and adds an `act_dismissed`
  line; the next press goes through. `act_dismiss("nope")` is 404.
- `test_uncertain_survives_restart`: an intent line written by hand with `superagent.append_log` and no outcome; a
  new Hub on the same folder has it in `super_uncertain`.
- `test_undo`: a done `pause` act in the log (written by a patched press), then `hub.tasks[t]["owner"] = "fred"` so
  the card serves `resume`; `act_undo(act)` calls `task_lever(t, "resume", ...)` through `super_act(..., "fred")`; an act of `accept` (written by hand) answers 409 `this act has no Undo`.
- `test_caps`: an `auto` Hub with `super_acts_task_hour` 1: the first `super` press of `confirm` goes, the second on the
  same task is 409 `1 background acts on this task within an hour`.

## 1.4 Steps

- [ ] 1. Write `tests/test_superact.py`; run `py -m unittest tests.test_superact`: red (no module `superact`).
- [ ] 2. Create `console/superact.py` (1.1). The pure classes go green; the Hub class stays red.
- [ ] 3. Make the 1.2 edits. `py -m unittest tests.test_superact tests.test_superagent_server tests.test_server`
      green.
- [ ] 4. Full suite green (report the count). Stage `console/superact.py`, `tests/test_superact.py` and only this
      task's hunks of `console/server.py`. Commit with the message above.
