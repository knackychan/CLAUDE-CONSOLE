# Task 2: GET /api/super serves the cards (read only)

> Contract: [README.md](README.md) 4.4, 4.5, 4.6, 4.10. Decisions D1 a (only served actions), D2 a (batch accept), D3 a
> (an observed chat only opens). The page will draw a button because `acts` lists it and enable it because its `off` is
> "". This task adds the data; it writes nothing and starts nothing (plan 58 section 3.9: GET is a pure projection).

**Files**
- Modify: `console/superwin.py` (`CARD_ACTS`, `card_acts`, `own_answer`, `batch_answer`, `order_lines`)
- Modify: `console/server.py` (`Hub._super_card`, `Hub._session_acts`, `Hub._super_facts`, `super_view` growth;
  other chats edit this file: anchored edits, stage only these hunks)
- Modify: `tests/test_superwin.py`; create the `ServedCardTest` class in `tests/test_superwin_server.py`

Commit boundary: `feat: GET /api/super serves each card's actions, facts and batch answer (plan 59 T2)`.

## 2.1 Tests first (red)

`tests/test_superwin.py` (pure; the served payloads are `Hub.actions`-shaped, copied from `server.py:1109` as of
`a627264`):

```python
def act(id_, label="", post="/api/task/x", off="", confirm=False, **body):
    return {"id": id_, "label": label or id_, "post": post, "body": dict(body, task="t"), "off": off, "confirm": confirm}


MSG = {"target": {"step": 1, "session": "s1"}, "mode": "answer", "reason": "", "timing": "", "cold": None, "attachments": True}


class CardActsTest(unittest.TestCase):
    """README 4.5: the allowlist per served state. Everything not listed is dropped; `off` is kept."""

    def view(self, state, primary=(), bar=(), menu=(), message=MSG):
        return {"state": state, "line": state, "primary": list(primary), "bar": list(bar), "menu": list(menu), "message": message}

    def ids(self, got):
        return [a["id"] for a in got["primary"]], [a["id"] for a in got["bar"]], [a["id"] for a in got["menu"]]

    def test_decision_keeps_every_option_and_drops_default_auto(self):
        v = self.view("decision", [act("1"), act("2"), act("default_auto")], [act("redo"), act("stop")], [act("terminal")])
        self.assertEqual(self.ids(superwin.card_acts(v, "decision")), (["1", "2"], [], []))

    def test_each_state_carries_only_what_a_card_may(self):
        table = [  # state, primary in, bar in, menu in -> primary, bar, menu out
            ("plan_ready", ["confirm", "confirm_auto"], ["edit_plan", "redo", "stop"], ["handoff"], (["confirm"], [], [])),
            ("hold", ["confirm"], ["keep", "stop"], ["retry"], (["confirm"], ["keep"], [])),
            ("suggestion", ["approve"], ["reject", "stop"], ["delete"], (["approve"], ["reject"], [])),
            ("done", ["accept"], ["reopen"], ["handoff", "folder", "delete"], (["accept"], ["reopen"], [])),
            ("failed_twice", ["retry"], ["stepdone", "handoff", "finish"], ["delete"], (["retry"], ["stepdone", "finish"], [])),
            ("stuck", ["retry"], ["stepdone", "finish"], ["delete"], (["retry"], ["stepdone", "finish"], [])),
            ("handed", ["start_next"], [], ["delete"], (["start_next"], [], [])),
            ("session_interrupted", ["resume"], [], [], (["resume"], [], [])),
            ("session_blocked", ["terminal"], [], [], (["terminal"], [], [])),
            ("session_stall", ["done"], [], [], (["done"], [], [])),
        ]
        for state, p, b, m, want in table:
            with self.subTest(state=state):
                v = self.view(state, [act(i) for i in p], [act(i) for i in b], [act(i) for i in m])
                self.assertEqual(self.ids(superwin.card_acts(v, "x")), want)

    def test_dismiss_is_kept_like_reject(self):
        v = self.view("suggestion", [act("approve")], [act("dismiss"), act("stop")])
        self.assertEqual(self.ids(superwin.card_acts(v, "suggestion"))[1], ["dismiss"])

    def test_a_hand_off_hint_carries_the_handoff_form_only(self):
        v = self.view("running", [], [act("stop"), act("pause")], [act("handoff", post=""), act("terminal"), act("delete")])
        self.assertEqual(self.ids(superwin.card_acts(v, "hand_off")), ([], ["handoff"], []))  # in the bar: a card draws primary and bar
        self.assertEqual(self.ids(superwin.card_acts(v, "stuck")), ([], [], []))  # running carries nothing otherwise

    def test_observed_running_paused_ready_carry_nothing_and_off_is_kept(self):
        for state in ("observed", "running", "paused", "ready", "stopped"):
            v = self.view(state, [act("resume")], [act("stop")], [act("continue"), act("fork")])
            self.assertEqual(self.ids(superwin.card_acts(v, "x")), ([], [], []), state)
        v = self.view("done", [act("accept", off="a step is running")])
        self.assertEqual(superwin.card_acts(v, "accept")["primary"][0]["off"], "a step is running")

    def test_the_message_and_line_ride_along(self):
        got = superwin.card_acts(self.view("done", [act("accept")]), "accept")
        self.assertEqual((got["state"], got["message"]["mode"], got["line"]), ("done", "answer", "done"))


class OwnAnswerTest(unittest.TestCase):
    ITEM = {"type": "task", "id": "t1"}

    def test_a_task_may_be_answered_in_the_box_when_the_message_is_an_answer_or_next(self):
        v = {"message": MSG}
        got = superwin.own_answer(v, "decision", self.ITEM)
        self.assertEqual(got, {"mode": "answer", "post": "/api/task/message", "off": "",
                               "body": {"task": "t1", "target": MSG["target"]}, "request_id": True})
        nxt = superwin.own_answer({"message": dict(MSG, mode="next")}, "suggestion", self.ITEM)
        self.assertEqual(nxt["mode"], "next")
        chat = superwin.own_answer({"message": MSG}, "chat", self.ITEM)  # a window-run chat task at a STOP question (plans 30, 42)
        self.assertEqual((chat["mode"], chat["post"]), ("answer", "/api/task/message"))
        self.assertIsNone(superwin.own_answer({"state": "observed"}, "chat", self.ITEM))  # an observed chat task has no message

    def test_not_for_other_kinds_or_other_modes(self):
        self.assertIsNone(superwin.own_answer({"message": MSG}, "accept", self.ITEM))
        self.assertIsNone(superwin.own_answer({"message": dict(MSG, mode="queued")}, "decision", self.ITEM))
        self.assertIsNone(superwin.own_answer({"message": None}, "decision", self.ITEM))

    def test_off_carries_the_served_reason(self):
        got = superwin.own_answer({"message": dict(MSG, reason="Supervisor off.")}, "stuck", self.ITEM)
        self.assertEqual(got["off"], "Supervisor off.")

    def test_a_console_run_answers_through_continue(self):
        item = {"type": "session", "id": "s9"}
        v = {"message": {"mode": "answer", "reason": "", "target": {"session": "s9"}}}
        self.assertEqual(superwin.own_answer(v, "stop", item), {"mode": "answer", "post": "/api/continue", "off": "",
                                                                "body": {"session": "s9"}, "request_id": False})
        self.assertIsNone(superwin.own_answer(v, "failed", item))


class BatchAnswerTest(unittest.TestCase):
    def member(self, **kw):
        base = {"kind": "accept", "level": "gated", "acts": {"primary": [act("accept", "Accept")]}}
        return dict(base, **kw)

    def test_identical_enabled_accepts_batch(self):
        self.assertEqual(superwin.batch_answer([self.member(), self.member()]), {"id": "accept", "label": "Accept"})

    def test_anything_different_or_disabled_or_confirming_does_not(self):
        off = self.member(acts={"primary": [act("accept", "Accept", off="a step is running")]})
        confirm = self.member(acts={"primary": [act("accept", "Accept", confirm=True)]})
        other = self.member(acts={"primary": [act("confirm", "Confirm")]})
        for bad in (off, confirm, other, self.member(level="auto"), self.member(kind="decision")):
            with self.subTest(bad=bad["kind"]):
                self.assertIsNone(superwin.batch_answer([self.member(), bad]))
        self.assertIsNone(superwin.batch_answer([]))
        self.assertIsNone(superwin.batch_answer([self.member(acts={"primary": []})]))

    def test_only_accept_is_a_batch_answer(self):
        m = self.member(kind="decision", acts={"primary": [act("1", "style.css")]})
        self.assertIsNone(superwin.batch_answer([m, m]))  # D2 a


class OrderLinesTest(unittest.TestCase):
    def test_comments_and_blanks_go_and_lines_are_clipped_and_masked(self):
        text = "# Standing orders\n\nfashion first.\n  never raise lint  \n# x\n" + "y" * 300 + "\nuse token=abc\n"
        got = superwin.order_lines(text)
        self.assertEqual(got[:2], ["fashion first.", "never raise lint"])
        self.assertEqual(len(got[2]), superagent.LINE_MAX)
        self.assertNotIn("abc", got[3])
        self.assertEqual(superwin.order_lines(""), [])
```

