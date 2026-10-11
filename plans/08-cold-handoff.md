# Plan 08: Cold-cache guard and seeded briefs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Related plans: [../PLAN.md](../PLAN.md) (master), [03-levers.md](03-levers.md) (the levers this guards), [07-cells-drawer.md](07-cells-drawer.md) (the session page and composer this extends)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md); [../CLAUDE.md](../CLAUDE.md)

**Goal:** A session that has been idle for hours with a large context must not be re-read by accident. Continue, Verify, Hand off, Escalate, Resume and a typed answer all replay the whole transcript as input; after the cache has expired that is billed at the cache-write price (a 444K chat on sonnet: about $1.11, on opus about $2.2). The session page now says so and asks for a second click. And it offers the free way out: **Brief a new task** pre-fills the new-task box with the facts of the old session (goal, last message, edited files, last verdict, git status), built locally with no model call, and **Verify in a new task** does the same with the Verify text, so a fresh chat of a few thousand tokens can check the repo.

**Architecture:** `transcript.first_prompt` reads the first prompt from the head of the transcript; `claude_cli.git_status` lists the folder's changes; the new `console/brief.py` is one pure function that formats the brief. `server.Hub.cold` decides "cold and large" and `Hub.levers` returns it as `cold`; `Handler._lever` refuses a lever on a cold session unless the body says `confirm: true` (so the guard also holds for a stale page and for the list cards). `GET /api/brief?session=&kind=task|verify` returns the text. The page arms the lever buttons (first click shows the cost, second click sends `confirm`) and gets two buttons. No new daemon, no model call, nothing is written.

**Tech Stack:** unchanged: Python 3.14 standard library, plain HTML/CSS/JS, `unittest`.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `master`). Run commands from the repo root in Git Bash. Start: 99 tests OK. Other chats edit `web/app.js` and `web/style.css` in parallel: apply Task 4 as anchored edits (find the old text, replace it), never as a whole-file copy, and stage only this plan's lines.

---

## Fixed decisions (Fred, 2026-10-11)

1. **Warn and confirm** (not disable, not note-only): on a cold large session the lever buttons stay; the first click turns the button into `Re-read ~$1.11? Click again` for 4 s, the second click runs. The service enforces it too (`confirm` must be `true`), so a card or peek-card answer on a cold session gets a 409 that says to open the session.
2. **Cold and large** = idle for `cold_after_s` (3600, new config key: it covers the 5 minute and the 1 hour cache lifetimes) **and** `ctx_tokens >= gauge_yellow_tokens` (150K). Below that the replay is cheap and nothing changes.
3. **Brief = facts only**: the first prompt of the old chat (transcript, masked, 1200 chars), the last Claude message (1200 chars), the files its Edit / Write / MultiEdit / NotebookEdit steps touched (20), the last verdict, `git status --short` of the folder (20 lines), and `Read PLAN.md first.` when the folder has a `PLAN.md`. Not the last six turns. It only pre-fills the composer: Fred edits it and presses Enter (Prep) or Ctrl+Enter (Run raw) as for any new task. A session with no transcript falls back to its title.
4. **Verify in a new task** (cold sessions only): `VERIFY_TEXT` plus a line that the earlier chat is not available, plus the same facts (no `PLAN.md` line). The verifier agent works from the repo, not from the old context.
5. **Estimated cost** = `ctx_tokens x prices[model].cache_write_5m / 1e6`, the cheaper of the two write tiers, so it is a floor. Model = the route's alias, sonnet when unknown. It is an estimate in the same sense as the transcript-based spend.
6. **Rules kept:** `server.Hub.levers` alone decides (the new `cold` key lives there); a VS Code or terminal chat is still only forked; nothing is written and no model is called by the brief; no emojis or em-dashes.
7. **Verified:** the Python tasks in a scratch clone of this repo (110 tests OK) and the page in a real browser against a seeded service (a 9 hour idle 444K chat and a 36 minute idle 200K chat, the fake path through `/api/levers` and `/api/brief`): the cold line and the two buttons show, the first click on Verify arms (`Re-read ~$1.11? Click again`), the second sends `{"session":"cold1","confirm":true}`, the label resets after 4 s, Brief fills the composer and scopes the list to the project, the warm chat has no `cold`. **Not verified by Claude:** the real pywebview window and a real cold session on Fred's machine (Task 5).

