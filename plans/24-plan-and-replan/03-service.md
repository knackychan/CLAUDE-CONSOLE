# Task 3: The service: the plan saved and checked, the split, the waits, the replan run, the levers and routes

> Contract: [README.md](README.md) 3.2, 3.3, 3.6, 3.7, 3.8, 3.9, 3.12. Depends on Tasks 1 and 2. Decisions D1 (3.1),
> D2 (3.1), D3 (3.1, the `read:` note). Not run in the scratch copy: the code below is written against
> `console/server.py` as of 2026-10-14 (plan 22 placed); every anchor is quoted, the executor verifies each with the
> tests of 3.8 before the commit.

**Files**
- Modify: `console/server.py` (`Hub.start_step`, `Hub._ended`, `Hub._go_on`, `Hub.task_levers`, `Hub.task_lever`,
  new `Hub.start_replan`, `Hub._replan_job`, `Hub._replan_done`, `Hub.answer_gap`, `Hub.edit_plan`;
  `task_row`; `Handler.do_POST`, `Handler._task`, new `Handler._task_answer`, `Handler._task_plan`),
  `console/tasks.py` (`fred`: `redo`, `keep`, `confirm` extended; `clear` keeps the plan files),
  `tests/fake_claude.py`, `tests/test_server.py`, `tests/test_tasks.py`

## 3.1 `Hub.start_step`: the design step's input, text and turn cap; the `read:` note (D1, D2, D3)

Replace the two lines

```python
        prompt = tasks.step_prompt(task, s, tasks.read_brief(self.folder, task, task["last_good"]), retry)
        max_turns = self.cfg["opus_max_turns"] if kind == "design" and tier == "opus" else 0
```

with

```python
        prev = tasks.read_brief(self.folder, task, task["last_good"])
        special, plan_text, part_text, read = "", "", "", [f"brief {task['last_good']:02d}" if prev else "no brief"]
        if kind == "design":
            special = plan.design_text(task, s, self.cfg, redo=task.get("redo", ""))
            prev = plan.design_input(self.folder, task, n) or prev  # D1 a: every earlier raw note, whole
            read = [f"notes 01-{n - 1:02d}" if n > 1 else "no note"]
        elif task.get("plan"):
            plan_text, part_text = plan.prompt_parts(self.folder, task, s)
            if plan_text:
                read.append(f"plan {task['plan']['kb']} KB")
            if s.get("part"):
                read.append(f"part {s['part']}")
            elif part_text:
                read.append(f"step {n} section")
        prompt = tasks.step_prompt(task, s, prev, retry, special=special, plan=plan_text, part=part_text)
        max_turns = self.cfg["design_max_turns"] if kind == "design" else 0  # D2 a
        route = dict(route, notes=route["notes"] + ["read: " + " · ".join(read)])  # D3 a: the chain says what it got
```

With D1 (b): drop the `prev = plan.design_input(...)` line and the `read` override. With D2 (b): keep today's
`max_turns` line. With D3 (b): drop the last line and write the copies into `steps/NN/` instead (not planned here).
`import plan, replan` at the top of server.py next to `compact`.

A step of kind `replan` never reaches `start_step`: `_go_on` routes it to `start_replan` (3.4).

## 3.2 `Hub._ended`: the PLAN block of a design step; the `Plan gap:` and `Replan:` lines

After `block_error = "no HANDOFF block" if block is None else tasks.check_handoff(block)` add:

```python
        found = None
        if cs["kind"] == "design" and not block_error:
            found = plan.parse(text)
            later = [x for x in task["steps"] if x["n"] > cs["n"]]
            room = max(self.cfg["task_max_steps"] - cs["n"], 1)
            why = ("no PLAN block" if found is None else
                   plan.check(found, later, self.cfg["plan_max_parts"], room))
            block_error = why if why == "no PLAN block" else f"plan: {why}" if why else ""
```

The question branch above it: `question = s["stop_question"] or tasks.reply_question(text)` stays; a `Plan gap:`
question is a question (`asks: Plan gap: ...`), nothing else to do there. A gap written only under Open questions
(no STOP line) is read after the block check: `gap = plan.gap(block) if block and not block_error else ""`, and
when `gap` is set the step is treated as having asked: `cs["asked"] = meta.get("started")` and
`tasks.on_step_ended(task, ok=True, block_error="", verdict="", verdict_detail="", question="Plan gap: " + gap,
now=now)`; commit and return. (The session's turn is over, so Fred's answer starts a new turn through `/api/task/answer`.)

