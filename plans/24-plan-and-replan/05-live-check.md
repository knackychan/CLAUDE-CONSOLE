# Task 5: Fred's live check

> Claude never starts a run, never POSTs `/api/run`, `/api/task` or `/api/prep`. Fred runs this in a real project
> (CONTENT MANAGER, or this repo on a scratch branch) after Task 4 is placed and the tray's service restarted.

## 5.1 A task with a design step, one plan

1. Run a task whose Prep chain has `scout, design, code, test, verify` (a request that edits two or three files,
   effort auto). Expected: after the design step, the Task page shows `Plan · from 02 design · N w · never cut ▾`;
   open, the six headings and `### Step 3: code` marked `this step`; `tasks/<id>/plan.md` in the data folder; the
   chain line `plan saved: ...` and step 3's start line ending `read: brief 02 · plan N KB · step 3 section`.
2. Read the plan: every Decisions line closed, final code where the step depends on it, the Tests by name, a Done
   check with a command. Note what the design step left open (a `Plan gap:` later tells the same).
3. The code step: its chat shows the plan in the prompt and its own section at the end; the diff follows the plan;
   the verify's verdict mentions no `plan drift:` on a plan it followed.

## 5.2 A split plan

4. A request that spans two modules (service and window). Expected: `plan saved: 2 sub-plans, ...`, `design split
   into 2 sub-plans: 2 code steps (Prep had 1)`, the step list with the two code rows `from plan`, the Plan row's
   parts list with their step and state, `plan/01-*.md` and `plan/02-*.md` in the folder; each code step's prompt
   carries the index and its own part only; the verify's prompt carries both parts.
5. A part marked `hard` routes to a stronger rung (the step row's model after `rung at start`).

## 5.3 The waits

6. `plan_hold` on in config.json (service restart): the task waits `plan ready: confirm` with Confirm plan / Edit /
   Stop; Edit, add a Decisions line, Save, Confirm: step 3 runs on the edited plan (its prompt carries the line).
7. A `Plan gap:`: a task whose request leaves a fork open on purpose (two config files could hold the setting).
   Expected: the code step stops, the Task page's askbox `Plan gap · step 03 stopped, nothing chosen`; Send answer:
   `plan.md` Decisions ends with `- Fred, <date>: ...`, the step continues in its chat and finishes. Then Redo design
   on another gap: the design step runs again with the question in its prompt, the done steps keep their place.
8. `plan_max_kb` set to 5 for one run: the task waits `plan N KB, over 5`; Accept runs on.

## 5.4 The replan

9. A scout whose handoff says `Replan: ...` (a request that names a file the project does not have, so the scout
   asks for a search first). Expected: the replan step inserted after 01, run with no session (the step row says
   `haiku/low`, no Open button), `steps/02-replan.md` written, the task waiting `replanned: 1 steps added` with the
   two lists; Confirm plan: the chain goes on with the search step; on another task, Keep old plan.
10. `replan_auto` on: no wait.

## 5.5 Record

- Each item: what was expected, what was seen, the task id. Findings become fixes in a plan 27 (as plan 19 did for
  plan 17) or small commits on this branch when they are one-liners.
- Costs: the design step's cost against the old 12-turn cap (D2), the plan's size in KB and words, the input tokens
  of the first code step with and without the plan (the context gauge of the step row).
