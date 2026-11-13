"""The emulated Amiga's memory, and the OS structures found in it (exec, dos, Intuition).

Offsets are from the Kickstart 3.1 includes, confirmed on a running Workbench (NOTES.md)."""
import os
import struct
from dataclasses import dataclass

from .link import AmiberryError

# exec
EXECBASE_AT = 4
CHKBASE = 0x26
THIS_TASK = 0x114
LIB_LIST = 0x17A
TASK_READY = 0x196
TASK_WAIT = 0x1A4
LN_TYPE = 8
LN_NAME = 0x0A
LIB_VERSION = 0x14
NT_PROCESS = 13
MAX_NODES = 1000

# dos
PR_SEGLIST = 0x80
PR_CLI = 0xAC
CLI_COMMAND_NAME = 0x10
CLI_MODULE = 0x3C
HUNK_HEADER = 0x3F3
MAX_SEGMENTS = 1000

# Intuition
IB_ACTIVE_WINDOW = 0x34
IB_FIRST_SCREEN = 0x3C
SC_LEFT, SC_TOP, SC_WIDTH, SC_HEIGHT = 8, 10, 12, 14
SC_MOUSE_Y, SC_MOUSE_X, SC_FLAGS, SC_TITLE = 16, 18, 20, 22
SC_BITMAP = 184
BM_BYTES_PER_ROW, BM_ROWS, BM_DEPTH, BM_PLANES = 0, 2, 5, 8
WBENCHSCREEN = 1
SCREENTYPE = 0x000F
SC_FIRST_WINDOW = 4
WD_LEFT, WD_TOP, WD_WIDTH, WD_HEIGHT = 4, 6, 8, 10
WD_FLAGS, WD_TITLE, WD_SCREEN, WD_LAYER = 24, 32, 46, 124
WFLG_BACKDROP = 0x00000100
WFLG_WBENCHWINDOW = 0x02000000
LR_FRONT, LR_BOUNDS = 0, 16          # a layer's front neighbour, and MinX, MinY, MaxX, MaxY
MAX_WINDOWS = 100


@dataclass(frozen=True)
class Library:
    name: str
    address: int
    version: int


@dataclass(frozen=True)
class BitMap:
    bytes_per_row: int
    rows: int
    depth: int
    planes: tuple


@dataclass(frozen=True)
class Screen:
    address: int
    left: int
    top: int
    width: int
    height: int
    title: str | None
    flags: int
    bitmap: BitMap

    @property
    def is_workbench(self):
        return self.flags & SCREENTYPE == WBENCHSCREEN

    def describe(self):
        return f"the {self.width} x {self.height} screen {self.title or '(no title)'!r}"


@dataclass(frozen=True)
class Window:
    address: int
    title: str | None
    screen: int
    left: int
    top: int
    width: int
    height: int
    flags: int = 0

    @property
    def is_workbench(self):
        """One of Workbench's own windows (its backdrop, root or drawer windows)."""
        return bool(self.flags & WFLG_WBENCHWINDOW)

    @property
    def is_backdrop(self):
        return bool(self.flags & WFLG_BACKDROP)


@dataclass(frozen=True)
class Hunk:
    """A program's hunk: its number in the hunk file, where its contents were loaded (None if
    the program has unloaded it) and its length in bytes."""
    number: int
    address: int | None
    length: int


@dataclass(frozen=True)
class _Loaded:
    """A seglist found in a process, and how it was found."""
    seglist: int
    where: str
    detached: bool


SIZES = {1: "byte", 2: "word", 4: "long"}


