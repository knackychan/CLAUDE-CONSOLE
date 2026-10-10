import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from console import guard, paths, server


class GuardTest(unittest.TestCase):
    def test_host(self):
        self.assertTrue(guard.host_ok("127.0.0.1:8770", 8770))
        self.assertTrue(guard.host_ok("localhost:8770", 8770))
        self.assertFalse(guard.host_ok("evil.example:8770", 8770))
        self.assertFalse(guard.host_ok(None, 8770))

    def test_post_header(self):
        self.assertTrue(guard.post_ok({"X-CC": "1"}))
        self.assertFalse(guard.post_ok({}))


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        folder = Path(self.tmp.name)
        (folder / "events-2026-10-10.jsonl").write_text(
            json.dumps({"ts": 9e12, "event": "UserPromptSubmit", "session_id": "s1", "prompt": "hello"}) + "\n",
            encoding="utf-8")
        cfg = paths.load_config()
        self.httpd, self.hub = server.make_server(cfg, port=0, folder=folder)
        self.hub.poll_once()
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def get(self, path, host=None, method="GET", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest(method, path, skip_host=True)
        conn.putheader("Host", host or f"127.0.0.1:{self.port}")
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        conn.endheaders()
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_state_endpoint(self):
        status, body = self.get("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["sessions"][0]["title"], "hello")

    def test_foreign_host_is_refused(self):
        self.assertEqual(self.get("/api/state", host="evil.example")[0], 403)

    def test_post_needs_header(self):
        self.assertEqual(self.get("/api/state", method="POST")[0], 403)
        self.assertEqual(self.get("/api/x", method="POST", headers={"X-CC": "1"})[0], 404)

    def test_static_and_ping(self):
        self.assertEqual(self.get("/")[0], 200)
        self.assertEqual(json.loads(self.get("/api/ping")[1]), {"app": "claude-console"})


if __name__ == "__main__":
    unittest.main()
