# Task 2: the dock card, the message box and the bar (UI-7, UI-8, UI-9)

Files: `web/app.js`, `web/style.css`, `tests/test_web.py`, `tests/live_board_check.py`, `tests/live_autopilot_check.py`,
`tests/live_task_chat_check.py`. Commit boundary: `feat: the needs-you dock card, the box hints and the bar from actions
(plan 55 Task 2)`. Depends on Task 1. Assumes D2 a, D3 a, D5 a, D6 a. **Stop 1 follows this task** (README section 6).

What the user gets: every gate answered on the page: Confirm and Confirm and auto accept, the decision options with
the default preselected and Take default and auto accept, Approve and Reject with the box's note, Confirm Fable,
Retry on a model with the box's note, Accept step result, Accept and Reopen. The ⋯ task menu is gone: Hand off,
Terminal, Folder and Delete are icons; the state's own actions are words; the primary is at the right edge.

## 1. Rules this task implements (README section 1)

- `GATES = plan_ready, decision, suggestion, hold, failed_twice, stuck, handed`: their `primary` actions are drawn in
  the dock card, never in the bar (UI-9). Every other state's `primary` sits at the bar's right edge: orange `you` for
  `ready` (the mock), ink `go` otherwise (Resume, Accept, Start next task outside a gate).
- The dock card also takes these bar or menu ids of its state: `plan_ready: edit_plan`, `suggestion: reject, dismiss`,
  `hold: keep`, `failed_twice: stepdone`, `stuck: stepdone`; the bar drops them.
- The bar: icons for the `menu` ids `handoff`, `terminal`, `folder`, `delete` (always drawn, greyed with `off`); the
  `menu` words without an icon only when `off === ""` and the action posts or has a form; `level_*` never (they are
  in the head); then `bar` (greyed when off); then the primary outside gates.
- An action with `post: ""` is drawn only when the page has its form (`FORM_IDS`): retry, handoff, add_step,
  edit_plan, reopen, start_next, review. `edit_steps` and `edit_prompt` have none (D3 a, README 4.2).
- After Reject (`actions.hint` present): a quiet dock card, tag "Supervisor", the sentence `actions.line` and the
  rejected decision, the why line `actions.hint`; no buttons (the bar has `add_step` and `finish` when the box is
  not in `next` mode).
- The box shows unless the state is `ready`, `handed`, `observed` or `preparing`. Its placeholder is the mode's hint
  (section 2.4); its Send is enabled from `actions.message.reason` alone.

## 2. Code (`web/app.js`)

### 2.1 The parts (insert after `function taskHead(` from Task 1)