class Memory:
    """Reads and writes the Amiga's memory over the link, big-endian as the 68000 stores it."""

    def __init__(self, link):
        self.link = link
        self._intuition = None   # (ExecBase, IntuitionBase) once found

    # ---- reading and writing

    def read(self, address, size=4):
        """The byte, word or long (size 1, 2 or 4) at an address, unsigned."""
        _check(address, size)
        return int(self.link.send("READ_MEM", address, size)[0])

    def read_byte(self, address):
        return self.read(address, 1)

    def read_word(self, address):
        return self.read(address, 2)

    def read_long(self, address):
        return self.read(address, 4)

    def read_signed_word(self, address):
        value = self.read(address, 2)
        return value - 0x10000 if value & 0x8000 else value

    def write(self, address, size, value):
        """Write a byte, word or long (size 1, 2 or 4). Negative values are stored as the 68000 would."""
        _check(address, size)
        bits = 8 * size
        if not -(1 << bits - 1) <= value < 1 << bits:
            raise AmiberryError(f"{value} doesn't fit in a {SIZES[size]}")
        self.link.send("WRITE_MEM", address, size, value & ((1 << bits) - 1))

    def read_block(self, address, length):
        """`length` bytes from an address, read a long at a time."""
        if length < 0 or address < 0 or address + length > 1 << 32:
            raise AmiberryError(f"can't read {length} bytes at ${address:X}")
        out = bytearray()
        end = address + length
        while address < end:
            left = end - address
            if address & 1 or left == 1:
                size = 1
            elif address & 2 or left < 4:
                size = 2
            else:
                size = 4
            out += self.read(address, size).to_bytes(size, "big")
            address += size
        return bytes(out)

    def read_string(self, address, limit=256):
        """The NUL-ended string at an address (Latin-1), or None for a null pointer."""
        if address == 0:
            return None
        out = bytearray()
        while len(out) < limit:
            size = 1 if address & 1 else 4 - (address & 2)
            data = self.read(address, size).to_bytes(size, "big")
            if 0 in data:
                out += data[:data.index(0)]
                break
            out += data
            address += size
        return out[:limit].decode("latin-1")

    def read_bstr(self, bptr):
        """The BCPL string a BPTR points at (a length byte, then the characters)."""
        if bptr == 0:
            return None
        address = 4 * bptr
        length = self.read(address, 1)
        return self.read_block(address + 1, length).decode("latin-1")

    # ---- exec

    def exec_base(self):
        """ExecBase, once exec has set it up (its ChkBase is its complement)."""
        base = self.read_long(EXECBASE_AT)
        if base == 0 or base & 1 or self.read_long(base + CHKBASE) != (~base & 0xFFFFFFFF):
            raise AmiberryError("exec isn't running yet: ExecBase (the long at 4) isn't set")
        return base

    def nodes(self, header):
        """The nodes of the exec list whose header is at `header`, each once."""
        seen = []
        node = self.read_long(header)
        for _ in range(MAX_NODES):
            following = self.read_long(node)
            if following == 0:
                break
            if node not in seen:
                seen.append(node)
            node = following
        return seen

    def libraries(self):
        """The open libraries, in exec's list order."""
        base = self.exec_base()
        return [Library(self.read_string(self.read_long(n + LN_NAME)), n, self.read_word(n + LIB_VERSION))
                for n in self.nodes(base + LIB_LIST)]

    def library(self, name):
        """An open library by name, e.g. `intuition.library`."""
        base = self.exec_base()
        for n in self.nodes(base + LIB_LIST):
            if self.read_string(self.read_long(n + LN_NAME)) == name:
                return Library(name, n, self.read_word(n + LIB_VERSION))
        raise AmiberryError(f"no library called {name!r} is open")

    def tasks(self):
        """Every task and process (their addresses): the running one, then ready, then waiting.
        A task that moved between lists while they were read is given once."""
        base = self.exec_base()
        found = []
        this = self.read_long(base + THIS_TASK)
        if this:
            found.append(this)
        for header in (base + TASK_READY, base + TASK_WAIT):
            found += [n for n in self.nodes(header) if n not in found]
        return found

    def task_name(self, task):
        return self.read_string(self.read_long(task + LN_NAME))

    def is_process(self, task):
        return self.read_byte(task + LN_TYPE) == NT_PROCESS

    # ---- dos: running programs and their hunks

    def segments(self, seglist, limit=MAX_SEGMENTS):
        """(content address, length) of each segment of a seglist (a BPTR), at most `limit`."""
        found = []
        bptr = seglist
        while bptr and len(found) < limit:
            seg = 4 * bptr
            if seg < 4 or seg > 0xFFFFFFFB:
                break
            length = self.read_long(seg - 4) - 8
            if not 0 <= length < 1 << 24:
                break
            found.append((seg + 4, length))
            bptr = self.read_long(seg)
        return found

    def _loaded(self):
        """Every program seglist held by a process: a Shell's `cli_Module`, and a process's own
        seglist (`pr_SegList` entry 3), each seglist once, with the process's name and command."""
        found = {}
        for task in self.tasks():
            if not self.is_process(task):
                continue
            name = self.task_name(task)
            cli = self.read_long(task + PR_CLI)
            if cli:
                module = self.read_long(4 * cli + CLI_MODULE)
                if module and module not in found:
                    command = self.read_bstr(self.read_long(4 * cli + CLI_COMMAND_NAME)) or ""
                    found[module] = (_Loaded(module, f"the Shell process {name!r} running {command!r}", False),
                                     command)
            array = self.read_long(task + PR_SEGLIST)
            if array:
                seglist = self.read_long(4 * array + 12)
                if seglist and seglist not in found:
                    found[seglist] = (_Loaded(seglist, f"the process {name!r}", True), name)
        return list(found.values())

    def hunks(self, program):
        """The hunks of a running program, given by name or by its hunk file on the PC.

        A name (e.g. `wait`, `PC:OctaMED/OctaMED.patched`, `OctaMED`) is matched, case ignored and
        without its path, against the commands Shells are running and the names of processes.
        A hunk file (a path that exists on the PC) is matched by its hunk sizes against every
        loaded program, which also finds a program that detached from its Shell, whatever its
        process is called; hunks it unloaded when it detached are given with no address."""
        path = os.path.expanduser(str(program))
        if os.path.isfile(path):
            return self._hunks_by_file(path)
        return self._hunks_by_name(str(program))

    def _hunks_by_name(self, program):
        wanted = _file_part(program).lower()
        matches = [loaded for loaded, name in self._loaded() if _file_part(name).lower() == wanted]
        if not matches:
            raise AmiberryError(
                f"{program} isn't running: no Shell is running it and no process has its name "
                "(a program that detaches from its Shell is found by giving its hunk file)")
        if len(matches) > 1:
            raise AmiberryError(f"{program} is running more than once: in "
                                + " and ".join(m.where for m in matches))
        return [Hunk(n, address, length)
                for n, (address, length) in enumerate(self.segments(matches[0].seglist))]

    def _hunks_by_file(self, path):
        sizes = hunk_sizes(path)
        best = []        # (hunks not loaded, _Loaded, segments), the fewest not loaded
        for loaded, _ in self._loaded():
            segments = self.segments(loaded.seglist, len(sizes) + 1)
            skipped = len(sizes) - len(segments)
            if not 0 <= skipped < len(sizes) or [l for _, l in segments] != sizes[skipped:]:
                continue
            if skipped and not loaded.detached:
                continue
            if best and skipped > best[0][0]:
                continue
            if best and skipped < best[0][0]:
                best = []
            best.append((skipped, loaded, segments))
        name = os.path.basename(path)
        if not best:
            raise AmiberryError(f"{name} isn't running: no loaded program has the hunks of {path}")
        if len(best) > 1:
            raise AmiberryError(f"{name} is running more than once: in "
                                + " and ".join(b[1].where for b in best))
        skipped, _, segments = best[0]
        return ([Hunk(n, None, sizes[n]) for n in range(skipped)]
                + [Hunk(skipped + n, address, length) for n, (address, length) in enumerate(segments)])

    # ---- Intuition

    def intuition_base(self):
        exec_base = self.exec_base()
        if self._intuition is None or self._intuition[0] != exec_base:
            self._intuition = (exec_base, self.library("intuition.library").address)
        return self._intuition[1]

    def front_screen(self):
        """The front screen: position, size, title and bitmap, from Intuition."""
        address = self.read_long(self.intuition_base() + IB_FIRST_SCREEN)
        if address == 0:
            raise AmiberryError("Intuition has no screen open")
        return self.screen(address)

    def screen(self, address):
        word = self.read_signed_word
        bm = address + SC_BITMAP
        depth = self.read_byte(bm + BM_DEPTH)
        bitmap = BitMap(self.read_word(bm + BM_BYTES_PER_ROW), self.read_word(bm + BM_ROWS), depth,
                        tuple(self.read_long(bm + BM_PLANES + 4 * p) for p in range(min(depth, 8))))
        return Screen(address, word(address + SC_LEFT), word(address + SC_TOP),
                      word(address + SC_WIDTH), word(address + SC_HEIGHT),
                      self.read_string(self.read_long(address + SC_TITLE)),
                      self.read_word(address + SC_FLAGS), bitmap)

    def screen_mouse(self, screen_address):
        """The pointer's position (x, y) in a screen's own pixels, as Intuition keeps it."""
        return (self.read_signed_word(screen_address + SC_MOUSE_X),
                self.read_signed_word(screen_address + SC_MOUSE_Y))

    def active_window(self):
        """The window that has the keyboard, or None."""
        address = self.read_long(self.intuition_base() + IB_ACTIVE_WINDOW)
        if address == 0:
            return None
        return self.window(address)

    def window(self, address):
        word = self.read_signed_word
        return Window(address, self.read_string(self.read_long(address + WD_TITLE)),
                      self.read_long(address + WD_SCREEN), word(address + WD_LEFT),
                      word(address + WD_TOP), word(address + WD_WIDTH), word(address + WD_HEIGHT),
                      self.read_long(address + WD_FLAGS))

    def windows(self, screen_address):
        """The windows open on a screen, the most recently opened first."""
        found = []
        address = self.read_long(screen_address + SC_FIRST_WINDOW)
        while address and len(found) < MAX_WINDOWS:
            found.append(self.window(address))
            address = self.read_long(address)
        return found

    def covering(self, window):
        """The boxes (left, top, right, bottom, inclusive) of the layers in front of a window's:
        other windows and the screen's title bar."""
        boxes = []
        layer = self.read_long(window.address + WD_LAYER)
        if layer == 0:
            return boxes
        layer = self.read_long(layer + LR_FRONT)
        while layer and len(boxes) < MAX_WINDOWS:
            boxes.append(tuple(self.read_signed_word(layer + LR_BOUNDS + 2 * i) for i in range(4)))
            layer = self.read_long(layer + LR_FRONT)
        return boxes


