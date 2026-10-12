import subprocess
import unittest

from console import tray, window


class FakeChild:
    def __init__(self, pid):
        self.pid, self.code, self.calls = pid, None, []

    def poll(self):
        return self.code

    def wait(self, timeout):
        self.calls.append(("wait", timeout))
        raise subprocess.TimeoutExpired("pythonw", timeout)

    def kill(self):
        self.calls.append(("kill",))
        self.code = 1


class FakeUser32:
    def __init__(self):
        self.timers = {}

    def GetDoubleClickTime(self):
        return 500

    def SetTimer(self, hwnd, timer, ms, proc):
        self.timers[timer] = ms

    def KillTimer(self, hwnd, timer):
        self.timers.pop(timer, None)


class LookTest(unittest.TestCase):
    def test_needs_wins_then_working_then_quiet(self):
        self.assertEqual(tray.look({"needs": 1, "working": 2, "done": 4}),
                         ("needs", "ContextCompanion: 1 needs you, 2 working"))
        self.assertEqual(tray.look({"needs": 3}), ("needs", "ContextCompanion: 3 need you"))
        self.assertEqual(tray.look({"needs": 0, "working": 1}), ("working", "ContextCompanion: 1 working"))
        self.assertEqual(tray.look({"done": 5, "replied": 2}), ("idle", "ContextCompanion: quiet"))


class TrayTest(unittest.TestCase):
    def setUp(self):
        self.started = []
        self.tray = tray.Tray(None, start=lambda: self.started.append(FakeChild(len(self.started) + 1))
                              or self.started[-1])
        self.addCleanup(setattr, window, "_hwnd", window._hwnd)
        window._hwnd = lambda title=window.TITLE, pid=None: 0  # never reach a real window

    def test_click_toggles_the_window_process(self):
        self.tray.toggle()
        self.assertEqual(len(self.started), 1)
        self.tray.open()                       # already open: no second window
        self.assertEqual(len(self.started), 1)
        self.tray.toggle()                     # no window up yet: the process is killed
        self.assertEqual(self.started[0].calls, [("kill",)])
        self.assertFalse(self.tray.alive())
        self.tray.toggle()
        self.assertEqual(len(self.started), 2)

    def test_closed_window_is_noticed(self):
        self.tray.open()
        self.started[0].code = 0               # Fred closed it from the page
        self.tray.toggle()
        self.assertEqual(len(self.started), 2)

    def tray_message(self, mouse):
        return self.tray._wndproc(None, tray.WM_TRAY, 0, mouse)

    def test_double_click_opens_one_window_and_keeps_it(self):
        self.tray.user32 = FakeUser32()
        for mouse in (tray.WM_LBUTTONUP, tray.WM_LBUTTONDBLCLK, tray.WM_LBUTTONUP):  # what a double click sends
            self.tray_message(mouse)
        self.assertEqual(len(self.started), 1)
        self.assertTrue(self.tray.alive())
        for mouse in (tray.WM_LBUTTONUP, tray.WM_LBUTTONDBLCLK, tray.WM_LBUTTONUP):  # again while it is open
            self.tray_message(mouse)
        self.assertEqual(len(self.started), 1)
        self.assertTrue(self.tray.alive())
        self.assertEqual(self.tray.user32.timers, {})  # the first click's close was called off

    def test_single_click_on_an_open_window_closes_it_after_the_double_click_time(self):
        self.tray.user32 = FakeUser32()
        self.tray_message(tray.WM_LBUTTONUP)
        self.tray_message(tray.WM_LBUTTONUP)
        self.assertTrue(self.tray.alive())
        self.assertEqual(self.tray.user32.timers, {tray.CLOSE_TIMER: 500})
        self.tray._wndproc(None, tray.WM_TIMER, tray.CLOSE_TIMER, 0)
        self.assertFalse(self.tray.alive())
        self.assertEqual(self.tray.user32.timers, {})

    def test_window_runs_as_its_own_quiet_process(self):
        seen = []
        self.addCleanup(setattr, subprocess, "Popen", subprocess.Popen)
        subprocess.Popen = lambda cmd, **kw: seen.append((cmd, kw))
        tray.start_window()
        cmd, kw = seen[0]
        self.assertEqual(cmd[1:], ["-m", "console", "--window"])
        self.assertEqual(kw["cwd"], tray.ROOT)
        self.assertEqual(kw["creationflags"], subprocess.CREATE_NO_WINDOW)


if __name__ == "__main__":
    unittest.main()
