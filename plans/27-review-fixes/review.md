# PR #1 review, plan by plan (2026-10-14)

Branch `claude/implement-orchestration-plans-1y4bic` at `cf69a48`. Plans 5, 24, 23, 18, 26 and 25 were checked
task by task against the tree: each plan's final code blocks were diffed against the files, and each listed function,
key, route and test was looked up. Review only, nothing pushed.

Tests on Linux (Python 3.13): 525 run, 3 failures and 1 error, exactly the four known Linux baseline failures
(test_tray import, test_redact Windows path, test_usage local day, test_window placement). `node --check web/app.js`
OK. Plan 25's Board was also loaded in headless Chromium with `<script>` and `<img onerror>` planted in titles, goals,
notes, briefs and the chain log: everything came out escaped, no console errors.

**Bottom line.** The build follows the plans closely: `plan.py`, `replan.py`, `fills.py`, `facts.py`, `compact.py`,
`tuning.py` and their tests are byte-identical to the plans, and every code task is present. No CLAUDE.md rule is
broken (127.0.0.1 and `guard` on every new route, writes only under the console folder, commands only from
`claude_cli` and the adapters, `cc_events.py` untouched). What the review found is mostly in edge paths the plans
themselves did not cover: 12 bugs, 14 risks, 9 gaps against the plan text, and nits. Live Windows checks remain
Fred's.

Marks: **[R]** reproduced here, **[C]** confirmed by reading the code, **[I]** inferred, not run.

## 1. Bugs

| # | Plan | Where | What goes wrong | Mark |
|---|---|---|---|---|
| B1 | 24 T3 | `server.py:1064`, `design_prompt.md:95` | The design prompt invites a `Replan:` line, but `replan.insert` then renumbers later steps after `plan.save`/`rebuild`. A single plan's `### Step N` lookup misses (the code step gets no section); a split plan's `parts[i].step` goes stale and a later `apply` drops `part`/`hard`. | R |
| B2 | 24 T2 | `replan.py` `check`/`apply` | A replan answer without an edit kind drops the verify of a code step already done (scout, code done, replan, test, verify becomes scout, code, replan, test). | R |
| B3 | 24 T3 | `server.py:784`, `:1239-1253`, `plan.py:321` | `answer` lever only checks the `Plan gap:` why, not that the task has a plan. On a plan-less task `add_answer` writes a stray plan.md and raises IndexError. | R |
| B4 | 24 T1/3 | `plan.py` `design_input` | Redo design stops at `n`, so the design step never sees the handoffs of done steps after it, though `design_text` says "its handoff is above". | C |
| B5 | 24 T3 | `server.py` `_ended` | A redo that turns a split plan into a single plan leaves `part`/`hard` on the old steps; `prompt_parts` then returns an empty section. Old `plan/NN-*.md` stay on disk. | I |
| B6 | 26 T4/T1 | `app.js:2366`, `tuning._tiers` | Save posts every tier whenever one changed. After a model is removed from models.json, its hidden row (no remove button) makes every tier Save fail with `unknown model`, until config.json is edited by hand. | R |
| B7 | 26 T1 | `tuning._number` | `validate` raises OverflowError on a huge integer (`10**400`), breaking its own "never raises" guard; the POST drops the connection. | R |
| B8 | 25 T1 | `server.py:1827` `_measure` | `n.isdigit()` accepts `²`; `int()` then raises and the connection drops instead of the promised 400. | R |
| B9 | 25 T2 | `app.js:3283` | Ctrl+N and Ctrl+P on the Board call `showPage("list")` without `closeBoard()`: the window stays 900 px wide and the service keeps `_board`, so a later grip drag saves `board` instead of `size`. | R |
| B10 | 18 T2 | `tasks.step_route` | A verify whose pool is empty keeps `share` None, so it never holds over pace (README 3.8 says it holds). | R |
| B11 | 18 T1 | `fills.peak_add` | Catches only ValueError; a hand-edited `peak_hours` like `{"add": [1]}` raises TypeError out of `balance`, so every step route marks its task broken. | C |
| B12 | 5 T5 | `server.py:845` vs `:853` | `start_step` calls `reload_models()` after `_route_for` chose the rung, so a models.json removal reaches routing one step late and a gone model can be picked once. | C |