After `action, lines = tasks.on_step_ended(...)` and `self.sync_costs(task)`, when `found is not None and action in
("next", "fix", "done")`:

```python
            task.pop("redo", None)
            task["plan"] = plan.save(self.folder, task, found, cs["n"])
            meta = task["plan"]
            what = (f"{len(meta['parts'])} sub-plans, " if meta["parts"] else "") + f"{meta['words']:,} w, {meta['kb']} KB"
            lines.append(tasks._line(now, cs, "done", "done", f"plan saved: {what}"))
            if meta["parts"]:
                lines += plan.rebuild(task, cs["n"], meta["parts"], now)
            if meta["kb"] > self.cfg["plan_max_kb"]:
                tasks._task_to(task, "waiting", f"plan {meta['kb']:.0f} KB, over {self.cfg['plan_max_kb']}", now, cs, lines)
                action = "wait"
            elif self.cfg["plan_hold"] and action == "next":
                tasks._task_to(task, "waiting", "plan ready: confirm", now, cs, lines)
                action = "wait"
```

placed before `tasks.write_note(...)`, so the note and the brief are still written for `next` and the waits (change
the three `if action in ("next", "fix", "done")` guards to also accept `"wait"` when `found is not None`: bind
`ended = action in ("next", "fix", "done") or (found is not None and action == "wait")` and use it in those guards).
`task["briefing"] = cs["n"]` and `start_brief` run as today; `_go_on` is called only for `action in ("next", "fix",
"retry")`, so a wait stays.

The `Replan:` line, after the note is written and before `_go_on`:

```python
        ask = replan.ask_line(block) if block and ended and cs["kind"] != "replan" else ""
        if ask and action == "next":
            if len(task["steps"]) < self.cfg["task_max_steps"]:
                lines += replan.insert(task, cs["n"], now, ask)
            else:
                lines.append(tasks._line(now, cs, "done", "done", f"replan refused: no room ({ask})"))
            self._commit(task, lines)
```

## 3.3 `Hub._go_on`: a replan step starts in a thread; the waits hold

After the Fable check and before `if self.task_levers(task["id"])["start"]`:

```python
        if nxt["kind"] == replan.KIND:
            self.start_replan(task, nxt["n"])
            return "start"
```

`_next_step` is unchanged. `task_levers`'s `start` reason stays `task is waiting` for every wait of README 3.6 (the
waits are `waiting` with their why; Confirm, Answer, Redo design, Keep old plan move the task to `running`).

## 3.4 `Hub.start_replan`, `_replan_job`, `_replan_done`

