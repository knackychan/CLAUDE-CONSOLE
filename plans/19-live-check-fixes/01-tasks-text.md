# Task 1: Step goals kept, bold markers, the verify step's own text, caps named

> Contract: [README.md](README.md) 3.2. Findings A1 and A8 (three of its four points; the hold is Task 4).

**Files**
- Modify: `console/tasks.py`, `console/server.py` (`Hub._ended`: one argument), `tests/test_tasks.py`,
  `tests/test_server.py`
- With D2 (b) only: `console/prep_prompt.md`, `tests/test_prep.py`

## 1.1 Step goals (A1)

Evidence: `task.json` of `20261012-122014-915f`, steps 1 and 2: goals end in `...` at 200 characters
(`tasks.STEP_GOAL_MAX = 200`, applied in `plan_steps` through `redact.clip`). Prep's goals run 250 to 400.

- `tasks.STEP_GOAL_MAX = 1000`. `plan_steps` keeps `redact.clip(goal, STEP_GOAL_MAX)` (a goal is one line).
- `GOAL_MAX = 6000` (the task prompt) is unchanged.
- The task title stays an 80-character clip (`Hub.create_task`): it is a row name. The brief prompt stops using it
  (Task 2).

Test (`tests/test_tasks.py`, replace the 200 assertion at line 273 of `test_plan_steps_validates_and_appends_verify`):

```python
    def test_plan_steps_keeps_a_long_goal(self):
        goal = " ".join(["word"] * 180)  # 899 characters
        self.assertEqual(tasks.plan_steps([{"kind": "scout", "goal": goal}], 6)[0]["goal"], goal)
        cut = tasks.plan_steps([{"kind": "scout", "goal": "x" * 1500}], 6)[0]["goal"]
        self.assertEqual((len(cut), cut[-1]), (1000, "…"))
```

## 1.2 Bold or quoted HANDOFF markers (A8)

`parse_handoff` compares each line's marker as `_mark(line)`:

```python
def _mark(line: str) -> str:
    """A marker line as the model may dress it: `**HANDOFF**`, `` `END HANDOFF` ``, `### HANDOFF`."""
    return line.strip().strip("*_`#").strip()
```

Only the marker lines are loosened; the four headings keep the exact `## Heading` rule of `check_handoff`.

```python
    def test_parse_handoff_accepts_dressed_markers(self):
        body = "## Findings\nx\n## Files touched\n- (none)\n## Open questions\n- (none)\n## Next\ngo"
        for start, end in (("**HANDOFF**", "**END HANDOFF**"), ("`HANDOFF`", "`END HANDOFF`"),
                           ("### HANDOFF", "### END HANDOFF"), ("  HANDOFF ", "END HANDOFF  ")):
            self.assertEqual(tasks.parse_handoff(f"text\n{start}\n{body}\n{end}\n"), body, start)
        self.assertIsNone(tasks.parse_handoff("**HANDOFF block follows**\n" + body + "\nEND HANDOFF"))
```

## 1.3 The verify step's own text (A8)

`levers.VERIFY_TEXT` says "the work of this session" and names the Agent tool; a step runs with the Agent tool
disallowed and checks an earlier step. In practice the verify model put `VERDICT:` before the HANDOFF block
(memory file), which the step prompt's "nothing after it" asks for.

```python
VERIFY_STEP = ("Check the work of step $checked as the handoff note above describes it: read the files it "
               "touched and run the project's tests or checks once. Do not edit any file. Put one line "
               "`VERDICT: PASS` or `VERDICT: FAIL <shortest failing line>` in your final message, just before "
               "the HANDOFF block.")
```

`step_prompt` uses `Template(VERIFY_STEP).safe_substitute(checked=step["checked"] or step["n"] - 1)` for a
verify step instead of `levers.VERIFY_TEXT`. `levers.VERIFY_TEXT` (the session lever) is unchanged.

