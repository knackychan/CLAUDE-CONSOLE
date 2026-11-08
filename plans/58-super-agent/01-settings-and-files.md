# Task 1: settings, gates, the super/ files and the kind file

> Contract: [README.md](README.md) 3.1, 3.2, 3.5, 3.11 (audit), 3.12, 3.13. Decisions D2, D8, D9.
> Mirrors `supervisor.policy` (the checks), `kinds.ensure` (the seed at start), `supervisor.append_log` (the log,
> except that values are masked before the line is dumped: README section 2, the masking trap).

**Files**
- Create: `console/superagent.py` (this task's part: head, constants, `settings`, `blocked`, `status`, the files)
- Create: `dotclaude/console/kinds/super.md`
- Modify: `console/kinds.py` (`NAMES` gains `"super"`), `console/paths.py` (`DEFAULTS`), `console/tuning.py` (`TUNING`,
  `SUPERVISOR_MODELS`, `WHOLE`)
- Modify: `console/__main__.py` (the import and one line; other chats edit this file: stage only this hunk,
  non-interactively, README rules)
- Create: `tests/test_superagent.py` (`SettingsTest`, `FilesTest`)
- Modify: `tests/test_kinds.py`, `tests/test_tuning.py`

Commit boundary: `feat: super agent settings, its files and its kind file (plan 58 T1)`.

## 1.1 `console/superagent.py`, part 1

```python
"""The super agent (plan 58; design/brainstorm/2026-11-08-super-agent.md, slice 1): one bounded, tool-free pass at a
time over every item that needs the user and every live task. Code rebuilds the digest for each pass; the pass reads it
with a notes file it rewrites and the user's standing orders, and answers with a rank, a batch or a later for each item
plus one recommendation line. It never acts in this slice. This module is pure functions and the files under
<home>/super/; the Hub owns the wakes, the pass thread and the spend (server.py). Reads never raise."""
import hashlib
import json
import math
import os
import re
import statistics
import time
from pathlib import Path
from string import Template

from . import compact, kinds, paths, redact, tasks
from .state import NEEDS_YOU

FOLDER = "super"
STATE_FILE, NOTES_FILE, ORDERS_FILE, LOG_FILE, PROMPT_FILE = (
    "state.json", "notes.md", "orders.md", "super.jsonl", "last-prompt.md")
OLD_LOG = "super.1.jsonl"
LOG_MAX = 5 * 1024 * 1024  # bytes: super.jsonl then moves to super.1.jsonl, replacing the older copy (D8)
MODEL_ALIASES = {"super_model": "haiku", "super_judge_model": "sonnet"}  # fixed, like supervisor.MODEL_ALIASES
_INT = {"super_debounce_s": (0, 300), "super_sweep_s": (300, 3600), "super_timeout_s": (10, 600),
        "super_notes_lines": (0, 200)}  # key -> (low, high) inclusive; a bool is never a count
_USD = {"super_pass_usd": (0, 1), "super_day_usd": (0, 20)}  # finite numbers; 0 turns the passes off
MAX_WAIT_S = 120  # a wake that new events keep pushing still runs this long after its first event
LATER_MAX_S = 86400  # a later's until is at most a day ahead
LINE_MAX = 200  # characters of one notes, orders, digest or task line
NOTES_MAX = 4000  # characters of notes.md after its line cut
ORDERS_MAX = 4000  # characters of the orders a pass reads
ORDERS_SEED = ("# Standing orders for the super agent (plan 58). One order per line, in your own words.\n"
               "# Lines that start with # are not sent to the super agent.\n")


def settings(cfg: dict) -> tuple:
    """(settings, errors): the super agent's numbers from config, checked like supervisor.policy (README 3.2). A bool,
    a wrong type or an out-of-range value takes the floor (0.0 for money) and adds its error; a model other than its
    alias is forced to the alias and adds its error. Any error keeps every pass from starting."""
    out, errors = {}, []
    for key, (low, high) in _INT.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            errors.append(f"{key} must be a whole number between {low} and {high}")
            value = low
        out[key] = value
    for key, (low, high) in _USD.items():
        value = cfg.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not low <= value <= high:
            errors.append(f"{key} must be a number between {low} and {high}")
            value = 0.0
        out[key] = float(value)
    for key, want in MODEL_ALIASES.items():
        if cfg.get(key) != want:
            errors.append(f"{key} must be {want}")
        out[key] = want
    return out, errors


def blocked(limits: dict, errors: list, state: dict, exe: bool) -> str:
    """Why no pass may start now ("" when one may), the first that holds: a settings error, off (a zero limit),
    Pause, no claude.exe (README 3.7)."""
    if errors:
        return "settings: " + errors[0]
    if limits["super_day_usd"] <= 0 or limits["super_pass_usd"] <= 0:
        return "off: super_day_usd or super_pass_usd is 0"
    if state.get("paused"):
        return "paused"
    if not exe:
        return "claude.exe not found"
    return ""


def status(limits: dict, errors: list, state: dict, spent: float, exe: bool) -> tuple:
    """(ranked, why) for the queue (README 3.8): blocked(), then over the day limit (`spent` is today's settled plus
    held spend), then no pass yet, then the last pass's error; (True, "") when the last ok pass's annotations hold."""
    why = blocked(limits, errors, state, exe)
    if why:
        return False, why
    if spent >= limits["super_day_usd"]:
        return False, f"over the day limit (${limits['super_day_usd']:.2f})"
    last = state.get("last")
    if not isinstance(last, dict):
        return False, "no pass yet"
    if not last.get("ok"):
        return False, str(last.get("error") or "the last pass failed")
    return True, ""


# -- the super/ files (Task 1) ------------------------------------------------------------------------------

def folder(home) -> Path:
    return Path(home) / FOLDER


def ensure(home) -> bool:
    """The service start: write orders.md with its two comment lines when it is missing; an existing file is never
    touched. True when written; a write error is skipped (a pass then reads no orders)."""
    path = folder(home) / ORDERS_FILE
    if path.exists():
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        paths.write_text_atomic(path, ORDERS_SEED)
    except OSError:
        return False
    return True


def blank_state() -> dict:
    """state.json's shape (README 3.5)."""
    return {"v": 1, "n": 0, "paused": False, "seen": {}, "ann": {}, "last": None, "digest": [], "claimed": None}


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_state(home) -> dict:
    """state.json with every key of blank_state() and only well-typed values; a missing, unreadable or malformed file,
    or a malformed part of one, reads as blank (it orders the queue and holds Pause, nothing else)."""
    state = blank_state()
    try:
        data = json.loads((folder(home) / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state
    if not isinstance(data, dict):
        return state
    if isinstance(data.get("n"), int) and not isinstance(data["n"], bool) and data["n"] >= 0:
        state["n"] = data["n"]
    if isinstance(data.get("paused"), bool):
        state["paused"] = data["paused"]
    if isinstance(data.get("seen"), dict):
        state["seen"] = {k: float(v) for k, v in data["seen"].items() if isinstance(k, str) and _num(v)}
    if isinstance(data.get("ann"), dict):
        state["ann"] = {k: v for k, v in data["ann"].items() if isinstance(k, str) and isinstance(v, dict)}
    for key in ("last", "claimed"):
        if isinstance(data.get(key), dict):
            state[key] = data[key]
    if isinstance(data.get("digest"), list):
        state["digest"] = [x for x in data["digest"] if isinstance(x, str)][:3]
    return state


def save_state(home, state: dict) -> None:
    """Whole-file replacement through paths.write_text_atomic (plan 54). Raises OSError: the Hub logs it."""
    path = folder(home) / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.write_text_atomic(path, json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n")


def read_notes(home) -> str:
    """notes.md as the last pass left it; "" when missing or unreadable."""
    try:
        return (folder(home) / NOTES_FILE).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def cut_notes(text, lines: int) -> str:
    """A pass's notes as notes.md keeps them: masked, blank lines dropped, at most `lines` lines of at most LINE_MAX
    characters, at most NOTES_MAX characters in all, ending with a newline; "" for no notes or `lines` 0."""
    if lines <= 0 or not isinstance(text, str):
        return ""
    kept = [line.rstrip()[:LINE_MAX] for line in redact.mask(text).replace("\r\n", "\n").split("\n") if line.strip()]
    out = "\n".join(kept[:lines])[:NOTES_MAX].rstrip()
    return out + "\n" if out else ""


def save_notes(home, text: str) -> None:
    path = folder(home) / NOTES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.write_text_atomic(path, text)


def read_orders(home) -> str:
    """The standing orders as a pass reads them: orders.md without blank lines and lines starting with #, each line
    cut at LINE_MAX characters, masked, at most ORDERS_MAX characters; "" when there are none."""
    try:
        raw = (folder(home) / ORDERS_FILE).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    kept = [line.strip()[:LINE_MAX] for line in raw.replace("\r\n", "\n").split("\n")
            if line.strip() and not line.lstrip().startswith("#")]
    return redact.mask("\n".join(kept))[:ORDERS_MAX]


def save_prompt(home, prompt: str) -> None:
    """last-prompt.md: the exact stdin of the last pass, for the live check (its texts are masked already)."""
    path = folder(home) / PROMPT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.write_text_atomic(path, prompt)


def _masked(value):
    """Every string of a JSON-ready value masked, keys included. Masking the dumped line instead can swallow a
    closing quote (a value that ends in `token=abc`) and break the line (README section 2); this keeps every line
    valid JSON."""
    if isinstance(value, str):
        return redact.mask(value)
    if isinstance(value, dict):
        return {redact.mask(str(k)): _masked(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_masked(v) for v in value]
    return value


def append_log(home, record: dict) -> None:
    """One JSON line in super.jsonl, every string in it masked (`ts` first unless the record has one). At LOG_MAX
    bytes the file first moves to super.1.jsonl, replacing the older copy; a move that fails is tried again at the
    next line (D8). Raises OSError on the append: the Hub logs it."""
    path = folder(home) / LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.stat().st_size >= LOG_MAX:
            os.replace(path, path.with_name(OLD_LOG))
    except OSError:
        pass
    line = json.dumps(_masked({"ts": time.time(), **record}), ensure_ascii=False, default=str)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()


def read_log(home) -> list:
    """Every parseable object line of super.jsonl (super.1.jsonl is not read)."""
    try:
        text = (folder(home) / LOG_FILE).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out = []
    for line in text.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out
```

`hashlib`, `re`, `statistics`, `Template`, `compact`, `kinds`, `tasks` and `NEEDS_YOU` are used by Tasks 2 and 3;
import them now so later tasks only add code below.

## 1.2 `dotclaude/console/kinds/super.md`

The person is `$you` (plan 31); `$lines` is `super_notes_lines`. No `Fred`, no em-dash (`tests/test_kinds.py`).

```markdown
# super

You are the Claude Console's super agent. $You runs many tasks at once, across several projects, and cannot follow
them all. Before an item reaches $you, you sort it: what $you must see first, what can wait, what can be answered
together. You read only the digest below, which the service built from its saved state; you run nothing, read nothing
else and change nothing. Your answer only orders $you's queue: $you still answers every item.

For each item under "Items for", return one entry with its handle (I1, I2, ...) as key:
- forward, at a rank (1 is first), with say: one line that tells $you what you recommend and why, in plain words,
  for example "Accept: the verify passed and no question is open". When the digest does not show something, say so;
  never present a guess as a fact.
- batch: items of the same kind that $you can answer the same way in one go get the same batch name (lower case, for
  example accept-1), such as three finished tasks whose verify passed. Each keeps its own rank.
- later: an item that loses nothing by waiting, with why: what it waits for, and until (optional): the local time it
  should come back, written YYYY-MM-DDTHH:MM, at most a day ahead. For example a finished task to accept while
  another task waits on a decision.
An item marked always reaches $you whatever you answer: rank it and give it a say line, never batch it or put it
later.

Rank first what blocks the most work or costs money while it waits: a decision a running chain waits on, a stuck task,
a cap or a hold; then a finished task to accept; then an observed chat. A default that is about to be taken ranks
high. Follow $you's standing orders over your own judgment. When two items ask the same thing, say so in both say
lines.

digest: one to three short lines for $you about the whole picture, from facts the digest shows: what runs, what is
stuck, what a signal shows, what was spent. notes: your memory for the next pass, at most $lines lines: what you
decided and why, what you are watching. Rewrite the notes whole each time and drop what no longer matters.

Never answer a question meant for $you, never pick an option for $you, never name a model id, a tool, a file path
outside a project or a shell command. Your ranks and say lines are advice.
```

## 1.3 Config, whitelist, kinds, start

`console/paths.py`, in `DEFAULTS` after `"supervisor_day_usd": 2,`:

```python
    # plan 58: the super agent's own passes (design/brainstorm/2026-11-08-super-agent.md 3.7). Models are fixed
    # aliases; super_day_usd or super_pass_usd at 0 turns the passes off.
    "super_model": "haiku",
    "super_judge_model": "sonnet",  # a pass whose new items hold a stuck task
    "super_debounce_s": 20,
    "super_sweep_s": 900,
    "super_timeout_s": 120,
    "super_notes_lines": 40,
    "super_pass_usd": 0.20,
    "super_day_usd": 1.0,
```

`console/tuning.py`, in `TUNING` after `"supervisor_stuck_model"`:

```python
    # plan 58: the super agent's settings (no Models page card yet, D9; config.json by hand or this whitelist)
    "super_debounce_s": ("super", "s", 0, 300),
    "super_sweep_s": ("super", "s", 300, 3600),
    "super_timeout_s": ("super", "s", 10, 600),
    "super_notes_lines": ("super", "lines", 0, 200),
    "super_pass_usd": ("super", "usd", 0, 1),
    "super_day_usd": ("super", "usd", 0, 20),
    "super_model": ("super", "rung", None, None),
    "super_judge_model": ("super", "rung", None, None),
```

and `SUPERVISOR_MODELS = {"supervisor_model": "haiku", "supervisor_stuck_model": "sonnet", "super_model": "haiku",
"super_judge_model": "sonnet"}  # never opus/fable/external`, and `WHOLE` gains `"lines"`. Update the unit comment
above `TUNING` to name `lines` among the whole-number units. `KEYS` needs no edit (it is built from `TUNING`).

`console/kinds.py`: `NAMES` ends `"prep", "supervisor", "planner", "super")`, and its comment names plan 58's pass.

`console/__main__.py`: `superagent` joins the `from . import ...` line (alphabetical: `..., server, superagent,
tasks`), and on the line after `kinds.ensure(paths.home())`:
`    superagent.ensure(paths.home())  # plan 58: super/orders.md, seeded once, then Fred's to edit`.

## 1.4 Tests first (red before the code)

`tests/test_superagent.py` (module docstring: plan 58, the pure parts; scratch homes from `tempfile.mkdtemp`, never
`~/.claude`; `T0 = 1_800_000_000.0`).

`SettingsTest`
- `test_defaults_pass`: `superagent.settings(paths.DEFAULTS)` is `({"super_debounce_s": 20, "super_sweep_s": 900,
  "super_timeout_s": 120, "super_notes_lines": 40, "super_pass_usd": 0.2, "super_day_usd": 1.0, "super_model":
  "haiku", "super_judge_model": "sonnet"}, [])`.
- `test_bad_values_fail_closed`: subTests over `super_debounce_s` = `"20"`, `True`, `-1`, `301`, `20.5`;
  `super_sweep_s` = 299; `super_timeout_s` = 9; `super_notes_lines` = 201; `super_pass_usd` = `-0.1`, `1.5`,
  `float("inf")`, `float("nan")`, `"0.2"`, `True`; `super_day_usd` = 21; each yields one error naming the key, and the
  value is the floor (`super_debounce_s` 0, money 0.0). Exact text once: `super_sweep_s` 299 gives `"super_sweep_s
  must be a whole number between 300 and 3600"`. `super_model` `"opus"` gives `"super_model must be haiku"` and the
  value `"haiku"`; a missing key is an error too.
- `test_blocked_and_status_order`: with `limits, _ = settings(DEFAULTS)`: errors `["x"]` gives `"settings: x"` before
  anything else; `super_day_usd` 0 and, apart, `super_pass_usd` 0 give `"off: super_day_usd or super_pass_usd is 0"`;
  paused gives `"paused"`; `exe=False` gives `"claude.exe not found"`; `status` with spent 1.0 gives `(False, "over
  the day limit ($1.00)")`, with no `last` `(False, "no pass yet")`, with `last` `{"ok": False, "error": "the pass
  failed: error_max_turns"}` that error, with `last` ok `(True, "")`.

`FilesTest`
- `test_ensure_seeds_orders_once`: `ensure(home)` is True and the file equals `ORDERS_SEED`; `read_orders(home)` is
  `""`; after Fred's edit, `ensure` is False and the edit stays; a home whose `super` is a file returns False without
  raising.
- `test_state_round_trip_and_bad_files`: `save_state` then `load_state` gives the saved dict; missing, `{`, `[]` and a
  directory named `state.json` each give `blank_state()`; `{"n": "3", "paused": "yes", "seen": {"k": "x", "j": 2},
  "ann": {"k": 1, "j": {}}, "digest": ["a", 2, "b", "c", "d"], "last": 5}` loads as `n` 0, `paused` False, `seen`
  `{"j": 2.0}`, `ann` `{"j": {}}`, `digest` `["a", "b", "c"]`, `last` None.
- `test_saves_go_through_write_text_atomic`: with `paths.write_text_atomic` patched to record and write, `save_state`,
  `save_notes`, `save_prompt` and `ensure` each write their file through it (four calls, four paths under
  `<home>/super/`).
- `test_cut_notes`: 50 non-blank lines with `lines` 40 keep 40; blank lines are dropped before counting; a
  300-character line is cut to 200; with `lines` 40, 30 lines of 199 characters keep at most 4000 characters before
  the final newline; `sk-ant-1234567890` becomes `***`; `lines` 0, and a text of `None` or `5`, give `""`; any other
  result ends with exactly one newline.
- `test_orders_drop_comments_blanks_and_secrets`: `"# head\n\nnever raise chats before 18:00\n  # indented\ntoken=abc\n"`
  reads `"never raise chats before 18:00\ntoken=***"`; 30 order lines of 199 characters read as at most 4000
  characters.
- `test_log_is_masked_and_rotates`: two `append_log` calls, one carrying `sk-ant-1234567890`, then `read_log` has two
  records with `ts` and no secret; a record `{"phase": "result", "out": {"items": [{"say": "set token=abc"}]}}` (a
  secret that ends a string) reads back as one valid record whose say is `"set token=***"`; with
  `superagent.LOG_MAX` patched to 100, the next append moves the file to `super.1.jsonl` and `super.jsonl` holds one
  line; a later rotation replaces `super.1.jsonl`; a line that is not JSON is skipped by `read_log`.
- `test_imports_point_one_way`: the source of `console/superagent.py` imports neither `server` nor `supervisor`, and no
  module but `server.py` and `__main__.py` imports `superagent` (scan `console/*.py`).

`tests/test_kinds.py`, `test_one_seed_per_chain_kind_in_the_shape`: `NAMES` equals `tasks.KINDS + ("prep",
"supervisor", "planner", "super")`; `"super"` joins the tuple of kinds without a worker HANDOFF; `seed_text("super")`
starts `"# super\n"` and holds `$You`, `$you` and `$lines`.

`tests/test_tuning.py`: `test_whitelist_is_the_contracts` gains the eight `super_*` keys; a new
`test_super_keys_are_ranged_and_the_models_fixed`, through the file's `check(**changes)` helper (`validate(changes,
CFG)`): `check(super_model="sonnet")[1]` is `{"super_model": "haiku only"}`; `check(super_judge_model="sonnet")[1]` is
`{}`; `check(super_notes_lines=40.5)[1]` is `{"super_notes_lines": "a whole number between 0 and 200"}`;
`check(super_sweep_s=200)[1]` is `{"super_sweep_s": "between 300 and 3600"}`; `check(super_day_usd=0)` is
`({"super_day_usd": 0}, {})` (off); `tuning.view(CFG)["super_day_usd"]` has `group` `super` and `unit` `usd`.

## 1.5 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_superagent tests.test_kinds tests.test_tuning`: red for the
      missing module, the missing kind and the missing keys.
- [ ] 2. Create `console/superagent.py` (1.1) and `super.md` (1.2); make the edits of 1.3. Focused tests green.
- [ ] 3. Full suite green (report the count). Stage the new files and the edited modules by path, and only this
      task's lines of `console/__main__.py` (non-interactive staging, README rules). Commit with the message above.
