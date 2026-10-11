// Claude Console window, Cells Drawer (BRAINSTORM 7.5): a folded pill with one peek card, or one open
// column: the list (needs you / working / done today), a session page, or the Prep page. A project
// picker in the header scopes the list and sets where a new task runs. Renders /api/stream snapshots;
// the levers, Prep and runs go through the same routes as phases 2-4.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const GUARDED = ["continue", "answer", "resume", "verify", "handoff", "escalate"];  // levers that re-read the context
const RESUME_TEXT = "You were interrupted. Check `git diff` first, then finish the task.";
const BUSY = new Set(["running", "quiet", "stall"]);
const PEEK = new Set(["stop", "blocked", "failed", "interrupted"]);  // a new one opens the peek card
const SPEND_CELL = 0.5;   // 1 spend cell = $0.50
const PILL_CHIPS = 9;
const DONE_SHOWN = 2;     // done sessions listed before "Show N more"
const TABS = [["steps", "Steps"], ["agents", "Agents"], ["timeline", "Timeline"], ["chat", "Chat"]];

let snap = null;
let cfg = null;          // /api/config
let live = false;
let form = "open";       // open | pill
let page = "list";       // list | session | prep | usage
let openId = null;
let tab = "steps";       // steps | agents | timeline | chat
let tlMin = -1;          // the Timeline's selected minute (minutes since 1970; -1: the last busy one)
let scope = "";          // the project folder the list shows ("" = all projects)
let project = "";        // where a new task runs (window.json, through /api/draft)
let card = null;         // the Prep card on screen
let busy = "";           // what the compose box waits for ("" = nothing)
let fail = null;         // {title, msg, retry} shown above the compose box
let draft = "";
let briefOpen = false;   // the session page's brief, open for the window (window.json)
let doneOpen = false;
let hi = 0;              // the picker's highlighted row
let draftTimer = null;
let onTop = true;
let peekKey = "";        // the event the peek card shows
let firstSnap = true;
let procSeq = 0;         // the newest process render; older ones are dropped
let procShown = "";      // session|tab the process pane shows now
let leversSig = "";
let cold = null;        // {idle_s, tokens, cost} when a lever would re-read the open session at full price
let coldTimer = null;
const seen = new Set();  // peek events already shown, answered or dismissed
const sent = {};         // "session|question" -> the session that runs the answer ("" = same one)
const cardMsg = {};      // session -> the last error of a list card

// -- helpers ---------------------------------------------------------------------------
function native() { return !!(window.pywebview && window.pywebview.api); }
function money(x) { return Number(x || 0).toFixed(2); }
function spentText(s) { return s.spent == null ? "&ndash;" : (s.spent_exact ? "" : "~") + money(s.spent); }
function kTokens(n) { return n >= 1000 ? Math.round(n / 1000) + "K" : String(n || 0); }
function two(n) { return String(n).padStart(2, "0"); }
function hhmm(ts) { return new Date(ts * 1000).toTimeString().slice(0, 5); }
function hms(ts) { return new Date(ts * 1000).toTimeString().slice(0, 8); }
function ago(sec) {
  sec = Math.max(0, Math.round(sec));
  if (sec < 60) return sec + "s";
  const min = Math.floor(sec / 60);
  if (min < 60) return min + "m" + (min < 10 && sec % 60 ? " " + (sec % 60) + "s" : "");
  return Math.floor(min / 60) + "h " + (min % 60) + "m";
}
function agoLong(sec) {  // the picker: 5m ago, 3h ago, 2d ago, 1w ago
  const min = Math.max(0, Math.round(sec / 60));
  if (min < 60) return min + "m ago";
  if (min < 1440) return Math.round(min / 60) + "h ago";
  if (min < 10080) return Math.round(min / 1440) + "d ago";
  return Math.round(min / 10080) + "w ago";
}
function elapsed(sec) {  // minutes and seconds under an hour; the seconds fall away in a narrow window
  sec = Math.max(0, Math.round(sec));
  if (sec >= 3600) return `${Math.floor(sec / 3600)}h ${two(Math.floor(sec % 3600 / 60))}m`;
  return `${Math.floor(sec / 60)}m<span class="ss"> ${two(sec % 60)}s</span>`;
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
function stateWord(s) {  // [glyph, word, tone]; a finished session says its verdict
  if (s.group === "done" && s.verdict === "PASS") return ["✓", "PASS", "g"];
  if (s.group === "done" && s.verdict === "FAIL") return ["×", "FAIL", "r"];
  return [s.symbol, label(s), tone(s)];
}
function cellsHtml(classes) { return classes.map((c) => `<i${c ? ` class="${c}"` : ""}></i>`).join(""); }
function liveSessions() { return snap ? snap.sessions.filter((s) => s.group !== "done")
  .sort((a, b) => (a.group === "needs" ? 0 : 1) - (b.group === "needs" ? 0 : 1)) : []; }
function current() { return snap && snap.sessions.find((s) => s.id === openId); }
function routeText(s) {
  const run = [alias(s.model), s.effort].filter(Boolean).join(" ");
  if (s.route === "unrouted") return run ? "unrouted · " + run : "unrouted";
  return run ? s.route + " · " + run : s.route;
}
function modelText(model, effort) { return [alias(model), effort].filter(Boolean).join(" "); }
function routeRows(s, rows) {  // the Route block: the Prep that wrote the prompt, then main and the agents
  const prep = s.prep
    ? { nm: "Prep", word: "done", model: s.prep_model, steps: s.prep_turns, unit: "t", cost: s.prep_cost }
    : { nm: "Prep", word: "none", model: "", steps: 0, unit: "", cost: null, off: true };
  return [prep].concat(rows);
}
function tlBase() { return Math.floor(snap.now / 60) - 29; }  // the minute of the Timeline's first cell
function projectName(dir) {
  const p = snap && snap.projects.find((x) => x.dir === dir);
  return (p && p.name) || baseName(dir);
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "X-CC": "1", "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const resp = await fetch(path, opts);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || "HTTP " + resp.status);
  return data;
}

// Replace an element's content only when it changed, and keep what the person is doing in it: typed text,
// the focused control and the scroll position of one inner scroller ({sel, end, reset}).
function focusKey(el) {
  if (el.id) return `[id="${el.id}"]`;
  for (const k of ["tab", "min", "open"]) if (el.dataset[k] !== undefined) return `[data-${k}="${el.dataset[k]}"]`;
  return "";
}
function setHtml(el, html, scroller) {
  if (el._html === html) return false;
  const active = document.activeElement, key = active && el.contains(active) ? focusKey(active) : "";
  const fields = [...el.querySelectorAll("input[id],textarea[id]")].map((f) => [f.id, f.value, f.selectionStart, f.selectionEnd]);
  const old = scroller && el.querySelector(scroller.sel);
  const top = old ? old.scrollTop : 0, atEnd = old ? old.scrollTop + old.clientHeight >= old.scrollHeight - 4 : false;
  el.innerHTML = html;
  el._html = html;
  for (const [id, value, a, b] of fields) {
    const f = $(id);
    if (f && f.value !== value) { f.value = value; try { f.setSelectionRange(a, b); } catch (e) { /* not a text field */ } }
  }
  const now = scroller && el.querySelector(scroller.sel);
  if (now) now.scrollTop = scroller.reset || (scroller.end && atEnd) ? (scroller.end ? now.scrollHeight : 0) : top;
  if (key) { const f = el.querySelector(key); if (f) f.focus({ preventScroll: true }); }
  return true;
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
function ctxTone(s) { return s.ctx_tone === "red" ? "r" : s.ctx_tone === "yellow" ? "y" : ""; }
function ctxMini(s) {  // the card's context: 15 x 2 cells and the figure
  return `<span class="ctx"><span class="cells">${cellsHtml(ctxClasses(s.ctx_tokens))}</span>
    <b class="${ctxTone(s)}">${s.ctx_tokens == null ? "?" : kTokens(s.ctx_tokens)}</b></span>`;
}

function chip(s) {
  const t = tone(s), flag = s.group === "needs" ? `<span class="dot${t === "r" ? " r" : ""}"></span>` : "";
  return `<button class="chipcell" data-open="${esc(s.id)}" title="${esc(label(s) + ": " + s.title)}">
    <span class="cells">${chipCells(s.ctx_tokens)}</span>
    <span class="gl ${t === "y" || t === "r" ? t : ""}">${s.symbol}</span>${flag}</button>`;
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
  const rail = liveSessions(), more = rail.length - PILL_CHIPS;
  $("pill").innerHTML = `<span class="grip pywebview-drag-region" title="Drag to move">&#8942;&#8942;</span>
    ${rail.slice(0, PILL_CHIPS).map(chip).join("")}${more > 0 ? `<span class="more">+${more}</span>` : ""}
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

// What a session that needs Fred says, and the buttons that unblock it (the peek card and the list card).
function needText(s) {
  if (s.state === "blocked" && s.denied) return `denied: ${s.denied.tool} ${s.denied.what}`;
  if (s.state === "failed" && s.failed) return `${s.failed.error} ${s.failed.details || ""}`.trim();
  if (s.state === "interrupted") return "The run stopped before it finished.";
  if (s.state === "stall") return "no events for 10 min, still running";
  if (s.ctx_tone === "red") return `context ${kTokens(s.ctx_tokens)}: hand off`;
  return "";
}
function needButtons(s, where, withOpen) {
  const b = (name, cls, text) => `<button class="btn${cls} sm" data-do="${name}" data-sid="${esc(s.id)}" data-where="${where}">${text}</button>`;
  let out = "";
  if (s.state === "blocked" && s.window && !s.run_live) out += b("terminal", "", "Open in terminal");
  if (s.state === "interrupted" && s.window) out += b("resume", " you", "Resume");
  return out + (withOpen ? b("open", "", "Open") : "");
}

function peekCard(s) {
  const t = tone(s), age = `<span class="age m">${ago(snap.now - s.last_ts)}</span>`;
  const head = `<div class="l1"><span class="st ${t}">${s.symbol} ${esc(label(s))}</span><span class="t">${esc(s.title)}</span>${age}</div>`;
  if (s.state === "stop") {
    return `<div class="askbox">${head}<div class="q">${esc(s.stop_question)}</div>
      <div class="lr"><input id="pk" aria-label="Answer" placeholder="Type your answer">
      <button class="btn you sm" data-do="send" data-sid="${esc(s.id)}" data-where="peek">Send answer</button></div><div id="pk-msg" class="say"></div></div>`;
  }
  return `<div class="askbox${t === "r" ? " r" : ""}">${head}<div class="q">${esc(needText(s))}</div>
    <div class="lr">${needButtons(s, "peek", true)}</div><div id="pk-msg" class="say"></div></div>`;
}

function dismissPeek() {
  if (!peekKey) return;
  seen.add(peekKey);
  renderFolded(true);
}

// send / terminal / resume / open from a peek card or a list card
async function unblock(button) {
  const name = button.dataset.do, peek = button.dataset.where === "peek";
  const s = snap && snap.sessions.find((x) => x.id === button.dataset.sid);
  if (!s) { if (peek) dismissPeek(); return; }
  if (name === "open") { if (peek) dismissPeek(); openSession(s.id); return; }
  const field = name === "send" ? $(peek ? "pk" : "ca-" + s.id) : null;
  const text = field ? field.value.trim() : "";
  if (name === "send" && !text) return;
  button.disabled = true;
  try {
    let r = null;
    if (name === "send") r = await api("/api/continue", { session: s.id, text });
    if (name === "resume") await api("/api/continue", { session: s.id, text: RESUME_TEXT });
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (peek) return dismissPeek();
    delete cardMsg[s.id];
    if (r) { sent[s.id + "|" + s.stop_question] = r.session === s.id ? "" : r.session; field.value = ""; }
    render();
  } catch (e) {
    button.disabled = false;
    if (peek) { $("pk-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`; fitPill(); }
    else { cardMsg[s.id] = e.message; render(); }
  }
}