## Code map

```text
console/
  transcript.py     + HEAD_BYTES, first_prompt
  claude_cli.py     + git_status
  brief.py          NEW  build(kind, goal, last, files, verdict, detail, status, plan) -> text
  paths.py          + "cold_after_s": 3600
  server.py         + Hub.cold, "cold" in Hub.levers, ctx_tokens + last_ts in Hub.session, Hub.steps(limit),
                      confirm check in _lever, GET /api/brief
web/
  app.js            GUARDED, cold, armed second click + confirm, Brief a new task, Verify in a new task, cold line
tests/
  test_transcript.py + 2   test_brief.py NEW 4   test_claude_cli.py + 1   test_server.py + 4
```

Dependencies: `server -> brief -> levers, redact`; `server -> transcript, claude_cli`.

## Files to modify

`console/transcript.py`, `console/claude_cli.py`, `console/paths.py`, `console/server.py`, `web/app.js`, `tests/test_transcript.py`, `tests/test_claude_cli.py`, `tests/test_server.py`, `PLAN.md`. New: `console/brief.py`, `tests/test_brief.py`. Unchanged: `cc_events.py`, `console/state.py`, `console/levers.py`, `console/runs.py`, `web/style.css`, `web/index.html`.

## TODO

- [x] Task 1: the first prompt of a chat from its transcript
- [x] Task 2: git status and the brief text
- [x] Task 3: service (cold in levers, confirm, /api/brief)
- [x] Task 4: window (armed lever buttons, two brief buttons)
- [ ] Task 5: Fred: live check on a real cold session, close the phase

---

### Task 1: The first prompt of a chat from its transcript

**Files:** modify `tests/test_transcript.py`, `console/transcript.py`

- [ ] **Step 1: In `tests/test_transcript.py`, add before the final `if __name__ == "__main__":`:**

```python
    def test_first_prompt(self):
        self.write(
            user("<system-reminder>rules</system-reminder>") | {"isMeta": True},
            user([{"type": "tool_result", "tool_use_id": "t0", "content": "x"}]),
            user([{"type": "text", "text": "[Request interrupted by user]"}]),
            user("start the cells drawer, key sk-abcdefghijkl1234"),
            user("second prompt"),
        )
        self.assertEqual(transcript.first_prompt(self.path), "start the cells drawer, key ***")
        self.write(claude([{"type": "text", "text": "hi"}]))
        self.assertEqual(transcript.first_prompt(self.path), "")
        self.assertEqual(transcript.first_prompt(Path(self.tmp.name) / "none.jsonl"), "")
        self.assertEqual(transcript.first_prompt(None), "")

    def test_first_prompt_reads_only_the_head(self):
        self.write(user("x" * 3000), user("later"), raw='{"type": "user", "mess')
        old = transcript.HEAD_BYTES
        transcript.HEAD_BYTES = 1000  # the first line is cut: it is skipped, the next ones are not read
        self.addCleanup(setattr, transcript, "HEAD_BYTES", old)
        self.assertEqual(transcript.first_prompt(self.path), "")
```

- [ ] **Step 2:** `py -m unittest tests.test_transcript` fails (`first_prompt` missing).

- [ ] **Step 3: In `console/transcript.py`, after `TAIL_BYTES = ...` add:**

```python
HEAD_BYTES = 256 * 1024  # the first prompt is near the start of the file
```

and append at the end of the file:

```python


def first_prompt(path) -> str:
    """The first thing typed in the chat, in words and masked ("" when none is in the first 256 KB)."""
    path = str(path or "")
    if not path.endswith(".jsonl"):
        return ""
    try:
        with open(path, "rb") as fh:
            data = fh.read(HEAD_BYTES)
    except OSError:
        return ""
    for raw in data.split(b"\n"):
        try:
            rec = json.loads(raw)
        except ValueError:
            continue  # also the line cut at the end of the 256 KB
        if not isinstance(rec, dict) or rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
            continue
        msg = rec.get("message")
        text = _words(msg.get("content") if isinstance(msg, dict) else None)
        if text and not text.startswith("[Request interrupted"):
            return redact.mask(text[:TEXT_MAX])
    return ""
```

