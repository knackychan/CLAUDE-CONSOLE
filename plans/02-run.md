# Plan 02: Run (phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Related plans: [../PLAN.md](../PLAN.md) (master), [01-watch.md](01-watch.md) (phase 1, done)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md) sections 4-8, 10, 12 (phase 2); [../CLAUDE.md](../CLAUDE.md)

**Goal:** Fred types a prompt in the window. Enter runs Prep (Haiku scouts the project, rewrites the prompt, picks a route) and shows a card that waits; Run starts `claude -p` detached in that project. The run shows up as a `window` session with a Chat tab, Stop, Open in terminal, an answer box for `STOP:` questions, and Resume when a crash cut it (Interrupted).

**Architecture:** `console/claude_cli.py` builds every `claude` command as an argument list. `console/prep.py` runs the blocking Prep call and saves `preps/<id>.json`. `console/runs.py` (`RunManager`) starts runs with a service-chosen session id, keeps their stdin (prompt in, interrupt in), copies their stream to `runs/<id>.jsonl`, and appends two lines of its own to the event log: `run_started` and `run_ended`. The hooks keep logging everything else, so `State` stays the one place that builds sessions. The window gets a prompt box, a Prep card view and session actions.

**Tech Stack:** unchanged: Python 3.14 standard library, pywebview 6.2.1, plain HTML/CSS/JS, `unittest`. Claude Code CLI 2.1.288.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `master`). Every path below is relative to it. Run commands from the repo root in Git Bash.

---

## Fixed decisions (verified 2026-10-10 on this machine, Claude Code 2.1.288, `claude --help` + experiments)

1. **Run command:** `claude.exe -p --model <m> --effort <e> --permission-mode auto --permission-prompts none --input-format stream-json --output-format stream-json --verbose --session-id <uuid> --name <title>` (resume: `--resume <uuid>` instead of `--session-id` and `--name`). The prompt goes in on stdin as one `{"type":"user","message":{"role":"user","content":...}}` line. Stdin stays open until the `result` line, then the service closes it and the process exits (stream-json input waits for more input otherwise).
2. **Stop = interrupt over stdin:** `{"type":"control_request","request_id":...,"request":{"subtype":"interrupt"}}`. Verified: Claude answers `control_response` success, logs `[Request interrupted by user]`, ends with `result` subtype `error_during_execution`, exits 1. Ctrl+C sent to the run's hidden console did nothing (verified), so there is no signal path. A run started by an earlier service has no stdin here: Stop falls back to `taskkill /PID <pid> /T /F`.
3. **Closing the window never stops a run:** when the service dies, stdin hits EOF; verified that Claude then finishes the current turn and exits 0. Runs also start with `CREATE_BREAKAWAY_FROM_JOB` (falls back without it) and `CREATE_NO_WINDOW`.
4. **The service picks the session id** (`--session-id <uuid4>`, verified honoured), so hook lines, `runs/<id>.jsonl` and `runs/<id>.json` share it. `--resume <id>` in `-p` keeps the same id and the context (verified).
5. **Prep command:** `claude.exe -p --model haiku --effort low --tools Read,Grep,Glob --permission-mode dontAsk --disable-slash-commands --strict-mcp-config --settings {"disableAllHooks": true} --no-session-persistence --output-format json --json-schema <schema>`, prompt on stdin. `--json-schema` works together with tool use: the answer is in `structured_output` (verified). Measured: 10-22 s, $0.03-0.04, 5-9 turns. `disableAllHooks` keeps Prep out of the event log (verified: 0 lines), so Prep never appears in the tree. Without `--tools` Haiku tried Bash and paid $0.11.
6. **Child environment:** a Claude Code session exports `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_PID` and others to its children; a test run started from a VS Code session inherited them and was logged as `vscode`. Runs and Prep get `os.environ` minus the 12 names in `claude_cli.SESSION_ENV`. The session's source comes from `run_started` (`window`), never from the transcript entrypoint.
7. **Never run the npm `claude.cmd` shim** (batch files re-parse arguments). `find_exe` uses `config.json` `claude_exe`, then `claude.exe` on PATH, then `<npm dir>\node_modules\@anthropic-ai\claude-code\bin\claude.exe` next to the shim (this machine: `C:\Users\DEROK137\AppData\Roaming\npm\...`).
8. **Runs only in folders listed in `config.json` `"projects"`** (BRAINSTORM 10: `claude -p` runs a project's hooks without a trust prompt). Fred adds them by hand (Task 7) or with the window's `Allow runs in <name>` button (Task 6b), which only accepts a folder a Claude Code session already ran in (seen in the event log). The project picker marks them `(runs)`.
9. **Prep prompt lives in `console/prep_prompt.md`** (`$raw` placeholder, `string.Template`). Fred's own prompter text is not in either repo; he can replace the file as long as `$raw` and the field list stay.
10. **STOP convention:** the service appends one footer line to every window-run prompt: `If you must stop for a decision only Fred can make, end your final message with one line: STOP: <question>`. Nothing in `route-model` or any CLAUDE.md is edited by code; Task 7 has an optional Fred step for VS Code sessions.
11. **Answer and Resume use one endpoint** (`POST /api/answer`), for window runs only and only when the run is not live. Resume sends the fixed text `You were interrupted. Check \`git diff\` first, then finish the task.` (`CLAUDE_CODE_RESUME_INTERRUPTED_TURN` is not used: not verified). Continue for any session is phase 3.
12. **Window sessions are not ended by SessionEnd** (each `-p` process ends after its turn and the session can resume; the test runs also logged no SessionEnd at all). They reach Done through Stale? after 30 min, like phase 1.
13. **Interrupted** = `run_ended` without a `result` line (process gone: crash, shutdown, kill). Found by the run's watcher thread, or by `RunManager.reconcile()` at start and every 15 s for runs of an earlier service. PID reuse could hide one until that PID exits; accepted.
14. **Denials:** with `--permission-prompts none` a denial lands in the result's `permission_denials`; `run_ended` carries the first 3 and the session turns Blocked with `window runs cannot ask: open in terminal`. Changed 2026-10-10 (Fred, after live check 2: a lookup run had 2 denials, used Read instead and succeeded): when the result is `success` the session stays Idle under Working and shows a yellow note `△ N denied <first> the run still finished; open in terminal to allow`; Blocked only when the run did not succeed.
15. **Route text:** `run_started` carries the route type only (`mechanical`, ..., or `raw`); the row shows `type · model/effort` as in phase 1.
16. **Files:** `runs/<id>.jsonl` is the raw stream plus the service's `cc_prompt` lines (full text, local only, like Claude's own transcripts); `runs/<id>.json` the run meta; `preps/<id>.json` the card; `draft.txt` the unsent prompt. `runs/` and `preps/` are pruned by mtime with `retention_days`.
17. **Not verified by Claude:** a live `--permission-mode auto` run (Claude's own auto-mode classifier refuses to let Claude start an autonomous agent) and Open in terminal (opens a console on Fred's screen). Both are in Task 7's live check.

## Code map

```text
console/
  claude_cli.py   NEW  find_exe, child_env, prep/run/terminal commands, user/interrupt messages, pid_alive, kill_tree, git_head, git_changed
  prep.py         NEW  SCHEMA, build_prompt, format_prompt, parse_output, run_prep, load
  prep_prompt.md  NEW  the Prep instructions + route table ($raw)
  runs.py         NEW  RunManager (start, stop, reconcile, open_terminal), read_lines, chat, result_record, prune
  events.py       + append()
  state.py        + window runs (run_started / run_ended), Interrupted, pasted-title cleanup, drive-letter spelling
  paths.py        + 6 config keys
  server.py       + Hub.runs, POST /api/prep /run /stop /answer /terminal /draft, GET /api/config /chat /draft
  __main__.py     + runs.prune at start
web/  index.html  app.js  style.css   prompt box, Prep card, actions, Steps / Chat tabs
tests/
  fake_claude.py  NEW  stand-in for claude.exe (same flags and JSON shapes)
  test_claude_cli.py  test_prep.py  test_runs.py   NEW
  test_state.py  test_server.py                    extended
```

Dependencies point one way: `claude_cli -> (stdlib)`; `prep -> claude_cli, redact`; `runs -> claude_cli, events, redact`; `server -> claude_cli, events, guard, paths, prep, runs, state`.

## Files to modify

`console/state.py`, `console/paths.py`, `console/events.py`, `console/server.py`, `console/__main__.py`, `web/index.html`, `web/app.js`, `web/style.css`, `tests/test_state.py`, `tests/test_server.py`, `PLAN.md`, this file. Everything else listed above is new.

## TODO

- [x] Task 1: config keys + state (window runs, Interrupted, titles)
- [x] Task 2: claude_cli
- [x] Task 3: Prep
- [x] Task 4: runs
- [x] Task 5: service routes
- [x] Task 6: window
- [x] Task 6b: Allow runs here (added 2026-10-10, Fred)
- [x] Task 7: Fred: projects in config.json + live check
- [x] Task 8: close the phase

---

### Task 1: Config keys + state

**Files:**
- Modify: `console/paths.py`, `console/state.py` (full files below)
- Test: `tests/test_state.py` (full file below; 3 new tests)

- [x] **Step 1: Replace `tests/test_state.py`** with:

```python
import copy
import unittest

from console import paths
from console.state import State

T0 = 1_000_000.0


def ev(event, ts, sid="s1", **extra):
    rec = {"event": event, "ts": ts, "session_id": sid, "project": "repo", "project_dir": "D:/repo"}
    rec.update(extra)
    return rec


class StateTest(unittest.TestCase):
    def setUp(self):
        self.state = State(copy.deepcopy(paths.DEFAULTS))

    def feed(self, *recs):
        for rec in recs:
            self.state.apply(rec)

    def row(self, now, sid="s1"):
        return next(r for r in self.state.snapshot(now)["sessions"] if r["id"] == sid)

    def test_turn_lifecycle_running_quiet_stall_idle_stale(self):
        self.feed(ev("UserPromptSubmit", T0, prompt="fix the updater retry"))
        self.assertEqual(self.row(T0 + 10)["state"], "running")
        self.assertEqual(self.row(T0 + 200)["state"], "quiet")
        self.assertEqual(self.row(T0 + 700)["state"], "stall")
        self.assertEqual(self.row(T0 + 700)["group"], "needs")
        self.feed(ev("Stop", T0 + 20))
        self.assertEqual(self.row(T0 + 30)["state"], "idle")
        self.assertEqual(self.row(T0 + 30)["group"], "working")
        self.assertEqual(self.row(T0 + 2000)["state"], "stale")
        self.assertEqual(self.row(T0 + 2000)["group"], "done")
        self.assertEqual(self.row(T0 + 30)["title"], "fix the updater retry")

    def test_stop_question_blocked_failed_done(self):
        self.feed(ev("UserPromptSubmit", T0), ev("Stop", T0 + 5, stop_question="how many retries?"))
        self.assertEqual((self.row(T0 + 6)["state"], self.row(T0 + 6)["group"]), ("stop", "needs"))
        self.feed(ev("UserPromptSubmit", T0 + 10))
        self.assertEqual(self.row(T0 + 11)["state"], "running")
        self.feed(ev("PermissionDenied", T0 + 12, tool="Bash", what="git push", reason="[Push]"))
        self.assertEqual(self.row(T0 + 13)["state"], "blocked")
        self.feed(ev("UserPromptSubmit", T0 + 14), ev("StopFailure", T0 + 15, error="rate_limit"))
        self.assertEqual(self.row(T0 + 16)["state"], "failed")
        self.feed(ev("SessionEnd", T0 + 17))
        self.assertEqual((self.row(T0 + 18)["state"], self.row(T0 + 18)["group"]), ("done", "done"))

    def test_stop_sets_model_source_route_and_gauge(self):
        self.feed(ev("UserPromptSubmit", T0),
                  ev("Stop", T0 + 1, model="claude-opus-5-5", context_tokens=330000,
                     entrypoint="claude-vscode", route="risky, opus, high"))
        row = self.row(T0 + 2)
        self.assertEqual((row["model"], row["source"], row["route"]), ("claude-opus-5-5", "vscode", "risky, opus, high"))
        self.assertEqual((row["ctx_fill"], row["ctx_tone"], row["group"]), (1.0, "red", "needs"))
        self.feed(ev("PostCompact", T0 + 3))
        self.assertIsNone(self.row(T0 + 4)["ctx_fill"])

    def test_gauge_thresholds(self):
        for tokens, tone in ((10000, "green"), (150000, "yellow"), (300000, "red")):
            self.feed(ev("Stop", T0, sid=f"g{tokens}", context_tokens=tokens))
            self.assertEqual(self.row(T0 + 1, f"g{tokens}")["ctx_tone"], tone)

    def test_agents_nest_under_their_session(self):
        self.feed(ev("UserPromptSubmit", T0),
                  ev("SubagentStart", T0 + 1, agent_id="a1", agent_type="verifier"),
                  ev("PreToolUse", T0 + 2, agent_id="a1", agent_type="verifier", effort="low",
                     tool="Bash", what="py -m unittest"),
                  ev("PreToolUse", T0 + 3, tool="Edit", what="updater.py"))
        row = self.row(T0 + 4)
        self.assertEqual(row["doing"], "Edit updater.py")
        agent = row["agents"][0]
        self.assertEqual((agent["type"], agent["effort"], agent["doing"], agent["steps"]),
                         ("verifier", "low", "Bash py -m unittest", 1))
        self.feed(ev("SubagentStop", T0 + 5, agent_id="a1", model="claude-sonnet-5-5", context_tokens=9100))
        agent = self.row(T0 + 6)["agents"][0]
        self.assertEqual((agent["text"], agent["model"], agent["tokens"]), ("Done", "claude-sonnet-5-5", 9100))
        self.assertEqual((agent["ctx_fill"], agent["ctx_tone"]), (0.03, "green"))
        steps = self.state.steps("s1")
        self.assertEqual([s["agent_type"] for s in steps], ["verifier", "main"])

    def test_two_writers_in_one_repo(self):
        self.feed(ev("PreToolUse", T0, sid="a", tool="Edit", what="x.py"),
                  ev("PreToolUse", T0 + 1, sid="b", tool="Write", what="y.py"),
                  ev("PreToolUse", T0 + 2, sid="c", tool="Read", what="z.py"))
        snap = self.state.snapshot(T0 + 10)
        self.assertEqual(snap["writers"], [{"project_dir": "D:/repo", "sessions": ["a", "b"]}])
        flags = {r["id"]: r["two_writers"] for r in snap["sessions"]}
        self.assertEqual(flags, {"a": True, "b": True, "c": False})
        self.assertEqual(self.state.snapshot(T0 + 700)["writers"], [])

    def test_old_sessions_are_hidden_and_order_is_stable(self):
        self.feed(ev("Stop", T0, sid="old"), ev("Stop", T0 + 90000, sid="new1"),
                  ev("Stop", T0 + 90001, sid="new2"), ev("PreToolUse", T0 + 90002, sid="new1", tool="Read"))
        ids = [r["id"] for r in self.state.snapshot(T0 + 90003)["sessions"]]
        self.assertEqual(ids, ["new1", "new2"])

    def test_window_run_lifecycle(self):
        self.feed(ev("run_started", T0, title="Fix add() in calc.py", route="mechanical",
                     reason="small", prep="p1", start_commit="abc", model="sonnet", effort="low"),
                  ev("UserPromptSubmit", T0 + 1, prompt="Goal: Fix add()"),
                  ev("Stop", T0 + 5, entrypoint="claude-vscode", model="claude-sonnet-5-5"),
                  ev("SessionEnd", T0 + 6),
                  ev("run_ended", T0 + 6, cost=0.25, subtype="success"))
        row = self.row(T0 + 7)
        self.assertEqual((row["state"], row["source"], row["title"], row["route"]),
                         ("idle", "window", "Fix add() in calc.py", "mechanical"))
        self.assertEqual((row["window"], row["run_live"], row["cost"], row["prep"], row["start_commit"]),
                         (True, False, 0.25, "p1", "abc"))
        self.assertEqual(row["model"], "claude-sonnet-5-5")

    def test_interrupted_stopped_and_denied_runs(self):
        self.feed(ev("run_started", T0), ev("run_ended", T0 + 5, interrupted=True))
        row = self.row(T0 + 6)
        self.assertEqual((row["state"], row["symbol"], row["group"]), ("interrupted", "‖", "needs"))
        self.feed(ev("run_started", T0 + 10), ev("run_ended", T0 + 12, stopped=True))
        self.assertEqual((self.row(T0 + 13)["state"], self.row(T0 + 13)["stopped"]), ("idle", True))
        self.feed(ev("run_started", T0 + 20),
                  ev("run_ended", T0 + 22, denials=[{"tool": "Bash", "what": "git push"}]))
        row = self.row(T0 + 23)
        self.assertEqual((row["state"], row["denied"]["what"]), ("blocked", "git push"))

    def test_pasted_prompt_title_and_drive_letter(self):
        self.feed(ev("UserPromptSubmit", T0, prompt='<pasted_content id="9a1c"> Project: D:/x', project_dir="d:/repo"),
                  ev("Stop", T0 + 1, sid="s2", project_dir="D:/repo"))
        self.assertEqual(self.row(T0 + 2)["title"], "Project: D:/x")
        self.assertEqual({r["project_dir"] for r in self.state.snapshot(T0 + 2)["sessions"]}, {"D:/repo"})


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_state -v`
Expected: the 3 new tests fail (`KeyError: 'window'`, title still holds `<pasted_content ...>`); the 7 old ones pass.

- [x] **Step 3: Replace `console/paths.py`** with:

```python
"""Where Claude Console keeps its files, and its config with defaults."""
import copy
import json
import os
from pathlib import Path

DEFAULTS = {
    "port": 8770,
    "retention_days": 14,
    "quiet_after_s": 180,
    "stall_after_s": 600,
    "stale_after_s": 1800,
    "writers_window_s": 600,
    "gauge_yellow_tokens": 150000,
    "gauge_red_tokens": 300000,
    "projects": [],
    "claude_exe": "",
    "prep_model": "haiku",
    "prep_timeout_s": 180,
    "default_model": "sonnet",
    "default_effort": "medium",
}


def home() -> Path:
    """The data folder: env CC_CONSOLE_HOME (tests), else ~/.claude/console."""
    env = os.environ.get("CC_CONSOLE_HOME")
    return Path(env) if env else Path.home() / ".claude" / "console"


def load_config() -> dict:
    """DEFAULTS overlaid with config.json; nested dicts merge one level deep."""
    cfg = copy.deepcopy(DEFAULTS)
    try:
        user = json.loads((home() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if not isinstance(user, dict):
        return cfg
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def ensure_config() -> dict:
    """Write config.json with the defaults if it does not exist, then load it."""
    path = home() / "config.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULTS, indent=2) + "\n", encoding="utf-8")
    return load_config()
```

- [x] **Step 4: Replace `console/state.py`** with:

```python
"""Sessions -> agents -> steps, built from event records; states computed at snapshot time."""
import re
from dataclasses import dataclass, field

from . import redact

# state -> (symbol, text, tone). Colour never carries a state alone.
STATES = {
    "running": ("▶", "Running", "info"),
    "quiet": ("…", "Quiet", "info"),
    "stall": ("◷", "Stall?", "warning"),
    "stop": ("?", "STOP", "warning"),
    "blocked": ("■", "Blocked", "danger"),
    "failed": ("×", "Failed", "danger"),
    "idle": ("○", "Idle", "info"),
    "stale": ("△", "Stale?", "warning"),
    "interrupted": ("‖", "Interrupted", "warning"),
    "done": ("✓", "Done", "success"),
}
NEEDS_YOU = {"stop", "blocked", "stall", "failed", "interrupted"}
DONE = {"done", "stale"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SOURCES = {"claude-vscode": "vscode", "cli": "terminal", "claude-desktop": "desktop"}
MAX_STEPS = 500
SHOW_FOR_S = 86400
_PASTED = re.compile(r"</?pasted_content[^>]*>")


def norm_dir(path: str) -> str:
    """One spelling per folder: VS Code reports the drive as d:, terminals as D:."""
    if len(path) > 1 and path[1] == ":":
        return path[0].upper() + path[1:]
    return path


@dataclass
class Agent:
    id: str
    type: str = ""
    started_ts: float = 0.0
    last_ts: float = 0.0
    effort: str = ""
    model: str = ""
    tokens: int = 0
    steps: int = 0
    doing: str = ""
    done: bool = False


@dataclass
class Session:
    id: str
    started_ts: float = 0.0
    last_ts: float = 0.0
    project: str = ""
    project_dir: str = ""
    cwd: str = ""
    title: str = ""
    source: str = ""
    model: str = ""
    effort: str = ""
    route: str = ""
    prompts: int = 0
    in_turn: bool = False
    ended: bool = False
    doing: str = ""
    ctx_tokens: int = None
    compactions: int = 0
    stop_question: str = ""
    denied: dict = None
    failed: dict = None
    last_write_ts: float = 0.0
    agents: dict = field(default_factory=dict)
    steps: list = field(default_factory=list)
    window: bool = False
    run_live: bool = False
    interrupted: bool = False
    stopped: bool = False
    cost: float = 0.0
    route_reason: str = ""
    prep: str = ""
    start_commit: str = ""


class State:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.sessions = {}

    def apply(self, rec: dict) -> None:
        sid = rec.get("session_id")
        if not sid:
            return
        ts = float(rec.get("ts") or 0)
        s = self.sessions.get(sid)
        if s is None:
            s = self.sessions[sid] = Session(id=sid, started_ts=ts)
        s.last_ts = max(s.last_ts, ts)
        for key in ("project", "project_dir", "cwd"):
            if rec.get(key):
                setattr(s, key, norm_dir(rec[key]) if key == "project_dir" else rec[key])
        agent = None
        aid = rec.get("agent_id")
        if aid:
            agent = s.agents.get(aid)
            if agent is None:
                agent = s.agents[aid] = Agent(id=aid, started_ts=ts)
            agent.last_ts = ts
            if rec.get("agent_type"):
                agent.type = rec["agent_type"]
            if rec.get("effort"):
                agent.effort = rec["effort"]
        elif rec.get("effort"):
            s.effort = rec["effort"]

        event = rec.get("event")
        if event == "SessionStart":
            s.ended = False
            if rec.get("model"):
                s.model = rec["model"]
        elif event == "UserPromptSubmit":
            s.in_turn, s.ended = True, False
            s.prompts += 1
            if not s.title:
                s.title = redact.clip(_PASTED.sub(" ", rec.get("prompt", "")), 60)
            s.denied = s.failed = None
            s.stop_question = ""
            s.interrupted = s.stopped = False
        elif event == "PreToolUse":
            s.in_turn = True
            tool, what = rec.get("tool", ""), rec.get("what", "")
            self._step(s, ts, aid, tool, what)
            doing = f"{tool} {what}".strip()
            if agent:
                agent.doing = doing
                agent.steps += 1
            else:
                s.doing = doing
            if tool in WRITE_TOOLS:
                s.last_write_ts = ts
        elif event == "SubagentStop" and agent:
            agent.done = True
            agent.doing = ""
            agent.model = rec.get("model") or agent.model
            agent.tokens = rec.get("context_tokens") or agent.tokens
        elif event == "PermissionDenied":
            s.denied = {"tool": rec.get("tool", ""), "what": rec.get("what", ""),
                        "reason": rec.get("reason", ""), "ts": ts}
            self._step(s, ts, aid, rec.get("tool", ""), rec.get("what", ""), denied=True)
        elif event == "Stop":
            s.in_turn = False
            s.doing = ""
            s.model = rec.get("model") or s.model
            if rec.get("context_tokens") is not None:
                s.ctx_tokens = rec["context_tokens"]
            if rec.get("entrypoint") and not s.window:
                s.source = SOURCES.get(rec["entrypoint"], rec["entrypoint"])
            if rec.get("route"):
                s.route = rec["route"]
            s.stop_question = rec.get("stop_question", "")
        elif event == "StopFailure":
            s.in_turn = False
            s.failed = {"error": rec.get("error", "unknown"), "details": rec.get("error_details", "")}
        elif event == "PostCompact":
            s.ctx_tokens = None
            s.compactions += 1
        elif event == "SessionEnd":
            s.in_turn = False
            s.ended = not s.window  # a window run's process ends after every turn; it can resume
        elif event == "run_started":
            s.window, s.run_live, s.source = True, True, "window"
            s.in_turn, s.ended = True, False
            s.interrupted = s.stopped = False
            s.denied = s.failed = None
            s.stop_question = ""
            if rec.get("title") and not s.title:
                s.title = redact.clip(rec["title"], 60)
            if rec.get("route"):
                s.route, s.route_reason = rec["route"], rec.get("reason", "")
            if rec.get("prep"):
                s.prep = rec["prep"]
            if rec.get("start_commit") and not s.start_commit:
                s.start_commit = rec["start_commit"]
            if rec.get("model") and not s.model:
                s.model = rec["model"]
        elif event == "run_ended":
            s.window, s.run_live, s.in_turn = True, False, False
            s.doing = ""
            s.cost += float(rec.get("cost") or 0)
            s.stopped = bool(rec.get("stopped"))
            s.interrupted = bool(rec.get("interrupted"))
            if rec.get("denials") and not s.denied:
                first = rec["denials"][0]
                s.denied = {"tool": first.get("tool", ""), "what": first.get("what", ""),
                            "reason": "window runs cannot ask: open in terminal", "ts": ts}

    def _step(self, s, ts, aid, tool, what, denied=False):
        s.steps.append({"ts": ts, "agent": aid or "", "tool": tool, "what": what, "denied": denied})
        if len(s.steps) > MAX_STEPS:
            del s.steps[: len(s.steps) - MAX_STEPS]

    # -- snapshot -----------------------------------------------------------------
    def state_of(self, s: Session, now: float) -> str:
        if s.ended:
            return "done"
        if s.failed:
            return "failed"
        if s.denied:
            return "blocked"
        if s.interrupted:
            return "interrupted"
        age = now - s.last_ts
        if s.in_turn:
            if age >= self.cfg["stall_after_s"]:
                return "stall"
            if age >= self.cfg["quiet_after_s"]:
                return "quiet"
            return "running"
        if s.stop_question:
            return "stop"
        if age >= self.cfg["stale_after_s"]:
            return "stale"
        return "idle"

    def gauge(self, tokens):
        """(fill, tone): fill is tokens / gauge_red_tokens, capped at 1.0.

        Token thresholds, not % of the window: the 5.x models have a 1M window, and a chat
        degrades long before it is full (Context Playbook)."""
        if tokens is None:
            return None, None
        red, yellow = self.cfg["gauge_red_tokens"], self.cfg["gauge_yellow_tokens"]
        fill = min(tokens / red, 1.0)
        if tokens >= red:
            return fill, "red"
        if tokens >= yellow:
            return fill, "yellow"
        return fill, "green"

    def writers(self, now: float) -> dict:
        """project -> session ids that wrote files in the last writers_window_s."""
        cutoff = now - self.cfg["writers_window_s"]
        by_project = {}
        for s in self.sessions.values():
            if not s.ended and s.last_write_ts >= cutoff and s.project_dir:
                by_project.setdefault(s.project_dir, []).append(s.id)
        return {p: ids for p, ids in by_project.items() if len(ids) >= 2}

    def snapshot(self, now: float) -> dict:
        writers = self.writers(now)
        writer_ids = {sid for ids in writers.values() for sid in ids}
        rows = []
        for s in sorted(self.sessions.values(), key=lambda x: x.started_ts):
            if now - s.last_ts > SHOW_FOR_S:
                continue
            state = self.state_of(s, now)
            pct, tone = self.gauge(s.ctx_tokens)
            if state in NEEDS_YOU or (tone == "red" and state not in DONE):
                group = "needs"
            elif state in DONE:
                group = "done"
            else:
                group = "working"
            symbol, text, state_tone = STATES[state]
            rows.append({
                "id": s.id, "project": s.project, "project_dir": s.project_dir,
                "title": s.title or f"(prompt not seen) {s.id[:8]}", "source": s.source or "?",
                "model": s.model, "effort": s.effort, "route": s.route or "unrouted",
                "state": state, "symbol": symbol, "text": text, "tone": state_tone,
                "group": group, "doing": s.doing, "prompts": s.prompts,
                "ctx_tokens": s.ctx_tokens, "ctx_fill": None if pct is None else round(pct, 3),
                "ctx_tone": tone, "compactions": s.compactions,
                "stop_question": s.stop_question, "denied": s.denied, "failed": s.failed,
                "two_writers": s.id in writer_ids,
                "window": s.window, "run_live": s.run_live, "stopped": s.stopped,
                "cost": round(s.cost, 4), "route_reason": s.route_reason, "prep": s.prep,
                "start_commit": s.start_commit, "cwd": s.cwd,
                "started_ts": s.started_ts, "last_ts": s.last_ts,
                "agents": [self._agent_row(a, s) for a in
                           sorted(s.agents.values(), key=lambda a: a.started_ts)],
            })
        return {
            "now": now,
            "sessions": rows,
            "writers": [{"project_dir": p, "sessions": ids} for p, ids in sorted(writers.items())],
            "counts": {g: sum(1 for r in rows if r["group"] == g) for g in ("needs", "working", "done")},
        }

    def _agent_row(self, a: Agent, s: Session) -> dict:
        if a.done:
            symbol, text, tone = STATES["done"]
        elif s.in_turn:
            symbol, text, tone = STATES["running"]
        else:
            symbol, text, tone = "…", "No stop seen", "info"
        fill, ctx_tone = self.gauge(a.tokens or None)
        return {"id": a.id, "type": a.type or "agent", "model": a.model, "effort": a.effort,
                "tokens": a.tokens, "steps": a.steps, "doing": a.doing,
                "symbol": symbol, "text": text, "tone": tone,
                "ctx_fill": None if fill is None else round(fill, 3), "ctx_tone": ctx_tone}

    def steps(self, session_id: str, limit: int = 200) -> list:
        s = self.sessions.get(session_id)
        if not s:
            return []
        types = {a.id: a.type for a in s.agents.values()}
        return [dict(step, agent_type=types.get(step["agent"], "") if step["agent"] else "main")
                for step in s.steps[-limit:]]
```

- [x] **Step 5: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 40 tests ... OK`.

- [x] **Step 6: Commit**

```bash
git add console/paths.py console/state.py tests/test_state.py
git commit -m "feat: window-run states, Interrupted, clean pasted titles, one drive spelling"
```

**DONE WHEN**
- [x] 40 tests OK; `git status --short` empty.

---

### Task 2: claude_cli

**Files:**
- Create: `console/claude_cli.py`
- Test: `tests/test_claude_cli.py`

- [x] **Step 1: Create `tests/test_claude_cli.py`**

```python
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from console import claude_cli


class CommandTest(unittest.TestCase):
    def test_run_command_new_and_resume(self):
        new = claude_cli.run_command(["claude.exe"], "sonnet", "medium", "abc", name="Fix add")
        self.assertEqual(new[:2], ["claude.exe", "-p"])
        for flag, value in (("--model", "sonnet"), ("--effort", "medium"), ("--permission-mode", "auto"),
                            ("--permission-prompts", "none"), ("--input-format", "stream-json"),
                            ("--output-format", "stream-json"), ("--session-id", "abc"), ("--name", "Fix add")):
            self.assertEqual(new[new.index(flag) + 1], value, flag)
        self.assertIn("--verbose", new)
        resumed = claude_cli.run_command(["claude.exe"], "sonnet", "medium", "abc", resume=True, name="x")
        self.assertEqual(resumed[resumed.index("--resume") + 1], "abc")
        self.assertNotIn("--session-id", resumed)
        self.assertNotIn("--name", resumed)

    def test_prep_command_is_read_only_and_hookless(self):
        cmd = claude_cli.prep_command(["claude.exe"], "haiku", {"type": "object"})
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Read,Grep,Glob")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(json.loads(cmd[cmd.index("--settings") + 1]), {"disableAllHooks": True})
        self.assertEqual(json.loads(cmd[cmd.index("--json-schema") + 1]), {"type": "object"})

    def test_messages(self):
        self.assertEqual(json.loads(claude_cli.user_message("hé")),
                         {"type": "user", "message": {"role": "user", "content": "hé"}})
        self.assertEqual(json.loads(claude_cli.interrupt_message("r1"))["request"], {"subtype": "interrupt"})

    def test_child_env_drops_session_variables_only(self):
        env = {"PATH": "x", "CLAUDE_CODE_ENTRYPOINT": "claude-vscode", "CLAUDECODE": "1",
               "CLAUDE_CONFIG_DIR": "keep"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(claude_cli.child_env(), {"PATH": "x", "CLAUDE_CONFIG_DIR": "keep"})

    def test_find_exe_prefers_config(self):
        self.assertEqual(claude_cli.find_exe({"claude_exe": r"C:\x\claude.exe"}), r"C:\x\claude.exe")

    def test_pid_alive(self):
        self.assertTrue(claude_cli.pid_alive(os.getpid()))
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        self.assertFalse(claude_cli.pid_alive(proc.pid))
        self.assertFalse(claude_cli.pid_alive(None))


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_claude_cli -v`
Expected: ERROR, `ImportError: cannot import name 'claude_cli' from 'console'`.

- [x] **Step 3: Create `console/claude_cli.py`**

```python
"""Everything about the `claude` executable: where it is, the commands we run, the child environment,
and the Windows process helpers. Commands are argument lists, never shell strings."""
import ctypes
import json
import os
import shutil
import subprocess
from pathlib import Path

MODELS = ["haiku", "sonnet", "opus", "fable"]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]

# Set by a Claude Code session for its own children. A run started from a window that was itself
# launched from a Claude Code terminal must not inherit them (wrong entrypoint, wrong parent session).
SESSION_ENV = {
    "CLAUDECODE", "CLAUDE_AGENT_SDK_VERSION", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
    "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_SSE_PORT", "CLAUDE_EFFORT",
    "CLAUDE_PID",
}
STOP_FOOTER = ("\n\nIf you must stop for a decision only Fred can make, end your final message with "
               "one line: STOP: <question>")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
BREAKAWAY = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)


def find_exe(cfg: dict):
    """The real claude.exe. Never the npm .cmd shim: batch files re-parse their arguments."""
    if cfg.get("claude_exe"):
        return cfg["claude_exe"]
    exe = shutil.which("claude.exe")
    if exe:
        return exe
    shim = shutil.which("claude.cmd") or shutil.which("claude")
    if shim:
        cand = Path(shim).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if cand.exists():
            return str(cand)
    return None


def child_env() -> dict:
    return {k: v for k, v in os.environ.items() if k.upper() not in SESSION_ENV}