function renderOnTop() {
  document.querySelectorAll('[data-go="ontop"]').forEach((b) => {
    b.classList.toggle("on", onTop);
    b.title = `Always on top (${onTop ? "on" : "off"})`;
  });
}

// -- pages -------------------------------------------------------------------------------
function showPage(name) {
  page = name;
  closePicker();
  document.querySelectorAll("[data-page]").forEach((p) => { p.hidden = p.dataset.page !== name; });
  leversSig = "";
  procShown = "";
  if (name === "session") $("sscroll").scrollTop = 0;
  clearInterval(usageTimer);
  usageTimer = null;
  if (name === "usage") { $("uscroll").scrollTop = 0; loadUsage(); usageTimer = setInterval(loadUsage, 60000); }
  render();
}

async function openSession(id, list = "steps") {
  if (form === "pill") await setForm("open");
  openId = id;
  tab = list;
  tlMin = -1;
  const s = current();
  if (s && s.project_dir) project = s.project_dir;
  showPage("session");
}

function inScope(s) { return !scope || s.project_dir === scope; }
function groups() {
  const mine = snap.sessions.filter(inScope);
  return { needs: mine.filter((s) => s.group === "needs"), work: mine.filter((s) => s.group === "working"),
    done: mine.filter((s) => s.group === "done").sort((a, b) => b.last_ts - a.last_ts) };
}
function navList() {  // the sessions ‹ › step through: the list in its order, or all when the open one is out of scope
  const g = groups(), all = [...g.needs, ...g.work, ...g.done];
  if (all.some((s) => s.id === openId)) return all;
  return [...snap.sessions].sort((a, b) => (a.group === "needs" ? 0 : 1) - (b.group === "needs" ? 0 : 1));
}

function render() {
  if (!snap) return;
  $("banner").hidden = live;
  if (firstSnap) {  // only events after the window opened bring up the peek card
    snap.sessions.filter((s) => PEEK.has(s.state)).forEach((s) => seen.add(peekId(s)));
    firstSnap = false;
  }
  if (form === "pill") { renderFolded(false); return; }
  snap.sessions.filter((s) => PEEK.has(s.state)).forEach((s) => seen.add(peekId(s)));  // seen while open
  if (page === "list") renderListPage();
  else if (page === "session") renderSession();
}

// -- list page ---------------------------------------------------------------------------
function spendRow(sp) {  // one row: solid = exact, hatched = estimated, orange outline at 80 % of the limit
  const solid = Math.round(sp.exact / SPEND_CELL), all = Math.round(sp.today / SPEND_CELL);
  const mark = sp.budget > 0 ? Math.ceil(sp.budget * 0.8 / SPEND_CELL) - 1 : -1;
  const cols = Math.max(30, all, mark + 1);
  const cls = Array.from({ length: cols }, (_, k) =>
    [k < solid ? "f" : k < all ? "h" : "", k === mark ? "mk" : ""].filter(Boolean).join(" "));
  return { cols, html: cellsHtml(cls) };
}

function renderTop() {
  const n = snap.counts.needs;
  $("needsbtn").hidden = !n;
  $("needsbtn").textContent = `${n} ${n === 1 ? "needs" : "need"} you`;
  $("scopenm").textContent = scope ? projectName(scope) : "All projects";
  const sp = snap.spend, row = spendRow(sp);
  setHtml($("today"), `<span class="big">${money(sp.today)}</span><span class="cells row30" style="--cols:${row.cols}">${row.html}</span>
    <span class="sub m"><span>today<span class="usd">, USD</span> · $${money(sp.burn)} / min</span>
    <span>${sp.budget > 0 ? "limit $" + sp.budget : "no limit"}</span></span>`);
  setHtml($("todaymore"), `<div class="legend"><span><i class="f"></i>exact $${money(sp.exact)}</span>
    <span><i class="h"></i>estimated $${money(sp.estimated)}</span>${sp.budget > 0 ? '<span><i class="mk"></i>80 % of limit</span>' : ""}</div>
    <div class="legend"><span>1 cell = $0.50</span>${sp.models.map(([m, f]) => `<span>${esc(m)} ${f < 0.01 ? "&lt;1" : Math.round(f * 100)} %</span>`).join("")}
    ${sp.runs ? `<span>window runs ${sp.runs}</span>` : ""}
    ${snap.writers.map((w) => `<span>2 writers: ${esc(baseName(w.project_dir))}</span>`).join("")}</div>
    <button class="btn sm go-usage" data-go="usage">Usage by day, week, month &#8250;</button>`);
}

function cardHtml(s) {
  const t = tone(s), key = s.id + "|" + s.stop_question;
  let third = "";
  if (s.state === "stop" && key in sent) {
    const to = sent[key];
    third = `<div class="m mut" data-stay>Answer sent. ${to ? `It runs in a window copy: <span class="link" data-open="${esc(to)}">open it</span>` : "It continues here."}</div>`;
  } else if (s.state === "stop") {
    third = `<div class="q">${esc(s.stop_question)}</div><div class="lr" data-stay><input id="ca-${esc(s.id)}" aria-label="Answer" placeholder="Type your answer">
      <button class="btn you sm" data-do="send" data-sid="${esc(s.id)}" data-where="card">Send</button></div>`;
  } else {
    const text = s.group === "needs" ? needText(s) : "", buttons = s.group === "needs" ? needButtons(s, "card", false) : "";
    const agent = s.agents.find((a) => a.text === "Running");
    third = (text ? `<div class="m mut">${esc(text)}</div>` : "") + (buttons ? `<div class="lr" data-stay>${buttons}</div>` : "");
    if (s.state === "running" && (s.doing || agent)) {
      third += `<div class="doing m"><span class="cells"><i class="f live"></i></span><span>${esc(agent ? agent.type : "main")}</span>
        <span>${esc(agent ? agent.doing : s.doing)}</span></div>`;
    }
  }
  if (cardMsg[s.id]) third += `<div class="say" data-stay><span class="r">${esc(cardMsg[s.id])}</span></div>`;
  const hand = s.handoff_hint ? ` <span class="st ${s.ctx_tone === "red" ? "r" : "q"}">· HAND OFF</span>` : "";
  return `<div class="card${t === "y" || t === "r" ? " " + t : ""}" data-open="${esc(s.id)}" tabindex="0" role="button"
    aria-label="${esc(label(s) + ": " + s.title)}">
    <div class="l1"><span class="st ${t}">${s.symbol} ${esc(label(s))}${hand}</span><span class="t">${esc(s.title)}</span>
    <span class="age m">${ago(snap.now - s.last_ts)}</span></div>
    <div class="l2 m"><span class="who">${esc(s.project)}${s.two_writers ? " · 2 writers" : ""}<span class="route"> · ${esc(routeText(s))}</span></span>
    <span class="cost">${spentText(s)}</span>${ctxMini(s)}</div>${third}</div>`;
}