```js
const GATES = new Set(["plan_ready", "decision", "suggestion", "hold", "failed_twice", "stuck", "handed"]);
const DOCK_TAKES = { plan_ready: ["edit_plan"], suggestion: ["reject", "dismiss"], hold: ["keep"], failed_twice: ["stepdone"], stuck: ["stepdone"] };
const FORM_IDS = new Set(["retry", "handoff", "add_step", "edit_plan", "reopen", "start_next", "review"]);
const NO_BOX = new Set(["ready", "handed", "observed", "preparing"]);
const ICON = {  // UI-8: the utility actions as 32 px icons (the locked mock's paths); their names are the served labels
  handoff: '<path d="M9.5 2.5h4v4M13.5 2.5l-6 6M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3"/>',
  terminal: '<rect x="1.5" y="2.5" width="13" height="11" rx="1.5"/><path d="M4.5 6l2 2-2 2M8.5 10.5h3"/>',
  folder: '<path d="M1.5 4.5a1 1 0 0 1 1-1h3.5l1.5 1.5h6a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z"/>',
  delete: '<path d="M2.5 4.5h11M6 4.5V3a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 .5.5v1.5M4 4.5l.7 8.6a1 1 0 0 0 1 .9h4.6a1 1 0 0 0 1-.9l.7-8.6"/>',
  attach: '<path d="M10.5 4.5l-5 5a1.5 1.5 0 0 0 2 2l5.5-5.5a3 3 0 0 0-4-4L3.5 7.5a4.5 4.5 0 0 0 6.5 6.5l4-4"/>' };
const svgIcon = (k) => `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[k]}</svg>`;
let optPick = {};   // task id -> the decision option Fred selected (the default until he picks one)
let sumOpen = "";   // the task whose Finished card lists its changed files
function drawable(a) { return !!a.post || FORM_IDS.has(a.id); }
function iconBtn(a, fn = "runAction") {
  return `<button class="p-ib${a.id === "delete" ? " dz" : ""}" data-aid="${esc(a.id)}" data-afn="${esc(fn)}" title="${esc(a.off ? `${a.label}: ${a.off}` : a.label)}" aria-label="${esc(a.label)}"${a.off ? " disabled" : ""}>${svgIcon(a.id)}</button>`;
}
function dockCard(o) {  // UI-7: a tag, one sentence, at most one line of why, its own buttons, the primary at the right (plan 53 reuses it)
  return `<div class="p-card${o.tone === "r" ? " r" : o.tone === "g" ? " g" : o.tone === "q" ? " q" : ""}" role="group" aria-label="${esc(o.tag)}">
    <span class="lbl ${o.tone || "y"}">${esc(o.tag)}</span>${o.q ? `<div class="q">${esc(o.q)}</div>` : ""}${o.why ? `<div class="why">${esc(o.why)}</div>` : ""}${o.body || ""}
    ${o.left || o.right ? `<div class="p-acts">${o.left || ""}<span class="sp"></span>${o.right || ""}</div>` : ""}</div>`;
}
function barHtml(o, fn = "runAction") {  // UI-8: icons, usage, then the state's words and bar actions, the primary at the right (plan 53 reuses it)
  const b = (a, cls) => actBtn(a, cls, { fn, state: o.state });
  return `<span class="p-tools">${o.icons.map((a) => iconBtn(a, fn)).join("")}</span>${o.use || ""}<span class="sp"></span>`
    + o.words.map((a) => b(a, "")).join("") + o.bar.map((a) => b(a, a.id === "stop" ? "stop" : "")).join("")
    + o.primary.map((a) => b(a, o.state === "ready" ? "you" : "go")).join("");
}
function useHtml(t, row, s = null) {  // UI-8: the shown step's context in 15 cells, its tokens, and the spend (D6 a: no "of $")
  const st = s || t.steps.find((x) => x.n === t.current) || latestStep(t);
  if (!st || st.state === "planned") return "";
  const tok = stepCtx(st), [y, r] = (cfg && cfg.gauge) || [150000, 300000], n = tok == null ? 0 : Math.min(15, Math.round(tok / (r / 15)));
  const cls = Array.from({ length: 15 }, (_, i) => (i < n ? (st.state === "running" && i === n - 1 ? "f live" : tok >= y ? "y" : "f") : ""));
  const spend = s ? `$${stepCostFig(s)} step` : "$" + money(row ? row.cost : 0);
  return `<span class="p-use" title="${esc(tok == null ? ctxUnknown(st) : `Context: ${kTokens(tok)} of ${kTokens(r)}`)} · spend ${esc(spend)}"><span class="cells">${cellsHtml(cls)}</span><b>${tok == null ? "?" : kTokens(tok)}</b><span class="dv"></span><b>${esc(spend)}</b></span>`;
}
function taskBar(t, d, row, withGate = false) {  // withGate: a step page draws the gate's primary in its bar (until Task 5)
  const A = acts(d), gate = GATES.has(A.state) && !withGate, taken = new Set(gate ? DOCK_TAKES[A.state] || [] : []);
  const menu = A.menu.filter((a) => !a.id.startsWith("level_") && !taken.has(a.id));
  return barHtml({ state: A.state, icons: menu.filter((a) => ICON[a.id]), use: useHtml(t, row),
    words: menu.filter((a) => !ICON[a.id] && a.off === "" && drawable(a)), bar: A.bar.filter((a) => !taken.has(a.id) && drawable(a)),
    primary: gate ? [] : A.primary.filter(drawable) });
}
function taskShell(tid, scroll, card, box, bar) {  // UI-7, UI-8: the page scrolls; the card, the box and the bar never scroll away
  return `<div class="idock" data-p="task"><div class="iscroll">${scroll}</div>${card ? `<div class="p-dock">${card}</div>` : ""}${box}<div class="p-bar">${bar}</div>${busyBox(tid)}</div>`;
}
function retryPick(t, cur) {  // D5 a: the model to retry on, inside the card; the note is the box's text
  return `<div class="p-retry"><label class="nl" for="b-retrymodel">Model</label><select class="in" id="b-retrymodel" aria-label="Model for the retry">${modelOptions(cur && cur.pick || "", true, cur && cur.kind)}</select>
    <button class="btn" data-tact="retrycancel" data-tid="${esc(t.id)}">Cancel</button><button class="btn you" data-tact="retry" data-tid="${esc(t.id)}">Retry</button></div>`;
}
function replanList(t) {  // the replan's new and dropped steps (was replanBox, without its buttons: they are served actions)
  const r = t.replan || { before: [], after: [], added: [], dropped: [] }, line = (x) => `${esc(x.kind)}: ${esc(x.goal)}`;
  const dropped = (r.dropped || []).map((i) => r.before[i]).filter(Boolean);
  return `<div class="plan1"><span class="lbl">New plan · ${r.after.length} steps <span class="m">(was ${r.before.length})</span></span>
      <ol>${r.after.map((x, k) => `<li class="${(r.added || []).includes(k) ? "add" : "old"}">${line(x)}</li>`).join("")}</ol></div>
    ${dropped.length ? `<div class="plan1"><span class="lbl">Dropped · ${dropped.length}</span><ol>${dropped.map((x) => `<li class="drop">${line(x)}</li>`).join("")}</ol></div>` : ""}`;
}
```

### 2.2 The card per state