- [ ] **Step 4:** `py -m unittest discover -s tests`: 101 tests OK. Commit: `feat: first prompt of a chat from its transcript`.

### Task 2: Git status and the brief text

**Files:** create `tests/test_brief.py`, `console/brief.py`; modify `tests/test_claude_cli.py`, `console/claude_cli.py`

- [ ] **Step 1: Create `tests/test_brief.py` with:**

```python
import unittest

from console import brief, levers


class BriefTest(unittest.TestCase):
    def test_task_brief_lists_the_facts(self):
        text = brief.build("task", goal="Implement the Cells Drawer", last="Step 3 is placed.",
                           files=["web/app.js", "web/style.css"], verdict="FAIL", detail="test_add - 3 != 4",
                           status=[" M web/app.js", "?? notes.md"], plan=True)
        self.assertTrue(text.startswith(brief.TASK_INTRO))
        for part in ("Goal (the first prompt of the earlier chat):\nImplement the Cells Drawer",
                     "Where it stopped (the last message of Claude):\nStep 3 is placed.",
                     "Files the earlier chat edited:\n- web/app.js\n- web/style.css",
                     "Last check: FAIL test_add - 3 != 4",
                     "Git status of the folder now:\n M web/app.js\n?? notes.md",
                     "Read PLAN.md first."):
            self.assertIn(part, text)

    def test_empty_parts_are_left_out(self):
        text = brief.build("task")
        self.assertEqual(text, brief.TASK_INTRO)

    def test_verify_brief_starts_with_the_verify_text(self):
        text = brief.build("verify", goal="g", files=["a.py"], plan=True)
        self.assertTrue(text.startswith(levers.VERIFY_TEXT))
        self.assertIn(brief.VERIFY_INTRO, text)
        self.assertIn("- a.py", text)
        self.assertNotIn("PLAN.md", text)

    def test_long_lists_and_texts_are_cut_and_masked(self):
        text = brief.build("task", goal="g" * 5000, files=[f"f{k}.py" for k in range(30)],
                           status=[f" M token=abc{k}" for k in range(30)])
        self.assertLess(len(text), 3500)
        self.assertIn("- and 10 more", text)
        self.assertIn("... and 10 more", text)
        self.assertIn(" M token=***", text)
        self.assertNotIn("token=abc", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: In `tests/test_claude_cli.py`:** extend the imports to
`import json, os, shutil, subprocess, sys, tempfile, unittest` (one per line, as the file does), add `from pathlib import Path` before `from unittest import mock`, and add before `def test_pid_alive`:

```python
    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_git_status_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(claude_cli.git_status(tmp), [])  # not a repo
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            Path(tmp, "a.txt").write_text("x", encoding="utf-8")
            self.assertEqual(claude_cli.git_status(tmp), ["?? a.txt"])
        self.assertEqual(claude_cli.git_status(os.path.join(tmp, "gone")), [])
```

- [ ] **Step 3:** `py -m unittest tests.test_brief tests.test_claude_cli` fails (no `brief`, no `git_status`).

- [ ] **Step 4: Append to `console/claude_cli.py`:**

```python


