"""Plan 54: whole-file Console saves while Windows metadata readers keep the destination open."""
from contextlib import ExitStack, contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest import mock

from console import kinds, paths, tasks, usage
from tests.test_tasks import make


@contextmanager
def metadata_reader(path, access=0x80, share=3):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), access, share, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield handle
    finally:
        kernel.CloseHandle(handle)


class AtomicTest(unittest.TestCase):
    def test_embedded_null_is_rejected_without_truncating_another_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            victim = Path(temporary) / "victim"
            victim.write_text("old", encoding="utf-8")
            with self.assertRaises(ValueError):
                paths.write_text_atomic(victim.with_name("victim\x00.json"), "new")
            self.assertEqual(victim.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(victim.parent.iterdir()), [victim])

    @unittest.skipUnless(os.name == "nt", "Windows file sharing")
    def test_old_reader_keeps_old_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "café-任務-\U00010437.json"
            paths.write_text_atomic(path, "old\n")
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            with metadata_reader(path, access=0x80000000, share=7) as reader:
                paths.write_text_atomic(path, "new 任務\n")
                data, size = ctypes.create_string_buffer(64), wintypes.DWORD()
                self.assertTrue(kernel.ReadFile(reader, data, len(data), ctypes.byref(size), None))
                self.assertEqual(data.raw[:size.value].decode("utf-8").replace("\r\n", "\n"), "old\n")
                self.assertEqual(path.read_text(encoding="utf-8"), "new 任務\n")
            self.assertEqual(list(Path(temporary).iterdir()), [path])

    def test_encoding_failure_preserves_destination_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            paths.write_text_atomic(path, "old")
            with self.assertRaises(UnicodeEncodeError):
                paths.write_text_atomic(path, "\ud800")
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_concurrent_writers_publish_whole_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            errors = []
            payloads = [json.dumps({"writer": n, "text": "任務" * 400}) for n in range(6)]

            def write(payload):
                try:
                    for _ in range(20):
                        paths.write_text_atomic(path, payload)
                except Exception as exc:
                    errors.append(repr(exc))

            threads = [threading.Thread(target=write, args=(payload,)) for payload in payloads]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertIn(path.read_text(encoding="utf-8"), payloads)
            self.assertEqual(list(path.parent.iterdir()), [path])


@unittest.skipUnless(os.name == "nt", "Windows file sharing")
class WindowsAtomicTest(unittest.TestCase):
    def test_temporary_file_remains_renameable_with_a_metadata_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            paths.write_text_atomic(path, "old")
            replace = os.replace

            with ExitStack() as readers:
                readers.enter_context(metadata_reader(path))

                def publish(source, destination):
                    readers.enter_context(metadata_reader(source))
                    self.assertEqual(path.read_text(encoding="utf-8"), "old")
                    replace(source, destination)

                with mock.patch.object(paths.os, "replace", side_effect=publish):
                    paths.write_text_atomic(path, "new")
                self.assertEqual(path.read_text(encoding="utf-8"), "new")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_task_save_while_metadata_reader_is_open(self):
        with tempfile.TemporaryDirectory() as home:
            home = Path(home) / "任務-\U00010437"
            task = make(("scout", "explain"))
            tasks.save(home, task)
            path = tasks.folder(home, task["id"]) / "task.json"
            with metadata_reader(path):
                task["why"] = "updated while indexed"
                tasks.save(home, task)
                self.assertEqual(tasks.load(home, task["id"]), task)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_nonsharing_content_reader_still_refuses_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            paths.write_text_atomic(path, "old")
            with path.open("rb") as reader:
                with self.assertRaises(PermissionError):
                    paths.write_text_atomic(path, "new")
                self.assertEqual(reader.read(), b"old")
                self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_other_console_writers_with_an_open_metadata_reader(self):
        with tempfile.TemporaryDirectory() as home:
            root, task, message = Path(home), make(("scout",)), {"id": "a" * 32}
            writers = (
                (root / "config.json", lambda: paths.set_config(root, {"task_max_steps": 8})),
                (root / "window.json", lambda: paths.save_window(root, board=True)),
                (root / usage.DAYS_FILE, lambda: usage._write(root, {"days": {}})),
                (root / "kinds" / "scout.md", lambda: kinds.save(root, "scout", kinds.seed_text("scout"))),
                (tasks.folder(root, task["id"]) / "messages" / (message["id"] + ".json"),
                 lambda: tasks.message_files(root, task, message, [])),
            )
            for path, write in writers:
                with self.subTest(path=path.name):
                    write()
                    with metadata_reader(path):
                        write()
                        self.assertTrue(path.read_text(encoding="utf-8"))
                    self.assertFalse(list(path.parent.glob("*.tmp")))

    def test_readonly_destination_still_refuses_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            paths.write_text_atomic(path, "old")
            path.chmod(stat.S_IREAD)
            try:
                with self.assertRaises(PermissionError):
                    paths.write_text_atomic(path, "new")
                self.assertEqual(path.read_text(encoding="utf-8"), "old")
                self.assertEqual(list(path.parent.iterdir()), [path])
            finally:
                path.chmod(stat.S_IREAD | stat.S_IWRITE)

    def test_native_access_error_is_not_retried(self):
        from console import winfiles
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            paths.write_text_atomic(path, "old")
            with mock.patch.object(winfiles._kernel, "SetFileInformationByHandle", return_value=False) as rename, \
                    mock.patch.object(winfiles.ctypes, "get_last_error", return_value=5), \
                    mock.patch.object(paths.os, "replace", wraps=os.replace) as ordinary, metadata_reader(path):
                with self.assertRaises(PermissionError):
                    paths.write_text_atomic(path, "new")
            rename.assert_called_once()
            ordinary.assert_called_once()
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_unsupported_native_mode_preserves_the_original_failure(self):
        from console import winfiles
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "task.json"
            paths.write_text_atomic(path, "old")
            with mock.patch.object(winfiles._kernel, "SetFileInformationByHandle", return_value=False) as rename, \
                    mock.patch.object(winfiles.ctypes, "get_last_error", return_value=87), \
                    mock.patch.object(paths.os, "replace", wraps=os.replace) as ordinary, metadata_reader(path):
                with self.assertRaises(PermissionError) as raised:
                    paths.write_text_atomic(path, "new")
            rename.assert_called_once()
            ordinary.assert_called_once()
            self.assertEqual(raised.exception.winerror, 5)
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            self.assertEqual(list(path.parent.iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
