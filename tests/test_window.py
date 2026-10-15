import tempfile
import unittest
from pathlib import Path

from console import paths, window


class FakeWindow:
    def __init__(self):
        self.calls = []
        self.x, self.y = 120, 80
        self.width, self.height = 400, 760
        self.on_top = True

    def resize(self, w, h):
        self.width, self.height = w, h
        self.calls.append(("resize", w, h))

    def move(self, x, y):
        self.x, self.y = x, y
        self.calls.append(("move", x, y))

    def minimize(self):
        self.calls.append(("minimize",))

    def destroy(self):
        self.calls.append(("destroy",))


class WindowApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.win = FakeWindow()
        self.api = window.WindowApi(self.folder)
        self.api._attach(self.win)
        # never touch the real Claude Console window while testing
        self.topmost = []
        for name, fake in (("set_topmost", lambda on: self.topmost.append(on) or True),
                           ("round_corners", lambda: True)):
            self.addCleanup(setattr, window, name, getattr(window, name))
            setattr(window, name, fake)

    def tearDown(self):
        self.tmp.cleanup()

    def test_forms_resize_and_are_remembered(self):
        self.assertEqual(self.api.state(), {"form": "open", "on_top": True})  # first start
        self.assertEqual(self.api.form("pill"), "pill")
        self.api.form("pill", 190)    # one peek card
        self.api.form("pill", 5000)   # never taller than PEEK_MAX_H
        self.assertEqual(self.api.form("anything"), "open")
        self.assertEqual(self.win.calls, [("resize", 380, 48), ("resize", 380, 190), ("resize", 380, 360),
                                          ("resize", window.OPEN_W, window.OPEN_H)])
        self.api.form("pill")
        self.assertFalse(self.api.on_top(False))
        self.assertEqual(self.topmost, [False])  # SetWindowPos, not pywebview's cross-thread TopMost
        again = window.WindowApi(self.folder)
        self.assertEqual(again.state(), {"form": "pill", "on_top": False})
        again._attach(self.win)
        again._restore()
        self.assertEqual(self.win.calls[-1], ("resize", 380, 48))
        self.api.minimize()
        self.api.close()
        self.assertEqual(self.win.calls[-2:], [("minimize",), ("destroy",)])

    def test_open_size_is_clamped_saved_and_read_back(self):
        self.assertEqual(window.clamp_size(10, 10), (window.OPEN_MIN_W, window.OPEN_MIN_H))
        self.assertEqual(window.clamp_size(99999, 99999), (window.OPEN_MAX_W, window.OPEN_MAX_H))
        self.assertEqual(window.clamp_size("x", None), (window.OPEN_W, window.OPEN_H))  # junk: the default
        self.api.form("open")
        self.assertEqual(self.api.resize(1, 99999), [window.OPEN_MIN_W, window.OPEN_MAX_H])
        self.assertEqual(self.win.calls[-1], ("resize", window.OPEN_MIN_W, window.OPEN_MAX_H))
        self.assertNotIn("view", paths.load_window(self.folder))  # mid-drag: not written yet
        self.assertEqual(self.api.resize(360, 900, True), [360, 900])
        self.assertEqual(paths.load_window(self.folder)["view"], [360, 900])
        again = window.WindowApi(self.folder)
        again._attach(self.win)
        self.assertEqual(again.form("open"), "open")  # the next start opens at the saved size
        self.assertEqual(self.win.calls[-1], ("resize", 360, 900))
        self.api.form("pill")
        self.assertIsNone(self.api.resize(500, 500, True))  # the grip belongs to the open form
        self.assertEqual(paths.load_window(self.folder)["view"], [360, 900])
        paths.save_window(self.folder, view=["bad"])
        self.assertEqual(window.WindowApi(self.folder).open_size(), (window.OPEN_W, window.OPEN_H))

    def test_scale_is_form_pixels_per_css_pixel(self):
        self.assertEqual(window.scale_of(400, 308), 1.3)  # Windows text size 130 %: WebView2 zooms, the form does not
        self.assertEqual(window.scale_of(400, 400), 1.0)
        self.assertEqual(window.scale_of(400, 397), 1.0)  # a pixel of frame is not a scale
        self.assertEqual(window.scale_of(1000, 100), 3.0)
        for junk in ((400, 0), (0, 400), ("x", 400), (None, None), (400, -5)):
            self.assertEqual(window.scale_of(*junk), 1.0)

    def test_text_size_scales_every_size_the_page_asks_for(self):
        self.api.form("open")
        self.assertEqual(self.api.fit(692), 1.3)  # the page lays out at 692 css px in a 900 px form
        self.assertEqual(self.win.calls[-1], ("resize", round(900 * 1.3), round(700 * 1.3)))
        self.assertEqual(paths.load_window(self.folder)["scale"], 1.3)
        self.assertEqual(self.api.fit(900), 1.3)  # the page now lays out at 900 css px: nothing changes
        self.assertEqual(len(self.win.calls), 2)
        self.assertEqual(self.api.resize(360, 900, True), [360, 900])  # css px in and out
        self.assertEqual(self.win.calls[-1], ("resize", 468, 1170))
        self.assertEqual(paths.load_window(self.folder)["view"], [360, 900])
        self.assertEqual(self.api.resize(1, 1), [window.OPEN_MIN_W, window.OPEN_MIN_H])  # 340 css px, not form px
        self.assertEqual(self.win.calls[-1], ("resize", round(340 * 1.3), round(420 * 1.3)))
        self.api.form("pill", 100)
        self.assertEqual(self.win.calls[-1], ("resize", round(380 * 1.3), round(100 * 1.3)))
        again = window.WindowApi(self.folder)  # the next start opens at the right size at once
        self.assertEqual(again.open_size(), (468, 1170))
        self.assertEqual(window.WindowApi(self.folder).state()["form"], "pill")

    def test_drag_follows_the_cursor_in_form_pixels(self):
        cursor = [(500, 300)]
        self.addCleanup(setattr, window, "cursor_pos", window.cursor_pos)
        window.cursor_pos = lambda: cursor[0]
        self.api.drag_start()
        cursor[0] = (620, 380)
        self.api.drag_move()
        self.assertEqual(self.win.calls[-1], ("move", 240, 160))
        cursor[0] = (400, 250)
        self.api.drag_move()
        self.assertEqual(self.win.calls[-1], ("move", 20, 30))
        window.cursor_pos = lambda: None  # no cursor: nothing moves
        self.api.drag_move()
        self.assertEqual(len(self.win.calls), 2)

    def test_the_one_view_keeps_the_board_size_fred_chose(self):  # plan 30 (Q1 a)
        self.assertEqual((window.OPEN_W, window.OPEN_H), (900, 700))
        self.assertFalse(hasattr(self.api, "board"))  # one view: nothing widens or narrows the window
        paths.save_window(self.folder, size=[400, 760], board=[820, 640])  # window.json from before plan 30
        self.assertEqual(window.WindowApi(self.folder).open_size(), (820, 640))  # the Board's size, not the compact one
        paths.save_window(self.folder, board=None)
        self.assertEqual(window.WindowApi(self.folder).open_size(), (900, 700))  # the old compact size is never read
        self.api.form("open")
        self.assertEqual(self.api.resize(560, 700, True), [560, 700])  # under 700 px: one column (style.css)
        self.assertEqual(window.WindowApi(self.folder).open_size(), (560, 700))

    def test_hwnd_is_only_this_process_window(self):
        # the test process has no window: an Explorer tab proxy or the real window of the same name
        # (another process) must not be picked, so always-on-top never reaches them
        self.assertEqual(window._hwnd(), 0)
        self.assertEqual(window._hwnd("no such window title", pid=0), 0)

    def test_place_is_kept_only_while_on_a_screen(self):
        self.assertEqual(self.api._place(), (None, None))
        self.api._remember_place()
        self.assertEqual(paths.load_window(self.folder)["x"], 120)
        self.assertEqual(self.api._place(), (120, 80))
        paths.save_window(self.folder, x=-99999, y=-99999)
        self.assertEqual(self.api._place(), (None, None))
        self.assertNotIn("_attach", [n for n in dir(self.api) if not n.startswith("_")])


if __name__ == "__main__":
    unittest.main()