## 2. Risks

| # | Plan | Where | Risk | Mark |
|---|---|---|---|---|
| K1 | 26, 23 | `paths.set_config`, `set_setting`, `set_harness`, `add_project` | Four config.json writers share one `config.json.tmp` and no lock, on a ThreadingHTTPServer. Concurrent POSTs can lose an update; on Windows `os.replace` can raise PermissionError, which `_setting` and `save_models` do not catch. | C |
| K2 | 26 | `Hub.reload_tuning` (`server.py:113-135`) | A key deleted from config.json by hand keeps its old live value until restart; reloaded values are not validated. | C |
| K3 | 23 T5 | `server.py:631-642` `auto_steps` | With `handoff_auto` on, a red run whose handoff pull keeps returning 409 never joins `auto_handed`; the `elif` keeps its FAIL verdict out of `due` forever and the pull is retried every second. | C |
| K4 | 23 T3/5 | `claude_cli.py:296-302` | Snapshot reads up to 500 untracked files of 1 MB each, inside `advance()`'s `tlock`. A project with an unignored venv or build folder stalls the hub on every step start and end. | I |
| K5 | 23 T3 | `claude_cli.git_snapshot` | No `-c core.quotePath=false` (or `-z`): non-ASCII paths come back octal-quoted, count 0 lines and fail the D5 path check. | C |
| K6 | 23 T5 | `server.py:1810` `_task` | Sends the raw task, so every step's `git_base` (up to 500 paths) goes to the window on each poll; the plan's guard says never. | C |
| K7 | 18 T3 | `usage.py:249-327` | `_read` returns `{}` on an unreadable usage-days.json and both writers then overwrite it, losing history and `seen` (double counting). `save_days` has no OSError guard. | C |
| K8 | 18 T4 | `server.py:264-270` `count_run` | `load_other` runs after `FILE_LOCK` is released; two overlapping calls can leave in-memory fills one run short. | I |
| K9 | 18 T3/4 | `poll_once` | An exception in `count_run` (malformed tokens) escapes `poll_once` at the end of `start_step` and marks a started task broken. | I |
| K10 | 5 T4 | `runs.py:269-296` | For adapters without an interrupt, if OpenCode (`--standalone`) or cmdc keeps running after its final event, the run lasts to `step_timeout_s` and ends `error_step_timeout` although it succeeded. On Linux it is not even killed (taskkill, known). | I |
| K11 | 5 T2 | `codex.py:28-31` | On Windows Codex is found as the npm `codex.cmd` shim, so `-C <cwd>` and the quoted effort value pass through cmd.exe; a path with `&`, `^` or `%` would break. | I |
| K12 | 24 T3 | `server.py` `_ended`, `plan.check` | Room for planned steps ignores done steps a redo keeps, so a redo can exceed `task_max_steps`; `_ended` and `replan.check` count the verify differently. | C |
| K13 | 24 T3 | `server.py:1174` `_go_on` | The replan pass starts without the project check, so it can run after the project left `projects`. The brief pass has the same exposure. | C |
| K14 | 24 T3 | redo from size or hold wait | The old design step's brief thread can still be running when the design step restarts, and then writes an outdated brief. | I |

## 3. Gaps against the plan text

