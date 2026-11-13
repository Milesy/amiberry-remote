import unittest

from amiberry_remote.keys import KEYS, Keyboard, key_codes
from amiberry_remote.link import AmiberryError, Link
from tests.fake_amiberry import FakeAmiberry

SHIFT, CTRL, F2 = 0x60, 0x63, 0x51


class KeysTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAmiberry().start()
        self.addCleanup(self.fake.__exit__)
        self.keyboard = Keyboard(Link(self.fake.path), sleep=lambda s: None)

    def test_help(self):
        self.keyboard.press("Help")
        self.assertEqual(self.fake.key_events(), [(0x5F, True), (0x5F, False)])

    def test_combination_releases_in_reverse(self):
        self.keyboard.press("Ctrl-F2")
        self.assertEqual(self.fake.key_events(), [(CTRL, True), (F2, True), (F2, False), (CTRL, False)])

    def test_names_ignore_case(self):
        self.assertEqual(key_codes("ramiga-e"), key_codes("RAmiga-E"))
        self.assertEqual(key_codes("LShift-RAmiga-E"), [0x60, 0x67, 0x12])
        self.assertEqual(key_codes("Ctrl--"), [CTRL, 0x0B])
        self.assertEqual(key_codes("F10"), [0x59])
        for name in ("Del", "Esc", "Return", "Enter", "Space", "Tab", "Up", "Down", "Left", "Right",
                     "LShift", "RShift", "LAmiga", "RAmiga", "Ctrl", "LAlt", "RAlt", "a", "0", ";"):
            self.assertEqual(len(key_codes(name)), 1, name)

    def test_typing_shifts_exactly_the_shifted_characters(self):
        text = "cd PC:OctaMED"
        self.keyboard.type(text)
        shifted, keys = False, []
        for code, down in self.fake.key_events():
            if code == SHIFT:
                shifted = down
            elif down:
                keys.append((code, shifted))
        self.assertEqual([code for code, _ in keys], [KEYS[c] for c in "cd"] + [KEYS["space"]]
                         + [KEYS[c] for c in "pc;octamed"])
        self.assertEqual([ch for ch, (_, shift) in zip(text, keys) if shift], list("PC:OMED"))
        self.assertEqual(self.fake.key_events()[-1], (SHIFT, False))
        self.assertEqual(self.keyboard.down, [])

    def test_return_for_a_line_end(self):
        self.keyboard.type("dir\n")
        self.assertEqual(self.fake.key_events()[-2:], [(0x44, True), (0x44, False)])

    def test_unknown_key_sends_nothing(self):
        with self.assertRaises(AmiberryError) as e:
            self.keyboard.press("Help", "Hlep")
        self.assertIn("'Hlep'", str(e.exception))
        with self.assertRaises(AmiberryError):
            self.keyboard.press("Ctrl+F2")
        self.assertEqual(self.fake.commands(), [])

    def test_untypable_character_sends_nothing(self):
        with self.assertRaises(AmiberryError) as e:
            self.keyboard.type("cd café")
        self.assertIn("'é'", str(e.exception))
        self.assertEqual(self.fake.commands(), [])

    def test_keys_released_when_a_step_fails(self):
        sent = []
        link = self.keyboard.link
        def send(*fields):
            sent.append(fields)
            if fields == ("SEND_KEY", F2, 1):
                raise AmiberryError("refused")
            return link.__class__.send(link, *fields)
        self.keyboard.link = type("L", (), {"send": staticmethod(send)})()
        with self.assertRaises(AmiberryError):
            self.keyboard.press("Ctrl-F2")
        self.assertEqual(sent[-1], ("SEND_KEY", CTRL, 0))
        self.assertEqual(self.keyboard.down, [])

    def test_hold_and_release(self):
        self.keyboard.key_down("LShift")
        self.keyboard.press("a")
        self.assertEqual(self.keyboard.down, [SHIFT])     # pressing another key keeps it held
        self.keyboard.key_up("LShift")
        self.assertEqual(self.fake.key_events(), [(SHIFT, True), (0x20, True), (0x20, False), (SHIFT, False)])


if __name__ == "__main__":
    unittest.main()
