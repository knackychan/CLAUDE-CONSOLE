// Claude Console window: renders /api/stream snapshots. Read-only in phase 1.
"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const GROUPS = [["needs", "Needs you"], ["working", "Working"], ["done", "Done today"]];

let snap = null;
let openId = null;
let live = false;

function kTokens(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "K" : String(n || 0); }
function clock(ts) { return new Date(ts * 1000).toTimeString().slice(0, 8); }
function routeText(s) {
  const run = [s.model, s.effort].filter(Boolean).join("/");
  if (s.route === "unrouted") return run ? "unrouted · " + run : "unrouted";
  return run ? s.route + " · " + run : s.route;
}

function gauge(s) {
  if (s.ctx_fill == null) return '<span class="mut">ctx ?</span>';
  const hint = s.ctx_tone === "red" ? " handoff" : s.ctx_tone === "yellow" ? " soon" : "";
  return `<span class="${s.ctx_tone}">ctx <span class="bar"><i style="width:${Math.round(s.ctx_fill * 100)}%"></i></span> ${kTokens(s.ctx_tokens)}${hint}</span>`;
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
  if (s.failed) html += `<div class="note m"><span class="danger">&times; ${esc(s.failed.error)}</span> <span class="mut">${esc(s.failed.details)}</span></div>`;
  for (const a of s.agents) {
    html += `<div class="row m ind"><span class="${a.tone}">${a.symbol}</span>
      <span class="title">${esc(a.type)}${a.model ? " &middot; " + esc(a.model) : ""}${a.effort ? "/" + esc(a.effort) : ""}
      &middot; ${a.doing ? esc(a.doing) : a.steps + (a.steps === 1 ? " step" : " steps")}${a.tokens ? " &middot; " + kTokens(a.tokens) : ""}</span></div>`;
  }
  return html;
}

function visible(s) { return !$("project").value || s.project_dir === $("project").value; }

function renderHome() {
  const rows = snap.sessions.filter(visible);
  let html = "";
  for (const [key, label] of GROUPS) {
    const list = rows.filter((s) => s.group === key);
    if (!list.length) continue;
    html += `<div class="sec">${label}</div>` + list.map(sessionRows).join("");
  }
  $("home").innerHTML = html || '<div class="empty">No Claude Code session in the last 24 h. Start one in VS Code or a terminal.</div>';
}

async function renderDetail() {
  const s = snap.sessions.find((x) => x.id === openId);
  if (!s) { closeDetail(); return; }
  const steps = await (await fetch("/api/steps?session=" + encodeURIComponent(openId))).json();
  let html = sessionRows(s);
  html += `<div class="row m mut">${s.prompts} prompt(s) &middot; ${s.compactions} compaction(s) &middot; route: ${esc(s.route)}</div>`;
  html += '<div class="sec">Steps</div>';
  html += steps.slice().reverse().map((st) => `<div class="row m${st.denied ? " danger" : ""}">
      <span class="mut">${clock(st.ts)}</span><span>${esc(st.agent_type)}</span>
      <span class="title">${esc(st.tool)} ${esc(st.what)}</span></div>`).join("")
      || '<div class="empty">No tool calls yet.</div>';
  $("detail").innerHTML = html;
}

function renderStrip() {
  const c = snap.counts;
  let html = `<span>${live ? "service &#9679; ok" : '<span class="danger">service &#9675; offline</span>'}</span>
    <span>${c.needs} need you &middot; ${c.working} working &middot; ${c.done} done</span>`;
  for (const w of snap.writers) {
    html += `<span class="warning">2 writers: ${esc(w.project_dir.split(/[\\/]/).pop())}</span>`;
  }
  $("strip").innerHTML = html;
  $("counts").innerHTML = c.needs ? `<span class="warning">! ${c.needs}</span>` : "";
}

function renderProjects() {
  const select = $("project");
  const known = new Set([...select.options].map((o) => o.value));
  for (const s of snap.sessions) {
    if (s.project_dir && !known.has(s.project_dir)) {
      select.add(new Option(s.project, s.project_dir));
      known.add(s.project_dir);
    }
  }
}

function render() {
  if (!snap) return;
  renderProjects();
  renderStrip();
  if (openId) renderDetail(); else renderHome();
}

function openDetail(id) { openId = id; $("home").hidden = true; $("detail").hidden = false; $("back").hidden = false; render(); }
function closeDetail() { openId = null; $("home").hidden = false; $("detail").hidden = true; $("back").hidden = true; render(); }

$("home").addEventListener("click", (e) => {
  const row = e.target.closest(".session");
  if (row) openDetail(row.dataset.id);
});
$("back").addEventListener("click", closeDetail);
$("project").addEventListener("change", render);

function connect() {
  const es = new EventSource("/api/stream");
  es.onmessage = (e) => { live = true; snap = JSON.parse(e.data); render(); };
  es.onerror = () => { live = false; if (snap) renderStrip(); };
}
connect();
