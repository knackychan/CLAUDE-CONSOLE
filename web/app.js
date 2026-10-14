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
const PEEK = new Set(["stop", "blocked", "failed", "interrupted", "verify_failed"]);  // a new one opens the peek card
const SPEND_CELL = 0.5;   // 1 spend cell = $0.50
const PILL_CHIPS = 9;
const DONE_SHOWN = 2;     // done sessions listed before "Show N more"
const TABS = [["chat", "Chat"], ["steps", "Steps"], ["agents", "Agents"], ["timeline", "Timeline"]];
const EFF_LEVELS = ["auto", "low", "medium", "high", "xhigh", "max"];  // the slider's values, in order
const TASK_WORD = { planned: ["Task", "n"], running: ["Task", "n"], waiting: ["Waiting", "y"],
  stuck: ["Stuck", "r"], done: ["Done", "g"], stopped: ["Stopped", "q"], handed: ["Handed off", "y"],  // [word, tone]
  handing: ["Handing off", "n"], handed_no_note: ["Handed off", "q"] };  // handed: the note is in, the next task is Fred's
const SESSION_SPRITE = { running: "running", stop: "waiting", blocked: "stuck", done: "done" };  // session state -> sprite

const px = (tone, ...rows) => rows.join("").split("").map((c) => (c === "x" ? tone : ""));  // one class per cell, "" is an off cell
const QMARK = px("y", ".xxx.", "x...x", "...x.", ".....", "..x..");  // the dot is the last cell: the second frame has it off
// Running: a sliding puzzle. Eight tiles of three shades and one hole; the hole walks through the board (every step is next to the
// last), then the walk is played back, so the 16 frames loop without a jump.
const BOARD = ["l4", "l2", "l3", "l3", "l4", "l2", "l2", "l3", ""];  // 3 x 3, row-major; the hole is the last cell
const HOLE_WALK = [8, 7, 4, 3, 0, 1, 2, 5, 8];
function slideFrames() {
  const b = BOARD.slice(), states = [b.slice()];
  for (let k = 1; k < HOLE_WALK.length; k++) {
    b[HOLE_WALK[k - 1]] = b[HOLE_WALK[k]];
    b[HOLE_WALK[k]] = "";
    states.push(b.slice());
  }
  return states.concat(states.slice(1, -1).reverse());
}
const SPRITE = {  // grid (5 by default), ms per frame, frames as one class per cell
  running: { grid: 3, step: 100, frames: slideFrames() },
  waiting: { step: 250, frames: [QMARK, QMARK.slice(0, -1).concat("")] },
  paused: { frames: [px("f", ".x.x.", ".x.x.", ".x.x.", ".x.x.", ".x.x.")] },
  stopped: { frames: [px("q", ".....", ".xxx.", ".xxx.", ".xxx.", ".....")] },
  stuck: { frames: [px("r", "x...x", ".x.x.", "..x..", ".x.x.", "x...x")] },
  done: { frames: [px("g", ".....", "....x", "...x.", "x.x..", ".x...")] },
  handed: { frames: [px("y", "..x..", "...x.", "xxxxx", "...x.", "..x..")] },  // an arrow: on to the next task
  handed_no_note: { frames: [px("q", "..x..", "...x.", "xxxxx", "...x.", "..x..")] },
  planned: { frames: [Array.from({ length: 25 }, (_, k) => (k === 12 ? "l2" : ""))] },
};
function sprite(name, flip = false) {
  const sp = SPRITE[name];
  if (!sp) return "";
  const n = sp.frames.length;
  const fr = sp.frames.map((cls, k) => `<span class="cells fr" style="--k:${k}">${cls.map((c) => `<i${c ? ` class="${c}"` : ""}></i>`).join("")}</span>`).join("");
  return `<span class="spr${sp.grid === 3 ? " g3" : ""}${n > 1 ? " anim n" + n : ""}${flip ? " flip" : ""}" style="--s:${sp.step || 0}ms" aria-hidden="true">${fr}</span>`;
}

const lastSeen = new Map(), freshUntil = new Map();
function fresh(kind, id, value, ms) {  // true for ms after value changed from a value painted before; never on the first paint
  const key = kind + id, was = lastSeen.get(key), now = Date.now();
  lastSeen.set(key, value);
  if (was !== undefined && was !== value) freshUntil.set(key, now + ms);
  return (freshUntil.get(key) || 0) > now;
}
const taskSprite = (t) => (t.owner === "fred" && (t.state === "running" || t.state === "waiting") ? "paused" : t.state === "handing" ? "running" : t.state);
const sessionMark = (s, glyph, tn) => {  // the sprite of a session state, or its glyph (a finished session with a FAIL verdict keeps its x)
  const name = SESSION_SPRITE[s.state];
  return !name || (name === "done" && tn !== "g") ? glyph + " " : sprite(name, fresh("f", "s" + s.id, s.state, 240));
};
const taskMark = (t) => sprite(taskSprite(t), fresh("f", "t" + t.id, t.state, 240));
const enterClass = (id, needs) => (fresh("n", id, needs ? "needs" : "", 600) && needs ? " enter" : "");  // the card flashes when it enters Needs you

let snap = null;
let cfg = null;          // /api/config
let live = false;
let form = "open";       // open | pill
let page = "list";       // list | session | prep | task | usage
let openId = null;
let taskId = null;       // the Task page's task
let taskData = null;     // GET /api/task for it: {task, levers, note, brief}
let taskSig = "";
let backTo = null;       // {page: "task", id} or {page: "session", id}: where the session or Task page's back arrow returns
let rawOpen = false;     // the Task page shows the raw note instead of the brief
const foldState = new Map(); // plan 23: fold label -> open, kept across redraws (Handoff, its headings, Facts, Window runs); closed on openTask
let settingBusy = false; // POST /api/setting in flight (the Window runs switch)
let settingErr = "";
let planOpen = new Set(); // the Task page's open plan folds (plan 24); closed on openTask
let planEdit = false;    // the plan askbox shows the editor
let planEditPart = 0;    // which text the editor holds: 0 the index, k part k
let tab = "chat";       // chat | steps | agents | timeline
let tlMin = -1;          // the Timeline's selected minute (minutes since 1970; -1: the last busy one)
let scope = "";          // the project folder the list shows ("" = all projects)
let project = "";        // where a new task runs (window.json, through /api/draft)
let effortPick = "auto"; // the slider: auto (the rules pick per step) or one level for every step (window.json)
let card = null;        // the Prep card on screen
let reviewCard = null;  // the rules review on screen (plan 22); it uses the Prep page section
let busy = "";           // what the compose box waits for ("" = nothing)
let fail = null;         // {title, msg, retry} shown above the compose box
let draft = "";
let draftKept = false;   // the box holds a draft from an earlier load: marked until typed over or cleared
let briefOpen = false;   // the session page's brief, open for the window (window.json)
let doneOpen = false;
let emptyOpen = false;
let hi = 0;              // the picker's highlighted row
let draftTimer = null;
let movedAt = 0;         // when the task target last changed project: its chip is marked for 4 s
let onTop = true;
let peekKey = "";        // the event the peek card shows
let firstSnap = true;
let procSeq = 0;         // the newest process render; older ones are dropped
let procShown = "";      // session|tab the process pane shows now
let leversSig = "";
let cold = null;        // {idle_s, tokens, cost} when a lever would re-read the open session at full price
let coldTimer = null;
let freshHandoff = false;  // Hand off after a PASS starts a new chat from a brief: it re-reads nothing
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
const RUNG = /^(claude|codex|opencode|cmd):/;  // a rung "harness:model"; a string with no such prefix is a Claude rung
function splitRung(rung) { const m = String(rung || "").match(/^(claude|codex|opencode|cmd):(.*)$/s); return m ? [m[1], m[2]] : ["claude", String(rung || "")]; }
function rungOf(harness, model) { return harness && harness !== "claude" && model && !RUNG.test(model) ? harness + ":" + model : model || ""; }
function alias(model) {  // "" for a harness rung, as claude_cli.model_alias does: an OpenCode id may contain "sonnet"
  if (RUNG.test(String(model || ""))) return "";
  return (String(model || "").match(/fable|opus|sonnet|haiku/) || [model || ""])[0];
}
function label(s) {
  if (s.auto_handoff && s.handoff_by) return "Handed off";  // plan 23: the service handed it off at red
  return s.state === "stop" ? "Asks you" : s.text;
}
function tone(s) {  // orange only for "needs you", red and green only for state
  if (s.state === "blocked" || s.state === "failed" || s.state === "verify_failed") return "r";
  if (s.group === "needs") return "y";
  if (s.state === "done" || s.state === "verified") return "g";
  return s.state === "running" || s.state === "replied" ? "n" : "q";
}
function stateWord(s) {  // [glyph, word, tone]; a finished session says its verdict
  if (s.group === "done" && s.state !== "verified" && s.verdict === "PASS") return ["✓", "PASS", "g"];
  if (s.group === "done" && s.verdict === "FAIL") return ["×", "FAIL", "r"];
  return [s.symbol, label(s), tone(s)];
}
function cellsHtml(classes) { return classes.map((c) => `<i${c ? ` class="${c}"` : ""}></i>`).join(""); }
function liveSessions() { return snap ? snap.sessions.filter((s) => s.group !== "done" && s.group !== "empty")
  .sort((a, b) => (a.group === "needs" ? 0 : 1) - (b.group === "needs" ? 0 : 1)) : []; }
