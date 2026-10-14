# Task 1: The six-heading HANDOFF block, the step prompt, the skill

> Contract: [README.md](README.md) 3.2, 3.5, 3.6 (the tools column), 3.12. Decisions D3 (the RULES tools), D4 (the
> `Next model:` wording). Run in the scratch copy: the code below is the final code. No commit at the end of this
> task: Task 2 ends with the commit of both (a four-heading brief fails the six-heading check, so the two land
> together).

**Files**
- Modify: `console/tasks.py` (`RULES` tools, `HEADINGS`, new `OLD_HEADINGS`, `READ_CAPPED`, `PROMPT_GOAL_MAX`,
  `LESSONS_IN_PROMPT`, `FIRST_STEP`; `check_handoff`, new `_check_headings`; new `facts_file`, `write_facts`,
  `read_facts`; `clear`; new `_LESSON_LINE`, `lessons_for`, `received`, `prompt_goal`; `step_prompt`)
- Modify: `console/step_prompt.md` (whole file below)
- Modify: `console/brief.py` (`build("next")`)
- Modify: `dotclaude/skills/session-handoff/SKILL.md` (steps 6 and 7, the Done line)
- Modify: `tests/fake_claude.py` (the block, `TROUBLE`, `TESTS-OK` / `TESTS-FAIL`, the brief answer: all of plan 23's
  words in one edit; Tasks 2 and 3 use them)
- Modify: `tests/test_tasks.py`, `tests/test_brief.py`, `tests/test_dotclaude.py`

**Lands on** plan 24 Task 1: `tasks.step_prompt` already takes `special`, `plan`, `part` and `step_prompt.md` already
has `$plan` and `$part`; keep them where the file below has them. Plan 24's test
`test_step_prompt_carries_the_plan_and_the_part` anchors on "Handoff note of the previous step": change that anchor
to "What the earlier steps left you:" (the only change to that test). Plan 24 also added `"replan": ("haiku", "low",
"")` to `RULES`: it keeps `""` (no session), and the D3 test below skips it.

**Lands on** plan 24 Task 2: `replan.note_block` writes the four old headings. Replace its `return` with

```python
    goal = redact.clip(task.get("goal") or task["title"], 300)
    return ("## Goal\n" + goal + "\n## Findings\n" + (r.get("why") or "no change") + "\n## Files touched\n- (none)\n"
            "## Troubleshooting\n- (none)\n## Open questions\n- (none)\n## Next\nSteps before:\n" + before
            + "\nSteps after:\n" + after)
```

(`redact` is imported in replan.py already; if not, add it to the `from . import` line.) Plan 24's
`test_note_block_lists_before_and_after` (or the test that calls `note_block`) gains
`self.assertEqual(tasks.check_handoff(note), "")`.

**Lands on** plan 5 README section 5: the rule line "The Agent tool is not available here" and the `Next model:
<haiku|sonnet|opus>` wording, which plan 5 left for this plan, are replaced below.

## 1.1 `console/tasks.py`

The diff against today's code (plan 24's `special`, `plan`, `part` are part of it here because plan 24 is not placed
in the scratch copy; with plan 24 placed, those lines are already in place):

