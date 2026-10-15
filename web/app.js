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
let page = "list";       // list | session | prep | task | usage | board
let openId = null;
let taskId = null;       // the Task page's task
let taskData = null;     // GET /api/task for it: {task, levers, note, brief}
let taskSig = "";
let backTo = null;       // {page: "task", id} or {page: "session", id}: where the session or Task page's back arrow returns
let rawOpen = false;     // the Task page shows the raw note instead of the brief
const foldLabel = new Map(); // plan 23: fold label -> open, kept across redraws (Handoff, its headings, Facts, Window runs); closed on openTask
let settingBusy = false; // POST /api/setting in flight (the Window runs switch)
let settingErr = "";
let planOpen = new Set(); // the Task page's open plan folds (plan 24); closed on openTask
const grown = new Set();  // plan 25: "<task>:<n>" rows whose ctx gauge line a click opened; cleared in openTask
let scrollCur = false;    // the Task page scrolls its current row into view once per openTask
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
let boardFrom = null;    // {page, id}: where the Board opened from; Esc and the back arrow return there
let boardTask = "";      // the picked task ("" none: the Board picks the newest in scope)
let boardPick = "";      // "" nothing (the Measure table), "t" the task head, "s<n>" a step, "c<n>" the connector after step n
let itab = "chat";       // the step inspector's tab (window.json board_tab)
let boardData = null;    // {id, sig, data}: GET /api/task of boardTask
let boardChat = null;    // {sid, at, chat}: GET /api/chat of the picked step's session
let measureData = null;  // {project, at, data}: GET /api/measure
let foldState = {};      // window.json folds: {key: open}
const toolOpen = new Set();  // "<session>:<k>": the chat's tool rows Fred opened (not kept)
const BOARD_KEYS = new Set(["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Escape"]);
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
  if (boardFrom && name !== "board" && !(name === "session" && backTo && backTo.page === "board")) {  // plan 27 B9: the Board left by any other way than closeBoard
    boardFrom = null;
    if (backTo && backTo.page === "board") backTo = null;
    if (native()) window.pywebview.api.board(false).catch(() => {});  // the compact size again; the service drops _board
  }
  page = name;
  closePicker();
  document.querySelectorAll("[data-page]").forEach((p) => { p.hidden = p.dataset.page !== name; });
  leversSig = "";
  taskSig = "";
  procShown = "";
  if (name === "session") $("sscroll").scrollTop = 0;
  if (name === "task") $("tscroll").scrollTop = 0;
  if (name === "board") { $("bchain").scrollTop = 0; boardData = null; }
  clearInterval(usageTimer);
  usageTimer = null;
  if (name === "usage") { $("uscroll").scrollTop = 0; loadUsage(); usageTimer = setInterval(loadUsage, 60000); }
  if (name === "models") { $("mscroll").scrollTop = 0; loadModels(); }  // plan 26: config.json as it is now
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
  else if (page === "board") renderBoard();
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
  $("boardbtn").hidden = !native() && innerWidth < 700;  // plan 25: in a browser the Board button shows once the viewport is wide
  $("boardbtn").classList.toggle("on", innerWidth >= 700);
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
  draftTimer = setTimeout(() => api("/api/draft", { text: draft, project, brief: briefOpen, effort: effortPick, board_tab: itab, folds: foldState }).catch(() => {}), 600);
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
  if (!q) html += `<div class="pset"><span class="lbl row">Settings<button class="link" data-go="models" title="Which model does each kind of step, the tiers' rungs, and the tuning numbers">Models and tuning &#8250;</button></span></div>` + harnessHtml() + `<div class="pset">${windowRunsFold()}</div>`;
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
  setHtml($("proc"), `<div class="pane" id="pane" tabindex="0">${chatPane(chat, id, "chat", { prompt: true, step: (oldStep(id) || [])[1] })}</div>`, { sel: ".pane", end: true, reset: procShown !== id + "|old" });
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
const AGENT_NAME = { claude: "Claude", codex: "Codex", opencode: "OpenCode", cmd: "Command Code" };
function toolsRow(list, key) {  // consecutive tool events fold into one row; a failed exit comes first, so an ellipsis never hides it
  const kinds = [...new Set(list.map((t) => t.split(/[ ·]/)[0]))].join(", ");
  const bad = list.map((t) => (t.match(/exit [1-9]\d*/) || [])[0]).find(Boolean), open = toolOpen.has(key);
  return `<button class="tools" data-fold data-tkey="${esc(key)}" aria-expanded="${open}"><span>${list.length} tool ${list.length === 1 ? "event" : "events"}${bad ? ` · <span class="r">${esc(bad)}</span>` : ""} · ${esc(kinds)}</span><span class="car">▾</span></button>
    <div class="tlist"${open ? "" : " hidden"}>${list.map((t) => `<span${/exit [1-9]/.test(t) ? ' class="r"' : ""}>${esc(t)}</span>`).join("")}</div>`;
}
function promptRow(text, o, key) {  // a task step's first turn is the prompt the service built: folded, not labelled You
  const s = o.step || {}, w = String(text || "").split(/\s+/).filter(Boolean).length, open = foldOpen("prompt", false);
  const from = s.n > 1 ? `goal and the handoff of ${two(s.n - 1)}` : "goal and the context pack";
  return `<div class="turn you prompt"><button class="fh" data-fold data-fkey="prompt" aria-expanded="${open}"><span class="lbl">Prompt</span><span class="fi">${from} · ${w} w</span><span class="car">▾</span></button><p${open ? "" : " hidden"}>${esc(text)}</p></div>`;
}
function handoffSplit(text, o, last) {  // a turn that ends with the HANDOFF block: the words before it, the chip, its Next line
  const t = String(text || ""), at = t.search(/(^|\n)HANDOFF\s*\n/);
  if (at < 0) return chatHtml(t);
  if (!o.step) return claudeTurn(t);  // a hand chat's skill block keeps plan 23's chip
  const block = t.slice(at), next = (block.match(/## Next\s*\n+([^\n]*)/) || [, ""])[1];
  const w = block.split(/\s+/).filter(Boolean).length;
  return `${chatHtml(t.slice(0, at))}<span class="hchip">HANDOFF block · <b>${w} w</b> · six headings ${o.board ? "in the Handoff tab" : "on the Task page"}</span>${next ? `<p>Next: ${esc(next)}</p>` : ""}`;
}
function stepOf(id) {  // the task step whose session, or one of whose attempts, is this session
  for (const t of snap.tasks || []) for (const x of t.steps) if (x.session === id || (x.attempts || []).some((a) => a.session === id)) return x;
  return undefined;
}
function chatPane(chat, sid, source, o = {}) {  // the Chat tab, the session page and the Board's: one grammar (interface 6.1)
  const items = chat.items || [], who = AGENT_NAME[chat.harness || "claude"] || "Claude", out = [];
  const lastClaude = items.map((i) => i.role).lastIndexOf("claude");
  let tools = [], k = 0, result = "";
  const flush = () => { if (tools.length) { out.push(toolsRow(tools, `${sid}:${k++}`)); tools = []; } };
  items.forEach((i, n) => {
    if (!["you", "claude", "note", "result"].includes(i.role) || (i.role === "note" && i.text !== "stopped")) { tools.push(i.text); return; }
    if (i.role === "result") { result = i.text || result; return; }
    flush();
    if (i.role === "you" && n === 0 && o.prompt) { out.push(promptRow(i.text, o, `${sid}:p`)); return; }
    if (i.role === "note") { out.push('<p class="src">stopped</p>'); return; }
    const writing = chat.live && n === lastClaude ? ' · writing<span class="cells"><i class="f live"></i></span>' : "";
    const lbl = `<span class="lbl">${i.role === "you" ? "You" : esc(who)}${i.ts ? " · " + hhmm(i.ts) : ""}${writing}</span>`;
    const body = i.role === "claude" ? handoffSplit(i.text, o, n === lastClaude) : i.text ? `<p>${esc(i.text)}</p>` : "";
    out.push(`<div class="turn ${i.role === "you" ? "you" : "claude"}">${lbl}${body}${o.compact ? "" : chatFiles(i.files, i.role, sid)}</div>`);
  });
  flush();
  const foot = chat.source === "window"
    ? "Streamed from this window run." + (chat.start_commit ? ` start ${esc(chat.start_commit.slice(0, 7))} · ${chat.changed == null ? "?" : chat.changed} file(s) changed since.` : "")
    : `Read from the ${esc(source === "?" ? "chat" : source)} transcript, in words and files; tool output stays in Steps.`;
  return `<div class="chat${o.compact ? " compact" : ""}">${out.join("") || '<p class="none">Nothing to show yet. A VS Code or terminal chat shows its turns once a prompt has named its transcript.</p>'}
    <p class="src">${foot}${result ? " · " + esc(result) : ""}</p></div>`;
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
    body = chatPane(chat, s.id, s.source, { prompt: !!taskTag(s), step: stepOf(s.id) });
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
  if (page === "board") return closeBoard();
  const b = backTo;
  backTo = null;
  if (b && b.page === "board") return showPage("board");  // plan 25: no resize, the window is still wide
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
function stepGauge(t, s) {  // the step's context as 15 cells and the figure; unknown is a word (ID-3)
  const ctx = stepCtx(s), live = s.state === "running";
  const cells = ctx == null ? `<b class="mut" title="${esc(ctxUnknown(s))}">unknown</b>`
    : `<span class="cells c30">${cellsHtml(ctxClasses(ctx).filter((_, k) => k % 2 === 0).map((c, k, a) => (live && c && !a[k + 1] ? c + " live" : c)))}</span><b class="${ctxFigTone(ctx)}">${kTokens(ctx)}</b>`;
  const hint = scoutHint(t, s, null);
  return `<span class="gg"><span title="context reached, 1 cell = 10K">ctx ${cells}</span>${hint ? `<span>· ${hint}</span>` : ""}</span>`;
}
function chainRow(t, s) {
  const ran = s.state !== "planned", ctx = stepCtx(s), key = t.id + ":" + s.n;
  const auto = s.n === t.current || s.state === "failed" || s.verdict === "FAIL" || (ctx != null && cfg && ctx >= cfg.gauge[0]);
  const gauge = ran && (auto || grown.has(key)), short = ran && !gauge;
  const tn = s.state === "handed" ? stepCell(t, s) : s.state === "failed" || s.verdict === "FAIL" ? "r" : s.note === "unchecked" ? "w" : s.state === "done" ? "g" : s.state === "running" ? "f" : "";
  const cells = cellsHtml(Array.from({ length: 6 }, (_, k) => (tn === "f" && k === 0 ? "f live" : tn)));
  const verdict = s.verdict ? `<span class="${s.verdict === "FAIL" ? "r" : "g"}">${esc(s.verdict)}${s.verdict === "FAIL" && s.verdict_detail ? " " + esc(s.verdict_detail) : ""}</span>` : "";
  const waits = t.state === "waiting" && s.n === t.current && /^(plan |replanned:|asks: Plan gap:)/.test(t.why || "");  // a plan wait: the reason, in orange
  const unpriced = ran && costUnknown(s) ? '<span title="no attempt of this step reported a cost">cost unknown</span>' : "";  // plan 27 G7: the words, in the sub line (the cost column is 38 px)
  const sub = [verdict, unpriced, s.retries ? "retry " + s.retries : "", stepTries(s), waits ? `<span class="y">${esc(t.why)}</span>` : esc(s.goal)].filter(Boolean).join(" · ");
  const from = s.part ? `<span class="tg" title="a write step the design step made: sub-plan ${s.part} of ${((t.plan || {}).parts || []).length}">from plan</span>` : "";
  return `<div class="row${s.n === t.current ? " cur" : ""}${short ? " short" : ""}${fresh("c", "t" + t.id + "." + s.n, s.state, 300) && s.state === "done" ? " adv" : ""}${s.note ? " n-" + s.note : ""}"${ran && !auto ? ` data-grow="${s.n}"` : ""}><span class="cells">${cells}</span>
    <span class="nm m">${two(s.n)} ${esc(s.kind)}${from}${s.model ? ` <span class="mdl">${esc(modelText(rungOf(s.harness, s.model), s.effort))}</span>` : ""}${triesHtml(s)}</span>
    <span class="m c">${!ran || costUnknown(s) ? "" : s.cost ? money(s.cost) : ""}</span>
    ${s.session ? `<button class="btn sm" data-open="${esc(s.session)}">Open</button>` : "<span></span>"}
    ${gauge ? stepGauge(t, s) : ""}${short && (s.note === "sent" || s.note === "checked") ? "" : noteChip(s, t)}${sub ? `<span class="sub">${sub}</span>` : ""}</div>`;
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
  const open = o.force ? true : o.key ? foldOpen(o.key, o.open) : foldLabel.has(label) ? foldLabel.get(label) : !!o.open;
  return `<div class="fold${o.cls ? " " + o.cls : ""}"><button class="fh" data-fold${o.key ? ` data-fkey="${esc(o.key)}"` : ""} aria-expanded="${open}"${o.title ? ` title="${esc(o.title)}"` : ""}><span class="lbl">${label}</span><span class="fi${o.tone ? " " + o.tone : ""}">${info}</span><span class="car">▾</span></button><div class="fb"${open ? "" : " hidden"}>${body}</div></div>`;
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
  const sec = (key, label, info, body) => open.includes(key) ? `<div class="hsec"><span class="lbl">${label}<span class="m">${info}</span></span>${body}</div>` : fold(label, info, body, { cls: "hf", key: "h." + key });
  const base = (p) => p.replace(/^.*\//, "").replace(/ \(.*$/, "");
  return `<div class="hb">${sec("goal", "Goal", whole && h.goal ? "whole · " + esc(h.goal) : "", `<p>${esc(h.goal) || "(none)"}</p>`)}
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
function factsFold(s, text) {  // the facts the service gathered when the step ended (plan 23): diff stat and the test line
  const f = (s && s.facts) || null;
  if (!f && !text) return "";  // plan 27: either one is worth showing
  const fail = !!f && String(f.tests || "").startsWith("FAIL");  // plan 23: "" (no test run), "23 OK" or "FAIL <first failing line>"
  const info = f ? `${f.files} ${f.files === 1 ? "file" : "files"} +${f.plus}${f.minus ? " -" + f.minus : ""} · ${esc(f.tests || "no test run")}` : "read";
  return fold("Facts", info, `<pre class="text mono">${esc(text || "")}</pre>`, { cls: "facts", tone: fail ? "r" : "", open: fail, key: "facts",
    title: "git diff --stat from the step's start to its end, and its last test command: code reads them, no model" });
}
function handoffFold(t, d, n, sn, meta, nextStep) {
  const brief = (d.briefs || {})[String(n)] || "", raw = (d.notes || {})[String(n)] || "";
  const sent = handoffSections(brief), wrote = handoffSections(raw), cut = ((meta && meta.cut) || []).map(normItem);
  const all = [].concat(sent.findings, sent.files, sent.trouble, sent.questions);
  for (const c of cut) if (!all.includes(c)) sent.findings.push(c);  // plan 27 (G2): the cut lines, struck under Findings, as inspConn does
  const words = meta ? meta.sent_w : brief.split(/\s+/).filter(Boolean).length;
  const label = nextStep ? `Handoff for ${two(nextStep.n)}` : "Last handoff";
  const info = `${words} w${meta && meta.fallback ? ' · <span class="y">as written</span>' : ""} · Next: ${esc(sent.next.split("\n")[0])}`;
  const head = meta ? `<div class="hd"><span class="m" title="${esc(meta.fallback ? "the brief pass failed: " + meta.fallback + "; code cut the note" : `by ${meta.by}, ${meta.turns} turns, $${money(meta.cost)}`)}">${meta.fallback ? "sent as written, cut by code" : `compacted from ${meta.raw_w} w`}</span>
      <span class="link m" data-tact="raw">${rawOpen ? "as sent" : `as ${two(n)} wrote it`}</span></div>` : "";
  const body = rawOpen ? headingBlock(wrote, cut, ["goal", "findings", "trouble", "questions", "next"]) : headingBlock(sent, cut, undefined, true);
  return `<div class="blk">${fold(label, info, head + body + factsFold(sn || {}, (d.facts || {})[String(n)]))}</div>`;
}
function pfold(key, label, info, body, o = {}) {
  const open = planOpen.has(key);
  return `<div class="fold${o.cls ? " " + o.cls : ""}"><button class="fh" data-tact="pfold" data-key="${esc(key)}" aria-expanded="${open}"><span class="lbl">${label}</span><span class="fi">${info}</span><span class="car">${open ? "▴" : "▾"}</span></button><div class="fb"${open ? "" : " hidden"}>${body}</div></div>`;
}
const partText = (d, n) => String((d.parts || {})[n] || "").replace(/^# Part [^\n]*\n+/, "");
const PLAN_FOLDS = { goal: "goal", decisions: "dec", "out of scope": "out", files: "files", steps: "steps", acceptance: "acc" };
function planFoldKey(key) {  // plan 27 G3: the six pinned keys of plan 25 5.6; every ### Step N shares plan.steps; any other heading is not kept
  const k = key.startsWith("st:") ? "steps" : PLAN_FOLDS[key.slice(key.indexOf(":") + 1).trim().toLowerCase()];
  return k ? "plan." + k : "";
}
function planOpenHtml(t, d, cur, o = {}) {  // the open plan by heading and the current step's section; o.board: keyed folds for the inspector, o.design / o.verify open Goal + Decisions / Acceptance
  const p = t.plan;
  if (!p) return "";
  const parts = p.parts || [], split = parts.length > 0, curN = cur ? cur.n : 0;
  const mk = (key, label, info, inner, open) => o.board ? fold(label, info, inner, { cls: "hf", key: planFoldKey(key), open })
    : pfold(key, label, info, inner, { cls: "hf" });
  let body = "";
  for (const sc of planSections(d.plan)) {
    if (split && sc.title === "Sub-plans") continue;
    if (!split && sc.title === "Steps") {
      const subs = splitHeads(sc.body, "### ").filter((x) => x.title);
      body += `<span class="lbl">Steps · ${subs.length}</span>` + subs.map((x) => {
        const mine = Number((/^Step (\d+)/.exec(x.title) || [])[1]) === curN, text = x.body.join("\n").trim();
        return mine ? `<div class="hsec"><span class="lbl">${esc(x.title)} <span class="tg n">this step</span></span>${stepBody(text)}</div>`
          : mk("st:" + x.title, esc(x.title), "", stepBody(text), false);
      }).join("");
      continue;
    }
    const open = o.board && ((/^goal/i.test(sc.title) && (o.design || !cur)) || (/^decisions/i.test(sc.title) && o.design) || (/^acceptance/i.test(sc.title) && o.verify));
    body += mk("s:" + sc.title, esc(sc.title), "", mdBlock(sc.body), !!open);
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
  return body;
}
function planRowHtml(t, d, cur) {  // after the chain: closed it is one line; open, the plan by heading and the current step's section
  const p = t.plan;
  if (!p) return "";
  const parts = p.parts || [], split = parts.length > 0, words = Number(p.words || 0).toLocaleString("en");
  const closed = `from ${two(p.from)} design · ` + (split ? `${parts.length} sub-plans · ${words} w` : `${words} w · never cut`);
  const body = planOpenHtml(t, d, cur);
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
    <div class="where"><span class="m">${esc(t.project)} / effort: ${esc(t.effort)} · $${money(row.cost)}</span><button class="btn sm" data-go="board" title="The chain as connected cells, with the handoffs between the steps: the window widens (Esc returns)">&#8660; Board</button></div>
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
  if (scrollCur) { scrollCur = false; const r = $("tscroll").querySelector(".row.cur"); if (r) r.scrollIntoView({ block: "nearest" }); }
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

function taskRowSig(row) {  // what changed in a task's row: the Task page and the Board fetch GET /api/task only when this does
  const at = row.steps.find((x) => x.n === row.current), run = at && snap.sessions.find((x) => x.id === at.session);
  return [row.updated, row.state, row.owner, row.why, row.briefing, row.cleared, row.cost, row.steps.map((x) => x.note + x.part).join(), row.plan ? row.plan.words : "", row.asks, row.hand_off, run ? run.state + run.run_live : ""].join("|");
}
async function renderTaskPage() {  // GET /api/task when the task's row changed; the drawing follows every snapshot
  const row = (snap.tasks || []).find((x) => x.id === taskId);
  const sig = row ? taskRowSig(row) : "gone";
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
  grown.clear();
  scrollCur = true;
  foldLabel.clear();
  planOpen = new Set();
  planEdit = false;
  planEditPart = 0;
  showPage("task");
}

let tArmTimer = null;
function actMsg() { return page === "board" ? $("b-msg") : $("ta-msg") || $("t-msg"); }  // where a failed lever says why
function actRedraw() { if (page === "board") { boardData = null; renderBoard(); } else { taskSig = ""; if (page === "task") renderTaskPage(); } }
async function taskAct(name, button) {
  const id = button.dataset.tid || taskId;
  if (name === "raw") { rawOpen = !rawOpen; drawTask(); return; }  // page only: the brief or the raw note
  if (name === "next") return startNext(id, button);  // the card's button too
  if (name === "pfold") { const k = button.dataset.key; if (planOpen.has(k)) planOpen.delete(k); else planOpen.add(k); drawTask(); return; }
  if (name === "edit") { planEdit = !planEdit; if (page === "board") renderBoard(); else drawTask(); return; }
  if (name === "saveplan") return savePlan(button);
  if (name === "gapanswer") return gapAnswer(button);
  if (!id) return;
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
    await api("/api/task/" + name, { task: id });
    if (name === "clear" && page === "board") {  // the Board's pick moves to the next task, not to the list
      const list = boardTasks(), k = list.findIndex((x) => x.id === id), to = list[k + 1] || list[k - 1];
      boardTask = to ? to.id : "";
      boardPick = "t";
      boardData = boardChat = null;
      renderBoard();
      return;
    }
    if (name === "clear") { taskId = null; showPage("list"); return; }
    actRedraw();  // redraw now, not at the next snapshot
  } catch (e) {
    button.disabled = false;
    const msg = page === "task" || page === "board" ? actMsg() : null;
    if (!msg) button.textContent = "Failed: " + e.message;
    else msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

async function gapAnswer(button) {  // a Plan gap: the answer joins the plan's Decisions and continues the step (POST /api/task/answer)
  const ask = button.closest(".askbox"), box = (ask && ask.querySelector("textarea")) || $("t-answer"), text = box ? box.value.trim() : "";
  if (!text) return;
  button.disabled = true;
  try {
    await api("/api/task/answer", { task: button.dataset.tid || taskId, text });
    box.value = "";
    actRedraw();
  } catch (e) {
    button.disabled = false;
    const msg = actMsg();
    if (msg) msg.innerHTML = `<span class="r">${esc(e.message)}</span>`;
  }
}

async function savePlan(button) {  // Fred's edit of the index or of a part, through the service only
  const ed = button.closest(".edbox"), box = (ed && ed.querySelector("textarea")) || $("t-edit");
  if (!box) return;
  button.disabled = true;
  try {
    await api("/api/task/plan", { task: button.dataset.tid || taskId, text: box.value, part: planEditPart });
    planEdit = false;
    actRedraw();
  } catch (e) {
    button.disabled = false;
    const msg = actMsg();
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
  const tid = button.dataset.tid, bd = tid && boardData && boardData.id === tid ? boardData.data : null;
  const t = bd ? bd.task : taskData && taskData.task, cur = t && t.steps.find((s) => s.n === t.current);
  const ask = button.closest(".askbox"), box = (ask && ask.querySelector("textarea")) || $("t-answer");
  const text = name === "answer" && box ? box.value.trim() : "";
  if (!cur || !cur.session || (name === "answer" && !text)) return;
  button.disabled = true;
  try {
    await api("/api/" + (name === "answer" ? "continue" : "handoff"), name === "answer" ? { session: cur.session, text } : { session: cur.session });
    if (box) box.value = "";
    actRedraw();  // redraw now, not at the next snapshot
  } catch (e) {
    button.disabled = false;
    const msg = actMsg();
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
  const out = {}, saved = savedTiers();
  for (const [k, t] of Object.entries(cfg.tuning)) if (!same(medit.values[k], t.value)) out[k] = medit.values[k];
  if (!same(cleanPins(medit.kinds), cleanPins(cfg.kind_pins || {}))) out.kinds = cleanPins(medit.kinds);
  const tiers = Object.fromEntries(Object.entries(medit.tiers).filter(([t, rows]) => !same(rows, saved[t])));  // plan 27 B6: only the tiers that changed; the service merges per tier
  if (Object.keys(tiers).length) out.tiers = tiers;
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
  const open = mqOpen.has("h" + tier);  // plan 27 B6: the hidden rungs listed on demand, each with its remove button (a model gone from models.json blocks its tier's Save)
  const hid = hidden.length ? `<div class="rhid" title="Turn the CLI on in Settings and its models come back">${hidden.length} hidden · ${esc(whyHidden(hidden[0].rung))} · <button class="rs" data-q="h${tier}" aria-expanded="${open}">${open ? "hide" : "show"}</button></div>` : "";
  const gone = rows.map((r, i) => {
    if (!open || !whyHidden(r.rung)) return "";
    const m = r.rung.includes(":") ? r.rung.slice(r.rung.indexOf(":") + 1) : r.rung;
    return `<div class="rhid one"><span class="nm">${esc(modelText(r.rung))} · ${esc(whyHidden(r.rung))}</span><button class="x" data-mrm="${tier}:${i}" aria-label="Remove ${esc(m)}" title="Remove from ${tier}">&#10005;</button></div>`;
  }).join("");
  const add = addOptions(tier);
  return `<div class="pcard">${cardHead("t" + tier, KCARD[tier][0], `${n} ${n === 1 ? "rung" : "rungs"}`, KCARD[tier][3])}${body}${hid}${gone}
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
function allowBad(key) {  // plan 27 G9: every window of a model key a finite number in tuning's allowance range
  const t = cfg.tuning.allowances, row = (medit.values.allowances || {})[key] || {};
  return Object.values(row).some((n) => typeof n !== "number" || !isFinite(n) || n < t.min || n > t.max) ? `a number between ${t.min} and ${t.max}` : "";
}
function tuneBad(k) {
  const t = cfg.tuning[k], v = medit.values[k];
  if (k === "allowances") { const key = Object.keys(v || {}).find(allowBad); return key ? `${key}: ${allowBad(key)}` : ""; }
  if (t.unit === "bool" || t.unit === "rung") return "";
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
  const rows = keys.map((key) => { const bad = allowBad(key); return `<div class="tf al${bad ? " bad" : ""}"><span class="nm">${esc(key)}</span><span class="v">${["day_usd", "week_usd", "month_usd"].map((w) =>
    `<input inputmode="decimal" data-mal="${esc(key)}:${w}" aria-label="${esc(key)} ${w.split("_")[0]} USD" placeholder="${w[0]}" value="${(al[key] || {})[w] ?? ""}">`).join("")}</span><span class="sub">${bad ? esc(bad) : "day · week · month, USD; empty: no allowance"}</span></div>`; }).join("");
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

// -- the Board (plan 25): the chain and the inspector, one page of the one window -------------------------------
function foldOpen(key, dflt) { return key && key in foldState ? foldState[key] : !!dflt; }
function saveFolds() { saveDraft(); }  // the draft save carries folds and board_tab

function boardTasks() {  // the tasks in scope, newest first; a finished or stopped task leaves a day after its last change (the picked one stays)
  return (snap.tasks || []).filter((t) => t.id === boardTask || ((!scope || sameDir(t.project_dir, scope)) && (taskGroup(t) !== "done" || snap.now - t.updated < 86400)))
    .sort((a, b) => b.updated - a.updated);
}
function boardProject() {
  if (scope) return scope;
  const t = (snap.tasks || []).find((x) => x.id === boardTask);
  return t ? t.project_dir : "";
}

async function openBoard(id) {  // the window widens to the saved Board size; Esc gives the old size back
  if (form === "pill") await setForm("open");
  boardFrom = page === "board" ? boardFrom : { page, id: page === "task" ? taskId : page === "session" ? openId : "" };
  boardTask = id || "";  // the opened task stays listed whatever the scope says
  const t = (snap.tasks || []).find((x) => x.id === id) || boardTasks()[0];
  boardTask = t ? t.id : "";
  boardPick = t && t.steps.some((s) => s.n === t.current) && t.state !== "done" ? "s" + t.current : t ? "t" : "";
  boardData = boardChat = null;
  planEdit = false;
  planEditPart = 0;
  if (native()) { try { await window.pywebview.api.board(true); } catch (e) { /* the window keeps its size */ } }
  showPage("board");
}
async function closeBoard() {  // back to the page the Board opened from, at the compact size
  const b = boardFrom;
  boardFrom = null;
  if (native()) { try { await window.pywebview.api.board(false); } catch (e) { /* the window keeps its size */ } }
  if (b && b.page === "task" && (snap.tasks || []).some((t) => t.id === b.id)) return openTask(b.id);
  if (b && b.page === "session" && b.id) return openSession(b.id, tab);
  showPage("list");
}

async function renderBoard() {
  const tasks = boardTasks(), row = tasks.find((t) => t.id === boardTask) || tasks[0];
  if (row && row.id !== boardTask) { boardTask = row.id; boardPick = "t"; boardData = null; }
  $("bcrumb").textContent = `Board / ${scope ? projectName(scope) : "All projects"} · ${tasks.length} ${tasks.length === 1 ? "task" : "tasks"}`;
  setHtml($("bfoot"), tasks.length ? `<span><span class="kbd">↑</span><span class="kbd">↓</span> step</span><span><span class="kbd">←</span><span class="kbd">→</span> task</span><span><span class="kbd">Enter</span> chat</span><span><span class="kbd">Esc</span> back</span><span class="sp"></span>
    <button class="q" title="A step's context in cells of 10K; the chip between two steps is the handoff the next one received, its words in the inspector" aria-label="Legend">?</button>` : "");
  const live = boardSessions(), liveHtml = live.map(boardSessionHtml).join("");
  if (live.length) $("bcrumb").textContent += ` · ${live.length} live ${live.length === 1 ? "chat" : "chats"}`;
  if (boardPick[0] === "l") await liveChatFetch(boardPick.slice(1));
  if (!row) {
    setHtml($("bchain"), liveHtml ? `<div class="tk folded">${liveHtml}</div>` : emptyBoard());
    setHtml($("bwrap"), liveHtml ? `<div class="binsp">${boardPick[0] === "l" ? inspLive(boardPick.slice(1)) : '<p class="note m">No task here. Pick a live chat on the left.</p>'}</div>` : "");
    return;
  }
  const sig = taskRowSig(row);
  if (!boardData || boardData.id !== row.id || boardData.sig !== sig) {
    const id = row.id, data = await api("/api/task?id=" + encodeURIComponent(id)).catch(() => false);
    if (page !== "board" || boardTask !== id) return;
    boardData = { id, sig, data };
  }
  const d = boardData.data;
  if (d && boardPick[0] === "s") await boardChatFetch(d, row);
  else if (boardPick === "") await measureFetch();
  if (page !== "board" || boardTask !== row.id) return;
  setHtml($("bchain"), (liveHtml ? `<div class="tk folded">${liveHtml}</div>` : "") + tasks.map((t) => chainHtml(t, t.id === row.id ? d : null, t.id === row.id ? boardPick : null)).join(""));
  setHtml($("bwrap"), `<div class="binsp">${await boardInspector(row, d)}</div>`, { sel: ".binsp", reset: boardWrapKey() });
}
function boardSessions() {  // plain chats that need Fred or are working: the list shows them, so the Board does too (a step's chat belongs to its task)
  const g = groups();
  return [...g.needs, ...g.work].sort((a, b) => b.last_ts - a.last_ts);
}
function boardSessionHtml(s) {  // one folded row, like a task head; a click opens the session page and Esc returns to the Board
  const [glyph, word, t] = stateWord(s);
  return `<div class="thead sess${boardPick === "l" + s.id ? " picked" : ""}" data-bpick="l${esc(s.id)}" tabindex="0" role="button" title="${esc(s.project)}">
    <div class="l1"><span class="st ${t}">${sessionMark(s, glyph, t)}${esc(word)}</span><span class="t">${esc(s.title)}</span><span class="age m">${ago(snap.now - s.last_ts)}</span></div>
    <div class="l2 m"><span class="who">${esc(s.project)}</span><span class="cost">${spentText(s)}</span></div></div>`;
}
function inspLive(id) {  // a plain chat picked on the Board: its facts and the way in
  const s = snap.sessions.find((x) => x.id === id);
  if (!s) return '<p class="note m">This chat is gone from the list.</p>';
  const [glyph, word, tn] = stateWord(s);
  return `<div class="ihead"><div class="ln1"><span class="st ${tn}">${sessionMark(s, glyph, tn)}${esc(word)}</span><h2>${esc(s.title)}</h2>
    <span class="lr"><button class="btn sm" data-open="${esc(s.id)}" title="The session page, with its levers">Open chat</button></span></div>
    <div class="meta"><span>${esc(s.project)}</span><span>spent <b>${spentText(s)}</b></span><span>${ago(snap.now - s.last_ts)}</span></div></div>
    <div class="ipane">${boardChat && boardChat.sid === id && boardChat.chat ? chatPane(boardChat.chat, id, s.source || "chat", { compact: true, board: true }) : '<p class="note m">Reading the chat.</p>'}</div>`;
}
async function liveChatFetch(sid) {  // a picked plain chat: fetched when the pick changed, and every 2 s while it runs
  const live = snap.sessions.find((x) => x.id === sid), running = !!live && live.state === "running", turn = live ? live.turn_ts : 0;
  if (boardChat && boardChat.sid === sid && boardChat.running === running && (!running || (snap.now - boardChat.at < 2 && boardChat.turn === turn))) return;
  const chat = await api("/api/chat?session=" + encodeURIComponent(sid)).catch(() => null);
  if (page !== "board" || boardPick !== "l" + sid) return;
  boardChat = chat ? { sid, at: snap.now, chat, running, turn } : null;
}
async function boardChatFetch(d, row) {  // the picked step's chat: when the pick changed, and every 2 s while the step runs
  const s = d.task.steps.find((x) => "s" + x.n === boardPick);
  if (!s || !s.session) { boardChat = null; return; }
  const live = snap.sessions.find((x) => x.id === s.session), running = s.state === "running";
  const turn = live ? live.turn_ts : 0;
  if (boardChat && boardChat.sid === s.session && boardChat.running === running && (!running || (snap.now - boardChat.at < 2 && boardChat.turn === turn))) return;
  const sid = s.session, chat = await api("/api/chat?session=" + encodeURIComponent(sid)).catch(() => null);
  if (page !== "board" || boardPick !== "s" + s.n) return;
  boardChat = chat ? { sid, at: snap.now, chat, running, turn } : null;
}
async function measureFetch() {  // the Measure table: once a minute per project
  const project = boardProject();
  if (!project) { measureData = null; return; }
  if (measureData && measureData.project === project && snap.now - measureData.at < 60) return;
  const data = await api("/api/measure?project=" + encodeURIComponent(project) + "&n=10").catch(() => null);
  if (page !== "board" || boardPick !== "") return;
  measureData = { project, at: snap.now, data };
}
function boardInspector(row, d) {
  if (boardPick[0] === "l") return inspLive(boardPick.slice(1));
  if (d === false) return '<p class="note m">This task is gone: it was cleared or its folder was removed.</p>';
  const t = d.task;
  if (boardPick === "t") return inspTask(t, d, row);
  const m = /^([sc])(\d+)$/.exec(boardPick), s = m && t.steps.find((x) => x.n === Number(m[2]));
  if (s && m[1] === "c") return inspConn(t, s, d, row);
  if (s) {
    if (s.kind === "replan" && s.n === t.current && String(t.why || "").startsWith("replanned:")) return inspReplan(t, s, d, row);
    if (s.n === t.current && /^(asks: )?Plan gap:/.test(row.asks || row.why || "")) return inspGap(t, s, d, row);
    return inspStep(t, s, d, row);
  }
  const project = boardProject();
  if (!project) return '<div class="ihead"><h2>Measure</h2></div><p class="note m">Pick a project to measure its tasks.</p>';
  return inspMeasure(measureData && measureData.project === project ? measureData.data : null, projectName(project));
}
function boardWrapKey() {  // true when the pick changed since the last draw: a new pick starts at the top, a redraw keeps the scroll
  const k = boardTask + "|" + boardPick + "|" + itab, changed = boardWrapKey.last !== k;
  boardWrapKey.last = k;
  return changed;
}

function boardItems(row) {  // ["t", "s1", "c1", "s2", ...] in chain order; a connector only when it is not pending
  const d = boardData && boardData.id === row.id ? boardData.data : null, t = d && d.task, steps = t ? t.steps : row.steps, out = ["t"];
  steps.forEach((s, k) => {
    out.push("s" + s.n);
    if (t && k < steps.length - 1 && connCase(t, s, d).cls !== "pending") out.push("c" + s.n);
  });
  return out;
}
function boardKey(e) {
  const tasks = boardTasks(), k = tasks.findIndex((t) => t.id === boardTask), row = tasks[k];
  e.preventDefault();
  if (e.key === "Escape") { if (boardPick) { boardPick = ""; renderBoard(); } else closeBoard(); return; }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const to = tasks[k + (e.key === "ArrowRight" ? 1 : -1)];
    if (to) { boardTask = to.id; boardPick = "t"; boardData = boardChat = null; renderBoard(); }
    return;
  }
  if (!row) return;
  const items = boardItems(row), at = items.indexOf(boardPick);
  if (e.key === "Enter") {
    if (boardPick[0] === "l") { backTo = { page: "board" }; openSession(boardPick.slice(1)); return; }
    const s = boardPick[0] === "s" && row.steps.find((x) => "s" + x.n === boardPick);
    if (s && s.session) { backTo = { page: "board" }; openSession(s.session); }
    return;
  }
  const to = items[at < 0 ? 0 : at + (e.key === "ArrowDown" ? 1 : -1)];
  if (to) { boardPick = to; renderBoard().then(() => { const f = document.querySelector(`#bchain [data-bpick="${to}"]`); if (f) f.focus({ preventScroll: false }); }); }
}

// the chain column
const BWORD = { running: ["Running", "n", "running"], done: ["Done", "g", "done"], failed: ["Fail", "r", "stuck"], planned: ["Planned", "q", "planned"],
  waiting: ["Waiting", "y", "waiting"], handed: ["Handed", "y", "done"] };  // [word, tone, sprite]
const HINT_IN_W = 300, HINT_CTX = 100000;  // D4 (a): a small handoff in and a large context reached: the step read on its own
function stepShown(t, s, row) {
  if (row && s.n === t.current && (row.state === "waiting" || row.asks)) return "waiting";
  return s.verdict === "FAIL" || s.state === "failed" ? "failed" : BWORD[s.state] ? s.state : "planned";
}
function stepCtx(s) {  // a running step's context is the live session row's; null and undefined both mean unknown
  const r = s.state === "running" && s.session ? snap.sessions.find((x) => x.id === s.session) : null;
  const v = r ? r.ctx_tokens : s.ctx_tokens;
  return v == null ? null : v;
}
const ctxUnknown = (s) => s.harness && s.harness !== "claude" ? `${s.harness} reports a turn's spend, not a context size` : "no context reading for this step";
function ctxFigTone(tok) { const [y, r] = cfg ? cfg.gauge : [150000, 300000]; return tok >= r ? "r" : tok >= y ? "y" : ""; }
function ctxMiniHtml(s) {  // a finished block: 15 cells and the figure, or the word
  const tok = stepCtx(s);
  if (tok == null) return `<span class="ctx" title="${esc(ctxUnknown(s))}">ctx unknown</span>`;
  return `<span class="ctx" title="context reached ${kTokens(tok)}"><span class="cells">${cellsHtml(ctxClasses(tok).filter((_, k) => k % 2 === 0))}</span><b class="${ctxFigTone(tok)}">${kTokens(tok)}</b></span>`;
}
function ctxRowHtml(s, live) {  // a full block: 30 cells and the figure, or the word unknown
  const tok = stepCtx(s);
  if (tok == null) return `<span class="cx"><span>ctx</span><span class="unk" title="${esc(ctxUnknown(s))}">unknown</span><span></span></span>`;
  const cls = ctxClasses(tok), last = cls.map((c) => c !== "").lastIndexOf(true);
  if (live && last >= 0) cls[last] += " live";
  return `<span class="cx"><span>ctx</span><span class="cells">${cellsHtml(cls)}</span><b class="${ctxFigTone(tok)}">${kTokens(tok)}</b></span>`;
}
function costUnknown(s) {  // plan 27 G7: a step whose cost no attempt reported (plan 5 README 3.6); a running attempt counts 0 until it ends
  const a = s.attempts || [];
  return s.cost == null || (a.length > 0 && a.every((x) => x.cost == null));
}
function stepCost(s) {  // plan 25 3: the service's s.cost, the sum of its attempts
  if (s.state === "planned") return "";
  return costUnknown(s) ? '<span class="cost unk" title="the harness reported no usage">cost unknown</span>' : `<span class="cost">${money(s.cost)}</span>`;
}
function rungTime(s) {
  const rung = modelText(rungOf(s.harness, s.model), s.effort);
  const t = stepTime(s);
  return `${esc(rung)}${t ? " · " + t : ""}`;
}
function triesHtml(s) {  // one 7 px square per attempt: red failed, green the one that passed, ink the live one
  const a = s.attempts || [];
  if (a.length < 2 && !a.some((x) => x.why)) return "";
  const cls = a.map((x, k) => (x.why ? "r" : k === a.length - 1 ? (s.state === "running" ? "f" : s.state === "done" ? "g" : "") : ""));
  return `<span class="tries" title="attempts: ${cls.map((c) => (c === "r" ? "failed" : c === "g" ? "passed" : c === "f" ? "live" : "stopped")).join(", ")}">${cls.map((c) => `<i class="${c}"></i>`).join("")}</span>`;
}
function scoutHint(t, s, d) {  // D4 (a): a step that received a small handoff and still reached a large context read too much on its own
  const prev = t.steps.find((x) => x.n === s.n - 1), meta = (prev && prev.brief_meta) || {}, ctx = stepCtx(s);
  if (meta.sent_w == null || ctx == null || meta.sent_w >= HINT_IN_W || ctx < HINT_CTX || s.state === "planned") return "";
  return `<span title="${meta.sent_w} w in, ${kTokens(ctx)} reached">△ scout first</span>`;
}
function stepBlock(t, s, d, row) {
  const shown = stepShown(t, s, row), [word, tn, spr] = BWORD[shown], pick = "s" + s.n, isPicked = boardPick === pick && row && row.id === boardTask;
  const from = s.part ? ' <span class="m" title="a write step the design step made">· from plan</span>' : "";
  const l1 = `<div class="l1"><span class="st ${tn}">${sprite(spr)}${word}</span><span class="nm">${two(s.n)} ${esc(s.kind)}${from}</span>${stepCost(s)}</div>`;
  const attr = `data-bpick="${pick}" tabindex="0" role="button"`;
  if (shown === "planned") return `<div class="sb one${isPicked ? " picked" : ""}" ${attr} title="rung at start (rule ${esc(s.kind)})">${l1}</div>`;
  const rung = `<span class="rt">${rungTime(s)}</span>`, tok = stepCtx(s), live = s.state === "running";
  const hot = tok != null && cfg && tok >= cfg.gauge[0];
  if (shown === "done" && !isPicked && s.n !== t.current && !hot) return `<div class="sb short" ${attr}>${l1}<div class="rung">${rung}${ctxMiniHtml(s)}</div></div>`;
  const sub = [s.verdict ? `<span class="${s.verdict === "FAIL" ? "r" : "g"}">${s.verdict === "FAIL" ? "FAIL " + esc(s.verdict_detail || "") : "PASS"}</span>` : "",
    scoutHint(t, s, d), shown === "waiting" && row ? `<span class="y">${esc(row.why || row.asks)}</span>` : ""].filter(Boolean).join(" · ");
  return `<div class="sb${shown === "waiting" ? " y" : ""}${live ? " cur" : ""}${isPicked ? " picked" : ""}" ${attr}>${l1}<div class="rung">${rung}${triesHtml(s)}</div>${ctxRowHtml(s, live)}${sub ? `<div class="sub" title="${esc(s.verdict_detail || "")}">${sub}</div>` : ""}</div>`;
}
function connCase(t, s, d) {  // the handoff after step s: its class, chip and title (README 3.5)
  const meta = s.brief_meta || {}, nn = two(s.n);
  if (s.state === "running" || t.briefing === s.n) return { cls: "writing", chip: "writing", title: s.state === "running" ? `step ${nn} is writing its handoff` : `Haiku is compacting the handoff for step ${nn}` };
  if (!(d.notes || {})[String(s.n)] && !s.brief_meta) return { cls: "pending", chip: "", title: "" };
  if (meta.fallback) return { cls: "fallback", chip: "as written · not compacted", title: meta.fallback };
  if (s.kind === "design" && t.plan && t.plan.from === s.n)
    return { cls: "plan", chip: "handoff · <b>plan</b>", title: `the handoff of step ${nn}, compacted to ${meta.sent_w == null ? "?" : meta.sent_w} words, and plan.md (${Number(t.plan.words || 0).toLocaleString("en")} words, never cut), which every later step reads` };
  if (meta.cut && meta.cut.length) {
    const n = (meta.raw_w || 0) - (meta.sent_w || 0);
    return { cls: "cut", chip: `handoff · <b>cut ${n} w</b>`, title: `step ${nn} wrote ${meta.raw_w} words; the next step received ${meta.sent_w} once compacted, Findings cut ${n} w` };
  }
  return { cls: "", chip: "handoff", title: `the handoff step ${nn} left for the next step${meta.sent_w == null ? "" : `, compacted to ${meta.sent_w} words`}` };
}
function connBlock(t, s, d) {  // after step s; none after the last
  if (!t.steps.some((x) => x.n > s.n)) return "";
  const c = connCase(t, s, d);
  if (c.cls === "pending") return '<div class="conn pending"><span class="ln"></span></div>';
  return `<div class="conn ${c.cls}${boardPick === "c" + s.n && boardData && boardData.id === boardTask ? " picked" : ""}" data-bpick="c${s.n}" tabindex="0" role="button"><span class="ln"></span><span class="chip" title="${esc(c.title)}">${c.chip}</span></div>`;
}
function chainHtml(row, d, picked) {  // a task of the chain: folded to its head, or (the picked one) unfolded to its steps
  const [word, tn] = TASK_WORD[taskShown(row)] || TASK_WORD.running, folded = d == null, n = row.count;
  const l2 = folded ? (row.state === "waiting" || row.asks ? `<span class="who y">${esc(row.why || row.asks)}</span>` : `<span class="who">${n} ${n === 1 ? "step" : "steps"}</span>`)
    : `<span class="who">${row.state === "done" || !row.current ? `${n} ${n === 1 ? "step" : "steps"}` : `step ${row.current} of ${n}`}</span>`;
  const head = `<div class="thead${picked === "t" ? " picked" : ""}" data-bpick="t" data-btask="${esc(row.id)}" tabindex="0" role="button" title="${esc(row.project)} · effort ${esc(row.effort)}">
    <div class="l1"><span class="st ${tn}">${sprite(taskSprite(row))}${word}</span><span class="t">${esc(row.title)}</span><span class="age m">${ago(snap.now - row.updated)}</span></div>
    <div class="l2 m">${l2}<span class="cost">${money(row.cost)}</span></div></div>`;
  if (folded) return `<div class="tk folded">${head}</div>`;
  if (d === false) return `<div class="tk">${head}<p class="note m">This task is gone.</p></div>`;
  const t = d.task, steps = t.steps, block = (s) => stepBlock(t, s, d, row);
  let html = head;
  for (let k = 0; k < steps.length; k++) {
    const s = steps[k], prev = steps[k - 1], nx = steps[k + 1];
    if (prev && s.kind === "fix" && nx && nx.kind === "verify" && nx.checked === s.n) {  // the fix insert: a bracket under the failed verify
      html += `<div class="branch"><span class="ln"></span><div class="in">${connBlock(t, prev, d)}${block(s)}${connBlock(t, s, d)}${block(nx)}</div></div>`;
      k++;
      continue;
    }
    html += (prev ? connBlock(t, prev, d) : "") + block(s);
  }
  return `<div class="tk">${html}</div>`;
}
function emptyBoard() {
  const where = scope ? projectName(scope) : "any project";
  return `<div class="empty"><div class="cells">${cellsHtml(Array(30).fill(""))}</div>
    <p>No task in ${esc(where)}. Type a task in the list; its steps show here as they run.</p></div>`;
}

// the inspector (plan 25 Tasks 5 and 6): the picked step, handoff, task head or the Measure table
const wc = (x) => String(x || "").split(/\s+/).filter(Boolean).length;
const stepNo = (s) => (s ? two(s.n) : "");
function stepTime(s) {
  return s.state === "running" && s.started ? elapsed(snap.now - s.started) : s.ended && s.started ? elapsed(s.ended - s.started) : "";
}
function stepCostFig(s) {  // the cost figure for the inspector's meta: the service's s.cost, or the word unknown
  return costUnknown(s) ? "unknown" : money(s.cost);
}
function sentWords(t, d, s) {  // the words step s received: the previous step's brief, from its meta or its file
  const prev = t.steps.find((x) => x.n === s.n - 1);
  if (!prev) return null;
  const m = prev.brief_meta;
  if (m && m.sent_w != null) return m.sent_w;
  const b = (d.briefs || {})[String(prev.n)];
  return b ? wc(b) : null;
}
function busyBox(tid) { return `<div id="b-msg" class="say" data-tid="${esc(tid)}"></div>`; }
function stepHead(t, s, d, row, extra = "") {
  const shown = stepShown(t, s, row), [word, tn, spr] = BWORD[shown], lv = d.levers || {};
  const failedTry = shown === "failed" && (s.attempts || []).length > 1 ? (s.attempts.find((a) => a.why) || s.attempts[0]) : null;
  const buttons = (s.session ? '<button class="btn sm" data-open="' + esc(s.session) + '" title="The session page, with its levers">Open chat</button>' : "")
    + (s.state === "running" && lv.stop === "" ? `<button class="btn sm stop" data-tact="stop" data-tid="${esc(t.id)}" title="Interrupts the run; the task stops">Stop</button>` : "")
    + (failedTry ? `<button class="btn sm" data-open="${esc(failedTry.session)}">Open try 1</button>` : "");
  const rung = s.state === "planned" ? "rung at start" : modelText(rungOf(s.harness, s.model), s.effort), time = stepTime(s);
  return `<div class="ihead"><div class="ln1"><span class="st ${tn}">${sprite(spr)}${word}</span><h2>${stepNo(s)} ${esc(s.kind)}${extra}</h2><span class="lr">${buttons}</span></div>
    <div class="meta"><span>${esc(rung)}</span><span>cost <b>${stepCostFig(s)}</b></span>${time ? `<span>${time}</span>` : ""}</div></div>${busyBox(t.id)}`;
}
function recvPane(t, s, d) {
  if (s.n === 1) return '<p class="note m">No handoff: step 1 gets the task goal and Prep\'s context pack.</p>';
  const prev = t.steps.find((x) => x.n === s.n - 1), brief = (d.briefs || {})[String(s.n - 1)] || "", meta = (prev && prev.brief_meta) || {};
  if (!brief) return `<p class="note m">The brief of step ${two(s.n - 1)} is not on disk (cleared, or the step never ran).</p>`;
  const w = meta.sent_w != null ? meta.sent_w : wc(brief);
  const plan = prev && prev.kind === "design" && t.plan && t.plan.from === prev.n
    ? `<p class="note m">and plan.md, ${Number(t.plan.words || 0).toLocaleString("en")} w, never cut (the Plan tab)</p>` : "";
  return `<div class="blk"><div class="hd"><span class="lbl">From ${two(s.n - 1)}</span><span class="m">${w} w · ${meta.fallback ? "as written" : "compacted"}</span></div>${plan}
    ${headingBlock(handoffSections(brief), [], ["goal", "findings", "questions", "next"])}</div>`;
}
function handPane(t, s, d) {
  const note = (d.notes || {})[String(s.n)] || "", meta = s.brief_meta || {}, nx = t.steps.find((x) => x.n === s.n + 1);
  if (s.state === "running") return '<p class="note m">Writing. Shows here when the run ends.</p>';
  if (s.state === "planned") return '<p class="note m">Not started.</p>';
  if (!note) return '<p class="note m">No handoff: the step ended without a HANDOFF block.</p>';
  const raw = meta.raw_w != null ? meta.raw_w : wc(note), got = meta.sent_w;
  const info = nx ? `wrote ${raw} w · ${two(nx.n)} received ${got == null ? "?" : got} w${meta.fallback ? " · sent as written" : ""}` : `wrote ${raw} w`;
  return `<div class="blk"><div class="hd"><span class="lbl">${nx ? "For " + two(nx.n) : "For the task's end"}</span><span class="m">${info}</span></div>
    ${headingBlock(handoffSections(note), (meta.cut || []).map(normItem))}${factsFold(s, (d.facts || {})[String(s.n)])}</div>`;
}
function routePane(s) {
  const notes = (s.notes || []).map((n) => `<span${/every .* over pace/.test(n) ? ' class="y"' : ""}>${esc(n)}</span>`).join("");
  const tries = (s.attempts || []).length > 1 ? `<div class="blk"><span class="lbl">Attempts</span><p class="note m">${stepTries(s)}</p></div>` : "";
  return `<div class="blk"><span class="lbl">Goal</span><p class="note ink">${esc(s.goal)}</p></div>
    <div class="blk"><span class="lbl">Route · in the order the rules applied</span><div class="rn">${notes || "<span>none yet</span>"}</div></div>${tries}`;
}
function planEditBox(t, d, tid) {  // plan 24's editor, on the Board: the index or a part, saved through the service
  const parts = (t.plan || {}).parts || [];
  const sel = parts.length ? `<select id="b-editpart" aria-label="Which text">${[`<option value="0">index</option>`, ...parts.map((x) => `<option value="${x.n}"${x.n === planEditPart ? " selected" : ""}>part ${x.n}: ${esc(x.title)}</option>`)].join("")}</select>` : "";
  const text = planEditPart ? partText(d, planEditPart) : d.plan;
  return `<div class="edbox">${sel}<textarea class="in" id="b-edit" rows="9" aria-label="plan.md" spellcheck="false">${esc(text)}</textarea>
    <div class="lr"><button class="btn go sm" data-tact="saveplan" data-tid="${esc(tid)}" title="Writes the plan through the service; the task folder stays the service's">Save</button></div></div>`;
}
function planPane(t, d, s) {
  const p = t.plan, n = s.n, design = n === p.from, verify = s.kind === "verify" || s.kind === "fix", parts = p.parts || [];
  const mine = parts.find((x) => { const st = t.steps.find((y) => y.part === x.n); return st && st.n === n; });
  const maxkb = (cfg && cfg.tuning && cfg.tuning.plan_max_kb && cfg.tuning.plan_max_kb.value) || 100;
  const head = design ? `written by this step · ${p.kb != null ? p.kb : "?"} KB of ${maxkb}`
    : parts.length ? `index and part ${mine ? mine.n : "none"} sent to this step`
    : verify ? "the whole plan: Steps and Acceptance are what you check" : `the whole plan, your ### Step ${n} again at the end of the prompt`;
  const next = t.steps.find((x) => x.n === n + 1), waits = t.state === "waiting" && /^(plan |asks: Plan gap:)/.test(t.why || "");
  const canEdit = design && next && next.state === "planned";  // plan 25 5.6; the service takes the Save while the task waits on its plan or is paused
  const edit = canEdit ? `<button class="btn sm" data-tact="edit" aria-expanded="${planEdit}" title="The plan in place, until the next step starts${waits || t.owner === "fred" ? "" : "; Save works while the task waits on its plan or is paused"}">Edit</button>` : "";
  return `<div class="blk"><div class="hd"><span class="lbl">plan.md${parts.length ? ` + ${parts.length} parts` : ""}</span><span class="m">${head}</span>${edit}</div>
    ${canEdit && planEdit ? planEditBox(t, d, t.id) : ""}${planOpenHtml(t, d, s, { board: true, design, verify })}</div>`;
}
function chatTab(t, s, d) {
  if (!s.session) return s.kind === "replan" ? '<p class="note m">No chat: the replan step runs one Haiku turn with no tools; its answer is in the Handoff tab.</p>'
    : '<p class="note m">Not started: the chat shows here as the step runs.</p>';
  if (!boardChat || boardChat.sid !== s.session || !boardChat.chat) return '<p class="note m">Reading the chat.</p>';
  const row = snap.sessions.find((x) => x.id === s.session);
  return chatPane(boardChat.chat, s.session, (row && row.source) || "chat", { prompt: true, step: s, compact: true, board: true });
}
function inspStep(t, s, d, row) {
  const has = d.plan && t.plan && s.n >= t.plan.from, prev = t.steps.find((x) => x.n === s.n - 1);
  const inW = sentWords(t, d, s), meta = s.brief_meta || {}, nx = t.steps.find((x) => x.n === s.n + 1);
  const outW = meta.raw_w != null ? meta.raw_w : (d.notes || {})[String(s.n)] ? wc(d.notes[String(s.n)]) : null;
  const sentW = meta.sent_w;
  const tabs = [["chat", "Chat"], ["recv", `Received${inW != null && prev ? ` <span class="n">${inW} w</span>` : ""}`],
    ["hand", `Handoff${outW != null ? ` <span class="n">${outW}${sentW != null && sentW < outW && nx ? " → " + sentW : ""} w</span>` : ""}`], ["route", "Route"]];
  if (has) tabs.push(["plan", `Plan <span class="n">${Number(t.plan.words || 0).toLocaleString("en")} w</span>`]);
  const tab = tabs.some(([k]) => k === itab) ? itab : "chat";
  const pane = tab === "chat" ? chatTab(t, s, d) : tab === "recv" ? recvPane(t, s, d) : tab === "hand" ? handPane(t, s, d) : tab === "route" ? routePane(s) : planPane(t, d, s);
  return `${stepHead(t, s, d, row)}${tabsHtml(tabs, tab)}<div class="ipane">${pane}</div>`;
}
function tabsHtml(tabs, tab) {
  return `<div class="tabs" role="tablist">${tabs.map(([k, l]) => `<button role="tab" data-itab="${k}" aria-selected="${tab === k}" tabindex="${tab === k ? 0 : -1}">${l}</button>`).join("")}</div>`;
}
function replanBox(t, s, d, row) {
  const r = t.replan || { before: [], after: [], added: [], dropped: [] }, tid = esc(t.id), lv = d.levers || {};
  const line = (x) => `${esc(x.kind)}: ${esc(x.goal)}`;
  const dropped = (r.dropped || []).map((i) => r.before[i]).filter(Boolean);
  const why = ((d.replan_note || "").match(/^## Why\s*\n+([^\n]*)/m) || [, ""])[1] || r.why || "";
  const b = (name, cls, label) => (lv[name] === "" ? `<button class="btn${cls}" data-tact="${name}" data-tid="${tid}">${label}</button>` : "");
  return `<div class="askbox"><span class="st y">${sprite("waiting")}Replanned <span class="lc">· after step ${two(s.n - 1)}</span></span>
    ${why ? `<div class="q">${esc(why)}</div>` : ""}
    <div class="plan1"><span class="lbl">New plan · ${r.after.length} steps <span class="m">(was ${r.before.length})</span></span>
      <ol>${r.after.map((x, k) => `<li class="${(r.added || []).includes(k) ? "add" : "old"}">${line(x)}</li>`).join("")}</ol></div>
    ${dropped.length ? `<div class="plan1"><span class="lbl">Dropped · ${dropped.length}</span><ol>${dropped.map((x) => `<li class="drop">${line(x)}</li>`).join("")}</ol></div>` : ""}
    <div class="lr">${b("confirm", " you", "Confirm plan")}${b("keep", "", "Keep old plan")}${b("stop", " stop", "Stop")}</div></div>`;
}
function inspReplan(t, s, d, row) {
  const prev = t.steps.find((x) => x.n === s.n - 1), next = ((prev && (d.notes || {})[String(prev.n)]) || "").match(/## Next\s*\n+([^\n]*)/);
  const notes = (s.notes || []).map((n) => `<span>${esc(n)}</span>`).join("");
  return `<div class="ihead"><div class="ln1"><span class="st y">${sprite("waiting")}Waiting</span><h2>${stepNo(s)} replan</h2></div></div>${busyBox(t.id)}
    ${replanBox(t, s, d, row)}
    ${fold("Why it ran", `${prev ? two(prev.n) + "'s Next asked for a replan" : "a replan"}`, `<p class="note">${next ? `The handoff of step ${two(prev.n)} ended with <span class="m">Next: ${esc(next[1])}</span>, so the service inserted this step.` : "The service inserted this step."}</p>`, { key: "replanwhy" })}
    ${fold("Route", `${rungTime(s)} · ${stepCostFig(s)}`, `<div class="rn">${notes || "<span>none yet</span>"}</div>`, { key: "replanroute" })}`;
}
function inspGap(t, s, d, row) {
  const q = String(row.asks || row.why || "").replace(/^(asks: )?Plan gap:\s*/, ""), lv = d.levers || {}, tid = esc(t.id);
  const has = d.plan && t.plan && s.n >= t.plan.from;
  const tabs = [["chat", "Chat"], ["recv", "Received"], ["hand", "Handoff"], ["route", "Route"]];
  if (has) tabs.push(["plan", `Plan <span class="n">${Number(t.plan.words || 0).toLocaleString("en")} w</span>`]);
  const tab = tabs.some(([k]) => k === itab) ? itab : "chat";
  const pane = tab === "chat" ? chatTab(t, s, d) : tab === "recv" ? recvPane(t, s, d) : tab === "hand" ? handPane(t, s, d) : tab === "route" ? routePane(s) : planPane(t, d, s);
  const b = (name, cls, label) => (lv[name] === "" ? `<button class="btn${cls}" data-tact="${name}" data-tid="${tid}">${label}</button>` : "");
  return `${stepHead(t, s, d, row, ' <span class="m mut">· from plan</span>')}
    <div class="askbox"><span class="st y">${sprite("waiting")}Plan gap <span class="lc">· step ${two(s.n)} stopped, nothing chosen</span></span>
      <div class="q">${esc(q)}</div>
      <textarea class="in" id="b-answer" rows="2" aria-label="Answer" placeholder="Your answer joins the plan's Decisions as Fred, ${new Date().toISOString().slice(0, 10)}: ... and continues step ${two(s.n)} in its chat."></textarea>
      <div class="lr">${b("answer", " you", "Send answer").replace('data-tact="answer"', 'data-tact="gapanswer"')}${b("redo", "", "Redo design")}${b("stop", " stop", "Stop")}</div></div>
    ${tabsHtml(tabs, tab)}<div class="ipane">${pane}</div>`;
}
function checksFold(meta) {  // what the code checked on the brief pass's answer (plan 23): closed unless one failed
  const list = meta.checks || [];
  if (!list.length) return "";
  const bad = list.filter((c) => !c.ok);
  const info = (bad.length ? `<span class="r">${bad.length} FAIL: ${esc(bad[0].name)}</span>` : `${list.length - bad.length} of ${list.length} pass`)
    + (meta.by ? ` · compacted by ${esc(meta.by)}` : "") + (meta.cost != null ? ` · $${Number(meta.cost).toFixed(3)}` : "")
    + (meta.turns ? ` · ${meta.turns} ${meta.turns === 1 ? "turn" : "turns"}` : "");
  const rows = list.map((c) => `<span><span class="${c.ok ? "g" : "r"}">${c.ok ? "✓" : "✗"}</span> ${esc(c.name)}${c.why ? ": " + esc(c.why) : ""}</span>`).join("");
  return fold("Checks", info, `<div class="checks">${rows}</div>`, { open: !!bad.length, force: !!bad.length, key: "checks" });
}
function inspConn(t, s, d, row) {  // the handoff after step s: what the next step received, the cut lines struck in place
  const nx = t.steps.find((x) => x.n === s.n + 1), meta = s.brief_meta || {}, note = (d.notes || {})[String(s.n)] || "";
  const title = `<h2>Handoff from ${stepNo(s)} ${esc(s.kind)} to ${nx ? stepNo(nx) + " " + esc(nx.kind) : "the end"}</h2>`;
  if (!note) {
    const why = t.briefing === s.n || s.state === "running" ? `Haiku is compacting the handoff for step ${stepNo(s)}.` : meta.fallback ? esc(meta.fallback) : "Not written yet.";
    return `<div class="ihead">${title}</div><p class="note m">${why}</p>`;
  }
  const h = handoffSections(note), cut = (meta.cut || []).map(normItem), all = [].concat(h.findings, h.files, h.trouble, h.questions);
  for (const c of cut) if (!all.includes(c)) h.findings.push(c);  // a cut line the note no longer holds: listed under Findings, tagged cut
  const open = ["questions", "next"].concat(["findings", "files", "trouble"].filter((k) => h[k].some((x) => cut.includes(x))));
  const raw = meta.raw_w != null ? meta.raw_w : wc(note), got = meta.sent_w;
  const cutMeta = meta.fallback ? "<span>sent as written</span>" : meta.cut && meta.cut.length ? `<span>cut <b>${raw - (got || 0)} w</b>, ${meta.cut.length} Findings lines</span>` : "";
  return `<div class="ihead"><div class="ln1">${title}</div>
    <div class="meta"><span>${stepNo(s)} wrote <b>${raw} w</b></span>${got != null ? `<span>${nx ? stepNo(nx) : "next"} received <b>${got} w</b></span>` : ""}${cutMeta}</div></div>${busyBox(t.id)}
    <div class="blk"><span class="lbl">What ${nx ? stepNo(nx) : "the next step"} received</span>${headingBlock(h, cut, open, true)}</div>${checksFold(meta)}`;
}
function inspTask(t, d, row) {
  const shown = taskShown(row), [word, tn] = TASK_WORD[shown] || TASK_WORD.running, lv = d.levers || {}, tid = esc(t.id), cur = t.steps.find((s) => s.n === t.current);
  const b = (name, cls, label) => (lv[name] === "" ? `<button class="btn sm${cls}" data-tact="${name}" data-tid="${tid}">${label}</button>` : "");
  const gap = /^(asks: )?Plan gap:/.test(row.asks || row.why || ""), replan = (t.why || "").startsWith("replanned:");
  const buttons = b("stop", " stop", "Stop") + b("pause", "", "Pause") + b("resume", " go", "Resume") + b("retry", " go", "Retry") + b("clear", "", "Clear");
  const nxt = cur && t.steps.find((x) => x.n === cur.n + 1);
  const now = cur && cur.state === "running"
    ? `<div class="now"><span class="cells"><i class="f live"></i></span><span>Now <b>${stepNo(cur)} ${esc(cur.kind)}</b> · ${rungTime(cur)}</span><span class="m">${nxt ? `next ${stepNo(nxt)} ${esc(nxt.kind)}` : "last step"}</span></div>` : "";
  let wait = "";
  if (row.asks && !gap) {
    wait = `<div class="askbox"><span class="st y">${sprite("waiting")}Asks you <span class="lc">· step ${cur ? two(cur.n) : ""}</span></span><div class="q">${esc(row.asks)}</div>
      <textarea class="in" id="b-tanswer" rows="2" aria-label="Answer" placeholder="Your answer continues step ${cur ? two(cur.n) : ""} in its chat."></textarea>
      <div class="lr">${cur && cur.session ? `<button class="btn you" data-tact="answer" data-tid="${tid}">Send answer</button>` : ""}${cur && cur.session ? `<button class="btn" data-open="${esc(cur.session)}">Open step ${cur.n}</button>` : ""}</div></div>`;
  } else if (gap || replan) {
    wait = `<div class="askbox"><span class="st y">${sprite("waiting")}${gap ? "Plan gap" : "Replanned"} <span class="lc">· answered in step ${cur ? two(cur.n) : ""}</span></span>
      <div class="lr">${cur ? `<button class="btn" data-bpick="s${cur.n}">Open step ${cur.n}</button>` : ""}</div></div>`;
  } else if ((t.state === "waiting" || t.state === "stuck") && t.why) {
    const c = lv.confirm === "" ? `<button class="btn you" data-tact="confirm" data-tid="${tid}">${esc(confirmLabel(t, row))}</button>` : "";
    wait = `<div class="askbox${t.state === "stuck" ? " r" : ""}"><span class="st ${tn}">${sprite(t.state === "stuck" ? "stuck" : "waiting")}${word}</span><div class="q">${esc(t.why)}</div>${c ? `<div class="lr">${c}</div>` : ""}</div>`;
  }
  const qs = d.questions || [], open = qs.filter((q) => !q.closed), closed = qs.filter((q) => q.closed);
  const qrow = (q) => `<div class="oqr${q.closed ? " closed" : ""}"><span class="gl">${q.closed ? "✓" : "?"}</span><span>${esc(q.q)}</span><span class="m">opened ${two(q.opened)}${q.closed ? " · closed " + two(q.closed) : ""}</span></div>`;
  const doneWhen = (String(t.goal || "").match(/Done when:\s*([^\n]*)/) || [, ""])[1] || String(t.goal || "").split("\n")[0].slice(0, 80);
  const log = d.chain || [], last = log[log.length - 1];
  const move = (c) => `${c.step ? two(c.step) : "task"} ${esc(c.from)} -> ${esc(c.to)}`;
  const n = row.count;
  return `<div class="ihead"><div class="ln1"><span class="st ${tn}">${sprite(taskSprite(row))}${word}</span><h2 title="${esc(taskDir(t.id))}">${esc(t.title)}</h2><span class="lr">${buttons}</span></div>
    <div class="meta"><span>${row.state === "done" || !t.current ? `${n} steps` : `step <b>${t.current}</b> of ${n}`}</span><span>cost <b>${money(row.cost)}</b></span><span>effort ${esc(t.effort)}</span></div></div>${busyBox(t.id)}
    ${now}${wait}
    ${fold("prompt.md", `Done when: ${esc(doneWhen)}`, `<pre class="text">${esc(t.goal)}</pre>`, { key: "promptmd" })}
    <div class="blk"><span class="lbl">Open questions · <span class="y">${open.length} open</span></span><div class="oq">${open.map(qrow).join("") || '<p class="note m">none</p>'}</div>
      ${closed.length ? fold("", `${closed.length} closed`, `<div class="oq">${closed.map(qrow).join("")}</div>`, { cls: "qf", key: "qclosed" }) : ""}</div>
    ${log.length ? fold("Chain log", `${log.length} moves · last ${hhmm(last.ts)} ${move(last)}`, `<div class="clog">${log.map((c) => `<div><span>${hms(c.ts)}</span><span title="${esc(c.why)}">${move(c)}${c.why ? ` (${esc(c.why)})` : ""}</span></div>`).join("")}</div>`, { key: "clog" }) : ""}`;
}
function inspMeasure(m, name) {
  if (!m) return '<div class="ihead"><h2>Measure</h2></div><p class="note m">The measure is not available.</p>';
  const head = `<div class="ihead"><h2>Measure · ${esc(name)} · last ${m.tasks} ${m.tasks === 1 ? "task" : "tasks"}</h2><div class="meta"><span>median per kind</span></div></div>`;
  if (!m.tasks || !(m.kinds || []).length) return `${head}<p class="note m">No finished step in ${esc(name)} yet: the table fills as tasks run.</p>`;
  const yel = cfg ? cfg.gauge[0] : 150000;
  let anyY = false;
  const bar = (v) => {
    if (v == null) return '<span class="bar"><b class="mut" title="no context reading">unknown</b></span>';
    const tone = v >= yel ? "y" : "f", n = Math.min(20, Math.round(20 * v / 200000));
    if (tone === "y") anyY = true;
    return `<span class="bar"><span class="cells">${cellsHtml(Array.from({ length: 20 }, (_, k) => (k < n ? tone : "")))}</span><b class="${tone === "y" ? "y" : ""}">${kTokens(v)}</b></span>`;
  };
  const w = (v) => (v == null ? "?" : v + " w");
  const rows = m.kinds.map((k) => `<span class="k${k.kind === m.hot ? " hot" : ""}">${esc(k.kind)}</span>`
    + (k.received == null && k.kind === "scout" ? '<span class="fig" title="the task goal and the context pack">pack</span>' : `<span class="fig" title="median words of the handoff received">${w(k.received)}</span>`)
    + bar(k.context) + `<span class="fig" title="median words of the handoff written">${w(k.handoff)}</span>`).join("");
  const hot = m.kinds.find((k) => k.kind === m.hot);
  const read = hot ? `<p class="note m">A kind that receives a small handoff and reaches a large context reads too much on its own: ${esc(hot.kind)} at ${kTokens(hot.context)} from ${hot.received == null ? "?" : hot.received} words in is the one to tune (scout first, or a turn cap).</p>` : "";
  return `${head}<div class="measure"><span class="hd2">kind</span><span class="hd2 r">received</span><span class="hd2">context</span><span class="hd2 r">handoff</span>${rows}</div>
    <div class="legend"><span><i class="f"></i>median</span>${anyY ? `<span><i class="y"></i>context past ${kTokens(yel)}</span>` : ""}<span>cell 10K · words as figures</span></div>${read}`;
}

// -- events ------------------------------------------------------------------------------
async function go(name, button) {
  if (name === "list") { backTo = null; showPage("list"); }
  if (name === "back") goBack();
  if (name === "board") openBoard(page === "task" ? taskId : "");
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
  if (name === "models") showPage("models");  // plan 26: the Settings band's Models and tuning link
  if (name === "fold") { if (page === "board") await closeBoard(); await setForm("pill"); }
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
    if (fb.dataset.tkey) { if (open) toolOpen.add(fb.dataset.tkey); else toolOpen.delete(fb.dataset.tkey); return; }  // a chat's tool row: not kept
    foldLabel.set(fb.querySelector(".lbl").textContent, open);
    if (fb.dataset.fkey) {  // plan 25: a keyed fold is remembered per window (window.json folds)
      foldState[fb.dataset.fkey] = open;
      while (Object.keys(foldState).length > 64) delete foldState[Object.keys(foldState)[0]];
      saveFolds();
    }
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
  const gr = e.target.closest("[data-grow]");  // plan 25: a finished row opens its ctx gauge line in place
  if (gr && !e.target.closest("button,a,.link")) {
    const key = taskId + ":" + gr.dataset.grow;
    if (grown.has(key)) grown.delete(key); else grown.add(key);
    drawTask();
    return;
  }
  const t = e.target.closest("[data-prep],[data-go],[data-open],[data-tab],[data-min],[data-act],[data-pact],[data-do],[data-here],[data-proj],[data-pick],[data-harness],[data-models],[data-step],[data-attach],[data-unattach],[data-task],[data-eff],[data-bpick],[data-itab],[data-tact],#brief,#today,#overpace");
  if (!t) return;
  if (t.matches(".card") && e.target.closest("[data-stay]")) return;  // typing an answer in a card
  if (t.dataset.open || t.dataset.task) {  // a session opened from a task returns to it, a task opened from a session too
    const card = t.closest(".card.task");
    backTo = t.dataset.open && t.closest("#bwrap,#bchain") ? { page: "board" }
      : t.dataset.open && (t.closest("#tscroll") || card) ? { page: "task", id: card ? card.dataset.task : taskId }
      : t.dataset.task && page === "session" ? { page: "session", id: openId } : null;
  }
  if (t.dataset.bpick !== undefined) {  // plan 25: a pick on the Board's chain
    if (t.dataset.btask && t.dataset.btask !== boardTask) { boardTask = t.dataset.btask; boardData = boardChat = null; }
    boardPick = t.dataset.bpick;
    renderBoard();
  } else if (t.dataset.itab) { itab = t.dataset.itab; saveDraft(); renderBoard(); }
  else if (t.dataset.eff) setEffort(t.dataset.eff);
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
  if (e.target.id === "t-editpart" || e.target.id === "b-editpart") {  // the plan editor switches between the index and a part
    planEditPart = Number(e.target.value) || 0;
    const onBoard = e.target.id === "b-editpart", d = onBoard ? boardData && boardData.data : taskData, box = $(onBoard ? "b-edit" : "t-edit");
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
  const onCtl = e.key !== "Escape" && e.target.matches('[data-page="board"] button, [data-page="board"] select');  // plan 27: Enter presses it, the arrows scroll
  if (page === "board" && form === "open" && BOARD_KEYS.has(e.key) && $("pop").hidden && !inField && !onCtl && !e.target.closest(".tabs")) return boardKey(e);
  if (e.key === "Escape") {
    if (!$("pop").hidden) closePicker();
    else if (form === "pill") dismissPeek();
    else if (page === "prep") prepAct("back");
    else if (page === "session" || page === "task" || page === "board") goBack();
    else if (page === "usage") showPage("list");
    else if (page === "models" && !inField && !Object.keys(modelChanges()).length) showPage("list");  // edits stay until Save or Discard
    return;
  }
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    const d = e.key === "ArrowRight" ? 1 : -1, s = current();
    if (e.target.matches("[data-tab]") && s) {
      tab = TABS[(TABS.findIndex(([k]) => k === tab) + d + TABS.length) % TABS.length][0];
      renderProc(s).then(() => { const f = $("tab-" + tab); if (f) f.focus(); }).catch(() => {});
      e.preventDefault();
    } else if (e.target.matches("[data-itab]")) {  // plan 25: the Board's tabs
      const all = [...e.target.parentElement.querySelectorAll("[data-itab]")], to = all[(all.indexOf(e.target) + d + all.length) % all.length];
      itab = to.dataset.itab;
      saveDraft();
      renderBoard().then(() => { const f = document.querySelector(`[data-itab="${itab}"]`); if (f) f.focus(); });
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
  itab = cfg && ["chat", "recv", "hand", "route", "plan"].includes(cfg.board_tab) ? cfg.board_tab : "chat";
  foldState = (cfg && cfg.folds) || {};
  connect();
})();