function current() { return snap && snap.sessions.find((s) => s.id === openId); }
function routeText(s) {
  const run = [s.harness && s.harness !== "claude" ? s.harness + " · " + s.model : alias(s.model), s.effort].filter(Boolean).join(" ");
  if (s.route === "unrouted") return run ? "unrouted · " + run : "unrouted";
  return run ? s.route + " · " + run : s.route;
}
function version(model) {  // claude-opus-4-8 -> "4.8", claude-haiku-4-5-20251001 -> "4.5"; an alias, an unversioned name or a harness rung -> ""
  if (RUNG.test(String(model || ""))) return "";
  const m = String(model || "").match(/(?:fable|opus|sonnet|haiku)-(\d+)(?:-(\d{1,2}))?(?=[-[]|$)/);  // a date or [1m] may follow
  return m ? m[1] + (m[2] ? "." + m[2] : "") : "";
}
function modelText(model, effort) {  // an alias shows the newest version the service has seen (snap.versions)
  if (RUNG.test(String(model || ""))) { const [h, m] = splitRung(model); return [h, m, effort].filter(Boolean).join(" · "); }
  const fam = alias(model), v = version(model) || (fam === model && snap && snap.versions ? snap.versions[fam] || "" : "");
  return [v ? fam + " " + v : fam, effort].filter(Boolean).join(" ");
}
function fableName() { return snap && snap.versions && snap.versions.fable ? "Fable " + snap.versions.fable : "Fable"; }
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
  for (const k of ["tab", "min", "open", "eff"]) if (el.dataset[k] !== undefined) return `[data-${k}="${el.dataset[k]}"]`;
  return "";
}
function setHtml(el, html, scroller) {
  if (el._html === html) return false;
  const picked = getSelection();  // text being selected stays put; the next snapshot swaps it in
  if (picked && !picked.isCollapsed && el.contains(picked.anchorNode)) return false;
  const active = document.activeElement, key = active && el.contains(active) ? focusKey(active) : "";
  const fields = [...el.querySelectorAll("input[id],textarea[id]")].map((f) => [f.id, f.value, f.selectionStart, f.selectionEnd]);
  const old = scroller && el.querySelector(scroller.sel);
  const top = old ? old.scrollTop : 0, atEnd = old ? old.scrollTop + old.clientHeight >= old.scrollHeight - 4 : false;
  el.innerHTML = html;
  el._html = html;
  for (const a of el.getAnimations({ subtree: true }))  // loops (sprites, live cells) run on the page clock: a repaint does not restart them at frame 0
    if (a.effect.getTiming().iterations === Infinity) a.startTime = 0;
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

// -- resize grip: the corner drives WindowApi.resize; the size is kept when the drag ends ------
let grip = null;

async function gripSize(e, keep) {
  const g = grip;
  if (g.busy && !keep) return;  // one resize at a time; the next move carries the latest size
  g.busy = true;
  try { await window.pywebview.api.resize(e.screenX - g.x, e.screenY - g.y, keep); } finally { g.busy = false; }
}

function gripEnd(e) {
  if (!grip) return;
  gripSize(e, true).catch(() => {});
  grip = null;
}

$("rsz").addEventListener("pointerdown", (e) => {
  if (!native() || form !== "open" || e.button !== 0) return;
  e.currentTarget.setPointerCapture(e.pointerId);
  grip = { x: e.screenX - window.innerWidth, y: e.screenY - window.innerHeight, busy: false };
  e.preventDefault();
});
$("rsz").addEventListener("pointermove", (e) => { if (grip) gripSize(e, false).catch(() => {}); });
$("rsz").addEventListener("pointerup", gripEnd);
$("rsz").addEventListener("pointercancel", gripEnd);

// -- drag regions: the cursor moves the window in Python (WindowApi.drag_*), in the form's own pixels ------
let dragging = null;

document.addEventListener("pointerdown", (e) => {
  const region = e.target.closest(".drag-region");
  if (!region || !native() || e.button !== 0) return;
  region.setPointerCapture(e.pointerId);
  dragging = { busy: false };
  window.pywebview.api.drag_start().catch(() => {});
  e.preventDefault();
});
document.addEventListener("pointermove", async (e) => {
  if (!dragging || dragging.busy) return;
  dragging.busy = true;
  try { await window.pywebview.api.drag_move(); } catch (err) { /* the window is closing */ } finally { if (dragging) dragging.busy = false; }
});
const dragEnd = () => { dragging = null; };
document.addEventListener("pointerup", dragEnd);
document.addEventListener("pointercancel", dragEnd);

async function fitPill() {
  if (native() && form === "pill") await window.pywebview.api.form("pill", Math.ceil($("folded").getBoundingClientRect().height));
}

function renderFolded(resize) {
  if (!snap) return;
  const rail = liveSessions(), more = rail.length - PILL_CHIPS;
  $("pill").innerHTML = `<span class="grip drag-region" title="Drag to move">&#8942;&#8942;</span>
    ${rail.slice(0, PILL_CHIPS).map(chip).join("")}${more > 0 ? `<span class="more">+${more}</span>` : ""}
    <span class="sp drag-region" title="Drag to move; double-click to open"></span>
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
  if (s.auto_handoff && s.handoff_by) return "";  // the card draws its own why
  if (s.state === "blocked" && s.denied) return `denied: ${s.denied.tool} ${s.denied.what}`;
  if (s.state === "failed" && s.failed) return `${s.failed.error} ${s.failed.details || ""}`.trim();
  if (s.state === "interrupted") return "The run stopped before it finished.";
  if (s.state === "verify_failed") return ("Verify FAIL " + s.verdict_detail).trim();
  if (s.state === "stall") return `no event for ${ago(snap.now - s.last_ts)}: the chat may be closed`;
  if (s.ctx_tone === "red") return `context ${kTokens(s.ctx_tokens)}: hand off`;
  return "";
}
function needButtons(s, where, withOpen) {
  const b = (name, cls, text) => `<button class="btn${cls} sm" data-do="${name}" data-sid="${esc(s.id)}" data-where="${where}">${text}</button>`;
  let out = "";
  if (s.state === "blocked" && s.window && !s.run_live) out += b("terminal", "", "Open in terminal");
  if (s.state === "interrupted" && s.window) out += b("resume", " you", "Resume");
  if (s.state === "stall" && !s.run_live) out += b("done", "", "Mark done");
  return out + (withOpen ? b("open", "", "Open") : "");
}

function peekCard(s) {
  const t = tone(s), age = `<span class="age m">${ago(snap.now - s.last_ts)}</span>`;
  const head = `<div class="l1"><span class="st ${t}">${sessionMark(s, s.symbol, t)}${esc(label(s))}</span><span class="t">${esc(s.title)}</span>${age}</div>`;
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
    if (name === "next") {  // plan 23 (HANDED OFF card): the box is seeded with the handoff, the card leaves Needs you
      seedBox(await api("/api/brief?session=" + encodeURIComponent(s.handoff_by) + "&kind=next"));
      if (s.auto_handoff) await api("/api/done", { session: s.id });
    }
    if (name === "send") r = await api("/api/continue", { session: s.id, text });
    if (name === "resume") await api("/api/continue", { session: s.id, text: RESUME_TEXT });
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (name === "done") await api("/api/done", { session: s.id });
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
  taskSig = "";
  procShown = "";
  if (name === "session") $("sscroll").scrollTop = 0;
  if (name === "task") $("tscroll").scrollTop = 0;
  clearInterval(usageTimer);
  usageTimer = null;
  if (name === "usage") { $("uscroll").scrollTop = 0; loadUsage(); usageTimer = setInterval(loadUsage, 60000); }
  render();
}

async function openSession(id, list = "chat") {
  if (form === "pill") await setForm("open");
  if (id !== openId) att.answer = att.fu = [];  // files were for the other session's boxes
  openId = id;
  tab = list;
  tlMin = -1;
  const s = current();
  if (s && s.project_dir) project = s.project_dir;
  showPage("session");
}

function inScope(s) { return !scope || s.project_dir === scope; }
function groups() {
  const mine = snap.sessions.filter((s) => inScope(s) && !s.task);  // a step session: its task row is the way in
  const work = mine.filter((s) => s.group === "working");
  const byAge = (g) => mine.filter((s) => s.group === g).sort((a, b) => b.last_ts - a.last_ts);
  return { needs: mine.filter((s) => s.group === "needs"), replied: byAge("replied"), empty: byAge("empty"),
    work: work.filter((s) => BUSY.has(s.state)),
    idle: work.filter((s) => !BUSY.has(s.state)).sort((a, b) => b.last_ts - a.last_ts), done: mine.filter((s) => s.group === "done").sort((a, b) => b.last_ts - a.last_ts) };
}
function stepNav() {  // a task step's session: the task's steps that ran, in order, as {id: last attempt, ids: every attempt}
  const s = current(), old = !s && oldStep(openId), tid = s ? s.task : old ? old[0].id : "";
  const t = tid && ((snap.tasks || []).find((x) => x.id === tid) || (old && old[0]));
  if (!t) return tid ? [] : null;  // a step of a cleared task: no pager, never every session
  return t.steps.filter((x) => x.session).map((x) => ({ id: x.session, ids: (x.attempts || []).map((a) => a.session) }));
}
function navAt(nav) { return nav.findIndex((x) => x.id === openId || (x.ids || []).includes(openId)); }
function navList() {  // the sessions ‹ › step through: the list in its order, or all when the open one is out of scope
  const steps = stepNav();
  if (steps) return steps;
  const g = groups(), all = [...g.needs, ...g.replied, ...g.work, ...g.idle, ...g.done];
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
  else if (page === "task") renderTaskPage();
}

// -- list page ---------------------------------------------------------------------------
function spendRow(sp) {  // 30 cells = $15 soft limit; capped so cells never collapse at high spend
  const all = Math.round(sp.today / SPEND_CELL);
  const mark = sp.budget > 0 ? Math.ceil(sp.budget * 0.8 / SPEND_CELL) - 1 : -1;
  const cls = Array.from({ length: 30 }, (_, k) =>
    [k < all ? "h" : "", k === mark ? "mk" : ""].filter(Boolean).join(" "));
  return { html: cellsHtml(cls) };
}

function renderTop() {
  const n = snap.counts.needs;
  $("needsbtn").hidden = !n;
  $("needsbtn").textContent = `${n} ${n === 1 ? "needs" : "need"} you`;
  $("scopenm").textContent = scope ? projectName(scope) : "All projects";
  const sp = snap.spend, row = spendRow(sp);
  setHtml($("today"), `<span class="big">${money(sp.today)}</span><span class="cells row30">${row.html}</span>
    <span class="sub m"><span>today<span class="usd">, USD</span> · $${money(sp.burn)} / min</span>
    <span>${sp.budget > 0 ? "limit $" + sp.budget : "no limit"}</span></span>`);
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
}

// -- tasks (plan 17): a card in the list, the step tag on its sessions ---------------------------------
function sameDir(a, b) { const n = (p) => String(p || "").replace(/[\\/]+/g, "\\").replace(/\\$/, "").toLowerCase(); return n(a) === n(b); }
function taskGroup(t) { return t.group === "working" ? "work" : t.group; }  // the service decides (task_row), counts read the same
const taskShown = (t) => (t.state === "handed" ? (t.handoff_note ? "handed" : t.group === "working" ? "handing" : "handed_no_note")
  : t.state === "running" && (t.asks || t.hand_off) ? "waiting" : t.state);  // a step's chat waits for Fred
const stepCell = (t, x) => (x.state === "handed" ? (t.state === "handed" && t.handoff_note ? "y" : "q")  // a handed step is not a checked one
  : x.state === "running" ? "f live" : x.state === "failed" || x.verdict === "FAIL" ? "r" : x.state === "done" ? "g" : "");
const handText = (h) => `↻ hand off: ${h}, one task = one chat`;
function taskGroups() {  // the scope's tasks by group; a finished or stopped task leaves the list a day after its last change
  const mine = (snap.tasks || []).filter((t) => !scope || sameDir(t.project_dir, scope));
  const by = (g) => mine.filter((t) => taskGroup(t) === g && (g !== "done" || snap.now - t.updated < 86400));
  return { needs: by("needs"), work: by("work"), done: by("done") };
}
function taskStep(t) { return t.steps.find((x) => x.n === t.current) || t.steps.find((x) => x.state !== "done") || t.steps[0]; }
function taskTag(s) {  // "step 2/4" after the title of a session that runs a task's step
  if (!s.task) return "";
  const t = (snap.tasks || []).find((x) => x.id === s.task);
  return `<span class="tag">step ${s.step}${t ? "/" + t.count : ""}</span>`;
}

function taskCard(t) {
  const [word, tn] = TASK_WORD[taskShown(t)] || TASK_WORD.running, cur = taskStep(t);
  const cells = t.steps.map((x) => stepCell(t, x));
  const live = t.steps.find((x) => x.note === "writing" || x.note === "unchecked" || x.note === "ready");
  const next = t.state === "handed" && t.handoff_note;  // a pending handoff: the next task and the note, one click each
  const ask = (t.asks || t.hand_off) && cur && cur.session;
  const gap = (t.asks || "").startsWith("Plan gap:"), planWhy = /^plan ready: confirm$|^plan .* KB, over /.test(t.why || "");
  const why = t.why === "confirm Fable" ? `${fableName()} may bill usage credits: confirm on the Task page` : t.asks || next ? "" : t.why;
  const third = (why ? `<div class="why m mut">${esc(why)}</div>` : "")
    + (t.asks ? `<div class="q">${esc(t.asks)}</div>` : "") + (t.hand_off ? `<div class="why m y">${esc(handText(t.hand_off))}</div>` : "")
    + (t.briefing ? '<div class="doing m"><span class="cells"><i class="f live"></i></span><span>Haiku is compacting the note</span></div>' : "")
    + (live ? noteChip(live, t) : "")
    + (gap ? `<div class="lr"><button class="btn you sm" data-task="${esc(t.id)}">Answer</button>
      <button class="btn sm" data-tact="redo" data-tid="${esc(t.id)}" title="Runs the design step again with this question">Redo design</button></div>`
      : planWhy ? `<div class="lr"><button class="btn you sm" data-task="${esc(t.id)}">${t.why.startsWith("plan ready") ? "Confirm" : "Accept"}</button></div>`
      : ask ? `<div class="lr"><button class="btn you sm" data-open="${esc(cur.session)}">Open</button></div>` : "")
    + (next ? `<div class="lr"><button class="btn you sm" data-tact="next" data-tid="${esc(t.id)}" title="A new task seeded with the handoff note">Start next task</button>
      <span class="link m" data-task="${esc(t.id)}" title="${esc(t.handoff_note)}">handoff note</span></div>` : "");
  return `<div class="card task${tn === "y" || tn === "r" ? " " + tn : ""}${enterClass("t" + t.id, tn === "y" || tn === "r")}" data-task="${esc(t.id)}" tabindex="0" role="button" aria-label="${esc(word + ": " + t.title)}">
    <div class="l1"><span class="st ${tn}">${taskMark({ ...t, state: taskShown(t) })}${word}</span><span class="t">${esc(t.title)}</span>
    <span class="age m" title="since the last change">${ago(snap.now - t.updated)}</span></div>
    <div class="l2 m"><span class="who">${esc(t.project)} · step ${cur ? cur.n : 1} / ${t.count}${cur ? " · " + esc(cur.kind) : ""}${cur && cur.part ? " · from plan" : ""}${cur && cur.model ? `<span class="route"> · ${esc(modelText(rungOf(cur.harness, cur.model), cur.effort))}</span>` : ""}</span>
    <span class="cost">${money(t.cost)}</span><span class="ctx"><span class="cells" style="--n:${cells.length}">${cellsHtml(cells)}</span></span></div>${third}</div>`;
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
  } else if (s.auto_handoff && s.handoff_by) {  // README 3.7: the service handed it off at red; one task = one chat
    third = `<div class="why m y">↻ ${s.window ? "" : "forked, then "}handed off by itself at ${kTokens(s.auto_handoff)}</div>
      <div class="lr" data-stay><span class="hn ready">✓ handoff ready</span>
      <button class="btn you sm" data-do="next" data-sid="${esc(s.id)}" data-where="card" title="Starts the next chat with the handoff in the task box: one task = one chat (auto hand off, D-5)">Start next chat</button>
      <span class="link m" data-open="${esc(s.handoff_by)}">handoff</span></div>`;
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
  return `<div class="card${t === "y" || t === "r" ? " " + t : ""}${enterClass("s" + s.id, s.group === "needs")}" data-open="${esc(s.id)}" tabindex="0" role="button"
    aria-label="${esc(label(s) + ": " + s.title)}">
    <div class="l1"><span class="st ${t}">${sessionMark(s, s.symbol, t)}${esc(label(s))}${hand}</span><span class="t">${esc(s.title)}</span>${taskTag(s)}
    <span class="age m" title="since the last event">${ago(snap.now - s.last_ts)}</span></div>
    <div class="l2 m"><span class="who">${esc(s.project)}${s.two_writers ? " · 2 writers" : ""}<span class="route"> · ${esc(routeText(s))}</span></span>
    <span class="cost">${spentText(s)}</span>${ctxMini(s)}</div>${third}</div>`;
}

function quietHtml(s, showProject) {
  const [glyph, word, t] = stateWord(s);
  const hand = s.handoff_hint ? ' <span class="st q">· HAND OFF</span>' : "";
  const reply = (s.state === "idle" || s.state === "replied") && s.reply ? `<div class="reply mut" title="${esc(s.reply)}">${esc(s.reply)}</div>` : "";
  return `<div class="card quiet${s.state === "idle" || s.state === "replied" ? " " + s.state : ""}" data-open="${esc(s.id)}" tabindex="0" role="button" aria-label="${esc(word + ": " + s.title)}">
    <div class="l1"><span class="st ${t}">${sessionMark(s, glyph, t)}${esc(word)}${hand}</span><span class="t">${esc(s.title)}${showProject ? ` <span class="m mut">· ${esc(s.project)}</span>` : ""}</span>${taskTag(s)}
    <span class="age m">${s.state === "replied" ? ago(snap.now - s.last_ts) : spentText(s)}</span></div>${reply}</div>`;
}

function renderListPage() {
  renderTop();
  const g = groups(), tk = taskGroups();  // a group's tasks come first, then its sessions
  const doneRows = [...tk.done.map(taskCard), ...g.done.map((s) => quietHtml(s, !scope))], shown = doneOpen ? doneRows : doneRows.slice(0, DONE_SHOWN);
  const sec = (cls, text, list, id = "") => list.length ? `<div class="sec"${id ? ` id="${id}"` : ""}><span class="lbl ${cls}">${text} · ${list.length}</span></div>` : "";
  let html = sec("y", "Needs you", [...tk.needs, ...g.needs], "needsec") + tk.needs.map(taskCard).join("") + g.needs.map(cardHtml).join("")
    + sec("", "Replied", g.replied) + g.replied.map((s) => quietHtml(s, !scope)).join("")
    + sec("", "Working", [...tk.work, ...g.work]) + tk.work.map(taskCard).join("") + g.work.map(cardHtml).join("")
    + sec("", "Idle", g.idle) + g.idle.map((s) => quietHtml(s, !scope)).join("")
    + sec("", "Done today", doneRows) + shown.join("")
    + (doneRows.length > DONE_SHOWN && !doneOpen ? `<div class="more-done"><button class="btn sm" data-go="moredone">Show ${doneRows.length - DONE_SHOWN} more</button></div>` : "")
    + (g.empty.length ? `<div class="more-done"><button class="btn sm" data-go="empties" title="Chats that loaded their rules and never got a prompt">${emptyOpen ? "Hide" : "Show"} ${g.empty.length} empty ${g.empty.length === 1 ? "chat" : "chats"}</button></div>`
      + (emptyOpen ? g.empty.map((s) => quietHtml(s, !scope)).join("") : "") : "");
  if (!g.needs.length && !g.replied.length && !g.work.length && !g.idle.length && !g.done.length && !g.empty.length
      && !tk.needs.length && !tk.work.length && !tk.done.length) {
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
function otherHarness() { return Object.entries((cfg && cfg.harnesses) || {}).some(([h, i]) => h !== "claude" && i.on && i.found); }
function runnable() { return !!cfg && cfg.claude && cfg.projects.includes(project); }

function renderCompose() {
  if (!project || !projectKnown(project)) project = (cfg && cfg.projects[0]) || (snap && snap.projects[0] && snap.projects[0].dir) || "";
  if (!snap) return;
  const box = $("c-prompt");
  box.disabled = !!busy || !runnable();
  box.placeholder = runnable() ? "New task in " + projectName(project) : "Allow runs first";
  const moved = Date.now() - movedAt < 4000;
  const chipHtml = `<button class="tgt${moved ? " moved" : ""}" data-pick title="Change project (Ctrl+P)">${esc(projectName(project))}<span class="car">&#9662;</span></button>`;
  let html;
  if (busy) html = `<span class="loading"><span class="cells">${cellsHtml(["f", "", "", "", "", ""])}</span>${esc(busy)}</span>`;
  else if (cfg && !cfg.claude) html = otherHarness()
    ? '<span class="r">claude.exe not found: Prep needs it; set "exe" under harnesses.claude</span>'
    : '<span class="r">claude.exe not found: set "claude_exe" in config.json</span>';
  else if (!project) html = "To run: start a Claude Code session in a project first";
  else if (!runnable()) html = `<span>Runs are off in ${chipHtml}: a run would use this repo's hooks and settings without asking.</span>
    <button class="btn sm" data-go="allow">Allow runs</button>`;
  else html = `<span>in</span>${chipHtml}<button class="btn sm" data-attach="compose" title="Images, PDF or text files (or paste, or drop them on the box)">Attach</button>
    <span class="hint"><span class="kbd">Enter</span>Prep</span>`;
  if (draftKept && !busy) html += '<span class="m mut">Draft kept from last time</span><button class="btn sm" data-go="cleardraft">Clear</button>';
  setHtml($("c-say"), html);
  setHtml($("files-compose"), filesHtml("compose"));
  renderEffort();
  setHtml($("preps"), preps().map(prepJobHtml).join(""));
  spin();
  setHtml($("prepfail"), fail ? `<div class="card r" style="cursor:default"><div class="l1"><span class="st r">× FAILED</span><span class="t">${esc(fail.title)}</span></div>
    <div class="m mut">${esc(fail.msg)}</div>${fail.retry ? '<div class="lr"><button class="btn go sm" data-go="retry">Try again</button></div>' : ""}</div>` : "");
}

// -- effort slider (plan 17): Auto, or one level for every step of a task and for a run --------------
function effortText() { return effortPick === "auto" ? "effort: auto (the rules pick per step)" : `effort: ${effortPick} on every step`; }

function renderEffort() {
  const at = EFF_LEVELS.indexOf(effortPick);
  const level = (lvl, k) => `<button role="radio" aria-checked="${at === k}" data-eff="${lvl}" tabindex="${at === k ? 0 : -1}"
    aria-label="${lvl}" title="${lvl}"><span class="cells"><i${at >= k ? ' class="f"' : ""}></i></span></button>`;
  setHtml($("effort"), `<button role="radio" aria-checked="${at === 0}" data-eff="auto" tabindex="${at === 0 ? 0 : -1}"
    title="Auto: the rules pick the effort per step (Alt+Up / Alt+Down change it)"><span class="m">Auto</span></button>
    ${EFF_LEVELS.slice(1).map((lvl, k) => level(lvl, k + 1)).join("")}
    <span class="eh">${effortPick === "auto" ? "Auto: the rules pick per step" : esc(effortPick) + " on every step"}</span>`);
}

function setEffort(value) {
  if (!EFF_LEVELS.includes(value) || value === effortPick) return;
  effortPick = value;
  saveDraft();
  renderEffort();
}

function stepEffort(d) { setEffort(EFF_LEVELS[Math.min(EFF_LEVELS.length - 1, Math.max(0, EFF_LEVELS.indexOf(effortPick) + d))]); }

// the effort a run without a Prep card uses: the slider's level, else the config default
function rawEffort() { return effortPick !== "auto" ? effortPick : cfg.default_effort; }

// -- Prep jobs: the strip above the composer; each runs in the service, then waits for Run ---------
function preps() { return (snap && snap.preps) || []; }

const prepSeen = new Set();  // a Prep row grows in once, the first time it is painted
function prepJobHtml(j) {
  const where = esc(projectName(j.project_dir)), id = esc(j.id), grow = prepSeen.has(j.id) ? "" : " grow";
  prepSeen.add(j.id);
  const isReview = j.kind === "review", name = isReview ? "Review rules" : "Prep";
  if (j.state === "running") {
    return `<div class="card${grow}" style="cursor:default"><div class="l1"><span class="st n">&#9676; ${name}</span><span class="t">${esc(j.raw)}</span>
      <span class="age m">${ago(snap.now - j.ts)}</span></div>
      <span class="loading"><span class="cells">${cellsHtml(["f", "", "", "", "", ""])}</span>Haiku is reading ${where}${isReview ? "'s rules" : ""}, 10 to 30 s</span></div>`;
  }
  if (j.state === "failed") {
    return `<div class="card r${grow}" style="cursor:default"><div class="l1"><span class="st r">× FAILED</span><span class="t">${name}: ${esc(j.raw)}</span></div>
      <div class="m mut">${esc(j.error)}</div><div class="lr"><button class="btn go sm" data-prep="${id}" data-pdo="retry">Try again</button>
      ${isReview ? "" : `<button class="btn sm" data-prep="${id}" data-pdo="edit">Edit</button>`}<button class="btn sm" data-prep="${id}" data-pdo="drop">Dismiss</button></div></div>`;
  }
  const c = j.card;
  if (isReview) {
    const n = c.proposals.length, what = n ? `${n} proposal${n === 1 ? "" : "s"}` : "nothing to change";
    return `<div class="card${grow}" data-prep="${id}" data-pdo="open" tabindex="0" role="button" aria-label="${esc("Review ready: " + what)}">
      <div class="l1"><span class="st g">&#9654; Review ready</span><span class="t">${esc(c.summary || what)}</span><span class="age m">${ago(snap.now - c.ts)}</span></div>
      <div class="l2 m"><span class="who">${where} · ${what} · ${c.misses} misses, ${c.lessons} lessons read</span><span class="cost">${money(c.cost)}</span></div></div>`;
  }
  const goal = c.fields.goal || c.raw;
  return `<div class="card${grow}" data-prep="${id}" data-pdo="open" tabindex="0" role="button" aria-label="${esc("Prep ready: " + goal)}">
    <div class="l1"><span class="st g">&#9654; Ready to run</span><span class="t">${esc(goal)}</span><span class="age m">${ago(snap.now - c.ts)}</span></div>
    <div class="l2 m"><span class="who">${where}<span class="route"> · ${esc(modelText(c.route.model, c.route.effort))}</span>${j.attached.length ? ` · ${j.attached.length} file${j.attached.length === 1 ? "" : "s"}` : ""}</span>
    <span class="cost">${money(c.cost)}</span></div></div>`;
}

async function prepJob(id, what) {
  const j = preps().find((x) => x.id === id);
  if (!j) return;
  if (j.kind === "review") {
    if (what === "open") { if (j.card) { card = null; reviewCard = j.card; showReview(); } return; }
    if (what === "retry") await startReview(j.project_dir);
    await dropPrep(id);
    return;
  }
  if (what === "open") { if (j.card) { card = j.card; showPrep(); } return; }
  if (what === "retry") await startPrep(j.project_dir, j.raw, [], id);  // the new job takes the old one's files first
  await dropPrep(id);
  if (what === "edit") { putBack(j.raw); if (j.attached.length) filesNotKept(); }
}

async function startReview(projectDir) {  // Haiku reads the project's rules, the misses and the lessons; nothing is written
  try { await api("/api/review", { project_dir: projectDir }); }
  catch (e) { fail = { title: "Review did not start", msg: e.message, retry: "" }; }
  card = null;
  reviewCard = null;
  showPage("list");
}

function jobFiles(id) { const j = preps().find((x) => x.id === id); return j ? j.attached.length : 0; }
function filesNotKept() {  // a job's files live in the service, not in this page: Edit cannot bring them back
  fail = { title: "Files not kept", msg: "Edit puts back the text only: attach the files again.", retry: "" };
  renderCompose();
}

function dropPrep(id) { return api("/api/prep/drop", { job: id }).catch(() => {}); }

function putBack(text) {  // a Prep's request back in the composer, to edit it
  draft = text;
  draftKept = false;
  $("c-prompt").value = text;
  saveDraft();
  showPage("list");
  $("c-prompt").focus();
}

// -- attachments: files sent inline with a prompt (console/attach.py checks them) ------------------
const ATTACH_FILES = 5, ATTACH_BYTES = 5 * 1024 * 1024;  // attach.MAX_FILES, attach.MAX_BYTES
const THUMB_PX = 160, THUMB_MAX = 24 * 1024;              // drawn here; attach.THUMB_MAX keeps it
const att = { compose: [], answer: [], fu: [] };          // per prompt box: {name, kind, bytes, data (base64), thumb}
let pickFor = "";                                         // the box the file dialog adds to
function sizeText(n) { return n < 1024 ? n + " B" : n < 1048576 ? Math.round(n / 1024) + " KB" : (n / 1048576).toFixed(1) + " MB"; }
function fileKind(f) { return f.type.startsWith("image/") ? "image" : f.type === "application/pdf" ? "pdf" : "text"; }
async function makeThumb(f) {  // a small JPEG of an image, kept with the prompt for the Chat ("" when it cannot be drawn)
  try {
    const bmp = await createImageBitmap(f), r = Math.min(1, THUMB_PX / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(bmp.width * r));
    c.height = Math.max(1, Math.round(bmp.height * r));
    const g = c.getContext("2d");
    g.fillStyle = "#fff";  // JPEG has no alpha: transparent parts on white
    g.fillRect(0, 0, c.width, c.height);
    g.drawImage(bmp, 0, 0, c.width, c.height);
    bmp.close();
    const url = c.toDataURL("image/jpeg", 0.72);
    return url.length <= THUMB_MAX ? url : "";
  } catch (e) { return ""; }
}
function fileChip(f, remove = "", src = "") {  // `src`: the thumbnail (a kept data URL, or /api/image)
  src = src || f.thumb || "";
  return `<li class="file">${src ? `<img class="thumb" src="${esc(src)}" alt="" loading="lazy" title="Click to enlarge">` : ""}<span class="k">${esc(f.kind)}</span><span class="nm" title="${esc(f.name)}">${esc(f.name)}</span>${f.bytes == null ? "" : `<span class="m">${sizeText(f.bytes)}</span>`}${remove}</li>`;
}
function filesHtml(key) {  // the chips under a prompt box, each with its remove button
  return att[key].map((f, k) => fileChip(f, `<button data-unattach="${key}" data-k="${k}" aria-label="Remove ${esc(f.name)}" title="Remove">&#10005;</button>`)).join("");
}
function imageSrc(f, role, sid) {  // a transcript's pasted image, or an image Claude wrote in the folder: read by the service
  if (!sid || f.kind !== "image" || f.thumb) return "";
  const q = "/api/image?session=" + encodeURIComponent(sid);
  if (f.at) return `${q}&at=${encodeURIComponent(f.at[0])}&k=${f.at[1]}`;
  return role === "claude" ? `${q}&path=${encodeURIComponent(f.name)}` : "";
}
function chatFiles(files, role, sid = "") {  // a Chat turn's files: what Fred attached, or what Claude wrote before its words
  if (!files || !files.length) return "";
  return `<ul class="files" aria-label="${role === "claude" ? "Files Claude wrote" : "Attached files"}">${role === "claude" ? '<li class="by">wrote</li>' : ""}${files.map((f) => fileChip(f, "", imageSrc(f, role, sid))).join("")}</ul>`;
}
function wire(list) { return list.map(({ name, data, thumb }) => ({ name, data, thumb })); }
function sendable(key) { return wire(att[key]); }
function boxKey(el) { return el.closest(".compose") ? "compose" : el.closest(".askbox") ? "answer" : el.closest("#levers") && $("fu") ? "fu" : ""; }
function attachSay(key, text) {
  if (key === "compose") { fail = { title: "Attach failed", msg: text, retry: "" }; renderCompose(); }
  else { const m = $(key === "answer" ? "a-msg" : "f-msg"); if (m) m.innerHTML = `<span class="r">${esc(text)}</span>`; }
}
function paintFiles(key) {
  if (key === "compose") renderCompose();
  else if (key === "answer") renderSession();
  else { leversSig = ""; const s = current(); if (s) renderLevers(s).catch(() => {}); }
}
async function addFiles(key, list) {
  if (!key) return;
  for (const f of list) {
    if (att[key].length >= ATTACH_FILES) { attachSay(key, `at most ${ATTACH_FILES} files per prompt`); break; }
    if (f.size > ATTACH_BYTES) { attachSay(key, `${f.name}: over 5 MB`); continue; }
    const data = await new Promise((ok, ko) => {
      const r = new FileReader();
      r.onload = () => ok(String(r.result).split(",")[1] || "");
      r.onerror = () => ko(r.error);
      r.readAsDataURL(f);
    }).catch(() => null);
    if (data === null) { attachSay(key, `${f.name}: could not be read`); continue; }
    const kind = fileKind(f), thumb = kind === "image" ? await makeThumb(f) : "";
    att[key].push({ name: f.name || "pasted." + (f.type.split("/")[1] || "png"), kind, bytes: f.size, data, thumb });
  }
  paintFiles(key);
}

let loadingTimer = null;
function spin() {  // the loading cells step while the composer waits or a Prep job runs
  const want = (!!busy || preps().some((j) => j.state === "running")) && !matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (want === !!loadingTimer) return;
  clearInterval(loadingTimer);
  loadingTimer = null;
  if (!want) return;
  let k = 0;
  loadingTimer = setInterval(() => {
    document.querySelectorAll(".loading .cells").forEach((row) => row.querySelectorAll("i").forEach((c, j) => { c.className = j === k % 6 ? "f" : ""; }));
    k++;
  }, 300);
}

function setBusy(text) {
  busy = text;
  fail = null;
  renderCompose();
}

function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => api("/api/draft", { text: draft, project, brief: briefOpen, effort: effortPick }).catch(() => {}), 600);
}

