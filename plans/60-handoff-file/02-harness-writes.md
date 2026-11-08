# Task 2: Give the model its output without changing project cwd

Plan only. All of D1 needs Fred's answer. Future files: the four adapters, `console/harness/__init__.py`,
`console/runs.py`, new `console/handoff_guard.py`, harness/run tests and a focused guard test.
Sources and limitations are in README section 5. The concrete code below is the recommended first release;
it deliberately refuses unsupported read-only file routes rather than guessing flags. D1d(b) needs a revised task.

## 1. Adapter seam and dispatch

Add keyword-only `handoff_path: str = ""` to each adapter's `run_command`. An empty value preserves existing
behavior exactly. RunManager passes a validated absolute path constructed from its own home and the reserved
relative path, not an HTTP string. Persist the output identity in run metadata (Task 3). `env(read_only)` remains
unchanged except that unsupported file-mode launches are refused before spawn.

Classify a file worker with `kind in tasks.SOURCE_READ_ONLY`, never `tools == READ_ONLY_TOOLS`. This does not
turn proofread into read-only: its existing tool list permits editing, despite the old generic prompt omission.
Keep all existing harness gates, including OpenCode/Command Code being excluded from verify/fix.

The two unsupported cases are final code, not a TODO that widens permissions:

```python
# In opencode.run_command and cmd.run_command, before constructing argv:
    if handoff_path and read_only:
        raise ValueError(f"{NAME}: no verified read-only handoff-file grant; choose Claude or Codex")
```

Add the same reason to `Hub.rung_ok` for `kind in FILE_KINDS` and `SOURCE_READ_ONLY`, after existing availability
checks. Auto routing filters these rungs before spending; an explicit choice is refused visibly. Do not modify
the automatic retry policy from the F1 fix. This refusal does not turn either harness on/off in configuration.

Writer Command Code adds `--add-dir <output-parent>` in argv, preserving accept-edits, `--no-skills`, effort,
Node entry-point handling and resume/fork flags. Its plan mode is not changed. Writer OpenCode keeps standalone,
project cwd, attached prompt and its existing writer environment; V2's external-path default and `--auto` allow
the write unless an explicit user/managed deny refuses it. No permission rule is removed. Real checks must
confirm this behavior; a denial still fails the step. Do not add undocumented V1 env overrides as a V2 solution.

## 2. Claude: one new file tool with a fail-closed guard

Source-read-only kinds gain `Write`; they do not gain Edit or Bash. Test/verify already have Bash and retain it.
All other listed tools stay as in RULES. Keep `--strict-mcp-config`, Agent disallow, budget and max turns.

In `console/harness/claude.py`, add `json`, `sys`, `Path` imports. The adapter already receives `read_only` and
`tools`; do this before its call to `claude_cli.run_command`, then append settings after that call:

```python
    if handoff_path and read_only:
        tools = ",".join(dict.fromkeys((tools or "").split(",") + ["Write"]))
```

```python
    if handoff_path:
        target = str(Path(handoff_path).absolute())
        settings = {"permissions": {"additionalDirectories": [str(Path(target).parent)]}}
        if read_only:
            guard = str(Path(__file__).resolve().parents[1] / "handoff_guard.py")
            settings["hooks"] = {"PreToolUse": [{
                "matcher": "Write|Edit|NotebookEdit",
                "hooks": [{"type": "command", "command": sys.executable,
                           "args": [guard, target], "timeout": 10, "onFailure": "block"}]
            }]}
        cmd += ["--settings", json.dumps(settings, ensure_ascii=False)]
```

`command` plus `args` is the documented direct-execution form. It avoids quoting a shell command containing
Fred's paths. The helper is an absolute installed-source path, not `python -m` resolved from the project cwd.
The actual executable must support `args` and `onFailure`; require Claude >= 2.1.295 and Task 5's failure probe.
Do not suppress managed deny rules; an explicit deny may make the output unavailable and must be reported.

Final contents of `console/handoff_guard.py` (standard library only):

