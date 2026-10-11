# Plan 09: Route trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Related plans: [../PLAN.md](../PLAN.md) (master), [02-run.md](02-run.md) (Prep and run_started), [04-polish.md](04-polish.md) (model mix), [07-cells-drawer.md](07-cells-drawer.md) (the session page this extends)
> Context: [../BRAINSTORM.md](../BRAINSTORM.md); [../CLAUDE.md](../CLAUDE.md)

**Goal:** The session page shows which model did what for a task. Today the Haiku Prep leaves no trace past the `✓ Prep` path step, the agent rows show no model, the session's model and effort sit at the end of a header line that gets cut off ("vague · op..."), and an Escalate shows no time. After this plan, the brief's Agents block becomes the **Route** block: a Prep row (model, turns, cost; a dim `Prep none` row when the chat had no Prep), main with its model and effort, each agent with its model (a running agent too), an escalation line with its time, and the session's model mix (cost share per model). The header gets a model chip that is never cut. Steps and Timeline rows tag a step with its model when it is not main's.

**Architecture:** the Prep card stores its model. `Handler._run` copies the card's model, cost and turns into the `run_started` line (`extra`), and `State` keeps them on the session, so a snapshot reads no file. `State.snapshot` adds `prep_model`, `prep_cost`, `prep_turns`, `escalated_ts` and `models` (the session's `usage.families` as shares, through a new `shares()` that `spend()` now uses too). `_agent_row` falls back to the agent transcript's model family while the agent runs (the hook only names it at SubagentStop). The page renders it; no new endpoint, no hook change.

**Tech Stack:** unchanged: Python 3.14 standard library, plain HTML/CSS/JS, `unittest`.

**Where:** repo root `D:\MY DOCS\MY TOOLS\CLAUDE CONSOLE\` (git, branch `master`). Run commands from the repo root in Git Bash. Start: 99 tests OK (110 if plan 08 ran first; the two plans touch different lines). Other chats edit `web/app.js` and `web/style.css` in parallel: apply every edit as an anchored edit (find the old text, replace it), never as a whole-file copy, and stage only this plan's lines.

---

## Fixed decisions (Fred, 2026-10-11)

1. **Route replaces Agents** in the brief (not a new tab). Rows: Prep, main, then the agents in start order. Columns: name, step cells, model, steps (`4t` = Prep turns), cost.
2. **Labels only**: model names in words, no colour per model; the locked palette is unchanged (no new token).
3. **No Prep** (VS Code, terminal, Run raw): a dim `Prep · none` row stays, so a skipped Haiku pass is visible.
4. **Step tags only where the model differs from main's**: Steps and Timeline rows of an agent on another model family get a dim `haiku` / `sonnet` tag before the tool.
5. **Model mix per session** = the session's transcript plus its agents' transcripts, cost share per family, biggest model first (same order as the daily spend line). Without a transcript reader the list is empty and the line is hidden.
6. **Rules kept:** no hook change (`cc_events.py` untouched), no new endpoint, nothing written outside `~/.claude/console/`, no emojis or em-dashes.
7. **Verified:** Tasks 1-2 in a scratch clone of this repo (100 tests OK) and the page in Chrome against a seeded service (a window run with Prep haiku 4 turns $0.021, main opus high after an escalation from sonnet/high, a done Explore on haiku, a running verifier on sonnet named only by its transcript; a VS Code chat with no Prep): the Route block, the escalation line with its time, `model mix opus 82 % sonnet 12 % haiku 6 %`, the header chip `opus high`, the step tags and the dim `Prep none` row all showed. **Not verified by Claude:** the real pywebview window at its 400 px width (Task 3).

## Code map

```text
console/
  prep.py      card + "model"
  server.py    _run: prep_model / prep_cost / prep_turns into run_started (extra)
  state.py     Session + prep_model, prep_cost, prep_turns, escalated_ts; shares(); snapshot rows +
               prep_*, escalated_ts, models; _agent_row model fallback from the agent transcript
web/
  app.js       modelText, routeRows, stepTag; agentRows + model/effort; Route block; header chip; tags
  style.css    .agent 5 columns, .agent.off, .esc, .where .mdl, .log .tag
tests/
  test_prep.py + 1 assertion   test_server.py + 1 assertion   test_state.py + 1 test
