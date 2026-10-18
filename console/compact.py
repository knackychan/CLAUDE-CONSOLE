"""The brief (plan 17, README 3.6b; plan 23): between two steps a Haiku pass with no tools compacts the finished
step's raw note, plus the brief before it, into what the next step needs, under the same six headings. The pass
decides nothing: code puts the Goal and the Troubleshooting back whole, checks its answer, cuts findings first, and
falls back to fixed cuts, so a failed pass never stops the chain."""
import json
import math
import re
import subprocess
from pathlib import Path
from string import Template

from . import claude_cli, redact, tasks

PROMPT_FILE = Path(__file__).resolve().parent / "compact_prompt.md"
_LIST = {"type": "array", "items": {"type": "string"}}
BRIEF_SCHEMA = {
    "type": "object",
    "properties": {"goal": {"type": "string"}, "findings": _LIST, "files": _LIST, "troubleshooting": _LIST,
                   "questions": _LIST, "next": {"type": "string"}},
    "required": ["goal", "findings", "files", "troubleshooting", "questions", "next"],
}
FINDINGS_CUT = 1500  # characters of the raw Findings the code fallback keeps
_NONE = {"none", "n/a", "-", "", "none recorded"}
_EXT = {"py", "md", "js", "mjs", "ts", "tsx", "jsx", "css", "html", "json", "jsonl", "txt", "toml", "yaml", "yml",
        "ini", "cfg", "bat", "cmd", "ps1", "sh", "sql", "csv", "xml", "svg", "png", "jpg", "rs", "go", "java", "c",
        "h", "cpp", "cs", "rb", "php", "lock", "woff2"}
_PATH = re.compile(r"(?<![\w@/\\.-])((?:[A-Za-z]:)?[/\\]?(?:[\w.-]+[/\\])*[\w-][\w.-]*\.([A-Za-z][A-Za-z0-9]{0,7}))"
                   r"(?::\d+(?:-\d+)?)?(?![\w/\\-])")


class BriefError(Exception):
    pass


def build_prompt(task: dict, step: dict, next_step, prev_brief: str, raw: str, words_target: int = 500) -> str:
    """compact_prompt.md filled in; `next_step` is None after the last step. The task is named by its goal (the
    title is an 80-character clip), `words_target` is the length asked for (`budget`)."""
    nxt = next_step or {"n": "-", "kind": "none",
                        "goal": "none, this was the last step: keep what a follow-up chat on this task needs"}
    return Template(PROMPT_FILE.read_text(encoding="utf-8")).safe_substitute(
        task=redact.clip(task.get("goal") or task["title"], 400), next_n=nxt["n"], m=len(task["steps"]),
        next_kind=nxt["kind"], next_goal=nxt["goal"], prev=prev_brief or "(none: this is the first brief)",
        n=step["n"], kind=step["kind"], raw=raw, words=words_target)


def _item(line) -> str:
    """One line of a section as an item: the bullet and the extra spaces gone; "" for a none line or a blank."""
    text = " ".join(str(line or "").split()).lstrip("-* ").strip()
    return "" if text.strip("().").lower() in _NONE else text


def _bullets(items) -> str:
    lines = [f"- {' '.join(str(item).split())}" for item in items if str(item).strip()]
    return "\n".join(lines) or "- (none)"


def render(fields: dict) -> str:
    """The six handoff headings in order; lists become `- ` lines, an empty one `- (none)`; the goal keeps its lines."""
    goal = "\n".join(" ".join(line.split()) for line in str(fields.get("goal") or "").splitlines() if line.strip())
    text = "\n".join([
        "## Goal", goal or "(none)",
        "## Findings", _bullets(fields.get("findings") or []),
        "## Files touched", _bullets(fields.get("files") or []),
        "## Troubleshooting", _bullets(fields.get("troubleshooting") or []),
        "## Open questions", _bullets(fields.get("questions") or []),
        "## Next", " ".join(str(fields.get("next") or "").split()) or "(none)"])
    return redact.mask(text)


def words(text: str) -> int:
    return len(str(text or "").split())


def note_body(raw: str) -> str:
    """A note file without its `# Step NN: ...` head line: what the step wrote."""
    text = str(raw or "")
    return text.split("\n\n", 1)[1] if text.startswith("# Step ") and "\n\n" in text else text


def limit(raw: str, prev: str) -> int:
    """What a brief compacts: the raw note plus the earlier brief it carries forward. It never adds to them."""
    return words(raw) + words(prev)