def git_status(cwd: str) -> list:
    """`git status --short` lines of `cwd` ([] when it is not a repo or git is missing)."""
    try:
        out = subprocess.run(["git", "status", "--short"], cwd=cwd, capture_output=True, text=True,
                             timeout=10, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return []
    return out.stdout.splitlines() if out.returncode == 0 else []
```

- [ ] **Step 5: Create `console/brief.py` with:**

```python
"""A new-task brief built from the facts of a session, with no model call: what a fresh chat needs to
take over a session whose context is too large to re-read (the cold-cache guard offers it)."""
from . import levers, redact

GOAL_MAX = 1200
LAST_MAX = 1200
FILES_MAX = 20
STATUS_MAX = 20
TASK_INTRO = ("Take over a task from an earlier chat whose context was too large to re-read. Start from "
              "the repo and the facts below, and check anything you rely on.")
VERIFY_INTRO = ("The earlier chat is not available here (its context was too large to re-read). Judge the "
                "files as they are now, from the facts below.")


def build(kind: str, goal: str = "", last: str = "", files: list = (), verdict: str = "", detail: str = "",
          status: list = (), plan: bool = False) -> str:
    """`kind` is "task" (hand the work over) or "verify" (VERIFY_TEXT plus the facts)."""
    out = [levers.VERIFY_TEXT + " " + VERIFY_INTRO if kind == "verify" else TASK_INTRO]
    if goal:
        out += ["", "Goal (the first prompt of the earlier chat):", redact.clip(goal, GOAL_MAX)]
    if last:
        out += ["", "Where it stopped (the last message of Claude):", redact.clip(last, LAST_MAX)]
    if files:
        shown = list(files)[:FILES_MAX]
        more = len(files) - len(shown)
        out += ["", "Files the earlier chat edited:"] + [f"- {f}" for f in shown]
        if more > 0:
            out.append(f"- and {more} more")
    if verdict:
        out += ["", "Last check: " + redact.clip(f"{verdict} {detail}".strip(), 200)]
    if status:
        shown = [redact.mask(line) for line in list(status)[:STATUS_MAX]]
        more = len(status) - len(shown)
        out += ["", "Git status of the folder now:"] + shown
        if more > 0:
            out.append(f"... and {more} more")
    if plan and kind != "verify":
        out += ["", "Read PLAN.md first."]
    return "\n".join(out)
```

- [ ] **Step 6:** `py -m unittest discover -s tests`: 106 tests OK. Commit: `feat: git status and the seeded brief text`.

### Task 3: Service (cold in levers, confirm, /api/brief)

**Files:** modify `tests/test_server.py`, `console/paths.py`, `console/server.py`

- [ ] **Step 1: In `tests/test_server.py`, class `RunServerTest`, add before `def test_verify_then_escalate_once(self):`:**

```python
    def idle_chat(self, sid, hours, tokens, transcript=None):
        """A VS Code chat whose last event was `hours` ago, holding `tokens` of context."""
        ts = time.time() - hours * 3600
        base = {"session_id": sid, "project": "proj", "project_dir": str(self.project), "cwd": str(self.project)}
        first = dict(base, event="UserPromptSubmit", ts=ts, prompt="fix add")
        if transcript:
            first["transcript_path"] = str(transcript)
        events.append(self.folder, first)
        events.append(self.folder, dict(base, event="PreToolUse", ts=ts + 1, tool="Edit", what="calc.py"))
        events.append(self.folder, dict(base, event="PreToolUse", ts=ts + 2, tool="Edit", what="calc.py"))
        events.append(self.folder, dict(base, event="PreToolUse", ts=ts + 3, tool="Read", what="notes.md"))
        events.append(self.folder, dict(base, event="Stop", ts=ts + 4, model="claude-sonnet-5-5",
                                        effort="medium", context_tokens=tokens))
        self.hub.poll_once()

    def test_a_cold_large_chat_needs_a_confirm_before_a_lever_re_reads_it(self):
        self.idle_chat("c1", hours=9, tokens=444000)
        lv = self.call("/api/levers?session=c1")[1]
        self.assertEqual(lv["cold"], {"idle_s": lv["cold"]["idle_s"], "tokens": 444000, "cost": 1.11})  # sonnet 2.5 / M
        self.assertTrue(9 * 3600 - 60 < lv["cold"]["idle_s"] < 9 * 3600 + 60)
        for lever, body in (("continue", {"text": "go"}), ("verify", {})):
            status, data = self.call(f"/api/{lever}", dict(body, session="c1"))
            self.assertEqual(status, 409, lever)
            self.assertTrue(data["error"].startswith("cold cache: 444K tokens, idle 9 h, would be re-read at full "
                                                     "price (about $1.11)"), data)
        self.assertEqual(self.call("/api/continue", {"session": "c1", "text": "go", "confirm": "yes"})[0], 409)
        self.assertEqual([s["id"] for s in self.hub.snapshot()["sessions"]], ["c1"])  # nothing started
        status, data = self.call("/api/continue", {"session": "c1", "text": "go", "confirm": True})
        self.assertEqual(status, 200)
        self.assertNotEqual(data["session"], "c1")
        self.wait_idle(data["session"])

    def test_no_cold_guard_for_a_recent_or_a_small_chat(self):
        self.idle_chat("r1", hours=0.5, tokens=444000)  # the cache may still be warm
        self.idle_chat("s1", hours=9, tokens=100000)  # cheap to re-read
        self.assertIsNone(self.call("/api/levers?session=r1")[1]["cold"])
        self.assertIsNone(self.call("/api/levers?session=s1")[1]["cold"])
        status, data = self.call("/api/continue", {"session": "s1", "text": "go"})
        self.assertEqual(status, 200)
        self.wait_idle(data["session"])

    def test_brief_of_a_session_from_its_transcript_and_steps(self):
        transcript = Path(self.tmp.name) / "c2.jsonl"
        transcript.write_text("".join(json.dumps(rec) + "\n" for rec in (
            {"type": "user", "timestamp": "2026-10-10T10:00:00Z",
             "message": {"role": "user", "content": "Implement the Cells Drawer window"}},
            {"type": "assistant", "timestamp": "2026-10-10T10:00:05Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "Step 3 is placed."}]}},
            {"type": "user", "timestamp": "2026-10-10T10:01:00Z",
             "message": {"role": "user", "content": "continue"}})), encoding="utf-8")
        (self.project / "PLAN.md").write_text("# plan", encoding="utf-8")
        self.idle_chat("c2", hours=9, tokens=444000, transcript=transcript)
        status, data = self.call("/api/brief?session=c2")
        self.assertEqual((status, data["project_dir"]), (200, self.hub.session("c2")["project_dir"]))
        for part in ("Goal (the first prompt of the earlier chat):\nImplement the Cells Drawer window",
                     "Where it stopped (the last message of Claude):\nStep 3 is placed.",
                     "Files the earlier chat edited:\n- calc.py\n\n", "Read PLAN.md first."):
            self.assertIn(part, data["text"])
        self.assertNotIn("notes.md", data["text"])  # a Read is not an edit
        verify = self.call("/api/brief?session=c2&kind=verify")[1]["text"]
        self.assertTrue(verify.startswith("Check the work of this session."))
        self.assertNotIn("PLAN.md", verify)
        self.assertEqual(self.call("/api/brief?session=nope")[0], 404)
        self.assertEqual(self.call("/api/brief?session=c2&kind=other")[0], 404)

    def test_brief_without_a_transcript_falls_back_to_the_title(self):
        self.idle_chat("c3", hours=9, tokens=444000)
        text = self.call("/api/brief?session=c3")[1]["text"]
        self.assertIn("Goal (the first prompt of the earlier chat):\nfix add", text)
        self.assertNotIn("Where it stopped", text)
```

- [ ] **Step 2:** `py -m unittest tests.test_server` fails (no `cold`, no `/api/brief`).

- [ ] **Step 3: `console/paths.py`:** in `DEFAULTS`, after `"daily_budget_usd": 15,` add

```python
    "cold_after_s": 3600,  # idle this long: both prompt-cache lifetimes (5 min, 1 h) are gone
```

- [ ] **Step 4: `console/server.py`**, six edits:

(a) the imports become

```python
from . import brief, claude_cli, events, guard, levers, paths, prep, runs, transcript, usage
from .state import MAX_STEPS, WRITE_TOOLS, State, norm_dir
```

(b) `Hub.steps` takes a limit:

```python
    def steps(self, session_id: str, limit: int = 200) -> list:
        with self.lock:
            return self.state.steps(session_id, limit)
```

(c) `Hub.session`: the last entry of the returned dict becomes
`"transcript_path": s.transcript_path, "ctx_tokens": s.ctx_tokens, "last_ts": s.last_ts}`

(d) add `Hub.cold` between `route_of` and `levers`, and add the `cold` key to the dict `levers` returns:

```python
    def cold(self, s: dict, model: str, now: float = None):
        """What a lever would re-read at full price: {idle_s, tokens, cost}, or None. The chat has been
        idle past cold_after_s (both cache lifetimes are gone) and holds gauge_yellow_tokens or more;
        cost = tokens x the 5-minute cache-write price of the route's model (the cheaper of the two)."""
        tokens, idle = s["ctx_tokens"], (now or time.time()) - s["last_ts"]
        if not tokens or tokens < self.cfg["gauge_yellow_tokens"] or idle < self.cfg["cold_after_s"]:
            return None
        price = self.cfg["prices"].get(model) or self.cfg["prices"]["sonnet"]
        return {"idle_s": int(idle), "tokens": tokens, "cost": round(tokens * price["cache_write_5m"] / 1e6, 2)}
```

and the last line of `levers` becomes

```python
                "fork": not window, "cwd": cwd or "", "cold": None if base else self.cold(s, model)}
