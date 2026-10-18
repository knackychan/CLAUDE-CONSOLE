"""Kind files (plan 28): one readable role file per step kind, `<home>/kinds/<kind>.md`, seeded from the repo's
`dotclaude/console/kinds/` at the service start when missing, editable without a rebuild (the window's Kinds tab or a
text editor). The service inlines a step's kind file into its prompt in place of the code's per-kind text and copies
the rendered text into the step folder as role.md. The text is string.Template text with named slots: $you and $You
everywhere, $checked (verify), $failed, $model and $effort (fix), the design and replan slots (plan.design_slots,
replan.build_prompt) and Prep's ($You, $raw, $misses, $window, prep.build_prompt). Never raises on a read: a missing or empty file reads the seed."""
import os
import re
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "dotclaude" / "console" / "kinds"
NAMES = ("scout", "search", "draft", "proofread", "edit", "code", "document", "explain", "debug", "test", "design",
         "replan", "verify", "fix", "prep", "supervisor")  # tasks.KINDS in its order (a test asserts it), then
# Prep (plan 29) and the supervisor's own pass (plan 44): neither is a worker kind
KIND_MAX = 32 * 1024  # bytes of one kind file the window may save
_HEAD = re.compile(r"# ([a-z]+)\s*")


def folder(home) -> Path:
    return Path(home) / "kinds"


def seed_text(kind: str) -> str:
    """The repo's copy of the kind file, "" for an unknown kind or a missing file."""
    if kind not in NAMES:
        return ""
    try:
        return (SEED / f"{kind}.md").read_text(encoding="utf-8")
    except OSError:
        return ""


def ensure(home) -> list:
    """Copy every seed file that `<home>/kinds/` lacks (the service start); an edited file is never replaced.
    Returns the kinds written; a write that fails is skipped (text() reads the seed then)."""
    written = []
    for kind in NAMES:
        path = folder(home) / f"{kind}.md"
        text = seed_text(kind)
        if path.exists() or not text:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written.append(kind)
        except OSError:
            continue
    return written


def text(home, kind: str) -> str:
    """The kind file as the console runs it: `<home>/kinds/<kind>.md`, else the seed when that is missing, empty or
    unreadable."""
    if kind not in NAMES:
        return ""
    try:
        own = (folder(home) / f"{kind}.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        own = ""
    return own if own.strip() else seed_text(kind)


def check(kind: str, body) -> str:
    """"" when `body` may be saved as the kind file of `kind`, else the reason: a known kind, text of at most KIND_MAX
    bytes whose first line is `# <kind>`."""
    if kind not in NAMES:
        return f"unknown kind: {kind}"
    if not isinstance(body, str) or not body.strip():
        return "the file is empty"
    if len(body.encode("utf-8")) > KIND_MAX:
        return f"over {KIND_MAX // 1024} KB"
    m = _HEAD.fullmatch(body.lstrip().splitlines()[0])
    if not m or m.group(1) != kind:
        return f"the first line must be # {kind}"
    return ""


def save(home, kind: str, body: str) -> str:
    """Write the kind file through a temp file (ValueError with check's reason when it may not be saved). With
    `body` None the file goes back to the seed. Returns the text now in force."""
    body = seed_text(kind) if body is None else body.replace("\r\n", "\n")
    why = check(kind, body)
    if why:
        raise ValueError(why)
    path = folder(home) / f"{kind}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{kind}.md.tmp")
    tmp.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return text(home, kind)


def body_of(text_: str) -> str:
    """The kind file without its `# <kind>` head line: what a prompt inlines."""
    lines = str(text_ or "").strip().splitlines()
    if lines and _HEAD.fullmatch(lines[0]):
        lines = lines[1:]
    return "\n".join(lines).strip()
