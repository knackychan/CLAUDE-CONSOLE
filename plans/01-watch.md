# Plan 01: Watch (phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Related plans: [../PLAN.md](../PLAN.md) (master, design changes made while planning)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md) sections 4-8, 10-12; [../CLAUDE.md](../CLAUDE.md)

**Goal:** A window that shows every Claude Code session on this machine, live: state, route, subagents, context gauge, Needs you, Quiet / Stall?, 2 writers, and a Steps list per session. Read-only: it starts nothing.

**Architecture:** An async Claude Code hook (`cc_events.py`) appends one masked JSON line per event to `~/.claude/console/events-YYYY-MM-DD.jsonl`. A stdlib HTTP service (`console/`) reads new lines every second, folds them into a `State` (sessions -> agents -> steps), and pushes snapshots over SSE. A pywebview window (`web/`) renders them.

**Tech Stack:** Python 3.14 standard library, pywebview 6.2.1 (already installed), plain HTML/CSS/JS, `unittest`.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `main`). Every path below is relative to it. Run every command from the repo root in Git Bash unless the step says PowerShell.

---

## Code map

```text
cc_events.py          hook entry point; imports console.paths + console.redact
install_hooks.py      Fred runs it: merge/remove our hooks in ~/.claude/settings.json
run.bat               window without a console (pythonw)
console/
  __init__.py
  paths.py            data folder (CC_CONSOLE_HOME or ~/.claude/console), config.json + DEFAULTS
  redact.py           mask(), clip(), summarize(tool, input, cwd)
  events.py           LogReader (incremental, tolerant), prune()
  state.py            State.apply(rec), snapshot(now), steps(id); STATES table
  guard.py            host_ok(), post_ok()
  server.py           Hub (poll thread + Condition), Handler (GET routes, SSE), make_server()
  __main__.py         py -m console [--serve]
web/
  index.html  style.css  app.js
tests/
  test_redact.py  test_cc_events.py  test_events.py  test_state.py  test_server.py  test_install_hooks.py
```

Dependencies point one way: `cc_events -> paths, redact`; `server -> events, guard, paths, state`; `state -> redact`. Nothing imports `server` except `__main__`.

## Files to modify

All files are new except `.gitignore` (new too: the repo has only BRAINSTORM.md, CLAUDE.md, PLAN.md, design/).

## TODO

- [x] Task 0: repo scaffolding
- [x] Task 1: paths + redact
- [x] Task 2: the hook script
- [x] Task 3: log reader
- [x] Task 4: state builder
- [x] Task 5: guard + service
- [x] Task 6: window
- [x] Task 7: hook installer + live check (Fred runs the installer)
- [x] Task 8: plan history + push nothing (local repo only)

---

### Task 0: Repo scaffolding

**Files:**
- Create: `.gitignore`, `requirements.txt`, `run.bat`, `console/__init__.py`, `tests/` (folder)

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.superpowers/
```

- [ ] **Step 2: Create `requirements.txt`**

```text
pywebview==6.2.1
```

- [ ] **Step 3: Create `run.bat`** (CRLF line endings; Git warns about LF/CRLF, that is fine)

```bat
@echo off
rem Claude Console: the window, no console (errors go to %USERPROFILE%\.claude\console\window-errors.log)
cd /d "%~dp0"
start "" pythonw -m console
```

- [ ] **Step 4: Create `console/__init__.py`**

```python
"""Claude Console: watch every Claude Code session from a small always-on-top window."""
```

- [ ] **Step 5: Check pywebview is importable**

Run: `py -c "import webview; print('ok')"`
Expected: `ok`. If it fails: `py -m pip install -r requirements.txt`.

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements.txt run.bat console/__init__.py
git commit -m "chore: scaffold Claude Console"
```

**DONE WHEN**
- [ ] `git status --short` is empty after the commit.

---

### Task 1: paths + redact

`paths.py` decides where data lives (tests point it at a temp folder through `CC_CONSOLE_HOME`). `redact.py` guarantees nothing secret or long reaches the log.

**Files:**
- Create: `console/paths.py`, `console/redact.py`
- Test: `tests/test_redact.py`

- [ ] **Step 1: Write the failing test** `tests/test_redact.py`

```python
import unittest

from console import redact


class MaskTest(unittest.TestCase):
    def test_masks_token_shapes(self):
        text = "curl -H 'Authorization: Bearer abcdefgh12345' sk-ant-1234567890 ghp_abcdefghijkl"
        out = redact.mask(text)
        self.assertNotIn("abcdefgh12345", out)
        self.assertNotIn("sk-ant-1234567890", out)
        self.assertNotIn("ghp_abcdefghijkl", out)

    def test_masks_key_value_but_keeps_the_name(self):
        self.assertEqual(redact.mask("OPENAI_API_KEY=xyz123 run"), "OPENAI_API_KEY=*** run")
        self.assertEqual(redact.mask('password: "hunter2"'), "password:***")

    def test_leaves_normal_text(self):
        self.assertEqual(redact.mask("py -m unittest discover -s tests"), "py -m unittest discover -s tests")


class ClipTest(unittest.TestCase):
    def test_collapses_whitespace_and_cuts(self):
        self.assertEqual(redact.clip("a  b\n c", 10), "a b c")
        self.assertEqual(redact.clip("abcdefghij", 5), "abcd\u2026")


class SummarizeTest(unittest.TestCase):
    def test_path_tools_are_relative_to_cwd(self):
        out = redact.summarize("Edit", {"file_path": "D:\\repo\\src\\a.py"}, "d:\\repo")
        self.assertEqual(out, "src/a.py")

    def test_bash_is_masked_and_clipped(self):
        out = redact.summarize("Bash", {"command": "export TOKEN=abc && " + "x" * 200})
        self.assertTrue(out.startswith("export TOKEN=*** &&"))
        self.assertEqual(len(out), 80)

    def test_agent_shows_type_and_description(self):
        out = redact.summarize("Agent", {"subagent_type": "verifier", "description": "run checks"})
        self.assertEqual(out, "verifier: run checks")

    def test_unknown_tool_gives_empty(self):
        self.assertEqual(redact.summarize("TodoWrite", {"todos": []}), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_redact -v`
