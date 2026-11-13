"""Screenshots in the Amiga's own pixels (design decision 8).

Amiberry's screenshot is its window: the display with a border, lores columns and non-interlaced
lines doubled. Where the front screen sits in it, and at what scale, is found once per screen by
matching a band of the screen's bitmap (read from memory) against the screenshot."""
import itertools
import os
import tempfile
import time
from dataclasses import dataclass

from PIL import Image, ImageChops

from .link import AmiberryError, NotRunning

SCALES = [(1, 1), (1, 2), (2, 1), (2, 2), (4, 1), (4, 2)]
BAND = 8                 # rows of the bitmap matched against the screenshot
POINTER_BOX = (-32, -16, 48, 40)    # around the pointer's position, in screen pixels: its sprite
MAX_BANDS = 4            # bands tried when one fits in more than one place
PAIRS = 8                # same-numbered cell pairs per colour number and line, to narrow placements
MAX_PAIRS = 48           # ... and in all


class Ambiguous(AmiberryError):
    """A band of the screen fits the screenshot in more than one place."""


@dataclass(frozen=True)
class Mapping:
    """Where a screen sits in Amiberry's screenshot: its top-left pixel and the scale per axis,
    for screenshots of the size it was found in."""
    left: int
    top: int
    scale_x: int
    scale_y: int
    shot_size: tuple


@dataclass(frozen=True)
class Comparison:
    """How an area of the screen compared with the picture expected there: how many pixels
    differ, the first that does (x, y on the screen), and where the screenshot and the
    difference picture were saved when any differ."""
    differing: int
    first: tuple | None
    shot_path: str | None = None
    diff_path: str | None = None

    @property
    def matches(self):
        return self.differing == 0


_saved = itertools.count(1)


