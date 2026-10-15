"""Harness adapters: one module per CLI that can run a window step (README 3.3 of plans/05-harnesses).

An adapter module has NAME, EXE_NAMES, TIERS, CAPS, INTERRUPT, RESUME, HOOKS and the functions find_exe,
version_command, run_command, is_result, summary, chat, stop, terminal_command and env. A rung is
"<harness>:<model>" (a Claude rung has no prefix). `runs` builds the command through run_command, writes the
stdin bytes, ends the run on is_result, reads summary and chat from the stream and stops through stop.
"""
import importlib
import shutil
from pathlib import Path

from .. import claude_cli
from ..claude_cli import split_rung  # noqa: F401  (defined there: claude_cli does not import this package)


NAMES = ("claude", "codex", "opencode", "cmd")
REGISTRY = {}


def _load() -> None:
    """Fill REGISTRY from the sibling modules that exist (codex, opencode and cmd arrive in later tasks)."""
    for name in NAMES:
        if name in REGISTRY:
            continue
        try:
            REGISTRY[name] = importlib.import_module(f".{name}", __package__)
        except ModuleNotFoundError as exc:
            if exc.name != f"{__package__}.{name}":
                raise


def get(name: str):
    """The adapter module; KeyError for an unknown name."""
    if name not in REGISTRY:
        _load()
    return REGISTRY[name]


def rung(harness: str, model: str) -> str:
    """The inverse of split_rung: a Claude rung has no prefix."""
    return model if harness == "claude" else f"{harness}:{model}"


def section(cfg: dict, name: str) -> dict:
    found = (cfg.get("harnesses") or {}).get(name)
    return found if isinstance(found, dict) and found else {"on": name == "claude", "exe": ""}


def tiers_of(cfg: dict, name: str) -> tuple:
    return get(name).TIERS


def models_of(cfg: dict, name: str) -> dict:
    """model -> tier from models.json (cfg["models"]), without what the adapter may not hold; never raises."""
    try:
        tiers = tiers_of(cfg, name)
    except KeyError:
        return {}
    models = (cfg.get("models") or {}).get(name)
    if not isinstance(models, dict):
        return {}
    return {m: t for m, t in models.items() if t in tiers and t in claude_cli.MODELS}


def is_on(cfg: dict, name: str) -> bool:
    return section(cfg, name).get("on") is True


def find_exe(cfg: dict, name: str):
    return get(name).find_exe(cfg)


def which(names: tuple, exe: str = ""):
    """`exe` when it is given and exists, else the first of `names` that shutil.which finds."""
    if exe and Path(exe).exists():
        return exe
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


_load()