```js
function taskCard(t, d, row) {  // UI-7: "" most of the time; one card for the gate that waits on Fred
  const A = acts(d), s = A.state, P = A.primary.filter(drawable), cur = t.steps.find((x) => x.n === t.current), tid = esc(t.id);
  const take = (id) => [...A.bar, ...A.menu].find((a) => a.id === id && drawable(a));
  const btn = (a, cls = "") => (a ? actBtn(a, cls, { state: s }) : "");
  const sup = d.supervisor || {};
  if (A.hint) return dockCard({ tag: "Supervisor", tone: "q", q: `${A.line}: ${decisionText({ decision: (sup.rejected || {}).decision }, t)}.`, why: A.hint });
  if (s === "plan_ready") {
    const left = t.steps.filter((x) => x.state === "planned").length;
    return dockCard({ tag: "Plan to confirm", q: `The plan is written. Confirm it and the last ${left} ${left === 1 ? "step runs" : "steps run"} on their own.`,
      left: btn(take("edit_plan")), right: btn(P.find((a) => a.id === "confirm_auto")) + btn(P.find((a) => a.id === "confirm"), "you") });
  }
  if (s === "decision") {
    const dec = t.decision || {}, why0 = String(t.why || "").replace(/^asks: /, ""), gap = why0.startsWith("Plan gap:");
    const opts = P.filter((a) => a.id !== "default_auto"), q = dec.q || row.asks || why0.replace(/^Plan gap:\s*/, "");
    if (!opts.length) return dockCard({ tag: gap ? "Plan gap" : "Asks you", q, why: gap ? "Answer it in the box below; it joins the plan's Decisions." : "Answer it in the box below." });
    const pick = opts.find((a) => a.id === optPick[t.id]) || opts.find((a) => a.id === dec.default) || opts[0];
    const tm = Number(((cfg && cfg.tuning && cfg.tuning.decision_timeout_s) || {}).value || 0);
    const mins = sup.mode === "auto" && dec.default && dec.asked && tm ? Math.max(1, Math.ceil((dec.asked + tm - snap.now) / 60)) : 0;
    const rows = opts.map((a) => `<button class="p-opt${a.id === dec.default ? " isdef" : ""}${a === pick ? " sel" : ""}" data-optpick="${esc(a.id)}" data-tid="${tid}" aria-pressed="${a === pick}"${a.off ? ` disabled title="${esc(a.off)}"` : ""}>
      <span class="k">${esc(a.id)}</span><span>${esc(a.label)}</span>${a.id === dec.default ? '<span class="def">default</span>' : "<span></span>"}</button>`).join("");
    return dockCard({ tag: "Your decision", q, why: [dec.why, mins ? `Console takes the default in ${mins} min if you do not choose.` : "The task waits for you."].filter(Boolean).join(" "),
      body: `<div class="p-opts" role="group" aria-label="Options">${rows}</div>`,
      right: btn(P.find((a) => a.id === "default_auto")) + actBtn(pick, "you", { state: s, label: "Confirm " + pick.id }) });
  }
  if (s === "suggestion") {
    const p = sup.pending || {}, [tag, tone] = SUP_HEAD[p.status] || SUP_HEAD.suggest;
    return dockCard({ tag, tone, q: decisionText(p.decision || {}, t) + ".", why: p.reason || p.error || "",
      left: btn(take("reject")) + btn(take("dismiss")), right: btn(P.find((a) => a.id === "approve"), "you") });
  }
  if (s === "hold") {
    const why = String(t.why || ""), fable = why === "confirm Fable", replan = why.startsWith("replanned:"), F = fableName() || "Fable";
    const q = fable ? `The ${cur ? cur.kind : "step"} wants to run on ${F}.` : replan ? `Replanned after step ${two(Math.max(1, (cur ? cur.n : 2) - 1))}.` : `Held: ${A.line.replace(/^held · /, "")}.`;
    return dockCard({ tag: "Held", q, why: fable ? `${F} is scarce, so you confirm it each time.` : "", body: replan ? replanList(t) : "",
      left: btn(take("keep")), right: P.map((a) => btn(a, "you")).join("") });
  }
  if (s === "failed_twice" || s === "stuck") {
    const failed = [...t.steps].reverse().find((x) => x.state === "failed" || x.verdict === "FAIL");
    const see = failed ? `<button class="btn" data-bpick="s${failed.n}" data-btask="${tid}">See the failure</button>` : "";
    return dockCard({ tag: s === "stuck" ? "Stuck" : "Failed twice", tone: "r", q: A.line.replace(/^(failed twice|stuck) · /, ""),
      why: s === "failed_twice" ? "Retry with a note, or take the result as it is." : "",
      body: retryOpen === t.id ? retryPick(t, cur) : "", left: see, right: btn(take("stepdone")) + P.map((a) => btn(a, "you")).join("") });
  }
  if (s === "done" && d.summary) {
    const sm = d.summary, f = (sm.files || []).length, fail = sm.steps.some((x) => x.verdict === "FAIL"), open = (sm.questions || []).length;
    const list = sumOpen === t.id ? `<ul class="p-files">${sm.files.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
    return dockCard({ tag: t.accepted ? "Accepted" : "Finished", tone: "g", q: `${sm.steps.length} steps${fail ? "" : " passed"}. ${f} ${f === 1 ? "file" : "files"} written.`,
      why: open ? `${open} open ${open === 1 ? "question" : "questions"} left.` : "", body: list,
      left: f ? `<button class="lnk" data-tact="sumfiles" data-tid="${tid}" aria-expanded="${!!list}">See the changed files</button>` : "" });
  }
  return "";  // handed: Task 6; running, paused, stopped, ready: nothing waits on Fred
}
```

### 2.3 The forms and the note (replace Task 1's two stubs)

Replace `function actBody(a) { return { ...a.body }; }  // Task 2 adds the box text as Reject's note` and
`function openActionForm(a, button, d) {}  // Task 2 fills ...` by:

```js
function actBody(a) {  // D5 a: Reject carries the box's words as its note
  const body = { ...a.body };
  if (a.id === "reject") { const note = ($("b-tcont")?.value || "").trim(); if (note) body.note = note; }
  return body;
}
function clearDraftText(tid) { const dr = taskDraft[tid]; if (dr) { dr.text = ""; dr.start = dr.end = 0; saveTaskDraft(tid); } }
function openActionForm(a, button, d) {  // a served action with post "" opens its existing form; the form posts its existing route
  const tid = boardTask, t = d && d.task;
  if (a.id === "retry") { retryOpen = retryOpen === tid ? "" : tid; renderBoard(); }
  else if (a.id === "handoff") taskHandoff("handofftask", tid);
  else if (a.id === "add_step") openNextForm(tid, undefined, Number(a.body.source_step) || 0, true);
  else if (a.id === "edit_plan") { planEdit = !planEdit; renderBoard(); }
  else if (a.id === "reopen") { const box = $("b-tcont"); if (box) box.focus(); }
  else if (a.id === "start_next") startNext(tid, button);
  else if (a.id === "review" && t) startReview(t.project_dir);
}
```

