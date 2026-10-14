# Task 4: Lean steps: no MCP server, the turn cap of read kinds, the one window setting

> Contract: [README.md](README.md) 3.6, 3.8 (`POST /api/setting`'s writer), 3.9. Run in the scratch copy: the code
> below is the final code against today's `claude_cli.py`, `runs.py`, `paths.py`. Independent of Tasks 1 to 3.

**Files**
- Modify: `console/claude_cli.py` (`run_command(strict_mcp)`)
- Modify: `console/runs.py` (`RunManager.start(strict_mcp)`, `limits["strict_mcp"]`)
- Modify: `console/paths.py` (DEFAULTS `read_max_turns`, `handoff_auto`; new `SETTINGS`, `set_setting`)
- Modify: `tests/test_claude_cli.py`, `tests/test_runs.py`, `tests/test_paths.py` (plan 24 Task 1 created it)

**Lands on** plan 5 Task 4: after plan 5, `runs.start` builds the command through the adapter with
`claude_only = {"tools": ..., "disallow": ..., "blocks": attach.blocks(files)}` for `claude`. Add
`"strict_mcp": bool(limits.get("strict_mcp"))` to that dict, `strict_mcp: bool = False` to the Claude adapter's
`run_command` (it passes it on to `claude_cli.run_command`), and keep `strict_mcp` in `limits` exactly as below.
Other adapters ignore it (they load no MCP server). Plan 5's `test_claude_adapter_wraps_claude_cli` is unchanged
(the default is False).

**Lands on** plan 24 Task 3: DEFAULTS has `design_max_turns` 30 where the diff's context shows `opus_max_turns` 12;
the two new keys go right after it.

**Lands on** plan 24 Task 1: `tests/test_paths.py` exists already (plan 24 put
`test_design_max_turns_replaces_the_opus_cap` there). Do not overwrite it: add the class `SettingTest` below to that
file and merge the imports (`json`, `tempfile`, `Path`, `paths`); keep plan 24's test as it is.

**Lands on** plan 5 Task 5: plan 5's `READ_MAX_TURNS` constant (15) goes; Task 5 of this plan reads
`cfg["read_max_turns"]`.

## 4.1 `console/claude_cli.py`

```diff
diff --git a/console/claude_cli.py b/console/claude_cli.py
index 75a1165..8dcc220 100644
--- a/console/claude_cli.py
+++ b/console/claude_cli.py
@@ -62,10 +62,11 @@ def brief_command(exe: list, model: str, schema: dict) -> list:
 
 def run_command(exe: list, model: str, effort: str, session_id: str, resume: bool = False,
                 name: str = "", fork: str = "", disallow: tuple = (), tools: str = None,
-                budget: float = 0.0, max_turns: int = 0) -> list:
+                budget: float = 0.0, max_turns: int = 0, strict_mcp: bool = False) -> list:
     """D5: auto mode, nobody answers prompts (a denial ends up in the result). Prompts go in on stdin.
     `fork`: start `session_id` as a copy of that chat (its context, a new id; the original is not touched).
-    Step limits (plan 17): `disallow` tool names, `tools` (the --tools list), a spend cap, a turn cap."""
+    Step limits (plan 17): `disallow` tool names, `tools` (the --tools list), a spend cap, a turn cap; plan 23:
+    `strict_mcp` loads no MCP server (--strict-mcp-config with no --mcp-config, as Prep runs)."""
     cmd = exe + ["-p", "--model", model, "--effort", effort, "--permission-mode", "auto",
                  "--permission-prompts", "none", "--input-format", "stream-json",
                  "--output-format", "stream-json", "--verbose"]
@@ -73,6 +74,8 @@ def run_command(exe: list, model: str, effort: str, session_id: str, resume: boo
         cmd += ["--disallowedTools", ",".join(disallow)]
     if tools is not None:
         cmd += ["--tools", tools]
+    if strict_mcp:
+        cmd += ["--strict-mcp-config"]
     if budget and budget > 0:
         cmd += ["--max-budget-usd", f"{budget:.2f}"]
     if max_turns and max_turns > 0:
```

`--strict-mcp-config` with no `--mcp-config` loads no MCP server; `--tools` alone does not remove MCP tools
(code.claude.com/docs/en/cli-reference, checked 2026-10-14; Prep's command already passes the flag).

## 4.2 `console/runs.py`

```diff
diff --git a/console/runs.py b/console/runs.py
index 7ed2e50..c54bc3b 100644
--- a/console/runs.py
+++ b/console/runs.py
@@ -148,7 +148,8 @@ class RunManager:
     def start(self, cwd: str, prompt: str, model: str, effort: str, resume: str = None,
               title: str = "", route: str = "", reason: str = "", prep: str = "",
               fork: str = "", kind: str = "run", extra: dict = None, files: list = (),
-              disallow: tuple = (), tools: str = "", budget: float = 0.0, max_turns: int = 0) -> str:
+              disallow: tuple = (), tools: str = "", budget: float = 0.0, max_turns: int = 0,
+              strict_mcp: bool = False) -> str:
         """A new run, a new turn of a window run (`resume`), or a window copy of another chat (`fork`).
         `kind` (run, continue, verify, handoff, escalate) and `extra` go into the run_started line.
         `files` (attach.parse) go inline after the prompt; the stream file keeps their summary only.
@@ -166,13 +167,15 @@ class RunManager:
                                  "files": attach.summary(files)}, ensure_ascii=False) + "\n")
         offset = path.stat().st_size
         old = self.meta(sid) or {}
-        limits = {"disallow": list(disallow), "tools": tools or "", "budget": budget, "max_turns": max_turns}
-        if resume and not (disallow or tools or budget or max_turns) and old.get("limits"):
+        limits = {"disallow": list(disallow), "tools": tools or "", "budget": budget, "max_turns": max_turns,
+                  "strict_mcp": strict_mcp}
+        if resume and not (disallow or tools or budget or max_turns or strict_mcp) and old.get("limits"):
             limits = old["limits"]
         cmd = claude_cli.run_command(self.exe, model, effort, sid, resume=bool(resume),
                                      name=redact.clip(title, 60), fork=fork,
                                      disallow=tuple(limits["disallow"]), tools=limits["tools"] or None,
-                                     budget=limits["budget"], max_turns=limits["max_turns"])
+                                     budget=limits["budget"], max_turns=limits["max_turns"],
+                                     strict_mcp=bool(limits.get("strict_mcp")))
         proc = self._spawn(cmd, cwd, path)
         footer = "" if prompt.startswith("/") else claude_cli.STOP_FOOTER  # a /skill takes no footer
         proc.stdin.write(claude_cli.user_message(prompt + footer, attach.blocks(files)))
```

## 4.3 `console/paths.py`

```diff
diff --git a/console/paths.py b/console/paths.py
index 6661387..ec03070 100644
--- a/console/paths.py
+++ b/console/paths.py
@@ -35,6 +35,8 @@ DEFAULTS = {
     "task_step_budget_usd": 3,
     "task_max_steps": 6,
     "opus_max_turns": 12,
+    "read_max_turns": 15,  # plan 23: --max-turns of a scout or search step
+    "handoff_auto": False,  # plan 23 (D-5): hand off a window run whose turn ends in the red zone
     "budget_warn_at": 0.8,  # share of a model's pace at which a step moves one model down
     "ladder": {  # newest rung first per tier, the alias first
         "haiku": ["haiku", "claude-haiku-4-5"],
@@ -106,6 +108,33 @@ def add_project(folder: Path, project: str) -> None:
     os.replace(tmp, path)
 
 
+SETTINGS = ("handoff_auto",)  # plan 23: the booleans the window may flip through POST /api/setting
+
+
+def set_setting(folder: Path, key: str, value: bool) -> None:
+    """Write one whitelisted boolean into <folder>/config.json; every other key stays as written. ValueError for a key
+    that is not in SETTINGS, a value that is not a bool, or a config.json that cannot be read."""
+    if key not in SETTINGS:
+        raise ValueError(f"not a setting: {key}")
+    if not isinstance(value, bool):
+        raise ValueError(f"{key} takes true or false")
+    path = Path(folder) / "config.json"
+    if path.exists():
+        try:
+            data = json.loads(path.read_text(encoding="utf-8"))
+        except (OSError, ValueError):
+            data = None
+        if not isinstance(data, dict):
+            raise ValueError(f"cannot read {path}: fix it by hand")
+    else:
+        data = copy.deepcopy(DEFAULTS)
+    data[key] = value
+    path.parent.mkdir(parents=True, exist_ok=True)
+    tmp = path.with_name("config.json.tmp")
+    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
+    os.replace(tmp, path)
+
+
 _WINDOW_LOCK = threading.Lock()  # the page (project) and the window (form, place) both save
 
 
```

## 4.4 Tests

`tests/test_claude_cli.py` (15 -> 16): `test_step_command_loads_no_mcp_server`.

```diff
diff --git a/tests/test_claude_cli.py b/tests/test_claude_cli.py
index 49c3863..f682ab3 100644
--- a/tests/test_claude_cli.py
+++ b/tests/test_claude_cli.py
@@ -47,6 +47,13 @@ class CommandTest(unittest.TestCase):
         two = claude_cli.run_command(["claude.exe"], "haiku", "low", "abc", disallow=("Agent", "Edit"))
         self.assertEqual(two[two.index("--disallowedTools") + 1], "Agent,Edit")
 
+    def test_step_command_loads_no_mcp_server(self):
+        cmd = claude_cli.run_command(["claude.exe"], "haiku", "low", "abc", tools="Read,Grep,Glob", strict_mcp=True)
+        self.assertIn("--strict-mcp-config", cmd)
+        self.assertNotIn("--mcp-config", cmd)  # strict with no config: no server at all
+        self.assertLess(cmd.index("--tools"), cmd.index("--strict-mcp-config"))
+        self.assertNotIn("--strict-mcp-config", claude_cli.run_command(["claude.exe"], "haiku", "low", "abc"))
+
     def test_tier_of_and_known_model(self):
         self.assertEqual([claude_cli.tier_of(m) for m in ("claude-opus-4-6", "opus", "gpt")], ["opus", "opus", ""])
         cfg = copy.deepcopy(paths.DEFAULTS)
```

`tests/test_runs.py`: `test_run_started_carries_task_and_step` passes `strict_mcp=True`, the limits hold it, a retry
keeps it, a plain run has `strict_mcp: False` (no new method).

```diff
diff --git a/tests/test_runs.py b/tests/test_runs.py
index b4cf506..9fd47e6 100644
--- a/tests/test_runs.py
+++ b/tests/test_runs.py
@@ -122,11 +122,11 @@ class RunsTest(unittest.TestCase):
 
     def test_run_started_carries_task_and_step(self):
         sid = self.mgr.start(str(self.project), "step", "haiku", "low", extra={"task": "t1", "step": 2},
-                             disallow=tasks.DISALLOW, tools="Read,Grep,Glob", budget=3)
+                             disallow=tasks.DISALLOW, tools="Read,Grep,Glob", budget=3, strict_mcp=True)
         self.assertTrue(wait_for(lambda: self.ended(sid)))
         started = [r for r in self.log() if r["event"] == "run_started"][0]
         self.assertEqual((started["task"], started["step"]), ("t1", 2))
-        limits = {"disallow": ["Agent"], "tools": "Read,Grep,Glob", "budget": 3, "max_turns": 0}
+        limits = {"disallow": ["Agent"], "tools": "Read,Grep,Glob", "budget": 3, "max_turns": 0, "strict_mcp": True}
         self.assertEqual(self.mgr.meta(sid)["limits"], limits)
         self.assertEqual(len(self.ended(sid)), 1)  # the fake claude ran, whatever the flags
         with mock.patch.object(runs.claude_cli, "run_command", wraps=runs.claude_cli.run_command) as cmd:
@@ -134,12 +134,12 @@ class RunsTest(unittest.TestCase):
             self.assertTrue(wait_for(lambda: len(self.ended(sid)) == 2))
         self.assertEqual(self.mgr.meta(sid)["limits"], limits)
         kwargs = cmd.call_args.kwargs
-        self.assertEqual((kwargs["disallow"], kwargs["tools"], kwargs["budget"], kwargs["max_turns"]),
-                         (("Agent",), "Read,Grep,Glob", 3, 0))
+        self.assertEqual((kwargs["disallow"], kwargs["tools"], kwargs["budget"], kwargs["max_turns"],
+                          kwargs["strict_mcp"]), (("Agent",), "Read,Grep,Glob", 3, 0, True))  # a retry keeps them
         plain = self.mgr.start(str(self.project), "plain", "sonnet", "low")  # no limits given: none kept
         self.assertTrue(wait_for(lambda: self.ended(plain)))
         self.assertEqual(self.mgr.meta(plain)["limits"],
-                         {"disallow": [], "tools": "", "budget": 0.0, "max_turns": 0})
+                         {"disallow": [], "tools": "", "budget": 0.0, "max_turns": 0, "strict_mcp": False})
 
     def test_forget_deletes_an_ended_run_only(self):
         sid = self.mgr.start(str(self.project), "first", "sonnet", "low")
```

`tests/test_paths.py` (+2, the class `SettingTest` added next to plan 24's test): `test_plan_23_defaults`, `test_set_setting_writes_one_key` (no config.json yet: the
defaults plus the key; a second write keeps `projects`; no `.tmp` left; ValueError for another key, a string, an int,
a broken file, which stays as it was).

```python
"""Plan 23: the config keys it adds and the one setting the window may write (paths.set_setting)."""
import json
import tempfile
import unittest
from pathlib import Path

from console import paths


class SettingTest(unittest.TestCase):
    def test_plan_23_defaults(self):
        d = paths.DEFAULTS
        self.assertEqual((d["read_max_turns"], d["handoff_auto"], d["brief_max_words"]), (15, False, 500))
        self.assertEqual(paths.SETTINGS, ("handoff_auto",))

    def test_set_setting_writes_one_key(self):
        with tempfile.TemporaryDirectory() as folder:
            paths.set_setting(Path(folder), "handoff_auto", True)  # no config.json yet: the defaults plus the key
            data = json.loads((Path(folder) / "config.json").read_text(encoding="utf-8"))
            self.assertIs(data["handoff_auto"], True)
            self.assertEqual(data["brief_max_words"], 500)
            data["projects"] = ["C:/x"]
            (Path(folder) / "config.json").write_text(json.dumps(data), encoding="utf-8")
            paths.set_setting(Path(folder), "handoff_auto", False)
            data = json.loads((Path(folder) / "config.json").read_text(encoding="utf-8"))
            self.assertEqual((data["handoff_auto"], data["projects"]), (False, ["C:/x"]))  # the rest stays
            self.assertFalse((Path(folder) / "config.json.tmp").exists())
            for key, value in (("brief_on", False), ("handoff_auto", "yes"), ("handoff_auto", 1)):
                with self.assertRaises(ValueError):
                    paths.set_setting(Path(folder), key, value)
            (Path(folder) / "config.json").write_text("{broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                paths.set_setting(Path(folder), "handoff_auto", True)
            self.assertEqual((Path(folder) / "config.json").read_text(encoding="utf-8"), "{broken")  # left as is


if __name__ == "__main__":
    unittest.main()
```

## 4.5 Steps

1. The tests. They fail.
2. The three modules.
3. Full suite: all OK (Linux scratch 350 = 347 + 3).
4. Commit: `Plan 23 Task 4: steps load no MCP server, read_max_turns and handoff_auto keys, set_setting (N tests OK)`.

**Drift guards**
- `set_setting` writes through a temp file and `os.replace`, as `paths.add_project` does; it never creates a key that
  is not in `SETTINGS`.
- `strict_mcp` defaults to False everywhere: window runs, forks and handoffs keep their MCP servers.
