# Plan 50 - Supervisor settings and spend on the Models and Usage pages

Status: written 2026-10-20 from the supervision review (item 5, and the plan 44 "Models/Usage UI" left open).
D1-D6 are written in as defaults; Fred confirms or changes them before step 1. No code changed.
Lands on plans 26 (Models page), 44 (backend), 48 (Board) and the Usage page (BRAINSTORM 7.5, D13).

## 1. Finding

- The backend takes every supervisor setting through the existing `POST /api/config/models` whitelist
  (`console/tuning.py` KEYS: the nine numeric `supervisor_*` keys in TUNING, plus `supervisor_mode` and
  `supervisor_projects`), and `GET /api/config` sends them (`tuning` and `supervisor_config`, server.py:4007, with
  the comment "no frontend wiring yet").
- The Models page shows none of them. `tuningTab` (app.js:2574) draws only keys listed in `TUNE`, and `MGROUP` has
  no `supervisor` card. `modelChanges` only posts keys of `cfg.tuning`, kinds and tiers, so a mode change could not
  be saved even if it were drawn.
- So the global mode and the per-project modes can only be changed by editing `config.json` by hand. Plan 48's live
  check "a project set to off runs its listed steps as a chain" cannot be done from the window.
- `GET /api/usage` sends `supervisor` (days, today, task_limit, day_limit, error; server.py:431). The Usage page
  never reads it, so the supervisor's own pass spend is invisible (it is not in the transcript totals either).
- The two pass models are fixed by the backend (`tuning.SUPERVISOR_MODELS`: haiku, and sonnet on a stuck or stalled
  wake). The Tiers tab's "Console's own passes" card does not name the supervisor.

## 2. Decisions (defaults, Fred confirms)