```diff
diff --git a/console/tasks.py b/console/tasks.py
index fbdab4d..4a99e1b 100644
--- a/console/tasks.py
+++ b/console/tasks.py
@@ -21,23 +21,28 @@ from . import claude_cli, levers, redact, routing
 RULES = {  # kind -> (model, effort, --tools list; "" = the default set). verify and fix are computed.
     "scout": ("haiku", "low", "Read,Grep,Glob"),
     "search": ("haiku", "low", "Read,Grep,Glob,WebFetch,WebSearch"),
-    "draft": ("haiku", "low", ""),
-    "proofread": ("haiku", "low", ""),
-    "edit": ("haiku", "low", ""),
-    "code": ("sonnet", "medium", ""),
-    "document": ("sonnet", "medium", ""),
+    "draft": ("haiku", "low", "Read,Edit,Write,Grep,Glob"),  # plan 23 (D3): an explicit list on every kind
+    "proofread": ("haiku", "low", "Read,Edit,Write,Grep,Glob"),
+    "edit": ("haiku", "low", "Read,Edit,Write,Grep,Glob"),
+    "code": ("sonnet", "medium", "Bash,Read,Edit,Write,Grep,Glob"),
+    "document": ("sonnet", "medium", "Read,Edit,Write,Grep,Glob"),
     "explain": ("sonnet", "medium", "Read,Grep,Glob"),
-    "debug": ("sonnet", "high", ""),
+    "debug": ("sonnet", "high", "Bash,Read,Edit,Write,Grep,Glob"),
     "test": ("haiku", "low", "Bash,Read,Grep,Glob"),
     "design": ("opus", "high", "Read,Grep,Glob,WebFetch,WebSearch"),
     "verify": ("", "", "Bash,Read,Grep,Glob"),
-    "fix": ("", "", ""),
+    "fix": ("", "", "Bash,Read,Edit,Write,Grep,Glob"),
 }
 KINDS = tuple(RULES)
 PREP_KINDS = tuple(k for k in KINDS if k not in ("verify", "fix"))  # what Prep may propose
 EDIT_KINDS = frozenset({"edit", "code", "debug", "document", "draft"})  # a verify follows the last of them
 DISALLOW = ("Agent",)
-HEADINGS = ("## Findings", "## Files touched", "## Open questions", "## Next")
+HEADINGS = ("## Goal", "## Findings", "## Files touched", "## Troubleshooting", "## Open questions", "## Next")
+OLD_HEADINGS = ("## Findings", "## Files touched", "## Open questions", "## Next")  # a note from before plan 23
+READ_CAPPED = ("scout", "search")  # kinds whose run gets --max-turns read_max_turns (plan 23)
+PROMPT_GOAL_MAX = 600  # the goal in a step prompt after step 1: every handoff carries its Goal heading (plan 23)
+LESSONS_IN_PROMPT = 5  # the newest lessons of the step's own kind that ride in its prompt (plan 23)
+FIRST_STEP = "This is the first step: there is no handoff note yet."
 MARK_START, MARK_END = "HANDOFF", "END HANDOFF"
 NOTE_MAX = 20 * 1024
 GOAL_MAX = 6000
@@ -177,19 +182,29 @@ def note_state(task: dict, s: dict, live: str = "") -> str:
     return "ready" if step(task, s["n"] + 1)["state"] == "planned" else "sent"
 
 
-def check_handoff(block: str) -> str:
-    """"" when the four headings stand on their own lines in order and Findings has text; else the reason."""
+def check_handoff(block: str, old_ok: bool = False) -> str:
+    """"" when the six headings stand on their own lines in order and Goal and Findings have text; else the reason.
+    `old_ok`: a four-heading note from before plan 23 (an old task folder) passes too; only read paths pass it."""
     lines = str(block or "").splitlines()
+    if old_ok and not any(line.strip() in ("## Goal", "## Troubleshooting") for line in lines):
+        return _check_headings(lines, OLD_HEADINGS)
+    return _check_headings(lines, HEADINGS)
+
+
+def _check_headings(lines: list, headings: tuple) -> str:
     at = []
-    for heading in HEADINGS:
+    for heading in headings:
         found = [i for i, line in enumerate(lines) if line.strip() == heading]
         if not found:
             return f"missing: {heading}"
         at.append(found[0])
     if at != sorted(at):
         return "headings out of order"
-    if not any(line.strip() for line in lines[at[0] + 1:at[1]]):
-        return "Findings is empty"
+    for heading in ("## Goal", "## Findings"):
+        if heading in headings:
+            i = headings.index(heading)
+            if not any(line.strip() for line in lines[at[i] + 1:at[i + 1]]):
+                return f"{heading[3:]} is empty"
     return ""
 
 
@@ -244,6 +259,11 @@ def handoff_file(task: dict, step: dict) -> str:
     return f"steps/{step['n']:02d}-handoff.md"
 
 
+def facts_file(task: dict, step: dict) -> str:
+    """The facts the service read when the step ended (git and its last test command): never compacted."""
+    return f"steps/{step['n']:02d}-{step['kind']}.facts.md"
+
+
 def brief_file(task: dict, step: dict) -> str:
     """The compacted note the next step reads (compact.py)."""
     return f"steps/{step['n']:02d}-{step['kind']}.brief.md"
@@ -633,6 +653,22 @@ def write_brief(home, task: dict, step: dict, text: str) -> str:
     return rel
 
 
+def write_facts(home, task: dict, step: dict, text: str) -> str:
+    """The facts text of `step` (facts.text), masked; returns the relative name."""
+    rel = facts_file(task, step)
+    path = folder(home, task["id"]) / rel
+    path.parent.mkdir(parents=True, exist_ok=True)
+    path.write_text(redact.mask(text), encoding="utf-8")
+    return rel
+
+
+def read_facts(home, task: dict, n: int) -> str:
+    try:
+        return (folder(home, task["id"]) / facts_file(task, step(task, n))).read_text(encoding="utf-8")
+    except (KeyError, OSError):
+        return ""
+
+
 def prune(home, days: float, now: float = None) -> list:
     """Remove the task folders of `done`, `stopped`, `stuck` and `handed` tasks whose task.json is older than `days`."""
     cutoff = (time.time() if now is None else now) - days * 86400
@@ -662,7 +698,8 @@ def clear(home, task: dict, keep_last: bool = True) -> list:
     if keep_last:
         last = step(task, task["last_good"]) if task["last_good"] else None
         keep = note_file(task, last) if last else ""
-        kept = {keep, brief_file(task, last) if last else "", task.get("handoff_note") or ""}
+        kept = {keep, brief_file(task, last) if last else "", facts_file(task, last) if last else "",
+                task.get("handoff_note") or ""}
         for path in sorted((root / "steps").glob("*.md")):
             if f"steps/{path.name}" not in kept:
                 path.unlink(missing_ok=True)
@@ -687,13 +724,48 @@ def _fix_text(task: dict, s: dict) -> str:
     return levers.escalate_text(before["verdict_detail"] if before else "", *route)
 
 
-def step_prompt(task: dict, step: dict, prev_note: str, retry_reason: str = "") -> str:
+_LESSON_LINE = re.compile(r"^- (\d{4}-\d\d-\d\d) - .*? - ([a-z]+): (.+)$")
+
+
+def lessons_for(lines, kind: str, limit: int = LESSONS_IN_PROMPT) -> list:
+    """The lessons a step of `kind` reads: lessons.md lines (levers.read_lessons, one project) whose kind is the
+    step's own, newest last, at most `limit`, as `<day>: <sentence>`. A chat's lesson (`chat`) reaches no step."""
+    out = []
+    for line in lines or ():
+        m = _LESSON_LINE.match(str(line).strip())
+        if m and m.group(2) == kind:
+            out.append(f"{m.group(1)}: {m.group(3)}")
+    return out[-limit:] if limit > 0 else []
+
+
+def received(prev_note: str, facts: str = "") -> str:
+    """What the earlier steps left a step: the previous brief, then the facts the service read (never compacted)."""
+    if not prev_note:
+        return FIRST_STEP
+    if not facts:
+        return prev_note
+    return f"{prev_note}\n\nFacts the service read when that step ended (git and its last test run, not compacted):\n{facts}"
+
+
+def prompt_goal(task: dict, step: dict) -> str:
+    """The goal as a step prompt carries it: whole (up to GOAL_MAX) for step 1, which has no handoff yet; cut to
+    PROMPT_GOAL_MAX characters for every later step, whose handoff restates it under ## Goal."""
+    goal = str(task.get("goal", ""))[:GOAL_MAX]
+    if step["n"] == 1 or len(goal) <= PROMPT_GOAL_MAX:
+        return goal
+    return goal[:PROMPT_GOAL_MAX - 1].rstrip() + "…"
+
+
+def step_prompt(task: dict, step: dict, prev_note: str, retry_reason: str = "", special: str = "",
+                plan: str = "", part: str = "", facts: str = "", lessons=()) -> str:
     kind = step["kind"]
-    special = (Template(VERIFY_STEP).safe_substitute(checked=step["checked"] or step["n"] - 1) if kind == "verify"
-               else _fix_text(task, step) if kind == "fix" else "")
+    special = special or (Template(VERIFY_STEP).safe_substitute(checked=step["checked"] or step["n"] - 1)
+                          if kind == "verify" else _fix_text(task, step) if kind == "fix" else "")
     retry = (f"Your earlier attempt at this step ended without a handoff: {retry_reason}. "
-             "Start again from the note above.") if retry_reason else ""
+             "Start again from the handoff below.") if retry_reason else ""
+    taught = (f"Lessons from earlier {kind} steps in this project (use one only where it applies):\n"
+              + "\n".join(f"- {line}" for line in lessons)) if lessons else ""
     return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
-        title=task["title"], goal=str(task.get("goal", ""))[:GOAL_MAX], n=step["n"], m=len(task["steps"]),
-        kind=kind, step_goal=step["goal"], special=special, retry=retry,
-        prev=prev_note or "This is the first step: there is no handoff note yet.")
+        title=task["title"], goal=prompt_goal(task, step), n=step["n"], m=len(task["steps"]),
+        kind=kind, step_goal=step["goal"], special=special, retry=retry, plan=plan, part=part,
+        lessons=taught, prev=received(prev_note, facts))
```

