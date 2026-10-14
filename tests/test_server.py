import base64
import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import quote
from pathlib import Path
from unittest import mock

from console import attach, brief, claude_cli, events, guard, levers, paths, server, tasks, usage


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

    def test_review_job_on_the_strip(self):
        levers.add_lesson(self.folder, levers.lesson_line("proj", "code", "profile first"))
        levers.add_miss(self.folder, levers.miss_line("proj", "code", "sonnet/medium", "sonnet/high", "x"))
        status, data = self.call("/api/review", {"project_dir": str(self.project)})
        self.assertEqual(status, 200, data)
        running = next(j for j in self.hub.snapshot()["preps"] if j["id"] == data["job"])
        self.assertEqual((running["kind"], running["state"], running["raw"]), ("review", "running", "Review rules"))
        row = self.prep_job(data["job"])
        self.assertEqual(row["state"], "done", row.get("error"))
        card = row["card"]
        self.assertEqual((card["id"], card["project_dir"], card["model"]), (data["job"], str(self.project), "haiku"))
        self.assertEqual((card["misses"], card["lessons"]), (1, 1))
        self.assertEqual(card["proposals"][0]["kind"], "remove")
        self.assertEqual(card["summary"], "CLAUDE.md is 12 lines, fine.")
        self.assertTrue((self.folder / "reviews" / f"{card['id']}.json").is_file())
        self.assertEqual(self.call("/api/prep/drop", {"job": data["job"]}), (200, {"job": data["job"]}))
        self.assertEqual(self.call("/api/review", {"project_dir": self.tmp.name})[0], 403)

    def wait_idle(self, sid):
        end = time.time() + 15
        while time.time() < end and (self.session(sid) is None or self.session(sid)["run_live"]):
            time.sleep(0.1)

    def test_fable_run_needs_the_confirm(self):
        body = {"project_dir": str(self.project), "prompt": "hi", "model": "fable", "effort": "low"}
        status, data = self.call("/api/run", body)
        self.assertEqual((status, data["error"]), (409, "confirm Fable: it may bill usage credits on this plan"))
        status, data = self.call("/api/run", dict(body, fable_ok=True))
        self.assertEqual(status, 200, data)
        self.wait_idle(data["session"])

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

    def test_chat_of_an_unknown_session_reads_its_transcript(self):
        sid = "0b1c2d3e-aaaa-bbbb-cccc-111122223333"  # no event, no run: an older step after Clear
        path = self.hub.user_home / ".claude" / "projects" / "X" / f"{sid}.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("".join(json.dumps(rec) + "\n" for rec in (
            {"type": "user", "timestamp": "2026-10-10T10:00:00Z", "message": {"role": "user", "content": "hello"}},
            {"type": "assistant", "timestamp": "2026-10-10T10:00:05Z", "message": {"role": "assistant", "content": [
                {"type": "text", "text": "Hi."}]}})), encoding="utf-8")
        chat = self.call(f"/api/chat?session={sid}")[1]
        self.assertEqual((chat["source"], [(i["role"], i["text"]) for i in chat["items"]]),
                         ("transcript", [("you", "hello"), ("claude", "Hi.")]))

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

    # -- plan 23: auto handoff at red ---------------------------------------------------------------------------
    def skill_here(self):
        skill = self.project / ".claude" / "skills" / "session-handoff"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")

    def red(self, sid, tokens=312000):
        events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": sid,  # what the hook logs
                                    "context_tokens": tokens})
        self.hub.poll_once()

    def test_setting_route_writes_handoff_auto_only(self):
        self.assertEqual(self.call("/api/setting", {"key": "handoff_auto", "value": True}),
                         (200, {"key": "handoff_auto", "value": True}))
        self.assertIs(self.hub.cfg["handoff_auto"], True)
        saved = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.assertIs(saved["handoff_auto"], True)
        self.assertIs(self.call("/api/config")[1]["handoff_auto"], True)
        self.assertEqual(self.call("/api/setting", {"key": "brief_on", "value": False}),
                         (400, {"error": "not a setting: brief_on"}))
        self.assertEqual(self.call("/api/setting", {"key": "handoff_auto", "value": "yes"})[0], 400)
        self.assertIs(self.hub.cfg["brief_on"], True)

    def test_auto_handoff_hands_a_red_window_run_off(self):
        self.skill_here()
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",
                                     "model": "sonnet", "effort": "medium"})[1]["session"]
        self.wait_idle(sid)
        self.red(sid)
        self.assertEqual(self.hub.auto_steps(), [])  # handoff_auto is off by default
        self.hub.cfg["handoff_auto"] = True
        self.assertEqual(self.hub.auto_steps(), [(sid, "handoff")])
        self.assertEqual(self.hub.runs.meta(sid)["model"], "sonnet")  # in place: a window run resumes
        self.wait_idle(sid)
        row = self.session(sid)
        self.assertEqual((row["state"], row["group"], row["kind"], row["auto_handoff"]),
                         ("done", "needs", "handoff", 312000))
        self.assertEqual(self.hub.auto_steps(), [])  # once per session
        self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["next"], "")  # Start next chat
        self.assertEqual(self.call("/api/done", {"session": sid})[0], 200)
        row = self.session(sid)
        self.assertEqual((row["group"], row["auto_handoff"]), ("done", 0))

    def test_auto_handoff_forks_a_red_vscode_chat_and_skips_route_steps(self):
        self.skill_here()
        self.hub.cfg["handoff_auto"] = True
        self.hub.auto_since = 0
        self.idle_chat("c6", hours=0, tokens=1000)
        self.assertEqual(self.hub.auto_steps(), [])  # not red
        self.idle_chat("c7", hours=0, tokens=312000)
        self.assertEqual(self.hub.auto_steps(), [("c7", "handoff")])
        fork = self.session("c7")["forks"][0]
        self.wait_idle(fork)
        row, copy_row = self.session("c7"), self.session(fork)
        self.assertEqual((row["state"], row["group"], row["auto_handoff"], row["handoff_by"]),
                         ("done", "needs", 312000, fork))  # the VS Code chat itself is never resumed
        self.assertEqual((copy_row["kind"], copy_row["auto_handoff"]), ("handoff", 0))  # one card: the chat's
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add",
                                     "model": "sonnet", "effort": "medium"})[1]["session"]
        self.wait_idle(sid)
        self.hub.cfg["handoff_auto"] = False
        self.red(sid)
        self.verdict(sid, "FAIL", "test_add - 3 != 4")
        self.hub.cfg["handoff_auto"] = True
        self.assertEqual(self.hub.auto_steps(), [(sid, "handoff")])  # red: the handoff, not an Escalate
        self.wait_idle(sid)

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

    def test_handoff_after_pass_starts_fresh_from_a_brief(self):
        skill = self.project / ".claude" / "skills" / "session-handoff"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add"})[1]["session"]
        self.wait_idle(sid)
        self.verdict(sid, "PASS")
        with mock.patch.object(self.hub.runs, "start", wraps=self.hub.runs.start) as start:
            status, data = self.call("/api/handoff", {"session": sid})
        self.assertEqual(status, 200)
        new = data["session"]
        self.assertNotEqual(new, sid)  # a fresh session: the earlier context is not re-read
        args, kw = start.call_args
        self.assertEqual((kw["resume"], kw["fork"], kw["kind"]), (None, "", "handoff"))
        self.assertEqual(tuple(args[2:4]), levers.HANDOFF_ROUTE)
        prompt = args[1]
        self.assertTrue(prompt.startswith(levers.HANDOFF_TEXT + " " + brief.HANDOFF_INTRO))
        self.assertIn("fix add", prompt)  # the goal, from the brief
        self.assertIn("Last check: PASS", prompt)
        self.assertNotIn("\n", prompt)  # one line: the skill takes it as its arguments
        self.wait_idle(new)
        row = self.session(sid)
        self.assertEqual((row["state"], row["handoff_by"]), ("done", new))
        self.assertIn("echo: /session-handoff", self.call(f"/api/brief?session={sid}&kind=next")[1]["text"])

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

    def test_open_folder_allows_a_folder_without_a_session(self):
        fresh = Path(self.tmp.name) / "fresh"
        fresh.mkdir()
        self.folder.mkdir(parents=True)
        (self.folder / "config.json").write_text('{"port": 8770, "projects": []}', encoding="utf-8")
        self.assertEqual(self.call("/api/open_folder", {"project_dir": str(fresh / "nope")})[0], 400)
        self.assertEqual(self.call("/api/allow", {"project_dir": str(fresh)})[0], 403)  # the session rule stays
        status, data = self.call("/api/open_folder", {"project_dir": str(fresh)})
        self.assertEqual(status, 200)
        self.assertIn(os.path.normcase(str(fresh)), [os.path.normcase(p) for p in data["projects"]])
        self.assertEqual(self.call("/api/open_folder", {"project_dir": str(fresh)})[0], 200)  # twice: no duplicate
        self.assertEqual(len(json.loads((self.folder / "config.json").read_text(encoding="utf-8"))["projects"]), 1)

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


