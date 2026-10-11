"""The logo and app icon (design/logo/): a 3 x 3 board of cells on a --win tile, a lit route climbing from
the bottom-left to the signal cell at the top-right. The tray draws it per state (the signal is orange only
when something needs Fred); assets/app.ico and the PNGs are this module's output, written by
`py -m console.icon` and checked by tests/test_icon.py. Standard library only."""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICO = ASSETS / "app.ico"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 256)
PNG_SIZES = (16, 32, 256)

TILE, OFF = (0x12, 0x13, 0x15), (0x24, 0x27, 0x2B)  # --win, --off
INK, MUT, YOU = (0xEB, 0xE8, 0xE1), (0x9A, 0x99, 0x93), (0xFF, 0x8A, 0x3D)  # --ink, --mut, --you
ROUTE = ((0, 2), (0, 1), (1, 1), (1, 0))  # (column, row) from the top-left
SIGNAL = (2, 0)
# (route, signal) per look: the logo, and the tray's three states
LOOKS = {"logo": (INK, YOU), "needs": (INK, YOU), "working": (INK, OFF), "idle": (MUT, OFF)}
# size: (margin, cell, gap) in whole pixels, so the small icons stay sharp
LAYOUT = {16: (1, 4, 1), 20: (2, 4, 2), 24: (1, 6, 2), 32: (2, 8, 2), 40: (3, 10, 2), 48: (3, 12, 3),
          64: (4, 16, 4), 256: (16, 64, 16)}
SAMPLES = 4  # per pixel side: 16 coverage samples


def layout(size: int) -> tuple:
    if size in LAYOUT:
        return LAYOUT[size]
    gap = max(1, round(size / 16))
    return (size - 3 * ((size - 4 * gap) // 3) - 2 * gap) / 2, (size - 4 * gap) // 3, gap


def _in_round(x: float, y: float, x0: float, y0: float, x1: float, y1: float, r: float) -> bool:
    if not (x0 <= x < x1 and y0 <= y < y1):
        return False
    dx, dy = max(x0 + r - x, 0, x - (x1 - r)), max(y0 + r - y, 0, y - (y1 - r))
    return dx * dx + dy * dy <= r * r


def pixels(size: int, look: str = "logo") -> bytes:
    """RGBA rows top-down, antialiased by SAMPLES x SAMPLES coverage."""
    route, signal = LOOKS[look]
    colours = {cell: route for cell in ROUTE}
    colours[SIGNAL] = signal
    margin, cell, gap = layout(size)
    tile_r, cell_r, step = size * 3 / 16, cell * 0.18, cell + gap
    n = SAMPLES
    out = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            hits, rgb = 0, [0, 0, 0]
            for sy in range(n):
                py = y + (sy + 0.5) / n
                for sx in range(n):
                    px = x + (sx + 0.5) / n
                    if not _in_round(px, py, 0, 0, size, size, tile_r):
                        continue
                    hits += 1
                    col, row = int((px - margin) // step), int((py - margin) // step)
                    fill = TILE
                    if 0 <= col < 3 and 0 <= row < 3:
                        cx, cy = margin + col * step, margin + row * step
                        if _in_round(px, py, cx, cy, cx + cell, cy + cell, cell_r):
                            fill = colours.get((col, row), OFF)
                    rgb[0] += fill[0]
                    rgb[1] += fill[1]
                    rgb[2] += fill[2]
            if hits:
                i = (y * size + x) * 4
                out[i:i + 4] = bytes((round(rgb[0] / hits), round(rgb[1] / hits), round(rgb[2] / hits),
                                      round(255 * hits / (n * n))))
    return bytes(out)


def bgra(rgba: bytes) -> bytes:
    """Win32 wants BGRA, straight alpha, for a 32-bit icon DIB."""
    out = bytearray(rgba)
    out[0::4], out[2::4] = rgba[2::4], rgba[0::4]
    return bytes(out)


def png(size: int, rgba: bytes) -> bytes:
    rows = b"".join(b"\x00" + rgba[y * size * 4:(y + 1) * size * 4] for y in range(size))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def _dib(size: int, rgba: bytes) -> bytes:
    """An ICO entry as a bottom-up 32-bit DIB plus an empty AND mask (the alpha channel does the work)."""
    head = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    colour = bgra(rgba)
    rows = b"".join(colour[y * size * 4:(y + 1) * size * 4] for y in reversed(range(size)))
    return head + rows + b"\x00" * (((size + 31) // 32) * 4 * size)


def ico(sizes=ICO_SIZES, look: str = "logo") -> bytes:
    """256 as PNG (the Vista format), the small sizes as DIBs, which every Win32 and .NET loader reads."""
    images = [png(s, pixels(s, look)) if s >= 256 else _dib(s, pixels(s, look)) for s in sizes]
    offset = 6 + 16 * len(sizes)
    head = struct.pack("<HHH", 0, 1, len(sizes))
    for s, data in zip(sizes, images):
        head += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return head + b"".join(images)


def write(folder: Path = ASSETS) -> list:
    folder.mkdir(parents=True, exist_ok=True)
    written = [folder / "app.ico"]
    written[0].write_bytes(ico())
    for s in PNG_SIZES:
        path = folder / f"logo-{s}.png"
        path.write_bytes(png(s, pixels(s)))
        written.append(path)
    return written


if __name__ == "__main__":
    for path in write(Path(sys.argv[1]) if len(sys.argv) > 1 else ASSETS):
        print(path)
