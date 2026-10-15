> Mirrored by Claude Console from its task folder tasks/20261015-152042-970e/03-design/ for history. Edit the console's copy: this file is rewritten.

# Part 1: Write plans/34-audit-fixes.md

## Files
- plans/34-audit-fixes.md (new)
## Actions
1. List `plans/`. If no `plans/34*` exists, the name is `plans/34-audit-fixes.md`. Otherwise take the lowest free number N of 34 or more, name the file `plans/N-audit-fixes.md`, and in the text below replace every `Plan 34`, `plan 34` and `34-audit-fixes` with N.
2. Create the file with the Write tool. Its content is exactly the text between the `~~~~` fences below (the fences are not part of it). Keep every line; add nothing.

~~~~
# Plan 34: Fixes from the codebase audit of 2026-10-15. Guided implementation plan

> Findings: section 1, from the audit task of 2026-10-15 (scout read, a full test run on Windows: 617 tests,
> 6 failures, and the design read). Master: [../PLAN.md](../PLAN.md). Rules: [../CLAUDE.md](../CLAUDE.md).
>
> Start state: master `17819fc` plus plan 33's changes (console/server.py, console/tasks.py, tests/test_server.py
> and others). Anchor by the quoted lines, never by line numbers; the line numbers below are those of the audit read.

Status: written 2026-10-15; no code changed. Not run in a scratch copy: each task writes its tests first, runs them and
sees them fail for the reason given, then makes the change, then runs the whole suite.

## 1. Findings

### Security
- F1 (bug) `cc_events.py:14-15`: `from console import paths, redact` sits outside any try. A console package that
  does not import (a half-saved edit, a syntax error) makes the hook exit 1 with a traceback in every session,
  against the CLAUDE.md rule "must never raise, must always exit 0".
- F2 (gap) `console/redact.py:5-15`: `mask` misses AWS keys (`AKIA`/`ASIA`), Google API keys (`AIza`), JWTs, PEM
  private key blocks and `Authorization: Basic`; `_ASSIGN` misses `passwd`, `authorization`, `cookie`, `credential`,
  `private_key`. The text reaches the event log through `cc_events.py:153` (prompt), `:173`, `:175` (reply), `:178`
  and `redact.summarize` (Bash, Grep, WebSearch), and the task files through `plan.py`, `prep.py` and `tasks.py`.
- F3 (gap) `cc_events.py:159`: the PermissionDenied `reason` is clipped but not masked; it can quote the command.

### Data safety
- F4 (risk) `console/runs.py:335` and `:376` with `console/claude_cli.py:175-197`: Stop on a run from an earlier
  service calls `kill_tree(meta["pid"])` (`taskkill /T /F`) when `pid_alive` is true, and `reconcile` keeps such a
  run open while its pid is alive. The service job kills every run when its service exits, so that pid is dead
  and may be reused: Stop can kill an unrelated process tree, and reconcile can leave the run unended forever.
- F5 (risk) `console/server.py:2084-2085` (`Handler._draft`): draft.txt is written in place from the HTTP threads;
  two saves or a crash mid-write leave half a draft, and an OSError (Windows, a reader holds the file) drops the
  connection with no answer.
- F6 (risk) `install_hooks.py:71`: settings.json is written in place after the backup; an interrupted write leaves
  Claude Code with a broken settings file (the backup exists, but Fred has to restore it by hand).

