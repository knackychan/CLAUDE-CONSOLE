"""Usage limits of the providers: which rungs share one subscription and how long a hit keeps them out of routing."""
import json
import re
import time
from pathlib import Path

from . import claude_cli

FILE = "limits.json"
WINDOWS = ((r"five[_ ]?hour|5[ -]?hour", 5 * 3600), (r"seven[_ ]?day|weekly|7[ -]?day", 7 * 86400),
           (r"daily|one[_ ]?day|1[ -]?day|24[ -]?hour", 86400), (r"(\d+)[ -]?hour", None))
TEXT = re.compile(r"usage limit|rate limit|hit your limit|quota|\b429\b", re.I)


def provider(rung: str) -> str:
    name, bare = claude_cli.split_rung(rung)
    if name == "opencode" and "/" in bare:
        return f"opencode:{bare.split('/', 1)[0]}"
    return name


def window_s(text: str):
    for pattern, seconds in WINDOWS:
        m = re.search(pattern, text or "", re.I)
        if m:
            return seconds if seconds else int(m.group(1)) * 3600
    return None


def until(hit: dict, now: float, default_s: int) -> float:
    if hit.get("until"):
        return float(hit["until"])
    return now + (hit.get("window_s") or default_s)


def read(folder, now: float = None) -> dict:
    now = time.time() if now is None else now
    try:
        data = json.loads((Path(folder) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and float(v.get("until") or 0) > now} \
        if isinstance(data, dict) else {}


def save(folder, data: dict) -> None:
    path = Path(folder) / FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(path)


def clock(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))
