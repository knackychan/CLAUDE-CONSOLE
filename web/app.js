// Claude Console window: renders /api/stream snapshots; phase 2 adds the prompt box, Prep card and runs.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const GROUPS = [["needs", "Needs you"], ["working", "Working"], ["done", "Done today"]];
const RESUME_TEXT = "You were interrupted. Check `git diff` first, then finish the task.";

let snap = null;
let cfg = null;       // /api/config
let view = "home";    // home | prep | detail
let openId = null;
let card = null;      // the Prep card on screen
let tab = "steps";
let busy = false;
let live = false;
let actionsSig = "";
let draftTimer = null;
let note = "";       // the composer's last message (an error stays until Fred types)

function kTokens(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "K" : String(n || 0); }
function clock(ts) { return new Date(ts * 1000).toTimeString().slice(0, 8); }
function baseName(p) { return String(p || "").split(/[\\/]/).filter(Boolean).pop() || p; }
function routeText(s) {
  const run = [s.model, s.effort].filter(Boolean).join("/");
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

function gauge(s, tokens = s.ctx_tokens) {
  if (s.ctx_fill == null) return '<span class="mut">ctx ?</span>';
  const hint = s.ctx_tone === "red" ? " handoff" : s.ctx_tone === "yellow" ? " soon" : "";
  return `<span class="${s.ctx_tone}">ctx <span class="bar"><i style="width:${Math.max(2, Math.round(s.ctx_fill * 100))}%"></i></span> ${kTokens(tokens)}${hint}</span>`;
}

function sessionRows(s) {
  let html = `<div class="row m session" data-id="${esc(s.id)}">
    <span class="${s.tone}">${s.symbol} ${esc(s.text)}</span>
    <span class="title">${esc(s.title)}</span>
    ${s.two_writers ? '<span class="badge warning">2 writers</span>' : ""}
    ${gauge(s)}</div>`;
  html += `<div class="row m ind mut"><span class="title">${esc(s.project)} &middot; ${esc(s.source)} &middot; ${esc(routeText(s))}${s.doing ? " &middot; " + esc(s.doing) : ""}</span></div>`;
  if (s.stop_question) html += `<div class="note ask"><span class="warning">? STOP</span> ${esc(s.stop_question)}</div>`;
  if (s.denied) html += `<div class="note m"><span class="danger">&#9632; denied</span> ${esc(s.denied.tool)} ${esc(s.denied.what)} <span class="mut">${esc(s.denied.reason)}</span></div>`;
  if (s.denials && s.denials.length) {
    const d = s.denials[0], more = s.denials.length > 1 ? ` (+${s.denials.length - 1})` : "";
    html += `<div class="note m"><span class="warning">&#9651; ${s.denials.length} denied</span> ${esc(d.tool)} ${esc(d.what)}${more} <span class="mut">the run still finished; open in terminal to allow</span></div>`;
  }
  if (s.failed) html += `<div class="note m"><span class="danger">&times; ${esc(s.failed.error)}</span> <span class="mut">${esc(s.failed.details)}</span></div>`;
  for (const a of s.agents) {
    html += `<div class="row m ind"><span class="${a.tone}">${a.symbol} ${esc(a.text)}</span>
      <span class="title">${esc(a.type)}${a.model ? " &middot; " + esc(a.model) : ""}${a.effort ? "/" + esc(a.effort) : ""}
      &middot; ${a.doing ? esc(a.doing) : a.steps + (a.steps === 1 ? " step" : " steps")}</span>
      ${a.tokens ? gauge(a, a.tokens) : ""}</div>`;
  }
  return html;
}

function visible(s) { return !$("project").value || s.project_dir === $("project").value; }

// -- home ----------------------------------------------------------------------------
function renderHome() {
  const rows = snap.sessions.filter(visible);
  let html = "";
  for (const [key, label] of GROUPS) {
    const list = rows.filter((s) => s.group === key);
    if (!list.length) continue;
    html += `<div class="sec">${label}</div>` + list.map(sessionRows).join("");
  }
  $("home").innerHTML = html || '<div class="empty">No Claude Code session in the last 24 h. Start one in VS Code or a terminal, or below.</div>';
}

function runnable() { return !!cfg && cfg.claude && cfg.projects.includes($("project").value); }

function hint() {
  if (!cfg) return "";
  if (!cfg.claude) return '<span class="danger">claude.exe not found: set "claude_exe" in config.json</span>';
  if (!$("project").value) return '<span class="mut">To run: pick a project in the list at the top (next to "Claude Console")</span>';
  if (!runnable()) return `<span class="mut">Runs are off here: a run uses this repo's hooks and settings without asking.</span>
    <button data-act="allow">Allow runs in ${esc(baseName($("project").value))}</button>`;
  return '<span class="mut">Enter = Prep &middot; Ctrl+Enter = Run raw &middot; Shift+Enter = new line</span>';
}

function say(html) { note = html || ""; $("msg").innerHTML = note || hint(); }

function renderComposer() {
  $("composer").hidden = view !== "home";
  $("prompt").disabled = busy || !runnable();
  $("prompt").placeholder = runnable() ? "Prompt for " + baseName($("project").value) : "";
  if (!busy) $("msg").innerHTML = note || hint();
}

function setBusy(on, text) {
  busy = on;
  note = "";
  renderComposer();
  if (on) say(`<span class="info">${esc(text)}</span>`);
}

async function doPrep() {
  const text = $("prompt").value.trim();
  if (!text || busy || !runnable()) return;
  setBusy(true, "Prep: Haiku is reading " + baseName($("project").value) + " (10-30 s) ...");
  try {
    card = await api("/api/prep", { project_dir: $("project").value, prompt: text });
    setBusy(false);
    showView("prep");
  } catch (e) {
    setBusy(false);
    say(`<span class="danger">Prep failed: ${esc(e.message)}</span>`);
  }
}

async function doRun(projectDir, prompt, model, effort, prepId) {
  if (busy) return;
  setBusy(true, "starting the run ...");
  try {
    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "" });
    $("prompt").value = "";
    saveDraft();
    card = null;
    setBusy(false);
    tab = "chat";
    openDetail(r.session);
  } catch (e) {
    setBusy(false);
    if (view === "prep") $("p-msg").innerHTML = `<span class="danger">${esc(e.message)}</span>`;
    else say(`<span class="danger">Run failed: ${esc(e.message)}</span>`);
  }
}

