# Plan 43: Codex is not sent a writing step it cannot write in, and a refused write fails the step

> Master: [../PLAN.md](../PLAN.md). Rules: [../CLAUDE.md](../CLAUDE.md). Extends plan 5 (the `error_shell_start`
> repair in README 3, `Hub.rung_ok` in 3.6) and plan 40 (a failed attempt retries on another provider).
> Start state: `6e54298` plus the uncommitted plan 41/42 work, branch `claude/brainstorm-task-actions`.
> Anchor by the quoted lines, never by line numbers.

Status: code done 2026-10-17 (Tasks 1-4; D1-D6 taken as proposed when Fred asked for the plan to be done). Task 5, the live
check, is Fred's. Deviation: the Task 3 test waits for step 1 to be `done`, not the task, because a `code` step adds a
verify step that the fake cannot pass.

## 1. What happened (2026-10-17)

Task `20261017-100629-a93e` step 03 and task `20261017-101332-2d28` steps 3-6 ran `code` on Codex in
`D:\MY DOCS\MY TOOLS\CONTENT MANAGER`. Every write was refused: Codex's `file_change` item ended `"status": "failed"`,
a Python write raised `PermissionError: [Errno 13]`, and the test suite reported 628 errors. The Console marked each
step `done` ("choose next step"), and in 2d28, Add next step on `auto` picked Codex four times in a row.

Reproduced with `codex sandbox -c sandbox_mode="workspace-write" -- <python.exe> probe.py`, plus Codex's own log
(`~/.codex/.sandbox/sandbox.<date>.log`). There were two causes, both outside the Console:

| Id | Cause | Evidence | Fred's fix (done 2026-10-17) |
|---|---|---|---|
| C1 | The project folder was owned by an orphan SID from an old Windows install, so Codex could not add its sandbox write ACE | `write ACE failed on D:\MY DOCS\MY TOOLS\CONTENT MANAGER: open ACL target for update (READ_CONTROL \| WRITE_DAC): Access is denied.` | admin `icacls "<dir>" /setowner "DEROK137\DEROK137"` (plain `DEROK137` names the PC) |
| C2 | `[windows] sandbox = "unelevated"`: Python 3.13+ `os.mkdir(path, 0o700)` (so `tempfile.mkdtemp`) sets an owner-only ACL that drops the sandbox SID | `0o777` mkdir + write OK, `0o700` mkdir + write `Permission denied` | `[windows] sandbox = "elevated"` in `~/.codex/config.toml`, approved once |

After both fixes the probe prints `OK`. 15 of Fred's top-level folders under `D:\MY DOCS\MY TOOLS` and
`D:\WORK\10 - AI` still have the old owner. A buyer who kept a data drive through a Windows reinstall hits C1. A
buyer still on the unelevated sandbox hits C2.

| Id | Where | Today | Change |
|---|---|---|---|
| F1 | `Hub.rung_ok` | Codex passes for any kind in any folder | a writing kind on Codex is refused with the exact fix when C1 or C2 holds (Task 2) |
| F2 | `codex.summary` | a turn whose writes all failed ends `success` | it ends `error_write_denied`; the step fails, in manual mode too (Task 1) |
| F3 | `tasks._retry_or_stuck` then `Hub.start_step` | the retry may balance onto Codex again | the retry skips the harness that could not write or start its shell (Task 3) |

## 2. Decisions (proposed; Fred to confirm)

- D1 The check covers Codex on Windows only, for kinds that write or run commands: tools `""` (the default set) or
  any of `Bash`, `Edit`, `Write` (`code`, `debug`, `edit`, `draft`, `proofread`, `document`, `test`, `verify`, `fix`,
  `replan`, chat). `scout`, `search`, `explain` and `design` keep Codex: reading worked in every failed task.
- D2 The check writes nothing and starts nothing. It reads the folder's owner (ctypes, `advapi32`) and
  `[windows] sandbox` from `$CODEX_HOME/config.toml` (default `~/.codex`) with `tomllib`. Anything it cannot read
  counts as allowed, so it never blocks on a guess.
- D3 The refusal names the fix, with the full account name built from `USERDOMAIN\USERNAME`:
  `codex: <dir> belongs to another Windows account, so its sandbox cannot write there; in an admin PowerShell:
  icacls "<dir>" /setowner "<DOMAIN>\<user>"` or `codex: its Windows sandbox is "unelevated", where Python temp
  folders fail; set [windows] sandbox = "elevated" in ~/.codex/config.toml and run codex once`.