| # | Plan | Gap | Fix direction |
|---|---|---|---|
| G1 | 24 T3 | `edit_plan` allows stopped, done and handed tasks (owner fred, not running). README 3.7: paused only. | Also require state running or waiting. |
| G2 | 23 T6 | Findings cut by `compact.cut` never show as struck on the Task page: the cut list holds the brief pass's paraphrased items and the "as sent" view passes `cut=[]`. Live check item 2 expects "N kept · M cut". | Append `meta.cut` as struck lines in the as-sent view (as the Board's `inspConn` already does); fix the plan text. |
| G3 | 25 T5 | Plan fold keys are built from heading text (`plan.ststep3...`), not the six pinned keys; each `### Step N` takes a window.json slot toward the 64 cap. | Map to `plan.goal/dec/out/files/steps/acc`. |
| G4 | 25 T7 | `.chain .row.short { padding-block: 5px; }` missing from style.css. | Add it. |
| G5 | 5 README 3.2b | Model gone from models.json routes with `pick refused: unknown model` instead of `model gone from models.json: <rung>`; unknown tier names and entries outside a harness's TIERS are kept or dropped silently instead of logged. | Note in `rung_ok`; filter `_ladder_from`; log in `reload_models`. |
| G6 | 5 dec. 12 | After plan 18, a pick whose harness is off falls to the balance (any rung) instead of Claude's rung of the same tier. Not in History. | Decide (see section 5), then code or History. |
| G7 | 5 T4/6 | An all-unpriced step shows `?` in the chain cost column; README 3.6 says `cost unknown`. | Word it as planned, or amend the plan. |
| G8 | 24 T1 | `opus_max_turns` is read on every load and never dropped from config.json (D2 says read once, then dropped). | Drop it in `set_config` or amend the text. |
| G9 | 26 T4 | Allowance fields are not checked in the window; bad values only fail at the server. | Mark a row red when not a finite 0 to 100000. |

## 4. Nits

- 25: `routePane` adds an inline `style="color:var(--ink)"` (CLAUDE.md: styling in style.css); `ITABS` and `at`/`run` in `renderTaskPage` unused; `.now` font differs from 6.5; `folds_ok` sits between constants; Board `boardKey` swallows Enter and arrows on focused inspector buttons (plan 2.8 as written, but a usability gap).
- 24: fake word `REPLAN-ASK` vs `REPLAN`; tests' step order `code, verify, test` vs the plan's `test, verify` (the code is right, the plan text is wrong); `start_replan` sets tier haiku whatever `brief_model` is; `plan.write` and `add_answer` write unmasked text and a multi-line answer can inject a `## ` heading.
- 23: `factsFold` with `force: fail` cannot be closed while red; `lessons_for` filters after a 40-line cut; D5 `touched` comes from the 30-line facts text; `step_prompt.md` blank-line handling differs from 1.2 (equivalent, not in History).
- 18: an unknown pick balances with no `pick refused` note; `cmd.py:84` likely counts cached tokens in input, unlike codex (inferred, check against cmdc output in the live check); plan 18 commit subjects lack the prescribed test count.
- 26: `_config` indentation; first tier Save freezes all three tiers into config.json (fixed with B6).
- 5: `harnesses()["claude"]["models"]` not `{}`; `cc_exit` line now on Claude streams too; OpenCode drops the STOP footer for `/` prompts, the others do not.
- Note for Fred (plan 18, by design): with `allowances: {}` (D2 a) every share is None, so routing follows tier order and there is no spread until allowances are set on the Models page.

## 5. Fix plan

One follow-up plan, `plans/27-review-fixes/`, written in the style of the earlier plans and placed on the PR branch
as one commit per task. Each task is tests first: a failing test that reproduces the finding, then the fix, then
`py -m unittest discover -s tests` with only the Linux baseline failing. No task changes a design decision; the two
that would are listed as questions at the end.

**Task 1: config.json writes (K1, K2, B7).**
- `paths.py`: a module-level `CONFIG_LOCK = threading.Lock()` held across read, modify and write in `set_config`,
  `set_setting`, `set_harness`, `add_project`; the tmp file named per call (`config.json.<pid>.<thread>.tmp`).
- `server.py`: `save_models` and `_setting` catch OSError and answer 500 with the reason.
- `tuning._number`: `try: float(value) except OverflowError` returns the range reason; one test.
- `Hub.reload_tuning`: a `tuning.KEYS` key missing from the file resets to `copy.deepcopy(paths.DEFAULTS[key])`;
  values `tuning.validate` refuses are dropped with a console.log line.
- Tests: two threads saving different keys both land; huge int is a 400; deleted key resets.

**Task 2: plan and replan edges (B1 to B5, K12, K14, G1).**
- `_ended`: a `Replan:` line from a design step is refused (`replan refused: design step`); `design_prompt.md:95`
  says to ask for a search before the design step instead.