In `async function runAction(button)`, replace `    await api(a.post, actBody(a));` with:

```js
    const body = actBody(a);
    await api(a.post, body);
    if (body.note) clearDraftText(boardTask);
```

### 2.4 The box (`stepFooter`, `taskMessageState`)

Add after `const NO_BOX`:

```js
function boxHint(A) {  // UI-8: one plain hint per mode (the mock's words); Reject's hint comes from the service
  if (A.hint) return A.hint;
  if (A.state === "suggestion") return "Why not, or what to do instead";
  if (A.state === "failed_twice" || A.state === "stuck") return "Tell the agent what to try differently on the retry";
  const m = A.message ? A.message.mode : "";
  return m === "answer" ? "Or write your own answer" : m === "next" ? "Ask for something more: it becomes the next step"
    : "Message the agent while it works, for example: use vitest, not jest";
}
```

`function taskMessageState(t, d)`: replace the whole body from `  let off = lv.continue || "";` to the final
`return { off, question, answer, gap, row, cur };` by:

```js
  const m = acts(d).message || d.message;  // plan 55: the served availability; no client rule decides delivery
  const answer = !!m && m.mode === "answer";
  let off = m ? m.reason || "" : "Reading delivery availability. Draft kept.";
  if (m && m.attachments === false && att[taskAttachKey(t.id)].length) off = m.mode === "next"
    ? "The supervisor reads text only. Remove the files." : "This harness cannot receive attachments. Remove the files or Retry on Claude.";
  if (gap && att[taskAttachKey(t.id)].length) off = "Plan-gap answers do not support attachments yet. Remove the files to send this answer.";
  if (streamLost || taskDisconnected.has(t.id)) off = "Disconnected. Draft kept; delivery is unavailable.";
  return { off, question, answer, gap, row, cur };
```

and in its first lines change `const answer = gap || !!(row?.stop_question || tr.asks);` to nothing (delete the line;
`answer` is computed above). The attachment and disconnect lines are client data guards (they keep files from being
dropped silently), not availability.

`function stepFooter(t, s, d, row)`: replace its `return` template by:

```js
  const A = acts(d), line = off || (state.gap ? "Your answer joins the plan's Decisions and continues this step." : "");
  return `<div class="task-composer p-box" data-task-composer="${tid}">
    ${historical ? `<div class="say history">History: step ${two(s?.n || cur.n)}${boardHistory ? " · earlier attempt" : ""}. Messages go to the current step.</div>` : ""}
    <label for="b-tcont" class="vh">${esc(destination)}</label>
    ${state.question ? `<div class="q">${esc(state.question)}</div>` : ""}
    ${taskMessages(t, d)}
    <div class="p-steer"><textarea class="in" id="b-tcont" data-tid="${tid}" data-sid="${esc(cur?.session || "")}" rows="1" aria-describedby="b-delivery" title="${esc(destination)}" placeholder="${esc(boxHint(A))}">${esc(draft.text)}</textarea>
      <button class="p-ib" data-attach="${key}" title="Attach files" aria-label="Attach files"${(A.message || d.message)?.attachments === false ? ` disabled title="${noFiles}"` : ""}>${svgIcon("attach")}</button>
      <button class="btn ${state.answer ? "you" : "go"}" data-tact="${state.answer ? "answer" : "cont"}" data-tid="${tid}"${off || draft.busy ? " disabled" : ""}>${draft.busy ? "Sending ..." : state.answer ? "Send answer" : "Send"}</button>${changed ? b("retarget", "Use current step") : ""}</div>
    <ul class="files" aria-label="Attached files">${filesHtml(key)}</ul>
    <div class="say${line ? "" : " vh"}" id="b-delivery">${esc(line || (A.message || d.message)?.timing || "Sends to the current conversation.")}</div>
    ${draft.error ? `<div class="say r" role="status">${esc(draft.error)}</div>` : ""}
    ${cold ? `<div class="say">Cold cache: ${kTokens(cold.tokens)} tokens, idle ${Math.round(cold.idle_s / 3600)} h. Re-read about $${money(cold.cost)}; a second click confirms.</div>` : ""}
    </div>`;
```

and change its line `const next = d.message?.mode === "next";` to `const next = (acts(d).message || d.message)?.mode === "next";`.

### 2.5 `inspTask` and what goes

Replace `function inspTask(t, d, row) { ... }` (from its signature line through its closing `}` after `return dock(...)`) by:

```js
function inspTask(t, d, row) {  // plan 55: head, the forms an action opened, recovery and the body scroll; the card, box and bar stay
  const tid = esc(t.id), cur = t.steps.find((s) => s.n === t.current);
  const [, src] = nextOpen && nextOpen.tid === t.id ? nextSource(d) : [null, null];
  const body = `${taskHead(t, d, row)}${handoffForm(t)}${planEdit ? planEditBox(t, d, tid) : ""}${src ? nextFormHtml(t, src, row, d) : ""}${recoveryBox(t, d)}
    ${supCard(t, d)}${routeHtml(t, d, row)}${fold("Goal", "", `<pre class="text goal">${esc(t.goal)}</pre>`, { key: "tgoal" })}${questionsFold(d)}`;
  return taskShell(t.id, `<div class="ipane">${body}</div>`, taskCard(t, d, row), NO_BOX.has(acts(d).state) ? "" : stepFooter(t, cur, d), taskBar(t, d, row));
}
```

