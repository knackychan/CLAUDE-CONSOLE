# Task 5: The service: facts and lessons in the prompt, brief_meta, the task routes, auto handoff, the setting route

> Contract: [README.md](README.md) 3.3 (`touched`), 3.4, 3.5, 3.6, 3.7, 3.8. Decisions D1 (`git_base`), D5 (`touched`).
> Depends on Tasks 1 to 4. Run in the scratch copy against today's `console/server.py` and `console/state.py` (plans 5
> and 24 not placed): the diffs below are what ran. Where plans 5 and 24 changed the same lines first, the **Lands on**
> lines give the final form; every anchor is quoted.

**Files**
- Modify: `console/server.py` (imports; `AUTO_HANDOFF_STATES`; `Hub.__init__` `auto_handed`; `Hub.pull(auto)`;
  `Hub.auto_steps`; `Hub.start_step`; `Hub._ended`; new `Hub._facts`; `Hub.start_brief`; `Hub._brief_job`;
  `Hub._brief_done`; `task_row`; `Handler.do_GET` `/api/config`; `Handler.do_POST` routes; new `Handler._setting`;
  `Handler._task`; new `Handler._step_texts`)
- Modify: `console/state.py` (`Session.auto_handoff`; `run_started`; `marked_done`; the snapshot row and its group)
- Modify: `tests/test_server.py`

## 5.1 `console/server.py`

