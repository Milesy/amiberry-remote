import unittest

from amiberry_remote.link import AmiberryError, Link
from amiberry_remote.memory import Memory
from amiberry_remote.pointer import Pointer, line
from tests.fake_amiberry import FakeAmiberry


class Clock:
    """Time that passes only when slept, so waits cost nothing."""
    def __init__(self):
        self.now = 0.0

    def sleep(self, seconds):
        self.now += seconds

    def __call__(self):
        return self.now


class PointerTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.fake.boot_workbench(640, 256)
        link = Link(self.fake.path)
        clock = Clock()
        self.pointer = Pointer(link, Memory(link), sleep=clock.sleep, clock=clock)

    def lores(self):
        self.fake.add_screen(320, 256, 5, "Game")

    def test_exact_from_any_start(self):
        for screen in ("hires", "lores"):
            if screen == "lores":
                self.lores()
            w, h = (640, 256) if screen == "hires" else (320, 256)
            targets = [(0, 0), (w - 1, h - 1), (w // 2 + 1, 3), (5, h - 2), (w * 330 // 640, 48)]
            for start in [(0, 0), (w - 1, h - 1), (w // 3, h // 2)]:
                for target in targets:
                    self.fake.put_mouse(*start)
                    self.pointer.move_to(*target)
                    self.assertEqual(self.fake.mouse(), target, (screen, start, target))
                    self.assertEqual(self.pointer.position(), target)

    def test_moves_are_small(self):
        self.fake.put_mouse(0, 0)
        self.pointer.move_to(639, 255)
        for line_ in self.fake.commands("SEND_MOUSE"):
            _, dx, dy, _ = line_.split("\t")
            self.assertLessEqual(max(abs(int(dx)), abs(int(dy))), 32)
        self.assertLess(len(self.fake.commands("SEND_MOUSE")), 200)

    def test_off_the_screen_is_refused_without_moving(self):
        self.fake.put_mouse(10, 10)
        for x, y in ((700, 10), (640, 10), (10, 256), (-1, 0)):
            with self.assertRaises(AmiberryError) as e:
                self.pointer.move_to(x, y)
            self.assertIn(f"x {x}, y {y} is off the 640 x 256 screen", str(e.exception))
        with self.assertRaises(AmiberryError):
            self.pointer.click(700, 10)
        with self.assertRaises(AmiberryError):
            self.pointer.drag(10, 10, 10, 300)
        self.assertEqual(self.fake.commands("SEND_MOUSE"), [])

    def test_stuck_pointer_says_where_it_got_to(self):
        self.fake.put_mouse(20, 30)
        self.fake.mouse_blocked = True
        with self.assertRaises(AmiberryError) as e:
            self.pointer.move_to(300, 100)
        self.assertIn("didn't get to x 300, y 100", str(e.exception))
        self.assertIn("got to x 20, y 30", str(e.exception))

    def test_click_at_the_target(self):
        self.fake.put_mouse(600, 200)
        self.pointer.click(330, 48)
        self.assertEqual(self.fake.button_events, [(1, (330, 48)), (0, (330, 48))])
        self.pointer.click(10, 11, "right")
        self.assertEqual(self.fake.button_events[2:], [(2, (10, 11)), (0, (10, 11))])
        with self.assertRaises(AmiberryError):
            self.pointer.click(10, 11, "middle")

    def test_drag_passes_through_every_position(self):
        for screen in ("hires", "lores"):
            if screen == "lores":
                self.lores()
            for (x1, y1, x2, y2) in ((100, 120, 160, 120), (150, 40, 120, 80)):
                self.fake.put_mouse(5, 5)
                start = len(self.fake.mouse_track)
                events = len(self.fake.button_events)
                self.pointer.drag(x1, y1, x2, y2)
                self.assertEqual(self.fake.button_events[events:], [(1, (x1, y1)), (0, (x2, y2))])
                held = [pos for pos, b in self.fake.mouse_track[start:] if b == 1]
                seen = iter(held)
                for point in line(x1, y1, x2, y2):
                    self.assertIn(point, seen, (screen, point))     # in order

    def test_right_button_drag_holds_the_right_button(self):
        self.fake.put_mouse(5, 5)
        start, events = len(self.fake.mouse_track), len(self.fake.button_events)
        self.pointer.drag(10, 2, 10, 30, button="right")
        self.assertEqual(self.fake.button_events[events:], [(2, (10, 2)), (0, (10, 30))])
        held = [pos for pos, b in self.fake.mouse_track[start:] if b == 2]
        seen = iter(held)
        for point in line(10, 2, 10, 30):
            self.assertIn(point, seen, point)
        with self.assertRaises(AmiberryError):
            self.pointer.drag(10, 2, 10, 30, button="middle")

    def test_drag_through_several_positions(self):
        self.fake.put_mouse(5, 5)
        start, events = len(self.fake.mouse_track), len(self.fake.button_events)
        path = [(300, 100), (290, 89), (340, 89), (360, 70)]
        self.pointer.drag(*[c for p in path for c in p], button="right")
        self.assertEqual(self.fake.button_events[events:], [(2, (300, 100)), (0, (360, 70))])
        seen = iter([pos for pos, b in self.fake.mouse_track[start:] if b == 2])
        expected = [path[0]] + [q for a, b in zip(path, path[1:]) for q in line(*a, *b)[1:]]
        for point in expected:
            self.assertIn(point, seen, point)
        before = self.pointer.clock()
        self.pointer.drag(300, 100, 290, 89, 360, 70, button="right", pause=7)
        self.assertGreaterEqual(self.pointer.clock() - before, 7)
        for bad in ((1, 2, 3), (1, 2), (1, 2, 3, 4, 5)):
            with self.assertRaises(AmiberryError):
                self.pointer.drag(*bad)

    def test_buttons_released_when_a_step_fails(self):
        self.fake.put_mouse(100, 120)
        sends = []
        original = self.fake.cmd_SEND_MOUSE
        def send(dx, dy, buttons):
            sends.append(buttons)
            if len(sends) == 10:
                self.fake.mouse_blocked = True
            return original(dx, dy, buttons)
        self.fake.cmd_SEND_MOUSE = send
        with self.assertRaises(AmiberryError):
            self.pointer.drag(100, 120, 160, 120)
        self.assertEqual(self.fake.mouse_buttons, 0)
        self.assertEqual(self.fake.commands("SEND_MOUSE")[-1], "SEND_MOUSE\t0\t0\t0")

    def test_line(self):
        self.assertEqual(line(0, 0, 3, 0), [(0, 0), (1, 0), (2, 0), (3, 0)])
        self.assertEqual(line(2, 2, 0, 0), [(2, 2), (1, 1), (0, 0)])
        self.assertEqual(len(line(0, 0, 10, 3)), 11)


if __name__ == "__main__":
    unittest.main()
