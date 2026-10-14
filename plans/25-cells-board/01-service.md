# Task 1: The service: open questions, the chain log, the measure table, ctx per step, the Board size

> Contract: [README.md](README.md) 3.1 to 3.3. Design: interface doc 2 (`window.json` `board`), 8.3 (task head: open
> questions, chain log; Measure), 11 (what each screen needs). Decisions: D2 (`open_questions`), D3 (`measure`'s
> `hot`). Run in a scratch copy of the working tree on 2026-10-14 with exactly this code: the 10 new tests pass, the
> full suite is 336 tests with only the 4 known Linux environment failures.
>
> Lands on: plan 23 Task 5 (`Hub._ended` calls `self._facts(...)` after `write_note`, below this task's anchor, which it
> leaves as it is; `/api/config` gained `handoff_auto`). Plan 23's service task (`Handler._task` builds `facts`, `notes`, `briefs`): reuse its `briefs` dict for
> `open_questions` instead of the line 1.4 adds (the function takes int or str keys). Plan 24 Task 3 (`Handler._task`
> adds `plan`, `parts`, `replan_note`; `Hub._ended` gains the PLAN checks): this task's two lines sit beside theirs,
> anchored below. Plan 26 Task 3 moved the `/api/config` dict into `Handler._config`: 1.4 edits it there.
> Nothing else in this task touches a function an earlier plan changes.

**Files**
- Modify: `console/tasks.py` (new section before `# -- prompts`: `section_items`, `question_key`, `open_questions`,
  `read_chain`, `note_words`, `same_dir`, `measure` and helpers `_words`, `_median`, `_count`; constants
  `QUESTIONS_HEAD`, `NO_ITEM`, `MEASURE_MAX`; `import statistics`)
- Modify: `console/server.py` (`import re`; constants `BOARD_TABS`, `FOLD_KEY`, `FOLDS_MAX` and `folds_ok`;
  `Hub._ended`; `Handler.do_GET` (`/api/config`, `/api/measure`); `Handler._draft`; `Handler._task`; new
  `Handler._measure`)
- Modify: `console/window.py` (`BOARD_W`, `BOARD_H`, `BOARD_MIN_W`, `clamp_board`, `WindowApi.__init__`, `form`,
  `_board_css`, `board_size`, `board`, `resize`)
- Modify: `tests/test_tasks.py` (helper `brief`, class `BoardTest`), `tests/test_server.py` (`from urllib.parse import
  quote`; three tests in `TaskServerTest`), `tests/test_window.py` (two tests in `WindowApiTest`)

## 1.1 `console/tasks.py`

Add `import statistics` after `import shutil`. Add this section right before `# -- prompts ----`:

```python
# -- the Board (plan 25): open questions, the chain log, the measure table ------------------------------------

QUESTIONS_HEAD = "## Open questions"
NO_ITEM = ("(none)", "none", "n/a", "-", "")
MEASURE_MAX = 50  # tasks at most in one measure table


def section_items(text: str, heading: str) -> list:
    """The `- ` items under `heading` in a note or a brief, without the dash, in order; "(none)" items dropped."""
    out, inside = [], False
    for line in str(text or "").splitlines():
        if line.startswith("## "):
            inside = line.strip() == heading
            continue
        item = line.strip()
        if inside and item.startswith(("- ", "* ")):
            item = item[2:].strip()
            if item.lower().rstrip(".") not in NO_ITEM:
                out.append(item)
    return out


def question_key(text: str) -> str:
    """Two spellings of one question compare equal: whitespace, case and a trailing `?` or `.` do not count."""
    return " ".join(str(text).split()).lower().rstrip(" ?.")


def open_questions(task: dict, briefs: dict) -> list:
    """[{q, opened, closed}] from the Open questions of each step's brief, in step order (D2 a): a question opens at
    the first brief that carries it and closes at the first later brief that no longer does; closed 0 = still open.
    `briefs` maps step numbers (int or the str of an int, as GET /api/task keys them) to the brief text."""
    texts = {int(k): v for k, v in (briefs or {}).items() if str(k).isdigit() and v}
    found, order = {}, []
    for s in task.get("steps") or []:
        n = s["n"]
        if n not in texts:
            continue
        here = {question_key(q): q for q in section_items(texts[n], QUESTIONS_HEAD)}
        for key, q in here.items():
            if key not in found:
                found[key] = {"q": q, "opened": n, "closed": 0}
                order.append(key)
        for key in order:
            if key not in here and not found[key]["closed"]:
                found[key]["closed"] = n
    return [found[k] for k in order]


def read_chain(home, task: dict, limit: int = 200) -> list:
    """The last `limit` lines of the task's chain.jsonl as dicts, oldest first; a broken line is skipped."""
    try:
        lines = (folder(home, task["id"]) / "chain.jsonl").read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return []
    out = []
    for line in lines[-limit:]:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _words(text) -> int:
    return len(str(text or "").split())


def note_words(text: str) -> int:
    """A note file's words without its `# Step NN: ...` head line."""
    lines = str(text or "").splitlines()
    return _words("\n".join(lines[1:] if lines and lines[0].startswith("# Step ") else lines))


