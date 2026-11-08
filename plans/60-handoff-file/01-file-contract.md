# Task 1: The file contract and accepted note

Plan only. Depends on Fred accepting README D1a, D2-D4, D6-D7. Future files:
`console/tasks.py`, `tests/test_tasks.py`. Reuse `HEADINGS`, `check_handoff`, `note_text`, `folder`, `step_dir`,
`read_note`, `redact.mask` and `paths.write_text_atomic`. Do not relax `parse_handoff` or add required STEP_KEYS.

## 1. Final storage code

Add `stat` and `uuid` imports. The input path is generated internally, never taken from a model/HTTP payload.
Use a fresh generation on every launch, including a resumed turn; do not derive it from `retries` or the
length of `attempts` (manual retries are unbounded, and a resumed question is still one attempt).

```python
OUTPUT_DIR = re.compile(r"attempt-[0-9a-f]{32}")
SOURCE_READ_ONLY = frozenset({"scout", "search", "explain", "design", "test", "verify"})
FILE_KINDS = frozenset(RULES) - {"replan"}


def output_path(home, task: dict, step: dict, rel: str) -> Path:
    """Only this step's generated output; refuse linked directories and files."""
    root = (Path(home) / "tasks").resolve()
    base = folder(home, task["id"]).absolute()
    if base.is_symlink() or base.is_junction() or base.parent.resolve() != root:
        raise ValueError("task folder leaves the Console tasks directory")
    parts = str(rel).split("/")
    if (len(parts) != 3 or parts[0] != step_dir(step)
            or not _STEP_DIR.fullmatch(parts[0])
            or not OUTPUT_DIR.fullmatch(parts[1]) or parts[2] != "handoff.md"):
        raise ValueError("invalid handoff output path")
    path = base
    for part in parts:
        path = path / part
        if path.is_symlink() or path.is_junction():
            raise ValueError("handoff output must not be a link")
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError("handoff output leaves the task folder")
    return path


def prepare_output(home, task: dict, step: dict) -> str:
    """Reserve an absent output in a new directory. Caller saves the reservation before spawn."""
    rel = f"{step_dir(step)}/attempt-{uuid.uuid4().hex}/handoff.md"
    path = output_path(home, task, step, rel)
    path.parent.mkdir(parents=True, exist_ok=False)
    step["handoff_output"] = rel
    step["handoff_error"] = ""
    step.pop("handoff_sealed", None)
    return rel


def read_output(home, task: dict, step: dict, rel: str) -> tuple:
    """(masked six-heading body or None, error). Reads only; never publishes."""
    try:
        path = output_path(home, task, step, rel)
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                return None, "handoff.md must be a regular, unlinked file"
            raw = stream.read(NOTE_MAX + 1)
        if len(raw) > NOTE_MAX:
            return None, "handoff.md is over 20 KB"
        body = raw.decode("utf-8-sig").strip()
    except FileNotFoundError:
        return None, "handoff.md was not written for this turn"
    except UnicodeError:
        return None, "handoff.md is not UTF-8"
    except (OSError, ValueError) as exc:
        return None, "cannot read handoff.md: " + redact.clip(str(exc), 160)
    why = check_handoff(body)
    if why:
        return None, "handoff.md: " + why
    body = redact.mask(body)
    if len(body.encode("utf-8")) > NOTE_MAX:
        return None, "handoff.md is over 20 KB after masking"
    why = check_handoff(body)
    return (None, "handoff.md after masking: " + why) if why else (body, "")


def saved_handoff(home, task: dict, step: dict) -> tuple:
    text = read_note(home, task, step["n"])
    body = text.split("\n\n", 1)[-1] if text.startswith("# Step ") else text
    if not body.strip():
        return None, "no saved handoff"
    why = check_handoff(body, old_ok=step.get("handoff_source") != "file")
    return (None, why) if why else (body, "")


def step_handoff(home, task: dict, step: dict, reply: str, meta: dict) -> tuple:
    """Current-turn transport. Absence in BOTH records is the legacy contract."""
    rel = step.get("handoff_output")
    recorded = meta.get("handoff_output")
    if rel or recorded:
        if not rel or rel != recorded or meta.get("task") != task["id"]:
            return None, "handoff output does not match the current turn"
        return read_output(home, task, step, rel)
    block = parse_handoff(reply)
    if block is None:
        return None, missing_block(reply)
    why = check_handoff(block)
    return (None, why) if why else (block, "")
```