def budget(cfg: dict, raw: str, prev: str) -> int:
    """The word target the prompt asks for: 60 % of what it compacts, at least 60, at most brief_max_words."""
    return max(60, min(cfg["brief_max_words"], limit(raw, prev) * 6 // 10))


def _sections(text: str) -> dict:
    """heading -> the lines under it, for the six handoff headings (a HANDOFF block is unwrapped first; a
    four-heading note from before plan 23 gives its four)."""
    text = tasks.parse_handoff(text) or text
    found, heading = {}, None
    for line in str(text or "").splitlines():
        if line.strip() in tasks.HEADINGS:
            heading = line.strip()
            found[heading] = []
        elif heading:
            found[heading].append(line)
    return {h: "\n".join(lines).strip() for h, lines in found.items()}


def _items(text: str, heading: str) -> list:
    return [i for i in (_item(line) for line in _sections(text).get(heading, "").splitlines()) if i]


def _open(text: str) -> list:
    """The open questions of a note or a brief: the lines under `## Open questions` that are not a none."""
    return _items(text, "## Open questions")


def carried(raw: str, prev: str) -> tuple:
    """(goal lines, troubleshooting lines) a brief must carry whole: the raw note's Goal (else the earlier brief's),
    and every Troubleshooting line of the earlier brief, then of the raw note, once each."""
    goal = _items(raw, "## Goal") or _items(prev, "## Goal")
    trouble = list(dict.fromkeys(_items(prev, "## Troubleshooting") + _items(raw, "## Troubleshooting")))
    return goal, trouble


def restore(fields: dict, raw: str, prev: str) -> dict:
    """The pass's answer with the carried Goal and Troubleshooting put back whole (D2 a): a paraphrase never cuts a
    dead end. Where nothing is carried the answer's own text stays. `fields` is not changed."""
    goal, trouble = carried(raw, prev)
    out = dict(fields)
    if goal:
        out["goal"] = "\n".join(goal)
    if trouble or raw or prev:
        out["troubleshooting"] = trouble
    return out


def paths(text: str) -> set:
    """The file paths a text names, normalised (forward slashes, lower case, no `./`, no `:line`): a token with a
    slash and an extension, or a bare name with a known extension (calc.py, README.md)."""
    out = set()
    for m in _PATH.finditer(str(text or "")):
        path, ext = m.group(1), m.group(2).lower()
        if ("/" in path or "\\" in path or ext in _EXT) and not path.startswith(("http", "www.")):
            out.add(path.replace("\\", "/").lower().removeprefix("./"))
    return out


def _named(path: str, pool) -> bool:
    """`path` is in `pool`, or one is the other with a folder in front (tasks.py and console/tasks.py)."""
    return any(path == q or q.endswith("/" + path) or path.endswith("/" + q) for q in pool)


def checks(block: str, max_words: int, raw: str = "", prev: str = "", touched=()) -> list:
    """Every check of a brief, in order: [{"name", "ok", "why"}] (why "" when ok). `raw` and `prev` are what it
    compacts; `touched` the paths the step's git facts list. Without `raw` only the first four run."""
    out, n = [], words(block)

    def add(name, why):
        out.append({"name": name, "ok": not why, "why": why})

    add("headings", tasks.check_handoff(block))
    add("words", f"over {max_words} words" if n > max_words else "")
    add("shorter", f"not shorter than what it compacts ({n} >= {limit(raw, prev)} words)"
        if raw and n >= limit(raw, prev) else "")
    add("questions", "dropped the open questions" if (_open(raw) or _open(prev)) and not _open(block) else "")
    if not raw:
        return out
    goal, trouble = carried(raw, prev)
    have_goal, have_trouble = set(_items(block, "## Goal")), set(_items(block, "## Troubleshooting"))
    add("goal", "cut the Goal" if any(line not in have_goal for line in goal) else "")
    add("troubleshooting", "cut the Troubleshooting" if any(line not in have_trouble for line in trouble) else "")
    named, earlier = paths(block), paths(_sections(prev).get("## Files touched", ""))
    add("continuity", "names no file of the earlier Files touched"
        if earlier and not any(_named(p, named) for p in earlier) else "")
    pool = paths(raw) | paths(prev) | {str(p).replace("\\", "/").lower() for p in touched}
    invented = sorted(p for p in named if not _named(p, pool))
    add("paths", f"names a path no step touched: {invented[0]}" if invented else "")
    return out


def check(block: str, max_words: int, raw: str = "", prev: str = "", touched=()) -> str:
    """"" when every check passes; else the first failing check's reason."""
    return next((c["why"] for c in checks(block, max_words, raw, prev, touched) if not c["ok"]), "")


def cut(fields: dict, max_words: int):
    """The answer with its last findings dropped until the rendered brief fits `max_words`; every other heading stays
    whole. None when one finding is left and it is still over. `fields` is not changed."""
    findings = list(fields.get("findings") or [])
    while len(findings) > 1 and words(render(dict(fields, findings=findings))) > max_words:
        findings.pop()
    out = dict(fields, findings=findings)
    return out if words(render(out)) <= max_words else None


def _merge(first: str, second: str) -> str:
    """The lines of `first` as they are, then the lines of `second` whose item `first` lacks; none lines dropped."""
    out, seen = [], set()
    for line in (str(first or "") + "\n" + str(second or "")).splitlines():
        item = _item(line)
        if item and item not in seen:
            seen.add(item)
            out.append(line.rstrip())
    return "\n".join(out)


def cut_lines(findings: str) -> list:
    """The Findings lines the fallback leaves out (past FINDINGS_CUT characters), as items."""
    out, at = [], 0
    for line in str(findings or "").splitlines(keepends=True):
        if at + len(line.rstrip("\n")) > FINDINGS_CUT and _item(line):
            out.append(_item(line))
        at += len(line)
    return out


def fallback(prev_brief: str, raw: str, cut: bool = True) -> str:
    """Code only: the carried Goal and Troubleshooting whole, the raw note's Findings cut, its Files touched with the
    earlier brief's after them, its Open questions as they are, its Next (else the earlier brief's). `cut` False keeps
    the Findings whole: the brief of a handoff under brief_max_words (plan 28, as_is)."""
    now, before = _sections(raw), _sections(prev_brief)
    goal, trouble = carried(raw, prev_brief)
    findings = now.get("## Findings", "")
    if cut and len(findings) > FINDINGS_CUT:
        findings = findings[:FINDINGS_CUT].rstrip() + "\n[cut]"
    nxt = now.get("## Next") or before.get("## Next") or "(none)"
    return redact.mask("\n".join([
        "## Goal", "\n".join(goal) or "(none recorded)",
        "## Findings", findings or "(none recorded)",
        "## Files touched", _merge(now.get("## Files touched"), before.get("## Files touched")) or "- (none)",
        "## Troubleshooting", "\n".join(f"- {line}" for line in trouble) or "- (none)",
        "## Open questions", now.get("## Open questions") or "- (none)",
        "## Next", nxt]))


AS_IS = "as is"  # brief_meta "by" of a brief no pass rewrote (plan 28)


def as_is(cfg: dict, prev_brief: str, raw: str) -> str:
    """Plan 28 (D14): the brief of a handoff that is already short. When the raw note's Findings, joined by code to
    what the earlier brief carries (fallback with nothing cut), fit brief_max_words, that text is the brief and no
    pass rewrites it; "" when it is over the cap (the pass runs) or the note has no handoff headings."""
    if not _sections(raw):
        return ""
    text = fallback(prev_brief, raw, cut=False)
    return text if words(text) <= cfg["brief_max_words"] else ""


def _budget_arg(max_cost: float) -> str:
    """--max-budget-usd's value, rounded down to a millionth so a tiny remaining allowance is never raised."""
    text = f"{math.floor(max_cost * 1_000_000) / 1_000_000:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _ask(cfg: dict, exe: list, project_dir: str, prompt: str, schema: dict = BRIEF_SCHEMA, info: dict = None,
         model: str = "", *, max_cost: float = 0.0, safe_mode: bool = False):
    """One `claude -p` pass on `model` (default brief_model) with no tools, the answer shaped by `schema`; (answer
    dict, cost) or BriefError with the reason. `info`, when given, gets the pass's `turns` and its reported `cost`
    (None when unknown, set before any failure is raised so a paid failure keeps its cost). The replan and the
    whole-task handoff passes use it too. Plan 44: a positive `max_cost` adds --max-budget-usd; `safe_mode` (the
    supervisor only) adds --safe-mode and denies every MCP tool, so no CLAUDE.md, memory or plugin rides along."""
    cmd = claude_cli.brief_command(exe, model or cfg["brief_model"], schema)
    if max_cost and max_cost > 0:
        cmd += ["--max-budget-usd", _budget_arg(max_cost)]
    if safe_mode:
        cmd += ["--safe-mode", "--disallowedTools", "mcp__*"]
    if info is not None:
        info["cost"] = None
    try:
        out = subprocess.run(cmd, cwd=project_dir, input=prompt.encode("utf-8"), capture_output=True,
                             timeout=cfg["brief_timeout_s"], env=claude_cli.child_env(),
                             creationflags=claude_cli.NO_WINDOW)
    except subprocess.TimeoutExpired:
        raise BriefError(f"the brief took longer than {cfg['brief_timeout_s']} s")
    except OSError as exc:
        if info is not None:
            info["cost"] = 0.0  # it never started: nothing was paid
        raise BriefError(f"cannot start claude: {exc}")
    stdout = out.stdout.decode("utf-8", "replace")
    try:
        data = json.loads(stdout)
    except ValueError:
        raise BriefError("the brief returned no JSON: " + redact.clip(stdout, 120))
    if not isinstance(data, dict):
        raise BriefError("the brief returned no JSON object")
    cost = data.get("total_cost_usd")
    known = isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost) and cost >= 0
    if info is not None:
        info["cost"] = float(cost) if known else None
    if data.get("is_error"):
        detail = data.get("subtype") or data.get("terminal_reason") or "no reason given"
        raise BriefError("the brief failed: " + redact.clip(str(detail), 200))
    if info is not None:
        info["turns"] = int(data.get("num_turns") or 0)
    if out.returncode:
        raise BriefError(f"claude exited with code {out.returncode}")
    fields = data.get("structured_output")
    if not isinstance(fields, dict):
        raise BriefError("the brief returned no structured output")
    return fields, data.get("total_cost_usd") or 0


