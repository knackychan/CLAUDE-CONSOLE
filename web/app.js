// Claude Console window, Console Cells (BRAINSTORM 7.5): a folded pill with one peek card, or a rail of
// session chips plus one pane (Overview, a session in focus, or the Prep card). Renders /api/stream
// snapshots; the levers, Prep and runs go through the same routes as phases 2-4.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const RESUME_TEXT = "You were interrupted. Check `git diff` first, then finish the task.";
const BUSY = new Set(["running", "quiet", "stall"]);
const PEEK = new Set(["stop", "blocked", "failed", "interrupted"]);  // a new one opens the peek card
const SPEND_CELL = 0.5;   // 1 spend cell = $0.50
const PILL_CHIPS = 9;

let snap = null;
let cfg = null;          // /api/config
let live = false;
let form = "open";       // open | pill
let pane = "overview";   // overview | focus | prep
let openId = null;
let tab = "steps";       // steps | timeline | chat
let card = null;         // the Prep card on screen
let busy = "";           // what the compose box waits for ("" = nothing)
let note = "";           // the compose box's last message (an error stays until Fred types)
let draft = "";
let project = "";        // the compose project (window.json, through /api/draft)
let draftTimer = null;
let leversSig = "";
let askSig = "";
let onTop = true;
let peekKey = "";        // the event the peek card shows
let firstSnap = true;
const seen = new Set();  // peek events already shown, answered or dismissed

// -- helpers ---------------------------------------------------------------------------
function native() { return !!(window.pywebview && window.pywebview.api); }
function money(x) { return Number(x || 0).toFixed(2); }
function spentText(s) { return s.spent == null ? "&ndash;" : (s.spent_exact ? "" : "~") + money(s.spent); }
function kTokens(n) { return n >= 1000 ? Math.round(n / 1000) + "K" : String(n || 0); }
function hhmm(ts) { return new Date(ts * 1000).toTimeString().slice(0, 5); }
function ago(sec) {
  sec = Math.max(0, Math.round(sec));
  if (sec < 60) return sec + "s";
  const min = Math.floor(sec / 60);
  if (min < 60) return min + "m" + (min < 10 && sec % 60 ? " " + (sec % 60) + "s" : "");
  return Math.floor(min / 60) + "h " + (min % 60) + "m";
}
function kb(bytes) { return (bytes / 1000).toFixed(1) + " KB"; }
function baseName(p) { return String(p || "").split(/[\\/]/).filter(Boolean).pop() || p; }
function alias(model) { return (String(model || "").match(/fable|opus|sonnet|haiku/) || [model || ""])[0]; }
function label(s) { return s.state === "stop" ? "Asks you" : s.text; }
function tone(s) {  // orange only for "needs you", red and green only for state
  if (s.state === "blocked" || s.state === "failed") return "r";
  if (s.group === "needs") return "y";
  if (s.state === "done") return "g";
  return s.state === "running" ? "n" : "q";
}
function abbrev(name) {  // CONTENT MANAGER -> CM, BRAINAMP -> BRAIN
  const words = String(name || "?").split(/[\s_\-.]+/).filter(Boolean);
  return (words.length > 1 ? words.map((w) => w[0]).join("").slice(0, 3) : (words[0] || "?").slice(0, 5)).toUpperCase();
}
function cellsHtml(classes) { return classes.map((c) => `<i${c ? ` class="${c}"` : ""}></i>`).join(""); }
function railSessions() { return snap ? snap.sessions.filter((s) => s.group !== "done")
  .sort((a, b) => (a.group === "needs" ? 0 : 1) - (b.group === "needs" ? 0 : 1)) : []; }
function current() { return snap && snap.sessions.find((s) => s.id === openId); }
function routeText(s) {
  const run = [alias(s.model), s.effort].filter(Boolean).join("/");
  if (s.route === "unrouted") return run ? "unrouted · " + run : "unrouted";
  return run ? s.route + " · " + run : s.route;
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "X-CC": "1", "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const resp = await fetch(path, opts);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || "HTTP " + resp.status);
  return data;
}

// -- cells -----------------------------------------------------------------------------
function ctxClasses(tokens) {  // 30 cells up to the red threshold; from yellow on is the hand-off zone
  const [yellow, red] = cfg ? cfg.gauge : [150000, 300000];
  const per = red / 30, half = Math.round(yellow / per);
  const n = tokens == null ? 0 : Math.min(30, Math.round(tokens / per));
  return Array.from({ length: 30 }, (_, k) => k < n ? (tokens >= red ? "r" : k >= half ? "y" : "f") : "");
}
function chipCells(tokens) {  // 5 x 6, filled from the bottom row up
  const order = ctxClasses(tokens), rows = [];
  for (let r = 0; r < 6; r++) rows.unshift(order.slice(r * 5, r * 5 + 5));
  return cellsHtml(rows.flat());
}
function activityCells(levels) { return cellsHtml(levels.map((v) => v ? "l" + v : "")); }

