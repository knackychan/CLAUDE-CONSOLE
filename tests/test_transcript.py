import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from console import transcript
from tests import fixtures


def user(content, **extra):
    return {"type": "user", "timestamp": "2026-10-10T10:00:00Z", "message": {"role": "user", "content": content},
            **extra}


def claude(blocks):
    return {"type": "assistant", "timestamp": "2026-10-10T10:00:05Z", "message": {"role": "assistant", "content": blocks}}


class TranscriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "s1.jsonl"

    def write(self, *recs, raw=""):
        self.path.write_text("".join(json.dumps(r) + "\n" for r in recs) + raw, encoding="utf-8")

    def test_find_by_id(self):
        root = Path(self.tmp.name)
        p = root / "D--WORK-APP" / "0b1c2d3e-aaaa-bbbb-cccc-111122223333.jsonl"
        p.parent.mkdir()
        p.write_text("", encoding="utf-8")
        self.assertEqual(transcript.find(root, "0b1c2d3e-aaaa-bbbb-cccc-111122223333"), p)
        self.assertIsNone(transcript.find(root, "../x"))
        self.assertIsNone(transcript.find(root, "0b1c2d3e-0000-0000-0000-000000000000"))

    def test_a_long_reply_is_whole_up_to_the_limit_then_marked_cut(self):
        self.write(claude([{"type": "text", "text": "a" * 5000}]),
                   claude([{"type": "text", "text": "b" * (transcript.TURN_MAX + 10)}]))
        first, second = transcript.turns(self.path)
        self.assertEqual(len(first["text"]), 5000)
        self.assertTrue(second["text"].endswith("[cut here, the full text is in the transcript]"))
        self.assertEqual(second["text"].count("b"), transcript.TURN_MAX)

    def test_words_only(self):
        self.write(
            user("fix the retry"),
            claude([{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "Looking."},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "a.py"}}]),
            user([{"type": "tool_result", "tool_use_id": "t1", "content": "file body"}]),
            user([{"type": "text", "text": "<system-reminder>skills</system-reminder>"},
                  {"type": "text", "text": "now the tests"}]),
            user([{"type": "text", "text": "Base directory for this skill: x"}], isMeta=True),
            claude([{"type": "text", "text": "side"}]) | {"isSidechain": True},
            {"type": "ai-title", "title": "x"},
            user("<pasted_content id=\"ab\">keep this</pasted_content>"),
            user([{"type": "text", "text": "[Request interrupted by user]"}]),
        )
        got = transcript.turns(self.path)
        self.assertEqual([(t["role"], t["text"]) for t in got], [
            ("you", "fix the retry"), ("claude", "Looking."), ("you", "now the tests"),
            ("you", "keep this"), ("note", "stopped")])
        self.assertEqual(got[0]["ts"], 1791626400.0)

    def test_last_six_and_a_cut_first_line(self):
        self.write(*[user(f"turn {k} " + "x" * 200) for k in range(40)], raw='{"type": "user", "mess')
        got = transcript.turns(self.path)
        self.assertEqual([t["text"][:8] for t in got], [f"turn {k} " for k in range(34, 40)])
        old = transcript.TAIL_BYTES
        transcript.TAIL_BYTES = 3000  # reads from the middle of a line: that line is dropped
        self.addCleanup(setattr, transcript, "TAIL_BYTES", old)
        got = transcript.turns(self.path, limit=50)
        self.assertTrue(0 < len(got) < 40 and got[-1]["text"].startswith("turn 39"))

    def test_files_fred_attached_and_files_claude_wrote(self):
        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "A" * 400}}
        doc = {"type": "document", "title": "spec.md",
               "source": {"type": "text", "media_type": "text/plain", "data": "# spec"}}
        pdf = {"type": "document", "title": "brief.pdf",
               "source": {"type": "base64", "media_type": "application/pdf", "data": "B" * 40}}
        write = {"type": "tool_use", "name": "Write", "input": {"file_path": "D:/p/out/chart.png", "content": "x"}}
        self.write(
            user([image, image, {"type": "text", "text": "match these"}], imagePasteIds=[1, 2]),
            user([doc, pdf]),  # files with no words still make a turn
            claude([write]) | {"cwd": "D:/p"},
            claude([{"type": "tool_use", "name": "Write", "input": {"file_path": "D:/p/notes.md"}}]) | {"cwd": "D:/p"},
            claude([{"type": "tool_use", "name": "Write", "input": {"file_path": "C:/Temp/smoke.py"}}]) | {"cwd": "D:/p"},
            claude([{"type": "text", "text": "Done."}]),
            claude([{"type": "tool_use", "name": "Edit", "input": {"file_path": "D:/p/a.py"}}]),
            claude([write]) | {"cwd": "D:/p"},
            user("next"),
        )
        got = transcript.turns(self.path, limit=10)
        self.assertEqual([(t["role"], t["text"]) for t in got],
                         [("you", "match these"), ("you", ""), ("claude", "Done."), ("claude", ""), ("you", "next")])
        self.assertEqual(got[0]["files"], [{"name": "image 1", "kind": "image", "bytes": 300},
                                           {"name": "image 2", "kind": "image", "bytes": 300}])
        self.assertEqual(got[1]["files"], [{"name": "spec.md", "kind": "text", "bytes": 6},
                                           {"name": "brief.pdf", "kind": "pdf", "bytes": 30}])
        self.assertEqual([(f["name"], f["kind"]) for f in got[2]["files"]],
                         [("out/chart.png", "image"), ("notes.md", "file")])
        self.assertEqual(got[3]["files"][0]["name"], "out/chart.png")  # wrote, then Fred spoke: its own row
        self.assertEqual(got[4]["files"], [])

    def test_a_pasted_image_says_where_it_is_for_its_thumbnail(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x01" * 30
        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": base64.b64encode(png).decode()}}
        self.write(user([{"type": "text", "text": "see"}, image], uuid="u-7"))
        self.assertEqual(transcript.turns(self.path)[0]["files"][0]["at"], ["u-7", 1])
        self.assertEqual(transcript.image(self.path, "u-7", 1), (png, "image/png"))
        self.assertIsNone(transcript.image(self.path, "u-7", 0))  # the text block
        self.assertIsNone(transcript.image(self.path, "u-8", 1))
        self.assertIsNone(transcript.image(Path(self.tmp.name) / "none.jsonl", "u-7", 1))

    def test_masks_and_ignores_other_files(self):
        self.write(user("use key sk-abcdefghijkl1234 now"))
        self.assertEqual(transcript.turns(self.path)[0]["text"], "use key *** now")
        self.assertEqual(transcript.turns(Path(self.tmp.name) / "none.jsonl"), [])
        (Path(self.tmp.name) / "notes.txt").write_text("{}", encoding="utf-8")
        self.assertEqual(transcript.turns(Path(self.tmp.name) / "notes.txt"), [])
        self.assertEqual(transcript.turns(None), [])

    def test_first_prompt(self):
        self.write(
            user("<system-reminder>rules</system-reminder>") | {"isMeta": True},
            user([{"type": "tool_result", "tool_use_id": "t0", "content": "x"}]),
            user([{"type": "text", "text": "[Request interrupted by user]"}]),
            user("start the cells drawer, key sk-abcdefghijkl1234"),
            user("second prompt"),
        )
        self.assertEqual(transcript.first_prompt(self.path), "start the cells drawer, key ***")
        self.write(claude([{"type": "text", "text": "hi"}]))
        self.assertEqual(transcript.first_prompt(self.path), "")
        self.assertEqual(transcript.first_prompt(Path(self.tmp.name) / "none.jsonl"), "")
        self.assertEqual(transcript.first_prompt(None), "")

    def test_first_prompt_reads_only_the_head(self):
        self.write(user("x" * 3000), user("later"), raw='{"type": "user", "mess')
        old = transcript.HEAD_BYTES
        transcript.HEAD_BYTES = 1000  # the first line is cut: it is skipped, the next ones are not read
        self.addCleanup(setattr, transcript, "HEAD_BYTES", old)
        self.assertEqual(transcript.first_prompt(self.path), "")


class OtherHarnessTranscriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_codex_turns(self):
        path = fixtures.codex_rollout(self.dir / "rollout.jsonl")
        got = transcript.codex_turns(path)
        self.assertEqual([(t["role"], t["text"]) for t in got],
                         [("you", "fix the retry on line 9"), ("claude", "Looking at the retry.")])
        self.assertIsNone(got[0]["ts"])  # this fixture carries no timestamp
        self.assertEqual(transcript.codex_turns(str(self.dir / "none.jsonl")), [])
        self.assertEqual(transcript.codex_turns(None), [])

    def test_cmd_turns(self):
        path = fixtures.cmd_transcript(self.dir / "c1.jsonl")
        got = transcript.cmd_turns(path)
        self.assertEqual([(t["role"], t["text"]) for t in got], [("you", "audit the project"),
                                                                 ("claude", "# Report\n\nDone.")])
        self.assertEqual(transcript.cmd_turns(str(self.dir / "none.jsonl")), [])

    def _opencode_db(self, name="oc.db", rows=4, table=True) -> Path:
        db = self.dir / name
        con = sqlite3.connect(str(db))
        if table:
            con.execute("CREATE TABLE session_message (id text, session_id text, type text, seq integer,"
                        " time_created integer, data text)")
            records = [("user", '{"text": "start the drawer"}'),
                       ("assistant", '{"content": [{"type": "reasoning", "text": "hmm"},'
                                     ' {"type": "text", "text": "Looking."}]}'),
                       ("user", '{"text": "now the tests"}'),
                       ("assistant", '{"content": [{"type": "text", "text": "Green."}]}')][:rows]
            for seq, (kind, data) in enumerate(records):
                con.execute("INSERT INTO session_message VALUES (?,?,?,?,?,?)",
                            (f"m{seq}", "ses-1", kind, seq, 1787367773728 + seq, data))
        con.commit()
        con.close()
        return db

    def test_opencode_turns(self):
        db = self._opencode_db()
        got = transcript.opencode_turns(db, "ses-1")
        self.assertEqual([(t["role"], t["text"]) for t in got], [("you", "start the drawer"), ("claude", "Looking."),
                                                                 ("you", "now the tests"), ("claude", "Green.")])
        self.assertEqual(got[0]["ts"], 1787367773.728)
        self.assertEqual(transcript.opencode_turns(self.dir / "none.db", "ses-1"), [])
        self.assertEqual(transcript.opencode_turns(self._opencode_db("empty.db", table=False), "ses-1"), [])
        self.assertEqual(transcript.opencode_turns(db, "ses-other"), [])

    def test_opencode_db_opened_read_only(self):
        db = self._opencode_db()
        before = db.read_bytes()
        transcript.opencode_turns(db, "ses-1")
        self.assertEqual(db.read_bytes(), before)

    def test_turns_of_dispatch(self):
        claude = self.dir / "claude.jsonl"
        claude.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n",
                          encoding="utf-8")
        self.assertEqual([t["text"] for t in transcript.turns_of("claude", claude, "s1")], ["hello"])
        self.assertEqual([t["text"] for t in transcript.turns_of("opencode", "", "ses-1",
                                                                 opencode_db=self._opencode_db())],
                         ["start the drawer", "Looking.", "now the tests", "Green."])
        self.assertEqual(transcript.first_prompt_of("claude", claude, "s1"), "hello")
        self.assertEqual(transcript.first_prompt_of("codex", fixtures.codex_rollout(self.dir / "r.jsonl"), "s1"),
                         "fix the retry on line 9")


if __name__ == "__main__":
    unittest.main()
