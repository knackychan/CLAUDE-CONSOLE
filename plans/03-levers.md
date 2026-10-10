# Plan 03: Levers (phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Related plans: [../PLAN.md](../PLAN.md) (master), [01-watch.md](01-watch.md) (phase 1, done), [02-run.md](02-run.md) (phase 2, done)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md) sections 3 (D6, D7), 5, 6, 7.3, 12 (phase 3); [../CLAUDE.md](../CLAUDE.md)

**Goal:** From a session's detail view Fred can Continue it (any session, not only window runs), Verify it (a `VERDICT: PASS|FAIL` line), Escalate it once after a FAIL (one step up, and the miss is logged for Prep), and Handoff it (`/session-handoff`, then Done). The window shows verdicts, a follow-up hint that says when to hand off, and a Timeline tab (bars over time per agent).

**Architecture:** The hook parses `VERDICT:` lines from `last_assistant_message` on Stop and SubagentStop. `console/levers.py` holds the texts the levers send, the escalation step and the `routing-misses.md` file. `server.Hub.levers()` is the one place that decides when a lever is allowed; `GET /api/levers` shows its answer and the four POST routes call it again. Every lever is a run started by the existing `RunManager`: a new turn of a window run (`--resume`), or a window copy of a VS Code / terminal chat (`--resume <id> --fork-session --session-id <new>`), so the original chat is never written to. `run_started` gains `kind`, `forked_from` and `escalated`; `State` builds verdicts, handoffs, forks, follow-ups and Timeline turns from the same event log.

**Tech Stack:** unchanged: Python 3.14 standard library, pywebview 6.2.1, plain HTML/CSS/JS, `unittest`. Claude Code CLI 2.1.296.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `master`). Every path below is relative to it. Run commands from the repo root in Git Bash.

---

## Fixed decisions (verified 2026-10-10 on this machine, Claude Code 2.1.296, `claude --help`, docs + experiments)

