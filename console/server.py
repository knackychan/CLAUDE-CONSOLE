"""The console service: reads the event log, keeps the state, serves the window over HTTP + SSE,
starts, stops and resumes window runs (phase 2), and pulls the levers (phase 3)."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import brief, claude_cli, events, guard, levers, paths, prep, runs, transcript, usage
from .state import MAX_STEPS, WRITE_TOOLS, State, norm_dir

WEB = Path(__file__).resolve().parent.parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/doto.woff2": ("doto.woff2", "font/woff2")}
POLL_S = 1.0
TICK_S = 15.0
HISTORY_S = 60.0  # the Usage page's scan of every transcript
APP_ID = "claude-console"
MAX_BODY = 256 * 1024
MAX_PROMPT = 20000
BUSY = {"running", "quiet", "stall"}


class Hub:
    """Owns the State. One thread polls the log; readers wait on `changed`."""

    def __init__(self, cfg: dict, folder: Path, exe: list = None):
        self.cfg = cfg
        self.folder = Path(folder)
        self.state = State(cfg)
        self.reader = events.LogReader(folder)
        self.runs = runs.RunManager(cfg, folder, exe)
        self.usage = usage.Usage(cfg["prices"])
        self.history = usage.History(cfg["prices"])
        self.usage_days = {}  # day -> totals: every transcript merged with usage-days.json
        self.usage_ready = False
        self.user_home = Path.home()  # where ~/.claude/skills is looked up (tests point it elsewhere)
        self.lock = threading.Lock()
        self.changed = threading.Condition(self.lock)
        self.version = 0
        self._stop = threading.Event()

    def poll_once(self) -> int:
        with self.lock:  # request threads call this too, right after they add a line
            new = self.reader.read_new()
            for rec in new:
                self.state.apply(rec)
            if new:
                self.version += 1
                self.changed.notify_all()
        return len(new)

    def read_costs(self) -> int:
        """Read what the shown sessions' transcripts added (estimated cost); new messages push a snapshot."""
        with self.lock:
            files = self.state.transcripts(time.time())
        self.usage.keep(files)
        new = sum(self.usage.poll(f) for f in files)  # file reads outside the lock: Usage has its own
        if new:
            with self.lock:
                self.version += 1
                self.changed.notify_all()
        return new

    def read_history(self) -> None:
        """The Usage page: what every transcript under ~/.claude/projects added, per day, merged with the
        closed days kept in usage-days.json (Claude Code deletes transcripts after 30 days)."""
        self.history.scan(self.user_home / ".claude" / "projects")
        scanned, today = self.history.days(), usage.day_of(time.time())
        usage.save_days(self.folder, scanned, today)
        days = usage.merge_days(usage.load_days(self.folder), scanned)
        with self.lock:
            self.usage_days, self.usage_ready = days, True

    def usage_report(self) -> dict:
        with self.lock:
            days, ready = self.usage_days, self.usage_ready
        today = usage.day_of(time.time())
        return {"ready": ready, "today": today, "first": min(days) if days else "",
                "limit": self.cfg["daily_budget_usd"], "days": days,
                "weeks": usage.weeks(days, today), "months": usage.months(days, today)}

    def history_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.read_history()
            except OSError:
                pass
            self._stop.wait(HISTORY_S)

    def tick(self) -> None:
        """Time-based states (Quiet, Stall?, Stale?) change without new events."""
        with self.lock:
            self.version += 1
            self.changed.notify_all()

    def run(self) -> None:
        self.runs.reconcile()
        last_tick = time.monotonic()
        while not self._stop.is_set():
            self.poll_once()
            self.read_costs()
            if time.monotonic() - last_tick >= TICK_S:
                self.runs.reconcile()
                self.tick()
                last_tick = time.monotonic()
            self._stop.wait(POLL_S)

    def start(self) -> None:
        threading.Thread(target=self.run, name="cc-hub", daemon=True).start()
        threading.Thread(target=self.history_loop, name="cc-usage", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> dict:
        now = time.time()
        with self.lock:
            return self.state.snapshot(now, self.usage, self.usage_days.get(usage.day_of(now)))

    def steps(self, session_id: str, limit: int = 200) -> list:
        with self.lock:
            return self.state.steps(session_id, limit)

    def session(self, session_id: str):
        with self.lock:
            s = self.state.sessions.get(session_id)
            if s is None:
                return None
            return {"cwd": s.cwd, "first_cwd": s.first_cwd or s.cwd, "window": s.window, "title": s.title,
                    "model": s.model, "effort": s.effort, "prep": s.prep, "start_commit": s.start_commit,
                    "project": s.project, "project_dir": s.project_dir, "route": s.route,
                    "run_live": s.run_live, "state": self.state.state_of(s, time.time()),
                    "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated,
                    "transcript_path": s.transcript_path, "ctx_tokens": s.ctx_tokens, "last_ts": s.last_ts,
                    "handoff_by": s.handoff_by if s.handed_off else ""}

    def route_of(self, session_id: str, s: dict) -> tuple:
        """(model, effort) the session runs on: a window run's own route, else the model last seen."""
        meta = self.runs.meta(session_id) or {}
        model = meta.get("model") or claude_cli.model_alias(s["model"]) or self.cfg["default_model"]
        effort = meta.get("effort") or (s["effort"] if s["effort"] in claude_cli.EFFORTS
                                        else self.cfg["default_effort"])
        return model, effort

    def cold(self, s: dict, model: str, now: float = None):
        """What a lever would re-read at full price: {idle_s, tokens, cost}, or None. The chat has been
        idle past cold_after_s (both cache lifetimes are gone) and holds gauge_yellow_tokens or more;
        cost = tokens x the 5-minute cache-write price of the route's model (the cheaper of the two)."""
        tokens, idle = s["ctx_tokens"], (now or time.time()) - s["last_ts"]
        if not tokens or tokens < self.cfg["gauge_yellow_tokens"] or idle < self.cfg["cold_after_s"]:
            return None
        price = self.cfg["prices"].get(model) or self.cfg["prices"]["sonnet"]
        return {"idle_s": int(idle), "tokens": tokens, "cost": round(tokens * price["cache_write_5m"] / 1e6, 2)}

    def levers(self, session_id):
        """What each lever would do for this session and why one is off ("" = allowed). The one
        place that decides; the POST handlers call it again before they start anything."""
        s = self.session(session_id) if isinstance(session_id, str) else None
        if s is None:
            return None
        meta = self.runs.meta(session_id)
        window = bool(s["window"] and meta)
        cwd = meta.get("cwd") if window else s["first_cwd"]  # Claude Code files a chat under its start folder
        if not self.allowed(s["project_dir"]):
            base = "runs are off in this project: pick it on the home view and allow runs"
        elif not self.runs.exe:
            base = "claude.exe not found; set \"claude_exe\" in config.json"
        elif s["run_live"] or s["state"] in BUSY or self.runs.is_live(session_id):
            base = "still working: wait until it stops"
        elif not cwd or not os.path.isdir(cwd):
            base = "the session's folder is gone"
        else:
            base = ""
        model, effort = self.route_of(session_id, s)
        step = levers.escalate_step(model, effort)
        if base:
            escalate = base
        elif s["verdict"] != "FAIL":
            escalate = "only after a FAIL verdict"
        elif s["escalated"]:
            escalate = f"escalated once already ({s['escalated']})"
        elif not step:
            escalate = "already on the top route"
        else:
            escalate = ""
        handoff = base or ("" if levers.handoff_ready(s["project_dir"], self.user_home) else
                           "the session-handoff skill is not installed here: copy "
                           "dotclaude/skills/session-handoff to ~/.claude/skills")
        nxt = base or ("" if s["handoff_by"] else "only after a Hand off")  # a new task seeded with the note
        return {"continue": base, "verify": base, "handoff": handoff, "escalate": escalate, "next": nxt,
                "after_verify": list(levers.after_verify(s["verdict"])), "route": f"{model}/{effort}", "escalate_to": "/".join(step) if step else "",
                "fork": not window, "cwd": cwd or "", "cold": None if base else self.cold(s, model)}

    def allowed(self, project_dir) -> str:
        """The configured folder matching `project_dir`, or "" (runs only in listed folders)."""
        if not isinstance(project_dir, str) or not project_dir:
            return ""
        want = os.path.normcase(os.path.abspath(project_dir))
        for folder in self.cfg.get("projects") or []:
            if os.path.normcase(os.path.abspath(folder)) == want and os.path.isdir(folder):
                return folder
        return ""

    def seen(self, project_dir: str) -> bool:
        """True when a Claude Code session already ran in `project_dir` (the event log saw it)."""
        want = os.path.normcase(os.path.abspath(project_dir))
        with self.lock:
            return any(s.project_dir and os.path.normcase(os.path.abspath(s.project_dir)) == want
                       for s in self.state.sessions.values())

    def allow(self, project_dir: str) -> list:
        """Fred's "Allow runs here": add the folder to config.json and to the live config."""
        folder = norm_dir(os.path.normpath(os.path.abspath(project_dir)))
        with self.lock:
            paths.add_project(self.folder, folder)
            projects = list(self.cfg.get("projects") or [])
            if not self.allowed(folder):
                projects.append(folder)
            self.cfg["projects"] = projects
            return projects


def project_list(cfg: dict) -> list:
    """config.json "projects" spelled like the sessions' project_dir, so the window can match them."""
    return [norm_dir(os.path.normpath(p)) for p in cfg.get("projects") or []]


class Handler(BaseHTTPRequestHandler):
    hub: Hub = None  # set by make_server

    def log_message(self, *args):  # keep the console quiet
        pass

    def _port(self) -> int:
        return self.server.server_address[1]

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, code: int, message: str) -> None:
        self._json({"error": message}, code)

    def do_GET(self):
        if not guard.host_ok(self.headers.get("Host"), self._port()):
            return self._send(403, b"forbidden", "text/plain")
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path in STATIC:
            name, ctype = STATIC[url.path]
            return self._send(200, (WEB / name).read_bytes(), ctype)
        if url.path == "/api/ping":
            return self._json({"app": APP_ID})
        if url.path == "/api/state":
            return self._json(self.hub.snapshot())
        if url.path == "/api/steps":
            return self._json(self.hub.steps(query.get("session", [""])[0]))
        if url.path == "/api/config":
            cfg, window = self.hub.cfg, paths.load_window(self.hub.folder)
            return self._json({"projects": project_list(cfg), "models": claude_cli.MODELS,
                               "efforts": claude_cli.EFFORTS, "default_model": cfg["default_model"],
                               "default_effort": cfg["default_effort"], "claude": bool(self.hub.runs.exe),
                               "config_path": str(self.hub.folder / "config.json"),
                               "gauge": [cfg["gauge_yellow_tokens"], cfg["gauge_red_tokens"]],
                               "project": window.get("project", ""), "brief": window.get("brief") is True})
        if url.path == "/api/usage":
            return self._json(self.hub.usage_report())
        if url.path == "/api/chat":
            return self._chat(query.get("session", [""])[0])
        if url.path == "/api/brief":
            return self._brief(query.get("session", [""])[0], query.get("kind", ["task"])[0])
        if url.path == "/api/levers":
            data = self.hub.levers(query.get("session", [""])[0])
            return self._json(data) if data else self._error(404, "unknown session")
        if url.path == "/api/draft":
            try:
                text = (self.hub.folder / "draft.txt").read_text(encoding="utf-8")
            except OSError:
                text = ""
            return self._json({"text": text})
        if url.path == "/api/stream":
            return self._stream()
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not guard.host_ok(self.headers.get("Host"), self._port()) or not guard.post_ok(self.headers):
            return self._send(403, b"forbidden", "text/plain")
        routes = {"/api/prep": self._prep, "/api/run": self._run, "/api/stop": self._stop,
                  "/api/terminal": self._terminal, "/api/draft": self._draft, "/api/allow": self._allow,
                  "/api/done": self._done}
        for lever in ("continue", "verify", "handoff", "escalate"):
            routes[f"/api/{lever}"] = lambda body, lever=lever: self._lever(body, lever)
        handler = routes.get(urlparse(self.path).path)
        if handler is None:
            return self._send(404, b"not found", "text/plain")
        body = self._body()
        if body is None:
            return self._error(400, "expected a JSON object")
        try:
            return handler(body)
        except (runs.RunError, prep.PrepError) as exc:
            return self._error(409, str(exc))

    def _body(self):
        try:
            size = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if size <= 0 or size > MAX_BODY:
            return None
        try:
            data = json.loads(self.rfile.read(size).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _text(self, body: dict, key: str) -> str:
        value = body.get(key)
        return value.strip() if isinstance(value, str) and len(value) <= MAX_PROMPT else ""

    # -- POST handlers ---------------------------------------------------------------
    def _prep(self, body):
        folder, raw = self.hub.allowed(body.get("project_dir")), self._text(body, "prompt")
        if not folder:
            return self._error(403, "not a project listed in config.json")
        if not raw:
            return self._error(400, "empty prompt")
        if not self.hub.runs.exe:
            return self._error(409, "claude.exe not found; set \"claude_exe\" in config.json")
        return self._json(prep.run_prep(self.hub.cfg, self.hub.folder, folder, raw, self.hub.runs.exe))

    def _run(self, body):
        folder, text = self.hub.allowed(body.get("project_dir")), self._text(body, "prompt")
        if not folder:
            return self._error(403, "not a project listed in config.json")
        if not text:
            return self._error(400, "empty prompt")
        cfg = self.hub.cfg
        model = body.get("model") or cfg["default_model"]
        effort = body.get("effort") or cfg["default_effort"]
        if model not in claude_cli.MODELS or effort not in claude_cli.EFFORTS:
            return self._error(400, "unknown model or effort")
        card = prep.load(self.hub.folder, body.get("prep")) if body.get("prep") else None
        if card:
            title = card["fields"].get("goal") or card["raw"]
            route = card["route"].get("type") or "routed"
            reason, prep_id = card.get("reason", ""), card["id"]
            extra = {"prep_model": card.get("model") or cfg["prep_model"], "prep_cost": card.get("cost"),
                     "prep_turns": card.get("turns")}  # the Route block's first row
        else:
            title, route, reason, prep_id, extra = text, "raw", "", "", None
        sid = self.hub.runs.start(folder, text, model, effort, title=title, route=route,
                                  reason=reason, prep=prep_id, extra=extra)
        self.hub.poll_once()
        return self._json({"session": sid})

    def _window_session(self, body):
        sid = body.get("session")
        s = self.hub.session(sid) if isinstance(sid, str) else None
        if not s or not s["window"] or not self.hub.runs.meta(sid):
            return None, None
        return sid, s

    def _stop(self, body):
        sid, s = self._window_session(body)
        if not sid:
            return self._error(404, "not a window run")
        result = self.hub.runs.stop(sid)
        return self._json({"stop": result})

    def _done(self, body):
        """Mark done: a chat that never sent its Stop (closed mid-turn) leaves the list until its next prompt."""
        sid = body.get("session")
        s = self.hub.session(sid) if isinstance(sid, str) else None
        if s is None:
            return self._error(404, "unknown session")
        if s["run_live"] or self.hub.runs.is_live(sid):
            return self._error(409, "a window run is still going: Stop it first")
        self.hub.runs.emit({"event": "marked_done", "session_id": sid})
        self.hub.poll_once()
        return self._json({"session": sid})

    def _lever(self, body, lever):
        """Continue (also STOP answers and Resume), Verify, Handoff, Escalate: a new turn of a window
        run, or a window copy (fork) of a VS Code / terminal chat, which stays as it is."""
        sid = body.get("session")
        info = self.hub.levers(sid)
        if info is None:
            return self._error(404, "unknown session")
        if info[lever]:
            return self._error(409, info[lever])
        if info["cold"] and body.get("confirm") is not True:  # the page asks with a second click
            c = info["cold"]
            return self._error(409, f"cold cache: {c['tokens'] // 1000}K tokens, idle {c['idle_s'] / 3600:.0f} h, "
                                    f"would be re-read at full price (about ${c['cost']:.2f}); open the session to "
                                    "confirm, or start a new task there with a brief")
        s = self.hub.session(sid)
        model, effort = self.hub.route_of(sid, s)
        extra, miss = {}, ""
        if lever == "continue":
            text = self._text(body, "text")
            if not text:
                return self._error(400, "empty prompt")
        elif lever == "verify":
            text = levers.VERIFY_TEXT
        elif lever == "handoff":
            text = levers.HANDOFF_TEXT
        else:  # escalate: one step up, once, and the miss is logged for Prep
            new_model, new_effort = levers.escalate_step(model, effort)
            route_from, route_to = f"{model}/{effort}", f"{new_model}/{new_effort}"
            miss = levers.miss_line(s["project"], s["route"], route_from, route_to, s["verdict_detail"])
            text = levers.escalate_text(s["verdict_detail"], new_model, new_effort)
            model, effort = new_model, new_effort
            extra = {"escalated": f"{route_from} -> {route_to}"}
        fork = sid if info["fork"] else ""
        new = self.hub.runs.start(info["cwd"], text, model, effort, resume=None if fork else sid, fork=fork,
                                  title="↳ " + (s["title"] or sid[:8]) if fork else "",
                                  route=s["route"] if fork else "", kind=lever, extra=extra)
        if miss:
            levers.add_miss(self.hub.folder, miss)
        self.hub.poll_once()
        return self._json({"session": new})

    def _terminal(self, body):
        sid, s = self._window_session(body)
        if not sid:
            return self._error(404, "not a window run")
        self.hub.runs.open_terminal(sid)
        return self._json({"ok": True})

    def _allow(self, body):
        """Only folders Claude Code already ran in: the page cannot add an arbitrary path."""
        want = body.get("project_dir")
        if not isinstance(want, str) or not want or not os.path.isdir(want):
            return self._error(400, "not a folder")
        if not self.hub.seen(want):
            return self._error(403, "only a folder with a Claude Code session can be allowed")
        try:
            self.hub.allow(want)
        except ValueError as exc:
            return self._error(409, str(exc))
        return self._json({"projects": project_list(self.hub.cfg)})

    def _draft(self, body):
        """The unsent prompt (draft.txt) and, when given, the compose project and whether the session
        page keeps its brief open (window.json)."""
        text, project, brief = body.get("text"), body.get("project"), body.get("brief")
        if not isinstance(text, str) or len(text) > MAX_PROMPT:
            return self._error(400, "bad draft")
        if project is not None and (not isinstance(project, str) or len(project) > 1000):
            return self._error(400, "bad project")
        if brief is not None and not isinstance(brief, bool):
            return self._error(400, "bad brief")
        self.hub.folder.mkdir(parents=True, exist_ok=True)
        (self.hub.folder / "draft.txt").write_text(text, encoding="utf-8")
        fields = {k: v for k, v in (("project", project), ("brief", brief)) if v is not None}
        if fields:
            paths.save_window(self.hub.folder, **fields)
        return self._json({"ok": True})

    # -- GET helpers -----------------------------------------------------------------
    def _chat(self, sid: str):
        """A window run's stream, or for a VS Code / terminal chat the last turns of its transcript."""
        meta = self.hub.runs.meta(sid) if sid and all(c.isalnum() or c == "-" for c in sid) else None
        if not meta:
            info = self.hub.session(sid)
            items = transcript.turns(info["transcript_path"]) if info else []
            return self._json({"items": items, "source": "transcript", "changed": None, "live": False})
        items = runs.chat(self.hub.runs.stream_path(sid), meta.get("cwd", ""))
        changed = claude_cli.git_changed(meta["cwd"], meta.get("start_commit", ""))
        return self._json({"items": items, "source": "window", "changed": changed,
                           "live": self.hub.runs.is_live(sid), "start_commit": meta.get("start_commit", "")})

    def _brief(self, sid: str, kind: str):
        """The text of a new task that takes over a session, built from its transcript, its steps and the
        folder's git status: no model call, nothing written."""
        s = self.hub.session(sid)
        if s is None or kind not in ("task", "verify", "next"):
            return self._error(404, "unknown session")
        if kind == "next":  # after a Hand off: the next task starts from the skill's note
            off = self.hub.levers(sid)["next"]
            if off:
                return self._error(409, off)
            return self._json({"text": brief.build("next", last=self._last_reply(s["handoff_by"])),
                               "project_dir": s["project_dir"]})
        turns = transcript.turns(s["transcript_path"])
        files = []
        for step in self.hub.steps(sid, MAX_STEPS):
            if step["tool"] in WRITE_TOOLS and step["what"] and step["what"] not in files:
                files.append(step["what"])
        folder = s["project_dir"] if os.path.isdir(s["project_dir"] or "") else s["cwd"]
        text = brief.build(kind, goal=transcript.first_prompt(s["transcript_path"]) or s["title"],
                           last=next((t["text"] for t in reversed(turns) if t["role"] == "claude"), ""),
                           files=files, verdict=s["verdict"], detail=s["verdict_detail"],
                           status=claude_cli.git_status(folder) if os.path.isdir(folder or "") else [],
                           plan=os.path.isfile(os.path.join(folder or "", "PLAN.md")))
        return self._json({"text": text, "project_dir": s["project_dir"]})

    def _last_reply(self, sid: str) -> str:
        """Claude's last message in a session: its window run's stream, or its transcript."""
        if self.hub.runs.meta(sid):
            items = runs.chat(self.hub.runs.stream_path(sid))
        else:
            s = self.hub.session(sid)
            items = transcript.turns(s["transcript_path"]) if s else []
        return next((i["text"] for i in reversed(items) if i["role"] == "claude"), "")

    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        seen = -1
        try:
            while True:
                with self.hub.changed:
                    if self.hub.version == seen:
                        self.hub.changed.wait(TICK_S)
                    current = self.hub.version
                if current == seen:
                    self.wfile.write(b": ping\n\n")
                else:
                    seen = current
                    data = json.dumps(self.hub.snapshot(), ensure_ascii=False)
                    self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionError, OSError):
            return


def make_server(cfg: dict, port: int = None, folder: Path = None, exe: list = None):
    """Bind 127.0.0.1 (never another host). Returns (httpd, hub); raises OSError if the port is taken.
    `exe` is the claude command prefix (tests pass a fake); default: the real claude.exe."""
    if exe is None:
        found = claude_cli.find_exe(cfg)
        exe = [found] if found else None
    hub = Hub(cfg, folder or paths.home(), exe)
    handler = type("BoundHandler", (Handler,), {"hub": hub})
    httpd = ThreadingHTTPServer(("127.0.0.1", cfg["port"] if port is None else port), handler)
    httpd.daemon_threads = True
    return httpd, hub