`renderInspector` keys the docked layout on `html.startsWith('<div class="idock"')`: `taskShell` starts with
`<div class="idock" data-p="task">`, which matches.

Delete, each whole: `function taskButtons(`, `function taskMenu(`, `function attentionArea(`, `function confirmLabel(`,
`function replanBox(`, `function gaugeHtml(`, `async function supAct(`; the lets `doneConfirm` and `supNote`; in
`supCard` the pending branch (from `  if (p && SUP_HEAD[p.status]) {` through its closing `}`) and the rejected
branch (from `  const rj = sup.rejected;` through its closing `}`), so `supCard` keeps only the quiet last decision
until Task 3. In `taskAct`: the lines `if (["supapprove", "supreject"].includes(name)) return supAct(name, button, id);`,
`if (name === "done") { doneConfirm = id; ... }`, `if (name === "canceldone") ...`, `if (name === "confirmdone") ...`;
change `const box = name === "retry" ? $("b-retrynote") : null;` to `const box = name === "retry" ? $("b-tcont") : null;`
and after `if (name === "retry") retryOpen = "";` add `if (name === "retry" && box && box.value.trim()) clearDraftText(id);`;
add before `if (!id) return;`:

```js
  if (name === "sumfiles") { sumOpen = sumOpen === id ? "" : id; renderBoard(); return; }
```

`function inspReplan(`: replace `${replanBox(t, s, d, row)}` with `<div class="askbox">${replanList(t)}</div>`.
`function inspGap(`: delete its `const b = ...` line and the `<div class="lr">${b("redo", ...)}${b("stop", ...)}</div>` line.
`function stepButtons(`: replace `if (s.n === t.current) return taskButtons(t, d);` with
`if (s.n === t.current) return \`<div class="p-bar">${taskBar(t, d, boardRow(t.id), true)}</div>\`;`.
`function recoveryBox(`: replace `(task menu)` with `(card)` in the two Retry and Accept sentences, and
`Stop (bar) ends that run.` stays.
The click handler: add `[data-optpick],` to the selector and, before the `data-aid` branch from Task 1:
`  else if (t.dataset.optpick) { optPick[t.dataset.tid] = t.dataset.optpick; renderBoard(); }`.
`taskChatAct`'s `chatresume` case: delete it if `grep -n 'chatresume' web/app.js` finds no other caller (the stopped
state's Resume is the served `/api/continue` action now).

## 3. Style (`web/style.css`, append after Task 1's block)

```css
/* plan 55: the needs-you dock card (UI-7), the box and the bar (UI-8) */
.idock[data-p] .iscroll { padding: 14px 18px 18px; scrollbar-gutter: stable; }
.p-dock { flex: none; max-height: 300px; overflow-y: auto; padding: 0 12px 8px; }
.p-card { display: grid; gap: 8px; grid-template-columns: minmax(0, 1fr); padding: 10px 12px; border-radius: 8px;
  background: color-mix(in srgb, var(--you) 9%, var(--win)); border: 1px solid color-mix(in srgb, var(--you) 40%, transparent); }
.p-card.r { background: color-mix(in srgb, var(--bad) 8%, var(--win)); border-color: color-mix(in srgb, var(--bad) 40%, transparent); }
.p-card.g, .p-card.q { background: var(--raise); border-color: var(--line); }
.p-card .q { font-size: 14px; font-weight: 600; }
.p-card .why { font-size: 13px; color: var(--mut); }
.lbl.g { color: var(--ok); }
.p-acts { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.p-acts .sp, .p-bar .sp { flex: 1; }
.p-opts { display: grid; gap: 6px; }
.p-opt { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; gap: 8px; align-items: baseline; min-height: 32px; padding: 8px 10px;
  border-radius: 6px; border: 1px solid var(--line); background: var(--win); color: var(--ink); font: 13px var(--ui); text-align: left; cursor: pointer; }
.p-opt:hover:not(:disabled) { border-color: var(--ink); }
.p-opt .k { font: 600 12px var(--mono); color: var(--mut); }
.p-opt .def { font: 600 11px var(--mono); color: var(--you); border: 1px solid color-mix(in srgb, var(--you) 45%, transparent); padding: 1px 5px; border-radius: 3px; }
.p-opt.isdef { border-color: color-mix(in srgb, var(--you) 55%, transparent); }
.p-opt.sel { border-color: var(--ink); box-shadow: inset 3px 0 0 var(--you); }
.p-retry { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.p-files { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font: 12px var(--mono); overflow-wrap: anywhere; }
.lnk { justify-self: start; min-height: 24px; background: none; border: 0; padding: 0; color: var(--ink); font: 12.5px var(--ui);
  text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--mut); cursor: pointer; }
.lnk:hover { text-decoration-color: var(--ink); }
.p-box { flex: none; border-top: 1px solid var(--line); padding: 12px 12px 4px; display: grid; gap: 6px; }
.p-steer { display: flex; gap: 8px; align-items: center; }
.p-steer textarea { flex: 1; min-width: 0; min-height: 40px; max-height: 120px; resize: none; padding: 8px 12px; font-size: 13.5px; }
.p-steer .btn { min-height: 40px; padding: 0 16px; }
.p-bar { flex: none; border-top: 1px solid var(--line); padding: 8px 12px 10px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.p-tools { display: inline-flex; gap: 2px; }
.p-tools:empty { display: none; }
.p-ib { width: 32px; height: 32px; flex: none; display: grid; place-items: center; border: 1px solid transparent; border-radius: 6px;
  background: transparent; color: var(--mut); cursor: pointer; }
.p-ib:hover:not(:disabled) { color: var(--ink); border-color: var(--line); background: var(--raise); }
.p-ib.dz:hover:not(:disabled) { color: var(--bad); border-color: color-mix(in srgb, var(--bad) 45%, transparent); }
.p-ib:disabled { opacity: .4; cursor: default; }
.p-use { display: inline-flex; align-items: center; gap: 6px; margin: 0 4px 0 8px; font: 11px var(--mono); color: var(--mut); white-space: nowrap; }
.p-use .cells { grid-template-columns: repeat(15, 4px); }
.p-use b { font-weight: 400; color: var(--ink); }
.p-use .dv { width: 1px; height: 14px; background: var(--line); }
.vh { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
@container (max-width: 560px) { .p-use .cells { display: none; } }
```

