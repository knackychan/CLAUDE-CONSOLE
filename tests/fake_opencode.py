"""A stand-in for opencode in tests: `run --standalone --format json -m <m> --file <path> [--session id [--fork]]
[--title t] <message>`. The prompt is read from the --file path (exit 2 when --file is missing).
Words: HANDOFF-OK, SLOW (3 s), STOP-ASK as fake_codex; FAIL exits 1 after the text. `--version`: 0.0.0-fake.
"""
import json
import sys
import time

from fake_claude import reply


def out(obj):
    print(json.dumps(obj), flush=True)


def main(argv):
    if argv[:1] == ["--version"]:
        print("0.0.0-fake")
        return 0
    if argv[:1] != ["run"] or len(argv) < 2:
        return 2
    rest, opts, i = argv[1:-1], {}, 0
    while i < len(rest):
        a = rest[i]
        if a in ("-m", "--file", "--session", "--title", "--format"):
            if i + 1 >= len(rest):
                return 2
            opts[a] = rest[i + 1]
            i += 2
        elif a in ("--standalone", "--auto", "--fork"):
            opts[a] = True
            i += 1
        else:
            return 2
    if "--file" not in opts:
        return 2
    try:
        prompt = open(opts["--file"], encoding="utf-8").read()
    except OSError:
        return 2
    out({"type": "session.created", "sessionID": opts.get("--session", "oc_fake")})
    out({"type": "tool", "tool": "read", "title": "calc.py"})
    if "SLOW" in prompt:
        time.sleep(3)
    out({"type": "text", "part": {"text": reply(prompt)}})
    if "FAIL" in prompt:
        return 1
    out({"type": "session.idle"})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
