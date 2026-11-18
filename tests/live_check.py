"""Checks against a real Amiberry, run only when AMIBERRY_LIVE_CONFIG names a config:

    AMIBERRY_LIVE_CONFIG=~/Amiberry/Configurations/A1200-OctaMED.uae \\
        .venv/bin/python -m unittest tests.live_check -v

It starts Amiberry with the config (or uses the one running) and quits it at the end. The
fourth check pauses the emulation for about half a second. Keep the PC's mouse off Amiberry's
window while it runs."""
import os
import time
import unittest

from amiberry_remote import Amiga

CONFIG = os.environ.get("AMIBERRY_LIVE_CONFIG")


@unittest.skipUnless(CONFIG, "set AMIBERRY_LIVE_CONFIG to an Amiberry config to run the live checks")
class LiveCheck(unittest.TestCase):
    times = []

    @classmethod
    def setUpClass(cls):
        start = time.monotonic()
        cls.amiga = Amiga.start(CONFIG)
        cls.times.append(("start Amiberry and wait for Workbench", time.monotonic() - start))

    @classmethod
    def tearDownClass(cls):
        start = time.monotonic()
        cls.amiga.quit()
        cls.times.append(("quit", time.monotonic() - start))
        print()
        for what, seconds in cls.times:
            print(f"  {seconds:6.2f} s  {what}")

    def timed(self, what, action, *args):
        start = time.monotonic()
        result = action(*args)
        self.times.append((what, time.monotonic() - start))
        return result

    def test_1_pointer_on_five_positions(self):
        screen = self.amiga.front_screen()
        self.assertTrue(screen.is_workbench)
        w, h = screen.width, screen.height
        for x, y in ((0, 0), (w - 1, h - 1), (w // 2, h // 2), (13, h - 7), (w - 21, 17)):
            self.timed(f"pointer to x {x}, y {y}", self.amiga.move_to, x, y)
            self.assertEqual(self.amiga.pointer(), (x, y))

    def test_2_shot_has_the_screens_size(self):
        screen = self.amiga.front_screen()
        picture = self.timed("first shot (finding the screen)", self.amiga.shot)
        self.assertEqual(picture.size, (screen.width, screen.height))
        picture = self.timed("next shot", self.amiga.shot)
        self.assertEqual(picture.size, (screen.width, screen.height))

    def test_3_shell_command_and_its_hunks(self):
        self.timed("run 'wait 60' in a new Shell", self.amiga.run, "wait 60")
        start = time.monotonic()
        while True:
            try:
                hunks = self.amiga.hunks("wait")
                break
            except Exception:
                if time.monotonic() - start > 5:
                    raise
                time.sleep(0.1)
        self.times.append(("until Wait's hunks are found", time.monotonic() - start))
        self.assertGreaterEqual(len(hunks), 1)
        for hunk in hunks:
            self.assertIsNotNone(hunk.address)
            self.assertGreater(hunk.length, 0)
            print(f"\n  Wait: hunk {hunk.number} at ${hunk.address:X}, {hunk.length} bytes", end="")

    def test_4_paused_memory_holds_still(self):
        dispatches = self.amiga.read(4) + 0x11C      # exec's DispCount: task switches so far
        screen = self.amiga.front_screen()
        with self.amiga.paused():
            first = self.amiga.read(dispatches)
            time.sleep(0.3)
            self.assertEqual(self.amiga.read(dispatches), first, "paused, the count moved")
            picture = self.timed("raw shot while paused", self.amiga.raw_shot)
            self.assertGreaterEqual(picture.width, screen.width)
            self.assertGreaterEqual(picture.height, screen.height)
        start = time.monotonic()
        while self.amiga.read(dispatches) == first:
            self.assertLess(time.monotonic() - start, 2, "resumed, the count didn't move")
            time.sleep(0.05)
        self.times.append(("until the count moved after resuming", time.monotonic() - start))


if __name__ == "__main__":
    unittest.main()