function quietHtml(s, showProject) {
  const [glyph, word, t] = stateWord(s);
  return `<div class="card quiet" data-open="${esc(s.id)}" tabindex="0" role="button" aria-label="${esc(word + ": " + s.title)}">
    <div class="l1"><span class="st ${t}">${glyph} ${esc(word)}</span><span class="t">${esc(s.title)}${showProject ? ` <span class="m mut">· ${esc(s.project)}</span>` : ""}</span>
    <span class="age m">${spentText(s)}</span></div></div>`;
}

function renderListPage() {
  renderTop();
  const g = groups(), shown = doneOpen ? g.done : g.done.slice(0, DONE_SHOWN);
  const sec = (cls, text, list, id = "") => list.length ? `<div class="sec"${id ? ` id="${id}"` : ""}><span class="lbl ${cls}">${text} · ${list.length}</span></div>` : "";
  let html = sec("y", "Needs you", g.needs, "needsec") + g.needs.map(cardHtml).join("")
    + sec("", "Working", g.work) + g.work.map(cardHtml).join("")
    + sec("", "Done today", g.done) + shown.map((s) => quietHtml(s, !scope)).join("")
    + (g.done.length > DONE_SHOWN && !doneOpen ? `<div class="more-done"><button class="btn sm" data-go="moredone">Show ${g.done.length - DONE_SHOWN} more</button></div>` : "");
  if (!g.needs.length && !g.work.length && !g.done.length) {
    html = scope
      ? `<div class="sec"><span class="lbl">${esc(projectName(scope))}</span></div><div class="empty"><div class="cells">${cellsHtml(Array(30).fill(""))}</div>
         <p>No session in ${esc(projectName(scope))} today. Type a task below, or pick All projects.</p></div>`
      : `<div class="empty"><div class="cells">${cellsHtml(Array(30).fill(""))}</div>
         <p>No Claude Code session in the last 24 hours. Start one in VS Code or a terminal, or type a task below.</p></div>`;
  }
  setHtml($("list"), html);
  renderCompose();
}

// -- compose -----------------------------------------------------------------------------
function runnable() { return !!cfg && cfg.claude && cfg.projects.includes(project); }

function renderCompose() {
  if (!project || !projectKnown(project)) project = (cfg && cfg.projects[0]) || (snap && snap.projects[0] && snap.projects[0].dir) || "";
  if (!snap) return;
  const box = $("c-prompt");
  box.disabled = !!busy || !runnable();
  box.placeholder = runnable() ? "New task" : "Allow runs first";
  const chipHtml = `<button class="tgt" data-pick title="Change project (Ctrl+P)">${esc(projectName(project))}<span class="car">&#9662;</span></button>`;
  let html;
  if (busy) html = `<span class="loading"><span class="cells">${cellsHtml(["f", "", "", "", "", ""])}</span>${esc(busy)}</span>`;
  else if (cfg && !cfg.claude) html = '<span class="r">claude.exe not found: set "claude_exe" in config.json</span>';
  else if (!project) html = "To run: start a Claude Code session in a project first";
  else if (!runnable()) html = `<span>Runs are off in ${chipHtml}: a run would use this repo's hooks and settings without asking.</span>
    <button class="btn sm" data-go="allow">Allow runs</button>`;
  else html = `<span>in</span>${chipHtml}<span class="hint"><span class="kbd">Enter</span>Prep</span>`;
  setHtml($("c-say"), html);
  setHtml($("prepfail"), fail ? `<div class="card r" style="cursor:default"><div class="l1"><span class="st r">× FAILED</span><span class="t">${esc(fail.title)}</span></div>
    <div class="m mut">${esc(fail.msg)}</div>${fail.retry ? '<div class="lr"><button class="btn go sm" data-go="retry">Try again</button></div>' : ""}</div>` : "");
}

let loadingTimer = null;
function setBusy(text) {
  busy = text;
  fail = null;
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
  draftTimer = setTimeout(() => api("/api/draft", { text: draft, project, brief: briefOpen }).catch(() => {}), 600);
}

async function doPrep() {
  const text = $("c-prompt").value.trim();
  if (!text || busy || !runnable()) return;
  setBusy(`Haiku is reading ${projectName(project)}, 10 to 30 s`);
  try {
    card = await api("/api/prep", { project_dir: project, prompt: text });
    setBusy("");
    showPrep();
  } catch (e) {
    setBusy("");
    fail = { title: "Prep failed", msg: e.message, retry: "prep" };
    renderCompose();
  }
}

async function doRun(projectDir, prompt, model, effort, prepId) {
  if (busy) return;
  setBusy("Starting the run ...");
  try {
    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "" });
    draft = "";
    $("c-prompt").value = "";
    saveDraft();
    card = null;
    setBusy("");
    openSession(r.session, "chat");
  } catch (e) {
    setBusy("");
    if (page === "prep") $("p-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`;
    else { fail = { title: "Run failed", msg: e.message, retry: "raw" }; renderCompose(); }
  }
}

async function allowRuns(button) {
  if (button) button.disabled = true;
  try {
    cfg.projects = (await api("/api/allow", { project_dir: project })).projects;
    fail = null;
    renderCompose();
    $("c-prompt").focus();
  } catch (err) {
    fail = { title: "Allow runs failed", msg: err.message, retry: "" };
    renderCompose();
  }
}

// -- project picker ------------------------------------------------------------------------
function projectKnown(dir) { return !!snap && ((!!cfg && cfg.projects.includes(dir)) || snap.projects.some((p) => p.dir === dir)); }

function projectRows() {  // allowed folders and every folder a session ran in, with what goes on there
  const by = new Map();
  const row = (dir) => { if (!by.has(dir)) by.set(dir, { dir, name: baseName(dir), on: cfg.projects.includes(dir), last: 0, today: 0, live: 0, needs: 0 }); return by.get(dir); };
  cfg.projects.forEach(row);
  snap.projects.forEach((p) => Object.assign(row(p.dir), { name: p.name || baseName(p.dir), last: p.last_ts, today: p.today }));
  snap.sessions.forEach((s) => { if (s.project_dir && s.group !== "done") { const r = row(s.project_dir); r.live++; r.needs += s.group === "needs"; } });
  return [...by.values()];
}

function pickRows() {
  const q = $("pfind").value.trim().toLowerCase();
  const recent = (p) => p.last || -Infinity;
  const order = (a, b) => (b.needs - a.needs) || (b.live - a.live) || (recent(b) - recent(a)) || a.name.localeCompare(b.name);
  const match = projectRows().filter((p) => !q || p.name.toLowerCase().includes(q));
  const line = (p) => {
    const meta = p.needs ? `<span class="meta y">${p.needs} needs you</span>` : p.live ? `<span class="meta">${p.live} live</span>`
      : `<span class="meta">${p.on ? (p.last ? agoLong(snap.now - p.last) : "no session yet") : "runs off"}</span>`;
    return `<button class="prow${p.on ? "" : " off"}" role="option" aria-selected="${scope === p.dir}" data-proj="${esc(p.dir)}">
      <span class="ck">${scope === p.dir ? "✓" : ""}</span><span class="nm">${esc(p.name)}</span>${meta}<span class="c">${p.today ? money(p.today) : "-"}</span></button>`;
  };
  const on = match.filter((p) => p.on).sort(order), off = match.filter((p) => !p.on).sort(order);
  let html = q ? "" : `<button class="prow" role="option" aria-selected="${!scope}" data-proj=""><span class="ck">${scope ? "" : "✓"}</span>
    <span class="nm">All projects</span><span class="meta">${liveSessions().length} live</span><span class="c">${money(snap.spend.today)}</span></button>`;
  if (on.length) html += `<div class="grp lbl">Runs allowed · ${on.length}</div>${on.map(line).join("")}`;
  if (off.length) html += `<div class="grp lbl">Runs off · ${off.length}</div>${off.map(line).join("")}`;
  if (!match.length) html = `<div class="none">No project matches "${esc(q)}". Projects appear here once a Claude Code session runs in them.</div>`;
  $("prows").innerHTML = html;
  hi = 0;
  markHi();
}