Task/step identity is already validated by the owning Hub operation. The root check rejects a linked task
directory below the resolved `<home>/tasks`. The Console home itself may be a user-selected resolved location. This is a local
artifact boundary, not protection against an adversarial process swapping filesystem objects during a read.
No new path API accepts arbitrary input filenames.

Replace `write_note`'s write, preserving its return value and assignment **after** the write succeeds:

```python
def write_note(home, task: dict, step: dict, block: str) -> str:
    rel = note_file(task, step)
    path = folder(home, task["id"]) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.write_text_atomic(path, note_text(task, step, block))
    step["handoff"] = rel
    return rel
```

For file candidates, read_output validates the masked body's UTF-8 length before publication. Redaction can
expand a short secret into a longer replacement. Reject over NOTE_MAX; `note_text` must not truncate an accepted
file candidate. Its masking must be idempotent on this body (assert in the future check). Legacy notes retain
their existing cap. Do not change `HEADINGS` or `_check_headings` semantics.

## 2. Failed output, history and Clear

Add the following final helper. Call only on a closed, no-longer-live turn, including failed or question turns;
never from GET. It makes a small masked diagnostic available on disk without accepting a failed note. The
accepted body has already been read into memory. A scrub error is retained in `handoff_error`; do not expose
the raw path in the Files tab. An oversized/non-UTF-8 output is replaced with a diagnostic, not accepted after
truncation. Do not reread a scrubbed diagnostic as a successful new result.

```python
def seal_output(home, task: dict, step: dict, rel: str) -> None:
    path = output_path(home, task, step, rel)
    try:
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("handoff.md must be a regular, unlinked file")
            raw = stream.read(NOTE_MAX + 1)
    except FileNotFoundError:
        return
    if len(raw) > NOTE_MAX:
        text = "Rejected output: over 20 KB. See the step's handoff error.\n"
    else:
        try:
            text = redact.mask(raw.decode("utf-8-sig"))
        except UnicodeError:
            text = "Rejected output: not UTF-8. See the step's handoff error.\n"
    paths.write_text_atomic(path, text)
```

Use the existing `notes.<k>.md` for a failed attempt's chat. Add the masked file rejection reason and generation
path to its header/body, without pretending the file was the assistant reply. A new field on the attempt,
`handoff_output`, points at the latest turn's output; do not cap generation names at 99 as notes names are capped.
`STEP_FILES`, `file_name_ok`, the HTTP file-open whitelist and old flat `steps/` layout need no new arbitrary
nested-path support: accepted `handoff.md` remains the normal visible file.

In `clear(keep_last=True)`, before the existing `if path.is_file()` clause, remove generated directories only:

```python
                if OUTPUT_DIR.fullmatch(path.name):
                    if path.is_symlink() or path.is_junction():
                        raise ValueError("refusing to clear a linked output directory")
                    if not path.resolve().is_relative_to(root.resolve()):
                        raise ValueError("output directory leaves the task folder")
                    if path.is_dir():
                        shutil.rmtree(path)
                    continue
```

Clear already runs only after live/recovery gates. Keep those gates. Task deletion/retention removes the whole
task as before. Do not recursively remove an inferred external path. On upgrade, there is no filesystem scan
or conversion; on restart only closed recorded generations needing sealing may be scrubbed.

## 3. Build-time checks, not run while planning

Add focused `tests/test_tasks.py` cases for prepare/read/select/publish, using a temporary CC_CONSOLE_HOME:

| Case | Assertion |
|---|---|
| Six headings; END token in normal prose | File validates; no markers needed; check_handoff remains the validator |
| Retry 2 with only turn 1's output | Missing current file, never old success |
| Continued question, same session | New UUID; old complete output cannot pass |
| Missing, empty, wrong order, empty Goal/Findings | Named failure, not fallback |
| 20 KiB boundary, multibyte UTF-8, BOM, malformed UTF-8 | Bounded byte check, BOM accepted, no accidental partial character |
| Redaction grows past cap or affects validation | Refuse; no accepted truncated/malformed note |
| Directory, link, junction, hardlink, traversal | Refuse and do not touch the external destination |
| Atomic publish raises | Previous canonical bytes and step.handoff unchanged |
| Legacy strict markers / saved four headings | Original behavior remains only on their intended read paths |
| Clear with two generations and last-good note | Removes generated directories, retains canonical/brief/facts; unrelated folders untouched |

Done check after implementation: `py -m unittest discover -s tests -p test_tasks.py` passes. No command in this
file is permission to run a real provider or to begin building before Fred reviews the plan.