Mirror `start_brief` / `_brief_job` / `_brief_done` (quoted in the README's anchors):

```python
    def start_replan(self, task: dict, n: int) -> None:
        """A replan step has no session: the pass runs in a thread on brief_model (README 3.9); the step is running
        with session "" until the answer is checked."""
        s, now = tasks.step(task, n), time.time()
        lines = tasks.start_step(task, n, "", {"model": self.cfg["brief_model"], "effort": "low",
                                              "notes": ["replan: the pass, no tools"]}, "", now)
        s["tier"] = "haiku"
        self._commit(task, lines)
        briefs = "\n\n".join(b for b in (tasks.read_brief(self.folder, task, k) for k in range(1, n)) if b)
        self.briefing.add(task["id"])  # the same flag: nothing else starts while a thread of the task runs
        threading.Thread(target=self._replan_job, args=(copy.deepcopy(task), n, briefs), name="cc-replan",
                         daemon=True).start()

    def _replan_job(self, task: dict, n: int, briefs: str) -> None:
        model = self.cfg["brief_model"]
        cfg = dict(self.cfg, brief_model=self.model_id(model) if model in claude_cli.MODELS else model)
        try:
            res = replan.run_replan(cfg, self.runs.exe, task, n, briefs)
        except Exception as exc:  # run_replan never raises; if it does, the step fails like a bad answer
            res = {"steps": [], "why": "", "cost": 0, "error": f"{type(exc).__name__}: {exc}"}
        self._replan_done(task["id"], n, res)

    def _replan_done(self, task_id: str, n: int, res: dict) -> None:
        with self.tlock:
            self.briefing.discard(task_id)
            task = self.tasks.get(task_id)
            if task is None or tasks.current_step(task) is None or tasks.current_step(task)["n"] != n:
                return  # cleared or stopped while the pass ran
            s, now, lines = tasks.step(task, n), time.time(), []
            s["attempts"][-1]["cost"] = s["cost"] = res["cost"]
            if res["error"]:
                action = tasks._retry_or_stuck(task, s, f"replan failed: {res['error']}", now, lines)
                self._commit(task, lines)
                if action == "retry" and task["owner"] == "service":
                    self._go_on(task)
                return
            lines += replan.propose(task, n, res["steps"], res["why"], now)
            tasks._finish(task, s, "done", now, lines)
            task["last_good"] = n
            try:
                tasks.write_note(self.folder, task, s, replan.note_block(task))
                prev = tasks.read_brief(self.folder, task, n - 1)
                tasks.write_brief(self.folder, task, s, prev)  # the pass adds nothing a later step reads
            except OSError:
                pass
            if self.cfg["replan_auto"]:
                lines += replan.apply(task, now)
                tasks._task_to(task, "running", "", now, s, lines)
            else:
                tasks._task_to(task, "waiting", replan.summary(task), now, s, lines)
            self._commit(task, lines)
            if self.cfg["replan_auto"] and task["owner"] == "service":
                self._go_on(task)
```

`tasks._retry_or_stuck` is the plan 17 helper (retry once with the reason, then stuck); `tasks.start_step` accepts
`session=""` (it stores what it is given; `task_row`'s `cs["session"]` guards are already `if cs and cs["session"]`).
`_advance_one` skips a running step whose session is `""` (add `if cs["session"] == "": return ""` where it reads
`self.session(cs["session"])`, next to the `briefing` check), so the thread alone ends the step.

## 3.5 `tasks.fred`: `redo`, `keep`, Confirm extended; `tasks.clear` keeps the plan

In `fred`, before `elif lever == "confirm":`:

```python
    elif lever == "keep":  # Keep old plan: the replan proposal is dropped
        if not (state == "waiting" and task["why"].startswith("replanned:")):
            return False, "no plan change waits", []
        lines += replan.keep(task, now)
        _task_to(task, "running", "", now, s, lines)
    elif lever == "redo":  # Redo design: the design step plans again with the question; done steps stay done
        design = next((x for x in task["steps"] if x["kind"] == "design"), None)
        waits = state == "waiting" and (task["why"].startswith("asks: Plan gap:") or task["why"].startswith("plan "))
        if design is None or not (waits or (state == "stuck" and s and s["kind"] == "design")):
            return False, "nothing to redo", []
        question = task["why"][len("asks: Plan gap: "):] if task["why"].startswith("asks: Plan gap:") else task["why"]
        if s and s["state"] == "running":
            _finish(task, s, "failed", now, lines, "stopped for a redo")
        for x in task["steps"]:
            if x["n"] >= design["n"] and x["state"] != "done" or x is design:
                if x["state"] != "planned":
                    lines.append(_line(now, x, x["state"], "planned", "redo by Fred"))
                x["state"], x["session"], x["ended"] = "planned", "", None
        task["redo"], task["current"] = question, design["n"]
        _task_to(task, "running", "", now, design, lines)
        lines.append(_line(now, design, "planned", "planned", f"design redone by Fred: {question}"))
        task["owner"] = "service"
```

(`redo` imports nothing new: `replan.keep` is reached through a late import at the top of `fred`, `from . import
replan`, as `new_task` imports `prep`; `replan` imports `tasks`, so the import is inside the function.) The design
step's `retries` is reset to 0 on a redo (`design["retries"] = 0`), so the redone plan gets its own retry.

In `confirm`, before the `else: return False, "nothing to confirm", []`:

```python
        elif state == "waiting" and task["why"].startswith("replanned:"):
            lines += replan.apply(task, now)
        elif state == "waiting" and task["why"] == "plan ready: confirm":
            lines.append(_line(now, s, "done", "done", "plan confirmed by Fred"))
        elif state == "waiting" and task["why"].startswith("plan ") and " KB, over " in task["why"]:
            lines.append(_line(now, s, "done", "done", "plan accepted by Fred"))
```

`tasks.clear`: the loop that deletes notes skips `plan.FILE` and the `plan/` folder in both modes (one line in its
file walk: `if p.name == "plan.md" or p.parent.name == "plan": continue`).

`Hub.task_levers` adds, next to `confirm`:

```python
            gap = state == "waiting" and task["why"].startswith("asks: Plan gap:")
            answer = base or ("" if gap else "no plan gap waits")
            has_design = any(x["kind"] == "design" for x in task["steps"])
            redo = base or ("" if has_design and (gap or (state == "waiting" and task["why"].startswith("plan "))
                                                 or (state == "stuck" and cs and cs["kind"] == "design"))
                            else "nothing to redo")
            keep = "" if state == "waiting" and task["why"].startswith("replanned:") else "no plan change waits"
            confirm = base or ("" if (state == "waiting" and (task["why"] == "confirm Fable" or task["why"] == "plan ready: confirm"
                                                              or task["why"].startswith(("replanned:", "plan ")))) or tasks.held(task)
                               else "nothing to confirm")
```

and returns `"answer": answer, "redo": redo, "keep": keep`. `Hub.task_lever` routes `redo` and `keep` through
`tasks.fred` like the others (the `if lever in ("retry", "confirm")` that calls `advance()` becomes
`("retry", "confirm", "redo", "keep")`); `stop` on a redo is already handled by `fred`.

## 3.6 `Hub.answer_gap`, `Hub.edit_plan` and the routes

```python
    def answer_gap(self, task_id: str, text: str) -> tuple:
        """Fred's Answer to a Plan gap: the line joins Decisions, then the answer continues the step's session
        (Hub.pull continue, the STOP answer path). Returns (status, body)."""
        with self.tlock:
            info = self.task_levers(task_id)
            if info is None:
                return 404, {"error": "unknown task"}
            if info["answer"]:
                return 409, {"error": info["answer"]}
            if not text.strip():
                return 400, {"error": "empty answer"}
            task, cs, now = self.tasks[task_id], tasks.current_step(self.tasks[task_id]), time.time()
            line = plan.add_answer(self.folder, task, text)
            self._commit(task, [tasks._line(now, cs, "running", "running", f"plan gap answered by Fred: {redact.clip(text, 120)}")])
        status, body = self.pull(cs["session"], "continue", text)  # the task goes running in _ended, as any answer
        return status, dict(body, task=task_id, line=line) if status == 200 else body

    def edit_plan(self, task_id: str, text: str, part: int = 0) -> tuple:
        """Fred's in-place edit of the index or of part `part`, checked like the design step's plan."""
        with self.tlock:
            task = self.tasks.get(task_id)
            if task is None or not task.get("plan"):
                return 404, {"error": "unknown task or no plan"}
            cs = tasks.current_step(task)
            waits = task["state"] == "waiting" and (task["why"].startswith(("plan ", "asks: Plan gap:")))
            paused = task["owner"] == "fred" and not (cs and cs["state"] == "running")
            if not (waits or paused):
                return 409, {"error": "the plan can be edited while the task waits on it or is paused"}
            found = {"index": text if not part else plan.read(self.folder, task),
                     "parts": [{"n": p["n"], "kind": p["kind"], "title": p["title"],
                                "text": text if p["n"] == part else plan.read_part(self.folder, task, p["n"])}
                               for p in task["plan"]["parts"]]}
            later = [x for x in task["steps"] if x["n"] > task["plan"]["from"]]
            why = plan.check(found, later, self.cfg["plan_max_parts"], max(self.cfg["task_max_steps"] - task["plan"]["from"], 1))
            if why:
                return 409, {"error": "plan: " + why}
            rel = plan.write(self.folder, task, text, part)
            task["plan"].update(words=plan.words(found), kb=plan.kb(found))
            self._commit(task, [tasks._line(time.time(), cs, task["state"], task["state"],
                                            "plan edited by Fred" + (f": part {part}" if part else ""))])
            return 200, {"task": task_id, "file": rel, "words": task["plan"]["words"], "kb": task["plan"]["kb"]}
```

An edit of a part's text in `found` keeps the `# Part N:` head out (the window sends the body it got from
`GET /api/task` `parts`, which is the file whole; `edit_plan` strips a first line starting `# Part ` before the check
and `plan.write` writes the file with the head again: `plan.part_body(text) -> str` in Task 1's module, with
`tests/test_plan.py::test_part_body_drops_the_head`).

`Handler.do_POST`: `routes["/api/task/answer"] = self._task_answer`, `routes["/api/task/plan"] = self._task_plan`, and
the lever loop gains `"redo", "keep"`. Handlers:

```python
    def _task_answer(self, body):
        status, data = self.hub.answer_gap(self._text(body, "task"), self._text(body, "text"))
        return self._json(data, status)

    def _task_plan(self, body):
        part = body.get("part") or 0
        if not isinstance(part, int) or part < 0:
            return self._error(400, "part must be a number")
        status, data = self.hub.edit_plan(self._text(body, "task"), self._text(body, "text"), part)
        return self._json(data, status)
```

`Handler._task` adds to its dict: `"plan": plan.read(self.hub.folder, task)`, `"parts": {p["n"]: plan.read_part(
self.hub.folder, task, p["n"]) for p in (task.get("plan") or {}).get("parts", [])}`, `"replan_note": tasks.read_note(
self.hub.folder, task, cs["n"]) if cs and cs["kind"] == "replan" else ""`.

`task_row` adds `"plan": t.get("plan") or None`, `"redo": t.get("redo") or ""`, and in each step dict
`"part": s.get("part") or 0, "hard": bool(s.get("hard"))`.

## 3.7 The fake claude (README 3.12)

In `tests/fake_claude.py` `reply(text)`, after the `HANDOFF-OK` branch:

```python
    if "PLAN-OK" in text:
        m = re.search(r"each write step \(([\d, ]+)\)", text)
        ns = [int(x) for x in re.findall(r"\d+", m.group(1))] if m else [3]
        body += "\nPLAN\n" + PLAN_INDEX.format(steps="".join(PLAN_STEP.format(n=n) for n in ns)) + "END PLAN\n" + HANDOFF_BLOCK
    if "PLAN-SPLIT" in text:
        body += "\nPLAN\n" + PLAN_SPLIT + "END PLAN\nSUBPLAN 1 code Calc module\n" + PLAN_PART.format(f="calc.py") \
                + "END SUBPLAN\nSUBPLAN 2 code Report module\n" + PLAN_PART.format(f="report.py") + "END SUBPLAN\n" + HANDOFF_BLOCK
    if "PLAN-BAD" in text:
        body += "\nPLAN\n" + PLAN_INDEX.format(steps=PLAN_STEP.format(n=3)).replace("## Acceptance\n- tests pass\n", "") + "END PLAN\n" + HANDOFF_BLOCK
    if "PLAN-GAP" in text:
        body += "\n" + HANDOFF_BLOCK.replace("- (none)\n## Next", "- Plan gap: which file holds the ladder?\n## Next") \
                + "\nSTOP: Plan gap: which file holds the ladder?"
    if "REPLAN" in text and "REPLAN-ADD" not in text:
        body += "\n" + HANDOFF_BLOCK.replace("## Next\nGo on", "## Next\nGo on. Replan: a search step is needed first")
```

with `PLAN_INDEX`, `PLAN_STEP`, `PLAN_SPLIT`, `PLAN_PART` the fixtures of `tests/test_plan.py` (copied, not
imported: the fake runs as a separate process). In `prep()` (the `--json-schema` path), when the prompt starts with
"Replan the rest of a task": return `{"steps": [{"kind": "search", "goal": "find the week bucket"}] + <the remaining
steps parsed from the prompt's "- kind: goal" lines>, "why": "search first"}` when `REPLAN-ADD` is in the prompt,
else the remaining steps unchanged with why `no change`.

## 3.8 Tests (`tests/test_server.py`, class `TaskServerTest`; `tests/test_tasks.py`)

A task of steps `scout, design, code, test, verify` through `self.call("/api/task", ...)` with the fake claude; the
prompt words go in the task goal so every step's prompt carries them (`PLAN-OK` and `HANDOFF-OK` together: the
scout answers with the handoff, the design step with the plan and the handoff; the fake adds the plan only when the
prompt is a design step's, that is when it contains "You are the design step").

- `test_design_step_saves_the_plan_and_the_next_step_reads_it`: after the design step, `tasks/<id>/plan.md` exists
  with `## Goal`; `task["plan"]["from"] == 2`, `words > 0`; the chain has `plan saved: `; the code step's prompt
  (read from `self.hub.runs.meta(sid)["prompt"]` or the prompt file the fake was given) contains "The plan (follow it,
  do not change it):" and "Your part of the plan:\n### Step 3: code"; the chain line that started step 3 ends with
  `read: brief 02 · plan 0.4 KB · step 3 section`.