- `replan.check`: when the answer has no edit kind and an edit step before `n` exists, append a verify of the last
  edit step.
- `task_levers`: `answer` requires `task.get("plan")`; `_ended` treats `Plan gap:` as special only with a plan.
- `plan.design_input`: on `task.get("redo")`, also append the notes of done steps after `n`.
- `_ended` on a single plan after a redo: pop `part`/`hard`, reset `Part k:` goals, remove `plan/` before `plan.save`.
- Room: `task_max_steps - n - done_after_n`, and one helper used by `_ended` and `replan.check`.
- Redo waits while `task["id"] in self.briefing` (lever reason `brief still writing`).
- `edit_plan`: also require state running or waiting.
- Tests: one per bullet, using the reproductions in section 1.

**Task 3: routing and fills (B10 to B12, K7 to K9, G5).**
- `step_route`: after the rung is settled, `share` from the rung's own budget when still None.
- `fills.peak_add`: catch `(ValueError, TypeError)`.
- `start_step`: `reload_models()` before `_route_for`.
- `usage._read` returns a sentinel for unreadable (not missing); writers then skip and move the file to
  `usage-days.json.bad`; `save_days` catches OSError.
- `usage.add_other` returns the dict it wrote under `FILE_LOCK`; `count_run` assigns it under `self.lock`.
- `poll_once`: `count_run` in `try/except Exception` with a log line.
- `rung_ok`: `model gone from models.json: <rung>`; `_ladder_from` keeps only `claude_cli.MODELS` tiers;
  `reload_models` logs dropped entries.

**Task 4: handoff and facts (K3 to K6, G2).**
- `auto_steps`: a refused handoff pull falls through to the `due` check and is recorded once per turn end.
- `git_snapshot`: `-c core.quotePath=false` on both git calls; untracked caps 100 files and 256 KB;
  line counting moved out of `tlock` (snapshot taken before `advance` takes the lock, passed in).
- `_task`: send a copy with `git_base` removed from every step.
- Task page as-sent view: `meta.cut` items appended under Findings as struck `li.cut`, through `normItem`.
- Tests: quoted path counts lines; `/api/task` has no `git_base`; refused auto handoff still escalates.

**Task 5: window (B6, B8, B9, G3, G4, G7, G9, 25 nits).**
- `modelChanges`: post only the tiers that differ; hidden rows get the remove button.
- `_measure`: `n.isascii() and n.isdigit() and len(n) <= 4`; test with `%C2%B2`.
- `showPage`: leaving the Board for anything but a session opened from it calls `board(false)` and clears
  `boardFrom`; `boardKey` skips focused buttons and selects.
- Plan fold keys mapped to the six pinned keys; `.chain .row.short` rule; `cost unknown` wording; allowance rows
  red when out of range; `routePane` inline style moved to a class; dead `ITABS`, `at`, `run` removed.
- Checked in headless Chromium at 400, 340 and 900 px with the fake claude, as the earlier window tasks were.

**Task 6: harness edges (K10, K11), after Fred's live check of plan 5 Task 7.**
- Adapters without an interrupt: after the final event, a 10 s grace, then `adapter.stop`, ending as success.
- Codex on a `.cmd` shim: `cwd=` instead of `-C`, bare `model_reasoning_effort=high`.
- `kill_tree`: `os.killpg` on POSIX (start runs with `start_new_session=True` there), taskkill on Windows, so the
  step timeout also works on Linux.
- Both wait on what the live check shows OpenCode and cmdc actually do at exit.

**Task 7: docs.** PLAN.md History line for plan 27; amend the plan texts the review found wrong (24's step order
and fake word, 23's 1.2 blank lines and the cut view, 25 2.8's key guard, 5's opencode TIERS block).

### Questions for Fred (each written for (a))

- **Q1, a pick whose harness is off (G6).** (a, recommended) keep plan 18's behaviour, balance within the tier, and
  record it in plan 5 decision 12. (b) restore decision 12: run Claude's rung of the same tier.
- **Q2, Task 6 timing.** (a, recommended) place Tasks 1 to 5 now and Task 6 after your plan 5 live check. (b) place
  Task 6 now on the inferred exit behaviour.
