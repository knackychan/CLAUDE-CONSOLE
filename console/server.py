"""The console service: reads the event log, keeps the state, serves the window over HTTP + SSE,
starts, stops and resumes window runs (phase 2), and pulls the levers (phase 3)."""
import copy
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import (attach, brief, claude_cli, compact, events, guard, harness, levers, paths, prep, redact, review,
               routing, runs, tasks, transcript, usage)
from .state import MAX_STEPS, WRITE_TOOLS, State, norm_dir

WEB = Path(__file__).resolve().parent.parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/doto.woff2": ("doto.woff2", "font/woff2")}
POLL_S = 1.0
TICK_S = 15.0
HISTORY_S = 60.0  # the Usage page's scan of every transcript
STORAGE_S = 3600.0  # the data folder's size line is recomputed this often
APP_ID = "claude-console"
MAX_BODY = 256 * 1024
MAX_FILES_BODY = attach.MAX_TOTAL * 4 // 3 + MAX_BODY  # /api/prep, /api/run and /api/continue carry base64 files
FILE_ROUTES = ("/api/prep", "/api/run", "/api/continue")
MAX_PROMPT = 20000
BUSY = {"running", "quiet", "stall"}
READ_MAX_TURNS = 15  # a scout or search on an adapter with a turn cap (plan 23 replaces it with read_max_turns)
PROBE_S = 20
READ_ONLY_TOOLS = "Read,Grep,Glob"  # a kind whose tools are exactly these is read only