function chip(s, big) {
  const t = tone(s), flag = s.group === "needs" ? `<span class="dot${t === "r" ? " r" : ""}"></span>` : "";
  return `<button class="chipcell${big && pane === "focus" && s.id === openId ? " sel" : ""}" data-open="${esc(s.id)}"
    title="${esc(label(s) + ": " + s.title)}"><span class="cells">${chipCells(s.ctx_tokens)}</span>
    <span class="gl ${t === "y" || t === "r" ? t : ""}">${s.symbol}</span>${big ? `<span class="lab">${esc(abbrev(s.project))}</span>` : ""}${flag}</button>`;
}

// -- forms: pill / open ------------------------------------------------------------------
async function setForm(name) {
  form = name;
  $("folded").hidden = name !== "pill";
  $("open").hidden = name !== "open";
  if (name === "pill") renderFolded(true);
  else if (native()) await window.pywebview.api.form("open");
  render();
}

async function fitPill() {
  if (native() && form === "pill") await window.pywebview.api.form("pill", Math.ceil($("folded").getBoundingClientRect().height));
}

function renderFolded(resize) {
  if (!snap) return;
  const rail = railSessions(), more = rail.length - PILL_CHIPS;
  $("pill").innerHTML = `<span class="grip pywebview-drag-region" title="Drag to move">&#8942;&#8942;</span>
    ${rail.slice(0, PILL_CHIPS).map((s) => chip(s, false)).join("")}${more > 0 ? `<span class="more">+${more}</span>` : ""}
    <span class="sp pywebview-drag-region" title="Drag to move; double-click to open"></span>
    <span class="big" title="Today, USD">${money(snap.spend.today)}</span>
    <button class="tb" data-go="unfold" aria-label="Open" title="Open (double-click the pill)">&#8964;</button>`;
  const found = snap.sessions.filter((s) => PEEK.has(s.state)).sort((a, b) => a.last_ts - b.last_ts)
    .find((s) => !seen.has(peekId(s)));
  const key = found ? peekId(found) : "";
  if (key !== peekKey || resize) {
    peekKey = key;
    $("peek").innerHTML = found ? peekCard(found) : "";
    $("folded").classList.toggle("card-on", !!found);
    fitPill();
  }
}

function peekId(s) { return `${s.id}|${s.state}|${s.turn_ts}`; }

function peekCard(s) {
  const t = tone(s), age = `<span class="age m">${ago(snap.now - s.last_ts)}</span>`;
  const head = `<div class="l1"><span class="st ${t}">${s.symbol} ${esc(label(s))}</span><span class="t">${esc(s.title)}</span>${age}</div>`;
  const open = '<button class="btn" data-peek="open">Open</button>';
  if (s.state === "stop") {
    return `<div class="askbox">${head}<div class="q">${esc(s.stop_question)}</div>
      <div class="lr"><input id="pk" aria-label="Answer" placeholder="Type your answer">
      <button class="btn you" data-peek="send">Send answer</button></div><div id="pk-msg" class="say"></div></div>`;
  }
  let text = "", buttons = open;
  if (s.state === "blocked" && s.denied) {
    text = `denied: ${s.denied.tool} ${s.denied.what}`;
    if (s.window && !s.run_live) buttons = '<button class="btn" data-peek="terminal">Open in terminal</button>' + open;
  } else if (s.state === "failed" && s.failed) {
    text = `${s.failed.error} ${s.failed.details || ""}`;
  } else if (s.state === "interrupted") {
    text = "The run stopped before it finished.";
    if (s.window) buttons = '<button class="btn you" data-peek="resume">Resume</button>' + open;
  }
  return `<div class="askbox${t === "r" ? " r" : ""}">${head}<div class="q">${esc(text)}</div>
    <div class="lr">${buttons}</div><div id="pk-msg" class="say"></div></div>`;
}

function dismissPeek() {
  if (!peekKey) return;
  seen.add(peekKey);
  renderFolded(true);
}

