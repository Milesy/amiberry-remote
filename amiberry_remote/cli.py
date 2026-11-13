"""The `amiberry-remote` command: the tool's operations by hand, on the running Amiberry."""
import argparse
import sys

from .link import AmiberryError
from .session import Amiga

SIZES = {"b": 1, "w": 2, "l": 4}


def number(text):
    """A number in decimal, `0x` hex or `$` hex."""
    t = text.strip()
    sign = -1 if t.startswith("-") else 1
    t = t.lstrip("+-")
    try:
        if t.startswith("$"):
            return sign * int(t[1:], 16)
        if t.lower().startswith("0x"):
            return sign * int(t[2:], 16)
        return sign * int(t, 10)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} isn't a number (decimal, 0x hex or $ hex)") from None


def hexa(value, digits=1):
    return f"${value:0{digits}X}"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"{self.prog}: {message} (see {self.prog.split()[0]} --help)\n")


def parser():
    p = Parser(prog="amiberry-remote", description="Drive the running Amiberry through its "
               "remote-control socket. Numbers: decimal, 0x hex or $ hex.")
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND", parser_class=Parser)

    def add(name, help, *args):
        s = sub.add_parser(name, help=help, description=help)
        for arg, kw in args:
            s.add_argument(arg, **kw)
        return s

    add("start", "start Amiberry with a config (or use the one running) and wait for Workbench",
        ("config", dict(metavar="CONFIG")),
        ("--timeout", dict(type=float, default=90, help="seconds to wait for Workbench (90)")))
    add("quit", "quit Amiberry and wait until it has gone")
    add("run", "open a new Shell and type each command into it",
        ("commands", dict(metavar="COMMAND", nargs="+")))
    add("key", "press keys in turn, e.g. Help, Ctrl-F2, RAmiga-E",
        ("names", dict(metavar="NAME", nargs="+")))
    add("type", "type text on the US keyboard (\\n for Return)", ("text", dict(metavar="TEXT")))
    add("pointer", "print the pointer's position on the front screen")
    add("click", "click at a position of the front screen",
        ("x", dict(type=number)), ("y", dict(type=number)),
        ("button", dict(nargs="?", choices=["left", "right"], default="left")))
    add("drag", "drag with the left button from one position to another",
        ("x1", dict(type=number)), ("y1", dict(type=number)),
        ("x2", dict(type=number)), ("y2", dict(type=number)))
    add("shot", "save a screenshot of the front screen in Amiga pixels",
        ("path", dict(metavar="PATH")),
        ("--raw", dict(metavar="RAW", help="also keep Amiberry's own screenshot here")))
    add("peek", "print the byte (b), word (w) or long (l, the default) at an address, or COUNT bytes",
        ("address", dict(type=number)), ("size", dict(nargs="?", default="l", metavar="b|w|l|COUNT")))
    add("poke", "write a byte, word or long",
        ("address", dict(type=number)), ("size", dict(choices=["b", "w", "l"])),
        ("value", dict(type=number)))
    add("library", "print an open library's address and version", ("name", dict(metavar="NAME")))
    add("hunks", "print a running program's hunks: number, address and length",
        ("program", dict(metavar="PROGRAM", help="its name, or its hunk file on the PC")))
    add("screen", "print the front screen's address, position, size, depth and title")
    add("send", "send one raw line to the socket and print the reply", ("line", dict(metavar="LINE")))
    return p


def run(args, out):
    if args.command == "start":
        Amiga.start(args.config, timeout=args.timeout)
        print("Workbench is up", file=out)
        return
    amiga = Amiga.connect()
    c = args.command
    if c == "quit":
        amiga.quit()
        print("Amiberry has quit", file=out)
    elif c == "run":
        amiga.run(*args.commands)
    elif c == "key":
        amiga.key(*args.names)
    elif c == "type":
        amiga.type(args.text.replace("\\n", "\n"))
    elif c == "pointer":
        x, y = amiga.pointer()
        print(f"{x} {y}", file=out)
    elif c == "click":
        amiga.click(args.x, args.y, args.button)
    elif c == "drag":
        amiga.drag(args.x1, args.y1, args.x2, args.y2)
    elif c == "shot":
        picture = amiga.shot(args.path, args.raw)
        print(f"{picture.width} x {picture.height}", file=out)
    elif c == "peek":
        peek(amiga, args.address, args.size, out)
    elif c == "poke":
        amiga.write(args.address, SIZES[args.size], args.value)
    elif c == "library":
        lib = amiga.library(args.name)
        print(f"{hexa(lib.address, 8)} version {lib.version}", file=out)
    elif c == "hunks":
        for h in amiga.hunks(args.program):
            where = hexa(h.address, 8) if h.address is not None else "not loaded"
            print(f"{h.number:3}  {where:>10}  {hexa(h.length)}", file=out)
    elif c == "screen":
        s = amiga.front_screen()
        print(f"{hexa(s.address, 8)}  {s.width} x {s.height} at {s.left}, {s.top}, "
              f"depth {s.bitmap.depth}, {'Workbench' if s.is_workbench else 'custom'}, "
              f"{s.title!r}", file=out)
    elif c == "send":
        reply = amiga.link.exchange(args.line)
        if reply.split("\t")[0].split("\n")[0] != "OK":
            raise AmiberryError(f"Amiberry refused {args.line!r}: {reply or 'no reply'}")
        print(reply, file=out)


def peek(amiga, address, size, out):
    if size in SIZES:
        print(hexa(amiga.read(address, SIZES[size]), 2 * SIZES[size]), file=out)
        return
    try:
        count = number(size)
    except argparse.ArgumentTypeError:
        raise AmiberryError(f"peek takes b, w, l or a count of bytes, not {size!r}") from None
    data = amiga.read_block(address, count)
    for i in range(0, len(data), 16):
        row = data[i:i + 16]
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        print(f"{hexa(address + i, 8)}: {row.hex(' '):<47}  {text}", file=out)


def main(argv=None, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    args = parser().parse_args(argv)
    try:
        run(args, out)
    except AmiberryError as e:
        print(f"amiberry-remote: {e}", file=err)
        return 1
    except KeyboardInterrupt:
        print("amiberry-remote: interrupted", file=err)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