```diff
diff --git a/console/server.py b/console/server.py
index d8691b0..66916f8 100644
--- a/console/server.py
+++ b/console/server.py
@@ -9,7 +9,7 @@ from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
 from urllib.parse import parse_qs, urlparse
 
-from . import (attach, brief, claude_cli, compact, events, guard, levers, paths, prep, redact, review, routing, runs,
+from . import (attach, brief, claude_cli, compact, events, facts, guard, levers, paths, prep, redact, review, routing, runs,
                tasks, transcript, usage)
 from .state import MAX_STEPS, WRITE_TOOLS, State, norm_dir
 
@@ -28,6 +28,7 @@ MAX_FILES_BODY = attach.MAX_TOTAL * 4 // 3 + MAX_BODY  # /api/prep, /api/run and
 FILE_ROUTES = ("/api/prep", "/api/run", "/api/continue")
 MAX_PROMPT = 20000
 BUSY = {"running", "quiet", "stall"}
+AUTO_HANDOFF_STATES = ("replied", "idle", "verified", "verify_failed")  # plan 23: a turn that ended
 
 
 class Hub:
@@ -55,6 +56,7 @@ class Hub:
         self.storage_at = 0.0
         self.version = 0
         self.auto_since = time.time()  # older verdicts never trigger an automatic step
+        self.auto_handed = set()  # plan 23: sessions handoff_auto handed off once (never twice)
         self._stop = threading.Event()
 
     def poll_once(self) -> int:
@@ -317,7 +319,7 @@ class Hub:
                     out[lever] = base or "a task step: use the task's levers"
         return out
 
-    def pull(self, sid, lever: str, text: str = "", confirm: bool = False, files: list = ()) -> tuple:
+    def pull(self, sid, lever: str, text: str = "", confirm: bool = False, files: list = (), auto: int = 0) -> tuple:
         """Continue (also STOP answers and Resume), Verify, Handoff, Escalate: a new turn of a window
         run, or a window copy (fork) of a VS Code / terminal chat, which stays as it is. De-escalate starts
         no turn: the next one runs on the task's starting route. Returns (status, body); a click and the
@@ -358,6 +360,8 @@ class Hub:
             text = levers.escalate_text(s["verdict_detail"], new_model, new_effort)
             model, effort = new_model, new_effort
             extra = {"escalated": f"{route_from} -> {route_to}"}
+        if auto and lever == "handoff":  # plan 23: auto_steps handed it off at `auto` context tokens
+            extra = dict(extra, auto_handoff=int(auto))
         fork = sid if info["fork"] and not fresh else ""
         with self.tlock:  # Continue in the current step of a stopped task resumes the task there; Hand off in the
             # current step hands the task over (tasks.fred)
@@ -383,13 +387,27 @@ class Hub:
         step itself: Escalate after FAIL, de-escalate after PASS. Only verdicts about the last turn that
         arrived while this service runs, never a VS Code or terminal chat, never past a cold-cache
         confirm, and only what self.levers allows. Returns the (session, lever) pairs it pulled."""
-        now = time.time()
+        now, red, auto = time.time(), self.cfg["gauge_red_tokens"], bool(self.cfg.get("handoff_auto"))
+        hand, due = [], []
         with self.lock:
-            due = [(s.id, "escalate" if st == "verify_failed" else "deescalate")
-                   for s in self.state.sessions.values()
-                   if s.window and not s.task and s.verdict_ts >= self.auto_since  # a step's verdict is its chain's
-                   for st in [self.state.state_of(s, now)] if st in ("verify_failed", "verified")]
+            for s in self.state.sessions.values():
+                if s.task:  # a step's verdict and context are its chain's
+                    continue
+                st = self.state.state_of(s, now)
+                if (auto and (s.ctx_tokens or 0) >= red
+                        and st in AUTO_HANDOFF_STATES and not s.handoff and s.id not in self.auto_handed
+                        and s.turns and (s.turns[-1][1] or 0) >= self.auto_since):
+                    hand.append((s.id, s.ctx_tokens))  # plan 23: a red turn hands off; no route step
+                elif s.window and s.verdict_ts >= self.auto_since and st in ("verify_failed", "verified"):
+                    due.append((s.id, "escalate" if st == "verify_failed" else "deescalate"))
         pulled = []
+        for sid, tokens in hand:  # pull forks a VS Code chat first: it is never resumed in place
+            try:
+                if self.pull(sid, "handoff", auto=tokens)[0] == 200:
+                    self.auto_handed.add(sid)
+                    pulled.append((sid, "handoff"))
+            except (runs.RunError, OSError):
+                continue
         for sid, lever in due:
             try:
                 if self.pull(sid, lever)[0] == 200:
@@ -593,15 +611,22 @@ class Hub:
         model = pick if pick and pick not in claude_cli.MODELS and claude_cli.tier_of(pick) == tier \
             else self.model_id(tier)
         retry = task["why"] if s["retries"] == 1 and s["state"] == "planned" else ""
-        prompt = tasks.step_prompt(task, s, tasks.read_brief(self.folder, task, task["last_good"]), retry)
-        max_turns = self.cfg["opus_max_turns"] if kind == "design" and tier == "opus" else 0
+        last = task["last_good"]
+        lessons = tasks.lessons_for(levers.read_lessons(self.folder, task["project"]), kind)
+        prompt = tasks.step_prompt(task, s, tasks.read_brief(self.folder, task, last), retry,
+                                   facts=tasks.read_facts(self.folder, task, last), lessons=lessons)
+        max_turns = (self.cfg["opus_max_turns"] if kind == "design" and tier == "opus" else
+                     self.cfg["read_max_turns"] if kind in tasks.READ_CAPPED else 0)
+        if "git_base" not in s:  # D1 a: the tree before the first attempt; the facts count the step's own lines
+            head = claude_cli.git_head(task["project_dir"])
+            s["git_base"] = {"commit": head, "files": claude_cli.git_snapshot(task["project_dir"], head)}
         try:
             sid = self.runs.start(
                 task["project_dir"], prompt, model, route["effort"],
                 title=f"{task['title']} · {n}/{len(task['steps'])} {kind}", route=kind,
                 reason=" · ".join(route["notes"]), prep=task["prep"], kind="task",
                 extra={"task": task["id"], "step": n}, disallow=tasks.DISALLOW, tools=tasks.RULES[kind][2],
-                budget=self.cfg["task_step_budget_usd"], max_turns=max_turns)
+                budget=self.cfg["task_step_budget_usd"], max_turns=max_turns, strict_mcp=True)
         except (runs.RunError, OSError) as exc:
             tasks._task_to(task, "stuck", str(exc), now, s, lines)
             return self._commit(task, lines)
@@ -725,6 +750,7 @@ class Hub:
         self.sync_costs(task)
         if action in ("next", "fix", "done"):
             tasks.write_note(self.folder, task, cs, block)
+            self._facts(task, cs, sid)
             lesson = tasks.lesson_of(block)
             if lesson:  # plan 22: one line per step that taught something, read by the rules review
                 levers.add_lesson(self.folder, levers.lesson_line(task["project"], cs["kind"], lesson, now))
@@ -739,6 +765,23 @@ class Hub:
             self._go_on(task)
         return action
 
+    def _facts(self, task: dict, cs: dict, sid: str) -> None:
+        """Plan 23: the step's end commit, its own lines against the tree it started on (D1 a) and its last test
+        command: s["end_commit"], s["facts"] and steps/NN-<kind>.facts.md, never compacted. A git or file error
+        leaves the facts it could read."""
+        cwd, base = task["project_dir"], cs.get("git_base") or {}
+        cs["end_commit"] = claude_cli.git_head(cwd)
+        after = claude_cli.git_snapshot(cwd, base.get("commit", "")) if base.get("files") is not None else None
+        changed = facts.delta(base["files"], after) if after is not None else {}
+        _, lines = runs.read_lines(self.runs.stream_path(sid), 0)
+        test = facts.last_test(lines)
+        cs["facts"] = facts.facts(changed, test)
+        try:
+            tasks.write_facts(self.folder, task, cs, facts.text(base.get("commit", ""), cs["end_commit"], changed,
+                                                                test, git=after is not None))
+        except OSError:
+            pass
+
     def start_brief(self, task: dict, n: int) -> None:
         """The brief between step `n` and the next: Haiku compacts the note in a thread, the code fallback stands
         in when it fails or brief_on is off. task["briefing"] = n until steps/NN-<kind>.brief.md is written."""
@@ -746,6 +789,7 @@ class Hub:
         nxt = tasks.step(task, n + 1) if n < len(task["steps"]) else None
         raw = tasks.read_note(self.folder, task, n)
         prev = tasks.read_brief(self.folder, task, n - 1)
+        touched = [p for k in range(1, n + 1) for p in facts.files_in(tasks.read_facts(self.folder, task, k))]
         task["briefing"] = n
         if not self.cfg["brief_on"]:
             text = compact.fallback(prev, raw)
@@ -754,13 +798,13 @@ class Hub:
             return
         self.briefing.add(task["id"])
         threading.Thread(target=self._brief_job, args=(copy.deepcopy(task), copy.deepcopy(s), copy.deepcopy(nxt),
-                                                       prev, raw), name="cc-brief", daemon=True).start()
+                                                       prev, raw, touched), name="cc-brief", daemon=True).start()
 
-    def _brief_job(self, task: dict, s: dict, nxt, prev: str, raw: str) -> None:
+    def _brief_job(self, task: dict, s: dict, nxt, prev: str, raw: str, touched: list = ()) -> None:
         model = self.cfg["brief_model"]
         cfg = dict(self.cfg, brief_model=self.model_id(model) if model in claude_cli.MODELS else model)
         try:
-            res = compact.run_brief(cfg, self.runs.exe, task, s, nxt, prev, raw)
+            res = compact.run_brief(cfg, self.runs.exe, task, s, nxt, prev, raw, touched)
         except Exception as exc:  # run_brief never raises; if it does, the chain still goes on
             text = compact.fallback(prev, raw)
             res = {"text": text, "cost": 0, "words": len(text.split()), "fallback": f"{type(exc).__name__}: {exc}"}
@@ -776,8 +820,9 @@ class Hub:
             s = tasks.step(task, n)
             why = (f"brief fallback: {res['fallback']}" if res["fallback"] else
                    f"brief: {len(raw.split())} -> {res['words']} words, ${res['cost']:.2f}"
-                   + (f", cut {res['cut']} findings" if res.get("cut") else ""))
+                   + (f", cut {len(res['cut'])} findings" if res.get("cut") else ""))
             task["briefing"] = 0
+            s["brief_meta"] = compact.brief_meta(res, raw)  # plan 23: what step n + 1 received
             try:
                 tasks.write_brief(self.folder, task, s, res["text"])
                 lines = [tasks._line(time.time(), s, "briefing", "briefed", why)]
@@ -910,6 +955,8 @@ def task_row(t: dict, live=lambda sid: "", sessions=None) -> dict:
             "steps": [{**{k: s[k] for k in ("n", "kind", "state", "model", "effort", "session", "verdict", "retries",
                                             "cost")},
                        "note": tasks.note_state(t, s, live(s["session"]) if s["state"] == "running" else ""),
+                       "end_commit": s.get("end_commit", ""), "brief_meta": s.get("brief_meta"),
+                       "facts": s.get("facts"),  # plan 23
                        "attempts": [{"session": a["session"], "cost": a["cost"], "why": a["why"]}
                                     for a in tasks.attempts(s)]} for s in t["steps"]]}
 
@@ -966,7 +1013,8 @@ class Handler(BaseHTTPRequestHandler):
                                "gauge": [cfg["gauge_yellow_tokens"], cfg["gauge_red_tokens"]],
                                "project": window.get("project", ""), "brief": window.get("brief") is True,
                                "ladder": cfg["ladder"], "effort": window.get("effort", "auto"),
-                               "kinds": tasks.PREP_KINDS, "edit_kinds": sorted(tasks.EDIT_KINDS)})
+                               "kinds": tasks.PREP_KINDS, "edit_kinds": sorted(tasks.EDIT_KINDS),
+                               "handoff_auto": bool(cfg["handoff_auto"])})
         if url.path == "/api/usage":
             return self._json(self.hub.usage_report())
         if url.path == "/api/image":
@@ -996,7 +1044,8 @@ class Handler(BaseHTTPRequestHandler):
         routes = {"/api/prep": self._prep, "/api/prep/drop": self._prep_drop, "/api/run": self._run, "/api/stop": self._stop,
                   "/api/terminal": self._terminal, "/api/draft": self._draft, "/api/allow": self._allow,
                   "/api/open_folder": lambda body: self._allow(body, sessions_only=False),
-                  "/api/done": self._done, "/api/task": self._task_new, "/api/review": self._review}
+                  "/api/done": self._done, "/api/task": self._task_new, "/api/review": self._review,
+                  "/api/setting": self._setting}
         for lever in ("continue", "verify", "handoff", "escalate"):
             routes[f"/api/{lever}"] = lambda body, lever=lever: self._lever(body, lever)
         for lever in ("stop", "pause", "resume", "retry", "confirm", "clear", "done"):
@@ -1120,6 +1169,19 @@ class Handler(BaseHTTPRequestHandler):
         self.hub.poll_once()
         return self._json({"session": sid})
 
+    def _setting(self, body):
+        """Plan 23: one whitelisted boolean of config.json (paths.SETTINGS: handoff_auto), written and live at once."""
+        key, value = body.get("key"), body.get("value")
+        try:
+            paths.set_setting(self.hub.folder, key, value)
+        except ValueError as exc:
+            return self._error(400, str(exc))
+        with self.hub.lock:
+            self.hub.cfg[key] = value
+            self.hub.version += 1
+            self.hub.changed.notify_all()
+        return self._json({"key": key, "value": value})
+
     def _lever(self, body, lever):
         files = attach.parse(body.get("files")) if lever == "continue" else []
         code, data = self.hub.pull(body.get("session"), lever, self._text(body, "text") if lever == "continue" else "",
@@ -1252,7 +1314,18 @@ class Handler(BaseHTTPRequestHandler):
                            "step_levers": self.hub.levers(cs["session"]) if cs and cs["session"] else None,
                            "note": tasks.read_note(self.hub.folder, task, last),
                            "brief": tasks.read_brief(self.hub.folder, task, last),
-                           "handoff": tasks.read_handoff(self.hub.folder, task)})
+                           "handoff": tasks.read_handoff(self.hub.folder, task),
+                           **self._step_texts(task)})
+
+    def _step_texts(self, task: dict) -> dict:
+        """Plan 23: every step's raw note, brief and facts, keyed by the step number as a string (absent: none)."""
+        out = {"notes": {}, "briefs": {}, "facts": {}}
+        for st in task["steps"]:
+            for key, read in (("notes", tasks.read_note), ("briefs", tasks.read_brief), ("facts", tasks.read_facts)):
+                text = read(self.hub.folder, task, st["n"])
+                if text:
+                    out[key][str(st["n"])] = text
+        return out
 
     def _stream(self):
         self.send_response(200)
```

