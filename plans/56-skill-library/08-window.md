# Task 8: the window contract (chip, Received, multi-selects, Skills tab)

> **Depends on plan 55** ([../55-autopilot-ui/](../55-autopilot-ui/), the web build of the locked autopilot design,
> being written 2026-11-07; the folder may not exist when this file is read). Both plans edit the Board, the Prep card and
> the Models page of `web/app.js` and `web/style.css`. Build this task only after plan 55's web build has landed, and
> read its README first for the names of the parts it made (chip, row, card, form, tab strip); where this file names a
> function, the builder uses plan 55's equivalent.
> **This file gives the data contract and the behaviour tests only. It makes no visual decision**: layout, spacing,
> colour and wording beyond the strings quoted here are the UI chat's work, drawn from the locked files in
> `design/rework/locked/` (CLAUDE.md rule: tokens first in `web/style.css`; no emoji, no em-dash; 340 px; state never
> colour alone).

**Files**
- Modify: `console/server.py` (`task_row` steps: three keys, below)
- Modify: `web/app.js`, `web/style.css`, `web/index.html` only as plan 55's structure requires
- Modify: `tests/test_web.py` (render tests in Node), `tests/test_server.py` (the `task_row` keys)

Commit boundary: `feat: the window shows and edits the skill library (plan 56 T8)`.

## 8.1 The one server change

`task_row(...)["steps"]` (the explicit list at `console/server.py` ~4228) gains `"skills": s.get("skills") or []`,
`"skills_by": s.get("skills_by") or ""`, `"skills_kb": s.get("skills_kb") or 0`. `GET /api/task` already returns the step
dicts whole (minus `git_base`, `touched`), so `skills`, `skills_by`, `skills_kb` and `skills_in` are there with no change.
Test: `test_task_row_and_get_task_carry_the_skills_keys` (a step with and without them; a step from before the library
gives `[]`, `""`, `0`).

## 8.2 Data contract, surface by surface

| Surface | Reads | Writes | Behaviour the tests pin |
|---|---|---|---|
| Step chip (a step row's second line) | the step's `skills`, `skills_by`, `skills_kb` (`GET /api/task`, snapshot rows) | nothing | text `skills: a, b`; the title carries `picked by <skills_by>` and `<skills_kb> KB`; **absent when `skills` is empty or missing** (every pre-library task); for a step whose `harness` is `codex` or `opencode` the title adds `this CLI may also list its own skills` (README section 2) |
| Received tab / Files tab | `GET /api/task/file?task&step&name=skills.md`; the Files list from `step_files` (already includes `skills.md`, Task 3) | nothing | `skills.md` opens like `role.md`; absent for a step with no skills |
| Task head note | `GET /api/config` `skills_error` | nothing | when non-empty the head says `skills: index.json invalid`; nothing otherwise |
| Prep card, one multi-select per step row | `GET /api/config` `skills` (rows with `hand`; ok rows first; the others dimmed with their `why`) | `POST /api/task` step row `skills: [names]` | the control starts at `Auto` (the key is **omitted**: code picks when the step starts); choosing any set, or `None`, sends the list (`None` = `[]`); the auto-inserted verify has no control |
| Add next step form | `POST /api/task/next/preview` -> `skills: {names, by, tags, files, dropped}` | `POST /api/task/next` `skills: [names]` only when Fred changed the control; absent otherwise | the control is preset to `names`; a line `picked by code from tags <tags>` (or `picked by you`); `None` sends `[]`; every change re-previews (the revision covers the list, Task 6) |
| Supervisor suggestion card (`add_next_step`) | `supervisor.pending.decision.skills` | nothing (Approve and Reject are unchanged) | the names the pass proposed are listed on the card; none when the field is absent |
| Models page, Skills tab | `GET /api/config` `skills`, `skills_error`, `skills_tags`; `GET /api/skill?name=` | `POST /api/skill` (Task 7) | below |

The Skills tab sits next to Kinds, Tiers and Tuning. Its behaviour:

- A list of the rows in index order, unindexed last; each shows name, `description`, `kb`, `kinds`, `tags`, `paths`,
  `always`, and `why` when not empty (a row whose `hand` is false cannot be picked anywhere; an unindexed one is dimmed
  and says `not in index.json`).
- Selecting a row loads `GET /api/skill`. The text editor shows the raw SKILL.md with no length limit; a pointer skill
  shows the text read-only with the line `points to ~/.claude/skills/<name>; edit it there`.
- The entry fields: `description` (text), `kinds` (multi-choice of the step kinds), `tags` (words, comma separated),
  `paths` (globs, one per line), `always` (switch). Save posts only what changed: `{name, text?, entry?}`; the whole
  entry object goes when any entry field changed. Reset posts `{name, reset: true}` and is offered only when `seed` is
  not empty.
- New skill: a name field (`NAME_RE`) plus the text; the first Save creates it (D8). There is no Delete.
- Errors from the route (`error` strings of Task 7's table) are shown beside the control that caused them; a `409
  index.json is invalid` explains the hand fix. A one-line help text says the first save normalizes the formatting of
  `index.json` and that the window cannot delete a skill.
- Dirty and discard behaviour copies the Kinds tab's (`kindRow` / `kindsTab`, `web/app.js` ~2468-2500, or plan 55's
  equivalent). Nothing here writes `config.json`.

## 8.3 Tests first (red before the code)

`tests/test_web.py` (Node render tests in the file's existing style; function names are plan 55's, the assertions are on
the output):
- `test_skills_chip`: a step with `skills: ["a", "b"]`, `skills_by: "code"`, `skills_kb: 6.1` renders `skills: a, b`
  and a title with `picked by code` and `6.1 KB`; a step with `[]`, with no keys, and a `chat` step render nothing; a
  `codex` step's title has the extra sentence.
- `test_prep_card_skill_control`: with `cfg.skills` the options list hand rows, dim the non-ok ones with their `why`;
  the posted step row has no `skills` key until the control is touched; `None` posts `[]`.
- `test_add_next_step_skill_control`: the preview preset fills the control; the request omits `skills` when untouched and
  carries the list when changed; the `picked by` line reads the preview's `by` and `tags`.
- `test_skills_tab`: rows render with `why` and the dim state; a pointer row is read-only; Save builds `{name, text}`,
  `{name, entry}` or both from the changed fields only; Reset appears only with a seed; a route error is shown; no
  Delete control exists; the tab strip has `Skills` after `Kinds`.
- `test_head_note_for_a_bad_index` and `test_suggestion_card_lists_proposed_skills`.
- 340 px and no-emoji/no-em-dash checks reuse the existing scans in `tests/test_web.py` (they must stay green).

`node --check web/app.js` after every edit. Plan 55's own headless pass (its Task for the web build) is where the
browser look is checked; this task adds the skills surfaces to that pass's list.

## 8.4 Steps and acceptance

- [ ] 1. Confirm plan 55's web build has landed; read its README; list the parts this task reuses.
- [ ] 2. Write the tests; run `py -m unittest tests.test_web tests.test_server` red for the new names.
- [ ] 3. The `task_row` keys, then the surfaces one at a time, each with its test green.
- [ ] 4. `node --check web/app.js`; full suite green; commit with the message above (stage only this plan's hunks of
      `web/app.js`).
