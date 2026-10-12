import base64
import unittest

from console import attach

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
PDF = b"%PDF-1.4\n%fake\n"


def page(name, data: bytes):
    return {"name": name, "data": base64.b64encode(data).decode()}


class AttachTest(unittest.TestCase):
    def test_kind_comes_from_the_bytes(self):
        self.assertEqual(attach.kind_of(PNG), ("image", "image/png"))
        self.assertEqual(attach.kind_of(b"\xff\xd8\xff\xe0rest"), ("image", "image/jpeg"))
        self.assertEqual(attach.kind_of(b"GIF89a..."), ("image", "image/gif"))
        self.assertEqual(attach.kind_of(b"RIFF\x00\x00\x00\x00WEBPVP8 "), ("image", "image/webp"))
        self.assertEqual(attach.kind_of(PDF), ("pdf", "application/pdf"))
        self.assertEqual(attach.kind_of("# Notes é\n".encode("utf-8")), ("text", "text/plain"))
        self.assertIsNone(attach.kind_of(b"PK\x03\x04\x00docx"))  # a zip (docx, xlsx): not inline
        self.assertIsNone(attach.kind_of(b"\xff\xfe\x00\x00"))

    def test_parse_and_blocks(self):
        files = attach.parse([page("C:\\shots\\a.png", PNG), page("spec.pdf", PDF), page("notes.md", b"# hi")])
        self.assertEqual(attach.summary(files), [{"name": "a.png", "kind": "image", "bytes": len(PNG)},
                                                 {"name": "spec.pdf", "kind": "pdf", "bytes": len(PDF)},
                                                 {"name": "notes.md", "kind": "text", "bytes": 4}])
        image, pdf, text = attach.blocks(files)
        self.assertEqual(image, {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                             "data": base64.b64encode(PNG).decode()}})
        self.assertEqual((pdf["type"], pdf["title"], pdf["source"]["media_type"], pdf["source"]["type"]),
                         ("document", "spec.pdf", "application/pdf", "base64"))
        self.assertEqual(text, {"type": "document", "title": "notes.md",
                                "source": {"type": "text", "media_type": "text/plain", "data": "# hi"}})
        self.assertEqual(attach.note(files), "\n\nAttached to this task, sent with the run: "
                                             "a.png (image), spec.pdf (pdf), notes.md (text).")
        self.assertEqual(attach.note([]), "")
        self.assertEqual(attach.parse(None), [])
        self.assertEqual(attach.parse([]), [])

    def test_an_image_keeps_a_small_thumbnail_only(self):
        thumb = "data:image/jpeg;base64," + "A" * 100
        files = attach.parse([dict(page("a.png", PNG), thumb=thumb), dict(page("b.png", PNG), thumb="data:text/html,<b>"),
                              dict(page("c.png", PNG), thumb="data:image/png;base64," + "A" * attach.THUMB_MAX),
                              dict(page("n.md", b"# hi"), thumb=thumb)])
        self.assertEqual([f["thumb"] for f in files], [thumb, "", "", ""])
        self.assertEqual(attach.summary(files)[0]["thumb"], thumb)
        self.assertNotIn("thumb", attach.summary(files)[1])

    def test_refusals_say_why(self):
        cases = [
            ([page("x.png", PNG)] * (attach.MAX_FILES + 1), "at most"),
            ("not a list", "at most"),
            ([{"name": "a.png"}], "needs a name"),
            ([{"name": "a.png", "data": "***"}], "not base64"),
            ([page("report.docx", b"PK\x03\x04\x14\x00\x06\x00rest")], "send images"),
            ([page("big.png", PNG + b"\x00" * attach.MAX_BYTES)], "over 5 MB"),
            ([page("log.txt", b"a" * (attach.MAX_TEXT + 1))], "over 256 KB"),
            ([page(f"{k}.png", PNG + b"\x00" * (attach.MAX_BYTES - 100)) for k in range(5)], "in all"),
        ]
        for files, why in cases:
            with self.subTest(why=why):
                with self.assertRaises(attach.AttachError) as err:
                    attach.parse(files)
                self.assertIn(why, str(err.exception))


if __name__ == "__main__":
    unittest.main()
