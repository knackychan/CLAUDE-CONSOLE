# Task 5: The window (B6, B8, B9, G3, G4, G7, G9, plan 25 and plan 26 nits)

> Contract: [review.md](review.md) findings B6, B8, B9, G3, G4, G7, G9 and the nits of plans 25 and 26; plan 26
> README 3.4 (what a Save posts) and Task 4 D1 (a) ("only what differs from the page's load"); plan 25 05-step-inspector.md
> 5.1 and 5.6 (cost word, fold keys `plan.<heading>`, the Edit condition), 06-handoff-task-measure.md 6.5 (`.now`),
> 07-task-page.md 7.3 (`.chain .row.short`); plan 25 03-chain.md (`stepCost(s)` reads `s.cost`, the service's sum of
> the attempts); plan 5 README 3.6 ("the Task page shows a step whose attempts are all unpriced as `cost unknown`").
> Depends on: nothing of plan 27 (any order after Task 1). Decisions: three, marked `Decision:` in 5.3, 5.6 and 5.7.
> Run in a scratch copy on 2026-10-14: the whole suite 527 tests (525 before, two added), only the 4 Linux baseline
> failures (test_tray import, test_redact Windows path, test_usage local day, test_window placement);
> `node --check web/app.js` OK; the headless check of 5.10 50 PASS and `no console errors` at 900 px (Board), 400 and
> 340 px (Task page, Models page); the same check on the unchanged window: 28 FAIL (5.11 step 3).
> Lands on: plan 26 Task 4 (`modelChanges`, `tierCard`, `tuneBad`, `allowanceFold`), plan 25 Tasks 2, 3, 5, 6, 7
> (`showPage`, the `keydown` Board line, `planOpenHtml`, `chainRow`, `stepCost`, `stepCostFig`, `routePane`,
> `planPane`, `renderTaskPage`, `ITABS`), plan 25 Task 1 (`Handler._measure`, `folds_ok`), plan 26 Task 3
> (`Handler._config`). Other plan 27 tasks: Task 4 changes the Task page's as-sent view (`handoffSections` callers in
> the Task page drawing), none of the functions here; Task 1 changes `Hub.save_models`' error handling, not its merge
> (this task only tests the merge); no other task touches `_measure`, `_config` or the module constants.

**Files**
- Modify: `console/server.py` (module constants: `folds_ok` moved below them; `Handler._config`: indentation of its
  last four lines; `Handler._measure`: the `if` line)