def _median(values):
    return round(statistics.median(values)) if values else None


def same_dir(a, b) -> bool:
    norm = lambda p: os.path.normcase(os.path.normpath(str(p)))
    return bool(a) and bool(b) and norm(a) == norm(b)


def _count(value):
    """A stored count (brief_meta words, ctx_tokens), or None for anything that is not a whole number."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def measure(home, project: str, n: int = 10) -> dict:
    """The Board's measure table (brainstorm 5.1 item 6): medians per step kind over the project's last `n` tasks,
    newest by `created`. received: the words a step got (the previous step's handoff after the brief pass,
    brief_meta.sent_w, else the brief file's words); context: the step's ctx_tokens; handoff: the words it wrote
    (brief_meta.raw_w, else the note file's words). Done steps only; a zero or unknown value is left out.
    hot: the kind with the most context per received word (D3 a), "" when no kind has both."""
    n = max(1, min(int(n), MEASURE_MAX))
    mine = sorted((t for t in load_all(home).values() if same_dir(t.get("project_dir"), project)),
                  key=lambda t: t.get("created") or 0, reverse=True)[:n]
    got, ctx, wrote, steps = {}, {}, {}, {}
    for t in mine:
        by_n = {s["n"]: s for s in t["steps"]}
        for s in t["steps"]:
            if s["state"] != "done":
                continue
            kind = s["kind"]
            steps[kind] = steps.get(kind, 0) + 1
            raw = _count((s.get("brief_meta") or {}).get("raw_w"))
            raw = raw if raw is not None else note_words(read_note(home, t, s["n"]))
            if raw:
                wrote.setdefault(kind, []).append(raw)
            prev = by_n.get(s["n"] - 1)
            if prev is not None:
                sent = _count((prev.get("brief_meta") or {}).get("sent_w"))
                sent = sent if sent is not None else _words(read_brief(home, t, prev["n"]))
                if sent:
                    got.setdefault(kind, []).append(sent)
            tokens = _count(s.get("ctx_tokens"))
            if tokens:
                ctx.setdefault(kind, []).append(tokens)
    rows = [{"kind": k, "steps": steps[k], "received": _median(got.get(k)), "context": _median(ctx.get(k)),
             "handoff": _median(wrote.get(k))} for k in KINDS if k in steps]
    both = [r for r in rows if r["received"] and r["context"]]
    hot = max(both, key=lambda r: r["context"] / r["received"])["kind"] if both else ""
    return {"project": project, "tasks": len(mine), "kinds": rows, "hot": hot}
```

Notes for the executor:
- `measure` reads task.json from disk (`load_all`), not the hub's memory: the service saves every transition, and the
  route runs only when the Board shows the table (once a minute at most, Task 6).
- With plan 24 placed, `KINDS` holds `replan`: its rows come out by themselves (a replan step has a brief and no
  session context: `context` stays None).
- With plan 23 placed, `brief_meta.raw_w` / `sent_w` are the figures; the file word counts are the fallback for task
  folders from before plan 23 (and for a cleared task, whose notes are gone: zero words are left out).

## 1.2 `Hub._ended` (`console/server.py`): the context a step reached

Anchor (today's code, unchanged by plans 24 and 23 at this spot):

```python
        if task["state"] == "waiting" and "asked" in cs and cs["asked"] == meta.get("started"):
            return ""  # no answer yet: the turn that asked is still the last one
        text, subtype = self.final_message(sid)
```

Insert one line before `text, subtype = ...`:

```python
        cs["ctx_tokens"] = s["ctx_tokens"]  # plan 25: the context the step reached (None: unknown, plan 5 3.6)
```

It runs for every turn that ended: a step that asked a question records its context and records it again when its
answered turn ends. `STEP_KEYS` does not grow (old task.json files load; everything reads it with `.get`).

## 1.3 Constants and `folds_ok` (`console/server.py`)

`import re` after `import os`. After `MAX_PROMPT = 20000`:

```python
BOARD_TABS = ("chat", "recv", "hand", "route", "plan")  # the Board's step inspector tabs (window.json board_tab)
FOLD_KEY = re.compile(r"[a-z][a-z0-9.]{0,39}")
FOLDS_MAX = 64
```

After `BUSY = {"running", "quiet", "stall"}` (before `class Hub`):

```python
def folds_ok(folds) -> bool:
    """window.json `folds`: {fold key: open} with at most FOLDS_MAX keys of the FOLD_KEY shape."""
    return (isinstance(folds, dict) and len(folds) <= FOLDS_MAX
            and all(isinstance(k, str) and FOLD_KEY.fullmatch(k) and isinstance(v, bool) for k, v in folds.items()))
```

## 1.4 Routes (`console/server.py`)

`Handler._config` (plan 26 Task 3 moved the `/api/config` dict there; `window` is its local
`paths.load_window(self.hub.folder)`). Its dict now ends with plan 26's line

```python
                "kind_rules": {k: {"rank": r[0], "effort": r[1], "tools": r[2]} for k, r in tasks.RULES.items()}}
```

(after plan 23's `handoff_auto`, plan 18's `tiers` and `kinds_tier`, plan 26's `kind_pins` and `tuning`: keep them
all). Replace that line with

```python
                "kind_rules": {k: {"rank": r[0], "effort": r[1], "tools": r[2]} for k, r in tasks.RULES.items()},
                "board_tab": window.get("board_tab", "chat"), "folds": window.get("folds") or {}}
```

`do_GET`, after the `/api/task` branch:

```python
        if url.path == "/api/measure":
            return self._measure(query)
```

`_draft`: read the two fields, check them after the effort check, and save them with the others:

```python
        effort, board_tab, folds = body.get("effort"), body.get("board_tab"), body.get("folds")
        ...
        if board_tab is not None and board_tab not in BOARD_TABS:
            return self._error(400, "bad board_tab")
        if folds is not None and not folds_ok(folds):
            return self._error(400, "bad folds")
        ...
        fields = {k: v for k, v in (("project", project), ("brief", brief), ("effort", effort),
                                    ("board_tab", board_tab), ("folds", folds)) if v is not None}
```

`_task`: before the `return self._json(...)` add (or reuse plan 23's dict, see Lands on)

```python
        briefs = {str(s["n"]): tasks.read_brief(self.hub.folder, task, s["n"]) for s in task["steps"]}
```

With plan 23 placed, write instead `texts = self._step_texts(task)` and `briefs = texts["briefs"]` there, and change
plan 23's `**self._step_texts(task),` in the answer to `**texts,` (one read of the files).

and add two keys at the end of the answer, after `"handoff"` (and after plan 23's and plan 24's keys):

```python
                           "questions": tasks.open_questions(task, briefs),
                           "chain": tasks.read_chain(self.hub.folder, task)})
```

New method after `_task`:

```python
    def _measure(self, query):
        """GET /api/measure?project=<folder>&n=10: the Board's measure table (tasks.measure)."""
        project, n = query.get("project", [""])[0], query.get("n", ["10"])[0]
        if not project or len(project) > 1000 or not n.isdigit():
            return self._error(400, "bad measure query")
        return self._json(tasks.measure(self.hub.folder, project, int(n)))
```

The GET passes `guard.host_ok` like every GET; it reads only the task folders under the data folder.

## 1.5 `console/window.py`: the Board size (ID-4)

After `OPEN_MAX_W, OPEN_MAX_H = 900, 1600`:

```python
BOARD_W, BOARD_H = 900, 680  # css px, the Board's first size (plan 25, ID-4); the grip on the Board replaces it
BOARD_MIN_W = 700  # under it the Board's two columns do not fit
```

After `clamp_size`:

```python
def clamp_board(w, h) -> tuple:
    """(w, h) for the Board: the open limits, but never narrower than BOARD_MIN_W; junk is the Board default."""
    try:
        w, h = int(w), int(h)
    except (TypeError, ValueError, OverflowError):
        return BOARD_W, BOARD_H
    return max(BOARD_MIN_W, min(w, OPEN_MAX_W)), max(OPEN_MIN_H, min(h, OPEN_MAX_H))
```

`WindowApi.__init__`, last line: `self._board = False  # the Board page is open: the window has the Board's size
(never kept across starts)`.

`form`: in the pill branch, `self._board = False` before the resize; in the open branch replace
`self._window.resize(*self.open_size())` with
`self._window.resize(*(self.board_size() if self._board else self.open_size()))`.

After `open_size`:

```python
    def _board_css(self) -> tuple:
        saved = paths.load_window(self._folder).get("board")
        return clamp_board(*saved) if isinstance(saved, list) and len(saved) == 2 else (BOARD_W, BOARD_H)

    def board_size(self) -> tuple:
        """The Board's remembered size in form px (window.json `board`, 900 x 680 the first time)."""
        w, h = self._board_css()
        return round(w * self._scale), round(h * self._scale)

    def board(self, on: bool):
        """The Board button (on) and the Board's Back or Esc (off): the open window takes the Board's size or its
        compact size again. Returns [w, h] in css px as applied, None unless the window is open."""
        if self._form != "open":
            return None
        self._board = bool(on)
        self._window.resize(*(self.board_size() if self._board else self.open_size()))
        return list(self._board_css() if self._board else self._css_size())
```

`resize`: replace its body after the form check with

```python
        w, h = clamp_board(w, h) if self._board else clamp_size(w, h)
        self._window.resize(round(w * self._scale), round(h * self._scale))
        if keep:  # on the Board the grip sets the Board's size, never the compact one
            paths.save_window(self._folder, **({"board": [w, h]} if self._board else {"size": [w, h]}))
        return [w, h]
```

`_restore` and `state` are unchanged: the window always starts compact; the page knows it is on the Board by its own
`page`.

## 1.6 Tests (write first; they fail before 1.1 to 1.5)

`tests/test_tasks.py`, at the end before `if __name__`:

```python
def brief(*questions):
    """A brief as compact.render writes it, with these Open questions."""
    qs = "\n".join(f"- {q}" for q in questions) or "- (none)"
    return f"## Findings\n- x\n## Files touched\n- a.py\n## Open questions\n{qs}\n## Next\nGo on"


class BoardTest(unittest.TestCase):
    """Plan 25 Task 1: open questions from the briefs, the chain log, the measure table."""

    def test_open_questions_open_and_close(self):
        task = make(("scout", "code", "document"))  # scout, code, verify, document
        briefs = {1: brief("Which exe is the real one?"), 2: brief("Which exe is the real one?", "Week or 7 days?"),
                  3: brief("Week or 7 days?")}
        self.assertEqual(tasks.open_questions(task, briefs), [
            {"q": "Which exe is the real one?", "opened": 1, "closed": 3},
            {"q": "Week or 7 days?", "opened": 2, "closed": 0}])

    def test_open_questions_ignore_none_spelling_and_missing_briefs(self):
        task = make(("scout", "code", "document"))
        briefs = {"1": brief(), "2": brief("Which  exe is the REAL one"), "3": "", "4": brief("which exe is the real one?")}
        self.assertEqual(tasks.open_questions(task, briefs), [{"q": "Which  exe is the REAL one", "opened": 2, "closed": 0}])
        self.assertEqual(tasks.open_questions(task, {}), [])
        self.assertEqual(tasks.section_items(brief("a", "b"), tasks.QUESTIONS_HEAD), ["a", "b"])

    def test_read_chain_skips_broken_lines(self):
        with tempfile.TemporaryDirectory() as home:
            task = make()
            self.assertEqual(tasks.read_chain(home, task), [])
            line = {"ts": 1.0, "step": 1, "from": "planned", "to": "running", "why": "", "session": "s1"}
            tasks.log(home, task["id"], [line, dict(line, step=2)])
            with open(tasks.folder(home, task["id"]) / "chain.jsonl", "a", encoding="utf-8") as fh:
                fh.write("{broken\n[1, 2]\n")
            tasks.log(home, task["id"], [dict(line, step=3)])
            self.assertEqual([r["step"] for r in tasks.read_chain(home, task)], [1, 2, 3])
            self.assertEqual([r["step"] for r in tasks.read_chain(home, task, limit=2)], [3])

    def done_task(self, home, project, created, ctx, meta=True):
        """scout, code, verify, all done; ctx = the three ctx_tokens; brief_meta words or files only."""
        task = make(("scout", "code"))
        task.update(project_dir=project, created=created)
        for s, tokens, (raw, sent) in zip(task["steps"], ctx, ((200, 160), (400, 300), (180, 0))):
            s.update(state="done", model="haiku", effort="low", session=f"s{s['n']}", ctx_tokens=tokens)
            if meta:
                s["brief_meta"] = {"raw_w": raw, "sent_w": sent, "cut": [], "checks": [], "by": "haiku",
                                   "cost": 0.004, "turns": 2, "fallback": ""}
            else:
                tasks.write_note(home, task, s, " ".join(["w"] * raw))
                tasks.write_brief(home, task, s, " ".join(["w"] * sent))
        tasks.save(home, task)
        return task

    def test_measure_medians_per_kind(self):
        with tempfile.TemporaryDirectory() as home:
            for k, ctx in enumerate(((30000, 90000, 50000), (40000, 110000, 70000), (50000, None, 60000))):
                self.done_task(home, "D:\\WORK\\APP", NOW + k, ctx)
            self.done_task(home, "D:\\WORK\\OTHER", NOW + 9, (1, 2, 3))  # another project
            planned = make(("scout",))
            planned.update(project_dir="D:\\WORK\\APP", created=NOW + 5)
            tasks.save(home, planned)  # its steps are planned: they add nothing but count as a task
            m = tasks.measure(home, "D:\\WORK\\APP", 10)
            self.assertEqual((m["project"], m["tasks"]), ("D:\\WORK\\APP", 4))
            self.assertEqual(m["kinds"], [
                {"kind": "scout", "steps": 3, "received": None, "context": 40000, "handoff": 200},
                {"kind": "code", "steps": 3, "received": 160, "context": 100000, "handoff": 400},
                {"kind": "verify", "steps": 3, "received": 300, "context": 60000, "handoff": 180}])
            self.assertEqual(m["hot"], "code")  # 100K from 160 words beats 60K from 300
            self.assertEqual(tasks.measure(home, "D:\\WORK\\APP", 1)["tasks"], 1)  # the newest only
            self.assertEqual(tasks.measure(home, "D:\\WORK\\NONE", 10), {"project": "D:\\WORK\\NONE", "tasks": 0,
                                                                         "kinds": [], "hot": ""})

    def test_measure_reads_the_files_without_brief_meta(self):
        with tempfile.TemporaryDirectory() as home:
            self.done_task(home, "D:\\WORK\\APP", NOW, (None, None, None), meta=False)
            m = tasks.measure(home, "D:\\WORK\\APP")
            self.assertEqual([(r["kind"], r["received"], r["context"], r["handoff"]) for r in m["kinds"]],
                             [("scout", None, None, 200), ("code", 160, None, 400), ("verify", 300, None, 180)])
            self.assertEqual(m["hot"], "")  # no context reading: nothing to name
```

What they assert: `test_open_questions_open_and_close` a question opens at its first brief and closes at the first
brief without it (D2 a); `test_open_questions_ignore_none_spelling_and_missing_briefs` `(none)` is no question, case,
spaces and a trailing `?` do not make two questions, an empty brief is skipped, str keys work;
`test_read_chain_skips_broken_lines` broken lines and non-dicts are skipped, `limit` keeps the last lines;
`test_measure_medians_per_kind` the medians per kind in `KINDS` order, another project and planned steps ignored, the
`n` newest tasks, `hot` by context per received word (D3 a), an unknown project is an empty table;
`test_measure_reads_the_files_without_brief_meta` without `brief_meta` the note (minus its head line) and brief word
counts stand in, and no context means no `hot`.

`tests/test_server.py`: `from urllib.parse import quote` after `import unittest`. In `TaskServerTest`, before
`test_draft_keeps_the_effort`, `test_draft_keeps_board_tab_and_folds`; at the end of the class:

```python
    def test_draft_keeps_board_tab_and_folds(self):
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["board_tab"], cfg["folds"]), ("chat", {}))
        self.assertEqual(self.call("/api/draft", {"text": "", "board_tab": "hand", "folds": {"b.facts": True}})[0], 200)
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["board_tab"], cfg["folds"]), ("hand", {"b.facts": True}))
        for bad in ({"board_tab": "notes"}, {"folds": {"B.X": True}}, {"folds": {"b.x": "yes"}}, {"folds": [1]},
                    {"folds": {f"k{i}": True for i in range(65)}}):
            self.assertEqual(self.call("/api/draft", dict(bad, text=""))[0], 400, bad)

    # -- plan 25: the Board ---------------------------------------------------------------------------------
    def test_task_carries_questions_chain_and_ctx(self):
        tid = self.make_task()
        task = self.until(tid, self.at(2), "step 2 starts")
        self.assertIn("ctx_tokens", task["steps"][0])  # stored when step 1 ended (None: the fake reports none)
        tasks.write_brief(self.folder, task, task["steps"][0], "## Findings\n- x\n## Open questions\n- Week or 7 days?\n## Next\ngo")
        data = self.task(tid)[1]
        self.assertEqual(data["questions"], [{"q": "Week or 7 days?", "opened": 1, "closed": 0}])
        moves = [(c["step"], c["from"], c["to"]) for c in data["chain"]]
        self.assertIn((1, "running", "done"), moves)
        self.assertEqual(data["chain"], self.chain(tid)[-200:])

    def test_measure_route(self):
        self.assertEqual(self.call("/api/measure")[0], 400)
        self.assertEqual(self.call("/api/measure?project=x&n=ten")[0], 400)
        tid = self.make_task()
        self.until(tid, self.at(2), "step 2 starts")
        status, data = self.call(f"/api/measure?project={quote(str(self.project))}&n=10")
        self.assertEqual(status, 200)
        self.assertEqual((data["tasks"], [r["kind"] for r in data["kinds"]]), (1, ["scout"]))
        self.assertEqual(self.call(f"/api/measure?project={quote(str(self.project))}&n=0")[1]["tasks"], 1)  # n >= 1
