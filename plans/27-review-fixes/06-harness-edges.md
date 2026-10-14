# Task 6: harness edges (K10, K11, kill_tree on POSIX, plan 5 nits)

> Contract: the PR #1 review (2026-10-14) findings K10 and K11, its Task 6 bullet "kill_tree: os.killpg on POSIX",
> and its section 4 nits for plan 5 (`harnesses()["claude"]["models"]` not `{}`, the STOP footer for `/` prompts) and
> plan 18 (`cmd.py` counts cached tokens in input); plan 5 README decision 8 (Stop), 3.3 (`INTERRUPT`, `stop`), Task 5
> (`Hub.harnesses`). Depends on: Fred's plan 5 live check (`plans/05-harnesses/07-live-check-close.md`) done and its
> fixtures pinned (review Q2 (a)); nothing of Tasks 1 to 5 of plan 27. Decisions: three, marked `Decision:` in 6.3,
> 6.4 and 6.6.
> Run in a scratch copy on 2026-10-14: the whole suite 531 tests (525 before, six added), only the 4 Linux baseline
> failures (test_tray import, test_redact Windows path, test_usage local day, test_window placement);
> `tests.test_runs` 25 OK (22 before), `tests.test_claude_cli` 18 OK, 2 skipped (16 before), `tests.test_harness`
> 28 OK (27 before), `tests.test_server.HarnessServerTest` OK (one assertion added).
> Lands on: plan 5 Tasks 2 to 5 (`codex.run_command`, `cmd.run_command`, `cmd.summary`, `RunManager.start`,
> `_spawn`, `_watch`, `Hub.harnesses`), plan 5 Task 1 (`claude.run_command`), plan 1 (`claude_cli.kill_tree`). Tasks
> 1 to 5 of plan 27 touch none of these functions (Task 1 changes other `Hub` methods and `Handler` routes of
> `server.py`; only the `"models"` entry of `Hub.harnesses` changes here).

## Before you start: what the live check must have shown

The code below is written for the expected answer to each question. Read plan 5 Task 7's History (and the three
fixtures under `tests/fixtures/`) first. Where an answer differs, change exactly the lines named, then run the
tests of this task again.

1. **Does `opencode run --standalone` exit after its final event?** (live check item 5.) Expected: unknown, which is
   why K10 exists; the code handles both. If it exits by itself within a second or two: nothing changes (the grace
   in 6.2 never fires for OpenCode). If it stays up: nothing changes either, the grace stops it after
   `RESULT_GRACE_S`. Two things change only if the observation says so: (a) if the fixture's last event is not
   matched by `opencode.is_result` (its `type` is not in `RESULT_TYPES` and does not end in `.idle`), plan 5 Task 7
   corrects `is_result` first; without that the grace has nothing to start from and the run still ends on
   `step_timeout_s`. (b) If OpenCode exits by itself but needs more than 5 s after its final event to do so (it
   writes its session), set `RESULT_GRACE_S` in 6.2 to twice the observed time, rounded up to whole seconds.
2. **Does cmdc exit after its result?** (live check item 4.) Expected: yes (`--output-format json` prints one result
   and the process ends), so the grace never fires for cmd. If it stays up: the grace ends the run, and because
   `cmd.summary` reads success from the exit code, 6.2 writes exit 0. Then, before this task lands, check the
   fixture's result line for an error field (`is_error`, `error`, `subtype`): if there is one, `cmd.summary` reads
   `subtype` from that field when the `cc_exit` line has `after_result` (one more `elif` in 6.5's `summary`, and a
   case in `test_summary_and_cap`); if there is none, keep 6.5 as written. Also `RESULT_GRACE_S` as in item 1 (b).