function doPrep() {  // the box empties at once; the Prep runs in the service and shows on the strip
  const text = $("c-prompt").value.trim();
  if (!text || !runnable()) return;
  draft = "";
  draftKept = false;
  $("c-prompt").value = "";
  saveDraft();
  const files = att.compose;  // they wait with the job in the service until its card runs
  att.compose = [];
  renderCompose();  // the chips leave with the text, before the service answers
  startPrep(project, text, files);
}

async function startPrep(projectDir, text, files = [], from = "") {  // `from`: Try again takes that job's files
  fail = null;
  try {
    await api("/api/prep", { project_dir: projectDir, prompt: text, files: wire(files), files_from: from });
  } catch (e) {
    if (!$("c-prompt").value.trim()) { draft = text; $("c-prompt").value = text; saveDraft(); }  // nothing typed since: the text comes back
    if (!att.compose.length) att.compose = files;
    fail = { title: "Prep failed", msg: e.message, retry: "prep" };
  }
  renderCompose();
}

async function doRun(projectDir, prompt, model, effort, prepId, from = "", fableOk = false) {  // true once the run started
  if (busy) return false;
  const mine = !prepId && !from;  // from the composer: its files go now; a card's wait with its job
  setBusy("Starting the run ...");
  try {
    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "",
      files: mine ? sendable("compose") : [], files_from: from, fable_ok: fableOk });
    if (mine) att.compose = [];
    card = null;
    setBusy("");
    openSession(r.session, "chat");
    return true;
  } catch (e) {
    setBusy("");
    if (page === "prep") $("p-msg").innerHTML = `<span class="r">${esc(e.message)}</span>`;
    else { fail = { title: "Run failed", msg: e.message, retry: "raw" }; renderCompose(); }
    return false;
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
  snap.sessions.forEach((s) => { if (s.project_dir && s.group !== "done" && s.group !== "empty") { const r = row(s.project_dir); r.live++; r.needs += s.group === "needs"; } });
  return [...by.values()];
}

