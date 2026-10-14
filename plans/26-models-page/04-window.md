# Task 4: The window: the Models and tuning page

> Contract: [README.md](README.md) 3.4 (what `/api/config` carries and what the Save answers). Design: interface doc
> 9b and 4 (the Settings band). Mock: `design/rework/locked/cells-board.html`, `modelsHtml` (the three tabs, the
> card heads with `?`, the rows `krow`, `rrow`, `tf`, the levers row `msave`) and its CSS (lines 605 to 651), the
> Settings band's link (line 1327). Depends on Task 3. Decisions D1 (`modelChanges`), D2 (`allowanceFold`).
> Run in a scratch copy on 2026-10-14 (plan 18 applied; plans 5, 23, 24 not placed): `node --check web/app.js` OK;
> the three tabs rendered in node over that copy's real `/api/config` answer, with a codex pin shown
> `pinned model hidden`, `opus · hard only` in write, the `n hidden` line, `Turns on design`, a value out of range
> (`between 1 and 12 (default 6)`), the changes and `n edited` counts (1, 1, 2). No browser on that box: the headless
> check (4.6 step 3) is the executor's.
> Lands on: plan 18 Task 5 (`modelOptions`, `rungFits`, `RANK_GROUP`: called, unchanged), plan 23 Task 6 (`fold` and
> its `[data-fold]` click branch: called, unchanged; the Settings band's Window runs card), plan 5 Task 6 (the
> Settings band and its Harnesses card: the link goes on the band's label; `cfg.harnesses` gives each harness's
> `on`, `found` and models.json models for `+ rung`), plan 24 4.4 (the `Turns on design` row is here), plan 25 (adds
> the Board page next to this one in `showPage` and `go`).

