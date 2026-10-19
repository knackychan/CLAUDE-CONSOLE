"""Where Claude Console keeps its files, and its config with defaults."""
import copy
import getpass
import json
import os
import subprocess
import threading
from pathlib import Path

DEFAULTS = {
    "port": 47770,
    "user_name": "",  # plan 31: the person the prompts and the plan's Decisions name; "" reads "the user"
    "retention_days": 14,
    "quiet_after_s": 180,
    "stall_after_s": 600,
    "stale_after_s": 1800,
    "replied_for_s": 600,  # a plain reply shows as Replied this long after the turn ended, then as Idle
    "writers_window_s": 600,
    "gauge_yellow_tokens": 150000,
    "gauge_red_tokens": 300000,
    "projects": [],
    "claude_exe": "",
    "prep_model": "haiku",
    "prep_timeout_s": 180,
    "planner_model": "opus",  # plan 47 D4: the pass that reviews a Prep card's scope and writes its steps; Claude only
    "planner_timeout_s": 120,
    "planner_max_cost": 0.5,  # plan 47 D6: --max-budget-usd of one planner pass
    "default_model": "sonnet",
    "default_effort": "medium",
    "handoff_after_followups": 2,
    "rules_max_lines": 200,
    "rules_max_kb": 16,
    "delegate_after_reads": 10,
    "miss_floor_days": 14,  # plan 22: an older routing miss is history, not a floor
    "review_model": "haiku",  # plan 22: the rules review, read only
    "review_timeout_s": 180,
    "daily_budget_usd": 15,
    "cold_after_s": 3600,  # idle this long: both prompt-cache lifetimes (5 min, 1 h) are gone
    # plan 17, task chain: see plans/17-tasks/README.md section 4
    "task_retention_days": 0,  # plan 28 (D9): 0 keeps every task folder; runs/ and preps/ keep retention_days
    "task_step_budget_usd": 3,
    "task_max_steps": 6,
    "design_max_turns": 30,  # plan 24 D2: --max-turns of a design step on any rung
    "read_max_turns": 15,  # plan 23: --max-turns of a scout or search step
    "handoff_auto": False,  # plan 23 (D-5): hand off a window run whose turn ends in the red zone
    "plan_max_kb": 100,  # the plan files together; over it the task waits, nothing is cut
    "plan_max_parts": 6,
    "plan_hold": False,  # the task waits after the design step for Confirm
    "replan_auto": False,  # a replan proposal applies without Confirm
    "budget_warn_at": 0.8,  # plan 18: share of pace that marks a model over pace and holds a verify on it
    # plan 18: the job tiers; each step takes the emptiest model of its tier (README 3.2 of plans/18-fills)
    "tiers": {
        "think": [{"rung": "opus", "effort": "auto"}, {"rung": "codex:gpt-6-astra", "effort": "auto"},
                  {"rung": "opencode:opencode-go/kimi-k3", "effort": "auto"},
                  {"rung": "opencode:opencode-go/glm-5.3", "effort": "auto"},
                  {"rung": "claude-opus-4-8", "effort": "auto"}, {"rung": "fable", "effort": "auto"}],
        "write": [{"rung": "sonnet", "effort": "auto"}, {"rung": "codex:gpt-6.1-sol", "effort": "auto"},
                  {"rung": "codex:gpt-6-sol", "effort": "auto"}, {"rung": "opus", "effort": "auto"},
                  {"rung": "opencode:opencode-go/deepseek-v4.1-flash", "effort": "auto"},
                  {"rung": "cmd:deepseek/deepseek-v4.1-flash", "effort": "auto"}],
        "read": [{"rung": "haiku", "effort": "auto"}, {"rung": "codex:gpt-6-luna", "effort": "auto"},
                 {"rung": "opencode:opencode-go/deepseek-v4.1-flash", "effort": "auto"},
                 {"rung": "cmd:deepseek/deepseek-v4.1-flash", "effort": "auto"}],
    },
    "kinds": {},  # plan 26: kind -> {"rung": "auto" | rung, "effort": "auto" | effort}; absent keeps the code's rule
    "allowances": {},  # model key -> {"day_usd", "week_usd", "month_usd"}; a key without one has no allowance
    "balance_margin": 0.1,  # the previous step's rung stays while its share is this close to the lowest
    "cache_bonus": 0.1,  # taken off the previous rung's share while its prompt cache is warm (5 minutes)
    "month_start_day": 1,  # the billing day the month window starts on (1 to 28)
    "peak_hours": {},  # provider -> {"hours": "14-19", "add": 0.2}; off
    "ladder": {  # newest rung first per tier, the alias first
        "haiku": ["haiku", "claude-haiku-4-5"],
        "sonnet": ["sonnet", "claude-sonnet-4-6"],
        "opus": ["opus", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6"],
        "fable": ["fable"],
    },
    # plan 05: harness adapters (the models of each live in models.json)
    "harnesses": {
        "claude": {"on": True, "exe": ""},
        "codex": {"on": False, "exe": ""},
        "opencode": {"on": False, "exe": ""},
        "cmd": {"on": False, "exe": ""},
    },
    "step_timeout_s": 1800,  # ends a run of an adapter with no turn or spend cap
    "limit_cooldown_s": 3600,
    "effort_variant": {},  # OpenCode: {model: {effort: variant}}
    "storage_warn_mb": 500,
    "task_clear_on_done": True,
    "brief_on": True,  # the Haiku pass that compacts a step's note into the next step's brief
    "brief_model": "haiku",
    "brief_max_words": 500,
    "brief_timeout_s": 60,
    "handoff_on": True,  # plan 44 navigation: the Haiku pass that summarizes a whole task's saved digest for a follow-up
    "handoff_model": "haiku",
    "handoff_max_words": 800,
    "handoff_timeout_s": 90,
    # plan 44: the event-driven supervisor's own policy (backend). Numeric/rung keys ride the Models page whitelist;
    # supervisor_mode and supervisor_projects are enum/map, validated separately and never shown as numeric tuning.
    "supervisor_mode": "suggest",  # off, suggest or auto
    "supervisor_projects": {},  # normalized configured-project path -> off|suggest|auto
    "supervisor_model": "haiku",  # the Claude alias only: a supervisor pass never runs on opus/fable
    "supervisor_stuck_model": "sonnet",  # one sonnet pass on a stuck/stalled wake
    "supervisor_debounce_s": 20,
    "supervisor_parallel": 1,
    "supervisor_timeout_s": 90,
    "supervisor_stall_s": 1800,
    "supervisor_max_auto_steps": 3,
    "supervisor_max_retries": 1,
    "supervisor_work_usd": 5,
    "supervisor_task_usd": 0.50,
    "supervisor_day_usd": 2,
    # USD per million tokens, API list prices (claude-api skill, 2026-10-06); fast mode costs 2x.
    # Haiku's higher price for prompts over 100K tokens is left out.
    "prices": {
        "fable": {"input": 10, "output": 50, "cache_read": 0.25, "cache_write_5m": 12.5, "cache_write_1h": 20},
        "opus": {"input": 4, "output": 20, "cache_read": 0.2, "cache_write_5m": 5, "cache_write_1h": 8},
        "sonnet": {"input": 2, "output": 10, "cache_read": 0.2, "cache_write_5m": 2.5, "cache_write_1h": 4},
        "haiku": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write_5m": 0.125, "cache_write_1h": 0.2},
    },
}

HARNESSES = ("claude", "codex", "opencode", "cmd")  # equal to harness.NAMES (a test asserts it)

# models.json (plan 05 3.2b): per CLI, model id -> tier, in the order the window lists them.
MODELS_DEFAULT = {
    "claude": {"opus": "opus", "sonnet": "sonnet", "haiku": "haiku", "fable": "fable",
               "claude-opus-4-8": "opus", "claude-opus-4-7": "opus", "claude-sonnet-4-6": "sonnet",
               "claude-haiku-4-5": "haiku"},
    "codex": {"gpt-6-astra": "opus", "gpt-6.1-sol": "sonnet", "gpt-6-sol": "sonnet", "gpt-6-luna": "haiku"},
    "opencode": {"opencode-go/deepseek-v4.1-flash": "haiku", "opencode-go/glm-5.3-flash": "haiku",
                 "opencode-go/qwen3.8-flash": "haiku", "opencode-go/gpt-6-luna": "haiku",
                 "opencode-go/kimi-k3": "opus", "opencode-go/glm-5.3": "opus"},
    "cmd": {"deepseek/deepseek-v4.1-flash": "haiku", "z-ai/glm-5.3-flash": "haiku",
            "Qwen/Qwen3.8-Flash": "haiku", "gpt-6-luna": "haiku"},
}
_LAST_GOOD = {}  # models.json path -> the last dict that parsed


def home() -> Path:
    """The data folder: env CC_CONSOLE_HOME (tests), else ~/.claude/console."""
    env = os.environ.get("CC_CONSOLE_HOME")
    return Path(env) if env else Path.home() / ".claude" / "console"


def load_models(write: bool = True) -> tuple:
    """(models, error): models.json parsed and "", or the last good dict (the defaults at first) and the error
    ("models.json line 12: Expecting ',' delimiter"). A missing file is written from MODELS_DEFAULT when
    `write`. Never raises."""
    path = home() / "models.json"
    last = _LAST_GOOD.get(str(path)) or copy.deepcopy(MODELS_DEFAULT)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if write:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(MODELS_DEFAULT, indent=2) + "\n", encoding="utf-8")
            except OSError:
                pass
        _LAST_GOOD[str(path)] = copy.deepcopy(MODELS_DEFAULT)
        return copy.deepcopy(MODELS_DEFAULT), ""
    except OSError as exc:
        return last, f"models.json: {exc.strerror or exc}"
    try:
        data = json.loads(text)
    except ValueError as exc:
        return last, f"models.json line {getattr(exc, 'lineno', 1)}: {getattr(exc, 'msg', exc)}"
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        return last, "models.json: expected an object of objects"
    _LAST_GOOD[str(path)] = copy.deepcopy(data)
    return data, ""


