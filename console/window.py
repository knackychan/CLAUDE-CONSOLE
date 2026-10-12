"""The borderless pywebview window (BRAINSTORM 7.5): folded, a 380 x 48 pill that grows down for one
peek card; open, 400 x 760 until the grip on the page resizes it. The page calls this as
window.pywebview.api.<method>(...); the form, the open size, the place on screen and always-on-top are
kept in window.json for the next start."""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from . import paths

PILL_W, PILL_H = 380, 48
OPEN_W, OPEN_H = 400, 760  # css px, the default open size; the grip's size replaces it
OPEN_MIN_W, OPEN_MIN_H = 340, 420  # css px: 340 is the narrowest layout in style.css; the form takes it times `scale`
OPEN_MAX_W, OPEN_MAX_H = 900, 1600
PEEK_MAX_H = 360  # the pill plus one card, never taller
TITLE = "ContextCompanion"  # the product name (temporary, Fred 2026-10-11): window title, tray tooltip and menu
BACKGROUND = "#121315"  # --win in style.css: what the window shows outside the page's own corners
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2
APP_ID = "ClaudeConsole.Window"  # AppUserModelID: the taskbar groups and pins the window apart from python


HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_KEEP = 0x0001 | 0x0002 | 0x0010 | 0x4000  # NOSIZE | NOMOVE | NOACTIVATE | ASYNCWINDOWPOS


def _hwnd(title: str = TITLE, pid: int = None) -> int:
    """This process's top-level window called `title`. FindWindowW alone can return another process's
    window of the same name (Explorer's Windows.Internal.Shell.TabProxyWindow did), and then always-on-top
    and the rounded corners went to that window."""
    pid = os.getpid() if pid is None else pid
    found = []
    try:
        user32 = ctypes.windll.user32
        buf, owner = ctypes.create_unicode_buffer(256), wintypes.DWORD()

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(hwnd, _):
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and user32.GetWindowTextW(hwnd, buf, 256) and buf.value == title:
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(each, 0)
    except (AttributeError, OSError):
        return 0
    return found[0] if found else 0


def clamp_size(w, h) -> tuple:
    """(w, h) held between the open window's minimum and maximum; anything not a number is the default."""
    try:
        w, h = int(w), int(h)
    except (TypeError, ValueError, OverflowError):
        return OPEN_W, OPEN_H
    return max(OPEN_MIN_W, min(w, OPEN_MAX_W)), max(OPEN_MIN_H, min(h, OPEN_MAX_H))


def scale_of(form_w, css_w) -> float:
    """Form pixels per CSS pixel: 1.0 normally, 1.3 when Windows' text size is 130 % (WebView2 zooms the page
    by it, the form does not: a 400 px form lays the page out at 308 CSS px). Within 0.03 of 1 is a frame, not
    a scale; junk is 1.0."""
    try:
        k = round(float(form_w) / float(css_w), 2)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return 1.0
    return 1.0 if not 0 < k < 1e6 or abs(k - 1) < 0.03 else max(0.5, min(k, 3.0))


def cursor_pos():
    """The cursor's (x, y) in the form's own pixels, or None."""
    point = wintypes.POINT()
    try:
        return (point.x, point.y) if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)) else None
    except (AttributeError, OSError):
        return None


def set_app_id(app_id: str = APP_ID) -> bool:
    """Own taskbar button with the window's icon (assets/app.ico): without an AppUserModelID Windows groups the
    window under pythonw.exe and shows Python's icon. Called before the window exists."""
    try:
        return ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id)) == 0
    except (AttributeError, OSError):
        return False


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
        self._scale = scale_of(saved.get("scale"), 1)  # form px per css px, measured by the page (`fit`)
        self._peek = PILL_H  # the pill's last css height
        self._drag = None

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
        """"pill" (with `height` > 48 css px while a peek card shows) or "open"."""
        if name == "pill":
            self._peek = max(PILL_H, min(int(height or PILL_H), PEEK_MAX_H))
            self._window.resize(round(PILL_W * self._scale), round(self._peek * self._scale))
        else:
            name = "open"
            self._window.resize(*self.open_size())
        self._form = name
        paths.save_window(self._folder, form=name)
        return name

    def _css_size(self) -> tuple:
        saved = paths.load_window(self._folder).get("size")
        return clamp_size(*saved) if isinstance(saved, list) and len(saved) == 2 else (OPEN_W, OPEN_H)

    def open_size(self) -> tuple:
        """The open window's remembered size in form px (the css size times the text-size scale); the default
        before the grip was ever used."""
        w, h = self._css_size()
        return round(w * self._scale), round(h * self._scale)

    def fit(self, css_w) -> float:
        """The page's width in css px: the form's width over it is the text-size scale. When it changed, the
        window takes its sizes again. Returns the scale."""
        k = scale_of(self._window.width, css_w)
        if k != self._scale:
            self._scale = k
            paths.save_window(self._folder, scale=k)
            self.form(self._form, self._peek)
        return self._scale

    def resize(self, w: int, h: int, keep: bool = False):
        """The page's grip: size the open window to (w, h) css px held to the limits, and with `keep` (the drag
        ended) write it to window.json. Returns [w, h] as applied, None unless the window is open."""
        if self._form != "open":
            return None
        w, h = clamp_size(w, h)
        self._window.resize(round(w * self._scale), round(h * self._scale))
        if keep:
            paths.save_window(self._folder, size=[w, h])
        return [w, h]

    def drag_start(self) -> None:
        """The page's drag region went down: the window follows the cursor from here, measured in the form's own
        pixels (pywebview's drag hands css px to a call that takes form px)."""
        at = cursor_pos()
        self._drag = (at, self._window.x, self._window.y) if at else None

    def drag_move(self) -> None:
        at = cursor_pos()
        if at and self._drag:
            (x0, y0), wx, wy = self._drag
            self._window.move(wx + at[0] - x0, wy + at[1] - y0)

    def on_top(self, on: bool) -> bool:
        self._on_top = bool(on)
        set_topmost(self._on_top)
        paths.save_window(self._folder, on_top=self._on_top)
        return self._on_top

    def minimize(self) -> None:
        self._window.minimize()

    def close(self) -> None:
        """Closes the window and ends its process; the service in the tray and window runs keep going."""
        self._window.destroy()
