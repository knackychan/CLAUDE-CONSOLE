# Plan 06: Visual rework (Console Cells) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Related plans: [../PLAN.md](../PLAN.md) (master), [01-watch.md](01-watch.md), [02-run.md](02-run.md), [03-levers.md](03-levers.md), [04-polish.md](04-polish.md) (phases 1-4, done)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md) sections 3 (D11), 6, 7.1-7.5, 2 (Non-goals); [../design/rework/README.md](../design/rework/README.md); the locked mockup [../design/rework/locked/console-cells.html](../design/rework/locked/console-cells.html); [../CLAUDE.md](../CLAUDE.md)

**Goal:** The window becomes Console Cells (BRAINSTORM 7.5): borderless, with two forms. Folded, a 380 x 48 pill with one cell chip per live session and today's spend; a new question, denial, failure or interruption opens one card under it (answer in place). Open, 400 x 640: a 56 px rail of session chips plus one pane (the Overview, one session in focus, or the Prep card). Every quantity is counted in cells: context in 10K cells, spend in $0.50 cells (solid exact, hatched estimated), activity in one-minute cells, agents in 2-step cells. The service adds what the cells need: an estimated cost per session and agent (transcript usage x a price table), per-minute activity, today's spend against a soft daily limit.

**Architecture:** The hook adds the transcript path to its turn lines. A new `console/usage.py` reads those transcripts (and the subagent ones) as they grow, counts each message's usage once and prices it with `config.json` `"prices"`. `State.snapshot` gains `spent`, `burn`, `activity`, `main_steps`, `turn_ts` per session, a cost per agent, and a `spend` block (today exact / estimated, burn rate, budget, model shares); the phase 4 `mix` block goes. A new `console/window.py` is the pywebview `js_api` (fold / open / on top / minimize / close) and keeps the form, place and on-top in `~/.claude/console/window.json`, which also keeps the compose project. `web/` is rewritten from the existing renderers: `index.html` (pill + rail + pane), `style.css` (the mockup's tokens first), `app.js`, plus Doto as a local `web/doto.woff2`.

**Tech Stack:** unchanged: Python 3.14 standard library, pywebview 6.2.1 (EdgeChromium), plain HTML/CSS/JS, `unittest`. Claude Code CLI 2.1.296.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `master`). Every path below is relative to it. Run commands from the repo root in Git Bash. Start: 87 tests OK.

---

## Fixed decisions (verified 2026-10-10 on this machine, Claude Code 2.1.296, pywebview 6.2.1, code.claude.com docs + experiments)

1. **Estimated cost: the service reads the transcripts** (Fred). Every hook input carries `transcript_path` (code.claude.com/docs/en/hooks, common input fields); the hook now logs it on `SessionStart`, `UserPromptSubmit` and `Stop` lines (a path, never content). The hook change is live as soon as `cc_events.py` is saved (no re-install): an already open chat gets its path at its next prompt; until then its cost shows `–`. `console/usage.py` reads each transcript of the shown sessions every poll (1 s), from its last line end, read only. Verified on this machine's transcripts: assistant lines carry `message.id`, `message.model`, `message.usage` (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens`, `speed`) and `timestamp`; a message's usage repeats, unchanged, on each of its content-block lines (315 lines, 163 ids in one 3.8 MB transcript), so a message id counts once; the main transcript holds no subagent lines (`isSidechain` false on all 315); subagents write `<transcript without .jsonl>/subagents/agent-<agent_id>.jsonl` (`agent-ac0618b17d35a1477.jsonl` for the hook's `agent_id` `ac0618b17d35a1477`). A fork copies its parent's lines, so a message id counts only in the first file it was seen in. Reading all 19 transcripts of this project (18 MB) took 0.05 s. Files of sessions no longer shown are forgotten.
2. **Price table** (Fred): `config.json` `"prices"`, USD per million tokens, the API list prices from the claude-api skill (cached 2026-10-06): opus 4 / 20, cache read 0.20, cache write 5 min 5.00, 1 h 8.00; sonnet 2 / 10, 0.20, 2.50, 4.00; haiku 0.10 / 0.50, 0.01, 0.125, 0.20; fable 10 / 50, 0.25, 12.50, 20.00 (cache writes 1.25x / 2x input). `usage.speed == "fast"` costs 2x. Haiku's price for prompts over 100K tokens is left out. A model the table does not name costs 0. On a subscription these are "equivalent cost".
3. **Exact or estimated.** A window run's own cost is exact: `total_cost_usd` from its result line (`run_ended`), solid cells. While a window run is live its session shows the transcript estimate (`~`, hatched). Today's exact spend = window runs finished since local midnight; estimated = the other sessions' transcript messages since midnight; the burn rate ("$ / min now") = the estimated cost of all shown transcripts in the last 5 minutes / 5; the model shares = today's estimated cost per model family over all transcripts.
4. **Soft daily limit and spend cells** (Fred): `daily_budget_usd` 15; 1 cell = $0.50 in a 30 x 5 grid filled column by column (the mockup's), so $75 shows; past that the grid gains one column per $2.50; the orange outline sits on the cell at 80 % of the limit (cell 24). `daily_budget_usd` 0 = no outline. The mockup's renderer counted columns where its legend counts cells; the plan counts cells.
5. **Activity cells** (Fred): tool steps (main and agents) per minute, last 30 minutes, fixed levels: 1-2 = l1, 3-5 = l2, 6-9 = l3, 10+ = l4, so rows compare.
6. **Rail and pill** (Fred): Needs you first, then Working, in start order (no reshuffle on every event); Done today lives in the Overview. The pill shows the first 9 chips and `+N`; about 6 chips fit in the 640 px rail, the rest scroll.
7. **Prep card takes the pane** (Fred): crumb `Prep / <project>`, the mockup's block grammar, Run / Run raw / Edit / Cancel in the bottom bar, Esc = Cancel.
8. **Steps, Timeline, Chat** (Fred): a segmented control on the feed block of the focus pane (Chat only for window runs).
9. **Compose project** (Fred): a select in the Overview compose row (allowed projects, then seen ones marked `(off)`), saved through `/api/draft` into `window.json`; the old header filter goes. `Allow runs in X` shows above the compose row when needed.
10. **Notes and extra levers** (Fred): one notes block under the title (FAIL detail, denial, failure, finished-with-denials, hand off, rules size, delegate?, 2 writers, escalated, window copy links, route, turns, rules files); glyph + word + text, orange only for a needs-you hand off, red for FAIL / denied / failed. Escalate and Resume join the lever bar when allowed; one muted "off" line under the buttons. Rail chips carry no badges.
11. **Model mix** (Fred): share of today's spend per model family, under the spend cells; the phase 4 counts (`State.mix`, the bottom strip) are removed. Window runs finished today and the "2 writers" warnings go in the Overview footer line.
12. **Window memory** (Fred): `~/.claude/console/window.json` keeps `form` (`pill` / `open`), `x`, `y` (saved when the window closes; dropped when no monitor shows that point), `on_top` and the compose `project`. First start: open, Overview, centred, on top.
13. **Peek card** (Fred): opens for a new `stop`, `blocked`, `failed` or `interrupted` session (not Stall? or a red gauge), oldest first, one at a time; an event is `id | state | turn start`. Send answer / Open in terminal / Resume / Open, or Esc, closes it and that event never reopens it. Events that exist when the window starts, or that happen while it is open, count as seen.
14. **Borderless window, verified** (closes the BRAINSTORM 7.5 open check): `frameless=True, easy_drag=False, transparent=True`; drag only on elements with class `pywebview-drag-region` (pywebview `DRAG_REGION_SELECTOR`). A frameless window asked for 400 x 640 came up 384 x 601; `window.resize()` from a thread then gave exactly 380 x 48, 380 x 200 and 400 x 640 (GetWindowRect), and `js_api` calls worked, so `WindowApi._restore` resizes once the window shows. `min_size` is (380, 48). pywebview drops the DWM shadow on a transparent window, so the forms draw a 1 px `--edge` line. Close (`✕`) destroys the window, which ends the service inside it; window runs keep going (detached, as before). Methods starting with `_` stay hidden from the page (pywebview skips them).
15. **Doto** (BRAINSTORM 7.5): the Google Fonts latin subset, weight 700, as `web/doto.woff2` (3,928 bytes), with its licence `web/doto-OFL.txt` (SIL OFL 1.1, from google/fonts); served at `/doto.woff2`; a test checks the page files hold no `https://` (no network calls). Cascadia Mono for every other figure, Segoe UI for text.
16. **Taken from the mockup without a question:** tokens and dark-first palette (light follows the system); tone: red for Blocked / Failed, orange for any other needs-you session, green for Done, ink for Running, muted otherwise; the STOP state reads `Asks you`; chip labels are the project's initials (CONTENT MANAGER -> CM) or its first 5 letters (BRAINAMP -> BRAIN); context cells = 30 cells up to `gauge_red_tokens`, the hand-off zone from `gauge_yellow_tokens` (10K and cell 15 by default), all red at red; the path cells Prep / Run / Verify / Hand off (green done, ink current, red FAIL); agent rows start with `main` (the session cost minus its agents); one blinking cell on the running agent (or on `main` while the session works and no agent runs), off for reduced motion; Stop asks for a second click within 3 s; Esc goes back (peek, Prep, focus), Ctrl+N = new task; `–` for a cost not known yet.
17. **Not in this plan:** a light / dark switch in the window (the system decides), the Jarvis widget link, other harnesses (phase 5).
18. **Not verified by Claude:** the native window on Fred's screen (rounded transparent corners, dragging, the peek card resizing the pill on a real event, the light theme). Task 7.

## Code map

```text
cc_events.py        + transcript_path on SessionStart / UserPromptSubmit / Stop lines
console/
  usage.py          NEW  transcripts -> cost per message (price table), per file, since a time, per family
  window.py         NEW  WindowApi (pywebview js_api): form, on_top, minimize, close; window.json
  state.py          + transcript_path, run_costs; spent, burn, activity, main_steps, turn_ts, agent cost,
                      spend block; - mix, family()
  paths.py          + daily_budget_usd, prices; load_window / save_window
  server.py         Hub.usage + read_costs(); /doto.woff2; /api/config gauge + project; /api/draft project
  __main__.py       borderless window with WindowApi
web/
  index.html        pill + peek, rail + pane
  style.css         Console Cells tokens and classes
  app.js            pill, peek, rail, Overview, focus, Prep, compose
  doto.woff2        NEW  Doto 700 latin (OFL)
  doto-OFL.txt      NEW  its licence
tests/
  test_usage.py     NEW  prices, incremental read, one count per message, forks, keep
  test_window.py    NEW  forms, sizes, window.json, place on screen
  test_cc_events.py test_state.py test_server.py   extended
```

Dependencies point one way: `state -> claude_cli, redact, usage`; `usage -> claude_cli`; `server -> usage`; `window -> paths`.

## Files to modify

`cc_events.py`, `console/state.py`, `console/paths.py`, `console/server.py`, `console/__main__.py`, `web/index.html`, `web/style.css`, `web/app.js`, `tests/test_cc_events.py`, `tests/test_state.py`, `tests/test_server.py`, `PLAN.md`, `BRAINSTORM.md`, `CLAUDE.md`, this file. New: `console/usage.py`, `console/window.py`, `web/doto.woff2`, `web/doto-OFL.txt`, `tests/test_usage.py`, `tests/test_window.py`. Unchanged: `install_hooks.py` (no new hook event), `console/runs.py`, `console/levers.py`, `console/prep.py`, `tests/fake_claude.py`.

## TODO

- [x] Task 1: hook logs the transcript path
- [x] Task 2: estimated cost from transcripts
- [x] Task 3: state (spend, activity, agent cost)
- [x] Task 4: service (reads transcripts, serves Doto, keeps the compose project)
- [x] Task 5: borderless window
- [x] Task 6: Console Cells window
- [ ] Task 7: Fred: live check in the real window
- [ ] Task 8: close the phase

---

### Task 1: Hook logs the transcript path

The hook runs inside every Claude Code session as soon as the file is saved: the change is one key, read with `.get()`, so it cannot raise.

**Files:**
- Modify: `cc_events.py` (two edits), `tests/test_cc_events.py` (one edit; 1 new test)

- [ ] **Step 1: Edit `tests/test_cc_events.py`**

Find:

```python
    def test_permission_denied_keeps_reason(self):
```

Replace with:

```python
    def test_turn_events_carry_the_transcript_path(self):
        for event in ("SessionStart", "UserPromptSubmit", "Stop"):
            rec = cc_events.build_record(self.base(event, transcript_path="C:/t/s1.jsonl"))
            self.assertEqual(rec["transcript_path"], "C:/t/s1.jsonl", event)
        rec = cc_events.build_record(self.base("PreToolUse", tool_name="Read", transcript_path="C:/t/s1.jsonl"))
        self.assertNotIn("transcript_path", rec)

    def test_permission_denied_keeps_reason(self):
```

- [ ] **Step 2: Run it, expect a failure**

```bash
py -m unittest tests.test_cc_events
```

Expected: `FAILED (errors=1)` (`KeyError: 'transcript_path'` in the new test).

- [ ] **Step 3: Edit `cc_events.py`**

Find:

```python
_INJECTED = re.compile(r"\s*<(?!pasted_content\b)([A-Za-z][\w-]*)[^>]*>.*?</\1>\s*", re.S)
```

Replace with:

```python
_INJECTED = re.compile(r"\s*<(?!pasted_content\b)([A-Za-z][\w-]*)[^>]*>.*?</\1>\s*", re.S)
# The service reads the transcript for the estimated cost (console/usage.py): a path, never content.
TRANSCRIPT_EVENTS = ("SessionStart", "UserPromptSubmit", "Stop")
```

Find:

```python
        rec["load_reason"] = data.get("load_reason")
    return {k: v for k, v in rec.items() if v not in (None, "")}
```

Replace with:

```python
        rec["load_reason"] = data.get("load_reason")
    if event in TRANSCRIPT_EVENTS:
        rec["transcript_path"] = data.get("transcript_path")
    return {k: v for k, v in rec.items() if v not in (None, "")}
```

- [ ] **Step 4: Run all tests**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 88 tests` ... `OK`.

- [ ] **Step 5: Commit**

```bash
git add cc_events.py tests/test_cc_events.py
git commit -m "feat: hook logs the transcript path on turn events"
```

**DONE WHEN**
- [ ] 88 tests OK; `git status --short` empty.

---

### Task 2: Estimated cost from transcripts

**Files:**
- Create: `console/usage.py`, `tests/test_usage.py` (full files below; 3 tests)
- Modify: `console/paths.py` (one edit)

- [ ] **Step 1: Create `tests/test_usage.py`** with:

```python
import json
import tempfile
import unittest
from pathlib import Path

from console import paths, usage

PRICES = paths.DEFAULTS["prices"]


def line(mid, model="claude-opus-5-5", ts="2026-10-10T10:00:00.000Z", side=False, **use):
    return json.dumps({"type": "assistant", "isSidechain": side, "timestamp": ts,
                       "message": {"id": mid, "model": model, "usage": use}}) + "\n"


class CostTest(unittest.TestCase):
    def test_message_cost(self):
        self.assertAlmostEqual(usage.message_cost("claude-opus-5-5", {"input_tokens": 1_000_000}, PRICES), 4.0)
        tagged = {"cache_creation_input_tokens": 300_000, "cache_read_input_tokens": 1_000_000,
                  "cache_creation": {"ephemeral_1h_input_tokens": 100_000}, "output_tokens": 10_000}
        # 200K 5-minute writes x 2.50 + 100K 1-hour writes x 4.00 + 1M reads x 0.20 + 10K out x 10
        self.assertAlmostEqual(usage.message_cost("claude-sonnet-5-5", tagged, PRICES), 0.5 + 0.4 + 0.2 + 0.1)
        self.assertAlmostEqual(usage.message_cost("claude-opus-5-5", {"output_tokens": 1_000_000, "speed": "fast"},
                                                  PRICES), 40.0)
        self.assertEqual(usage.message_cost("gpt-5", {"input_tokens": 1_000_000}, PRICES), 0.0)


class UsageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "s1.jsonl")
        self.usage = usage.Usage(PRICES)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, mode="a"):
        with open(self.path, mode, encoding="utf-8") as fh:
            fh.write(text)

    def test_reads_as_the_file_grows_and_counts_each_message_once(self):
        self.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n"
                   + line("m1", input_tokens=1_000_000)
                   + line("m1", input_tokens=1_000_000)  # the same message, its next content block
                   + line("m2", model="<synthetic>", input_tokens=5)
                   + line("m3", ts="2026-10-10T11:00:00.000Z", output_tokens=50_000)[:40], "w")
        self.assertEqual(self.usage.poll(self.path), 1)
        self.assertAlmostEqual(self.usage.cost([self.path]), 4.0)
        self.write(line("m3", ts="2026-10-10T11:00:00.000Z", output_tokens=50_000)[40:])
        self.assertEqual(self.usage.poll(self.path), 1)
        self.assertEqual(self.usage.poll(self.path), 0)
        self.assertAlmostEqual(self.usage.cost([self.path]), 5.0)
        since = usage._when("2026-10-10T10:30:00Z")
        self.assertAlmostEqual(self.usage.cost([self.path], since=since), 1.0)
        self.assertEqual(self.usage.poll(str(Path(self.tmp.name) / "missing.jsonl")), 0)

    def test_fork_copies_count_once_and_families(self):
        self.write(line("m1", input_tokens=1_000_000) + line("m2", model="claude-haiku-5-5", output_tokens=1_000_000), "w")
        fork = str(Path(self.tmp.name) / "s2.jsonl")
        Path(fork).write_text(line("m1", input_tokens=1_000_000) + line("m9", model="claude-sonnet-5-5",
                                                                         input_tokens=1_000_000), encoding="utf-8")
        self.usage.poll(self.path)
        self.usage.poll(fork)
        self.assertAlmostEqual(self.usage.cost([fork]), 2.0)
        fams = self.usage.families([self.path, fork])
        self.assertEqual(sorted(fams), ["haiku", "opus", "sonnet"])
        self.assertAlmostEqual(fams["opus"], 4.0)
        self.usage.keep([fork])
        self.assertEqual(self.usage.cost([self.path]), 0)
        self.assertEqual(self.usage.poll(fork), 0)  # still read up to its end
        self.assertEqual(Path(usage.agent_path(self.path, "a1")).as_posix(),
                         Path(self.tmp.name, "s1", "subagents", "agent-a1.jsonl").as_posix())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it, expect a failure**

