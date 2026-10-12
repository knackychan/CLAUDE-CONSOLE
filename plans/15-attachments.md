# Sub-plan 15: Attachments on window runs, and files in the Chat

> Master: [PLAN.md](../PLAN.md). Written 2026-10-12. Scope (c) and image thumbnails decided by Fred
> 2026-10-12. Tasks 1-2 placed 2026-10-12 (169 tests OK); Task 3 (Fred's live check) open.

## The two answers

**1. Attach files or photos to a window run: yes, with no new CLI flag.** Window runs already send the
prompt as a stream-json `user` message on stdin (`--input-format stream-json`). Its `message.content`
can be a list of content blocks: a text block, then image blocks
(`{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": ...}}`), as shown in
code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode ("Image uploads", streaming input only).
The CLI reference has no `--file` / attach flag; `--input-format` is the documented way.
Checked on CLI 2.1.296 with `claude -p --model haiku ... --input-format stream-json --output-format
stream-json --verbose`: one message with a PNG, a base64 PDF `document` block and a text `document`
block got "Red; ZEBRA42; MANGO." ($0.0009); a 5.3 MB PNG also went through (Claude Code downsizes it).
The docs show only the image shape; `document` blocks over stream-json are checked live only.

**2. Show attachments in the Chat: yes, read-only, as chips (name, kind, size), images with a thumbnail.**
- Fred's files in a VS Code or terminal transcript: `user` records whose `message.content` holds
  `image` blocks (base64 `source`; the record also carries `imagePasteIds`) and `document` blocks
  (`title`, `source` text/plain or base64 PDF). Seen in 40+ transcripts on this machine (2.1.295-296).
  The transcript format is not documented on code.claude.com (the sessions page says only where it is
  stored), so this rests on those files. `attachment` records with `attachment.type: "file"` are
  @-mentions; they stay out because the `@path` is already in Fred's words.
- Fred's files in a window run: the stream does not echo Fred's message (no `--replay-user-messages`),
  so the service writes name, kind, size and the page's small thumbnail into the `cc_prompt` line it
  already writes. Never the file bytes.
- Claude's files: an assistant message has text, tool_use and thinking blocks only, so Claude never
  attaches a file to its words. What Claude hands over is a file it wrote: a `Write` tool_use whose
  `input.file_path` is inside the session's folder shows as a chip under Claude's next words (scratch
  files elsewhere, like temp scripts, stay in Steps). Images Claude only looked at (`tool_result` image
  blocks of Read) stay in Steps too.

## Decisions

- **Scope (c)** (Fred): the new-task box, the STOP answer box and the follow-up box on the session page take
  files, by the Attach button (file dialog), paste (a screenshot) or drop on the box. A drop anywhere else is
  swallowed so the page never navigates to the file. The peek card and the list-card answer stay text only.
- **VS Code / terminal chats:** an answer or follow-up runs in a window copy (fork), as every Continue there;
  its files go to that copy. The original chat is not touched.
- **Inline, not a path.** Files go inside the prompt message, so Claude sees them with no tool call and no
  read outside the project. Nothing is copied to disk; `runs/<id>.jsonl` and `preps/<id>.json` keep names,
  sizes and thumbnails only. `cc_events.py` is untouched (the hook logs the prompt text as before).
- **Kinds from the first bytes** (`console/attach.py`): PNG, JPEG, GIF, WebP as `image`; PDF as a base64
  `document`; any UTF-8 file with no NUL byte as a text `document` titled with its name. Anything else
  (docx, xlsx, zip) is refused with "send images (PNG, JPEG, GIF, WebP), PDF or text files".
- **Limits:** 5 files per prompt, 5 MB per image or PDF, 256 KB per text file (about 64K tokens),
  20 MB in all. Only `/api/prep`, `/api/run` and `/api/continue` take the bigger body
  (`MAX_FILES_BODY`, about 27 MB); every other route keeps 256 KB. All still pass `console/guard.py`.
- **Thumbnails** (Fred: "if possible"). Three sources, no image library:
  - Files Fred attaches in the window: the page draws a JPEG of at most 160 px on a canvas
    (`makeThumb`); the service keeps it only if it is a JPEG or PNG data URL of 24 KB or less
    (`attach.THUMB_MAX`), in the `cc_prompt` line and the Prep job, so it shows in the tray, on the Prep
    page and in the window-run Chat.
  - Images Fred pasted in a VS Code or terminal chat: `GET /api/image?session=&at=<line uuid>&k=<block>`
    reads that one block from the transcript (read only, images only).
  - Images Claude wrote: `GET /api/image?session=&path=<relative>` reads the file only when it resolves
    inside the session's folder (the window run's cwd, else the session's cwd or project folder), is at
    most 5 MB and starts like a PNG, JPEG, GIF or WebP. SVG shows as a file chip, without a picture.
  A click on a thumbnail opens it in place, up to the pane's width and 60 % of its height; a second click
  closes it. An image gone from the folder keeps its chip without the picture.
- **Prep and its jobs:** Prep never gets the bytes. The files wait with the Prep job in the service's
  memory (`Hub.preps[job]["files"]`; the snapshot carries `attached`, a summary with thumbnails); Prep reads
  one extra line naming them (`attach.note`; the card keeps the text as typed); Run and Run raw from the card
  send them; Try again carries them to the new job (`files_from`). Edit puts back the text only and says
  "attach the files again". A service restart drops waiting files (memory only).
- **Levers:** files ride on `Hub.pull(..., files)` (plan 16's single gate), Continue only.
- `transcript.TAIL_BYTES` goes from 1 MB to 4 MB so pasted images do not push Fred's last turns out of the tail.

## Tasks

- [x] Task 1 (Claude): service side, the Task 1 diff (`console/attach.py` new, `claude_cli.py`, `runs.py`,
  `transcript.py`, `server.py`, `tests/fake_claude.py`, tests). Placed 2026-10-12: 158 tests before, 169 after.
- [x] Task 2 (Claude): window side, the Task 2 diff (`web/app.js`, `web/index.html`, `web/style.css`).
  Placed 2026-10-12, checked in headless Edge (see Verified).
- [ ] Task 3 (Fred): live check in the real window after a tray restart (the service must reload).
  1. New task: Attach a screenshot and a PDF, Ctrl+Enter. The Chat shows both chips under You, the
     screenshot with its thumbnail; Claude describes the screenshot.
  2. Win+Shift+S, then Ctrl+V in the task box: a chip with a thumbnail appears. Drag a file from Explorer
     onto the box (pywebview may handle drops itself; if nothing happens, note it here).
  3. Enter (Prep) with a file: the Ready card says "1 file"; the Prep page lists it; Run sends it.
  4. A follow-up with a file on a VS Code chat: a window copy starts with the file; the VS Code chat is
     unchanged.
  5. Open a VS Code chat where you pasted images: "image 1", "image 2" with thumbnails under your turn;
     click one to enlarge. Images Claude wrote in the repo show under its reply.

## Verified (Claude, 2026-10-12)

- Docs: cli-reference (no attach flag; `--input-format stream-json`), headless (stream-json in and out),
  agent-sdk/streaming-vs-single-mode (image block shape, streaming input only).
- Live CLI 2.1.296 calls above (image, PDF, text document; a 5.3 MB PNG).
- Built in a scratch copy of the working tree (with the uncommitted Prep jobs and plan 16's `Hub.pull`):
  169 tests OK; the patch then applied to the repo, same files, 169 OK.
- Window driven by Playwright in headless Edge at 400 px dark and 340 px light with the fake claude:
  Attach dialog, paste, drop, remove; Enter to a Ready card "3 files", the Prep page list, Run, chips in the
  Chat; Ctrl+Enter with a pasted image; a refused .docx on a follow-up (400 with the reason), then a dropped
  text file; Edit's note. Thumbnails with real PNGs: 120 x 80 and 160 x 89 JPEGs in the tray, kept through
  Prep and the run into the Chat; a seeded VS Code transcript gave both pasted images (from `/api/image`
  `at`) and Claude's `out/grid.png` (`path`); a missing `out/gone.png` 404s and keeps its chip; click opens
  and closes; no horizontal scroll; no page errors.
- A flaky miss in the test script (1 in 3) was the page's start-up draft restore landing after the script
  typed: test timing, not this change.
- `transcript.turns` on a real transcript of this repo (session 15512960) gives "image 1" and "image 2"
  (25 KB each) on the prompt that pasted them.

## Task 1 diff (service)

```diff
diff --git a/console/attach.py b/console/attach.py
new file mode 100644
index 0000000..e0d701e
--- /dev/null
+++ b/console/attach.py
@@ -0,0 +1,119 @@
+"""Files Fred attaches to a window-run prompt. They go inline, as content blocks of the stream-json user
+message (the documented image / document shapes), so Claude sees them without a tool call. The kind
+comes from the first bytes, never from the name. Only name, kind, size and, for an image, the small
+thumbnail the page drew are kept (the cc_prompt line); the bytes are never written."""
+import base64
+import binascii
+import re
+from pathlib import Path
+
+MAX_FILES = 5
+THUMB_MAX = 24 * 1024          # one thumbnail data URL (the page draws about 160 px JPEGs, 5-15 KB)
+_THUMB = re.compile(r"data:image/(jpeg|png);base64,[A-Za-z0-9+/]+=*")
+MAX_BYTES = 5 * 1024 * 1024    # one image or PDF (Claude Code downsizes big images itself)
+MAX_TEXT = 256 * 1024          # one text file: about 64K tokens
+MAX_TOTAL = 20 * 1024 * 1024   # all files of one prompt
+_IMAGES = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"),
+           (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"))
+SENDABLE = "images (PNG, JPEG, GIF, WebP), PDF or text files"
+
+
+class AttachError(ValueError):
+    pass
+
+
+def kind_of(data: bytes):
+    """(kind, media type): image, pdf or text; None when Claude could not take the file inline."""
+    for magic, media in _IMAGES:
+        if data.startswith(magic):
+            return "image", media
+    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
+        return "image", "image/webp"
+    if data.startswith(b"%PDF-"):
+        return "pdf", "application/pdf"
+    if b"\x00" not in data:
+        try:
+            data.decode("utf-8")
+            return "text", "text/plain"
+        except UnicodeDecodeError:
+            pass
+    return None
+
+
+def parse(files) -> list:
+    """The page's [{name, data (base64), thumb?}] -> [{name, kind, media_type, bytes, data, thumb}].
+    `data` stays base64 for images and PDFs and becomes the text for text files; `thumb` is the page's
+    data URL for an image, kept only when it is a small JPEG or PNG ("" otherwise, never an error)."""
+    if not files:
+        return []
+    if not isinstance(files, list) or len(files) > MAX_FILES:
+        raise AttachError(f"at most {MAX_FILES} files per prompt")
+    out, total = [], 0
+    for f in files:
+        name, b64 = (f.get("name"), f.get("data")) if isinstance(f, dict) else (None, None)
+        if not isinstance(name, str) or not isinstance(b64, str):
+            raise AttachError("each file needs a name and its data")
+        name = name.replace("\\", "/").rsplit("/", 1)[-1].strip()[:120] or "file"
+        try:
+            data = base64.b64decode(b64, validate=True)
+        except (binascii.Error, ValueError):
+            raise AttachError(f"{name}: not base64")
+        kind = kind_of(data)
+        if not kind:
+            raise AttachError(f"{name}: send {SENDABLE}")
+        limit = MAX_TEXT if kind[0] == "text" else MAX_BYTES
+        if len(data) > limit:
+            raise AttachError(f"{name}: over {limit // 1024} KB" if limit < 1048576 else
+                              f"{name}: over {limit // 1048576} MB")
+        total += len(data)
+        if total > MAX_TOTAL:
+            raise AttachError(f"over {MAX_TOTAL // 1048576} MB in all")
+        thumb = f.get("thumb")
+        ok = kind[0] == "image" and isinstance(thumb, str) and len(thumb) <= THUMB_MAX and _THUMB.fullmatch(thumb)
+        out.append({"name": name, "kind": kind[0], "media_type": kind[1], "bytes": len(data),
+                    "data": data.decode("utf-8") if kind[0] == "text" else b64, "thumb": thumb if ok else ""})
+    return out
+
+
+def blocks(files: list) -> list:
+    """Content blocks for claude_cli.user_message, after the prompt's text block."""
+    out = []
+    for f in files:
+        if f["kind"] == "image":
+            out.append({"type": "image", "source": {"type": "base64", "media_type": f["media_type"], "data": f["data"]}})
+        elif f["kind"] == "pdf":
+            out.append({"type": "document", "title": f["name"],
+                        "source": {"type": "base64", "media_type": "application/pdf", "data": f["data"]}})
+        else:
+            out.append({"type": "document", "title": f["name"],
+                        "source": {"type": "text", "media_type": "text/plain", "data": f["data"]}})
+    return out
+
+
+def note(files: list) -> str:
+    """The line Prep reads instead of the files (Prep never gets the bytes; the run does)."""
+    if not files:
+        return ""
+    return "\n\nAttached to this task, sent with the run: " + ", ".join(f"{f['name']} ({f['kind']})" for f in files) + "."
+
+
+def summary(files: list) -> list:
+    """What the Chat shows and the run log keeps: no file bytes, an image's thumbnail when there is one."""
+    return [{"name": f["name"], "kind": f["kind"], "bytes": f["bytes"], **({"thumb": f["thumb"]} if f.get("thumb") else {})}
+            for f in files]
+
+
+def folder_image(folder: str, rel: str):
+    """(bytes, media type) of an image Claude wrote inside the session's folder, for its Chat thumbnail;
+    None for anything else: outside the folder, missing, too big, or not PNG / JPEG / GIF / WebP."""
+    try:
+        base = Path(folder).resolve()
+        path = (base / rel).resolve()
+        path.relative_to(base)
+        if not path.is_file() or path.stat().st_size > MAX_BYTES:
+            return None
+        data = path.read_bytes()
+    except (OSError, ValueError, TypeError):
+        return None
+    kind = kind_of(data)
+    return (data, kind[1]) if kind and kind[0] == "image" else None
diff --git a/console/claude_cli.py b/console/claude_cli.py
index 1d673cf..35be6e1 100644
--- a/console/claude_cli.py
+++ b/console/claude_cli.py
@@ -86,8 +86,10 @@ def terminal_command(exe: list, session_id: str, model: str = "", effort: str =
     return cmd
 
 
-def user_message(text: str) -> bytes:
-    msg = {"type": "user", "message": {"role": "user", "content": text}}
+def user_message(text: str, blocks: list = ()) -> bytes:
+    """`blocks`: attached files (console/attach.py), after the text in one content list."""
+    content = [{"type": "text", "text": text}, *blocks] if blocks else text
+    msg = {"type": "user", "message": {"role": "user", "content": content}}
     return (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
 
 
diff --git a/console/runs.py b/console/runs.py
index 5172d83..0503901 100644
--- a/console/runs.py
+++ b/console/runs.py
@@ -8,7 +8,7 @@ import time
 import uuid
 from pathlib import Path
 
-from . import claude_cli, events, redact
+from . import attach, claude_cli, events, redact, transcript
 
 WATCH_S = 0.5
 CHAT_TEXT = 4000
@@ -43,34 +43,41 @@ def read_lines(path: Path, start: int):
 
 
 def chat(path: Path, cwd: str = "", limit: int = 200) -> list:
-    """The window run's conversation: prompts, assistant text, tool calls, results."""
+    """The window run's conversation: prompts (with the files Fred attached), assistant text (with the
+    files Claude wrote before it), tool calls, results."""
     _, lines = read_lines(path, 0)
-    items = []
+    items, wrote = [], []
     for d in lines:
         kind = d.get("type")
         if "raw" in d:
             items.append({"role": "note", "text": redact.clip(d["raw"], 300)})
         elif kind == "cc_prompt":
-            items.append({"role": "you", "text": d.get("text", "")[:CHAT_TEXT], "ts": d.get("ts")})
+            transcript.flush_wrote(items, wrote)
+            items.append({"role": "you", "text": d.get("text", "")[:CHAT_TEXT], "ts": d.get("ts"),
+                          "files": d.get("files") or []})
         elif kind == "assistant" and not d.get("parent_tool_use_id"):
             for block in (d.get("message") or {}).get("content") or []:
                 if block.get("type") == "text" and block.get("text", "").strip():
-                    items.append({"role": "claude", "text": block["text"][:CHAT_TEXT]})
+                    items.append({"role": "claude", "text": block["text"][:CHAT_TEXT], "files": wrote[:]})
+                    wrote.clear()
                 elif block.get("type") == "tool_use":
                     what = redact.summarize(block.get("name"), block.get("input"), cwd)
                     items.append({"role": "tool", "text": f"{block.get('name', '')} {what}".strip()})
+                    transcript.note_write(wrote, block, cwd)
         elif kind == "user" and not d.get("parent_tool_use_id"):
             content = (d.get("message") or {}).get("content")
             if isinstance(content, list) and any("[Request interrupted" in str(b.get("text", ""))
                                                  for b in content if isinstance(b, dict)):
                 items.append({"role": "note", "text": "stopped"})
         elif kind == "result":
+            transcript.flush_wrote(items, wrote)
             cost = d.get("total_cost_usd") or 0
             denials = len(d.get("permission_denials") or [])
             text = f"{d.get('subtype', '')} · ${cost:.2f} · {d.get('num_turns', 0)} turns"
             if denials:
                 text += f" · {denials} denied"
             items.append({"role": "result", "text": text})
+    transcript.flush_wrote(items, wrote)
     return items[-limit:]
 
 
@@ -140,9 +147,10 @@ class RunManager:
     # -- start ----------------------------------------------------------------------
     def start(self, cwd: str, prompt: str, model: str, effort: str, resume: str = None,
               title: str = "", route: str = "", reason: str = "", prep: str = "",
-              fork: str = "", kind: str = "run", extra: dict = None) -> str:
+              fork: str = "", kind: str = "run", extra: dict = None, files: list = ()) -> str:
         """A new run, a new turn of a window run (`resume`), or a window copy of another chat (`fork`).
-        `kind` (run, continue, verify, handoff, escalate) and `extra` go into the run_started line."""
+        `kind` (run, continue, verify, handoff, escalate) and `extra` go into the run_started line.
+        `files` (attach.parse) go inline after the prompt; the stream file keeps their summary only."""
         if not self.exe:
             raise RunError("claude.exe not found; set \"claude_exe\" in config.json")
         sid = resume or str(uuid.uuid4())
@@ -151,13 +159,14 @@ class RunManager:
         self.runs.mkdir(parents=True, exist_ok=True)
         path = self.stream_path(sid)
         with open(path, "a", encoding="utf-8") as fh:
-            fh.write(json.dumps({"type": "cc_prompt", "ts": time.time(), "text": prompt}, ensure_ascii=False) + "\n")
+            fh.write(json.dumps({"type": "cc_prompt", "ts": time.time(), "text": prompt,
+                                 "files": attach.summary(files)}, ensure_ascii=False) + "\n")
         offset = path.stat().st_size
         cmd = claude_cli.run_command(self.exe, model, effort, sid, resume=bool(resume),
                                      name=redact.clip(title, 60), fork=fork)
         proc = self._spawn(cmd, cwd, path)
         footer = "" if prompt.startswith("/") else claude_cli.STOP_FOOTER  # a /skill takes no footer
-        proc.stdin.write(claude_cli.user_message(prompt + footer))
+        proc.stdin.write(claude_cli.user_message(prompt + footer, attach.blocks(files)))
         proc.stdin.flush()
         with self.lock:
             self.live[sid] = proc
diff --git a/console/server.py b/console/server.py
index 15d4050..edd5b94 100644
--- a/console/server.py
+++ b/console/server.py
@@ -8,7 +8,7 @@ from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
 from urllib.parse import parse_qs, urlparse
 
-from . import brief, claude_cli, events, guard, levers, paths, prep, routing, runs, transcript, usage
+from . import attach, brief, claude_cli, events, guard, levers, paths, prep, routing, runs, transcript, usage
 from .state import MAX_STEPS, WRITE_TOOLS, State, norm_dir
 
 WEB = Path(__file__).resolve().parent.parent / "web"
@@ -21,6 +21,8 @@ TICK_S = 15.0
 HISTORY_S = 60.0  # the Usage page's scan of every transcript
 APP_ID = "claude-console"
 MAX_BODY = 256 * 1024
+MAX_FILES_BODY = attach.MAX_TOTAL * 4 // 3 + MAX_BODY  # /api/prep, /api/run and /api/continue carry base64 files
+FILE_ROUTES = ("/api/prep", "/api/run", "/api/continue")
 MAX_PROMPT = 20000
 BUSY = {"running", "quiet", "stall"}
 
@@ -94,20 +96,29 @@ class Hub:
                 pass
             self._stop.wait(HISTORY_S)
 
-    def start_prep(self, project_dir: str, raw: str) -> str:
-        """Prep in its own thread: the request answers at once and the strip shows the job as it runs."""
+    def start_prep(self, project_dir: str, raw: str, files: list = ()) -> str:
+        """Prep in its own thread: the request answers at once and the strip shows the job as it runs.
+        `files` (attach.parse) wait with the job, in memory only, for the run its card starts."""
         job = prep.new_id()
         with self.lock:
             self.preps[job] = {"id": job, "project_dir": project_dir, "raw": raw, "ts": time.time(),
-                               "state": "running"}
+                               "state": "running", "files": list(files)}
             self.version += 1
             self.changed.notify_all()
-        threading.Thread(target=self._prep_job, args=(job, project_dir, raw), name="cc-prep", daemon=True).start()
+        threading.Thread(target=self._prep_job, args=(job, project_dir, raw, attach.note(files)),
+                         name="cc-prep", daemon=True).start()
         return job
 
-    def _prep_job(self, job: str, project_dir: str, raw: str) -> None:
+    def prep_files(self, job) -> list:
+        """The files waiting with a Prep job ([] for an unknown job)."""
+        with self.lock:
+            return list(self.preps.get(job, {}).get("files") or []) if isinstance(job, str) else []
+
+    def _prep_job(self, job: str, project_dir: str, raw: str, note: str = "") -> None:
+        """`note` names the attached files for Prep; the card on the strip keeps the text as typed."""
         try:
-            end = {"state": "done", "card": prep.run_prep(self.cfg, self.folder, project_dir, raw, self.runs.exe, job)}
+            card = prep.run_prep(self.cfg, self.folder, project_dir, raw + note, self.runs.exe, job)
+            end = {"state": "done", "card": dict(card, raw=raw)}
         except Exception as exc:  # whatever went wrong, the job ends: a pill never spins forever
             end = {"state": "failed", "error": str(exc) or type(exc).__name__}
         with self.lock:
@@ -155,7 +166,9 @@ class Hub:
         now = time.time()
         with self.lock:
             snap = self.state.snapshot(now, self.usage, self.usage_days.get(usage.day_of(now)))
-            snap["preps"] = sorted((dict(j) for j in self.preps.values()), key=lambda j: j["ts"])
+            snap["preps"] = sorted(({**{k: v for k, v in j.items() if k != "files"},
+                                     "attached": attach.summary(j["files"])} for j in self.preps.values()),
+                                   key=lambda j: j["ts"])
             return snap
 
     def steps(self, session_id: str, limit: int = 200) -> list:
@@ -246,11 +259,12 @@ class Hub:
                 "after_verify": list(levers.after_verify(s["verdict"])), "route": f"{model}/{effort}", "escalate_to": "/".join(step) if step else "",
                 "fork": not window, "cwd": cwd or "", "cold": None if base else self.cold(s, model)}
 
-    def pull(self, sid, lever: str, text: str = "", confirm: bool = False) -> tuple:
+    def pull(self, sid, lever: str, text: str = "", confirm: bool = False, files: list = ()) -> tuple:
         """Continue (also STOP answers and Resume), Verify, Handoff, Escalate: a new turn of a window
         run, or a window copy (fork) of a VS Code / terminal chat, which stays as it is. De-escalate starts
         no turn: the next one runs on the task's starting route. Returns (status, body); a click and the
-        automatic step (auto_steps) pass the same gate, self.levers."""
+        automatic step (auto_steps) pass the same gate, self.levers. `files` (attach.parse) go with a
+        Continue only."""
         info = self.levers(sid)
         if info is None:
             return 404, {"error": "unknown session"}
@@ -284,7 +298,8 @@ class Hub:
         fork = sid if info["fork"] else ""
         new = self.runs.start(info["cwd"], text, model, effort, resume=None if fork else sid, fork=fork,
                               title="↳ " + (s["title"] or sid[:8]) if fork else "",
-                              route=s["route"] if fork else "", kind=lever, extra=extra)
+                              route=s["route"] if fork else "", kind=lever, extra=extra,
+                              files=files if lever == "continue" else ())
         if miss:
             levers.add_miss(self.folder, miss)
         self.poll_once()
@@ -391,6 +406,8 @@ class Handler(BaseHTTPRequestHandler):
                                "project": window.get("project", ""), "brief": window.get("brief") is True})
         if url.path == "/api/usage":
             return self._json(self.hub.usage_report())
+        if url.path == "/api/image":
+            return self._image(query)
         if url.path == "/api/chat":
             return self._chat(query.get("session", [""])[0])
         if url.path == "/api/brief":
@@ -416,23 +433,26 @@ class Handler(BaseHTTPRequestHandler):
                   "/api/done": self._done}
         for lever in ("continue", "verify", "handoff", "escalate"):
             routes[f"/api/{lever}"] = lambda body, lever=lever: self._lever(body, lever)
-        handler = routes.get(urlparse(self.path).path)
+        path = urlparse(self.path).path
+        handler = routes.get(path)
         if handler is None:
             return self._send(404, b"not found", "text/plain")
-        body = self._body()
+        body = self._body(MAX_FILES_BODY if path in FILE_ROUTES else MAX_BODY)
         if body is None:
             return self._error(400, "expected a JSON object")
         try:
             return handler(body)
+        except attach.AttachError as exc:
+            return self._error(400, str(exc))
         except (runs.RunError, prep.PrepError) as exc:
             return self._error(409, str(exc))
 
-    def _body(self):
+    def _body(self, limit: int = MAX_BODY):
         try:
             size = int(self.headers.get("Content-Length") or 0)
         except ValueError:
             return None
-        if size <= 0 or size > MAX_BODY:
+        if size <= 0 or size > limit:
             return None
         try:
             data = json.loads(self.rfile.read(size).decode("utf-8"))
@@ -453,7 +473,8 @@ class Handler(BaseHTTPRequestHandler):
             return self._error(400, "empty prompt")
         if not self.hub.runs.exe:
             return self._error(409, "claude.exe not found; set \"claude_exe\" in config.json")
-        return self._json({"job": self.hub.start_prep(folder, raw)})
+        files = attach.parse(body.get("files")) or self.hub.prep_files(body.get("files_from"))  # Try again: the old job's
+        return self._json({"job": self.hub.start_prep(folder, raw, files)})
 
     def _prep_drop(self, body):
         job = body.get("job")
@@ -481,8 +502,10 @@ class Handler(BaseHTTPRequestHandler):
                      "prep_turns": card.get("turns")}  # the Route block's first row
         else:
             title, route, reason, prep_id, extra = text, "raw", "", "", None
+        # sent now (the composer), or waiting with the card's Prep job (Run, or Run raw with files_from)
+        files = attach.parse(body.get("files")) or self.hub.prep_files(prep_id or body.get("files_from"))
         sid = self.hub.runs.start(folder, text, model, effort, title=title, route=route,
-                                  reason=reason, prep=prep_id, extra=extra)
+                                  reason=reason, prep=prep_id, extra=extra, files=files)
         if prep_id:
             self.hub.drop_prep(prep_id)  # the card became this run
         self.hub.poll_once()
@@ -515,8 +538,9 @@ class Handler(BaseHTTPRequestHandler):
         return self._json({"session": sid})
 
     def _lever(self, body, lever):
+        files = attach.parse(body.get("files")) if lever == "continue" else []
         code, data = self.hub.pull(body.get("session"), lever, self._text(body, "text") if lever == "continue" else "",
-                                   body.get("confirm") is True)
+                                   body.get("confirm") is True, files)
         return self._json(data, code)
 
     def _terminal(self, body):
@@ -569,6 +593,25 @@ class Handler(BaseHTTPRequestHandler):
         return self._json({"items": items, "source": "window", "changed": changed,
                            "live": self.hub.runs.is_live(sid), "start_commit": meta.get("start_commit", "")})
 
+    def _image(self, query):
+        """A Chat thumbnail: an image Fred pasted into a transcript (`at` = line uuid, `k` = block), or an
+        image Claude wrote inside the session's folder (`path`, relative). Read only; images only."""
+        one = lambda key: query.get(key, [""])[0]
+        sid = one("session")
+        s = self.hub.session(sid) if sid else None
+        if not s:
+            return self._error(404, "unknown session")
+        if one("path"):
+            meta = self.hub.runs.meta(sid) if all(c.isalnum() or c == "-" for c in sid) else None
+            found = attach.folder_image((meta or {}).get("cwd") or s["cwd"] or s["project_dir"], one("path"))
+        else:
+            at, k = one("at"), one("k")
+            ok = at and all(c.isalnum() or c == "-" for c in at) and k.isdigit()
+            found = transcript.image(s["transcript_path"], at, int(k)) if ok else None
+        if not found:
+            return self._error(404, "no such image")
+        return self._send(200, *found)
+
     def _brief(self, sid: str, kind: str):
         """The text of a new task that takes over a session, built from its transcript, its steps and the
         folder's git status: no model call, nothing written."""
diff --git a/console/transcript.py b/console/transcript.py
index ec2cffd..0e9b9a7 100644
--- a/console/transcript.py
+++ b/console/transcript.py
@@ -1,13 +1,15 @@
 """The last turns of a Claude Code chat in words, read from its transcript: a VS Code or terminal chat
 has no stream of its own. Read only, from the end of the file; tool calls, tool results and thinking
 stay out (Steps shows tool calls)."""
+import base64
 import json
 import re
 from datetime import datetime
+from pathlib import PurePath
 
-from . import redact
+from . import attach, redact
 
-TAIL_BYTES = 1024 * 1024  # read from the end: enough for the last few turns of a long chat
+TAIL_BYTES = 4 * 1024 * 1024  # read from the end: the last few turns of a long chat, pasted images included
 HEAD_BYTES = 256 * 1024  # the first prompt is near the start of the file
 TURNS = 6
 TEXT_MAX = 1500   # the first prompt (a title, a brief goal)
@@ -16,6 +18,7 @@ TURN_MAX = 20000  # one chat turn: a long reply must not end mid-word
 # Fred's own pastes stay, as in cc_events.py.
 _INJECTED = re.compile(r"\s*<(?!pasted_content\b)([A-Za-z][\w-]*)[^>]*>.*?</\1>\s*", re.S)
 _PASTED = re.compile(r"</?pasted_content[^>]*>")
+IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}  # the kinds a Chat thumbnail shows (attach.kind_of)
 
 
 def _when(stamp):
@@ -37,8 +40,46 @@ def _words(content) -> str:
     return _PASTED.sub("", _INJECTED.sub(" ", text)).strip()
 
 
+def _attached(content, uuid: str = "") -> list:
+    """Files Fred sent with a prompt: pasted or dropped images, attached documents (name, kind, size).
+    An image also says where it is (`at`: the line's uuid and the block's index) for its thumbnail."""
+    out = []
+    for k, b in enumerate(content if isinstance(content, list) else []):
+        src = b.get("source") if isinstance(b, dict) else None
+        if not isinstance(src, dict) or b.get("type") not in ("image", "document"):
+            continue
+        data = src.get("data") if isinstance(src.get("data"), str) else ""
+        size = len(data) * 3 // 4 if src.get("type") == "base64" else len(data.encode("utf-8"))
+        if b["type"] == "image":
+            out.append({"name": f"image {sum(f['kind'] == 'image' for f in out) + 1}", "kind": "image", "bytes": size,
+                        **({"at": [uuid, k]} if uuid else {})})
+        else:
+            out.append({"name": redact.clip(str(b.get("title") or "document"), 120),
+                        "kind": "pdf" if src.get("media_type") == "application/pdf" else "text", "bytes": size})
+    return out
+
+
+def note_write(wrote: list, block: dict, cwd: str = "") -> None:
+    """A Write call inside the session's folder is a file Claude made: it shows under Claude's next
+    words. Scratch files elsewhere (temp scripts) stay in Steps."""
+    if block.get("type") != "tool_use" or block.get("name") != "Write" or not cwd:
+        return
+    name = redact.summarize("Write", block.get("input"), cwd)
+    if name and not PurePath(name).is_absolute() and ":" not in name and all(f["name"] != name for f in wrote):
+        ext = name.rsplit(".", 1)[-1].lower()
+        wrote.append({"name": name, "kind": "image" if ext in IMAGE_EXT else "file", "bytes": None})
+
+
+def flush_wrote(items: list, wrote: list) -> None:
+    """Files Claude wrote with no words after them (the turn ended or Fred spoke next)."""
+    if wrote:
+        items.append({"role": "claude", "text": "", "files": wrote[:]})
+        wrote.clear()
+
+
 def turns(path, limit: int = TURNS) -> list:
-    """[{role: you | claude | note, text, ts}] oldest first: the last `limit` turns of the transcript."""
+    """[{role: you | claude | note, text, ts, files}] oldest first: the last `limit` turns of the transcript.
+    `files`: what Fred attached to a prompt, or what Claude wrote before a reply."""
     path = str(path or "")
     if not path.endswith(".jsonl"):
         return []
@@ -52,7 +93,7 @@ def turns(path, limit: int = TURNS) -> list:
     lines = data.split(b"\n")
     if start:
         lines = lines[1:]  # the first line was cut in the middle
-    out = []
+    out, wrote = [], []
     for raw in lines:
         try:
             rec = json.loads(raw)
@@ -62,19 +103,60 @@ def turns(path, limit: int = TURNS) -> list:
         if kind not in ("user", "assistant") or rec.get("isMeta") or rec.get("isSidechain"):
             continue
         msg = rec.get("message")
-        text = _words(msg.get("content") if isinstance(msg, dict) else None)
-        if not text:
+        content = msg.get("content") if isinstance(msg, dict) else None
+        text = _words(content)
+        files = _attached(content, str(rec.get("uuid") or "")) if kind == "user" else []
+        if kind == "assistant":
+            for block in content if isinstance(content, list) else []:
+                if isinstance(block, dict):
+                    note_write(wrote, block, rec.get("cwd") or "")
+        if not text and not files:
             continue
+        ts = _when(rec.get("timestamp"))
         if text.startswith("[Request interrupted"):
-            out.append({"role": "note", "text": "stopped", "ts": _when(rec.get("timestamp"))})
+            out.append({"role": "note", "text": "stopped", "ts": ts})
+            continue
+        text = redact.mask(text)
+        if len(text) > TURN_MAX:
+            text = text[:TURN_MAX].rstrip() + "\n[cut here, the full text is in the transcript]"
+        if kind == "user":
+            flush_wrote(out, wrote)
+            out.append({"role": "you", "text": text, "ts": ts, "files": files})
         else:
-            text = redact.mask(text)
-            if len(text) > TURN_MAX:
-                text = text[:TURN_MAX].rstrip() + "\n[cut here, the full text is in the transcript]"
-            out.append({"role": "you" if kind == "user" else "claude", "text": text, "ts": _when(rec.get("timestamp"))})
+            out.append({"role": "claude", "text": text, "ts": ts, "files": wrote[:]})
+            wrote.clear()
+    flush_wrote(out, wrote)
     return out[-limit:]
 
 
+def image(path, uuid: str, k: int):
+    """(bytes, media type) of image block `k` in Fred's line `uuid`, for its Chat thumbnail; None when
+    the line, the block or the image is not there. Read only, line by line."""
+    path = str(path or "")
+    if not path.endswith(".jsonl") or not uuid:
+        return None
+    needle = f'"{uuid}"'.encode("utf-8")
+    try:
+        with open(path, "rb") as fh:
+            for raw in fh:
+                if needle not in raw:
+                    continue
+                rec = json.loads(raw)
+                if not isinstance(rec, dict) or rec.get("uuid") != uuid:
+                    continue  # a line that only points at it (parentUuid)
+                content = (rec.get("message") or {}).get("content")
+                block =content[k] if isinstance(content, list) and 0 <= k < len(content) else None
+                src = block.get("source") if isinstance(block, dict) and block.get("type") == "image" else None
+                if not isinstance(src, dict) or src.get("type") != "base64":
+                    return None
+                data = base64.b64decode(src.get("data") or "")
+                kind = attach.kind_of(data)
+                return (data, kind[1]) if kind and kind[0] == "image" else None
+    except (OSError, ValueError, TypeError, AttributeError):
+        return None
+    return None
+
+
 def first_prompt(path) -> str:
     """The first thing typed in the chat, in words and masked ("" when none is in the first 256 KB)."""
     path = str(path or "")
diff --git a/tests/fake_claude.py b/tests/fake_claude.py
index 8c5d218..9759b3a 100644
--- a/tests/fake_claude.py
+++ b/tests/fake_claude.py
@@ -54,6 +54,8 @@ def run():
         if msg.get("type") != "user":
             continue
         text = msg["message"]["content"]
+        if isinstance(text, list):  # attached files: the text block, then one block per file
+            text = text[0]["text"] + " +" + " +".join(b["type"] for b in text[1:])
         out({"type": "system", "subtype": "init", "session_id": sid, "cwd": "."})
         out({"type": "assistant", "session_id": sid, "parent_tool_use_id": None, "message": {
             "role": "assistant", "content": [
diff --git a/tests/test_attach.py b/tests/test_attach.py
new file mode 100644
index 0000000..dcab6e2
--- /dev/null
+++ b/tests/test_attach.py
@@ -0,0 +1,71 @@
+import base64
+import unittest
+
+from console import attach
+
+PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
+PDF = b"%PDF-1.4\n%fake\n"
+
+
+def page(name, data: bytes):
+    return {"name": name, "data": base64.b64encode(data).decode()}
+
+
+class AttachTest(unittest.TestCase):
+    def test_kind_comes_from_the_bytes(self):
+        self.assertEqual(attach.kind_of(PNG), ("image", "image/png"))
+        self.assertEqual(attach.kind_of(b"\xff\xd8\xff\xe0rest"), ("image", "image/jpeg"))
+        self.assertEqual(attach.kind_of(b"GIF89a..."), ("image", "image/gif"))
+        self.assertEqual(attach.kind_of(b"RIFF\x00\x00\x00\x00WEBPVP8 "), ("image", "image/webp"))
+        self.assertEqual(attach.kind_of(PDF), ("pdf", "application/pdf"))
+        self.assertEqual(attach.kind_of("# Notes é\n".encode("utf-8")), ("text", "text/plain"))
+        self.assertIsNone(attach.kind_of(b"PK\x03\x04\x00docx"))  # a zip (docx, xlsx): not inline
+        self.assertIsNone(attach.kind_of(b"\xff\xfe\x00\x00"))
+
+    def test_parse_and_blocks(self):
+        files = attach.parse([page("C:\\shots\\a.png", PNG), page("spec.pdf", PDF), page("notes.md", b"# hi")])
+        self.assertEqual(attach.summary(files), [{"name": "a.png", "kind": "image", "bytes": len(PNG)},
+                                                 {"name": "spec.pdf", "kind": "pdf", "bytes": len(PDF)},
+                                                 {"name": "notes.md", "kind": "text", "bytes": 4}])
+        image, pdf, text = attach.blocks(files)
+        self.assertEqual(image, {"type": "image", "source": {"type": "base64", "media_type": "image/png",
+                                                             "data": base64.b64encode(PNG).decode()}})
+        self.assertEqual((pdf["type"], pdf["title"], pdf["source"]["media_type"], pdf["source"]["type"]),
+                         ("document", "spec.pdf", "application/pdf", "base64"))
+        self.assertEqual(text, {"type": "document", "title": "notes.md",
+                                "source": {"type": "text", "media_type": "text/plain", "data": "# hi"}})
+        self.assertEqual(attach.note(files), "\n\nAttached to this task, sent with the run: "
+                                             "a.png (image), spec.pdf (pdf), notes.md (text).")
+        self.assertEqual(attach.note([]), "")
+        self.assertEqual(attach.parse(None), [])
+        self.assertEqual(attach.parse([]), [])
+
+    def test_an_image_keeps_a_small_thumbnail_only(self):
+        thumb = "data:image/jpeg;base64," + "A" * 100
+        files = attach.parse([dict(page("a.png", PNG), thumb=thumb), dict(page("b.png", PNG), thumb="data:text/html,<b>"),
+                              dict(page("c.png", PNG), thumb="data:image/png;base64," + "A" * attach.THUMB_MAX),
+                              dict(page("n.md", b"# hi"), thumb=thumb)])
+        self.assertEqual([f["thumb"] for f in files], [thumb, "", "", ""])
+        self.assertEqual(attach.summary(files)[0]["thumb"], thumb)
+        self.assertNotIn("thumb", attach.summary(files)[1])
+
+    def test_refusals_say_why(self):
+        cases = [
+            ([page("x.png", PNG)] * (attach.MAX_FILES + 1), "at most"),
+            ("not a list", "at most"),
+            ([{"name": "a.png"}], "needs a name"),
+            ([{"name": "a.png", "data": "***"}], "not base64"),
+            ([page("report.docx", b"PK\x03\x04\x14\x00\x06\x00rest")], "send images"),
+            ([page("big.png", PNG + b"\x00" * attach.MAX_BYTES)], "over 5 MB"),
+            ([page("log.txt", b"a" * (attach.MAX_TEXT + 1))], "over 256 KB"),
+            ([page(f"{k}.png", PNG + b"\x00" * (attach.MAX_BYTES - 100)) for k in range(5)], "in all"),
+        ]
+        for files, why in cases:
+            with self.subTest(why=why):
+                with self.assertRaises(attach.AttachError) as err:
+                    attach.parse(files)
+                self.assertIn(why, str(err.exception))
+
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/tests/test_claude_cli.py b/tests/test_claude_cli.py
index d1f6338..74b23d9 100644
--- a/tests/test_claude_cli.py
+++ b/tests/test_claude_cli.py
@@ -45,6 +45,9 @@ class CommandTest(unittest.TestCase):
     def test_messages(self):
         self.assertEqual(json.loads(claude_cli.user_message("hé")),
                          {"type": "user", "message": {"role": "user", "content": "hé"}})
+        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "iVBO"}}
+        self.assertEqual(json.loads(claude_cli.user_message("see", [image]))["message"]["content"],
+                         [{"type": "text", "text": "see"}, image])
         self.assertEqual(json.loads(claude_cli.interrupt_message("r1"))["request"], {"subtype": "interrupt"})
 
     def test_child_env_drops_session_variables_only(self):
diff --git a/tests/test_runs.py b/tests/test_runs.py
index 60933cc..a2fe132 100644
--- a/tests/test_runs.py
+++ b/tests/test_runs.py
@@ -1,3 +1,4 @@
+import base64
 import copy
 import json
 import os
@@ -8,7 +9,7 @@ import unittest
 from pathlib import Path
 from unittest import mock
 
-from console import events, paths, runs
+from console import attach, events, paths, runs
 
 FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_claude.py")]
 
@@ -60,6 +61,36 @@ class RunsTest(unittest.TestCase):
         self.assertEqual(items[2]["text"], "Read calc.py")
         self.assertFalse(self.mgr.is_live(sid))
 
+    def test_attached_files_go_inline_and_only_their_summary_is_kept(self):
+        files = attach.parse([{"name": "shot.png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\nPIXELS").decode()},
+                              {"name": "notes.md", "data": base64.b64encode(b"# notes").decode()}])
+        sid = self.mgr.start(str(self.project), "look", "sonnet", "low", files=files)
+        self.assertTrue(wait_for(lambda: self.ended(sid)))
+        items = runs.chat(self.mgr.stream_path(sid), str(self.project))
+        self.assertEqual(items[0]["files"], [{"name": "shot.png", "kind": "image", "bytes": 14},
+                                             {"name": "notes.md", "kind": "text", "bytes": 7}])
+        self.assertIn("+image +document", items[1]["text"])  # the fake claude got the blocks
+        stream = self.mgr.stream_path(sid).read_text(encoding="utf-8")
+        self.assertNotIn(files[0]["data"], stream)
+        self.assertNotIn("# notes", stream)
+
+    def test_chat_puts_files_claude_wrote_under_its_next_words(self):
+        path = self.mgr.runs / "s1.jsonl"
+        self.mgr.runs.mkdir(parents=True)
+        write = lambda p: {"type": "tool_use", "name": "Write", "input": {"file_path": p, "content": "x"}}
+        lines = [{"type": "cc_prompt", "ts": 1, "text": "draw it"},
+                 {"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
+                     write(str(self.project / "out" / "chart.png")), {"type": "text", "text": "Drew it."},
+                     write(str(self.project / "log.txt"))]}},
+                 {"type": "result", "subtype": "success", "total_cost_usd": 0.1, "num_turns": 1}]
+        path.write_text("".join(json.dumps(d) + "\n" for d in lines), encoding="utf-8")
+        items = runs.chat(path, str(self.project))
+        self.assertEqual([(i["role"], i["text"]) for i in items if i["role"] != "tool"][:3],
+                         [("you", "draw it"), ("claude", "Drew it."), ("claude", "")])
+        claude = [i for i in items if i["role"] == "claude"]
+        self.assertEqual([f["name"] for f in claude[0]["files"]], ["out/chart.png"])
+        self.assertEqual((claude[0]["files"][0]["kind"], claude[1]["files"][0]["name"]), ("image", "log.txt"))
+
     def test_stop_sends_an_interrupt(self):
         sid = self.mgr.start(str(self.project), "SLOW task", "sonnet", "low")
         self.assertTrue(wait_for(lambda: "echo: SLOW" in self.mgr.stream_path(sid).read_text(encoding="utf-8")))
diff --git a/tests/test_server.py b/tests/test_server.py
index 592ee38..da05fa4 100644
--- a/tests/test_server.py
+++ b/tests/test_server.py
@@ -1,3 +1,4 @@
+import base64
 import http.client
 import json
 import sys
@@ -7,7 +8,7 @@ import time
 import unittest
 from pathlib import Path
 
-from console import brief, events, guard, levers, paths, server
+from console import attach, brief, events, guard, levers, paths, server
 
 
 class GuardTest(unittest.TestCase):
@@ -98,6 +99,30 @@ class ServerTest(unittest.TestCase):
         for page in ("/", "/style.css", "/app.js"):  # the window makes no network calls
             self.assertNotIn(b"https://", self.get(page)[1], page)
 
+    def test_image_thumbnails_from_the_transcript_and_the_folder(self):
+        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
+        folder = Path(self.tmp.name) / "proj"
+        (folder / "out").mkdir(parents=True)
+        (folder / "out" / "grid.png").write_bytes(png)
+        (folder / "notes.md").write_text("# not an image", encoding="utf-8")
+        (Path(self.tmp.name) / "secret.png").write_bytes(png)  # outside the session's folder
+        transcript = Path(self.tmp.name) / "s3.jsonl"
+        transcript.write_text(json.dumps({"type": "user", "uuid": "u-1", "message": {"role": "user", "content": [
+            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
+                                         "data": base64.b64encode(png).decode()}},
+            {"type": "text", "text": "look"}]}}) + "\n", encoding="utf-8")
+        with open(Path(self.tmp.name) / "events-2026-10-10.jsonl", "a", encoding="utf-8") as fh:
+            fh.write(json.dumps({"ts": 9e12, "event": "UserPromptSubmit", "session_id": "s3", "prompt": "look",
+                                 "cwd": str(folder), "transcript_path": str(transcript)}) + "\n")
+        self.hub.poll_once()
+        self.assertEqual(self.get("/api/image?session=s3&at=u-1&k=0"), (200, png))
+        self.assertEqual(self.get("/api/image?session=s3&path=out/grid.png"), (200, png))
+        for bad in ("at=u-1&k=1", "at=u-2&k=0", "at=u-1&k=x", "path=notes.md", "path=../secret.png",
+                    "path=" + str(Path(self.tmp.name) / "secret.png")):
+            self.assertEqual(self.get("/api/image?session=s3&" + bad)[0], 404, bad)
+        self.assertEqual(self.get("/api/image?session=nope&at=u-1&k=0")[0], 404)
+        self.assertEqual(self.get("/api/image?session=s3&at=u-1&k=0", host="evil.example")[0], 403)
+
     def test_hub_reads_transcripts_for_the_estimate(self):
         transcript = Path(self.tmp.name) / "s2.jsonl"
         transcript.write_text(json.dumps({"type": "assistant", "timestamp": "2026-10-10T10:00:00Z", "message": {
@@ -232,6 +257,44 @@ class RunServerTest(unittest.TestCase):
         while time.time() < end and (self.session(sid) is None or self.session(sid)["run_live"]):
             time.sleep(0.1)
 
+    def test_run_and_continue_take_files(self):
+        big = {"name": "shot.png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x01" * 1024 * 1024).decode()}
+        status, data = self.call("/api/run", {"project_dir": str(self.project), "prompt": "look", "files": [big]})
+        self.assertEqual(status, 200)  # over the 256 KB of the other routes
+        sid = data["session"]
+        self.wait_idle(sid)
+        chat = self.call(f"/api/chat?session={sid}")[1]
+        self.assertEqual(chat["items"][0]["files"], [{"name": "shot.png", "kind": "image", "bytes": 1024 * 1024 + 8}])
+        note = {"name": "n.txt", "data": base64.b64encode(b"more").decode()}
+        self.assertEqual(self.call("/api/continue", {"session": sid, "text": "and this", "files": [note]}),
+                         (200, {"session": sid}))
+        self.wait_idle(sid)
+        you = [i for i in self.call(f"/api/chat?session={sid}")[1]["items"] if i["role"] == "you"]
+        self.assertEqual(you[1]["files"][0]["name"], "n.txt")
+        zip_ = {"name": "a.docx", "data": base64.b64encode(b"PK\x03\x04\x14\x00\x00").decode()}
+        status, data = self.call("/api/run", {"project_dir": str(self.project), "prompt": "x", "files": [zip_]})
+        self.assertEqual((status, data["error"]), (400, "a.docx: send " + attach.SENDABLE))
+
+    def test_prep_job_keeps_files_for_its_run(self):
+        shot = {"name": "shot.png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\nPIXELS").decode()}
+        old = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "fix it", "files": [shot]})[1]["job"]
+        job = self.prep_job(old)
+        self.assertEqual(job["attached"], [{"name": "shot.png", "kind": "image", "bytes": 14}])
+        self.assertNotIn("files", job)  # the bytes never reach the snapshot
+        self.assertNotIn(shot["data"], json.dumps(self.hub.snapshot()))
+        self.assertEqual(job["card"]["raw"], "fix it")  # as typed; Prep read the names too:
+        saved = json.loads((self.folder / "preps" / f"{old}.json").read_text(encoding="utf-8"))
+        self.assertTrue(saved["raw"].endswith("sent with the run: shot.png (image)."))
+        new = self.call("/api/prep", {"project_dir": str(self.project), "prompt": "fix it", "files_from": old})[1]["job"]
+        self.assertEqual(self.prep_job(new)["attached"][0]["name"], "shot.png")  # Try again keeps them
+        card = self.prep_job(new)["card"]
+        sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": card["prompt"], "prep": card["id"]})[1]["session"]
+        self.wait_idle(sid)
+        self.assertEqual(self.call(f"/api/chat?session={sid}")[1]["items"][0]["files"][0]["name"], "shot.png")
+        raw = self.call("/api/run", {"project_dir": str(self.project), "prompt": "fix it", "files_from": old})[1]["session"]
+        self.wait_idle(raw)  # Run raw from a card: its job's files too
+        self.assertEqual(self.call(f"/api/chat?session={raw}")[1]["items"][0]["files"][0]["name"], "shot.png")
+
     def test_continue_resumes_and_stop_interrupts(self):
         sid = self.call("/api/run", {"project_dir": str(self.project), "prompt": "SLOW one"})[1]["session"]
         self.assertEqual(self.call("/api/continue", {"session": sid, "text": "go"})[0], 409)  # still running
diff --git a/tests/test_transcript.py b/tests/test_transcript.py
index 5bfbe39..133d1a8 100644
--- a/tests/test_transcript.py
+++ b/tests/test_transcript.py
@@ -1,3 +1,4 @@
+import base64
 import json
 import tempfile
 import unittest
@@ -62,6 +63,47 @@ class TranscriptTest(unittest.TestCase):
         got = transcript.turns(self.path, limit=50)
         self.assertTrue(0 < len(got) < 40 and got[-1]["text"].startswith("turn 39"))
 
+    def test_files_fred_attached_and_files_claude_wrote(self):
+        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "A" * 400}}
+        doc = {"type": "document", "title": "spec.md",
+               "source": {"type": "text", "media_type": "text/plain", "data": "# spec"}}
+        pdf = {"type": "document", "title": "brief.pdf",
+               "source": {"type": "base64", "media_type": "application/pdf", "data": "B" * 40}}
+        write = {"type": "tool_use", "name": "Write", "input": {"file_path": "D:/p/out/chart.png", "content": "x"}}
+        self.write(
+            user([image, image, {"type": "text", "text": "match these"}], imagePasteIds=[1, 2]),
+            user([doc, pdf]),  # files with no words still make a turn
+            claude([write]) | {"cwd": "D:/p"},
+            claude([{"type": "tool_use", "name": "Write", "input": {"file_path": "D:/p/notes.md"}}]) | {"cwd": "D:/p"},
+            claude([{"type": "tool_use", "name": "Write", "input": {"file_path": "C:/Temp/smoke.py"}}]) | {"cwd": "D:/p"},
+            claude([{"type": "text", "text": "Done."}]),
+            claude([{"type": "tool_use", "name": "Edit", "input": {"file_path": "D:/p/a.py"}}]),
+            claude([write]) | {"cwd": "D:/p"},
+            user("next"),
+        )
+        got = transcript.turns(self.path, limit=10)
+        self.assertEqual([(t["role"], t["text"]) for t in got],
+                         [("you", "match these"), ("you", ""), ("claude", "Done."), ("claude", ""), ("you", "next")])
+        self.assertEqual(got[0]["files"], [{"name": "image 1", "kind": "image", "bytes": 300},
+                                           {"name": "image 2", "kind": "image", "bytes": 300}])
+        self.assertEqual(got[1]["files"], [{"name": "spec.md", "kind": "text", "bytes": 6},
+                                           {"name": "brief.pdf", "kind": "pdf", "bytes": 30}])
+        self.assertEqual([(f["name"], f["kind"]) for f in got[2]["files"]],
+                         [("out/chart.png", "image"), ("notes.md", "file")])
+        self.assertEqual(got[3]["files"][0]["name"], "out/chart.png")  # wrote, then Fred spoke: its own row
+        self.assertEqual(got[4]["files"], [])
+
+    def test_a_pasted_image_says_where_it_is_for_its_thumbnail(self):
+        png = b"\x89PNG\r\n\x1a\n" + b"\x01" * 30
+        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png",
+                                             "data": base64.b64encode(png).decode()}}
+        self.write(user([{"type": "text", "text": "see"}, image], uuid="u-7"))
+        self.assertEqual(transcript.turns(self.path)[0]["files"][0]["at"], ["u-7", 1])
+        self.assertEqual(transcript.image(self.path, "u-7", 1), (png, "image/png"))
+        self.assertIsNone(transcript.image(self.path, "u-7", 0))  # the text block
+        self.assertIsNone(transcript.image(self.path, "u-8", 1))
+        self.assertIsNone(transcript.image(Path(self.tmp.name) / "none.jsonl", "u-7", 1))
+
     def test_masks_and_ignores_other_files(self):
         self.write(user("use key sk-abcdefghijkl1234 now"))
         self.assertEqual(transcript.turns(self.path)[0]["text"], "use key *** now")
```

## Task 2 diff (window)

```diff
diff --git a/web/app.js b/web/app.js
index c4ca62f..31becaa 100644
--- a/web/app.js
+++ b/web/app.js
@@ -321,6 +321,7 @@ function showPage(name) {
 
 async function openSession(id, list = "chat") {
   if (form === "pill") await setForm("open");
+  if (id !== openId) att.answer = att.fu = [];  // files were for the other session's boxes
   openId = id;
   tab = list;
   tlMin = -1;
@@ -460,8 +461,10 @@ function renderCompose() {
   else if (!project) html = "To run: start a Claude Code session in a project first";
   else if (!runnable()) html = `<span>Runs are off in ${chipHtml}: a run would use this repo's hooks and settings without asking.</span>
     <button class="btn sm" data-go="allow">Allow runs</button>`;
-  else html = `<span>in</span>${chipHtml}<span class="hint"><span class="kbd">Enter</span>Prep</span>`;
+  else html = `<span>in</span>${chipHtml}<button class="btn sm" data-attach="compose" title="Images, PDF or text files (or paste, or drop them on the box)">Attach</button>
+    <span class="hint"><span class="kbd">Enter</span>Prep</span>`;
   setHtml($("c-say"), html);
+  setHtml($("files-compose"), filesHtml("compose"));
   setHtml($("preps"), preps().map(prepJobHtml).join(""));
   spin();
   setHtml($("prepfail"), fail ? `<div class="card r" style="cursor:default"><div class="l1"><span class="st r">× FAILED</span><span class="t">${esc(fail.title)}</span></div>
@@ -486,7 +489,7 @@ function prepJobHtml(j) {
   const c = j.card, goal = c.fields.goal || c.raw;
   return `<div class="card" data-prep="${id}" data-pdo="open" tabindex="0" role="button" aria-label="${esc("Prep ready: " + goal)}">
     <div class="l1"><span class="st g">&#9654; Ready to run</span><span class="t">${esc(goal)}</span><span class="age m">${ago(snap.now - c.ts)}</span></div>
-    <div class="l2 m"><span class="who">${where}<span class="route"> · ${esc(c.route.model)} ${esc(c.route.effort)}</span></span>
+    <div class="l2 m"><span class="who">${where}<span class="route"> · ${esc(c.route.model)} ${esc(c.route.effort)}</span>${j.attached.length ? ` · ${j.attached.length} file${j.attached.length === 1 ? "" : "s"}` : ""}</span>
     <span class="cost">${money(c.cost)}</span></div></div>`;
 }
 
@@ -494,9 +497,15 @@ async function prepJob(id, what) {
   const j = preps().find((x) => x.id === id);
   if (!j) return;
   if (what === "open") { if (j.card) { card = j.card; showPrep(); } return; }
+  if (what === "retry") await startPrep(j.project_dir, j.raw, [], id);  // the new job takes the old one's files first
   await dropPrep(id);
-  if (what === "edit") putBack(j.raw);
-  if (what === "retry") startPrep(j.project_dir, j.raw);
+  if (what === "edit") { putBack(j.raw); if (j.attached.length) filesNotKept(); }
+}
+
+function jobFiles(id) { const j = preps().find((x) => x.id === id); return j ? j.attached.length : 0; }
+function filesNotKept() {  // a job's files live in the service, not in this page: Edit cannot bring them back
+  fail = { title: "Files not kept", msg: "Edit puts back the text only: attach the files again.", retry: "" };
+  renderCompose();
 }
 
 function dropPrep(id) { return api("/api/prep/drop", { job: id }).catch(() => {}); }
@@ -509,6 +518,75 @@ function putBack(text) {  // a Prep's request back in the composer, to edit it
   $("c-prompt").focus();
 }
 
+// -- attachments: files sent inline with a prompt (console/attach.py checks them) ------------------
+const ATTACH_FILES = 5, ATTACH_BYTES = 5 * 1024 * 1024;  // attach.MAX_FILES, attach.MAX_BYTES
+const THUMB_PX = 160, THUMB_MAX = 24 * 1024;              // drawn here; attach.THUMB_MAX keeps it
+const att = { compose: [], answer: [], fu: [] };          // per prompt box: {name, kind, bytes, data (base64), thumb}
+let pickFor = "";                                         // the box the file dialog adds to
+function sizeText(n) { return n < 1024 ? n + " B" : n < 1048576 ? Math.round(n / 1024) + " KB" : (n / 1048576).toFixed(1) + " MB"; }
+function fileKind(f) { return f.type.startsWith("image/") ? "image" : f.type === "application/pdf" ? "pdf" : "text"; }
+async function makeThumb(f) {  // a small JPEG of an image, kept with the prompt for the Chat ("" when it cannot be drawn)
+  try {
+    const bmp = await createImageBitmap(f), r = Math.min(1, THUMB_PX / Math.max(bmp.width, bmp.height));
+    const c = document.createElement("canvas");
+    c.width = Math.max(1, Math.round(bmp.width * r));
+    c.height = Math.max(1, Math.round(bmp.height * r));
+    const g = c.getContext("2d");
+    g.fillStyle = "#fff";  // JPEG has no alpha: transparent parts on white
+    g.fillRect(0, 0, c.width, c.height);
+    g.drawImage(bmp, 0, 0, c.width, c.height);
+    bmp.close();
+    const url = c.toDataURL("image/jpeg", 0.72);
+    return url.length <= THUMB_MAX ? url : "";
+  } catch (e) { return ""; }
+}
+function fileChip(f, remove = "", src = "") {  // `src`: the thumbnail (a kept data URL, or /api/image)
+  src = src || f.thumb || "";
+  return `<li class="file">${src ? `<img class="thumb" src="${esc(src)}" alt="" loading="lazy" title="Click to enlarge">` : ""}<span class="k">${esc(f.kind)}</span><span class="nm" title="${esc(f.name)}">${esc(f.name)}</span>${f.bytes == null ? "" : `<span class="m">${sizeText(f.bytes)}</span>`}${remove}</li>`;
+}
+function filesHtml(key) {  // the chips under a prompt box, each with its remove button
+  return att[key].map((f, k) => fileChip(f, `<button data-unattach="${key}" data-k="${k}" aria-label="Remove ${esc(f.name)}" title="Remove">&#10005;</button>`)).join("");
+}
+function imageSrc(f, role, sid) {  // a transcript's pasted image, or an image Claude wrote in the folder: read by the service
+  if (!sid || f.kind !== "image" || f.thumb) return "";
+  const q = "/api/image?session=" + encodeURIComponent(sid);
+  if (f.at) return `${q}&at=${encodeURIComponent(f.at[0])}&k=${f.at[1]}`;
+  return role === "claude" ? `${q}&path=${encodeURIComponent(f.name)}` : "";
+}
+function chatFiles(files, role, sid = "") {  // a Chat turn's files: what Fred attached, or what Claude wrote before its words
+  if (!files || !files.length) return "";
+  return `<ul class="files" aria-label="${role === "claude" ? "Files Claude wrote" : "Attached files"}">${role === "claude" ? '<li class="by">wrote</li>' : ""}${files.map((f) => fileChip(f, "", imageSrc(f, role, sid))).join("")}</ul>`;
+}
+function wire(list) { return list.map(({ name, data, thumb }) => ({ name, data, thumb })); }
+function sendable(key) { return wire(att[key]); }
+function boxKey(el) { return el.closest(".compose") ? "compose" : el.closest(".askbox") ? "answer" : el.closest("#levers") && $("fu") ? "fu" : ""; }
+function attachSay(key, text) {
+  if (key === "compose") { fail = { title: "Attach failed", msg: text, retry: "" }; renderCompose(); }
+  else { const m = $(key === "answer" ? "a-msg" : "f-msg"); if (m) m.innerHTML = `<span class="r">${esc(text)}</span>`; }
+}
+function paintFiles(key) {
+  if (key === "compose") renderCompose();
+  else if (key === "answer") renderSession();
+  else { leversSig = ""; const s = current(); if (s) renderLevers(s).catch(() => {}); }
+}
+async function addFiles(key, list) {
+  if (!key) return;
+  for (const f of list) {
+    if (att[key].length >= ATTACH_FILES) { attachSay(key, `at most ${ATTACH_FILES} files per prompt`); break; }
+    if (f.size > ATTACH_BYTES) { attachSay(key, `${f.name}: over 5 MB`); continue; }
+    const data = await new Promise((ok, ko) => {
+      const r = new FileReader();
+      r.onload = () => ok(String(r.result).split(",")[1] || "");
+      r.onerror = () => ko(r.error);
+      r.readAsDataURL(f);
+    }).catch(() => null);
+    if (data === null) { attachSay(key, `${f.name}: could not be read`); continue; }
+    const kind = fileKind(f), thumb = kind === "image" ? await makeThumb(f) : "";
+    att[key].push({ name: f.name || "pasted." + (f.type.split("/")[1] || "png"), kind, bytes: f.size, data, thumb });
+  }
+  paintFiles(key);
+}
+
 let loadingTimer = null;
 function spin() {  // the loading cells step while the composer waits or a Prep job runs
   const want = (!!busy || preps().some((j) => j.state === "running")) && !matchMedia("(prefers-reduced-motion: reduce)").matches;
@@ -540,25 +618,32 @@ function doPrep() {  // the box empties at once; the Prep runs in the service an
   draft = "";
   $("c-prompt").value = "";
   saveDraft();
-  startPrep(project, text);
+  const files = att.compose;  // they wait with the job in the service until its card runs
+  att.compose = [];
+  renderCompose();  // the chips leave with the text, before the service answers
+  startPrep(project, text, files);
 }
 
-async function startPrep(projectDir, text) {
+async function startPrep(projectDir, text, files = [], from = "") {  // `from`: Try again takes that job's files
   fail = null;
   try {
-    await api("/api/prep", { project_dir: projectDir, prompt: text });
+    await api("/api/prep", { project_dir: projectDir, prompt: text, files: wire(files), files_from: from });
   } catch (e) {
     if (!$("c-prompt").value.trim()) { draft = text; $("c-prompt").value = text; saveDraft(); }  // nothing typed since: the text comes back
+    if (!att.compose.length) att.compose = files;
     fail = { title: "Prep failed", msg: e.message, retry: "prep" };
   }
   renderCompose();
 }
 
-async function doRun(projectDir, prompt, model, effort, prepId) {  // true once the run started
+async function doRun(projectDir, prompt, model, effort, prepId, from = "") {  // true once the run started
   if (busy) return false;
+  const mine = !prepId && !from;  // from the composer: its files go now; a card's wait with its job
   setBusy("Starting the run ...");
   try {
-    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "" });
+    const r = await api("/api/run", { project_dir: projectDir, prompt, model, effort, prep: prepId || "",
+      files: mine ? sendable("compose") : [], files_from: from });
+    if (mine) att.compose = [];
     card = null;
     setBusy("");
     openSession(r.session, "chat");
@@ -658,6 +743,7 @@ function showPrep() {
   $("crumb").textContent = "Prep / " + projectName(card.project_dir);
   $("pscroll").innerHTML = `
     <div class="blk"><span class="lbl">You typed</span><div class="text">${esc(card.raw)}</div></div>
+    ${jobFiles(card.id) ? `<div class="blk"><span class="lbl">Sent with the run</span>${chatFiles(preps().find((x) => x.id === card.id).attached, "you")}</div>` : ""}
     ${f.where ? `<div class="blk"><span class="lbl">Scouted</span><div class="m">${esc(f.where)}</div></div>` : ""}
     <div class="blk"><span class="lbl">Enhanced prompt (edit freely)</span>
       <textarea id="p-prompt" class="in m" rows="9" spellcheck="false">${esc(card.prompt)}</textarea></div>
@@ -679,9 +765,9 @@ async function prepAct(name) {  // Run drops the card's job in the service; Run
   if (busy || !card) return;
   const c = card;
   if (name === "run") doRun(c.project_dir, $("p-prompt").value.trim(), $("p-model").value, $("p-effort").value, c.id);
-  if (name === "raw" && await doRun(c.project_dir, c.raw, cfg.default_model, cfg.default_effort, "")) dropPrep(c.id);
+  if (name === "raw" && await doRun(c.project_dir, c.raw, cfg.default_model, cfg.default_effort, "", c.id)) dropPrep(c.id);
   if (name === "back") { card = null; showPage("list"); }
-  if (name === "edit") { card = null; await dropPrep(c.id); putBack(c.raw); }
+  if (name === "edit") { card = null; const had = jobFiles(c.id); await dropPrep(c.id); putBack(c.raw); if (had) filesNotKept(); }
   if (name === "cancel") { card = null; dropPrep(c.id); showPage("list"); }
 }
 
@@ -709,7 +795,9 @@ function askBlock(s) {
       : `Your answer runs in a window copy of this chat. The ${s.source} chat stays as it is.`;
     return `<div class="askbox"><div class="q">${esc(s.stop_question)}</div>
       <textarea class="in" id="answer" rows="3" aria-label="Answer" placeholder="${esc(where)}"></textarea>
+      <ul class="files" aria-label="Attached files">${filesHtml("answer")}</ul>
       <div class="lr"><button class="btn you" data-act="answer">Send answer</button>
+      <button class="btn" data-attach="answer" title="Images, PDF or text files (or paste, or drop them on the box)">Attach</button>
       ${s.window && !s.run_live ? '<button class="btn" data-act="terminal">Open in terminal</button>' : ""}</div>
       <div id="a-msg" class="say"></div></div>`;
   }
@@ -882,9 +970,9 @@ async function renderProc(s) {
     const turns = chat.items.filter((i) => i.role !== "tool");
     const foot = chat.source === "window"
       ? "Streamed from this window run." + (chat.start_commit ? ` start ${esc(chat.start_commit.slice(0, 7))} · ${chat.changed == null ? "?" : chat.changed} file(s) changed since.` : "")
-      : `Read from the ${esc(s.source === "?" ? "chat" : s.source)} transcript, in words; tool output stays in Steps.`;
+      : `Read from the ${esc(s.source === "?" ? "chat" : s.source)} transcript, in words and files; tool output stays in Steps.`;
     body = `<div class="chat">${turns.map((i) => `<div class="turn ${i.role}"><span class="lbl">${i.role === "you" ? "You" : i.role === "claude" ? "Claude" : esc(i.role)}${i.ts ? " · " + hhmm(i.ts) : ""}</span>
-      ${i.role === "claude" ? chatHtml(i.text) : `<p>${esc(i.text)}</p>`}</div>`).join("") || '<p class="none">Nothing to show yet. A VS Code or terminal chat shows its turns once a prompt has named its transcript.</p>'}
+      ${i.role === "claude" ? chatHtml(i.text) : i.text ? `<p>${esc(i.text)}</p>` : ""}${chatFiles(i.files, i.role, s.id)}</div>`).join("") || '<p class="none">Nothing to show yet. A VS Code or terminal chat shows its turns once a prompt has named its transcript.</p>'}
       <p class="src">${foot}</p></div>`;
   }
   const html = `<div class="tabs" role="tablist" aria-label="Process">${TABS.map(([id, nm]) =>
@@ -907,7 +995,8 @@ async function renderLevers(s) {
   let html = "";
   if (lv && !lv.continue && !s.stop_question) {
     html += `<div class="lr"><input id="fu" aria-label="Follow-up" placeholder="${lv.fork ? "Follow-up (runs in a window copy)" : "Follow-up"}">
-      <button class="btn go" data-act="continue">Continue</button></div>`;
+      <button class="btn" data-attach="fu" title="Images, PDF or text files (or paste, or drop them on the box)">Attach</button>
+      <button class="btn go" data-act="continue">Continue</button></div><ul class="files" aria-label="Attached files">${filesHtml("fu")}</ul>`;
   }
   let buttons = "";
   if (s.run_live) buttons += '<button class="btn stop" data-act="stop">Stop</button>';
@@ -979,9 +1068,10 @@ async function act(name, button) {
     if (name === "done") await api("/api/done", { session: s.id });
     if (name === "resume") r = await api("/api/continue", { session: s.id, text: RESUME_TEXT, confirm });
     if (name === "continue" || name === "answer") {
-      const text = $(name === "answer" ? "answer" : "fu").value.trim();
+      const key = name === "answer" ? "answer" : "fu", text = $(key).value.trim();
       if (!text) { button.disabled = false; return; }
-      r = await api("/api/continue", { session: s.id, text, confirm });
+      r = await api("/api/continue", { session: s.id, text, confirm, files: sendable(key) });
+      att[key] = [];
     }
     if (["verify", "handoff", "escalate"].includes(name)) r = await api("/api/" + name, { session: s.id, confirm });
     if (r && r.session !== s.id) { openSession(r.session, "chat"); return; }  // a window copy (fork)
@@ -1217,10 +1307,13 @@ async function rawRun() {
 
 document.addEventListener("click", (e) => {
   if (!$("pop").hidden && !e.target.closest("#pop") && !e.target.closest("[data-pick]")) closePicker();
-  const t = e.target.closest("[data-prep],[data-go],[data-open],[data-tab],[data-min],[data-act],[data-pact],[data-do],[data-here],[data-proj],[data-pick],[data-step],#brief,#today");
+  if (e.target.matches("img.thumb")) { e.target.closest(".file").classList.toggle("open"); return; }  // enlarge in place
+  const t = e.target.closest("[data-prep],[data-go],[data-open],[data-tab],[data-min],[data-act],[data-pact],[data-do],[data-here],[data-proj],[data-pick],[data-step],[data-attach],[data-unattach],#brief,#today");
   if (!t) return;
   if (t.matches(".card") && e.target.closest("[data-stay]")) return;  // typing an answer in a card
-  if (t.dataset.prep) prepJob(t.dataset.prep, t.dataset.pdo);
+  if (t.dataset.attach) { pickFor = t.dataset.attach; $("filepick").value = ""; $("filepick").click(); }
+  else if (t.dataset.unattach) { att[t.dataset.unattach].splice(Number(t.dataset.k), 1); paintFiles(t.dataset.unattach); }
+  else if (t.dataset.prep) prepJob(t.dataset.prep, t.dataset.pdo);
   else if (t.dataset.go) go(t.dataset.go, t);
   else if (t.dataset.do) unblock(t);
   else if (t.dataset.open) openSession(t.dataset.open);
@@ -1245,6 +1338,20 @@ document.addEventListener("click", (e) => {
   }
 });
 
+$("filepick").addEventListener("change", (e) => addFiles(pickFor, [...e.target.files]));
+document.addEventListener("error", (e) => {  // an image gone from the transcript or the folder: the chip stays, without it
+  if (e.target instanceof HTMLImageElement && e.target.matches("img.thumb")) e.target.remove();
+}, true);
+document.addEventListener("paste", (e) => {  // a pasted screenshot or copied file joins the box's files
+  const files = [...((e.clipboardData && e.clipboardData.files) || [])], key = boxKey(e.target);
+  if (files.length && key) { e.preventDefault(); addFiles(key, files); }
+});
+document.addEventListener("dragover", (e) => { e.preventDefault(); });  // a file dropped anywhere must not open in the page
+document.addEventListener("drop", (e) => {
+  e.preventDefault();
+  if (e.dataTransfer && e.dataTransfer.files.length) addFiles(boxKey(e.target), [...e.dataTransfer.files]);
+});
+
 document.addEventListener("dblclick", (e) => {
   if (e.target.closest(".pill .sp")) setForm("open");
   else if (e.target.closest(".top .sp")) setForm("pill");
diff --git a/web/index.html b/web/index.html
index 23f99a2..71253a7 100644
--- a/web/index.html
+++ b/web/index.html
@@ -31,9 +31,11 @@
       <div id="prepfail"></div>
       <div class="compose">
         <div class="lr"><textarea id="c-prompt" rows="1" spellcheck="false" aria-label="New task"
-          title="Enter = Prep · Ctrl+Enter = Run raw · Shift+Enter = new line"></textarea></div>
+          title="Enter = Prep · Ctrl+Enter = Run raw · Shift+Enter = new line · paste or drop files to attach"></textarea></div>
+        <ul id="files-compose" class="files" aria-label="Attached files"></ul>
         <div id="c-say" class="say"></div>
       </div>
+      <input id="filepick" type="file" multiple hidden>
     </section>
 
     <section data-page="session" hidden>
diff --git a/web/style.css b/web/style.css
index 81c47b8..9bd31cd 100644
--- a/web/style.css
+++ b/web/style.css
@@ -373,6 +373,23 @@ h2 { font: 600 17px/1.3 var(--ui); margin: 0; text-wrap: balance; overflow-wrap:
 .turn th.right, .turn td.right { text-align: right; font-variant-numeric: tabular-nums; }
 .turn.note p, .turn.result p { color: var(--mut); font: 12px var(--mono); }
 .chat .src { font: 11px var(--mono); color: var(--mut); margin: 0; }
+
+/* attached files: chips under a prompt box (with a remove button) and under a Chat turn */
+.files { display: flex; flex-wrap: wrap; gap: 4px; min-width: 0; margin: 0; padding: 0; list-style: none; }
+.files:empty { display: none; }
+.file { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; min-height: 22px; padding: 1px 7px;
+  border: 1px solid var(--line); border-radius: 4px; background: var(--raise); font: 11px var(--mono); color: var(--ink); }
+.file .k { color: var(--mut); text-transform: uppercase; letter-spacing: .04em; }
+.file .nm { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
+.file .m { color: var(--mut); font-variant-numeric: tabular-nums; white-space: nowrap; }
+.file button { margin-right: -5px; padding: 0 4px; border: 0; background: none; color: var(--mut); font: inherit; cursor: pointer; }
+.file button:hover { color: var(--ink); }
+.files .by { align-self: center; font: 11px var(--mono); color: var(--mut); }
+.file .thumb { flex: none; width: 40px; height: 40px; margin: 2px 0 2px -4px; object-fit: cover; border-radius: 3px;
+  background: var(--off); cursor: zoom-in; }
+.file.open { flex-wrap: wrap; }
+.file.open .thumb { order: 9; flex-basis: 100%; width: auto; height: auto; max-width: 100%; max-height: 60vh;
+  margin: 4px 0; object-fit: contain; cursor: zoom-out; }
 .levers { flex: none; border-top: 1px solid var(--line); padding: 8px 10px; display: grid; gap: 6px; }
 .levers:empty { display: none; }
 
```