What each part does (the diff is the code):

- `start_step`: the previous step's facts go under its brief (`tasks.received` through `step_prompt(facts=)`); the
  lessons of the step's kind (`levers.read_lessons` of the project, then `tasks.lessons_for`); `read_max_turns` on
  `tasks.READ_CAPPED`; `git_base` once, before the first attempt's run (D1 a); `strict_mcp=True`.
- `_ended`: right after `tasks.write_note`, `self._facts(task, cs, sid)` (only when the note is written: `next`,
  `fix`, `done`). `_facts` sets `end_commit`, diffs the snapshot against `git_base`, reads the last test command from
  the run's stream, sets `s["facts"]` and writes the facts file; a git failure leaves `facts.files` 0 and the text's
  `git:` line; an `OSError` on the write is swallowed (the chain goes on).
- `start_brief` reads every facts file of steps 1 to n through `facts.files_in` and passes the list to the thread
  (D5 a); `_brief_job` passes it to `run_brief`; `_brief_done` stores `compact.brief_meta(res, raw)` on the step and
  the chain line says `cut N findings`.
- `task_row` steps: `end_commit`, `brief_meta`, `facts`. `GET /api/task`: `notes`, `briefs`, `facts` through
  `_step_texts`. `/api/config`: `handoff_auto`. `POST /api/setting`: `_setting`.