```bash
py -m unittest tests.test_usage
```

Expected: `FAILED (errors=1)` (`ImportError: cannot import name 'usage' from 'console'`).

- [ ] **Step 3: Edit `console/paths.py`**

Find:

```python
    "delegate_after_reads": 10,
}
```

Replace with:

```python
    "delegate_after_reads": 10,
    "daily_budget_usd": 15,
    # USD per million tokens, API list prices (claude-api skill, 2026-10-06); fast mode costs 2x.
    # Haiku's higher price for prompts over 100K tokens is left out.
    "prices": {
        "fable": {"input": 10, "output": 50, "cache_read": 0.25, "cache_write_5m": 12.5, "cache_write_1h": 20},
        "opus": {"input": 4, "output": 20, "cache_read": 0.2, "cache_write_5m": 5, "cache_write_1h": 8},
        "sonnet": {"input": 2, "output": 10, "cache_read": 0.2, "cache_write_5m": 2.5, "cache_write_1h": 4},
        "haiku": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write_5m": 0.125, "cache_write_1h": 0.2},
    },
}
```

- [ ] **Step 4: Create `console/usage.py`** with:

```python
"""Estimated cost from Claude Code transcripts: each assistant message's usage x the price table in
config.json ("prices", USD per million tokens). Read only, as the files grow: one offset per file.
A message's usage repeats on each of its content-block lines, and a fork copies its parent's lines,
so a message id counts once, in the first file it was seen in."""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from . import claude_cli


def agent_path(transcript: str, agent_id: str) -> str:
    """Where Claude Code writes a subagent's transcript: <session>/subagents/agent-<id>.jsonl."""
    return str(Path(transcript).with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl")


def message_cost(model: str, usage: dict, prices: dict) -> float:
    """USD for one message; 0.0 for a model the table does not price."""
    p = prices.get(claude_cli.model_alias(model))
    if not p:
        return 0.0
    tagged = usage.get("cache_creation") or {}
    write_1h = int(tagged.get("ephemeral_1h_input_tokens") or 0)
    write_5m = max(0, int(usage.get("cache_creation_input_tokens") or 0) - write_1h)
    cost = (int(usage.get("input_tokens") or 0) * p["input"]
            + int(usage.get("output_tokens") or 0) * p["output"]
            + int(usage.get("cache_read_input_tokens") or 0) * p["cache_read"]
            + write_5m * p["cache_write_5m"] + write_1h * p["cache_write_1h"]) / 1e6
    return cost * 2 if usage.get("speed") == "fast" else cost


def _when(stamp) -> float:
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


class Usage:
    def __init__(self, prices: dict):
        self.prices = prices
        self.lock = threading.Lock()
        self.offsets = {}   # path -> bytes read (always at a line end)
        self.messages = {}  # path -> {message id: (ts, family, cost)}
        self.owner = {}     # message id -> the path that counts it

    def poll(self, path: str) -> int:
        """Read what was added to `path`; returns the number of new messages."""
        try:
            size = os.path.getsize(path)
        except (OSError, TypeError, ValueError):
            return 0
        start = self.offsets.get(path, 0)
        if size == start:
            return 0
        if size < start:  # rewritten: read it again
            start = 0
            with self.lock:
                for mid in self.messages.pop(path, {}):
                    self.owner.pop(mid, None)
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                data = fh.read()
        except OSError:
            return 0
        end = data.rfind(b"\n") + 1  # a half-written last line waits for the next poll
        new = 0
        with self.lock:
            msgs = self.messages.setdefault(path, {})
            for line in data[:end].splitlines():
                if b'"usage"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) and rec.get("type") == "assistant" else None
                usage = msg.get("usage") if isinstance(msg, dict) else None
                if not usage or msg.get("model") in (None, "<synthetic>"):
                    continue
                mid = msg.get("id") or rec.get("uuid")
                if self.owner.setdefault(mid, path) != path:
                    continue
                new += mid not in msgs
                msgs[mid] = (_when(rec.get("timestamp")), claude_cli.model_alias(msg["model"]),
                             message_cost(msg["model"], usage, self.prices))
            self.offsets[path] = start + end
        return new

    def keep(self, paths) -> None:
        """Forget the files of sessions no longer shown: the service runs for days."""
        keep = set(paths)
        with self.lock:
            for path in (set(self.offsets) | set(self.messages)) - keep:
                for mid in self.messages.pop(path, {}):
                    if self.owner.get(mid) == path:
                        del self.owner[mid]
                self.offsets.pop(path, None)

    def cost(self, paths, since: float = 0.0) -> float:
        with self.lock:
            return sum(c for p in paths for ts, _, c in self.messages.get(p, {}).values() if ts >= since)

    def families(self, paths, since: float = 0.0) -> dict:
        out = {}
        with self.lock:
            for p in paths:
                for ts, fam, c in self.messages.get(p, {}).values():
                    if ts >= since and c:
                        out[fam] = out.get(fam, 0.0) + c
        return out
```

- [ ] **Step 5: Run all tests**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 91 tests` ... `OK`.

- [ ] **Step 6: Commit**

```bash
git add console/usage.py console/paths.py tests/test_usage.py
git commit -m "feat: estimated cost from transcripts and the price table"
```

**DONE WHEN**
- [ ] 91 tests OK; `git status --short` empty.

---

### Task 3: State: spend, activity, agent cost

`State.snapshot(now, usage=None)` takes the `usage.Usage` reader (the hub passes it in Task 4; without it every estimate is 0). The phase 4 `mix` block and `family()` go (fixed decision 11); the phase 4 page reads `mix`, so between this task and Task 6 the old window shows no rows: finish Task 6 before starting the window.

**Files:**
- Modify: `console/state.py` (full file below), `tests/test_state.py` (two edits; `test_model_mix` replaced by 2 tests)

- [ ] **Step 1: Edit `tests/test_state.py`**

Find:

```python
import copy
import unittest

from console import paths
from console.state import State

T0 = 1_000_000.0
```

Replace with:

```python
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from console import paths, usage
from console.state import State

T0 = 1_000_000.0


def line(mid, ts, model, **use):
    """One transcript line with a usage block, `ts` seconds since the epoch."""
    stamp = datetime.fromtimestamp(ts, timezone.utc).isoformat()
    return json.dumps({"type": "assistant", "timestamp": stamp,
                       "message": {"id": mid, "model": model, "usage": use}}) + "\n"
