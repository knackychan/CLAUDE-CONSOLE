# Task 1: state v2, Fred's Later, the window queue, the one count, the mode, the log

> Contract: [README.md](README.md) 4.1a, 4.2, 4.3, 4.7, 4.10. Decisions D8 a (the queue spans all projects), D9 a (the word),
> D10 a (a finished task waiting for Accept is an item; written for a, the lines another answer drops are marked `D10`).
> Pure module first, then the three server seams (`snapshot`, the tick, `super_view`'s queue call) and the tray.
> Everything here reads plan 58's documented contract (README section 2); step 0 binds its Hub names in one method.

**Files**
- Create: `console/superwin.py` (also `accept_items`, D10 a)
- Modify: `console/superagent.py` (state v2: `extra_state`, `upgrade`, `check_extra`, `blank_state`, `load_state`)
- Modify: `console/server.py` (`Hub._super_inputs`, `_super_window`, `_super_summary`, `snapshot`, the tick's log lines,
  the one queue call in `super_view`; other chats edit this file: anchored edits, stage only these hunks)
- Modify: `console/tray.py` (`look`)
- Create: `tests/test_superwin.py`, `tests/test_superwin_server.py`
- Modify: `tests/test_superagent.py` (`load_state` of a v1 file returns the v2 keys with `looked` at the oldest `seen`; a malformed
  `hand`, `log` or `messages` blocks passes like any malformed key and never resets Pause), `tests/test_tray.py`

Commit boundary: `feat: the super agent window's state and its one count (plan 59 T1)`.

## 1.0 Step 0: bind plan 58's names (30 minutes, no behaviour)

Read the built `Hub` super section and write `Hub._super_inputs()` so it returns exactly the dict below. This is the
only method in this plan that names plan 58's Hub attributes; the rest of the plan calls it.

```python
    def _super_inputs(self) -> dict:
        """Plan 59: what the window needs from plan 58's Hub state, in one place (rename here, nowhere else).
        ranked/why: superagent.status; error: a settings error, a storage error or no claude.exe ("" for none);
        off: super_day_usd or super_pass_usd is 0; capped: today's settled plus held spend reached the day limit;
        sorting: None or {"n", "items", "since"}; last: state["last"]; never_reviewed: live items not in `reviewed`
        (plan 58 coverage); today: the day's super spend or None when the ledger cannot be read."""
        limits, errors = superagent.settings(self.cfg)
        ...  # bind to plan 58 Task 5/6: super_view builds the same facts for GET /api/super
        return {"ranked": ranked, "why": why, "error": error, "off": off, "capped": capped, "sorting": sorting,
                "never_reviewed": never, "today": today, "limits": limits}
```

Test it first (Section 1.1, `test_inputs_contract`): a scratch Hub with no task returns `ranked` False, `why` `no pass yet`,
`error` `""`, `off` False, `capped` False, `sorting` None, `never_reviewed` 0.

## 1.1 Tests first (red)

`tests/test_superwin.py`

```python
"""Plan 59 Task 1: superwin is pure. Items are plain dicts; superagent.queue is stubbed where only the wrapper is
under test, and plan 58's golden fixture (tests.test_superagent, table 4.2) is used once end to end."""
import unittest
from unittest import mock

from console import superagent, superwin

T0 = 1_800_000_000.0


def item(key, kind="hold", always="", project="D:/p", pid=None):
    return {"key": key, "type": "task", "id": pid or key, "kind": kind, "always": always, "project": "p",
            "project_dir": project, "title": "Task " + key, "label": key}


def state(**over):
    s = superagent.blank_state()
    s.update(over)
    return s


def stub_queue(items_, st, now, ranked):  # one card per item in the given order; later empty
    return {"queue": [{"batch": "", "rank": n, "items": [dict(i, new=False, do="forward", say="", why="")]}
                      for n, i in enumerate(items_, 1)], "later": []}


class AcceptItemTest(unittest.TestCase):
    """D10 a: a task that finished within a day and is not accepted is an item of kind `accept`."""

    def row(self, tid="d1", group="done", **kw):
        return dict({"id": tid, "group": group, "project": "p", "project_dir": "D:/p", "title": "Task " + tid, "label": tid}, **kw)

    def task(self, tid="d1", **kw):
        steps = [{"kind": "code", "state": "done", "attempts": [{}]}, {"kind": "verify", "state": "done", "verdict": "PASS", "attempts": [{}]}]
        return dict({"id": tid, "state": "done", "accepted": 0, "chat": False, "updated": T0, "steps": steps}, **kw)

    def items(self, rows, tasks, now=T0 + 60):
        return superwin.accept_items({"tasks": rows}, {t["id"]: t for t in tasks}, now)

    def test_a_fresh_finish_is_an_accept_item(self):
        (got,) = self.items([self.row()], [self.task()])
        self.assertEqual((got["kind"], got["always"], got["type"], got["id"]), ("accept", "", "task", "d1"))
        self.assertRegex(got["key"], r"^task:d1:[0-9a-f]{16}$")

    def test_not_for_accepted_chat_old_or_needs_rows(self):
        for label, rows, tasks, now in (
                ("accepted", [self.row()], [self.task(accepted=T0)], T0 + 60),
                ("chat", [self.row()], [self.task(chat=True)], T0 + 60),
                ("older than a day", [self.row()], [self.task()], T0 + superwin.ACCEPT_WINDOW_S + 1),
                ("already a needs row", [self.row(group="needs")], [self.task()], T0 + 60),
                ("still running", [self.row()], [self.task(state="running")], T0 + 60),
                ("no task", [self.row()], [], T0 + 60)):
            with self.subTest(label):
                self.assertEqual(self.items(rows, tasks, now), [])

    def test_the_key_moves_with_verify_verdict_and_attempts_not_with_time(self):
        k0 = self.items([self.row()], [self.task()])[0]["key"]
        self.assertEqual(self.items([self.row()], [self.task(updated=T0 + 500)], T0 + 600)[0]["key"], k0)
        t = self.task()
        t["steps"][1]["verdict"] = "FAIL"
        self.assertNotEqual(self.items([self.row()], [t])[0]["key"], k0)
        t = self.task()
        t["steps"].append({"kind": "code", "state": "done", "attempts": [{}]})  # a Reopen added a step
        self.assertNotEqual(self.items([self.row()], [t])[0]["key"], k0)


class StateTest(unittest.TestCase):
    def test_blank_state_is_v2_with_the_new_keys(self):
        s = superagent.blank_state()
        self.assertEqual(s["v"], 2)
        for key, empty in (("hand", {}), ("back", {}), ("fwd", []), ("looked", None), ("looked_cost", None),
                           ("log", []), ("messages", [])):
            self.assertEqual(s[key], empty)

    def test_upgrade_v1_adds_defaults_and_starts_looked_at_the_oldest_seen(self):
        v1 = {"v": 1, "n": 4, "paused": False, "seen": {"a": T0 + 5, "b": T0 + 1}, "reviewed": {}, "ann": {}, "last": None,
              "digest": [], "claimed": None}
        s = superagent.upgrade(v1, T0 + 99)
        self.assertEqual((s["v"], s["looked"], s["hand"], s["log"]), (2, T0 + 1, {}, []))
        self.assertEqual(superagent.upgrade(superagent.blank_state(), T0)["v"], 2)
        self.assertEqual(superagent.upgrade({"v": 1, "seen": {}}, T0 + 7)["looked"], T0 + 7)

    def test_check_extra_names_the_malformed_key(self):
        ok = superagent.blank_state()
        self.assertEqual(superagent.check_extra(ok), "")
        for key, bad in (("hand", {"k": "soon"}), ("hand", {"k": True}), ("hand", [1]), ("back", {"k": 1.5}),
                         ("fwd", [1]), ("looked", "x"), ("looked_cost", -1), ("log", [{"ts": 1, "g": 2, "t": "x", "p": ""}]),
                         ("log", ["x"]), ("messages", [{"id": "u", "ts": 1, "text": "x" * 501}]),
                         ("messages", [{"id": "u", "ts": 1, "text": "x"}] * 4)):
            with self.subTest(key=key, bad=bad):
                s = superagent.blank_state()
                s[key] = bad
                self.assertIn(key, superagent.check_extra(s))


class HandLaterTest(unittest.TestCase):
    def test_put_later_holds_one_fixed_hour_and_refuses_always_and_unknown(self):
        live = [item("a"), item("b", always="Fable confirm"), item("c")]
        s = state()
        done, refused = superwin.put_later(s, ["a", "b", "zz"], live, T0)
        self.assertEqual((done, s["hand"]), (["a"], {"a": T0 + 3600}))
        self.assertEqual(refused, {"b": "stays here: Fable confirm", "zz": "unknown item"})

    def test_a_decision_whose_default_is_about_to_be_taken_stays_too(self):
        live = [dict(item("a"), left_s=300, default="style.css"), dict(item("b"), left_s=None, default="style.css"), dict(item("c"), left_s=300, default="")]
        s = state()
        done, refused = superwin.put_later(s, ["a", "b", "c"], live, T0)
        self.assertEqual(done, ["b", "c"])
        self.assertRegex(refused["a"], r"^stays here: the default is taken at \d\d:\d\d$")
        self.assertEqual(superwin.stay_reason(live[1], T0), "")

    def test_hand_is_capped(self):
        live = [item(f"k{n}") for n in range(superwin.HAND_MAX + 5)]
        s = state()
        done, refused = superwin.put_later(s, [i["key"] for i in live], live, T0)
        self.assertEqual(len(s["hand"]), superwin.HAND_MAX)
        self.assertEqual(len(refused), 5)
        self.assertTrue(all(r == "Later is full: bring some back" for r in refused.values()))

    def test_queue_takes_hand_items_out_and_lists_them_in_later(self):
        live = [item("a"), item("b"), item("c")]
        s = state(seen={"a": T0, "b": T0 + 10, "c": T0 + 20}, hand={"b": T0 + 3600})
        with mock.patch.object(superagent, "queue", side_effect=stub_queue) as q:
            out = superwin.queue(live, s, T0 + 100, True)
        self.assertEqual([i["key"] for i in q.call_args.args[0]], ["a", "c"])  # superagent never sees b
        self.assertEqual([c["items"][0]["key"] for c in out["queue"]], ["a", "c"])
        (later,) = out["later"]
        self.assertEqual((later["key"], later["by"], later["do"], later["why"], later["age_s"]), ("b", "you", "later", "You put it later.", 90))
        self.assertRegex(later["until"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d$")
        self.assertEqual(superwin.counts(out["queue"], out["later"]), {"queue": 2, "later": 1, "always": 0, "new": 0})

    def test_an_item_that_must_stay_comes_back_even_inside_its_hour(self):
        live = [dict(item("a"), left_s=60, default="style.css"), item("b")]
        s = state(seen={"a": T0, "b": T0}, hand={"a": T0 + 3600, "b": T0 + 3600})
        with mock.patch.object(superagent, "queue", side_effect=stub_queue):
            out = superwin.queue(live, s, T0 + 5, True)
        self.assertEqual([c["items"][0]["key"] for c in out["queue"]], ["a"])
        self.assertEqual([i["key"] for i in out["later"]], ["b"])

    def test_hand_holds_in_every_mode_but_the_super_agents_own_later_does_not(self):
        live = [item("a"), item("b")]
        s = state(seen={"a": T0, "b": T0}, hand={"a": T0 + 3600})
        with mock.patch.object(superagent, "queue", side_effect=stub_queue):
            unranked = superwin.queue(live, s, T0 + 5, False)
        self.assertEqual([i["key"] for i in unranked["later"]], ["a"])

    def test_an_expired_hour_returns_the_item_once_with_the_back_marker(self):
        live = [item("a"), item("b")]
        s = state(n=7, hand={"a": T0 + 10, "gone": T0 + 10}, fwd=["gone"], back={"gone": 1})
        back, changed = superwin.sync(s, live, T0 + 11)
        self.assertEqual((back, changed, s["hand"], s["back"], s["fwd"]), (["a"], True, {}, {"a": 7}, []))
        self.assertEqual(superwin.sync(s, live, T0 + 12), ([], False))

    def test_back_marker_clears_when_a_later_pass_finishes(self):
        live = [item("a")]
        s = state(n=7, back={"a": 7}, last={"n": 7, "ok": True, "at": T0})
        self.assertEqual(superwin.sync(s, live, T0 + 1), ([], False))
        s["last"] = {"n": 8, "ok": True, "at": T0 + 50}
        self.assertEqual(superwin.sync(s, live, T0 + 60), ([], True))
        self.assertEqual(s["back"], {})

    def test_bring_back_from_either_later_and_the_pass_cannot_send_it_away_again(self):
        live = [item("a"), item("b"), item("c")]
        s = state(n=3, hand={"a": T0 + 3600}, ann={"b": {"do": "later", "until": T0 + 900, "rank": 1, "why": "w"}})
        done, refused = superwin.bring_back(s, ["a", "b", "c", "zz"], live)
        self.assertEqual(done, ["a", "b"])
        self.assertEqual(refused, {"c": "not in Later", "zz": "unknown item"})
        self.assertEqual((s["hand"], s["back"], s["fwd"]), ({}, {"a": 3, "b": 3}, ["a", "b"]))
        self.assertEqual((s["ann"]["b"]["do"], s["ann"]["b"]["until"]), ("forward", None))
        s["ann"]["b"]["do"] = "later"  # a later pass tries again
        with mock.patch.object(superagent, "queue", side_effect=stub_queue) as q:
            out = superwin.queue(live, s, T0 + 1, True)
        self.assertEqual(q.call_args.args[1]["ann"]["b"]["do"], "forward")
        self.assertEqual([c["items"][0]["back"] for c in out["queue"]], [True, True, False])


class CountTest(unittest.TestCase):
    def test_counts_by_project_marks_and_rev(self):
        a, b, c = item("a", project="D:/p"), item("b", project="D:/q"), item("c", project="D:/p")
        s = state(seen={"a": T0, "b": T0, "c": T0}, hand={"c": T0 + 3600})
        with mock.patch.object(superagent, "queue", side_effect=stub_queue):
            out = superwin.queue([a, b, c], s, T0 + 1, False)
        cards, later = out["queue"], out["later"]
        self.assertEqual(superwin.by_project(cards), {"D:/p": 1, "D:/q": 1})
        self.assertEqual(sum(superwin.by_project(cards).values()), superwin.counts(cards, later)["queue"])
        marks = superwin.marks(cards, later)
        self.assertEqual((marks["a"], marks["b"]), (["queue"], ["queue"]))
        self.assertEqual(marks["c"][0], "later")
        self.assertRegex(marks["c"][1], r"^\d\d:\d\d$")

    def test_a_batch_counts_each_member(self):
        cards = [{"batch": "acc", "rank": 1, "items": [item("a"), item("b"), item("c")]},
                 {"batch": "", "rank": 2, "items": [item("d")]}]
        self.assertEqual(superwin.counts(cards, [])["queue"], 4)
        self.assertEqual(superwin.by_project(cards), {"D:/p": 4})

    def test_rev_moves_with_advice_hand_back_mode_and_log_but_not_with_age_or_cost(self):
        live = [dict(item("a"), age_s=5, cost=0.1), item("b")]
        s = state(ann={"a": {"do": "forward", "rank": 1, "say": "x", "why": "", "batch": "", "until": None}})
        r0 = superwin.rev(live, s, "ranked", True, T0)
        live[0].update(age_s=500, cost=9.0)
        self.assertEqual(superwin.rev(live, s, "ranked", True, T0 + 30), r0)
        self.assertEqual(superwin.rev(list(reversed(live)), s, "ranked", True, T0), r0)  # order of the live list is not advice
        changes = [lambda: s["ann"]["a"].update(say="y"), lambda: s["ann"]["a"].update(rank=2),
                   lambda: s["hand"].update(b=T0 + 3600), lambda: s["back"].update(a=1), lambda: s["fwd"].append("b"),
                   lambda: s["log"].append({"ts": T0 + 1, "g": "x", "t": "t", "p": ""}), lambda: s.update(paused=True),
                   lambda: s.update(last={"n": 2, "ok": True})]
        for change in changes:
            change()
            r1 = superwin.rev(live, s, "ranked", True, T0)
            self.assertNotEqual(r1, r0)
            r0 = r1
        self.assertNotEqual(superwin.rev(live, s, "paused", False, T0), r0)

    def test_rev_sees_a_later_expire_and_an_hour_pass(self):
        live = [item("a"), item("b")]
        s = state(ann={"a": {"do": "later", "rank": 1, "say": "", "why": "w", "batch": "", "until": T0 + 100}}, hand={"b": T0 + 200})
        self.assertNotEqual(superwin.rev(live, s, "ranked", True, T0 + 50), superwin.rev(live, s, "ranked", True, T0 + 150))
        self.assertNotEqual(superwin.rev(live, s, "ranked", True, T0 + 150), superwin.rev(live, s, "ranked", True, T0 + 250))


class ModeTest(unittest.TestCase):
    def test_mode_table(self):
        ok, bad = {"ok": True}, {"ok": False}
        table = [  # error, paused, off, capped, sorting, last, never_reviewed, mode
            ("boom", True, False, False, False, ok, 0, "error"),
            ("", True, True, False, False, ok, 0, "paused"),
            ("", False, True, True, False, ok, 0, "off"),
            ("", False, False, True, True, ok, 0, "capped"),
            ("", False, False, False, True, bad, 3, "sorting"),
            ("", False, False, False, False, None, 0, "waiting"),
            ("", False, False, False, False, bad, 0, "failed"),
            ("", False, False, False, False, ok, 2, "partial"),
            ("", False, False, False, False, ok, 0, "ranked"),
        ]
        for error, paused, off, capped, sorting, last, never, want in table:
            with self.subTest(want=want):
                self.assertEqual(superwin.mode(error=error, paused=paused, off=off, capped=capped, sorting=sorting,
                                               last=last, never_reviewed=never), want)

    def test_controls(self):
        c = superwin.controls
        self.assertEqual(c("ranked"), {"pause": {"label": "Pause", "off": ""}, "resume": None, "sort": {"label": "Sort now", "off": ""}})
        self.assertEqual(c("paused")["resume"], {"label": "Resume", "off": ""})
        self.assertIsNone(c("paused")["pause"])
        self.assertEqual(c("paused")["sort"]["off"], "Resume first")
        self.assertEqual(c("sorting")["sort"], {"label": "Sorting", "off": "A sort is running"})
        self.assertEqual(c("failed")["sort"], {"label": "Sort again", "off": ""})
        for mode in ("off", "capped", "error"):
            self.assertIsNone(c(mode)["pause"])
            self.assertTrue(c(mode)["sort"]["off"])
        self.assertEqual(c("waiting")["sort"]["off"], "")

    def test_row_line(self):
        f = superwin.row_line
        kw = dict(running=6, later=2, last_hm="14:01", sorting_n=1, reviewed=10, live=14)
        self.assertEqual(f("ranked", **kw), "6 running · 2 later · sorted 14:01")
        self.assertEqual(f("sorting", **kw), "sorting 1 item · 6 running")
        self.assertEqual(f("sorting", **dict(kw, sorting_n=4)), "sorting 4 items · 6 running")
        self.assertEqual(f("partial", **kw), "reviewed 10 of 14 · 6 running")
        self.assertEqual(f("paused", **kw), "paused · oldest first · 6 running")
        self.assertEqual(f("off", **kw), "off · oldest first")
        self.assertEqual(f("capped", **kw), "today's limit reached · oldest first")
        self.assertEqual(f("failed", **kw), "last sort failed · oldest first")
        self.assertEqual(f("waiting", **kw), "waiting to sort · 6 running")
        self.assertEqual(f("error", **kw), "cannot sort · oldest first")


class LogTest(unittest.TestCase):
    def test_note_masks_clips_caps_and_ages(self):
        s = state()
        superwin.note(s, T0, "✓", "set token=abc123 done " + "x" * 400, "MOTION STUDIO")
        (line,) = s["log"]
        self.assertNotIn("abc123", line["t"])
        self.assertLessEqual(len(line["t"]), superwin.LOG_TEXT)
        for n in range(80):
            superwin.note(s, T0 + n, "·", f"line {n}")
        self.assertEqual(len(s["log"]), superwin.LOG_MAX)
        self.assertEqual(s["log"][-1]["t"], "line 79")
        superwin.note(s, T0 + 8 * 86400, "·", "fresh")
        self.assertEqual([x["t"] for x in s["log"]], ["fresh"])  # everything older than 7 days left

    def test_since_lists_newest_first_after_looked(self):
        s = state(looked=T0 + 10)
        for n, text in enumerate(("old", "a", "b")):
            superwin.note(s, T0 + 5 + n * 10, "·", text)
        got = superwin.since(s, T0 + 100)
        self.assertEqual([x["t"] for x in got["lines"]], ["b", "a"])
        self.assertRegex(got["lines"][0]["tm"], r"^\d\d:\d\d$")
        self.assertEqual(got["at"], T0 + 10)

    def test_mark_seen_sets_looked_and_cost(self):
        s = state(looked=T0)
        superwin.mark_seen(s, T0 + 50, 4.25)
        self.assertEqual((s["looked"], s["looked_cost"]), (T0 + 50, 4.25))
        self.assertEqual(superwin.since(s, T0 + 60)["lines"], [])
        self.assertEqual(superwin.spent_since(s, 5.0), 0.75)
        self.assertEqual(superwin.spent_since(s, 3.0), 0.0)  # never below zero
        self.assertEqual(superwin.spent_since(state(), 5.0), 0.0)  # never marked: unknown, shown as 0


class MessageTest(unittest.TestCase):
    def test_add_masks_refuses_long_and_caps_at_three(self):
        s = state()
        m = superwin.add_message(s, "fashion first, token=abc", T0, "u1")
        self.assertEqual((m["id"], m["ts"]), ("u1", T0))
        self.assertNotIn("abc", m["text"])
        superwin.add_message(s, "two", T0, "u2")
        superwin.add_message(s, "x" * superwin.MESSAGE_MAX, T0, "u3")
        with self.assertRaisesRegex(ValueError, "3 messages wait for the next sort"):
            superwin.add_message(s, "four", T0, "u4")
        for bad in ("   ", "", None, "x" * (superwin.MESSAGE_MAX + 1)):  # Fred's words are never cut silently
            with self.assertRaisesRegex(ValueError, "message must contain 1 to 500 characters"):
                superwin.add_message(state(), bad, T0, "u5")

    def test_drop_removes_only_the_ones_a_pass_read(self):
        s = state()
        for n in range(3):
            superwin.add_message(s, f"m{n}", T0, f"u{n}")
        superwin.drop_messages(s, ["u0", "u2"])
        self.assertEqual([m["id"] for m in s["messages"]], ["u1"])


class PurityTest(unittest.TestCase):
    def test_superwin_imports_neither_server_nor_supervisor_and_touches_no_file(self):
        import ast
        import console.superwin as mod
        tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
        names = {a.name.split(".")[-1] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        names |= {a.name.split(".")[-1] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse(names & {"server", "supervisor", "tasks", "paths", "usage"}, names)
        calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertFalse(calls & {"open", "print"}, calls)
```

Plan 58's golden fixture end to end (the one place the real `superagent.queue` runs; `[58 T2]`): in the same file,

```python
from tests import test_superagent as sa


class GoldenWithHandTest(unittest.TestCase):
    """Plan 58 table 4.2 with Fred's hour: B goes later; the rest keeps its order; the count follows."""

    def setUp(self):
        self.items, self.state, self.now = sa.golden_queue_fixture()  # plan 58's fixture (now T0+400, last pass T0+200)

    @staticmethod
    def keys(out):
        return [[i["key"] for i in c["items"]] for c in out["queue"]]

    def test_ranked_and_unranked_with_b_put_later(self):
        base = superwin.queue(self.items, self.state, self.now, True)
        self.assertEqual(self.keys(base), [["G"], ["A"], ["C"], ["D", "E"], ["B"], ["I"], ["F"]])  # plan 58 4.2, ranked
        self.assertEqual(superwin.counts(base["queue"], base["later"])["queue"], 8)
        done, _ = superwin.put_later(self.state, ["B"], self.items, self.now)
        self.assertEqual(done, ["B"])
        out = superwin.queue(self.items, self.state, self.now, True)
        self.assertEqual(self.keys(out), [["G"], ["A"], ["C"], ["D", "E"], ["I"], ["F"]])
        self.assertEqual([i["key"] for i in out["later"]], ["H", "B"])  # H: the super agent's, B: Fred's hour
        counts = superwin.counts(out["queue"], out["later"])
        self.assertEqual((counts["queue"], counts["later"]), (7, 2))
        unranked = superwin.queue(self.items, self.state, self.now, False)
        self.assertEqual([i["key"] for i in unranked["later"]], ["B"])  # unranked: H is back in For you, B stays
        self.assertEqual(superwin.counts(unranked["queue"], unranked["later"])["queue"], 8)

    def test_a_always_item_cannot_be_put_later(self):
        done, refused = superwin.put_later(self.state, ["G", "A"], self.items, self.now)
        self.assertEqual(done, [])
        self.assertEqual(refused["A"], "stays here: Fable confirm")
        self.assertEqual(refused["G"], "stays here: decision without a default")
```

(If plan 58's built fixture has another name, the `setUp` line is the one to change; the expected card keys are plan 58's
table 4.2 and must not change. The `always` strings are plan 58's `always_reason` words, table 4.1.)

`tests/test_superwin_server.py` (reuses plan 58's `SuperHubTest` fixtures: `make_task`, frozen clocks, patched `superagent.run`)

```python
"""Plan 59 Task 1 at the Hub: the snapshot's one count, the tick's log, the fallback. No model, no hub loop."""
import unittest
from unittest import mock

from console import server, superagent, superwin, tray
from tests.test_superagent_server import SuperHubTest, T0


class WindowCountTest(SuperHubTest):
    def test_inputs_contract(self):
        got = self.hub._super_inputs()
        for key, want in (("ranked", False), ("why", "no pass yet"), ("error", ""), ("off", False), ("capped", False),
                          ("sorting", None), ("never_reviewed", 0)):
            self.assertEqual(got[key], want)

    def test_snapshot_has_one_count_everywhere(self):
        for n in (1, 2, 3):
            self.task(n)
        self.tick(T0)
        snap = self.hub.snapshot()
        self.assertEqual(snap["counts"]["needs"], 3)
        self.assertEqual(snap["counts"]["for_you"], 3)
        sup = snap["super"]
        self.assertEqual((sup["for_you"], sup["later"], sup["mode"]), (3, 0, "waiting"))
        self.assertEqual(sum(sup["by_project"].values()), 3)
        self.assertEqual(set(sup["marks"]), {t["id"] for t in snap["tasks"]})
        self.assertRegex(sup["rev"], r"^[0-9a-f]{12}$")
        self.assertIn("waiting to sort", sup["line"])

    def test_fred_s_hour_lowers_the_count_but_never_the_raw_needs(self):
        a, b = self.task(1), self.task(2)
        self.tick(T0)
        self.hub.super["hand"][self.key(a)] = T0 + 3600
        snap = self.hub.snapshot()
        self.assertEqual((snap["counts"]["needs"], snap["counts"]["for_you"], snap["super"]["later"]), (2, 1, 1))
        self.assertEqual(snap["super"]["marks"][a][0], "later")
        self.assertEqual(snap["super"]["marks"][b], ["queue"])

    def test_a_fresh_finish_reaches_for_you_but_not_the_raw_needs(self):  # D10 a
        d = self.task(1, state="done", why="")
        snap = self.hub.snapshot()
        self.assertEqual((snap["counts"]["needs"], snap["counts"]["for_you"]), (0, 1))
        self.assertEqual(snap["super"]["marks"][d], ["queue"])
        self.hub.tasks[d]["accepted"] = T0
        self.assertEqual(self.hub.snapshot()["counts"]["for_you"], 0)
        self.hub.tasks[d].update(accepted=0, updated=T0 - 2 * 86400)
        self.assertEqual(self.hub.snapshot()["counts"]["for_you"], 0)  # older than a day: quiet

    def test_the_snapshot_reads_no_file_and_runs_no_gate(self):
        self.task(1)
        with mock.patch.object(server.Hub, "actions", side_effect=AssertionError("Hub.actions")), \
                mock.patch.object(superagent, "save_state", side_effect=AssertionError("save")), \
                mock.patch.object(superagent, "append_log", side_effect=AssertionError("log")):
            snap = self.hub.snapshot()
        self.assertEqual(snap["counts"]["for_you"], 1)

    def test_a_failing_super_falls_back_to_the_raw_count(self):
        self.task(1)
        self.task(2)
        with mock.patch.object(superagent, "items", side_effect=RuntimeError("boom")):
            snap = self.hub.snapshot()
        self.assertEqual((snap["counts"]["for_you"], snap["super"]["mode"], snap["super"]["for_you"]), (2, "error", 2))
        self.assertEqual(snap["super"]["marks"], {})

    def test_paused_and_off_show_their_mode_and_unranked_line(self):
        self.task(1)
        self.hub.super["paused"] = True
        self.assertEqual(self.hub.snapshot()["super"]["mode"], "paused")
        self.assertIn("paused · oldest first", self.hub.snapshot()["super"]["line"])
        self.hub.super["paused"] = False
        self.hub.cfg["super_day_usd"] = 0
        sup = self.hub.snapshot()["super"]
        self.assertEqual((sup["mode"], sup["line"]), ("off", "off · oldest first"))


class WindowLogTest(SuperHubTest):
    def lines(self):
        return [x["t"] for x in self.hub.super["log"]]

    def test_no_line_on_the_first_tick_then_settled_and_ended_lines(self):
        a = self.task(1)
        b = self.task(2, state="running", why="")
        self.tick(T0)
        self.assertEqual(self.hub.super["log"], [])
        self.hub.tasks[a].update(state="running", why="")  # answered: the item leaves
        self.hub.tasks[b].update(state="done", why="")  # the running task ended
        self.tick(T0 + 5)
        got = self.lines()
        self.assertIn("Task 1: hold settled", got)
        self.assertIn("Task 2 finished", got)
        self.assertEqual({x["g"] for x in self.hub.super["log"]}, {"◇", "✓"})

    def test_a_pass_result_writes_one_sorted_line_and_a_failure_writes_its_error(self):
        self.task(1)
        self.tick(T0)
        self.tick(T0 + 20)
        self.drain()
        self.assertEqual(self.lines()[-1], "Super agent sorted 1 item: 1 for you, 0 later")
        self.answer = lambda prompt: {"out": None, "cost": 0.02, "model": "haiku", "turns": 6,
                                      "error": "the pass failed: error_max_turns", "ms": 9}
        self.task(2)
        self.tick(T0 + 40)
        self.tick(T0 + 60)
        self.drain()
        self.assertEqual(self.lines()[-1], "Super agent sort failed: the pass failed: error_max_turns")

    def test_an_expired_hour_arms_a_back_wake_like_plan_58_s_expired_later(self):
        a = self.task(1)
        self.tick(T0)
        self.tick(T0 + 20)
        self.drain()
        self.hub.super["hand"][self.key(a)] = T0 + 100
        self.tick(T0 + 101)
        self.assertEqual(self.hub.super["back"][self.key(a)], self.hub.super["n"])
        self.assertIn(("back", self.key(a)), self.hub.super_wake["events"])


class TrayCountTest(unittest.TestCase):
    def test_look_reads_for_you_when_the_snapshot_has_it(self):
        self.assertEqual(tray.look({"needs": 5, "for_you": 2, "working": 1}), ("needs", "ContextCompanion: 2 for you, 1 working"))
        self.assertEqual(tray.look({"needs": 0, "for_you": 0, "working": 0}), ("idle", "ContextCompanion: quiet"))
        self.assertEqual(tray.look({"needs": 3, "working": 0})[1], "ContextCompanion: 3 for you")  # an old snapshot
        self.assertEqual(tray.look({"needs": 5, "for_you": 0, "working": 2})[0], "working")  # all in Later: nothing needs Fred now
```

Edits to existing tests in the same commit: `tests/test_tray.py` `LookTest` expectations that say `needs you` read `for you`
(`"1 needs you, 2 working"` becomes `"1 for you, 2 working"`; plural forms collapse because "for you" has no number
agreement); `tests/test_server.py` lines asserting `counts` keep passing (the key is additive).

## 1.2 Code

### `console/superagent.py` (state v2; anchors are plan 58 Task 1's `blank_state` and `load_state`)

```python
STATE_VERSION = 2  # plan 59: v1 is read and upgraded, v2 is written
MESSAGES_MAX = 3
MESSAGE_MAX = 500
HAND_MAX = 200
LOG_MAX = 60


def extra_state() -> dict:
    """The keys plan 59 adds to state.json (README 4.2)."""
    return {"hand": {}, "back": {}, "fwd": [], "looked": None, "looked_cost": None, "log": [], "messages": []}


def upgrade(state: dict, now: float) -> dict:
    """v1 -> v2 in place: add the defaults; Since you looked starts at the oldest seen time, else now."""
    if state.get("v") == 1:
        for key, empty in extra_state().items():
            state.setdefault(key, empty)
        seen = [t for t in (state.get("seen") or {}).values() if _num(t)]
        state["looked"] = min(seen) if seen else float(now)
        state["v"] = 2
    return state


def check_extra(state: dict) -> str:
    """"" for a well-formed v2 tail, else which key is malformed (the strict read of plan 58 R4 covers it)."""
    hand, back, fwd, log, msgs = (state.get(k) for k in ("hand", "back", "fwd", "log", "messages"))
    if not isinstance(hand, dict) or len(hand) > HAND_MAX or any(not isinstance(k, str) or not _num(v) for k, v in hand.items()):
        return "hand is malformed"
    if not isinstance(back, dict) or any(not isinstance(k, str) or not isinstance(v, int) or isinstance(v, bool) for k, v in back.items()):
        return "back is malformed"
    if not isinstance(fwd, list) or any(not isinstance(k, str) for k in fwd):
        return "fwd is malformed"
    if state.get("looked") is not None and not _num(state["looked"]):
        return "looked is malformed"
    if state.get("looked_cost") is not None and not (_num(state["looked_cost"]) and state["looked_cost"] >= 0):
        return "looked_cost is malformed"
    if not isinstance(log, list) or len(log) > LOG_MAX or any(
            not isinstance(x, dict) or not _num(x.get("ts")) or not all(isinstance(x.get(f), str) for f in ("g", "t", "p")) for x in log):
        return "log is malformed"
    if not isinstance(msgs, list) or len(msgs) > MESSAGES_MAX or any(
            not isinstance(m, dict) or not isinstance(m.get("id"), str) or not _num(m.get("ts"))
            or not isinstance(m.get("text"), str) or len(m["text"]) > MESSAGE_MAX for m in msgs):
        return "messages is malformed"
    return ""
```

`blank_state()`: `"v": 2` and `**extra_state()`. `load_state`: where it rejects an unsupported `v`, accept `(1, 2)`;
after its existing key checks add `state = upgrade(state, time.time()); error = check_extra(state)` and return that
error through the same path plan 58 uses for a malformed key (blocks passes, raw queue, Pause not reset). A v1 file is
not rewritten until the next save.

### `console/superwin.py`

```python
"""Plan 59: the data behind the super agent window. Pure: no files, no threads, no HTTP; Hub and Handler call it.
It reads plan 58's items, state and queue (console/superagent.py) and adds Fred's Later, the log behind Since you
looked, the one count, the mode, the controls and the row line. It imports neither server nor supervisor."""
import hashlib
import json
import math
import time

from . import redact, superagent

HAND_LATER_S = 3600     # Later by hand is one fixed hour (Fred, 2026-11-08)
HAND_MAX = superagent.HAND_MAX
HAND_WHY = "You put it later."
LOG_MAX = superagent.LOG_MAX
LOG_AGE_S = 7 * 86400
LOG_TEXT = 160
MESSAGES_MAX = superagent.MESSAGES_MAX
MESSAGE_MAX = superagent.MESSAGE_MAX
MODES = ("ranked", "partial", "sorting", "paused", "off", "capped", "failed", "waiting", "error")


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _local(ts) -> str:
    return time.strftime("%Y-%m-%dT%H:%M", time.localtime(ts))


def hm(ts) -> str:
    return time.strftime("%H:%M", time.localtime(ts)) if _num(ts) and ts > 0 else ""


# -- the accept item (D10 a) ---------------------------------------------------------------------------------------

ACCEPT_WINDOW_S = 24 * 3600   # a finished task asks for Accept for a day, then goes quiet


def accept_items(snap: dict, by_id: dict, now: float) -> list:
    """Items for finished tasks that wait for Accept (README 4.1a), in the shape of superagent.items: state done, not
    accepted, not a chat, not already a `needs` row (a pending supervisor card keeps its own item), finished within a
    day. The key's event hashes the task id, the step count, the last verify's verdict and the attempt count."""
    out = []
    for row in snap["tasks"]:
        t = by_id.get(row["id"])
        if (t is None or t.get("chat") or t.get("state") != "done" or t.get("accepted") or row["group"] == "needs"
                or now - float(t.get("updated") or 0) > ACCEPT_WINDOW_S):
            continue
        verify = [s for s in t["steps"] if s["kind"] == "verify" and s["state"] == "done"]
        verdict = (verify[-1].get("verdict") or "") if verify else ""
        attempts = sum(len(s.get("attempts") or []) for s in t["steps"])
        event = superagent._event(["accept", t["id"], len(t["steps"]), verdict, attempts])  # [58 T2] private helper
        out.append({"key": f"task:{t['id']}:{event}", "type": "task", "id": t["id"], "kind": "accept", "always": "",
                    "project": row["project"], "project_dir": row["project_dir"], "title": row["title"], "label": row["label"]})
    return out


# -- Later by hand, Bring back ------------------------------------------------------------------------------------

def stay_reason(item: dict, now: float) -> str:
    """Why an item has no Later ("" for none): code's always-forward reason, or a decision whose default is about to be
    taken at `auto` (plan 58 R1). The page draws this string; it never derives it."""
    if item.get("always"):
        return item["always"]
    if item.get("left_s") is not None and item.get("default"):
        return f"the default is taken at {hm(now + item['left_s'])}"
    return ""


def put_later(state: dict, keys, live: list, now: float) -> tuple:
    """Fred's Later: one fixed hour. Returns (done keys, {key: reason}). An item that stays here (stay_reason) is
    refused; the hand is capped."""
    by_key = {i["key"]: i for i in live}
    done, refused = [], {}
    for key in keys:
        found = by_key.get(key)
        if found is None:
            refused[key] = "unknown item"
        elif stay_reason(found, now):
            refused[key] = "stays here: " + stay_reason(found, now)
        elif key not in state["hand"] and len(state["hand"]) >= HAND_MAX:
            refused[key] = "Later is full: bring some back"
        else:
            state["hand"][key] = float(now) + HAND_LATER_S
            state["back"].pop(key, None)
            if key in state["fwd"]:
                state["fwd"].remove(key)
            done.append(key)
    return done, refused


def bring_back(state: dict, keys, live: list) -> tuple:
    """Bring back from either Later. The key joins `fwd` (no pass sends it away again) and carries `back` until a later
    pass has finished. Returns (done keys, {key: reason})."""
    by_key = {i["key"] for i in live}
    done, refused = [], {}
    for key in keys:
        ann = state["ann"].get(key)
        if key not in by_key:
            refused[key] = "unknown item"
        elif key in state["hand"]:
            del state["hand"][key]
        elif isinstance(ann, dict) and ann.get("do") == "later":
            ann.update(do="forward", until=None)
        else:
            refused[key] = "not in Later"
            continue
        state["back"][key] = state.get("n", 0)
        if key not in state["fwd"]:
            state["fwd"].append(key)
        done.append(key)
    return done, refused


def sync(state: dict, live: list, now: float) -> tuple:
    """The tick's housekeeping for the v2 keys. A hand entry whose hour passed returns once (`back`); departed keys
    are forgotten; a back marker clears when a pass later than it has finished. Returns (back keys, changed)."""
    keys = {i["key"] for i in live}
    returned, changed = [], False
    for key in list(state["hand"]):
        if key not in keys:
            del state["hand"][key]
            changed = True
        elif state["hand"][key] <= now:
            del state["hand"][key]
            state["back"][key] = state.get("n", 0)
            returned.append(key)
            changed = True
    last = state.get("last") if isinstance(state.get("last"), dict) else {}
    done_n = last.get("n") if last.get("ok") and isinstance(last.get("n"), int) else 0
    for key in list(state["back"]):
        if key not in keys or done_n > state["back"][key]:
            del state["back"][key]
            changed = True
    fwd = [k for k in state["fwd"] if k in keys]
    if fwd != state["fwd"]:
        state["fwd"] = fwd
        changed = True
    return returned, changed


# -- the window queue and its one count ---------------------------------------------------------------------------

def queue(live: list, state: dict, now: float, ranked: bool) -> dict:
    """superagent.queue with Fred's hour taken out first and Bring back kept forward. {"queue": [card], "later": [item]};
    every live item sits in exactly one of them. Items gain `back`; a later item gains `by` (sa or you)."""
    hand = {k: u for k, u in state["hand"].items() if u > now}
    mine = [i for i in live if i["key"] in hand and not stay_reason(i, now)]  # an item that must stay comes back even inside its hour
    mine_keys = {i["key"] for i in mine}
    fwd = set(state["fwd"])
    ann = {k: (dict(a, do="forward", until=None) if k in fwd and a.get("do") == "later" else a) for k, a in state["ann"].items()}
    out = superagent.queue([i for i in live if i["key"] not in mine_keys], dict(state, ann=ann), now, ranked)
    back = set(state["back"])
    cards = []
    for card in out["queue"]:
        items = [dict(i, back=i["key"] in back or bool((state["ann"].get(i["key"]) or {}).get("back"))) for i in card["items"]]
        cards.append(dict(card, items=items))
    later = [dict(i, by="sa") for i in out["later"]]
    seen = state["seen"]
    for i in mine:
        first = seen.get(i["key"])
        later.append(dict(i, by="you", do="later", rank=0, say="", why=HAND_WHY, batch="", until=_local(hand[i["key"]]),
                          new=False, back=False, age_s=max(0, int(now - first)) if _num(first) else 0))
    later.sort(key=lambda i: (i.get("until") or "", i["key"]))
    return {"queue": cards, "later": later}


def counts(cards: list, later: list) -> dict:
    """The one number is `queue`: the items inside the cards (a batch counts each member)."""
    items = [i for c in cards for i in c["items"]]
    return {"queue": len(items), "later": len(later), "always": sum(1 for i in items if i.get("always")),
            "new": sum(1 for i in items if i.get("new"))}


def by_project(cards: list) -> dict:
    out = {}
    for card in cards:
        for i in card["items"]:
            out[i["project_dir"]] = out.get(i["project_dir"], 0) + 1
    return out


def marks(cards: list, later: list) -> dict:
    """Task or session id -> ["queue"] or ["later", "HH:MM"]: what the list rows need, nothing more."""
    out = {i["id"]: ["queue"] for c in cards for i in c["items"]}
    out.update({i["id"]: ["later", (i.get("until") or "")[-5:]] for i in later})
    return out


def rev(live: list, state: dict, mode: str, ranked: bool, now: float) -> str:
    """12 hex over the live keys with their stored advice, Fred's hour, the back markers, the mode and the log tail.
    It never moves with age, cost, time left or evidence the cheap path cannot read, so the snapshot and the full view
    compute the same value from the same live set."""
    last = state.get("last") if isinstance(state.get("last"), dict) else {}
    log = state.get("log") or []
    ann, hand, back, fwd = state["ann"], state["hand"], state["back"], set(state["fwd"])
    rows = []
    for key in sorted(i["key"] for i in live):
        a = ann.get(key) if isinstance(ann.get(key), dict) else {}
        rows.append([key, a.get("do", ""), a.get("rank", 0), a.get("say", ""), a.get("why", ""),
                     a.get("do") == "later" and _num(a.get("until")) and a["until"] > now,
                     _num(hand.get(key)) and hand[key] > now, key in back or bool(a.get("back")), key in fwd])
    basis = [mode, bool(ranked), last.get("n"), bool(state.get("paused")), state.get("looked"), log[-1]["ts"] if log else 0, rows]
    return hashlib.sha256(json.dumps(basis, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


# -- the mode, the controls, the row line --------------------------------------------------------------------------

def mode(*, error: str, paused: bool, off: bool, capped: bool, sorting: bool, last, never_reviewed: int) -> str:
    """README 4.10, first that holds."""
    if error:
        return "error"
    if paused:
        return "paused"
    if off:
        return "off"
    if capped:
        return "capped"
    if sorting:
        return "sorting"
    if last is None:
        return "waiting"
    if not last.get("ok"):
        return "failed"
    return "partial" if never_reviewed else "ranked"


_SORT_OFF = {"paused": "Resume first", "sorting": "A sort is running", "off": "The super agent is not sorting today",
             "capped": "The super agent is not sorting today", "error": "The super agent cannot sort: see the note"}


def controls(mode_: str) -> dict:
    """The bar's Pause, Resume and Sort, each {label, off} or None; the page draws them and decides nothing."""
    label = "Sorting" if mode_ == "sorting" else "Sort again" if mode_ == "failed" else "Sort now"
    return {"pause": None if mode_ in ("paused", "off", "capped", "error") else {"label": "Pause", "off": ""},
            "resume": {"label": "Resume", "off": ""} if mode_ == "paused" else None,
            "sort": {"label": label, "off": _SORT_OFF.get(mode_, "")}}


def row_line(mode_: str, *, running: int, later: int, last_hm: str, sorting_n: int, reviewed: int, live: int) -> str:
    return {"ranked": f"{running} running · {later} later · sorted {last_hm}",
            "waiting": f"waiting to sort · {running} running",
            "sorting": f"sorting {sorting_n} {'item' if sorting_n == 1 else 'items'} · {running} running",
            "partial": f"reviewed {reviewed} of {live} · {running} running",
            "paused": f"paused · oldest first · {running} running",
            "off": "off · oldest first", "capped": "today's limit reached · oldest first",
            "failed": "last sort failed · oldest first", "error": "cannot sort · oldest first"}[mode_]


# -- Since you looked, messages ------------------------------------------------------------------------------------

def kind_word(kind: str) -> str:
    return {"hand_off": "hand-off hint", "failed_twice": "failed twice"}.get(kind, kind.replace("_", " "))


def note(state: dict, now: float, g: str, text: str, project: str = "") -> None:
    """One line of the log: masked, clipped, newest last, at most LOG_MAX lines, none older than 7 days."""
    line = {"ts": float(now), "g": g, "t": redact.clip(redact.mask(str(text)), LOG_TEXT),
            "p": redact.clip(redact.mask(str(project)), 80)}
    state["log"] = ([x for x in state["log"] if now - x["ts"] <= LOG_AGE_S] + [line])[-LOG_MAX:]


def since(state: dict, now: float) -> dict:
    """The lines after `looked`, newest first. `looked` None (never marked) lists the whole log."""
    looked = state.get("looked")
    lines = [dict(x, tm=hm(x["ts"])) for x in reversed(state["log"]) if not _num(looked) or x["ts"] > looked]
    return {"at": looked, "lines": lines}


def mark_seen(state: dict, now: float, cost_total: float) -> None:
    state["looked"], state["looked_cost"] = float(now), float(cost_total)


def spent_since(state: dict, cost_total: float) -> float:
    """The tasks' spend since the mark; 0 when never marked or when tasks were deleted since."""
    base = state.get("looked_cost")
    return round(max(0.0, float(cost_total) - base), 4) if _num(base) else 0.0


def add_message(state: dict, text, now: float, mid: str) -> dict:
    raw = str(text or "").strip()
    if not raw or len(raw) > MESSAGE_MAX:  # Fred's words are refused, never cut silently
        raise ValueError(f"message must contain 1 to {MESSAGE_MAX} characters")
    if len(state["messages"]) >= MESSAGES_MAX:
        raise ValueError(f"{MESSAGES_MAX} messages wait for the next sort")
    message = {"id": mid, "ts": float(now), "text": redact.clip(redact.mask(raw), MESSAGE_MAX)}
    state["messages"].append(message)
    return message


def drop_messages(state: dict, ids) -> None:
    gone = set(ids)
    state["messages"] = [m for m in state["messages"] if m["id"] not in gone]
```

### `console/tray.py`

```python
def look(counts: dict) -> tuple:
    """(kind, tooltip) from the snapshot's group counts. plan 59: `for_you` is what reaches Fred; an older snapshot
    without it falls back to the raw needs."""
    needs, working = counts.get("for_you", counts.get("needs", 0)), counts.get("working", 0)
    parts = [f"{needs} for you"] if needs else []
    if working:
        parts.append(f"{working} working")
    kind = "needs" if needs else "working" if working else "idle"
    return kind, f"{window.TITLE}: " + (", ".join(parts) or "quiet")
```

### `console/server.py`

Imports: add `superwin` beside `superagent`. Insert the methods beside plan 58's `_super_*` section.

```python
    def _super_live(self, snap: dict, now: float) -> list:
        """The live items: plan 58's needs set plus the accept items (D10 a). Every plan 58 call of
        `superagent.items(snap, self.tasks)` (tick, window, view, admission) becomes this one call. D10 b: drop the
        second term."""
        return superagent.items(snap, self.tasks) + superwin.accept_items(snap, self.tasks, now)

    def _super_window(self, snap: dict, described=None) -> dict:
        """The window's data from one snapshot: the live items, the queue, the one count, the mode and the row line.
        `described` is the full list of super_view's described items; without it the items are described cheaply
        (superagent.describe with view={}: pure, no Hub.actions, no brief or file read). Same `rev` either way."""
        now, inp, st = self.super_clock(), self._super_inputs(), self.super
        live = described
        if live is None:
            timeout, rows = self.cfg["decision_timeout_s"], {r["id"]: r for r in [*snap["tasks"], *snap["sessions"]]}
            live = []
            for i in self._super_live(snap, now):
                task = self.tasks.get(i["id"]) if i["type"] == "task" else None
                level = supervisor.policy(self.cfg, task, now)["mode"] if task else ""
                live.append(superagent.describe(i, task, rows.get(i["id"], {}), {}, level, timeout, now))
        out = superwin.queue(live, st, now, inp["ranked"])
        cards, later = out["queue"], out["later"]
        n = superwin.counts(cards, later)
        reviewed = sum(1 for i in live if i["key"] in st["reviewed"])
        mode = superwin.mode(error=inp["error"], paused=bool(st["paused"]), off=inp["off"], capped=inp["capped"],
                             sorting=inp["sorting"] is not None, last=st["last"], never_reviewed=inp["never_reviewed"])
        running = sum(1 for t in snap["tasks"] if t["group"] == "working")
        line = superwin.row_line(mode, running=running, later=n["later"], last_hm=superwin.hm(superagent.last_at(st)),
                                 sorting_n=(inp["sorting"] or {}).get("items", 0), reviewed=reviewed, live=len(live))
        return {"cards": cards, "later": later, "counts": n, "mode": mode, "line": line, "live": live,
                "by_project": superwin.by_project(cards), "marks": superwin.marks(cards, later),
                "rev": superwin.rev(live, st, mode, inp["ranked"], now), "inputs": inp, "now": now}

    def _super_summary(self, snap: dict) -> dict:
        """snap["super"]: what the header, the tray, the row and the list read. Falls back to the raw needs count."""
        try:
            with self.tlock:
                w = self._super_window(snap)
            return {"rev": w["rev"], "mode": w["mode"], "for_you": w["counts"]["queue"], "later": w["counts"]["later"],
                    "line": w["line"], "by_project": w["by_project"], "marks": w["marks"], "error": ""}
        except Exception as exc:  # the count must never drop below what needs Fred
            per = {}
            for r in [*snap["tasks"], *snap["sessions"]]:
                if r["group"] == "needs" and not r.get("task") and not r.get("chat_task"):
                    per[r["project_dir"]] = per.get(r["project_dir"], 0) + 1
            return {"rev": "", "mode": "error", "for_you": snap["counts"]["needs"], "later": 0, "line": "cannot sort · oldest first",
                    "by_project": per, "marks": {}, "error": redact.clip(redact.mask(f"{type(exc).__name__}: {exc}"), 200)}
```

`snapshot()`: after the `with self.lock:` block and before `return snap`, anchored on the line
`        snap["spend"]["fills"] = self.fill_marks()  # outside the lock: budget() takes it`:

```python
        snap["super"] = self._super_summary(snap)  # plan 59: outside self.lock, under tlock (tlock is taken first)
        snap["counts"]["for_you"] = snap["super"]["for_you"]
```

The fallback's task-row query uses `snap["tasks"]` rows (group `needs`), so a task row and a session row count once,
as `counts.needs` does. `test_a_failing_super_falls_back_to_the_raw_count` pins it.

The tick (plan 58 Task 5, `_super_tick`): after `live = superagent.items(...)` and `superagent.sync(...)`, add

```python
            back, moved = superwin.sync(self.super, live, now)
            events += [("back", key) for key in back]  # the same wake as plan 58's expired Later
            logged = self._super_log_changes(live, ended, now)
            if moved or logged:
                self._super_save_required()  # plan 58's required-save path (a failure blocks admission)
```

(`events`, `ended` and the save call are plan 58's own names for the tick's event list, the tasks that ended since the
last tick and its required save; bind them at step 0.) And the log writer:

```python
    def _super_log_changes(self, live: list, ended: list, now: float) -> bool:
        """Since you looked: a line for each task that ended and each key that left the live set. Not on the first tick."""
        prev, self._super_prev = getattr(self, "_super_prev", None), {i["key"]: i for i in live}
        if prev is None:
            return False
        before = len(self.super["log"])
        for task in ended:
            state, title = task["state"], task["title"]
            if state == "done":
                superwin.note(self.super, now, "✓", f"{title} finished", task["project"])
            elif state == "stuck":
                superwin.note(self.super, now, "✕", f"{title} is stuck: {task['why']}", task["project"])
            else:
                superwin.note(self.super, now, "·", f"{title} {state}", task["project"])
        for key, gone in prev.items():
            if key not in self._super_prev:
                superwin.note(self.super, now, "◇", f"{gone['title']}: {superwin.kind_word(gone['kind'])} settled", gone["project"])
        return len(self.super["log"]) != before
```

The pass result (plan 58 Task 5 publication step, after the final state is built and before it is saved): on ok,
`w = self._super_window(self.snapshot())` is not needed; use the counts already computed for the new annotations:

```python
        n = superwin.counts(*(lambda o: (o["queue"], o["later"]))(superwin.queue(live, self.super, now, True)))
        superwin.note(self.super, now, "◆", f"Super agent sorted {last['items']} item{'' if last['items'] == 1 else 's'}: {n['queue']} for you, {n['later']} later", "All projects")
```

and on a failed result `superwin.note(self.super, now, "✕", f"Super agent sort failed: {last['error']}", "All projects")`.

`super_view` (plan 58 Task 6): replace its call `superagent.queue(items_, state, now, ranked)` by
`superwin.queue(items_, state, now, ranked)`; its `counts` by `superwin.counts(...)` (which keeps plan 58's four keys);
add `rev` (`superwin.rev(described, state, mode, ranked, now)`) and `by_project`. Task 2 adds the card fields.

## 1.3 Steps and acceptance

- [ ] 0. Bind `Hub._super_inputs` (section 1.0). `grep -n "superagent.items(" console/server.py` and replace each plan 58
      call by `self._super_live(snap, now)` (D10 a).
- [ ] 1. Write the tests; run `py -m unittest tests.test_superwin tests.test_superwin_server`: red for the missing module,
      state keys and Hub methods.
- [ ] 2. Make the 1.2 edits. Focused tests green; `tests.test_superagent`, `tests.test_superagent_server`,
      `tests.test_tray`, `tests.test_server` green.
- [ ] 3. Full suite green (report the count). `git diff --stat` shows only the files above. Stage the new files by path
      and only this task's hunks of `console/server.py` and `console/superagent.py`. Commit with the message above.
