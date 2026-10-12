import base64
import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from console import attach, brief, events, guard, levers, paths, server


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
        self.assertEqual(self.get("/api/usage", host="evil.example")[0], 403)

    def test_usage_endpoint_sums_every_transcript(self):
        now = time.time()
        today, yesterday = time.strftime("%Y-%m-%d"), time.strftime("%Y-%m-%d", time.localtime(now - 86400))
        root = Path(self.tmp.name) / "home" / ".claude" / "projects" / "d--work-X"
        root.mkdir(parents=True)
        stamp = lambda ts: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts)) + "Z"
        line = lambda mid, ts: json.dumps({"type": "assistant", "cwd": "D:/work/X", "timestamp": stamp(ts),
                                           "message": {"id": mid, "model": "claude-opus-5-5",
                                                       "usage": {"input_tokens": 1_000_000}}}) + "\n"
        (root / "s9.jsonl").write_text(line("m1", now - 86400) + line("m2", now), encoding="utf-8")
        self.hub.user_home = Path(self.tmp.name) / "home"
        status, body = self.get("/api/usage")
        self.assertEqual((status, json.loads(body)["ready"]), (200, False))
        self.hub.read_history()
        data = json.loads(self.get("/api/usage")[1])
        self.assertTrue(data["ready"])
        self.assertEqual((data["today"], data["first"], data["limit"]), (today, yesterday, 15))
        self.assertEqual(data["days"][today]["projects"], {"X": 4.0})
        self.assertEqual(data["days"][yesterday]["tokens"], [1_000_000, 0, 0, 0])
        self.assertEqual((len(data["weeks"]), len(data["months"])), (12, 12))
        self.assertEqual(data["months"][-1]["month"], today[:7])
        self.assertAlmostEqual(sum(w["cost"] for w in data["weeks"]), 8.0)
        kept = json.loads((Path(self.tmp.name) / "usage-days.json").read_text(encoding="utf-8"))["days"]
        self.assertEqual(sorted(kept), [yesterday])  # closed days only

    def test_post_needs_header(self):
        self.assertEqual(self.get("/api/state", method="POST")[0], 403)
        self.assertEqual(self.get("/api/x", method="POST", headers={"X-CC": "1"})[0], 404)

    def test_static_and_ping(self):
        self.assertEqual(self.get("/")[0], 200)
        self.assertEqual(json.loads(self.get("/api/ping")[1]), {"app": "claude-console"})
        status, font = self.get("/doto.woff2")
        self.assertEqual((status, font[:4]), (200, b"wOF2"))
        for page in ("/", "/style.css", "/app.js"):  # the window makes no network calls
            self.assertNotIn(b"https://", self.get(page)[1], page)

    def test_image_thumbnails_from_the_transcript_and_the_folder(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        folder = Path(self.tmp.name) / "proj"
        (folder / "out").mkdir(parents=True)
        (folder / "out" / "grid.png").write_bytes(png)
        (folder / "notes.md").write_text("# not an image", encoding="utf-8")
        (Path(self.tmp.name) / "secret.png").write_bytes(png)  # outside the session's folder
        transcript = Path(self.tmp.name) / "s3.jsonl"
        transcript.write_text(json.dumps({"type": "user", "uuid": "u-1", "message": {"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.b64encode(png).decode()}},
            {"type": "text", "text": "look"}]}}) + "\n", encoding="utf-8")
        with open(Path(self.tmp.name) / "events-2026-10-10.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": 9e12, "event": "UserPromptSubmit", "session_id": "s3", "prompt": "look",
                                 "cwd": str(folder), "transcript_path": str(transcript)}) + "\n")
        self.hub.poll_once()
        self.assertEqual(self.get("/api/image?session=s3&at=u-1&k=0"), (200, png))
        self.assertEqual(self.get("/api/image?session=s3&path=out/grid.png"), (200, png))
        for bad in ("at=u-1&k=1", "at=u-2&k=0", "at=u-1&k=x", "path=notes.md", "path=../secret.png",
                    "path=" + str(Path(self.tmp.name) / "secret.png")):
            self.assertEqual(self.get("/api/image?session=s3&" + bad)[0], 404, bad)
        self.assertEqual(self.get("/api/image?session=nope&at=u-1&k=0")[0], 404)
        self.assertEqual(self.get("/api/image?session=s3&at=u-1&k=0", host="evil.example")[0], 403)

    def test_hub_reads_transcripts_for_the_estimate(self):
        transcript = Path(self.tmp.name) / "s2.jsonl"
        transcript.write_text(json.dumps({"type": "assistant", "timestamp": "2026-10-10T10:00:00Z", "message": {
            "id": "m1", "model": "claude-sonnet-5-5", "usage": {"input_tokens": 1_000_000}}}) + "\n", encoding="utf-8")
        with open(Path(self.tmp.name) / "events-2026-10-10.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": 9e12, "event": "UserPromptSubmit", "session_id": "s2", "prompt": "hi",
                                 "transcript_path": str(transcript)}) + "\n")
        self.hub.poll_once()
        self.assertEqual(self.hub.read_costs(), 1)
        self.assertEqual(self.hub.read_costs(), 0)
        row = next(s for s in self.hub.snapshot()["sessions"] if s["id"] == "s2")
        self.assertEqual((row["spent"], row["spent_exact"]), (2.0, False))