class Hub:
    """Owns the State. One thread polls the log; readers wait on `changed`."""

    def __init__(self, cfg: dict, folder: Path, exe: list = None, exes: dict = None):
        self.cfg = cfg
        self.folder = Path(folder)
        self.state = State(cfg)
        self.reader = events.LogReader(folder)
        self.runs = runs.RunManager(cfg, folder, exe)  # runs.exes is filled by the probe
        self.exes = dict(exes or {})  # {harness: command prefix} given by the caller (the tests' fakes)
        self.versions_h = {}  # harness -> version string
        self.found = {}  # harness -> bool
        self.usage = usage.Usage(cfg["prices"])
        self.history = usage.History(cfg["prices"])
        self.usage_days = {}  # day -> totals: every transcript merged with usage-days.json
        self.usage_ready = False
        self.preps = {}  # Prep jobs on the window's strip: id -> {id, project_dir, raw, ts, state, card | error}
        self.user_home = Path.home()  # where ~/.claude/skills is looked up (tests point it elsewhere)
        self.lock = threading.Lock()
        self.changed = threading.Condition(self.lock)
        self.tasks = tasks.load_all(folder)  # plan 17: id -> task; the dict itself changes under self.lock
        self.tlock = threading.RLock()  # one task move at a time: advance, create, the lever routes, the brief thread
        self._notes = {}  # session id -> (stream size, live note state), for _live_note
        self.briefing = set()  # ids of the tasks whose brief thread is running
        self.storage = {}  # usage.folder_sizes of the data folder, refreshed hourly on the usage thread
        self.storage_at = 0.0
        self.version = 0
        self.auto_since = time.time()  # older verdicts never trigger an automatic step
        self._stop = threading.Event()
        self.models_mtime = self._models_mtime()  # models.json as cfg["models"] was read
        self.models_error = ""
        self.probing = threading.Thread(target=self.probe, name="probe", daemon=True)
        self.probing.start()

    # -- plan 5: harnesses and models.json -----------------------------------------------
    @staticmethod
    def _models_mtime():
        try:
            return (paths.home() / "models.json").stat().st_mtime_ns
        except OSError:
            return None

    def reload_models(self, force: bool = False) -> None:
        """Reread models.json when its mtime changed (or `force`); a file with an error keeps the last good lists."""
        mtime = self._models_mtime()
        if not force and mtime == self.models_mtime:
            return
        models, error = paths.load_models(write=False)
        with self.lock:
            self.models_mtime, self.models_error = mtime, error
            if not error:
                self.cfg["models"] = models
                if isinstance(models.get("claude"), dict) and models["claude"]:
                    self.cfg["ladder"] = paths._ladder_from(models["claude"], self.cfg.get("ladder") or {})
            self.version += 1
            self.changed.notify_all()

    def models_file(self) -> dict:
        count = sum(len(v) for v in (self.cfg.get("models") or {}).values() if isinstance(v, dict))
        return {"path": str(paths.home() / "models.json"), "count": count, "error": self.models_error}

    def probe(self, names=None) -> dict:
        """For each harness that is on: find its exe and run its version command (never a prompt). Never raises:
        a failure is found False, version "" and a line in the service log."""
        for name in names or harness.NAMES:
            cmd, version = None, ""
            try:
                if name == "claude":
                    cmd = self.runs.exe
                elif harness.is_on(self.cfg, name):
                    cmd = self.exes.get(name)
                    if not cmd:
                        found = harness.find_exe(self.cfg, name)
                        cmd = [found] if found else None
                if cmd:
                    adapter = harness.get(name)
                    try:
                        out = subprocess.run(adapter.version_command(list(cmd)), capture_output=True, text=True,
                                             stdin=subprocess.DEVNULL, timeout=PROBE_S, creationflags=claude_cli.NO_WINDOW,
                                             env=claude_cli.child_env() | adapter.env(False))
                        lines = (out.stdout.strip() or out.stderr.strip()).splitlines()
                        version = redact.clip(lines[0], 60) if lines else ""
                        if out.returncode != 0 and name != "claude":
                            raise OSError(f"{name} --version exited {out.returncode}")
                    except (OSError, subprocess.SubprocessError, ValueError) as exc:
                        version = ""
                        if name != "claude":
                            cmd = None
                        self._log(f"probe {name}: {type(exc).__name__}: {exc}")
            except Exception as exc:  # whatever went wrong, the harness is not found
                cmd, version = (self.runs.exe if name == "claude" else None), ""
                self._log(f"probe {name}: {type(exc).__name__}: {exc}")
            with self.lock:
                self.found[name], self.versions_h[name] = bool(cmd), version
                if name != "claude":
                    if cmd:
                        self.runs.exes[name] = list(cmd)
                    else:
                        self.runs.exes.pop(name, None)
                self.version += 1
                self.changed.notify_all()
        return self.harnesses()

    def _log(self, line: str) -> None:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            with open(self.folder / "console.log", "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
        except OSError:
            pass

    def harnesses(self) -> dict:
        return {name: {"on": harness.is_on(self.cfg, name), "found": bool(self.runs.exe) if name == "claude" else bool(self.found.get(name)),
                       "version": self.versions_h.get(name, ""), "models": harness.models_of(self.cfg, name),
                       "tiers": list(harness.get(name).TIERS if name in harness.REGISTRY else claude_cli.MODELS)}
                for name in harness.NAMES}

    def set_harness(self, name: str, on: bool) -> dict:
        if name == "claude" and not on:
            raise ValueError("Prep and the brief pass run on Claude")
        paths.set_harness(self.folder, name, on)  # ValueError when config.json cannot be read
        with self.lock:
            section = self.cfg.setdefault("harnesses", {}).setdefault(name, {"on": False, "exe": ""})
            section["on"] = bool(on)
        return self.probe([name])

    def rung_ok(self, rung, kind: str = "") -> str:
        """"" when `rung` may run a step of `kind` ("" = a plain Run), else the reason (README 3.6)."""
        name, bare = claude_cli.split_rung(rung)
        if name != "claude":
            if not harness.is_on(self.cfg, name):
                return f"{name} is off"
            if not self.found.get(name):
                return f"{name}: not found on PATH"
        if not isinstance(rung, str) or not claude_cli.known_model(self.cfg, rung):
            return "unknown model or effort"
        if name in ("opencode", "cmd") and kind:
            if kind in ("verify", "fix"):
                return f"{name}: not on verify or fix steps"
            if claude_cli.tier_of(rung, self.cfg) != "opus" and (tasks.RULES.get(kind) or ("haiku",))[0] not in (
                    "haiku", "sonnet"):
                return f"{name}: {bare} is not a think model"
        return ""

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
        if time.time() - self.storage_at >= STORAGE_S:  # at start, then once an hour: one os.walk
            sizes = usage.folder_sizes(self.folder)
            with self.lock:
                self.storage, self.storage_at = sizes, time.time()

    def usage_report(self) -> dict:
        with self.lock:
            days, ready, storage = self.usage_days, self.usage_ready, self.storage
        today = usage.day_of(time.time())
        return {"ready": ready, "today": today, "first": min(days) if days else "",
                "limit": self.cfg["daily_budget_usd"], "days": days,
                "weeks": usage.weeks(days, today), "months": usage.months(days, today),
                "storage": storage, "storage_warn_mb": self.cfg["storage_warn_mb"]}

    def history_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.read_history()
            except OSError:
                pass
            self._stop.wait(HISTORY_S)

    def start_prep(self, project_dir: str, raw: str, files: list = ()) -> str:
        """Prep in its own thread: the request answers at once and the strip shows the job as it runs.
        `files` (attach.parse) wait with the job, in memory only, for the run its card starts."""
        job = prep.new_id()
        with self.lock:
            self.preps[job] = {"id": job, "project_dir": project_dir, "raw": raw, "ts": time.time(),
                               "state": "running", "files": list(files)}
            self.version += 1
            self.changed.notify_all()
        threading.Thread(target=self._prep_job, args=(job, project_dir, raw, attach.note(files)),
                         name="cc-prep", daemon=True).start()
        return job

    def prep_files(self, job) -> list:
        """The files waiting with a Prep job ([] for an unknown job)."""
        with self.lock:
            return list(self.preps.get(job, {}).get("files") or []) if isinstance(job, str) else []

    def _prep_job(self, job: str, project_dir: str, raw: str, note: str = "") -> None:
        """`note` names the attached files for Prep; the card on the strip keeps the text as typed."""
        try:
            card = prep.run_prep(self.cfg, self.folder, project_dir, raw + note, self.runs.exe, job)
            end = {"state": "done", "card": dict(card, raw=raw)}
        except Exception as exc:  # whatever went wrong, the job ends: a pill never spins forever
            end = {"state": "failed", "error": str(exc) or type(exc).__name__}
        self._end_job(job, end)

    def _end_job(self, job: str, end: dict) -> None:
        with self.lock:
            if job in self.preps:  # dropped while it ran: nothing to show
                self.preps[job].update(end)
                self.version += 1
                self.changed.notify_all()

    def start_review(self, project_dir: str) -> str:
        """The rules review (plan 22) rides the Prep strip: same dict, same drop route, `kind` "review"."""
        job = review.new_id()
        with self.lock:
            self.preps[job] = {"id": job, "kind": "review", "project_dir": project_dir, "raw": "Review rules",
                               "ts": time.time(), "state": "running", "files": []}
            self.version += 1
            self.changed.notify_all()
        threading.Thread(target=self._review_job, args=(job, project_dir), name="cc-review", daemon=True).start()
        return job

    def _review_job(self, job: str, project_dir: str) -> None:
        try:
            end = {"state": "done", "card": review.run_review(self.cfg, self.folder, project_dir, self.runs.exe, job)}
        except Exception as exc:
            end = {"state": "failed", "error": str(exc) or type(exc).__name__}
        self._end_job(job, end)

    def drop_prep(self, job: str) -> bool:
        """Off the strip: the card was run, edited or dismissed. Its preps/<id>.json stays."""
        with self.lock:
            if self.preps.pop(job, None) is None:
                return False
            self.version += 1
            self.changed.notify_all()
        return True

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
            self.auto_steps()
            self.advance()
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
            snap = self.state.snapshot(now, self.usage, self.usage_days.get(usage.day_of(now)))
            snap["preps"] = sorted(({**{k: v for k, v in j.items() if k != "files"},
                                     "attached": attach.summary(j["files"])} for j in self.preps.values()),
                                   key=lambda j: j["ts"])
            rows = {r["id"]: r for r in snap["sessions"]}
            snap["tasks"] = sorted((task_row(t, self._live_note, rows) for t in self.tasks.values()),
                                   key=lambda r: r["updated"], reverse=True)
            loose = [r for r in snap["sessions"] if not r.get("task")]  # a task counts once, not per step session
            count = lambda g: sum(1 for r in loose if r["group"] == g)
            tg = lambda g: sum(1 for t in snap["tasks"] if t["group"] == g)
            snap["counts"] = {"needs": count("needs") + tg("needs"),
                              "replied": count("replied"), "working": count("working") + tg("working"),
                              "done": count("done"), "empty": count("empty")}
            return snap

    def steps(self, session_id: str, limit: int = 200) -> list:
        with self.lock:
            return self.state.steps(session_id, limit)

    def session(self, session_id: str):
        with self.lock:
            s = self.state.sessions.get(session_id)
            if s is None:
                return None
            return {"cwd": s.cwd, "first_cwd": s.first_cwd or s.cwd, "window": s.window, "title": s.title,
                    "model": s.model, "effort": s.effort, "harness": s.harness, "prep": s.prep, "start_commit": s.start_commit,
                    "project": s.project, "project_dir": s.project_dir, "route": s.route,
                    "run_live": s.run_live, "state": self.state.state_of(s, time.time()),
                    "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated,
                    "transcript_path": s.transcript_path, "ctx_tokens": s.ctx_tokens, "last_ts": s.last_ts,
                    "handoff_by": s.handoff_by if s.handed_off else "",
                    "task": s.task, "step": s.step, "cost": s.cost, "stop_question": s.stop_question,
                    "interrupted": s.interrupted, "stopped": s.stopped, "denied": s.denied, "failed": s.failed,
                    "verdict_ts": s.verdict_ts}

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
        hname = (meta.get("harness") or "claude") if window else "claude"
        adapter = harness.get(hname)
        cwd = meta.get("cwd") if window else s["first_cwd"]  # Claude Code files a chat under its start folder
        if not self.allowed(s["project_dir"]):
            base = "runs are off in this project: pick it on the home view and allow runs"
        elif not self.runs.exe_for(hname):
            base = ("claude.exe not found; set \"claude_exe\" in config.json" if hname == "claude"
                    else f"{hname}: not found")
        elif s["run_live"] or s["state"] in BUSY or self.runs.is_live(session_id):
            base = "still working: wait until it stops"
        elif not cwd or not os.path.isdir(cwd):
            base = "the session's folder is gone"
        else:
            base = ""
        model, effort = self.route_of(session_id, s)
        step = levers.escalate_step(model, effort) if hname == "claude" else None
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
        start = routing.parse((meta or {}).get("start_route"))
        if base:
            deescalate = base
        elif not window:
            deescalate = "only for window runs"
        elif s["verdict"] != "PASS":
            deescalate = "only after a PASS verdict"
        elif not start:
            deescalate = "no starting route recorded"
        elif routing.rank(start) >= routing.rank((model, effort)):
            deescalate = "already on the task's starting route"
        else:
            deescalate = ""
        handoff = base or ("" if levers.handoff_ready(s["project_dir"], self.user_home) else
                           "the session-handoff skill is not installed here: copy "
                           "dotclaude/skills/session-handoff to ~/.claude/skills")
        nxt = base or ("" if s["handoff_by"] else "only after a Hand off")  # a new task seeded with the note
        cont = base
        if hname != "claude" and not base:  # a harness resumes where its adapter can and has a session id
            cont = ("" if adapter.RESUME and meta.get("harness_session") else "this session cannot be resumed")
        out = {"continue": cont, "verify": base, "handoff": handoff, "escalate": escalate, "next": nxt,
               "handoff_fresh": s["verdict"] == "PASS" and not s["task"],  # a new chat from a brief, no re-read
               "deescalate": deescalate, "deescalate_to": "/".join(start) if start else "",
               "after_verify": list(levers.after_verify(s["verdict"])), "route": f"{model}/{effort}", "escalate_to": "/".join(step) if step else "",
               "fork": not window, "cwd": cwd or "", "cold": None if base else self.cold(s, model),
               "terminal": "" if adapter.terminal_command([], "x", "", "") is not None else "claude only",
               "harness": hname}
        if hname != "claude":  # the hooks, the skills and the terminal chat are Claude Code's
            for lever in ("verify", "handoff", "escalate", "deescalate", "terminal"):
                out[lever] = "claude only"
            out["deescalate_to"], out["escalate_to"] = "", ""
        task = self.tasks.get(s["task"]) if s["task"] else None
        if task and task["state"] in ("planned", "running", "waiting"):  # a working chain owns its steps' turns
            cs = tasks.current_step(task)
            asked = (task["state"] == "waiting" and task["why"].startswith("asks: ")
                     and cs is not None and cs["session"] == session_id)
            for lever in ("continue", "verify", "handoff", "escalate", "deescalate"):
                if not (lever in ("continue", "handoff") and asked):  # answer the step's question, or hand off
                    out[lever] = base or "a task step: use the task's levers"
        return out

    def pull(self, sid, lever: str, text: str = "", confirm: bool = False, files: list = ()) -> tuple:
        """Continue (also STOP answers and Resume), Verify, Handoff, Escalate: a new turn of a window
        run, or a window copy (fork) of a VS Code / terminal chat, which stays as it is. De-escalate starts
        no turn: the next one runs on the task's starting route. Returns (status, body); a click and the
        automatic step (auto_steps) pass the same gate, self.levers. `files` (attach.parse) go with a
        Continue only."""
        info = self.levers(sid)
        if info is None:
            return 404, {"error": "unknown session"}
        if info[lever]:
            return 409, {"error": info[lever]}
        fresh = lever == "handoff" and info["handoff_fresh"]  # nothing is re-read: no cold-cache confirm
        if info["cold"] and not confirm and lever != "deescalate" and not fresh:  # the page asks with a second click
            c = info["cold"]
            return 409, {"error": f"cold cache: {c['tokens'] // 1000}K tokens, idle {c['idle_s'] / 3600:.0f} h, "
                                  f"would be re-read at full price (about ${c['cost']:.2f}); open the session to "
                                  "confirm, or start a new task there with a brief"}
        if lever == "deescalate":
            self.runs.set_route(sid, *routing.parse(info["deescalate_to"]))
            return 200, {"session": sid, "route": info["deescalate_to"]}
        s = self.session(sid)
        model, effort = self.route_of(sid, s)
        extra, miss = {}, ""
        if lever == "continue":
            if not text:
                return 400, {"error": "empty prompt"}
        elif lever == "verify":
            text = levers.VERIFY_TEXT
        elif lever == "handoff" and fresh:  # after a PASS: a new chat runs the skill on the session's brief
            text = levers.HANDOFF_TEXT + " " + self.brief_text(sid, s, "handoff")
            model, effort = levers.HANDOFF_ROUTE
            extra = {"handoff_of": sid}
        elif lever == "handoff":
            text = levers.HANDOFF_TEXT
        else:  # escalate: one step up, once, and the miss is logged for Prep
            new_model, new_effort = levers.escalate_step(model, effort)
            route_from, route_to = f"{model}/{effort}", f"{new_model}/{new_effort}"
            miss = levers.miss_line(s["project"], s["route"], route_from, route_to, s["verdict_detail"])
            text = levers.escalate_text(s["verdict_detail"], new_model, new_effort)
            model, effort = new_model, new_effort
            extra = {"escalated": f"{route_from} -> {route_to}"}
        fork = sid if info["fork"] and not fresh else ""
        with self.tlock:  # Continue in the current step of a stopped task resumes the task there; Hand off in the
            # current step hands the task over (tasks.fred)
            task = self.tasks.get(s["task"]) if s["task"] and lever in ("continue", "handoff") and not fork else None
            if task and ((lever == "continue" and task["state"] != "stopped")
                         or (tasks.current_step(task) or {}).get("session") != sid):
                task = None
            new = self.runs.start(info["cwd"], text, model, effort, resume=None if fork or fresh else sid, fork=fork,
                                  title="↳ " + (s["title"] or sid[:8]) if fork or fresh else "",
                                  route=s["route"] if fork else "", kind=lever, extra=extra,
                                  files=files if lever == "continue" else ())
            if miss:
                levers.add_miss(self.folder, miss)
            self.poll_once()  # the run_started line first: _ended reads this turn, not the stopped one
            if task:
                ok, _, lines = tasks.fred(task, lever, time.time())
                if ok:
                    self._commit(task, lines)
        return 200, {"session": new}

    def auto_steps(self) -> list:
        """Plan 16 (Fred: b): when a window run's turn ends with a verdict, the service takes the route
        step itself: Escalate after FAIL, de-escalate after PASS. Only verdicts about the last turn that
        arrived while this service runs, never a VS Code or terminal chat, never past a cold-cache
        confirm, and only what self.levers allows. Returns the (session, lever) pairs it pulled."""
        now = time.time()
        with self.lock:
            due = [(s.id, "escalate" if st == "verify_failed" else "deescalate")
                   for s in self.state.sessions.values()
                   if s.window and not s.task and s.verdict_ts >= self.auto_since  # a step's verdict is its chain's
                   for st in [self.state.state_of(s, now)] if st in ("verify_failed", "verified")]
        pulled = []
        for sid, lever in due:
            try:
                if self.pull(sid, lever)[0] == 200:
                    pulled.append((sid, lever))
            except (runs.RunError, OSError):  # a click got there first, or claude did not start
                continue
        return pulled

    # -- plan 17: the task chain ---------------------------------------------------------
    def budget(self) -> dict:
        """model id -> share of its pace used. Sub-plan 18 fills it from the usage windows; {} until then."""
        return {}

    def tier_budget(self) -> dict:
        """tier -> the least share over the tier's rungs (a rung budget() does not list counts as unused): a tier
        is over its pace only when every rung is. What tasks.step_route receives; {} while budget() is."""
        shares, out = self.budget(), {}
        for tier, rungs in (self.cfg.get("ladder") or {}).items():
            if any(rung in shares for rung in rungs):
                out[tier] = min(shares.get(rung, 0) for rung in rungs)
        return out

    def model_id(self, tier: str) -> str:
        """The model to pass for a tier: the first rung of the ladder under budget_warn_at of its pace, else the
        tier alias."""
        shares, warn = self.budget(), self.cfg["budget_warn_at"]
        rungs = (self.cfg.get("ladder") or {}).get(tier) or [tier]
        return next((rung for rung in rungs if shares.get(rung, 0) < warn), tier)

    def last_reply(self, sid: str) -> str:
        """Claude's last message in a session: its window run's stream, or its transcript."""
        if self.runs.meta(sid):
            items = self.runs.chat_of(sid)
        else:
            s = self.session(sid)
            items = transcript.turns(s["transcript_path"]) if s else []
        return next((i["text"] for i in reversed(items) if i["role"] == "claude"), "")

    def brief_text(self, sid: str, s: dict, kind: str) -> str:
        """brief.build from a session's facts (goal, last message, edited files, verdict, git status): no model
        call, nothing written. What a new chat reads instead of the session's context."""
        files = []
        for step in self.steps(sid, MAX_STEPS):
            if step["tool"] in WRITE_TOOLS and step["what"] and step["what"] not in files:
                files.append(step["what"])
        folder = s["project_dir"] if os.path.isdir(s["project_dir"] or "") else s["cwd"]
        return brief.build(kind, goal=transcript.first_prompt(s["transcript_path"]) or s["title"],
                           last=self.last_reply(sid), files=files, verdict=s["verdict"],
                           detail=s["verdict_detail"],
                           status=claude_cli.git_status(folder) if os.path.isdir(folder or "") else [],
                           plan=os.path.isfile(os.path.join(folder or "", "PLAN.md")))

    def _live_note(self, sid: str) -> str:
        """tasks.live_note of a running step's reply so far; the stream is read again only when it grew."""
        path = self.runs.stream_path(sid)
        try:
            size = path.stat().st_size
        except OSError:
            return "writing"
        key, hit = self._notes.get(sid, (None, ""))
        if key != size:
            hit = tasks.live_note(self.final_message(sid)[0])
            self._notes[sid] = (size, hit)
        return hit

    def final_message(self, sid: str) -> tuple:
        """(the last assistant text, the last result's subtype) of a window run's current turn, whole: runs.chat
        cuts a text at 4000 characters, and a step's HANDOFF block stands at the end of its final message. Read
        through the run's adapter; a timed-out run reports error_step_timeout (the retry reason reads it)."""
        meta = self.runs.meta(sid) or {}
        _, lines = runs.read_lines(self.runs.stream_path(sid), meta.get("offset", 0))  # this turn only
        summary = harness.get(meta.get("harness") or "claude").summary(lines)
        return summary["final"], "error_step_timeout" if meta.get("timed_out") else summary["subtype"]

    def _next_step(self, task: dict):
        """The step that would start now: the first of a planned task, the current step when it was reset to
        planned (a retry), the one after a done current step; None when nothing is left."""
        cs = tasks.current_step(task)
        if cs is None:
            return task["steps"][0] if task["steps"] else None
        if cs["state"] == "planned":
            return cs
        if cs["state"] == "done" and cs["n"] < len(task["steps"]):
            return tasks.step(task, cs["n"] + 1)
        return None

    def _route_for(self, task: dict, s: dict) -> dict:
        """tasks.step_route for step `s`, with everything it reads: the checked step, the misses, the last note."""
        return tasks.step_route(
            s["kind"], pick=claude_cli.tier_of(s["pick"], self.cfg) if s["pick"] else "",
            checked=tasks.checked_route(task, s), demand=task["demand"],
            misses=routing.fresh(levers.read_misses(self.folder, task["project"]), self.cfg["miss_floor_days"]),
            prev=tasks.read_note(self.folder, task, task["last_good"]),
            budget=self.tier_budget(), warn_at=self.cfg["budget_warn_at"], effort=task["effort"])

    def task_levers(self, task_id) -> dict:
        """What each task lever would do and why one is off ("" = allowed); None for an unknown id. The one
        gate: advance and the POST handlers both ask it."""
        with self.tlock:
            task = self.tasks.get(task_id) if isinstance(task_id, str) else None
            if task is None:
                return None
            state, owner, cs, nxt = task["state"], task["owner"], tasks.current_step(task), self._next_step(task)
            if not self.allowed(task["project_dir"]):
                base = "runs are off in this project: pick it on the home view and allow runs"
            elif not self.runs.exe:
                base = "claude.exe not found; set \"claude_exe\" in config.json"
            elif not os.path.isdir(task["project_dir"]):
                base = "the task's folder is gone"
            else:
                base = ""
            live = bool(cs and cs["session"] and self.runs.is_live(cs["session"]))
            if base:
                start = base
            elif owner != "service" or (state not in ("planned", "running")
                                        and not (state == "waiting" and task["why"] == "confirm Fable")
                                        and not tasks.held(task)):
                start = f"task is {state}" + (" and paused" if owner == "fred" else "")
            elif cs and cs["state"] == "running":
                start = "a step is running"
            elif nxt is None:
                start = "no step to start"
            elif claude_cli.tier_of(nxt["pick"], self.cfg) == "fable" and not task["fable_ok"]:
                start = "confirm Fable"
            else:
                start = ""
            # Stop, Pause and Clear start nothing: they work in a project taken off the list or a folder gone
            stop = "" if state in ("running", "waiting") else f"task is {state}"
            pause = ("" if owner == "service" and state in ("running", "waiting") else
                     "already paused" if owner == "fred" and state in ("running", "waiting") else f"task is {state}")
            resume = base or ("" if owner == "fred" and state in ("running", "waiting") else "not paused")
            retry = base or ("still working: wait until it stops" if live else
                             "" if state in ("stuck", "stopped") else f"task is {state}")
            confirm = base or ("" if (state == "waiting" and task["why"] == "confirm Fable") or tasks.held(task)
                               else "nothing to confirm")
            clear = ("still working: wait until it stops" if live else
                     "" if state in ("planned", "done", "stuck", "stopped", "handed") else f"task is {state}")
            done = ("still working: wait until it stops" if live else  # Mark done starts nothing
                    "" if state in ("waiting", "stuck", "stopped", "handed") else f"task is {state}")
            route = self._route_for(task, nxt) if nxt else None
            return {"start": start, "stop": stop, "pause": pause, "resume": resume, "retry": retry,
                    "confirm": confirm, "clear": clear, "done": done,
                    "route": f"{cs['model']}/{cs['effort']}" if cs and cs["model"] else "",
                    "next_route": f"{route['model']}/{route['effort']}" if route and not route["hold"] else "",
                    "cwd": task["project_dir"]}

    def _commit(self, task: dict, lines=()) -> None:
        """Chain lines to chain.jsonl, task.json whole, and a new snapshot for the window."""
        if lines:
            tasks.log(self.folder, task["id"], list(lines))
        tasks.save(self.folder, task)
        with self.lock:
            self.version += 1
            self.changed.notify_all()

    def create_task(self, card: dict, steps: list, effort: str, title: str = "") -> str:
        """A task from a Prep card and the step list Fred edited on it; step 1 starts at once."""
        folder = self.allowed(card.get("project_dir"))
        if not folder:
            raise runs.RunError("runs are off in this project: pick it on the home view and allow runs")
        planned = tasks.plan_steps(steps, self.cfg["task_max_steps"])
        if not planned:
            raise runs.RunError("a task needs at least one step")
        # plan_steps keeps tier aliases only; a rung of the ladder that Fred picked on the card is put back
        shown = [i for i in steps if isinstance(i, dict) and i.get("kind") in tasks.PREP_KINDS
                 and isinstance(i.get("goal"), str) and i["goal"].strip()][:self.cfg["task_max_steps"]]
        for item, step in zip(shown, [p for p in planned if p["kind"] in tasks.PREP_KINDS]):
            if item.get("model") not in claude_cli.MODELS and claude_cli.known_model(self.cfg, item.get("model")):
                step["pick"] = item["model"]
        with self.tlock:
            name = redact.clip(title or (card.get("fields") or {}).get("goal") or card.get("raw") or "task", 80)
            task = tasks.new_task(folder, Path(folder).name, name, card["prompt"], planned,
                                  (card.get("route") or {}).get("type") or "", card.get("demand") or {}, card["id"],
                                  effort, time.time())
            tasks.folder(self.folder, task["id"]).mkdir(parents=True, exist_ok=True)
            (tasks.folder(self.folder, task["id"]) / "prompt.md").write_text(task["goal"], encoding="utf-8")
            tasks.save(self.folder, task)
            with self.lock:
                self.tasks[task["id"]] = task
            self.drop_prep(card["id"])
            self.advance()
            self.poll_once()
        return task["id"]

    def start_step(self, task: dict, n: int) -> None:
        """Route step `n` and start its run; a hold waits for Fred, a run that cannot start makes the task stuck."""
        s, now, lines = tasks.step(task, n), time.time(), []
        route = self._route_for(task, s)
        if route["hold"] and task.get("hold_ok") != n:
            tasks._task_to(task, "waiting", route["hold"], now, s, lines)
            return self._commit(task, lines)
        if route["hold"]:  # Fred's Run anyway, for this step only
            route = dict(route, notes=route["notes"] + ["budget: hold released by Fred"], hold="")
            task.pop("hold_ok", None)
        self.reload_models()
        kind, tier = s["kind"], route["model"]
        pick, notes = s["pick"], list(route["notes"])  # a rung Fred picked is used as given, unless the budget moved
        # the step to another tier
        model = pick if pick and pick not in claude_cli.MODELS and claude_cli.tier_of(pick, self.cfg) == tier \
            else self.model_id(tier)
        hname, model_name = claude_cli.split_rung(model)
        if hname != "claude":
            why = self.rung_ok(model, kind)
            if why:  # turned off or not found since Prep, or a cheap rung on a kind it may not run (decision 12)
                model = self.model_id(tier)
                hname, model_name = "claude", model
                word = ("off" if not harness.is_on(self.cfg, claude_cli.split_rung(pick)[0]) else
                        "not found" if "not found" in why else "refused")
                notes.append(f"harness: {claude_cli.split_rung(pick)[0]} {word} -> {model}")
            else:
                notes.append(f"harness: {hname}")
        elif pick and claude_cli.split_rung(pick)[0] != "claude" and not claude_cli.tier_of(pick, self.cfg):
            notes.append(f"model gone from models.json: {pick}")
        route = dict(route, notes=notes)
        retry = task["why"] if s["retries"] == 1 and s["state"] == "planned" else ""
        prompt = tasks.step_prompt(task, s, tasks.read_brief(self.folder, task, task["last_good"]), retry)
        adapter = harness.get(hname)
        read_only = tasks.RULES[kind][2] == READ_ONLY_TOOLS if kind in tasks.RULES else False
        max_turns = (READ_MAX_TURNS if adapter.CAPS and kind in ("scout", "search") else
                     self.cfg["design_max_turns"] if kind == "design" else 0)
        try:
            sid = self.runs.start(
                task["project_dir"], prompt, model_name, route["effort"],
                title=f"{task['title']} · {n}/{len(task['steps'])} {kind}", route=kind,
                reason=" · ".join(route["notes"]), prep=task["prep"], kind="task",
                extra={"task": task["id"], "step": n}, disallow=tasks.DISALLOW, tools=tasks.RULES[kind][2],
                budget=self.cfg["task_step_budget_usd"], max_turns=max_turns, harness=hname, read_only=read_only)
        except (runs.RunError, OSError) as exc:
            tasks._task_to(task, "stuck", str(exc), now, s, lines)
            return self._commit(task, lines)
        lines = tasks.start_step(task, n, sid, dict(route, model=model),
                                 (self.runs.meta(sid) or {}).get("start_commit", ""), now)
        s["tier"], s["harness"] = tier, hname
        self._commit(task, lines)
        self.poll_once()

    def advance(self) -> list:
        """One pass over the tasks the service owns (the hub loop calls it every second): read the state and the
        files, call tasks.* for every decision, start what may start. Returns [(task id, action)]."""
        acted = []
        with self.tlock:
            for task in list(self.tasks.values()):
                try:
                    action = self._advance_one(task)
                except Exception as exc:  # one bad task never stops the hub loop: it waits for Fred, stuck
                    action = self._broken(task, exc)
                if action:
                    acted.append((task.get("id", ""), action))
        return acted

    def sync_costs(self, task: dict) -> bool:
        """Each attempt's cost from its session row once its run has ended (a stopped run's cost lands with its
        run_ended, after the Stop); a step's cost is the sum of its attempts. True when anything changed."""
        changed = False
        for st in task["steps"]:
            for a in st.get("attempts") or []:
                if a.get("final") or not a.get("session") or (st["state"] == "running" and a is st["attempts"][-1]):
                    continue  # a running step's session may take more turns (an answered question)
                row, meta = self.session(a["session"]), self.runs.meta(a["session"])
                if row is None or row["run_live"] or (meta and not meta.get("ended")):
                    continue
                a.update(cost=row["cost"], final=True)
                st["cost"] = tasks.step_cost(st)
                changed = True
        return changed

    def _advance_one(self, task: dict) -> str:
        if self.sync_costs(task):
            self._commit(task)
        if task["state"] == "done" and task.get("briefing") and task["id"] not in self.briefing:
            self.start_brief(task, task["briefing"])  # the service restarted while the last brief ran
            return ""
        cs = tasks.current_step(task)
        if task["state"] == "handed" and not task.get("handoff_note") and cs and cs["state"] == "handed":
            return self._handed(task, cs)
        if task["owner"] == "fred" and task["state"] in ("running", "waiting") and cs and cs["state"] == "running":
            return self._ended(task, cs)  # paused: the step that ended is closed; nothing starts after it
        if task["owner"] != "service" or task["state"] not in ("planned", "running", "waiting"):
            return ""
        if cs and cs["state"] == "running":
            return self._ended(task, cs)
        if task["state"] == "waiting":
            return ""  # a hold or a Fable confirm: Fred acts
        return self._go_on(task)

    def _broken(self, task: dict, exc: Exception) -> str:
        """A task move raised (a disk error, a task.json from another version): the task is stuck with the error
        as its why, saved when the disk lets it."""
        now, why = time.time(), redact.clip(f"{type(exc).__name__}: {exc}", 200)
        line = {"ts": now, "step": task.get("current") or 0, "from": f"task:{task.get('state', '')}",
                "to": "task:stuck", "why": why, "session": ""}
        task.update(state="stuck", why=why, updated=now)
        try:
            self._commit(task, [line])
        except Exception:  # the window still shows it stuck
            with self.lock:
                self.version += 1
                self.changed.notify_all()
        return "stuck"

    def _handed(self, task: dict, cs: dict) -> str:
        """Fred's Hand off ran /session-handoff in the step's chat: once that run made the chat Done, its last
        message goes to steps/NN-handoff.md. The task stays handed off until Fred marks it done."""
        s = self.session(cs["session"]) if cs["session"] else None
        text = self.last_reply(s["handoff_by"]) if s and s["handoff_by"] else ""
        if not text:
            return ""
        rel = tasks.write_handoff(self.folder, task, cs, text)
        self._commit(task, [tasks._line(time.time(), cs, "handing", "handed", f"handoff note: {rel}")])
        return "handed"

    def _ended(self, task: dict, cs: dict) -> str:
        """The current step's run: still going, waiting for Fred's answer, or ended (README 3.7). The verdict and
        the question are read in the reply: the Stop hook that also logs them is async and may come late."""
        now, sid = time.time(), cs["session"]
        s = self.session(sid)
        if s is None:  # its first event is not in yet
            return ""
        if s["run_live"]:
            if task["state"] == "waiting":  # Fred answered the question
                lines = []
                tasks._task_to(task, "running", "", now, cs, lines)
                self._commit(task, lines)
            return ""
        meta = self.runs.meta(sid) or {}
        if meta and not meta.get("ended"):  # the watcher has not closed it yet
            return ""
        if task["state"] == "waiting" and "asked" in cs and cs["asked"] == meta.get("started"):
            return ""  # no answer yet: the turn that asked is still the last one
        text, subtype = self.final_message(sid)
        question = s["stop_question"] or tasks.reply_question(text)
        if question:
            cs["asked"] = meta.get("started")
            action, lines = tasks.on_step_ended(task, ok=True, block_error="", verdict="", verdict_detail="",
                                                question=question, now=now)
            self._commit(task, lines)
            return action
        block = tasks.parse_handoff(text)
        block_error = "no HANDOFF block" if block is None else tasks.check_handoff(block)
        # a denial in auto mode is not a failure: the model works around it and its handoff says what is left
        ok = not (s["interrupted"] or s["stopped"] or s["failed"]) and subtype == "success"
        verdict, detail = tasks.reply_verdict(text)
        if not verdict and s["verdict_ts"] >= (cs["started"] or 0):
            verdict, detail = s["verdict"], s["verdict_detail"]
        action, lines = tasks.on_step_ended(task, ok=ok, block_error=block_error, verdict=verdict,
                                            verdict_detail=detail if verdict else "", question="", now=now,
                                            cap=tasks.cap_reason(subtype, meta.get("limits")))
        self.sync_costs(task)
        if action in ("next", "fix", "done"):
            tasks.write_note(self.folder, task, cs, block)
            lesson = tasks.lesson_of(block)
            if lesson:  # plan 22: one line per step that taught something, read by the rules review
                levers.add_lesson(self.folder, levers.lesson_line(task["project"], cs["kind"], lesson, now))
        if action == "fix":
            levers.add_miss(self.folder, task["miss"])
        if action in ("next", "fix", "done"):
            task["briefing"] = cs["n"]  # saved with the transition, so a restart finds the unfinished brief
        self._commit(task, lines)
        if action in ("next", "fix", "done"):  # the last step gets a brief too: Start next chat reads it
            self.start_brief(task, cs["n"])
        if action in ("next", "fix", "retry") and task["owner"] == "service":
            self._go_on(task)
        return action

    def start_brief(self, task: dict, n: int) -> None:
        """The brief between step `n` and the next: Haiku compacts the note in a thread, the code fallback stands
        in when it fails or brief_on is off. task["briefing"] = n until steps/NN-<kind>.brief.md is written."""
        s = tasks.step(task, n)
        nxt = tasks.step(task, n + 1) if n < len(task["steps"]) else None
        raw = tasks.read_note(self.folder, task, n)
        prev = tasks.read_brief(self.folder, task, n - 1)
        task["briefing"] = n
        if not self.cfg["brief_on"]:
            text = compact.fallback(prev, raw)
            self._brief_done(task["id"], n, {"text": text, "cost": 0, "words": len(text.split()),
                                             "fallback": "brief is off"}, raw)
            return
        self.briefing.add(task["id"])
        threading.Thread(target=self._brief_job, args=(copy.deepcopy(task), copy.deepcopy(s), copy.deepcopy(nxt),
                                                       prev, raw), name="cc-brief", daemon=True).start()

    def _brief_job(self, task: dict, s: dict, nxt, prev: str, raw: str) -> None:
        model = self.cfg["brief_model"]
        cfg = dict(self.cfg, brief_model=self.model_id(model) if model in claude_cli.MODELS else model)
        try:
            res = compact.run_brief(cfg, self.runs.exe, task, s, nxt, prev, raw)
        except Exception as exc:  # run_brief never raises; if it does, the chain still goes on
            text = compact.fallback(prev, raw)
            res = {"text": text, "cost": 0, "words": len(text.split()), "fallback": f"{type(exc).__name__}: {exc}"}
        self._brief_done(task["id"], s["n"], res, raw)

    def _brief_done(self, task_id: str, n: int, res: dict, raw: str) -> None:
        """Write the brief, clear the flag, log it; a task that reached done is cleared now (README 3.9)."""
        with self.tlock:
            self.briefing.discard(task_id)
            task = self.tasks.get(task_id)
            if task is None:  # cleared while the pass ran
                return
            s = tasks.step(task, n)
            why = (f"brief fallback: {res['fallback']}" if res["fallback"] else
                   f"brief: {len(raw.split())} -> {res['words']} words, ${res['cost']:.2f}"
                   + (f", cut {len(res['cut'])} findings" if res.get("cut") else ""))
            task["briefing"] = 0
            try:
                tasks.write_brief(self.folder, task, s, res["text"])
                lines = [tasks._line(time.time(), s, "briefing", "briefed", why)]
                if task["state"] == "done" and self.cfg["task_clear_on_done"] and not task.get("cleared"):
                    lines.append(self._clear_done(task, s))
                self._commit(task, lines)
            except OSError:  # the folder is gone (cleared by hand, or the data folder was removed)
                pass

    def _clear_done(self, task: dict, s: dict) -> dict:
        """task_clear_on_done: the notes but the last, and the step streams. Returns the chain line."""
        freed = 0
        for sid in tasks.clear(self.folder, task, keep_last=True):
            try:
                freed += self.runs.forget(sid)
            except runs.RunError:  # already forgotten, or still going
                continue
        return tasks._line(time.time(), s, "task:done", "task:cleared", f"{freed} bytes freed")

    def _go_on(self, task: dict) -> str:
        """Start the step that may start: step 1 of a planned task, a retry, the one after a done step."""
        nxt, now = self._next_step(task), time.time()
        if nxt is None or task["owner"] != "service":  # paused: Resume starts it
            return ""
        cs = tasks.current_step(task)
        if cs and cs["state"] == "done" and task.get("briefing"):  # between steps: the next one reads the brief
            if task["id"] not in self.briefing:
                self.start_brief(task, task["briefing"])  # the service restarted while it ran
            if task.get("briefing"):
                return ""
        if claude_cli.tier_of(nxt["pick"], self.cfg) == "fable" and not task["fable_ok"]:
            lines = []
            tasks._task_to(task, "waiting", "confirm Fable", now, nxt, lines)
            self._commit(task, lines)
            return "wait"
        if self.task_levers(task["id"])["start"]:
            return ""
        self.start_step(task, nxt["n"])
        return "start"

    def task_lever(self, task_id, lever: str) -> tuple:
        """Fred's Stop, Pause, Resume, Retry, Confirm, Clear and Mark done. task_levers decides first; Stop is the run's
        interrupt (runs.stop), never a kill. Returns (status, body)."""
        with self.tlock:
            info = self.task_levers(task_id)
            if info is None:
                return 404, {"error": "unknown task"}
            if info[lever]:
                return 409, {"error": info[lever]}
            task, now = self.tasks[task_id], time.time()
            if lever == "clear":
                for sid in tasks.clear(self.folder, task, keep_last=False):
                    try:
                        self.runs.forget(sid)
                    except runs.RunError:
                        continue
                with self.lock:
                    del self.tasks[task_id]
                    self.version += 1
                    self.changed.notify_all()
                return 200, {"task": task_id, "state": "cleared"}
            cs = tasks.current_step(task)
            if lever == "stop" and cs and cs["state"] == "running" and self.runs.is_live(cs["session"]):
                self.runs.stop(cs["session"])
            ok, why, lines = tasks.fred(task, lever, now, next_n=(self._next_step(task) or {}).get("n", 0))
            if not ok:
                return 409, {"error": why}
            self._commit(task, lines)
            if lever in ("retry", "confirm"):
                self.advance()
            self.poll_once()
            return 200, {"task": task_id, "state": task["state"]}

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


def task_row(t: dict, live=lambda sid: "", sessions=None) -> dict:
    """A task as the window's list shows it (the whole task.json is GET /api/task). `live(session)` is the
    note state of a running step's reply (Hub._live_note); `sessions` (id -> snapshot row) gives the current step's
    chat. A step whose turn is over and asks a STOP question or shows a hand-off hint needs Fred, even before
    task.json says so (its run may not have ended yet)."""
    cs = tasks.current_step(t)
    r = (sessions or {}).get(cs["session"]) if cs and cs["session"] else None
    over = r is not None and r["state"] not in BUSY and cs["state"] != "done" and t["state"] not in ("done", "stopped", "handed")
    asks = (t["why"][len("asks: "):] if t["state"] == "waiting" and t["why"].startswith("asks: ") else
            r["stop_question"] if over and r["state"] == "stop" else "")
    hand_off = ("" if not (over and r["handoff_hint"]) else
                "the context is large" if r["ctx_tone"] == "red" else f"{r['follow_ups']} follow-ups")
    noted = t["state"] == "handed" and bool(t.get("handoff_note"))  # a pending handoff: Start next task
    handing = t["state"] == "handed" and not noted and r is not None and r["state"] in BUSY  # the skill writes it
    group = ("needs" if t["state"] in ("waiting", "stuck") or asks or hand_off or noted else
             "working" if t["state"] in ("planned", "running") or handing else "done")
    return {"id": t["id"], "title": t["title"], "project": t["project"], "project_dir": t["project_dir"],
            "group": group, "asks": asks, "hand_off": hand_off,
            "state": t["state"], "owner": t["owner"], "current": t["current"], "count": len(t["steps"]),
            "why": t["why"], "updated": t["updated"], "effort": t["effort"],
            "cost": round(sum(tasks.step_cost(s) for s in t["steps"]), 4),
            "route": f"{cs['model']}/{cs['effort']}" if cs and cs["model"] else "",
            "briefing": t.get("briefing") or 0, "cleared": bool(t.get("cleared")),
            "handoff_note": t.get("handoff_note") or "",
            "paused_after": cs["n"] if t["owner"] == "fred" and t["state"] in ("running", "waiting") and cs
            and cs["state"] != "running" else 0,  # the step ended while paused: nothing starts until Resume
            "hold": t["why"].endswith(" over its pace"),
            "steps": [{**{k: s[k] for k in ("n", "kind", "state", "model", "effort", "session", "verdict", "retries",
                                            "cost")},
                       "note": tasks.note_state(t, s, live(s["session"]) if s["state"] == "running" else ""),
                       "attempts": [{"session": a["session"], "cost": a["cost"], "why": a["why"]}
                                    for a in tasks.attempts(s)]} for s in t["steps"]]}


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
            self.hub.reload_models()
            cfg, window = self.hub.cfg, paths.load_window(self.hub.folder)
            found = self.hub.harnesses()
            return self._json({"projects": project_list(cfg), "models": claude_cli.MODELS,
                               "efforts": claude_cli.EFFORTS, "default_model": cfg["default_model"],
                               "default_effort": cfg["default_effort"], "claude": found["claude"]["found"],
                               "harnesses": found, "models_file": self.hub.models_file(),
                               "config_path": str(self.hub.folder / "config.json"),
                               "gauge": [cfg["gauge_yellow_tokens"], cfg["gauge_red_tokens"]],
                               "project": window.get("project", ""), "brief": window.get("brief") is True,
                               "ladder": cfg["ladder"], "effort": window.get("effort", "auto"),
                               "kinds": tasks.PREP_KINDS, "edit_kinds": sorted(tasks.EDIT_KINDS)})
        if url.path == "/api/usage":
            return self._json(self.hub.usage_report())
        if url.path == "/api/image":
            return self._image(query)
        if url.path == "/api/chat":
            return self._chat(query.get("session", [""])[0])
        if url.path == "/api/brief":
            return self._brief(query.get("session", [""])[0], query.get("kind", ["task"])[0])
        if url.path == "/api/levers":
            data = self.hub.levers(query.get("session", [""])[0])
            return self._json(data) if data else self._error(404, "unknown session")
        if url.path == "/api/task":
            return self._task(query.get("id", [""])[0])
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
        routes = {"/api/prep": self._prep, "/api/prep/drop": self._prep_drop, "/api/run": self._run, "/api/stop": self._stop,
                  "/api/terminal": self._terminal, "/api/draft": self._draft, "/api/allow": self._allow,
                  "/api/open_folder": lambda body: self._allow(body, sessions_only=False),
                  "/api/done": self._done, "/api/task": self._task_new, "/api/review": self._review,
                  "/api/harness": self._harness, "/api/models/reload": self._models_reload,
                  "/api/models/open": self._models_open}
        for lever in ("continue", "verify", "handoff", "escalate"):
            routes[f"/api/{lever}"] = lambda body, lever=lever: self._lever(body, lever)
        for lever in ("stop", "pause", "resume", "retry", "confirm", "clear", "done"):
            routes[f"/api/task/{lever}"] = lambda body, lever=lever: self._task_lever(body, lever)
        path = urlparse(self.path).path
        handler = routes.get(path)
        if handler is None:
            return self._send(404, b"not found", "text/plain")
        body = self._body(MAX_FILES_BODY if path in FILE_ROUTES else MAX_BODY)
        if body is None:
            return self._error(400, "expected a JSON object")
        try:
            return handler(body)
        except attach.AttachError as exc:
            return self._error(400, str(exc))
        except (runs.RunError, prep.PrepError) as exc:
            return self._error(409, str(exc))

    def _body(self, limit: int = MAX_BODY):
        try:
            size = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if size <= 0 or size > limit:
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
        files = attach.parse(body.get("files")) or self.hub.prep_files(body.get("files_from"))  # Try again: the old job's
        return self._json({"job": self.hub.start_prep(folder, raw, files)})

    def _prep_drop(self, body):
        job = body.get("job")
        if not isinstance(job, str) or not self.hub.drop_prep(job):
            return self._error(404, "unknown Prep job")
        return self._json({"job": job})

    def _review(self, body):
        folder = self.hub.allowed(body.get("project_dir"))
        if not folder:
            return self._error(403, "not a project listed in config.json")
        if not self.hub.runs.exe:
            return self._error(409, "claude.exe not found; set \"claude_exe\" in config.json")
        return self._json({"job": self.hub.start_review(folder)})

    def _run(self, body):
        folder, text = self.hub.allowed(body.get("project_dir")), self._text(body, "prompt")
        if not folder:
            return self._error(403, "not a project listed in config.json")
        if not text:
            return self._error(400, "empty prompt")
        cfg = self.hub.cfg
        model = body.get("model") or cfg["default_model"]
        effort = body.get("effort") or cfg["default_effort"]
        why = self.hub.rung_ok(model) if isinstance(model, str) else "unknown model or effort"
        if why == "unknown model or effort" or effort not in claude_cli.EFFORTS:
            return self._error(400, "unknown model or effort")
        if why:
            return self._error(409, why)
        if claude_cli.tier_of(model, cfg) == "fable" and body.get("fable_ok") is not True:  # print mode bills credits
            return self._error(409, "confirm Fable: it may bill usage credits on this plan")
        card = prep.load(self.hub.folder, body.get("prep")) if body.get("prep") else None
        if card:
            title = card["fields"].get("goal") or card["raw"]
            route = card["route"].get("type") or "routed"
            reason, prep_id = card.get("reason", ""), card["id"]
            extra = {"prep_model": card.get("model") or cfg["prep_model"], "prep_cost": card.get("cost"),
                     "prep_turns": card.get("turns")}  # the Route block's first row
        else:
            title, route, reason, prep_id, extra = text, "raw", "", "", None
        # sent now (the composer), or waiting with the card's Prep job (Run, or Run raw with files_from)
        files = attach.parse(body.get("files")) or self.hub.prep_files(prep_id or body.get("files_from"))
        hname, model_name = claude_cli.split_rung(model)
        sid = self.hub.runs.start(folder, text, model_name, effort, title=title, route=route,
                                  reason=reason, prep=prep_id, extra=extra, files=files, harness=hname)
        if prep_id:
            self.hub.drop_prep(prep_id)  # the card became this run
        self.hub.poll_once()
        return self._json({"session": sid})

    def _harness(self, body):
        name, on = body.get("name"), body.get("on")
        if name not in harness.NAMES or not isinstance(on, bool):
            return self._error(400, "expected a harness name and on true or false")
        try:
            return self._json({"harnesses": self.hub.set_harness(name, on)})
        except ValueError as exc:
            message = str(exc)
            return self._error(400 if name == "claude" and not on else 500, message)

    def _models_reload(self, body):
        self.hub.reload_models(force=True)
        return self._json({"models_file": self.hub.models_file(), "harnesses": self.hub.harnesses()})

    def _models_open(self, body):
        """Open models.json in Fred's editor: the one fixed path, nothing from the caller."""
        path = paths.home() / "models.json"
        if not path.is_file():
            return self._error(404, "models.json does not exist yet")
        opener = getattr(os, "startfile", None)
        if opener is None:
            return self._error(409, "opening a file needs Windows")
        opener(str(path))
        return self._json({"ok": True})

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
        task = self.hub.tasks.get(s["task"]) if s["task"] else None
        cs = tasks.current_step(task) if task else None
        if cs and cs["session"] == sid and task["state"] in ("running", "waiting"):  # the task's Stop, not a retry
            code, data = self.hub.task_lever(task["id"], "stop")
            return self._json({"stop": data["state"], "task": task["id"]} if code == 200 else data, code)
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
        files = attach.parse(body.get("files")) if lever == "continue" else []
        code, data = self.hub.pull(body.get("session"), lever, self._text(body, "text") if lever == "continue" else "",
                                   body.get("confirm") is True, files)
        return self._json(data, code)

    def _task_new(self, body):
        """Run as task: the card (Prep job id), its prompt as edited on the page and the step list."""
        card = prep.load(self.hub.folder, body.get("prep")) if isinstance(body.get("prep"), str) else None
        if card is None:
            return self._error(404, "unknown Prep card")
        if not self.hub.allowed(card.get("project_dir")):
            return self._error(403, "not a project listed in config.json")
        text, effort, steps = self._text(body, "prompt"), body.get("effort", "auto"), body.get("steps")
        if not text:
            return self._error(400, "empty prompt")
        if effort != "auto" and effort not in claude_cli.EFFORTS:
            return self._error(400, "unknown effort")
        if not isinstance(steps, list) or not all(isinstance(s, dict) for s in steps):
            return self._error(400, "bad steps")
        for n, item in enumerate(steps, 1):
            why = self.hub.rung_ok(item["model"], str(item.get("kind") or "")) if item.get("model") else ""
            if why:
                return self._error(400, f"step {n}: {why}")
        title = body.get("title") if isinstance(body.get("title"), str) else ""
        return self._json({"task": self.hub.create_task(dict(card, prompt=text), steps, effort, title.strip())})

    def _task_lever(self, body, lever):
        code, data = self.hub.task_lever(body.get("task"), lever)
        return self._json(data, code)

    def _terminal(self, body):
        sid, s = self._window_session(body)
        if not sid:
            return self._error(404, "not a window run")
        self.hub.runs.open_terminal(sid)
        return self._json({"ok": True})

    def _allow(self, body, sessions_only: bool = True):
        """Only folders Claude Code already ran in: the page cannot add an arbitrary path. The picker's
        Open folder (sessions_only False) passes a folder Fred chose in the OS dialog."""
        want = body.get("project_dir")
        if not isinstance(want, str) or not want or not os.path.isdir(want):
            return self._error(400, "not a folder")
        if sessions_only and not self.hub.seen(want):
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
        effort = body.get("effort")
        if not isinstance(text, str) or len(text) > MAX_PROMPT:
            return self._error(400, "bad draft")
        if project is not None and (not isinstance(project, str) or len(project) > 1000):
            return self._error(400, "bad project")
        if brief is not None and not isinstance(brief, bool):
            return self._error(400, "bad brief")
        if effort is not None and effort != "auto" and effort not in claude_cli.EFFORTS:
            return self._error(400, "bad effort")
        self.hub.folder.mkdir(parents=True, exist_ok=True)
        (self.hub.folder / "draft.txt").write_text(text, encoding="utf-8")
        fields = {k: v for k, v in (("project", project), ("brief", brief), ("effort", effort)) if v is not None}
        if fields:
            paths.save_window(self.hub.folder, **fields)
        return self._json({"ok": True})

    # -- GET helpers -----------------------------------------------------------------
    def _chat(self, sid: str):
        """A window run's stream, or for a VS Code / terminal chat the last turns of its transcript."""
        meta = self.hub.runs.meta(sid) if sid and all(c.isalnum() or c == "-" for c in sid) else None
        if not meta:
            info = self.hub.session(sid)
            path = info["transcript_path"] if info else transcript.find(
                self.hub.user_home / ".claude" / "projects", sid)  # an older step: no row, no stream
            items = transcript.turns(path) if path else []
            return self._json({"items": items, "source": "transcript", "changed": None, "live": False})
        items = self.hub.runs.chat_of(sid)
        changed = claude_cli.git_changed(meta["cwd"], meta.get("start_commit", ""))
        return self._json({"items": items, "source": "window", "changed": changed,
                           "live": self.hub.runs.is_live(sid), "start_commit": meta.get("start_commit", "")})

    def _image(self, query):
        """A Chat thumbnail: an image Fred pasted into a transcript (`at` = line uuid, `k` = block), or an
        image Claude wrote inside the session's folder (`path`, relative). Read only; images only."""
        one = lambda key: query.get(key, [""])[0]
        sid = one("session")
        s = self.hub.session(sid) if sid else None
        if not s:
            return self._error(404, "unknown session")
        if one("path"):
            meta = self.hub.runs.meta(sid) if all(c.isalnum() or c == "-" for c in sid) else None
            found = attach.folder_image((meta or {}).get("cwd") or s["cwd"] or s["project_dir"], one("path"))
        else:
            at, k = one("at"), one("k")
            ok = at and all(c.isalnum() or c == "-" for c in at) and k.isdigit()
            found = transcript.image(s["transcript_path"], at, int(k)) if ok else None
        if not found:
            return self._error(404, "no such image")
        return self._send(200, *found)

    def _brief(self, sid: str, kind: str):
        """The text of a new task that takes over a session, built from its transcript, its steps and the
        folder's git status: no model call, nothing written."""
        s = self.hub.session(sid)
        if s is None or kind not in ("task", "verify", "next"):
            return self._error(404, "unknown session")
        task = self.hub.tasks.get(s["task"]) if s["task"] else None
        note = ((tasks.read_handoff(self.hub.folder, task) or tasks.read_brief(self.hub.folder, task, s["step"]))
                if task and kind == "next" else "")
        if note:  # a task's step session: the next chat starts from the handoff note, else from the step's brief
            return self._json({"text": brief.build("next", last=note), "project_dir": s["project_dir"]})
        if kind == "next":  # after a Hand off: the next task starts from the skill's note
            off = self.hub.levers(sid)["next"]
            if off:
                return self._error(409, off)
            return self._json({"text": brief.build("next", last=self.hub.last_reply(s["handoff_by"])),
                               "project_dir": s["project_dir"]})
        return self._json({"text": self.hub.brief_text(sid, s, kind), "project_dir": s["project_dir"]})

    def _task(self, task_id: str):
        task = self.hub.tasks.get(task_id) if tasks.safe_id(task_id) else None
        if task is None:
            return self._error(404, "unknown task")
        last, cs = task["last_good"], tasks.current_step(task)
        return self._json({"task": task, "levers": self.hub.task_levers(task_id),
                           "step_levers": self.hub.levers(cs["session"]) if cs and cs["session"] else None,
                           "note": tasks.read_note(self.hub.folder, task, last),
                           "brief": tasks.read_brief(self.hub.folder, task, last),
                           "handoff": tasks.read_handoff(self.hub.folder, task)})

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


def make_server(cfg: dict, port: int = None, folder: Path = None, exe: list = None, exes: dict = None):
    """Bind 127.0.0.1 (never another host). Returns (httpd, hub); raises OSError if the port is taken.
    `exe` is the claude command prefix (tests pass a fake); default: the real claude.exe. `exes` are the other
    harnesses' command prefixes as RunManager takes them (tests pass fakes); the probe finds the rest."""
    if exe is None:
        found = claude_cli.find_exe(cfg)
        exe = [found] if found else None
    hub = Hub(cfg, folder or paths.home(), exe, exes)
    handler = type("BoundHandler", (Handler,), {"hub": hub})
    httpd = ThreadingHTTPServer(("127.0.0.1", cfg["port"] if port is None else port), handler)
    httpd.daemon_threads = True
    return httpd, hub