class Screenshots:
    """Takes screenshots over the link and turns them into pictures of the front screen.
    Comparisons park the pointer out of the way first with `pointer`, if given."""

    def __init__(self, link, memory, pointer=None, save_dir=None, sleep=time.sleep,
                 clock=time.monotonic):
        self.link = link
        self.memory = memory
        self.pointer = pointer
        self.save_dir = save_dir or os.environ.get("AMIBERRY_SHOTS", "amiberry-shots")
        self.sleep = sleep
        self.clock = clock
        self.mappings = {}

    def raw(self, path=None):
        """Amiberry's own screenshot (its window, border and all), saved at `path` if given."""
        if path is not None:
            path = os.path.abspath(os.path.expanduser(path))
            self.link.send("SCREENSHOT", path)
            with Image.open(path) as image:
                return image.convert("RGB")
        handle, temp = tempfile.mkstemp(prefix="amiberry-shot-", suffix=".png")
        os.close(handle)
        try:
            self.link.send("SCREENSHOT", temp)
            with Image.open(temp) as image:
                return image.convert("RGB")
        finally:
            os.unlink(temp)

    def shot(self, path=None, raw_path=None):
        """A picture of the front screen in its own pixels (one per Amiga pixel, the border
        removed and doubled lines or columns undone), saved at `path` if given. The raw
        screenshot is kept at `raw_path` if given."""
        screen = self.memory.front_screen()
        mapping = self.mappings.get(_key(screen))
        raw = None
        if mapping is not None:
            raw = self.raw(raw_path)
            if raw.size != mapping.shot_size:
                mapping = None
        if mapping is None:
            mapping, raw = self.calibrate(screen, raw_path)
        picture = crop(raw, screen, mapping)
        if path is not None:
            picture.save(os.path.expanduser(path))
        return picture

    # ---- comparing

    def compare(self, area, expected, bits=4, park=True):
        """Compare an area of the front screen with the picture expected there.

        `area` is (left, top) or (left, top, width, height) in screen pixels; `expected` a picture
        (PIL image or file) of the area's size. Colours are compared to `bits` bits per gun: 4
        (the default) is the precision of OCS/ECS colours, 8 compares exactly. When pixels differ,
        the screenshot and a difference picture are saved (in `save_dir`) and their paths given."""
        want, name = _expected(expected)
        box = _box(area, want.size)
        screen = self.memory.front_screen()
        _inside(box, screen)
        if park:
            self.park(box, screen)
        got = self.shot()
        return self._compare(got, box, want, bits, name)

    def wait_for(self, area, expected, timeout=20, bits=4, park=True, interval=0.1):
        """Take screenshots until an area of the front screen matches the picture expected there,
        and give the comparison; after `timeout` seconds, stop with an error giving the paths of
        the last screenshot and its difference picture."""
        want, name = _expected(expected)
        box = _box(area, want.size)
        end = self.clock() + timeout
        parked_on = None
        problem = None
        last = None
        while True:
            try:
                screen = self.memory.front_screen()
                _inside(box, screen)
                if park and parked_on != screen.address:
                    self.park(box, screen)
                    parked_on = screen.address
                got = self.shot()
                last = got
                result = _count(got, box, want, bits)
                if result[0] == 0:
                    return Comparison(0, None)
                problem = None
            except NotRunning:
                raise
            except AmiberryError as e:
                problem = e                 # e.g. a screen still opening: keep waiting
            if self.clock() >= end:
                break
            self.sleep(interval)
        if last is not None and problem is None:
            c = self._compare(last, box, want, bits, name)
            raise AmiberryError(
                f"the screen didn't show {name} at x {box[0]}, y {box[1]} within {timeout:g} s: "
                f"{c.differing} pixels differ, the first at x {c.first[0]}, y {c.first[1]} "
                f"(screenshot {c.shot_path}, differences {c.diff_path})")
        path = self.save_raw(name)
        raise AmiberryError(f"the screen didn't show {name} at x {box[0]}, y {box[1]} within "
                            f"{timeout:g} s: {problem} (screenshot {path})")

    def park(self, box, screen):
        """If the pointer's sprite may cover an area, put the pointer in the bottom-right corner of
        the screen, else the first of the bottom-left, top-right and top-left corners clear of it."""
        if self.pointer is None:
            return
        if not _overlaps(_sprite(self.memory.screen_mouse(screen.address)), box):
            return
        corners = [(screen.width - 1, screen.height - 1), (0, screen.height - 1),
                   (screen.width - 1, 0), (0, 0)]
        clear = [c for c in corners if not _overlaps(_sprite(c), box)]
        self.pointer.move_to(*(clear or corners)[0], screen=screen)

    def _compare(self, got, box, want, bits, name):
        differing, first, mask = _count(got, box, want, bits)
        if not differing:
            return Comparison(0, None)
        stem = f"{_safe(name)}-{time.strftime('%Y%m%d-%H%M%S')}-{next(_saved)}"
        os.makedirs(self.save_dir, exist_ok=True)
        shot_path = os.path.abspath(os.path.join(self.save_dir, stem + "-shot.png"))
        diff_path = os.path.abspath(os.path.join(self.save_dir, stem + "-diff.png"))
        got.save(shot_path)
        difference_picture(got.crop(_corners(box)), mask).save(diff_path)
        return Comparison(differing, first, shot_path, diff_path)

    def save_raw(self, name):
        """Save Amiberry's own screenshot in `save_dir`; gives its path ("not taken" if it can't)."""
        os.makedirs(self.save_dir, exist_ok=True)
        path = os.path.abspath(os.path.join(
            self.save_dir, f"{_safe(name)}-{time.strftime('%Y%m%d-%H%M%S')}-{next(_saved)}-raw.png"))
        try:
            self.raw(path)
        except AmiberryError:
            return "not taken"
        return path

    # ---- where the screen is in a screenshot

    def calibrate(self, screen, raw_path=None):
        """Find where `screen` sits in a new screenshot and keep it: (the mapping, the screenshot).
        A band that fits in more than one place gives way to the next band down; a band that fits
        nowhere is read again once, in case it changed between reading it and the screenshot."""
        start, retried = 0, False
        for _ in range(MAX_BANDS + 1):
            band_top, band = self.band(screen, start)
            pointer = self.memory.screen_mouse(screen.address)
            raw = self.raw(raw_path)
            try:
                mapping = find_mapping(screen, raw, band_top, band, pointer)
            except Ambiguous:
                start = band_top + BAND
                continue
            except AmiberryError:
                if retried:
                    raise
                retried = True
                continue
            self.mappings[_key(screen)] = mapping
            return mapping, raw
        raise AmiberryError(f"can't tell where {screen.describe()} is in Amiberry's screenshot: "
                            f"{MAX_BANDS} bands of it each fit in more than one place")

    def band(self, screen, start=0):
        """The first band of BAND rows, from row `start` down, in which every row has more than one
        colour and not all rows are the same: (its first row, rows of colour numbers)."""
        bitmap = screen.bitmap
        if bitmap.depth == 0 or bitmap.depth > 8 or not all(bitmap.planes):
            raise AmiberryError(f"{screen.describe()} has no planar bitmap to find it by")
        row_bytes = (screen.width + 7) // 8
        rows = []
        for y in range(start, min(screen.height, bitmap.rows)):
            planes = [self.memory.read_block(plane + y * bitmap.bytes_per_row, row_bytes)
                      for plane in bitmap.planes]
            row = colour_numbers(planes, screen.width)
            rows = rows + [row] if len(set(row)) > 1 else []
            if len(rows) >= BAND and len({tuple(r) for r in rows[-BAND:]}) > 1:
                return y - BAND + 1, rows[-BAND:]
        raise AmiberryError(f"{screen.describe()} has no {BAND} rows in a row with more than one "
                            "colour each: nothing to find it by in a screenshot")


