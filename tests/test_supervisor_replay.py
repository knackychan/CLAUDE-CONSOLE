"""Plan 44 T11: the --supervisor-replay CLI branch makes one guarded local request and no local effect."""
import io
import json
import sys
import unittest
from unittest import mock

from console import __main__


class SupervisorReplayCliTest(unittest.TestCase):
    def setUp(self):
        self.cfg = {"port": 47771, "supervisor_timeout_s": 90}

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            try:
                code = __main__.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_invalid_args_are_refused_without_network(self):
        for argv in (
            ["--supervisor-replay"],
            ["--supervisor-replay", "bad id", "1"],
            ["--supervisor-replay", "20260101-000000-abcd", "x"],
            ["--supervisor-replay", "20260101-000000-abcd", "0"],
            ["--supervisor-replay", "20260101-000000-abcd", "1", "--serve"],
        ):
            code, out, err = self.run_main(argv)
            self.assertEqual(code, 2, argv)

    def test_absent_service_fails_with_a_prompt(self):
        with mock.patch.object(__main__.paths, "load_config", return_value=self.cfg), \
                mock.patch.object(__main__, "already_running", return_value=False), \
                mock.patch.object(__main__.paths, "ensure_config", side_effect=AssertionError("no config")):
            code, out, err = self.run_main(["--supervisor-replay", "20260101-000000-abcd", "1"])
        self.assertEqual(code, 1)
        self.assertIn("Start the Console service before replay", err)

    def test_replay_sends_one_guarded_request_and_prints_the_answer(self):
        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"task": "t", "wake": 1, "no_dispatch": True}).encode()

        with mock.patch.object(__main__.paths, "load_config", return_value=self.cfg), \
                mock.patch.object(__main__, "already_running", return_value=True), \
                mock.patch.object(__main__.urllib.request, "urlopen", return_value=Resp()) as url, \
                mock.patch.object(__main__.urllib.request, "Request",
                                  wraps=__main__.urllib.request.Request) as make, \
                mock.patch.object(__main__.paths, "ensure_config", side_effect=AssertionError("no config")):
            code, out, err = self.run_main(["--supervisor-replay", "20260101-000000-abcd", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(url.call_count, 1)
        self.assertIn("no_dispatch", out)
        self.assertEqual(make.call_args[0][0], "http://127.0.0.1:47771/api/task/supervisor/replay")
        self.assertEqual(make.call_args[1]["headers"]["X-CC"], "1")

    def test_http_error_is_printed_and_returns_one(self):
        body = io.BytesIO(json.dumps({"error": "the task is busy"}).encode())
        err_http = __main__.urllib.error.HTTPError("url", 409, "conflict", {}, body)
        with mock.patch.object(__main__.paths, "load_config", return_value=self.cfg), \
                mock.patch.object(__main__, "already_running", return_value=True), \
                mock.patch.object(__main__.urllib.request, "urlopen", side_effect=err_http):
            code, out, err = self.run_main(["--supervisor-replay", "20260101-000000-abcd", "1"])
        self.assertEqual(code, 1)
        self.assertIn("the task is busy", out)


if __name__ == "__main__":
    unittest.main()