## 4. Tests

### 4.1 New (red first), `tests/test_web.py`

```python
@unittest.skipUnless(NODE, "Node is not installed")
class AutopilotDockTest(unittest.TestCase):
    """Plan 55 Task 2: the dock card, the box and the bar place GET /api/task actions; no gate is rebuilt in JS."""
    A = """const act = (id, label, post, body, o = {}) => Object.assign({id, label, post, body: Object.assign({task: 't'}, body || {}), off: '', confirm: false}, o);
      const icons = [act('handoff', 'Hand off', ''), act('terminal', 'Open in terminal', '/api/terminal', {session: 's'}),
        act('folder', 'Open folder', '/api/task/folder'), act('delete', 'Delete', '/api/task/clear', {}, {confirm: true}),
        act('retry', 'Retry on a model', '', {}, {off: 'still running'}), act('level_gated', 'gated', '/api/task/supervisor', {mode: 'gated'})];
      const A = (state, primary, bar, o = {}) => Object.assign({state, line: state, primary, bar, menu: icons, message: {mode: 'queued', reason: '', timing: 'Queued', target: {step: 1, attempt: 1}}}, o); """
    setup = OpenedTaskTest.setup + A

    def card(self, expr):
        return render(self.setup + expr + "; taskCard(t, d, row)")

    def bar(self, expr):
        return render(self.setup + expr + "; taskBar(t, d, row)")

    def test_plan_ready_card_and_bar(self):
        x = ("d.actions = A('plan_ready', [act('confirm', 'Confirm plan', '/api/task/confirm'), act('confirm_auto', 'Confirm, and run plans automatically from now on', '/api/task/confirm', {remember: 'auto'})], "
             "[act('edit_plan', 'Edit plan', ''), act('redo', 'Redo design', '/api/task/redo'), act('stop', 'Stop', '/api/task/stop', {}, {confirm: true})])")
        card = self.card(x)
        self.assertIn("Plan to confirm", card)
        self.assertLess(card.index('data-aid="edit_plan"'), card.index('data-aid="confirm_auto"'))
        self.assertLess(card.index('data-aid="confirm_auto"'), card.index('data-aid="confirm"'))
        self.assertIn(">Read or edit the plan<", card)
        self.assertIn(">Confirm and auto accept<", card)
        self.assertRegex(card, r'class="btn you" data-aid="confirm"[^>]*>Confirm<')
        bar = self.bar(x)
        for gone in ('data-aid="edit_plan"', 'data-aid="confirm"', 'data-aid="confirm_auto"', 'data-aid="level_gated"', 'data-aid="retry"'):
            self.assertNotIn(gone, bar)
        for there in ('data-aid="redo"', 'data-aid="stop"', 'data-aid="handoff"', 'data-aid="terminal"', 'data-aid="folder"', 'data-aid="delete"'):
            self.assertIn(there, bar)
        self.assertLess(bar.index('data-aid="delete"'), bar.index('data-aid="redo"'))  # icons left, words right

    def test_decision_card_preselects_the_default_and_confirms_the_pick(self):
        x = ("t.decision = {q: 'Which folder name?', options: [{key: 'a', text: 'PRODUCT_SHEETS_DIR'}, {key: 'b', text: 'SHEETS_DIR'}], default: 'a', asked: 90}; "
             "d.actions = A('decision', [act('a', 'PRODUCT_SHEETS_DIR', '/api/task/message', {mode: 'answer', text: 'PRODUCT_SHEETS_DIR'}), "
             "act('b', 'SHEETS_DIR', '/api/task/message', {mode: 'answer', text: 'SHEETS_DIR'}), act('default_auto', 'Take the default from now on', '/api/task/message', {mode: 'answer', text: 'PRODUCT_SHEETS_DIR', remember: 'auto'})], "
             "[act('stop', 'Stop', '/api/task/stop', {}, {confirm: true})])")
        card = self.card(x)
        self.assertIn('data-optpick="a" data-tid="t" aria-pressed="true"', card)
        self.assertIn('data-optpick="b" data-tid="t" aria-pressed="false"', card)
        self.assertIn(">default<", card)
        self.assertIn('data-aid="a" data-afn="runAction">Confirm a<', card)
        self.assertIn(">Take default and auto accept<", card)
        self.assertIn("The task waits for you.", card)
        self.assertIn('data-aid="b" data-afn="runAction">Confirm b<', self.card(x + "; optPick.t = 'b'"))
        auto = self.card(x + "; d.supervisor = {mode: 'auto'}; cfg = {tuning: {decision_timeout_s: {value: 600}}}")
        self.assertIn("Console takes the default in 9 min if you do not choose.", auto)  # snap.now 100, asked 90
        plain = self.card("t.why = 'asks: Which database?'; row.asks = 'Which database?'; d.actions = A('decision', [], [])")
        self.assertIn("Which database?", plain)
        self.assertNotIn("data-aid", plain)

    def test_suggestion_card_and_the_card_after_reject(self):
        x = ("d.supervisor = {mode: 'suggest', pending: {wake: 3, status: 'suggest', reason: 'a verify checks 340 px', error: '', decision: {decision: 'add_next_step', kind: 'verify', source_step: 1, model: 'auto'}}, audit: []}; "
             "d.actions = A('suggestion', [act('approve', 'Approve', '/api/task/supervisor', {wake: 3, action: 'approve'})], "
             "[act('reject', 'Reject', '/api/task/supervisor', {wake: 3, action: 'reject'}), act('stop', 'Stop', '/api/task/stop', {}, {confirm: true})])")
        card = self.card(x)
        self.assertIn("Supervisor suggests", card)
        self.assertIn("Add 03 verify from 01&#39;s handover.", card)
        self.assertLess(card.index('data-aid="reject"'), card.index('data-aid="approve"'))
        self.assertNotIn('data-aid="reject"', self.bar(x))
        after = self.card("d.supervisor = {mode: 'suggest', pending: null, rejected: {wake: 3, decision: 'add_next_step', note: true}}; "
                          "d.actions = A('running', [], [], {line: 'You rejected wake 3', hint: 'Write what to do instead, your note goes with it'})")
        self.assertIn("You rejected wake 3", after)
        self.assertIn("Write what to do instead, your note goes with it", after)
        self.assertNotIn("data-aid", after)

    def test_hold_failed_twice_and_done(self):
        fable = self.card("t.why = 'confirm Fable'; d.actions = A('hold', [act('confirm', 'Confirm', '/api/task/confirm', {}, {confirm: true})], [])")
        self.assertIn("Confirm Fable<", fable)
        failed = ("t.state = 'stuck'; t.steps[0].state = 'failed'; d.actions = A('failed_twice', [act('retry', 'Retry on a model', '')], "
                  "[act('stepdone', 'Accept step result', '/api/task/stepdone'), act('finish', 'Finish', '/api/task/done', {}, {confirm: true})], {line: 'failed twice · verify failed twice'})")
        card = self.card(failed)
        self.assertIn('data-bpick="s1" data-btask="t">See the failure<', card)
        self.assertIn('data-aid="stepdone"', card)
        self.assertIn('class="btn you" data-aid="retry"', card)
        self.assertNotIn("b-retrymodel", card)
        self.assertIn('id="b-retrymodel"', self.card(failed + "; retryOpen = 't'"))
        self.assertNotIn('data-aid="stepdone"', self.bar(failed))
        self.assertIn('data-aid="finish"', self.bar(failed))
        done = ("t.state = 'done'; d.summary = {steps: [{n: 1, kind: 'code', verdict: ''}, {n: 2, kind: 'verify', verdict: 'PASS'}], files: ['a.ts', 'b.ts'], questions: []}; "
                "d.actions = A('done', [act('accept', 'Accept', '/api/task/accept')], [act('reopen', 'Reopen', '')])")
        self.assertIn("2 steps passed. 2 files written.", self.card(done))
        self.assertRegex(self.bar(done), r'class="btn go" data-aid="accept"')
        self.assertIn('data-aid="reopen"', self.bar(done))

    def test_bar_draws_menu_words_only_when_open_and_forms_only_when_the_page_has_them(self):
        x = ("d.actions = A('ready', [act('start', 'Start', '/api/task/resume')], [act('edit_steps', 'Edit steps', ''), act('drop', 'Drop', '/api/task/clear', {}, {confirm: true})])")
        bar = self.bar(x)
        self.assertNotIn("edit_steps", bar)  # D3 a: no editor for a saved planned task
        self.assertRegex(bar, r'class="btn you" data-aid="start"')
        self.assertIn('class="p-ib dz" data-aid="delete"', bar)
        self.assertNotIn('data-aid="retry"', bar)  # a menu word that is off is not drawn
        self.assertIn('title="Hand off"', bar)

    def test_box_hint_per_mode_and_hidden_where_no_words(self):
        hints = {"A('running', [], [])": "Message the agent while it works",
                 "A('decision', [], [], {message: {mode: 'answer', reason: ''}})": "Or write your own answer",
                 "A('done', [], [], {message: {mode: 'next', reason: ''}})": "Ask for something more: it becomes the next step",
                 "A('suggestion', [], [])": "Why not, or what to do instead",
                 "A('failed_twice', [], [])": "Tell the agent what to try differently on the retry"}
        for expr, hint in hints.items():
            with self.subTest(expr):
                self.assertIn(hint, render(self.setup + f"d.actions = {expr}; stepFooter(t, t.steps[0], d)"))
        for state in ("ready", "handed"):
            self.assertNotIn('id="b-tcont"', render(self.setup + f"d.actions = A('{state}', [], []); inspTask(t, d, row)"))
        off = render(self.setup + "d.actions = A('running', [], [], {message: {mode: 'queued', reason: 'Task not started'}}); stepFooter(t, t.steps[0], d)")
        self.assertIn("Task not started", off)
        self.assertRegex(off, r'data-tact="cont"[^>]* disabled')

    def test_reject_sends_the_box_text_as_its_note(self):
        got = render(self.setup + """(async () => {
          const calls = []; api = async (p, b) => { calls.push([p, b]); return {}; }; renderBoard = async () => {};
          d.actions = A('suggestion', [], [act('reject', 'Reject', '/api/task/supervisor', {wake: 3, action: 'reject'})]);
          boardTask = 't'; boardData = {id: 't', data: d}; taskDraft.t = {text: ' not yet ', target: '', start: 0, end: 0};
          const els = {'b-tcont': {value: ' not yet '}}; document = {getElementById: (id) => els[id] || null};
          await runAction({dataset: {aid: 'reject'}, innerHTML: '', textContent: '', disabled: false});
          return {calls, left: taskDraft.t.text};
        })()""")
        self.assertEqual(got["calls"], [["/api/task/supervisor", {"task": "t", "wake": 3, "action": "reject", "note": "not yet"}]])
        self.assertEqual(got["left"], "")

    def test_no_client_gate_is_left(self):
        src = APP.read_text(encoding="utf-8")
        for gone in ("function taskButtons(", "function taskMenu(", "function attentionArea(", "function confirmLabel(", "function supAct(",
                     "function gaugeHtml(", "function replanBox(", "doneConfirm", "supNote", 'lv.stop === ""', 'lv.pause === ""',
                     "d.handoff_available === \"\"", "details class=\"action-more\" data-key=\"more\""):
            self.assertNotIn(gone, src)
```