Notes the executor must not change:
- `check_handoff`'s reasons keep today's words; `Goal is empty` is new and comes before `Findings is empty`.
- `old_ok` checks the four old headings only when neither `## Goal` nor `## Troubleshooting` stands in the block.
- `prompt_goal` cuts at `PROMPT_GOAL_MAX - 1` characters, strips the right end, adds `…` (one character).
- `lessons_for` parses `levers.lesson_line`'s shape `- <day> - <project> - <kind>: <sentence>`; the project part may
  hold ` - ` (the regex is non-greedy up to the last ` - <kind>: `).
- `RULES` tools: D3 (a). With D3 (b) the six edit-kind rows keep `""` and the RulesTest rows below keep theirs.

## 1.2 `console/step_prompt.md` (the whole file after this task)

```text
You run one step of a task that Claude Console drives as a chain of separate runs. Earlier steps ran in other
sessions; what they found reaches you only through the handoff below. Later steps will see only your handoff.

Task: $title
$goal

Step $n of $m: $kind. $step_goal
$special
$retry
$plan

What the earlier steps left you:
$prev

$lessons
$part

Rules for this step:
- Do only this step. Do not start the next one, and do not run /session-handoff.
- Work alone: read what you need yourself, as little as the step needs, and do not hand the work to another agent.
- Do not edit files unless the step is edit, code, debug, document, draft or fix.
- End your final message with this block, filled in, and nothing after it:

HANDOFF
## Goal
The task goal in one line, then this step's part of it in one line.
## Findings
What you learned or did, in a few lines, with the file paths and line numbers that matter.
## Files touched
- path (what changed), or: - (none)
## Troubleshooting
- what failed and what fixed it, what you tried that does not work, a command that reproduces it, or: - (none)
## Open questions
- a question the next step or Fred must settle, or: - (none)
## Next
One line for the next step. Add `Next model: <tier>/<effort>` only when the next step needs more than planned: the
tier is haiku, sonnet or opus (cheapest to strongest, whatever CLI runs the step), the effort low, medium or high.
Add `Lesson: <one sentence>` only when something transferable surprised you, what you would tell someone starting
this kind of step tomorrow; most steps have none, so leave the line out rather than pad.
END HANDOFF
```

D4 (a) is the `Next model: <tier>/<effort>` paragraph; with (b) it would name `read|write|think` and need plan 18.

## 1.3 `console/brief.py`

```diff
diff --git a/console/brief.py b/console/brief.py
index 3b5bc75..6b5d836 100644
--- a/console/brief.py
+++ b/console/brief.py
@@ -1,6 +1,6 @@
 """A new-task brief built from the facts of a session, with no model call: what a fresh chat needs to
 take over a session whose context is too large to re-read (the cold-cache guard offers it)."""
-from . import levers, redact
+from . import levers, redact, tasks
 
 GOAL_MAX = 1200
 LAST_MAX = 1200
@@ -22,8 +22,9 @@ def build(kind: str, goal: str = "", last: str = "", files: list = (), verdict:
     """`kind` is "task" (hand the work over), "verify" (VERIFY_TEXT plus the facts), "handoff" (the facts on one
     line, the arguments of /session-handoff in a fresh chat) or "next" (the handoff note `last` of a chat that
     ran /session-handoff)."""
-    if kind == "next":  # the note keeps its lines: the starter prompt is a few of them
-        note = last.strip()
+    if kind == "next":  # the note keeps its lines; a skill note that ends with the HANDOFF block gives the block alone
+        block = tasks.parse_handoff(last)
+        note = (block if block is not None and not tasks.check_handoff(block, old_ok=True) else str(last or "")).strip()
         note = note if len(note) <= NOTE_MAX else note[: NOTE_MAX - 1] + "…"
         return "\n".join([NEXT_INTRO] + (["", "Handoff note:", note] if note else []))
     out = [levers.VERIFY_TEXT + " " + VERIFY_INTRO if kind == "verify" else
```

