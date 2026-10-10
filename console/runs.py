"""Window runs: start `claude -p` detached, copy its stream to runs/<id>.jsonl, stop it, find
interrupted ones. The service only adds `run_started` / `run_ended` lines to the event log; the hooks
log the rest, so State stays the single place that builds sessions."""
import json
import subprocess
import threading
import time
import uuid
from pathlib import Path

from . import claude_cli, events, redact

WATCH_S = 0.5
CHAT_TEXT = 4000


class RunError(Exception):
    pass


def read_lines(path: Path, start: int):
    """(new offset, parsed complete lines) from `start`; non-JSON lines come back as {"raw": text}."""
    try:
        with open(path, "rb") as fh:
            fh.seek(start)
            chunk = fh.read()
    except OSError:
        return start, []
    end = chunk.rfind(b"\n")
    if end < 0:
        return start, []
    out = []
    for raw in chunk[:end].splitlines():
        text = raw.decode("utf-8", "replace").strip()
        if not text:
            continue
        try:
            rec = json.loads(text)
        except ValueError:
            rec = {"raw": text}
        out.append(rec if isinstance(rec, dict) else {"raw": text})
    return start + end + 1, out


def chat(path: Path, cwd: str = "", limit: int = 200) -> list:
    """The window run's conversation: prompts, assistant text, tool calls, results."""
    _, lines = read_lines(path, 0)
    items = []
    for d in lines:
        kind = d.get("type")
        if "raw" in d:
            items.append({"role": "note", "text": redact.clip(d["raw"], 300)})
        elif kind == "cc_prompt":
            items.append({"role": "you", "text": d.get("text", "")[:CHAT_TEXT], "ts": d.get("ts")})
        elif kind == "assistant" and not d.get("parent_tool_use_id"):
            for block in (d.get("message") or {}).get("content") or []:
                if block.get("type") == "text" and block.get("text", "").strip():
                    items.append({"role": "claude", "text": block["text"][:CHAT_TEXT]})
                elif block.get("type") == "tool_use":
                    what = redact.summarize(block.get("name"), block.get("input"), cwd)
                    items.append({"role": "tool", "text": f"{block.get('name', '')} {what}".strip()})
        elif kind == "user" and not d.get("parent_tool_use_id"):
            content = (d.get("message") or {}).get("content")
            if isinstance(content, list) and any("[Request interrupted" in str(b.get("text", ""))
                                                 for b in content if isinstance(b, dict)):
                items.append({"role": "note", "text": "stopped"})
        elif kind == "result":
            cost = d.get("total_cost_usd") or 0
            denials = len(d.get("permission_denials") or [])
            text = f"{d.get('subtype', '')} · ${cost:.2f} · {d.get('num_turns', 0)} turns"
            if denials:
                text += f" · {denials} denied"
            items.append({"role": "result", "text": text})
    return items[-limit:]


def result_record(session_id: str, result, exit_code, stopped: bool) -> dict:
    """The run_ended event line for one finished process."""
    rec = {"event": "run_ended", "session_id": session_id, "exit": exit_code,
           "stopped": stopped, "interrupted": result is None and not stopped}
    if result:
        rec["subtype"] = result.get("subtype", "")
        rec["cost"] = result.get("total_cost_usd") or 0
        denials = []
        for d in (result.get("permission_denials") or [])[:3]:
            tool = d.get("tool_name", "")
            denials.append({"tool": tool, "what": redact.summarize(tool, d.get("tool_input"))})
        if denials:
            rec["denials"] = denials
    return rec


