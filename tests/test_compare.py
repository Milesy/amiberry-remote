import os
import tempfile
import unittest

from PIL import Image

from amiberry_remote.link import AmiberryError, Link
from amiberry_remote.memory import Memory
from amiberry_remote.pointer import Pointer
from amiberry_remote.screen import Screenshots
from tests.fake_amiberry import FakeAmiberry
from tests.test_pointer import Clock
from tests.test_screen import picture

# An OCS colour (each gun 4 bits) as Amiberry shows it, and as a PC drawing program might write it.
SHOWN = (0xFF, 0x88, 0x00)
DRAWN = (0xF0, 0x80, 0x00)


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.fake.boot_workbench(320, 128, 2)
        self.sc = self.fake.add_screen(320, 128, 3, "OctaMED")
        self.palette = [(0, 0, 0), (0xAA, 0xAA, 0xAA), (0xFF, 0xFF, 0xFF), SHOWN,
                        (0x00, 0x55, 0xAA), (0x11, 0x22, 0x33), (0x66, 0x00, 0x00), (0x00, 0x77, 0x00)]
        self.picture = picture(320, 128, 3, seed=3)
        self.fake.draw(self.sc, self.picture, self.palette)
        self.fake.put_mouse(300, 120)
        link = Link(self.fake.path)
        memory = Memory(link)
        clock = Clock()
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.shots = Screenshots(link, memory, Pointer(link, memory, sleep=clock.sleep, clock=clock),
                                 save_dir=self.dir.name, sleep=clock.sleep, clock=clock)

    def expected(self, box):
        return self.fake.screen_image(self.sc).crop((box[0], box[1], box[0] + box[2], box[1] + box[3]))

    def saved(self):
        return sorted(os.listdir(self.dir.name))

    def test_equal_area(self):
        box = (10, 20, 100, 40)
        result = self.shots.compare(box, self.expected(box))
        self.assertEqual((result.differing, result.first, result.matches), (0, None, True))
        self.assertEqual(self.saved(), [])
        self.assertEqual(self.shots.compare(box[:2], self.expected(box)).differing, 0)

    def test_three_pixels_differ(self):
        box = (10, 20, 100, 40)
        want = self.expected(box)
        for x, y in ((50, 7), (3, 30), (99, 39)):
            r, g, b = want.getpixel((x, y))
            want.putpixel((x, y), (255 - r, g, b))
        path = os.path.join(self.dir.name, "title.png")
        want.save(path)
        result = self.shots.compare(box, path)
        self.assertEqual(result.differing, 3)
        self.assertEqual(result.first, (10 + 50, 20 + 7))
        self.assertEqual(sorted(os.path.basename(p) for p in (result.shot_path, result.diff_path)),
                         [f for f in self.saved() if f != "title.png"])
        self.assertTrue(result.shot_path.endswith("-shot.png") and "title.png" in result.shot_path)
        with Image.open(result.shot_path) as shot:
            self.assertEqual(shot.size, (320, 128))
        with Image.open(result.diff_path) as diff:
            red = dict((c, n) for n, c in diff.convert("RGB").getcolors()).get((255, 0, 0))
            self.assertEqual((diff.size, red), ((100, 40), 3))

    def test_colours_to_four_bits_by_default(self):
        self.picture.paste(3, (50, 50, 70, 60))
        self.fake.draw(self.sc, self.picture, self.palette)
        want = Image.new("RGB", (20, 10), DRAWN)
        self.assertEqual(self.shots.compare((50, 50), want).differing, 0)
        self.assertEqual(self.shots.compare((50, 50), want, bits=8).differing, 200)

    def test_wrong_size_refused(self):
        with self.assertRaises(AmiberryError) as e:
            self.shots.compare((0, 0, 100, 40), Image.new("RGB", (100, 41)))
        self.assertIn("100 x 41", str(e.exception))
        self.assertIn("100 x 40", str(e.exception))
        with self.assertRaises(AmiberryError) as e:
            self.shots.compare((300, 0), Image.new("RGB", (100, 41)))
        self.assertIn("isn't inside", str(e.exception))
        self.assertEqual(self.fake.commands("SCREENSHOT"), [])

    def test_pointer_parked_off_the_area(self):
        box = (250, 100, 70, 28)                 # bottom-right: the pointer goes bottom-left
        self.fake.put_mouse(280, 110)
        self.assertEqual(self.shots.compare(box, self.expected(box)).differing, 0)
        self.assertEqual(self.fake.mouse(), (0, 127))
        box = (10, 20, 100, 40)
        self.fake.put_mouse(50, 30)
        self.assertEqual(self.shots.compare(box, self.expected(box)).differing, 0)
        self.assertEqual(self.fake.mouse(), (319, 127))

    def test_not_parked_when_told(self):
        box = (10, 20, 100, 40)
        self.fake.put_mouse(50, 30)
        result = self.shots.compare(box, self.expected(box), park=False)
        self.assertGreater(result.differing, 0)                   # the pointer shows
        self.assertEqual(self.fake.mouse(), (50, 30))

    def test_wait_until_the_screen_changes(self):
        box = (0, 0, 320, 13)
        title = picture(320, 128, 3, seed=11)
        self.fake.draw(self.sc, title, self.palette)
        want = self.expected(box)
        self.fake.draw(self.sc, self.picture, self.palette)
        original = self.fake.cmd_SCREENSHOT
        def screenshot(path):
            if len(self.fake.shots) == 4:
                self.fake.draw(self.sc, title, self.palette)
            return original(path)
        self.fake.cmd_SCREENSHOT = screenshot
        result = self.shots.wait_for(box[:2], want, timeout=20)
        self.assertTrue(result.matches)
        self.assertEqual(len(self.fake.shots), 5)       # 4 before the change, 1 after
        self.assertEqual(self.saved(), [])

    def test_wait_times_out(self):
        box = (0, 0, 320, 13)
        want = Image.new("RGB", (320, 13), (1, 2, 3))
        with self.assertRaises(AmiberryError) as e:
            self.shots.wait_for(box[:2], want, timeout=2)
        message = str(e.exception)
        self.assertIn("within 2 s", message)
        files = [f for f in self.saved()]
        self.assertEqual(len(files), 2)
        for f in files:
            self.assertIn(os.path.join(self.dir.name, f), message)


if __name__ == "__main__":
    unittest.main()
