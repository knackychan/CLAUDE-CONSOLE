"""The console service: reads the event log, keeps the state, serves the window over HTTP + SSE."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import events, guard, paths
from .state import State

WEB = Path(__file__).resolve().parent.parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}
POLL_S = 1.0
TICK_S = 15.0
APP_ID = "claude-console"


class Hub:
    """Owns the State. One thread polls the log; readers wait on `changed`."""

    def __init__(self, cfg: dict, folder: Path):
        self.state = State(cfg)
        self.reader = events.LogReader(folder)
        self.lock = threading.Lock()
        self.changed = threading.Condition(self.lock)
        self.version = 0
        self._stop = threading.Event()

    def poll_once(self) -> int:
        new = self.reader.read_new()
        with self.lock:
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
        last_tick = time.monotonic()
        while not self._stop.is_set():
            self.poll_once()
            if time.monotonic() - last_tick >= TICK_S:
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

    def do_GET(self):
        if not guard.host_ok(self.headers.get("Host"), self._port()):
            return self._send(403, b"forbidden", "text/plain")
        url = urlparse(self.path)
        if url.path in STATIC:
            name, ctype = STATIC[url.path]
            return self._send(200, (WEB / name).read_bytes(), ctype)
        if url.path == "/api/ping":
            return self._json({"app": APP_ID})
        if url.path == "/api/state":
            return self._json(self.hub.snapshot())
        if url.path == "/api/steps":
            sid = parse_qs(url.query).get("session", [""])[0]
            return self._json(self.hub.steps(sid))
        if url.path == "/api/stream":
            return self._stream()
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not guard.host_ok(self.headers.get("Host"), self._port()) or not guard.post_ok(self.headers):
            return self._send(403, b"forbidden", "text/plain")
        return self._send(404, b"not found", "text/plain")

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


def make_server(cfg: dict, port: int = None, folder: Path = None):
    """Bind 127.0.0.1 (never another host). Returns (httpd, hub); raises OSError if the port is taken."""
    hub = Hub(cfg, folder or paths.home())
    handler = type("BoundHandler", (Handler,), {"hub": hub})
    httpd = ThreadingHTTPServer(("127.0.0.1", cfg["port"] if port is None else port), handler)
    httpd.daemon_threads = True
    return httpd, hub
