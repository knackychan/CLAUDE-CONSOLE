"""Window runs: start `claude -p` detached, copy its stream to runs/<id>.jsonl, stop it, find
interrupted ones. The service only adds `run_started` / `run_ended` lines to the event log; the hooks
log the rest, so State stays the single place that builds sessions."""
import json
import subprocess
import threading
import time
import uuid
from itertools import chain
from pathlib import Path

from . import attach, claude_cli, events, redact
from . import harness as harness_pkg

WATCH_S = 0.5
CHAT_TEXT = 4000
CMD_PROMPT_MAX = 30000  # Command Code takes the prompt in argv


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


def chat(path: Path, cwd: str = "", limit: int = 200, harness: str = "claude") -> list:
    """The window run's conversation, read by the harness's adapter (prompts with the files Fred attached,
    assistant text, tool calls, results)."""
    _, lines = read_lines(path, 0)
    return harness_pkg.get(harness).chat(lines, cwd)[-limit:]


def result_record(session_id: str, summary: dict, exit_code, stopped: bool, timed_out: bool = False) -> dict:
    """The run_ended event line for one finished process; `summary` is the adapter's summary() of the turn.
    cost and tokens are left out when the adapter did not report them (never 0)."""
    subtype = "error_step_timeout" if timed_out else summary.get("subtype", "")
    rec = {"event": "run_ended", "session_id": session_id, "exit": exit_code,
           "stopped": stopped, "interrupted": not summary.get("subtype") and not stopped and not timed_out}
    if subtype:
        rec["subtype"] = subtype
    if summary.get("cost") is not None:
        rec["cost"] = summary["cost"]
    if summary.get("tokens") is not None:
        rec["tokens"] = summary["tokens"]
    if summary.get("denials"):
        rec["denials"] = summary["denials"]
    return rec