class RunServerTest(unittest.TestCase):
    """POST routes with the fake claude: prep, run, chat, stop, levers, draft."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        cfg = dict(paths.load_config(), projects=[str(self.project)])
        fake = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
        self.httpd, self.hub = server.make_server(cfg, port=0, folder=self.folder, exe=fake)
        self.hub.user_home = Path(self.tmp.name)  # no ~/.claude/skills here unless a test adds one
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

    def prep_job(self, job, end=None):
        """The job as the snapshot shows it, once it has left `running` (None when it is gone)."""
        end = end or time.time() + 15
        while True:
            row = next((j for j in self.hub.snapshot()["preps"] if j["id"] == job), None)
            if row is None or row["state"] != "running" or time.time() > end:
                return row
            time.sleep(0.05)

    def test_prep_then_run_then_chat(self):
        status, data = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "fix add"})
        self.assertEqual(status, 200)
        job = self.prep_job(data["job"])
        self.assertEqual((job["state"], job["raw"], job["project_dir"]), ("done", "fix add", str(self.project)))
        card = job["card"]
        self.assertEqual(card["id"], data["job"])
        status, data = self.call("/api/run", {"project_dir": str(self.project), "prompt": card["prompt"],
                                              "model": "sonnet", "effort": "low", "prep": card["id"]})
        self.assertEqual(status, 200)
        sid = data["session"]
        row = self.session(sid)
        self.assertEqual((row["source"], row["title"], row["route"]),
                         ("window", "Fix add() in calc.py", "mechanical"))
        self.assertEqual((row["prep_model"], row["prep_cost"], row["prep_turns"]), ("haiku", 0.03, 5))
        self.assertEqual(self.hub.snapshot()["preps"], [])  # the run took the Prep card off the strip
        end = time.time() + 15
        while time.time() < end and self.session(sid)["run_live"]:
            time.sleep(0.1)
        self.assertEqual(self.session(sid)["cost"], 0.01)
        chat = self.call(f"/api/chat?session={sid}")[1]
        self.assertEqual([i["role"] for i in chat["items"]], ["you", "claude", "tool", "result"])
        self.assertFalse(chat["live"])

    def test_prep_runs_in_the_background(self):
        start = time.monotonic()
        status, data = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "SLOW fix add"})
        self.assertEqual(status, 200)
        self.assertLess(time.monotonic() - start, 1.5)  # the answer does not wait for Haiku (2 s here)
        running = next(j for j in self.hub.snapshot()["preps"] if j["id"] == data["job"])
        self.assertEqual((running["state"], running["raw"]), ("running", "SLOW fix add"))
        self.assertNotIn("card", running)
        version = self.hub.version
        self.assertEqual(self.prep_job(data["job"])["state"], "done")
        self.assertGreater(self.hub.version, version)  # the stream pushed the finished card

    def test_failed_prep_stays_on_the_strip_until_dropped(self):
        job = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "BROKEN"})[1]["job"]
        row = self.prep_job(job)
        self.assertEqual(row["state"], "failed")
        self.assertIn("Prep returned no JSON", row["error"])
        self.assertEqual(self.call("/api/prep/drop", {"job": job}), (200, {"job": job}))
        self.assertEqual(self.hub.snapshot()["preps"], [])
        self.assertEqual(self.call("/api/prep/drop", {"job": job})[0], 404)

    def test_prep_job_never_spins_forever(self):
        def boom(*args, **kwargs):
            raise OSError("disk full")
        real, server.prep.run_prep = server.prep.run_prep, boom
        try:
            job = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "x"})[1]["job"]
            row = self.prep_job(job)
        finally:
            server.prep.run_prep = real
        self.assertEqual((row["state"], row["error"]), ("failed", "disk full"))

    def wait_idle(self, sid):
        end = time.time() + 15
        while time.time() < end and (self.session(sid) is None or self.session(sid)["run_live"]):
            time.sleep(0.1)

    def test_run_and_continue_take_files(self):
        big = {"name": "shot.png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x01" * 1024 * 1024).decode()}
        status, data = self.call("/api/run", {"project_dir": str(self.project), "prompt": "look", "files": [big]})
        self.assertEqual(status, 200)  # over the 256 KB of the other routes
        sid = data["session"]
        self.wait_idle(sid)
        chat = self.call(f"/api/chat?session={sid}")[1]
        self.assertEqual(chat["items"][0]["files"], [{"name": "shot.png", "kind": "image", "bytes": 1024 * 1024 + 8}])
        note = {"name": "n.txt", "data": base64.b64encode(b"more").decode()}
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "and this", "files": [note]}),
                         (200, {"session": sid}))
        self.wait_idle(sid)
        you = [i for i in self.call(f"/api/chat?session={sid}")[1]["items"] if i["role"] == "you"]
        self.assertEqual(you[1]["files"][0]["name"], "n.txt")
        zip_ = {"name": "a.docx", "data": base64.b64encode(b"PK\x03\x04\x14\x00\x00").decode()}
        status, data = self.call("/api/run", {"project_dir": str(self.project), "prompt": "x", "files": [zip_]})
        self.assertEqual((status, data["error"]), (400, "a.docx: send " + attach.SENDABLE))

    def test_prep_job_keeps_files_for_its_run(self):
        shot = {"name": "shot.png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\nPIXELS").decode()}
        old = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "fix it", "files": [shot]})[1]["job"]
        job = self.prep_job(old)
        self.assertEqual(job["attached"], [{"name": "shot.png", "kind": "image", "bytes": 14}])
        self.assertNotIn("files", job)  # the bytes never reach the snapshot
        self.assertNotIn(shot["data"], json.dumps(self.hub.snapshot()))
        self.assertEqual(job["card"]["raw"], "fix it")  # as typed; Prep read the names too:
        saved = json.loads((self.folder / "preps" / f"{old}.json").read_text(encoding="utf-8"))
        self.assertTrue(saved["raw"].endswith("sent with the run: shot.png (image)."))
        new = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "fix it", "files_from": old})[1]["job"]
        self.assertEqual(self.prep_job(new)["attached"][0]["name"], "shot.png")  # Try again keeps them
        card = self.prep_job(new)["card"]
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": card["prompt"], "prep": card["id"]})[1]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.call(f"/api/chat?session={sid}")[1]["items"][0]["files"][0]["name"], "shot.png")
        raw = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix it", "files_from": old})[1]["session"]
        self.wait_idle(raw)  # Run raw from a card: its job's files too
        self.assertEqual(self.call(f"/api/chat?session={raw}")[1]["items"][0]["files"][0]["name"], "shot.png")

    def test_continue_resumes_and_stop_interrupts(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "SLOW one"})[1]["session"]
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "go"})[0], 409)  # still running
        end = time.time() + 15
        while time.time() < end and "echo" not in self.hub.runs.stream_path(sid).read_text(encoding="utf-8"):
            time.sleep(0.1)
        self.assertEqual(self.call("/api/stop", {"session": sid}), (200, {"stop": "interrupt"}))
        while time.time() < end and self.session(sid)["run_live"]:
            time.sleep(0.1)
        self.assertEqual(self.session(sid)["stopped"], True)
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "go on"}), (200, {"session": sid}))

    def test_mark_done_a_chat_that_never_stopped(self):
        events.append(self.folder, {"event": "UserPromptSubmit", "ts": time.time(), "session_id": "v2",
                                    "project": "proj", "project_dir": str(self.project), "prompt": "x"})
        self.hub.poll_once()
        self.assertEqual(self.call("/api/done", {"session": "nope"})[0], 404)
        self.assertEqual(self.call("/api/done", {"session": "v2"}), (200, {"session": "v2"}))
        self.assertEqual(self.session("v2")["state"], "done")

    def test_levers_fork_a_vscode_session(self):
        for event, extra in (("UserPromptSubmit", {"prompt": "fix add"}),
                             ("Stop", {"model": "claude-sonnet-5-5", "effort": "medium"})):
            events.append(self.folder, dict({"event": event, "ts": time.time(), "session_id": "v1",
                                             "project": "proj", "project_dir": str(self.project),
                                             "cwd": str(self.project)}, **extra))
        self.hub.poll_once()
        lv = self.call("/api/levers?session=v1")[1]
        self.assertEqual((lv["continue"], lv["fork"], lv["route"]), ("", True, "sonnet/medium"))
        self.assertEqual(lv["escalate"], "only after a FAIL verdict")
        self.assertIn("session-handoff skill", lv["handoff"])
        self.assertEqual(self.call("/api/handoff", {"session": "v1"})[0], 409)
        self.assertEqual(self.call("/api/levers?session=nope")[0], 404)
        self.assertEqual(self.call("/api/continue", {"session": "v1", "text": " "})[0], 400)
        status, data = self.call("/api/continue", {"session": "v1", "text": "and the tests"})
        self.assertEqual(status, 200)
        fork = data["session"]
        self.assertNotEqual(fork, "v1")
        row = self.session(fork)
        self.assertEqual((row["forked_from"], row["title"], row["kind"], row["source"]),
                         ("v1", "↳ fix add", "continue", "window"))
        self.assertEqual(self.session("v1")["forks"], [fork])
        self.assertEqual((self.hub.runs.meta(fork)["model"], self.hub.runs.meta(fork)["effort"]), ("sonnet", "medium"))
        self.wait_idle(fork)

    def test_chat_of_a_vscode_chat_reads_its_transcript(self):
        transcript = Path(self.tmp.name) / "v2.jsonl"
        transcript.write_text("".join(json.dumps(rec) + "\n" for rec in (
            {"type": "user", "timestamp": "2026-10-10T10:00:00Z", "message": {"role": "user", "content": "hello"}},
            {"type": "assistant", "timestamp": "2026-10-10T10:00:05Z", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Hi."}, {"type": "tool_use", "name": "Read", "input": {}}]}})),
            encoding="utf-8")
        events.append(self.folder, {"event": "UserPromptSubmit", "ts": time.time(), "session_id": "v2",
                                    "project": "proj", "project_dir": str(self.project), "prompt": "hello",
                                    "transcript_path": str(transcript)})
        self.hub.poll_once()
        chat = self.call("/api/chat?session=v2")[1]
        self.assertEqual((chat["source"], [(i["role"], i["text"]) for i in chat["items"]]),
                         ("transcript", [("you", "hello"), ("claude", "Hi.")]))
        self.assertEqual(self.call("/api/chat?session=nope")[1]["items"], [])

    def idle_chat(self, sid, hours, tokens, transcript=None):
        """A VS Code chat whose last event was `hours` ago, holding `tokens` of context."""
        ts = time.time() - hours * 3600
        base = {"session_id": sid, "project": "proj", "project_dir": str(self.project), "cwd": str(self.project)}
        first = dict(base, event="UserPromptSubmit", ts=ts, prompt="fix add")
        if transcript:
            first["transcript_path"] = str(transcript)
        events.append(self.folder, first)
        events.append(self.folder, dict(base, event="PreToolUse", ts=ts + 1, tool="Edit", what="calc.py"))
        events.append(self.folder, dict(base, event="PreToolUse", ts=ts + 2, tool="Edit", what="calc.py"))
        events.append(self.folder, dict(base, event="PreToolUse", ts=ts + 3, tool="Read", what="notes.md"))
        events.append(self.folder, dict(base, event="Stop", ts=ts + 4, model="claude-sonnet-5-5",
                                        effort="medium", context_tokens=tokens))
        self.hub.poll_once()

    def test_a_cold_large_chat_needs_a_confirm_before_a_lever_re_reads_it(self):
        self.idle_chat("c1", hours=9, tokens=444000)
        lv = self.call("/api/levers?session=c1")[1]
        self.assertEqual(lv["cold"], {"idle_s": lv["cold"]["idle_s"], "tokens": 444000, "cost": 1.11})  # sonnet 2.5 / M
        self.assertTrue(9 * 3600 - 60 < lv["cold"]["idle_s"] < 9 * 3600 + 60)
        for lever, body in (("continue", {"text": "go"}), ("verify", {})):
            status, data = self.call(f"/api/{lever}", dict(body, session="c1"))
            self.assertEqual(status, 409, lever)
            self.assertTrue(data["error"].startswith("cold cache: 444K tokens, idle 9 h, would be re-read at full "
                                                     "price (about $1.11)"), data)
        self.assertEqual(self.call("/api/continue", {"session": "c1", "text": "go", "confirm": "yes"})[0], 409)
        self.assertEqual([s["id"] for s in self.hub.snapshot()["sessions"]], ["c1"])  # nothing started
        status, data = self.call("/api/continue", {"session": "c1", "text": "go", "confirm": True})
        self.assertEqual(status, 200)
        self.assertNotEqual(data["session"], "c1")
        self.wait_idle(data["session"])

    def test_no_cold_guard_for_a_recent_or_a_small_chat(self):
        self.idle_chat("r1", hours=0.5, tokens=444000)  # the cache may still be warm
        self.idle_chat("s1", hours=9, tokens=100000)  # cheap to re-read
        self.assertIsNone(self.call("/api/levers?session=r1")[1]["cold"])
        self.assertIsNone(self.call("/api/levers?session=s1")[1]["cold"])
        status, data = self.call("/api/continue", {"session": "s1", "text": "go"})
        self.assertEqual(status, 200)
        self.wait_idle(data["session"])

    def test_brief_of_a_session_from_its_transcript_and_steps(self):
        transcript = Path(self.tmp.name) / "c2.jsonl"
        transcript.write_text("".join(json.dumps(rec) + "\n" for rec in (
            {"type": "user", "timestamp": "2026-10-10T10:00:00Z",
             "message": {"role": "user", "content": "Implement the Cells Drawer window"}},
            {"type": "assistant", "timestamp": "2026-10-10T10:00:05Z",
             "message": {"role": "assistant", "content": [{"type": "text", "text": "Step 3 is placed."}]}},
            {"type": "user", "timestamp": "2026-10-10T10:01:00Z",
             "message": {"role": "user", "content": "continue"}})), encoding="utf-8")
        (self.project / "PLAN.md").write_text("# plan", encoding="utf-8")
        self.idle_chat("c2", hours=9, tokens=444000, transcript=transcript)
        status, data = self.call("/api/brief?session=c2")
        self.assertEqual((status, data["project_dir"]), (200, self.hub.session("c2")["project_dir"]))
        for part in ("Goal (the first prompt of the earlier chat):\nImplement the Cells Drawer window",
                     "Where it stopped (the last message of Claude):\nStep 3 is placed.",
                     "Files the earlier chat edited:\n- calc.py\n\n", "Read PLAN.md first."):
            self.assertIn(part, data["text"])
        self.assertNotIn("notes.md", data["text"])  # a Read is not an edit
        verify = self.call("/api/brief?session=c2&kind=verify")[1]["text"]
        self.assertTrue(verify.startswith("Check the work of this session."))
        self.assertNotIn("PLAN.md", verify)
        self.assertEqual(self.call("/api/brief?session=nope")[0], 404)
        self.assertEqual(self.call("/api/brief?session=c2&kind=other")[0], 404)

    def test_brief_without_a_transcript_falls_back_to_the_title(self):
        self.idle_chat("c3", hours=9, tokens=444000)
        text = self.call("/api/brief?session=c3")[1]["text"]
        self.assertIn("Goal (the first prompt of the earlier chat):\nfix add", text)
        self.assertNotIn("Where it stopped", text)

    def test_verify_then_escalate_once(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",
                                     "model": "sonnet", "effort": "high"})[1]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.call("/api/escalate", {"session": sid}), (409, {"error": "only after a FAIL verdict"}))
        self.assertEqual(self.call("/api/verify", {"session": sid}), (200, {"session": sid}))
        self.wait_idle(sid)
        events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": sid,  # what the hook logs
                                    "verdict": "FAIL", "verdict_detail": "test_add - 3 != 4"})
        self.hub.poll_once()
        self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["escalate_to"], "opus/high")
        self.assertEqual(self.call("/api/escalate", {"session": sid}), (200, {"session": sid}))
        self.assertEqual(self.hub.runs.meta(sid)["model"], "opus")
        self.wait_idle(sid)
        self.assertEqual(self.session(sid)["escalated"], "sonnet/high -> opus/high")
        self.assertTrue(self.call(f"/api/levers?session={sid}")[1]["escalate"].startswith("escalated once already"))
        misses = levers.read_misses(self.folder, "proj")
        self.assertEqual(len(misses), 1)
        self.assertTrue(misses[0].endswith(" - proj - raw: sonnet/high failed (test_add - 3 != 4); "
                                           "next time start at opus/high."))
        you = [i["text"] for i in self.call(f"/api/chat?session={sid}")[1]["items"] if i["role"] == "you"]
        self.assertTrue(you[1].startswith("Check the work of this session."))
        self.assertIn("`~/.claude/agents`", you[1])  # the user-level verifier counts too (plan 04 Task 5)
        self.assertTrue(you[2].startswith("The checks failed: test_add - 3 != 4. You now run on opus/high"))

    def verdict(self, sid, verdict, detail=""):
        events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": sid,  # what the hook logs
                                    "verdict": verdict, "verdict_detail": detail})
        self.hub.poll_once()

    def test_route_steps_run_by_themselves_through_levers(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",
                                     "model": "sonnet", "effort": "medium"})[1]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.hub.auto_steps(), [])  # no verdict, no step
        self.assertEqual(self.hub.pull(sid, "deescalate"), (409, {"error": "only after a PASS verdict"}))
        self.verdict(sid, "FAIL", "test_add - 3 != 4")
        self.assertEqual(self.hub.auto_steps(), [(sid, "escalate")])
        self.assertEqual(self.hub.runs.meta(sid)["model"], "sonnet")
        self.assertEqual(self.hub.runs.meta(sid)["effort"], "high")
        self.wait_idle(sid)
        self.assertEqual(self.session(sid)["escalated"], "sonnet/medium -> sonnet/high")
        self.verdict(sid, "FAIL", "still 3 != 4")
        self.assertEqual(self.hub.auto_steps(), [])  # once per task: levers says "escalated once already"
        self.verdict(sid, "PASS")
        lv = self.call(f"/api/levers?session={sid}")[1]
        self.assertEqual((lv["deescalate"], lv["deescalate_to"]), ("", "sonnet/medium"))
        self.assertEqual(self.hub.auto_steps(), [(sid, "deescalate")])
        meta = self.hub.runs.meta(sid)
        self.assertEqual((meta["model"], meta["effort"], meta["start_route"]), ("sonnet", "medium", "sonnet/medium"))
        self.assertFalse(self.hub.runs.is_live(sid))  # de-escalate starts no turn
        lv = self.call(f"/api/levers?session={sid}")[1]
        self.assertEqual((lv["deescalate"], lv["route"]), ("already on the task's starting route", "sonnet/medium"))
        self.assertEqual(self.hub.auto_steps(), [])
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "next"}), (200, {"session": sid}))
        self.assertEqual(self.hub.runs.meta(sid)["effort"], "medium")  # the next turn runs on the lower route
        self.wait_idle(sid)

    def test_route_steps_skip_old_verdicts_and_vscode_chats(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",
                                     "model": "sonnet", "effort": "medium"})[1]["session"]
        self.wait_idle(sid)
        self.hub.auto_since = time.time() + 60  # as if the service started after this verdict
        self.verdict(sid, "FAIL")
        self.assertEqual(self.hub.auto_steps(), [])
        self.hub.auto_since = 0
        self.idle_chat("c4", hours=0, tokens=1000)  # a VS Code chat: Escalate only by a click (a fork)
        self.verdict("c4", "FAIL")
        self.assertEqual(self.hub.levers("c4")["escalate"], "")  # a click may, the service does not
        self.assertEqual([lever for s, lever in self.hub.auto_steps() if s == "c4"], [])

    def test_handoff_marks_the_session_done(self):
        skill = self.project / ".claude" / "skills" / "session-handoff"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add"})[1]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.call("/api/handoff", {"session": sid}), (200, {"session": sid}))
        self.wait_idle(sid)
        row = self.session(sid)
        self.assertEqual((row["state"], row["group"], row["kind"]), ("done", "done", "handoff"))

    def test_handoff_starts_a_new_session_with_the_note(self):
        skill = self.project / ".claude" / "skills" / "session-handoff"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add"})[1]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["next"], "only after a Hand off")
        self.assertEqual(self.call(f"/api/brief?session={sid}&kind=next"), (409, {"error": "only after a Hand off"}))
        self.call("/api/handoff", {"session": sid})
        self.wait_idle(sid)
        self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["next"], "")
        status, data = self.call(f"/api/brief?session={sid}&kind=next")
        self.assertEqual((status, data["project_dir"]), (200, self.hub.session(sid)["project_dir"]))
        self.assertTrue(data["text"].startswith(brief.NEXT_INTRO))
        self.assertIn("Handoff note:\necho: /session-handoff", data["text"])  # the skill's last message
        new = self.call("/api/run", {"project_dir": str(self.project), "prompt": data["text"]})[1]["session"]
        self.assertNotEqual(new, sid)
        self.wait_idle(new)
        you = [i["text"] for i in self.call(f"/api/chat?session={new}")[1]["items"] if i["role"] == "you"]
        self.assertEqual(you, [data["text"]])
        self.assertEqual(self.session(sid)["state"], "done")  # the source stays Done
        self.assertNotEqual(self.session(new)["state"], "done")

    def test_lever_order_after_verify(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add"})[1]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["after_verify"], ["handoff", "escalate", "done"])
        for verdict, order in (("PASS", ["handoff", "done"]), ("FAIL", ["escalate", "handoff", "done"])):
            events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": sid,
                                        "verdict": verdict, "verdict_detail": ""})
            self.hub.poll_once()
            self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["after_verify"], order, verdict)

    def test_allow_adds_a_folder_claude_code_ran_in(self):
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        self.folder.mkdir(parents=True)
        (self.folder / "config.json").write_text('{"port": 8770, "projects": []}', encoding="utf-8")
        events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": "v1",
                                    "project": "other", "project_dir": str(other)})
        self.hub.poll_once()
        run = {"project_dir": str(other), "prompt": "x"}
        self.assertEqual(self.call("/api/run", dict(run, model="gpt-9"))[0], 403)
        self.assertEqual(self.call("/api/allow", {"project_dir": self.tmp.name})[0], 403)  # no session there
        self.assertEqual(self.call("/api/allow", {"project_dir": str(other / "nope")})[0], 400)
        status, data = self.call("/api/allow", {"project_dir": str(other)})
        self.assertEqual(status, 200)
        self.assertEqual(data["projects"], self.call("/api/config")[1]["projects"])
        self.assertEqual(len(data["projects"]), 2)
        saved = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.assertEqual((saved["port"], len(saved["projects"])), (8770, 1))
        self.assertEqual(self.call("/api/allow", {"project_dir": str(other)})[0], 200)  # twice: no duplicate
        self.assertEqual(len(json.loads((self.folder / "config.json").read_text(encoding="utf-8"))["projects"]), 1)
        self.assertEqual(self.call("/api/run", dict(run, model="gpt-9"))[0], 400)  # past the folder check

    def test_draft_and_config(self):
        self.assertEqual(self.call("/api/draft", {"text": "half a prompt"}), (200, {"ok": True}))
        self.assertEqual(self.call("/api/draft")[1], {"text": "half a prompt"})
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["projects"], cfg["claude"], cfg["default_model"], cfg["project"]),
                         ([str(self.project)], True, "sonnet", ""))
        self.assertEqual(self.call("/api/draft", {"text": "", "project": str(self.project)})[0], 200)
        self.assertEqual(self.call("/api/config")[1]["project"], str(self.project))
        self.assertEqual(cfg["gauge"], [150000, 300000])
        self.assertEqual(self.call("/api/draft", {"text": "", "project": 3})[0], 400)
        self.assertIs(cfg["brief"], False)
        self.assertEqual(self.call("/api/draft", {"text": "", "brief": True})[0], 200)
        config = self.call("/api/config")[1]
        self.assertEqual((config["brief"], config["project"]), (True, str(self.project)))  # project kept
        self.assertEqual(self.call("/api/draft", {"text": "", "brief": "yes"})[0], 400)


if __name__ == "__main__":
    unittest.main()