**Files**
- Modify: `web/index.html` (the `models` page section, before `<div id="utip"`)
- Modify: `web/app.js` (the Models page block before `function storageLine()`; `showPage`; `go`; the Escape branch;
  the Settings band's label)
- Modify: `web/style.css` (4.5, at the end)

## 4.1 `web/index.html`

Before `<div id="utip" class="utip" hidden></div>`:

```html
    <section data-page="models" hidden>
      <div class="top">
        <button class="rb" data-go="list" title="Back to the list (Esc)" aria-label="Back">&#8592;</button>
        <span class="crumb m">Models and tuning</span>
        <span class="sp drag-region" title="Drag to move; double-click to fold"></span>
        <span data-winbtns></span>
      </div>
      <div id="mtabs" class="tabs" role="tablist"></div>
      <div id="mscroll" class="scroll mp"></div>
      <div id="mbar" class="levers"></div>
    </section>
```

## 4.2 The Settings band's link

The Settings band (plan 5 Task 6's Harnesses card, plan 23 Task 6's Window runs card) opens with its `Settings`
label. That label becomes a row with the link, as the mock's line 1327:

```html
<span class="lbl row">Settings<button class="link" data-go="models" title="Which model does each kind of step, the tiers' rungs, and the tuning numbers">Models and tuning &#8250;</button></span>
```

If the band has no label element (the cards start the block), add this one as its first child. The document click
handler already routes `[data-go]` to `go`.

## 4.3 `showPage`, `go`, Escape

In `showPage`, after the `usage` line:

```js
  if (name === "models") { $("mscroll").scrollTop = 0; loadModels(); }  // plan 26: config.json as it is now
```

In `go`, after `if (name === "usage") showPage("usage");`:

```js
  if (name === "models") showPage("models");  // plan 26: the Settings band's Models and tuning link
```

In the keydown handler's Escape branch, after `else if (page === "usage") showPage("list");`:

```js
    else if (page === "models" && !inField && !Object.keys(modelChanges()).length) showPage("list");  // edits stay until Save or Discard
```

(`inField` is declared just above the Escape branch today; if it moved below, declare the check's own
`["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)`.)

## 4.4 The page (`web/app.js`, before `function storageLine()`)

```js
// -- Models and tuning page (plan 26, interface 9b) ----------------------------------------
// The page edits a working copy of what /api/config carries (kind_pins, tiers, tuning); Save posts the changed keys
// to /api/config/models, the service checks them, writes config.json and reloads them: nothing is rebuilt.
let mtab = "kinds";        // kinds | tiers | tuning
let medit = null;          // the working copy: {values: {key: value}, kinds: {kind: {rung, effort}}, tiers: {tier: [{rung, effort}]}}
let mmsg = "";             // the last Save's refusal, shown in the levers row
let mbusy = false;         // a Save is on its way
const mqOpen = new Set();  // the cards whose ? line is open
const PASSES = [["prep_model", "Prep", "enhances the prompt, plans the steps"], ["brief_model", "Handoff pass", "compacts a step's handoff"],
  ["review_model", "Rules review", "read only"], ["default_model", "Run default", "the composer's Run"]];
const TUNE = {  // key -> [label, unit word, scale from the config value to the shown one]; the service sends value, default, range
  task_max_steps: ["Steps per task", "", 1], task_step_budget_usd: ["Spend per step", "$", 1],
  step_timeout_s: ["Step timeout", "s", 1], design_max_turns: ["Turns on design", "", 1],
  read_max_turns: ["Turns on read kinds", "", 1], plan_max_kb: ["Plan size at most", "KB", 1],
  plan_max_parts: ["Sub-plans at most", "", 1], plan_hold: ["Hold each plan for me", "", 1],
  replan_auto: ["Replan without asking", "", 1], brief_max_words: ["Handoff words", "w", 1],
  brief_timeout_s: ["Pass timeout", "s", 1], balance_margin: ["Spread margin", "points", 100],
  cache_bonus: ["Warm cache bonus", "points", 100], budget_warn_at: ["Over pace at", "% of pace", 100],
  daily_budget_usd: ["Daily budget", "$", 1], gauge_yellow_tokens: ["Yellow from", "K", 0.001],
  gauge_red_tokens: ["Red from", "K", 0.001],
};
const MGROUP = {  // Tuning cards: [name, the one fact, the ? sentence]
  steps: ["Steps", "limits per step and task", "Limits for one step and one task: how many steps, how much one step may spend, how long it may run and how many turns it may take."],
  plan: ["Plan", "the design step's plan", "The plan a design step writes: its size, how many sub-plans it may split into, and whether you confirm it and its replans."],
  handoff: ["Handoff", "between steps", "What passes between steps: the word limit of a handoff and how long the pass that compacts it may take."],
  balancing: ["Balancing", "spread across models", "How work is spread across models: each step takes the least-used model of its tier; the margin lets the same model run again while usage is close; over pace marks a model that is ahead of its allowance."],
  gauge: ["Context gauge", "the cells' colours", "When the context cells turn yellow and red. Red is also where auto hand off starts."],
};
const KCARD = {  // Kinds and Tiers cards per tier: [name, the one fact on Kinds, the ? sentence on Kinds, on Tiers]
  read: ["Read", "look, search, small edits", "Kinds that look things up or make small changes. Their models come from the read tier, the cheap and fast ones.",
    "The cheap, fast models, for looking things up, small edits and tests."],
  write: ["Write", "code and prose", "Kinds that write code or prose, such as implementing a feature or fixing a bug. Their models come from the write tier.",
    "The everyday coding models, for writing code and prose. A model ranked above this tier runs only on steps Prep judges hard."],
  think: ["Think", "plans and decisions", "Kinds that plan and decide. Their models come from the think tier, the strongest ones.",
    "The strongest models, for design and hard decisions. Fable, ranked above opus, runs only on design steps Prep judges hard."],
};
const RANKS = ["haiku", "sonnet", "opus", "fable"];
const clone = (x) => JSON.parse(JSON.stringify(x));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

async function loadModels() {
  try { cfg = await api("/api/config"); mmsg = ""; } catch (e) { mmsg = e.message; }
  resetModels();
  renderModels();
}
function resetModels() {
  if (!cfg || !cfg.tuning) { medit = null; return; }
  medit = { values: Object.fromEntries(Object.entries(cfg.tuning).map(([k, t]) => [k, clone(t.value)])),
    kinds: clone(cfg.kind_pins || {}),
    tiers: Object.fromEntries(Object.entries(cfg.tiers || {}).map(([t, rows]) => [t, rows.map((r) => ({ rung: r.rung, effort: r.effort }))])) };
}
function savedTiers() { return Object.fromEntries(Object.entries(cfg.tiers || {}).map(([t, rows]) => [t, rows.map((r) => ({ rung: r.rung, effort: r.effort }))])); }
function pinOf(pins, k) { const p = pins[k] || {}; return { rung: p.rung || "auto", effort: p.effort || "auto" }; }
function cleanPins(pins) {  // a kind on auto and auto is the code's rule: nothing to keep (the service drops it too)
  return Object.fromEntries(Object.entries(pins).map(([k, p]) => [k, pinOf(pins, k)]).filter(([, p]) => p.rung !== "auto" || p.effort !== "auto"));
}
function modelChanges() {  // the keys a Save would post, with their values (D1 a: only what differs from the page's load)
  if (!medit) return {};
  const out = {};
  for (const [k, t] of Object.entries(cfg.tuning)) if (!same(medit.values[k], t.value)) out[k] = medit.values[k];
  if (!same(cleanPins(medit.kinds), cleanPins(cfg.kind_pins || {}))) out.kinds = cleanPins(medit.kinds);
  if (!same(medit.tiers, savedTiers())) out.tiers = medit.tiers;
  return out;
}
function tabEdits(tab) {
  const ch = modelChanges(), passes = PASSES.map(([k]) => k);
  if (tab === "kinds") {
    const a = cleanPins(medit.kinds), b = cleanPins(cfg.kind_pins || {});
    return new Set([...Object.keys(a), ...Object.keys(b)].filter((k) => !same(a[k], b[k]))).size;
  }
  if (tab === "tiers") return Object.keys(medit.tiers).filter((t) => !same(medit.tiers[t], savedTiers()[t])).length + passes.filter((k) => k in ch).length;
  return Object.keys(ch).filter((k) => cfg.tuning[k] && !passes.includes(k)).length;
}
function rankOf(rung) {  // what /api/config says, else models.json through the Harnesses card (plan 5), else a Claude alias
  for (const rows of Object.values(cfg.tiers || {})) { const x = rows.find((r) => r.rung === rung); if (x && x.rank) return x.rank; }
  if (rung.includes(":")) { const [h, ...m] = rung.split(":"); return (((cfg.harnesses || {})[h] || {}).models || {})[m.join(":")] || ""; }
  const a = alias(rung);
  return RANKS.includes(a) ? a : "";
}
function whyHidden(rung) {
  for (const rows of Object.values(cfg.tiers || {})) { const x = rows.find((r) => r.rung === rung); if (x) return x.why; }
  return "";
}
function cardHead(id, name, fact, help) {
  const open = mqOpen.has(id);
  return `<div class="ph"><span class="nm">${esc(name)}</span><button class="q" data-q="${esc(id)}" aria-expanded="${open}" aria-label="What is ${esc(name)}?" title="${esc(help)}">?</button><span class="m">${fact}</span></div><p class="qh"${open ? "" : " hidden"}>${esc(help)}</p>`;
}
function effSel(value, label, attrs, start = "") {
  const auto = value === "auto";
  return `<span class="pick e${auto ? " auto" : ""}"${auto && start ? ` title="auto: starts at ${esc(start)}; Prep and the router may raise it"` : ""}><select ${attrs} aria-label="${esc(label)} effort">${["auto", ...cfg.efforts].map((e) => `<option${e === value ? " selected" : ""}>${e}</option>`).join("")}</select></span>`;
}

// Kinds: one row per kind, in cards by tier; verify and fix in a Checks card, set by the rule
function kindRow(k) {
  const tier = cfg.kinds_tier[k], rule = (cfg.kind_rules || {})[k] || {}, p = pinOf(medit.kinds, k), was = pinOf(cfg.kind_pins || {}, k);
  let opts = modelOptions(p.rung === "auto" ? "" : p.rung, false, k);
  const listed = p.rung === "auto" || opts.includes(`value="${esc(p.rung)}"`);
  if (!listed) opts = `<option value="${esc(p.rung)}" selected>${esc(modelText(p.rung))} (hidden)</option>` + opts;
  const turns = k === "design" ? medit.values.design_max_turns : ["scout", "search"].includes(k) ? medit.values.read_max_turns : 0;
  const sub = [rule.tools ? "tools " + rule.tools.replaceAll(",", ", ") : "default tools", turns ? turns + " turns" : ""].filter(Boolean).join(" · ");
  const ed = !same(p, was), why = listed ? "" : whyHidden(p.rung);
  return `<div class="krow${ed ? " ed" : ""}"><span class="nm">${esc(k)}</span>
    <span class="pick r${p.rung === "auto" ? " auto" : ""}"><select data-mkind="${esc(k)}" data-mf="rung" aria-label="${esc(k)} model"><option value="auto"${p.rung === "auto" ? " selected" : ""}>auto · ${tier}</option>${opts}</select></span>
    ${effSel(p.effort, k, `data-mkind="${esc(k)}" data-mf="effort"`, rule.effort)}
    <span class="sub">${listed ? esc(sub) : `<span class="r">pinned model hidden${why ? " · " + esc(why) : ""}</span>`}${p.effort !== "auto" ? " · effort pinned" : ""}${ed ? ` · <button class="rs" data-mreset="kind:${esc(k)}">reset</button>` : ""}</span></div>`;
}
function kindsTab() {
  const byTier = { read: [], write: [], think: [] };
  for (const k of cfg.kinds) if (byTier[cfg.kinds_tier[k]]) byTier[cfg.kinds_tier[k]].push(k);
  const fixed = (k, why, sub) => `<div class="krow fixed"><span class="nm">${k}</span><span class="lock">${why}</span><span class="sub">${sub}</span></div>`;
  return `<p class="hint">Which model and effort each kind of step takes. Auto lets Prep and the router decide (the tier's emptiest model; the effort from the kind's start, raised when Prep judges the step hard); a picked model or effort pins it as this kind's default. The Prep card can still change one step.</p>
    ${["read", "write", "think"].map((t) => `<div class="pcard">${cardHead("k" + t, KCARD[t][0], KCARD[t][1], KCARD[t][2] + " Kinds: " + byTier[t].join(", ") + ".")}${byTier[t].map(kindRow).join("")}</div>`).join("")}
    <div class="pcard">${cardHead("kchecks", "Checks", "set by the rule, not here", "Verify and fix are set by a rule: verify runs one rank above the model that wrote the step; fix takes the failed step's tier. They cannot be changed here.")}
      ${fixed("verify", "one rank above", "the rung that wrote the step; never opencode or cmd")}${fixed("fix", "the failed step's tier", "after a FAIL; never opencode or cmd")}</div>`;
}

// Tiers: each tier's rungs in order (drag, or Alt+Up / Alt+Down on a row); hidden rungs keep their place
function addOptions(tier) {
  const have = new Set(medit.tiers[tier].map((r) => r.rung)), out = [];
  for (const t of cfg.models) for (const r of ((cfg.ladder || {})[t] || [t])) out.push(r);
  for (const [h, x] of Object.entries(cfg.harnesses || {})) {
    if (h === "claude" || !x.on || !x.found) continue;
    for (const m of Object.keys(x.models || {})) out.push(`${h}:${m}`);
  }
  return [...new Set(out)].filter((r) => !have.has(r) && rankOf(r)
    && !(tier === "think" && /^(opencode|cmd):/.test(r) && rankOf(r) !== "opus"));
}
function tierCard(tier) {
  const rows = medit.tiers[tier] || [], base = { read: "haiku", write: "sonnet", think: "opus" }[tier];
  let n = 0;
  const hidden = rows.filter((r) => whyHidden(r.rung));
  const body = rows.map((r, i) => {
    if (whyHidden(r.rung)) return "";
    n += 1;
    const rank = rankOf(r.rung), hard = rank && RANKS.indexOf(rank) > RANKS.indexOf(base);
    const [h, m] = r.rung.includes(":") ? [r.rung.split(":")[0], r.rung.slice(r.rung.indexOf(":") + 1)] : ["claude", r.rung];
    return `<div class="rrow" draggable="true" tabindex="0" data-mrow="${tier}:${i}"${hard ? ` title="ranks above the ${tier} tier: used only when Prep judges the step hard"` : ""}>
      <span class="gr" aria-hidden="true">&#8942;&#8942;</span><span class="o">${n}</span><span class="nm"><span class="h">${esc(h)} · </span>${esc(m)}${hard ? '<span class="h"> · hard only</span>' : ""}</span>
      ${effSel(r.effort, m, `data-meff="${tier}:${i}"`)}<button class="x" data-mrm="${tier}:${i}" aria-label="Remove ${esc(m)}" title="Remove from ${tier}">&#10005;</button></div>`;
  }).join("");
  const hid = hidden.length ? `<div class="rhid" title="Turn the CLI on in Settings and its models come back">${hidden.length} hidden · ${esc(whyHidden(hidden[0].rung))}</div>` : "";
  const add = addOptions(tier);
  return `<div class="pcard">${cardHead("t" + tier, KCARD[tier][0], `${n} ${n === 1 ? "rung" : "rungs"}`, KCARD[tier][3])}${body}${hid}
    <div class="radd"><span class="pick auto"><select data-madd="${tier}" aria-label="Add a rung to ${tier}"><option value="">+ rung</option>${add.map((r) => `<option value="${esc(r)}">${esc(modelText(r))}</option>`).join("")}</select></span><span class="m">${tier === "think" ? "no cheap models" : "cheap models allowed"}</span></div></div>`;
}
function tiersTab() {
  const claude = [];
  for (const t of cfg.models) for (const r of ((cfg.ladder || {})[t] || [t])) claude.push(r);
  const pass = ([k, name, sub]) => {
    const v = medit.values[k], ed = !same(v, cfg.tuning[k].value);
    const opts = k === "default_model" ? modelOptions(v, false)
      : [...new Set(claude)].map((r) => `<option value="${esc(r)}"${r === v ? " selected" : ""}>${esc(modelText(r))}</option>`).join("");
    return `<div class="krow${ed ? " ed" : ""}"><span class="nm">${name}</span><span class="pick r"><select data-mval="${k}" aria-label="${name} model">${opts}</select></span><span></span>
      <span class="sub">${k} · ${esc(sub)}${ed ? ` · <button class="rs" data-mreset="val:${k}">reset</button>` : ""}</span></div>`;
  };
  return `<p class="hint">Each step takes the emptiest model of its tier, so the load spreads from the first step; the order breaks ties and is used while usage is unknown. Drag to reorder. Models of a CLI that is off or not found are hidden; one line says how many. The models come from models.json (Settings, Harnesses, Open).</p>
    ${["think", "write", "read"].map(tierCard).join("")}
    <div class="pcard">${cardHead("tpasses", "Console's own passes", "not steps", "Jobs the console runs for itself, not task steps: Prep enhances your prompt and plans the steps, the handoff pass compacts what a step hands to the next, the rules review checks CLAUDE.md, Run default is the composer's plain Run.")}${PASSES.map(pass).join("")}</div>`;
}

