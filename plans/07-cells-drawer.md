# Plan 07: Cells Drawer window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Related plans: [../PLAN.md](../PLAN.md) (master), [06-rework.md](06-rework.md) (the pill, peek card, borderless window, estimated cost and cells this plan builds on; its Tasks 1-6 are placed, its Tasks 7-8 are closed by this plan's Tasks 5-6)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md) sections 3 (D11, D12), 7.1-7.5; [../design/rework/README.md](../design/rework/README.md); the locked mockup [../design/rework/locked/cells-drawer.html](../design/rework/locked/cells-drawer.html) (its notes column holds the reasoning) and the token reference [../design/rework/locked/console-cells.html](../design/rework/locked/console-cells.html); [../CLAUDE.md](../CLAUDE.md)

**Goal:** The open window becomes Cells Drawer (BRAINSTORM 7.5, D12). One column and no rail. The list is home: a header with a searchable project picker and the "N need you" chip, today's spend as one row of cells, sessions grouped Needs you / Working / Done today as cards in words with the answer or the unblock in place, and the composer with its target project named. A card opens the session page: head, the ask or denial, one muted note line, the brief (path and one row of figures; click or Space opens context, agent lanes and activity), the process tabs Steps / Agents / Timeline / Chat, and the levers bar, with `‹ ›` and Up / Down between sessions and Esc back. The Prep card is its own page. The pill, the peek card, the states, the borderless window and the form memory stay as plan 06 built them. No horizontal scroll at 400 or 340 px (the window is a CSS container); orange only for "needs you", state never by colour alone, one blinking cell per screen, one Doto figure per screen.

**Architecture:** The service adds three things the page needs: `console/transcript.py` (the last turns of a VS Code or terminal chat, in words, from the transcript it already reads for the estimate), a `projects` list in the snapshot (every project a session ran in, when it was last active, what it cost today) for the picker, and `brief` next to the compose project in `window.json` (through `/api/draft`). The bar timeline (`State.timeline`, `Hub.timeline`, `/api/timeline`) goes: the Timeline tab counts the activity buckets the snapshot already has and reads one minute's steps from `/api/steps`. `web/` is rewritten from the plan 06 renderers: `index.html` (pill + peek, three pages, the picker), `style.css` (the mockup's classes on the plan 06 tokens), `app.js` (renderRail, the Overview, the focus pane, the compose project select and the seg control are gone).

**Tech Stack:** unchanged: Python 3.14 standard library, pywebview 6.2.1 (EdgeChromium), plain HTML/CSS/JS, `unittest`. Claude Code CLI 2.1.296.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `master`). Every path below is relative to it. Run commands from the repo root in Git Bash. Start: 95 tests OK.

---

## Fixed decisions (Fred's answers 2026-10-10; the rest verified on this machine, Claude Code 2.1.296)

1. **Cells Drawer is the target** (Fred). `design/rework/locked/cells-drawer.html` is locked (copied from `explored/d-cells-drawer.html`); `console-cells.html` stays the reference for tokens, type and the cell motif. BRAINSTORM D12 and 7.5, the README tables and the CLAUDE.md rule were updated when it was locked (commit `docs: lock Cells Drawer ...`). Plan 06 Tasks 1-5 (hook, usage, state, service, borderless window) stand unchanged.
2. **Chat for VS Code and terminal chats** (Fred): `/api/chat` returns the last 6 turns of the chat's transcript, text blocks only. Verified on this machine's transcripts: lines have `type` `user` or `assistant`, `isMeta`, `isSidechain`, an ISO `timestamp` and `message.content` as a string or a list of blocks (`text`, `tool_use`, `tool_result`, `thinking`, `image`); a user line can carry injected text blocks (`<system-reminder>` ...), which are dropped (Fred's own `<pasted_content>` stays, as in the hook). `[Request interrupted ...]` becomes the note `stopped`. The file is read from its last 1 MB, read only, only for a path the hook logged and that ends in `.jsonl`. Window runs keep their stream (`runs.chat`); the page hides the `tool` lines of it, so both read in words. The response gains `source` (`window` or `transcript`).
3. **Timeline** (Fred): one cell per minute for the last 30 minutes, the snapshot's activity levels (1-2 / 3-5 / 6-9 / 10+ steps). A click or `<-` / `->` selects a minute; its steps are the `/api/steps` entries of that minute (the last 200). The selected minute is kept as a minute number, so the cells sliding on by a minute do not change what is selected.
4. **The Prep card is its own page** (Fred) with Back (= Edit, the text stays), Run / Run raw / Edit / Cancel, Esc = Cancel.
5. **Notes** (Fred): one muted line under the session head, only when there is a note (FAIL detail, denied-but-finished, hand off, rules size, should delegate, 2 writers, escalated, window copy links). Dropped with the notes block: the route reason (a tooltip on the `where` line), the turns / compactions line and the rules file list (the rules note names the files over the limit).
6. **Brief open or folded** (Fred): one choice for the window, `brief` in `~/.claude/console/window.json`, saved through `/api/draft` (`{text, project, brief}`, `brief` must be a boolean) and read from `/api/config`. Folded by default.
7. **Project picker.** A page-drawn popover under the header (never a native `<select>`), Ctrl+P from anywhere, a find box with focus on open, Up / Down / Enter / Esc, groups Runs allowed and Runs off. The rows are the `config.json` folders plus every folder a session ran in (the new snapshot key `projects`: `dir`, `name`, `last_ts`, `today`, also for a session older than the 24 h the list shows); each row says `N needs you`, `N live` or when it was last active (`runs off`, `no session yet`) and what it cost today. Sorted by needs you, live, last activity. One choice, two effects: it scopes the list and becomes the target of a new task (All projects keeps the target). The target is saved in `window.json` (`project`, as in plan 06); the scope is not. Opening a session sets the target to its project; `New task here` scopes the list to it and focuses the box. The `N need you` chip counts every project and clears the scope.
8. **Today strip.** `today` as the one Doto figure, one row of cells ($0.50 each: solid exact, hatched estimated, orange outline at 80 % of `daily_budget_usd`), `$ / min` and the limit. 30 cells = the $15 limit; past it the row gets one more cell per $0.50 (they shrink, nothing scrolls). One click opens the breakdown: exact / estimated, 1 cell = $0.50, model shares, window runs, the `2 writers` warnings.
9. **Cards.** Line 1: glyph + state word, title, age (a hand-off hint adds `HAND OFF`). Line 2 in fixed columns: project (+ `2 writers`) and route, cost, context as 15 x 2 cells and the figure. Line 3 by state: a STOP question with an answer box (Enter or Send), `denied: ...` / the failure / the interruption / the red context with `Open in terminal` (a blocked window run) and `Resume` (an interrupted window run), the running agent or `main` with the live step and the one blinking cell. Done sessions are one quiet line each (PASS / FAIL / DONE, cost); two show, `Show N more` for the rest. Clicking a card opens the session, Enter on a focused card too. **Not built:** the mock's `Dismiss` (a denial has no service state to dismiss; the card opens the session and the peek card has no Dismiss either).
10. **Answering in place.** From a card or the session page the answer goes to `/api/continue` as before (a VS Code or terminal chat runs in a window copy and stays as it is). A card then reads `Answer sent. It runs in a window copy: open it` (kept in the page for that question; the original chat is unchanged, so it stays in Needs you), or `It continues here.` for a window run.
11. **Session page.** Head: glyph + state + age, the title, `project / source / route` and `New task here`. Then the note line, the ask box (the question, an answer box, `Send answer`, `Open in terminal` for a window run) or the denial / failure card, then the brief: the path (Prep, Run, Verify, Hand off as 6 cells each, green done, ink current, red FAIL), then spent (Doto, `~` for an estimate), `$ / min`, context (30 cells and the figure; the label turns into `hand off soon` from the yellow threshold and `hand off now` from the red one), time and steps (main + agents). Opened it adds context against the hand-off marks, the agent lanes (1 cell = 2 steps, `▶` live, `✓` done) and the activity row. The process takes the rest of the height (at least 200 px; the page scrolls when the brief is open): Steps (newest first, time with seconds, agent, step; the live step carries the one blinking cell, a question `?`, a denial `■`), Agents N (state in words, steps, cost, last step), Timeline, Chat. Up / Down (outside text fields and the pane) and `‹ ›` step through the list in its order (the scoped list; all sessions when the open one is out of scope); `<-` / `->` move between the tabs and between the minutes.
12. **Keeping what Fred is doing.** The service pushes a snapshot about every second while events flow, and the list now holds inputs. `setHtml` replaces an element's content only when it changed and keeps typed text, the focused control and the scroll position of the process pane; the picker is outside every re-rendered element, so a snapshot never closes it.
13. **Responsive.** The open window is a CSS container (`container-type: inline-size`); below 372 px the grip, the `USD` word, the route on cards, the picker's sort note and the seconds of `time` go, the window buttons narrow to 26 px and context in the brief falls back to the card's 15 x 2 cells. Checked at 400 and 340 px.
14. **Focus ring and selection are ink**, not orange: orange means "needs you" and nothing else. Window buttons (`⊤`, `–`, `✕`) exist only in the pywebview window (`html.native`).
15. **Removed** (what D drops): `renderRail`, the rail, the Overview pane, the compose project `<select>`, the `seg` control, the notes block, `State.timeline`, `Hub.timeline` and `/api/timeline`.
16. **Verified in a browser, not on Fred's screen.** Claude checked the pages in an iframe of 400 x 640 and of 340 x 640 against a seeded service with the fake claude (a harness in the scratchpad, Task 4 Step 5): every view of the mock, both widths, dark, and light by setting the light tokens by hand (the page's own light theme is the plan 06 media query, unchanged). **Not verified by Claude:** the native window (dragging by the new `.top` bar, the double-click fold, the pill resizing for a peek card, WebView2 focus, the system light theme) and the page on real sessions and transcripts. Task 5.

## Code map

```text
console/
  transcript.py     NEW  the last turns of a chat in words, from its transcript
  state.py          + day_cost, projects (snapshot key "projects"); - timeline
  server.py         /api/chat reads a transcript for a non-window session; /api/draft + /api/config "brief";
                    - Hub.timeline, /api/timeline; Hub.session + transcript_path
web/
  index.html        pill + peek, three pages (list, session, Prep), the picker
  style.css         Cells Drawer classes on the plan 06 tokens
  app.js            list, cards, picker, session page, process tabs, Prep page, compose, pill, peek
tests/
  test_transcript.py  NEW  words only, last six, cut line, masking, other files
  test_state.py     + projects; - timeline
  test_server.py    + chat of a VS Code chat, brief in window.json; - timeline calls
```

Dependencies point one way: `server -> transcript -> redact`; `state` is unchanged in what it imports.

## Files to modify

`console/state.py`, `console/server.py`, `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_state.py`, `tests/test_server.py`, `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md`, `plans/06-rework.md`, this file. New: `console/transcript.py`, `tests/test_transcript.py`. Unchanged: `cc_events.py`, `console/usage.py`, `console/window.py`, `console/runs.py`, `console/levers.py`, `console/prep.py`, `console/paths.py`, `console/__main__.py`, `install_hooks.py`, `tests/fake_claude.py`.

## TODO

- [ ] Task 1: the last turns of a chat from its transcript
- [ ] Task 2: state lists the projects for the picker
- [ ] Task 3: service (chat from transcripts, brief in window.json, bar timeline removed)
- [ ] Task 4: Cells Drawer window
- [ ] Task 5: Fred: live check in the real window (also closes plan 06 Task 7)
- [ ] Task 6: close the phase (also closes plan 06 Task 8)

---

### Task 1: The last turns of a chat from its transcript

A VS Code or terminal chat has no stream of its own; its transcript (which the service already reads for the estimate) has the words. New module, read only, never raises.

**Files:**
- Create: `tests/test_transcript.py`, `console/transcript.py`

- [ ] **Step 1: Create `tests/test_transcript.py` with:**

```python
import json
import tempfile
import unittest
from pathlib import Path

from console import transcript


def user(content, **extra):
    return {"type": "user", "timestamp": "2026-10-10T10:00:00Z", "message": {"role": "user", "content": content},
            **extra}


def claude(blocks):
    return {"type": "assistant", "timestamp": "2026-10-10T10:00:05Z", "message": {"role": "assistant", "content": blocks}}


class TranscriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "s1.jsonl"

    def write(self, *recs, raw=""):
        self.path.write_text("".join(json.dumps(r) + "\n" for r in recs) + raw, encoding="utf-8")

    def test_words_only(self):
        self.write(
            user("fix the retry"),
            claude([{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "Looking."},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]),
            user([{"type": "tool_result", "tool_use_id": "t1", "content": "file body"}]),
            user([{"type": "text", "text": "<system-reminder>skills</system-reminder>"},
                  {"type": "text", "text": "now the tests"}]),
            user([{"type": "text", "text": "Base directory for this skill: x"}], isMeta=True),
            claude([{"type": "text", "text": "side"}]) | {"isSidechain": True},
            {"type": "ai-title", "title": "x"},
            user("<pasted_content id=\"ab\">keep this</pasted_content>"),
            user([{"type": "text", "text": "[Request interrupted by user]"}]),
        )
        got = transcript.turns(self.path)
        self.assertEqual([(t["role"], t["text"]) for t in got], [
            ("you", "fix the retry"), ("claude", "Looking."), ("you", "now the tests"),
            ("you", "keep this"), ("note", "stopped")])
        self.assertEqual(got[0]["ts"], 1791626400.0)

    def test_last_six_and_a_cut_first_line(self):
        self.write(*[user(f"turn {k} " + "x" * 200) for k in range(40)], raw='{"type": "user", "mess')
        got = transcript.turns(self.path)
        self.assertEqual([t["text"][:8] for t in got], [f"turn {k} " for k in range(34, 40)])
        old = transcript.TAIL_BYTES
        transcript.TAIL_BYTES = 3000  # reads from the middle of a line: that line is dropped
        self.addCleanup(setattr, transcript, "TAIL_BYTES", old)
        got = transcript.turns(self.path, limit=50)
        self.assertTrue(0 < len(got) < 40 and got[-1]["text"].startswith("turn 39"))

    def test_masks_and_ignores_other_files(self):
        self.write(user("use key sk-abcdefghijkl1234 now"))
        self.assertEqual(transcript.turns(self.path)[0]["text"], "use key *** now")
        self.assertEqual(transcript.turns(Path(self.tmp.name) / "none.jsonl"), [])
        (Path(self.tmp.name) / "notes.txt").write_text("{}", encoding="utf-8")
        self.assertEqual(transcript.turns(Path(self.tmp.name) / "notes.txt"), [])
        self.assertEqual(transcript.turns(None), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it**

```bash
py -m unittest tests.test_transcript
```

Expected: `FAILED (errors=1)` (`ImportError: cannot import name 'transcript' from 'console'`).

- [ ] **Step 3: Create `console/transcript.py` with:**

```python
"""The last turns of a Claude Code chat in words, read from its transcript: a VS Code or terminal chat
has no stream of its own. Read only, from the end of the file; tool calls, tool results and thinking
stay out (Steps shows tool calls)."""
import json
import re
from datetime import datetime

from . import redact

TAIL_BYTES = 1024 * 1024  # read from the end: enough for the last few turns of a long chat
TURNS = 6
TEXT_MAX = 1500
# A block Claude Code or an extension puts into a user line (<system-reminder>, <command-name>, ...).
# Fred's own pastes stay, as in cc_events.py.
_INJECTED = re.compile(r"\s*<(?!pasted_content\b)([A-Za-z][\w-]*)[^>]*>.*?</\1>\s*", re.S)
_PASTED = re.compile(r"</?pasted_content[^>]*>")


def _when(stamp):
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _words(content) -> str:
    """The text blocks of one message, without injected blocks and tool blocks."""
    if isinstance(content, str):
        parts = [content]
    elif isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    else:
        return ""
    text = "\n".join(p for p in parts if isinstance(p, str))
    return _PASTED.sub("", _INJECTED.sub(" ", text)).strip()


def turns(path, limit: int = TURNS) -> list:
    """[{role: you | claude | note, text, ts}] oldest first: the last `limit` turns of the transcript."""
    path = str(path or "")
    if not path.endswith(".jsonl"):
        return []
    try:
        with open(path, "rb") as fh:
            start = max(0, fh.seek(0, 2) - TAIL_BYTES)
            fh.seek(start)
            data = fh.read()
    except OSError:
        return []
    lines = data.split(b"\n")
    if start:
        lines = lines[1:]  # the first line was cut in the middle
    out = []
    for raw in lines:
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        kind = rec.get("type") if isinstance(rec, dict) else None
        if kind not in ("user", "assistant") or rec.get("isMeta") or rec.get("isSidechain"):
            continue
        msg = rec.get("message")
        text = _words(msg.get("content") if isinstance(msg, dict) else None)
        if not text:
            continue
        if text.startswith("[Request interrupted"):
            out.append({"role": "note", "text": "stopped", "ts": _when(rec.get("timestamp"))})
        else:
            out.append({"role": "you" if kind == "user" else "claude", "text": redact.mask(text[:TEXT_MAX]),
                        "ts": _when(rec.get("timestamp"))})
    return out[-limit:]
```

- [ ] **Step 4: Run it**

```bash
py -m unittest tests.test_transcript
```

Expected: `Ran 3 tests` ... `OK`.

- [ ] **Step 5: Run it**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 98 tests` ... `OK`.

