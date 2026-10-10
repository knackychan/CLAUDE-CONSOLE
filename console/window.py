"""The borderless pywebview window (BRAINSTORM 7.5): folded, a 380 x 48 pill that grows down for one
peek card; open, 400 x 640. The page calls this as window.pywebview.api.<method>(...); the form,
the place on screen and always-on-top are kept in window.json for the next start."""
import ctypes
from ctypes import wintypes
from pathlib import Path

from . import paths

PILL_W, PILL_H = 380, 48
OPEN_W, OPEN_H = 400, 640
PEEK_MAX_H = 360  # the pill plus one card, never taller
TITLE = "Claude Console"
BACKGROUND = "#121315"  # --win in style.css: what the window shows outside the page's own corners
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2


HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_KEEP = 0x0001 | 0x0002 | 0x0010 | 0x4000  # NOSIZE | NOMOVE | NOACTIVATE | ASYNCWINDOWPOS


def _hwnd(title: str = TITLE) -> int:
    try:
        return ctypes.windll.user32.FindWindowW(None, title) or 0
    except (AttributeError, OSError):
        return 0


def set_topmost(on: bool, title: str = TITLE) -> bool:
    """Always on top, without blocking: pywebview sets Form.TopMost from the page's call thread, which
    froze the window; SetWindowPos with ASYNCWINDOWPOS hands the change to the window's own thread."""
    hwnd = _hwnd(title)
    if not hwnd:
        return False
    after = HWND_TOPMOST if on else HWND_NOTOPMOST
    return bool(ctypes.windll.user32.SetWindowPos(wintypes.HWND(hwnd), wintypes.HWND(after), 0, 0, 0, 0, SWP_KEEP))


def round_corners(title: str = TITLE) -> bool:
    """Windows 11 rounds a borderless window (8 px, antialiased) only when asked; a WinForms form cannot
    be transparent, so without this its square corners show around the page's rounded ones."""
    try:
        hwnd = _hwnd(title)
        pref = ctypes.c_int(DWMWCP_ROUND)
        return bool(hwnd) and ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), ctypes.sizeof(pref)) == 0
    except (AttributeError, OSError):
        return False  # before Windows 11: square corners


def on_screen(x: int, y: int) -> bool:
    """True when a monitor shows that point (a saved place on an unplugged screen is dropped)."""
    try:
        return bool(ctypes.windll.user32.MonitorFromPoint(wintypes.POINT(x + 20, y + 20), 0))
    except (AttributeError, OSError, TypeError, ValueError):
        return True


class WindowApi:
    """Names starting with _ stay hidden from the page."""

    def __init__(self, folder: Path):
        self._folder = Path(folder)
        self._window = None
        saved = paths.load_window(self._folder)
        self._form = saved.get("form") if saved.get("form") in ("pill", "open") else "open"
        self._on_top = saved.get("on_top") is not False

    def _attach(self, window) -> None:
        self._window = window

    def _place(self):
        """The saved (x, y) when it is still on a screen, else (None, None): centred."""
        saved = paths.load_window(self._folder)
        x, y = saved.get("x"), saved.get("y")
        if isinstance(x, int) and isinstance(y, int) and on_screen(x, y):
            return x, y
        return None, None

    def _restore(self) -> None:
        """After the window shows: pywebview sizes a frameless window short of the asked size."""
        round_corners()
        self.form(self._form)

    def _remember_place(self) -> None:
        paths.save_window(self._folder, x=self._window.x, y=self._window.y)

    def state(self) -> dict:
        return {"form": self._form, "on_top": self._on_top}

    def form(self, name: str, height: int = 0) -> str:
        """"pill" (with `height` > 48 while a peek card shows) or "open"."""
        if name == "pill":
            self._window.resize(PILL_W, max(PILL_H, min(int(height or PILL_H), PEEK_MAX_H)))
        else:
            name = "open"
            self._window.resize(OPEN_W, OPEN_H)
        self._form = name
        paths.save_window(self._folder, form=name)
        return name

    def on_top(self, on: bool) -> bool:
        self._on_top = bool(on)
        set_topmost(self._on_top)
        paths.save_window(self._folder, on_top=self._on_top)
        return self._on_top

    def minimize(self) -> None:
        self._window.minimize()

    def close(self) -> None:
        """Closes the window and the service inside it; window runs keep going (they are detached)."""
        self._window.destroy()
