# Task 2: plan and replan edges (B1 to B5, K12 to K14, G1, plan 24 nits)

> Contract: [review.md](review.md) findings B1, B2, B3, B4, B5, K12, K13, K14, G1 and the plan 24 nits
> (`plan.write` and `add_answer` unmasked, a multi-line answer injects a `## ` heading, `start_replan` sets tier haiku);
> plan 24 README 3.4, 3.6, 3.7, 3.9, 3.10. Depends on: nothing of plan 27 (Task 1 touches other functions).
> Decisions: four, marked `Decision:` in 2.2, 2.3, 2.5 and 2.6.
> Run in a scratch copy on 2026-10-14: the whole suite 538 tests (525 before, thirteen added; the thirteenth, 2.5.4b, added by the lead and run on the combined copy), only the 4 Linux
> baseline failures (test_tray import, test_redact Windows path, test_usage local day, test_window placement);
> `tests.test_plan` 23 OK (21 before), `tests.test_replan` 8 OK (6 before), `tests.test_server` nine tests more.
> Lands on: plan 24 Tasks 1 to 3 (`plan.py`, `replan.py`, `design_prompt.md`, `Hub._ended`, `Hub._go_on`,
> `Hub._advance_one`, `Hub.start_replan`, `Hub.task_levers`, `Hub.edit_plan`), plan 23 Task 5 (`Hub.start_brief`'s `touched` line, kept),
> plan 18 (`fills.rank_of`, read only). Tasks 1, 3, 4, 5 and 6 of plan 27 touch none of the functions below; Task 3
> changes `tasks.step_route` and Task 4 `Hub._task` and `auto_steps`, so anchor by the quoted lines, not line numbers.

**Files**
- Modify: `console/tasks.py` (new `room_after`, after `plan_steps`)
- Modify: `console/replan.py` (`check` replaced whole)
- Modify: `console/plan.py` (`import shutil`; new `drop_parts`; `write`, `with_answer`, `add_answer`, `design_input`
  replaced whole; one line of `design_text`)
- Modify: `console/design_prompt.md` (the last paragraph)
- Modify: `console/server.py` (new `Hub._base`; `Hub.task_levers`: the `base` block and the `answer` / `redo` lines;
  `Hub._ended`: four places; `Hub.start_brief`: the `brief_on` branch; `Hub._go_on`: the replan branch; `Hub._advance_one`: the restart branch;
  `Hub.start_replan`: the tier line; `Hub.edit_plan`: two places)
- Modify: `tests/test_plan.py` (two tests), `tests/test_replan.py` (two tests), `tests/test_server.py` (one line of
  `test_replan_refused_when_no_room`, two `until` lines of `test_plan_over_the_size_waits`, nine tests in
  `TaskServerTest`)

What the review found, in short. A design step's `Replan:` line inserts a step after it, which renumbers the steps the
plan's `### Step N` sections and `parts[i].step` name (B1). A replan answer with no edit kind drops the verify of a code
step already done (B2). The `answer` lever only reads the why, so on a plan-less task `add_answer` writes a stray
plan.md and raises IndexError (B3). On a redo the design step never reads the notes of the done steps after it, though
its prompt says "its handoff is above" (B4). A redo that turns a split into a single plan leaves `part` / `hard` on the
steps (their prompt gets no section) and the old `plan/NN-*.md` on disk (B5). The room for a split or a replan ignores
the done steps a redo keeps, and `_ended` counts the verify where `replan.check` does not (K12). The replan pass (and
the brief pass) runs after the project left `projects` (K13). A redo can restart the design step while its old brief
thread still writes (K14). `edit_plan` accepts a stopped, done or handed task (G1). The nits: plan files written by
Fred unmasked, a multi-line answer, and the replan step's tier.

## 2.1 `console/tasks.py`: `room_after` (K12)

Insert after `def plan_steps(...)` (after its last line `    return steps` and the two blank lines), before
`def new_task(`:

```python
def room_after(task: dict, n: int, max_steps: int) -> int:
    """How many steps may still follow step `n` (plan 27): task_max_steps minus n minus the done steps a redo kept
    after n. A verify or fix is never counted (the service re-places it), here and in what the callers count:
    plan.check (a split), replan.check (a replan answer) and Hub._ended (a `Replan:` line)."""
    kept = sum(1 for s in task["steps"] if s["n"] > n and s["state"] == "done" and s["kind"] not in ("verify", "fix"))
    return max_steps - n - kept
```

## 2.2 `console/replan.py`: `check` (B2, K12)

Replace `def check(task: dict, n: int, answer, max_steps: int) -> tuple:` whole (down to its `    return steps, ""`)
with:

```python
def check(task: dict, n: int, answer, max_steps: int) -> tuple:
    """(steps, "") when the answer is a usable remaining chain, else ([], why). The steps are blank dicts numbered
    from n + 1, the verify re-placed after the last edit, as tasks.plan_steps does; known kinds with a goal only;
    at most MAX_ADDED more than the remaining steps; the chain (verify left out) within tasks.room_after. An answer
    with no edit kind keeps the verify the replaced steps held, of the last edit step before n (plan 27)."""
    rest = remaining(task, n)
    items = answer.get("steps") if isinstance(answer, dict) else None
    if not isinstance(items, list) or not items:
        return [], "no steps in the answer"
    kept = []
    for item in items:
        if not isinstance(item, dict) or item.get("kind") not in tasks.PREP_KINDS or item.get("kind") == KIND:
            return [], f"unknown kind: {item.get('kind') if isinstance(item, dict) else item}"
        goal = item.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            return [], "a step has no goal"
        kept.append((item["kind"], redact.clip(goal, tasks.STEP_GOAL_MAX)))
    if len(kept) > len(rest) + MAX_ADDED:
        return [], f"{len(kept) - len(rest)} steps added, over {MAX_ADDED}"
    room = tasks.room_after(task, n, max_steps)
    if len(kept) > room:
        return [], f"{max_steps - room + len(kept)} steps in all, over task_max_steps {max_steps}"
    steps = [tasks._blank(n + i + 1, kind, goal) for i, (kind, goal) in enumerate(kept)]
    edits = [i for i, s in enumerate(steps) if s["kind"] in tasks.EDIT_KINDS]
    if edits:
        after = edits[-1] + 1
        steps.insert(after, tasks._blank(0, "verify", f"Check step {n + after}", checked=n + after))
        for i, s in enumerate(steps):
            s["n"] = n + i + 1
    else:
        before = [s["n"] for s in task["steps"] if s["n"] < n and s["kind"] in tasks.EDIT_KINDS]
        tail = any(s["n"] > n and s["kind"] == "verify" and s["state"] != "done" for s in task["steps"])
        if before and tail:  # the code is done, its verify was in the replaced tail: it stays, last
            steps.append(tasks._blank(n + len(steps) + 1, "verify", f"Check step {before[-1]}", checked=before[-1]))
    return steps, ""
```

Decision: the kept verify is appended after the answer's last step and only when a verify that was not done sat in
the replaced tail, because a verify the chain already ran (scout, code, verify, replan, test) must not run twice and
with no edit step in the answer there is no later place to put it. The reason text is unchanged for a chain with no
done step after n (`max_steps - room` is then `n`).

## 2.3 `console/plan.py` (B4, B5, nits)

1. Replace the import line `import re` (the first import) with:

```python
import re
import shutil
```

2. Insert before `def read(home, task: dict) -> str:`:

```python
def drop_parts(home, task: dict, n: int) -> None:
    """Before a redo's plan is saved (plan 27): the earlier plan's plan/ folder goes, and the planned steps after
    design step `n` lose `part`, `hard` and their `Part k: ` goal head, so a single plan reaches them through its
    `### Step N` sections (a split rebuilds them anyway). Done steps keep what they ran with."""
    shutil.rmtree(tasks.folder(home, task["id"]) / PART_DIR, ignore_errors=True)
    for s in task["steps"]:
        if s["n"] > n and s["state"] != "done" and "part" in s:
            del s["part"]
            s.pop("hard", None)
            s["goal"] = re.sub(r"^Part \d+: ", "", s["goal"], count=1)


```

Decision: the goal of a former part step becomes the part's title (`Part 2: Report module` becomes `Report module`),
because Prep's original goal is gone after `rebuild` and the title is what the step did; and `plan/` is removed before
every save that follows a redo (single or split), because a split with fewer or renamed parts leaves stale files the
same way.

3. Replace `def write(home, task: dict, text: str, k: int = 0) -> str:`, `def with_answer(...)` and
`def add_answer(...)` whole (from `def write(` down to, not including, the line
`# -- what the prompts carry ---...`) with:

```python
def write(home, task: dict, text: str, k: int = 0) -> str:
    """Fred's edit of the index (k = 0) or of part k, through the service; a part is written with its head line
    again, masked like save. Returns the relative file name."""
    rel = FILE if not k else next(p["file"] for p in task["plan"]["parts"] if p["n"] == k)
    path = tasks.folder(home, task["id"]) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if k:
        title = next(p["title"] for p in task["plan"]["parts"] if p["n"] == k)
        text = f"# Part {k}: {title}\n\n" + part_body(text)
    path.write_text(redact.mask(str(text or "")), encoding="utf-8")
    return rel


def with_answer(index: str, answer: str, day: str = "") -> str:
    """The index with `- Fred, <date>: <answer>` as the last line of ## Decisions; the answer on one line, its
    whitespace collapsed (a multi-line answer adds no heading)."""
    day = day or date.today().isoformat()
    answer = " ".join(str(answer or "").split())
    lines = str(index or "").splitlines()
    out, on, placed = [], False, False
    for line in lines:
        if on and line.startswith("## ") and not placed:
            while out and not out[-1].strip():
                out.pop()
            out += [f"- Fred, {day}: {answer}", ""]
            placed = True
        if line.strip() == "## Decisions":
            on = True
        out.append(line)
    if on and not placed:
        while out and not out[-1].strip():
            out.pop()
        out.append(f"- Fred, {day}: {answer}")
    return "\n".join(out).rstrip() + "\n"


def add_answer(home, task: dict, answer: str, day: str = "") -> str:
    """Append Fred's answer to the Decisions of plan.md, masked by write; returns the line written."""
    text = redact.mask(with_answer(read(home, task), answer, day))
    write(home, task, text)
    return text.rstrip().splitlines()[-1] if not section(text, "## Decisions") else section(text, "## Decisions").splitlines()[-1]


```

4. In `def design_text(...)`, replace the line

```python
        max_kb=cfg["plan_max_kb"], max_parts=cfg["plan_max_parts"], room=max(cfg["task_max_steps"] - step["n"], 1),
```

with

```python
        max_kb=cfg["plan_max_kb"], max_parts=cfg["plan_max_parts"],
        room=max(tasks.room_after(task, step["n"], cfg["task_max_steps"]), 1),
```

5. Replace `def design_input(home, task: dict, n: int) -> str:` whole with:

```python
def design_input(home, task: dict, n: int) -> str:
    """What the design step reads instead of a brief: the raw handoff notes of every earlier step, whole (D1); on a
    redo (task["redo"]) also the notes of the done steps after n, which the redo keeps (plan 27)."""
    out = []
    for s in task["steps"]:
        if s["n"] == n or (s["n"] > n and not (task.get("redo") and s["state"] == "done")):
            continue
        note = tasks.read_note(home, task, s["n"])
        if note:
            out.append(note)
    return "\n\n".join(out)
```

## 2.4 `console/design_prompt.md` (B1)

Replace the last paragraph (the two lines from `A plan that needs another kind of step than a write step` to `the
service inserts a replan.`) with:

```text
A plan that needs another kind of step than a write step (a search, a test run before the code) cannot add it
here, and the service refuses a `Replan:` line from this step (it would renumber the steps your sections name).
When you cannot close the plan without such a step, ask Fred for it before the design step: stop with the
question line the end of this prompt describes, naming the kind of step, what it must find, and why.
```

(The question line is the `STOP: <question>` rule `claude_cli.STOP_FOOTER` puts under every step prompt; the task
then waits as any question does. Do not write a literal `STOP:` at the start of a line here: `tasks.reply_question`
reads such a line in any reply that quotes the prompt, and in the scratch copy the fake claude, which echoes its
prompt, made every design step "ask" until the wording was changed to this one.)

## 2.5 `console/server.py`

### 2.5.1 `Hub._base` and `Hub.task_levers` (K13, B3, K14)

Insert before `    def task_levers(self, task_id) -> dict:`:

```python
    def _base(self, task: dict) -> str:
        """Why nothing may run in the task's folder now ("" = it may): the project left the list, no claude.exe, or
        the folder is gone. task_levers, _go_on (the replan pass) and start_brief (the brief pass) ask it."""
        if not self.allowed(task["project_dir"]):
            return "runs are off in this project: pick it on the home view and allow runs"
        if not self.runs.exe:
            return "claude.exe not found; set \"claude_exe\" in config.json"
        if not os.path.isdir(task["project_dir"]):
            return "the task's folder is gone"
        return ""

```

In `task_levers`, replace

```python
            if not self.allowed(task["project_dir"]):
                base = "runs are off in this project: pick it on the home view and allow runs"
            elif not self.runs.exe:
                base = "claude.exe not found; set \"claude_exe\" in config.json"
            elif not os.path.isdir(task["project_dir"]):
                base = "the task's folder is gone"
            else:
                base = ""
```

with

```python
            base = self._base(task)
```

Replace

```python
            answer = base or ("" if gap else "no plan gap waits")
            has_design = any(x["kind"] == "design" for x in task["steps"])
            redo = base or ("" if has_design and (gap or (state == "waiting" and why.startswith("plan "))
                                                 or (state == "stuck" and cs and cs["kind"] == "design"))
                            else "nothing to redo")
```

with

```python
            answer = base or ("" if gap and task.get("plan") else "no plan gap waits")  # plan 27: a plan-less task asks plainly
            has_design = any(x["kind"] == "design" for x in task["steps"])
            redo = base or ("" if has_design and (gap or (state == "waiting" and why.startswith("plan "))
                                                 or (state == "stuck" and cs and cs["kind"] == "design"))
                            else "nothing to redo")
            if not redo and task["id"] in self.briefing:  # plan 27: an old brief must not land after the redo
                redo = "brief still writing"
```

Decision (K14): the redo lever refuses while the task's id is in `self.briefing` (reason `brief still writing`),
not `_brief_done` ignoring a step that is no longer done, because the lever is the one gate the window already
shows and the brief pass takes seconds; `_brief_done` stays as plan 24 wrote it.

### 2.5.2 `Hub._ended` (B1, B3, B5, K12)

1. Replace

```python
            room = max(self.cfg["task_max_steps"] - cs["n"], 1)
```

with

```python
            room = max(tasks.room_after(task, cs["n"], self.cfg["task_max_steps"]), 1)  # plan 27: done steps kept
```

2. Replace

```python
        gap = plan.gap(block) if block and ok and not block_error and cs["kind"] != "design" else ""
```

with

```python
        gap = (plan.gap(block) if block and ok and not block_error and cs["kind"] != "design" and task.get("plan")
               else "")  # plan 27: `Plan gap:` means something only in a task with a plan
```

3. Replace

```python
        if found is not None and action in ("next", "fix", "done"):
            task.pop("redo", None)
            task["plan"] = plan.save(self.folder, task, found, cs["n"])
```

with

```python
        if found is not None and action in ("next", "fix", "done"):
            if task.pop("redo", None) is not None:  # plan 27: the old plan's parts go before the new plan is saved
                plan.drop_parts(self.folder, task, cs["n"])
            task["plan"] = plan.save(self.folder, task, found, cs["n"])
```

4. Replace

```python
        ask = replan.ask_line(block) if block and ended and cs["kind"] != "replan" else ""
        if ask and action == "next":
            if len(task["steps"]) < self.cfg["task_max_steps"]:
                lines += replan.insert(task, cs["n"], now, ask)
            else:
                lines.append(tasks._line(now, cs, "done", "done", f"replan refused: no room ({ask})"))
```

with

```python
        ask = replan.ask_line(block) if block and ended and cs["kind"] != "replan" else ""
        if ask and cs["kind"] == "design":  # plan 27: an insert would renumber the steps the plan's sections name
            lines.append(tasks._line(now, cs, "done", "done", f"replan refused: design step ({ask})"))
        elif ask and action == "next":
            later = sum(1 for x in task["steps"] if x["n"] > cs["n"] and x["state"] != "done"
                        and x["kind"] not in ("verify", "fix"))
            if later + 1 <= tasks.room_after(task, cs["n"], self.cfg["task_max_steps"]):  # the verify not counted
                lines += replan.insert(task, cs["n"], now, ask)
            else:
                lines.append(tasks._line(now, cs, "done", "done", f"replan refused: no room ({ask})"))
```

### 2.5.3 `Hub.start_brief` (K13, the brief pass)

Replace

```python
        task["briefing"] = n
        if not self.cfg["brief_on"]:
            text = compact.fallback(prev, raw)
            self._brief_done(task["id"], n, {"text": text, "cost": 0, "words": len(text.split()),
                                             "fallback": "brief is off"}, raw)
            return
```

with

```python
        task["briefing"] = n
        base = self._base(task)  # plan 27: no pass in a folder taken off the list; the code fallback stands in
        if not self.cfg["brief_on"] or base:
            text = compact.fallback(prev, raw)
            self._brief_done(task["id"], n, {"text": text, "cost": 0, "words": len(text.split()),
                                             "fallback": base or "brief is off"}, raw)
            return
```

Decision: the brief pass in a folder taken off the list writes the code fallback (chain `brief fallback: runs are off
in this project: ...`) instead of making the task stuck, because the step it briefs already ran and its note is on
disk; the next step is still refused by the `start` lever, and a replan step by 2.5.4.

### 2.5.4 `Hub._go_on` (K13)

Replace

```python
        if nxt["kind"] == replan.KIND:
            if task["state"] == "waiting" or task["id"] in self.briefing:
                return ""
            self.start_replan(task, nxt["n"])
```

with

```python
        if nxt["kind"] == replan.KIND:
            if task["state"] == "waiting" or task["id"] in self.briefing:
                return ""
            base = self._base(task)
            if base:  # plan 27: the pass runs claude in the folder, so it needs the project as a step does
                lines = []
                tasks._task_to(task, "stuck", base, now, nxt, lines)
                self._commit(task, lines)
                return "stuck"
            self.start_replan(task, nxt["n"])
```

### 2.5.4b `Hub._advance_one` (K13, the pass restarted after a service restart)

Added by the lead after the scratch run (the same check as 2.5.4 on the other caller of `start_replan`). Replace

```python
            if task["id"] not in self.briefing:  # the service restarted while the pass ran: run it again
                self.start_replan(task, cs["n"])
            return ""
```

with

```python
            if task["id"] not in self.briefing:  # the service restarted while the pass ran: run it again
                base = self._base(task)
                if base:  # plan 27: as in _go_on, the pass runs claude in the folder and needs the project
                    lines = []
                    tasks._task_to(task, "stuck", base, time.time(), cs, lines)
                    self._commit(task, lines)
                    return "stuck"
                self.start_replan(task, cs["n"])
            return ""
```

### 2.5.5 `Hub.start_replan` (plan 24 nit)

Replace

```python
        s["tier"] = "haiku"
```

with

```python
        s["tier"] = fills.rank_of(self.cfg["brief_model"], self.cfg)  # plan 27: the rank brief_model runs on
```

(`rank_of` gives `""` for a model it cannot rank; `tasks.checked_route` then falls back to the model's alias, as for
any step.)

### 2.5.6 `Hub.edit_plan` (G1, K12)

Replace

```python
            paused = task["owner"] == "fred" and not (cs and cs["state"] == "running")
```

with

```python
            paused = (task["owner"] == "fred" and task["state"] in ("running", "waiting")  # plan 27: paused only
                      and not (cs and cs["state"] == "running"))
```

Replace

```python
            why = plan.check(found, later, self.cfg["plan_max_parts"], max(self.cfg["task_max_steps"] - task["plan"]["from"], 1))
```

with

```python
            room = max(tasks.room_after(task, task["plan"]["from"], self.cfg["task_max_steps"]), 1)
            why = plan.check(found, later, self.cfg["plan_max_parts"], room)
```

## 2.6 Tests

### `tests/test_plan.py`

In `class FilesTest`, insert after `test_write_replaces_the_index_or_a_part` (after its last line
`self.assertEqual(plan.read_part(self.home, self.t, 2), "# Part 2: Report module\n\n## Files\n- b\n")`):

```python

    def test_write_and_add_answer_mask_and_keep_one_line(self):
        self.t["plan"] = plan.save(self.home, self.t, plan.parse(split()), 2)
        plan.write(self.home, self.t, SPLIT_INDEX + "- token: sk-ant-abcdefghijklmnop\n")
        self.assertNotIn("sk-ant-abcdefghijklmnop", plan.read(self.home, self.t))
        plan.write(self.home, self.t, "## Files\n- api_key=hunter2hunter2\n", 2)
        self.assertNotIn("hunter2hunter2", plan.read_part(self.home, self.t, 2))
        plan.write(self.home, self.t, SPLIT_INDEX)
        line = plan.add_answer(self.home, self.t, "use sk-ant-abcdefghijklmnop\n## Acceptance\n- nothing", "2026-10-14")
        self.assertEqual(line, "- Fred, 2026-10-14: use *** ## Acceptance - nothing")
        text = plan.read(self.home, self.t)
        self.assertEqual(text.count("\n## Acceptance\n"), 1)  # the answer adds no heading
        self.assertNotIn("sk-ant-", text)
```

In `class PromptTest`, insert after `test_design_input_is_every_earlier_note_whole` (after its last line
`self.assertGreater(len(text.split()), 600)`):

```python

    def test_design_input_on_a_redo_adds_the_done_later_notes(self):
        home, t = tempfile.mkdtemp(), make_task()
        for n, words in ((1, "scout found calc.py"), (3, "code step wrote add()"), (4, "test step ran it")):
            s = tasks.step(t, n)
            s.update(model="haiku", effort="low", session=f"s{n}", state="done")
            tasks.write_note(home, t, s, "## Findings\n" + words)
        tasks.step(t, 4)["state"] = "planned"  # a note left by an attempt that is not done: not read
        self.assertNotIn("code step wrote add()", plan.design_input(home, t, 2))  # first design: earlier notes only
        t["redo"] = "which file holds the ladder?"
        text = plan.design_input(home, t, 2)
        self.assertIn("scout found calc.py", text)
        self.assertIn("code step wrote add()", text)
        self.assertNotIn("test step ran it", text)
```

### `tests/test_replan.py`

In `class ReplanTest`, insert after `test_propose_apply_and_keep` (after its last line
`self.assertEqual(replan.apply(t, 8.0), [])`):

```python

    def test_check_keeps_the_verify_of_a_done_edit_step(self):
        t = make_task(kinds=("scout", "code", "replan", "test", "verify"))  # the verify checks step 2
        t["steps"][1]["state"] = t["steps"][2]["state"] = "done"
        steps, why = replan.check(t, 3, {"why": "w", "steps": [{"kind": "test", "goal": "run it"}]}, 8)
        self.assertEqual(why, "")
        self.assertEqual([(s["n"], s["kind"], s["checked"], s["goal"]) for s in steps],
                         [(4, "test", 0, "run it"), (5, "verify", 2, "Check step 2")])
        replan.propose(t, 3, steps, "w", 6.0)
        replan.apply(t, 7.0)
        self.assertEqual([s["kind"] for s in t["steps"]], ["scout", "code", "replan", "test", "verify"])
        done = make_task(kinds=("scout", "code", "verify", "replan", "test"))  # already verified: none added
        for s in done["steps"][:4]:
            s["state"] = "done"
        steps, _ = replan.check(done, 4, {"why": "w", "steps": [{"kind": "test", "goal": "run it"}]}, 8)
        self.assertEqual([s["kind"] for s in steps], ["test"])

    def test_room_counts_the_done_steps_kept_after_n(self):
        t = make_task(kinds=("scout", "replan", "code", "code", "verify"))  # a redo kept step 3 done
        t["steps"][1]["state"] = t["steps"][2]["state"] = "done"
        self.assertEqual(tasks.room_after(t, 2, 6), 3)  # 6 - 2 - the done code step; the verify is not counted
        three = {"why": "", "steps": [{"kind": "code", "goal": "g"}] * 3}
        self.assertEqual(replan.check(t, 2, three, 5)[1], "6 steps in all, over task_max_steps 5")
        self.assertEqual(replan.check(t, 2, three, 6)[1], "")
```

### `tests/test_server.py`

In `test_replan_refused_when_no_room`, replace

```python
        self.hub.cfg["task_max_steps"] = 5  # the chain is 5 long (scout, design, code, test, verify)
```

with

```python
        self.hub.cfg["task_max_steps"] = 4  # scout, design, code, test (the verify is not counted): no room for a 5th
```

(With the verify no longer counted, 5 leaves room for the replan step; 4 is the same "full chain" case. The test
passes before and after the fix.)

In `test_plan_over_the_size_waits`, replace

```python
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits on the size")
```

with

```python
        task = self.until(tid, lambda t: t["state"] == "waiting" and not t.get("briefing"), "the task waits on the size")
```

and replace

```python
        task = self.until(other, lambda t: t["state"] == "waiting", "the second task waits")
```

with

```python
        task = self.until(other, lambda t: t["state"] == "waiting" and not t.get("briefing"), "the second task waits")
```

(The K14 guard makes the redo lever say `brief still writing` while the design step's brief thread runs; this test
read the lever and posted Redo right after the wait began, and failed in the scratch copy with
`AssertionError: 'brief still writing' != ''` once 2.5.1 was in.)

In `class TaskServerTest`, insert after `test_clear_keeps_the_plan_files` (after its last line
`self.assertTrue((folder / "task.json").is_file())`), before the line `    # -- plan 25: the Board ---...`:

```python

    # -- plan 27 Task 2: plan and replan edges --------------------------------------------------------------

    def test_design_step_replan_line_is_refused(self):
        tid = self.plan_task(goals={2: "plan it REPLAN-ASK"})
        task = self.until(tid, self.at(3), "step 3 starts")
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout", "design", "code", "verify", "test"])
        self.assertIn("replan refused: design step (a search step is needed first)", self.whys(tid))
        self.assertIn("Your part of the plan:\n### Step 3: code", self.full_prompt(task["steps"][2]["session"]))
        self.assertIn("the service refuses a `Replan:` line from this step", self.full_prompt(task["steps"][1]["session"]))

    def test_plan_gap_answer_needs_a_plan(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "look"}, {"kind": "code", "goal": "write PLAN-GAP"}])
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits on the question")
        self.assertEqual(task["why"], "asks: Plan gap: which file holds the ladder?")
        self.assertNotIn("plan", task)
        self.assertEqual(self.task(tid)[1]["levers"]["answer"], "no plan gap waits")
        self.assertEqual(self.call("/api/task/answer", {"task": tid, "text": "config.json"}),
                         (409, {"error": "no plan gap waits"}))
        self.assertFalse((self.folder / "tasks" / tid / "plan.md").exists())

    def test_redo_to_a_single_plan_drops_the_parts(self):
        tid = self.plan_task(words="HANDOFF-OK PLAN-SPLIT", kinds=("scout", "design", "code"))
        self.until(tid, self.at(3), "part 1 runs")
        self.hub.tasks[tid]["goal"] += " PLAN-GAP"  # part 2 stops on a gap; part 1 has its prompt already
        task = self.until(tid, lambda t: t["state"] == "waiting", "part 2 waits on a gap")
        self.assertEqual([(s["kind"], s["state"], s.get("part")) for s in task["steps"][2:4]],
                         [("code", "done", 1), ("code", "running", 2)])
        task["goal"] = task["goal"].replace(" PLAN-GAP", "").replace("PLAN-SPLIT", "PLAN-OK")
        self.assertEqual(self.call("/api/task/redo", {"task": tid})[0], 200)
        task = self.until(tid, self.at(4), "step 4 runs on the single plan")
        self.assertEqual(task["plan"]["parts"], [])
        self.assertNotIn("part", task["steps"][3])
        self.assertNotIn("hard", task["steps"][3])
        self.assertEqual(task["steps"][3]["goal"], "Report module")
        self.assertEqual(task["steps"][2]["part"], 1)  # a done step keeps what it ran with
        self.assertFalse((self.folder / "tasks" / tid / "plan").exists())
        self.assertIn("Your part of the plan:\n### Step 4: code", self.full_prompt(task["steps"][3]["session"]))

    def test_redo_room_counts_the_done_steps(self):
        self.hub.cfg["task_max_steps"] = 4
        tid = self.plan_task(kinds=("scout", "design", "code", "code"), goals={4: "second PLAN-GAP"})
        task = self.until(tid, lambda t: t["state"] == "waiting", "step 4 waits on a gap")
        task["goal"] = task["goal"].replace("PLAN-OK", "PLAN-SPLIT")
        self.assertEqual(self.call("/api/task/redo", {"task": tid})[0], 200)
        task = self.until(tid, lambda t: t["state"] == "stuck", "the split does not fit")
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout", "design", "code", "code", "verify"])
        self.assertEqual(task["why"], "plan: 2 steps after the design step, over task_max_steps (after one retry)")

    def test_replan_pass_needs_the_project_allowed(self):
        tid = self.replan_task()
        self.hub.cfg["projects"] = []  # Fred took the project off the list while the scout ran
        task = self.until(tid, lambda t: t["state"] != "running", "the task leaves running")
        self.assertEqual((task["state"], task["why"]),
                         ("stuck", "runs are off in this project: pick it on the home view and allow runs"))
        self.assertEqual((task["steps"][1]["kind"], task["steps"][1]["state"]), ("replan", "planned"))
        self.assertIn("brief fallback: runs are off in this project: pick it on the home view and allow runs",
                      self.whys(tid))

    def test_replan_pass_restarted_after_a_restart_needs_the_project_allowed(self):
        self.hub.cfg["task_max_steps"] = 8
        tid = self.replan_task()
        self.until(tid, lambda t: t["state"] == "waiting", "the task waits on the replan")
        with self.hub.tlock:  # the state a service restart finds: the pass was running, no thread holds the task
            task = self.hub.tasks[tid]
            task.update(state="running", owner="service", why="")
            task["steps"][1].update(state="running", session="")
            self.hub.briefing.discard(tid)
            self.hub.cfg["projects"] = []  # and Fred took the project off the list meanwhile
            with mock.patch.object(self.hub, "start_replan") as start:
                self.assertEqual(self.hub._advance_one(task), "stuck")
            start.assert_not_called()
        self.assertEqual((task["state"], task["why"]),
                         ("stuck", "runs are off in this project: pick it on the home view and allow runs"))

    def test_redo_waits_while_the_brief_writes(self):
        self.hub.cfg["plan_hold"] = True
        tid = self.plan_task()
        self.until(tid, lambda t: t["state"] == "waiting" and not t.get("briefing"), "the task holds, briefed")
        self.hub.briefing.add(tid)  # the design step's brief thread is still writing
        self.assertEqual(self.task(tid)[1]["levers"]["redo"], "brief still writing")
        self.assertEqual(self.call("/api/task/redo", {"task": tid}), (409, {"error": "brief still writing"}))
        self.hub.briefing.discard(tid)
        self.assertEqual(self.call("/api/task/redo", {"task": tid})[0], 200)

    def test_plan_edit_refused_on_a_stopped_task(self):
        self.hub.cfg["plan_hold"] = True
        tid = self.plan_task()
        self.until(tid, lambda t: t["state"] == "waiting", "the task holds")
        text = (self.folder / "tasks" / tid / "plan.md").read_text(encoding="utf-8")
        self.assertEqual(self.call("/api/task/stop", {"task": tid})[0], 200)
        self.assertEqual(self.call("/api/task/plan", {"task": tid, "text": text}),
                         (409, {"error": "the plan can be edited while the task waits on it or is paused"}))

    def test_replan_step_tier_follows_brief_model(self):
        self.hub.cfg.update(brief_model="sonnet", task_max_steps=8)
        tid = self.replan_task()
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits on the replan")
        self.assertEqual((task["steps"][1]["model"], task["steps"][1]["tier"]), ("sonnet", "sonnet"))
```

How the server tests drive the fake claude: the fake answers from words in the prompt only (plan 24 README 3.12), so
two tests change `task["goal"]` in `hub.tasks` between steps (the goal rides in every later step's prompt): B5 adds
`PLAN-GAP` while part 1 runs (part 2 then stops on a gap) and swaps `PLAN-SPLIT` for `PLAN-OK` before the redo; K12
swaps `PLAN-OK` for `PLAN-SPLIT` before the redo. K14 adds the task id to `hub.briefing` by hand, the state the brief
thread holds while it runs, so the test does not race the thread.

## 2.7 Steps

1. Add the tests of 2.6 (and the one-line change to `test_replan_refused_when_no_room`). Run
   `py -m unittest tests.test_plan tests.test_replan`: four of the new tests fail, as seen in the scratch copy:
   - `test_write_and_add_answer_mask_and_keep_one_line`: `AssertionError: 'sk-ant-abcdefghijklmnop' unexpectedly
     found in '# Plan: calc\n## Goal\ntwo modules. ...- token: sk-ant-abcdefghijklmnop\n'`
   - `test_design_input_on_a_redo_adds_the_done_later_notes`: `AssertionError: 'code step wrote add()' not found in
     '# Step 01: scout on haiku/low, session s1\n\n## Findings\nscout found calc.py'`
   - `test_check_keeps_the_verify_of_a_done_edit_step`: `AssertionError: Lists differ: [(4, 'test', 0, 'run it')] !=
     [(4, 'test', 0, 'run it'), (5, 'verify', 2, 'Check step 2')]`
   - `test_room_counts_the_done_steps_kept_after_n`: `AttributeError: module 'console.tasks' has no attribute
     'room_after'`
2. Run the eight new server tests (`py -m unittest tests.test_server.TaskServerTest.test_design_step_replan_line_is_refused`
   and the seven after it, by name): all fail, as seen in the scratch copy:
   - `test_design_step_replan_line_is_refused`: `Lists differ: ['scout', 'design', 'replan', 'code', 'verify',
     'test'] != ['scout', 'design', 'code', 'verify', 'test']`
   - `test_plan_gap_answer_needs_a_plan`: `AssertionError: '' != 'no plan gap waits'`
   - `test_redo_to_a_single_plan_drops_the_parts`: `AssertionError: 'part' unexpectedly found in {'n': 4, 'kind':
     'code', 'goal': 'Part 2: Report module', ... 'notes': [..., 'read: brief 02 · plan 0.4 KB · part 2'], ...
     'part': 2, 'hard': True, ...}` (the step reads part 2 of a plan that has no parts: its prompt gets no section)
   - `test_redo_room_counts_the_done_steps`: `Lists differ: ['scout', 'design', 'code', 'code', 'code', 'verify'] !=
     ['scout', 'design', 'code', 'code', 'verify']` (the split went through: six steps, five counted, over 4)
   - `test_replan_pass_needs_the_project_allowed`: `Tuples differ: ('waiting', 'replanned: 1 steps added') !=
     ('stuck', 'runs are off in this project: pi[34 chars]uns')`
   - `test_redo_waits_while_the_brief_writes`: `AssertionError: '' != 'brief still writing'`
   - `test_plan_edit_refused_on_a_stopped_task`: `Tuples differ: (200, {'task': '...', 'fi[35 chars]0.4}) != (409,
     {'error': 'the plan can be edited wh[35 chars]ed'})`
   - `test_replan_step_tier_follows_brief_model`: `Tuples differ: ('sonnet', 'haiku') != ('sonnet', 'sonnet')`
3. Apply 2.1, 2.2 and 2.3: `tests.test_plan` (23) and `tests.test_replan` (8) are green.
4. Apply 2.4 and 2.5 and the `test_plan_over_the_size_waits` change: the eight server tests are green;
   `py -m unittest tests.test_server` all OK (133).
5. Run the whole suite `py -m unittest discover -s tests`: thirteen tests more than before, nothing new failing (on
   Linux 538 run, only the 4 baseline failures).
6. Commit: `plan 27 task 2: design step Replan refused, verify kept, answer needs a plan, redo reads later notes and drops parts, one room rule, project check before the replan pass, redo waits for the brief, edit paused only, plan text masked (B1-B5 K12-K14 G1) (538 tests)`.

## 2.8 Drift guards

- `tasks.room_after` is the only room rule: `plan.check`'s `room` argument (from `Hub._ended` and `Hub.edit_plan`),
  `plan.design_text`'s `$room`, `replan.check` and the `Replan:` insert in `_ended` all go through it, and none of
  them counts a verify or a fix. Do not add a second formula.
- `plan.check`, `plan.rebuild`, `replan.insert`, `replan.apply` and `tasks.on_step_ended` are unchanged; the service
  still re-checks nothing the validators decide.
- A design step's `Replan:` line is never inserted, whatever the room; the chain line is
  `replan refused: design step (<ask>)` and the task goes on as without the line. Other kinds keep the insert.
- `Plan gap:` is special only when `task.get("plan")`: without a plan the STOP question is a plain question
  (Continue answers it from the step's chat; the `answer` lever stays off). `Hub.levers` is unchanged.
- `plan.drop_parts` runs only when `task["redo"]` was set, removes only `tasks/<id>/plan/`, and touches only planned
  steps after the design step; done steps keep `part` and `hard`.
- Everything the service writes into the plan files passes `redact.mask` (`save`, `write`, `add_answer`). The plan is
  still never cut or compacted: collapsing whitespace applies to Fred's answer line only.
- `Hub._base` is the same three checks, same texts, as the `base` block it replaces; `start` and the other levers
  read it as before.
- `_brief_done` and `_replan_done` are not changed. The redo lever is the K14 guard.
- `s["tier"]` of a replan step comes from `fills.rank_of(brief_model, cfg)`; the step's `model` stays `brief_model`
  as given.
- No line of `design_prompt.md` (or any prompt template) starts with `STOP:`; the prompt names the footer's rule
  in words.
- No new file, no new config key, nothing written outside the data folder; `cc_events.py` untouched.