- D4 A Codex turn whose last `file_change` failed, with no later completed one, ends `error_write_denied`. The step
  fails through the existing path (`cap_reason`, `_retry_or_stuck`), so a manual chain stops instead of going
  "choose next step". `error_write_denied` and `error_shell_start` add the harness to the step's `avoid` list, which
  the retry's routing refuses.
- D5 No general "done with no file changed" flag: a step that finds its work already done is fine (a93e step 4).
- D6 The Console never fixes C1 or C2 itself: both need admin rights or another CLI's config (CLAUDE.md rules).

## 3. Tasks, in order

Each task: tests first, see them fail, place the code, `py -m unittest discover -s tests`, commit
`plan 43 task N: <what> (<n> tests OK)`.

### Task 1: a refused write ends the turn `error_write_denied` (`console/harness/codex.py`, `console/tasks.py`)

In `codex.summary`, next to `shell_failed`:

```python
    shell_failed = False
    write_failed = False
```

In its `item.completed` branch, after the `command_execution` block:

```python
            if item.get("type") == "file_change":
                write_failed = item.get("status") == "failed"
```

In the `turn.started` branch, next to `shell_failed = False`, add `write_failed = False`. Replace the end check:

```python
    if subtype == "success" and shell_failed:
        subtype = "error_shell_start"
    elif subtype == "success" and write_failed:
        subtype = "error_write_denied"
```

In `codex.chat`, replace `status = "error" if summary(turn_lines)["subtype"] == "error_shell_start" else "success"`
with:

```python
            status = "error" if summary(turn_lines)["subtype"] in ("error_shell_start", "error_write_denied") else "success"
```

In `tasks.cap_reason`, after the `error_shell_start` branch:

```python
    if subtype == "error_write_denied":
        return "Codex could not write a file (its sandbox refused it or the patch failed); the retry runs on another harness"
```

`tests/fake_codex.py`: in `main`, before the `agent_message` line:

```python
    if "DENIED" in prompt:
        out({"type": "item.completed", "item": {"type": "file_change", "status": "failed",
                                                "changes": [{"path": "PLAN.md", "kind": "update"}]}})
```

and add `DENIED (a failed file_change)` to its docstring's word list.

Tests: `tests/test_harness.py` (+1, after `test_shell_start_failure_is_not_success`):

```python
    def test_failed_file_change_is_write_denied(self):
        failed = {"type": "item.completed", "item": {"type": "file_change", "status": "failed",
                  "changes": [{"path": "D:/p/PLAN.md", "kind": "update"}]}}
        done = {"type": "turn.completed"}
        self.assertEqual(codex.summary([failed, done])["subtype"], "error_write_denied")
        self.assertEqual(codex.chat([failed, done], "/w")[-1]["text"], "error · 1 turns")
        wrote = {"type": "item.completed", "item": {"type": "file_change", "status": "completed", "changes": []}}
        self.assertEqual(codex.summary([failed, wrote, done])["subtype"], "success")
        self.assertEqual(codex.summary([failed, done, {"type": "turn.started"}, done])["subtype"], "success")
```

`tests/test_tasks.py` (+1, after `test_shell_start_failure_does_not_advance`):

```python
    def test_write_denied_does_not_advance(self):
        task = make(("code",))
        run(task, 1)
        why = tasks.cap_reason("error_write_denied", None)
        self.assertIn("could not write a file", why)
        action, _ = end(task, ok=False, cap=why)
        self.assertEqual((action, task["current"], task["last_good"]), ("retry", 1, 0))
```

### Task 2: the write check (`console/harness/codex.py`, `console/server.py`)

`console/harness/codex.py`: add `import ctypes`, `import tomllib` and `from ctypes import wintypes` to the imports,
`WINDOWS = os.name == "nt"` under `CHAT_TEXT`, and after `env()`:

```python
def write_block(cwd: str) -> str:
    """Plan 43: why Codex's Windows sandbox cannot write in `cwd`, else "". Reads only: the sandbox mode in
    config.toml and the folder's owner; anything unreadable counts as fine (D2)."""
    if not WINDOWS or not cwd:
        return ""
    if _sandbox_mode() == "unelevated":
        return ('codex: its Windows sandbox is "unelevated", where Python temp folders fail; set '
                '[windows] sandbox = "elevated" in ~/.codex/config.toml and run codex once')
    if not _owned_by_me(cwd):
        who = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
        return (f"codex: {cwd} belongs to another Windows account, so its sandbox cannot write there; "
                f'in an admin PowerShell: icacls "{cwd}" /setowner "{who}"')
    return ""


def _sandbox_mode() -> str:
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    try:
        with open(os.path.join(home, "config.toml"), "rb") as f:
            win = tomllib.load(f).get("windows")
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    return str(win.get("sandbox", "")) if isinstance(win, dict) else ""


def _owned_by_me(path: str) -> bool:
    """True when this process's user owns `path`; True too when Windows cannot tell (no false alarm)."""
    advapi, kernel = ctypes.WinDLL("advapi32"), ctypes.WinDLL("kernel32")
    advapi.GetNamedSecurityInfoW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD,
                                            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                          ctypes.POINTER(wintypes.DWORD)]
    advapi.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    owner, sd = ctypes.c_void_p(), ctypes.c_void_p()
    if advapi.GetNamedSecurityInfoW(path, 1, 1, ctypes.byref(owner), None, None, None, ctypes.byref(sd)):
        return True  # SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION
    token = wintypes.HANDLE()
    try:
        if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
            return True
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))  # TokenUser
        buf = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, buf, size, ctypes.byref(size)):
            return True
        return bool(advapi.EqualSid(owner, ctypes.c_void_p.from_buffer(buf).value))  # TOKEN_USER.User.Sid
    finally:
        if token:
            kernel.CloseHandle(token)
        kernel.LocalFree(sd)
```

(`_owned_by_me` was run on 2026-10-17 against CONTENT MANAGER and CLAUDE CONSOLE (True), `D:\WORK\10 - AI\AI TOOLS`
and `D:\MY DOCS\MY TOOLS\BLENDER` (False), and a missing path (True).)

`console/server.py`, `Hub.rung_ok`: the signature becomes `def rung_ok(self, rung, kind: str = "", cwd: str = "") -> str:`
and the docstring gains `; cwd: the step's folder, for the harness's write check (plan 43)`. Before the final `return ""`:

```python
        tools = (tasks.RULES.get(kind) or ("", "", ""))[2]
        block = getattr(harness.get(name), "write_block", None) if name != "claude" else None
        if block and kind and cwd and (not tools or {"Bash", "Edit", "Write"} & set(tools.split(","))):
            why = block(cwd)
            if why:
                return why
```

Pass the folder at every call that has a task or card (each anchored by its current text):
- `_route_for`: `refuse=lambda rung: self.rung_ok(rung, s["kind"])` becomes
  `refuse=lambda rung: self.rung_ok(rung, s["kind"], task["project_dir"]) or self._avoided(rung, s)` (`_avoided`
  is placed in Task 3).
- `_next_route`: `refuse=self.rung_ok` becomes `refuse=lambda r: self.rung_ok(r, kind, task["project_dir"])`.
  `self.rung_ok(requested, kind)` (twice) and `refuse=lambda r: self.rung_ok(r, kind)` gain `task["project_dir"]`.
- `next_model_options`: the three `self.rung_ok(rung, kind)` / `self.rung_ok(row["rung"], kind)` gain
  `task["project_dir"]`.
- `start_step`: both `self.rung_ok(route["rung"], s["kind"])` gain `task["project_dir"]`.
- The task-create handler: `self.hub.rung_ok(item["model"], str(item.get("kind") or ""))` gains
  `card.get("project_dir") or ""`.

Tests: `tests/test_harness.py` (+2):

```python
    def test_write_block_reads_the_sandbox_mode_and_the_owner(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home, "config.toml")
            with mock.patch.dict(os.environ, {"CODEX_HOME": home, "USERDOMAIN": "PC", "USERNAME": "fred"}), \
                    mock.patch.object(codex, "WINDOWS", True):
                with mock.patch.object(codex, "_owned_by_me", return_value=True):
                    self.assertEqual(codex.write_block(home), "")  # no config.toml
                    config.write_text('[windows]\nsandbox = "elevated"\n', encoding="utf-8")
                    self.assertEqual(codex.write_block(home), "")
                    config.write_text("not = [toml", encoding="utf-8")
                    self.assertEqual(codex.write_block(home), "")
                    config.write_text('[windows]\nsandbox = "unelevated"\n', encoding="utf-8")
                    self.assertIn('[windows] sandbox = "elevated"', codex.write_block(home))
                config.write_text('[windows]\nsandbox = "elevated"\n', encoding="utf-8")
                with mock.patch.object(codex, "_owned_by_me", return_value=False):
                    self.assertIn('icacls "D:/old" /setowner "PC\\fred"', codex.write_block("D:/old"))
            with mock.patch.object(codex, "WINDOWS", False):
                self.assertEqual(codex.write_block(home), "")

    @unittest.skipUnless(os.name == "nt", "the owner check is Windows only")
    def test_a_new_folder_is_owned_by_me(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(codex._owned_by_me(d))
        self.assertTrue(codex._owned_by_me(str(Path(d) / "gone")))
```

