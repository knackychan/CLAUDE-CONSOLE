"""Files Fred attaches to a window-run prompt. They go inline, as content blocks of the stream-json user
message (the documented image / document shapes), so Claude sees them without a tool call. The kind
comes from the first bytes, never from the name. Only name, kind, size and, for an image, the small
thumbnail the page drew are kept (the cc_prompt line); the bytes are never written."""
import base64
import binascii
import re
from pathlib import Path

MAX_FILES = 5
THUMB_MAX = 24 * 1024          # one thumbnail data URL (the page draws about 160 px JPEGs, 5-15 KB)
_THUMB = re.compile(r"data:image/(jpeg|png);base64,[A-Za-z0-9+/]+=*")
MAX_BYTES = 5 * 1024 * 1024    # one image or PDF (Claude Code downsizes big images itself)
MAX_TEXT = 256 * 1024          # one text file: about 64K tokens
MAX_TOTAL = 20 * 1024 * 1024   # all files of one prompt
_IMAGES = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"),
           (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"))
SENDABLE = "images (PNG, JPEG, GIF, WebP), PDF or text files"


class AttachError(ValueError):
    pass


def kind_of(data: bytes):
    """(kind, media type): image, pdf or text; None when Claude could not take the file inline."""
    for magic, media in _IMAGES:
        if data.startswith(magic):
            return "image", media
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image", "image/webp"
    if data.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if b"\x00" not in data:
        try:
            data.decode("utf-8")
            return "text", "text/plain"
        except UnicodeDecodeError:
            pass
    return None


def parse(files) -> list:
    """The page's [{name, data (base64), thumb?}] -> [{name, kind, media_type, bytes, data, thumb}].
    `data` stays base64 for images and PDFs and becomes the text for text files; `thumb` is the page's
    data URL for an image, kept only when it is a small JPEG or PNG ("" otherwise, never an error)."""
    if not files:
        return []
    if not isinstance(files, list) or len(files) > MAX_FILES:
        raise AttachError(f"at most {MAX_FILES} files per prompt")
    out, total = [], 0
    for f in files:
        name, b64 = (f.get("name"), f.get("data")) if isinstance(f, dict) else (None, None)
        if not isinstance(name, str) or not isinstance(b64, str):
            raise AttachError("each file needs a name and its data")
        name = name.replace("\\", "/").rsplit("/", 1)[-1].strip()[:120] or "file"
        try:
            data = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise AttachError(f"{name}: not base64")
        kind = kind_of(data)
        if not kind:
            raise AttachError(f"{name}: send {SENDABLE}")
        limit = MAX_TEXT if kind[0] == "text" else MAX_BYTES
        if len(data) > limit:
            raise AttachError(f"{name}: over {limit // 1024} KB" if limit < 1048576 else
                              f"{name}: over {limit // 1048576} MB")
        total += len(data)
        if total > MAX_TOTAL:
            raise AttachError(f"over {MAX_TOTAL // 1048576} MB in all")
        thumb = f.get("thumb")
        ok = kind[0] == "image" and isinstance(thumb, str) and len(thumb) <= THUMB_MAX and _THUMB.fullmatch(thumb)
        out.append({"name": name, "kind": kind[0], "media_type": kind[1], "bytes": len(data),
                    "data": data.decode("utf-8") if kind[0] == "text" else b64, "thumb": thumb if ok else ""})
    return out


def blocks(files: list) -> list:
    """Content blocks for claude_cli.user_message, after the prompt's text block."""
    out = []
    for f in files:
        if f["kind"] == "image":
            out.append({"type": "image", "source": {"type": "base64", "media_type": f["media_type"], "data": f["data"]}})
        elif f["kind"] == "pdf":
            out.append({"type": "document", "title": f["name"],
                        "source": {"type": "base64", "media_type": "application/pdf", "data": f["data"]}})
        else:
            out.append({"type": "document", "title": f["name"],
                        "source": {"type": "text", "media_type": "text/plain", "data": f["data"]}})
    return out


def note(files: list) -> str:
    """The line Prep reads instead of the files (Prep never gets the bytes; the run does)."""
    if not files:
        return ""
    return "\n\nAttached to this task, sent with the run: " + ", ".join(f"{f['name']} ({f['kind']})" for f in files) + "."


def summary(files: list) -> list:
    """What the Chat shows and the run log keeps: no file bytes, an image's thumbnail when there is one."""
    return [{"name": f["name"], "kind": f["kind"], "bytes": f["bytes"], **({"thumb": f["thumb"]} if f.get("thumb") else {})}
            for f in files]


def folder_image(folder: str, rel: str):
    """(bytes, media type) of an image Claude wrote inside the session's folder, for its Chat thumbnail;
    None for anything else: outside the folder, missing, too big, or not PNG / JPEG / GIF / WebP."""
    try:
        base = Path(folder).resolve()
        path = (base / rel).resolve()
        path.relative_to(base)
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except (OSError, ValueError, TypeError):
        return None
    kind = kind_of(data)
    return (data, kind[1]) if kind and kind[0] == "image" else None
