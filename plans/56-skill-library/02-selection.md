# Task 2: selection, pure

> Contract: [README.md](README.md) 3.4, 3.5 and the golden tables of section 4. Decision D6.
> BRAINSTORM 14.4 items 1, 2 and 4. No file is written, no model is asked, no Hub state is read.

**Files**
- Modify: `console/skills.py` (`admit`, `pick`, `resolve`, `inputs`, `tags_of`, `files_of`, `rel_files`)
- Modify: `tests/test_skills.py` (`SelectionTest`, `InputsTest`)

Commit boundary: `feat: pick skills by kind, tags and files, with the golden table (plan 56 T2)`.

## 2.1 Functions

```python
def rel_files(project_dir: str, files) -> list
    """Normalize paths for matching: `\` -> `/`, leading `./` removed, an absolute path that is inside `project_dir`
    (compared with os.path.normcase) made relative, an absolute path outside it, an empty string and any path with a
    `..` segment dropped; first-seen order, deduplicated. Never raises."""

def files_of(text: str) -> list
    """README 3.5: the paths a `## Files` / `#### Files` section names, one per line. Never raises."""

def tags_of(text: str, vocab) -> list
    """The first line of `text` that reads `Tags: a, b` (case-insensitive label, optional leading `-`, `*`, `>` or
    backticks), split on commas and spaces, lower-cased, kept when in `vocab`; `Tags: none` and no line give []."""

def admit(row: dict, kind: str) -> str
    """"" when code or the supervisor may use `row` for a `kind` step (row ok, kind in tasks.KINDS, row.kinds empty or
    containing kind), else why: the row's own why, or `not for <kind> steps`. One rule, shared by pick, resolve's `add`
    and (Task 5) supervisor.clean_skills."""

def pick(reg: dict, kind: str, tags, files) -> list        # README 3.4, verbatim
def resolve(reg: dict, kind: str, tags, files, add=(), fred=None) -> dict   # README 3.4, verbatim
def inputs(home, task: dict, step: dict, vocab) -> tuple    # README 3.5: (tags, files); never raises
```

`pick` and `resolve` take the registry dict of Task 1 (`reg["skills"]` rows) and read nothing else. `inputs` reads
`plan.read`, `plan.read_part`, `plan.table`, `plan.section`, `plan.step_section` and `tasks.read_facts` only through the
public helpers named, wraps its reads in `try/except (OSError, ValueError, KeyError)` and returns `([], [])` pieces for
whatever it could not read. It never calls `skills.body`.

Match counting (README 3.4): `matches = len(set(row.tags) & set(tags)) + sum(1 for f in files if any(glob(f, g) for g in
row.paths))` with `glob(f, g) = PurePosixPath(f).full_match(g, case_sensitive=False)` in a `try/except ValueError`
(a malformed glob matches nothing; `check_entry` already refused the obvious ones).

`resolve` returns the dict of README 3.4 with `names` as a list of `str`, `by` as one of `""`, `code`, `supervisor`,
`fred`, and `dropped` entries `{"name", "why"}` in the order met. Reasons: `unknown skill`, the row's own `why`
(for example `marker line: END HANDOFF`, `not in index.json`), `not for <kind> steps`. A `fred` list item that is not a
string is dropped with `unknown skill`.

## 2.2 Tests first (red before the code)

`SelectionTest`
- `test_golden_pick_table`: the fixture registry of README section 4 built through `skills.registry` from a scratch
  library (so the trap rows get their real `why`), then every one of the 16 rows of the table asserted with
  `assertEqual(pick(...), expected)`. The helper `golden_registry()` lives in `tests/test_skills.py` and is imported by
  the later tasks' tests.
- `test_resolve_table`: R1 to R8 of section 4, asserting `names`, `by` and `dropped` (the `why` strings exact).
- `test_pick_is_deterministic_and_pure`: the same call 20 times gives one list; `tags` given as a set, a list in two
  orders or a tuple gives the same list; the input registry compares equal before and after (deepcopy).
- `test_no_count_or_size_limit` (D18): a registry of 200 `always` rows picks 200 names; a row whose body is 300 KB is
  picked exactly like a small one (`pick` never reads a body).
- `test_admit`: an ok row with empty kinds admits any `tasks.KINDS` kind; a row with kinds admits only those and says
  `not for scout steps` otherwise; a row that is not ok returns its own `why`; `chat` and an unknown kind return
  `not for chat steps`.
- `test_a_malformed_glob_never_raises_and_matches_nothing`.
- `test_fred_order_is_kept_and_duplicates_collapse`: fred `[b, a, b]` -> `[b, a]`; add `[c, c]` -> once, after the code's.

`InputsTest` (plan and facts fixtures are built with the same helpers `tests/test_plan.py` and `tests/test_tasks.py`
use; no new fixture format)
- `test_rel_files`: `Web\app.js` -> `Web/app.js`; `./a/b.py` -> `a/b.py`; `D:\proj\console\x.py` with project
  `D:\proj` -> `console/x.py` (and case-insensitively on `d:\PROJ`); `D:\other\x.py` dropped; `../x` and `a/../b` dropped;
  `""` dropped; duplicates collapse.
- `test_files_of_line_forms`: `- web/app.js (change): the chip`, `` `console/x.py` (new): y ``, `* tests/test_a.py: asserts`,
  `> console/z.py`, `web/style.css` bare; a prose line `The files this step touches, from the list above.` gives nothing
  (its first token `The` has neither `.` nor `/`); `- (none)` gives nothing; an empty text, `None` and a
  10,000-character line never raise.
- `test_tags_of`: `Tags: web, ui-ux` with vocab; an unknown word dropped; `TAGS: Web` -> `["web"]`; `Tags: none` -> `[]`;
  the first `Tags:` line wins; a `Tags:` line inside a code fence still counts (the design step writes it plain; the
  rule is only "first matching line").
- `test_inputs_for_a_split_plan_part`: a task whose `plan` meta has two parts, a Sub-plans table whose row 1 `owns`
  `console/a.py`, a part file with `Tags: backend` and a `## Files` section naming `console/b.py (change)`: a step with
  `part == 1` gets files `[console/a.py, console/b.py]` and tags including `backend`.
- `test_inputs_for_a_single_plan_step`: a plan index with `### Step 2: code` holding `Tags: web, ui-ux` and a
  `#### Files` section; step 2 gets those; step 3 (a `verify`, no section) gets the index's `## Files` lines and the
  task tags only.
- `test_inputs_for_a_manual_step`: `step["source_step"] = 1`; the source has `touched == ["web/app.js"]` -> files
  `[web/app.js]`; with no `touched` key, the saved facts file `- web/style.css | +3 -1` style line gives
  `[web/style.css]`; the goal `fix the web tests` with vocab `{web, tests}` adds `web`, `tests`; a non-manual step's goal
  words are ignored.
- `test_inputs_first_source_wins_and_the_design_step_has_none`: a manual step on a task with a plan uses the source's
  files, not the part's; the design step (`step["n"] <= plan["from"]`) and a task with no plan give no files.
- `test_task_tags_merge_in_order_and_are_filtered`: `task["tags"] = ["Web", "nonsense", 3, "web"]` with vocab `{web}`
  gives `["web"]`; the plan's tag comes after the task's, deduplicated.
- `test_inputs_never_raise`: a missing plan file, an unreadable facts file, `task["plan"]` of the wrong type, a part
  number with no part: `inputs` returns lists, no exception.

## 2.3 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_skills` red for the new names.
- [ ] 2. Implement the seven functions. Focused tests green; the Task 1 tests still green.
- [ ] 3. Full suite green. Commit with the message above.