- `pull(..., auto=0)`: a handoff pulled by `auto_steps` carries `extra["auto_handoff"] = tokens` into `run_started`.
- `auto_steps`: README 3.7. The red check comes first: a red session in the hand-off list takes no route step.

**Lands on** plan 5 Task 5 and plan 24 Task 3 (`Hub.start_step`). After both, the prompt and turn-cap lines read
(plan 24's `special`, `plan_text`, `part_text`, `prev` and plan 5's `adapter` are theirs):

```python
        last = task["last_good"]
        lessons = tasks.lessons_for(levers.read_lessons(self.folder, task["project"]), kind)
        prompt = tasks.step_prompt(task, s, prev, retry, special=special, plan=plan_text, part=part_text,
                                   facts=tasks.read_facts(self.folder, task, last), lessons=lessons)
        max_turns = (self.cfg["design_max_turns"] if kind == "design" else
                     self.cfg["read_max_turns"] if adapter.CAPS and kind in tasks.READ_CAPPED else 0)
        if "git_base" not in s:  # D1 a: the tree before the first attempt; the facts count the step's own lines
            head = claude_cli.git_head(task["project_dir"])
            s["git_base"] = {"commit": head, "files": claude_cli.git_snapshot(task["project_dir"], head)}
```

and `strict_mcp=True` joins the `self.runs.start(...)` keyword arguments (plan 5's runs.start passes it to the
Claude adapter only, Task 4). Plan 24's design step reads every raw note as `prev` (its D1): the facts of the last
good step still follow them.