const hsErr = {};  // harness name -> the last error from POST /api/harness; "models" -> from the models.json row
const hsBusy = new Set();
function harnessHtml() {  // the Harnesses group: state is a glyph plus a word, never colour alone
  const hs = (cfg && cfg.harnesses) || {};
  const names = Object.keys(hs);
  if (!names.length) return "";
  const rows = names.map((name) => {
    const i = hs[name], st = !i.on ? ["–", "off"] : !i.found ? ["×", "not found"] : ["✓", "on"];
    const btn = name === "claude" ? '<span class="m mut">always on</span>'
      : `<button class="btn sm" data-harness="${esc(name)}" data-on="${i.on ? "false" : "true"}"${hsBusy.has(name) ? " disabled" : ""}>${hsBusy.has(name) ? "..." : i.on ? "Turn off" : "Turn on"}</button>`;
    const extra = hsErr[name] ? `<span class="r">${esc(hsErr[name])}</span>`
      : i.on && !i.found ? `<span class="m mut">set "exe" under harnesses.${esc(name)} in ${esc(cfg.config_path || "config.json")}</span>` : "";
    return `<div class="hs" data-hname="${esc(name)}"><span class="nm">${esc(name)} <span class="st m">${st[0]} ${st[1]}</span></span>${btn}
      ${i.version ? `<span class="m mut wide">${esc(i.version)}</span>` : ""}${extra ? `<span class="wide">${extra}</span>` : ""}</div>`;
  }).join("");
  const mf = cfg.models_file || {};
  const mrow = `<div class="hs" data-hname="models"><span class="nm">Models <span class="m mut">· models.json · ${mf.count || 0} models</span></span>
    <span class="btns"><button class="btn sm" data-models="open"${hsBusy.has("models") ? " disabled" : ""}>Open</button><button class="btn sm" data-models="reload"${hsBusy.has("models") ? " disabled" : ""}>Reload</button></span>
    ${mf.error ? `<span class="r wide">${esc(mf.error)}</span>` : hsErr.models ? `<span class="r wide">${esc(hsErr.models)}</span>` : ""}</div>`;
  return `<div class="grp lbl">Harnesses</div>${rows}${mrow}`;
}
function windowRunsFold() {  // interface 4, ID-2: config.json stays the truth; POST /api/setting writes it
  const on = !!(cfg && cfg.handoff_auto), red = cfg && cfg.gauge ? cfg.gauge[1] : 300000;
  const ctl = `<button class="sw" role="switch" data-setting="handoff_auto" aria-checked="${on}" aria-label="auto hand off" title="${on ? "Turn off" : "Turn on"}${settingBusy ? " (waiting for the service)" : ""}"${settingBusy ? ' aria-busy="true"' : ""}>${settingBusy ? "..." : on ? "on" : "off"}</button>`;
  const row = `<div class="sr"><span class="gl ${on ? "g" : ""}">${on ? "●" : "○"}</span><span class="nm">Auto hand off</span><span class="ctl">${ctl}</span>
    <span class="sub${settingErr ? " r" : ""}">${esc(settingErr || `at ${kTokens(red)} · red zone`)}</span>
    <span class="why">Hands off a window run that ends its turn in the red zone and seeds the next chat; a VS Code chat is forked first.</span></div>`;
  return fold("Window runs", `auto hand off: ${on ? "on" : "off"}`, row);
}
async function harnessAct(button) {
  const name = button.dataset.harness;
  hsBusy.add(name); delete hsErr[name]; pickRows();
  try { cfg.harnesses = (await api("/api/harness", { name, on: button.dataset.on === "true" })).harnesses; }
  catch (err) { hsErr[name] = err.message; }
  hsBusy.delete(name);
  if (!$("pop").hidden) pickRows();
}
async function modelsAct(button) {
  const what = button.dataset.models;
  hsBusy.add("models"); delete hsErr.models; pickRows();
  try {
    if (what === "open") await api("/api/models/open", {});
    else { const r = await api("/api/models/reload", {}); cfg.models_file = r.models_file; cfg.harnesses = r.harnesses; cfg = Object.assign(cfg, await api("/api/config")); }
  } catch (err) { hsErr.models = err.message; }
  hsBusy.delete("models");
  if (!$("pop").hidden) pickRows();
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
  if (!q) html += harnessHtml() + `<div class="pset">${windowRunsFold()}</div>`;
  $("prows").innerHTML = html;
  hi = 0;
  markHi();
}

function markHi() {
  const rows = [...document.querySelectorAll("#prows .prow")];
  rows.forEach((r, k) => r.classList.toggle("hi", k === hi));
  if (rows[hi]) rows[hi].scrollIntoView({ block: "nearest" });
}

function placePicker(from) {  // beside the control that opened it: below when there is room, else above
  const r = from.getBoundingClientRect(), o = $("open").getBoundingClientRect(), pop = $("pop");
  const below = o.bottom - r.bottom, above = r.top - o.top, up = above > below;
  pop.style.top = up ? "auto" : (r.bottom - o.top + 4) + "px";  // under the header, banner or not
  pop.style.bottom = up ? (o.bottom - r.top + 4) + "px" : "auto";
  pop.style.maxHeight = Math.max(160, (up ? above : below) - 12) + "px";
}

function openPicker(from) {
  if (!snap || !cfg) return;
  if (form === "pill") return;
  if (page !== "list") showPage("list");
  $("pop").hidden = false;
  placePicker(from || $("scope"));
  $("scope").setAttribute("aria-expanded", "true");
  $("pfind").value = "";
  pickRows();
  $("pfind").focus();
}

function closePicker() {
  $("pop").hidden = true;
  $("scope").setAttribute("aria-expanded", "false");
}

async function openFolder() {  // VS Code's Open Folder: the OS dialog picks it, then runs are allowed there
  let dir = "";
  try { dir = await window.pywebview.api.pick_folder(); } catch (err) { return; }
  if (!dir) return;
  try {
    cfg.projects = (await api("/api/open_folder", { project_dir: dir })).projects;
    fail = null;
    pick(dir);
  } catch (err) {
    closePicker();
    fail = { title: "Open folder failed", msg: err.message, retry: "" };
    renderCompose();
  }
}

function pick(dir) {  // a project scopes the list and becomes the task target; All projects keeps the target
  scope = dir;
  if (dir && dir !== project) { movedAt = Date.now(); setTimeout(renderCompose, 4000); }  // the chip shows the move
  if (dir) project = dir;
  doneOpen = false;
  closePicker();
  render();
  saveDraft();
}

// -- Prep page ---------------------------------------------------------------------------
function options(list, value) { return list.map((v) => `<option${v === value ? " selected" : ""}>${esc(v)}</option>`).join(""); }

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

// Run as task: one row per step. A verify row is fixed text (the service adds it after the last editing step).
function stepRowHtml(st) {
  if (st.kind === "verify") {
    return `<div class="srow fixed"><span class="n m"></span><span><b class="m">verify</b> <span class="mut">added by the Console after the last editing step</span></span></div>`;
  }
  return `<div class="srow" data-row><span class="n m"></span>
    <select data-skind aria-label="Kind">${options(cfg.kinds, st.kind)}</select>
    <select data-smodel aria-label="Model">${modelOptions(st.pick || "", true, st.kind)}</select>
    <button class="rb" data-pact="rmstep" aria-label="Remove step" title="Remove step">&#10005;</button>
    <input data-sgoal aria-label="Goal" value="${esc(st.goal)}" spellcheck="false" placeholder="Goal of this step"></div>`;
}

function stepsChanged() {  // the verify row, numbers, the Fable note and Run as task (two rows or more) follow the rows
  const list = $("p-steps"), fixed = list && list.querySelector(".srow.fixed");
  const edits = !!list && [...list.querySelectorAll("[data-row] [data-skind]")].some((s) => (cfg.edit_kinds || []).includes(s.value));
  if (edits && !fixed) list.insertAdjacentHTML("beforeend", stepRowHtml({ kind: "verify" }));  // the service adds it after the last edit
  if (!edits && fixed) fixed.remove();
  const rows = [...document.querySelectorAll("#p-steps .srow")];
  rows.forEach((r, k) => { r.querySelector(".n").textContent = k + 1; });
  const fable = [...document.querySelectorAll("#p-model, #p-steps [data-smodel]")].some((s) => alias(s.value) === "fable");
  const kinds = [...new Set([...rows].map((r) => (r.querySelector("[data-skind]") || { value: "verify" }).value))];
  if ($("p-floors")) $("p-floors").innerHTML = kinds.map((k) => floorText(k, "steps")).filter(Boolean).map(esc).join("<br>");
  const note = $("p-fable"), run = document.querySelector('#pbar [data-pact="task"]');
  if (note) note.hidden = !fable;
  if (run) run.hidden = rows.length < 2;
}

function floorText(kind, noun) {  // a routing miss of this kind (Escalate wrote it) lifts its start above the rule
  const f = ((card && card.floors) || {})[kind];
  return f ? `Floor from Escalate${f.date ? " (" + f.date + ")" : ""}: ${kind} ${noun} start at ${f.route}, above their rule; a model you pick here holds.` : "";
}

function showPrep() {
  const f = card.fields, steps = card.steps || [];
  $("crumb").textContent = "Prep / " + projectName(card.project_dir);
  $("pscroll").innerHTML = `
    <div class="blk"><span class="lbl">Project</span><div class="proj m"><b>${esc(projectName(card.project_dir))}</b> <span class="mut">${esc(card.project_dir)}</span></div></div>
    <div class="blk"><span class="lbl">You typed</span><div class="text">${esc(card.raw)}</div></div>
    ${jobFiles(card.id) ? `<div class="blk"><span class="lbl">Sent with the run</span>${chatFiles(preps().find((x) => x.id === card.id).attached, "you")}</div>` : ""}
    ${f.where ? `<div class="blk"><span class="lbl">Scouted</span><div class="m">${esc(f.where)}</div></div>` : ""}
    <div class="blk"><span class="lbl">Enhanced prompt (edit freely)</span>
      <textarea id="p-prompt" class="in m" rows="9" spellcheck="false">${esc(card.prompt)}</textarea></div>
    ${f.question ? `<div class="askbox" style="margin:0"><span class="st y">? Question</span><div class="q">${esc(f.question)}</div></div>` : ""}
    <div class="blk"><span class="lbl">Run route (one session)</span><div class="prep-row">
      <select id="p-model" aria-label="Model">${modelOptions(card.route.model, false)}</select>
      <select id="p-effort" aria-label="Effort">${options(cfg.efforts, effortPick !== "auto" ? effortPick : card.route.effort)}</select>
      <span class="m mut">${esc(card.route.type)}</span></div>
      ${card.reason ? `<div class="mut">${esc(card.reason)}</div>` : ""}
      ${floorText(card.route.type, "runs") ? `<div class="m mut">${esc(floorText(card.route.type, "runs"))}</div>` : ""}
      <div class="lr"><button class="btn sm" data-pact="review" title="Haiku reads this project's CLAUDE.md and rules files, the routing misses and the lessons, and proposes what to cut or add. Nothing is written.">Review rules</button></div></div>
    <div class="blk"><div class="hd"><span class="lbl">Steps</span><button class="btn sm" data-pact="addstep">+ step</button></div>
      <div id="p-steps">${steps.map(stepRowHtml).join("") || '<p class="m mut" data-nosteps>Prep proposed no steps. Add steps to run this as a task.</p>'}</div>
      <div class="m mut">Run as task: each step's model comes from its kind (auto) or the model you pick on its row, not from the Run route above. A verify step runs one model above the step it checks.</div>
      <div id="p-floors" class="m mut"></div>
      <div id="p-fable" class="say" hidden>${esc(fableName())} may bill usage credits on this plan; it asks you to confirm before it runs</div>
      <div class="m mut">${esc(effortText())}</div></div>
    <div class="m mut">Prep $${Number(card.cost).toFixed(3)} · ${card.turns} turns</div>`;
  $("pbar").innerHTML = `<div class="m runs-in">Runs in <b>${esc(projectName(card.project_dir))}</b></div><div class="lr"><button class="btn go" data-pact="task" hidden>Run as task</button>
    <button class="btn go" data-pact="run">Run</button>
    <button class="btn" data-pact="raw">Run raw</button><button class="btn" data-pact="edit">Edit</button>
    <button class="btn" data-pact="cancel">Cancel</button></div><div id="p-msg" class="say"></div>`;
  stepsChanged();
  showPage("prep");
  $("p-prompt").focus();
}

const REVIEW_KIND = { remove: "Remove", demote: "Demote to a procedure", rule: "New rule", procedure: "New procedure", keep: "Keep as is" };
function showReview() {  // the Prep page section, with proposals instead of a card; Copy puts a line on the clipboard
  const c = reviewCard, items = c.proposals;
  $("crumb").textContent = "Review / " + projectName(c.project_dir);
  const one = (p, k) => `<div class="blk"><div class="hd"><span class="lbl">${esc(REVIEW_KIND[p.kind] || p.kind)}${p.target ? " · " + esc(p.target) : ""}</span>
      ${p.text ? `<button class="btn sm" data-pact="copy" data-k="${k}">Copy</button>` : ""}</div>
    ${p.text ? `<div class="text m">${esc(p.text)}</div>` : ""}
    ${p.why ? `<div class="mut">${esc(p.why)}</div>` : ""}
    ${p.sources.length ? `<div class="m mut">from: ${p.sources.map(esc).join(" · ")}</div>` : ""}</div>`;
  $("pscroll").innerHTML = `
    <div class="blk"><span class="lbl">Project</span><div class="proj m"><b>${esc(projectName(c.project_dir))}</b> <span class="mut">${esc(c.project_dir)}</span></div></div>
    <div class="blk"><span class="lbl">Summary</span><div class="text">${esc(c.summary || "(none)")}</div></div>
    ${items.length ? items.map(one).join("") : '<p class="m mut">Nothing to change: the rules read fine against the misses and the lessons.</p>'}
    <div class="m mut">Proposals only: nothing was written. Paste what you agree with into CLAUDE.md or a skill yourself.</div>
    <div class="m mut">Review $${Number(c.cost).toFixed(3)} · ${c.turns} turns · ${c.misses} misses, ${c.lessons} lessons read</div>`;
  $("pbar").innerHTML = `<div class="lr"><button class="btn" data-pact="rdrop">Dismiss</button><button class="btn" data-pact="back">Back</button></div><div id="p-msg" class="say"></div>`;
  showPage("prep");
}

async function copyText(button) {
  const p = reviewCard.proposals[Number(button.dataset.k)], msg = $("p-msg");
  try { await navigator.clipboard.writeText(p.text); setHtml(msg, "copied"); }
  catch (e) { setHtml(msg, '<span class="r">the clipboard is not reachable here: select the text and copy it</span>'); }
}

function stepList() {  // the rows as the page shows them (the order is the chain's); empty goals drop out
  return [...document.querySelectorAll("#p-steps [data-row]")].map((r) => {
    const step = { kind: r.querySelector("[data-skind]").value, goal: r.querySelector("[data-sgoal]").value.trim() };
    const model = r.querySelector("[data-smodel]").value;
    return model ? Object.assign(step, { model }) : step;
  }).filter((s) => s.goal);
}

