"""Prep (D3, D4): a read-only Haiku pass scouts the project, rewrites the prompt and picks a route.
The card always waits for Fred; nothing here starts a run.

Plan 29 (D6, D7): the prompt opens its task folder when it is sent, `<home>/tasks/<id>/` with prompt.md as typed; the
Prep job and the task share that id. Prep's files go in `00-prep/`: role.md (the prompt Prep ran), prep.json (the
card), prompt.md (the enhanced prompt), scouting.md (what Prep read) and handoff.md (built here, the handoff step 1
reads). task.json is written only when the card runs (Hub.create_task, Hub.chat_task); a folder without one is an
unsent prompt: a dropped card removes it, and one left by a restart goes after ORPHAN_DAYS."""
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path
from string import Template

from . import claude_cli, kinds, levers, paths, redact, routing, tasks

PROMPT_FILE = kinds.SEED / "prep.md"  # plan 29: the prep kind file's repo copy (the service reads kinds.text)
DIR = "00-prep"
ORPHAN_DAYS = 2  # an unsent prompt's folder (no task.json) left by a restart goes at the service start after this
FINDINGS_CUT = 600  # characters of the scouting a writer step 1 gets (a design step reads scouting.md whole)
TYPES = ["mechanical", "lookup", "normal", "risky", "vague"]
_TEXT = {"type": "string"}
TEXT_KEYS = ["goal", "where", "keep", "done_when", "last_decisions", "question", "reason", "scouting"]
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
        "scouting": _TEXT,  # plan 29 (D7): what Prep read, one line each; never required (parse_output fills "")
    },
    "required": ["goal", "route"],
}
LABELS = [("goal", "Goal"), ("where", "Where"), ("keep", "Keep"), ("done_when", "Done when"),
          ("last_decisions", "Last decisions"), ("question", "Open question")]


class PrepError(Exception):
    pass


