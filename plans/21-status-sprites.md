# Plan 21: status sprites

> Context: [../BRAINSTORM.md](../BRAINSTORM.md) section 7.5, [../PLAN.md](../PLAN.md), mockup `design/rework/explored/status-sprites.html`
> (moves to `design/rework/locked/` when Fred locks it). Display only: snapshot fields, levers and service logic do not change.

## Decision

Fred chose option B (2026-10-12): the pixel sprites sit beside the cell motif. Each task and session state gets a 5 x 5 sprite of
3 px `.cells i` cells (the size of `.chipcell .cells`) in front of its state word, replacing the text glyphs. The cell rows, gauges and
the context row stay as the locked `cells-drawer.html` has them. BRAINSTORM 7.5 dial MOTION goes from 1 to 2.

Anti-slop: only a state carries motion. Running and waiting animate; paused, stopped, stuck, done and planned are still.

## Sprites

| State | Tone | Frames | Used for |
|---|---|---|---|
| running | ink shades | 16 x 100 ms, a 3 x 3 slide puzzle of 5 px tiles (the same 19 px square) | task `running` / `planned`-to-run, session `running`, agent working |
| waiting | orange | 2 x 250 ms, a `?` whose dot blinks twice a second | task `waiting`, session `stop` (asks) |
| paused | ink | 1 (two bars) | task owned by Fred while `running` / `waiting` (the Paused line) |
| stopped | muted | 1 (solid 3 x 3) | task `stopped` |
| stuck | red | 1 (an X) | task `stuck`, session `blocked` |
| done | green | 1 (a check) | task `done`, session `done` |
| planned | dim | 1 (one centre cell) | task `planned` |

Reduced motion: frame 0 shows and nothing moves. All motion rules sit inside `@media (prefers-reduced-motion: no-preference)`; no JS
check is needed because the classes only matter there.

## Motion (state changes only)

1. State flip: when a task or session changes state, its new sprite fades in once, 240 ms, 3 steps.
2. Entering Needs you: the card flashes an orange outline twice in 600 ms.
3. Chain advance: when a step becomes done on the Task page its six cells fill left to right, 300 ms.
4. A new Prep job row grows in, 160 ms ease-out.
5. `spin()` (the Prep and composer loading cells) is unchanged.

## Running mark (decided by Fred, 2026-10-12)

The 3-cell worm was rejected (it does not suit the cell style). The running mark is variant A, a slide puzzle: eight tiles in three
shades (l2, l3, l4) and one hole on a 3 x 3 board of 5 px tiles; the hole walks 8, 7, 4, 3, 0, 1, 2, 5, 8 and the walk is played back, 16 frames
of 100 ms, seamless loop. The turning cube face (variant B) was dropped. The mockup is locked: `design/rework/locked/status-sprites.html`.

## Steps

One file per commit; run `node --check web/app.js` after each app.js step and the unit tests at the end.

### 1. CSS, `web/style.css`

After the `@keyframes blink` line add (this is the code as shipped):

```css
.cells i.q { background: var(--mut); }

/* status sprites (BRAINSTORM 7.5, plan 21): 5 x 5 cells of 3 px, one .fr layer per frame in one grid area; frame 0 is the still state */
.spr { display: inline-grid; margin-right: 6px; flex: none; }
.spr .cells.fr { grid-area: 1 / 1; grid-template-columns: repeat(5, 3px); }  /* .cells.fr: stronger than .log .cells and .arow .cells */
.spr .fr + .fr { opacity: 0; }
.spr.g3 .cells.fr { grid-template-columns: repeat(3, 5px); gap: 2px; }  /* the running puzzle: 3 x 3 tiles of 5 px, a 19 px square like the 5 x 5 sprites */
.st:has(.spr) { display: inline-flex; align-items: center; }
.st:has(.spr) .lc, .st:has(.spr) .st { margin-left: .6em; }  /* flex drops the space before a nested span */
@media (prefers-reduced-motion: no-preference) {
  .spr.anim .fr { animation-timing-function: steps(1); animation-iteration-count: infinite; animation-delay: calc(var(--k) * var(--s)); }
  .spr.n16 .fr { animation-name: spr16; animation-duration: calc(var(--s) * 16); }
  .spr.n2 .fr { animation-name: spr2; animation-duration: calc(var(--s) * 2); }
  .spr.flip { animation: sprin 240ms steps(3) 1; }
  .card.enter { animation: need 600ms steps(1) 1; }
  .card.grow { overflow: hidden; animation: grow 160ms ease-out 1; }
  .chain .row.adv .cells i { animation: cellon 50ms steps(1) backwards; }
  .chain .row.adv .cells i:nth-child(2) { animation-delay: 50ms; }
  .chain .row.adv .cells i:nth-child(3) { animation-delay: 100ms; }
  .chain .row.adv .cells i:nth-child(4) { animation-delay: 150ms; }
  .chain .row.adv .cells i:nth-child(5) { animation-delay: 200ms; }
  .chain .row.adv .cells i:nth-child(6) { animation-delay: 250ms; }
}
@keyframes spr16 { 0% { opacity: 1; } 6.25%, 100% { opacity: 0; } }
@keyframes spr2 { 0% { opacity: 1; } 50%, 100% { opacity: 0; } }
@keyframes sprin { from { opacity: 0; } to { opacity: 1; } }
@keyframes need { 0%, 66% { outline: 2px solid var(--you); outline-offset: -2px; } 33%, 100% { outline: 2px solid transparent; outline-offset: -2px; } }
@keyframes cellon { from { background: var(--off); } }
@keyframes grow { from { max-height: 0; opacity: 0; } to { max-height: 8em; opacity: 1; } }
```

