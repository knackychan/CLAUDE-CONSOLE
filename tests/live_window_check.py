"""Live check of the window's drag and resize (plan 19 follow-up, finding "drag and resize glitch").

Not a unit test (no test_ prefix, so `unittest discover` skips it): it opens the real pywebview window on a
scratch home and service, presses the real mouse on the page's grip and drag region, and reads the form's
rectangle back with Win32. It moves the cursor for about ten seconds per width; keep the hands off.

    py tests/live_window_check.py [400 340 ...]      exit 0 when every width passes, 1 otherwise

What it checks, per open width W (the form is W x 760 physical px):
  drag     the cursor presses the drag region, moves by (+120, +80) px and lets go: the form's top-left
           corner moved by the same (+-3 px).
  grip     the cursor presses the resize handle, moves down-right by (+60, +40) px and lets go: the form grew
           by the same (+-3 px), and it never shrank on the way.
Run it with WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--force-device-scale-factor=1.3 to get Windows' 130 % text
size without changing the system setting.
Found 2026-10-12: the page's CSS px are not the form's px (devicePixelRatio 1.3 on Fred's screen: a 400 px
form lays the page out at 308 CSS px) and pywebview's drag and WindowApi.resize take the page's numbers as
form pixels, so the handle jumps back at the first move and the window trails the cursor.
"""
import ctypes
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TOL = 3  # px
user32 = ctypes.windll.user32
LEFTDOWN, LEFTUP = 0x0002, 0x0004


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def rect(hwnd) -> tuple:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def mouse_drag(x0, y0, dx, dy, steps=10, pause=0.05, probe=None):
    """Press at (x0, y0), move to (x0 + dx, y0 + dy) in `steps`, release; `probe()` runs after each move."""
    user32.SetCursorPos(int(x0), int(y0))
    time.sleep(0.2)
    user32.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.2)
    seen = []
    for i in range(1, steps + 1):
        user32.SetCursorPos(int(x0 + dx * i / steps), int(y0 + dy * i / steps))
        time.sleep(pause)
        if probe:
            seen.append(probe())
    time.sleep(0.4)
    if probe:
        seen.append(probe())
    user32.mouse_event(LEFTUP, 0, 0, 0, 0)
    time.sleep(0.5)
    return seen


def run_width(width: int, port: int, home: Path, results: list) -> None:
    import webview
    from console import icon, paths, window

    paths.save_window(home, form="open", size=[width, 760], x=50, y=50)
    api = window.WindowApi(home)
    win = webview.create_window(window.TITLE, f"http://127.0.0.1:{port}/", js_api=api, width=width, height=760,
                                x=50, y=50, min_size=(window.OPEN_MIN_W, window.PILL_H), frameless=True,
                                easy_drag=False, background_color=window.BACKGROUND, on_top=True)
    api._attach(win)

    def work():
        try:
            time.sleep(4)
            for _ in range(60):  # a cold start loads the page late: wait for its pywebviewready handler
                if win.evaluate_js("document.documentElement.classList.contains('native')"):
                    break
                time.sleep(0.5)
            api._restore()
            time.sleep(1.5)
            hwnd = window._hwnd()
            user32.SetForegroundWindow(hwnd)
            dpr = win.evaluate_js("devicePixelRatio")
            res = {"width": width, "dpr": dpr, "inner": win.evaluate_js("[innerWidth, innerHeight]"), "problems": []}

            def centre(selector):
                """Screen position (physical px) of the middle of the widest visible `selector` element."""
                box = win.evaluate_js("""((sel) => {
                    const els = [...document.querySelectorAll(sel)].filter((el) => el.offsetParent);
                    els.sort((a, b) => b.getBoundingClientRect().width - a.getBoundingClientRect().width);
                    const r = els[0].getBoundingClientRect();
                    return [r.left + r.width / 2, r.top + r.height / 2];
                })(%s)""" % json.dumps(selector))
                left, top = rect(hwnd)[:2]
                return left + box[0] * dpr, top + box[1] * dpr

            # drag region first: the grip changes the layout
            left, top, _, _ = rect(hwnd)
            px, py = centre("#open .drag-region")
            dx, dy = 120, 80
            mouse_drag(px, py, dx, dy)
            l3, t3, _, _ = rect(hwnd)
            res["drag"] = {"start": [left, top], "end": [l3, t3], "cursor_moved": [dx, dy]}
            if abs((l3 - left) - dx) > TOL or abs((t3 - top) - dy) > TOL:
                res["problems"].append(f"drag: the window moved ({l3 - left}, {t3 - top}), the cursor moved ({dx}, {dy})")

            # resize grip
            left, top, right, bottom = rect(hwnd)
            gx, gy = centre("#rsz")
            dx, dy = 60, 40
            sizes = mouse_drag(gx, gy, dx, dy, probe=lambda: (rect(hwnd)[2] - rect(hwnd)[0], rect(hwnd)[3] - rect(hwnd)[1]))
            l2, t2, r2, b2 = rect(hwnd)
            res["grip"] = {"start": [right - left, bottom - top], "path": sizes, "end": [r2 - l2, b2 - t2]}
            want_w, want_h = right - left + dx, bottom - top + dy
            if min(w for w, _ in sizes) < right - left - TOL:
                res["problems"].append(f"grip: the window shrank to {min(w for w, _ in sizes)} wide on the way")
            if abs((r2 - l2) - want_w) > TOL or abs((b2 - t2) - want_h) > TOL:
                res["problems"].append(f"grip: ended {r2 - l2} x {b2 - t2}, the cursor asked for {want_w} x {want_h}")
            results.append(res)
        except Exception as e:  # report it, never hang the window
            results.append({"width": width, "problems": [f"check failed to run: {e!r}"]})
        finally:
            user32.mouse_event(LEFTUP, 0, 0, 0, 0)
            win.destroy()

    webview.start(work, icon=str(icon.ICO))


def main(argv) -> int:
    widths = [int(a) for a in argv] or [400, 340]
    port = free_port()
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / "config.json").write_text(json.dumps({"port": port}), encoding="utf-8")
        env = dict(os.environ, CC_CONSOLE_HOME=str(home))
        svc = subprocess.Popen([sys.executable, "-m", "console", "--serve"], cwd=ROOT, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=1).read()
                    break
                except OSError:
                    time.sleep(0.2)
            os.environ["CC_CONSOLE_HOME"] = str(home)
            results = []
            for w in widths:  # one window per process: pywebview starts once
                out = subprocess.run([sys.executable, __file__, "--one", str(w), str(port), str(home)],
                                     capture_output=True, text=True, timeout=120, env=env)
                line = [x for x in out.stdout.splitlines() if x.startswith("RESULT ")]
                results.append(json.loads(line[-1][7:]) if line else {"width": w, "problems": ["no result: " + out.stderr[-300:]]})
        finally:
            svc.terminate()
    bad = 0
    for r in results:
        print(f"-- {r['width']} px (dpr {r.get('dpr')}, page {r.get('inner')} css px)")
        for key in ("grip", "drag"):
            if key in r:
                print(f"   {key}: {r[key]}")
        for p in r["problems"]:
            print("   FAIL", p)
        bad += bool(r["problems"])
        if not r["problems"]:
            print("   ok")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--one":
        w, port, home = int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
        out = []
        run_width(w, port, home, out)
        print("RESULT " + json.dumps(out[0] if out else {"width": w, "problems": ["window never ran the check"]}))
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
