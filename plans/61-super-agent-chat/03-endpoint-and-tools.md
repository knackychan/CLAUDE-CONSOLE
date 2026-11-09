# Task 3: the MCP endpoint and the tools

> Contract: [README.md](README.md) 3.3, 3.4. The endpoint is the only door of the chat's tools; it is reachable only
> with a live turn's token, so before Task 4 only tests register one.

**Files**
- Create: `console/mcp.py`, `console/chattools.py`
- Modify: `console/guard.py` (`mcp_ok`)
- Modify: `console/superchat.py` (part 1: the thread file)
- Modify: `console/server.py` (imports, `Hub.__init__` chat fields, `Hub.chat_card`, `make_server` sets `hub.port`,
  `do_POST` and `do_GET` lines, `Handler._mcp`; stage only this task's hunks)
- Create: `tests/test_mcp.py`, `tests/test_chattools.py`

Commit boundary: `feat: the Console MCP endpoint and the chat's tools (plan 61 T3)`.

## 3.1 `console/mcp.py`

```python
"""Plan 61: a stateless MCP endpoint (README 3.3): JSON-RPC 2.0 over POST, JSON answers only, tools only. Pure:
the Handler passes one parsed message, the tool list and a call function."""
from . import redact

VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")  # newest first; an unknown ask gets the first
PART_MAX = 40_000  # the CLI moves a longer text part to a file (sticker-generator-simple)
TOTAL_MAX = 160_000
TYPES = {"string": str, "integer": int, "boolean": bool, "array": list, "object": dict}


def error(id_, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _ok(id_, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def check_args(schema: dict, args) -> str:
    """"" when `args` fits the tool's schema (the keywords chattools uses), else the first reason."""
    if not isinstance(args, dict):
        return "arguments must be an object"
    props = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in args:
            return f"{key} is required"
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            return f"unknown argument {str(key)[:40]}"
        kind = TYPES[spec["type"]]
        if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
            return f"{key} must be {spec['type']}"
        if "enum" in spec and value not in spec["enum"]:
            return f"{key}: one of " + ", ".join(map(str, spec["enum"]))
        if isinstance(value, str) and len(value) > spec.get("maxLength", 10 ** 9):
            return f"{key}: at most {spec['maxLength']} characters"
        if kind is int and value < spec.get("minimum", value):
            return f"{key}: at least {spec['minimum']}"
        if kind is list:
            if len(value) > spec.get("maxItems", 10 ** 9):
                return f"{key}: at most {spec['maxItems']} entries"
            if any(not isinstance(v, str) or len(v) > 200 for v in value):
                return f"{key}: a list of short texts"
    return ""


def result(text: str, is_error: bool = False) -> dict:
    """A tools/call result: masked, cut at TOTAL_MAX, split into text parts of at most PART_MAX."""
    text = redact.mask(text)
    if len(text) > TOTAL_MAX:
        text = text[:TOTAL_MAX] + f"\n[cut: {len(text) - TOTAL_MAX} more characters]"
    parts = [text[i:i + PART_MAX] for i in range(0, len(text), PART_MAX)] or [""]
    return {"content": [{"type": "text", "text": p} for p in parts], "isError": bool(is_error)}


def handle(msg, tools: list, call):
    """The answer to one message, or None for a notification. `call(name, args)` returns (text, is_error)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    if "id" not in msg:
        return None
    id_, method, params = msg["id"], msg["method"], msg.get("params") or {}
    if not isinstance(params, dict):
        return error(id_, -32602, "params must be an object")
    if method == "initialize":
        asked = params.get("protocolVersion")
        return _ok(id_, {"protocolVersion": asked if asked in VERSIONS else VERSIONS[0],
                         "capabilities": {"tools": {"listChanged": False}},
                         "serverInfo": {"name": "console", "version": "61"},
                         "instructions": "Claude Console's own tools: read the tasks, press their card actions."})
    if method == "ping":
        return _ok(id_, {})
    if method == "tools/list":
        return _ok(id_, {"tools": [{k: t[k] for k in ("name", "description", "inputSchema", "annotations")}
                                   for t in tools]})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        tool = next((t for t in tools if t["name"] == name), None)
        if tool is None:
            return error(id_, -32602, "Unknown tool: " + str(name)[:60])
        why = check_args(tool["inputSchema"], args)
        if why:
            return _ok(id_, result(why, True))
        try:
            text, is_error = call(name, args)
        except Exception as exc:  # a bug in one tool answers that tool's error, never a dead endpoint
            text, is_error = "tool failed: " + redact.clip(str(exc), 300), True
        return _ok(id_, result(text, is_error))
    return error(id_, -32601, "Method not found")
```

## 3.2 `console/guard.py`

```python
import hmac


def mcp_ok(headers, tokens: dict) -> str:
    """POST /api/mcp (plan 61): the turn whose Bearer token this is; "" for a missing, wrong or stale token."""
    auth = headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return ""
    given = auth[7:].strip().encode("utf-8")
    for token, turn in list(tokens.items()):
        if hmac.compare_digest(given, token.encode("utf-8")):
            return turn
    return ""
```

(`import hmac` at the top of the module.)

## 3.3 `console/superchat.py`, part 1: the thread file

Add after part 0 (and `import json, os` plus `from . import paths, redact, superagent` at the top):

```python
FOLDER, THREAD_FILE, OLD_FILE = "chat", "thread.json", "thread.1.json"
KEEP = 200  # turns and cards kept in thread.json; the session keeps its own memory


def folder(home):
    return superagent.folder(home) / FOLDER


def blank() -> dict:
    return {"v": 1, "session": "", "prompt_hash": "", "model": "", "tokens": 0, "turns": [], "cards": []}


def load(home) -> dict:
    """The thread; a missing file is a blank thread; an unreadable one is a blank thread with `error` (sending waits
    for New chat, which keeps the file as thread.1.json)."""
    try:
        data = json.loads((folder(home) / THREAD_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return blank()
    except (OSError, ValueError, UnicodeError) as exc:
        return dict(blank(), error="thread.json is unreadable: " + redact.clip(redact.mask(str(exc)), 200))
    if not isinstance(data, dict) or data.get("v") != 1 or not isinstance(data.get("turns"), list) \
            or not isinstance(data.get("cards"), list) or not isinstance(data.get("session"), str):
        return dict(blank(), error="thread.json has an unknown shape")
    return dict(blank(), **data)


def save(home, thread: dict) -> None:
    """Whole-file replacement (plan 54); raises OSError."""
    data = {k: v for k, v in thread.items() if k != "error"}
    data["turns"], data["cards"] = data["turns"][-KEEP:], data["cards"][-KEEP:]
    path = folder(home) / THREAD_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=1))


def rotate(home) -> None:
    """New chat: thread.json becomes thread.1.json (the older copy replaced)."""
    try:
        os.replace(folder(home) / THREAD_FILE, folder(home) / OLD_FILE)
    except FileNotFoundError:
        pass
```

## 3.4 `console/chattools.py`

```python
"""Plan 61: the chat's Console tools (README 3.4). Each reads the Hub or presses through Hub.super_act; a card for
the user goes to the thread through Hub.chat_card. Every answer is JSON text; mcp.result masks and splits it."""
import json
import os
import time
import uuid

from . import redact, superact, supervisor, tasks

READ = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}
TASK = {"type": "string", "maxLength": 64, "description": "a task id from overview"}
TEXT = {"type": "string", "maxLength": 1000}
GOAL_MAX, HANDOFF_MAX, READ_MAX = 1500, 4000, 30000
RESUME_TEXT = "You were interrupted. Check `git diff` first, then finish the task."


class ToolError(Exception):
    """A refusal the model reads: the tool answers isError with this text."""


def _schema(props=None, required=()):
    return {"type": "object", "additionalProperties": False, "properties": props or {}, "required": list(required)}


TOOLS = [
    {"name": "overview", "annotations": READ, "inputSchema": _schema(),
     "description": "Every task now: its state line, level, current step and model, cost and the ids of its enabled "
                    "actions; what waits for the user in the super agent's order with its say lines; Later; Console "
                    "runs that need the user; the chat's spend today; the latest acts."},
    {"name": "task", "annotations": READ, "inputSchema": _schema({"task": TASK}, ["task"]),
     "description": "One task: goal, steps, last handoff, its card's actions (id, label, off reason, confirm, form "
                    "arguments) and its message box (mode, why it is closed, when words arrive)."},
    {"name": "read", "annotations": READ,
     "inputSchema": _schema({"task": TASK, "what": {"type": "string", "enum": ["plan", "handoff", "note", "brief"]},
                             "step": {"type": "integer", "minimum": 1}}, ["task", "what"]),
     "description": "A task's file: its plan, its handoff, or one step's note or brief (default: the last good step)."},
    {"name": "usage", "annotations": READ, "inputSchema": _schema(),
     "description": "Model fills, pace and limits; the chat's and the passes' spend today."},
    {"name": "act", "annotations": WRITE,
     "inputSchema": _schema({"task": TASK, "action": {"type": "string", "maxLength": 40},
                             "model": {"type": "string", "enum": list(superact.MODELS)},
                             "note": {"type": "string", "maxLength": superact.TEXT_MAX},
                             "text": {"type": "string", "maxLength": superact.TEXT_MAX},
                             "kind": {"type": "string", "enum": list(tasks.NEXT_KINDS)},
                             "follow_up": {"type": "boolean"}}, ["task", "action"]),
     "description": "Press one action of a task's card by its id (from task or overview); forms take their own "
                    "arguments. Answers done, refused with the reason, or needs_click: a Confirm card the user clicks."},
    {"name": "tell", "annotations": WRITE, "inputSchema": _schema({"task": TASK, "text": TEXT}, ["task", "text"]),
     "description": "Send words to a task's own message box: guidance, an answer or the next step, as the box serves it."},
    {"name": "session", "annotations": WRITE,
     "inputSchema": _schema({"session": {"type": "string", "maxLength": 64},
                             "action": {"type": "string", "enum": ["answer", "resume"]}, "text": TEXT},
                            ["session", "action"]),
     "description": "A Console window run without a task: answer its STOP question, or resume it."},
    {"name": "new_work", "annotations": WRITE,
     "inputSchema": _schema({"project": {"type": "string", "maxLength": 300},
                             "text": {"type": "string", "maxLength": 4000}}, ["project", "text"]),
     "description": "Start Prep for new work in a project (its name or folder); the user presses Start on the Prep card."},
    {"name": "propose_order", "annotations": WRITE,
     "inputSchema": _schema({"text": {"type": "string", "maxLength": 200}}, ["text"]),
     "description": "Propose one standing order line for the background passes; the user saves it with a click."},
]


def _task(hub, tid):
    with hub.tlock:
        task = hub.tasks.get(tid) if isinstance(tid, str) and tasks.safe_id(tid) else None
    if task is None:
        raise ToolError("unknown task: read overview for the ids")
    return task


def _clip(text, limit):
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + f"\n[cut: {len(text) - limit} more characters]"


def _actions(card):
    out = []
    for place in superact.PLACES:
        for a in card.get(place) or []:
            entry = {"id": a["id"], "label": a["label"], "place": place}
            if a["off"]:
                entry["off"] = a["off"]
            if a["confirm"]:
                entry["confirm"] = True
            if not a["post"]:
                entry["form"] = list(superact.FORMS[a["id"]]) if a["id"] in superact.FORMS else "opens in the window"
            out.append(entry)
    return out


def _item(i):
    return {"task": i.get("id"), "title": i.get("title"), "ask": i.get("ask"), "say": i.get("say"),
            "always": i.get("always") or ""}


def overview(hub, turn, args):
    now = time.time()
    rows = []
    with hub.tlock:
        for t in sorted(hub.tasks.values(), key=lambda t: t.get("updated") or 0, reverse=True):
            if t["state"] in ("done", "handed") and now - (t.get("updated") or 0) > 86400:
                continue
            card = hub.actions(t)
            cs = tasks.current_step(t) if t.get("current") else None
            rows.append({"task": t["id"], "title": t["title"], "project": t.get("project", ""), "line": card["line"],
                         "level": supervisor.policy(hub.cfg, t, now)["mode"],
                         "step": f"{cs['n']:02d} {cs['kind']}" if cs else "",
                         "model": (cs.get("model") or cs.get("pick") or "") if cs else "",
                         "cost": round(sum(tasks.step_cost(s) for s in t["steps"]), 2),
                         "actions": [a["id"] for a in superact.flat(card) if not a["off"]]})
            if len(rows) >= 60:
                break
    view, snap = hub.super_view(), hub.snapshot()
    runs = [{"session": r["id"], "project": r.get("project", ""), "state": r.get("state", "")}
            for r in snap.get("sessions", []) if r.get("window") and r.get("group") == "needs"
            and not r.get("task") and not r.get("chat_task")][:20]
    return {"now": time.strftime("%Y-%m-%d %H:%M", time.localtime(now)), "tasks": rows,
            "for_you": [_item(i) for c in view.get("queue", []) for i in c.get("items", [])][:30],
            "sorted": view.get("state"), "later": [_item(i) for i in view.get("later", [])][:20],
            "runs": runs, "chat_spend": hub.chat_spend(), "acts": hub.recent_acts(10)}


def task(hub, turn, args):
    t = _task(hub, args["task"])
    with hub.tlock:
        card, message = hub.actions(t), hub.message_availability(t)
        level = supervisor.policy(hub.cfg, t, time.time())["mode"]
        pending = hub.supervisor_view(t)["pending"] or {}
        steps = [{"n": s["n"], "kind": s["kind"], "model": s.get("model") or s.get("pick") or "", "state": s["state"],
                  "cost": round(tasks.step_cost(s), 2), "verdict": s.get("verdict") or ""} for s in t["steps"]]
    return {"task": t["id"], "title": t["title"], "project": t.get("project", ""),
            "goal": _clip(t.get("goal"), GOAL_MAX), "state": t["state"], "why": t.get("why", ""), "level": level,
            "line": card["line"], "hint": card.get("hint", ""), "steps": steps,
            "handoff": _clip(tasks.read_handoff(hub.folder, t), HANDOFF_MAX), "actions": _actions(card),
            "supervisor": {"status": pending.get("status"), "reason": pending.get("reason") or pending.get("error") or ""}
                          if pending else None,
            "message": {"mode": message.get("mode"), "off": message.get("reason") or "",
                        "timing": message.get("timing") or ""}}


def read(hub, turn, args):
    t, what = _task(hub, args["task"]), args["what"]
    if what == "plan":
        try:
            text = (tasks.folder(hub.folder, t["id"]) / "plan.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        except (OSError, UnicodeError) as exc:
            raise ToolError("the plan cannot be read: " + redact.clip(str(exc), 200))
    elif what == "handoff":
        text = tasks.read_handoff(hub.folder, t)
    else:
        n = args.get("step") or t.get("last_good") or t.get("current") or 0
        if not any(s["n"] == n for s in t["steps"]):
            raise ToolError(f"no step {n}")
        text = (tasks.read_note if what == "note" else tasks.read_brief)(hub.folder, t, n)
    return {"task": t["id"], "what": what, "text": _clip(text or "(empty)", READ_MAX)}


def usage(hub, turn, args):
    return {"fills": hub.budget(), "chat": hub.chat_spend(), "passes": hub.super_view().get("spend")}


def act(hub, turn, args):
    rest = {k: args[k] for k in ("model", "note", "text", "kind", "follow_up") if k in args}
    status, body = hub.super_act(args["task"], args["action"], rest, "chat")
    if body.get("outcome") == "needs_click":
        card = hub.chat_card(turn, {"type": "confirm", "task": body["task"], "title": body["title"],
                                    "action": body["action"], "label": body["label"], "args": body["args"],
                                    "why": body["why"], "hash": body["hash"]})
        return {"outcome": "needs_click", "card": card, "why": body["why"],
                "say": "A Confirm card is in the thread: the user clicks it."}
    if body.get("outcome") != "done":
        raise ToolError(f"{body.get('outcome', 'refused')}: {body.get('why') or status}")
    return body


def tell(hub, turn, args):
    t, text = _task(hub, args["task"]), args["text"].strip()
    if not text:
        raise ToolError("text is empty")
    with hub.tlock:
        message = hub.message_availability(t)
    if message.get("reason"):
        raise ToolError("the box is closed: " + message["reason"])
    status, body = hub.task_message({"task": t["id"], "request_id": str(uuid.uuid4()), "text": redact.mask(text),
                                     "target": message["target"]})
    if not 200 <= status < 300:
        raise ToolError(body.get("error") or f"status {status}")
    hub._act_note({"phase": "told", "origin": "chat", "task": t["id"], "mode": message["mode"], "chars": len(text)})
    return {"outcome": "sent", "mode": message["mode"], "timing": message.get("timing") or ""}


def session(hub, turn, args):
    sid, what = args["session"], args["action"]
    row = hub.session(sid)
    if not row or not row.get("window"):
        raise ToolError("not a Console window run")
    with hub.tlock:
        in_task = any(a.get("session") == sid for t in hub.tasks.values() for s in t["steps"]
                      for a in tasks.attempts(s))
    if in_task:
        raise ToolError("this run is a task step: use task and act")
    text = (args.get("text") or "").strip()
    if what == "answer" and not text:
        raise ToolError("text: the answer")
    status, body = hub.pull(sid, "continue", redact.mask(text or RESUME_TEXT), False, [])
    if not 200 <= status < 300:
        raise ToolError(body.get("error") or f"status {status}")
    hub._act_note({"phase": "told", "origin": "chat", "session": sid, "mode": what, "chars": len(text)})
    return {"outcome": "sent", "session": sid}


def new_work(hub, turn, args):
    want, text = args["project"].strip(), args["text"].strip()
    dirs = [os.path.normpath(p) for p in hub.cfg.get("projects") or []]
    match = [d for d in dirs if os.path.normcase(d) == os.path.normcase(os.path.normpath(want or "."))
             or os.path.basename(d).lower() == want.lower()]
    if len(match) != 1:
        raise ToolError("project: one of " + ", ".join(os.path.basename(d) for d in dirs))
    folder = hub.allowed(match[0])
    if not folder:
        raise ToolError("not a project listed in config.json")
    if not text:
        raise ToolError("text: describe the work")
    if not hub.runs.exe:
        raise ToolError("claude.exe not found")
    job = hub.start_prep(folder, redact.mask(text), [])
    card = hub.chat_card(turn, {"type": "prep", "job": job, "project": os.path.basename(folder),
                                "text": redact.clip(redact.mask(text), 200)})
    hub._act_note({"phase": "told", "origin": "chat", "project": folder, "mode": "prep", "chars": len(text)})
    return {"outcome": "prep started", "job": job, "card": card,
            "say": "The Prep card appears in the composer; the user presses Start there."}


def propose_order(hub, turn, args):
    text = " ".join(args["text"].split())
    if not text or text.startswith("#"):
        raise ToolError("text: one order line")
    card = hub.chat_card(turn, {"type": "order", "text": redact.mask(text)})
    return {"outcome": "needs_click", "card": card, "say": "A Save order card is in the thread: the user saves it."}


FUNCS = {"overview": overview, "task": task, "read": read, "usage": usage, "act": act, "tell": tell,
         "session": session, "new_work": new_work, "propose_order": propose_order}
NAMES = tuple(t["name"] for t in TOOLS)


def call(hub, turn, name, args) -> tuple:
    """(text, is_error) of one tools/call; mcp.handle has checked the arguments."""
    try:
        out = FUNCS[name](hub, turn, args)
    except ToolError as exc:
        return str(exc), True
    return json.dumps(out, ensure_ascii=False, default=str), False
```

## 3.5 `console/server.py`

Imports: add `chattools`, `mcp` to the `from . import ...` line.

`Hub.__init__`, after the Task 1 lines:

```python
        self.chat_lock = threading.Lock()  # plan 61: innermost; tlock is never taken while it is held
        self.chat_thread = superchat.load(self.folder)
        self.chat_tokens, self.chat_busy, self.chat_proc = {}, None, None  # token -> turn; the live turn and process
        self.chat_rev = 0  # snap.chat.rev: the window reads the thread again when it changes
        self.port = cfg["port"]  # make_server sets the bound port
```

A Hub method after `chat_spend`:

```python
    def chat_card(self, turn, card):
        """A card for Fred in the thread (README 3.4): confirm, order or prep. Returns its id."""
        card = dict(card, id=uuid.uuid4().hex[:12], turn=turn, state="open", at=time.time())
        with self.chat_lock:
            self.chat_thread["cards"].append(card)
            self.chat_rev += 1
            try:
                superchat.save(self.folder, self.chat_thread)
            except OSError:
                pass  # shown from memory; the turn's end saves again
        self._super_changed()
        return card["id"]
```

`make_server`, after `httpd.daemon_threads = True`: `hub.port = httpd.server_address[1]  # plan 61: the chat's mcp.json`.

`Handler.do_POST`, first lines:

```python
    def do_POST(self):
        if urlparse(self.path).path == "/api/mcp":  # plan 61: the chat's tools carry a Bearer token, not X-CC
            return self._mcp()
        if not guard.host_ok(self.headers.get("Host"), self._port()) or not guard.post_ok(self.headers):
```

`Handler.do_GET`, beside the `/api/super` line (plan 58 Task 6): `if url.path == "/api/mcp": return self._send(405,
b"POST only", "text/plain")`.

A Handler method after `_super`:

```python
    def _mcp(self):
        if not guard.host_ok(self.headers.get("Host"), self._port()):
            return self._send(403, b"forbidden", "text/plain")
        turn = guard.mcp_ok(self.headers, self.hub.chat_tokens)
        if not turn:
            return self._send(401, b"unauthorized", "text/plain")
        msg = self._body()
        if msg is None:
            return self._json(mcp.error(None, -32700, "Parse error"), 400)
        reply = mcp.handle(msg, chattools.TOOLS, lambda name, args: chattools.call(self.hub, turn, name, args))
        if reply is None:
            return self._send(202, b"", "application/json")
        return self._json(reply)
```

## 3.6 Tests first

`tests/test_mcp.py`:

```python
"""Plan 61 Task 3: the MCP endpoint, pure and over HTTP. No paid provider, no port 47770, no ~/.claude."""
import http.client
import json
import unittest

from console import chattools, guard, mcp
from tests import test_server

TOOLS = [{"name": "echo", "description": "d", "annotations": {"readOnlyHint": True},
          "inputSchema": {"type": "object", "additionalProperties": False, "required": ["text"],
                          "properties": {"text": {"type": "string", "maxLength": 5}, "n": {"type": "integer", "minimum": 1}}}}]


def call(name, args):
    return ("x" * 90_001 if args["text"] == "big" else "said " + args["text"]), False


class McpTest(unittest.TestCase):
    def ask(self, method, params=None, id_=1):
        msg = {"jsonrpc": "2.0", "method": method, **({"id": id_} if id_ is not None else {})}
        if params is not None:
            msg["params"] = params
        return mcp.handle(msg, TOOLS, call)

    def test_methods(self):
        init = self.ask("initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertEqual((init["protocolVersion"], init["serverInfo"]["name"]), ("2025-06-18", "console"))
        self.assertEqual(self.ask("initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"],
                         mcp.VERSIONS[0])
        self.assertEqual(self.ask("ping")["result"], {})
        self.assertEqual([t["name"] for t in self.ask("tools/list")["result"]["tools"]], ["echo"])
        self.assertIsNone(self.ask("notifications/initialized", id_=None))
        self.assertEqual(self.ask("server/discover")["error"], {"code": -32601, "message": "Method not found"})
        self.assertEqual(mcp.handle([1], TOOLS, call)["error"]["code"], -32600)

    def test_call_checks_arguments(self):
        ok = self.ask("tools/call", {"name": "echo", "arguments": {"text": "hi"}})["result"]
        self.assertEqual(ok, {"content": [{"type": "text", "text": "said hi"}], "isError": False})
        for args, why in (({}, "text is required"), ({"text": "toolong"}, "text: at most 5 characters"),
                          ({"text": "a", "x": 1}, "unknown argument x"), ({"text": "a", "n": True}, "n must be integer"),
                          ({"text": "a", "n": 0}, "n: at least 1")):
            res = self.ask("tools/call", {"name": "echo", "arguments": args})["result"]
            self.assertEqual((res["isError"], res["content"][0]["text"]), (True, why))
        self.assertEqual(self.ask("tools/call", {"name": "nope"})["error"]["code"], -32602)

    def test_split_and_mask(self):
        res = mcp.result("x" * 90_001)
        self.assertEqual([len(p["text"]) for p in res["content"]], [40_000, 40_000, 10_001])
        self.assertEqual(mcp.result("token=abc123")["content"][0]["text"], "token=***")

    def test_guard(self):
        tokens = {"tok-1": "turn1"}
        self.assertEqual(guard.mcp_ok({"Authorization": "Bearer tok-1"}, tokens), "turn1")
        for auth in ("", "Bearer nope", "tok-1", "Basic tok-1"):
            self.assertEqual(guard.mcp_ok({"Authorization": auth}, tokens), "")


class McpRouteTest(test_server.RunServerTest):
    def mcp(self, msg, token="tok-1", host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        headers = {"Host": host or f"127.0.0.1:{self.port}", "Content-Type": "application/json",
                   "Authorization": f"Bearer {token}"}
        conn.request("POST", "/api/mcp", body=json.dumps(msg).encode("utf-8"), headers=headers)
        resp = conn.getresponse()
        raw, kind = resp.read(), resp.getheader("Content-Type") or ""
        conn.close()
        return resp.status, (json.loads(raw) if raw and kind.startswith("application/json") else raw.decode() or None)

    def test_tokens(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        self.assertEqual(self.mcp(msg)[0], 401)  # no live turn
        self.hub.chat_tokens["tok-1"] = "turn1"
        status, body = self.mcp(msg)
        self.assertEqual(status, 200)
        self.assertEqual([t["name"] for t in body["result"]["tools"]], list(chattools.NAMES))
        self.assertEqual(self.mcp(msg, token="tok-2")[0], 401)
        self.assertEqual(self.mcp(msg, host="evil.example:80")[0], 403)
        self.assertEqual(self.mcp({"jsonrpc": "2.0", "method": "notifications/initialized"}), (202, None))
        del self.hub.chat_tokens["tok-1"]
        self.assertEqual(self.mcp(msg)[0], 401)  # stale
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("GET", "/api/mcp", headers={"Host": f"127.0.0.1:{self.port}"})
        self.assertEqual(conn.getresponse().status, 405)  # a text body: RunServerTest.call would parse JSON
        conn.close()
```

`tests/test_chattools.py`: `ChatToolsTest` with `SuperActHubTest`'s `setUp` (Task 1) and `call(name, **args)`
returning `json.loads(text)` when `is_error` is False, else the error text:

- `test_overview_and_task`: tasks 1 (waiting `plan ready: confirm`) and 2 (running): `overview` has both in `tasks`
  with `title`, `line` (task 1 `plan ready · confirm`), `level` `gated`, task 1's `actions` containing `confirm`;
  `for_you` and `later` are lists; `chat_spend` and `acts` present. `task` of task 1 has `goal` `goal`,
  `steps` of two, `actions` whose `edit_plan` entry has `form` `opens in the window` and whose `confirm` entry has
  `place` `primary`; `message.mode` present. `task` of `zz` is the error `unknown task: read overview for the ids`.
- `test_read`: `read {task, what: "brief"}` returns the brief `make_task` wrote (`## Open questions`); `what: "plan"`
  with no file is `(empty)`; `step: 9` is the error `no step 9`; a `plan.md` of 40,000 characters comes back cut with
  `[cut: 10000 more characters]`.
- `test_act_paths`: `task_lever` patched: `act {task: t1, action: "confirm"}` returns `outcome` `done`; `act {task: t1,
  action: "stop"}` returns `outcome` `needs_click` and a `card` id; `hub.chat_thread["cards"][-1]` has `type`
  `confirm`, `action` `stop`, `state` `open`, the `hash`, and `thread.json` on disk has it; `act {task: t1, action:
  "edit_plan"}` is the error `refused: opens in the window`.
- `test_tell`: `task_message` patched to `(200, {"message": {"status": "queued"}})`: `tell {task: t2, text: "use
  style.css"}` returns `outcome` `sent`; the patched call's body has a UUID `request_id` and the availability's
  `target`; the last audit line is `phase` `told`, `chars` 13, and no `style.css` in it.
- `test_session_refuses_task_steps_and_unknown_runs`: `session {session: "nope", action: "resume"}` is the error
  `not a Console window run`.
- `test_new_work`: `start_prep` patched to return `"job1"`: `new_work {project: "proj", text: "add a footer"}` returns
  `job` `job1` and a Prep card; `project: "nope"` is the error `project: one of proj`.
- `test_propose_order`: returns `needs_click` and an `order` card with the text; `text: "# x"` is the error `text: one
  order line`.

## 3.7 Steps

- [ ] 1. Write the tests; `py -m unittest tests.test_mcp tests.test_chattools`: red.
- [ ] 2. Create `console/mcp.py` and `console/chattools.py`; add `mcp_ok` and part 1 of `superchat.py`. The pure
      tests go green.
- [ ] 3. Make the 3.5 edits. Focused tests green; `tests.test_server` green (`do_POST` unchanged for every other path).
- [ ] 4. Full suite green (report the count). Stage the new files, `console/guard.py`, `console/superchat.py`, and
      only this task's hunks of `console/server.py`. Commit with the message above.