async function peekAct(name, button) {
  const s = snap.sessions.find((x) => peekId(x) === peekKey);
  if (!s) return dismissPeek();
  if (name === "open") { dismissPeek(); openSession(s.id); await setForm("open"); return; }
  button.disabled = true;
  try {
    if (name === "send") {
      const text = $("pk").value.trim();
      if (!text) { button.disabled = false; return; }
      await api("/api/continue", { session: s.id, text });
    }
    if (name === "resume") await api("/api/continue", { session: s.id, text: RESUME_TEXT });
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    dismissPeek();
  } catch (e) {
    button.disabled = false;
    $("pk-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`;
    fitPill();
  }
}

// -- rail --------------------------------------------------------------------------------
function renderRail() {
  $("chips").innerHTML = railSessions().map((s) => chip(s, true)).join("");
  $("total").innerHTML = `${money(snap.spend.today)}<small>today</small>`;
  $("banner").hidden = live;
}

function renderOnTop() {
  $("ontop").classList.toggle("on", onTop);
  $("ontop").title = `Always on top (${onTop ? "on" : "off"})`;
}

// -- panes -------------------------------------------------------------------------------
function showPane(name) {
  pane = name;
  leversSig = askSig = "";
  if (name === "overview") {
    $("scroll").innerHTML = '<div id="o-body" class="stack"></div>';
    $("bar").innerHTML = `<div class="compose"><div id="c-say" class="say"></div>
      <div class="lr"><select id="c-project" aria-label="Project"></select>
      <textarea id="c-prompt" rows="1" spellcheck="false" aria-label="New task"
        title="Enter = Prep · Ctrl+Enter = Run raw · Shift+Enter = new line"></textarea><span class="kbd">Enter</span></div></div>`;
    $("c-prompt").value = draft;
  } else if (name === "focus") {
    $("scroll").innerHTML = `<div id="f-head" class="stack"></div><div id="f-ask" class="stack"></div>
      <div id="f-body" class="stack"></div><div id="f-feed" class="stack"></div>`;
    $("bar").innerHTML = '<div id="f-levers" class="levers"></div>';
  } else {
    renderPrep();
  }
  render();
}

function openSession(id, list = "steps") { openId = id; tab = list; showPane("focus"); }

function render() {
  if (!snap) return;
  renderRail();
  if (firstSnap) {  // only events after the window opened bring up the peek card
    snap.sessions.filter((s) => PEEK.has(s.state)).forEach((s) => seen.add(peekId(s)));
    firstSnap = false;
  }
  if (form === "pill") { renderFolded(false); return; }
  snap.sessions.filter((s) => PEEK.has(s.state)).forEach((s) => seen.add(peekId(s)));  // seen while open
  if (pane === "overview") renderOverview();
  else if (pane === "focus") renderFocus();
}

// -- overview ----------------------------------------------------------------------------
function cardHtml(s) {
  const t = tone(s);
  let sub = s.stop_question || "";
  if (s.denied) sub = `denied: ${s.denied.tool} ${s.denied.what}`;
  else if (s.failed) sub = `${s.failed.error} ${s.failed.details || ""}`;
  else if (s.state === "interrupted") sub = "stopped before it finished: Resume";
  else if (s.state === "stall") sub = "no events for 10 min, still running";
  else if (!sub && s.ctx_tone === "red") sub = `context ${kTokens(s.ctx_tokens)}: hand off`;
  else if (s.state === "done") sub = s.verdict ? s.verdict : routeText(s);
  return `<button class="card${t === "y" || t === "r" ? " " + t : ""}" data-open="${esc(s.id)}">
    <span class="l1"><span class="st ${t}">${s.symbol} ${esc(label(s))}</span><span class="t">${esc(s.title)}</span>
    <span class="age m">${ago(snap.now - s.last_ts)}</span></span>
    <span class="sub m">${esc(s.project)}${sub ? " · " + esc(sub) : ""}</span></button>`;
}

function spendCells(sp) {
  const solid = Math.round(sp.exact / SPEND_CELL), all = Math.round(sp.today / SPEND_CELL);
  const mark = sp.budget > 0 ? Math.ceil(sp.budget * 0.8 / SPEND_CELL) - 1 : -1;
  const cols = Math.max(30, Math.ceil(Math.max(all, mark + 1) / 5));
  const cls = Array.from({ length: cols * 5 }, (_, k) =>
    [k < solid ? "f" : k < all ? "h" : "", k === mark ? "mk" : ""].filter(Boolean).join(" "));
  return `<div class="cells spend" style="--cols:${cols}">${cellsHtml(cls)}</div>`;
}

function renderOverview() {
  $("crumb").textContent = "All projects · today";
  const sp = snap.spend, rail = railSessions();
  const needs = snap.sessions.filter((s) => s.group === "needs");
  const done = snap.sessions.filter((s) => s.group === "done");
  let html = `<div class="hero"><span class="big">${money(sp.today)}</span><span class="side">
    <span class="lbl">Today, USD</span><b>$${money(sp.burn)} / min now</b>
    <span class="m mut">${sp.budget > 0 ? "soft limit $" + sp.budget : "no soft limit"}</span></span></div>
    <div class="blk">${spendCells(sp)}<div class="legend"><span><i class="f"></i>exact $${money(sp.exact)}</span>
    <span><i class="h"></i>estimated $${money(sp.estimated)}</span>${sp.budget > 0 ? '<span><i class="mk"></i>80 % of limit</span>' : ""}
    <span>1 cell = $0.50</span></div>
    ${sp.models.length ? `<div class="legend">${sp.models.map(([m, f]) =>
      `<span>${esc(m)} ${f < 0.01 ? "&lt;1" : Math.round(f * 100)} %</span>`).join("")}</div>` : ""}</div>`;
  if (rail.length) {
    html += `<div class="blk"><div class="hd"><span class="lbl">Activity · last 30 min</span><span class="m">cost</span></div>
      <div class="heat">${rail.map((s) => {
        const t = tone(s);
        return `<button class="hrow" data-open="${esc(s.id)}" title="${esc(label(s) + ": " + s.title)}">
        <span class="nm m${t === "y" || t === "r" ? " " + t : ""}">${s.symbol} ${esc(s.title)}</span>
        <span class="cells act30">${activityCells(s.activity)}</span><span class="c m">${spentText(s)}</span></button>`;
      }).join("")}</div>
      <div class="haxis"><span></span><span><span>${hhmm(snap.now - 1800)}</span><span>${hhmm(snap.now)}</span></span><span></span></div></div>`;
  }
  if (needs.length) html += `<div class="blk"><div class="hd"><span class="lbl">Needs you · ${needs.length}</span></div>${needs.map(cardHtml).join("")}</div>`;
  if (done.length) html += `<div class="blk"><div class="hd"><span class="lbl">Done today · ${done.length}</span></div>${done.map(cardHtml).join("")}</div>`;
  if (!snap.sessions.length) {
    html += `<div class="empty"><span class="lbl">Empty</span><div class="cells">${cellsHtml(Array(30).fill(""))}</div>
      <p>No Claude Code session in the last 24 hours. Start one in VS Code or a terminal, or type a task below.</p></div>`;
  }
  const pass = done.filter((s) => s.verdict === "PASS").length;
  html += `<div class="legend"><span>done today ${done.length}${pass ? " · " + pass + " PASS" : ""}</span>
    ${sp.runs ? `<span>window runs ${sp.runs}</span>` : ""}
    ${snap.writers.map((w) => `<span>2 writers: ${esc(baseName(w.project_dir))}</span>`).join("")}</div>`;
  $("o-body").innerHTML = html;
  renderCompose();
}

// -- compose (Overview) -----------------------------------------------------------------
function projects() {
  const out = new Map();
  if (cfg) for (const p of cfg.projects) out.set(p, baseName(p));
  if (snap) for (const s of snap.sessions) if (s.project_dir && !out.has(s.project_dir)) out.set(s.project_dir, s.project + " (off)");
  return out;
}

function runnable() { return !!cfg && cfg.claude && cfg.projects.includes(project); }

function renderCompose() {
  const select = $("c-project");
  if (!select) return;
  const list = projects();
  if (!list.has(project)) project = (cfg && cfg.projects[0]) || [...list.keys()][0] || "";
  const opts = [...list].map(([dir, name]) => `<option value="${esc(dir)}"${dir === project ? " selected" : ""}>${esc(name)}</option>`).join("");
  if (select.dataset.sig !== opts) { select.innerHTML = opts; select.dataset.sig = opts; }
  $("c-prompt").disabled = !!busy || !runnable();
  $("c-prompt").placeholder = runnable() ? "New task in " + baseName(project) : "";
  let html = note;
  if (busy) html = `<span class="loading"><span class="cells">${cellsHtml(["f", "", "", "", "", ""])}</span>${esc(busy)}</span>`;
  else if (!html && cfg && !cfg.claude) html = '<span class="r">claude.exe not found: set "claude_exe" in config.json</span>';
  else if (!html && !project) html = "To run: start a Claude Code session in a project first";
  else if (!html && !runnable()) html = `Runs are off in ${esc(baseName(project))}: a run uses this repo's hooks and settings without asking.
    <button class="btn" data-go="allow">Allow runs in ${esc(baseName(project))}</button>`;
  $("c-say").innerHTML = html;
}

let loadingTimer = null;
function setBusy(text) {
  busy = text;
  note = "";
  clearInterval(loadingTimer);
  if (text && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    let k = 0;
    loadingTimer = setInterval(() => {
      document.querySelectorAll(".loading .cells i").forEach((c, j) => { c.className = j === k % 6 ? "f" : ""; });
      k++;
    }, 300);
  }
  renderCompose();
}

function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => api("/api/draft", { text: draft, project }).catch(() => {}), 600);
}