function markHi() {
  const rows = [...document.querySelectorAll("#prows .prow")];
  rows.forEach((r, k) => r.classList.toggle("hi", k === hi));
  if (rows[hi]) rows[hi].scrollIntoView({ block: "nearest" });
}

function openPicker() {
  if (!snap || !cfg) return;
  if (form === "pill") return;
  if (page !== "list") showPage("list");
  $("pop").hidden = false;
  $("pop").style.top = ($("scope").getBoundingClientRect().bottom - $("open").getBoundingClientRect().top + 4) + "px";  // under the header, banner or not
  $("scope").setAttribute("aria-expanded", "true");
  $("pfind").value = "";
  pickRows();
  $("pfind").focus();
}

function closePicker() {
  $("pop").hidden = true;
  $("scope").setAttribute("aria-expanded", "false");
}

function pick(dir) {  // a project scopes the list and becomes the task target; All projects keeps the target
  scope = dir;
  if (dir) project = dir;
  doneOpen = false;
  closePicker();
  render();
  saveDraft();
}

// -- Prep page ---------------------------------------------------------------------------
function options(list, value) { return list.map((v) => `<option${v === value ? " selected" : ""}>${esc(v)}</option>`).join(""); }

function showPrep() {
  const f = card.fields;
  $("crumb").textContent = "Prep / " + projectName(card.project_dir);
  $("pscroll").innerHTML = `
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
  $("pbar").innerHTML = `<div class="lr"><button class="btn go" data-pact="run">Run</button>
    <button class="btn" data-pact="raw">Run raw</button><button class="btn" data-pact="edit">Edit</button>
    <button class="btn" data-pact="cancel">Cancel</button></div><div id="p-msg" class="say"></div>`;
  showPage("prep");
  $("p-prompt").focus();
}

function prepAct(name) {
  if (busy) return;
  if (name === "run") doRun(card.project_dir, $("p-prompt").value.trim(), $("p-model").value, $("p-effort").value, card.id);
  if (name === "raw") doRun(card.project_dir, card.raw, cfg.default_model, cfg.default_effort, "");
  if (name === "edit") { card = null; showPage("list"); $("c-prompt").focus(); }
  if (name === "cancel") { card = null; draft = ""; $("c-prompt").value = ""; saveDraft(); showPage("list"); }
}

// -- session page ------------------------------------------------------------------------
function noteLine(s) {  // one muted line, only when there is something to say
  const out = [], link = (id) => `<span class="link" data-open="${esc(id)}">${esc(id.slice(0, 8))}</span>`;
  if (s.verdict === "FAIL") out.push(`<span class="r">× FAIL ${esc(s.verdict_detail)}</span>`);
  if (s.denials && s.denials.length) {
    const d = s.denials[0], more = s.denials.length > 1 ? ` +${s.denials.length - 1}` : "";
    out.push(`△ ${s.denials.length} denied (${esc(d.tool)} ${esc(d.what)}${more}), the run still finished`);
  }
  if (s.handoff_hint) out.push(`<span class="${s.group === "needs" ? "y" : ""}">↻ hand off: ${s.ctx_tone === "red" ? "the context is large" : s.follow_ups + " follow-ups"}, one task = one chat</span>`);
  if (s.rules_warn) out.push(`△ rules: ${esc(s.rules_warn)}`);
  if (s.delegate_hint) out.push(`⇢ delegate? ${s.reads} reads in the main chat this turn`);
  if (s.two_writers) out.push("△ 2 writers: another session edits files in this repo");
  if (s.escalated) out.push(`↑ escalated ${esc(s.escalated)}`);
  if (s.forked_from) out.push(`↳ copy of ${link(s.forked_from)}`);
  if (s.forks.length) out.push(`↳ continued in ${s.forks.map(link).join(" ")}`);
  return out.length ? `<p class="note m">${out.join(" · ")}</p>` : "";
}

function askBlock(s) {
  if (s.state === "stop") {
    const where = s.window ? "Your answer continues this run."
      : `Your answer runs in a window copy of this chat. The ${s.source} chat stays as it is.`;
    return `<div class="askbox"><div class="q">${esc(s.stop_question)}</div>
      <textarea class="in" id="answer" rows="3" aria-label="Answer" placeholder="${esc(where)}"></textarea>
      <div class="lr"><button class="btn you" data-act="answer">Send answer</button>
      ${s.window && !s.run_live ? '<button class="btn" data-act="terminal">Open in terminal</button>' : ""}</div>
      <div id="a-msg" class="say"></div></div>`;
  }
  if (s.state === "blocked" && s.denied) {
    return `<div class="card r"><div class="denied">denied: ${esc(s.denied.tool)} ${esc(s.denied.what)} <span class="mut">${esc(s.denied.reason)}</span></div>
      ${s.window && !s.run_live ? '<div class="lr"><button class="btn go sm" data-act="terminal">Open in terminal</button></div>' : ""}
      <div id="a-msg" class="say"></div></div>`;
  }
  if (s.state === "failed" && s.failed) {
    return `<div class="card r"><div class="denied">× ${esc(s.failed.error)} ${esc(s.failed.details || "")}</div></div>`;
  }
  return "";
}

function pathHtml(s) {  // the playbook path: Prep, Run, Verify, Hand off
  const working = BUSY.has(s.state);
  const steps = [
    ["Prep", s.prep ? "ok" : ""],
    ["Run", working && !["verify", "handoff"].includes(s.kind) ? "cur" : s.prompts ? "ok" : ""],
    ["Verify", s.verdict === "PASS" ? "ok" : s.verdict === "FAIL" ? "bad" : working && s.kind === "verify" ? "cur" : ""],
    ["Hand off", s.state === "done" ? "ok" : working && s.kind === "handoff" ? "cur" : ""],
  ];
  const fill = { ok: "g", cur: "f", bad: "r", "": "" }, mark = { ok: "✓ ", cur: "▶ ", bad: "× ", "": "" };
  return steps.map(([n, st]) => `<span class="${st}"><span class="cells">${cellsHtml(Array(6).fill(fill[st]))}</span>${mark[st]}${n}</span>`).join("");
}

function agentRows(s, steps) {  // main first, then the agents; `steps` (oldest first) gives each one's last step
  const working = BUSY.has(s.state), running = s.agents.some((a) => a.text === "Running");
  const agentCost = s.agents.reduce((t, a) => t + a.cost, 0);
  const last = (id) => { for (let k = steps.length - 1; k >= 0; k--) if (steps[k].agent === id) return steps[k]; return null; };
  return [{ nm: "main", id: "", steps: s.main_steps, cost: s.spent == null ? null : Math.max(0, s.spent - agentCost),
            model: s.model, effort: s.effort, word: working ? (running ? "waiting" : "working") : label(s).toLowerCase() }]
    .concat(s.agents.map((a) => ({ nm: a.type, id: a.id, steps: a.steps, cost: a.cost, verdict: a.verdict,
      model: a.model, effort: a.effort,
      word: a.text === "Running" ? "working" : a.text === "Done" ? "done" : a.text.toLowerCase() })))
    .map((r) => Object.assign(r, { last: last(r.id) }));
}

function renderBrief(s) {
  const t = ctxTone(s), steps = s.main_steps + s.agents.reduce((n, a) => n + a.steps, 0);
  const [yellow, red] = cfg ? cfg.gauge : [150000, 300000];
  const end = BUSY.has(s.state) ? snap.now : s.last_ts;
  const spent = s.spent == null ? "&ndash;" : (s.spent_exact ? "" : '<span class="est" title="estimated">~</span>') + money(s.spent);
  const word = t === "r" ? "hand off now" : t === "y" ? "hand off soon" : "context";
  const rows = agentRows(s, []);
  return `<div class="bwrap">
    <button class="brief" id="brief" aria-expanded="${briefOpen}" aria-controls="more" title="Context, agents and activity (click or Space)">
      <span class="path">${pathHtml(s)}<span class="car" aria-hidden="true">${briefOpen ? "▴" : "▾"}</span></span>
      <span class="stats">
        <span><small>spent</small><b class="usd">${spent}</b></span>
        <span><small>$ / min</small><b>${money(s.burn)}</b></span>
        <span><small class="${t}">${word}</small><span class="cx"><span class="cells">${cellsHtml(ctxClasses(s.ctx_tokens))}</span>
          <b class="${t}">${s.ctx_tokens == null ? "?" : kTokens(s.ctx_tokens)}</b></span></span>
        <span><small>time</small><b>${elapsed(end - s.started_ts)}</b></span>
        <span><small>steps</small><b>${steps}</b></span>
      </span>
    </button>
    <div class="more" id="more"${briefOpen ? "" : " hidden"}>
      <div class="blk"><div class="hd"><span class="lbl${t ? " " + t : ""}">Context${t === "y" ? " · hand off soon" : t === "r" ? " · hand off now" : ""}</span>
        <span class="m">1 cell = ${kTokens(red / 30)}</span></div>
        <div class="cells act30">${cellsHtml(ctxClasses(s.ctx_tokens))}</div>
        <div class="scale"><span>0</span><span>${kTokens(yellow)} hand off soon</span><span>${kTokens(red)} hand off</span></div></div>
      <div class="blk"><div class="hd"><span class="lbl">Route · 1 cell = 2 steps</span><span class="m">model · steps / cost</span></div><div class="agents">
        ${routeRows(s, rows).map((r) => `<div class="agent${r.off ? " off" : ""}"><span class="nm m" title="${esc(r.nm)}">${r.word === "done" ? "✓ " : r.word === "working" ? "▶ " : ""}${esc(r.nm)}${r.verdict ? " " + esc(r.verdict) : ""}</span>
          <span class="cells">${cellsHtml(Array.from({ length: 24 }, (_, k) => k < Math.ceil(r.steps / 2) ? "f" : ""))}</span>
          <span class="m" title="${esc(r.model || "")}">${r.off ? "none" : esc(modelText(r.model, r.effort)) || "&ndash;"}</span>
          <span class="m"${r.unit ? ' title="turns"' : ""}>${r.off ? "" : r.steps + (r.unit || "")}</span><span class="m c">${r.cost == null ? "&ndash;" : money(r.cost)}</span></div>`).join("")}
        ${s.escalated ? `<div class="esc m">↑ escalated ${esc(s.escalated)}${s.escalated_ts ? " · " + hhmm(s.escalated_ts) : ""}</div>` : ""}</div>
        ${s.models.length ? `<div class="legend"><span>model mix</span>${s.models.map(([m, f]) => `<span>${esc(m)} ${f < 0.01 ? "&lt;1" : Math.round(f * 100)} %</span>`).join("")}</div>` : ""}</div>
      <div class="blk"><div class="hd"><span class="lbl">Activity · last 30 min</span><span class="m">1 cell = 1 min</span></div>
        <div class="cells act30">${activityCells(s.activity)}</div></div>
    </div></div>`;
}

function renderSession() {
  const s = current(), nav = navList(), k = nav.findIndex((x) => x.id === openId);
  $("pos").textContent = k >= 0 ? `${k + 1} of ${nav.length}` : "";
  $("prev").disabled = k <= 0;
  $("next").disabled = k < 0 || k >= nav.length - 1;
  if (!s) {
    setHtml($("sbody"), '<div class="mut">Starting ... (the session shows up with its first event)</div>');
    $("proc").innerHTML = "";
    $("proc")._html = "";
    setHtml($("levers"), "");
    return;
  }
  const t = tone(s);
  const when = BUSY.has(s.state) ? ago(snap.now - s.turn_ts) : (s.state === "stop" ? "waiting " : "") + ago(snap.now - s.last_ts);
  const src = s.source === "?" ? "" : s.source + " / ";
  setHtml($("sbody"), `<div class="head"><span class="st ${t}">${s.symbol} ${esc(label(s))} <span class="lc">· ${when}</span></span><h2>${esc(s.title)}</h2>
    <div class="where"><span class="m" title="${esc(s.route_reason || "")}">${esc(s.project)} / ${esc(src)}${esc(s.route)}</span>
    ${s.model ? `<span class="mdl" title="${esc(s.model)}">${esc(modelText(s.model, s.effort))}</span>` : ""}
    ${s.project_dir ? `<button class="btn sm" data-here="${esc(s.project_dir)}">New task here</button>` : ""}</div></div>
    ${noteLine(s)}${askBlock(s)}${renderBrief(s)}`);
  renderProc(s).catch(() => {});
  renderLevers(s).catch(() => {});
}

const LIVE = '<span class="cells"><i class="f live"></i></span>';
function logRow(x, mark = "", tag = "") {  // `tag`: the step's model when it is not main's
  return `<div${x.denied ? ' class="r"' : ""}><span>${mark}</span><span>${hms(x.ts)}</span><span>${esc(x.agent_type)}</span><span>${tag ? `<span class="tag">${esc(tag)}</span>` : ""}${esc(x.tool)} ${esc(x.what)}</span></div>`;
}
function stepTag(s) {  // agent id -> its model family, only where it differs from main's
  const main = alias(s.model), by = {};
  for (const a of s.agents) if (alias(a.model) && alias(a.model) !== main) by[a.id] = alias(a.model);
  return (x) => by[x.agent] || "";
}

async function renderProc(s) {
  const seq = ++procSeq, wanted = tab;
  let steps = [], chat = null;
  if (wanted === "chat") chat = await api("/api/chat?session=" + encodeURIComponent(s.id));
  else steps = await api("/api/steps?session=" + encodeURIComponent(s.id));
  if (seq !== procSeq || openId !== s.id || tab !== wanted) return;
  const rows = agentRows(s, steps);
  const newest = steps.slice().reverse();
  let body = "";
  if (wanted === "steps") {
    const mark = s.state === "running" ? LIVE : s.state === "stop" ? '<span class="st y">?</span>' : s.state === "blocked" ? '<span class="st r">■</span>' : "";
    const tag = stepTag(s);
    body = newest.length ? `<div class="log">${newest.map((x, k) => logRow(x, k === 0 ? mark : "", tag(x))).join("")}</div>` : '<p class="none">No step yet.</p>';
  } else if (wanted === "agents") {
    body = `<div class="alist">${rows.map((r) => {
      const m = r.word === "working" && s.state === "running" ? LIVE : r.word === "done" ? '<span class="st g">✓</span>'
        : `<span class="st ${r.word === "waiting" ? "q" : tone(s)}">${r.word === "waiting" ? "○" : s.symbol}</span>`;
      return `<div class="arow">${m}<span class="nm">${esc(r.nm)}${r.verdict ? " " + esc(r.verdict) : ""}</span><span class="m">${esc(r.word)}${r.model ? " · " + esc(alias(r.model)) : ""}</span>
        <span class="m">${r.steps} steps</span><span class="m c">${r.cost == null ? "&ndash;" : money(r.cost)}</span>
        <span class="last m">${r.last ? `${hms(r.last.ts)} <span>${esc(r.last.tool)} ${esc(r.last.what)}</span>` : "no step yet"}</span></div>`;
    }).join("")}</div>`;
  } else if (wanted === "timeline") {
    const act = s.activity, base = tlBase(), at = (k) => (base + k) * 60;
    if (tlMin < base || tlMin > base + 29) tlMin = base + Math.max(0, act.findLastIndex((v) => v > 0));  // the cells move on by themselves
    const sel = tlMin - base, inMin = newest.filter((x) => Math.floor(x.ts / 60) === tlMin);
    body = `<div class="tl"><div class="hd"><span class="lbl">Last 30 min</span><span class="m">1 cell = 1 min</span></div>
      <div class="mins" role="group" aria-label="Steps per minute">${act.map((v, k) => {
        const n = newest.filter((x) => Math.floor(x.ts / 60) === base + k).length, what = `${hhmm(at(k))}, ${n} step${n === 1 ? "" : "s"}`;
        return `<button data-min="${k}" aria-pressed="${k === sel}" tabindex="${k === sel ? 0 : -1}" aria-label="${what}" title="${what}"><i class="${v ? "l" + v : ""}"></i></button>`;
      }).join("")}</div>
      <div class="scale"><span>${hhmm(at(0))}</span><span>${hhmm(at(15))}</span><span>${hhmm(at(29))}</span></div>
      <div class="hd at"><span class="lbl">${hhmm(at(sel))} · ${inMin.length} step${inMin.length === 1 ? "" : "s"}</span><span class="m">← → other minutes</span></div>
      ${inMin.length ? `<div class="log">${inMin.map((x) => logRow(x, "", stepTag(s)(x))).join("")}</div>` : '<p class="none">No step in this minute.</p>'}</div>`;
  } else {
    const turns = chat.items.filter((i) => i.role !== "tool");
    const foot = chat.source === "window"
      ? "Streamed from this window run." + (chat.start_commit ? ` start ${esc(chat.start_commit.slice(0, 7))} · ${chat.changed == null ? "?" : chat.changed} file(s) changed since.` : "")
      : `Read from the ${esc(s.source === "?" ? "chat" : s.source)} transcript, in words; tool output stays in Steps.`;
    body = `<div class="chat">${turns.map((i) => `<div class="turn ${i.role}"><span class="lbl">${i.role === "you" ? "You" : i.role === "claude" ? "Claude" : esc(i.role)}${i.ts ? " · " + hhmm(i.ts) : ""}</span>
      <p>${esc(i.text)}</p></div>`).join("") || '<p class="none">Nothing to show yet. A VS Code or terminal chat shows its turns once a prompt has named its transcript.</p>'}
      <p class="src">${foot}</p></div>`;
  }
  const html = `<div class="tabs" role="tablist" aria-label="Process">${TABS.map(([id, nm]) =>
    `<button role="tab" id="tab-${id}" data-tab="${id}" aria-selected="${wanted === id}" aria-controls="pane" tabindex="${wanted === id ? 0 : -1}">${nm}${id === "agents" ? ` <span class="n">${rows.length}</span>` : ""}</button>`).join("")}</div>
    <div class="pane" id="pane" role="tabpanel" aria-labelledby="tab-${wanted}" tabindex="0">${body}</div>`;
  const key = s.id + "|" + wanted;
  setHtml($("proc"), html, { sel: ".pane", end: wanted === "chat", reset: key !== procShown });
  procShown = key;
}

async function renderLevers(s) {
  const sig = [s.id, s.window, s.run_live, s.stop_question, s.state, s.verdict, s.escalated,
               s.handoff_hint, s.forks.length, Math.floor((snap.now - s.last_ts) / 600)].join("|");  // the last one: idle turns cold
  if (sig === leversSig) return;
  leversSig = sig;
  cold = null;
  const lv = s.run_live ? null : await api("/api/levers?session=" + encodeURIComponent(s.id)).catch(() => null);
  if (openId !== s.id || leversSig !== sig) return;
  cold = lv && !lv.continue ? lv.cold : null;
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
  if (lv && s.project_dir) {  // a new task that takes over: built here from the transcript, no model call
    buttons += `<button class="btn${cold ? " go" : ""}" data-act="brief" title="A new task with the goal, the last message, the edited files and the git status of this one">Brief a new task</button>`;
    if (cold) buttons += '<button class="btn" data-act="vbrief" title="The Verify text plus the same facts, in a new task">Verify in a new task</button>';
  }
  if (buttons) html += `<div class="lr">${buttons}</div>`;
  if (cold) html += `<div class="say">Cold cache: ${kTokens(cold.tokens)} tokens, idle ${Math.round(cold.idle_s / 3600)} h. Continue, Verify, Hand off and Escalate re-read them at full price, about $${money(cold.cost)} (a second click confirms). A new task with a brief costs almost nothing.</div>`;
  let off = "";
  if (lv && lv.continue) off = "Levers off: " + lv.continue;
  else if (lv && lv.handoff) off = "Hand off is off: " + lv.handoff;
  if (lv && !lv.continue && s.verdict === "FAIL" && lv.escalate) off += (off ? " · " : "") + "Escalate is off: " + lv.escalate;
  html += `<div class="say">${esc(off)}</div><div id="f-msg" class="say"></div>`;
  setHtml($("levers"), html);
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
  const typed = name === "answer" ? $("answer") : name === "continue" ? $("fu") : null;
  if (typed && !typed.value.trim()) return;  // nothing to send: no cost to confirm
  if (cold && GUARDED.includes(name) && !button.dataset.armed) {  // two clicks: a cold cache re-reads the context at full price
    button.dataset.armed = "1";
    button.dataset.label = button.textContent;
    button.textContent = `Re-read ~$${money(cold.cost)}? Click again`;
    clearTimeout(coldTimer);
    coldTimer = setTimeout(() => { delete button.dataset.armed; button.textContent = button.dataset.label; }, 4000);
    return;
  }
  const confirm = Boolean(button.dataset.armed);
  const msg = name === "answer" || (name === "terminal" && $("a-msg")) ? $("a-msg") : $("f-msg");
  button.disabled = true;
  try {
    let r = null;
    if (name === "brief" || name === "vbrief") {  // pre-fill the new-task box; Fred edits it and runs it
      const b = await api("/api/brief?session=" + encodeURIComponent(s.id) + (name === "vbrief" ? "&kind=verify" : ""));
      pick(b.project_dir);
      showPage("list");
      draft = b.text;
      $("c-prompt").value = draft;
      saveDraft();
      renderCompose();
      $("c-prompt").focus();
      button.disabled = false;
      return;
    }
    if (name === "stop") { button.textContent = "Stopping ..."; await api("/api/stop", { session: s.id }); }
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (name === "resume") r = await api("/api/continue", { session: s.id, text: RESUME_TEXT, confirm });
    if (name === "continue" || name === "answer") {
      const text = $(name === "answer" ? "answer" : "fu").value.trim();
      if (!text) { button.disabled = false; return; }
      r = await api("/api/continue", { session: s.id, text, confirm });
    }
    if (["verify", "handoff", "escalate"].includes(name)) r = await api("/api/" + name, { session: s.id, confirm });
    if (r && r.session !== s.id) { openSession(r.session, "chat"); return; }  // a window copy (fork)
    if (r) tab = "chat";
    leversSig = "";  // redraw from the next snapshot
  } catch (e) {
    button.disabled = false;
    if (msg) msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

function step(d) {  // ‹ › and Up / Down: the neighbouring session in the list's order
  const nav = navList(), k = nav.findIndex((x) => x.id === openId), to = nav[k + d];
  if (k >= 0 && to) { openSession(to.id, tab); }
}

// -- usage page (BRAINSTORM D13): cost and tokens per day, week and month from every transcript ------------
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MON_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];
const WDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000];  // one column cell: $ or M tokens
let usage = null;        // /api/usage
let uMonth = "";         // the calendar's month, YYYY-MM
let uPicked = "";        // the picked day, YYYY-MM-DD
let uRange = "days";     // days | weeks | months
let uMetric = "cost";    // cost | tok
let usageTimer = null;
function dkey(d) { return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`; }
function ddate(k) { const [y, m, d] = k.split("-").map(Number); return new Date(y, m - 1, d || 1); }
function addDays(k, n) { const d = ddate(k); d.setDate(d.getDate() + n); return dkey(d); }
function dayName(k) { const d = ddate(k); return `${WDAY[d.getDay()]} ${d.getDate()} ${MON[d.getMonth()]}`; }
function usd(v) { return v >= 1000 ? "$" + Math.round(v).toLocaleString("en-US") : "$" + money(v); }
function tokText(n) {
  if (n >= 1e9) return (n / 1e9).toFixed(n >= 1e10 ? 0 : 1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e8 ? 0 : 1) + "M";
  return n >= 1e3 ? Math.round(n / 1e3) + "K" : String(n || 0);
}
function uCost(k) { const d = usage.days[k]; return d ? d.cost : 0; }
function uTok(k) { const d = usage.days[k]; return d ? d.tokens.reduce((a, b) => a + b, 0) : 0; }
function uSum(from, to) {  // inclusive days
  let cost = 0, tok = 0, used = 0;
  for (let k = from; k <= to; k = addDays(k, 1)) {
    if (!usage.days[k]) continue;
    cost += uCost(k); tok += uTok(k); used++;
  }
  return { cost, tok, used };
}
function uLimit() { return usage.limit > 0 ? usage.limit : 15; }
function uTone(c) { const L = uLimit(); return !c ? "" : c < L ? "l1" : c < 3 * L ? "l2" : c < 6 * L ? "l3" : "l4"; }
function monthEnd(m) { const d = ddate(m + "-01"); return dkey(new Date(d.getFullYear(), d.getMonth() + 1, 0)); }