// Tuning: the numbers; a value off its default has the blue edge and a reset; out of range turns red and blocks Save
function shown(k, v) { const s = TUNE[k] ? TUNE[k][2] : 1; return v == null ? "" : String(Math.round(v * s * 1000) / 1000); }
function tuneBad(k) {
  const t = cfg.tuning[k], v = medit.values[k];
  if (t.unit === "bool" || t.unit === "rung" || k === "allowances") return "";
  const whole = ["steps", "s", "turns", "kb", "parts", "words", "tokens"].includes(t.unit);
  if (typeof v !== "number" || !isFinite(v) || v < t.min || v > t.max || (whole && !Number.isInteger(v)))
    return `${whole ? "a whole number " : ""}between ${shown(k, t.min)} and ${shown(k, t.max)} (default ${shown(k, t.default)})`;
  if (k === "gauge_yellow_tokens" && v >= medit.values.gauge_red_tokens) return "yellow must start under red";
  return "";
}
function tuneRow(k) {
  const t = cfg.tuning[k], [label, unit] = TUNE[k], v = medit.values[k], ed = !same(v, t.default), bad = tuneBad(k);
  const reset = ed ? ` · <button class="rs" data-mreset="def:${k}">reset</button>` : "";
  if (t.unit === "bool") {
    return `<div class="tf${ed ? " ed" : ""}"><span class="nm">${label}</span><span class="v"><button class="sw${v ? " on" : ""}" role="switch" aria-checked="${!!v}" data-mbool="${k}" title="${v ? "Turn off" : "Turn on"}">${v ? "on" : "off"}</button></span><span class="sub">${k} · default ${t.default ? "on" : "off"}${reset}</span></div>`;
  }
  const pre = unit === "$" ? "$" : "", post = unit === "$" ? "" : unit;
  return `<div class="tf${ed ? " ed" : ""}${bad ? " bad" : ""}"><span class="nm">${label}</span><span class="v">${pre}<input inputmode="decimal" data-mnum="${k}" aria-label="${esc(label)}" value="${esc(shown(k, v))}">${post}</span>
    <span class="sub">${bad ? esc(bad) : `${k} · default ${shown(k, t.default)}${reset}`}</span></div>`;
}
function allowanceFold() {  // D2 a: a row per usable tier rung's model key and per key already set; empty = none
  const al = medit.values.allowances || {}, keys = [...new Set([...Object.values(cfg.tiers || {}).flat().filter((r) => !r.why).map((r) => r.key), ...Object.keys(al)])];
  const set = Object.keys(al).filter((k) => Object.keys(al[k] || {}).length).length;
  const rows = keys.map((key) => `<div class="tf al"><span class="nm">${esc(key)}</span><span class="v">${["day_usd", "week_usd", "month_usd"].map((w) =>
    `<input inputmode="decimal" data-mal="${esc(key)}:${w}" aria-label="${esc(key)} ${w.split("_")[0]} USD" placeholder="${w[0]}" value="${(al[key] || {})[w] ?? ""}">`).join("")}</span><span class="sub">day · week · month, USD; empty: no allowance</span></div>`).join("");
  return fold("Allowances", `${set} of ${keys.length} models · day / week / month`, rows, { cls: "alw" });
}
function tuningTab() {
  const groups = {};
  for (const [k, t] of Object.entries(cfg.tuning)) if (TUNE[k]) (groups[t.group] = groups[t.group] || []).push(k);
  return `<p class="hint">Numbers the service reads at each step. Saved to config.json; a hand edit of the file shows here after Reload.</p>
    ${Object.entries(MGROUP).filter(([g]) => groups[g]).map(([g, [name, fact, help]]) => `<div class="pcard">${cardHead("g" + g, name, fact, help)}${groups[g].map(tuneRow).join("")}${g === "balancing" ? allowanceFold() : ""}</div>`).join("")}`;
}