## 1.4 `dotclaude/skills/session-handoff/SKILL.md`

```diff
diff --git a/dotclaude/skills/session-handoff/SKILL.md b/dotclaude/skills/session-handoff/SKILL.md
index 5d59471..45d5709 100644
--- a/dotclaude/skills/session-handoff/SKILL.md
+++ b/dotclaude/skills/session-handoff/SKILL.md
@@ -31,16 +31,33 @@ Turns the useful part of a long chat into a few one-line records, so a fresh cha
 
      The project is the git root folder's name; the kind is `chat`.
 5. Remove or correct any older line this chat proved wrong (notes spread mistakes too).
-6. Print a starter prompt for the next chat, at most 5 lines: the project, the files to read first, the next step, the check that proves it is done.
-7. Tell the user the exit:
-   - default: `/clear <short-name>` (the name labels this chat in `/resume`), then paste the starter prompt;
+6. Tell the user the exit, in one line:
+   - default: `/clear <short-name>` (the name labels this chat in `/resume`), then paste the handoff block below;
    - only if the task must continue in this chat: `/compact focus on <the open step and the decisions above>`.
+7. End the message with the handoff block, the same six headings a Claude Console task step writes, so the next chat (or the console's Start next chat) reads it whole. Nothing comes after `END HANDOFF`. Keep it under 300 words; a heading with nothing to say gets `- (none)`:
+
+```
+HANDOFF
+## Goal
+<the task goal in one line, then what the next chat does of it in one line>
+## Findings
+- <what this chat established that the next one needs, one line each>
+## Files touched
+- <path>: <what changed, one line>
+## Troubleshooting
+- <a trap the next chat would hit again: the symptom, then what works>
+## Open questions
+- <only questions the next chat cannot answer from the files>
+## Next
+<the next step and the check that proves it is done; name a file to read first>
+END HANDOFF
+```
 
 ## Done looks like
 
 - Every decision from step 2 appears in exactly one place (PLAN.md History, a memory file, or a proposed CLAUDE.md line shown to the user).
 - `git diff` shows only one-line additions or corrections to History / memory files, no code changes.
-- The starter prompt names a file to read and a check to run.
+- The message ends with the HANDOFF block; its Next names a file to read and a check to run.
 - A lesson, when there was one, is one line in `~/.claude/console/lessons.md` and nowhere else.
 
 ## Never
```

Fred copies the folder to `~/.claude/skills/session-handoff/` himself (CLAUDE.md); the code never writes there.

## 1.5 `tests/fake_claude.py`

