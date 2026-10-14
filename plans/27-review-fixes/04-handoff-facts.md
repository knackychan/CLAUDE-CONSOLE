# Task 4: handoff and facts (K3, K4, K5, K6, G2, plan 23 nits)

> Contract: [review.md](review.md) findings K3, K4, K5, K6, G2 and the three plan 23 nits (`factsFold` with
> `force: fail` cannot be closed while red; `lessons_for` filters after a 40-line cut; D5 `touched` comes from the
> 30-line facts text); plan 23 README 3.4 and 3.10, Task 3 (`git_snapshot`), Task 5 (the service, the guard "never
> send git_base"), Task 6 (`factsFold` as 6.2 wrote it: `if (!f && !text) return "";`, no `force`).
> Depends on: nothing of plan 27 (Tasks 1 to 3 touch none of the functions below; see Lands on).
> Decisions: two, marked `Decision:` in 4.2 and 4.4.
> Run in a scratch copy on 2026-10-14: the whole suite 531 tests (525 before, six added), only the 4 Linux baseline
> failures (test_tray import, test_redact Windows path, test_usage local day, test_window placement);
> `tests.test_facts` 9 OK (7 before); `node --check web/app.js` OK; the Task page checked in headless Chromium at
> 400 x 760 and 340 x 760 (4.8).
> Lands on: plan 23 Task 3 (`claude_cli.git_snapshot`), Task 5 (`Hub.auto_steps`, `Hub._facts`, `Hub.start_brief`,
> `Handler._task`, the lessons line of `Hub.start_step`), Task 6 (`factsFold`, `handoffFold`), plan 25 Task 5
> (`factsFold`'s `key: "facts"` and `<pre>` body). Plan 27 Task 3 also edits `Hub.start_step` (it moves
> `self.reload_models()` above `_route_for`): this task changes one other line of it (the `lessons =` line), so the
> two edits commute; apply each by its anchor, not by line number.

**Files**
- Modify: `console/server.py` (`Hub.__init__`: one line inserted; `Hub.auto_steps` replaced whole; `Hub.start_step`:
  the `lessons =` line; `Hub._facts`: one line inserted; `Hub.start_brief`: the `touched =` line; `Handler._task`:
  two lines)
- Modify: `console/claude_cli.py` (`UNTRACKED_READ_MAX` lowered, new `UNTRACKED_MAX`; `git_snapshot`: the `for cmd`
  tuple and the untracked slice)
- Modify: `console/tasks.py` (new constant `LESSONS_READ`)
- Modify: `web/app.js` (`factsFold`: four lines; `handoffFold`: the `sent` line, two lines inserted, the `body` line)
- Modify: `tests/test_facts.py` (two tests in `FactsTest`)
- Modify: `tests/test_server.py` (one test in `RunServerTest`, three in `TaskServerTest`)
- `web/style.css`, `web/index.html`: nothing (`li.cut`, `.tag`, `.fold.facts` exist from plan 23 Task 6)

What the review found, in short: with `handoff_auto` on, a red window run whose handoff pull keeps answering 409 (no
`session-handoff` skill, a cold-cache confirm) never joins `auto_handed`, and the `elif` keeps its FAIL or PASS verdict
out of `due`, so the route step never runs and the pull is retried every second (K3). `git_snapshot` reads up to 500
untracked files of up to 1 MB each, inside `advance()`'s `tlock` (K4), and runs git without
`-c core.quotePath=false`, so a non-ASCII path comes back octal-quoted (`"caf\303\251.py"`), counts 0 lines and fails
the brief's D5 path check (K5). `Handler._task` sends the raw task, every step's `git_base` (up to 500 paths) with it,
on every poll of the Task page (K6). The Task page's "as sent" view passes `cut=[]` to `headingBlock`, and the brief no
longer holds the cut findings, so after a LONG cut it reads `1 line · whole`, never `N kept · M cut` (G2).

## 4.1 `console/server.py`: `Hub.__init__` and `Hub.auto_steps` (K3)

In `Hub.__init__`, insert after the line

```python
        self.auto_handed = set()  # plan 23: sessions handoff_auto handed off once (never twice)
```

the line

```python
        self.auto_refused = {}  # plan 27: session id -> the turn end whose auto handoff was refused (tried once per turn)
```

Replace `def auto_steps(self) -> list:` whole (from its `def` line down to and including its `return pulled`) with:

```python
    def auto_steps(self) -> list:
        """Plan 16 (Fred: b): when a window run's turn ends with a verdict, the service takes the route
        step itself: Escalate after FAIL, de-escalate after PASS. Only verdicts about the last turn that
        arrived while this service runs, never a VS Code or terminal chat, never past a cold-cache
        confirm, and only what self.levers allows. Returns the (session, lever) pairs it pulled."""
        now, red, auto = time.time(), self.cfg["gauge_red_tokens"], bool(self.cfg.get("handoff_auto"))
        hand, due = [], []
        with self.lock:
            for s in self.state.sessions.values():
                if s.task:  # a step's verdict and context are its chain's
                    continue
                st = self.state.state_of(s, now)
                turn = (s.turns[-1][1] or 0) if s.turns else 0
                step = ("escalate" if st == "verify_failed" else "deescalate") if (
                    s.window and s.verdict_ts >= self.auto_since and st in ("verify_failed", "verified")) else ""
                if (auto and (s.ctx_tokens or 0) >= red
                        and st in AUTO_HANDOFF_STATES and not s.handoff and s.id not in self.auto_handed
                        and s.turns and turn >= self.auto_since and self.auto_refused.get(s.id) != turn):
                    hand.append((s.id, s.ctx_tokens, turn, step))  # plan 23: a red turn hands off; no route step
                elif step:
                    due.append((s.id, step))
        pulled = []
        for sid, tokens, turn, step in hand:  # pull forks a VS Code chat first: it is never resumed in place
            try:
                if self.pull(sid, "handoff", auto=tokens)[0] == 200:
                    self.auto_handed.add(sid)
                    pulled.append((sid, "handoff"))
                    continue
            except (runs.RunError, OSError):
                pass
            self.auto_refused[sid] = turn  # plan 27: refused, so not again before this session's next turn end
            if step:  # and the verdict still takes its route step
                due.append((sid, step))
        for sid, lever in due:
            try:
                if self.pull(sid, lever)[0] == 200:
                    pulled.append((sid, lever))
            except (runs.RunError, OSError):  # a click got there first, or claude did not start
                continue
        return pulled
```

- `turn` is the end time of the session's last turn (`s.turns[-1][1]`), the same value the old condition compared to
  `auto_since`. A refused (non-200) or failed (`RunError`, `OSError`) handoff pull records it in `auto_refused`, so
  the next pass skips the handoff until the session has a new turn end, and the verdict's route step (`step`) joins
  `due` in the same pass. A handed-off session still joins `auto_handed` and never takes a route step.
- `s.turns and` stays in the condition: a session with no turn never hands off, even when a test sets `auto_since` 0.

## 4.2 `console/claude_cli.py`: `git_snapshot` (K4, K5)

Replace the line

```python
UNTRACKED_READ_MAX = 1024 * 1024  # an untracked file larger than this counts 0 lines (plan 23 facts)
```

whole with

```python
UNTRACKED_READ_MAX = 256 * 1024  # an untracked file larger than this counts 0 lines (plan 23 facts, plan 27 K4)
UNTRACKED_MAX = 100  # untracked files a snapshot reads; later ones are left out (plan 27 K4: an unignored venv)
```

In `git_snapshot`, replace the line

```python
    for cmd in (["git", "diff", "--numstat", commit], ["git", "ls-files", "--others", "--exclude-standard"]):
```

whole with

```python
    for cmd in (["git", "-c", "core.quotePath=false", "diff", "--numstat", commit],  # plan 27 K5: paths as written
                ["git", "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"]):
```

and the line

```python
    for name in outs[1].splitlines()[:facts.SNAPSHOT_MAX]:
```

whole with

```python
    for name in outs[1].splitlines()[:UNTRACKED_MAX]:
```

- `facts.SNAPSHOT_MAX` (500) stays: it caps the whole snapshot (numstat files plus untracked files) in
  `facts.parse_numstat` and `facts.snapshot`, a different cap from the untracked files read, so the 100 is a new
  constant in `claude_cli`, next to `UNTRACKED_READ_MAX`. The worst case read is now 100 files of 256 KB (25 MB)
  instead of 500 of 1 MB (500 MB).
- `core.quotePath=false` returns non-ASCII paths as UTF-8 (the call already decodes `utf-8`); a path with a tab, a
  newline or a double quote is still quoted by git, as before (out of this finding).

Decision: the snapshot stays inside `tlock`, with the lower caps, because it cannot be moved out cleanly.
`start_step` is reached only through `_go_on`, which runs under `tlock` from `advance` (the hub loop, and inside
`create_task` and `task_lever`, which already hold `tlock`, so the `RLock` is held twice there), from `_ended` and
from `_replan_done`; so `start_step` cannot release it around the git calls. The base snapshot must be taken after the
service decides a step starts and before `runs.start` (it is the tree the step starts on), and the end snapshot in
`_facts` must land before `_ended` calls `start_brief` and `_go_on` (the next step's prompt reads
`steps/NN-<kind>.facts.md`, and `start_brief` reads `touched`). Taking the snapshot before `advance` takes the lock
would mean predicting, outside the lock, which task will start or end a step, a second copy of `_advance_one`'s
decisions. What waits on `tlock` is the task moves, `/api/task` (`task_levers`) and `/api/usage` (`fail_hours`);
`/api/state` and the session list use `self.lock`.

## 4.3 `console/server.py`: `Handler._task` (K6)

In `Handler._task`, replace the two lines

```python
        texts = self._step_texts(task)
        return self._json({"task": task, "levers": self.hub.task_levers(task_id),
```

whole with

```python
        texts = self._step_texts(task)
        sent = dict(task, steps=[{k: v for k, v in s.items() if k not in ("git_base", "touched")}  # plan 27 K6
                                 for s in task["steps"]])
        return self._json({"task": sent, "levers": self.hub.task_levers(task_id),
```

- Every other key of the response, and every read below it (`read_note`, `plan.read`, `open_questions`, ...), keeps
  `task` (the hub's own dict): only the copy sent as `"task"` is trimmed. The window reads neither key (`grep
  git_base web/app.js` finds nothing). `touched` is the key 4.4 adds.

## 4.4 `console/server.py`: `Hub._facts` and `Hub.start_brief` (plan 23 nit: D5 `touched`)

In `Hub._facts`, insert after the line

```python
        cs["facts"] = facts.facts(changed, test)
```

the line

```python
        cs["touched"] = list(changed)  # plan 27: every path for the brief's D5 check (the facts text lists 30)
```

In `Hub.start_brief`, replace the line

```python
        touched = [p for k in range(1, n + 1) for p in facts.files_in(tasks.read_facts(self.folder, task, k))]
```

whole with

```python
        done = {x["n"]: x for x in task["steps"]}
        touched = [p for k in range(1, n + 1)  # plan 27: every path; a step from before plan 27 has its facts text only
                   for p in (done[k]["touched"] if "touched" in done.get(k, {}) else
                             facts.files_in(tasks.read_facts(self.folder, task, k)))]
```

Decision: the full path list lives in a new step key `s["touched"]` (task.json), not inside `s["facts"]`, because
`s["facts"]` goes to the window in every snapshot row (`task_row`) and in `/api/task`: the paths (up to 500, the
`facts.SNAPSHOT_MAX` of the delta) stay in the service like `git_base`, and `_task` drops them (4.3). A step that ended
before this change has no `touched` and keeps the old source, the facts text's diff stat lines.

## 4.5 `console/tasks.py` and `Hub.start_step` (plan 23 nit: `lessons_for` after a 40-line cut)

In `console/tasks.py`, insert after the line

```python
LESSONS_IN_PROMPT = 5  # the newest lessons of the step's own kind that ride in its prompt (plan 23)
```

the line

```python
LESSONS_READ = 1000  # the project's lessons.md lines lessons_for picks the step's kind from (plan 27: filter, then cut)
```

In `Hub.start_step`, replace the line

```python
        lessons = tasks.lessons_for(levers.read_lessons(self.folder, task["project"]), kind)
```

whole with

```python
        lessons = tasks.lessons_for(levers.read_lessons(self.folder, task["project"], tasks.LESSONS_READ), kind)
```

- `levers.read_lessons` already reads the whole file; the limit only slices the project's lines, so 1000 costs no
  extra read. `levers.LESSONS_SHOWN` (40) stays the default for the rules review (`console/review.py`), which shows
  the newest lessons of every kind. `tasks.lessons_for` itself is unchanged: it still keeps the newest
  `LESSONS_IN_PROMPT` of the step's kind.

## 4.6 `web/app.js`: `factsFold` (plan 23 nit: `force: fail`)

In `factsFold`, replace the four lines

```js
  if (!f || !text) return "";
  const fail = String(f.tests || "").startsWith("FAIL");  // plan 23: "" (no test run), "23 OK" or "FAIL <first failing line>"
  const info = `${f.files} ${f.files === 1 ? "file" : "files"} +${f.plus}${f.minus ? " -" + f.minus : ""} · ${esc(f.tests || "no test run")}`;
  return fold("Facts", info, `<pre class="text mono">${esc(text)}</pre>`, { cls: "facts", tone: fail ? "r" : "", open: fail, force: fail, key: "facts",
```

whole with

```js
  if (!f && !text) return "";  // plan 27: either one is worth showing
  const fail = !!f && String(f.tests || "").startsWith("FAIL");  // plan 23: "" (no test run), "23 OK" or "FAIL <first failing line>"
  const info = f ? `${f.files} ${f.files === 1 ? "file" : "files"} +${f.plus}${f.minus ? " -" + f.minus : ""} · ${esc(f.tests || "no test run")}` : "read";
  return fold("Facts", info, `<pre class="text mono">${esc(text || "")}</pre>`, { cls: "facts", tone: fail ? "r" : "", open: fail, key: "facts",
```

- As plan 23 6.2 wrote it: a red step opens the fold by default (`open: fail`), and Fred can close it; with plan 25's
  `key: "facts"` the choice is kept in window.json `folds` like every keyed fold. `"read"` is 6.2's info for a facts
  text with no `s.facts` (a step whose task.json lost the key). The title line after these four stays as it is.

## 4.7 `web/app.js`: `handoffFold`, the "as sent" view (G2)

In `handoffFold`, replace the line

```js
  const sent = handoffSections(brief), wrote = handoffSections(raw), cut = (meta && meta.cut) || [];
```

whole with

```js
  const sent = handoffSections(brief), wrote = handoffSections(raw), cut = ((meta && meta.cut) || []).map(normItem);
  const all = [].concat(sent.findings, sent.files, sent.trouble, sent.questions);
  for (const c of cut) if (!all.includes(c)) sent.findings.push(c);  // plan 27 (G2): the cut lines, struck under Findings, as inspConn does
```

and replace the line

```js
  const body = rawOpen ? headingBlock(wrote, cut, ["goal", "findings", "trouble", "questions", "next"]) : headingBlock(sent, [], undefined, true);
```

whole with

```js
  const body = rawOpen ? headingBlock(wrote, cut, ["goal", "findings", "trouble", "questions", "next"]) : headingBlock(sent, cut, undefined, true);
```

- The same three steps as the Board's `inspConn`: `meta.cut` through `normItem`, each cut item the brief does not hold
  appended to Findings, and `cut` passed to `headingBlock`, which strikes them (`li.cut` with the `cut` tag) and counts
  `N kept · M cut`. The "as NN wrote it" view keeps its own items and now gets the same normalized `cut`.
- `words`, `info` and `head` are unchanged: they read `meta.sent_w` and `sent.next`, never the Findings list.

## 4.8 Tests

`tests/test_facts.py`: insert after the last line of `test_git_snapshot_on_a_real_repo`
(`self.assertIsNone(claude_cli.git_snapshot(tempfile.gettempdir(), head))  # not this repo's commit`), inside
`FactsTest`:

```python

    @unittest.skipUnless(subprocess.run(["git", "--version"], capture_output=True).returncode == 0, "no git")
    def test_git_snapshot_reads_non_ascii_paths(self):  # plan 27 (K5): no octal-quoted path
        with tempfile.TemporaryDirectory() as repo:
            run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, check=True)
            run("init", "-q")
            run("config", "core.quotePath", "true")  # git's default, whatever the global config says
            (Path(repo) / "naïve.py").write_text("a\n", encoding="utf-8")
            run("add", "naïve.py")
            run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "start")
            head = claude_cli.git_head(repo)
            (Path(repo) / "naïve.py").write_text("a\nb\n", encoding="utf-8")
            (Path(repo) / "café.py").write_text("x\ny\nz\n", encoding="utf-8")
            snap = claude_cli.git_snapshot(repo, head)
            self.assertEqual(snap, {"naïve.py": [1, 0], "café.py": [3, 0]})
            self.assertEqual(facts.files_in(facts.text(head, head, snap, None)), ["naïve.py", "café.py"])

    @unittest.skipUnless(subprocess.run(["git", "--version"], capture_output=True).returncode == 0, "no git")
    def test_git_snapshot_caps_the_untracked_files(self):  # plan 27 (K4): a venv or a build folder stays cheap
        with tempfile.TemporaryDirectory() as repo:
            run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, check=True)
            run("init", "-q")
            run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "start")
            head = claude_cli.git_head(repo)
            (Path(repo) / "big.txt").write_bytes(b"x\n" * (claude_cli.UNTRACKED_READ_MAX // 2 + 1))  # one byte over
            (Path(repo) / "build").mkdir()
            for k in range(claude_cli.UNTRACKED_MAX + 20):
                (Path(repo) / "build" / f"f{k:03d}.txt").write_text("1\n", encoding="utf-8")
            snap = claude_cli.git_snapshot(repo, head)
            self.assertEqual((claude_cli.UNTRACKED_MAX, claude_cli.UNTRACKED_READ_MAX), (100, 256 * 1024))
            self.assertEqual(len(snap), claude_cli.UNTRACKED_MAX)  # the first 100 untracked files, in git's order
            self.assertEqual(snap["big.txt"], [0, 0])  # over 256 KB: listed, its lines not read
```

`tests/test_server.py`, in `RunServerTest`: insert right before `def test_handoff_marks_the_session_done(self):`
(after the last two lines of `test_auto_handoff_forks_a_red_vscode_chat_and_skips_route_steps`:
`self.assertEqual(self.hub.auto_steps(), [(sid, "handoff")])  # red: the handoff, not an Escalate` and
`self.wait_idle(sid)`):

```python
    def test_refused_auto_handoff_still_escalates_and_is_tried_once_per_turn(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",  # no session-handoff skill
                                     "model": "sonnet", "effort": "medium"})[1]["session"]
        self.wait_idle(sid)
        self.red(sid)
        self.verdict(sid, "FAIL", "test_add - 3 != 4")
        self.hub.cfg["handoff_auto"] = True
        self.assertNotEqual(self.hub.pull(sid, "handoff")[0], 200)  # refused: the pull answers 409
        calls = []
        real = self.hub.pull
        self.hub.pull = lambda s, lever, **kw: calls.append(lever) or real(s, lever, **kw)
        self.assertEqual(self.hub.auto_steps(), [(sid, "escalate")])  # the FAIL verdict still takes its step
        self.wait_idle(sid)
        self.hub.auto_steps()
        self.hub.auto_steps()
        self.assertEqual(calls.count("handoff"), 2)  # once for the FAIL turn, once for the escalated turn, not every pass
        self.assertNotIn(sid, self.hub.auto_handed)  # never handed off

```

`tests/test_server.py`, in `TaskServerTest`: insert after the last line of `test_facts_are_read_when_a_step_ends`
(`self.assertEqual(self.task(tid)[1]["task"]["steps"][0]["facts"], step1["facts"])`):

```python

    def test_task_route_sends_no_git_base(self):  # plan 27 (K6): the snapshots stay in the service
        tid = self.make_task()
        task = self.until(tid, self.at(2), "step 2 starts")
        self.assertIn("git_base", task["steps"][0])
        sent = self.task(tid)[1]["task"]
        self.assertEqual([s for s in sent["steps"] if "git_base" in s or "touched" in s], [])
        self.assertEqual(sent["steps"][0]["session"], task["steps"][0]["session"])  # the rest of the step is sent
        self.assertIn("git_base", self.hub.tasks[tid]["steps"][0])  # a copy was trimmed, not the hub's task

    def test_brief_check_reads_every_path_a_step_touched(self):  # plan 27 (23 nit): not the facts text's 30 lines
        try:
            self.git("init", "-q")
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("no git")
        self.git("commit", "-q", "--allow-empty", "-m", "base")
        tid = self.make_task()
        task = self.until(tid, self.at(2), "step 2 starts")
        step1 = task["steps"][0]
        for k in range(35):
            (self.project / f"f{k:02d}.py").write_text("x = 1\n", encoding="utf-8")
        with self.hub.tlock:
            self.hub._facts(task, step1, step1["session"])
        self.assertIn(" ... and 5 more", tasks.read_facts(self.folder, task, 1))  # the text stays short
        seen = []
        self.hub._brief_job = lambda t, s, nxt, prev, raw, touched=(): seen.append(sorted(touched))
        with self.hub.tlock:
            self.hub.start_brief(task, 1)
        end = time.time() + 5
        while not seen and time.time() < end:
            time.sleep(0.05)
        self.assertEqual(seen, [[f"f{k:02d}.py" for k in range(35)]])
```

and insert after the last two lines of `test_lessons_reach_steps_of_their_kind`
(`self.assertNotIn("a chat lesson", first)` and `self.settled(tid)`):

```python

    def test_a_kinds_lesson_outlives_many_of_other_kinds(self):  # plan 27 (23 nit): the kind filter comes first
        levers.add_lesson(self.folder, levers.lesson_line("proj", "scout", "read calc.py before tests"))
        for k in range(levers.LESSONS_SHOWN + 5):  # newer lessons of another kind, more than the Review page shows
            levers.add_lesson(self.folder, levers.lesson_line("proj", "code", f"code lesson {k}"))
        tid = self.make_task(steps=self.TWO)
        task = self.until(tid, self.at(2), "step 2 starts")
        self.assertIn("read calc.py before tests", self.prompt_of(task["steps"][0]["session"]))
        self.settled(tid)
```

What each failed with before the fix (seen in the scratch copy):

| Test | Failure before the fix |
|---|---|
| `test_refused_auto_handoff_still_escalates_and_is_tried_once_per_turn` | `AssertionError: Lists differ: [] != [('<sid>', 'escalate')]` |
| `test_git_snapshot_reads_non_ascii_paths` | `AssertionError: {'"na\\303\\257ve.py"': [1, 0], '"caf\\303\\251.py"': [0, 0]} != {'naïve.py': [1, 0], 'café.py': [3, 0]}` |
| `test_git_snapshot_caps_the_untracked_files` | `AttributeError: module 'console.claude_cli' has no attribute 'UNTRACKED_MAX'` |
| `test_task_route_sends_no_git_base` | `AssertionError: Lists differ: [{'n': 1, 'kind': 'scout', 'goal': 'find t[1877 chars]de'}] != []` |
| `test_brief_check_reads_every_path_a_step_touched` | `AssertionError: Lists differ`: 30 paths (`f00.py` to `f29.py`) against 35 |
| `test_a_kinds_lesson_outlives_many_of_other_kinds` | `AssertionError: 'read calc.py before tests' not found in "You run one step of a task ...` |

The window item (4.6, 4.7), checked in headless Chromium (Playwright from `/opt/node22/lib/node_modules/playwright`,
the browser under `/opt/pw-browsers`; no `playwright install`): a scratch `CC_CONSOLE_HOME` with a `config.json` made
from `paths.DEFAULTS` with `"port": 47794` (another writer may hold 47770) and the scratch project in `projects`;
a seeded task (like plan 25's checks: `tasks.new_task`, two done steps, `last_good` 2, step 2 with
`brief_meta.cut` = `["- the <b>first</b>  long finding", "second   long finding"]`, a note whose Findings hold those
two and `kept`, a brief whose Findings hold `kept` only, `facts` `{"files": 2, "plus": 5, "minus": 1, "tests":
"FAIL FAIL: test_add"}` and a facts file); `CC_CONSOLE_HOME=<scratch> python3 -m console --serve`; the page opened at
400 x 760 and 340 x 760, the task card clicked, the Handoff fold opened:

| Check | Before | After |
|---|---|---|
| "as sent" Findings label | `Findings1 line · whole` | `Findings1 kept · 2 cut` |
| struck `li.cut s` in "as sent" | none | `the <b>first</b> long finding`, `second long finding` (escaped, normalized) |
| "as 02 wrote it" Findings | `1 kept · 2 cut` | `1 kept · 2 cut` (unchanged) |
| red Facts fold after a close and a redraw | open again (`force`) | stays closed |
| console errors, horizontal overflow | none | none |

## 4.9 Steps

1. Write the two tests of `tests/test_facts.py`. `python -m unittest tests.test_facts` fails: the non-ASCII test
   with the octal-quoted paths above, the caps test with `AttributeError: ... no attribute 'UNTRACKED_MAX'`.
2. Apply 4.2. `tests.test_facts`: 9 OK.
3. Write `test_refused_auto_handoff_still_escalates_and_is_tried_once_per_turn`. Run
   `python -m unittest tests.test_server.RunServerTest.test_refused_auto_handoff_still_escalates_and_is_tried_once_per_turn`:
   fails with `Lists differ: [] != [('<sid>', 'escalate')]`. Apply 4.1. Green.
4. Write `test_task_route_sends_no_git_base` and `test_brief_check_reads_every_path_a_step_touched`. Both fail as in
   the table. Apply 4.3 and 4.4. Green.
5. Write `test_a_kinds_lesson_outlives_many_of_other_kinds`. Fails (`'read calc.py before tests' not found`). Apply
   4.5. Green.
6. Apply 4.6 and 4.7. `node --check web/app.js`. Check the Task page in headless Chromium (or Edge) as 4.8 says, at
   400 and 340 px: `N kept · M cut` in the "as sent" view, the cut lines struck, the red Facts fold closable, no
   console error, no horizontal overflow.
7. The full suite `py -m unittest discover -s tests`: all OK on Windows (Linux scratch: 531 run, only the 4 baseline
   failures).
8. Commit: `Plan 27 Task 4: handoff and facts (auto handoff falls through, snapshot caps and quotePath, no git_base sent, cut lines as sent) (N tests OK)`.

**Drift guards**
- `auto_steps` never pulls a handoff twice for the same turn end, and a handed-off session (in `auto_handed`) still
  takes no route step. Do not drop `s.turns and` from the handoff condition.
- `git_snapshot` stays read only (two git commands, file reads) with the 10 s timeout and `NO_WINDOW`; `facts.py` is not
  changed and `facts.SNAPSHOT_MAX` stays 500. Do not move the snapshot out of `tlock` in this task (see the Decision).
- `git_base` and `touched` never reach the window: not in `task_row`, not in `/api/task`. `Handler._task` trims a copy;
  the hub's task dict and task.json keep both keys.
- `tasks.lessons_for` and `levers.read_lessons`' default (40, used by the rules review) are unchanged.
- No CSS change: `li.cut`, `.tag` and `.fold.facts` exist. No other function of `server.py` changes (Tasks 1 to 3 and
  5 edit other functions of the same file in parallel; `Hub.start_step` is shared with Task 3, one line each).
- Plan 23's text for the cut view (Task 6) is amended by Task 7 (docs), not here.
