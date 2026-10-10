"""Prep (D3, D4): a read-only Haiku pass scouts the project, rewrites the prompt and picks a route.
The card always waits for Fred; nothing here starts a run."""
import json
import secrets
import subprocess
import time
from pathlib import Path
from string import Template

from . import claude_cli, levers, redact

PROMPT_FILE = Path(__file__).resolve().parent / "prep_prompt.md"
TYPES = ["mechanical", "lookup", "normal", "risky", "vague"]
_TEXT = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "goal": _TEXT, "where": _TEXT, "keep": _TEXT, "done_when": _TEXT,
        "last_decisions": _TEXT, "question": _TEXT, "reason": _TEXT,
        "route": {"type": "object", "properties": {
            "type": {"type": "string", "enum": TYPES},
            "model": {"type": "string", "enum": claude_cli.MODELS},
            "effort": {"type": "string", "enum": claude_cli.EFFORTS},
        }, "required": ["type", "model", "effort"]},
    },
    "required": ["goal", "where", "keep", "done_when", "last_decisions", "question", "route", "reason"],
}
LABELS = [("goal", "Goal"), ("where", "Where"), ("keep", "Keep"), ("done_when", "Done when"),
          ("last_decisions", "Last decisions"), ("question", "Open question")]


class PrepError(Exception):
    pass


def build_prompt(raw: str, misses=()) -> str:
    """The Prep instructions with Fred's request and this project's routing misses filled in."""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        raw=raw.strip(), misses="\n".join(misses) or "(none)")


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
        raise PrepError("Prep failed: " + redact.clip(data.get("result", ""), 200))
    fields = data.get("structured_output")
    if not isinstance(fields, dict) or not isinstance(fields.get("route"), dict):
        raise PrepError("Prep returned no structured output")
    route = fields["route"]
    if route.get("model") not in claude_cli.MODELS or route.get("effort") not in claude_cli.EFFORTS:
        raise PrepError("Prep picked an unknown route")
    return {"fields": fields, "cost": data.get("total_cost_usd") or 0, "turns": data.get("num_turns") or 0}


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def run_prep(cfg: dict, folder: Path, project_dir: str, raw: str, exe: list) -> dict:
    """Blocking (about 10-30 s). Saves preps/<id>.json and returns the card."""
    cmd = claude_cli.prep_command(exe, cfg["prep_model"], SCHEMA)
    prompt = build_prompt(raw, levers.read_misses(folder, Path(project_dir).name))
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
    card = {
        "id": new_id(), "ts": time.time(), "project_dir": project_dir, "raw": raw,
        "fields": fields, "prompt": format_prompt(fields), "route": fields["route"],
        "reason": fields.get("reason", ""), "cost": result["cost"], "turns": result["turns"],
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