async function doPrep() {
  const text = $("c-prompt").value.trim();
  if (!text || busy || !runnable()) return;
  setBusy(`Haiku is reading ${baseName(project)}, 10 to 30 s`);
  try {
    card = await api("/api/prep", { project_dir: project, prompt: text });
    setBusy("");
    showPane("prep");
  } catch (e) {
    setBusy("");
    note = `<span class="r">Prep failed: ${esc(e.message)}</span>`;
    renderCompose();
  }
}

async function doRun(projectDir, prompt, model, effort, prepId) {
  if (busy) return;
  setBusy("Starting the run ...");
  try {
    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "" });
    draft = "";
    saveDraft();
    card = null;
    setBusy("");
    openSession(r.session, "chat");
  } catch (e) {
    setBusy("");
    if (pane === "prep") $("p-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`;
    else { note = `<span class="r">Run failed: ${esc(e.message)}</span>`; renderCompose(); }
  }
}

async function allowRuns(button) {
  button.disabled = true;
  try {
    cfg.projects = (await api("/api/allow", { project_dir: project })).projects;
    note = "";
    renderCompose();
    $("c-prompt").focus();
  } catch (err) {
    note = `<span class="r">Allow failed: ${esc(err.message)}</span>`;
    renderCompose();
  }
}

