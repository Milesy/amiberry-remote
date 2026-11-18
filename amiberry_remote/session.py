"""The object callers use: one running Amiberry and the Amiga in it."""
import os
import shutil
import subprocess
import time

from PIL import ImageChops

from .keys import Keyboard
from .link import AmiberryError, Link, NotRunning
from .memory import Memory
from .pointer import Pointer
from .screen import Screenshots

APPIMAGE = "~/amiga/emu/Amiberry-8.4.2-x86_64.AppImage"


def find_amiberry():
    """The Amiberry program: `$AMIBERRY`, else `amiberry` on the PATH, else the 8.4.2 AppImage."""
    looked = []
    env = os.environ.get("AMIBERRY")
    if env:
        path = os.path.expanduser(env)
        if _runnable(path):
            return path
        looked.append(f"$AMIBERRY ({path})")
    else:
        looked.append("$AMIBERRY (not set)")
    on_path = shutil.which("amiberry")
    if on_path:
        return on_path
    looked.append("amiberry on the PATH")
    default = os.path.expanduser(APPIMAGE)
    if _runnable(default):
        return default
    looked.append(default)
    raise AmiberryError("can't find the Amiberry program; looked at " + ", ".join(looked))


def _runnable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


class Amiga:
    """An Amiberry answering on its socket, and the Amiga it emulates.

    `Amiga.connect()` uses the Amiberry already running; `Amiga.start(config)` starts one with a
    config (or uses the one running) and waits for Workbench."""

    poll = 0.5              # between checks while waiting for Workbench
    settle = 1.0            # between the two screenshots that must agree once Workbench is up
    answer_limit = 30       # seconds for a started Amiberry to answer on its socket
    window_limit = 3        # seconds for a window to open and get the keyboard

    def __init__(self, link=None, process=None, sleep=time.sleep, clock=time.monotonic):
        self.link = link or Link()
        self.process = process
        self.sleep = sleep
        self.clock = clock
        self.memory = Memory(self.link)
        self.keyboard = Keyboard(self.link)
        self.mouse = Pointer(self.link, self.memory)
        self.screenshots = Screenshots(self.link, self.memory, self.mouse)

    # ---- the session

    @classmethod
    def connect(cls, socket=None):
        """The Amiberry already running (it isn't reset). Not running is an error."""
        amiga = cls(Link(socket))
        amiga.link.send("PING")
        return amiga

    @classmethod
    def start(cls, config, timeout=90, socket=None):
        """Start Amiberry with a config file (no settings window) and wait for Workbench, at most
        `timeout` seconds. An Amiberry already running is used as it is. The config isn't changed."""
        path = os.path.abspath(os.path.expanduser(config))
        if not os.path.isfile(path):
            raise AmiberryError(f"there's no Amiberry config at {path}")
        amiga = cls(Link(socket))
        if not amiga.link.ping():
            program = find_amiberry()
            amiga.process = subprocess.Popen(
                [program, "--config", path, "-G"], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            amiga._wait_for_answer(program)
        amiga.wait_for_workbench(timeout)
        return amiga

    def _wait_for_answer(self, program):
        end = self.clock() + self.answer_limit
        while not self.link.ping():
            status = self.process.poll()
            if status is not None:
                raise AmiberryError(f"Amiberry ({program}) stopped with status {status} "
                                    "before answering on its socket")
            if self.clock() >= end:
                raise AmiberryError(f"Amiberry ({program}) didn't answer on {self.link.path} "
                                    f"within {self.answer_limit} s")
            self.sleep(0.1)

    def wait_for_workbench(self, timeout=90):
        """Wait until Workbench is up: exec and Intuition running, the Workbench process there,
        its screen in front, and two screenshots a second apart the same. After `timeout`
        seconds, an error giving what it was waiting for and the path of a screenshot."""
        end = self.clock() + timeout
        previous = None
        while True:
            waiting = self._workbench_not_ready()
            if waiting is None:
                shot = self.screenshots.raw()
                if previous is not None and ImageChops.difference(shot, previous).getbbox() is None:
                    return
                previous = shot
                waiting = "the screen to settle"
                pause = self.settle
            else:
                previous = None
                pause = self.poll
            if self.clock() >= end:
                break
            self.sleep(pause)
        path = "not taken"
        if waiting != "Amiberry to answer":
            path = self.screenshots.save_raw("workbench")
        raise AmiberryError(f"Workbench wasn't up within {timeout:g} s: still waiting for "
                            f"{waiting} (screenshot {path})")

    def _workbench_not_ready(self):
        """What Workbench is still waiting for, or None if it is up."""
        if not self.link.ping():
            return "Amiberry to answer"
        try:
            self.memory.exec_base()
        except AmiberryError:
            return "exec to start"
        try:
            self.memory.intuition_base()
        except AmiberryError:
            return "intuition.library"
        if not any(self.memory.is_process(t) and self.memory.task_name(t) == "Workbench"
                   for t in self.memory.tasks()):
            return "the Workbench process"
        try:
            if self.memory.front_screen().is_workbench:
                return None
        except AmiberryError:
            pass
        return "Workbench's screen in front"

    def run(self, *commands):
        """Open a new Shell window and type each command into it, with Return. Before each, the
        Shell window must have the keyboard. Returns once the keys are sent."""
        shell = self.open_shell()
        for command in commands:
            active = self.active_window()
            if active is None or active.address != shell.address:
                raise AmiberryError(
                    f"the Shell window doesn't have the keyboard to type {command!r}: "
                    f"{_named(active)} has it")
            self.type(command + "\n")

    def open_shell(self):
        """Open a new Shell window with Workbench's Execute Command (Right Amiga+E, Right Amiga+X
        to clear the command it remembers, then `newshell`) and make sure it has the keyboard;
        gives the window."""
        screen = self.front_screen()
        if not screen.is_workbench:
            raise AmiberryError(f"can't open a Shell: {screen.describe()} is in front, "
                                "not Workbench's")
        active = self.active_window()
        if active is None or not active.is_workbench:
            self._activate(self._workbench_window(screen), "a Workbench window")
            active = self.active_window()
        before = active.address
        self.key("RAmiga-E")
        requester = self._wait_for_window({before}, "Workbench's Execute Command requester "
                                          "(Right Amiga+E)")
        self.key("RAmiga-X")        # the requester keeps the last command: clear it
        self.type("newshell\n")
        shell = self._wait_for_window({before, requester.address}, None)
        if shell is None:
            others = [w for w in self.memory.windows(screen.address)
                      if w.address not in (before, requester.address) and not w.is_workbench]
            if not others:
                raise AmiberryError("newshell didn't open a Shell window")
            shell = others[0]
            self._activate(shell, "the new Shell window")
        return shell

    def _wait_for_window(self, not_these, name):
        """The active window once it is a window other than `not_these`; None (or, with a name,
        an error) if none is within `window_limit` seconds."""
        end = self.clock() + self.window_limit
        while True:
            active = self.active_window()
            if active is not None and active.address not in not_these:
                return active
            if self.clock() >= end:
                if name is None:
                    return None
                raise AmiberryError(f"{name} didn't open: {_named(active)} still has the keyboard")
            self.sleep(0.05)

    def _workbench_window(self, screen):
        windows = [w for w in self.memory.windows(screen.address) if w.is_workbench]
        if not windows:
            raise AmiberryError("Workbench has no window open to take Right Amiga+E")
        return next((w for w in windows if w.is_backdrop), windows[0])

    def _activate(self, window, name):
        """Click a spot of a window that no other window covers, so it gets the keyboard."""
        x, y = self._uncovered(window)
        self.click(x, y)
        end = self.clock() + self.window_limit
        while True:
            active = self.active_window()
            if active is not None and active.address == window.address:
                return
            if self.clock() >= end:
                raise AmiberryError(f"clicking {name} at x {x}, y {y} didn't give it the keyboard: "
                                    f"{_named(active)} has it")
            self.sleep(0.05)

    def _uncovered(self, window):
        """A spot inside a window that no other window (or the screen's title bar) covers, as near
        its middle as can be."""
        covering = self.memory.covering(window)
        left, top = window.left + 4, window.top + 4
        right, bottom = window.left + window.width - 5, window.top + window.height - 5
        cx, cy = (left + right) // 2, (top + bottom) // 2
        spots = sorted(((x, y) for x in range(left, right + 1, 8) for y in range(top, bottom + 1, 4)),
                       key=lambda s: (s[0] - cx) ** 2 + (s[1] - cy) ** 2)
        for x, y in spots:
            if not any(l <= x <= r and t <= y <= b for l, t, r, b in covering):
                return x, y
        raise AmiberryError(f"{_named(window)} is covered by other windows: nowhere to click it")

    def quit(self, timeout=10):
        """Quit Amiberry and wait until it has gone (its socket no longer answers)."""
        try:
            self.link.send("QUIT")
        except NotRunning:
            return
        except AmiberryError:
            pass            # it may close the connection as it goes
        end = self.clock() + timeout
        while self.link.ping():
            if self.clock() >= end:
                raise AmiberryError(f"Amiberry still answers {timeout:g} s after QUIT")
            self.sleep(0.1)
        if self.process is not None:
            try:
                self.process.wait(max(0.0, end - self.clock()))
            except subprocess.TimeoutExpired:
                raise AmiberryError(f"Amiberry's process is still running {timeout:g} s after "
                                    "QUIT") from None

    # ---- keys

    def key(self, *keys):
        """Press and release keys in turn: `key("Help")`, `key("Ctrl-F2", "Return")`."""
        self.keyboard.press(*keys)

    def key_down(self, key):
        """Press a key or combination and keep it held."""
        self.keyboard.key_down(key)

    def key_up(self, key):
        """Release a held key or combination."""
        self.keyboard.key_up(key)

    def type(self, text):
        """Type text on the US keyboard; a line end is Return."""
        self.keyboard.type(text)

    # ---- mouse

    def pointer(self):
        """The pointer's position (x, y) on the front screen, in its own pixels."""
        return self.mouse.position()

    def move_to(self, x, y):
        """Put the pointer exactly on x, y of the front screen."""
        self.mouse.move_to(x, y)

    def click(self, x, y, button="left"):
        """Click the left or right button at x, y of the front screen."""
        self.mouse.click(x, y, button)

    def drag(self, *coords, button="left", pause=0.0):
        """Drag with a button ("left" or "right") held from x1, y1 through each further x, y to
        the last, passing every pixel between. A right-button drag from a menu title to an item
        picks that item: drag(300, 100, 290, 89, 360, 70, button="right", pause=0.3). `pause`
        seconds are spent at each position between the first and the last."""
        self.mouse.drag(*coords, button=button, pause=pause)

    # ---- screen

    def shot(self, path=None, raw_path=None):
        """A picture (PIL image) of the front screen in its own pixels, saved at `path` if given;
        Amiberry's own screenshot is kept at `raw_path` if given."""
        return self.screenshots.shot(path, raw_path)

    def compare(self, area, expected, bits=4, park=True):
        """Compare an area ((left, top) or (left, top, width, height)) of the front screen with an
        expected picture (a file or PIL image): a Comparison with the pixels that differ, the
        first that does, and the paths of the screenshot and difference picture saved if any do."""
        return self.screenshots.compare(area, expected, bits, park)

    def wait_for(self, area, expected, timeout=20, bits=4, park=True):
        """Wait until an area of the front screen matches an expected picture; an error giving
        the last screenshot and difference picture if it doesn't within `timeout` seconds."""
        return self.screenshots.wait_for(area, expected, timeout, bits, park)

    # ---- memory

    def read(self, address, size=4):
        """The byte, word or long (size 1, 2 or 4) at an address, unsigned."""
        return self.memory.read(address, size)

    def write(self, address, size, value):
        """Write a byte, word or long (size 1, 2 or 4)."""
        self.memory.write(address, size, value)

    def read_block(self, address, length):
        """`length` bytes from an address."""
        return self.memory.read_block(address, length)

    def library(self, name):
        """An open library by name: its name, address and version."""
        return self.memory.library(name)

    def hunks(self, program):
        """The hunks of a running program (number, address, length), by name or by hunk file:
        `hunks("wait")`, `hunks("~/amiga/local-octamed/OctaMED/OctaMED.patched")`."""
        return self.memory.hunks(program)

    def front_screen(self):
        """The front screen: address, position, size, title, flags and bitmap."""
        return self.memory.front_screen()

    def active_window(self):
        """The window that has the keyboard (address, title, screen, position, size), or None."""
        return self.memory.active_window()


def _named(window):
    if window is None:
        return "no window"
    return f"the window {window.title!r}" if window.title else "an untitled window"