class RunManager:
    """One per service. `live` holds the processes this service started (it owns their stdin)."""

    def __init__(self, cfg: dict, folder: Path, exe: list = None, exes: dict = None):
        self.cfg = cfg
        self.folder = Path(folder)
        self.runs = self.folder / "runs"
        self.exe = exe              # the Claude command prefix (every earlier caller)
        self.exes = exes or {}      # {harness name: command prefix} for the other adapters
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

    def set_route(self, sid: str, model: str, effort: str) -> None:
        """The route the next turn of this window run starts on (de-escalate starts no turn itself)."""
        meta = self.meta(sid)
        if meta:
            meta.update(model=model, effort=effort)
            self._save_meta(meta)

    def emit(self, rec: dict) -> None:
        rec = dict(rec, ts=round(time.time(), 3))
        events.append(self.folder, rec)

    def exe_for(self, name: str):
        return self.exe if name == "claude" else self.exes.get(name)

    def meta_harness(self, sid: str) -> str:
        return (self.meta(sid) or {}).get("harness") or "claude"

    def chat_of(self, sid: str, limit: int = 200) -> list:
        meta = self.meta(sid) or {}
        return chat(self.stream_path(sid), meta.get("cwd", ""), limit, meta.get("harness") or "claude")

    def is_live(self, sid: str) -> bool:
        with self.lock:
            proc = self.live.get(sid)
        if proc is not None:
            return proc.poll() is None
        meta = self.meta(sid)
        return bool(meta and not meta.get("ended") and claude_cli.pid_alive(meta.get("pid")))

    # -- start ----------------------------------------------------------------------
    def start(self, cwd: str, prompt: str, model: str, effort: str, resume: str = None,
              title: str = "", route: str = "", reason: str = "", prep: str = "",
              fork: str = "", kind: str = "run", extra: dict = None, files: list = (),
              disallow: tuple = (), tools: str = "", budget: float = 0.0, max_turns: int = 0,
              harness: str = "claude", read_only: bool = False, strict_mcp: bool = False) -> str:
        """A new run, a new turn of a window run (`resume`), or a window copy of another chat (`fork`).
        `kind` (run, continue, verify, handoff, escalate) and `extra` go into the run_started line.
        `files` (attach.parse) go inline after the prompt (Claude only); the stream file keeps their summary only.
        The step limits (`disallow`, `tools` where "" is the default set, `budget`, `max_turns`) are kept in the
        run meta; a resumed turn given none reuses them, so a retry or a STOP answer keeps its restrictions.
        `strict_mcp` (plan 23, Claude only): the run loads no MCP server; kept in the same limits.
        `harness` is taken by a new run only: a resume reads it from the run's meta, a fork from the forked run's."""
        sid = resume or str(uuid.uuid4())
        old = self.meta(sid) or {}
        forked = (self.meta(fork) or {}) if fork else {}
        if resume:
            harness = old.get("harness") or "claude"
        elif fork:
            harness = forked.get("harness") or "claude"
        try:
            adapter = harness_pkg.get(harness)
        except KeyError:
            raise RunError(f"unknown harness {harness}") from None
        exe = self.exe_for(harness)
        if not exe:
            raise RunError("claude.exe not found; set \"claude_exe\" in config.json" if harness == "claude"
                           else f"{harness}: not found")
        if resume and self.is_live(sid):
            raise RunError("this session is still running")
        if harness == "cmd" and len(prompt) > CMD_PROMPT_MAX:
            raise RunError(f"prompt too long for {harness} ({len(prompt)} chars)")
        harness_sid = sid  # the id the command resumes or forks: the console's for Claude, the CLI's otherwise
        if harness != "claude":
            if resume:
                harness_sid = old.get("harness_session") or ""
            elif fork:
                harness_sid = forked.get("harness_session") or ""
            if (resume or fork) and not (harness_sid and adapter.RESUME):
                raise RunError("this session cannot be resumed: no harness session id")
        self.runs.mkdir(parents=True, exist_ok=True)
        limits = {"disallow": list(disallow), "tools": tools or "", "budget": budget, "max_turns": max_turns,
                  "strict_mcp": bool(strict_mcp)}
        if resume and not (disallow or tools or budget or max_turns or strict_mcp) and old.get("limits"):
            limits = old["limits"]
        if not adapter.CAPS:
            limits["timeout_s"] = int(self.cfg.get("step_timeout_s") or 0)
        if resume and not read_only:
            read_only = bool(old.get("read_only"))
        model_prompt = prompt
        if harness != "claude" and files:  # only Claude takes attachments: the model gets their names
            names = ", ".join(f["name"] for f in attach.summary(files))
            model_prompt += f"\n\nAttached files: {names} (this harness cannot read them)"
        common = dict(prompt=model_prompt, resume=bool(resume), fork=harness_sid if fork else "",
                      read_only=read_only, budget=limits["budget"], max_turns=limits["max_turns"],
                      name=redact.clip(title, 60))
        if harness == "claude":
            common.update(fork=fork, tools=limits["tools"] or None, disallow=tuple(limits["disallow"]),
                          blocks=attach.blocks(files), strict_mcp=bool(limits.get("strict_mcp")))
        elif harness == "opencode":
            pfile = self.runs / f"{sid}.prompt.md"
            pfile.write_text(model_prompt if prompt.startswith("/") else model_prompt + claude_cli.STOP_FOOTER,
                             encoding="utf-8")
            common.update(variants=(self.cfg.get("effort_variant") or {}).get(model), prompt_file=str(pfile))
        try:
            cmd, stdin = adapter.run_command(exe, model, effort, cwd, harness_sid, **common)
        except ValueError as exc:
            raise RunError(str(exc)) from None
        path = self.stream_path(sid)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "cc_prompt", "ts": time.time(), "text": prompt,
                                 "files": attach.summary(files)}, ensure_ascii=False) + "\n")
        offset = path.stat().st_size
        proc = self._spawn(cmd, cwd, path, stdin, claude_cli.child_env() | adapter.env(read_only),
                           close_stdin=not adapter.INTERRUPT)
        with self.lock:
            self.live[sid] = proc
            self.stopping.discard(sid)
        start_commit = claude_cli.git_head(cwd)
        started = time.time()
        self._save_meta({"session_id": sid, "pid": proc.pid, "cwd": cwd, "model": model, "effort": effort,
                         "offset": offset, "started": started, "ended": None,
                         "start_commit": old.get("start_commit") or start_commit,
                         "start_route": old.get("start_route") or f"{model}/{effort}",  # de-escalate goes back here
                         "limits": limits, "harness": harness,
                         "harness_session": old.get("harness_session", "") if resume else "",
                         "read_only": bool(read_only), "timed_out": False})
        rec = {"event": "run_started", "session_id": sid, "cwd": cwd, "project": Path(cwd).name,
               "project_dir": cwd, "pid": proc.pid, "harness": harness,
               "model": model, "effort": effort, "resume": bool(resume), "start_commit": start_commit,
               "kind": kind}
        for key, value in (("title", title), ("route", route), ("reason", reason), ("prep", prep),
                           ("forked_from", fork)):
            if value:
                rec[key] = value
        rec.update(extra or {})
        self.emit(rec)
        threading.Thread(target=self._watch, args=(sid, proc, path, offset, adapter, started),
                         name=f"run-{sid[:8]}", daemon=True).start()
        return sid

    def _spawn(self, cmd: list, cwd: str, path: Path, stdin: bytes = None, env: dict = None,
               close_stdin: bool = False):
        """Start the process with stdout and stderr into the stream file, write `stdin` when given and close
        it when the adapter has no interrupt (a CLI reading piped stdin would wait for an EOF otherwise)."""
        out = open(path, "ab")
        try:
            kwargs = dict(cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=subprocess.STDOUT,
                          env=env if env is not None else claude_cli.child_env())
            try:  # leave any job object so closing the window's parent cannot take the run with it
                proc = subprocess.Popen(cmd, creationflags=claude_cli.NO_WINDOW | claude_cli.BREAKAWAY, **kwargs)
            except OSError:
                proc = subprocess.Popen(cmd, creationflags=claude_cli.NO_WINDOW, **kwargs)
            claude_cli.join_service_job(proc.pid)  # the run ends with this service, never as an orphan
        finally:
            out.close()
        try:
            if stdin is not None:
                proc.stdin.write(stdin)
                proc.stdin.flush()
            if close_stdin:
                proc.stdin.close()
        except OSError:  # the process is already gone: _watch reports how it ended
            pass
        return proc

    def _append(self, path: Path, rec: dict) -> None:
        """One service line at the end of the stream (after a last line the process left unterminated)."""
        try:
            with open(path, "rb+") as fh:
                fh.seek(0, 2)
                lead = b""
                if fh.tell():
                    fh.seek(-1, 2)
                    lead = b"" if fh.read(1) == b"\n" else b"\n"
                fh.write(lead + json.dumps(rec).encode("utf-8") + b"\n")
        except OSError:
            pass

    def _watch(self, sid: str, proc, path: Path, offset: int, adapter, started: float) -> None:
        """Close stdin after the result line (stream-json input waits for more otherwise). A capless adapter
        (no turn or spend flag) is stopped once the run is older than step_timeout_s: a cap, not Fred's Stop."""
        seen, timed_out = False, False
        while True:
            offset, lines = read_lines(path, offset)
            seen = seen or any(adapter.is_result(d) for d in lines)
            if (seen or proc.poll() is not None) and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
            if proc.poll() is not None:
                self._append(path, {"type": "cc_exit", "code": proc.returncode, "ts": time.time()})
                break
            limit = self.cfg.get("step_timeout_s") or 0
            if not adapter.CAPS and limit > 0 and not timed_out and time.time() - started > limit:
                timed_out = True  # stopping is NOT set: this is a cap
                meta = self.meta(sid)
                if meta:
                    meta["timed_out"] = True
                    self._save_meta(meta)
                try:
                    adapter.stop(proc)
                except (OSError, ValueError):
                    pass
            time.sleep(WATCH_S)
        self._finish(sid, proc.returncode, timed_out)
        with self.lock:
            if self.live.get(sid) is proc:
                del self.live[sid]

    def _finish(self, sid: str, exit_code, timed_out: bool = False) -> None:
        with self.lock:
            stopped = sid in self.stopping
            self.stopping.discard(sid)
        meta = self.meta(sid) or {"session_id": sid}
        if meta.get("ended"):
            return
        adapter = harness_pkg.get(meta.get("harness") or "claude")
        _, lines = read_lines(self.stream_path(sid), meta.get("offset", 0))  # this turn only
        summary = adapter.summary(lines)
        if not (exit_code is not None or any(adapter.is_result(d) for d in lines)):
            summary = dict(summary, subtype="")  # no result and no exit: the turn was cut
        if summary.get("session_id") and not meta.get("harness_session") and summary["session_id"] != sid \
                and (meta.get("harness") or "claude") != "claude":
            meta["harness_session"] = summary["session_id"]
        meta["ended"] = time.time()
        self._save_meta(meta)
        self.emit(result_record(sid, summary, exit_code, stopped, timed_out))

    # -- stop -----------------------------------------------------------------------
    def stop(self, sid: str) -> str:
        adapter = harness_pkg.get(self.meta_harness(sid))
        with self.lock:
            proc = self.live.get(sid)
            if proc is not None:  # ours: the adapter interrupts (Claude) or kills the tree (no interrupt)
                if proc.poll() is not None:
                    return "not running"
                self.stopping.add(sid)
                try:
                    return adapter.stop(proc)
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

    def forget(self, sid: str) -> int:
        """Delete the stream and the meta of an ended run (the task clear); returns the bytes freed."""
        if self.meta(sid) is None:
            raise RunError("not a window run")
        if self.is_live(sid):
            raise RunError("this session is still running")
        freed = 0
        for path in (self.stream_path(sid), self.meta_path(sid), self.runs / f"{sid}.prompt.md"):
            try:
                size = path.stat().st_size
                path.unlink()
                freed += size
            except OSError:
                pass
        return freed

    # -- recovery -------------------------------------------------------------------
    def reconcile(self) -> int:
        """Runs started by an earlier service: emit run_ended once their process is gone, or once its turn
        has a result line (an orphan left alive after its service died; no service can write to it again).
        No result line and a dead process means the turn was cut (crash, shutdown): Interrupted."""
        if not self.runs.exists():
            return 0
        done = 0
        for meta_file in self.runs.glob("*.json"):
            sid = meta_file.stem
            with self.lock:
                if sid in self.live:
                    continue
            meta = self.meta(sid)
            if not meta or meta.get("ended"):
                continue
            _, lines = read_lines(self.stream_path(sid), meta.get("offset", 0))
            is_result = harness_pkg.get(meta.get("harness") or "claude").is_result
            if not any(is_result(d) for d in lines) and claude_cli.pid_alive(meta.get("pid")):
                continue
            self._finish(sid, None)
            done += 1
        return done

    def open_terminal(self, sid: str) -> None:
        meta = self.meta(sid)
        if not meta:
            raise RunError("not a window run")
        name = meta.get("harness") or "claude"
        adapter = harness_pkg.get(name)
        argv = adapter.terminal_command(self.exe_for(name) or [], meta.get("harness_session") or sid,
                                        meta.get("model", ""), meta.get("effort", ""))
        if argv is None:
            raise RunError("claude only")
        if self.is_live(sid):
            raise RunError("stop the run first: two writers on one session")
        subprocess.Popen(argv, cwd=meta["cwd"],
                         env=claude_cli.child_env(), creationflags=claude_cli.NEW_CONSOLE)


def prune(folder: Path, retention_days: int, now: float = None) -> list:
    """Delete runs/* and preps/* files not touched for `retention_days`."""
    cutoff = (now or time.time()) - retention_days * 86400
    removed = []
    for sub in ("runs", "preps"):
        for path in sorted(chain((Path(folder) / sub).glob("*.json*"), (Path(folder) / sub).glob("*.prompt.md"))):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed.append(f"{sub}/{path.name}")
            except OSError:
                pass
    return removed