```

## TODO

- [ ] Task 1: service (Prep model on the card and the run, Route fields in the snapshot)
- [ ] Task 2: window (Route block, header chip, step tags)
- [ ] Task 3: Fred: live check in the real window, close the phase

---

### Task 1: Service

**Files:** `console/prep.py`, `console/server.py`, `console/state.py`, `tests/test_prep.py`, `tests/test_server.py`, `tests/test_state.py`

- [ ] **Step 1: the tests (they fail first)**

`tests/test_prep.py`, in `test_run_prep_saves_the_card`, after the `card["route"]` assertion add:

```python
            self.assertEqual((card["model"], card["cost"], card["turns"]), ("haiku", 0.03, 5))
```

`tests/test_server.py`, in `test_prep_then_run_then_chat`, after the `("window", "Fix add() in calc.py", "mechanical")` assertion add:

```python
        self.assertEqual((row["prep_model"], row["prep_cost"], row["prep_turns"]), ("haiku", 0.03, 5))
```

`tests/test_state.py`, insert before `def test_projects_for_the_picker(self):`:

```python
    def test_route_prep_agent_models_and_escalation(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        chat = str(Path(tmp.name) / "r.jsonl")
        Path(chat).write_text(line("m1", T0 - 60, "claude-opus-5-5", output_tokens=300_000), encoding="utf-8")
        agent = Path(usage.agent_path(chat, "x1"))
        agent.parent.mkdir(parents=True)
        agent.write_text(line("m2", T0 - 30, "claude-haiku-5-5", output_tokens=4_000_000), encoding="utf-8")
        self.feed(ev("run_started", T0 - 100, sid="r", model="opus", prep="p1", prep_model="haiku",
                     prep_cost=0.02, prep_turns=3),
                  ev("UserPromptSubmit", T0 - 99, sid="r", transcript_path=chat),
                  ev("SubagentStart", T0 - 40, sid="r", agent_id="x1", agent_type="Explore"),
                  ev("run_started", T0 - 20, sid="r", kind="escalate", escalated="sonnet/high -> opus/high"))
        reader = usage.Usage(paths.DEFAULTS["prices"])
        for f in self.state.transcripts(T0):
            reader.poll(f)
        row = self.state.snapshot(T0, reader)["sessions"][0]
        self.assertEqual((row["prep_model"], row["prep_cost"], row["prep_turns"]), ("haiku", 0.02, 3))
        self.assertEqual((row["escalated"], row["escalated_ts"]), ("sonnet/high -> opus/high", T0 - 20))
        self.assertEqual(row["agents"][0]["model"], "haiku")  # still running: named by its transcript
        self.assertEqual(row["models"], [["opus", 0.75], ["haiku", 0.25]])  # opus $6, haiku $2
        self.assertEqual(self.state.snapshot(T0)["sessions"][0]["models"], [])  # no reader, no shares

```

Run: `py -m unittest discover -s tests` - expect 3 failures (KeyError / AssertionError).

- [ ] **Step 2: `console/prep.py`** - in `run_prep`, the card:

Old:
```python
        "reason": fields.get("reason", ""), "cost": result["cost"], "turns": result["turns"],
    }
```
New:
```python
        "reason": fields.get("reason", ""), "cost": result["cost"], "turns": result["turns"],
        "model": cfg["prep_model"],
    }
```

- [ ] **Step 3: `console/server.py`** - in `Handler._run`:

Old:
```python
            reason, prep_id = card.get("reason", ""), card["id"]
        else:
            title, route, reason, prep_id = text, "raw", "", ""
        sid = self.hub.runs.start(folder, text, model, effort, title=title, route=route,
                                  reason=reason, prep=prep_id)
```
New:
```python
            reason, prep_id = card.get("reason", ""), card["id"]
            extra = {"prep_model": card.get("model") or cfg["prep_model"], "prep_cost": card.get("cost"),
                     "prep_turns": card.get("turns")}  # the Route block's first row
        else:
            title, route, reason, prep_id, extra = text, "raw", "", "", None
        sid = self.hub.runs.start(folder, text, model, effort, title=title, route=route,
                                  reason=reason, prep=prep_id, extra=extra)
```

- [ ] **Step 4: `console/state.py`** - eight anchored edits.

4a. `Session` fields. Old:
```python
    prep: str = ""
    start_commit: str = ""
```
New:
```python
    prep: str = ""
    prep_model: str = ""       # the Prep that wrote the prompt: its model, cost and turns (Route block)
    prep_cost: float = None
    prep_turns: int = 0
    start_commit: str = ""
```

4b. Old:
```python
    escalated: str = ""        # "sonnet/medium -> sonnet/high" once Escalate ran (once per task)
