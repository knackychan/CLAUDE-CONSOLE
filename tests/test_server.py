import http.client
import json
import sys
import tempfile
import threading
import time
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


class RunServerTest(unittest.TestCase):
    """POST routes with the fake claude: prep, run, chat, stop, answer, draft."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        cfg = dict(paths.load_config(), projects=[str(self.project)])
        fake = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
        self.httpd, self.hub = server.make_server(cfg, port=0, folder=self.folder, exe=fake)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        for proc in list(self.hub.runs.live.values()):
            proc.kill()
        end = time.time() + 10
        while self.hub.runs.live and time.time() < end:  # let the watcher threads finish
            time.sleep(0.05)
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def call(self, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        headers = {"Host": f"127.0.0.1:{self.port}"}
        if body is None:
            conn.request("GET", path, headers=headers)
        else:
            headers.update({"X-CC": "1", "Content-Type": "application/json"})
            conn.request("POST", path, body=json.dumps(body).encode("utf-8"), headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read() or b"null")
        conn.close()
        return resp.status, data

    def session(self, sid):
        self.hub.poll_once()
        return next((s for s in self.hub.snapshot()["sessions"] if s["id"] == sid), None)

    def test_only_listed_projects_can_run(self):
        self.assertEqual(self.call("/api/run", {"project_dir": self.tmp.name, "prompt": "x"})[0], 403)
        self.assertEqual(self.call("/api/prep", {"project_dir": "C:/Windows", "prompt": "x"})[0], 403)
        self.assertEqual(self.call("/api/run", {"project_dir": str(self.project), "prompt": " "})[0], 400)
        self.assertEqual(self.call("/api/run", {"project_dir": str(self.project), "prompt": "x",
                                                "model": "gpt-9"})[0], 400)
        self.assertEqual(self.call("/api/stop", {"session": "nope"})[0], 404)

    def test_prep_then_run_then_chat(self):
        status, card = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "fix add"})
        self.assertEqual(status, 200)
        status, data = self.call("/api/run", {"project_dir": str(self.project), "prompt": card["prompt"],
                                              "model": "sonnet", "effort": "low", "prep": card["id"]})
        self.assertEqual(status, 200)
        sid = data["session"]
        row = self.session(sid)
        self.assertEqual((row["source"], row["title"], row["route"]),
                         ("window", "Fix add() in calc.py", "mechanical"))
        end = time.time() + 15
        while time.time() < end and self.session(sid)["run_live"]:
            time.sleep(0.1)
        self.assertEqual(self.session(sid)["cost"], 0.01)
        chat = self.call(f"/api/chat?session={sid}")[1]
        self.assertEqual([i["role"] for i in chat["items"]], ["you", "claude", "tool", "result"])
        self.assertFalse(chat["live"])

    def test_answer_resumes_and_stop_interrupts(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "SLOW one"})[1]["session"]
        self.assertEqual(self.call("/api/answer", {"session": sid, "text": "go"})[0], 409)  # still running
        end = time.time() + 15
        while time.time() < end and "echo" not in self.hub.runs.stream_path(sid).read_text(encoding="utf-8"):
            time.sleep(0.1)
        self.assertEqual(self.call("/api/stop", {"session": sid}), (200, {"stop": "interrupt"}))
        while time.time() < end and self.session(sid)["run_live"]:
            time.sleep(0.1)
        self.assertEqual(self.session(sid)["stopped"], True)
        self.assertEqual(self.call("/api/answer", {"session": sid, "text": "go on"}), (200, {"session": sid}))

    def test_draft_and_config(self):
        self.assertEqual(self.call("/api/draft", {"text": "half a prompt"}), (200, {"ok": True}))
        self.assertEqual(self.call("/api/draft")[1], {"text": "half a prompt"})
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["projects"], cfg["claude"], cfg["default_model"]), ([str(self.project)], True, "sonnet"))


if __name__ == "__main__":
    unittest.main()