def hunk_sizes(path):
    """The length in bytes of each hunk of an Amiga program file, from its hunk header."""
    with open(path, "rb") as f:
        data = f.read(64 * 1024)
    def long(i):
        if 4 * i + 4 > len(data):
            raise AmiberryError(f"{path} isn't an Amiga program: its hunk header is cut short")
        return struct.unpack_from(">I", data, 4 * i)[0]
    if len(data) < 4 or long(0) != HUNK_HEADER:
        raise AmiberryError(f"{path} isn't an Amiga program: it doesn't start with a hunk header")
    i = 1
    while long(i):                       # resident library names (none in practice)
        i += long(i) + 1
    first, last = long(i + 2), long(i + 3)
    i += 4
    sizes = []
    for _ in range(last - first + 1):
        size = long(i)
        i += 1
        if size >> 30 == 3:              # memory attributes in a long of their own
            i += 1
        sizes.append((size & 0x3FFFFFFF) * 4)
    return sizes


def _file_part(name):
    """A command or file name without its device and directories."""
    return name.replace(":", "/").rsplit("/", 1)[-1]


def _check(address, size):
    if size not in SIZES:
        raise AmiberryError(f"a memory size is 1, 2 or 4 bytes, not {size}")
    if not 0 <= address <= 0xFFFFFFFF - (size - 1):
        raise AmiberryError(f"${address:X} isn't an Amiga address")
    if size > 1 and address & 1:
        raise AmiberryError(f"can't access a {SIZES[size]} at the odd address ${address:X}")
