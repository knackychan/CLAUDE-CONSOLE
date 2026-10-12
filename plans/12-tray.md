# Plan 12: Tray icon, window on demand

> Related plans: [../PLAN.md](../PLAN.md) (master), [06-rework.md](06-rework.md) (borderless window, form memory), [07-cells-drawer.md](07-cells-drawer.md) (the page)

**Goal:** a hidden console costs about 40 MB, not about 330. The service lives in a tray process; the pywebview
window (and its WebView2) runs as its own process only while it is open.

## Fixed decisions (Fred, 2026-10-11, D14)

1. **Option A2 of the comparison** (below): keep pywebview and the Cells Drawer window; add a tray icon written
   with ctypes (no new package); the window is a child process started from the icon and ended when it closes.
2. **Not taken:** pywebview hidden to the tray (WebView2 keeps about 208 MB while hidden); a tray icon opening the
   page in Edge `--app` (drops the pill, always-on-top and the rounded borderless window, 210 MB when open, no gain);
   a Tk or Win32 popup (cannot draw the locked design; a second UI to keep).
3. **No pre-warmed window** (Fred, 2026-10-11): a click shows the window in about 0.7 s and its content in about
   0.95 s (measured warm: .NET + WinForms load 0.33 s, form + WebView2 0.27 s, page 0.22 s); that is fast enough,
   and a hidden window kept ready would cost about 290 MB idle.

## Measured (2026-10-11, Windows 11 26200, 60 s each, private MB)

| What ran | Private MB | CPU per 60 s |
|---|---|---|
| Old window (pythonw + WebView2, visible, live data) | ~329 | 0.75 s |
| Service only (`--serve`, copy of the real data) | 38 | 0.19 s |
| pywebview window hidden, client only | 208 | 0.22 s |
| Edge `--app`, own profile | 210 | 1.09 s |
| **Tray process with the window closed (this plan)** | **39** | **0.14 s** |

Opening the window adds the old cost (6 WebView2 processes); closing it frees them (counted: 12, 18, 12).

## Behaviour

- `py -m console` (and `run.bat`): service + tray icon, and the window opens at start as before.
- Left click on the icon: open the window, or close it when open (the close waits the double-click time). Double click:
  open it, never a second one (2026-10-11: the second click of a double click used to kill the window it had started). Right click: `Open` / `Close window`, `Quit Claude Console`.
- The close button on the page ends the window process only; the service and runs keep going. Quit is in the tray menu.
- The icon is the logo (plan 14, `console/icon.py`): its signal cell is orange (`--you`) when something needs Fred, its
  route ink (`--ink`) while sessions work, muted (`--mut`) when quiet, on a `--win` tile; the tooltip says `Claude Console: 2 need you, 1 working` or `quiet`.
  Repainted on state change, at most every 2 s.
- Closing from the tray sends WM_CLOSE, so the window saves its place in window.json; a window not up yet is killed.
- Explorer restarts (`TaskbarCreated`) add the icon again.
- `py -m console --window`: the window only, for a running service (what the tray starts); exit 1 without one.

## Code map

```text
console/tray.py      look(), start_window(), Tray: open / close / toggle / watch, Win32 run loop
console/__main__.py  --window; tray by default; open_window() split out of main()
console/window.py    close() docstring: the window only
tests/test_tray.py   look, toggle with a fake process, the --window command (4 tests; the icon's are in test_icon.py)
```

`Tray.close` finds the window with `window._hwnd(title, pid=...)` (the pid filter in the working tree, not yet committed).

## TODO

- [x] Task 1: tray, `--window`, tests (130 OK)
- [x] Task 2: live check on a scratch home (port 47771): window started as a child, tray click closed it with its place
      saved, reopened, Quit from the menu ended the tray, the window and the port; `--window` without a service exits 1
- [ ] Task 3: Fred: restart the console (Quit the old window, then `run.bat`), pin the icon on the taskbar
      (Windows 11 puts new icons in the overflow), check the colours on a real "needs you"

## Not done / open

- A second `py -m console` while the tray runs opens a window the tray does not track (a tray click opens another).
- No toast on "needs you": the icon colour and tooltip only.
- Started from a terminal with `py -m console`, Ctrl+C does not stop the message loop: Quit from the menu.
- No .exe and no shortcut script (Fred, 2026-10-11): `run.bat` stays the launcher. An .exe would add a build step
  and save no RAM; a Start-menu or login shortcut is Fred's to make by hand if he wants one.