```

Find (the whole `test_model_mix` method):

```python
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
```

Replace with:

```python
    def test_spent_exact_or_estimated_and_today(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        chat, run = str(Path(tmp.name) / "a.jsonl"), str(Path(tmp.name) / "b.jsonl")
        Path(chat).write_text(line("m1", T0 - 60, "claude-opus-5-5", input_tokens=1_000_000), encoding="utf-8")
        agent = Path(usage.agent_path(chat, "x1"))
        agent.parent.mkdir(parents=True)
        agent.write_text(line("m2", T0 - 30, "claude-haiku-5-5", output_tokens=2_000_000), encoding="utf-8")
        Path(run).write_text(line("m3", T0 - 20, "claude-sonnet-5-5", input_tokens=500_000), encoding="utf-8")
        self.feed(ev("UserPromptSubmit", T0 - 100, sid="a", transcript_path=chat),
                  ev("SubagentStart", T0 - 40, sid="a", agent_id="x1", agent_type="Explore"),
                  ev("run_started", T0 - 50, sid="b", model="sonnet"),
                  ev("UserPromptSubmit", T0 - 49, sid="b", transcript_path=run),
                  ev("run_ended", T0 - 10, sid="b", cost=1.25, subtype="success"),
                  ev("run_started", T0 - 5, sid="c", model="sonnet"),
                  ev("UserPromptSubmit", T0 - 4, sid="d"))
        reader = usage.Usage(paths.DEFAULTS["prices"])
        for f in self.state.transcripts(T0):
            reader.poll(f)
        snap = self.state.snapshot(T0, reader)
        rows = {r["id"]: r for r in snap["sessions"]}
        self.assertEqual((rows["a"]["spent"], rows["a"]["spent_exact"], rows["a"]["burn"]), (5.0, False, 1.0))
        self.assertEqual(rows["a"]["agents"][0]["cost"], 1.0)
        self.assertEqual((rows["b"]["spent"], rows["b"]["spent_exact"]), (1.25, True))
        self.assertEqual((rows["c"]["spent"], rows["c"]["spent_exact"]), (None, False))  # live, no transcript yet
        self.assertIsNone(rows["d"]["spent"])
        self.assertEqual(snap["spend"], {"today": 6.25, "exact": 1.25, "estimated": 5.0, "burn": 1.2, "budget": 15,
                                         "runs": 1, "models": [["opus", 0.667], ["sonnet", 0.167], ["haiku", 0.167]]})
        self.assertEqual(self.state.snapshot(T0)["spend"]["today"], 1.25)  # no reader: exact only

    def test_activity_cells_per_minute(self):
        now = 1_000_020.0  # a minute boundary
        recs = [ev("UserPromptSubmit", now - 1900)]
        for back, n, agents in ((-10, 12, 2), (5 * 60 - 1, 1, 0), (600, 4, 0), (29 * 60, 7, 0), (31 * 60, 1, 0)):
            recs += [ev("PreToolUse", now - back, tool="Read", what="a.py",
                        **({"agent_id": "x1"} if k < agents else {})) for k in range(n)]
        self.feed(*sorted(recs, key=lambda r: r["ts"]))
        row = self.row(now + 30)
        self.assertEqual(row["activity"], [3] + [0] * 18 + [2] + [0] * 4 + [1] + [0] * 4 + [4])
        self.assertEqual((row["main_steps"], row["turn_ts"]), (23, now - 1900))
```

- [ ] **Step 2: Run them, expect failures**

```bash
py -m unittest tests.test_state
```

Expected: `FAILED (errors=2)` (`AttributeError: 'State' object has no attribute 'transcripts'`, `KeyError: 'activity'`).

- [ ] **Step 3: Replace `console/state.py`** with:

```python
"""Sessions -> agents -> steps, built from event records; states computed at snapshot time."""
import re
import time
from dataclasses import dataclass, field

from . import claude_cli, redact, usage as usage_mod

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
ACTIVITY_MIN = 30               # activity cells: one per minute, the last 30 minutes
ACTIVITY_STEPS = (1, 3, 6, 10)  # steps in a minute for levels 1-4 (Fred: 1-2, 3-5, 6-9, 10+)
BURN_S = 300                    # "$ / min now" is the estimated cost of the last 5 minutes / 5
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
    run_costs: list = field(default_factory=list)  # [ts, cost] per finished window run: exact spend
    transcript_path: str = ""  # read by usage.Usage for the estimated cost


def midnight(now: float) -> float:
    """Local midnight before `now`: "today" for the spend figures."""
    t = time.localtime(now)
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


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
        if rec.get("transcript_path"):
            s.transcript_path = rec["transcript_path"]
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
            s.run_costs.append([ts, float(rec.get("cost") or 0)])
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

    def files(self, s: Session) -> list:
        """The session's transcript and its agents' transcripts ([] until a hook line names it)."""
        if not s.transcript_path:
            return []
        return [s.transcript_path] + [usage_mod.agent_path(s.transcript_path, a) for a in s.agents]

    def transcripts(self, now: float) -> list:
        """Every transcript of the shown sessions: the hub reads them for the estimated cost."""
        return [f for s in self.sessions.values() if now - s.last_ts <= SHOW_FOR_S for f in self.files(s)]

    def activity(self, s: Session, now: float) -> list:
        """Tool steps (main + agents) per minute over the last ACTIVITY_MIN minutes, oldest first,
        as levels 0-4."""
        counts = [0] * ACTIVITY_MIN
        end = int(now // 60)
        for step in s.steps:
            back = end - int(step["ts"] // 60)
            if 0 <= back < ACTIVITY_MIN:
                counts[ACTIVITY_MIN - 1 - back] += 1
        return [sum(c >= t for t in ACTIVITY_STEPS) for c in counts]

    def snapshot(self, now: float, usage=None) -> dict:
        """`usage` (a usage.Usage) adds the estimated cost; without it every estimate is 0."""
        cost = usage.cost if usage else (lambda files, since=0.0: 0.0)
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
            files = self.files(s)
            exact = s.window and not s.run_live  # a live window run has no result line yet: estimate
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
                "turn_ts": s.turns[-1][0] if s.turns else s.started_ts,
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
                "spent": round(s.cost if exact else cost(files), 4) if exact or files else None,
                "spent_exact": exact,
                "burn": round(cost(files, now - BURN_S) / (BURN_S / 60), 4),
                "activity": self.activity(s, now),
                "main_steps": sum(1 for st in s.steps if not st["agent"]),
                "agents": [self._agent_row(a, s, cost) for a in
                           sorted(s.agents.values(), key=lambda a: a.started_ts)],
            })
        return {
            "now": now,
            "sessions": rows,
            "writers": [{"project_dir": p, "sessions": ids} for p, ids in sorted(writers.items())],
            "counts": {g: sum(1 for r in rows if r["group"] == g) for g in ("needs", "working", "done")},
            "spend": self.spend([self.sessions[r["id"]] for r in rows], now, usage),
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

    def spend(self, sessions: list, now: float, usage=None) -> dict:
        """Today since local midnight: exact = finished window runs (their result line), estimated =
        the other sessions' transcripts; the model shares and the burn rate come from all transcripts."""
        start = midnight(now)
        exact = sum(c for s in sessions for ts, c in s.run_costs if ts >= start)
        runs = sum(1 for s in sessions for ts, _ in s.run_costs if ts >= start)
        every = [f for s in sessions for f in self.files(s)]
        estimated = burn = 0.0
        families = {}
        if usage:
            estimated = usage.cost([f for s in sessions if not s.window for f in self.files(s)], start)
            burn = usage.cost(every, now - BURN_S) / (BURN_S / 60)
            families = usage.families(every, start)
        total = sum(families.values())
        rank = {m: i for i, m in enumerate(claude_cli.MODELS[::-1])}  # biggest first
        models = [[m, round(c / total, 3)] for m, c in
                  sorted(families.items(), key=lambda kv: (rank.get(kv[0], len(rank)), kv[0]))]
        return {"today": round(exact + estimated, 4), "exact": round(exact, 4),
                "estimated": round(estimated, 4), "burn": round(burn, 4),
                "budget": self.cfg["daily_budget_usd"], "runs": runs, "models": models}

    def _agent_row(self, a: Agent, s: Session, cost=None) -> dict:
        if a.done:
            symbol, text, tone = STATES["done"]
        elif s.in_turn:
            symbol, text, tone = STATES["running"]
        else:
            symbol, text, tone = "…", "No stop seen", "info"
        fill, ctx_tone = self.gauge(a.tokens or None)
        spent = cost([usage_mod.agent_path(s.transcript_path, a.id)]) if cost and s.transcript_path else 0.0
        return {"id": a.id, "type": a.type or "agent", "model": a.model, "effort": a.effort,
                "tokens": a.tokens, "steps": a.steps, "doing": a.doing, "verdict": a.verdict,
                "cost": round(spent, 4),
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

- [ ] **Step 4: Run all tests**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 92 tests` ... `OK`.

- [ ] **Step 5: Commit**

```bash
git add console/state.py tests/test_state.py
git commit -m "feat: state adds estimated spend, activity cells and today's spend"
```

**DONE WHEN**
- [ ] 92 tests OK; `git status --short` empty.

---

### Task 4: Service: reads transcripts, serves Doto, keeps the compose project

**Files:**
- Modify: `console/server.py` (eight edits in two steps), `console/paths.py` (two edits), `tests/test_server.py` (two edits; 1 new test)
- Create: `web/doto.woff2`, `web/doto-OFL.txt` (downloaded, checked by SHA-256)

- [ ] **Step 1: Edit `tests/test_server.py`**

Find:

```python
    def test_static_and_ping(self):
        self.assertEqual(self.get("/")[0], 200)
        self.assertEqual(json.loads(self.get("/api/ping")[1]), {"app": "claude-console"})
```

Replace with:

```python
    def test_static_and_ping(self):
        self.assertEqual(self.get("/")[0], 200)
        self.assertEqual(json.loads(self.get("/api/ping")[1]), {"app": "claude-console"})
        status, font = self.get("/doto.woff2")
        self.assertEqual((status, font[:4]), (200, b"wOF2"))
        for page in ("/", "/style.css", "/app.js"):  # the window makes no network calls
            self.assertNotIn(b"https://", self.get(page)[1], page)

    def test_hub_reads_transcripts_for_the_estimate(self):
        transcript = Path(self.tmp.name) / "s2.jsonl"
        transcript.write_text(json.dumps({"type": "assistant", "timestamp": "2026-10-10T10:00:00Z", "message": {
            "id": "m1", "model": "claude-sonnet-5-5", "usage": {"input_tokens": 1_000_000}}}) + "\n", encoding="utf-8")
        with open(Path(self.tmp.name) / "events-2026-10-10.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": 9e12, "event": "UserPromptSubmit", "session_id": "s2", "prompt": "hi",
                                 "transcript_path": str(transcript)}) + "\n")
        self.hub.poll_once()
        self.assertEqual(self.hub.read_costs(), 1)
        self.assertEqual(self.hub.read_costs(), 0)
        row = next(s for s in self.hub.snapshot()["sessions"] if s["id"] == "s2")
        self.assertEqual((row["spent"], row["spent_exact"]), (2.0, False))
```

Find:

```python
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["projects"], cfg["claude"], cfg["default_model"]), ([str(self.project)], True, "sonnet"))
```

Replace with:

```python
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["projects"], cfg["claude"], cfg["default_model"], cfg["project"]),
                         ([str(self.project)], True, "sonnet", ""))
        self.assertEqual(self.call("/api/draft", {"text": "", "project": str(self.project)})[0], 200)
        self.assertEqual(self.call("/api/config")[1]["project"], str(self.project))
        self.assertEqual(cfg["gauge"], [150000, 300000])
        self.assertEqual(self.call("/api/draft", {"text": "", "project": 3})[0], 400)
```

- [ ] **Step 2: Run them, expect failures**

```bash
py -m unittest tests.test_server
```

Expected: `FAILED (failures=1, errors=2)` (`KeyError: 'project'`, `AttributeError: 'Hub' object has no attribute 'read_costs'`, `/doto.woff2` gives `(404, b'not ')`).

- [ ] **Step 3: Download Doto and its licence.** In Git Bash from the repo root:

```bash
curl -fsSL -o web/doto.woff2 "https://fonts.gstatic.com/s/doto/v3/t5tJIRMbNJ6TQG7Il_EKPqP9zTnvqqGNcuvLMt1JIphF3-WuyE-T.woff2"
curl -fsSL -o web/doto-OFL.txt "https://raw.githubusercontent.com/google/fonts/main/ofl/doto/OFL.txt"
sha256sum web/doto.woff2 web/doto-OFL.txt
```

Expected (stop and tell Fred if either differs):

```text
2a4172c50d322f9d1f7c900fa93bad86a591e9626f4048ade721c97ef150c2b6 *web/doto.woff2
26a7b58bdba6cda8a78ca6e8b3791d8013b8abc6d5e6519f84193893aee02020 *web/doto-OFL.txt
```

The woff2 URL is the `latin` face of `https://fonts.googleapis.com/css2?family=Doto:wght@700` (asked with a Chrome user agent); the licence starts `Copyright 2024 The Doto Project Authors`.

- [ ] **Step 4: Edit `console/paths.py`**

Find:

```python
import copy
import json
import os
from pathlib import Path
```

Replace with:

```python
import copy
import json
import os
import threading
from pathlib import Path
```

Find:

```python
def ensure_config() -> dict:
```

Replace with:

```python
_WINDOW_LOCK = threading.Lock()  # the page (project) and the window (form, place) both save


def load_window(folder: Path) -> dict:
    """window.json: the window's last form, place, always-on-top, and the compose project."""
    try:
        data = json.loads((Path(folder) / "window.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_window(folder: Path, **fields) -> dict:
    """Merge `fields` into window.json (written whole, through a temp file)."""
    with _WINDOW_LOCK:
        data = dict(load_window(folder), **fields)
        path = Path(folder) / "window.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name("window.json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return data


def ensure_config() -> dict:
```

- [ ] **Step 5: Edit `console/server.py`**

Find:

```python
from . import claude_cli, events, guard, levers, paths, prep, runs
```

Replace with:

```python
from . import claude_cli, events, guard, levers, paths, prep, runs, usage
```

Find:

```python
          "/style.css": ("style.css", "text/css; charset=utf-8")}
```

Replace with:

```python
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/doto.woff2": ("doto.woff2", "font/woff2")}
```

Find:

```python
        self.runs = runs.RunManager(cfg, folder, exe)
```

Replace with:

```python
        self.runs = runs.RunManager(cfg, folder, exe)
        self.usage = usage.Usage(cfg["prices"])
```

Find:

```python
    def tick(self) -> None:
```

Replace with:

```python
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

    def tick(self) -> None:
```

Find:

```python
            self.poll_once()
            if time.monotonic() - last_tick >= TICK_S:
```

Replace with:

```python
            self.poll_once()
            self.read_costs()
            if time.monotonic() - last_tick >= TICK_S:
```

Find:

```python
            return self.state.snapshot(time.time())
```

Replace with:

```python
            return self.state.snapshot(time.time(), self.usage)
```

- [ ] **Step 6: Edit `console/server.py` (config and draft)**

Find:

```python
                               "config_path": str(self.hub.folder / "config.json")})
```

Replace with:

```python
                               "config_path": str(self.hub.folder / "config.json"),
                               "gauge": [cfg["gauge_yellow_tokens"], cfg["gauge_red_tokens"]],
                               "project": paths.load_window(self.hub.folder).get("project", "")})
```

Find:

```python
    def _draft(self, body):
        text = body.get("text")
        if not isinstance(text, str) or len(text) > MAX_PROMPT:
            return self._error(400, "bad draft")
        self.hub.folder.mkdir(parents=True, exist_ok=True)
        (self.hub.folder / "draft.txt").write_text(text, encoding="utf-8")
        return self._json({"ok": True})
```

Replace with:

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
```

- [ ] **Step 7: Run all tests**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 93 tests` ... `OK`.

- [ ] **Step 8: Commit**

```bash
git add console/server.py console/paths.py tests/test_server.py web/doto.woff2 web/doto-OFL.txt
git commit -m "feat: service reads transcripts for the estimate, serves Doto, keeps the compose project"
```

