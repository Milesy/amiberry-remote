"""A fake Amiberry for the unit tests: serves the remote-control socket from a thread, with a
memory image that READ_MEM and WRITE_MEM act on, and a log of every command it was sent."""
import os
import socket
import struct
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from amiberry_remote.keys import CHARACTERS  # noqa: E402


class FakeAmiberry:
    """Answers commands as Amiberry 8.4.2 does: one line in, one line out, connection closed.
    `replies` overrides the reply to a command by its name (e.g. {"PING": "ERROR\\tbusy"})."""

    def __init__(self, path=None, memory_size=0x200000):
        self.dir = None
        if path is None:
            self.dir = tempfile.mkdtemp(prefix="fake-amiberry-")
            path = os.path.join(self.dir, "amiberry.sock")
        self.path = path
        self.memory = bytearray(memory_size)
        self.log = []
        self.replies = {}
        self.lock = threading.RLock()
        self.server = None
        self.thread = None
        self.next_free = 0x1000
        self.mouse_at = None        # the pointer in Intuition's units (hires columns, interlaced lines)
        self.mouse_blocked = False  # True: moves are ignored, as if something held the pointer
        self.mouse_buttons = 0
        self.button_events = []     # (buttons, position) at each change of the buttons
        self.mouse_track = []       # (position, buttons) after each SEND_MOUSE
        # The display as Amiberry shows it: screenshot size, where the front screen's top-left
        # pixel is, the scale per axis, and the border colour.
        self.display = dict(size=(756, 576), offset=(76, 38), scale=(1, 2), border=(0, 0, 0))
        self.pictures = {}          # screen -> "P" image of its colour numbers
        self.palettes = {}          # screen -> [(r, g, b)] per colour number
        self.show_pointer = True
        self.shots = []             # paths written by SCREENSHOT
        self.intuition_base = None
        self.layers = {}            # screen -> its layers, front to back
        self.window_of = {}         # layer -> window (the screen's title bar has none)
        self.keys_down = set()
        self.typed = {}             # window -> text typed into it since its last Return
        self.lines = []             # (window, line) for each Return
        self.requester = None       # Workbench's Execute Command requester, while open
        self.shell_activates = True # False: a new Shell window opens without the keyboard
        self.shells = []            # Shell windows opened with newshell
        self.quit_delay = 0.0       # seconds between answering QUIT and the socket going
        self.execute_text = ""      # the command the Execute Command requester remembers

    # ---- serving

    def start(self):
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen(8)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        """Stop answering and remove the socket, as Amiberry does when it quits."""
        server, self.server = self.server, None
        if server is not None:
            try:
                server.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            server.close()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(2)
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        if self.dir:
            try:
                os.rmdir(self.dir)
            except OSError:
                pass

    def _serve(self):
        while self.server is not None:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                line = data.decode("latin-1").rstrip("\n")
                quitting = False
                with self.lock:
                    self.log.append(line)
                    reply = self.handle(line)
                    if line.split("\t")[0] == "QUIT" and reply.startswith("OK"):
                        quitting = True
                try:
                    conn.sendall((reply + "\n").encode("latin-1"))
                except OSError:
                    pass
            if quitting:
                def stop_later():
                    time.sleep(self.quit_delay)
                    self.stop()
                threading.Thread(target=stop_later, daemon=True).start()
                return

    # ---- commands

    def handle(self, line):
        fields = line.split("\t")
        name = fields[0]
        if name in self.replies:
            return self.replies[name]
        method = getattr(self, "cmd_" + name, None)
        if method is None:
            return "ERROR\tunknown command"
        try:
            return method(*fields[1:])
        except (TypeError, ValueError, IndexError) as e:
            return f"ERROR\t{e}"

    def cmd_PING(self):
        return "OK\tPONG"

    def cmd_QUIT(self):
        return "OK"

    def cmd_READ_MEM(self, addr, width):
        addr, width = int(addr), int(width)
        if width not in (1, 2, 4) or addr < 0 or addr + width > 1 << 32:
            return "ERROR\tinvalid address or width"
        # Past the image (ROM, custom chips) reads as 0.
        return f"OK\t{int.from_bytes(self.memory[addr:addr + width].ljust(width, bytes(1)), 'big')}"

    def cmd_WRITE_MEM(self, addr, width, value):
        addr, width, value = int(addr), int(width), int(value)
        if width not in (1, 2, 4) or addr < 0 or addr + width > len(self.memory):
            return "ERROR\tinvalid address or width"
        self.memory[addr:addr + width] = (value & ((1 << 8 * width) - 1)).to_bytes(width, "big")
        return "OK"

    # ---- the memory image

    def commands(self, name=None):
        """The commands logged (their lines), or only those with the given name."""
        with self.lock:
            return [l for l in self.log if name is None or l.split("\t")[0] == name]

    def alloc(self, size, align=4):
        addr = (self.next_free + align - 1) // align * align
        self.next_free = addr + size
        if self.next_free > len(self.memory):
            raise MemoryError("fake memory full")
        return addr

    def put_byte(self, addr, value):
        self.memory[addr] = value & 0xFF

    def put_word(self, addr, value):
        self.memory[addr:addr + 2] = struct.pack(">H", value & 0xFFFF)

    def put_long(self, addr, value):
        self.memory[addr:addr + 4] = struct.pack(">I", value & 0xFFFFFFFF)

    def get_word(self, addr):
        return struct.unpack(">H", self.memory[addr:addr + 2])[0]

    def get_long(self, addr):
        return struct.unpack(">I", self.memory[addr:addr + 4])[0]

    def put_bytes(self, addr, data):
        self.memory[addr:addr + len(data)] = data

    def put_string(self, text):
        """A NUL-ended string in new memory; gives its address."""
        data = text.encode("latin-1") + b"\0"
        addr = self.alloc(len(data), 2)
        self.put_bytes(addr, data)
        return addr

    # ---- exec

    def new_list(self, header):
        self.put_long(header, header + 4)
        self.put_long(header + 4, 0)
        self.put_long(header + 8, header)

    def add_tail(self, header, node):
        last = self.get_long(header + 8)
        self.put_long(node, header + 4)
        self.put_long(node + 4, last)
        self.put_long(last, node)
        self.put_long(header + 8, node)

    def remove_node(self, node):
        following, previous = self.get_long(node), self.get_long(node + 4)
        self.put_long(previous, following)
        self.put_long(following + 4, previous)

    def boot_exec(self):
        """ExecBase at 4 with its library and task lists, exec.library in the list."""
        base = self.alloc(0x300)
        self.exec_base = base
        self.put_long(4, base)
        self.put_long(base + 0x26, ~base)
        for header in (0x17A, 0x196, 0x1A4):
            self.new_list(base + header)
        self._name_node(base, "exec.library", 9)
        self.put_word(base + 0x14, 40)
        self.add_tail(base + 0x17A, base)
        return base

    def _name_node(self, node, name, node_type):
        self.put_byte(node + 8, node_type)
        self.put_long(node + 10, self.put_string(name))

    def add_library(self, name, version=40, size=0x80):
        lib = self.alloc(size)
        self._name_node(lib, name, 9)
        self.put_word(lib + 0x14, version)
        self.add_tail(self.exec_base + 0x17A, lib)
        return lib

    def add_task(self, name, process=True, waiting=True):
        task = self.alloc(0x100)
        self._name_node(task, name, 13 if process else 1)
        self.add_tail(self.exec_base + (0x1A4 if waiting else 0x196), task)
        return task

    def set_this_task(self, task):
        self.put_long(self.exec_base + 0x114, task)

    # ---- dos: seglists, Shells and detached programs

    def make_seglist(self, lengths):
        """Segments of these content lengths, chained; gives the first segment's BPTR and the
        segments' (content address, length) pairs."""
        segments = []
        for length in lengths:
            block = self.alloc(length + 8)
            self.put_long(block, length + 8)
            segments.append(block + 4)
        for seg, following in zip(segments, segments[1:] + [0]):
            self.put_long(seg, following // 4)
        return segments[0] // 4, [(seg + 4, length) for seg, length in zip(segments, lengths)]

    def put_bstr(self, text):
        data = text.encode("latin-1")
        addr = self.alloc(len(data) + 1)
        self.put_byte(addr, len(data))
        self.put_bytes(addr + 1, data)
        return addr // 4

    def add_shell(self, command, lengths, name="Shell Process"):
        """A Shell process running `command`, loaded as segments of these lengths."""
        proc = self.add_task(name)
        cli = self.alloc(0x40)
        self.put_long(proc + 0xAC, cli // 4)
        self.put_long(cli + 0x10, self.put_bstr(command))
        seglist, segments = self.make_seglist(lengths) if lengths else (0, [])
        self.put_long(cli + 0x3C, seglist)
        return proc, segments

    def add_detached(self, name, lengths):
        """A process of its own (no CLI) whose seglist is in its pr_SegList entry 3."""
        proc = self.add_task(name)
        array = self.alloc(24)
        self.put_long(array, 2)
        seglist, segments = self.make_seglist(lengths)
        self.put_long(array + 12, seglist)
        self.put_long(proc + 0x80, array // 4)
        return proc, segments

    # ---- Intuition

    def boot_intuition(self):
        self.intuition_base = self.add_library("intuition.library", 40)
        return self.intuition_base

    def add_screen(self, width, height, depth, title, workbench=False, interleaved=False,
                   left=0, top=0):
        """A screen with a cleared bitmap, put in front."""
        sc = self.alloc(0x160)
        self.put_word(sc + 8, left)
        self.put_word(sc + 10, top)
        self.put_word(sc + 12, width)
        self.put_word(sc + 14, height)
        self.put_word(sc + 20, 0x0001 if workbench else 0x000F)
        self.put_long(sc + 22, self.put_string(title) if title is not None else 0)
        row = (width + 15) // 16 * 2
        bm = sc + 184
        self.put_word(bm + 2, height)
        self.put_byte(bm + 5, depth)
        planes = self.alloc(row * height * depth)
        if interleaved:
            self.put_word(bm, row * depth)
            for p in range(depth):
                self.put_long(bm + 8 + 4 * p, planes + p * row)
        else:
            self.put_word(bm, row)
            for p in range(depth):
                self.put_long(bm + 8 + 4 * p, planes + p * row * height)
        self.put_long(sc, self.get_long(self.intuition_base + 0x3C))
        self.put_long(self.intuition_base + 0x3C, sc)
        self.layers[sc] = [self._layer(0, 0, width - 1, 10)]
        self._relink(sc)
        return sc

    def _layer(self, left, top, right, bottom):
        layer = self.alloc(0x40)
        for i, v in enumerate((left, top, right, bottom)):
            self.put_word(layer + 16 + 2 * i, v)
        return layer

    def _relink(self, screen):
        layers = self.layers[screen]
        for i, layer in enumerate(layers):
            self.put_long(layer, layers[i - 1] if i > 0 else 0)                       # front
            self.put_long(layer + 4, layers[i + 1] if i + 1 < len(layers) else 0)     # back

    def add_window(self, screen, title, left=0, top=0, width=200, height=100, active=True,
                   backdrop=False, workbench=False):
        """A window, in front of the others (a backdrop window behind them all)."""
        win = self.alloc(0x100)
        for off, value in ((4, left), (6, top), (8, width), (10, height)):
            self.put_word(win + off, value)
        self.put_long(win + 24, (0x100 if backdrop else 0) | (0x02000000 if workbench else 0))
        self.put_long(win + 32, self.put_string(title) if title is not None else 0)
        self.put_long(win + 46, screen)
        self.put_long(win, self.get_long(screen + 4))
        self.put_long(screen + 4, win)
        layer = self._layer(left, top, left + width - 1, top + height - 1)
        self.put_long(win + 124, layer)
        self.window_of[layer] = win
        if backdrop:
            self.layers[screen].append(layer)
        else:
            self.layers[screen].insert(0, layer)
        self._relink(screen)
        if active:
            self.activate(win)
        return win

    def close_window(self, win, activate=None):
        screen = self.get_long(win + 46)
        address, previous = screen + 4, None
        while self.get_long(address) != win:
            address = self.get_long(address)
        self.put_long(address, self.get_long(win))
        layer = self.get_long(win + 124)
        self.layers[screen].remove(layer)
        del self.window_of[layer]
        self._relink(screen)
        if self.active() == win:
            self.activate(activate or 0)

    def activate(self, win):
        self.put_long(self.intuition_base + 0x34, win)

    def active(self):
        return self.get_long(self.intuition_base + 0x34)

    def window_at(self, x, y):
        """The window whose layer is frontmost at a screen position (None: the title bar or none)."""
        screen = self.get_long(self.intuition_base + 0x3C)
        for layer in self.layers.get(screen, []):
            left, top, right, bottom = (self.get_word(layer + 16 + 2 * i) for i in range(4))
            if left <= x <= right and top <= y <= bottom:
                return self.window_of.get(layer)
        return None

    def boot_workbench(self, width=640, height=256, depth=2):
        """exec, a few libraries, Intuition with the Workbench screen and its backdrop window
        active, and a Workbench process."""
        self.boot_exec()
        self.add_library("graphics.library", 40)
        self.boot_intuition()
        self.add_library("dos.library", 40)
        self.add_task("input.device", process=False)
        self.workbench_task = self.add_task("Workbench")
        self.workbench_screen = self.add_screen(
            width, height, depth, "Workbench Screen", workbench=True, interleaved=True)
        self.backdrop = self.add_window(self.workbench_screen, None, 0, 11, width, height - 11,
                                        backdrop=True, workbench=True)
        return self

    # ---- keyboard

    def cmd_SEND_KEY(self, code, state):
        code, state = int(code), int(state)
        if not 0 <= code <= 0x7F or state not in (0, 1):
            return "ERROR\tinvalid key code or state"
        if not state:
            self.keys_down.discard(code)
            return "OK"
        self.keys_down.add(code)
        if self.intuition_base is None or code in (0x60, 0x61, 0x63, 0x64, 0x65, 0x66, 0x67):
            return "OK"
        active = self.active()
        if 0x67 in self.keys_down:                      # Right Amiga: a menu shortcut
            if code == 0x12 and active and self.get_long(active + 24) & 0x02000000 \
                    and self.requester is None:
                self.before_requester = active
                self.requester = self.add_window(self.workbench_screen, "Execute a File",
                                                 0, 11, 400, 67)
                self.typed[self.requester] = self.execute_text     # it keeps the last command
            elif code == 0x32 and active:                           # X in a string gadget: clear
                self.typed[active] = ""
            return "OK"
        if code == 0x44:                                # Return
            line = self.typed.pop(active, "")
            self.lines.append((active, line))
            if active and active == self.requester:
                self.execute_text = line
                self.requester = None
                self.close_window(active, self.before_requester)
                if line == "newshell":
                    width = self.get_word(self.workbench_screen + 12)
                    self.shells.append(self.add_window(self.workbench_screen, "AmigaShell", 0, 0,
                                                       width, 130, active=self.shell_activates))
            return "OK"
        shifted = bool(self.keys_down & {0x60, 0x61})
        for ch, (c, shift) in CHARACTERS.items():
            if c == code and shift == shifted and ch not in "\n\t":
                self.typed[active] = self.typed.get(active, "") + ch
                break
        return "OK"

    def shell_lines(self):
        """The lines typed into Shell windows opened with newshell."""
        return [line for win, line in self.lines if win in self.shells]

    def key_events(self):
        """(code, down) for each SEND_KEY received."""
        return [(int(c), s == "1") for _, c, s in (l.split("\t") for l in self.commands("SEND_KEY"))]

    # ---- mouse

    def mouse_accelerate(self, counts):
        """Workbench-like speed-up: moves of more than 4 counts go twice as far."""
        return counts * 2 if abs(counts) > 4 else counts

    def _mouse_screen(self):
        sc = self.get_long(self.intuition_base + 0x3C)
        width, height = self.get_word(sc + 12), self.get_word(sc + 14)
        return sc, width, height, (1 if width >= 640 else 2), (2 if height <= 300 else 1)

    def put_mouse(self, x, y):
        """Put the pointer on x, y of the front screen."""
        sc, width, height, sx, sy = self._mouse_screen()
        self.mouse_at = [x * sx, y * sy]
        self._show_mouse()

    def mouse(self):
        sc = self.get_long(self.intuition_base + 0x3C)
        return self.get_word(sc + 18), self.get_word(sc + 16)

    def _show_mouse(self):
        sc, width, height, sx, sy = self._mouse_screen()
        self.mouse_at[0] = max(0, min(width * sx - 1, self.mouse_at[0]))
        self.mouse_at[1] = max(0, min(height * sy - 1, self.mouse_at[1]))
        self.put_word(sc + 18, self.mouse_at[0] // sx)
        self.put_word(sc + 16, self.mouse_at[1] // sy)

    def cmd_SEND_MOUSE(self, dx, dy, buttons):
        dx, dy, buttons = int(dx), int(dy), int(buttons)
        if self.mouse_at is None:
            self.put_mouse(0, 0)
        if not self.mouse_blocked:
            self.mouse_at[0] += self.mouse_accelerate(dx)
            self.mouse_at[1] += self.mouse_accelerate(dy)
            self._show_mouse()
        if buttons != self.mouse_buttons:
            self.button_events.append((buttons, self.mouse()))
            if buttons & 1 and not self.mouse_buttons & 1:
                win = self.window_at(*self.mouse())
                if win:
                    self.activate(win)
            self.mouse_buttons = buttons
        self.mouse_track.append((self.mouse(), buttons))
        return "OK"

    # ---- the display and SCREENSHOT

    def draw(self, screen, picture, palette=None):
        """Put a picture (a "P" image of colour numbers, the screen's size) in a screen's bitmap."""
        from PIL import Image
        width, height = self.get_word(screen + 12), self.get_word(screen + 14)
        assert picture.size == (width, height), picture.size
        bm = screen + 184
        bpr, depth = self.get_word(bm), self.memory[bm + 5]
        planes = [self.get_long(bm + 8 + 4 * p) for p in range(depth)]
        data = picture.tobytes()
        row_bytes = (width + 15) // 16 * 2
        for y in range(height):
            row = data[y * width:(y + 1) * width]
            for p, plane in enumerate(planes):
                bit = 1 << p
                packed = bytearray(row_bytes)
                for x, n in enumerate(row):
                    if n & bit:
                        packed[x >> 3] |= 0x80 >> (x & 7)
                self.put_bytes(plane + y * bpr, packed)
        self.pictures[screen] = picture.copy()
        if palette is not None:
            self.palettes[screen] = palette
        elif screen not in self.palettes:
            self.palettes[screen] = default_palette(depth)

    def screen_image(self, screen):
        """The screen as Amiberry would show it: its picture in its palette's colours."""
        from PIL import Image
        width, height = self.get_word(screen + 12), self.get_word(screen + 14)
        picture = self.pictures.get(screen) or Image.new("P", (width, height), 0)
        palette = self.palettes.get(screen) or default_palette(self.memory[screen + 184 + 5])
        image = picture.copy()
        flat = [v for rgb in palette for v in rgb]
        image.putpalette(flat + [0] * (768 - len(flat)))
        return image.convert("RGB")

    def framebuffer(self):
        from PIL import Image
        if self.intuition_base is None or not self.get_long(self.intuition_base + 0x3C):
            return Image.new("RGB", self.display["size"], self.display["border"])
        screen = self.get_long(self.intuition_base + 0x3C)
        shown = self.screen_image(screen)
        sx, sy = self.display["scale"]
        shown = shown.resize((shown.width * sx, shown.height * sy), Image.NEAREST)
        frame = Image.new("RGB", self.display["size"], self.display["border"])
        ox, oy = self.display["offset"]
        frame.paste(shown, (ox, oy))
        if self.show_pointer and self.mouse_at is not None:
            mx, my = self.mouse()
            x, y = ox + mx * sx, oy + my * sy
            for dy in range(6 * sy):          # a small arrow-ish sprite at the hot spot
                for dx in range(max(1, 6 * sx - dy)):
                    if 0 <= x + dx < frame.width and 0 <= y + dy < frame.height:
                        frame.putpixel((x + dx, y + dy), (255, 0, 255))
        return frame

    def cmd_SCREENSHOT(self, path):
        self.framebuffer().save(path)
        self.shots.append(path)
        return f"OK\t{path}"


def default_palette(depth):
    """A palette with every colour different."""
    return [((n * 67) % 256, (n * 151 + 40) % 256, (n * 23 + 90) % 256) for n in range(1 << depth)]


def main():
    """Run as a stand-in for the Amiberry program: `fake_amiberry.py --config FILE -G`. Serves
    on $AMIBERRY_SOCKET, booted to Workbench, until QUIT; writes its arguments to
    $FAKE_AMIBERRY_ARGS if set."""
    args_file = os.environ.get("FAKE_AMIBERRY_ARGS")
    if args_file:
        with open(args_file, "w") as f:
            f.write("\n".join(sys.argv[1:]))
    fake = FakeAmiberry(os.environ["AMIBERRY_SOCKET"])
    fake.boot_workbench()
    fake.start()
    fake.thread.join()


if __name__ == "__main__":
    main()