```diff
diff --git a/tests/fake_claude.py b/tests/fake_claude.py
index 28de0b2..b0f3b3e 100644
--- a/tests/fake_claude.py
+++ b/tests/fake_claude.py
@@ -5,7 +5,7 @@ Prep (--json-schema): reads the prompt on stdin, prints one result object.
   "THINK" / "BULK" in the request: the route rates reasoning / token volume high.
   "CHAIN" in the request: `steps` holds a scout and a code step (else `steps` is []).
   A request that starts with "Compact the handoff note" is the brief pass: it answers the brief schema
-  (findings, files, questions, next); "LONG" in it gives 80 findings (over the word cap), "BROKEN"/"SLOW" as above.
+  (goal, findings, files, troubleshooting, questions, next); "LONG" in it gives 80 findings (over the word cap), "BROKEN"/"SLOW" as above.
   A request that starts with "You review the rules" is the rules review: one remove proposal and a summary.
 Run (--input-format stream-json): per user message prints init / assistant / result.
   "SLOW" in the message: prints the assistant line, then waits for an interrupt or EOF.
@@ -18,6 +18,9 @@ Run (--input-format stream-json): per user message prints init / assistant / res
   VERDICT-FAIL also waits 1 s before the result line (a test appends the verdict event meanwhile).
   "STOP-ASK" in the message: the assistant text ends with `STOP: which file?`.
   "MAXTURNS" in the message: the result's subtype is `error_max_turns` (a step that hit its turn cap).
+  "TROUBLE" with HANDOFF-OK: the block's Troubleshooting has one line (plan 23).
+  "TESTS-OK" / "TESTS-FAIL" in the message: before the reply, a Bash tool_use `py -m unittest discover -s tests` and
+  its tool_result (23 tests OK / one FAIL with is_error) (plan 23 facts).
 """
 import json
 import sys
@@ -53,13 +56,13 @@ def prep():
         fields["steps"] = [{"kind": "scout", "goal": "find the add() callers"},
                            {"kind": "code", "goal": "fix add() and its test"}]
     if raw.startswith("Compact the handoff note"):  # the brief pass (console/compact.py)
-        fields = {"findings": ["add() is in calc.py:2", "test_add covers it"], "files": ["calc.py"],
-                  "questions": [], "next": "Fix add() and run the test"}
+        fields = {"goal": "Fix add() in calc.py", "findings": ["add() is in calc.py:2", "test_add covers it"],
+                  "files": ["calc.py"], "troubleshooting": [], "questions": [], "next": "Fix add() and run the test"}
         if "LONG" in raw:
             fields["findings"] = [f"finding {i} says that this long line holds a good many words to pad the brief "
                                   "past its word cap" for i in range(80)]
         if "HUGE" in raw:
-            fields["findings"] = ["word " * 450]
+            fields["findings"] = ["word " * 550]
     if raw.startswith("You review the rules"):  # the rules review (console/review.py)
         fields = {"proposals": [{"kind": "remove", "target": "Always write tests first", "text": "",
                                  "why": "derivable: the Commands section names the test command",
@@ -75,12 +78,21 @@ def prep():
     return 0
 
 
-HANDOFF_BLOCK = ("HANDOFF\n## Findings\nadd() is in calc.py:2\n"
+HANDOFF_BLOCK = ("HANDOFF\n## Goal\nFix add() in calc.py; this step: find add() and its callers\n## Findings\n"
+                 "add() is in calc.py:2\n"
                  "test_add in tests/test_calc.py covers it and fails on a negative number\n"
                  "the callers in report.py and cli.py pass ints only\n## Files touched\n- (none)\n"
+                 "## Troubleshooting\n- (none)\n"
                  "## Open questions\n- (none)\n## Next\nGo on\nEND HANDOFF")  # longer than the fake brief
 
 
+TESTS_OK = "....\n----------------------------------------------------------------------\nRan 23 tests in 0.412s\n\nOK"
+TESTS_FAIL = ("Exit code 1\n..F.\n======================================================================\n"
+              "FAIL: test_add (tests.test_calc.CalcTest.test_add)\n------------------------------------------------"
+              "----------------------\nTraceback (most recent call last):\n  File \"tests/test_calc.py\", line 6\n"
+              "AssertionError: 3 != 4\n\nRan 4 tests in 0.010s\n\nFAILED (failures=1)")
+
+
 def reply(text):
     """The assistant text: the user message echoed, the step prompt's own HANDOFF template defanged (a quoted
     marker is not a block), then what the words in the message ask for."""
@@ -92,6 +104,8 @@ def reply(text):
             block = block.replace("\nGo on\n", "\nGo on\nNext model: opus/high\n")
         if "LESSON" in text:  # the step's Lesson line, inside the block's Next
             block = block.replace("\nGo on\n", "\nGo on\nLesson: fake claude teaches one thing\n")
+        if "TROUBLE" in text:  # a dead end the brief must carry whole (plan 23)
+            block = block.replace("## Troubleshooting\n- (none)", "## Troubleshooting\n- py -3.12 fails here: use py -3.14")
         body += "\n\n" + block
     if "VERDICT-PASS" in text:
         body += "\nVERDICT: PASS"
@@ -112,6 +126,15 @@ def run():
         if isinstance(text, list):  # attached files: the text block, then one block per file
             text = text[0]["text"] + " +" + " +".join(b["type"] for b in text[1:])
         out({"type": "system", "subtype": "init", "session_id": sid, "cwd": "."})
+        for word, ok in (("TESTS-OK", True), ("TESTS-FAIL", False)):  # plan 23: a test command and its tool result
+            if word in text:
+                out({"type": "assistant", "session_id": sid, "parent_tool_use_id": None, "message": {
+                    "role": "assistant", "content": [{"type": "tool_use", "id": "toolu_test", "name": "Bash",
+                                                      "input": {"command": "py -m unittest discover -s tests"}}]}})
+                output = (TESTS_OK if ok else TESTS_FAIL)
+                out({"type": "user", "session_id": sid, "parent_tool_use_id": None, "message": {
+                    "role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_test",
+                                                 "content": output, "is_error": not ok}]}})
         out({"type": "assistant", "session_id": sid, "parent_tool_use_id": None, "message": {
             "role": "assistant", "content": [
                 {"type": "text", "text": "echo: " + reply(text)},
```

## 1.6 Tests

`tests/test_tasks.py` (65 -> 72 test methods):