**DONE WHEN**
- [ ] 93 tests OK; `git status --short` empty.

---

### Task 5: Borderless window

**Files:**
- Create: `console/window.py`, `tests/test_window.py` (full files below; 2 tests)
- Modify: `console/__main__.py` (one edit)

- [ ] **Step 1: Create `tests/test_window.py`** with:

```python
import tempfile
import unittest
from pathlib import Path

from console import paths, window


class FakeWindow:
    def __init__(self):
        self.calls = []
        self.x, self.y = 120, 80
        self.on_top = True

    def resize(self, w, h):
        self.calls.append(("resize", w, h))

    def minimize(self):
        self.calls.append(("minimize",))

    def destroy(self):
        self.calls.append(("destroy",))


class WindowApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.win = FakeWindow()
        self.api = window.WindowApi(self.folder)
        self.api._attach(self.win)

    def tearDown(self):
        self.tmp.cleanup()

    def test_forms_resize_and_are_remembered(self):
        self.assertEqual(self.api.state(), {"form": "open", "on_top": True})  # first start
        self.assertEqual(self.api.form("pill"), "pill")
        self.api.form("pill", 190)    # one peek card
        self.api.form("pill", 5000)   # never taller than PEEK_MAX_H
        self.assertEqual(self.api.form("anything"), "open")
        self.assertEqual(self.win.calls, [("resize", 380, 48), ("resize", 380, 190), ("resize", 380, 360),
                                          ("resize", 400, 640)])
        self.api.form("pill")
        self.assertFalse(self.api.on_top(False))
        self.assertFalse(self.win.on_top)
        again = window.WindowApi(self.folder)
        self.assertEqual(again.state(), {"form": "pill", "on_top": False})
        again._attach(self.win)
        again._restore()
        self.assertEqual(self.win.calls[-1], ("resize", 380, 48))
        self.api.minimize()
        self.api.close()
        self.assertEqual(self.win.calls[-2:], [("minimize",), ("destroy",)])

    def test_place_is_kept_only_while_on_a_screen(self):
        self.assertEqual(self.api._place(), (None, None))
        self.api._remember_place()
        self.assertEqual(paths.load_window(self.folder)["x"], 120)
        self.assertEqual(self.api._place(), (120, 80))
        paths.save_window(self.folder, x=-99999, y=-99999)
        self.assertEqual(self.api._place(), (None, None))
        self.assertNotIn("_attach", [n for n in dir(self.api) if not n.startswith("_")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it, expect a failure**

```bash
py -m unittest tests.test_window
```

Expected: `FAILED (errors=1)` (`ImportError: cannot import name 'window' from 'console'`).

- [ ] **Step 3: Create `console/window.py`** with:

```python
"""The borderless pywebview window (BRAINSTORM 7.5): folded, a 380 x 48 pill that grows down for one
peek card; open, 400 x 640. The page calls this as window.pywebview.api.<method>(...); the form,
the place on screen and always-on-top are kept in window.json for the next start."""
import ctypes
from ctypes import wintypes
from pathlib import Path

from . import paths

PILL_W, PILL_H = 380, 48
OPEN_W, OPEN_H = 400, 640
PEEK_MAX_H = 360  # the pill plus one card, never taller


def on_screen(x: int, y: int) -> bool:
    """True when a monitor shows that point (a saved place on an unplugged screen is dropped)."""
    try:
        return bool(ctypes.windll.user32.MonitorFromPoint(wintypes.POINT(x + 20, y + 20), 0))
    except (AttributeError, OSError, TypeError, ValueError):
        return True


class WindowApi:
    """Names starting with _ stay hidden from the page."""

    def __init__(self, folder: Path):
        self._folder = Path(folder)
        self._window = None
        saved = paths.load_window(self._folder)
        self._form = saved.get("form") if saved.get("form") in ("pill", "open") else "open"
        self._on_top = saved.get("on_top") is not False

    def _attach(self, window) -> None:
        self._window = window

    def _place(self):
        """The saved (x, y) when it is still on a screen, else (None, None): centred."""
        saved = paths.load_window(self._folder)
        x, y = saved.get("x"), saved.get("y")
        if isinstance(x, int) and isinstance(y, int) and on_screen(x, y):
            return x, y
        return None, None

    def _restore(self) -> None:
        """After the window shows: pywebview sizes a frameless window short of the asked size."""
        self.form(self._form)

    def _remember_place(self) -> None:
        paths.save_window(self._folder, x=self._window.x, y=self._window.y)

    def state(self) -> dict:
        return {"form": self._form, "on_top": self._on_top}

    def form(self, name: str, height: int = 0) -> str:
        """"pill" (with `height` > 48 while a peek card shows) or "open"."""
        if name == "pill":
            self._window.resize(PILL_W, max(PILL_H, min(int(height or PILL_H), PEEK_MAX_H)))
        else:
            name = "open"
            self._window.resize(OPEN_W, OPEN_H)
        self._form = name
        paths.save_window(self._folder, form=name)
        return name

    def on_top(self, on: bool) -> bool:
        self._on_top = bool(on)
        self._window.on_top = self._on_top
        paths.save_window(self._folder, on_top=self._on_top)
        return self._on_top

    def minimize(self) -> None:
        self._window.minimize()

    def close(self) -> None:
        """Closes the window and the service inside it; window runs keep going (they are detached)."""
        self._window.destroy()
```

- [ ] **Step 4: Edit `console/__main__.py`**

Find:

```python
    import webview  # imported late: --serve works without pywebview
    webview.create_window("Claude Console", url, width=420, height=640,
                          min_size=(360, 400), on_top=True)
    webview.start()
    return 0
```

Replace with:

```python
    import webview  # imported late: --serve works without pywebview
    from . import window
    api = window.WindowApi(paths.home())
    x, y = api._place()
    win = webview.create_window("Claude Console", url, js_api=api, width=window.OPEN_W, height=window.OPEN_H,
                                x=x, y=y, min_size=(window.PILL_W, window.PILL_H), frameless=True,
                                easy_drag=False, transparent=True, on_top=api.state()["on_top"])
    api._attach(win)
    win.events.closing += api._remember_place
    webview.start(api._restore)
    return 0
```

- [ ] **Step 5: Run all tests**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 95 tests` ... `OK`.

- [ ] **Step 6: Commit**

```bash
git add console/window.py console/__main__.py tests/test_window.py
git commit -m "feat: borderless window with a pill and an open form, remembered in window.json"
```

**DONE WHEN**
- [ ] 95 tests OK; `git status --short` empty. (The old page still renders in the borderless window until Task 6.)

---

### Task 6: Console Cells window

All styling stays in `web/style.css`, tokens first (CLAUDE.md). The page works the same in a browser (`py -m console --serve`): there the window buttons (`–`, `✕`, `⊤`) are hidden and folding only swaps the form on the page.

**Files:**
- Modify: `web/index.html`, `web/style.css`, `web/app.js` (full files below)

- [ ] **Step 1: Replace `web/index.html`** with:

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
    <nav id="rail" class="rail" aria-label="Sessions">
      <div class="drag pywebview-drag-region" title="Drag to move">&#8943;</div>
      <button class="rb" data-go="overview" title="Overview (Esc)" aria-label="Overview">&#9638;</button>
      <div class="sep"></div>
      <div id="chips" class="chips"></div>
      <div class="sep"></div>
      <button class="rb" data-go="new" title="New task (Ctrl+N)" aria-label="New task">&#65291;</button>
      <div class="grow pywebview-drag-region" title="Drag to move"></div>
      <div id="total" class="total"></div>
      <button id="ontop" class="rb on native-only" data-go="ontop" title="Always on top (on)" aria-label="Always on top">&#8868;</button>
      <button class="rb" data-go="fold" title="Fold to pill" aria-label="Fold to pill">&#8963;</button>
    </nav>
    <section class="pane">
      <div id="banner" class="banner" hidden><b>OFFLINE</b> The service stopped answering. Runs keep going; the window reconnects by itself.</div>
      <div class="ptop">
        <span id="crumb" class="crumb m pywebview-drag-region"></span>
        <button class="rb native-only" data-go="minimize" aria-label="Minimize">&ndash;</button>
        <button class="rb x native-only" data-go="close" aria-label="Close" title="Close window (runs keep going)">&#10005;</button>
      </div>
      <div id="scroll" class="scroll"></div>
      <div id="bar"></div>
    </section>
  </div>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Replace `web/style.css`** with:

```css
/* Console Cells (BRAINSTORM 7.5, design/rework/locked/console-cells.html). All styling lives here,
   tokens first. Dark first; the light theme follows the system. Every quantity is counted in cells. */
@font-face { font-family: "Doto"; src: url("/doto.woff2") format("woff2"); font-weight: 700; font-display: block; }
:root {
  --page: #0b0c0e; --win: #121315; --rail: #0e0f11; --raise: #1a1c1f; --off: #24272b; --ink: #ebe8e1;
  --mut: #9a9993; --line: #26292d; --edge: rgb(255 255 255 / 6%);
  --you: #ff8a3d; --bad: #ff5a4e; --ok: #5ed39a; --on-you: #1a0d00; --close: #c42b1c;
  --ui: "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
  --mono: "Cascadia Mono", Consolas, monospace;
  --dot: "Doto", "Cascadia Mono", monospace;
  color-scheme: dark;
}
@media (prefers-color-scheme: light) {
  :root {
    --page: #dedcd6; --win: #f4f3ef; --rail: #ebe9e4; --raise: #e7e5e0; --off: #d6d4ce; --ink: #17181b;
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
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
  outline: 2px solid var(--you); outline-offset: 1px; }
.m { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; }
.mut { color: var(--mut); }
.lbl { font: 500 10.5px var(--mono); letter-spacing: .04em; text-transform: uppercase; color: var(--mut); }
.lbl.y { color: var(--you); } .lbl.r { color: var(--bad); }
.pywebview-drag-region { cursor: grab; }

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

/* session chips (pill and rail) */
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

/* open: rail + pane */
.win { width: 100vw; height: 100vh; background: var(--win); border-radius: 12px; border: 1px solid var(--edge);
  display: grid; grid-template-columns: 56px minmax(0, 1fr); overflow: hidden; }
.rail { background: var(--rail); border-right: 1px solid var(--line); display: flex; flex-direction: column;
  align-items: center; gap: 4px; padding: 6px 0 4px; user-select: none; min-height: 0; }
.rail .drag { color: var(--mut); font-size: 12px; letter-spacing: -1px; height: 14px; line-height: 10px; width: 100%; text-align: center; }
.rail .sep { width: 26px; height: 1px; background: var(--line); margin: 3px 0; flex: none; }
.rail .chips { display: flex; flex-direction: column; align-items: center; gap: 4px; overflow-y: auto;
  min-height: 0; scrollbar-width: none; }
.rail .grow { flex: 1; width: 100%; min-height: 8px; }
.rail .chipcell { width: 46px; padding: 5px 0 3px; gap: 3px; flex: none; }
.rail .chipcell .cells { grid-template-columns: repeat(5, 4px); }
.rail .chipcell.sel { background: var(--raise); box-shadow: inset 0 0 0 1px var(--line); }
.rail .chipcell .lab { font: 500 9px var(--mono); color: var(--mut); max-width: 46px; overflow: hidden; white-space: nowrap; }
.rail .chipcell .gl { font-size: 10px; }
.rail .chipcell .dot { top: 3px; right: 6px; }
.rb { width: 34px; height: 32px; border: 0; border-radius: 6px; background: transparent; color: var(--mut);
  cursor: pointer; font: 14px var(--ui); flex: none; }
.rb:hover { background: var(--raise); color: var(--ink); }
.rb.on { color: var(--ink); }
.rb.x:hover { background: var(--close); color: #fff; }
.total { font: 700 15px/1 var(--dot); text-align: center; }
.total small { display: block; font: 9px var(--mono); color: var(--mut); margin-top: 2px; }
.native-only { display: none; }
html.native .native-only { display: inline-block; }

.pane { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.ptop { height: 36px; flex: none; display: flex; align-items: center; gap: 6px; padding-left: 12px;
  border-bottom: 1px solid var(--line); user-select: none; }
.ptop .crumb { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--mut); }
.ptop .rb { width: 34px; height: 36px; border-radius: 0; }
.banner { flex: none; display: flex; gap: 8px; align-items: center; padding: 6px 12px;
  background: color-mix(in srgb, var(--bad) 12%, var(--win)); font: 12px var(--ui); border-bottom: 1px solid var(--line); }
.banner b { color: var(--bad); font: 600 11px var(--mono); }
.scroll { flex: 1; overflow-y: auto; padding: 12px; display: grid; gap: 14px; align-content: start; }
.stack { display: grid; gap: 14px; align-content: start; min-width: 0; }
.stack:empty { display: none; }
h2 { font: 600 16px/1.3 var(--ui); margin: 3px 0 0; text-wrap: balance; overflow-wrap: anywhere; }
.hero { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 14px; align-items: end; }
.hero .big { font: 700 40px/.9 var(--dot); letter-spacing: .02em; }
.hero .side { display: grid; gap: 1px; justify-items: end; text-align: right; min-width: 0; }
.hero .side b { font: 500 13px var(--mono); }
.hero .side .m { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.blk { display: grid; gap: 5px; }
.blk .hd { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
.blk .hd .m { color: var(--mut); }
.notes { display: grid; gap: 3px; color: var(--mut); }
.notes div { overflow-wrap: anywhere; }
.notes b { font: 600 11px var(--mono); margin-right: 6px; color: var(--ink); }
.notes b.y { color: var(--you); } .notes b.r { color: var(--bad); }
.link { color: var(--ink); text-decoration: underline; text-underline-offset: 2px; cursor: pointer; }
.ctx15 { grid-template-columns: repeat(15, minmax(0, 1fr)); gap: 2px; }
.ctx15 i { aspect-ratio: 1.2; }
.scale { display: flex; justify-content: space-between; font: 10px var(--mono); color: var(--mut); }
.path { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
.path > span { display: grid; gap: 4px; font: 500 11px var(--mono); color: var(--mut); }
.path .cells { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.path .cells i { aspect-ratio: 1.6; }
.path .cur { color: var(--ink); } .path .ok { color: var(--ok); } .path .bad { color: var(--bad); }
.agents { display: grid; gap: 6px; }
.agent { display: grid; grid-template-columns: 74px minmax(0, 1fr) 40px 40px; gap: 8px; align-items: center; }
.agent .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.agent .cells { grid-template-columns: repeat(24, minmax(0, 1fr)); }
.agent span:nth-child(n+3) { text-align: right; color: var(--mut); }
.agent span.c { color: var(--ink); }
.act30 { grid-template-columns: repeat(30, minmax(0, 1fr)); }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
.seg button { font: 500 11px var(--mono); border: 0; background: transparent; color: var(--mut); padding: 3px 8px; cursor: pointer; }
.seg button.on { background: var(--raise); color: var(--ink); }
.feed { display: grid; gap: 2px; color: var(--mut); }
.feed > div { display: grid; grid-template-columns: 40px 64px minmax(0, 1fr); gap: 8px; }
.feed > div span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.feed > div span:last-child { color: var(--ink); }
.feed > div.r span:last-child { color: var(--bad); }
.tl { display: grid; grid-template-columns: 84px minmax(0, 1fr); gap: 8px; align-items: center; }
.tl .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--mut); }
.tl-track { position: relative; height: 10px; background: var(--off); border-radius: 1px; }
.tl-track i { position: absolute; top: 0; bottom: 0; min-width: 2px; background: var(--ink); }
.tl-axis { display: flex; justify-content: space-between; font: 10px var(--mono); color: var(--mut); }
.chat { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: 8px; }
.chat .who { color: var(--mut); font: 11px var(--mono); }
.chat .text { white-space: pre-wrap; overflow-wrap: anywhere; }
.chat.you .text { font-weight: 600; }
.chat.tool .text, .chat.result .text { color: var(--mut); font: 12px var(--mono); }
.chat.note .text { color: var(--you); }
.levers { flex: none; border-top: 1px solid var(--line); padding: 8px 10px; display: grid; gap: 6px; }
.levers:empty { display: none; }
.say { font: 11px var(--mono); color: var(--mut); min-height: 0; overflow-wrap: anywhere; }
.say:empty { display: none; }
.say .r { color: var(--bad); }
.say .btn { min-height: 24px; padding: 1px 8px; margin-left: 6px; font-size: 11px; }

/* overview */
.spend { grid-template-columns: repeat(var(--cols, 30), minmax(0, 1fr)); grid-template-rows: repeat(5, auto);
  grid-auto-flow: column; }
.legend { display: flex; gap: 12px; flex-wrap: wrap; font: 10.5px var(--mono); color: var(--mut); }
.legend span { display: inline-flex; gap: 5px; align-items: center; }
.legend i { width: 8px; height: 8px; display: inline-block; border-radius: 1px; background: var(--off); }
.legend i.f { background: var(--ink); }
.legend i.h { background: repeating-linear-gradient(135deg, var(--ink) 0 1.2px, transparent 1.2px 3.2px), var(--off); }
.legend i.mk { box-shadow: inset 0 0 0 1px var(--you); }
.heat { display: grid; gap: 4px; }
.hrow { background: transparent; border: 0; padding: 0; text-align: left; width: 100%; display: grid;
  grid-template-columns: 84px minmax(0, 1fr) 40px; gap: 8px; align-items: center; cursor: pointer; border-radius: 4px; }
.hrow:hover .nm { color: var(--ink); }
.hrow .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--mut); }
.hrow .nm.y { color: var(--you); } .hrow .nm.r { color: var(--bad); }
.hrow .c { text-align: right; }
.haxis { display: grid; grid-template-columns: 84px minmax(0, 1fr) 40px; gap: 8px; font: 10px var(--mono); color: var(--mut); }
.haxis span:nth-child(2) { display: flex; justify-content: space-between; }
.card { display: grid; gap: 3px; padding: 8px 10px; border-radius: 8px; background: var(--raise);
  border: 1px solid transparent; text-align: left; cursor: pointer; width: 100%; }
.card:hover { border-color: var(--line); }
.card.y { border-color: color-mix(in srgb, var(--you) 45%, transparent); }
.card.r { border-color: color-mix(in srgb, var(--bad) 45%, transparent); }
.card .sub { color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.compose { flex: none; border-top: 1px solid var(--line); padding: 8px 10px; display: grid; gap: 6px; }
.compose .lr { flex-wrap: nowrap; }
.compose select { max-width: 120px; background: var(--raise); border: 1px solid var(--line); border-radius: 6px;
  padding: 6px 4px; font: 11px var(--mono); }
.compose textarea { flex: 1; min-width: 0; resize: none; field-sizing: content; min-height: 34px; max-height: 140px;
  font: 13px var(--ui); background: var(--raise); border: 1px solid transparent; border-radius: 6px; padding: 7px 9px; }
.kbd { font: 11px var(--mono); color: var(--mut); border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; }
.empty { display: grid; gap: 8px; justify-items: start; padding: 8px 0; }
.empty .cells { grid-template-columns: repeat(15, 10px); }
.empty p { margin: 0; color: var(--mut); font-size: 13px; max-width: 34ch; }
.loading { display: flex; gap: 8px; align-items: center; color: var(--mut); font-size: 12px; }
.loading .cells { grid-template-columns: repeat(6, 6px); }
.prep-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.prep-row select { background: var(--raise); border: 1px solid var(--line); border-radius: 6px; padding: 4px; font: 12px var(--mono); }
.text { white-space: pre-wrap; overflow-wrap: anywhere; }
```

- [ ] **Step 3: Replace `web/app.js`** with:

```javascript
// Claude Console window, Console Cells (BRAINSTORM 7.5): a folded pill with one peek card, or a rail of
// session chips plus one pane (Overview, a session in focus, or the Prep card). Renders /api/stream
// snapshots; the levers, Prep and runs go through the same routes as phases 2-4.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const RESUME_TEXT = "You were interrupted. Check `git diff` first, then finish the task.";
const BUSY = new Set(["running", "quiet", "stall"]);
const PEEK = new Set(["stop", "blocked", "failed", "interrupted"]);  // a new one opens the peek card
const SPEND_CELL = 0.5;   // 1 spend cell = $0.50
const PILL_CHIPS = 9;

let snap = null;
let cfg = null;          // /api/config
let live = false;
let form = "open";       // open | pill
let pane = "overview";   // overview | focus | prep
let openId = null;
let tab = "steps";       // steps | timeline | chat
let card = null;         // the Prep card on screen
let busy = "";           // what the compose box waits for ("" = nothing)
let note = "";           // the compose box's last message (an error stays until Fred types)
let draft = "";
let project = "";        // the compose project (window.json, through /api/draft)
let draftTimer = null;
let leversSig = "";
let askSig = "";
let onTop = true;
let peekKey = "";        // the event the peek card shows
let firstSnap = true;
const seen = new Set();  // peek events already shown, answered or dismissed

// -- helpers ---------------------------------------------------------------------------
function native() { return !!(window.pywebview && window.pywebview.api); }
function money(x) { return Number(x || 0).toFixed(2); }
function spentText(s) { return s.spent == null ? "&ndash;" : (s.spent_exact ? "" : "~") + money(s.spent); }
function kTokens(n) { return n >= 1000 ? Math.round(n / 1000) + "K" : String(n || 0); }
function hhmm(ts) { return new Date(ts * 1000).toTimeString().slice(0, 5); }
function ago(sec) {
  sec = Math.max(0, Math.round(sec));
  if (sec < 60) return sec + "s";
  const min = Math.floor(sec / 60);
  if (min < 60) return min + "m" + (min < 10 && sec % 60 ? " " + (sec % 60) + "s" : "");
  return Math.floor(min / 60) + "h " + (min % 60) + "m";
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
function abbrev(name) {  // CONTENT MANAGER -> CM, BRAINAMP -> BRAIN
  const words = String(name || "?").split(/[\s_\-.]+/).filter(Boolean);
  return (words.length > 1 ? words.map((w) => w[0]).join("").slice(0, 3) : (words[0] || "?").slice(0, 5)).toUpperCase();
}
function cellsHtml(classes) { return classes.map((c) => `<i${c ? ` class="${c}"` : ""}></i>`).join(""); }
function railSessions() { return snap ? snap.sessions.filter((s) => s.group !== "done")
  .sort((a, b) => (a.group === "needs" ? 0 : 1) - (b.group === "needs" ? 0 : 1)) : []; }
function current() { return snap && snap.sessions.find((s) => s.id === openId); }
function routeText(s) {
  const run = [alias(s.model), s.effort].filter(Boolean).join("/");
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

function chip(s, big) {
  const t = tone(s), flag = s.group === "needs" ? `<span class="dot${t === "r" ? " r" : ""}"></span>` : "";
  return `<button class="chipcell${big && pane === "focus" && s.id === openId ? " sel" : ""}" data-open="${esc(s.id)}"
    title="${esc(label(s) + ": " + s.title)}"><span class="cells">${chipCells(s.ctx_tokens)}</span>
    <span class="gl ${t === "y" || t === "r" ? t : ""}">${s.symbol}</span>${big ? `<span class="lab">${esc(abbrev(s.project))}</span>` : ""}${flag}</button>`;
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
  const rail = railSessions(), more = rail.length - PILL_CHIPS;
  $("pill").innerHTML = `<span class="grip pywebview-drag-region" title="Drag to move">&#8942;&#8942;</span>
    ${rail.slice(0, PILL_CHIPS).map((s) => chip(s, false)).join("")}${more > 0 ? `<span class="more">+${more}</span>` : ""}
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

function peekCard(s) {
  const t = tone(s), age = `<span class="age m">${ago(snap.now - s.last_ts)}</span>`;
  const head = `<div class="l1"><span class="st ${t}">${s.symbol} ${esc(label(s))}</span><span class="t">${esc(s.title)}</span>${age}</div>`;
  const open = '<button class="btn" data-peek="open">Open</button>';
  if (s.state === "stop") {
    return `<div class="askbox">${head}<div class="q">${esc(s.stop_question)}</div>
      <div class="lr"><input id="pk" aria-label="Answer" placeholder="Type your answer">
      <button class="btn you" data-peek="send">Send answer</button></div><div id="pk-msg" class="say"></div></div>`;
  }
  let text = "", buttons = open;
  if (s.state === "blocked" && s.denied) {
    text = `denied: ${s.denied.tool} ${s.denied.what}`;
    if (s.window && !s.run_live) buttons = '<button class="btn" data-peek="terminal">Open in terminal</button>' + open;
  } else if (s.state === "failed" && s.failed) {
    text = `${s.failed.error} ${s.failed.details || ""}`;
  } else if (s.state === "interrupted") {
    text = "The run stopped before it finished.";
    if (s.window) buttons = '<button class="btn you" data-peek="resume">Resume</button>' + open;
  }
  return `<div class="askbox${t === "r" ? " r" : ""}">${head}<div class="q">${esc(text)}</div>
    <div class="lr">${buttons}</div><div id="pk-msg" class="say"></div></div>`;
}

function dismissPeek() {
  if (!peekKey) return;
  seen.add(peekKey);
  renderFolded(true);
}