### 4.2 Deleted or rewritten in the same commit

- Deleted (what they pin is gone by design): `TaskOverviewTest.test_finish_task_is_in_the_menu_and_its_confirm_is_inline_and_green`,
  `test_accept_step_result_is_recovery_only`, `test_retry_is_drawn_once_and_only_when_the_menu_opened_it`,
  `test_manual_boundary_does_not_say_to_resume`, `test_no_paused_note_unless_resume_is_open`,
  `test_resume_renders_from_the_lever_after_a_pause`, `test_verify_is_inside_add_step_not_standalone`,
  `test_question_and_confirm_share_one_attention_area`; `OpenedTaskTest.test_sup_card_shows_approve_only_where_allowed`,
  `test_task_bar_is_stop_or_resume_pause_and_menu`; `LooseEndsWebTest.test_sup_card_after_reject_points_to_the_box`.
  Their behaviour is now `Hub.actions`' (covered by `tests/test_server.py::test_actions_per_state` and
  `test_actions_after_reject_and_in_recovery`) and the placement tests above.
- `TaskOverviewTest.test_replan_approval_renders_on_overview`: render `taskCard(t, d, row)` with
  `d.actions = A('hold', [act('confirm', 'Confirm plan', '/api/task/confirm')], [act('keep', 'Keep old plan', '/api/task/keep')])`;
  assert one `data-aid="confirm"`, one `data-aid="keep"`, the word `search`, no `Open step 2`.
