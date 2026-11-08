# Task 3: card text, live lines, signals, the digest, the prompt, the answer check and the pass

> Contract: [README.md](README.md) 3.7, 3.9 (the card fields), 3.12; decisions D3, D4, D11.
> Mirrors plan 44's pass: `supervisor.build_prompt` (kind body, code reminder, digest last), `supervisor.run`
> (`compact._ask`, safe mode, a copied cfg for the timeout), `supervisor.shape` (no answer on a bad shape).

**Files**
- Modify: `console/superagent.py` (append this task's section; nothing above it changes)
- Modify: `tests/fake_claude.py` (the docstring line, the `superagent()` branch, one line in `prep()`)
- Modify: `tests/test_superagent.py` (`DescribeTest`, `LinesTest`, `DigestTest`, `AnswerTest`, `RunTest`)

Commit boundary: `feat: super agent digest, answer check and bounded pass (plan 58 T3)`.

## 3.1 `console/superagent.py`, part 3 (append)

```python
# -- card text, the digest and the pass (Task 3) --------------------------------------------------------------

ASK_MAX = 300  # characters of one card's ask line
OPTION_MAX = 120  # characters of one option, a default or an open question
DIGEST_MAX = 32 * 1024  # bytes of the digest
OMIT_ROOM = 512  # bytes kept for the "omitted" lines of optional blocks that do not fit
ITEMS_MAX = 30  # items with a handle in one digest; the rest are counted and keep their place
ITEM_MAX = 600  # characters of one item's block
LIVE_MAX = 40  # live task lines, and signals, in one digest
QUESTIONS_MAX = 3  # open questions shown per task item
DO = ("forward", "batch", "later")
SAY_MAX = WHY_MAX = 200
BATCH_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
JUDGE_KINDS = ("stuck", "failed_twice")  # a new item of these kinds makes the pass a sonnet pass (D-b)
SLOW_MIN_S = 60  # a running step is never slow before a minute
SLOW_SAMPLES = 3  # ended steps of a kind before their median counts


def _clip(text, limit: int) -> str:
    """Masked, whitespace collapsed, at most `limit` characters; "" for None."""
    return redact.clip(redact.mask("" if text is None else str(text)), limit)


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _age(seconds) -> str:
    """A duration as the digest writes it: 45 s, 12 min, 2 h 5 min."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    return f"{s // 3600} h {s % 3600 // 60} min"


def describe(item: dict, task, row: dict, view: dict, level: str, timeout_s, now: float) -> dict:
    """README 3.9: one item with its card fields, every text masked and clipped (pure). `task` is None for a session
    item; `row` is its snapshot row (server.task_row, or the session row); `view` is Hub.actions(task) ({} for a
    session, or when it failed). ask: one line; options and default: a decision's texts while it is not taken;
    left_s: the seconds before the default is taken, at auto only; supervisor: the task supervisor's say line;
    source: a session's harness."""
    out = dict(item, ask="", options=[], default="", left_s=None, level=level, supervisor="", source="")
    if item["type"] == "session":
        ask = str(row.get("text") or row.get("state") or "")
        if row.get("stop_question"):
            ask += ": " + str(row["stop_question"])
        out.update(ask=_clip(ask, ASK_MAX), source=_clip(row.get("source"), 40))
        return out
    kind = item["kind"]
    if kind == "question":
        ask = "asks: " + str(row.get("asks") or "")
    elif kind == "hand_off":
        ask = "hand off: " + str(row.get("hand_off") or "")
    else:
        ask = view.get("line") or task.get("why") or task.get("state") or ""
    out.update(ask=_clip(ask, ASK_MAX), supervisor=_clip((row.get("supervisor") or {}).get("say"), ASK_MAX))
    decision = task.get("decision") if isinstance(task.get("decision"), dict) else {}
    if kind == "decision" and not decision.get("taken"):
        options = [o for o in decision.get("options") or [] if isinstance(o, dict)]
        out["options"] = [_clip(o.get("text"), OPTION_MAX) for o in options]
        picked = next((o for o in options if o.get("key") == decision.get("default")), None)
        out["default"] = _clip(picked.get("text"), OPTION_MAX) if picked else ""
        if level == "auto" and picked and _num(decision.get("asked")) and _num(timeout_s):
            out["left_s"] = max(0, int(timeout_s - (now - decision["asked"])))
    return out


def live_tasks(by_id: dict) -> list:
    """The tasks in flight (not done, stopped or handed, never accepted), the most recently changed first."""
    live = [t for t in by_id.values() if t.get("state") not in ("done", "stopped", "handed") and not t.get("accepted")]
    return sorted(live, key=lambda t: (-float(t.get("updated") or 0), t["id"]))


def _started(step: dict):
    """When the step's current run started: its last attempt's start, else the step's; None when unknown."""
    runs = tasks.attempts(step)
    for value in ((runs[-1].get("started") if runs else None), step.get("started")):
        if _num(value):
            return float(value)
    return None


def task_line(task: dict, level: str, now: float) -> str:
    """One live task as the digest lists it, masked, at most LINE_MAX characters: label and project, state, the
    current step and its route, how long it has run (or its state), the cost so far, retries, FAIL verdicts, level."""
    steps = task.get("steps") or []
    cs = tasks.current_step(task) if task.get("current") else None
    parts = [f"{tasks.label(task['id']) or task['id']} {task.get('project') or ''}".strip(), str(task.get("state") or "")]
    if cs:
        parts.append(f"step {cs['n']}/{len(steps)} {cs['kind']} "
                     f"{cs.get('model') or cs.get('pick') or 'auto'}/{cs.get('effort') or 'auto'}")
        started = _started(cs)
        parts.append(f"{_age(now - started)} in step" if cs.get("state") == "running" and started is not None
                     else str(cs.get("state") or ""))
    cost = sum(tasks.step_cost(s) for s in steps)
    fails = sum(1 for s in steps if s.get("kind") == "verify" and s.get("verdict") == "FAIL")
    retries = sum(int(s.get("retries") or 0) for s in steps)
    parts += [f"${cost:.2f}", f"retries {retries}", f"FAILs {fails}", f"level {level}"]
    return _clip(" · ".join(p for p in parts if p), LINE_MAX)


def signals(by_id: dict, now: float) -> list:
    """The two watchdog signals of slice 1 (D4), from saved step data only. `slow`: a running step in its current run
    for at least SLOW_MIN_S and for more than twice the median of its kind's ended steps (done or failed, both times
    known, at least SLOW_SAMPLES of them across every task). `same_fail`: a live task whose last two FAIL verifies
    carry the same, non-empty detail. [{task, kind, line}] in live_tasks order, at most LIVE_MAX, lines masked."""
    spans = {}
    for task in by_id.values():
        for s in task.get("steps") or []:
            if s.get("state") in ("done", "failed") and _num(s.get("started")) and _num(s.get("ended")) \
                    and s["ended"] >= s["started"]:
                spans.setdefault(s.get("kind"), []).append(s["ended"] - s["started"])
    out = []
    for task in live_tasks(by_id):
        label = tasks.label(task["id"]) or task["id"]
        cs = tasks.current_step(task) if task.get("current") else None
        if cs and cs.get("state") == "running":
            started, ended = _started(cs), spans.get(cs.get("kind")) or []
            if started is not None and len(ended) >= SLOW_SAMPLES:
                median, took = statistics.median(ended), now - started
                if took >= SLOW_MIN_S and took > 2 * median:
                    out.append({"task": label, "kind": "slow", "line": _clip(
                        f"{label}: step {cs['n']} {cs['kind']} has run {_age(took)}, over twice the median "
                        f"{_age(median)} of {len(ended)} ended {cs['kind']} steps", LINE_MAX)})
        fails = [s for s in task.get("steps") or [] if s.get("kind") == "verify" and s.get("verdict") == "FAIL"]
        if len(fails) >= 2 and fails[-1].get("verdict_detail") \
                and fails[-1].get("verdict_detail") == fails[-2].get("verdict_detail"):
            out.append({"task": label, "kind": "same_fail", "line": _clip(
                f"{label}: verify steps {fails[-2]['n']} and {fails[-1]['n']} failed the same way: "
                f"{fails[-1]['verdict_detail']}", LINE_MAX)})
    return out[:LIVE_MAX]


def fingerprint(live: list, by_id: dict, sigs: list) -> str:
    """16 hex of the SHA-256 over what a sweep compares (D-c): the item keys; each live task's state, current step,
    the step's state and retries, and its cost in whole dollars (cents would move at every sweep while a task runs);
    the signals. Equal to the last pass's: the sweep starts nothing."""
    rows = []
    for task in live_tasks(by_id):
        cs = tasks.current_step(task) if task.get("current") else None
        cost = sum(tasks.step_cost(s) for s in task.get("steps") or [])
        rows.append([task["id"], task.get("state"), task.get("current") or 0, cs.get("state") if cs else "",
                     int(cs.get("retries") or 0) if cs else 0, int(cost)])
    data = [sorted(i["key"] for i in live), rows, sorted([s["task"], s["kind"]] for s in sigs)]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


def levels(cfg: dict) -> str:
    """The head's Levels line: the global level, then each project's own level (config supervisor_projects)."""
    parts = [f"global {cfg.get('supervisor_mode') or 'gated'}"]
    projects = cfg.get("supervisor_projects") if isinstance(cfg.get("supervisor_projects"), dict) else {}
    parts += [f"{Path(str(p)).name or p} {m}" for p, m in sorted(projects.items()) if isinstance(m, str)]
    return _clip("; ".join(parts), LINE_MAX)


def trigger_words(events) -> str:
    """A wake's events as the head's Triggers line, for example "2 new items, 1 task ended, sweep"."""
    count = {}
    for what, _ in events or ():
        count[what] = count.get(what, 0) + 1
    words = []
    for what, one, many in (("new", "new item", "new items"), ("back", "back from later", "back from later"),
                            ("ended", "task ended", "tasks ended")):
        if count.get(what):
            words.append(f"{count[what]} {one if count[what] == 1 else many}")
    words += [what for what in ("sweep", "asked") if count.get(what)]
    return ", ".join(words) or "none"


def item_block(handle: str, item: dict, now: float) -> str:
    """One item of the digest, at most ITEM_MAX characters. Its card texts were masked by describe; the project, the
    title and the open questions (`questions`, set by the Hub) are masked here."""
    who = f"task {item['label']}" if item["type"] == "task" else f"observed chat {item['label']}"
    head = [handle, f"always ({item['always']})" if item.get("always") else "", who, _clip(item.get("project"), 60),
            _clip(item.get("title"), OPTION_MAX)]
    meta = [f"kind {item['kind']}", f"seen {_age(item.get('age_s') or 0)} ago", f"level {item.get('level') or ''}"]
    if item.get("source"):
        meta.append(item["source"])
    lines = [" · ".join(p for p in head if p), "   " + " · ".join(meta)]
    if item.get("ask"):
        lines.append("   ask: " + item["ask"])
    if item.get("options"):
        text = "   options: " + " ".join(f"{k}) {o}" for k, o in enumerate(item["options"], 1))
        if item.get("default"):
            text += f" · default {item['default']}"
            if item.get("left_s") is not None:
                text += f", taken in {_age(item['left_s'])}"
        lines.append(text)
    if item.get("supervisor"):
        lines.append("   task supervisor: " + item["supervisor"])
    questions = [_clip(q, OPTION_MAX) for q in (item.get("questions") or [])[:QUESTIONS_MAX]]
    if questions:
        lines.append("   open questions: " + " | ".join(questions))
    if item.get("do"):
        rank = item["rank"] if item.get("rank") is not None else "-"
        lines.append(f"   last pass: {item['do']} rank {rank}: {item.get('say') or ''}".rstrip())
    text = "\n".join(lines)
    return text if len(text) <= ITEM_MAX else text[:ITEM_MAX - 1] + "…"


def digest(head: dict, items_: list, orders: str, notes: str, live_lines: list, sigs: list, you: str,
           now: float) -> tuple:
    """(text, handles): the pass's digest, at most DIGEST_MAX bytes (README 3.7). `head` is {n, trigger, spent,
    day_usd, levels}. The head and the items are always in: the first ITEMS_MAX items, in the order given, get the
    handles I1, I2, ... (fewer when their blocks do not fit; the rest are counted and keep their place). The optional
    blocks fill what is left in priority order (standing orders, notes, signals, live tasks); one that does not fit
    is replaced by its title and size. `handles` maps a handle to its item's key. Pure."""
    you = you or "the user"
    top = "\n".join([f"# Super agent pass {head['n']} · {time.strftime('%Y-%m-%d %H:%M', time.localtime(now))}",
                     "Triggers: " + (head.get("trigger") or "none"),
                     f"Spend today: ${head.get('spent') or 0:.2f} of ${head.get('day_usd') or 0:.2f} a day",
                     "Levels: " + (head.get("levels") or "")])

    def item_part(shown):
        if not shown:
            return f"Items for {you}: none."
        more = len(items_) - len(shown)
        span = "handle I1" if len(shown) == 1 else f"handles I1 to I{len(shown)}"
        tail = f"; {more} more not shown, they keep their place" if more else ""
        return "\n".join([f"Items for {you} ({len(shown)}, {span}{tail}):"] +
                         [item_block(f"I{k}", item, now) for k, item in enumerate(shown, 1)])

    shown = items_[:ITEMS_MAX]
    while shown and _size(top) + _size(item_part(shown)) + OMIT_ROOM > DIGEST_MAX:
        shown = shown[:-1]
    items_text = item_part(shown)
    handles = {f"I{k}": item["key"] for k, item in enumerate(shown, 1)}
    extra = len(live_lines) - LIVE_MAX
    blocks = {"orders": f"Standing orders from {you}:\n" + (orders or "none"),
              "notes": "Your notes from the last pass:\n" + (notes.rstrip("\n") if notes else "none"),
              "signals": "Signals:\n" + ("\n".join("- " + s["line"] for s in sigs) if sigs else "none"),
              "live": f"Live tasks ({len(live_lines)}):\n" + ("\n".join(
                  live_lines[:LIVE_MAX] + ([f"... and {extra} more"] if extra > 0 else [])) or "none")}
    room = DIGEST_MAX - OMIT_ROOM - _size(top) - _size(items_text)
    for name in ("orders", "notes", "signals", "live"):  # priority order
        need = _size(blocks[name]) + 2
        if need <= room:
            room -= need
        else:
            blocks[name] = f"{blocks[name].split(chr(10), 1)[0].rstrip(':')}: omitted ({_size(blocks[name])} bytes)"
    order = [top, blocks["orders"], blocks["notes"], items_text, blocks["live"], blocks["signals"]]
    return "\n\n".join(order) + "\n", handles


SCHEMA_REMINDER = ("Answer with one JSON object that matches the given schema: items (at most one entry per handle, "
                   "its handle as key), digest (at most three lines) and notes. The digest follows.")


def build_prompt(raw: str, digest_text: str, you: str, notes_lines: int) -> str:
    """The pass's stdin: the super kind body ($you, $You and $lines filled), the schema reminder (code, so a later
    slice changes the contract without a Reset of an edited super.md), then the digest last and untouched (its
    dollar signs are text, never template slots)."""
    you = you or "the user"
    body = Template(kinds.body_of(raw)).safe_substitute(you=you, You=you[:1].upper() + you[1:], lines=str(notes_lines))
    return f"{body}\n\n{SCHEMA_REMINDER}\n\n{digest_text}"


# The answer (README 3.7). Only the keywords plan 44's supervisor schema already uses (the CLI accepts them);
# no act and no order field in this slice (D11).
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["items", "digest", "notes"],
    "properties": {
        "items": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["key", "do", "rank", "say"],
            "properties": {
                "key": {"type": "string"},
                "do": {"type": "string", "enum": list(DO)},
                "rank": {"type": "integer", "minimum": 1},
                "say": {"type": "string", "maxLength": SAY_MAX},
                "why": {"type": "string", "maxLength": WHY_MAX},
                "batch": {"type": "string", "maxLength": 32},
                "until": {"type": "string", "maxLength": 16},
            }}},
        "digest": {"type": "array", "items": {"type": "string", "maxLength": LINE_MAX}},
        "notes": {"type": "string"},
    },
}


def shape(out) -> str:
    """"" when the answer has its three fields with the right types and nothing else; else why it is no answer."""
    if not isinstance(out, dict):
        return "the answer is not an object"
    extra = sorted(set(out) - {"items", "digest", "notes"})
    if extra:
        return f"unknown field {_clip(extra[0], 40)}"
    if not isinstance(out.get("items"), list):
        return "items is missing or not a list"
    if not isinstance(out.get("digest"), list):
        return "digest is missing or not a list"
    if not isinstance(out.get("notes"), str):
        return "notes is missing or not text"
    return ""


def _local(text):
    """A local YYYY-MM-DDTHH:MM as a timestamp; None when it is not one."""
    try:
        return time.mktime(time.strptime(text, "%Y-%m-%dT%H:%M"))
    except (TypeError, ValueError, OverflowError):
        return None


def check(out: dict, handles: dict, items_: dict, now: float, notes_lines: int) -> dict:
    """An answer that passed shape(), as state.json keeps it (README 3.7 rules; untrusted, pure). `handles` maps I1..
    to keys; `items_` maps a key to {kind, always}. Returns {ann: {key: {do, rank, say, why, batch, until}}, digest,
    notes, dropped: [{at, why}], trimmed: [{at, why}]}; `at` is the entry's index in the answer, -1 for a batch
    undone as a whole."""
    ann, dropped, trimmed, taken = {}, [], [], set()
    for at, entry in enumerate(out["items"]):
        if not isinstance(entry, dict):
            dropped.append({"at": at, "why": "entry is not an object"})
            continue
        handle = entry.get("key")
        if not isinstance(handle, str) or handle not in handles:
            dropped.append({"at": at, "why": f"unknown handle {_clip(handle, 40)}"})
            continue
        if handle in taken:
            dropped.append({"at": at, "why": f"a second entry for {handle}"})
            continue
        do, rank = entry.get("do"), entry.get("rank")
        if do not in DO:
            dropped.append({"at": at, "why": "do must be forward, batch or later"})
            continue
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            dropped.append({"at": at, "why": "rank must be a whole number from 1"})
            continue
        taken.add(handle)
        key = handles[handle]
        a = {"do": do, "rank": rank, "batch": "", "until": None,
             "say": _clip(entry["say"], SAY_MAX) if isinstance(entry.get("say"), str) else "",
             "why": _clip(entry["why"], WHY_MAX) if isinstance(entry.get("why"), str) else ""}
        if do == "batch":
            name = entry.get("batch")
            if isinstance(name, str) and BATCH_RE.fullmatch(name):
                a["batch"] = name
            else:
                a["do"] = "forward"
                trimmed.append({"at": at, "why": "batch name refused"})
        if do == "later" and entry.get("until") not in (None, ""):
            t = _local(entry.get("until"))
            if t is not None and now < t <= now + LATER_MAX_S:
                a["until"] = t
            else:
                trimmed.append({"at": at, "why": "until refused"})
        reason = (items_.get(key) or {}).get("always")
        if reason and a["do"] != "forward":
            a.update(do="forward", batch="", until=None)
            trimmed.append({"at": at, "why": f"always forwarded: {reason}"})
        ann[key] = a
    groups = {}
    for key, a in ann.items():
        if a["batch"]:
            groups.setdefault(a["batch"], []).append(key)
    for name, keys in groups.items():
        why = ("one member" if len(keys) == 1 else
               "kinds differ" if len({(items_.get(k) or {}).get("kind") for k in keys}) > 1 else "")
        if why:
            for k in keys:
                ann[k].update(do="forward", batch="")
            trimmed.append({"at": -1, "why": f"batch {name} undone: {why}"})
    lines = [_clip(x, LINE_MAX) for x in out["digest"] if isinstance(x, str) and x.strip()][:3]
    return {"ann": ann, "digest": lines, "notes": cut_notes(out["notes"], notes_lines), "dropped": dropped,
            "trimmed": trimmed}


def pass_model(limits: dict, new_items: list) -> str:
    """super_judge_model when the wake's new items hold a stuck or failed-twice task (D-b), else super_model."""
    if any(i.get("kind") in JUDGE_KINDS for i in new_items):
        return limits["super_judge_model"]
    return limits["super_model"]


def run(cfg: dict, exe, cwd, prompt: str, model: str, max_cost) -> dict:
    """Blocking; no writes, no mutation. One tool-free structured `claude -p` in `cwd` (<home>/super, D3) with
    super_timeout_s, `max_cost` as --max-budget-usd, safe mode and every MCP tool denied: plan 44's pass command,
    unchanged. Returns {out, cost, model, turns, error, ms}: `out` is the answer that passed shape(), None on any
    failure; a paid failure keeps its reported cost (None when unknown, never a free zero)."""
    start = time.monotonic()
    info = {"cost": None, "turns": 0}
    res = {"out": None, "cost": None, "model": model, "turns": 0, "error": "", "ms": 0}
    if not exe:
        res.update(cost=0.0, error="claude.exe not found")
        return res
    if not _num(max_cost) or max_cost <= 0:  # a zero max_cost would mean no budget flag at all
        res.update(cost=0.0, error="no budget for the pass")
        return res
    asked = dict(cfg, brief_timeout_s=cfg["super_timeout_s"])
    try:
        fields, _ = compact._ask(asked, exe, str(cwd), prompt, SCHEMA, info, model=model, max_cost=max_cost,
                                 safe_mode=True)
    except compact.BriefError as exc:
        res.update(cost=info.get("cost"), turns=info.get("turns", 0), ms=_ms(start),
                   error=str(exc).replace("the brief", "the pass"))
        return res
    except Exception as exc:  # an unexpected runner failure is still no answer
        res.update(cost=info.get("cost"), ms=_ms(start), error="the pass failed: " + _clip(exc, 200))
        return res
    res.update(cost=info.get("cost"), turns=info.get("turns", 0), ms=_ms(start))
    why = shape(fields)
    if why:
        res["error"] = f"the pass gave no answer ({why})"
        return res
    res["out"] = fields
    return res
```

## 3.2 `tests/fake_claude.py`

Docstring, after the `scope` line: `  A schema with an `items` property is the super agent pass (plan 58): see superagent() for its SUPER-* modes.`

After `planner()`:

```python
def superagent(raw):
    """Plan 58: the super agent pass (its schema has an `items` property). Every handle (the item lines that start
    with `I<n> `; ASCII only, since stdin is read in the locale encoding) is forwarded, ranked in reverse (the last
    handle first), with say `fake: I<n>`. SUPER-LATER puts I1 later for an hour; SUPER-BATCH puts every entry in the
    batch fake-batch; SUPER-UNKNOWN adds an entry for I99; SUPER-BAD answers items that are not a list; SUPER-ERROR
    an error envelope that still reports its cost. The notes carry the digest's head line (which pass wrote them)."""
    if "SUPER-ERROR" in raw:
        out({"type": "result", "subtype": "error_max_turns", "is_error": True, "total_cost_usd": 0.02, "num_turns": 6})
        return 1
    handles = re.findall(r"^(I\d+) ", raw, re.M)
    n = len(handles)
    entries = [{"key": h, "do": "forward", "rank": n - k, "say": f"fake: {h}"} for k, h in enumerate(handles)]
    if "SUPER-LATER" in raw and entries:
        entries[0].update(do="later", why="fake: it can wait",
                          until=time.strftime("%Y-%m-%dT%H:%M", time.localtime(time.time() + 3600)))
    if "SUPER-BATCH" in raw:
        for e in entries:
            e.update(do="batch", batch="fake-batch")
    if "SUPER-UNKNOWN" in raw:
        entries.append({"key": "I99", "do": "forward", "rank": 1, "say": "fake: unknown"})
    head = next((line for line in raw.splitlines() if line.startswith("# Super agent pass")), "")
    fields = {"items": "not a list" if "SUPER-BAD" in raw else entries, "digest": [f"fake digest: {n} items"],
              "notes": f"fake notes\n{head}"}
    out({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.003, "num_turns": 2,
         "result": json.dumps(fields), "structured_output": fields})
    return 0
```

In `prep()`, after `if "scope" in props: return planner(raw)`: `if "items" in props: return superagent(raw)`. No
other schema has a top-level `items` property (checked: brief, handoff, planner, prep, replan, review, supervisor).

## 3.3 Tests first (red before the code)

Helpers: `item(name, kind="hold", always="", type_="task", **extra)` builds a Task 2 item dict (key `task:<id>:<name>`)
with the card fields of `describe` at their empty values plus `age_s` 0 and the annotation fields empty; `FAKE =
[sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]`; `cfg = dict(paths.DEFAULTS,
super_timeout_s=90)`.

`DescribeTest`
- `test_decision_card_fields`: row 1 of table 4.1 (`make_task` with `decision=dict(DECISION)`), its row from
  `server.task_row`, view `{"line": "needs you · Which file?"}`, level `auto`, `timeout_s` 600, now T0+100: `ask`
  `"needs you · Which file?"`, `options` `["style.css", "app.js"]`, `default` `"style.css"`, `left_s` 500; at level
  `gated` `left_s` is None; with the decision's `taken` `"default"`, `options` `[]` and `default` `""`.
- `test_session_and_row_only_kinds`: a session item and row (`text` `"Stopped"`, `stop_question` `"which file?"`,
  `source` `"vscode"`) at level `observed` give `ask` `"Stopped: which file?"` and `source` `"vscode"`; a question
  item with the row's `asks` `"Which file?"` gives `"asks: Which file?"`; a hand_off item with `hand_off` `"the context
  is large"` gives `"hand off: the context is large"`; a view line holding `token=abc` gives `token=***`; a 500-character
  view line is cut to `ASK_MAX`; a row whose supervisor `say` is `"finish: all checks pass"` gives that `supervisor`.

`LinesTest`
- `test_task_line`: a running task (step 1 code `sonnet`/`medium`, `retries` 1, state running, one attempt started T0
  with cost 0.25) at now T0+125, level `gated`, is exactly `"0111-a001 proj · running · step 1/2 code sonnet/medium ·
  2 min in step · $0.25 · retries 1 · FAILs 0 · level gated"`.
- `test_live_tasks_order_and_filter`: tasks running (updated T0+5), waiting (T0+9), done, stopped, handed, and a
  waiting one with `accepted` set give `live_tasks` ids `[waiting, running]`.
- `test_slow_needs_three_samples_and_a_minute`: three done code steps in other tasks lasting 60, 80 and 100 s, and a
  running code step whose attempt started T0: at T0+150 no signal; at T0+170 one `slow` signal whose line is
  `"0111-a001: step 1 code has run 2 min, over twice the median 1 min of 3 ended code steps"`; with two samples
  none; with samples of 10, 10 and 10 s and the step at T0+30 none (under `SLOW_MIN_S`).
- `test_same_fail_needs_two_equal_details`: a stuck task with steps code 1, verify 2, fix 3, verify 4
  (`tasks._blank`), verify 2 and 4 `verdict` FAIL with `verdict_detail` `"test_x fails"`: one `same_fail` signal,
  line `"0111-a001: verify steps 2 and 4 failed the same way: test_x fails"`; different details, or empty ones,
  give none.
- `test_fingerprint_moves_with_state_not_cents`: equal inputs give equal 16-hex strings; a new item key, the current
  step moving, a retry and a new signal each change it; the running task's cost going from $0.25 to $0.75 keeps it,
  and to $1.25 changes it.
- `test_levels_and_trigger_words`: `levels(dict(paths.DEFAULTS, supervisor_projects={"D:/work/app": "auto"}))` is
  `"global gated; app auto"`; `trigger_words([("new", "a"), ("new", "b"), ("ended", "t"), ("sweep", "")])` is `"2 new
  items, 1 task ended, sweep"`; `[("back", "k"), ("asked", "sort")]` gives `"1 back from later, asked"`; `[]` gives
  `"none"`.

`DigestTest`
- `test_item_block_lines`: the decision item of the README example (label `0111-a001`, project `proj`, title `Task
  a001`, `ask` `"needs you · Which file?"`, `options` `["style.css", "app.js"]`, `default` `"style.css"`, `left_s`
  500, level `auto`, `age_s` 300, `do` `forward`, `rank` 2, `say` `"Pick style.css: the plan names it"`, `questions`
  `["Keep the old class names?"]`) gives exactly:

  ```
  I1 · task 0111-a001 · proj · Task a001
     kind decision · seen 5 min ago · level auto
     ask: needs you · Which file?
     options: 1) style.css 2) app.js · default style.css, taken in 8 min
     open questions: Keep the old class names?
     last pass: forward rank 2: Pick style.css: the plan names it
  ```

  and a session item (label `3f2a9c1e`, kind `failed`, level `observed`, source `vscode`, ask `Failed`, title `a
  chat`) gives `"I2 · observed chat 3f2a9c1e · proj · a chat\n   kind failed · seen 0 s ago · level observed ·
  vscode\n   ask: Failed"`; an always item's first line reads `"I1 · always (Fable confirm) · task ..."`; a block
  over `ITEM_MAX` ends with `"…"` at exactly `ITEM_MAX` characters.
- `test_digest_layout_and_handles`: head `{"n": 3, "trigger": "2 new items, sweep", "spent": 0.031, "day_usd": 1.0,
  "levels": "global gated; proj auto"}`, two items, orders `"never raise chats before 18:00"`, notes `"watch
  0111-a001\n"`, one live line, one signal, you `"Fred"`, now T0: the text starts `"# Super agent pass 3 · " +
  time.strftime("%Y-%m-%d %H:%M", time.localtime(T0)) + "\nTriggers: 2 new items, sweep\nSpend today: $0.03 of $1.00 a
  day\nLevels: global gated; proj auto\n\n"`; the blocks follow in the order `Standing orders from Fred:`, `Your notes
  from the last pass:`, `Items for Fred (2, handles I1 to I2):`, `Live tasks (1):`, `Signals:`; `handles` is `{"I1":
  key1, "I2": key2}`; the text ends with exactly one newline. With one item the title is `Items for Fred (1, handle
  I1):`; with none, `Items for Fred: none.` and `handles` `{}`; empty orders, notes, lines and signals each read
  `none`.
- `test_digest_caps_items_and_omits_blocks_that_do_not_fit`: 35 items give handles `I1` to `I30` and the title
  `"Items for the user (30, handles I1 to I30; 5 more not shown, they keep their place):"`; orders of 40 000
  characters become one line matching `^Standing orders from the user: omitted \(\d+ bytes\)$` while the notes block
  still fits; 45 live lines show 40 and `... and 5 more`; every digest built here is at most `DIGEST_MAX` bytes; 30
  items whose blocks are 600 characters of `"漢"` (3 bytes each) get fewer handles than 30 and still fit.
- `test_prompt_fills_slots_and_keeps_the_digest`: `build_prompt(kinds.seed_text("super"), "Digest $5 and $you\n",
  "Fred", 40)` holds `"Fred runs many tasks at once"` and `"at most 40 lines"`, no `$You`, `$you` or `$lines` before
  the digest, the reminder before the digest, and ends with `"Digest $5 and $you\n"` (untouched); `you` `""` reads
  `the user` / `The user`.
- `test_schema_is_the_contract`: `SCHEMA["required"]` is `["items", "digest", "notes"]`; the entry's `do` enum is
  `["forward", "batch", "later"]`; `act` and `order` appear nowhere in `json.dumps(SCHEMA)` (D11); the keywords used
  (walk `properties` values and `items`) are a subset of `{"type", "additionalProperties", "required", "properties",
  "items", "enum", "minimum", "maxLength"}`.

`AnswerTest`
- `test_shape_reasons`: `[]` gives `"the answer is not an object"`; the three fields plus `act` give `"unknown field
  act"`; no `items` gives `"items is missing or not a list"`; `digest` `"x"` gives `"digest is missing or not a
  list"`; `notes` 5 gives `"notes is missing or not text"`; the three fields alone give `""`.
- `test_check_rules`: handles `{"I1": kA, "I2": kB, "I3": kC, "I4": kD}`; items kA `{kind hold, always "Fable
  confirm"}`, kB `{decision, ""}`, kC `{hold, ""}`, kD `{hold, ""}`; now T0; entries in this order:
  0 `"x"`; 1 `{key I9, do forward, rank 1, say "z"}`; 2 `{key I1, do later, rank 3, say "a", until <T0+3600 local>}`;
  3 `{key I1, do forward, rank 1, say "again"}`; 4 `{key I2, do "drop", rank 1, say "b"}`; 5 `{key I2, do forward,
  rank 0, say "b"}`; 6 `{key I2, do batch, rank 2, say "b", batch "Bad Name"}`; 7 `{key I3, do later, rank 4, say
  "c", why "waits on I2", until "2026-13-99T99:99"}`; 8 `{key I4, do batch, rank 5, say "d", batch "acc"}`. Then
  `ann` is `{kA: {do forward, rank 3, say "a", why "", batch "", until None}, kB: {forward, 2, "b", "", "", None},
  kC: {later, 4, "c", "waits on I2", "", None}, kD: {forward, 5, "d", "", "", None}}`; `dropped` is at 0 `entry is not
  an object`, 1 `unknown handle I9`, 3 `a second entry for I1`, 4 `do must be forward, batch or later`, 5 `rank must
  be a whole number from 1`; `trimmed` is `[{2, "always forwarded: Fable confirm"}, {6, "batch name refused"}, {7,
  "until refused"}, {-1, "batch acc undone: one member"}]`; a rank of `True` is dropped like 0.
- `test_until_window_and_batches`: a later `until` of `time.strftime("%Y-%m-%dT%H:%M", time.localtime(T0 + 3600))`
  is kept as `T0 + 3600`; T0+90000 (over a day) and T0-60 are refused; two hold items in batch `acc` stay batched;
  a hold and a decision in batch `acc` are both forward with `{-1, "batch acc undone: kinds differ"}`.
- `test_texts_are_masked_and_clipped`: a say of `"token=abc " + "x" * 300` becomes at most 200 characters and holds
  `token=***`, not `abc`; digest `["a", 5, "", "b", "c", "d"]` gives `["a", "b", "c"]`; notes of 50 lines with
  `notes_lines` 40 give 40 lines.
- `test_pass_model`: with `settings(DEFAULTS)[0]`, new items holding a `stuck` or a `failed_twice` give `sonnet`; a
  `hold` and `[]` give `haiku`.

`RunTest` (the fake claude, a temporary `cwd`)
- `test_one_call_with_the_pass_flags`: spy on `compact.subprocess.run` (as plan 44's `RunnerTest` does): one call;
  `kw["cwd"]` is the folder; `kw["timeout"]` is 90; `--model` `haiku`; `--max-budget-usd` `0.2`; `--tools` `""`;
  `--max-turns` `6`; `--disallowedTools` `mcp__*`; `--safe-mode` present; `--json-schema` decodes to
  `superagent.SCHEMA`; no `--resume`, `--session-id` or `--add-dir`. The prompt is `build_prompt(seed, "I1 · task
  a\nI2 · task b\n", "Fred", 40)`; the result is `out.items` `[{key I1, rank 2, say "fake: I1", do forward}, {key I2,
  rank 1, ...}]`, `cost` 0.003, `turns` 2, `error` `""`, `model` `haiku`, `ms` an int >= 0.
- `test_failures_are_no_answer_and_keep_their_cost`: `SUPER-ERROR` in the digest gives `error` `"the pass failed:
  error_max_turns"`, `cost` 0.02, `out` None; `SUPER-BAD` gives `"the pass gave no answer (items is missing or not a
  list)"`, `cost` 0.003; `exe` None gives `"claude.exe not found"`, `cost` 0.0; `max_cost` 0, -1, `True` and `"0.2"`
  each give `"no budget for the pass"`, `cost` 0.0 and no subprocess call; `subprocess.run` raising
  `TimeoutExpired` gives `"the pass took longer than 90 s"`, `cost` None; raising `RuntimeError("boom
  sk-ant-1234567890")` gives `"the pass failed: boom ***"`.

## 3.4 Steps and acceptance

- [ ] 1. Write the tests; run `py -m unittest tests.test_superagent`: red for the missing functions and the fake's
      missing branch.
- [ ] 2. Append 3.1 to `console/superagent.py`; make the 3.2 edits. Focused tests green.
- [ ] 3. Full suite green (report the count); `tests/test_supervisor.py` and `tests/test_planner.py` still pass (the
      fake's routing). Commit with the message above.