Expected: ERROR, `ImportError: cannot import name 'redact' from 'console'`.

- [ ] **Step 3: Create `console/paths.py`**

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

- [ ] **Step 4: Create `console/redact.py`**

```python
"""Masking and short summaries: nothing secret or long ever reaches the event log."""
import re
from pathlib import PurePath

_SECRETS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
]
_ASSIGN = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:api[_-]?key|token|secret|password)[A-Z0-9_]*)\s*([=:])\s*"
    r"(\"[^\"]*\"|'[^']*'|\S+)"
)
_PATH_TOOLS = {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit"}


def mask(text) -> str:
    """Replace token-shaped strings and key=value secrets with ***."""
    if not text:
        return ""
    text = str(text)
    for rx in _SECRETS:
        text = rx.sub("***", text)
    return _ASSIGN.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)


def clip(text, limit: int) -> str:
    """Collapse whitespace and cut to `limit` characters (ending with an ellipsis)."""
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _short_path(path: str, cwd: str) -> str:
    try:
        return str(PurePath(path).relative_to(PurePath(cwd))).replace("\\", "/")
    except (ValueError, TypeError):
        return str(path).replace("\\", "/")


def summarize(tool, tool_input, cwd: str = "") -> str:
    """One short, masked line saying what a tool call touches."""
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tool in _PATH_TOOLS:
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        return clip(_short_path(path, cwd), 80) if path else ""
    if tool in ("Bash", "PowerShell"):
        return clip(mask(ti.get("command", "")), 80)
    if tool in ("Grep", "Glob"):
        return clip(mask(ti.get("pattern", "")), 60)
    if tool in ("Agent", "Task"):
        kind = ti.get("subagent_type") or "agent"
        return clip(f"{kind}: {ti.get('description', '')}", 80)
    if tool == "Skill":
        return clip(ti.get("skill", ""), 60)
    if tool == "WebFetch":
        url = re.sub(r"^https?://", "", str(ti.get("url", "")))
        return clip(url.split("/")[0], 60)
    if tool == "WebSearch":
        return clip(mask(ti.get("query", "")), 60)
    return ""
```

- [ ] **Step 5: Run the test**

Run: `py -m unittest tests.test_redact -v`
Expected: `Ran 8 tests ... OK`.

- [ ] **Step 6: Commit**

```bash
git add console/paths.py console/redact.py tests/test_redact.py
git commit -m "feat: data paths, config defaults, masking and tool summaries"
```

**DONE WHEN**
- [ ] 8 tests pass; `mask("OPENAI_API_KEY=x")` keeps the name and hides the value.

---

### Task 2: The hook script

