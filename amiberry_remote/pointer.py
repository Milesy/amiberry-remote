"""Putting the pointer on an exact position of the front screen, and clicking and dragging there.

`SEND_MOUSE` moves are relative and may be sped up by Workbench's input preferences, so the pointer
is steered: each move aims at the distance left, using how far the moves so far went, and the
position is read back from Intuition after every move (design decision 7)."""
import time

from .link import AmiberryError

LEFT, RIGHT = 1, 2
STILL_LIMIT = 10      # moves in a row that don't show: the pointer is held somewhere
BUTTONS = {"left": LEFT, "right": RIGHT}


def line(x1, y1, x2, y2):
    """The pixels of a straight line from one position to another, both ends included."""
    dx, dy = abs(x2 - x1), -abs(y2 - y1)
    sx, sy = (1 if x2 > x1 else -1), (1 if y2 > y1 else -1)
    err = dx + dy
    points = [(x1, y1)]
    x, y = x1, y1
    while (x, y) != (x2, y2):
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
        points.append((x, y))
    return points


class Pointer:
    """Steers the pointer over the link, reading its position from memory."""

    def __init__(self, link, memory, max_step=32, limit=200, settle=0.2, poll=0.005, hold=0.05,
                 gap=0.05, sleep=time.sleep, clock=time.monotonic):
        self.link = link
        self.memory = memory
        self.max_step = max_step      # counts per move; near the target moves are smaller
        self.limit = limit            # moves before giving up on a position
        self.settle = settle          # how long a move may take to show
        self.poll = poll
        self.hold = hold              # a click's button held this long
        self.gap = gap
        self.sleep = sleep
        self.clock = clock
        self.buttons = 0

    def position(self, screen=None):
        """The pointer's position (x, y) on the front screen, in its pixels."""
        screen = screen or self.memory.front_screen()
        return self.memory.screen_mouse(screen.address)

    def _check(self, screen, x, y):
        if not (0 <= x < screen.width and 0 <= y < screen.height):
            raise AmiberryError(f"x {x}, y {y} is off {screen.describe()}")

    def move_to(self, x, y, screen=None):
        """Put the pointer exactly on x, y of the front screen (its own pixels)."""
        screen = screen or self.memory.front_screen()
        self._check(screen, x, y)
        self._steer(screen, (x, y))

    def _send(self, dx, dy, buttons):
        self.link.send("SEND_MOUSE", dx, dy, buttons)
        self.buttons = buttons

    def _wait_for_move(self, screen, before):
        """The position once a move has shown: two reads a poll apart that agree, and differ from
        `before`. If nothing changes within `settle`, the move was too small to show."""
        end = self.clock() + self.settle
        last = self.memory.screen_mouse(screen.address)
        while True:
            if last != before:
                self.sleep(self.poll)
                again = self.memory.screen_mouse(screen.address)
                if again == last:
                    return last
                last = again
                continue
            if self.clock() >= end:
                return last
            self.sleep(self.poll)
            last = self.memory.screen_mouse(screen.address)

    def _steer(self, screen, target):
        pos = self.memory.screen_mouse(screen.address)
        ratio = [None, None]          # pixels moved per count, per axis, from the last move
        nudge = [1, 1]                # count multiplier after moves that didn't show
        still = 0                     # moves in a row that didn't show at all
        for _ in range(self.limit):
            if pos == target:
                return
            counts = []
            for axis in (0, 1):
                left = target[axis] - pos[axis]
                if left == 0:
                    counts.append(0)
                    continue
                if ratio[axis]:
                    c = round(left / ratio[axis])
                else:
                    c = left                      # first move: a guess of one pixel per count
                if c == 0:
                    c = 1 if left > 0 else -1
                c *= nudge[axis]
                counts.append(max(-self.max_step, min(self.max_step, c)))
            self._send(counts[0], counts[1], self.buttons)
            new = self._wait_for_move(screen, pos)
            for axis in (0, 1):
                moved = new[axis] - pos[axis]
                if counts[axis] == 0:
                    continue
                if moved == 0:
                    nudge[axis] = min(nudge[axis] * 2, self.max_step)
                else:
                    nudge[axis] = 1
                    if moved * counts[axis] > 0:
                        ratio[axis] = moved / counts[axis]
            still = still + 1 if new == pos else 0
            pos = new
            if still == STILL_LIMIT:
                break
        if pos != target:
            raise AmiberryError(
                f"the pointer didn't get to x {target[0]}, y {target[1]} on {screen.describe()}: "
                f"it got to x {pos[0]}, y {pos[1]}"
                + (f" and stopped moving" if still == STILL_LIMIT else f" in {self.limit} moves"))

    def click(self, x, y, button="left"):
        """Click a button ("left" or "right") at x, y of the front screen."""
        bit = _button(button)
        screen = self.memory.front_screen()
        self._check(screen, x, y)
        try:
            self._steer(screen, (x, y))
            self._send(0, 0, bit)
            self.sleep(self.hold)
            self._send(0, 0, 0)
            self.sleep(self.gap)
        finally:
            self.release()

    def drag(self, *coords, button="left", pause=0.0):
        """Hold a button ("left" or "right") at the first position and move a pixel at a time
        along straight lines through each further position, then release it at the last one.
        `coords` is x1, y1, x2, y2[, x3, y3 ...]. With the right button this picks a menu item:
        go from where the menu opens to its title, then to the item, and let go there. `pause`
        seconds are spent at each position between the first and the last: a menu needs a moment
        on its title to show that title's items (MagicMenu, as on ClassicWB, measured 0.3 s)."""
        bit = _button(button)
        points = _points(coords)
        screen = self.memory.front_screen()
        for x, y in points:
            self._check(screen, x, y)
        try:
            self._steer(screen, points[0])
            self._send(0, 0, bit)
            self.sleep(self.hold)
            for n, (a, b) in enumerate(zip(points, points[1:])):
                if n:
                    self.sleep(pause)
                for point in line(*a, *b)[1:]:
                    self._steer(screen, point)
            self.sleep(self.hold)
            self._send(0, 0, 0)
            self.sleep(self.gap)
        finally:
            self.release()

    def release(self):
        """Release the buttons if any are held."""
        if self.buttons:
            self._send(0, 0, 0)


def _points(coords):
    if len(coords) < 4 or len(coords) % 2:
        raise AmiberryError(f"a drag needs pairs of x, y for at least two positions, not {list(coords)}")
    return [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]


def _button(button):
    if button not in BUTTONS:
        raise AmiberryError(f"a mouse button is 'left' or 'right', not {button!r}")
    return BUTTONS[button]