def prep_command(exe: list, model: str, schema: dict) -> list:
    """Read-only, no hooks (keeps Prep out of the event log), no skills or MCP (cheaper)."""
    return exe + ["-p", "--model", model, "--effort", "low", "--tools", "Read,Grep,Glob",
                  "--permission-mode", "dontAsk", "--disable-slash-commands", "--strict-mcp-config",
                  "--settings", '{"disableAllHooks": true}', "--no-session-persistence",
                  "--output-format", "json", "--json-schema", json.dumps(schema)]


def run_command(exe: list, model: str, effort: str, session_id: str, resume: bool = False,
                name: str = "") -> list:
    """D5: auto mode, nobody answers prompts (a denial ends up in the result). Prompts go in on stdin."""
    cmd = exe + ["-p", "--model", model, "--effort", effort, "--permission-mode", "auto",
                 "--permission-prompts", "none", "--input-format", "stream-json",
                 "--output-format", "stream-json", "--verbose"]
    cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
    if name and not resume:
        cmd += ["--name", name]
    return cmd


def terminal_command(exe: list, session_id: str) -> list:
    return exe + ["--resume", session_id]


def user_message(text: str) -> bytes:
    msg = {"type": "user", "message": {"role": "user", "content": text}}
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")


def interrupt_message(request_id: str) -> bytes:
    msg = {"type": "control_request", "request_id": request_id, "request": {"subtype": "interrupt"}}
    return (json.dumps(msg) + "\n").encode("utf-8")


def pid_alive(pid) -> bool:
    if not pid:
        return False
    if os.name != "nt":
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False
    k = ctypes.windll.kernel32
    handle = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    code = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(handle, ctypes.byref(code))
    k.CloseHandle(handle)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


def kill_tree(pid) -> None:
    """Last resort for a run this service did not start (no stdin to send an interrupt to)."""
    subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True,
                   creationflags=NO_WINDOW)


def git_head(cwd: str) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True,
                             timeout=10, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def git_changed(cwd: str, commit: str):
    """Files changed since `commit` (committed or not) plus untracked files; None if unknown."""
    if not commit:
        return None
    names = set()
    for cmd in (["git", "diff", "--name-only", commit], ["git", "ls-files", "--others", "--exclude-standard"]):
        try:
            out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10,
                                 creationflags=NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        names.update(line for line in out.stdout.splitlines() if line.strip())
    return len(names)
```

- [x] **Step 4: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 46 tests ... OK`.

- [x] **Step 5: Commit**

```bash
git add console/claude_cli.py tests/test_claude_cli.py
git commit -m "feat: claude command builder, child env, Windows process helpers"
```

**DONE WHEN**
- [x] 46 tests OK; `git status --short` empty.

---

### Task 3: Prep

**Files:**
- Create: `console/prep.py`, `console/prep_prompt.md`, `tests/fake_claude.py`
- Test: `tests/test_prep.py`

- [x] **Step 1: Create `tests/fake_claude.py`** (used by Tasks 3-5; `unittest discover` skips it: its name does not start with `test`)

```python
"""A stand-in for claude.exe in tests: same flags, same JSON shapes (recorded from Claude Code 2.1.288).

Prep (--json-schema): reads the prompt on stdin, prints one result object.
Run (--input-format stream-json): per user message prints init / assistant / result.
  "SLOW" in the message: prints the assistant line, then waits for an interrupt or EOF.
  "DENY" in the message: the result carries one permission denial.
"""
import json
import sys


def out(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else ""


def result(sid, subtype="success", denials=()):
    return {"type": "result", "subtype": subtype, "session_id": sid, "total_cost_usd": 0.01,
            "num_turns": 2, "permission_denials": list(denials), "is_error": subtype != "success"}


def prep():
    raw = sys.stdin.read()
    fields = {"goal": "Fix add() in calc.py", "where": "calc.py:2", "keep": "the signature",
              "done_when": "py -m unittest passes", "last_decisions": "", "question": "",
              "route": {"type": "mechanical", "model": "sonnet", "effort": "low"},
              "reason": "one-line fix with a clear spec"}
    if "BROKEN" in raw:
        print("not json")
        return 0
    out({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.03,
         "num_turns": 5, "result": json.dumps(fields), "structured_output": fields})
    return 0


def run():
    sid = arg("--session-id") or arg("--resume")
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("type") != "user":
            continue
        text = msg["message"]["content"]
        out({"type": "system", "subtype": "init", "session_id": sid, "cwd": "."})
        out({"type": "assistant", "session_id": sid, "parent_tool_use_id": None, "message": {
            "role": "assistant", "content": [
                {"type": "text", "text": "echo: " + text},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "calc.py"}}]}})
        if "SLOW" in text:
            nxt = sys.stdin.readline()
            if nxt and json.loads(nxt).get("type") == "control_request":
                req = json.loads(nxt)
                out({"type": "control_response", "response": {"subtype": "success",
                                                              "request_id": req["request_id"]}})
                out({"type": "user", "session_id": sid, "parent_tool_use_id": None, "message": {
                    "role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]}})
                out(result(sid, "error_during_execution"))
                return 1
        denials = [{"tool_name": "Bash", "tool_input": {"command": "git push"}}] if "DENY" in text else []
        out(result(sid, denials=denials))
    return 0


if __name__ == "__main__":
    sys.exit(prep() if "--json-schema" in sys.argv else run())
```

- [x] **Step 2: Create `tests/test_prep.py`**

```python
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from console import paths, prep

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
FIELDS = {"goal": "Fix add()", "where": "calc.py", "keep": "", "done_when": "tests pass",
          "last_decisions": "", "question": "which file?", "reason": "small",
          "route": {"type": "mechanical", "model": "sonnet", "effort": "low"}}


class PrepTest(unittest.TestCase):
    def test_format_prompt_skips_empty_fields(self):
        self.assertEqual(prep.format_prompt(FIELDS),
                         "Goal: Fix add()\nWhere: calc.py\nDone when: tests pass\nOpen question: which file?")

    def test_build_prompt_inserts_the_request(self):
        text = prep.build_prompt("  make $HOME {x} work  ")
        self.assertTrue(text.rstrip().endswith("Request:\nmake $HOME {x} work"))
        self.assertIn("| risky |", text)

    def test_parse_output(self):
        good = json.dumps({"is_error": False, "structured_output": FIELDS, "total_cost_usd": 0.03, "num_turns": 5})
        self.assertEqual(prep.parse_output(good)["fields"]["goal"], "Fix add()")
        for bad in ("nope", json.dumps({"is_error": True, "result": "boom"}), json.dumps({"result": "x"}),
                    json.dumps({"structured_output": dict(FIELDS, route={"model": "gpt", "effort": "low"})})):
            with self.assertRaises(prep.PrepError):
                prep.parse_output(bad)

    def test_run_prep_saves_the_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = copy.deepcopy(paths.DEFAULTS)
            card = prep.run_prep(cfg, Path(tmp), tmp, "fix the add function", FAKE)
            self.assertEqual(card["route"], {"type": "mechanical", "model": "sonnet", "effort": "low"})
            self.assertTrue(card["prompt"].startswith("Goal: Fix add() in calc.py\nWhere: calc.py:2"))
            self.assertEqual(prep.load(Path(tmp), card["id"])["raw"], "fix the add function")
            self.assertIsNone(prep.load(Path(tmp), "../x"))
            with self.assertRaises(prep.PrepError):
                prep.run_prep(cfg, Path(tmp), tmp, "BROKEN", FAKE)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 3: Run it to see it fail**

Run: `py -m unittest tests.test_prep -v`
Expected: ERROR, `ImportError: cannot import name 'prep' from 'console'`.

- [x] **Step 4: Create `console/prep_prompt.md`**

````markdown
You are a prompt formatter for Claude Code. Fred typed the request at the end for the project in the
current folder. Do three things, then answer with the JSON object only.

1. Scout (at most 8 tool calls, Read / Grep / Glob only). Read CLAUDE.md first if it exists, then the
   History section of PLAN.md if it exists, then routing-misses.md if it exists. Find the files,
   functions and rules the request touches.
2. Enhance: rewrite the request so another model can do it with no other context. Do not solve the
   task. Do not invent requirements. If something essential is unclear, ask one question in
   `question` (else "").
3. Route: pick the cheapest route that should succeed. A line in routing-misses.md that matches this
   kind of task overrides the table.

| type | when | model | effort |
|---|---|---|---|
| mechanical | rename, copy, docs text, a 1-2 file edit with a clear spec | sonnet | low |
| lookup | find, explain, summarise, read many files, no edits | haiku | low |
| normal | a feature or fix with a clear spec or plan | sonnet | medium |
| risky | database schema, threading, security, installer or updater, anything near user data | opus | high |
| vague | design-heavy or unclear (and ask in `question`) | opus | high |

Fields: goal (one sentence), where (files and functions, short), keep (what must not break),
done_when (a check that can be run), last_decisions (from PLAN.md History, one line each, or ""),
question, route {type, model, effort}, reason (one sentence: why this route).

Request:
$raw
````

- [x] **Step 5: Create `console/prep.py`**

```python
"""Prep (D3, D4): a read-only Haiku pass scouts the project, rewrites the prompt and picks a route.
The card always waits for Fred; nothing here starts a run."""
import json
import secrets
import subprocess
import time
from pathlib import Path
from string import Template

from . import claude_cli, redact

PROMPT_FILE = Path(__file__).resolve().parent / "prep_prompt.md"
TYPES = ["mechanical", "lookup", "normal", "risky", "vague"]
_TEXT = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "goal": _TEXT, "where": _TEXT, "keep": _TEXT, "done_when": _TEXT,
        "last_decisions": _TEXT, "question": _TEXT, "reason": _TEXT,
        "route": {"type": "object", "properties": {
            "type": {"type": "string", "enum": TYPES},
            "model": {"type": "string", "enum": claude_cli.MODELS},
            "effort": {"type": "string", "enum": claude_cli.EFFORTS},
        }, "required": ["type", "model", "effort"]},
    },
    "required": ["goal", "where", "keep", "done_when", "last_decisions", "question", "route", "reason"],
}
LABELS = [("goal", "Goal"), ("where", "Where"), ("keep", "Keep"), ("done_when", "Done when"),
          ("last_decisions", "Last decisions"), ("question", "Open question")]


class PrepError(Exception):
    pass


def build_prompt(raw: str) -> str:
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(raw=raw.strip())