function runRaw() {
  const text = $("prompt").value.trim();
  if (text && runnable()) doRun($("project").value, text, cfg.default_model, cfg.default_effort, "");
}

$("msg").addEventListener("click", async (e) => {
  if (e.target.dataset.act !== "allow" || busy) return;
  e.target.disabled = true;
  try {
    cfg.projects = (await api("/api/allow", { project_dir: $("project").value })).projects;
    note = "";
    render();
    $("prompt").focus();
  } catch (err) {
    say(`<span class="danger">Allow failed: ${esc(err.message)}</span>`);
  }
});

function saveDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => api("/api/draft", { text: $("prompt").value }).catch(() => {}), 600);
}

// -- Prep card -----------------------------------------------------------------------
function options(list, current) {
  return list.map((v) => `<option${v === current ? " selected" : ""}>${esc(v)}</option>`).join("");
}

function renderPrep() {
  const f = card.fields;
  $("prep").innerHTML = `
    <div class="sec">Prep &middot; ${esc(baseName(card.project_dir))}</div>
    <div class="row m mut">You typed</div>
    <div class="note">${esc(card.raw)}</div>
    ${f.where ? `<div class="row m mut"><span class="title">Scouted: ${esc(f.where)}</span></div>` : ""}
    <div class="row m mut">Enhanced prompt (edit freely)</div>
    <textarea id="p-prompt" class="m edit" rows="9" spellcheck="false">${esc(card.prompt)}</textarea>
    ${f.question ? `<div class="note ask"><span class="warning">? question</span> ${esc(f.question)}</div>` : ""}
    <div class="row m">Route
      <select id="p-model" class="m">${options(cfg.models, card.route.model)}</select>
      <select id="p-effort" class="m">${options(cfg.efforts, card.route.effort)}</select>
      <span class="title mut">${esc(card.route.type)}</span></div>
    ${card.reason ? `<div class="note mut">${esc(card.reason)}</div>` : ""}
    <div class="row m mut">Prep: $${Number(card.cost).toFixed(3)} &middot; ${card.turns} turns</div>
    <div class="actions">
      <button data-act="p-run" class="primary">Run</button>
      <button data-act="p-raw">Run raw</button>
      <button data-act="p-edit">Edit</button>
      <button data-act="p-cancel">Cancel</button>
    </div>
    <div id="p-msg" class="m note"></div>`;
  $("p-prompt").focus();
}

