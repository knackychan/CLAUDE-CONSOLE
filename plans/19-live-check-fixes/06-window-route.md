# Task 6: Model versions, Confirm to use Fable, the project in sight, a restored draft marked

> Contract: [README.md](README.md) 3.4 (`versions`, the `/api/run` guard), 3.5. Findings A7 (D3), B3 (D7 a), B4,
> B5. Depends on Task 4.

**Files**
- Modify: `web/app.js`, `web/style.css`. No Python. Checks as in Task 5 (5.6).

## 6.1 Every model text shows its version (B3)

Evidence: today only rungs show one (`opus 4.8`): `version()` reads the number from the name, and an alias
(`opus`, `sonnet`, `haiku`, `fable`) has none. `ladder.fable` is `["fable"]` only.

```js
function modelText(model, effort) {  // an alias shows the newest version the service has seen (snap.versions)
  const fam = alias(model), v = version(model) || (fam === model && snap && snap.versions ? snap.versions[fam] || "" : "");
  return [v ? fam + " " + v : fam, effort].filter(Boolean).join(" ");
}
```

That covers the card's route select, the step rows (`modelOptions`), the task card, the Task page, the session
header and the strip's Ready row (change its `${esc(c.route.model)} ${esc(c.route.effort)}` to
`${esc(modelText(c.route.model, c.route.effort))}`). `routeText(s)` keeps `alias(s.model)` (a list row stays short).

## 6.2 Confirm to use Fable (A7, D3 a)

- Wording: `fableName()` returns `"Fable " + snap.versions.fable` or `"Fable"`. The Task page's confirm button
  reads `Confirm to use ${fableName()}` (not for a hold: Task 5 gives that one `Run anyway`). The task card's why
  line shows `confirm Fable` as `${fableName()} may bill usage credits: confirm on the Task page`.
- The card route (`#p-model`): the Fable note `#p-fable` shows when `#p-model` or any step row is on a Fable model
  (`stepsChanged()` reads `#p-model` too; the `change` listener calls it for `#p-model`).
- Plain Run with a Fable model is two clicks, like the Task page's Stop: the first click arms the button with
  `Confirm to use ${fableName()}` for 3 s; the second calls `doRun(..., fableOk = true)`.
  `doRun(projectDir, prompt, model, effort, prepId, from = "", fableOk = false)` adds `fable_ok: fableOk` to the
  body. A 409 from the service shows in `#p-msg` as any run error.
- With D3 (b) instead: `modelOptions(value, withAuto, noFable)` leaves `fable` out for `#p-model`, nothing else.

## 6.3 The project in sight (B4)

Evidence: the picker was on CLAUDE CONSOLE and a task ran there; the Prep card names the project only in the
crumb (`Prep / CLAUDE CONSOLE`).

- `showPrep()`: the first block of `#pscroll` is `<div class="blk"><span class="lbl">Project</span><div
  class="proj m"><b>NAME</b> <span class="mut">DIR</span></div></div>`; `#pbar` starts with `<div class="m runs-in">Runs
  in <b>NAME</b></div>` above the buttons.
- The task box placeholder: `New task in NAME` (when runnable).
- A project change: `pick(dir)` with a different `project` sets `movedAt = Date.now()`; `renderCompose` gives the
  target chip `.tgt` the class `moved` while `Date.now() - movedAt < 4000` (one `setTimeout(renderCompose, 4000)`
  ends it). `style.css`: `.tgt.moved { border-color: var(--ink); background: var(--raise); }` (tokens only; no
  orange: orange is "needs you").

## 6.4 A restored draft is marked (B5)

Evidence: "test" from an earlier draft was glued to the next request ("testfind").

- At load (app.js near line 1717): `draftKept = !!draft.trim();` (a new `let draftKept = false;` with the other
  `let`s at the top).
- `renderCompose()`: when `draftKept` and not busy, the say line ends with `<span class="m mut">Draft kept from last
  time</span><button class="btn sm" data-go="cleardraft">Clear</button>`.
- `go("cleardraft")`: `draft = ""; $("c-prompt").value = ""; draftKept = false; saveDraft(); renderCompose();
  $("c-prompt").focus();`
- The input handler (line 1626) sets `draftKept = false`; the first `focus` of `#c-prompt` while `draftKept`
  selects the text, so typing replaces it (`{ once: true }` listener added at load when `draftKept`).

## 6.5 Screens (as Task 5, 5.6)

At 400 and 340 px, each PNG read: the Prep card with its project block, the `Runs in` line and the route select
showing `opus 5.5` (seed one session event with `claude-opus-5-5` in the scratch event log, or a fake run whose
model is a full id); the step row select listing versions; `#p-model` on fable: the note and the armed button
text; the compose row with a kept draft and its Clear; the chip after a project change.

## 6.6 Order (one commit per step)

1. 6.1; screens; commit `feat: every model text shows its version (plan 19 Task 6)`.
2. 6.2; screens; commit.
3. 6.3; screens; commit.
4. 6.4; reload with a draft; commit.
5. `node --check web/app.js`, the suite; PLAN.md History line; commit.