**Lands on** plan 5 Task 5 (`Hub._facts`): a non-Claude step's stream has no Claude tool results. Read the harness
from the run's meta and pass it on:

```python
        harness = (self.runs.meta(sid) or {}).get("harness") or "claude"
        test = facts.last_test(lines) if harness == "claude" else None
        ...
            tasks.write_facts(self.folder, task, cs, facts.text(base.get("commit", ""), cs["end_commit"], changed,
                                                                test, git=after is not None,
                                                                read_tests=harness == "claude"))
```

and read the lines with plan 5's stream reader for the run (`runs.read_lines(self.runs.stream_path(sid), 0)` stays
right for Claude).

**Lands on** plan 24 Task 3 (`Hub._ended`): plan 24 adds the PLAN block checks and the `Replan:` insert after
`write_note`; `self._facts(...)` goes right after `tasks.write_note(...)`, before plan 24's lines. A replan step
(no session) never reaches `_ended`, so it has no facts; `start_brief`'s `files_in` reads `""` for it.

**Lands on** plan 5 Task 5 (`Hub.pull`: its `rung_ok` check; `Handler._task`) and plan 24 Task 3 (`task_row` gains
`plan`, `redo` and each step's `part` and `hard`; `Handler._task` gains `plan`, `parts`, `replan_note`): this task's
lines go beside theirs as the diff's anchors show; keep every key they added (the `auto` argument and its two lines in
`pull`, this task's three step keys in `task_row` next to plan 24's `part` and `hard`, `**self._step_texts(task)` at the end of `_task`'s answer).

## 5.2 `console/state.py`

**Lands on** plan 5 Task 4 (`Session.harness`, `run_started` builds a session from the run lines alone, the row gains
`harness`): add this task's lines next to plan 5's at the quoted anchors; if plan 5 put `"harness"` on the row line
quoted below, keep it on that line.

```diff
diff --git a/console/state.py b/console/state.py
index a9642e5..383bdb1 100644
--- a/console/state.py
+++ b/console/state.py
@@ -113,6 +113,7 @@ class Session:
     handoff_by: str = ""       # the session whose last message is the handoff note (itself or its Handoff copy)
     forked_from: str = ""
     handoff_of: str = ""       # a fresh Handoff chat (after a PASS): the session it hands off
+    auto_handoff: int = 0      # plan 23: the service handed it off by itself at this many context tokens
     forks: list = field(default_factory=list)
     turns: list = field(default_factory=list)  # [start, end or None] per turn; the last start is turn_ts
     rules: dict = field(default_factory=dict)  # file -> {scope, lines, bytes}: CLAUDE.md / rules loaded
@@ -260,6 +261,7 @@ class State:
             s.compactions += 1
         elif event == "marked_done":  # Fred's Mark done; the chat's next prompt brings it back
             s.in_turn, s.ended, s.doing = False, True, ""
+            s.auto_handoff = 0  # plan 23: the HANDED OFF card leaves Needs you
             self._turn_close(s, ts)
         elif event == "SessionEnd":
             s.in_turn = False
@@ -279,6 +281,10 @@ class State:
             s.handoff = s.kind == "handoff"
             if rec.get("handoff_of"):
                 s.handoff_of = rec["handoff_of"]
+            s.auto_handoff = 0
+            if rec.get("auto_handoff"):  # plan 23: Hub.auto_steps started it; the card is the chat it hands off
+                origin = self.sessions.get(rec.get("forked_from") or rec.get("handoff_of") or "")
+                (origin if origin and origin is not s else s).auto_handoff = int(rec["auto_handoff"])
             if rec.get("task"):
                 s.task, s.step = rec["task"], int(rec.get("step") or 0)
             if rec.get("escalated"):
@@ -478,6 +484,8 @@ class State:
                 group = "replied"
             else:
                 group = "working"
+            if s.auto_handoff and s.handed_off and not s.ended:  # plan 23: HANDED OFF waits for Start next chat
+                group = "needs"
             symbol, text, state_tone = STATES[state]
             follow_ups = max(0, s.prompts - 1)
             files = self.files(s)
@@ -503,7 +511,7 @@ class State:
                 "prep_model": s.prep_model, "prep_cost": s.prep_cost, "prep_turns": s.prep_turns,
                 "models": shares(fams(files)),
                 "task": s.task, "step": s.step,
-                "kind": s.kind, "handoff": s.handoff, "handoff_by": s.handoff_by if s.handed_off else "", "forked_from": s.forked_from, "forks": list(s.forks),
+                "kind": s.kind, "handoff": s.handoff, "handoff_by": s.handoff_by if s.handed_off else "", "auto_handoff": s.auto_handoff, "forked_from": s.forked_from, "forks": list(s.forks),
                 "follow_ups": follow_ups,
                 "handoff_hint": state not in DONE and (
                     tone == "red" or follow_ups >= self.cfg["handoff_after_followups"]),
```

## 5.3 Tests (`tests/test_server.py`, 84 -> 90 test methods)

```diff
diff --git a/tests/test_server.py b/tests/test_server.py
index 60de90e..fdfc4c3 100644
--- a/tests/test_server.py
+++ b/tests/test_server.py
@@ -2,6 +2,7 @@ import base64
 import http.client
 import json
 import os
+import subprocess
 import sys
 import tempfile
 import threading
@@ -538,6 +539,73 @@ class RunServerTest(unittest.TestCase):
         self.assertEqual(self.hub.levers("c4")["escalate"], "")  # a click may, the service does not
         self.assertEqual([lever for s, lever in self.hub.auto_steps() if s == "c4"], [])
 
+    # -- plan 23: auto handoff at red ---------------------------------------------------------------------------
+    def skill_here(self):
+        skill = self.project / ".claude" / "skills" / "session-handoff"
+        skill.mkdir(parents=True)
+        (skill / "SKILL.md").write_text("x", encoding="utf-8")
+
+    def red(self, sid, tokens=312000):
+        events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": sid,  # what the hook logs
+                                    "context_tokens": tokens})
+        self.hub.poll_once()
+
+    def test_setting_route_writes_handoff_auto_only(self):
+        self.assertEqual(self.call("/api/setting", {"key": "handoff_auto", "value": True}),
+                         (200, {"key": "handoff_auto", "value": True}))
+        self.assertIs(self.hub.cfg["handoff_auto"], True)
+        saved = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
+        self.assertIs(saved["handoff_auto"], True)
+        self.assertIs(self.call("/api/config")[1]["handoff_auto"], True)
+        self.assertEqual(self.call("/api/setting", {"key": "brief_on", "value": False}),
+                         (400, {"error": "not a setting: brief_on"}))
+        self.assertEqual(self.call("/api/setting", {"key": "handoff_auto", "value": "yes"})[0], 400)
+        self.assertIs(self.hub.cfg["brief_on"], True)
+
+    def test_auto_handoff_hands_a_red_window_run_off(self):
+        self.skill_here()
+        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",
+                                     "model": "sonnet", "effort": "medium"})[1]["session"]
+        self.wait_idle(sid)
+        self.red(sid)
+        self.assertEqual(self.hub.auto_steps(), [])  # handoff_auto is off by default
+        self.hub.cfg["handoff_auto"] = True
+        self.assertEqual(self.hub.auto_steps(), [(sid, "handoff")])
+        self.assertEqual(self.hub.runs.meta(sid)["model"], "sonnet")  # in place: a window run resumes
+        self.wait_idle(sid)
+        row = self.session(sid)
+        self.assertEqual((row["state"], row["group"], row["kind"], row["auto_handoff"]),
+                         ("done", "needs", "handoff", 312000))
+        self.assertEqual(self.hub.auto_steps(), [])  # once per session
+        self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["next"], "")  # Start next chat
+        self.assertEqual(self.call("/api/done", {"session": sid})[0], 200)
+        row = self.session(sid)
+        self.assertEqual((row["group"], row["auto_handoff"]), ("done", 0))
+
+    def test_auto_handoff_forks_a_red_vscode_chat_and_skips_route_steps(self):
+        self.skill_here()
+        self.hub.cfg["handoff_auto"] = True
+        self.hub.auto_since = 0
+        self.idle_chat("c6", hours=0, tokens=1000)
+        self.assertEqual(self.hub.auto_steps(), [])  # not red
+        self.idle_chat("c7", hours=0, tokens=312000)
+        self.assertEqual(self.hub.auto_steps(), [("c7", "handoff")])
+        fork = self.session("c7")["forks"][0]
+        self.wait_idle(fork)
+        row, copy_row = self.session("c7"), self.session(fork)
+        self.assertEqual((row["state"], row["group"], row["auto_handoff"], row["handoff_by"]),
+                         ("done", "needs", 312000, fork))  # the VS Code chat itself is never resumed
+        self.assertEqual((copy_row["kind"], copy_row["auto_handoff"]), ("handoff", 0))  # one card: the chat's
+        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",
+                                     "model": "sonnet", "effort": "medium"})[1]["session"]
+        self.wait_idle(sid)
+        self.hub.cfg["handoff_auto"] = False
+        self.red(sid)
+        self.verdict(sid, "FAIL", "test_add - 3 != 4")
+        self.hub.cfg["handoff_auto"] = True
+        self.assertEqual(self.hub.auto_steps(), [(sid, "handoff")])  # red: the handoff, not an Escalate
+        self.wait_idle(sid)
+
     def test_handoff_marks_the_session_done(self):
         skill = self.project / ".claude" / "skills" / "session-handoff"
         skill.mkdir(parents=True)
@@ -723,6 +791,7 @@ class TaskServerTest(RunServerTest):
         self.assertEqual((row["task"], row["step"], row["kind"]), (tid, 1, "task"))
         limits = self.hub.runs.meta(step["session"])["limits"]
         self.assertEqual((limits["disallow"], limits["tools"], limits["budget"]), (["Agent"], "Read,Grep,Glob", 3))
+        self.assertEqual((limits["strict_mcp"], limits["max_turns"]), (True, 15))  # plan 23: no MCP, read_max_turns
         self.assertEqual(self.hub.snapshot()["preps"], [])  # the card became the task
         # a second task in the same project starts beside the first (plan 20: parallel tasks per project)
         other = tasks.new_task(str(self.project), "proj", "Other", "goal", tasks.plan_steps(
@@ -865,7 +934,7 @@ class TaskServerTest(RunServerTest):
     def test_turn_cap_is_named_in_the_retry(self):
         tid = self.make_task(steps=[{"kind": "scout", "goal": "MAXTURNS look"}])
         task = self.until(tid, lambda t: t["state"] == "stuck", "stuck after the retry")
-        self.assertEqual(task["why"], "it hit the turn cap (? turns) (after one retry)")
+        self.assertEqual(task["why"], "it hit the turn cap (15 turns) (after one retry)")
 
     def test_retry_sums_the_cost_of_both_attempts(self):
         tid = self.make_task(words="", steps=[{"kind": "scout", "goal": "look"}])  # no HANDOFF: retry, then stuck
@@ -1111,7 +1180,7 @@ class TaskServerTest(RunServerTest):
             self.assertFalse(self.hub.runs.meta_path(sid).exists())
         folder = self.folder / "tasks" / tid
         self.assertEqual(sorted(p.name for p in (folder / "steps").iterdir()),
-                         ["02-explain.brief.md", "02-explain.md"])  # the last note and its brief
+                         ["02-explain.brief.md", "02-explain.facts.md", "02-explain.md"])  # the last note, its brief and facts
         saved = tasks.load(self.folder, tid)
         self.assertTrue(saved["cleared"])
         self.assertEqual((saved["state"], saved["steps"][0]["handoff"], saved["steps"][1]["handoff"]),
@@ -1199,7 +1325,8 @@ class TaskServerTest(RunServerTest):
         self.assertEqual([(s["n"], s["kind"], s["state"]) for s in row["steps"]],
                          [(1, "scout", "running"), (2, "code", "planned"), (3, "verify", "planned")])
         self.assertEqual(sorted(row["steps"][0]), sorted(["n", "kind", "state", "model", "effort", "session",
-                                                          "verdict", "retries", "cost", "note", "attempts"]))
+                                                          "verdict", "retries", "cost", "note", "attempts",
+                                                          "end_commit", "brief_meta", "facts"]))
         self.assertIn(row["steps"][0]["note"], ("writing", "unchecked"))
         self.until(tid, self.at(2), "step 2 starts")
         steps = next(t for t in self.hub.snapshot()["tasks"] if t["id"] == tid)["steps"]
@@ -1212,6 +1339,8 @@ class TaskServerTest(RunServerTest):
         self.assertEqual(data["levers"]["start"], "a step is running")
         self.assertIn("## Findings\nadd() is in calc.py:2", data["note"])
         self.assertIn("test_add covers it", data["brief"])
+        self.assertEqual((list(data["notes"]), list(data["briefs"]), list(data["facts"])), (["1"], ["1"], ["1"]))
+        self.assertEqual(data["notes"]["1"], data["note"])  # plan 23: every step's texts, keyed by its number
         self.assertEqual(self.task("../x")[0], 404)
         self.assertEqual(self.task("20260101-000000-ffff")[0], 404)
 
@@ -1252,6 +1381,7 @@ class TaskServerTest(RunServerTest):
         config = self.call("/api/config")[1]
         self.assertEqual((config["effort"], config["kinds"]), ("max", list(tasks.PREP_KINDS)))
         self.assertEqual(config["edit_kinds"], sorted(tasks.EDIT_KINDS))
+        self.assertIs(config["handoff_auto"], False)
         self.assertEqual(self.call("/api/draft", {"text": "", "effort": "turbo"})[0], 400)
         self.assertEqual(self.call("/api/draft", {"text": "", "effort": "auto"})[0], 200)
         self.assertEqual(self.call("/api/config")[1]["effort"], "auto")
```

- `test_chain_starts_step_one_from_the_card`: the scout's limits hold `strict_mcp` True and `max_turns` 15.
- `test_turn_cap_is_named_in_the_retry`: the reason names `15 turns` (the scout now has a cap; if plan 5 Task 5
  already wrote `15 turns` there for its `READ_MAX_TURNS`, the line stays as it is).
- `test_done_task_is_cleared`: the last facts file stays with the last note and brief.
- `test_task_snapshot_and_get`: the row's step keys gain `end_commit`, `brief_meta`, `facts` (the keys plan 24 Task 3
  and plan 5 added to that sorted list, `part`, `hard`, `harness`, stay in it); `GET /api/task` has `notes`, `briefs`,
  `facts` keyed `"1"`.