### Test reliability
- F7 (bug, tests) `tests/test_server.py:154` (`RunServerTest.setUp`) and `:2430` (`HarnessServerTest.setUp`) build
  cfg with `paths.load_config()` and no `CC_CONSOLE_HOME`. They read Fred's `~/.claude/console/config.json` and
  models.json, and the Hub rereads models.json from there before each route. The harness probe also finds the real
  codex and opencode through `shutil.which`. This causes five of the six failures:
  `test_config_lists_harnesses` (opencode on in Fred's config), `test_harness_switch` (opencode found on PATH),
  `test_probe_never_raises` (codex found on PATH), `test_run_refuses_off_or_unknown_rung` (cmd on in Fred's config,
  its model not in models.json), and `test_budget_hold_waits_for_fred` (Fred's think tier holds rungs with no share,
  so the note reads `balance: opus 90 %`). Worse, a test run can write to Fred's data folder.
- F8 (flaky test) `tests/test_server.py:2265` (`test_bulk_delete_takes_finished_tasks_only`): the fake run can end
  before the delete. The running task is then refused with `task is running` (`Hub.task_levers` `clear`) instead
  of `still working: wait until it stops`. Both refusals are right; the test pins one.

### Checked, no change
- `server.py:1746`, `:1795` Host and X-CC on every route; `:1814` body caps; `:2275` binds 127.0.0.1.
- window.json: `paths.save_window` (`paths.py:324-333`) already writes through a temp file under `_WINDOW_LOCK`.
- `/api/chat` (`server.py:2095-2099`): `transcript.find` (`transcript.py:184-189`) refuses an id outside
  `[0-9a-f-]{8,64}` before its glob.
- `runs.open_terminal` (`runs.py:394`): its cwd comes from the run's meta, which only this service writes, for a run
  it started in a listed project.
- `redact.clip`'s U+2026: a character in data, not prose.
- `attach.py:110-112`, `tasks.safe_id` (`tasks.py:70-71`), `server.py:2041`, `:2186`, `cc_events.py:96-130`, `:205-213`.

### Already planned elsewhere
- `claude_cli.kill_tree` calls taskkill on every OS: plan 27 Task 6 (kill by process group on POSIX), after plan 5's
  live check.

### Not audited in this pass
- console/state.py, replan.py, prep.py, review.py, compact.py, tuning.py, levers.py, kinds.py, usage.py, plan.py,
  routing.py, fills.py, brief.py, facts.py, events.py, harness/*.py (beyond `find_exe` and `which`), web/*, dotclaude/**.
  The scout's turn cap ran out. A second pass is a new task.

## 2. Tasks, in order

| # | Section | What it delivers | Findings | Tests added |
|---|---|---|---|---|
| 1 | Task 1 | the hook's import inside never-raise; the PermissionDenied reason masked | F1, F3 | 2 |
| 2 | Task 2 | more secret shapes and key names masked | F2 | 2 |
| 3 | Task 3 | `claude_cli.run_alive`: Stop and reconcile never act on a recycled pid | F4 | 4 |
| 4 | Task 4 | `paths.write_text_atomic` for draft.txt (500 on failure); settings.json through a temp file | F5, F6 | 3 |
| 5 | Task 5 | test_server isolated from this machine's data folder and PATH; the delete race accepted | F7, F8 | 0 (edits) |
| 6 | Task 6 | PLAN.md row and History when placed | | none |

Order: 1 to 5, one commit each, `plan 34 task N: <what> (<findings>) (<n> tests OK)`, then 6. The tasks touch
disjoint functions. Tasks 4 and 5 both edit tests/test_server.py, in different classes and methods.

## 3. Decisions

| # | Decision | Task |
|---|---|---|
| 1 | A failed console import makes `main` drain stdin and return 0; nothing is logged (there is nothing to log with) | 1 |
| 2 | `Authorization: Basic x` is masked through `_ASSIGN`'s value (scheme plus token), not a bare `basic` pattern (it would eat "a basic understanding") | 2 |
| 3 | `auth`, `pwd` are not key names (they hit `author:`, prose); `passwd`, `authorization`, `cookie`, `credential`, `private_key` are | 2 |
| 4 | A process created more than `PID_SLACK_S` (2.0 s) after `meta["started"]` is not the run; no `started`, or an unreadable creation time (POSIX), trusts `pid_alive` as today | 3 |
| 5 | One helper `paths.write_text_atomic`; install_hooks.py keeps its own three lines (it is a standalone stdlib script) | 4 |
| 6 | A draft write that fails answers 500 `draft not saved: <strerror>`; the old draft stays | 4 |
| 7 | test_server's data folder is `<tmp>/data` (created), not `self.folder`, so no test's view of `self.folder` changes | 5 |
| 8 | `shutil.which` returns None in HarnessServerTest; claude is probed through `runs.exe` (the fake), so it is unaffected | 5 |
| 9 | If one of the six failures remains after Task 5, stop and report it to Fred; change nothing more | 5 |

## Task 1: the hook never raises on import; the denied reason masked (F1, F3)

**Files**
- Modify: `tests/test_cc_events.py` (imports `shutil`, `subprocess`, `sys`; class `ImportFailureTest`;
  `BuildRecordTest.test_permission_denied_reason_is_masked`)
- Modify: `cc_events.py` (the import lines, `build_record`'s PermissionDenied line, `main`)

**1.1 Tests first.** Add `import shutil`, `import subprocess` and `import sys` to the imports in alphabetical order.
In `BuildRecordTest`, after `test_permission_denied_keeps_reason`:

```python
    def test_permission_denied_reason_is_masked(self):
        """Plan 34 F3: the reason can quote the command."""
        rec = cc_events.build_record(self.base("PermissionDenied", tool_name="Bash", tool_input={"command": "x"},
                                               reason="denied: OPENAI_API_KEY=*** in command"))
        self.assertEqual(rec["reason"], "denied: OPENAI_API_KEY=*** in command")
```

Before `if __name__ == "__main__":`:

```python
class ImportFailureTest(unittest.TestCase):
    def test_a_broken_console_package_still_exits_0(self):
        """Plan 34 F1: the import of console sits inside the never-raise rule."""
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(Path(cc_events.__file__), Path(tmp) / "cc_events.py")
            (Path(tmp) / "console").mkdir()
            (Path(tmp) / "console" / "__init__.py").write_text("raise ImportError('broken on purpose')\n",
                                                                encoding="utf-8")
            payload = json.dumps({"hook_event_name": "SessionEnd", "session_id": "s9"}).encode()
            proc = subprocess.run([sys.executable, str(Path(tmp) / "cc_events.py")], input=payload,
                                  capture_output=True, timeout=30,
                                  env=dict(os.environ, CC_CONSOLE_HOME=str(Path(tmp) / "home")))
            self.assertEqual((proc.returncode, proc.stderr), (0, b""))
            self.assertFalse((Path(tmp) / "home").exists())
```

Run `py -m unittest tests.test_cc_events`: both fail (exit 1 with the ImportError traceback; the key unmasked).

**1.2 `cc_events.py`.** Replace the two lines

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
from console import paths, redact  # noqa: E402
```

with

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from console import paths, redact  # noqa: E402
except Exception:  # plan 34 F1: a broken console package must not break the session (never raise, exit 0)
    paths = redact = None
```

Replace `rec["reason"] = redact.clip(data.get("reason", ""), 120)` with
`rec["reason"] = redact.clip(redact.mask(data.get("reason", "")), 120)`.

Replace the first two lines of `main`:

```python
def main() -> int:
    try:
```

with

```python
def main() -> int:
    if paths is None or redact is None:  # plan 34 F1: the console package did not import; nothing to log with
        try:
            sys.stdin.buffer.read()  # take the payload so Claude Code's write never meets a closed pipe
        except Exception:
            pass
        return 0
    try:
```

**Done check:** `py -m unittest tests.test_cc_events` ends `OK`.

## Task 2: more secret shapes masked (F2)

**Files**
- Modify: `tests/test_redact.py` (two tests in `MaskTest`)
- Modify: `console/redact.py` (`_SECRETS`, `_ASSIGN`)

**2.1 Tests first.** In `MaskTest`, after `test_leaves_normal_text`:

```python
    def test_masks_cloud_keys_jwt_and_pem(self):
        """Plan 34 F2."""
        self.assertEqual(redact.mask("aws AKIAABCDEFGHIJKLMNOP x"), "aws *** x")
        self.assertEqual(redact.mask("g AIza" + "B" * 35 + " x"), "g *** x")
        self.assertEqual(redact.mask("t eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF123_-x end"), "t *** end")
        self.assertEqual(redact.mask("a\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----\nb"),
                         "a\n***\nb")
        self.assertEqual(redact.mask("cut -----BEGIN PRIVATE KEY-----\nMIIEow"), "cut ***")

    def test_masks_more_key_names(self):
        """Plan 34 F2: more names, and Basic auth through the value; prose stays."""
        self.assertEqual(redact.mask("Authorization: Basic dXNlcjpwYXNzd29yZA== next"), "Authorization:*** next")
        self.assertEqual(redact.mask("COOKIE=abc123"), "COOKIE=***")
        self.assertEqual(redact.mask("db_passwd: hunter2"), "db_passwd:***")
        self.assertEqual(redact.mask("private_key = 'xyz'"), "private_key=***")
        self.assertEqual(redact.mask("aws_credentials=abc"), "aws_credentials=***")
        self.assertEqual(redact.mask("a basic understanding"), "a basic understanding")
        self.assertEqual(redact.mask("the author: Fred"), "the author: Fred")
```

Run `py -m unittest tests.test_redact`: the two new tests fail.

**2.2 `console/redact.py`.** Replace `_SECRETS` and `_ASSIGN` whole (from `_SECRETS=*** to the `)` closing
`_ASSIGN`) with:

```python
_SECRETS=***
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)"),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
]
_ASSIGN = re.compile(  # plan 34 F2: more names; an auth scheme and its token are one value
    r"(?i)\b([A-Z0-9_]*(?:api[_-]?key|token|secret|password|passwd|authorization|cookie|credential|private[_-]?key)"
    r"[A-Z0-9_]*)\s*([=:])\s*"
    r"(\"[^\"]*\"|'[^']*'|(?:basic|bearer|digest)\s+\S+|\S+)"
)
```

**Done check:** `py -m unittest tests.test_redact` shows only the known Windows-path baseline failure on Linux, and
`OK` on Windows.

## Task 3: Stop and reconcile never act on a recycled pid (F4)

**Files**
- Modify: `tests/test_claude_cli.py` (two tests in `CommandTest`)
- Modify: `tests/test_runs.py` (two tests in `RunsTest`)
- Modify: `console/claude_cli.py` (new `PID_SLACK_S`, `process_started`, `run_alive` after `pid_alive`)
- Modify: `console/runs.py` (`RunManager.stop`, `RunManager.reconcile`: one condition each)

**3.1 Tests first.** In `CommandTest` of tests/test_claude_cli.py, after `test_pid_alive`:

```python
    def test_run_alive_refuses_a_recycled_pid(self):
        """Plan 34 F4: a process born after its run's start (plus the slack) holds a recycled pid."""
        with mock.patch.object(claude_cli, "pid_alive", return_value=True), \
                mock.patch.object(claude_cli, "process_started", return_value=100.0):
            self.assertTrue(claude_cli.run_alive(5, 99.0))
            self.assertFalse(claude_cli.run_alive(5, 50.0))
            self.assertTrue(claude_cli.run_alive(5, None))  # an old meta without "started"
        with mock.patch.object(claude_cli, "pid_alive", return_value=True), \
                mock.patch.object(claude_cli, "process_started", return_value=None):
            self.assertTrue(claude_cli.run_alive(5, 50.0))  # creation time unknown: pid_alive alone
        with mock.patch.object(claude_cli, "pid_alive", return_value=False):
            self.assertFalse(claude_cli.run_alive(5, 99.0))

    @unittest.skipUnless(os.name == "nt", "the creation time is read on Windows only")
    def test_process_started_reads_this_process(self):
        born = claude_cli.process_started(os.getpid())
        self.assertIsNotNone(born)
        self.assertLess(born, time.time())
        self.assertGreater(born, time.time() - 86400)
        self.assertIsNone(claude_cli.process_started(None))
```

In `RunsTest` of tests/test_runs.py, after `test_reconcile_ends_an_orphan_whose_turn_has_a_result`:

```python
    def test_stop_spares_a_recycled_pid(self):
        """Plan 34 F4: a meta left by an earlier service names a pid a newer process holds: Stop kills nothing."""
        self.mgr.runs.mkdir(parents=True)
        self.mgr._save_meta({"session_id": "old", "pid": 4, "cwd": str(self.project), "offset": 0,
                             "model": "sonnet", "effort": "low", "started": 1000.0, "ended": None})
        with mock.patch.object(runs.claude_cli, "pid_alive", return_value=True), \
                mock.patch.object(runs.claude_cli, "process_started", return_value=5000.0), \
                mock.patch.object(runs.claude_cli, "kill_tree") as kill:
            self.assertEqual(self.mgr.stop("old"), "not running")
            kill.assert_not_called()
        with mock.patch.object(runs.claude_cli, "pid_alive", return_value=True), \
                mock.patch.object(runs.claude_cli, "process_started", return_value=999.0), \
                mock.patch.object(runs.claude_cli, "kill_tree") as kill:
            self.assertEqual(self.mgr.stop("old"), "killed")
            kill.assert_called_once_with(4)

    def test_reconcile_ends_a_run_whose_pid_was_recycled(self):
        self.mgr.runs.mkdir(parents=True)
        self.mgr.stream_path("old").write_text('{"type":"cc_prompt","text":"x"}\n', encoding="utf-8")
        self.mgr._save_meta({"session_id": "old", "pid": 4, "cwd": str(self.project), "offset": 0,
                             "model": "sonnet", "effort": "low", "started": 1000.0, "ended": None})
        with mock.patch.object(runs.claude_cli, "pid_alive", return_value=True), \
                mock.patch.object(runs.claude_cli, "process_started", return_value=5000.0):
            self.assertEqual(self.mgr.reconcile(), 1)
        self.assertEqual(self.ended("old")[0]["interrupted"], True)
```

Run `py -m unittest tests.test_claude_cli tests.test_runs`: the four fail (no `run_alive` / `process_started`).

**3.2 `console/claude_cli.py`.** Insert between `pid_alive` and `def kill_tree(pid) -> None:`:

```python
PID_SLACK_S = 2.0  # plan 34 F4: a process born this long after its run's "started" holds a recycled pid


def process_started(pid):
    """When process <pid> was created (epoch seconds), or None when that cannot be read: gone, no access, or not
    Windows (plan 34 F4)."""
    if not pid or os.name != "nt":
        return None
    k = ctypes.windll.kernel32
    handle = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        times = [ctypes.c_ulonglong() for _ in range(4)]  # creation, exit, kernel, user: FILETIME, 100 ns since 1601
        if not k.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        return (times[0].value - 116444736000000000) / 1e7
    finally:
        k.CloseHandle(handle)


def run_alive(pid, started) -> bool:
    """pid_alive, and the process is the run that started at `started` (meta["started"], epoch seconds): a process
    created more than PID_SLACK_S after it holds a recycled pid. A meta without `started`, or a creation time that
    cannot be read, trusts pid_alive alone (plan 34 F4)."""
    if not pid_alive(pid):
        return False
    if not started:
        return True
    born = process_started(pid)
    return born is None or born <= float(started) + PID_SLACK_S
```

**3.3 `console/runs.py`.** In `stop`, replace
`if meta and not meta.get("ended") and claude_cli.pid_alive(meta.get("pid")):` with
`if meta and not meta.get("ended") and claude_cli.run_alive(meta.get("pid"), meta.get("started")):`.
In `reconcile`, replace
`if not any(is_result(d) for d in lines) and claude_cli.pid_alive(meta.get("pid")):` with
`if not any(is_result(d) for d in lines) and claude_cli.run_alive(meta.get("pid"), meta.get("started")):`.

**Done check:** `py -m unittest tests.test_claude_cli tests.test_runs` ends `OK`.

## Task 4: draft.txt and settings.json written through a temp file (F5, F6)

**Files**
- Modify: `tests/test_paths.py` (class `AtomicWriteTest`)
- Modify: `tests/test_server.py` (`RunServerTest.test_draft_write_failure_answers_500`)
- Modify: `tests/test_install_hooks.py` (imports; `InstallHooksTest.test_write_goes_through_a_temp_file`)
- Modify: `console/paths.py` (new `write_text_atomic` before `_WINDOW_LOCK = threading.Lock()`)
- Modify: `console/server.py` (`Handler._draft`: two lines)
- Modify: `install_hooks.py` (`import os`; the write in `main`)

**4.1 Tests first.** tests/test_paths.py: the imports must hold `os`, `tempfile`, `unittest`, `Path` and `mock`; add
any missing one in its alphabetical place. Before `if __name__ == "__main__":` (or at the end of the file if there is
none):

```python
class AtomicWriteTest(unittest.TestCase):
    def test_write_text_atomic_replaces_whole_and_cleans_up(self):
        """Plan 34 F5: the text lands whole; a failed replace keeps the old file and leaves no temp file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "draft.txt"
            paths.write_text_atomic(path, "one")
            self.assertEqual(path.read_text(encoding="utf-8"), "one")
            with mock.patch.object(paths.os, "replace", side_effect=PermissionError(13, "in use")):
                with self.assertRaises(PermissionError):
                    paths.write_text_atomic(path, "two")
            self.assertEqual(path.read_text(encoding="utf-8"), "one")
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["draft.txt"])
```

tests/test_server.py, in `RunServerTest`, after `tearDown`'s following helper methods, as the first test method of
the class (before its first `def test_`):

```python
    def test_draft_write_failure_answers_500(self):
        """Plan 34 F5: draft.txt goes through a temp file; a failed write answers with the reason, the old draft stays."""
        self.assertEqual(self.call("/api/draft", {"text": "hello"}), (200, {"ok": True}))
        self.assertEqual([p.name for p in self.folder.glob("draft.txt.*")], [])
        with mock.patch.object(server.paths, "write_text_atomic", side_effect=PermissionError(13, "in use")):
            self.assertEqual(self.call("/api/draft", {"text": "bye"}), (500, {"error": "draft not saved: in use"}))
        self.assertEqual((self.folder / "draft.txt").read_text(encoding="utf-8"), "hello")
```

tests/test_install_hooks.py: add `import io`, `import json`, `import tempfile`, `from pathlib import Path` and
`from unittest import mock` to the imports (stdlib group, alphabetical, before `import install_hooks`). In
`InstallHooksTest`, after `test_remove_takes_only_ours`:

```python
    def test_write_goes_through_a_temp_file(self):
        """Plan 34 F6: settings.json is replaced whole; a failed replace leaves it as it was and no temp file."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text('{"model": "opus"}\n', encoding="utf-8")
            with mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(install_hooks.main(["--write", "--settings", str(path), "--python", "py.exe"]), 0)
            written = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(written["model"], "opus")
            self.assertIn("Stop", written["hooks"])
            before = path.read_text(encoding="utf-8")
            with mock.patch.object(install_hooks.os, "replace", side_effect=PermissionError(13, "in use")), \
                    mock.patch("sys.stdout", io.StringIO()):
                with self.assertRaises(PermissionError):
                    install_hooks.main(["--remove", "--settings", str(path)])
            self.assertEqual(path.read_text(encoding="utf-8"), before)
            self.assertEqual([p.name for p in Path(tmp).glob("*.tmp")], [])
```

Run `py -m unittest tests.test_paths tests.test_install_hooks` and
`py -m unittest tests.test_server.RunServerTest.test_draft_write_failure_answers_500`: the three fail (no
`write_text_atomic`, no `install_hooks.os`).

**4.2 `console/paths.py`.** Insert before the line
`_WINDOW_LOCK = threading.Lock()  # the page (project) and the window (form, place) both save`:

```python
def write_text_atomic(path: Path, text: str) -> None:
    """Write <path> whole through a temp file of this write's own (pid and thread in its name), then os.replace: a
    reader never sees half a file and two writers never share a temp file (plan 34 F5). OSError propagates, with the
    temp file removed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


```

**4.3 `console/server.py`.** In `Handler._draft`, replace

```python
        self.hub.folder.mkdir(parents=True, exist_ok=True)
        (self.hub.folder / "draft.txt").write_text(text, encoding="utf-8")
```

with

```python
        try:
            paths.write_text_atomic(self.hub.folder / "draft.txt", text)
        except OSError as exc:  # plan 34 F5: os.replace on Windows while a reader holds the file
            return self._error(500, f"draft not saved: {exc.strerror or exc}")
```

**4.4 `install_hooks.py`.** Add `import os` after `import json`. Replace
`    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")` with:

```python
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")  # plan 34 F6: never half a settings.json
    try:
        tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
```

**Done check:** `py -m unittest tests.test_paths tests.test_install_hooks tests.test_server` shows only the six F7/F8
failures (Task 5 fixes them).

## Task 5: test_server isolated from this machine (F7, F8)

**Files**
- Modify: `tests/test_server.py` (`RunServerTest.setUp`, `HarnessServerTest.setUp`,
  `TaskServerTest.test_bulk_delete_takes_finished_tasks_only`)

These are test-only changes. The "test first" check is the six failures seen before the change and gone after it.

**5.1** Run `py -m unittest tests.test_server` and note the six failures of section 1 (F7 five, F8 one when the race
hits).

**5.2 `RunServerTest.setUp`.** After the line `        self.project.mkdir()` (the first one, in `RunServerTest`), insert:

```python
        data = Path(self.tmp.name) / "data"
        data.mkdir()
        home = mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": str(data)})
        home.start()  # plan 34 F7: config.json and models.json from the test, never from this machine
        self.addCleanup(home.stop)
```

**5.3 `HarnessServerTest.setUp`.** After the line `        self.folder.mkdir()`, insert:

```python
        data = Path(self.tmp.name) / "data"
        data.mkdir()
        for patcher in (mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": str(data)}),  # plan 34 F7: not this machine's
                        mock.patch("shutil.which", return_value=None)):  # config.json, models.json or PATH
            patcher.start()
            self.addCleanup(patcher.stop)
```

**5.4 `test_bulk_delete_takes_finished_tasks_only`.** Replace
`        self.assertEqual(data["refused"], {running: "still working: wait until it stops"})` with:

```python
        self.assertEqual(list(data["refused"]), [running])  # plan 34 F8: live, or its run ended before the chain moved
        self.assertIn(data["refused"][running], ("still working: wait until it stops", "task is running"))
```

**5.5** Run `py -m unittest tests.test_server`: `OK`. If any of the six still fails, stop and report its message to
Fred; change nothing more (decision 9).

**Done check:** `py -m unittest discover -s tests` ends `OK` on Windows; the count is 617 plus 11, or more if other
plans added tests since.

## Task 6: PLAN.md when placed

Change PLAN.md's row 34 state to `code done <date>` and append a History line:
`- <date> - Plan 34 Tasks 1-5 placed, tests first, one commit each (<before> -> <after> tests OK).` Then list any
departure from this file. Edit only these two lines: other chats edit PLAN.md in parallel.
~~~~

## Tests
- No test files: this part writes a document.
## Done check
`py -c "import pathlib;t=pathlib.Path('plans/34-audit-fixes.md').read_text(encoding='utf-8');print(t.count('\n## Task '), 'F8' in t, chr(8212) in t)"` prints `6 True False`.
