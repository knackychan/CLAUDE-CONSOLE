# Task 3: The facts under the brief

> Contract: [README.md](README.md) 3.4, 3.10. Decision D1 (the step's own lines). Depends on Task 1 (the facts file
> helpers in `tasks.py`, the fake's `TESTS-OK` / `TESTS-FAIL`). Run in the scratch copy: the code below is the final
> code. The service uses it in Task 5; nothing calls it before.

**Files**
- Create: `console/facts.py` (the whole file below)
- Modify: `console/claude_cli.py` (new `UNTRACKED_READ_MAX`, `git_snapshot`)
- Create: `tests/test_facts.py` (the whole file below)

## 3.1 `console/facts.py`

```python
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
```

D1 (a) is `snapshot` and `delta` (and `git_snapshot` below): with (b) the facts would come from
`git diff --numstat <start>..<end>` once, with no snapshot at the start.

- `TEST_CMD` names the test runners a command line may hold (unittest, pytest, tox, nox, jest, vitest, mocha, rspec,
  phpunit, ctest, `npm|pnpm|yarn|bun [run] test`, `go test`, `cargo test`, `dotnet test`, `mvn ... test`,
  `gradle[w] ... test`, `make test`); a word boundary on both sides, so `cat test_plan.py` and `ls tests` are not
  test commands.
- `last_test` reads Claude's stream-json only (an `assistant` line's `tool_use` named `Bash`, the `user` line's
  `tool_result` with its `tool_use_id`); a later test command wins; no result yet gives None.

## 3.2 `console/claude_cli.py`

```diff
diff --git a/console/claude_cli.py b/console/claude_cli.py
index 75a1165..8dcc220 100644
--- a/console/claude_cli.py
+++ b/console/claude_cli.py
@@ -227,6 +230,36 @@ def git_changed(cwd: str, commit: str):
     return len(names)
 
 
+UNTRACKED_READ_MAX = 1024 * 1024  # an untracked file larger than this counts 0 lines (plan 23 facts)
+
+
+def git_snapshot(cwd: str, commit: str):
+    """The tree against `commit` for the facts (plan 23): {path: [plus, minus]} from `git diff --numstat <commit>`,
+    plus each untracked file as [its lines, 0]; None when git cannot tell (not a repo, no commit). Read only: no git
+    object, index or file is written."""
+    from . import facts  # here, not at the top: facts is pure and imports redact only
+    if not commit:
+        return None
+    outs = []
+    for cmd in (["git", "diff", "--numstat", commit], ["git", "ls-files", "--others", "--exclude-standard"]):
+        try:
+            out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW,
+                                 encoding="utf-8", errors="replace")
+        except (OSError, subprocess.SubprocessError):
+            return None
+        if out.returncode != 0:
+            return None
+        outs.append(out.stdout)
+    untracked = {}
+    for name in outs[1].splitlines()[:facts.SNAPSHOT_MAX]:
+        path = Path(cwd) / name
+        try:
+            untracked[name] = path.read_bytes().count(b"\n") if path.stat().st_size <= UNTRACKED_READ_MAX else 0
+        except OSError:
+            untracked[name] = 0
+    return facts.snapshot(outs[0], untracked)
+
+
 def git_status(cwd: str) -> list:
     """`git status --short` lines of `cwd` ([] when it is not a repo or git is missing)."""
     try:
```

`git_snapshot` runs two read-only git commands with the 10 s timeout and `NO_WINDOW` of the module's other git
helpers, counts the lines of each untracked file of at most 1 MB (a larger one counts 0) and returns None when either
command fails (no repository, an unknown commit, no git). It never writes.

## 3.3 Tests

`tests/test_facts.py` (7 test methods), the whole file:

```python
"""Plan 23: the facts under the brief (console/facts.py): git numstat snapshots, the step's own lines, the last test."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from console import claude_cli, facts

OK_RUN = "....\n----------------------------------------------------------------------\nRan 23 tests in 0.412s\n\nOK"
FAIL_RUN = ("Exit code 1\n..F.\n======================================================================\n"
            "FAIL: test_add (tests.test_calc.CalcTest.test_add)\n-----\nTraceback (most recent call last):\n"
            "  File \"tests/test_calc.py\", line 6\nAssertionError: 3 != 4\n\nRan 4 tests in 0.010s\n\nFAILED (failures=1)")


def stream(command, output, error=False, other=()):
    """Claude stream-json lines: an assistant tool_use Bash and the user tool_result with its id."""
    lines = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{k}", "name": "Bash",
                                                            "input": {"command": c}}]}} for k, c in enumerate(other)]
    lines += [{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{k}", "content": "x"}]}}
              for k, _ in enumerate(other)]
    lines += [{"type": "assistant", "message": {"content": [
                  {"type": "text", "text": "running the tests"},
                  {"type": "tool_use", "id": "tt", "name": "Bash", "input": {"command": command}}]}},
              {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tt", "is_error": error,
                                                        "content": [{"type": "text", "text": output}]}]}}]
    return lines


class FactsTest(unittest.TestCase):
    def test_parse_numstat(self):
        text = "12\t3\tconsole/tasks.py\n-\t-\tassets/icon.png\n4\t0\tweb/{old.js => app.js}\n1\t1\ta.py => b.py\nbad line"
        self.assertEqual(facts.parse_numstat(text), {"console/tasks.py": [12, 3], "assets/icon.png": [0, 0],
                                                     "web/app.js": [4, 0], "b.py": [1, 1]})
        self.assertEqual(facts.parse_numstat(""), {})

    def test_snapshot_adds_untracked_files(self):
        snap = facts.snapshot("2\t1\tcalc.py\n", {"new.py": 30, "calc.py": 99})
        self.assertEqual(snap, {"calc.py": [2, 1], "new.py": [30, 0]})  # a tracked file keeps its numstat

    def test_delta_is_the_steps_own_lines(self):
        before = {"calc.py": [2, 1], "old.md": [5, 0]}  # an earlier step's uncommitted lines
        after = {"calc.py": [6, 2], "old.md": [5, 0], "new.py": [30, 0]}
        self.assertEqual(facts.delta(before, after), {"calc.py": [4, 1], "new.py": [30, 0]})
        self.assertEqual(facts.delta(after, after), {})
        self.assertEqual(facts.delta({"x.py": [3, 0]}, {}), {"x.py": [0, 0]})  # reverted: touched, no lines
        self.assertEqual(facts.facts({"calc.py": [4, 1], "new.py": [30, 0]}, None),
                         {"files": 2, "plus": 34, "minus": 1, "tests": ""})

    def test_last_test_reads_the_tool_result(self):
        lines = stream("py -m unittest discover -s tests", OK_RUN, other=["git status", "pytest -q"])
        test = facts.last_test(lines)
        self.assertEqual(test, {"command": "py -m unittest discover -s tests", "output": OK_RUN, "error": False})
        self.assertIsNone(facts.last_test(stream("git diff", "x")))  # not a test command
        self.assertIsNone(facts.last_test(stream("npm test", "x")[:1]))  # no result in the stream yet
        self.assertIsNone(facts.last_test([{"raw": "not json"}, {"type": "result"}]))
        for cmd in ("python -m pytest tests", "npm run test", "go test ./...", "cargo test", "make test",
                    "uv run pytest -x"):
            self.assertTrue(facts.TEST_CMD.search(cmd), cmd)
        for cmd in ("git status", "cat test_plan.py", "ls tests"):
            self.assertFalse(facts.TEST_CMD.search(cmd), cmd)

    def test_test_word(self):
        self.assertEqual(facts.test_word(None), "")
        self.assertEqual(facts.test_word({"command": "c", "output": OK_RUN, "error": False}), "23 OK")
        self.assertEqual(facts.test_word({"command": "c", "output": "== 7 passed in 0.5s ==", "error": False}), "7 OK")
        self.assertEqual(facts.test_word({"command": "c", "output": "all good", "error": False}), "OK")
        self.assertEqual(facts.test_word({"command": "c", "output": FAIL_RUN, "error": True}),
                         "FAIL FAIL: test_add (tests.test_calc.CalcTest.test_add)")
        self.assertEqual(facts.test_word({"command": "c", "output": "1 failed, 3 passed", "error": False}),
                         "FAIL 1 failed, 3 passed")
        self.assertEqual(facts.test_word({"command": "c", "output": "", "error": True}), "FAIL exit code not 0")

    def test_text(self):
        changed = {"console/tasks.py": [12, 3], "tests/test_tasks.py": [40, 0]}
        ok = facts.text("abc1234567", "def7654321", changed, {"command": "py -m unittest", "output": OK_RUN,
                                                              "error": False})
        self.assertEqual(ok.splitlines(), ["git diff --stat abc1234..def7654",
                                           " console/tasks.py    | +12 -3",
                                           " tests/test_tasks.py | +40 -0",
                                           "2 files changed, +52 -3",
                                           "Tests: py -m unittest",
                                           "Ran 23 tests in 0.412s", "OK"])
        self.assertEqual(facts.files_in(ok), ["console/tasks.py", "tests/test_tasks.py"])  # start_brief's touched
        failed = facts.text("abc1234567", "abc1234567", {}, {"command": "py -m unittest", "output": FAIL_RUN,
                                                             "error": True})
        self.assertEqual(failed.splitlines()[:3], ["git diff --stat abc1234..working tree", "no file changed",
                                                   "Tests: py -m unittest"])
        self.assertIn("FAIL: test_add (tests.test_calc.CalcTest.test_add)", failed)
        self.assertIn("AssertionError: 3 != 4", failed)
        self.assertNotIn("Traceback", failed)  # the failing lines only
        self.assertEqual(facts.text("", "", {}, None).splitlines(),
                         ["git: no repository here, or no start commit", "Tests: none ran in this step"])
        self.assertEqual(facts.text("", "", {}, None, git=False, read_tests=False).splitlines()[1], facts.NOT_READ)
        many = {f"f{k}.py": [1, 0] for k in range(35)}
        self.assertIn(" ... and 5 more", facts.text("a" * 40, "b" * 40, many, None))

    @unittest.skipUnless(subprocess.run(["git", "--version"], capture_output=True).returncode == 0, "no git")
    def test_git_snapshot_on_a_real_repo(self):
        with tempfile.TemporaryDirectory() as repo:
            run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, check=True)
            run("init", "-q")
            run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "start")
            (Path(repo) / "calc.py").write_text("a\nb\n", encoding="utf-8")
            run("add", "calc.py")
            run("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "calc")
            head = claude_cli.git_head(repo)
            before = claude_cli.git_snapshot(repo, head)
            self.assertEqual(before, {})
            (Path(repo) / "calc.py").write_text("a\nb\nc\n", encoding="utf-8")
            (Path(repo) / "new.py").write_text("x\ny\n", encoding="utf-8")
            after = claude_cli.git_snapshot(repo, head)
            self.assertEqual(after, {"calc.py": [1, 0], "new.py": [2, 0]})
            self.assertEqual(facts.delta(before, after), {"calc.py": [1, 0], "new.py": [2, 0]})
            self.assertEqual(claude_cli.git_status(repo), [" M calc.py", "?? new.py"])  # the index is untouched
            self.assertIsNone(claude_cli.git_snapshot(repo, ""))
            self.assertIsNone(claude_cli.git_snapshot(tempfile.gettempdir(), head))  # not this repo's commit


if __name__ == "__main__":
    unittest.main()
```

