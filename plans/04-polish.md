# Plan 04: Polish (phase 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Related plans: [../PLAN.md](../PLAN.md) (master), [01-watch.md](01-watch.md), [02-run.md](02-run.md), [03-levers.md](03-levers.md) (phases 1-3, done)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md) sections 1 (playbooks), 3 (D6), 6, 7.1, 12 (phase 4), 2 (Non-goals); [../CLAUDE.md](../CLAUDE.md)

**Goal:** The window warns when a session's rules files are too big, flags a turn that did heavy reading in the main chat instead of a subagent, and shows today's model mix in the status strip. A `/session-handoff` run inside a VS Code or terminal chat makes it Done like a window Handoff. The `route-model` and `session-handoff` skills and the `verifier` agent move from CONTENT MANAGER to `~/.claude/` (generic versions kept in this repo under `dotclaude/`, copied by Fred), and `route-model` reads and writes the console's `~/.claude/console/routing-misses.md`.

**Architecture:** The hook gains one event, `InstructionsLoaded`: one log line per CLAUDE.md / rules file a session loads, with its size. `State` keeps those files per session, counts the main chat's read steps per turn, notices a handoff skill run inside a chat, and adds a `mix` block (models, runs, cost) to every snapshot. The window only renders these fields (no new route). The three user-level files live in `dotclaude/` (the same layout as `~/.claude/`); a test keeps the `route-model` table equal to Prep's table and its miss line readable by `levers.read_misses`.

**Tech Stack:** unchanged: Python 3.14 standard library, pywebview 6.2.1, plain HTML/CSS/JS, `unittest`. Claude Code CLI 2.1.296.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `master`). Every path below is relative to it. Run commands from the repo root in Git Bash. Start: 79 tests OK.

---

## Fixed decisions (verified 2026-10-10 on this machine, Claude Code 2.1.296, code.claude.com docs + experiments)