In `test_step_prompt_text`, replace the two `Check the work of this session.` assertions:

```python
        self.assertIn("\nCheck the work of step 2 as the handoff note above describes it", verify)
        self.assertIn("just before the HANDOFF block", verify)
        self.assertNotIn("this session", verify)
        self.assertNotIn("with the Agent tool", verify)
        self.assertNotIn("Check the work of step", code)
```

## 1.4 Caps named in the retry reason (A8)

`tasks.cap_reason(subtype: str, limits: dict) -> str`:

```python
def cap_reason(subtype: str, limits: dict) -> str:
    """Why a step's run stopped at one of its caps (the result subtypes of the Agent SDK), else ""."""
    limits = limits or {}
    if subtype == "error_max_turns":
        return f"it hit the turn cap ({limits.get('max_turns') or '?'} turns)"
    if subtype == "error_max_budget_usd":
        return f"it hit the step budget ({float(limits.get('budget') or 0):.2f} USD)"
    return ""
```

`on_step_ended(..., cap: str = "")`: when `not ok` and `cap`, the reason is `cap` (instead of `the run did not
finish cleanly`). `Hub._ended` passes `cap=tasks.cap_reason(subtype, meta.get("limits"))` (the run meta keeps the
limits, `runs.py` line 169).

```python
    def test_cap_reason_names_the_cap(self):
        self.assertEqual(tasks.cap_reason("error_max_turns", {"max_turns": 12}), "it hit the turn cap (12 turns)")
        self.assertEqual(tasks.cap_reason("error_max_budget_usd", {"budget": 3}), "it hit the step budget (3.00 USD)")
        self.assertEqual(tasks.cap_reason("success", {}), "")
        task = make(("code",))
        run(task, 1)
        action, _ = tasks.on_step_ended(task, ok=False, block_error="", verdict="", verdict_detail="", question="",
                                        now=2.0, cap="it hit the turn cap (12 turns)")
        self.assertEqual((action, task["why"]), ("retry", "it hit the turn cap (12 turns)"))
```

(`make` and `run` are the helpers `test_tasks.py` already has; use their real names if they differ.)

Server test (`TaskServerTest`): the fake claude needs a word for it. Add to `tests/fake_claude.py` (docstring
and run loop): `"MAXTURNS"` in the message makes the result `subtype` `error_max_turns` with `is_error` true.

```python
    def test_turn_cap_is_named_in_the_retry(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "MAXTURNS look"}])
        task = self.until(tid, lambda t: t["state"] == "stuck", "stuck after the retry")
        self.assertEqual(task["why"], "it hit the turn cap (? turns) (after one retry)")
```

(A scout step has no `--max-turns`, so the limit reads `?`; the test pins that a cap reason replaces the generic
one. If the executor finds `max_turns` is 0 rather than missing, the expected text is still `?` by the `or`.)

## 1.5 Prep prompt sentence (only with D2 b; skip with D2 a)

In `console/prep_prompt.md`, after the sentence ending `put the writing in a later one.`, add: `A request that
edits files gets at least its edit step in steps, even when your own reading already found the places: put them in
that step's goal. Leave steps [] only for a question, a lookup or a one-line change.` Test in `tests/test_prep.py`
`test_prompt_keeps_the_edit_step`: the sentence is in the prompt file. The type table is not touched.

## 1.6 Order (one commit per step)

1. 1.1 test, fails (goal cut at 200); constant; suite; commit `fix: step goals kept up to 1000 characters (plan 19 Task 1)`.
2. 1.2 test, fails; `_mark`; suite; commit.
3. 1.3 test change, fails; `VERIFY_STEP`; suite; commit.
4. 1.4 unit test, fails; `cap_reason`, `cap=`; fake word; server test, fails; `Hub._ended`; suite; commit.
5. With D2 b: 1.5; suite; commit.
6. PLAN.md History line for Task 1 (own line only), commit.
