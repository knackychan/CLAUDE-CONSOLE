"""Facts under the brief (plan 23, brainstorm 5.1): what code knows about a finished step for free, never
compacted. The real Files touched come from git (the step's own lines: a snapshot of `git diff --numstat` and
the untracked files when the step starts and when it ends), the test result from the last test command the step
ran (its tool result in the run stream). Pure: claude_cli runs git, the service reads the stream."""
import re

from . import redact

TEST_CMD = re.compile(r"(?<![\w-])(?:unittest|pytest|py\.test|tox|nox|jest|vitest|mocha|rspec|phpunit|ctest"
                      r"|(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test|go\s+test|cargo\s+test|dotnet\s+test"
                      r"|mvn\b[^|;&]*\btest|gradlew?\b[^|;&]*\btest|make\s+test)(?![\w-])")
_FAILED = re.compile(r"^FAILED\b|^FAIL:|^ERROR:|\b\d+ failed\b|^Tests:.*\bfailed\b", re.M)
_FAIL_LINE = re.compile(r"^(?:FAIL|ERROR|FAILED)\b|^E\s+\S|\b\w*(?:Error|Exception)\b|\b\d+ failed\b|^Tests:.*failed")
_PASS_LINE = re.compile(r"^Ran \d+ tests?\b|^OK\b|\b\d+ passed\b|^Tests:")
_COUNT = (re.compile(r"^Ran (\d+) tests?\b", re.M), re.compile(r"\b(\d+) passed\b"),
          re.compile(r"^Tests:\s+(?:\d+ \w+, )*(\d+) passed", re.M))
FAIL_LINES = 20
DIFF_LINES = 30
SNAPSHOT_MAX = 500


def parse_numstat(text: str) -> dict:
    """`git diff --numstat` output -> {path: [plus, minus]}; a binary file (`-  -`) counts 0 and 0; a rename
    `old => new` (or `dir/{a => b}`) is filed under its new path."""
    out = {}
    for line in str(text or "").splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        plus, minus, path = parts
        if " => " in path:
            path = re.sub(r"\{[^{}]* => ([^{}]*)\}", r"\1", path) if "{" in path else path.split(" => ")[-1]
            path = path.replace("//", "/")
        out[path] = [int(plus) if plus.isdigit() else 0, int(minus) if minus.isdigit() else 0]
        if len(out) >= SNAPSHOT_MAX:
            break
    return out


def snapshot(numstat: str, untracked: dict) -> dict:
    """The tree against one commit: the numstat's files, then each untracked file as [its lines, 0]."""
    out = parse_numstat(numstat)
    for path, lines in (untracked or {}).items():
        if len(out) >= SNAPSHOT_MAX:
            break
        out.setdefault(path, [int(lines or 0), 0])
    return out


def delta(before: dict, after: dict) -> dict:
    """{path: [plus, minus]} of the files whose lines changed between two snapshots against the same commit: the
    step's own work, whether it committed it or not (an earlier step's uncommitted lines are in `before` already).
    A file whose count fell back (a revert) counts with 0 and 0."""
    out = {}
    for path in sorted(set(before or {}) | set(after or {})):
        b, a = (before or {}).get(path, [0, 0]), (after or {}).get(path, [0, 0])
        if list(a) != list(b):
            out[path] = [max(0, a[0] - b[0]), max(0, a[1] - b[1])]
    return out


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def last_test(lines: list):
    """The last test command a run stream shows (Claude stream-json: a Bash tool_use whose command TEST_CMD matches,
    and the tool_result with its id): {"command", "output", "error"}; None when the step ran none, or its result
    is not in the stream."""
    found, results = None, {}
    for d in lines or ():
        message = d.get("message") if isinstance(d, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if d.get("type") == "assistant" and block.get("type") == "tool_use" and block.get("name") == "Bash":
                command = str((block.get("input") or {}).get("command") or "")
                if TEST_CMD.search(command):
                    found = (block.get("id"), command)
            elif d.get("type") == "user" and block.get("type") == "tool_result":
                results[block.get("tool_use_id")] = (_result_text(block.get("content")), bool(block.get("is_error")))
    if not found or found[0] not in results:
        return None
    output, error = results[found[0]]
    return {"command": found[1], "output": output, "error": error}


def test_word(test) -> str:
    """The `tests` fact: "" (no test command), "23 OK" / "OK", or "FAIL <first failing line>"."""
    if not test:
        return ""
    out = test["output"]
    if test["error"] or _FAILED.search(out):
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        first = next((line for line in lines if _FAIL_LINE.search(line)), lines[-1] if lines else "exit code not 0")
        return "FAIL " + redact.clip(redact.mask(first), 150)
    for rx in _COUNT:
        m = rx.search(out)
        if m:
            return f"{m.group(1)} OK"
    return "OK"


def facts(changed: dict, test) -> dict:
    """s["facts"]: {"files", "plus", "minus", "tests"}."""
    return {"files": len(changed), "plus": sum(v[0] for v in changed.values()),
            "minus": sum(v[1] for v in changed.values()), "tests": test_word(test)}


_STAT_LINE = re.compile(r"^ (\S.*?) +\| \+\d+ -\d+$")


def files_in(text: str) -> list:
    """The paths of a facts text's diff stat lines: what Hub.start_brief passes compact.run_brief as `touched`."""
    return [m.group(1) for m in map(_STAT_LINE.match, str(text or "").splitlines()) if m]


NOT_READ = "Tests: not read (this CLI's stream carries no tool result the service reads)"


def text(start: str, end: str, changed: dict, test, git: bool = True, read_tests: bool = True) -> str:
    """steps/NN-<kind>.facts.md: the diff stat of the step's own lines, then its last test command and the lines that
    matter (the failing ones, or the summary). `read_tests` False: a harness whose stream last_test cannot read
    (plan 5's codex, opencode, cmd). Masked by tasks.write_facts."""
    if not git or not start:
        out = ["git: no repository here, or no start commit"]
    else:
        out = [f"git diff --stat {start[:7]}..{end[:7] if end and end != start else 'working tree'}"]
        width = max((len(p) for p in list(changed)[:DIFF_LINES]), default=0)
        out += [f" {p.ljust(width)} | +{v[0]} -{v[1]}" for p, v in list(changed.items())[:DIFF_LINES]]
        if len(changed) > DIFF_LINES:
            out.append(f" ... and {len(changed) - DIFF_LINES} more")
        f = facts(changed, None)
        out.append(f"{f['files']} files changed, +{f['plus']} -{f['minus']}" if changed else "no file changed")
    if test:
        word = test_word(test)
        out.append("Tests: " + redact.clip(test["command"], 160))
        rx = _FAIL_LINE if word.startswith("FAIL") else _PASS_LINE
        keep = [redact.clip(line.strip(), 200) for line in test["output"].splitlines() if rx.search(line.strip())]
        out += keep[:FAIL_LINES] or [word]
    else:
        out.append("Tests: none ran in this step" if read_tests else NOT_READ)
    return "\n".join(out)
