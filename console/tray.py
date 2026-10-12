"""The tray icon (BRAINSTORM D14): the service lives in this process and the pywebview window is a child
process that exists only while it is open, so a hidden console costs about 40 MB instead of about 330
(WebView2). Left click opens or closes the window, a double click opens it; the right-click menu has
Open / Close window and Quit.
The icon is the logo (console/icon.py): its signal cell is orange when something needs Fred, its route ink
while sessions work, muted when all is quiet.
Win32 through ctypes, no new package."""
import ctypes
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

from . import icon, window

ROOT = Path(__file__).resolve().parent.parent
EVERY_S = 2.0  # at most one snapshot per 2 s for the icon
CLOSE_WAIT_S = 3.0

WM_NULL, WM_CLOSE, WM_COMMAND, WM_TIMER = 0x0000, 0x0010, 0x0111, 0x0113
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
CLOSE_TIMER = 1  # a click on an open window closes it once the double-click time has passed
WM_TRAY = 0x8000 + 1  # WM_APP + 1
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x1, 0x2, 0x4
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x0002, 0x0080, 0x0100
SM_CXSMICON = 49
CMD_TOGGLE, CMD_QUIT = 1, 2


def look(counts: dict) -> tuple:
    """(kind, tooltip) from the snapshot's group counts."""
    needs, working = counts.get("needs", 0), counts.get("working", 0)
    parts = [f"{needs} need{'s' if needs == 1 else ''} you"] if needs else []
    if working:
        parts.append(f"{working} working")
    kind = "needs" if needs else "working" if working else "idle"
    return kind, f"{window.TITLE}: " + (", ".join(parts) or "quiet")


def start_window() -> subprocess.Popen:
    """The window as its own process (`py -m console --window`), without a console."""
    exe = Path(sys.executable)
    quiet = exe.with_name("pythonw.exe")
    return subprocess.Popen([str(quiet if quiet.exists() else exe), "-m", "console", "--window"], cwd=ROOT,
                            creationflags=subprocess.CREATE_NO_WINDOW)


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


def _dlls():
    """Own WinDLL objects, so the argtypes set here never reach other code in the process."""
    user32, gdi32, shell32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32"), ctypes.WinDLL("shell32")
    kernel32 = ctypes.WinDLL("kernel32")
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                       wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      wintypes.HWND, wintypes.LPVOID]
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, wintypes.LPVOID]
    user32.SetTimer.restype = ctypes.c_size_t
    user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
    user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
    user32.CreateIconIndirect.restype = wintypes.HICON
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
                                       ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, wintypes.LPVOID]
    gdi32.CreateBitmap.restype = wintypes.HBITMAP
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    return user32, gdi32, shell32, kernel32