- `test_design_step_reads_the_raw_notes_whole` (D1 a): the design step's prompt contains the scout's raw note text
  (`add() is in calc.py:2`) and not the brief's fallback line; its `read:` note is `notes 01-01`.
- `test_design_step_has_the_design_turn_cap` (D2 a): the run's limits carry `max_turns == cfg["design_max_turns"]`
  on a `sonnet` design pick too.
- `test_split_plan_rebuilds_the_write_steps`: with `PLAN-SPLIT`, after the design step the steps read
  `scout, design, code (part 1), code (part 2), test, verify` with `checked == 4`; `plan/01-calc-module.md` and
  `plan/02-report-module.md` exist; chain `design split into 2 sub-plans: 2 code steps (Prep had 1)`; step 4's prompt
  carries `Your part of the plan:\n# Part 2: Report module`.
- `test_bad_plan_retries_then_sticks`: `PLAN-BAD`: the design step's first attempt ends `plan: missing: ## Acceptance`,
  retries once, then the task is `stuck` with that why.
- `test_plan_over_the_size_waits`: `cfg["plan_max_kb"] = 0.3`: the task waits, `why.startswith("plan ") and
  " KB, over 0.3" in why`; Confirm runs on (chain `plan accepted by Fred`); on a second task Redo design puts the
  design step back to `planned` with `task["redo"]` set to the why.