One process per hook event. Reads the hook JSON from stdin, writes one line. Facts it relies on (checked 2026-10-10 in code.claude.com/docs/en/hooks and on this machine's transcripts):
- every input has `session_id`, `cwd`, `transcript_path`, `hook_event_name`, `permission_mode`, `effort.level`; inside a subagent also `agent_id`, `agent_type`;
- `SubagentStop` has `agent_transcript_path`; `Stop` has `last_assistant_message`; `PermissionDenied` has `tool_name`, `tool_input`, `reason`; `StopFailure` has `error`, `error_details`; `PostCompact` has `trigger`; `SessionEnd` has `reason`;
- transcript lines of type `assistant` carry `message.model`, `message.usage` (`input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`), `isSidechain`, `entrypoint` (`claude-vscode`, `cli`, `claude-desktop` seen here).

**Files:**
- Create: `cc_events.py`
- Test: `tests/test_cc_events.py`

- [ ] **Step 1: Write the failing test** `tests/test_cc_events.py`

```python
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cc_events


def assistant_line(model="claude-sonnet-5-5", inp=10, read=1000, create=90, side=False, entry="claude-vscode"):
    return json.dumps({"type": "assistant", "isSidechain": side, "entrypoint": entry,
                       "message": {"model": model, "usage": {"input_tokens": inp,
                                   "cache_read_input_tokens": read,
                                   "cache_creation_input_tokens": create}}})


class TranscriptTailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "t.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_reads_last_main_assistant_line(self):
        self.path.write_text("\n".join([
            assistant_line(read=5),
            json.dumps({"type": "user"}),
            assistant_line(model="claude-haiku-5-5", read=9999, side=True),
            assistant_line(read=2000),
            "{broken",
        ]) + "\n", encoding="utf-8")
        out = cc_events.transcript_tail(self.path)
        self.assertEqual(out, {"model": "claude-sonnet-5-5", "context_tokens": 2100,
                               "entrypoint": "claude-vscode"})

    def test_sidechain_for_agent_transcripts(self):
        self.path.write_text(assistant_line(model="claude-haiku-5-5", side=True) + "\n", encoding="utf-8")
        self.assertEqual(cc_events.transcript_tail(self.path, sidechain=True)["model"], "claude-haiku-5-5")

    def test_missing_file_gives_empty(self):
        self.assertEqual(cc_events.transcript_tail(self.path), {})
        self.assertEqual(cc_events.transcript_tail(None), {})


class BuildRecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "myrepo"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "src").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def base(self, event, **extra):
        data = {"hook_event_name": event, "session_id": "s1", "cwd": str(self.repo / "src"),
                "permission_mode": "auto", "effort": {"level": "medium"}}
        data.update(extra)
        return data

    def test_project_is_git_root(self):
        rec = cc_events.build_record(self.base("SessionStart", source="startup"), now=100.0)
        self.assertEqual(rec["project"], "myrepo")
        self.assertEqual(rec["project_dir"], str(self.repo))
        self.assertEqual(rec["effort"], "medium")
        self.assertEqual(rec["ts"], 100.0)
        self.assertNotIn("agent_id", rec)

    def test_prompt_is_masked_and_clipped(self):
        rec = cc_events.build_record(self.base("UserPromptSubmit", prompt="token=abc " + "y" * 300))
        self.assertTrue(rec["prompt"].startswith("token=***"))
        self.assertEqual(len(rec["prompt"]), 120)

    def test_pre_tool_use_has_summary_not_input(self):
        rec = cc_events.build_record(self.base("PreToolUse", tool_name="Read", tool_use_id="t1",
                                               tool_input={"file_path": str(self.repo / "src" / "a.py")},
                                               agent_id="ag1", agent_type="Explore"))
        self.assertEqual((rec["tool"], rec["what"], rec["agent_id"]), ("Read", "a.py", "ag1"))
        self.assertNotIn("tool_input", rec)

    def test_stop_reads_route_and_stop_question(self):
        msg = "Done.\n`Route: mechanical, low effort, cavecrew-builder on sonnet`\nSTOP: how many retries?"
        rec = cc_events.build_record(self.base("Stop", last_assistant_message=msg, transcript_path=""))
        self.assertEqual(rec["route"], "mechanical, low effort, cavecrew-builder on sonnet")
        self.assertEqual(rec["stop_question"], "how many retries?")

    def test_permission_denied_keeps_reason(self):
        rec = cc_events.build_record(self.base("PermissionDenied", tool_name="Bash",
                                               tool_input={"command": "git push"}, reason="[Push]"))
        self.assertEqual((rec["what"], rec["reason"]), ("git push", "[Push]"))


class MainTest(unittest.TestCase):
    def test_main_appends_one_line_and_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": tmp}):
            payload = json.dumps({"hook_event_name": "SessionEnd", "session_id": "s9", "reason": "other"})
            with mock.patch("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode()))):
                self.assertEqual(cc_events.main(), 0)
            with mock.patch("sys.stdin", io.TextIOWrapper(io.BytesIO(b"not json"))):
                self.assertEqual(cc_events.main(), 0)
            files = list(Path(tmp).glob("events-*.jsonl"))
            self.assertEqual(len(files), 1)
            lines = files[0].read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["reason"], "other")
            self.assertTrue((Path(tmp) / "hook-errors.log").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_cc_events -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'cc_events'`.

- [ ] **Step 3: Create `cc_events.py`**

```python
"""Claude Code hook: append one JSON line per event to the Claude Console log.

Registered as an async command hook in ~/.claude/settings.json by install_hooks.py.
It never raises and always exits 0, so it cannot break or slow a session.
"""
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from console import paths, redact  # noqa: E402

TAIL_BYTES = 512 * 1024
_ROUTE = re.compile(r"^[\s`*>\-]*Route:\s*(.+?)[\s`*]*$", re.M)
_STOP = re.compile(r"^[\s`*>\-]*STOP:\s*(.+?)[\s`*]*$", re.M)


def project_root(cwd: str):
    """The nearest folder above `cwd` that holds .git, or None."""
    if not cwd:
        return None
    p = Path(cwd)
    for folder in [p, *p.parents][:30]:
        if (folder / ".git").exists():
            return folder
    return None


def last_match(rx, text: str) -> str:
    found = rx.findall(text or "")
    return found[-1].strip() if found else ""


def transcript_tail(path, sidechain: bool = False) -> dict:
    """Model, context tokens and entrypoint of the last assistant line of a transcript."""
    out = {}
    if not path:
        return out
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - TAIL_BYTES))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError, ValueError):
        return out
    for line in reversed(lines):
        if '"assistant"' not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("type") != "assistant":
            continue
        if bool(rec.get("isSidechain")) != sidechain:
            continue
        msg = rec.get("message") or {}
        usage = msg.get("usage") or {}
        if not usage or msg.get("model") in (None, "<synthetic>"):
            continue
        out["model"] = msg["model"]
        out["context_tokens"] = (int(usage.get("input_tokens") or 0)
                                 + int(usage.get("cache_read_input_tokens") or 0)
                                 + int(usage.get("cache_creation_input_tokens") or 0))
        if rec.get("entrypoint"):
            out["entrypoint"] = rec["entrypoint"]
        return out
    return out


def build_record(data: dict, now: float = None) -> dict:
    """Turn one hook input into one small, masked log record."""
    event = data.get("hook_event_name", "")
    cwd = data.get("cwd") or ""
    root = project_root(cwd)
    effort = data.get("effort")
    rec = {
        "ts": round(time.time() if now is None else now, 3),
        "event": event,
        "session_id": data.get("session_id", ""),
        "cwd": cwd,
        "project": root.name if root else (Path(cwd).name if cwd else ""),
        "project_dir": str(root) if root else cwd,
        "agent_id": data.get("agent_id"),
        "agent_type": data.get("agent_type"),
        "permission_mode": data.get("permission_mode"),
        "effort": effort.get("level") if isinstance(effort, dict) else effort,
    }
    tool = data.get("tool_name")
    if event == "UserPromptSubmit":
        rec["prompt"] = redact.clip(redact.mask(data.get("prompt", "")), 120)
    elif event in ("PreToolUse", "PermissionDenied"):
        rec["tool"] = tool
        rec["what"] = redact.summarize(tool, data.get("tool_input"), cwd)
        rec["tool_use_id"] = data.get("tool_use_id")
        if event == "PermissionDenied":
            rec["reason"] = redact.clip(data.get("reason", ""), 120)
    elif event == "SubagentStop":
        tail = transcript_tail(data.get("agent_transcript_path"), sidechain=True)
        rec["model"] = tail.get("model")
        rec["context_tokens"] = tail.get("context_tokens")
    elif event == "Stop":
        rec.update(transcript_tail(data.get("transcript_path")))
        message = data.get("last_assistant_message") or ""
        route = last_match(_ROUTE, message)
        question = last_match(_STOP, message)
        if route:
            rec["route"] = redact.clip(route, 80)
        if question:
            rec["stop_question"] = redact.clip(redact.mask(question), 200)
    elif event == "StopFailure":
        rec["error"] = data.get("error") or "unknown"
        rec["error_details"] = redact.clip(redact.mask(data.get("error_details", "")), 120)
    elif event == "SessionStart":
        rec["source"] = data.get("source")
        rec["model"] = data.get("model")
    elif event == "PostCompact":
        rec["trigger"] = data.get("trigger")
    elif event == "SessionEnd":
        rec["reason"] = data.get("reason")
    return {k: v for k, v in rec.items() if v not in (None, "")}


def append(rec: dict) -> None:
    """Add one line to today's events file (one write call per line)."""
    folder = paths.home()
    folder.mkdir(parents=True, exist_ok=True)
    day = time.strftime("%Y-%m-%d", time.localtime(rec["ts"]))
    line = json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(folder / f"events-{day}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(line)


def log_error() -> None:
    try:
        path = paths.home() / "hook-errors.log"
        if path.exists() and path.stat().st_size > 1_000_000:
            path.unlink()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
    except Exception:
        pass


def main() -> int:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        data = json.loads(raw) if raw.strip() else {}
        if isinstance(data, dict) and data.get("hook_event_name"):
            append(build_record(data))
    except Exception:
        log_error()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test**

Run: `py -m unittest tests.test_cc_events -v`
Expected: `Ran 9 tests ... OK`.

- [ ] **Step 5: Time it on a real transcript** (Git Bash; writes to a temp folder, not the real log)

```bash
T=$(cygpath -m "$(ls -t ~/.claude/projects/*/*.jsonl | head -1)")
H=$(cygpath -m "$(mktemp -d)")
py -c "import json,sys; print(json.dumps({'hook_event_name':'Stop','session_id':'t','cwd':'.','transcript_path':sys.argv[1],'last_assistant_message':'ok'}))" "$T" > "$H/stop.json"
time (CC_CONSOLE_HOME="$H" py cc_events.py < "$H/stop.json")
tail -1 "$H"/events-*.jsonl
```

Expected: `real` under 0.3 s; the last line is a `"event":"Stop"` record with `model` and `context_tokens`.

- [ ] **Step 6: Commit**

```bash
git add cc_events.py tests/test_cc_events.py
git commit -m "feat: async hook that logs one masked line per Claude Code event"
```

**DONE WHEN**
- [ ] 9 tests pass; the timing step prints a Stop record with `context_tokens`.
- [ ] Bad stdin still exits 0 (covered by `test_main_appends_one_line_and_never_raises`).

---

### Task 3: Log reader

**Files:**
- Create: `console/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing test** `tests/test_events.py`

```python
import json
import tempfile
import time
import unittest
from pathlib import Path

from console import events


class LogReaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.file = self.folder / "events-2026-10-10.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        with open(self.file, "a", encoding="utf-8") as fh:
            fh.write(text)

    def line(self, ts, event="Stop", sid="s1"):
        return json.dumps({"ts": ts, "event": event, "session_id": sid}) + "\n"

    def test_reads_only_new_lines(self):
        reader = events.LogReader(self.folder)
        self.write(self.line(1) + self.line(2))
        self.assertEqual([r["ts"] for r in reader.read_new()], [1, 2])
        self.assertEqual(reader.read_new(), [])
        self.write(self.line(3))
        self.assertEqual([r["ts"] for r in reader.read_new()], [3])

    def test_waits_for_a_half_written_line(self):
        reader = events.LogReader(self.folder)
        full = self.line(5)
        self.write(full[:10])
        self.assertEqual(reader.read_new(), [])
        self.write(full[10:])
        self.assertEqual([r["ts"] for r in reader.read_new()], [5])

    def test_skips_broken_and_foreign_lines(self):
        reader = events.LogReader(self.folder)
        self.write("{broken\n" + json.dumps({"ts": 1}) + "\n" + self.line(7))
        self.assertEqual([r["ts"] for r in reader.read_new()], [7])

    def test_merges_two_days_in_time_order(self):
        (self.folder / "events-2026-10-09.jsonl").write_text(self.line(4), encoding="utf-8")
        self.write(self.line(2))
        self.assertEqual([r["ts"] for r in events.LogReader(self.folder).read_new()], [2, 4])


class PruneTest(unittest.TestCase):
    def test_removes_files_older_than_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            now = time.mktime((2026, 10, 20, 12, 0, 0, 0, 0, -1))
            for day in ("2026-10-01", "2026-10-05", "2026-10-06", "2026-10-20"):
                (folder / f"events-{day}.jsonl").write_text("", encoding="utf-8")
            removed = events.prune(folder, 14, now=now)
            self.assertEqual(sorted(removed), ["events-2026-10-01.jsonl", "events-2026-10-05.jsonl"])
            self.assertEqual(len(list(folder.glob("*.jsonl"))), 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_events -v`
Expected: ERROR, `ImportError: cannot import name 'events' from 'console'`.

- [ ] **Step 3: Create `console/events.py`**

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

- [ ] **Step 4: Run the test**

Run: `py -m unittest tests.test_events -v`
Expected: `Ran 5 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add console/events.py tests/test_events.py
git commit -m "feat: incremental, crash-tolerant event log reader and pruning"
```

**DONE WHEN**
- [ ] 5 tests pass, including the half-written line and the broken line cases.

---

### Task 4: State builder

Rules (BRAINSTORM section 6, with the token gauge from PLAN.md):

| State | When |
|---|---|
| Done | SessionEnd seen |
| Failed | StopFailure since the last prompt |
| Blocked | PermissionDenied since the last prompt |
| Running / Quiet / Stall? | in a turn (prompt or tool seen, no Stop yet); last event under 180 s / 180-600 s / over 600 s |
| STOP | turn ended and the last message had a `STOP: <question>` line |
| Idle / Stale? | turn ended; last event under / over 1800 s |

Groups: **needs** = STOP, Blocked, Stall?, Failed, or a red gauge (unless Done / Stale?); **done** = Done, Stale?; **working** = the rest. Sessions with no event for 24 h are hidden. Rows keep start order (they do not jump on every event). Two writers = two or more open sessions with Edit / Write / MultiEdit / NotebookEdit in the same `project_dir` within 600 s.

**Files:**
- Create: `console/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing test** `tests/test_state.py`

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_state -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'console.state'`.

- [ ] **Step 3: Create `console/state.py`**

```python
"""Sessions -> agents -> steps, built from event records; states computed at snapshot time."""
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
    "done": ("✓", "Done", "success"),
}
NEEDS_YOU = {"stop", "blocked", "stall", "failed"}
DONE = {"done", "stale"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SOURCES = {"claude-vscode": "vscode", "cli": "terminal", "claude-desktop": "desktop"}
MAX_STEPS = 500
SHOW_FOR_S = 86400


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
                setattr(s, key, rec[key])
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
                s.title = redact.clip(rec.get("prompt", ""), 60)
            s.denied = s.failed = None
            s.stop_question = ""
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
            if rec.get("entrypoint"):
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
            s.ended, s.in_turn = True, False

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

    def gauge(self, s: Session):
        """(fill, tone): fill is ctx_tokens / gauge_red_tokens, capped at 1.0.

        Token thresholds, not % of the window: the 5.x models have a 1M window, and a chat
        degrades long before it is full (Context Playbook)."""
        if s.ctx_tokens is None:
            return None, None
        red, yellow = self.cfg["gauge_red_tokens"], self.cfg["gauge_yellow_tokens"]
        fill = min(s.ctx_tokens / red, 1.0)
        if s.ctx_tokens >= red:
            return fill, "red"
        if s.ctx_tokens >= yellow:
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
            pct, tone = self.gauge(s)
            if state in NEEDS_YOU or (tone == "red" and state not in DONE):
                group = "needs"
            elif state in DONE:
                group = "done"
            else:
                group = "working"
            symbol, text, state_tone = STATES[state]
            rows.append({
                "id": s.id, "project": s.project, "project_dir": s.project_dir,
                "title": s.title or "(no prompt yet)", "source": s.source or "?",
                "model": s.model, "effort": s.effort, "route": s.route or "unrouted",
                "state": state, "symbol": symbol, "text": text, "tone": state_tone,
                "group": group, "doing": s.doing, "prompts": s.prompts,
                "ctx_tokens": s.ctx_tokens, "ctx_fill": None if pct is None else round(pct, 3),
                "ctx_tone": tone, "compactions": s.compactions,
                "stop_question": s.stop_question, "denied": s.denied, "failed": s.failed,
                "two_writers": s.id in writer_ids,
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
        return {"id": a.id, "type": a.type or "agent", "model": a.model, "effort": a.effort,
                "tokens": a.tokens, "steps": a.steps, "doing": a.doing,
                "symbol": symbol, "text": text, "tone": tone}

    def steps(self, session_id: str, limit: int = 200) -> list:
        s = self.sessions.get(session_id)
        if not s:
            return []
        types = {a.id: a.type for a in s.agents.values()}
        return [dict(step, agent_type=types.get(step["agent"], "") if step["agent"] else "main")
                for step in s.steps[-limit:]]
```

- [ ] **Step 4: Run the test**

Run: `py -m unittest tests.test_state -v`
Expected: `Ran 7 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add console/state.py tests/test_state.py
git commit -m "feat: session/agent/step state with Needs you, gauge and two-writers"
```

**DONE WHEN**
- [ ] 7 tests pass.

---

### Task 5: Guard + service

**Files:**
- Create: `console/guard.py`, `console/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing test** `tests/test_server.py`

```python
import http.client
import json
import tempfile
import threading
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_server -v`
Expected: ERROR, `ImportError: cannot import name 'guard' from 'console'`.

- [ ] **Step 3: Create `console/guard.py`**

```python
"""Localhost guard: the service can later start processes, so only this machine's window may talk to it."""

POST_HEADER = "X-CC"


def host_ok(host_header, port: int) -> bool:
    """True when the Host header names this service on loopback."""
    return host_header in (f"127.0.0.1:{port}", f"localhost:{port}")


def post_ok(headers) -> bool:
    """POSTs must carry X-CC: 1 (a plain HTML form or image tag cannot add it)."""
    return headers.get(POST_HEADER) == "1"
```

- [ ] **Step 4: Create `console/server.py`**

```python
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
```

- [ ] **Step 5: Create the three web files now** (the static test serves `web/index.html`; Task 6 checks them in the window)

`web/index.html`:

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
  <main id="detail" hidden></main>
  <footer id="strip" class="strip m"></footer>
  <script src="/app.js"></script>
</body>
</html>
```

`web/style.css`:

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
```

`web/app.js`:

```javascript
// Claude Console window: renders /api/stream snapshots. Read-only in phase 1.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const GROUPS = [["needs", "Needs you"], ["working", "Working"], ["done", "Done today"]];

let snap = null;
let openId = null;
let live = false;

function kTokens(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "K" : String(n || 0); }
function clock(ts) { return new Date(ts * 1000).toTimeString().slice(0, 8); }
function routeText(s) {
  const run = [s.model, s.effort].filter(Boolean).join("/");
  if (s.route === "unrouted") return run ? "unrouted · " + run : "unrouted";
  return run ? s.route + " · " + run : s.route;
}

function gauge(s) {
  if (s.ctx_fill == null) return '<span class="mut">ctx ?</span>';
  const hint = s.ctx_tone === "red" ? " handoff" : s.ctx_tone === "yellow" ? " soon" : "";
  return `<span class="${s.ctx_tone}">ctx <span class="bar"><i style="width:${Math.round(s.ctx_fill * 100)}%"></i></span> ${kTokens(s.ctx_tokens)}${hint}</span>`;
}

function sessionRows(s) {
  let html = `<div class="row m session" data-id="${esc(s.id)}">
    <span class="${s.tone}">${s.symbol} ${esc(s.text)}</span>
    <span class="title">${esc(s.title)}</span>
    ${s.two_writers ? '<span class="badge warning">2 writers</span>' : ""}
    ${gauge(s)}</div>`;
  html += `<div class="row m ind mut">${esc(s.project)} &middot; ${esc(s.source)} &middot; ${esc(routeText(s))}${s.doing ? " &middot; " + esc(s.doing) : ""}</div>`;
  if (s.stop_question) html += `<div class="note ask"><span class="warning">? STOP</span> ${esc(s.stop_question)}</div>`;
  if (s.denied) html += `<div class="note m"><span class="danger">&#9632; denied</span> ${esc(s.denied.tool)} ${esc(s.denied.what)} <span class="mut">${esc(s.denied.reason)}</span></div>`;
  if (s.failed) html += `<div class="note m"><span class="danger">&times; ${esc(s.failed.error)}</span> <span class="mut">${esc(s.failed.details)}</span></div>`;
  for (const a of s.agents) {
    html += `<div class="row m ind"><span class="${a.tone}">${a.symbol}</span>
      <span class="title">${esc(a.type)}${a.model ? " &middot; " + esc(a.model) : ""}${a.effort ? "/" + esc(a.effort) : ""}
      &middot; ${a.doing ? esc(a.doing) : a.steps + (a.steps === 1 ? " step" : " steps")}${a.tokens ? " &middot; " + kTokens(a.tokens) : ""}</span></div>`;
  }
  return html;
}

function visible(s) { return !$("project").value || s.project_dir === $("project").value; }

function renderHome() {
  const rows = snap.sessions.filter(visible);
  let html = "";
  for (const [key, label] of GROUPS) {
    const list = rows.filter((s) => s.group === key);
    if (!list.length) continue;
    html += `<div class="sec">${label}</div>` + list.map(sessionRows).join("");
  }
  $("home").innerHTML = html || '<div class="empty">No Claude Code session in the last 24 h. Start one in VS Code or a terminal.</div>';
}

async function renderDetail() {
  const s = snap.sessions.find((x) => x.id === openId);
  if (!s) { closeDetail(); return; }
  const steps = await (await fetch("/api/steps?session=" + encodeURIComponent(openId))).json();
  let html = sessionRows(s);
  html += `<div class="row m mut">${s.prompts} prompt(s) &middot; ${s.compactions} compaction(s) &middot; route: ${esc(s.route)}</div>`;
  html += '<div class="sec">Steps</div>';
  html += steps.slice().reverse().map((st) => `<div class="row m${st.denied ? " danger" : ""}">
      <span class="mut">${clock(st.ts)}</span><span>${esc(st.agent_type)}</span>
      <span class="title">${esc(st.tool)} ${esc(st.what)}</span></div>`).join("")
      || '<div class="empty">No tool calls yet.</div>';
  $("detail").innerHTML = html;
}

function renderStrip() {
  const c = snap.counts;
  let html = `<span>${live ? "service &#9679; ok" : '<span class="danger">service &#9675; offline</span>'}</span>
    <span>${c.needs} need you &middot; ${c.working} working &middot; ${c.done} done</span>`;
  for (const w of snap.writers) {
    html += `<span class="warning">2 writers: ${esc(w.project_dir.split(/[\\/]/).pop())}</span>`;
  }
  $("strip").innerHTML = html;
  $("counts").innerHTML = c.needs ? `<span class="warning">! ${c.needs}</span>` : "";
}

function renderProjects() {
  const select = $("project");
  const known = new Set([...select.options].map((o) => o.value));
  for (const s of snap.sessions) {
    if (s.project_dir && !known.has(s.project_dir)) {
      select.add(new Option(s.project, s.project_dir));
      known.add(s.project_dir);
    }
  }
}

function render() {
  if (!snap) return;
  renderProjects();
  renderStrip();
  if (openId) renderDetail(); else renderHome();
}

function openDetail(id) { openId = id; $("home").hidden = true; $("detail").hidden = false; $("back").hidden = false; render(); }
function closeDetail() { openId = null; $("home").hidden = false; $("detail").hidden = true; $("back").hidden = true; render(); }

$("home").addEventListener("click", (e) => {
  const row = e.target.closest(".session");
  if (row) openDetail(row.dataset.id);
});
$("back").addEventListener("click", closeDetail);
$("project").addEventListener("change", render);

function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => { live = true; snap = JSON.parse(e.data); render(); };
  es.onerror = () => { live = false; if (snap) renderStrip(); };
}
connect();
```

- [ ] **Step 6: Run the test**

Run: `py -m unittest tests.test_server -v`
Expected: `Ran 6 tests ... OK`.

- [ ] **Step 7: Commit**

```bash
git add console/guard.py console/server.py web/ tests/test_server.py
git commit -m "feat: localhost service with state, steps and SSE stream"
```

**DONE WHEN**
- [ ] 6 tests pass; a foreign Host header gets 403; a POST without `X-CC: 1` gets 403.

---

### Task 6: Window

**Files:**
- Create: `console/__main__.py`

- [ ] **Step 1: Create `console/__main__.py`**

```python
"""py -m console          open the window (service runs inside it)
py -m console --serve  service only; open http://127.0.0.1:8770/ in a browser"""
import argparse
import json
import sys
import threading
import urllib.request

