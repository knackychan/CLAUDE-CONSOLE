# Task 1: `console/build.py`, the build module (README 4.1 to 4.4, 4.8)

Files: `console/build.py` (new, about 300 lines), `console/paths.py` (`build_cap_usd`), `console/tuning.py` (the key),
`tests/test_build.py` (new), `tests/test_tuning.py`. No web file: the Models page row for the key is Task 4.
Commit boundary: `feat: the build module: sub-plan items, build.json, moves, prompt, summary (plan 53 Task 1)`.
Pure: no threads, no HTTP, no model call; the file functions at the end are the only IO, shaped like `tasks.load`,
`tasks.save`, `tasks.log`, `tasks.read_chain`. Checked against HEAD `9b6f988` (2026-11-07): `tasks.safe_id` takes ids of
up to 20 characters from `[0-9a-f-]`, which the 20-character build id fits; `redact.mask` and `redact.clip` exist;
`limits.TEXT` is a compiled regex (use `.search`); `tasks.GOAL_MAX` is 6000; `tasks.prep_id(task)` is the Prep id of a task.

## Constants

```python
DIR, FILE, LOG = "builds", "build.json", "build.jsonl"
LEVELS = ("gated", "auto")                                                   # D1
BUILD_STATES = ("planned", "running", "waiting", "stopped", "done")
ITEM_STATES = ("planned", "preparing", "ready", "held", "running", "accepted", "skipped", "failed")
BUILD_KEYS = ("id", "project_dir", "project", "title", "folder", "goal_file", "level", "cap_usd", "state", "owner",
              "why", "current", "pause_after", "created", "updated", "ended", "items")
ITEM_KEYS = ("n", "file", "title", "state", "prep", "task", "cost", "drift", "drift_note", "retried", "why",
             "sha", "files", "questions", "started", "ended")                # sha, files, questions: README 4.2
LIVE = ("running", "waiting")                                                # a build in these states is live (F14)
DONE_SHOWN, FILES_SHOWN, QUESTIONS_SHOWN = 20, 6, 6                          # README 4.4
TITLE_MAX, CAP_MAX, ITEMS_MAX = 80, 10000, 60
LINT_WORDS, LINT_TASKS = 1200, 3                                             # README D5 note: defaults for Fred
OPEN_WORDS = re.compile(r"\b(TBD|TODO|choose|either)\b|\bif needed\b", re.I) # the words design.md bans from Decisions
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

def digest(project_dir: str, items: list) -> str:
    """The first 16 hex characters of the sha256 over `file|size|mtime_ns` of every item, in list order, one per
    line (a file that cannot be read counts as `file|-|-`). The preview returns it; Create must send it back and the
    service compares it with a fresh one (README 4.7, F10). Pure but for the stat calls."""

def file_sha(project_dir: str, file: str) -> str:
    """The first 16 hex characters of the sha256 of the file's bytes, "" when it is not a readable file. The item's
    `sha` (README 4.2) is taken with it when the item's Prep starts."""

def lint(text: str, goal: bool = False) -> list:
    """Mechanical warnings, short plain sentences, [] when clean; never raises, never refuses anything. For a
    sub-plan (goal False): `no Done check with a command` unless a line containing "done check" (any case) is
    followed within three lines by a backticked or fenced command; `N words, over LINT_WORDS` when longer;
    `N Task/Step headings, over LINT_TASKS` when more `#{2,4} (Task|Step) \d+` headings than that. For the goal
    file (goal True): `no Decisions heading` when no heading line contains "decisions"; else `open decision words:
    <words>` for OPEN_WORDS found between that heading and the next heading of the same or higher level."""
```

Reads are `Path(project_dir, folder)`; the returned `file` is always `folder + "/" + name` with forward slashes, so
the prompt and the row show what Fred typed.

## The build and its moves

```python
def new_build(project_dir: str, project: str, title: str, folder: str, goal_file: str, items: list, level: str,
              cap_usd: float, now: float) -> dict:
    """A build dict (README 4.2): state planned, owner service, current 0, every item planned with prep/task "",
    cost 0, drift "", retried 0, why "", sha "", files [], questions [], started/ended None. `items` is the list
    the service built from the preview's `keep`. ValueError on an unknown level, a cap outside
    0..CAP_MAX, no items, or a title over TITLE_MAX after clip (the title defaults to the folder's last part)."""

def whole(b) -> bool          # every BUILD_KEYS key, items a list of dicts with every ITEM_KEYS key, states known
def current_item(b: dict):   # the item with n == b["current"], or None (before Start, after the end)
def _line(now, n, frm, to, why="") -> dict   # {"ts", "n", "from", "to", "why"} (README 4.3)
def move(b, state, why, now, lines) -> None  # build-level: appends `build:<old> -> build:<new>`, sets updated
def move_item(b, item, state, why, now, lines) -> None  # `item:<old> -> item:<new>`; sets item["why"], started on
                                                         # preparing, ended on accepted/skipped/failed
def close_item(b, item, state, why, cost, now, lines, files=(), questions=()) -> None:
    """accepted | skipped with the cost (0 for skipped) and the task summary's `files` and `questions` at this
    moment, stored on the item (README 4.2; [] for skipped); then: current -> the next item's n (the next planned
    one; a skipped later item is passed over), or len(items)+1 and build done with the `done: 8 accepted, 1 skipped,
    $84.20` line; pause_after -> owner fred, why `paused after NN`, state waiting (README 4.5). `failed` (a Deleted
    task) is not closed here: `move_item` sets it, `current` stays on it, and Continue or Skip decides."""

def live_in_project(builds: dict, project_dir: str, except_id: str = "") -> str:
    """The title of another build of `project_dir` (tasks.same_dir) whose state is in LIVE, else "" (README F14)."""
```

`fred(b, lever, now, n=0, level="", cap=None, spent=0.0) -> (ok, why, lines)`, Fred's levers with no Hub (the service
checks the task side first, Task 3):

| lever | allowed when | does |
|---|---|---|
| `start` | state `planned` or `stopped` | state `running`, owner `service`; current 1 when 0; line `started by Fred`. The service refuses first, with 409, when `Hub._base` for the project is not empty or `live_in_project` names another build (README 4.7); `fred` itself knows neither |
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
    summary (the service reads them from the closed items' stored `files` and `questions`, README 4.2, never from
    a task folder). Clips: DONE_SHOWN items ("... 3 more"), FILES_SHOWN files per item, QUESTIONS_SHOWN questions; the
    whole text under tasks.GOAL_MAX (the done list is cut first). Goal line absent when goal_file is "". The last
    line is README 4.4's (follow the code, name the stale lines; no DECISION block)."""

def context(b: dict, item: dict, done: list, questions: list) -> dict:
    """card["build"] (README 4.6): {"id", "n", "of", "title", "file", "goal_file", "done", "questions"}, the same
    clips as prompt."""
```

## Spent, accept and the limit retry

```python
def spent(b: dict, cost_of) -> float:
    """Closed items' cost plus cost_of(task_id) of the current item's task when it has one; `cost_of` returns the
    task's step costs plus its card's cost (the service: sum(step_cost) + task["prep"]["cost"]). 4 decimals."""

def acceptable(task: dict, summary: dict, card_visible: bool, busy: str = "") -> str:     # D6
    """"" when an auto build may accept `task`: state done, not accepted, the last verify step (highest n with
    kind verify) has verdict PASS or there is no verify step, summary["questions"] is empty, not card_visible, and
    `busy` is "". `busy` is the service's reason that the task is not settled: "brief writing" (task["briefing"] or
    its id in Hub.briefing) or "supervisor pass pending" (its id in Hub.wakes or Hub.supervising); the open
    questions come from the last brief, and the done wake may leave a card. Else the reason, in this order: "not
    done", "already accepted", "verify FAIL", "2 open questions", "supervisor card", then `busy`. (A done task's last
    verify is PASS unless Fred used Finish on a task that failed twice, which is the "verify FAIL" case.)"""

def limit_key(task: dict) -> str:
    """The limits.json key a usage-limit stuck task waits on: the current step's `limit` when it has one (set when the
    run hit the limit), else the text of the task's `why` before its first ": " (Hub.limited writes `<key>: <why>,
    until HH:MM`), "" when neither. A step that never started this attempt has no `limit` of its own."""

def limit_stuck(item: dict, task: dict, limits_now: dict) -> bool:        # D8
    """True when task is stuck, its why matches LIMIT_WHY.search, `item["retried"]` is 0,
    `limit_key(task)` is not "" and is not a key of `limits_now` (the unexpired entries of Hub.limits: the
    service passes {k: v for k, v in hub.limits.items() if v["until"] > now}). The key is the provider or the rung
    itself (plan 45); matching it by the task's own key avoids guessing a provider from a model name."""
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
    "files": deduplicated in item order, "questions": every open one}. A closed item reports its own stored `files`
    and `questions` (README 4.2), so a Deleted task changes nothing; `task_summaries` maps task id -> tasks.summary
    and is read only for an item still `running` (the service passes it for the current one); an item without a task
    has files [] and questions []."""
```

## Files

```python
def folder(home, build_id) -> Path    # home / DIR / id; ValueError on an unsafe id (tasks.safe_id)
def save(home, b) -> None             # paths.write_text_atomic(folder(home, b["id"]) / FILE, json), exactly as tasks.save
def load(home, build_id)              # the dict, or None when missing, unreadable or not whole
def load_all(home) -> dict            # id -> build, every builds/*/build.json that loads
def log(home, build_id, lines) -> None       # append to build.jsonl, masked (redact.mask on why)
def read_chain(home, build_id, limit=200) -> list
def delete(home, build_id) -> bool    # shutil.rmtree of the folder; False when absent
```

`save` is the one place a build file is written whole (plan 54, README 4.1): it calls `paths.write_text_atomic` and
nothing else, with no `.tmp`, `os.replace`, in-place write or retry of its own. The caller holds `Hub.tlock` (the lock
all build moves take), so `save` takes no lock of its own and keeps the caller's. `log` is an append, like
`tasks.log`. The module imports `paths` for this and for nothing else.

## Config

`paths.DEFAULTS["build_cap_usd"] = 25` with the comment `# plan 53 D4: a new build's cap, 0 = none`;
`tuning.TUNING["build_cap_usd"] = ("build", "usd", 0, 10000)`. The service sends it in `tuning.view` at once, but the
Models page draws only the keys that have a `TUNE` entry and the groups that have an `MGROUP` entry in `web/app.js`
(`tuneRow`, the `MGROUP` loop), so the row appears with Task 4's two small entries (`04-window.md`), not by itself.
`tests/test_tuning.py::test_whitelist_is_the_contracts` pins the exact set of `tuning.KEYS`, so it gains `"build_cap_usd"`
(that edit is part of this task, tests first); `test_every_key_has_its_default_range_and_group` loops over `TUNING` and
needs no change.

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
  task, an already accepted task each give their reason; no verify step at all -> "".
- `test_acceptable_waits_for_the_brief_and_the_done_wake`: everything else clean, `busy="brief writing"` and
  `busy="supervisor pass pending"` give those reasons and a clean call gives "" (the service builds `busy` in Task 3).
- `test_limit_stuck`: a stuck task with "usage limit" in its why and a key absent from `limits_now` -> True; the key
  present -> False; `item["retried"] == 1` -> False; a stuck why without the words -> False; a task not stuck -> False.
- `test_limit_stuck_takes_the_key_from_the_why`: a stuck task whose step has no `limit` and whose why is
  `claude: You've hit your limit, until 08:00 (after one retry)` -> `limit_key` is `claude`; with a step `limit` of
  `opencode:openai` that key wins; a why that does not start with a key and a step without `limit` -> "" and False.
- `test_close_item_keeps_files_and_questions`: `close_item(..., files=[...], questions=[...])` stores them on the item;
  `summary` reports them for a closed item with no entry in `task_summaries`.
- `test_lint_sub_plan_and_goal_file`: a file with a `Done check` line and a backticked command -> []; one without ->
  `no Done check with a command`; 1300 words -> the size warning; four `### Task N` headings -> the headings warning; a
  goal file with `Decisions` and `choose` under it -> `open decision words: choose`; one with no Decisions heading ->
  `no Decisions heading`; binary or empty text -> [] without raising.
- `test_digest_changes_with_a_file_and_file_sha_reads_bytes`: edit, add, remove a file -> a different digest; the same
  folder -> the same digest; `file_sha` of a missing file is "".
- `test_live_in_project`: a running build of the same dir (spelled with different case or slashes) is named; a stopped,
  done or planned one is not; `except_id` skips itself.
- `test_row_groups_and_lines`: waiting -> needs and "needs you · ..."; done -> "done · 8 sub-plans · $84.20";
  running with a task row in needs -> group needs.
- `test_summary_dedupes_files_in_item_order`.
- `test_save_load_log_delete_round_trip`: builds/<id>/build.json and build.jsonl; a file that is not whole is skipped
  by load_all; delete removes the folder.
- `test_save_uses_the_shared_writer` (plan 54): with `paths.write_text_atomic` patched by `mock.patch.object(paths,
  "write_text_atomic")`, `build.save(home, b)` calls it once with `builds/<id>/build.json` and the JSON text and writes
  nothing else; `os.replace` patched to fail is never reached by `save`; the folder holds no `.tmp` afterwards. `folder(home, "../x")` raises ValueError (an unsafe id)
  before any file is opened.
- `test_save_while_a_metadata_reader_is_open` (Windows only, `@unittest.skipUnless(os.name == "nt")`, built like
  `tests/test_atomic.py::WindowsAtomicTest::test_task_save_while_metadata_reader_is_open`, reusing its
  `metadata_reader`): a handle open on `builds/<id>/build.json` with delete sharing refused for metadata does not stop
  a second `build.save`; the new text is read afterwards and the folder holds only `build.json` and `build.jsonl`.
- `tests/test_tuning.py::test_build_cap_key`: the key validates in 0..10000, a string is refused; and
  `test_whitelist_is_the_contracts` lists `build_cap_usd`.
