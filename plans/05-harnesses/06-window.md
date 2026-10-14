# Task 6: the window: Harnesses block, rung labels, harness chip, off reasons

> Contract: [README.md](README.md) 3.7. Depends on Task 5. Browser code only: `web/app.js`, `web/index.html`,
> `web/style.css` (tokens first, Console Cells motif, `design/rework/locked/cells-drawer.html`). Anchored edits,
> never a whole-file copy. `node --check web/app.js` after every step; `tests/test_window.py` unchanged unless a
> selector it reads moves.

## Changes in `web/app.js`

- `alias(model)` / `modelText(model, effort)`: a rung with a colon splits into `(h, m)` and shows `${h} · ${m}` plus
  ` · ${effort}` as today, with no version lookup; `version()` returns `""` for it. `fableName` unchanged.
- `modelOptions(value, withAuto, kind = "")` (today's signature plus `kind`): after Claude's ladder groups, one
  `<optgroup label="codex">` per harness in `cfg.harnesses` that is `on && found` and has models, one option per
  model with value `h:m` and text `h · m`. `opencode` and `cmd` options only when `kind` is `""` (`#p-model`, the
  Run route) or a kind their model's tier covers (a `haiku` model: rule tier `haiku` or `sonnet`; an `opus`
  model: any kind; never verify or fix) (`cfg.kinds_tier`, a `{kind: tier}` map `/api/config` gains from
  `tasks.RULES`); README decision 11, D-2. A step row's select is redrawn when its kind changes (the existing
  `[data-skind]` change handler), and a pick the new kind cannot hold falls back to Auto.
- `alias(model)`: returns `""` for a string whose prefix before the first colon is a harness name, as
  `claude_cli.model_alias` does (README 3.1), so `alias(...) === "fable"` and the `includes("fable")` check on
  `#p-model` never match a harness rung.
- The settings popover (the project picker's popover, `pickerHtml`): under the Runs allowed / Runs off groups a
  `Harnesses` group: one row per name in the order of `cfg.harnesses` keys with the name, the state word (`on`,
  `off`, `not found`; glyph plus word, never colour alone), the version in `.m`, and a button `Turn on` / `Turn off`
  (`data-harness`, `data-on`), absent for `claude` (a muted `always on` instead). Click: the button is pending
  (`disabled`, text `...`) until `POST /api/harness` answers; on success `cfg.harnesses` is replaced and the popover
  redraws; on error the row shows the message in `.r` (as Allow runs failed does). A row that is `on` but
  `not found` shows one muted line: `set "exe" under harnesses.<name> in config.json` with the config path.
- Session head (`renderSession`): when `s.harness && s.harness !== "claude"`, the model chip reads
  `modelText(s.harness + ":" + s.model, s.effort)`; the brief line's context cell shows `context unknown` when the
  row has no `ctx_tokens` and `harness !== "claude"` (a Claude row with none keeps today's empty gauge).
- Task card and Task page step rows: the step's `harness` (from the task row) prefixes the model the same way.
- Levers bar: a lever whose reason is `claude only` renders as today's off lever with that reason (the existing
  off-note path); nothing new.
- Prep card step rows and the Route block: the selects come from `modelOptions`, so they list harness rungs.
- Composer hint: when `cfg.claude` is false but another harness is on and found, the hint reads
  `claude.exe not found: Prep needs it; set "exe" under harnesses.claude` (Prep and the brief are Claude's).

## `web/index.html`

- Nothing structural: the popover and the selects are drawn by `app.js`. If `pickerHtml` builds from a template
  node, the Harnesses group gets its own `<template id="t-harness">` next to it.

## `web/style.css`

- `.hs` (a harness row): the `.row` grid of the Runs allowed rows; `.hs .st` the state word in `.m`; no new colour
  token (orange stays "needs you", not for `not found`).

## Check (headless Edge over CDP, the scratch service with `exes` set to the fakes, as plan 19 did)

- 400 and 340 px: the popover with the Harnesses group (codex on and found with a version, opencode off, cmd on
  but not found with the config line), Turn on / Turn off round trip, a Prep card whose `#p-model` lists
  `codex · gpt-6.1-sol`, a run on it with the session head chip `codex · gpt-6.1-sol · medium` and
  `context unknown`, the levers bar with Verify / Hand off / Escalate / Open in terminal off and their reason,
  a task card whose scout step shows `codex · ...`. No `Uncaught` in the console log. Screenshots read.
- `node --check web/app.js` OK; `py -m unittest discover -s tests` 376 OK.

## Steps

1. `modelText` / `alias` / `modelOptions`; check a Prep card.
2. The Harnesses group and `POST /api/harness` round trip.
3. Session head, task card, Task page chips and `context unknown`.
4. Commit: `feat: Harnesses block, harness rungs and chips in the window (plan 05 Task 6)`.

## Drift guards

- No new colour for a harness; state is glyph plus word.
- A select never lists a rung of a harness that is off or not found.
- Styling only in `web/style.css`, tokens first; no inline styles in `app.js` templates.