```diff
diff --git a/tests/test_tasks.py b/tests/test_tasks.py
index ec699b8..d53a0fe 100644
--- a/tests/test_tasks.py
+++ b/tests/test_tasks.py
@@ -7,8 +7,10 @@ from unittest import mock
 
 from console import claude_cli, levers, prep, tasks
 
-GOOD = ("## Findings\nadd() is in calc.py:2\n## Files touched\n- calc.py (fixed add)\n"
-        "## Open questions\n- (none)\n## Next\nRun the tests")
+GOOD = ("## Goal\nAdd the export; this step: fix add()\n## Findings\nadd() is in calc.py:2\n## Files touched\n"
+        "- calc.py (fixed add)\n## Troubleshooting\n- (none)\n## Open questions\n- (none)\n## Next\nRun the tests")
+OLD = ("## Findings\nadd() is in calc.py:2\n## Files touched\n- calc.py (fixed add)\n"
+       "## Open questions\n- (none)\n## Next\nRun the tests")  # a note from before plan 23
 
 
 class RulesTest(unittest.TestCase):
@@ -26,25 +28,25 @@ class RulesTest(unittest.TestCase):
         self.rule("search", "haiku", "low", "Read,Grep,Glob,WebFetch,WebSearch")
 
     def test_rule_draft_haiku_low(self):
-        self.rule("draft", "haiku", "low", "")
+        self.rule("draft", "haiku", "low", "Read,Edit,Write,Grep,Glob")
 
     def test_rule_proofread_haiku_low(self):
-        self.rule("proofread", "haiku", "low", "")
+        self.rule("proofread", "haiku", "low", "Read,Edit,Write,Grep,Glob")
 
     def test_rule_edit_haiku_low(self):
-        self.rule("edit", "haiku", "low", "")
+        self.rule("edit", "haiku", "low", "Read,Edit,Write,Grep,Glob")
 
     def test_rule_code_sonnet_medium(self):
-        self.rule("code", "sonnet", "medium", "")
+        self.rule("code", "sonnet", "medium", "Bash,Read,Edit,Write,Grep,Glob")
 
     def test_rule_document_sonnet_medium(self):
-        self.rule("document", "sonnet", "medium", "")
+        self.rule("document", "sonnet", "medium", "Read,Edit,Write,Grep,Glob")
 
     def test_rule_explain_sonnet_medium(self):
         self.rule("explain", "sonnet", "medium", "Read,Grep,Glob")
 
     def test_rule_debug_sonnet_high(self):
-        self.rule("debug", "sonnet", "high", "")
+        self.rule("debug", "sonnet", "high", "Bash,Read,Edit,Write,Grep,Glob")
 
     def test_rule_test_haiku_low(self):
         self.rule("test", "haiku", "low", "Bash,Read,Grep,Glob")
@@ -54,7 +56,10 @@ class RulesTest(unittest.TestCase):
 
     def test_kind_sets_safe_id_and_disallow(self):
         self.assertEqual(tasks.RULES["verify"][2], "Bash,Read,Grep,Glob")
-        self.assertEqual(tasks.RULES["fix"][2], "")
+        self.assertEqual(tasks.RULES["fix"][2], "Bash,Read,Edit,Write,Grep,Glob")
+        self.assertTrue(all(tasks.RULES[k][2] for k in tasks.KINDS if k != "replan"),  # replan: no session
+                        "plan 23: every kind names its tools")
+        self.assertEqual(tasks.READ_CAPPED, ("scout", "search"))
         self.assertEqual(set(tasks.PREP_KINDS), set(tasks.RULES) - {"verify", "fix"})
         self.assertEqual(set(tasks.EDIT_KINDS), {"edit", "code", "debug", "document", "draft"})
         self.assertEqual(tasks.DISALLOW, ("Agent",))
@@ -212,6 +217,8 @@ class HandoffTest(unittest.TestCase):
 
     def test_check_handoff_reasons(self):
         self.assertEqual(tasks.check_handoff(GOOD), "")
+        self.assertEqual(tasks.HEADINGS, ("## Goal", "## Findings", "## Files touched", "## Troubleshooting",
+                                          "## Open questions", "## Next"))
         self.assertEqual(tasks.check_handoff(GOOD.replace("\n## Next\nRun the tests", "")), "missing: ## Next")
         swapped = GOOD.replace("## Files touched", "## TMP").replace("## Open questions", "## Files touched")
         swapped = swapped.replace("## TMP", "## Open questions")
@@ -222,6 +229,21 @@ class HandoffTest(unittest.TestCase):
         inline = GOOD.replace("## Next\n", "## Next: ")  # a heading must be a whole line
         self.assertEqual(tasks.check_handoff(inline), "missing: ## Next")
 
+    def test_check_handoff_needs_goal_and_troubleshooting(self):
+        self.assertEqual(tasks.check_handoff(GOOD.replace("## Goal\nAdd the export; this step: fix add()\n", "")),
+                         "missing: ## Goal")
+        self.assertEqual(tasks.check_handoff(GOOD.replace("## Troubleshooting\n- (none)\n", "")),
+                         "missing: ## Troubleshooting")
+        self.assertEqual(tasks.check_handoff(GOOD.replace("Add the export; this step: fix add()", "  ")), "Goal is empty")
+        self.assertEqual(tasks.check_handoff(OLD), "missing: ## Goal")  # a step's new block needs all six
+
+    def test_old_four_heading_note_checks_on_read_paths(self):
+        self.assertEqual(tasks.check_handoff(OLD, old_ok=True), "")
+        self.assertEqual(tasks.check_handoff(GOOD, old_ok=True), "")
+        self.assertEqual(tasks.check_handoff(OLD.replace("## Next\n", "## Next: "), old_ok=True), "missing: ## Next")
+        half = GOOD.replace("## Troubleshooting\n- (none)\n", "")  # a Goal heading: a new note, all six
+        self.assertEqual(tasks.check_handoff(half, old_ok=True), "missing: ## Troubleshooting")
+
     def test_next_hint(self):
         self.assertEqual(tasks.next_hint(GOOD + "\nNext model: sonnet/high"), ("sonnet", "high"))
         self.assertIsNone(tasks.next_hint(GOOD + "\nNext model: gpt/high"))
@@ -697,9 +719,12 @@ class ChainTest(unittest.TestCase):
             def files():
                 return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
 
-            self.assertEqual(len(files()), 6)
+            for n in (1, 3):
+                tasks.write_facts(home, task, tasks.step(task, n), f"facts {n}")
+            self.assertEqual(len(files()), 8)
             self.assertEqual(tasks.clear(home, task, keep_last=True), ["s1", "s2", "s3"])
-            self.assertEqual(files(), ["chain.jsonl", "prompt.md", "steps/03-search.md", "task.json"])
+            self.assertEqual(files(), ["chain.jsonl", "prompt.md", "steps/03-search.facts.md", "steps/03-search.md",
+                                       "task.json"])
             self.assertTrue(task["cleared"])
             self.assertEqual([s["handoff"] for s in task["steps"]], ["", "", "steps/03-search.md"])
             self.assertEqual(tasks.clear(home, task, keep_last=False), ["s1", "s2", "s3"])
@@ -748,13 +773,16 @@ class ChainTest(unittest.TestCase):
         task = make(("scout", "code"))
         run(task, 1)
         first = tasks.step_prompt(task, tasks.step(task, 1), "")
-        self.assertIn("This is the first step: there is no handoff note yet.", first)
+        self.assertIn("What the earlier steps left you:\nThis is the first step: there is no handoff note yet.", first)
         code = tasks.step_prompt(task, tasks.step(task, 2), "PREVIOUS NOTE TEXT\n## Findings\nkept")
         self.assertIn("Task: Add the export\nWrite the export and test it", code)
         self.assertIn("Step 2 of 3: code. goal of code", code)
-        self.assertIn("PREVIOUS NOTE TEXT\n## Findings\nkept", code)
-        self.assertIn("HANDOFF\n## Findings", code)
-        self.assertIn("END HANDOFF", code)
+        self.assertIn("What the earlier steps left you:\nPREVIOUS NOTE TEXT\n## Findings\nkept", code)
+        self.assertIn("HANDOFF\n## Goal\n", code)
+        start = code.index("\nHANDOFF\n")
+        heads = [code.index("\n" + h + "\n", start) for h in tasks.HEADINGS]
+        self.assertEqual(heads, sorted(heads))  # the template's six headings, in order
+        self.assertTrue(code.rstrip().endswith("END HANDOFF"))
         self.assertIn("`Lesson: <one sentence>`", code)
         self.assertIn("most steps have none", code)
         self.assertIn("do not run /session-handoff", code)
@@ -768,11 +796,73 @@ class ChainTest(unittest.TestCase):
         self.assertNotIn("Check the work of step", code)
         retry = tasks.step_prompt(task, tasks.step(task, 2), "note", "no HANDOFF block")
         self.assertIn("Your earlier attempt at this step ended without a handoff: no HANDOFF block. "
-                      "Start again from the note above.", retry)
+                      "Start again from the handoff below.", retry)
         self.assertNotIn("Your earlier attempt", code)
         long = dict(task, goal="g" * 9000)
         self.assertLess(len(tasks.step_prompt(long, tasks.step(long, 1), "")), 9000)
 
+    def test_step_prompt_is_harness_neutral(self):
+        task = make(("scout", "code"))
+        text = tasks.step_prompt(task, tasks.step(task, 2), "note")
+        self.assertNotIn("Agent tool", text)
+        self.assertIn("do not hand the work to another agent", text)
+        self.assertIn("`Next model: <tier>/<effort>`", text)
+        self.assertIn("tier is haiku, sonnet or opus", text.replace("\n", " "))
+        self.assertEqual(tasks.next_hint("Next model: opus/high"), ("opus", "high"))  # the hint still parses
+        self.assertNotIn(chr(0x2014), tasks.PROMPT_FILE.read_text(encoding="utf-8"))
+
+    def test_goal_is_cut_to_600_after_the_first_step(self):
+        task = make(("scout", "code"))
+        task["goal"] = "g" * 2000
+        self.assertEqual(tasks.PROMPT_GOAL_MAX, 600)
+        self.assertEqual(tasks.prompt_goal(task, tasks.step(task, 1)), "g" * 2000)  # step 1 has no handoff yet
+        later = tasks.prompt_goal(task, tasks.step(task, 2))
+        self.assertEqual((len(later), later[-1]), (600, "…"))
+        self.assertIn("\n" + later + "\n", tasks.step_prompt(task, tasks.step(task, 2), "note"))
+        task["goal"] = "short goal"
+        self.assertEqual(tasks.prompt_goal(task, tasks.step(task, 2)), "short goal")
+
+    def test_received_puts_the_facts_under_the_brief(self):
+        self.assertEqual(tasks.received("", "facts"), tasks.FIRST_STEP)
+        self.assertEqual(tasks.received("BRIEF", ""), "BRIEF")
+        both = tasks.received("BRIEF", "git diff --stat a..b")
+        self.assertTrue(both.startswith("BRIEF\n\nFacts the service read when that step ended"))
+        self.assertTrue(both.endswith("not compacted):\ngit diff --stat a..b"))
+        task = make(("scout", "code"))
+        text = tasks.step_prompt(task, tasks.step(task, 2), "BRIEF", facts="FACTS LINE")
+        self.assertLess(text.index("BRIEF"), text.index("FACTS LINE"))
+        self.assertLess(text.index("FACTS LINE"), text.index("Rules for this step:"))
+
+    def test_lessons_for_the_step_kind_only(self):
+        lines = ["- 2026-10-01 - APP - code: profile before optimizing",
+                 "- 2026-10-02 - APP - scout: grep the callers first",
+                 "- 2026-10-03 - APP - chat: a chat lesson reaches no step",
+                 "- 2026-10-04 - MY - APP - code: a project name with a dash still parses",
+                 "not a lesson line"]
+        self.assertEqual(tasks.lessons_for(lines, "code"), ["2026-10-01: profile before optimizing",
+                                                            "2026-10-04: a project name with a dash still parses"])
+        self.assertEqual(tasks.lessons_for(lines, "scout"), ["2026-10-02: grep the callers first"])
+        self.assertEqual(tasks.lessons_for(lines, "verify"), [])
+        many = [f"- 2026-10-{d:02d} - APP - code: lesson {d}" for d in range(1, 10)]
+        self.assertEqual(tasks.lessons_for(many, "code"), [f"2026-10-{d:02d}: lesson {d}" for d in range(5, 10)])
+        task = make(("scout", "code"))
+        text = tasks.step_prompt(task, tasks.step(task, 2), "note", lessons=tasks.lessons_for(lines, "code"))
+        self.assertIn("Lessons from earlier code steps in this project (use one only where it applies):\n"
+                      "- 2026-10-01: profile before optimizing\n", text)
+        self.assertLess(text.index("Lessons from"), text.index("Rules for this step:"))
+        self.assertNotIn("Lessons from", tasks.step_prompt(task, tasks.step(task, 2), "note"))
+
+    def test_facts_file_round_trip(self):
+        with tempfile.TemporaryDirectory() as home:
+            task = make(("scout", "code"))
+            one = tasks.step(task, 1)
+            self.assertEqual(tasks.facts_file(task, one), "steps/01-scout.facts.md")
+            self.assertEqual(tasks.read_facts(home, task, 1), "")
+            rel = tasks.write_facts(home, task, one, "Tests: py -m unittest token=abc123\nOK")
+            self.assertEqual(rel, "steps/01-scout.facts.md")
+            self.assertEqual(tasks.read_facts(home, task, 1), "Tests: py -m unittest token=***\nOK")
+            self.assertEqual(tasks.read_facts(home, task, 9), "")
+
 
 class NoteStateTest(unittest.TestCase):
     def test_live_note(self):
```

