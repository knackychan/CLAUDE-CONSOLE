"""A stand-in for codex.exe in tests: same flags, the documented JSONL shapes (codex-cli 0.162.1).

`exec [options] [resume <id> | fork <id>] -`: options stand before the subcommand (an option after it exits 2);
the prompt is read on stdin. Words in the prompt: HANDOFF-OK (a HANDOFF block ends the message), FAIL
(turn.failed), DENIED (a failed file_change), SLOW (3 s before the message), STOP-ASK (`STOP: which file?`), MAXTURNS ignored.
`--version` prints `codex-cli 0.0.0-fake`.
"""
import json
import sys
import time

from fake_claude import reply

VALUE_OPTIONS = ("-C", "-m", "-c", "-s")
FLAGS = ("--json", "--skip-git-repo-check")


def out(obj):
    print(json.dumps(obj), flush=True)


def main(argv):
    if argv[:1] == ["--version"]:
        print("codex-cli 0.0.0-fake")
        return 0
    if argv[:1] != ["exec"]:
        return 2
    rest, thread, sub = argv[1:], "th_fake", ""
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in VALUE_OPTIONS:
            if sub or i + 1 >= len(rest):
                return 2
            i += 2
        elif a in FLAGS:
            if sub:
                return 2
            i += 1
        elif a in ("resume", "fork") and not sub:
            if i + 1 >= len(rest):
                return 2
            sub, thread = a, rest[i + 1]
            i += 2
        elif a == "-":
            i += 1
            break
        else:
            return 2
    if i != len(rest):
        return 2
    prompt = sys.stdin.read()
    out({"type": "thread.started", "thread_id": thread})
    out({"type": "turn.started"})
    out({"type": "item.completed", "item": {"type": "command_execution", "command": "py -m unittest",
                                            "exit_code": 0}})
    if "SLOW" in prompt:
        time.sleep(3)
    if "DENIED" in prompt:
        out({"type": "item.completed", "item": {"type": "file_change", "status": "failed",
                                                "changes": [{"path": "PLAN.md", "kind": "update"}]}})
    out({"type": "item.completed", "item": {"type": "agent_message", "text": reply(prompt)}})
    if "FAIL" in prompt:
        out({"type": "turn.failed", "error": {"message": "fake failure"}})
        return 1
    out({"type": "turn.completed", "usage": {"input_tokens": 2000, "cached_input_tokens": 800,
                                             "output_tokens": 300, "reasoning_output_tokens": 100}})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