| # | Question | Default |
|---|---|---|
| D1 | Where the settings live | A sixth card on the Tuning tab, "Supervisor", after Gauge: the mode row, the projects fold, then the nine numbers. No new tab. |
| D2 | Mode control | One segmented row `off · suggest · auto` (the task menu's segment, plan 48), default `suggest`, with the reset link like other rows. |
| D3 | Per-project modes | A fold "Projects" in the card: one row per configured project (`cfg.projects`) with `default · off · suggest · auto`. `default` removes the project's entry, so the global mode applies. The whole map is posted on Save (the backend replaces it). |
| D4 | What a change affects | Future tasks only (plan 44 4.2: a task keeps its mode). The card's `?` says so, and says that the task menu changes one task. |
| D5 | Usage page | One block after the fills, "Supervisor passes": today `$x of $day_limit` as cells of $0.50, and the month's total and pass count. No calendar tone, and these passes stay out of the transcript totals (they have no transcript). A ledger error shows one red line. |
| D6 | Design | No mock: the card reuses the Tuning row, fold and segment styles and the Usage block reuses the fills row. If Fred wants a mock first, it goes in `design/rework/explored/` and step 3 waits. |

## 3. Changes

### 3.1 `web/app.js`, Models page

- `TUNE` gains labels for the nine numeric keys: `supervisor_debounce_s: ["Wait after a step ends", "s", 1]`,
  `supervisor_parallel: ["Passes at once", "", 1]`, `supervisor_timeout_s: ["Pass timeout", "s", 1]`,
  `supervisor_stall_s: ["Stalled after", "s", 1]`, `supervisor_max_auto_steps: ["Auto steps before you act", "", 1]`,
  `supervisor_max_retries: ["Auto retries per step", "", 1]`, `supervisor_work_usd: ["Auto work spend before you act",
  "$", 1]`, `supervisor_task_usd: ["Pass spend per task", "$", 1]`, `supervisor_day_usd: ["Pass spend per day", "$",
  1]`. The two `rung` keys (`supervisor_model`, `supervisor_stuck_model`) stay out of `TUNE`.
- `MGROUP.supervisor = ["Supervisor", "decides between steps", "<D4 sentence>: the mode for new tasks, per project,
  and the limits of auto mode and of the supervisor's own passes. The task menu changes one task."]`.
- `resetModels()`: `medit.supMode = cfg.supervisor_config.mode`, `medit.supProjects = clone(cfg.supervisor_config.projects)`.
- `modelChanges()`: adds `supervisor_mode` when `medit.supMode` differs from the saved mode, and `supervisor_projects`
  (the whole map) when it differs by `same()`. `tabEdits("tuning")` counts both.
- `supRows()`: drawn first inside the supervisor card by `tuningTab` (like `allowanceFold` for balancing):
  - the mode row: `.tf` with three buttons `data-msup="mode:<m>"`, `aria-pressed` on the pick, `ed` and reset when not
    `suggest`;
  - `fold("Projects", "<n> set · default <mode>", rows)`: one row per `cfg.projects` path, its name, four buttons
    `data-msup="proj:<i>:<m>"` (`default` included); the saved key is matched with `sameDir`, and a change writes the
    entry under the `cfg.projects` spelling (the backend normalizes it) after removing any `sameDir` match.
- The click handler at app.js:2657 adds `[data-msup]`: set `medit.supMode` or the project entry, then `renderModels()`.
- Tiers tab, the "Console's own passes" card: one fixed row `Supervisor · haiku, sonnet on a stuck step` with the
  hint "fixed: the supervisor never runs on opus or fable" (no select).

### 3.2 `web/app.js`, Usage page

- `usageSupervisor()` after `usageFills()` in `renderUsage`: from `usage.supervisor`. Today: the cost as cells of
  $0.50 against `day_limit` (`cellsHtml`, the orange edge at 80 % as the fills do), `$x of $y · n passes`; then the
  month: sum of `days` from `uMonth`'s first day to its end, `$x · n passes`; `unknown` or `reserved` above zero adds
  "· n unknown". `error` shows `<p class="r">The supervisor ledger could not be read: <error></p>`. No block when
  every day in the month is zero and there is no error.
- The footer sentence gains: "Supervisor passes are counted from usage-days.json, apart from the transcripts."

### 3.3 Server

None. Remove the "(no frontend wiring yet)" words from the comment at server.py:4006.

### 3.4 Docs

`CLAUDE.md`: the Models page line gains "including the supervisor mode, its project map and its limits".
`PLAN.md` row 50 and History.

## 4. Tests (first, red)

`tests/test_web.py`, a new `SupervisorSettingsTest`:

- `test_tuning_has_a_supervisor_card`: the card, the nine labels, no select for the two pass models.
- `test_mode_change_posts_supervisor_mode`: a click on `auto` makes `modelChanges()` equal `{supervisor_mode: "auto"}`;
  a click back on `suggest` makes it empty.
- `test_project_mode_posts_the_whole_map`: with projects `D:\a`, `D:\b` and saved `{"d:\\a": "off"}`, setting `D:\b`
  to auto posts both entries; setting `D:\a` to `default` drops it; a saved lower-case key is shown on its project.
- `test_tiers_names_the_supervisor_passes`.
- `test_usage_shows_supervisor_spend`: today cost and limit, the month total and pass count, the unknown note, the
  error line, and no block on a zero month.

`tests/test_tuning.py`: `test_models_post_saves_mode_and_map_together` through
`POST /api/config/models`, as one Save (all or nothing), to pin the contract the page now uses.

## 5. Order and checks

One commit per step, tests first, stage only this plan's lines (other chats edit `web/app.js`, PLAN.md, CLAUDE.md).

1. Tests red (4).
2. Models page (3.1). `py -m unittest tests.test_web`, `node --check web/app.js`.
3. Usage page (3.2).
4. Server comment and docs (3.3, 3.4). Full suite.

Headless check (fake claude, scratch home, as plan 48): change the global mode, set one project to off, Save,
Reload: the values stay; Start a card in that project: `supervised: false`. Usage page with a scratch ledger:
the block reads. 400 and 340 px, dark and light, no horizontal scroll.

Live check (Fred): set a project to off from the Models page and run one card there as a chain.

## 6. Not done here

- The client's `supMode()` mirror of the server's mode rule stays (review item 10).
- A message that names a model (item 3), the Reject hint (item 6), the empty uncertain card after a restart
  (item 8) and stall wakes for other harnesses (item 9).
- No change to which models the supervisor uses.