1. **Rules size comes from the `InstructionsLoaded` hook** (Fred). code.claude.com/docs/en/hooks: it fires "when a `CLAUDE.md` or `.claude/rules/*.md` file is loaded into context", at session start and again for lazy loads, and is async; its input adds `file_path`, `memory_type` (`User`, `Project`, `Local`, `Managed`) and `load_reason` (`session_start`, `nested_traversal`, `path_glob_match`, `include`, `compact`). Verified with `claude -p` on 2.1.296: one event each for `~/.claude/CLAUDE.md` (`User`) and the project's `CLAUDE.md` (`Project`). The hook logs `file` (relative to the project root, else `~/...`), `lines`, `bytes`, `scope`, `load_reason`; a file it cannot read keeps only `file`. Loads inside a subagent (`agent_id`) are not the chat's and are ignored. The docs say it does not fire for an `AGENTS.md` read directly, so such a project shows no rules. Fred runs `py install_hooks.py --write` once (Task 5): only sessions started after that show rules.
2. **Rules limits** (Fred): a warning when any loaded file is over 200 lines (code.claude.com/docs/en/memory: "target under 200 lines per CLAUDE.md file") or all loaded files together are over 16 KB (1 KB = 1000 bytes, about 4K tokens). Config keys `rules_max_lines` (200) and `rules_max_kb` (16). Today CONTENT MANAGER warns (its CLAUDE.md is 149 lines but 20.8 KB); CLAUDE CONSOLE does not (2.1 KB). The row gets a `rules 21.0 KB` badge (title: the reason), the detail lists every file and the reason. Not a Needs-you state.
3. **Should delegate** (Fred): main-thread `Read`, `Grep`, `Glob`, `WebFetch`, `WebSearch` steps in the current turn (or the last one, until the next prompt) >= `delegate_after_reads` (10). Subagent steps do not count. The row gets a `delegate?` badge and the detail `⇢ delegate N reads in the main chat this turn: heavy reading belongs in a subagent (Explore)`. Not shown for Done / Stale? rows; not a Needs-you state.
4. **Model mix** (Fred): in the bottom status strip (Fred), after the counts: the shown sessions (last 24 h) and their subagent runs per model family (`claude-opus-5-5` -> `opus` with `claude_cli.model_alias`; another model keeps its own name), biggest first (`fable`, `opus`, `sonnet`, `haiku`, then others by name), e.g. `opus 1 · sonnet 2 · haiku 1`; then `runs N · $X.XX` for the window runs (each `run_started` line) and their cost (BRAINSTORM 7.1 "today's runs and equivalent cost"). Sessions or agents with no model yet are not counted.
5. **A handoff inside a chat makes it Done** (Fred), closing the phase 3 Troubleshooting item. Verified: a typed `/hello` skill in `claude -p` logs `UserPromptSubmit` with prompt `/hello` and no `PreToolUse` (docs, UserPromptExpansion: "typing `/skillname` directly bypasses `PreToolUse`"); a skill Claude calls itself logs a main-thread `PreToolUse` `Skill` step with `what` = `session-handoff` (twice in today's CONTENT MANAGER log). Either one marks the turn; its `Stop` makes the session Done (`handed_off`), `StopFailure` clears the mark, a new prompt reopens the session (as for a window Handoff). A `Skill` call inside a subagent does not count. No hook change (no `UserPromptExpansion` event needed).
6. **The three files move through this repo** (Fred). Generic versions live in `dotclaude/skills/route-model/SKILL.md`, `dotclaude/skills/session-handoff/SKILL.md`, `dotclaude/agents/verifier.md` (the layout of `~/.claude/`). Claude does not write `~/.claude/`: code.claude.com/docs/en/permission-modes lists `.claude` among the protected directories ("Writes to a small set of paths are never auto-approved"), and CLAUDE.md allows code to write only `~/.claude/console/`. Fred copies them in this order, each checked before the next (Fred): `session-handoff` (Handoff in every project), `verifier` (Verify uses an agent everywhere), `route-model` (Task 5).
7. **CONTENT MANAGER after the move** (Fred): its `.claude/skills/route-model` and `.claude/skills/session-handoff` are deleted (untracked there; code.claude.com/docs/en/skills: "Enterprise over personal, and personal over project", so they would be dead copies). Its `.claude/agents/verifier.md` stays as an override (code.claude.com/docs/en/sub-agents: `.claude/agents/` has priority 3, `~/.claude/agents/` priority 4; it runs `npm run check` for `web/src`). No restart: both docs pages say Claude Code watches `~/.claude/skills/` and `~/.claude/agents/` (both folders exist on this machine).
8. **route-model uses the console's misses file** (Fred). It reads the project's lines of `~/.claude/console/routing-misses.md` and, after an escalation in a chat, appends one line in the console's format (`- <date> - <project> - <type>: <from> failed (<why>); next time start at <to>.`), so Prep reads chat misses too. That write is to a protected path: Fred approves it once per session (auto mode: the classifier decides); escalations are rare. Its route table is Prep's table (`console/prep_prompt.md`) plus a "who does it" column, and its escalation step is `levers.escalate_step`'s; `tests/test_dotclaude.py` checks the table and the miss line. It also carries the `STOP: <question>` line (BRAINSTORM phase 2 asked for it). Verified live on a scratch repo with the skill as a project skill: `/route-model` on haiku read `~/.claude/console/routing-misses.md` and printed `Route: mechanical, low effort, cavecrew-builder on sonnet`, which the hook logged as the route.
9. **The generic verifier** takes its checks from the project's CLAUDE.md (Commands / Testing), else `py -m unittest discover -s tests` or a `package.json` `check` / `test` script, and runs all checks when nothing is uncommitted (Verify often follows a committed run). Verified live on a scratch repo with a failing test: it reported `VERDICT: FAIL` with the failing line, and the hook logged the verdict on SubagentStop and Stop.
10. **Handoff off note** now says how to fix it: `the session-handoff skill is not installed here: copy dotclaude/skills/session-handoff to ~/.claude/skills`.
11. **Hook time**: about 130 ms per event in today's runs against 100 ms for a bare `py -c pass` on this machine (it was 75 ms in phase 1 on a quieter machine); the hook is async, so no session waits for it.
12. **Not in this plan:** the Jarvis widget link (BRAINSTORM 12 says "later"); `MEMORY.md` size (auto memory is not reported by `InstructionsLoaded`, and the docs already cap it at 200 lines or 25 KB).
13. **Not verified by Claude:** the copies into `~/.claude` (Fred's), the VS Code flows, and the protected-path prompt when `route-model` appends a miss. All are in Task 5.

## Code map

```text
cc_events.py        + rules_file(): InstructionsLoaded lines carry file, lines, bytes, scope, load_reason
install_hooks.py    + InstructionsLoaded in EVENTS
console/
  state.py          + rules, reads, chat_handoff, runs per session; rules_warn(), mix(); family()
  paths.py          + rules_max_lines, rules_max_kb, delegate_after_reads
  server.py         Handoff off note names the copy step
web/app.js          rules badge + detail list, delegate badge + note, model mix in the strip
dotclaude/          NEW  user-level files Fred copies to ~/.claude
  skills/route-model/SKILL.md
  skills/session-handoff/SKILL.md
  agents/verifier.md
tests/
  test_dotclaude.py NEW  frontmatter, route table = Prep's, route and miss lines parse
  test_cc_events.py  test_state.py   extended
```

Dependencies point one way: `state -> claude_cli, redact` (new: `claude_cli.model_alias`, `claude_cli.MODELS`); `tests/test_dotclaude -> cc_events, claude_cli, levers, prep`.

## Files to modify

`cc_events.py`, `install_hooks.py`, `console/state.py`, `console/paths.py`, `console/server.py`, `web/app.js`, `tests/test_cc_events.py`, `tests/test_state.py`, `PLAN.md`, `CLAUDE.md`, this file. New: `dotclaude/skills/route-model/SKILL.md`, `dotclaude/skills/session-handoff/SKILL.md`, `dotclaude/agents/verifier.md`, `tests/test_dotclaude.py`. Unchanged: `web/index.html`, `web/style.css` (no new class), `console/levers.py`, `console/runs.py`, `console/prep.py`, `tests/fake_claude.py`.

## TODO

- [x] Task 1: hook logs loaded rules files
- [x] Task 2: state (rules, delegate, chat handoff, model mix)
- [x] Task 3: window
- [x] Task 4: dotclaude skills and agent
- [x] Task 5: Fred: hooks, skill moves, live check
- [x] Task 6: close the phase

---

### Task 1: Hook logs loaded rules files

The hook runs inside every Claude Code session as soon as the file is saved: keep it raising nothing (`rules_file()` returns what it could read). The new event only fires once Fred re-runs the installer (Task 5).

**Files:**
- Modify: `cc_events.py`, `install_hooks.py` (full files below)
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

    def test_stop_none_is_no_question(self):
        for answer in ("none", "None.", "n/a", "-"):
            rec = cc_events.build_record(self.base("Stop", last_assistant_message=f"Done.\nSTOP: {answer}"))
            self.assertNotIn("stop_question", rec, answer)

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

    def test_instructions_loaded_measures_the_file(self):
        rules = self.repo / "CLAUDE.md"
        rules.write_bytes(b"# Rules\n" + b"- one rule\n" * 4 + b"last line")
        rec = cc_events.build_record(self.base("InstructionsLoaded", file_path=str(rules),
                                               memory_type="Project", load_reason="session_start"))
        self.assertEqual((rec["file"], rec["lines"], rec["bytes"], rec["scope"], rec["load_reason"]),
                         ("CLAUDE.md", 6, 61, "Project", "session_start"))
        mine = Path(self.tmp.name) / ".claude" / "CLAUDE.md"
        mine.parent.mkdir()
        mine.write_bytes(b"one\ntwo\n")
        with mock.patch.object(Path, "home", return_value=Path(self.tmp.name)):
            rec = cc_events.build_record(self.base("InstructionsLoaded", file_path=str(mine), memory_type="User"))
        self.assertEqual((rec["file"], rec["lines"], rec["bytes"]), ("~/.claude/CLAUDE.md", 2, 8))
        rec = cc_events.build_record(self.base("InstructionsLoaded", file_path=str(self.repo / "gone.md")))
        self.assertEqual(rec["file"], "gone.md")
        self.assertNotIn("lines", rec)

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
Expected: ERROR in `test_instructions_loaded_measures_the_file`, `KeyError: 'file'`.

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
RULES_READ_MAX = 4 * 1024 * 1024  # a rules file bigger than this is counted by size only
_ROUTE = re.compile(r"^[\s`*>\-]*Route:\s*(.+?)[\s`*]*$", re.M)
_STOP = re.compile(r"^[\s`*>\-]*STOP:\s*(.+?)[\s`*]*$", re.M)
# A model that obeys the STOP footer with nothing to ask writes `STOP: none`: not a question.
_NO_QUESTION = {"none", "n/a", "-", ""}
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


def rules_file(path, root) -> dict:
    """A loaded CLAUDE.md / rules file: a short name (inside the project, or ~/...), lines, bytes."""
    if not path:
        return {}
    p = Path(path)
    name = p.as_posix()
    for base, prefix in ((root, ""), (Path.home(), "~/")):
        if base and p.is_relative_to(base):
            name = prefix + p.relative_to(base).as_posix()
            break
    out = {"file": name}
    try:
        out["bytes"] = p.stat().st_size
        with open(p, "rb") as fh:
            data = fh.read(RULES_READ_MAX)
    except OSError:
        return out
    out["lines"] = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
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
        if question.rstrip(".").lower() not in _NO_QUESTION:
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
    elif event == "InstructionsLoaded":
        rec.update(rules_file(data.get("file_path"), root))
        rec["scope"] = data.get("memory_type")
        rec["load_reason"] = data.get("load_reason")
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

- [ ] **Step 4: Replace `install_hooks.py`** with:

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
          "PermissionDenied", "Stop", "StopFailure", "PostCompact", "SessionEnd",
          "InstructionsLoaded"]
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

- [ ] **Step 5: Run the tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 80 tests ... OK`.

- [ ] **Step 6: Commit**

```bash
git add cc_events.py install_hooks.py tests/test_cc_events.py
git commit -m "feat: hook logs the rules files a session loads (InstructionsLoaded)"
```

**DONE WHEN**
- [ ] 80 tests OK; `py install_hooks.py` (dry run, writes nothing) lists `InstructionsLoaded`; `git status --short` empty.

---

### Task 2: State

**Files:**
- Modify: `console/state.py`, `console/paths.py` (full files below)
- Test: `tests/test_state.py` (full file below; 4 new tests)

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

    def test_rules_size_warning(self):
        self.feed(ev("InstructionsLoaded", T0, file="~/.claude/CLAUDE.md", scope="User", lines=3, bytes=229,
                     load_reason="session_start"),
                  ev("InstructionsLoaded", T0, file="CLAUDE.md", scope="Project", lines=149, bytes=20791),
                  ev("InstructionsLoaded", T0 + 1, agent_id="a1", file="web/CLAUDE.md", lines=900, bytes=1),
                  ev("UserPromptSubmit", T0 + 2, prompt="fix it"))
        row = self.row(T0 + 3)
        self.assertEqual([r["file"] for r in row["rules"]], ["~/.claude/CLAUDE.md", "CLAUDE.md"])  # not the agent's
        self.assertEqual((row["rules_bytes"], row["rules_warn"]), (21020, "21.0 KB in all (over 16 KB)"))
        self.feed(ev("InstructionsLoaded", T0 + 4, file="CLAUDE.md", scope="Project", lines=230, bytes=9000),
                  ev("InstructionsLoaded", T0 + 4, sid="small", file="CLAUDE.md", lines=33, bytes=2085))
        self.assertEqual(self.row(T0 + 5)["rules_warn"], "CLAUDE.md 230 lines (over 200)")
        self.assertEqual(self.row(T0 + 5, "small")["rules_warn"], "")

    def test_should_delegate_flag(self):
        self.feed(ev("UserPromptSubmit", T0))
        for i in range(9):
            self.feed(ev("PreToolUse", T0 + 1 + i, tool="Read", what=f"f{i}.py"))
        self.feed(ev("PreToolUse", T0 + 10, agent_id="a1", agent_type="Explore", tool="Read"),
                  ev("PreToolUse", T0 + 11, tool="Edit", what="f1.py"))
        self.assertEqual((self.row(T0 + 12)["reads"], self.row(T0 + 12)["delegate_hint"]), (9, False))
        self.feed(ev("PreToolUse", T0 + 13, tool="Grep", what="def x"), ev("Stop", T0 + 14))
        self.assertEqual((self.row(T0 + 15)["reads"], self.row(T0 + 15)["delegate_hint"]), (10, True))
        self.feed(ev("UserPromptSubmit", T0 + 16))
        self.assertEqual((self.row(T0 + 17)["reads"], self.row(T0 + 17)["delegate_hint"]), (0, False))

    def test_handoff_typed_or_called_in_a_chat(self):
        self.feed(ev("UserPromptSubmit", T0, sid="typed", prompt="/session-handoff"),
                  ev("Stop", T0 + 5, sid="typed"),
                  ev("UserPromptSubmit", T0, sid="called", prompt="its time to handoff, give me the prompt"),
                  ev("PreToolUse", T0 + 1, sid="called", tool="Skill", what="session-handoff"),
                  ev("UserPromptSubmit", T0, sid="failed", prompt="/session-handoff"),
                  ev("StopFailure", T0 + 2, sid="failed", error="rate_limit"),
                  ev("UserPromptSubmit", T0, sid="agent", prompt="go"),
                  ev("PreToolUse", T0 + 1, sid="agent", agent_id="a1", tool="Skill", what="session-handoff"),
                  ev("Stop", T0 + 2, sid="agent"))
        self.assertEqual(self.row(T0 + 6, "typed")["state"], "done")
        self.assertEqual(self.row(T0 + 2, "called")["state"], "running")  # Done only once the turn ends
        self.feed(ev("Stop", T0 + 3, sid="called"))
        self.assertEqual((self.row(T0 + 4, "called")["state"], self.row(T0 + 4, "called")["group"]), ("done", "done"))
        self.assertEqual(self.row(T0 + 3, "failed")["state"], "failed")
        self.assertEqual(self.row(T0 + 3, "agent")["state"], "idle")
        self.feed(ev("UserPromptSubmit", T0 + 7, sid="typed", prompt="one more thing"), ev("Stop", T0 + 8, sid="typed"))
        self.assertEqual(self.row(T0 + 9, "typed")["state"], "idle")  # a new prompt reopens it

    def test_model_mix(self):
        self.feed(ev("Stop", T0, sid="a", model="claude-opus-5-5"),
                  ev("SubagentStop", T0 + 1, sid="a", agent_id="x1", model="claude-haiku-5-5"),
                  ev("SubagentStop", T0 + 2, sid="a", agent_id="x2", model="claude-haiku-5-5"),
                  ev("SubagentStart", T0 + 3, sid="a", agent_id="x3"),
                  ev("run_started", T0 + 4, sid="b", model="sonnet"),
                  ev("run_ended", T0 + 5, sid="b", cost=0.25, subtype="success"),
                  ev("run_started", T0 + 6, sid="b"),
                  ev("run_ended", T0 + 7, sid="b", cost=0.5, subtype="success"),
                  ev("Stop", T0 + 8, sid="c", model="gpt-5"),
                  ev("Stop", T0 - 90000, sid="old", model="claude-fable-5-1"))
        self.assertEqual(self.state.snapshot(T0 + 9)["mix"],
                         {"models": [["opus", 1], ["sonnet", 1], ["haiku", 2], ["gpt-5", 1]], "runs": 2, "cost": 0.75})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_state`
Expected: `FAILED (failures=1, errors=3)`: `KeyError: 'mix'`, `KeyError: 'rules'`, `KeyError: 'reads'`, and `AssertionError: 'idle' != 'done'` in `test_handoff_typed_or_called_in_a_chat`.

- [ ] **Step 3: Replace `console/paths.py`** with:

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
    "rules_max_lines": 200,
    "rules_max_kb": 16,
    "delegate_after_reads": 10,
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

from . import claude_cli, redact

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
READ_TOOLS = {"Read", "Grep", "Glob", "WebFetch", "WebSearch"}  # main-chat reads: "should delegate"
HANDOFF_SKILL = "session-handoff"
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
    rules: dict = field(default_factory=dict)  # file -> {scope, lines, bytes}: CLAUDE.md / rules loaded
    reads: int = 0             # main-chat Read / Grep / Glob / WebFetch / WebSearch steps this turn
    chat_handoff: bool = False  # this turn ran /session-handoff inside the chat: its Stop makes it Done
    runs: int = 0              # window runs (run_started lines), for the model-mix strip


def family(model: str) -> str:
    """claude-sonnet-5-5 -> sonnet; another model keeps its own name."""
    return claude_cli.model_alias(model) or str(model or "")


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
            s.reads = 0
            words = rec.get("prompt", "").split()
            s.chat_handoff = bool(words) and words[0] == "/" + HANDOFF_SKILL  # typed: no Skill step
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
                s.reads += tool in READ_TOOLS
                if tool == "Skill" and what.split(":")[-1] == HANDOFF_SKILL:  # Claude ran the skill itself
                    s.chat_handoff = True
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
            if s.chat_handoff:  # /session-handoff ran in this turn: Done, like a window Handoff
                s.handed_off, s.chat_handoff = True, False
        elif event == "StopFailure":
            s.in_turn = False
            s.chat_handoff = False
            self._turn_close(s, ts)
            s.failed = {"error": rec.get("error", "unknown"), "details": rec.get("error_details", "")}
        elif event == "InstructionsLoaded" and not agent and rec.get("file"):
            s.rules[rec["file"]] = {"scope": rec.get("scope", ""), "lines": int(rec.get("lines") or 0),
                                    "bytes": int(rec.get("bytes") or 0)}
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
            s.runs += 1
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
                "rules": [dict(r, file=f) for f, r in s.rules.items()],
                "rules_bytes": sum(r["bytes"] for r in s.rules.values()),
                "rules_warn": self.rules_warn(s.rules),
                "reads": s.reads,
                "delegate_hint": state not in DONE and s.reads >= self.cfg["delegate_after_reads"],
                "agents": [self._agent_row(a, s) for a in
                           sorted(s.agents.values(), key=lambda a: a.started_ts)],
            })
        return {
            "now": now,
            "sessions": rows,
            "writers": [{"project_dir": p, "sessions": ids} for p, ids in sorted(writers.items())],
            "counts": {g: sum(1 for r in rows if r["group"] == g) for g in ("needs", "working", "done")},
            "mix": self.mix([self.sessions[r["id"]] for r in rows]),
        }

    def rules_warn(self, rules: dict) -> str:
        """Why the loaded rules are too big ("" = fine): a file over rules_max_lines, or all of
        them together over rules_max_kb (docs: "target under 200 lines per CLAUDE.md file")."""
        max_lines, max_kb = self.cfg["rules_max_lines"], self.cfg["rules_max_kb"]
        out = [f"{name} {r['lines']} lines (over {max_lines})"
               for name, r in rules.items() if r["lines"] > max_lines]
        total = sum(r["bytes"] for r in rules.values()) / 1000
        if total > max_kb:
            out.append(f"{total:.1f} KB in all (over {max_kb} KB)")
        return "; ".join(out)

    def mix(self, sessions: list) -> dict:
        """The model-mix strip: shown sessions and agent runs per model family, window runs, cost."""
        counts = {}
        for s in sessions:
            for model in [s.model] + [a.model for a in s.agents.values()]:
                if model:
                    counts[family(model)] = counts.get(family(model), 0) + 1
        rank = {m: i for i, m in enumerate(claude_cli.MODELS[::-1])}  # biggest first, then others by name
        models = sorted(counts.items(), key=lambda kv: (rank.get(kv[0], len(rank)), kv[0]))
        return {"models": [list(kv) for kv in models], "runs": sum(s.runs for s in sessions),
                "cost": round(sum(s.cost for s in sessions), 4)}

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