- `test_plan_hold_waits_for_confirm`: `cfg["plan_hold"] = True`: why `plan ready: confirm`; `POST /api/task/plan`
  with an edited index (an added Decisions line) answers 200 and the file carries it; a text without `## Goal`
  answers 409 `plan: missing: ## Goal`; Confirm starts step 3.
- `test_plan_gap_waits_and_the_answer_joins_decisions`: `PLAN-GAP` on the code step: why
  `asks: Plan gap: which file holds the ladder?`; `GET /api/task` levers `answer == ""`; `POST /api/task/answer
  {task, text: "config.json"}` answers 200 with `session`; `plan.md` Decisions ends with `- Fred, <today>: config.json`;
  chain `plan gap answered by Fred: config.json`; the task is `running`.
- `test_redo_design_keeps_done_steps`: a gap on step 4 (the test step done? no: make the chain `scout, design, code,
  code, verify` with `PLAN-OK` naming steps 3 and 4, the gap on step 4): Redo design leaves step 3 `done`, step 2 and
  4 `planned`, `current == 2`, `task["redo"]` the question; the design prompt then contains "Fred asked for this plan
  again" and "(done, kept)"; after it ends, step 3 is still done.
- `test_replan_line_inserts_a_replan_step_and_waits`: `REPLAN` on the scout (with `HANDOFF-OK`), goal with
  `REPLAN-ADD`: after the scout, steps read `scout, replan, design, code, test, verify`; the replan step runs with
  session `""` and ends `done` with `steps/02-replan.md` written; the task waits with `replanned: 1 steps added`;
  `task["replan"]["after"][0]["kind"] == "search"`; Confirm applies (`plan changed: 5 steps follow 02`, the steps
  read `scout, replan, search, design, code, test, verify`); on a second task Keep old plan drops it (`old plan kept
  by Fred`, the steps as before).
