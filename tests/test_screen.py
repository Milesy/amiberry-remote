import os
import random
import tempfile
import time
import unittest

from PIL import Image, ImageChops

from amiberry_remote.link import AmiberryError, Link
from amiberry_remote.memory import Memory
from amiberry_remote.screen import Screenshots
from tests.fake_amiberry import FakeAmiberry


def picture(width, height, depth, seed=1, plain_rows=0):
    """Colour numbers like a screen's: plain background with blocks and specks of other colours,
    the first `plain_rows` rows all colour 0."""
    rng = random.Random(seed)
    image = Image.new("P", (width, height), 0)
    for _ in range(width * height // 40):
        x, y = rng.randrange(width), rng.randrange(plain_rows, height)
        w, h = rng.randrange(1, 9), rng.randrange(1, 4)
        image.paste(rng.randrange(1, 1 << depth), (x, y, min(width, x + w), min(height, y + h)))
    return image


class ScreenshotTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.fake.boot_workbench(320, 128, 2)
        link = Link(self.fake.path)
        self.shots = Screenshots(link, Memory(link))
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def screen(self, width, height, depth, title="Game", **kw):
        sc = self.fake.add_screen(width, height, depth, title, **kw)
        self.fake.draw(sc, picture(width, height, depth, **{k: v for k, v in kw.items() if k == "seed"}))
        return sc

    def assertSame(self, a, b):
        self.assertEqual(a.size, b.size)
        self.assertIsNone(ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox())

    def test_scales_and_borders(self):
        self.fake.show_pointer = False
        for scale, size, offset, border in (((1, 1), (400, 200), (13, 21), (10, 10, 10)),
                                            ((1, 2), (380, 300), (40, 30), (0, 0, 0)),
                                            ((2, 2), (700, 300), (5, 17), (200, 0, 0))):
            sc = self.screen(320, 128, 3)
            self.fake.display.update(scale=scale, size=size, offset=offset, border=border)
            shot = self.shots.shot()
            self.assertSame(shot, self.fake.screen_image(sc))
            mapping = self.shots.mappings[(sc, 320, 128, 3)]
            self.assertEqual((mapping.left, mapping.top, mapping.scale_x, mapping.scale_y),
                             offset + scale)

    def test_hires_screen_as_amiberry_shows_it(self):
        self.fake.show_pointer = False
        sc = self.screen(640, 256, 4, interleaved=True)
        start = time.monotonic()
        shot = self.shots.shot()
        self.assertSame(shot, self.fake.screen_image(sc))
        self.assertLess(time.monotonic() - start, 5)

    def test_pointer_over_the_band(self):
        sc = self.screen(320, 128, 3)
        self.fake.put_mouse(100, 2)
        shot = self.shots.shot()
        expected = self.fake.screen_image(sc)
        diff = ImageChops.difference(shot, expected).getbbox()
        self.assertIsNotNone(diff)                       # the pointer shows...
        self.assertTrue(98 <= diff[0] and diff[2] <= 110 and diff[3] <= 10, diff)   # ...only there

    def test_band_below_plain_rows(self):
        self.fake.show_pointer = False
        sc = self.fake.add_screen(320, 128, 2, "Plain top")
        self.fake.draw(sc, picture(320, 128, 2, seed=5, plain_rows=40))
        self.assertGreaterEqual(self.shots.band(self.shots.memory.front_screen())[0], 40)
        self.assertSame(self.shots.shot(), self.fake.screen_image(sc))

    def test_all_one_colour(self):
        self.fake.add_screen(320, 128, 2, "Blank")
        with self.assertRaises(AmiberryError) as e:
            self.shots.shot()
        self.assertIn("'Blank'", str(e.exception))

    def test_ambiguous_band_gives_way_to_the_next(self):
        # Rows 8-15 repeat rows 0-7, so each of those bands fits in two places; rows 16-23 don't.
        self.fake.show_pointer = False
        sc = self.fake.add_screen(320, 128, 3, "Repeats")
        image = picture(320, 128, 3, seed=9)
        image.paste(image.crop((0, 0, 320, 8)), (0, 8))
        self.fake.draw(sc, image)
        self.assertSame(self.shots.shot(), self.fake.screen_image(sc))
        self.assertEqual(len(self.fake.shots), 3)        # one screenshot per band tried

    def test_no_scale_fits(self):
        self.fake.show_pointer = False
        self.screen(320, 128, 3, title="OctaMED")
        self.fake.display.update(scale=(3, 3), size=(1000, 400), offset=(10, 8))
        with self.assertRaises(AmiberryError) as e:
            self.shots.shot()
        self.assertIn("can't find the 320 x 128 screen 'OctaMED'", str(e.exception))

    def test_mapping_found_once(self):
        self.fake.show_pointer = False
        self.screen(320, 128, 3)
        self.shots.shot()
        reads = len(self.fake.commands("READ_MEM"))
        self.shots.shot()
        self.assertLess(len(self.fake.commands("READ_MEM")) - reads, 30)   # the screen, not the band

    def test_paths(self):
        self.fake.show_pointer = False
        sc = self.screen(320, 128, 3)
        path, raw = os.path.join(self.dir.name, "now.png"), os.path.join(self.dir.name, "raw.png")
        self.shots.shot(path, raw_path=raw)
        with Image.open(path) as saved:
            self.assertSame(saved, self.fake.screen_image(sc))
        with Image.open(raw) as saved:
            self.assertEqual(saved.size, (756, 576))


if __name__ == "__main__":
    unittest.main()