// -- Prep card ---------------------------------------------------------------------------
function options(list, value) { return list.map((v) => `<option${v === value ? " selected" : ""}>${esc(v)}</option>`).join(""); }

function renderPrep() {
  const f = card.fields;
  $("crumb").textContent = "Prep / " + baseName(card.project_dir);
  $("scroll").innerHTML = `
    <div class="blk"><span class="lbl">You typed</span><div class="text">${esc(card.raw)}</div></div>
    ${f.where ? `<div class="blk"><span class="lbl">Scouted</span><div class="m">${esc(f.where)}</div></div>` : ""}
    <div class="blk"><span class="lbl">Enhanced prompt (edit freely)</span>
      <textarea id="p-prompt" class="in m" rows="9" spellcheck="false">${esc(card.prompt)}</textarea></div>
    ${f.question ? `<div class="askbox" style="margin:0"><span class="st y">? Question</span><div class="q">${esc(f.question)}</div></div>` : ""}
    <div class="blk"><span class="lbl">Route</span><div class="prep-row">
      <select id="p-model" aria-label="Model">${options(cfg.models, card.route.model)}</select>
      <select id="p-effort" aria-label="Effort">${options(cfg.efforts, card.route.effort)}</select>
      <span class="m mut">${esc(card.route.type)}</span></div>
      ${card.reason ? `<div class="mut">${esc(card.reason)}</div>` : ""}</div>
    <div class="m mut">Prep $${Number(card.cost).toFixed(3)} · ${card.turns} turns</div>`;
  $("bar").innerHTML = `<div class="levers"><div class="lr"><button class="btn go" data-pact="run">Run</button>
    <button class="btn" data-pact="raw">Run raw</button><button class="btn" data-pact="edit">Edit</button>
    <button class="btn" data-pact="cancel">Cancel</button></div><div id="p-msg" class="say"></div></div>`;
  $("p-prompt").focus();
}

function prepAct(name) {
  if (busy) return;
  if (name === "run") doRun(card.project_dir, $("p-prompt").value.trim(), $("p-model").value, $("p-effort").value, card.id);
  if (name === "raw") doRun(card.project_dir, card.raw, cfg.default_model, cfg.default_effort, "");
  if (name === "edit") { card = null; showPane("overview"); $("c-prompt").focus(); }
  if (name === "cancel") { card = null; draft = ""; saveDraft(); showPane("overview"); }
}

// -- focus: one session ------------------------------------------------------------------
function notes(s) {
  const out = [];
  const line = (word, cls, text) => out.push(`<div><b class="${cls}">${word}</b>${text}</div>`);
  if (s.verdict === "FAIL" && s.verdict_detail) line("× FAIL", "r", esc(s.verdict_detail));
  if (s.denied) line("■ denied", "r", `${esc(s.denied.tool)} ${esc(s.denied.what)} <span class="mut">${esc(s.denied.reason)}</span>`);
  if (s.denials && s.denials.length) {
    const d = s.denials[0], more = s.denials.length > 1 ? ` (+${s.denials.length - 1})` : "";
    line(`△ ${s.denials.length} denied`, "", `${esc(d.tool)} ${esc(d.what)}${more}: the run still finished; open it in a terminal to allow`);
  }
  if (s.failed) line("× " + esc(s.failed.error), "r", esc(s.failed.details));
  if (s.handoff_hint) line("↻ hand off", s.group === "needs" ? "y" : "",
    `${s.ctx_tone === "red" ? "the context is large" : s.follow_ups + " follow-ups"}: one task = one chat`);
  if (s.rules_warn) line("△ rules", "", `${esc(s.rules_warn)}: keep CLAUDE.md short; move procedures to skills and narrow rules to path rules`);
  if (s.delegate_hint) line("⇢ delegate", "", `${s.reads} reads in the main chat this turn: heavy reading belongs in a subagent (Explore)`);
  if (s.two_writers) line("△ 2 writers", "", "another session edits files in this repo");
  if (s.escalated) line("↑ escalated", "", esc(s.escalated));
  if (s.forked_from) line("↳ copy of", "", `<span class="link" data-open="${esc(s.forked_from)}">${esc(s.forked_from.slice(0, 8))}</span>`);
  if (s.forks.length) line("↳ continued in", "", s.forks.map((f) => `<span class="link" data-open="${esc(f)}">${esc(f.slice(0, 8))}</span>`).join(" "));
  line("route", "", `${esc(routeText(s))}${s.route_reason ? ` <span class="mut">${esc(s.route_reason)}</span>` : ""}`);
  line("turns", "", `${s.follow_ups} follow-up(s) · ${s.compactions} compaction(s)${s.stopped ? " · stopped by you" : ""}`);
  if (s.rules.length) line("rules", "", s.rules.map((r) => `${esc(r.file)} ${r.lines} lines ${kb(r.bytes)}`).join(" · "));
  return `<div class="notes m">${out.join("")}</div>`;
}