def colour_numbers(planes, width):
    """A row's colour numbers from its bitplane bytes (plane 0 first)."""
    row = [0] * width
    for p, data in enumerate(planes):
        bit = 1 << p
        for x in range(width):
            if data[x >> 3] & (0x80 >> (x & 7)):
                row[x] |= bit
    return row


def find_mapping(screen, raw, band_top, band, pointer):
    """The placement and scale at which, on each line, the screenshot's colour is a function of the
    band's colour numbers (pixels near the pointer, a sprite, left out). It is per line because
    the copper may change colours from one line to the next (ClassicWB's backdrop gradient does).
    No such placement is an error.

    For each scale, placements are first narrowed with whole-picture operations: cells on a line
    with the same number must show the same colour, and a few cells covering every number must not
    all show one colour. The placements left are then checked cell by cell, each cell's whole block of
    scaled pixels (so a placement one doubled line off doesn't fit)."""
    width, height = raw.size
    px, py = pointer
    x0, y0, x1, y1 = POINTER_BOX
    cells = [(x, band_top + y, n) for y, row in enumerate(band) for x, n in enumerate(row)
             if not (px + x0 <= x < px + x1 and py + y0 <= band_top + y < py + y1)]
    same, spread = _pairs(cells)
    # Cells of the rarest numbers on their line first: a wrong placement fails on them at once.
    count = {}
    for x, y, n in cells:
        count[y, n] = count.get((y, n), 0) + 1
    cells.sort(key=lambda c: count[c[1], c[2]])
    pixels = raw.load()
    found = []
    for sx, sy in SCALES:
        places_x = width - screen.width * sx + 1
        places_y = height - screen.height * sy + 1
        if places_x <= 0 or places_y <= 0:
            continue
        def shifted(cell):
            x, y = cell[0] * sx, cell[1] * sy
            return raw.crop((x, y, x + places_x, y + places_y))
        unequal = Image.new("L", (places_x, places_y), 0)       # same number, different colours
        for a, b in same:
            unequal = ImageChops.lighter(unequal, _differ(shifted(a), shifted(b)))
        varied = Image.new("L", (places_x, places_y), 0)         # not all one colour
        for a, b in spread:
            varied = ImageChops.lighter(varied, _differ(shifted(a), shifted(b)))
        ok = ImageChops.logical_and(ImageChops.invert(unequal).convert("1"), varied.convert("1"))
        data = ok.convert("L").tobytes()
        i = data.find(b"\xff")
        while i >= 0:
            left, top = i % places_x, i // places_x
            if _fits(cells, pixels, left, top, sx, sy):
                colours = {pixels[left + x * sx, top + y * sy] for x, y, _ in cells}
                found.append((len(colours), Mapping(left, top, sx, sy, raw.size)))
            i = data.find(b"\xff", i + 1)
    if not found:
        raise AmiberryError(
            f"can't find {screen.describe()} in Amiberry's {width} x {height} screenshot "
            "at any scale (1, 2 or 4 across, 1 or 2 down)")
    found.sort(key=lambda f: -f[0])
    best = [m for n, m in found if n == found[0][0]]
    if len(best) > 1:
        raise Ambiguous(
            f"{screen.describe()} fits Amiberry's screenshot in {len(best)} places "
            f"({best[0]} and {best[1]}); can't tell which")
    return best[0]


def _differ(a, b):
    """255 where two RGB pictures differ, 0 where they are the same."""
    return ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v else 0)