class TaskServerTest(RunServerTest):
    """Plan 17 Task 4: the supervisor. The hub loop does not run in these tests: `advance()` is called by hand
    (through `until`), so every pass is one the test can see."""

    def prep_card(self, text="CHAIN fix add"):
        job = self.call("/api/prep", {"project_dir": str(self.project), "prompt": text})[1]["job"]
        row = self.prep_job(job)
        self.assertEqual(row["state"], "done")
        return row["card"]

    def post_task(self, card, words="HANDOFF-OK", steps=None, effort="auto"):
        """POST /api/task with the card's steps (or `steps`); `words` ride in the prompt, which every step carries."""
        steps = steps or [{"kind": s["kind"], "goal": s["goal"]} for s in card["steps"]]
        return self.call("/api/task", {"prep": card["id"], "prompt": f"{card['prompt']}\n{words}".strip(),
                                       "steps": steps, "effort": effort})

    def make_task(self, text="CHAIN fix add", **kwargs):
        status, data = self.post_task(self.prep_card(text), **kwargs)
        self.assertEqual(status, 200, data)
        return data["task"]

    def task(self, tid):
        return self.call(f"/api/task?id={tid}")

    def until(self, tid, cond, what, seconds=25):
        """advance() until cond(task) holds; fails with the task's state when it never does."""
        end = time.time() + seconds
        while time.time() < end:
            self.hub.poll_once()
            self.hub.advance()
            task = self.hub.tasks[tid]
            if cond(task):
                return task
            time.sleep(0.1)
        self.fail(f"{what}: state {task['state']} ({task['why']}), steps "
                  f"{[(s['n'], s['kind'], s['state']) for s in task['steps']]}")

    def at(self, n, state="running"):
        return lambda task: any(s["n"] == n and s["state"] == state for s in task["steps"])

    def prompt_of(self, sid):
        return next(i["text"] for i in self.call(f"/api/chat?session={sid}")[1]["items"] if i["role"] == "you")

    def chain(self, tid):
        path = self.folder / "tasks" / tid / "chain.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_chain_starts_step_one_from_the_card(self):
        card = self.prep_card()
        status, data = self.post_task(card)
        self.assertEqual(status, 200)
        tid = data["task"]
        folder = self.folder / "tasks" / tid
        self.assertTrue((folder / "task.json").is_file())
        self.assertIn("HANDOFF-OK", (folder / "prompt.md").read_text(encoding="utf-8"))
        task = self.task(tid)[1]["task"]
        step = task["steps"][0]
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout", "code", "verify"])
        self.assertEqual((task["state"], task["current"], step["state"], step["model"], step["effort"]),
                         ("running", 1, "running", "haiku", "low"))
        row = self.session(step["session"])
        self.assertEqual((row["task"], row["step"], row["kind"]), (tid, 1, "task"))
        limits = self.hub.runs.meta(step["session"])["limits"]
        self.assertEqual((limits["disallow"], limits["tools"], limits["budget"]), (["Agent"], "Read,Grep,Glob", 3))
        self.assertEqual((limits["strict_mcp"], limits["max_turns"]), (True, 15))  # plan 23: no MCP, read_max_turns
        self.assertEqual(self.hub.snapshot()["preps"], [])  # the card became the task
        # a second task in the same project starts beside the first (plan 20: parallel tasks per project)
        other = tasks.new_task(str(self.project), "proj", "Other", "goal", tasks.plan_steps(
            [{"kind": "scout", "goal": "look"}], 6), "normal", {}, "", "auto", time.time())
        self.hub.tasks[other["id"]] = other
        self.assertEqual(self.hub.task_levers(other["id"])["start"], "")
        self.assertIsNone(self.hub.task_levers("nope"))

    def test_good_handoff_starts_the_next_step(self):
        tid = self.make_task()
        task = self.until(tid, self.at(2), "step 2 starts")
        step1, step2 = task["steps"][0], task["steps"][1]
        note = (self.folder / "tasks" / tid / "steps" / "01-scout.md").read_text(encoding="utf-8")
        self.assertTrue(note.startswith(f"# Step 01: scout on haiku/low, session {step1['session']}\n\n"))
        self.assertIn("## Findings\nadd() is in calc.py:2", note)
        self.assertEqual((step1["state"], step1["handoff"], task["last_good"]), ("done", "steps/01-scout.md", 1))
        self.assertEqual((step2["model"], step2["effort"]), ("sonnet", "medium"))
        task = self.until(tid, self.at(3), "the verify step starts")
        verify = task["steps"][2]
        self.assertEqual((verify["model"], verify["effort"]), ("opus", "medium"))  # one model up from sonnet/medium
        moves = [(c["step"], c["from"], c["to"]) for c in self.chain(tid)]
        for move in ((1, "planned", "running"), (1, "running", "done"), (2, "planned", "running"),
                     (2, "running", "done"), (3, "planned", "running")):
            self.assertIn(move, moves)

    def test_pinned_step_runs_on_its_model(self):
        """A step Fred pinned to sonnet runs on sonnet even when the note before it asks for opus; the verify
        after it is the only step one model up."""
        card = self.prep_card()
        steps = [{"kind": "scout", "goal": "find add()"}, {"kind": "debug", "goal": "fix add()", "model": "sonnet"}]
        status, data = self.post_task(card, words="HANDOFF-OK HINT-OPUS", steps=steps)
        self.assertEqual(status, 200, data)
        tid = data["task"]
        task = self.until(tid, self.at(3), "the verify step starts")
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout", "debug", "verify"])
        note = (self.folder / "tasks" / tid / "steps" / "01-scout.md").read_text(encoding="utf-8")
        self.assertIn("Next model: opus/high", note)  # the hint was there to be read
        self.assertEqual([(s["pick"], s["model"], s["effort"]) for s in task["steps"]],
                         [("", "haiku", "low"), ("sonnet", "sonnet", "high"), ("", "opus", "high")])
        self.assertIn("hint: opus/high -> pick sonnet kept", task["steps"][1]["notes"])
        self.assertEqual(self.hub.runs.meta(task["steps"][1]["session"])["model"], "sonnet")

    def test_pinned_step_beats_the_miss_floor(self):
        """Fred's live case of 2026-10-13: a code step pinned to sonnet under an Escalate floor of opus/high
        runs on sonnet (at the floor's effort); the verify after it is the only step on opus."""
        levers.add_miss(self.folder, levers.miss_line("proj", "code", "sonnet/high", "opus/high", "NameError"))
        card = self.prep_card()
        self.assertEqual(card["floors"]["code"]["route"], "opus/high")  # the card shows the floor
        steps = [{"kind": "scout", "goal": "find add()"}, {"kind": "code", "goal": "fix add()", "model": "sonnet"}]
        status, data = self.post_task(card, steps=steps)
        self.assertEqual(status, 200, data)
        task = self.until(data["task"], self.at(3), "the verify step starts")
        self.assertEqual([(s["pick"], s["model"], s["effort"]) for s in task["steps"]],
                         [("", "haiku", "low"), ("sonnet", "sonnet", "high"), ("", "opus", "high")])
        self.assertIn("floor code: opus/high -> pick sonnet/high kept", task["steps"][1]["notes"])

    def test_old_miss_is_no_floor_for_a_step(self):
        old = "- 2020-01-01 - proj - code: sonnet/medium failed (x); next time start at opus/high."
        levers.add_miss(self.folder, old)
        card = self.prep_card()
        self.assertEqual(card["floors"], {})
        task = self.until(self.make_task(), self.at(2), "the code step starts")
        self.assertEqual((task["steps"][1]["model"], task["steps"][1]["effort"]), ("sonnet", "medium"))
        self.assertFalse(any(n.startswith("floor") for n in task["steps"][1]["notes"]))

    def test_missing_handoff_retries_once_then_stuck(self):
        tid = self.make_task(words="")
        first = self.hub.tasks[tid]["steps"][0]["session"]
        task = self.until(tid, lambda t: t["steps"][0]["retries"] == 1 and t["steps"][0]["session"] != first
                          and t["steps"][0]["state"] == "running", "step 1 runs again")
        step = task["steps"][0]
        self.assertEqual((step["model"], step["effort"]), ("haiku", "low"))  # the same route
        self.assertIn("ended without a handoff: no HANDOFF block", self.prompt_of(step["session"]))
        self.assertNotIn("ended without a handoff", self.prompt_of(first))
        task = self.until(tid, lambda t: t["state"] == "stuck", "the task is stuck")
        self.assertEqual(task["why"], "no HANDOFF block (after one retry)")
        self.assertEqual(self.call("/api/task/retry", {"task": tid}), (200, {"task": tid, "state": "running"}))
        self.assertEqual(self.hub.tasks[tid]["steps"][0]["state"], "running")
        self.assertEqual(self.call("/api/task/retry", {"task": tid})[0], 409)  # running now

    def test_verify_fail_inserts_fix_and_verify(self):
        tid = self.make_task()
        verify = self.hub.tasks[tid]["steps"][2]
        verify["goal"] += " VERDICT-FAIL"  # the fake claude waits 1 s, so the verdict event can land while it runs
        task = self.until(tid, self.at(3), "the verify runs")
        self.verdict(task["steps"][2]["session"], "FAIL", "test_add - 3 != 4")
        task = self.until(tid, lambda t: len(t["steps"]) == 5, "fix and verify are inserted")
        task["steps"][4]["goal"] += " VERDICT-FAIL"  # the second verify fails the same way
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout", "code", "verify", "fix", "verify"])
        self.assertEqual(task["escalated"], "sonnet/medium -> sonnet/high")
        task = self.until(tid, self.at(4), "the fix runs")
        self.assertEqual((task["steps"][3]["model"], task["steps"][3]["effort"]), ("sonnet", "high"))
        misses = levers.read_misses(self.folder, "proj")
        self.assertEqual(len(misses), 1)
        # the reply's `VERDICT: FAIL x` line wins over the hook's event: the hook is async and may come late
        self.assertIn(" - proj - code: sonnet/medium failed (x); next time start at sonnet/high.", misses[0])
        task = self.until(tid, self.at(5), "the second verify runs")
        self.verdict(task["steps"][4]["session"], "FAIL", "still 3 != 4")
        task = self.until(tid, lambda t: t["state"] == "stuck", "the task is stuck")
        self.assertTrue(task["why"].startswith("verify failed twice"), task["why"])

    TWO = [{"kind": "scout", "goal": "look around"}, {"kind": "explain", "goal": "say what you saw"}]  # no verify

    def settled(self, tid, state="done"):
        """advance() until the task has `state` and its brief thread is over."""
        return self.until(tid, lambda t: t["state"] == state and not t.get("briefing"), f"the task is {state}")

    def test_a_step_lesson_lands_in_lessons_md(self):
        tid = self.make_task(words="HANDOFF-OK LESSON", steps=[{"kind": "scout", "goal": "look"}])  # no edit: no verify
        self.settled(tid)
        lines = levers.read_lessons(self.folder, "proj")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].endswith(" - proj - scout: fake claude teaches one thing"), lines[0])
        self.assertEqual(levers.read_lessons(self.folder, "other"), [])
        tid = self.make_task(words="HANDOFF-OK", steps=[{"kind": "scout", "goal": "look"}])
        self.settled(tid)
        self.assertEqual(len(levers.read_lessons(self.folder, "proj")), 1)  # no Lesson line: nothing added

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=self.project, check=True,
                       capture_output=True)

    def test_facts_are_read_when_a_step_ends(self):
        try:
            self.git("init", "-q")
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("no git")
        (self.project / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base")
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.project, capture_output=True, text=True).stdout.strip()
        tid = self.make_task(words="HANDOFF-OK TESTS-OK")
        task = self.until(tid, self.at(2), "step 2 starts")
        step1 = task["steps"][0]
        self.assertEqual(step1["git_base"]["commit"], base)
        self.assertEqual((step1["end_commit"], step1["facts"]["files"], step1["facts"]["tests"]), (base, 0, "23 OK"))
        text = tasks.read_facts(self.folder, task, 1)
        self.assertIn("no file changed", text)
        self.assertIn("Ran 23 tests", text)
        self.assertIn("Ran 23 tests", self.prompt_of(task["steps"][1]["session"]))  # step 2 reads the facts
        # the step's own lines: written after its start, counted against git_base
        (self.project / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (self.project / "new.py").write_text("x = 1\n", encoding="utf-8")
        with self.hub.tlock:
            self.hub._facts(task, step1, step1["session"])
        self.assertEqual((step1["facts"]["files"], step1["facts"]["plus"], step1["facts"]["minus"]), (2, 2, 1))
        self.assertIn("calc.py", tasks.read_facts(self.folder, task, 1))
        self.assertEqual(self.task(tid)[1]["task"]["steps"][0]["facts"], step1["facts"])

    def test_brief_meta_and_the_carried_troubleshooting(self):
        tid = self.make_task(words="HANDOFF-OK TROUBLE", steps=[{"kind": "scout", "goal": "look"},
                                                               {"kind": "explain", "goal": "say"}])
        task = self.settled(tid)
        meta = task["steps"][0]["brief_meta"]
        self.assertEqual(sorted(meta), ["by", "checks", "cost", "cut", "fallback", "raw_w", "sent_w", "turns"])
        self.assertGreater(meta["raw_w"], 0)
        self.assertEqual(meta["fallback"], "")
        brief2 = tasks.read_brief(self.folder, task, 2)
        self.assertIn("py -3.12 fails here: use py -3.14", brief2)  # carried whole through both briefs
        row = next(t for t in self.hub.snapshot()["tasks"] if t["id"] == tid)
        self.assertEqual(row["steps"][0]["brief_meta"], meta)
        self.assertNotIn("git_base", row["steps"][0])

    def test_lessons_reach_steps_of_their_kind(self):
        levers.add_lesson(self.folder, levers.lesson_line("proj", "scout", "read calc.py before tests"))
        levers.add_lesson(self.folder, levers.lesson_line("proj", "code", "run the suite twice"))
        levers.add_lesson(self.folder, levers.lesson_line("proj", "chat", "a chat lesson"))
        tid = self.make_task(steps=self.TWO)
        task = self.until(tid, self.at(2), "step 2 starts")
        first = self.prompt_of(task["steps"][0]["session"])
        self.assertIn("read calc.py before tests", first)
        self.assertNotIn("run the suite twice", first)
        self.assertNotIn("a chat lesson", first)
        self.settled(tid)

    def over(self, key):
        """A budget() (plan 18) with one model key at 90 % of its pace, binding on the day."""
        return lambda: {key: {"share": 0.9, "binding": "day", "day": {"unknown_runs": 0}}}

    def test_stop_question_waits_for_fred(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "look STOP-ASK"}, self.TWO[1]])
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        events.append(self.folder, {"event": "Stop", "ts": time.time(), "session_id": sid,  # what the hook logs
                                    "stop_question": "which file?"})
        self.wait_idle(sid)
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits")
        self.assertEqual(task["why"], "asks: which file?")
        self.assertEqual(self.hub.advance(), [])  # nothing moves until Fred answers
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "calc.py HANDOFF-OK"}),
                         (200, {"session": sid}))
        self.hub.poll_once()
        self.hub.advance()
        self.assertEqual(self.hub.tasks[tid]["state"], "running")  # the answer is running
        task = self.until(tid, self.at(2), "the next step starts")
        self.assertEqual((task["steps"][0]["state"], task["steps"][0]["session"]), ("done", sid))

    def test_turn_cap_is_named_in_the_retry(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "MAXTURNS look"}])
        task = self.until(tid, lambda t: t["state"] == "stuck", "stuck after the retry")
        self.assertEqual(task["why"], "it hit the turn cap (15 turns) (after one retry)")  # a scout is read-capped

    def test_retry_sums_the_cost_of_both_attempts(self):
        tid = self.make_task(words="", steps=[{"kind": "scout", "goal": "look"}])  # no HANDOFF: retry, then stuck
        self.until(tid, lambda t: t["state"] == "stuck", "stuck after the retry")
        self.until(tid, lambda t: all(a["final"] for a in t["steps"][0]["attempts"]), "both costs in")
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual(len(step["attempts"]), 2)
        self.assertAlmostEqual(step["cost"], 0.02)
        row = next(r for r in self.hub.snapshot()["tasks"] if r["id"] == tid)
        self.assertEqual([a["session"] for a in row["steps"][0]["attempts"]], [a["session"] for a in step["attempts"]])
        self.assertAlmostEqual(row["cost"], 0.02)

    def test_stopped_step_gets_its_cost(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "SLOW look"}])
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.call("/api/task/stop", {"task": tid})
        self.wait_idle(sid)
        task = self.until(tid, lambda t: t["steps"][0]["attempts"][0]["final"], "the stopped run's cost")
        self.assertAlmostEqual(task["steps"][0]["cost"], 0.01)
        self.assertEqual(task["state"], "stopped")

    def test_clear_removes_every_attempt_stream(self):
        tid = self.make_task(words="", steps=[{"kind": "scout", "goal": "look"}])
        task = self.until(tid, lambda t: t["state"] == "stuck", "stuck after the retry")
        sids = [a["session"] for a in task["steps"][0]["attempts"]]
        self.assertEqual(len(sids), 2)
        for sid in sids:
            self.wait_idle(sid)
        self.assertEqual(self.call("/api/task/clear", {"task": tid})[0], 200)
        for sid in sids:
            self.assertFalse(self.hub.runs.stream_path(sid).exists(), sid)

    def test_stop_interrupts_the_step_never_kills(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "SLOW look"}])
        old = self.hub.tasks[tid]["steps"][0]["session"]
        self.assertEqual(self.call("/api/task/stop", {"task": tid}), (200, {"task": tid, "state": "stopped"}))
        self.wait_idle(old)
        self.assertIn("[Request interrupted", self.hub.runs.stream_path(old).read_text(encoding="utf-8"))
        task = self.hub.tasks[tid]
        self.assertEqual((task["state"], task["owner"], task["steps"][0]["state"]), ("stopped", "fred", "failed"))
        self.assertEqual(self.hub.advance(), [])
        self.assertEqual(self.call("/api/task/retry", {"task": tid}), (200, {"task": tid, "state": "running"}))
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual((step["state"], self.hub.tasks[tid]["owner"]), ("running", "service"))
        self.assertNotEqual(step["session"], old)
        self.assertIsNotNone(self.session(old))  # the old session row stays

    def test_pause_and_resume(self):
        tid = self.make_task(steps=self.TWO)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.assertEqual(self.call("/api/task/pause", {"task": tid}), (200, {"task": tid, "state": "running"}))
        self.assertEqual(self.hub.tasks[tid]["owner"], "fred")
        self.wait_idle(sid)
        self.until(tid, lambda t: t["steps"][0]["state"] == "done", "step 1 closed while paused")
        self.assertEqual(len([s for s in self.hub.tasks[tid]["steps"] if s["session"]]), 1)  # nothing after it
        self.assertEqual(self.call("/api/task/resume", {"task": tid}), (200, {"task": tid, "state": "running"}))
        self.until(tid, self.at(2), "step 2 starts")

    def test_pause_closes_an_ended_step(self):
        tid = self.make_task(steps=self.TWO)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.call("/api/task/pause", {"task": tid})
        self.wait_idle(sid)
        task = self.until(tid, lambda t: t["steps"][0]["state"] == "done", "step 1 closed while paused")
        self.assertEqual((task["owner"], task["steps"][1]["session"]), ("fred", ""))
        self.assertTrue((self.folder / "tasks" / tid / "steps" / "01-scout.md").exists())
        self.until(tid, lambda t: not t.get("briefing"), "the brief ran while paused")
        self.assertTrue((self.folder / "tasks" / tid / "steps" / "01-scout.brief.md").exists())
        self.assertEqual(self.hub.advance(), [])  # nothing starts while paused
        self.assertEqual(self.hub.tasks[tid]["steps"][1]["session"], "")
        row = next(r for r in self.hub.snapshot()["tasks"] if r["id"] == tid)
        self.assertEqual((row["paused_after"], row["hold"]), (1, False))
        self.call("/api/task/resume", {"task": tid})
        self.until(tid, self.at(2), "step 2 starts after Resume")

    def test_task_only_in_allowed_projects(self):
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        card = {"id": "20260101-000000-abcd", "project_dir": str(other), "raw": "x", "prompt": "x", "fields": {},
                "route": {}, "demand": {}, "steps": []}
        (self.folder / "preps").mkdir(parents=True, exist_ok=True)
        (self.folder / "preps" / f"{card['id']}.json").write_text(json.dumps(card), encoding="utf-8")
        status, _ = self.post_task(card, steps=self.TWO)
        self.assertEqual(status, 403)
        self.assertEqual(self.hub.tasks, {})
        self.assertEqual(self.call("/api/task", {"prep": "nope", "prompt": "x", "steps": []})[0], 404)

    def test_auto_steps_skip_task_sessions(self):
        tid = self.make_task(steps=self.TWO)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.wait_idle(sid)
        self.verdict(sid, "FAIL", "test_add - 3 != 4")
        self.assertEqual(self.hub.auto_steps(), [])  # the chain owns the verdicts of its steps

    def test_restart_resumes_the_chain(self):
        tid = self.make_task(steps=self.TWO)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.wait_idle(sid)
        again = server.Hub(self.hub.cfg, self.folder, self.hub.runs.exe)  # the service restarted
        again.user_home = self.hub.user_home
        again.poll_once()
        self.assertEqual(again.tasks[tid]["steps"][0]["state"], "running")  # as the old service left it
        end = time.time() + 25
        while time.time() < end and not again.tasks[tid]["steps"][1]["session"]:
            again.poll_once()
            again.advance()
            time.sleep(0.1)
        task = again.tasks[tid]
        self.assertEqual((task["steps"][0]["state"], bool(task["steps"][1]["session"])), ("done", True))
        while time.time() < end and (again.runs.live or again.briefing):  # let its run and brief end before cleanup
            time.sleep(0.1)

    def test_fable_needs_a_confirm(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "look", "model": "fable"}])
        task = self.hub.tasks[tid]
        self.assertEqual((task["state"], task["why"], task["steps"][0]["session"]), ("waiting", "confirm Fable", ""))
        levers_ = self.task(tid)[1]["levers"]
        self.assertEqual((levers_["start"], levers_["confirm"]), ("confirm Fable", ""))
        self.assertEqual(self.call("/api/task/confirm", {"task": tid}), (200, {"task": tid, "state": "running"}))
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual((step["state"], self.hub.runs.meta(step["session"])["model"]), ("running", "fable"))
        self.assertEqual(self.call("/api/task/confirm", {"task": tid})[0], 409)

    def test_budget_hold_waits_for_fred(self):
        self.hub.budget = self.over("opus")
        tid = self.make_task(steps=[{"kind": "design", "goal": "plan it PLAN-OK"}])  # over pace no longer moves a step
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual((step["model"], step["tier"], step["effort"]), ("opus", "opus", "high"))
        self.assertIn("balance: every think rung over pace -> opus 90 %", self.session(step["session"])["route_reason"])
        self.settled(tid)
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])  # its verify would run on opus: it holds
        task = self.until(tid, lambda t: t["state"] == "waiting", "the verify holds")
        self.assertEqual(task["why"], "opus over its pace")
        self.assertEqual([s["state"] for s in task["steps"]], ["done", "planned"])
        self.assertEqual(self.hub.advance(), [])  # it waits for Fred, it does not poll the budget

    def test_budget_hold_released_by_confirm(self):
        self.hub.budget = self.over("opus")
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])
        self.until(tid, lambda t: t["state"] == "waiting", "the verify holds")
        self.assertEqual(self.hub.task_levers(tid)["confirm"], "")
        self.assertTrue(next(r for r in self.hub.snapshot()["tasks"] if r["id"] == tid)["hold"])
        self.assertEqual(self.call("/api/task/confirm", {"task": tid})[0], 200)
        task = self.until(tid, self.at(2), "the verify starts")
        step = task["steps"][1]
        self.assertEqual(claude_cli.tier_of(step["model"]), "opus")
        self.assertIn("budget: hold released by Fred", step["notes"])
        self.assertNotIn("hold_ok", task)

    def test_counts_fold_task_steps_into_their_task(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "STOP-ASK look"}])
        self.until(tid, lambda t: t["state"] == "waiting", "the step asks")
        counts = self.hub.snapshot()["counts"]
        self.assertEqual((counts["needs"], counts["working"]), (1, 0))  # the task, not also its step session

    def test_counts_a_held_task_as_needs(self):
        self.hub.budget = self.over("opus")
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])
        self.until(tid, lambda t: t["state"] == "waiting" and not t.get("briefing"), "the verify holds")
        counts = self.hub.snapshot()["counts"]
        self.assertEqual((counts["needs"], counts["done"]), (1, 0))  # a hold needs Fred; its ended step is no row

    def test_a_step_that_asks_or_should_hand_off_needs_fred(self):
        # task.json still says running (the run has not ended), but the step's chat waits for Fred
        now, ids = time.time(), {}
        for sid, prompts, question in (("asks", 1, "which file?"), ("long", 3, "")):
            task = tasks.new_task(str(self.project), "proj", sid, "goal", tasks.plan_steps(
                [{"kind": "code", "goal": "write it"}], 6), "normal", {}, "", "auto", now)
            task.update(state="running", current=1)
            task["steps"][0].update(state="running", session=sid, model="sonnet", effort="high")
            self.hub.tasks[task["id"]] = ids[sid] = task
            events.append(self.folder, {"event": "run_started", "ts": now, "session_id": sid, "cwd": str(self.project),
                                        "project_dir": str(self.project),
                                        "task": task["id"], "step": 1, "kind": "task"})
            for k in range(prompts):
                events.append(self.folder, {"event": "UserPromptSubmit", "ts": now + k, "session_id": sid,
                                            "prompt": f"turn {k}"})
            events.append(self.folder, {"event": "Stop", "ts": now + 5, "session_id": sid,
                                        "stop_question": question})
        self.hub.poll_once()
        snap = self.hub.snapshot()
        rows = {r["id"]: r for r in snap["tasks"]}
        asks, long = rows[ids["asks"]["id"]], rows[ids["long"]["id"]]
        self.assertEqual((asks["group"], asks["asks"], asks["hand_off"]), ("needs", "which file?", ""))
        self.assertEqual((long["group"], long["asks"], long["hand_off"]), ("needs", "", "2 follow-ups"))
        self.assertEqual((snap["counts"]["needs"], snap["counts"]["working"]), (2, 0))  # steps not counted again
        page = self.task(ids["asks"]["id"])[1]
        # the Task page's answer and Hand off buttons ask Hub.levers: no run_ended yet, so not before it lands
        self.assertEqual(page["step_levers"]["continue"], "still working: wait until it stops")
        self.hub.tasks[ids["long"]["id"]]["state"] = "stopped"  # Fred stopped it: not his turn any more
        self.assertEqual(next(r for r in self.hub.snapshot()["tasks"] if r["id"] == ids["long"]["id"])["group"],
                         "done")

    def test_hand_off_of_an_asking_step_hands_the_task_over(self):
        skill = self.project / ".claude" / "skills" / "session-handoff"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        tid = self.make_task(steps=[{"kind": "scout", "goal": "STOP-ASK look"}, self.TWO[1]])
        self.until(tid, lambda t: t["state"] == "waiting", "the step asks")
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.assertEqual(self.hub.levers(sid)["handoff"], "")  # Hand off instead of an answer
        self.assertEqual(self.hub.task_levers(tid)["done"], "")
        self.assertEqual(self.call("/api/handoff", {"session": sid}), (200, {"session": sid}))
        task = self.hub.tasks[tid]
        self.assertEqual((task["state"], task["steps"][0]["state"], task["steps"][1]["state"]),
                         ("handed", "handed", "planned"))  # handed, not a checked step
        self.wait_idle(sid)
        self.hub.advance()
        self.assertEqual((task["state"], task["steps"][1]["state"]), ("handed", "planned"))  # nothing starts after
        self.assertEqual(self.session(sid)["kind"], "handoff")
        self.assertEqual(task["handoff_note"], "steps/01-handoff.md")  # the skill's last message, kept in the task
        self.assertIn("echo: /session-handoff", (self.folder / "tasks" / tid / "steps" / "01-handoff.md").read_text(
            encoding="utf-8"))
        self.assertIn(("handing", "handed"), [(c["from"], c["to"]) for c in self.chain(tid)])
        row = next(r for r in self.hub.snapshot()["tasks"] if r["id"] == tid)
        self.assertEqual((row["group"], row["handoff_note"], row["steps"][0]["note"]),
                         ("needs", "steps/01-handoff.md", "handed"))  # a pending handoff: Start next task
        page = self.task(tid)[1]
        self.assertIn("echo: /session-handoff", page["handoff"])
        status, seed = self.call(f"/api/brief?session={sid}&kind=next")
        self.assertEqual(status, 200)
        self.assertIn("echo: /session-handoff", seed["text"])  # the next task starts from the handoff note
        self.assertEqual(self.hub.advance(), [])  # written once
        self.assertEqual(self.call("/api/task/done", {"task": tid}), (200, {"task": tid, "state": "done"}))
        row = next(r for r in self.hub.snapshot()["tasks"] if r["id"] == tid)
        self.assertEqual((row["group"], row["steps"][0]["state"]), ("done", "handed"))
        self.assertEqual(self.call("/api/task/done", {"task": tid}), (409, {"error": "task is done"}))

    def test_nothing_written_outside_home(self):
        tid = self.make_task(steps=self.TWO)
        self.settled(tid)
        self.assertEqual(list(self.project.iterdir()), [])  # the fake claude writes no file, and nor does the service
        folder = self.folder / "tasks" / tid
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["chain.jsonl", "prompt.md", "steps", "task.json"])

    def test_done_task_is_cleared(self):
        tid = self.make_task(steps=self.TWO)
        self.settled(tid)
        sids = [s["session"] for s in self.hub.tasks[tid]["steps"]]
        self.assertEqual(len(sids), 2)
        for sid in sids:
            self.assertFalse(self.hub.runs.stream_path(sid).exists())
            self.assertFalse(self.hub.runs.meta_path(sid).exists())
        folder = self.folder / "tasks" / tid
        self.assertEqual(sorted(p.name for p in (folder / "steps").iterdir()),
                         ["02-explain.brief.md", "02-explain.facts.md", "02-explain.md"])  # the last note, its brief and facts
        saved = tasks.load(self.folder, tid)
        self.assertTrue(saved["cleared"])
        self.assertEqual((saved["state"], saved["steps"][0]["handoff"], saved["steps"][1]["handoff"]),
                         ("done", "", "steps/02-explain.md"))
        last = self.chain(tid)[-1]
        self.assertEqual((last["from"], last["to"]), ("task:done", "task:cleared"))
        self.assertIsNotNone(self.session(sids[0]))  # the session rows (the event log) stay

    def test_done_task_stays_whole_without_the_setting(self):
        self.hub.cfg["task_clear_on_done"] = False
        tid = self.make_task(steps=self.TWO)
        self.settled(tid)
        sids = [s["session"] for s in self.hub.tasks[tid]["steps"]]
        self.assertTrue(all(self.hub.runs.stream_path(sid).exists() for sid in sids))
        self.assertIn("01-scout.md", [p.name for p in (self.folder / "tasks" / tid / "steps").iterdir()])
        self.assertFalse(self.hub.tasks[tid].get("cleared"))

    def test_clear_removes_a_stuck_task(self):
        tid = self.make_task(words="", steps=self.TWO)
        self.assertEqual(self.call("/api/task/clear", {"task": tid})[0], 409)  # running
        task = self.until(tid, lambda t: t["state"] == "stuck", "the task is stuck")
        sid = task["steps"][0]["session"]
        self.wait_idle(sid)
        self.assertEqual(self.call("/api/task/clear", {"task": tid}), (200, {"task": tid, "state": "cleared"}))
        self.assertFalse((self.folder / "tasks" / tid).exists())
        self.assertFalse(self.hub.runs.stream_path(sid).exists())
        self.assertEqual([t["id"] for t in self.hub.snapshot()["tasks"]], [])
        self.assertEqual(self.call("/api/task/clear", {"task": tid})[0], 404)

    def test_brief_runs_between_steps(self):
        tid = self.make_task(steps=self.TWO)
        self.until(tid, lambda t: t.get("briefing") == 1, "step 1 is briefed")
        row = self.hub.snapshot()["tasks"][0]
        self.assertEqual((row["id"], row["briefing"]), (tid, 1))
        task = self.until(tid, self.at(2), "step 2 starts")
        brief_file = self.folder / "tasks" / tid / "steps" / "01-scout.brief.md"
        text = brief_file.read_text(encoding="utf-8")
        for heading in tasks.HEADINGS:
            self.assertIn(heading, text)
        self.assertLess(len(text.split()), 400)
        self.assertIn("test_add covers it", text)  # the Haiku pass wrote it, not the code fallback
        brief_lines = [c["why"] for c in self.chain(tid) if c["why"].startswith("brief")]
        self.assertEqual(len(brief_lines), 1)
        self.assertRegex(brief_lines[0], r"^brief: \d+ -> \d+ words, \$0\.0\d$")
        prompt = self.prompt_of(task["steps"][1]["session"])
        self.assertIn("test_add covers it", prompt)  # step 2 reads the brief ...
        self.assertNotIn("# Step 01:", prompt)  # ... and not the raw note

    def test_brief_is_the_code_fallback_when_off(self):
        self.hub.cfg["brief_on"] = False
        with mock.patch.object(server.compact, "run_brief", side_effect=AssertionError("no second claude")) as ask:
            tid = self.make_task(steps=self.TWO)
            task = self.until(tid, self.at(2), "step 2 starts")
        self.assertEqual(ask.call_count, 0)
        text = (self.folder / "tasks" / tid / "steps" / "01-scout.brief.md").read_text(encoding="utf-8")
        self.assertIn("add() is in calc.py:2", text)
        self.assertNotIn("test_add covers it", text)
        self.assertTrue(any(c["why"].startswith("brief fallback:") for c in self.chain(tid)))
        self.assertNotIn("# Step 01:", self.prompt_of(task["steps"][1]["session"]))

    def test_brief_fallback_never_blocks_the_chain(self):
        # the brief request holds the next step's goal, so HUGE goes in step 2's
        tid = self.make_task(steps=[self.TWO[0], {"kind": "explain", "goal": "say it HUGE"}])
        task = self.until(tid, self.at(2), "step 2 starts")
        self.assertIn("brief fallback: over 500 words", [c["why"] for c in self.chain(tid)])
        text = (self.folder / "tasks" / tid / "steps" / "01-scout.brief.md").read_text(encoding="utf-8")
        self.assertIn("add() is in calc.py:2", text)
        self.assertEqual(task["steps"][1]["state"], "running")

    def test_a_long_brief_is_cut_not_dropped(self):
        tid = self.make_task(steps=[self.TWO[0], {"kind": "explain", "goal": "say it LONG"}])
        self.until(tid, self.at(2), "step 2 starts")
        whys = [c["why"] for c in self.chain(tid)]
        self.assertTrue(any(w.startswith("brief: ") and ", cut " in w and w.endswith(" findings") for w in whys), whys)
        self.assertFalse(any(w.startswith("brief fallback") for w in whys))

    def test_task_snapshot_and_get(self):
        tid = self.make_task()
        row = next(t for t in self.hub.snapshot()["tasks"] if t["id"] == tid)
        for key in ("id", "title", "project", "project_dir", "state", "owner", "current", "count", "why", "updated",
                    "effort", "cost", "route", "steps"):
            self.assertIn(key, row)
        self.assertEqual((row["project"], row["state"], row["owner"], row["current"], row["count"], row["route"]),
                         ("proj", "running", "service", 1, 3, "haiku/low"))
        self.assertEqual([(s["n"], s["kind"], s["state"]) for s in row["steps"]],
                         [(1, "scout", "running"), (2, "code", "planned"), (3, "verify", "planned")])
        self.assertEqual(sorted(row["steps"][0]), sorted(["n", "kind", "state", "model", "effort", "session",
                                                          "verdict", "retries", "cost", "note", "attempts", "part", "hard",
                                                          "end_commit", "brief_meta", "facts"]))
        self.assertIn(row["steps"][0]["note"], ("writing", "unchecked"))
        self.until(tid, self.at(2), "step 2 starts")
        steps = next(t for t in self.hub.snapshot()["tasks"] if t["id"] == tid)["steps"]
        self.assertEqual(steps[0]["note"], "sent")
        self.assertIn(steps[1]["note"], ("writing", "unchecked"))
        status, data = self.task(tid)
        self.assertEqual(status, 200)
        self.assertEqual(data["task"]["id"], tid)
        self.assertEqual(data["levers"]["route"], "sonnet/medium")
        self.assertEqual(data["levers"]["start"], "a step is running")
        self.assertIn("## Findings\nadd() is in calc.py:2", data["note"])
        self.assertIn("test_add covers it", data["brief"])
        self.assertEqual((list(data["notes"]), list(data["briefs"]), list(data["facts"])), (["1"], ["1"], ["1"]))
        self.assertEqual(data["notes"]["1"], data["note"])  # plan 23: every step's texts, keyed by its number
        self.assertEqual(self.task("../x")[0], 404)
        self.assertEqual(self.task("20260101-000000-ffff")[0], 404)

    def test_balance_spreads_a_tier(self):
        """Plan 18: a write tier of two Claude rungs; the emptiest model runs, its verify one rank above it."""
        self.hub.cfg["tiers"] = dict(self.hub.cfg["tiers"], write=[{"rung": "sonnet", "effort": "auto"},
                                                                   {"rung": "claude-haiku-4-5", "effort": "auto"}])
        self.hub.budget = lambda: {"sonnet": {"share": 0.9, "binding": "week"}, "haiku": {"share": 0.2, "binding": "day"}}
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual((step["model"], step["tier"]), ("claude-haiku-4-5", "haiku"))
        self.assertEqual(self.hub.runs.meta(step["session"])["model"], "claude-haiku-4-5")
        self.assertIn("balance: sonnet 90 % -> claude-haiku-4-5 20 %", step["notes"])
        task = self.until(tid, lambda t: t["state"] == "waiting", "the verify holds")
        self.assertEqual(task["why"], "sonnet over its pace")  # haiku's code is checked on sonnet, over its pace

    def test_a_hard_design_step_on_fable_waits_for_the_confirm(self):
        """Plan 18: fable is hard only in think; when the balance picks it, the Fable confirm still holds the step."""
        self.hub.budget = lambda: {"opus": {"share": 0.9, "binding": "day"}, "fable": {"share": 0.1, "binding": "day"}}
        tid = self.make_task(text="THINK plan it", steps=[{"kind": "design", "goal": "plan it"}])  # reasoning high
        task = self.until(tid, lambda t: t["state"] == "waiting", "the fable step waits")
        self.assertEqual((task["why"], task["steps"][0]["state"]), ("confirm Fable", "planned"))
        self.assertEqual(self.call("/api/task/confirm", {"task": tid})[0], 200)
        task = self.until(tid, self.at(1), "the design step starts")
        self.assertEqual((task["steps"][0]["model"], task["steps"][0]["tier"]), ("fable", "fable"))

    def test_budget_reads_the_usage_days(self):
        today = usage.day_of(time.time())
        self.assertEqual(self.hub.budget(), {})  # usage not read yet: the tiers' order routes
        self.hub.cfg["allowances"] = {"opus": {"day_usd": 10, "week_usd": 50, "month_usd": 150}}
        with self.hub.lock:
            self.hub.usage_days = {today: {"cost": 5.0, "tokens": [0, 0, 0, 0], "projects": {}, "models": {"opus": 5.0}}}
            self.hub.usage_ready = True
        fill = self.hub.budget()["opus"]
        self.assertEqual((fill["day"]["used_usd"], fill["day"]["allowance_usd"]), (5.0, 10.0))
        self.assertIn(fill["binding"], ("day", "week", "month"))
        self.assertEqual(fill["via"], ["claude"])
        self.assertIsNone(self.hub.budget()["sonnet"]["share"])  # no allowance
        data = self.call("/api/usage")[1]
        self.assertEqual((data["fills"]["opus"]["day"]["used_usd"], data["fail_hours"], data["warn_at"]), (5.0, {}, 0.8))
        cfg = self.call("/api/config")[1]
        self.assertEqual(cfg["kinds_tier"]["design"], "think")
        self.assertEqual(cfg["kinds_tier"]["scout"], "read")
        think = {r["rung"]: r for r in cfg["tiers"]["think"]}
        self.assertEqual((think["opus"]["why"], think["opus"]["key"], think["fable"]["hard"]), ("", "opus", True))
        self.assertNotEqual(think["codex:gpt-6-astra"]["why"], "")  # codex is not usable here

    def test_runs_of_another_harness_count_once(self):
        sid, ts = "0000-codex", time.time()
        self.hub.runs.runs.mkdir(parents=True, exist_ok=True)
        self.hub.runs.meta_path(sid).write_text(json.dumps({"harness": "codex", "model": "gpt-6.1-sol"}), encoding="utf-8")
        self.hub.cfg["prices"] = dict(self.hub.cfg["prices"], **{"gpt-6.1-sol": {"input": 2, "output": 10, "cache_read": 0.2}})
        rec = {"event": "run_ended", "session_id": sid, "ts": ts,
               "tokens": {"input": 1_000_000, "output": 100_000, "cache_read": 0}}
        self.assertTrue(self.hub.count_run(rec))
        self.assertFalse(self.hub.count_run(rec))  # a restart replays the line: counted once
        row = self.hub.usage_other[usage.day_of(ts)]["gpt-6.1-sol"]
        self.assertEqual((row["cost"], row["runs"], row["unknown"]), (3.0, 1, 0))
        self.assertTrue(self.hub.count_run(dict(rec, ts=ts + 1, tokens=None)))  # no usage: unknown, never zero
        self.assertEqual(self.hub.usage_other[usage.day_of(ts)]["gpt-6.1-sol"]["unknown"], 1)
        self.hub.runs.meta_path("0000-claude").write_text(json.dumps({"model": "sonnet"}), encoding="utf-8")
        self.assertFalse(self.hub.count_run(dict(rec, session_id="0000-claude")))  # the transcripts price Claude
        today = self.hub.snapshot()["spend"]
        self.assertEqual(today["fills"]["over"], [])

    def test_models_page_saves_to_config_json(self):
        """Plan 26: POST /api/config/models writes the checked keys, keeps every other key, and the hub uses them."""
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["kind_pins"], cfg["tuning"]["task_max_steps"]["value"]), ({}, 6))
        self.assertEqual(cfg["tuning"]["balance_margin"], {"value": 0.1, "default": 0.1, "min": 0, "max": 0.5,
                                                           "unit": "share", "group": "balancing"})
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "config.json").write_text(json.dumps({"projects": [str(self.project)], "port": 47770,
                                                             "tiers": {"write": ["sonnet"]}}), encoding="utf-8")
        status, data = self.call("/api/config/models", {"changes": {
            "task_max_steps": 8, "balance_margin": 0.15, "tiers": {"read": ["haiku", "claude-haiku-4-5"]},
            "kinds": {"test": {"rung": "auto", "effort": "medium"}}, "allowances": {"opus": {"day_usd": 12}}}})
        self.assertEqual(status, 200, data)
        self.assertEqual((data["tuning"]["task_max_steps"]["value"], data["kind_pins"]),
                         (8, {"test": {"rung": "auto", "effort": "medium"}}))
        written = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.assertEqual((written["projects"], written["port"], written["task_max_steps"]), ([str(self.project)], 47770, 8))
        self.assertEqual(written["tiers"], {"write": ["sonnet"], "read": [{"rung": "haiku", "effort": "auto"},
                                                                         {"rung": "claude-haiku-4-5", "effort": "auto"}]})
        self.assertEqual((self.hub.cfg["task_max_steps"], self.hub.cfg["balance_margin"]), (8, 0.15))
        self.assertEqual([r["rung"] for r in data["tiers"]["read"]], ["haiku", "claude-haiku-4-5"])
        self.assertEqual(len(self.hub.cfg["tiers"]["think"]), len(paths.DEFAULTS["tiers"]["think"]))  # untouched tier
        self.assertEqual(self.hub.cfg["allowances"], {"opus": {"day_usd": 12}})

    def test_models_page_reload_shows_a_hand_edit(self):
        """Plan 26 README 3.1: a hand edit of config.json shows on the page after Reload (GET /api/config)."""
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / "config.json"
        path.write_text(json.dumps({"projects": [str(self.project)], "port": 47770}), encoding="utf-8")
        self.call("/api/config")
        path.write_text(json.dumps({"projects": [str(self.project)], "port": 1, "brief_max_words": 450}),
                        encoding="utf-8")
        os.utime(path, (time.time() + 5, time.time() + 5))
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["tuning"]["brief_max_words"]["value"], self.hub.cfg["brief_max_words"]), (450, 450))
        self.assertNotEqual(self.hub.cfg["port"], 1)  # only the page's keys are reread

    def test_models_page_refuses_with_reasons(self):
        before = self.hub.cfg["task_max_steps"]
        status, data = self.call("/api/config/models", {"changes": {"task_max_steps": 99, "port": 1}})
        self.assertEqual(status, 400)
        self.assertEqual(data["errors"], {"task_max_steps": "between 1 and 12", "port": "not a setting this page changes"})
        self.assertIn("task_max_steps: between 1 and 12", data["error"])
        self.assertEqual(self.hub.cfg["task_max_steps"], before)
        self.assertFalse((self.folder / "config.json").exists() and
                         "task_max_steps" in json.loads((self.folder / "config.json").read_text(encoding="utf-8")))
        self.assertEqual(self.call("/api/config/models", {"changes": []})[0], 400)
        self.assertEqual(self.call("/api/config/models", {"other": 1})[0], 400)
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "config.json").write_text("{ broken", encoding="utf-8")
        status, data = self.call("/api/config/models", {"changes": {"task_max_steps": 7}})
        self.assertEqual(status, 409)
        self.assertIn("fix it by hand", data["error"])
        self.assertEqual((self.folder / "config.json").read_text(encoding="utf-8"), "{ broken")  # never overwritten

    def test_a_pinned_kind_routes_its_steps(self):
        status, data = self.call("/api/config/models", {"changes": {"kinds": {"code": {"rung": "claude-haiku-4-5",
                                                                                         "effort": "low"}}}})
        self.assertEqual(status, 200, data)
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])
        step = self.hub.tasks[tid]["steps"][0]
        self.assertEqual((step["model"], step["tier"], step["effort"]), ("claude-haiku-4-5", "haiku", "low"))
        self.assertIn("pin code: claude-haiku-4-5", step["notes"])
        self.assertIn("pin effort: low", step["notes"])

    def test_get_task_carries_plan_parts_and_step_part(self):
        """The window contract (plan 24 Task 4): GET /api/task has the plan text, the parts by number and the
        step's part and hard; the snapshot row (task_row) has the plan meta and each step's part and hard."""
        self.hub.cfg["plan_hold"] = True
        tid = self.make_task(words="HANDOFF-OK PLAN-SPLIT",
                             steps=[{"kind": "scout", "goal": "look"}, {"kind": "design", "goal": "plan it"},
                                    {"kind": "code", "goal": "write"}, {"kind": "verify", "goal": "check"}])
        self.until(tid, lambda t: t["state"] == "waiting" and t["why"] == "plan ready: confirm", "the plan waits")
        data = self.task(tid)[1]
        self.assertIn("## Sub-plans", data["plan"])
        self.assertEqual(sorted(data["parts"]), ["1", "2"])
        self.assertIn("calc.py", data["parts"]["1"])
        meta = data["task"]["plan"]
        self.assertEqual([p["n"] for p in meta["parts"]], [1, 2])
        self.assertEqual([s.get("part", 0) for s in data["task"]["steps"] if s["kind"] == "code"], [1, 2])
        row = next(t for t in self.hub.snapshot()["tasks"] if t["id"] == tid)
        self.assertEqual(row["plan"]["from"], meta["from"])
        self.assertEqual([(s["part"], s["hard"]) for s in row["steps"] if s["kind"] == "code"], [(1, False), (2, True)])

    def test_a_rung_can_be_run_by_hand(self):
        run = {"project_dir": str(self.project), "prompt": "fix add", "effort": "low"}
        status, data = self.call("/api/run", dict(run, model="claude-haiku-4-5"))
        self.assertEqual(status, 200)
        self.assertEqual(self.hub.runs.meta(data["session"])["model"], "claude-haiku-4-5")
        self.assertEqual(self.call("/api/run", dict(run, model="claude-haiku-3"))[0], 400)
        self.assertEqual(self.call("/api/config")[1]["ladder"]["haiku"], ["haiku", "claude-haiku-4-5"])
        self.wait_idle(data["session"])

    def test_usage_reports_storage(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix add"})[1]["session"]
        self.wait_idle(sid)
        self.hub.read_history()
        data = self.call("/api/usage")[1]
        self.assertGreater(data["storage"]["runs"], 0)
        self.assertGreaterEqual(data["storage"]["total"], data["storage"]["runs"])
        self.assertEqual(sorted(data["storage"]), ["events", "other", "preps", "runs", "tasks", "total"])
        self.assertEqual(data["storage_warn_mb"], 500)

    def test_draft_keeps_board_tab_and_folds(self):
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["board_tab"], cfg["folds"]), ("chat", {}))
        self.assertEqual(self.call("/api/draft", {"text": "", "board_tab": "hand", "folds": {"b.facts": True}})[0], 200)
        cfg = self.call("/api/config")[1]
        self.assertEqual((cfg["board_tab"], cfg["folds"]), ("hand", {"b.facts": True}))
        for bad in ({"board_tab": "notes"}, {"folds": {"B.X": True}}, {"folds": {"b.x": "yes"}}, {"folds": [1]},
                    {"folds": {f"k{i}": True for i in range(65)}}):
            self.assertEqual(self.call("/api/draft", dict(bad, text=""))[0], 400, bad)

    def test_draft_keeps_the_effort(self):
        self.assertEqual(self.call("/api/config")[1]["effort"], "auto")
        self.assertEqual(self.call("/api/draft", {"text": "", "effort": "max"}), (200, {"ok": True}))
        config = self.call("/api/config")[1]
        self.assertEqual((config["effort"], config["kinds"]), ("max", list(tasks.PREP_KINDS)))
        self.assertEqual(config["edit_kinds"], sorted(tasks.EDIT_KINDS))
        self.assertIs(config["handoff_auto"], False)
        self.assertEqual(self.call("/api/draft", {"text": "", "effort": "turbo"})[0], 400)
        self.assertEqual(self.call("/api/draft", {"text": "", "effort": "auto"})[0], 200)
        self.assertEqual(self.call("/api/config")[1]["effort"], "auto")

    # -- review fixes (2026-10-12) ---------------------------------------------------------------------------
    def loose_task(self, title="Loose"):
        """A task put in the hub by hand (not through a card): one scout step, planned."""
        task = tasks.new_task(str(self.project), "proj", title, "goal", tasks.plan_steps(
            [{"kind": "scout", "goal": "look"}], 6), "normal", {}, "", "auto", time.time())
        self.hub.tasks[task["id"]] = task
        return task

    def test_a_broken_task_never_stops_the_hub(self):
        broken = self.loose_task("Broken")
        del broken["steps"][0]["pick"]  # a bug, or a task.json from another version
        self.assertEqual(self.hub.advance(), [(broken["id"], "stuck")])
        self.assertEqual(broken["state"], "stuck")
        self.assertTrue(broken["why"].startswith("KeyError"), broken["why"])
        self.assertEqual(self.hub.advance(), [])  # a stuck task is left for Fred
        self.assertTrue(any(t["id"] == broken["id"] for t in self.hub.snapshot()["tasks"]))
        tid = self.make_task(steps=self.TWO)
        with mock.patch.object(server.tasks, "save", side_effect=PermissionError(13, "in use")):
            task = self.until(tid, lambda t: t["state"] == "stuck", "a failed save makes the task stuck")
        self.assertIn("PermissionError", task["why"])

    def test_verdict_and_question_come_from_the_reply(self):
        """No Stop event here (the hook is async and may land after run_ended): the chain reads the reply."""
        tid = self.make_task(steps=[{"kind": "code", "goal": "write it"}])
        self.hub.tasks[tid]["steps"][1]["goal"] += " VERDICT-PASS"
        task = self.settled(tid)
        self.assertEqual((task["steps"][1]["verdict"], task["steps"][1]["retries"]), ("PASS", 0))
        tid = self.make_task(steps=[{"kind": "scout", "goal": "look STOP-ASK"}, self.TWO[1]])
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits")
        self.assertEqual(task["why"], "asks: which file?")
        lines = len(self.chain(tid))
        self.assertEqual(self.hub.advance(), [])
        self.assertEqual(len(self.chain(tid)), lines)  # waiting writes nothing more

    def test_a_denial_does_not_fail_a_finished_step(self):
        tid = self.make_task(steps=self.TWO)
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        events.append(self.folder, {"event": "PermissionDenied", "ts": time.time(), "session_id": sid,
                                    "tool": "Bash", "what": "git push", "reason": "[Push]"})
        task = self.until(tid, self.at(2), "step 2 starts")
        self.assertEqual((task["steps"][0]["session"], task["steps"][0]["retries"]), (sid, 0))

    def test_session_levers_leave_task_steps_to_the_chain(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "look STOP-ASK"}, self.TWO[1]])
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.until(tid, lambda t: t["state"] == "waiting", "the task waits")
        skill = self.hub.user_home / ".claude" / "skills" / "session-handoff"  # Hand off needs the skill here
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# session-handoff\n", encoding="utf-8")
        lv = self.hub.levers(sid)
        self.assertEqual(lv["continue"], "")  # Fred answers the step's question here
        self.assertEqual(lv["handoff"], "")  # a question leaves Hand off open too
        for lever in ("verify", "escalate", "deescalate"):
            self.assertEqual(lv[lever], "a task step: use the task's levers", lever)
        self.assertEqual(self.call("/api/verify", {"session": sid})[0], 409)
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "calc.py HANDOFF-OK"})[0], 200)
        self.until(tid, self.at(2), "the next step starts")
        self.assertEqual(self.hub.levers(sid)["continue"], "a task step: use the task's levers")

    def test_session_stop_stops_the_task(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "SLOW look"}])
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.assertEqual(self.call("/api/stop", {"session": sid}), (200, {"stop": "stopped", "task": tid}))
        self.wait_idle(sid)
        task = self.hub.tasks[tid]
        self.assertEqual((task["state"], task["owner"], task["steps"][0]["retries"]), ("stopped", "fred", 0))
        self.assertEqual(self.hub.advance(), [])  # no retry: Fred stopped it

    def test_continue_on_the_stopped_step_resumes_the_task(self):
        tid = self.make_task(steps=[self.TWO[0], {"kind": "code", "goal": "fix it SLOW"},
                                   {"kind": "explain", "goal": "say what changed"}])
        task = self.until(tid, self.at(2), "step 2 runs")
        sid = task["steps"][1]["session"]
        self.assertEqual(self.call("/api/stop", {"session": sid}), (200, {"stop": "stopped", "task": tid}))
        self.wait_idle(sid)
        self.hub.poll_once()
        self.assertEqual((task["state"], task["owner"], task["steps"][1]["state"]), ("stopped", "fred", "failed"))
        self.assertEqual(self.hub.levers(sid)["continue"], "")
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "found it in calc.py HANDOFF-OK"}),
                         (200, {"session": sid}))
        step = task["steps"][1]
        self.assertEqual((task["state"], task["owner"], step["state"], step["session"]),
                         ("running", "service", "running", sid))  # the same session, resumed
        task = self.until(tid, self.at(3), "step 3 starts")
        self.assertEqual((step["state"], step["handoff"], step["retries"], task["last_good"]),
                         ("done", "steps/02-code.md", 0, 2))
        self.assertNotEqual(task["steps"][2]["session"], sid)
        moves = [(c["step"], c["from"], c["to"], c["why"]) for c in self.chain(tid)]
        self.assertIn((2, "failed", "running", "continued by Fred"), moves)
        self.assertIn((2, "running", "done", ""), moves)
        task = self.until(tid, lambda t: t["steps"][1]["attempts"][-1]["final"], "both turns' cost")
        self.assertAlmostEqual(task["steps"][1]["cost"], 0.02)  # one session, two turns, counted once

    def test_continue_on_a_stopped_step_still_live_is_refused(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "SLOW look"}])
        task = self.hub.tasks[tid]
        sid = task["steps"][0]["session"]
        tasks.fred(task, "stop", time.time())  # stopped, and the interrupt has not ended the run yet
        self.assertEqual(self.hub.levers(sid)["continue"], "still working: wait until it stops")
        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "go on HANDOFF-OK"}),
                         (409, {"error": "still working: wait until it stops"}))
        self.assertEqual((task["state"], task["owner"]), ("stopped", "fred"))
        self.hub.runs.stop(sid)
        self.wait_idle(sid)

    def test_stop_and_clear_need_no_allowed_project(self):
        tid = self.make_task(steps=[{"kind": "scout", "goal": "SLOW look"}])
        sid = self.hub.tasks[tid]["steps"][0]["session"]
        self.hub.cfg["projects"] = []  # Fred took the project off the list mid-task
        self.assertTrue(self.task(tid)[1]["levers"]["retry"].startswith("runs are off"))
        self.assertEqual(self.call("/api/task/stop", {"task": tid}), (200, {"task": tid, "state": "stopped"}))
        self.wait_idle(sid)
        self.assertEqual(self.call("/api/task/retry", {"task": tid})[0], 409)
        self.assertEqual(self.call("/api/task/clear", {"task": tid}), (200, {"task": tid, "state": "cleared"}))
        planned = self.loose_task("Never ran")
        self.hub.advance()
        self.assertEqual(planned["state"], "planned")  # it cannot start here
        self.assertEqual(self.call("/api/task/clear", {"task": planned["id"]})[0], 200)  # README 3.7: not running

    # -- plan 24 Task 3: the plan, its waits, the replan step -------------------------------------------------

    def plan_task(self, words="HANDOFF-OK PLAN-OK", kinds=("scout", "design", "code", "test"), goals=None):
        goals = goals or {}
        steps = [{"kind": k, "goal": goals.get(i + 1, f"do {k}")} for i, k in enumerate(kinds)]
        status, data = self.post_task(self.prep_card(), words=words, steps=steps)
        self.assertEqual(status, 200, data)
        return data["task"]

    def full_prompt(self, sid):  # the chat view cuts a long prompt; the run keeps it whole
        for line in self.hub.runs.stream_path(sid).read_text(encoding="utf-8").splitlines():
            if '"cc_prompt"' in line:
                return json.loads(line)["text"]
        self.fail("no cc_prompt line")

    def whys(self, tid):
        return [c["why"] for c in self.chain(tid)]

    def test_design_step_saves_the_plan_and_the_next_step_reads_it(self):
        tid = self.plan_task()
        task = self.until(tid, self.at(3), "step 3 starts")
        folder = self.folder / "tasks" / tid
        self.assertIn("## Goal", (folder / "plan.md").read_text(encoding="utf-8"))
        self.assertEqual(task["plan"]["from"], 2)
        self.assertGreater(task["plan"]["words"], 0)
        self.assertTrue(any(w.startswith("plan saved: ") for w in self.whys(tid)))
        prompt = self.full_prompt(task["steps"][2]["session"])
        self.assertIn("The plan (follow it, do not change it):", prompt)
        self.assertIn("Your part of the plan:\n### Step 3: code", prompt)
        self.assertRegex(task["steps"][2]["notes"][-1], r"^read: brief 02 · plan [\d.]+ KB · step 3 section$")
        row = next(t for t in self.hub.snapshot()["tasks"] if t["id"] == tid)
        self.assertEqual(row["plan"]["from"], 2)
        self.assertEqual(self.task(tid)[1]["plan"], (folder / "plan.md").read_text(encoding="utf-8"))

    def test_design_step_reads_the_raw_notes_whole(self):
        tid = self.plan_task()
        task = self.until(tid, self.at(2), "the design step starts")
        prompt = self.full_prompt(task["steps"][1]["session"])
        self.assertIn("add() is in calc.py:2", prompt)
        self.assertIn("You are the design step", prompt)
        self.assertEqual(task["steps"][1]["notes"][-1], "read: notes 01-01")

    def test_design_step_has_the_design_turn_cap(self):
        tid = self.plan_task()
        task = self.until(tid, self.at(2), "the design step starts")
        self.assertEqual(self.hub.runs.meta(task["steps"][1]["session"])["limits"]["max_turns"],
                         self.hub.cfg["design_max_turns"])
        self.hub.tasks[tid]["steps"][1]["pick"] = "sonnet"  # on any rung
        self.hub.tasks[tid]["steps"][1]["state"] = "planned"
        self.hub.tasks[tid]["steps"][1]["session"] = ""
        self.hub.tasks[tid]["current"] = 1
        self.hub.tasks[tid]["steps"][0]["state"] = "done"
        self.hub.start_step(self.hub.tasks[tid], 2)
        self.assertEqual(self.hub.runs.meta(self.hub.tasks[tid]["steps"][1]["session"])["limits"]["max_turns"],
                         self.hub.cfg["design_max_turns"])

    def test_split_plan_rebuilds_the_write_steps(self):
        tid = self.plan_task(words="HANDOFF-OK PLAN-SPLIT")
        task = self.until(tid, self.at(4), "step 4 starts")
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout", "design", "code", "code", "verify", "test"])
        self.assertEqual(task["steps"][4]["checked"], 4)
        folder = self.folder / "tasks" / tid
        self.assertTrue((folder / "plan" / "01-calc-module.md").is_file())
        self.assertTrue((folder / "plan" / "02-report-module.md").is_file())
        self.assertIn("design split into 2 sub-plans: 2 code steps (Prep had 1)", self.whys(tid))
        self.assertIn("Your part of the plan:\n# Part 2: Report module", self.full_prompt(task["steps"][3]["session"]))
        self.assertEqual([(s["part"], s["hard"]) for s in self.task(tid)[1]["task"]["steps"][2:4]],
                         [(1, False), (2, True)])

    def test_bad_plan_retries_then_sticks(self):
        tid = self.plan_task(words="HANDOFF-OK PLAN-BAD")
        task = self.until(tid, lambda t: t["state"] == "stuck", "the task is stuck")
        self.assertEqual(task["steps"][1]["retries"], 1)
        self.assertEqual(task["why"], "plan: missing: ## Acceptance (after one retry)")
        self.assertNotIn("plan", task)

    def test_plan_over_the_size_waits(self):
        self.hub.cfg["plan_max_kb"] = 0.3
        tid = self.plan_task()
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits on the size")
        self.assertTrue(task["why"].startswith("plan ") and " KB, over 0.3" in task["why"], task["why"])
        self.assertEqual(self.task(tid)[1]["levers"]["redo"], "")
        self.assertEqual(self.call("/api/task/confirm", {"task": tid})[0], 200)
        self.until(tid, self.at(3), "step 3 starts")
        self.assertIn("plan accepted by Fred", self.whys(tid))
        other = self.plan_task()  # a second task: Redo design plans again
        task = self.until(other, lambda t: t["state"] == "waiting", "the second task waits")
        why = task["why"]
        self.assertEqual(self.call("/api/task/redo", {"task": other})[0], 200)
        task = self.hub.tasks[other]
        self.assertEqual(task["redo"], why)
        self.assertEqual(task["steps"][1]["retries"], 0)
        self.hub.cfg["plan_max_kb"] = 100
        task = self.until(other, self.at(3), "step 3 starts after the redo")
        self.assertNotIn("redo", task)

    def test_plan_hold_waits_for_confirm(self):
        self.hub.cfg["plan_hold"] = True
        tid = self.plan_task()
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task holds")
        self.assertEqual(task["why"], "plan ready: confirm")
        text = (self.folder / "tasks" / tid / "plan.md").read_text(encoding="utf-8")
        edited = text.replace("## Out of scope", "- Fred, 2026-10-14: use ints\n\n## Out of scope", 1)
        status, data = self.call("/api/task/plan", {"task": tid, "text": edited})
        self.assertEqual(status, 200, data)
        self.assertIn("Fred, 2026-10-14: use ints", (self.folder / "tasks" / tid / "plan.md").read_text(encoding="utf-8"))
        status, data = self.call("/api/task/plan", {"task": tid, "text": text.replace("## Goal", "## Aim")})
        self.assertEqual((status, data["error"]), (409, "plan: missing: ## Goal"))
        self.assertEqual(self.call("/api/task/plan", {"task": tid, "text": "x", "part": -1})[0], 400)
        self.assertEqual(self.call("/api/task/confirm", {"task": tid})[0], 200)
        task = self.until(tid, self.at(3), "step 3 starts")
        self.assertIn("plan confirmed by Fred", self.whys(tid))
        self.assertEqual(self.call("/api/task/plan", {"task": tid, "text": text})[0], 409)  # running: no edit

    def test_plan_gap_waits_and_the_answer_joins_decisions(self):
        tid = self.plan_task(goals={3: "write it PLAN-GAP"})
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits on a gap")
        self.assertEqual(task["why"], "asks: Plan gap: which file holds the ladder?")
        self.assertEqual(self.task(tid)[1]["levers"]["answer"], "")
        self.assertEqual(self.call("/api/task/answer", {"task": tid, "text": " "})[0], 400)
        status, data = self.call("/api/task/answer", {"task": tid, "text": "config.json"})
        self.assertEqual(status, 200, data)
        self.assertTrue(data["session"])
        plan_text = (self.folder / "tasks" / tid / "plan.md").read_text(encoding="utf-8")
        decisions = plan_text.split("## Decisions")[1].split("## Out of scope")[0].strip()
        self.assertTrue(decisions.endswith(f"- Fred, {__import__('datetime').date.today().isoformat()}: config.json"))
        self.assertIn("plan gap answered by Fred: config.json", self.whys(tid))
        self.until(tid, lambda t: t["state"] == "running", "the task runs again")
        self.assertEqual(self.call("/api/task/answer", {"task": tid, "text": "again"})[0], 409)

    def test_redo_design_keeps_done_steps(self):
        tid = self.plan_task(words="HANDOFF-OK PLAN-OK", kinds=("scout", "design", "code", "code"),
                             goals={4: "second PLAN-GAP"})
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits on a gap in step 4")
        self.assertEqual([s["state"] for s in task["steps"][:4]], ["done", "done", "done", "running"])
        question = task["why"][len("asks: Plan gap: "):]
        self.assertEqual(self.call("/api/task/redo", {"task": tid})[0], 200)
        task = self.hub.tasks[tid]
        self.assertEqual([s["state"] in ("planned", "running") for s in task["steps"][:4]], [False, True, False, True])
        self.assertEqual((task["current"], task["redo"]), (2, question))
        task = self.until(tid, self.at(2), "the design step runs again")
        prompt = self.full_prompt(task["steps"][1]["session"])
        self.assertIn("Fred asked for this plan again", prompt)
        self.assertIn("(done, kept)", prompt)
        task = self.until(tid, self.at(4), "step 4 runs again")
        self.assertEqual(task["steps"][2]["state"], "done")

    def replan_task(self, goal_words="REPLAN-ADD"):
        status, data = self.post_task(self.prep_card(), words=f"HANDOFF-OK {goal_words}", steps=[
            {"kind": "scout", "goal": "look REPLAN-ASK"}, {"kind": "design", "goal": "plan it"},
            {"kind": "code", "goal": "write it"}, {"kind": "test", "goal": "run it"}])
        self.assertEqual(status, 200, status)
        return data["task"]

    def test_replan_line_inserts_a_replan_step_and_waits(self):
        self.hub.cfg["task_max_steps"] = 8
        tid = self.replan_task()
        task = self.until(tid, lambda t: t["state"] == "waiting", "the task waits on the replan")
        self.assertEqual([s["kind"] for s in task["steps"]], ["scout", "replan", "design", "code", "verify", "test"])
        step = task["steps"][1]
        self.assertEqual((step["state"], step["session"], step["model"]), ("done", "", self.hub.cfg["brief_model"]))
        self.assertTrue((self.folder / "tasks" / tid / "steps" / "02-replan.md").is_file())
        self.assertEqual(task["why"], "replanned: 1 steps added")
        self.assertEqual(task["replan"]["after"][0]["kind"], "search")
        self.assertEqual(self.task(tid)[1]["levers"]["keep"], "")
        self.assertIn("replan inserted after 01: a search step is needed first", self.whys(tid))
        self.assertEqual(self.call("/api/task/confirm", {"task": tid})[0], 200)
        self.assertIn("plan changed: 5 steps follow 02", self.whys(tid))
        task = self.hub.tasks[tid]
        self.assertEqual([s["kind"] for s in task["steps"]],
                         ["scout", "replan", "search", "design", "code", "verify", "test"])
        self.assertNotIn("replan", task)
        other = self.replan_task()  # a second task: Keep old plan
        self.until(other, lambda t: t["state"] == "waiting", "the second task waits")
        self.assertEqual(self.call("/api/task/keep", {"task": other})[0], 200)
        self.assertIn("old plan kept by Fred", self.whys(other))
        self.assertEqual([s["kind"] for s in self.hub.tasks[other]["steps"]],
                         ["scout", "replan", "design", "code", "verify", "test"])
        self.assertEqual(self.call("/api/task/keep", {"task": other})[0], 409)

    def test_replan_auto_applies_without_confirm(self):
        self.hub.cfg.update(replan_auto=True, task_max_steps=8)
        tid = self.replan_task()
        self.until(tid, self.at(3), "the search step starts")
        whys = self.whys(tid)
        after = whys[whys.index("replanned: 1 steps added"):]
        self.assertTrue(any(w.startswith("plan changed:") for w in after), whys)
        self.assertNotEqual(self.hub.tasks[tid]["why"], "replanned: 1 steps added")

    def test_replan_refused_when_no_room(self):
        self.hub.cfg["task_max_steps"] = 5  # the chain is 5 long (scout, design, code, test, verify)
        tid = self.replan_task()
        self.until(tid, self.at(2), "step 2 starts")
        self.assertTrue(any(w.startswith("replan refused: no room") for w in self.whys(tid)))

    def test_clear_keeps_the_plan_files(self):
        tid = self.plan_task(kinds=("scout", "design", "code"), words="HANDOFF-OK PLAN-SPLIT VERDICT-PASS")
        self.until(tid, lambda t: t["state"] == "done" or t["state"] == "stuck", "the task ends", seconds=60)
        self.assertEqual(self.hub.tasks[tid]["state"], "done", self.hub.tasks[tid]["why"])
        task = self.until(tid, lambda t: not t.get("briefing"), "the last brief is written")
        self.hub._clear_done(task, task["steps"][-1])
        folder = self.folder / "tasks" / tid
        self.assertTrue((folder / "plan.md").is_file())
        self.assertTrue(any((folder / "plan").glob("*.md")))
        self.assertTrue((folder / "task.json").is_file())

    # -- plan 25: the Board ---------------------------------------------------------------------------------
    def test_task_carries_questions_chain_and_ctx(self):
        tid = self.make_task()
        task = self.until(tid, self.at(2), "step 2 starts")
        self.assertIn("ctx_tokens", task["steps"][0])  # stored when step 1 ended (None: the fake reports none)
        tasks.write_brief(self.folder, task, task["steps"][0], "## Findings\n- x\n## Open questions\n- Week or 7 days?\n## Next\ngo")
        data = self.task(tid)[1]
        self.assertEqual(data["questions"], [{"q": "Week or 7 days?", "opened": 1, "closed": 0}])
        moves = [(c["step"], c["from"], c["to"]) for c in data["chain"]]
        self.assertIn((1, "running", "done"), moves)
        self.assertEqual(data["chain"], self.chain(tid)[-200:])

    def test_measure_route(self):
        self.assertEqual(self.call("/api/measure")[0], 400)
        self.assertEqual(self.call("/api/measure?project=x&n=ten")[0], 400)
        tid = self.make_task()
        self.until(tid, self.at(2), "step 2 starts")
        status, data = self.call(f"/api/measure?project={quote(str(self.project))}&n=10")
        self.assertEqual(status, 200)
        self.assertEqual((data["tasks"], [r["kind"] for r in data["kinds"]]), (1, ["scout"]))
        self.assertEqual(self.call(f"/api/measure?project={quote(str(self.project))}&n=0")[1]["tasks"], 1)  # n >= 1