3. **What does cmdc's usage report for input vs cached tokens?** (the `tests/fixtures/cmd-run.jsonl` result line.)
   Expected: OpenAI-style, `cached_input_tokens` counted inside `input_tokens`, as Codex reports it (the cmd models
   are OpenAI-compatible ones). 6.5 is written for that. If the line has `cache_read_input_tokens` (Anthropic style)
   or no cache key: 6.5 still holds, nothing changes. If it has `cached_input_tokens` but `input_tokens` already
   excludes them (the input count is smaller than the cached count on a resumed turn, or Fred's provider page says
   so): in 6.5 replace `max((usage.get("input_tokens") or 0) - inside, 0)` with `usage.get("input_tokens") or 0`, and
   in 6.8 `test_summary_and_cap` expect `"input": 500` for the `openai` case.
4. **Which codex exe does the probe find on Windows, `codex.cmd` or `codex.exe`?** (live check item 3.) Expected:
   `codex.cmd`, the npm shim (the vendor folder holding `codex.exe` is not on PATH). 6.4 is written so that the
   answer changes no line: the command never carries the cwd and never a quote, whichever exe runs it
   (`Decision:` in 6.4). If `codex.exe` was found: no change. If `codex.cmd` was found and live check item 8 (Stop)
   showed a `node` or `codex` process left in Task Manager after Stop: not this task's code (taskkill `/T` already
   takes the tree); record it in plan 5's History and stop to ask Fred.
5. **Does Codex accept the bare effort value?** (not a live check item; one command for Fred, a few seconds:)
   `codex exec --skip-git-repo-check -c model_reasoning_effort=high "say hi"` in any folder. Expected: the header
   Codex prints names `reasoning effort: high` and no config error. If it errors: in 6.4 keep the bare value only
   for a `.cmd` / `.bat` exe (`PurePath(str(exe[0])).suffix.lower() in (".cmd", ".bat")`, as `cmd.run_command`
   tests it) and the quoted `f'model_reasoning_effort="{...}"'` otherwise; `test_command_shape` then checks both.

## Why a stop after the final event keeps the Stop rule

CLAUDE.md: "Stop is the stream-json interrupt, never a kill of a run this service owns." Plan 5 decision 8 (Fred
confirmed after the review, 2026-10-13): "An adapter without an interrupt is stopped with `claude_cli.kill_tree`
(the tree, so the model's child commands end too); the rule "Stop is the stream-json interrupt, never a kill of a
run this service owns" holds for Claude runs, and this is the one documented exception for harnesses that have no
interrupt". The grace in 6.2 runs only for `adapter.INTERRUPT` false (Codex, OpenCode, cmd), goes through that
adapter's own `stop` (which is `kill_tree`, decision 8's exception), and never touches a Claude run (`INTERRUPT`
true, its turn ends when `_watch` closes stdin after the result line, as before). It is the same path plan 5 Task 4
already uses for the step timeout on these adapters; the difference is the turn's final event is already in the
stream, so the run ends as that turn ended, not as `error_step_timeout` and not as Fred's Stop (`stopping` is not
set, so `run_ended.stopped` stays false).

**Files**
- Modify: `console/claude_cli.py` (import line, new `stop_footer` after `STOP_FOOTER`, `kill_tree` replaced whole)
- Modify: `console/runs.py` (import line, new `RESULT_GRACE_S`, one statement in `RunManager.start`, `_spawn`'s
  `kwargs`, `_watch` replaced whole)