async function peekAct(name, button) {
  const s = snap.sessions.find((x) => peekId(x) === peekKey);
  if (!s) return dismissPeek();
  if (name === "open") { dismissPeek(); openSession(s.id); await setForm("open"); return; }
  button.disabled = true;
  try {
    if (name === "send") {
      const text = $("pk").value.trim();
      if (!text) { button.disabled = false; return; }
      await api("/api/continue", { session: s.id, text });
    }
    if (name === "resume") await api("/api/continue", { session: s.id, text: RESUME_TEXT });
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    dismissPeek();
  } catch (e) {
    button.disabled = false;
    $("pk-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`;
    fitPill();
  }
}

// -- rail --------------------------------------------------------------------------------
function renderRail() {
  $("chips").innerHTML = railSessions().map((s) => chip(s, true)).join("");
  $("total").innerHTML = `${money(snap.spend.today)}<small>today</small>`;
  $("banner").hidden = live;
}

function renderOnTop() {
  $("ontop").classList.toggle("on", onTop);
  $("ontop").title = `Always on top (${onTop ? "on" : "off"})`;
}

// -- panes -------------------------------------------------------------------------------
function showPane(name) {
  pane = name;
  leversSig = askSig = "";
  if (name === "overview") {
    $("scroll").innerHTML = '<div id="o-body" class="stack"></div>';
    $("bar").innerHTML = `<div class="compose"><div id="c-say" class="say"></div>
      <div class="lr"><select id="c-project" aria-label="Project"></select>
      <textarea id="c-prompt" rows="1" spellcheck="false" aria-label="New task"
        title="Enter = Prep · Ctrl+Enter = Run raw · Shift+Enter = new line"></textarea><span class="kbd">Enter</span></div></div>`;
    $("c-prompt").value = draft;
  } else if (name === "focus") {
    $("scroll").innerHTML = `<div id="f-head" class="stack"></div><div id="f-ask" class="stack"></div>
      <div id="f-body" class="stack"></div><div id="f-feed" class="stack"></div>`;
    $("bar").innerHTML = '<div id="f-levers" class="levers"></div>';
  } else {
    renderPrep();
  }
  render();
}

function openSession(id, list = "steps") { openId = id; tab = list; showPane("focus"); }

function render() {
  if (!snap) return;
  renderRail();
  if (firstSnap) {  // only events after the window opened bring up the peek card
    snap.sessions.filter((s) => PEEK.has(s.state)).forEach((s) => seen.add(peekId(s)));
    firstSnap = false;
  }
  if (form === "pill") { renderFolded(false); return; }
  snap.sessions.filter((s) => PEEK.has(s.state)).forEach((s) => seen.add(peekId(s)));  // seen while open
  if (pane === "overview") renderOverview();
  else if (pane === "focus") renderFocus();
}

// -- overview ----------------------------------------------------------------------------
function cardHtml(s) {
  const t = tone(s);
  let sub = s.stop_question || "";
  if (s.denied) sub = `denied: ${s.denied.tool} ${s.denied.what}`;
  else if (s.failed) sub = `${s.failed.error} ${s.failed.details || ""}`;
  else if (s.state === "interrupted") sub = "stopped before it finished: Resume";
  else if (s.state === "stall") sub = "no events for 10 min, still running";
  else if (!sub && s.ctx_tone === "red") sub = `context ${kTokens(s.ctx_tokens)}: hand off`;
  else if (s.state === "done") sub = s.verdict ? s.verdict : routeText(s);
  return `<button class="card${t === "y" || t === "r" ? " " + t : ""}" data-open="${esc(s.id)}">
    <span class="l1"><span class="st ${t}">${s.symbol} ${esc(label(s))}</span><span class="t">${esc(s.title)}</span>
    <span class="age m">${ago(snap.now - s.last_ts)}</span></span>
    <span class="sub m">${esc(s.project)}${sub ? " · " + esc(sub) : ""}</span></button>`;
}

function spendCells(sp) {
  const solid = Math.round(sp.exact / SPEND_CELL), all = Math.round(sp.today / SPEND_CELL);
  const mark = sp.budget > 0 ? Math.ceil(sp.budget * 0.8 / SPEND_CELL) - 1 : -1;
  const cols = Math.max(30, Math.ceil(Math.max(all, mark + 1) / 5));
  const cls = Array.from({ length: cols * 5 }, (_, k) =>
    [k < solid ? "f" : k < all ? "h" : "", k === mark ? "mk" : ""].filter(Boolean).join(" "));
  return `<div class="cells spend" style="--cols:${cols}">${cellsHtml(cls)}</div>`;
}

function renderOverview() {
  $("crumb").textContent = "All projects · today";
  const sp = snap.spend, rail = railSessions();
  const needs = snap.sessions.filter((s) => s.group === "needs");
  const done = snap.sessions.filter((s) => s.group === "done");
  let html = `<div class="hero"><span class="big">${money(sp.today)}</span><span class="side">
    <span class="lbl">Today, USD</span><b>$${money(sp.burn)} / min now</b>
    <span class="m mut">${sp.budget > 0 ? "soft limit $" + sp.budget : "no soft limit"}</span></span></div>
    <div class="blk">${spendCells(sp)}<div class="legend"><span><i class="f"></i>exact $${money(sp.exact)}</span>
    <span><i class="h"></i>estimated $${money(sp.estimated)}</span>${sp.budget > 0 ? '<span><i class="mk"></i>80 % of limit</span>' : ""}
    <span>1 cell = $0.50</span></div>
    ${sp.models.length ? `<div class="legend">${sp.models.map(([m, f]) =>
      `<span>${esc(m)} ${f < 0.01 ? "&lt;1" : Math.round(f * 100)} %</span>`).join("")}</div>` : ""}</div>`;
  if (rail.length) {
    html += `<div class="blk"><div class="hd"><span class="lbl">Activity · last 30 min</span><span class="m">cost</span></div>
      <div class="heat">${rail.map((s) => {
        const t = tone(s);
        return `<button class="hrow" data-open="${esc(s.id)}" title="${esc(label(s) + ": " + s.title)}">
        <span class="nm m${t === "y" || t === "r" ? " " + t : ""}">${s.symbol} ${esc(s.title)}</span>
        <span class="cells act30">${activityCells(s.activity)}</span><span class="c m">${spentText(s)}</span></button>`;
      }).join("")}</div>
      <div class="haxis"><span></span><span><span>${hhmm(snap.now - 1800)}</span><span>${hhmm(snap.now)}</span></span><span></span></div></div>`;
  }
  if (needs.length) html += `<div class="blk"><div class="hd"><span class="lbl">Needs you · ${needs.length}</span></div>${needs.map(cardHtml).join("")}</div>`;
  if (done.length) html += `<div class="blk"><div class="hd"><span class="lbl">Done today · ${done.length}</span></div>${done.map(cardHtml).join("")}</div>`;
  if (!snap.sessions.length) {
    html += `<div class="empty"><span class="lbl">Empty</span><div class="cells">${cellsHtml(Array(30).fill(""))}</div>
      <p>No Claude Code session in the last 24 hours. Start one in VS Code or a terminal, or type a task below.</p></div>`;
  }
  const pass = done.filter((s) => s.verdict === "PASS").length;
  html += `<div class="legend"><span>done today ${done.length}${pass ? " · " + pass + " PASS" : ""}</span>
    ${sp.runs ? `<span>window runs ${sp.runs}</span>` : ""}
    ${snap.writers.map((w) => `<span>2 writers: ${esc(baseName(w.project_dir))}</span>`).join("")}</div>`;
  $("o-body").innerHTML = html;
  renderCompose();
}

// -- compose (Overview) -----------------------------------------------------------------
function projects() {
  const out = new Map();
  if (cfg) for (const p of cfg.projects) out.set(p, baseName(p));
  if (snap) for (const s of snap.sessions) if (s.project_dir && !out.has(s.project_dir)) out.set(s.project_dir, s.project + " (off)");
  return out;
}

function runnable() { return !!cfg && cfg.claude && cfg.projects.includes(project); }

function renderCompose() {
  const select = $("c-project");
  if (!select) return;
  const list = projects();
  if (!list.has(project)) project = (cfg && cfg.projects[0]) || [...list.keys()][0] || "";
  const opts = [...list].map(([dir, name]) => `<option value="${esc(dir)}"${dir === project ? " selected" : ""}>${esc(name)}</option>`).join("");
  if (select.dataset.sig !== opts) { select.innerHTML = opts; select.dataset.sig = opts; }
  $("c-prompt").disabled = !!busy || !runnable();
  $("c-prompt").placeholder = runnable() ? "New task in " + baseName(project) : "";
  let html = note;
  if (busy) html = `<span class="loading"><span class="cells">${cellsHtml(["f", "", "", "", "", ""])}</span>${esc(busy)}</span>`;
  else if (!html && cfg && !cfg.claude) html = '<span class="r">claude.exe not found: set "claude_exe" in config.json</span>';
  else if (!html && !project) html = "To run: start a Claude Code session in a project first";
  else if (!html && !runnable()) html = `Runs are off in ${esc(baseName(project))}: a run uses this repo's hooks and settings without asking.
    <button class="btn" data-go="allow">Allow runs in ${esc(baseName(project))}</button>`;
  $("c-say").innerHTML = html;
}

let loadingTimer = null;
function setBusy(text) {
  busy = text;
  note = "";
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
  draftTimer = setTimeout(() => api("/api/draft", { text: draft, project }).catch(() => {}), 600);
}

async function doPrep() {
  const text = $("c-prompt").value.trim();
  if (!text || busy || !runnable()) return;
  setBusy(`Haiku is reading ${baseName(project)}, 10 to 30 s`);
  try {
    card = await api("/api/prep", { project_dir: project, prompt: text });
    setBusy("");
    showPane("prep");
  } catch (e) {
    setBusy("");
    note = `<span class="r">Prep failed: ${esc(e.message)}</span>`;
    renderCompose();
  }
}

async function doRun(projectDir, prompt, model, effort, prepId) {
  if (busy) return;
  setBusy("Starting the run ...");
  try {
    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "" });
    draft = "";
    saveDraft();
    card = null;
    setBusy("");
    openSession(r.session, "chat");
  } catch (e) {
    setBusy("");
    if (pane === "prep") $("p-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`;
    else { note = `<span class="r">Run failed: ${esc(e.message)}</span>`; renderCompose(); }
  }
}

async function allowRuns(button) {
  button.disabled = true;
  try {
    cfg.projects = (await api("/api/allow", { project_dir: project })).projects;
    note = "";
    renderCompose();
    $("c-prompt").focus();
  } catch (err) {
    note = `<span class="r">Allow failed: ${esc(err.message)}</span>`;
    renderCompose();
  }
}

// -- Prep card ---------------------------------------------------------------------------
function options(list, value) { return list.map((v) => `<option${v === value ? " selected" : ""}>${esc(v)}</option>`).join(""); }