for _name in dir(RunServerTest):  # the subclass reuses the setUp and helpers, not the tests of its parent
    if _name.startswith("test_"):
        setattr(TaskServerTest, _name, None)



FAKE_CODEX = [sys.executable, str(Path(__file__).resolve().parent / "fake_codex.py")]
FAKE_CMD = [sys.executable, str(Path(__file__).resolve().parent / "fake_cmd.py")]
FAKE_OPENCODE = [sys.executable, str(Path(__file__).resolve().parent / "fake_opencode.py")]


class HarnessServerTest(TaskServerTest):
    """Plan 5 Task 5: the probe, the harness switch, harness rungs on runs and task steps, the levers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "home"
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        self.folder.mkdir()
        cfg = dict(paths.load_config(), projects=[str(self.project)])
        cfg["harnesses"]["codex"]["on"] = True
        cfg["models"]["codex"] = {"gpt-6.1-sol": "sonnet"}
        (self.folder / "config.json").write_text(json.dumps({"projects": [str(self.project)]}), encoding="utf-8")
        fake = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
        self.httpd, self.hub = server.make_server(cfg, port=0, folder=self.folder, exe=fake,
                                                  exes={"codex": FAKE_CODEX})
        self.hub.user_home = Path(self.tmp.name)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.hub.probing.join(10)

    def turn_on(self, name, fake, models):
        """A harness on, found through its fake, with its models: what the switch and the probe do."""
        self.hub.cfg["harnesses"][name]["on"] = True
        self.hub.cfg["models"][name] = models
        self.hub.exes[name] = fake
        self.hub.probe([name])

    def started(self, sid):
        """The run_started line of a run, from the event log."""
        lines = [json.loads(line) for path in sorted(self.folder.glob("events-*.jsonl"))
                 for line in path.read_text(encoding="utf-8").splitlines()]
        return next(r for r in lines if r.get("event") == "run_started" and r["session_id"] == sid)

    def test_config_lists_harnesses(self):
        data = self.call("/api/config")[1]
        self.assertEqual(list(data["harnesses"]), ["claude", "codex", "opencode", "cmd"])
        codex = data["harnesses"]["codex"]
        self.assertEqual((codex["on"], codex["found"]), (True, True))
        self.assertTrue(codex["version"].startswith("codex-cli"))
        self.assertEqual(codex["models"], {"gpt-6.1-sol": "sonnet"})
        self.assertFalse(data["harnesses"]["opencode"]["on"])
        self.assertEqual((data["claude"], data["harnesses"]["claude"]["found"]), (True, True))
        self.assertEqual(set(data["models_file"]), {"path", "count", "error"})

    def test_harness_switch(self):
        status, data = self.call("/api/harness", {"name": "opencode", "on": True})
        self.assertEqual(status, 200)
        self.assertEqual((data["harnesses"]["opencode"]["on"], data["harnesses"]["opencode"]["found"]), (True, False))
        written = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        self.assertTrue(written["harnesses"]["opencode"]["on"])
        self.assertEqual(written["projects"], [str(self.project)])
        status, data = self.call("/api/harness", {"name": "claude", "on": False})
        self.assertEqual((status, data["error"]), (400, "Prep and the brief pass run on Claude"))
        self.assertEqual(self.call("/api/harness", {"name": "nope", "on": True})[0], 400)
        self.assertEqual(self.call("/api/harness", {"name": "codex", "on": "yes"})[0], 400)
        (self.folder / "config.json").write_text("{broken", encoding="utf-8")
        status, data = self.call("/api/harness", {"name": "codex", "on": False})
        self.assertEqual(status, 500)
        self.assertIn("fix it by hand", data["error"])

    def test_run_on_a_codex_rung(self):
        status, data = self.call("/api/run", {"project_dir": str(self.project), "prompt": "look at calc",
                                              "model": "codex:gpt-6.1-sol", "effort": "low"})
        self.assertEqual(status, 200, data)
        sid = data["session"]
        self.wait_idle(sid)
        rec = self.started(sid)
        self.assertEqual((rec["harness"], rec["model"]), ("codex", "gpt-6.1-sol"))
        self.assertEqual(self.session(sid)["harness"], "codex")
        info = self.call(f"/api/levers?session={sid}")[1]
        self.assertEqual((info["verify"], info["terminal"], info["handoff"], info["escalate"]), ("claude only",) * 4)
        end = time.time() + 10
        while time.time() < end and self.call(f"/api/levers?session={sid}")[1]["continue"]:
            time.sleep(0.1)
        self.assertEqual(self.call(f"/api/levers?session={sid}")[1]["continue"], "")
        self.assertEqual(self.call("/api/terminal", {"session": sid})[0], 409)

    def test_run_refuses_off_or_unknown_rung(self):
        body = {"project_dir": str(self.project), "prompt": "x", "model": "cmd:deepseek-v4.1-flash"}
        status, data = self.call("/api/run", body)
        self.assertEqual((status, data["error"]), (409, "cmd is off"))
        status, data = self.call("/api/run", dict(body, model="codex:nope"))
        self.assertEqual((status, data["error"]), (400, "unknown model or effort"))
        self.hub.found["codex"] = False
        self.assertEqual(self.call("/api/run", dict(body, model="codex:gpt-6.1-sol"))[0], 409)

    def test_task_step_pick_on_codex(self):
        steps = [{"kind": "scout", "goal": "find add()", "model": "codex:gpt-6.1-sol"},
                 {"kind": "code", "goal": "fix add()"}]
        tid = self.make_task(steps=steps)
        task = self.until(tid, self.at(2), "step 2 starts on Claude")
        first, second = task["steps"][0], task["steps"][1]
        self.assertEqual((first["harness"], first["model"], first["tier"]), ("codex", "codex:gpt-6.1-sol", "sonnet"))
        self.assertIn("harness: codex", first["notes"])
        self.assertEqual(self.started(first["session"])["harness"], "codex")
        meta = self.hub.runs.meta(first["session"])
        self.assertEqual((meta["harness"], meta["read_only"], meta["model"]), ("codex", True, "gpt-6.1-sol"))
        self.assertEqual(first["state"], "done")
        self.assertEqual((second["harness"], second["model"]), ("claude", "sonnet"))
        self.assertEqual(self.hub.runs.meta(second["session"])["harness"], "claude")

    def test_chat_and_final_message_for_codex(self):
        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "say hi HANDOFF-OK",
                                     "model": "codex:gpt-6.1-sol", "effort": "low"})[1]["session"]
        self.wait_idle(sid)
        end = time.time() + 10
        while time.time() < end and not self.hub.runs.meta(sid)["ended"]:
            time.sleep(0.1)
        items = self.call(f"/api/chat?session={sid}")[1]["items"]
        self.assertEqual(items[0]["role"], "you")
        self.assertIn("claude", [i["role"] for i in items])
        text, subtype = self.hub.final_message(sid)
        self.assertIn("say hi", text)
        self.assertIn("HANDOFF", text)
        self.assertEqual(subtype, "success")
        self.assertEqual(self.hub.last_reply(sid), next(i["text"] for i in reversed(items) if i["role"] == "claude"))

    def test_cheap_rung_refused_on_a_design_step(self):
        self.turn_on("cmd", FAKE_CMD, {"deepseek-v4.1-flash": "haiku"})
        self.turn_on("opencode", FAKE_OPENCODE, {"kimi-k3": "opus"})
        card = self.prep_card()

        def post(kind, model):
            return self.post_task(card, steps=[{"kind": kind, "goal": "g", "model": model}])
        status, data = post("design", "cmd:deepseek-v4.1-flash")
        self.assertEqual(status, 400)
        self.assertIn("is not a think model", data["error"])
        self.assertIn("step 1", data["error"])
        status, data = post("verify", "opencode:kimi-k3")
        self.assertEqual(status, 400)
        self.assertIn("not on verify or fix steps", data["error"])
        self.assertEqual(self.hub.rung_ok("opencode:kimi-k3", "design"), "")
        self.assertEqual(self.hub.rung_ok("cmd:deepseek-v4.1-flash", "scout"), "")
        self.assertEqual(self.hub.rung_ok("cmd:deepseek-v4.1-flash", "code"), "")
        self.assertEqual(self.hub.rung_ok("cmd:deepseek-v4.1-flash"), "")
        self.assertEqual(self.hub.rung_ok("cmd:deepseek-v4.1-flash", "design").split(": ")[0], "cmd")
        self.assertEqual(post("scout", "cmd:deepseek-v4.1-flash")[0], 200)

    def test_cheap_rung_accepted_on_code(self):
        self.turn_on("cmd", FAKE_CMD, {"deepseek-v4.1-flash": "haiku"})
        status, data = self.post_task(self.prep_card(), steps=[
            {"kind": "code", "goal": "g", "model": "cmd:deepseek-v4.1-flash"}])
        self.assertEqual(status, 200, data)

    def test_step_pick_falls_back_when_harness_off(self):
        steps = [{"kind": "scout", "goal": "look"}, {"kind": "scout", "goal": "again",
                                                      "model": "codex:gpt-6.1-sol"}]
        tid = self.make_task(steps=steps)
        self.assertEqual(self.hub.tasks[tid]["steps"][1]["pick"], "codex:gpt-6.1-sol")
        self.assertEqual(self.call("/api/harness", {"name": "codex", "on": False})[0], 200)
        task = self.until(tid, self.at(2), "step 2 starts")
        step = task["steps"][1]
        self.assertEqual((step["harness"], step["model"], step["tier"]), ("claude", "sonnet", "sonnet"))
        self.assertIn("pick refused: codex is off -> balance", step["notes"])
        self.assertEqual(self.hub.runs.meta(step["session"])["harness"], "claude")

    def test_step_timeout_reaches_the_retry_reason(self):
        self.hub.cfg["step_timeout_s"] = 1
        steps = [{"kind": "scout", "goal": "SLOW look", "model": "codex:gpt-6.1-sol"}]
        tid = self.make_task(steps=steps)
        task = self.until(tid, lambda t: "step timeout" in t["why"], "the timeout is the reason", seconds=40)
        self.assertIn("it hit the step timeout (1 s)", task["why"])

    def test_probe_never_raises(self):
        self.hub.exes.pop("codex")
        self.hub.cfg["harnesses"]["codex"]["exe"] = str(Path(self.tmp.name) / "no-such-codex")
        harnesses = self.hub.probe(["codex"])
        self.assertEqual((harnesses["codex"]["found"], harnesses["codex"]["version"]), (False, ""))
        self.hub.exes["codex"] = [str(Path(self.tmp.name) / "no-such-codex")]
        harnesses = self.hub.probe()
        self.assertEqual((harnesses["codex"]["found"], harnesses["codex"]["version"]), (False, ""))
        self.assertTrue(harnesses["claude"]["found"])
        self.assertEqual(self.call("/api/config")[0], 200)  # the service keeps serving


for _name in dir(TaskServerTest):  # the subclass reuses the setUp and helpers, not the tests of its parents
    if _name.startswith("test_") and _name not in HarnessServerTest.__dict__:
        setattr(HarnessServerTest, _name, None)


if __name__ == "__main__":
    unittest.main()
