# Task 6: The window: the Handoff fold, the HANDOFF chip, the HANDED OFF card, the Window runs switch

> Contract: [README.md](README.md) 3.4, 3.7, 3.8 (what `GET /api/task`, `task_row`, the session row and `/api/config`
> carry). Design: interface doc 3 (the HANDED OFF card), 4 (Window runs, ID-2), 6.1 (the chip), 7 (the Handoff fold and
> its Facts), ID-5 (no word cells on a handoff), ID-9 (Received / Handoff in the UI). Mock:
> `design/rework/locked/cells-board.html`: `fold` (line 922), `headingBlock` (981), the `tpage` view's `handoff` fold
> (1290), the HANDED OFF card in `listHtml` (1230), `settingsHtml` (1305, the `windowRuns` row), `chatHtml`'s chip
> (1042); CSS lines 185 to 188 (`.hn`), 216 to 244 (`.pset`, `.sr`, `.sw`), 351 to 352 (`.turn .hchip`), 516 to 527
> (`.hb`, `.hsec`, `li.cut`, `.fold.facts`), 582 to 590 (`.fold`, `.fh`, `.fb`). Depends on Task 5. Guided: not run in
> the scratch copy; every name, string and anchor is pinned here.

**Files**
- Modify: `web/app.js` (new `fold`, `HEADS`, `handoffSections`, `headingBlock`, `handoffBlock`, `factsFold`,
  `handoffFold`, `windowRunsFold`; `drawTask`'s `brief` block; `chatPane`; `cardHtml`; `needText`; `unblock`;
  one delegated click handler for `[data-fold]` and one for the Window runs switch; `rawOpen` keeps its meaning)
- Modify: `web/style.css` (the mock's rules named above, after the tokens; no new token)
- `web/index.html`: nothing (every block is drawn)

**Lands on** plan 24 Task 4: `drawTask` draws the Plan row after `chain` and before `brief`; the Handoff fold below
replaces `brief` and stays after the Plan row. **Lands on** plan 5 Task 6: the picker's settings band (`.pset`) with
the Harnesses fold and the `sw` / `sr` helpers exist; the Window runs fold goes right after Harnesses and reuses them
(if plan 5 named them otherwise, use its names and keep the markup below).

## 6.1 Shared helpers (top of the Task page section of app.js; plan 25's Board reuses them)

```js
function fold(label, info, body, o = {}) {  // the mock's fold: a head button and a body; o.cls, o.tone ("r" | "y"), o.open, o.title
  return `<div class="fold${o.cls ? " " + o.cls : ""}"><button class="fh" data-fold aria-expanded="${!!o.open}"${o.title ? ` title="${esc(o.title)}"` : ""}><span class="lbl">${label}</span><span class="fi${o.tone ? " " + o.tone : ""}">${info}</span><span class="car">▾</span></button><div class="fb"${o.open ? "" : " hidden"}>${body}</div></div>`;
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
```

`headingBlock` takes `cut` as a list of strings (brief_meta.cut holds items, not indexes) and a fourth `whole` flag;
the mock's version took a `{heading: [indexes]}` map. The Goal and Next keep their lines (`\n` stays inside the `<p>`
with `white-space: pre-wrap` from `.hsec p`; add that one property to the ported rule).

## 6.2 The Handoff fold (`drawTask`)

Replace the four lines from `const text = rawOpen ? d.note : d.brief;` to the end of the `const brief = ...` statement
with:

```js
  const n = t.last_good, sn = t.steps.find((x) => x.n === n), meta = (sn && sn.brief_meta) || null;
  const nextStep = t.steps.find((x) => x.n === n + 1), two = (k) => String(k).padStart(2, "0");
  const brief = t.briefing ? `<div class="blk"><span class="loading"><span class="cells">${cellsHtml(["f live", "", "", "", "", ""])}</span>Compacting the handoff of ${two(t.briefing)}</span></div>`
    : n ? handoffFold(t, d, n, sn, meta, nextStep) : "";
```

and add, next to the helpers of 6.1:

```js
function factsFold(f, text) {  // the facts the service read when the step ended: never compacted (README 3.4)
  if (!f && !text) return "";
  const fail = f && f.tests.startsWith("FAIL");
  const info = f ? `${f.files} ${f.files === 1 ? "file" : "files"} +${f.plus} -${f.minus}${f.tests ? " · " + esc(f.tests) : ""}` : "read";
  return fold("Facts", info, `<p class="mono">${esc(text || "").replace(/\n/g, "<br>")}</p>`,
              { cls: "facts", tone: fail ? "r" : "", open: fail, title: "git diff --stat from the step's start to its end, and its last test command: code reads them, no model" });
}
function handoffFold(t, d, n, sn, meta, nextStep) {
  const two = (k) => String(k).padStart(2, "0"), brief = d.briefs[String(n)] || "", raw = d.notes[String(n)] || "";
  const sent = handoffSections(brief), wrote = handoffSections(raw), cut = (meta && meta.cut) || [];
  const words = meta ? meta.sent_w : brief.split(/\s+/).filter(Boolean).length;
  const label = nextStep ? `Handoff for ${two(nextStep.n)}` : "Last handoff";
  const info = `${words} w${meta && meta.fallback ? ' · <span class="y">as written</span>' : ""} · Next: ${esc(sent.next.split("\n")[0])}`;
  const head = meta ? `<div class="hd"><span class="m" title="${esc(meta.fallback ? "the brief pass failed: " + meta.fallback + "; code cut the note" : `by ${meta.by}, ${meta.turns} turns, $${money(meta.cost)}`)}">${meta.fallback ? "sent as written, cut by code" : `compacted from ${meta.raw_w} w`}</span>
      <span class="link m" data-tact="raw">${rawOpen ? "as sent" : `as ${two(n)} wrote it`}</span></div>` : "";
  const body = rawOpen ? headingBlock(wrote, cut, ["goal", "findings", "trouble", "questions", "next"]) : headingBlock(sent, [], undefined, true);
  return `<div class="blk">${fold(label, info, head + body + factsFold(sn && sn.facts, d.facts[String(n)]), { open: handOpen })}</div>`;
}
```

- `handOpen` is a new page flag next to `rawOpen` (`let handOpen = false;`), set from the fold's `aria-expanded` by
  the delegated handler (6.6) when the fold is the Handoff fold, reset in `openTask` like `rawOpen`.
- `data-tact="raw"` keeps today's handler (`rawOpen = !rawOpen; drawTask();`).
- `t.state === "done"` with no next step reads `Last handoff`; a task that never wrote a note draws nothing.
- No word cells anywhere (ID-5): words are figures.

## 6.3 The HANDOFF chip (`chatPane`)

In `chatPane`, the Claude branch `i.role === "claude" ? chatHtml(i.text) : ...` becomes
`i.role === "claude" ? claudeTurn(i.text) : ...` with:

```js
function claudeTurn(text) {  // a step's (or a skill's) final reply: the block folds to a chip and its Next line
  const hb = handoffBlock(text);
  if (!hb) return chatHtml(text);
  const h = handoffSections(hb[1]), w = hb[1].split(/\s+/).filter(Boolean).length;
  return (hb[0].trim() ? chatHtml(hb[0]) : "") + `<span class="hchip">HANDOFF block · <b>${w} w</b> · six headings</span><p>Next: ${esc(h.next.split("\n")[0])}</p>`;
}
```

CSS: the mock's `.turn .hchip` and `.turn .hchip b` (lines 351 to 352).

## 6.4 The HANDED OFF card (`cardHtml`, `needText`, `unblock`)

- `needText(s)`: first line `if (s.auto_handoff && s.handoff_by) return "";` (the card draws its own why).
- In `cardHtml`, before `const text = s.group === "needs" ? ...`, a branch for `s.auto_handoff && s.handoff_by`:

```js
  } else if (s.auto_handoff && s.handoff_by) {  // README 3.7: the service handed it off at red; one task = one chat
    third = `<div class="why m y">↻ ${s.window ? "" : "forked, then "}handed off by itself at ${kTokens(s.auto_handoff)}</div>
      <div class="lr" data-stay><span class="hn ready">✓ handoff ready</span>
      <button class="btn you sm" data-do="next" data-sid="${esc(s.id)}" data-where="card" title="Starts the next chat with the handoff in the task box: one task = one chat (auto hand off, D-5)">Start next chat</button>
      <span class="link m" data-open="${esc(s.handoff_by)}">handoff</span></div>`;
```

  The label (`label(s)`) of such a row is `Handed off` (`if (s.auto_handoff && s.handoff_by) return "Handed off";` as
  the first line of `label`), tone `y`.
- `unblock`: in the `name === "next"` branch, after `seedBox(...)`, `if (s.auto_handoff) await api("/api/done", { session: s.id });`
  (the card leaves Needs you; the chat stays Done).
- CSS: `.hn`, `.hn.ready` (mock 185 to 186). `kTokens` exists (`needText` uses it).

## 6.5 The Window runs switch (picker settings band)

