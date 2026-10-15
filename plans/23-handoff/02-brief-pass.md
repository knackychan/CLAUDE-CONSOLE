# Task 2: The brief pass on six headings

> Contract: [README.md](README.md) 3.3, 3.4 (`brief_meta`), 3.9 (`brief_max_words`). Decisions D2 (`restore`), D5
> (the `paths` check). Depends on Task 1 (not committed yet). Run in the scratch copy: the code below is the final
> code. Ends with the commit of Tasks 1 and 2.

**Files**
- Modify: `console/compact.py` (the whole file below: `BRIEF_SCHEMA`, `render`, `note_body`, `_sections`, `_items`,
  `carried`, `restore`, `paths`, `_named`, `checks`, `check`, `cut`, `_merge`, `cut_lines`, `fallback`, `_ask(info)`,
  `_fields_ok`, `_first`, `run_brief(touched)`, `brief_meta`)
- Modify: `console/compact_prompt.md` (the answer paragraph)
- Modify: `console/paths.py` (`brief_max_words` 500)
- Modify: `tests/test_compact.py` (the whole file below), `tests/test_server.py` (one expectation)

**Lands on** plan 24 Task 2: plan 24 gave `_ask` its `schema` argument and moved the field check into `run_brief`
(`_fields_ok`); the file below keeps both, adds `info` (the pass's `num_turns`), and `_fields_ok` checks the six
fields. `replan.py` calls `compact._ask(cfg, exe, project_dir, prompt, schema)`: unchanged, `info` defaults to None.

## 2.1 `console/compact.py` (the whole file after this task)

```python
"""The brief (plan 17, README 3.6b; plan 23): between two steps a Haiku pass with no tools compacts the finished
step's raw note, plus the brief before it, into what the next step needs, under the same six headings. The pass
decides nothing: code puts the Goal and the Troubleshooting back whole, checks its answer, cuts findings first, and
falls back to fixed cuts, so a failed pass never stops the chain."""
import json
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


def fallback(prev_brief: str, raw: str) -> str:
    """Code only: the carried Goal and Troubleshooting whole, the raw note's Findings cut, its Files touched with the
    earlier brief's after them, its Open questions as they are, its Next (else the earlier brief's)."""
    now, before = _sections(raw), _sections(prev_brief)
    goal, trouble = carried(raw, prev_brief)
    findings = now.get("## Findings", "")
    if len(findings) > FINDINGS_CUT:
        findings = findings[:FINDINGS_CUT].rstrip() + "\n[cut]"
    nxt = now.get("## Next") or before.get("## Next") or "(none)"
    return redact.mask("\n".join([
        "## Goal", "\n".join(goal) or "(none recorded)",
        "## Findings", findings or "(none recorded)",
        "## Files touched", _merge(now.get("## Files touched"), before.get("## Files touched")) or "- (none)",
        "## Troubleshooting", "\n".join(f"- {line}" for line in trouble) or "- (none)",
        "## Open questions", now.get("## Open questions") or "- (none)",
        "## Next", nxt]))


def _ask(cfg: dict, exe: list, project_dir: str, prompt: str, schema: dict = BRIEF_SCHEMA, info: dict = None):
    """One `claude -p` pass on brief_model with no tools, the answer shaped by `schema`; (answer dict, cost) or
    BriefError with the reason. `info`, when given, gets the pass's `turns`. The replan pass uses it too."""
    cmd = claude_cli.brief_command(exe, cfg["brief_model"], schema)
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
    if info is not None:
        info["turns"] = int(data.get("num_turns") or 0)
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
```

D2 (a) is `restore` and its call in `run_brief`; with (b) drop the call and the `goal` / `troubleshooting` checks fail
to the fallback. D5 (a) is the `pool` line of `checks` (the facts paths in `touched`); with (b) the pool is the two
notes' `## Files touched` paths only.

The path rule (`_PATH`, `paths`): a token with a slash or backslash and an extension, or a bare name whose extension is
in `_EXT`; a trailing `:12` or `:12-30` is dropped; a URL is not a path; everything lower case with forward slashes.
`_named` matches exactly or when one path ends with `/` plus the other (`tasks.py` and `console/tasks.py`).

## 2.2 `console/compact_prompt.md`

```diff
diff --git a/console/compact_prompt.md b/console/compact_prompt.md
index 8c4d80d..0060650 100644
--- a/console/compact_prompt.md
+++ b/console/compact_prompt.md
@@ -11,8 +11,10 @@ $prev
 Raw handoff note of step $n ($kind):
 $raw
 
-Answer with the JSON object only, at most $words words in all: findings (short lines, file paths and line
-numbers kept), files (the paths with what changed, the earlier brief's included), questions (every open
-question of the raw note and of the earlier brief that is not answered yet, each in a few words; never drop one
-and never move one into next), next (one line for the next step; keep a `Next model: m/e` note only if the raw
-note had one).
+Answer with the JSON object only, at most $words words in all: goal (the Goal lines of the raw note, copied whole),
+findings (short lines, file paths and line numbers kept; leave out the least useful first), files (the paths with
+what changed, the earlier brief's included), troubleshooting (every Troubleshooting line of the earlier brief and of
+the raw note, copied whole: a fresh model cannot rediscover a dead end cheaply), questions (every open question of
+the raw note and of the earlier brief that is not answered yet, each in a few words; never drop one and never move
+one into next), next (one line for the next step; keep a `Next model: m/e` note only if the raw note had one). Name
+no file that neither note names.
```

## 2.3 `console/paths.py`

```diff
diff --git a/console/paths.py b/console/paths.py
index 6661387..ec03070 100644
--- a/console/paths.py
+++ b/console/paths.py
@@ -46,7 +48,7 @@ DEFAULTS = {
     "task_clear_on_done": True,
     "brief_on": True,  # the Haiku pass that compacts a step's note into the next step's brief
     "brief_model": "haiku",
-    "brief_max_words": 400,
+    "brief_max_words": 500,  # plan 23: six headings (Goal and Troubleshooting carried whole)
     "brief_timeout_s": 60,
     # USD per million tokens, API list prices (claude-api skill, 2026-10-06); fast mode costs 2x.
     # Haiku's higher price for prompts over 100K tokens is left out.
```

## 2.4 Tests

`tests/test_compact.py` (12 -> 17 test methods), the whole file after this task:

```python
import copy
import sys
import tempfile
import unittest
from pathlib import Path

from console import compact, paths, tasks

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
FIELDS = {"goal": "Fix add() in calc.py", "findings": ["add() is in calc.py:2", "test_add covers it"],
          "files": ["calc.py"], "troubleshooting": [], "questions": [], "next": "Fix add() and run the test"}
RAW = ("# Step 01: scout on haiku/low, session s1\n\n## Goal\nFix add() in calc.py; this step: find add()\n"
       "## Findings\nadd() is in calc.py:2\ntest_add in tests/test_calc.py covers it and fails on a negative number\n"
       "the callers in report.py and cli.py pass ints only\n## Files touched\n- (none)\n## Troubleshooting\n- (none)\n"
       "## Open questions\n- (none)\n## Next\nFix add() and run the test")
OLD_RAW = ("# Step 01: scout on haiku/low, session s1\n\n## Findings\nadd() is in calc.py:2\n"
           "## Files touched\n- (none)\n## Open questions\n- (none)\n## Next\nFix add() and run the test")


def make_task(project_dir="."):
    steps = tasks.plan_steps([{"kind": "scout", "goal": "Find add()"}, {"kind": "code", "goal": "Fix add()"}], 6)
    return tasks.new_task(project_dir, "APP", "Fix add", "Fix add() in calc.py", steps, "normal", {}, "", "auto", 1.0)


class BriefTest(unittest.TestCase):
    def test_schema_and_defaults(self):
        self.assertEqual(compact.BRIEF_SCHEMA["required"],
                         ["goal", "findings", "files", "troubleshooting", "questions", "next"])
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["findings"], {"type": "array", "items": {"type": "string"}})
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["troubleshooting"],
                         {"type": "array", "items": {"type": "string"}})
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["goal"], {"type": "string"})
        self.assertEqual(compact.BRIEF_SCHEMA["properties"]["next"], {"type": "string"})
        cfg = paths.DEFAULTS
        self.assertEqual((cfg["brief_on"], cfg["brief_model"], cfg["brief_max_words"], cfg["brief_timeout_s"]),
                         (True, "haiku", 500, 60))

    def test_render_and_check(self):
        text = compact.render(FIELDS)
        self.assertEqual(text, "## Goal\nFix add() in calc.py\n## Findings\n- add() is in calc.py:2\n- test_add covers it\n"
                               "## Files touched\n- calc.py\n## Troubleshooting\n- (none)\n"
                               "## Open questions\n- (none)\n## Next\nFix add() and run the test")
        self.assertEqual(compact.check(text, 500), "")
        long = compact.render(dict(FIELDS, findings=["word " * 30] * 20))  # 600 words
        self.assertEqual(compact.check(long, 500), "over 500 words")
        self.assertEqual(compact.check("nothing useful", 500), "missing: ## Goal")
        empty = compact.render({"goal": "", "findings": [], "files": [], "troubleshooting": [], "questions": [],
                                "next": ""})
        self.assertEqual(compact.check(empty, 500), "")
        self.assertTrue(empty.startswith("## Goal\n(none)\n## Findings\n- (none)\n"))
        messy = compact.render(dict(FIELDS, findings=["two\nlines  here", "key sk-abcdefghijkl1234"], next="a\nb",
                                    goal="line one\n\n  line   two  "))
        self.assertIn("- two lines here\n- key ***\n", messy)
        self.assertTrue(messy.startswith("## Goal\nline one\nline two\n## Findings"))
        self.assertTrue(messy.endswith("## Next\na b"))

    def test_checks_list_every_check_in_order(self):
        brief = compact.render(FIELDS)
        found = compact.checks(brief, 500, RAW, "")
        self.assertEqual([c["name"] for c in found], ["headings", "words", "shorter", "questions", "goal",
                                                      "troubleshooting", "continuity", "paths"])
        self.assertEqual(found[4], {"name": "goal", "ok": False, "why": "cut the Goal"})  # the pass's own goal line
        self.assertTrue(all(c["ok"] for c in found if c["name"] != "goal"))
        self.assertEqual([c["name"] for c in compact.checks(brief, 500)], ["headings", "words", "shorter", "questions"])

    def test_check_rejects_a_first_brief_not_shorter_than_its_note(self):
        brief = compact.restore(FIELDS, RAW, "")
        self.assertEqual(compact.check(compact.render(brief), 500, RAW + " pad" * 40, ""), "")
        short_raw = ("## Goal\ng\n## Findings\nx\n## Files touched\n- (none)\n## Troubleshooting\n- (none)\n"
                     "## Open questions\n- (none)\n## Next\ngo")
        self.assertTrue(compact.check(compact.render(FIELDS), 500, short_raw, "").startswith(
            "not shorter than what it compacts"))

    def test_check_lets_a_rolling_brief_carry_the_earlier_brief(self):
        prev = compact.render(dict(FIELDS, findings=["earlier step found " + "x " * 30]))
        brief = compact.render(compact.restore(dict(FIELDS, findings=FIELDS["findings"] + ["earlier step found it"]),
                                               RAW, prev))
        self.assertGreater(compact.words(brief), compact.words(compact.render(FIELDS)))
        self.assertEqual(compact.check(brief, 500, RAW, prev), "")

    def test_check_rejects_a_brief_that_drops_open_questions(self):
        raw = RAW.replace("## Open questions\n- (none)", "## Open questions\n- Fred: green suite or no new failures?")
        raw += " pad" * 40
        dropped = compact.render(compact.restore(FIELDS, raw, ""))
        kept = compact.render(compact.restore(dict(FIELDS, questions=["Fred: green suite or no new failures?"]), raw, ""))
        self.assertEqual(compact.check(dropped, 500, raw, ""), "dropped the open questions")
        self.assertEqual(compact.check(kept, 500, raw, ""), "")

    def test_goal_and_troubleshooting_are_carried_whole(self):
        prev = compact.render(dict(FIELDS, troubleshooting=["py -3.12 fails here: use py -3.14"]))
        raw = RAW.replace("## Troubleshooting\n- (none)", "## Troubleshooting\n- the fake needs PYTHONUTF8=1")
        goal, trouble = compact.carried(raw, prev)
        self.assertEqual(goal, ["Fix add() in calc.py; this step: find add()"])
        self.assertEqual(trouble, ["py -3.12 fails here: use py -3.14", "the fake needs PYTHONUTF8=1"])
        paraphrased = dict(FIELDS, troubleshooting=["use a newer python"])
        self.assertEqual(compact.check(compact.render(paraphrased), 500, raw, prev), "cut the Goal")
        self.assertEqual(compact.check(compact.render(dict(paraphrased, goal=goal[0])), 500, raw, prev),
                         "cut the Troubleshooting")
        fixed = compact.restore(paraphrased, raw, prev)
        self.assertEqual((fixed["goal"], fixed["troubleshooting"]), (goal[0], trouble))
        self.assertEqual(paraphrased["troubleshooting"], ["use a newer python"])  # the answer itself is not changed
        self.assertEqual(compact.check(compact.render(fixed), 500, raw, prev), "")
        self.assertEqual(compact.carried(OLD_RAW, "")[0], [])  # an old note has no Goal: nothing to carry
        self.assertEqual(compact.carried(OLD_RAW, prev)[0], ["Fix add() in calc.py"])  # the earlier brief's Goal

    def test_continuity_keeps_a_file_of_the_earlier_files_touched(self):
        prev = compact.render(dict(FIELDS, files=["console/tasks.py (six headings)"]))
        raw = RAW.replace("## Files touched\n- (none)", "## Files touched\n- console/compact.py (checks)")
        lost = compact.restore(dict(FIELDS, files=["console/compact.py"]), raw, prev)
        self.assertEqual(compact.check(compact.render(lost), 500, raw, prev), "names no file of the earlier Files touched")
        kept = compact.restore(dict(FIELDS, files=["console/compact.py", "tasks.py"]), raw, prev)  # a short name counts
        self.assertEqual(compact.check(compact.render(kept), 500, raw, prev), "")
        first = compact.restore(dict(FIELDS, files=[]), raw, "")
        self.assertNotIn("names no file", compact.check(compact.render(first), 500, raw, ""))  # no earlier list

    def test_no_invented_path(self):
        brief = compact.restore(dict(FIELDS, findings=["add() is in calc.py:2", "see web/app.js:40"]), RAW, "")
        self.assertEqual(compact.check(compact.render(brief), 500, RAW, ""), "names a path no step touched: web/app.js")
        self.assertEqual(compact.check(compact.render(brief), 500, RAW, "", touched=["web/app.js"]), "")
        self.assertEqual(compact.paths("calc.py:2, tests/test_calc.py::test_add, D:\\WORK\\APP\\x.py, ./y.md, e.g. "
                                       "i.e. 0.03 v1.2.3 https://code.claude.com/docs/a.html README.md"),
                         {"calc.py", "tests/test_calc.py", "d:/work/app/x.py", "y.md", "readme.md"})

    def test_fallback_keeps_goal_files_trouble_and_cuts_findings(self):
        raw = ("# Step 01: scout on haiku/low, session s1\n\n## Goal\nship it\n## Findings\n" + "a" * 3000 +
               "\nlast line\n## Files touched\n- a.py (x)\n- b.py (y)\n## Troubleshooting\n- pip is offline\n"
               "## Open questions\n- which one?\n## Next\nDo the thing")
        prev = compact.render(dict(FIELDS, files=["a.py (x)", "c.py (z)"], troubleshooting=["tests need -s tests"]))
        text = compact.fallback(prev, raw)
        self.assertEqual(tasks.check_handoff(text), "")
        self.assertIn("## Goal\nship it\n## Findings\n", text)
        self.assertIn("## Files touched\n- a.py (x)\n- b.py (y)\n- c.py (z)\n## Troubleshooting\n- tests need -s tests\n"
                      "- pip is offline\n## Open questions\n- which one?\n## Next\nDo the thing", text)
        self.assertIn("a" * 1500, text)
        self.assertNotIn("a" * 1501, text)
        self.assertEqual(compact.cut_lines(compact._sections(raw)["## Findings"]), ["a" * 3000, "last line"])
        no_next = "## Findings\nseen\n## Files touched\n- (none)\n## Open questions\n- (none)"
        self.assertTrue(compact.fallback(compact.render(FIELDS), no_next).endswith("## Next\nFix add() and run the test"))
        self.assertTrue(compact.fallback("", no_next).endswith("## Next\n(none)"))
        marked = "HANDOFF\n" + RAW.split("\n\n", 1)[1] + "\nEND HANDOFF"  # a raw message with the markers
        self.assertEqual(tasks.check_handoff(compact.fallback("", marked)), "")
        self.assertEqual(tasks.check_handoff(compact.fallback("", "")), "")  # nothing to cut from still checks out
        self.assertEqual(tasks.check_handoff(compact.fallback("", OLD_RAW)), "")  # an old note gives six headings

    def test_build_prompt(self):
        task = make_task()
        text = compact.build_prompt(task, tasks.step(task, 1), tasks.step(task, 2), "", RAW + "\ncost $HOME")
        self.assertTrue(text.startswith("Compact the handoff note"))
        self.assertIn("Task: Fix add", text)
        self.assertIn("Next step (2 of 3, code): Fix add()", text)
        self.assertIn("Raw handoff note of step 1 (scout):\n" + RAW, text)
        self.assertIn("cost $HOME", text)
        self.assertIn("Earlier brief (what the steps before already kept):\n(none", text)
        self.assertIn("goal (the Goal lines of the raw note, copied whole)", text)
        self.assertIn("troubleshooting (every Troubleshooting line", text)
        again = compact.build_prompt(task, tasks.step(task, 2), tasks.step(task, 3), "PREV BRIEF", RAW)
        self.assertIn("PREV BRIEF", again)
        last = compact.build_prompt(task, tasks.step(task, 3), None, "", RAW)
        self.assertIn("this was the last step", last)

    def test_prompt_names_the_goal_and_a_word_target(self):
        task = make_task()
        task["goal"] = "Goal: " + "g" * 600
        text = compact.build_prompt(task, tasks.step(task, 1), tasks.step(task, 2), "", RAW, 120)
        self.assertIn("Task: Goal: ggg", text)
        self.assertNotIn("g" * 400, text)
        self.assertIn("at most 120 words in all", text)
        self.assertIn("never drop one", text)
        self.assertNotIn("$", text)
        self.assertEqual(compact.budget({"brief_max_words": 500}, "w " * 1000, ""), 500)
        self.assertEqual(compact.budget({"brief_max_words": 500}, "w " * 50, ""), 60)
        self.assertEqual(compact.budget({"brief_max_words": 500}, "w " * 200, "w " * 100), 180)

    def test_run_brief_uses_the_fake(self):
        cfg = copy.deepcopy(paths.DEFAULTS)
        with tempfile.TemporaryDirectory() as project:
            task = make_task(project)
            result = compact.run_brief(cfg, FAKE, task, tasks.step(task, 1), tasks.step(task, 2), "", RAW)
        self.assertEqual(result["text"], compact.render(compact.restore(FIELDS, RAW, "")))
        self.assertIn("## Goal\nFix add() in calc.py; this step: find add()\n", result["text"])
        self.assertEqual((result["cost"], result["fallback"], result["model"], result["cut"]), (0.03, "", "haiku", []))
        self.assertEqual(result["turns"], 5)
        self.assertTrue(all(c["ok"] for c in result["checks"]))
        self.assertEqual(len(result["checks"]), 8)
        self.assertLess(result["words"], 500)
        self.assertEqual(result["words"], len(result["text"].split()))

    def test_run_brief_cuts_an_over_long_answer_instead_of_dropping_it(self):
        cfg = copy.deepcopy(paths.DEFAULTS)
        with tempfile.TemporaryDirectory() as project:
            task = make_task(project)
            raw = RAW.replace("## Files touched", "word " * 120 + "\n## Files touched") + "\nLONG"
            result = compact.run_brief(cfg, FAKE, task, tasks.step(task, 1), tasks.step(task, 2), "", raw)
        self.assertEqual(result["fallback"], "")
        self.assertGreater(len(result["cut"]), 0)
        self.assertTrue(result["cut"][-1].startswith("finding 79 says"))  # the last findings go first
        self.assertLessEqual(result["words"], 500)
        self.assertEqual(result["words"], len(result["text"].split()))
        self.assertIn("finding 0 says", result["text"])
        self.assertNotIn("finding 79 says", result["text"])
        self.assertEqual(compact.check(result["text"], 500), "")

    def test_cut_keeps_every_heading_but_findings(self):
        fields = dict(FIELDS, findings=[f"finding {i} " + "w " * 40 for i in range(20)], files=["calc.py"],
                      troubleshooting=["pip is offline"], questions=["which pi?"], next="Fix add()")
        cut = compact.cut(fields, 200)
        self.assertEqual((cut["files"], cut["troubleshooting"], cut["questions"], cut["next"], cut["goal"]),
                         (["calc.py"], ["pip is offline"], ["which pi?"], "Fix add()", FIELDS["goal"]))
        self.assertLessEqual(compact.words(compact.render(cut)), 200)
        self.assertEqual(cut["findings"], fields["findings"][:len(cut["findings"])])
        self.assertEqual(len(fields["findings"]), 20)  # the answer itself is not changed
        self.assertIsNone(compact.cut(dict(fields, questions=["q " * 300]), 200))  # one finding left, still over

    def test_run_brief_falls_back_on_a_bad_answer(self):
        cfg = copy.deepcopy(paths.DEFAULTS)
        with tempfile.TemporaryDirectory() as project:
            task = make_task(project)
            one, two = tasks.step(task, 1), tasks.step(task, 2)
            huge = compact.run_brief(cfg, FAKE, task, one, two, "", RAW + "\nHUGE")
            self.assertEqual(huge["fallback"], "over 500 words")  # one finding alone is too long: nothing to cut
            self.assertEqual(huge["text"], compact.fallback("", RAW + "\nHUGE"))
            self.assertEqual(huge["cost"], 0.03)  # the pass was paid for even though the answer was dropped
            self.assertEqual(huge["checks"][1], {"name": "words", "ok": False, "why": "over 500 words"})
            broken = compact.run_brief(cfg, FAKE, task, one, two, "", RAW + "\nBROKEN")
            self.assertIn("no JSON", broken["fallback"])
            self.assertEqual(broken["text"], compact.fallback("", RAW + "\nBROKEN"))
            self.assertEqual((broken["cost"], broken["checks"], broken["turns"]), (0, [], 0))
            slow = compact.run_brief(dict(cfg, brief_timeout_s=1), FAKE, task, one, two, "", RAW + "\nSLOW")
            self.assertEqual(slow["fallback"], "the brief took longer than 1 s")
            self.assertEqual(slow["text"], compact.fallback("", RAW + "\nSLOW"))
            gone = compact.run_brief(cfg, ["no-such-claude-exe"], task, one, two, "", RAW)
            self.assertIn("cannot start claude", gone["fallback"])
            self.assertEqual(tasks.check_handoff(gone["text"]), "")

    def test_brief_meta_shape(self):
        res = {"text": "x", "cost": 0.0123456789, "words": 290, "model": "haiku", "cut": ["finding 9"],
               "fallback": "", "checks": [{"name": "headings", "ok": True, "why": ""}], "turns": 2}
        meta = compact.brief_meta(res, RAW)
        self.assertEqual(sorted(meta), ["by", "checks", "cost", "cut", "fallback", "raw_w", "sent_w", "turns"])
        self.assertEqual((meta["raw_w"], meta["sent_w"], meta["cut"], meta["by"], meta["cost"], meta["turns"],
                          meta["fallback"]),
                         (compact.words(compact.note_body(RAW)), 290, ["finding 9"], "haiku", 0.012346, 2, ""))
        self.assertNotIn("# Step", compact.note_body(RAW))
        off = compact.brief_meta({"text": "y", "cost": 0, "words": 40, "fallback": "brief is off"}, RAW)
        self.assertEqual((off["by"], off["checks"], off["turns"], off["cut"], off["fallback"]),
                         ("code", [], 0, [], "brief is off"))


if __name__ == "__main__":
    unittest.main()
```

- `test_schema_and_defaults`: the six required fields in order; `brief_max_words` 500.
- `test_render_and_check`, `test_checks_list_every_check_in_order` (the eight names of README 3.3),
  `test_check_rejects_a_first_brief_not_shorter_than_its_note`, `test_check_lets_a_rolling_brief_carry_the_earlier_brief`,
  `test_check_rejects_a_brief_that_drops_open_questions`.
- New: `test_goal_and_troubleshooting_are_carried_whole` (D2), `test_continuity_keeps_a_file_of_the_earlier_files_touched`,
  `test_no_invented_path` (D5, the suffix match, a URL and `:line`), `test_fallback_keeps_goal_files_trouble_and_cuts_findings`,
  `test_brief_meta_shape`.
- `test_run_brief_uses_the_fake`, `test_run_brief_cuts_an_over_long_answer_instead_of_dropping_it` (`cut` is a list of
  items), `test_cut_keeps_every_heading_but_findings`, `test_run_brief_falls_back_on_a_bad_answer` (`over 500 words` on
  HUGE, `checks` in the result).

`tests/test_server.py`, the one expectation the 500 changes:

```diff
diff --git a/tests/test_server.py b/tests/test_server.py
index 60de90e..fdfc4c3 100644
--- a/tests/test_server.py
+++ b/tests/test_server.py
@@ -1176,11 +1245,68 @@ class TaskServerTest(RunServerTest):
         # the brief request holds the next step's goal, so HUGE goes in step 2's
         tid = self.make_task(steps=[self.TWO[0], {"kind": "explain", "goal": "say it HUGE"}])
         task = self.until(tid, self.at(2), "step 2 starts")
-        self.assertIn("brief fallback: over 400 words", [c["why"] for c in self.chain(tid)])
+        self.assertIn("brief fallback: over 500 words", [c["why"] for c in self.chain(tid)])
         text = (self.folder / "tasks" / tid / "steps" / "01-scout.brief.md").read_text(encoding="utf-8")
         self.assertIn("add() is in calc.py:2", text)
         self.assertEqual(task["steps"][1]["state"], "running")
 
+    # -- plan 23: facts, brief_meta, the carried Troubleshooting, lessons by kind -----------------------------------
+    @unittest.skipUnless(subprocess.run(["git", "--version"], capture_output=True).returncode == 0, "no git")
+    def test_facts_are_read_when_a_step_ends(self):
+        git = lambda *a: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=self.project,
+                                        capture_output=True, check=True)
+        (self.project / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
+        git("init", "-q")
+        git("add", "calc.py")
+        git("commit", "-q", "-m", "start")
+        head = claude_cli.git_head(str(self.project))
+        tid = self.make_task(steps=self.TWO, words="HANDOFF-OK TESTS-OK")
+        self.until(tid, self.at(1), "step 1 starts")
+        self.assertEqual(self.hub.tasks[tid]["steps"][0]["git_base"], {"commit": head, "files": {}})
+        (self.project / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")  # the step's work
+        (self.project / "notes.md").write_text("one\ntwo\n", encoding="utf-8")
+        task = self.until(tid, self.at(2), "step 2 starts")
+        s1 = task["steps"][0]
+        self.assertEqual(s1["facts"], {"files": 2, "plus": 3, "minus": 1, "tests": "23 OK"})
+        self.assertEqual(s1["end_commit"], head)
+        text = (self.folder / "tasks" / tid / "steps" / "01-scout.facts.md").read_text(encoding="utf-8")
+        self.assertEqual(text.splitlines()[:4], [f"git diff --stat {head[:7]}..working tree", " calc.py  | +1 -1",
+                                                 " notes.md | +2 -0", "2 files changed, +3 -1"])
+        self.assertIn("Ran 23 tests in 0.412s", text)
+        prompt = self.prompt_of(task["steps"][1]["session"])
+        self.assertIn("Facts the service read when that step ended", prompt)
+        self.assertIn(" calc.py  | +1 -1", prompt)  # under the brief, never compacted
+        self.assertEqual(self.task(tid)[1]["facts"]["1"], text)
+
+    def test_brief_meta_and_the_carried_troubleshooting(self):
+        tid = self.make_task(steps=self.TWO, words="HANDOFF-OK TROUBLE")
+        task = self.until(tid, self.at(2), "step 2 starts")
+        meta = task["steps"][0]["brief_meta"]
+        self.assertEqual((meta["by"], meta["fallback"], meta["cut"], meta["turns"]), ("haiku", "", [], 5))  # the fake brief pass reports 5 turns
+        self.assertGreater(meta["raw_w"], meta["sent_w"])
+        self.assertEqual([c["name"] for c in meta["checks"]], ["headings", "words", "shorter", "questions", "goal",
+                                                               "troubleshooting", "continuity", "paths"])
+        self.assertTrue(all(c["ok"] for c in meta["checks"]))
+        brief_text = (self.folder / "tasks" / tid / "steps" / "01-scout.brief.md").read_text(encoding="utf-8")
+        self.assertIn("## Troubleshooting\n- py -3.12 fails here: use py -3.14", brief_text)  # the pass dropped it
+        self.assertIn("## Goal\nFix add() in calc.py; this step: find add() and its callers", brief_text)
+        self.assertEqual(task["steps"][0]["facts"]["files"], 0)  # not a git repo: no file, no test
+        self.assertIn("git: no repository here", self.task(tid)[1]["facts"]["1"])
+
+    def test_lessons_reach_steps_of_their_kind(self):
+        now = time.time()
+        levers.add_lesson(self.folder, levers.lesson_line("proj", "explain", "say the file before the line", now))
+        levers.add_lesson(self.folder, levers.lesson_line("proj", "chat", "a chat lesson stays out", now))
+        levers.add_lesson(self.folder, levers.lesson_line("other", "explain", "another project stays out", now))
+        tid = self.make_task(steps=self.TWO)
+        task = self.until(tid, self.at(2), "step 2 starts")
+        first, second = (self.prompt_of(s["session"]) for s in task["steps"])
+        self.assertNotIn("Lessons from earlier", first)  # no scout lesson
+        self.assertIn("Lessons from earlier explain steps in this project", second)
+        self.assertIn("say the file before the line", second)
+        self.assertNotIn("a chat lesson stays out", second)
+        self.assertNotIn("another project stays out", second)
+
     def test_a_long_brief_is_cut_not_dropped(self):
         tid = self.make_task(steps=[self.TWO[0], {"kind": "explain", "goal": "say it LONG"}])
         self.until(tid, self.at(2), "step 2 starts")
```

## 2.5 Steps

1. `tests/test_compact.py` as above and the test_server line. Run `py -m unittest tests.test_compact`: the new tests
   fail.
2. `console/compact.py`, `console/compact_prompt.md`, the `paths.py` line.
3. `py -m unittest discover -s tests`: all OK but the four environment failures of the Linux baseline (none on Fred's
   Windows). Linux scratch: 340 tests (326 + 14).
4. Commit Tasks 1 and 2: `Plan 23 Tasks 1-2: six-heading HANDOFF block everywhere, the brief pass carries Goal and
   Troubleshooting whole, continuity checks, brief_max_words 500 (N tests OK)` with the attribution lines.

**Drift guards**
- The brief pass never sees the facts text; `touched` is a list of paths (Task 5 fills it).
- `checks` always returns all eight entries when `raw` is given, in the README order; the window and plan 25 show
  them by name.
- `cut` removes findings only; Goal, Files touched, Troubleshooting, Open questions and Next stay whole.
- `brief_meta.by` is `code` whenever `fallback` is non-empty, whatever model ran first.