async function loadUsage() {
  try { usage = await api("/api/usage"); } catch (e) { usage = { error: e.message }; }
  if (usage.today && !uMonth) { uMonth = usage.today.slice(0, 7); uPicked = usage.today; }
  renderUsage();
}

function usageHead() {
  const first = uMonth + "-01", end = monthEnd(uMonth), to = end < usage.today ? end : usage.today, s = uSum(first, to);
  const wk = uSum(addDays(usage.today, -((ddate(usage.today).getDay() + 6) % 7)), usage.today);
  let over = 0;
  for (let k = first; k <= to; k = addDays(k, 1)) if (usage.limit > 0 && uCost(k) >= usage.limit) over++;
  const fig = (label, value, under) => `<span><small>${label}</small><b>${value}</b><i>${under}</i></span>`;
  const firstMonth = (usage.first || usage.today).slice(0, 7), d = ddate(first);
  return `<div class="uhead"><span class="big"><span class="est">~</span>${s.cost >= 1000 ? Math.round(s.cost) : money(s.cost)}</span>
      <span class="mon"><button class="rb" id="u-prev" data-umonth="-1" aria-label="Previous month"${uMonth <= firstMonth ? " disabled" : ""}>&#8249;</button>
        <b>${MON_LONG[d.getMonth()]} ${d.getFullYear()}</b>
        <button class="rb" id="u-next" data-umonth="1" aria-label="Next month"${uMonth >= usage.today.slice(0, 7) ? " disabled" : ""}>&#8250;</button></span>
      <span class="sub m">est. USD · ${tokText(s.tok)} tokens · ${s.used} ${s.used === 1 ? "day" : "days"} used</span></div>
    <div class="ustats">${fig("today", usd(uCost(usage.today)), tokText(uTok(usage.today)) + " tok")}
      ${fig("this week", usd(wk.cost), tokText(wk.tok) + " tok")}
      ${fig("avg / day", usd(s.used ? s.cost / s.used : 0), "days used")}
      ${usage.limit > 0 ? fig(`over $${usage.limit}`, `${over} of ${s.used}`, "days used") : fig("days used", String(s.used), "no limit")}</div>`;
}

