# Task 5: The window: tier groups, the over-pace line, Models share of pace, Verify FAIL by hour

> Contract: [README.md](README.md) 3.7 (what `/api/config`, `/api/usage` and the snapshot carry). Design: interface
> doc section 3 (the today strip: `N models over pace · fills ▾` opens the breakdown, whose fills line lists the
> models over pace with `Usage ›`), 5 (the model select grouped think / write / read, off rungs hidden), 9 (Usage:
> Models · share of pace, one bar of 20 cells for the binding window, the row opens to the three windows, dotted
> bars without an allowance, `cost unknown · n runs`; Verify FAIL by hour as a fold), 12 (ID-6). Mock:
> `design/rework/locked/cells-board.html`, `listHtml` (`.overpace`, `.todaymore`, `.fline`) and `usageHtml`
> (`.mfill`, `.heat`), CSS lines 155 to 160 and 410 to 430. Depends on Task 4.
> Run in a scratch copy on 2026-10-14 (plans 5, 23, 24 not placed): `node --check web/app.js` OK; the Usage
> functions rendered in node over a seeded `usage` (a row at 150 % orange, a dotted `kimi-k3` row with
> `cost unknown · 2 runs`, the heatmap's `sonnet most FAIL at 15:00`). No browser on that box: the headless check
> (5.7 step 3) is the executor's.
> Lands on: plan 23 Task 6 (`fold(label, info, body, o)`, its `[data-fold]` click branch and the `.fold` / `.fh` /
> `.fb` CSS: this task calls `fold` and adds nothing to them; the scratch copy, without plan 23, carried a 6-line
> `fold` of the same signature), plan 5 Task 6 (the Prep card's and step row's model select: `modelOptions` replaced
> whole, its callers keep their arguments), plan 25 (the Board draws its own rows; nothing here).

**Files**
- Modify: `web/app.js` (`modelOptions` replaced whole with `RANK_GROUP` and `rungFits`; the step row's call;
  `renderTop`'s today strip; the Usage page's state, `usageDay`'s families line, new `fillCells`, `sharePct`,
  `fillWin`, `fillRow`, `usageFills`, `usageFails`, `renderUsage`, the `#uscroll` click handler; the document click
  handler's selector and `#today` branch)
- Modify: `web/index.html` (`#overpace`, one line)
- Modify: `web/style.css` (the block of 5.6 at the end; no new token: every colour is a token of today's `:root`)

## 5.1 The model select (`modelOptions`)

Replace the comment above `function modelOptions(value, withAuto)` and the function (from `// every tier with its
rungs from config.json "ladder"` to its closing `}`) with:

```js
// plan 18: the tier groups think / write / read. Each rung of config.json "tiers" that can run now (no `why`)
// sits under its rank's group (opus in write shows under think), then the Claude ladder rungs no tier lists;
// `auto` is a step's "let the rules pick"
const RANK_GROUP = { haiku: "read", sonnet: "write", opus: "think", fable: "think" };
function rungFits(kind, rung, rank) {  // plan 5 decision 11: opencode and cmd never on verify or fix; a cheap model on read and write kinds
  const h = rung.includes(":") ? rung.split(":")[0] : "claude";
  if ((h !== "opencode" && h !== "cmd") || !kind) return true;
  return rank === "opus" || ["read", "write"].includes((cfg.kinds_tier || {})[kind]);
}
function modelOptions(value, withAuto, kind = "") {
  const opt = (v) => `<option value="${esc(v)}"${v === value ? " selected" : ""}>${esc(modelText(v))}</option>`;
  const seen = new Set(), groups = { think: [], write: [], read: [] };
  for (const tier of ["think", "write", "read"]) {
    for (const x of (cfg.tiers || {})[tier] || []) {
      if (x.why || seen.has(x.rung) || !RANK_GROUP[x.rank] || !rungFits(kind, x.rung, x.rank)) continue;
      seen.add(x.rung);
      groups[RANK_GROUP[x.rank]].push(x.rung);
    }
  }
  for (const tier of cfg.models) {
    for (const r of (cfg.ladder && cfg.ladder[tier] && cfg.ladder[tier].length ? cfg.ladder[tier] : [tier])) {
      if (!seen.has(r) && RANK_GROUP[alias(r)]) { seen.add(r); groups[RANK_GROUP[alias(r)]].push(r); }
    }
  }
  return (withAuto ? `<option value=""${seen.has(value) ? "" : " selected"}>auto</option>` : "")
    + Object.entries(groups).filter(([, list]) => list.length)
      .map(([g, list]) => `<optgroup label="${g}">${list.map(opt).join("")}</optgroup>`).join("");
}
```

In the step row (`srow`), the model select passes the row's kind:

```js
    <select data-smodel aria-label="Model">${modelOptions(st.pick || "", true, st.kind)}</select>
```

Every other caller (the Prep card's model select, the Run row) keeps its two arguments: with no kind every usable
rung shows. A rung with a `why` (harness off or not found, or a model models.json lost) is not listed; config.json
keeps it (README 3.8). A pick that is no longer listed shows `auto` selected (the route then refuses or balances it,
README 3.6 step 2). `alias` and `modelText` are today's helpers.

## 5.2 The today strip (`renderTop`)

`web/index.html`, after `<button id="today" ...></button>`:

```html
        <button id="overpace" class="overpace" aria-expanded="false" hidden title="The today breakdown: where the spend went and which models are over their pace"></button>
```

In `renderTop`, replace the `setHtml($("todaymore"), ...)` call (from `setHtml($("todaymore"),` to its closing
`);`) with:

```js
  const fl = sp.fills || { over: [], unknown: [] };  // plan 18: models at or over budget_warn_at of their pace
  $("overpace").hidden = !fl.over.length;
  setHtml($("overpace"), `<span><b class="y">${fl.over.length} ${fl.over.length === 1 ? "model" : "models"} over pace</b> · fills</span><span class="car">&#9662;</span>`);
  setHtml($("todaymore"), `<div class="legend"><span><i class="h"></i>estimated $${money(sp.today)} (list prices)</span>
    ${sp.budget > 0 ? '<span><i class="mk"></i>80 % of limit</span>' : ""}</div>
    <div class="legend"><span>1 cell = $0.50</span>${sp.models.map(([m, f]) => `<span>${esc(m)} ${f < 0.01 ? "&lt;1" : Math.round(f * 100)} %</span>`).join("")}
    ${sp.runs ? `<span>window runs ${sp.runs}</span>` : ""}
    ${snap.writers.map((w) => `<span>2 writers: ${esc(baseName(w.project_dir))}</span>`).join("")}</div>
    ${fl.unknown.length ? `<div class="legend">${fl.unknown.map(([k, n]) => `<span>${esc(k)}: cost unknown, ${n} ${n === 1 ? "run" : "runs"}</span>`).join("")}</div>` : ""}
    ${fl.over.length ? `<div class="fline"><span class="m">fills · ${fl.over.map(([k, sh, w]) => `<b class="y" title="${esc(w)} window">${esc(k)} ${Math.round(sh * 100)}</b>`).join(" · ")} % of pace</span>
      <button class="btn sm go-usage" data-go="usage">Usage &#8250;</button></div>`
      : '<button class="btn sm go-usage" data-go="usage">Usage by day, week, month &#8250;</button>'}`);
```

The first five lines inside the template are today's, unchanged; if an earlier plan changed them, keep its lines and
add only `fl`, the `#overpace` lines and the last four lines.

In the document click handler, add `#overpace` to the `closest(...)` selector (after `#today`; plan 23 Task 6's
`[data-fold]` handling, wherever it put it, stays as it is), and replace the `else if (t.id === "today") { ... }` branch with:

```js
  } else if (t.id === "today" || t.id === "overpace") {  // plan 18: the over-pace line opens the same breakdown
    const open = t.getAttribute("aria-expanded") !== "true";
    $("today").setAttribute("aria-expanded", String(open));
    $("overpace").setAttribute("aria-expanded", String(open));
    $("todaymore").hidden = !open;
```

## 5.3 The Usage page

After `let usageTimer = null;`:

```js
const fillsOpen = new Set();  // plan 18: the model rows opened to their three windows
const WIN = ["day", "week", "month"];
```

In `usageDay`, the families line (`const fams = ...`) gains the day's unknown runs:

```js
  const fams = Object.entries(r.models).filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1])
    .map(([f, c]) => `<span>${esc(f)} ${r.cost ? Math.round(100 * c / r.cost) : 0} %</span>`).join("")
    + Object.entries(r.unknown || {}).map(([k, n]) => `<span>${esc(k)}: cost unknown · ${n} ${n === 1 ? "run" : "runs"}</span>`).join("");
```

Before `function storageLine()`:

```js
// plan 18: Models · share of pace. One row per model key, one bar of 20 cells for the window that binds (ID-6):
// 20 cells = the window's allowance, the outlined cell the pace; orange at or over budget_warn_at
function fillCells(x, over) {
  const used = x.allowance_usd ? Math.min(20, Math.round(20 * x.used_usd / x.allowance_usd)) : 0;
  const mark = x.allowance_usd ? Math.max(0, Math.round(20 * x.pace_usd / x.allowance_usd) - 1) : -1;
  return Array.from({ length: 20 }, (_, k) => [k < used ? (over ? "y" : "f") : "", k === mark ? "mk" : ""].filter(Boolean).join(" "));
}
function sharePct(x) { return x == null ? "&ndash;" : Math.round(x * 100) + " %"; }
function fillWin(f, w) {
  const x = f[w], over = x.share != null && x.share >= usage.warn_at;
  return `<span class="rw"><span>${w}</span><span class="cells">${cellsHtml(fillCells(x, over))}</span><b class="${over ? "y" : ""}">${sharePct(x.share)}</b></span>`;
}
function fillRow(key, f) {
  const via = f.via && f.via.length && f.via.join() !== "claude" ? "via " + f.via.join(", ") : "claude";
  const nm = `<span class="nm" title="${esc(key)}">${esc(key)}<small>${esc(via)}</small></span>`;
  if (f.share == null) {
    const why = f.unknown_runs ? `cost unknown · ${f.unknown_runs} ${f.unknown_runs === 1 ? "run" : "runs"}` : "no allowance";
    return `<div class="mfill na">${nm}<span class="rw"><span></span><span class="cells">${cellsHtml(Array(20).fill(""))}</span><b class="mut">&ndash;</b></span><span class="rest m">${why}</span></div>`;
  }
  const others = WIN.filter((w) => w !== f.binding), open = fillsOpen.has(key);
  const rest = others.map((w) => `${w[0]} ${f[w].share == null ? "&ndash;" : Math.round(f[w].share * 100)}`).join(" · ");
  return `<div class="mfill" data-fill="${esc(key)}" role="button" tabindex="0" aria-expanded="${open}" title="click for the three windows">${nm}${fillWin(f, f.binding)}<span class="rest m" title="the other two windows, share of pace">${rest}</span></div>
    <div class="mfill more"${open ? "" : " hidden"}><span></span>${others.map((w) => fillWin(f, w)).join("")}</div>`;
}
function usageFills() {
  const rows = Object.entries(usage.fills || {}).filter(([, f]) => WIN.some((w) => f[w].allowance_usd) || f.month.used_usd > 0 || f.unknown_runs);
  if (!rows.length) return "";
  rows.sort((a, b) => (b[1].share ?? -1) - (a[1].share ?? -1));
  const margin = Math.round(usage.balance_margin * 100);
  return `<div class="ublk"><div class="hd"><span class="lbl">Models · share of pace</span><span class="m">over pace first</span></div>
    <div class="mfills">${rows.map(([k, f]) => fillRow(k, f)).join("")}</div>
    <div class="legend"><span><i class="f"></i>used</span><span><i class="mk"></i>pace</span><span>20 cells = allowance</span><span><b class="y">orange</b> over pace</span></div>
    ${fold("config", `balance_margin ${usage.balance_margin} · warn_at ${usage.warn_at}`, `<p class="note m">Each step takes the emptiest model of its tier (lowest share of pace), the same one again while the fills are within ${margin} points, so the load spreads from the first step. A model through two CLIs is one fill. Allowances in config.json "allowances".</p>`)}</div>`;
}
// plan 18: Verify FAIL by hour, the evidence for peak_hours: rows per model that wrote the checked step, 24 hours
function usageFails() {
  const rows = Object.entries(usage.fail_hours || {});
  if (!rows.length) return "";
  let top = null;
  for (const [k, r] of rows) {
    const f = r.fails.reduce((a, b) => a + b, 0);
    if (f && (!top || f > top.f)) top = { k, f, h: r.fails.indexOf(Math.max(...r.fails)) };
  }
  const info = (top ? `${esc(top.k)} most FAIL at ${two(top.h)}:00` : "no FAIL") + " · last 30 days";
  const head = "<span></span>" + Array.from({ length: 24 }, (_, h) => `<span class="hr">${h % 6 === 0 ? two(h) : ""}</span>`).join("");
  const body = rows.map(([k, r]) => `<span class="rn" title="via ${esc(r.via.join(", "))}">${esc(k)}</span>` + r.runs.map((n, h) =>
    `<span class="hc${r.fails[h] ? " l" + Math.min(r.fails[h], 4) : ""}" title="${two(h)}:00 ${esc(k)}: ${n ? `${r.fails[h]} of ${n} FAIL` : "no verify"}"></span>`).join("")).join("");
  return `<div class="ublk">${fold("Verify FAIL by hour", info, `<div class="heat">${head}${body}</div>
    <div class="legend"><span><i></i>no FAIL</span><span><i class="hl1"></i>1</span><span><i class="hl4"></i>4 or more</span><span>rows: the model that wrote the checked step</span></div>
    <p class="note m">Evidence for peak_hours (off): counted over the verify verdicts of the tasks kept.</p>`)}</div>`;
}
```

In `renderUsage`, the page and its footer:

```js
  setHtml($("uscroll"), usageHead() + usageFills() + usageCalendar() + usageDay() + usageChart() + usageFails() + storageLine()
    + `<p class="ufoot">Estimated from the transcripts at the list prices in config.json, fast mode 2x; other harnesses' usage x
       their price row in "prices", and runs without usage or without a price row count as unknown, never as zero. Kept from ${esc(since)}:
       Claude Code deletes transcripts after 30 days, so the service keeps each closed day in usage-days.json.</p>`);
```

The `#uscroll` click handler: add `[data-fill]` to its `closest(...)` selector and, as its first branch:

```js
  if (t.dataset.fill) { if (!fillsOpen.delete(t.dataset.fill)) fillsOpen.add(t.dataset.fill); }  // plan 18: the three windows
  else if (t.dataset.day) uPicked = t.dataset.day;
```

(the `if (t.dataset.day)` line it replaces becomes the `else if`; the rest of the handler is unchanged and ends in
`renderUsage()` as today).

## 5.4 What the page shows (from the mock and the interface doc 9)

- Rows: every key of `usage.fills` with an allowance, spend this month or unknown runs; over pace first by share,
  rows without a share last. Closed row: the key with `via codex` (or `claude`) under it, the binding window's word,
  20 cells (allowance = 20 cells, the outlined cell the pace, filled cells orange at or over `warn_at`), the share,
  then the other two windows as `w 44 · m 31`. Open row (click): the three windows as bars.
- A key without a share: dotted cells, `-`, and `no allowance` or `cost unknown · n runs` (D3 a).
- The `config` fold at the block's end: `balance_margin 0.1 · warn_at 0.8`, one paragraph on the spread.
- Verify FAIL by hour: a fold, closed line `sonnet most FAIL at 15:00 · last 30 days` (or `no FAIL`); rows per model
  key that wrote the checked step, 24 hour cells shaded by FAIL count (1 to 4 or more), hour labels every 6 hours.
- Today strip: `#overpace` shows only while a model is at or over `warn_at`; it opens `#todaymore` like `#today`.

## 5.5 Plan 26's Tiers tab

The Models page (plan 26) edits `tiers` and `allowances`; this task only reads them. `cfg.tiers` and
`cfg.kinds_tier` are the `/api/config` keys plan 26 reuses.

## 5.6 `web/style.css`

At the end of the file (after plan 23's and plan 24's blocks), from the mock's CSS (lines 155 to 160, 410 to 430),
with `[hidden]` guards, the heat legend swatches and a 360 px step:

```css
/* plan 18: the today strip's over-pace line and fills line (mock listHtml) */
.overpace { display: flex; justify-content: space-between; gap: 8px; align-items: center; width: 100%; padding: 4px 12px; border: 0; border-bottom: 1px solid var(--line); background: transparent; color: var(--mut); font: 11px var(--mono); cursor: pointer; text-align: left; }
.overpace[hidden] { display: none; }
.overpace b { font-weight: 400; } .overpace b.y { color: var(--you); }
.overpace .car { font-size: 9px; }
.overpace[aria-expanded="true"] .car { display: inline-block; transform: rotate(180deg); }
.fline { display: flex; justify-content: space-between; gap: 8px; align-items: center; color: var(--mut); min-width: 0; }
.fline .m { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fline b { font-weight: 400; } .fline b.y { color: var(--you); }
/* plan 18: Usage, Models share of pace (mock usageHtml .mfill) and Verify FAIL by hour (.heat) */
.mfills { display: grid; min-width: 0; }
.mfill { display: grid; grid-template-columns: minmax(0, 112px) minmax(0, 1fr) auto; gap: 2px 10px; align-items: center; padding: 6px 0; border-top: 1px solid var(--line); cursor: pointer; }
.mfill:first-of-type { border-top: 0; }
.mfill[hidden] { display: none; }
.mfill.na { cursor: default; }
.mfill.more { border-top: 0; padding-top: 0; cursor: default; grid-template-columns: minmax(0, 112px) minmax(0, 1fr); }
.mfill.more .rw { grid-column: 2; }
.mfill .rest { font-size: 10.5px; color: var(--mut); text-align: right; white-space: nowrap; }
.mfill .nm { font: 12px var(--mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; align-self: start; padding-top: 1px; }
.mfill .nm small { display: block; color: var(--mut); font-size: 10.5px; white-space: normal; }
.mfill .rw { display: grid; grid-template-columns: 32px minmax(0, 1fr) 44px; gap: 6px; align-items: center; font: 10.5px var(--mono); color: var(--mut); min-width: 0; }
.mfill .rw .cells { grid-template-columns: repeat(20, minmax(0, 1fr)); }
.mfill .rw .cells i { aspect-ratio: auto; height: 6px; }
.mfill .rw b { font-weight: 400; text-align: right; color: var(--ink); }
.mfill .rw b.y { color: var(--you); } .mfill .rw b.mut { color: var(--mut); }
.mfill.na .rw .cells i { background: repeating-linear-gradient(0deg, transparent 0 2px, color-mix(in srgb, var(--off) 70%, transparent) 2px 3px); }
.heat { display: grid; grid-template-columns: 124px repeat(24, minmax(0, 1fr)); gap: 1px; align-items: center; }
.heat .rn { font: 11px var(--mono); color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 6px; }
.heat .hc { height: 14px; background: var(--off); border-radius: 1px; }
.heat .hc.l1, .legend i.hl1 { background: color-mix(in srgb, var(--bad) 22%, var(--off)); }
.heat .hc.l2 { background: color-mix(in srgb, var(--bad) 48%, var(--off)); }
.heat .hc.l3 { background: color-mix(in srgb, var(--bad) 74%, var(--off)); }
.heat .hc.l4, .legend i.hl4 { background: var(--bad); }
.heat .hr { font: 9.5px var(--mono); color: var(--mut); text-align: center; }
.ublk .note { font-size: 11px; }
@media (max-width: 360px) {
  .mfill, .mfill.more { grid-template-columns: minmax(0, 84px) minmax(0, 1fr); }
  .mfill .rest { grid-column: 2; text-align: left; }
  .heat { grid-template-columns: 84px repeat(24, minmax(0, 1fr)); }
}
```

## 5.7 Steps

1. The `app.js`, `index.html` and `style.css` edits in the order 5.1 to 5.6.
2. `node --check web/app.js`; the full suite (no Python change: the count of Task 4).
3. Headless Edge (or Chromium) at 400 and 340 px on `py -m console --serve` with `CC_CONSOLE_HOME` pointed at a
   scratch folder holding a usage-days.json of 3.5 with two days of `opus` spend, one `other` run of
   `gpt-6.1-sol` priced and one unknown, `allowances` for `opus` and `gpt-6.1-sol` in config.json: the today strip
   shows `1 model over pace · fills` when `opus` is over; it opens the breakdown with the fills line and
   the line `gpt-6.1-sol: cost unknown, 1 run`; the Usage page shows the rows (one open, one closed, one dotted), the config
   fold and the heatmap fold; the Prep card's model select shows the three groups and no codex rung while codex is
   off; no console error, no horizontal overflow at 340 px.
4. Commit: `plan 18 task 5: the window shows fills, over pace and the tier groups (N tests OK)`.

## 5.8 Drift guards

- The window never computes a share: it draws `usage.fills` and `snap.spend.fills` as the service sent them.
- Orange means at or over `warn_at` (`.y`); nothing in this task uses red for a fill (red is a FAIL's colour, the
  heatmap's).
- No emoji, no em-dash in any text; `&#9662;` and `&#8250;` are the mock's carets.
