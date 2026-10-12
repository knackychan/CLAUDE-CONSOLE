"""A stand-in for claude.exe in tests: same flags, same JSON shapes (recorded from Claude Code 2.1.288).

Prep (--json-schema): reads the prompt on stdin, prints one result object.
  "SLOW" in the request: waits 2 s first (Prep runs in the background).
  "THINK" / "BULK" in the request: the route rates reasoning / token volume high.
  "CHAIN" in the request: `steps` holds a scout and a code step (else `steps` is []).
  A request that starts with "Compact the handoff note" is the brief pass: it answers the brief schema
  (findings, files, questions, next); "LONG" in it gives 80 findings (over the word cap), "BROKEN"/"SLOW" as above.
Run (--input-format stream-json): per user message prints init / assistant / result.
  "SLOW" in the message: prints the assistant line, then waits for an interrupt or EOF.
  "DENY" in the message: the result carries one permission denial.
  The echo quotes the step prompt's own HANDOFF template lines ("> HANDOFF"), so a step has no block by default.
  "HANDOFF-OK" in the message: the assistant text ends with a valid HANDOFF block.
  "VERDICT-PASS" / "VERDICT-FAIL" in the message: it ends with a `VERDICT: PASS` / `VERDICT: FAIL x` line;
  VERDICT-FAIL also waits 1 s before the result line (a test appends the verdict event meanwhile).
  "STOP-ASK" in the message: the assistant text ends with `STOP: which file?`.
  "MAXTURNS" in the message: the result's subtype is `error_max_turns` (a step that hit its turn cap).
"""
import json
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
              "reason": "one-line fix with a clear spec", "steps": []}
    if "THINK" in raw:
        fields["route"]["reasoning"] = "high"
    if "BULK" in raw:
        fields["route"]["volume"] = "high"
    if "CHAIN" in raw:
        fields["steps"] = [{"kind": "scout", "goal": "find the add() callers"},
                           {"kind": "code", "goal": "fix add() and its test"}]
    if raw.startswith("Compact the handoff note"):  # the brief pass (console/compact.py)
        fields = {"findings": ["add() is in calc.py:2", "test_add covers it"], "files": ["calc.py"],
                  "questions": [], "next": "Fix add() and run the test"}
        if "LONG" in raw:
            fields["findings"] = [f"finding {i} says that this long line holds a good many words to pad the brief "
                                  "past its word cap" for i in range(80)]
        if "HUGE" in raw:
            fields["findings"] = ["word " * 450]
    if "BROKEN" in raw:
        print("not json")
        return 0
    if "SLOW" in raw:
        time.sleep(2)
    out({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.03,
         "num_turns": 5, "result": json.dumps(fields), "structured_output": fields})
    return 0


HANDOFF_BLOCK = ("HANDOFF\n## Findings\nadd() is in calc.py:2\n"
                 "test_add in tests/test_calc.py covers it and fails on a negative number\n"
                 "the callers in report.py and cli.py pass ints only\n## Files touched\n- (none)\n"
                 "## Open questions\n- (none)\n## Next\nGo on\nEND HANDOFF")  # longer than the fake brief


def reply(text):
    """The assistant text: the user message echoed, the step prompt's own HANDOFF template defanged (a quoted
    marker is not a block), then what the words in the message ask for."""
    lines = [("> " + line) if line.strip() in ("HANDOFF", "END HANDOFF") else line for line in text.splitlines()]
    body = "\n".join(lines)
    if "HANDOFF-OK" in text:
        body += "\n\n" + HANDOFF_BLOCK
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