- [ ] **Step 6: Commit**

```bash
git add console/transcript.py tests/test_transcript.py
git commit -m "feat: the last turns of a chat from its transcript"
```

**DONE WHEN**
- [ ] 98 tests OK; `git status --short` empty.

---

### Task 2: State lists the projects for the picker

The picker needs every project a session ran in (also one whose sessions are older than the 24 h the list shows), when it was last active and what it cost today. `State.day_cost` is the per-session piece of the existing `spend` figure; `spend` uses it, so its numbers do not change.

**Files:**
- Modify: `tests/test_state.py` (one new test), `console/state.py`

- [ ] **Step 1: Edit `tests/test_state.py`**

Find:

```python
        self.assertEqual(self.state.snapshot(T0)["spend"]["today"], 1.25)  # no reader: exact only

    def test_activity_cells_per_minute(self):
        now = 1_000_020.0  # a minute boundary
```

Replace with:

```python
        self.assertEqual(self.state.snapshot(T0)["spend"]["today"], 1.25)  # no reader: exact only

    def test_projects_for_the_picker(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        chat = str(Path(tmp.name) / "a.jsonl")
        Path(chat).write_text(line("m1", T0 - 60, "claude-opus-5-5", input_tokens=1_000_000), encoding="utf-8")
        self.feed(ev("UserPromptSubmit", T0 - 4 * 86400, sid="o", project="OLD", project_dir="D:/old"),
                  ev("UserPromptSubmit", T0 - 100, sid="a", transcript_path=chat),
                  ev("run_started", T0 - 50, sid="b", model="sonnet"),
                  ev("run_ended", T0 - 10, sid="b", cost=1.25, subtype="success"))
        reader = usage.Usage(paths.DEFAULTS["prices"])
        for f in self.state.transcripts(T0):
            reader.poll(f)
        snap = self.state.snapshot(T0, reader)
        self.assertEqual([r["id"] for r in snap["sessions"]], ["a", "b"])  # the old session is not shown ...
        self.assertEqual(snap["projects"], [  # ... but its project still is a choice
            {"dir": "D:/old", "name": "OLD", "last_ts": T0 - 4 * 86400, "today": 0.0},
            {"dir": "D:/repo", "name": "repo", "last_ts": T0 - 10, "today": 5.25}])
        self.assertEqual(self.state.snapshot(T0)["projects"][1]["today"], 1.25)  # no reader: exact only

    def test_activity_cells_per_minute(self):
        now = 1_000_020.0  # a minute boundary
```

- [ ] **Step 2: Run it**

```bash
py -m unittest tests.test_state
```

Expected: `FAILED (errors=1)` (`KeyError: 'projects'` in the new test).

- [ ] **Step 3: Edit `console/state.py`**

Find:

```python
                           sorted(s.agents.values(), key=lambda a: a.started_ts)],
            })
        return {
            "now": now,
            "sessions": rows,
            "writers": [{"project_dir": p, "sessions": ids} for p, ids in sorted(writers.items())],
            "counts": {g: sum(1 for r in rows if r["group"] == g) for g in ("needs", "working", "done")},
            "spend": self.spend([self.sessions[r["id"]] for r in rows], now, usage),
        }
```

Replace with:

```python
                           sorted(s.agents.values(), key=lambda a: a.started_ts)],
            })
        shown = [self.sessions[r["id"]] for r in rows]
        return {
            "now": now,
            "sessions": rows,
            "writers": [{"project_dir": p, "sessions": ids} for p, ids in sorted(writers.items())],
            "counts": {g: sum(1 for r in rows if r["group"] == g) for g in ("needs", "working", "done")},
            "spend": self.spend(shown, now, usage),
            "projects": self.projects(shown, now, usage),
        }
```

Find:

```python
        families = {}
        if usage:
            estimated = usage.cost([f for s in sessions if not s.window for f in self.files(s)], start)
            burn = usage.cost(every, now - BURN_S) / (BURN_S / 60)
            families = usage.families(every, start)
```

Replace with:

```python
        families = {}
        if usage:
            estimated = sum(self.day_cost(s, start, usage) for s in sessions if not s.window)
            burn = usage.cost(every, now - BURN_S) / (BURN_S / 60)
            families = usage.families(every, start)
```

Find:

```python
                "estimated": round(estimated, 4), "burn": round(burn, 4),
                "budget": self.cfg["daily_budget_usd"], "runs": runs, "models": models}

    def _agent_row(self, a: Agent, s: Session, cost=None) -> dict:
```

Replace with:

```python
                "estimated": round(estimated, 4), "burn": round(burn, 4),
                "budget": self.cfg["daily_budget_usd"], "runs": runs, "models": models}

    def day_cost(self, s: Session, start: float, usage=None) -> float:
        """What one session cost since `start`: a window session's finished runs (exact), else the
        transcript estimate (0 without a reader)."""
        if s.window:
            return sum(c for ts, c in s.run_costs if ts >= start)
        return usage.cost(self.files(s), start) if usage else 0.0

    def projects(self, shown: list, now: float, usage=None) -> list:
        """Every project a session ran in (also one older than SHOW_FOR_S): when it was last active and
        what today's shown sessions cost there. The window's project picker reads this."""
        start, today, found = midnight(now), {}, {}
        for s in shown:
            if s.project_dir:
                today[s.project_dir] = today.get(s.project_dir, 0.0) + self.day_cost(s, start, usage)
        for s in self.sessions.values():
            if s.project_dir:
                p = found.setdefault(s.project_dir, {"dir": s.project_dir, "name": s.project, "last_ts": 0.0})
                p["last_ts"] = max(p["last_ts"], s.last_ts)
                p["name"] = s.project or p["name"]
        return [dict(p, today=round(today.get(d, 0.0), 4)) for d, p in sorted(found.items())]

    def _agent_row(self, a: Agent, s: Session, cost=None) -> dict:
```