- `test_parse_numstat` (binary `-  -`, the two rename forms, a bad line), `test_snapshot_adds_untracked_files`,
  `test_delta_is_the_steps_own_lines` (an earlier step's lines stay out, a revert counts as 0 and 0, `facts.facts`),
  `test_last_test_reads_the_tool_result` (the later test command wins, a non-test command, no result yet, raw lines;
  `TEST_CMD` on nine commands), `test_test_word`, `test_text` (the head, padded lines, counts, failing lines without
  the traceback, no git, `NOT_READ`, ` ... and 5 more`, `files_in`), `test_git_snapshot_on_a_real_repo` (a temp repo;
  skipped without git; `git status` shows the index untouched; None for an empty commit and for a folder that is not
  that repo).

## 3.4 Steps

1. `tests/test_facts.py`. `py -m unittest tests.test_facts` fails (no module).
2. `console/facts.py`, `claude_cli.git_snapshot`.
3. The full suite: all OK (Linux scratch 347 = 340 + 7).
4. Commit: `Plan 23 Task 3: facts module (step's own git lines, last test command from the stream) (N tests OK)`.

**Drift guards**
- `facts.py` imports `redact` only and runs no process: `claude_cli` runs git, the service reads the stream.
- `claude_cli.git_snapshot` imports `facts` inside the function (facts must stay importable without claude_cli).
- No test touches the user's repository: the git test works in a `TemporaryDirectory`.