Also: `.log > div` and `.arow` first column 8px becomes 19px (the sprite width), `.log .spr, .arow .spr` have no right margin.
`.spr .cells.fr` is deliberately stronger than `.log .cells` and `.arow .cells`, which set a 6px column.

### 2. Sprite table and helpers, `web/app.js`

Replace `TASK_WORD` (lines 19-20) with the word table without glyphs and add the table below it (same code as the mockup):

```js
const TASK_WORD = { planned: ["Task", "n"], running: ["Task", "n"], waiting: ["Waiting", "y"],
  stuck: ["Stuck", "r"], done: ["Done", "g"], stopped: ["Stopped", "q"] };  // [word, tone]
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
const taskSprite = (t) => (t.owner === "fred" && (t.state === "running" || t.state === "waiting") ? "paused" : t.state);
```

Every `TASK_WORD` use (`const [glyph, word, tn] = ...`, lines 455 and 1379) becomes `const [word, tn] = ...`. The state mark is
`sprite(taskSprite(t), fresh("f", "t" + t.id, t.state, 240)) + word` in place of `${glyph} ${word}`.

### 3. Call sites, `web/app.js` (one commit each)

1. `taskCard` (455-468): the `.st` mark as above; add `${fresh("n", "t" + t.id, tn === "y" || tn === "r" ? "needs" : "", 600) && (tn === "y" || tn === "r") ? " enter" : ""}` to the card class.
2. Task head (1379-1386): same mark; the `paused` text stays.
3. `cardHtml` (470-500) and `quietHtml`: the mark is `SESSION_SPRITE[s.state] ? sprite(SESSION_SPRITE[s.state], fresh("f", "s" + s.id, s.state, 240)) : s.symbol + " "` followed by the label; `cardHtml` adds `enter` the same way as the task card, keyed on `s.group === "needs"`.
4. `LIVE` (1138) becomes `const LIVE = sprite("running");`; the steps-tab marks (1195) become `sprite("waiting")` for `stop`, `sprite("stuck")` for `blocked`; the Agents tab (1200) uses `sprite("done")` for `done`. Waiting agents keep the `○` glyph.
5. `chainRow` (1359-1366): the six cells stay; add ` adv` to the row class when `fresh("c", "t" + t.id + "." + s.n, s.state, 300) && s.state === "done"`.
6. `prepJobHtml` (590-): a module `const prepSeen = new Set()`; each card gets ` grow` in its class when `!prepSeen.has(j.id)`, then `prepSeen.add(j.id)`.

### 4. Check

- `py -m unittest discover -s tests` passes with the same count; `node --check web/app.js` passes.
- Headless Edge at 400 and 340 px against `design/rework/locked/`: screenshots read, no `Uncaught` in the log.
- With `--force-prefers-reduced-motion`, `getAnimations()` on `.spr`, `.card` and `.row` is empty.

### 5. Docs

BRAINSTORM 7.5: MOTION 1 becomes MOTION 2 with the sentence "motion only on a running or waiting mark and on a state change". PLAN.md row 21.

## Done when

The checks in step 4 pass, Fred has seen the marks live and locked the mockup.