def format_prompt(fields: dict) -> str:
    """The enhanced prompt as Fred sees and edits it on the card."""
    lines = []
    for key, label in LABELS:
        value = str(fields.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def parse_output(stdout: str) -> dict:
    """The `structured_output` of `claude -p --output-format json --json-schema ...`."""
    try:
        data = json.loads(stdout)
    except ValueError:
        raise PrepError("Prep returned no JSON: " + redact.clip(stdout, 200))
    if not isinstance(data, dict):
        raise PrepError("Prep returned no JSON object")
    if data.get("is_error"):
        raise PrepError("Prep failed: " + redact.clip(data.get("result", ""), 200))
    fields = data.get("structured_output")
    if not isinstance(fields, dict) or not isinstance(fields.get("route"), dict):
        raise PrepError("Prep returned no structured output")
    route = fields["route"]
    if route.get("model") not in claude_cli.MODELS or route.get("effort") not in claude_cli.EFFORTS:
        raise PrepError("Prep picked an unknown route")
    return {"fields": fields, "cost": data.get("total_cost_usd") or 0, "turns": data.get("num_turns") or 0}


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def run_prep(cfg: dict, folder: Path, project_dir: str, raw: str, exe: list) -> dict:
    """Blocking (about 10-30 s). Saves preps/<id>.json and returns the card."""
    cmd = claude_cli.prep_command(exe, cfg["prep_model"], SCHEMA)
    try:
        out = subprocess.run(cmd, cwd=project_dir, input=build_prompt(raw).encode("utf-8"),
                             capture_output=True, timeout=cfg["prep_timeout_s"], env=claude_cli.child_env(),
                             creationflags=claude_cli.NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise PrepError(f"Prep took longer than {cfg['prep_timeout_s']} s")
    except OSError as exc:
        raise PrepError(f"cannot start claude: {exc}")
    result = parse_output(out.stdout.decode("utf-8", "replace"))
    fields = result["fields"]
    card = {
        "id": new_id(), "ts": time.time(), "project_dir": project_dir, "raw": raw,
        "fields": fields, "prompt": format_prompt(fields), "route": fields["route"],
        "reason": fields.get("reason", ""), "cost": result["cost"], "turns": result["turns"],
    }
    preps = Path(folder) / "preps"
    preps.mkdir(parents=True, exist_ok=True)
    (preps / f"{card['id']}.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return card


def load(folder: Path, prep_id: str):
    if not prep_id or not all(c.isalnum() or c == "-" for c in prep_id):
        return None
    try:
        return json.loads((Path(folder) / "preps" / f"{prep_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
```

- [x] **Step 6: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 50 tests ... OK`.

- [x] **Step 7: Commit**

```bash
git add console/prep.py console/prep_prompt.md tests/fake_claude.py tests/test_prep.py
git commit -m "feat: Prep - read-only Haiku pass that rewrites the prompt and picks a route"
```

**DONE WHEN**
- [x] 50 tests OK; `git status --short` empty.

---

### Task 4: Runs

**Files:**
- Create: `console/runs.py`
- Modify: `console/events.py` (full file below: adds `append`)
- Test: `tests/test_runs.py`

- [x] **Step 1: Create `tests/test_runs.py`**

```python
import copy
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from console import events, paths, runs

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]


def wait_for(check, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        if check():
            return True
        time.sleep(0.1)
    return False


class RunsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        self.mgr = runs.RunManager(copy.deepcopy(paths.DEFAULTS), self.folder, FAKE)

    def tearDown(self):
        for proc in list(self.mgr.live.values()):
            proc.kill()
        end = time.time() + 10
        while self.mgr.live and time.time() < end:  # let the watcher threads finish
            time.sleep(0.05)
        self.tmp.cleanup()

    def log(self):
        return events.LogReader(self.folder).read_new()

    def ended(self, sid):
        return [r for r in self.log() if r["event"] == "run_ended" and r["session_id"] == sid]

    def test_run_writes_stream_and_events(self):
        sid = self.mgr.start(str(self.project), "fix add", "sonnet", "low", title="Fix add", route="r", prep="p1")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        started = [r for r in self.log() if r["event"] == "run_started"][0]
        self.assertEqual((started["session_id"], started["title"], started["prep"]), (sid, "Fix add", "p1"))
        self.assertEqual((started["project"], started["project_dir"]), ("proj", str(self.project)))
        end = self.ended(sid)[0]
        self.assertEqual((end["subtype"], end["cost"], end["stopped"], end["interrupted"]),
                         ("success", 0.01, False, False))
        items = runs.chat(self.mgr.stream_path(sid), str(self.project))
        self.assertEqual([i["role"] for i in items], ["you", "claude", "tool", "result"])
        self.assertEqual(items[0]["text"], "fix add")
        self.assertIn("STOP: <question>", items[1]["text"])  # the footer reached claude
        self.assertEqual(items[2]["text"], "Read calc.py")
        self.assertFalse(self.mgr.is_live(sid))

    def test_stop_sends_an_interrupt(self):
        sid = self.mgr.start(str(self.project), "SLOW task", "sonnet", "low")
        self.assertTrue(wait_for(lambda: "echo: SLOW" in self.mgr.stream_path(sid).read_text(encoding="utf-8")))
        self.assertEqual(self.mgr.stop(sid), "interrupt")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        self.assertEqual((self.ended(sid)[0]["stopped"], self.ended(sid)[0]["interrupted"]), (True, False))
        self.assertIn("stopped", [i["text"] for i in runs.chat(self.mgr.stream_path(sid))])
        self.assertEqual(self.mgr.stop(sid), "not running")

    def test_resume_keeps_the_session(self):
        sid = self.mgr.start(str(self.project), "first", "sonnet", "low")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        self.assertEqual(self.mgr.start(str(self.project), "second", "sonnet", "low", resume=sid), sid)
        self.assertTrue(wait_for(lambda: len(self.ended(sid)) == 2))
        texts = [i["text"] for i in runs.chat(self.mgr.stream_path(sid)) if i["role"] == "you"]
        self.assertEqual(texts, ["first", "second"])

    def test_reconcile_marks_a_cut_run_interrupted(self):
        self.mgr.runs.mkdir(parents=True)
        self.mgr.stream_path("dead").write_text('{"type":"cc_prompt","text":"x"}\n', encoding="utf-8")
        self.mgr._save_meta({"session_id": "dead", "pid": 4, "cwd": str(self.project), "offset": 0,
                             "model": "sonnet", "effort": "low", "ended": None})
        with mock.patch.object(runs.claude_cli, "pid_alive", return_value=False):
            self.assertEqual(self.mgr.reconcile(), 1)
            self.assertEqual(self.mgr.reconcile(), 0)
        self.assertEqual(self.ended("dead")[0]["interrupted"], True)

    def test_result_record_lists_denials(self):
        rec = runs.result_record("s", {"subtype": "success", "total_cost_usd": 0.2, "permission_denials": [
            {"tool_name": "Bash", "tool_input": {"command": "git push --force"}}]}, 0, False)
        self.assertEqual(rec["denials"], [{"tool": "Bash", "what": "git push --force"}])
        self.assertTrue(runs.result_record("s", None, None, False)["interrupted"])

    def test_prune_old_run_files(self):
        self.mgr.runs.mkdir(parents=True)
        old = self.mgr.stream_path("old")
        old.write_text("", encoding="utf-8")
        os.utime(old, (1, 1))
        self.mgr.stream_path("new").write_text("", encoding="utf-8")
        self.assertEqual(runs.prune(self.folder, 14), ["runs/old.jsonl"])


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_runs -v`
Expected: ERROR, `ImportError: cannot import name 'runs' from 'console'`.

- [x] **Step 3: Replace `console/events.py`** with:

```python
"""Read the daily event files incrementally and prune old ones."""
import json
import time
from pathlib import Path


class LogReader:
    """Returns only lines added since the last call; skips broken lines."""

    def __init__(self, folder: Path, days: int = 2):
        self.folder = Path(folder)
        self.days = days
        self.offsets = {}

    def files(self):
        return sorted(self.folder.glob("events-*.jsonl"))[-self.days:]

    def read_new(self) -> list:
        out = []
        for path in self.files():
            start = self.offsets.get(path.name, 0)
            try:
                with open(path, "rb") as fh:
                    fh.seek(start)
                    chunk = fh.read()
            except OSError:
                continue
            end = chunk.rfind(b"\n")
            if end < 0:
                continue  # nothing, or a line still being written
            self.offsets[path.name] = start + end + 1
            for raw in chunk[:end].splitlines():
                try:
                    rec = json.loads(raw.decode("utf-8"))
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("session_id") and rec.get("event"):
                    out.append(rec)
        out.sort(key=lambda r: r.get("ts", 0))
        return out


def append(folder: Path, rec: dict) -> None:
    """The service's own lines (run_started, run_ended), same format and file as the hook's."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    day = time.strftime("%Y-%m-%d", time.localtime(rec["ts"]))
    line = json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(folder / f"events-{day}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(line)


def prune(folder: Path, retention_days: int, now: float = None) -> list:
    """Delete events-YYYY-MM-DD.jsonl files older than `retention_days`. Returns names."""
    cutoff = time.strftime("%Y-%m-%d", time.localtime((now or time.time()) - retention_days * 86400))
    removed = []
    for path in Path(folder).glob("events-*.jsonl"):
        day = path.stem[len("events-"):]
        if day < cutoff:
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass
    return removed
```

- [x] **Step 4: Create `console/runs.py`**

```python
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
```

- [x] **Step 5: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 56 tests ... OK` (about 3 s more: the run tests start the fake claude).

- [x] **Step 6: Commit**

```bash
git add console/events.py console/runs.py tests/test_runs.py
git commit -m "feat: window runs - detached claude -p, stream copy, interrupt, interrupted detection"
```

**DONE WHEN**
- [x] 56 tests OK; `git status --short` empty.

---

### Task 5: Service routes

**Files:**
- Modify: `console/server.py` (full file below), `console/__main__.py` (two edits)
- Test: `tests/test_server.py` (full file below; 4 new tests)

- [x] **Step 1: Replace `tests/test_server.py`** with:

```python
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from console import guard, paths, server


class GuardTest(unittest.TestCase):
    def test_host(self):
        self.assertTrue(guard.host_ok("127.0.0.1:8770", 8770))
        self.assertTrue(guard.host_ok("localhost:8770", 8770))
        self.assertFalse(guard.host_ok("evil.example:8770", 8770))
        self.assertFalse(guard.host_ok(None, 8770))

    def test_post_header(self):
        self.assertTrue(guard.post_ok({"X-CC": "1"}))
        self.assertFalse(guard.post_ok({}))


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        folder = Path(self.tmp.name)
        (folder / "events-2026-10-10.jsonl").write_text(
            json.dumps({"ts": 9e12, "event": "UserPromptSubmit", "session_id": "s1", "prompt": "hello"}) + "\n",
            encoding="utf-8")
        cfg = paths.load_config()
        self.httpd, self.hub = server.make_server(cfg, port=0, folder=folder)
        self.hub.poll_once()
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def get(self, path, host=None, method="GET", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest(method, path, skip_host=True)
        conn.putheader("Host", host or f"127.0.0.1:{self.port}")
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        conn.endheaders()
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_state_endpoint(self):
        status, body = self.get("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["sessions"][0]["title"], "hello")

    def test_foreign_host_is_refused(self):
        self.assertEqual(self.get("/api/state", host="evil.example")[0], 403)

    def test_post_needs_header(self):
        self.assertEqual(self.get("/api/state", method="POST")[0], 403)
        self.assertEqual(self.get("/api/x", method="POST", headers={"X-CC": "1"})[0], 404)

    def test_static_and_ping(self):
        self.assertEqual(self.get("/")[0], 200)
        self.assertEqual(json.loads(self.get("/api/ping")[1]), {"app": "claude-console"})


class RunServerTest(unittest.TestCase):
    """POST routes with the fake claude: prep, run, chat, stop, answer, draft."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        cfg = dict(paths.load_config(), projects=[str(self.project)])
        fake = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
        self.httpd, self.hub = server.make_server(cfg, port=0, folder=self.folder, exe=fake)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        for proc in list(self.hub.runs.live.values()):
            proc.kill()
        end = time.time() + 10
        while self.hub.runs.live and time.time() < end:  # let the watcher threads finish
            time.sleep(0.05)
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def call(self, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        headers = {"Host": f"127.0.0.1:{self.port}"}
        if body is None:
            conn.request("GET", path, headers=headers)
        else:
            headers.update({"X-CC": "1", "Content-Type": "application/json"})
            conn.request("POST", path, body=json.dumps(body).encode("utf-8"), headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read() or b"null")
        conn.close()
        return resp.status, data

    def session(self, sid):
        self.hub.poll_once()
        return next((s for s in self.hub.snapshot()["sessions"] if s["id"] == sid), None)

    def test_only_listed_projects_can_run(self):
        self.assertEqual(self.call("/api/run", {"project_dir": self.tmp.name, "prompt": "x"})[0], 403)
        self.assertEqual(self.call("/api/prep", {"project_dir": "C:/Windows", "prompt": "x"})[0], 403)
        self.assertEqual(self.call("/api/run", {"project_dir": str(self.project), "prompt": " "})[0], 400)
        self.assertEqual(self.call("/api/run", {"project_dir": str(self.project), "prompt": "x",
                                                "model": "gpt-9"})[0], 400)
        self.assertEqual(self.call("/api/stop", {"session": "nope"})[0], 404)

    def test_prep_then_run_then_chat(self):
        status, card = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "fix add"})
        self.assertEqual(status, 200)
        status, data = self.call("/api/run", {"project_dir": str(self.project), "prompt": card["prompt"],
                                              "model": "sonnet", "effort": "low", "prep": card["id"]})
        self.assertEqual(status, 200)
        sid = data["session"]
        row = self.session(sid)
        self.assertEqual((row["source"], row["title"], row["route"]),
                         ("window", "Fix add() in calc.py", "mechanical"))
        end = time.time() + 15
        while time.time() < end and self.session(sid)["run_live"]:
            time.sleep(0.1)
        self.assertEqual(self.session(sid)["cost"], 0.01)
        chat = self.call(f"/api/chat?session={sid}")[1]
        self.assertEqual([i["role"] for i in chat["items"]], ["you", "claude", "tool", "result"])
        self.assertFalse(chat["live"])

    def test_answer_resumes_and_stop_interrupts(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "SLOW one"})[1]["session"]
        self.assertEqual(self.call("/api/answer", {"session": sid, "text": "go"})[0], 409)  # still running
        end = time.time() + 15
        while time.time() < end and "echo" not in self.hub.runs.stream_path(sid).read_text(encoding="utf-8"):
            time.sleep(0.1)
        self.assertEqual(self.call("/api/stop", {"session": sid}), (200, {"stop": "interrupt"}))
        while time.time() < end and self.session(sid)["run_live"]:
            time.sleep(0.1)
        self.assertEqual(self.session(sid)["stopped"], True)
        self.assertEqual(self.call("/api/answer", {"session": sid, "text": "go on"}), (200, {"session": sid}))

    def test_draft_and_config(self):
        self.assertEqual(self.call("/api/draft", {"text": "half a prompt"}), (200, {"ok": True}))
        self.assertEqual(self.call("/api/draft")[1], {"text": "half a prompt"})
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["projects"], cfg["claude"], cfg["default_model"]), ([str(self.project)], True, "sonnet"))


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_server -v`
Expected: ERROR in `RunServerTest` (`make_server() got an unexpected keyword argument 'exe'`); the 6 old tests pass.

- [x] **Step 3: Replace `console/server.py`** with:

```python
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
```

- [x] **Step 4: Edit `console/__main__.py`**

Find:
```python
from . import events, paths, server
```
Replace with:
```python
from . import events, paths, runs, server
```
Find:
```python
    events.prune(paths.home(), cfg["retention_days"])
```
Replace with:
```python
    events.prune(paths.home(), cfg["retention_days"])
    runs.prune(paths.home(), cfg["retention_days"])
```

- [x] **Step 5: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 60 tests ... OK`.

- [x] **Step 6: Commit**

```bash
git add console/server.py console/__main__.py tests/test_server.py
git commit -m "feat: service routes for Prep, Run, Stop, Answer, Open in terminal, Chat, draft"
```

**DONE WHEN**
- [x] 60 tests OK; `git status --short` empty.

---

### Task 6: Window

**Files:**
- Modify: `web/index.html`, `web/app.js`, `web/style.css` (full files below)

- [x] **Step 1: Replace `web/index.html`** with:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Claude Console</title>
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <header class="row hd">
    <span id="back" class="link" hidden>&larr;</span>
    <span class="name">Claude Console</span>
    <select id="project" class="m"><option value="">All projects</option></select>
    <span id="counts" class="m"></span>
  </header>
  <main id="home"></main>
  <main id="prep" hidden></main>
  <main id="detail" hidden>
    <div id="d-head"></div>
    <div id="d-actions"></div>
    <div id="d-tabs" class="row m tabs"></div>
    <div id="d-body"></div>
  </main>
  <footer id="composer">
    <textarea id="prompt" class="m" rows="3" spellcheck="false"></textarea>
    <div id="msg" class="m"></div>
  </footer>
  <footer id="strip" class="strip m"></footer>
  <script src="/app.js"></script>
</body>
</html>
```

- [x] **Step 2: Replace `web/app.js`** with:

```javascript
// Claude Console window: renders /api/stream snapshots; phase 2 adds the prompt box, Prep card and runs.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const GROUPS = [["needs", "Needs you"], ["working", "Working"], ["done", "Done today"]];
const RESUME_TEXT = "You were interrupted. Check `git diff` first, then finish the task.";

let snap = null;
let cfg = null;       // /api/config
let view = "home";    // home | prep | detail
let openId = null;
let card = null;      // the Prep card on screen
let tab = "steps";
let busy = false;
let live = false;
let actionsSig = "";
let draftTimer = null;
let note = "";       // the composer's last message (an error stays until Fred types)

function kTokens(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "K" : String(n || 0); }
function clock(ts) { return new Date(ts * 1000).toTimeString().slice(0, 8); }
function baseName(p) { return String(p || "").split(/[\\/]/).filter(Boolean).pop() || p; }
function routeText(s) {
  const run = [s.model, s.effort].filter(Boolean).join("/");
  if (s.route === "unrouted") return run ? "unrouted · " + run : "unrouted";
  return run ? s.route + " · " + run : s.route;
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "X-CC": "1", "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const resp = await fetch(path, opts);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || "HTTP " + resp.status);
  return data;
}

function gauge(s, tokens = s.ctx_tokens) {
  if (s.ctx_fill == null) return '<span class="mut">ctx ?</span>';
  const hint = s.ctx_tone === "red" ? " handoff" : s.ctx_tone === "yellow" ? " soon" : "";
  return `<span class="${s.ctx_tone}">ctx <span class="bar"><i style="width:${Math.max(2, Math.round(s.ctx_fill * 100))}%"></i></span> ${kTokens(tokens)}${hint}</span>`;
}

function sessionRows(s) {
  let html = `<div class="row m session" data-id="${esc(s.id)}">
    <span class="${s.tone}">${s.symbol} ${esc(s.text)}</span>
    <span class="title">${esc(s.title)}</span>
    ${s.two_writers ? '<span class="badge warning">2 writers</span>' : ""}
    ${gauge(s)}</div>`;
  html += `<div class="row m ind mut"><span class="title">${esc(s.project)} &middot; ${esc(s.source)} &middot; ${esc(routeText(s))}${s.doing ? " &middot; " + esc(s.doing) : ""}</span></div>`;
  if (s.stop_question) html += `<div class="note ask"><span class="warning">? STOP</span> ${esc(s.stop_question)}</div>`;
  if (s.denied) html += `<div class="note m"><span class="danger">&#9632; denied</span> ${esc(s.denied.tool)} ${esc(s.denied.what)} <span class="mut">${esc(s.denied.reason)}</span></div>`;
  if (s.failed) html += `<div class="note m"><span class="danger">&times; ${esc(s.failed.error)}</span> <span class="mut">${esc(s.failed.details)}</span></div>`;
  for (const a of s.agents) {
    html += `<div class="row m ind"><span class="${a.tone}">${a.symbol} ${esc(a.text)}</span>
      <span class="title">${esc(a.type)}${a.model ? " &middot; " + esc(a.model) : ""}${a.effort ? "/" + esc(a.effort) : ""}
      &middot; ${a.doing ? esc(a.doing) : a.steps + (a.steps === 1 ? " step" : " steps")}</span>
      ${a.tokens ? gauge(a, a.tokens) : ""}</div>`;
  }
  return html;
}

function visible(s) { return !$("project").value || s.project_dir === $("project").value; }

// -- home ----------------------------------------------------------------------------
function renderHome() {
  const rows = snap.sessions.filter(visible);
  let html = "";
  for (const [key, label] of GROUPS) {
    const list = rows.filter((s) => s.group === key);
    if (!list.length) continue;
    html += `<div class="sec">${label}</div>` + list.map(sessionRows).join("");
  }
  $("home").innerHTML = html || '<div class="empty">No Claude Code session in the last 24 h. Start one in VS Code or a terminal, or below.</div>';
}

function runnable() { return !!cfg && cfg.claude && cfg.projects.includes($("project").value); }

function hint() {
  if (!cfg) return "";
  if (!cfg.claude) return '<span class="danger">claude.exe not found: set "claude_exe" in config.json</span>';
  if (!runnable()) return `<span class="mut">To run: pick a project listed in "projects" of ${esc(cfg.config_path)}</span>`;
  return '<span class="mut">Enter = Prep &middot; Ctrl+Enter = Run raw &middot; Shift+Enter = new line</span>';
}

function say(html) { note = html || ""; $("msg").innerHTML = note || hint(); }

function renderComposer() {
  $("composer").hidden = view !== "home";
  $("prompt").disabled = busy || !runnable();
  $("prompt").placeholder = runnable() ? "Prompt for " + baseName($("project").value) : "";
  if (!busy) $("msg").innerHTML = note || hint();
}

function setBusy(on, text) {
  busy = on;
  note = "";
  renderComposer();
  if (on) say(`<span class="info">${esc(text)}</span>`);
}

async function doPrep() {
  const text = $("prompt").value.trim();
  if (!text || busy || !runnable()) return;
  setBusy(true, "Prep: Haiku is reading " + baseName($("project").value) + " (10-30 s) ...");
  try {
    card = await api("/api/prep", { project_dir: $("project").value, prompt: text });
    setBusy(false);
    showView("prep");
  } catch (e) {
    setBusy(false);
    say(`<span class="danger">Prep failed: ${esc(e.message)}</span>`);
  }
}

async function doRun(projectDir, prompt, model, effort, prepId) {
  if (busy) return;
  setBusy(true, "starting the run ...");
  try {
    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "" });
    $("prompt").value = "";
    saveDraft();
    card = null;
    setBusy(false);
    tab = "chat";
    openDetail(r.session);
  } catch (e) {
    setBusy(false);
    if (view === "prep") $("p-msg").innerHTML = `<span class="danger">${esc(e.message)}</span>`;
    else say(`<span class="danger">Run failed: ${esc(e.message)}</span>`);
  }
}

function runRaw() {
  const text = $("prompt").value.trim();
  if (text && runnable()) doRun($("project").value, text, cfg.default_model, cfg.default_effort, "");
}

function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => api("/api/draft", { text: $("prompt").value }).catch(() => {}), 600);
}

// -- Prep card -----------------------------------------------------------------------
function options(list, current) {
  return list.map((v) => `<option${v === current ? " selected" : ""}>${esc(v)}</option>`).join("");
}

function renderPrep() {
  const f = card.fields;
  $("prep").innerHTML = `
    <div class="sec">Prep &middot; ${esc(baseName(card.project_dir))}</div>
    <div class="row m mut">You typed</div>
    <div class="note">${esc(card.raw)}</div>
    ${f.where ? `<div class="row m mut"><span class="title">Scouted: ${esc(f.where)}</span></div>` : ""}
    <div class="row m mut">Enhanced prompt (edit freely)</div>
    <textarea id="p-prompt" class="m edit" rows="9" spellcheck="false">${esc(card.prompt)}</textarea>
    ${f.question ? `<div class="note ask"><span class="warning">? question</span> ${esc(f.question)}</div>` : ""}
    <div class="row m">Route
      <select id="p-model" class="m">${options(cfg.models, card.route.model)}</select>
      <select id="p-effort" class="m">${options(cfg.efforts, card.route.effort)}</select>
      <span class="title mut">${esc(card.route.type)}</span></div>
    ${card.reason ? `<div class="note mut">${esc(card.reason)}</div>` : ""}
    <div class="row m mut">Prep: $${Number(card.cost).toFixed(3)} &middot; ${card.turns} turns</div>
    <div class="actions">
      <button data-act="p-run" class="primary">Run</button>
      <button data-act="p-raw">Run raw</button>
      <button data-act="p-edit">Edit</button>
      <button data-act="p-cancel">Cancel</button>
    </div>
    <div id="p-msg" class="m note"></div>`;
  $("p-prompt").focus();
}

$("prep").addEventListener("click", (e) => {
  const act = e.target.dataset && e.target.dataset.act;
  if (!act || busy) return;
  if (act === "p-run") doRun(card.project_dir, $("p-prompt").value.trim(), $("p-model").value, $("p-effort").value, card.id);
  if (act === "p-raw") doRun(card.project_dir, card.raw, cfg.default_model, cfg.default_effort, "");
  if (act === "p-edit") { card = null; showView("home"); $("prompt").focus(); }
  if (act === "p-cancel") { card = null; $("prompt").value = ""; saveDraft(); showView("home"); }
});

// -- session detail ------------------------------------------------------------------
function renderActions(s) {
  const sig = [s.id, s.window, s.run_live, s.stop_question, s.state].join("|");
  if (sig === actionsSig) return;
  actionsSig = sig;
  if (!s.window) { $("d-actions").innerHTML = ""; return; }
  let html = '<div class="actions">';
  if (s.run_live) html += '<button data-act="stop">Stop</button>';
  else html += '<button data-act="terminal">Open in terminal</button>';
  if (!s.run_live && s.state === "interrupted") html += '<button data-act="resume" class="primary">Resume</button>';
  html += "</div>";
  if (!s.run_live && s.stop_question) {
    html += `<div class="answer"><input id="d-answer" class="m" placeholder="Answer: ${esc(s.stop_question)}">
      <button data-act="answer" class="primary">Answer</button></div>`;
  }
  html += '<div id="d-msg" class="m note"></div>';
  $("d-actions").innerHTML = html;
}

function renderTabs(s) {
  if (!s.window) tab = "steps";
  const tabs = s.window ? [["steps", "Steps"], ["chat", "Chat"]] : [["steps", "Steps"]];
  $("d-tabs").innerHTML = tabs.map(([k, label]) =>
    `<span class="tab${k === tab ? " on" : ""}" data-tab="${k}">${label}</span>`).join("");
}

async function renderBody(s) {
  if (tab === "chat") {
    const chat = await api("/api/chat?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "chat") return;
    let html = "";
    if (chat.start_commit) {
      const changed = chat.changed == null ? "?" : chat.changed;
      html += `<div class="row m mut">start ${esc(chat.start_commit.slice(0, 7))} &middot; ${changed} file(s) changed since</div>`;
    }
    html += chat.items.map((i) => `<div class="chat ${i.role}"><span class="who m">${esc(i.role)}</span><div class="text${i.role === "tool" || i.role === "result" ? " m" : ""}">${esc(i.text)}</div></div>`).join("")
      || '<div class="empty">Nothing yet.</div>';
    $("d-body").innerHTML = html;
    return;
  }
  const steps = await (await fetch("/api/steps?session=" + encodeURIComponent(s.id))).json();
  if (openId !== s.id || tab !== "steps") return;
  $("d-body").innerHTML = steps.slice().reverse().map((st) => `<div class="row m${st.denied ? " danger" : ""}">
      <span class="mut">${clock(st.ts)}</span><span>${esc(st.agent_type)}</span>
      <span class="title">${esc(st.tool)} ${esc(st.what)}</span></div>`).join("")
      || '<div class="empty">No tool calls yet.</div>';
}

function renderDetail() {
  const s = snap.sessions.find((x) => x.id === openId);
  if (!s) {
    $("d-head").innerHTML = '<div class="empty">Starting ... (the session shows up with its first event)</div>';
    return;
  }
  let head = sessionRows(s);
  const cost = s.window ? ` &middot; $${Number(s.cost).toFixed(2)}` : "";
  head += `<div class="row m mut">${s.prompts} prompt(s) &middot; ${s.compactions} compaction(s)${cost}${s.stopped ? " &middot; stopped by you" : ""}</div>`;
  if (s.route_reason) head += `<div class="note mut">${esc(s.route_reason)}</div>`;
  $("d-head").innerHTML = head;
  renderActions(s);
  renderTabs(s);
  renderBody(s).catch(() => {});
}

async function act(name, button) {
  const s = snap.sessions.find((x) => x.id === openId);
  if (!s) return;
  button.disabled = true;
  try {
    if (name === "stop") await api("/api/stop", { session: s.id });
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (name === "resume") await api("/api/answer", { session: s.id, text: RESUME_TEXT });
    if (name === "answer") {
      const text = $("d-answer").value.trim();
      if (!text) { button.disabled = false; return; }
      await api("/api/answer", { session: s.id, text });
      tab = "chat";
    }
    actionsSig = "";  // redraw from the next snapshot
  } catch (e) {
    button.disabled = false;
    $("d-msg").innerHTML = `<span class="danger">${esc(e.message)}</span>`;
  }
}

$("detail").addEventListener("click", (e) => {
  const t = e.target;
  if (t.dataset.tab) { tab = t.dataset.tab; render(); return; }
  if (t.dataset.act) act(t.dataset.act, t);
});
$("detail").addEventListener("keydown", (e) => {
  if (e.target.id === "d-answer" && e.key === "Enter") act("answer", document.querySelector('[data-act="answer"]'));
});

// -- frame ---------------------------------------------------------------------------
function renderStrip() {
  const c = snap.counts;
  let html = `<span>${live ? "service &#9679; ok" : '<span class="danger">service &#9675; offline</span>'}</span>
    <span>${c.needs} need you &middot; ${c.working} working &middot; ${c.done} done</span>`;
  for (const w of snap.writers) {
    html += `<span class="warning">2 writers: ${esc(baseName(w.project_dir))}</span>`;
  }
  $("strip").innerHTML = html;
  $("counts").innerHTML = c.needs ? `<span class="warning">! ${c.needs}</span>` : "";
}

function addProject(dir, label) {
  const select = $("project");
  if (dir && ![...select.options].some((o) => o.value === dir)) select.add(new Option(label, dir));
}

function renderProjects() {
  if (cfg) for (const p of cfg.projects) addProject(p, baseName(p) + " (runs)");
  if (snap) for (const s of snap.sessions) addProject(s.project_dir, s.project);
}

function render() {
  renderProjects();
  renderComposer();
  if (!snap) return;
  renderStrip();
  if (view === "detail") renderDetail();
  else if (view === "home") renderHome();
}

function showView(name) {
  view = name;
  for (const v of ["home", "prep", "detail"]) $(v).hidden = v !== name;
  $("back").hidden = name === "home";
  if (name === "prep") renderPrep();
  render();
}

function openDetail(id) { openId = id; actionsSig = ""; showView("detail"); }

$("home").addEventListener("click", (e) => {
  const row = e.target.closest(".session");
  if (row) { tab = "steps"; openDetail(row.dataset.id); }
});
$("back").addEventListener("click", () => { openId = null; showView("home"); });
$("project").addEventListener("change", render);
$("prompt").addEventListener("input", () => { note = ""; saveDraft(); });
$("prompt").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || e.shiftKey) return;
  e.preventDefault();
  if (e.ctrlKey) runRaw(); else doPrep();
});

function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => { live = true; snap = JSON.parse(e.data); render(); };
  es.onerror = () => { live = false; if (snap) renderStrip(); };
}

(async () => {
  try { cfg = await api("/api/config"); } catch (e) { cfg = null; }
  try { $("prompt").value = (await api("/api/draft")).text; } catch (e) { /* no draft */ }
  render();
  connect();
})();
```

- [x] **Step 3: Replace `web/style.css`** with:

```css
/* All styling lives here, as tokens first, so a visual rework only touches this file. */
:root {
  color-scheme: light dark;
  --bg: light-dark(#ffffff, #181818);
  --fg: light-dark(#1a1c1f, #ffffff);
  --mut: light-dark(rgb(26 28 31 / 52%), rgb(255 255 255 / 52%));
  --bd: light-dark(rgb(26 28 31 / 10%), rgb(255 255 255 / 10%));
  --info: light-dark(#1f7fd6, #83c3ff);
  --success: light-dark(#00873a, #40c977);
  --warning: light-dark(#a86400, #f5b74a);
  --danger: light-dark(#ba2623, #fa423e);
  --row: 28px;
  --font: "Segoe UI", system-ui, sans-serif;
  --mono: "Cascadia Mono", Consolas, monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--fg); font: 13px/1.45 var(--font); }
body { display: flex; flex-direction: column; min-height: 100vh; }
main { flex: 1; overflow-y: auto; }
.m { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; }
.row { display: flex; align-items: center; gap: 8px; min-height: var(--row); padding: 0 10px;
       border-bottom: 1px solid var(--bd); }
.hd { position: sticky; top: 0; background: var(--bg); font-weight: 500; }
.hd .name { flex: 1; }
.hd select { background: transparent; color: var(--fg); border: 1px solid var(--bd); }
.sec { padding: 6px 10px 2px; font-size: 11px; letter-spacing: .06em; text-transform: uppercase;
       color: var(--mut); }
.mut { color: var(--mut); }
.info { color: var(--info); } .success { color: var(--success); }
.warning { color: var(--warning); } .danger { color: var(--danger); }
.green { color: var(--success); } .yellow { color: var(--warning); } .red { color: var(--danger); }
.session { cursor: pointer; }
.session:hover { background: color-mix(in srgb, var(--fg) 5%, transparent); }
.title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ind { padding-left: 26px; }
.note { padding: 4px 10px 6px 26px; border-bottom: 1px solid var(--bd); }
.ask { border-left: 3px solid var(--warning); }
.bar { display: inline-block; width: 56px; height: 6px; border: 1px solid var(--bd);
       position: relative; vertical-align: middle; }
.bar i { position: absolute; inset: 0 auto 0 0; background: currentColor; }
.badge { border: 1px solid currentColor; border-radius: 3px; padding: 0 4px; font-size: 11px; }
.link { cursor: pointer; color: var(--info); }
.empty { padding: 24px 10px; color: var(--mut); }
.strip { display: flex; gap: 12px; flex-wrap: wrap; padding: 4px 10px; font-size: 11px;
         color: var(--mut); border-top: 1px solid var(--bd); }

/* phase 2: prompt box, Prep card, session actions, Chat */
#composer { border-top: 1px solid var(--bd); padding: 6px 10px 4px; }
#composer textarea, .edit { width: 100%; resize: vertical; background: transparent; color: var(--fg);
  border: 1px solid var(--bd); padding: 4px 6px; font: inherit; }
#composer textarea:focus, .edit:focus, .answer input:focus { outline: 1px solid var(--info); }
.edit { display: block; margin: 4px 10px; width: calc(100% - 20px); }
#msg { min-height: 18px; font-size: 11px; }
select { background: transparent; color: var(--fg); border: 1px solid var(--bd); }
.actions { display: flex; gap: 6px; padding: 6px 10px; flex-wrap: wrap; }
button { font: 12px var(--font); color: var(--fg); background: transparent; border: 1px solid var(--bd);
  border-radius: 3px; padding: 2px 10px; cursor: pointer; }
button:hover { border-color: var(--info); }
button.primary { border-color: var(--info); color: var(--info); }
button:disabled { opacity: .5; cursor: progress; }
.answer { display: flex; gap: 6px; padding: 0 10px 6px; }
.answer input { flex: 1; background: transparent; color: var(--fg); border: 1px solid var(--bd); padding: 2px 6px; }
.tabs { gap: 14px; }
.tab { cursor: pointer; color: var(--mut); }
.tab.on { color: var(--fg); border-bottom: 2px solid var(--info); }
.chat { display: flex; gap: 8px; padding: 4px 10px; border-bottom: 1px solid var(--bd); }
.chat .who { flex: 0 0 48px; color: var(--mut); font-size: 11px; }
.chat .text { flex: 1; min-width: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.chat.you .text { color: var(--info); }
.chat.tool .text, .chat.result .text { color: var(--mut); }
.chat.note .text { color: var(--warning); }
```

- [x] **Step 4: Syntax check**

Run: `node --check web/app.js && echo ok`
Expected: `ok`. Then `py -m unittest discover -s tests` -> `Ran 60 tests ... OK`.

- [x] **Step 5: Browser check with the fake claude** (no real model calls)

In Git Bash from the repo root (the fake needs an absolute path: runs start in the project folder):

```bash
mkdir -p "$TEMP/cc-smoke/proj" && git -C "$TEMP/cc-smoke/proj" init -q && git -C "$TEMP/cc-smoke/proj" -c user.name=x -c user.email=x@x commit -q --allow-empty -m init
py -c "
import os, sys
from console import paths, server
smoke = os.path.join(os.environ['TEMP'], 'cc-smoke')
cfg = dict(paths.DEFAULTS, projects=[os.path.join(smoke, 'proj')])
httpd, hub = server.make_server(cfg, port=8772, folder=os.path.join(smoke, 'home'),
                                exe=[sys.executable, os.path.abspath('tests/fake_claude.py')])
hub.start(); print('http://127.0.0.1:8772/'); httpd.serve_forever()"
```

Open `http://127.0.0.1:8772/` and check, in order:
1. With "All projects" the prompt box is disabled and the hint points to the project list (Task 6b); pick `proj (runs)`: the box enables, the hint reads `Enter = Prep · Ctrl+Enter = Run raw · Shift+Enter = new line`.
2. Type `fix the add function`, Enter: the hint shows `Prep: Haiku is reading proj ...`, then the Prep card: You typed, `Scouted: calc.py:2`, the editable prompt (`Goal: Fix add() in calc.py` ...), Route `sonnet` / `low` / `mechanical`, the reason, `Prep: $0.030 · 5 turns`.
3. Run: the detail opens on Chat: `start <7 chars> · 0 file(s) changed since`, then you / claude (echo with the STOP footer) / tool `Read calc.py` / result `success · $0.01 · 2 turns`; the row reads `proj · window · mechanical · sonnet/low`; the button row shows `Open in terminal` (do not click it here).
4. Back, type `SLOW raw task`, Ctrl+Enter: `▶ Running` with a Stop button; Stop: `○ Idle`, `stopped by you`, Chat ends with note `stopped` and `error_during_execution`.
5. Stop the server (Ctrl+C) and delete the folder: `rm -rf "$TEMP/cc-smoke"`.

- [x] **Step 6: Commit**

```bash
git add web/index.html web/app.js web/style.css
git commit -m "feat: window prompt box, Prep card, run actions and Chat tab"
```

**DONE WHEN**
- [x] The 5 browser checks pass; 60 tests OK; `git status --short` empty.

---

### Task 6b: Allow runs here

Added 2026-10-10 after Tasks 1-6: Fred asked not to edit `config.json` by hand for every project. The code is in the repo (commit `feat: Allow runs here button`), not repeated here.

- `paths.add_project(folder, project)`: adds one folder to `config.json` `"projects"`, keeps every other key, no duplicate (case and slash spelling ignored), writes through `config.json.tmp` + `os.replace`. A `config.json` that exists but cannot be parsed is never overwritten: ValueError -> 409.
- `POST /api/allow {"project_dir"}`: 400 if not a folder, 403 if no session in the event log has that `project_dir` (the page cannot add an arbitrary path), else adds it to `config.json` and to the live config; returns `{"projects": [...]}` spelled like `/api/config`.
- Window: a project that is picked but not listed shows `Runs are off here: a run uses this repo's hooks and settings without asking.` and a button `Allow runs in <name>`; after the click the option reads `<name> (runs)` and the prompt box enables. `All projects` keeps the Task 6 hint.
- Test: `test_allow_adds_a_folder_claude_code_ran_in` (61 tests). Browser check with the fake claude passed (button, option label, `config.json` kept `port`).
- Claude cannot fill the real `projects` list: the auto-mode classifier refuses it (it grants permissions). Fred uses the button or edits the file.

**DONE WHEN**
- [x] 61 tests OK; `git status --short` empty.

---

### Task 7: Fred: projects + live check

Claude cannot do this task: its auto-mode classifier refuses to let Claude start an autonomous `claude -p --permission-mode auto` run, and Open in terminal opens a console on Fred's screen.

- [x] **Step 1 (Fred): allow the folders runs may use.** In the window pick the project and click `Allow runs in <name>` (after Step 3's restart), or list them in `%USERPROFILE%\.claude\console\config.json` (keep the other keys), for example:

```json
  "projects": [
    "D:\\MY DOCS\\MY TOOLS\\CLAUDE CONSOLE",
    "D:\\MY DOCS\\MY TOOLS\\CONTENT MANAGER"
  ],
```

- [x] **Step 2 (Fred, optional): STOP rule for VS Code sessions.** Window runs already get the footer. For VS Code / terminal sessions to show `? STOP` too, add this line to `%USERPROFILE%\.claude\CLAUDE.md`:

```markdown
- When you must stop for a decision only Fred can make, end your final message with one line: `STOP: <question>`.
```

- [x] **Step 3: Restart the window** (close it, `run.bat`: the open window still runs the phase 1 Python code).

- [x] **Step 4: Live check** in the Claude Console repo (pick `CLAUDE CONSOLE (runs)`):
1. Prompt `list the Python files in console/ and count their lines; do not edit anything`, Enter. Expected: card in 10-30 s with route `lookup` / `haiku` / `low` (or close), cost about $0.03-0.04.
2. Run. Expected: a `window` row under Working, `▶ Running`, Steps fill from the hooks (Glob / Bash ...), Chat shows Claude's text, then `○ Idle` with model, ctx gauge and a cost; the row does not turn Done.
3. Prompt `write a 900-word story about a lighthouse keeper in story.txt`, Ctrl+Enter (Run raw), then Stop within 10 s. Expected: `stopped by you`, Chat note `stopped`. Delete `story.txt` if it was written.
4. Open in terminal on that session. Expected: a console opens with `claude --resume` on the same conversation; close it.
5. Crash recovery: Run raw `count to 200 slowly, one number per line`, then close the window AND end the service process (Task Manager: the `pythonw` running `-m console`) while it runs. Wait 1 min, `run.bat` again. Expected: the run finished on its own (stdin EOF) and shows `○ Idle`, or, if its process was killed with the service, `‖ Interrupted` with Resume; Resume continues it.
6. `~/.claude/console/hook-errors.log` and `window-errors.log` have no new lines.

**DONE WHEN**
- [x] Fred listed the projects; checks 1-6 pass (note anything that differed in History / Troubleshooting).

---

### Task 8: Close the phase

- [x] **Step 1:** In `../PLAN.md`, set sub-plan 2 to "done <date>" and add a dated History line (what was built, test count, anything that differed).
- [x] **Step 2:** In this file, tick the TODO list, add the History line, add any bug + fix to Troubleshooting.
- [x] **Step 3:** In `../CLAUDE.md`, add under Rules: `- Window runs: commands come only from console/claude_cli.py; runs only in config.json "projects"; Stop is the stream-json interrupt, never a kill of a run this service owns.`
- [x] **Step 4:** Commit: `git add PLAN.md CLAUDE.md plans/02-run.md && git commit -m "docs: phase 2 done"`.
- [x] **Added by Fred after the live check** (own commit, 63 tests): Open in terminal passes the run's `--model` / `--effort` (it opened on Fred's default Opus 5.5 / high); the hook drops injected blocks at the start of a prompt (`<browser_instruction>`, `<task-notification>`, `<agent-message>`; `<pasted_content>` stays) before clipping, and State never takes a title that still starts with a tag (older log lines).

**DONE WHEN**
- [x] `git status --short` is empty and `git log --oneline` shows one commit per task.

---

## DONE WHEN (whole plan)

- [x] `py -m unittest discover -s tests` -> 61 tests OK (60 + Task 6b).
- [x] A prompt typed in the window goes Prep card -> Run -> a live `window` session with Steps and Chat; Stop, Answer, Resume and Open in terminal work.
- [x] Closing the window never stops a run; a run cut by a crash shows Interrupted after restart.
- [x] Nothing outside `~/.claude/console/`, this repo and the run's own project folder was written by the code.

## History

- 2026-10-10 - Plan written. All code was run in a scratch clone first: 60 tests OK; real Prep through the service (22 s, $0.039, card with route mechanical / sonnet / low); window flows checked in a browser with the fake claude (Prep card, Run, Chat, Stop, STOP answer, Interrupted + Resume; no console errors). CLI facts from `claude --help` 2.1.288 and experiments (interrupt, EOF, `--session-id`, `--resume`, hook-free Prep).
- 2026-10-10 - Tasks 1-6 placed from this plan unchanged (60 tests OK, the 5 browser checks passed with the fake claude). Then, asked by Fred: Task 6b `Allow runs in <name>` button (Claude could not fill `projects` itself: its auto-mode classifier refused), default port 47770 (8770 clashed with Fred's dev apps), hint points to the project picker.
- 2026-10-10 - Task 7 live check passed: Prep 10-30 s, route lookup / haiku / low; the run showed Steps and Chat and ended Idle ($0.11, 56.8K); Stop gave `stopped by you` and no `story.txt`; Open in terminal resumed the same conversation; closing the window mid-run let the run finish on its own (stdin EOF), shown Idle after restart; no error-log lines. Differed: auto mode denied 2 tool calls of the lookup run, Haiku used Read instead and succeeded, yet the session showed Blocked; decision 14 changed (success + denials = Idle with a note). Task 8 additions: see Task 8. 63 tests OK.
- Open: `--model haiku` resolves to `claude-haiku-4-5-20251001` on CLI 2.1.288 (Prep and lookup runs); full model ids would need MODELS and the route table changed. Chat shows Claude's markdown as plain text (visual rework).

## Troubleshooting

- **Issue:** the prompt box stays disabled.
  **Cause:** the picked project is not in `config.json` `"projects"`, or `claude.exe` was not found (the hint says which).
  **Fix:** add the folder (Task 7 step 1) or set `"claude_exe"` to the full path of `claude.exe`; restart the window.
- **Issue:** Prep fails with `Prep returned no structured output`.
  **Cause:** the Haiku pass ran out of turns or `prep_prompt.md` lost its field list.
  **Fix:** restore `console/prep_prompt.md` from git; raise `prep_timeout_s` if it timed out.
- **Issue:** a window run shows `■ Blocked ... window runs cannot ask`.
  **Cause:** auto mode denied a tool and nobody can approve in `-p`.
  **Fix:** Open in terminal and approve there, or Answer with a different instruction.
- **Issue:** Stop says `killed` instead of stopping cleanly.
  **Cause:** the run was started by an earlier service (window restarted), so there was no stdin to send the interrupt to.
  **Fix:** none; the conversation is kept and can be resumed.
- **Issue:** a run that finished fine showed `■ Blocked`.
  **Cause:** auto mode denied a tool call (here `find -exec wc` and a PowerShell loop); Claude used another tool and succeeded, but every denial made the session Blocked.
  **Fix:** decision 14 changed: a `success` result with denials stays Idle with a `△ N denied` note (commit `fix: a window run that succeeded despite denials ...`).
- **Issue:** a session title reads `<browser_instruction>...` (or `<task-notification>`, `<agent-message>`).
  **Cause:** an extension or Claude Code put a block before Fred's text and the hook clipped the prompt to 120 characters inside it.
  **Fix:** the hook drops such leading blocks before clipping; State skips a title that still starts with a tag.
- **Issue:** `Allow runs in <name>` is not shown.
  **Cause:** the button appears only once a project is picked in the list at the top (`All projects` shows a hint instead).
  **Fix:** pick the project.
