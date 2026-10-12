"""The brief (plan 17, README 3.6b): between two steps a Haiku pass with no tools and one turn compacts the
finished step's raw note, plus the brief before it, into what the next step needs. The pass decides nothing:
code checks its answer and falls back to fixed cuts, so a failed pass never stops the chain."""
import json
import subprocess
from pathlib import Path
from string import Template

from . import claude_cli, redact, tasks

PROMPT_FILE = Path(__file__).resolve().parent / "compact_prompt.md"
_LIST = {"type": "array", "items": {"type": "string"}}
BRIEF_SCHEMA = {
    "type": "object",
    "properties": {"findings": _LIST, "files": _LIST, "questions": _LIST, "next": {"type": "string"}},
    "required": ["findings", "files", "questions", "next"],
}
FINDINGS_CUT = 1500  # characters of the raw Findings the code fallback keeps


class BriefError(Exception):
    pass


def build_prompt(task: dict, step: dict, next_step, prev_brief: str, raw: str, words_target: int = 400) -> str:
    """compact_prompt.md filled in; `next_step` is None after the last step. The task is named by its goal (the
    title is an 80-character clip), `words_target` is the length asked for (`budget`)."""
    nxt = next_step or {"n": "-", "kind": "none",
                        "goal": "none, this was the last step: keep what a follow-up chat on this task needs"}
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        task=redact.clip(task.get("goal") or task["title"], 400), next_n=nxt["n"], m=len(task["steps"]),
        next_kind=nxt["kind"], next_goal=nxt["goal"], prev=prev_brief or "(none: this is the first brief)",
        n=step["n"], kind=step["kind"], raw=raw, words=words_target)


def _bullets(items) -> str:
    lines = [f"- {' '.join(str(item).split())}" for item in items if str(item).strip()]
    return "\n".join(lines) or "- (none)"


def render(fields: dict) -> str:
    """The four handoff headings in order; lists become `- ` lines, an empty one `- (none)`."""
    text = "\n".join([
        "## Findings", _bullets(fields.get("findings") or []),
        "## Files touched", _bullets(fields.get("files") or []),
        "## Open questions", _bullets(fields.get("questions") or []),
        "## Next", " ".join(str(fields.get("next") or "").split()) or "(none)"])
    return redact.mask(text)


def words(text: str) -> int:
    return len(str(text or "").split())


def limit(raw: str, prev: str) -> int:
    """What a brief compacts: the raw note plus the earlier brief it carries forward. It never adds to them."""
    return words(raw) + words(prev)


