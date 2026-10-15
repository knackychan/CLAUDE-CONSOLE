"""A stand-in for cmdc in tests: `-p <query> --output-format json --no-auto-update ...`.
Exits 2 without --no-auto-update. "MAXTURNS" in the query: exits 8 after the events, no result line.
Words: HANDOFF-OK, STOP-ASK as fake_codex; SLOW sleeps 3 s; FAIL exits 1. `-v` prints `Command Code v0.0.0-fake`.
"""
import json
import sys
import time

from fake_claude import reply

VALUE_OPTIONS = ("-p", "--output-format", "-m", "--effort", "--max-turns", "--permission-mode", "--session",
                 "-r", "-n")
FLAGS = ("--no-auto-update", "--skip-onboarding", "--no-skills", "--fork-session")


def out(obj):
    print(json.dumps(obj), flush=True)


def main(argv):
    if "--no-auto-update" not in argv:
        return 2
    if "-v" in argv:
        print("Command Code v0.0.0-fake")
        return 0
    opts, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if a in VALUE_OPTIONS:
            if i + 1 >= len(argv):
                return 2
            opts[a] = argv[i + 1]
            i += 2
        elif a in FLAGS:
            opts[a] = True
            i += 1
        else:
            return 2
    query = opts.get("-p")
    if query is None:
        return 2
    sid = opts.get("--session") or opts.get("-r") or "cmd_fake"
    out({"event": "start", "session_id": sid})
    out({"event": "tool", "name": "read", "input": "calc.py"})
    if "SLOW" in query:
        time.sleep(3)
    text = reply(query)
    out({"event": "assistant", "text": text})
    if "MAXTURNS" in query:
        return 8
    if "FAIL" in query:
        return 1
    out({"type": "result", "result": text, "usage": {"input_tokens": 500, "output_tokens": 100}})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