- [ ] **Step 5: Run the tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 84 tests ... OK`.

- [ ] **Step 6: Commit**

```bash
git add console/state.py console/paths.py tests/test_state.py
git commit -m "feat: state keeps loaded rules, main-chat reads, in-chat handoffs and the model mix"
```

**DONE WHEN**
- [ ] 84 tests OK; `git status --short` empty.

---

### Task 3: Window

**Files:**
- Modify: `web/app.js` (full file below), `console/server.py` (one edit below). `web/index.html` and `web/style.css` are unchanged.

- [ ] **Step 1: Replace `web/app.js`** with:

```javascript
// Claude Console window: renders /api/stream snapshots; phase 2 adds the prompt box, Prep card and runs;
// phase 3 the levers (Continue, Verify, Handoff, Escalate), verdicts and the Timeline tab;
// phase 4 the rules-size warning, the should-delegate flag and the model-mix strip.
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
function kb(bytes) { return (bytes / 1000).toFixed(1) + " KB"; }
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
    ${s.rules_warn ? `<span class="badge warning" title="${esc(s.rules_warn)}">rules ${kb(s.rules_bytes)}</span>` : ""}
    ${s.delegate_hint ? '<span class="badge warning">delegate?</span>' : ""}
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
  if (s.rules.length) {
    const files = s.rules.map((r) => `${esc(r.file)} ${r.lines} lines ${kb(r.bytes)}${r.scope ? " (" + esc(r.scope.toLowerCase()) + ")" : ""}`);
    head += `<div class="note m mut">rules: ${files.join(" &middot; ")}</div>`;
  }
  if (s.rules_warn) head += `<div class="note m"><span class="warning">&#9651; rules</span> ${esc(s.rules_warn)}: keep CLAUDE.md short; move procedures to skills and narrow rules to path rules</div>`;
  if (s.delegate_hint) head += `<div class="note m"><span class="warning">&#8674; delegate</span> ${s.reads} reads in the main chat this turn: heavy reading belongs in a subagent (Explore)</div>`;
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
  const mix = snap.mix;
  if (mix.models.length) html += `<span>${mix.models.map(([m, n]) => esc(m) + " " + n).join(" &middot; ")}</span>`;
  if (mix.runs) html += `<span>runs ${mix.runs} &middot; $${Number(mix.cost).toFixed(2)}</span>`;
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