- [ ] **Step 4: Run it**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 99 tests` ... `OK`.

- [ ] **Step 5: Commit**

```bash
git add console/state.py tests/test_state.py
git commit -m "feat: state lists the projects for the picker"
```

**DONE WHEN**
- [ ] 99 tests OK; `git status --short` empty.

---

### Task 3: Service: chat from transcripts, the brief in window.json, the bar timeline removed

`/api/chat` for a session that is not a window run now reads its transcript (through the path the hook logged; `Hub.session` gains `transcript_path`). `/api/draft` accepts `brief` (boolean) next to `project`; `/api/config` returns it. The bar timeline is removed (Fixed decision 3): `State.timeline`, `Hub.timeline`, `/api/timeline` and their tests.

**Files:**
- Modify: `tests/test_state.py`, `tests/test_server.py`, `console/state.py`, `console/server.py`

- [ ] **Step 1: Edit `tests/test_state.py`**

Find:

```python
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
```

Replace with:

```python
        self.assertFalse(self.row(T0 + 4000, "big")["handoff_hint"])  # Stale?: no hint

    def test_rules_size_warning(self):
        self.feed(ev("InstructionsLoaded", T0, file="~/.claude/CLAUDE.md", scope="User", lines=3, bytes=229,
```

- [ ] **Step 2: Edit `tests/test_server.py`**

Find:

```python
        self.assertEqual((self.hub.runs.meta(fork)["model"], self.hub.runs.meta(fork)["effort"]), ("sonnet", "medium"))
        self.wait_idle(fork)
        timeline = self.call(f"/api/timeline?session={fork}")[1]
        self.assertEqual([lane["label"] for lane in timeline["lanes"]], ["main"])
        self.assertEqual(len(timeline["lanes"][0]["spans"]), 1)

    def test_verify_then_escalate_once(self):
```

Replace with:

```python
        self.assertEqual((self.hub.runs.meta(fork)["model"], self.hub.runs.meta(fork)["effort"]), ("sonnet", "medium"))
        self.wait_idle(fork)

    def test_chat_of_a_vscode_chat_reads_its_transcript(self):
        transcript = Path(self.tmp.name) / "v2.jsonl"
        transcript.write_text("".join(json.dumps(rec) + "\n" for rec in (
            {"type": "user", "timestamp": "2026-10-10T10:00:00Z", "message": {"role": "user", "content": "hello"}},
            {"type": "assistant", "timestamp": "2026-10-10T10:00:05Z", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Hi."}, {"type": "tool_use", "name": "Read", "input": {}}]}})),
            encoding="utf-8")
        events.append(self.folder, {"event": "UserPromptSubmit", "ts": time.time(), "session_id": "v2",
                                    "project": "proj", "project_dir": str(self.project), "prompt": "hello",
                                    "transcript_path": str(transcript)})
        self.hub.poll_once()
        chat = self.call("/api/chat?session=v2")[1]
        self.assertEqual((chat["source"], [(i["role"], i["text"]) for i in chat["items"]]),
                         ("transcript", [("you", "hello"), ("claude", "Hi.")]))
        self.assertEqual(self.call("/api/chat?session=nope")[1]["items"], [])

    def test_verify_then_escalate_once(self):
```

Find:

```python
        self.assertEqual(cfg["gauge"], [150000, 300000])
        self.assertEqual(self.call("/api/draft", {"text": "", "project": 3})[0], 400)
```

Replace with:

```python
        self.assertEqual(cfg["gauge"], [150000, 300000])
        self.assertEqual(self.call("/api/draft", {"text": "", "project": 3})[0], 400)
        self.assertIs(cfg["brief"], False)
        self.assertEqual(self.call("/api/draft", {"text": "", "brief": True})[0], 200)
        config = self.call("/api/config")[1]
        self.assertEqual((config["brief"], config["project"]), (True, str(self.project)))  # project kept
        self.assertEqual(self.call("/api/draft", {"text": "", "brief": "yes"})[0], 400)
```

- [ ] **Step 3: Run it**

```bash
py -m unittest tests.test_server
```

Expected: `FAILED (errors=2)` (`KeyError: 'source'` in the new chat test, `KeyError: 'brief'` in `test_draft_and_config`).

- [ ] **Step 4: Edit `console/state.py`**

Find:

```python
    forked_from: str = ""
    forks: list = field(default_factory=list)
    turns: list = field(default_factory=list)  # [start, end or None] per turn, for the Timeline
    rules: dict = field(default_factory=dict)  # file -> {scope, lines, bytes}: CLAUDE.md / rules loaded
    reads: int = 0             # main-chat Read / Grep / Glob / WebFetch / WebSearch steps this turn
```

Replace with:

```python
    forked_from: str = ""
    forks: list = field(default_factory=list)
    turns: list = field(default_factory=list)  # [start, end or None] per turn; the last start is turn_ts
    rules: dict = field(default_factory=dict)  # file -> {scope, lines, bytes}: CLAUDE.md / rules loaded
    reads: int = 0             # main-chat Read / Grep / Glob / WebFetch / WebSearch steps this turn
```

Find:

```python
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

Replace with:

```python
                for step in s.steps[-limit:]]
```

- [ ] **Step 5: Edit `console/server.py`**

Find:

```python
from urllib.parse import parse_qs, urlparse

from . import claude_cli, events, guard, levers, paths, prep, runs, usage
from .state import State, norm_dir
```

Replace with:

```python
from urllib.parse import parse_qs, urlparse

from . import claude_cli, events, guard, levers, paths, prep, runs, transcript, usage
from .state import State, norm_dir
```

Find:

```python
            return self.state.steps(session_id)

    def timeline(self, session_id: str):
        with self.lock:
            return self.state.timeline(session_id, time.time())

    def session(self, session_id: str):
        with self.lock:
```

Replace with:

```python
            return self.state.steps(session_id)

    def session(self, session_id: str):
        with self.lock:
```

Find:

```python
                    "project": s.project, "project_dir": s.project_dir, "route": s.route,
                    "run_live": s.run_live, "state": self.state.state_of(s, time.time()),
                    "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated}

    def route_of(self, session_id: str, s: dict) -> tuple:
```

Replace with:

```python
                    "project": s.project, "project_dir": s.project_dir, "route": s.route,
                    "run_live": s.run_live, "state": self.state.state_of(s, time.time()),
                    "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated,
                    "transcript_path": s.transcript_path}

    def route_of(self, session_id: str, s: dict) -> tuple:
```

Find:

```python
            return self._json(self.hub.steps(query.get("session", [""])[0]))
        if url.path == "/api/config":
            cfg = self.hub.cfg
            return self._json({"projects": project_list(cfg), "models": claude_cli.MODELS,
                               "efforts": claude_cli.EFFORTS, "default_model": cfg["default_model"],
                               "default_effort": cfg["default_effort"], "claude": bool(self.hub.runs.exe),
                               "config_path": str(self.hub.folder / "config.json"),
                               "gauge": [cfg["gauge_yellow_tokens"], cfg["gauge_red_tokens"]],
                               "project": paths.load_window(self.hub.folder).get("project", "")})
        if url.path == "/api/chat":
            return self._chat(query.get("session", [""])[0])
        if url.path in ("/api/levers", "/api/timeline"):
            sid = query.get("session", [""])[0]
            data = self.hub.levers(sid) if url.path == "/api/levers" else self.hub.timeline(sid)
            return self._json(data) if data else self._error(404, "unknown session")
        if url.path == "/api/draft":
```

Replace with:

```python
            return self._json(self.hub.steps(query.get("session", [""])[0]))
        if url.path == "/api/config":
            cfg, window = self.hub.cfg, paths.load_window(self.hub.folder)
            return self._json({"projects": project_list(cfg), "models": claude_cli.MODELS,
                               "efforts": claude_cli.EFFORTS, "default_model": cfg["default_model"],
                               "default_effort": cfg["default_effort"], "claude": bool(self.hub.runs.exe),
                               "config_path": str(self.hub.folder / "config.json"),
                               "gauge": [cfg["gauge_yellow_tokens"], cfg["gauge_red_tokens"]],
                               "project": window.get("project", ""), "brief": window.get("brief") is True})
        if url.path == "/api/chat":
            return self._chat(query.get("session", [""])[0])
        if url.path == "/api/levers":
            data = self.hub.levers(query.get("session", [""])[0])
            return self._json(data) if data else self._error(404, "unknown session")
        if url.path == "/api/draft":
```

Find:

```python

    def _draft(self, body):
        """The unsent prompt (draft.txt) and, when given, the compose project (window.json)."""
        text, project = body.get("text"), body.get("project")
        if not isinstance(text, str) or len(text) > MAX_PROMPT:
            return self._error(400, "bad draft")
        if project is not None and (not isinstance(project, str) or len(project) > 1000):
            return self._error(400, "bad project")
        self.hub.folder.mkdir(parents=True, exist_ok=True)
        (self.hub.folder / "draft.txt").write_text(text, encoding="utf-8")
        if project is not None:
            paths.save_window(self.hub.folder, project=project)
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
```

Replace with:

```python

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

    def _stream(self):
```

- [ ] **Step 6: Run it**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 99 tests` ... `OK`.

- [ ] **Step 7: Commit**

```bash
git add console/state.py console/server.py tests/test_state.py tests/test_server.py
git commit -m "feat: chat of a VS Code chat from its transcript, brief in window.json, bar timeline removed"
```

**DONE WHEN**
- [ ] 99 tests OK; `git grep -n timeline -- console tests` finds nothing; `git status --short` empty.

---

### Task 4: Cells Drawer window

All styling stays in `web/style.css`, tokens first (CLAUDE.md). The page works the same in a browser (`py -m console --serve`): there the window buttons (`⊤`, `–`, `✕`) are hidden and folding only swaps the form on the page. The page has no `https://` (a test checks it).

**Files:**
- Replace: `web/index.html`, `web/style.css`, `web/app.js` (full files below)

- [ ] **Step 1: Replace `web/index.html` with:**

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
  <div id="folded" class="peek" hidden>
    <div id="pill" class="pill"></div>
    <div id="peek"></div>
  </div>
  <div id="open" class="win">
    <div id="banner" class="banner" hidden><b>OFFLINE</b> The service stopped answering. Runs keep going; the window reconnects by itself.</div>

    <section data-page="list">
      <div class="top">
        <span class="grip pywebview-drag-region" title="Drag to move">&#8942;&#8942;</span>
        <button id="scope" class="scope" data-pick aria-haspopup="listbox" aria-expanded="false" title="Project (Ctrl+P)"><span id="scopenm" class="nm">All projects</span><span class="car">&#9662;</span></button>
        <button id="needsbtn" class="needs" data-go="needs" title="Show what needs you, in every project" hidden></button>
        <span class="sp pywebview-drag-region" title="Drag to move; double-click to fold"></span>
        <span data-winbtns></span>
      </div>
      <div id="listscroll" class="scroll">
        <button id="today" class="today" aria-expanded="false" title="Show today's breakdown"></button>
        <div id="todaymore" class="todaymore" hidden></div>
        <div id="list"></div>
      </div>
      <div id="prepfail"></div>
      <div class="compose">
        <div class="lr"><textarea id="c-prompt" rows="1" spellcheck="false" aria-label="New task"
          title="Enter = Prep · Ctrl+Enter = Run raw · Shift+Enter = new line"></textarea></div>
        <div id="c-say" class="say"></div>
      </div>
    </section>

    <section data-page="session" hidden>
      <div class="top">
        <button class="rb" data-go="list" title="Back to the list (Esc)" aria-label="Back">&#8592;</button>
        <span id="pos" class="crumb m"></span>
        <button id="prev" class="rb" data-step="-1" title="Previous session (Up)" aria-label="Previous session">&#8249;</button>
        <button id="next" class="rb" data-step="1" title="Next session (Down)" aria-label="Next session">&#8250;</button>
        <span class="sp pywebview-drag-region" title="Drag to move; double-click to fold"></span>
        <span data-winbtns></span>
      </div>
      <div id="sscroll" class="scroll sess"><div id="sbody" class="body"></div><div id="proc" class="proc"></div></div>
      <div id="levers" class="levers"></div>
    </section>

    <section data-page="prep" hidden>
      <div class="top">
        <button class="rb" data-pact="edit" title="Back to the list, keeping the text" aria-label="Back">&#8592;</button>
        <span id="crumb" class="crumb m"></span>
        <span class="sp pywebview-drag-region" title="Drag to move; double-click to fold"></span>
        <span data-winbtns></span>
      </div>
      <div id="pscroll" class="scroll stack"></div>
      <div id="pbar" class="levers"></div>
    </section>

    <div id="pop" class="pop" role="dialog" aria-label="Pick a project" hidden>
      <div class="find"><input id="pfind" aria-label="Find a project" placeholder="Find a project" autocomplete="off"><span class="kbd">Esc</span></div>
      <div id="prows" class="rows" role="listbox"></div>
      <div class="foot"><span>&#8593; &#8595; move</span><span>Enter pick</span><span class="sort">sorted: needs you, live, recent</span></div>
    </div>
  </div>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Replace `web/style.css` with:**

```css
/* Cells Drawer (BRAINSTORM 7.5, design/rework/locked/cells-drawer.html; tokens and cell motif from
   console-cells.html). All styling lives here, tokens first. Dark first; the light theme follows the
   system. Every quantity is counted in cells. Orange means "needs you" and nothing else. */
@font-face { font-family: "Doto"; src: url("/doto.woff2") format("woff2"); font-weight: 700; font-display: block; }
:root {
  --page: #0b0c0e; --win: #121315; --raise: #1a1c1f; --off: #24272b; --ink: #ebe8e1;
  --mut: #9a9993; --line: #26292d; --edge: rgb(255 255 255 / 6%);
  --you: #ff8a3d; --bad: #ff5a4e; --ok: #5ed39a; --on-you: #1a0d00; --close: #c42b1c;
  --ui: "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
  --mono: "Cascadia Mono", Consolas, monospace;
  --dot: "Doto", "Cascadia Mono", monospace;
  color-scheme: dark;
}
@media (prefers-color-scheme: light) {
  :root {
    --page: #dedcd6; --win: #f4f3ef; --raise: #e7e5e0; --off: #d6d4ce; --ink: #17181b;
    --mut: #5f5e59; --line: #d2d0ca; --edge: rgb(0 0 0 / 8%);
    --you: #b84f00; --bad: #c0352b; --ok: #1d7a4b; --on-you: #fff7f0;
    color-scheme: light;
  }
}

* { box-sizing: border-box; }
[hidden] { display: none !important; }
html, body { height: 100%; margin: 0; }
body { background: var(--page); color: var(--ink); font: 13px/1.45 var(--ui); overflow: hidden; }
html.native body { background: transparent; }  /* the pywebview window is transparent: the forms draw it */
button, input, select, textarea { font: inherit; color: inherit; }
/* the focus ring and the selection are ink, not orange: orange stays reserved for "needs you" */
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
  outline: 2px solid var(--ink); outline-offset: 1px; }
::selection { background: color-mix(in srgb, var(--ink) 22%, transparent); }
.m { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; }
.mut { color: var(--mut); }
.lbl { font: 500 10.5px var(--mono); letter-spacing: .04em; text-transform: uppercase; color: var(--mut); }
.lbl.y { color: var(--you); } .lbl.r { color: var(--bad); }
.pywebview-drag-region { cursor: grab; }
.link { color: var(--ink); text-decoration: underline; text-underline-offset: 2px; cursor: pointer; }

/* cells */
.cells { display: grid; gap: 1px; }
.cells i { display: block; aspect-ratio: 1; background: var(--off); border-radius: 1px; }
.cells i.f { background: var(--ink); }
.cells i.y { background: var(--you); }
.cells i.r { background: var(--bad); }
.cells i.g { background: var(--ok); }
.cells i.h { background: repeating-linear-gradient(135deg, var(--ink) 0 1.2px, transparent 1.2px 3.2px), var(--off); }
.cells i.mk { box-shadow: inset 0 0 0 1px var(--you); }
.cells i.l1 { background: color-mix(in srgb, var(--ink) 22%, var(--off)); }
.cells i.l2 { background: color-mix(in srgb, var(--ink) 48%, var(--off)); }
.cells i.l3 { background: color-mix(in srgb, var(--ink) 74%, var(--off)); }
.cells i.l4 { background: var(--ink); }
@media (prefers-reduced-motion: no-preference) { .cells i.live { animation: blink 1.6s steps(2, jump-none) infinite; } }
@keyframes blink { 50% { background: var(--off); } }

/* session chips (the pill) */
.chipcell { position: relative; display: grid; justify-items: center; gap: 1px; border: 0; background: transparent;
  padding: 3px 4px; border-radius: 6px; cursor: pointer; color: var(--ink); }
.chipcell:hover { background: var(--raise); }
.chipcell .cells { grid-template-columns: repeat(5, 3px); }
.chipcell .gl { font: 600 9px/1 var(--mono); color: var(--mut); }
.chipcell .gl.y { color: var(--you); } .chipcell .gl.r { color: var(--bad); } .chipcell .gl.n { color: var(--ink); }
.chipcell .dot { position: absolute; top: 1px; right: 0; width: 6px; height: 6px; background: var(--you); border-radius: 1px; }
.chipcell .dot.r { background: var(--bad); }
.more { font: 500 10px var(--mono); color: var(--mut); padding: 0 2px; }

/* folded: the pill, and one peek card under it */
.peek { width: 100vw; background: var(--win); border-radius: 24px; border: 1px solid var(--edge); overflow: hidden; }
.peek.card-on { border-radius: 16px; }
.pill { height: 46px; display: flex; align-items: center; gap: 6px; padding: 0 6px 0 14px; user-select: none; }
.peek.card-on .pill { border-bottom: 1px solid var(--line); }
.grip { color: var(--mut); letter-spacing: -2px; font-size: 12px; margin-right: 2px; }
.pill .sp { flex: 1; align-self: stretch; }
.pill .big { font: 700 20px/1 var(--dot); letter-spacing: .02em; padding: 0 4px; }
.tb { width: 34px; height: 34px; border: 0; border-radius: 17px; background: transparent; color: var(--mut);
  cursor: pointer; font: 14px var(--ui); display: grid; place-items: center; }
.tb:hover { background: var(--raise); color: var(--ink); }

/* shared pieces */
.askbox { margin: 8px; padding: 10px; border-radius: 8px; background: color-mix(in srgb, var(--you) 9%, var(--win));
  border: 1px solid color-mix(in srgb, var(--you) 40%, transparent); display: grid; gap: 6px; }
.askbox.r { background: color-mix(in srgb, var(--bad) 9%, var(--win));
  border-color: color-mix(in srgb, var(--bad) 40%, transparent); }
.askbox .q { font: 600 15px/1.4 var(--ui); white-space: pre-wrap; overflow-wrap: anywhere; }
.l1 { display: flex; align-items: center; gap: 8px; min-width: 0; }
.t { flex: 1; min-width: 0; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.age { color: var(--mut); white-space: nowrap; }
.st { font: 600 11px var(--mono); white-space: nowrap; letter-spacing: .02em; text-transform: uppercase; }
.st.y { color: var(--you); } .st.r { color: var(--bad); } .st.g { color: var(--ok); } .st.n { color: var(--ink); }
.st.q { color: var(--mut); }
.st .lc { text-transform: none; }
.lr { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.lr input, textarea.in { flex: 1; min-width: 0; font: 13px var(--ui); color: var(--ink); background: var(--raise);
  border: 1px solid var(--line); border-radius: 6px; padding: 6px 9px; }
textarea.in { width: 100%; resize: vertical; }
textarea.in.m { font: 12px/1.45 var(--mono); }
.btn { font: 600 12px var(--ui); color: var(--ink); background: transparent; border: 1px solid var(--line);
  border-radius: 6px; padding: 5px 12px; cursor: pointer; white-space: nowrap; min-height: 32px; }
.btn:hover { border-color: var(--ink); }
.btn:disabled { opacity: .5; cursor: progress; }
.btn.go { background: var(--ink); color: var(--win); border-color: var(--ink); }
.btn.you { background: var(--you); border-color: var(--you); color: var(--on-you); }
.btn.stop { color: var(--bad); }
.btn.sm { min-height: 26px; padding: 2px 9px; font-size: 11px; }
.say { font: 11px var(--mono); color: var(--mut); overflow-wrap: anywhere; }
.say:empty { display: none; }
.say .r { color: var(--bad); }
.kbd { font: 11px var(--mono); color: var(--mut); border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; }
.text { white-space: pre-wrap; overflow-wrap: anywhere; }
.loading { display: flex; gap: 8px; align-items: center; color: var(--mut); font-size: 12px; }
.loading .cells { grid-template-columns: repeat(6, 6px); }
.empty { display: grid; gap: 10px; justify-items: start; padding: 16px 12px 8px; }
.empty .cells { grid-template-columns: repeat(15, 10px); }
.empty p { margin: 0; color: var(--mut); font-size: 13px; max-width: 40ch; text-wrap: pretty; }

/* open window: one column. The window is a CSS container, so the 340 px layout follows its width.
   Spacing scale 4 / 8 / 12 / 16 / 24. */
.win { position: relative; width: 100vw; height: 100vh; background: var(--win); border-radius: 12px;
  border: 1px solid var(--edge); display: flex; flex-direction: column; overflow: hidden; container-type: inline-size; }
.win > section { display: contents; }
.top { height: 36px; flex: none; display: flex; align-items: center; gap: 4px; padding-left: 10px;
  border-bottom: 1px solid var(--line); user-select: none; }
.top .sp { flex: 1; align-self: stretch; min-width: 8px; }
.top .crumb { color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.top [data-winbtns] { display: contents; }
.rb { width: 34px; height: 36px; border: 0; background: transparent; color: var(--mut); cursor: pointer;
  font: 14px var(--ui); display: grid; place-items: center; flex: none; }
.rb:hover { background: var(--raise); color: var(--ink); }
.rb.on { color: var(--ink); }
.rb.x:hover { background: var(--close); color: #fff; }
.rb:disabled { opacity: .35; cursor: default; background: transparent; }
.needs { font: 600 11px var(--mono); color: var(--you); border: 1px solid color-mix(in srgb, var(--you) 45%, transparent);
  background: transparent; border-radius: 4px; padding: 1px 7px; cursor: pointer; white-space: nowrap; margin-left: 4px; flex: none; }
.needs:hover { background: color-mix(in srgb, var(--you) 10%, transparent); }
.scroll { flex: 1; overflow-y: auto; overflow-x: hidden; min-height: 0; min-width: 0; scrollbar-width: thin;
  scrollbar-color: var(--off) transparent; }
.banner { flex: none; display: flex; gap: 8px; align-items: center; padding: 6px 12px;
  background: color-mix(in srgb, var(--bad) 12%, var(--win)); font: 12px var(--ui); border-bottom: 1px solid var(--line); }
.banner b { color: var(--bad); font: 600 11px var(--mono); }
/* single-column grids must never grow past the window: long one-line texts ellipsize instead */
.body, .card, .blk, .askbox, .compose, .levers, .todaymore, .empty, .stack { grid-template-columns: minmax(0, 1fr); }
.stack { display: grid; gap: 14px; align-content: start; padding: 12px; }
/* 340 px: the scope keeps its full name; window buttons, the route on cards and the picker's sort note give way */
@container (max-width: 372px) {
  .top { padding-left: 8px; }
  .top .grip { display: none; }
  .top .rb { width: 26px; }
  .needs { padding: 1px 5px; margin-left: 2px; }
  .today .usd { display: none; }
  .l2 .route { display: none; }
  .pop .foot .sort { display: none; }
  .stats { gap: 0 8px; }
  .stats .cx .cells { flex: none; grid-template-columns: repeat(15, 3px); }
  .stats .cx .cells i { aspect-ratio: 1; height: auto; }
  .stats .ss { display: none; }
  .stats small { font-size: 10px; letter-spacing: -.02em; }
  .log > div { grid-template-columns: 8px 54px 64px minmax(0, 1fr); gap: 6px; font-size: 11px; }
  .tabs { gap: 14px; }
}

/* today strip: one row of cells, 30 cells = the soft daily limit */
.today { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; align-items: center; width: 100%;
  padding: 10px 12px; background: transparent; border: 0; border-bottom: 1px solid var(--line); color: var(--ink);
  font: inherit; text-align: left; cursor: pointer; }
.today:hover { background: color-mix(in srgb, var(--raise) 60%, transparent); }
.today .big { font: 700 30px/.9 var(--dot); letter-spacing: .02em; grid-row: span 2; }
.today .row30 { grid-template-columns: repeat(var(--cols, 30), minmax(0, 1fr)); }
.today .sub { display: flex; justify-content: space-between; gap: 8px; color: var(--mut); min-width: 0; }
.today .sub span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.today .sub span:last-child { flex: none; }
.todaymore { padding: 2px 12px 10px; display: grid; gap: 6px; border-bottom: 1px solid var(--line); }
.legend { display: flex; gap: 12px; flex-wrap: wrap; font: 10.5px var(--mono); color: var(--mut); }
.legend span { display: inline-flex; gap: 5px; align-items: center; }
.legend i { width: 8px; height: 8px; display: inline-block; border-radius: 1px; background: var(--off); }
.legend i.f { background: var(--ink); }
.legend i.h { background: repeating-linear-gradient(135deg, var(--ink) 0 1.2px, transparent 1.2px 3.2px), var(--off); }
.legend i.mk { box-shadow: inset 0 0 0 1px var(--you); }

/* the list: tight inside a group (6 px between cards), generous between groups (20 px above a label) */
.sec { display: flex; justify-content: space-between; align-items: baseline; padding: 20px 12px 6px; }
#list > .sec:first-child { padding-top: 12px; }
.card { margin: 0 8px 6px; padding: 8px 10px; border-radius: 8px; background: var(--raise); border: 1px solid transparent;
  display: grid; gap: 4px; cursor: pointer; text-align: left; }
.card:hover { border-color: var(--line); }
.card.y { border-color: color-mix(in srgb, var(--you) 45%, transparent); background: color-mix(in srgb, var(--you) 7%, var(--raise)); }
.card.r { border-color: color-mix(in srgb, var(--bad) 45%, transparent); }
.card.quiet { background: transparent; padding-block: 3px; gap: 0; }
.card.quiet .t { font-weight: 400; }
/* line 2 is the instrument line, one size down: cost and context sit in fixed columns and line up down the list */
.l2 { display: grid; grid-template-columns: minmax(0, 1fr) 38px 98px; gap: 6px; align-items: center; color: var(--mut); font-size: 11px; }
.l2 .who { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.l2 .cost { text-align: right; color: var(--ink); }
.ctx { display: flex; align-items: center; gap: 6px; justify-content: flex-end; }
.ctx .cells { grid-template-columns: repeat(15, 3px); }
.ctx b { font-weight: 400; width: 30px; text-align: right; }
.ctx b.y { color: var(--you); } .ctx b.r { color: var(--bad); }
.doing { display: flex; align-items: center; gap: 6px; color: var(--mut); white-space: nowrap; overflow: hidden; }
.doing .cells { grid-template-columns: 6px; flex: none; }
.doing span:last-child { color: var(--ink); overflow: hidden; text-overflow: ellipsis; }
.card .q { font-size: 13px; overflow-wrap: anywhere; }
.more-done { padding: 0 12px 12px; }

/* composer: the task box takes the whole width; the target project sits under it as a chip of the same family as the scope */
.compose { flex: none; border-top: 1px solid var(--line); padding: 8px 10px; display: grid; gap: 6px; }
.compose .lr { flex-wrap: nowrap; }
.compose textarea { flex: 1; min-width: 0; resize: none; field-sizing: content; min-height: 34px; max-height: 140px;
  font: 13px var(--ui); background: var(--raise); border: 1px solid transparent; border-radius: 6px; padding: 7px 9px; }
.compose textarea:disabled { opacity: .55; }
.compose .say { font: 12px var(--ui); display: flex; gap: 8px; align-items: center; flex-wrap: wrap; min-height: 24px; }
.compose .say .hint { margin-left: auto; font: 11px var(--mono); white-space: nowrap; }
.compose .say .hint .kbd { margin-right: 4px; }
.tgt { display: inline-flex; align-items: center; gap: 5px; height: 24px; font: 600 11px var(--mono); color: var(--ink);
  background: transparent; border: 1px solid var(--line); border-radius: 5px; padding: 0 7px; cursor: pointer; max-width: 200px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tgt:hover { border-color: var(--ink); }
.tgt .car { color: var(--mut); font-size: 9px; }

/* project picker: a page-drawn popover under the header, never a native select */
.scope { display: flex; align-items: center; gap: 6px; min-width: 0; max-width: 170px; height: 28px; padding: 0 8px;
  border: 1px solid var(--line); border-radius: 6px; background: transparent; color: var(--ink); font: 600 12px var(--mono);
  cursor: pointer; flex: 0 1 auto; }
.scope:hover, .scope[aria-expanded="true"] { border-color: var(--ink); }
.scope .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.scope .car { color: var(--mut); font-size: 10px; }
.pop { position: absolute; top: 40px; left: 8px; right: 8px; z-index: 5; max-height: calc(100% - 56px); display: flex;
  flex-direction: column; background: var(--win); border: 1px solid var(--line); border-radius: 10px;
  box-shadow: 0 24px 60px rgb(0 0 0 / 45%); overflow: hidden; }
.pop .find { flex: none; display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--line); }
.pop .find input { flex: 1; min-width: 0; font: 13px var(--ui); color: var(--ink); background: var(--raise);
  border: 1px solid transparent; border-radius: 6px; padding: 6px 9px; }
.pop .rows { overflow-y: auto; padding: 4px 0 6px; scrollbar-width: thin; scrollbar-color: var(--off) transparent; }
.pop .grp { padding: 8px 12px 3px; }
.prow { display: grid; grid-template-columns: 14px minmax(0, 1fr) auto 44px; gap: 8px; align-items: center; width: 100%;
  padding: 5px 12px; border: 0; background: transparent; color: var(--ink); font: 13px var(--ui); text-align: left; cursor: pointer; }
.prow:hover, .prow.hi { background: var(--raise); }
.prow .ck { font: 11px var(--mono); color: var(--ink); }
.prow .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.prow .meta { font: 11px var(--mono); color: var(--mut); white-space: nowrap; }
.prow .meta.y { color: var(--you); }
.prow .c { font: 11px var(--mono); text-align: right; color: var(--mut); }
.prow.off .nm { color: var(--mut); }
.pop .none { padding: 10px 12px; color: var(--mut); font-size: 13px; }
.pop .foot { flex: none; border-top: 1px solid var(--line); padding: 6px 12px; display: flex; gap: 12px; font: 10.5px var(--mono); color: var(--mut); }
.pop .foot span { white-space: nowrap; }
.pop .foot .sort { margin-left: auto; }

/* session page: the head reads first, then the ask (or the denial), then one brief that folds the instruments,
   then the process, which takes the rest of the height. Rhythm: 4 px inside the head, 12 px between blocks. */
.scroll.sess { display: flex; flex-direction: column; }
.body { padding: 12px 12px 0; display: grid; gap: 12px; align-content: start; flex: none; }
.body > * { min-width: 0; }
.head { display: grid; gap: 4px; }
h2 { font: 600 17px/1.3 var(--ui); margin: 0; text-wrap: balance; overflow-wrap: anywhere; }
.where { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-top: 2px; min-width: 0; }
.where .m { flex: 1; min-width: 0; color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.where .btn { flex: none; }
.note { margin: 0; color: var(--mut); overflow-wrap: anywhere; }
.note .y { color: var(--you); } .note .r { color: var(--bad); }
.body .askbox, .body .card { margin: 0; }
.body .card { cursor: default; }
.denied { font: 12px var(--mono); overflow-wrap: anywhere; }
/* the brief: one button, read in one glance (path, then one line of figures in fixed columns).
   Click or Space opens the details in the same block; nothing in them changes meaning */
.bwrap { border-radius: 8px; background: var(--raise); border: 1px solid transparent; }
.bwrap:hover { border-color: var(--line); }
.brief { display: grid; gap: 10px; width: 100%; padding: 8px 10px 9px; border: 0; border-radius: 8px; background: transparent;
  color: var(--ink); font: inherit; text-align: left; cursor: pointer; }
.path { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)) 12px; gap: 6px; align-items: end; }
.path > span { display: grid; gap: 4px; min-width: 0; font: 500 11px/1.2 var(--mono); color: var(--mut); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
.path .cells { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.path .cells i { aspect-ratio: auto; height: 4px; }
.path .cur { color: var(--ink); font-weight: 600; } .path .ok { color: var(--ok); } .path .bad { color: var(--bad); }
.path > .car { font: 11px/1.2 var(--mono); text-align: right; }
.brief:hover .car, .brief[aria-expanded="true"] .car { color: var(--ink); }
.stats { display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto auto; gap: 0 10px; align-items: end; }
.stats > span { display: grid; gap: 4px; min-width: 0; }
.stats small { font: 10.5px/1 var(--mono); color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stats small.y { color: var(--you); } .stats small.r { color: var(--bad); }
.stats b { font: 500 12px/18px var(--mono); white-space: nowrap; font-variant-numeric: tabular-nums; }
.stats b.usd { font: 700 22px/18px var(--dot); letter-spacing: .02em; }
.stats b.usd .est { font: 500 13px var(--mono); color: var(--mut); margin-right: 1px; }
.stats .cx { display: flex; align-items: center; gap: 5px; min-width: 0; height: 18px; }
.stats .cx .cells { flex: 1; min-width: 0; grid-template-columns: repeat(30, minmax(0, 1fr)); }
.stats .cx .cells i { aspect-ratio: auto; height: 7px; }
.stats .cx b { flex: none; width: 30px; text-align: right; }
.stats b.y { color: var(--you); } .stats b.r { color: var(--bad); }
.more { border-top: 1px solid var(--line); padding: 10px 10px 12px; display: grid; gap: 14px; }
.blk { display: grid; gap: 5px; }
.blk .hd, .tl .hd { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.blk .hd .m, .tl .hd .m { color: var(--mut); white-space: nowrap; }
.scale { display: flex; justify-content: space-between; font: 10px var(--mono); color: var(--mut); }
.agents { display: grid; gap: 6px; }
.agent { display: grid; grid-template-columns: 96px minmax(0, 1fr) 30px 40px; gap: 8px; align-items: center; }
.agent .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.agent .cells { grid-template-columns: repeat(24, minmax(0, 1fr)); }
.agent span:nth-child(n+3) { text-align: right; color: var(--mut); }
.agent span.c { color: var(--ink); }
.act30 { grid-template-columns: repeat(30, minmax(0, 1fr)); }
/* the process: tabs, then one pane that scrolls on its own and never drops below 200 px */
.proc { flex: 1 1 0; min-height: 200px; display: flex; flex-direction: column; margin-top: 8px; }
.tabs { flex: none; display: flex; gap: 16px; padding: 0 12px; border-bottom: 1px solid var(--line); }
.tabs button { font: 12px var(--ui); color: var(--mut); background: transparent; border: 0; padding: 0; min-height: 32px;
  cursor: pointer; white-space: nowrap; }
.tabs button:hover { color: var(--ink); }
.tabs button[aria-selected="true"] { color: var(--ink); font-weight: 600; box-shadow: inset 0 -2px var(--ink); }
.tabs .n { font: 11px var(--mono); }
.pane { flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; padding: 8px 12px 12px; scrollbar-width: thin;
  scrollbar-color: var(--off) transparent; }
.pane .none { margin: 4px 0 0; color: var(--mut); font-size: 13px; }
.log { display: grid; gap: 1px; }
.log > div { display: grid; grid-template-columns: 8px 58px 80px minmax(0, 1fr); gap: 8px; align-items: center;
  font: 11.5px/19px var(--mono); color: var(--mut); font-variant-numeric: tabular-nums; }
.log > div > span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.log > div > span:last-child { color: var(--ink); }
.log > div.r > span:last-child { color: var(--bad); }
.log .cells { grid-template-columns: 6px; }
.log .st { font-size: 11px; }
.alist { display: grid; gap: 12px; }
.arow { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto auto 34px; gap: 2px 8px; align-items: center; }
.arow .cells { grid-template-columns: 6px; }
.arow .nm { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.arow .m { color: var(--mut); white-space: nowrap; }
.arow .m.c { color: var(--ink); text-align: right; }
.arow .last { grid-column: 2 / -1; color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.arow .last span { color: var(--ink); }
.tl { display: grid; gap: 6px; }
.tl .mins { display: grid; grid-template-columns: repeat(30, minmax(0, 1fr)); gap: 2px; }
.tl .mins button { display: block; padding: 0; border: 0; background: transparent; cursor: pointer; border-radius: 2px; }
.tl .mins i { display: block; height: 22px; border-radius: 1px; background: var(--off); }
.tl .mins i.l1 { background: color-mix(in srgb, var(--ink) 22%, var(--off)); }
.tl .mins i.l2 { background: color-mix(in srgb, var(--ink) 48%, var(--off)); }
.tl .mins i.l3 { background: color-mix(in srgb, var(--ink) 74%, var(--off)); }
.tl .mins i.l4 { background: var(--ink); }
.tl .mins button[aria-pressed="true"] { outline: 1px solid var(--ink); outline-offset: 1px; }
.tl .mins button:focus-visible { outline-width: 2px; }
.tl .hd.at { margin-top: 8px; }
.chat { display: grid; gap: 12px; }
.turn { display: grid; gap: 3px; }
.turn p { margin: 0; font-size: 13px; line-height: 1.45; text-wrap: pretty; white-space: pre-wrap; overflow-wrap: anywhere; }
.turn.you { padding-left: 9px; border-left: 2px solid var(--line); }
.turn.note p, .turn.result p { color: var(--mut); font: 12px var(--mono); }
.chat .src { font: 11px var(--mono); color: var(--mut); margin: 0; }
.levers { flex: none; border-top: 1px solid var(--line); padding: 8px 10px; display: grid; gap: 6px; }
.levers:empty { display: none; }

/* Prep page */
.prep-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.prep-row select { background: var(--raise); border: 1px solid var(--line); border-radius: 6px; padding: 4px; font: 12px var(--mono); }

/* window buttons only exist in the pywebview window */
html:not(.native) .native-only { display: none; }
```

- [ ] **Step 3: Replace `web/app.js` with:**

```javascript
// Claude Console window, Cells Drawer (BRAINSTORM 7.5): a folded pill with one peek card, or one open
// column: the list (needs you / working / done today), a session page, or the Prep page. A project
// picker in the header scopes the list and sets where a new task runs. Renders /api/stream snapshots;
// the levers, Prep and runs go through the same routes as phases 2-4.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const RESUME_TEXT = "You were interrupted. Check `git diff` first, then finish the task.";
const BUSY = new Set(["running", "quiet", "stall"]);
const PEEK = new Set(["stop", "blocked", "failed", "interrupted"]);  // a new one opens the peek card
const SPEND_CELL = 0.5;   // 1 spend cell = $0.50
const PILL_CHIPS = 9;
const DONE_SHOWN = 2;     // done sessions listed before "Show N more"
const TABS = [["steps", "Steps"], ["agents", "Agents"], ["timeline", "Timeline"], ["chat", "Chat"]];

let snap = null;
let cfg = null;          // /api/config
let live = false;
let form = "open";       // open | pill
let page = "list";       // list | session | prep
let openId = null;
let tab = "steps";       // steps | agents | timeline | chat
let tlMin = -1;          // the Timeline's selected minute (minutes since 1970; -1: the last busy one)
let scope = "";          // the project folder the list shows ("" = all projects)
let project = "";        // where a new task runs (window.json, through /api/draft)
let card = null;         // the Prep card on screen
let busy = "";           // what the compose box waits for ("" = nothing)
let fail = null;         // {title, msg, retry} shown above the compose box
let draft = "";
let briefOpen = false;   // the session page's brief, open for the window (window.json)
let doneOpen = false;
let hi = 0;              // the picker's highlighted row
let draftTimer = null;
let onTop = true;
let peekKey = "";        // the event the peek card shows
let firstSnap = true;
let procSeq = 0;         // the newest process render; older ones are dropped
let procShown = "";      // session|tab the process pane shows now
let leversSig = "";
const seen = new Set();  // peek events already shown, answered or dismissed
const sent = {};         // "session|question" -> the session that runs the answer ("" = same one)
const cardMsg = {};      // session -> the last error of a list card

// -- helpers ---------------------------------------------------------------------------
function native() { return !!(window.pywebview && window.pywebview.api); }
function money(x) { return Number(x || 0).toFixed(2); }
function spentText(s) { return s.spent == null ? "&ndash;" : (s.spent_exact ? "" : "~") + money(s.spent); }
function kTokens(n) { return n >= 1000 ? Math.round(n / 1000) + "K" : String(n || 0); }
function two(n) { return String(n).padStart(2, "0"); }
function hhmm(ts) { return new Date(ts * 1000).toTimeString().slice(0, 5); }
function hms(ts) { return new Date(ts * 1000).toTimeString().slice(0, 8); }
function ago(sec) {
  sec = Math.max(0, Math.round(sec));
  if (sec < 60) return sec + "s";
  const min = Math.floor(sec / 60);
  if (min < 60) return min + "m" + (min < 10 && sec % 60 ? " " + (sec % 60) + "s" : "");
  return Math.floor(min / 60) + "h " + (min % 60) + "m";
}
function agoLong(sec) {  // the picker: 5m ago, 3h ago, 2d ago, 1w ago
  const min = Math.max(0, Math.round(sec / 60));
  if (min < 60) return min + "m ago";
  if (min < 1440) return Math.round(min / 60) + "h ago";
  if (min < 10080) return Math.round(min / 1440) + "d ago";
  return Math.round(min / 10080) + "w ago";
}
function elapsed(sec) {  // minutes and seconds under an hour; the seconds fall away in a narrow window
  sec = Math.max(0, Math.round(sec));
  if (sec >= 3600) return `${Math.floor(sec / 3600)}h ${two(Math.floor(sec % 3600 / 60))}m`;
  return `${Math.floor(sec / 60)}m<span class="ss"> ${two(sec % 60)}s</span>`;
}
function kb(bytes) { return (bytes / 1000).toFixed(1) + " KB"; }
function baseName(p) { return String(p || "").split(/[\\/]/).filter(Boolean).pop() || p; }
function alias(model) { return (String(model || "").match(/fable|opus|sonnet|haiku/) || [model || ""])[0]; }
function label(s) { return s.state === "stop" ? "Asks you" : s.text; }
function tone(s) {  // orange only for "needs you", red and green only for state
  if (s.state === "blocked" || s.state === "failed") return "r";
  if (s.group === "needs") return "y";
  if (s.state === "done") return "g";
  return s.state === "running" ? "n" : "q";
}
function stateWord(s) {  // [glyph, word, tone]; a finished session says its verdict
  if (s.group === "done" && s.verdict === "PASS") return ["✓", "PASS", "g"];
  if (s.group === "done" && s.verdict === "FAIL") return ["×", "FAIL", "r"];
  return [s.symbol, label(s), tone(s)];
}
function cellsHtml(classes) { return classes.map((c) => `<i${c ? ` class="${c}"` : ""}></i>`).join(""); }
function liveSessions() { return snap ? snap.sessions.filter((s) => s.group !== "done")
  .sort((a, b) => (a.group === "needs" ? 0 : 1) - (b.group === "needs" ? 0 : 1)) : []; }
function current() { return snap && snap.sessions.find((s) => s.id === openId); }
function routeText(s) {
  const run = [alias(s.model), s.effort].filter(Boolean).join(" ");
  if (s.route === "unrouted") return run ? "unrouted · " + run : "unrouted";
  return run ? s.route + " · " + run : s.route;
}
function tlBase() { return Math.floor(snap.now / 60) - 29; }  // the minute of the Timeline's first cell
function projectName(dir) {
  const p = snap && snap.projects.find((x) => x.dir === dir);
  return (p && p.name) || baseName(dir);
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "X-CC": "1", "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const resp = await fetch(path, opts);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || "HTTP " + resp.status);
  return data;
}

// Replace an element's content only when it changed, and keep what the person is doing in it: typed text,
// the focused control and the scroll position of one inner scroller ({sel, end, reset}).
function focusKey(el) {
  if (el.id) return `[id="${el.id}"]`;
  for (const k of ["tab", "min", "open"]) if (el.dataset[k] !== undefined) return `[data-${k}="${el.dataset[k]}"]`;
  return "";
}
function setHtml(el, html, scroller) {
  if (el._html === html) return false;
  const active = document.activeElement, key = active && el.contains(active) ? focusKey(active) : "";
  const fields = [...el.querySelectorAll("input[id],textarea[id]")].map((f) => [f.id, f.value, f.selectionStart, f.selectionEnd]);
  const old = scroller && el.querySelector(scroller.sel);
  const top = old ? old.scrollTop : 0, atEnd = old ? old.scrollTop + old.clientHeight >= old.scrollHeight - 4 : false;
  el.innerHTML = html;
  el._html = html;
  for (const [id, value, a, b] of fields) {
    const f = $(id);
    if (f && f.value !== value) { f.value = value; try { f.setSelectionRange(a, b); } catch (e) { /* not a text field */ } }
  }
  const now = scroller && el.querySelector(scroller.sel);
  if (now) now.scrollTop = scroller.reset || (scroller.end && atEnd) ? (scroller.end ? now.scrollHeight : 0) : top;
  if (key) { const f = el.querySelector(key); if (f) f.focus({ preventScroll: true }); }
  return true;
}

// -- cells -----------------------------------------------------------------------------
function ctxClasses(tokens) {  // 30 cells up to the red threshold; from yellow on is the hand-off zone
  const [yellow, red] = cfg ? cfg.gauge : [150000, 300000];
  const per = red / 30, half = Math.round(yellow / per);
  const n = tokens == null ? 0 : Math.min(30, Math.round(tokens / per));
  return Array.from({ length: 30 }, (_, k) => k < n ? (tokens >= red ? "r" : k >= half ? "y" : "f") : "");
}
function chipCells(tokens) {  // 5 x 6, filled from the bottom row up
  const order = ctxClasses(tokens), rows = [];
  for (let r = 0; r < 6; r++) rows.unshift(order.slice(r * 5, r * 5 + 5));
  return cellsHtml(rows.flat());
}
function activityCells(levels) { return cellsHtml(levels.map((v) => v ? "l" + v : "")); }
function ctxTone(s) { return s.ctx_tone === "red" ? "r" : s.ctx_tone === "yellow" ? "y" : ""; }
function ctxMini(s) {  // the card's context: 15 x 2 cells and the figure
  return `<span class="ctx"><span class="cells">${cellsHtml(ctxClasses(s.ctx_tokens))}</span>
    <b class="${ctxTone(s)}">${s.ctx_tokens == null ? "?" : kTokens(s.ctx_tokens)}</b></span>`;
}

function chip(s) {
  const t = tone(s), flag = s.group === "needs" ? `<span class="dot${t === "r" ? " r" : ""}"></span>` : "";
  return `<button class="chipcell" data-open="${esc(s.id)}" title="${esc(label(s) + ": " + s.title)}">
    <span class="cells">${chipCells(s.ctx_tokens)}</span>
    <span class="gl ${t === "y" || t === "r" ? t : ""}">${s.symbol}</span>${flag}</button>`;
}

// -- forms: pill / open ------------------------------------------------------------------
async function setForm(name) {
  form = name;
  $("folded").hidden = name !== "pill";
  $("open").hidden = name !== "open";
  if (name === "pill") renderFolded(true);
  else if (native()) await window.pywebview.api.form("open");
  render();
}

async function fitPill() {
  if (native() && form === "pill") await window.pywebview.api.form("pill", Math.ceil($("folded").getBoundingClientRect().height));
}

function renderFolded(resize) {
  if (!snap) return;
  const rail = liveSessions(), more = rail.length - PILL_CHIPS;
  $("pill").innerHTML = `<span class="grip pywebview-drag-region" title="Drag to move">&#8942;&#8942;</span>
    ${rail.slice(0, PILL_CHIPS).map(chip).join("")}${more > 0 ? `<span class="more">+${more}</span>` : ""}
    <span class="sp pywebview-drag-region" title="Drag to move; double-click to open"></span>
    <span class="big" title="Today, USD">${money(snap.spend.today)}</span>
    <button class="tb" data-go="unfold" aria-label="Open" title="Open (double-click the pill)">&#8964;</button>`;
  const found = snap.sessions.filter((s) => PEEK.has(s.state)).sort((a, b) => a.last_ts - b.last_ts)
    .find((s) => !seen.has(peekId(s)));
  const key = found ? peekId(found) : "";
  if (key !== peekKey || resize) {
    peekKey = key;
    $("peek").innerHTML = found ? peekCard(found) : "";
    $("folded").classList.toggle("card-on", !!found);
    fitPill();
  }
}

function peekId(s) { return `${s.id}|${s.state}|${s.turn_ts}`; }

// What a session that needs Fred says, and the buttons that unblock it (the peek card and the list card).
function needText(s) {
  if (s.state === "blocked" && s.denied) return `denied: ${s.denied.tool} ${s.denied.what}`;
  if (s.state === "failed" && s.failed) return `${s.failed.error} ${s.failed.details || ""}`.trim();
  if (s.state === "interrupted") return "The run stopped before it finished.";
  if (s.state === "stall") return "no events for 10 min, still running";
  if (s.ctx_tone === "red") return `context ${kTokens(s.ctx_tokens)}: hand off`;
  return "";
}
function needButtons(s, where, withOpen) {
  const b = (name, cls, text) => `<button class="btn${cls} sm" data-do="${name}" data-sid="${esc(s.id)}" data-where="${where}">${text}</button>`;
  let out = "";
  if (s.state === "blocked" && s.window && !s.run_live) out += b("terminal", "", "Open in terminal");
  if (s.state === "interrupted" && s.window) out += b("resume", " you", "Resume");
  return out + (withOpen ? b("open", "", "Open") : "");
}

function peekCard(s) {
  const t = tone(s), age = `<span class="age m">${ago(snap.now - s.last_ts)}</span>`;
  const head = `<div class="l1"><span class="st ${t}">${s.symbol} ${esc(label(s))}</span><span class="t">${esc(s.title)}</span>${age}</div>`;
  if (s.state === "stop") {
    return `<div class="askbox">${head}<div class="q">${esc(s.stop_question)}</div>
      <div class="lr"><input id="pk" aria-label="Answer" placeholder="Type your answer">
      <button class="btn you sm" data-do="send" data-sid="${esc(s.id)}" data-where="peek">Send answer</button></div><div id="pk-msg" class="say"></div></div>`;
  }
  return `<div class="askbox${t === "r" ? " r" : ""}">${head}<div class="q">${esc(needText(s))}</div>
    <div class="lr">${needButtons(s, "peek", true)}</div><div id="pk-msg" class="say"></div></div>`;
}

function dismissPeek() {
  if (!peekKey) return;
  seen.add(peekKey);
  renderFolded(true);
}

// send / terminal / resume / open from a peek card or a list card
async function unblock(button) {
  const name = button.dataset.do, peek = button.dataset.where === "peek";
  const s = snap && snap.sessions.find((x) => x.id === button.dataset.sid);
  if (!s) { if (peek) dismissPeek(); return; }
  if (name === "open") { if (peek) dismissPeek(); openSession(s.id); return; }
  const field = name === "send" ? $(peek ? "pk" : "ca-" + s.id) : null;
  const text = field ? field.value.trim() : "";
  if (name === "send" && !text) return;
  button.disabled = true;
  try {
    let r = null;
    if (name === "send") r = await api("/api/continue", { session: s.id, text });
    if (name === "resume") await api("/api/continue", { session: s.id, text: RESUME_TEXT });
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (peek) return dismissPeek();
    delete cardMsg[s.id];
    if (r) { sent[s.id + "|" + s.stop_question] = r.session === s.id ? "" : r.session; field.value = ""; }
    render();
  } catch (e) {
    button.disabled = false;
    if (peek) { $("pk-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`; fitPill(); }
    else { cardMsg[s.id] = e.message; render(); }
  }
}

function renderOnTop() {
  document.querySelectorAll('[data-go="ontop"]').forEach((b) => {
    b.classList.toggle("on", onTop);
    b.title = `Always on top (${onTop ? "on" : "off"})`;
  });
}

// -- pages -------------------------------------------------------------------------------
function showPage(name) {
  page = name;
  closePicker();
  document.querySelectorAll("[data-page]").forEach((p) => { p.hidden = p.dataset.page !== name; });
  leversSig = "";
  procShown = "";
  if (name === "session") $("sscroll").scrollTop = 0;
  render();
}

async function openSession(id, list = "steps") {
  if (form === "pill") await setForm("open");
  openId = id;
  tab = list;
  tlMin = -1;
  const s = current();
  if (s && s.project_dir) project = s.project_dir;
  showPage("session");
}

function inScope(s) { return !scope || s.project_dir === scope; }
function groups() {
  const mine = snap.sessions.filter(inScope);
  return { needs: mine.filter((s) => s.group === "needs"), work: mine.filter((s) => s.group === "working"),
    done: mine.filter((s) => s.group === "done").sort((a, b) => b.last_ts - a.last_ts) };
}
function navList() {  // the sessions ‹ › step through: the list in its order, or all when the open one is out of scope
  const g = groups(), all = [...g.needs, ...g.work, ...g.done];
  if (all.some((s) => s.id === openId)) return all;
  return [...snap.sessions].sort((a, b) => (a.group === "needs" ? 0 : 1) - (b.group === "needs" ? 0 : 1));
}

function render() {
  if (!snap) return;
  $("banner").hidden = live;
  if (firstSnap) {  // only events after the window opened bring up the peek card
    snap.sessions.filter((s) => PEEK.has(s.state)).forEach((s) => seen.add(peekId(s)));
    firstSnap = false;
  }
  if (form === "pill") { renderFolded(false); return; }
  snap.sessions.filter((s) => PEEK.has(s.state)).forEach((s) => seen.add(peekId(s)));  // seen while open
  if (page === "list") renderListPage();
  else if (page === "session") renderSession();
}

// -- list page ---------------------------------------------------------------------------
function spendRow(sp) {  // one row: solid = exact, hatched = estimated, orange outline at 80 % of the limit
  const solid = Math.round(sp.exact / SPEND_CELL), all = Math.round(sp.today / SPEND_CELL);
  const mark = sp.budget > 0 ? Math.ceil(sp.budget * 0.8 / SPEND_CELL) - 1 : -1;
  const cols = Math.max(30, all, mark + 1);
  const cls = Array.from({ length: cols }, (_, k) =>
    [k < solid ? "f" : k < all ? "h" : "", k === mark ? "mk" : ""].filter(Boolean).join(" "));
  return { cols, html: cellsHtml(cls) };
}

function renderTop() {
  const n = snap.counts.needs;
  $("needsbtn").hidden = !n;
  $("needsbtn").textContent = `${n} ${n === 1 ? "needs" : "need"} you`;
  $("scopenm").textContent = scope ? projectName(scope) : "All projects";
  const sp = snap.spend, row = spendRow(sp);
  setHtml($("today"), `<span class="big">${money(sp.today)}</span><span class="cells row30" style="--cols:${row.cols}">${row.html}</span>
    <span class="sub m"><span>today<span class="usd">, USD</span> · $${money(sp.burn)} / min</span>
    <span>${sp.budget > 0 ? "limit $" + sp.budget : "no limit"}</span></span>`);
  setHtml($("todaymore"), `<div class="legend"><span><i class="f"></i>exact $${money(sp.exact)}</span>
    <span><i class="h"></i>estimated $${money(sp.estimated)}</span>${sp.budget > 0 ? '<span><i class="mk"></i>80 % of limit</span>' : ""}</div>
    <div class="legend"><span>1 cell = $0.50</span>${sp.models.map(([m, f]) => `<span>${esc(m)} ${f < 0.01 ? "&lt;1" : Math.round(f * 100)} %</span>`).join("")}
    ${sp.runs ? `<span>window runs ${sp.runs}</span>` : ""}
    ${snap.writers.map((w) => `<span>2 writers: ${esc(baseName(w.project_dir))}</span>`).join("")}</div>`);
}

function cardHtml(s) {
  const t = tone(s), key = s.id + "|" + s.stop_question;
  let third = "";
  if (s.state === "stop" && key in sent) {
    const to = sent[key];
    third = `<div class="m mut" data-stay>Answer sent. ${to ? `It runs in a window copy: <span class="link" data-open="${esc(to)}">open it</span>` : "It continues here."}</div>`;
  } else if (s.state === "stop") {
    third = `<div class="q">${esc(s.stop_question)}</div><div class="lr" data-stay><input id="ca-${esc(s.id)}" aria-label="Answer" placeholder="Type your answer">
      <button class="btn you sm" data-do="send" data-sid="${esc(s.id)}" data-where="card">Send</button></div>`;
  } else {
    const text = s.group === "needs" ? needText(s) : "", buttons = s.group === "needs" ? needButtons(s, "card", false) : "";
    const agent = s.agents.find((a) => a.text === "Running");
    third = (text ? `<div class="m mut">${esc(text)}</div>` : "") + (buttons ? `<div class="lr" data-stay>${buttons}</div>` : "");
    if (s.state === "running" && (s.doing || agent)) {
      third += `<div class="doing m"><span class="cells"><i class="f live"></i></span><span>${esc(agent ? agent.type : "main")}</span>
        <span>${esc(agent ? agent.doing : s.doing)}</span></div>`;
    }
  }
  if (cardMsg[s.id]) third += `<div class="say" data-stay><span class="r">${esc(cardMsg[s.id])}</span></div>`;
  const hand = s.handoff_hint ? ` <span class="st ${s.ctx_tone === "red" ? "r" : "q"}">· HAND OFF</span>` : "";
  return `<div class="card${t === "y" || t === "r" ? " " + t : ""}" data-open="${esc(s.id)}" tabindex="0" role="button"
    aria-label="${esc(label(s) + ": " + s.title)}">
    <div class="l1"><span class="st ${t}">${s.symbol} ${esc(label(s))}${hand}</span><span class="t">${esc(s.title)}</span>
    <span class="age m">${ago(snap.now - s.last_ts)}</span></div>
    <div class="l2 m"><span class="who">${esc(s.project)}${s.two_writers ? " · 2 writers" : ""}<span class="route"> · ${esc(routeText(s))}</span></span>
    <span class="cost">${spentText(s)}</span>${ctxMini(s)}</div>${third}</div>`;
}

function quietHtml(s, showProject) {
  const [glyph, word, t] = stateWord(s);
  return `<div class="card quiet" data-open="${esc(s.id)}" tabindex="0" role="button" aria-label="${esc(word + ": " + s.title)}">
    <div class="l1"><span class="st ${t}">${glyph} ${esc(word)}</span><span class="t">${esc(s.title)}${showProject ? ` <span class="m mut">· ${esc(s.project)}</span>` : ""}</span>
    <span class="age m">${spentText(s)}</span></div></div>`;
}

function renderListPage() {
  renderTop();
  const g = groups(), shown = doneOpen ? g.done : g.done.slice(0, DONE_SHOWN);
  const sec = (cls, text, list, id = "") => list.length ? `<div class="sec"${id ? ` id="${id}"` : ""}><span class="lbl ${cls}">${text} · ${list.length}</span></div>` : "";
  let html = sec("y", "Needs you", g.needs, "needsec") + g.needs.map(cardHtml).join("")
    + sec("", "Working", g.work) + g.work.map(cardHtml).join("")
    + sec("", "Done today", g.done) + shown.map((s) => quietHtml(s, !scope)).join("")
    + (g.done.length > DONE_SHOWN && !doneOpen ? `<div class="more-done"><button class="btn sm" data-go="moredone">Show ${g.done.length - DONE_SHOWN} more</button></div>` : "");
  if (!g.needs.length && !g.work.length && !g.done.length) {
    html = scope
      ? `<div class="sec"><span class="lbl">${esc(projectName(scope))}</span></div><div class="empty"><div class="cells">${cellsHtml(Array(30).fill(""))}</div>
         <p>No session in ${esc(projectName(scope))} today. Type a task below, or pick All projects.</p></div>`
      : `<div class="empty"><div class="cells">${cellsHtml(Array(30).fill(""))}</div>
         <p>No Claude Code session in the last 24 hours. Start one in VS Code or a terminal, or type a task below.</p></div>`;
  }
  setHtml($("list"), html);
  renderCompose();
}

// -- compose -----------------------------------------------------------------------------
function runnable() { return !!cfg && cfg.claude && cfg.projects.includes(project); }

function renderCompose() {
  if (!project || !projectKnown(project)) project = (cfg && cfg.projects[0]) || (snap && snap.projects[0] && snap.projects[0].dir) || "";
  if (!snap) return;
  const box = $("c-prompt");
  box.disabled = !!busy || !runnable();
  box.placeholder = runnable() ? "New task" : "Allow runs first";
  const chipHtml = `<button class="tgt" data-pick title="Change project (Ctrl+P)">${esc(projectName(project))}<span class="car">&#9662;</span></button>`;
  let html;
  if (busy) html = `<span class="loading"><span class="cells">${cellsHtml(["f", "", "", "", "", ""])}</span>${esc(busy)}</span>`;
  else if (cfg && !cfg.claude) html = '<span class="r">claude.exe not found: set "claude_exe" in config.json</span>';
  else if (!project) html = "To run: start a Claude Code session in a project first";
  else if (!runnable()) html = `<span>Runs are off in ${chipHtml}: a run would use this repo's hooks and settings without asking.</span>
    <button class="btn sm" data-go="allow">Allow runs</button>`;
  else html = `<span>in</span>${chipHtml}<span class="hint"><span class="kbd">Enter</span>Prep</span>`;
  setHtml($("c-say"), html);
  setHtml($("prepfail"), fail ? `<div class="card r" style="cursor:default"><div class="l1"><span class="st r">× FAILED</span><span class="t">${esc(fail.title)}</span></div>
    <div class="m mut">${esc(fail.msg)}</div>${fail.retry ? '<div class="lr"><button class="btn go sm" data-go="retry">Try again</button></div>' : ""}</div>` : "");
}

let loadingTimer = null;
function setBusy(text) {
  busy = text;
  fail = null;
  clearInterval(loadingTimer);
  if (text && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    let k = 0;
    loadingTimer = setInterval(() => {
      document.querySelectorAll(".loading .cells i").forEach((c, j) => { c.className = j === k % 6 ? "f" : ""; });
      k++;
    }, 300);
  }
  renderCompose();
}

function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => api("/api/draft", { text: draft, project, brief: briefOpen }).catch(() => {}), 600);
}

async function doPrep() {
  const text = $("c-prompt").value.trim();
  if (!text || busy || !runnable()) return;
  setBusy(`Haiku is reading ${projectName(project)}, 10 to 30 s`);
  try {
    card = await api("/api/prep", { project_dir: project, prompt: text });
    setBusy("");
    showPrep();
  } catch (e) {
    setBusy("");
    fail = { title: "Prep failed", msg: e.message, retry: "prep" };
    renderCompose();
  }
}

async function doRun(projectDir, prompt, model, effort, prepId) {
  if (busy) return;
  setBusy("Starting the run ...");
  try {
    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "" });
    draft = "";
    $("c-prompt").value = "";
    saveDraft();
    card = null;
    setBusy("");
    openSession(r.session, "chat");
  } catch (e) {
    setBusy("");
    if (page === "prep") $("p-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`;
    else { fail = { title: "Run failed", msg: e.message, retry: "raw" }; renderCompose(); }
  }
}

async function allowRuns(button) {
  if (button) button.disabled = true;
  try {
    cfg.projects = (await api("/api/allow", { project_dir: project })).projects;
    fail = null;
    renderCompose();
    $("c-prompt").focus();
  } catch (err) {
    fail = { title: "Allow runs failed", msg: err.message, retry: "" };
    renderCompose();
  }
}

// -- project picker ------------------------------------------------------------------------
function projectKnown(dir) { return !!snap && ((!!cfg && cfg.projects.includes(dir)) || snap.projects.some((p) => p.dir === dir)); }

function projectRows() {  // allowed folders and every folder a session ran in, with what goes on there
  const by = new Map();
  const row = (dir) => { if (!by.has(dir)) by.set(dir, { dir, name: baseName(dir), on: cfg.projects.includes(dir), last: 0, today: 0, live: 0, needs: 0 }); return by.get(dir); };
  cfg.projects.forEach(row);
  snap.projects.forEach((p) => Object.assign(row(p.dir), { name: p.name || baseName(p.dir), last: p.last_ts, today: p.today }));
  snap.sessions.forEach((s) => { if (s.project_dir && s.group !== "done") { const r = row(s.project_dir); r.live++; r.needs += s.group === "needs"; } });
  return [...by.values()];
}

function pickRows() {
  const q = $("pfind").value.trim().toLowerCase();
  const recent = (p) => p.last || -Infinity;
  const order = (a, b) => (b.needs - a.needs) || (b.live - a.live) || (recent(b) - recent(a)) || a.name.localeCompare(b.name);
  const match = projectRows().filter((p) => !q || p.name.toLowerCase().includes(q));
  const line = (p) => {
    const meta = p.needs ? `<span class="meta y">${p.needs} needs you</span>` : p.live ? `<span class="meta">${p.live} live</span>`
      : `<span class="meta">${p.on ? (p.last ? agoLong(snap.now - p.last) : "no session yet") : "runs off"}</span>`;
    return `<button class="prow${p.on ? "" : " off"}" role="option" aria-selected="${scope === p.dir}" data-proj="${esc(p.dir)}">
      <span class="ck">${scope === p.dir ? "✓" : ""}</span><span class="nm">${esc(p.name)}</span>${meta}<span class="c">${p.today ? money(p.today) : "-"}</span></button>`;
  };
  const on = match.filter((p) => p.on).sort(order), off = match.filter((p) => !p.on).sort(order);
  let html = q ? "" : `<button class="prow" role="option" aria-selected="${!scope}" data-proj=""><span class="ck">${scope ? "" : "✓"}</span>
    <span class="nm">All projects</span><span class="meta">${liveSessions().length} live</span><span class="c">${money(snap.spend.today)}</span></button>`;
  if (on.length) html += `<div class="grp lbl">Runs allowed · ${on.length}</div>${on.map(line).join("")}`;
  if (off.length) html += `<div class="grp lbl">Runs off · ${off.length}</div>${off.map(line).join("")}`;
  if (!match.length) html = `<div class="none">No project matches "${esc(q)}". Projects appear here once a Claude Code session runs in them.</div>`;
  $("prows").innerHTML = html;
  hi = 0;
  markHi();
}

function markHi() {
  const rows = [...document.querySelectorAll("#prows .prow")];
  rows.forEach((r, k) => r.classList.toggle("hi", k === hi));
  if (rows[hi]) rows[hi].scrollIntoView({ block: "nearest" });
}

function openPicker() {
  if (!snap || !cfg) return;
  if (form === "pill") return;
  if (page !== "list") showPage("list");
  $("pop").hidden = false;
  $("pop").style.top = ($("scope").getBoundingClientRect().bottom - $("open").getBoundingClientRect().top + 4) + "px";  // under the header, banner or not
  $("scope").setAttribute("aria-expanded", "true");
  $("pfind").value = "";
  pickRows();
  $("pfind").focus();
}

function closePicker() {
  $("pop").hidden = true;
  $("scope").setAttribute("aria-expanded", "false");
}

function pick(dir) {  // a project scopes the list and becomes the task target; All projects keeps the target
  scope = dir;
  if (dir) project = dir;
  doneOpen = false;
  closePicker();
  render();
  saveDraft();
}

// -- Prep page ---------------------------------------------------------------------------
function options(list, value) { return list.map((v) => `<option${v === value ? " selected" : ""}>${esc(v)}</option>`).join(""); }

function showPrep() {
  const f = card.fields;
  $("crumb").textContent = "Prep / " + projectName(card.project_dir);
  $("pscroll").innerHTML = `
    <div class="blk"><span class="lbl">You typed</span><div class="text">${esc(card.raw)}</div></div>
    ${f.where ? `<div class="blk"><span class="lbl">Scouted</span><div class="m">${esc(f.where)}</div></div>` : ""}
    <div class="blk"><span class="lbl">Enhanced prompt (edit freely)</span>
      <textarea id="p-prompt" class="in m" rows="9" spellcheck="false">${esc(card.prompt)}</textarea></div>
    ${f.question ? `<div class="askbox" style="margin:0"><span class="st y">? Question</span><div class="q">${esc(f.question)}</div></div>` : ""}
    <div class="blk"><span class="lbl">Route</span><div class="prep-row">
      <select id="p-model" aria-label="Model">${options(cfg.models, card.route.model)}</select>
      <select id="p-effort" aria-label="Effort">${options(cfg.efforts, card.route.effort)}</select>
      <span class="m mut">${esc(card.route.type)}</span></div>
      ${card.reason ? `<div class="mut">${esc(card.reason)}</div>` : ""}</div>
    <div class="m mut">Prep $${Number(card.cost).toFixed(3)} · ${card.turns} turns</div>`;
  $("pbar").innerHTML = `<div class="lr"><button class="btn go" data-pact="run">Run</button>
    <button class="btn" data-pact="raw">Run raw</button><button class="btn" data-pact="edit">Edit</button>
    <button class="btn" data-pact="cancel">Cancel</button></div><div id="p-msg" class="say"></div>`;
  showPage("prep");
  $("p-prompt").focus();
}

function prepAct(name) {
  if (busy) return;
  if (name === "run") doRun(card.project_dir, $("p-prompt").value.trim(), $("p-model").value, $("p-effort").value, card.id);
  if (name === "raw") doRun(card.project_dir, card.raw, cfg.default_model, cfg.default_effort, "");
  if (name === "edit") { card = null; showPage("list"); $("c-prompt").focus(); }
  if (name === "cancel") { card = null; draft = ""; $("c-prompt").value = ""; saveDraft(); showPage("list"); }
}

// -- session page ------------------------------------------------------------------------
function noteLine(s) {  // one muted line, only when there is something to say
  const out = [], link = (id) => `<span class="link" data-open="${esc(id)}">${esc(id.slice(0, 8))}</span>`;
  if (s.verdict === "FAIL") out.push(`<span class="r">× FAIL ${esc(s.verdict_detail)}</span>`);
  if (s.denials && s.denials.length) {
    const d = s.denials[0], more = s.denials.length > 1 ? ` +${s.denials.length - 1}` : "";
    out.push(`△ ${s.denials.length} denied (${esc(d.tool)} ${esc(d.what)}${more}), the run still finished`);
  }
  if (s.handoff_hint) out.push(`<span class="${s.group === "needs" ? "y" : ""}">↻ hand off: ${s.ctx_tone === "red" ? "the context is large" : s.follow_ups + " follow-ups"}, one task = one chat</span>`);
  if (s.rules_warn) out.push(`△ rules: ${esc(s.rules_warn)}`);
  if (s.delegate_hint) out.push(`⇢ delegate? ${s.reads} reads in the main chat this turn`);
  if (s.two_writers) out.push("△ 2 writers: another session edits files in this repo");
  if (s.escalated) out.push(`↑ escalated ${esc(s.escalated)}`);
  if (s.forked_from) out.push(`↳ copy of ${link(s.forked_from)}`);
  if (s.forks.length) out.push(`↳ continued in ${s.forks.map(link).join(" ")}`);
  return out.length ? `<p class="note m">${out.join(" · ")}</p>` : "";
}

function askBlock(s) {
  if (s.state === "stop") {
    const where = s.window ? "Your answer continues this run."
      : `Your answer runs in a window copy of this chat. The ${s.source} chat stays as it is.`;
    return `<div class="askbox"><div class="q">${esc(s.stop_question)}</div>
      <textarea class="in" id="answer" rows="3" aria-label="Answer" placeholder="${esc(where)}"></textarea>
      <div class="lr"><button class="btn you" data-act="answer">Send answer</button>
      ${s.window && !s.run_live ? '<button class="btn" data-act="terminal">Open in terminal</button>' : ""}</div>
      <div id="a-msg" class="say"></div></div>`;
  }
  if (s.state === "blocked" && s.denied) {
    return `<div class="card r"><div class="denied">denied: ${esc(s.denied.tool)} ${esc(s.denied.what)} <span class="mut">${esc(s.denied.reason)}</span></div>
      ${s.window && !s.run_live ? '<div class="lr"><button class="btn go sm" data-act="terminal">Open in terminal</button></div>' : ""}
      <div id="a-msg" class="say"></div></div>`;
  }
  if (s.state === "failed" && s.failed) {
    return `<div class="card r"><div class="denied">× ${esc(s.failed.error)} ${esc(s.failed.details || "")}</div></div>`;
  }
  return "";
}

function pathHtml(s) {  // the playbook path: Prep, Run, Verify, Hand off
  const working = BUSY.has(s.state);
  const steps = [
    ["Prep", s.prep ? "ok" : ""],
    ["Run", working && !["verify", "handoff"].includes(s.kind) ? "cur" : s.prompts ? "ok" : ""],
    ["Verify", s.verdict === "PASS" ? "ok" : s.verdict === "FAIL" ? "bad" : working && s.kind === "verify" ? "cur" : ""],
    ["Hand off", s.state === "done" ? "ok" : working && s.kind === "handoff" ? "cur" : ""],
  ];
  const fill = { ok: "g", cur: "f", bad: "r", "": "" }, mark = { ok: "✓ ", cur: "▶ ", bad: "× ", "": "" };
  return steps.map(([n, st]) => `<span class="${st}"><span class="cells">${cellsHtml(Array(6).fill(fill[st]))}</span>${mark[st]}${n}</span>`).join("");
}

function agentRows(s, steps) {  // main first, then the agents; `steps` (oldest first) gives each one's last step
  const working = BUSY.has(s.state), running = s.agents.some((a) => a.text === "Running");
  const agentCost = s.agents.reduce((t, a) => t + a.cost, 0);
  const last = (id) => { for (let k = steps.length - 1; k >= 0; k--) if (steps[k].agent === id) return steps[k]; return null; };
  return [{ nm: "main", id: "", steps: s.main_steps, cost: s.spent == null ? null : Math.max(0, s.spent - agentCost),
            word: working ? (running ? "waiting" : "working") : label(s).toLowerCase() }]
    .concat(s.agents.map((a) => ({ nm: a.type, id: a.id, steps: a.steps, cost: a.cost, verdict: a.verdict,
      word: a.text === "Running" ? "working" : a.text === "Done" ? "done" : a.text.toLowerCase() })))
    .map((r) => Object.assign(r, { last: last(r.id) }));
}

function renderBrief(s) {
  const t = ctxTone(s), steps = s.main_steps + s.agents.reduce((n, a) => n + a.steps, 0);
  const [yellow, red] = cfg ? cfg.gauge : [150000, 300000];
  const end = BUSY.has(s.state) ? snap.now : s.last_ts;
  const spent = s.spent == null ? "&ndash;" : (s.spent_exact ? "" : '<span class="est" title="estimated">~</span>') + money(s.spent);
  const word = t === "r" ? "hand off now" : t === "y" ? "hand off soon" : "context";
  const rows = agentRows(s, []);
  return `<div class="bwrap">
    <button class="brief" id="brief" aria-expanded="${briefOpen}" aria-controls="more" title="Context, agents and activity (click or Space)">
      <span class="path">${pathHtml(s)}<span class="car" aria-hidden="true">${briefOpen ? "▴" : "▾"}</span></span>
      <span class="stats">
        <span><small>spent</small><b class="usd">${spent}</b></span>
        <span><small>$ / min</small><b>${money(s.burn)}</b></span>
        <span><small class="${t}">${word}</small><span class="cx"><span class="cells">${cellsHtml(ctxClasses(s.ctx_tokens))}</span>
          <b class="${t}">${s.ctx_tokens == null ? "?" : kTokens(s.ctx_tokens)}</b></span></span>
        <span><small>time</small><b>${elapsed(end - s.started_ts)}</b></span>
        <span><small>steps</small><b>${steps}</b></span>
      </span>
    </button>
    <div class="more" id="more"${briefOpen ? "" : " hidden"}>
      <div class="blk"><div class="hd"><span class="lbl${t ? " " + t : ""}">Context${t === "y" ? " · hand off soon" : t === "r" ? " · hand off now" : ""}</span>
        <span class="m">1 cell = ${kTokens(red / 30)}</span></div>
        <div class="cells act30">${cellsHtml(ctxClasses(s.ctx_tokens))}</div>
        <div class="scale"><span>0</span><span>${kTokens(yellow)} hand off soon</span><span>${kTokens(red)} hand off</span></div></div>
      <div class="blk"><div class="hd"><span class="lbl">Agents · 1 cell = 2 steps</span><span class="m">steps / cost</span></div><div class="agents">
        ${rows.map((r) => `<div class="agent"><span class="nm m" title="${esc(r.nm)}">${r.word === "done" ? "✓ " : r.word === "working" ? "▶ " : ""}${esc(r.nm)}${r.verdict ? " " + esc(r.verdict) : ""}</span>
          <span class="cells">${cellsHtml(Array.from({ length: 24 }, (_, k) => k < Math.ceil(r.steps / 2) ? "f" : ""))}</span>
          <span class="m">${r.steps}</span><span class="m c">${r.cost == null ? "&ndash;" : money(r.cost)}</span></div>`).join("")}</div></div>
      <div class="blk"><div class="hd"><span class="lbl">Activity · last 30 min</span><span class="m">1 cell = 1 min</span></div>
        <div class="cells act30">${activityCells(s.activity)}</div></div>
    </div></div>`;
}

function renderSession() {
  const s = current(), nav = navList(), k = nav.findIndex((x) => x.id === openId);
  $("pos").textContent = k >= 0 ? `${k + 1} of ${nav.length}` : "";
  $("prev").disabled = k <= 0;
  $("next").disabled = k < 0 || k >= nav.length - 1;
  if (!s) {
    setHtml($("sbody"), '<div class="mut">Starting ... (the session shows up with its first event)</div>');
    $("proc").innerHTML = "";
    $("proc")._html = "";
    setHtml($("levers"), "");
    return;
  }
  const t = tone(s);
  const when = BUSY.has(s.state) ? ago(snap.now - s.turn_ts) : (s.state === "stop" ? "waiting " : "") + ago(snap.now - s.last_ts);
  const src = s.source === "?" ? "" : s.source + " / ";
  setHtml($("sbody"), `<div class="head"><span class="st ${t}">${s.symbol} ${esc(label(s))} <span class="lc">· ${when}</span></span><h2>${esc(s.title)}</h2>
    <div class="where"><span class="m" title="${esc(s.route_reason || "")}">${esc(s.project)} / ${esc(src)}${esc(routeText(s))}</span>
    ${s.project_dir ? `<button class="btn sm" data-here="${esc(s.project_dir)}">New task here</button>` : ""}</div></div>
    ${noteLine(s)}${askBlock(s)}${renderBrief(s)}`);
  renderProc(s).catch(() => {});
  renderLevers(s).catch(() => {});
}

const LIVE = '<span class="cells"><i class="f live"></i></span>';
function logRow(x, mark = "") {
  return `<div${x.denied ? ' class="r"' : ""}><span>${mark}</span><span>${hms(x.ts)}</span><span>${esc(x.agent_type)}</span><span>${esc(x.tool)} ${esc(x.what)}</span></div>`;
}

async function renderProc(s) {
  const seq = ++procSeq, wanted = tab;
  let steps = [], chat = null;
  if (wanted === "chat") chat = await api("/api/chat?session=" + encodeURIComponent(s.id));
  else steps = await api("/api/steps?session=" + encodeURIComponent(s.id));
  if (seq !== procSeq || openId !== s.id || tab !== wanted) return;
  const rows = agentRows(s, steps);
  const newest = steps.slice().reverse();
  let body = "";
  if (wanted === "steps") {
    const mark = s.state === "running" ? LIVE : s.state === "stop" ? '<span class="st y">?</span>' : s.state === "blocked" ? '<span class="st r">■</span>' : "";
    body = newest.length ? `<div class="log">${newest.map((x, k) => logRow(x, k === 0 ? mark : "")).join("")}</div>` : '<p class="none">No step yet.</p>';
  } else if (wanted === "agents") {
    body = `<div class="alist">${rows.map((r) => {
      const m = r.word === "working" && s.state === "running" ? LIVE : r.word === "done" ? '<span class="st g">✓</span>'
        : `<span class="st ${r.word === "waiting" ? "q" : tone(s)}">${r.word === "waiting" ? "○" : s.symbol}</span>`;
      return `<div class="arow">${m}<span class="nm">${esc(r.nm)}${r.verdict ? " " + esc(r.verdict) : ""}</span><span class="m">${esc(r.word)}</span>
        <span class="m">${r.steps} steps</span><span class="m c">${r.cost == null ? "&ndash;" : money(r.cost)}</span>
        <span class="last m">${r.last ? `${hms(r.last.ts)} <span>${esc(r.last.tool)} ${esc(r.last.what)}</span>` : "no step yet"}</span></div>`;
    }).join("")}</div>`;
  } else if (wanted === "timeline") {
    const act = s.activity, base = tlBase(), at = (k) => (base + k) * 60;
    if (tlMin < base || tlMin > base + 29) tlMin = base + Math.max(0, act.findLastIndex((v) => v > 0));  // the cells move on by themselves
    const sel = tlMin - base, inMin = newest.filter((x) => Math.floor(x.ts / 60) === tlMin);
    body = `<div class="tl"><div class="hd"><span class="lbl">Last 30 min</span><span class="m">1 cell = 1 min</span></div>
      <div class="mins" role="group" aria-label="Steps per minute">${act.map((v, k) => {
        const n = newest.filter((x) => Math.floor(x.ts / 60) === base + k).length, what = `${hhmm(at(k))}, ${n} step${n === 1 ? "" : "s"}`;
        return `<button data-min="${k}" aria-pressed="${k === sel}" tabindex="${k === sel ? 0 : -1}" aria-label="${what}" title="${what}"><i class="${v ? "l" + v : ""}"></i></button>`;
      }).join("")}</div>
      <div class="scale"><span>${hhmm(at(0))}</span><span>${hhmm(at(15))}</span><span>${hhmm(at(29))}</span></div>
      <div class="hd at"><span class="lbl">${hhmm(at(sel))} · ${inMin.length} step${inMin.length === 1 ? "" : "s"}</span><span class="m">← → other minutes</span></div>
      ${inMin.length ? `<div class="log">${inMin.map((x) => logRow(x)).join("")}</div>` : '<p class="none">No step in this minute.</p>'}</div>`;
  } else {
    const turns = chat.items.filter((i) => i.role !== "tool");
    const foot = chat.source === "window"
      ? "Streamed from this window run." + (chat.start_commit ? ` start ${esc(chat.start_commit.slice(0, 7))} · ${chat.changed == null ? "?" : chat.changed} file(s) changed since.` : "")
      : `Read from the ${esc(s.source === "?" ? "chat" : s.source)} transcript, in words; tool output stays in Steps.`;
    body = `<div class="chat">${turns.map((i) => `<div class="turn ${i.role}"><span class="lbl">${i.role === "you" ? "You" : i.role === "claude" ? "Claude" : esc(i.role)}${i.ts ? " · " + hhmm(i.ts) : ""}</span>
      <p>${esc(i.text)}</p></div>`).join("") || '<p class="none">Nothing to show yet. A VS Code or terminal chat shows its turns once a prompt has named its transcript.</p>'}
      <p class="src">${foot}</p></div>`;
  }
  const html = `<div class="tabs" role="tablist" aria-label="Process">${TABS.map(([id, nm]) =>
    `<button role="tab" id="tab-${id}" data-tab="${id}" aria-selected="${wanted === id}" aria-controls="pane" tabindex="${wanted === id ? 0 : -1}">${nm}${id === "agents" ? ` <span class="n">${rows.length}</span>` : ""}</button>`).join("")}</div>
    <div class="pane" id="pane" role="tabpanel" aria-labelledby="tab-${wanted}" tabindex="0">${body}</div>`;
  const key = s.id + "|" + wanted;
  setHtml($("proc"), html, { sel: ".pane", end: wanted === "chat", reset: key !== procShown });
  procShown = key;
}

async function renderLevers(s) {
  const sig = [s.id, s.window, s.run_live, s.stop_question, s.state, s.verdict, s.escalated,
               s.handoff_hint, s.forks.length].join("|");
  if (sig === leversSig) return;
  leversSig = sig;
  const lv = s.run_live ? null : await api("/api/levers?session=" + encodeURIComponent(s.id)).catch(() => null);
  if (openId !== s.id || leversSig !== sig) return;
  let html = "";
  if (lv && !lv.continue && !s.stop_question) {
    html += `<div class="lr"><input id="fu" aria-label="Follow-up" placeholder="${lv.fork ? "Follow-up (runs in a window copy)" : "Follow-up"}">
      <button class="btn go" data-act="continue">Continue</button></div>`;
  }
  let buttons = "";
  if (s.run_live) buttons += '<button class="btn stop" data-act="stop">Stop</button>';
  if (lv && !lv.verify) buttons += '<button class="btn" data-act="verify">Verify</button>';
  if (lv && !lv.handoff) buttons += `<button class="btn${s.handoff_hint ? " go" : ""}" data-act="handoff">Hand off</button>`;
  if (lv && !lv.escalate) buttons += `<button class="btn go" data-act="escalate">Escalate to ${esc(lv.escalate_to)}</button>`;
  if (lv && !lv.continue && s.window && s.state === "interrupted") buttons += '<button class="btn go" data-act="resume">Resume</button>';
  if (s.window && !s.run_live) buttons += '<button class="btn" data-act="terminal" title="Open in terminal">Terminal</button>';
  if (buttons) html += `<div class="lr">${buttons}</div>`;
  let off = "";
  if (lv && lv.continue) off = "Levers off: " + lv.continue;
  else if (lv && lv.handoff) off = "Hand off is off: " + lv.handoff;
  if (lv && !lv.continue && s.verdict === "FAIL" && lv.escalate) off += (off ? " · " : "") + "Escalate is off: " + lv.escalate;
  html += `<div class="say">${esc(off)}</div><div id="f-msg" class="say"></div>`;
  setHtml($("levers"), html);
}

let stopTimer = null;
async function act(name, button) {
  const s = current();
  if (!s) return;
  if (name === "stop" && !button.dataset.armed) {  // two clicks: a stopped turn is lost work
    button.dataset.armed = "1";
    button.textContent = "Stop run? Click again";
    clearTimeout(stopTimer);
    stopTimer = setTimeout(() => { delete button.dataset.armed; button.textContent = "Stop"; }, 3000);
    return;
  }
  const msg = name === "answer" || (name === "terminal" && $("a-msg")) ? $("a-msg") : $("f-msg");
  button.disabled = true;
  try {
    let r = null;
    if (name === "stop") { button.textContent = "Stopping ..."; await api("/api/stop", { session: s.id }); }
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (name === "resume") r = await api("/api/continue", { session: s.id, text: RESUME_TEXT });
    if (name === "continue" || name === "answer") {
      const text = $(name === "answer" ? "answer" : "fu").value.trim();
      if (!text) { button.disabled = false; return; }
      r = await api("/api/continue", { session: s.id, text });
    }
    if (["verify", "handoff", "escalate"].includes(name)) r = await api("/api/" + name, { session: s.id });
    if (r && r.session !== s.id) { openSession(r.session, "chat"); return; }  // a window copy (fork)
    if (r) tab = "chat";
    leversSig = "";  // redraw from the next snapshot
  } catch (e) {
    button.disabled = false;
    if (msg) msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

function step(d) {  // ‹ › and Up / Down: the neighbouring session in the list's order
  const nav = navList(), k = nav.findIndex((x) => x.id === openId), to = nav[k + d];
  if (k >= 0 && to) { openSession(to.id, tab); }
}

// -- events ------------------------------------------------------------------------------
async function go(name, button) {
  if (name === "list") showPage("list");
  if (name === "new") { if (form === "pill") await setForm("open"); showPage("list"); $("c-prompt").focus(); }
  if (name === "needs") {
    if (scope) pick("");
    const n = $("needsec");
    if (n) n.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  if (name === "moredone") { doneOpen = true; render(); }
  if (name === "fold") await setForm("pill");
  if (name === "unfold") await setForm("open");
  if (name === "allow") allowRuns(button);
  if (name === "retry" && fail) {
    const retry = fail.retry;
    fail = null;
    if (retry === "prep") doPrep();
    else if (retry === "raw") rawRun();
    else if (retry === "allow") allowRuns(null);
    else renderCompose();
  }
  if (!native()) return;
  if (name === "minimize") window.pywebview.api.minimize();
  if (name === "close") window.pywebview.api.close();
  if (name === "ontop") { onTop = await window.pywebview.api.on_top(!onTop); renderOnTop(); }
}

function rawRun() {
  const text = $("c-prompt").value.trim();
  if (text && runnable()) doRun(project, text, cfg.default_model, cfg.default_effort, "");
}

document.addEventListener("click", (e) => {
  if (!$("pop").hidden && !e.target.closest("#pop") && !e.target.closest("[data-pick]")) closePicker();
  const t = e.target.closest("[data-go],[data-open],[data-tab],[data-min],[data-act],[data-pact],[data-do],[data-here],[data-proj],[data-pick],[data-step],#brief,#today");
  if (!t) return;
  if (t.matches(".card") && e.target.closest("[data-stay]")) return;  // typing an answer in a card
  if (t.dataset.go) go(t.dataset.go, t);
  else if (t.dataset.do) unblock(t);
  else if (t.dataset.open) openSession(t.dataset.open);
  else if (t.dataset.tab) { tab = t.dataset.tab; const s = current(); if (s) renderProc(s).catch(() => {}); }
  else if (t.dataset.min !== undefined) { tlMin = tlBase() + Number(t.dataset.min); const s = current(); if (s) renderProc(s).catch(() => {}); }
  else if (t.dataset.act) act(t.dataset.act, t);
  else if (t.dataset.pact) prepAct(t.dataset.pact);
  else if (t.dataset.here !== undefined) { pick(t.dataset.here); showPage("list"); $("c-prompt").focus(); }
  else if (t.dataset.proj !== undefined) pick(t.dataset.proj);
  else if (t.dataset.step) step(Number(t.dataset.step));
  else if (t.hasAttribute("data-pick")) { if ($("pop").hidden) openPicker(); else closePicker(); }
  else if (t.id === "brief") {
    briefOpen = !briefOpen;
    t.setAttribute("aria-expanded", String(briefOpen));
    t.querySelector(".car").textContent = briefOpen ? "▴" : "▾";
    $("more").hidden = !briefOpen;
    saveDraft();
  } else if (t.id === "today") {
    const open = t.getAttribute("aria-expanded") !== "true";
    t.setAttribute("aria-expanded", String(open));
    $("todaymore").hidden = !open;
  }
});

document.addEventListener("dblclick", (e) => {
  if (e.target.closest(".pill .sp")) setForm("open");
  else if (e.target.closest(".top .sp")) setForm("pill");
});

document.addEventListener("input", (e) => {
  if (e.target.id === "c-prompt") { draft = e.target.value; fail = null; saveDraft(); renderCompose(); }
});

$("pfind").addEventListener("input", pickRows);
$("pfind").addEventListener("keydown", (e) => {
  const rows = document.querySelectorAll("#prows .prow");
  if (e.key === "ArrowDown") { hi = Math.min(rows.length - 1, hi + 1); markHi(); e.preventDefault(); }
  if (e.key === "ArrowUp") { hi = Math.max(0, hi - 1); markHi(); e.preventDefault(); }
  if (e.key === "Enter" && rows[hi]) { pick(rows[hi].dataset.proj); e.preventDefault(); }
  if (e.key === "Escape") { closePicker(); $("scope").focus(); e.stopPropagation(); }
});

document.addEventListener("keydown", (e) => {
  const id = e.target.id || "";
  if (id === "c-prompt" && e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (e.ctrlKey) rawRun();
    else doPrep();
    return;
  }
  if (id === "fu" && e.key === "Enter") return act("continue", document.querySelector('[data-act="continue"]'));
  if (id === "pk" && e.key === "Enter") return unblock(document.querySelector('[data-do="send"][data-where="peek"]'));
  if (id.startsWith("ca-") && e.key === "Enter") return unblock(e.target.closest("[data-stay]").querySelector('[data-do="send"]'));
  if (e.key === "Enter" && e.target.matches(".card[data-open]")) { e.target.click(); return; }
  if (e.ctrlKey && e.key.toLowerCase() === "n") { e.preventDefault(); go("new"); return; }
  if (e.ctrlKey && e.key.toLowerCase() === "p") { e.preventDefault(); openPicker(); return; }
  const inField = ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
  if (e.key === "Escape") {
    if (!$("pop").hidden) closePicker();
    else if (form === "pill") dismissPeek();
    else if (page === "prep") prepAct("cancel");
    else if (page === "session") showPage("list");
    return;
  }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const d = e.key === "ArrowRight" ? 1 : -1, s = current();
    if (e.target.matches("[data-tab]") && s) {
      tab = TABS[(TABS.findIndex(([k]) => k === tab) + d + TABS.length) % TABS.length][0];
      renderProc(s).then(() => { const f = $("tab-" + tab); if (f) f.focus(); }).catch(() => {});
      e.preventDefault();
    } else if (e.target.matches("[data-min]") && s) {
      tlMin = Math.min(tlBase() + 29, Math.max(tlBase(), tlMin + d));
      renderProc(s).then(() => { const f = document.querySelector(`[data-min="${tlMin - tlBase()}"]`); if (f) f.focus(); }).catch(() => {});
      e.preventDefault();
    }
    return;
  }
  if ((e.key === "ArrowUp" || e.key === "ArrowDown") && page === "session" && form === "open" && !inField
      && !e.target.closest("#pane")) {
    step(e.key === "ArrowDown" ? 1 : -1);
    e.preventDefault();
  }
});

window.addEventListener("pywebviewready", async () => {
  document.documentElement.classList.add("native");
  const st = await window.pywebview.api.state();
  onTop = st.on_top;
  renderOnTop();
  if (st.form !== form) await setForm(st.form);
});

function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => { live = true; snap = JSON.parse(e.data); render(); };
  es.onerror = () => { live = false; if (snap) $("banner").hidden = false; };
}

(async () => {
  const buttons = `<button class="rb on native-only" data-go="ontop" title="Always on top (on)" aria-label="Always on top">&#8868;</button>
    <button class="rb" data-go="fold" title="Fold to pill (double-click this bar)" aria-label="Fold to pill">&#8963;</button>
    <button class="rb native-only" data-go="minimize" aria-label="Minimize">&ndash;</button>
    <button class="rb x native-only" data-go="close" aria-label="Close" title="Close window (runs keep going)">&#10005;</button>`;
  document.querySelectorAll("[data-winbtns]").forEach((el) => { el.innerHTML = buttons; });
  try { cfg = await api("/api/config"); } catch (e) { cfg = null; }
  try { draft = (await api("/api/draft")).text; } catch (e) { /* no draft */ }
  $("c-prompt").value = draft;
  project = (cfg && cfg.project) || "";
  briefOpen = !!(cfg && cfg.brief);
  connect();
})();
```

- [ ] **Step 4: Run it**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 99 tests` ... `OK` (`test_static_and_ping` reads the three page files).

- [ ] **Step 5: Create the check harness in the scratchpad (not in the repo)**

It seeds a throw-away data folder in `$TEMP` with nine sessions (a STOP question, a denial, a running one with two agents, one over the red context in a project without runs, an idle one, four done), five allowed projects, transcripts for the Chat tab, and starts the service with the fake claude. Nothing is written outside `$TEMP`. Save it as `<scratchpad>/serve_fake.py`:

```python
"""Scratch harness: serve a clone of the console with seeded sessions and the fake claude.
usage: py serve_fake.py <clone dir> <port> [empty]"""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

clone, port = Path(sys.argv[1]).resolve(), int(sys.argv[2])
empty = len(sys.argv) > 3
sys.path.insert(0, str(clone))
from console import events, paths, server  # noqa: E402

root = Path(tempfile.mkdtemp(prefix="ccfake-"))
home = root / "home"
now = time.time()
dirs = {}
for name in ("CLAUDE CONSOLE", "CONTENT MANAGER", "BRAINAMP", "SQUARE LAB", "PORTFOLIO SITE"):
    (root / name).mkdir()
    dirs[name] = str(root / name)
dirs["fashion_packshots_ai"] = str(root / "fashion_packshots_ai")  # not allowed
(root / "fashion_packshots_ai").mkdir()
cfg = dict(paths.load_config(), projects=[dirs[n] for n in ("CLAUDE CONSOLE", "CONTENT MANAGER", "BRAINAMP", "SQUARE LAB", "PORTFOLIO SITE")])
fake = [sys.executable, str(clone / "tests" / "fake_claude.py")]


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def transcript(sid, turns, model="claude-sonnet-5-5", tokens=0):
    path = root / f"{sid}.jsonl"
    lines = []
    t = now - 3000
    for who, text in turns:
        t += 120
        if who == "you":
            lines.append({"type": "user", "timestamp": iso(t), "message": {"role": "user", "content": text}})
        else:
            lines.append({"type": "assistant", "timestamp": iso(t), "message": {
                "id": f"{sid}-{t}", "model": model, "usage": {"input_tokens": tokens, "output_tokens": 800},
                "role": "assistant", "content": [{"type": "text", "text": text}, {"type": "tool_use", "name": "Read", "input": {}}]}})
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    return str(path)


def ev(sid, proj, ts, event, **extra):
    d = dirs[proj]
    events.append(home, dict({"ts": ts, "event": event, "session_id": sid, "project": proj, "project_dir": d, "cwd": d}, **extra))


def steps(sid, proj, spec, agent=None):
    # spec: list of (seconds ago, tool, what)
    for ago, tool, what in spec:
        extra = {"agent_id": agent[0], "agent_type": agent[1]} if agent else {}
        ev(sid, proj, now - ago, "PreToolUse", tool=tool, what=what, **extra)


if not empty:
    # 1 asks you (vscode)
    tp = transcript("cm", [("you", "The updater keeps retrying on 429 and hammers the API. Make it back off."),
                           ("claude", "Retry now backs off exponentially and waits for Retry-After."),
                           ("you", "Add tests."),
                           ("claude", "Keep the old cache key, or migrate entries to the v2 key?")], tokens=1_000_000)
    ev("cm", "CONTENT MANAGER", now - 1700, "UserPromptSubmit", prompt="Fix updater retry on 429", transcript_path=tp)
    steps("cm", "CONTENT MANAGER", [(1500 - 60 * k, "Edit" if k % 2 else "Read", f"src/updater{k}.py") for k in range(12)])
    ev("cm", "CONTENT MANAGER", now - 840, "Stop", model="claude-sonnet-5-5", context_tokens=182000, entrypoint="claude-vscode",
       stop_question="Keep the old cache key, or migrate entries to the v2 key?", route="mechanical", transcript_path=tp)
    # 2 blocked
    ev("br", "BRAINAMP", now - 600, "UserPromptSubmit", prompt="Add transcript search endpoint")
    steps("br", "BRAINAMP", [(500, "Edit", "server.py"), (400, "Bash", "py -m unittest")])
    ev("br", "BRAINAMP", now - 180, "PermissionDenied", tool="Bash", what="git push origin main", reason="[Push] not allowed")
    # 3 running with agents
    tp3 = transcript("cc", [("you", "Draft a redesign proposal for the window."), ("claude", "Reading the plan first.")], model="claude-opus-5-5", tokens=400_000)
    ev("cc", "CLAUDE CONSOLE", now - 400, "UserPromptSubmit", prompt="Redesign proposal for the window", transcript_path=tp3, effort="high")
    ev("cc", "CLAUDE CONSOLE", now - 395, "SubagentStart", agent_id="ag1", agent_type="Explore")
    steps("cc", "CLAUDE CONSOLE", [(380 - 30 * k, "Read", f"console/m{k}.py") for k in range(6)], agent=("ag1", "Explore"))
    ev("cc", "CLAUDE CONSOLE", now - 200, "SubagentStop", agent_id="ag1", agent_type="Explore", model="claude-haiku-5-5", context_tokens=38000)
    ev("cc", "CLAUDE CONSOLE", now - 190, "SubagentStart", agent_id="ag2", agent_type="general-purpose")
    steps("cc", "CLAUDE CONSOLE", [(180 - 15 * k, "Read", f"web/f{k}.js") for k in range(9)], agent=("ag2", "general-purpose"))
    steps("cc", "CLAUDE CONSOLE", [(5, "Read", "web/app.js")], agent=("ag2", "general-purpose"))
    # 4 running, red context, project without runs
    ev("fpa", "fashion_packshots_ai", now - 2500, "UserPromptSubmit", prompt="Batch prepare launch split")
    steps("fpa", "fashion_packshots_ai", [(2000 - 100 * k, "Edit", f"batch/p{k}.py") for k in range(15)] + [(8, "Edit", "batch/prepare.py")])
    ev("fpa", "fashion_packshots_ai", now - 7, "Stop", model="claude-sonnet-5-5", context_tokens=312000, entrypoint="cli")
    ev("fpa", "fashion_packshots_ai", now - 5, "UserPromptSubmit", prompt="again")
    steps("fpa", "fashion_packshots_ai", [(3, "Edit", "batch/prepare.py")])
    # 5 idle
    ev("lv", "CLAUDE CONSOLE", now - 1300, "UserPromptSubmit", prompt="Phase 3 levers live check")
    steps("lv", "CLAUDE CONSOLE", [(1250, "Read", "console/levers.py"), (1240, "Bash", "py -m unittest")])
    ev("lv", "CLAUDE CONSOLE", now - 1200, "Stop", model="claude-sonnet-5-5", context_tokens=71000, entrypoint="claude-vscode")
    # done (ended)
    for sid, proj, title in (("d1", "CLAUDE CONSOLE", "Verify routing table"), ("d2", "SQUARE LAB", "Docs cleanup"),
                             ("d3", "CLAUDE CONSOLE", "Rename hook fields"), ("d4", "CLAUDE CONSOLE", "Doto woff2 bundle")):
        ev(sid, proj, now - 5000, "UserPromptSubmit", prompt=title)
        ev(sid, proj, now - 4900, "Stop", model="claude-sonnet-5-5", context_tokens=30000)
        ev(sid, proj, now - 4800, "SessionEnd")
    ev("d1", "CLAUDE CONSOLE", now - 4850, "Stop", verdict="PASS", model="claude-sonnet-5-5")

httpd, hub = server.make_server(cfg, port=port, folder=home, exe=fake)
hub.start()
print("serving", port, root, flush=True)
httpd.serve_forever()
```

- [ ] **Step 6: Start it and open the page in two frames**

```bash
py <scratchpad>/serve_fake.py . 47811 &
```

The first line printed is `serving 47811 <temp folder>`. Open `http://127.0.0.1:47811/api/ping` in a browser tab, then in the page console replace the body with two frames of the real window widths:

```javascript
document.body.style.cssText = "margin:0;background:#555;display:flex;gap:20px;padding:10px";
document.body.innerHTML = '<iframe id="a" src="/" style="width:400px;height:640px;border:0"></iframe><iframe id="b" src="/" style="width:340px;height:640px;border:0"></iframe>';
```

The frames are same-origin, so the checks can click, type and call the page's functions through `frame.contentWindow` (`let` globals through `contentWindow.eval("snap")`), and read layout. "No horizontal scroll" means `contentDocument.documentElement.scrollWidth === contentWindow.innerWidth` and no element of `.win` has `getBoundingClientRect().right` past the frame's width.

- [ ] **Step 7: Check in the browser, at 400 and at 340 px**

1. **List.** Needs you (3 cards: the STOP question with its answer box, the denial, the red context), Working (idle, running with its live step and one blinking cell), Done today (two quiet lines and `Show 2 more`). The today strip shows one Doto figure, one row of cells with the orange outline, `limit $15`; a click opens the breakdown (exact / estimated, `1 cell = $0.50`, model shares, window runs). The `3 need you` chip is orange. At 340 px the route and the `USD` word are gone and nothing scrolls sideways.
2. **Picker.** The scope button opens it (Ctrl+P too; the find box has focus); it lists All projects, Runs allowed (5) and Runs off (1) with `N needs you` in orange, `N live`, `1h ago`, `no session yet` and today's cost; typing `cont` leaves CONTENT MANAGER; Enter scopes the list to it (one card), the scope button and the target chip under the task box say CONTENT MANAGER; Esc closes it. Picking `fashion_packshots_ai` says `Runs are off in ...` with `Allow runs`; the button turns the box on.
3. **Answer in place.** Typing in a card's answer box and Enter sends it; the card reads `Answer sent. It runs in a window copy: open it`; the link opens the copy.
4. **Session page.** From a card: the head, the note line when there is a note (the red-context session has `↻ hand off`), the ask box, the brief folded (path, spent in Doto with `~`, `$ / min`, `hand off soon` in orange from 150K, time, steps; at 340 px the seconds are gone and the label still fits); a click on the brief opens context, agent lanes and activity and saves `brief` (`GET /api/config` says `true`); a second click folds it. `‹ ›` and Up / Down change the session (`n of m` in the bar), Esc goes back to the list.
5. **Process tabs.** Steps (newest first, the live step has the blinking cell), Agents 3 (main, Explore done, general-purpose), Timeline (30 cells, the selected minute outlined; click a cell and `<-` / `->` change the minute and its steps), Chat of a VS Code session (the turns of the seeded transcript in words, scrolled to the end, `Read from the vscode transcript ...`). Arrow keys on a focused tab move between tabs and keep the focus.
6. **Prep page.** Typing a task in the box and Enter shows `Haiku is reading ...` in the box, then the Prep page (You typed, Scouted, the editable prompt, Route, Run / Run raw / Edit / Cancel); `Run` opens the session on its Chat tab (`YOU`, `CLAUDE`, `RESULT success`, the follow-up box and Verify / Hand off / Terminal); `Edit` returns to the list with the text kept; Esc cancels.
7. **Stop.** Run `SLOW one` from the box with Ctrl+Enter: its session shows `Stop`; the first click says `Stop run? Click again`, the second stops it (`stopped` in `/api/state`).
8. **Pill and peek.** `⌃` folds the page to the pill (a chip per live session, today's spend); a new STOP event appended to the harness's `events-*.jsonl` while folded opens one card under the pill, which `Send answer` closes; `⌄` opens the window again.
9. **States.** A second harness run (`... 47812 empty`) shows the empty list text; stopping that service shows the `OFFLINE` banner and the picker still opens under the header. A task containing the word `BROKEN` makes the fake Prep answer with no JSON: the `Prep failed` card (`Prep returned no JSON: not json`) shows above the box with `Try again`.
10. **Light.** Set the light tokens on the frame's `documentElement` (`--page #dedcd6`, `--win #f4f3ef`, `--raise #e7e5e0`, `--off #d6d4ce`, `--ink #17181b`, `--mut #5f5e59`, `--line #d2d0ca`, `--you #b84f00`, `--bad #c0352b`, `--ok #1d7a4b`, `--on-you #fff7f0`): the list, a session and the picker stay readable, orange is still only on needs-you.
11. No errors from the page in the console (`error` and `unhandledrejection` listeners on both frames stay empty through checks 1-9).

Stop the harness (`taskkill //PID <pid> //F` for the process listening on 47811) and delete the `ccfake-*` folder in `$TEMP`.

- [ ] **Step 8: Commit**

```bash
git add web/index.html web/style.css web/app.js
git commit -m "feat: Cells Drawer window: list, session page, project picker, Prep page"
```

**DONE WHEN**
- [ ] The 11 browser checks pass; 99 tests OK; `git status --short` empty.

---

### Task 5: Fred: live check in the real window

Claude cannot see Fred's screen or VS Code chats. Close the running window first (it still runs plan 06's page), then start it with `run.bat`. This also covers plan 06 Task 7 (steps 1, 2 and 5 below), whose rail wording is superseded.

- [ ] **Step 1: The two forms.** The window opens borderless, 400 x 640, rounded corners, no title bar, on top. Drag it by `⋮⋮`, the empty bar space next to the scope chip and the `N need you` chip, or the empty bar space on a session page. `⊤` turns always-on-top off and on (title `Always on top (off)`), `–` minimizes, `✕` closes it (a running window run keeps going). `⌃` or a double-click on the empty bar folds it to the 380 x 48 pill at the same top-left corner; a double-click on the empty pill space or `⌄` opens it again. Fold, move the pill, close it, start `run.bat`: it comes back at the same place and form. `~/.claude/console/window.json` holds `form`, `x`, `y`, `on_top`, `project`, `brief`.
- [ ] **Step 2: The list on real sessions.** Your open VS Code chats appear in Needs you / Working / Done today with the right state words; costs are `~` for chats and exact for window runs; the today strip and the picker's per-project cost agree with the Overview figures you saw in plan 06; the picker lists your real projects (Runs allowed and Runs off) and the ones with a live session first; pick one, the list scopes and the task box target follows; `Allow runs` on a project with runs off turns the box on.
- [ ] **Step 3: Answer in place.** In a VS Code chat: `End your reply with one line: STOP: <a yes or no question for me>`. When the turn ends the card shows the question; answer `yes` in the card: `Answer sent. It runs in a window copy`, the copy opens from the link and answers from the chat's context; the VS Code chat is untouched. Do the same with the window folded: the pill grows one card, `Send answer` closes it and the pill shrinks back to 48 px; Esc closes a card too.
- [ ] **Step 4: Session page and Chat.** Open a VS Code chat: the brief, `Agents`, `Timeline` (click a minute: its steps), and `Chat` showing the last turns of that chat in words (yours and Claude's, no tool output); a window run's Chat shows its stream in words. Fold and open the brief, restart the window: it keeps the choice. `‹ ›`, Up / Down and Esc move between sessions and back.
- [ ] **Step 5: Light theme and narrow.** Windows Settings > Personalization > Colours > Light: the window turns light, everything readable, orange only on needs-you; back to Dark. Make the window narrower if the OS lets you (the frameless window may not); the page holds at 340 px by the browser check.
- [ ] **Step 6:** `~/.claude/console/hook-errors.log` and `window-errors.log` have no new lines.

**DONE WHEN**
- [ ] Steps 1-6 pass; anything that differed is noted in History / Troubleshooting.

---

### Task 6: Close the phase

Also closes plan 06 (its Tasks 7-8).

- [ ] **Step 1:** In `../PLAN.md`, set sub-plans 6 and 7 to "done <date>" and add one dated History line (what was built, test count, anything that differed).
- [ ] **Step 2:** In `../BRAINSTORM.md` 7.4, replace "Replaced by 7.5 once the rework sub-plan is done." with "Replaced by 7.5 (phases 6 and 7, <date>)."; in 7.5, replace "Open check: resizing a frameless pywebview window from code on Windows (pill to open window)." with "Resizing the frameless window from code works (plan 06, fixed decision 14)."
- [ ] **Step 3:** In `06-rework.md`, tick Tasks 7 and 8 in its TODO list and add a History line saying Tasks 7-8 were done through plan 07 Tasks 5-6. In this file, tick the TODO list, add the History line, and add any bug + fix to Troubleshooting.
- [ ] **Step 4:** `../CLAUDE.md` already names the locked file (done when D was locked); check that rule still reads right.
- [ ] **Step 5:** Commit: `git add PLAN.md BRAINSTORM.md CLAUDE.md plans/06-rework.md plans/07-cells-drawer.md && git commit -m "docs: phase 7 done"` (stage only your own lines if another chat edited the shared docs).

**DONE WHEN**
- [ ] `git status --short` is empty and `git log --oneline` shows one commit per task.

---

## DONE WHEN (whole plan)

- [ ] `py -m unittest discover -s tests` -> 99 tests OK.
- [ ] The open window is the list, the session page and the Prep page; there is no rail, no Overview, no project `<select>`.
- [ ] The searchable project picker scopes the list and sets the target of a new task; runs-off projects offer `Allow runs`.
- [ ] A STOP question is answered in place from a card, the session page or the peek card; a denial, failure or interruption is unblocked in place.
- [ ] The session page shows the brief (remembered folded or open), Steps, Agents, Timeline and Chat; Chat works for VS Code and terminal chats.
- [ ] No horizontal scroll at 400 or 340 px; dark and light; orange only for "needs you".
- [ ] The page makes no network calls; nothing outside `~/.claude/console/`, this repo and the run's own project folder was written by the code or by Claude.

## History

- 2026-10-10 - Plan written. Fred decided: lock Cells Drawer (D12) and keep Console Cells as the token reference; Chat for VS Code and terminal chats from the transcript (last 6 turns, text blocks); Timeline as one cell per minute from the activity buckets plus that minute's steps; the Prep card as its own page; one muted note line; the brief's open state in `window.json`. Claude chose and recorded in Fixed decisions: no `Dismiss` on cards, the in-page `Answer sent` state, the growing today row, the selected minute kept as a minute number, the picker data (`projects` in the snapshot), the navigation order. All code was written in a scratch clone first: 99 tests OK (95 + 3 transcript + 1 projects; the timeline test out, the chat test in), each task's new tests fail as written and pass after its code; the window was checked in a browser at 400 and 340 px (checks 1-11 of Task 4: every view of the mock, dark, light by hand-set tokens, the pill and a peek card from a new event, the picker, the answer in place, Prep, Run, Stop, empty and offline states, no console errors). The plan was then replayed in a fresh clone (find blocks matched once, tests failed then passed as listed, every file equal to the scratch code). Tasks 5-6 are Fred's.

## Troubleshooting

- **Issue:** the Chat tab of a VS Code chat says `Nothing to show yet`.
  **Cause:** no hook line has named that chat's transcript yet (a chat opened before plan 06 Task 1, until its next prompt), or the chat has no text turn.
  **Fix:** none needed: the next prompt brings the path.
- **Issue:** a project is missing from the picker.
  **Cause:** the picker lists the `config.json` folders and the folders a session ran in (the event log keeps 14 days).
  **Fix:** start a Claude Code session in it once, or add it to `"projects"` in `~/.claude/console/config.json`.
- **Issue:** a card keeps `Answer sent` and stays in Needs you.
  **Cause:** the answer of a VS Code or terminal chat runs in a window copy; the original chat is not touched and still ends on its question.
  **Fix:** open the copy from the link; answer in the original chat itself when you want it to continue there.
- **Issue:** the typed answer or the follow-up disappears when the session changes state.
  **Cause:** the box belongs to the card or ask block that was replaced (a new question, another session).
  **Fix:** type it again; the page keeps text across the one-second snapshots, not across a different card.