$("prep").addEventListener("click", (e) => {
  const act = e.target.dataset && e.target.dataset.act;
  if (!act || busy) return;
  if (act === "p-run") doRun(card.project_dir, $("p-prompt").value.trim(), $("p-model").value, $("p-effort").value, card.id);
  if (act === "p-raw") doRun(card.project_dir, card.raw, cfg.default_model, cfg.default_effort, "");
  if (act === "p-edit") { card = null; showView("home"); $("prompt").focus(); }
  if (act === "p-cancel") { card = null; $("prompt").value = ""; saveDraft(); showView("home"); }
});

// -- session detail ------------------------------------------------------------------
function renderActions(s) {
  const sig = [s.id, s.window, s.run_live, s.stop_question, s.state].join("|");
  if (sig === actionsSig) return;
  actionsSig = sig;
  if (!s.window) { $("d-actions").innerHTML = ""; return; }
  let html = '<div class="actions">';
  if (s.run_live) html += '<button data-act="stop">Stop</button>';
  else html += '<button data-act="terminal">Open in terminal</button>';
  if (!s.run_live && s.state === "interrupted") html += '<button data-act="resume" class="primary">Resume</button>';
  html += "</div>";
  if (!s.run_live && s.stop_question) {
    html += `<div class="answer"><input id="d-answer" class="m" placeholder="Answer: ${esc(s.stop_question)}">
      <button data-act="answer" class="primary">Answer</button></div>`;
  }
  html += '<div id="d-msg" class="m note"></div>';
  $("d-actions").innerHTML = html;
}

function renderTabs(s) {
  if (!s.window) tab = "steps";
  const tabs = s.window ? [["steps", "Steps"], ["chat", "Chat"]] : [["steps", "Steps"]];
  $("d-tabs").innerHTML = tabs.map(([k, label]) =>
    `<span class="tab${k === tab ? " on" : ""}" data-tab="${k}">${label}</span>`).join("");
}

async function renderBody(s) {
  if (tab === "chat") {
    const chat = await api("/api/chat?session=" + encodeURIComponent(s.id));
    if (openId !== s.id || tab !== "chat") return;
    let html = "";
    if (chat.start_commit) {
      const changed = chat.changed == null ? "?" : chat.changed;
      html += `<div class="row m mut">start ${esc(chat.start_commit.slice(0, 7))} &middot; ${changed} file(s) changed since</div>`;
    }
    html += chat.items.map((i) => `<div class="chat ${i.role}"><span class="who m">${esc(i.role)}</span><div class="text${i.role === "tool" || i.role === "result" ? " m" : ""}">${esc(i.text)}</div></div>`).join("")
      || '<div class="empty">Nothing yet.</div>';
    $("d-body").innerHTML = html;
    return;
  }
  const steps = await (await fetch("/api/steps?session=" + encodeURIComponent(s.id))).json();
  if (openId !== s.id || tab !== "steps") return;
  $("d-body").innerHTML = steps.slice().reverse().map((st) => `<div class="row m${st.denied ? " danger" : ""}">
      <span class="mut">${clock(st.ts)}</span><span>${esc(st.agent_type)}</span>
      <span class="title">${esc(st.tool)} ${esc(st.what)}</span></div>`).join("")
      || '<div class="empty">No tool calls yet.</div>';
}