def budget(cfg: dict, raw: str, prev: str) -> int:
    """The word target the prompt asks for: 60 % of what it compacts, at least 60, at most brief_max_words."""
    return max(60, min(cfg["brief_max_words"], limit(raw, prev) * 6 // 10))


def _open(text: str) -> list:
    """The open questions of a note or a brief: the lines under `## Open questions` that are not a none."""
    lines = _sections(text).get("## Open questions", "").splitlines()
    out = [line.strip().lstrip("-* ").strip() for line in lines]
    return [q for q in out if q and q.strip("().").lower() not in ("none", "n/a", "")]


def check(block: str, max_words: int, raw: str = "", prev: str = "") -> str:
    """"" when the block has the four headings, fits `max_words`, is shorter than what it compacts (when `raw` is
    given) and keeps the open questions; else the reason."""
    why = tasks.check_handoff(block)
    if why:
        return why
    n = words(block)
    if n > max_words:
        return f"over {max_words} words"
    if raw and n >= limit(raw, prev):
        return f"not shorter than what it compacts ({n} >= {limit(raw, prev)} words)"
    if (_open(raw) or _open(prev)) and not _open(block):
        return "dropped the open questions"
    return ""


def cut(fields: dict, max_words: int):
    """The answer with its last findings dropped until the rendered brief fits `max_words`; files, questions and
    next stay whole. None when one finding is left and it is still over. `fields` is not changed."""
    findings = list(fields.get("findings") or [])
    while len(findings) > 1 and words(render(dict(fields, findings=findings))) > max_words:
        findings.pop()
    out = dict(fields, findings=findings)
    return out if words(render(out)) <= max_words else None


def _sections(text: str) -> dict:
    """heading -> the lines under it, for the four handoff headings (a HANDOFF block is unwrapped first)."""
    text = tasks.parse_handoff(text) or text
    found, heading = {}, None
    for line in str(text or "").splitlines():
        if line.strip() in tasks.HEADINGS:
            heading = line.strip()
            found[heading] = []
        elif heading:
            found[heading].append(line)
    return {h: "\n".join(lines).strip() for h, lines in found.items()}


def fallback(prev_brief: str, raw: str) -> str:
    """Code only: the raw note's Files touched and Open questions as they are, its Findings cut, its Next (else
    the previous brief's)."""
    now, before = _sections(raw), _sections(prev_brief)
    findings = now.get("## Findings", "")
    if len(findings) > FINDINGS_CUT:
        findings = findings[:FINDINGS_CUT].rstrip() + "\n[cut]"
    nxt = now.get("## Next") or before.get("## Next") or "(none)"
    return redact.mask("\n".join([
        "## Findings", findings or "(none recorded)",
        "## Files touched", now.get("## Files touched") or "- (none)",
        "## Open questions", now.get("## Open questions") or "- (none)",
        "## Next", nxt]))


def _ask(cfg: dict, exe: list, project_dir: str, prompt: str):
    """One `claude -p` pass; (fields, cost) or BriefError with the reason."""
    cmd = claude_cli.brief_command(exe, cfg["brief_model"], BRIEF_SCHEMA)
    try:
        out = subprocess.run(cmd, cwd=project_dir, input=prompt.encode("utf-8"), capture_output=True,
                             timeout=cfg["brief_timeout_s"], env=claude_cli.child_env(),
                             creationflags=claude_cli.NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise BriefError(f"the brief took longer than {cfg['brief_timeout_s']} s")
    except OSError as exc:
        raise BriefError(f"cannot start claude: {exc}")
    stdout = out.stdout.decode("utf-8", "replace")
    try:
        data = json.loads(stdout)
    except ValueError:
        raise BriefError("the brief returned no JSON: " + redact.clip(stdout, 120))
    if not isinstance(data, dict):
        raise BriefError("the brief returned no JSON object")
    if data.get("is_error"):
        detail = data.get("subtype") or data.get("terminal_reason") or "no reason given"
        raise BriefError("the brief failed: " + redact.clip(str(detail), 200))
    fields = data.get("structured_output")
    lists = ("findings", "files", "questions")
    if not isinstance(fields, dict) or not all(isinstance(fields.get(k), list) for k in lists) \
            or not isinstance(fields.get("next"), str):
        raise BriefError("the brief returned no structured output")
    return fields, data.get("total_cost_usd") or 0


def run_brief(cfg: dict, exe: list, task: dict, step: dict, next_step, prev_brief: str, raw: str) -> dict:
    """Blocking (about 5 to 15 s; the service runs it in a thread). Never raises: any failure, or an answer
    that fails `check` ends in `fallback`, except one that is only too long: its last findings are cut (`cut`
    counts them) and it is checked again. {"text", "cost", "words", "model", "cut", "fallback": "" | why}."""
    cost, why, dropped = 0, "", 0
    try:
        prompt = build_prompt(task, step, next_step, prev_brief, raw, budget(cfg, raw, prev_brief))
        fields, cost = _ask(cfg, exe, task["project_dir"], prompt)
        text = render(fields)
        why = check(text, cfg["brief_max_words"], raw, prev_brief)
        if why.startswith(("over ", "not shorter")):
            short = cut(fields, min(cfg["brief_max_words"], limit(raw, prev_brief) - 1))
            if short:
                dropped = len(fields["findings"]) - len(short["findings"])
                text = render(short)
                why = check(text, cfg["brief_max_words"], raw, prev_brief)
    except BriefError as exc:
        text, why = "", str(exc)
    if why:
        text, dropped = fallback(prev_brief, raw), 0
    return {"text": text, "cost": cost, "words": len(text.split()), "model": cfg["brief_model"], "cut": dropped,
            "fallback": why}
