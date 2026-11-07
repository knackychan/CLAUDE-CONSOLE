# Task 1: `console/build.py`, the build module (README 4.1 to 4.4, 4.8)

Files: `console/build.py` (new, about 260 lines), `console/paths.py` (`build_cap_usd`), `console/tuning.py` (the key),
`tests/test_build.py` (new), `tests/test_tuning.py`.
Commit boundary: `feat: the build module: sub-plan items, build.json, moves, prompt, summary (plan 53 Task 1)`.
Pure: no threads, no HTTP, no model call; the file functions at the end are the only IO, shaped like `tasks.load`,
`tasks.save`, `tasks.log`, `tasks.read_chain`.

## Constants

```python
DIR, FILE, LOG = "builds", "build.json", "build.jsonl"
LEVELS = ("gated", "auto")                                                   # D1
BUILD_STATES = ("planned", "running", "waiting", "stopped", "done")
ITEM_STATES = ("planned", "preparing", "ready", "held", "running", "accepted", "skipped", "failed")
BUILD_KEYS = ("id", "project_dir", "project", "title", "folder", "goal_file", "level", "cap_usd", "state", "owner",
              "why", "current", "pause_after", "created", "updated", "ended", "items")
ITEM_KEYS = ("n", "file", "title", "state", "prep", "task", "cost", "drift", "drift_note", "retried", "why",
             "started", "ended")
DONE_SHOWN, FILES_SHOWN, QUESTIONS_SHOWN = 20, 6, 6                          # README 4.4
TITLE_MAX, CAP_MAX, ITEMS_MAX = 80, 10000, 60
_ITEM = re.compile(r"^(\d{1,3})-(.+)$")                                      # D5: NN-<name>.md or NN-<name>/README.md
NOT_ITEMS = ("readme.md", "plan.md")                                         # the folder's own index files
_HEAD = re.compile(r"^#\s+(.+?)\s*$", re.M)
LIMIT_WHY = limits.TEXT                                                      # D8: a stuck why that names a usage limit
```

## Items from a folder (D5)