- Modify: `web/app.js` (`showPage`, `chainRow`, new `PLAN_FOLDS` and `planFoldKey` before `planOpenHtml`, the `mk` line
  of `planOpenHtml`, `renderTaskPage`'s first two lines, `modelChanges`, `tierCard`, new `allowBad` before `tuneBad`,
  `tuneBad`'s first `if`, `allowanceFold`'s `rows`, new `costUnknown` and `stepCost` replaced, `ITABS` removed,
  `stepCostFig`, `routePane`'s Goal line, `planPane`'s Edit lines, the `keydown` handler's Board line)
- Modify: `web/style.css` (`.note.ink`; `.rhid .rs` joins the `.rs` rule; `.rhid .x` joins the `.rrow .x` rules;
  `.rhid.one`, `.rhid.one .nm`, `.rhid .x`; `.now`'s font; `.chain .row.short`)
- Modify: `tests/test_server.py` (two tests in `TaskServerTest`)

What the review found, in short: a Models page Save posts every tier as soon as one changed, so a tier that still names
a model gone from models.json (a hidden row with no remove button) makes every tier Save fail with `unknown model`
until config.json is edited by hand (B6). `_measure` takes `²` as a digit and `int()` then raises, so the
connection drops (B8). Ctrl+N and Ctrl+P on the Board go to the list without `closeBoard()`: the window stays 900 px
wide and the service keeps `_board`, so a later grip drag saves `board` instead of `size` (B9). The Board's plan fold
keys are built from the heading text (`plan.sgoal`, `plan.ststep2code`), one window.json slot per `### Step N` (G3).
`.chain .row.short` has no rule (G4). An all-unpriced step shows no `cost unknown` anywhere (G7: the Task page row
shows nothing because the service stores `step_cost` 0, the Board shows `0.00`). Allowance fields take any text and
fail only at the server (G9). Nits: `routePane`'s inline style, dead `ITABS` and `at`/`run`, `.now`'s font, `boardKey`
eats Enter and the arrows on a focused inspector button, `planPane`'s Edit condition differs from 5.6, `stepCost`
sums attempts instead of reading `s.cost`, `folds_ok` sits between constants, `_config` loses its indentation.

## 5.1 `console/server.py` (constants, `Handler._config`, `Handler._measure`)

Replace these lines (after `BUSY = {"running", "quiet", "stall"}`) whole:

```python


def folds_ok(folds) -> bool:
    """window.json `folds`: {fold key: open} with at most FOLDS_MAX keys of the FOLD_KEY shape."""
    return (isinstance(folds, dict) and len(folds) <= FOLDS_MAX
            and all(isinstance(k, str) and FOLD_KEY.fullmatch(k) and isinstance(v, bool) for k, v in folds.items()))
AUTO_HANDOFF_STATES = ("replied", "idle", "verified", "verify_failed")  # plan 23: a turn that ended
PROBE_S = 20
READ_ONLY_TOOLS = "Read,Grep,Glob"  # a kind whose tools are exactly these is read only
```

with:

```python
AUTO_HANDOFF_STATES = ("replied", "idle", "verified", "verify_failed")  # plan 23: a turn that ended
PROBE_S = 20
READ_ONLY_TOOLS = "Read,Grep,Glob"  # a kind whose tools are exactly these is read only


def folds_ok(folds) -> bool:
    """window.json `folds`: {fold key: open} with at most FOLDS_MAX keys of the FOLD_KEY shape."""
    return (isinstance(folds, dict) and len(folds) <= FOLDS_MAX
            and all(isinstance(k, str) and FOLD_KEY.fullmatch(k) and isinstance(v, bool) for k, v in folds.items()))
```

(the two blank lines before `class Hub:` stay). In `Handler._config`, replace the last four lines of the returned dict:

```python
                "handoff_auto": bool(cfg["handoff_auto"]),
            "kind_pins": cfg.get("kinds") or {}, "tuning": tuning.view(cfg),
            "kind_rules": {k: {"rank": r[0], "effort": r[1], "tools": r[2]} for k, r in tasks.RULES.items()},
            "board_tab": window.get("board_tab", "chat"), "folds": window.get("folds") or {}}
```

with (the same keys, aligned with the dict's other lines):

```python
                "handoff_auto": bool(cfg["handoff_auto"]),
                "kind_pins": cfg.get("kinds") or {}, "tuning": tuning.view(cfg),
                "kind_rules": {k: {"rank": r[0], "effort": r[1], "tools": r[2]} for k, r in tasks.RULES.items()},
                "board_tab": window.get("board_tab", "chat"), "folds": window.get("folds") or {}}
```

In `Handler._measure`, replace the line

```python
        if not project or len(project) > 1000 or not n.isdigit():
```

with:

```python
        if not project or len(project) > 1000 or not (n.isascii() and n.isdigit() and len(n) <= 4):
```

`isascii` keeps out `²` (B8: `isdigit` true, `int` raises) and the other Unicode digits `int` would read; four digits
are more than `tasks.measure` ever needs (the Board asks for 10).

## 5.2 `web/app.js`: `showPage` and the Board's key line (B9, the `boardKey` nit)

Replace the first three lines of `showPage`:

```js
function showPage(name) {
  page = name;
  closePicker();
```

with:

```js
function showPage(name) {
  if (boardFrom && name !== "board" && !(name === "session" && backTo && backTo.page === "board")) {  // plan 27 B9: the Board left by any other way than closeBoard
    boardFrom = null;
    if (backTo && backTo.page === "board") backTo = null;
    if (native()) window.pywebview.api.board(false).catch(() => {});  // the compact size again; the service drops _board
  }
  page = name;
  closePicker();
```

`boardFrom` is set from `openBoard` to `closeBoard` and nowhere else, so it is the "window is wide" flag. `closeBoard`
clears it before its own `board(false)` and the page it returns to, so it never resizes twice. A session opened from
the Board (Enter in `boardKey`, a `data-open` click in `#bwrap` or `#bchain`: both set `backTo = { page: "board" }`
first) keeps the wide window, as plan 25 2.8 says; its Esc (`goBack`) returns to the Board. Every other way out (Ctrl+N
`go("new")`, Ctrl+P `openPicker`, `go("list")`, the Settings band's links, a `data-here` click, Clear) now shrinks the
window and drops `backTo` to the Board.

In the `document.addEventListener("keydown", ...)` handler, replace the line

```js
  if (page === "board" && form === "open" && BOARD_KEYS.has(e.key) && $("pop").hidden && !inField && !e.target.closest(".tabs")) return boardKey(e);
```

with:

```js
  const onCtl = e.key !== "Escape" && e.target.matches('[data-page="board"] button, [data-page="board"] select');  // plan 27: Enter presses it, the arrows scroll
  if (page === "board" && form === "open" && BOARD_KEYS.has(e.key) && $("pop").hidden && !inField && !onCtl && !e.target.closest(".tabs")) return boardKey(e);
```

On a focused button or select of the Board, Enter and the arrows keep their browser meaning (Enter clicks the button,
ArrowDown scrolls `.binsp`); Esc still goes to `boardKey` (clears the pick, then closes). The chain's blocks are
`div role="button"`, not `button`, so the arrows still move the pick there.

## 5.3 `web/app.js`: the Models page (B6, G9)

Replace `modelChanges` whole:

```js
function modelChanges() {  // the keys a Save would post, with their values (D1 a: only what differs from the page's load)
  if (!medit) return {};
  const out = {}, saved = savedTiers();
  for (const [k, t] of Object.entries(cfg.tuning)) if (!same(medit.values[k], t.value)) out[k] = medit.values[k];
  if (!same(cleanPins(medit.kinds), cleanPins(cfg.kind_pins || {}))) out.kinds = cleanPins(medit.kinds);
  const tiers = Object.fromEntries(Object.entries(medit.tiers).filter(([t, rows]) => !same(rows, saved[t])));  // plan 27 B6: only the tiers that changed; the service merges per tier
  if (Object.keys(tiers).length) out.tiers = tiers;
  return out;
}
```

The service already merges per tier (`paths.set_config(..., merge=("tiers",))` updates config.json's `tiers` one level
deep; `Hub.save_models` does `{**self.cfg["tiers"], **value}`): `test_a_one_tier_save_keeps_the_other_tiers_as_written`
(5.9) pins it. This also fixes the plan 26 nit "the first tier Save freezes all three tiers into config.json".

In `tierCard`, replace the line

```js
  const hid = hidden.length ? `<div class="rhid" title="Turn the CLI on in Settings and its models come back">${hidden.length} hidden · ${esc(whyHidden(hidden[0].rung))}</div>` : "";
```

with:

```js
  const open = mqOpen.has("h" + tier);  // plan 27 B6: the hidden rungs listed on demand, each with its remove button (a model gone from models.json blocks its tier's Save)
  const hid = hidden.length ? `<div class="rhid" title="Turn the CLI on in Settings and its models come back">${hidden.length} hidden · ${esc(whyHidden(hidden[0].rung))} · <button class="rs" data-q="h${tier}" aria-expanded="${open}">${open ? "hide" : "show"}</button></div>` : "";
  const gone = rows.map((r, i) => {
    if (!open || !whyHidden(r.rung)) return "";
    const m = r.rung.includes(":") ? r.rung.slice(r.rung.indexOf(":") + 1) : r.rung;
    return `<div class="rhid one"><span class="nm">${esc(modelText(r.rung))} · ${esc(whyHidden(r.rung))}</span><button class="x" data-mrm="${tier}:${i}" aria-label="Remove ${esc(m)}" title="Remove from ${tier}">&#10005;</button></div>`;
  }).join("");
```

and in its `return` line replace `${body}${hid}` with `${body}${hid}${gone}`.

Decision: the hidden rungs are listed behind a `show` / `hide` button on the existing `N hidden · <reason>` line, not
always, because a fresh config.json has 8 hidden rungs (codex, opencode and cmd are off by default) and listing them all
would bury the visible rows; the line and its text stay as plan 26 pinned them. The toggle reuses `mqOpen` and the
existing `[data-q]` click branch; the remove button reuses `data-mrm` (the index is the row's place in
`medit.tiers[tier]`, hidden rows included, as the Alt+arrow code already assumes).

Insert before `function tuneBad(k) {`:

```js
function allowBad(key) {  // plan 27 G9: every window of a model key a finite number in tuning's allowance range
  const t = cfg.tuning.allowances, row = (medit.values.allowances || {})[key] || {};
  return Object.values(row).some((n) => typeof n !== "number" || !isFinite(n) || n < t.min || n > t.max) ? `a number between ${t.min} and ${t.max}` : "";
}
```

In `tuneBad`, replace the line

```js
  if (t.unit === "bool" || t.unit === "rung" || k === "allowances") return "";
```

with:

```js
  if (k === "allowances") { const key = Object.keys(v || {}).find(allowBad); return key ? `${key}: ${allowBad(key)}` : ""; }
  if (t.unit === "bool" || t.unit === "rung") return "";
```

`renderModels` already disables Save and says `a value is out of range` when any `tuneBad(k)` is non-empty, so the
allowances join that with no other change. The range is `cfg.tuning.allowances.min` and `.max`, which `/api/config`
sends from `tuning.TUNING["allowances"]` (0 and 100000): the same numbers `tuning._allowances` checks.

In `allowanceFold`, replace the `const rows = ...` statement (two lines) with:

```js
  const rows = keys.map((key) => { const bad = allowBad(key); return `<div class="tf al${bad ? " bad" : ""}"><span class="nm">${esc(key)}</span><span class="v">${["day_usd", "week_usd", "month_usd"].map((w) =>
    `<input inputmode="decimal" data-mal="${esc(key)}:${w}" aria-label="${esc(key)} ${w.split("_")[0]} USD" placeholder="${w[0]}" value="${(al[key] || {})[w] ?? ""}">`).join("")}</span><span class="sub">${bad ? esc(bad) : "day · week · month, USD; empty: no allowance"}</span></div>`; }).join("");
```

The existing `.tf.bad .v input` and `.tf.bad .sub` rules paint the row red. The `change` handler is unchanged: a bad
text is stored as `NaN` (`Number("abc")`), which `allowBad` refuses; an emptied field deletes the window as before.

## 5.4 `web/app.js`: plan fold keys (G3)

Insert before `function planOpenHtml(t, d, cur, o = {}) {`:

```js
const PLAN_FOLDS = { goal: "goal", decisions: "dec", "out of scope": "out", files: "files", steps: "steps", acceptance: "acc" };
function planFoldKey(key) {  // plan 27 G3: the six pinned keys of plan 25 5.6; every ### Step N shares plan.steps; any other heading is not kept
  const k = key.startsWith("st:") ? "steps" : PLAN_FOLDS[key.slice(key.indexOf(":") + 1).trim().toLowerCase()];
  return k ? "plan." + k : "";
}
```

In `planOpenHtml`, replace the first line of `const mk = ...`:

```js
  const mk = (key, label, info, inner, open) => o.board ? fold(label, info, inner, { cls: "hf", key: "plan." + key.replace(/[^a-z0-9]+/gi, "").toLowerCase().slice(0, 30), open })
```

with:

```js
  const mk = (key, label, info, inner, open) => o.board ? fold(label, info, inner, { cls: "hf", key: planFoldKey(key), open })
```

(the `: pfold(...)` line under it stays: the Task page keeps its `planOpen` keys). The keys `mk` receives are
`"s:" + <## heading>` and `"st:" + <### Step N heading>`; the six `## ` headings are `plan.HEADINGS`. A heading outside
them (none passes `plan.check`) gets `""`, so `fold` falls back to its label memory and takes no window.json slot.

## 5.5 `web/app.js`: costs (G7 and the `stepCost` nit)

Replace `function stepCost(s) { ... }` whole (four lines) with:

```js
function costUnknown(s) {  // plan 27 G7: a step whose cost no attempt reported (plan 5 README 3.6); a running attempt counts 0 until it ends
  const a = s.attempts || [];
  return s.cost == null || (a.length > 0 && a.every((x) => x.cost == null));
}
function stepCost(s) {  // plan 25 3: the service's s.cost, the sum of its attempts
  if (s.state === "planned") return "";
  return costUnknown(s) ? '<span class="cost unk" title="the harness reported no usage">cost unknown</span>' : `<span class="cost">${money(s.cost)}</span>`;
}
```

Replace `function stepCostFig(s) { ... }` whole (four lines) with:

```js
function stepCostFig(s) {  // the cost figure for the inspector's meta: the service's s.cost, or the word unknown
  return costUnknown(s) ? "unknown" : money(s.cost);
}
```

Why `costUnknown` reads the attempts: `tasks.start_attempt` writes `cost: 0` on a new attempt; `Hub.sync_costs` sets the
attempt's `cost` to the session row's `cost` when the run ends, which is `None` for a harness that reported none (plan
5 Task 4), and `s.cost = tasks.step_cost(s)`, which counts `None` as 0. So an all-unpriced step has `s.cost == 0` and
every attempt `cost == null`; a step still running has a `0` attempt and is not unknown; a step with one priced attempt
shows the priced sum. Both `/api/task` (the raw task) and the snapshot's task row (`attempts: [{session, cost, why}]`)
carry the attempts' costs.

In `chainRow` (the Task page), replace the line

```js
  const sub = [verdict, s.retries ? "retry " + s.retries : "", stepTries(s), waits ? `<span class="y">${esc(t.why)}</span>` : esc(s.goal)].filter(Boolean).join(" · ");
```

with:

```js
  const unpriced = ran && costUnknown(s) ? '<span title="no attempt of this step reported a cost">cost unknown</span>' : "";  // plan 27 G7: the words, in the sub line (the cost column is 38 px)
  const sub = [verdict, unpriced, s.retries ? "retry " + s.retries : "", stepTries(s), waits ? `<span class="y">${esc(t.why)}</span>` : esc(s.goal)].filter(Boolean).join(" · ");
```

and the line

```js
    <span class="m c">${!ran ? "" : s.cost == null ? "?" : s.cost ? money(s.cost) : ""}</span>
```

with:

```js
    <span class="m c">${!ran || costUnknown(s) ? "" : s.cost ? money(s.cost) : ""}</span>
```

Decision: on the Task page the words go first in the row's sub line and the cost column stays empty, because the
column is 38 px (`.chain .row` grid `41px minmax(0, 1fr) 38px 46px`) and `cost unknown` does not fit it at 340 px; on
the Board's chain block and the inspector's meta the words take the figure's place. Plan 25's `? cost` wording
(03-chain.md, its drift guard "cost unknown is `? cost`") is replaced by plan 5's `cost unknown`; Task 7 amends plan 25.

## 5.6 `web/app.js`: `planPane`'s Edit (plan 25 5.6 nit)

In `planPane`, replace the two lines

```js
  const canEdit = design && next && next.state === "planned" && (waits || t.owner === "fred");
  const edit = canEdit ? `<button class="btn sm" data-tact="edit" aria-expanded="${planEdit}" title="The plan in place, until the next step starts">Edit</button>` : "";
```

with:

```js
  const canEdit = design && next && next.state === "planned";  // plan 25 5.6; the service takes the Save while the task waits on its plan or is paused
  const edit = canEdit ? `<button class="btn sm" data-tact="edit" aria-expanded="${planEdit}" title="The plan in place, until the next step starts${waits || t.owner === "fred" ? "" : "; Save works while the task waits on its plan or is paused"}">Edit</button>` : "";
```

Decision: the button follows plan 25 5.6 exactly ("on the design step while the next step has not started"; plan 24
exposes no `d.levers.plan`), and the extra `waits || owner fred` test moves into the button's title, because
`Hub.edit_plan` stays the one gate (409 `the plan can be edited while the task waits on it or is paused`, shown in
`#b-msg` by the existing Save handler) and the title says when Save will be taken. `waits` stays in use.

## 5.7 `web/app.js`: dead code and the inline style (plan 25 nits)

- Remove the line `const ITABS = ["chat", "recv", "hand", "route", "plan"];` (under `// the inspector (plan 25 Tasks
  5 and 6)`). Nothing reads it; the start-up code and `BOARD_TABS` in server.py keep their own lists.
- In `renderTaskPage`, replace its first two lines

  ```js
    const row = (snap.tasks || []).find((x) => x.id === taskId), at = row && row.steps.find((x) => x.n === row.current);
    const run = at && snap.sessions.find((x) => x.id === at.session);
  ```

  with:

  ```js
    const row = (snap.tasks || []).find((x) => x.id === taskId);
  ```

  (`taskRowSig` computes its own `at` and `run`; leave it as it is.)
- In `routePane`, replace `<p class="note" style="color:var(--ink)">${esc(s.goal)}</p>` with
  `<p class="note ink">${esc(s.goal)}</p>`.

Decision: only `routePane`'s inline style moves to a class, because it is the one the review names; the older
`style="cursor:default"` and `style="margin:0"` lines of plans 17 to 24 are outside this task.

## 5.8 `web/style.css`

After `.note .y { color: var(--you); } .note .r { color: var(--bad); }` insert:

```css
.note.ink { color: var(--ink); }
```

Replace `.ed .rs, .tf .rs {` with `.ed .rs, .tf .rs, .rhid .rs {` (the rest of that rule unchanged). Replace the three
lines from `.rrow .x {` to the `.rhid {` line with:

```css
.rrow .x, .rhid .x { width: 24px; height: 24px; border: 0; border-radius: 5px; background: transparent; color: var(--mut); cursor: pointer; font-size: 11px; }
.rrow .x:hover, .rhid .x:hover { background: var(--raise); color: var(--ink); }
.rhid { padding: 5px 12px; border-top: 1px solid var(--line); font: 11px var(--mono); color: var(--mut); }
.rhid.one { display: flex; align-items: center; gap: 6px; min-width: 0; padding-block: 1px; border-top: 0; }
.rhid.one .nm { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rhid .x { flex: none; }
```

(`min-width: 0` on `.rhid.one` matters: without it a long opencode model name widens the whole `.pcard` past the window
at 340 px.) In the `.now` rule replace `font: 12.5px var(--ui);` with `font: 11.5px var(--mono);` (plan 25 6.5). After
`.chain .row[data-grow] { cursor: pointer; }` (the file's last line) append:

```css
.chain .row.short { padding-block: 5px; }
```

No new token.

## 5.9 Tests (`tests/test_server.py`, class `TaskServerTest`)

Insert before `    def test_models_page_reload_shows_a_hand_edit(self):`:

```python
    def test_a_one_tier_save_keeps_the_other_tiers_as_written(self):
        """Plan 27 B6: the page posts only the tiers that changed; the service merges per tier, so a tier that names
        a model gone from models.json stays in config.json as written and never blocks a Save of another tier."""
        self.folder.mkdir(parents=True, exist_ok=True)
        think = [{"rung": "opus", "effort": "auto"}, {"rung": "codex:gpt-gone", "effort": "high"}]
        read = [{"rung": "haiku", "effort": "auto"}]
        (self.folder / "config.json").write_text(json.dumps({"projects": [str(self.project)], "tiers": {
            "think": think, "write": [{"rung": "sonnet", "effort": "auto"}], "read": read}}), encoding="utf-8")
        status, data = self.call("/api/config/models", {"changes": {"tiers": {"write": ["sonnet", "opus"]}}})
        self.assertEqual(status, 200, data)
        written = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))["tiers"]
        self.assertEqual((written["think"], written["read"]), (think, read))
        self.assertEqual([r["rung"] for r in written["write"]], ["sonnet", "opus"])
        self.assertEqual(self.call("/api/config/models", {"changes": {"tiers": {"read": ["haiku", "sonnet"]}}})[0], 200)
        written = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))["tiers"]
        self.assertEqual(written["think"], think)
        status, data = self.call("/api/config/models", {"changes": {"tiers": {"think": think}}})
        self.assertEqual((status, data["errors"]), (400, {"tiers": "think 2: unknown model: codex:gpt-gone"}))

```

Insert after the last line of `test_measure_route`
(`        self.assertEqual(self.call(f"/api/measure?project={quote(str(self.project))}&n=0")[1]["tasks"], 1)  # n >= 1`):

```python

    def test_measure_refuses_a_digit_that_is_not_ascii(self):
        """Plan 27 B8: `²` passes str.isdigit but not int(); the answer is the promised 400, not a dropped connection."""
        for n in ("%C2%B2", "%D9%A3", "12345"):
            self.assertEqual(self.call(f"/api/measure?project=x&n={n}"), (400, {"error": "bad measure query"}), n)
```

(`%D9%A3` is the Arabic-Indic digit 3, which `int` reads: before the fix it answered 200; `12345` is five digits.)

## 5.10 The headless check (900, 400 and 340 px)

Run it on a scratch data folder and port, never on Fred's `~/.claude/console`. Paths below use `$T` for a scratch
folder and `$R` for the repository; on Fred's Windows box use `py` for `python3` and a `fakeclaude.cmd` containing
`@py "%~dp0..\tests\fake_claude.py" %*`-style absolute paths instead of the shell wrapper.

1. Scratch: `mkdir -p $T/home $T/proj`; in `$T/proj` a git repo with one commit (`printf 'def add(a, b):\n    return a - b\n'
   > calc.py; git init -q; git add .; git commit -qm init`); `$T/fakeclaude`:

   ```sh
   #!/bin/sh
   exec python3 $R/tests/fake_claude.py "$@"
   ```

   (`chmod +x`); `$T/home/config.json` (port 47785, or any free port; the think tier names a model gone from
   models.json, B6's case):

   ```json
   {"projects": ["$T/proj"], "port": 47785, "claude_exe": "$T/fakeclaude",
    "tiers": {"think": [{"rung": "opus", "effort": "auto"}, {"rung": "codex:gpt-gone", "effort": "auto"}]}}
   ```

2. Start the service from `$R`: `CC_CONSOLE_HOME=$T/home python3 -m console --serve` (in the background; note its PID).
3. `python3 $T/mk.py 47785 $T/proj` (below): it makes a `VERDICT-FAIL` task run to its second verify, a `PLAN-OK` task
   run past its design step, then sets `plan_hold` and makes a third that waits on `plan ready: confirm`; it prints the
   three ids: `<plan> <fail> <hold>`.
4. Stop the service (kill that PID only; never `pkill -f "console --serve"`, which also ends other writers' services and
   your own shell), run `python3 $T/unpriced.py $T/home <fail>` (step 1 of the fail task as a harness that reported no
   cost), start the service again.
5. `PW_CHROMIUM=<chromium under /opt/pw-browsers>/chrome-linux/chrome NODE_PATH=<global node_modules with playwright>
   node $T/check.js 47785 <plan> <fail> <hold> $T/home`: every line `PASS`, last line `no console errors`, exit 0 (50
   checks). The browser's own `favicon.ico` 404 is not counted (the page asks for none).
6. Look at two screenshots once (`page.screenshot`): the Tiers tab at 340 px with a `show` opened (the hidden rows end
   in `…` and `✕` inside the card) and the Board at 900 px on the fail task (`cost unknown` on 01 code).

`$T/mk.py`:

```python
"""Plan 27 Task 5 check data: three tasks on the fake claude. Usage: python3 mk.py <port> <project>. Prints the ids."""
import json, sys, time, urllib.request, urllib.error
PORT, PROJECT = int(sys.argv[1]), sys.argv[2]


def call(path, body=None):
    h, data = {"Host": f"127.0.0.1:{PORT}"}, None
    if body is not None:
        h.update({"X-CC": "1", "Content-Type": "application/json"})
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, headers=h)) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def task(words, steps):
    job = call("/api/prep", {"project_dir": PROJECT, "prompt": "CHAIN fix add"})[1]["job"]
    while True:
        row = next((j for j in call("/api/state")[1]["preps"] if j["id"] == job), None)
        if row and row["state"] != "running":
            break
        time.sleep(0.3)
    status, data = call("/api/task", {"prep": row["card"]["id"], "prompt": row["card"]["prompt"] + "\n" + words,
                                      "steps": steps, "effort": "auto"})
    assert status == 200, data
    return data["task"]


def settled(tid):
    while True:
        t = next(x for x in call("/api/state")[1]["tasks"] if x["id"] == tid)
        if t["state"] not in ("planned", "running"):
            return t
        time.sleep(0.5)


fail = task("HANDOFF-OK VERDICT-FAIL", [{"kind": "code", "goal": "fix add"}, {"kind": "verify", "goal": "check the fix"}])
plan = task("HANDOFF-OK PLAN-OK", [{"kind": "design", "goal": "plan the fix"}, {"kind": "code", "goal": "fix add"}])
settled(fail), settled(plan)
assert call("/api/config/models", {"changes": {"plan_hold": True}})[0] == 200
hold = task("HANDOFF-OK PLAN-OK", [{"kind": "design", "goal": "plan the fix"}, {"kind": "code", "goal": "fix add"}])
t = settled(hold)
assert t["state"] == "waiting" and t["why"].startswith("plan "), t
print(plan, fail, hold)
```

`$T/unpriced.py`:

```python
"""Plan 27 Task 5 check data: step 1 of a task as a harness that reported no cost. Run with the service stopped.
Usage: python3 unpriced.py <data folder> <task id>"""
import json, sys
from pathlib import Path
path = Path(sys.argv[1]) / "tasks" / sys.argv[2] / "task.json"
task = json.loads(path.read_text(encoding="utf-8"))
step = task["steps"][0]
for a in step["attempts"]:
    a["cost"] = None
step["cost"] = 0  # what tasks.step_cost gives for attempts that are all unpriced
path.write_text(json.dumps(task, indent=1), encoding="utf-8")
```

`$T/check.js` (stubs `window.pywebview.api` on the 900 px page so `native()` is true and every `board(on)` call is
recorded; reads the page's own globals `page`, `boardFrom`, `boardPick`, `medit`, `mmsg`):

```js
// plan 27 Task 5: the window checks in headless Chromium
// node check.js <port> <plan task id> <fail task id> <hold task id> <data folder>   (the ids as mk.py prints them)
const { chromium } = require("playwright");
const [port, planTask, failTask, holdTask, home] = process.argv.slice(2);
const fs = require("fs");
const URL = `http://127.0.0.1:${port}/`;
const out = [], errors = [];
const ok = (cond, what) => { out.push(`${cond ? "PASS" : "FAIL"} ${what}`); };
const STUB = () => {  // window.pywebview.api: every call recorded, each answers null
  window.__calls = [];
  window.pywebview = { api: new Proxy({}, { get: (_, name) => async (...a) => { window.__calls.push([name, ...a]); return null; } }) };
};
async function open(browser, w, h, stub) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  page.on("console", (m) => { if (m.type() === "error" && !/favicon\.ico$/.test(m.location().url || "")) errors.push(`${w}px: ${m.text()}`); });  // the browser's own favicon request is not the page's
  page.on("pageerror", (e) => errors.push(`${w}px: ${e.message}`));
  page.on("response", (r) => { if (r.status() >= 400) errors.push(`${w}px: ${r.status()} ${r.request().method()} ${r.url()}`); });
  if (stub) await page.addInitScript(STUB);
  await page.goto(URL);
  await page.waitForFunction(() => typeof snap !== "undefined" && snap && cfg);
  return page;
}
const noOverflow = (page, sel) => page.evaluate((sel) => [...document.querySelectorAll(sel)].every((e) => e.scrollWidth <= e.clientWidth + 1)
  && document.documentElement.scrollWidth <= innerWidth, sel);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.PW_CHROMIUM });
  // 1. Board at 900 x 680, native stub: B9, boardKey guard, G3 fold keys, G7 words, .now font, routePane class
  let page = await open(browser, 900, 680, true);
  await page.evaluate((id) => openBoard(id), planTask);
  await page.waitForFunction(() => page === "board" && document.querySelector(".binsp"));
  await wait(500);
  ok(await page.evaluate(() => JSON.stringify(window.__calls.filter((c) => c[0] === "board")) === "[[\"board\",true]]"), "Board opens with board(true)");
  ok(await noOverflow(page, ".bchain, .binsp"), "900 px Board: no horizontal overflow");
  ok(await page.evaluate(() => { const n = document.createElement("div"); n.className = "now"; document.body.append(n); const f = getComputedStyle(n), r = f.fontSize + " " + f.fontFamily === "11.5px " + getComputedStyle(document.documentElement).getPropertyValue("--mono").trim(); n.remove(); return r; }), ".now is 11.5px var(--mono) (plan 25 6.5)");
  await page.evaluate(() => { boardPick = "s1"; itab = "plan"; return renderBoard(); });
  await wait(300);
  const keys = await page.evaluate(() => [...document.querySelectorAll(".binsp [data-fkey]")].map((b) => b.dataset.fkey));
  ok(keys.length && keys.every((k) => ["plan.goal", "plan.dec", "plan.out", "plan.files", "plan.steps", "plan.acc"].includes(k)), `G3 plan fold keys: ${keys.join(" ")}`);
  ok(keys.includes("plan.steps"), "G3 a non-current ### Step N takes plan.steps");
  ok(await page.evaluate(() => !document.querySelector('.binsp [data-tact="edit"]')), "no Edit on a design step whose next step ran");
  // boardKey: Enter on a focused inspector button presses it; ArrowDown leaves the pick alone
  const fh = '.binsp .hf .fh';  // the plan's first fold head (Goal)
  const before = await page.$eval(fh, (b) => b.getAttribute("aria-expanded"));
  await page.focus(fh);
  await page.keyboard.press("Enter");
  ok(await page.$eval(fh, (b, was) => b.getAttribute("aria-expanded") !== was, before) && await page.evaluate(() => page === "board" && boardPick === "s1"), "Enter on a focused fold head toggles it, the pick stays");
  await page.evaluate(() => { const i = document.querySelector(".binsp"); i.style.maxHeight = "120px"; i.scrollTop = 0; });
  await page.focus(fh);
  await page.keyboard.press("ArrowDown");
  await wait(300);
  ok(await page.evaluate(() => boardPick === "s1" && document.querySelector(".binsp").scrollTop > 0), "ArrowDown on a focused button scrolls .binsp, the pick stays");
  await page.evaluate(() => document.querySelector(".binsp").style.maxHeight = "");
  await page.evaluate(() => { boardPick = "s1"; itab = "route"; return renderBoard(); });
  await wait(300);
  ok(await page.evaluate(() => !!document.querySelector(".ipane p.note.ink") && !document.querySelector(".ipane p[style]")), "routePane: class ink, no inline style");
  await page.evaluate(() => document.querySelector("#bchain [data-bpick]").focus());
  await page.keyboard.press("ArrowDown");
  await wait(300);
  ok(await page.evaluate(() => boardPick !== "s1"), "ArrowDown on the chain still moves the pick");
  // B9: Ctrl+N on the Board
  await page.evaluate(() => { document.activeElement.blur(); window.__calls = []; });
  await page.keyboard.press("Control+n");
  await wait(300);
  ok(await page.evaluate(() => page === "list" && boardFrom === null && JSON.stringify(window.__calls) === "[[\"board\",false]]"), "B9 Ctrl+N leaves the Board with board(false)");
  // B9: Ctrl+P on the Board
  await page.evaluate((id) => openBoard(id), planTask);
  await page.waitForFunction(() => page === "board");
  await page.evaluate(() => { window.__calls = []; document.activeElement.blur(); });
  await page.keyboard.press("Control+p");
  await wait(300);
  ok(await page.evaluate(() => page === "list" && boardFrom === null && window.__calls.some((c) => c[0] === "board" && c[1] === false)), "B9 Ctrl+P leaves the Board with board(false)");
  await page.keyboard.press("Escape");
  // a session opened from the Board keeps the wide window; Esc returns to the Board; Esc again closes it once
  await page.evaluate((id) => openBoard(id), planTask);
  await page.waitForFunction(() => page === "board");
  await page.evaluate(() => { boardPick = "s1"; return renderBoard(); });
  await page.evaluate(() => { window.__calls = []; document.querySelector("#bchain [data-bpick='s1']").focus(); });
  await page.keyboard.press("Enter");
  await wait(300);
  ok(await page.evaluate(() => page === "session" && boardFrom !== null && !window.__calls.some((c) => c[0] === "board")), "a session opened from the Board keeps the Board size");
  await page.evaluate(() => document.activeElement.blur());
  await page.keyboard.press("Escape");
  await wait(300);
  ok(await page.evaluate(() => page === "board"), "Esc on that session returns to the Board");
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await wait(300);
  ok(await page.evaluate(() => page === "list" && JSON.stringify(window.__calls.filter((c) => c[0] === "board")) === "[[\"board\",false]]"), "Esc Esc closes the Board with one board(false)");
  // plan 25 5.6: Edit on the design step of a task that waits on its plan
  await page.evaluate((id) => openBoard(id), holdTask);
  await page.waitForFunction(() => page === "board" && document.querySelector(".sb"));
  await page.evaluate(() => { boardPick = "s1"; itab = "plan"; return renderBoard(); });
  await wait(300);
  ok(await page.evaluate(() => !!document.querySelector('.binsp [data-tact="edit"]')), "Edit shows on the design step while the next step is planned (plan 25 5.6)");
  // G7: the chain words
  await page.evaluate((id) => openBoard(id), failTask);
  await page.waitForFunction(() => page === "board" && document.querySelector(".sb"));
  await wait(300);
  const costs = await page.evaluate(() => [...document.querySelectorAll("#bchain .sb .cost")].map((c) => c.textContent));
  ok(costs[0] === "cost unknown" && costs.slice(1).every((c) => /^\d+\.\d\d$/.test(c)), `G7 Board chain costs: ${costs.join(" | ")}`);
  ok(await noOverflow(page, ".bchain, .binsp"), "900 px Board (fail task): no horizontal overflow");
  await page.close();

  // 2. Task page at 400 and 340: G4 short rows, G7 words in the sub line
  for (const w of [400, 340]) {
    page = await open(browser, w, 760, false);
    await page.evaluate((id) => openTask(id), failTask);
    await page.waitForFunction(() => document.querySelector("#tscroll .chain .row"));
    await wait(300);
    const pad = await page.evaluate(() => { const r = document.querySelector(".chain .row.short"); return r ? getComputedStyle(r).paddingTop : "none"; });
    ok(pad === "5px", `${w} px Task page: .chain .row.short padding ${pad}`);
    const subs = await page.evaluate(() => [...document.querySelectorAll(".chain .row")].map((r) => (r.querySelector(".c") || {}).textContent + " / " + ((r.querySelector(".sub") || {}).textContent || "").slice(0, 40)));
    ok(subs[0].startsWith(" / cost unknown · ") && subs.slice(1).every((x) => /^\d+\.\d\d \//.test(x)), `${w} px G7 Task page rows (cost / sub): ${subs.join(" | ")}`);
    ok(await noOverflow(page, "#tscroll"), `${w} px Task page: no horizontal overflow`);
    await page.close();
  }

  // 3. Models page at 400 and 340: B6 tiers posted, hidden rung removable; G9 allowance rows
  for (const w of [400, 340]) {
    page = await open(browser, w, 760, false);
    await page.evaluate(() => { showPage("models"); });
    await page.waitForFunction(() => medit);
    await page.evaluate(() => { mtab = "tiers"; renderModels(); });
    const hid = await page.evaluate(() => [...document.querySelectorAll(".rhid")].map((r) => r.textContent.trim()));
    ok(hid.length === 3 && !hid.some((x) => /✕/.test(x)), `${w} px hidden lines, closed: ${hid.join(" | ")}`);
    const eff = w === 400 ? "high" : "low";
    await page.selectOption('select[data-meff="write:0"]', eff);
    const ch = await page.evaluate(() => modelChanges());
    ok(JSON.stringify(Object.keys(ch.tiers || {})) === '["write"]', `${w} px B6 a write edit posts only write: ${JSON.stringify(ch)}`);
    await page.evaluate(() => saveModels());
    await page.waitForFunction(() => !mbusy);
    const saved = JSON.parse(fs.readFileSync(home + "/config.json", "utf8")).tiers;
    ok(await page.evaluate(() => mmsg === "") && saved.write[0].effort === eff && saved.think.some((r) => r.rung === "codex:gpt-gone"),
      `${w} px B6 Save: ${await page.evaluate(() => mmsg || "saved")}; think as written: ${JSON.stringify(saved.think)}`);
    await page.selectOption('select[data-meff="write:0"]', "medium");
    if (await page.$('[data-q="hthink"]')) await page.click('[data-q="hthink"]');
    const listed = await page.evaluate(() => [...document.querySelectorAll(".rhid.one")].map((r) => r.textContent.trim()));
    ok(listed.some((x) => /gpt-gone/.test(x)), `${w} px show lists the hidden think rungs: ${listed.join(" | ")}`);
    if (await page.$('[data-q="hwrite"]')) await page.click('[data-q="hwrite"]');  // the longest hidden names
    ok(await page.evaluate(() => [...document.querySelectorAll(".pcard")].every((c) => c.getBoundingClientRect().right <= innerWidth)), `${w} px the open hidden lists keep every card inside the window`);
    if (await page.$('.rhid.one button[aria-label="Remove gpt-gone"]')) await page.click('.rhid.one button[aria-label="Remove gpt-gone"]');
    const ch2 = await page.evaluate(() => Object.keys(modelChanges().tiers || {}).sort().join());
    ok(ch2 === "think,write" && !(await page.$('.rhid.one button[aria-label="Remove gpt-gone"]')), `${w} px removing the hidden rung changes think: ${ch2}`);
    ok(await noOverflow(page, "#mscroll"), `${w} px Tiers tab: no horizontal overflow`);
    await page.evaluate(() => { resetModels(); mtab = "tuning"; renderModels(); });
    await page.evaluate(() => { const f = document.querySelector(".alw [data-fold]"); if (f.getAttribute("aria-expanded") !== "true") f.click(); });
    const inp = '.alw input[data-mal$=":day_usd"]';
    for (const [v, bad] of [["abc", true], ["200000", true], ["-1", true], ["50", false], ["", false]]) {
      await page.fill(inp, v);
      await page.keyboard.press("Tab");  // the change event, as a person leaving the field
      const st = await page.evaluate(() => ({ bad: !!document.querySelector(".alw .tf.al.bad"), save: (document.querySelector('[data-mact="save"]') || {}).disabled }));
      ok(st.bad === bad && (st.save === undefined ? !bad : st.save === bad), `${w} px G9 allowance "${v}": row bad ${st.bad}, Save disabled ${st.save}`);
    }
    ok(await noOverflow(page, "#mscroll"), `${w} px Tuning tab: no horizontal overflow`);
    await page.close();
  }
  await browser.close();
  console.log(out.join("\n"));
  console.log(errors.length ? "CONSOLE ERRORS:\n" + errors.join("\n") : "no console errors");
  process.exit(out.some((l) => l.startsWith("FAIL")) || errors.length ? 1 : 0);
})();
```

The check saves the write tier twice (400 px `high`, 340 px `low`) into the scratch config.json: run it on a fresh `$T`
each time, or the 400 px Save finds no change. None of `mk.py`, `unpriced.py`, `check.js` is committed.

## 5.11 Steps

1. Add the two tests of 5.9; run
   `py -m unittest tests.test_server.TaskServerTest.test_a_one_tier_save_keeps_the_other_tiers_as_written
   tests.test_server.TaskServerTest.test_measure_refuses_a_digit_that_is_not_ascii`:
   the measure test errors with `http.client.RemoteDisconnected: Remote end closed connection without response` (the
   service prints `ValueError: invalid literal for int() with base 10: '²'`); the tiers test passes already (it pins
   the service's per-tier merge that 5.3 relies on: the B6 fault is the window's).
2. Apply 5.1; both tests are green, and `test_measure_route` still is.
3. Before touching `web/`, run the headless check of 5.10 on the unchanged window: it reports 28 FAIL, among them
   `.now is 11.5px var(--mono)`, `G7 Board chain costs: 0.00 | 0.01 | 0.01 | 0.01`,
   `G7 Task page rows (cost / sub):  / fix add | ...`,
   `G3 plan fold keys: plan.sgoal plan.sdecisions plan.soutofscope plan.sfiles plan.ststep2code plan.sacceptance`,
   `B9 Ctrl+N leaves the Board with board(false)`, `B9 Ctrl+P ...`, `Enter on a focused fold head toggles it`,
   `.chain .row.short padding 7px`, `B6 a write edit posts only write: {"tiers":{"read":...,"write":...,"think":...}}`,
   `B6 Save: tiers: think 2: unknown model: codex:gpt-gone`, `G9 allowance "abc": row bad false, Save disabled false`,
   and the console shows `400 POST .../api/config/models`. (Use a fresh `$T` for the run after the fix.)
4. Apply 5.2 to 5.8; `node --check web/app.js`.
5. Run the headless check again on a fresh `$T`: 50 PASS, `no console errors`; look at the two screenshots of 5.10
   step 6.
6. Run the whole suite `py -m unittest discover -s tests`: two tests more than before, nothing new failing (on Linux
   only the 4 baseline failures).
7. Commit: `plan 27 task 5: window fixes: tiers posted per tier, hidden rungs removable, Board left cleanly, plan fold keys, cost unknown, allowance checks, measure query (B6 B8 B9 G3 G4 G7 G9)`.

## 5.12 Drift guards

- `server.Hub.save_models` and `paths.set_config` are not changed here: the per-tier merge is theirs, the window only
  stops sending tiers it did not change. Never send a tier the page did not edit.
- The window size changes only through `WindowApi.board(on)`; `showPage` calls `board(false)` only while `boardFrom` is
  set, and `closeBoard` stays the Board's normal way out (it clears `boardFrom` first). A session opened from the Board
  keeps the Board size and `backTo = { page: "board" }`.
- `boardKey` still owns the arrows, Enter and Esc on the chain and on the page; it yields only Enter and the arrows on a
  focused `button` or `select` of the Board page, and never Esc.
- The Board's plan fold keys are exactly `plan.goal`, `plan.dec`, `plan.out`, `plan.files`, `plan.steps`, `plan.acc`
  (plan 25 5.6); the Task page's `pfold` keys do not change.
- Unknown cost is the words `cost unknown` (`unknown` after `cost` in the inspector meta), never `0.00`, `?` or an
  estimate; a known cost is `money(s.cost)`, the service's sum, not a sum done in the window.
- The allowance range comes from `/api/config` `tuning.allowances` (`tuning.TUNING`), never a number written in app.js.
- `_measure` answers 400 `bad measure query` for anything but 1 to 4 ASCII digits; `tasks.measure` is unchanged.
- No new token in style.css; no inline style added to app.js; `cc_events.py` is not touched; nothing here writes
  outside the data folder.