from . import events, paths, server


def already_running(port: int) -> bool:
    """True when our own service answers on the port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as resp:
            return json.loads(resp.read()).get("app") == server.APP_ID
    except (OSError, ValueError):
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="console")
    parser.add_argument("--serve", action="store_true", help="service only, no window")
    args = parser.parse_args(argv)

    if sys.stderr is None:  # started with pythonw (run.bat): keep errors readable
        paths.home().mkdir(parents=True, exist_ok=True)
        sys.stderr = open(paths.home() / "window-errors.log", "a", encoding="utf-8")
    cfg = paths.ensure_config()
    events.prune(paths.home(), cfg["retention_days"])
    port = cfg["port"]
    url = f"http://127.0.0.1:{port}/"

    httpd = None
    try:
        httpd, hub = server.make_server(cfg)
    except OSError:
        if not already_running(port):
            print(f"port {port} is used by another program; set another \"port\" in "
                  f"{paths.home() / 'config.json'}", file=sys.stderr)
            return 1
    if httpd:
        hub.start()
        threading.Thread(target=httpd.serve_forever, name="cc-http", daemon=True).start()

    if args.serve:
        if not httpd:
            print(f"already running: {url}")
            return 0
        print(url)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            return 0

    import webview  # imported late: --serve works without pywebview
    webview.create_window("Claude Console", url, width=420, height=640,
                          min_size=(360, 400), on_top=True)
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the full suite**

Run: `py -m unittest discover -s tests`
Expected: `Ran 35 tests ... OK` (the installer tests come in Task 7).

- [ ] **Step 3: Service smoke test with fake data** (Git Bash; temp data folder and port 8779 so the real log is untouched)

```bash
H=$(cygpath -m "$(mktemp -d)")
echo '{"port": 8779}' > "$H/config.json"
echo '{"ts": 9999999999, "event": "UserPromptSubmit", "session_id": "demo", "project": "demo", "project_dir": "D:/demo", "prompt": "demo task"}' > "$H/events-2026-10-10.jsonl"
CC_CONSOLE_HOME="$H" py -m console --serve &
sleep 2
curl -s http://127.0.0.1:8779/api/state | head -c 300; echo
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: evil:8779" http://127.0.0.1:8779/api/state
kill %1
```

Expected: JSON containing `"title": "demo task"`, then `403`.

- [ ] **Step 4: Window check** (PowerShell, real data folder; with no hooks yet the window says there is no session)

Run: `py -m console`
Expected: a 420 x 640 window titled "Claude Console" stays on top of other windows; header with "All projects"; body "No Claude Code session in the last 24 h..."; footer "service ● ok". Close it with the window's X.

- [ ] **Step 5: Commit**

```bash
git add console/__main__.py
git commit -m "feat: py -m console opens the always-on-top window"
```

**DONE WHEN**
- [ ] 35 tests pass; smoke test prints the demo session and 403; the window opens on top and closes cleanly.

---

### Task 7: Hook installer + live check

Claude cannot edit its own settings (the permission classifier blocks it), so **Fred runs step 4**.

Hook config facts (code.claude.com/docs/en/hooks, 2026-10-10): exec form = `command` (a real `.exe`) + `args`; `async: true` runs in the background; omitting `matcher` matches every occurrence.

**Files:**
- Create: `install_hooks.py`
- Test: `tests/test_install_hooks.py`

- [ ] **Step 1: Write the failing test** `tests/test_install_hooks.py`

```python
import unittest

import install_hooks


class InstallHooksTest(unittest.TestCase):
    def test_merge_adds_every_event_once_and_keeps_other_hooks(self):
        other = {"matcher": "Bash", "hooks": [{"type": "command", "command": "x.sh"}]}
        settings = {"model": "opus", "hooks": {"PreToolUse": [other]}}
        install_hooks.merge(settings, python="py.exe")
        install_hooks.merge(settings, python="py.exe")  # second run changes nothing
        self.assertEqual(settings["model"], "opus")
        for event in install_hooks.EVENTS:
            ours = [g for g in settings["hooks"][event] if install_hooks._is_ours(g)]
            self.assertEqual(len(ours), 1, event)
            self.assertEqual(ours[0]["hooks"][0],
                             {"type": "command", "command": "py.exe", "args": [install_hooks.SCRIPT], "async": True})
        self.assertIn(other, settings["hooks"]["PreToolUse"])

    def test_remove_takes_only_ours(self):
        other = {"hooks": [{"type": "command", "command": "x.sh"}]}
        settings = install_hooks.merge({"hooks": {"Stop": [other]}}, python="py.exe")
        install_hooks.remove(settings)
        self.assertEqual(settings, {"hooks": {"Stop": [other]}})
        self.assertEqual(install_hooks.remove(install_hooks.merge({}, python="p")), {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_install_hooks -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'install_hooks'`.

- [ ] **Step 3: Create `install_hooks.py`**

```python
"""Add (or remove) the Claude Console hooks in ~/.claude/settings.json.

