# Task 6: the thread in the window

> Contract: [README.md](README.md) 3.7 and the design's section 7. Builds after plan 59's web tasks are merged and
> after Fred locks the mock of 6.2. Part 6.1 (server) may build as soon as plan 59 Task 3 is merged.

**Files**
- Modify: `console/chattools.py` (`later`, `bring_back`, the `key` of `_item`)
- Modify: `console/superchat.py` (`ACTIONS`, `ACTIONS_TEXT`)
- Modify: `console/server.py` (`chat_action`, `Hub._chat_save_order`; stage only this task's hunks)
- Create (design session): `design/rework/explored/g-super-agent-chat.html`; after Fred's lock,
  `design/rework/locked/super-agent-chat.html`
- Modify (after the lock): `web/app.js`, `web/style.css`
- Modify: `tests/test_chattools.py`, `tests/test_superchat.py`

Commit boundaries: `feat: chat Later, Bring back and Save order (plan 61 T6a)`; the mock's own design commit; `feat:
the super agent thread in the window (plan 61 T6b)`.

## 6.1 Server (T6a)

`console/chattools.py`: `_item` gains `"key": i.get("key")`; two tools join `TOOLS` (and `FUNCS`):

```python
    {"name": "later", "annotations": WRITE,
     "inputSchema": _schema({"keys": {"type": "array", "maxItems": 20, "items": {"type": "string"}}}, ["keys"]),
     "description": "Put For you items later for one hour, by their keys from overview."},
    {"name": "bring_back", "annotations": WRITE,
     "inputSchema": _schema({"keys": {"type": "array", "maxItems": 20, "items": {"type": "string"}}}, ["keys"]),
     "description": "Bring items back from Later into For you, by their keys from overview."},
```

```python
def _super_write(hub, action, keys):
    status, body = hub.super_action({"action": action, "keys": keys})  # plan 59 Task 3: Fred's own Later
    if status != 200:
        raise ToolError(body.get("error") or f"status {status}")
    return {"outcome": "done", "done": body.get("done", keys)}


def later(hub, turn, args):
    return _super_write(hub, "later", args["keys"])


def bring_back(hub, turn, args):
    return _super_write(hub, "bring_back", args["keys"])
```

`console/superchat.py`: `ACTIONS` gains `"save_order": ({"action", "card"}, set())` and `ACTIONS_TEXT` reads
`"action: send, stop, new, confirm, cancel, save_order, dismiss or undo"`.

`console/server.py`: `chat_action` gains, before the `dismiss` line, `if action == "save_order": return
self._chat_save_order(body["card"])`, and a method after `_chat_card_press`:

```python
    def _chat_save_order(self, card_id):
        """Fred's Save of an order card: one line appended to orders.md through plan 59's POST /api/super orders."""
        with self.chat_lock:
            card = next((c for c in self.chat_thread["cards"] if c.get("id") == card_id), None)
            if card is None or card["state"] != "open" or card["type"] != "order":
                return 404, {"error": "no open order card " + str(card_id)[:20]}
            card["state"] = "pressing"
        path = superagent.folder(self.folder) / superagent.ORDERS_FILE
        try:
            current = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = superagent.ORDERS_SEED
        except (OSError, UnicodeError) as exc:
            current, error = None, "orders.md cannot be read: " + superagent._clip(exc, 200)
        if current is None:
            status, body = 503, {"error": error}
        else:
            status, body = self.super_action({"action": "orders",
                                              "text": current.rstrip("\n") + "\n" + card["text"] + "\n"})
        with self.chat_lock:
            card.update(state="done" if status == 200 else "open", why="" if status == 200 else body.get("error", ""))
            try:
                superchat.save(self.folder, self.chat_thread)
            except OSError:
                pass
        self._chat_changed()
        return status, {"card": card_id, "state": card["state"], "error": body.get("error", "")}
```

Tests: `test_chattools.ChatToolsTest.test_later_and_bring_back` (`super_action` patched: the bodies sent are `{action:
"later", keys: [k]}` and `{action: "bring_back", keys: [k]}`; a 409 becomes the tool's error text);
`test_superchat.ChatRouteTest.test_save_order` (a `propose_order` turn, then POST `{action: "save_order", card}`:
`orders.md` keeps its two seed comment lines and ends with the order; the card is `done`; a second save is 404).

## 6.2 The mock (a design session, before any web code)

An explored copy of `design/rework/locked/super-agent.html` as `design/rework/explored/g-super-agent-chat.html`, made
with the impeccable rules of `design/rework/` and the locked tokens, showing:

1. The super agent page with a **Thread** section after For you: Fred's lines, a streamed reply, tool steps folded
   into `3 steps` (open: `Read "gauge fix"`, `Pressed retry on "gauge fix" (opus)`), task titles as chips that open the
   task.
2. A **Confirm card** (the action, the task, why it needs Fred, Confirm and Cancel) and its **Out of date** state.
3. A **Save order** card and a **Prep** card (Prep started for a project, Open the composer).
4. **Act lines** in the thread and in Since you looked, with Undo (Resume after Pause, Stop after a start or retry)
   and, after Accept, Reopen (which opens the card's Reopen form); a background act's line marked as the super
   agent's.
5. An **uncertain** act with Dismiss.
6. The **box chip** toggling between a page's own target (Task, Answer, New work) and `◆ Super agent`; off its
   page, a one-line reply over the box with Open thread.
7. The bar with **Stop** while a turn runs and **New chat**; the chip's off state `chat off for today`.
8. 900, 400 and 340 px; dark and light; reduced motion (the streamed text appears without motion).

Fred locks it (the file moves to `design/rework/locked/super-agent-chat.html` with his note), or asks for changes.
No web code before the lock.

## 6.3 The web (T6b, after the lock)

Requirements the code meets; this file is refreshed with the final code from the locked mock before T6b starts (the
same session that builds it, which re-reads plan 59's shipped `web/app.js`):

- Data: `GET /api/super/chat` when `snap.chat.rev` changes (and once when the page opens); writes only through `POST
  /api/super/chat` (send, stop, new, confirm, cancel, save_order, dismiss, undo). Nothing else is written.
- The Thread section goes into plan 59's `swPage` after For you, through its `sect(...)` helper.
- `swTarget` gains the kind `sa` (plan 59 does not build it; README 59 amendment): Enter sends `{action: "send",
  text, page, selected}` where `page` is the current page's name and `selected` the selected task or run id. A
  `409` shows its `error` in the box's line; `off` disables the box with its reason.
- Confirm, Cancel, Save, Dismiss and Undo buttons act only on a trusted event (`event.isTrusted`), click or key, so no
  script on the page presses them. A Confirm card whose POST answers `out_of_date` shows Out of date with Open the
  task.
- An interrupted turn shows Interrupted with Ask again (sends the same text again).
- Every string from the server goes through `esc`; no `innerHTML` of raw text.
- Styles in `web/style.css`, tokens first, from the locked mock.

Checks: `node --check web/app.js`; headless Edge at 900, 400 and 340 px, dark and light, reduced motion, with a
scratch service (`py -m console --serve` on a free port with a scratch `CC_CONSOLE_HOME`, the fake claude as
`claude_exe`); screenshots kept in the plan's folder.

## 6.4 Steps

- [ ] 1. T6a: write the 6.1 tests (red), make the edits (green), full suite green; commit.
- [ ] 2. Design session: the mock of 6.2; Fred reviews; lock or change.
- [ ] 3. Refresh 6.3 of this file with the final code from the locked mock; Fred reads it.
- [ ] 4. T6b: build, check, full suite green; commit.
