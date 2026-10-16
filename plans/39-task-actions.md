# Plan 39: Task actions on the task page and on any step. Guided implementation plan

> Design: [../design/brainstorm/2026-10-16-task-actions.md](../design/brainstorm/2026-10-16-task-actions.md) (decided:
> option 2, the dock placement, D1-D6 all (a); section 6 is the sketch this plan expands, section 7 its acceptance).
> Master: [../PLAN.md](../PLAN.md). Rules: [../CLAUDE.md](../CLAUDE.md). Contracts this plan extends:
> [36 next step](36-next-step/README.md) (sections 3.1, 3.4) and its [design guideline](../design/brainstorm/2026-10-15-next-step.md);
> placement binds to plan 38 U3 and U11 ([38-ui-audit-fixes.md](38-ui-audit-fixes.md)).
>
> Start state: `42ecd0f` (branch `claude/brainstorm-task-actions`: plan 38 tasks 1-3 and 8 on top of `claude/nice-cori-d93jgp`).
> Anchor by the quoted lines, never by line numbers. Every edit below is an anchored edit of the function named with it;
> no file is replaced whole.

Status: written 2026-10-16, no code changed. Decisions D1-D6 answered (a) by Fred on 2026-10-16 (section 3). Every task
writes its tests first where a test can see the change (tasks, server, the Board's pure render functions) and checks the
Board headless with `tests/fake_claude.py` as plan 36 Task 4 did. Five tasks, one commit each:
`plan 39 task N: <what> (<n> tests OK)`.

## 1. Findings

What the code does today and what changes, with every caller of each helper the plan touches (read on 42ecd0f).

| Id | Where | Anchor (quoted) | Today | Change (task) |
|---|---|---|---|---|
| F1 | `console/server.py` `Hub._next_source` | `source = tasks.current_step(task)` and `or source["n"] != len(task["steps"])` / `or any(s["n"] > source["n"] for s in task["steps"])):` / `return None, "Next steps start from the latest step"` | the only source is the current, last step | the source is `tasks.step(task, source_n)`; a done step with a session and a saved note or final reply is a source (D2 a); a later unfinished step refuses; the latest replied chat is closed by the branch (D3 a); task conditions unchanged (D5 a) (Task 1) |
| F1c | callers of `_next_source` | `next_availability` (`found, why = self._next_source(task.get("id"), source["n"] if source else 0,`), `preview_next` (`found, why = self._next_source(tid, n, sid)`), `request_next` (`found, why = self._next_source(payload["task"], payload["source_step"], payload["source_session"])`) and, through `preview_next`, `request_next`'s second preview | all pass the current step or the client's `source_step` | unchanged call sites; `next_sources` is a fourth caller (Task 1) |
| F2 | `console/server.py` `Hub.next_availability` | `return {"available": not why, "reason": why, "source_step": source["n"] if source else 0,` | the latest step's answer; `task_levers["add_next"]` and GET `next_step` read it | unchanged: the task-level answer stays the latest step's (the task conditions are the same for every source, and a live latest turn refuses every older source too). New `Hub.next_sources(task)` answers per step (Task 1) |
| F3 | `console/server.py` `Handler._task` | `"next_step": self.hub.next_availability(task),` | GET /api/task has `levers`, `next_step`, `step_levers` | gains `"sources": {"01": "", "02": "no saved note or final reply", ...}` (Task 1) |
| F4 | `console/tasks.py` `append_step` | `def append_step(task: dict, kind: str, goal: str, pick: str = "", now: float = None) -> dict:` / `source = current_step(task)` / `if kind not in NEXT_KINDS or source is None or source["n"] != len(task["steps"]):` / `n = source["n"] + 1` | the source is the current last step; the new number is `source + 1`; the source chat is closed when running | `source=None` keyword (None: the current step); the new number is `len(task["steps"]) + 1`; `checked = source["n"]` for a verify; `current` and `last_good` go to the source; any replied chat still `running` (the source or the latest step) is closed done (D3 a) (Task 1) |
| F4c | callers of `append_step` | `request_next`: `step = tasks.append_step(updated, payload["kind"], payload["instructions"],` ; tests: `tests/test_tasks.NextStepTest` (9 calls), none in `test_server.py` (it goes through the API) | one caller in code | passes `source=` and logs the closed chat and the lineage on the chain (Task 1) |
| F5 | `console/server.py` `Hub._next_route` | `step = tasks._blank(source["n"] + 1, kind, "", requested if requested != "auto" else "",` / `route = self._route_for(task, step)` | the routed stand-in is numbered `source + 1` and routed with the task's `last_good` (the latest step) as the previous rung and note | numbered `len(task["steps"]) + 1`; routed with `last_good` = the source, as the append will set it (Task 1) |
| F6 | `console/server.py` `Hub.request_next` | `self._commit(updated, [tasks._line(time.time(), step, "reserved", "planned",` / `f"manual request {request_id}")])` | one chain line, no lineage | the line reads `manual request <id> from step 02`; a chat closed by the branch logs `running -> done (closed by step 04)` (Task 1) |
| F7 | `console/server.py` `task_row` | `"end_commit": s.get("end_commit", ""), "brief_meta": s.get("brief_meta"),` | the list's step rows carry no lineage | `"source_step": s.get("source_step") or 0` (Task 4) |
| F8 | `console/server.py` `Hub.start_step` | `if "source_step" in s:  # plan 36: a manual step reads its saved handover package, not a fresh brief` / `read = [f"handover from step {s['source_step']:02d}"]` | already reads the step's own `received-handoff.md` and names `source_step` | unchanged: a branch from 02 logs `handover from step 02` as it is |
| F9 | `console/server.py` `Hub.levers` | `if task and task.get("progression") == "manual":  # plan 36: a manual chain's steps are not branch points` / `out[lever] = base or "Next steps start from the latest step"` | only the newest chat step keeps its turns | unchanged (CLAUDE.md: `Hub.levers` alone decides Continue / Verify / Handoff / Escalate; an older session is never continued, verified or handed off in place; a branch is a fresh session, `resume=None`) |
| F9c | `current_step` users touched by a branch | `_next_step` (`cs = tasks.current_step(task)`: a done current step below `len(steps)` skips done steps and finds the reserved one), `task_levers` (`state, owner, cs, nxt = ...`), `task_row` (`cs = tasks.current_step(t)`), `_task` (`last, cs = task["last_good"], tasks.current_step(task)`), `levers` (`cs = tasks.current_step(task) if task else None`), `tasks.fred`, `tasks.on_step_ended` | between the reservation and `start_step`, `current` is the source (today the latest) | the same window now shows the older source as current for the one call that reserves and starts (`request_next` calls `start_step` at once); `_next_step` skips the done steps after it (`x["state"] != "done"`) and returns the reserved step, so a hub pass in that window starts nothing else. No change |
| F10 | `web/app.js` `inspTask` | `const levers = \`<div class="v-levers">${lv.done === "" ? \`<button class="btn" data-tact="done" data-tid="${tid}">Mark done</button>\` : ""}` and the head's `${busyBox(t.id)}` | the task page is a plain pane with Mark done / Delete at its foot and no next action | the page docks like a step page (`dock(...)`); the bar carries Add next step, Verify, Continue, Finish task, Hand off, Delete (Task 2) |
| F11 | `web/app.js` `nextSecondary` | `const lv = d.levers || {}, tid = esc(t.id);` / `const ho = lv.handoff === "" ?` / `const nx = lv.next === "" ?` | reads `task_levers`, which never carries `handoff` or `next`: Hand off and Start new task never render (plan 36 Task 3 slip) | reads `d.step_levers` (Task 2) |
| F12 | `web/app.js` `nextActions` | `const cur = t.current == null ? s.n : t.current, open = nextOpen && nextOpen.key === nextKey(t, s);` / `if (!s.session \|\| s.n !== cur \|\| open \|\| (s.state === "running" && !chatReplied(s))) return "";` | buttons only on the current step | an older step reads `d.sources[two(s.n)]`: Add step from here and Verify this step when `""`, one disabled button with the reason otherwise (Task 3) |
| F13 | `web/app.js` `histFoot` | `const why = ns.available === false && ns.reason ? ns.reason : "Next steps start from the latest step";` | the footer explains and links to the latest step | keeps only Go to step NN (Task 3) |
| F14 | `web/app.js` `stepFooter` | `if (!s.session \|\| s.n !== current) return steps.length > 1 ? histFoot(t, s, d) : "";` before `if (open) return nextFormHtml(t, s, row, d);` | an older step can never show the form | the open check comes first (Task 3) |
| F15 | `web/app.js` the form's source: `openNextForm`, `nextPreview`, `startNextStep`, `nextReseed` | `const t = bd && bd.task, s = t && t.steps.find((x) => x.n === t.current);` (three times) and `const t = bd && bd.task, s = t && t.steps.find((x) => x.n === t.current);` in `nextReseed` | the form is bound to `t.current` | bound to the source held in `nextOpen` through its key (task + step + session); `openNextForm(tid, kind, n)` and `verifyNext(tid, n)` take the step (Task 3) |
| F15c | `nextOpen` users | the `input` listener (`if (nextOpen && e.target.id === "b-ninstr")`), the `change` listener (`const d = nextDraft[nextOpen.key];`), `nextReseed`, `nextFormHtml` (`nextView.key === nextKey(t, s)`), `nextActions`, `stepFooter`, `openNextForm`, `nextPreview`, `cancelNextForm`, `startNextStep`, the Escape handler (`if (e.key === "Escape" && nextOpen)`) | `nextOpen = { tid, key }` | the shape stays `{tid, key}`; `nextSource(bd)` resolves the step from the key (Task 3) |
| F16 | `web/app.js` `nextFormHtml` | `<div class="nfrom"><span class="lbl">Next step</span><span class="m">From ${two(s.n)} ${esc(s.kind)}</span>` | the source line | unchanged text; one line under it when the source is not the latest step (D6 a) (Task 3) |
| F17 | `web/app.js` `VERIFY_DEFAULT`, `nextInstr` | `const VERIFY_DEFAULT = "Check the previous step against its goal, tests and unresolved risks. Do not edit files: " +` / `return kind === "verify" ? VERIFY_DEFAULT : nextSeed(t, d, s);` | one text for every source | `verifyDefault(n)` names the step it checks (D4 a) (Task 3) |
| F18 | `web/app.js` `nextSeed` | `const prev = t.steps.find((x) => x.n === s.n - 1) \|\| s;` | the seed is the Next section of the step before the source (a plan 36 slip: for source 01 it is its own note, for source 02 it is 01's) | the source's own note or brief (Task 3) |
| F19 | `web/app.js` `receivedNote`, `recvPane` | `const prev = t.steps.find((x) => x.n === s.n - 1), meta = (prev && prev.brief_meta) \|\| {};` (receivedNote); `const prev = t.steps.find((x) => x.n === s.n - 1), brief = (d.briefs \|\| {})[String(s.n - 1)] \|\| "", meta = (prev && prev.brief_meta) \|\| {};` (recvPane) | lineage assumed `n - 1` | both read `s.source_step \|\| s.n - 1` (Task 4) |
| F20 | `web/app.js` `chainStepHtml` | `s.part ? '<span title="a write step the design step made">from plan</span>' : ""].filter(Boolean).join(" · ");` | the row's second line | gains `from 02` when `source_step` is set and is not `n - 1` (Task 4) |
| F21 | `plans/36-next-step/README.md` 3.1 and the Excluded line | `eligible. Other paused, stopped, failed/stuck, and handed tasks must first use their existing` / `recovery/resume/next-task actions. Historical steps are inspectable, not branch points.` and `Excluded: branching/DAG UI, arbitrary old-step forks, global workflow builder, auto-running` | the plan 36 contract | amended to say older done steps are sources since plan 39 (Task 5) |

Not changed, and why: `sentWords` and `scoutHint` read `brief_meta` of step `n - 1` (a brief's word count, which a manual
step never receives: it reads its package); `Hub.levers` (F9); `_next_package`, `received_manifest`, `start_step` (F8:
they already take the source as given); `web/style.css` (the dock, `.nform .nfrom`, `.hfoot` and `.lr.sub` exist).

Tests that pin the old rule and change with Task 1 (each amended in its task, never deleted): `tests/test_server.py`
`test_preview_refuses_an_unknown_task_a_foreign_session_and_unsafe_ids` (`"Next steps start from the latest step", over)`
and its "a historical step is not a branch point" tail), `test_duplicate_request_id_is_stable_and_a_stale_revision_is_refused`
(`race[1]["error"]), (409, "Next steps start from the latest step"))`); `tests/test_tasks.py`
`test_append_step_refuses_a_kind_goal_or_source_it_cannot_take` (the `late` task: still refused, with the new reason);
`tests/test_web.py` `test_historical_step_points_to_the_latest`, `test_replied_chat_footer_offers_continue_and_next_step`,
`test_verify_seeds_a_concrete_default`, `test_instructions_seed_from_the_previous_next_section`,
`test_a_reseed_shows_in_the_open_field` (Tasks 2 and 3). The Hub.levers assertions (`self.hub.levers(sid)["continue"]`
reads "Next steps start from the latest step") stay as they are: F9.

## 2. Tasks, in order

| # | Delivers | Files | Tests |
|---|---|---|---|
| 1 | any done step as a source: `_next_source` takes a step, `next_sources` and GET `sources`, `append_step(source=)`, numbering, `last_good`, the chain lines, D2 / D3 / D5 | `console/server.py`, `console/tasks.py` | test_tasks +3, test_server +4, 3 amended |
| 2 | the task page dock: Add next step, Verify, Continue (D1), Finish task, Hand off, Delete; the `step_levers` fix (F11) | `web/app.js` | test_web +2, 1 amended |
| 3 | per-step actions on an older step: the dock buttons, the footer, the form bound to `nextOpen`'s source, the shared-tree line (D6), the Verify default (D4), the seed (F18) | `web/app.js` | test_web +3, 4 amended |
| 4 | lineage in the list: `task_row` `source_step`, the `from 02` tag, `receivedNote` and `recvPane` by source | `console/server.py`, `web/app.js` | test_server +1, test_web +1 |
| 5 | headless pass, Fred's live check, PLAN.md, plan 36 README 3.1 and Excluded | tests (scratch), `PLAN.md`, `plans/36-next-step/README.md` | none |

Each task: write the tests, see them fail, place the code, run `py -m unittest discover -s tests` and
`node --check web/app.js`, commit `plan 39 task N: <what> (<n> tests OK)`.

### Task 1: any done step as a source (D2 a, D3 a, D5 a)

Tests first.

`tests/test_tasks.py`, in `NextStepTest` after `test_append_step_finishes_a_running_chat_and_drops_the_legacy_flag`:

```python
    def test_append_step_from_an_older_done_step_takes_the_next_number(self):
        """Plan 39 Task 1 (D2 a): any done step with a session is a source; the new step is numbered after the last,
        is checked against its source when a verify, and current / last_good point at the source until it starts."""
        task = self.manual()  # step 01 scout, done, manual
        tasks.append_step(task, "code", "write it", now=NOW)
        run(task, 2)
        self.assertEqual(end(task)[0], "manual")
        tasks.append_step(task, "verify", "check it", now=NOW)
        run(task, 3, "opus", "high")
        self.assertEqual(end(task, verdict="FAIL", verdict_detail="3 != 4")[0], "manual")
        new = tasks.append_step(task, "verify", "check it again", now=NOW + 300, source=tasks.step(task, 2))
        self.assertEqual([s["n"] for s in task["steps"]], [1, 2, 3, 4])
        self.assertEqual((new["n"], new["checked"], new["source_step"], new["source_session"]), (4, 2, 2, "s2"))
        self.assertEqual((task["current"], task["last_good"], task["state"], task["owner"]), (2, 2, "running", "service"))
        self.assertEqual(task["steps"][2]["state"], "done")  # step 03 stays as it was
        failed = tasks.append_step(task, "code", "fix what 03 found", now=NOW + 400, source=tasks.step(task, 3))
        self.assertEqual((failed["n"], failed["source_step"], failed["checked"]), (5, 3, 0))  # a FAIL verify is a source

    def test_append_step_refuses_an_older_step_that_is_not_done_or_has_unfinished_followers(self):
        """Plan 39 Task 1 (D5 a): a planned or running later step refuses the branch; so does a source that is not done."""
        task = self.manual()
        tasks.append_step(task, "code", "write it", now=NOW)
        run(task, 2)  # step 02 runs: 01 is done but a later step has not finished
        with self.assertRaises(ValueError) as refused:
            tasks.append_step(task, "code", "again", now=NOW, source=tasks.step(task, 1))
        self.assertEqual(str(refused.exception), "a later step has not finished")
        with self.assertRaises(ValueError) as refused:  # the running code step itself is no source
            tasks.append_step(task, "code", "again", now=NOW, source=tasks.step(task, 2))
        self.assertEqual(str(refused.exception), "only a done step is a source")
        with self.assertRaises(ValueError):  # a step that is not this task's
            tasks.append_step(task, "code", "again", now=NOW, source=dict(tasks.step(task, 1)))
        self.assertEqual(len(task["steps"]), 2)

    def test_a_branch_closes_the_latest_replied_chat(self):
        """Plan 39 Task 1 (D3 a): branching from an older step while the latest step is a chat still in running
        closes that chat done, as the latest-step append does for its own source chat."""
        task = make(("scout",))
        task["progression"] = "manual"
        run(task, 1)
        end(task)
        chat = tasks.chat_step(2, "what next", "w2", "sonnet", "medium", NOW + 10)
        chat.update(source_step=1, source_session="s1")
        task["steps"].append(chat)
        task.update(current=2, last_good=1, state="running", owner="service")
        new = tasks.append_step(task, "code", "do it from 01", now=NOW + 20, source=tasks.step(task, 1))
        self.assertEqual((new["n"], new["source_step"]), (3, 1))
        self.assertEqual((chat["state"], chat["ended"]), ("done", NOW + 20))
```

Amend `test_append_step_refuses_a_kind_goal_or_source_it_cannot_take`: the `late` block keeps its `assertRaises` and
gains the reason:

```python
        with self.assertRaises(ValueError) as refused:
            tasks.append_step(late, "code", "again", now=NOW)
        self.assertEqual(str(refused.exception), "a later step has not finished")  # plan 39: 02 is planned, not done
```

`tests/test_server.py`, in `NextStepServerTest`. First give `source_of` and `start_next` a step: amend

```python
    def source_of(self, tid, kind="code", instructions="do the next thing", model="auto"):
        src = tasks.current_step(self.hub.tasks[tid])
```

to

```python
    def source_of(self, tid, kind="code", instructions="do the next thing", model="auto", at=0):
        task = self.hub.tasks[tid]
        src = tasks.step(task, at) if at else tasks.current_step(task)  # plan 39: any done step may be the source
```

and `start_next(self, tid, kind="code", instructions="do the next thing", model="auto", expect=200)` gains `at=0`,
passing it on: `body = self.source_of(tid, kind, instructions, model, at)`. Then, after
`test_a_reserved_step_that_recorded_a_session_was_launched`:

```python
    # -- plan 39 Task 1: any done step as a source ------------------------------------------------------------

    def three_steps(self):
        """01 scout, 02 code, 03 verify, all done at the manual boundary (the fake's verify passes)."""
        tid = self.one_step_task()
        self.start_next(tid, "code", "add the missing case HANDOFF-OK")
        self.boundary(tid, 2)
        self.start_next(tid, "verify", "check it VERDICT-PASS")
        self.boundary(tid, 3)
        return tid

    def test_sources_name_every_done_step_and_the_reason_for_the_rest(self):
        tid = self.three_steps()
        task = self.task(tid)[1]
        self.assertEqual(task["sources"], {"01": "", "02": "", "03": ""})
        self.assertEqual(task["levers"]["add_next"], "")  # the task-level answer stays the latest step's
        self.start_next(tid, "code", "the next thing SLOW")
        self.until(tid, self.at(4), "step 4 runs")
        task = self.task(tid)[1]
        self.assertEqual(task["sources"]["04"], "Available when this turn finishes")
        self.assertEqual(task["sources"]["02"], "a later step has not finished")  # D5 a: nothing branches while a step runs
        self.assertEqual(self.call("/api/task/stop", {"task": tid})[0], 200)
        self.until(tid, lambda t: t["state"] == "stopped", "stopped")
        self.wait_idle(self.hub.tasks[tid]["steps"][3]["session"])  # the interrupted run has ended
        task = self.task(tid)[1]
        self.assertEqual(task["sources"]["02"], "a later step has not finished")  # 04 failed: Retry or Finish first
        self.assertEqual(task["sources"]["04"], "use the existing recovery action for this step")

    def test_a_branch_from_an_older_step_takes_the_next_number_and_its_own_handover(self):
        tid = self.three_steps()
        status, pv = self.call("/api/task/next/preview", self.source_of(tid, "verify", "check 02 again VERDICT-PASS", at=2))
        self.assertEqual(status, 200, pv)
        self.assertEqual(pv["source"]["step"], 2)
        self.assertIn(f"task {tid}, step 02", pv["text"])
        data, _ = self.start_next(tid, "verify", "check 02 again VERDICT-PASS", at=2)
        self.assertEqual(data["step"], 4)
        task = self.until(tid, self.at(4), "step 4 starts")
        new = task["steps"][3]
        self.assertEqual((new["source_step"], new["checked"], task["current"]), (2, 2, 4))
        self.assertEqual([s["state"] for s in task["steps"][:3]], ["done", "done", "done"])  # 03 stays
        folder = self.folder / "tasks" / tid / "04-verify"
        self.assertIn(f"Handover from task {tid}, step 02", folder.joinpath("received-handoff.md").read_text(encoding="utf-8"))
        self.assertIn("saved handover from step 02", folder.joinpath("received.md").read_text(encoding="utf-8"))
        chain = self.task(tid)[1]["chain"]
        self.assertTrue(any(c["step"] == 4 and c["why"].endswith("from step 02") for c in chain), chain)
        self.assertIn("handover from step 02", task["steps"][3]["notes"][-1])  # start_step read the step's own package
        self.boundary(tid, 4)
        self.assertEqual(self.hub.tasks[tid]["last_good"], 4)

    def test_a_branch_closes_the_latest_replied_chat_and_logs_it(self):
        tid = self.one_step_task()
        self.start_next(tid, "chat", "what should we do next?")
        task = self.until(tid, self.at(2), "the chat step starts")
        self.wait_idle(task["steps"][1]["session"])
        self.assertEqual(self.task(tid)[1]["sources"]["01"], "")  # D3 a: a replied chat does not block the branch
        data, _ = self.start_next(tid, "code", "take the other road", at=1)
        self.assertEqual(data["step"], 3)
        task = self.until(tid, self.at(3), "step 3 starts")
        self.assertEqual(task["steps"][1]["state"], "done")
        chain = self.task(tid)[1]["chain"]
        self.assertTrue(any(c["step"] == 2 and c["to"] == "done" and c["why"] == "closed by step 03" for c in chain), chain)

    def test_a_duplicate_branch_request_returns_the_same_step(self):
        tid = self.three_steps()
        body = self.source_of(tid, "code", "from two", at=2)
        status, pv = self.call("/api/task/next/preview", body)
        self.assertEqual(status, 200, pv)
        first = self.call("/api/task/next", dict(body, revision=pv["revision"], request_id="c" * 32))
        again = self.call("/api/task/next", dict(body, revision=pv["revision"], request_id="c" * 32))
        self.assertEqual((first[0], again[0], first[1]["step"], again[1]["step"]), (200, 200, 4, 4))
        self.assertEqual(len(self.hub.tasks[tid]["steps"]), 4)
```

Amend two tests. In `test_preview_refuses_an_unknown_task_a_foreign_session_and_unsafe_ids`, the reason for a foreign
session or step is now `"unknown source step"` (both `assertEqual` lines that read
`"Next steps start from the latest step"`), and the tail becomes the opposite claim:

```python
        self.start_next(tid, "code", "the next thing")  # plan 39: a historical done step is a source
        self.boundary(tid)
        status, pv = self.call("/api/task/next/preview", base)
        self.assertEqual((status, pv["source"]["step"]), (200, 1), pv)
        self.assertEqual(len(self.hub.tasks[tid]["steps"]), 2)  # a preview reserves nothing
```

In `test_duplicate_request_id_is_stable_and_a_stale_revision_is_refused` the race is refused because step 02 runs, not
because 01 is historical: `body = self.source_of(tid, "code", "add the guard SLOW")` (the fake waits for an interrupt, so
02 cannot reach the boundary during the test) and
`self.assertEqual((race[0], race[1]["error"]), (409, "a later step has not finished"))`.

Code. `console/tasks.py`, `append_step` whole (anchor: `def append_step(task: dict, kind: str, goal: str, pick: str = "", now: float = None) -> dict:`
through `return new`):

```python
def append_step(task: dict, kind: str, goal: str, pick: str = "", now: float = None, source: dict = None) -> dict:
    """Reserve one manual successor of `source` (None: the current step). Plan 39: any done step of the task with a
    session is a source; the new number is the next free one, never the source's plus one; `current` and `last_good`
    point at the source until start_step moves `current`. Launch and source readiness belong to Hub."""
    source = current_step(task) if source is None else source
    if kind not in NEXT_KINDS or source is None or not any(x is source for x in task["steps"]) or not source["session"]:
        raise ValueError("no appendable source step")
    if source["state"] != "done" and not (source["kind"] == CHAT and source["state"] == "running"):
        raise ValueError("only a done step is a source")
    if any(x["state"] != "done" and not (x["kind"] == CHAT and x["state"] == "running")
           for x in task["steps"] if x["n"] > source["n"]):
        raise ValueError("a later step has not finished")
    if not isinstance(goal, str) or not goal.strip() or len(goal) > STEP_GOAL_MAX:
        raise ValueError("step instructions must be 1 to 1000 characters")
    if task.get("progression") not in (None, "manual"):
        raise ValueError("task does not use manual progression")
    n = len(task["steps"]) + 1
    new = _blank(n, kind, goal.strip(), pick, checked=source["n"] if kind == "verify" else 0)
    new.update(source_step=source["n"], source_session=source["session"])
    task["steps"].append(new)
    task["progression"] = "manual"
    task.pop("chat", None)
    task["current"] = source["n"]
    task["last_good"] = source["n"]
    task["owner"], task["state"], task["why"] = "service", "running", ""
    task["updated"] = time.time() if now is None else now
    for x in task["steps"]:  # D3 a: a replied chat still in running (the source, or the latest step) is closed by the branch
        if x is not new and x["kind"] == CHAT and x["state"] == "running":
            x.update(state="done", ended=task["updated"])
    return new
```

The `fresh` case of the existing test (a task that never ran, `current` 0) still raises "no appendable source step";
the `late` case raises "a later step has not finished".

`console/server.py`, `Hub._next_source` whole (anchor: `def _next_source(self, task_id, source_n, source_sid):` through
`return (task, source, row, meta), ""`):

```python
    def _next_source(self, task_id, source_n, source_sid):
        """The step a next step may start from, or why not. Plan 39 (D2 a): any done step with a session and a saved
        note or final reply is a source, a FAIL verify included; the latest step keeps its plan 36 fallback (built
        from the last reply). The task conditions are plan 36's, unchanged (D5 a): a running automatic chain, a stuck
        or a stopped task refuse and keep Retry / Resume / Stop. A replied latest chat is closed by the branch (D3 a)."""
        task = self.tasks.get(task_id) if isinstance(task_id, str) and tasks.safe_id(task_id) else None
        if task is None:
            return None, "unknown task"
        source = (next((s for s in task["steps"] if s["n"] == source_n), None)
                  if isinstance(source_n, int) and not isinstance(source_n, bool) else None)
        if source is None or not isinstance(source_sid, str) or not source_sid or source["session"] != source_sid:
            return None, "unknown source step"
        latest = task["steps"][-1]
        if source is not latest and source["state"] != "done":
            return None, "only a done step is a source"
        if any(x["state"] != "done" and not (x["kind"] == tasks.CHAT and x["state"] == "running")
               for x in task["steps"] if x["n"] > source["n"]):
            return None, "a later step has not finished"
        if task.get("progression") not in (None, "manual"):
            return None, "task uses automatic progression"
        if task.get("briefing") or task["id"] in self.briefing:
            return None, "handover is still being prepared"
        row, meta = self.session(source_sid), self.runs.meta(source_sid) or {}
        if self.runs.is_live(source_sid) or (row is not None and row["run_live"]):
            return None, "Available when this turn finishes"
        if row and (row["interrupted"] or row["stopped"] or row["failed"] or row["denied"]):
            return None, "use the existing recovery action for this step"
        reply = self.final_message(source_sid)[0] if meta else ""
        if not reply and source["state"] == "done":
            reply = tasks.read_step_file(self.folder, task, source, "notes.md")
            saved = tasks.read_note(self.folder, task, source["n"])
            if saved:
                reply += "\n\nHANDOFF\n" + saved.split("\n\n", 1)[-1] + "\nEND HANDOFF"
        if source is not latest and not reply.strip():
            return None, "no saved note or final reply"
        if (row and row["stop_question"]) or tasks.reply_question(reply):
            return None, "answer the pending question first"
        if not meta.get("ended") and source["state"] != "done":
            return None, "Available when this turn finishes"
        chat_turn = latest["kind"] == tasks.CHAT and latest["state"] == "running"
        if source is not latest and chat_turn:  # D3 a: the branch closes the latest chat once its turn is over
            last_row = self.session(latest["session"]) if latest["session"] else None
            if (latest["session"] and self.runs.is_live(latest["session"])) or (
                    last_row is not None and (last_row["run_live"] or last_row["stop_question"])):
                return None, "Available when the latest turn finishes"
        boundary = (task.get("progression") == "manual" and latest["state"] == "done" and task["owner"] == "fred"
                    and task["state"] == "waiting" and (task["why"] == "choose next step" or
                    task["why"].startswith("VERDICT: FAIL")))
        reopened = task["state"] == "done" and latest["state"] == "done"
        legacy_chat = bool(task.get("chat") and chat_turn and task["state"] in ("running", "done"))
        manual_chat = bool(task.get("progression") == "manual" and chat_turn and task["state"] == "running")
        if not (boundary or reopened or legacy_chat or manual_chat):
            return None, f"task is {task['state']}"
        return (task, source, row, meta), ""
```

For the latest step every answer is the one plan 36 gave, except that a bad step or session now reads
`unknown source step` (it was `Next steps start from the latest step`, which is no longer true).

After `next_availability` (anchor: its last line `"source_session": source.get("session", "") if source else ""}`), add:

```python
    def next_sources(self, task) -> dict:
        """Plan 39: GET /api/task `sources`, step number (two digits) -> "" when the step may be the source of a next
        step, else the reason. _next_source once per step, so the Board shows a button only where the service would
        accept the request and reproduces no rule of its own (plan 36 3.4)."""
        return {f"{s['n']:02d}": self._next_source(task.get("id"), s["n"], s.get("session", ""))[1]
                for s in task["steps"]}
```

`Hub._next_route`: replace

```python
        step = tasks._blank(source["n"] + 1, kind, "", requested if requested != "auto" else "",
                            checked=source["n"] if kind == "verify" else 0)
        route = self._route_for(task, step)
```

with

```python
        step = tasks._blank(len(task["steps"]) + 1, kind, "", requested if requested != "auto" else "",
                            checked=source["n"] if kind == "verify" else 0)
        route = self._route_for(dict(task, last_good=source["n"]), step)  # plan 39: the previous note and rung are the source's
```

`Hub.request_next`: replace

```python
            updated = copy.deepcopy(task)
            step = tasks.append_step(updated, payload["kind"], payload["instructions"],
                                     payload["model"] if payload["model"] != "auto" else "", time.time())
```

with

```python
            updated, now = copy.deepcopy(task), time.time()
            closing = [x for x in updated["steps"] if x["kind"] == tasks.CHAT and x["state"] == "running"]  # D3 a
            step = tasks.append_step(updated, payload["kind"], payload["instructions"],
                                     payload["model"] if payload["model"] != "auto" else "", now,
                                     source=tasks.step(updated, source["n"]))
```

and replace

```python
                self._commit(updated, [tasks._line(time.time(), step, "reserved", "planned",
                                                   f"manual request {request_id}")])
```

with

```python
                lines = [tasks._line(now, x, "running", "done", f"closed by step {step['n']:02d}") for x in closing]
                lines.append(tasks._line(now, step, "reserved", "planned",
                                         f"manual request {request_id} from step {source['n']:02d}"))
                self._commit(updated, lines)
```

`Handler._task`: after `"next_step": self.hub.next_availability(task),` add
`"sources": self.hub.next_sources(task),`.

Check: `py -m unittest tests.test_tasks tests.test_server` green with the 7 new and 3 amended tests; the four Linux
baseline failures of plan 38's History (test_tray, test_redact, test_usage, test_window) are not this plan. Read the
chain of a branch in `tasks/<id>/chain.jsonl`: `reserved -> planned (manual request .. from step 02)`.

### Task 2: the task page dock (D1 a)

Tests first, `tests/test_web.py`, in `NextStepUITest`:

```python
    def test_task_page_dock_shows_each_action_only_where_the_service_allows_it(self):
        """Plan 39 Task 2: the task page's dock bar reads task_levers for Add next step, Finish task and Delete, and
        step_levers for Continue and Hand off; Add next step is the filled button, else Finish task."""
        snap = {"sessions": [{"id": "s2", "state": "idle", "run_live": False}], "tasks": [], "versions": {}, "projects": []}
        t = "{id: 't', current: 2, steps: [{n: 1, session: 's1', state: 'done', kind: 'scout'}, {n: 2, session: 's2', state: 'running', kind: 'chat'}]}"
        html = render(self._setup(snap=snap) + f"taskButtons({t}, {{levers: {{add_next: '', done: '', clear: ''}}, "
                      "step_levers: {continue: '', handoff: ''}, next_step: {source_step: 2}})")
        for text in ('class="btn sm go" data-tact="nextopen" data-tid="t" data-n="2"', 'data-tact="nextverify" data-tid="t" data-n="2"',
                     'data-tact="gochat" data-tid="t" data-n="2"', 'data-tact="done"', 'data-tact="handoff"', 'data-tact="clear"'):
            self.assertIn(text, html)
        self.assertLess(html.index("Add next step"), html.index("Finish task"))
        self.assertLess(html.index("Finish task"), html.index("Delete"))
        off = render(self._setup(snap=snap) + f"taskButtons({t}, {{levers: {{add_next: 'task is stuck', done: '', clear: 'task is stuck'}}, "
                     "step_levers: {continue: 'still working', handoff: 'still working'}}})")
        self.assertIn('disabled title="task is stuck">Add next step', off)
        self.assertIn('class="btn sm go" data-tact="done"', off)  # the primary falls to Finish task
        for text in ("Verify", "Continue", "Hand off", "Delete"):
            self.assertNotIn(text, off)

    def test_hand_off_and_start_new_task_read_the_step_levers(self):
        """Plan 39 Task 2 (plan 36 Task 3 slip): the Board's levers are task_levers, which never carry handoff or next."""
        html = render(self._setup() + "nextSecondary({id: 't'}, {levers: {handoff: '', next: ''}, step_levers: {handoff: 'x', next: 'y'}})")
        self.assertEqual(html, "")
        html = render(self._setup() + "nextSecondary({id: 't'}, {levers: {}, step_levers: {handoff: '', next: ''}})")
        self.assertIn("Hand off", html)
        self.assertIn("Start new task", html)
```

Amend `test_replied_chat_footer_offers_continue_and_next_step`: the first `render` call's data becomes
`{levers: {add_next: '', done: ''}, step_levers: {handoff: '', next: ''}}` (the `dock` render keeps its data).

Code, `web/app.js`.

1. `nextSecondary`: replace `const lv = d.levers || {}, tid = esc(t.id);` (the first line of that function; the same
   line opens `nextActions` after its `const cur ...` line, so anchor on the function head
   `function nextSecondary(t, d) {`) with
   `const lv = d.step_levers || {}, tid = esc(t.id);  // plan 39: Hand off and Start new task are session levers, never task_levers`.

2. Before `function inspTask(t, d, row) {` add:

```js
function latestStep(t) {  // plan 39: the step with the highest number (the only one Continue and Hand off can reach)
  return (t.steps || []).reduce((a, x) => (x.n > (a ? a.n : 0) ? x : a), null);
}
function taskButtons(t, d) {  // plan 39 Task 2: the task page's dock bar; each button only where the service allows it
  const lv = d.levers || {}, sl = d.step_levers || {}, ns = d.next_step || {}, tid = esc(t.id), last = latestStep(t);
  const n = ns.source_step || (last ? last.n : 0);
  const add = lv.add_next === ""
    ? `<button class="btn sm go" data-tact="nextopen" data-tid="${tid}" data-n="${n}" title="A fresh session in this task, in the same folder, with step ${two(n)}'s handover">Add next step</button>`
      + `<button class="btn sm" data-tact="nextverify" data-tid="${tid}" data-n="${n}" title="Add next step with Verify selected: a fresh session checks step ${two(n)}">Verify</button>`
    : `<button class="btn sm" disabled title="${esc(lv.add_next || "Add next step is not available yet")}">Add next step</button>`;
  const cont = sl.continue === "" && last && last.session && last.kind === "chat"  // D1 a: one click lands in the latest chat's follow-up box
    ? `<button class="btn sm" data-tact="gochat" data-tid="${tid}" data-n="${last.n}" title="The latest chat's follow-up box: more conversation with this agent">Continue</button>` : "";
  const fin = lv.done === "" ? `<button class="btn sm${lv.add_next === "" ? "" : " go"}" data-tact="done" data-tid="${tid}" title="Ends this task; its history stays">Finish task</button>` : "";
  const ho = sl.handoff === "" ? `<button class="btn sm" data-tact="handoff" data-tid="${tid}" title="Prepare a handoff for a separate task.">Hand off</button>` : "";
  const del = lv.clear === "" ? `<button class="btn sm stop" data-tact="clear" data-tid="${tid}" title="Deletes tasks/${tid} with its runs; a plan mirrored into the project stays">Delete</button>` : "";
  return add + cont + fin + ho + del;
}
```

3. `inspTask`: delete the two lines that start `  const levers = \`<div class="v-levers">` and
   `    </div>\`;  // plan 38 U11: why Stop / Retry / Delete are off lives in the task head's title, not a line`. Then the
   return statement: its first line ends `<span class="lr">${buttons}</span></div>` and continues on the next lines;
   replace from `  return \`<div class="ihead">` to the closing `    ${levers}\`;` with

```js
  const head = `<div class="ihead"><div class="ln1"><span class="st ${tn}">${sprite(taskSprite(row))}${word}</span><h2 title="${esc(taskDir(t.id))}">${esc(t.title)}</h2><span class="lr">${buttons}</span></div>
    <div class="meta"${off ? ` title="${off}"` : ""}>${labHtml(t.id)}<button class="olink" data-tact="folder" data-tid="${tid}" title="${esc(taskDir(t.id))}">Open folder</button></div>
    <div class="meta"><span>${esc(t.project)}</span><span>${row.state === "done" || !t.current ? `${n} steps` : `step <b>${t.current}</b> of ${n}`}</span><span>cost <b>${money(row.cost)}</b></span><span>effort ${esc(t.effort)}</span>${DONE_STATES.has(t.state) ? `<span>${esc(t.state)} <b>${hhmm(t.updated)}</b></span>` : ""}</div></div>`;
  const body = `${now}${wait}
    ${fold("prompt.md", "", `<pre class="text">${esc(t.goal)}</pre>`, { key: "promptmd" })}
    ${open.length || closed.length ? `<div class="blk">${open.length ? `<span class="lbl">Open questions · <span class="y">${open.length} open</span></span><div class="oq">${open.map(qrow).join("")}</div>` : ""}
      ${closed.length ? fold(`${closed.length} closed question${closed.length === 1 ? "" : "s"}`, "", `<div class="oq">${closed.map(qrow).join("")}</div>`, { cls: "qf", key: "qclosed" }) : ""}</div>` : ""}
    ${log.length ? fold("Chain log", `${log.length}`, `<div class="clog">${log.map((c) => `<div><span>${hms(c.ts)}</span><span title="${esc(c.why)}">${move(c)}${c.why ? ` (${esc(c.why)})` : ""}</span></div>`).join("")}</div>`, { key: "clog" }) : ""}`;
  return dock(head, `<div class="ipane">${body}</div>`, taskButtons(t, d), t.id);  // plan 39: the task page docks like a step page
```

   The head's `${busyBox(t.id)}` goes with it (`dock` renders the one `b-msg` box in the bar). `renderBoard` already
   detects the dock (`html.startsWith('<div class="idock"')`) and scrolls `.iscroll`; Stop / Pause / Resume / Retry stay
   in the head's `${buttons}`; the Retry box, the ask box and the open questions stay in the pane.

4. `taskAct`: replace `  if (name === "nextopen") return openNextForm(id);` with

```js
  if (name === "nextopen") return openNextForm(id, undefined, Number(button.dataset.n) || 0);
  if (name === "nextverify") return openNextForm(id, "verify", Number(button.dataset.n) || 0);
  if (name === "gochat") return goChat(id, Number(button.dataset.n) || 0);
```

   (Task 3 gives `openNextForm` its third argument; until then it ignores it, which is the latest step: the same
   behaviour.) After `async function openTaskFolder(id, button) {` 's function add:

```js
async function goChat(tid, n) {  // plan 39 D1 a: Continue on the task page lands in the latest chat's follow-up box
  if (!n) return;
  boardPick = "s" + n;
  itab = "chat";
  await renderBoard();
  const f = $("b-tcont");
  if (f) f.focus({ preventScroll: true });
}
```

   `done`, `handoff` and `clear` already arm with a second click in `taskAct` (`Mark the task done? Click again`,
   `Hand off ends the task? Click again`, `Delete the task folder? Click again`); `handoff` goes to `stepAct`, which
   addresses the current step's session, the latest chat.

Check: `node --check web/app.js`; test_web green. Headless (plan 36 Task 4's harness, `tests/fake_claude.py`): on a
replied chat task's page the bar reads Add next step (filled), Verify, Continue, Finish task, Hand off, Delete; Continue
lands the caret in the follow-up box; Add next step opens the form on the latest step's Chat tab in one click; at the
boundary of a three-step manual task the bar reads Add next step, Verify, Finish task, Delete; a stuck task shows
Retry in the head and a disabled Add next step with its reason; no second `b-msg`.

### Task 3: per-step actions on an older step (D4 a, D6 a)

Tests first, `tests/test_web.py`, in `NextStepUITest`:

```python
    def test_older_done_step_offers_a_branch_where_the_service_allows_it(self):
        """Plan 39 Task 3: the dock of an older step reads sources[NN]; the Board reproduces no rule of its own."""
        t = "{id: 't', current: 3, steps: [{n: 1, session: 's1', state: 'done'}, {n: 2, session: 's2', state: 'done'}, {n: 3, session: 's3', state: 'done'}]}"
        ok = render(self._setup() + f"nextActions({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{add_next: '', done: ''}}, sources: {{'01': '', '02': '', '03': ''}}}})")
        self.assertIn('class="btn sm go" data-tact="nextopen" data-tid="t" data-n="2"', ok)
        self.assertIn("Add step from here", ok)
        self.assertIn('data-tact="nextverify" data-tid="t" data-n="2"', ok)
        self.assertIn("Verify this step", ok)
        self.assertNotIn("Finish task", ok)  # the task's own actions stay on the task page and the latest step
        off = render(self._setup() + f"nextActions({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{add_next: ''}}, sources: {{'02': 'no saved note or final reply'}}}})")
        self.assertIn('disabled title="no saved note or final reply">Add step from here', off)
        self.assertNotIn("Verify this step", off)
        self.assertEqual(render(self._setup() + f"nextActions({t}, {{n: 2, session: 's2', state: 'done'}}, {{levers: {{}}}})"), "")
        latest = render(self._setup() + f"nextActions({t}, {{n: 3, session: 's3', state: 'done'}}, {{levers: {{add_next: '', done: ''}}, sources: {{'03': ''}}}})")
        self.assertIn("Add next step", latest)
        self.assertIn("Finish task", latest)
        foot = render(self._setup() + f"histFoot({t}, {{n: 2}}, {{}})")
        self.assertIn("Go to step 03", foot)
        self.assertNotIn("Next steps start", foot)

    def test_form_from_an_older_step_names_it_and_the_steps_that_ran_since(self):
        """Plan 39 Task 3 (D4 a, D6 a): the source line, the shared-tree line and the Verify default name the source."""
        view = {"key": "t|2|s2", "busy": False, "revision": "r", "text": "HANDOFF\n## Goal\ngoal\nEND HANDOFF",
                "route": {"rung": "opus", "model": "opus", "effort": "high", "notes": []}, "models": []}
        t = ("{id: 't', project_dir: 'C:/repo/APP', current: 4, steps: [{n: 1, session: 's1', kind: 'scout'}, {n: 2, session: 's2', kind: 'code'}, "
             "{n: 3, session: 's3', kind: 'verify'}, {n: 4, session: 's4', kind: 'chat'}]}")
        html = render(self._setup(view=view) + f"nextOpen = {{tid: 't', key: 't|2|s2'}}; nextFormHtml({t}, {{n: 2, session: 's2', kind: 'code'}}, null, {{}})")
        self.assertIn("From 02 code", html)
        self.assertIn("Starts from step 02's handover on the project as it is now; steps 03 and 04 ran since.", html)
        one = render(self._setup(view=view) + f"sinceLine({t}, {{n: 3}})")
        self.assertIn("step 04 ran since", one)
        self.assertEqual(render(self._setup() + f"sinceLine({t}, {{n: 4}})"), "")
        self.assertTrue(render("verifyDefault(2)").startswith("Check step 02 against its goal, its tests and its unresolved risks"))
        self.assertIn("Do not edit files", render("nextInstr({steps: []}, {}, {n: 2}, 'verify', null)"))

    def test_the_form_is_bound_to_the_source_in_next_open_not_to_current(self):
        """Plan 39 Task 3: openNextForm, nextPreview, startNextStep and nextReseed resolve the source from nextOpen's key."""
        out = render(self._setup() + "(() => { const bd = {task: {id: 't', current: 3, steps: [{n: 2, session: 's2', kind: 'code'}, {n: 3, session: 's3', kind: 'verify'}]}}; "
                     "nextOpen = {tid: 't', key: 't|2|s2'}; const [t, s] = nextSource(bd); "
                     "nextOpen = {tid: 't', key: 't|2|other'}; const [, gone] = nextSource(bd); return [t && t.id, s && s.n, gone]; })()")
        self.assertEqual(out, ["t", 2, None])
```

Amend four tests. `test_historical_step_points_to_the_latest`: drop the
`self.assertIn("Next steps start from the latest step", html)` line (Go to step 02 stays).
`test_verify_seeds_a_concrete_default`: `nextInstr({steps: []}, {}, {n: 1}, 'verify', null)` stays and its assertions stay
(the text still carries `VERDICT: PASS or FAIL` and `Do not edit files`). `test_instructions_seed_from_the_previous_next_section`
and `test_a_none_next_section_seeds_blank`: the seed is now the source's own note, so the step passed is `{n: 1}` with
`notes["1"]` (the test names stay, their docstring-free bodies change the `{n: 2}` to `{n: 1}`).
`test_a_reseed_shows_in_the_open_field`: `VERIFY_DEFAULT` becomes `verifyDefault(1)` (three places in its expression).

Code, `web/app.js`, in the `// -- plan 36 Task 3` section and the functions after it.

1. Replace

```js
const VERIFY_DEFAULT = "Check the previous step against its goal, tests and unresolved risks. Do not edit files: " +
  "report VERDICT: PASS or FAIL and what you found.";
```

with

```js
const verifyDefault = (n) => `Check step ${two(n)} against its goal, its tests and its unresolved risks. Do not edit files: ` +
  "report VERDICT: PASS or FAIL and what you found.";  // plan 39 D4 a: the default names the step it checks
```

   and in `nextInstr` replace `return kind === "verify" ? VERIFY_DEFAULT : nextSeed(t, d, s);` with
   `return kind === "verify" ? verifyDefault(s.n) : nextSeed(t, d, s);`.

2. `nextSeed`: replace

```js
  const prev = t.steps.find((x) => x.n === s.n - 1) || s;
  const text = (d.notes || {})[String(prev.n)] || (d.briefs || {})[String(prev.n)] || "";
```

   with

```js
  const text = (d.notes || {})[String(s.n)] || (d.briefs || {})[String(s.n)] || "";  // plan 39: the source's own Next, not the step before it
```

   and its comment `// the previous step's usable Next section, else ""` with `// the source step's usable Next section, else ""`.

3. After `function setInstr(draft, text) {` 's function add:

```js
function nextSource(bd) {  // plan 39: the form's source, from nextOpen's key (task + step + session), never t.current
  const t = bd && bd.task, s = t && nextOpen && t.steps.find((x) => nextKey(t, x) === nextOpen.key);
  return s ? [t, s] : [null, null];
}
function sinceLine(t, s) {  // plan 39 D6 a: the shared tree, said once, whenever the source is not the latest step
  const later = (t.steps || []).filter((x) => x.n > s.n).map((x) => two(x.n));
  if (!later.length) return "";
  const list = later.length === 1 ? `step ${later[0]}` : `steps ${later.slice(0, -1).join(", ")} and ${later[later.length - 1]}`;
  return `<div class="nfrom"><span class="m">Starts from step ${two(s.n)}'s handover on the project as it is now; ${list} ran since.</span></div>`;
}
```

4. `nextReseed`: replace `const t = bd && bd.task, s = t && t.steps.find((x) => x.n === t.current);` (the line inside
   `nextReseed`, right after `const bd = boardData && nextOpen && boardData.id === nextOpen.tid ? boardData.data : null;`)
   with `const [t, s] = nextSource(bd);`.

5. `nextFormHtml`: after the line that ends `<span class="m">Same project: ${esc(projectName(t.project_dir))}</span></div>` +
   (the `.nfrom` div) insert `` `${sinceLine(t, s)}` + `` so the line sits under the source line, above the Work row.

6. `nextActions` whole (anchor: `function nextActions(t, s, d) {  // plan 38 U3:` through `return add + fin;`):

```js
function nextActions(t, s, d) {  // plan 38 U3: in stepButtons, on every tab; plan 39: an older done step offers a branch
  const open = nextOpen && nextOpen.key === nextKey(t, s), last = latestStep(t), latest = !last || s.n === last.n;
  if (!s.session || open || (s.state === "running" && !chatReplied(s))) return "";
  const lv = d.levers || {}, tid = esc(t.id);
  if (!latest) {  // the service's answer per step (GET /api/task sources); the Board reproduces no rule of its own
    const why = (d.sources || {})[two(s.n)];
    if (why == null) return "";
    return why === ""
      ? `<button class="btn sm go" data-tact="nextopen" data-tid="${tid}" data-n="${s.n}" title="A fresh session in this task from step ${two(s.n)}'s handover, on the project as it is now">Add step from here</button>`
        + `<button class="btn sm" data-tact="nextverify" data-tid="${tid}" data-n="${s.n}" title="A fresh session checks step ${two(s.n)} against its goal, its tests and its risks">Verify this step</button>`
      : `<button class="btn sm" disabled title="${esc(why)}">Add step from here</button>`;
  }
  const add = lv.add_next === ""
    ? `<button class="btn sm go" data-tact="nextopen" data-tid="${tid}" data-n="${s.n}" title="A fresh session in this task, in the same folder, with the handover">Add next step</button>`
    : `<button class="btn sm" disabled title="${esc(lv.add_next || "Add next step is not available yet")}">Add next step</button>`;
  const fin = lv.done === "" ? `<button class="btn sm" data-tact="done" data-tid="${tid}">Finish task</button>` : "";
  return add + fin;
}
```

   The latest step keeps Add next step and Finish task as plan 38 U3 placed them; the task's own actions (Continue, Hand
   off, Delete) live on the task page and in the step's existing buttons, not on an older step.

7. `histFoot` whole (anchor: `function histFoot(t, s, d) {` through its closing `}`):

```js
function histFoot(t, s, d) {  // plan 39: an older step's footer keeps only the way to the latest step; its actions are in the dock
  const latest = latestStep(t);
  if (!latest || latest.n === s.n) return "";
  return `<div class="askbox cont hfoot"><div class="lr"><button class="btn sm" data-bpick="s${latest.n}" data-btask="${esc(t.id)}">Go to step ${two(latest.n)}</button></div></div>`;
}
```

8. `stepFooter`: replace

```js
  const current = t.current == null ? s.n : t.current;
  if (!s.session || s.n !== current) return steps.length > 1 ? histFoot(t, s, d) : "";
  const key = nextKey(t, s), open = nextOpen && nextOpen.key === key, lv = d.levers || {}, question = row && row.stop_question;
  const live = s.state === "running" && !chatReplied(s);
  if (open) return nextFormHtml(t, s, row, d);
```

   with

```js
  const key = nextKey(t, s), open = nextOpen && nextOpen.key === key, lv = d.levers || {}, question = row && row.stop_question;
  if (open) return nextFormHtml(t, s, row, d);  // plan 39: on the source's own Chat tab, the latest step or an older one
  const current = t.current == null ? s.n : t.current;
  if (!s.session || s.n !== current) return steps.length > 1 ? histFoot(t, s, d) : "";
  const live = s.state === "running" && !chatReplied(s);
```

9. `openNextForm` whole (anchor: `async function openNextForm(tid, kind) {` through `await nextPreview();` and its `}`):

```js
async function openNextForm(tid, kind, n) {  // plan 39: from step n (0: the service's latest source), on that step's Chat tab
  const bd = boardData && boardData.id === tid ? boardData.data : null;
  const t = bd && bd.task, ns = (bd && bd.next_step) || {};
  const s = t && t.steps.find((x) => x.n === (n || ns.source_step || t.current));
  if (!s || !s.session) return;
  const key = nextKey(t, s);
  const box = $("b-tcont");
  if (box) fuDraft[box.dataset.sid || ""] = box.value;
  nextOpen = { tid, key };
  boardPick = "s" + s.n;  // from the task page or an older step: the form opens on the source's own Chat tab
  itab = "chat";
  nextDraftFor(t, bd, s);
  if (kind) { nextDraft[key].kind = kind; setInstr(nextDraft[key], nextInstr(t, bd, s, kind, null)); }
  nextView = null;
  focusWork = true;
  renderBoard();
  await nextPreview();
}
```

10. `verifyNext`: `async function verifyNext(tid) {` becomes `async function verifyNext(tid, n) {`;
    `boardPick = "s" + (row && row.current ? row.current : 1);` becomes
    `boardPick = "s" + (n || (row && row.current ? row.current : 1));`; `await openNextForm(tid, "verify");` becomes
    `await openNextForm(tid, "verify", n);`. (The session page's `data-nverify` keeps calling it with one argument.)

11. `nextPreview` and `startNextStep`: in each, replace
    `const t = bd && bd.task, s = t && t.steps.find((x) => x.n === t.current);` with `const [t, s] = nextSource(bd);`.
    The preview and the append already post `source_step: s.n, source_session: s.session`, so the request carries
    the older step; `startNextStep` already picks the new step (`boardPick = "s" + data.step`) and focuses its heading.

Check: `node --check web/app.js`; test_web green (3 new, 4 amended). Headless with the fake claude, a three-step manual
task at its boundary: pick 02, the dock reads Add step from here (filled), Verify this step, Open chat; the footer reads
Go to step 03 only; Add step from here opens the form on 02's Chat tab with From 02 code and the shared-tree line
("steps 03 ran since" never appears: the singular is "step 03 ran since"); Verify this step opens it with Verify and
"Check step 02 against ..."; Start appends 04 with `source_step` 2, selects 04's Chat tab, and 03 stays in the chain;
Escape and Cancel close the form and return focus to the dock button; a running step's dock shows the disabled
button with "Available when this turn finishes".

### Task 4: lineage in the list

Tests first. `tests/test_server.py`, in `ChatTaskGroupTest`'s neighbour `test_task_row_carries_label_prep_and_fix_links`
(or a new test next to it):

```python
    def test_task_row_carries_the_source_step_of_a_branch(self):
        """Plan 39 Task 4: the list's rows carry source_step, 0 when the step has none."""
        t = tasks.new_task("/p", "proj", "fix add()", "goal", tasks.plan_steps([{"kind": "code", "goal": "g"}], 6),
                           "normal", {}, "", "auto", 1000.0)
        t["steps"][0].update(state="done", session="s1")
        t.update(current=1, progression="manual")
        new = tasks.append_step(t, "verify", "check 01", now=1001.0)
        self.assertEqual([s["source_step"] for s in server.task_row(t)["steps"]], [0, 1])
        self.assertEqual(new["source_step"], 1)
```

`tests/test_web.py`, in `NextStepUITest`:

```python
    def test_chain_row_tags_a_branch_with_its_source(self):
        """Plan 39 Task 4: `from 02` on the row's second line when source_step is set and is not n - 1; no indentation."""
        t = ("{id: 't', current: 4, steps: [{n: 1, kind: 'scout', state: 'done', source_step: 0}, {n: 2, kind: 'code', state: 'done', source_step: 1}, "
             "{n: 3, kind: 'verify', state: 'done', source_step: 2}, {n: 4, kind: 'code', state: 'done', source_step: 2}]}")
        html = render(self._setup() + f"stepRows({t})")
        self.assertEqual(html.count("from 02"), 1)
        self.assertIn('<span class="n">04</span>', html)
        self.assertNotIn('class="v-subs"', html)  # a branch is a tag, never a nested list
        self.assertEqual(render(self._setup() + f"receivedNote({t}, {{n: 4, state: 'done', source_step: 2}})"), "")
```

Code. `console/server.py` `task_row`: after `"end_commit": s.get("end_commit", ""), "brief_meta": s.get("brief_meta"),`
add `"source_step": s.get("source_step") or 0,  # plan 39: lineage, one integer`.

`web/app.js`:

1. `receivedNote`: replace `const prev = t.steps.find((x) => x.n === s.n - 1), meta = (prev && prev.brief_meta) || {};`
   (the first line of `receivedNote`) with
   `const prev = t.steps.find((x) => x.n === (s.source_step || s.n - 1)), meta = (prev && prev.brief_meta) || {};  // plan 39: by source`.

2. `chainStepHtml`: replace `s.part ? '<span title="a write step the design step made">from plan</span>' : ""].filter(Boolean).join(" · ");`
   with

```js
    s.part ? '<span title="a write step the design step made">from plan</span>' : "",
    s.source_step && s.source_step !== s.n - 1 ? `<span title="a branch: this step started from step ${two(s.source_step)}'s handover">from ${two(s.source_step)}</span>` : ""].filter(Boolean).join(" · ");
```

3. `recvPane`: replace

```js
  const prev = t.steps.find((x) => x.n === s.n - 1), brief = (d.briefs || {})[String(s.n - 1)] || "", meta = (prev && prev.brief_meta) || {};
  const note = (d.notes || {})[String(s.n - 1)] || "", cut = (meta.cut || []).map(normItem);
  if (!brief && !note) return `<p class="note m">The brief of step ${two(s.n - 1)} is not on disk (cleared, or the step never ran).</p>`;
```

   with

```js
  const from = s.source_step || s.n - 1;  // plan 39: a branch received its source's note, not the step before it
  const prev = t.steps.find((x) => x.n === from), brief = (d.briefs || {})[String(from)] || "", meta = (prev && prev.brief_meta) || {};
  const note = (d.notes || {})[String(from)] || "", cut = (meta.cut || []).map(normItem);
  if (!brief && !note) return `<p class="note m">The brief of step ${two(from)} is not on disk (cleared, or the step never ran).</p>`;
```

   and `<span class="lbl">From ${two(s.n - 1)}</span>` in its return with `<span class="lbl">From ${two(from)}</span>`.

Check: test_server and test_web green (+2); headless: after Task 3's branch, row 04 reads `04 code · <rung> · from 02`,
row 03 is unchanged, no indentation; 04's Received tab is headed From 02 and shows 02's note.

### Task 5: headless pass, Fred's live check, the records

- Headless, as plan 36 Task 4 (Playwright, Chromium, `tests/fake_claude.py`, a scratch `CC_CONSOLE_HOME`, the service
  in-process; the script stays in the scratch folder, not the repo): at 900 / 400 / 340 px, dark and light, reduced
  motion and 130 % text scaling: (1) the task page dock of a replied chat task and of a three-step manual task at its
  boundary; every button present only when its lever is ""; Continue focuses `b-tcont`; (2) a branch from 02 with 03
  present: the form's two source lines, Start, 04 selected, `from 02` on its row, 03 inspectable; (3) Verify this step
  from 02: the default names step 02, the route says a fresh session; (4) no horizontal overflow, the dock bar wraps at
  340 px, no page errors, Escape and Cancel return focus. Fix failures as a batch, one confirmation pass, record the
  count in History.
- Fred on Windows, 100 % and 130 %: the task page dock on a real replied chat; Add step from here on an older step of a
  real task and the branch's handover; Verify this step; the light theme bar.
- `plans/36-next-step/README.md`: in 3.1 replace `recovery/resume/next-task actions. Historical steps are inspectable, not branch points.`
  with `recovery/resume/next-task actions. Since plan 39 any done step with a session and a saved note or final reply is a source too (D2 a); the branch is a fresh session numbered after the last step, never a resume of the old one.`
  and in Excluded replace `Excluded: branching/DAG UI, arbitrary old-step forks, global workflow builder, auto-running`
  with `Excluded: branching/DAG UI, sibling numbering and sub-tasks (plan 39 makes older done steps sources, as a tag on a numbered list), global workflow builder, auto-running`.
- `PLAN.md`: row 39's state to `code done <date> (<n> tests OK)` and a History line naming the departures, if any.

## 3. Decisions (Fred, 2026-10-16: (a) on all six)

- **D1** (a): Continue on the task page is one button that jumps to the latest chat's Chat tab and focuses its follow-up
  box; no second textarea on the task page.
- **D2** (a): sources are `done` steps with a session and a saved note or final reply, a FAIL verify included; `failed` and
  `handed` steps are not (a later plan may add them).
- **D3** (a): a branch from an older step while the latest step is a replied chat still in `running` closes that chat
  `done`, with a chain line, as the latest-step append does for its own source chat.
- **D4** (a): the Verify default on any step names the step it checks: "Check step 02 against its goal, its tests and its
  unresolved risks. Do not edit files: report VERDICT: PASS or FAIL and what you found."
- **D5** (a): automatic chains unchanged: a running automatic chain, a stuck or a stopped task refuse a branch and keep
  Retry / Resume / Stop; a done automatic chain converts to manual on its first branch, as today.
- **D6** (a): the one-line shared-tree note shows whenever the source is not the latest step, differing facts or not.

Rules that bind every task: `Hub.levers` unchanged (no older session is continued, verified or handed off in place; a
branch is a fresh session, `resume=None`); `Hub.task_levers` and `Hub.next_sources` own availability and the Board shows
a button only where the service would accept the request; the chain stays a numbered list with `source_step` as the one
lineage integer (no letters, no sub-tasks, no graph, no worktree); buttons live in the dock bar of the picked thing only
(no hover actions, no per-row menu, no new global keys); stdlib + pywebview, plain HTML/CSS/JS, no `web/style.css` change.

## 4. History

- 2026-10-16 - Plan written from the decided brainstorm (option 2, dock placement, D1-D6 (a)), on 42ecd0f. Every helper
  the plan changes was read with its callers (section 1). No code changed. Two slips found while reading and folded into
  the tasks: `nextSecondary` reads `task_levers` (F11, Task 2) and `nextSeed` reads the note of the step before the
  source (F18, Task 3); one gap: `recvPane` labels a manual step's Received tab by `n - 1` (F19, Task 4).