function usageCalendar() {
  const d = ddate(uMonth + "-01"), lead = (d.getDay() + 6) % 7, n = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  const L = uLimit();
  let html = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map((w) => `<span class="wd">${w}</span>`).join("") + "<span></span>".repeat(lead);
  for (let i = 1; i <= n; i++) {
    const k = `${uMonth}-${two(i)}`, c = uCost(k);
    if (k > usage.today || !usage.first || k < usage.first) {
      html += `<button class="day ${k > usage.today ? "fut" : "na"}" disabled${k > usage.today ? "" : ' title="No transcript left for this day"'}><span>${i}</span></button>`;
      continue;
    }
    const tip = `${dayName(k)}|${c ? `${usd(c)} · ${tokText(uTok(k))} tokens` : "no use"}`;
    html += `<button class="day ${uTone(c)}${k === usage.today ? " now" : ""}" id="ud-${k}" data-day="${k}" data-tip="${esc(tip)}"
      aria-pressed="${k === uPicked}" aria-label="${esc(tip.replace("|", ": "))}"><span>${i}</span>${c ? `<span class="dc">$${Math.round(c)}</span>` : ""}</button>`;
  }
  return `<div class="ublk"><div class="hd"><span class="lbl">Days</span><span class="legend"><span><i class="l1"></i>&lt; $${L}</span>
      <span><i class="l2"></i>&lt; ${3 * L}</span><span><i class="l3"></i>&lt; ${6 * L}</span><span><i class="l4"></i>${6 * L}+</span></span></div>
    <div class="cal">${html}</div></div>`;
}