`tests/test_server.py`: in `HarnessServerTest.setUp`, the `mock.patch.dict(os.environ, {"CC_CONSOLE_HOME": str(data)})`
gains `"CODEX_HOME": str(data)` (no config.toml there, so a developer's own Codex config never decides a test). Add
`from console.harness import codex as codex_adapter` to the imports and (+1):

```python
    def test_codex_is_refused_for_writing_kinds_where_it_cannot_write(self):
        with mock.patch.object(codex_adapter, "write_block", return_value="codex: cannot write here"):
            self.assertEqual(self.hub.rung_ok("codex:gpt-6.1-sol", "code", str(self.project)), "codex: cannot write here")
            self.assertEqual(self.hub.rung_ok("codex:gpt-6.1-sol", "verify", str(self.project)), "codex: cannot write here")
            self.assertEqual(self.hub.rung_ok("codex:gpt-6.1-sol", "scout", str(self.project)), "")
            self.assertEqual(self.hub.rung_ok("codex:gpt-6.1-sol", "code"), "")
            self.assertEqual(self.hub.rung_ok("sonnet", "code", str(self.project)), "")
```

### Task 3: the retry skips the harness that failed (`console/server.py`)

In `Hub._ended`, after `subtype = "error_step_timeout" if meta.get("timed_out") else summary["subtype"]`:

```python
        if subtype in ("error_write_denied", "error_shell_start"):  # plan 43 (D4): the retry goes elsewhere
            cs["avoid"] = sorted(set(cs.get("avoid") or ()) | {claude_cli.split_rung(cs["model"])[0]})
```

New method next to `limited`:

```python
    def _avoided(self, rung: str, s: dict) -> str:
        """Plan 43: "" unless step `s` already failed to write or start its shell on this rung's harness."""
        name = claude_cli.split_rung(rung)[0]
        return f"{name}: could not write in this step; the retry uses another harness" if name in (s.get("avoid") or ()) else ""
```

In `start_step`, `refused = self.limited(manual["rung"]) if manual else ""` becomes:

```python
        refused = (self.limited(manual["rung"]) or self._avoided(manual["rung"], s)) if manual else ""
```

Tests: `tests/test_server.py` `HarnessServerTest` (+1):

```python
    def test_write_denied_codex_step_retries_on_another_harness(self):
        tid = self.make_task(steps=[{"kind": "code", "goal": "DENIED HANDOFF-OK", "model": "codex:gpt-6.1-sol"}])
        task = self.until(tid, lambda t: t["state"] == "done", "the retry completes")
        step = task["steps"][0]
        self.assertIn("could not write a file", step["attempts"][0]["why"])
        self.assertEqual(step["avoid"], ["codex"])
        self.assertEqual(step["harness"], "claude")
```

### Task 4: records

- PLAN.md: row 43 status `code done (<n> tests OK)`; one History line.
- `CLAUDE.md` is unchanged (no new rule: the check reads, D2).

### Task 5: live check (Fred)

1. Restart the service when no task runs.
2. In a task on `D:\WORK\10 - AI\AI TOOLS` (or any folder still owned by the old account): Add next step, kind `code`.
   The Model list shows the Codex rungs greyed out with the icacls line, and `auto` picks Claude or OpenCode.
3. The same task, kind `scout`: Codex is offered.
4. In CONTENT MANAGER, a `code` step on Codex edits a file and runs the tests (elevated sandbox, owner fixed).

## 4. Not in this plan

Running Codex's own `codex sandbox` probe from the Console (it writes in the project, and the two read-only checks
cover both known causes); fixing the owner or the Codex config from the Console (D6); a "no file changed" flag on
other harnesses (D5); an OpenCode or Command Code write check (their runs wrote fine: OpenCode ran the 560-test
suite in CONTENT MANAGER on 2026-10-17).