```
New:
```python
    escalated: str = ""        # "sonnet/medium -> sonnet/high" once Escalate ran (once per task)
    escalated_ts: float = 0.0
```

4c. In `apply`, `run_started`. Old:
```python
            if rec.get("escalated"):
                s.escalated = rec["escalated"]
```
New:
```python
            if rec.get("escalated"):
                s.escalated, s.escalated_ts = rec["escalated"], ts
```

4d. Old:
```python
                if s.escalated:
                    parent.escalated = s.escalated  # once per task, whichever copy escalated
                elif parent.escalated:
                    s.escalated = parent.escalated
```
New:
```python
                if s.escalated:  # once per task, whichever copy escalated
                    parent.escalated, parent.escalated_ts = s.escalated, s.escalated_ts
                elif parent.escalated:
                    s.escalated, s.escalated_ts = parent.escalated, parent.escalated_ts
```

4e. Old:
```python
            if rec.get("prep"):
                s.prep = rec["prep"]
```
New:
```python
            if rec.get("prep"):
                s.prep = rec["prep"]
                s.prep_model = rec.get("prep_model") or ""
                s.prep_cost = rec.get("prep_cost")
                s.prep_turns = int(rec.get("prep_turns") or 0)
```

4f. Insert before `def midnight(now: float) -> float:`:
```python
def shares(families: dict) -> list:
    """[[family, share of the cost]], biggest model first: the spend line and a session's Route block."""
    total = sum(families.values())
    if not total:
        return []
    rank = {m: i for i, m in enumerate(claude_cli.MODELS[::-1])}
    return [[m, round(c / total, 3)] for m, c in
            sorted(families.items(), key=lambda kv: (rank.get(kv[0], len(rank)), kv[0]))]


```

4g. `snapshot`. Old:
```python
        cost = usage.cost if usage else (lambda files, since=0.0: 0.0)
```
New:
```python
        cost = usage.cost if usage else (lambda files, since=0.0: 0.0)
        fams = usage.families if usage else (lambda files, since=0.0: {})
```
Old:
```python
                "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated,
                "kind": s.kind,
```
New:
```python
                "verdict": s.verdict, "verdict_detail": s.verdict_detail, "escalated": s.escalated,
                "escalated_ts": s.escalated_ts,
                "prep_model": s.prep_model, "prep_cost": s.prep_cost, "prep_turns": s.prep_turns,
                "models": shares(fams(files)),
                "kind": s.kind,