function usageDay() {
  const r = usage.days[uPicked], head = `<div class="hd"><b>${dayName(uPicked)}${uPicked === usage.today ? " · today" : ""}</b>`;
  if (!r) return `<div class="ublk"><div class="dayd">${head}<span class="m">$0.00</span></div><p class="none">No Claude Code use this day.</p></div></div>`;
  const projects = Object.entries(r.projects).filter(([, c]) => c >= 0.005).sort((a, b) => b[1] - a[1]);
  const top = projects.length ? projects[0][1] : 1;
  const fams = Object.entries(r.models).filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1])
    .map(([f, c]) => `<span>${esc(f)} ${r.cost ? Math.round(100 * c / r.cost) : 0} %</span>`).join("");
  const tk = (label, n) => `<span><small>${label}</small><b>${tokText(n)}</b></span>`;
  return `<div class="ublk"><div class="dayd">${head}<span class="m">~${usd(r.cost)}</span></div>
    <div class="tok">${tk("input", r.tokens[0])}${tk("output", r.tokens[1])}${tk("cache write", r.tokens[2])}${tk("cache read", r.tokens[3])}</div>
    <div class="uprj">${projects.map(([p, c]) => {
      const n = Math.max(1, Math.round(30 * c / top));
      return `<div class="urow"><span class="nm" title="${esc(p)}">${esc(p)}</span><span class="cells">${cellsHtml(Array.from({ length: 30 }, (_, k) => k < n ? "f" : ""))}</span><span class="c m">${usd(c)}</span></div>`;
    }).join("")}</div>
    <div class="legend">${fams}</div></div></div>`;
}

function usageBuckets() {  // one column each, oldest first
  const tok = uMetric === "tok", first = usage.first || usage.today;
  if (uRange === "days") {
    return Array.from({ length: 30 }, (_, j) => {
      const k = addDays(usage.today, j - 29), d = ddate(k);
      return { k, na: k < first, c: uCost(k), t: uTok(k), v: tok ? uTok(k) : uCost(k), label: dayName(k), short: `${d.getDate()} ${MON[d.getMonth()]}` };
    });
  }
  if (uRange === "weeks") {
    return usage.weeks.map((w) => {
      const d = ddate(w.start), short = `${d.getDate()} ${MON[d.getMonth()]}`;
      return { k: w.start, na: addDays(w.start, 6) < first, c: w.cost, t: w.tokens, v: tok ? w.tokens : w.cost, label: "week of " + short, short };
    });
  }
  return usage.months.map((m) => {
    const d = ddate(m.month + "-01");
    return { k: m.month, na: m.month < first.slice(0, 7), c: m.cost, t: m.tokens, v: tok ? m.tokens : m.cost,
      label: `${MON_LONG[d.getMonth()]} ${d.getFullYear()}`, short: MON[d.getMonth()] };
  });
}

function usageChart() {
  const b = usageBuckets(), tok = uMetric === "tok", unit = tok ? 1e6 : 1;
  const max = Math.max(...b.map((x) => x.v)), step = STEPS.map((s) => s * unit).find((s) => max / s <= 20) || STEPS[STEPS.length - 1] * unit;
  const cols = b.map((x) => {
    const tip = `${x.label}|${x.na ? "before the first transcript" : `${usd(x.c)} · ${tokText(x.t)} tokens`}`;
    if (x.na) return `<button class="col na" disabled data-tip="${esc(tip)}" aria-label="${esc(tip.replace("|", ": "))}"></button>`;
    const full = Math.floor(x.v / step), part = x.v - full * step > 0 ? 1 : 0;
    const on = uRange === "days" ? x.k === uPicked : uRange === "months" ? x.k === uMonth : false;
    return `<button class="col" id="uc-${x.k}" data-col="${x.k}" data-tip="${esc(tip)}" aria-pressed="${on}" aria-label="${esc(tip.replace("|", ": "))}">${"<i></i>".repeat(full)}${part ? '<i class="l2"></i>' : ""}</button>`;
  }).join("");
  const lim = uRange === "days" && !tok && usage.limit > 0
    ? `<div class="lim" style="bottom:${(usage.limit / step) * 6 - 1}px"><span>limit $${usage.limit}</span></div>` : "";
  const top = b.reduce((a, x) => x.v > a.v ? x : a, b[0]), mid = b[Math.floor(b.length / 2)];
  const tabs = [["days", "Days"], ["weeks", "Weeks"], ["months", "Months"]].map(([k, l]) =>
    `<button role="tab" id="ur-${k}" data-range="${k}" aria-selected="${uRange === k}">${l}</button>`).join("");
  return `<div class="ublk"><div class="tabs" role="tablist">${tabs}
      <span class="seg"><button id="um-cost" data-metric="cost" aria-pressed="${!tok}">$</button><button id="um-tok" data-metric="tok" aria-pressed="${tok}">tokens</button></span></div>
    <div class="plot" style="grid-template-columns:repeat(${b.length}, minmax(0, 1fr))">${cols}${lim}</div>
    <div class="scale"><span>${b[0].short}</span><span>${mid.short}</span><span>${uRange === "days" ? "today" : b[b.length - 1].short}</span></div>
    <div class="hd"><span class="m mut">1 cell = ${tok ? tokText(step) + " tokens" : "$" + step}</span>
      <span class="m mut">${top.v ? `top ${tok ? tokText(top.v) : usd(top.v)}, ${uRange === "days" ? top.label : top.short}` : ""}</span></div></div>`;
}

function renderUsage() {
  if (page !== "usage") return;
  $("utip").hidden = true;
  if (!usage || usage.error || !usage.ready) {
    const text = usage && usage.error ? `The service did not answer: ${usage.error}` : "Reading every transcript, a few seconds the first time";
    setHtml($("uscroll"), `<div class="empty"><span class="loading"><span class="cells">${cellsHtml(["f", "", "", "", "", ""])}</span>${esc(text)}</span></div>`);
    if (usage && !usage.error && !usage.ready) setTimeout(() => { if (page === "usage") loadUsage(); }, 2000);
    return;
  }
  const since = usage.first ? dayName(usage.first) : "today";
  setHtml($("uscroll"), usageHead() + usageCalendar() + usageDay() + usageChart()
    + `<p class="ufoot">Estimated from the transcripts at the list prices in config.json, fast mode 2x. Kept from ${esc(since)}:
       Claude Code deletes transcripts after 30 days, so the service keeps each closed day in usage-days.json.</p>`);
}