async function runAsTask(c, button) {
  const steps = stepList(), msg = $("p-msg");
  if (!steps.length) { msg.innerHTML = '<span class="r">Give at least one step a goal</span>'; return; }
  button.disabled = true;
  try {
    const r = await api("/api/task", { prep: c.id, prompt: $("p-prompt").value.trim(), steps, effort: effortPick });
    card = null;
    openTask(r.task);
  } catch (e) {
    button.disabled = false;
    msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

async function prepAct(name, button) {  // Run drops the card's job in the service; Run raw, Edit and Cancel drop it here
  if (reviewCard && !card) {  // the Review page (plan 22) shares this section
    if (name === "back") { reviewCard = null; showPage("list"); }
    if (name === "rdrop") { dropPrep(reviewCard.id); reviewCard = null; showPage("list"); }
    if (name === "copy") copyText(button);
    return;
  }
  if (busy || !card) return;
  const c = card;
  if (name === "addstep") {
    const hint = $("p-steps").querySelector("[data-nosteps]");
    if (hint) hint.remove();
    const last = $("p-steps").lastElementChild;  // the verify row stays last
    if (last && last.matches(".fixed")) last.insertAdjacentHTML("beforebegin", stepRowHtml({ kind: "code", goal: "" }));
    else $("p-steps").insertAdjacentHTML("beforeend", stepRowHtml({ kind: "code", goal: "" }));
    stepsChanged();
    const goals = document.querySelectorAll("#p-steps [data-sgoal]");
    goals[goals.length - 1].focus();
  }
  if (name === "rmstep") { button.closest(".srow").remove(); stepsChanged(); }
  if (name === "task") runAsTask(c, button);
  if (name === "run") {
    const fable = alias($("p-model").value) === "fable";
    if (fable && !button.dataset.armed) {  // two clicks, like the Task page's Stop: Fable may bill usage credits
      button.dataset.armed = "1";
      button.dataset.label = button.textContent;
      button.textContent = `Confirm to use ${fableName()}`;
      setTimeout(() => { delete button.dataset.armed; button.textContent = button.dataset.label; }, 3000);
      return;
    }
    doRun(c.project_dir, $("p-prompt").value.trim(), $("p-model").value, $("p-effort").value, c.id, "", fable);
  }
  if (name === "raw" && await doRun(c.project_dir, c.raw, cfg.default_model, rawEffort(), "", c.id)) dropPrep(c.id);
  if (name === "back") { card = null; showPage("list"); }
  if (name === "edit") { card = null; const had = jobFiles(c.id); await dropPrep(c.id); putBack(c.raw); if (had) filesNotKept(); }
  if (name === "cancel") { card = null; dropPrep(c.id); showPage("list"); }
  if (name === "review") startReview(c.project_dir);
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
  if (s.rules_warn) out.push(`△ rules: ${esc(s.rules_warn)}${s.project_dir ? ' · <span class="link" data-act="review" title="Haiku proposes what to cut; nothing is written">Review</span>' : ""}`);
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
      <ul class="files" aria-label="Attached files">${filesHtml("answer")}</ul>
      <div class="lr"><button class="btn you" data-act="answer">Send answer</button>
      <button class="btn" data-attach="answer" title="Images, PDF or text files (or paste, or drop them on the box)">Attach</button>
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
  const unk = s.ctx_tokens == null && s.harness && s.harness !== "claude";
  const word = unk ? "context unknown" : t === "r" ? "hand off now" : t === "y" ? "hand off soon" : "context";
  const rows = agentRows(s, []);
  return `<div class="bwrap">
    <button class="brief" id="brief" aria-expanded="${briefOpen}" aria-controls="more" title="Context, agents and activity (click or Space)">
      <span class="path">${pathHtml(s)}<span class="car" aria-hidden="true">${briefOpen ? "▴" : "▾"}</span></span>
      <span class="stats">
        <span><small>spent</small><b class="usd">${spent}</b></span>
        <span><small>$ / min</small><b>${money(s.burn)}</b></span>
        <span><small class="${t}">${word}</small><span class="cx"><span class="cells">${cellsHtml(ctxClasses(s.ctx_tokens))}</span>
          <b class="${t}">${unk ? "" : s.ctx_tokens == null ? "?" : kTokens(s.ctx_tokens)}</b></span></span>
        <span><small title="since the chat started">session</small><b>${elapsed(end - s.started_ts)}</b></span>
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

function taskLink(s) {  // "task · step 2/4" under the title of a step's session, a link to the Task page
  if (!s.task) return "";
  const t = (snap.tasks || []).find((x) => x.id === s.task), text = `task · step ${s.step}${t ? "/" + t.count : ""}`;
  return t ? `<div class="m"><span class="link" data-task="${esc(t.id)}">${text}</span></div>` : `<div class="m mut">${text}</div>`;
}

function oldStep(id) {  // [task, step] when `id` is a session of the task on the Task page; else null
  const t = taskData && taskData.task;
  const s = t && t.steps.find((x) => x.session === id || (x.attempts || []).some((a) => a.session === id));
  return s ? [t, s] : null;
}
async function renderOldChat(id) {  // a step session out of the snapshot: its transcript, no tabs
  const seq = ++procSeq, chat = await api("/api/chat?session=" + encodeURIComponent(id));
  if (seq !== procSeq || openId !== id) return;
  setHtml($("proc"), `<div class="pane" id="pane" tabindex="0">${chatPane(chat, id, "chat")}</div>`, { sel: ".pane", end: true, reset: procShown !== id + "|old" });
  procShown = id + "|old";
}
function renderSession() {
  const s = current(), nav = navList(), k = navAt(nav);
  $("pos").textContent = k >= 0 ? `${stepNav() ? "step " : ""}${k + 1} of ${nav.length}` : "";
  $("prev").disabled = k <= 0;
  $("next").disabled = k < 0 || k >= nav.length - 1;
  if (!s) {
    const old = oldStep(openId);
    setHtml($("sbody"), old ? `<div class="head"><h2>${esc(old[0].title)}</h2>
      <div class="m">step ${old[1].n}/${old[0].steps.length} · ${esc(old[1].kind)} · older than a day: the Chat reads its transcript</div>
      <div class="m"><span class="link" data-task="${esc(old[0].id)}">task</span></div></div>`
      : '<div class="mut">Starting ... (the session shows up with its first event)</div>');
    if (old) renderOldChat(openId).catch(() => {});
    else { $("proc").innerHTML = ""; $("proc")._html = ""; }
    setHtml($("levers"), "");
    return;
  }
  const t = tone(s);
  const when = BUSY.has(s.state) ? "turn " + ago(snap.now - s.turn_ts) : (s.state === "stop" ? "waiting " : "") + ago(snap.now - s.last_ts);
  const src = s.source === "?" ? "" : s.source + " / ";
  setHtml($("sbody"), `<div class="head"><span class="st ${t}">${sessionMark(s, s.symbol, t)}${esc(label(s))} <span class="lc">· ${when}</span></span><h2>${esc(s.title)}</h2>${taskLink(s)}
    <div class="where"><span class="m" title="${esc(s.route_reason || "")}">${esc(s.project)} / ${esc(src)}${esc(s.route)}</span>
    ${s.model ? `<span class="mdl" title="${esc(s.model)}">${esc(modelText(rungOf(s.harness, s.model), s.effort))}</span>` : ""}
    ${s.project_dir ? `<button class="btn sm" data-here="${esc(s.project_dir)}">New task here</button>` : ""}</div></div>
    ${noteLine(s)}${askBlock(s)}${renderBrief(s)}`);
  renderProc(s).catch(() => {});
  renderLevers(s).catch(() => {});
}

const LIVE = sprite("running");
function logRow(x, mark = "", tag = "") {  // `tag`: the step's model when it is not main's
  return `<div${x.denied ? ' class="r"' : ""}><span>${mark}</span><span>${hms(x.ts)}</span><span>${esc(x.agent_type)}</span><span>${tag ? `<span class="tag">${esc(tag)}</span>` : ""}${esc(x.tool)} ${esc(x.what)}</span></div>`;
}
function stepTag(s) {  // agent id -> its model family, only where it differs from main's
  const main = alias(s.model), by = {};
  for (const a of s.agents) if (alias(a.model) && alias(a.model) !== main) by[a.id] = alias(a.model);
  return (x) => by[x.agent] || "";
}

// A chat reply as HTML: Markdown pipe tables become <table>s, everything else stays escaped text.
const TBL_SEP = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;
function tblCells(line) { return line.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|")); }
function tblHtml(head, sep, rows) {
  const al = tblCells(sep).map((c) => (c.startsWith(":") ? (c.endsWith(":") ? "center" : "left") : c.endsWith(":") ? "right" : ""));
  const row = (tag) => (line) => { const c = tblCells(line);
    return `<tr>${al.map((a, k) => `<${tag}${a ? ` class="${a}"` : ""}>${esc(c[k] ?? "")}</${tag}>`).join("")}</tr>`; };
  return `<div class="tbl"><table><thead>${row("th")(head)}</thead><tbody>${rows.map(row("td")).join("")}</tbody></table></div>`;
}
function chatHtml(text) {
  const lines = String(text ?? "").split("\n"), out = [];
  let para = [];
  const flush = () => { const t = para.join("\n").replace(/^\n+|\n+$/g, ""); if (t) out.push(`<p>${esc(t)}</p>`); para = []; };
  for (let k = 0; k < lines.length; k++) {
    if (lines[k].includes("|") && k + 1 < lines.length && lines[k + 1].includes("-") && TBL_SEP.test(lines[k + 1])
        && tblCells(lines[k]).length === tblCells(lines[k + 1]).length) {
      let end = k + 2;
      while (end < lines.length && lines[end].trim() && lines[end].includes("|")) end++;
      flush();
      out.push(tblHtml(lines[k], lines[k + 1], lines.slice(k + 2, end)));
      k = end - 1;
    } else para.push(lines[k]);
  }
  flush();
  return out.join("");
}

function claudeTurn(text) {  // a step's (or a skill's) final reply: the block folds to a chip and its Next line
  const hb = handoffBlock(text);
  if (!hb) return chatHtml(text);
  const h = handoffSections(hb[1]), w = hb[1].split(/\s+/).filter(Boolean).length;
  return (hb[0].trim() ? chatHtml(hb[0]) : "") + `<span class="hchip">HANDOFF block · <b>${w} w</b> · six headings</span><p>Next: ${esc(h.next.split("\n")[0])}</p>`;
}
function chatPane(chat, sid, source) {  // the Chat tab's markup: a window run's stream or a transcript's turns
  const turns = chat.items.filter((i) => i.role !== "tool");
  const foot = chat.source === "window"
    ? "Streamed from this window run." + (chat.start_commit ? ` start ${esc(chat.start_commit.slice(0, 7))} · ${chat.changed == null ? "?" : chat.changed} file(s) changed since.` : "")
    : `Read from the ${esc(source === "?" ? "chat" : source)} transcript, in words and files; tool output stays in Steps.`;
  return `<div class="chat">${turns.map((i) => `<div class="turn ${i.role}"><span class="lbl">${i.role === "you" ? "You" : i.role === "claude" ? "Claude" : esc(i.role)}${i.ts ? " · " + hhmm(i.ts) : ""}</span>
    ${i.role === "claude" ? claudeTurn(i.text) : i.text ? `<p>${esc(i.text)}</p>` : ""}${chatFiles(i.files, i.role, sid)}</div>`).join("") || '<p class="none">Nothing to show yet. A VS Code or terminal chat shows its turns once a prompt has named its transcript.</p>'}
    <p class="src">${foot}</p></div>`;
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
    const mark = s.state === "running" ? LIVE : s.state === "stop" ? sprite("waiting") : s.state === "blocked" ? sprite("stuck") : "";
    const tag = stepTag(s);
    body = newest.length ? `<div class="log">${newest.map((x, k) => logRow(x, k === 0 ? mark : "", tag(x))).join("")}</div>` : '<p class="none">No step yet.</p>';
  } else if (wanted === "agents") {
    body = `<div class="alist">${rows.map((r) => {
      const m = r.word === "working" && s.state === "running" ? LIVE : r.word === "done" ? sprite("done")
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
    body = chatPane(chat, s.id, s.source);
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
               s.handoff_hint, s.handoff_by, s.forks.length, Math.floor((snap.now - s.last_ts) / 600)].join("|");  // the last one: idle turns cold
  if (sig === leversSig) return;
  leversSig = sig;
  cold = null;
  const lv = s.run_live ? null : await api("/api/levers?session=" + encodeURIComponent(s.id)).catch(() => null);
  if (openId !== s.id || leversSig !== sig) return;
  cold = lv && !lv.continue ? lv.cold : null;
  freshHandoff = Boolean(lv && lv.handoff_fresh);
  let html = "";
  if (lv && !lv.continue && !s.stop_question) {
    html += `<div class="lr"><input id="fu" aria-label="Follow-up" placeholder="${lv.fork ? "Follow-up (runs in a window copy)" : "Follow-up"}">
      <button class="btn" data-attach="fu" title="Images, PDF or text files (or paste, or drop them on the box)">Attach</button>
      <button class="btn go" data-act="continue">Continue</button></div><ul class="files" aria-label="Attached files">${filesHtml("fu")}</ul>`;
  }
  let buttons = "";
  if (s.run_live) buttons += '<button class="btn stop" data-act="stop">Stop</button>';
  if (lv && !lv.next) buttons += '<button class="btn go" data-act="next" title="A new task seeded with the handoff note">Start next chat</button>';
  if (lv && !lv.continue && s.window && s.state === "interrupted") buttons += '<button class="btn go" data-act="resume">Resume</button>';
  if (lv && !lv.verify) buttons += '<button class="btn" data-act="verify">Verify</button>';
  const after = {  // what follows Verify, in the order the service gives (levers.after_verify)
    handoff: lv && !lv.handoff ? `<button class="btn${s.handoff_hint || s.verdict === "PASS" ? " go" : ""}" data-act="handoff">Hand off</button>` : "",
    escalate: lv && !lv.escalate ? `<button class="btn go" data-act="escalate">Escalate to ${esc(lv.escalate_to)}</button>` : "",
    done: !s.run_live && s.group !== "done" ? '<button class="btn" data-act="done" title="Leave the list until the next prompt">Mark done</button>' : "",
  };
  for (const k of lv ? lv.after_verify : ["done"]) buttons += after[k] || "";
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

function seedBox(b) {  // pre-fill the new-task box with a brief; Fred edits it and runs it
  pick(b.project_dir);
  showPage("list");
  draft = b.text;
  draftKept = false;
  $("c-prompt").value = draft;
  saveDraft();
  renderCompose();
  $("c-prompt").focus();
}

let stopTimer = null;
async function act(name, button) {
  const s = current();
  if (!s) return;
  if (name === "review") return startReview(s.project_dir);
  if (name === "stop" && !button.dataset.armed) {  // two clicks: a stopped turn is lost work
    button.dataset.armed = "1";
    button.textContent = "Stop run? Click again";
    clearTimeout(stopTimer);
    stopTimer = setTimeout(() => { delete button.dataset.armed; button.textContent = "Stop"; }, 3000);
    return;
  }
  const typed = name === "answer" ? $("answer") : name === "continue" ? $("fu") : null;
  if (typed && !typed.value.trim()) return;  // nothing to send: no cost to confirm
  if (cold && GUARDED.includes(name) && !(name === "handoff" && freshHandoff) && !button.dataset.armed) {  // two clicks: a cold cache re-reads the context at full price
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
    if (name === "brief" || name === "vbrief" || name === "next") {  // pre-fill the new-task box; Fred edits it and runs it
      const kind = { vbrief: "&kind=verify", next: "&kind=next" }[name] || "";
      seedBox(await api("/api/brief?session=" + encodeURIComponent(s.id) + kind));
      button.disabled = false;
      return;
    }
    if (name === "stop") { button.textContent = "Stopping ..."; await api("/api/stop", { session: s.id }); }
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (name === "done") await api("/api/done", { session: s.id });
    if (name === "resume") r = await api("/api/continue", { session: s.id, text: RESUME_TEXT, confirm });
    if (name === "continue" || name === "answer") {
      const key = name === "answer" ? "answer" : "fu", text = $(key).value.trim();
      if (!text) { button.disabled = false; return; }
      r = await api("/api/continue", { session: s.id, text, confirm, files: sendable(key) });
      att[key] = [];
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
  const nav = navList(), k = navAt(nav), to = nav[k + d];
  if (k >= 0 && to) { openSession(to.id, tab); }
}
function goBack() {  // the session page and the Task page: back where they came from, else the list
  const b = backTo;
  backTo = null;
  if (b && b.page === "task" && (snap.tasks || []).some((t) => t.id === b.id)) return openTask(b.id);
  if (b && b.page === "session") return openSession(b.id, tab);
  showPage("list");
}

// -- task page (plan 17): the chain, the brief for the next step, the levers ----------------------------------
function taskDir(id) {  // the task's folder in the data folder (config_path is <data folder>\config.json)
  const home = String((cfg && cfg.config_path) || "").replace(/[\\/]config\.json$/, "");
  return home ? home + "\\tasks\\" + id : "";
}

function stepTries(s) {  // the earlier attempts of a step, each a link to its chat: "try 1 no HANDOFF block"
  const all = s.attempts && s.attempts.length ? s.attempts : (s.session ? [{ session: s.session, why: "" }] : []);
  return all.slice(0, -1).map((a, k) => `<span class="link" data-open="${esc(a.session)}">try ${k + 1}</span>${a.why ? " " + esc(a.why) : ""}`).join(" · ");
}
function noteChip(s, t) {  // what the step does now, by its handoff note from the snapshot row's `note`
  if (!s.note) return "";
  const me = `${two(s.n)} ${s.kind}`, nxt = two(s.n + 1);
  const [word, tip] = {
    writing: [`${me} running`, "not written yet"],
    unchecked: [`${me} running · note written`, "written, checked when the run ends"],
    checked: ["✓ note checked", "checked"],
    ready: [`✓ note ready for step ${nxt}`, `checked, step ${nxt} has not started`],
    sent: [`note sent to step ${nxt}`, `step ${nxt} started with it`],
    handed: ["↻ handed off · note written", "the session-handoff note; Start next task seeds a new task with it"],
  }[s.note] || [s.note, ""];
  return `<span class="hn ${s.note}" title="the HANDOFF note of step ${s.n}: ${esc(tip)}">${esc(word)}</span>`;
}
function chainRow(t, s) {
  const tn = s.state === "handed" ? stepCell(t, s) : s.state === "failed" || s.verdict === "FAIL" ? "r" : s.note === "unchecked" ? "w" : s.state === "done" ? "g" : s.state === "running" ? "f" : "";
  const cells = cellsHtml(Array.from({ length: 6 }, (_, k) => (tn === "f" && k === 0 ? "f live" : tn)));
  const verdict = s.verdict ? `<span class="${s.verdict === "FAIL" ? "r" : "g"}">${esc(s.verdict)}${s.verdict === "FAIL" && s.verdict_detail ? " " + esc(s.verdict_detail) : ""}</span>` : "";
  const waits = t.state === "waiting" && s.n === t.current && /^(plan |replanned:|asks: Plan gap:)/.test(t.why || "");  // a plan wait: the reason, in orange
  const sub = [verdict, s.retries ? "retry " + s.retries : "", stepTries(s), waits ? `<span class="y">${esc(t.why)}</span>` : esc(s.goal)].filter(Boolean).join(" · ");
  const from = s.part ? `<span class="tg" title="a write step the design step made: sub-plan ${s.part} of ${((t.plan || {}).parts || []).length}">from plan</span>` : "";
  return `<div class="row${s.n === t.current ? " cur" : ""}${fresh("c", "t" + t.id + "." + s.n, s.state, 300) && s.state === "done" ? " adv" : ""}${s.note ? " n-" + s.note : ""}"><span class="cells">${cells}</span>
    <span class="nm m">${two(s.n)} ${esc(s.kind)}${from}${s.model ? ` <span class="mdl">${esc(modelText(rungOf(s.harness, s.model), s.effort))}</span>` : ""}</span>
    <span class="m c">${s.cost ? money(s.cost) : ""}</span>
    ${s.session ? `<button class="btn sm" data-open="${esc(s.session)}">Open</button>` : "<span></span>"}
    ${noteChip(s, t)}${sub ? `<span class="sub">${sub}</span>` : ""}</div>`;
}

function handedBox(d, t, cur, shown) {  // Fred handed the task off: the skill's note, then Start next task (Mark done ends it)
  const [word, tn] = TASK_WORD[shown] || TASK_WORD.handed, dir = taskDir(t.id);
  const body = d.handoff
    ? `<pre class="text">${esc(d.handoff)}</pre>${dir ? `<div class="m tpath">${esc(dir + "\\" + t.handoff_note.replace(/\//g, "\\"))}</div>` : ""}`
    : `<p class="note m mut">${shown === "handing" ? `The chat of step ${cur.n} is writing its handoff note.` : "No handoff note: the handoff run did not finish."}</p>`;
  return `<div class="askbox${tn === "y" ? "" : " ho"}"><span class="st ${tn}">${taskMark({ ...t, state: shown })}${word} <span class="lc">· step ${cur.n}</span></span>
    ${body}<div class="lr">${d.handoff ? '<button class="btn you" data-tact="next" title="A new task seeded with the handoff note">Start next task</button>' : ""}
    ${cur.session ? `<button class="btn" data-open="${esc(cur.session)}">Open step ${cur.n}</button>` : ""}</div><div id="ta-msg" class="say"></div></div>`;
}

// -- the plan (plan 24): plan.md by heading, one fold each; the plan is words and folds, never cells ---------------
function splitHeads(text, lead) {  // [{title, body}] split on lines that start with `lead`; a fenced block never splits
  const out = [{ title: "", body: [] }];
  let fence = false;
  for (const line of String(text || "").split("\n")) {
    if (/^\s*```/.test(line)) fence = !fence;
    if (!fence && line.startsWith(lead)) out.push({ title: line.slice(lead.length).trim(), body: [] });
    else out[out.length - 1].body.push(line);
  }
  return out;
}
function planSections(text) { return splitHeads(text, "## ").filter((x) => x.title).map((x) => ({ title: x.title, body: x.body.join("\n").trim() })); }
function mdBlock(text) {  // lists, code blocks as written (pre.text, never re-flowed), lines as paragraphs
  let out = "", list = "", fence = null;
  const shut = () => { if (list) out += `</${list}>`; list = ""; };
  for (const line of String(text || "").split("\n")) {
    if (/^\s*```/.test(line)) {
      if (fence === null) { shut(); fence = []; } else { out += `<pre class="text">${esc(fence.join("\n"))}</pre>`; fence = null; }
      continue;
    }
    if (fence) { fence.push(line); continue; }
    const li = /^\s*(?:([-*])|\d+[.)])\s+(.*)$/.exec(line);
    if (li) {
      const k = li[1] ? "ul" : "ol";
      if (list !== k) { shut(); out += `<${k}${k === "ul" ? ' class="mono"' : ""}>`; list = k; }
      out += `<li>${esc(li[2])}</li>`;
      continue;
    }
    shut();
    if (line.trim()) out += `<p>${esc(line.trim())}</p>`;
  }
  if (fence) out += `<pre class="text">${esc(fence.join("\n"))}</pre>`;
  shut();
  return out;
}
function stepBody(text) {  // a ### Step N section or a sub-plan: Files, Actions, Tests, Done check as labelled blocks
  const bits = [];
  let fence = false;
  for (const line of String(text || "").split("\n")) {
    if (/^\s*```/.test(line)) fence = !fence;
    const m = !fence && /^#{2,4} (.*)$/.exec(line);
    if (m) bits.push({ title: m[1].trim(), body: [] });
    else (bits.length ? bits[bits.length - 1] : bits[bits.push({ title: "", body: [] }) - 1]).body.push(line);
  }
  return bits.map((b) => (b.title ? `<span class="lbl s">${esc(b.title)}</span>` : "") + mdBlock(b.body.join("\n"))).join("");
}
// -- plan 23: the Handoff fold, its facts, the chip's block parser ---------------------------------
function fold(label, info, body, o = {}) {  // a head button and a body; o.cls, o.tone ("r" | "y"), o.open, o.title; the open state outlives a redraw
  const open = foldState.has(label) ? foldState.get(label) : !!o.open;
  return `<div class="fold${o.cls ? " " + o.cls : ""}"><button class="fh" data-fold aria-expanded="${open}"${o.title ? ` title="${esc(o.title)}"` : ""}><span class="lbl">${label}</span><span class="fi${o.tone ? " " + o.tone : ""}">${info}</span><span class="car">▾</span></button><div class="fb"${open ? "" : " hidden"}>${body}</div></div>`;
}
const HEADS = { "## Goal": "goal", "## Findings": "findings", "## Files touched": "files", "## Troubleshooting": "trouble",
                "## Open questions": "questions", "## Next": "next" };  // tasks.HEADINGS
const normItem = (line) => String(line).trim().replace(/^[-*]\s*/, "").split(/\s+/).join(" ");  // compact._item
function handoffSections(text) {  // a note, a brief or a HANDOFF block -> its six headings; a four-heading note gives four
  const h = { goal: "", findings: [], files: [], trouble: [], questions: [], next: "" };
  const body = String(text || "").replace(/^[\s\S]*?\nHANDOFF\n/, "\n").replace(/\nEND HANDOFF[\s\S]*$/, "");
  let key = null;
  for (const line of body.split("\n")) {
    if (HEADS[line.trim()]) { key = HEADS[line.trim()]; continue; }
    const item = normItem(line);
    if (!key || !item || /^\(?(none|n\/a|none recorded)\)?\.?$/i.test(item)) continue;
    if (key === "goal" || key === "next") h[key] += (h[key] ? "\n" : "") + item;
    else h[key].push(item);
  }
  return h;
}
function headingBlock(h, cut = [], open = ["goal", "findings", "questions", "next"], whole = false) {
  // the six headings; `cut`: finding items the brief pass left out (brief_meta.cut), struck in place with a `cut` tag
  const li = (x) => cut.includes(x) ? `<li class="cut"><span class="tag">cut</span> <s>${esc(x)}</s></li>` : `<li>${esc(x)}</li>`;
  const ul = (items, mono = false) => `<ul${mono ? ' class="mono"' : ""}>${items.map(li).join("")}</ul>`;
  const count = (items) => { const c = items.filter((x) => cut.includes(x)).length;
    return c ? `${items.length - c} kept · ${c} cut` : `${items.length} ${items.length === 1 ? "line" : "lines"}${whole ? " · whole" : ""}`; };
  const sec = (key, label, info, body) => open.includes(key) ? `<div class="hsec"><span class="lbl">${label}<span class="m">${info}</span></span>${body}</div>` : fold(label, info, body, { cls: "hf" });
  const base = (p) => p.replace(/^.*\//, "").replace(/ \(.*$/, "");
  return `<div class="hb">${sec("goal", "Goal", "", `<p>${esc(h.goal) || "(none)"}</p>`)}
    ${sec("findings", "Findings", count(h.findings), ul(h.findings))}
    ${sec("files", "Files touched", h.files.length ? `${h.files.length} · ${h.files.slice(0, 2).map(base).map(esc).join(", ")}${h.files.length > 2 ? " +" + (h.files.length - 2) : ""}` : "none", ul(h.files, true))}
    ${sec("trouble", "Troubleshooting", h.trouble.length ? count(h.trouble) : "none", ul(h.trouble))}
    ${h.questions.length ? sec("questions", "Open questions", `<span class="y">${h.questions.length} open</span>`, ul(h.questions)) : ""}
    ${sec("next", "Next", "", `<p>${esc(h.next) || "(none)"}</p>`)}</div>`;
}
function handoffBlock(text) {  // the last HANDOFF ... END HANDOFF of a reply: [before, block] or null (runs.chat may cut a long reply)
  const t = String(text || ""), a = t.lastIndexOf("\nHANDOFF\n"), b = t.lastIndexOf("\nEND HANDOFF");
  return a >= 0 && b > a ? [t.slice(0, a), t.slice(a + 9, b)] : null;
}
function factsFold(f, text) {  // the facts the service read when the step ended: never compacted (README 3.4)
  if (!f && !text) return "";
  const fail = f && f.tests.startsWith("FAIL");
  const info = f ? `${f.files} ${f.files === 1 ? "file" : "files"} +${f.plus} -${f.minus}${f.tests ? " · " + esc(f.tests) : ""}` : "read";
  return fold("Facts", info, `<p class="mono">${esc(text || "").replace(/\n/g, "<br>")}</p>`,
              { cls: "facts", tone: fail ? "r" : "", open: fail, title: "git diff --stat from the step's start to its end, and its last test command: code reads them, no model" });
}
function handoffFold(t, d, n, sn, meta, nextStep) {
  const brief = (d.briefs || {})[String(n)] || "", raw = (d.notes || {})[String(n)] || "";
  const sent = handoffSections(brief), wrote = handoffSections(raw), cut = (meta && meta.cut) || [];
  const words = meta ? meta.sent_w : brief.split(/\s+/).filter(Boolean).length;
  const label = nextStep ? `Handoff for ${two(nextStep.n)}` : "Last handoff";
  const info = `${words} w${meta && meta.fallback ? ' · <span class="y">as written</span>' : ""} · Next: ${esc(sent.next.split("\n")[0])}`;
  const head = meta ? `<div class="hd"><span class="m" title="${esc(meta.fallback ? "the brief pass failed: " + meta.fallback + "; code cut the note" : `by ${meta.by}, ${meta.turns} turns, $${money(meta.cost)}`)}">${meta.fallback ? "sent as written, cut by code" : `compacted from ${meta.raw_w} w`}</span>
      <span class="link m" data-tact="raw">${rawOpen ? "as sent" : `as ${two(n)} wrote it`}</span></div>` : "";
  const body = rawOpen ? headingBlock(wrote, cut, ["goal", "findings", "trouble", "questions", "next"]) : headingBlock(sent, [], undefined, true);
  return `<div class="blk">${fold(label, info, head + body + factsFold(sn && sn.facts, (d.facts || {})[String(n)]))}</div>`;
}
function pfold(key, label, info, body, o = {}) {
  const open = planOpen.has(key);
  return `<div class="fold${o.cls ? " " + o.cls : ""}"><button class="fh" data-tact="pfold" data-key="${esc(key)}" aria-expanded="${open}"><span class="lbl">${label}</span><span class="fi">${info}</span><span class="car">${open ? "▴" : "▾"}</span></button><div class="fb"${open ? "" : " hidden"}>${body}</div></div>`;
}
const partText = (d, n) => String((d.parts || {})[n] || "").replace(/^# Part [^\n]*\n+/, "");
function planRowHtml(t, d, cur) {  // after the chain: closed it is one line; open, the plan by heading and the current step's section
  const p = t.plan;
  if (!p) return "";
  const parts = p.parts || [], split = parts.length > 0, words = Number(p.words || 0).toLocaleString("en"), curN = cur ? cur.n : 0;
  const closed = `from ${two(p.from)} design · ` + (split ? `${parts.length} sub-plans · ${words} w` : `${words} w · never cut`);
  let body = "";
  for (const sc of planSections(d.plan)) {
    if (split && sc.title === "Sub-plans") continue;
    if (!split && sc.title === "Steps") {
      const subs = splitHeads(sc.body, "### ").filter((x) => x.title);
      body += `<span class="lbl">Steps · ${subs.length}</span>` + subs.map((x) => {
        const mine = Number((/^Step (\d+)/.exec(x.title) || [])[1]) === curN, text = x.body.join("\n").trim();
        return mine ? `<div class="hsec"><span class="lbl">${esc(x.title)} <span class="tg n">this step</span></span>${stepBody(text)}</div>`
          : pfold("st:" + x.title, esc(x.title), "", stepBody(text), { cls: "hf" });
      }).join("");
      continue;
    }
    body += pfold("s:" + sc.title, esc(sc.title), "", mdBlock(sc.body), { cls: "hf" });
  }
  if (split) {
    const stepOf = (n) => t.steps.find((s) => s.part === n);
    const rows = parts.map((x) => {
      const st = stepOf(x.n), mine = st && st.n === curN;
      const [word, tn] = !st ? ["planned", "q"] : st.state === "done" ? ["done", "g"] : st.state === "waiting" || st.state === "failed" ? [st.state, "y"] : st.state === "running" ? ["running", ""] : ["planned", "q"];
      const sub = [x.hard ? '<span class="tg" title="the designer judged this part hard: a stronger rung for this step alone">hard</span>' : "", (x.depends || []).length ? `depends on ${esc(x.depends.join(", "))}` : "", `owns ${esc((x.owns || []).join(", "))}`].filter(Boolean).join(" · ");
      return `<div class="prt${mine ? " cur" : ""}"><span class="o">${x.n}</span><span class="tt">${esc(x.title)}</span><span class="m mut">${st ? two(st.n) + " " : ""}${esc(x.kind)} · <span class="${tn}">${word}</span></span><span class="sub">${sub}</span></div>`;
    }).join("");
    const mine = parts.find((x) => { const st = stepOf(x.n); return st && st.n === curN; });
    body += `<span class="lbl">Sub-plans · ${parts.length}</span><div class="parts">${rows}</div>`
      + (mine ? `<div class="hsec"><span class="lbl">Part ${mine.n} · ${esc(mine.title)} <span class="tg n">this step</span></span>${stepBody(partText(d, mine.n))}</div>` : "");
  }
  return `<div class="blk">${pfold("plan", "Plan", esc(closed), `<div class="blk">${body || '<p class="m mut" style="margin:0">plan.md is empty.</p>'}</div>`)}</div>`;
}
function confirmLabel(t, row) {  // the one button that answers the wait: the same words in the askbox and the bar
  const why = t.why || "";
  return why.startsWith("replanned:") || why === "plan ready: confirm" ? "Confirm plan" : /^plan .* KB, over /.test(why) ? "Accept"
    : row && row.hold ? "Run anyway" : `Confirm to use ${fableName()}`;
}
function planAsk(t, d, cur, lv, row) {  // the four plan waits (askbox html), or "" when the task waits on something else
  const why = t.why || "", p = t.plan || {}, parts = p.parts || [], n = cur ? cur.n : t.current;
  const b = (lvName, name, cls, label, extra = "") => (lv[lvName] === "" ? `<button class="btn${cls}" data-tact="${name}"${extra}>${label}</button>` : "");
  const stop = b("stop", "stop", " stop", "Stop"), head = (word, sub) => `<span class="st y">${sprite("waiting")}${word} <span class="lc">· ${sub}</span></span>`;
  const sizeText = `${parts.length ? parts.length + " sub-plans · " : ""}${Number(p.words || 0).toLocaleString("en")} w`;
  if (t.state !== "waiting") return "";
  if (why.startsWith("asks: Plan gap:")) {
    const q = why.slice("asks: Plan gap:".length).trim();
    return `<div class="askbox">${head("Plan gap", `step ${two(n)} stopped, nothing chosen`)}<div class="q">${esc(q)}</div>
      <textarea class="in" id="t-answer" rows="3" aria-label="Answer" placeholder="Your answer joins the plan's Decisions and continues step ${two(n)}."></textarea>
      <div class="lr">${b("answer", "gapanswer", " you", "Send answer")}${b("redo", "redo", "", "Redo design", ' title="Runs the design step again with this question; the steps still planned are rebuilt, the done ones stay"')}
      ${cur && cur.session ? `<button class="btn" data-open="${esc(cur.session)}">Open step ${n}</button>` : ""}</div>
      <div class="say">A writer never decides for the plan: your answer is written under Decisions as "Fred, ${new Date().toISOString().slice(0, 10)}: ...".</div><div id="ta-msg" class="say"></div></div>`;
  }
  if (why === "plan ready: confirm") {
    const sel = parts.length ? `<select id="t-editpart" aria-label="Which text">${[`<option value="0">index</option>`, ...parts.map((x) => `<option value="${x.n}"${x.n === planEditPart ? " selected" : ""}>part ${x.n}: ${esc(x.title)}</option>`)].join("")}</select>` : "";
    const text = planEditPart ? partText(d, planEditPart) : d.plan;
    const ed = planEdit ? `<div class="edbox">${sel}<textarea class="in" id="t-edit" rows="9" aria-label="plan.md" spellcheck="false">${esc(text)}</textarea>
      <div class="lr"><button class="btn go sm" data-tact="saveplan" title="Writes the plan through the service; the task folder stays the service's">Save</button></div></div>` : "";
    return `<div class="askbox">${head("Plan ready", sizeText)}
      <div class="lr">${b("confirm", "confirm", " you", confirmLabel(t, row))}<button class="btn" data-tact="edit" aria-expanded="${planEdit}">Edit</button>${stop}</div>${ed}
      <div class="say">plan_hold is on: the plan waits for you before any step runs.</div><div id="ta-msg" class="say"></div></div>`;
  }
  if (/^plan .* KB, over /.test(why)) {
    const kb = (/^plan ([\d.,]+) KB/.exec(why) || [])[1] || "";
    return `<div class="askbox">${head("Plan is large", kb + " KB")}<div class="q">${esc(why)}</div>
      <div class="lr">${b("confirm", "confirm", " you", confirmLabel(t, row))}${b("redo", "redo", "", "Redo design")}${stop}</div>
      <div class="say">Nothing is cut: the whole plan goes to every later step.</div><div id="ta-msg" class="say"></div></div>`;
  }
  if (why.startsWith("replanned:")) {
    const r = t.replan || { before: [], after: [], added: [], dropped: [] };
    const line = (x) => `${esc(x.kind)}: ${esc(x.goal)}`;
    const dropped = (r.dropped || []).map((i) => r.before[i]).filter(Boolean);
    return `<div class="askbox">${head("Replanned", `after step ${two(r.step || n)}`)}
      ${r.why ? `<div class="q">${esc(r.why)}</div>` : ""}
      <div class="plan1"><span class="lbl">New plan · ${r.after.length} steps <span class="m">(was ${r.before.length})</span></span>
        <ol>${r.after.map((x, k) => `<li class="${(r.added || []).includes(k) ? "add" : "old"}">${line(x)}</li>`).join("")}</ol></div>
      ${dropped.length ? `<div class="plan1"><span class="lbl">Dropped · ${dropped.length}</span><ol>${dropped.map((x) => `<li class="drop">${line(x)}</li>`).join("")}</ol></div>` : ""}
      <div class="lr">${b("confirm", "confirm", " you", confirmLabel(t, row))}${b("keep", "keep", "", "Keep old plan")}${stop}</div>
      <div class="say">replan_auto is off: a changed plan waits for you.</div><div id="ta-msg" class="say"></div></div>`;
  }
  return "";
}

function drawTask() {
  const d = taskData;
  if (!d) {
    setHtml($("tscroll"), d === false ? '<p class="mut">This task is gone: it was cleared or its folder was removed. <span class="link" data-go="list">Back to the list</span></p>'
      : `<span class="loading"><span class="cells">${cellsHtml(["f live", "", "", "", "", ""])}</span>Reading the task</span>`);
    setHtml($("tbar"), "");
    return;
  }
  const t = d.task, lv = d.levers || {}, cur = t.steps.find((s) => s.n === t.current);
  const dir = taskDir(t.id), row = (snap.tasks || []).find((x) => x.id === t.id) || {}, shown = row.id ? taskShown(row) : t.state;
  const [word, tn] = TASK_WORD[shown] || TASK_WORD.running;
  const paused = t.owner === "fred" && (t.state === "running" || t.state === "waiting") ? " · paused" : "";
  const head = `<div class="head tk"><span class="st ${tn}">${taskMark({ ...t, state: shown })}${word} <span class="lc">· ${ago(snap.now - t.updated)}${paused}</span></span>
    <h2>${esc(t.title)}</h2>
    <div class="where"><span class="m">${esc(t.project)} / effort: ${esc(t.effort)} · $${money(row.cost)}</span></div>
    ${dir ? `<div class="m tpath" title="${esc(dir)}">${esc(dir)}</div>` : ""}</div>${row.paused_after
    ? `<p class="note m">Paused: step ${row.paused_after} ended. Nothing starts until you Resume.</p>` : ""}`;
  const sl = d.step_levers || {}, ask = cur && cur.session ? row.asks : "", hand = cur && cur.session ? row.hand_off : "";
  const planBox = planAsk(t, d, cur, lv, row);
  const why = t.state === "handed" && cur ? handedBox(d, t, cur, shown)
    : planBox ? planBox
    : ask || hand  // the step's question or hand-off hint, answered here; Hub.levers says when (step_levers)
    ? `<div class="askbox"><span class="st y">${sprite("waiting")}${ask ? "Asks you" : "Hand off"} <span class="lc">· step ${cur.n}</span></span>
       ${ask ? `<div class="q">${esc(ask)}</div>
       <textarea class="in" id="t-answer" rows="3" aria-label="Answer" placeholder="Your answer continues step ${cur.n} in its chat."></textarea>` : ""}
       ${hand ? `<p class="note m"><span class="y">${esc(handText(hand))}</span>${sl.handoff ? ` · <span class="mut">Hand off off: ${esc(sl.handoff)}</span>` : ""}</p>` : ""}
       <div class="lr">${ask ? '<button class="btn you" data-tact="answer">Send answer</button>' : ""}
       ${sl.handoff === "" ? '<button class="btn go" data-tact="handoff" title="Hand the task over: the chat of this step writes its handoff note, nothing more starts">Hand off</button>' : ""}
       <button class="btn" data-open="${esc(cur.session)}">Open step ${cur.n}</button></div><div id="ta-msg" class="say"></div></div>`
    : (t.state === "waiting" || t.state === "stuck") && t.why
    ? `<div class="askbox${t.state === "stuck" ? " r" : ""}"><span class="st ${tn}">${sprite(t.state)}${word}</span><div class="q">${esc(t.why)}</div></div>`
    : t.why ? `<p class="note m">${esc(t.why)}</p>` : "";
  const notes = new Map((row.steps || []).map((x) => [x.n, x.note]));  // the note state is in the snapshot row, not task.json
  const chain = `<div class="blk"><span class="lbl">Steps · ${t.steps.length}</span><div class="chain">${t.steps.map((s) => chainRow(t, { ...s, note: notes.get(s.n) || "" })).join("")}</div>
    ${t.cleared ? '<p class="m mut" style="margin:0">cleared: notes and streams removed</p>' : ""}</div>`;
  const planRow = planRowHtml(t, d, cur);
  const n = t.last_good, sn = t.steps.find((x) => x.n === n), meta = (sn && sn.brief_meta) || null;
  const nextStep = t.steps.find((x) => x.n === n + 1);
  const brief = t.briefing ? `<div class="blk"><span class="loading"><span class="cells">${cellsHtml(["f live", "", "", "", "", ""])}</span>Compacting the handoff of ${two(t.briefing)}</span></div>`
    : n ? handoffFold(t, d, n, sn, meta, nextStep) : "";
  setHtml($("tscroll"), head + why + chain + planRow + brief);
  const b = (name, cls, label) => `<button class="btn${cls}" data-tact="${name}">${label}</button>`;
  let buttons = "";
  if (lv.stop === "") buttons += b("stop", " stop", "Stop");
  if (lv.pause === "") buttons += b("pause", "", "Pause");
  if (lv.resume === "") buttons += b("resume", " go", "Resume");
  if (lv.retry === "") buttons += b("retry", " go", "Retry");
  if (t.state === "stuck" && lv.redo === "") buttons += b("redo", "", "Redo design");  // a bad plan twice: plan again
  if (lv.confirm === "" && !planBox) buttons += b("confirm", " you", confirmLabel(t, row));  // the plan waits have it in the askbox
  if (lv.done === "") buttons += b("done", "", "Mark done");
  if (lv.clear === "") buttons += b("clear", "", "Clear");
  const off = new Map();  // the reasons, one line each: "Retry, Clear off: task is running"
  const keys = ["stop", "pause", "retry", "clear", ...(paused ? ["resume"] : [])];  // why Resume is off, while paused
  for (const k of keys) if (lv[k]) off.set(lv[k], [...(off.get(lv[k]) || []), k[0].toUpperCase() + k.slice(1)]);
  const reasons = [...off].map(([why, names]) => `${names.join(", ")} off: ${why}`).join(" · ");
  setHtml($("tbar"), `${buttons ? `<div class="lr">${buttons}</div>` : ""}<div class="say">${esc(reasons)}</div><div id="t-msg" class="say"></div>`);
}

async function renderTaskPage() {  // GET /api/task when the task's row changed; the drawing follows every snapshot
  const row = (snap.tasks || []).find((x) => x.id === taskId), at = row && row.steps.find((x) => x.n === row.current);
  const run = at && snap.sessions.find((x) => x.id === at.session);
  const sig = row ? [row.updated, row.state, row.owner, row.why, row.briefing, row.cleared, row.cost, row.steps.map((x) => x.note + x.part).join(), row.plan ? row.plan.words : "", row.asks, row.hand_off, run ? run.state + run.run_live : ""].join("|") : "gone";
  if (sig !== taskSig) {
    taskSig = sig;
    const id = taskId, data = await api("/api/task?id=" + encodeURIComponent(id)).catch(() => false);
    if (taskId !== id || taskSig !== sig || page !== "task") return;
    taskData = data;
  }
  drawTask();
}

async function openTask(id) {
  if (form === "pill") await setForm("open");
  taskId = id;
  taskData = null;
  rawOpen = false;
  foldState.clear();
  planOpen = new Set();
  planEdit = false;
  planEditPart = 0;
  showPage("task");
}

let tArmTimer = null;
async function taskAct(name, button) {
  if (name === "raw") { rawOpen = !rawOpen; drawTask(); return; }  // page only: the brief or the raw note
  if (name === "next") return startNext(button.dataset.tid || taskId, button);  // the card's button too
  if (name === "pfold") { const k = button.dataset.key; if (planOpen.has(k)) planOpen.delete(k); else planOpen.add(k); drawTask(); return; }
  if (name === "edit") { planEdit = !planEdit; drawTask(); return; }
  if (name === "saveplan") return savePlan(button);
  if (name === "gapanswer") return gapAnswer(button);
  if (!taskId && !button.dataset.tid) return;
  const arm = { stop: "Stop the task? Click again", clear: "Delete its notes and streams? Click again",
    handoff: "Hand off ends the task? Click again", done: "Mark the task done? Click again" }[name];
  if (arm && !button.dataset.armed) {  // two clicks: a stop loses the running step, a clear deletes the notes
    button.dataset.armed = "1";
    button.dataset.label = button.textContent;
    button.textContent = arm;
    clearTimeout(tArmTimer);
    tArmTimer = setTimeout(() => { delete button.dataset.armed; button.textContent = button.dataset.label; }, 3000);
    return;
  }
  if (name === "answer" || name === "handoff") return stepAct(name, button);  // session levers on the step's chat
  button.disabled = true;
  try {
    await api("/api/task/" + name, { task: button.dataset.tid || taskId });
    if (name === "clear") { taskId = null; showPage("list"); return; }
    taskSig = "";  // redraw now, not at the next snapshot
    if (page === "task") renderTaskPage();
  } catch (e) {
    button.disabled = false;
    const msg = page === "task" ? $("ta-msg") || $("t-msg") : null;
    if (!msg) button.textContent = "Failed: " + e.message;
    else msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

async function gapAnswer(button) {  // a Plan gap: the answer joins the plan's Decisions and continues the step (POST /api/task/answer)
  const box = $("t-answer"), text = box ? box.value.trim() : "";
  if (!text) return;
  button.disabled = true;
  try {
    await api("/api/task/answer", { task: taskId, text });
    box.value = "";
    taskSig = "";
    renderTaskPage();
  } catch (e) {
    button.disabled = false;
    const msg = $("ta-msg");
    if (msg) msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

async function savePlan(button) {  // Fred's edit of the index or of a part, through the service only
  const box = $("t-edit");
  if (!box) return;
  button.disabled = true;
  try {
    await api("/api/task/plan", { task: taskId, text: box.value, part: planEditPart });
    planEdit = false;
    taskSig = "";
    renderTaskPage();
  } catch (e) {
    button.disabled = false;
    const msg = $("ta-msg");
    if (msg) msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

async function startNext(id, button) {  // a handed-off task: the new-task box seeded with its handoff note; nothing runs yet
  const row = (snap.tasks || []).find((x) => x.id === id), cur = row && row.steps.find((x) => x.n === row.current);
  if (!cur || !cur.session) return;
  button.disabled = true;
  try {
    seedBox(await api("/api/brief?session=" + encodeURIComponent(cur.session) + "&kind=next"));
  } catch (e) {
    const msg = $("ta-msg");
    if (msg && page === "task") msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
    else button.textContent = "Failed: " + e.message;
  }
  button.disabled = false;
}

async function stepAct(name, button) {  // the current step's question or hand-off, from the Task page: a session lever
  const t = taskData && taskData.task, cur = t && t.steps.find((s) => s.n === t.current), box = $("t-answer");
  const text = name === "answer" && box ? box.value.trim() : "";
  if (!cur || !cur.session || (name === "answer" && !text)) return;
  button.disabled = true;
  try {
    await api("/api/" + (name === "answer" ? "continue" : "handoff"), name === "answer" ? { session: cur.session, text } : { session: cur.session });
    if (box) box.value = "";
    taskSig = "";  // redraw now, not at the next snapshot
    renderTaskPage();
  } catch (e) {
    button.disabled = false;
    const msg = $("ta-msg");
    if (msg) msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
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
const fillsOpen = new Set();  // plan 18: the model rows opened to their three windows
const WIN = ["day", "week", "month"];
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
        .map(([f, c]) => `<span>${esc(f)} ${r.cost ? Math.round(100 * c / r.cost) : 0} %</span>`).join("")
    + Object.entries(r.unknown || {}).map(([k, n]) => `<span>${esc(k)}: cost unknown · ${n} ${n === 1 ? "run" : "runs"}</span>`).join("");
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
function storageLine() {  // the data folder's size by subfolder; orange over storage_warn_mb
  const st = usage.storage;
  if (!st || !st.total) return "";
  const mb = (n) => (n >= 10 * 1048576 ? Math.round(n / 1048576) : (n / 1048576).toFixed(1)), over = st.total > usage.storage_warn_mb * 1048576;
  return `<p class="ufoot ustore m${over ? " y" : ""}">data folder ${mb(st.total)} MB: runs ${mb(st.runs)}, events ${mb(st.events)}, tasks ${mb(st.tasks)}, preps ${mb(st.preps)}, other ${mb(st.other)}</p>`;
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
  setHtml($("uscroll"), usageHead() + usageFills() + usageCalendar() + usageDay() + usageChart() + usageFails() + storageLine()
    + `<p class="ufoot">Estimated from the transcripts at the list prices in config.json, fast mode 2x; other harnesses' usage x
       their price row in "prices", and runs without usage or without a price row count as unknown, never as zero. Kept from ${esc(since)}:
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
  const t = e.target.closest("[data-fill],[data-day],[data-col],[data-range],[data-metric],[data-umonth]");
  if (!t || t.disabled) return;
  if (t.dataset.fill) { if (!fillsOpen.delete(t.dataset.fill)) fillsOpen.add(t.dataset.fill); }  // plan 18: the three windows
  else if (t.dataset.day) uPicked = t.dataset.day;
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
  if (name === "list") { backTo = null; showPage("list"); }
  if (name === "back") goBack();
  if (name === "new") { if (form === "pill") await setForm("open"); showPage("list"); $("c-prompt").focus(); }
  if (name === "needs") {
    if (scope) pick("");
    const n = $("needsec");
    if (n) n.scrollIntoView({ block: "start", behavior: "smooth" });
  }
  if (name === "moredone") { doneOpen = true; render(); }
  if (name === "cleardraft") { draft = ""; $("c-prompt").value = ""; draftKept = false; saveDraft(); renderCompose(); $("c-prompt").focus(); }
  if (name === "empties") { emptyOpen = !emptyOpen; render(); }
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

async function rawRun() {
  const text = $("c-prompt").value.trim();
  if (!text || !runnable() || !await doRun(project, text, cfg.default_model, rawEffort(), "")) return;
  draft = "";
  draftKept = false;
  $("c-prompt").value = "";
  saveDraft();
}

document.addEventListener("click", async (e) => {
  if (!$("pop").hidden && !e.target.closest("#pop") && !e.target.closest("[data-pick]")) closePicker();
  const fb = e.target.closest("[data-fold]");  // plan 23: a fold head toggles its body and remembers it
  if (fb) {
    const open = fb.getAttribute("aria-expanded") !== "true";
    fb.setAttribute("aria-expanded", String(open));
    fb.nextElementSibling.hidden = !open;
    foldState.set(fb.querySelector(".lbl").textContent, open);
    return;
  }
  const swb = e.target.closest("[data-setting]");
  if (swb && !settingBusy) {
    settingBusy = true; settingErr = ""; pickRows();
    try { cfg.handoff_auto = (await api("/api/setting", { key: "handoff_auto", value: swb.getAttribute("aria-checked") !== "true" })).value; }
    catch (err) { settingErr = err.message; }
    settingBusy = false; pickRows();
    return;
  }
  if (e.target.matches("img.thumb")) { e.target.closest(".file").classList.toggle("open"); return; }  // enlarge in place
  const t = e.target.closest("[data-prep],[data-go],[data-open],[data-tab],[data-min],[data-act],[data-pact],[data-do],[data-here],[data-proj],[data-pick],[data-harness],[data-models],[data-step],[data-attach],[data-unattach],[data-task],[data-eff],[data-tact],#brief,#today,#overpace");
  if (!t) return;
  if (t.matches(".card") && e.target.closest("[data-stay]")) return;  // typing an answer in a card
  if (t.dataset.open || t.dataset.task) {  // a session opened from a task returns to it, a task opened from a session too
    const card = t.closest(".card.task");
    backTo = t.dataset.open && (t.closest("#tscroll") || card) ? { page: "task", id: card ? card.dataset.task : taskId }
      : t.dataset.task && page === "session" ? { page: "session", id: openId } : null;
  }
  if (t.dataset.eff) setEffort(t.dataset.eff);
  else if (t.dataset.task) openTask(t.dataset.task);
  else if (t.dataset.tact) taskAct(t.dataset.tact, t);
  else if (t.dataset.attach) { pickFor = t.dataset.attach; $("filepick").value = ""; $("filepick").click(); }
  else if (t.dataset.unattach) { att[t.dataset.unattach].splice(Number(t.dataset.k), 1); paintFiles(t.dataset.unattach); }
  else if (t.dataset.prep) prepJob(t.dataset.prep, t.dataset.pdo);
  else if (t.dataset.go) go(t.dataset.go, t);
  else if (t.dataset.do) unblock(t);
  else if (t.dataset.open) openSession(t.dataset.open);
  else if (t.dataset.tab) { tab = t.dataset.tab; const s = current(); if (s) renderProc(s).catch(() => {}); }
  else if (t.dataset.min !== undefined) { tlMin = tlBase() + Number(t.dataset.min); const s = current(); if (s) renderProc(s).catch(() => {}); }
  else if (t.dataset.act) act(t.dataset.act, t);
  else if (t.dataset.pact) prepAct(t.dataset.pact, t);
  else if (t.dataset.here !== undefined) { pick(t.dataset.here); showPage("list"); $("c-prompt").focus(); }
  else if (t.dataset.harness) harnessAct(t);
  else if (t.dataset.models) modelsAct(t);
  else if (t.dataset.proj !== undefined) pick(t.dataset.proj);
  else if (t.dataset.step) step(Number(t.dataset.step));
  else if (t.hasAttribute("data-pick")) { if ($("pop").hidden) openPicker(t); else closePicker(); }
  else if (t.id === "brief") {
    briefOpen = !briefOpen;
    t.setAttribute("aria-expanded", String(briefOpen));
    t.querySelector(".car").textContent = briefOpen ? "▴" : "▾";
    $("more").hidden = !briefOpen;
    saveDraft();
  } else if (t.id === "today" || t.id === "overpace") {  // plan 18: the over-pace line opens the same breakdown
    const open = t.getAttribute("aria-expanded") !== "true";
    $("today").setAttribute("aria-expanded", String(open));
    $("overpace").setAttribute("aria-expanded", String(open));
    $("todaymore").hidden = !open;
  }
});

$("filepick").addEventListener("change", (e) => addFiles(pickFor, [...e.target.files]));
document.addEventListener("error", (e) => {  // an image gone from the transcript or the folder: the chip stays, without it
  if (e.target instanceof HTMLImageElement && e.target.matches("img.thumb")) e.target.remove();
}, true);
document.addEventListener("paste", (e) => {  // a pasted screenshot or copied file joins the box's files
  const files = [...((e.clipboardData && e.clipboardData.files) || [])], key = boxKey(e.target);
  if (files.length && key) { e.preventDefault(); addFiles(key, files); }
});
document.addEventListener("dragover", (e) => { e.preventDefault(); });  // a file dropped anywhere must not open in the page
document.addEventListener("drop", (e) => {
  e.preventDefault();
  if (e.dataTransfer && e.dataTransfer.files.length) addFiles(boxKey(e.target), [...e.dataTransfer.files]);
});

document.addEventListener("dblclick", (e) => {
  if (e.target.closest(".pill .sp")) setForm("open");
  else if (e.target.closest(".top .sp")) setForm("pill");
});

document.addEventListener("input", (e) => {
  if (e.target.id === "c-prompt") { draft = e.target.value; draftKept = false; fail = null; saveDraft(); renderCompose(); }
});

document.addEventListener("change", (e) => {
  if (e.target.id === "t-editpart") {  // the plan editor switches between the index and a part
    planEditPart = Number(e.target.value) || 0;
    const d = taskData, box = $("t-edit");
    if (d && box) box.value = planEditPart ? partText(d, planEditPart) : d.plan;
    return;
  }
  if (e.target.matches("[data-skind]")) {  // the kind decides which harness rungs the row may hold; a pick it cannot hold falls back to Auto
    const sel = e.target.closest("[data-row]").querySelector("[data-smodel]"), cur = sel.value;
    sel.innerHTML = modelOptions(cur, true, e.target.value);
    if (sel.value !== cur) sel.value = "";
  }
  if (e.target.matches("#p-model, [data-smodel], [data-skind]")) stepsChanged();
});

$("popen").addEventListener("click", openFolder);
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
  if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown") && (id === "c-prompt" || e.target.closest("#effort"))) {
    e.preventDefault();  // the slider: Up = more effort
    stepEffort(e.key === "ArrowUp" ? 1 : -1);
    return;
  }
  if (id === "c-prompt" && e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (e.ctrlKey) rawRun();
    else doPrep();
    return;
  }
  if (id === "answer" && e.key === "Enter" && !e.shiftKey && !e.isComposing) {  // Shift+Enter keeps the newline
    e.preventDefault();
    return act("answer", document.querySelector('[data-act="answer"]'));
  }
  if (id === "fu" && e.key === "Enter") return act("continue", document.querySelector('[data-act="continue"]'));
  if (id === "pk" && e.key === "Enter") return unblock(document.querySelector('[data-do="send"][data-where="peek"]'));
  if (id.startsWith("ca-") && e.key === "Enter") return unblock(e.target.closest("[data-stay]").querySelector('[data-do="send"]'));
  if (e.key === "Enter" && e.target.matches(".card[data-open],.card[data-prep],.card[data-task]")) { e.target.click(); return; }
  if (e.ctrlKey && e.key.toLowerCase() === "n") { e.preventDefault(); go("new"); return; }
  if (e.ctrlKey && e.key.toLowerCase() === "p") { e.preventDefault(); openPicker(); return; }
  const inField = ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
  if (e.key === "Escape") {
    if (!$("pop").hidden) closePicker();
    else if (form === "pill") dismissPeek();
    else if (page === "prep") prepAct("back");
    else if (page === "session" || page === "task") goBack();
    else if (page === "usage") showPage("list");
    return;
  }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const d = e.key === "ArrowRight" ? 1 : -1, s = current();
    if (e.target.matches("[data-tab]") && s) {
      tab = TABS[(TABS.findIndex(([k]) => k === tab) + d + TABS.length) % TABS.length][0];
      renderProc(s).then(() => { const f = $("tab-" + tab); if (f) f.focus(); }).catch(() => {});
      e.preventDefault();
    } else if (e.target.matches("[data-eff]")) {  // the slider is a radio group: the arrows move the pick
      stepEffort(d);
      const f = document.querySelector(`[data-eff="${effortPick}"]`);
      if (f) f.focus();
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
  await window.pywebview.api.fit(window.innerWidth);  // Windows' text size zooms the page, not the form
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
  draftKept = !!draft.trim();
  if (draftKept) $("c-prompt").addEventListener("focus", (e) => { setTimeout(() => { if (draftKept) e.target.select(); }); }, { once: true });  // after the click: typing replaces it
  project = (cfg && cfg.project) || "";
  briefOpen = !!(cfg && cfg.brief);
  effortPick = cfg && EFF_LEVELS.includes(cfg.effort) ? cfg.effort : "auto";
  connect();
})();