function pathHtml(s) {  // the playbook path: Prep, Run, Verify, Hand off
  const working = BUSY.has(s.state);
  const steps = [
    ["Prep", s.prep ? "ok" : ""],
    ["Run", working && !["verify", "handoff"].includes(s.kind) ? "cur" : s.prompts ? "ok" : ""],
    ["Verify", s.verdict === "PASS" ? "ok" : s.verdict === "FAIL" ? "bad" : working && s.kind === "verify" ? "cur" : ""],
    ["Hand off", s.state === "done" ? "ok" : working && s.kind === "handoff" ? "cur" : ""],
  ];
  const fill = { ok: "g", cur: "f", bad: "r", "": "" };
  return `<div class="path" aria-label="Task progress">${steps.map(([n, st]) =>
    `<span class="${st}"><span class="cells">${cellsHtml(Array(6).fill(fill[st]))}</span>${n}</span>`).join("")}</div>`;
}

function agentsHtml(s) {
  const working = BUSY.has(s.state), agentLive = s.agents.some((a) => a.text === "Running");
  const agentCost = s.agents.reduce((t, a) => t + a.cost, 0);
  const rows = [{ nm: "main", steps: s.main_steps, cost: s.spent == null ? null : Math.max(0, s.spent - agentCost),
                  live: working && !agentLive }]
    .concat(s.agents.map((a) => ({ nm: a.type + (a.text === "Done" ? " ✓" : "") + (a.verdict ? " " + a.verdict : ""),
                                   steps: a.steps, cost: a.cost, live: a.text === "Running" })));
  return `<div class="blk"><div class="hd"><span class="lbl">Agents · 1 cell = 2 steps</span><span class="m">steps / cost</span></div>
    <div class="agents">${rows.map((r) => {
      const n = Math.min(24, Math.max(Math.ceil(r.steps / 2), r.live ? 1 : 0));
      const cls = Array.from({ length: 24 }, (_, k) => k < n ? (r.live && k === n - 1 ? "f live" : "f") : "");
      return `<div class="agent"><span class="nm m" title="${esc(r.nm)}">${esc(r.nm)}</span><span class="cells">${cellsHtml(cls)}</span>
        <span class="m">${r.steps}</span><span class="m c">${r.cost == null ? "&ndash;" : money(r.cost)}</span></div>`;
    }).join("")}</div></div>`;
}

function renderFocus() {
  const s = current();
  if (!s) {
    $("crumb").textContent = "Starting ...";
    $("f-head").innerHTML = '<div class="mut">Starting ... (the session shows up with its first event)</div>';
    return;
  }
  const t = tone(s);
  $("crumb").textContent = [s.project, s.source === "?" ? "" : s.source, [alias(s.model), s.effort].filter(Boolean).join(" ")].filter(Boolean).join(" / ");
  const when = BUSY.has(s.state) ? ago(snap.now - s.turn_ts) : (s.state === "stop" ? "waiting " : "") + ago(snap.now - s.last_ts);
  $("f-head").innerHTML = `<div><span class="st ${t}">${s.symbol} ${esc(label(s))} · ${when}</span><h2>${esc(s.title)}</h2></div>`;
  renderAsk(s);
  const ctxWord = s.ctx_tone === "red" ? " · hand off" : s.ctx_tone === "yellow" ? " · hand off soon" : "";
  const [yellow, red] = cfg ? cfg.gauge : [150000, 300000];
  let body = "";
  if (s.state !== "stop") {
    body += `<div class="hero"><span class="big">${spentText(s)}</span><span class="side"><span class="lbl">Spent, USD</span>
      <b>$${money(s.burn)} / min</b>${s.doing ? `<span class="m mut" title="${esc(s.doing)}">doing: ${esc(s.doing)}</span>` : ""}</span></div>`;
  }
  body += notes(s) + `<div class="blk"><div class="hd"><span class="lbl${ctxWord ? (s.ctx_tone === "red" ? " r" : " y") : ""}">Context · ${s.ctx_tokens == null ? "?" : kTokens(s.ctx_tokens)}${ctxWord}</span>
    <span class="m">1 cell = ${kTokens(red / 30)}</span></div><div class="cells ctx15">${cellsHtml(ctxClasses(s.ctx_tokens))}</div>
    <div class="scale"><span>0</span><span>${kTokens(yellow)} hand off soon</span><span>${kTokens(red)} hand off</span></div></div>`;
  body += pathHtml(s);
  if (s.state !== "stop") body += agentsHtml(s);
  body += `<div class="blk"><div class="hd"><span class="lbl">Activity · last 30 min</span><span class="m">1 cell = 1 min</span></div>
    <div class="cells act30">${activityCells(s.activity)}</div></div>`;
  $("f-body").innerHTML = body;
  if (!s.window && tab === "chat") tab = "steps";
  const tabs = [["steps", "Steps"], ["timeline", "Timeline"]].concat(s.window ? [["chat", "Chat"]] : []);
  if (!$("f-list")) $("f-feed").innerHTML = '<div class="blk"><div id="f-tabs" class="hd"></div><div id="f-list"></div></div>';
  $("f-tabs").innerHTML = `<span class="lbl">${tabs.find(([k]) => k === tab)[1]}</span><span class="seg">${tabs.map(([k, n]) =>
    `<button class="${k === tab ? "on" : ""}" data-tab="${k}">${n}</button>`).join("")}</span>`;
  renderList(s).catch(() => {});
  renderLevers(s).catch(() => {});
}