- [ ] **Step 2: Edit `console/server.py`** (in `Hub.levers`). Replace:

```python
        handoff = base or ("" if levers.handoff_ready(s["project_dir"], self.user_home) else
                           "the session-handoff skill is not installed here (phase 4 moves it to ~/.claude)")
```

with:

```python
        handoff = base or ("" if levers.handoff_ready(s["project_dir"], self.user_home) else
                           "the session-handoff skill is not installed here: copy "
                           "dotclaude/skills/session-handoff to ~/.claude/skills")
```

- [ ] **Step 3: Syntax check**

Run: `node --check web/app.js && echo ok`
Expected: `ok`. Then `py -m unittest discover -s tests` -> `Ran 84 tests ... OK` (`test_levers_fork_a_vscode_session` still finds `session-handoff skill` in the note).

- [ ] **Step 4: Browser check with the fake claude** (no real model calls)

Save this as `$TEMP/cc-smoke4.py` (outside the repo). It logs two VS Code sessions (`v1`: CONTENT MANAGER-sized rules, 12 main-chat reads, a haiku Explore agent, opus; `v2`: Claude ran `session-handoff` in the chat) and serves on port 8774:

```python
"""Phase 4 browser check: the service with the fake claude and two logged VS Code sessions."""
import os
import subprocess
import sys
import time

from console import events, paths, server

smoke = sys.argv[1]
proj, home = os.path.join(smoke, "proj"), os.path.join(smoke, "home")
os.makedirs(proj, exist_ok=True)
subprocess.run(["git", "init", "-q", proj])
now = time.time()
base = {"project": "proj", "project_dir": proj, "cwd": proj}
lines = [
    ("v1", -300, "InstructionsLoaded", {"file": "~/.claude/CLAUDE.md", "scope": "User", "lines": 3, "bytes": 229,
                                        "load_reason": "session_start"}),
    ("v1", -300, "InstructionsLoaded", {"file": "CLAUDE.md", "scope": "Project", "lines": 149, "bytes": 20791,
                                        "load_reason": "session_start"}),
    ("v1", -290, "UserPromptSubmit", {"prompt": "split the importer"}),
    ("v1", -200, "SubagentStart", {"agent_id": "a1", "agent_type": "Explore"}),
    ("v1", -150, "SubagentStop", {"agent_id": "a1", "agent_type": "Explore", "model": "claude-haiku-5-5",
                                  "context_tokens": 30000}),
    ("v1", -60, "Stop", {"model": "claude-opus-5-5", "effort": "high", "entrypoint": "claude-vscode",
                         "context_tokens": 80000}),
    ("v2", -250, "InstructionsLoaded", {"file": "CLAUDE.md", "scope": "Project", "lines": 33, "bytes": 2085,
                                        "load_reason": "session_start"}),
    ("v2", -240, "UserPromptSubmit", {"prompt": "tune the strip"}),
    ("v2", -200, "Stop", {"model": "claude-sonnet-5-5", "effort": "medium", "entrypoint": "claude-vscode",
                          "context_tokens": 40000}),
    ("v2", -100, "UserPromptSubmit", {"prompt": "its time to handoff, give me the prompt"}),
    ("v2", -95, "PreToolUse", {"tool": "Skill", "what": "session-handoff"}),
    ("v2", -80, "Stop", {"model": "claude-sonnet-5-5", "entrypoint": "claude-vscode", "context_tokens": 45000}),
]
for i in range(12):
    lines.append(("v1", -280 + i * 5, "PreToolUse", {"tool": "Read", "what": f"importer/part{i}.py"}))
for sid, dt, event, extra in sorted(lines, key=lambda x: x[1]):
    events.append(home, dict(base, session_id=sid, ts=now + dt, event=event, **extra))
cfg = dict(paths.DEFAULTS, projects=[proj])
httpd, hub = server.make_server(cfg, port=8774, folder=home,
                                exe=[sys.executable, os.path.abspath("tests/fake_claude.py")])
hub.user_home = smoke
hub.start()
print("http://127.0.0.1:8774/", flush=True)
httpd.serve_forever()
```