def _pairs(cells):
    """Pairs of cells on a line with the same colour number, spread along it (up to PAIRS per
    number and line), and pairs of cells joining one cell of each number in a chain."""
    by_line = {}
    by_number = {}
    for cell in cells:
        by_line.setdefault((cell[1], cell[2]), []).append(cell)
        by_number.setdefault(cell[2], []).append(cell)
    same = []
    per_group = max(2, PAIRS // max(1, len(by_line) // BAND))
    for group in sorted(by_line.values(), key=len):          # the rarest, most telling, first
        k = min(len(group), per_group)
        same += [(group[0], group[len(group) * j // k]) for j in range(1, k)]
    same = same[:MAX_PAIRS]
    firsts = [group[len(group) // 2] for group in by_number.values()]
    spread = list(zip(firsts, firsts[1:]))
    return same, spread


def _fits(cells, pixels, left, top, sx, sy):
    """True if on each line each colour number shows as one colour over each of its cells' whole
    blocks of scaled pixels, and not every number as the same colour."""
    colour_of = {}
    for x, y, n in cells:
        bx, by = left + x * sx, top + y * sy
        colour = colour_of.setdefault((y, n), pixels[bx, by])
        for dy in range(sy):
            for dx in range(sx):
                if pixels[bx + dx, by + dy] != colour:
                    return False
    return len(set(colour_of.values())) > 1


def _expected(expected):
    """The expected picture (RGB) and a name for it."""
    if isinstance(expected, Image.Image):
        return expected.convert("RGB"), "the expected picture"
    path = os.path.expanduser(str(expected))
    try:
        with Image.open(path) as image:
            return image.convert("RGB"), os.path.basename(path)
    except OSError as e:
        raise AmiberryError(f"can't read the expected picture {path}: {e}") from None


def _box(area, size):
    """(left, top, width, height) from an area of 2 or 4 numbers and the expected picture's size."""
    if len(area) == 2:
        return (area[0], area[1]) + tuple(size)
    if len(area) != 4:
        raise AmiberryError(f"an area is (left, top) or (left, top, width, height), not {area}")
    if tuple(area[2:]) != tuple(size):
        raise AmiberryError(f"the expected picture is {size[0]} x {size[1]} but the area is "
                            f"{area[2]} x {area[3]}")
    return tuple(area)


def _inside(box, screen):
    left, top, width, height = box
    if left < 0 or top < 0 or left + width > screen.width or top + height > screen.height:
        raise AmiberryError(f"the {width} x {height} area at x {left}, y {top} isn't inside "
                            f"{screen.describe()}")


def _corners(box):
    return (box[0], box[1], box[0] + box[2], box[1] + box[3])


def _sprite(position):
    """The box (left, top, width, height) the pointer's sprite may cover at a position."""
    x0, y0, x1, y1 = POINTER_BOX
    return (position[0] + x0, position[1] + y0, x1 - x0, y1 - y0)


def _overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _safe(name):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name).strip("._") or "area"


def reduce(image, bits):
    """A picture with each gun cut to its top `bits` bits."""
    if bits == 8:
        return image
    if not 1 <= bits <= 8:
        raise AmiberryError(f"colours are compared at 1 to 8 bits per gun, not {bits}")
    mask = 0xFF << (8 - bits) & 0xFF
    return image.point(lambda v: v & mask)


def _count(got, box, want, bits):
    """(pixels differing, the first one's screen position, a mask picture: 255 where they differ)."""
    area = got.crop(_corners(box))
    mask = ImageChops.difference(reduce(area, bits), reduce(want, bits)).convert("L")
    mask = mask.point(lambda v: 255 if v else 0)
    data = mask.tobytes()
    differing = data.count(255)
    if not differing:
        return 0, None, mask
    i = data.index(255)
    return differing, (box[0] + i % box[2], box[1] + i // box[2]), mask


def difference_picture(area, mask):
    """The area dimmed, with its differing pixels in red."""
    dim = area.point(lambda v: v // 3)
    return Image.composite(Image.new("RGB", area.size, (255, 0, 0)), dim, mask)


def _key(screen):
    return (screen.address, screen.width, screen.height, screen.bitmap.depth)


def crop(raw, screen, mapping):
    """The screen's own picture out of a screenshot, one pixel per Amiga pixel."""
    m = mapping
    box = (m.left, m.top, m.left + screen.width * m.scale_x, m.top + screen.height * m.scale_y)
    picture = raw.crop(box)
    if (m.scale_x, m.scale_y) != (1, 1):
        picture = picture.resize((screen.width, screen.height), Image.NEAREST)
    return picture