```js
let settingBusy = false;
function windowRunsFold() {  // interface 4, ID-2: config.json stays the truth; POST /api/setting writes it
  const on = !!(cfg && cfg.handoff_auto), red = cfg ? cfg.gauge[1] : 300000;
  const ctl = `<button class="sw" role="switch" data-setting="handoff_auto" aria-checked="${on}" aria-label="auto hand off" title="${on ? "Turn off" : "Turn on"}${settingBusy ? " (waiting for the service)" : ""}"${settingBusy ? ' aria-busy="true"' : ""}>${settingBusy ? "..." : on ? "on" : "off"}</button>`;
  const row = `<div class="sr"><span class="gl ${on ? "g" : ""}">${on ? "●" : "○"}</span><span class="nm">Auto hand off</span><span class="ctl">${ctl}</span>
    <span class="sub${settingErr ? " r" : ""}">${esc(settingErr || `at ${kTokens(red)} · red zone`)}</span>
    <span class="why">Hands off a window run that ends its turn in the red zone and seeds the next chat; a VS Code chat is forked first.</span></div>`;
  return fold("Window runs", `auto hand off: ${on ? "on" : "off"}`, row);
}
```

`let settingErr = "";` beside it. The band (plan 5 Task 6) appends `windowRunsFold()` after the Harnesses fold. The
click handler (in the picker's delegated click):

```js
  const swb = e.target.closest("[data-setting]");
  if (swb && !settingBusy) {
    settingBusy = true; settingErr = ""; pickRows();
    try { cfg.handoff_auto = (await api("/api/setting", { key: "handoff_auto", value: swb.getAttribute("aria-checked") !== "true" })).value; }
    catch (err) { settingErr = err.message; }
    settingBusy = false; pickRows();
    return;
  }
```

(`pickRows` redraws the band with the rows; if plan 5 draws the band elsewhere, call that function.) Space on the
focused switch is a click (it is a button). CSS: `.pset`, `.pop .pset .fold .fh*`, `.sr*`, `.sw*` (mock 216 to 244).

## 6.6 The fold handler and CSS

- One delegated click handler on `document` for `[data-fold]`: toggle `aria-expanded`, toggle `hidden` on the next
  sibling `.fb`; when the button is the Handoff fold's head (`closest(".blk")` inside `#tscroll` and its label starts
  with `Handoff` or `Last handoff`), store `handOpen`. It must not trigger the list card's `data-open` (stop the event
  there).
- style.css, after the token block and next to the Task page rules: the mock's lines 516 to 527 and 582 to 590, the
  `.hn` lines 185 to 188, the `.turn .hchip` lines 351 to 352, the settings lines 216 to 244. Tokens only (`--raise`,
  `--line`, `--mut`, `--ink`, `--ok`, `--on-ok`, `--you`, `--bad`, `--wip`, `--off`, `--win`, `--mono`, `--ui`); a token
  the window lacks (check `--off`, `--on-ok`, `--wip`) is taken from `console-cells.html`'s token block with its dark
  value too.

## 6.7 Checks

1. `node --check web/app.js`.
2. The full suite (no Python change in this task; the count of Task 5).
3. Headless Chromium at 400 and 340 px against `py -m console --serve` on a `CC_CONSOLE_HOME` temp folder with the fake
   claude (as plan 24 Task 4 did): a task `scout, explain` with `HANDOFF-OK TROUBLE TESTS-FAIL` (the Handoff fold closed
   line, open: six headings, Troubleshooting carried, the Facts fold red and open with the FAIL line; `as 01 wrote it`
   shows the raw note), one with `LONG` (a `cut` tag on struck findings, `N kept · M cut`), a window run made red by an
   appended `Stop` event with `context_tokens` 312000 and `handoff_auto` switched on from the band (the HANDED OFF
   card, Start next chat seeds the box and the card leaves Needs you), a step chat showing the chip. No console errors,
   no horizontal scroll.
4. Commit: `Plan 23 Task 6: Handoff fold with facts, HANDOFF chip, HANDED OFF card, Window runs switch (N tests OK)`.

The "as sent" view also lists `meta.cut` struck under Findings, so a LONG cut shows `N kept · M cut` (plan 27 Task 4); `factsFold` opens red without `force`, so it can be closed.

**Drift guards**
- The window never parses a facts text: it shows it as written (`.mono`, `<br>` lines) and reads `s.facts` for the
  closed line.
- UI words: Handoff, Received (plan 25's tab), `handoff ready`; never "note" or "brief" in visible text (code names
  only). The loading line says `Compacting the handoff of NN`.
- `handoffSections` matches the six headings exactly as `tasks.HEADINGS` spells them.