function showTip(el) {
  const tip = $("utip"), [a, b] = el.dataset.tip.split("|");
  tip.innerHTML = `${esc(a)}<small>${esc(b)}</small>`;
  tip.hidden = false;
  const w = $("open").getBoundingClientRect(), r = el.getBoundingClientRect();
  tip.style.left = Math.min(Math.max(4, r.left - w.left + r.width / 2 - tip.offsetWidth / 2), w.width - tip.offsetWidth - 4) + "px";
  tip.style.top = Math.max(40, r.top - w.top - tip.offsetHeight - 6) + "px";
}
function moveMonth(n) { const d = ddate(uMonth + "-01"); d.setMonth(d.getMonth() + n); uMonth = dkey(d).slice(0, 7); renderUsage(); }
$("uscroll").addEventListener("click", (e) => {
  const t = e.target.closest("[data-day],[data-col],[data-range],[data-metric],[data-umonth]");
  if (!t || t.disabled) return;
  if (t.dataset.day) uPicked = t.dataset.day;
  else if (t.dataset.col && uRange === "days") { uPicked = t.dataset.col; uMonth = uPicked.slice(0, 7); }
  else if (t.dataset.col && uRange === "months") uMonth = t.dataset.col;
  else if (t.dataset.range) uRange = t.dataset.range;
  else if (t.dataset.metric) uMetric = t.dataset.metric;
  else if (t.dataset.umonth) return moveMonth(Number(t.dataset.umonth));
  renderUsage();
});
$("uscroll").addEventListener("pointerover", (e) => { const el = e.target.closest("[data-tip]"); if (el) showTip(el); else $("utip").hidden = true; });
$("uscroll").addEventListener("pointerleave", () => { $("utip").hidden = true; });
$("uscroll").addEventListener("focusin", (e) => { const el = e.target.closest("[data-tip]"); if (el) showTip(el); else $("utip").hidden = true; });
$("uscroll").addEventListener("scroll", () => { $("utip").hidden = true; });

// -- events ------------------------------------------------------------------------------
async function go(name, button) {
  if (name === "list") showPage("list");
  if (name === "new") { if (form === "pill") await setForm("open"); showPage("list"); $("c-prompt").focus(); }
  if (name === "needs") {
    if (scope) pick("");
    const n = $("needsec");
    if (n) n.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  if (name === "moredone") { doneOpen = true; render(); }
  if (name === "usage") showPage("usage");
  if (name === "fold") await setForm("pill");
  if (name === "unfold") await setForm("open");
  if (name === "allow") allowRuns(button);
  if (name === "retry" && fail) {
    const retry = fail.retry;
    fail = null;
    if (retry === "prep") doPrep();
    else if (retry === "raw") rawRun();
    else if (retry === "allow") allowRuns(null);
    else renderCompose();
  }
  if (!native()) return;
  if (name === "minimize") window.pywebview.api.minimize();
  if (name === "close") window.pywebview.api.close();
  if (name === "ontop") { onTop = await window.pywebview.api.on_top(!onTop); renderOnTop(); }
}

function rawRun() {
  const text = $("c-prompt").value.trim();
  if (text && runnable()) doRun(project, text, cfg.default_model, cfg.default_effort, "");
}

document.addEventListener("click", (e) => {
  if (!$("pop").hidden && !e.target.closest("#pop") && !e.target.closest("[data-pick]")) closePicker();
  const t = e.target.closest("[data-go],[data-open],[data-tab],[data-min],[data-act],[data-pact],[data-do],[data-here],[data-proj],[data-pick],[data-step],#brief,#today");
  if (!t) return;
  if (t.matches(".card") && e.target.closest("[data-stay]")) return;  // typing an answer in a card
  if (t.dataset.go) go(t.dataset.go, t);
  else if (t.dataset.do) unblock(t);
  else if (t.dataset.open) openSession(t.dataset.open);
  else if (t.dataset.tab) { tab = t.dataset.tab; const s = current(); if (s) renderProc(s).catch(() => {}); }
  else if (t.dataset.min !== undefined) { tlMin = tlBase() + Number(t.dataset.min); const s = current(); if (s) renderProc(s).catch(() => {}); }
  else if (t.dataset.act) act(t.dataset.act, t);
  else if (t.dataset.pact) prepAct(t.dataset.pact);
  else if (t.dataset.here !== undefined) { pick(t.dataset.here); showPage("list"); $("c-prompt").focus(); }
  else if (t.dataset.proj !== undefined) pick(t.dataset.proj);
  else if (t.dataset.step) step(Number(t.dataset.step));
  else if (t.hasAttribute("data-pick")) { if ($("pop").hidden) openPicker(); else closePicker(); }
  else if (t.id === "brief") {
    briefOpen = !briefOpen;
    t.setAttribute("aria-expanded", String(briefOpen));
    t.querySelector(".car").textContent = briefOpen ? "▴" : "▾";
    $("more").hidden = !briefOpen;
    saveDraft();
  } else if (t.id === "today") {
    const open = t.getAttribute("aria-expanded") !== "true";
    t.setAttribute("aria-expanded", String(open));
    $("todaymore").hidden = !open;
  }
});

document.addEventListener("dblclick", (e) => {
  if (e.target.closest(".pill .sp")) setForm("open");
  else if (e.target.closest(".top .sp")) setForm("pill");
});

document.addEventListener("input", (e) => {
  if (e.target.id === "c-prompt") { draft = e.target.value; fail = null; saveDraft(); renderCompose(); }
});

$("pfind").addEventListener("input", pickRows);
$("pfind").addEventListener("keydown", (e) => {
  const rows = document.querySelectorAll("#prows .prow");
  if (e.key === "ArrowDown") { hi = Math.min(rows.length - 1, hi + 1); markHi(); e.preventDefault(); }
  if (e.key === "ArrowUp") { hi = Math.max(0, hi - 1); markHi(); e.preventDefault(); }
  if (e.key === "Enter" && rows[hi]) { pick(rows[hi].dataset.proj); e.preventDefault(); }
  if (e.key === "Escape") { closePicker(); $("scope").focus(); e.stopPropagation(); }
});

document.addEventListener("keydown", (e) => {
  const id = e.target.id || "";
  if (id === "c-prompt" && e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (e.ctrlKey) rawRun();
    else doPrep();
    return;
  }
  if (id === "fu" && e.key === "Enter") return act("continue", document.querySelector('[data-act="continue"]'));
  if (id === "pk" && e.key === "Enter") return unblock(document.querySelector('[data-do="send"][data-where="peek"]'));
  if (id.startsWith("ca-") && e.key === "Enter") return unblock(e.target.closest("[data-stay]").querySelector('[data-do="send"]'));
  if (e.key === "Enter" && e.target.matches(".card[data-open]")) { e.target.click(); return; }
  if (e.ctrlKey && e.key.toLowerCase() === "n") { e.preventDefault(); go("new"); return; }
  if (e.ctrlKey && e.key.toLowerCase() === "p") { e.preventDefault(); openPicker(); return; }
  const inField = ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
  if (e.key === "Escape") {
    if (!$("pop").hidden) closePicker();
    else if (form === "pill") dismissPeek();
    else if (page === "prep") prepAct("cancel");
    else if (page === "session" || page === "usage") showPage("list");
    return;
  }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const d = e.key === "ArrowRight" ? 1 : -1, s = current();
    if (e.target.matches("[data-tab]") && s) {
      tab = TABS[(TABS.findIndex(([k]) => k === tab) + d + TABS.length) % TABS.length][0];
      renderProc(s).then(() => { const f = $("tab-" + tab); if (f) f.focus(); }).catch(() => {});
      e.preventDefault();
    } else if (e.target.matches("[data-min]") && s) {
      tlMin = Math.min(tlBase() + 29, Math.max(tlBase(), tlMin + d));
      renderProc(s).then(() => { const f = document.querySelector(`[data-min="${tlMin - tlBase()}"]`); if (f) f.focus(); }).catch(() => {});
      e.preventDefault();
    }
    return;
  }
  if ((e.key === "ArrowUp" || e.key === "ArrowDown") && page === "session" && form === "open" && !inField
      && !e.target.closest("#pane")) {
    step(e.key === "ArrowDown" ? 1 : -1);
    e.preventDefault();
  }
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
  es.onerror = () => { live = false; if (snap) $("banner").hidden = false; };
}

(async () => {
  const buttons = `<button class="rb on native-only" data-go="ontop" title="Always on top (on)" aria-label="Always on top">&#8868;</button>
    <button class="rb" data-go="fold" title="Fold to pill (double-click this bar)" aria-label="Fold to pill">&#8963;</button>
    <button class="rb native-only" data-go="minimize" aria-label="Minimize">&ndash;</button>
    <button class="rb x native-only" data-go="close" aria-label="Close" title="Close window (runs keep going)">&#10005;</button>`;
  document.querySelectorAll("[data-winbtns]").forEach((el) => { el.innerHTML = buttons; });
  try { cfg = await api("/api/config"); } catch (e) { cfg = null; }
  try { draft = (await api("/api/draft")).text; } catch (e) { /* no draft */ }
  $("c-prompt").value = draft;
  project = (cfg && cfg.project) || "";
  briefOpen = !!(cfg && cfg.brief);
  connect();
})();