- RulesTest: the six edit-kind rows (D3); `test_kind_sets_safe_id_and_disallow` asserts every kind but `replan` names
  its tools and `READ_CAPPED`.
- HandoffTest: `test_check_handoff_reasons` pins `HEADINGS`; `test_check_handoff_needs_goal_and_troubleshooting`
  (`missing: ## Goal`, `missing: ## Troubleshooting`, `Goal is empty`, a four-heading note fails a step);
  `test_old_four_heading_note_checks_on_read_paths`.
- ChainTest: `clear` keeps the last facts file; the step prompt test anchors on "What the earlier steps left you:",
  the six template headings in order, `END HANDOFF` last, the retry line; new `test_step_prompt_is_harness_neutral`,
  `test_goal_is_cut_to_600_after_the_first_step`, `test_received_puts_the_facts_under_the_brief`,
  `test_lessons_for_the_step_kind_only`, `test_facts_file_round_trip` (masked: `token=abc123` -> `token=***`).

`tests/test_brief.py` (5 -> 6): `test_next_brief_of_a_skill_note_is_its_handoff_block`.

```diff
diff --git a/tests/test_brief.py b/tests/test_brief.py
index bb43978..782b001 100644
--- a/tests/test_brief.py
+++ b/tests/test_brief.py
@@ -27,6 +27,15 @@ class BriefTest(unittest.TestCase):
         self.assertEqual(brief.build("next"), brief.NEXT_INTRO)
         self.assertTrue(brief.build("next", last="x" * 5000).endswith("x…"))
 
+    def test_next_brief_of_a_skill_note_is_its_handoff_block(self):
+        block = ("HANDOFF\n## Goal\nShip plan 23.\n## Findings\n- the brief pass works\n## Files touched\n- (none)\n"
+                 "## Troubleshooting\n- (none)\n## Open questions\n- (none)\n## Next\nWrite the window task.\nEND HANDOFF")
+        note = "Done. Next session: /session-handoff resume\n\n" + block
+        text = brief.build("next", last=note)
+        self.assertIn("## Troubleshooting", text)
+        self.assertNotIn("Done. Next session", text)  # the block alone
+        self.assertIn("free text", brief.build("next", last="free text"))  # a note with no block keeps its lines
+
     def test_verify_brief_starts_with_the_verify_text(self):
         text = brief.build("verify", goal="g", files=["a.py"], plan=True)
         self.assertTrue(text.startswith(levers.VERIFY_TEXT))
```