class RunManager:
    """One per service. `live` holds the processes this service started (it owns their stdin)."""

    def __init__(self, cfg: dict, folder: Path, exe: list = None):
        self.cfg = cfg
        self.folder = Path(folder)
        self.runs = self.folder / "runs"
        self.exe = exe
        self.lock = threading.Lock()
        self.live = {}
        self.stopping = set()

    # -- files ----------------------------------------------------------------------
    def stream_path(self, sid: str) -> Path:
        return self.runs / f"{sid}.jsonl"

    def meta_path(self, sid: str) -> Path:
        return self.runs / f"{sid}.json"

    def meta(self, sid: str):
        try:
            return json.loads(self.meta_path(sid).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _save_meta(self, meta: dict) -> None:
        self.meta_path(meta["session_id"]).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    def emit(self, rec: dict) -> None:
        rec = dict(rec, ts=round(time.time(), 3))
        events.append(self.folder, rec)

    def is_live(self, sid: str) -> bool:
        with self.lock:
            proc = self.live.get(sid)
        if proc is not None:
            return proc.poll() is None
        meta = self.meta(sid)
        return bool(meta and not meta.get("ended") and claude_cli.pid_alive(meta.get("pid")))

    # -- start ----------------------------------------------------------------------
    def start(self, cwd: str, prompt: str, model: str, effort: str, resume: str = None,
              title: str = "", route: str = "", reason: str = "", prep: str = "") -> str:
        if not self.exe:
            raise RunError("claude.exe not found; set \"claude_exe\" in config.json")
        sid = resume or str(uuid.uuid4())
        if resume and self.is_live(sid):
            raise RunError("this session is still running")
        self.runs.mkdir(parents=True, exist_ok=True)
        path = self.stream_path(sid)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "cc_prompt", "ts": time.time(), "text": prompt}, ensure_ascii=False) + "\n")
        offset = path.stat().st_size
        cmd = claude_cli.run_command(self.exe, model, effort, sid, resume=bool(resume),
                                     name=redact.clip(title, 60))
        proc = self._spawn(cmd, cwd, path)
        proc.stdin.write(claude_cli.user_message(prompt + claude_cli.STOP_FOOTER))
        proc.stdin.flush()
        with self.lock:
            self.live[sid] = proc
            self.stopping.discard(sid)
        start_commit = claude_cli.git_head(cwd)
        self._save_meta({"session_id": sid, "pid": proc.pid, "cwd": cwd, "model": model, "effort": effort,
                         "offset": offset, "started": time.time(), "ended": None,
                         "start_commit": (self.meta(sid) or {}).get("start_commit") or start_commit})
        rec = {"event": "run_started", "session_id": sid, "cwd": cwd, "project": Path(cwd).name,
               "project_dir": cwd, "pid": proc.pid,
               "model": model, "effort": effort, "resume": bool(resume), "start_commit": start_commit}
        for key, value in (("title", title), ("route", route), ("reason", reason), ("prep", prep)):
            if value:
                rec[key] = value
        self.emit(rec)
        threading.Thread(target=self._watch, args=(sid, proc, path, offset), name=f"run-{sid[:8]}",
                         daemon=True).start()
        return sid

    def _spawn(self, cmd: list, cwd: str, path: Path):
        out = open(path, "ab")
        try:
            kwargs = dict(cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=subprocess.STDOUT,
                          env=claude_cli.child_env())
            try:  # leave any job object so closing the window's parent cannot take the run with it
                return subprocess.Popen(cmd, creationflags=claude_cli.NO_WINDOW | claude_cli.BREAKAWAY, **kwargs)
            except OSError:
                return subprocess.Popen(cmd, creationflags=claude_cli.NO_WINDOW, **kwargs)
        finally:
            out.close()

    def _watch(self, sid: str, proc, path: Path, offset: int) -> None:
        """Close stdin after the result line (stream-json input waits for more otherwise)."""
        result = None
        while True:
            offset, lines = read_lines(path, offset)
            for d in lines:
                if d.get("type") == "result":
                    result = d
            if (result is not None or proc.poll() is not None) and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
            if proc.poll() is not None:
                offset, lines = read_lines(path, offset)
                result = next((d for d in reversed(lines) if d.get("type") == "result"), result)
                break
            time.sleep(WATCH_S)
        self._finish(sid, result, proc.returncode)
        with self.lock:
            if self.live.get(sid) is proc:
                del self.live[sid]

    def _finish(self, sid: str, result, exit_code) -> None:
        with self.lock:
            stopped = sid in self.stopping
            self.stopping.discard(sid)
        meta = self.meta(sid) or {"session_id": sid}
        if meta.get("ended"):
            return
        meta["ended"] = time.time()
        self._save_meta(meta)
        self.emit(result_record(sid, result, exit_code, stopped))

    # -- stop -----------------------------------------------------------------------
    def stop(self, sid: str) -> str:
        with self.lock:
            proc = self.live.get(sid)
            if proc is not None:  # ours: never kill, only interrupt
                if proc.poll() is not None:
                    return "not running"
                self.stopping.add(sid)
                try:
                    proc.stdin.write(claude_cli.interrupt_message("stop-" + uuid.uuid4().hex[:8]))
                    proc.stdin.flush()
                    return "interrupt"
                except (OSError, ValueError):  # stdin already closed: the turn is ending by itself
                    self.stopping.discard(sid)
                    return "finishing"
        meta = self.meta(sid)
        if meta and not meta.get("ended") and claude_cli.pid_alive(meta.get("pid")):
            with self.lock:
                self.stopping.add(sid)
            claude_cli.kill_tree(meta["pid"])
            return "killed"
        return "not running"

    # -- recovery -------------------------------------------------------------------
    def reconcile(self) -> int:
        """Runs started by an earlier service: emit run_ended once their process is gone.
        No result line means the turn was cut (crash, shutdown): Interrupted."""
        if not self.runs.exists():
            return 0
        done = 0
        for meta_file in self.runs.glob("*.json"):
            sid = meta_file.stem
            with self.lock:
                if sid in self.live:
                    continue
            meta = self.meta(sid)
            if not meta or meta.get("ended") or claude_cli.pid_alive(meta.get("pid")):
                continue
            _, lines = read_lines(self.stream_path(sid), meta.get("offset", 0))
            result = next((d for d in reversed(lines) if d.get("type") == "result"), None)
            self._finish(sid, result, None)
            done += 1
        return done

    def open_terminal(self, sid: str) -> None:
        meta = self.meta(sid)
        if not meta:
            raise RunError("not a window run")
        if self.is_live(sid):
            raise RunError("stop the run first: two writers on one session")
        subprocess.Popen(claude_cli.terminal_command(self.exe, sid), cwd=meta["cwd"],
                         env=claude_cli.child_env(), creationflags=claude_cli.NEW_CONSOLE)


def prune(folder: Path, retention_days: int, now: float = None) -> list:
    """Delete runs/* and preps/* files not touched for `retention_days`."""
    cutoff = (now or time.time()) - retention_days * 86400
    removed = []
    for sub in ("runs", "preps"):
        for path in (Path(folder) / sub).glob("*.json*"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed.append(f"{sub}/{path.name}")
            except OSError:
                pass
    return removed