function renderModels() {
  if (page !== "models") return;
  if (!medit) { setHtml($("mscroll"), `<p class="hint pad">${esc(mmsg || "Loading...")}</p>`); setHtml($("mtabs"), ""); setHtml($("mbar"), ""); return; }
  const tabs = [["kinds", "Kinds"], ["tiers", "Tiers"], ["tuning", "Tuning"]];
  setHtml($("mtabs"), tabs.map(([k, l]) => { const n = tabEdits(k); return `<button role="tab" data-mtab="${k}" aria-selected="${mtab === k}">${l}${n ? ` <span class="n">${n} edited</span>` : ""}</button>`; }).join(""));
  setHtml($("mscroll"), `<div class="pane">${mtab === "tiers" ? tiersTab() : mtab === "tuning" ? tuningTab() : kindsTab()}</div>`);
  const n = Object.keys(modelChanges()).length, bad = Object.keys(cfg.tuning).some((k) => tuneBad(k));
  const say = mmsg ? `<span class="r">${esc(mmsg)}</span>` : bad ? '<span class="r">a value is out of range</span>'
    : n ? `<b>${n} ${n === 1 ? "change" : "changes"}</b> · used from the next step` : "config.json · as saved";
  setHtml($("mbar"), `<div class="msave"><span class="m" title="Save writes config.json; the service reloads it and uses it from the next step">${say}</span>
    ${n ? `<button class="btn" data-mact="discard">Discard</button><button class="btn go" data-mact="save"${bad || mbusy ? " disabled" : ""}>${mbusy ? "..." : "Save"}</button>`
    : '<button class="btn" data-mact="reload" title="Read config.json again">Reload</button>'}</div>`);
}

