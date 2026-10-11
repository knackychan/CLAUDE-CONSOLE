"""Where Claude Console keeps its files, and its config with defaults."""
import copy
import json
import os
import threading
from pathlib import Path

DEFAULTS = {
    "port": 47770,
    "retention_days": 14,
    "quiet_after_s": 180,
    "stall_after_s": 600,
    "stale_after_s": 1800,
    "writers_window_s": 600,
    "gauge_yellow_tokens": 150000,
    "gauge_red_tokens": 300000,
    "projects": [],
    "claude_exe": "",
    "prep_model": "haiku",
    "prep_timeout_s": 180,
    "default_model": "sonnet",
    "default_effort": "medium",
    "handoff_after_followups": 2,
    "rules_max_lines": 200,
    "rules_max_kb": 16,
    "delegate_after_reads": 10,
    "daily_budget_usd": 15,
    "cold_after_s": 3600,  # idle this long: both prompt-cache lifetimes (5 min, 1 h) are gone
    # USD per million tokens, API list prices (claude-api skill, 2026-10-06); fast mode costs 2x.
    # Haiku's higher price for prompts over 100K tokens is left out.
    "prices": {
        "fable": {"input": 10, "output": 50, "cache_read": 0.25, "cache_write_5m": 12.5, "cache_write_1h": 20},
        "opus": {"input": 4, "output": 20, "cache_read": 0.2, "cache_write_5m": 5, "cache_write_1h": 8},
        "sonnet": {"input": 2, "output": 10, "cache_read": 0.2, "cache_write_5m": 2.5, "cache_write_1h": 4},
        "haiku": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write_5m": 0.125, "cache_write_1h": 0.2},
    },
}


def home() -> Path:
    """The data folder: env CC_CONSOLE_HOME (tests), else ~/.claude/console."""
    env = os.environ.get("CC_CONSOLE_HOME")
    return Path(env) if env else Path.home() / ".claude" / "console"


def load_config() -> dict:
    """DEFAULTS overlaid with config.json; nested dicts merge one level deep."""
    cfg = copy.deepcopy(DEFAULTS)
    try:
        user = json.loads((home() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if not isinstance(user, dict):
        return cfg
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def add_project(folder: Path, project: str) -> None:
    """Add `project` to "projects" in <folder>/config.json; every other key stays as written.
    Raises ValueError when config.json exists but cannot be read (never overwrite Fred's file)."""
    path = Path(folder) / "config.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            raise ValueError(f"cannot read {path}: fix it by hand")
    else:
        data = copy.deepcopy(DEFAULTS)
    projects = data.get("projects") if isinstance(data.get("projects"), list) else []
    key = os.path.normcase(os.path.abspath(project))
    if all(os.path.normcase(os.path.abspath(p)) != key for p in projects if isinstance(p, str)):
        projects.append(project)
    data["projects"] = projects
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("config.json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


_WINDOW_LOCK = threading.Lock()  # the page (project) and the window (form, place) both save


def load_window(folder: Path) -> dict:
    """window.json: the window's last form, place, always-on-top, and the compose project."""
    try:
        data = json.loads((Path(folder) / "window.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_window(folder: Path, **fields) -> dict:
    """Merge `fields` into window.json (written whole, through a temp file)."""
    with _WINDOW_LOCK:
        data = dict(load_window(folder), **fields)
        path = Path(folder) / "window.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name("window.json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return data


def ensure_config() -> dict:
    """Write config.json with the defaults if it does not exist, then load it."""
    path = home() / "config.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULTS, indent=2) + "\n", encoding="utf-8")
    return load_config()