```
Old:
```python
                "agents": [self._agent_row(a, s, cost) for a in
```
New:
```python
                "agents": [self._agent_row(a, s, cost, fams) for a in
```

4h. `spend`. Old:
```python
        total = sum(families.values())
        rank = {m: i for i, m in enumerate(claude_cli.MODELS[::-1])}  # biggest first
        models = [[m, round(c / total, 3)] for m, c in
                  sorted(families.items(), key=lambda kv: (rank.get(kv[0], len(rank)), kv[0]))]
```
New:
```python
        models = shares(families)
```
`_agent_row`. Old:
```python
    def _agent_row(self, a: Agent, s: Session, cost=None) -> dict:
```
New:
```python
    def _agent_row(self, a: Agent, s: Session, cost=None, fams=None) -> dict:
```
Old:
```python
        spent = cost([usage_mod.agent_path(s.transcript_path, a.id)]) if cost and s.transcript_path else 0.0
        return {"id": a.id, "type": a.type or "agent", "model": a.model, "effort": a.effort,
```
New:
```python
        files = [usage_mod.agent_path(s.transcript_path, a.id)] if s.transcript_path else []
        spent = cost(files) if cost and files else 0.0
        seen = fams(files) if fams and files else {}  # a running agent: the model its transcript names
        model = a.model or (max(seen, key=seen.get) if seen else "")
        return {"id": a.id, "type": a.type or "agent", "model": model, "effort": a.effort,
```

- [ ] **Step 5: run** `py -m unittest discover -s tests` - expect 100 OK (111 after plan 08).
- [ ] **Step 6: commit** `console/prep.py console/server.py console/state.py tests/test_prep.py tests/test_server.py tests/test_state.py`: `feat: route trace data: Prep model on the run, agent models, session model mix`

---

### Task 2: Window

**Files:** `web/app.js`, `web/style.css` (anchored edits; other chats edit both)

- [ ] **Step 1: helpers.** In `web/app.js` insert before `function tlBase() {`:

```js
function modelText(model, effort) { return [alias(model), effort].filter(Boolean).join(" "); }
function routeRows(s, rows) {  // the Route block: the Prep that wrote the prompt, then main and the agents
  const prep = s.prep
    ? { nm: "Prep", word: "done", model: s.prep_model, steps: s.prep_turns, unit: "t", cost: s.prep_cost }
    : { nm: "Prep", word: "none", model: "", steps: 0, unit: "", cost: null, off: true };
  return [prep].concat(rows);
}
```

- [ ] **Step 2: `agentRows` carries model and effort.** Old:
```js
  return [{ nm: "main", id: "", steps: s.main_steps, cost: s.spent == null ? null : Math.max(0, s.spent - agentCost),
            word: working ? (running ? "waiting" : "working") : label(s).toLowerCase() }]
    .concat(s.agents.map((a) => ({ nm: a.type, id: a.id, steps: a.steps, cost: a.cost, verdict: a.verdict,
```
New:
```js
  return [{ nm: "main", id: "", steps: s.main_steps, cost: s.spent == null ? null : Math.max(0, s.spent - agentCost),
            model: s.model, effort: s.effort, word: working ? (running ? "waiting" : "working") : label(s).toLowerCase() }]
    .concat(s.agents.map((a) => ({ nm: a.type, id: a.id, steps: a.steps, cost: a.cost, verdict: a.verdict,
      model: a.model, effort: a.effort,
```

- [ ] **Step 3: the Route block** in `renderBrief`. Old:
```js
      <div class="blk"><div class="hd"><span class="lbl">Agents · 1 cell = 2 steps</span><span class="m">steps / cost</span></div><div class="agents">
        ${rows.map((r) => `<div class="agent"><span class="nm m" title="${esc(r.nm)}">${r.word === "done" ? "✓ " : r.word === "working" ? "▶ " : ""}${esc(r.nm)}${r.verdict ? " " + esc(r.verdict) : ""}</span>
          <span class="cells">${cellsHtml(Array.from({ length: 24 }, (_, k) => k < Math.ceil(r.steps / 2) ? "f" : ""))}</span>
          <span class="m">${r.steps}</span><span class="m c">${r.cost == null ? "&ndash;" : money(r.cost)}</span></div>`).join("")}</div></div>
```
New:
```js
      <div class="blk"><div class="hd"><span class="lbl">Route · 1 cell = 2 steps</span><span class="m">model · steps / cost</span></div><div class="agents">
        ${routeRows(s, rows).map((r) => `<div class="agent${r.off ? " off" : ""}"><span class="nm m" title="${esc(r.nm)}">${r.word === "done" ? "✓ " : r.word === "working" ? "▶ " : ""}${esc(r.nm)}${r.verdict ? " " + esc(r.verdict) : ""}</span>
          <span class="cells">${cellsHtml(Array.from({ length: 24 }, (_, k) => k < Math.ceil(r.steps / 2) ? "f" : ""))}</span>
          <span class="m" title="${esc(r.model || "")}">${r.off ? "none" : esc(modelText(r.model, r.effort)) || "&ndash;"}</span>
          <span class="m"${r.unit ? ' title="turns"' : ""}>${r.off ? "" : r.steps + (r.unit || "")}</span><span class="m c">${r.cost == null ? "&ndash;" : money(r.cost)}</span></div>`).join("")}
        ${s.escalated ? `<div class="esc m">↑ escalated ${esc(s.escalated)}${s.escalated_ts ? " · " + hhmm(s.escalated_ts) : ""}</div>` : ""}</div>
        ${s.models.length ? `<div class="legend"><span>model mix</span>${s.models.map(([m, f]) => `<span>${esc(m)} ${f < 0.01 ? "&lt;1" : Math.round(f * 100)} %</span>`).join("")}</div>` : ""}</div>
```

- [ ] **Step 4: header chip** in `renderSession`. Old:
```js
    <div class="where"><span class="m" title="${esc(s.route_reason || "")}">${esc(s.project)} / ${esc(src)}${esc(routeText(s))}</span>
```
New:
```js
    <div class="where"><span class="m" title="${esc(s.route_reason || "")}">${esc(s.project)} / ${esc(src)}${esc(s.route)}</span>
    ${s.model ? `<span class="mdl" title="${esc(s.model)}">${esc(modelText(s.model, s.effort))}</span>` : ""}
```
(`routeText` stays: the list cards still use it.)

- [ ] **Step 5: step tags.** Old:
```js
function logRow(x, mark = "") {
  return `<div${x.denied ? ' class="r"' : ""}><span>${mark}</span><span>${hms(x.ts)}</span><span>${esc(x.agent_type)}</span><span>${esc(x.tool)} ${esc(x.what)}</span></div>`;
}
```
New:
```js
function logRow(x, mark = "", tag = "") {  // `tag`: the step's model when it is not main's
  return `<div${x.denied ? ' class="r"' : ""}><span>${mark}</span><span>${hms(x.ts)}</span><span>${esc(x.agent_type)}</span><span>${tag ? `<span class="tag">${esc(tag)}</span>` : ""}${esc(x.tool)} ${esc(x.what)}</span></div>`;
}
function stepTag(s) {  // agent id -> its model family, only where it differs from main's
  const main = alias(s.model), by = {};
  for (const a of s.agents) if (alias(a.model) && alias(a.model) !== main) by[a.id] = alias(a.model);
  return (x) => by[x.agent] || "";
}
```
Old (Steps tab):
```js
    body = newest.length ? `<div class="log">${newest.map((x, k) => logRow(x, k === 0 ? mark : "")).join("")}</div>` : '<p class="none">No step yet.</p>';
```
New:
```js
    const tag = stepTag(s);
    body = newest.length ? `<div class="log">${newest.map((x, k) => logRow(x, k === 0 ? mark : "", tag(x))).join("")}</div>` : '<p class="none">No step yet.</p>';
```
Old (Timeline tab):
```js
      ${inMin.length ? `<div class="log">${inMin.map((x) => logRow(x)).join("")}</div>` : '<p class="none">No step in this minute.</p>'}</div>`;
```
New:
```js
      ${inMin.length ? `<div class="log">${inMin.map((x) => logRow(x, "", stepTag(s)(x))).join("")}</div>` : '<p class="none">No step in this minute.</p>'}</div>`;
```

- [ ] **Step 6: Agents tab shows the model.** Old:
```js
      return `<div class="arow">${m}<span class="nm">${esc(r.nm)}${r.verdict ? " " + esc(r.verdict) : ""}</span><span class="m">${esc(r.word)}</span>
```
New:
```js
      return `<div class="arow">${m}<span class="nm">${esc(r.nm)}${r.verdict ? " " + esc(r.verdict) : ""}</span><span class="m">${esc(r.word)}${r.model ? " · " + esc(alias(r.model)) : ""}</span>
```

- [ ] **Step 7: `web/style.css`.** Old:
```css
.agent { display: grid; grid-template-columns: 96px minmax(0, 1fr) 30px 40px; gap: 8px; align-items: center; }
```
New:
```css
.agent { display: grid; grid-template-columns: 84px minmax(0, 1fr) 72px 30px 40px; gap: 8px; align-items: center; }
```
Old:
```css
.agent span.c { color: var(--ink); }
```
New:
```css
.agent span.c { color: var(--ink); }
/* the Route block: model in words (no colour per model); a chat with no Prep shows a dim row */
.agent span:nth-child(3) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.agent.off .nm, .agent.off span.c { color: var(--mut); }
.esc { font-size: 11px; color: var(--mut); }
.where .mdl { flex: none; font: 12px var(--mono); color: var(--ink); white-space: nowrap; }
.log .tag { color: var(--mut); margin-right: 6px; }
```

- [ ] **Step 8: check** `node -e "new Function(require('fs').readFileSync('web/app.js','utf8'))"` (no output = parses), then `py -m unittest discover -s tests` (unchanged count).
- [ ] **Step 9: commit** only this task's hunks of `web/app.js` and `web/style.css` (`git add -p`): `feat: Route block, model chip and step model tags on the session page`

---

### Task 3: Fred: live check, close the phase

- [ ] Restart the window (`run.bat`). Start a task with Prep (Enter), then Run.
- [ ] Open the session, expand the brief: `✓ Prep haiku Nt $x`, `main <model> <effort>`, and once Claude starts an agent its row with its model while it is still running. A VS Code chat shows `Prep none`, dim.
- [ ] The header shows the model chip at 400 px; the project / source / route text is what gets cut.
- [ ] Steps: an Explore step on haiku under an opus main has the `haiku` tag; main's steps have none.
- [ ] After a Verify FAIL + Escalate: the `↑ escalated a -> b · hh:mm` line.
- [ ] Note: runs started before this plan show `✓ Prep – 0t –` (their run_started line has no Prep model); that is expected.
- [ ] PLAN.md: row 9 `done <date>` and a History line.
