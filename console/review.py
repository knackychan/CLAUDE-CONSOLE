"""The rules review (plan 22): a read-only Haiku pass over a project's CLAUDE.md and rules files, with the
console's routing misses and lessons, proposes what to remove, demote or add. It proposes only: nothing is
written anywhere but reviews/<id>.json; Fred copies a line he agrees with."""
import json
import secrets
import subprocess
import time
from pathlib import Path
from string import Template

from . import claude_cli, levers, redact, routing

PROMPT_FILE = Path(__file__).resolve().parent / "review_prompt.md"
KINDS = ["remove", "demote", "rule", "procedure", "keep"]
MAX_PROPOSALS = 6
_TEXT = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {"type": "array", "items": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": KINDS}, "target": _TEXT, "text": _TEXT, "why": _TEXT,
            "sources": {"type": "array", "items": _TEXT},
        }, "required": ["kind", "target", "text", "why", "sources"]}},
        "summary": _TEXT,
    },
    "required": ["proposals", "summary"],
}


class ReviewError(Exception):
    pass


def build_prompt(misses=(), lessons=(), days: float = 0) -> str:
    window = f"in the last {days:g} days " if days else ""
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        max=MAX_PROPOSALS, window=window, misses="\n".join(misses) or "(none)",
        lessons="\n".join(lessons) or "(none)")


def parse_output(stdout: str) -> dict:
    """{"proposals", "summary", "cost", "turns"} from `claude -p --output-format json --json-schema`."""
    try:
        data = json.loads(stdout)
    except ValueError:
        raise ReviewError("Review returned no JSON: " + redact.clip(stdout, 200))
    if not isinstance(data, dict):
        raise ReviewError("Review returned no JSON object")
    if data.get("is_error"):
        errors = data.get("errors")
        parts = [data.get("subtype"), data.get("terminal_reason"), data.get("result")]
        parts += errors if isinstance(errors, list) else [errors]
        detail = "; ".join(str(p) for p in dict.fromkeys(parts) if p)
        raise ReviewError("Review failed: " + redact.clip(detail or "no reason given", 300))
    fields = data.get("structured_output")
    if not isinstance(fields, dict) or not isinstance(fields.get("proposals"), list):
        raise ReviewError("Review returned no structured output")
    proposals = []
    for p in fields["proposals"][:MAX_PROPOSALS]:
        if isinstance(p, dict) and p.get("kind") in KINDS:
            proposals.append({"kind": p["kind"], "target": str(p.get("target") or ""), "text": str(p.get("text") or ""),
                              "why": str(p.get("why") or ""),
                              "sources": [str(s) for s in p.get("sources") or [] if str(s).strip()]})
    return {"proposals": proposals, "summary": str(fields.get("summary") or ""),
            "cost": data.get("total_cost_usd") or 0, "turns": data.get("num_turns") or 0}


def new_id() -> str:
    return time.strftime("r%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def run_review(cfg: dict, folder: Path, project_dir: str, exe: list, job_id: str = "") -> dict:
    """Blocking (the service runs it in a job thread). Saves reviews/<id>.json and returns the card."""
    cmd = claude_cli.prep_command(exe, cfg["review_model"], SCHEMA)
    project = Path(project_dir).name
    misses = routing.fresh(levers.read_misses(folder, project), cfg["miss_floor_days"])
    lessons = levers.read_lessons(folder, project)
    prompt = build_prompt(misses, lessons, cfg["miss_floor_days"])
    try:
        out = subprocess.run(cmd, cwd=project_dir, input=prompt.encode("utf-8"), capture_output=True,
                             timeout=cfg["review_timeout_s"], env=claude_cli.child_env(),
                             creationflags=claude_cli.NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise ReviewError(f"Review took longer than {cfg['review_timeout_s']} s")
    except OSError as exc:
        raise ReviewError(f"cannot start claude: {exc}")
    result = parse_output(out.stdout.decode("utf-8", "replace"))
    card = {"id": job_id or new_id(), "ts": time.time(), "project_dir": project_dir, "model": cfg["review_model"],
            "proposals": result["proposals"], "summary": redact.mask(result["summary"]),
            "cost": result["cost"], "turns": result["turns"], "misses": len(misses), "lessons": len(lessons)}
    reviews = Path(folder) / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    (reviews / f"{card['id']}.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return card
