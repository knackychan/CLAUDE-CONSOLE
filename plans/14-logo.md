# Plan 14: Logo and app icon

> Related plans: [../PLAN.md](../PLAN.md) (master), [12-tray.md](12-tray.md) (tray icon states)

**Goal:** one mark for the tray, the taskbar and the docs, drawn from the Console Cells motif, and a product
name that does not say Claude (phase 5 adds Codex, OpenCode and Command Code).

## The mark

A 3 x 3 board of cells on a `--win` tile (the window itself). A route of four lit cells climbs from the
bottom-left to the signal cell at the top-right; the other four cells are `--off`. The signal is `--you`
orange in the logo. Geometry in whole pixels per size (`icon.LAYOUT`, margin = gap = size / 16, cell = size / 4
at 16, 32, 64, 256), so 16 and 32 px stay sharp.

- Tray: `needs` = the logo, `working` = ink route with an off signal, `idle` = muted route, off signal.
- Taskbar: `assets/app.ico` (16 to 64 px as DIBs, 256 px as PNG), passed to `webview.start(icon=...)`; the
  window process sets the AppUserModelID `ClaudeConsole.Window` first, so it gets its own taskbar button
  instead of grouping under pythonw.exe with Python's icon.
- Sources: `design/logo/logo.svg` (vector, same 256 geometry), `design/logo/preview.html` (sizes, tray
  states on dark and light taskbars, name lockups in Doto).

## Name (Fred, 2026-10-11: temporary, may change)

**ContextCompanion**: the companion window that watches every session's context, tokens and route, whatever
the harness. Only the shown name changed: `window.TITLE` (window title, tray tooltip, `Quit` menu item) and the
page `<title>`. Unchanged on purpose, so a later rename stays one line: the package and folder names, the data
folder `~/.claude/console/`, the ping id `claude-console`, the AppUserModelID `ClaudeConsole.Window` (a change
would drop a taskbar pin), the tray window class, docstrings and docs.
Turned down: Signalbox, Switchboard, Tally; Context Watch, Token Tower, RouteWatch; Aiguilleur, Vigie, Jauge;
Context Keeper, Context Coach, Context Helper.

## Code map

```text
console/icon.py      pixels(size, look), layout(), png(), ico(); `py -m console.icon` writes assets/
console/tray.py      _icon() draws icon.pixels(size, kind) (the one-cell drawing is gone)
console/window.py    TITLE (the shown name), APP_ID, set_app_id()
console/__main__.py  open_window(): set_app_id() before the window, icon=assets/app.ico
assets/              app.ico, logo-16.png, logo-32.png, logo-256.png
tests/test_icon.py   layout, look colours, corners, BGRA, assets equal the renderer, SVG board (7 tests)
```

## TODO

- [x] Task 1: renderer, assets, tray and window wiring, tests (140 OK)
- [x] Task 2: live check on a scratch home (port 47771): the window's ICON_SMALL and ICON_BIG read back equal
      to the logo at 16 and 32 px, the taskbar showed its own button with the mark; the tray's three states
      built through `Tray._icon` at 16, 20, 24 and 32 px read back equal; no window-errors.log lines
- [x] Task 3: name ContextCompanion (temporary) in `window.TITLE` and the page title; 140 tests OK
- [ ] Task 4: Fred: restart the console and look at the tray icon on a real "needs you"
