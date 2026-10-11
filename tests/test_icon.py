import struct
import unittest
import zlib

from console import icon


def png_pixels(data: bytes) -> tuple:
    """(size, RGBA rows) of one of our PNGs: 8-bit RGBA, filter 0 on every row."""
    size = struct.unpack(">I", data[16:20])[0]
    start = data.index(b"IDAT") + 4
    length = struct.unpack(">I", data[start - 8:start - 4])[0]
    raw = zlib.decompress(data[start:start + length])
    stride = size * 4 + 1
    return size, b"".join(raw[y * stride + 1:(y + 1) * stride] for y in range(size))


class LogoTest(unittest.TestCase):
    def pixel(self, size, look, col, row):
        """The centre of one board cell."""
        margin, cell, gap = icon.layout(size)
        x = int(margin + col * (cell + gap) + cell / 2)
        y = int(margin + row * (cell + gap) + cell / 2)
        i = (y * size + x) * 4
        return tuple(icon.pixels(size, look)[i:i + 4])

    def test_every_size_fits_its_board(self):
        for size in icon.ICO_SIZES + (18, 28):
            margin, cell, gap = icon.layout(size)
            self.assertEqual(2 * margin + 3 * cell + 2 * gap, size, size)

    def test_signal_is_orange_only_when_something_needs_you(self):
        for size in (16, 20, 24, 32):
            self.assertEqual(self.pixel(size, "needs", 2, 0), (*icon.YOU, 255))
            self.assertEqual(self.pixel(size, "working", 2, 0), (*icon.OFF, 255))
            self.assertEqual(self.pixel(size, "working", 0, 2), (*icon.INK, 255))
            self.assertEqual(self.pixel(size, "idle", 1, 1), (*icon.MUT, 255))
            self.assertEqual(self.pixel(size, "idle", 2, 2), (*icon.OFF, 255))

    def test_tile_has_rounded_transparent_corners(self):
        data = icon.pixels(16)
        self.assertEqual(data[3], 0)                         # top-left corner
        self.assertEqual(data[(8 * 16 + 0) * 4 + 3], 255)    # middle of the left edge

    def test_bgra_swaps_red_and_blue(self):
        self.assertEqual(icon.bgra(bytes((1, 2, 3, 4, 5, 6, 7, 8))), bytes((3, 2, 1, 4, 7, 6, 5, 8)))


class AssetsTest(unittest.TestCase):
    """assets/ is the output of `py -m console.icon`: re-run it after changing the logo."""

    def test_pngs_match_the_logo(self):
        for size in icon.PNG_SIZES:
            data = (icon.ASSETS / f"logo-{size}.png").read_bytes()
            self.assertEqual(png_pixels(data), (size, icon.pixels(size)), size)

    def test_ico_holds_every_size(self):
        data = icon.ICO.read_bytes()
        self.assertEqual(struct.unpack("<HHH", data[:6]), (0, 1, len(icon.ICO_SIZES)))
        for n, size in enumerate(icon.ICO_SIZES):
            w, h, _, _, planes, bits, length, offset = struct.unpack("<BBBBHHII", data[6 + 16 * n:22 + 16 * n])
            self.assertEqual((w or 256, h or 256, planes, bits), (size, size, 1, 32))
            image = data[offset:offset + length]
            if size >= 256:
                self.assertEqual(png_pixels(image), (size, icon.pixels(size)))
            else:
                self.assertEqual(image, icon._dib(size, icon.pixels(size)))

    def test_svg_draws_the_same_board(self):
        svg = (icon.ROOT / "design" / "logo" / "logo.svg").read_text(encoding="utf-8")
        self.assertIn('viewBox="0 0 256 256"', svg)
        self.assertIn("#ff8a3d", svg)
        self.assertEqual(svg.count("<rect"), 10)              # the tile and nine cells


if __name__ == "__main__":
    unittest.main()
