"""Golden Prep routes (plan 22): three reference requests Prep must route the same way after every change to
the prep kind file (dotclaude/console/kinds/prep.md, plan 29). Fred's script: it calls the real claude three times (about $0.09). Not a unit test.

    py tests/golden_prep.py            runs in this repo's folder, prints one line per case, exits 1 on a miss
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from console import claude_cli, paths, prep  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = [  # (request, expected type): baseline, the real change, the noise case
    ("rename the variable s to sess in console/state.py State.state_of; nothing else", "mechanical"),
    ("change how install_hooks.py edits ~/.claude/settings.json so a missing file is created", "risky"),
    ("explain how Hub.levers decides when Escalate may run; no edits", "lookup"),
]


def main() -> int:
    cfg = paths.load_config()
    found = claude_cli.find_exe(cfg)
    if not found:
        print("claude.exe not found; set claude_exe in config.json")
        return 2
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:  # the cards go nowhere near ~/.claude/console
        for raw, want in CASES:
            card = prep.run_prep(cfg, Path(tmp), str(ROOT), raw, [found])
            got = card["route"]["type"]
            scouted = bool(str(card["fields"].get("scouting") or "").strip())  # plan 29: Prep says what it read
            mark = "ok  " if got == want and scouted else "MISS"
            bad += got != want or not scouted
            got += "" if scouted else " (no scouting)"
            print(f"{mark} {want:<10} got {got:<10} {card['route']['model']}/{card['route']['effort']}  ${card['cost']:.3f}  {raw}")
    print("golden: PASS" if not bad else f"golden: FAIL {bad} of {len(CASES)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