`tests/test_superwin_server.py` (real Hub; `Hub.actions` is real for the four states a scratch task can reach, canned for
the rest; the file's import line gains `DECISION`: `from tests.test_superagent_server import SuperHubTest, T0, DECISION`):

```python
class ServedCardTest(SuperHubTest):
    """GET /api/super's cards, read through Hub.super_view() (the HTTP wrapper is plan 58 Task 6's)."""

    def card(self, view, tid):
        return next(i for c in view["queue"] for i in c["items"] if i["id"] == tid)

    def test_plan_to_confirm_hold_stuck_and_done_carry_their_served_actions(self):
        plan = self.task(1)                                              # waiting, plan ready: confirm
        fable = self.task(2, why="confirm Fable")
        stuck = self.task(3, state="stuck", why="step 01 failed")
        done = self.task(4, state="done", why="")
        view = self.hub.super_view()
        a = self.card(view, plan)["acts"]
        self.assertEqual((a["state"], [x["id"] for x in a["primary"]], a["primary"][0]["post"]), ("plan_ready", ["confirm"], "/api/task/confirm"))
        f = self.card(view, fable)
        self.assertEqual((f["acts"]["state"], f["always"], f["acts"]["primary"][0]["confirm"]), ("hold", "Fable confirm", True))
        s = self.card(view, stuck)["acts"]
        self.assertEqual(([x["id"] for x in s["primary"]], s["primary"][0]["post"]), (["retry"], ""))   # a form: opens the task
        self.assertEqual([x["id"] for x in s["bar"]], ["stepdone", "finish"])
        d = self.card(view, done)
        self.assertEqual((d["acts"]["primary"][0]["id"], d["acts"]["primary"][0]["post"]), ("accept", "/api/task/accept"))
        self.assertEqual(d["facts"], [["no verify · 2 steps · $0.10", "h"]])

    def test_every_card_has_the_new_fields(self):
        t = self.task(1)
        item = self.card(self.hub.super_view(), t)
        for key in ("back", "incomplete", "observed", "path", "open", "facts", "acts", "own", "stay"):
            self.assertIn(key, item)
        self.assertEqual((item["back"], item["incomplete"], item["observed"]), (False, "", False))
        self.assertEqual(item["path"], ["proj", "Task 1"])
        self.assertEqual(item["open"], {"kind": "task", "id": t, "step": 1})
        self.assertEqual(item["stay"], "")                                   # a plan to confirm may go later
        fable = self.card(self.hub.super_view(), self.task(2, why="confirm Fable"))
        self.assertEqual(fable["stay"], "Fable confirm")                     # code's reason, drawn as "Stays here"

    def test_canned_states(self):
        t = self.task(1, why="asks: Which file?", decision=dict(DECISION))  # kind `decision`: `own` needs it (OWN_KINDS)
        canned = {
            "decision": {"state": "decision", "line": "needs you · Which file?", "primary": [act("1", "style.css", "/api/task/message"), act("2", "app.js", "/api/task/message"), act("default_auto")],
                         "bar": [act("stop")], "menu": [act("terminal")], "message": MSG},
            "suggestion": {"state": "suggestion", "line": "needs you", "primary": [act("approve", post="/api/task/supervisor")],
                           "bar": [act("reject", post="/api/task/supervisor"), act("stop")], "menu": [], "message": dict(MSG, mode="next")},
            "observed": {"state": "observed", "line": "observed · VS Code", "primary": [], "bar": [], "menu": [act("continue")]},
        }
        for name, payload in canned.items():
            with self.subTest(name), mock.patch.object(server.Hub, "actions", return_value=payload):
                item = self.card(self.hub.super_view(), t)
                self.assertEqual(item["observed"], name == "observed")
                if name == "decision":
                    self.assertEqual([a["id"] for a in item["acts"]["primary"]], ["1", "2"])
                    self.assertEqual(item["own"]["post"], "/api/task/message")
                if name == "observed":
                    self.assertEqual((item["acts"]["primary"], item["acts"]["menu"], item["own"]), ([], [], None))

    def test_a_console_run_session_serves_its_levers_not_a_task_view(self):
        row = {"id": "s1", "group": "needs", "state": "interrupted", "window": True, "run_live": False, "title": "Run", "project": "proj",
               "project_dir": str(self.project), "text": "stopped", "stop_question": "", "source": "window", "last_ts": T0}
        lv = {"continue": "", "terminal": "", "verify": ""}
        with mock.patch.object(server.Hub, "session", return_value=dict(row, cwd=str(self.project))), \
                mock.patch.object(server.Hub, "levers", return_value=lv):
            acts = self.hub._session_acts("s1")
        self.assertEqual(acts["state"], "session_interrupted")
        self.assertEqual(acts["primary"], [{"id": "resume", "label": "Resume", "post": "/api/continue",
                                            "body": {"session": "s1", "text": server.RESUME_TEXT}, "off": "", "confirm": False}])
        for state, ids in (("blocked", ["terminal"]), ("stall", ["done"]), ("failed", []), ("verify_failed", [])):
            with mock.patch.object(server.Hub, "session", return_value=dict(row, state=state)), \
                    mock.patch.object(server.Hub, "levers", return_value=lv):
                self.assertEqual([a["id"] for a in self.hub._session_acts("s1")["primary"]], ids, state)
        with mock.patch.object(server.Hub, "session", return_value=dict(row, state="stop")), \
                mock.patch.object(server.Hub, "levers", return_value=dict(lv, **{"continue": "still working: wait until it stops"})):
            stop = self.hub._session_acts("s1")
        self.assertEqual(stop["message"]["reason"], "still working: wait until it stops")
        with mock.patch.object(server.Hub, "session", return_value=dict(row, window=False)):
            self.assertEqual(self.hub._session_acts("s1")["state"], "observed")

    def test_batch_card_has_an_answer_only_when_every_member_serves_the_same_accept(self):
        a, b = self.task(1, state="done", why=""), self.task(2, state="done", why="")
        for t in (a, b):
            self.hub.super["ann"][self.key(t)] = {"do": "batch", "rank": 1, "say": "ok", "why": "", "batch": "acc", "until": None}
        self.hub.super["last"] = {"n": 1, "ok": True, "at": T0, "items": 2}
        card = next(c for c in self.hub.super_view()["queue"] if len(c["items"]) == 2)
        self.assertEqual(card["answer"], {"id": "accept", "label": "Accept"})
        self.hub.tasks[b]["accepted"] = T0  # one member no longer serves an accept
        self.hub.super["ann"][self.key(a)]["batch"] = "acc"
        view = self.hub.super_view()
        self.assertTrue(all(c.get("answer") is None for c in view["queue"]))

    def test_the_top_level_fields(self):
        self.task(1)
        view = self.hub.super_view()
        self.assertEqual(view["mode"], "waiting")
        self.assertEqual(view["controls"]["sort"], {"label": "Sort now", "off": ""})
        self.assertEqual(view["controls"]["pause"], {"label": "Pause", "off": ""})
        self.assertEqual(view["order_lines"], [])
        self.assertEqual(view["since"], {"at": view["since"]["at"], "lines": [], "spent": {"tasks": 0.0}})
        self.assertEqual(view["counts"]["queue"], self.hub.snapshot()["super"]["for_you"])  # the one number
        self.assertEqual(view["rev"], self.hub.snapshot()["super"]["rev"])
        self.assertEqual(view["by_project"], self.hub.snapshot()["super"]["by_project"])

    def test_orders_lines_follow_the_file(self):
        (superagent.folder(self.hub.folder) / superagent.ORDERS_FILE).write_text("# mine\nfashion first\n", encoding="utf-8")  # plan 58's orders file
        self.assertEqual(self.hub.super_view()["order_lines"], ["fashion first"])

    def test_unranked_modes_keep_every_action(self):
        t = self.task(1)
        self.hub.super["paused"] = True
        view = self.hub.super_view()
        self.assertEqual((view["state"], view["mode"], view["controls"]["resume"]), ("unranked", "paused", {"label": "Resume", "off": ""}))
        item = self.card(view, t)
        self.assertEqual([a["id"] for a in item["acts"]["primary"]], ["confirm"])
        self.assertEqual(item["say"], "")

    def test_get_calls_actions_once_per_item_outside_tlock_and_writes_nothing(self):
        for n in range(1, 6):
            self.task(n)
        held = []
        real = server.Hub.actions

        def spy_actions(hub, task):
            held.append(hub.tlock._is_owned())  # RLock: True when this thread holds it
            return real(hub, task)

        with mock.patch.object(server.Hub, "actions", autospec=True, side_effect=spy_actions) as spy, \
                mock.patch.object(superagent, "save_state", side_effect=AssertionError("save")), \
                mock.patch.object(superagent, "append_log", side_effect=AssertionError("log")), \
                mock.patch("console.paths.write_text_atomic", side_effect=AssertionError("write")):
            view = self.hub.super_view()
        self.assertEqual(spy.call_count, 5)  # plan 58's describe loop once per item; the card reuses that view
        self.assertEqual(held, [False] * 5)  # the gates run outside tlock, as GET /api/task does
        self.assertEqual(view["counts"]["queue"], 5)
        self.assertEqual(self.hub.super_threads, [])

    def test_get_at_thirty_items_fits_the_budget(self):  # README 9: measured here, not at the end
        import statistics
        import time as clock
        for n in range(1, 31):
            self.task(n)
        samples = []
        for _ in range(5):
            t = clock.perf_counter()
            self.hub.super_view()
            samples.append(clock.perf_counter() - t)
        ms = statistics.median(samples) * 1000
        self.assertLess(ms, 150 * 4, f"GET /api/super at 30 items took {ms:.0f} ms")  # 4x slack for a loaded test machine; Task 8 measures for real
```

## 2.2 Code

### `console/superwin.py` (additions)

```python
# README 4.5: what a queue card may carry, by the served `state` of Hub.actions (or _session_acts). The page draws what
# is listed here and enables it by `off`; a state not listed carries nothing. None means every primary action.
CARD_ACTS = {
    "decision": (None, (), ()),                      # every option; default_auto stays on the task page
    "plan_ready": (("confirm",), (), ()),
    "hold": (("confirm", "retry"), ("keep",), ()),
    "suggestion": (("approve",), ("reject", "dismiss"), ()),
    "done": (("accept",), ("reopen",), ()),
    "failed_twice": (("retry", "resume"), ("stepdone", "finish"), ()),
    "stuck": (("retry", "resume"), ("stepdone", "finish"), ()),
    "handed": (("start_next",), (), ()),
    "session_interrupted": (("resume",), (), ()),
    "session_blocked": (("terminal",), (), ()),
    "session_stall": (("done",), (), ()),
}
HAND_OFF_CARD = ((), ("handoff",), ())               # a hand-off hint: the task's own Hand off form, in the bar (a card draws primary and bar)
# [D1 b, Fred 2026-11-08] with plan 55 Task 0 and this plan's Task 0 served: "failed_twice" and "stuck" put "retry_up"
# first in primary (the orange primary), "hold" adds "run_instead" to primary, and HAND_OFF_CARD becomes
# ((), ("hint_dismiss", "handoff"), ()). Nothing else changes; a card still draws only what Hub.actions serves.
OWN_KINDS = frozenset({"decision", "question", "suggestion", "failed_twice", "stuck", "stop", "chat"})  # chat: a window-run chat task's STOP question
BATCH_ANSWERS = frozenset({"accept"})                # D2 a


def card_acts(view: dict, kind: str) -> dict:
    """The served actions a card may carry (README 4.5). `view` is Hub.actions(task) or Hub._session_acts(sid)."""
    take = HAND_OFF_CARD if kind == "hand_off" else CARD_ACTS.get(view.get("state", ""), ((), (), ()))
    primary_ids, bar_ids, menu_ids = take

    def keep(actions, ids):
        return [dict(a) for a in actions or [] if (ids is None and a["id"] != "default_auto") or (ids is not None and a["id"] in ids)]

    return {"state": view.get("state", ""), "line": view.get("line", ""), "hint": view.get("hint", ""),
            "primary": keep(view.get("primary"), primary_ids), "bar": keep(view.get("bar"), bar_ids),
            "menu": keep(view.get("menu"), menu_ids), "message": view.get("message")}


def own_answer(view: dict, kind: str, item: dict):
    """Write your own answer: where the box would post, or None. An answer or a next-step message only (a queued
    guidance is not an answer); `off` carries the served reason so the link can be greyed with it."""
    m = view.get("message")
    if kind not in OWN_KINDS or not m or m.get("mode") not in ("answer", "next"):
        return None
    if item["type"] == "session":
        return ({"mode": "answer", "post": "/api/continue", "off": m.get("reason", ""), "body": {"session": item["id"]},
                 "request_id": False} if kind == "stop" else None)
    return {"mode": m["mode"], "post": "/api/task/message", "off": m.get("reason", ""),
            "body": {"task": item["id"], "target": m.get("target")}, "request_id": True}


def batch_answer(members: list):
    """The one action a batch card answers with, or None (README 4.6): every member serves the same enabled,
    non-confirming `accept`, with the same label, kind and level."""
    first = None
    for it in members:
        ps = [a for a in (it.get("acts") or {}).get("primary", []) if a["id"] in BATCH_ANSWERS and not a["off"] and not a["confirm"]]
        if len(ps) != 1:
            return None
        sig = (ps[0]["id"], ps[0]["label"], it.get("kind"), it.get("level"))
        if first is None:
            first = sig
        elif sig != first:
            return None
    return {"id": first[0], "label": first[1]} if first else None


def order_lines(text: str) -> list:
    """The orders a pass reads: non-blank lines that do not start with #, trimmed, masked, clipped."""
    out = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(redact.clip(redact.mask(line), superagent.LINE_MAX))
    return out
```

### `console/server.py`

```python
    def _session_acts(self, sid: str) -> dict:
        """Hub.actions-shaped view of a session that is not a task (README 4.5), from Hub.levers alone. A session that
        is not a Console run is observed: nothing answers it from here."""
        row, lv = self.session(sid), self.levers(sid) or {}
        base = {"state": "observed", "line": "", "primary": [], "bar": [], "menu": [], "message": None}
        if row is None or not row["window"]:
            return dict(base, line="observed")
        act = lambda id_, label, post, body, off="": {"id": id_, "label": label, "post": post, "body": body, "off": off, "confirm": False}
        state = row["state"]
        if state == "stop":
            return dict(base, state="session_stop", line=state, message={"mode": "answer", "reason": lv.get("continue", ""),
                        "target": {"session": sid}, "timing": "Sends an answer to the run."})
        if state == "interrupted":
            primary = [act("resume", "Resume", "/api/continue", {"session": sid, "text": RESUME_TEXT}, lv.get("continue", ""))]
        elif state == "blocked":
            primary = [act("terminal", "Open in terminal", "/api/terminal", {"session": sid}, lv.get("terminal", ""))]
        elif state == "stall":
            primary = [act("done", "Mark done", "/api/done", {"session": sid})]
        else:
            primary = []
        return dict(base, state="session_" + state, line=state, primary=primary)

    @staticmethod
    def _super_facts(task, view: dict, incomplete: str) -> list:
        """The facts code knows for an accept card: the last verify's verdict, steps and cost. "h" marks a fact Fred
        should not lean on (no verify, a FAIL, or evidence the pass could not read)."""
        if not task or view.get("state") != "done":
            return []
        verify = [s for s in task["steps"] if s["kind"] == "verify" and s["state"] == "done"]
        verdict = verify[-1].get("verdict") if verify else ""
        word = "verify output not available" if incomplete else {"PASS": "verify passed", "FAIL": "verify failed"}.get(verdict, "no verify")
        rest = view["line"].split(" · ", 1)[-1]
        return [[f"{word} · {rest}", "ok" if word == "verify passed" else "h"]]

    def _super_card(self, item: dict, task, view) -> dict:
        """README 4.4: one queue item's served fields. Read only; `item` is plan 58's described item and `view` the
        Hub.actions(task) plan 58's describe loop already computed for it (never computed twice); a session item has
        no view and gets _session_acts."""
        view = self._session_acts(item["id"]) if item["type"] == "session" else (view or self.actions(task))
        acts, inc = superwin.card_acts(view, item["kind"]), item.get("incomplete") or ""  # [58 R7] the flag's name
        step = 0
        if task is not None:
            failed = [s["n"] for s in task["steps"] if s["state"] == "failed" or s.get("verdict") == "FAIL"]
            step = failed[-1] if item["kind"] in ("failed_twice", "stuck") and failed else task["current"]
        return dict(item, acts=acts, own=superwin.own_answer(view, item["kind"], item), observed=view["state"] == "observed",
                    stay=superwin.stay_reason(item, self.super_clock()), incomplete=inc, facts=self._super_facts(task, view, inc), path=[item["project"], item["title"]],
                    open={"kind": item["type"], "id": item["id"], "step": step})
```

`RESUME_TEXT = "You were interrupted. Check `git diff` first, then finish the task."` joins the module constants and
`Hub.actions` uses it (the string at `server.py:1239` is replaced by the constant; no wording change).

`super_view` (plan 58 Task 6, with Task 1's swap of `superagent.queue` for `superwin.queue`). It already describes every
live item (`described`, plan 58 3.9: full `describe`, evidence read, bounded) and, to do so, calls `Hub.actions(task)`
once per task item. **Lock scope**: that describe loop runs outside `tlock` on a copy of the items and the state taken
under it (GET /api/task calls `actions` without `tlock` today, 58 README 2); only the copy is taken under the lock.
Keep each item's view: `views[item["key"]] = view` in that loop (one line in plan 58's code; bind at step 0). Build the
window data from the described list, so the view and the snapshot differ only in how much evidence they read:

```python
        w = self._super_window(snap, described, state=projection, raw=self.super, spend=today)  # Task 1: queue over the described items; mode, rev, by_project, counts
        for card in w["cards"]:
            card["items"] = [self._super_card(i, self.tasks.get(i["id"]) if i["type"] == "task" else None, views.get(i["key"])) for i in card["items"]]
            card["answer"] = superwin.batch_answer(card["items"]) if len(card["items"]) > 1 else None
        later = [dict(i, path=[i["project"], i["title"]]) for i in w["later"]]
        spent = superwin.spent_since(self.super, sum(r["cost"] for r in snap["tasks"]))
        view.update(queue=w["cards"], later=later, rev=w["rev"], mode=w["mode"], counts=w["counts"], paused_at=self.super.get("paused_at"),
                    controls=superwin.controls(w["mode"]), by_project=w["by_project"], order_lines=superwin.order_lines(orders_text),
                    since={**superwin.since(self.super, w["now"]), "spent": {"tasks": spent}})
```

(`orders_text` is the orders text plan 58's view already reads for its `orders` field; `projection` is plan 58's
current-basis-filtered copy of the state its GET queues from (R3), `today` the spend figure its one ledger read gave,
`views` the dict above. A card item keeps every plan 58 field and gains `acts`, `own`, `observed`, `incomplete`, `facts`,
`path`, `open`, `back`. `view["state"]`, `why`, `sorting`, `last`, `spend`, `coverage`, `digest`, `notes` stay plan 58's.)
The orders file in the tests is `superagent.folder(hub.folder) / superagent.ORDERS_FILE` (58/01:44, :118); plan 58 has
no helper method for it and this plan adds none.

## 2.3 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_superwin tests.test_superwin_server`: red for the missing functions.
- [ ] 2. Make the 2.2 edits. Focused tests green; `tests.test_superagent_server` (plan 58's GET tests) green: every
      field it asserts is still there. `test_get_at_thirty_items_fits_the_budget` reports its median in its message:
      note the figure in the commit body (README 9: measured here first).
- [ ] 3. Full suite green (report the count). Stage the test files by path and only this task's hunks of
      `console/server.py` and `console/superwin.py`. Commit with the message above.