- `RecoveryBoxTest` (four tests) and `LooseEndsWebTest.test_recovery_box_names_the_uncertain_decision`: call
  `recoveryBox(t, d)` instead of `attentionArea(t, d, row)`; the expected `(task menu)` becomes `(card)`.
- `UnifiedTaskChatTest`: every case that builds `d` without `message` gains `d.message = {mode, reason, timing, target}`
  with the reason the old fallback produced (the server's own words: `tests/test_server.py` pins them); the
  `test_table_states_keep_editable_input_and_honest_delivery_gate` case list asserts `reason` shown verbatim and
  "Reading delivery availability. Draft kept." when `d.message` is absent. `test_composer_has_no_duplicate_session_controls`
  keeps its assertions (`Attach` is in the icon's label).
- `OpenedTaskTest.test_route_lists_proposed_steps_dim`: drop the three `gaugeHtml` assertions (the bar's `useHtml`
  is tested above); the route part stays until Task 3.

### 4.3 Headless (`tests/live_board_check.py`, add to `CHECKS`)

```python
def dock_checks(page, name):  # Task 2: the card stays in sight, the primary is the rightmost control, no ⋯ menu
    assert page.locator("details.action-more").count() == 0, (name, "no task menu")
    card = page.locator(".p-card")
    if name in ("plan_ready", "decision", "suggestion"):
        assert card.count() == 1, (name, "one dock card")
        box, main = card.bounding_box(), page.locator(".idock[data-p]").bounding_box()
        assert box["y"] >= main["y"] and box["y"] + box["height"] <= main["y"] + main["height"], (name, "card scrolled away")
        right = page.locator(".p-card .p-acts > *").last
        assert "you" in (right.get_attribute("class") or ""), (name, "primary at the right")
    if name in ("running", "planning"):
        assert card.count() == 0, (name, "no card while it runs")
    assert page.locator(".p-bar .p-ib").count() >= 2, (name, "icon tools")
```

`tests/live_autopilot_check.py`: check 1's `page.get_by_role("button", name="Confirm plan", exact=True)` becomes
`page.locator('.p-card [data-aid="confirm"]')`. `tests/live_task_chat_check.py`: the two `details.action-more summary`
clicks go; Hand off is `page.locator('.p-bar [data-aid="handoff"]')`; the `nextopen` step (Add step on a model from the
task menu) is replaced by the same check on a rejected supervisor card's bar (`[data-aid="add_step"]`), or dropped
with a note if that fixture has no supervisor (D3 a: `actions` lists Add step only after Reject).

## 5. Run

`node --check web/app.js`; `py -m unittest tests.test_web`; `py -m tests.live_autopilot_check`; `py -m tests.live_task_chat_check`;
`py -m tests.live_board_check --shots <scratch>`; the full suite in the background. Then **stop 1**: send Fred the
screenshots (the mock's states and README section 5's) and wait for his answer on D14 and README 4.3.