```python
"""Read-only Claude file tools may write only the assigned step output."""
import json
import os
from pathlib import Path
import sys


def allowed(event: dict, target: str) -> bool:
    if event.get("tool_name") != "Write":
        return False
    value = (event.get("tool_input") or {}).get("file_path")
    if not isinstance(value, str) or not Path(value).is_absolute():
        return False
    wanted, actual = Path(target), Path(value)
    for parent in (wanted.parent, wanted.parent.parent, wanted.parent.parent.parent):
        if parent.is_symlink() or parent.is_junction():
            return False
    if actual.is_symlink() or actual.is_junction():
        return False
    if actual.exists() and (not actual.is_file() or actual.stat().st_nlink != 1):
        return False
    return os.path.normcase(str(actual.resolve())) == os.path.normcase(str(wanted.resolve()))


def main() -> int:
    try:
        event = json.load(sys.stdin)
        ok = isinstance(event, dict) and len(sys.argv) == 2 and allowed(event, sys.argv[1])
    except Exception:
        ok = False
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "allow" if ok else "deny",
        "permissionDecisionReason": "Only this turn's handoff.md is writable by file tools"
    }}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The guard rejects linked/junction parents through the task directory before comparing resolved paths.
Keep the helper standalone: do not import
`tasks` and load the Console/harness tree into each hook. Test parent links as well as file links.
This hook restricts file tools. It is **not** a shell sandbox: tests/verify keep their existing shell authority
(D1b). Do not advertise arbitrary subprocesses as read-only. Do not change cc_events or install_hooks.py.

## 3. Codex: preserve the Windows fix and the writer's package roots

Writing file steps retain existing `-s workspace-write`, network setting and `_package_roots(cwd)`. Append the
resolved output parent to that list, deduplicated, before the existing JSON/TOML writable_roots argument. Use
argv entries, not a composed shell string. Run `write_block(output_parent)` after creating it and before spawn;
retain `write_block(project)` for writing work. Preserve the PATH workaround and `.env`/managed denials.

For a source-read-only file step, do not emit `-s read-only` or any `sandbox_workspace_write` option. Use the
documented profile, with `-c` entries before resume/fork as existing options are. Final helper:

```python
def handoff_permissions(path: str) -> list:
    root = Path(path).resolve().parent.as_posix()
    scratch = (Path(root) / "tmp").as_posix()
    args = [
        "-c", 'default_permissions="console_handoff"',
        "-c", 'permissions.console_handoff.extends=":read-only"',
        "-c", "permissions.console_handoff.filesystem." + json.dumps(root) + '="write"',
        "-c", 'permissions.console_handoff.network.enabled=false',
        "-c", 'approval_policy="never"',
    ]
    for key in ("TMP", "TEMP", "TMPDIR"):
        args += ["-c", f"shell_environment_policy.set.{key}=" + json.dumps(scratch)]
    return args
```

The grant is one output directory, not the task root, home, or project. All other reads keep the inherited
read-only profile. Before spawn, RunManager creates `tmp` under that output directory for the Codex read-only
path; TMP/TEMP/TMPDIR point there. This preserves ordinary temporary-file tests without granting a whole system
temp directory or writable source tree. No package cache roots or network write-mode extras are injected.
Tests needing a writable project fail honestly; they do not cause automatic sandbox broadening. Fred can choose a different
harness through existing actions. The new artifact exception is the only write grant added here.

Preflight must inspect effective legacy sandbox settings and the configured version, not just check for the
word `--add-dir` in help. A top-level/user/project/profile `sandbox_mode` overrides the new permissions profile;
managed requirements may forbid the custom profile. Refuse a conflict with:

```text
codex: read-only handoff output needs permission profiles; legacy sandbox settings or managed policy conflict.
Review the Codex configuration, or choose Claude. Console has changed no CLI settings.
```

This is a release gate: use Codex's effective-configuration diagnostics in the build/live-check session to
verify that the actual run selects this profile, including resumed turns. A compatible top-level config on
this machine is evidence, not proof about project/profile/managed layers. If there is no reliable read-only
effective-config preflight for the installed CLI, mark Codex's read-only file route unavailable with that reason
until Fred chooses the setup change; do not silently continue on the legacy sandbox. The helper is final for
the documented compatible configuration, not a promise to override an administrator.

Do not use `--output-last-message` as the file write: that captures a reply and keeps the same response-format
dependence, contrary to Fred's chosen transport. Do not use `--ignore-user-config`, a replacement CODEX_HOME,
danger-full-access, elevated shell execution or an ACL change to make the plan appear to work.

## 4. Future checks and rollout conditions

Adapter/run unit cases assert argv and environment for scout, verify and code on all four harnesses, with and
without an output. Include Windows paths with spaces, non-ASCII and both separators, resumed turns, package
root deduplication and write_block failures on the output parent. Keep normal chat/legacy commands unchanged.
Guard tests call `allowed` on exact target, another file, missing path, links, hardlinks and malformed inputs;
invoke the script with invalid JSON to prove denial rather than a traceback/fail-open exit.

Task 5 then checks actual tools: writing output succeeds; a project file-tool edit fails for read-only work;
Claude missing/broken/timed-out guard blocks the tool; Codex uses the intended profile on Windows and Continue.
Unit argv tests cannot prove any of those. OpenCode/Command Code read-only refusal is an acceptance case, not a
successful support claim. Their writer grants must also be checked if Fred keeps those harnesses available.

Done check after implementation: focused `test_harness.py`, `test_runs.py` and guard cases pass. Real checks are
recorded separately, with CLI versions and observed outcomes. No global or project CLI configuration is written.
