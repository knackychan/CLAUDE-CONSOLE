# Task 4: The chat grammar, shared by the session page and the Board

> Contract: [README.md](README.md) 3.4 (`chatPane`, `toolsRow`, `promptRow`, `handoffSplit`, `AGENT_NAME`), 3.6
> (`--me` / `--ai` for the chat only). Design: interface doc 6.1 (chat turns: the agent on the left with the `--ai`
> edge, Fred on the right with `--me`, tool events folded, the first prompt folded, the writing mark, the source line),
> ID-8. Mock: `cells-board.html` functions `toolsRow`, `promptRow`, `chatHtml(c, s)` (the Board's), `sessionHtml()`
> (the session page), the CSS block `/* chat turns (Fred, 2026-10-13) */` (`.chat` to `.turn.prompt p`) and the
> tokens `--me`, `--ai` in all three `:root` blocks. Depends on Task 2.
>
> Lands on: plan 23 Task 6 (the `.hchip` HANDOFF chip, its `.hchip` CSS): plan 23 made `chatPane`'s claude branch call
> its `claudeTurn(i.text)` (which uses its `handoffBlock`). The rewritten `chatPane` below calls `handoffSplit`
> instead; `handoffSplit` hands a turn with no `o.step` (a hand chat that ran the session-handoff skill) to plan 23's
> `claudeTurn`, so `claudeTurn` and `handoffBlock` stay as plan 23 wrote them. Keep one copy of the `.hchip` CSS. Plan 5 Task 6 (`chat.harness`, the Codex and
> OpenCode chats through the same `runs.chat` roles): `AGENT_NAME` reads it.

**Files**
- Modify: `web/app.js` (`chatPane` rewritten with an options argument; new `toolsRow`, `promptRow`, `handoffSplit`,
  `AGENT_NAME`; `renderProc`'s and `renderOldChat`'s calls; the `[data-fold]` handler gains the tool rows)
- Modify: `web/style.css` (tokens `--me`, `--ai` in every `:root` block; the chat rules replace `.turn.you`,
  `.turn.you > .lbl`, `.turn.claude > .lbl` and the `.lbl` pill rules)

## 4.1 Tokens (`web/style.css`, the `:root` blocks)

Dark (`:root`): `--me: #c4a7ff; --ai: #7aa7ff;`. Light (the `prefers-color-scheme: light` block and
`:root[data-theme="light"]` when the stylesheet has it): `--me: #6a48c9; --ai: #2f5fc4;`. Used by `.turn.you`,
`.turn.claude`, their labels and `.turn.prompt .fh .lbl` only (README 3.6).

## 4.2 `chatPane(chat, sid, source, o = {})`

`chat` is `GET /api/chat` (`{items, source, live, start_commit, changed, harness}`); `o.prompt` (fold the first `you`
turn into a Prompt row: a task step's session), `o.step` (the step row, for the Prompt row's words and the HANDOFF
chip), `o.compact` (the Board: 12.5 px text, no files strip).

```js
const AGENT_NAME = { claude: "Claude", codex: "Codex", opencode: "OpenCode", cmd: "Command Code" };
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
    if (i.role === "note") { out.push(`<p class="src">stopped</p>`); return; }
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
```

- Roles (`runs.chat`): `you`, `claude`, `tool`, `note`, `result`; a transcript gives `you`, `claude`, `note`. A
  `note` other than `stopped` is a tool line (a harness's command summary, plan 5); `stopped` stays its own muted line.
- The source line stays at the end (the locked mock and review 3.8 over the "on top" of 6.1: README 2).
- `result` items are not turns: the last one's text joins the source line (`· ended 14:19:48 ...`).

## 4.3 `toolsRow(list, key)`

```js
function toolsRow(list, key) {  // consecutive tool events fold into one row; a failed exit comes first, so an ellipsis never hides it
  const kinds = [...new Set(list.map((t) => t.split(/[ ·]/)[0]))].join(", ");
  const bad = list.map((t) => (t.match(/exit [1-9]\d*/) || [])[0]).find(Boolean), open = toolOpen.has(key);
  return `<button class="tools" data-fold data-tkey="${esc(key)}" aria-expanded="${open}"><span>${list.length} tool ${list.length === 1 ? "event" : "events"}${bad ? ` · <span class="r">${esc(bad)}</span>` : ""} · ${esc(kinds)}</span><span class="car">▾</span></button>
    <div class="tlist"${open ? "" : " hidden"}>${list.map((t) => `<span${/exit [1-9]/.test(t) ? ' class="r"' : ""}>${esc(t)}</span>`).join("")}</div>`;
}
```

The `[data-fold]` handler: a button with `data-tkey` toggles its next sibling and records the key in `toolOpen` (add
or delete); it is not saved to window.json (a tool row's key holds a session id). The `setHtml` repaint every second
keeps the row open because `toolOpen` is read on each draw.

## 4.4 `promptRow(text, o, key)`

```js
function promptRow(text, o, key) {  // a task step's first turn is the prompt the service built: folded, not labelled You
  const s = o.step || {}, w = String(text || "").split(/\s+/).filter(Boolean).length, open = foldOpen("prompt", false);
  const from = s.n > 1 ? `goal and the handoff of ${two(s.n - 1)}` : "goal and the context pack";
  return `<div class="turn you prompt"><button class="fh" data-fold data-fkey="prompt" aria-expanded="${open}"><span class="lbl">Prompt</span><span class="fi">${from} · ${w} w</span><span class="car">▾</span></button><p${open ? "" : " hidden"}>${esc(text)}</p></div>`;
}
```

`o.prompt` is set for a session that runs a task step (`taskTag(s)` finds a task, or `oldStep(id)` does) and on the
Board; a chat Fred started by hand keeps its first `You` turn.

## 4.5 `handoffSplit(text, o, last)`

```js
function handoffSplit(text, o, last) {  // a turn that ends with the HANDOFF block: the words before it, the chip, its Next line
  const t = String(text || ""), at = t.search(/(^|\n)HANDOFF\s*\n/);
  if (at < 0) return chatHtml(t);
  if (!o.step) return claudeTurn(t);  // plan 23 Task 6: a hand chat's skill block keeps plan 23's chip
  const block = t.slice(at), next = (block.match(/## Next\s*\n+([^\n]*)/) || [, ""])[1];
  const w = block.split(/\s+/).filter(Boolean).length;
  return `${chatHtml(t.slice(0, at))}<span class="hchip">HANDOFF block · <b>${w} w</b> · six headings ${o.board ? "in the Handoff tab" : "on the Task page"}</span>${next ? `<p>Next: ${esc(next)}</p>` : ""}`;
}
```

On the session page (no Board tab) the chip reads `HANDOFF block · N w · six headings on the Task page` (pass
`o.board` from the Board to choose the words). Without `o.step` (a hand chat) plan 23's `claudeTurn` draws it: the
text whole, or plan 23's chip when it ends with a HANDOFF block.

## 4.6 Callers

- `renderProc` (the session page's Chat tab): `chatPane(chat, s.id, s.source, { prompt: !!taskTag(s), step: stepOf(s.id) })`,
  `stepOf(id)` the task step whose `session` or attempts hold the id (from `snap.tasks`), else `undefined`.
- `renderOldChat(id)`: `chatPane(chat, id, "chat", { prompt: true, step: old[1] })`.
- The Board (Task 5): `chatPane(chat, s.session, "chat", { prompt: true, step: s, compact: true, board: true })`.

## 4.7 `web/style.css`

Replace the current chat rules (`.chat` to `.chat .src`, keeping the `.turn .tbl` and table rules) with the mock's
block: `.chat`, `.turn` (max-width 82%), `.turn p`, `.turn > .lbl`, `.turn.claude` and its label, `.turn.you` and its
label, `.turn > .lbl .cells`, `.turn .hchip`, `.turn .hchip b` (if plan 23 placed `.hchip`, keep one copy), `.tools`,
`.tools:hover`, `.tools span`, `.tools .car`, `.tlist`, `.tlist .r`, `.chat .src` (centred), `.turn.prompt` and its
`.fh`, `.lbl`, `p`. Add `.chat.compact .turn p { font-size: 12.5px; }` and keep `user-select: text; cursor: text` on
`.chat`. Delete `.turn.you > .lbl, .turn.claude > .lbl { ... padding: 1px 7px ... }`, `.turn.you > .lbl { background:
var(--ink) ... }`, `.turn.claude > .lbl { background: var(--off) ... }` and `.turn.you { padding-left: 9px;
border-left ... }`. `.turn.note p, .turn.result p` goes (those roles are no longer turns).

## 4.8 Checks

1. 400 x 760, the session page of a fake window run with tools: `You` on the right in the `--me` tint, `Claude` on the
   left in `--ai`, consecutive tool events one row `N tool events · Bash, Read`, a failing one shows `exit 1` in red
   first; open the row, wait 2 s (two repaints): it stays open.
2. A task step's session: the first turn is the folded `Prompt · goal and the context pack · N w`; open it, reload:
   it stays open (window.json `folds.prompt`).
3. The step's last turn with a HANDOFF block: the words before it, the chip with its words, `Next: ...`; the six
   headings are not in the chat.
4. A running window run: `writing` with the live cell on the last Claude turn only.
5. 340 x 760: no horizontal overflow (`.turn` max-width, `.tools span` ellipsis); light theme (`data-theme="light"`):
   the light tokens.

## 4.9 Steps, in order

1. `style.css` (4.1, 4.7).
2. `app.js`: `AGENT_NAME`, `toolsRow`, `promptRow`, `handoffSplit`, `chatPane`, `stepOf`; the callers (4.6); the
   `[data-fold]` handler's `data-tkey` branch.
3. `node --check web/app.js`; the full suite; the checks of 4.8.
4. Commit `plan 25 task 4: the chat grammar on the session page and the Board (N tests OK)`.

Expected count: unchanged.

## 4.10 Drift guards

- One `chatPane`; the Board passes options, never a copy (README 3.7).
- `--me` and `--ai` on chat bubbles and labels only.
- No role is invented: the grammar reads `runs.chat`'s roles as they are; any other role (`tool`, or one a later plan
  adds) is a tool line.