```

(e) `do_GET`: after the `/api/chat` branch add

```python
        if url.path == "/api/brief":
            return self._brief(query.get("session", [""])[0], query.get("kind", ["task"])[0])
```

(f) `_lever`: after `if info[lever]: return self._error(409, info[lever])` add

```python
        if info["cold"] and body.get("confirm") is not True:  # the page asks with a second click
            c = info["cold"]
            return self._error(409, f"cold cache: {c['tokens'] // 1000}K tokens, idle {c['idle_s'] / 3600:.0f} h, "
                                    f"would be re-read at full price (about ${c['cost']:.2f}); open the session to "
                                    "confirm, or start a new task there with a brief")
```

and add `_brief` before `_stream`:

```python
    def _brief(self, sid: str, kind: str):
        """The text of a new task that takes over a session, built from its transcript, its steps and the
        folder's git status: no model call, nothing written."""
        s = self.hub.session(sid)
        if s is None or kind not in ("task", "verify"):
            return self._error(404, "unknown session")
        turns = transcript.turns(s["transcript_path"])
        files = []
        for step in self.hub.steps(sid, MAX_STEPS):
            if step["tool"] in WRITE_TOOLS and step["what"] and step["what"] not in files:
                files.append(step["what"])
        folder = s["project_dir"] if os.path.isdir(s["project_dir"] or "") else s["cwd"]
        text = brief.build(kind, goal=transcript.first_prompt(s["transcript_path"]) or s["title"],
                           last=next((t["text"] for t in reversed(turns) if t["role"] == "claude"), ""),
                           files=files, verdict=s["verdict"], detail=s["verdict_detail"],
                           status=claude_cli.git_status(folder) if os.path.isdir(folder or "") else [],
                           plan=os.path.isfile(os.path.join(folder or "", "PLAN.md")))
        return self._json({"text": text, "project_dir": s["project_dir"]})
