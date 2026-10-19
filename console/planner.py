"""Plan 47: the planner pass. After Prep, one bounded `claude -p` on `planner_model` (opus by default) reviews the
card's scope and writes its step list. Read-only tools (Read, Grep, Glob) in the project folder, so it checks
Prep's claims; never a task session, never writes, never edits the project. Any failure (timeout, no JSON, bad
shape, an error envelope, no exe) leaves Prep's own steps to `run_prep` with `error` set: `run` never raises. It
shares no code with the supervisor."""
import json
import subprocess
from string import Template

from . import claude_cli, kinds, paths, prep, redact, tasks

SCOPES = ["ok", "too_big", "too_small", "unclear"]
SCHEMA = {
    "type": "object",
    "properties": {
        "scope": {"type": "string", "enum": SCOPES},
        "note": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": list(tasks.PREP_KINDS)}, "goal": {"type": "string"},
        }, "required": ["kind", "goal"]}},
    },
    "required": ["scope", "note", "steps"],
}
NOTE_MAX = 300  # characters of the note the card shows


def build_prompt(card: dict, you: str, text: str) -> str:
    """The planner kind file (`$You` filled) followed by the card as evidence: the request as typed, the enhanced
    prompt, the route and demand, the scouting and Prep's proposed steps, one `- kind: goal` line each."""
    fields, route = card.get("fields") or {}, card.get("route") or {}
    steps = [f"- {s.get('kind')}: {s.get('goal')}" for s in fields.get("steps") or []
             if isinstance(s, dict) and s.get("kind") and s.get("goal")]
    head = Template(kinds.body_of(text)).safe_substitute(You=you)
    return "\n".join([
        head, "",
        "Request as typed:", str(card.get("raw") or "").strip() or "(none)", "",
        "Enhanced prompt:", prep.format_prompt(fields) or "(none)", "",
        f"Route: {route.get('type', '')}, {route.get('model', '')}/{route.get('effort', '')}, "
        f"reasoning {route.get('reasoning', '')}, volume {route.get('volume', '')}", "",
        "Scouting (what Prep read):", str(fields.get("scouting") or "").strip() or "(none)", "",
        "Prep's proposed steps:", "\n".join(steps) or "(none)", ""])


def shape(fields) -> str:
    """"" when `fields` is an answer of SCHEMA, else the reason."""
    if not isinstance(fields, dict):
        return "no JSON object"
    if fields.get("scope") not in SCOPES:
        return "scope is not one of " + ", ".join(SCOPES)
    if not isinstance(fields.get("note"), str):
        return "note is not text"
    if not isinstance(fields.get("steps"), list):
        return "steps is not a list"
    for item in fields["steps"]:
        if not isinstance(item, dict) or item.get("kind") not in tasks.PREP_KINDS:
            return "a step has an unknown kind"
        if not isinstance(item.get("goal"), str) or not item["goal"].strip():
            return "a step has no goal"
    return ""


def _failed(model: str, error: str, cost=None, turns: int = 0) -> dict:
    return {"steps": [], "scope": "", "note": "", "cost": cost, "model": model, "turns": turns, "error": error}


def run(cfg: dict, exe: list, project_dir: str, card: dict, text: str) -> dict:
    """Blocking, inside Prep's job thread. {"steps": plan_steps-validated list, "scope", "note", "cost", "model",
    "turns", "error"}; on any failure steps is [] and error says why, cost is what the CLI reported (None when no
    envelope came back, 0 when nothing ran)."""
    model = cfg.get("planner_model") or "opus"
    if not exe:
        return _failed(model, "claude.exe not found", cost=0)
    cmd = claude_cli.planner_command(exe, model, SCHEMA, cfg.get("planner_max_cost") or 0.5)
    prompt = build_prompt(card, paths.you(cfg, start=True), text)
    timeout = cfg.get("planner_timeout_s") or 120
    try:
        out = subprocess.run(cmd, cwd=project_dir, input=prompt.encode("utf-8"), capture_output=True,
                             timeout=timeout, env=claude_cli.child_env(), creationflags=claude_cli.NO_WINDOW)
    except subprocess.TimeoutExpired:
        return _failed(model, f"the planner took longer than {timeout} s")
    except OSError as exc:
        return _failed(model, f"cannot start claude: {exc}")
    try:
        data = json.loads(out.stdout.decode("utf-8", "replace"))
    except ValueError:
        return _failed(model, "the planner returned no JSON")
    if not isinstance(data, dict):
        return _failed(model, "the planner returned no JSON object")
    cost, turns = data.get("total_cost_usd"), data.get("num_turns") or 0
    if data.get("is_error"):
        errors = data.get("errors")
        parts = [data.get("subtype"), data.get("terminal_reason"), data.get("result")]
        parts += errors if isinstance(errors, list) else [errors]
        detail = "; ".join(str(p) for p in dict.fromkeys(parts) if p)
        return _failed(model, "the planner failed: " + redact.clip(detail or "no reason given", 300), cost, turns)
    fields = data.get("structured_output")
    why = shape(fields)
    if why:
        return _failed(model, "the planner answered badly: " + why, cost, turns)
    steps = tasks.plan_steps(fields["steps"], cfg.get("task_max_steps") or 6)
    note = redact.clip(" ".join(fields["note"].split()), NOTE_MAX)
    return {"steps": steps, "scope": fields["scope"], "note": note, "cost": cost, "model": model, "turns": turns,
            "error": "" if steps else "no valid steps"}