- `test_draft_keeps_the_effort`: `/api/config` has `handoff_auto` False.
- New, RunServerTest: `test_setting_route_writes_handoff_auto_only`, `test_auto_handoff_hands_a_red_window_run_off`
  (off by default; on: one handoff in place, the row `done` / `needs` / `auto_handoff` 312000, once only, Start next
  chat allowed, Mark done clears it), `test_auto_handoff_forks_a_red_vscode_chat_and_skips_route_steps` (a chat under
  red is left alone, a red one is forked, the card is the chat's, a red window run with a FAIL verdict hands off
  instead of escalating). Helpers `skill_here`, `red`.
- New, TaskServerTest: `test_facts_are_read_when_a_step_ends` (a temp git repo in the test's project folder; the
  step's work written between start and end; `git_base`, `facts`, `end_commit`, the facts text, step 2's prompt, the
  task route; skipped without git), `test_brief_meta_and_the_carried_troubleshooting`,
  `test_lessons_reach_steps_of_their_kind`.

## 5.4 Steps

1. The tests of 5.3. Run `py -m unittest tests.test_server`: the new and changed ones fail.
2. `console/state.py`, then `console/server.py` (with the Lands-on forms where plans 5 and 24 are placed).
3. Full suite: all OK (Linux scratch: 356 run, 352 OK, the 4 environment failures of the baseline).
4. Commit: `Plan 23 Task 5: facts and lessons in step prompts, brief_meta, task routes, auto handoff at red,
   POST /api/setting (N tests OK)`.

**Drift guards**
- `Hub.levers` is not changed: the auto handoff goes through `pull`, so every gate (runs allowed, skill installed,
  still working, cold cache, a task step) holds.
- `auto_handed` is in memory only: after a service restart `auto_since` keeps old turns out.
- `_facts` runs inside `tlock` like the rest of `_ended` (two git commands, 10 s timeout each at worst).
- `git_base` is never sent to the window; `task_row` lists the three fields of README 3.8 only.
- `/api/setting` goes through `do_POST`'s guard like every route; it writes config.json only.
