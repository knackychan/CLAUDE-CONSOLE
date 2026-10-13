# Plan 22: lessons, miss decay and the rules review

> Context: [../PLAN.md](../PLAN.md), [../CLAUDE.md](../CLAUDE.md), [17-tasks/README.md](17-tasks/README.md)
> (sections 3.5 and 3.6), [04-polish.md](04-polish.md) (rules-size warning, routing-misses.md).
> Source of the ideas: github.com/kju4q/q-agent-harness (`COMPACTION.md`, `VERIFICATION.md`,
> `memory/hot/MAINTENANCE.md`, `docs/task-setups.md`), read on 2026-10-13. Nothing is copied from it:
> the shapes below are the console's own.

**Goal:** the console records what each task taught, stops treating an old routing miss as a rule, and can
ask Haiku to review a project's rules against those records. It proposes; it never edits a project file.

**Architecture:** one more one-line file in `~/.claude/console/` (`lessons.md`, the shape of
`routing-misses.md`), written by the step chain (an optional `Lesson:` line in the HANDOFF block) and by
the `session-handoff` skill. `routing.fresh` drops miss lines older than `miss_floor_days` before Prep and
the step router read them. A Review job runs like a Prep job (same strip, same drop route, same `claude -p`
flags: Read / Grep / Glob, no hooks) from `console/review.py` and `console/review_prompt.md`; its card lists
proposals with a Copy button each. The fix text gets a three-hypotheses frame; the verifier gets two lines.

**Tech stack:** Python 3.14 standard library, the existing fake claude in tests, plain JS.

## Decisions taken while writing (zero-decision plan, 2026-10-13)

- Proposals only. The console writes `~/.claude/console/` only (CLAUDE.md rule), and `session-handoff`
  never edits CLAUDE.md: the Review card shows each proposal with Copy; Fred pastes what he agrees with.
  No approve-and-write flow, no edits to `routing-misses.md`.
- One lessons file for every project, lines tagged with the project folder name, like the misses file.
- A lesson rides inside the HANDOFF block as a `Lesson:` line (like `Next model:`): the four headings and
  `check_handoff` do not change, and an old step without one still passes.
- Decay by date only: a miss older than `miss_floor_days` (14) is neither a floor nor shown to Prep. The
  file keeps every line (history for the Review).
- Review kinds: remove, demote, rule, procedure, keep. At most 6 proposals. Haiku, read only, timeout 180 s.
- Where Review starts: the `rules:` note on a session page (a `Review` link) and a `Review rules` button
  on the Prep card. The result opens in the Prep page section (`#pscroll`, `#pbar`) under a Review crumb.
- The golden Prep check is a script Fred runs (`tests/golden_prep.py`, three real Prep calls, about $0.09),
  not a unit test: the unit suite never calls a model.

## File map

| File | Change |
|---|---|
| `console/paths.py` | `miss_floor_days`, `review_model`, `review_timeout_s` in `DEFAULTS` |
| `console/levers.py` | `lesson_line`, `add_lesson`, `read_lessons`; `_append` / `_read` shared with the misses; `FIX_FRAME` in `escalate_text` |
| `console/routing.py` | `fresh(misses, days, now)` |
| `console/prep.py` | Prep reads fresh misses; `build_prompt(raw, misses, days)` |
| `console/prep_prompt.md` | the misses heading names the window |
| `console/tasks.py` | `lesson_of(block)` |
| `console/step_prompt.md` | the `Lesson:` line |
| `console/review.py`, `console/review_prompt.md` | new |
| `console/server.py` | fresh misses for steps, the lesson written at a step's end, `start_review`, `_review_job`, `_end_job`, `POST /api/review` |
| `web/app.js` | review jobs on the strip, `showReview`, the two entry points, Copy |
| `dotclaude/skills/session-handoff/SKILL.md` | step 4 writes the lesson line |
| `dotclaude/skills/route-model/SKILL.md` | step 2 ignores a miss older than 14 days |
| `dotclaude/agents/verifier.md` | two Never lines |
| `tests/fake_claude.py` | the review answer; `LESSON` in a step reply |
| `tests/test_levers.py`, `test_routing.py`, `test_tasks.py`, `test_review.py` (new), `test_server.py`, `test_dotclaude.py` | tests |
| `tests/golden_prep.py` | new, Fred's script |
| `PLAN.md` | row 22, History line |

Every task: tests first, run them, place the code, run `py -m unittest discover -s tests`, commit. The
count before this plan: 312 (PLAN History 2026-10-13). Commit with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

### Task 1: the lessons file and miss decay (`levers.py`, `routing.py`, `paths.py`)

**Files:** modify `console/paths.py`, `console/levers.py`, `console/routing.py`; test `tests/test_levers.py`, `tests/test_routing.py`.

- [ ] **Step 1: tests**

Append to `tests/test_levers.py` inside `LeversTest`:

```python
    def test_lessons_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = time.mktime((2026, 10, 13, 12, 0, 0, 0, 0, -1))
            line = levers.lesson_line("CALC", "code", "  profile before\noptimizing token=abc  ", now)
            self.assertEqual(line, "- 2026-10-13 - CALC - code: profile before optimizing token=***")
            levers.add_lesson(Path(tmp), line)
            levers.add_lesson(Path(tmp), levers.lesson_line("OTHER", "", "x", now))
            self.assertEqual(levers.read_lessons(Path(tmp), "CALC"), [line])
            self.assertEqual(levers.read_lessons(Path(tmp), "OTHER"), ["- 2026-10-13 - OTHER - chat: x"])
            text = (Path(tmp) / "lessons.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Lessons"))
            self.assertEqual(levers.read_lessons(Path(tmp) / "nope", "CALC"), [])
            self.assertEqual(levers.read_misses(Path(tmp), "CALC"), [])  # the two files stay apart
            self.assertLessEqual(len(levers.lesson_line("P", "code", "w" * 500, now)), 240)

    def test_escalate_text_frames_the_fix(self):
        text = levers.escalate_text("test_x - KeyError", "sonnet", "high")
        self.assertTrue(text.startswith("The checks failed: test_x - KeyError. You now run on sonnet/high (escalated once). "))
        self.assertIn(levers.FIX_FRAME, text)
        self.assertIn("three plausible causes", levers.FIX_FRAME)
        self.assertIn("smallest check", levers.FIX_FRAME)
        self.assertTrue(text.endswith("`VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`."))
        self.assertIn("see the last VERDICT line", levers.escalate_text("", "opus", "high"))
```

Append to `tests/test_routing.py` inside `RoutingTest`:

```python
    def test_fresh_drops_misses_older_than_the_window(self):
        import time
        now = time.mktime((2026, 10, 13, 12, 0, 0, 0, 0, -1))
        old = "- 2026-09-20 - APP - code: sonnet/medium failed (x); next time start at opus/high."
        edge = "- 2026-09-29 - APP - code: sonnet/medium failed (x); next time start at sonnet/high."
        new = "- 2026-10-12 - APP - debug: sonnet/high failed (y); next time start at opus/high."
        undated = "misc line"
        self.assertEqual(routing.fresh([old, edge, new, undated], 14, now), [edge, new, undated])
        self.assertEqual(routing.fresh([old, new], 0, now), [old, new])  # 0 = no decay
        self.assertIsNone(routing.floor(routing.fresh([old], 14, now), "code"))
        self.assertEqual(routing.floors(routing.fresh([old, new], 14, now)), {"debug": {"route": "opus/high", "date": "2026-10-12"}})
```

- [ ] **Step 2: run, expect failures**

Run: `py -m unittest tests.test_levers tests.test_routing -v`
Expected: `AttributeError: module 'console.levers' has no attribute 'lesson_line'`, `... 'routing' has no attribute 'fresh'`.

- [ ] **Step 3: `console/paths.py`**

After the line `"delegate_after_reads": 10,` insert:

```python
    "miss_floor_days": 14,  # plan 22: an older routing miss is history, not a floor
    "review_model": "haiku",  # plan 22: the rules review, read only
    "review_timeout_s": 180,
```

- [ ] **Step 4: `console/levers.py`**

Replace the module docstring's first line with:

```python
"""Phase 3 levers: the texts Verify, Handoff and Escalate send, the escalation step, the order after
Verify, the routing-misses file and (plan 22) the lessons file. When a lever is allowed is decided in one
place: server.Hub.levers."""
```

After `MISSES_SHOWN = 20` add:

```python
LESSONS_FILE = "lessons.md"
LESSONS_HEAD = ("# Lessons\n\nOne line per lesson: a step's `Lesson:` line (written by Claude Console) or a "
                "chat's (written by session-handoff). The rules review reads the lines of its project.\n\n")
LESSONS_SHOWN = 40
FIX_FRAME = ("Before you edit: name up to three plausible causes, the evidence for and against each, and the "
             "smallest check that tells them apart; run that check; fix only the cause it confirmed.")
```

Replace `escalate_text`:

```python
def escalate_text(detail: str, model: str, effort: str) -> str:
    failed = detail or "see the last VERDICT line"
    return (f"The checks failed: {failed}. You now run on {model}/{effort} (escalated once). {FIX_FRAME} "
            "Then run the checks again and end your final message with one line: "
            "`VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>`.")
```

Replace `miss_line`, `add_miss` and `read_misses` (from `def miss_line` to the end of the file) with:

```python
def _day(now: float = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))


def miss_line(project: str, task_type: str, route_from: str, route_to: str, detail: str,
              now: float = None) -> str:
    why = redact.clip(redact.mask(detail), 120) or "verifier FAIL"
    return (f"- {_day(now)} - {project} - {task_type or 'unrouted'}: {route_from} failed ({why}); "
            f"next time start at {route_to}.")


def lesson_line(project: str, kind: str, text: str, now: float = None) -> str:
    """One lesson: `- <day> - <project> - <step kind or chat>: <one sentence>` (masked, clipped at 200)."""
    what = redact.clip(redact.mask(" ".join(str(text or "").split())), 200)
    return f"- {_day(now)} - {project} - {kind or 'chat'}: {what}"


def _append(folder: Path, name: str, head: str, line: str) -> None:
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    lead = "" if path.exists() and path.stat().st_size else head  # decided before the open creates the file
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(lead + line + "\n")


def _read(folder: Path, name: str, project: str, limit: int) -> list:
    """The last `limit` lines of one project (matched by the project folder's name)."""
    try:
        lines = (Path(folder) / name).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    tag = f" - {project} - "
    return [line for line in lines if line.startswith("- ") and tag in line][-limit:]


def add_miss(folder: Path, line: str) -> None:
    _append(folder, MISSES_FILE, MISSES_HEAD, line)


def read_misses(folder: Path, project: str, limit: int = MISSES_SHOWN) -> list:
    return _read(folder, MISSES_FILE, project, limit)


def add_lesson(folder: Path, line: str) -> None:
    _append(folder, LESSONS_FILE, LESSONS_HEAD, line)


def read_lessons(folder: Path, project: str, limit: int = LESSONS_SHOWN) -> list:
    return _read(folder, LESSONS_FILE, project, limit)
```

Note on `_append`: the old `add_miss` wrote the head when the file did not exist; `lead` keeps that and also
heads an empty file.

- [ ] **Step 5: `console/routing.py`**

Change the imports to:

```python
import re
import time

from .claude_cli import EFFORTS, MODELS
```

After `def floors(misses) -> dict:` ... (after the function) and before `def pick`, add:

```python
def fresh(misses, days: float, now: float = None) -> list:
    """The miss lines dated within `days` of `now`, plus undated ones; `days` 0 keeps every line. An older
    miss is history for the rules review, not a floor (plan 22)."""
    if not days:
        return list(misses)
    cutoff = time.strftime("%Y-%m-%d", time.localtime((now or time.time()) - days * 86400))
    out = []
    for line in misses:
        d = _DATE.match(line)
        if not d or d.group(1) >= cutoff:
            out.append(line)
    return out
```

Add to the module docstring's last sentence: `... (Escalate wrote it: that route failed last time; a miss older than miss_floor_days is dropped by fresh())`.

- [ ] **Step 6: run**

Run: `py -m unittest tests.test_levers tests.test_routing -v`
Expected: all OK, including the old `test_misses_file_round_trip` (the head is still written on first use).

- [ ] **Step 7: commit**

```bash
git add console/paths.py console/levers.py console/routing.py tests/test_levers.py tests/test_routing.py
git commit -m "feat: lessons file, miss decay by date, the fix frame (plan 22 Task 1)"
```

---

### Task 2: Prep and the step router read fresh misses (`prep.py`, `prep_prompt.md`, `server.py`)

**Files:** modify `console/prep.py`, `console/prep_prompt.md`, `console/server.py:463-470`; test `tests/test_prep.py`, `tests/test_server.py`.

- [ ] **Step 1: tests**

Append to `tests/test_prep.py` inside `PrepTest`:

```python
    def test_build_prompt_names_the_miss_window(self):
        self.assertIn("Routing misses in this project in the last 14 days (Escalate wrote them; newest last):\n(none)",
                      prep.build_prompt("x", days=14))
        self.assertIn("Routing misses in this project (Escalate wrote them; newest last):", prep.build_prompt("x"))

    def test_run_prep_reads_only_fresh_misses(self):
        from console import levers, routing
        with tempfile.TemporaryDirectory() as tmp:
            folder, project = Path(tmp) / "home", Path(tmp) / "proj"
            project.mkdir()
            old = "- 2020-01-01 - proj - mechanical: sonnet/low failed (x); next time start at opus/high."
            levers.add_miss(folder, old)
            cfg = dict(copy.deepcopy(paths.DEFAULTS), miss_floor_days=14)
            card = prep.run_prep(cfg, folder, str(project), "fix add", FAKE)
            self.assertEqual((card["route"]["model"], card["route"]["effort"]), ("sonnet", "low"))  # no floor
            self.assertEqual(card["floors"], {})
            card = prep.run_prep(dict(cfg, miss_floor_days=0), folder, str(project), "fix add", FAKE)
            self.assertEqual(card["floors"], {"mechanical": {"route": "opus/high", "date": "2020-01-01"}})
            self.assertEqual((card["route"]["model"], card["route"]["effort"]), ("opus", "high"))
```

Check the top of `tests/test_prep.py` imports `copy`, `tempfile`, `Path`, `paths`, `FAKE` (it does: see its header).

Append to `tests/test_server.py` inside `TaskServerTest` (after `test_pinned_step_beats_the_miss_floor`):

```python
    def test_old_miss_is_no_floor_for_a_step(self):
        old = "- 2020-01-01 - proj - code: sonnet/medium failed (x); next time start at opus/high."
        levers.add_miss(self.folder, old)
        card = self.prep_card()
        self.assertEqual(card["floors"], {})
        task = self.until(self.make_task(), self.at(2), "the code step starts")
        self.assertEqual((task["steps"][1]["model"], task["steps"][1]["effort"]), ("sonnet", "medium"))
        self.assertFalse(any(n.startswith("floor") for n in task["steps"][1]["notes"]))
```

- [ ] **Step 2: run, expect failures**

Run: `py -m unittest tests.test_prep tests.test_server.TaskServerTest.test_old_miss_is_no_floor_for_a_step -v`
Expected: the window test fails on the heading text; the fresh tests fail with `opus/high` floors.

- [ ] **Step 3: `console/prep_prompt.md`**

Replace the line `Routing misses in this project (Escalate wrote them; newest last):` with:

```
Routing misses in this project $window(Escalate wrote them; newest last):
```

- [ ] **Step 4: `console/prep.py`**

Replace `build_prompt`:

```python
def build_prompt(raw: str, misses=(), days: float = 0) -> str:
    """The Prep instructions with Fred's request and this project's routing misses filled in; `days` names
    the window the misses were kept from (0: not named)."""
    window = f"in the last {days:g} days " if days else ""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        raw=raw.strip(), misses="\n".join(misses) or "(none)", window=window)
```

In `run_prep` replace the two lines

```python
    misses = levers.read_misses(folder, Path(project_dir).name)
    prompt = build_prompt(raw, misses)
```

with

```python
    days = cfg.get("miss_floor_days", 0)
    misses = routing.fresh(levers.read_misses(folder, Path(project_dir).name), days)
    prompt = build_prompt(raw, misses, days)
```

- [ ] **Step 5: `console/server.py` `_route_for`**

Replace `misses=levers.read_misses(self.folder, task["project"]),` with:

```python
            misses=routing.fresh(levers.read_misses(self.folder, task["project"]), self.cfg["miss_floor_days"]),
```

- [ ] **Step 6: run**

Run: `py -m unittest tests.test_prep tests.test_server tests.test_levers -v`
Expected: OK. `test_levers.test_misses_file_round_trip` still finds the miss line in `prep.build_prompt("x", [line])` and `"\n(none)\n"` in `prep.build_prompt("x")`.

- [ ] **Step 7: commit**

```bash
git add console/prep.py console/prep_prompt.md console/server.py tests/test_prep.py tests/test_server.py
git commit -m "feat: Prep and the step router ignore a routing miss older than miss_floor_days (plan 22 Task 2)"
```

---

### Task 3: a step's `Lesson:` line (`tasks.py`, `step_prompt.md`, `server.py`, fake claude)

**Files:** modify `console/tasks.py`, `console/step_prompt.md`, `console/server.py:655-705`, `tests/fake_claude.py`; test `tests/test_tasks.py`, `tests/test_server.py`.

- [ ] **Step 1: tests**

Append to `tests/test_tasks.py`, in the class that holds `test_next_hint` (the handoff tests):

```python
    def test_lesson_of(self):
        self.assertEqual(tasks.lesson_of(GOOD + "\nLesson: profile before optimizing."), "profile before optimizing.")
        self.assertEqual(tasks.lesson_of(GOOD + "\n**Lesson:** keep the first one\nLesson: the last one wins"), "the last one wins")
        for none in ("", GOOD, GOOD + "\nLesson: none", GOOD + "\nLesson: -", GOOD + "\nLesson: N/A."):
            self.assertEqual(tasks.lesson_of(none), "", none)
        self.assertEqual(tasks.lesson_of("a lesson: not a line start"), "")
```

In `test_step_prompt_text` add after `self.assertIn("END HANDOFF", code)`:

```python
        self.assertIn("`Lesson: <one sentence>`", code)
        self.assertIn("most steps have none", code)
```

In the same file, in `test_verify_fail_inserts_fix_and_verify_once` (line 423 area), after the line that builds
`before = tasks.step_prompt(task, fix, "PREV")` add:

```python
        self.assertIn(levers.FIX_FRAME, before)  # a fix step names its hypotheses before it edits
```

Append to `tests/test_server.py` inside `TaskServerTest`:

```python
    def test_a_step_lesson_lands_in_lessons_md(self):
        tid = self.make_task(words="HANDOFF-OK LESSON", steps=[{"kind": "scout", "goal": "look"}])  # no edit: no verify
        self.settled(tid)
        lines = levers.read_lessons(self.folder, "proj")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].endswith(" - proj - scout: fake claude teaches one thing"), lines[0])
        self.assertEqual(levers.read_lessons(self.folder, "other"), [])
        tid = self.make_task(words="HANDOFF-OK", steps=[{"kind": "scout", "goal": "look"}])
        self.settled(tid)
        self.assertEqual(len(levers.read_lessons(self.folder, "proj")), 1)  # no Lesson line: nothing added
```

- [ ] **Step 2: run, expect failures**

Run: `py -m unittest tests.test_tasks -v 2>&1 | tail -5`
Expected: `AttributeError: module 'console.tasks' has no attribute 'lesson_of'` and the prompt assertion fails.

- [ ] **Step 3: `console/tasks.py`**

After `reply_question` add:

```python
_LESSON = re.compile(r"^[\s`*>\-]*Lesson:\**\s*(.+?)[\s`*]*$", re.M)


def lesson_of(block: str) -> str:
    """The last `Lesson: <one sentence>` line of a handoff block (plan 22); "" for none or `Lesson: none`."""
    found = _LESSON.findall(str(block or ""))
    text = found[-1].strip() if found else ""
    return "" if text.rstrip(".").lower() in _NO_QUESTION else text
```

(`_NO_QUESTION` is defined above `reply_question`; keep `lesson_of` below it.)

- [ ] **Step 4: `console/step_prompt.md`**

Replace the `## Next` paragraph of the template with:

```
## Next
One line for the next step. Add `Next model: <haiku|sonnet|opus>/<low|medium|high>` only when the next step
needs more than planned. Add `Lesson: <one sentence>` only when something transferable surprised you, what you
would tell someone starting this kind of step tomorrow; most steps have none, so leave the line out rather than pad.
END HANDOFF
```

- [ ] **Step 5: `console/server.py` `_ended`**

Replace

```python
        if action in ("next", "fix", "done"):
            tasks.write_note(self.folder, task, cs, block)
```

with

```python
        if action in ("next", "fix", "done"):
            tasks.write_note(self.folder, task, cs, block)
            lesson = tasks.lesson_of(block)
            if lesson:  # plan 22: one line per step that taught something, read by the rules review
                levers.add_lesson(self.folder, levers.lesson_line(task["project"], cs["kind"], lesson, now))
```

- [ ] **Step 6: `tests/fake_claude.py`**

In `reply`, after the `HINT-OPUS` branch inside `if "HANDOFF-OK" in text:` add:

```python
        if "LESSON" in text:  # the step's Lesson line, inside the block's Next
            block = block.replace("\nGo on\n", "\nGo on\nLesson: fake claude teaches one thing\n")
```

Add to the docstring, under the HINT-OPUS line: `"LESSON" with it: the block's Next carries a `Lesson:` line (plan 22).`

- [ ] **Step 7: run**

Run: `py -m unittest tests.test_tasks tests.test_server -v 2>&1 | tail -5`
Expected: OK.

- [ ] **Step 8: commit**

```bash
git add console/tasks.py console/step_prompt.md console/server.py tests/fake_claude.py tests/test_tasks.py tests/test_server.py
git commit -m "feat: a step's Lesson: line is kept in lessons.md (plan 22 Task 3)"
```

---

### Task 4: the Review job (`review.py`, `review_prompt.md`, `server.py`)

**Files:** create `console/review.py`, `console/review_prompt.md`, `tests/test_review.py`; modify `console/server.py`, `tests/fake_claude.py`; test `tests/test_server.py`.

- [ ] **Step 1: tests**

Create `tests/test_review.py`:

```python
import json
import unittest

from console import review


PROPOSAL = {"kind": "remove", "target": "Always write tests first", "text": "",
            "why": "derivable: the Commands section already names the test command", "sources": ["Always write tests first"]}


class ReviewTest(unittest.TestCase):
    def test_schema_shape(self):
        self.assertEqual(set(review.SCHEMA["required"]), {"proposals", "summary"})
        item = review.SCHEMA["properties"]["proposals"]["items"]
        self.assertEqual(set(item["required"]), {"kind", "target", "text", "why", "sources"})
        self.assertEqual(item["properties"]["kind"]["enum"], review.KINDS)
        self.assertEqual(review.KINDS, ["remove", "demote", "rule", "procedure", "keep"])

    def test_build_prompt(self):
        text = review.build_prompt(["- m1"], ["- l1", "- l2"], 14)
        self.assertIn("in the last 14 days ", text)
        self.assertTrue(text.rstrip().endswith("Lessons in this project (newest last):\n- l1\n- l2"))
        self.assertIn("\n- m1\n", text)
        self.assertIn("at most 6 items", text)
        for kind in review.KINDS:
            self.assertIn(f"- {kind}:", text)
        self.assertIn("(none)", review.build_prompt())
        self.assertNotIn("$", review.build_prompt(["$HOME"]).replace("$HOME", ""))

    def test_parse_output(self):
        good = json.dumps({"is_error": False, "structured_output": {"proposals": [PROPOSAL], "summary": "fine"},
                           "total_cost_usd": 0.02, "num_turns": 4})
        out = review.parse_output(good)
        self.assertEqual((out["proposals"], out["summary"], out["cost"], out["turns"]), ([PROPOSAL], "fine", 0.02, 4))
        many = json.dumps({"structured_output": {"proposals": [PROPOSAL] * 9, "summary": ""}})
        self.assertEqual(len(review.parse_output(many)["proposals"]), review.MAX_PROPOSALS)
        for bad in ("nope", json.dumps({"is_error": True, "subtype": "error_max_turns", "errors": ["turns"]}),
                    json.dumps({"result": "x"}), json.dumps({"structured_output": {"proposals": "x", "summary": ""}})):
            with self.assertRaises(review.ReviewError, msg=bad):
                review.parse_output(bad)
        with self.assertRaises(review.ReviewError) as ctx:
            review.parse_output(json.dumps({"is_error": True, "subtype": "error_max_turns", "errors": ["turns"]}))
        self.assertIn("error_max_turns", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
```

Append to `tests/test_server.py` inside `RunServerTest` (after `test_prep_job_never_spins_forever`):

```python
    def test_review_job_on_the_strip(self):
        levers.add_lesson(self.folder, levers.lesson_line("proj", "code", "profile first"))
        levers.add_miss(self.folder, levers.miss_line("proj", "code", "sonnet/medium", "sonnet/high", "x"))
        status, data = self.call("/api/review", {"project_dir": str(self.project)})
        self.assertEqual(status, 200, data)
        running = next(j for j in self.hub.snapshot()["preps"] if j["id"] == data["job"])
        self.assertEqual((running["kind"], running["state"], running["raw"]), ("review", "running", "Review rules"))
        row = self.prep_job(data["job"])
        self.assertEqual(row["state"], "done", row.get("error"))
        card = row["card"]
        self.assertEqual((card["id"], card["project_dir"], card["model"]), (data["job"], str(self.project), "haiku"))
        self.assertEqual((card["misses"], card["lessons"]), (1, 1))
        self.assertEqual(card["proposals"][0]["kind"], "remove")
        self.assertEqual(card["summary"], "CLAUDE.md is 12 lines, fine.")
        self.assertTrue((self.folder / "reviews" / f"{card['id']}.json").is_file())
        self.assertEqual(self.call("/api/prep/drop", {"job": data["job"]}), (200, {"job": data["job"]}))
        self.assertEqual(self.call("/api/review", {"project_dir": self.tmp.name})[0], 403)
```

- [ ] **Step 2: run, expect failures**

Run: `py -m unittest tests.test_review tests.test_server.RunServerTest.test_review_job_on_the_strip -v 2>&1 | tail -5`
Expected: `ModuleNotFoundError: No module named 'console.review'`; the server test gets 404 on `/api/review`.

- [ ] **Step 3: `console/review_prompt.md`**

```
You review the rules an agent loads on every request in the project in the current folder. Read CLAUDE.md at
the root if it exists, then every .claude/rules/*.md (at most 8 tool calls, Read / Grep / Glob only). Then read
the routing misses and the lessons below. Propose changes; write nothing. Answer with the JSON object only.

Judge each rule against five faults: stale (describes how the system used to work), redundant (said twice),
derivable (one grep finds it), too specific (one kind of task only: a procedure, not a rule), unenforceable
(nothing to act on). Every rule costs context on every request, so be strict.

Propose at most $max items. Each has exactly one kind:
- remove: a rule to delete. target: the rule's first words. text: "". why: its fault and one sentence.
- demote: a rule that belongs in a skill or a procedure. target: the rule. text: the procedure in one line.
- rule: a new one-sentence rule for every task, drawn from lessons or misses that repeat. target: "".
  text: the line, starting with "- ".
- procedure: numbered steps for one kind of task, drawn from lessons that repeat. target: the task kind.
  text: the steps, under 120 words, with a "Done when" line.
- keep: nothing to change. Use it alone, once, when the rules are fine. target and text: "".

Rules: a lesson or a miss seen once is noise; a rule or a procedure needs two or more that agree. Propose
nothing rather than pad: an empty list is a common answer. `sources`: the lesson lines, miss lines or rule
text a proposal rests on. `summary`: one sentence on the rules' size and health. Plain words, no em dashes,
no hype. The JSON object has exactly two keys, always present: proposals (a list, [] when empty), summary.

Routing misses in this project $window(Escalate wrote them; newest last):
$misses

Lessons in this project (newest last):
$lessons
```

- [ ] **Step 4: `console/review.py`**

```python
"""The rules review (plan 22): a read-only Haiku pass over a project's CLAUDE.md and rules files, with the
console's routing misses and lessons, proposes what to remove, demote or add. It proposes only: nothing is
written anywhere but reviews/<id>.json; Fred copies a line he agrees with."""
import json
import secrets
import subprocess
import time
from pathlib import Path
from string import Template

from . import claude_cli, levers, redact, routing

PROMPT_FILE = Path(__file__).resolve().parent / "review_prompt.md"
KINDS = ["remove", "demote", "rule", "procedure", "keep"]
MAX_PROPOSALS = 6
_TEXT = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": KINDS}, "target": _TEXT, "text": _TEXT, "why": _TEXT,
            "sources": {"type": "array", "items": _TEXT},
        }, "required": ["kind", "target", "text", "why", "sources"]}},
        "summary": _TEXT,
    },
    "required": ["proposals", "summary"],
}


class ReviewError(Exception):
    pass


def build_prompt(misses=(), lessons=(), days: float = 0) -> str:
    window = f"in the last {days:g} days " if days else ""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        max=MAX_PROPOSALS, window=window, misses="\n".join(misses) or "(none)",
        lessons="\n".join(lessons) or "(none)")


def parse_output(stdout: str) -> dict:
    """{"proposals", "summary", "cost", "turns"} from `claude -p --output-format json --json-schema`."""
    try:
        data = json.loads(stdout)
    except ValueError:
        raise ReviewError("Review returned no JSON: " + redact.clip(stdout, 200))
    if not isinstance(data, dict):
        raise ReviewError("Review returned no JSON object")
    if data.get("is_error"):
        errors = data.get("errors")
        parts = [data.get("subtype"), data.get("terminal_reason"), data.get("result")]
        parts += errors if isinstance(errors, list) else [errors]
        detail = "; ".join(str(p) for p in dict.fromkeys(parts) if p)
        raise ReviewError("Review failed: " + redact.clip(detail or "no reason given", 300))
    fields = data.get("structured_output")
    if not isinstance(fields, dict) or not isinstance(fields.get("proposals"), list):
        raise ReviewError("Review returned no structured output")
    proposals = []
    for p in fields["proposals"][:MAX_PROPOSALS]:
        if isinstance(p, dict) and p.get("kind") in KINDS:
            proposals.append({"kind": p["kind"], "target": str(p.get("target") or ""), "text": str(p.get("text") or ""),
                              "why": str(p.get("why") or ""),
                              "sources": [str(s) for s in p.get("sources") or [] if str(s).strip()]})
    return {"proposals": proposals, "summary": str(fields.get("summary") or ""),
            "cost": data.get("total_cost_usd") or 0, "turns": data.get("num_turns") or 0}


def new_id() -> str:
    return time.strftime("r%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def run_review(cfg: dict, folder: Path, project_dir: str, exe: list, job_id: str = "") -> dict:
    """Blocking (the service runs it in a job thread). Saves reviews/<id>.json and returns the card."""
    cmd = claude_cli.prep_command(exe, cfg["review_model"], SCHEMA)
    project = Path(project_dir).name
    misses = routing.fresh(levers.read_misses(folder, project), cfg["miss_floor_days"])
    lessons = levers.read_lessons(folder, project)
    prompt = build_prompt(misses, lessons, cfg["miss_floor_days"])
    try:
        out = subprocess.run(cmd, cwd=project_dir, input=prompt.encode("utf-8"), capture_output=True,
                             timeout=cfg["review_timeout_s"], env=claude_cli.child_env(),
                             creationflags=claude_cli.NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise ReviewError(f"Review took longer than {cfg['review_timeout_s']} s")
    except OSError as exc:
        raise ReviewError(f"cannot start claude: {exc}")
    result = parse_output(out.stdout.decode("utf-8", "replace"))
    card = {"id": job_id or new_id(), "ts": time.time(), "project_dir": project_dir, "model": cfg["review_model"],
            "proposals": result["proposals"], "summary": redact.mask(result["summary"]),
            "cost": result["cost"], "turns": result["turns"], "misses": len(misses), "lessons": len(lessons)}
    reviews = Path(folder) / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    (reviews / f"{card['id']}.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return card
```

- [ ] **Step 5: `tests/fake_claude.py`**

In `prep()`, before `if "BROKEN" in raw:` add:

```python
    if raw.startswith("You review the rules"):  # the rules review (console/review.py)
        fields = {"proposals": [{"kind": "remove", "target": "Always write tests first", "text": "",
                                 "why": "derivable: the Commands section names the test command",
                                 "sources": ["Always write tests first"]}],
                  "summary": "CLAUDE.md is 12 lines, fine."}
```

Add to the docstring after the brief-pass lines: `A request that starts with "You review the rules" is the rules review: one remove proposal and a summary.`

- [ ] **Step 6: `console/server.py`**

Import: add `review` to the `from . import (...)` list (alphabetical, after `redact`).

Replace `_prep_job` and add the review methods (keep `start_prep`, `prep_files`, `drop_prep` as they are):

```python
    def _prep_job(self, job: str, project_dir: str, raw: str, note: str = "") -> None:
        """`note` names the attached files for Prep; the card on the strip keeps the text as typed."""
        try:
            card = prep.run_prep(self.cfg, self.folder, project_dir, raw + note, self.runs.exe, job)
            end = {"state": "done", "card": dict(card, raw=raw)}
        except Exception as exc:  # whatever went wrong, the job ends: a pill never spins forever
            end = {"state": "failed", "error": str(exc) or type(exc).__name__}
        self._end_job(job, end)

    def _end_job(self, job: str, end: dict) -> None:
        with self.lock:
            if job in self.preps:  # dropped while it ran: nothing to show
                self.preps[job].update(end)
                self.version += 1
                self.changed.notify_all()

    def start_review(self, project_dir: str) -> str:
        """The rules review (plan 22) rides the Prep strip: same dict, same drop route, `kind` "review"."""
        job = review.new_id()
        with self.lock:
            self.preps[job] = {"id": job, "kind": "review", "project_dir": project_dir, "raw": "Review rules",
                               "ts": time.time(), "state": "running", "files": []}
            self.version += 1
            self.changed.notify_all()
        threading.Thread(target=self._review_job, args=(job, project_dir), name="cc-review", daemon=True).start()
        return job

    def _review_job(self, job: str, project_dir: str) -> None:
        try:
            end = {"state": "done", "card": review.run_review(self.cfg, self.folder, project_dir, self.runs.exe, job)}
        except Exception as exc:
            end = {"state": "failed", "error": str(exc) or type(exc).__name__}
        self._end_job(job, end)
```

In `do_POST` add `"/api/review": self._review` to the `routes` dict (after `"/api/task": self._task_new`).

After `_prep_drop` add:

```python
    def _review(self, body):
        folder = self.hub.allowed(body.get("project_dir"))
        if not folder:
            return self._error(403, "not a project listed in config.json")
        if not self.hub.runs.exe:
            return self._error(409, "claude.exe not found; set \"claude_exe\" in config.json")
        return self._json({"job": self.hub.start_review(folder)})
```

- [ ] **Step 7: run**

Run: `py -m unittest tests.test_review tests.test_server -v 2>&1 | tail -5`
Expected: OK. `snapshot()` already serialises every job (it strips `files` and adds `attached`), so the
review job shows on `/api/state` with `kind: "review"`; Prep jobs have no `kind` key.

- [ ] **Step 8: commit**

```bash
git add console/review.py console/review_prompt.md console/server.py tests/fake_claude.py tests/test_review.py tests/test_server.py
git commit -m "feat: the rules review job: Haiku proposes, nothing is written (plan 22 Task 4)"
```

---

### Task 5: the window (`web/app.js`)

**Files:** modify `web/app.js`. Check: `node --check web/app.js`, then a look in headless Edge or the window.

- [ ] **Step 1: state and the strip**

After `let card = null;        // the Prep card on screen` add:

```js
let reviewCard = null;  // the rules review on screen (plan 22); it uses the Prep page section
```

Replace `prepJobHtml` with:

```js
function prepJobHtml(j) {
  const where = esc(projectName(j.project_dir)), id = esc(j.id), grow = prepSeen.has(j.id) ? "" : " grow";
  prepSeen.add(j.id);
  const isReview = j.kind === "review", name = isReview ? "Review rules" : "Prep";
  if (j.state === "running") {
    return `<div class="card${grow}" style="cursor:default"><div class="l1"><span class="st n">&#9676; ${name}</span><span class="t">${esc(j.raw)}</span>
      <span class="age m">${ago(snap.now - j.ts)}</span></div>
      <span class="loading"><span class="cells">${cellsHtml(["f", "", "", "", "", ""])}</span>Haiku is reading ${where}${isReview ? "'s rules" : ""}, 10 to 30 s</span></div>`;
  }
  if (j.state === "failed") {
    return `<div class="card r${grow}" style="cursor:default"><div class="l1"><span class="st r">× FAILED</span><span class="t">${name}: ${esc(j.raw)}</span></div>
      <div class="m mut">${esc(j.error)}</div><div class="lr"><button class="btn go sm" data-prep="${id}" data-pdo="retry">Try again</button>
      ${isReview ? "" : `<button class="btn sm" data-prep="${id}" data-pdo="edit">Edit</button>`}<button class="btn sm" data-prep="${id}" data-pdo="drop">Dismiss</button></div></div>`;
  }
  const c = j.card;
  if (isReview) {
    const n = c.proposals.length, what = n ? `${n} proposal${n === 1 ? "" : "s"}` : "nothing to change";
    return `<div class="card${grow}" data-prep="${id}" data-pdo="open" tabindex="0" role="button" aria-label="${esc("Review ready: " + what)}">
      <div class="l1"><span class="st g">&#9654; Review ready</span><span class="t">${esc(c.summary || what)}</span><span class="age m">${ago(snap.now - c.ts)}</span></div>
      <div class="l2 m"><span class="who">${where} · ${what} · ${c.misses} misses, ${c.lessons} lessons read</span><span class="cost">${money(c.cost)}</span></div></div>`;
  }
  const goal = c.fields.goal || c.raw;
  return `<div class="card${grow}" data-prep="${id}" data-pdo="open" tabindex="0" role="button" aria-label="${esc("Prep ready: " + goal)}">
    <div class="l1"><span class="st g">&#9654; Ready to run</span><span class="t">${esc(goal)}</span><span class="age m">${ago(snap.now - c.ts)}</span></div>
    <div class="l2 m"><span class="who">${where}<span class="route"> · ${esc(modelText(c.route.model, c.route.effort))}</span>${j.attached.length ? ` · ${j.attached.length} file${j.attached.length === 1 ? "" : "s"}` : ""}</span>
    <span class="cost">${money(c.cost)}</span></div></div>`;
}
```

Replace `prepJob` with:

```js
async function prepJob(id, what) {
  const j = preps().find((x) => x.id === id);
  if (!j) return;
  if (j.kind === "review") {
    if (what === "open") { if (j.card) { reviewCard = j.card; showReview(); } return; }
    if (what === "retry") await startReview(j.project_dir);
    await dropPrep(id);
    return;
  }
  if (what === "open") { if (j.card) { card = j.card; showPrep(); } return; }
  if (what === "retry") await startPrep(j.project_dir, j.raw, [], id);  // the new job takes the old one's files first
  await dropPrep(id);
  if (what === "edit") { putBack(j.raw); if (j.attached.length) filesNotKept(); }
}

async function startReview(projectDir) {  // Haiku reads the project's rules, the misses and the lessons; nothing is written
  try { await api("/api/review", { project_dir: projectDir }); }
  catch (e) { fail = { title: "Review did not start", msg: e.message, retry: "" }; }
  card = null;
  reviewCard = null;
  showPage("list");
}
```

- [ ] **Step 2: the Review page**

After `showPrep` (before `stepsChanged` or right after `showPrep`'s closing brace) add:

```js
const REVIEW_KIND = { remove: "Remove", demote: "Demote to a procedure", rule: "New rule", procedure: "New procedure", keep: "Keep as is" };
function showReview() {  // the Prep page section, with proposals instead of a card; Copy puts a line on the clipboard
  const c = reviewCard, items = c.proposals;
  $("crumb").textContent = "Review / " + projectName(c.project_dir);
  const one = (p, k) => `<div class="blk"><div class="hd"><span class="lbl">${esc(REVIEW_KIND[p.kind] || p.kind)}${p.target ? " · " + esc(p.target) : ""}</span>
      ${p.text ? `<button class="btn sm" data-pact="copy" data-k="${k}">Copy</button>` : ""}</div>
    ${p.text ? `<div class="text m">${esc(p.text)}</div>` : ""}
    ${p.why ? `<div class="mut">${esc(p.why)}</div>` : ""}
    ${p.sources.length ? `<div class="m mut">from: ${p.sources.map(esc).join(" · ")}</div>` : ""}</div>`;
  $("pscroll").innerHTML = `
    <div class="blk"><span class="lbl">Project</span><div class="proj m"><b>${esc(projectName(c.project_dir))}</b> <span class="mut">${esc(c.project_dir)}</span></div></div>
    <div class="blk"><span class="lbl">Summary</span><div class="text">${esc(c.summary || "(none)")}</div></div>
    ${items.length ? items.map(one).join("") : '<p class="m mut">Nothing to change: the rules read fine against the misses and the lessons.</p>'}
    <div class="m mut">Proposals only: nothing was written. Paste what you agree with into CLAUDE.md or a skill yourself.</div>
    <div class="m mut">Review $${Number(c.cost).toFixed(3)} · ${c.turns} turns · ${c.misses} misses, ${c.lessons} lessons read</div>`;
  $("pbar").innerHTML = `<div class="lr"><button class="btn" data-pact="rdrop">Dismiss</button><button class="btn" data-pact="back">Back</button></div><div id="p-msg" class="say"></div>`;
  showPage("prep");
}

async function copyText(button) {
  const p = reviewCard.proposals[Number(button.dataset.k)], msg = $("p-msg");
  try { await navigator.clipboard.writeText(p.text); setHtml(msg, "copied"); }
  catch (e) { setHtml(msg, '<span class="r">the clipboard is not reachable here: select the text and copy it</span>'); }
}
```

- [ ] **Step 3: `prepAct`**

At the top of `prepAct`, replace `if (busy || !card) return;` with:

```js
  if (reviewCard && !card) {  // the Review page (plan 22) shares this section
    if (name === "back") { reviewCard = null; showPage("list"); }
    if (name === "rdrop") { dropPrep(reviewCard.id); reviewCard = null; showPage("list"); }
    if (name === "copy") copyText(button);
    return;
  }
  if (busy || !card) return;
```

In `prepAct`, after the `if (name === "cancel") ...` line add:

```js
  if (name === "review") startReview(c.project_dir);
```

- [ ] **Step 4: the two entry points**

In `showPrep`, replace

```js
      ${floorText(card.route.type, "runs") ? `<div class="m mut">${esc(floorText(card.route.type, "runs"))}</div>` : ""}</div>
```

with

```js
      ${floorText(card.route.type, "runs") ? `<div class="m mut">${esc(floorText(card.route.type, "runs"))}</div>` : ""}
      <div class="lr"><button class="btn sm" data-pact="review" title="Haiku reads this project's CLAUDE.md and rules files, the routing misses and the lessons, and proposes what to cut or add. Nothing is written.">Review rules</button></div></div>
```

In `noteLine`, replace

```js
  if (s.rules_warn) out.push(`△ rules: ${esc(s.rules_warn)}`);
```

with

```js
  if (s.rules_warn) out.push(`△ rules: ${esc(s.rules_warn)}${s.project_dir ? ' · <span class="link" data-act="review" title="Haiku proposes what to cut; nothing is written">Review</span>' : ""}`);
```

In `act`, after `const s = current(); if (!s) return;` add:

```js
  if (name === "review") return startReview(s.project_dir);
```

- [ ] **Step 5: check**

Run: `node --check web/app.js`
Expected: no output.

Then `py -m console --serve` with `CC_CONSOLE_HOME` set to a scratch folder that lists this repo in
`config.json` `projects`, open `http://127.0.0.1:47770/`, type a request, open the card: a `Review rules`
button sits under the Run route block; click it: a `◌ Review rules` row on the strip, then `▸ Review ready`;
open it: the proposals, Copy puts the text on the clipboard, Dismiss removes the job. On a session with a
`rules:` note, the `Review` link does the same. Nothing new in `~/.claude/console/` but `reviews/<id>.json`.

- [ ] **Step 6: commit**

```bash
git add web/app.js
git commit -m "feat: Review rules from the Prep card and the rules note; proposals with Copy (plan 22 Task 5)"
```

---

### Task 6: the skills and the verifier (`dotclaude/`)

**Files:** modify `dotclaude/skills/session-handoff/SKILL.md`, `dotclaude/skills/route-model/SKILL.md`, `dotclaude/agents/verifier.md`; test `tests/test_dotclaude.py`.

- [ ] **Step 1: tests**

Append to `tests/test_dotclaude.py` inside `DotClaudeTest`:

```python
    def test_handoff_lesson_line_parses(self):
        text = FILES["session-handoff"].read_text(encoding="utf-8")
        self.assertIn("~/.claude/console/lessons.md", text)
        example = next(line for line in text.splitlines() if re.match(r"- \d{4}-\d\d-\d\d - .* - chat: ", line))
        with tempfile.TemporaryDirectory() as tmp:
            levers.add_lesson(Path(tmp), example)
            self.assertEqual(levers.read_lessons(Path(tmp), "CLAUDE CONSOLE"), [example])
        day = time.mktime((2026, 10, 13, 12, 0, 0, 0, 0, -1))
        body = example.split(" - chat: ", 1)[1]
        self.assertEqual(levers.lesson_line("CLAUDE CONSOLE", "chat", body, day), example)
        self.assertIn("most chats teach nothing", text)

    def test_route_model_ignores_old_misses(self):
        text = FILES["route-model"].read_text(encoding="utf-8")
        self.assertIn("older than 14 days", text)
        self.assertEqual(paths.DEFAULTS["miss_floor_days"], 14)  # the skill's number is the console's

    def test_verifier_trusts_checks_over_reading(self):
        text = FILES["verifier"].read_text(encoding="utf-8")
        self.assertIn("never stands in for them", text)
        self.assertIn("not when the work looks right", text)
```

The test file's import line becomes `from console import claude_cli, levers, paths, prep`.

- [ ] **Step 2: run, expect failures**

Run: `py -m unittest tests.test_dotclaude -v 2>&1 | tail -5`
Expected: the three new tests fail (`StopIteration` or `AssertionError`).

- [ ] **Step 3: `dotclaude/skills/session-handoff/SKILL.md`**

In step 4, after the bullet that ends `propose the CLAUDE.md line to the user, do not write it.`, add one more
bullet (indented like the others), with this text:

> a lesson, what you would tell someone starting this kind of task tomorrow (transferable, one sentence; most chats teach nothing, so leave it out rather than pad): append one line to `~/.claude/console/lessons.md` (create it with the line `# Lessons` and a blank line first if it does not exist), in exactly this shape, so Claude Console's rules review reads it:

Under that bullet, a fenced block (three backticks, indented under the bullet as the misses example is in
`route-model` step 8) holding this one line:

```
- 2026-10-13 - CLAUDE CONSOLE - chat: a stream-json interrupt stops a turn cleanly where Ctrl+C to a hidden console does nothing.
```

Then, still under the bullet: `The project is the git root folder's name; the kind is `chat`.`

In "Done looks like" add the bullet:

> A lesson, when there was one, is one line in `~/.claude/console/lessons.md` and nowhere else.

In "Never" add the bullet:

> Never write a lesson that only applies to this one file or chat: most chats teach nothing, and a padded line costs every later review.

- [ ] **Step 4: `dotclaude/skills/route-model/SKILL.md`**

Replace step 2 with:

```
2. Read the project's lines in `~/.claude/console/routing-misses.md` and apply any that match this task type. Ignore a line older than 14 days: it is history, not a rule (Claude Console drops it the same way, `miss_floor_days`).
```

In "Read first", the misses bullet becomes: `` - `~/.claude/console/routing-misses.md`, the lines tagged with this project (` - <project folder name> - `) from the last 14 days. Past misses override the table. ``

- [ ] **Step 5: `dotclaude/agents/verifier.md`**

In "## Never" add:

```
- Never let your own reading replace a check: what you say about the code interprets what the commands printed, it never stands in for them.
- Never stop at confidence: the verdict is PASS when the required checks passed, not when the work looks right.
```

- [ ] **Step 6: run**

Run: `py -m unittest tests.test_dotclaude -v 2>&1 | tail -5`
Expected: OK.

- [ ] **Step 7: commit, then copy**

```bash
git add dotclaude tests/test_dotclaude.py
git commit -m "feat: session-handoff writes a lesson, route-model ignores old misses, verifier trusts checks (plan 22 Task 6)"
```

Fred copies the three files to `~/.claude/skills/session-handoff/SKILL.md`, `~/.claude/skills/route-model/SKILL.md`, `~/.claude/agents/verifier.md` (CLAUDE.md rule: Claude never writes outside `~/.claude/console/`).

---

### Task 7: the golden Prep script (`tests/golden_prep.py`)

**Files:** create `tests/golden_prep.py`. Not collected by `unittest discover` (the name does not start with `test_`).

- [ ] **Step 1: the script**

```python
"""Golden Prep routes (plan 22): three reference requests Prep must route the same way after every change to
prep_prompt.md. Fred's script: it calls the real claude three times (about $0.09). Not a unit test.

    py tests/golden_prep.py            runs in this repo's folder, prints one line per case, exits 1 on a miss
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from console import claude_cli, paths, prep  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = [  # (request, expected type): baseline, the real change, the noise case
    ("rename the variable s to sess in console/state.py State.state_of; nothing else", "mechanical"),
    ("change how install_hooks.py edits ~/.claude/settings.json so a missing file is created", "risky"),
    ("explain how Hub.levers decides when Escalate may run; no edits", "lookup"),
]


def main() -> int:
    cfg = paths.load_config()
    found = claude_cli.find_exe(cfg)
    if not found:
        print("claude.exe not found; set claude_exe in config.json")
        return 2
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:  # the cards go nowhere near ~/.claude/console
        for raw, want in CASES:
            card = prep.run_prep(cfg, Path(tmp), str(ROOT), raw, [found])
            got = card["route"]["type"]
            mark = "ok  " if got == want else "MISS"
            bad += got != want
            print(f"{mark} {want:<10} got {got:<10} {card['route']['model']}/{card['route']['effort']}  ${card['cost']:.3f}  {raw}")
    print("golden: PASS" if not bad else f"golden: FAIL {bad} of {len(CASES)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: check it parses, then Fred runs it**

Run: `py -m py_compile tests/golden_prep.py && py -m unittest discover -s tests 2>&1 | tail -3`
Expected: compiled, and the suite count is unchanged by this file.

Fred: `py tests/golden_prep.py`; expected three `ok` lines. A `MISS` on the third case (lookup) is the one
to watch: Prep tends to call an explain request `normal`.

- [ ] **Step 3: commit**

```bash
git add tests/golden_prep.py
git commit -m "test: golden Prep routes, Fred's script (plan 22 Task 7)"
```

---

### Task 8: PLAN.md (row 22 and the "written" History line exist since 2026-10-13)

- [ ] **Step 1: the row's state**

In the Sub-plans table, row 22's last cell becomes `code done <date> (<N> tests OK, node --check OK), Fred's look and golden run open`.

- [ ] **Step 2: History**

Append one line: `- <date> - Plan 22 Tasks 1-7 placed (<N> tests OK): ...` naming what differed from this plan, if anything.

- [ ] **Step 3: commit**

```bash
git add PLAN.md
git commit -m "docs: plan 22 placed"
```

## Done when

- `py -m unittest discover -s tests` passes: 312 before, plus the 15 tests above (327 expected; report the real count in History).
- `node --check web/app.js` is silent.
- A task step whose reply carries `Lesson:` adds one line to `~/.claude/console/lessons.md`; a miss dated more than 14 days back no longer shows on the Prep card as a floor; `Review rules` on the Prep card ends in a card of proposals with Copy, and `reviews/<id>.json` is the only file written.
- Fred copied the three `dotclaude/` files to `~/.claude` and ran `py tests/golden_prep.py` once.

## Self-review (2026-10-13)

- Spec coverage: lessons (Tasks 1, 3, 6), compaction lever (Tasks 4, 5), hygiene categories (review prompt, Task 4), miss decay (Tasks 1, 2, 6), debugging frame (Task 1 `FIX_FRAME`, used by `tasks._fix_text` and the Escalate lever through `levers.escalate_text`), verifier wording (Task 6), golden examples (Task 7).
- Names used across tasks: `levers.lesson_line / add_lesson / read_lessons / FIX_FRAME`, `routing.fresh`, `tasks.lesson_of`, `review.run_review / new_id / KINDS / MAX_PROPOSALS / SCHEMA / ReviewError`, `Hub.start_review / _review_job / _end_job`, `POST /api/review`, job `kind: "review"`, `reviewCard`, `showReview`, `startReview`, `copyText`, `data-pact` values `review`, `copy`, `rdrop`, `back`.
- `prep.load` rejects ids with characters other than alnum and `-`: review ids (`r20261013-120000-ab12`) pass it but are never loaded by `/api/run` because a review job has no `card.prompt`; the window never sends one.
