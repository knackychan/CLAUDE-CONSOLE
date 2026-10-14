# Task 8: Fred's live check of plan 27

> Depends on: Tasks 1 to 5 placed (items 1 to 7); Task 6 placed (item 8). Fred's task: Claude never starts a run,
> never POSTs `/api/run`, `/api/task` or `/api/prep`. Windows, Python 3.14, the real window (`run.bat`).
> Each item says what to do and what you should see. Write what you saw under the item; a difference becomes a
> plan 27 finding for a follow-up, not a fix in place.

1. **Config writes (Task 1).** On the Models page change one Tuning number and Save while, in the settings popover,
   you switch a harness off and on. Both changes are in `~/.claude/console/config.json`, no `config.json.*.tmp` file is
   left in the folder.
2. **Hand edit and Reload (Task 1).** With the window open, delete `task_max_steps` from config.json by hand, press
   Reload on the Models page: it shows the default (6). Put `"balance_margin": "x"` in by hand, Reload: the page keeps
   the old value and `console.log` has a line naming `balance_margin`.
3. **Plan edges (Task 2).** A task `scout, design, code, test, verify` whose design step ends with a `Replan:` line:
   the chain log says `replan refused: design step` and the code step's Received tab shows its `### Step` section. On
   a task without a design step, no Answer button appears for a step that writes `Plan gap:`.
4. **Redo while the brief writes (Task 2).** With `"plan_hold": true` in config.json, let a design step end so
   the task waits on the plan hold, and press Redo design at once: the button is off with `brief still writing` until
   the step's brief is in, then works.
5. **Routing (Task 3).** Remove one codex model from `models.json`, press Reload models, start a task whose Prep pick
   names it: the step's Route tab reads `pick refused: model gone from models.json: codex:<model> -> balance`.
6. **Facts and handoff (Task 4).** A task in a project with a file named with an accent (for example `café.md`)
   changed by a code step: the Facts fold counts its lines. A step whose brief cut findings: the Task page's Handoff
   fold reads `N kept · M cut` with the cut lines struck.
7. **Window (Task 5).** On the Board press Ctrl+N: the window returns to its list size. Back on the Board, Tab to a
   button in the inspector and press Enter: the button acts. On the Models page, remove a model from models.json,
   Reload, reorder the read tier and Save: the Save goes through; the hidden row shows under `show` with a remove
   button. A Codex step with no price row shows `cost unknown`.
8. **Harness edges (Task 6, after plan 5's live check).** An OpenCode step and a cmd step end as success within about
   10 s of their last line, never `error_step_timeout`. A Codex step in a folder whose name contains `&` runs in
   that folder (its first command's output shows the path).

Commit (docs only, the observations under each item): `docs: plan 27 live check (plan 27 Task 8)`.