function renderAsk(s) {
  const sig = s.state === "stop" ? s.id + "|" + s.stop_question : "";
  if (sig === askSig) return;
  askSig = sig;
  if (!sig) { $("f-ask").innerHTML = ""; return; }
  const where = s.window ? "Your answer continues this run."
    : `Your answer runs in a window copy of this chat. The ${s.source} chat stays as it is.`;
  $("f-ask").innerHTML = `<div class="askbox" style="margin:0"><div class="q">${esc(s.stop_question)}</div>
    <textarea class="in" id="answer" rows="3" aria-label="Answer" placeholder="${esc(where)}"></textarea>
    <div class="lr"><button class="btn you" data-act="answer">Send answer</button>
    ${s.window && !s.run_live ? '<button class="btn" data-act="terminal">Open in terminal</button>' : ""}</div>
    <div id="a-msg" class="say"></div></div>`;
}

function timelineHtml(t) {
  if (!t.lanes.some((lane) => lane.spans.length)) return '<div class="mut">Nothing yet.</div>';
  const total = Math.max(1, t.end - t.start), pos = (x) => (x - t.start) / total * 100;
  return t.lanes.map((lane) => `<div class="tl"><span class="nm m">${esc(lane.label)}${lane.verdict ? " " + esc(lane.verdict) : ""}</span>
    <span class="tl-track">${lane.spans.map(([a, b]) => `<i title="${hhmm(a)} · ${ago(b - a)}"
      style="left:${pos(a).toFixed(2)}%;width:${Math.max(0.6, pos(b) - pos(a)).toFixed(2)}%"></i>`).join("")}</span></div>`).join("")
    + `<div class="tl"><span></span><span class="tl-axis"><span>${hhmm(t.start)}</span><span>${ago(t.end - t.start)}</span><span>${hhmm(t.end)}</span></span></div>`;
}