function renderDetail() {
  const s = snap.sessions.find((x) => x.id === openId);
  if (!s) {
    $("d-head").innerHTML = '<div class="empty">Starting ... (the session shows up with its first event)</div>';
    return;
  }
  let head = sessionRows(s);
  const cost = s.window ? ` &middot; $${Number(s.cost).toFixed(2)}` : "";
  head += `<div class="row m mut">${s.prompts} prompt(s) &middot; ${s.compactions} compaction(s)${cost}${s.stopped ? " &middot; stopped by you" : ""}</div>`;
  if (s.route_reason) head += `<div class="note mut">${esc(s.route_reason)}</div>`;
  $("d-head").innerHTML = head;
  renderActions(s);
  renderTabs(s);
  renderBody(s).catch(() => {});
}

async function act(name, button) {
  const s = snap.sessions.find((x) => x.id === openId);
  if (!s) return;
  button.disabled = true;
  try {
    if (name === "stop") await api("/api/stop", { session: s.id });
    if (name === "terminal") await api("/api/terminal", { session: s.id });
    if (name === "resume") await api("/api/answer", { session: s.id, text: RESUME_TEXT });
    if (name === "answer") {
      const text = $("d-answer").value.trim();
      if (!text) { button.disabled = false; return; }
      await api("/api/answer", { session: s.id, text });
      tab = "chat";
    }
    actionsSig = "";  // redraw from the next snapshot
  } catch (e) {
    button.disabled = false;
    $("d-msg").innerHTML = `<span class="danger">${esc(e.message)}</span>`;
  }
}

$("detail").addEventListener("click", (e) => {
  const t = e.target;
  if (t.dataset.tab) { tab = t.dataset.tab; render(); return; }
  if (t.dataset.act) act(t.dataset.act, t);
});
$("detail").addEventListener("keydown", (e) => {
  if (e.target.id === "d-answer" && e.key === "Enter") act("answer", document.querySelector('[data-act="answer"]'));
});

// -- frame ---------------------------------------------------------------------------
function renderStrip() {
  const c = snap.counts;
  let html = `<span>${live ? "service &#9679; ok" : '<span class="danger">service &#9675; offline</span>'}</span>
    <span>${c.needs} need you &middot; ${c.working} working &middot; ${c.done} done</span>`;
  for (const w of snap.writers) {
    html += `<span class="warning">2 writers: ${esc(baseName(w.project_dir))}</span>`;
  }
  $("strip").innerHTML = html;
  $("counts").innerHTML = c.needs ? `<span class="warning">! ${c.needs}</span>` : "";
}

function addProject(dir, label) {
  const select = $("project");
  const opt = [...select.options].find((o) => o.value === dir);
  if (opt) { if (label.endsWith("(runs)")) opt.text = label; }  // just allowed
  else if (dir) select.add(new Option(label, dir));
}

function renderProjects() {
  if (cfg) for (const p of cfg.projects) addProject(p, baseName(p) + " (runs)");
  if (snap) for (const s of snap.sessions) addProject(s.project_dir, s.project);
}

function render() {
  renderProjects();
  renderComposer();
  if (!snap) return;
  renderStrip();
  if (view === "detail") renderDetail();
  else if (view === "home") renderHome();
}

function showView(name) {
  view = name;
  for (const v of ["home", "prep", "detail"]) $(v).hidden = v !== name;
  $("back").hidden = name === "home";
  if (name === "prep") renderPrep();
  render();
}

function openDetail(id) { openId = id; actionsSig = ""; showView("detail"); }

$("home").addEventListener("click", (e) => {
  const row = e.target.closest(".session");
  if (row) { tab = "steps"; openDetail(row.dataset.id); }
});
$("back").addEventListener("click", () => { openId = null; showView("home"); });
$("project").addEventListener("change", render);
$("prompt").addEventListener("input", () => { note = ""; saveDraft(); });
$("prompt").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || e.shiftKey) return;
  e.preventDefault();
  if (e.ctrlKey) runRaw(); else doPrep();
});

function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => { live = true; snap = JSON.parse(e.data); render(); };
  es.onerror = () => { live = false; if (snap) renderStrip(); };
}

(async () => {
  try { cfg = await api("/api/config"); } catch (e) { cfg = null; }
  try { $("prompt").value = (await api("/api/draft")).text; } catch (e) { /* no draft */ }
  render();
  connect();
})();