function renderPrep() {
  const f = card.fields;
  $("crumb").textContent = "Prep / " + baseName(card.project_dir);
  $("scroll").innerHTML = `
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
  $("bar").innerHTML = `<div class="levers"><div class="lr"><button class="btn go" data-pact="run">Run</button>
    <button class="btn" data-pact="raw">Run raw</button><button class="btn" data-pact="edit">Edit</button>
    <button class="btn" data-pact="cancel">Cancel</button></div><div id="p-msg" class="say"></div></div>`;
  $("p-prompt").focus();
}

function prepAct(name) {
  if (busy) return;
  if (name === "run") doRun(card.project_dir, $("p-prompt").value.trim(), $("p-model").value, $("p-effort").value, card.id);
  if (name === "raw") doRun(card.project_dir, card.raw, cfg.default_model, cfg.default_effort, "");
  if (name === "edit") { card = null; showPane("overview"); $("c-prompt").focus(); }
  if (name === "cancel") { card = null; draft = ""; saveDraft(); showPane("overview"); }
}

// -- focus: one session ------------------------------------------------------------------
function notes(s) {
  const out = [];
  const line = (word, cls, text) => out.push(`<div><b class="${cls}">${word}</b>${text}</div>`);
  if (s.verdict === "FAIL" && s.verdict_detail) line("× FAIL", "r", esc(s.verdict_detail));
  if (s.denied) line("■ denied", "r", `${esc(s.denied.tool)} ${esc(s.denied.what)} <span class="mut">${esc(s.denied.reason)}</span>`);
  if (s.denials && s.denials.length) {
    const d = s.denials[0], more = s.denials.length > 1 ? ` (+${s.denials.length - 1})` : "";
    line(`△ ${s.denials.length} denied`, "", `${esc(d.tool)} ${esc(d.what)}${more}: the run still finished; open it in a terminal to allow`);
  }
  if (s.failed) line("× " + esc(s.failed.error), "r", esc(s.failed.details));
  if (s.handoff_hint) line("↻ hand off", s.group === "needs" ? "y" : "",
    `${s.ctx_tone === "red" ? "the context is large" : s.follow_ups + " follow-ups"}: one task = one chat`);
  if (s.rules_warn) line("△ rules", "", `${esc(s.rules_warn)}: keep CLAUDE.md short; move procedures to skills and narrow rules to path rules`);
  if (s.delegate_hint) line("⇢ delegate", "", `${s.reads} reads in the main chat this turn: heavy reading belongs in a subagent (Explore)`);
  if (s.two_writers) line("△ 2 writers", "", "another session edits files in this repo");
  if (s.escalated) line("↑ escalated", "", esc(s.escalated));
  if (s.forked_from) line("↳ copy of", "", `<span class="link" data-open="${esc(s.forked_from)}">${esc(s.forked_from.slice(0, 8))}</span>`);
  if (s.forks.length) line("↳ continued in", "", s.forks.map((f) => `<span class="link" data-open="${esc(f)}">${esc(f.slice(0, 8))}</span>`).join(" "));
  line("route", "", `${esc(routeText(s))}${s.route_reason ? ` <span class="mut">${esc(s.route_reason)}</span>` : ""}`);
  line("turns", "", `${s.follow_ups} follow-up(s) · ${s.compactions} compaction(s)${s.stopped ? " · stopped by you" : ""}`);
  if (s.rules.length) line("rules", "", s.rules.map((r) => `${esc(r.file)} ${r.lines} lines ${kb(r.bytes)}`).join(" · "));
  return `<div class="notes m">${out.join("")}</div>`;
}

function pathHtml(s) {  // the playbook path: Prep, Run, Verify, Hand off
  const working = BUSY.has(s.state);
  const steps = [
    ["Prep", s.prep ? "ok" : ""],
    ["Run", working && !["verify", "handoff"].includes(s.kind) ? "cur" : s.prompts ? "ok" : ""],
    ["Verify", s.verdict === "PASS" ? "ok" : s.verdict === "FAIL" ? "bad" : working && s.kind === "verify" ? "cur" : ""],
    ["Hand off", s.state === "done" ? "ok" : working && s.kind === "handoff" ? "cur" : ""],
  ];
  const fill = { ok: "g", cur: "f", bad: "r", "": "" };
  return `<div class="path" aria-label="Task progress">${steps.map(([n, st]) =>
    `<span class="${st}"><span class="cells">${cellsHtml(Array(6).fill(fill[st]))}</span>${n}</span>`).join("")}</div>`;
}

function agentsHtml(s) {
  const working = BUSY.has(s.state), agentLive = s.agents.some((a) => a.text === "Running");
  const agentCost = s.agents.reduce((t, a) => t + a.cost, 0);
  const rows = [{ nm: "main", steps: s.main_steps, cost: s.spent == null ? null : Math.max(0, s.spent - agentCost),
                  live: working && !agentLive }]
    .concat(s.agents.map((a) => ({ nm: a.type + (a.text === "Done" ? " ✓" : "") + (a.verdict ? " " + a.verdict : ""),
                                   steps: a.steps, cost: a.cost, live: a.text === "Running" })));
  return `<div class="blk"><div class="hd"><span class="lbl">Agents · 1 cell = 2 steps</span><span class="m">steps / cost</span></div>
    <div class="agents">${rows.map((r) => {
      const n = Math.min(24, Math.max(Math.ceil(r.steps / 2), r.live ? 1 : 0));
      const cls = Array.from({ length: 24 }, (_, k) => k < n ? (r.live && k === n - 1 ? "f live" : "f") : "");
      return `<div class="agent"><span class="nm m" title="${esc(r.nm)}">${esc(r.nm)}</span><span class="cells">${cellsHtml(cls)}</span>
        <span class="m">${r.steps}</span><span class="m c">${r.cost == null ? "&ndash;" : money(r.cost)}</span></div>`;
    }).join("")}</div></div>`;
}

function renderFocus() {
  const s = current();
  if (!s) {
    $("crumb").textContent = "Starting ...";
    $("f-head").innerHTML = '<div class="mut">Starting ... (the session shows up with its first event)</div>';
    return;
  }
  const t = tone(s);
  $("crumb").textContent = [s.project, s.source === "?" ? "" : s.source, [alias(s.model), s.effort].filter(Boolean).join(" ")].filter(Boolean).join(" / ");
  const when = BUSY.has(s.state) ? ago(snap.now - s.turn_ts) : (s.state === "stop" ? "waiting " : "") + ago(snap.now - s.last_ts);
  $("f-head").innerHTML = `<div><span class="st ${t}">${s.symbol} ${esc(label(s))} · ${when}</span><h2>${esc(s.title)}</h2></div>`;
  renderAsk(s);
  const ctxWord = s.ctx_tone === "red" ? " · hand off" : s.ctx_tone === "yellow" ? " · hand off soon" : "";
  const [yellow, red] = cfg ? cfg.gauge : [150000, 300000];
  let body = "";
  if (s.state !== "stop") {
    body += `<div class="hero"><span class="big">${spentText(s)}</span><span class="side"><span class="lbl">Spent, USD</span>
      <b>$${money(s.burn)} / min</b>${s.doing ? `<span class="m mut" title="${esc(s.doing)}">doing: ${esc(s.doing)}</span>` : ""}</span></div>`;
  }
  body += notes(s) + `<div class="blk"><div class="hd"><span class="lbl${ctxWord ? (s.ctx_tone === "red" ? " r" : " y") : ""}">Context · ${s.ctx_tokens == null ? "?" : kTokens(s.ctx_tokens)}${ctxWord}</span>
    <span class="m">1 cell = ${kTokens(red / 30)}</span></div><div class="cells ctx15">${cellsHtml(ctxClasses(s.ctx_tokens))}</div>
    <div class="scale"><span>0</span><span>${kTokens(yellow)} hand off soon</span><span>${kTokens(red)} hand off</span></div></div>`;
  body += pathHtml(s);
  if (s.state !== "stop") body += agentsHtml(s);
  body += `<div class="blk"><div class="hd"><span class="lbl">Activity · last 30 min</span><span class="m">1 cell = 1 min</span></div>
    <div class="cells act30">${activityCells(s.activity)}</div></div>`;
  $("f-body").innerHTML = body;
  if (!s.window && tab === "chat") tab = "steps";
  const tabs = [["steps", "Steps"], ["timeline", "Timeline"]].concat(s.window ? [["chat", "Chat"]] : []);
  if (!$("f-list")) $("f-feed").innerHTML = '<div class="blk"><div id="f-tabs" class="hd"></div><div id="f-list"></div></div>';
  $("f-tabs").innerHTML = `<span class="lbl">${tabs.find(([k]) => k === tab)[1]}</span><span class="seg">${tabs.map(([k, n]) =>
    `<button class="${k === tab ? "on" : ""}" data-tab="${k}">${n}</button>`).join("")}</span>`;
  renderList(s).catch(() => {});
  renderLevers(s).catch(() => {});
}

function renderAsk(s) {
  const sig = s.state === "stop" ? s.id + "|" + s.stop_question : "";
  if (sig === askSig) return;
  askSig = sig;
  if (!sig) { $("f-ask").innerHTML = ""; return; }
  const where = s.window ? "Your answer continues this run."
    : `Your answer runs in a window copy of this chat. The ${s.source} chat stays as it is.`;
  $("f-ask").innerHTML = `<div class="askbox" style="margin:0"><div class="q">${esc(s.stop_question)}</div>
    <textarea class="in" id="answer" rows="3" aria-label="Answer" placeholder="${esc(where)}"></textarea>
    <div class="lr"><button class="btn you" data-act="answer">Send answer</button>
    ${s.window && !s.run_live ? '<button class="btn" data-act="terminal">Open in terminal</button>' : ""}</div>
    <div id="a-msg" class="say"></div></div>`;
}

function timelineHtml(t) {
  if (!t.lanes.some((lane) => lane.spans.length)) return '<div class="mut">Nothing yet.</div>';
  const total = Math.max(1, t.end - t.start), pos = (x) => (x - t.start) / total * 100;
  return t.lanes.map((lane) => `<div class="tl"><span class="nm m">${esc(lane.label)}${lane.verdict ? " " + esc(lane.verdict) : ""}</span>
    <span class="tl-track">${lane.spans.map(([a, b]) => `<i title="${hhmm(a)} · ${ago(b - a)}"
      style="left:${pos(a).toFixed(2)}%;width:${Math.max(0.6, pos(b) - pos(a)).toFixed(2)}%"></i>`).join("")}</span></div>`).join("")
    + `<div class="tl"><span></span><span class="tl-axis"><span>${hhmm(t.start)}</span><span>${ago(t.end - t.start)}</span><span>${hhmm(t.end)}</span></span></div>`;
}

async function renderList(s) {
  let html;
  if (tab === "timeline") {
    const t = await api("/api/timeline?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "timeline") return;
    html = `<div class="heat">${timelineHtml(t)}</div>`;
  } else if (tab === "chat") {
    const chat = await api("/api/chat?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "chat") return;
    html = chat.start_commit ? `<div class="m mut">start ${esc(chat.start_commit.slice(0, 7))} · ${chat.changed == null ? "?" : chat.changed} file(s) changed since</div>` : "";
    html += `<div class="heat">${chat.items.map((i) => `<div class="chat ${i.role}"><span class="who">${esc(i.role)}</span>
      <div class="text">${esc(i.text)}</div></div>`).join("") || '<div class="mut">Nothing yet.</div>'}</div>`;
  } else {
    const steps = await api("/api/steps?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "steps") return;
    html = `<div class="feed m">${steps.slice().reverse().map((st) => `<div${st.denied ? ' class="r"' : ""}>
      <span>${hhmm(st.ts)}</span><span>${esc(st.agent_type)}</span><span>${esc(st.tool)} ${esc(st.what)}</span></div>`).join("")
      || '<div class="mut">No tool calls yet.</div>'}</div>`;
  }
  if ($("f-list")) $("f-list").innerHTML = html;
}

async function renderLevers(s) {
  const sig = [s.id, s.window, s.run_live, s.stop_question, s.state, s.verdict, s.escalated,
               s.handoff_hint, s.forks.length].join("|");
  if (sig === leversSig) return;
  leversSig = sig;
  const lv = s.run_live ? null : await api("/api/levers?session=" + encodeURIComponent(s.id)).catch(() => null);
  if (openId !== s.id || leversSig !== sig || !$("f-levers")) return;
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
  $("f-levers").innerHTML = html;
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
  const msg = name === "answer" || name === "terminal" && $("a-msg") ? $("a-msg") : $("f-msg");
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
    leversSig = askSig = "";  // redraw from the next snapshot
  } catch (e) {
    button.disabled = false;
    if (msg) msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

// -- events ------------------------------------------------------------------------------
async function go(name, button) {
  if (name === "overview") { if (form === "pill") await setForm("open"); showPane("overview"); }
  if (name === "new") { if (form === "pill") await setForm("open"); showPane("overview"); $("c-prompt").focus(); }
  if (name === "fold") await setForm("pill");
  if (name === "unfold") await setForm("open");
  if (name === "allow") allowRuns(button);
  if (!native()) return;
  if (name === "minimize") window.pywebview.api.minimize();
  if (name === "close") window.pywebview.api.close();
  if (name === "ontop") { onTop = await window.pywebview.api.on_top(!onTop); renderOnTop(); }
}

document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-go],[data-open],[data-tab],[data-act],[data-pact],[data-peek]");
  if (!t) return;
  if (t.dataset.go) go(t.dataset.go, t);
  else if (t.dataset.open) { const id = t.dataset.open; if (form === "pill") setForm("open"); openSession(id); }
  else if (t.dataset.tab) { tab = t.dataset.tab; render(); }
  else if (t.dataset.act) act(t.dataset.act, t);
  else if (t.dataset.pact) prepAct(t.dataset.pact);
  else if (t.dataset.peek) peekAct(t.dataset.peek, t);
});

document.addEventListener("dblclick", (e) => { if (e.target.closest(".pill .sp")) setForm("open"); });

document.addEventListener("input", (e) => {
  if (e.target.id === "c-prompt") { draft = e.target.value; note = ""; saveDraft(); }
});

document.addEventListener("change", (e) => {
  if (e.target.id === "c-project") { project = e.target.value; note = ""; renderCompose(); saveDraft(); }
});

document.addEventListener("keydown", (e) => {
  const id = e.target.id;
  if (id === "c-prompt" && e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    const text = e.target.value.trim();
    if (e.ctrlKey) { if (text && runnable()) doRun(project, text, cfg.default_model, cfg.default_effort, ""); }
    else doPrep();
    return;
  }
  if (id === "fu" && e.key === "Enter") return act("continue", document.querySelector('[data-act="continue"]'));
  if (id === "pk" && e.key === "Enter") return peekAct("send", document.querySelector('[data-peek="send"]'));
  if (e.ctrlKey && e.key.toLowerCase() === "n") { e.preventDefault(); go("new"); return; }
  if (e.key !== "Escape") return;
  if (form === "pill") dismissPeek();
  else if (pane === "prep") prepAct("cancel");
  else if (pane === "focus") showPane("overview");
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
  es.onerror = () => { live = false; if (snap) renderRail(); };
}

(async () => {
  try { cfg = await api("/api/config"); } catch (e) { cfg = null; }
  try { draft = (await api("/api/draft")).text; } catch (e) { /* no draft */ }
  project = (cfg && cfg.project) || "";
  showPane("overview");
  connect();
})();
```

- [ ] **Step 4: Run all tests**

```bash
py -m unittest discover -s tests
```

Expected: `Ran 95 tests` ... `OK` (`test_static_and_ping` checks the new files hold no `https://`).

- [ ] **Step 5: Browser check with the fake claude at 420 px** (no real model calls, no real data)

Save as `$TEMP/cc-smoke6.py`:

```python
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from console import events, paths, server

smoke = sys.argv[1]
proj, home, tdir = (os.path.join(smoke, n) for n in ("proj", "home", "transcripts"))
for folder in (proj, tdir):
    os.makedirs(folder, exist_ok=True)
subprocess.run(["git", "init", "-q", proj])
now = time.time()


def transcript(sid, msgs, agent=""):
    """msgs: (seconds ago, model, input tokens, output tokens) -> one usage line each."""
    path = os.path.join(tdir, f"{sid}.jsonl")
    if agent:
        path = os.path.join(tdir, sid, "subagents", f"agent-{agent}.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for k, (back, model, inp, out) in enumerate(msgs):
            stamp = datetime.fromtimestamp(now - back, timezone.utc).isoformat()
            fh.write(json.dumps({"type": "assistant", "timestamp": stamp, "message": {
                "id": f"{sid}{agent}-{k}", "model": model,
                "usage": {"input_tokens": inp, "output_tokens": out}}}) + "\n")
    return os.path.join(tdir, f"{sid}.jsonl")


OPUS, SONNET, HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"
files = {
    "redesign": transcript("redesign", [(b, OPUS, 60000, 2000) for b in range(400, 0, -40)]),
    "updater": transcript("updater", [(b, SONNET, 50000, 1500) for b in range(1700, 900, -60)]),
    "search": transcript("search", [(b, SONNET, 30000, 800) for b in range(300, 120, -30)]),
    "batch": transcript("batch", [(b, OPUS, 90000, 3000) for b in range(1750, 0, -70)]),
    "levers": transcript("levers", [(b, SONNET, 20000, 500) for b in range(1300, 1000, -50)]),
    "done": transcript("done", [(b, HAIKU, 20000, 500) for b in range(3000, 2500, -100)]),
}
transcript("redesign", [(b, HAIKU, 40000, 1000) for b in range(350, 200, -30)], agent="a1")
transcript("redesign", [(b, SONNET, 40000, 1000) for b in range(150, 0, -20)], agent="a2")

projects = {"redesign": "CLAUDE CONSOLE", "updater": "CONTENT MANAGER", "search": "BRAINAMP",
            "batch": "fashion_packshots_ai", "levers": "CLAUDE CONSOLE", "done": "CONTENT MANAGER"}
lines = [
    ("redesign", -420, "UserPromptSubmit", {"prompt": "Redesign proposal for the window"}),
    ("redesign", -380, "SubagentStart", {"agent_id": "a1", "agent_type": "Explore"}),
    ("redesign", -190, "SubagentStop", {"agent_id": "a1", "agent_type": "Explore", "model": HAIKU, "context_tokens": 38000}),
    ("redesign", -160, "SubagentStart", {"agent_id": "a2", "agent_type": "general-purpose"}),
    ("updater", -1800, "UserPromptSubmit", {"prompt": "Fix updater retry on 429"}),
    ("updater", -840, "Stop", {"model": SONNET, "effort": "medium", "entrypoint": "claude-vscode", "context_tokens": 182000,
                               "stop_question": "Keep the old cache key, or migrate entries to the v2 key?"}),
    ("search", -320, "UserPromptSubmit", {"prompt": "Add transcript search endpoint"}),
    ("search", -180, "PermissionDenied", {"tool": "Bash", "what": "git push origin main", "reason": "[Push] auto mode"}),
    ("batch", -1790, "UserPromptSubmit", {"prompt": "Batch prepare launch split"}),
    ("batch", -1600, "Stop", {"model": OPUS, "effort": "high", "entrypoint": "claude-vscode", "context_tokens": 312000}),
    ("batch", -1590, "UserPromptSubmit", {"prompt": "continue with the split"}),
    ("levers", -1400, "UserPromptSubmit", {"prompt": "Phase 3 levers live check"}),
    ("levers", -1000, "Stop", {"model": SONNET, "effort": "medium", "entrypoint": "claude-vscode", "context_tokens": 71000}),
    ("done", -3100, "UserPromptSubmit", {"prompt": "Tune the strip"}),
    ("done", -2500, "Stop", {"model": HAIKU, "entrypoint": "claude-vscode", "context_tokens": 30000, "verdict": "PASS"}),
    ("done", -2400, "SessionEnd", {"reason": "other"}),
]
for sid in files:
    lines.append((sid, -3200 if sid == "done" else -1850, "SessionStart", {"transcript_path": files[sid]}))
for k in range(36):
    lines.append(("redesign", -400 + k * 11, "PreToolUse",
                  {"tool": "Read", "what": f"web/part{k}.js", **({"agent_id": "a2"} if k > 22 else {})}))
for k in range(60):
    lines.append(("batch", -1580 + k * 26, "PreToolUse", {"tool": "Edit", "what": f"split/step{k}.py"}))
for k in range(8):
    lines.append(("updater", -1700 + k * 100, "PreToolUse", {"tool": "Grep", "what": "cache_key src/"}))
for sid, dt, event, extra in sorted(lines, key=lambda x: x[1]):
    name = projects[sid]
    rec = {"project": name, "project_dir": proj if name == "CLAUDE CONSOLE" else "D:/fake/" + name, "cwd": proj,
           "session_id": sid, "ts": now + dt, "event": event}
    if sid == "redesign":
        rec["effort"] = "high"
    events.append(home, dict(rec, **extra))
cfg = dict(paths.DEFAULTS, projects=[proj])
httpd, hub = server.make_server(cfg, port=8776, folder=home,
                                exe=[sys.executable, os.path.abspath("tests/fake_claude.py")])
hub.user_home = smoke
hub.start()
print("http://127.0.0.1:8776/", flush=True)
httpd.serve_forever()
```

In Git Bash from the repo root:

```bash
rm -rf "$TEMP/cc-smoke6" && PYTHONPATH=. py "$TEMP/cc-smoke6.py" "$TEMP/cc-smoke6"
```

Open `http://127.0.0.1:8776/` in a browser view 420 x 640 (DevTools device toolbar, or an `<iframe>` of that size) and check, in order:
1. **Overview:** crumb `All projects · today`; the Doto figure about `16.34` with `$0.xx / min now` and `soft limit $15`; about 33 hatched spend cells with the orange outline on cell 24; `exact $0.00 · estimated $16.34 · 80 % of limit · 1 cell = $0.50`; `opus 81 % sonnet 18 % haiku <1 %`; five activity rows (`? Fix upda...` and `■ Add tran...` coloured, `~10.50` on the batch row); `Needs you · 3` (Asks you, Blocked, the batch row with `context 312K: hand off`); `Done today · 1` (`Tune the strip`, `PASS`); footer `done today 1 · 1 PASS`. Rail chips `CM`, `BRAIN`, `FPA`, `CC`, `CC` (the first three with a needs-you square), total `16.34 today`.
2. **Focus:** click the `Redesign proposal for the window` row: crumb `CLAUDE CONSOLE / high`; `~3.54` with `doing: Read web/part22.js`; the notes `⇢ delegate 23 reads ...`, `route unrouted · high`; context `?`; path `Run` in ink; agents `main 23 2.80`, `Explore ✓ 0 0.02`, `general-p... 13 0.72` (its last cell blinks); activity cells; the seg `Steps | Timeline`, Steps newest first; the bar `Levers off: still working: wait until it stops`.
3. **Asks you:** click the `CM` chip: `? ASKS YOU · WAITING 1xM`, the question in an orange box with a textarea (`Your answer runs in a window copy of this chat. The vscode chat stays as it is.`), `Context · 182K · hand off soon` in orange with 3 orange cells in the second row, no hero, no agents.
4. **Pill and peek:** click `⌃` (fold): the 380 px pill with the five chips and the figure. In a second Git Bash, add a new question:
   ```bash
   PYTHONPATH=. py -c "import sys,time; from console import events; events.append(sys.argv[1], {'ts': time.time(), 'event': 'Stop', 'session_id': 'levers', 'project': 'CLAUDE CONSOLE', 'project_dir': sys.argv[2], 'cwd': sys.argv[2], 'stop_question': 'Run the live check now, or wait for Fred?', 'model': 'claude-sonnet-5-5', 'entrypoint': 'claude-vscode', 'context_tokens': 72000})" "$TEMP/cc-smoke6/home" "$TEMP/cc-smoke6/proj"
   ```
   Within 2 s a card opens under the pill: `? ASKS YOU Phase 3 levers live check`, the question, an input and `Send answer`. Type `run it now`, Send: the card closes; `⌄` opens the window: a new `○ ↳ Phase 3 levers live check` chip (`PROJ`) is a window copy with `0.01` on its activity row.
5. **Prep and a run:** Overview, the compose select reads `proj`; type `fix add() in calc.py`, Enter: the loading cells (only a flash with the fake claude), then the pane `Prep / proj` (You typed, Scouted `calc.py:2`, the enhanced prompt, Route `sonnet` `low` `mechanical`, `Prep $0.030 · 5 turns`) with Run / Run raw / Edit / Cancel. Run: the focus pane opens on `Chat` (`you ...`, `claude echo: ...`), crumb `proj / window / sonnet low`, the bar `Continue`, `Verify`, `Terminal` and `Hand off is off: the session-handoff skill is not installed here: ...`.
6. **Stop:** follow-up `SLOW please`, Continue: the bar shows `Stop`; click it: `Stop run? Click again`; click again: the head turns `○ IDLE`. Timeline shows two lanes; Verify starts a run (Chat).
7. **Offline:** stop the server (Ctrl+C): the red `OFFLINE` banner shows above the crumb.
8. No errors in the browser console (start the server again and reload once to check the page load too).
9. Stop the server and delete the files: `rm -rf "$TEMP/cc-smoke6" "$TEMP/cc-smoke6.py"`.

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/style.css web/app.js
git commit -m "feat: Console Cells window: pill and peek card, session rail, Overview, focus pane, Prep card"
```

**DONE WHEN**
- [ ] The 8 browser checks pass; 95 tests OK; `git status --short` empty.

---

### Task 7: Fred: live check in the real window

Claude cannot see Fred's screen or VS Code chats. Close the running window first (it still runs the phase 4 code), then start it with `run.bat`.

- [ ] **Step 1: The two forms**
1. The window opens borderless, 400 x 640, rounded corners, no title bar, on top. Drag it by `⋯`, the empty rail space under `＋`, or the crumb. `⊤` turns always-on-top off and on (title `Always on top (off)`), `–` minimizes, `✕` closes it (a running window run keeps going).
2. `⌃` folds it to the 380 x 48 pill at the same top-left corner; drag it by `⋮⋮` or the empty pill space; a double-click there or `⌄` opens it again.
3. Fold, move the pill, close it with `✕` after opening, start `run.bat` again: it comes back open at the same place; fold and restart from the pill form (close the pill by opening it first): it starts as the pill. `~/.claude/console/window.json` holds `form`, `x`, `y`, `on_top`, `project`.
- [ ] **Step 2: Costs**
1. A VS Code chat started (or prompted again) after Task 1 shows `~<cost>` in its focus pane and on its Overview row; the agents' costs add up to at most the session's.
2. A window run: while it runs, `~<estimate>`; when it ends, the exact figure (no `~`) within about 10 % of the estimate.
3. Overview: the hatched cells follow the estimates, the solid ones the finished window runs; the model shares match the day's models.
- [ ] **Step 3: Peek card on a real event.** Fold the window. In a VS Code chat: `End your reply with one line: STOP: <a yes or no question for me>`. Expected: when that turn ends, the pill grows down with one card (the question, an input, `Send answer`); `Send answer` with `yes` runs a window copy and the card closes, the pill shrinks back to 48 px; Esc on a card closes it too.
- [ ] **Step 4: Light theme.** Windows Settings > Personalization > Colours > Light: the window turns light (off-white panes, dark ink, orange only on needs-you), everything readable; back to Dark.
- [ ] **Step 5:** `~/.claude/console/hook-errors.log` and `window-errors.log` have no new lines.

**DONE WHEN**
- [ ] Steps 1-5 pass; anything that differed is noted in History / Troubleshooting.

---

### Task 8: Close the phase

- [ ] **Step 1:** In `../PLAN.md`, set sub-plan 6 to "done <date>" and add a dated History line (what was built, test count, anything that differed).
- [ ] **Step 2:** In `../BRAINSTORM.md` 7.4, replace "Replaced by 7.5 once the rework sub-plan is done." with "Replaced by 7.5 (phase 6, <date>)."; in 7.5, replace "Open check: resizing a frameless pywebview window from code on Windows (pill to open window)." with "Resizing the frameless window from code works (plan 06, fixed decision 14)."
- [ ] **Step 3:** In this file, tick the TODO list, add the History line, add any bug + fix to Troubleshooting.
- [ ] **Step 4:** In `../CLAUDE.md`, replace the rule line starting `- All styling is in web/style.css, tokens first.` with `- All styling is in web/style.css, tokens first. The window follows Console Cells (BRAINSTORM 7.5, plans/06-rework.md); design/rework/ holds the references.`
- [ ] **Step 5:** Commit: `git add PLAN.md BRAINSTORM.md CLAUDE.md plans/06-rework.md && git commit -m "docs: phase 6 done"`.

**DONE WHEN**
- [ ] `git status --short` is empty and `git log --oneline` shows one commit per task.

---

## DONE WHEN (whole plan)

- [ ] `py -m unittest discover -s tests` -> 95 tests OK.
- [ ] The window is borderless with the pill and the open form, remembered across restarts.
- [ ] Context, spend, activity and agents are shown in cells; estimated cost is hatched and marked `~`, exact cost solid.
- [ ] A new question, denial, failure or interruption opens one peek card under the pill; answering in place works.
- [ ] The Prep card, levers, Steps / Timeline / Chat and the compose project work as in phases 2-4.
- [ ] The page makes no network calls; nothing outside `~/.claude/console/`, this repo and the run's own project folder was written by the code or by Claude.

## History

- 2026-10-10 - Plan written. Fred decided: the service reads the transcripts for the estimated cost (hook adds `transcript_path`), API list prices in `config.json`, `daily_budget_usd` 15 with a growing $0.50 grid, activity levels 1-2 / 3-5 / 6-9 / 10+ steps per minute, rail = needs + working (Done in the Overview), the Prep card takes the pane, a Steps | Timeline | Chat seg control, a project select in the compose row, one notes block plus the same lever bar, model shares of today's spend, the window remembers its form and place, a peek card only for new events. All code was run in a scratch clone first: 95 tests OK; the frameless resize checked on this machine (open check closed: 380 x 48, 380 x 200, 400 x 640 exactly; a second start came back as the pill at the saved place); the estimate checked on this project's real transcripts (19 files, 0.05 s); the plan was then replayed in a fresh clone (each task's new tests fail as written, then pass: 88, 91, 92, 93, 95, 95; every file equal to the scratch code; both downloads matched their SHA-256), and the fresh clone was checked in a browser at 420 px with the fake claude (Overview, focus, asks-you pane, pill and a peek card from a new event answered in place, Prep, Run, two-click Stop, Timeline, Verify, offline banner; no console errors from the page).
- 2026-10-10 - Tasks 1-6 placed as written, one commit each (88, 91, 92, 93, 95, 95 tests OK; every find block matched, both Doto SHA-256 values matched). Task 6 browser check at 420 x 640 (an iframe of that size, fake claude, scratch data in `$TEMP`, files deleted after): checks 1-8 passed. Differed: the Timeline in check 6 shows one lane (`main`) with two bars (three after Verify), not "two lanes" (the fake claude runs no agents); the burn figure read `$0.94 / min now` (the plan says `$0.xx`); the page console showed only warnings from a Chrome extension, none from the page. The window itself (Task 7) was not started. Task 7 is Fred's.

## Troubleshooting

- **Issue:** a session shows `–` for its cost.
  **Cause:** no hook line has named its transcript yet (a chat opened before Task 1, until its next prompt), or a window run whose first hook line has not arrived.
  **Fix:** none needed: the next prompt (or the first tool step of the run) brings the path.
- **Issue:** the estimate differs from the bill.
  **Cause:** list prices (`config.json` `"prices"`), no Haiku long-prompt tier, no batch or priority pricing; on a subscription it is an equivalent cost.
  **Fix:** edit `"prices"` in `~/.claude/console/config.json` (each model's five numbers, USD per million tokens) and restart the window.
- **Issue:** the window starts off screen or at an odd place.
  **Cause:** `window.json` holds a place from another monitor layout that a monitor still covers.
  **Fix:** delete `x` and `y` from `~/.claude/console/window.json` (or the whole file) and restart.
- **Issue:** a chip is missing from the rail.
  **Cause:** about 6 chips fit in 640 px; the rest scroll (wheel over the rail).
  **Fix:** none needed; Done sessions are in the Overview, not the rail.