def _fields_ok(fields: dict) -> bool:
    """The brief answer has its four lists and its two strings."""
    return all(isinstance(fields.get(k), list) for k in ("findings", "files", "troubleshooting", "questions")) \
        and all(isinstance(fields.get(k), str) for k in ("goal", "next"))


def _first(found: list) -> str:
    return next((c["why"] for c in found if not c["ok"]), "")


def run_brief(cfg: dict, exe: list, task: dict, step: dict, next_step, prev_brief: str, raw: str,
              touched=()) -> dict:
    """Blocking (about 5 to 15 s; the service runs it in a thread). Never raises: any failure, or an answer that
    fails `checks` ends in `fallback`, except one that is only too long: its last findings are cut and it is checked
    again. {"text", "cost", "words", "model", "cut": [finding items left out], "fallback": "" | why, "checks",
    "turns"}."""
    cost, turns, why, dropped, found = 0, 0, "", [], []
    try:
        prompt = build_prompt(task, step, next_step, prev_brief, raw, budget(cfg, raw, prev_brief))
        info = {}
        fields, cost = _ask(cfg, exe, task["project_dir"], prompt, BRIEF_SCHEMA, info)
        turns = info.get("turns", 0)
        if not _fields_ok(fields):
            raise BriefError("the brief returned no structured output")
        fields = restore(fields, raw, prev_brief)
        text = render(fields)
        found = checks(text, cfg["brief_max_words"], raw, prev_brief, touched)
        why = _first(found)
        if why.startswith(("over ", "not shorter")):
            short = cut(fields, min(cfg["brief_max_words"], limit(raw, prev_brief) - 1))
            if short:
                dropped = [i for i in (_item(x) for x in fields["findings"][len(short["findings"]):]) if i]
                text = render(short)
                found = checks(text, cfg["brief_max_words"], raw, prev_brief, touched)
                why = _first(found)
    except BriefError as exc:
        text, why = "", str(exc)
    if why:
        text, dropped = fallback(prev_brief, raw), cut_lines(_sections(raw).get("## Findings", ""))
    return {"text": text, "cost": cost, "words": words(text), "model": cfg["brief_model"], "cut": dropped,
            "fallback": why, "checks": found, "turns": turns}


def brief_meta(res: dict, raw: str) -> dict:
    """What the brief pass did with a step's note, as task.json keeps it (s["brief_meta"], plan 25 reads it): words
    written and sent, the finding items left out, the checks, who wrote the text, the cost and turns, the fallback."""
    return {"raw_w": words(note_body(raw)), "sent_w": int(res.get("words") or 0), "cut": list(res.get("cut") or []),
            "checks": list(res.get("checks") or []), "by": "code" if res.get("fallback") else res.get("model", ""),
            "cost": round(float(res.get("cost") or 0), 6), "turns": int(res.get("turns") or 0),
            "fallback": res.get("fallback") or ""}