In Git Bash from the repo root:

```bash
rm -rf "$TEMP/cc-smoke4" && PYTHONPATH=. py "$TEMP/cc-smoke4.py" "$TEMP/cc-smoke4"
```

Open `http://127.0.0.1:8774/` and check, in order:
1. Home, Working: `split the importer` with the badges `rules 21.0 KB` (hover: `21.0 KB in all (over 16 KB)`) and `delegate?`, and the agent row `✓ Done Explore · claude-haiku-5-5`. Done today: `✓ Done tune the strip` (Claude's own `Skill session-handoff`, no button clicked). The strip: `opus 1 · sonnet 1 · haiku 1`, no `runs`.
2. Open `split the importer`: the notes `rules: ~/.claude/CLAUDE.md 3 lines 0.2 KB (user) · CLAUDE.md 149 lines 20.8 KB (project)`, `△ rules 21.0 KB in all (over 16 KB): keep CLAUDE.md short; ...` and `⇢ delegate 12 reads in the main chat this turn: ...`; the actions show `Verify` and `Continue` and the note `Handoff off: the session-handoff skill is not installed here: copy dotclaude/skills/session-handoff to ~/.claude/skills`.
3. Back home, pick `proj (runs)` in the project list, type `say hello`, Ctrl+Enter: the run opens on Chat and ends `○ Idle`; the strip now reads `opus 1 · sonnet 2 · haiku 1` and `runs 1 · $0.01`.
4. No errors in the browser console (reload once to check the page load too).
5. Stop the server (Ctrl+C) and delete the files: `rm -rf "$TEMP/cc-smoke4" "$TEMP/cc-smoke4.py"`.

- [ ] **Step 5: Commit**

```bash
git add web/app.js console/server.py
git commit -m "feat: window shows the rules-size warning, the should-delegate flag and the model mix"
```

**DONE WHEN**
- [ ] The 4 browser checks pass; 84 tests OK; `git status --short` empty.

---

### Task 4: dotclaude skills and agent

Generic versions of the three CONTENT MANAGER files (no CONTENT MANAGER paths left), for every project. Claude writes them in this repo only; Fred copies them to `~/.claude` in Task 5.

**Files:**
- Create: `dotclaude/skills/session-handoff/SKILL.md`, `dotclaude/agents/verifier.md`, `dotclaude/skills/route-model/SKILL.md`
- Test: `tests/test_dotclaude.py` (new, 3 tests)

- [ ] **Step 1: Create `tests/test_dotclaude.py`** with:

```python
"""The user-level skills and agent Fred copies to ~/.claude: they must agree with the console's code."""
import re
import tempfile
import time
import unittest
from pathlib import Path

import cc_events
from console import claude_cli, levers, prep

ROOT = Path(__file__).resolve().parent.parent
DOT = ROOT / "dotclaude"
FILES = {"route-model": DOT / "skills" / "route-model" / "SKILL.md",
         "session-handoff": DOT / "skills" / "session-handoff" / "SKILL.md",
         "verifier": DOT / "agents" / "verifier.md"}


def front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(line.split(": ", 1) for line in m.group(1).splitlines()) if m else {}


def table(text: str) -> dict:
    """type -> (model, effort) from a route table whose cells are type | when | model | effort | ..."""
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] in prep.TYPES:
            rows[cells[0]] = (cells[2], cells[3])
    return rows


class DotClaudeTest(unittest.TestCase):
    def test_frontmatter(self):
        for name, path in FILES.items():
            meta = front(path)
            self.assertEqual(meta.get("name"), name, path)
            self.assertTrue(meta.get("description", "").startswith("Use "), path)
            self.assertNotIn(chr(0x2014), path.read_text(encoding="utf-8"), path)  # no em-dashes in prose
        agent = front(FILES["verifier"])
        self.assertEqual((agent["tools"], agent["model"], agent["effort"]), ("Bash, Read, Grep, Glob", "sonnet", "low"))

    def test_route_table_matches_prep(self):
        skill = table(FILES["route-model"].read_text(encoding="utf-8"))
        self.assertEqual(skill, table(prep.PROMPT_FILE.read_text(encoding="utf-8")))
        self.assertEqual(sorted(skill), sorted(prep.TYPES))
        for model, effort in skill.values():
            self.assertIn(model, claude_cli.MODELS)
            self.assertIn(effort, claude_cli.EFFORTS)

    def test_route_and_miss_lines_parse(self):
        text = FILES["route-model"].read_text(encoding="utf-8")
        self.assertIn("~/.claude/console/routing-misses.md", text)
        route = re.search(r"`(Route: [^`]+)`", text).group(1)
        self.assertEqual(cc_events.last_match(cc_events._ROUTE, route), "mechanical, low effort, cavecrew-builder on sonnet")
        example = next(line for line in text.splitlines() if re.match(r"- \d{4}-\d\d-\d\d - ", line))
        with tempfile.TemporaryDirectory() as tmp:
            levers.add_miss(Path(tmp), example)
            self.assertEqual(levers.read_misses(Path(tmp), "CLAUDE CONSOLE"), [example])
        day = time.mktime((2026, 10, 10, 12, 0, 0, 0, 0, -1))
        self.assertEqual(levers.miss_line("CLAUDE CONSOLE", "normal", "sonnet/medium", "sonnet/high",
                                          "tests/test_state.py:40 - KeyError: 'rules'", day), example)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to see it fail**

Run: `py -m unittest tests.test_dotclaude`
Expected: `FAILED (errors=3)`, `FileNotFoundError: ... dotclaude\skills\route-model\SKILL.md`.

- [ ] **Step 3: Create `dotclaude/skills/session-handoff/SKILL.md`** with:

```markdown
---
name: session-handoff
description: Use when a task has landed, the chat has run long, or the user corrected the same point twice, before running /clear or /compact. Writes the decisions and the next step as one-liners where the next chat will read them, then hands the user a restart line. Stops before the next task starts.
---

# Session handoff

Turns the useful part of a long chat into a few one-line records, so a fresh chat can start clean without losing its decisions. It writes the records and a starter prompt, then stops; the user runs `/clear` (Claude cannot run slash commands). In Claude Console the turn that runs this skill marks the session Done.

## Read first

- The project's `CLAUDE.md`, then its plan: `PLAN.md` at the repo root, or `projects/<name>/PLAN.md` in a repo with several projects. Its `## History` section is the decision log.
- The auto-memory index `MEMORY.md` and any memory file it lists for the same project.
- `git status --short` and `git log --oneline -5` for what actually changed.

## Steps

1. Check inputs: name the task of this chat in one line. If no task was finished or decided, say so and stop (nothing to hand off).
2. List the decisions made in this chat. One line each: what + why. Drop anything the code or git history already records.
3. List what is still open: the next step, and any check that has not been run (tests, build, GUI check).
4. Write each decision where it belongs:
   - project decision or progress: append one dated line to `## History` in the project's `PLAN.md`, in the format already used there (for example `- 2026-10-10 - <what>; <why>.`); a project without a `PLAN.md` gets none, use memory instead;
   - how the user wants work done, or a fact for every future chat: update or add an auto-memory file (check for an existing one first, then the `MEMORY.md` pointer);
   - a rule for every task in this repo: propose the CLAUDE.md line to the user, do not write it.
5. Remove or correct any older line this chat proved wrong (notes spread mistakes too).
6. Print a starter prompt for the next chat, at most 5 lines: the project, the files to read first, the next step, the check that proves it is done.
7. Tell the user the exit:
   - default: `/clear <short-name>` (the name labels this chat in `/resume`), then paste the starter prompt;
   - only if the task must continue in this chat: `/compact focus on <the open step and the decisions above>`.

## Done looks like

- Every decision from step 2 appears in exactly one place (PLAN.md History, a memory file, or a proposed CLAUDE.md line shown to the user).
- `git diff` shows only one-line additions or corrections to History / memory files, no code changes.
- The starter prompt names a file to read and a check to run.

## Never

- Never write notes into folders the project's CLAUDE.md marks as generated, exported or wiped, and never create a new decisions file without the user asking.
- Never paste a chat summary into memory or PLAN.md; one line per decision, or nothing.
- Never edit CLAUDE.md in this skill; propose the line and let the user decide.

## Sources

CONTENT MANAGER `data/notes/context-playbook.md` (levers 1, 3 and 5; "Lever details"), source page by @donimas: famous-mandarin-287.notion.site/Context-Playbook-3f11be55d9b881e7a6f6eee5d74b196d. `/clear [name]` and `/compact [instructions]` checked against code.claude.com/docs/en/commands on 2026-10-10. Moved from CONTENT MANAGER to `~/.claude/skills` by Claude Console plan 04.
```

- [ ] **Step 4: Create `dotclaude/agents/verifier.md`** with:

````markdown
---
name: verifier
description: Use after a code change in any project to run the checks that fit the changed files and report PASS or FAIL with the shortest failing lines. Runs checks only; edits nothing. A project's own .claude/agents/verifier.md replaces this one.
tools: Bash, Read, Grep, Glob
model: sonnet
effort: low
maxTurns: 15
---

# Verifier

You run the project's checks on the current working tree and report. You never fix anything; the parent session decides what to do with a FAIL.

## Steps

1. Find the checks: read the project's `CLAUDE.md` (its Commands or Testing section names the test and check commands). If it names none, use what the repo has:
   - Python with a `tests/` folder: `py -m unittest discover -s tests` (or `pytest` when the repo configures it);
   - a `package.json` with a `check` or `test` script: `npm run check` / `npm test` in that folder.
2. `git status --short` and `git diff --name-only HEAD` list the changed files. Run the checks that cover them; if nothing changed (the work may be committed already), run all the checks from step 1.
3. Run each check once. Do not retry a failing check.
4. Report in this shape, nothing else:

```
VERDICT: PASS | FAIL
checks: <command> -> <ok | N failed>
failing: <file:line relative to the repo root, or test name> - <shortest decisive error line>   (one per failure, max 10)
not covered: <what these checks cannot see, e.g. GUI behaviour, a live network call>
```

If no check exists at all, report `VERDICT: FAIL no checks found` and say what you looked for.

## Never

- Never edit, create or delete files.
- Never start the app, open a database writable, or touch the data folders the project's CLAUDE.md protects.
- Never paste full logs; quote the shortest line that shows the failure.
````

- [ ] **Step 5: Create `dotclaude/skills/route-model/SKILL.md`** with:

````markdown
---
name: route-model
description: Use at the start of a coding task in Claude Code (or when the user asks which model or effort to use) to pick effort first, then the model tier, by task type and risk; then verify, escalate once on FAIL, and log the miss. Stops after the verify step reports PASS or after one escalation.
---

# Route model

Picks the cheapest route that should solve the task: effort level first, model tier second, delegating mechanical or read-heavy parts to subagents with a fixed model. It checks the result with code, escalates one step at most, and records every miss so the next route is better. Claude Console's Prep step uses the same table and the same misses file.

## Read first

- The task as the user wrote it, and the project's plan if one exists (a zero-decision plan usually runs fine at lower effort).
- The project's `CLAUDE.md`: what it calls risky (database, threading, installer, user data) decides the `risky` row.
- `~/.claude/console/routing-misses.md`, the lines tagged with this project (` - <project folder name> - `). Past misses override the table.
- The `verifier` agent (`.claude/agents/verifier.md` in the project, else `~/.claude/agents/verifier.md`).

## Route table

| type | when | model | effort | who does it |
|---|---|---|---|---|
| mechanical | rename, copy, docs text, a 1-2 file edit with a clear spec | sonnet | low | `cavecrew-builder` subagent with `model: sonnet` |
| lookup | find, explain, summarise, read many files, no edits | haiku | low | `cavecrew-investigator` or Explore subagent; restate the rules that matter (they do not see CLAUDE.md) |
| normal | a feature or fix with a clear spec or plan | sonnet | medium | main session |
| risky | database schema, threading, security, installer or updater, anything near user data | opus | high | main session: tell the user `/model opus` before starting |
| vague | design-heavy or unclear (and ask in `question`) | opus | high | ask questions or brainstorm first, then re-route; plan mode |

## Steps

1. Check inputs: restate the task in one line. If it is vague, ask the clarifying questions before routing (a clear spec buys more than effort does).
2. Read the project's lines in `~/.claude/console/routing-misses.md` and apply any that match this task type.
3. Pick the row. Tell the user the route on its own line, in this shape (Claude Console reads it): `Route: mechanical, low effort, cavecrew-builder on sonnet`.
4. If the main session's level should change, tell the user the command (`/effort low|medium|high|xhigh|max`, or `/model haiku|sonnet|opus|fable`); Claude cannot run slash commands. Change routes at the start, not mid-task: a model switch rebuilds the prompt cache.
5. For delegated parts, call the Agent tool with the row's agent and `model`; this skill counts as the explicit instruction for an `effort` value when the row names one.
6. Verify with code: run the `verifier` agent; its report ends in `VERDICT: PASS` or `VERDICT: FAIL <line>`.
7. On FAIL: one repair at the same route. If it still fails, escalate one step, once: effort +1 while below high; at high or above, the next model (haiku, sonnet, opus, fable) at the same effort; on fable, effort +1. If that fails too, stop and report the failing lines.
8. If step 7 escalated, append one line to `~/.claude/console/routing-misses.md` (create it with the line `# Routing misses` and a blank line first if it does not exist). Use exactly this shape, so Claude Console's Prep can read it:

```
- 2026-10-10 - CLAUDE CONSOLE - normal: sonnet/medium failed (tests/test_state.py:40 - KeyError: 'rules'); next time start at sonnet/high.
```

   The project is the git root folder's name; the type is the row from step 3.
9. If you must stop for a decision only the user can make, end the message with one line: `STOP: <question>`.

## Done looks like

- The route line was shown to the user before work started.
- The verify step's output is quoted (PASS, or the shortest failing line).
- Every escalation has a matching line in `~/.claude/console/routing-misses.md`.

## Never

- Never escalate more than once per task, or retry the same failing route more than once.
- Never call the work done on a cheap route without a code check; a passing test can still hide a wrong patch, so say what the check did not cover.
- Never switch the model mid-task to save money on the remaining steps.
- Never write misses anywhere else (not auto memory, not the repo): one file, read by Prep and by this skill.

## Sources

CONTENT MANAGER `data/notes/model-routing-playbook.md` (5 rules, patterns 1 to 5, "The GOAT router in real tools", "The spec rule"); page by @donimas: famous-mandarin-287.notion.site/Model-Routing-Playbook-3f01be55d9b881fbb5d5f0a20f30b265. `/effort`, `/model` and subagent `model` / `effort` frontmatter checked against code.claude.com/docs (commands, model-config, sub-agents). Moved from CONTENT MANAGER to `~/.claude/skills` by Claude Console plan 04; the table matches `console/prep_prompt.md` (a test checks it).
````

- [ ] **Step 6: Run the tests**

Run: `py -m unittest discover -s tests`
Expected: `Ran 87 tests ... OK`.

- [ ] **Step 7: Commit**

```bash
git add dotclaude tests/test_dotclaude.py
git commit -m "feat: user-level route-model, session-handoff and verifier in dotclaude/"
```

**DONE WHEN**
- [ ] 87 tests OK; `grep -rn "CONTENT MANAGER" dotclaude` shows only the two `Sources` lines; `git status --short` empty.

---

### Task 5: Fred: hooks, skill moves, live check

Claude cannot do this task: it writes `~/.claude/settings.json` (the installer) and `~/.claude/skills` / `~/.claude/agents` (protected paths), deletes files in CONTENT MANAGER, and needs Fred's VS Code chats. Do the steps in order; each skill is checked before the next is copied.

- [ ] **Step 1 (Fred): add the new hook event.** In Git Bash from the repo root:

```bash
py install_hooks.py            # dry run: the list ends with InstructionsLoaded
py install_hooks.py --write    # backs up settings.json, then writes
```

Then restart the window (close it, `run.bat`): the open window still runs the phase 3 code.

- [ ] **Step 2: Rules, delegate, model mix**
1. **Rules**: start a new VS Code chat in CONTENT MANAGER (`say hi in one line`). Expected: its row has a `rules 21.0 KB` badge (about: CONTENT MANAGER's CLAUDE.md is being edited); the detail lists `~/.claude/CLAUDE.md 3 lines 0.2 KB (user) · CLAUDE.md 149 lines 20.8 KB (project)` and the `△ rules ... (over 16 KB)` note. A new chat in CLAUDE CONSOLE lists its two files and has no badge. Chats started before Step 1 list nothing.
2. **Delegate**: in a new VS Code chat in CLAUDE CONSOLE: `Without a subagent, use the Read tool on every file in console/ and tests/ one by one, then say done in one line. Do not edit anything.` Expected: `delegate?` on the row while it reads (from the 10th read), the detail note `⇢ delegate N reads in the main chat this turn ...`; the next prompt in that chat clears it.
3. **Model mix**: the strip shows `<model> <n>` pairs that match the models on today's rows and agent rows, and `runs N · $X.XX` once a window run exists today.

- [ ] **Step 3 (Fred): move session-handoff, then check it.** In Git Bash from the repo root:

```bash
mkdir -p ~/.claude/skills/session-handoff
cp dotclaude/skills/session-handoff/SKILL.md ~/.claude/skills/session-handoff/
rm -r "/d/MY DOCS/MY TOOLS/CONTENT MANAGER/.claude/skills/session-handoff"
```

Checks:
1. The detail of an idle window run in CLAUDE CONSOLE shows a `Handoff` button (no `Handoff off` note).
2. In a scratch project with runs allowed and no PLAN.md (for example `D:\MY DOCS\MY TOOLS\cc-levers` from plan 03 Task 7: Run raw `say hello in one line`), click Handoff. Expected: the reply says there is nothing to hand off, and the row turns `✓ Done`.
3. In a VS Code chat Fred is ready to close, type `/session-handoff`. Expected: when that turn ends, its row turns `✓ Done` with no click in the window (it writes that chat's decisions, as the skill always did).

- [ ] **Step 4 (Fred): copy the verifier, then check it.**

```bash
cp dotclaude/agents/verifier.md ~/.claude/agents/
```

Check: Verify on an idle window run in CLAUDE CONSOLE (it has no project verifier). Expected: Chat shows an `Agent verifier: ...` tool line, the session gets an agent row `verifier` with a `PASS` badge, and the run ends with `VERDICT: PASS`. CONTENT MANAGER keeps its own `.claude/agents/verifier.md` (it wins there).

- [ ] **Step 5 (Fred): move route-model, then check it.**

```bash
mkdir -p ~/.claude/skills/route-model
cp dotclaude/skills/route-model/SKILL.md ~/.claude/skills/route-model/
rm -r "/d/MY DOCS/MY TOOLS/CONTENT MANAGER/.claude/skills/route-model"
```

Check: a new VS Code chat in CLAUDE CONSOLE: `/route-model rename the variable s to sess in console/state.py; only pick and print the route, do not edit anything`. Expected: a `Route: mechanical, low effort, ...` line, which becomes the row's route; Steps show a `Read` of `.../.claude/console/routing-misses.md`.

- [ ] **Step 6:** `~/.claude/console/hook-errors.log` and `window-errors.log` have no new lines.

**DONE WHEN**
- [ ] Steps 1-6 pass; anything that differed is noted in History / Troubleshooting.

---

### Task 6: Close the phase

- [ ] **Step 1:** In `../PLAN.md`, set sub-plan 4 to "done <date>" and add a dated History line (what was built, test count, anything that differed).
- [ ] **Step 2:** In this file, tick the TODO list, add the History line, add any bug + fix to Troubleshooting.
- [ ] **Step 3:** In `../CLAUDE.md`, add under Rules: `- User-level skills and agents live in dotclaude/ (same layout as ~/.claude); Fred copies them to ~/.claude. Code and Claude write ~/.claude/console/ only.`
- [ ] **Step 4:** Commit: `git add PLAN.md CLAUDE.md plans/04-polish.md && git commit -m "docs: phase 4 done"`.

**DONE WHEN**
- [ ] `git status --short` is empty and `git log --oneline` shows one commit per task.

---

## DONE WHEN (whole plan)

- [x] `py -m unittest discover -s tests` -> 87 tests OK.
- [x] A session whose rules are over 200 lines in one file or 16 KB in all shows a `rules` badge and the file list.
- [x] A turn with 10 or more main-chat reads shows `delegate?`.
- [x] The strip shows today's model mix and the window runs with their cost.
- [x] A `/session-handoff` run inside a VS Code chat makes it Done.
- [x] `route-model`, `session-handoff` and `verifier` work from `~/.claude` in every project; `route-model` reads and writes `~/.claude/console/routing-misses.md` (live: the read, and after the Verify text fix and a restart, Verify ran the `~/.claude` verifier: agent row `verifier · claude-sonnet-5-5/low`, PASS; no chat escalated, so the miss write is not seen live yet).
- [x] Nothing outside `~/.claude/console/`, this repo and the run's own project folder was written by the code or by Claude.

## History

- 2026-10-10 - Plan written. Fred decided: rules limits 200 lines per file or 16 KB in all, measured with the `InstructionsLoaded` hook and shown as a row badge plus a detail list; "should delegate" at 10 main-chat reads in a turn; the model mix counts sessions and agent runs per model plus window runs and cost, in the bottom strip; a handoff inside a chat makes it Done; the three files go through `dotclaude/` and Fred copies them (handoff, then verifier, then route-model); route-model writes chat misses to `~/.claude/console/routing-misses.md`; CONTENT MANAGER keeps its verifier as an override. All code was run in a scratch clone first: 87 tests OK; the tasks were replayed in a fresh clone (each task's new tests fail as written, then pass: 80, 84, 84, 87); the window checked in a browser with the fake claude (badges, notes, strip, a window run in the mix, no console errors). CLI facts from real `claude -p` calls on 2.1.296 (InstructionsLoaded fields, a typed `/skill` logs only UserPromptSubmit, the generic verifier's FAIL verdict, route-model's Route line and misses read, session-handoff's "nothing to hand off"; about $0.05 in all).
- 2026-10-10 - Tasks 1-4 placed exactly as written (80, 84, 84, 87 tests; the 4 browser checks passed with the fake claude). Task 5 by Fred: hooks re-installed, the three files copied to `~/.claude`, CONTENT MANAGER's two skill copies removed; live: `rules 21.0 KB` on a new CONTENT MANAGER chat (149 lines, 20,791 bytes + 229), `delegate?` after 27 main-chat reads, window Handoff and a typed `/session-handoff` both made the session Done, Verify gave a PASS badge, `/route-model` set the row's route and read the console misses file, no error-log lines. Differed: Fred first copied the old CONTENT MANAGER skill versions (replaced by the generic ones); Verify ran the tests itself instead of the `~/.claude` verifier, and the strip was below the scrolling page: both fixed in one commit (87 tests, see Troubleshooting).

## Troubleshooting

- **Issue:** no `rules` line in the detail of a session.
  **Cause:** the session started before Fred re-ran `install_hooks.py --write` (Task 5 Step 1), or the project uses an `AGENTS.md` that Claude Code reads directly (no `InstructionsLoaded` event for it, per the docs).
  **Fix:** start a new chat after Step 1; for `AGENTS.md`, import it from a `CLAUDE.md`.
- **Issue:** `delegate?` on a window run.
  **Cause:** window runs are counted like any chat: 10 or more main-chat reads in one turn.
  **Fix:** none needed; delegate the reading in the prompt next time, or raise `delegate_after_reads` in `config.json`.
- **Issue:** route-model asks for permission to edit `~/.claude/console/routing-misses.md`.
  **Cause:** `~/.claude` is a protected path; no allow rule can pre-approve it (docs, permission-modes).
  **Fix:** approve it (`Yes, and allow Claude to edit files in its ~/.claude folder for this session` keeps it to this session); escalations are rare.
- **Issue:** a row turned `✓ Done` after Claude ran `session-handoff` on its own.
  **Cause:** the skill is model-invocable; a main-thread `Skill session-handoff` step counts as a handoff (fixed decision 5).
  **Fix:** type the next prompt in that chat: it reopens.
- **Issue:** Verify ran the tests itself and showed no `verifier` agent row, although `~/.claude/agents/verifier.md` existed (Task 5 Step 4).
  **Cause:** `levers.VERIFY_TEXT` said "If this project has a `verifier` agent"; Claude looked only in the repo's `.claude/agents`.
  **Fix:** the text now names both places and the Agent tool (`the project's .claude/agents or ~/.claude/agents`); `tests/test_server.py` checks it (still 87 tests).
- **Issue:** the model-mix strip was not visible in the window.
  **Cause:** `body` had `min-height: 100vh`, so the whole page scrolled and the strip sat under the last row.
  **Fix:** `body { height: 100vh; }` and `main { min-height: 0; }` in `web/style.css`: only the list scrolls, the prompt box and strip stay at the bottom.
- **Issue:** `~/.claude/skills` held the CONTENT MANAGER versions (Content Manager paths, misses in auto memory) after the move.
  **Cause:** they were copied from CONTENT MANAGER before Task 4 had created `dotclaude/`.
  **Fix:** copy the three `dotclaude/` files over them (Task 5 Steps 3-5 commands).
