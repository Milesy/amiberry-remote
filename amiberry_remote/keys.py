"""Amiga keys by name, and typing text on the Amiga's US keyboard.

Key codes are the raw codes of the Hardware Reference Manual's keyboard map."""
import re
import time

from .link import AmiberryError

KEYS = {}
KEYS.update(zip("qwertyuiop", range(0x10, 0x1A)))
KEYS.update(zip("asdfghjkl", range(0x20, 0x29)))
KEYS.update(zip("zxcvbnm", range(0x31, 0x38)))
KEYS.update(zip("1234567890", range(0x01, 0x0B)))
KEYS.update({
    "`": 0x00, "-": 0x0B, "=": 0x0C, "\\": 0x0D, "[": 0x1A, "]": 0x1B, ";": 0x29, "'": 0x2A,
    ",": 0x38, ".": 0x39, "/": 0x3A,
    "space": 0x40, "backspace": 0x41, "tab": 0x42, "enter": 0x43, "return": 0x44, "esc": 0x45,
    "del": 0x46, "up": 0x4C, "down": 0x4D, "right": 0x4E, "left": 0x4F, "help": 0x5F,
    "lshift": 0x60, "rshift": 0x61, "shift": 0x60, "capslock": 0x62, "ctrl": 0x63,
    "lalt": 0x64, "ralt": 0x65, "alt": 0x64, "lamiga": 0x66, "ramiga": 0x67,
    "num0": 0x0F, "num1": 0x1D, "num2": 0x1E, "num3": 0x1F, "num4": 0x2D, "num5": 0x2E,
    "num6": 0x2F, "num7": 0x3D, "num8": 0x3E, "num9": 0x3F, "numdot": 0x3C, "numminus": 0x4A,
    "numlparen": 0x5A, "numrparen": 0x5B, "numslash": 0x5C, "numstar": 0x5D, "numplus": 0x5E,
})
KEYS.update({f"f{n}": 0x4F + n for n in range(1, 11)})

LSHIFT = KEYS["lshift"]

# Typing on the US keymap: character -> (key, Shift held)
CHARACTERS = {c: (KEYS[c], False) for c in "`1234567890-=\\qwertyuiop[]asdfghjkl;'zxcvbnm,./"}
CHARACTERS.update({c.upper(): (KEYS[c], True) for c in "qwertyuiopasdfghjklzxcvbnm"})
CHARACTERS.update({s: (KEYS[c], True) for s, c in zip('~!@#$%^&*()_+|{}:"<>?', "`1234567890-=\\[];',./")})
CHARACTERS.update({" ": (KEYS["space"], False), "\n": (KEYS["return"], False), "\t": (KEYS["tab"], False)})

_PART = re.compile(r"[A-Za-z0-9]+|.")


def key_codes(combination):
    """The key codes of a key or a combination written with `-` (`Help`, `Ctrl-F2`, `RAmiga-E`,
    `Ctrl--`), names matched without regard to case."""
    codes = []
    i = 0
    while True:
        part = _PART.match(combination, i)
        if part is None:
            break
        name = part.group()
        code = KEYS.get(name.lower())
        if code is None:
            raise AmiberryError(f"no Amiga key is called {name!r} (in {combination!r})")
        codes.append(code)
        i = part.end()
        if i == len(combination):
            return codes
        if combination[i] != "-":
            break
        i += 1
    raise AmiberryError(f"{combination!r} isn't a key or keys joined with '-'")


def typed(text):
    """(key code, Shift held) for each character of a text."""
    keys = []
    for ch in text:
        if ch not in CHARACTERS:
            raise AmiberryError(f"{ch!r} can't be typed on the Amiga's US keyboard (in {text!r})")
        keys.append(CHARACTERS[ch])
    return keys


class Keyboard:
    """Presses keys over the link: each key down for `hold` seconds with `gap` seconds after."""

    def __init__(self, link, hold=0.05, gap=0.05, sleep=time.sleep):
        self.link = link
        self.hold = hold
        self.gap = gap
        self.sleep = sleep
        self.down = []          # codes held, in the order they went down

    def _send(self, code, down):
        self.link.send("SEND_KEY", code, 1 if down else 0)
        if down:
            self.down.append(code)
        elif code in self.down:
            self.down.remove(code)

    def release_all(self, keep=()):
        """Release every key this keyboard holds but those in `keep`, the last pressed first."""
        for code in reversed([c for c in self.down if c not in keep]):
            self._send(code, False)

    def press(self, *combinations):
        """Press and release keys or combinations in turn: `press("Help")`, `press("Ctrl-F2")`.
        In a combination the keys go down in order and come up in reverse order."""
        all_codes = [key_codes(c) for c in combinations]      # every name checked before sending
        held = list(self.down)
        try:
            for codes in all_codes:
                for code in codes:
                    self._send(code, True)
                    self.sleep(self.hold)
                for code in reversed(codes):
                    self._send(code, False)
                    self.sleep(self.gap)
        finally:
            self.release_all(keep=held)

    def key_down(self, combination):
        """Press a key or combination and keep it held."""
        codes = key_codes(combination)
        for code in codes:
            self._send(code, True)
            self.sleep(self.gap)

    def key_up(self, combination):
        """Release a held key or combination, in reverse order."""
        codes = key_codes(combination)
        for code in reversed(codes):
            self._send(code, False)
            self.sleep(self.gap)

    def type(self, text):
        """Type text as a person would on the US keyboard: Shift held for capitals and shifted
        characters, Return for a line end."""
        keys = typed(text)                                     # every character checked first
        held = list(self.down)
        shifted = False
        try:
            for code, shift in keys:
                if shift != shifted:
                    self._send(LSHIFT, shift)
                    shifted = shift
                    self.sleep(self.gap)
                self._send(code, True)
                self.sleep(self.hold)
                self._send(code, False)
                self.sleep(self.gap)
        finally:
            self.release_all(keep=held)