```

- [ ] **Step 5:** `py -m unittest discover -s tests`: 110 tests OK (the existing lever tests still pass: their sessions have no `ctx_tokens`, so `cold` is `None`). Commit: `feat: cold-cache guard on the levers and /api/brief`.

### Task 4: Window (armed lever buttons, two brief buttons)

**Files:** modify `web/app.js` (anchored edits; the file is also edited by other chats)

- [ ] **Step 1:** after the line `const esc = ...` block (just before `const RESUME_TEXT =`) add:

```js
const GUARDED = ["continue", "answer", "resume", "verify", "handoff", "escalate"];  // levers that re-read the context
```

- [ ] **Step 2:** after `let leversSig = "";` add:

```js
let cold = null;        // {idle_s, tokens, cost} when a lever would re-read the open session at full price
let coldTimer = null;
```

- [ ] **Step 3: `renderLevers`.** (a) The `sig` list gets a tenth part so the bar redraws when a session turns cold while open, and `cold` is cleared before the fetch:

```js
  const sig = [s.id, s.window, s.run_live, s.stop_question, s.state, s.verdict, s.escalated,
               s.handoff_hint, s.forks.length, Math.floor((snap.now - s.last_ts) / 600)].join("|");  // the last one: idle turns cold
  if (sig === leversSig) return;
  leversSig = sig;
  cold = null;