```python
def rel_ok(project_dir: str, path: str) -> str:
    """"" when `path` is a relative path under `project_dir` (forward or back slashes, no "..", not absolute, not
    empty, no NUL); else the reason ("not a relative path", "leaves the project", "empty path")."""

def items_from(project_dir: str, folder: str) -> list:
    """[{"n": 1, "file": "<folder>/01-paths.md", "title", "words"}] for every `NN-*.md` file and `NN-*/README.md`
    directly under `folder`, sorted by (NN, name); numbering restarts at 1 in list order (two files with the same NN
    keep both, name order). The folder's own README.md and PLAN.md are not items. A file that cannot be read gives
    title = its stem and words 0. Raises ValueError (the route's 400) when rel_ok refuses or the folder is missing.
    At most ITEMS_MAX items."""

def title_of(text: str, fallback: str) -> str:
    """The first `# ` heading, as written (`Plan 3: Paths`, `Part 2: Settings` keep their prefix), clipped to
    TITLE_MAX; else `fallback` (the stem with its NN- prefix removed, dashes to spaces)."""
```

Reads are `Path(project_dir, folder)`; the returned `file` is always `folder + "/" + name` with forward slashes, so
the prompt and the row show what Fred typed.

## The build and its moves

```python
def new_build(project_dir: str, project: str, title: str, folder: str, goal_file: str, items: list, level: str,
              cap_usd: float, now: float) -> dict:
    """A build dict (README 4.2): state planned, owner service, current 0, every item planned with prep/task "",
    cost 0, drift "", retried 0, why "", started/ended None. ValueError on an unknown level, a cap outside
    0..CAP_MAX, no items, or a title over TITLE_MAX after clip (the title defaults to the folder's last part)."""

def whole(b) -> bool          # every BUILD_KEYS key, items a list of dicts with every ITEM_KEYS key, states known
def current_item(b: dict):   # the item with n == b["current"], or None (before Start, after the end)
def _line(now, n, frm, to, why="") -> dict   # {"ts", "n", "from", "to", "why"} (README 4.3)
def move(b, state, why, now, lines) -> None  # build-level: appends `build:<old> -> build:<new>`, sets updated
def move_item(b, item, state, why, now, lines) -> None  # `item:<old> -> item:<new>`; sets item["why"], started on
                                                         # preparing, ended on accepted/skipped/failed
def close_item(b, item, state, why, cost, now, lines) -> None:
    """accepted | skipped | failed with the cost (0 for skipped); then: current -> the next item's n (the next
    planned one; a skipped later item is passed over), or len(items)+1 and build done with the `done: 8 accepted,
    1 skipped, $84.20` line; pause_after -> owner fred, why `paused after NN`, state waiting (README 4.5)."""
```

`fred(b, lever, now, n=0, level="", cap=None, spent=0.0) -> (ok, why, lines)`, Fred's levers with no Hub (the service
checks the task side first, Task 3):

| lever | allowed when | does |
|---|---|---|
| `start` | state `planned` or `stopped` | state `running`, owner `service`; current 1 when 0; line `started by Fred` |
| `stop` | state `running` or `waiting` | state `stopped`, owner `fred`, why `stopped by Fred`; the current item keeps its state (a `preparing` item goes back to `planned`: the job is dropped by the service) |
| `pause` | `running` or `waiting`, not already | `pause_after` true; line `pause after NN by Fred` |
| `resume` | owner `fred` (paused) | owner `service`, state `running`, why `""`; also clears `pause_after` |
| `skip` | item `n` is the current one in planned, preparing, ready, held, failed, or a done task's item waiting for Accept; or a later planned item | `close_item(skipped)` for the current one; a later item just `skipped` (no current move) |
| `level` | `level in LEVELS` | sets it; line `level gated -> auto by Fred` |
| `cap` | 0..CAP_MAX | sets `cap_usd`; line `cap 25 -> 40 by Fred`; a `waiting` build whose why starts with `cap:` returns to `running` when spent < cap (the service passes spent: `fred(..., cap=cap, spent=x)`) |

`continue` is not here: it needs the Hub (Prep again, or create_task). Refusals: `(False, "build is done", [])`,
`"not paused"`, `"already paused"`, `"item 3 is running"`, `"unknown level"`, `"cap: a number between 0 and 10000"`.

## The item prompt (README 4.4)

```python
def prompt(b: dict, item: dict, done: list, questions: list) -> str:
    """`done`: [{"n", "title", "state", "files": [...]}] for every closed item before `item` (the service builds it
    from tasks.summary of each item's task); `questions`: the open questions of the previous accepted item's
    summary. Clips: DONE_SHOWN items ("... 3 more"), FILES_SHOWN files per item, QUESTIONS_SHOWN questions; the
    whole text under tasks.GOAL_MAX (the done list is cut first). Goal line absent when goal_file is ""."""

def context(b: dict, item: dict, done: list, questions: list) -> dict:
    """card["build"] (README 4.6): {"id", "n", "of", "title", "file", "goal_file", "done", "questions"}, the same
    clips as prompt."""
```

## Spent, accept and the limit retry

```python
def spent(b: dict, cost_of) -> float:
    """Closed items' cost plus cost_of(task_id) of the current item's task when it has one; `cost_of` returns the
    task's step costs plus its card's cost (the service: sum(step_cost) + task["prep"]["cost"]). 4 decimals."""

def acceptable(task: dict, summary: dict, card_visible: bool) -> str:     # D6
    """"" when an auto build may accept `task`: state done, not accepted, the last verify step (highest n with
    kind verify) has verdict PASS or there is no verify step, summary["questions"] is empty, not card_visible.
    Else the reason: "2 open questions", "verify FAIL", "supervisor card", "not done"."""

def limit_stuck(task: dict, limits_now: dict, now: float) -> bool:        # D8
    """True when task is stuck, its why matches LIMIT_WHY, the current item has retried 0, and no entry of
    `limits_now` (Hub.limits after its expiry sweep) keys the current step's model: limits.provider(model) or the
    model itself (plan 45)."""
```

## The row and the summary

```python
def row(b: dict, task_row=None, now: float = None) -> dict:
    """README 4.8. `line`: README section 5's sentence: waiting -> "needs you · " + why (or "held · " + why for a
    held item at auto, "paused after NN"); stopped -> "stopped · 3 of 9"; done -> "done · 8 sub-plans · $84.20";
    running with a task -> "build · 3 of 9 · 03" (the page appends that task's own status line: the row carries
    `item.task`, Task 4's buildLine); running without a task -> "build · 3 of 9 · preparing".
    `group`: needs when waiting or task_row["group"] == "needs"; done when done or stopped; else working."""

def summary(b: dict, task_summaries: dict) -> dict:
    """{"items": [{"n", "title", "state", "cost", "files", "questions"}], "accepted", "skipped", "failed", "cost",
    "files": deduplicated in item order, "questions": every open one}; task_summaries maps task id -> tasks.summary
    of that task (the service reads them); an item without a task has files [] and questions []."""
```

## Files

```python
def folder(home, build_id) -> Path    # home / DIR / id; ValueError on an unsafe id (tasks.safe_id)
def save(home, b) -> None             # json through a temp file (paths.write_text_atomic), as tasks.save
def load(home, build_id)              # the dict, or None when missing, unreadable or not whole
def load_all(home) -> dict            # id -> build, every builds/*/build.json that loads
def log(home, build_id, lines) -> None       # append to build.jsonl, masked (redact.mask on why)
def read_chain(home, build_id, limit=200) -> list
def delete(home, build_id) -> bool    # shutil.rmtree of the folder; False when absent
```

## Config

`paths.DEFAULTS["build_cap_usd"] = 25` with the comment `# plan 53 D4: a new build's cap, 0 = none`;
`tuning.TUNING["build_cap_usd"] = ("build", "usd", 0, 10000)`; the Models page shows it in a new group "build" by
itself (the page draws groups from the view; no web change).

## Tests (first, red), `tests/test_build.py`

- `test_items_from_folder_in_number_then_name_order`: a temp project with `plans/02-b.md`, `plans/01-a.md`,
  `plans/01-c/README.md`, `plans/README.md`, `plans/notes.md`: items are 01-a, 01-c, 02-b with n 1, 2, 3; titles from
  the headings; `notes.md` and `README.md` absent.
- `test_items_from_refuses_paths_outside_the_project`: `..`, an absolute path and a missing folder raise ValueError
  with the rel_ok reason.
- `test_new_build_and_whole`: the dict has every key; `whole` rejects a missing key and an unknown state.
- `test_fred_levers`: start from planned and from stopped; stop keeps the item; pause then resume; skip the current
  planned item advances `current`; skip a later item leaves `current`; skip of a running item refused; level and cap
  lines; a cap raise above spent returns a cap-held build to running.
- `test_close_item_advances_pauses_and_ends`: three items; accepted -> current 2; pause_after -> owner fred and the
  `paused after 02` why; the last close -> done with the summary line.
- `test_prompt_lists_done_items_questions_and_clips`: the lines of README 4.4 in order; no Goal line without a goal
  file; 25 done items show 20 and `... 5 more`; the whole text under GOAL_MAX with a long done list.
- `test_acceptable_rule`: PASS with no questions -> ""; a FAIL verify, two questions, a visible card, a not-done
  task each give their reason; no verify step at all -> "".
- `test_limit_stuck`: a stuck task with "usage limit" in its why and an expired entry -> True; a live entry for its
  provider -> False; retried 1 -> False; a stuck why without the words -> False.
- `test_row_groups_and_lines`: waiting -> needs and "needs you · ..."; done -> "done · 8 sub-plans · $84.20";
  running with a task row in needs -> group needs.
- `test_summary_dedupes_files_in_item_order`.
- `test_save_load_log_delete_round_trip`: builds/<id>/build.json and build.jsonl; a file that is not whole is skipped
  by load_all; delete removes the folder.
- `tests/test_tuning.py::test_build_cap_key`: the key validates in 0..10000, a string is refused.