- `test_replan_auto_applies_without_confirm`: `cfg["replan_auto"] = True`: no wait, the chain carries
  `plan changed:` right after `replanned:`.
- `test_replan_refused_when_no_room`: `task_max_steps` equal to the chain length: chain `replan refused: no room`.
- `test_clear_keeps_the_plan_files`: Clear on a done task with a plan: `plan.md` and `plan/` remain, the streams go.
- `tests/test_tasks.py`: `test_fred_redo_resets_the_design_and_later_planned_steps`,
  `test_fred_keep_drops_the_replan_proposal`, `test_fred_confirm_covers_the_plan_waits` (the four why texts),
  `test_clear_keeps_plan_md_and_the_parts`.

Commit `plan 24 task 3: service: plan saved and checked, split, waits, replan run, levers and routes` with the test
count.

## 3.9 Drift guards

- `tasks.on_step_ended` is not edited; the plan checks feed `block_error` (README 3.11).
- Every wait is `tasks._task_to(task, "waiting", why, ...)` with the why texts of README 3.3; the window reads the
  why, never a new field.
- `Hub.pull` is unchanged; `answer_gap` calls it.
- The replan thread uses `self.briefing` as its flag; `_go_on` already waits on it.
- `start_step` composes; nothing is copied into the task folder but the plan files and the notes (D3 a).
