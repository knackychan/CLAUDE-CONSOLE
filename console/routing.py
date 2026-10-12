"""Demand routing: the route a task's demand calls for, decided in code from what Prep reports.
Heavy reasoning goes to opus/high; heavy token volume with light reasoning goes to haiku (sonnet when the
reasoning is medium); anything else keeps Prep's pick. The newest routing miss of the same task type is a
floor the route never goes under (Escalate wrote it: that route failed last time)."""
import re

from .claude_cli import EFFORTS, MODELS

LEVELS = ["low", "medium", "high"]
_START = re.compile(r" - ([a-z]+): .*next time start at (\w+)/(\w+)\.$")
_DATE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) ")


def parse(text: str):
    """"sonnet/medium" -> ("sonnet", "medium"); None when it is not a known route."""
    model, _, effort = str(text or "").partition("/")
    return (model, effort) if model in MODELS and effort in EFFORTS else None


def rank(route: tuple) -> tuple:
    return MODELS.index(route[0]), EFFORTS.index(route[1])


def by_demand(route: dict) -> tuple:
    """(model, effort) from Prep's route {type, model, effort, reasoning, volume}."""
    pick = route["model"], route["effort"]
    reasoning, volume = route.get("reasoning"), route.get("volume")
    if reasoning == "high":
        return (max(pick[0], "opus", key=MODELS.index),  # never under opus/high, keep fable or max
                max(pick[1], "high", key=EFFORTS.index))
    if volume == "high":
        return ("sonnet", "medium") if reasoning == "medium" else ("haiku", "low")
    return pick


def floor(misses, task_type: str):
    """The route the newest miss of `task_type` says to start at, or None."""
    for line in reversed(list(misses)):
        m = _START.search(line)
        if m and m.group(1) == task_type and m.group(2) in MODELS and m.group(3) in EFFORTS:
            return m.group(2), m.group(3)
    return None


def floors(misses) -> dict:
    """Every floor in the miss lines, the newest per type: {type: {"route": "opus/high", "date": "2026-10-12"}}.
    The Prep card shows them, so a step that starts above its rule is not a surprise."""
    out = {}
    for line in misses:
        m, d = _START.search(line), _DATE.match(line)
        if m and m.group(2) in MODELS and m.group(3) in EFFORTS:
            out[m.group(1)] = {"route": f"{m.group(2)}/{m.group(3)}", "date": d.group(1) if d else ""}
    return out


def pick(route: dict, misses=()) -> tuple:
    chosen = by_demand(route)
    low = floor(misses, route.get("type"))
    return low if low and rank(low) > rank(chosen) else chosen
