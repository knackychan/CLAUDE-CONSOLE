"""Add (or remove) the Claude Console hooks in ~/.claude/settings.json.

Fred runs this himself (Claude cannot edit its own settings):
    py install_hooks.py            show what would be added
    py install_hooks.py --write    back up settings.json, then add the hooks
    py install_hooks.py --remove   back up settings.json, then remove them
    --python <exe>                 the interpreter the hook runs with (default: this one)
Running --write twice changes nothing the second time.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "SubagentStart", "SubagentStop",
          "PermissionDenied", "Stop", "StopFailure", "PostCompact", "SessionEnd",
          "InstructionsLoaded"]
SCRIPT = str(Path(__file__).resolve().parent / "cc_events.py")


def our_handler(python: str = None) -> dict:
    return {"type": "command", "command": python or sys.executable, "args": [SCRIPT], "async": True}


def _is_ours(group: dict) -> bool:
    return any(SCRIPT in (h.get("args") or []) for h in group.get("hooks", []))


def merge(settings: dict, python: str = None) -> dict:
    hooks = settings.setdefault("hooks", {})
    for event in EVENTS:
        groups = [g for g in hooks.get(event, []) if not _is_ours(g)]
        groups.append({"hooks": [our_handler(python)]})
        hooks[event] = groups
    return settings


def remove(settings: dict) -> dict:
    hooks = settings.get("hooks", {})
    for event in list(hooks):
        groups = [g for g in hooks[event] if not _is_ours(g)]
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    return settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--settings", default=str(Path.home() / ".claude" / "settings.json"))
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    path = Path(args.settings)
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    result = remove(settings) if args.remove else merge(settings, python=args.python)
    if not (args.write or args.remove):
        print(json.dumps({"hooks": {e: result["hooks"][e] for e in EVENTS}}, indent=2))
        print("\n(dry run: nothing written; use --write)")
        return 0
    if path.exists():
        backup = path.with_name(f"settings.json.bak-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(path, backup)
        print(f"backup: {backup}")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{'removed from' if args.remove else 'written to'} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