- Modify: `console/harness/codex.py` (`run_command`'s docstring, `cmd` list and return line)
- Modify: `console/harness/cmd.py` (`run_command`'s `cmd` list, the usage block of `summary`)
- Modify: `console/harness/claude.py` (the last two lines of `run_command`)
- Modify: `console/server.py` (`Hub.harnesses` only)
- Modify: `tests/fake_codex.py`, `tests/fake_cmd.py`, `tests/fake_opencode.py` (the word `LINGER`)
- Modify: `tests/test_runs.py`, `tests/test_claude_cli.py`, `tests/test_harness.py`, `tests/test_server.py`

## 6.1 `console/claude_cli.py`

Replace the import lines `import shutil` / `import subprocess` (lines 6 and 7) with:

```python
import shutil
import signal
import subprocess
```

Insert after the `STOP_FOOTER = (...)` statement (its last line is `               "one line: STOP: <question>")`):

```python


def stop_footer(prompt: str) -> str:
    """The footer every harness adds to a run's prompt: none for a slash command (plan 27 Task 6)."""
    return "" if str(prompt).startswith("/") else STOP_FOOTER
```

Replace `kill_tree` whole. Current:

```python
def kill_tree(pid) -> None:
    """Last resort for a run this service did not start (no stdin to send an interrupt to)."""
    subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True,
                   creationflags=NO_WINDOW)
```

New:

```python
def kill_tree(pid) -> None:
    """Kill a process and its children: a run this service did not start (no stdin to send an interrupt to), or
    the Stop of an adapter without an interrupt (plan 5 decision 8). Windows: taskkill /T /F. POSIX: the run's
    process group (runs.RunManager._spawn starts each run in a new session, so its pid is its group id); a pid that
    leads no group of its own is killed alone, so this never takes the service's own group. Never raises there."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True,
                       creationflags=NO_WINDOW)
        return
    pid = int(pid)
    try:
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:  # gone already, or not ours
        pass
```

## 6.2 `console/runs.py`

Replace the import lines `import json` / `import subprocess` with:

```python
import json
import os
import subprocess
```

Insert after `CMD_PROMPT_MAX = 30000  # Command Code takes the prompt in argv`:

```python
RESULT_GRACE_S = 10  # an adapter without an interrupt still running this long after its final event is stopped
```

In `RunManager.start`, the `elif harness == "opencode":` branch. Replace:

```python
            pfile.write_text(model_prompt if prompt.startswith("/") else model_prompt + claude_cli.STOP_FOOTER,
                             encoding="utf-8")
```

with:

```python
            pfile.write_text(model_prompt + claude_cli.stop_footer(prompt), encoding="utf-8")
```

In `_spawn`, insert after the two lines

```python
            kwargs = dict(cwd=cwd, stdin=subprocess.PIPE, stdout=out, stderr=subprocess.STDOUT,
                          env=env if env is not None else claude_cli.child_env())
```

these lines (same indentation, before the `try:  # leave any job object ...` line; the `creationflags` stay as they
are: they are 0 on POSIX):

```python
            if os.name != "nt":  # its own process group, so claude_cli.kill_tree can end the run with its children
                kwargs["start_new_session"] = True
```

Replace `_watch` whole (from `    def _watch(` to the line before `    def _finish(`) with:

```python
    def _watch(self, sid: str, proc, path: Path, offset: int, adapter, started: float) -> None:
        """Close stdin after the result line (stream-json input waits for more otherwise). A capless adapter
        (no turn or spend flag) is stopped once the run is older than step_timeout_s: a cap, not Fred's Stop.
        An adapter without an interrupt still running RESULT_GRACE_S after its final event is stopped too: its
        turn is done, so the run ends as that turn ended (exit 0 in cc_exit and run_ended, the OS code kept in
        cc_exit's `after_result`), never as a timeout (plan 27 Task 6, K10)."""
        seen, timed_out, seen_at, lingered = False, False, None, False
        while True:
            offset, lines = read_lines(path, offset)
            seen = seen or any(adapter.is_result(d) for d in lines)
            if seen and seen_at is None:
                seen_at = time.time()
            if (seen or proc.poll() is not None) and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
            if proc.poll() is not None:
                end = {"type": "cc_exit", "code": 0 if lingered else proc.returncode, "ts": time.time()}
                if lingered:
                    end["after_result"] = proc.returncode
                self._append(path, end)
                break
            if not adapter.INTERRUPT and seen_at is not None and not (lingered or timed_out) \
                    and time.time() - seen_at > RESULT_GRACE_S:
                lingered = True  # stopping is NOT set and timed_out stays False: the turn has ended
                try:
                    adapter.stop(proc)
                except (OSError, ValueError):
                    pass
            limit = self.cfg.get("step_timeout_s") or 0
            if not adapter.CAPS and limit > 0 and not (timed_out or lingered) and time.time() - started > limit:
                timed_out = True  # stopping is NOT set: this is a cap
                meta = self.meta(sid)
                if meta:
                    meta["timed_out"] = True
                    self._save_meta(meta)
                try:
                    adapter.stop(proc)
                except (OSError, ValueError):
                    pass
            time.sleep(WATCH_S)
        self._finish(sid, 0 if lingered else proc.returncode, timed_out)
        with self.lock:
            if self.live.get(sid) is proc:
                del self.live[sid]
```

## 6.3 Exit 0 after the grace

`Decision: a run stopped after its final event records exit 0 (cc_exit "code" and run_ended "exit"), with the OS
exit code in cc_exit "after_result", because opencode.summary and cmd.summary read success from the exit code
(plan 5 Task 3) and the review's fix asks that the run "ends as success"; keeping the real code beside it means
nothing is lost, and no adapter changes for it.` Codex reads its subtype from `turn.completed` / `turn.failed`, so a
failed Codex turn that lingers still ends as `error`.

## 6.4 `console/harness/codex.py` (K11)

`Decision: always cwd= and the bare effort value, not only when the exe is a .cmd shim, because runs._spawn already
gives every run cwd=, `codex exec` works in its process cwd when -C is absent, and Codex's -c parses a value as TOML
and takes one that is not TOML as a literal string, so model_reasoning_effort=high and model_reasoning_effort="high"
set the same key; one command shape for both exes keeps one test.` (Before you start, item 5, is the check.)

In `run_command`, replace:

```python
    """Options stand before `resume` / `fork`; the prompt is read from stdin (`-`). budget, max_turns and name
    have no Codex flag and are ignored (step_timeout_s is the cap)."""
    cmd = list(exe) + ["exec", "--json", "-C", cwd, "--skip-git-repo-check", "-m", model,
                       "-c", f'model_reasoning_effort="{EFFORT.get(effort, "medium")}"',
                       "-s", "read-only" if read_only else "workspace-write"]
```

with:

```python
    """Options stand before `resume` / `fork`; the prompt is read from stdin (`-`). budget, max_turns and name
    have no Codex flag and are ignored (step_timeout_s is the cap). `cwd` is the process cwd (runs sets it), not
    `-C`, and the effort value is bare: on Windows Codex is often the npm codex.cmd shim, and cmd.exe re-reads its
    arguments, so no path and no quote rides in argv (plan 27 Task 6, K11). `-c` parses the value as TOML and
    takes a value that is not TOML as a plain string, so `high` and `"high"` set the same key."""
    cmd = list(exe) + ["exec", "--json", "--skip-git-repo-check", "-m", model,
                       "-c", f"model_reasoning_effort={EFFORT.get(effort, 'medium')}",
                       "-s", "read-only" if read_only else "workspace-write"]
```

Replace the return line `    return cmd, (prompt + claude_cli.STOP_FOOTER).encode("utf-8")` with:

```python
    return cmd, (prompt + claude_cli.stop_footer(prompt)).encode("utf-8")
```

The `cwd` parameter stays in the signature (every adapter's `run_command` has it; plan 5 3.3).

## 6.5 `console/harness/cmd.py`

In `run_command`, replace:

```python
    cmd = list(exe) + ["-p", prompt + claude_cli.STOP_FOOTER, "--output-format", "json", "--no-auto-update",
                       "--skip-onboarding", "--no-skills", "-m", model, "--effort", EFFORT.get(effort, "medium"),
                       "--permission-mode", "plan" if read_only else "accept-edits"]
```

with:

```python
    cmd = list(exe) + ["-p", prompt + claude_cli.stop_footer(prompt), "--output-format", "json",
                       "--no-auto-update", "--skip-onboarding", "--no-skills", "-m", model,
                       "--effort", EFFORT.get(effort, "medium"),
                       "--permission-mode", "plan" if read_only else "accept-edits"]
```

In `summary`, replace (depends on Before you start, item 3):

```python
        if isinstance(usage, dict):
            cached = usage.get("cached_input_tokens") or usage.get("cache_read_input_tokens") or 0
            tokens = {"input": usage.get("input_tokens") or 0, "output": usage.get("output_tokens") or 0,
                      "cache_read": cached, "context": None}
```

with:

```python
        if isinstance(usage, dict):  # OpenAI-style usage counts cached_input_tokens inside input_tokens (as Codex);
            # Anthropic-style cache_read_input_tokens are outside it (plan 27 Task 6)
            inside = usage.get("cached_input_tokens") or 0
            cached = inside or usage.get("cache_read_input_tokens") or 0
            tokens = {"input": max((usage.get("input_tokens") or 0) - inside, 0),
                      "output": usage.get("output_tokens") or 0, "cache_read": cached, "context": None}
```

## 6.6 The STOP footer: one rule (plan 5 nit)

`Decision: no harness adds the STOP footer to a prompt that starts with "/", because Claude (plan 5 Task 1) and
OpenCode (plan 5 Task 4) already skip it there, a slash command's text is its argument, and one helper
(claude_cli.stop_footer) used by all four keeps the rule in one place.`

`console/harness/claude.py`, in `run_command`, replace:

```python
    footer = "" if prompt.startswith("/") else claude_cli.STOP_FOOTER
    return cmd, claude_cli.user_message(prompt + footer, blocks)
```

with:

```python
    return cmd, claude_cli.user_message(prompt + claude_cli.stop_footer(prompt), blocks)
```

(Codex in 6.4, cmd in 6.5, OpenCode in 6.2's `start` line.)

## 6.7 `console/server.py` (`Hub.harnesses`, plan 5 nit)

The window never reads `harnesses.claude.models`: `addOptions` skips `claude`, `rankOf` reads a Claude rung through
`alias`, and the Tiers tab builds Claude's rungs from `cfg.ladder`. So plan 5 Task 5's text holds, no amendment.
Replace:

```python
                       "version": self.versions_h.get(name, ""), "models": harness.models_of(self.cfg, name),
```

with:

```python
                       "version": self.versions_h.get(name, ""),
                       "models": {} if name == "claude" else harness.models_of(self.cfg, name),
```

## 6.8 Tests

`tests/fake_codex.py`: in the docstring replace `MAXTURNS ignored.` (end of the "Words" sentence) with
`MAXTURNS ignored, LINGER (stays up` and a new line `60 s after turn.completed, a CLI that does not exit after its
final event).` In `main`, replace the last `    return 0` (after the `turn.completed` line) with:

```python
    if "LINGER" in prompt:
        time.sleep(60)
    return 0
```

`tests/fake_cmd.py`: docstring `FAIL exits 1.` becomes `FAIL exits 1; LINGER stays up 60 s after the result.`; in
`main`, after the `out({"type": "result", ...})` line, before `    return 0`:

```python
    if "LINGER" in query:
        time.sleep(60)
```

`tests/fake_opencode.py`: docstring `FAIL exits 1 after the text.` becomes `FAIL exits 1 after the text; LINGER stays
up 60 s after` and a new line `session.idle.`; in `main`, after `    out({"type": "session.idle"})`, before
`    return 0`:

```python
    if "LINGER" in prompt:
        time.sleep(60)
```

`tests/test_runs.py`: remove the line `import signal`. Insert after the `FAKE_CMD = ...` line:

```python
FAKE_OPENCODE = [sys.executable, str(Path(__file__).resolve().parent / "fake_opencode.py")]
```

In `HarnessRunsTest.setUp`, remove these three lines (kill_tree now works on POSIX):

```python
        killer = mock.patch.object(claude_cli, "kill_tree", lambda pid: os.kill(int(pid), signal.SIGTERM))
        killer.start()  # taskkill is Windows' tree kill; the fakes have no children
        self.addCleanup(killer.stop)
```

Insert in `HarnessRunsTest` after `test_stop_kills_a_codex_run`:

```python
    def test_a_run_left_running_after_its_result_ends_as_success(self):
        # plan 27 Task 6 (K10): a CLI without an interrupt that stays up after its final event is stopped after
        # RESULT_GRACE_S; the turn is a success, not a timeout and not Fred's Stop
        self.mgr.exes["opencode"] = FAKE_OPENCODE
        with mock.patch.object(runs, "RESULT_GRACE_S", 1):
            for name, model in (("codex", "gpt-6.1-sol"), ("opencode", "kimi-k3"), ("cmd", "gpt-6-luna")):
                with self.subTest(harness=name):
                    begun = time.time()
                    sid = self.mgr.start(str(self.project), "LINGER task", model, "medium", harness=name)
                    self.assertTrue(wait_for(lambda: self.ended(sid), 20))
                    self.assertLess(time.time() - begun, 15)  # the fake sleeps 60 s after its final event
                    end = self.ended(sid)[0]
                    self.assertEqual((end["subtype"], end["exit"], end["stopped"], end["interrupted"]),
                                     ("success", 0, False, False))
                    self.assertFalse(self.mgr.meta(sid)["timed_out"])
                    last = runs.read_lines(self.mgr.stream_path(sid), 0)[1][-1]
                    self.assertEqual((last["type"], last["code"]), ("cc_exit", 0))
                    self.assertNotEqual(last["after_result"], 0)  # the OS exit code of the stopped process

    def test_opencode_prompt_file_follows_the_footer_rule(self):
        self.mgr.exes["opencode"] = FAKE_OPENCODE
        for prompt, footer in (("/review now", ""), ("review now", claude_cli.STOP_FOOTER)):
            sid = self.mgr.start(str(self.project), prompt, "kimi-k3", "medium", harness="opencode")
            self.assertTrue(wait_for(lambda: self.ended(sid)))
            self.assertEqual((self.mgr.runs / f"{sid}.prompt.md").read_text(encoding="utf-8"), prompt + footer)

    @unittest.skipIf(os.name == "nt", "process groups are POSIX; Windows uses the job object and taskkill")
    def test_a_run_leads_its_own_process_group(self):
        sid = self.mgr.start(str(self.project), "SLOW task", "gpt-6.1-sol", "medium", harness="codex")
        proc = self.mgr.live[sid]
        self.assertEqual(os.getpgid(proc.pid), proc.pid)
        self.assertTrue(wait_for(lambda: self.ended(sid), 20))
```

(`opencode` is added per test, not in `setUp`: `test_a_harness_without_an_exe_is_refused` needs it absent.)

`tests/test_claude_cli.py`: insert before `@unittest.skipUnless(os.name == "nt", "job objects are Windows only")`:

```python
def gone(pid) -> bool:
    """True when `pid` has exited (a zombie nobody reaped yet counts as gone)."""
    try:
        state = Path(f"/proc/{int(pid)}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return not claude_cli.pid_alive(pid)
    return state in ("Z", "X")


@unittest.skipIf(os.name == "nt", "process groups are POSIX; Windows uses taskkill /T")
class KillTreePosixTest(unittest.TestCase):
    def test_kill_tree_ends_the_run_and_its_children(self):
        # plan 27 Task 6: a run starts in a new session, so kill_tree takes its whole process group
        parent = subprocess.Popen([sys.executable, "-c",
                                   "import subprocess,sys,time; "
                                   "c = subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                                   "print(c.pid, flush=True); time.sleep(60)"],
                                  stdout=subprocess.PIPE, text=True, start_new_session=True)
        self.addCleanup(parent.wait)
        child = int(parent.stdout.readline())
        parent.stdout.close()
        claude_cli.kill_tree(parent.pid)
        parent.wait(10)
        for _ in range(50):
            if gone(child):
                break
            time.sleep(0.1)
        self.assertTrue(gone(child))

    def test_kill_tree_of_a_lone_process_and_of_a_gone_pid(self):
        # not a group leader (started without a new session): only that process; this test process lives on
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        claude_cli.kill_tree(proc.pid)
        self.assertIsNotNone(proc.wait(10))
        claude_cli.kill_tree(proc.pid)  # reaped: no such process, never raises
```

`tests/test_harness.py`, `CodexTest.test_command_shape`: replace

```python
        self.assertEqual(cmd[cmd.index("-C") + 1], "D:/p")
        self.assertEqual(cmd[cmd.index("-m") + 1], "gpt-6.1-sol")
        self.assertEqual(cmd[cmd.index("-c") + 1], 'model_reasoning_effort="high"')
```

with:

```python
        self.assertNotIn("-C", cmd)  # plan 27 Task 6 (K11): the process cwd, no path through a .cmd shim
        self.assertNotIn("D:/p", cmd)
        self.assertEqual(cmd[cmd.index("-m") + 1], "gpt-6.1-sol")
        self.assertEqual(cmd[cmd.index("-c") + 1], "model_reasoning_effort=high")  # bare: no quotes for cmd.exe
```

Insert before `class OpenCodeTest(unittest.TestCase):`:

```python
class StopFooterTest(unittest.TestCase):
    def test_one_rule_for_slash_prompts(self):
        # plan 27 Task 6: every harness leaves the STOP footer off a prompt that starts with "/"
        self.assertEqual(claude_cli.stop_footer("/review"), "")
        self.assertEqual(claude_cli.stop_footer("review"), claude_cli.STOP_FOOTER)
        _, stdin = codex.run_command(["x"], "m", "low", "/w", "sid", prompt="/review now")
        self.assertEqual(stdin.decode(), "/review now")
        cmd, _ = cmd_adapter.run_command(["cmdc"], "m", "low", "/w", "sid", prompt="/review now")
        self.assertEqual(cmd[cmd.index("-p") + 1], "/review now")
        _, slash = claude_adapter.run_command(["fake"], "sonnet", "medium", "/w", "sid", prompt="/review now")
        self.assertEqual(slash, claude_cli.user_message("/review now"))


```

`CmdTest.test_summary_and_cap`: insert after `        self.assertEqual(s["tokens"]["input"], 500)` (depends on
Before you start, item 3):

```python
        # plan 27 Task 6: OpenAI-style usage counts the cached tokens inside input_tokens (as Codex does)
        openai = cmd_adapter.summary([{"type": "result", "result": "x", "usage": {
            "input_tokens": 500, "cached_input_tokens": 200, "output_tokens": 100}}])
        self.assertEqual(openai["tokens"], {"input": 300, "output": 100, "cache_read": 200, "context": None})
        anthropic = cmd_adapter.summary([{"type": "result", "result": "x", "usage": {
            "input_tokens": 500, "cache_read_input_tokens": 200, "output_tokens": 100}}])
        self.assertEqual(anthropic["tokens"], {"input": 500, "output": 100, "cache_read": 200, "context": None})
```

`tests/test_server.py`, `HarnessServerTest.test_config_lists_harnesses`: insert after
`        self.assertEqual((data["claude"], data["harnesses"]["claude"]["found"]), (True, True))`:

```python
        self.assertEqual(data["harnesses"]["claude"]["models"], {})  # plan 5 Task 5: Claude's models are the ladder
```

## 6.9 Steps

1. Read plan 5 Task 7's History and fixtures; answer the five questions of "Before you start" and apply the line
   changes they name, if any.
2. Write the tests of 6.8 (fakes first). Run `py -m unittest tests.test_harness tests.test_claude_cli
   tests.test_server.HarnessServerTest.test_config_lists_harnesses`. Seen in the scratch copy on Linux (on Windows
   the two `KillTreePosixTest` tests are skipped):
   - `test_one_rule_for_slash_prompts`: `AttributeError: module 'console.claude_cli' has no attribute 'stop_footer'`
   - `test_kill_tree_ends_the_run_and_its_children` and `test_kill_tree_of_a_lone_process_and_of_a_gone_pid`:
     `FileNotFoundError: [Errno 2] No such file or directory: 'taskkill'`
   - `CmdTest.test_summary_and_cap`: `AssertionError: {'input': 500, 'output': 100, 'cache_read': 200, 'context':
     None} != {'input': 300, ...}`
   - `CodexTest.test_command_shape`: `AssertionError: '-C' unexpectedly found in ['x', 'exec', '--json', '-C',
     'D:/p', ...]`
   - `test_config_lists_harnesses`: `AssertionError: {'opus': 'opus', 'sonnet': 'sonnet', 'haik[139 chars]iku'} != {}`
3. Run `py -m unittest tests.test_runs.HarnessRunsTest`. Seen on Linux (the `kill_tree` patch is gone):
   - `test_a_run_left_running_after_its_result_ends_as_success`: `AttributeError: <module 'console.runs' ...> does
     not have the attribute 'RESULT_GRACE_S'`
   - `test_a_run_leads_its_own_process_group`: `AssertionError: 27450 != 27464`
   - `test_step_timeout_stops_a_capless_run`: `AssertionError: 'turn.completed' unexpectedly found in ...` (taskkill
     is missing, so the timeout never killed the run)
   - `test_stop_kills_a_codex_run`: `AssertionError: 'finishing' != 'kill'`
   On Windows only the first fails (`taskkill` exists there).
4. Apply 6.1 to 6.7. Run the same commands: all green (`tests.test_runs` 25, `tests.test_claude_cli` 18 with 2
   skipped on Linux, `tests.test_harness` 28).
5. The whole suite `py -m unittest discover -s tests`: 531 in the scratch copy (525 plus six), plus whatever Tasks 1
   to 5 added; only the Linux baseline failures on Linux, none on Windows.
6. Commit: `plan 27 task 6: harness edges: grace stop after the final event, codex cwd, kill_tree on POSIX (N tests
   OK)`.

## 6.10 Drift guards

- The grace runs only for `adapter.INTERRUPT` false, and only through `adapter.stop`. A Claude run is never killed
  by `_watch`; its Stop stays the stream-json interrupt (CLAUDE.md).
- The grace sets neither `stopping` nor `timed_out` nor `meta["timed_out"]`; the step timeout and the grace never
  both fire for one run (each checks the other's flag).
- `kill_tree` keeps taskkill `/T /F` as the Windows path, unchanged; `_spawn` keeps both `creationflags` attempts
  and `join_service_job`; `start_new_session` is set on POSIX only.
- `kill_tree` never calls `os.killpg` on a pid that is not its own group leader (it would take the service's
  group); it never raises on POSIX.
- `codex.run_command` keeps its signature (`cwd` stays, unused) and option order (options before `resume` /
  `fork`); `cmd.run_command` keeps its `.cmd` / `.bat` refusal.
- `claude_cli.stop_footer` is the only place that decides the footer; no adapter tests `startswith("/")` itself.
- `Hub.harnesses` changes only the `"models"` entry, for `claude` only; the other keys and the order of
  `harness.NAMES` stay.
- Do not touch `opencode.summary`, `cmd._exit_code` or `result_record`: exit 0 comes from `_watch` (6.3).