```

`tests/test_window.py`, in `WindowApiTest` before `test_hwnd_is_only_this_process_window`:

```python
    def test_board_opens_at_its_size_and_returns(self):
        self.assertEqual(window.clamp_board(10, 10), (window.BOARD_MIN_W, window.OPEN_MIN_H))
        self.assertEqual(window.clamp_board("x", 1), (window.BOARD_W, window.BOARD_H))
        self.api.form("open")
        self.api.resize(360, 900, True)  # the compact size Fred set
        self.assertEqual(self.api.board(True), [900, 680])  # the first time: 900 x 680
        self.assertEqual(self.win.calls[-1], ("resize", 900, 680))
        self.api.fit(900)  # a text-size check while the Board is open keeps the Board's size
        self.assertEqual(self.api.resize(820, 640, True), [820, 640])  # the grip on the Board
        self.assertEqual(self.api.resize(500, 640, False), [window.BOARD_MIN_W, 640])  # never under 700
        self.assertEqual(paths.load_window(self.folder)["size"], [360, 900])  # the compact size is untouched
        self.assertEqual(self.api.board(False), [360, 900])
        self.assertEqual(self.win.calls[-1], ("resize", 360, 900))
        self.assertEqual(self.api.board(True), [820, 640])  # the Board's size is kept in window.json
        self.assertEqual(paths.load_window(self.folder)["board"], [820, 640])

    def test_board_needs_the_open_window(self):
        self.api.form("pill")
        self.assertIsNone(self.api.board(True))
        self.api.form("open")
        self.api.board(True)
        self.api.form("pill")  # folding leaves the Board: unfolding opens the compact size
        self.assertEqual(self.api.form("open"), "open")
        self.assertEqual(self.win.calls[-1], ("resize", window.OPEN_W, window.OPEN_H))
        self.assertEqual(window.WindowApi(self.folder)._board, False)  # never kept across starts