1. **`haiku` stays an alias (no full model id).** Fred asked whether to switch to `claude-haiku-5-5`. Verified on 2.1.296: `claude -p --model haiku` reports `modelUsage` `claude-haiku-5-5`, the same as `--model claude-haiku-5-5`. The Haiku 4.5 seen in phase 2 came from CLI 2.1.288; code.claude.com/docs/en/model-config: "Use v2.1.293 or later with Haiku 5.5", and aliases "update over time". A pinned id would need a code change at every new model; the alias does not. `claude_cli.MODELS`, the Prep schema and the route table stay `haiku / sonnet / opus / fable`. Task 7 checks the model a Haiku run reports.
2. **VS Code / terminal sessions are forked, never resumed in place** (Fred). `claude -p --resume <id> --fork-session --session-id <new> --name <title>` (with the phase 2 run flags) starts `<new>` with the old chat's context; verified: the new id is honoured, the context is kept (a word given in turn 1 was recalled in the fork), `--name`, `--permission-mode auto --permission-prompts none` and stream-json input work together. The VS Code chat is not touched. The copy is a normal window run: title `↳ <original title>`, the original's follow-up count and context tokens, a link back (`window copy of <id>`); the original row says `continued in a window copy`. Window runs keep resuming their own id (phase 2).
3. **A fork starts in the folder the chat started in** (`Session.first_cwd`, the first `cwd` the log saw): Claude Code files a chat under its start folder, so `--resume` must run there.
4. **When a lever is allowed** (`Hub.levers`): the session's `project_dir` is in `config.json` `"projects"`, `claude.exe` is found, the session is not Running / Quiet / Stall? and has no live run, and its folder exists. Escalate also needs a FAIL verdict, no earlier escalation and a step above the route; Handoff also needs the skill (decision 9). Each "no" carries the reason the window shows (`Levers off: ...`).
5. **Continue replaces Answer.** `POST /api/continue {"session", "text"}` serves Continue, STOP answers and Resume (`POST /api/answer` is removed). Verify, Handoff and Escalate are `POST /api/verify|handoff|escalate {"session"}`; the service builds their text. All four return `{"session": <id>}` (a fork's new id).
6. **Verify** (Fred): a button. It sends `levers.VERIFY_TEXT`: run the project's `verifier` agent if it has one, else its tests or checks once, edit nothing, end with `VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`. Cost only when clicked.
7. **Verdict** = the last `VERDICT: PASS|FAIL` line of `last_assistant_message` on Stop (main thread) and SubagentStop (the verifier agent). Both fields are in code.claude.com/docs/en/hooks ("Stop hooks receive ... `last_assistant_message`"; SubagentStop "receive ... `agent_transcript_path`, and `last_assistant_message`"). Detail: the rest of that line, else the first `failing:` line (the verifier's report format), masked, 160 characters. The session keeps the newest verdict; agent rows and Timeline lanes show their own. The hook writes it, so the service adds no `verdict` line (BRAINSTORM 5 listed one).
8. **Escalate** (Fred: effort to high, then model): only after FAIL, once per task (a fork and its original share the flag). Step: effort +1 while below `high`; at `high` or above, the next model (haiku -> sonnet -> opus -> fable) at the same effort; on fable, effort +1; fable/max has none. Examples: haiku/low -> haiku/medium, sonnet/medium -> sonnet/high, sonnet/high -> opus/high, opus/xhigh -> fable/xhigh, fable/high -> fable/xhigh. The run (resume or fork) uses the new route and `levers.escalate_text(detail, model, effort)`. `run_started` carries `escalated: "<from> -> <to>"`; there is no separate `escalated` event line.
9. **Handoff** (Fred: skill where present): sends `/session-handoff`. Verified: a `/skill` sent as the stream-json user message expands in `-p`, also on a fork. No STOP footer is added to a prompt that starts with `/`. Allowed only when `SKILL.md` exists in `<project_dir>/.claude/skills/session-handoff/` or `~/.claude/skills/session-handoff/` (today: CONTENT MANAGER only; phase 4 moves the skill to `~/.claude`). A Handoff run that ends `success` makes the session Done, and its original too when it is a fork; a failed one changes nothing. A new prompt in a handed-off chat reopens it.
10. **routing-misses.md lives in `~/.claude/console/`** (CLAUDE.md: never write anywhere else). One line per Escalate: `- <date> - <project> - <route type or unrouted>: <from> failed (<why>); next time start at <to>.` Prep puts the project's last 20 lines into its prompt (`$misses` in `console/prep_prompt.md`). The `route-model` skill still reads the file in its auto-memory folder; phase 4 (moving the skill) can point it here.
11. **Follow-up hint:** `follow_ups = prompts - 1`. `handoff_hint` when the session is not Done / Stale? and the gauge is red or `follow_ups >= handoff_after_followups` (new config key, default 2). The row gets a `handoff?` badge (a red gauge already reads `handoff`), the detail a note `↻ hand off <why>: one task = one chat`, and the Handoff button is highlighted.
12. **Timeline** (D7 C): the `main` lane is one bar per turn (UserPromptSubmit or `run_started` to Stop, StopFailure, SessionEnd or `run_ended`; an open turn runs to now); then one bar per agent (first event to SubagentStop, or to now while the turn runs). One time axis per session (start, length, end), bars placed in %. No Prep lane (Prep's duration is not logged). Every session gets the Timeline tab; Chat stays for window runs.
13. **A FAIL verdict is not a Needs-you state** (BRAINSTORM 6 unchanged); the row shows `× FAIL <detail>` under it.
14. **Not verified by Claude:** a live `--permission-mode auto` run (Claude's auto-mode classifier refuses to let Claude start one) and a fork of a real VS Code chat. Both are in Task 7.

## Code map

```text
cc_events.py        + verdict(): VERDICT lines from Stop / SubagentStop
console/
  levers.py         NEW  VERIFY_TEXT, HANDOFF_TEXT, escalate_step, escalate_text, handoff_ready, miss_line, add_miss, read_misses
  claude_cli.py     + run_command(fork=), model_alias
  prep.py           + build_prompt(raw, misses); run_prep reads the project's misses
  prep_prompt.md    + $misses block
  runs.py           + start(fork=, kind=, extra=); no STOP footer after a /skill
  state.py          + verdicts, kind, handoff / handed_off, forks, first_cwd, turns, follow-ups, timeline()
  paths.py          + handoff_after_followups
  server.py         + Hub.levers / route_of / timeline, GET /api/levers /api/timeline, POST /api/continue /verify /handoff /escalate (- /api/answer)
web/  app.js  style.css   lever buttons, verdict badges, follow-up hint, Timeline tab
tests/
  test_levers.py    NEW
  test_cc_events.py  test_state.py  test_claude_cli.py  test_runs.py  test_server.py   extended
```

Dependencies point one way: `levers -> claude_cli, redact`; `prep -> claude_cli, levers, redact`; `server -> claude_cli, events, guard, levers, paths, prep, runs, state`.

## Files to modify

`cc_events.py`, `console/claude_cli.py`, `console/prep.py`, `console/prep_prompt.md`, `console/runs.py`, `console/state.py`, `console/paths.py`, `console/server.py`, `web/app.js`, `web/style.css`, the five test files above, `PLAN.md`, `CLAUDE.md`, this file. New: `console/levers.py`, `tests/test_levers.py`. Unchanged: `web/index.html`, `tests/fake_claude.py`, `console/__main__.py`, `install_hooks.py`.

## TODO

- [x] Task 1: hook verdicts
- [x] Task 2: state (verdict, levers, forks, follow-ups, Timeline)
- [x] Task 3: claude_cli fork + levers + Prep misses
- [x] Task 4: runs (fork, kind)
- [x] Task 5: service routes
- [x] Task 6: window
- [x] Task 7: Fred: live check
- [x] Task 8: close the phase

---

### Task 1: Hook verdicts

The hook runs inside every Claude Code session as soon as the file is saved: keep it raising nothing (`verdict()` takes `None`).

**Files:**
- Modify: `cc_events.py` (full file below)
- Test: `tests/test_cc_events.py` (full file below; 1 new test)

- [ ] **Step 1: Replace `tests/test_cc_events.py`** with:

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

    def test_injected_blocks_are_not_the_prompt(self):
        prompt = ('<browser_instruction># Claude in Chrome\n' + "x" * 500 + '</browser_instruction>\n'
                  '<pasted_content id="1">Project: D:/x</pasted_content>')
        rec = cc_events.build_record(self.base("UserPromptSubmit", prompt=prompt))
        self.assertEqual(rec["prompt"], '<pasted_content id="1">Project: D:/x</pasted_content>')
        rec = cc_events.build_record(self.base("UserPromptSubmit",
                                               prompt="<task-notification><task-id>b1</task-id></task-notification>"))
        self.assertEqual(rec.get("prompt", ""), "")  # empty fields are left out of the line

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

    def test_verdict_from_stop_and_subagent_stop(self):
        msg = ("Checked.\nVERDICT: FAIL\nchecks: py -m unittest -> 1 failed\n"
               "failing: tests/test_calc.py:9 - AssertionError: 3 != 4")
        rec = cc_events.build_record(self.base("Stop", transcript_path="", last_assistant_message=msg))
        self.assertEqual((rec["verdict"], rec["verdict_detail"]),
                         ("FAIL", "tests/test_calc.py:9 - AssertionError: 3 != 4"))
        rec = cc_events.build_record(self.base("SubagentStop", agent_id="a1", agent_type="verifier",
                                               last_assistant_message="**VERDICT: PASS**\nchecks: ok"))
        self.assertEqual(rec["verdict"], "PASS")
        self.assertNotIn("verdict_detail", rec)
        rec = cc_events.build_record(self.base("Stop", last_assistant_message="VERDICT: FAIL token=abc broke"))
        self.assertEqual(rec["verdict_detail"], "token=*** broke")
        self.assertNotIn("verdict", cc_events.build_record(self.base("Stop", last_assistant_message="all good")))

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

Run: `py -m unittest tests.test_cc_events`
Expected: ERROR in `test_verdict_from_stop_and_subagent_stop`, `KeyError: 'verdict'`.

- [ ] **Step 3: Replace `cc_events.py`** with:

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
# The verifier agent's report: `VERDICT: PASS | FAIL`, then `failing: <file:line> - <error>` lines.
_VERDICT = re.compile(r"^[\s`*>\-]*VERDICT:\s*(PASS|FAIL)\b[ \t`*:\-]*(.*?)[ \t`*]*$", re.M)
_FAILING = re.compile(r"^[\s`*>\-]*failing:\s*(.+?)[\s`*]*$", re.M)
# A block Claude Code or an extension puts before (or instead of) Fred's text, e.g.
# <browser_instruction>, <task-notification>. Fred's own pastes (<pasted_content>) stay.
_INJECTED = re.compile(r"\s*<(?!pasted_content\b)([A-Za-z][\w-]*)[^>]*>.*?</\1>\s*", re.S)


def strip_injected(text: str) -> str:
    """The prompt without the injected blocks at its start."""
    text = str(text or "")
    for _ in range(10):
        m = _INJECTED.match(text)
        if not m:
            break
        text = text[m.end():]
    return text


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


def verdict(text: str) -> dict:
    """The last `VERDICT: PASS|FAIL` line, with its detail (else the first `failing:` line)."""
    found = _VERDICT.findall(text or "")
    if not found:
        return {}
    word, detail = found[-1]
    if not detail and word == "FAIL":
        m = _FAILING.search(text)
        detail = m.group(1) if m else ""
    out = {"verdict": word}
    if detail:
        out["verdict_detail"] = redact.clip(redact.mask(detail), 160)
    return out


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
        rec["prompt"] = redact.clip(redact.mask(strip_injected(data.get("prompt", ""))), 120)
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
        rec.update(verdict(data.get("last_assistant_message")))
    elif event == "Stop":
        rec.update(transcript_tail(data.get("transcript_path")))
        message = data.get("last_assistant_message") or ""
        route = last_match(_ROUTE, message)
        question = last_match(_STOP, message)
        if route:
            rec["route"] = redact.clip(route, 80)
        if question:
            rec["stop_question"] = redact.clip(redact.mask(question), 200)
        rec.update(verdict(message))
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

- [ ] **Step 4: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 64 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add cc_events.py tests/test_cc_events.py
git commit -m "feat: hook logs VERDICT lines from Stop and SubagentStop"
```

**DONE WHEN**
- [ ] 64 tests OK; `git status --short` empty.

---

### Task 2: State

**Files:**
- Modify: `console/state.py`, `console/paths.py` (full files below)
- Test: `tests/test_state.py` (full file below; 5 new tests)

- [ ] **Step 1: Replace `tests/test_state.py`** with:

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
        self.feed(ev("run_started", T0 + 30),  # it still succeeded: Idle, the denials only as a note
                  ev("run_ended", T0 + 32, subtype="success",
                     denials=[{"tool": "Bash", "what": "find ."}, {"tool": "PowerShell", "what": "ls"}]))
        row = self.row(T0 + 33)
        self.assertEqual((row["state"], row["group"], row["denied"]), ("idle", "working", None))
        self.assertEqual([d["tool"] for d in row["denials"]], ["Bash", "PowerShell"])
        self.feed(ev("run_started", T0 + 40))
        self.assertEqual(self.row(T0 + 41)["denials"], [])

    def test_pasted_prompt_title_and_drive_letter(self):
        self.feed(ev("UserPromptSubmit", T0, prompt='<pasted_content id="9a1c"> Project: D:/x', project_dir="d:/repo"),
                  ev("Stop", T0 + 1, sid="s2", project_dir="D:/repo"))
        self.assertEqual(self.row(T0 + 2)["title"], "Project: D:/x")
        self.assertEqual({r["project_dir"] for r in self.state.snapshot(T0 + 2)["sessions"]}, {"D:/repo"})
        self.feed(ev("UserPromptSubmit", T0 + 3, sid="s3", prompt="<browser_instruction># Claude in Chrome…"),
                  ev("UserPromptSubmit", T0 + 4, sid="s3", prompt="fix the title"))
        self.assertEqual(self.row(T0 + 5, "s3")["title"], "fix the title")

    def test_verdict_from_agent_and_main(self):
        self.feed(ev("UserPromptSubmit", T0),
                  ev("SubagentStart", T0 + 1, agent_id="v1", agent_type="verifier"),
                  ev("SubagentStop", T0 + 5, agent_id="v1", verdict="FAIL", verdict_detail="test_calc.py:9 - 3 != 4"),
                  ev("Stop", T0 + 6))
        row = self.row(T0 + 7)
        self.assertEqual((row["verdict"], row["verdict_detail"], row["agents"][0]["verdict"]),
                         ("FAIL", "test_calc.py:9 - 3 != 4", "FAIL"))
        self.feed(ev("UserPromptSubmit", T0 + 8), ev("Stop", T0 + 9, verdict="PASS"))
        self.assertEqual((self.row(T0 + 10)["verdict"], self.row(T0 + 10)["verdict_detail"]), ("PASS", ""))

    def test_escalate_and_handoff_runs(self):
        self.feed(ev("run_started", T0, kind="run", model="sonnet", effort="low"),
                  ev("run_ended", T0 + 5, subtype="success"),
                  ev("run_started", T0 + 6, kind="escalate", escalated="sonnet/low -> sonnet/medium"),
                  ev("run_ended", T0 + 9, subtype="success"))
        row = self.row(T0 + 10)
        self.assertEqual((row["escalated"], row["kind"]), ("sonnet/low -> sonnet/medium", "escalate"))
        self.feed(ev("run_started", T0 + 11, kind="handoff"))
        self.assertEqual((self.row(T0 + 12)["state"], self.row(T0 + 12)["handoff"]), ("running", True))
        self.feed(ev("run_ended", T0 + 13, subtype="error_during_execution"))
        self.assertEqual(self.row(T0 + 14)["state"], "idle")  # a failed handoff is not Done
        self.feed(ev("run_started", T0 + 15, kind="handoff"), ev("run_ended", T0 + 16, subtype="success"))
        self.assertEqual((self.row(T0 + 17)["state"], self.row(T0 + 17)["group"]), ("done", "done"))
        self.feed(ev("run_started", T0 + 18, kind="continue"))
        self.assertEqual(self.row(T0 + 19)["state"], "running")

    def test_fork_of_a_vscode_session(self):
        self.feed(ev("UserPromptSubmit", T0, sid="v", prompt="fix the updater"),
                  ev("UserPromptSubmit", T0 + 1, sid="v"),
                  ev("Stop", T0 + 2, sid="v", context_tokens=1000, entrypoint="claude-vscode"),
                  ev("run_started", T0 + 3, sid="f", kind="handoff", forked_from="v", title="↳ fix the updater"),
                  ev("UserPromptSubmit", T0 + 4, sid="f", prompt="/session-handoff"),
                  ev("run_ended", T0 + 6, sid="f", subtype="success"))
        parent, fork = self.row(T0 + 7, "v"), self.row(T0 + 7, "f")
        self.assertEqual((parent["forks"], parent["state"], parent["source"]), (["f"], "done", "vscode"))
        self.assertEqual((fork["forked_from"], fork["title"], fork["follow_ups"], fork["source"]),
                         ("v", "↳ fix the updater", 2, "window"))
        self.feed(ev("UserPromptSubmit", T0 + 8, sid="v"))  # Fred typed in VS Code again
        self.assertEqual(self.row(T0 + 9, "v")["state"], "running")

    def test_follow_up_hint(self):
        self.feed(ev("UserPromptSubmit", T0), ev("Stop", T0 + 1), ev("UserPromptSubmit", T0 + 2), ev("Stop", T0 + 3))
        self.assertEqual((self.row(T0 + 4)["follow_ups"], self.row(T0 + 4)["handoff_hint"]), (1, False))
        self.feed(ev("UserPromptSubmit", T0 + 5), ev("Stop", T0 + 6))
        self.assertEqual((self.row(T0 + 7)["follow_ups"], self.row(T0 + 7)["handoff_hint"]), (2, True))
        self.feed(ev("Stop", T0, sid="big", context_tokens=400000))
        self.assertTrue(self.row(T0 + 1, "big")["handoff_hint"])
        self.assertFalse(self.row(T0 + 4000, "big")["handoff_hint"])  # Stale?: no hint

    def test_timeline_turns_and_agents(self):
        self.feed(ev("UserPromptSubmit", T0),
                  ev("SubagentStart", T0 + 2, agent_id="a1", agent_type="Explore"),
                  ev("SubagentStop", T0 + 6, agent_id="a1"),
                  ev("Stop", T0 + 8),
                  ev("UserPromptSubmit", T0 + 20),
                  ev("PreToolUse", T0 + 21, agent_id="a2", agent_type="verifier", tool="Bash"))
        t = self.state.timeline("s1", T0 + 30)
        self.assertEqual((t["start"], t["end"]), (T0, T0 + 30))
        self.assertEqual([lane["label"] for lane in t["lanes"]], ["main", "Explore", "verifier"])
        self.assertEqual(t["lanes"][0]["spans"], [[T0, T0 + 8], [T0 + 20, T0 + 30]])
        self.assertEqual(t["lanes"][1]["spans"], [[T0 + 2, T0 + 6]])
        self.assertEqual(t["lanes"][2]["spans"], [[T0 + 21, T0 + 30]])
        self.assertIsNone(self.state.timeline("nope", T0))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_state`
Expected: 5 errors: `KeyError: 'escalated'`, `KeyError: 'follow_ups'`, `KeyError: 'forks'`, `AttributeError: 'State' object has no attribute 'timeline'`, `KeyError: 'verdict'`.

- [ ] **Step 3: Replace `console/paths.py`** with (one new key, `handoff_after_followups`):

```python
"""Where Claude Console keeps its files, and its config with defaults."""
import copy
import json
import os
from pathlib import Path

DEFAULTS = {
    "port": 47770,
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
    "handoff_after_followups": 2,
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


def add_project(folder: Path, project: str) -> None:
    """Add `project` to "projects" in <folder>/config.json; every other key stays as written.
    Raises ValueError when config.json exists but cannot be read (never overwrite Fred's file)."""
    path = Path(folder) / "config.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            raise ValueError(f"cannot read {path}: fix it by hand")
    else:
        data = copy.deepcopy(DEFAULTS)
    projects = data.get("projects") if isinstance(data.get("projects"), list) else []
    key = os.path.normcase(os.path.abspath(project))
    if all(os.path.normcase(os.path.abspath(p)) != key for p in projects if isinstance(p, str)):
        projects.append(project)
    data["projects"] = projects
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("config.json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def ensure_config() -> dict:
    """Write config.json with the defaults if it does not exist, then load it."""
    path = home() / "config.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULTS, indent=2) + "\n", encoding="utf-8")
    return load_config()
```

- [ ] **Step 4: Replace `console/state.py`** with:

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
MAX_TURNS = 200
SHOW_FOR_S = 86400
_PASTED = re.compile(r"</?pasted_content[^>]*>")
_TAGGED = re.compile(r"<[A-Za-z]")  # an injected block the hook clipped before it closed: not a title


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
    verdict: str = ""


@dataclass
class Session:
    id: str
    started_ts: float = 0.0
    last_ts: float = 0.0
    project: str = ""
    project_dir: str = ""
    cwd: str = ""
    first_cwd: str = ""  # where the chat started: Claude Code files it under this folder (resume / fork)
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
    denials: list = field(default_factory=list)  # a run that still succeeded: shown as a note
    verdict: str = ""          # PASS / FAIL from the last VERDICT: line (verifier or main)
    verdict_detail: str = ""
    escalated: str = ""        # "sonnet/medium -> sonnet/high" once Escalate ran (once per task)
    kind: str = ""             # the last window run: run, continue, verify, handoff, escalate
    handoff: bool = False      # a Handoff run is going
    handed_off: bool = False   # a Handoff run succeeded: Done
    forked_from: str = ""
    forks: list = field(default_factory=list)
    turns: list = field(default_factory=list)  # [start, end or None] per turn, for the Timeline


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
        if rec.get("cwd") and not s.first_cwd:
            s.first_cwd = rec["cwd"]
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
            text = redact.clip(_PASTED.sub(" ", rec.get("prompt", "")), 60)
            if not s.title and not _TAGGED.match(text):
                s.title = text
            s.denied = s.failed = None
            s.stop_question = ""
            s.interrupted = s.stopped = s.handed_off = False
            self._turn_open(s, ts)
        elif event == "PreToolUse":
            s.in_turn = True
            self._turn_open(s, ts)
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
            if rec.get("verdict"):
                agent.verdict = rec["verdict"]
                self._verdict(s, rec)
        elif event == "PermissionDenied":
            s.denied = {"tool": rec.get("tool", ""), "what": rec.get("what", ""),
                        "reason": rec.get("reason", ""), "ts": ts}
            self._step(s, ts, aid, rec.get("tool", ""), rec.get("what", ""), denied=True)
        elif event == "Stop":
            s.in_turn = False
            s.doing = ""
            self._turn_close(s, ts)
            s.model = rec.get("model") or s.model
            if rec.get("context_tokens") is not None:
                s.ctx_tokens = rec["context_tokens"]
            if rec.get("entrypoint") and not s.window:
                s.source = SOURCES.get(rec["entrypoint"], rec["entrypoint"])
            if rec.get("route"):
                s.route = rec["route"]
            s.stop_question = rec.get("stop_question", "")
            if rec.get("verdict"):
                self._verdict(s, rec)
        elif event == "StopFailure":
            s.in_turn = False
            self._turn_close(s, ts)
            s.failed = {"error": rec.get("error", "unknown"), "details": rec.get("error_details", "")}
        elif event == "PostCompact":
            s.ctx_tokens = None
            s.compactions += 1
        elif event == "SessionEnd":
            s.in_turn = False
            self._turn_close(s, ts)
            s.ended = not s.window  # a window run's process ends after every turn; it can resume
        elif event == "run_started":
            s.window, s.run_live, s.source = True, True, "window"
            s.in_turn, s.ended = True, False
            self._turn_open(s, ts)
            s.interrupted = s.stopped = s.handed_off = False
            s.denied = s.failed = None
            s.denials = []
            s.stop_question = ""
            s.kind = rec.get("kind") or "run"
            s.handoff = s.kind == "handoff"
            if rec.get("escalated"):
                s.escalated = rec["escalated"]
            parent = self.sessions.get(rec.get("forked_from") or "")
            if parent and parent is not s:
                s.forked_from = parent.id
                if s.id not in parent.forks:
                    parent.forks.append(s.id)
                if not s.prompts:  # the copy carries the parent's context: same follow-up count
                    s.prompts, s.ctx_tokens = parent.prompts, parent.ctx_tokens
                if s.escalated:
                    parent.escalated = s.escalated  # once per task, whichever copy escalated
                elif parent.escalated:
                    s.escalated = parent.escalated
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
            self._turn_close(s, ts)
            s.cost += float(rec.get("cost") or 0)
            s.stopped = bool(rec.get("stopped"))
            s.interrupted = bool(rec.get("interrupted"))
            if s.handoff and rec.get("subtype") == "success":
                s.handed_off = True
                parent = self.sessions.get(s.forked_from)
                if parent:
                    parent.handed_off = True
            s.handoff = False
            if rec.get("denials") and rec.get("subtype") == "success":
                s.denials = [{"tool": d.get("tool", ""), "what": d.get("what", "")} for d in rec["denials"]]
            elif rec.get("denials") and not s.denied:
                first = rec["denials"][0]
                s.denied = {"tool": first.get("tool", ""), "what": first.get("what", ""),
                            "reason": "window runs cannot ask: open in terminal", "ts": ts}

    def _step(self, s, ts, aid, tool, what, denied=False):
        s.steps.append({"ts": ts, "agent": aid or "", "tool": tool, "what": what, "denied": denied})
        if len(s.steps) > MAX_STEPS:
            del s.steps[: len(s.steps) - MAX_STEPS]

    def _verdict(self, s, rec):
        s.verdict, s.verdict_detail = rec["verdict"], rec.get("verdict_detail", "")

    def _turn_open(self, s, ts):
        if not s.turns or s.turns[-1][1] is not None:
            s.turns.append([ts, None])
            if len(s.turns) > MAX_TURNS:
                del s.turns[0]

    def _turn_close(self, s, ts):
        if s.turns and s.turns[-1][1] is None:
            s.turns[-1][1] = ts

    # -- snapshot -----------------------------------------------------------------
    def state_of(self, s: Session, now: float) -> str:
        if s.ended or s.handed_off:
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
            follow_ups = max(0, s.prompts - 1)
            rows.append({
                "id": s.id, "project": s.project, "project_dir": s.project_dir,
                "title": s.title or f"(prompt not seen) {s.id[:8]}", "source": s.source or "?",
                "model": s.model, "effort": s.effort, "route": s.route or "unrouted",
                "state": state, "symbol": symbol, "text": text, "tone": state_tone,
                "group": group, "doing": s.doing, "prompts": s.prompts,
                "ctx_tokens": s.ctx_tokens, "ctx_fill": None if pct is None else round(pct, 3),
                "ctx_tone": tone, "compactions": s.compactions,
                "stop_question": s.stop_question, "denied": s.denied, "failed": s.failed,
                "denials": s.denials,
                "two_writers": s.id in writer_ids,
                "window": s.window, "run_live": s.run_live, "stopped": s.stopped,
                "cost": round(s.cost, 4), "route_reason": s.route_reason, "prep": s.prep,
                "start_commit": s.start_commit, "cwd": s.cwd,
                "started_ts": s.started_ts, "last_ts": s.last_ts,
                "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated,
                "kind": s.kind, "handoff": s.handoff, "forked_from": s.forked_from, "forks": list(s.forks),
                "follow_ups": follow_ups,
                "handoff_hint": state not in DONE and (
                    tone == "red" or follow_ups >= self.cfg["handoff_after_followups"]),
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
                "tokens": a.tokens, "steps": a.steps, "doing": a.doing, "verdict": a.verdict,
                "symbol": symbol, "text": text, "tone": tone,
                "ctx_fill": None if fill is None else round(fill, 3), "ctx_tone": ctx_tone}

    def steps(self, session_id: str, limit: int = 200) -> list:
        s = self.sessions.get(session_id)
        if not s:
            return []
        types = {a.id: a.type for a in s.agents.values()}
        return [dict(step, agent_type=types.get(step["agent"], "") if step["agent"] else "main")
                for step in s.steps[-limit:]]

    def timeline(self, session_id: str, now: float):
        """Bars over time (D7 C): the main thread's turns, then one bar per agent run."""
        s = self.sessions.get(session_id)
        if not s:
            return None
        live = s.in_turn or s.run_live
        end = now if live else s.last_ts
        lanes = [{"label": "main", "tone": "info", "verdict": "",
                  "spans": [[a, end if b is None else b] for a, b in s.turns]}]
        for a in sorted(s.agents.values(), key=lambda x: x.started_ts):
            stop = a.last_ts if a.done or not live else end
            lanes.append({"label": a.type or "agent", "tone": "success" if a.done else "info",
                          "verdict": a.verdict, "spans": [[a.started_ts, stop]]})
        start = min([s.started_ts] + [sp[0] for lane in lanes for sp in lane["spans"]])
        return {"start": start, "end": max(end, start), "lanes": lanes}
```

- [ ] **Step 5: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 69 tests ... OK`.

- [ ] **Step 6: Commit**

```bash
git add console/paths.py console/state.py tests/test_state.py
git commit -m "feat: state keeps verdicts, lever runs, forks, follow-ups and Timeline turns"
```

**DONE WHEN**
- [ ] 69 tests OK; `git status --short` empty.

---

### Task 3: claude_cli fork, levers, Prep misses

**Files:**
- Create: `console/levers.py`, `tests/test_levers.py`
- Modify: `console/claude_cli.py`, `console/prep.py`, `console/prep_prompt.md` (full files below)
- Test: `tests/test_claude_cli.py` (full file below; 2 new tests)

- [ ] **Step 1: Replace `tests/test_claude_cli.py`** with:

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

    def test_run_command_fork(self):
        cmd = claude_cli.run_command(["claude.exe"], "sonnet", "low", "new", name="↳ x", fork="old")
        i = cmd.index("--resume")
        self.assertEqual(cmd[i:i + 5], ["--resume", "old", "--fork-session", "--session-id", "new"])
        self.assertEqual(cmd[cmd.index("--name") + 1], "↳ x")

    def test_model_alias(self):
        names = ("claude-sonnet-5-5", "claude-haiku-4-5-20251001", "opus", "gpt-9", None)
        self.assertEqual([claude_cli.model_alias(m) for m in names], ["sonnet", "haiku", "opus", "", ""])

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

    def test_terminal_keeps_the_run_model(self):
        self.assertEqual(claude_cli.terminal_command(["claude.exe"], "abc", "sonnet", "low"),
                         ["claude.exe", "--resume", "abc", "--model", "sonnet", "--effort", "low"])
        self.assertEqual(claude_cli.terminal_command(["claude.exe"], "abc"), ["claude.exe", "--resume", "abc"])

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

- [ ] **Step 2: Create `tests/test_levers.py`**

```python
import tempfile
import time
import unittest
from pathlib import Path

from console import levers, prep


class LeversTest(unittest.TestCase):
    def test_escalate_step(self):
        cases = {("haiku", "low"): ("haiku", "medium"), ("sonnet", "medium"): ("sonnet", "high"),
                 ("sonnet", "high"): ("opus", "high"), ("opus", "high"): ("fable", "high"),
                 ("opus", "xhigh"): ("fable", "xhigh"), ("fable", "high"): ("fable", "xhigh"),
                 ("fable", "max"): None, ("gpt", "low"): None}
        for (model, effort), want in cases.items():
            self.assertEqual(levers.escalate_step(model, effort), want, (model, effort))

    def test_misses_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = time.mktime((2026, 10, 10, 12, 0, 0, 0, 0, -1))
            line = levers.miss_line("CALC", "mechanical", "sonnet/low", "sonnet/medium",
                                    "test_add - 3 != 4 token=abc", now)
            self.assertEqual(line, "- 2026-10-10 - CALC - mechanical: sonnet/low failed "
                                   "(test_add - 3 != 4 token=***); next time start at sonnet/medium.")
            levers.add_miss(Path(tmp), line)
            levers.add_miss(Path(tmp), levers.miss_line("OTHER", "", "opus/high", "fable/high", "", now))
            self.assertEqual(levers.read_misses(Path(tmp), "CALC"), [line])
            self.assertIn("unrouted: opus/high failed (verifier FAIL)", levers.read_misses(Path(tmp), "OTHER")[0])
            text = (Path(tmp) / "routing-misses.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Routing misses"))
            self.assertEqual(levers.read_misses(Path(tmp) / "nope", "CALC"), [])
            self.assertIn(line, prep.build_prompt("x", [line]))
            self.assertIn("\n(none)\n", prep.build_prompt("x"))

    def test_handoff_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, home = Path(tmp) / "proj", Path(tmp) / "home"
            proj.mkdir()
            self.assertFalse(levers.handoff_ready(str(proj), home))
            local = proj / ".claude" / "skills" / "session-handoff"
            local.mkdir(parents=True)
            (local / "SKILL.md").write_text("x", encoding="utf-8")
            self.assertTrue(levers.handoff_ready(str(proj), home))
            self.assertFalse(levers.handoff_ready("", home))
            mine = home / ".claude" / "skills" / "session-handoff"
            mine.mkdir(parents=True)
            (mine / "SKILL.md").write_text("x", encoding="utf-8")
            self.assertTrue(levers.handoff_ready("", home))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run them to see them fail**

Run: `py -m unittest tests.test_claude_cli tests.test_levers`
Expected: 3 errors: `AttributeError: module 'console.claude_cli' has no attribute 'model_alias'`, `TypeError: run_command() got an unexpected keyword argument 'fork'`, `ImportError: cannot import name 'levers' from 'console'`.

- [ ] **Step 4: Replace `console/claude_cli.py`** with:

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
                name: str = "", fork: str = "") -> list:
    """D5: auto mode, nobody answers prompts (a denial ends up in the result). Prompts go in on stdin.
    `fork`: start `session_id` as a copy of that chat (its context, a new id; the original is not touched)."""
    cmd = exe + ["-p", "--model", model, "--effort", effort, "--permission-mode", "auto",
                 "--permission-prompts", "none", "--input-format", "stream-json",
                 "--output-format", "stream-json", "--verbose"]
    if fork:
        cmd += ["--resume", fork, "--fork-session", "--session-id", session_id]
    elif resume:
        cmd += ["--resume", session_id]
    else:
        cmd += ["--session-id", session_id]
    if name and not resume:
        cmd += ["--name", name]
    return cmd


def model_alias(model: str) -> str:
    """claude-sonnet-5-5 -> sonnet (the names routes use); "" when unknown."""
    low = str(model or "").lower()
    return next((m for m in MODELS if m in low), "")


def terminal_command(exe: list, session_id: str, model: str = "", effort: str = "") -> list:
    """Interactive resume on the run's own model and effort (not Fred's default)."""
    cmd = exe + ["--resume", session_id]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    return cmd


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

- [ ] **Step 5: Create `console/levers.py`**

```python
"""Phase 3 levers: the texts Verify, Handoff and Escalate send, the escalation step, and the
routing-misses file. When a lever is allowed is decided in one place: server.Hub.levers."""
import time
from pathlib import Path

from . import claude_cli, redact

VERIFY_TEXT = ("Check the work of this session. If this project has a `verifier` agent, run it; otherwise "
               "run the project's tests or checks once. Do not edit any file. End your final message "
               "with one line: `VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`.")
HANDOFF_TEXT = "/session-handoff"
HANDOFF_SKILL = Path("skills") / "session-handoff" / "SKILL.md"
MISSES_FILE = "routing-misses.md"
MISSES_HEAD = ("# Routing misses\n\nOne line per Escalate, written by Claude Console. "
               "Prep reads the lines of its project.\n\n")
MISSES_SHOWN = 20


def escalate_step(model: str, effort: str):
    """One step up (route-model: effort first, then a bigger model): effort +1 up to high, then
    the next model at the same effort; on the top model, effort +1. None when nothing is above."""
    models, efforts = claude_cli.MODELS, claude_cli.EFFORTS
    if model not in models or effort not in efforts:
        return None
    e, m = efforts.index(effort), models.index(model)
    if e < efforts.index("high"):
        return model, efforts[e + 1]
    if m + 1 < len(models):
        return models[m + 1], effort
    if e + 1 < len(efforts):
        return model, efforts[e + 1]
    return None


def escalate_text(detail: str, model: str, effort: str) -> str:
    failed = detail or "see the last VERDICT line"
    return (f"The checks failed: {failed}. You now run on {model}/{effort} (escalated once). Find and fix "
            "the cause, run the checks again, then end your final message with one line: "
            "`VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`.")


def handoff_ready(project_dir: str, home: Path = None) -> bool:
    """True when Claude Code can expand /session-handoff here: the project's or Fred's own skill."""
    places = [Path(project_dir) / ".claude" if project_dir else None, Path(home or Path.home()) / ".claude"]
    return any(p is not None and (p / HANDOFF_SKILL).is_file() for p in places)


def miss_line(project: str, task_type: str, route_from: str, route_to: str, detail: str,
              now: float = None) -> str:
    day = time.strftime("%Y-%m-%d", time.localtime(now or time.time()))
    why = redact.clip(redact.mask(detail), 120) or "verifier FAIL"
    return (f"- {day} - {project} - {task_type or 'unrouted'}: {route_from} failed ({why}); "
            f"next time start at {route_to}.")


def add_miss(folder: Path, line: str) -> None:
    path = Path(folder) / MISSES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    head = "" if path.exists() else MISSES_HEAD
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(head + line + "\n")


def read_misses(folder: Path, project: str, limit: int = MISSES_SHOWN) -> list:
    """The last `limit` miss lines of one project (matched by the project folder's name)."""
    try:
        lines = (Path(folder) / MISSES_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    tag = f" - {project} - "
    return [line for line in lines if line.startswith("- ") and tag in line][-limit:]
```

- [ ] **Step 6: Replace `console/prep.py`** with:

```python
"""Prep (D3, D4): a read-only Haiku pass scouts the project, rewrites the prompt and picks a route.
The card always waits for Fred; nothing here starts a run."""
import json
import secrets
import subprocess
import time
from pathlib import Path
from string import Template

from . import claude_cli, levers, redact

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


def build_prompt(raw: str, misses=()) -> str:
    """The Prep instructions with Fred's request and this project's routing misses filled in."""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        raw=raw.strip(), misses="\n".join(misses) or "(none)")


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
    prompt = build_prompt(raw, levers.read_misses(folder, Path(project_dir).name))
    try:
        out = subprocess.run(cmd, cwd=project_dir, input=prompt.encode("utf-8"),
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

- [ ] **Step 7: Replace `console/prep_prompt.md`** with:

```markdown
You are a prompt formatter for Claude Code. Fred typed the request at the end for the project in the
current folder. Do three things, then answer with the JSON object only.

1. Scout (at most 8 tool calls, Read / Grep / Glob only). Read CLAUDE.md first if it exists, then the
   History section of PLAN.md if it exists, then routing-misses.md if it exists. Find the files,
   functions and rules the request touches.
2. Enhance: rewrite the request so another model can do it with no other context. Do not solve the
   task. Do not invent requirements. If something essential is unclear, ask one question in
   `question` (else "").
3. Route: pick the cheapest route that should succeed. A routing miss (listed below, or in a
   routing-misses.md you read) that matches this kind of task overrides the table.

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

Routing misses in this project (Escalate wrote them; newest last):
$misses

Request:
$raw
```

- [ ] **Step 8: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 74 tests ... OK`.

- [ ] **Step 9: Commit**

```bash
git add console/claude_cli.py console/levers.py console/prep.py console/prep_prompt.md tests/test_claude_cli.py tests/test_levers.py
git commit -m "feat: fork command, escalation step, routing misses read by Prep"
```

**DONE WHEN**
- [ ] 74 tests OK; `git status --short` empty.

---

### Task 4: Runs

**Files:**
- Modify: `console/runs.py` (full file below)
- Test: `tests/test_runs.py` (full file below; 1 new test)

- [ ] **Step 1: Replace `tests/test_runs.py`** with:

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

    def test_fork_starts_a_window_copy(self):
        sid = self.mgr.start(str(self.project), "/session-handoff", "sonnet", "low", fork="vscode-1",
                             title="↳ fix", kind="handoff", extra={"escalated": "x"})
        self.assertNotEqual(sid, "vscode-1")
        self.assertTrue(wait_for(lambda: self.ended(sid)))
        started = [r for r in self.log() if r["event"] == "run_started"][0]
        self.assertEqual((started["kind"], started["forked_from"], started["escalated"]),
                         ("handoff", "vscode-1", "x"))
        claude = [i["text"] for i in runs.chat(self.mgr.stream_path(sid)) if i["role"] == "claude"]
        self.assertEqual(claude, ["echo: /session-handoff"])  # no STOP footer after a /skill
        self.assertEqual(self.mgr.meta(sid)["model"], "sonnet")

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

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_runs`
Expected: ERROR in `test_fork_starts_a_window_copy`, `TypeError: RunManager.start() got an unexpected keyword argument 'fork'`.

- [ ] **Step 3: Replace `console/runs.py`** with:

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
              title: str = "", route: str = "", reason: str = "", prep: str = "",
              fork: str = "", kind: str = "run", extra: dict = None) -> str:
        """A new run, a new turn of a window run (`resume`), or a window copy of another chat (`fork`).
        `kind` (run, continue, verify, handoff, escalate) and `extra` go into the run_started line."""
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
                                     name=redact.clip(title, 60), fork=fork)
        proc = self._spawn(cmd, cwd, path)
        footer = "" if prompt.startswith("/") else claude_cli.STOP_FOOTER  # a /skill takes no footer
        proc.stdin.write(claude_cli.user_message(prompt + footer))
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
               "model": model, "effort": effort, "resume": bool(resume), "start_commit": start_commit,
               "kind": kind}
        for key, value in (("title", title), ("route", route), ("reason", reason), ("prep", prep),
                           ("forked_from", fork)):
            if value:
                rec[key] = value
        rec.update(extra or {})
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
        subprocess.Popen(claude_cli.terminal_command(self.exe, sid, meta.get("model", ""), meta.get("effort", "")),
                         cwd=meta["cwd"],
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

- [ ] **Step 4: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 75 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add console/runs.py tests/test_runs.py
git commit -m "feat: runs can fork a chat and carry their lever kind"
```

**DONE WHEN**
- [ ] 75 tests OK; `git status --short` empty.

---

### Task 5: Service routes

**Files:**
- Modify: `console/server.py` (full file below)
- Test: `tests/test_server.py` (full file below; `test_answer_...` becomes `test_continue_...`, 3 new tests)

- [ ] **Step 1: Replace `tests/test_server.py`** with:

```python
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from console import events, guard, levers, paths, server


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
    """POST routes with the fake claude: prep, run, chat, stop, levers, draft."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        cfg = dict(paths.load_config(), projects=[str(self.project)])
        fake = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
        self.httpd, self.hub = server.make_server(cfg, port=0, folder=self.folder, exe=fake)
        self.hub.user_home = Path(self.tmp.name)  # no ~/.claude/skills here unless a test adds one
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

    def wait_idle(self, sid):
        end = time.time() + 15
        while time.time() < end and (self.session(sid) is None or self.session(sid)["run_live"]):
            time.sleep(0.1)

    def test_continue_resumes_and_stop_interrupts(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "SLOW one"})[1]["session"]
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "go"})[0], 409)  # still running
        end = time.time() + 15
        while time.time() < end and "echo" not in self.hub.runs.stream_path(sid).read_text(encoding="utf-8"):
            time.sleep(0.1)
        self.assertEqual(self.call("/api/stop", {"session": sid}), (200, {"stop": "interrupt"}))
        while time.time() < end and self.session(sid)["run_live"]:
            time.sleep(0.1)
        self.assertEqual(self.session(sid)["stopped"], True)
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "go on"}), (200, {"session": sid}))

    def test_levers_fork_a_vscode_session(self):
        for event, extra in (("UserPromptSubmit", {"prompt": "fix add"}),
                             ("Stop", {"model": "claude-sonnet-5-5", "effort": "medium"})):
            events.append(self.folder, dict({"event": event, "ts": time.time(), "session_id": "v1",
                                             "project": "proj", "project_dir": str(self.project),
                                             "cwd": str(self.project)}, **extra))
        self.hub.poll_once()
        lv = self.call("/api/levers?session=v1")[1]
        self.assertEqual((lv["continue"], lv["fork"], lv["route"]), ("", True, "sonnet/medium"))
        self.assertEqual(lv["escalate"], "only after a FAIL verdict")
        self.assertIn("session-handoff skill", lv["handoff"])
        self.assertEqual(self.call("/api/handoff", {"session": "v1"})[0], 409)
        self.assertEqual(self.call("/api/levers?session=nope")[0], 404)
        self.assertEqual(self.call("/api/continue", {"session": "v1", "text": " "})[0], 400)
        status, data = self.call("/api/continue", {"session": "v1", "text": "and the tests"})
        self.assertEqual(status, 200)
        fork = data["session"]
        self.assertNotEqual(fork, "v1")
        row = self.session(fork)
        self.assertEqual((row["forked_from"], row["title"], row["kind"], row["source"]),
                         ("v1", "↳ fix add", "continue", "window"))
        self.assertEqual(self.session("v1")["forks"], [fork])
        self.assertEqual((self.hub.runs.meta(fork)["model"], self.hub.runs.meta(fork)["effort"]), ("sonnet", "medium"))
        self.wait_idle(fork)
        timeline = self.call(f"/api/timeline?session={fork}")[1]
        self.assertEqual([lane["label"] for lane in timeline["lanes"]], ["main"])
        self.assertEqual(len(timeline["lanes"][0]["spans"]), 1)

    def test_verify_then_escalate_once(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",
                                     "model": "sonnet", "effort": "high"})[1]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.call("/api/escalate", {"session": sid}), (409, {"error": "only after a FAIL verdict"}))
        self.assertEqual(self.call("/api/verify", {"session": sid}), (200, {"session": sid}))
        self.wait_idle(sid)
        events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": sid,  # what the hook logs
                                    "verdict": "FAIL", "verdict_detail": "test_add - 3 != 4"})
        self.hub.poll_once()
        self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["escalate_to"], "opus/high")
        self.assertEqual(self.call("/api/escalate", {"session": sid}), (200, {"session": sid}))
        self.assertEqual(self.hub.runs.meta(sid)["model"], "opus")
        self.wait_idle(sid)
        self.assertEqual(self.session(sid)["escalated"], "sonnet/high -> opus/high")
        self.assertTrue(self.call(f"/api/levers?session={sid}")[1]["escalate"].startswith("escalated once already"))
        misses = levers.read_misses(self.folder, "proj")
        self.assertEqual(len(misses), 1)
        self.assertTrue(misses[0].endswith(" - proj - raw: sonnet/high failed (test_add - 3 != 4); "
                                           "next time start at opus/high."))
        you = [i["text"] for i in self.call(f"/api/chat?session={sid}")[1]["items"] if i["role"] == "you"]
        self.assertTrue(you[1].startswith("Check the work of this session."))
        self.assertTrue(you[2].startswith("The checks failed: test_add - 3 != 4. You now run on opus/high"))

    def test_handoff_marks_the_session_done(self):
        skill = self.project / ".claude" / "skills" / "session-handoff"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add"})[1]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.call("/api/handoff", {"session": sid}), (200, {"session": sid}))
        self.wait_idle(sid)
        row = self.session(sid)
        self.assertEqual((row["state"], row["group"], row["kind"]), ("done", "done", "handoff"))

    def test_allow_adds_a_folder_claude_code_ran_in(self):
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        self.folder.mkdir(parents=True)
        (self.folder / "config.json").write_text('{"port": 8770, "projects": []}', encoding="utf-8")
        events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": "v1",
                                    "project": "other", "project_dir": str(other)})
        self.hub.poll_once()
        run = {"project_dir": str(other), "prompt": "x"}
        self.assertEqual(self.call("/api/run", dict(run, model="gpt-9"))[0], 403)
        self.assertEqual(self.call("/api/allow", {"project_dir": self.tmp.name})[0], 403)  # no session there
        self.assertEqual(self.call("/api/allow", {"project_dir": str(other / "nope")})[0], 400)
        status, data = self.call("/api/allow", {"project_dir": str(other)})
        self.assertEqual(status, 200)
        self.assertEqual(data["projects"], self.call("/api/config")[1]["projects"])
        self.assertEqual(len(data["projects"]), 2)
        saved = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.assertEqual((saved["port"], len(saved["projects"])), (8770, 1))
        self.assertEqual(self.call("/api/allow", {"project_dir": str(other)})[0], 200)  # twice: no duplicate
        self.assertEqual(len(json.loads((self.folder / "config.json").read_text(encoding="utf-8"))["projects"]), 1)
        self.assertEqual(self.call("/api/run", dict(run, model="gpt-9"))[0], 400)  # past the folder check

    def test_draft_and_config(self):
        self.assertEqual(self.call("/api/draft", {"text": "half a prompt"}), (200, {"ok": True}))
        self.assertEqual(self.call("/api/draft")[1], {"text": "half a prompt"})
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["projects"], cfg["claude"], cfg["default_model"]), ([str(self.project)], True, "sonnet"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_server`
Expected: 4 errors, each `json.decoder.JSONDecodeError: Expecting value` (the new routes answer 404 in plain text).

- [ ] **Step 3: Replace `console/server.py`** with:

```python
"""The console service: reads the event log, keeps the state, serves the window over HTTP + SSE,
starts, stops and resumes window runs (phase 2), and pulls the levers (phase 3)."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import claude_cli, events, guard, levers, paths, prep, runs
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
BUSY = {"running", "quiet", "stall"}


class Hub:
    """Owns the State. One thread polls the log; readers wait on `changed`."""

    def __init__(self, cfg: dict, folder: Path, exe: list = None):
        self.cfg = cfg
        self.folder = Path(folder)
        self.state = State(cfg)
        self.reader = events.LogReader(folder)
        self.runs = runs.RunManager(cfg, folder, exe)
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

    def timeline(self, session_id: str):
        with self.lock:
            return self.state.timeline(session_id, time.time())

    def session(self, session_id: str):
        with self.lock:
            s = self.state.sessions.get(session_id)
            if s is None:
                return None
            return {"cwd": s.cwd, "first_cwd": s.first_cwd or s.cwd, "window": s.window, "title": s.title,
                    "model": s.model, "effort": s.effort, "prep": s.prep, "start_commit": s.start_commit,
                    "project": s.project, "project_dir": s.project_dir, "route": s.route,
                    "run_live": s.run_live, "state": self.state.state_of(s, time.time()),
                    "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated}

    def route_of(self, session_id: str, s: dict) -> tuple:
        """(model, effort) the session runs on: a window run's own route, else the model last seen."""
        meta = self.runs.meta(session_id) or {}
        model = meta.get("model") or claude_cli.model_alias(s["model"]) or self.cfg["default_model"]
        effort = meta.get("effort") or (s["effort"] if s["effort"] in claude_cli.EFFORTS
                                        else self.cfg["default_effort"])
        return model, effort

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
                           "the session-handoff skill is not installed here (phase 4 moves it to ~/.claude)")
        return {"continue": base, "verify": base, "handoff": handoff, "escalate": escalate,
                "route": f"{model}/{effort}", "escalate_to": "/".join(step) if step else "",
                "fork": not window, "cwd": cwd or ""}

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
            cfg = self.hub.cfg
            return self._json({"projects": project_list(cfg), "models": claude_cli.MODELS,
                               "efforts": claude_cli.EFFORTS, "default_model": cfg["default_model"],
                               "default_effort": cfg["default_effort"], "claude": bool(self.hub.runs.exe),
                               "config_path": str(self.hub.folder / "config.json")})
        if url.path == "/api/chat":
            return self._chat(query.get("session", [""])[0])
        if url.path in ("/api/levers", "/api/timeline"):
            sid = query.get("session", [""])[0]
            data = self.hub.levers(sid) if url.path == "/api/levers" else self.hub.timeline(sid)
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
                  "/api/terminal": self._terminal, "/api/draft": self._draft, "/api/allow": self._allow}
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

    def _lever(self, body, lever):
        """Continue (also STOP answers and Resume), Verify, Handoff, Escalate: a new turn of a window
        run, or a window copy (fork) of a VS Code / terminal chat, which stays as it is."""
        sid = body.get("session")
        info = self.hub.levers(sid)
        if info is None:
            return self._error(404, "unknown session")
        if info[lever]:
            return self._error(409, info[lever])
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

- [ ] **Step 4: Run all tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 78 tests ... OK`.

- [ ] **Step 5: Commit**

```bash
git add console/server.py tests/test_server.py
git commit -m "feat: service routes for Continue, Verify, Handoff, Escalate, levers and Timeline"
```

**DONE WHEN**
- [ ] 78 tests OK; `git status --short` empty.

---

### Task 6: Window

**Files:**
- Modify: `web/app.js`, `web/style.css` (full files below). `web/index.html` is unchanged.

- [ ] **Step 1: Replace `web/app.js`** with:

```javascript
// Claude Console window: renders /api/stream snapshots; phase 2 adds the prompt box, Prep card and runs;
// phase 3 the levers (Continue, Verify, Handoff, Escalate), verdicts and the Timeline tab.
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
function dur(sec) {
  sec = Math.max(0, Math.round(sec));
  if (sec < 90) return sec + " s";
  const min = Math.round(sec / 60);
  return min < 90 ? min + " min" : Math.floor(min / 60) + " h " + (min % 60) + " min";
}
function verdictBadge(v) { return v ? `<span class="badge ${v === "PASS" ? "success" : "danger"}">${esc(v)}</span>` : ""; }
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
    ${verdictBadge(s.verdict)}
    ${s.two_writers ? '<span class="badge warning">2 writers</span>' : ""}
    ${s.handoff_hint && s.ctx_tone !== "red" ? '<span class="badge warning">handoff?</span>' : ""}
    ${gauge(s)}</div>`;
  const ups = s.follow_ups ? ` &middot; ${s.follow_ups} follow-up${s.follow_ups === 1 ? "" : "s"}` : "";
  const fork = s.forks.length ? " &middot; continued in a window copy" : "";
  html += `<div class="row m ind mut"><span class="title">${esc(s.project)} &middot; ${esc(s.source)} &middot; ${esc(routeText(s))}${ups}${fork}${s.doing ? " &middot; " + esc(s.doing) : ""}</span></div>`;
  if (s.verdict === "FAIL" && s.verdict_detail) html += `<div class="note m"><span class="danger">&times; FAIL</span> ${esc(s.verdict_detail)}</div>`;
  if (s.stop_question) html += `<div class="note ask"><span class="warning">? STOP</span> ${esc(s.stop_question)}</div>`;
  if (s.denied) html += `<div class="note m"><span class="danger">&#9632; denied</span> ${esc(s.denied.tool)} ${esc(s.denied.what)} <span class="mut">${esc(s.denied.reason)}</span></div>`;
  if (s.denials && s.denials.length) {
    const d = s.denials[0], more = s.denials.length > 1 ? ` (+${s.denials.length - 1})` : "";
    html += `<div class="note m"><span class="warning">&#9651; ${s.denials.length} denied</span> ${esc(d.tool)} ${esc(d.what)}${more} <span class="mut">the run still finished; open in terminal to allow</span></div>`;
  }
  if (s.failed) html += `<div class="note m"><span class="danger">&times; ${esc(s.failed.error)}</span> <span class="mut">${esc(s.failed.details)}</span></div>`;
  for (const a of s.agents) {
    html += `<div class="row m ind"><span class="${a.tone}">${a.symbol} ${esc(a.text)}</span>${verdictBadge(a.verdict)}
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
  if (!$("project").value) return '<span class="mut">To run: pick a project in the list at the top (next to "Claude Console")</span>';
  if (!runnable()) return `<span class="mut">Runs are off here: a run uses this repo's hooks and settings without asking.</span>
    <button data-act="allow">Allow runs in ${esc(baseName($("project").value))}</button>`;
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

$("msg").addEventListener("click", async (e) => {
  if (e.target.dataset.act !== "allow" || busy) return;
  e.target.disabled = true;
  try {
    cfg.projects = (await api("/api/allow", { project_dir: $("project").value })).projects;
    note = "";
    render();
    $("prompt").focus();
  } catch (err) {
    say(`<span class="danger">Allow failed: ${esc(err.message)}</span>`);
  }
});

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
function leverButton(lv, key, label, primary) {
  return lv[key] ? "" : `<button data-act="${key}"${primary ? ' class="primary"' : ""}>${label}</button>`;
}

async function renderActions(s) {
  const sig = [s.id, s.window, s.run_live, s.stop_question, s.state, s.verdict, s.escalated,
               s.handoff_hint, s.forks.length].join("|");
  if (sig === actionsSig) return;
  actionsSig = sig;
  let lv = null;
  if (!s.run_live) lv = await api("/api/levers?session=" + encodeURIComponent(s.id)).catch(() => null);
  if (openId !== s.id || actionsSig !== sig) return;
  let html = '<div class="actions">';
  if (s.run_live) html += '<button data-act="stop">Stop</button>';
  else if (s.window) html += '<button data-act="terminal">Open in terminal</button>';
  if (!s.run_live && s.window && s.state === "interrupted" && lv && !lv.continue) {
    html += '<button data-act="resume" class="primary">Resume</button>';
  }
  if (lv) {
    html += leverButton(lv, "verify", "Verify");
    html += leverButton(lv, "handoff", "Handoff", s.handoff_hint);
    if (!lv.escalate) html += `<button data-act="escalate" class="primary">Escalate to ${esc(lv.escalate_to)}</button>`;
  }
  html += "</div>";
  if (lv && !lv.continue) {
    const answer = !!s.stop_question;
    const hint = answer ? "Answer: " + s.stop_question
      : lv.fork ? "Follow-up (runs in a window copy of this chat)" : "Follow-up";
    html += `<div class="answer"><input id="d-answer" class="m" placeholder="${esc(hint)}">
      <button data-act="continue" class="primary">${answer ? "Answer" : "Continue"}</button></div>`;
  }
  if (s.handoff_hint) {
    const why = s.ctx_tone === "red" ? "the context is large" : `${s.follow_ups} follow-ups`;
    html += `<div class="note m"><span class="warning">&#8635; hand off</span> ${why}: one task = one chat</div>`;
  }
  if (lv && lv.continue) html += `<div class="note m mut">Levers off: ${esc(lv.continue)}</div>`;
  else if (lv && lv.handoff) html += `<div class="note m mut">Handoff off: ${esc(lv.handoff)}</div>`;
  if (lv && !lv.continue && s.verdict === "FAIL" && lv.escalate) html += `<div class="note m mut">Escalate off: ${esc(lv.escalate)}</div>`;
  html += '<div id="d-msg" class="m note"></div>';
  $("d-actions").innerHTML = html;
}

function renderTabs(s) {
  if (!s.window && tab === "chat") tab = "steps";
  const tabs = [["steps", "Steps"], ["timeline", "Timeline"]].concat(s.window ? [["chat", "Chat"]] : []);
  $("d-tabs").innerHTML = tabs.map(([k, label]) =>
    `<span class="tab${k === tab ? " on" : ""}" data-tab="${k}">${label}</span>`).join("");
}

function timelineHtml(t) {
  if (!t.lanes.some((lane) => lane.spans.length)) return '<div class="empty">Nothing yet.</div>';
  const total = Math.max(1, t.end - t.start);
  const pos = (x) => (x - t.start) / total * 100;
  let html = "";
  for (const lane of t.lanes) {
    const bars = lane.spans.map(([a, b]) => `<i class="${lane.tone}" title="${clock(a)} &middot; ${dur(b - a)}"
      style="left:${pos(a).toFixed(2)}%;width:${Math.max(0.6, pos(b) - pos(a)).toFixed(2)}%"></i>`).join("");
    html += `<div class="row m tl"><span class="tl-name">${esc(lane.label)} ${verdictBadge(lane.verdict)}</span>
      <span class="tl-track">${bars}</span></div>`;
  }
  return html + `<div class="row m mut tl"><span class="tl-name"></span><span class="tl-axis">
    <span>${clock(t.start)}</span><span>${dur(t.end - t.start)}</span><span>${clock(t.end)}</span></span></div>`;
}

async function renderBody(s) {
  if (tab === "timeline") {
    const t = await api("/api/timeline?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "timeline") return;
    $("d-body").innerHTML = timelineHtml(t);
    return;
  }
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
  head += `<div class="row m mut">${s.follow_ups} follow-up(s) &middot; ${s.compactions} compaction(s)${cost}${s.stopped ? " &middot; stopped by you" : ""}</div>`;
  if (s.escalated) head += `<div class="row m mut"><span class="title">escalated ${esc(s.escalated)}</span></div>`;
  if (s.forked_from) head += `<div class="row m mut"><span class="title">window copy of <span class="link" data-open="${esc(s.forked_from)}">${esc(s.forked_from.slice(0, 8))}</span></span></div>`;
  if (s.route_reason) head += `<div class="note mut">${esc(s.route_reason)}</div>`;
  $("d-head").innerHTML = head;
  renderActions(s).catch(() => {});
  renderTabs(s);
  renderBody(s).catch(() => {});
}

async function act(name, button) {
  const s = snap.sessions.find((x) => x.id === openId);
  if (!s) return;
  button.disabled = true;
  try {
    let r = null;
    if (name === "stop") await api("/api/stop", { session: s.id });
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (name === "resume") r = await api("/api/continue", { session: s.id, text: RESUME_TEXT });
    if (name === "continue") {
      const text = $("d-answer").value.trim();
      if (!text) { button.disabled = false; return; }
      r = await api("/api/continue", { session: s.id, text });
    }
    if (["verify", "handoff", "escalate"].includes(name)) r = await api("/api/" + name, { session: s.id });
    if (r) tab = "chat";
    if (r && r.session !== s.id) { openDetail(r.session); return; }  // a window copy (fork)
    actionsSig = "";  // redraw from the next snapshot
  } catch (e) {
    button.disabled = false;
    $("d-msg").innerHTML = `<span class="danger">${esc(e.message)}</span>`;
  }
}

$("detail").addEventListener("click", (e) => {
  const t = e.target;
  if (t.dataset.tab) { tab = t.dataset.tab; render(); return; }
  if (t.dataset.open) { tab = "steps"; openDetail(t.dataset.open); return; }
  if (t.dataset.act) act(t.dataset.act, t);
});
$("detail").addEventListener("keydown", (e) => {
  if (e.target.id === "d-answer" && e.key === "Enter") act("continue", document.querySelector('[data-act="continue"]'));
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
  const opt = [...select.options].find((o) => o.value === dir);
  if (opt) { if (label.endsWith("(runs)")) opt.text = label; }  // just allowed
  else if (dir) select.add(new Option(label, dir));
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

- [ ] **Step 2: Replace `web/style.css`** with:

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
#msg button { margin-left: 6px; padding: 0 8px; font-size: 11px; }
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

/* phase 3: levers, verdicts, Timeline */
.tl-name { flex: 0 0 88px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tl-track { flex: 1; position: relative; height: 10px; border-bottom: 1px dotted var(--bd); }
.tl-track i { position: absolute; top: 1px; bottom: 1px; min-width: 2px; background: currentColor; }
.tl-axis { flex: 1; display: flex; justify-content: space-between; font-size: 11px; }
```

- [ ] **Step 3: Syntax check**

Run: `node --check web/app.js && echo ok`
Expected: `ok`. Then `py -m unittest discover -s tests` -> `Ran 78 tests ... OK`.

- [ ] **Step 4: Browser check with the fake claude** (no real model calls)

Save this as `$TEMP/cc-smoke3.py` (outside the repo). It logs two VS Code sessions (`v1`: a verifier FAIL; `v2`: 3 prompts), adds a `session-handoff` skill to the smoke project and serves on port 8773:

```python
"""Phase 3 browser check: the service with the fake claude and two logged VS Code sessions."""
import os
import subprocess
import sys
import time

from console import events, paths, server

smoke = sys.argv[1]
proj, home = os.path.join(smoke, "proj"), os.path.join(smoke, "home")
skill = os.path.join(proj, ".claude", "skills", "session-handoff")
os.makedirs(skill, exist_ok=True)
with open(os.path.join(skill, "SKILL.md"), "w", encoding="utf-8") as fh:
    fh.write("---\nname: session-handoff\ndescription: test\n---\n")
subprocess.run(["git", "init", "-q", proj])
now = time.time()
base = {"project": "proj", "project_dir": proj, "cwd": proj}
lines = [
    ("v1", -120, "UserPromptSubmit", {"prompt": "fix the add function"}),
    ("v1", -100, "SubagentStart", {"agent_id": "a1", "agent_type": "verifier"}),
    ("v1", -95, "PreToolUse", {"agent_id": "a1", "agent_type": "verifier", "tool": "Bash", "what": "py -m unittest"}),
    ("v1", -60, "SubagentStop", {"agent_id": "a1", "agent_type": "verifier", "verdict": "FAIL",
                                 "verdict_detail": "tests/test_calc.py:9 - AssertionError: 3 != 4"}),
    ("v1", -50, "Stop", {"model": "claude-sonnet-5-5", "effort": "medium", "entrypoint": "claude-vscode",
                         "context_tokens": 42000, "verdict": "FAIL",
                         "verdict_detail": "tests/test_calc.py:9 - AssertionError: 3 != 4"}),
]
for i in range(3):
    lines += [("v2", -300 + i * 60, "UserPromptSubmit", {"prompt": "tune the gauge colours"}),
              ("v2", -280 + i * 60, "Stop", {"model": "claude-opus-5-5", "effort": "high",
                                             "entrypoint": "claude-vscode", "context_tokens": 90000})]
for sid, dt, event, extra in sorted(lines, key=lambda x: x[1]):
    events.append(home, dict(base, session_id=sid, ts=now + dt, event=event, **extra))
cfg = dict(paths.DEFAULTS, projects=[proj])
httpd, hub = server.make_server(cfg, port=8773, folder=home,
                                exe=[sys.executable, os.path.abspath("tests/fake_claude.py")])
hub.user_home = smoke
hub.start()
print("http://127.0.0.1:8773/", flush=True)
httpd.serve_forever()
```

In Git Bash from the repo root:

```bash
rm -rf "$TEMP/cc-smoke3" && PYTHONPATH=. py "$TEMP/cc-smoke3.py" "$TEMP/cc-smoke3"
```

Open `http://127.0.0.1:8773/` and check, in order:
1. Home, Working: `tune the gauge colours` with a `handoff?` badge and `· 2 follow-ups`; `fix the add function` with a `FAIL` badge, the note `× FAIL tests/test_calc.py:9 - AssertionError: 3 != 4`, and the agent row `✓ Done FAIL verifier · 1 step`.
2. Open `fix the add function`: buttons `Verify`, `Handoff`, `Escalate to sonnet/high` (highlighted); the box `Follow-up (runs in a window copy of this chat)` with `Continue`; tabs `Steps`, `Timeline` (no Chat). Timeline: a `main` bar over the whole width, a `verifier FAIL` bar from about 29% to 86%, the axis `<start> 70 s <end>`.
3. Escalate: the window opens the copy on Chat: title `↳ fix the add function`, `proj · window · unrouted · sonnet/high`, `escalated sonnet/medium -> sonnet/high`, `window copy of v1`; Chat `you` starts `The checks failed: tests/test_calc.py:9 ...`. `$TEMP/cc-smoke3/home/routing-misses.md` ends with `- <today> - proj - unrouted: sonnet/medium failed (tests/test_calc.py:9 - AssertionError: 3 != 4); next time start at sonnet/high.`
4. Click `v1` in `window copy of v1`: the meta line ends `· continued in a window copy`; no Escalate button; the note `Escalate off: escalated once already (sonnet/medium -> sonnet/high)`.
5. Back in the copy: type `SLOW more work`, Enter: `▶ Running` with Stop; Stop: `○ Idle`, `stopped by you`. Handoff: the copy and `fix the add function` both move to `Done today` with `✓ Done`; the copy's Chat ends with `you /session-handoff`.
6. Open `tune the gauge colours`: `Handoff` is highlighted and the note reads `↻ hand off 2 follow-ups: one task = one chat`. No errors in the browser console.
7. Stop the server (Ctrl+C) and delete the files: `rm -rf "$TEMP/cc-smoke3" "$TEMP/cc-smoke3.py"`.

- [ ] **Step 5: Commit**

```bash
git add web/app.js web/style.css
git commit -m "feat: window levers, verdict badges, follow-up hint and Timeline tab"
```

**DONE WHEN**
- [ ] The 6 browser checks pass; 78 tests OK; `git status --short` empty.

---

### Task 7: Fred: live check

Claude cannot do this task: its auto-mode classifier refuses to let Claude start an autonomous `claude -p --permission-mode auto` run, and a fork of a real VS Code chat needs Fred's chats.

- [ ] **Step 1: Restart the window** (close it, `run.bat`): the open window still runs the phase 2 code. The hook (Task 1) is already live.

- [ ] **Step 2: A scratch project for Escalate** (so the escalated run cannot touch a real repo). In Git Bash:

```bash
mkdir -p "/d/MY DOCS/MY TOOLS/cc-levers" && git -C "/d/MY DOCS/MY TOOLS/cc-levers" init -q
```

Add `"D:\\MY DOCS\\MY TOOLS\\cc-levers"` to `"projects"` in `%USERPROFILE%\.claude\console\config.json` (keep the other keys; `Allow runs in` only offers folders a session already ran in), then restart the window again.

- [ ] **Step 3: Live checks**
1. **Verify** in `CLAUDE CONSOLE (runs)`: Run raw `say hello in one line; do not edit anything`, wait for `○ Idle`, click Verify. Expected: Chat shows `py -m unittest discover -s tests` (this repo has no verifier agent), the run ends with `VERDICT: PASS`, the row gets a `PASS` badge; the Timeline shows two `main` bars.
2. **Continue + follow-up hint** on that session: Continue `what did you just check? one line`. Expected: same row, `2 follow-up(s)`, a `handoff?` badge, Handoff highlighted with the note; Handoff itself shows `Handoff off: the session-handoff skill is not installed here` (only CONTENT MANAGER has it until phase 4).
3. **Escalate** in `cc-levers (runs)`: Run raw (default route sonnet/medium) with the three lines `Reply with exactly these three lines and nothing else:` / `VERDICT: FAIL` / `failing: demo - escalate check`. Expected: the row gets `FAIL` and `× FAIL demo - escalate check`; the detail offers `Escalate to sonnet/high`. Click it: the same row runs on sonnet/high with `escalated sonnet/medium -> sonnet/high`; `%USERPROFILE%\.claude\console\routing-misses.md` has the line for `cc-levers`; afterwards Escalate is off (`escalated once already`).
4. **Fork a VS Code chat**: pick an idle VS Code chat in a project with runs (for example a finished chat in CLAUDE CONSOLE), Continue `in one line: what was this chat about? do not edit anything`. Expected: a new `window` row `↳ <title>` opens on Chat and answers from the old context; the VS Code chat shows no new turn; the original row reads `continued in a window copy`.
5. **Handoff (optional, writes notes)**: in CONTENT MANAGER, Handoff on a finished window run or copy whose decisions should be kept. Expected: `/session-handoff` runs (PLAN.md History / memory lines appear in that repo's `git diff`), then the row turns `✓ Done`. Skip it if no session there needs a handoff.
6. **Haiku 5.5**: Prep `list the files in console/ ; do not edit anything` in CLAUDE CONSOLE, Run on its route (lookup / haiku / low). Expected: the row's model reads `claude-haiku-5-5`.
7. `~/.claude/console/hook-errors.log` and `window-errors.log` have no new lines.

- [ ] **Step 4 (Fred, optional): remove the scratch project**: delete `D:\MY DOCS\MY TOOLS\cc-levers` and its `"projects"` entry.

**DONE WHEN**
- [ ] Checks 1-4, 6 and 7 pass (5 when done); anything that differed is noted in History / Troubleshooting.

---

### Task 8: Close the phase

- [ ] **Step 1:** In `../PLAN.md`, set sub-plan 3 to "done <date>" and add a dated History line (what was built, test count, anything that differed).
- [ ] **Step 2:** In this file, tick the TODO list, add the History line, add any bug + fix to Troubleshooting.
- [ ] **Step 3:** In `../CLAUDE.md`, add under Rules: `- Levers: server.Hub.levers alone decides when Continue / Verify / Handoff / Escalate may run; a VS Code or terminal chat is only ever forked, never resumed in place.`
- [ ] **Step 4:** Commit: `git add PLAN.md CLAUDE.md plans/03-levers.md && git commit -m "docs: phase 3 done"`.

**DONE WHEN**
- [ ] `git status --short` is empty and `git log --oneline` shows one commit per task.

---

## DONE WHEN (whole plan)

- [x] `py -m unittest discover -s tests` -> 79 tests OK (78 planned + the `STOP: none` test).
- [x] Any session can be continued from the window; a VS Code / terminal chat continues as a window copy and stays untouched.
- [x] Verify gives a PASS / FAIL badge; Escalate runs once, one step up, and writes a routing-misses line that the next Prep reads.
- [x] Handoff runs `/session-handoff` and makes the session Done (fake claude only; live check 5 not tried); the follow-up hint says when.
- [x] The Timeline tab shows turns and agent runs over time.
- [x] Nothing outside `~/.claude/console/`, this repo and the run's own project folder was written by the code.

## History

- 2026-10-10 - Plan written. Fred decided: fork VS Code / terminal chats, Handoff only where the skill is installed, a Verify button, escalation ladder "effort to high, then model", keep the `haiku` alias (verified Haiku 5.5 on CLI 2.1.296). All code was run in a scratch clone first: 78 tests OK; the plan's tasks were replayed in a fresh clone (each task's tests fail as written, then pass: 64, 69, 74, 75, 78); the window flows were checked in a browser with the fake claude (Escalate fork, routing-misses line, Stop, Handoff Done, follow-up hint, Timeline; no console errors). CLI facts from real `claude -p` calls on 2.1.296 (alias resolution, `--fork-session --session-id`, a `/skill` over stream-json, the full fork command with `--name` and auto mode; about $0.003 in all).
- 2026-10-10 - Tasks 1-6 placed exactly as written (64, 69, 74, 75, 78 tests; the 6 browser checks passed with the fake claude). Task 7 live check by Fred: checks 1-4, 6, 7 passed (Escalate was run in CLAUDE CONSOLE instead of cc-levers: the escalated run edited nothing); check 5 not tried. Differed: `STOP: none` became a STOP question, fixed in `cc_events.py` (79 tests); check 2 shows no Handoff button when the skill is missing, only `Handoff off: ...`; a VS Code chat that ran `/session-handoff` itself keeps the hint (see Troubleshooting).

## Troubleshooting

- **Issue:** the lever buttons are missing and the detail says `Levers off: runs are off in this project ...`.
  **Cause:** the session's project is not in `config.json` `"projects"`.
  **Fix:** pick the project on the home view and click `Allow runs in <name>`, or add it to `config.json`.
- **Issue:** `Handoff off: the session-handoff skill is not installed here`.
  **Cause:** the skill exists only in CONTENT MANAGER until phase 4 moves it to `~/.claude/skills`.
  **Fix:** none needed; run `/session-handoff` in the chat itself, or wait for phase 4.
- **Issue:** a window copy (fork) ends at once as `‖ Interrupted` and Chat shows a `No conversation found` note.
  **Cause:** the original chat was not found from its start folder (moved or deleted, or it started outside the project).
  **Fix:** Open the original chat in VS Code instead; the copy can be left to go Stale?.
- **Issue:** no `PASS` / `FAIL` badge after Verify.
  **Cause:** the reply had no line starting with `VERDICT: PASS` or `VERDICT: FAIL` (the hook only reads that shape).
  **Fix:** Continue with `end with one line: VERDICT: PASS or VERDICT: FAIL <line>`.
- **Issue:** a window run sat in Needs you with the STOP question `none` (Task 7 check 3).
  **Cause:** the prompt asked for exact lines and the service's STOP footer asked for a STOP line; Claude obeyed both and wrote `STOP: none`, which the hook read as a question.
  **Fix:** `cc_events.py` ignores `STOP: none`, `n/a` and `-` (1 new test in `tests/test_cc_events.py`, 79 tests).
- **Issue:** a VS Code chat that already ran `/session-handoff` itself keeps the `handoff` hint and is not Done.
  **Cause:** only a Handoff run started by the window (`kind: handoff`) marks a session Done; a skill call inside the chat is just a `Skill session-handoff` step.
  **Fix:** none in phase 3; do not click Handoff there (it would fork the whole context and write the notes twice). The row goes Stale? on its own.
