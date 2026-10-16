"""A stand-in for claude.exe in tests: same flags, same JSON shapes (recorded from Claude Code 2.1.288).

Prep (--json-schema): reads the prompt on stdin, prints one result object.
  "SLOW" in the request: waits 2 s first (Prep runs in the background).
  "THINK" / "BULK" in the request: the route rates reasoning / token volume high.
  "CHAIN" in the request: `steps` holds a scout and a code step (else `steps` is []).
  A request that starts with "Compact the handoff note" is the brief pass: it answers the brief schema
  (goal, findings, files, troubleshooting, questions, next); "LONG" in it gives 80 findings (over the word cap), "BROKEN"/"SLOW" as above.
  A request that starts with "You review the rules" is the rules review: one remove proposal and a summary.
Run (--input-format stream-json): per user message prints init / assistant / result.
  "SLOW" in the message: prints the assistant line, then waits for an interrupt or EOF.
  "DENY" in the message: the result carries one permission denial.
  The echo quotes the step prompt's own HANDOFF template lines ("> HANDOFF"), so a step has no block by default.
  "HANDOFF-OK" in the message: the assistant text ends with a valid HANDOFF block.
  "HINT-OPUS" with it: the block's Next ends with `Next model: opus/high` (a hint for the step after).
  "LESSON" with it: the block's Next carries a `Lesson:` line (plan 22).
  "STEP-BLOCKED" with it: the block's Next carries `Status: blocked: the test runner is missing` (plan 38).
  "VERDICT-PASS" / "VERDICT-FAIL" in the message: it ends with a `VERDICT: PASS` / `VERDICT: FAIL x` line;
  VERDICT-FAIL also waits 1 s before the result line (a test appends the verdict event meanwhile).
  "STOP-ASK" in the message: the assistant text ends with `STOP: which file?`.
  "MAXTURNS" in the message: the result's subtype is `error_max_turns` (a step that hit its turn cap).
  "TROUBLE" with HANDOFF-OK: the block's Troubleshooting has one line (plan 23).
  "PLAN-OK" / "PLAN-SPLIT" / "PLAN-BAD" in a design step's message (it contains "You are the design step"): the reply
  carries a valid single plan (one `### Step N: code` per number listed after "each write step (") / a valid split
  plan with two parts / a plan without ## Acceptance, then the HANDOFF block (plan 24).
  "PLAN-GAP" in any other step's message: a Plan gap under Open questions and `STOP: Plan gap: ...`.
  "REPLAN-ASK" in the message with HANDOFF-OK: the block's Next ends with `Replan: a search step is needed first`.
  A request that starts with "Replan the rest of a task" is the replan pass: the remaining steps unchanged
  (`no change`), or with "REPLAN-ADD" in it one search step first (`search first`).
  "TESTS-OK" / "TESTS-FAIL" in the message: before the reply, a Bash tool_use `py -m unittest discover -s tests` and
  its tool_result (23 tests OK / one FAIL with is_error) (plan 23 facts).
"""
import json
import re
import sys
import time