`tests/test_dotclaude.py` (6 -> 7): `test_handoff_block_is_the_step_block` (the skill's example block parses, its
headings are `tasks.HEADINGS` in order, it passes `check_handoff`).

```diff
diff --git a/tests/test_dotclaude.py b/tests/test_dotclaude.py
index 7be756f..aab9aba 100644
--- a/tests/test_dotclaude.py
+++ b/tests/test_dotclaude.py
@@ -6,7 +6,7 @@ import unittest
 from pathlib import Path
 
 import cc_events
-from console import claude_cli, levers, paths, prep
+from console import claude_cli, levers, paths, prep, tasks
 
 ROOT = Path(__file__).resolve().parent.parent
 DOT = ROOT / "dotclaude"
@@ -77,6 +77,14 @@ class DotClaudeTest(unittest.TestCase):
         self.assertEqual(levers.lesson_line("CLAUDE CONSOLE", "chat", body, day), example)
         self.assertIn("most chats teach nothing", text)
 
+    def test_handoff_block_is_the_step_block(self):
+        text = FILES["session-handoff"].read_text(encoding="utf-8")
+        block = tasks.parse_handoff(text)
+        self.assertIsNotNone(block)
+        self.assertEqual([line for line in block.splitlines() if line.startswith("## ")], list(tasks.HEADINGS))
+        self.assertEqual(tasks.check_handoff(block), "")  # the template the skill shows passes the step check
+        self.assertIn("Nothing comes after `END HANDOFF`", text)
+
     def test_route_model_ignores_old_misses(self):
         text = FILES["route-model"].read_text(encoding="utf-8")
         self.assertIn("older than 14 days", text)
```

## 1.7 Steps

1. Write the test changes of 1.6. Run `py -m unittest tests.test_tasks tests.test_brief tests.test_dotclaude`: the new
   ones fail.
2. `console/tasks.py` (1.1), `console/step_prompt.md` (1.2), `console/brief.py` (1.3), the skill (1.4), the fake (1.5).
3. The three modules pass. The full suite is not green yet (the brief pass still writes four headings): go on to
   Task 2 without a commit.

This task adds 9 test methods (7 + 1 + 1); with Task 2's 5 the shared commit adds 14 (Linux scratch 326 -> 340).

**Drift guards**
- No other module defines a heading list; `compact` (Task 2) imports `tasks.HEADINGS`.
- `FIRST_STEP`'s text is today's ("This is the first step: there is no handoff note yet."): old tests and the window
  match it.
- The template stays the last thing in the prompt; `$part` sits before the rules, `$lessons` before `$part`.
