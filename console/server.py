"""The console service: reads the event log, keeps the state, serves the window over HTTP + SSE,
and (phase 2) starts, stops and resumes window runs."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import claude_cli, events, guard, paths, prep, runs
from .state import State, norm_dir

WEB = Path(__file__).resolve().parent.parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}
POLL_S = 1.0
TICK_S = 15.0
APP_ID = "claude-console"
MAX_BODY = 256 * 1024
MAX_PROMPT = 20000


class Hub:
    """Owns the State. One thread polls the log; readers wait on `changed`."""

    def __init__(self, cfg: dict, folder: Path, exe: list = None):
        self.cfg = cfg
        self.folder = Path(folder)
        self.state = State(cfg)
        self.reader = events.LogReader(folder)
        self.runs = runs.RunManager(cfg, folder, exe)
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
            if time.monotonic() - last_tick >= TICK_S:
                self.runs.reconcile()
                self.tick()
                last_tick = time.monotonic()
            self._stop.wait(POLL_S)

    def start(self) -> None:
        threading.Thread(target=self.run, name="cc-hub", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> dict:
        with self.lock:
            return self.state.snapshot(time.time())

    def steps(self, session_id: str) -> list:
        with self.lock:
            return self.state.steps(session_id)

    def session(self, session_id: str):
        with self.lock:
            s = self.state.sessions.get(session_id)
            return None if s is None else {"cwd": s.cwd, "window": s.window, "title": s.title,
                                           "model": s.model, "effort": s.effort, "prep": s.prep,
                                           "start_commit": s.start_commit}

    def allowed(self, project_dir) -> str:
        """The configured folder matching `project_dir`, or "" (runs only in listed folders)."""
        if not isinstance(project_dir, str) or not project_dir:
            return ""
        want = os.path.normcase(os.path.abspath(project_dir))
        for folder in self.cfg.get("projects") or []:
            if os.path.normcase(os.path.abspath(folder)) == want and os.path.isdir(folder):
                return folder
        return ""


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
            cfg = self.hub.cfg
            projects = [norm_dir(os.path.normpath(p)) for p in cfg.get("projects") or []]
            return self._json({"projects": projects, "models": claude_cli.MODELS,
                               "efforts": claude_cli.EFFORTS, "default_model": cfg["default_model"],
                               "default_effort": cfg["default_effort"], "claude": bool(self.hub.runs.exe),
                               "config_path": str(self.hub.folder / "config.json")})
        if url.path == "/api/chat":
            return self._chat(query.get("session", [""])[0])
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
                  "/api/answer": self._answer, "/api/terminal": self._terminal, "/api/draft": self._draft}
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
        else:
            title, route, reason, prep_id = text, "raw", "", ""
        sid = self.hub.runs.start(folder, text, model, effort, title=title, route=route,
                                  reason=reason, prep=prep_id)
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

    def _answer(self, body):
        """STOP answers and Interrupted resumes: the same session, a new turn."""
        sid, s = self._window_session(body)
        text = self._text(body, "text")
        if not sid:
            return self._error(404, "not a window run")
        if not text:
            return self._error(400, "empty answer")
        meta = self.hub.runs.meta(sid)
        if not self.hub.allowed(meta.get("cwd")):
            return self._error(403, "not a project listed in config.json")
        self.hub.runs.start(meta["cwd"], text, meta["model"], meta["effort"], resume=sid)
        self.hub.poll_once()
        return self._json({"session": sid})

    def _terminal(self, body):
        sid, s = self._window_session(body)
        if not sid:
            return self._error(404, "not a window run")
        self.hub.runs.open_terminal(sid)
        return self._json({"ok": True})

    def _draft(self, body):
        text = body.get("text")
        if not isinstance(text, str) or len(text) > MAX_PROMPT:
            return self._error(400, "bad draft")
        self.hub.folder.mkdir(parents=True, exist_ok=True)
        (self.hub.folder / "draft.txt").write_text(text, encoding="utf-8")
        return self._json({"ok": True})

    # -- GET helpers -----------------------------------------------------------------
    def _chat(self, sid: str):
        meta = self.hub.runs.meta(sid) if sid and all(c.isalnum() or c == "-" for c in sid) else None
        if not meta:
            return self._json({"items": [], "changed": None, "live": False})
        items = runs.chat(self.hub.runs.stream_path(sid), meta.get("cwd", ""))
        changed = claude_cli.git_changed(meta["cwd"], meta.get("start_commit", ""))
        return self._json({"items": items, "changed": changed, "live": self.hub.runs.is_live(sid),
                           "start_commit": meta.get("start_commit", "")})

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