class Tray:
    """`start` makes the window process (tests pass a fake). Win32 starts only in `run`."""

    def __init__(self, hub, start=start_window):
        self.hub = hub
        self.start = start
        self.child = None
        self.hwnd = None
        self.icons = {}
        self.shown = None
        self.doubled = False

    def alive(self) -> bool:
        return self.child is not None and self.child.poll() is None

    def open(self) -> None:
        if not self.alive():
            self.child = self.start()

    def close(self) -> None:
        """WM_CLOSE to the window, so pywebview saves its place; a window not up yet is killed."""
        if not self.alive():
            return
        hwnd = window._hwnd(window.TITLE, pid=self.child.pid)
        if hwnd:
            ctypes.windll.user32.PostMessageW(wintypes.HWND(hwnd), WM_CLOSE, 0, 0)
            try:
                self.child.wait(CLOSE_WAIT_S)
                return
            except subprocess.TimeoutExpired:
                pass
        self.child.kill()

    def toggle(self) -> None:
        self.close() if self.alive() else self.open()

    def click(self) -> None:
        """Left click: a closed window opens at once; an open one closes after the double-click time, so the
        first click of a double click cannot close it. A double click sends up, double, up: the last up is
        not a click."""
        if self.doubled:
            self.doubled = False
        elif self.alive():
            self.user32.SetTimer(self.hwnd, CLOSE_TIMER, self.user32.GetDoubleClickTime(), None)
        else:
            self.open()

    def double_click(self) -> None:
        """Double click: the window stays or comes up, never a second one."""
        self.user32.KillTimer(self.hwnd, CLOSE_TIMER)
        self.doubled = True
        self.open()

    def watch(self) -> None:
        """Repaint the icon when the state changes (also on the hub's 15 s tick), at most every EVERY_S."""
        seen = None
        while True:
            with self.hub.changed:
                self.hub.changed.wait_for(lambda: self.hub.version != seen, timeout=60)
                seen = self.hub.version
            try:
                self.show(*look(self.hub.snapshot()["counts"]))
            except Exception:  # a failed repaint keeps the old icon; the thread must live
                pass
            time.sleep(EVERY_S)

    # Win32 below: not reached by the tests

    def run(self) -> None:
        """Add the icon, open the window, pump messages until Quit."""
        self.user32, self.gdi32, self.shell32, kernel32 = _dlls()
        try:
            self.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2: a sharp icon
        except (AttributeError, OSError):
            pass
        self.size = self.user32.GetSystemMetrics(SM_CXSMICON) or 16
        self.restart = self.user32.RegisterWindowMessageW("TaskbarCreated")  # Explorer restarted: add again
        self._proc = WNDPROC(self._wndproc)
        cls = WNDCLASSW(lpfnWndProc=self._proc, hInstance=kernel32.GetModuleHandleW(None),
                        lpszClassName="ClaudeConsoleTray")
        self.user32.RegisterClassW(ctypes.byref(cls))
        self.hwnd = self.user32.CreateWindowExW(0, cls.lpszClassName, f"{window.TITLE} tray", 0, 0, 0, 0, 0,
                                                None, None, cls.hInstance, None)
        self.shown = ("idle", window.TITLE)
        self._notify(NIM_ADD)
        self.open()
        threading.Thread(target=self.watch, name="cc-tray", daemon=True).start()
        msg = wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))

    def show(self, kind: str, tip: str) -> None:
        if self.hwnd and (kind, tip) != self.shown:
            self.shown = (kind, tip)
            self._notify(NIM_MODIFY)

    def _icon(self, kind: str):
        if kind not in self.icons:
            size = self.size
            head = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=size, biHeight=-size,
                                    biPlanes=1, biBitCount=32)
            bits = ctypes.c_void_p()
            color = self.gdi32.CreateDIBSection(None, ctypes.byref(head), 0, ctypes.byref(bits), None, 0)
            pixels = icon.bgra(icon.pixels(size, kind))
            ctypes.memmove(bits, pixels, len(pixels))
            mask = self.gdi32.CreateBitmap(size, size, 1, 1, None)
            info = ICONINFO(fIcon=True, hbmMask=mask, hbmColor=color)
            self.icons[kind] = self.user32.CreateIconIndirect(ctypes.byref(info))
            self.gdi32.DeleteObject(mask)
            self.gdi32.DeleteObject(color)
        return self.icons[kind]

    def _notify(self, action: int) -> bool:
        kind, tip = self.shown
        data = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.hwnd, uID=1,
                               uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP, uCallbackMessage=WM_TRAY,
                               hIcon=self._icon(kind), szTip=tip[:127])
        return bool(self.shell32.Shell_NotifyIconW(action, ctypes.byref(data)))

    def _menu(self) -> None:
        menu = self.user32.CreatePopupMenu()
        self.user32.AppendMenuW(menu, 0, CMD_TOGGLE, "Close window" if self.alive() else "Open")
        self.user32.AppendMenuW(menu, 0, CMD_QUIT, f"Quit {window.TITLE}")
        point = wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(point))
        self.user32.SetForegroundWindow(self.hwnd)  # else the menu stays open after a click elsewhere
        cmd = self.user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_NONOTIFY | TPM_RETURNCMD,
                                         point.x, point.y, 0, self.hwnd, None)
        self.user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        self.user32.DestroyMenu(menu)
        if cmd == CMD_TOGGLE:
            self.toggle()
        elif cmd == CMD_QUIT:
            self.quit()

    def quit(self) -> None:
        self.close()
        self._notify(NIM_DELETE)
        self.user32.DestroyWindow(self.hwnd)
        self.hwnd = None
        self.user32.PostQuitMessage(0)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY and lparam == WM_LBUTTONUP:
            self.click()
            return 0
        if msg == WM_TRAY and lparam == WM_LBUTTONDBLCLK:
            self.double_click()
            return 0
        if msg == WM_TIMER and wparam == CLOSE_TIMER:
            self.user32.KillTimer(self.hwnd, CLOSE_TIMER)
            self.close()
            return 0
        if msg == WM_TRAY and lparam == WM_RBUTTONUP:
            self._menu()
            return 0
        if msg == self.restart and self.hwnd:
            self._notify(NIM_ADD)
            return 0
        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