async function saveModels() {
  const changes = modelChanges();
  if (!Object.keys(changes).length) return;
  mbusy = true; mmsg = ""; renderModels();
  try { cfg = await api("/api/config/models", { changes }); resetModels(); } catch (e) { mmsg = e.message; }
  mbusy = false;
  renderModels();
}
function moveRung(tier, from, to) {
  const rows = medit.tiers[tier];
  if (to < 0 || to >= rows.length || from === to) return;
  const [r] = rows.splice(from, 1);
  rows.splice(to, 0, r);
  renderModels();
}
let mdrag = null;  // "tier:index" of the row being dragged
$("mscroll").addEventListener("dragstart", (e) => { const r = e.target.closest("[data-mrow]"); if (r) { mdrag = r.dataset.mrow; e.dataTransfer.effectAllowed = "move"; } });
$("mscroll").addEventListener("dragover", (e) => { const r = e.target.closest("[data-mrow]"); if (r && mdrag && r.dataset.mrow.split(":")[0] === mdrag.split(":")[0]) e.preventDefault(); });
$("mscroll").addEventListener("drop", (e) => {
  const r = e.target.closest("[data-mrow]");
  if (!r || !mdrag) return;
  e.preventDefault();
  const [tier, from] = mdrag.split(":"), to = Number(r.dataset.mrow.split(":")[1]);
  mdrag = null;
  if (r.dataset.mrow.split(":")[0] === tier) moveRung(tier, Number(from), to);
});
$("mscroll").addEventListener("keydown", (e) => {
  const r = e.target.closest("[data-mrow]");
  if (!r || !e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
  e.preventDefault();
  const [tier, i] = r.dataset.mrow.split(":"), rows = medit.tiers[tier];
  let j = Number(i);
  do { j += e.key === "ArrowUp" ? -1 : 1; } while (j >= 0 && j < rows.length && whyHidden(rows[j].rung));  // over hidden rungs
  moveRung(tier, Number(i), j);
  const moved = $("mscroll").querySelector(`[data-mrow="${tier}:${j}"]`);
  if (moved) moved.focus();
});
$("mscroll").addEventListener("change", (e) => {
  const t = e.target;
  if (t.dataset.mkind) { const p = pinOf(medit.kinds, t.dataset.mkind); p[t.dataset.mf] = t.value; medit.kinds[t.dataset.mkind] = p; }
  else if (t.dataset.meff) { const [tier, i] = t.dataset.meff.split(":"); medit.tiers[tier][Number(i)].effort = t.value; }
  else if (t.dataset.madd) { if (t.value) medit.tiers[t.dataset.madd].push({ rung: t.value, effort: "auto" }); }
  else if (t.dataset.mval) medit.values[t.dataset.mval] = t.value;
  else if (t.dataset.mnum) {
    const k = t.dataset.mnum, n = Number(t.value.trim().replace(",", "."));
    medit.values[k] = t.value.trim() === "" || !isFinite(n) ? NaN : Math.round(n / TUNE[k][2] * 1e6) / 1e6;
  } else if (t.dataset.mal) {
    const [key, w] = t.dataset.mal.split(":"), al = clone(medit.values.allowances || {}), row = al[key] || {};
    if (t.value.trim() === "") delete row[w]; else row[w] = Number(t.value.trim().replace(",", "."));
    if (Object.keys(row).length) al[key] = row; else delete al[key];
    medit.values.allowances = al;
  } else return;
  mmsg = "";
  renderModels();
});
$("mscroll").addEventListener("click", (e) => {
  const t = e.target.closest("[data-q],[data-mreset],[data-mrm],[data-mbool]");
  if (!t) return;
  if (t.dataset.q) { if (!mqOpen.delete(t.dataset.q)) mqOpen.add(t.dataset.q); }
  else if (t.dataset.mrm) { const [tier, i] = t.dataset.mrm.split(":"); medit.tiers[tier].splice(Number(i), 1); }
  else if (t.dataset.mbool) medit.values[t.dataset.mbool] = !medit.values[t.dataset.mbool];
  else {
    const [what, k] = t.dataset.mreset.split(":");
    if (what === "kind") { if (cfg.kind_pins && cfg.kind_pins[k]) medit.kinds[k] = clone(cfg.kind_pins[k]); else delete medit.kinds[k]; }
    else if (what === "val") medit.values[k] = clone(cfg.tuning[k].value);
    else medit.values[k] = clone(cfg.tuning[k].default);
  }
  mmsg = "";
  renderModels();
});
$("mtabs").addEventListener("click", (e) => { const t = e.target.closest("[data-mtab]"); if (t) { mtab = t.dataset.mtab; renderModels(); $("mscroll").scrollTop = 0; } });
$("mbar").addEventListener("click", (e) => {
  const t = e.target.closest("[data-mact]");
  if (!t || t.disabled) return;
  if (t.dataset.mact === "save") saveModels();
  else if (t.dataset.mact === "discard") { resetModels(); mmsg = ""; renderModels(); }
  else loadModels();
});
```

What it shows (interface 9b, the mock):

- Kinds: a card per tier (Read, Write, Think) from `cfg.kinds_tier`, one row per kind: the name over its tools and
  turn cap (`kind_rules`, `design_max_turns`, `read_max_turns`), a rung select (`auto · <tier>`, then the usable
  rungs from plan 18's `modelOptions` for that kind), an effort select (`auto` titled `auto: starts at <effort>`).
  A pin off the saved value has the blue edge and `reset`; a pinned rung that is not offered shows `(hidden)` and
  `pinned model hidden · <reason>` in red. A Checks card holds verify and fix, fixed.
- Tiers: a card per tier (think, write, read): order, `harness · model`, `hard only` when ranked above the tier, the
  effort, remove; drag a row, or Alt+Up / Alt+Down on a focused row; hidden rungs keep their place and one line counts
  them (`1 hidden · codex is off`); `+ rung` lists what can be added (think: no opencode or cmd model below opus).
  The last card: Prep, Handoff pass, Rules review (Claude rungs), Run default (any rung).
- Tuning: a card per group with the rows of `TUNE` (label, field with its unit, `key · default N`, `reset` off the
  default, red with the range when out of it), switches for `plan_hold` and `replan_auto`, and the Allowances fold
  in Balancing (D2 a).
- The levers row: `N changes · used from the next step` with Discard and Save (off while a value is out of range or a
  Save is on its way), `config.json · as saved` with Reload when nothing changed, the refusal in red after a 400.

## 4.5 `web/style.css`

At the end of the file. The first block is the mock's card and compact select: add it only when `grep -n "^\.pcard {"
web/style.css` and `grep -n "^\.pick {" web/style.css` find nothing (an earlier plan may have ported them; then
skip the rules it has).

```css
/* plan 26: the card and the compact select of the mock (lines 262 to 266, 274 to 278), when no earlier plan ported them */
.pcard { display: grid; background: var(--win); border: 1px solid var(--line); border-radius: 8px; min-width: 0; }
.pcard > .ph { display: flex; align-items: center; gap: 10px; min-height: 34px; padding: 0 10px 0 12px; border-bottom: 1px solid var(--line); }
.pcard > .ph .nm { font: 600 12.5px var(--ui); color: var(--ink); }
.pcard > .ph .m { flex: 1; min-width: 0; text-align: right; color: var(--mut); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pcard > .ph .btn.sm { min-height: 24px; }
.pick { position: relative; display: inline-flex; align-items: center; min-width: 0; max-width: 100%; }
.pick select { appearance: none; -webkit-appearance: none; min-width: 0; max-width: 100%; height: 24px; padding: 0 18px 0 7px; border: 1px solid transparent; border-radius: 5px; background: var(--raise); color: var(--ink); font: 11.5px var(--mono); cursor: pointer; text-overflow: ellipsis; }
.pick select:hover { border-color: var(--line); }
.pick::after { content: "▾"; position: absolute; right: 6px; font-size: 9px; color: var(--mut); pointer-events: none; }
.pick.auto select { color: var(--mut); background: transparent; border-color: var(--line); border-style: dashed; }

/* plan 26: the Models and tuning page (mock: modelsHtml and its CSS, 2026-10-14). Tabs Kinds / Tiers / Tuning in the
   Settings card grammar; an edited value carries the blue edge and a reset, a value at its default carries nothing */
.mp .pane { padding: 10px 12px 14px; display: grid; gap: 10px; align-content: start; }
.mp .hint { margin: 0; font: 11.5px/1.45 var(--ui); color: var(--mut); text-wrap: pretty; }
.mp .hint.pad { padding: 12px; }
.pcard > .ph .q { flex: none; width: 16px; height: 16px; margin-left: -4px; padding: 0; border: 1px solid var(--line); border-radius: 50%; background: transparent; color: var(--mut); font: 600 10px/14px var(--ui); cursor: help; }
.pcard > .ph .q:hover, .pcard > .ph .q[aria-expanded="true"] { color: var(--ink); border-color: var(--ink); }
.pcard > .qh { margin: 0; padding: 7px 12px 8px; border-bottom: 1px solid var(--line); background: var(--raise); font: 12px/1.45 var(--ui); color: var(--mut); text-wrap: pretty; }
.pcard > .qh[hidden] { display: none; }
.krow { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 1px 6px; align-items: center; padding: 7px 8px 7px 12px; }
.krow + .krow { border-top: 1px solid var(--line); }
.krow .nm { grid-column: 1; grid-row: 1; font: 500 13px var(--ui); color: var(--ink); }
.krow .pick { grid-row: 1; }
.krow .pick.r { grid-column: 2; } .krow .pick.e { grid-column: 3; }
.krow .pick.r select { max-width: 190px; }
.krow .sub { grid-column: 1 / -1; grid-row: 2; font: 10.5px var(--mono); color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.krow .sub .r { color: var(--bad); }
.krow.fixed .nm { color: var(--mut); }
.krow.fixed .lock { grid-column: 2 / -1; grid-row: 1 / span 2; font: 11px var(--mono); color: var(--mut); text-align: right; }
.ed { box-shadow: inset 2px 0 0 var(--wip); }
.ed .rs, .tf .rs { padding: 0; border: 0; background: transparent; font: inherit; color: var(--wip); cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.rrow { display: grid; grid-template-columns: 14px 16px minmax(0, 1fr) auto 24px; gap: 6px; align-items: center; padding: 6px 6px 6px 10px; }
.rrow + .rrow { border-top: 1px solid var(--line); }
.rrow:focus-visible { outline: 2px solid var(--ink); outline-offset: -2px; }
.rrow .gr { color: var(--mut); font-size: 11px; letter-spacing: -2px; cursor: grab; }
.rrow .o { font: 10.5px var(--mono); color: var(--mut); }
.rrow .nm { font: 12px var(--mono); color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rrow .nm .h { color: var(--mut); }
.rrow .x { width: 24px; height: 24px; border: 0; border-radius: 5px; background: transparent; color: var(--mut); cursor: pointer; font-size: 11px; }
.rrow .x:hover { background: var(--raise); color: var(--ink); }
.rhid { padding: 5px 12px; border-top: 1px solid var(--line); font: 11px var(--mono); color: var(--mut); }
.radd { display: flex; gap: 6px; align-items: center; padding: 6px 10px 8px; border-top: 1px solid var(--line); }
.radd .m { color: var(--mut); font-size: 11px; margin-left: auto; }
.tf { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 1px 10px; align-items: center; padding: 7px 10px 7px 12px; }
.tf + .tf { border-top: 1px solid var(--line); }
.tf .nm { font: 500 13px var(--ui); color: var(--ink); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tf .sub { grid-column: 1; font: 10.5px var(--mono); color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tf .v { grid-column: 2; grid-row: 1 / span 2; display: inline-flex; align-items: center; gap: 5px; font: 11px var(--mono); color: var(--mut); }
.tf .v input { width: 70px; height: 26px; padding: 0 7px; border: 1px solid var(--line); border-radius: 5px; background: var(--raise); color: var(--ink); font: 12px var(--mono); text-align: right; }
.tf .v input:focus-visible { outline: 2px solid var(--ink); outline-offset: 0; }
.tf.bad .v input { border-color: var(--bad); }
.tf.bad .sub { color: var(--bad); }
.tf.al .v input { width: 54px; }
.tf .sw { min-width: 44px; height: 22px; padding: 0 8px; border: 1px solid var(--line); border-radius: 11px; background: var(--off); color: var(--mut); font: 11px var(--mono); cursor: pointer; }
.tf .sw.on { background: color-mix(in srgb, var(--ok) 18%, var(--win)); border-color: color-mix(in srgb, var(--ok) 50%, var(--line)); color: var(--ink); }
.mp .pcard .fold .fh { padding: 0 10px 0 12px; min-height: 32px; align-items: center; }
.msave { display: flex; align-items: center; gap: 8px; min-width: 0; }
.msave .m { flex: 1; min-width: 0; color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msave .m b { color: var(--wip); font-weight: 400; } .msave .m .r { color: var(--bad); }
.pset > .lbl.row { display: flex; justify-content: space-between; align-items: baseline; }
.pset > .lbl.row .link { padding: 0; border: 0; background: transparent; text-transform: none; letter-spacing: 0; font: 11.5px var(--ui); color: var(--ink); }
@media (max-width: 372px) {
  .krow { grid-template-columns: minmax(0, 1fr) auto; }
  .krow .pick.r { grid-column: 1 / -1; grid-row: 3; } .krow .pick.r select { max-width: 100%; }
  .krow .pick.e { grid-column: 2; }
  .tf.al .v input { width: 46px; }
}
```

## 4.6 Steps

1. `index.html`, then the `app.js` edits 4.2 to 4.4, then `style.css`.
2. `node --check web/app.js`; the full suite (no Python change: the count of Task 3).
3. Headless Edge or Chromium at 400 and 340 px on `py -m console --serve` with `CC_CONSOLE_HOME` pointed at a scratch
   folder (its own config.json; never Fred's): open the page from the Settings band; Kinds: pin `code` to effort
   `high`, the tab says `1 edited`, the row has the blue edge and `reset`; Tiers: drag a rung, Alt+Down on another,
   add one with `+ rung`, remove one; Tuning: type 99 in Steps per task (red, `between 1 and 12 (default 6)`, Save
   off), fix it, open Allowances and set one day value; Save: the levers row says `config.json · as saved` and the
   scratch config.json holds exactly the saved keys with every other key as before; Discard after an edit restores
   the row; Reload after a hand edit of the file shows it. No console error, no horizontal overflow at 340 px (the
   kind rows wrap the rung select under the name).
4. Commit: `plan 26 task 4: the Models and tuning page (N tests OK)`.

## 4.7 Drift guards

- The page edits a copy and posts only the changed keys (D1 a); it never writes models.json and never computes a
  route.
- Colours: the blue `--wip` edge for an edited value, red `--bad` for out of range and a hidden pin, nothing orange
  (orange is "needs you").
- No emoji, no em-dash; `&#8250;`, `&#8942;` and `&#10005;` are the mock's glyphs.