async function renderList(s) {
  let html;
  if (tab === "timeline") {
    const t = await api("/api/timeline?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "timeline") return;
    html = `<div class="heat">${timelineHtml(t)}</div>`;
  } else if (tab === "chat") {
    const chat = await api("/api/chat?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "chat") return;
    html = chat.start_commit ? `<div class="m mut">start ${esc(chat.start_commit.slice(0, 7))} · ${chat.changed == null ? "?" : chat.changed} file(s) changed since</div>` : "";
    html += `<div class="heat">${chat.items.map((i) => `<div class="chat ${i.role}"><span class="who">${esc(i.role)}</span>
      <div class="text">${esc(i.text)}</div></div>`).join("") || '<div class="mut">Nothing yet.</div>'}</div>`;
  } else {
    const steps = await api("/api/steps?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "steps") return;
    html = `<div class="feed m">${steps.slice().reverse().map((st) => `<div${st.denied ? ' class="r"' : ""}>
      <span>${hhmm(st.ts)}</span><span>${esc(st.agent_type)}</span><span>${esc(st.tool)} ${esc(st.what)}</span></div>`).join("")
      || '<div class="mut">No tool calls yet.</div>'}</div>`;
  }
  if ($("f-list")) $("f-list").innerHTML = html;
}

async function renderLevers(s) {
  const sig = [s.id, s.window, s.run_live, s.stop_question, s.state, s.verdict, s.escalated,
               s.handoff_hint, s.forks.length].join("|");
  if (sig === leversSig) return;
  leversSig = sig;
  const lv = s.run_live ? null : await api("/api/levers?session=" + encodeURIComponent(s.id)).catch(() => null);
  if (openId !== s.id || leversSig !== sig || !$("f-levers")) return;
  let html = "";
  if (lv && !lv.continue && !s.stop_question) {
    html += `<div class="lr"><input id="fu" aria-label="Follow-up" placeholder="${lv.fork ? "Follow-up (runs in a window copy)" : "Follow-up"}">
      <button class="btn go" data-act="continue">Continue</button></div>`;
  }
  let buttons = "";
  if (s.run_live) buttons += '<button class="btn stop" data-act="stop">Stop</button>';
  if (lv && !lv.verify) buttons += '<button class="btn" data-act="verify">Verify</button>';
  if (lv && !lv.handoff) buttons += `<button class="btn${s.handoff_hint ? " go" : ""}" data-act="handoff">Hand off</button>`;
  if (lv && !lv.escalate) buttons += `<button class="btn go" data-act="escalate">Escalate to ${esc(lv.escalate_to)}</button>`;
  if (lv && !lv.continue && s.window && s.state === "interrupted") buttons += '<button class="btn go" data-act="resume">Resume</button>';
  if (s.window && !s.run_live) buttons += '<button class="btn" data-act="terminal" title="Open in terminal">Terminal</button>';
  if (buttons) html += `<div class="lr">${buttons}</div>`;
  let off = "";
  if (lv && lv.continue) off = "Levers off: " + lv.continue;
  else if (lv && lv.handoff) off = "Hand off is off: " + lv.handoff;
  if (lv && !lv.continue && s.verdict === "FAIL" && lv.escalate) off += (off ? " · " : "") + "Escalate is off: " + lv.escalate;
  html += `<div class="say">${esc(off)}</div><div id="f-msg" class="say"></div>`;
  $("f-levers").innerHTML = html;
}

let stopTimer = null;
async function act(name, button) {
  const s = current();
  if (!s) return;
  if (name === "stop" && !button.dataset.armed) {  // two clicks: a stopped turn is lost work
    button.dataset.armed = "1";
    button.textContent = "Stop run? Click again";
    clearTimeout(stopTimer);
    stopTimer = setTimeout(() => { delete button.dataset.armed; button.textContent = "Stop"; }, 3000);
    return;
  }
  const msg = name === "answer" || name === "terminal" && $("a-msg") ? $("a-msg") : $("f-msg");
  button.disabled = true;
  try {
    let r = null;
    if (name === "stop") { button.textContent = "Stopping ..."; await api("/api/stop", { session: s.id }); }
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (name === "resume") r = await api("/api/continue", { session: s.id, text: RESUME_TEXT });
    if (name === "continue" || name === "answer") {
      const text = $(name === "answer" ? "answer" : "fu").value.trim();
      if (!text) { button.disabled = false; return; }
      r = await api("/api/continue", { session: s.id, text });
    }
    if (["verify", "handoff", "escalate"].includes(name)) r = await api("/api/" + name, { session: s.id });
    if (r && r.session !== s.id) { openSession(r.session, "chat"); return; }  // a window copy (fork)
    if (r) tab = "chat";
    leversSig = askSig = "";  // redraw from the next snapshot
  } catch (e) {
    button.disabled = false;
    if (msg) msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

// -- events ------------------------------------------------------------------------------
async function go(name, button) {
  if (name === "overview") { if (form === "pill") await setForm("open"); showPane("overview"); }
  if (name === "new") { if (form === "pill") await setForm("open"); showPane("overview"); $("c-prompt").focus(); }
  if (name === "fold") await setForm("pill");
  if (name === "unfold") await setForm("open");
  if (name === "allow") allowRuns(button);
  if (!native()) return;
  if (name === "minimize") window.pywebview.api.minimize();
  if (name === "close") window.pywebview.api.close();
  if (name === "ontop") { onTop = await window.pywebview.api.on_top(!onTop); renderOnTop(); }
}

document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-go],[data-open],[data-tab],[data-act],[data-pact],[data-peek]");
  if (!t) return;
  if (t.dataset.go) go(t.dataset.go, t);
  else if (t.dataset.open) { const id = t.dataset.open; if (form === "pill") setForm("open"); openSession(id); }
  else if (t.dataset.tab) { tab = t.dataset.tab; render(); }
  else if (t.dataset.act) act(t.dataset.act, t);
  else if (t.dataset.pact) prepAct(t.dataset.pact);
  else if (t.dataset.peek) peekAct(t.dataset.peek, t);
});

document.addEventListener("dblclick", (e) => { if (e.target.closest(".pill .sp")) setForm("open"); });

document.addEventListener("input", (e) => {
  if (e.target.id === "c-prompt") { draft = e.target.value; note = ""; saveDraft(); }
});

document.addEventListener("change", (e) => {
  if (e.target.id === "c-project") { project = e.target.value; note = ""; renderCompose(); saveDraft(); }
});

document.addEventListener("keydown", (e) => {
  const id = e.target.id;
  if (id === "c-prompt" && e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    const text = e.target.value.trim();
    if (e.ctrlKey) { if (text && runnable()) doRun(project, text, cfg.default_model, cfg.default_effort, ""); }
    else doPrep();
    return;
  }
  if (id === "fu" && e.key === "Enter") return act("continue", document.querySelector('[data-act="continue"]'));
  if (id === "pk" && e.key === "Enter") return peekAct("send", document.querySelector('[data-peek="send"]'));
  if (e.ctrlKey && e.key.toLowerCase() === "n") { e.preventDefault(); go("new"); return; }
  if (e.key !== "Escape") return;
  if (form === "pill") dismissPeek();
  else if (pane === "prep") prepAct("cancel");
  else if (pane === "focus") showPane("overview");
});

window.addEventListener("pywebviewready", async () => {
  document.documentElement.classList.add("native");
  const st = await window.pywebview.api.state();
  onTop = st.on_top;
  renderOnTop();
  if (st.form !== form) await setForm(st.form);
});

function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => { live = true; snap = JSON.parse(e.data); render(); };
  es.onerror = () => { live = false; if (snap) renderRail(); };
}

(async () => {
  try { cfg = await api("/api/config"); } catch (e) { cfg = null; }
  try { draft = (await api("/api/draft")).text; } catch (e) { /* no draft */ }
  project = (cfg && cfg.project) || "";
  showPane("overview");
  connect();
})();
