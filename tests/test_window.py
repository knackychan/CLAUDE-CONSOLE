import tempfile
import unittest
from pathlib import Path

from console import paths, window


class FakeWindow:
    def __init__(self):
        self.calls = []
        self.x, self.y = 120, 80
        self.on_top = True

    def resize(self, w, h):
        self.calls.append(("resize", w, h))

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

    def tearDown(self):
        self.tmp.cleanup()

    def test_forms_resize_and_are_remembered(self):
        self.assertEqual(self.api.state(), {"form": "open", "on_top": True})  # first start
        self.assertEqual(self.api.form("pill"), "pill")
        self.api.form("pill", 190)    # one peek card
        self.api.form("pill", 5000)   # never taller than PEEK_MAX_H
        self.assertEqual(self.api.form("anything"), "open")
        self.assertEqual(self.win.calls, [("resize", 380, 48), ("resize", 380, 190), ("resize", 380, 360),
                                          ("resize", 400, 640)])
        self.api.form("pill")
        self.assertFalse(self.api.on_top(False))
        self.assertFalse(self.win.on_top)
        again = window.WindowApi(self.folder)
        self.assertEqual(again.state(), {"form": "pill", "on_top": False})
        again._attach(self.win)
        again._restore()
        self.assertEqual(self.win.calls[-1], ("resize", 380, 48))
        self.api.minimize()
        self.api.close()
        self.assertEqual(self.win.calls[-2:], [("minimize",), ("destroy",)])

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