def build_prompt(raw: str, misses=(), days: float = 0, you: str = "The user", text: str = None) -> str:
    """The Prep instructions with the request and this project's routing misses filled in; `days` names the window
    the misses were kept from (0: not named); `you` is paths.you(cfg, start=True) (plan 31); `text` is the prep kind
    file (kinds.text, plan 29), the repo's seed when None."""
    window = f"in the last {days:g} days " if days else ""
    text = PROMPT_FILE.read_text(encoding="utf-8") if text is None else text
    return Template(kinds.body_of(text)).safe_substitute(
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
    """Blocking (about 10-30 s; the service runs it in a job thread). Saves the card in tasks/<id>/00-prep/ (save)
    and returns it; `prep_id` is the job's id, so the card, its job and its task share one name."""
    cmd = claude_cli.prep_command(exe, cfg["prep_model"], SCHEMA)
    days = cfg.get("miss_floor_days", 0)
    misses = routing.fresh(levers.read_misses(folder, Path(project_dir).name), days)
    prompt = build_prompt(raw, misses, days, paths.you(cfg, start=True), kinds.text(folder, "prep"))
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
    save(folder, card, prompt)
    return card


def dir_of(home, prep_id: str) -> Path:
    """tasks/<id>/00-prep/ of a Prep id (a task id: prep.new_id makes both)."""
    return tasks.folder(home, prep_id) / DIR


def begin(home, prep_id: str, raw: str) -> None:
    """The prompt was sent (Hub.start_prep, plan 29): its task folder with prompt.md as typed."""
    where = tasks.folder(home, prep_id)
    where.mkdir(parents=True, exist_ok=True)
    (where / "prompt.md").write_text(str(raw or "").strip() + "\n", encoding="utf-8")


def handoff_text(card: dict, first_goal: str = None) -> str:
    """00-prep/handoff.md (plan 29): the six headings built from the card, as a step leaves them. Goal is the enhanced
    goal, Findings the scouting, Open questions Prep's question, Next step 1's goal (`first_goal`, else the card's
    first step, else one chat on the card's route)."""
    fields, route = card.get("fields") or {}, card.get("route") or {}
    goal = redact.clip(" ".join(str(fields.get("goal") or card.get("raw") or "").split()), 300)
    scouting = str(fields.get("scouting") or "").strip() or "(Prep read nothing)"
    question = str(fields.get("question") or "").strip()
    if first_goal is None:
        first_goal = (card.get("steps") or [{}])[0].get("goal") or ""
    nxt = first_goal or f"One chat on {route.get('model', '')}/{route.get('effort', '')} does the whole request."
    return ("## Goal\n" + goal + "\n## Findings\n" + scouting + "\n## Files touched\n- (none)\n## Troubleshooting\n"
            "- (none)\n## Open questions\n" + (f"- {question}" if question else "- (none)") + "\n## Next\n" + nxt + "\n")


def save(home, card: dict, sent: str = "") -> None:
    """The card's files in tasks/<id>/00-prep/: prep.json whole, prompt.md (the enhanced prompt), scouting.md when
    Prep wrote one, handoff.md, and role.md (`sent`, the prompt Prep ran) when given. Masked like a step's files."""
    where = dir_of(home, card["id"])
    where.mkdir(parents=True, exist_ok=True)
    (where / "prep.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    files = {"prompt.md": card.get("prompt") or "", "handoff.md": handoff_text(card),
             "scouting.md": str((card.get("fields") or {}).get("scouting") or "").strip(),
             "role.md": f"# prep\n\n{sent}" if sent else ""}
    for name, text in files.items():
        if text:
            (where / name).write_text(redact.mask(text).rstrip("\n") + "\n", encoding="utf-8")


def load(folder: Path, prep_id: str):
    """The card of a Prep id: tasks/<id>/00-prep/prep.json, else a card from before plan 29 in preps/<id>.json."""
    if not prep_id or not all(c.isalnum() or c == "-" for c in prep_id):
        return None
    where = [dir_of(folder, prep_id) / "prep.json"] if tasks.safe_id(prep_id) else []
    for path in where + [Path(folder) / "preps" / f"{prep_id}.json"]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


def read(home, task: dict, name: str) -> str:
    """One file of the task's 00-prep/ ("" when missing): handoff.md, scouting.md, prompt.md."""
    try:
        return (tasks.folder(home, task["id"]) / DIR / name).read_text(encoding="utf-8")
    except OSError:
        return ""


def first_handoff(home, task: dict) -> str:
    """What step 1 of a task Prep made receives (plan 29): 00-prep/handoff.md with its Findings cut to FINDINGS_CUT
    characters; "" for a task with no Prep handoff (Raw, or a task from before plan 29)."""
    text = read(home, task, "handoff.md")
    head, sep, rest = text.partition("## Findings\n")
    if not sep:
        return text.strip()
    findings, sep2, tail = rest.partition("\n## Files touched")
    if len(findings) > FINDINGS_CUT:
        findings = findings[:FINDINGS_CUT - 1].rstrip() + "\u2026"
    return (head + sep + findings + sep2 + tail).strip()


def summary(card: dict, state: str = "done") -> dict:
    """task["prep"] (plan 29, D6): what the window shows as step 0. `state` is done, or skipped for Raw (no card)."""
    if not card:
        return {"id": "", "state": "skipped"}
    return {"id": card["id"], "state": state, "model": card.get("model") or "", "turns": card.get("turns") or 0,
            "cost": card.get("cost") or 0, "route": dict(card.get("route") or {}), "reason": card.get("reason") or "",
            "question": (card.get("fields") or {}).get("question") or "",
            "steps": [{"kind": x["kind"], "goal": x["goal"]} for x in card.get("steps") or []]}


def discard(home, prep_id: str) -> bool:
    """Remove an unsent prompt's folder (plan 29: a dropped card leaves no history). Only a folder with no
    task.json goes; True when one was removed."""
    if not tasks.safe_id(prep_id):
        return False
    where = tasks.folder(home, prep_id)
    if not where.is_dir() or (where / "task.json").exists():
        return False
    shutil.rmtree(where, ignore_errors=True)
    return not where.exists()


def prune_orphans(home, now: float = None, days: float = ORPHAN_DAYS) -> list:
    """At the service start: the folders of prompts never run (no task.json, a card the restart lost) older than
    `days`, whatever task_retention_days says. Returns the ids removed."""
    root, now, gone = Path(home) / "tasks", now or time.time(), []
    if not root.is_dir():
        return gone
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not tasks.safe_id(entry.name) or (entry / "task.json").exists():
            continue
        try:
            age = now - os.path.getmtime(entry)
        except OSError:
            continue
        if age > days * 86400 and discard(home, entry.name):
            gone.append(entry.name)
    return gone