def _ladder_from(claude_models: dict, fallback: dict) -> dict:
    """tier -> rungs in file order, the alias (the tier's own name) first; only the tiers of claude_cli.MODELS
    (review G5: Hub.reload_models logs the others)."""
    from .claude_cli import MODELS  # late, as claude_cli.known_model imports harness: paths stays import-free
    ladder = {tier: [] for tier in fallback if tier in MODELS}
    for model, tier in claude_models.items():
        if tier in MODELS:
            ladder.setdefault(tier, []).append(model)
    return {tier: sorted(rungs, key=lambda m: m != tier) for tier, rungs in ladder.items() if rungs}


def load_config() -> dict:
    """DEFAULTS overlaid with config.json; nested dicts merge one level deep. Adds cfg["models"] (models.json)
    and, when models.json exists, cfg["ladder"] built from its Claude list."""
    cfg = copy.deepcopy(DEFAULTS)
    try:
        user = json.loads((home() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        user = None
    if isinstance(user, dict):
        for key, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    if isinstance(user, dict) and "design_max_turns" not in user and "opus_max_turns" in user:
        cfg["design_max_turns"] = user["opus_max_turns"]  # plan 24 D2: the old key counts once
    cfg.pop("opus_max_turns", None)
    claude = cfg["harnesses"].get("claude")
    if isinstance(claude, dict) and not claude.get("exe") and cfg.get("claude_exe"):
        claude["exe"] = cfg["claude_exe"]
    models, _ = load_models(write=False)
    models = copy.deepcopy(models)
    for name, section in cfg["harnesses"].items():  # an earlier build kept the lists in config.json
        if name not in models and isinstance(section, dict) and isinstance(section.get("models"), dict):
            models[name] = dict(section["models"])
    cfg["models"] = models
    if (home() / "models.json").exists() and isinstance(models.get("claude"), dict) and models["claude"]:
        cfg["ladder"] = _ladder_from(models["claude"], cfg["ladder"])
    return cfg


CONFIG_LOCK = threading.Lock()  # plan 27 (K1): every read-modify-write of config.json; the HTTP handlers run in threads


def _rewrite_config(path: Path, change, missing=None) -> None:
    """Read <path> (config.json), apply `change(data)` and write it back whole through a temp file of this write's
    own, all under CONFIG_LOCK. A missing file starts as `missing()`, or raises ValueError when `missing` is None;
    a file that is not a JSON object raises ValueError and is left as is (never overwrite Fred's file). OSError
    from the write (os.replace on Windows while a reader holds the file) propagates, with the temp file removed."""
    with CONFIG_LOCK:
        if path.exists() or missing is None:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None
            if not isinstance(data, dict):
                raise ValueError(f"cannot read {path}: fix it by hand")
        else:
            data = missing()
        change(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"config.json.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise


def set_harness(folder: Path, name: str, on: bool) -> None:
    """Write harnesses.<name>.on into <folder>/config.json; every other key stays as written.
    Raises ValueError for an unknown name or a config.json that cannot be read."""
    if name not in HARNESSES:
        raise ValueError(f"unknown harness: {name}")

    def change(data):
        harnesses = data.get("harnesses")
        if not isinstance(harnesses, dict):
            harnesses = data["harnesses"] = {}
        entry = harnesses.get(name)
        if not isinstance(entry, dict):
            entry = harnesses[name] = {"on": False, "exe": ""}
        entry["on"] = bool(on)

    _rewrite_config(Path(folder) / "config.json", change)


def add_project(folder: Path, project: str) -> None:
    """Add `project` to "projects" in <folder>/config.json; every other key stays as written.
    Raises ValueError when config.json exists but cannot be read (never overwrite Fred's file)."""

    def change(data):
        projects = data.get("projects") if isinstance(data.get("projects"), list) else []
        key = os.path.normcase(os.path.abspath(project))
        if all(os.path.normcase(os.path.abspath(p)) != key for p in projects if isinstance(p, str)):
            projects.append(project)
        data["projects"] = projects

    _rewrite_config(Path(folder) / "config.json", change, lambda: copy.deepcopy(DEFAULTS))


def set_config(folder: Path, values: dict, merge=("tiers",)) -> None:
    """Write `values` into <folder>/config.json with every other key as written (plan 26; set_harness does the same
    for one key): a key named in `merge` updates the file's object one level deep (a tier Fred did not touch keeps
    its list), any other key replaces the file's value. Raises ValueError when config.json exists but cannot be read
    (never overwrite Fred's file)."""

    def change(data):
        for key, value in values.items():
            if key in merge and isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value

    _rewrite_config(Path(folder) / "config.json", change, dict)


SETTINGS = ("handoff_auto",)  # plan 23: the booleans the window may flip through POST /api/setting


def set_setting(folder: Path, key: str, value: bool) -> None:
    """Write one whitelisted boolean into <folder>/config.json; every other key stays as written. ValueError for a key
    that is not in SETTINGS, a value that is not a bool, or a config.json that cannot be read."""
    if key not in SETTINGS:
        raise ValueError(f"not a setting: {key}")
    if not isinstance(value, bool):
        raise ValueError(f"{key} takes true or false")

    def change(data):
        data[key] = value

    _rewrite_config(Path(folder) / "config.json", change, lambda: copy.deepcopy(DEFAULTS))


def _drop_opus_max_turns(folder: Path) -> None:
    """Plan 24 D2: the old opus_max_turns counts once as design_max_turns (when that key is not set), then leaves
    config.json. Run at the service start; a file that cannot be read or written is left as is."""
    path = Path(folder) / "config.json"
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(user, dict) or "opus_max_turns" not in user:
        return

    def change(data):
        if "opus_max_turns" in data:
            data.setdefault("design_max_turns", data["opus_max_turns"])
            del data["opus_max_turns"]

    try:
        _rewrite_config(path, change)
    except (OSError, ValueError):
        pass  # load_config still reads the old key as the fallback


def write_text_atomic(path: Path, text: str) -> None:
    """Write <path> whole through a temp file of this write's own (pid and thread in its name), then os.replace: a
    reader never sees half a file and two writers never share a temp file (plan 34 F5). OSError propagates, with the
    temp file removed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


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


NAME_MAX = 60  # plan 31: user_name, in characters, on one line


def you(cfg: dict, start: bool = False) -> str:
    """The person as prompts and the plan's Decisions name them (plan 31): config `user_name` with its whitespace
    collapsed, else "the user" ("The user" with `start`, at the head of a sentence or a Decisions line)."""
    name = cfg.get("user_name") if isinstance(cfg, dict) else ""
    name = " ".join(name.split())[:NAME_MAX] if isinstance(name, str) else ""
    return name or ("The user" if start else "the user")


def os_user_name() -> str:
    """The name a fresh config.json starts with (plan 31): git's global user.name, else the OS login, else "".
    Never raises; git gets 5 s."""
    try:
        out = subprocess.run(["git", "config", "--global", "user.name"], capture_output=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        name = " ".join(out.stdout.decode("utf-8", "replace").split()) if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        name = ""
    if not name:
        try:
            name = " ".join(str(getpass.getuser() or "").split())
        except Exception:  # getpass raises when no variable names the login (a service account)
            name = ""
    return name[:NAME_MAX]


def _fill_user_name(folder: Path) -> None:
    """Plan 31: a config.json without `user_name` gets it once, from os_user_name, at the service start. A key
    already there (empty included: Fred cleared it) is never touched; a file that cannot be read is left as is."""
    path = Path(folder) / "config.json"
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(user, dict) or "user_name" in user:
        return
    name = os_user_name()
    try:
        _rewrite_config(path, lambda data: data.setdefault("user_name", name))
    except (OSError, ValueError):
        pass  # load_config reads DEFAULTS' "": the prompts say "the user"


def ensure_config() -> dict:
    """Write config.json with the defaults if it does not exist, then load it."""
    path = home() / "config.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({k: v for k, v in DEFAULTS.items() if k != "user_name"}, indent=2) + "\n",
                        encoding="utf-8")
    _drop_opus_max_turns(path.parent)
    _fill_user_name(path.parent)
    load_models()  # writes models.json when missing
    return load_config()