Fred runs this himself (Claude cannot edit its own settings):
    py install_hooks.py            show what would be added
    py install_hooks.py --write    back up settings.json, then add the hooks
    py install_hooks.py --remove   back up settings.json, then remove them
    --python <exe>                 the interpreter the hook runs with (default: this one)
Running --write twice changes nothing the second time.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "SubagentStart", "SubagentStop",
          "PermissionDenied", "Stop", "StopFailure", "PostCompact", "SessionEnd"]
SCRIPT = str(Path(__file__).resolve().parent / "cc_events.py")


def our_handler(python: str = None) -> dict:
    return {"type": "command", "command": python or sys.executable, "args": [SCRIPT], "async": True}


def _is_ours(group: dict) -> bool:
    return any(SCRIPT in (h.get("args") or []) for h in group.get("hooks", []))


def merge(settings: dict, python: str = None) -> dict:
    hooks = settings.setdefault("hooks", {})
    for event in EVENTS:
        groups = [g for g in hooks.get(event, []) if not _is_ours(g)]
        groups.append({"hooks": [our_handler(python)]})
        hooks[event] = groups
    return settings


def remove(settings: dict) -> dict:
    hooks = settings.get("hooks", {})
    for event in list(hooks):
        groups = [g for g in hooks[event] if not _is_ours(g)]
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    return settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--settings", default=str(Path.home() / ".claude" / "settings.json"))
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    path = Path(args.settings)
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    result = remove(settings) if args.remove else merge(settings, python=args.python)
    if not (args.write or args.remove):
        print(json.dumps({"hooks": {e: result["hooks"][e] for e in EVENTS}}, indent=2))
        print("\n(dry run: nothing written; use --write)")
        return 0
    if path.exists():
        backup = path.with_name(f"settings.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, backup)
        print(f"backup: {backup}")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{'removed from' if args.remove else 'written to'} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Then: `py -m unittest discover -s tests` -> `Ran 37 tests ... OK`. Commit:

```bash
git add install_hooks.py tests/test_install_hooks.py
git commit -m "feat: installer that merges or removes the Claude Console hooks"
```

- [ ] **Step 4 (Fred, in his own terminal): install the hooks**

```bat
cd /d "D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE"
py install_hooks.py
py install_hooks.py --write
```

The first command only prints the hooks; the second backs up `~/.claude/settings.json` to `settings.json.bak-<date>` and adds them. Open sessions pick the hooks up too (seen 2026-10-10); a session whose prompt was sent before the install shows "(prompt not seen) <id>" until its next prompt.

- [ ] **Step 5: Live check** (any project)

1. `run.bat` (the window opens).
2. In a new Claude Code chat, send: `List the files in this folder, then use an Explore agent to find the README`.
3. Watch the window.

Expected:
- the session appears under **Working** with its title, `vscode`, and `▶ Running` while it works;
- an `Explore` row appears under it while the agent runs, then `✓`;
- after the answer: `○ Idle`, model and effort filled, a `ctx` gauge with a token count;
- clicking the session shows the Steps list (Bash / Glob / Read ...), newest first; `←` goes back;
- `~/.claude/console/hook-errors.log` does not exist (or has no new lines).

**DONE WHEN**
- [ ] 37 tests pass.
- [ ] Fred ran `--write`; the live check shows the session, the agent row, the gauge and the Steps.
- [ ] No new lines in `hook-errors.log`.

---

### Task 8: Close the phase

- [ ] **Step 1:** In `../PLAN.md`, set sub-plan 1 to "done <date>" and add a dated History line (what was built, test count, anything that differed from this plan).
- [ ] **Step 2:** In this file, tick the TODO list and add the History line below; add any bug + fix to Troubleshooting.
- [ ] **Step 3:** Commit: `git add PLAN.md plans/01-watch.md && git commit -m "docs: phase 1 done"`.

**DONE WHEN**
- [ ] `git status --short` is empty and `git log --oneline` shows one commit per task.

---

## DONE WHEN (whole plan)

- [ ] `py -m unittest discover -s tests` -> 37 tests OK.
- [ ] A real Claude Code session shows up live with state, agents, gauge and Steps.
- [ ] Closing the window does not affect any Claude Code session (hooks keep logging; reopening shows the same sessions).
- [ ] Nothing outside `~/.claude/console/` and this repo was written by the code (settings.json only by Fred's `--write`).

## History

- 2026-10-10 - Tasks 6-8 done. Window check and live check passed (session, Explore agent row ending in `✓ Done`, red gauge, Steps; no hook-errors.log). Change after the live check: agent rows now show `✓ Done` text and a context bar from their tokens (Fred's request).
- 2026-10-10 - Tasks 0-7 step 3 executed (files copied from the verified scratch copy, one commit per task, 37 tests OK, installer dry run points at this repo's cc_events.py). Pending: Task 6 step 4 window check, Task 7 steps 4-5 (Fred installs the hooks, live check), Task 8.
- 2026-10-10 - Plan written. Every code block was run in a scratch copy first: 37 tests OK, hook about 75 ms on a real transcript, service smoke-tested.

## Troubleshooting

- **Issue:** a session title starts with `<pasted_content id="...">`.
  **Cause:** the prompt was pasted; Claude Code wraps pasted text in that tag and the hook logs the first 120 characters.
  **Fix:** plan 02 Task 1 strips the tag from titles.
- **Issue:** a change to `console/*.py` does not show in the open window.
  **Cause:** the window process loaded the old code (static files are read per request, Python is not).
  **Fix:** close the window and start `run.bat` again.
- **Issue:** a console window flashes on every hook event.
  **Cause:** Claude Code starts `python.exe` for the hook.
  **Fix:** `py install_hooks.py --write --python "C:\Users\DEROK137\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"` (replaces our entries; `pythonw.exe` has no console and still reads the piped stdin). Check one event still lands in the log afterwards.
- **Issue:** a session shows "(prompt not seen)" and source "?".
  **Cause:** its prompt was sent before the hooks were installed; source is only known after its first Stop.
  **Fix:** none needed; the next prompt and Stop fill both.
- **Issue:** the window shows nothing although hooks are installed.
  **Cause:** hooks load at session start.
  **Fix:** start a new chat or restart VS Code; then check `~/.claude/console/events-<today>.jsonl` grows.
- **Issue:** `port 8770 is used by another program`.
  **Fix:** set `"port"` in `~/.claude/console/config.json` to a free port.