```

## 1.7 Steps

1. Write the tests of 1.6; run them: they fail (`AttributeError` on `tasks.open_questions`, `window.clamp_board`; 404
   on `/api/measure`; no `board_tab` in `/api/config`).
2. `console/tasks.py` (1.1); `py -m unittest tests.test_tasks -q`.
3. `console/server.py` (1.2 to 1.4); `py -m unittest tests.test_server -q`.
4. `console/window.py` (1.5); `py -m unittest tests.test_window -q`.
5. The full suite. Commit `plan 25 task 1: open questions, chain log, measure, ctx per step, the Board size (N tests OK)`.

Expected count: the count before this task plus 10: 5 in `tests/test_tasks.py` (`BoardTest`), 3 in
`tests/test_server.py` (`TaskServerTest`, the draft one included), 2 in `tests/test_window.py`.

## 1.8 Drift guards

- `open_questions` and `measure` are pure readers: they never write a file and never call a model.
- The measure counts done steps only; a running, failed or planned step adds nothing; a value of 0 or None is left out
  (never a false zero, D-3).
- `ctx_tokens` is stored from the session row as it is; no estimate from characters (ID-3 keeps unknown unknown).
- `WindowApi.board` never writes `size`; `resize` on the Board never writes `size`; nothing writes `_board` to disk.
- `/api/draft` keeps refusing what it refused before; the two new fields are optional.