def out(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else ""


def result(sid, subtype="success", denials=()):
    return {"type": "result", "subtype": subtype, "session_id": sid, "total_cost_usd": 0.01,
            "num_turns": 2, "permission_denials": list(denials), "is_error": subtype != "success"}


def prep():
    raw = sys.stdin.read()
    fields = {"goal": "Fix add() in calc.py", "where": "calc.py:2", "keep": "the signature",
              "done_when": "py -m unittest passes", "last_decisions": "", "question": "",
              "route": {"type": "mechanical", "reasoning": "low", "volume": "low", "model": "sonnet",
                        "effort": "low"},
              "reason": "one-line fix with a clear spec", "steps": [],
              "scouting": "calc.py:2 add(): the function to fix\ntests/test_calc.py test_add: the test that covers it"}
    if "SCOUT-LONG" in raw:  # plan 29: a scouting over prep.FINDINGS_CUT characters
        fields["scouting"] = "\n".join(f"file{i:02d}.py: read for the request, one line on why it matters" for i in range(30))
    if "THINK" in raw:
        fields["route"]["reasoning"] = "high"
    if "BULK" in raw:
        fields["route"]["volume"] = "high"
    if "CHAIN" in raw:
        fields["steps"] = [{"kind": "scout", "goal": "find the add() callers"},
                           {"kind": "code", "goal": "fix add() and its test"}]
    if raw.startswith("Compact the handoff note"):  # the brief pass (console/compact.py)
        fields = {"goal": "Fix add() in calc.py", "findings": ["add() is in calc.py:2", "test_add covers it"],
                  "files": ["calc.py"], "troubleshooting": [], "questions": [], "next": "Fix add() and run the test"}
        if "LONG" in raw:
            fields["findings"] = [f"finding {i} says that this long line holds a good many words to pad the brief "
                                  "past its word cap" for i in range(80)]
        if "HUGE" in raw:
            fields["findings"] = ["word " * 550]
    if raw.startswith("Replan the rest of a task"):  # the replan pass (console/replan.py)
        rest = raw.split("The remaining steps", 1)[-1].split("Answer with the JSON", 1)[0]
        kept = [{"kind": m.group(1), "goal": m.group(2)} for m in re.finditer(r"^- ([a-z]+): (.+)$", rest, re.M)]
        if "REPLAN-ADD" in raw:
            fields = {"steps": [{"kind": "search", "goal": "find the week bucket"}] + kept, "why": "search first"}
        else:
            fields = {"steps": kept, "why": "no change"}
    if raw.startswith("You review the rules"):  # the rules review (console/review.py)
        fields = {"proposals": [{"kind": "remove", "target": "Always write tests first", "text": "",
                                 "why": "derivable: the Commands section names the test command",
                                 "sources": ["Always write tests first"]}],
                  "summary": "CLAUDE.md is 12 lines, fine."}
    if "BROKEN" in raw:
        print("not json")
        return 0
    if "SLOW" in raw:
        time.sleep(2)
    out({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.03,
         "num_turns": 5, "result": json.dumps(fields), "structured_output": fields})
    return 0


HANDOFF_BLOCK = ("HANDOFF\n## Goal\nFix add() in calc.py; this step: find add() and its callers\n## Findings\n"
                 "add() is in calc.py:2\n"
                 "test_add in tests/test_calc.py covers it and fails on a negative number\n"
                 "the callers in report.py and cli.py pass ints only\n## Files touched\n- (none)\n"
                 "## Troubleshooting\n- (none)\n## Open questions\n- (none)\n## Next\nGo on\nEND HANDOFF")  # longer than the fake brief


TESTS_OK = "....\n----------------------------------------------------------------------\nRan 23 tests in 0.412s\n\nOK"
TESTS_FAIL = ("Exit code 1\n..F.\n======================================================================\n"
              "FAIL: test_add (tests.test_calc.CalcTest.test_add)\n------------------------------------------------"
              "----------------------\nTraceback (most recent call last):\n  File \"tests/test_calc.py\", line 6\n"
              "AssertionError: 3 != 4\n\nRan 4 tests in 0.010s\n\nFAILED (failures=1)")


PLAN_STEP = """### Step {n}: code
#### Files
- calc.py
#### Actions
1. `def add(a: int, b: int) -> int` in calc.py.
#### Tests
- tests/test_calc.py::test_add asserts add(1, 2) == 3
#### Done check
py -m unittest tests.test_calc -q prints OK
"""
PLAN_INDEX = """# Plan: calc
## Goal
add() in calc.py; done when the test passes.
## Decisions
- add lives in calc.py: the only module.
## Out of scope
- sub()
## Files
- calc.py (change): add()
## Steps
{steps}
## Acceptance
- tests pass
"""
PLAN_SPLIT = """# Plan: calc
## Goal
two modules.
## Decisions
- one part per module.
## Out of scope
- (none)
## Sub-plans
| # | Part | Kind | Owns | Depends on | Hard |
|---|---|---|---|---|---|
| 1 | Calc module | code | calc.py | - | no |
| 2 | Report module | code | report.py, calc.py | 1 | yes |
## Acceptance
- both suites pass
"""
PLAN_PART = """## Files
- {f}
## Actions
1. write {f}
## Tests
- tests/test_{f}.py::test_it
## Done check
py -m unittest -q
"""


def reply(text):
    """The assistant text: the user message echoed, the step prompt's own HANDOFF template defanged (a quoted
    marker is not a block), then what the words in the message ask for."""
    lines = [("> " + line) if line.strip() in ("HANDOFF", "END HANDOFF") else line for line in text.splitlines()]
    body = "\n".join(lines)
    if "HANDOFF-OK" in text:
        block = HANDOFF_BLOCK
        if "HINT-OPUS" in text:  # the note asks the next step up: `Next model:` inside the block's Next
            block = block.replace("\nGo on\n", "\nGo on\nNext model: opus/high\n")
        if "LESSON" in text:  # the step's Lesson line, inside the block's Next
            block = block.replace("\nGo on\n", "\nGo on\nLesson: fake claude teaches one thing\n")
        if "STEP-BLOCKED" in text:  # the step says it could not do its work (plan 38)
            block = block.replace("\nGo on\n", "\nGo on\nStatus: blocked: the test runner is missing\n")
        if "TROUBLE" in text:  # a dead end the brief must carry whole (plan 23)
            block = block.replace("## Troubleshooting\n- (none)", "## Troubleshooting\n- py -3.12 fails here: use py -3.14")
        body += "\n\n" + block
    design = "You are the design step" in text
    if design and "PLAN-OK" in text:
        m = re.search(r"each write step \(([\d, ]+)\)", text)
        ns = [int(x) for x in re.findall(r"\d+", m.group(1))] if m else [3]
        body += "\nPLAN\n" + PLAN_INDEX.format(steps="".join(PLAN_STEP.format(n=n) for n in ns)) + "END PLAN\n" + HANDOFF_BLOCK
    if design and "PLAN-SPLIT" in text:
        body += "\nPLAN\n" + PLAN_SPLIT + "END PLAN\nSUBPLAN 1 code Calc module\n" + PLAN_PART.format(f="calc.py") \
                + "END SUBPLAN\nSUBPLAN 2 code Report module\n" + PLAN_PART.format(f="report.py") + "END SUBPLAN\n" + HANDOFF_BLOCK
    if design and "PLAN-BAD" in text:
        body += "\nPLAN\n" + PLAN_INDEX.format(steps=PLAN_STEP.format(n=3)).replace("## Acceptance\n- tests pass\n", "") \
                + "END PLAN\n" + HANDOFF_BLOCK
    if not design and "PLAN-GAP" in text:
        body += "\n" + HANDOFF_BLOCK.replace("- (none)\n## Next", "- Plan gap: which file holds the ladder?\n## Next") \
                + "\nSTOP: Plan gap: which file holds the ladder?"
    if "REPLAN-ASK" in text and "HANDOFF-OK" in text:
        body += "\n" + HANDOFF_BLOCK.replace("## Next\nGo on", "## Next\nGo on. Replan: a search step is needed first")
    if "VERDICT-PASS" in text:
        body += "\nVERDICT: PASS"
    if "VERDICT-FAIL" in text:
        body += "\nVERDICT: FAIL x"
    if "STOP-ASK" in text:
        body += "\nSTOP: which file?"
    return body


def run():
    sid = arg("--session-id") or arg("--resume")
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("type") != "user":
            continue
        text = msg["message"]["content"]
        if isinstance(text, list):  # attached files: the text block, then one block per file
            text = text[0]["text"] + " +" + " +".join(b["type"] for b in text[1:])
        out({"type": "system", "subtype": "init", "session_id": sid, "cwd": "."})
        for word, ok in (("TESTS-OK", True), ("TESTS-FAIL", False)):  # plan 23: a test command and its tool result
            if word in text:
                out({"type": "assistant", "session_id": sid, "parent_tool_use_id": None, "message": {
                    "role": "assistant", "content": [{"type": "tool_use", "id": "toolu_test", "name": "Bash",
                                                      "input": {"command": "py -m unittest discover -s tests"}}]}})
                out({"type": "user", "session_id": sid, "parent_tool_use_id": None, "message": {
                    "role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_test",
                                                 "content": TESTS_OK if ok else TESTS_FAIL, "is_error": not ok}]}})
        out({"type": "assistant", "session_id": sid, "parent_tool_use_id": None, "message": {
            "role": "assistant", "content": [
                {"type": "text", "text": "echo: " + reply(text)},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "calc.py"}}]}})
        if "SLOW" in text:
            nxt = sys.stdin.readline()
            if nxt and json.loads(nxt).get("type") == "control_request":
                req = json.loads(nxt)
                out({"type": "control_response", "response": {"subtype": "success",
                                                              "request_id": req["request_id"]}})
                out({"type": "user", "session_id": sid, "parent_tool_use_id": None, "message": {
                    "role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]}})
                out(result(sid, "error_during_execution"))
                return 1
        denials = [{"tool_name": "Bash", "tool_input": {"command": "git push"}}] if "DENY" in text else []
        if "VERDICT-FAIL" in text:
            time.sleep(1)  # the test appends the verdict event while the run is still live, as the hook would
        out(result(sid, "error_max_turns" if "MAXTURNS" in text else "success", denials=denials))
    return 0


if __name__ == "__main__":
    sys.exit(prep() if "--json-schema" in sys.argv else run())