```

(b) after `if (openId !== s.id || leversSig !== sig) return;` add `  cold = lv && !lv.continue ? lv.cold : null;`

(c) between the Terminal button line and `if (buttons) html += ...` add the two buttons, and after that `if (buttons)` line add the cold note:

```js
  if (lv && s.project_dir) {  // a new task that takes over: built here from the transcript, no model call
    buttons += `<button class="btn${cold ? " go" : ""}" data-act="brief" title="A new task with the goal, the last message, the edited files and the git status of this one">Brief a new task</button>`;
    if (cold) buttons += '<button class="btn" data-act="vbrief" title="The Verify text plus the same facts, in a new task">Verify in a new task</button>';
  }
  if (buttons) html += `<div class="lr">${buttons}</div>`;
  if (cold) html += `<div class="say">Cold cache: ${kTokens(cold.tokens)} tokens, idle ${Math.round(cold.idle_s / 3600)} h. Continue, Verify, Hand off and Escalate re-read them at full price, about $${money(cold.cost)} (a second click confirms). A new task with a brief costs almost nothing.</div>`;
```

- [ ] **Step 4: `act`.** After the `if (name === "stop" && !button.dataset.armed) { ... return; }` block and before `const msg = ...` add:

```js
  const typed = name === "answer" ? $("answer") : name === "continue" ? $("fu") : null;
  if (typed && !typed.value.trim()) return;  // nothing to send: no cost to confirm
  if (cold && GUARDED.includes(name) && !button.dataset.armed) {  // two clicks: a cold cache re-reads the context at full price
    button.dataset.armed = "1";
    button.dataset.label = button.textContent;
    button.textContent = `Re-read ~$${money(cold.cost)}? Click again`;
    clearTimeout(coldTimer);
    coldTimer = setTimeout(() => { delete button.dataset.armed; button.textContent = button.dataset.label; }, 4000);
    return;
  }
  const confirm = Boolean(button.dataset.armed);
```

Inside the `try {` after `let r = null;` add:

```js
    if (name === "brief" || name === "vbrief") {  // pre-fill the new-task box; Fred edits it and runs it
      const b = await api("/api/brief?session=" + encodeURIComponent(s.id) + (name === "vbrief" ? "&kind=verify" : ""));
      pick(b.project_dir);
      showPage("list");
      draft = b.text;
      $("c-prompt").value = draft;
      saveDraft();
      renderCompose();
      $("c-prompt").focus();
      button.disabled = false;
      return;
    }
```

and pass `confirm` in the three lever calls in `act`:
`api("/api/continue", { session: s.id, text: RESUME_TEXT, confirm })`, `api("/api/continue", { session: s.id, text, confirm })`, `api("/api/" + name, { session: s.id, confirm })`.

(`unblock()` for the list and peek cards stays as it is: on a cold session its call gets the 409 text, shown on the card, which says to open the session.)

- [ ] **Step 5:** `node --check web/app.js` and `py -m unittest discover -s tests` (110 OK).

- [ ] **Step 6: Live check in a browser (scratchpad harness).** Seed a home folder with `console.events.append`: a session idle 9 h with `context_tokens` 444000 and an Edit step, one idle 0.6 h with 200000, a transcript file for the first; `config.json` with `port`, `projects` (the folder) and `claude_exe` (any file); run `CC_CONSOLE_HOME=<home> py -m console --serve`; open the page, `openSession("<id>")`. Expect: `Brief a new task` (orange) and `Verify in a new task` next to the levers and the cold line with `$1.11`; Verify once shows `Re-read ~$1.11? Click again` and returns to `Verify` after 4 s; clicking twice posts `{"session":..., "confirm": true}`; Brief opens the list scoped to the project with the brief in the composer; the warm session shows only `Brief a new task` and no cold line.

### Task 5: Fred: live check and close the phase

- [ ] **Step 1:** Restart the window. Open an idle session that has been off for hours with a large context (the gauge is red or yellow). Check: the cold line and the two buttons show; Continue / Verify / Hand off need a second click; `Brief a new task` fills the box with the goal, the last message, the files and the git status; Enter (Prep) or Ctrl+Enter (Run raw) starts a fresh chat from it; `Verify in a new task` runs the verifier against the repo and ends with a `VERDICT:` line.
- [ ] **Step 2:** Compare the estimate with the `~` spend of the first turn of the confirmed lever (the floor should be close to it, a bit under when the 1 hour tier applies).
- [ ] **Step 3:** Mark Tasks 1-5 in the TODO, set the PLAN.md row to `done <date>`, add a History line with the test count and what differed.
