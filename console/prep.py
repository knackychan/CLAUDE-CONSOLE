"""Prep (D3, D4): a read-only Haiku pass scouts the project, rewrites the prompt and picks a route.
The card always waits for Fred; nothing here starts a run."""
import json
import secrets
import subprocess
import time
from pathlib import Path
from string import Template

from . import claude_cli, levers, paths, redact, routing, tasks

PROMPT_FILE = Path(__file__).resolve().parent / "prep_prompt.md"
TYPES = ["mechanical", "lookup", "normal", "risky", "vague"]
_TEXT = {"type": "string"}
TEXT_KEYS = ["goal", "where", "keep", "done_when", "last_decisions", "question", "reason"]
# Only goal and route are required, and route comes first: on long answers Haiku left out other keys and resent
# the same object on all 5 retries (troubleshooting/prep-structured-output.md). parse_output fills the rest.
SCHEMA = {
    "type": "object",
    "properties": {
        "route": {"type": "object", "properties": {
            "type": {"type": "string", "enum": TYPES},
            "model": {"type": "string", "enum": claude_cli.MODELS},
            "effort": {"type": "string", "enum": claude_cli.EFFORTS},
            "reasoning": {"type": "string", "enum": routing.LEVELS},
            "volume": {"type": "string", "enum": routing.LEVELS},
        }, "required": ["type", "reasoning", "volume", "model", "effort"]},
        **{key: _TEXT for key in TEXT_KEYS},
        "steps": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": list(tasks.PREP_KINDS)}, "goal": _TEXT,
        }, "required": ["kind", "goal"]}},
    },
    "required": ["goal", "route"],
}
LABELS = [("goal", "Goal"), ("where", "Where"), ("keep", "Keep"), ("done_when", "Done when"),
          ("last_decisions", "Last decisions"), ("question", "Open question")]


class PrepError(Exception):
    pass


def build_prompt(raw: str, misses=(), days: float = 0, you: str = "The user") -> str:
    """The Prep instructions with the request and this project's routing misses filled in; `days` names the window
    the misses were kept from (0: not named); `you` is paths.you(cfg, start=True) (plan 31)."""
    window = f"in the last {days:g} days " if days else ""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        raw=raw.strip(), misses="\n".join(misses) or "(none)", window=window, You=you)


def format_prompt(fields: dict) -> str:
    """The enhanced prompt as Fred sees and edits it on the card."""
    lines = []
    for key, label in LABELS:
        value = str(fields.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def parse_output(stdout: str) -> dict:
    """The `structured_output` of `claude -p --output-format json --json-schema ...`."""
    try:
        data = json.loads(stdout)
    except ValueError:
        raise PrepError("Prep returned no JSON: " + redact.clip(stdout, 200))
    if not isinstance(data, dict):
        raise PrepError("Prep returned no JSON object")
    if data.get("is_error"):
        # an error result has no `result`: the reason is in subtype, terminal_reason and errors
        errors = data.get("errors")
        parts = [data.get("subtype"), data.get("terminal_reason"), data.get("result")]
        parts += errors if isinstance(errors, list) else [errors]
        detail = "; ".join(str(p) for p in dict.fromkeys(parts) if p)
        raise PrepError("Prep failed: " + redact.clip(detail or "no reason given", 300))
    fields = data.get("structured_output")
    if not isinstance(fields, dict) or not isinstance(fields.get("route"), dict):
        raise PrepError("Prep returned no structured output")
    route = fields["route"]
    if route.get("model") not in claude_cli.MODELS or route.get("effort") not in claude_cli.EFFORTS:
        raise PrepError("Prep picked an unknown route")
    for key in TEXT_KEYS:
        fields.setdefault(key, "")
    return {"fields": fields, "cost": data.get("total_cost_usd") or 0, "turns": data.get("num_turns") or 0}


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def run_prep(cfg: dict, folder: Path, project_dir: str, raw: str, exe: list, prep_id: str = "") -> dict:
    """Blocking (about 10-30 s; the service runs it in a job thread). Saves preps/<id>.json and returns
    the card; `prep_id` is the job's id, so the card and its job share one name."""
    cmd = claude_cli.prep_command(exe, cfg["prep_model"], SCHEMA)
    days = cfg.get("miss_floor_days", 0)
    misses = routing.fresh(levers.read_misses(folder, Path(project_dir).name), days)
    prompt = build_prompt(raw, misses, days, paths.you(cfg, start=True))
    try:
        out = subprocess.run(cmd, cwd=project_dir, input=prompt.encode("utf-8"),
                             capture_output=True, timeout=cfg["prep_timeout_s"], env=claude_cli.child_env(),
                             creationflags=claude_cli.NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise PrepError(f"Prep took longer than {cfg['prep_timeout_s']} s")
    except OSError as exc:
        raise PrepError(f"cannot start claude: {exc}")
    result = parse_output(out.stdout.decode("utf-8", "replace"))
    fields = result["fields"]
    route, picked = fields["route"], (fields["route"]["model"], fields["route"]["effort"])
    route["model"], route["effort"] = routing.pick(route, misses)  # the demand rule decides, not Prep
    if (route["model"], route["effort"]) != picked:
        fields["reason"] = (f"{fields.get('reason', '')} Demand rule: {'/'.join(picked)} -> "
                            f"{route['model']}/{route['effort']}.").strip()
    steps = tasks.plan_steps(fields.get("steps") or [], cfg["task_max_steps"])  # the only validator
    card = {
        "id": prep_id or new_id(), "ts": time.time(), "project_dir": project_dir, "raw": raw,
        "fields": fields, "prompt": format_prompt(fields), "route": fields["route"],
        "steps": steps, "demand": {"reasoning": route["reasoning"], "volume": route["volume"]},
        "reason": fields.get("reason", ""), "cost": result["cost"], "turns": result["turns"],
        "model": cfg["prep_model"], "floors": routing.floors(misses),
    }
    preps = Path(folder) / "preps"
    preps.mkdir(parents=True, exist_ok=True)
    (preps / f"{card['id']}.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return card


def load(folder: Path, prep_id: str):
    if not prep_id or not all(c.isalnum() or c == "-" for c in prep_id):
        return None
    try:
        return json.loads((Path(folder) / "preps" / f"{prep_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
