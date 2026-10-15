"""Add (or remove) the Claude Console hooks in every CLI's config file.

Fred runs this himself (Claude cannot edit its own settings):
    py install_hooks.py                                   show what would be added (Claude Code)
    py install_hooks.py --harness codex,cmd,opencode      show what would be added there
    py install_hooks.py --harness all --write             back up each file, then add the hooks
    py install_hooks.py --harness all --remove            back up each file, then remove them
    --python <exe>                                        the interpreter the hook runs with (default: this one)
Running --write twice changes nothing the second time. The other CLIs' hooks must be trusted once by Fred
(Codex `/hooks`; Command Code asks when it starts): no hook writes another CLI's trust state.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "SubagentStart", "SubagentStop",
          "PermissionDenied", "Stop", "StopFailure", "PostCompact", "SessionEnd",
          "InstructionsLoaded"]
CODEX_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "SubagentStart", "SubagentStop", "Stop",
                "PostCompact", "SessionEnd", "Interrupt"]
CMD_EVENTS = ["SessionStart", "PreToolUse", "Stop"]
HARNESSES = ("claude", "codex", "cmd", "opencode")
SCRIPT = str(Path(__file__).resolve().parent / "cc_events.py")
PLUGIN_SRC = Path(__file__).resolve().parent / "hooks" / "opencode" / "claude-console.js"
PLUGIN_NAME = "claude-console"  # OpenCode 2.x loads a plugins/ directory's index.js (plan 37 README 5)
PLUGIN_PACKAGE = {"type": "module", "main": "index.js"}


def our_handler(python: str = None) -> dict:
    return {"type": "command", "command": python or sys.executable, "args": [SCRIPT], "async": True}


def _is_ours(group: dict) -> bool:
    return any(SCRIPT in (h.get("args") or []) for h in (group or {}).get("hooks", []))


def _is_ours_cmd(group: dict) -> bool:
    """True when a Codex or Command Code group holds our command (their handler has no `args`)."""
    return any(SCRIPT in str(h.get("command") or "") for h in (group or {}).get("hooks") or [])


def codex_handler(python: str) -> dict:
    cmd = f'"{python}" "{SCRIPT}" --harness codex'
    return {"type": "command", "command": cmd, "commandWindows": cmd, "async": True, "timeout": 5}


def cmd_handler(python: str) -> dict:
    return {"type": "command", "command": f'"{python}" "{SCRIPT}" --harness cmd', "timeout": 5}


def _merge(container: dict, events: list, handler: dict, ours) -> dict:
    """Our group appended to each event, any earlier one of ours dropped; every other group kept."""
    for event in events:
        groups = [g for g in container.get(event, []) if not ours(g)]
        container[event] = groups + [{"hooks": [handler]}]
    return container


def _drop(container: dict, ours) -> dict:
    """Every event without our group; an event left empty goes."""
    for event in list(container):
        groups = [g for g in container[event] if not ours(g)]
        if groups:
            container[event] = groups
        else:
            del container[event]
    return container


def merge(settings: dict, python: str = None) -> dict:
    _merge(settings.setdefault("hooks", {}), EVENTS, our_handler(python), _is_ours)
    return settings


def remove(settings: dict) -> dict:
    _drop(settings.get("hooks", {}), _is_ours)
    if not settings.get("hooks"):
        settings.pop("hooks", None)
    return settings


def merge_codex(data: dict, python: str) -> dict:
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    data["hooks"] = _merge(hooks, CODEX_EVENTS, codex_handler(python), _is_ours_cmd)
    return data


def remove_codex(data: dict) -> dict:
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        _drop(hooks, _is_ours_cmd)
        if not hooks:
            data.pop("hooks", None)
    return data


def merge_cmd(data: dict, python: str) -> dict:
    hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
    data["hooks"] = _merge(hooks, CMD_EVENTS, cmd_handler(python), _is_ours_cmd)
    return data


def remove_cmd(data: dict) -> dict:
    return remove_codex(data)


def plugin_text(python: str) -> str:
    """The plugin with its two constants filled: the paths as JS strings (backslashes escaped)."""
    text = PLUGIN_SRC.read_text(encoding="utf-8")
    return text.replace('"__PYTHON__"', json.dumps(python)).replace('"__SCRIPT__"', json.dumps(SCRIPT))


def _read_json(path: Path):
    """(data, error): the parsed file ({} when it is missing), or (None, message) when it does not parse."""
    if not path.exists():
        return {}, ""
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, ValueError) as exc:
        return None, f"{path}: {exc}"


def _save(path: Path, text: str, stamp: str) -> None:
    """Back the file up beside itself, then write through a temp file: a half-written config never lands."""
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-{stamp}")
        shutil.copy2(path, backup)
        print(f"backup: {backup}")
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")  # plan 34 F6: never half a settings.json
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    print(f"written to {path}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", default="claude", help="claude, codex, cmd, opencode, or all")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--settings", default=str(Path.home() / ".claude" / "settings.json"))
    parser.add_argument("--codex", default=str(Path.home() / ".codex" / "hooks.json"))
    parser.add_argument("--cmd", default=str(Path.home() / ".commandcode" / "settings.json"))
    parser.add_argument("--opencode-dir", default=str(Path.home() / ".config" / "opencode" / "plugins"))
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    names = [n.strip() for n in args.harness.split(",") if n.strip()]
    if "all" in names:
        names = list(HARNESSES)
    unknown = [n for n in names if n not in HARNESSES]
    if unknown:
        print(f"unknown harness: {', '.join(unknown)} (claude, codex, cmd, opencode, all)")
        return 2
    write, removing, stamp = bool(args.write or args.remove), args.remove, time.strftime("%Y%m%d-%H%M%S")
    for name in names:
        if name == "claude":
            path = Path(args.settings)
            data, error = _read_json(path)
            if error:
                print(error)
                return 1
            data = remove(data) if removing else merge(data, python=args.python)
            if not write:
                print(f"claude: {path}\n{json.dumps({'hooks': data.get('hooks', {})}, indent=2)}")
                continue
            _save(path, json.dumps(data, indent=2) + "\n", stamp)
        elif name == "opencode":
            dest = Path(args.opencode_dir) / PLUGIN_NAME
            if not write:
                print(f"opencode: would {'delete' if removing else 'write'} {dest}"
                      + ("" if removing else f"\n  {dest / 'index.js'}\n  {dest / 'package.json'}"))
                continue
            if removing:
                if dest.is_dir():  # our own copy: reproducible from the repo, nothing to back up
                    shutil.rmtree(dest)
                    print(f"removed {dest}")
                else:
                    print(f"nothing to remove: {dest}")
            else:
                dest.mkdir(parents=True, exist_ok=True)
                _save(dest / "index.js", plugin_text(args.python), stamp)
                _save(dest / "package.json", json.dumps(PLUGIN_PACKAGE, indent=2) + "\n", stamp)
        else:
            path = Path(args.codex if name == "codex" else args.cmd)
            data, error = _read_json(path)
            if error:
                print(error)
                return 1
            if name == "codex":
                data = remove_codex(data) if removing else merge_codex(data, python=args.python)
            else:
                data = remove_cmd(data) if removing else merge_cmd(data, python=args.python)
            if not write:
                print(f"{name}: {path}\n{json.dumps(data.get('hooks', {}), indent=2)}")
                continue
            _save(path, json.dumps(data, indent=2) + "\n", stamp)
            if not removing:
                print("Trust the new hooks: run codex, type /hooks and trust \"cc_events.py\""
                      if name == "codex" else "Trust the new hooks: run cmdc once and accept them")
    if not write:
        print("\n(dry run: nothing written; use --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
